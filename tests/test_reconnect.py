"""Regressões da falha real GROUND_VELOCITY e retomada após reconexão."""
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from aerocarreira.domain import AIRPORTS, MISSIONS, Career, FlightTracker, FlightSample, Phase, distance_nm
from aerocarreira.sim_adapter import SampleReader
from aerocarreira.storage import Storage


class FakeRequests:
    def __init__(self, overrides=None):
        self.values = {
            'PLANE_LATITUDE': -7.65, 'PLANE_LONGITUDE': -34.85,
            'PLANE_ALTITUDE': 1200, 'PLANE_ALT_ABOVE_GROUND': 1165,
            'AIRSPEED_INDICATED': 75, 'GROUND_VELOCITY': 72,
            'VERTICAL_SPEED': -260, 'SIM_ON_GROUND': 0,
            'STALL_WARNING': 0, 'FUEL_TOTAL_QUANTITY': 9.5,
        }
        self.values.update(overrides or {})

    def get(self, key):
        value = self.values[key]
        if isinstance(value, Exception):
            raise value
        return value


class ReaderTests(unittest.TestCase):
    def test_ground_velocity_none_does_not_terminate_or_invalidate_sample(self):
        req = FakeRequests({'GROUND_VELOCITY': None})
        rd = SampleReader(req, clock=lambda: 100)
        sample, missing = rd.read()
        self.assertEqual(missing, [])
        self.assertTrue(sample.groundspeed_estimated)
        self.assertEqual(sample.groundspeed_kt, sample.ias_kt)
        self.assertEqual(rd.soft_missing, {'GROUND_VELOCITY'})
        req.values['GROUND_VELOCITY'] = 72
        sample, missing = rd.read()
        self.assertFalse(sample.groundspeed_estimated)
        self.assertEqual(sample.groundspeed_kt, 72)

    def test_transient_critical_loss_skips_sample_without_crash(self):
        req = FakeRequests({'SIM_ON_GROUND': None})
        rd = SampleReader(req)
        sample, missing = rd.read()
        self.assertIsNone(sample)
        self.assertIn('SIM_ON_GROUND', missing)
        req.values['SIM_ON_GROUND'] = 1
        sample, missing = rd.read()
        self.assertIsNotNone(sample)
        self.assertTrue(sample.on_ground)

    def test_soft_simvar_exception_degrades_but_preserves_telemetry(self):
        req = FakeRequests({'GROUND_VELOCITY': RuntimeError('sem resposta'),
                            'VERTICAL_SPEED': None})
        s, missing = SampleReader(req).read()
        self.assertEqual(missing, [])
        self.assertEqual(s.vs_fpm, 0)
        self.assertTrue(s.groundspeed_estimated)


