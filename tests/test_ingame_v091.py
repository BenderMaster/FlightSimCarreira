"""v0.9.1: authenticated InGame commands and owner-thread validation."""
import json
import unittest
import urllib.request
from urllib.error import HTTPError
from queue import Empty
from time import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

from aerocarreira.ingame_bridge import LocalPanelServer, PanelState
from aerocarreira.app import Application
from aerocarreira.domain import Phase


class CommandBridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = LocalPanelServer(PanelState(), port=0, allow_commands=True)
        self.port = self.bridge.start()
        self.url = 'http://127.0.0.1:' + str(self.port)

    def tearDown(self):
        self.bridge.stop()

    def request(self, path, data=None, key=True, origin=True, content_type='application/json'):
        headers = {'X-Flight-Action-Key': self.bridge.action_key} if key else {}
        if origin:
            headers['Origin'] = self.url
        if data is not None:
            headers['Content-Type'] = content_type
            data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(self.url+path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status, response.read(), response.headers
        except HTTPError as exc:
            return exc.code, exc.read(), exc.headers

    def payload(self, action='offer_accept', value='offer-001', request_id='abc1234567890xyz'):
        return {'action':action,'value':value,'request_id':request_id}

    def test_icon_and_ephemeral_write_capability(self):
        code, image, headers = self.request('/brand-icon.png')
        self.assertEqual(code,200)
        self.assertTrue(image.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(headers['Content-Type'], 'image/png')
        with urllib.request.urlopen(self.url+'/',timeout=3) as response:
            page = response.read().decode('utf-8')
        self.assertIn(self.bridge.action_key,page)
        self.assertNotIn('__FLIGHTSIM_WRITABLE__',page)
        self.assertIn('content="true"',page)
        code, data, _ = self.request('/api/v1/health')
        self.assertEqual(code,200)
        self.assertFalse(json.loads(data)['read_only'])

    def test_queue_receipt_and_idempotent_retry(self):
        payload=self.payload()
        code, body, _ = self.request('/api/v2/commands',payload)
        self.assertEqual(code,202)
        self.assertEqual(json.loads(body)['status'],'pending')
        code, _, _ = self.request('/api/v2/commands',payload)
        self.assertEqual(code,202)
        self.assertEqual(self.bridge.commands.get_nowait(),(
            payload['request_id'],'offer_accept','offer-001'))
        with self.assertRaises(Empty):
            self.bridge.commands.get_nowait()
        receipt='/api/v2/commands/'+payload['request_id']
        self.assertEqual(json.loads(self.request(receipt)[1])['status'],'pending')
        self.bridge.finish_command(payload['request_id'],True,'Contrato aceito')
        done=json.loads(self.request(receipt)[1])
        self.assertEqual(done['status'],'accepted')
        self.assertEqual(done['message'],'Contrato aceito')
        self.bridge.finish_command(payload['request_id'],False,'not allowed')
        self.assertEqual(json.loads(self.request(receipt)[1])['status'],'accepted')
        self.assertEqual(self.request('/api/v2/commands',self.payload(value='new offer'))[0],409)

    def test_bounded_schema_and_csrf(self):
        examples=[
            self.payload(action='system_command'),
            self.payload(value={'reward':100000}),
            self.payload(action='fuel_toggle',value='true'),
            self.payload(action='fuel_refuel',value=True),
            self.payload(action='fuel_refuel',value=-1),
            self.payload(action='fuel_refuel',value=3000),
            {**self.payload(), 'price':1},
            self.payload(request_id='tiny'),
        ]
        for data in examples:
            with self.subTest(data=data):
                self.assertEqual(self.request('/api/v2/commands',data)[0],400)
        self.assertEqual(self.request('/api/v2/commands',self.payload(),key=False)[0],403)
        self.assertEqual(self.request('/api/v2/commands',self.payload(),origin=False)[0],403)
        self.assertEqual(self.request('/api/v2/commands',self.payload(),content_type='text/plain')[0],403)
        self.assertEqual(self.request('/api/v2/commands/abc1234567890xyz',key=False)[0],403)
        with self.assertRaises(Empty):
            self.bridge.commands.get_nowait()
        self.assertEqual(self.request('/command',self.payload())[0],405)

    def test_readonly_fixture_remains_readonly(self):
        standalone=LocalPanelServer(PanelState(),port=0)
        standalone.start()
        try:
            url='http://127.0.0.1:'+str(standalone.port)
            req=urllib.request.Request(url+'/api/v2/commands',
                data=json.dumps(self.payload()).encode(),
                headers={'Content-Type':'application/json','Origin':url,
                         'X-Flight-Action-Key':standalone.action_key})
            with self.assertRaises(HTTPError) as result:
                urllib.request.urlopen(req,timeout=3)
            self.assertEqual(result.exception.code,405)
        finally:
            standalone.stop()


class ApplicationCommandTests(unittest.TestCase):
    def setUp(self):
        self.app=object.__new__(Application)
        self.app.mode='MSFS'
        self.app.connected=True
        self.app.sim=Mock()
        self.app.tracker=SimpleNamespace(phase=None)
        self.app.last_sample=SimpleNamespace(on_ground=True,timestamp=time(),
            aircraft_title='Cessna 152',total_weight_lbs=None,max_gross_weight_lbs=None)
        self.app.dashboard=Mock()
        self.app.storage=Mock()
        self.app.career=SimpleNamespace(mission=None,balance=10000)
        self.app.msfs_airports_ready=True
        self.app._log=Mock()
        self.app.balance_var=Mock()
        self.app.fuel_manager=Mock()

    def test_accept_valid_offer_and_deny_disconnected_or_airborne(self):
        offer=SimpleNamespace(id='offer-001')
        self.app.dashboard.presenter.offers={'offer-001':offer}
        self.app.storage.contract_completed.return_value=False
        self.app.storage.get_pilot.return_value={'name':'QA'}
        self.app._accept_specific=Mock(return_value=True)
        with patch('aerocarreira.app.eligibility',return_value=(True,'')):
            ok,msg=self.app._execute_ingame_command('offer_accept','offer-001')
            self.assertTrue(ok,msg)
            self.app._accept_specific.assert_called_once_with(offer, interactive=False)
            self.app.connected=False
            ok,_=self.app._execute_ingame_command('offer_accept','offer-001')
            self.assertFalse(ok)
            self.app.connected=True
            self.app.tracker.phase=Phase.AIRBORNE
            ok,_=self.app._execute_ingame_command('offer_accept','offer-001')
            self.assertFalse(ok)
            self.app._accept_specific.assert_called_once()

    def test_prepare_cancel_requires_current_mission(self):
        self.app.career.mission=SimpleNamespace(id='flight-123')
        self.app._prepare_active_plan=Mock(return_value=True)
        self.app._queue_payload_load=Mock(return_value=True)
        self.app._checkpoint=Mock()
        self.app._cancel=Mock()
        ok,_=self.app._execute_ingame_command('dispatch_prepare','stale')
        self.assertFalse(ok)
        ok,_=self.app._execute_ingame_command('dispatch_prepare','flight-123')
        self.assertTrue(ok)
        self.app._prepare_active_plan.assert_called_once_with(automatic=True)
        self.app._checkpoint.assert_called_once_with(force=True)
        ok,_=self.app._execute_ingame_command('mission_cancel','flight-123')
        self.assertTrue(ok)
        self.app._cancel.assert_called_once()

    def test_fuel_guard_and_request_to_existing_manager(self):
        self.app.storage.fleet_manager.return_value.selected.return_value={
            'ref':'legacy:c152','code':'c152','title':'Cessna 152'}
        self.app.storage.get_setting.return_value='9880'
        self.app.fuel_manager.get.return_value=None
        tanks={'LEFT_MAIN':10.0,'RIGHT_MAIN':10.0}
        self.app.fuel_manager.change_liters.return_value={
            'tanks':tanks,'target_liters':75,'cost_brl':120}
        ok,msg=self.app._execute_ingame_command('fuel_refuel',75)
        self.assertTrue(ok,msg)
        self.app.fuel_manager.change_liters.assert_called_once_with('legacy:c152',75)
        self.app.sim.request_fuel_restore.assert_called_once_with(tanks)
        self.assertEqual(self.app.career.balance,9880)
        self.app.last_sample.aircraft_title='Cessna 172'
        ok,_=self.app._execute_ingame_command('fuel_refuel',80)
        self.assertFalse(ok)
        self.app.fuel_manager.change_liters.assert_called_once()

    def test_rejected_ingame_contract_does_not_open_tk_dialog(self):
        from aerocarreira.domain import MISSIONS
        app=self.app
        app.mode='Desconectado'
        app.storage.get_pilot.return_value=None
        app.airport_catalog=None
        app.msfs_airports_ready=False
        app._ingame_last_error=None
        with patch('aerocarreira.app.strict_mission', return_value=MISSIONS[0]), \
             patch('aerocarreira.app.messagebox.showwarning') as warning:
            ok=app._accept_specific(MISSIONS[0],interactive=False)
            self.assertFalse(ok)
            warning.assert_not_called()
            self.assertTrue(app._ingame_last_error)
