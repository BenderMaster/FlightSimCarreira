"""Regressões de progresso visual e exigência de horas (sem Tk em CI)."""
import tempfile
import unittest
from pathlib import Path
from aerocarreira.contracts import next_level_xp, pilot_level
from aerocarreira.pilot import (QUALIFICATIONS, qualification_eligibility,
                                progress_fraction, level_progress)
from aerocarreira.storage import Storage


class ProgressLogicTests(unittest.TestCase):
    def test_level_bar_uses_the_current_level_interval(self):
        self.assertEqual(level_progress(0)["fraction"], 0)
        self.assertAlmostEqual(level_progress(80)["fraction"], 80/115)
        self.assertEqual(level_progress(80)["remaining"], 35)
        self.assertEqual(level_progress(115)["level"], 2)
        self.assertEqual(level_progress(115)["fraction"], 0)
        self.assertEqual(level_progress(260)["level"], 3)
        self.assertEqual(level_progress(260)["fraction"], 0)
        level_3 = level_progress(300)
        self.assertEqual(level_3["level"], pilot_level(300))
        self.assertAlmostEqual(level_3["fraction"], (300-260)/(next_level_xp(3)-260))
        self.assertEqual(level_progress(-50)["fraction"], 0)
        self.assertIsNone(level_progress(1_000_000)["next_level"])
        self.assertEqual(level_progress(1_000_000)["fraction"], 1)

    def test_bar_caps_at_100_percent_and_zero_goal_is_complete(self):
        self.assertEqual(progress_fraction(20, 0), 1)
        self.assertEqual(progress_fraction(1000, 40), 1)
        self.assertEqual(progress_fraction(-1, 40), 0)
        self.assertEqual(progress_fraction(20, 40), .5)

    def test_pca_needs_hours_flights_and_xp_independently(self):
        owned={"PPA"}
        for flights, xp, hours, expected in [
            (8, 160, 9.99, "horas"),
            (7, 160, 10, "voos"),
            (8, 159, 10, "XP"),
        ]:
            ok,reason=qualification_eligibility("PCA",owned,flights,xp,hours)
            self.assertFalse(ok)
            self.assertIn(expected,reason)
        self.assertEqual(qualification_eligibility("PCA",owned,8,160,10), (True,"Disponível"))

    def test_all_advanced_qualifications_require_hours(self):
        for q in QUALIFICATIONS[1:]:
            self.assertGreater(q.hours,0)
            required=set(q.prerequisites)
            self.assertFalse(qualification_eligibility(q.code,required,q.flights,q.xp,q.hours-0.1)[0])
            self.assertTrue(qualification_eligibility(q.code,required,q.flights,q.xp,q.hours)[0])

    def test_existing_awarded_qualification_survives_threshold_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'career.db'
            db=Storage(path)
            db.create_pilot('Piloto Antigo','PIL123','SIPE')
            with db.conn:
                db.conn.execute("INSERT INTO pilot_qualifications(code,awarded_utc) VALUES('PCA',100)")
            db.set_setting('balance','7740')
            db.close()
            db=Storage(path)
            self.assertEqual(db.get_setting('balance'),'7740')
            self.assertIn('PCA',db.owned_qualifications())
            self.assertEqual(db.pilot_stats()['hours'],0)
            self.assertFalse(qualification_eligibility('PCA',{'PPA'},8,160,0)[0])
            db.close()

    def test_actual_flight_duration_counts_for_unlock(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Storage(Path(directory)/'career.db')
            db.create_pilot('Piloto Teste','PIL000','SIPE')
            with db.conn:
                for i in range(8):
                    db.conn.execute('INSERT INTO flights (started_utc,ended_utc,stall_warnings) VALUES(?,?,0)',
                                    (i*10000,i*10000+4500))
                db.conn.execute("INSERT INTO pilot_xp_ledger(flight_key,xp,awarded_utc) VALUES('test',160,100)")
            self.assertAlmostEqual(db.pilot_stats()['hours'],10)
            self.assertTrue(db.earn_qualification('PCA'))
            db.close()

if __name__ == '__main__': unittest.main()
