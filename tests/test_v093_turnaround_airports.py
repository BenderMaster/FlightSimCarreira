"""v0.9.3: verified parking, delayed payout, native airport details and map."""
import struct
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

from aerocarreira.domain import FlightSample, Career, Mission
from aerocarreira.app import Application
from aerocarreira.sim_adapter import SampleReader
from aerocarreira.turnaround import TurnaroundGate, parking_status
from aerocarreira.airport_facilities import (DetailCollector, parse_facility_packet,
    parse_facility_end, DATA_ID, DATA_END_ID, AIRPORT, RUNWAY, PARKING,
    APPROACH_LIGHTS, VASI)


def sample(t=1,**kwargs):
    values=dict(timestamp=t,latitude=-8.126,longitude=-34.918,
        altitude_ft=36,agl_ft=0,ias_kt=0,groundspeed_kt=0.0,
        vs_fpm=0.0,on_ground=True,engine_running=False,
        on_any_runway=False,atc_on_parking_spot=True,
        plane_in_parking_state=True,parking_brake_set=True,
        groundspeed_estimated=False,aircraft_title='Cessna 152')
    values.update(kwargs)
    return FlightSample(**values)


class ParkingTests(unittest.TestCase):
    def test_acceptance_requires_real_stand_not_runway(self):
        ok,_=parking_status(sample(engine_running=True))
        self.assertTrue(ok)
        for change in ({'on_any_runway':True},{'on_any_runway':None},
                       {'atc_on_parking_spot':False,'plane_in_parking_state':False},
                       {'groundspeed_estimated':True},{'groundspeed_kt':9.0},
                       {'parking_brake_set':False},{'parking_brake_set':None},
                       {'on_ground':False}):
            with self.subTest(change=change):
                allowed,_=parking_status(sample(**change))
                self.assertFalse(allowed)

    def test_shutdown_requires_all_engines_and_six_seconds(self):
        gate=TurnaroundGate()
        e={'type':'landing','timestamp':10,'lat':-8.126,'lon':-34.918,'touchdown_fpm_est':-170}
        gate.begin(e,sample(10),'REG-ABC')
        self.assertFalse(gate.observe(sample(12,engine_running=True),'REG-ABC'))
        self.assertFalse(gate.observe(sample(13),'REG-ABC'))
        self.assertFalse(gate.observe(sample(17),'REG-ABC'))  # stale gap resets
        self.assertFalse(gate.observe(sample(18),'REG-ABC'))
        self.assertFalse(gate.observe(sample(23),'REG-ABC'))  # gap>4, reset again
        self.assertFalse(gate.observe(sample(24),'REG-ABC'))
        self.assertFalse(gate.observe(sample(27),'REG-ABC'))
        self.assertTrue(gate.observe(sample(30),'REG-ABC'))
        self.assertEqual(gate.pending['mission_id'],'REG-ABC')

    def test_restored_gate_restarts_hold_and_rejects_wrong_aircraft(self):
        g=TurnaroundGate()
        e={'type':'landing','timestamp':10,'lat':-8.126,'lon':-34.918}
        g.begin(e,sample(10),'REG-A')
        g.observe(sample(12),'REG-A')
        restored=TurnaroundGate.restore(g.snapshot())
        self.assertIsNone(restored.since)
        self.assertFalse(restored.observe(sample(14,aircraft_title='Baron G58'),'REG-A'))
        self.assertFalse(restored.observe(sample(15),'REG-OTHER'))
        self.assertFalse(restored.observe(sample(16),'REG-A'))

    def test_multiengine_requires_all_sensors(self):
        raw=dict(PLANE_LATITUDE=-8.12,PLANE_LONGITUDE=-34.92,PLANE_ALTITUDE=40,
                 PLANE_ALT_ABOVE_GROUND=0,AIRSPEED_INDICATED=0,SIM_ON_GROUND=1,
                 GROUND_VELOCITY=0,VERTICAL_SPEED=0,NUMBER_OF_ENGINES=2,
                 **{'GENERAL_ENG_COMBUSTION:1':0,'GENERAL_ENG_COMBUSTION:2':1})
        reader=SampleReader(raw,clock=lambda:10)
        s,_=reader.read()
        self.assertTrue(s.engine_running)
        raw['GENERAL_ENG_COMBUSTION:2']=0
        s,_=reader.read()
        self.assertFalse(s.engine_running)
        del raw['GENERAL_ENG_COMBUSTION:2']
        s,_=reader.read()
        self.assertIsNone(s.engine_running)
        self.assertFalse(parking_status(replace(sample(),engine_running=None),shutdown=True)[0])

    def test_career_preview_does_not_pay_or_clear_contract(self):
        m=Mission(id='REG-TEST',origin='SBRF',destination='SIPE',
                  title='Frete',reward=1200)
        # Mission's optional coords avoid depending on global fake airports.
        m=replace(m,origin_lat=-8.126,origin_lon=-34.918,
                  destination_lat=-8.126,destination_lon=-34.918)
        career=Career(balance=5000)
        career.mission=m
        career.origin_confirmed=True
        event={'type':'landing','timestamp':15,'lat':-8.126,'lon':-34.918}
        preview=career.evaluate([event],'Cessna 152',settle=False)
        self.assertEqual(preview['reward'],1200)
        self.assertEqual(career.balance,5000)
        self.assertEqual(career.mission,m)
        settlement=career.evaluate([event],'Cessna 152')
        self.assertEqual(settlement['reward'],1200)
        self.assertEqual(career.balance,6200)
        self.assertIsNone(career.mission)

    def test_app_pending_payment_requires_destination_and_shutdown(self):
        m=Mission(id='REG-TEST',origin='SBRF',destination='SIPE',
                  title='Frete',reward=900,
                  origin_lat=-8.126,origin_lon=-34.918,
                  destination_lat=-8.126,destination_lon=-34.918)
        app=object.__new__(Application)
        app.career=Career(balance=3000)
        app.career.mission=m
        app.career.origin_confirmed=True
        app.mode='MSFS';app.connected=True
        app._log=Mock();app._finalize_landing=Mock()
        app.turnaround=TurnaroundGate()
        event={'type':'landing','timestamp':10,'lat':-8.126,'lon':-34.918,
               'touchdown_fpm_est':-155}
        app.turnaround.begin(event,sample(10),'REG-TEST')
        for ts in [11,12,13,14]:
            app._complete_pending_turnaround(sample(ts,engine_running=True))
        self.assertEqual(app.career.balance,3000)
        self.assertFalse(app._finalize_landing.called)
        for ts in [15,17,19,21]:
            app._complete_pending_turnaround(sample(ts))
        self.assertEqual(app.career.balance,3900)
        app._finalize_landing.assert_called_once()
        end=app._finalize_landing.call_args.args[1]
        self.assertEqual(end['timestamp'],21)
        self.assertEqual(end['touchdown_fpm_est'],-155)


