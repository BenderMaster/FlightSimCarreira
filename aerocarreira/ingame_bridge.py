"""Ponte HTTP local SOMENTE-LEITURA para protótipo do painel MSFS 2020.

Segurança: atende somente loopback, não expõe SQLite, não aceita POST/PUT,
não habilita CORS e não inclui ações financeiras. O HTML é de autoria própria.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock, Thread
import json

DEFAULT_PORT = 8769


class PanelState:
    def __init__(self):
        self.lock = RLock()
        self.state = {'version': 1,'status':'offline','phase':'aguardando',
                      'balance':0,'mission':None,'position':None,'aircraft':None,
                      'fuel_gallons':None,'updated':None}

    def update(self, **fields):
        with self.lock:
            self.state.update(fields)

    def get(self):
        with self.lock:
            return dict(self.state)


class LocalPanelServer:
    """Servidor local independente de Tk, não realiza comandos no MSFS."""
    def __init__(self, state: PanelState, port: int = DEFAULT_PORT,
                 page_path: Path | None = None):
        self.state = state
        self.page_path=page_path or (Path(__file__).resolve().parent.parent/'in_game'/'flightcare_panel.html')
        self.port=port
        self.server = None
        self.thread = None

    def start(self):
        if self.server is not None:
            return self.port
        state=self.state
        html=self.page_path.read_bytes()
        port=self.port
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def _deny(self,code):
                self.send_response(code);self.send_header('Content-Length','0');self.end_headers()
            def do_POST(self): self._deny(405)
            do_PUT = do_POST
            do_DELETE = do_POST
            def do_GET(self):
                if self.headers.get('Host','').lower() not in (f'127.0.0.1:{self.server.server_address[1]}',f'localhost:{self.server.server_address[1]}'):
                    return self._deny(403)
                if self.path in ('/','/index.html'):
                    content=html;kind='text/html; charset=utf-8'
                elif self.path=='/api/status':
                    content=json.dumps(state.get(),ensure_ascii=False,allow_nan=False).encode('utf-8')
                    kind='application/json; charset=utf-8'
                else:
                    return self._deny(404)
                self.send_response(200)
                self.send_header('Content-Type',kind)
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")
                self.send_header('Content-Length',str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        self.server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.thread=Thread(target=self.server.serve_forever,name='FlightSimCarreira-local-bridge',daemon=True)
        self.thread.start()
        return port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = None
