"""Regressões do Bloco Financeiro v0.5: ledger idempotente e migração segura."""
from __future__ import annotations
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from aerocarreira.finance import (brl, market_reward, estimated_minutes,
    mission_radius_by_level, flight_operating_cost)
from aerocarreira.contracts import (generate_offers, AirportCatalog, pilot_level)
from aerocarreira.domain import AIRPORTS
from aerocarreira.storage import Storage


class FinanceCoreTests(unittest.TestCase):
    def test_reais_not_dollars(self):
        self.assertEqual(brl(7130), 'R$ 7.130')
        self.assertEqual(brl(-2455), '-R$ 2.455')

    def test_twenty_minutes_pays_about_1500(self):
        # 22.5NM a 90kt + 5min planejamento = 20min
        self.assertEqual(estimated_minutes(22.5),20)
        self.assertGreaterEqual(market_reward(22.5),1400)
        self.assertLessEqual(market_reward(22.5),1650)
        self.assertGreater(market_reward(50),market_reward(22.5))

    def test_freelancer_and_levels(self):
        self.assertLess(market_reward(22.5,freelance=True),market_reward(22.5))
        self.assertLess(mission_radius_by_level(1),mission_radius_by_level(10))
        self.assertLessEqual(mission_radius_by_level(1),55)

    def test_region_offers_short_and_attractive(self):
        center=AIRPORTS['SIPE']
        catalog=AirportCatalog(locations=AIRPORTS)
        offers=generate_offers(center,catalog,{'xp':0,'level':1,'hours':0},{'PPA'}, {},20835)
        self.assertTrue(offers)
        for m in offers:
            self.assertTrue(m.destination in ('SIFC','SBRF','SBJP'))
            self.assertGreaterEqual(m.reward,750)
            self.assertLessEqual(m.reward,4500)

    def test_fuel_cost_and_fallback(self):
        data=flight_operating_cost('c152',1200,15,13.3)
        self.assertFalse(data['fuel_estimated'])
        self.assertGreater(data['fuel_brl'],0)
        self.assertGreater(data['wear'],0)
        estimate=flight_operating_cost('c152',1200,None,None)
        self.assertTrue(estimate['fuel_estimated'])
        self.assertGreater(estimate['fuel_brl'],0)
        self.assertEqual(flight_operating_cost('unknown',1200,None,None)['fuel_brl'],0)


class FinanceStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'carreira.db'
        self.db=Storage(self.path)
        self.db.create_pilot('Teste Piloto','TEST01','SIPE')
        self.db.set_setting('balance','7130')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def flight(self, number=1, code='Cessna 152', mission='REG-SIPE-20999-01',reward=1550,fuel_start=15,fuel_end=13):
        st={'timestamp':number*10000.0, 'lat':AIRPORTS['SIPE'].latitude,'lon':AIRPORTS['SIPE'].longitude}
        en={'timestamp':number*10000.0+1200,'lat':AIRPORTS['SIFC'].latitude,'lon':AIRPORTS['SIFC'].longitude}
        cp={'version':1,'career':{'mission_id':None},'tracker':{'phase':'solo'}}
        result=self.db.finalize_flight(st,en,-176,0,mission,reward,cp,aircraft_title=code,
                                     fuel_start=fuel_start,fuel_end=fuel_end)
        return st,result

    def test_starter_once_and_no_historical_charge(self):
        self.assertTrue(self.db.claim_starter())
        self.assertFalse(self.db.claim_starter())
        self.assertEqual(self.db.get_setting('balance'),'7130')
        self.assertEqual(len(self.db.owned_fleet()),1)

    def test_owned_cost_net_and_wear_and_idempotent(self):
        self.db.claim_starter()
        start,first=self.flight()
        self.assertTrue(first)
        fin=self.db.flight_finance(start)
        self.assertEqual(fin['gross'],1550)
        self.assertGreater(fin['expenses'],0)
        self.assertEqual(int(self.db.get_setting('balance')),7130+fin['net'])
        first_condition=self.db.owned_fleet()[0]['condition']
        self.assertLess(first_condition,100)
        self.assertEqual(self.db.flight(1) if False else self.flight()[1],False)
        self.assertEqual(self.db.owned_fleet()[0]['condition'],first_condition)
        self.assertEqual(len(self.db.list_flights()),1)
        self.assertEqual(self.db.pilot_stats()['xp'],40)
        self.assertEqual(len(self.db.finance_history()),3)

    def test_freelance_employer_pays_operating_cost(self):
        self.db.claim_starter()
        start,first=self.flight(mission='FREE-SIPE-20999-01')
        self.assertTrue(first)
        fin=self.db.flight_finance(start)
        self.assertEqual(fin['gross'],1550)
        self.assertEqual(fin['expenses'],0)
        self.assertEqual(self.db.owned_fleet()[0]['condition'],100)

    def test_no_charge_without_registered_aircraft(self):
        start,first=self.flight()
        self.assertTrue(first)
        self.assertEqual(self.db.flight_finance(start)['expenses'],0)

    def test_optional_tax(self):
        self.db.set_setting('income_tax_enabled','1')
        start,_=self.flight()
        self.assertEqual(self.db.flight_finance(start)['expenses'],round(1550*.04))
        self.assertEqual(self.db.get_setting('simulated_failures_enabled'),'0')

    def test_insurance_requires_money_and_preserves_flag(self):
        self.db.claim_starter()
        paid=self.db.set_insurance('c152',True)
        self.assertEqual(paid,7130-220)
        self.assertTrue(self.db.owned_fleet()[0]['insured'])
        self.assertEqual(self.db.set_insurance('c152',False),paid)
        with self.assertRaises(ValueError):self.db.set_insurance('c152',False)

    def test_service_and_reopen(self):
        self.db.claim_starter()
        self.flight()
        condition=self.db.owned_fleet()[0]['condition']
        self.assertLess(condition,100)
        amount=self.db.service_aircraft('c152')
        self.assertEqual(self.db.owned_fleet()[0]['condition'],100)
        self.assertEqual(int(self.db.get_setting('balance')),amount)
        self.db.close()
        self.db=Storage(self.path)
        self.assertEqual(self.db.owned_fleet()[0]['condition'],100)
        self.assertEqual(int(self.db.get_setting('balance')),amount)
        with self.assertRaises(ValueError):self.db.service_aircraft('c152')

    def test_loan_and_repayment(self):
        self.assertEqual(self.db.take_loan(10000),17130)
        self.assertEqual(self.db.outstanding_loan(),10800)
        with self.assertRaises(ValueError):self.db.take_loan(30000)
        self.assertEqual(self.db.repay_loan(1000),16130)
        self.assertEqual(self.db.outstanding_loan(),9800)

    def test_purchase_rejects_low_balance_no_ledger(self):
        with self.assertRaises(ValueError):self.db.buy_aircraft('c172')
        self.assertEqual(self.db.get_setting('balance'),'7130')
        self.assertFalse(self.db.owned_fleet())
        self.assertEqual(self.db.finance_history(),[])

    def test_migration_from_old_db_keeps_balance_and_flights(self):
        self.db.close()
        self.path.unlink()
        legacy=sqlite3.connect(self.path)
        legacy.execute('CREATE TABLE settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        legacy.execute("INSERT INTO settings VALUES('balance','7130')")
        legacy.execute('CREATE TABLE flights (id INTEGER PRIMARY KEY AUTOINCREMENT,started_utc REAL NOT NULL,ended_utc REAL NOT NULL,from_lat REAL,from_lon REAL,to_lat REAL,to_lon REAL,touchdown_fpm_est REAL,stall_warnings INTEGER NOT NULL,mission_id TEXT,reward INTEGER NOT NULL DEFAULT 0)')
        legacy.execute("INSERT INTO flights(started_utc,ended_utc,stall_warnings,mission_id,reward) VALUES(1,2,0,'old',860)")
        legacy.commit(); legacy.close()
        self.db=Storage(self.path)
        self.assertEqual(self.db.get_setting('balance'),'7130')
        self.assertEqual(len(self.db.list_flights()),1)
        self.assertEqual(self.db.finance_history(),[])
        self.assertTrue(self.path.with_name('carreira.pre_v050.backup.db').is_file())

if __name__ == '__main__':unittest.main()
