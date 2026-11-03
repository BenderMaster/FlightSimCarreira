"""Base própria SQLite: nunca lê/escreve NeoFly."""
import json
import sqlite3
from time import time
from .pilot import validate_pilot, qualification_eligibility, QUAL_BY_CODE, flight_xp
from .contracts import aircraft_family, aircraft_model, pilot_level, next_level_xp
from .domain import Mission
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
        self.conn.commit()
        if self.get_setting("balance") is None:
            self.set_setting("balance", "5000")

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
                        aircraft_title: str | None = None) -> bool:
        """Pouso+crédito+estado em UMA transação; repetição não duplica dinheiro.

        A identidade é determinada pela decolagem original e sobrevive a reinícios.
        """
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
            cursor = self.conn.execute('''INSERT OR IGNORE INTO flights
                (started_utc,ended_utc,from_lat,from_lon,to_lat,to_lon,
                touchdown_fpm_est,stall_warnings,mission_id,reward,flight_key,aircraft_title)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (start["timestamp"], end["timestamp"], start["lat"], start["lon"],
                 end["lat"], end["lon"], touchdown_fpm_est, stalls,
                 mission_id, actual_reward, flight_key, aircraft_title))
            inserted = cursor.rowcount == 1
            if inserted:
                old_balance = int(self.get_setting("balance") or 5000)
                new_balance = old_balance + actual_reward
                if self.get_pilot() is not None:
                    self.conn.execute("INSERT OR IGNORE INTO pilot_xp_ledger(flight_key,xp,awarded_utc) VALUES(?,?,?)",
                                      (flight_key, flight_xp(actual_reward), time()))
                self.conn.execute("INSERT INTO settings(key,value) VALUES('balance',?) "
                                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(new_balance),))
                self.conn.execute("INSERT INTO settings(key,value) VALUES('flight_checkpoint_v1',?) "
                                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                  (json.dumps(checkpoint, ensure_ascii=False),))
        return inserted

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
                code, progress["qualifications"], progress["flights"], progress["xp"])
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
                raise ValueError(f'Investimento mínimo: ${OWN_INVESTMENT:,}.')
            self.conn.execute("UPDATE settings SET value=? WHERE key='balance'",(str(balance-OWN_INVESTMENT),))
            self.conn.execute('UPDATE career_status SET mode=?,employer_code=NULL,owner_company=?,updated_utc=? WHERE id=1',
                              ('empresario',company_name,now))
        return self.employment_state()

    def close(self):
        self.conn.close()
