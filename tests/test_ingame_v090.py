"""v0.9.0 InGame: read-only API, SDK structure and isolation contracts."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import urllib.request
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

from aerocarreira.ingame_bridge import PanelState, LocalPanelServer, PROTOCOL_VERSION, FONT_FILES, FONT_ROOT

ROOT = Path(__file__).resolve().parents[1]


class InGameFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / 'panel.html'
        path.write_text(
            '<meta name="flight-panel-key" content="__FLIGHTSIM_PANEL_KEY__">', encoding='utf-8'
        )
        self.state = PanelState()
        self.state.update(
            status='connected', mode='MSFS', phase='solo', balance=38720,
            aircraft='Cessna 152', telemetry={'ias_kt': 75},
            position={'lat': -8.12, 'lon': -34.92},
            mission={'origin': 'SBRF', 'destination': 'SIPE', 'reward': 1500},
            updated=100.0,
        )
        self.bridge = LocalPanelServer(self.state, port=0, page_path=path)
        self.port = self.bridge.start()
        self.base = 'http://127.0.0.1:' + str(self.port)

    def tearDown(self):
        self.bridge.stop()
        self.temp.cleanup()

    def request(self, path, method='GET', key=None, host=None):
        headers = {}
        if key is not None:
            headers['X-Flight-Panel-Key'] = key
        if host is not None:
            headers['Host'] = host
        req = urllib.request.Request(self.base + path, method=method, headers=headers)
        return urllib.request.urlopen(req, timeout=3)

    def test_versioned_read_authenticated_and_live(self):
        with self.request('/api/v1/status', key=self.bridge.read_key) as response:
            value = json.load(response)
            self.assertEqual(response.headers['Access-Control-Allow-Origin'], None)
        self.assertEqual(value['version'], PROTOCOL_VERSION)
        self.assertEqual(value['telemetry']['ias_kt'], 75)
        self.assertEqual(value['balance'], 38720)
        self.state.update(balance=39000)
        with self.request('/api/v1/status', key=self.bridge.read_key) as response:
            self.assertEqual(json.load(response)['balance'], 39000)

    def test_unauthed_read_and_mutations_denied(self):
        for path, method, key in [
            ('/api/v1/status', 'GET', None),
            ('/api/v1/status', 'GET', 'bad'),
            ('/api/v1/diagnostics', 'GET', None),
            ('/api/v1/status', 'POST', self.bridge.read_key),
            ('/api/status', 'PUT', None),
            ('/api/status', 'DELETE', None),
        ]:
            with self.subTest(path=path, method=method):
                with self.assertRaises(HTTPError) as exc:
                    self.request(path, method, key)
                self.assertIn(exc.exception.code, (403, 405))
        self.assertEqual(self.state.get()['balance'], 38720)

    def test_host_is_restricted_to_loopback_and_no_cors(self):
        with self.assertRaises(HTTPError) as exc:
            self.request('/api/v1/status', key=self.bridge.read_key,
                         host='attacker.example')
        self.assertEqual(exc.exception.code, 403)
        with self.request('/api/v1/health') as resp:
            health = json.load(resp)
            self.assertTrue(health['read_only'])
            self.assertEqual(health['protocol'], PROTOCOL_VERSION)
        with self.request('/api/v1/diagnostics', key=self.bridge.read_key) as resp:
            self.assertGreater(json.load(resp)['rejected'], 0)

    def test_ephemeral_key_in_response_never_static_package(self):
        with self.request('/') as resp:
            body = resp.read().decode('utf-8')
            self.assertIn(self.bridge.read_key, body)
            self.assertNotIn('__FLIGHTSIM_PANEL_KEY__', body)
            self.assertNotIn('Access-Control-Allow-Origin', str(resp.headers))
            self.assertNotIn('frame-ancestors', resp.headers.get('Content-Security-Policy',''))
        package_html = (ROOT / 'in_game/toolbar/PackageSources/html_ui/'
                        'InGamePanels/FlightCare/FlightCare.html').read_text(encoding='utf-8')
        self.assertNotIn(self.bridge.read_key, package_html)
        self.assertIn('http://127.0.0.1:8769/', package_html)
        self.assertNotIn('X-Flight-Token', package_html)
        self.assertNotIn('POST', package_html)
        self.assertNotEqual(
            LocalPanelServer(PanelState(), port=0, page_path=Path(self.temp.name)/'panel.html').read_key,
            self.bridge.read_key,
        )

    def test_bundled_pt_br_font_and_csp(self):
        for route, filename in FONT_FILES.items():
            with self.subTest(route=route):
                self.assertTrue((FONT_ROOT / filename).is_file())
                with self.request(route) as response:
                    raw = response.read()
                    self.assertEqual(response.headers['Content-Type'], 'font/ttf')
                    self.assertGreater(len(raw), 1000)
                    self.assertIn("font-src 'self'", response.headers['Content-Security-Policy'])
        # This fixture intentionally overrides the page with a tiny HTML
        # token template. Assert bundled production HTML separately.
        html = (ROOT / 'in_game' / 'flightcare_panel.html').read_text(encoding='utf-8')
        self.assertIn("font-family:'FlightSimBarlow'", html)
        self.assertIn('Visão geral', html)
        self.assertIn('Navegação', html)
        self.assertIn('Aeronave', html)

    def test_legacy_endpoint_and_no_directory_traversal(self):
        with self.request('/api/status') as resp:
            state = json.load(resp)
        self.assertEqual(state['balance'], 38720)
        self.assertNotIn('telemetry', state)
        for path in ('/../private', '/api/v1/status?debug=1', '/command'):
            with self.subTest(path=path):
                with self.assertRaises(HTTPError):
                    self.request(path, key=self.bridge.read_key)

    def test_package_xml_and_icons_are_self_contained(self):
        root = ROOT / 'in_game/toolbar'
        project = ET.parse(root / 'package.xml').getroot()
        package = ET.parse(root / 'PackageDefinitions/flightsimcarreira-panel.xml').getroot()
        definition = ET.parse(root / 'PackageSources/InGamePanels/flightsimcarreira-panel.xml').getroot()
        panel = definition.find('InGamePanels.InGamePanelDefinition')
        self.assertEqual(project.attrib['Version'], '2')
        self.assertEqual(package.attrib['Version'], '0.9.0')
        # A toolbar is a MISC *package*, with an SPB *asset group*.
        # UNKNOWN or SPB as ContentType blocks Build All on MSFS 2020.
        self.assertEqual(package.findtext('ItemSettings/ContentType'), 'MISC')
        self.assertEqual(sorted(g.findtext('Type') for g in package.findall('AssetGroups/AssetGroup')), ['Copy', 'SPB'])
        self.assertEqual(panel.attrib['id'], 'PANEL_FLIGHTSIMCARREIRA')
        self.assertEqual(panel.attrib['icon'], 'ICON_TOOLBAR_FLIGHTSIMCARREIRA')
        self.assertEqual(panel.attrib['buttonVisible'], 'true')
        self.assertEqual(panel.attrib['resizeDirections'].lower(), 'both')
        self.assertGreaterEqual(float(panel.attrib['minWidth']), 40)
        self.assertGreaterEqual(float(panel.attrib['minHeight']), 40)
        self.assertGreater(float(panel.attrib['defaultWidth']), float(panel.attrib['minWidth']))
        self.assertGreater(float(panel.attrib['defaultHeight']), float(panel.attrib['minHeight']))
        wrapper=(root/'PackageSources/html_ui/InGamePanels/FlightCare/FlightCare.html').read_text(encoding='utf-8')
        self.assertNotIn('content-fit=', wrapper)
        self.assertIn('id="flightSimFrame"', wrapper)
        wrapper_js = (root/'PackageSources/html_ui/InGamePanels/FlightCare/FlightCare.js').read_text(encoding='utf-8')
        self.assertIn("addEventListener('panelActive'", wrapper_js)
        self.assertNotIn("classList.add('draggable')", wrapper_js)
        self.assertIn("addEventListener('panelReady'", wrapper_js)
        self.assertIn("addEventListener('onResizeElement'", wrapper_js)
        self.assertIn("reportPanelGeometry('active')", wrapper_js)
        self.assertNotIn('html,body,ingamepanel-flightcare', wrapper)
        self.assertIn('height:100% !important', wrapper)
        self.assertIn('flex:1 1 auto !important', wrapper)
        self.assertTrue((root/'PackageSources'/panel.attrib['url']).exists())
        for folder in ('icons/toolbar','Textures/Menu/toolbar'):
            path = root / 'PackageSources/html_ui' / folder / (
                panel.attrib['icon'] + '.svg')
            self.assertTrue(path.is_file(), str(path))
            icon = ET.parse(path).getroot()
            self.assertEqual(icon.attrib['id'], 'Titre')
        html = (ROOT / 'in_game/flightcare_panel.html').read_text(encoding='utf-8')
        self.assertIn('__FLIGHTSIM_PANEL_KEY__', html)
        self.assertIn('/api/v1/status', html)
        for page_name in ('dashboard','route','aircraft','career'):
            self.assertIn('data-page="' + page_name + '"', html)
            self.assertIn('data-view="' + page_name + '"', html)
        self.assertIn('grid-template-columns:154px', html)
        self.assertIn('nav.side', html)
        self.assertNotIn("fetch('/command'", html)
        self.assertIn('/api/v2/commands', html)
        self.assertIn('__FLIGHTSIM_ACTION_KEY__', html)
        self.assertIn('data-view="market"', html)
        self.assertNotIn('MapLibre', html)


if __name__ == '__main__':
    unittest.main()
