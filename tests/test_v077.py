"""Regressões v0.7.7: inventário offline, devolução, manifestos e payload."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from aerocarreira.storage import Storage
from aerocarreira.fuel import FuelManager, LITERS_PER_GALLON
from aerocarreira.domain import FlightSample, Mission
from aerocarreira.contracts import mission_manifest, AIRPORTS, AirportCatalog, generate_offers
from aerocarreira.payload import choose_station, assess_payload, KG_TO_LBS
from aerocarreira.planning import Preflight, inspect_preflight
from aerocarreira.sim_adapter import SampleReader

def sample(**kwargs):
    default=dict(timestamp=10,latitude=-8.126,longitude=-34.923,altitude_ft=100,
        agl_ft=0,ias_kt=0,groundspeed_kt=0,vs_fpm=0,on_ground=True,
        aircraft_title='Cessna 152',total_weight_lbs=1250,
        max_gross_weight_lbs=1670,payload_station_count=2,
        payload_station_weights={'1':170.0,'2':0.0})
    default.update(kwargs)
    return FlightSample(**default)

class V077Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'save.db'
        self.db=Storage(self.path)
        self.db.create_pilot('Teste','QA777','SBRF')
        self.db.claim_starter()
        self.db.set_setting('balance','20000')
        self.now=1000.0
        self.fuel=FuelManager(self.db,clock=lambda:self.now)
        self.caps={'LEFT_MAIN':13.0,'RIGHT_MAIN':13.0}
        self.initial={'LEFT_MAIN':8.0,'RIGHT_MAIN':8.0}
        self.fuel.observe('legacy:c152','c152',self.initial,16,True,self.caps)

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def test_inventory_saved_after_restart_day_later(self):
        self.fuel.set_target_liters('legacy:c152',20*LITERS_PER_GALLON)
        self.assertAlmostEqual(sum(self.fuel.get('legacy:c152')['tanks'].values()),20)
        # MSFS reiniciou dias depois com 10 gal. NÃO confundir com consumo.
        next_day=FuelManager(self.db,clock=lambda:self.now+86400*4)
        status,correction=next_day.observe('legacy:c152','c152',
            {'LEFT_MAIN':5,'RIGHT_MAIN':5},10,True,self.caps)
        self.assertEqual(status,'restore')
        self.assertAlmostEqual(sum(correction.values()),20)
        self.assertAlmostEqual(sum(next_day.get('legacy:c152')['tanks'].values()),20)

    def test_paid_fuel_refund_exact_once_and_not_initial_fuel(self):
        ref='legacy:c152'
        start=int(self.db.get_setting('balance'))
        added=self.fuel.set_target_liters(ref,20*LITERS_PER_GALLON)
        self.assertGreater(added['cost_brl'],0)
        after_purchase=int(self.db.get_setting('balance'))
        self.assertLess(after_purchase,start)
        returned=self.fuel.set_target_liters(ref,17*LITERS_PER_GALLON)
        self.assertGreater(returned['refund_brl'],0)
        self.assertEqual(returned['refund_brl'],round(3*LITERS_PER_GALLON*7))
        self.assertEqual(int(self.db.get_setting('balance')),after_purchase+returned['refund_brl'])
        # Tanque inicial (16 gal) era calibrado, não pago.
        drained=self.fuel.set_target_liters(ref,0)
        self.assertEqual(drained['refund_brl'],round(1*LITERS_PER_GALLON*7))
        self.assertGreater(drained['non_refundable_liters'],0)
        with self.assertRaises(ValueError):
            self.fuel.set_target_liters(ref,-1)
        with self.assertRaises(ValueError):
            self.fuel.set_target_liters(ref,999999)
        self.assertLessEqual(int(self.db.get_setting('balance')),start)

    def test_legacy_paid_liters_can_be_refunded_but_not_exceeded(self):
        with self.db.conn:
            self.db._money_movement('legacy-refuel','abastecimento',-106,
                'Abastecimento 4.0 gal — legacy:c152')
        returned=self.fuel.set_target_liters('legacy:c152',12*LITERS_PER_GALLON)
        self.assertEqual(returned['refund_brl'],round(4*LITERS_PER_GALLON*7))
        self.assertAlmostEqual(self.fuel.refundable_liters('legacy:c152'),0,places=2)
        drained=self.fuel.set_target_liters('legacy:c152',0)
        self.assertEqual(drained['refund_brl'],0)

    def test_fleet_independence_for_fuel_and_wear(self):
        first=self.fuel.get('legacy:c152')
        with self.db.conn:
            self.db.conn.execute("""INSERT INTO fleet_fuel
                (aircraft_ref,model,tanks_json,caps_json,updated_utc)
                VALUES('unit:777','c152','{"LEFT_MAIN":2,"RIGHT_MAIN":2}',
                       '{"LEFT_MAIN":13,"RIGHT_MAIN":13}',1000)""")
        self.fuel.set_target_liters('legacy:c152',18*LITERS_PER_GALLON)
        self.assertAlmostEqual(sum(self.fuel.get('unit:777')['tanks'].values()),4)
        self.assertAlmostEqual(sum(self.fuel.get('legacy:c152')['tanks'].values()),18)

    def test_realistic_manifest_is_deterministic_and_saved(self):
        one=mission_manifest('cargo','REG-SBRF-33-01')
        two=mission_manifest('cargo','REG-SBRF-33-01')
        self.assertEqual(one,two)
        self.assertGreater(one[1],0)
        pilot={'xp':10000,'hours':90}
        from aerocarreira.domain import AIRPORTS
        cat=AirportCatalog()
        offers=generate_offers(AIRPORTS['SBRF'],cat,pilot,{'PPA','PCA','IFR','MLTE','PLA'},{},21342)
        self.assertTrue(offers)
        self.assertTrue(all(o.manifest and o.payload_kg>0 for o in offers))
        self.db.save_offers('SBRF',offers,now=1000,valid_s=3600)
        saved=self.db.active_offers('SBRF',1001)
        self.assertEqual({x.id:(x.manifest,x.payload_kg) for x in saved},
                         {x.id:(x.manifest,x.payload_kg) for x in offers})

    def test_empty_payload_station_and_mtow_checks(self):
        m=Mission('P','SBRF','SBJP','Carga',1500,category='cargo',
                  manifest='Engradado de vinhos',payload_kg=42)
        self.assertEqual(choose_station({'1':170,'2':0},2),2)
        self.assertIsNone(choose_station({'1':170,'2':80},2))
        result=assess_payload(m,sample(),'c152')
        self.assertEqual(result['station'],2)
        self.assertAlmostEqual(result['weight_lbs'],42*KG_TO_LBS,places=2)
        with self.assertRaises(ValueError):
            assess_payload(m,sample(total_weight_lbs=1600),'c152')
        with self.assertRaises(ValueError):
            assess_payload(m,sample(payload_station_weights={'1':175,'2':75}),'c152')
        with self.assertRaises(ValueError):
            assess_payload(m,sample(aircraft_title='Cessna 172 Skyhawk'),'c152')

    def test_simconnect_reads_payload_station_without_required_failure(self):
        raw=dict(PLANE_LATITUDE=-8.1,PLANE_LONGITUDE=-34.9,
                 PLANE_ALTITUDE=100,PLANE_ALT_ABOVE_GROUND=0,
                 AIRSPEED_INDICATED=0,SIM_ON_GROUND=1,
                 GROUND_VELOCITY=0,VERTICAL_SPEED=0,
                 PAYLOAD_STATION_COUNT=2)
        raw['PAYLOAD_STATION_WEIGHT:1']=175
        raw['PAYLOAD_STATION_WEIGHT:2']=0
        reading,missing=SampleReader(raw,clock=lambda:10).read()
        self.assertFalse(missing)
        self.assertEqual(reading.payload_station_count,2)
        self.assertEqual(reading.payload_station_weights['2'],0)

    def test_weight_bonus_only_after_verified_safe_loading(self):
        m=Mission('P','SBRF','SBJP','Carga',1500,category='cargo',payload_kg=42)
        p=Preflight(m.id,'Cessna 152',planned_weight_lbs=1450,
                    max_weight_lbs=1670,payload_checked=True)
        self.assertFalse(inspect_preflight(m,p)['weight_ok'])
        verified=inspect_preflight(m,p,verified={'payload':True})
        self.assertTrue(verified['weight_ok'])
        self.assertAlmostEqual(verified['bonus_fraction'],.025)
        self.assertFalse(inspect_preflight(m,replace(p,planned_weight_lbs=1800),verified={'payload':True})['weight_ok'])

if __name__=='__main__':
    unittest.main()
