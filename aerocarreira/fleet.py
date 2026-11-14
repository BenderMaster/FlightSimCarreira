"""Frota avançada fictícia: aviões novos, usados, aluguel e venda.

Mantém a tabela legacy owned_aircraft separada para migração aditiva. Não
modifica aeronaves do MSFS nem representa titularidade de addons comprados.
"""
from __future__ import annotations
import hashlib
import random
from dataclasses import dataclass
import re
from time import time, time_ns
from .finance import AIRCRAFT_ECONOMY


@dataclass(frozen=True)
class UsedOffer:
    offer_id: str
    code: str
    title: str
    price: int
    condition: float
    hours: float
    airport: str


def used_market(airport: str, week: int, count: int = 5) -> list[UsedOffer]:
    """Ofertas determinísticas, sem criar tabelas globais nem varrer aeroportos."""
    if len(airport) != 4 or not airport.isalnum():
        raise ValueError('ICAO de mercado inválido')
    rng = random.Random(int.from_bytes(hashlib.sha256(f'{airport}-{week}-used-v1'.encode()).digest()[:8],'big'))
    models = list(AIRCRAFT_ECONOMY.values())
    offers = []
    for i in range(min(max(0,count),10)):
        p = models[i % len(models)]
        condition=round(rng.uniform(62,94),1)
        hours=round(rng.uniform(160,3200),1)
        # Distinct market price, used units can never be resold at a profit.
        price = round(p.purchase_price * (0.47 + condition/400) / 100)*100
        offers.append(UsedOffer(f'USED-{airport}-{week}-{i}',p.code,p.title,price,condition,hours,airport))
    return offers


def rental_fee(code: str, hours: int) -> int:
    """Cotação única usada pelo Mercado e pelo caixa da carreira."""
    if code not in AIRCRAFT_ECONOMY:raise ValueError('Modelo desconhecido')
    if type(hours) is not int or not 1<=hours<=168:raise ValueError('Aluguel permitido de 1 a 168 horas')
    return max(100,round(AIRCRAFT_ECONOMY[code].purchase_price*.0018*hours/24/10)*10)


def resale_price(aircraft: dict) -> int:
    model=AIRCRAFT_ECONOMY[aircraft['code']]
    if aircraft['kind']=='starter':
        return 0
    return max(0,round(min(aircraft['price_paid']*.78,
                           model.purchase_price*.60*float(aircraft['condition'])/100)/100)*100)


