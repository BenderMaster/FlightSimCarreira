"""Regressões: clima simulador vs METAR de estação, sem rede na GUI."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from aerocarreira.weather import MetarCache,metar_data,sim_conditions,within_nm
from aerocarreira.domain import FlightSample,FlightTracker,Career,MISSIONS
from aerocarreira.fuel import FuelManager
from aerocarreira.storage import Storage
from aerocarreira.dashboard import DashboardPresenter


class WeatherTests(unittest.TestCase):
    def test_no_metar_when_unknown_station(self):
        self.assertIsNone(metar_data([], 'SIPE'))
        self.assertIsNone(metar_data([{'icaoId':'SBRF','rawOb':'SBRF ...'}],'SIPE'))
    def test_metar_noaa_fields_source(self):
        obj=metar_data([{'icaoId':'SBJP','rawOb':'SBJP 041200Z 09008KT CAVOK 29/23 Q1013','wdir':90,'wspd':8}], 'SBJP')
        self.assertEqual(obj['wind_kt'],8)
        self.assertIn('NOAA',obj['source'])
    def test_cache_async_and_no_repeated_requests(self):
        calls=[]
        def request(code):
            calls.append(code)
            return {'icao':code,'raw':'METAR OBSERVADO'}
        c=MetarCache(request=request)
        self.assertIsNone(c.get('SBJP'))
        until=time.monotonic()+2
        while c.get('SBJP') is None and time.monotonic()<until:time.sleep(.02)
        self.assertEqual(len(calls),1)
        self.assertEqual(c.get('SBJP')['raw'],'METAR OBSERVADO')
    def test_sim_conditions_only_report_present(self):
        sample=SimpleNamespace(wind_direction_deg=90,wind_kt=6,ambient_temperature_c=28,
            visibility_m=None,sea_level_pressure_hpa=1012)
        s=sim_conditions(sample)
        self.assertEqual(s['wind_direction'],90)
        self.assertIsNone(s['visibility_m'])
        self.assertIn('MSFS',s['source'])
    def test_airport_proximity(self):
        self.assertTrue(within_nm(-8.1264,-34.9228,None,None,'SBRF'))
        self.assertFalse(within_nm(-7.14,-34.95,None,None,'SBRF'))
    def test_dashboard_does_not_invent_metar(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Storage(Path(tmp)/'carreira.db')
            a=SimpleNamespace(storage=db,fuel_manager=FuelManager(db),last_sample=None,
                airport_catalog=None,connected=False,mode='Desconectado',career=Career(),
                tracker=FlightTracker(),realism_frozen=0,status_var=Mock(get=lambda:'offline'),
                phase_var=Mock(get=lambda:'solo'),log_text=Mock(get=lambda *_:''),
                _saved_preflight=lambda:None)
            presenter=DashboardPresenter(a);s=presenter.snapshot()
            self.assertIsNone(s['weather']['origin'])
            self.assertIsNone(s['weather']['destination_metar'])
            db.close()


if __name__=='__main__':unittest.main()
