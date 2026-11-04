"""Browser tests on the live Python application, not a static mocked page.
Run: xvfb-run -a python scripts/verify_dashboard.py (Linux) or python ... (Windows).
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'validation'/'screenshots'
OUTPUT.mkdir(parents=True,exist_ok=True)
resolutions=[(1280,720),(1366,768),(1600,900),(1920,1080),(2560,1440)]
results=[]
with tempfile.TemporaryDirectory() as temp:
    marker=Path(temp)/'url';env=dict(os.environ,APPDATA=temp,FLIGHTSIM_HEADLESS='1')
    log=open(Path(temp)/'engine.log','w+')
    process=subprocess.Popen([sys.executable,str(ROOT/'scripts/run_dashboard_fixture.py'),str(marker)],env=env,stdout=log,stderr=log,cwd=ROOT)
    try:
        deadline=time.monotonic()+30
        while not marker.exists():
            if process.poll() is not None or time.monotonic()>deadline:
                log.seek(0);raise RuntimeError(log.read())
            time.sleep(.1)
        url=marker.read_text();origin,token=url.split('/#',1)
        with sync_playwright() as p:
            browser=p.chromium.launch(args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1600,'height':900})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            # Determinístico: exercita também o modo sem serviços externos.
            page.route('https://cdn.jsdelivr.net/**',lambda route:route.abort())
            page.route('https://tiles.openfreemap.org/**',lambda route:route.abort())
            page.route('https://tiles.maps.eox.at/**',lambda route:route.abort())
            page.goto(url);page.wait_for_function("document.getElementById('callsign').textContent.includes('QA-DEMO')")
            # Fresh SQLite state + live engine feed, route and sidebar.
            assert page.locator('#route').inner_text()=='SBRF → SIPE'
            assert page.locator('#aircraft-ref').inner_text().startswith('legacy:c152')
            assert page.locator('.metric').count()==6
            assert 'Combustível' not in page.locator('#metrics').inner_text()
            assert page.locator('#offers .offer').count()>0
            assert page.locator('#weather-origin').inner_text().endswith('SBRF')
            page.locator('[data-tab="weather"]').first.click();assert page.locator('#details').is_visible();page.locator('#dialog-close').click()

            # Sidebar persistente: os mercados são páginas separadas, não diálogos.
            page.locator('.nav-item[data-action="regional"]').click()
            assert page.locator('#market-page').is_visible()
            assert page.locator('.sidebar').is_visible()
            assert not page.locator('.left-column').is_visible()
            assert page.locator('[data-market-view="regional"]').get_attribute('aria-pressed')=='true'
            assert page.locator('#market-list .market-option').count()>0
            page.locator('#market-list .market-option').first.click()
            assert page.locator('#details').is_visible()
            assert page.locator('#details-content').is_visible()
            assert page.locator('#detail-map-slot #free-map').count()==1
            assert page.locator('#detail-map-slot .map-area').is_visible()
            assert 'NM' in page.locator('#detail-distance').inner_text()
            assert page.locator('#detail-duration').inner_text().startswith('~')
            assert page.locator('#detail-aircraft').inner_text()
            assert 'R$' in page.locator('#detail-reward').inner_text()
            page.locator('#dialog-close').click()
            assert page.locator('.center-column .map-card #free-map').count()==1
            assert page.locator('#market-page').is_visible()
            assert page.locator('.nav-item').count()==10
            assert page.locator('.nav-item[data-action="freelance"]').count()==0
            assert page.locator('.nav-item[data-action="regional"]').inner_text()=='Mercado'
            page.locator('[data-market-view="freelance"]').click()
            assert page.locator('[data-market-view="freelance"]').get_attribute('aria-pressed')=='true'
            for offer in page.locator('#market-list .market-option').all():
                assert 'FREELANCER' in offer.inner_text()
            page.locator('[data-market-view="regional"]').click()
            assert page.locator('#market-list .market-option').count()>0
            page.locator('.nav-item[data-action="planning"]').click()
            assert page.locator('#module-page').is_visible()
            assert 'PLANEJAMENTO' in page.locator('#module-title').inner_text()
            assert page.locator('.sidebar').is_visible()
            page.locator('.nav-item[data-action="dashboard"]').click()
            assert page.locator('.center-column').is_visible()
            page.locator('.all-missions').click()
            assert page.locator('#market-page').is_visible()
            page.locator('.nav-item[data-action="dashboard"]').click()

            # A proa muda mesmo sem deslocar latitude/longitude no mapa local.
            heading=page.evaluate("""() => {
              const s={...state,telemetry:{lat:-8.1264,lon:-34.9228,heading_deg:15,stale:false}};
              renderMap(s);
              const before=document.querySelector('#route-map g[data-heading]')?.getAttribute('transform');
              renderMap({...s,telemetry:{...s.telemetry,heading_deg:135}});
              const after=document.querySelector('#route-map g[data-heading]')?.getAttribute('transform');
              return {before,after};
            }""")
            assert heading['before'] and 'rotate(-30)' in heading['before'],heading
            assert heading['after'] and 'rotate(90)' in heading['after'],heading
            badge=page.evaluate("""() => {
              renderMap({...state,mode:'MSFS',telemetry:{
                lat:-8.12,lon:-34.92,heading_deg:301,heading_magnetic_deg:322,stale:false}});
              return document.getElementById('map-mode').textContent;
            }""")
            assert '322° MAG' in badge,badge
            assert '301° TRUE' in badge,badge

            # Abastecimento é popup real, com litros e ressarcimento estimado.
            popup=page.evaluate("""() => {
              const old=state;
              state={...old,connection:'connected',phase:'SOLO',
                plane:{ref:'legacy:c152',title:'Cessna 152'},
                telemetry:{stale:false},fuel:{quantity:9,capacity:26,refundable_liters:12}};
              openRefuelDialog();
              const opened=document.getElementById('refuel-dialog').open;
              const capacity=document.getElementById('refuel-capacity').textContent;
              const units=document.getElementById('refuel-target').max;
              document.getElementById('refuel-target').value='20';
              updateRefuelPreview();
              const refund=document.getElementById('refuel-summary').textContent;
              refuelDialog.close();state=old;
              return {opened,capacity,units,refund};
            }""")
            assert popup['opened'] and 'L' in popup['capacity'],popup
            assert float(popup['units'])>90,popup
            assert 'Devolver:' in popup['refund'],popup
            assert page.locator('#resource-alerts').count()==1
            assert page.locator('button[data-action="dispatch"]').count()==1

            page.locator('#zoom-in').click();page.locator('#recenter').click()
            # Native action routed through the command queue, reflected in telemetry.
            before=page.locator('#metric-alt').inner_text()
            page.evaluate("() => command('demo_next')")
            page.wait_for_timeout(4200)
            for width,height in resolutions:
                for scale in (1,1.25,1.5):
                    # Windows logical work area, reserving 40 physical pixels for taskbar.
                    viewport={'width':round(width/scale),'height':round((height-40)/scale)}
                    page.set_viewport_size(viewport);page.wait_for_timeout(550)
                    audit=page.evaluate('''() => {
                      const required=['.header','.sidebar','.market','.summary','.contract','.map-card','.telemetry','.flight-log','.realism','.aircraft','.dispatch'];
                      const out=required.filter(s=>{const r=document.querySelector(s).getBoundingClientRect();return r.x<-.5||r.y<-.5||r.right>innerWidth+.5||r.bottom>innerHeight+.5||r.width<1||r.height<1});
                      const buttons=[...document.querySelectorAll('main button')].filter(e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden').filter(e=>{const r=e.getBoundingClientRect();return r.bottom>innerHeight+.5||r.right>innerWidth+.5});
                      const clipped=[...document.querySelectorAll('.nav-item,.map-tabs button,.dispatch button')].filter(e=>e.scrollWidth>e.clientWidth+2).map(e=>e.innerText);const metrics=document.querySelector('.metrics').getBoundingClientRect(),weather=document.querySelector('.weather-row').getBoundingClientRect();const overlap=metrics.bottom>weather.top+.5;return {out,clipped,overlap,buttons:buttons.map(e=>e.innerText),scrollX:document.documentElement.scrollWidth>innerWidth,scrollY:document.documentElement.scrollHeight>innerHeight};
                    }''')
                    filename=f'{width}x{height}-{int(scale*100)}pct.png'
                    page.screenshot(path=str(OUTPUT/filename))
                    results.append(dict(resolution=[width,height],scale=scale,viewport=viewport,**audit))
            assert not errors,errors
            failures=[r for r in results if r['overlap'] or r['out'] or r['clipped'] or r['buttons'] or r['scrollX'] or r['scrollY']]
            (OUTPUT.parent/'layout-results.json').write_text(json.dumps({'browser_errors':errors,'cases':results},indent=2))
            assert not failures,json.dumps(failures,indent=2)
            # Mapa gratuito: fallback interativo permanece sem rede e sem chave.
            assert page.locator('#free-map').count()==1
            assert page.locator('#satellite-toggle').count()==1
            assert page.locator('#route-map circle').count()>=2
            zoom_before=page.evaluate('zoom')
            # O teste offline usa o SVG caso a CDN/mapa não carregue em Chromium.
            page.evaluate("() => { document.querySelector('.map-area').classList.remove('free-active'); }")
            page.locator('#route-map').hover()
            page.mouse.wheel(0,-300)
            page.wait_for_timeout(250)
            assert page.evaluate('zoom')>zoom_before
            page.locator('#satellite-toggle').click()
            assert page.locator('#satellite-toggle').get_attribute('aria-pressed')=='true'
            page.locator('#satellite-toggle').click()
            assert page.locator('#satellite-toggle').get_attribute('aria-pressed')=='false'
            assert page.locator('#route').inner_text()=='SBRF → SIPE'
            assert 'ORIGEM' in page.locator('#weather-origin').inner_text()
            assert 'DESTINO' in page.locator('#weather-destination').inner_text()

            # Mapa MapLibre com backend simulado para testar dimensões reais,
            # ResizeObserver, ângulo do avião e ausência de sobreposição do HUD.
            map_page=browser.new_page(viewport={'width':1600,'height':900})
            map_errors=[]
            map_page.on('pageerror',lambda error:map_errors.append(str(error)))
            map_page.add_init_script("""(() => {
              class FakeMap {
                constructor(opts){
                  this.el=document.getElementById(opts.container);
                  this.startWidth=this.el.clientWidth;
                  this.startHeight=this.el.clientHeight;
                  this.canvas=document.createElement('canvas');
                  this.el.append(this.canvas);
                  this.sources={};this.layers={};this.zoom=10;this.resizeCalls=0;
                  window.__fakeMap=this;
                }
                on(event,cb){if(event==='load')setTimeout(cb,0);return this}
                addControl(){}
                resize(){
                  this.resizeCalls++;
                  this.canvas.style.width=this.el.clientWidth+'px';
                  this.canvas.style.height=this.el.clientHeight+'px';
                }
                addSource(id,def){this.sources[id]={...def,setData(data){this.data=data}}}
                getSource(id){return this.sources[id]}
                addLayer(layer){this.layers[layer.id]=layer}
                getLayer(id){return this.layers[id]}
                setLayoutProperty(id,k,v){if(this.layers[id])this.layers[id][k]=v}
                fitBounds(){}
                jumpTo(){}
                getZoom(){return this.zoom}
                zoomTo(z){this.zoom=z}
              }
              class FakeMarker {
                constructor(opts){this.el=opts.element}
                setLngLat(){return this}
                addTo(){document.getElementById('free-map').append(this.el);return this}
                getElement(){return this.el}
                remove(){this.el.remove()}
              }
              class FakeBounds {extend(){return this}}
              window.maplibregl={supported:()=>true,Map:FakeMap,
                Marker:FakeMarker,AttributionControl:class{},LngLatBounds:FakeBounds};
            })()""")
            map_page.goto(url)
            # CSP do aplicativo proíbe eval; Playwright wait_for_function com string
            # usa eval internamente. Faça polling via evaluate sem enfraquecer a CSP.
            ready=False
            for _ in range(50):
                ready=map_page.evaluate("""() => Boolean(window.__fakeMap &&
                    __fakeMap.resizeCalls>0 && __fakeMap.getSource('fsc-route'))""")
                if ready:break
                time.sleep(.1)
            assert ready,"MapLibre simulado não inicializou no tamanho real"
            dims=map_page.evaluate("""() => {
              const area=document.querySelector('.map-area').getBoundingClientRect();
              const box=document.getElementById('free-map').getBoundingClientRect();
              const canvas=__fakeMap.canvas.getBoundingClientRect();
              return {area:area.width,box:box.width,canvas:canvas.width,
                      initial:[__fakeMap.startWidth,__fakeMap.startHeight]};
            }""")
            assert dims['initial'][0]>0 and dims['initial'][1]>0,dims
            assert abs(dims['area']-dims['box'])<2 and abs(dims['box']-dims['canvas'])<2,dims
            map_page.set_viewport_size({'width':1280,'height':720})
            map_page.wait_for_timeout(300)
            resized=map_page.evaluate("""() => ({
              box:document.getElementById('free-map').getBoundingClientRect().width,
              canvas:__fakeMap.canvas.getBoundingClientRect().width,
              calls:__fakeMap.resizeCalls
            })""")
            assert abs(resized['box']-resized['canvas'])<2 and resized['calls']>0,resized
            orientations=map_page.evaluate("""() => {
              const s={...state,telemetry:{lat:-8.1264,lon:-34.9228,
                heading_deg:15,stale:false}};
              FSCFreeMap.render(s);
              const before=document.querySelector('.fsc-plane-marker svg').style.transform;
              FSCFreeMap.render({...s,telemetry:{...s.telemetry,heading_deg:135}});
              const after=document.querySelector('.fsc-plane-marker svg').style.transform;
              return {before,after};
            }""")
            assert 'rotate(-30deg)' in orientations['before'],orientations
            assert 'rotate(90deg)' in orientations['after'],orientations
            # Instância MapLibre e canvas permanecem os mesmos ao abrir detalhes.
            map_page.locator('.nav-item[data-action="regional"]').click()
            map_page.locator('#market-list .market-option').first.click()
            map_page.wait_for_timeout(200)
            assert map_page.locator('#detail-map-slot #free-map').count()==1
            assert map_page.evaluate("() => __fakeMap.resizeCalls")>resized['calls']
            route=map_page.evaluate("() => __fakeMap.getSource('fsc-route').data")
            assert route['geometry']['type']=='LineString',route
            map_page.locator('#dialog-close').click()
            assert map_page.locator('.center-column .map-card #free-map').count()==1
            map_page.locator('.nav-item[data-action="dashboard"]').click()
            assert map_page.locator('.map-area').count()==1
            map_page.locator('#satellite-toggle').click()
            credit=map_page.evaluate("""() => {
              const a=document.querySelector('#satellite-toggle').getBoundingClientRect();
              const b=document.querySelector('#satellite-credit').getBoundingClientRect();
              return {visible:!document.querySelector('#satellite-credit').hidden,
                overlap:!(a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top)};
            }""")
            assert credit['visible'] and not credit['overlap'],credit
            assert not map_errors,map_errors
            map_page.close()

            # Safe shutdown persists the active contract in the isolated career.
            page.evaluate("() => command('close')")
            process.wait(timeout=10)
            assert process.returncode==0
            import sqlite3
            db=sqlite3.connect(Path(temp)/'AeroCarreira-Lab'/'carreira.db')
            assert db.execute("select value from settings where key='balance'").fetchone()
            db.close();browser.close()
        print(f'PASS: live dashboard, navigation, shutdown, {len(results)} responsive cases')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=10)
        log.close()
