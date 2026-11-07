"""Playwright smoke for the local, live InGame bridge (no MSFS SDK in CI)."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
from aerocarreira.ingame_bridge import PanelState, LocalPanelServer

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'validation' / 'ingame'
OUTPUT.mkdir(parents=True, exist_ok=True)

state = PanelState()
state.update(status='connected', mode='MSFS', phase='solo',
    aircraft='Cessna 152', balance=12345, fuel_gallons=13.2, remaining_nm=22.3,
    updated=100.0, position={'lat':-8.05,'lon':-34.9},
    telemetry={'ias_kt':91,'gs_kt':87,'altitude_ft':3200,'agl_ft':1700,
               'vs_fpm':-200,'heading_deg':15.0,'on_ground':False},
    mission={'origin':'SBRF','destination':'SIPE','title':'Entrega expressa',
             'reward':1500,'origin_lat':-8.126,'origin_lon':-34.924,
             'destination_lat':-7.97,'destination_lon':-34.96})
bridge = LocalPanelServer(state, port=0)
bridge.start()
url = 'http://127.0.0.1:' + str(bridge.port) + '/'
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':780,'height':620})
        errors=[]
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_function("document.getElementById('aircraft').textContent==='Cessna 152'")
        assert page.locator('#balance').inner_text() == 'R$ 12.345', page.locator('#balance').inner_text()
        assert 'SIMCONNECT ATIVO' in page.locator('#status').inner_text()
        assert 'SBRF' in page.locator('#origin').inner_text()
        assert page.locator('#map-content .track').count() == 1
        assert page.locator('#map-content .airplane').count() == 1
        page.locator('#mode').click()
        assert page.locator('#details').is_visible()
        assert page.locator('#hdg').inner_text() == '15.0°'
        page.screenshot(path=str(OUTPUT/'ingame-completo.png'),full_page=True)
        state.update(status='reconnecting', aircraft=None, telemetry=None)
        page.locator('#refresh').click()
        page.wait_for_function("document.getElementById('status').textContent==='RECONECTANDO'")
        state.update(status='connected', aircraft='Cessna 172',balance=45678)
        page.locator('#refresh').click()
        page.wait_for_function("document.getElementById('aircraft').textContent==='Cessna 172'")
        assert page.locator('#balance').inner_text()=='R$ 45.678'
        for width,height in [(320,520),(420,740),(800,700),(1120,800)]:
            page.set_viewport_size({'width':width,'height':height})
            page.wait_for_timeout(50)
            overflow=page.evaluate('document.documentElement.scrollWidth - window.innerWidth')
            assert overflow<=2,(width,overflow)
        page.screenshot(path=str(OUTPUT/'ingame-compacto.png'),full_page=True)
        assert not errors,errors
        browser.close()
finally:
    bridge.stop()
print(json.dumps({'ingame':'ok','screenshots':str(OUTPUT)},ensure_ascii=False))
