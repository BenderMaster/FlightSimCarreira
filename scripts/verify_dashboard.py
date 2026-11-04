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

            # O menu deve ser exibido no próprio WebView (inclusive freelancer).
            page.locator('.nav-item[data-action="market"]').first.click()
            assert page.locator('#market-dialog').is_visible()
            assert page.locator('#market-list .market-option').count()>0
            page.locator('[data-market-filter="freelance"]').click()
            assert page.locator('[data-market-filter="freelance"]').get_attribute('aria-pressed')=='true'
            for offer in page.locator('#market-list .market-option').all():
                assert 'FREELANCER' in offer.inner_text()
            page.locator('[data-market-filter="regional"]').click()
            assert page.locator('#market-list .market-option').count()>0
            page.locator('#market-dialog-close').click()
            assert not page.locator('#market-dialog').is_visible()
            page.locator('.all-missions').click()
            assert page.locator('#market-dialog').is_visible()
            page.locator('#market-dialog-done').click()

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
                      const buttons=[...document.querySelectorAll('main button')].filter(e=>!e.closest('dialog')).filter(e=>{const r=e.getBoundingClientRect();return r.bottom>innerHeight+.5||r.right>innerWidth+.5});
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
