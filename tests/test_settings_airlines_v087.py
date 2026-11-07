"""v0.8.7: airline type ratings, safe settings, focus event queue regression."""
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from aerocarreira import airline_operations, pilot_career, settings_center, type_ratings
from aerocarreira.contracts import AirportCatalog
from aerocarreira.domain import AIRPORTS
from aerocarreira.employment import vacancies, weekly_period, employment_eligibility, generate_employer_routes
from aerocarreira.profiles import ProfileManager
from aerocarreira.storage import Storage


class AirlineTypeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.db=Storage(self.root/'carreira.db')
        self.db.create_pilot('Testador','TESTRF','SBRF')
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_fleets_are_airline_specific(self):
        self.assertEqual(set(type_ratings.FLEETS['gol']),
            {'b737700','b737800','b737max8','a330900neo','a320neo'})
        self.assertIn('a320neo',type_ratings.FLEETS['azul'])
        self.assertIn('a320neo',type_ratings.FLEETS['latam'])
        self.assertNotIn('c152',type_ratings.FLEETS['gol'])
        self.assertFalse(type_ratings.valid_for_company('gol','c152',{'c152'}))
        self.assertFalse(type_ratings.valid_for_company('gol','a320neo',set()))
        self.assertTrue(type_ratings.valid_for_company('gol','a320neo',{'a320neo'}))
        self.assertFalse(type_ratings.valid_for_company('latam','b737800',{'b737800'}))
        self.assertTrue(type_ratings.valid_for_company('nordeste','c152',set()))
        self.assertFalse(type_ratings.valid_for_company('nordeste','a320neo',set()))

    def test_aliases_reject_ambiguous_titles(self):
        for title,model in (
            ('Airbus A320neo LEAP','a320neo'),
            ('Airbus A320-200','a320200'),
            ('A321neo','a321neo'),('Airbus A321P2F','a321p2f'),
            ('Boeing 737 MAX 8','b737max8'),('Boeing 737-800','b737800'),
            ('Embraer E195-E2','e195e2'),('ATR 72-600','atr72600'),
            ('Boeing 787-9','b7879'),('Cessna 408 SkyCourier','c408'),
        ):
            self.assertEqual(type_ratings.detect_model(title),model,title)
        for title in ('A320','Airbus A321','Boeing 737','A320 A321neo','Boeing 737 MAX 8 737-800',''):
            self.assertIsNone(type_ratings.detect_model(title),title)

    def test_training_requires_msfs_and_two_recorded_flights(self):
        conn=self.db.conn
        self.assertFalse(type_ratings.record_training(conn,'demo1',
            'Airbus A320neo',10,900,-145,0,msfs_verified=False))
        self.assertFalse(type_ratings.record_training(conn,'wrong',
            'Airbus A320neo',10,900,-145,1,msfs_verified=True))
        self.assertFalse(type_ratings.record_training(conn,'short',
            'Airbus A320neo',10,200,-145,0,msfs_verified=True))
        self.assertFalse(type_ratings.record_training(conn,'unverified_landing',
            'Airbus A320neo',10,900,None,0,msfs_verified=True))
        self.assertTrue(type_ratings.record_training(conn,'valid1',
            'Airbus A320neo',10,900,-145,0,msfs_verified=True))
        self.assertEqual(type_ratings.owned(self.db),set())
        self.assertFalse(type_ratings.record_training(conn,'valid1',
            'Airbus A320neo',10,900,-145,0,msfs_verified=True))
        self.assertTrue(type_ratings.record_training(conn,'valid2',
            'Airbus A320neo',1100,2100,-190,0,msfs_verified=True))
        self.assertEqual(type_ratings.owned(self.db),{'a320neo'})
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM airline_type_training").fetchone()[0],2)

    def test_employer_requires_type_rating_and_correct_available_model(self):
        stats={'level':99,'hours':200,'xp':100000,'flights':200}
        quals={'PPA','PCA','IFR','MLTE','PLA'}
        period=weekly_period(1800000000.)
        for company in ('azul','gol','latam'):
            vacancy=next(v for v in vacancies(period,'SBRF') if v.company==company)
            self.assertFalse(employment_eligibility(vacancy,stats,quals,set())[0])
            self.assertTrue(employment_eligibility(vacancy,stats,quals,{'a320neo'})[0])
            catalog=AirportCatalog(AIRPORTS)
            good=generate_employer_routes(company,AIRPORTS['SBRF'],catalog,stats,quals,
                {},period,ratings={'a320neo'},available={'a320neo'})
            self.assertTrue(good,company)
            self.assertTrue(all(m.employer_plane=='a320neo' for m in good))
            self.assertFalse(generate_employer_routes(company,AIRPORTS['SBRF'],
                catalog,stats,quals,{},period,ratings=set(),available={'a320neo'}))
            self.assertFalse(generate_employer_routes(company,AIRPORTS['SBRF'],
                catalog,stats,quals,{},period,ratings={'a320neo'},available={'c152'}))

    def test_salary_hierarchy(self):
        self.assertEqual(airline_operations.BASE_SALARY,
            {'nordeste':9000,'azul':30000,'gol':23000,'latam':17000})
        self.assertEqual(airline_operations.rate('azul',50,50)[0] >
                         airline_operations.rate('gol',50,50)[0],True)
        self.assertGreater(airline_operations.rate('gol',50,50)[0],
                           airline_operations.rate('latam',50,50)[0])
        self.assertGreater(airline_operations.rate('latam',50,50)[0],
                           airline_operations.rate('nordeste',50,50)[0])


class SettingsCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()

    def test_preferences_types_and_persistence(self):
        self.assertTrue(settings_center.read_global(self.root)['autoconnect'])
        settings_center.save_global(self.root,'autoconnect',False)
        settings_center.save_global(self.root,'interface_scale',125)
        self.assertEqual(settings_center.read_global(self.root)['interface_scale'],125)
        self.assertFalse(settings_center.read_global(self.root)['autoconnect'])
        for key,value in [('autoconnect','false'),('interface_scale',200),
                          ('interface_scale',True),('bad',True)]:
            with self.assertRaises(ValueError):
                settings_center.save_global(self.root,key,value)
        self.assertFalse(settings_center.read_global(self.root)['autoconnect'])

    def test_backup_sqlite_wal_and_restore_new_profile(self):
        profiles=ProfileManager(self.root)
        db=Storage(profiles.database())
        try:
            db.create_pilot('Piloto Oficial','TESTEX','SBRF')
            db.set_setting('balance','123456')
            db.conn.execute("INSERT INTO flights(started_utc,ended_utc,stall_warnings) VALUES(0,620,0)")
            db.conn.commit()
            app=SimpleNamespace(profiles=profiles,storage=db)
            archive=self.root/'backup.zip'
            self.assertEqual(settings_center.export_profiles(app,archive),1)
            with zipfile.ZipFile(archive) as z:
                self.assertIn('profiles/principal/carreira.db',z.namelist())
            self.assertEqual(len(settings_center.import_profiles(app,archive)),1)
            self.assertEqual(len(profiles.list()),2)
            self.assertEqual(db.get_setting('balance'),'123456')
            newest=next(p for p in profiles.list() if p['id']!='principal')
            imported=sqlite3.connect(profiles.database(newest['id']))
            try:
                self.assertEqual(imported.execute(
                    "SELECT value FROM settings WHERE key='balance'").fetchone()[0],
                    '123456')
                self.assertEqual(imported.execute("SELECT COUNT(*) FROM flights").fetchone()[0],1)
            finally:imported.close()
        finally:db.close()

    def test_backup_rejects_external_zip_entries(self):
        profiles=ProfileManager(self.root)
        db=Storage(profiles.database())
        try:
            db.create_pilot('Oficial','TESTXX','SBRF')
            app=SimpleNamespace(profiles=profiles,storage=db)
            bad=self.root/'malicious.zip'
            with zipfile.ZipFile(bad,'w') as z:
                z.writestr('manifest.json',json.dumps({
                    'format':'flightsim-settings-087','profiles':[]}))
                z.writestr('../out.txt','unsafe')
            with self.assertRaises(ValueError):
                settings_center.import_profiles(app,bad)
            self.assertEqual(len(profiles.list()),1)
        finally:db.close()

    def test_diagnostics_redacts_path_and_coordinates(self):
        raw=r'C:\Users\Pilot\Sensitive\file.txt lat=-8.123 lon=34.25'
        safe=settings_center.sanitize_log(raw)
        self.assertNotIn('Sensitive',safe)
        self.assertNotIn('-8.123',safe)
        self.assertNotIn('34.25',safe)


class UnlockQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Storage(Path(self.temp.name)/'carreira.db')
        self.db.create_pilot('Teste','TESTXX','SBRF')
    def tearDown(self):
        self.db.close();self.temp.cleanup()

    def test_events_are_queued_ordered_acknowledged_and_persisted(self):
        pilot_career.snapshot(self.db,{'kind':'official'})
        with self.db.conn:
            pilot_career.event(self.db,'test:unlock1',1500,'gain','first_flight','Primeiro voo')
            pilot_career.event(self.db,'test:unlock2',1501,'promotion','cabo','Nova patente')
        pending=pilot_career.snapshot(self.db,{'kind':'official'})['pending_unlocks']
        self.assertEqual(len(pending),2)
        first,second=[x['id'] for x in pending]
        with self.assertRaises(ValueError):
            pilot_career.acknowledge_event(self.db,second)
        self.assertTrue(pilot_career.acknowledge_event(self.db,first))
        self.assertEqual([x['id'] for x in
            pilot_career.snapshot(self.db,{'kind':'official'})['pending_unlocks']],[second])
        self.assertFalse(pilot_career.acknowledge_event(self.db,first))
        self.assertTrue(pilot_career.acknowledge_event(self.db,second))
        self.assertEqual(pilot_career.snapshot(self.db,{'kind':'official'})['pending_unlocks'],[])
