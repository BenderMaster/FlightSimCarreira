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

    def _save(self, ref, model, tanks, capacities, consumed_gal=0.0):
        with self.db.conn:
            self.db.conn.execute('''INSERT INTO fleet_fuel(aircraft_ref,model,tanks_json,caps_json,updated_utc)
                VALUES(?,?,?,?,?) ON CONFLICT(aircraft_ref) DO UPDATE SET model=excluded.model,
                tanks_json=excluded.tanks_json,caps_json=excluded.caps_json,updated_utc=excluded.updated_utc''',
                (ref,model,json.dumps(tanks,sort_keys=True),json.dumps(capacities,sort_keys=True),self.clock()))
            if consumed_gal>0:
                self.db.conn.execute('''UPDATE fleet_fuel_credit
                     SET refundable_liters=max(0,refundable_liters-?)
                     WHERE aircraft_ref=?''',(consumed_gal*LITERS_PER_GALLON,ref))

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
        # v0.7.7: o relógio de dias anteriores NÃO é tempo de consumo em voo.
        # Inventário SQLite tem precedência na primeira leitura de solo.
        first_session=ref not in self.last_seen
        elapsed=max(0,now-self.last_seen.get(ref,now))
        self.last_seen[ref]=now
        if first_session and enabled:
            if not on_ground:
                return 'airborne_resume',None
            if any(abs(observed[k]-old['tanks'][k])>.18 for k in expected):
                if not old['capacities'] or set(old['capacities'])!=set(expected):
                    return 'read_only',None
                self.last_correction[ref]=now
                self.restore_attempts[ref]=1
                return 'restore',dict(expected)
            return 'restored_from_save',None
        # No modo desligado aceitamos consumo mas não permitimos acumular
        # combustível inserido manualmente para obter combustível grátis depois.
        if not enabled:
            reduced={k:min(expected[k],float(observed[k])) for k in expected}
            if reduced!=expected or caps:
                self._save(ref,model,reduced,old['capacities'],
                           consumed_gal=max(0,sum(expected.values())-sum(reduced.values())))
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
                self._save(ref,model,reduced,old['capacities'],
                           consumed_gal=max(0,sum(expected.values())-sum(reduced.values())))
            return 'consuming',None
        if not old['capacities'] or set(old['capacities'])!=set(expected):
            return 'read_only',None
        if self.restore_attempts.get(ref,0)>=6:
            return 'write_not_confirmed',None
        if now-self.last_correction.get(ref,-1e12)<2.5:
            return 'awaiting_write',None
        self.last_correction[ref]=now
        self.restore_attempts[ref]=self.restore_attempts.get(ref,0)+1
        return 'restore',dict(expected)

    def refundable_liters(self, ref):
        row=self.db.conn.execute('SELECT refundable_liters FROM fleet_fuel_credit WHERE aircraft_ref=?',
                                 (ref,)).fetchone()
        return max(0.0,float(row[0])) if row else 0.0

    def set_target_liters(self, ref, desired_liters):
        """Compra/devolução proporcional por tanque em transação SQLite única.

        Combustível gratuito de calibração NÃO pode ser reembolsado.
        """
        if isinstance(desired_liters,bool):
            raise ValueError('Quantidade de combustível inválida')
        try:desired=float(desired_liters)
        except (TypeError,ValueError,OverflowError) as exc:
            raise ValueError('Quantidade de combustível inválida') from exc
        old=self.get(ref)
        if not old or not old['capacities'] or set(old['tanks'])!=set(old['capacities']):
            raise ValueError('Tanques não sincronizados. Conecte a aeronave em solo.')
        if self.db.get_setting('fuel_control_enabled')!='1':
            raise ValueError('Ative o controle de combustível do addon.')
        if self.db.fleet_manager().get(ref) is None:
            raise ValueError('Aeronave própria ou alugada não encontrada.')
        capacities=old['capacities']
        capacity_gal=sum(capacities.values())
        if not isfinite(desired) or desired<0 or desired>capacity_gal*LITERS_PER_GALLON+.05:
            raise ValueError('Quantidade fora da capacidade de combustível da aeronave.')
        desired=min(capacity_gal*LITERS_PER_GALLON,desired)
        old_liters=sum(old['tanks'].values())*LITERS_PER_GALLON
        delta=desired-old_liters
        if abs(delta)<.05:
            raise ValueError('Quantidade já selecionada; nada a abastecer/devolver.')
        ratio=desired/(capacity_gal*LITERS_PER_GALLON)
        new={k:round(capacities[k]*ratio,5) for k in old['tanks']}
        if not valid_tanks(new,capacities=capacities):
            raise ValueError('Falha ao balancear os tanques.')
        credit=self.refundable_liters(ref)
        if delta>0:
            money=-max(1,round(delta*FUEL_BRL_PER_LITER))
            kind='abastecimento'
            updated_credit=min(desired,credit+delta)
        else:
            refundable=min(-delta,credit)
            money=max(0,round(refundable*FUEL_BRL_PER_LITER))
            kind='devolucao_combustivel'
            updated_credit=min(desired,max(0,credit+delta))
        with self.db.conn:
            self.db._money_movement('refuel:'+ref+':'+str(time_ns()),kind,money,
                f'{"Compra" if delta>0 else "Devolução"} {abs(delta):.2f} L de combustível — {ref}')
            self.db.conn.execute('''UPDATE fleet_fuel SET tanks_json=?,caps_json=?,updated_utc=?
                                    WHERE aircraft_ref=?''',
                (json.dumps(new,sort_keys=True),json.dumps(capacities,sort_keys=True),self.clock(),ref))
            self.db.conn.execute('''INSERT INTO fleet_fuel_credit(aircraft_ref,refundable_liters)
                VALUES(?,?) ON CONFLICT(aircraft_ref) DO UPDATE SET
                refundable_liters=excluded.refundable_liters''',(ref,round(updated_credit,4)))
        self.restore_attempts.pop(ref,None)
        self.last_seen.pop(ref,None)  # leitura seguinte solicita sincronização
        return {'target_liters':round(desired,2),'target_gallons':round(desired/LITERS_PER_GALLON,2),
                'capacity_liters':round(capacity_gal*LITERS_PER_GALLON,2),
                'cost_brl':max(0,-money),'refund_brl':max(0,money),
                'refundable_liters':round(updated_credit,2),'tanks':new}

    def refuel_full(self, ref):
        old=self.get(ref)
        if not old or not old['capacities']:
            raise ValueError('Tanques ainda não sincronizados.')
        return self.set_target_liters(ref,sum(old['capacities'].values())*LITERS_PER_GALLON)
