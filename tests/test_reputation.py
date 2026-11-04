"""Validação da reputação persistida e da leitura pelo Dashboard v0.7.1."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from aerocarreira.reputation import reputation_from_flights, pilot_reputation
from aerocarreira.storage import Storage
from aerocarreira.dashboard import DashboardPresenter
from aerocarreira.fuel import FuelManager
from aerocarreira.domain import Career, FlightTracker


class ReputationTests(unittest.TestCase):
    def test_new_career_neutral(self):
        self.assertEqual(reputation_from_flights([])['score'], 50)

    def test_historical_records_survive_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'carreira.db'
            db = Storage(path)
            self.assertEqual(pilot_reputation(db.conn)['score'], 50)
            db.save_flight(dict(timestamp=100, lat=-8, lon=-35),
                           dict(timestamp=120, lat=-7.9, lon=-35), -210, 0, 'REG-1', 1800)
            self.assertEqual(pilot_reputation(db.conn)['score'], 53)
            db.close()
            again = Storage(path)
            self.assertEqual(pilot_reputation(again.conn)['score'], 53)
            again.close()

    def test_stall_hard_landing_and_no_soft_landing_farming(self):
        self.assertEqual(reputation_from_flights([(2000, 1, -700)])['score'], 42)
        self.assertEqual(reputation_from_flights([(2000, 0, -50)])['score'],
                         reputation_from_flights([(2000, 0, -100)])['score'])
        self.assertEqual(reputation_from_flights([(900, 0, None)] * 100)['score'], 100)
        self.assertEqual(reputation_from_flights([(0, 4, -1000)] * 100)['score'], 0)

    def test_presenter_reads_reputation_from_flight_history(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Storage(Path(temp) / 'career.db')
            app = SimpleNamespace(storage=db, fuel_manager=FuelManager(db), last_sample=None,
                airport_catalog=None, connected=False, mode='Desconectado', career=Career(),
                tracker=FlightTracker(), realism_frozen=0, status_var=Mock(get=lambda:'offline'),
                phase_var=Mock(get=lambda:'AGUARDANDO'), log_text=Mock(get=lambda *a:''),
                _saved_preflight=lambda:None)
            state = DashboardPresenter(app).snapshot()
            self.assertEqual(state['summary']['reputation']['score'], 50)
            db.close()


if __name__ == '__main__':
    unittest.main()
