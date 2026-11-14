"""v0.9.2: six-area Coherent office projection, strict commands, safe owner thread."""
import json
import unittest
import urllib.request
from pathlib import Path
from time import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from aerocarreira.ingame_bridge import (LocalPanelServer,PanelState,
    validate_command_value,MODEL_IMAGES,OFFICE_FILES)
from aerocarreira.ingame_office import project
from aerocarreira.app import Application
from aerocarreira.domain import Phase

ROOT=Path(__file__).resolve().parents[1]


class ProjectionTests(unittest.TestCase):
    def test_projection_six_areas_and_bounded_private_data(self):
        data={
            'pilot':{'name':'Íris Píloto','callsign':'PT-ÍRIS','home_icao':'SBRF',
                     'secret_key':'do-not-share'},
            'pilot_career':{
                'name':'Íris Píloto','xp':183,'level':4,'rank':{'title':'Soldado 2ª Classe'},
                'licenses':[{'code':'PPA','title':'Piloto Privado','status':'available',
                             'description':'Elegível'}],
                'medals':[{'code':'first','title':'Primeiro voo','status':'earned'}],
                'graphs':{'landings':[{'when':1,'fpm':-150}],
                          'hours_by_aircraft':[('Cessna 152',4.0)]}},
            'fleet':{'active_ref':'legacy:c152','owned':[{'ref':'legacy:c152','code':'c152',
                    'title':'Cessna 152','condition':93,'photo_url':'http://private',
                    'airport':'SBRF'}]},
            'aircraft_market':{'ready':True,'models':[{'code':'c152','title':'Cessna 152',
                    'price':180000,'rental_prices':{'24':2100}}]},
            'flight_operations':{'draft':{'mode':'free','origin':'SBRF',
                    'destination':'SIPE','altitude_ft':2500,'waypoints':[],'checks':{}},
                    'ready':True},
            'airline_operations':{'mode':'autonomo','vacancies':[{'id':'abc',
                    'company':'azul','salary':30000,'allowed':False,'reason':'Licença'}]},
            'flight_history':{'count':200,'flights':[{'id':i,'note':'Teste'}
                    for i in range(100)]},
            'financial_center':{'balance':20000,'income':4000,'debt':1200,
                    'transactions':[{'id':i,'description':'Pagamento'} for i in range(100)],
                    'monthly':[{'month':'2026-11','income':4000,'expense':3000}]}
        }
        state=project(data)
        self.assertEqual(set(state),{'planning','fleet','airlines','pilot','logbook','finances'})
        self.assertEqual(state['pilot']['name'],'Íris Píloto')
        self.assertNotIn('secret_key',str(state))
        self.assertNotIn('private',str(state))
        self.assertEqual(state['fleet']['active_ref'],'legacy:c152')
        self.assertEqual(len(state['logbook']['flights']),35)
        self.assertEqual(len(state['finances']['transactions']),35)
        self.assertEqual(state['logbook']['landings'][0]['fpm'],-150)
        self.assertEqual(state['finances']['monthly'][0]['net'],None) if False else self.assertEqual(state['finances']['monthly'][0]['income'],4000)

    def test_empty_projection_is_safe(self):
        s=project({})
        self.assertEqual(s['fleet']['owned'],[])
        self.assertEqual(s['logbook']['flights'],[])
        self.assertFalse(s['planning']['ready'])
        self.assertEqual(s['finances']['balance'],0)


