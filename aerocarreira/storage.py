"""Base própria SQLite: nunca lê/escreve NeoFly."""
import json
import sqlite3
from pathlib import Path
from typing import Optional


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
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

    def list_flights(self):
        return self.conn.execute("SELECT id, started_utc, ended_utc, touchdown_fpm_est, stall_warnings, mission_id, reward FROM flights ORDER BY id DESC LIMIT 100").fetchall()

    def close(self):
        self.conn.close()
