"""Airline Operations v0.8.5 — payroll, commitments and company isolation."""
import tempfile
import unittest
from pathlib import Path
from aerocarreira.storage import Storage
from aerocarreira import airline_operations as ops
from aerocarreira.contracts import AirportCatalog
from aerocarreira.domain import AIRPORTS

class AirlineOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"carreira.db"
        self.db=Storage(self.path)
        self.db.create_pilot('Teste','TESTE','SIPE')
        self.start=1800000000.0
        self.db.set_setting('balance','500000')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def hired(self,tier=0,company='nordeste'):
        with self.db.conn:
            self.db.conn.execute("UPDATE career_status SET mode='empregado',employer_code=?,updated_utc=? WHERE id=1",
                                 (company,self.start))
        ops.hire(self.db,company,self.start,tier)
        return ops.active_agreement(self.db)

    def work(self,number=5,duration=3600):
        for i in range(number):
            t=self.start+i*7200+60
            self.assertTrue(ops.record_employee_flight(
                self.db,'EMP-nordeste-SIPE-0-%02d'%i,
                'takeoff:airline:%d'%i,t,t+duration))

    def test_salary_and_xp_only_at_end_of_week(self):
        agreement=self.hired()
        self.work(5)
        self.assertEqual(self.db.airline_payroll(self.start+ops.WEEK_SECONDS-1),[])
        self.assertEqual(int(self.db.get_setting('balance')),500000)
        self.assertFalse(self.db.conn.execute("SELECT 1 FROM pilot_xp_ledger").fetchone())
        settled=self.db.airline_payroll(self.start+ops.WEEK_SECONDS+1)
        self.assertEqual(len(settled),1)
        self.assertEqual(settled[0]['result'],'cumprido')
        self.assertGreater(settled[0]['salary'],0)
        self.assertEqual(int(self.db.get_setting('balance')),
                         500000+settled[0]['salary'])
        xp=self.db.conn.execute("SELECT xp FROM pilot_xp_ledger WHERE flight_key=?",
                               ('salary:'+str(agreement['id'])+':0',)).fetchone()
        self.assertEqual(xp[0],settled[0]['xp'])
        self.assertEqual(self.db.airline_payroll(self.start+ops.WEEK_SECONDS+100),[])
        self.assertEqual(int(self.db.get_setting('balance')),
                         500000+settled[0]['salary'])

    def test_company_weekly_salary_base_is_quadruped_and_consistent(self):
        expected={'nordeste':36000,'azul':120000,'gol':92000,'latam':68000}
        self.assertEqual(ops.BASE_SALARY,expected)
        for company,salary in expected.items():
            employer=ops.EMPLOYER_BY_CODE[company]
            self.assertEqual(employer.weekly_salary,salary)
            self.assertEqual(ops.rate(company,employer.min_level,50,0)[0],salary)

    def test_economy_migration_scales_only_unsettled_payroll_once(self):
        agreement=self.hired()
        aid=agreement['id']
        with self.db.conn:
            self.db.conn.execute("INSERT INTO airline_week_rates VALUES(?,?,?,?,?)",
                                 (aid,0,9000,150,0))
            self.db.conn.execute("INSERT INTO airline_week_rates VALUES(?,?,?,?,?)",
                                 (aid,1,17000,150,0))
            self.db.conn.execute("INSERT INTO airline_payroll VALUES(?,?,?,?,?,?,?,?,?)",
                (aid,1,5,36000,0,17000,150,'cumprido',self.start+ops.WEEK_SECONDS+1))
            self.db.conn.execute("INSERT INTO contract_offers VALUES(?,?,?,?,?)",
                ('OLD-OFFER','SIPE','{}',self.start,self.start+86400))
            self.db.conn.execute("DELETE FROM settings WHERE key='economy_rebalance_v093_alpha3'")
        self.db.close()
        self.db=Storage(self.path)
        rows=dict(self.db.conn.execute(
            "SELECT week,base_salary FROM airline_week_rates WHERE agreement_id=?",(aid,)).fetchall())
        self.assertEqual(rows[0],36000)
        self.assertEqual(rows[1],17000)  # payroll already settled: historical amount unchanged
        self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM contract_offers").fetchone()[0],0)
        self.db.close()
        self.db=Storage(self.path)
        rows=dict(self.db.conn.execute(
            "SELECT week,base_salary FROM airline_week_rates WHERE agreement_id=?",(aid,)).fetchall())
        self.assertEqual(rows[0],36000)  # reopening does not multiply it again

    def test_ten_percent_commitment_penalizes_when_only_basic_met(self):
        self.hired(10);self.work(5)
        frozen=self.db.conn.execute(
            "SELECT base_salary,base_xp FROM airline_week_rates").fetchone()
        paid=self.db.airline_payroll(self.start+ops.WEEK_SECONDS+1)[0]
        self.assertEqual(paid['result'],'penalizado')
        self.assertEqual(paid['salary'],round(frozen[0]*.9))
        self.assertEqual(paid['xp'],round(frozen[1]*.9))

    def test_twenty_percent_target_and_penalty(self):
        self.hired(20);self.work(12)
        frozen=self.db.conn.execute(
            "SELECT base_salary,base_xp FROM airline_week_rates").fetchone()
        paid=self.db.airline_payroll(self.start+ops.WEEK_SECONDS+1)[0]
        self.assertEqual(paid['result'],'cumprido')
        self.assertEqual(paid['salary'],round(frozen[0]*1.2))
        self.assertEqual(paid['xp'],round(frozen[1]*1.2))
        self.assertEqual(ops.thresholds('nordeste',20),{'hours':20,'flights':12})
        self.assertEqual(ops.thresholds('nordeste',10),{'hours':15,'flights':8})
        self.assertEqual(ops.thresholds('nordeste',0),{'hours':10,'flights':5})

    def test_no_payment_without_basic_hours_or_flights(self):
        self.hired(20);self.work(2,600)
        paid=self.db.airline_payroll(self.start+ops.WEEK_SECONDS+1)[0]
        self.assertEqual(paid['salary'],0)
        self.assertEqual(paid['xp'],0)
        self.assertEqual(paid['result'],'sem_meta')
        self.assertEqual(int(self.db.get_setting('balance')),500000)

    def test_hours_instead_of_flights_is_sufficient(self):
        self.hired(10);self.work(4,4*3600)
        paid=self.db.airline_payroll(self.start+ops.WEEK_SECONDS+1)[0]
        self.assertEqual(paid['result'],'cumprido')
        self.assertGreater(paid['salary'],0)
        self.assertEqual(paid['factor'],1.1)

    def test_employee_flight_never_pays_immediate_cash_or_xp(self):
        self.hired(0)
        start={'timestamp':self.start+300,'lat':AIRPORTS['SIPE'].latitude,
               'lon':AIRPORTS['SIPE'].longitude}
        end={'timestamp':self.start+2300,'lat':AIRPORTS['SBJP'].latitude,
             'lon':AIRPORTS['SBJP'].longitude}
        key='EMP-nordeste-SIPE-0-00'
        before=int(self.db.get_setting('balance'))
        ck={'version':1,'career':{},'tracker':{'phase':'solo'}}
        saved=self.db.finalize_flight(start,end,-140,0,key,9000,ck,
            aircraft_title='Cessna 172 Skyhawk',fuel_start=35,fuel_end=27,
            flight_xp_extra=7,flight_xp_weight_bonus=5,destination='SBJP')
        self.assertTrue(saved)
        self.assertEqual(int(self.db.get_setting('balance')),before)
        self.assertEqual(self.db.conn.execute(
            "SELECT xp FROM pilot_xp_ledger").fetchone()[0],0)
        self.assertEqual(self.db.conn.execute(
            "SELECT reward FROM flights").fetchone()[0],0)
        self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM airline_work").fetchone()[0],1)
        self.assertFalse(self.db.finalize_flight(start,end,-140,0,key,9000,ck,
            aircraft_title='Cessna 172 Skyhawk',destination='SBJP'))
        self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM airline_work").fetchone()[0],1)

    def test_founding_400k_separates_business_cash_from_personal(self):
        with self.db.conn:
            self.db.conn.execute("INSERT INTO pilot_xp_ledger VALUES('end',25000,?)",(self.start,))
            self.db.conn.execute("INSERT INTO flights(started_utc,ended_utc,stall_warnings) VALUES(0,100000,0)")
            self.db.conn.execute("INSERT INTO pilot_qualifications VALUES('PLA',?)",(self.start,))
        self.assertEqual(ops.OWN_INVESTMENT,400000)
        self.db.found_company('Aero Teste',self.start)
        self.assertEqual(int(self.db.get_setting('balance')),100000)
        company=self.db.company_business()
        self.assertEqual(company['balance'],400000)
        self.assertEqual(company['name'],'Aero Teste')
        self.assertEqual(company['transactions'][0]['kind'],'aporte')
        with self.assertRaises(ValueError):self.db.found_company('Outra',self.start)
        bought=self.db.company_buy_plane('c172',self.start+1)
        self.assertGreater(bought,0)
        self.assertEqual(int(self.db.get_setting('balance')),100000)
        company=self.db.company_business()
        self.assertEqual(company['balance'],255000)
        self.assertEqual(company['planes'][0]['code'],'c172')
        self.assertEqual(len(self.db.fleet_manager().all()),0)

    def test_corporate_flight_only_affects_business_ledger(self):
        with self.db.conn:
            self.db.conn.execute("INSERT INTO pilot_xp_ledger VALUES('end',25000,?)",(self.start,))
            self.db.conn.execute("INSERT INTO flights(started_utc,ended_utc,stall_warnings) VALUES(0,100000,0)")
            self.db.conn.execute("INSERT INTO pilot_qualifications VALUES('PLA',?)",(self.start,))
        self.db.found_company('Aero Teste',self.start)
        self.db.company_buy_plane('c172',self.start+1)
        routes=self.db.company_routes(AIRPORTS['SIPE'],AirportCatalog(AIRPORTS),17)
        self.assertTrue(routes)
        mission=routes[0]
        takeoff={'timestamp':self.start+200,'lat':AIRPORTS['SIPE'].latitude,
                 'lon':AIRPORTS['SIPE'].longitude}
        arrival={'timestamp':self.start+2000,'lat':AIRPORTS[mission.destination].latitude,
                 'lon':AIRPORTS[mission.destination].longitude}
        cash_before=int(self.db.get_setting('balance'))
        xp_before=self.db.conn.execute('SELECT COUNT(*),COALESCE(SUM(xp),0) FROM pilot_xp_ledger').fetchone()
        company_before=self.db.company_business()['balance']
        ck={'version':1,'career':{},'tracker':{'phase':'solo'}}
        done=self.db.finalize_flight(takeoff,arrival,-170,0,mission.id,mission.reward,ck,
            aircraft_title='Cessna 172 Skyhawk',destination=mission.destination,
            fuel_start=40,fuel_end=35)
        self.assertTrue(done)
        self.assertEqual(int(self.db.get_setting('balance')),cash_before)
        self.assertEqual(self.db.company_business()['operations'],1)
        self.assertGreater(self.db.company_business()['balance'],company_before)
        self.assertEqual(self.db.conn.execute("SELECT reward FROM flights ORDER BY id DESC LIMIT 1").fetchone()[0],0)
        xp_after=self.db.conn.execute(
            'SELECT COUNT(*),COALESCE(SUM(xp),0) FROM pilot_xp_ledger').fetchone()
        # Flight history keeps an explicit zero-XP record for auditability.
        self.assertEqual(xp_after[0],xp_before[0]+1)
        self.assertEqual(xp_after[1],xp_before[1])
        self.assertFalse(self.db.finalize_flight(takeoff,arrival,-170,0,mission.id,mission.reward,ck,
            aircraft_title='Cessna 172 Skyhawk',destination=mission.destination))
        self.assertEqual(self.db.company_business()['operations'],1)

if __name__=='__main__':unittest.main()
