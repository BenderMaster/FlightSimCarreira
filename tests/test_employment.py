"""Modalidades e vagas — regressões críticas, testes sem simulador."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from aerocarreira.storage import Storage
from aerocarreira.employment import (vacancies, weekly_period, EMPLOYER_BY_CODE,
    employment_eligibility, generate_employer_routes, OWN_MIN_LEVEL, OWN_INVESTMENT)
from aerocarreira.contracts import AirportCatalog
from aerocarreira.domain import AIRPORTS


class EmploymentTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.path=Path(self.dir.name)/'carreira.db'
        self.db=Storage(self.path)
        self.db.create_pilot('Piloto Teste','ABC123','SIPE')
        self.now=1800000000.0
        self.period=weekly_period(self.now)
        self.catalog=AirportCatalog(AIRPORTS)

    def tearDown(self):
        self.db.close();self.dir.cleanup()

    def good_stats(self):
        return {'level':99,'hours':200,'xp':100000,'flights':300,'qualifications':{'PPA','PCA','IFR','MLTE','PLA'}}

    def test_starts_as_autonomous_and_preserves_old_db(self):
        self.assertEqual(self.db.employment_state()['mode'],'autonomo')
        self.db.set_setting('balance','6270')
        self.db.save_flight({'timestamp':100,'lat':0,'lon':0},{'timestamp':120,'lat':0,'lon':1},-172,0,'ITA-IGA',420)
        self.db.close();self.db=Storage(self.path)
        self.assertEqual(self.db.get_setting('balance'),'6270')
        self.assertEqual(len(self.db.list_flights()),1)
        self.assertEqual(self.db.get_pilot()['home_icao'],'SIPE')
        self.assertEqual(self.db.employment_state()['mode'],'autonomo')

    def test_vacancy_weekly_deterministic_and_scoped(self):
        items=vacancies(self.period,'SIPE')
        self.assertEqual(items,vacancies(self.period,'SIPE'))
        self.assertEqual(len(items),4)
        self.assertEqual(len({x.id for x in items}),4)
        self.assertNotEqual({x.id for x in items},{x.id for x in vacancies(self.period+1,'SIPE')})
        self.assertTrue(all(x.airport=='SIPE' for x in items))
        self.assertTrue(all('simulação' not in EMPLOYER_BY_CODE[x.company].name and 'fictícia' not in EMPLOYER_BY_CODE[x.company].name for x in items))
        with self.assertRaises(ValueError):vacancies(self.period,'../abc')

    def test_real_airline_names_are_not_actual_jobs(self):
        self.assertTrue({'gol','azul','latam'}.issubset(EMPLOYER_BY_CODE))
        self.assertTrue(all(EMPLOYER_BY_CODE[k].real_name_reference for k in ('gol','azul','latam')))
        self.assertFalse(employment_eligibility(vacancies(self.period,'SIPE')[0],
            {'level':1,'hours':0},{'PPA'})[0])

    def test_application_checks_rules_and_same_week_duplicates(self):
        v=next(v for v in vacancies(self.period,'SIPE') if v.company=='nordeste')
        with self.assertRaises(ValueError):self.db.apply_vacancy(v,self.now)
        with self.db.conn:
            self.db.conn.execute("INSERT INTO pilot_xp_ledger VALUES('test',250,?)",(self.now,))
            self.db.conn.execute("INSERT INTO flights(started_utc,ended_utc,stall_warnings) VALUES(?,?,?)",(1,3601,0))
        self.assertGreaterEqual(self.db.pilot_stats()['level'],2)
        self.db.apply_vacancy(v,self.now)
        with self.assertRaisesRegex(ValueError,'candidatura'):self.db.apply_vacancy(v,self.now)
        with self.assertRaises(ValueError): self.db.apply_vacancy(replace(v, id='fake'),self.now)
        self.assertEqual(self.db.employment_state()['mode'],'autonomo')
        self.assertEqual(self.db.review_applications(self.now),[])
        self.db.close();self.db=Storage(self.path)
        self.assertEqual(len(self.db.list_applications()),1)
        result=self.db.review_applications((self.period+1)*7*86400+1)
        self.assertEqual(len(result),1)
        self.assertIn(result[0]['result'],('rejected','hired'))
        self.assertEqual(self.db.review_applications((self.period+1)*7*86400+2),[])
        if result[0]['result']=='hired':
            self.assertEqual(self.db.employment_state()['mode'],'empregado')
            self.db.resign_employment((self.period+1)*7*86400+4)
            self.assertEqual(self.db.employment_state()['mode'],'autonomo')
        self.assertEqual(self.db.get_setting('balance'),'5000')  # nenhum salário automático

    def test_hired_routes_are_local_and_qualified(self):
        origin=AIRPORTS['SIPE']
        routes=generate_employer_routes('nordeste',origin,self.catalog,self.good_stats(),{'PPA','PCA','IFR','MLTE','PLA'},
                                        {'single':30,'c172':20},self.period)
        self.assertLessEqual(len(routes),2)
        self.assertTrue(routes)
        self.assertTrue(all(x.company_code=='nordeste' and x.freelance and x.origin=='SIPE' for x in routes))
        self.assertTrue(all(x.employer_plane=='c172' for x in routes))
        self.assertFalse(generate_employer_routes('nordeste',origin,self.catalog,
            {'level':1,'hours':0},{'PPA'},{},self.period))
        self.assertFalse(generate_employer_routes('nonexistent',origin,self.catalog,self.good_stats(),{'PPA'},{},self.period))

    def test_endgame_company_validation_and_atomic_investment(self):
        with self.assertRaises(ValueError):self.db.found_company('Nossa Empresa',self.now)
        self.db.set_setting('balance','500000')
        # XP/hours são lidos de fatos existentes, não é possível forçar nível por parâmetro UI.
        with self.db.conn:
            self.db.conn.execute("INSERT INTO pilot_xp_ledger VALUES('endgame',8000,?)",(self.now,))
            self.db.conn.execute("INSERT INTO flights(started_utc,ended_utc,stall_warnings) VALUES(?,?,?)",(0,100000,0))
            self.db.conn.execute("INSERT OR IGNORE INTO pilot_qualifications VALUES('PLA',?)",(self.now,))
        self.assertGreaterEqual(self.db.pilot_stats()['level'],OWN_MIN_LEVEL)
        with self.assertRaises(ValueError):self.db.found_company('  ',self.now)
        state=self.db.found_company('Aero Bender',self.now)
        self.assertEqual(state['mode'],'empresario')
        self.assertEqual(state['owner_company'],'Aero Bender')
        self.assertEqual(int(self.db.get_setting('balance')),500000-OWN_INVESTMENT)
        with self.assertRaises(ValueError):self.db.found_company('Duplicada',self.now)
        self.assertEqual(int(self.db.get_setting('balance')),100000)
        self.db.close();self.db=Storage(self.path)
        self.assertEqual(self.db.employment_state()['owner_company'],'Aero Bender')

    def test_expired_application_not_permitted(self):
        v=vacancies(self.period,'SIPE')[0]
        with self.assertRaises(ValueError):self.db.apply_vacancy(v,(self.period+1)*7*86400+1)

    def test_local_market_invalidation_doesnt_delete_completed(self):
        self.db.conn.execute("INSERT INTO completed_contracts VALUES('FREE-1','key',?)",(self.now,))
        self.db.conn.commit()
        self.db.save_offers('SIPE',[],self.now)
        self.db.invalidate_market()
        self.assertTrue(self.db.contract_completed('FREE-1'))


if __name__=='__main__':unittest.main()
