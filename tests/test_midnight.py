"""Contracts for the presentation adapter and authenticated transport."""
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from queue import Empty
from unittest.mock import Mock, patch
from aerocarreira.storage import Storage
from aerocarreira.fuel import FuelManager
from aerocarreira.domain import Career, FlightTracker, MISSIONS, Phase
from aerocarreira.dashboard import DashboardPresenter, mission_data
from aerocarreira.midnight_server import DashboardServer, ASSETS
from aerocarreira.dashboard_controller import DashboardController

class PresenterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=Storage(Path(self.temp.name)/'career.db')
        self.app=SimpleNamespace(storage=self.db,fuel_manager=FuelManager(self.db),last_sample=None,
            airport_catalog=None,connected=False,mode='Desconectado',career=Career(),tracker=FlightTracker(),
            realism_frozen=0,status_var=Mock(get=lambda:'offline'),phase_var=Mock(get=lambda:'AGUARDANDO'),
            log_text=Mock(get=lambda *a:'real log\n'),_saved_preflight=lambda:None)
        self.presenter=DashboardPresenter(self.app)
    def tearDown(self):self.db.close();self.temp.cleanup()
    def pilot(self):self.db.create_pilot('Test Pilot','TEST01','SBRF');self.db.claim_starter();self.db.fleet_manager().select('legacy:c152')
    def test_empty_state_does_not_invent_pilot_aircraft_route_or_weather(self):
        s=self.presenter.snapshot();self.assertIsNone(s['pilot']);self.assertIsNone(s['mission']);self.assertIsNone(s['plane']);self.assertIsNone(s['telemetry']);self.assertEqual(s['offers'],[])
    def test_sqlite_balance_and_pilot_progress_update(self):
        self.pilot();self.db.set_setting('balance','12345');s=self.presenter.snapshot()
        self.assertEqual(s['balance'],12345);self.assertEqual(s['country'],'BR');self.assertIn('PPA',s['summary']['qualifications'])
        self.db.conn.execute("INSERT INTO pilot_xp_ledger(flight_key,xp,awarded_utc) VALUES('test',400,1)");self.db.conn.commit()
        changed=self.presenter.snapshot();self.assertGreater(changed['progress']['level'],s['progress']['level']);self.assertNotEqual(changed['progress']['fraction'],s['progress']['fraction'])
    def test_no_external_market_while_msfs_airports_not_confirmed(self):
        self.app.mode='MSFS'
        self.app.connected=True
        self.pilot()
        self.assertEqual(self.presenter.snapshot()['offers'],[])
        self.assertFalse(self.presenter.snapshot()['airports']['ready'])

    def test_market_comes_from_persistent_generator(self):
        self.app.mode='Demo'  # Catálogo embutido permitido SOMENTE na demonstração
        self.pilot();s=self.presenter.snapshot();self.assertTrue(s['offers'])
        ids={m.id for m in self.db.active_offers('SBRF')};self.assertTrue(all(o['id'] in ids for o in s['offers']))
    def test_legacy_route_uses_real_airport_coordinates(self):
        m=mission_data(MISSIONS[0]);self.assertAlmostEqual(m['start'][0],-8.126388889);self.assertGreater(m['distance'],20)
        self.app.career.accept(MISSIONS[0]);self.assertEqual(self.presenter.snapshot()['mission']['id'],MISSIONS[0].id)
    def test_fuel_is_only_reported_from_inventory(self):
        self.pilot();s=self.presenter.snapshot();self.assertIsNone(s['fuel']['quantity'])
        self.app.fuel_manager.observe('legacy:c152','c152',{'LEFT_MAIN':8,'RIGHT_MAIN':8},16,True,{'LEFT_MAIN':13,'RIGHT_MAIN':13})
        s=self.presenter.snapshot();self.assertEqual(s['fuel']['quantity'],16)
    def test_operating_result_includes_prepaid_fuel_and_excludes_loans(self):
        self.pilot()
        self.db.take_loan(1000)
        self.app.fuel_manager.observe('legacy:c152','c152',{'LEFT_MAIN':8,'RIGHT_MAIN':8},16,True,{'LEFT_MAIN':13,'RIGHT_MAIN':13})
        paid=self.app.fuel_manager.refuel_full('legacy:c152')
        summary=self.presenter.snapshot()['summary']
        self.assertEqual(summary['net'],-paid['cost_brl'])
        self.assertNotEqual(summary['net'],int(self.db.get_setting('balance')))

    def test_webview_failure_opens_complete_classic_fallback(self):
        controller=object.__new__(DashboardController)
        controller.closed=False;controller.fallback=False;controller.app=Mock()
        controller.process=Mock(returncode=1);controller.process.poll.return_value=1
        controller.presenter=Mock();controller.server=Mock()
        controller.server.commands.get_nowait.side_effect=Empty
        with patch('aerocarreira.dashboard_controller.messagebox.showerror'):
            controller.tick()
        self.assertTrue(controller.fallback)
        controller.app.root.deiconify.assert_called_once()

    def test_close_can_be_retried_after_checkpoint_failure(self):
        from aerocarreira.app import Application
        app=object.__new__(Application)
        app._checkpoint=Mock(side_effect=[OSError('disk full'),None])
        app.bridge=Mock();app.sim=Mock();app.storage=Mock();app.root=Mock();app.dashboard=None
        with self.assertRaises(OSError):app._close()
        self.assertFalse(getattr(app,'_closing',False))
        app._close();app.storage.close.assert_called_once()

    def test_telemetry_poll_does_not_rescan_world_airports_each_frame(self):
        from aerocarreira.demo import demo_samples
        from aerocarreira.domain import AIRPORTS
        self.pilot();self.app.mode='Demo';self.app.connected=True;self.app.last_sample=demo_samples()[0]
        from aerocarreira.contracts import AirportCatalog
        self.app.airport_catalog=Mock(wraps=AirportCatalog(locations=AIRPORTS),locations=AIRPORTS)
        self.app.airport_catalog.nearest.return_value=AIRPORTS['SBRF']
        for _ in range(5):self.presenter.snapshot()
        self.app.airport_catalog.nearest.assert_called_once()

    def test_frozen_bonus_is_reported(self):
        self.pilot();self.app.career.accept(MISSIONS[0]);self.app.tracker.phase=Phase.AIRBORNE;self.app.realism_frozen=.18
        s=self.presenter.snapshot();self.assertEqual(s['bonus']['bonus_fraction'],.18);self.assertTrue(s['bonus']['frozen'])
    def test_avatar_is_local_image_not_path_in_snapshot(self):
        self.pilot();path=Path(self.temp.name)/'avatar.png';path.write_bytes(b'png-for-presentation-test');self.db.set_setting('pilot_avatar_v1',str(path))
        s=self.presenter.snapshot();self.assertTrue(s['avatar'].startswith('data:image/png;base64,'));self.assertNotIn(str(path),json.dumps(s))
    def test_fuel_toggle_blocked_airborne(self):
        self.app.tracker.phase=Phase.AIRBORNE
        controller=object.__new__(DashboardController);controller.app=Mock()
        controller.app.storage=self.db;controller.app.tracker=self.app.tracker
        old=self.db.get_setting('fuel_control_enabled')
        with patch('aerocarreira.dashboard_controller.messagebox.showwarning') as warning:
            controller.dispatch({'action':'fuel'});warning.assert_called_once()
        self.assertEqual(self.db.get_setting('fuel_control_enabled'),old)
    def test_offer_confirmed_in_webview_skips_invisible_tk_confirmation(self):
        self.app.mode='Demo'
        self.pilot()
        self.presenter.refresh_market()
        offer=next(iter(self.presenter.offers.values()))
        controller=object.__new__(DashboardController)
        app=Mock()
        app.storage=self.db
        controller.app=app
        controller.presenter=self.presenter
        with patch('aerocarreira.dashboard_controller.messagebox.askyesno') as ask:
            controller.dispatch({'action':'offer','id':offer.id})
            ask.assert_not_called()
        app._accept_specific.assert_called_once_with(offer)

    def test_native_navigation_has_separate_market_pages_and_compact_satellite_credits(self):
        html=(ASSETS/'index.html').read_text(encoding='utf-8')
        js=(ASSETS/'app.js').read_text(encoding='utf-8')
        css=(ASSETS/'style.css').read_text(encoding='utf-8')
        self.assertIn('id="market-page"',html)
        self.assertIn('data-market-view="regional"',html)
        self.assertIn('data-market-view="freelance"',html)
        self.assertIn("['globe','Mercado','regional']",js)
        self.assertNotIn("['plane','Mercado Freelancer','freelance']",js)
        self.assertIn('id="detail-map-slot"',html)
        self.assertIn('mountSharedMap(view',js)
        self.assertIn('function headingDisplay(t)',js)
        self.assertIn('id="module-page"',html)
        self.assertNotIn('<dialog id="market-dialog"',html)
        self.assertIn('function navigate(destination)',js)
        self.assertIn('Boolean(o.freelance)===freelance',js)
        self.assertIn('id="satellite-credit" class="satellite-credit"',html)
        self.assertIn('EOX IT Services GmbH',html)
        self.assertIn('.workspace:not([data-view="dashboard"])',css)

    def test_finance_window_command_calls_existing_handler(self):
        app=Mock();controller=object.__new__(DashboardController);controller.app=app;controller.closed=False
        app.root.winfo_children.return_value=[]
        controller.dispatch({'action':'finance'});app._finance_window.assert_called_once()

