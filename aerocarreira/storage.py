"""Base própria SQLite: nunca lê/escreve NeoFly."""
import json
import sqlite3
from time import time, time_ns
from .pilot import validate_pilot, qualification_eligibility, QUAL_BY_CODE, flight_xp
from .contracts import aircraft_family, aircraft_model, pilot_level, next_level_xp
from .domain import Mission
from .finance import AIRCRAFT_ECONOMY, brl, flight_operating_cost
from .fleet import init_fleet, FleetManager
from .employment import (Vacancy, EMPLOYER_BY_CODE, vacancies, weekly_period,
    employment_eligibility, selection_result, OWN_MIN_LEVEL, OWN_MIN_HOURS,
    OWN_INVESTMENT, valid_company_name)
from pathlib import Path
from dataclasses import asdict
from typing import Optional


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.path.is_file() and self.path.stat().st_size > 0
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        # Backup transacional antes da migração: snapshot SQLite inclui o WAL.
        # Nunca substituir backup anterior ao abrir o aplicativo novamente.
        if existing:
            backup_path = self.path.with_name(self.path.stem + '.pre_v040.backup.db')
            if not backup_path.exists():
                backup_conn = sqlite3.connect(backup_path)
                try:
                    self.conn.backup(backup_conn)
                finally:
                    # Context manager de sqlite3 NÃO fecha handle no Windows.
                    # Fechar explicitamente evita WinError 32 em pasta temporária.
                    backup_conn.close()
        # Segunda migração, backup separado; sem tocar no NeoFly.
        if existing:
            safety = self.path.with_name(self.path.stem + '.pre_v050.backup.db')
            if not safety.exists():
                backup = sqlite3.connect(safety)
                try:
                    self.conn.backup(backup)
                finally:
                    backup.close()
        self.conn.execute("PRAGMA busy_timeout=3000")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_utc REAL NOT NULL,
                ended_utc REAL NOT NULL,
                from_lat REAL, from_lon REAL, to_lat REAL, to_lon REAL,
                touchdown_fpm_est REAL, stall_warnings INTEGER NOT NULL,
                mission_id TEXT, reward INTEGER NOT NULL DEFAULT 0);
        """)
        # Migração aditiva: preserva DB criado nas versões 0.1 e 0.1.1.
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(flights)")}
        if "flight_key" not in columns:
            self.conn.execute("ALTER TABLE flights ADD COLUMN flight_key TEXT")
        self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_flights_unique_key ON flights(flight_key)")
        if "aircraft_title" not in columns:
            self.conn.execute("ALTER TABLE flights ADD COLUMN aircraft_title TEXT")
        # Bloco 1: tabelas aditivas; nenhuma tabela antiga é alterada ou apagada.
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS pilot_profile (
                id INTEGER PRIMARY KEY CHECK(id=1),
                name TEXT NOT NULL, callsign TEXT NOT NULL,
                home_icao TEXT NOT NULL, created_utc REAL NOT NULL,
                updated_utc REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS pilot_qualifications (
                code TEXT PRIMARY KEY, awarded_utc REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS pilot_xp_ledger (
                flight_key TEXT PRIMARY KEY, xp INTEGER NOT NULL,
                awarded_utc REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS contract_offers (
                id TEXT PRIMARY KEY, origin TEXT NOT NULL,
                data_json TEXT NOT NULL, created_utc REAL NOT NULL, expires_utc REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_contract_origin ON contract_offers(origin,expires_utc);
            CREATE TABLE IF NOT EXISTS completed_contracts (
                contract_id TEXT PRIMARY KEY, flight_key TEXT NOT NULL, completed_utc REAL NOT NULL);
        """)
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS career_status (
                id INTEGER PRIMARY KEY CHECK(id=1),
                mode TEXT NOT NULL DEFAULT 'autonomo',
                employer_code TEXT, owner_company TEXT,
                updated_utc REAL NOT NULL);
            INSERT OR IGNORE INTO career_status(id,mode,updated_utc) VALUES(1,'autonomo',0);
            CREATE TABLE IF NOT EXISTS job_applications (
                vacancy_id TEXT PRIMARY KEY, company_code TEXT NOT NULL,
                data_json TEXT NOT NULL, applied_utc REAL NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','hired','rejected')),
                decided_utc REAL);
            CREATE INDEX IF NOT EXISTS idx_job_status ON job_applications(status);
        """)
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS finance_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
                amount INTEGER NOT NULL, balance_after INTEGER NOT NULL,
                description TEXT NOT NULL, occurred_utc REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS owned_aircraft (
                code TEXT PRIMARY KEY, condition REAL NOT NULL DEFAULT 100,
                hours REAL NOT NULL DEFAULT 0,
                insured INTEGER NOT NULL DEFAULT 0,
                purchased_utc REAL NOT NULL,
                CHECK(condition BETWEEN 0 AND 100), CHECK(hours >= 0));
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                principal INTEGER NOT NULL, debt INTEGER NOT NULL,
                created_utc REAL NOT NULL, CHECK(debt >= 0));
        """)
        # Bloco 5: frota individual sem substituir a tabela de aeronaves antigas.
        if existing:
            safety = self.path.with_name(self.path.stem + '.pre_v060.backup.db')
            if not safety.exists():
                target = sqlite3.connect(safety)
                try:
                    self.conn.backup(target)
                finally:
                    target.close()
        if existing:
            safety = self.path.with_name(self.path.stem + '.pre_v061.backup.db')
            if not safety.exists():
                target=sqlite3.connect(safety)
                try:
                    self.conn.backup(target)
                finally:
                    target.close()
        init_fleet(self.conn)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS fleet_fuel (
            aircraft_ref TEXT PRIMARY KEY, model TEXT NOT NULL,
            tanks_json TEXT NOT NULL, caps_json TEXT NOT NULL,
            updated_utc REAL NOT NULL)""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS refundable_fuel_v077
            (aircraft_ref TEXT PRIMARY KEY, paid_liters REAL NOT NULL DEFAULT 0)""")
        self.conn.commit()
        if self.get_setting("balance") is None:
            self.set_setting("balance", "5000")
        # Novo balanceamento: invalida só o CACHE de ofertas. Contrato aceito
        # sobrevive no checkpoint e preserva a recompensa contratada.
        if self.get_setting('market_pricing_v05') != '1':
            with self.conn:
                self.conn.execute('DELETE FROM contract_offers')
                self.conn.execute("INSERT INTO settings(key,value) VALUES('market_pricing_v05','1') "
                                  "ON CONFLICT(key) DO UPDATE SET value='1'")
        if self.get_setting('income_tax_enabled') is None:
            self.set_setting('income_tax_enabled','0')
        if self.get_setting('simulated_failures_enabled') is None:
            self.set_setting('simulated_failures_enabled','0')
        if self.get_setting('fuel_control_enabled') is None:
            self.set_setting('fuel_control_enabled','1')

    def recover_legacy_location(self, catalog=None) -> str | None:
        """Recupera último pouso do starter legado sem alterar voos/finanças."""
        if self.get_setting('legacy_location_recovered_v061') == '1':
            return None
        from .contracts import aircraft_model, AirportCatalog
        fleet = FleetManager(self)
        current = self.get_setting('active_aircraft_ref')
        rows = self.conn.execute("""SELECT aircraft_title, to_lat, to_lon, mission_id
                FROM flights WHERE aircraft_title IS NOT NULL
                ORDER BY ended_utc DESC LIMIT 100""").fetchall()
        found = None
        for title, lat, lon, mission in rows:
            model = aircraft_model(title)
            if model is None:
                continue
            if not self.conn.execute('SELECT 1 FROM owned_aircraft WHERE code=?',(model,)).fetchone():
                continue
            if current and current != 'legacy:'+model:
                continue  # pode ter voado em outro exemplar selecionado
            if mission and mission.startswith(('FREE-','EMP-')):
                continue  # aeronave do contratante
            if lat is None or lon is None:
                continue
            airport = (catalog or AirportCatalog()).nearest(float(lat),float(lon),3)
            if airport:
                found = ('legacy:'+model,airport.icao)
            break  # último voo relevante decide: não recorrer a um voo antigo
        with self.conn:
            if found:
                self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    ('fleet_location:'+found[0],found[1]))
            self.conn.execute("INSERT INTO settings(key,value) VALUES('legacy_location_recovered_v061','1') "
                              "ON CONFLICT(key) DO UPDATE SET value='1'")
        return found[1] if found else None

    def fleet_manager(self):
        return FleetManager(self)

    def get_setting(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str):
        with self.conn:
            self.conn.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def save_flight(self, start: dict, end: dict, touchdown_fpm_est, stall_warnings: int, mission_id=None, reward=0):
        with self.conn:
            self.conn.execute("""INSERT INTO flights(started_utc,ended_utc,from_lat,from_lon,to_lat,to_lon,touchdown_fpm_est,stall_warnings,mission_id,reward)
                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (start['timestamp'], end['timestamp'], start['lat'], start['lon'], end['lat'], end['lon'], touchdown_fpm_est, stall_warnings, mission_id, reward))

    def get_checkpoint(self) -> dict | None:
        raw = self.get_setting("flight_checkpoint_v1")
        return json.loads(raw) if raw else None

    def set_checkpoint(self, checkpoint: dict):
        self.set_setting("flight_checkpoint_v1", json.dumps(checkpoint, ensure_ascii=False))

    def finalize_flight(self, start: dict, end: dict, touchdown_fpm_est, stalls: int,
                        mission_id: str | None, reward: int, checkpoint: dict,
                        aircraft_title: str | None = None,
                        fuel_start: float | None = None, fuel_end: float | None = None,
                        realism_fraction: float = 0.0, destination: str | None = None,
                        fuel_penalty_fraction: float = 0.0, fuel_prepaid: bool = False,
                        flight_xp_extra: int = 0) -> bool:
        """Pouso+crédito+estado em UMA transação; repetição não duplica dinheiro.

        A identidade é determinada pela decolagem original e sobrevive a reinícios.
        """
        if not isinstance(realism_fraction,(float,int)) or not 0 <= realism_fraction <= .18:
            raise ValueError('Bônus de realismo inválido')
        if isinstance(flight_xp_extra,bool) or not isinstance(flight_xp_extra,int) or not -15<=flight_xp_extra<=7:
            raise ValueError('XP de segurança fora dos limites')
        if not isinstance(fuel_penalty_fraction,(float,int)) or fuel_penalty_fraction not in (0,.3):
            raise ValueError('Penalidade de combustível inválida')
        flight_key = f"takeoff:{float(start['timestamp']):.6f}:{float(start['lat']):.7f}:{float(start['lon']):.7f}"
        with self.conn:
            # Se o pouso já foi processado, não reivindicar outro contrato.
            if self.conn.execute("SELECT 1 FROM flights WHERE flight_key=?", (flight_key,)).fetchone():
                return False
            # Um contrato gerado pode ser pago apenas UMA vez por ID; isso
            # bloqueia exploração do mercado após reiniciar o aplicativo.
            actual_reward = reward
            if mission_id and (mission_id.startswith("REG-") or mission_id.startswith("FREE-") or mission_id.startswith("EMP-")):
                claim = self.conn.execute(
                    "INSERT OR IGNORE INTO completed_contracts(contract_id,flight_key,completed_utc) VALUES(?,?,?)",
                    (mission_id, flight_key, time()))
                if claim.rowcount == 0:
                    actual_reward = 0
            realism_amount = round(actual_reward * float(realism_fraction)) if actual_reward > 0 else 0
            pre_penalty_reward = actual_reward + realism_amount
            fuel_penalty = round(pre_penalty_reward * fuel_penalty_fraction)
            gross_reward = pre_penalty_reward - fuel_penalty
            cursor = self.conn.execute('''INSERT OR IGNORE INTO flights
                (started_utc,ended_utc,from_lat,from_lon,to_lat,to_lon,
                touchdown_fpm_est,stall_warnings,mission_id,reward,flight_key,aircraft_title)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (start["timestamp"], end["timestamp"], start["lat"], start["lon"],
                 end["lat"], end["lon"], touchdown_fpm_est, stalls,
                 mission_id, gross_reward, flight_key, aircraft_title))
            inserted = cursor.rowcount == 1
            if inserted:
                old_balance = int(self.get_setting("balance") or 0)
                # Uma aeronave própria selecionada é individualizada; fallback legado
                # mantém os voos antigos sem migrar/duplicar inventário.
                model = aircraft_model(aircraft_title)
                fleet = FleetManager(self)
                selected = fleet.selected()
                legacy = self.conn.execute('SELECT condition,hours,insured FROM owned_aircraft WHERE code=?',(model,)).fetchone() if model else None
                company_plane = bool(mission_id and mission_id.startswith(('FREE-', 'EMP-')))
                selected_matches = bool(selected and selected['code']==model)
                flight_asset = selected if selected_matches else (None if selected else (
                    {'ref':'legacy:'+model,'code':model,'insured':bool(legacy[2]),'kind':'legacy'} if legacy else None))
                charged = bool(flight_asset and mission_id and not company_plane)
                costs = flight_operating_cost(model, end['timestamp'] - start['timestamp'],
                    fuel_start, fuel_end, bool(flight_asset and flight_asset['insured'])) if charged else {}
                if charged and fuel_prepaid:
                    # O combustível já foi comprado no hangar; evitar dupla cobrança.
                    costs['fuel_brl'] = 0
                tax = round(gross_reward * .04) if (gross_reward > 0 and
                    self.get_setting('income_tax_enabled') == '1') else 0
                total_expenses = tax + sum(costs.get(k, 0) for k in ('fuel_brl','airport_brl','insurance_brl'))
                new_balance = old_balance + gross_reward - total_expenses
                if actual_reward:
                    self._ledger_in_transaction(f'{flight_key}:income', 'contrato', actual_reward,
                        old_balance + actual_reward, f'Contrato {mission_id}')
                if realism_amount:
                    self._ledger_in_transaction(f'{flight_key}:realism', 'bonus_realismo', realism_amount,
                        old_balance + gross_reward, f'Bônus realismo +{realism_fraction:.0%}: {mission_id}')
                if fuel_penalty:
                    self._ledger_in_transaction(f'{flight_key}:fuel_optout', 'penalidade_combustivel',
                        -fuel_penalty, old_balance + gross_reward,
                        'Controle de combustível desligado: -30% da receita')
                if tax:
                    self._ledger_in_transaction(f'{flight_key}:tax', 'taxa_simulada', -tax,
                                                old_balance+gross_reward-tax,
                                                'Tributação opcional de carreira (fictícia)')
                if charged:
                    if flight_asset['ref'].startswith('legacy:'):
                        self.conn.execute('UPDATE owned_aircraft SET condition=max(0,condition-?), hours=hours+? WHERE code=?',
                            (costs['wear'], max(0,(end['timestamp']-start['timestamp'])/3600), model))
                    elif flight_asset['ref'].startswith('unit:'):
                        self.conn.execute('UPDATE fleet_units SET condition=max(0,condition-?), flight_hours=flight_hours+? WHERE id=?',
                            (costs['wear'], max(0,(end['timestamp']-start['timestamp'])/3600), int(flight_asset['ref'][5:])))
                    running = old_balance + gross_reward - tax
                    for key, kind, desc in (
                        ('fuel_brl','combustivel','Combustível utilizado em voo'),
                        ('airport_brl','taxa_aeroporto','Taxa de operação no destino')):
                        amount = int(costs.get(key,0))
                        if amount:
                            running -= amount
                            self._ledger_in_transaction(f'{flight_key}:{kind}',kind,-amount,running,desc)
                # Posicionamento da aeronave é independente do contrato ter sido pago:
                # inclui starter, exemplares novos/usados, aluguel e voos livres.
                # Freelancer/emprego não movimenta aeronave pessoal.
                if destination and flight_asset and not company_plane:
                    ref = flight_asset['ref']
                    if ref.startswith('legacy:'):
                        self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                                          "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                          ('fleet_location:'+ref,destination))
                    elif ref.startswith('unit:'):
                        self.conn.execute('UPDATE fleet_units SET airport=? WHERE id=?',
                                          (destination,int(ref[5:])))
                    elif ref.startswith('rent:'):
                        self.conn.execute('UPDATE rented_aircraft SET airport=? WHERE id=?',
                                          (destination,int(ref[5:])))
                if self.get_pilot() is not None:
                    xp_gross = flight_xp(actual_reward) + (round(flight_xp(actual_reward)*realism_fraction)
                                                           if actual_reward > 0 else 0)
                    # Só altera XP do voo atual; arremetida nunca retira XP
                    # previamente creditado. Ledger é idempotente por flight_key.
                    xp_gross=max(0,xp_gross+flight_xp_extra)
                    xp_net = max(0,xp_gross - round(xp_gross*fuel_penalty_fraction))
                    self.conn.execute("INSERT OR IGNORE INTO pilot_xp_ledger(flight_key,xp,awarded_utc) VALUES(?,?,?)",
                                      (flight_key, xp_net, time()))
                self.conn.execute("INSERT INTO settings(key,value) VALUES('balance',?) "
                                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(new_balance),))
                self.conn.execute("INSERT INTO settings(key,value) VALUES('flight_checkpoint_v1',?) "
                                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                  (json.dumps(checkpoint, ensure_ascii=False),))
        return inserted

    def apply_postflight_taxi_penalty(self, flight_key: str) -> int:
        """Desconta XP de táxi da mesma decolagem, no máximo uma vez.

        Fica num registro individual, atômico e idempotente. Não muda R$,
        registro de voos, nem XP de qualquer outra decolagem.
        """
        if not isinstance(flight_key,str) or not flight_key.startswith('takeoff:') or len(flight_key)>100:
            raise ValueError('Identificador de voo inválido')
        marker='postflight_taxi_v2:'+flight_key
        with self.conn:
            if self.conn.execute('SELECT 1 FROM settings WHERE key=?',(marker,)).fetchone():
                return 0
            if not self.conn.execute('SELECT 1 FROM flights WHERE flight_key=?',(flight_key,)).fetchone():
                return 0
            row=self.conn.execute('SELECT xp FROM pilot_xp_ledger WHERE flight_key=?',(flight_key,)).fetchone()
            if row is None:return 0
            deduction=min(2,max(0,int(row[0])))
            if deduction:
                self.conn.execute('UPDATE pilot_xp_ledger SET xp=xp-? WHERE flight_key=?',
                                  (deduction,flight_key))
            self.conn.execute('INSERT INTO settings(key,value) VALUES(?,?)',(marker,str(deduction)))
            return deduction

    def _ledger_in_transaction(self, key: str, kind: str, amount: int,
                               balance_after: int, description: str) -> None:
        self.conn.execute("""INSERT OR IGNORE INTO finance_ledger
            (event_key,kind,amount,balance_after,description,occurred_utc)
            VALUES(?,?,?,?,?,?)""",(key,kind,int(amount),int(balance_after),description,time()))

    def _money_movement(self, key: str, kind: str, amount: int, description: str) -> int:
        # Chamadores usam `with self.conn:` para preservar atomicidade de
        # movimento + mutação do bem, inclusive em caso de falha posterior.
        if self.conn.execute('SELECT 1 FROM finance_ledger WHERE event_key=?',(key,)).fetchone():
            raise ValueError('Movimento já registrado.')
        old = int(self.get_setting('balance') or 0)
        if amount < 0 and old < -amount:
            raise ValueError(f'Saldo insuficiente: {brl(old)}. Use financiamento ou ganhe contratos.')
        new = old + amount
        self._ledger_in_transaction(key,kind,amount,new,description)
        self.conn.execute("INSERT INTO settings(key,value) VALUES('balance',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(new),))
        return new

    def finance_history(self, limit: int = 30) -> list[dict]:
        rows=self.conn.execute('SELECT kind,amount,balance_after,description,occurred_utc FROM finance_ledger ORDER BY id DESC LIMIT ?', (max(1,min(300,limit)),)).fetchall()
        return [dict(zip(('kind','amount','balance_after','description','occurred_utc'),r)) for r in rows]

    def flight_finance(self, start: dict) -> dict:
        flight_key = f"takeoff:{float(start['timestamp']):.6f}:{float(start['lat']):.7f}:{float(start['lon']):.7f}"
        rows=self.conn.execute('SELECT kind,amount FROM finance_ledger WHERE event_key LIKE ?', (flight_key+':%',)).fetchall()
        gross=sum(amount for kind,amount in rows if kind in ('contrato','bonus_realismo','penalidade_combustivel'))
        costs=-sum(amount for kind,amount in rows if kind in ('combustivel','taxa_aeroporto','taxa_simulada'))
        bonus=sum(amount for kind,amount in rows if kind=='bonus_realismo')
        return {'gross':gross,'expenses':costs,'net':gross-costs,'realism_bonus':bonus}

    def claim_starter(self) -> bool:
        """Uma aeronave inicial, concedida apenas uma vez à carreira por opção explícita."""
        if self.get_pilot() is None:
            raise ValueError('Cadastre o piloto primeiro.')
        with self.conn:
            if self.get_setting('starter_claimed') == '1':
                return False
            self.conn.execute("INSERT OR IGNORE INTO owned_aircraft(code,purchased_utc) VALUES('c152',?)",(time(),))
            self.conn.execute("INSERT INTO settings(key,value) VALUES('starter_claimed','1') ON CONFLICT(key) DO UPDATE SET value='1'")
            return True

    def owned_fleet(self) -> list[dict]:
        rows=self.conn.execute('SELECT code,condition,hours,insured FROM owned_aircraft ORDER BY code').fetchall()
        return [{'code':r[0], 'name':AIRCRAFT_ECONOMY[r[0]].title if r[0] in AIRCRAFT_ECONOMY else r[0],
                 'condition':r[1], 'hours':r[2], 'insured':bool(r[3])} for r in rows]

    def buy_aircraft(self, code: str) -> int:
        plane=AIRCRAFT_ECONOMY.get(code)
        if plane is None: raise ValueError('Modelo desconhecido.')
        if self.get_pilot() is None: raise ValueError('Cadastre o piloto primeiro.')
        if self.conn.execute('SELECT 1 FROM owned_aircraft WHERE code=?',(code,)).fetchone():
            raise ValueError('Modelo já está na sua frota.')
        with self.conn:
            balance=self._money_movement(f'purchase:{code}', 'compra_aviao', -plane.purchase_price,
                                         'Compra de '+plane.title)
            self.conn.execute('INSERT INTO owned_aircraft(code,purchased_utc) VALUES(?,?)',(code,time()))
            return balance

    def service_aircraft(self, code: str) -> int:
        plane=AIRCRAFT_ECONOMY.get(code)
        row=self.conn.execute('SELECT condition FROM owned_aircraft WHERE code=?',(code,)).fetchone()
        if plane is None or row is None: raise ValueError('Aeronave não pertence à frota.')
        if row[0] >= 99.9: raise ValueError('Aeronave já está revisada.')
        price=plane.service_cost + round((100-row[0])*60)
        with self.conn:
            balance=self._money_movement(f'service:{code}:{time_ns()}', 'manutencao', -price,
                                         'Revisão de '+plane.title)
            self.conn.execute('UPDATE owned_aircraft SET condition=100 WHERE code=?',(code,))
            return balance

    def set_insurance(self, code: str, enabled: bool) -> int:
        plane=AIRCRAFT_ECONOMY.get(code)
        row=self.conn.execute('SELECT insured FROM owned_aircraft WHERE code=?',(code,)).fetchone()
        if plane is None or row is None: raise ValueError('Aeronave não pertence à frota.')
        if bool(row[0]) == bool(enabled): raise ValueError('Seguro já está neste estado.')
        with self.conn:
            if enabled:
                balance=self._money_movement(f'insurance:{code}:{time_ns()}', 'seguro', -plane.insurance_price,
                                             'Apólice virtual para '+plane.title)
            else:
                balance=int(self.get_setting('balance') or 0)
            self.conn.execute('UPDATE owned_aircraft SET insured=? WHERE code=?',(1 if enabled else 0,code))
            return balance

    def take_loan(self, principal: int) -> int:
        if not isinstance(principal,int) or principal < 1000 or principal > 30000:
            raise ValueError('Financiamento permitido: R$ 1.000 a R$ 30.000.')
        if self.conn.execute('SELECT 1 FROM loans WHERE debt>0').fetchone():
            raise ValueError('Quite o financiamento anterior primeiro.')
        with self.conn:
            cursor=self.conn.execute('INSERT INTO loans(principal,debt,created_utc) VALUES(?,?,?)',
                                      (principal,round(principal*1.08),time()))
            return self._money_movement(f'loan:{cursor.lastrowid}','financiamento',principal,'Crédito de financiamento virtual')

    def outstanding_loan(self) -> int:
        return int(self.conn.execute('SELECT COALESCE(SUM(debt),0) FROM loans').fetchone()[0])

    def repay_loan(self, amount: int) -> int:
        row=self.conn.execute('SELECT id,debt FROM loans WHERE debt>0 ORDER BY id LIMIT 1').fetchone()
        if row is None: raise ValueError('Sem empréstimo em aberto.')
        if not isinstance(amount,int) or amount<=0 or amount>row[1]:
            raise ValueError(f'Parcela deve ser de R$ 1 até {brl(row[1])}.')
        with self.conn:
            balance=self._money_movement(f'loan-repay:{row[0]}:{time_ns()}', 'parcela',-amount,'Pagamento financiamento')
            self.conn.execute('UPDATE loans SET debt=debt-? WHERE id=?',(amount,row[0]))
            return balance

    def list_flights(self):
        return self.conn.execute("SELECT id, started_utc, ended_utc, touchdown_fpm_est, stall_warnings, mission_id, reward FROM flights ORDER BY id DESC LIMIT 100").fetchall()

    def get_pilot(self) -> dict | None:
        row = self.conn.execute("SELECT name,callsign,home_icao,created_utc,updated_utc "
                                "FROM pilot_profile WHERE id=1").fetchone()
        return dict(zip(("name", "callsign", "home_icao", "created_utc", "updated_utc"), row)) if row else None

    def create_pilot(self, name: str, callsign: str, home_icao: str) -> dict:
        name, callsign, home_icao = validate_pilot(name, callsign, home_icao)
        if self.get_pilot() is not None:
            raise ValueError("Já existe um piloto. Edite o cadastro existente.")
        with self.conn:
            now = time()
            self.conn.execute("INSERT INTO pilot_profile VALUES(1,?,?,?,?,?)",
                              (name, callsign, home_icao, now, now))
            # Apenas habilitação de entrada, virtual. Outras são conquistadas.
            self.conn.execute("INSERT OR IGNORE INTO pilot_qualifications VALUES('PPA',?)", (now,))
        return self.get_pilot()

    def update_pilot(self, name: str, callsign: str, home_icao: str) -> dict:
        name, callsign, home_icao = validate_pilot(name, callsign, home_icao)
        if self.get_pilot() is None:
            raise ValueError("Crie o piloto antes de editar.")
        with self.conn:
            self.conn.execute("UPDATE pilot_profile SET name=?,callsign=?,home_icao=?,updated_utc=? WHERE id=1",
                              (name, callsign, home_icao, time()))
        return self.get_pilot()

    def pilot_stats(self) -> dict:
        flights, duration = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(MAX(0,ended_utc-started_utc)),0) FROM flights").fetchone()
        xp = self.conn.execute("SELECT COALESCE(SUM(xp),0) FROM pilot_xp_ledger").fetchone()[0]
        level = pilot_level(int(xp))
        return {"flights": int(flights), "hours": float(duration) / 3600,
                "xp": int(xp), "level": level, "next_level_xp": next_level_xp(level),
                "qualifications": self.owned_qualifications()}

    def family_experience(self) -> dict[str, int]:
        """Histórico por família de aeronave. Voos antigos continuam no diário."""
        counts: dict[str, int] = {}
        for (title,) in self.conn.execute("SELECT aircraft_title FROM flights WHERE aircraft_title IS NOT NULL"):
            family = aircraft_family(title)
            if family:
                counts[family] = counts.get(family, 0) + 1
            model = aircraft_model(title)
            if model:
                counts[model] = counts.get(model, 0) + 1
        return counts

    def invalidate_market(self):
        """Após contratar/demitir, atualizar somente o cache de ofertas local."""
        with self.conn:
            self.conn.execute('DELETE FROM contract_offers')

    def contract_completed(self, contract_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM completed_contracts WHERE contract_id=?", (contract_id,)).fetchone() is not None

    def active_offers(self, origin: str, now: float | None = None) -> list[Mission]:
        now = time() if now is None else now
        rows = self.conn.execute("SELECT data_json FROM contract_offers WHERE origin=? AND expires_utc>? ORDER BY id", (origin, now)).fetchall()
        missions = [Mission(**json.loads(r[0])) for r in rows]
        return [m for m in missions if not self.contract_completed(m.id)]

    def save_offers(self, origin: str, offers: list[Mission], now: float | None = None, valid_s: float = 86400):
        """Mantém no máximo 20 ofertas, somente no aeroporto da região atual."""
        from dataclasses import asdict
        now = time() if now is None else now
        if len(offers) > 20:
            raise ValueError("Limite regional excedido: máximo 20 propostas")
        if any(m.origin != origin or len(m.id) > 120 for m in offers):
            raise ValueError("Propostas devem corresponder à região atual")
        with self.conn:
            self.conn.execute("DELETE FROM contract_offers")
            self.conn.executemany("INSERT INTO contract_offers VALUES(?,?,?,?,?)", [
                (m.id, m.origin, json.dumps(asdict(m), ensure_ascii=False), now, now + valid_s)
                for m in offers if not self.contract_completed(m.id)])

    def offer_cache_valid(self, origin: str, now: float | None = None) -> bool:
        now = time() if now is None else now
        row = self.conn.execute("SELECT COUNT(*), MIN(expires_utc) FROM contract_offers").fetchone()
        count_origin = self.conn.execute("SELECT COUNT(*) FROM contract_offers WHERE origin=?", (origin,)).fetchone()[0]
        return bool(row[0] and count_origin == row[0] and row[1] > now)

    def owned_qualifications(self) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT code FROM pilot_qualifications").fetchall()}

    def earn_qualification(self, code: str) -> bool:
        if self.get_pilot() is None:
            raise ValueError("Crie um piloto antes das habilitações.")
        if code not in QUAL_BY_CODE:
            raise ValueError("Habilitação desconhecida.")
        with self.conn:
            progress = self.pilot_stats()
            eligible, reason = qualification_eligibility(
                code, progress["qualifications"], progress["flights"], progress["xp"], progress["hours"])
            if not eligible:
                raise ValueError(reason)
            result = self.conn.execute(
                "INSERT OR IGNORE INTO pilot_qualifications(code,awarded_utc) VALUES(?,?)", (code, time()))
            return result.rowcount == 1


    # Bloco 3 — modalidades de carreira (dados simulados, independentes do NeoFly).
    def employment_state(self) -> dict:
        row=self.conn.execute('SELECT mode, employer_code, owner_company FROM career_status WHERE id=1').fetchone()
        return dict(zip(('mode','employer_code','owner_company'),row))

    def list_applications(self) -> list[dict]:
        rows=self.conn.execute('SELECT vacancy_id,company_code,status,applied_utc,decided_utc FROM job_applications ORDER BY applied_utc DESC LIMIT 30').fetchall()
        return [dict(zip(('vacancy_id','company_code','status','applied_utc','decided_utc'),r)) for r in rows]

    def apply_vacancy(self, vacancy: Vacancy, now: float) -> None:
        if self.get_pilot() is None:
            raise ValueError('Cadastre seu piloto primeiro.')
        if self.employment_state()['mode'] != 'autonomo':
            raise ValueError('Para se candidatar, retorne primeiro à carreira autônoma.')
        period=weekly_period(now)
        if vacancy.opens_period!=period or vacancy not in vacancies(period,vacancy.airport):
            raise ValueError('Vaga expirada ou não pertence ao mercado deste período.')
        if self.conn.execute('SELECT 1 FROM job_applications WHERE status=?',('pending',)).fetchone():
            raise ValueError('Já existe uma candidatura em análise.')
        if self.conn.execute('SELECT 1 FROM job_applications WHERE vacancy_id=?',(vacancy.id,)).fetchone():
            raise ValueError('Esta vaga já recebeu uma candidatura tua.')
        # Uma candidatura por período impede reroll artificial depois de rejeição.
        if self.conn.execute('SELECT 1 FROM job_applications WHERE applied_utc>=? AND applied_utc<?',
            (period*7*86400,(period+1)*7*86400)).fetchone():
            raise ValueError('Limite: uma candidatura por semana.')
        ok,reason=employment_eligibility(vacancy,self.pilot_stats(),self.owned_qualifications())
        if not ok:
            raise ValueError(reason)
        profile=self.get_pilot()
        application={'vacancy':asdict(vacancy), 'callsign':profile['callsign'],
                     'stats':{'level':self.pilot_stats()['level'], 'hours':self.pilot_stats()['hours']}}
        with self.conn:
            self.conn.execute('INSERT INTO job_applications VALUES(?,?,?,?,?,NULL)',
                (vacancy.id,vacancy.company,json.dumps(application,ensure_ascii=False),now,'pending'))

    def review_applications(self, now: float) -> list[dict]:
        """Resolve candidaturas somente depois do encerramento do período.

        Não paga salários nem concede vaga de empresas reais; empregos são fictícios.
        """
        updates=[]
        current_period=weekly_period(now)
        applications=self.conn.execute("SELECT vacancy_id,data_json FROM job_applications WHERE status='pending'").fetchall()
        for vacancy_id,raw in applications:
            try:
                app=json.loads(raw)
                vacancy=Vacancy(**(app['vacancy'] if 'vacancy' in app else app))
            except (ValueError,TypeError,KeyError):
                continue
            if current_period < vacancy.closes_period:
                continue
            pilot=self.get_pilot()
            if pilot is None:
                continue
            application_key=app.get('callsign',pilot['callsign'])
            stored_stats=app.get('stats',self.pilot_stats())
            result='hired' if (self.employment_state()['mode']=='autonomo' and
                selection_result(vacancy,stored_stats,application_key)) else 'rejected'
            with self.conn:
                cursor=self.conn.execute("UPDATE job_applications SET status=?,decided_utc=? WHERE vacancy_id=? AND status='pending'",
                                         (result,now,vacancy_id))
                if cursor.rowcount:
                    if result=='hired':
                        self.conn.execute('UPDATE career_status SET mode=?,employer_code=?,owner_company=NULL,updated_utc=? WHERE id=1',
                                          ('empregado',vacancy.company,now))
                    updates.append({'vacancy_id':vacancy_id,'result':result,'company':vacancy.company})
        return updates

    def resign_employment(self, now: float) -> None:
        if self.employment_state()['mode'] != 'empregado':
            raise ValueError('Não há emprego ativo para encerrar.')
        with self.conn:
            self.conn.execute('UPDATE career_status SET mode=?,employer_code=NULL,updated_utc=? WHERE id=1',('autonomo',now))

    def found_company(self, company_name: str, now: float) -> dict:
        company_name=valid_company_name(company_name)
        if self.get_pilot() is None:
            raise ValueError('Cadastre um piloto primeiro.')
        if self.employment_state()['mode'] != 'autonomo':
            raise ValueError('Encerre o vínculo empregatício antes de fundar sua companhia.')
        stats=self.pilot_stats()
        if (stats['level']<OWN_MIN_LEVEL or stats['hours']<OWN_MIN_HOURS
                or 'PLA' not in stats['qualifications']):
            raise ValueError(f'Endgame: nível {OWN_MIN_LEVEL}, {OWN_MIN_HOURS:g} h e PLA obrigatórios.')
        with self.conn:
            row=self.conn.execute("SELECT value FROM settings WHERE key='balance'").fetchone()
            balance=int(row[0]) if row else 0
            if balance < OWN_INVESTMENT:
                raise ValueError(f'Investimento mínimo: {brl(OWN_INVESTMENT)}.')
            self._money_movement(f'company:{company_name}:{time_ns()}', 'fundacao', -OWN_INVESTMENT,
                                 'Registro da companhia própria')
            self.conn.execute('UPDATE career_status SET mode=?,employer_code=NULL,owner_company=?,updated_utc=? WHERE id=1',
                              ('empresario',company_name,now))
        return self.employment_state()

    def close(self):
        self.conn.close()
