"""Ponte InGame read-only: no simulator commands, no career mutations.

The toolbar loads a *same-origin iframe* at 127.0.0.1:8769. An ephemeral
capability is injected into the served HTML (never into the Community package).
This is defense in depth for reads, not authentication for financial actions.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock, Thread
from time import time
import hmac
import json
import secrets

DEFAULT_PORT = 8769
PROTOCOL_VERSION = 2


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
                 page_path: Path | None = None):
        self.state = state
        self.page_path = page_path or (
            Path(__file__).resolve().parent.parent / 'in_game' / 'flightcare_panel.html'
        )
        self.port = port
        self.read_key = secrets.token_urlsafe(32)
        self.started_at = time()
        self.requests = 0
        self.rejected = 0
        self.server = None
        self.thread = None

    def start(self):
        if self.server is not None:
            return self.server.server_address[1]
        # Build the served page once. The key is not present in SDK source assets.
        html = self.page_path.read_text(encoding='utf-8').replace(
            '__FLIGHTSIM_PANEL_KEY__', self.read_key
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
                                 "connect-src 'self'; base-uri 'none'; form-action 'none'")
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(body)

            def do_POST(self):
                owner.rejected += 1
                self.reply(405)

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
                if path in ('/', '/index.html'):
                    return self.reply(200, html, 'text/html; charset=utf-8')
                if path == '/api/v1/health':
                    return self.reply(200, json.dumps({
                        'protocol': PROTOCOL_VERSION, 'read_only': True,
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
                            'protocol': PROTOCOL_VERSION, 'read_only': True,
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

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = None
            self.thread = None
