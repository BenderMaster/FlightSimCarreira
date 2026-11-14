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
                   'fuel_toggle', 'fuel_refuel'}
REQUEST_ID = re.compile(r'^[A-Za-z0-9_-]{16,64}$')
FONT_FILES = {
    '/fonts/BarlowSemiCondensed-Regular.ttf': 'BarlowSemiCondensed-Regular.ttf',
    '/fonts/BarlowSemiCondensed-SemiBold.ttf': 'BarlowSemiCondensed-SemiBold.ttf',
}


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
                    if not 0 < length <= 1024:
                        raise ValueError('Tamanho inválido')
                    raw = self.rfile.read(length)
                    payload = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                    if type(payload) is not dict or set(payload) != {'request_id', 'action', 'value'}:
                        raise ValueError('Formato inválido')
                    request_id, action, value = payload['request_id'], payload['action'], payload['value']
                    if (type(request_id) is not str or not REQUEST_ID.fullmatch(request_id) or
                            type(action) is not str or action not in ALLOWED_ACTIONS):
                        raise ValueError('Comando desconhecido')
                    if action in ('offer_accept', 'mission_cancel', 'dispatch_prepare'):
                        if type(value) is not str or not 1 <= len(value) <= 100:
                            raise ValueError('Identificador inválido')
                    elif action == 'fuel_toggle':
                        if type(value) is not bool:
                            raise ValueError('Opção inválida')
                    elif action == 'fuel_refuel':
                        if type(value) not in (float, int) or not 0 <= value <= 2000:
                            raise ValueError('Litros inválidos')
                    elif value is not None:
                        raise ValueError('Campo inesperado')
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
