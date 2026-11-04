"""v0.7.3: proa verdadeira do MSFS e contratos freelancer no dashboard."""
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from aerocarreira.sim_adapter import OPTIONAL, SampleReader, true_heading_degrees
from aerocarreira.domain import FlightSample, FlightTracker, Career, Mission, Phase
from aerocarreira.dashboard import DashboardPresenter, mission_data
from aerocarreira.fuel import FuelManager
from aerocarreira.storage import Storage


class TrueHeadingTests(unittest.TestCase):
    def test_true_heading_simvar_declared_optional_radians(self):
        self.assertEqual(OPTIONAL['heading_true_rad'], 'PLANE_HEADING_DEGREES_TRUE')
        self.assertAlmostEqual(true_heading_degrees(math.radians(15)),15)
        self.assertAlmostEqual(true_heading_degrees(math.radians(350)),350)
        self.assertAlmostEqual(true_heading_degrees(2*math.pi),0)
        self.assertAlmostEqual(true_heading_degrees(-math.pi/2),270)
        self.assertEqual(true_heading_degrees(0),0)

    def test_missing_corrupt_heading_never_disconnects(self):
        for value in (None,'NaN',float('inf'),'bad'):
            self.assertIsNone(true_heading_degrees(value))
        essential={'PLANE_LATITUDE':-8.1,'PLANE_LONGITUDE':-34.9,
                    'PLANE_ALTITUDE':900,'PLANE_ALT_ABOVE_GROUND':5,
                    'AIRSPEED_INDICATED':0,'SIM_ON_GROUND':1,
                    'GROUND_VELOCITY':0,'VERTICAL_SPEED':0}
        reader=SampleReader(essential,clock=lambda:30)
        sample,missing=reader.read()
        self.assertEqual(missing,[])
        self.assertIsNone(sample.heading_true_deg)

    def test_reader_converts_heading_while_aircraft_stationary(self):
        essentials={'PLANE_LATITUDE':-8.1,'PLANE_LONGITUDE':-34.9,
                    'PLANE_ALTITUDE':900,'PLANE_ALT_ABOVE_GROUND':5,
                    'AIRSPEED_INDICATED':0,'SIM_ON_GROUND':1,
                    'GROUND_VELOCITY':0,'VERTICAL_SPEED':0,
                    'PLANE_HEADING_DEGREES_TRUE':math.radians(15)}
        reader=SampleReader(essentials,clock=lambda:30)
        first,_=reader.read()
        self.assertAlmostEqual(first.heading_true_deg,15)
        essentials['PLANE_HEADING_DEGREES_TRUE']=math.radians(110)
        second,_=reader.read()
        self.assertAlmostEqual(second.heading_true_deg,110)
        self.assertEqual(first.latitude,second.latitude)
        self.assertEqual(first.longitude,second.longitude)

    def test_freelancer_metadata_preserved(self):
        m=Mission('x','SBRF','SIPE','Freelancer',1000,
                  category='cargo',freelance=True,employer_plane='c152',
                  origin_lat=-8.1,origin_lon=-34.9,
                  destination_lat=-7.7,destination_lon=-34.8)
        data=mission_data(m)
        self.assertTrue(data['freelance'])
        self.assertEqual(data['employer_plane'],'c152')
        self.assertEqual(data['reward'],1000)


if __name__=='__main__':
    unittest.main()