def init_fleet(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS fleet_units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        aircraft_title TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('new','used')),
        price_paid INTEGER NOT NULL CHECK(price_paid >= 0),
        condition REAL NOT NULL CHECK(condition BETWEEN 0 AND 100),
        flight_hours REAL NOT NULL CHECK(flight_hours >= 0),
        airport TEXT NOT NULL,
        registration TEXT NOT NULL,
        insured INTEGER NOT NULL DEFAULT 0,
        acquired_utc REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS rented_aircraft (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL,
        aircraft_title TEXT NOT NULL, airport TEXT NOT NULL,
        expires_utc REAL NOT NULL, price_paid INTEGER NOT NULL,
        created_utc REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS fleet_market_requests (request_id TEXT PRIMARY KEY, operation TEXT NOT NULL, created_utc REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS fleet_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, aircraft_ref TEXT NOT NULL,
        kind TEXT NOT NULL, description TEXT NOT NULL, occurred_utc REAL NOT NULL);
    ''')


class FleetManager:
    def __init__(self, storage):
        self.db=storage
        self.conn=storage.conn

    def all(self, now: float | None = None):
        now=time() if now is None else now
        old=self.db.owned_fleet()
        result=[{'ref':'legacy:'+p['code'],'code':p['code'],'title':p['name'],
                 'kind':'starter' if p['code']=='c152' and self.db.get_setting('starter_claimed')=='1' else 'legacy',
                 'price_paid':0,'condition':p['condition'],'hours':p['hours'],'airport':self.db.get_setting('fleet_location:legacy:'+p['code']) or self.db.get_setting('fleet_home') or 'SBRF',
                 'insured':p['insured'],'expires':None} for p in old]
        rows=self.conn.execute('''SELECT id,code,aircraft_title,kind,price_paid,condition,
                                      flight_hours,airport,insured FROM fleet_units ORDER BY id''').fetchall()
        result.extend({'ref':f'unit:{r[0]}','code':r[1],'title':r[2], 'kind':r[3],
                       'price_paid':r[4],'condition':r[5],'hours':r[6],'airport':r[7],
                       'insured':bool(r[8]),'expires':None} for r in rows)
        rentals=self.conn.execute('SELECT id,code,aircraft_title,airport,expires_utc,price_paid FROM rented_aircraft WHERE expires_utc>? ORDER BY id',(now,)).fetchall()
        result.extend({'ref':f'rent:{r[0]}','code':r[1],'title':r[2],'kind':'rented',
                       'price_paid':r[5],'condition':100,'hours':0,'airport':r[3],
                       'insured':True,'expires':r[4]} for r in rentals)
        return result

    def get(self, ref):
        return next((x for x in self.all() if x['ref']==ref),None)

    def select(self, ref):
        item=self.get(ref)
        if not item: raise ValueError('Aeronave não existe ou aluguel expirou.')
        self.db.set_setting('active_aircraft_ref', ref)
        return item

    def selected(self):
        return self.get(self.db.get_setting('active_aircraft_ref') or '')

    def _claim_request(self, request_id, action):
        if request_id is None:return
        if (not isinstance(request_id,str) or
                re.fullmatch(r'[a-f0-9-]{36}',request_id) is None):
            raise ValueError('Identificador de transação inválido')
        if self.conn.execute('SELECT 1 FROM fleet_market_requests WHERE request_id=?',(request_id,)).fetchone():
            raise ValueError('Esta solicitação financeira já foi processada.')
        self.conn.execute('INSERT INTO fleet_market_requests(request_id,operation,created_utc) VALUES(?,?,?)',
                          (request_id,action,time()))

    def purchase(self, code, airport='SBRF', *, offer: UsedOffer | None=None, request_id=None):
        if self.db.get_pilot() is None: raise ValueError('Cadastre um piloto antes de comprar aeronaves.')
        if code not in AIRCRAFT_ECONOMY: raise ValueError('Aeronave desconhecida')
        if offer is not None and (offer.code!=code or offer.airport!=airport):
            raise ValueError('Oferta incompatível com o aeroporto ou modelo')
        plane=AIRCRAFT_ECONOMY[code]
        price=offer.price if offer else plane.purchase_price
        # IDs de oferta podem ser revendidos? Não: cada oferta pode ser aceita uma vez.
        with self.conn:
            self._claim_request(request_id,'buy_used' if offer else 'buy_new')
            if offer is not None:
                already=self.conn.execute('SELECT 1 FROM fleet_log WHERE aircraft_ref=? AND kind=?',(offer.offer_id,'used_purchase')).fetchone()
                if already: raise ValueError('Esta aeronave usada já foi vendida.')
            self.db._money_movement(f'fleet-buy:{time_ns()}', 'compra_aviao', -price,
                                    f'Compra de {plane.title} ({"usado" if offer else "novo"})')
            cursor=self.conn.execute('''INSERT INTO fleet_units(code,aircraft_title,kind,price_paid,
                condition,flight_hours,airport,registration,acquired_utc)
                VALUES(?,?,?,?,?,?,?,?,?)''',(code,plane.title,'used' if offer else 'new',price,
                offer.condition if offer else 100,offer.hours if offer else 0,airport,
                f'FSCR{time_ns()%10000000:07}',time()))
            unit_ref=f'unit:{cursor.lastrowid}'
            self.conn.execute('INSERT INTO fleet_log(aircraft_ref,kind,description,occurred_utc) VALUES(?,?,?,?)',
                              (offer.offer_id if offer else unit_ref,
                               'used_purchase' if offer else 'new_purchase',unit_ref,time()))
            self.conn.execute("INSERT INTO settings(key,value) VALUES('active_aircraft_ref',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(unit_ref,))
        return self.get(unit_ref)

    def rent(self, code, airport='SBRF', hours=24, *, request_id=None):
        if self.db.get_pilot() is None: raise ValueError('Cadastre um piloto.')
        fee=rental_fee(code,hours)
        plane=AIRCRAFT_ECONOMY[code]
        now=time()
        with self.conn:
            self._claim_request(request_id,'rent')
            self.db._money_movement(f'rent:{time_ns()}','aluguel',-fee,f'Aluguel {plane.title} por {hours}h')
            cursor=self.conn.execute('INSERT INTO rented_aircraft(code,aircraft_title,airport,expires_utc,price_paid,created_utc) VALUES(?,?,?,?,?,?)',
                  (code,plane.title,airport,now+hours*3600,fee,now))
            ref=f'rent:{cursor.lastrowid}'
            self.conn.execute("INSERT INTO settings(key,value) VALUES('active_aircraft_ref',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(ref,))
        return self.get(ref)

    def sell(self, ref, *, request_id=None):
        plane=self.get(ref)
        if not plane or not ref.startswith('unit:'):
            raise ValueError('Somente aeronaves novas/usadas próprias podem ser vendidas; inicial e aluguel são excluídos.')
        price=resale_price(plane)
        with self.conn:
            self._claim_request(request_id,'sell')
            r=self.conn.execute('DELETE FROM fleet_units WHERE id=?',(int(ref.split(':')[1]),))
            if r.rowcount!=1: raise ValueError('Aeronave indisponível')
            # O exemplar deixa de pertencer à carreira; a foto não pode
            # ficar órfã nem ser herdada por outra aeronave do mesmo modelo.
            self.conn.execute('DELETE FROM fleet_photos WHERE aircraft_ref=?',(ref,))
            self.db._money_movement(f'fleet-sell:{ref}:{time_ns()}','venda_aviao',price,f'Venda de {plane["title"]}')
            if self.db.get_setting('active_aircraft_ref')==ref:
                self.conn.execute("DELETE FROM settings WHERE key='active_aircraft_ref'")
        return price

    def set_insurance(self, ref, enabled, *, request_id=None):
        """Update a unit's insurance through the same transactional fleet ledger.

        Legacy aircraft retain the established Storage.set_insurance semantics.
        Rentals do not support policy changes; original rules remain authoritative.
        """
        plane=self.get(ref)
        if plane is None or plane['kind']=='rented':
            raise ValueError('Seguro permitido somente para aeronaves próprias.')
        enabled=bool(enabled)
        if bool(plane['insured'])==enabled:
            raise ValueError('A apólice já está neste estado.')
        if ref.startswith('legacy:'):
            return self.db.set_insurance(plane['code'],enabled)
        if not ref.startswith('unit:'):
            raise ValueError('Aeronave não encontrada na frota.')
        model=AIRCRAFT_ECONOMY.get(plane['code'])
        if model is None:raise ValueError('Modelo desconhecido para seguro.')
        with self.conn:
            self._claim_request(request_id,'insurance')
            if enabled:
                self.db._money_movement('fleet-insurance:'+ref+':'+(request_id or str(time_ns())),
                    'seguro',-model.insurance_price,'Apólice virtual para '+plane['title'])
            self.conn.execute('UPDATE fleet_units SET insured=? WHERE id=?',
                (int(enabled),int(ref.split(':',1)[1])))
        return int(self.db.get_setting('balance') or 0)

    def service(self, ref):
        plane=self.get(ref)
        if not plane or not ref.startswith('unit:'):
            raise ValueError('Revisão de aeronave legada permanece no menu Finanças/Hangar.')
        if plane['condition']>=99.9: raise ValueError('Aeronave já revisada.')
        price=AIRCRAFT_ECONOMY[plane['code']].service_cost+round((100-plane['condition'])*60)
        with self.conn:
            self.db._money_movement(f'fleet-service:{time_ns()}','manutencao',-price,'Revisão de '+plane['title'])
            self.conn.execute('UPDATE fleet_units SET condition=100 WHERE id=?',(int(ref[5:]),))
        return price

    def ensure_location(self, ref: str, airport: str):
        """Registra pouso para exemplar próprio, starter legado ou aluguel ativo."""
        if not airport or len(airport)!=4 or not airport.isalnum():
            return False
        if not self.get(ref):
            return False
        with self.conn:
            if ref.startswith('unit:'):
                return bool(self.conn.execute('UPDATE fleet_units SET airport=? WHERE id=?',
                    (airport,int(ref[5:]))).rowcount)
            if ref.startswith('rent:'):
                return bool(self.conn.execute('UPDATE rented_aircraft SET airport=? WHERE id=?',
                    (airport,int(ref[5:]))).rowcount)
            if ref.startswith('legacy:'):
                self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                  ('fleet_location:'+ref,airport))
                return True
        return False
