"""Bloco 2: nível, mercado regional, freelancer, idempotência e migração."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest
from aerocarreira.contracts import (AirportCatalog, TYPE_BY_CODE, EMPLOYER_FLEET,
    pilot_level, next_level_xp, eligibility, generate_offers, matches_aircraft, aircraft_family)
from aerocarreira.domain import Airport, AIRPORTS, Career, FlightTracker, FlightSample, Mission, Phase
from aerocarreira.storage import Storage
from aerocarreira.sim_adapter import SampleReader


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'carreira.db'
        self.db = Storage(self.path)
        self.db.create_pilot('Piloto de Teste','PILOT1','SIPE')
        self.origin = AIRPORTS['SIPE']
        self.catalog = AirportCatalog({**AIRPORTS,
            'KJFK':Airport('KJFK','New York',40.6413,-73.7781),
            'KSEA':Airport('KSEA','Seattle',47.450,-122.309)})

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def generated(self, stats=None, quals=None, families=None):
        return generate_offers(self.origin,self.catalog, stats or self.db.pilot_stats(),
            quals or self.db.owned_qualifications(),families or self.db.family_experience(),
            21490)

    def sample(self, t, airport, on_ground, gs=0, agl=0, title='Asobo Cessna 152'):
        a = AIRPORTS[airport]
        return FlightSample(t,a.latitude,a.longitude,1000+agl,agl,max(gs,35),gs,
                            -172 if not on_ground else 0,on_ground,aircraft_title=title)

    def test_levels_progressive_and_unbounded_under_100(self):
        self.assertEqual(pilot_level(0),1)
        self.assertEqual(pilot_level(114),1)
        self.assertEqual(pilot_level(115),2)
        self.assertEqual(pilot_level(259),2)
        self.assertEqual(pilot_level(260),3)
        self.assertEqual(next_level_xp(8),1760)
        self.assertGreater(pilot_level(2500),10)

    def test_all_kinds_and_balanced_unlocks(self):
        self.assertEqual(set(TYPE_BY_CODE),{'cargo','tourism','passenger','airtaxi','humanitarian',
                         'medical','executive','rescue','special'})
        self.assertEqual({x:TYPE_BY_CODE[x].min_level for x in ('cargo','airtaxi','medical','executive','rescue')},
                         {'cargo':1,'airtaxi':3,'medical':6,'executive':8,'rescue':10})
        mission=Mission('x','SIPE','SIFC','',200,category='rescue')
        self.assertFalse(eligibility(mission,{'xp':0,'hours':0},{'PPA'})[0])
        self.assertFalse(eligibility(mission,{'xp':5000,'hours':10},{'PPA'})[0])
        self.assertTrue(eligibility(mission,{'xp':5000,'hours':10},{'PPA','PCA','IFR'})[0])

    def test_local_only_limited_deterministic_and_freelance(self):
        offers = self.generated()
        self.assertLessEqual(len(offers),13)
        self.assertGreater(len(offers),0)
        self.assertTrue(all(m.origin=='SIPE' and m.destination in ('SIFC','SBRF','SBJP') for m in offers))
        self.assertEqual(len({m.id for m in offers}),len(offers))
        self.assertEqual(offers,self.generated())
        self.assertTrue(any(m.freelance and m.employer_plane=='c152' for m in offers))
        self.assertTrue(all(m.category=='cargo' for m in offers))

    def test_freelance_expertise_and_model_guards(self):
        m=Mission('FREE','SIPE','SIFC','',150,category='cargo',freelance=True,employer_plane='c172')
        s={'xp':400,'hours':3}
        self.assertFalse(eligibility(m,s,{'PPA'},{} )[0])
        self.assertTrue(eligibility(m,s,{'PPA'},{'single':2})[0])
        self.assertTrue(matches_aircraft('Asobo Cessna 172 Skyhawk G1000','c172'))
        self.assertFalse(matches_aircraft('Asobo Cessna 152','c172'))
        self.assertEqual(aircraft_family('Cessna Citation CJ4'),'jet')
        self.assertIsNone(aircraft_family(None))

    def test_freelance_payout_only_if_aircraft_matches_at_both_ends(self):
        offer=next(x for x in self.generated() if x.freelance)
        c=Career()
        c.accept(offer,self.sample(0,'SIPE',True))
        c.evaluate([{'type':'takeoff','timestamp':10,'lat':self.origin.latitude,
                     'lon':self.origin.longitude}], 'Cessna 172')
        target=self.catalog.locations[offer.destination]
        landing={'type':'landing','timestamp':100,'lat':target.latitude,'lon':target.longitude}
        self.assertIsNone(c.evaluate([landing], 'Asobo Cessna 152'))
        self.assertEqual(c.balance,5000)
        self.assertIsNotNone(c.mission)
        c.evaluate([{'type':'takeoff','timestamp':110,'lat':self.origin.latitude,'lon':self.origin.longitude}],
                   'Asobo Cessna 152')
        self.assertIsNone(c.evaluate([landing],None))
        self.assertEqual(c.evaluate([landing],'Asobo Cessna 152')['reward'],offer.reward)

    def test_generated_contract_snapshot_restored_without_catalog(self):
        offer=next(m for m in self.generated() if not m.freelance)
        c=Career()
        c.accept(offer,self.sample(0,'SIPE',True))
        snapshot=c.snapshot()
        self.db.set_checkpoint({'version':1,'tracker':FlightTracker().snapshot(), 'career':snapshot})
        self.db.close();self.db=Storage(self.path)
        restored=Career(int(self.db.get_setting('balance')))
        restored.restore(self.db.get_checkpoint()['career'])
        self.assertEqual(restored.mission,offer)
        self.assertTrue(restored.origin_confirmed)

    def test_market_cache_24h_and_only_current_region(self):
        offers=self.generated()
        self.db.save_offers('SIPE',offers,now=100000,valid_s=3600)
        self.assertTrue(self.db.offer_cache_valid('SIPE',100030))
        self.assertFalse(self.db.offer_cache_valid('SBRF',100030))
        self.assertFalse(self.db.offer_cache_valid('SIPE',104000))
        self.assertEqual(len(self.db.active_offers('SIPE',100030)),len(offers))
        new=generate_offers(AIRPORTS['SBRF'],self.catalog,self.db.pilot_stats(),{'PPA'},{},21490)
        self.db.save_offers('SBRF',new,now=100100,valid_s=3600)
        self.assertEqual(self.db.active_offers('SIPE',100101),[])
        self.assertLessEqual(self.db.conn.execute('SELECT COUNT(*) FROM contract_offers').fetchone()[0],13)

    def test_cannot_store_unbounded_or_wrong_region(self):
        m=self.generated()[0]
        with self.assertRaises(ValueError): self.db.save_offers('SBRF',[m])
        with self.assertRaises(ValueError): self.db.save_offers('SIPE',[m]*21)

    def test_payment_only_once_per_generated_contract_even_with_new_takeoff(self):
        m=self.generated()[0]
        self.db.save_offers('SIPE',[m],now=1000,valid_s=9999)
        cp={'version':1,'career':{'mission_id':None},'tracker':{'phase':'solo'}}
        def finish(i):
            start={'timestamp':1000+i*100,'lat':self.origin.latitude,'lon':self.origin.longitude}
            dest=self.catalog.locations[m.destination]
            end={'timestamp':1060+i*100,'lat':dest.latitude,'lon':dest.longitude}
            return self.db.finalize_flight(start,end,-172,0,m.id,m.reward,cp,aircraft_title='Asobo Cessna 152')
        self.assertTrue(finish(0))
        self.assertTrue(self.db.contract_completed(m.id))
        self.assertEqual(self.db.active_offers('SIPE',1001),[])
        self.assertEqual(self.db.get_setting('balance'),str(5000+m.reward))
        self.assertFalse(finish(0))
        self.assertTrue(finish(1))   # novo voo, MESMO contrato, sem pagamento repetido
        self.assertEqual(self.db.get_setting('balance'),str(5000+m.reward))
        self.assertEqual(self.db.conn.execute('SELECT COUNT(*) FROM flights').fetchone()[0],2)
        self.assertEqual(self.db.conn.execute('SELECT SUM(reward) FROM flights').fetchone()[0],m.reward)

    def test_legacy_migration_keeps_balance_and_history(self):
        self.db.set_setting('balance','6270')
        self.db.save_flight({'timestamp':100,'lat':-7,'lon':-34},
                            {'timestamp':200,'lat':-7,'lon':-34},-120,0,'ITA-IGA',420)
        self.db.close()
        self.db=Storage(self.path)
        self.assertEqual(self.db.get_setting('balance'),'6270')
        self.assertEqual(len(self.db.list_flights()),1)
        self.assertIn('aircraft_title',{col[1] for col in self.db.conn.execute('PRAGMA table_info(flights)')})
        self.assertEqual(self.db.pilot_stats()['level'],1)
        self.assertEqual(self.db.family_experience(),{})

    def test_title_soft_read_and_experience_increment(self):
        from aerocarreira.domain import FlightSample
        class MockRequest:
            def get(self,k):
                mapping={'PLANE_LATITUDE':-7.8,'PLANE_LONGITUDE':-34.8,'PLANE_ALTITUDE':200,
                         'PLANE_ALT_ABOVE_GROUND':200,'AIRSPEED_INDICATED':70,'SIM_ON_GROUND':0,
                         'GROUND_VELOCITY':65,'VERTICAL_SPEED':-150,
                         'TITLE':'Asobo Cessna 152'}
                return mapping.get(k)
        reader=SampleReader(MockRequest(),clock=lambda:100)
        sample,missing=reader.read()
        self.assertEqual(missing,[])
        self.assertEqual(sample.aircraft_title,'Asobo Cessna 152')
        cp={'career':{},'tracker':{}}
        self.db.finalize_flight({'timestamp':100,'lat':-7,'lon':-34},
            {'timestamp':200,'lat':-7,'lon':-34},-100,0,None,0,cp,sample.aircraft_title)
        self.assertEqual(self.db.family_experience(),{'single':1,'c152':1})


if __name__ == '__main__':
    unittest.main()

class GlobalCatalogAndRegressionTests(unittest.TestCase):
    def test_world_catalog_adapter_without_network(self):
        import types,sys
        from unittest.mock import patch
        def load(format):
            self = {'lat':47.45,'lon':-122.308,'name':'Seattle'}
            other={'lat':47.55,'lon':-122.301,'name':'Boeing Field'}
            return {'KSEA':self,'KBFI':other,'NOPE':{'lat':float('nan'),'lon':0,'name':'bad'}}
        with patch.dict(sys.modules,{'airportsdata':types.SimpleNamespace(load=load)}):
            catalog=AirportCatalog()
        self.assertTrue(catalog.global_catalog)
        self.assertIn('KSEA',catalog.locations)
        self.assertNotIn('NOPE',catalog.locations)
        near=catalog.nearest(47.45,-122.308,3)
        self.assertEqual(near.icao,'KSEA')
        self.assertTrue(any(a.icao=='KBFI' for a,_ in catalog.around(near,100)))
        self.assertFalse(any(a.icao=='SIPE' for a,_ in catalog.around(near,100)))

    def test_cannot_claim_different_contract_with_same_flight_key(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Storage(Path(folder)/'career.db')
            cp={'career':{},'tracker':{}}
            s={'timestamp':100.0,'lat':-7.65,'lon':-34.86}
            e={'timestamp':120.0,'lat':-7.84,'lon':-34.89}
            self.assertTrue(db.finalize_flight(s,e,-110,0,'REG-SIPE-1',100,cp))
            self.assertFalse(db.finalize_flight(s,e,-110,0,'REG-SIPE-2',200,cp))
            self.assertFalse(db.contract_completed('REG-SIPE-2'))
            self.assertEqual(db.get_setting('balance'),'5100')
            db.close()

    def test_freelance_requires_model_expertise_if_specified(self):
        from aerocarreira.contracts import PLANE_BY_CODE
        m=Mission('FREE-JET','SIPE','SIFC','Teste',1000,
                  category='executive',freelance=True,employer_plane='cj4')
        s={'xp':20000,'hours':80.0}
        quals={'PPA','PCA','IFR','MLTE','PLA'}
        self.assertFalse(eligibility(m,s,quals,{'jet':10,'cj4':0})[0])
        self.assertTrue(eligibility(m,s,quals,{'jet':10,'cj4':1})[0])
        self.assertGreater(PLANE_BY_CODE['cj4'].min_model_flights,0)

    def test_unavailable_coordinates_no_airport(self):
        import math
        c=AirportCatalog({'KSEA':Airport('KSEA','Seattle',47.45,-122.3)})
        self.assertIsNone(c.nearest(float('nan'),-122))
        self.assertIsNone(c.nearest(30,20,5))
