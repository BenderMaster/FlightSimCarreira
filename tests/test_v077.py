"""v0.7.7: persistência do combustível, manifes­tos, peso/MTOW, navdata e XP."""
import ctypes
import json
import math
import struct
import tempfile
import unittest
from pathlib import Path

from aerocarreira.storage import Storage
from aerocarreira.fuel import FuelManager
from aerocarreira.manifest import mission_manifest
from aerocarreira.msfs_navdata import remember_airport,stored_airport,overlay_mission,overlay_catalog
from aerocarreira.sim_facilities import FacilityDataPacket,decode_airport_packet,FACILITY_RECV_ID
from aerocarreira.payload import load_plan,load_confirmed
from aerocarreira.contracts import AirportCatalog
from aerocarreira.domain import Mission,FlightSample,AIRPORTS


class V077Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'pilot.db'
        self.db=Storage(self.path)
        self.db.create_pilot('Piloto','QA777','SBRF')
        self.db.claim_starter()
        self.ref='legacy:c152'
        self.now=1000.
        self.fuel=FuelManager(self.db,clock=lambda:self.now)
        self.caps={'LEFT_MAIN':13.,'RIGHT_MAIN':13.}
        self.level={'LEFT_MAIN':8.,'RIGHT_MAIN':8.}

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def test_restart_restores_paid_fuel_instead_of_consuming_days(self):
        self.assertEqual(self.fuel.observe(self.ref,'c152',self.level,16,True,self.caps)[0],'calibrated')
        self.fuel.change_liters(self.ref,80.)
        self.db.close()
        self.db=Storage(self.path)
        new=FuelManager(self.db,clock=lambda:self.now+86400*3)
        status,correction=new.observe(self.ref,'c152',self.level,16,True,self.caps)
        self.assertEqual(status,'restore')
        self.assertAlmostEqual(sum(correction.values())*3.785411784,80.,places=1)
        self.assertAlmostEqual(sum(new.get(self.ref)['tanks'].values())*3.785411784,80.,places=1)

    def test_fuel_return_only_purchased_not_free_initial(self):
        self.fuel.observe(self.ref,'c152',self.level,16,True,self.caps)
        old=int(self.db.get_setting('balance'))
        bought=self.fuel.change_liters(self.ref,85.)
        self.assertGreater(bought['cost_brl'],0)
        self.assertTrue(self.fuel.confirm_pending(self.ref))
        returned=self.fuel.change_liters(self.ref,40.)
        self.assertGreater(returned['refund_brl'],0)
        self.assertTrue(self.fuel.confirm_pending(self.ref))
        self.assertLessEqual(int(self.db.get_setting('balance')),old)
        self.assertLessEqual(returned['refund_brl'],bought['cost_brl'])
        # Sem compra rastreada, a própria carga inicial não gera dinheiro.
        free_return=self.fuel.change_liters(self.ref,0.)
        self.assertEqual(free_return['refund_brl'],0)
        with self.assertRaises(ValueError):self.fuel.change_liters(self.ref,-20)

    def test_failed_fuel_write_rolls_back_without_double_payment(self):
        self.fuel.observe(self.ref,'c152',self.level,16,True,self.caps)
        balance=int(self.db.get_setting('balance'))
        previous=self.fuel.get(self.ref)['tanks']
        result=self.fuel.change_liters(self.ref,85.)
        self.assertTrue(self.fuel.pending(self.ref))
        with self.assertRaises(ValueError):self.fuel.change_liters(self.ref,55.)
        restored=self.fuel.rollback_pending(self.ref)
        self.assertEqual(restored,previous)
        self.assertEqual(self.db.get_setting('balance'),str(balance))
        self.assertIsNone(self.fuel.rollback_pending(self.ref))
        self.assertIsNone(self.fuel.pending(self.ref))
        self.assertEqual(self.fuel.get(self.ref)['tanks'],previous)

    def test_two_aircraft_fuel_inventories_are_isolated(self):
        self.fuel.observe(self.ref,'c152',self.level,16,True,self.caps)
        self.db.set_setting('balance','1000000')
        other=self.db.fleet_manager().purchase('c172','SBRF')
        c172={'LEFT_MAIN':20.,'RIGHT_MAIN':20.}
        self.fuel.observe(other['ref'],'c172',c172,40,True,
            {'LEFT_MAIN':26.5,'RIGHT_MAIN':26.5})
        self.fuel.change_liters(self.ref,10.)
        self.assertEqual(sum(self.fuel.get(other['ref'])['tanks'].values()),40)
        self.db.close();self.db=Storage(self.path)
        self.assertEqual(self.db.fleet_manager().get(other['ref'])['condition'],100)
        self.assertEqual(sum(FuelManager(self.db).get(other['ref'])['tanks'].values()),40)

    def test_manifest_is_stable_and_human_readable(self):
        for kind in ('cargo','tourism','passenger','humanitarian','medical'):
            mission=Mission('REG-SBRF-1-'+kind,'SBRF','SBJP','Genérico',1800,category=kind)
            first=mission_manifest(mission)
            self.assertEqual(first,mission_manifest(mission))
            self.assertGreater(first.payload_kg,0)
            self.assertTrue(first.manifest_label)
            self.assertNotIn('Genérico',first.title)
            self.assertTrue(first.title.find('—')>=0)
            if kind in ('tourism','passenger'):self.assertEqual(first.passenger_count,1)
        self.assertEqual(mission_manifest(first),first)

    def test_payload_with_two_stations_and_max_weight(self):
        mission=Mission('A','SBRF','SBJP','Voo turístico',1000,payload_kg=74,
                        manifest_label='Flávia Martins',manifest_kind='passenger',passenger_count=1)
        s=FlightSample(1,-8,-34,100,0,0,0,0,True,
                       total_weight_lbs=1370,max_gross_weight_lbs=1670,
                       payload_station_count=2,payload_station_weights={1:160.,2:0.})
        prepared=load_plan(s,mission)
        self.assertEqual(set(prepared['stations']),{2})
        self.assertTrue(load_confirmed({2:prepared['stations'][2]},prepared['stations']))
        self.assertTrue(load_confirmed({'2':prepared['stations'][2]},prepared['stations']))
        self.assertFalse(load_confirmed({2:0.},prepared['stations']))
        with self.assertRaisesRegex(ValueError,'Excesso de peso'):
            load_plan(s.__class__(**{**s.__dict__,'total_weight_lbs':1600}),mission)
        with self.assertRaisesRegex(ValueError,'estações'):
            load_plan(s.__class__(**{**s.__dict__,'payload_station_weights':None}),mission)

    def test_msfs_airport_override_must_be_from_sdk(self):
        m=Mission('A','SBRF','SBJP','Carga',1800,origin_lat=-8.0,
                  origin_lon=-34.9,destination_lat=-7.0,destination_lon=-34.0)
        remember_airport(self.db,'SBRF',-8.1266,-34.922)
        single=overlay_mission(m,self.db)
        self.assertEqual(single.nav_source,'MISTO')
        remember_airport(self.db,'SBJP',-7.148,-34.95)
        resolved=overlay_mission(m,self.db)
        self.assertEqual(resolved.nav_source,'MSFS')
        self.assertAlmostEqual(resolved.destination_lon,-34.95)
        self.assertEqual(resolved.reward,m.reward)
        catalog=AirportCatalog(locations=AIRPORTS)
        overlay_catalog(catalog,self.db)
        self.assertAlmostEqual(catalog.locations['SBRF'].latitude,-8.1266)
        self.assertIsNone(stored_airport(self.db,'SNUW'))
        with self.assertRaises(ValueError):remember_airport(self.db,'SBJP',200,0)

    def test_facility_packet_is_validated_before_trusting_coordinates(self):
        raw=ctypes.create_string_buffer(80)
        item=ctypes.cast(raw,ctypes.POINTER(FacilityDataPacket)).contents
        item.dwSize=60;item.dwID=FACILITY_RECV_ID;item.UserRequestId=5012
        raw_values=struct.pack('<dd',-7.147,-34.95)
        ctypes.memmove(ctypes.addressof(raw)+FacilityDataPacket.Data.offset,
                       raw_values,16)
        out=decode_airport_packet(ctypes.cast(raw,ctypes.c_void_p),60,{5012:'SBJP'})
        self.assertEqual(out['icao'],'SBJP')
        self.assertAlmostEqual(out['lon'],-34.95)
        self.assertIsNone(decode_airport_packet(ctypes.cast(raw,ctypes.c_void_p),20,{5012:'SBJP'}))
        self.assertIsNone(decode_airport_packet(ctypes.cast(raw,ctypes.c_void_p),60,{}))

    def test_weight_bonus_awarded_once_and_preserves_history(self):
        start={'timestamp':300,'lat':-8,'lon':-34}
        end={'timestamp':600,'lat':-7,'lon':-35}
        params=(start,end,-120,0,'REG-W',1500,{'career':{},'tracker':{}})
        self.assertTrue(self.db.finalize_flight(*params,flight_xp_weight_bonus=5))
        self.assertFalse(self.db.finalize_flight(*params,flight_xp_weight_bonus=5))
        xp=self.db.conn.execute('SELECT xp FROM pilot_xp_ledger').fetchone()[0]
        self.assertEqual(xp,45)
        with self.assertRaises(ValueError):
            self.db.finalize_flight(start,{'timestamp':601,'lat':-7,'lon':-35},
                -100,0,None,0,{},flight_xp_weight_bonus=7)


if __name__=='__main__':unittest.main()
