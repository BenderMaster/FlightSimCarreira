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
        elapsed=max(0,now-self.last_seen.get(ref,old['updated_at']))
        self.last_seen[ref]=now
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
            # Ignorar flutuação positiva de até 0.12 gal; não aumentar o inventário.
            reduced={k:min(expected[k],float(observed[k])) for k in expected}
            if reduced!=expected or caps:
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
        return 'restore',dict(expected)

    def refuel_full(self, ref):
        """Transação única: combustível pago + novo alvo de todos os tanques."""
        old=self.get(ref)
        if not old or not old['capacities'] or set(old['tanks'])!=set(old['capacities']):
            raise ValueError('Tanques/capacidades ainda não sincronizados. Conecte a aeronave no solo.')
        if self.db.get_setting('fuel_control_enabled')!='1':
            raise ValueError('Ative o controle de combustível do addon para abastecer.')
        if self.db.fleet_manager().get(ref) is None:
            raise ValueError('Aeronave própria/alugada não encontrada.')
        caps=old['capacities']
        new={k:round(caps[k],4) for k in old['tanks']}
        if not valid_tanks(new,capacities=caps):
            raise ValueError('Capacidades inválidas; abastecimento recusado.')
        added=sum(new.values())-sum(old['tanks'].values())
        if added<=.03:
            raise ValueError('Tanques já estão praticamente cheios.')
        price=max(1,round(added*LITERS_PER_GALLON*FUEL_BRL_PER_LITER))
        with self.db.conn:
            self.db._money_movement('refuel:'+ref+':'+str(time_ns()),'abastecimento',-price,
                                    f'Abastecimento {added:.1f} gal — {ref}')
            self.db.conn.execute('''UPDATE fleet_fuel SET tanks_json=?,updated_utc=? WHERE aircraft_ref=?''',
                                 (json.dumps(new,sort_keys=True),self.clock(),ref))
        return {'added_gal':round(added,2),'cost_brl':price,'total_gal':round(sum(new.values()),2)}

    def set_target_liters(self, ref: str, target_liters: float) -> dict:
        """Ajusta o TOTAL em litros preservando distribuição proporcional.

        Compra e devolução são transações atômicas no DB do piloto. Reembolso
        apenas pelo combustível comprovadamente comprado neste inventário.
        Não gera saldo pela calibração inicial gratuita do MSFS.
        """
        if not isinstance(target_liters,(int,float)) or not isfinite(target_liters):
            raise ValueError('Quantidade em litros inválida.')
        old=self.get(ref)
        if not old or not old['capacities'] or set(old['tanks'])!=set(old['capacities']):
            raise ValueError('Aguardando leitura completa e válida dos tanques da aeronave no solo.')
        if self.db.get_setting('fuel_control_enabled')!='1':
            raise ValueError('Ative o controle de combustível antes de abastecer.')
        if not self.db.fleet_manager().get(ref):
            raise ValueError('Aeronave da frota não encontrada.')
        capacity=sum(old['capacities'].values())
        current=sum(old['tanks'].values())
        target=round(float(target_liters)/LITERS_PER_GALLON,5)
        if target < 0 or target > capacity+.0001:
            raise ValueError(f'Escolha de 0 até {capacity*LITERS_PER_GALLON:.1f} litros.')
        if abs(target-current)<.015:
            raise ValueError('A quantidade informada já corresponde aos tanques.')
        caps=old['capacities']
        # Distribui combustível sem transbordar nenhum tanque.
        new={k:round(target*v/capacity,5) for k,v in caps.items()}
        difference=target-sum(new.values())
        last=list(new)[-1]
        new[last]=round(new[last]+difference,5)
        if not valid_tanks(new,capacities=caps):
            raise ValueError('Ajuste resultaria em nível de tanque inválido.')
        delta_liters=(target-current)*LITERS_PER_GALLON
        with self.db.conn:
            self.db.conn.execute("""CREATE TABLE IF NOT EXISTS refundable_fuel_v077
                (aircraft_ref TEXT PRIMARY KEY, paid_liters REAL NOT NULL DEFAULT 0)""")
            record=self.db.conn.execute(
                'SELECT paid_liters FROM refundable_fuel_v077 WHERE aircraft_ref=?',(ref,)).fetchone()
            paid=max(0,float(record[0])) if record else 0.0
            added=max(0,delta_liters)
            removed=max(0,-delta_liters)
            refund_liters=min(removed,paid)
            # Não creditar devolução de combustível calibrado gratuitamente.
            cash=(-round(added*FUEL_BRL_PER_LITER) if added else
                  round(refund_liters*FUEL_BRL_PER_LITER))
            if cash:
                self.db._money_movement(
                    f'fuel-adjust:{ref}:{time_ns()}',
                    'abastecimento' if cash<0 else 'devolucao_combustivel',cash,
                    f'Combustível {delta_liters:+.2f} L ({ref}); reembolso elegível {refund_liters:.2f} L')
            self.db.conn.execute("""INSERT INTO fleet_fuel
                (aircraft_ref,model,tanks_json,caps_json,updated_utc)
                VALUES(?,?,?,?,?) ON CONFLICT(aircraft_ref)
                DO UPDATE SET tanks_json=excluded.tanks_json,
                    updated_utc=excluded.updated_utc""",
                (ref,old['model'],json.dumps(new,sort_keys=True),
                 json.dumps(caps,sort_keys=True),self.clock()))
            new_paid=max(0,paid+added-refund_liters)
            self.db.conn.execute("""INSERT INTO refundable_fuel_v077(aircraft_ref,paid_liters)
                VALUES(?,?) ON CONFLICT(aircraft_ref)
                DO UPDATE SET paid_liters=excluded.paid_liters""",(ref,new_paid))
        # Próxima amostra do worker reconcilia com inventário atualizado.
        self.restore_attempts.pop(ref,None)
        self.last_correction.pop(ref,None)
        return {'target_liters':round(target*LITERS_PER_GALLON,2),
            'capacity_liters':round(capacity*LITERS_PER_GALLON,2),
            'change_liters':round(delta_liters,2),'cost_brl':max(0,-cash),
            'refund_brl':max(0,cash),'non_refundable_liters':round(removed-refund_liters,2),
            'tanks':new}

    def refundable_liters(self,ref: str) -> float:
        try:
            row=self.db.conn.execute('SELECT paid_liters FROM refundable_fuel_v077 WHERE aircraft_ref=?',(ref,)).fetchone()
        except Exception:
            return 0.0
        return max(0,float(row[0])) if row else 0.0
