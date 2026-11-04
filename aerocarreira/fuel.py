"""Combustível sob controle do addon: inventário SQLite e sincronização segura.

O motor NÃO cria combustível. Primeira calibração só é permitida no solo; os
níveis posteriores devem resultar de consumo observado ou de abastecimento pago.
Comandos de escrita de tanque são enviados exclusivamente ao worker SimConnect.
"""
from __future__ import annotations
import json
from math import isfinite
from time import time, time_ns
from .finance import AIRCRAFT_ECONOMY, FUEL_BRL_PER_LITER, LITERS_PER_GALLON

# Variáveis individuais settable pelo SimConnect; TOTAL_QUANTITY é leitura apenas.
TANKS = ('LEFT_MAIN','RIGHT_MAIN','CENTER','LEFT_AUX','RIGHT_AUX',
         'CENTER2','CENTER3','LEFT_TIP','RIGHT_TIP','EXTERNAL1','EXTERNAL2')
TANK_QUANTITY = {x: 'FUEL_TANK_'+x+'_QUANTITY' for x in TANKS}
TANK_CAPACITY = {x: 'FUEL_TANK_'+x+'_CAPACITY' for x in TANKS}


def valid_tanks(tanks, total=None, capacities=None):
    if not isinstance(tanks, dict) or not tanks:
        return False
    if any(k not in TANKS or not isinstance(v,(float,int)) or not isfinite(v) or v < 0 for k,v in tanks.items()):
        return False
    if total is not None and (not isfinite(total) or abs(sum(tanks.values())-total) > max(.45,total*.02)):
        return False  # não escrever num avião com tanques não identificados
    if capacities:
        for key,value in tanks.items():
            cap=capacities.get(key)
            if cap is not None and (not isfinite(cap) or value > cap + .3):
                return False
    return True