class RecoveryTests(unittest.TestCase):
    def sample(self, t, code, ground, agl=0, gs=0, vs=0):
        ap = AIRPORTS[code]
        return FlightSample(t, ap.latitude, ap.longitude, 33+agl, agl,
                            55 if not ground else 0, gs, vs, ground)

    def test_nearby_airfield_is_sifc(self):
        a, b = AIRPORTS['SIPE'], AIRPORTS['SIFC']
        d = distance_nm(a.latitude, a.longitude, b.latitude, b.longitude)
        self.assertTrue(9 < d < 15, d)
        self.assertEqual(next(m for m in MISSIONS if m.id == 'ITA-IGA').destination, 'SIFC')

    def test_resume_after_restart_on_final_and_credit_only_once(self):
        m = next(m for m in MISSIONS if m.id == 'ITA-IGA')
        tr = FlightTracker()
        c = Career()
        c.accept(m, self.sample(100, 'SIPE', True))
        tr.update(self.sample(100, 'SIPE', True))
        c.evaluate(tr.update(self.sample(105, 'SIPE', False, 35, 58, 350)))
        tr.update(self.sample(140, 'SIPE', False, 1500, 75, 0))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'carreira.db'
            db = Storage(path)
            db.set_checkpoint({'version': 1, 'career': c.snapshot(), 'tracker': tr.snapshot()})
            db.close()
            db = Storage(path)
            cp = db.get_checkpoint()
            resumed = FlightTracker.from_snapshot(cp['tracker'])
            career = Career(int(db.get_setting('balance')))
            career.restore(cp['career'])
            self.assertEqual(resumed.phase, Phase.AIRBORNE)
            self.assertEqual(career.mission.id, 'ITA-IGA')
            # MSFS não enviou nenhuma amostra por ~12 min, mas voltou em solo no destino.
            self.assertEqual(resumed.update(self.sample(900, 'SIFC', True, 0, 28, -95)), [])
            events = resumed.update(self.sample(903, 'SIFC', True))
            self.assertEqual([e['type'] for e in events], ['landing'])
            payment = career.evaluate(events)
            self.assertEqual(payment['reward'], 420)
            start = next(e for e in resumed.events if e['type'] == 'takeoff')
            after = FlightTracker(); after.update(self.sample(903, 'SIFC', True))
            final = {'version':1, 'career':career.snapshot(), 'tracker':after.snapshot()}
            args = (start, events[0], events[0]['touchdown_fpm_est'], resumed.stalls, payment['mission'], 420, final)
            self.assertTrue(db.finalize_flight(*args))
            self.assertFalse(db.finalize_flight(*args))
            self.assertEqual(db.get_setting('balance'), '5420')
            self.assertEqual(len(db.list_flights()), 1)
            self.assertIsNone(db.get_checkpoint()['career']['mission_id'])
            db.close()

    def test_old_database_migrates_without_losing_flights(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'legacy.db'
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute("INSERT INTO settings VALUES ('balance', '5850')")
            db.execute('''CREATE TABLE flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT, started_utc REAL NOT NULL, ended_utc REAL NOT NULL,
                from_lat REAL, from_lon REAL, to_lat REAL, to_lon REAL,
                touchdown_fpm_est REAL, stall_warnings INTEGER NOT NULL,
                mission_id TEXT, reward INTEGER NOT NULL DEFAULT 0)''')
            db.execute("INSERT INTO flights (started_utc,ended_utc,stall_warnings,mission_id,reward) VALUES (1,10,0,'REC-ITA',850)")
            db.commit(); db.close()
            upgraded = Storage(path)
            self.assertEqual(upgraded.get_setting('balance'), '5850')
            self.assertEqual(len(upgraded.list_flights()), 1)
            fields = {row[1] for row in upgraded.conn.execute('PRAGMA table_info(flights)')}
            self.assertIn('flight_key', fields)
            upgraded.close()

    def test_checkpoint_keeps_unknown_airport_from_paying(self):
        c = Career()
        m = next(m for m in MISSIONS if m.id == 'ITA-IGA')
        c.accept(m, self.sample(0, 'SIPE', True))
        c.evaluate([{'type':'takeoff','timestamp':10,'lat':AIRPORTS['SIPE'].latitude,
                     'lon':AIRPORTS['SIPE'].longitude}])
        recovered = Career(); recovered.restore(c.snapshot())
        self.assertIsNone(recovered.evaluate([{'type':'landing','timestamp':200,
            'lat':AIRPORTS['SBJP'].latitude,'lon':AIRPORTS['SBJP'].longitude}]))
        self.assertEqual(recovered.balance, 5000)


if __name__ == '__main__': unittest.main()

class WorkerTests(unittest.TestCase):
    def test_single_ground_velocity_failure_keeps_worker_connected(self):
        import sys
        import types
        import time
        from unittest.mock import patch
        from queue import Queue, Empty
        from aerocarreira.sim_adapter import SimConnectWorker
        class FakeConnection:
            quit = False
            def exit(self): pass
        class FakeAQ(FakeRequests):
            def __init__(self, connection, _time=200):
                super().__init__({'GROUND_VELOCITY': None})
        fake = types.ModuleType('SimConnect')
        fake.SimConnect = FakeConnection
        fake.AircraftRequests = FakeAQ
        q=Queue()
        with patch.dict(sys.modules, {'SimConnect':fake}):
            worker=SimConnectWorker(q,interval=0.01,generation=33,reconnect_delay=0.01)
            worker.start()
            deadline=time.monotonic()+1.0
            msgs=[]
            while time.monotonic()<deadline:
                try:
                    msg=q.get(timeout=0.05)
                    msgs.append(msg)
                    if msg[0]=='sample': break
                except Empty:
                    pass
            worker.stop()
            worker.thread.join(timeout=2)
        self.assertTrue(any(x[0]=='sample' for x in msgs),msgs)
        self.assertFalse(any(x[0]=='warning' and 'Conexão interrompida' in x[1] for x in msgs),msgs)
        self.assertTrue(all(x[2]==33 for x in msgs))
