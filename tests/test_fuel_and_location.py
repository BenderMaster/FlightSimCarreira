"""v0.6.1: combustível fiscalizado pelo addon e aeroporto real do exemplar."""
import tempfile
import unittest
from pathlib import Path
from aerocarreira.storage import Storage
from aerocarreira.fuel import FuelManager, valid_tanks
from aerocarreira.domain import AIRPORTS
from aerocarreira.contracts import AirportCatalog


class FuelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'career.db'
        self.db=Storage(self.path)
        self.db.create_pilot('Tester','TC123','SIPE')
        self.db.claim_starter()
        self.db.set_setting('balance','11532')
        self.now=1000.0
        self.manager=FuelManager(self.db,clock=lambda:self.now)
        self.caps={'LEFT_MAIN':13.0,'RIGHT_MAIN':13.0}
        self.base={'LEFT_MAIN':8.0,'RIGHT_MAIN':8.0}
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def observe(self,tanks,total=None,on_ground=True,enabled=True):
        if total is None: total=sum(tanks.values())
        return self.manager.observe('legacy:c152','c152',tanks,total,on_ground,self.caps,enabled)
    def test_initial_calibration_only_ground_and_never_free_refill(self):
        self.assertEqual(self.observe(self.base,on_ground=False)[0],'uninitialized')
        self.assertIsNone(self.manager.get('legacy:c152'))
        self.assertEqual(self.observe(self.base)[0],'calibrated')
        self.now+=3
        new={'LEFT_MAIN':12.0,'RIGHT_MAIN':12.0}
        status,correction=self.observe(new)
        self.assertEqual(status,'restore')
        self.assertEqual(correction,self.base)
        self.assertEqual(self.manager.get('legacy:c152')['tanks'],self.base)
        self.now+=3
        self.assertEqual(self.observe(self.base)[0],'consuming')
    def test_gradual_consumption_is_saved_and_survives_restart(self):
        self.observe(self.base)
        self.now+=3
        smaller={'LEFT_MAIN':7.95,'RIGHT_MAIN':7.95}
        self.assertEqual(self.observe(smaller)[0],'consuming')
        self.db.close();self.db=Storage(self.path)
        other=FuelManager(self.db,clock=lambda:self.now+1)
        self.assertEqual(other.get('legacy:c152')['tanks'],smaller)
        self.manager=other
    def test_sudden_drop_is_not_free_fuel_drain(self):
        self.observe(self.base)
        self.now+=3
        self.assertEqual(self.observe({'LEFT_MAIN':1,'RIGHT_MAIN':1})[0],'restore')
    def test_missing_tank_data_never_writes(self):
        self.assertEqual(self.observe({'LEFT_MAIN':8},16)[0],'unsupported')
        self.assertIsNone(self.manager.get('legacy:c152'))
        self.assertFalse(valid_tanks({'LEFT_MAIN':99,'RIGHT_MAIN':99},198,self.caps))
    def test_disabled_mode_keeps_consumption_but_not_added_fuel(self):
        self.observe(self.base)
        self.now+=3
        self.observe({'LEFT_MAIN':7.9,'RIGHT_MAIN':7.9},enabled=False)
        self.assertEqual(self.manager.get('legacy:c152')['tanks']['LEFT_MAIN'],7.9)
        self.now+=3
        self.assertEqual(self.observe({'LEFT_MAIN':13,'RIGHT_MAIN':13},enabled=False)[0],'disabled')
        self.assertEqual(self.manager.get('legacy:c152')['tanks']['LEFT_MAIN'],7.9)
        self.now+=3
        self.assertEqual(self.observe({'LEFT_MAIN':13,'RIGHT_MAIN':13})[0],'restore')
    def test_paid_refuel_and_no_double_charging(self):
        self.observe(self.base)
        result=self.manager.refuel_full('legacy:c152')
        self.assertAlmostEqual(result['added_gal'],10)
        self.assertGreater(result['cost_brl'],250)
        self.assertEqual(int(self.db.get_setting('balance')),11532-result['cost_brl'])
        self.assertEqual(sum(self.manager.get('legacy:c152')['tanks'].values()),26)
        self.now+=4
        status,corr=self.observe(self.base)
        self.assertEqual(status,'restore')
        self.assertEqual(sum(corr.values()),26)
        st={'timestamp':2000,'lat':AIRPORTS['SIPE'].latitude,'lon':AIRPORTS['SIPE'].longitude}
        en={'timestamp':3000,'lat':AIRPORTS['SIFC'].latitude,'lon':AIRPORTS['SIFC'].longitude}
        cp={'career':{},'tracker':{}}
        self.assertTrue(self.db.finalize_flight(st,en,-150,0,'REG-A',1300,cp,
            aircraft_title='Cessna 152',fuel_start=26,fuel_end=24,
            fuel_prepaid=True,destination='SIFC'))
        info=self.db.flight_finance(st)
        self.assertGreater(info['expenses'],0)
        self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM finance_ledger WHERE kind='combustivel'").fetchone()[0],0)
        self.assertEqual(self.db.fleet_manager().all()[0]['airport'],'SIFC')
    def test_no_money_no_refuel(self):
        self.observe(self.base)
        self.db.set_setting('balance','10')
        before=self.manager.get('legacy:c152')['tanks']
        with self.assertRaises(ValueError):self.manager.refuel_full('legacy:c152')
        self.assertEqual(self.manager.get('legacy:c152')['tanks'],before)
    def test_penalty_exact_xp_and_finance_idempotent(self):
        st={'timestamp':100,'lat':AIRPORTS['SIPE'].latitude,'lon':AIRPORTS['SIPE'].longitude}
        en={'timestamp':1300,'lat':AIRPORTS['SIFC'].latitude,'lon':AIRPORTS['SIFC'].longitude}
        cp={'career':{},'tracker':{},'fuel_penalty_frozen':.3}
        args=(st,en,-170,0,'FREE-TEST',2000,cp)
        self.assertTrue(self.db.finalize_flight(*args,aircraft_title='Cessna 152',realism_fraction=.1,fuel_penalty_fraction=.3))
        self.assertFalse(self.db.finalize_flight(*args,aircraft_title='Cessna 152',realism_fraction=.1,fuel_penalty_fraction=.3))
        self.assertEqual(self.db.flight_finance(st)['gross'],1540)
        self.assertEqual(self.db.pilot_stats()['xp'],31)
        self.assertEqual(self.db.get_setting('balance'),'13072')
        self.assertEqual(len(self.db.list_flights()),1)
        self.assertEqual(self.db.conn.execute("SELECT amount FROM finance_ledger WHERE kind='penalidade_combustivel'").fetchone()[0],-660)
        self.db.close();self.db=Storage(self.path)
        self.assertEqual(self.db.get_setting('balance'),'13072')
        self.assertEqual(self.db.pilot_stats()['xp'],31)

class LocationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Storage(Path(self.tmp.name)/'career.db')
        self.db.create_pilot('Tester','TC123','SBRF')
        self.db.claim_starter()
        self.db.set_setting('balance','1000000')
        self.cp={'career':{},'tracker':{}}
        self.st={'timestamp':100,'lat':AIRPORTS['SIPE'].latitude,'lon':AIRPORTS['SIPE'].longitude}
        self.en={'timestamp':500,'lat':AIRPORTS['SIFC'].latitude,'lon':AIRPORTS['SIFC'].longitude}
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def test_legacy_position_moves_on_paid_and_unpaid_flights(self):
        self.assertEqual(self.db.fleet_manager().all()[0]['airport'],'SBRF')
        self.db.finalize_flight(self.st,self.en,-120,0,'REG-A',800,self.cp,
                                aircraft_title='Cessna 152',destination='SIFC')
        self.assertEqual(self.db.fleet_manager().all()[0]['airport'],'SIFC')
        en2={'timestamp':900,'lat':AIRPORTS['SIPE'].latitude,'lon':AIRPORTS['SIPE'].longitude}
        st2={'timestamp':700,'lat':AIRPORTS['SIFC'].latitude,'lon':AIRPORTS['SIFC'].longitude}
        self.db.finalize_flight(st2,en2,-100,0,None,0,self.cp,
                                aircraft_title='Cessna 152',destination='SIPE')
        self.assertEqual(self.db.fleet_manager().all()[0]['airport'],'SIPE')
    def test_freelancer_does_not_move_private_starter(self):
        self.db.finalize_flight(self.st,self.en,-160,0,'FREE-TEST',2000,self.cp,
                                aircraft_title='Cessna 152',destination='SIFC')
        self.assertEqual(self.db.fleet_manager().all()[0]['airport'],'SBRF')
    def test_recover_last_legacy_landing_only_once(self):
        self.db.finalize_flight(self.st,self.en,-150,0,'REG-A',800,self.cp,aircraft_title='Cessna 152')
        cat=AirportCatalog(locations=AIRPORTS)
        self.assertEqual(self.db.recover_legacy_location(cat),'SIFC')
        self.assertEqual(self.db.fleet_manager().all()[0]['airport'],'SIFC')
        self.assertIsNone(self.db.recover_legacy_location(cat))
    def test_new_unit_and_rental_locations(self):
        unit=self.db.fleet_manager().purchase('c172','SBRF')
        fm=self.db.fleet_manager()
        fm.ensure_location(unit['ref'],'SIFC')
        self.assertEqual(fm.get(unit['ref'])['airport'],'SIFC')
        rental=fm.rent('c152','SIPE')
        fm.ensure_location(rental['ref'],'SIFC')
        self.assertEqual(fm.get(rental['ref'])['airport'],'SIFC')

