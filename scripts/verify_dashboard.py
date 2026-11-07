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
            # NOAA prevalece sobre MSFS e a preferência explícita faz aparecer ambos.
            preferred=page.evaluate("""() => {
              const original=state;
              const sample={...original,mission:{...original.mission,destination:'SBJP'},
                weather:{destination_metar:{raw:'SBJP 270900Z 11008KT CAVOK'},
                  destination_sim:{wind_kt:14},show_sim_with_noaa:false}};
              renderWeather(sample);
              const defaultText=document.getElementById('weather-destination-values').textContent;
              renderWeather({...sample,weather:{...sample.weather,show_sim_with_noaa:true}});
              const withSim=document.getElementById('weather-destination-values').textContent;
              renderWeather(original);
              return {defaultText,withSim};
            }""")
            assert 'SBJP 270900Z' in preferred['defaultText'] and 'MSFS' not in preferred['defaultText'],preferred
            assert 'MSFS' in preferred['withSim'],preferred
            # 20% no painel; refuel é diálogo proposital, não navegação pop-up.
            warnings=page.evaluate("""() => {
              const original=state;
              render({...original,maintenance_alerts:{fuel_low:true,condition_low:true},
                plane:{...original.plane,condition:15},fuel:{...original.fuel,quantity:3,capacity:26}});
              const messages=document.getElementById('resource-alerts').textContent;
              render(original);return messages;
            }""")
            assert 'Combustível' in warnings and '20%' in warnings and 'Aeronave' in warnings,warnings
            page.evaluate("""() => {
              state={...state,connection:'connected',phase:'SOLO',
                fuel:{...state.fuel,quantity:12,capacity:26,refundable_liters:5}};
              openRefuelDialog();
            }""")
            assert page.locator('#refuel-dialog').is_visible()
            page.locator('#refuel-target').fill('20')
            assert 'Crédito:' in page.locator('#refuel-price').inner_text()
            page.locator('#refuel-cancel').click()
            assert not page.locator('#refuel-dialog').is_visible()

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
            assert page.locator('#detail-manifest-name').inner_text()
            assert 'kg' in page.locator('#detail-payload').inner_text()
            assert page.locator('#detail-nav-source').inner_text()
            assert 'R$' in page.locator('#detail-reward').inner_text()
            page.locator('#dialog-close').click()
            assert page.locator('.center-column .map-card #free-map').count()==1
            assert page.locator('#market-page').is_visible()
            assert page.locator('.nav-item').count()==11
            assert page.locator('.nav-item[data-action="freelance"]').count()==0
            assert page.locator('.nav-item[data-action="regional"]').inner_text()=='Mercado'
            page.locator('[data-market-view="freelance"]').click()
            assert page.locator('[data-market-view="freelance"]').get_attribute('aria-pressed')=='true'
            for offer in page.locator('#market-list .market-option').all():
                assert 'FREELANCER' in offer.inner_text()
            page.locator('[data-market-view="regional"]').click()
            assert page.locator('#market-list .market-option').count()>0
            # Bloco 1: frota usa página própria, não o módulo placeholder / loja.
            page.locator('.nav-item[data-action="fleet"]').click()
            assert page.locator('#fleet-page').is_visible()
            assert not page.locator('#module-page').is_visible()
            assert page.locator('.sidebar').is_visible()
            assert 'FROTA' in page.locator('#fleet-page-title').inner_text()
            assert page.locator('#fleet-list .fleet-item').count()==1
            assert page.locator('#fleet-name').inner_text()=='Cessna 152'
            assert page.locator('#fleet-active').is_visible()
            assert page.locator('#fleet-photo').is_visible()
            assert page.locator('#fleet-photo').evaluate('(e)=>getComputedStyle(e).objectFit')=='contain'
            assert page.locator('#fleet-use').is_disabled()
            assert page.locator('#fleet-upload').is_enabled()
            # Duas unidades do mesmo modelo são listadas independentemente;
            # foto personalizada deve refletir no quadro e Dashboard ativa.
            custom=page.evaluate("""() => {
              const original=state;
              const owned=state.fleet.owned;
              const twin={...owned[0],ref:'unit:98765',photo_url:'/c152.jpg?v=98765',
                          kind:'used',is_active:false,title:'Cessna 152 (teste)'};
              const synthetic={...state,fleet:{...state.fleet,owned:[...owned,twin]}};
              render(synthetic);
              const count=document.querySelectorAll('#fleet-list .fleet-item').length;
              document.querySelector('#fleet-list [data-fleet-ref="unit:98765"]').click();
              const result={count,selected:document.getElementById('fleet-name').textContent,
                img:document.getElementById('fleet-photo').getAttribute('src')};
              render(original);
              return result;
            }""")
            assert custom['count']==2,custom
            assert 'teste' in custom['selected'] and '98765' in custom['img'],custom
            assert page.locator('#fleet-list .fleet-item').count()==1
            photo=page.evaluate("""() => {
              const original=state;
              const file='/c152.jpg?v=simulated-unique';
              render({...original,plane:{...original.plane,photo_url:file}});
              const src=document.getElementById('aircraft-photo').getAttribute('src');
              const visible=!document.getElementById('aircraft-photo').hidden;
              const credit=document.getElementById('photo-credit').hidden;
              render(original);return {src,visible,credit};
            }""")
            assert photo['src']=="/c152.jpg?v=simulated-unique" and photo['visible'] and photo['credit'],photo
            # Mercado de aeronaves é página própria e não se mistura a contratos ou Hangar.
            page.locator('.nav-item[data-action="aircraft_market"]').click()
            assert page.locator('#aircraft-market-page').is_visible()
            assert not page.locator('#fleet-page').is_visible()
            assert not page.locator('#module-page').is_visible()
            assert page.locator('.sidebar').is_visible()
            assert page.locator('#am-list .aircraft-market-item').count()==5
            assert page.locator('#am-lock').is_visible()  # fixture tem contrato ativo
            assert page.locator('#am-confirm-open').is_disabled()
            for tab,value in [('used',5),('rent',5),('sell',1),('new',5)]:
                page.locator('[data-aircraft-market-tab="'+tab+'"]').click()
                assert page.locator('[data-aircraft-market-tab="'+tab+'"]').get_attribute('aria-pressed')=='true'
                assert page.locator('#am-list .aircraft-market-item').count()==value
            page.locator('[data-aircraft-market-tab="rent"]').click()
            page.locator('#am-duration').select_option('72')
            assert page.locator('#am-price').inner_text()
            # Simula só a cotação liberada e valida o modal sem pagar na carreira QA.
            quote=page.evaluate("""() => {
              const original=state;
              const m=original.aircraft_market;
              render({...original,aircraft_market:{...m,ready:true,reason:'',balance:10000000}});
              const enabled=!document.getElementById('am-confirm-open').disabled;
              const price=document.getElementById('am-price').textContent;
              const balance=document.getElementById('am-after').textContent;
              document.getElementById('am-confirm-open').click();
              const dialogOpen=document.getElementById('aircraft-checkout-dialog').open;
              const desc=document.getElementById('aircraft-checkout-description').textContent;
              document.getElementById('am-cancel').click();
              const dialogClosed=!document.getElementById('aircraft-checkout-dialog').open;
              render(original);
              return {enabled,price,balance,dialogOpen,dialogClosed,desc};
            }""")
            assert quote['enabled'] and quote['price'].startswith('R') and quote['balance'].startswith('R'),quote
            assert quote['dialogOpen'] and quote['dialogClosed'] and 'alugar' in quote['desc'],quote
            page.locator('[data-aircraft-market-tab="sell"]').click()
            assert page.locator('#am-confirm-open').is_disabled()
            page.locator('.nav-item[data-action="planning"]').click()
            assert 'PLANEJAMENTO' in page.locator('#flightops-title').inner_text()
            assert page.locator('#flightops-page').is_visible()
            assert not page.locator('#module-page').is_visible()
            assert page.locator('#flightops-map-slot #free-map').count()==1
            assert page.locator('#flightops-map-slot .map-area').is_visible()
            assert page.locator('.sidebar').is_visible()
            assert page.locator('#fo-waypoints').is_visible()
            # A fixture abre com contrato ativo: mude para voo livre antes de editar ICAOs.
            page.locator('#fo-free').click()
            # Rota direta antes do salvamento; a prévia vem do motor real.
            page.locator('#fo-origin').fill('SBRF')
            page.locator('#fo-destination').fill('SIPE')
            page.locator('#fo-plan').click()
            route_ready=False
            for _ in range(60):
                route_ready=page.evaluate("""() => {
                  const r=FSCFlightOps.mapState(state).mission;
                  return Boolean(r && r.route_points?.length===2);
                }""")
                if route_ready:break
                time.sleep(.1)
            assert route_ready,'Planejar rota deve desenhar SBRF → SIPE sem salvar'
            assert page.locator('#fo-distance').inner_text().endswith('NM')
            # Clique direito usa o mesmo handler proposeWaypoint, sem popup.
            proposed=page.evaluate("() => FSCFlightOps.proposeWaypoint(-8.20,-34.95)")
            assert proposed and not page.locator('#fo-map-point-dialog').is_visible()
            assert 'FSC01' in page.locator('#fo-waypoints').inner_text()
            assert page.evaluate("() => FSCFlightOps.mapState(state).mission.route_points.length")==3
            # Arrastar solta na nova posição (mesmo método do dragend MapLibre/SVG).
            moved=page.evaluate("() => FSCFlightOps.moveWaypoint(0,-8.15,-34.85)")
            assert moved
            assert '-8,15' in page.locator('#fo-waypoints').inner_text()
            before_save=page.evaluate("""() => ({
              draft:JSON.stringify(state.flight_operations.draft),
              points:FSCFlightOps.mapState(state).mission.route_points
            })""")
            assert abs(before_save['points'][1][0]-(-8.15))<1e-6,before_save
            page.locator('#fo-waypoints button').first.click()
            assert page.evaluate("() => FSCFlightOps.mapState(state).mission.route_points.length")==2
            assert page.evaluate("() => JSON.stringify(state.flight_operations.draft)")==before_save['draft']
            page.locator('#fo-fix-label').fill('FSC01')
            page.locator('#fo-fix-lat').fill('-8.1')
            page.locator('#fo-fix-lon').fill('-34.9')
            page.locator('#fo-add-fix').click()
            assert 'FSC01' in page.locator('#fo-waypoints').inner_text()
            assert 'PRÉVIA' in page.locator('#fo-status').inner_text()
            page.locator('#fo-waypoints button').first.click()
            assert 'FSC01' not in page.locator('#fo-waypoints').inner_text()
            page.locator('.nav-item[data-action="dashboard"]').click()
            assert page.locator('.center-column .map-card #free-map').count()==1
            # Pilot Career: página nativa, abas, distintivos SVG e modal do gerenciador.
            page.locator('.nav-item[data-action="pilot"]').click()
            assert page.locator('#pilot-career-page').is_visible()
            assert not page.locator('#module-page').is_visible()
            assert page.locator('#pc-main-rank svg').count()==1
            assert page.locator('#pc-medal-gallery').count()==1
            page.locator('[data-pc-tab="achievements"]').click()
            assert page.locator('#pc-medal-gallery .pc-achievement').count()>=10
            assert page.title().startswith('FlightSim')
            assert page.locator('.brand strong').inner_text()=='FlightSim'
            assert page.locator('symbol#i-plane path').count()==1
            for code,number in [('first_plane','1º'),('first_flight','1º'),
                                ('hundred_hours','100h'),('reputation70','70%'),
                                ('reputation90','90%')]:
                medal=page.locator('#pc-medal-gallery svg.pc-medal-'+code)
                assert medal.count()==1
                assert number in medal.locator('text').all_text_contents()
            assert page.locator('#pc-medal-gallery svg.pc-medal-first_plane use[href="#i-plane"]').count()==1
            # Medalhas devem contar a conquista pela própria arte, não só pela cor.
            assert page.locator('#pc-medal-gallery svg.pc-medal-first_plane').count()==1
            assert page.locator('#pc-medal-gallery svg.pc-medal-three_planes').count()==1
            assert '90%' in page.locator('#pc-medal-gallery svg.pc-medal-reputation90').text_content()
            assert '70%' in page.locator('#pc-medal-gallery svg.pc-medal-reputation70').text_content()
            page.locator('[data-pc-tab="licenses"]').click()
            assert page.locator('#pc-license-grid .pc-license').count()==5
            assert page.locator('#pc-license-grid .pc-license-seal-svg use[href="#i-plane"]').count()==5
            for tier in range(1,6):
                assert page.locator(f'#pc-license-grid .pc-license-tier-{tier} .pc-license-emblem svg').count()==1
                assert page.locator(f'#pc-license-grid .pc-license-tier-{tier} .pc-license-stamp').count()==1
            page.locator('[data-pc-tab="graphs"]').click()
            # Gráficos são derivados de histórico real; sem voos não há barras.
            # Alimentar SOMENTE o DOM do teste com dados sintéticos (sem SQLite).
            page.evaluate("""() => {
              const demo=structuredClone(state);
              demo.pilot_career.flights=(demo.pilot_career.flights||0)+100;
              demo.pilot_career.graphs={
                landings:[{fpm:-198},{fpm:-265},{fpm:-142},{fpm:-311}],
                contracts:[['2026-10',2],['2026-11',3]],
                hours_by_aircraft:[['Cessna 152',3.5],['Baron G58',1.7]]
              };
              FSCPilotCareer.render(demo);
            }""")
            assert page.locator('#pc-graphs .pc-chart-card').count()==3
            assert page.locator('#pc-graphs .pc-chart-unit').count()==3
            assert page.locator('#pc-graphs .pc-chart-legend').count()==3
            assert page.locator('#pc-graphs .pc-chart-card').first.locator('svg text').count()>=5
            assert page.locator('#pc-graphs .pc-chart-summary').count()==3
            assert page.locator('#pc-graphs .pc-chart-breakdown').count()>=1
            page.locator('[data-pc-tab="timeline"]').click()
            assert page.locator('#pc-timeline-list').is_visible()
            page.locator('#pc-manage-profiles').click()
            assert page.locator('#pc-profiles-dialog').is_visible()
            assert page.locator('#pc-new-name').input_value()=='Teste'
            assert page.locator('#pc-new-admin').is_checked()
            page.locator('#pc-close-profiles').click()
            assert not page.locator('#pc-profiles-dialog').is_visible()
            # Estados Admin são somente DOM sintético, nunca SQLite.
            # O polling pode redesenhar o piloto oficial enquanto o teste
            # aguarda uma animação; manter a fixture APENAS na página Playwright.
            page.evaluate("""() => {
              const renderOriginal=FSCPilotCareer.render;
              FSCPilotCareer.render=(fresh)=>{
                const clone=structuredClone(fresh);
                clone.pilot_career.is_test=true;
                clone.pilot_career.showcase={level:90,xp:500000,reputation:90,
                  achievements:{veteran:'earned'},licenses:{PLA:'earned'},rank:'marechal'};
                renderOriginal(clone);
              };
              FSCPilotCareer.render(state);
            }""")
            page.locator('[data-pc-tab="admin"]').click()
            assert page.locator('#pc-admin-rank-gallery .pc-gallery-rank').count()==18
            page.locator('#pc-admin-preview-loss').click()
            assert page.locator('#pc-unlock').is_visible()
            assert page.locator('#pc-unlock .pc-fragment-left').count()==1
            # A animação dura pouco, mas o diálogo nunca fecha sozinho.
            page.wait_for_timeout(2800)
            assert page.locator('#pc-unlock').is_visible()
            page.locator('#pc-unlock-dismiss').click()
            assert not page.locator('#pc-unlock').is_visible()
            page.evaluate("() => FSCPilotCareer.showUnlock('recovery','Reputação 90','reputation90')")
            assert 'CONQUISTA RECUPERADA' in page.locator('#pc-unlock-kicker').inner_text()
            page.locator('#pc-close-unlock').click()
            page.locator('#pc-admin-preview-promotion').click()
            assert page.locator('#pc-unlock-art svg.pc-rank-svg').count()==1
            page.locator('#pc-close-unlock').click()
            assert page.locator('#pc-rank-fallback').count()==0
            assert page.locator('#pc-header-rank svg').count()==1
            page.locator('[data-pc-tab="overview"]').click()
            for width,height in [(1280,720),(1600,900),(1920,1080)]:
                page.set_viewport_size({'width':width,'height':height})
                page.wait_for_timeout(130)
                assert page.locator('#pilot-career-page').is_visible()
                assert page.locator('#pc-hero').count()==0  # CSS class, not duplicate node
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.screenshot(path=str(OUTPUT/f'pilot-career-{width}x{height}.png'))
            page.set_viewport_size({'width':1600,'height':900})
            # Financial Center: 5 abas nativas; fixture somente DOM, sem mover dinheiro.
            page.locator('.nav-item[data-action="finance"]').click()
            assert page.locator('#financial-center-page').is_visible()
            assert not page.locator('#module-page').is_visible()
            assert page.locator('.fin-tabs button').count()==5
            page.evaluate("""() => {
              const original=FSCFinancialCenter.render;
              FSCFinancialCenter.render=(incoming,force)=>{
                const clone=structuredClone(incoming);
                clone.financial_center={
                  ...clone.financial_center, balance:26284,income:15400,expenses:4100,
                  operating_net:11300,assets_value:97500,invested:145000,net_worth:114984,
                  debt:8800,loan_open:true,contracts_completed:4,total_transactions:2,
                  expense_categories:[{kind:'seguro',label:'Seguro de aeronave',value:220},
                    {kind:'abastecimento',label:'Abastecimento',value:550}],
                  monthly:[{month:'2026-10',income:6200,expense:1800},
                           {month:'2026-11',income:9200,expense:2300}],
                  transactions:[
                    {id:2,event_key:'insurance:1',kind:'seguro',label:'Seguro de aeronave',
                      category:'operacional',amount:-220,balance_after:26284,
                      description:'Apólice C152',occurred_utc:1794000000},
                    {id:1,event_key:'contract:1',kind:'contrato',label:'Contrato',
                      category:'receita',amount:1550,balance_after:26504,
                      description:'Contrato SBRF → SBJP',occurred_utc:1793900000}],
                  operations:[{id:1,flight_key:'test-flight',started_utc:1793900000,
                    ended_utc:1793901200,mission:'REG-SBRF-SBJP',aircraft:'Cessna 152',
                    gross:1550,expenses:210,net:1340,bonus:0,fuel:140,airport:70,tax:0,
                    paid:true}],
                  assets:[{ref:'unit:1',title:'Cessna 172 Skyhawk',kind:'new',
                    purchase_price:145000,resale_price:97500,condition:98,
                    airport:'SBRF',insured:true}]
                };
                original(clone,force);
              };
              FSCFinancialCenter.render(state,true);
            }""")
            assert '26.284' in page.locator('#fin-balance').inner_text()
            assert '11.300' in page.locator('#fin-net').inner_text()
            assert page.locator('#fin-monthly-chart svg rect').count()==4
            assert 'Seguro' in page.locator('#fin-expense-chart').inner_text()
            page.locator('[data-fin-tab="statement"]').click()
            assert page.locator('#fin-transactions tr.fin-transaction').count()==2
            page.locator('#fin-category').select_option('operacional')
            assert page.locator('#fin-transactions tr.fin-transaction').count()==1
            page.locator('#fin-transactions tr.fin-transaction').first.click()
            assert page.locator('#fin-receipt').is_visible()
            assert 'Apólice C152' in page.locator('#fin-receipt-body').inner_text()
            page.locator('#fin-receipt-close').click()
            page.locator('#fin-category').select_option('all')
            page.locator('[data-fin-tab="flights"]').click()
            assert page.locator('.fin-operation').count()==1
            assert '1.340' in page.locator('.fin-operation').inner_text()
            page.locator('[data-fin-tab="assets"]').click()
            assert '97.500' in page.locator('#fin-resale').inner_text()
            assert 'Segurada' in page.locator('#fin-assets-list').inner_text()
            page.locator('[data-fin-tab="bank"]').click()
            assert page.locator('#fin-take-loan').is_disabled()
            page.locator('[data-fin-loan-preset="150000"]').click()
            assert '162.000' in page.locator('#fin-loan-total').inner_text()
            page.locator('#fin-repay-value').fill('1000')
            assert '7.800' in page.locator('#fin-repay-after').inner_text()
            page.locator('#fin-repay').click()
            assert page.locator('#fin-confirm').is_visible()
            page.locator('#fin-confirm-cancel').click()  # Sem cobrança real.
            for width,height in [(1280,720),(1600,900),(1920,1080)]:
                page.set_viewport_size({'width':width,'height':height})
                page.wait_for_timeout(130)
                assert page.locator('#financial-center-page').is_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.screenshot(path=str(OUTPUT/f'financial-center-{width}x{height}.png'))
            page.set_viewport_size({'width':1600,'height':900})
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
            assert heading['before'] and 'rotate(15)' in heading['before'],heading
            assert heading['after'] and 'rotate(135)' in heading['after'],heading
            # Render e leitura devem ocorrer no MESMO frame JS: o poll do
            # snapshot roda a cada 500ms e pode substituir o texto entre
            # duas leituras Playwright (falso negativo intermitente).
            heading_label=page.evaluate("""() => {
              renderMap({...state,mode:'MSFS',telemetry:{
                lat:-8.12,lon:-34.92,heading_deg:301,heading_magnetic_deg:322,stale:false}});
              return document.getElementById('map-mode').innerText;
            }""")
            assert '322° MAG' in heading_label,heading_label
            assert '301° TRUE' in heading_label,heading_label

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
            assert 'rotate(15deg)' in orientations['before'],orientations
            assert 'rotate(135deg)' in orientations['after'],orientations
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
