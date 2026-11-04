"""Regressões v0.7.7: inventário persistente, manifesto, navdata e segurança."""
import json
import math
import struct
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from aerocarreira.contracts import AirportCatalog, generate_offers
from aerocarreira.domain import Airport, FlightSample, Mission
from aerocarreira.fuel import FuelManager
from aerocarreira.manifest import assign_manifest, payload_limits
from aerocarreira.navdata import resolve_mission_navdata, official_route_ready
from aerocarreira.sim_adapter import SampleReader
from aerocarreira.sim_facilities import decode_airport_packet
from aerocarreira.storage import Storage
from aerocarreira.planning import Preflight, inspect_preflight


class TestV077(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Storage(Path(self.tmp.name)/'pilot.db')
        self.db.create_pilot('Piloto de Teste','FL-77','SBRF')
        self.db.claim_starter()
        self.db.fleet_manager().select('legacy:c152')
        self.caps={'LEFT_MAIN':13.0,'RIGHT_MAIN':13.0}
        self.tanks={'LEFT_MAIN':8.0,'RIGHT_MAIN':8.0}
        self.clock=[1000.0]
        self.manager=FuelManager(self.db,clock=lambda:self.clock[0])
    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def observe(self,fuel=None):
        tanks=fuel if fuel is not None else self.tanks
        return self.manager.observe('legacy:c152','c152',tanks,sum(tanks.values()),
                    True,self.caps,True)

    def test_first_session_next_day_restores_saved_fuel(self):
        self.assertEqual(self.observe()[0],'calibrated')
        self.clock[0]+=2000
        low={'LEFT_MAIN':7.8,'RIGHT_MAIN':7.8}
        self.assertEqual(self.observe(low)[0],'consuming')
        self.clock[0]+=86400*4
        next_launch=FuelManager(self.db,clock=lambda:self.clock[0])
        status,expected=next_launch.observe('legacy:c152','c152',
                            {'LEFT_MAIN':1,'RIGHT_MAIN':1},2,True,self.caps,True)
        self.assertEqual(status,'restore')
        self.assertAlmostEqual(expected['LEFT_MAIN'],7.8)
        self.assertAlmostEqual(next_launch.get('legacy:c152')['tanks']['LEFT_MAIN'],7.8)

    def test_refuel_partial_and_only_paid_liters_refund(self):
        self.observe()
        self.assertEqual(self.manager.refundable_liters('legacy:c152'),0.0)
        full=self.manager.set_target_liters('legacy:c152',20.0*3.785411784)
        self.assertGreater(full['cost_brl'],0)
        self.assertAlmostEqual(full['refundable_liters'],4*3.785411784,places=2)
        self.assertLess(int(self.db.get_setting('balance')),5000)
        refund=self.manager.set_target_liters('legacy:c152',15.0*3.785411784)
        self.assertGreater(refund['refund_brl'],0)
        self.assertEqual(refund['target_gallons'],15.0)
        self.assertAlmostEqual(refund['refundable_liters'],0.0)
        cannot_profit=self.manager.set_target_liters('legacy:c152',10.0*3.785411784)
        self.assertEqual(cannot_profit['refund_brl'],0)
        self.assertEqual(cannot_profit['refundable_liters'],0)
        self.assertAlmostEqual(sum(self.manager.get('legacy:c152')['tanks'].values()),10.0,places=3)

    def test_reducing_fuel_consumes_refund_credit(self):
        self.observe()
        self.manager.set_target_liters('legacy:c152',24*3.785411784)
        self.manager.last_seen['legacy:c152']=self.clock[0]
        self.clock[0]+=5000
        self.manager.observe({'LEFT_MAIN':11.5,'RIGHT_MAIN':11.5})
        self.assertLess(self.manager.refundable_liters('legacy:c152'),8*3.785411784)

    def test_no_overcapacity_no_fuel_without_enough_balance(self):
        self.observe()
        with self.assertRaises(ValueError):
            self.manager.set_target_liters('legacy:c152',10000)
        with self.assertRaises(ValueError):
            self.manager.set_target_liters('legacy:c152',float('nan'))
        self.db.set_setting('balance','0')
        with self.assertRaises(ValueError):
            self.manager.set_target_liters('legacy:c152',26*3.785411784)
        self.assertAlmostEqual(sum(self.manager.get('legacy:c152')['tanks'].values()),16)

    def test_manifest_deterministic_fictional_and_persistent(self):
        m=Mission('REG-SBRF-10-01','SBRF','SBJP','Carga leve',1000,category='cargo')
        a,b=assign_manifest(m),assign_manifest(m)
        self.assertEqual(a,b)
        self.assertGreater(a.payload_kg,0)
        self.assertTrue(a.manifest_description)
        self.assertIn(a.manifest_description,a.title)
        restored=Mission(**json.loads(json.dumps(a.__dict__)))
        self.assertEqual(restored,a)
        passenger=assign_manifest(replace(m,id='REG-SBRF-10-02',category='tourism'))
        self.assertEqual(passenger.payload_kind,'passageiro')
        self.assertIn('Voo turístico',passenger.title)

    def test_all_generated_offers_have_manifests(self):
        origin=Airport('SBRF','Recife',-8.126,-34.922)
        aps={'SBRF':origin,'SBJP':Airport('SBJP','João Pessoa',-7.15,-34.95),
             'SBMO':Airport('SBMO','Maceió',-9.51,-35.8)}
        c=AirportCatalog(aps)
        offers=generate_offers(origin,c,{'level':2,'xp':100,'hours':2},{'PPA'},
                               {'single':3,'c152':3},24500)
        self.assertTrue(offers)
        self.assertTrue(all(m.payload_kg>0 and m.manifest_description for m in offers))

    def sample(self,**kwargs):
        return FlightSample(timestamp=1000,latitude=-8,longitude=-34,altitude_ft=100,
          agl_ft=0,ias_kt=0,groundspeed_kt=0,vs_fpm=0,on_ground=True,
          aircraft_title='Cessna 152',payload_station_count=2,
          payload_station_2_lbs=0,total_weight_lbs=1430,max_gross_weight_lbs=1670,
          **kwargs)

    def test_payload_weight_validated_against_mtow(self):
        mission=assign_manifest(Mission('PAY-1','SBRF','SBJP','Passeio',2000,category='tourism'))
        ok=payload_limits(self.sample(),mission)
        self.assertGreater(ok['target_lbs'],0)
        self.assertLessEqual(ok['projected_lbs'],ok['max_lbs'])
        with self.assertRaises(ValueError):
            payload_limits(replace(self.sample(),total_weight_lbs=1670),mission)
        with self.assertRaises(ValueError):
            payload_limits(replace(self.sample(),on_ground=False),mission)
        with self.assertRaises(ValueError):
            payload_limits(replace(self.sample(),payload_station_count=None),mission)

    def test_reader_payload_optional_never_invents(self):
        raw={'PLANE_LATITUDE':-8,'PLANE_LONGITUDE':-34,'PLANE_ALTITUDE':100,
             'PLANE_ALT_ABOVE_GROUND':0,'AIRSPEED_INDICATED':0,
             'SIM_ON_GROUND':1,'GROUND_VELOCITY':0,'VERTICAL_SPEED':0}
        reading,_=SampleReader(raw,clock=lambda:1000).read()
        self.assertIsNone(reading.payload_station_count)
        self.assertIsNone(reading.payload_station_2_lbs)
        raw.update({'PAYLOAD_STATION_COUNT':2,'PAYLOAD_STATION_WEIGHT:2':84.7})
        reading,_=SampleReader(raw,clock=lambda:1001).read()
        self.assertEqual(reading.payload_station_count,2)
        self.assertAlmostEqual(reading.payload_station_2_lbs,84.7)

    def test_weight_bonus_only_verified_on_both_money_and_xp(self):
        m=Mission('V077','SBRF','SBJP','Carga',2000,category='cargo')
        p=Preflight('V077','Cessna 152',payload_checked=True,
                    planned_weight_lbs=1300,max_weight_lbs=1670)
        report=inspect_preflight(m,p)
        self.assertEqual(report['bonus_fraction'],0)
        self.assertFalse(report['weight_ok'])
        result=inspect_preflight(m,p,verified={'weight':True})
        self.assertAlmostEqual(result['bonus_fraction'],.025)
        self.assertTrue(result['weight_ok'])

    def test_airport_packet_uses_msfs2020_packed_33_byte_layout(self):
        airport=lambda name,lat,lon:(name.encode().ljust(6,b'\0')+b'BR\0'+
                                  struct.pack('<ddd',lat,lon,0.0))
        body=airport('SNUW',-8.10,-35.12)+airport('SBGR',-23.43,-46.47)
        packet=struct.pack('<7I',28+len(body),0,18,42,2,0,1)+body
        head,rows=decode_airport_packet(packet)
        self.assertEqual(head['request_id'],42)
        self.assertEqual(rows,[('SNUW',-8.1,-35.12)])
        with self.assertRaises(ValueError):
            decode_airport_packet(packet[:-4])

    def test_sim_airports_override_fallback_and_route_resolves(self):
        fallback={'SBRF':Airport('SBRF','Recife',-8.12,-34.92),
                  'SNUW':Airport('SNUW','Sertânia',-7.1,-34.8)}
        c=AirportCatalog(fallback)
        m=Mission('TEST','SBRF','SNUW','Carga',1000,origin_lat=-8.12,origin_lon=-34.92,
                  destination_lat=-7.1,destination_lon=-34.8)
        self.assertFalse(official_route_ready(m,c))
        self.assertEqual(c.merge_msfs_airports([('SNUW',-8.22,-37.33),('SBRF',-8.126,-34.923)]),2)
        self.assertTrue(official_route_ready(m,c))
        resolved=resolve_mission_navdata(m,c)
        self.assertAlmostEqual(resolved.destination_lon,-37.33)
        self.assertAlmostEqual(c.locations['SNUW'].longitude,-37.33)

if __name__=='__main__':unittest.main()
