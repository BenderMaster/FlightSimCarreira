"""Private loopback transport. Token authentication, same-origin writes, bounded queue."""
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue, Full

ACTIONS={'pilot','market','fleet','planning','finance','employment','history','reports','settings','connect','disconnect',
         'demo','demo_next','legacy','cancel','plan','fuel','refuel','service','avatar','refresh','offer','close','save_log','installed','analyze','locate','local_panel'}
ASSETS=Path(__file__).with_name('midnight')
class DashboardServer:
    def __init__(self):
        self.token=secrets.token_urlsafe(32)
        self.commands=Queue(maxsize=32)
        self.state=b'{}'
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,status,data,mime='application/json'):
                self.send_response(status)
                self.send_header('Content-Type',mime)
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' https://cdn.jsdelivr.net blob:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: blob: https://tiles.openfreemap.org https://tiles.maps.eox.at https://cdn.jsdelivr.net; connect-src 'self' https://tiles.openfreemap.org https://tiles.maps.eox.at https://cdn.jsdelivr.net; font-src 'self' https://tiles.openfreemap.org https://cdn.jsdelivr.net; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'")
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def valid_host(self):return self.headers.get('Host')==owner.host
            def authorized(self):return self.valid_host() and secrets.compare_digest(self.headers.get('X-Flight-Token',''),owner.token)
            def do_GET(self):
                if not self.valid_host():self.reply(403,b'{}');return
                if self.path=='/state':
                    self.reply(200,owner.state) if self.authorized() else self.reply(403,b'{}');return
                paths={'/scenery.jpg':('scenery.jpg','image/jpeg'),'/c152.jpg':('c152.jpg','image/jpeg'),'/':('index.html','text/html; charset=utf-8'),'/style.css':('style.css','text/css'),'/app.js':('app.js','text/javascript'),'/free-map.js':('free-map.js','text/javascript'),'/vendor/maplibre-gl.js':('vendor/maplibre-gl.js','text/javascript'),'/vendor/maplibre-gl.css':('vendor/maplibre-gl.css','text/css'),'/scenery.svg':('scenery.svg','image/svg+xml'),'/fonts/BarlowSemiCondensed-Regular.ttf':('fonts/BarlowSemiCondensed-Regular.ttf','font/ttf'),'/fonts/BarlowSemiCondensed-SemiBold.ttf':('fonts/BarlowSemiCondensed-SemiBold.ttf','font/ttf')}
                if self.path not in paths:self.reply(404,b'{}');return
                name,mime=paths[self.path];asset=ASSETS/name
                if not asset.is_file():self.reply(404,b'{}');return
                self.reply(200,asset.read_bytes(),mime)
            def do_POST(self):
                if not self.authorized() or self.headers.get('Origin')!=owner.origin:
                    self.reply(403,b'{}');return
                if self.path!='/command':self.reply(404,b'{}');return
                try:
                    n=int(self.headers.get('Content-Length','0'))
                    if not 0<n<=2048 or self.headers.get('Content-Type')!='application/json':raise ValueError()
                    data=json.loads(self.rfile.read(n))
                    if not isinstance(data,dict) or data.get('action') not in ACTIONS:raise ValueError()
                    if set(data)-{'action','id'} or ('id' in data and (not isinstance(data['id'],str) or len(data['id'])>200)):raise ValueError()
                    owner.commands.put_nowait(data)
                except Full:self.reply(429,b'{}');return
                except (ValueError,TypeError):self.reply(400,b'{}');return
                self.reply(202,b'{"queued":true}')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.host=f'127.0.0.1:{self.server.server_port}'
        self.origin='http://'+self.host
        self.url=self.origin+'/#'+self.token
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
    def start(self):self.thread.start()
    def publish(self,state):self.state=json.dumps(state,ensure_ascii=False,allow_nan=False).encode()
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
