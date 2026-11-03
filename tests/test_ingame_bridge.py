"""Read-only loopback for in-game web panel; no simulator needed."""
import json
import tempfile
import unittest
import urllib.request
from pathlib import Path
from aerocarreira.ingame_bridge import PanelState, LocalPanelServer

class PanelBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        path=Path(self.temp.name)/'panel.html'
        path.write_text('<html>FlightSimCarreira</html>',encoding='utf-8')
        self.state=PanelState()
        self.state.update(status='connected',balance=7740,phase='solo')
        self.bridge=LocalPanelServer(self.state,port=0,page_path=path)
        # autoport needs port-aware host check: server port assigned by OS
        self.bridge.start()
        self.port=self.bridge.server.server_address[1]
    def tearDown(self):
        self.bridge.stop();self.temp.cleanup()
    def test_status_loopback(self):
        req=urllib.request.Request(f'http://127.0.0.1:{self.port}/api/status')
        with urllib.request.urlopen(req,timeout=2) as rsp:
            data=json.load(rsp)
        self.assertEqual(data['balance'],7740)
    def test_no_post_mutation_and_no_directory_traversal(self):
        from urllib.error import HTTPError
        for target,method in [('/api/status','POST'),('/../../secrets','GET')]:
            req=urllib.request.Request(f'http://127.0.0.1:{self.port}{target}',method=method)
            with self.assertRaises(HTTPError): urllib.request.urlopen(req,timeout=2)
