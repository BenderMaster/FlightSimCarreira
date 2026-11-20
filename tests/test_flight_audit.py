"""Regressão v0.7.5: telemetria, procedimentos, arremetida e XP idempotente."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from aerocarreira.domain import FlightSample, FlightTracker, Phase
from aerocarreira.flight_audit import (
    real_clock_verified, assistance_verified, flight_safety_xp)
from aerocarreira.sim_adapter import SampleReader
from aerocarreira.storage import Storage


def sample(t,ground=True,agl=0,gs=0,ias=0,vs=0,**kwargs):
    return FlightSample(t,-8.12,-34.92,110+agl,agl,ias,gs,vs,ground,**kwargs)


class FlightAuditTests(unittest.TestCase):
    def test_time_near_utc_midnight_is_not_preset_proof(self):
        base=datetime(2026,11,4,0,1,0,tzinfo=timezone.utc)
        self.assertTrue(real_clock_verified(sample(1,zulu_time_s=86370,sim_rate=1),base))
        self.assertFalse(real_clock_verified(sample(1,zulu_time_s=15000,sim_rate=1),base))
        self.assertFalse(real_clock_verified(sample(1,zulu_time_s=60,sim_rate=4),base))
        self.assertIsNone(real_clock_verified(sample(1,zulu_time_s=None,sim_rate=1),base))

    def test_assistance_requires_complete_real_telemetry(self):
        on=sample(1,assistance_takeoff=False,assistance_landing=False,
                  ai_controls=False,unlimited_fuel=False)
        self.assertTrue(assistance_verified(on))
        self.assertFalse(assistance_verified(replace(on,assistance_landing=True)))
        self.assertFalse(assistance_verified(replace(on,unlimited_fuel=True)))
        self.assertIsNone(assistance_verified(replace(on,ai_controls=None)))

    def test_missing_simvars_remain_none(self):
        raw={'PLANE_LATITUDE':-8,'PLANE_LONGITUDE':-34,
             'PLANE_ALTITUDE':100,'PLANE_ALT_ABOVE_GROUND':0,
             'AIRSPEED_INDICATED':0,'SIM_ON_GROUND':1,
             'GROUND_VELOCITY':0,'VERTICAL_SPEED':0}
        s,missing=SampleReader(raw,clock=lambda:1).read()
        self.assertEqual(missing,[])
        self.assertIsNone(s.assistance_landing)
        self.assertIsNone(s.engine_running)
        self.assertIsNone(s.light_beacon)
        self.assertIsNone(s.g_force)
        self.assertIsNone(assistance_verified(s))

    def test_reader_optional_sensors_and_true_bool(self):
        raw={'PLANE_LATITUDE':-8,'PLANE_LONGITUDE':-34,
             'PLANE_ALTITUDE':100,'PLANE_ALT_ABOVE_GROUND':0,
             'AIRSPEED_INDICATED':0,'SIM_ON_GROUND':1,
             'GROUND_VELOCITY':0,'VERTICAL_SPEED':0,
             'ASSISTANCE_LANDING_ENABLED':0,'ASSISTANCE_TAKEOFF_ENABLED':0,
             'AI_CONTROLS':0,'UNLIMITED_FUEL':0,'LIGHT_LANDING':1,
             'NUMBER_OF_ENGINES':1,'GENERAL_ENG_COMBUSTION:1':1,'G_FORCE':1.4,'ZULU_TIME':1000}
        s,_=SampleReader(raw,clock=lambda:1).read()
        self.assertTrue(assistance_verified(s))
        self.assertTrue(s.light_landing)
        self.assertTrue(s.engine_running)
        self.assertEqual(s.g_force,1.4)

    def test_go_around_keeps_flight_and_suppresses_smooth_bonus(self):
        tr=FlightTracker()
        seq=[sample(0),sample(10,False,12,60,60,250),
             sample(20,False,900,80,80,500),
             sample(30,False,500,75,75,-500),
             sample(40,False,200,65,65,-300),
             sample(45,False,460,70,70,500),
             sample(60,False,1000,75,75,600),
             sample(90,False,200,65,65,-300),
             sample(100,False,10,55,55,-100),
             sample(101,True,0,48,48,0),
             sample(104,True,0,5,5,0)]
        events=[]
        for s in seq:events.extend(tr.update(s))
        self.assertEqual(len([e for e in events if e['type']=='go_around']),1)
        self.assertEqual(len([e for e in events if e['type']=='landing']),1)
        self.assertEqual(tr.go_arounds,1)
        self.assertEqual(flight_safety_xp(tr,-100),0)

    def test_smooth_landing_bonus_four_xp_at_final_touchdown(self):
        tr=FlightTracker()
        for s in [sample(0),sample(10,False,20,60,60,300),
                  sample(20,False,100,66,66,-120),
                  sample(21,True,0,44,44,0),sample(24,True,0,10,10,0)]:
            tr.update(s)
        self.assertEqual(tr.phase,Phase.LANDED)
        self.assertEqual(flight_safety_xp(tr,-120),4)
        self.assertEqual(flight_safety_xp(tr,-150),0)
        self.assertEqual(flight_safety_xp(tr,None),0)

    def test_touch_and_go_not_completed_until_final_landing(self):
        tr=FlightTracker()
        samples=[sample(0),sample(10,False,20,70,70,300),
                 sample(20,False,100,70,70,-200),
                 sample(30,False,15,55,55,-125),
                 sample(31,True,0,42,42,0),
                 sample(32.5,True,0,45,45,0),
                 sample(33,False,30,60,60,220),
                 sample(50,False,30,60,60,-120),
                 sample(51,True,0,40,40,0),
                 sample(54,True,0,10,10,0)]
        events=[]
        for s in samples:events.extend(tr.update(s))
        self.assertEqual(tr.touch_and_go,1)
        self.assertEqual([e['type'] for e in events].count('landing'),1)

    def test_taxi_threshold_excludes_takeoff_run(self):
        runway=FlightTracker()
        for s in [sample(0),sample(3,True,0,29,26),sample(15,True,0,37,36),
                  sample(20,False,10,64,64,250)]:
            runway.update(s)
        self.assertEqual(runway.taxi_violations,0)
        taxi=FlightTracker()
        for s in [sample(0),sample(5,True,0,29,21),
                  sample(15,True,0,32,23),sample(18,True,0,2,2),
                  sample(130,False,10,61,61,250)]:
            taxi.update(s)
        self.assertEqual(taxi.taxi_violations,1)

    def test_lights_gforce_stall_and_checkpoint(self):
        tr=FlightTracker()
        seq=[sample(0),
             sample(5,True,0,8,8,0,engine_running=True,light_beacon=True,light_taxi=True),
             sample(10,False,12,60,60,350),
             sample(20,False,900,80,80,400,g_force=1),
             sample(22,False,700,70,70,-200,g_force=2.4,light_landing=True),
             sample(24,False,510,66,66,-200,g_force=2.4,light_landing=True),
             sample(25,False,400,66,66,-150,g_force=1.0,stall_warning=True),
             sample(26,False,300,64,64,-120,g_force=1.0,stall_warning=True),
             sample(27,True,0,40,40,0),
             sample(30,True,0,8,8,0)]
        for s in seq:tr.update(s)
        self.assertEqual(tr.hard_g_events,1)
        self.assertEqual(tr.stalls,1)
        self.assertTrue(tr.light_beacon_taxi_ok)
        self.assertTrue(tr.light_taxi_ok)
        self.assertTrue(tr.light_landing_approach_ok)
        self.assertEqual(flight_safety_xp(tr,-120),2)
        cp=FlightTracker.from_snapshot(tr.snapshot())
        self.assertEqual(cp.hard_g_events,1)
        self.assertTrue(cp.light_taxi_ok)
        self.assertEqual(cp.stalls,1)
        self.assertEqual(FlightTracker.from_snapshot({'phase':'solo'}).go_arounds,0)

    def test_ledger_adds_xp_once_and_does_not_clawback_earlier_flights(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Storage(Path(folder)/'career.db')
            db.create_pilot('Teste','FLY01','SBRF')
            start={'timestamp':100,'lat':-8,'lon':-34}
            end={'timestamp':200,'lat':-8,'lon':-34}
            args=(start,end,-100,0,None,0,{'version':1})
            self.assertTrue(db.finalize_flight(*args,flight_xp_extra=4))
            self.assertFalse(db.finalize_flight(*args,flight_xp_extra=4))
            row=db.conn.execute("SELECT xp FROM pilot_xp_ledger").fetchone()
            self.assertEqual(row[0],29)
            other={'timestamp':300,'lat':-8,'lon':-34}
            db.finalize_flight(other,end,-400,1,None,0,{'version':1},flight_xp_extra=-5)
            self.assertEqual(db.conn.execute("SELECT SUM(xp) FROM pilot_xp_ledger").fetchone()[0],49)
            db.close()

if __name__=='__main__':
    unittest.main()