class TransportTests(unittest.TestCase):
    def setUp(self):self.server=DashboardServer();self.server.publish({'balance':17});self.server.start()
    def tearDown(self):self.server.stop()
    def request(self,path='/state',data=None,auth=True,origin=True,host=None):
        headers={'X-Flight-Token':self.server.token} if auth else {}
        if origin:headers['Origin']=self.server.origin
        if host:headers['Host']=host
        if data is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(self.server.origin+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=3) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:return e.code,e.read()
    def test_loopback_and_authenticated_read(self):
        self.assertEqual(self.server.server.server_address[0],'127.0.0.1');self.assertEqual(self.request()[0],200);self.assertEqual(self.request(auth=False)[0],403)
    def test_foreign_origin_missing_token_and_dns_rebinding_blocked(self):
        self.assertEqual(self.request('/command',{'action':'fuel'},auth=False)[0],403)
        self.assertEqual(self.request('/command',{'action':'fuel'},origin=False)[0],403)
        self.assertEqual(self.request(host='attacker.example')[0],403)
    def test_command_queue_no_financial_parameters(self):
        self.assertEqual(self.request('/command',{'action':'finance'})[0],202)
        self.assertEqual(self.server.commands.get_nowait(),{'action':'finance'})
        self.assertEqual(self.request('/command',{'action':'finance','amount':9999})[0],400)
        self.assertEqual(self.request('/command',{'action':'eval'})[0],400)
    def test_bounded_queue_and_no_path_traversal(self):
        for _ in range(32):self.server.commands.put({'action':'settings'})
        self.assertEqual(self.request('/command',{'action':'settings'})[0],429)
        self.assertEqual(self.request('/../storage.py')[0],404)
    def test_aircraft_market_routes_are_allowlisted_and_authenticated(self):
        self.assertEqual(self.request('/aircraft-market.js')[0],200)
        code,body=self.request('/')
        self.assertEqual(code,200)
        self.assertIn(b'id="aircraft-market-page"',body)
        self.assertIn(b'id="aircraft-checkout-dialog"',body)
        command={'action':'aircraft_buy_new','id':'c152|f0c7c7f3-3e4a-4d7b-9538-aea2b43ff5fd'}
        self.assertEqual(self.request('/command',command)[0],202)
        self.assertEqual(self.server.commands.get_nowait(),command)
        self.assertEqual(self.request('/command',command,auth=False)[0],403)
        self.assertEqual(self.request('/command',command,origin=False)[0],403)
        self.assertEqual(self.request('/command',{'action':'aircraft_buy_new','id':None})[0],400)
        self.assertEqual(self.request('/command',{'action':'aircraft_rewrite_balance','id':'1'})[0],400)

    def test_custom_fleet_photo_precedes_catalog_showcase(self):
        js=(ASSETS/'app.js').read_text(encoding='utf-8')
        self.assertIn("if(plane?.photo_url)return {src:plane.photo_url,kind:'custom'}",js)
        for code in ('c172','g58','kingair','cj4'):
            self.assertIn(code+":'/market-"+code+".jpg'",js)
        self.assertIn("kind:'showcase'",js)

    def test_offline_aircraft_showcase_photos_are_allowlisted(self):
        from io import BytesIO
        from PIL import Image
        for model in ('c172','g58','kingair','cj4'):
            with self.subTest(model=model):
                status,body=self.request('/market-'+model+'.jpg')
                self.assertEqual(status,200)
                self.assertTrue(body.startswith(b'\xff\xd8\xff'))
                self.assertGreater(len(body),15000)
                with Image.open(BytesIO(body)) as photo:
                    self.assertEqual(photo.format,'JPEG')
                    self.assertGreaterEqual(photo.width,1000)
                    self.assertGreaterEqual(photo.height,700)
        self.assertEqual(self.request('/market-invalid.jpg')[0],404)
        self.assertEqual(self.request('/market-c172.svg')[0],404)

    def test_flight_operations_is_native_and_same_map(self):
        html=(ASSETS/'index.html').read_text(encoding='utf-8')
        js=(ASSETS/'app.js').read_text(encoding='utf-8')
        planner=(ASSETS/'flight-operations.js').read_text(encoding='utf-8')
        self.assertIn('id="flightops-page"',html)
        self.assertIn('id="flightops-map-slot"',html)
        self.assertIn('id="fo-waypoints"',html)
        self.assertIn('id="fo-check-payload"',html)
        self.assertIn("const parent=view==='planning'",js)
        self.assertIn("window.FSCFlightOps?.render(s)",js)
        self.assertIn("flightops_save",planner)
        self.assertIn("flightops_export",planner)
        self.assertIn("flightops_send",planner)

    def test_flightops_transport_requires_token_and_does_not_allow_extra_fields(self):
        self.assertEqual(self.request('/flight-operations.js')[0],200)
        payload={"mode":"free","origin":"SIPE","destination":"SIFC",
                 "altitude_ft":2500,"waypoints":[],
                 "checks":{"route_checked":False,"runway_checked":False,
                           "fuel_checked":False,"payload_checked":False}}
        request={"action":"flightops_save","payload":payload}
        self.assertEqual(self.request('/command',request)[0],202)
        self.assertEqual(self.server.commands.get_nowait(),request)
        self.assertEqual(self.request('/command',request,auth=False)[0],403)
        self.assertEqual(self.request('/command',request,origin=False)[0],403)
        self.assertEqual(self.request('/command',{**request,"amount":500})[0],400)
        self.assertEqual(self.request('/command',{"action":"flightops_save","payload":{}})[0],400)
        self.assertEqual(self.request('/command',{"action":"flightops_send"})[0],202)
        self.assertEqual(self.request('/flight-operations.py')[0],404)

    def test_pilot_career_is_native_and_local_asset(self):
        html=(ASSETS/'index.html').read_text(encoding='utf-8')
        js=(ASSETS/'app.js').read_text(encoding='utf-8')
        profile=(ASSETS/'pilot-career.js').read_text(encoding='utf-8')
        self.assertIn('id="pilot-career-page"',html)
        self.assertIn('id="pc-admin-rank-gallery"',html)
        self.assertIn('id="pc-unlock"',html)
        self.assertIn('id="pc-unlock-dismiss"',html)
        self.assertNotIn('id="pc-rank-fallback"',html)
        self.assertIn("case 'first_plane':",profile)
        self.assertIn("case 'three_planes':",profile)
        self.assertIn('CONQUISTA RECUPERADA',profile)
        self.assertNotIn('showUnlock.timeout=window.setTimeout',profile)
        self.assertIn("view==='pilot'",js)
        self.assertIn("window.FSCPilotCareer?.render(s)",js)
        self.assertIn("pc-fragment-left",profile)
        self.assertEqual(self.request('/pilot-career.js')[0],200)
        self.assertEqual(self.request('/profiles.py')[0],404)

    def test_pilot_transport_auth_and_showcase_payload(self):
        payload={'level':1,'xp':0,'reputation':50,'rank':None,'licenses':{},'achievements':{}}
        cmd={'action':'pilot_showcase','payload':payload}
        self.assertEqual(self.request('/command',cmd)[0],202)
        self.assertEqual(self.request('/command',cmd,auth=False)[0],403)
        self.assertEqual(self.request('/command',cmd,origin=False)[0],403)
        self.assertEqual(self.request('/command',{'action':'pilot_showcase','id':'admin'})[0],400)
        self.assertEqual(self.request('/command',{'action':'pilot_profile_switch','id':'principal'})[0],202)
        self.assertEqual(self.request('/command',{'action':'flightops_clear'})[0],202)

    def test_static_page_contains_no_session_token(self):
        code,body=self.request('/');self.assertEqual(code,200);self.assertNotIn(self.server.token.encode(),body)
        self.assertIn(b'<img src="/brand-icon.png"',body)
        self.assertNotIn(b'<span class="logo"><svg>',body)

    def test_approved_brand_icon_served_by_local_app(self):
        code,body=self.request('/brand-icon.png')
        self.assertEqual(code,200)
        self.assertTrue(body.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertGreater(len(body),100)

if __name__=='__main__':unittest.main()
