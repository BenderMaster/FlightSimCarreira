"""Bloco 1: migração sem perda, cadastro, XP idempotente e habilitações."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from aerocarreira.pilot import validate_pilot, qualification_eligibility, QUALIFICATIONS
from aerocarreira.storage import Storage


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Storage(Path(self.temp.name) / "career.sqlite")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def flight(self, i, reward=420):
        start = {"timestamp": 1000 + i*100, "lat": -7.6566, "lon": -34.8569}
        end = {"timestamp": 1030 + i*100, "lat": -7.8444, "lon": -34.8913}
        return self.db.finalize_flight(start, end, -172, 0, "ITA-IGA" if reward else None,
                                       reward, {"career": {"mission_id": None}, "tracker": {"phase": "solo"}})

    def test_new_pilot_defaults_to_initial_virtual_qualification(self):
        self.assertIsNone(self.db.get_pilot())
        p = self.db.create_pilot("  Capitão   de Teste  ", "fs1234", "sbrf")
        self.assertEqual((p["name"], p["callsign"], p["home_icao"]),
                         ("Capitão de Teste", "FS1234", "SBRF"))
        self.assertEqual(self.db.owned_qualifications(), {"PPA"})
        self.assertEqual(self.db.get_setting("balance"), "5000")
        with self.assertRaises(ValueError):
            self.db.create_pilot("Outro Piloto", "FS9999", "SBJP")

    def test_validation_rejects_invalid_profile(self):
        for args in [("a", "ABC1", "SBRF"), ("Nome", "?", "SBRF"),
                     ("Nome", "FS123", "SIPE123"), ("Nome\nA", "FS123", "SBRF")]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                validate_pilot(*args)
        self.assertIsNone(self.db.get_pilot())

    def test_edit_keeps_qualifications_and_money(self):
        self.db.set_setting("balance", "6270")
        self.db.create_pilot("Primeiro Piloto", "FS0001", "SBRF")
        self.db.update_pilot("Novo Piloto", "FS0002", "SIPE")
        self.assertEqual(self.db.get_pilot()["home_icao"], "SIPE")
        self.assertEqual(self.db.get_setting("balance"), "6270")
        self.assertEqual(self.db.owned_qualifications(), {"PPA"})
        self.assertRaises(ValueError, self.db.update_pilot, "", "FS0002", "SIPE")
        self.assertEqual(self.db.get_pilot()["name"], "Novo Piloto")

    def test_xp_earned_once_per_real_flight_and_no_soft_landing_bonus(self):
        self.db.create_pilot("Piloto Teste", "FS0001", "SIPE")
        self.assertTrue(self.flight(1))
        self.assertFalse(self.flight(1))
        stats = self.db.pilot_stats()
        self.assertEqual((stats["xp"], stats["flights"]), (40, 1))
        self.assertEqual(self.db.get_setting("balance"), "5420")
        self.assertEqual(len(self.db.list_flights()), 1)
        self.assertTrue(self.flight(2, reward=0))
        self.assertEqual(self.db.pilot_stats()["xp"], 65)

    def test_qualifications_unlock_only_at_threshold_and_prerequisites(self):
        self.db.create_pilot("Piloto Teste", "FS0001", "SIPE")
        self.assertRaises(ValueError, self.db.earn_qualification, "PCA")
        for i in range(4):
            self.assertTrue(self.flight(i))
        self.assertEqual(self.db.pilot_stats()["xp"], 160)
        self.assertTrue(self.db.earn_qualification("PCA"))
        self.assertRaises(ValueError,
                          self.db.earn_qualification, "PCA")
        self.assertRaises(ValueError, self.db.earn_qualification, "IFR")
        for i in range(4, 8):
            self.flight(i)
        self.assertTrue(self.db.earn_qualification("IFR"))
        self.assertRaises(ValueError, self.db.earn_qualification, "MLTE")
        for i in range(8, 12):
            self.flight(i)
        self.assertTrue(self.db.earn_qualification("MLTE"))
        self.assertRaises(ValueError, self.db.earn_qualification, "PLA")
        for i in range(12, 40):
            self.flight(i)
        self.assertTrue(self.db.earn_qualification("PLA"))
        self.assertEqual(self.db.owned_qualifications(), {q.code for q in QUALIFICATIONS})

    def test_profile_and_progress_survive_restart(self):
        self.db.create_pilot("Piloto Teste", "FS0001", "SIPE")
        self.flight(1)
        self.db.close()
        self.db = Storage(Path(self.temp.name) / "career.sqlite")
        self.assertEqual(self.db.get_pilot()["callsign"], "FS0001")
        self.assertEqual(self.db.pilot_stats()["xp"], 40)
        self.assertEqual(self.db.get_setting("balance"), "5420")

    def test_legacy_database_migration_preserves_money_flights_and_checkpoint(self):
        self.db.close()
        path = Path(self.temp.name) / "career.sqlite"
        db = sqlite3.connect(path)
        db.execute("DELETE FROM settings")
        db.execute("INSERT INTO settings VALUES ('balance','6270')")
        db.execute("INSERT INTO settings VALUES('flight_checkpoint_v1','{\"version\":1,\"career\":{\"mission_id\":null}}')")
        db.execute('''INSERT INTO flights(started_utc,ended_utc,from_lat,from_lon,to_lat,to_lon,
            touchdown_fpm_est,stall_warnings,mission_id,reward)
            VALUES (1,3601,-7,-34,-7,-34,-172,0,'ITA-IGA',420)''')
        db.execute("DROP TABLE IF EXISTS pilot_profile")
        db.execute("DROP TABLE IF EXISTS pilot_qualifications")
        db.execute("DROP TABLE IF EXISTS pilot_xp_ledger")
        db.commit(); db.close()
        self.db = Storage(path)
        self.assertEqual(self.db.get_setting("balance"), "6270")
        self.assertEqual(self.db.pilot_stats()["flights"], 1)
        self.assertAlmostEqual(self.db.pilot_stats()["hours"], 1.0)
        self.assertEqual(self.db.pilot_stats()["xp"], 0)
        self.assertIsNone(self.db.get_pilot())
        self.assertIsNone(self.db.get_checkpoint()["career"]["mission_id"])
        self.db.create_pilot("Piloto Teste", "FS0001", "SIPE")
        self.assertEqual(self.db.pilot_stats()["xp"], 0)

    def test_no_xp_generated_without_registered_pilot(self):
        self.flight(1)
        self.assertEqual(self.db.pilot_stats()["xp"], 0)
        self.db.create_pilot("Piloto Teste", "FS0001", "SIPE")
        self.assertEqual(self.db.pilot_stats()["flights"], 1)
        self.assertEqual(self.db.pilot_stats()["xp"], 0)

    def test_missing_qualification_or_pilot_is_rejected(self):
        self.assertRaises(ValueError, self.db.earn_qualification, "PCA")
        self.db.create_pilot("Piloto Teste", "FS0001", "SIPE")
        self.assertRaises(ValueError, self.db.earn_qualification, "NAO_EXISTE")
        self.assertEqual(qualification_eligibility("PCA", {"PPA"}, 4, 160), (True, "Disponível"))
        self.assertEqual(qualification_eligibility("MLTE", {"PPA"}, 50, 3000)[0], False)


if __name__ == "__main__":
    unittest.main()
