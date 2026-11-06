"""Perfis seguros e Pilot Career: idempotência, promoções e medalhas variáveis."""
import json
import tempfile
import unittest
from pathlib import Path

from aerocarreira.profiles import ProfileManager
from aerocarreira.storage import Storage
from aerocarreira.pilot_career import (
    rank_for_level, snapshot, set_showcase, equip, init
)
from aerocarreira.planning import Preflight, inspect_preflight
from aerocarreira.domain import MISSIONS


class ProfileManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.original=Storage(self.root/'carreira.db')
        self.original.create_pilot('Piloto original','BM2564','SBRF')
        self.original.set_setting('balance','26284')
        self.original.close()
        self.profiles=ProfileManager(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_existing_pilot_kept_in_place_and_backup_is_readable(self):
        self.assertEqual(self.profiles.active()['id'],'principal')
        self.assertTrue((self.root/'carreira.pre_profiles.backup.db').exists())
        self.assertEqual(self.profiles.database(),self.root/'carreira.db')
        db=Storage(self.profiles.database())
        self.assertEqual(db.get_pilot()['callsign'],'BM2564')
        self.assertEqual(db.get_setting('balance'),'26284')
        db.close()

    def test_create_switch_and_reset_isolated_test(self):
        created=self.profiles.create('Teste','TESTE','SBRF',test_admin=True)
        self.assertEqual(created['kind'],'test')
        self.assertNotEqual(self.profiles.database(created['id']),self.profiles.database())
        official=Storage(self.profiles.database())
        self.assertEqual(official.get_setting('balance'),'26284')
        official.close()
        self.profiles.switch(created['id'])
        test=Storage(self.profiles.database())
        self.assertEqual(test.get_pilot()['name'],'Teste')
        self.assertEqual(test.get_setting('pilot_test_guard_v1'),'1')
        test.set_setting('balance','99999')
        test.close()
        self.profiles.reset_test(created['id'])
        new=Storage(self.profiles.database())
        self.assertNotEqual(new.get_setting('balance'),'99999')
        self.assertEqual(new.get_pilot()['callsign'],'TESTE')
        new.close()
        self.profiles.switch('principal')
        original=Storage(self.profiles.database())
        self.assertEqual(original.get_setting('balance'),'26284')
        original.close()

    def test_reject_invalid_id_and_admin_outside_teste(self):
        with self.assertRaises(ValueError):
            self.profiles.create('Outro','OUTRO','SBRF',test_admin=True)
        with self.assertRaises(ValueError):
            self.profiles.switch('../../carreira.db')
        with self.assertRaises(ValueError):
            self.profiles.reset_test('principal')

    def test_other_official_profile_has_own_money_and_data(self):
        new=self.profiles.create('Segundo','SEGU2','SBRF')
        self.assertEqual(new['kind'],'official')
        db=Storage(self.profiles.database(new['id']))
        self.assertIsNone(db.get_setting('pilot_test_guard_v1'))
        self.assertEqual(db.pilot_stats()['flights'],0)
        db.close()


class PilotCareerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Storage(Path(self.temp.name)/'pilot.db')
        self.db.create_pilot('Teste','TESTE','SBRF')
        self.profile={'id':'01'*16,'kind':'test'}
        self.db.set_setting('pilot_test_guard_v1','1')

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def flight(self,count,*,reward=1000,stalls=0):
        with self.db.conn:
            latest=self.db.conn.execute(
                "SELECT COALESCE(MAX(ended_utc),0) FROM flights").fetchone()[0]
            for i in range(count):
                when=max(1000,latest)+(i+1)*3600
                self.db.conn.execute("""INSERT INTO flights
                 (started_utc,ended_utc,touchdown_fpm_est,stall_warnings,
                  mission_id,reward,aircraft_title)
                 VALUES(?,?,?,?,?,?,?)""",
                 (when-1200,when,-250,stalls,'REG-T' if reward else None,
                  reward,'Cessna 152'))

    def test_rank_hierarchy_and_range(self):
        self.assertEqual(rank_for_level(1)[0],'soldado2')
        self.assertEqual(rank_for_level(5)[0],'soldado1')
        self.assertEqual(rank_for_level(10)[0],'cabo')
        self.assertEqual(rank_for_level(70)[0],'brigadeiro')
        self.assertEqual(rank_for_level(100)[0],'marechal')

    def test_variable_badge_gains_breaks_and_recovers_once(self):
        self.flight(7)  # 50 + 7*(1 voo + 2 contrato) = 71
        s=snapshot(self.db,self.profile)
        medal=next(x for x in s['medals'] if x['code']=='reputation70')
        self.assertEqual(medal['status'],'earned')
        equip(self.db,self.profile,'reputation70',{'reputation70'})
        self.assertEqual(snapshot(self.db,self.profile)['equipped'],'reputation70')
        self.flight(1,reward=0,stalls=4)
        lost=snapshot(self.db,self.profile)
        self.assertEqual(next(x for x in lost['medals'] if x['code']=='reputation70')['status'],'locked')
        self.assertIsNone(lost['equipped'])
        self.assertTrue(any(e['kind']=='loss' and e['code']=='reputation70'
                            for e in lost['timeline']))
        seq=lost['events_seq']
        self.assertEqual(snapshot(self.db,self.profile)['events_seq'],seq)
        self.flight(10)
        back=snapshot(self.db,self.profile)
        self.assertEqual(next(x for x in back['medals'] if x['code']=='reputation70')['status'],'earned')
        self.assertEqual(back['equipped'],'reputation70')
        self.assertGreater(back['events_seq'],seq)

    def test_permanent_medals_not_lost_with_bad_landing(self):
        self.flight(1)
        self.assertEqual(next(x for x in snapshot(self.db,self.profile)['medals']
                              if x['code']=='first_flight')['status'],'earned')
        self.flight(1,reward=0,stalls=4)
        self.assertEqual(next(x for x in snapshot(self.db,self.profile)['medals']
                              if x['code']=='first_flight')['status'],'earned')

    def test_showcase_is_visual_and_never_changes_real_xp_or_money(self):
        before=(self.db.pilot_stats()['xp'],self.db.get_setting('balance'))
        payload={'level':90,'xp':500000,'reputation':99,'rank':'marechal',
                 'licenses':{'PLA':'earned','PPA':'locked'},
                 'achievements':{'veteran':'earned','reputation90':'available'}}
        set_showcase(self.db,self.profile,payload)
        s=snapshot(self.db,self.profile)
        self.assertEqual(s['rank']['code'],'marechal')
        self.assertEqual(s['level'],90)
        self.assertEqual(s['xp'],500000)
        self.assertEqual(next(x for x in s['licenses'] if x['code']=='PLA')['status'],'earned')
        self.assertEqual(next(x for x in s['medals'] if x['code']=='veteran')['status'],'earned')
        self.assertEqual(before,(self.db.pilot_stats()['xp'],self.db.get_setting('balance')))
        with self.assertRaises(ValueError):
            set_showcase(self.db,{'id':'principal','kind':'official'},payload)

    def test_audit_ignores_manual_flags_and_unverified_data(self):
        p=Preflight(MISSIONS[0].id,'Cessna 152',runway_checked=True,
                    route_checked=True,fuel_checked=True,payload_checked=True,
                    planned_fuel_gal=100,planned_weight_lbs=1800,max_weight_lbs=2500)
        self.assertEqual(inspect_preflight(MISSIONS[0],p)['bonus_fraction'],0)
        good=Preflight(MISSIONS[0].id,'Cessna 152',planned_fuel_gal=20,
                       planned_weight_lbs=1800,max_weight_lbs=2500)
        result=inspect_preflight(MISSIONS[0],good,verified={
            'clock':True,'assists':True,'fuel':True,'weight':True})
        self.assertTrue(result['weight_ok'])
        self.assertGreater(result['bonus_fraction'],.06)


if __name__=='__main__':unittest.main()
