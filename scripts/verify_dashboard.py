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
            page.goto(url);page.wait_for_function("document.getElementById('callsign').textContent.includes('QA-DEMO')")
            # Fresh SQLite state + live engine feed, route and sidebar.
            assert page.locator('#route').inner_text()=='SBRF → SIPE'
            assert page.locator('#aircraft-ref').inner_text().startswith('legacy:c152')
            assert page.locator('.metric').count()==6
            assert 'Combustível' not in page.locator('#metrics').inner_text()
            assert page.locator('#offers .offer').count()>0
            assert page.locator('#weather-origin').inner_text().endswith('SBRF')
            page.locator('[data-tab="weather"]').first.click();assert page.locator('#details').is_visible();page.locator('#dialog-close').click()
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
