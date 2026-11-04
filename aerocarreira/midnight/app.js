'use strict';
const token=location.hash.slice(1);history.replaceState(null,'',location.pathname);
const $=id=>document.getElementById(id),money=n=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL',maximumFractionDigits:0}).format(n),number=(n,d=0)=>Number(n).toLocaleString('pt-BR',{maximumFractionDigits:d}),text=(id,v)=>$(id).textContent=v;
const icon=n=>{const s=document.createElementNS('http://www.w3.org/2000/svg','svg'),u=document.createElementNS(s.namespaceURI,'use');u.setAttribute('href','#i-'+n);s.append(u);return s};
const node=(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=value;return e};
let state={},zoom=1,mapPanX=0,mapPanY=0,selectedOffer=null,lastOfferKey='',pollFailures=0,planeTrack=null,planeBearing=0,recenterPlane=false,marketFilter='all',marketLastKey='';
const nav=[['home','Dashboard','dashboard'],['plane','Missões e Contratos','market'],['globe','Mercado Regional','market'],['hangar','Frota / Hangar','fleet'],['map','Planejamento de Voo','planning'],['pilot','Meu Piloto','pilot'],['coins','Finanças','finance'],['building','Companhias','employment'],['book','Logbook','history'],['chart','Análise e Relatórios','reports'],['gear','Configurações','settings']];
for(const [ic,label,action] of nav){const b=node('button','nav-item'+(action==='dashboard'?' active':''));b.append(icon(ic),node('span','',label));b.dataset.action=action;$('navigation').append(b)}
const metricNames=[['ias','gauge','Velocidade (IAS)','kt'],['gs','gauge','Velocidade (GS)','kt'],['alt','mountain','Altitude (MSL)','ft'],['agl','layers','Altura (AGL)','ft'],['vs','arrows','Razão Vertical','ft/min'],['phase','plane','Fase do Voo','']];
for(const [key,ic,label] of metricNames){const m=node('div','metric');m.append(icon(ic));const v=node('strong','','—');v.id='metric-'+key;m.append(v,node('small','',label));$('metrics').append(m)}
function toast(message){text('toast',message);$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),4000)}
async function command(action,id){try{const r=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json','X-Flight-Token':token},body:JSON.stringify(id!==undefined?{action,id}:{action})});if(!r.ok)throw Error();if(!['refresh','close'].includes(action))toast('Solicitação enviada ao aplicativo.');}catch{toast('Não foi possível enviar. Verifique se o aplicativo está aberto.')}}
document.addEventListener('click',e=>{const b=e.target.closest('[data-action]');if(b){if(b.dataset.action==='dashboard')return;if(b.dataset.action==='market'){openMarket();return;}command(b.dataset.action)}const tab=e.target.closest('[data-tab]');if(tab&&tab.dataset.tab==='weather')showDetails('METEOROLOGIA • MSFS / NOAA',weatherDetails());});
function showDetails(title,body,offer){text('dialog-title',title);text('dialog-text',body);selectedOffer=offer||null;$('dialog-accept').hidden=!offer;$('dialog-accept').disabled=!!offer&&!offer.allowed;$('details').showModal()}
$('dialog-close').onclick=()=>$('details').close();$('dialog-accept').onclick=()=>{if(selectedOffer?.allowed){command('offer',selectedOffer.id);$('details').close();if($('market-dialog').open)$('market-dialog').close()}};
function bar(id,ratio){$(id).style.width=(Math.min(1,Math.max(0,ratio||0))*100)+'%'}
function renderOffers(s){const key=JSON.stringify([s.offers,s.mission?.id]);if(key===lastOfferKey)return;lastOfferKey=key;$('offers').replaceChildren();const offers=s.offers.slice(0,5);if(!offers.length){const empty=node('div','empty');empty.append(icon('globe'),node('span','',s.pilot?'Sem propostas disponíveis. Atualize o mercado ou confira sua base e habilitações.':'Cadastre seu piloto para descobrir os contratos da região.'));$('offers').append(empty);return}
for(const o of offers){const b=node('button','offer'+(s.mission?.id===o.id?' active':'')+(!o.allowed?' locked':''));b.append(icon(o.category.toLowerCase().includes('carga')?'box':'plane'));const d=node('div');d.append(node('strong','',o.category));const meta=node('div','offer-meta');meta.append(node('span','',o.origin+' → '+o.destination),node('span','price',money(o.reward)));d.append(meta,node('small','duration',(o.minutes===null?'—':'~ '+Math.floor(o.minutes/60)+'h'+String(o.minutes%60).padStart(2,'0'))+(!o.allowed?' • Bloqueado':'')));b.append(d);b.onclick=()=>showDetails(o.category,o.origin+' → '+o.destination+'\nPagamento bruto: '+money(o.reward)+'\n'+(o.distance===null?'Distância indisponível':number(o.distance)+' NM • '+o.minutes+' min')+'\n\n'+o.reason,o);$('offers').append(b)}}

function openMarket(filter='all'){
  marketFilter=filter;marketLastKey='';
  $('market-search').value='';
  renderMarketDialog(state,true);
  if(!$('market-dialog').open)$('market-dialog').showModal();
}
function renderMarketDialog(s,force=false){
  if(!s?.offers||(!force&&!$('market-dialog').open))return;
  const key=JSON.stringify([s.offers,s.mission?.id,marketFilter,$('market-search').value.trim()]);
  if(!force&&key===marketLastKey)return;
  marketLastKey=key;
  const search=$('market-search').value.trim().toLocaleLowerCase('pt-BR');
  document.querySelectorAll('[data-market-filter]').forEach(button=>{
    const on=button.dataset.marketFilter===marketFilter;
    button.classList.toggle('selected',on);button.setAttribute('aria-pressed',String(on));
  });
  const location=s.market?s.market.icao+' • '+s.market.name:'Base não cadastrada';
  text('market-dialog-base',location+'  |  Piloto '+(s.pilot?.callsign||'não cadastrado'));
  const items=s.offers.filter(o=>(marketFilter==='all'||(marketFilter==='freelance'?
     o.freelance:!o.freelance))&&(!search||[o.title,o.category,o.origin,o.destination,
      o.freelance?'freelancer':'regional'].join(' ').toLocaleLowerCase('pt-BR').includes(search)));
  $('market-list').replaceChildren();
  if(!items.length){
    $('market-list').append(node('p','market-empty',
      search?'Nenhum contrato corresponde à busca.':
      marketFilter==='freelance'?'Nenhuma oferta freelancer disponível nesta região e nível.':
      'Nenhuma missão disponível. Confira aeroporto-base, nível e habilitações.'));
    return;
  }
  for(const o of items){
    const item=node('button','market-option'+(!o.allowed?' locked':''));
    item.type='button';item.dataset.offerId=o.id;
    const title=node('div','offer-line');
    title.append(node('strong','',o.origin+' → '+o.destination),node('span','market-pay',money(o.reward)));
    const chip=node('div','type-chip'+(o.freelance?' freelance':''),o.category+(o.freelance?'  •  FREELANCER':''));
    item.append(title,chip);
    item.append(node('small','',o.title||'Missão regional'));
    const plane=o.freelance?(' • Aeronave fornecida pelo contratante: '+(o.employer_plane||'conforme contrato')):'';
    const time=o.minutes!=null?' • ~'+Math.floor(o.minutes/60)+'h'+String(o.minutes%60).padStart(2,'0'):'';
    item.append(node('small','',time+plane));
    if(!o.allowed)item.append(node('small','',o.reason||'Requisitos do piloto insuficientes'));
    if(s.mission&&s.mission.id!==o.id)item.append(node('small','', 'Conclua ou cancele o contrato atual antes de aceitar outro.'));
    item.onclick=()=>showDetails(o.category+(o.freelance?' • Freelancer':''),
      o.origin+' → '+o.destination+'\nPagamento bruto: '+money(o.reward)+
      '\n'+(o.distance==null?'Distância indisponível':number(o.distance)+' NM')+
      plane+'\n\n'+(o.reason||'A aceitação será validada pelo motor da carreira.'),Object.assign({},o,{allowed:o.allowed&&(!s.mission||s.mission.id===o.id)}));
    $('market-list').append(item);
  }
}
$('market-dialog-close').onclick=$('market-dialog-done').onclick=()=>$('market-dialog').close();
$('market-refresh').onclick=()=>command('refresh');
$('market-search').addEventListener('input',()=>renderMarketDialog(state,true));
document.querySelectorAll('[data-market-filter]').forEach(b=>b.onclick=()=>{
 marketFilter=b.dataset.marketFilter;renderMarketDialog(state,true);
});

function renderSummary(s){
  const rep=s.summary?.reputation?.score;
  const band=s.summary?.reputation?.band||'neutral';
  const entries=[['plane','Voos realizados',s.summary.flights],
    ['clock','Horas de voo',number(s.summary.hours,1)+' h'],
    ['layers','Resultado operacional',money(s.summary.net),'money'],
    ['badge','Bônus de realismo',money(s.summary.bonus),'money'],
    ['pilot','Reputação',Number.isFinite(rep)?rep+'%':'Indisponível','reputation rep-'+band]];
  $('summary').replaceChildren();
  for(const [ic,label,v,c] of entries){
    const row=node('div','summary-row '+(c||''));
    row.append(icon(ic),node('span','',label),node('b','',v));
    if(label==='Reputação'&&Number.isFinite(rep)){
      row.style.setProperty('--rep-percentage',Math.max(0,Math.min(100,rep))+'%');
      row.style.setProperty('--rep-color',{good:'#80ef65',neutral:'#35d6ff',warning:'#f4be4b',critical:'#f86b72'}[band]||'#35d6ff');
    }
    $('summary').append(row);
  }
  bar('summary-progress',s.progress.fraction);
}
function weatherSummary(w){
 if(!w)return 'Sem dados confirmados';
 const parts=[];
 if(w.wind_direction!=null&&w.wind_kt!=null)parts.push(Math.round(w.wind_direction)+'° / '+number(w.wind_kt)+' kt');
 if(w.temperature_c!=null)parts.push(number(w.temperature_c,1)+' °C');
 if(w.sea_level_pressure_hpa!=null)parts.push(number(w.sea_level_pressure_hpa,0)+' hPa');
 if(w.visibility_m!=null)parts.push(number(w.visibility_m/1000,1)+' km vis.');
 if(w.raw&&!parts.length)parts.push(w.raw.slice(0,60));
 return parts.join(' • ')||'Dados parciais';
}
function weatherDetails(){
 const w=state.weather||{},a=state.mission?.origin||'—',b=state.mission?.destination||'—';
 const o=w.origin,n=w.destination_metar,d=w.destination_sim;
 return 'ORIGEM '+a+' — MSFS (condições junto à aeronave)\n'+(o?weatherSummary(o):'Sem leitura perto da origem')+
  '\n\nDESTINO '+b+' — NOAA METAR OFICIAL\n'+(n?(n.raw||weatherSummary(n)):'Sem METAR disponível para este aeroporto')+
  (n?.stale?'\nObservação em cache (pode estar desatualizada).':'')+
  '\n\nDESTINO — MSFS (ao aproximar-se até 10 NM)\n'+(d?weatherSummary(d):'Aguardando aproximação')+
  '\n\nSimConnect não fornece texto METAR completo; clima selecionado no MSFS pode diferir da NOAA.';
}
function renderWeather(s){
 const w=s.weather||{},o=w.origin,n=w.destination_metar,d=w.destination_sim;
 text('weather-origin','ORIGEM • MSFS '+(s.mission?.origin||'—'));
 text('weather-origin-values',o?weatherSummary(o):'Aguardando condições do MSFS na origem');
 text('weather-destination','DESTINO • NOAA '+(s.mission?.destination||'—'));
 text('weather-destination-values',d?'MSFS: '+weatherSummary(d)+' • NOAA: '+(n?.raw||'indisponível').slice(0,55):
  n?(n.raw||'METAR disponível').slice(0,80):'Aguardando METAR NOAA • sem estação?');
}
function render(s){state=s;if(!s.progress)return;const p=s.pilot;const country=s.country==='BR'?'':s.country?' · '+s.country:'';text('callsign',(p?.callsign||'CADASTRAR PILOTO')+country);if(s.country==='BR'){const flag=node('span','flag-br');flag.title='Brasil • país da base';$('callsign').append(flag)}text('qualification',p?({autonomo:'Piloto autônomo',empregado:'Piloto empregado',proprietario:'Companhia própria'}[s.employment]||s.employment)+' • '+s.summary.qualifications.join(' / '):'Crie sua carreira');text('level',p?'NÍVEL '+s.progress.level:'NÍVEL —');text('xp',p?'XP '+s.progress.xp+' / '+s.progress.target+' ('+Math.round(s.progress.fraction*100)+'%)':'XP —');bar('xpbar',s.progress.fraction);text('balance',money(s.balance));text('connection',{connected:'Conectado',reconnecting:'Reconectando',disconnected:'Desconectado'}[s.connection]);$('led').style.background={connected:'#86fc24',reconnecting:'#ffc400',disconnected:'#e06a75'}[s.connection];$('avatar').hidden=!s.avatar;if(s.avatar&&$('avatar').src!==s.avatar)$('avatar').src=s.avatar;
text('market-base',s.market?s.market.icao+' — '+s.market.name:'Cadastre sua base');renderOffers(s);renderMarketDialog(s);renderSummary(s);
const m=s.mission;const bonus=s.bonus?.bonus_fraction||0;text('route',m?m.origin+' → '+m.destination:'Selecione uma missão');text('distance',m?'Distância: '+(m.distance===null?'—':number(m.distance)+' NM')+'  |  Prev. voo: '+(m.minutes===null?'—':m.minutes+' min'):'Explore o mercado regional para começar');text('category',m?.category||'');text('reward',m?money(m.reward):'—');text('bonus-value',m?'+'+number(bonus*100,1)+'%':'—');text('mission-status',m?(s.bonus?.frozen?'EM VOO • CONGELADO':'RESERVADO'):'');
for(const [key,, ,unit] of metricNames){const e=$('metric-'+key);if(key==='phase'){e.textContent=s.phase;e.style.color='#8df63e';continue}e.replaceChildren(document.createTextNode(s.telemetry?number(s.telemetry[key]):'—'),node('small','',' '+unit))}text('telemetry-status',s.mode==='Demo'?'DEMONSTRAÇÃO':s.telemetry?.stale?'ÚLTIMA LEITURA • SEM ATUALIZAÇÃO':s.connection==='connected'?'':'AGUARDANDO MSFS');renderWeather(s);text('log',s.log.slice(-8).join('\n'));$('log').scrollTop=$('log').scrollHeight;text('realism-total',m?'+'+number(bonus*100,1)+'%':'—');
const labels=['Clima ao vivo','Horário real','Assistências realistas','Pista e iluminação','Rota revisada','Combustível adequado','Peso dentro do limite'];const components=Object.values(s.bonus?.components||{});$('checklist').replaceChildren();labels.forEach((label,i)=>{const ok=components[i]?.ok;const e=node('div',ok?'ok':'');e.append(icon('check'),node('span','',label));e.title=(components[i]?'+'+number(components[i].rate*100,1)+'% • ':'')+(i<5?'Declaração do piloto':'Telemetria/estimativa');$('checklist').append(e)});text('edit-plan',s.bonus?.frozen?'Congelado na decolagem • Ver despacho':'Revisar no despacho →');
const a=s.plane;const photo=a?.code==='c152';$('aircraft-photo').hidden=!photo;$('photo-credit').hidden=!photo;document.querySelector('.aircraft-art').classList.toggle('has-photo',photo);document.querySelector('.aircraft-art>svg').style.display=photo?'none':'';document.querySelector('.aircraft-art>span').hidden=photo;text('aircraft-name',a?.title||'Nenhuma aeronave');text('aircraft-ref',a?a.ref+' • '+a.kind:'Selecione no Hangar');document.querySelectorAll('[data-action=refuel],[data-action=service]').forEach(b=>{b.disabled=!!a?.ref.startsWith('contract:');b.title=b.disabled?'Aeronave fornecida pelo contratante':''});text('location',a?.airport||'—');text('condition',a?.condition!==null&&a?number(a.condition,1)+'%':'Indisponível');bar('conditionbar',a?a.condition/100:0);$('conditionbar').style.background=a?.condition<40?'#ef6464':a?.condition<75?'#ffc400':'';const f=s.fuel;const q=f.quantity;const ratio=q!==null&&f.capacity?q/f.capacity:null;text('fuel-value',q!==null?number(q,1)+' gal'+(ratio!==null?' ('+number(ratio*100)+'%)':''):'Sem leitura validada');bar('fuelbar',ratio);text('fuel-title','Controle: '+(f.enabled?'ATIVO':'DESLIGADO'));text('fuel-status',f.enabled?(s.connection==='connected'?'Confira a confirmação no registro':'Aguardando MSFS • sem confirmação'):'Penalidade de 30% em R$ e XP');$('fuel-toggle').classList.toggle('on',f.enabled);text('connection-hint',s.mode==='Demo'?'DEMONSTRAÇÃO • Telemetria simulada':s.connection==='connected'?s.status:'Conecte ao MSFS em Configurações.');renderMap(s)}
function svgNode(tag,attrs,textValue){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs||{}))e.setAttribute(k,v);if(textValue!==undefined)e.textContent=textValue;return e}
function renderMap(s){
  window.FSCFreeMap?.render(s);
  if(window.FSCFreeMap?.isActive()){
    text('map-mode',s.telemetry?.stale?'POSIÇÃO DESATUALIZADA':s.telemetry?.heading_deg!=null?'PROA '+String(Math.round(s.telemetry.heading_deg)).padStart(3,'0')+'° • MSFS':s.telemetry?'POSIÇÃO MSFS':'MAPA E ROTA');
    return;
  }
  const svg=$('route-map');svg.replaceChildren();const m=s.mission;const points=[];if(!m&&!s.telemetry&&s.market)points.push({lat:s.market.lat,lon:s.market.lon,label:s.market.icao,type:'airport'});if(m?.start)points.push({lat:m.start[0],lon:m.start[1],label:m.origin,type:'airport'});if(m?.end)points.push({lat:m.end[0],lon:m.end[1],label:m.destination,type:'airport'});if(s.telemetry)points.push({lat:s.telemetry.lat,lon:s.telemetry.lon,label:s.mode==='Demo'?'DEMO':'AERONAVE',type:'plane'});if(!points.length){svg.append(svgNode('text',{x:450,y:160,'text-anchor':'middle',fill:'#a4c2d0',stroke:'none','font-size':18},'Selecione um contrato para visualizar a rota'));svg.append(svgNode('text',{x:450,y:190,'text-anchor':'middle',fill:'#5c8c9d',stroke:'none','font-size':12},'Mapa offline • nenhuma rota fictícia'));return}
const lat0=(Math.max(...points.map(p=>p.lat))+Math.min(...points.map(p=>p.lat)))/2;const lon0=(Math.max(...points.map(p=>p.lon))+Math.min(...points.map(p=>p.lon)))/2;const cos=Math.max(.05,Math.cos(lat0*Math.PI/180));const xspan=Math.max(.2,...points.map(p=>Math.abs(p.lon-lon0)*cos*2)),yspan=Math.max(.15,...points.map(p=>Math.abs(p.lat-lat0)*2));const scale=Math.min(700/xspan,230/yspan)*zoom;
if(recenterPlane&&s.telemetry){
  // Centraliza o avião na projeção SVG local, mesmo com missão aberta.
  mapPanX=-(s.telemetry.lon-lon0)*cos*scale;
  mapPanY=(s.telemetry.lat-lat0)*scale;
  recenterPlane=false;
}
const xy=p=>[450+(p.lon-lon0)*cos*scale+mapPanX,170-(p.lat-lat0)*scale+mapPanY];
// Mapa local interativo (offline) permanece disponível quando não há chave Google.
const loaded=0;
document.querySelector('.map-caption').textContent='MAPA LOCAL • COORDENADAS REAIS';
for(let x=30;x<900;x+=60)svg.append(svgNode('line',{x1:x,y1:0,x2:x,y2:340,stroke:'#49636b','stroke-width':.5,opacity:loaded?.18:1}));for(let y=20;y<340;y+=40)svg.append(svgNode('line',{x1:0,y1:y,x2:900,y2:y,stroke:'#49636b','stroke-width':.5,opacity:loaded?.18:1}));
for(let x=90;x<900;x+=180)svg.append(svgNode('text',{x,y:328,fill:'#557f8c',stroke:'none','font-size':10,'text-anchor':'middle'},(lon0+(x-450-mapPanX)/cos/scale).toFixed(2)+'°'));
for(let y=60;y<300;y+=80)svg.append(svgNode('text',{x:8,y,fill:'#557f8c',stroke:'none','font-size':10},(lat0-(y-170-mapPanY)/scale).toFixed(2)+'°'));
if(m?.start&&m?.end){const a=xy(points[0]),b=xy(points[1]);svg.append(svgNode('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:'#00e9f9','stroke-width':9,opacity:.12}));svg.append(svgNode('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:'#00e9f9','stroke-width':3}))}
for(const p of points){const [x,y]=xy(p);if(x<20||x>880||y<20||y>315)continue;if(p.type==='plane'){
  const current={lat:p.lat,lng:p.lon};
  if(planeTrack&&window.FSCFreeMap&&
    Math.hypot((current.lat-planeTrack.lat)*111000,(current.lng-planeTrack.lng)*111000*Math.cos(current.lat*Math.PI/180))>25){
    planeBearing=window.FSCFreeMap.bearing(planeTrack,current);
  }
  planeTrack=current;
  if(Number.isFinite(s.telemetry?.heading_deg))planeBearing=s.telemetry.heading_deg;
  const planeSize=25;
  const g=svgNode('g',{transform:`translate(${x},${y}) rotate(${planeBearing-45}) scale(${planeSize/260}) translate(-157,-160)`,'data-heading':Number.isFinite(s.telemetry?.heading_deg)?String(s.telemetry.heading_deg):'indisponível'});
  g.append(svgNode('path',{d:window.FSCFreeMap?.aircraftPath||'M0 0',fill:'#35d6ff',stroke:'#d9fcff','stroke-width':1}));
  svg.append(g);
}else{svg.append(svgNode('circle',{cx:x,cy:y,r:14,fill:'#00d7ec',opacity:.13,stroke:'none'}));svg.append(svgNode('circle',{cx:x,cy:y,r:8,fill:'#06cfe4',stroke:'#ebfcff','stroke-width':3}));const labelY=y>55?y-36:y+21;svg.append(svgNode('rect',{x:x-31,y:labelY,width:62,height:24,rx:5,fill:'#031016',stroke:'#8fa6a9'}));svg.append(svgNode('text',{x,y:labelY+17,'text-anchor':'middle',fill:'#f4f9fc',stroke:'none','font-size':15,'font-weight':700},p.label))}}
const nm=60*90/scale;svg.append(svgNode('path',{d:'M760 294v6h90v-6',stroke:'#b9dce8','stroke-width':2}));svg.append(svgNode('text',{x:805,y:288,'text-anchor':'middle',fill:'#c9e3ed',stroke:'none','font-size':12},number(nm,1)+' NM'));text('map-mode',s.mode==='Demo'?'DEMONSTRAÇÃO':s.telemetry?.stale?'POSIÇÃO DESATUALIZADA':s.telemetry?'POSIÇÃO MSFS':'ROTA PLANEJADA')}
$('zoom-in').onclick=()=>{if(window.FSCFreeMap?.zoomBy(1))return;zoom=Math.min(16,zoom*1.3);renderMap(state)};
$('zoom-out').onclick=()=>{if(window.FSCFreeMap?.zoomBy(-1))return;zoom=Math.max(.2,zoom/1.3);renderMap(state)};
$('recenter').onclick=()=>{if(window.FSCFreeMap?.recenter(state))return;if(state.telemetry){recenterPlane=true}else{zoom=1;mapPanX=mapPanY=0;}renderMap(state)};
const mapSvg=$('route-map');
mapSvg.addEventListener('wheel',e=>{if(window.FSCFreeMap?.isActive())return;
  e.preventDefault();zoom=Math.min(16,Math.max(.2,zoom*(e.deltaY<0?1.18:1/1.18)));renderMap(state);
},{passive:false});
let drag=null;
mapSvg.addEventListener('pointerdown',e=>{if(e.button!==0||window.FSCFreeMap?.isActive())return;
  drag={x:e.clientX,y:e.clientY};mapSvg.setPointerCapture(e.pointerId)});
mapSvg.addEventListener('pointermove',e=>{if(!drag||window.FSCFreeMap?.isActive())return;
  const ratioX=900/Math.max(1,mapSvg.clientWidth),ratioY=340/Math.max(1,mapSvg.clientHeight);
  mapPanX+=(e.clientX-drag.x)*ratioX;mapPanY+=(e.clientY-drag.y)*ratioY;
  drag={x:e.clientX,y:e.clientY};renderMap(state)});
const endDrag=()=>{drag=null};
mapSvg.addEventListener('pointerup',endDrag);mapSvg.addEventListener('pointercancel',endDrag);
$('satellite-toggle').onclick=()=>{const on=window.FSCFreeMap?.toggleSatellite();$('satellite-toggle').setAttribute('aria-pressed',String(!!on));if(!window.FSCFreeMap?.isActive())toast('Mapa local disponível. Satélite requer conexão online.')};
async function poll(){try{const response=await fetch('/state',{headers:{'X-Flight-Token':token},cache:'no-store'});if(!response.ok)throw Error();render(await response.json());pollFailures=0}catch{pollFailures++;if(pollFailures===3){text('connection','App indisponível');$('led').style.background='#e06a75';text('telemetry-status','SEM ATUALIZAÇÃO');toast('Conexão com o aplicativo interrompida.')}}finally{setTimeout(poll,500)}}poll();

$('minimize').onclick=()=>{if(window.pywebview?.api)window.pywebview.api.minimize();else toast('Minimizar disponível na janela Windows.');};

$('photo-credit').onclick=()=>showDetails('Fotografia • Cessna 152','Md Shaifuzzaman Ayon — Cessna 152 Aircraft, Wikimedia Commons.\nCC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/\nFonte: https://commons.wikimedia.org/wiki/File:Cessna_152_Aircraft.jpg\nArquivo original preservado; exibição com recorte e tonalização CSS. A apresentação adaptada mantém CC BY-SA 4.0.\nFoto ilustrativa do modelo, não do exemplar virtual do piloto.');
