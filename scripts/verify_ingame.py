"""Playwright smoke for the local, live InGame bridge (no MSFS SDK in CI)."""
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright, expect
from aerocarreira.ingame_bridge import PanelState, LocalPanelServer
from aerocarreira.ingame_office import project
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
bridge = LocalPanelServer(state, port=0, allow_commands=True)
bridge.start()
url = 'http://127.0.0.1:' + str(bridge.port) + '/'
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':780,'height':620})
        errors=[]
        page.on('pageerror', lambda e: errors.append(str(e)))
        # Emulate the older MSFS2020 Coherent GT DOM: replaceChildren may be
        # absent even though it works in the modern CI Chromium.
        page.add_init_script("Object.defineProperty(Element.prototype, 'replaceChildren', {value: undefined, configurable: true})")
        page.goto(url)
        assert page.evaluate("typeof document.getElementById('market-list').replaceChildren") == 'undefined'
        # The actual app font must be downloadable by same-origin Coherent iframe.
        assert 'FlightSimBarlow' in page.locator('body').evaluate("(el) => getComputedStyle(el).fontFamily")
        page.evaluate("Promise.all([document.fonts.load('400 16px FlightSimBarlow'),document.fonts.load('700 16px FlightSimBarlow')])")
        assert page.evaluate("document.fonts.check('400 16px FlightSimBarlow')")
        assert page.evaluate("document.fonts.check('700 16px FlightSimBarlow')")
        # The Win11/Coherent 8-11px labels were too small in the MSFS toolbar.
        # Keep typography readable at the approved floating-tablet width.
        computed_px = lambda selector: page.locator(selector).first.evaluate(
            "(el) => parseFloat(getComputedStyle(el).fontSize)")
        assert computed_px('body') >= 15
        assert computed_px('nav.side button span') >= 14
        assert computed_px('.metric span') >= 12
        assert computed_px('.pair') >= 13
        assert page.locator('.logo img').get_attribute('src') == '/brand-icon.png'
        assert page.locator('.logo img').evaluate('(el) => el.complete && el.naturalWidth > 0')
        assert 'Visão geral' in page.locator('#page-title').inner_text()
        expect(page.locator('#aircraft')).to_have_text('Cessna 152', timeout=8000)
        assert page.locator('#balance').inner_text() == 'R$ 12.345', page.locator('#balance').inner_text()
        # Exercise every new office section against a real loopback server.
        fixture = {
          'pilot':{'name':'Íris Piloto','callsign':'PT-ABC','home_icao':'SBRF'},
          'pilot_career':{'name':'Íris Piloto','level':5,'xp':550,'reputation':90,
               'rank':{'title':'Soldado 1ª classe'},'hours':13.5,'contracts':8,
               'licenses':[{'code':'PPA','title':'Piloto Privado','status':'available'}],
               'medals':[{'code':'primeiro','title':'Primeiro Voo','status':'earned'}]},
          'flight_operations':{'draft':{'mode':'contract','origin':'SBRF',
               'destination':'SIPE','altitude_ft':2500,'waypoints':[],
               'checks':{'runway_checked':True,'route_checked':False,
                         'fuel_checked':False,'payload_checked':False}},
               'ready':True,'route':{'origin':'SBRF','destination':'SIPE',
               'distance_nm':40,'minutes':35,'fuel_required_gal':5.5}},
          'fleet':{'active_ref':'legacy:c152','owned':[{'ref':'legacy:c152',
               'code':'c152','title':'Cessna 152','airport':'SBRF',
               'condition':93,'hours':20,'kind':'starter','is_active':True}]},
          'aircraft_market':{'ready':True,'airport':'SBRF',
               'models':[{'code':'c172','title':'Cessna 172 Skyhawk',
                          'price':180000,'cruise_kts':118,
                          'rental_prices':{'24':1800}}]},
          'airline_operations':{'mode':'autonomo','investment':400000,
               'vacancies':[{'id':'azul-01','name':'Azul','company':'azul',
               'salary':30000,'allowed':True,'min_level':4,'min_hours':10}],
               'type_ratings':[{'code':'a320neo','title':'Airbus A320neo',
               'rated':False,'flights':1,'required':2,'installed':True}]},
          'flight_history':{'count':1,'flights':[{'id':1,'aircraft':'Cessna 152',
               'started_utc':1763000000,'hours':0.5,'direct_nm':35,
               'touchdown_fpm':-150,'stalls':0,'note':'Bom voo!','xp':50}]},
          'financial_center':{'balance':12345,'income':30000,'expenses':1500,
               'debt':3000,'net_worth':145000,'loan_limit':150000,'loan_rate':.08,
               'monthly':[{'month':'2026-11','income':8000,'expense':2000}],
               'transactions':[{'id':1,'label':'Contrato','amount':8000,
               'description':'Pagamento de missão','occurred_utc':1763000000}]}
        }
        state.update(office=project(fixture),office_updated=1)
        page.locator('#refresh').click()
        expect(page.locator('#planning-status')).to_have_text('Catálogo MSFS confirmado',timeout=8000)
        for view,title in [
            ('planning','Planejamento de voo'),
            ('hangar','Meu hangar'),
            ('airlines','Companhias aéreas'),
            ('career','Íris Piloto'),
            ('logbook','Logbook'),
            ('finances','Finanças')
        ]:
            page.locator('[data-view="'+view+'"]').click()
            assert page.locator('[data-page="'+view+'"]').is_visible(), view
            assert title in page.locator('[data-page="'+view+'"]').inner_text(), view
            page.screenshot(path=str(OUTPUT/('ingame-v092-'+view+'.png')),full_page=True)
        page.locator('[data-view="planning"]').click()
        assert page.locator('#plan-origin').input_value()=='SBRF'
        assert page.locator('#plan-destination').input_value()=='SIPE'
        page.locator('#wp-label').fill('FIX01')
        page.locator('#wp-lat').fill('-8.1234')
        page.locator('#wp-lon').fill('-34.5678')
        page.locator('#wp-add').click()
        assert 'FIX01' in page.locator('#waypoint-list').inner_text()
        page.locator('#waypoint-list button').first.click()
        assert page.locator('#wp-label').input_value()=='FIX01'
        page.locator('[data-view="finances"]').click()
        assert page.locator('.finance-month').count()==1
        page.locator('[data-view="dashboard"]').click()

        assert 'SIMCONNECT ATIVO' in page.locator('#status').inner_text()
        assert 'SIMCONNECT • LIVE' in page.locator('#connection-badge').inner_text()
        assert 'FlightSim Windows respondendo' in page.locator('#companion-label').inner_text()
        assert 'SBRF' in page.locator('#origin').inner_text()
        assert page.locator('.route .arrow svg path').count() == 1
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
        # Exercise a real button-to-HTTP-to-Tk-queue flow without changing any
        # career database, then verify the pending receipt updates in the tablet.
        state.update(ground_operations={'offer_allowed':True,'reason':'Estacionamento confirmado',
            'awaiting_turnaround':False},offers=[{'id':'QA-OFFER','origin':'SBRF','destination':'SIPE',
            'title':'Voo de teste','category':'Regional','reward':1200,
            'freelance':False,'distance':42,'minutes':27,'allowed':True,
            'reason':'','manifest_label':'Carga leve'}],
            market_ready=True, mission=None,
            telemetry={'ias_kt':0,'gs_kt':0,'altitude_ft':31,'on_ground':True})
        state.update(airport_services={'SIPE':{'ils':True,'papi':False,
            'runway_lights':True,'approach_lights':None,'fuel_spot':True}})
        page.locator('#refresh').click()
        page.locator('[data-view="market"]').click()
        expect(page.locator('.offer-row')).to_have_count(1,timeout=8000)
        assert page.locator('.offer-route-arrow').count()==1,'Expected SVG arrow, not missing text glyph'
        assert 'ILS: Sim' in page.locator('.market-services').inner_text()
        assert 'PAPI: Não' in page.locator('.market-services').inner_text()
        assert 'Luzes aprox.: Não verificado' in page.locator('.market-services').inner_text()
        page.locator('#market-service-filter').select_option('ils')
        assert page.locator('.offer-row').count()==1
        page.locator('#market-service-filter').select_option('papi')
        assert page.locator('.offer-row').count()==0
        page.locator('#market-service-filter').select_option('all')
        expect(page.locator('.offer-row')).to_have_count(1)
        state.update(ground_operations={'offer_allowed':False,
            'reason':'Pista ainda ocupada','awaiting_turnaround':False})
        page.locator('#refresh').click()
        expect(page.locator('.offer-row button')).to_be_disabled()
        assert 'ACEITE BLOQUEADO' in page.locator('#market-ground-status').inner_text()
        state.update(ground_operations={'offer_allowed':True,
            'reason':'Estacionamento confirmado','awaiting_turnaround':False})
        page.locator('#refresh').click()
        expect(page.locator('.offer-row button')).to_be_enabled()
        page.screenshot(path=str(OUTPUT/'ingame-v093-market-facilities.png'),full_page=True)
        page.locator('.offer-row button').click()
        expect(page.locator('#confirm-shade')).to_be_visible()
        page.locator('#confirm-yes').click()
        request_id, action, value = bridge.commands.get(timeout=5)
        assert action == 'offer_accept' and value == 'QA-OFFER'
        bridge.finish_command(request_id, True, 'Contrato aceito no motor')
        expect(page.locator('#action-feedback')).to_contain_text('Contrato aceito no motor',timeout=8000)
        page.locator('[data-view="dashboard"]').click()
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
            assert computed_px('nav.side button span') >= 11, (width, 'navigation font too small')
        page.screenshot(path=str(OUTPUT/'ingame-tablet-responsivo.png'),full_page=True)
        assert not errors,errors
        # Frontend JS/render regressions are not motor/network outages.
        # The error must be classified distinctly instead of clearing telemetry.
        broken = browser.new_page(viewport={'width':780,'height':620})
        broken.goto(url)
        expect(broken.locator('#aircraft')).to_have_text('Cessna 172',timeout=8000)
        broken.evaluate("document.getElementById('market-list').remove()")
        broken.locator('#refresh').click()
        expect(broken.locator('#status')).to_have_text('ERRO NA INTERFACE',timeout=8000)
        assert 'DADOS RECEBIDOS' in broken.locator('#connection-badge').inner_text()
        assert 'motor indisponível' not in broken.locator('#status').inner_text().lower()
        broken.close()
        # Simulate the dynamic Coherent wrapper nodes that the simulator inserts.
        # An earlier Alpha silently collapsed the iframe to a 120px strip even
        # though the server/browser tests had all passed.
        wrapper = (ROOT / 'in_game/toolbar/PackageSources/html_ui/'
                   'InGamePanels/FlightCare/FlightCare.html').read_text(encoding='utf-8')
        css = wrapper.split('<style>', 1)[1].split('</style>', 1)[0]
        probe = browser.new_page(viewport={'width':920,'height':640})
        probe.set_content(
            '<!doctype html><html><head><style>'+css+'</style></head><body '
            'style="margin:0"><div style="width:100vw;height:100vh">'
            '<ingame-ui id="FlightSimCarreira">'
            '<div class="ingameUiContent"><div class="ingameUiWrapper">'
            '<div id="flightSimContent"><iframe id="flightSimFrame" '
            'src="about:blank"></iframe></div></div></div>'
            '</ingame-ui></div></body></html>')
        for width,height in [(920,640),(580,440),(360,420)]:
            probe.set_viewport_size({'width':width,'height':height})
            size = probe.locator('#flightSimFrame').bounding_box()
            assert size is not None and size['height'] >= height * .85, (width,height,size)
            assert size['width'] >= width * .85, (width,height,size)
        probe.screenshot(path=str(OUTPUT/'ingame-sdk-wrapper-height.png'),full_page=True)
        probe.close()
        browser.close()
finally:
    bridge.stop()
print(json.dumps({'ingame':'ok','screenshots':str(OUTPUT)},ensure_ascii=False))
