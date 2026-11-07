"""Playwright smoke for the local, live InGame bridge (no MSFS SDK in CI)."""
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright, expect
from aerocarreira.ingame_bridge import PanelState, LocalPanelServer
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
        # The actual app font must be downloadable by same-origin Coherent iframe.
        expect(page.locator('body')).to_have_css('font-family', '"FlightSimBarlow", Arial, sans-serif')
        page.evaluate("document.fonts.load('400 16px FlightSimBarlow')")
        assert page.evaluate("document.fonts.check('400 16px FlightSimBarlow')")
        assert page.evaluate("document.fonts.check('600 16px FlightSimBarlow')")
        assert 'Visão geral' in page.locator('#page-title').inner_text()
        expect(page.locator('#aircraft')).to_have_text('Cessna 152', timeout=8000)
        assert page.locator('#balance').inner_text() == 'R$ 12.345', page.locator('#balance').inner_text()
        assert 'SIMCONNECT ATIVO' in page.locator('#status').inner_text()
        assert 'SBRF' in page.locator('#origin').inner_text()
        assert page.locator('[data-page="dashboard"]').is_visible()
        assert not page.locator('[data-page="route"]').is_visible()
        page.screenshot(path=str(OUTPUT/'ingame-tablet-dashboard.png'),full_page=True)
        page.locator('[data-view="route"]').click()
        assert page.locator('[data-page="route"]').is_visible()
        assert page.locator('#map-content .track').count() == 1
        assert page.locator('#map-content .airplane').count() == 1
        page.screenshot(path=str(OUTPUT/'ingame-tablet-mapa.png'),full_page=True)
        page.locator('[data-view="aircraft"]').click()
        assert page.locator('#details').is_visible()
        assert page.locator('#hdg').inner_text() == '15.0°'
        page.locator('[data-view="career"]').click()
        assert page.locator('[data-page="career"]').is_visible()
        page.locator('[data-view="dashboard"]').click()
        assert page.locator('[data-page="dashboard"]').is_visible()
        state.update(status='reconnecting', aircraft=None, telemetry=None)
        page.locator('#refresh').click()
        expect(page.locator('#status')).to_have_text('RECONECTANDO', timeout=8000)
        state.update(status='connected', aircraft='Cessna 172',balance=45678)
        page.locator('#refresh').click()
        expect(page.locator('#aircraft')).to_have_text('Cessna 172', timeout=8000)
        assert page.locator('#balance').inner_text()=='R$ 45.678'
        for width,height in [(320,320),(420,740),(560,380),(800,700),(1120,800)]:
            page.set_viewport_size({'width':width,'height':height})
            page.wait_for_timeout(50)
            overflow=page.evaluate('document.documentElement.scrollWidth - window.innerWidth')
            assert overflow<=2,(width,overflow)
        page.screenshot(path=str(OUTPUT/'ingame-tablet-responsivo.png'),full_page=True)
        assert not errors,errors
        browser.close()
finally:
    bridge.stop()
print(json.dumps({'ingame':'ok','screenshots':str(OUTPUT)},ensure_ascii=False))