def packet(kind,uid,parent,value,req=6201):
    body=value
    size=40+len(body)
    return struct.pack('<7I',size,0,DATA_ID,req,uid,parent,kind)+b'\x01\x00\x00\x00'+struct.pack('<2I',0,1)+body


class FacilityTests(unittest.TestCase):
    def test_native_packet_and_details_summary(self):
        col=DetailCollector('SBRF')
        values=[
            packet(AIRPORT,1,0,struct.pack('<2i',2,3)),
            packet(RUNWAY,2,1,b'IFRF\x00\x00\x00\x00'+b'\x00'*8),
            packet(RUNWAY,3,1,b'\x00'*16),
            packet(PARKING,4,1,struct.pack('<i',1)),
            packet(PARKING,5,1,struct.pack('<i',12)),
            packet(PARKING,6,1,struct.pack('<i',8)),
            packet(VASI,7,2,struct.pack('<i',8)),
            packet(APPROACH_LIGHTS,8,2,struct.pack('<i',3))
        ]
        for value in values:
            col.feed(value,6201)
        result=col.finish()
        self.assertEqual(result['runways'],2)
        self.assertEqual(result['parkings'],3)
        self.assertTrue(result['ils'])
        self.assertTrue(result['papi'])
        self.assertTrue(result['approach_lights'])
        self.assertTrue(result['fuel_spot'])
        self.assertIsNone(result['fuel_service'])

    def test_unknown_never_becomes_no(self):
        col=DetailCollector('SIPE')
        col.feed(packet(AIRPORT,1,0,struct.pack('<2i',1,2)),6201)
        result=col.finish()
        self.assertIsNone(result['ils'])
        self.assertIsNone(result['fuel_spot'])
        self.assertIsNone(result['papi'])
        self.assertIsNone(result['approach_lights'])

    def test_rejects_wrong_packet_instead_of_trusting_arbitrary_values(self):
        good=packet(PARKING,2,1,struct.pack('<i',12))
        with self.assertRaises(ValueError):parse_facility_packet(good,9999)
        with self.assertRaises(ValueError):parse_facility_packet(good[:15],6201)
        with self.assertRaises(ValueError):parse_facility_packet(good[:-1],6201)
        end=struct.pack('<4I',16,0,DATA_END_ID,6201)
        self.assertTrue(parse_facility_end(end,6201))
        with self.assertRaises(ValueError):parse_facility_end(end,6202)


if __name__=='__main__':unittest.main()