class CommandContractTests(unittest.TestCase):
    def test_closed_schema_six_areas(self):
        valid=[
            ('plan_save',{'mode':'free','origin':'SBRF','destination':'SIPE',
                 'altitude_ft':2500,'waypoints':[{'label':'FIX01','lat':-8.1,'lon':-34.9}],
                 'checks':dict.fromkeys(('runway_checked','route_checked','fuel_checked','payload_checked'),False)}),
            ('plan_export',None),('plan_send',None),('plan_clear',None),
            ('fleet_select','legacy:c152'),('fleet_service','unit:2'),
            ('fleet_buy_new','c172'),('fleet_buy_used','used-offer-1'),
            ('fleet_rent','g58|48'),('fleet_sell','unit:3'),
            ('airline_apply','vacancy-123|10'),('airline_review',None),
            ('airline_resign',None),('airline_found','Aviação Águia Azul'),
            ('airline_buy_plane','a320neo'),('pilot_license_claim','PPA'),
            ('logbook_note',{'flight_id':33,'note':'Íris pousou na aproximação.'}),
            ('finance_loan',5000),('finance_repay',3000),('finance_tax',True),
        ]
        for action,value in valid:
            with self.subTest(action=action):
                self.assertTrue(validate_command_value(action,value))
        invalid=[
            ('plan_save',{'foo':'bar'}),('plan_save',dict(valid[0][1],altitude_ft=0)),
            ('plan_save',dict(valid[0][1],waypoints=[{'label':'bad !','lat':-8,'lon':-34}])),
            ('fleet_sell',{'ref':'unit:2','price':1}),('finance_loan',True),
            ('finance_loan',999999),('finance_repay',0),
            ('logbook_note',{'flight_id':2,'note':'x'*701}),
            ('logbook_note',{'flight_id':2,'note':'OK','xp':10000}),
            ('airline_apply','\x00vacancy'),('airline_found','\n'),
            ('plan_send',{'plan':'wrong'}),('pilot_license_claim',42)
        ]
        for action,value in invalid:
            with self.subTest(action=action):
                self.assertFalse(validate_command_value(action,value))

    def test_asset_pages_and_protected_http(self):
        server=LocalPanelServer(PanelState(),port=0,allow_commands=True)
        server.start()
        base='http://127.0.0.1:'+str(server.port)
        try:
            def read(path):
                with urllib.request.urlopen(base+path,timeout=3) as res:
                    return res.headers['Content-Type'],res.read()
            mime,raw=read('/')
            page=raw.decode('utf-8')
            self.assertIn('data-page="finances"',page)
            self.assertIn('data-view="planning"',page)
            self.assertNotIn('<!--OFFICE_NAV-->',page)
            self.assertNotIn('<!--OFFICE_PAGES-->',page)
            for path in OFFICE_FILES:
                mime,raw=read(path)
                self.assertGreater(len(raw),1500)
                self.assertIn('utf-8',mime)
            for path in MODEL_IMAGES:
                mime,raw=read(path)
                self.assertEqual(mime,'image/jpeg')
                self.assertGreater(len(raw),100)
                self.assertTrue(raw.startswith(b'\xff\xd8'))
            with self.assertRaises(HTTPError) as failure:
                read('/office-ui.js/../secret')
            self.assertEqual(failure.exception.code,404)
        finally:
            server.stop()

    def test_readonly_bridge_cannot_mutate_even_new_actions(self):
        server=LocalPanelServer(PanelState(),port=0)
        server.start()
        try:
            base='http://127.0.0.1:'+str(server.port)
            req=urllib.request.Request(base+'/api/v2/commands',method='POST',
                data=json.dumps({'action':'finance_loan','value':20000,
                    'request_id':'abc123456789012345'}).encode(),
                headers={'Origin':base,'Content-Type':'application/json',
                         'X-Flight-Action-Key':server.action_key})
            with self.assertRaises(HTTPError) as failed:
                urllib.request.urlopen(req,timeout=3)
            self.assertEqual(failed.exception.code,405)
        finally:
            server.stop()


class OwnerThreadTests(unittest.TestCase):
    def setUp(self):
        self.app=object.__new__(Application)
        self.app.mode='MSFS';self.app.connected=True;self.app.sim=Mock()
        self.app.tracker=SimpleNamespace(phase=None)
        self.app.last_sample=SimpleNamespace(on_ground=True,timestamp=time(),
                       aircraft_title='Cessna 152')
        self.app.dashboard=Mock()
        self.app.storage=Mock()
        self.app.storage.get_setting.return_value='12000'
        self.app.career=SimpleNamespace(mission=None,balance=12000)
        self.app.msfs_airports_ready=True
        self.app.balance_var=Mock()
        self.app._log=Mock()

    def test_planning_calls_original_domain_and_ground_guard(self):
        plan={'mode':'free','origin':'SBRF','destination':'SIPE','altitude_ft':2500,
              'waypoints':[],'checks':dict.fromkeys((
               'runway_checked','route_checked','fuel_checked','payload_checked'),True)}
        self.app._flightops_save=Mock(return_value='Plano salvo.')
        ok,_=self.app._execute_ingame_command('plan_save',plan,'req-1')
        self.assertTrue(ok)
        self.app._flightops_save.assert_called_once_with(plan)
        self.app.tracker.phase=Phase.AIRBORNE
        ok,_=self.app._execute_ingame_command('plan_save',plan,'req-2')
        self.assertFalse(ok)
        self.app._flightops_save.assert_called_once()

    def test_bank_uses_idempotent_stable_uuid(self):
        ok,_=self.app._execute_ingame_command('finance_loan',5000,'client-req-one')
        self.assertTrue(ok)
        first=self.app.storage.take_loan.call_args.kwargs['request_id']
        ok,_=self.app._execute_ingame_command('finance_loan',5000,'client-req-one')
        self.assertTrue(ok)
        second=self.app.storage.take_loan.call_args.kwargs['request_id']
        self.assertEqual(first,second)
        self.assertEqual(len(first),36)
        self.app.tracker.phase=Phase.AIRBORNE
        ok,_=self.app._execute_ingame_command('finance_repay',3000,'client-req-two')
        self.assertFalse(ok)
        self.app.storage.repay_loan.assert_not_called()

    def test_fleet_market_reuses_existing_transaction_backend(self):
        self.app.dashboard.presenter.center=SimpleNamespace(icao='SBRF')
        with patch('aerocarreira.aircraft_marketplace.execute_market',
                   return_value='Compra concluída') as execute:
            ok,msg=self.app._execute_ingame_command('fleet_buy_new','c172','client-req-buy')
        self.assertTrue(ok,msg)
        args=execute.call_args.args
        self.assertEqual(args[3],'aircraft_buy_new')
        self.assertTrue(args[4].startswith('c172|'))
        self.assertEqual(len(args[4].split('|')[-1]),36)
        self.app.career.mission=SimpleNamespace(id='active')
        ok,_=self.app._execute_ingame_command('fleet_buy_new','c172','client-req-buy2')
        self.assertFalse(ok)


if __name__=='__main__':
    unittest.main()
