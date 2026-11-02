"""Base própria SQLite: nunca lê/escreve NeoFly."""
import json
import sqlite3
from time import time
from .pilot import validate_pilot, qualification_eligibility, QUAL_BY_CODE, flight_xp
from pathlib import Path
from typing import Optional


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
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
                        mission_id: str | None, reward: int, checkpoint: dict) -> bool:
        """Pouso+crédito+estado em UMA transação; repetição não duplica dinheiro.

        A identidade é determinada pela decolagem original e sobrevive a reinícios.
        """
        flight_key = f"takeoff:{float(start['timestamp']):.6f}:{float(start['lat']):.7f}:{float(start['lon']):.7f}"
        with self.conn:
            cursor = self.conn.execute('''INSERT OR IGNORE INTO flights
                (started_utc,ended_utc,from_lat,from_lon,to_lat,to_lon,
                touchdown_fpm_est,stall_warnings,mission_id,reward,flight_key)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (start["timestamp"], end["timestamp"], start["lat"], start["lon"],
                 end["lat"], end["lon"], touchdown_fpm_est, stalls,
                 mission_id, reward, flight_key))
            inserted = cursor.rowcount == 1
            if inserted:
                old_balance = int(self.get_setting("balance") or 5000)
                new_balance = old_balance + reward
                if self.get_pilot() is not None:
                    self.conn.execute("INSERT OR IGNORE INTO pilot_xp_ledger(flight_key,xp,awarded_utc) VALUES(?,?,?)",
                                      (flight_key, flight_xp(reward), time()))
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
        return {"flights": int(flights), "hours": float(duration) / 3600,
                "xp": int(xp), "qualifications": self.owned_qualifications()}

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

    def close(self):
        self.conn.close()
