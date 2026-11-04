"""v0.7.6: proa magnética, pista, taxi pós-pouso, XP e ETA por aeronave."""
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from aerocarreira.domain import FlightSample, FlightTracker, Mission
from aerocarreira.dashboard import mission_data
from aerocarreira.sim_adapter import SampleReader, OPTIONAL
from aerocarreira.taxi import PostLandingTaxi, heading_delta
from aerocarreira.storage import Storage
from aerocarreira.planning import Preflight, inspect_preflight


def sample(t,ground=True,gs=0,ias=None,hdg=90,runway=None,**kwargs):
    return FlightSample(t,-8.126,-34.923,100,0,
        gs if ias is None else ias,gs,0,ground,
        heading_true_deg=hdg,on_any_runway=runway,**kwargs)


def observe_takeoff(tr,sequence):
    for point in sequence:
        if not point.on_ground:
            point=replace(point,agl_ft=12)
        tr.update(point)


class V076Tests(unittest.TestCase):
    def test_magnetic_heading_and_runway_simvars(self):
        self.assertEqual(heading_delta(350,10),20)
        self.assertIsNone(heading_delta(None,20))
        data={'PLANE_LATITUDE':-8.1,'PLANE_LONGITUDE':-34.9,'PLANE_ALTITUDE':100,
            'PLANE_ALT_ABOVE_GROUND':0,'AIRSPEED_INDICATED':0,'SIM_ON_GROUND':1,
            'GROUND_VELOCITY':0,'VERTICAL_SPEED':0,
            'PLANE_HEADING_DEGREES_TRUE':math.radians(301),
            'PLANE_HEADING_DEGREES_MAGNETIC':math.radians(322),'ON_ANY_RUNWAY':1}
        s,_=SampleReader(data,clock=lambda:10).read()
        self.assertAlmostEqual(s.heading_true_deg,301)
        self.assertAlmostEqual(s.heading_magnetic_deg,322)
        self.assertTrue(s.on_any_runway)
        self.assertEqual(OPTIONAL['on_any_runway'],'ON_ANY_RUNWAY')
        data.pop('ON_ANY_RUNWAY')
        s,_=SampleReader(data,clock=lambda:12).read()
        self.assertIsNone(s.on_any_runway)

    def test_runway_roll_acceleration_not_taxi_violation(self):
        tr=FlightTracker()
        observe_takeoff(tr,[sample(0),sample(4,True,27,20,runway=True),
            sample(18,True,39,32,runway=True),sample(24,False,63,63,runway=True)])
        self.assertEqual(tr.taxi_violations,0)

    def test_fallback_unknown_runway_straight_acceleration(self):
        tr=FlightTracker()
        observe_takeoff(tr,[sample(0),sample(3,True,27,21),
            sample(15,True,36,32),sample(20,False,66,66)])
        self.assertEqual(tr.taxi_violations,0)

    def test_custom_runway_false_but_straight_acceleration_is_exempt(self):
        # Cenário do MSFS onde ON ANY RUNWAY falha em pista customizada.
        tr=FlightTracker()
        observe_takeoff(tr,[sample(0),sample(3,True,27,21,runway=False),
            sample(15,True,36,32,runway=False),
            sample(20,False,66,66,runway=False)])
        self.assertEqual(tr.taxi_violations,0)

    def test_incorrect_runway_false_during_rollout_is_not_taxi(self):
        monitor=PostLandingTaxi.begin({'timestamp':5,'lat':-8,'lon':-34},
            sample(100,True,60,60,runway=False))
        self.assertIsNone(monitor.observe(sample(105,True,42,40,runway=False)))
        self.assertIsNone(monitor.observe(sample(115,True,27,25,runway=False)))
        self.assertIsNone(monitor.observe(sample(130,True,25,23,runway=False)))
        self.assertEqual(monitor.phase,'rollout')
        self.assertIsNone(monitor.observe(sample(135,True,8,8,runway=False)))
        self.assertEqual(monitor.phase,'taxi')
        self.assertFalse(monitor.penalty_marked)

    def test_known_taxiway_fast_includes_before_takeoff(self):
        tr=FlightTracker()
        observe_takeoff(tr,[sample(0),sample(3,True,29,22,runway=False),
            sample(15,True,31,23,runway=False),sample(17,True,12,10,runway=False),
            sample(35,True,40,37,runway=True),sample(40,False,67,67,runway=True)])
        self.assertEqual(tr.taxi_violations,1)

    def test_fallback_fast_turn_versus_straight_run(self):
        tr=FlightTracker()
        observe_takeoff(tr,[sample(0),sample(3,True,30,22,hdg=90),
            sample(13,True,34,25,hdg=135),sample(17,True,5,5,hdg=140),
            sample(40,False,67,67,hdg=140)])
        self.assertEqual(tr.taxi_violations,1)
        saved=FlightTracker.from_snapshot(tr.snapshot())
        self.assertEqual(saved.taxi_violations,1)

    def test_landing_rollout_is_exempt_until_exit_or_slowdown(self):
        monitor=PostLandingTaxi.begin({'timestamp':5,'lat':-8,'lon':-34},
            sample(100,True,65,65,runway=True))
        for point in [sample(101,True,57,55,runway=True),
                      sample(111,True,44,43,runway=True),
                      sample(121,True,31,30,runway=True)]:
            self.assertIsNone(monitor.observe(point))
        self.assertEqual(monitor.phase,'rollout')

    def test_postlanding_taxi_deducts_once_after_slowdown(self):
        m=PostLandingTaxi.begin({'timestamp':5,'lat':-8,'lon':-34},
            sample(100,True,59,59,hdg=90,runway=True))
        for point in [sample(105,True,45,44,runway=True),
                      sample(115,True,8,8,runway=True),
                      sample(120,True,28,25,runway=False),
                      sample(130,True,30,28,runway=False)]:
            event=m.observe(point)
        self.assertEqual(event,m.flight_key)
        self.assertIsNone(m.observe(sample(132,True,32,30,runway=False)))
        self.assertTrue(PostLandingTaxi.from_snapshot(m.snapshot()).penalty_marked)

    def test_postlanding_turn_identifies_taxi(self):
        m=PostLandingTaxi.begin({'timestamp':1,'lat':-8,'lon':-34},
            sample(40,True,60,60,hdg=350,runway=True))
        self.assertIsNone(m.observe(sample(41,True,51,51,hdg=350,runway=True)))
        self.assertIsNone(m.observe(sample(45,True,30,30,hdg=24,runway=False)))
        self.assertEqual(m.phase,'taxi')
        self.assertIsNone(m.observe(sample(51,True,28,28,hdg=40,runway=True)))

    def test_idempotent_postlanding_penalty_isolated_to_same_flight(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Storage(Path(folder)/'carreira.db')
            db.create_pilot('Piloto','QA1','SBRF')
            start={'timestamp':10,'lat':-8.1,'lon':-34.9}
            end={'timestamp':120,'lat':-8.2,'lon':-34.8}
            self.assertTrue(db.finalize_flight(start,end,-100,0,None,0,{'version':1}))
            key=PostLandingTaxi.begin(start,sample(120)).flight_key
            self.assertEqual(db.apply_postflight_taxi_penalty(key),2)
            self.assertEqual(db.apply_postflight_taxi_penalty(key),0)
            self.assertEqual(db.conn.execute('SELECT xp FROM pilot_xp_ledger WHERE flight_key=?',
                (key,)).fetchone()[0],23)
            self.assertEqual(db.conn.execute('SELECT COUNT(*) FROM flights').fetchone()[0],1)
            self.assertEqual(db.get_setting('balance'),'5000')
            db.close()

    def test_per_aircraft_eta_and_no_weather_component(self):
        mission=Mission('T','SBRF','SBJP','Carga',1900,origin_lat=-8.126,
            origin_lon=-34.923,destination_lat=-7.148,destination_lon=-34.95)
        slow=mission_data(mission,'c152')
        fast=mission_data(mission,'cj4')
        self.assertGreater(slow['minutes'],fast['minutes'])
        self.assertEqual(slow['aircraft_label'],'Cessna 152')
        self.assertEqual(fast['cruise_kts'],340)
        planned=Preflight('T','Cessna 152',real_weather_declared=True)
        pre=inspect_preflight(mission,planned)
        self.assertEqual(pre['bonus_fraction'],0)
        self.assertFalse(any('Clima' in k for k in pre['components']))

if __name__=='__main__':
    unittest.main()
