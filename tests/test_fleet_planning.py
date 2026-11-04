"""Bloco 5: aeronaves instaladas, frota única, oferta usada, despacho e bônus."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from aerocarreira.aircraft_catalog import (packages_root_from_cfg,
    detect_package_roots, scan_installed_aircraft)
from aerocarreira.finance import AIRCRAFT_ECONOMY
from aerocarreira.fleet import used_market, resale_price
from aerocarreira.domain import AIRPORTS, MISSIONS
from aerocarreira.planning import Preflight, inspect_preflight, aircraft_title_matches
from aerocarreira.storage import Storage


class CatalogTests(unittest.TestCase):
    def test_parse_steam_config_and_addon_livery_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'MSFS Packages'
            mod=root/'Community'/'my-aircraft'/'SimObjects'/'Airplanes'/'CustomPlane'
            mod.mkdir(parents=True)
            config=mod/'aircraft.cfg'
            config.write_text('''[FLTSIM.0]\ntitle=My Plane Blue\nui_manufacturer=TestCo\nui_type=Single\ntexture=blue\n[FLTSIM.1]\ntitle=My Plane Red\ntexture=red\n''')
            opt=Path(temp)/'UserCfg.opt'
            opt.write_text(f'InstalledPackagesPath "{root}"\n')
            self.assertEqual(packages_root_from_cfg(opt),root)
            found=scan_installed_aircraft([root])
            self.assertEqual(len(found),2)
            self.assertEqual({a.title for a in found},{'My Plane Blue','My Plane Red'})
            self.assertTrue(all(x.source=='Community' for x in found))
            self.assertIn('texture=red',config.read_text())

    def test_invalid_path_does_not_scan_outside_known_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'UserCfg.opt'
            path.write_text('UnrelatedPath "C:\\XYZ"\n')
            self.assertIsNone(packages_root_from_cfg(path))
            self.assertEqual(scan_installed_aircraft([Path(temp)]),[])


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.m=next(m for m in MISSIONS if m.id=='ITA-IGA')

    def test_declared_weather_time_assistances_never_count_as_verified(self):
        p=Preflight(self.m.id,'Cessna 152',True,True,True,True,True,True,True,
                    planned_fuel_gal=12.0,planned_weight_lbs=1500,max_weight_lbs=1670)
        report=inspect_preflight(self.m,p)
        self.assertAlmostEqual(report['bonus_fraction'],.09)
        confirmed=inspect_preflight(self.m,p,verified={'clock':True,'assists':True})
        self.assertAlmostEqual(confirmed['bonus_fraction'],.15)
        self.assertFalse(confirmed['components']['Clima ao vivo (não verificável)']['ok'])
        self.assertTrue(report['fuel_ok'])
        self.assertTrue(report['weight_ok'])
        self.assertFalse(report['manual_verified'])

    def test_unverified_live_and_unmeasured_get_no_free_bonus(self):
        p=Preflight(self.m.id,'Cessna 152',fuel_checked=True,payload_checked=True)
        d=inspect_preflight(self.m,p)
        self.assertEqual(d['bonus_fraction'],0)
        self.assertFalse(d['fuel_ok'])
        self.assertFalse(d['weight_ok'])
        self.assertIsNotNone(d['fuel_required_gal'])

    def test_overweight_and_underfueled_not_rewarded(self):
        p=Preflight(self.m.id,'Cessna 152',fuel_checked=True,payload_checked=True,
                    planned_fuel_gal=0.1,planned_weight_lbs=1700,max_weight_lbs=1670)
        d=inspect_preflight(self.m,p)
        self.assertEqual(d['bonus_fraction'],0)

    def test_simconnect_aircraft_title_can_include_manufacturer(self):
        self.assertTrue(aircraft_title_matches('Cessna 152', 'TEXTRON AVIATION CESSNA 152'))
        self.assertTrue(aircraft_title_matches('Cessna 172 Skyhawk', 'ASOBO Cessna 172 Skyhawk'))
        self.assertFalse(aircraft_title_matches('Cessna 152', 'Cessna 172 Skyhawk'))
        self.assertFalse(aircraft_title_matches('Cessna 152', None))

    def test_plan_wrong_mission_rejected(self):
        with self.assertRaises(ValueError):
            inspect_preflight(self.m,Preflight('wrong','Cessna 152'))


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'career.db'
        self.db=Storage(self.path)
        self.db.create_pilot('Pilot Alpha','ABC123','SBRF')
        self.db.set_setting('balance','1200000')
        self.fm=self.db.fleet_manager()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_purchase_two_same_model_and_resell_one_without_duplicates(self):
        a=self.fm.purchase('c152','SBRF')
        b=self.fm.purchase('c152','SBRF')
        self.assertNotEqual(a['ref'],b['ref'])
        self.assertEqual(len(self.fm.all()),2)
        self.assertLess(resale_price(a),AIRCRAFT_ECONOMY['c152'].purchase_price)
        gain=self.fm.sell(a['ref'])
        self.assertGreater(gain,0)
        self.assertEqual(self.fm.selected()['ref'],b['ref'])
        self.assertEqual(len(self.fm.all()),1)

    def test_used_offer_purchase_idempotent(self):
        offer=used_market('SIPE',12345)[0]
        first=self.fm.purchase(offer.code,'SIPE',offer=offer)
        self.assertAlmostEqual(first['condition'],offer.condition)
        self.assertAlmostEqual(first['hours'],offer.hours)
        with self.assertRaises(ValueError):
            self.fm.purchase(offer.code,'SIPE',offer=offer)
        self.assertEqual(len(self.fm.all()),1)
        self.db.close();self.db=Storage(self.path);self.fm=self.db.fleet_manager()
        self.assertEqual(len(self.fm.all()),1)

    def test_rent_valid_then_expire_and_reject_sale(self):
        rent=self.fm.rent('c152','SBRF',1)
        self.assertEqual(rent['kind'],'rented')
        with self.assertRaises(ValueError): self.fm.sell(rent['ref'])
        self.assertIsNone(next((x for x in self.fm.all(rent['expires']+1) if x['ref']==rent['ref']),None))

    def test_starter_preserved_and_not_sellable(self):
        self.assertTrue(self.db.claim_starter())
        starter=self.fm.all()[0]
        self.assertEqual(starter['ref'],'legacy:c152')
        with self.assertRaises(ValueError): self.fm.sell(starter['ref'])

    def test_realism_bonus_is_atomic_and_separate_in_ledger(self):
        self.db.claim_starter()
        self.db.set_setting('balance','7130')
        start={'timestamp':100,'lat':AIRPORTS['SIPE'].latitude,'lon':AIRPORTS['SIPE'].longitude}
        end={'timestamp':1300,'lat':AIRPORTS['SIFC'].latitude,'lon':AIRPORTS['SIFC'].longitude}
        cp={'version':1,'career':{'mission_id':None},'tracker':{'phase':'solo'}}
        args=(start,end,-140,0,'REG-SIPE-T-1',1500,cp)
        self.assertTrue(self.db.finalize_flight(*args,aircraft_title='Cessna 152',
            fuel_start=12,fuel_end=11.5,realism_fraction=.18,destination='SIFC'))
        income=self.db.flight_finance(start)
        self.assertEqual(income['gross'],1770)
        self.assertEqual(income['realism_bonus'],270)
        self.assertEqual(self.db.pilot_stats()['xp'],47)  # 40 + 7
        after=int(self.db.get_setting('balance'))
        self.assertFalse(self.db.finalize_flight(*args,aircraft_title='Cessna 152',realism_fraction=.18))
        self.assertEqual(int(self.db.get_setting('balance')),after)
        self.assertEqual(len(self.db.list_flights()),1)

    def test_bonus_rejected_if_greater_than_limit(self):
        start={'timestamp':100,'lat':0,'lon':0}
        end={'timestamp':200,'lat':0,'lon':0}
        with self.assertRaises(ValueError):
            self.db.finalize_flight(start,end,-100,0,None,0,{},realism_fraction=.21)

    def test_buy_new_and_selected_own_wear_persists(self):
        unit=self.fm.purchase('c172','SBRF')
        cp={'version':1,'career':{},'tracker':{}}
        start={'timestamp':1000,'lat':AIRPORTS['SBRF'].latitude,'lon':AIRPORTS['SBRF'].longitude}
        end={'timestamp':2200,'lat':AIRPORTS['SIPE'].latitude,'lon':AIRPORTS['SIPE'].longitude}
        self.assertTrue(self.db.finalize_flight(start,end,-175,0,'REG-X1',1800,cp,
            aircraft_title='Cessna 172 Skyhawk',fuel_start=24,fuel_end=22,destination='SIPE'))
        aircraft=self.fm.selected()
        self.assertLess(aircraft['condition'],100)
        self.assertGreater(aircraft['hours'],0)
        self.assertEqual(aircraft['airport'],'SIPE')


if __name__=='__main__':unittest.main()
