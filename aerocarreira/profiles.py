"""Perfis de carreira independentes; legado é sempre o banco raiz intacto."""
from __future__ import annotations
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path
from uuid import uuid4
from .pilot import validate_pilot


class ProfileManager:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = self.root / "pilot_profiles.json"
        if not self.index.exists():
            legacy = self.root / "carreira.db"
            if legacy.is_file():
                # Backup consistente do SQLite, inclusive conteúdo do WAL.
                backup = self.root / "carreira.pre_profiles.backup.db"
                if not backup.exists():
                    source = sqlite3.connect(f"file:{legacy}?mode=ro", uri=True)
                    target = sqlite3.connect(backup)
                    try:
                        source.backup(target)
                    finally:
                        target.close()
                        source.close()
            self._write({"version": 1, "active": "principal",
                         "profiles": [{"id": "principal", "name": "Carreira principal",
                                       "callsign": "", "home_icao": "", "kind": "official"}]})
        self.data = json.loads(self.index.read_text(encoding="utf-8"))
        if (self.data.get("version") != 1 or not isinstance(self.data.get("profiles"), list)
                or not self.data.get("active")):
            raise ValueError("Registro de perfis inválido; não foi sobrescrito.")
        if not any(p["id"] == self.data["active"] for p in self.data["profiles"]):
            raise ValueError("Perfil ativo ausente; nenhum banco foi modificado.")

    def _write(self, data):
        temp = self.index.with_name(self.index.name + ".new")
        try:
            with temp.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.index)
        finally:
            temp.unlink(missing_ok=True)

    def list(self):
        return [dict(p) for p in self.data["profiles"]]

    def get(self, profile_id):
        return next((dict(p) for p in self.data["profiles"] if p["id"] == profile_id), None)

    def active(self):
        return self.get(self.data["active"])

    def path(self, profile_id=None):
        profile = self.get(profile_id or self.data["active"])
        if not profile:
            raise ValueError("Perfil desconhecido.")
        if profile["id"] == "principal":
            return self.root
        if not re.fullmatch(r"[0-9a-f]{32}", profile["id"]):
            raise ValueError("Identificador de perfil inválido.")
        return self.root / "profiles" / profile["id"]

    def database(self, profile_id=None):
        return self.path(profile_id) / "carreira.db"

    def switch(self, profile_id):
        if not self.get(profile_id):
            raise ValueError("Perfil desconhecido.")
        if self.data["active"] == profile_id:
            return False
        next_data = dict(self.data, active=profile_id)
        self._write(next_data)
        self.data = next_data
        return True

    def update_active(self, name, callsign, home_icao):
        name, callsign, home_icao = validate_pilot(name, callsign, home_icao)
        for p in self.data["profiles"]:
            if p["id"] == self.data["active"]:
                p.update(name=name, callsign=callsign, home_icao=home_icao)
        self._write(self.data)

    def create(self, name, callsign, home_icao, *, test_admin=False):
        name, callsign, home_icao = validate_pilot(name, callsign, home_icao)
        if type(test_admin) is not bool:
            raise ValueError("Permissão de teste inválida.")
        if test_admin and name.casefold() != "teste":
            raise ValueError("O ambiente Admin deve ser criado com nome Teste.")
        profile_id = uuid4().hex
        profile = {"id": profile_id, "name": name, "callsign": callsign,
                   "home_icao": home_icao, "kind": "test" if test_admin else "official"}
        folder = self.root / "profiles" / profile_id
        folder.mkdir(parents=True, exist_ok=False)
        from .storage import Storage
        db = None
        try:
            db = Storage(folder / "carreira.db")
            db.create_pilot(name, callsign, home_icao)
            if test_admin:
                db.set_setting("pilot_test_guard_v1", "1")
            db.close()
            db = None
            self._write(dict(self.data, profiles=self.data["profiles"] + [profile]))
            self.data["profiles"].append(profile)
            return profile
        except Exception:
            if db:
                db.close()
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def reset_test(self, profile_id):
        profile = self.get(profile_id)
        if not profile or profile["kind"] != "test" or profile_id == "principal":
            raise ValueError("Somente o perfil Teste pode ser reiniciado.")
        folder = self.path(profile_id)
        current = folder / "carreira.db"
        if not current.is_file():
            raise ValueError("Banco de teste inexistente.")
        # O chamador DEVE fechar a conexão antes. Backup nunca é substituído.
        backup = folder / ("carreira.pre_reset." + uuid4().hex + ".db")
        shutil.copy2(current, backup)
        for suffix in ("", "-wal", "-shm"):
            (folder / ("carreira.db" + suffix)).unlink(missing_ok=True)
        from .storage import Storage
        db = Storage(current)
        try:
            db.create_pilot(profile["name"], profile["callsign"], profile["home_icao"])
            db.set_setting("pilot_test_guard_v1", "1")
        finally:
            db.close()
        return backup