if __name__=='__main__':unittest.main()

class SimConnectFuelTests(unittest.TestCase):
    def test_reader_recognizes_c152_tanks(self):
        from aerocarreira.sim_adapter import SampleReader, REQUIRED
        values={key:0.0 for key in REQUIRED.values()}
        values.update({'TITLE':'Textron Aviation Cessna 152', 'SIM_ON_GROUND':1,
            'FUEL_TOTAL_QUANTITY':12.5, 'FUEL_TANK_LEFT_MAIN_QUANTITY':6.25,
            'FUEL_TANK_RIGHT_MAIN_QUANTITY':6.25,
            'FUEL_TANK_LEFT_MAIN_CAPACITY':13.0,
            'FUEL_TANK_RIGHT_MAIN_CAPACITY':13.0})
        class Fake:
            def get(self,name):return values.get(name)
        rd=SampleReader(Fake(),clock=lambda:100)
        sample,missing=rd.read()
        self.assertFalse(missing)
        self.assertEqual(sample.fuel_tanks,{'LEFT_MAIN':6.25,'RIGHT_MAIN':6.25})
        self.assertEqual(sample.fuel_tank_capacities,{'LEFT_MAIN':13,'RIGHT_MAIN':13})

    def test_worker_writes_individual_tanks_not_read_only_total(self):
        import sys,time,types
        from unittest.mock import patch
        from queue import Queue,Empty
        from aerocarreira.sim_adapter import SimConnectWorker, REQUIRED
        sent=[]
        class Connection:
            quit=False
            def exit(self):pass
        class Requests:
            def __init__(self,*args,**kw):pass
            def get(self,key):
                if key in REQUIRED.values():return float(key=='SIM_ON_GROUND')
                return 1.0 if key=='FUEL_TOTAL_QUANTITY' else None
            def set(self,key,val):
                sent.append((key,val)); return None
        fake=types.ModuleType('SimConnect')
        fake.SimConnect=Connection; fake.AircraftRequests=Requests
        q=Queue()
        with patch.dict(sys.modules,{'SimConnect':fake}):
            worker=SimConnectWorker(q,interval=.01,reconnect_delay=.01)
            worker.start()
            worker.request_fuel_restore({'LEFT_MAIN':6.0,'RIGHT_MAIN':6.0})
            deadline=time.monotonic()+2
            msgs=[]
            while time.monotonic()<deadline:
                try:
                    evt=q.get(timeout=.05);msgs.append(evt)
                    if evt[0]=='fuel_sent':break
                except Empty:pass
            worker.stop();worker.thread.join(timeout=2)
        self.assertEqual(sent,[('FUEL_TANK_LEFT_MAIN_QUANTITY',6.0),('FUEL_TANK_RIGHT_MAIN_QUANTITY',6.0)])
        self.assertTrue(any(e[0]=='fuel_sent' for e in msgs))
        self.assertFalse(any('FUEL_TOTAL_QUANTITY'==k for k,v in sent))
        with self.assertRaises(ValueError):worker.request_fuel_restore({'TOTAL_QUANTITY':12})

    def test_legacy_last_flight_has_no_payout_change_when_recovering_location(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Storage(Path(temp)/'career.db')
            db.create_pilot('User','FLIGHT1','SBRF');db.claim_starter()
            st={'timestamp':1,'lat':AIRPORTS['SIPE'].latitude,'lon':AIRPORTS['SIPE'].longitude}
            en={'timestamp':10,'lat':AIRPORTS['SIFC'].latitude,'lon':AIRPORTS['SIFC'].longitude}
            db.finalize_flight(st,en,-100,0,'REG-TEST',1800,{'career':{},'tracker':{}},aircraft_title='Cessna 152')
            balance=db.get_setting('balance')
            count=len(db.list_flights())
            db.recover_legacy_location(AirportCatalog(locations=AIRPORTS))
            self.assertEqual(db.get_setting('balance'),balance)
            self.assertEqual(len(db.list_flights()),count)
            db.close()
