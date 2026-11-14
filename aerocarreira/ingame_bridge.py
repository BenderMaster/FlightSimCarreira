"""Ponte InGame read-only: no simulator commands, no career mutations.

The toolbar loads a *same-origin iframe* at 127.0.0.1:8769. An ephemeral
capability is injected into the served HTML (never into the Community package).
This is defense in depth for reads, not authentication for financial actions.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock, Thread
from queue import Queue, Full
import re
from time import time
import hmac
import json
import secrets

DEFAULT_PORT = 8769
PROTOCOL_VERSION = 2
# Fonts are bundled with the existing Midnight Ops Windows distribution.
# Coherent GT does not necessarily see host-system fonts (e.g. Segoe UI).
FONT_ROOT = Path(__file__).resolve().parent / 'midnight' / 'fonts'
BRAND_ICON = FONT_ROOT.parent / 'brand-icon.png'
ALLOWED_ACTIONS = {'offer_accept', 'mission_cancel', 'dispatch_prepare', 'market_refresh',
                   'fuel_toggle', 'fuel_refuel',
                   'plan_save','plan_export','plan_send','plan_clear',
                   'fleet_select','fleet_service','fleet_buy_new','fleet_buy_used',
                   'fleet_rent','fleet_sell','fleet_insurance',
                   'airline_apply','airline_review','airline_resign','airline_found','airline_buy_plane',
                   'pilot_license_claim','logbook_note',
                   'finance_loan','finance_repay','finance_tax'}
REQUEST_ID = re.compile(r'^[A-Za-z0-9_-]{16,64}$')
FONT_FILES = {
    '/fonts/BarlowSemiCondensed-Regular.ttf': 'BarlowSemiCondensed-Regular.ttf',
    '/fonts/BarlowSemiCondensed-SemiBold.ttf': 'BarlowSemiCondensed-SemiBold.ttf',
}
# Existing showcase photographs, packaged with the Windows app. Never accept
# filesystem paths from the iframe or fetch remote content.
OFFICE_FILES = {
 '/office-ui.js':('office-ui.js','application/javascript; charset=utf-8'),
 '/office-ui.css':('office-ui.css','text/css; charset=utf-8')
}
MODEL_IMAGES = {
    '/media/c172.jpg': 'market-c172.jpg',
    '/media/g58.jpg': 'market-g58.jpg',
    '/media/kingair.jpg': 'market-kingair.jpg',
    '/media/cj4.jpg': 'market-cj4.jpg',
}


def validate_command_value(action, value):
    """Closed per-command schema: browser may express intent, never price or XP.

    Final domain validation always runs later on the Tk owner thread.
    """
    if action == 'airline_found':
        return type(value) is str and 3 <= len(value) <= 50 and not any(
            ord(ch) < 32 or ord(ch) == 127 for ch in value)
    if action in ('offer_accept','mission_cancel','dispatch_prepare',
                  'fleet_select','fleet_service','fleet_buy_new','fleet_buy_used',
                  'fleet_rent','fleet_sell','fleet_insurance','airline_apply','airline_found',
                  'airline_buy_plane','pilot_license_claim'):
        return type(value) is str and 1 <= len(value) <= 110 and all(
            32 <= ord(c) <= 126 for c in value)
    if action in ('fuel_toggle','finance_tax'):
        return type(value) is bool
    if action == 'fuel_refuel':
        return type(value) in (float,int) and 0 <= value <= 2000 and value == value
    if action in ('finance_loan','finance_repay'):
        return type(value) is int and 1 <= value <= 500000
    if action == 'logbook_note':
        return type(value) is dict and set(value) == {'flight_id','note'} and (
            type(value['flight_id']) is int and 1 <= value['flight_id'] <= 10000000 and
            type(value['note']) is str and len(value['note']) <= 700)
    if action == 'plan_save':
        if type(value) is not dict or set(value) != {
                'mode','origin','destination','altitude_ft','waypoints','checks'}:
            return False
        if (value['mode'] not in ('free','contract') or
                type(value['origin']) is not str or type(value['destination']) is not str or
                not all(re.fullmatch('[A-Z0-9]{4}',v or '') for v in (
                    value['origin'], value['destination'])) or
                type(value['altitude_ft']) is not int or not 500 <= value['altitude_ft'] <= 45000 or
                type(value['waypoints']) is not list or len(value['waypoints']) > 8 or
                type(value['checks']) is not dict):
            return False
        if set(value['checks']) != {'runway_checked','route_checked','fuel_checked','payload_checked'} or not all(
                type(x) is bool for x in value['checks'].values()):
            return False
        for waypoint in value['waypoints']:
            if (type(waypoint) is not dict or set(waypoint) != {'label','lat','lon'} or
                    type(waypoint['label']) is not str or not re.fullmatch('[A-Z0-9_-]{1,12}',waypoint['label']) or
                    type(waypoint['lat']) not in (int,float) or type(waypoint['lon']) not in (int,float) or
                    not -90 <= waypoint['lat'] <= 90 or not -180 <= waypoint['lon'] <= 180):
                return False
        return True
    return value is None


class PanelState:
    def __init__(self):
        self.lock = RLock()
        self.state = {
            'version': PROTOCOL_VERSION, 'status': 'offline',
            'phase': 'aguardando', 'balance': 0, 'mission': None,
            'position': None, 'aircraft': None, 'fuel_gallons': None,
            'telemetry': None, 'remaining_nm': None, 'mode': None,
            'updated': None,
        }

    def update(self, **fields):
        with self.lock:
            self.state.update(fields)

    def get(self):
        with self.lock:
            # Never expose a mutable reference shared with the Tk owner thread.
            return dict(self.state)


class LocalPanelServer:
    """Loopback-only, single-purpose, read-only companion to the toolbar."""

    def __init__(self, state: PanelState, port: int = DEFAULT_PORT,
                 page_path: Path | None = None, allow_commands: bool = False):
        self.state = state
        self.page_path = page_path or (
            Path(__file__).resolve().parent.parent / 'in_game' / 'flightcare_panel.html'
        )
        self.port = port
        self.read_key = secrets.token_urlsafe(32)
        self.action_key = secrets.token_urlsafe(32)
        self.allow_commands = allow_commands
        self.commands = Queue(maxsize=32)
        self.receipts = {}
        self.command_lock = RLock()
        self.started_at = time()
        self.requests = 0
        self.rejected = 0
        self.server = None
        self.thread = None

    def start(self):
        if self.server is not None:
            return self.server.server_address[1]
        # Build the served page once. The key is not present in SDK source assets.
        html = (self.page_path.read_text(encoding='utf-8')
                .replace('__FLIGHTSIM_PANEL_KEY__', self.read_key)
                .replace('__FLIGHTSIM_ACTION_KEY__', self.action_key)
                .replace('__FLIGHTSIM_WRITABLE__', 'true' if self.allow_commands else 'false')
                .replace('<!--OFFICE_NAV-->',(self.page_path.parent/'office-nav.html').read_text(encoding='utf-8') if (self.page_path.parent/'office-nav.html').is_file() else '')
                .replace('<!--OFFICE_PAGES-->',(self.page_path.parent/'office-pages.html').read_text(encoding='utf-8') if (self.page_path.parent/'office-pages.html').is_file() else '')
                ).encode('utf-8')
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = 'FlightSim-InGame/0.9'

            def log_message(self, *_):
                # Avoid a log entry on each 1.5s state poll.
                return

            def reply(self, code, body=b'', mime='application/json; charset=utf-8'):
                self.send_response(code)
                self.send_header('Content-Type', mime)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                # No frame-ancestors restriction: the MSFS Coherent wrapper must
                # embed this loopback page. Never allow cross-origin CORS reads.
                self.send_header('Content-Security-Policy',
                                 "default-src 'none'; script-src 'self' 'unsafe-inline'; "
                                 "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                                 "connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'")
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(body)

            def do_POST(self):
                if self.path != '/api/v2/commands' or not owner.allow_commands:
                    owner.rejected += 1
                    return self.reply(405)
                expected = '127.0.0.1:' + str(self.server.server_address[1])
                if (self.headers.get('Host', '').lower() != expected or
                        self.headers.get('Origin', '') != 'http://' + expected or
                        self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json' or
                        not hmac.compare_digest(self.headers.get('X-Flight-Action-Key', ''),
                                                owner.action_key)):
                    owner.rejected += 1
                    return self.reply(403)
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 4096:
                        raise ValueError('Tamanho inválido')
                    raw = self.rfile.read(length)
                    payload = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                    if type(payload) is not dict or set(payload) != {'request_id', 'action', 'value'}:
                        raise ValueError('Formato inválido')
                    request_id, action, value = payload['request_id'], payload['action'], payload['value']
                    if (type(request_id) is not str or not REQUEST_ID.fullmatch(request_id) or
                            type(action) is not str or action not in ALLOWED_ACTIONS):
                        raise ValueError('Comando desconhecido')
                    if not validate_command_value(action,value):
                        raise ValueError('Parâmetros inválidos')
                except (ValueError, TypeError, UnicodeDecodeError):
                    owner.rejected += 1
                    return self.reply(400)
                with owner.command_lock:
                    receipt = owner.receipts.get(request_id)
                    if receipt is not None:
                        if receipt['action'] != action or receipt['value'] != value:
                            owner.rejected += 1
                            return self.reply(409)
                    else:
                        if len(owner.receipts) >= 256:
                            done = [key for key, data in owner.receipts.items()
                                    if data['status'] != 'pending']
                            if not done:
                                return self.reply(429)
                            owner.receipts.pop(done[0])
                        receipt = {'request_id': request_id, 'action': action, 'value': value,
                                   'status': 'pending', 'message': 'Aguardando motor FlightSim'}
                        try:
                            owner.commands.put_nowait((request_id, action, value))
                        except Full:
                            return self.reply(429)
                        owner.receipts[request_id] = receipt
                return self.reply(202, json.dumps(receipt, ensure_ascii=False).encode('utf-8'))

            do_PUT = do_POST
            do_PATCH = do_POST
            do_DELETE = do_POST

            def do_GET(self):
                owner.requests += 1
                expected = '127.0.0.1:' + str(self.server.server_address[1])
                host = self.headers.get('Host', '').lower()
                if host not in (expected, 'localhost:' + str(self.server.server_address[1])):
                    owner.rejected += 1
                    return self.reply(403)
                path = self.path
                if path == '/brand-icon.png':
                    if not BRAND_ICON.is_file():
                        return self.reply(404)
                    return self.reply(200, BRAND_ICON.read_bytes(), 'image/png')
                if path.startswith('/api/v2/commands/') and owner.allow_commands:
                    request_id = path[len('/api/v2/commands/'):]
                    if (not REQUEST_ID.fullmatch(request_id) or
                            not hmac.compare_digest(self.headers.get('X-Flight-Action-Key', ''),
                                                    owner.action_key)):
                        owner.rejected += 1
                        return self.reply(403)
                    with owner.command_lock:
                        receipt = owner.receipts.get(request_id)
                        return self.reply(200, json.dumps(receipt, ensure_ascii=False).encode('utf-8')) if receipt else self.reply(404)
                if path in OFFICE_FILES:
                    name,mime=OFFICE_FILES[path]
                    asset=owner.page_path.parent/name
                    if not asset.is_file():return self.reply(404)
                    return self.reply(200,asset.read_bytes(),mime)
                if path in MODEL_IMAGES:
                    image = FONT_ROOT.parent / MODEL_IMAGES[path]
                    if not image.is_file():
                        owner.rejected += 1
                        return self.reply(404)
                    return self.reply(200,image.read_bytes(),'image/jpeg')
                if path in FONT_FILES:
                    # Exact-match resource allowlist; no filesystem paths from URLs.
                    f = FONT_ROOT / FONT_FILES[path]
                    if not f.is_file():
                        owner.rejected += 1
                        return self.reply(404)
                    return self.reply(200, f.read_bytes(), 'font/ttf')
                if path in ('/', '/index.html'):
                    return self.reply(200, html, 'text/html; charset=utf-8')
                if path == '/api/v1/health':
                    return self.reply(200, json.dumps({
                        'protocol': PROTOCOL_VERSION, 'read_only': not owner.allow_commands,
                        'server': 'FlightSim InGame', 'uptime_s': int(time()-owner.started_at)
                    }).encode('utf-8'))
                if path == '/api/status':
                    # Historical read-only endpoint retained for the browser
                    # diagnostic panel introduced in v0.6. No write endpoint.
                    snapshot = owner.state.get()
                    legacy = {k: snapshot.get(k) for k in (
                        'version', 'status', 'phase', 'balance', 'mission',
                        'position', 'aircraft', 'fuel_gallons', 'updated'
                    )}
                    return self.reply(200, json.dumps(
                        legacy, ensure_ascii=False, allow_nan=False
                    ).encode('utf-8'))
                if path in ('/api/v1/status', '/api/v1/diagnostics'):
                    supplied = self.headers.get('X-Flight-Panel-Key', '')
                    if not hmac.compare_digest(supplied, owner.read_key):
                        owner.rejected += 1
                        return self.reply(403)
                    if path == '/api/v1/diagnostics':
                        data = {
                            'protocol': PROTOCOL_VERSION, 'read_only': not owner.allow_commands,
                            'requests': owner.requests, 'rejected': owner.rejected,
                            'bridge_updated': owner.state.get().get('updated'),
                        }
                    else:
                        data = owner.state.get()
                    try:
                        encoded = json.dumps(data, ensure_ascii=False,
                                             allow_nan=False).encode('utf-8')
                    except (TypeError, ValueError):
                        owner.rejected += 1
                        return self.reply(503)
                    return self.reply(200, encoded)
                owner.rejected += 1
                return self.reply(404)

        server = ThreadingHTTPServer(('127.0.0.1', self.port), Handler)
        self.server = server
        self.port = server.server_address[1]
        self.thread = Thread(target=server.serve_forever,
                             name='FlightSim-InGame-ReadOnly', daemon=True)
        self.thread.start()
        return self.port

    def finish_command(self, request_id, ok, message):
        """Complete a command after it runs on the Tk owner thread."""
        with self.command_lock:
            receipt = self.receipts.get(request_id)
            if receipt and receipt['status'] == 'pending':
                receipt['status'] = 'accepted' if ok else 'rejected'
                receipt['message'] = str(message)[:260]

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = None
            self.thread = None