class FuelManager:
    """Reconciliação feita na thread da UI; escrita é comando para o worker.

    Aceita somente consumo gradual; aumentos e quedas súbitas são restaurados.
    Sem telemetria suficiente, jamais tenta alterar os tanques do simulador.
    """
    def __init__(self, storage, clock=time):
        self.db=storage
        self.clock=clock
        self.last_seen={}
        self.last_correction={}
        self.restore_attempts={}
        self.awaiting={}

    def get(self, ref):
        row=self.db.conn.execute('SELECT model,tanks_json,caps_json,updated_utc FROM fleet_fuel WHERE aircraft_ref=?',(ref,)).fetchone()
        if not row:return None
        return {'model':row[0], 'tanks':json.loads(row[1]), 'capacities':json.loads(row[2]),'updated_at':row[3]}

    def _save(self, ref, model, tanks, capacities):
        with self.db.conn:
            self.db.conn.execute('''INSERT INTO fleet_fuel(aircraft_ref,model,tanks_json,caps_json,updated_utc)
                VALUES(?,?,?,?,?) ON CONFLICT(aircraft_ref) DO UPDATE SET model=excluded.model,
                tanks_json=excluded.tanks_json,caps_json=excluded.caps_json,updated_utc=excluded.updated_utc''',
                (ref,model,json.dumps(tanks,sort_keys=True),json.dumps(capacities,sort_keys=True),self.clock()))

    def observe(self, ref, model, observed, total, on_ground, capacities=None, enabled=True):
        """Retorna (status, correção?) ou None; a correção contém nomes de tanques.

        Na primeira vez aceita leitura de combustível inicial SOMENTE em solo.
        Falha de leitura / tanques parciais = sem escrita, sem supor fuel restante.
        """
        if total is None or model not in AIRCRAFT_ECONOMY or not valid_tanks(observed,total,capacities):
            return 'unsupported', None
        now=self.clock()
        old=self.get(ref)
        caps={k:float(v) for k,v in (capacities or {}).items() if k in observed and isinstance(v,(int,float)) and isfinite(v) and v>0}
        if old is None:
            if not on_ground:return 'uninitialized',None
            self._save(ref,model,observed,caps)
            self.last_seen[ref]=now
            return 'calibrated',None
        if old['model']!=model or set(old['tanks'])!=set(observed):
            return 'mismatch',None # não transferir combustível de outro avião/tanques
        expected=old['tanks']
        if caps and old['capacities']:
            if any(abs(caps.get(k,0)-old['capacities'].get(k,0))>max(.5,old['capacities'].get(k,0)*.05)
                   for k in expected):
                return 'mismatch',None  # capacidade trocada: não sobrescrever outro modelo/tanque
        if caps and caps!=old['capacities']:
            old['capacities']=caps
        first_read=ref not in self.last_seen
        elapsed=max(0,now-self.last_seen.get(ref,now))
        self.last_seen[ref]=now
        # Primeiro sample após reiniciar: NÃO inferir consumo por dias offline.
        # A cópia SQLite é autoritativa ao iniciar no chão, e deve ser restaurada.
        if first_read and enabled and on_ground:
            mismatch=any(abs(float(observed[k])-expected[k])>.15 for k in expected)
            if mismatch:
                if not old['capacities'] or set(old['capacities'])!=set(expected):
                    return 'read_only',None
                self.last_correction[ref]=now
                self.restore_attempts[ref]=1
                self.awaiting[ref]=dict(expected)
                return 'restore',dict(expected)
        elif first_read and not on_ground:
            # Reabertura em voo: não acrescentar combustível ao avião em voo.
            return 'awaiting_ground',None
        # No modo desligado aceitamos consumo mas não permitimos acumular
        # combustível inserido manualmente para obter combustível grátis depois.
        if not enabled:
            reduced={k:min(expected[k],float(observed[k])) for k in expected}
            if reduced!=expected or caps:
                self._save(ref,model,reduced,old['capacities'])
            return 'disabled',None
        per_second=AIRCRAFT_ECONOMY[model].fuel_lph/LITERS_PER_GALLON/3600
        max_drop=max(.12,elapsed*per_second*4+.12)
        total_drop=sum(expected.values())-sum(observed.values())
        increase=any(observed[k]>expected[k]+.12 for k in expected)
        # Corrigir manipulações do menu do simulador e saltos sem causa física.
        invalid_drop=total_drop>max_drop or any(observed[k]<0 for k in expected)
        if not increase and not invalid_drop:
            self.restore_attempts.pop(ref,None)
            self.awaiting.pop(ref,None)
            reduced={k:min(expected[k],float(observed[k])) for k in expected}
            if reduced!=expected or caps:
                burned=max(0,sum(expected.values())-sum(reduced.values()))*LITERS_PER_GALLON
                self._reduce_refundable(ref,burned)
                self._save(ref,model,reduced,old['capacities'])
            return 'consuming',None
        if not old['capacities'] or set(old['capacities'])!=set(expected):
            return 'read_only',None
        if self.restore_attempts.get(ref,0)>=3:
            return 'write_not_confirmed',None
        if now-self.last_correction.get(ref,-1e12)<2.5:
            return 'awaiting_write',None
        self.last_correction[ref]=now
        self.restore_attempts[ref]=self.restore_attempts.get(ref,0)+1
        self.awaiting[ref]=dict(expected)
        return 'restore',dict(expected)

    def _refundable(self,ref):
        return max(0,float(self.db.get_setting('fuel_refundable_liters:'+ref) or 0))

    def _reduce_refundable(self,ref,burned_liters):
        if burned_liters<=.0001:return
        self.db.set_setting('fuel_refundable_liters:'+ref,
            str(round(max(0,self._refundable(ref)-burned_liters),5)))

    def pending(self,ref):
        raw=self.db.get_setting('fuel_pending_adjustment:'+ref)
        if not raw:return None
        try:return json.loads(raw)
        except (ValueError,TypeError):return None

    def confirm_pending(self,ref):
        if not self.pending(ref):return False
        with self.db.conn:
            self.db.conn.execute("DELETE FROM settings WHERE key=?",('fuel_pending_adjustment:'+ref,))
        return True

    def rollback_pending(self,ref):
        """Estorno idempotente quando a DLL recusa o envio ou a leitura falha."""
        pending=self.pending(ref)
        if not pending:return None
        with self.db.conn:
            amount=-int(pending['amount'])
            old_balance=int(self.db.get_setting('balance') or 0)
            balance=old_balance+amount
            self.db._ledger_in_transaction('refund-failed:'+pending['event_key'],
                'estorno_abastecimento',amount,balance,
                'Reversão por falha de escrita no MSFS: '+ref)
            self.db.conn.execute("""INSERT INTO settings(key,value) VALUES('balance',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",(str(balance),))
            self.db.conn.execute('UPDATE fleet_fuel SET tanks_json=?,updated_utc=? WHERE aircraft_ref=?',
                (json.dumps(pending['old_tanks'],sort_keys=True),self.clock(),ref))
            self.db.conn.execute("""INSERT INTO settings(key,value) VALUES(?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                ('fuel_refundable_liters:'+ref,str(pending['old_credit'])))
            self.db.conn.execute("DELETE FROM settings WHERE key=?",('fuel_pending_adjustment:'+ref,))
        self.awaiting.pop(ref,None)
        self.restore_attempts.pop(ref,None)
        self.last_correction.pop(ref,None)
        return pending['old_tanks']

    def change_liters(self, ref, target_liters):
        """Alvo absoluto por aeronave, transação única do inventário e caixa.

        Reembolsa somente o volume COMPRADO e ainda não consumido nesta
        versão, evitando explorar combustível inicial gratuito do MSFS.
        """
        if not isinstance(target_liters,(int,float)) or not isfinite(target_liters):
            raise ValueError('Quantidade de litros inválida.')
        if self.pending(ref):
            raise ValueError('Abastecimento anterior aguarda confirmação do MSFS.')
        old=self.get(ref)
        if not old or not old['capacities'] or set(old['tanks'])!=set(old['capacities']):
            raise ValueError('Calibre tanques no solo antes de abastecer.')
        if self.db.get_setting('fuel_control_enabled')!='1':
            raise ValueError('Ative o controle de combustível.')
        if not self.db.fleet_manager().get(ref):
            raise ValueError('Aeronave própria/alugada não encontrada.')
        caps=old['capacities']
        total_capacity=sum(caps.values())*LITERS_PER_GALLON
        if not (0<=target_liters<=total_capacity+.05):
            raise ValueError(f'Informe um valor de 0 a {total_capacity:.1f} litros.')
        target_liters=min(float(target_liters),total_capacity)
        current=sum(old['tanks'].values())*LITERS_PER_GALLON
        difference=target_liters-current
        if abs(difference)<.20:
            raise ValueError('Quantidade já está no nível selecionado.')
        # Distribuir conforme capacidade dos tanques, preservando simetria lateral.
        new={name:round(caps[name]*(target_liters/total_capacity),5) for name in caps}
        if not valid_tanks(new,capacities=caps):raise ValueError('Balanceamento de tanques inválido.')
        paid=self._refundable(ref)
        refund_liters=min(max(0,-difference),paid)
        amount=(-max(1,round(difference*FUEL_BRL_PER_LITER)) if difference>0
                else round(refund_liters*FUEL_BRL_PER_LITER))
        next_credit=(paid+max(difference,0)) if difference>0 else max(0,paid-refund_liters)
        event_key='fuel-adjust:'+ref+':'+str(time_ns())
        with self.db.conn:
            if amount:
                self.db._money_movement(event_key,
                    'abastecimento' if amount<0 else 'devolucao_combustivel',amount,
                    f'Combustível {difference:+.1f} L — {ref}')
            self.db.conn.execute('UPDATE fleet_fuel SET tanks_json=?,updated_utc=? WHERE aircraft_ref=?',
                (json.dumps(new,sort_keys=True),self.clock(),ref))
            self.db.conn.execute("""INSERT INTO settings(key,value) VALUES(?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                ('fuel_pending_adjustment:'+ref,json.dumps({
                    'event_key':event_key,'amount':amount,'old_tanks':old['tanks'],
                    'old_credit':paid,'new_tanks':new})))
            self.db.conn.execute("""INSERT INTO settings(key,value) VALUES(?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                ('fuel_refundable_liters:'+ref,str(round(next_credit,5))))
        self.awaiting[ref]=dict(new)
        self.restore_attempts.pop(ref,None)
        self.last_correction.pop(ref,None)
        return {'tanks':new,'delta_liters':round(difference,2),'target_liters':round(target_liters,2),
                'cost_brl':max(0,-amount),'refund_brl':max(0,amount),
                'nonrefundable_return_liters':round(max(0,-difference)-refund_liters,2),
                'event_key':event_key}

    def refuel_full(self,ref):
        old=self.get(ref)
        if not old or not old['capacities']:
            raise ValueError('Calibre tanques antes de completar.')
        result=self.change_liters(ref,sum(old['capacities'].values())*LITERS_PER_GALLON)
        return dict(result,added_gal=round(max(0,sum(result['tanks'].values())-sum(old['tanks'].values())),5),
                    total_gal=round(sum(result['tanks'].values()),5))