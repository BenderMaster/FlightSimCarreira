'use strict';
const token=location.hash.slice(1);history.replaceState(null,'',location.pathname);
const $=id=>document.getElementById(id),money=n=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL',maximumFractionDigits:0}).format(n),number=(n,d=0)=>Number(n).toLocaleString('pt-BR',{maximumFractionDigits:d}),text=(id,v)=>$(id).textContent=v;
const icon=n=>{const s=document.createElementNS('http://www.w3.org/2000/svg','svg'),u=document.createElementNS(s.namespaceURI,'use');u.setAttribute('href','#i-'+n);s.append(u);return s};
const node=(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=value;return e};
let selectedFleetRef=null,fleetViewKey='',fleetListKey='';
let state={},zoom=1,mapPanX=0,mapPanY=0,selectedOffer=null,lastOfferKey='',pollFailures=0,planeTrack=null,planeBearing=0,recenterPlane=false,marketLastKey='',view='dashboard',previousView='dashboard';
const nav=[['home','Dashboard','dashboard'],['globe','Mercado','regional'],['hangar','Frota / Hangar','fleet'],['store','Mercado de Aeronaves','aircraft_market'],['map','Planejamento de Voo','planning'],['pilot','Meu Piloto','pilot'],['coins','Finanças','finance'],['building','Companhias','employment'],['book','Logbook','history'],['chart','Análise e Relatórios','reports'],['gear','Configurações','settings']];
for(const [ic,label,action] of nav){const b=node('button','nav-item'+(action==='dashboard'?' active':''));b.append(icon(ic),node('span','',label));b.dataset.action=action;$('navigation').append(b)}
const metricNames=[['ias','gauge','Velocidade (IAS)','kt'],['gs','gauge','Velocidade (GS)','kt'],['alt','mountain','Altitude (MSL)','ft'],['agl','layers','Altura (AGL)','ft'],['vs','arrows','Razão Vertical','ft/min'],['phase','plane','Fase do Voo','']];
for(const [key,ic,label] of metricNames){const m=node('div','metric');m.append(icon(ic));const v=node('strong','','—');v.id='metric-'+key;m.append(v,node('small','',label));$('metrics').append(m)}
function toast(message){text('toast',message);$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),4000)}
async function command(action,id){try{const r=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json','X-Flight-Token':token},body:JSON.stringify(id!==undefined?{action,id}:{action})});if(!r.ok)throw Error();if(!['refresh','close'].includes(action))toast('Solicitação enviada ao aplicativo.');}catch{toast('Não foi possível enviar. Verifique se o aplicativo está aberto.')}}
const routeActions=new Set(nav.map(item=>item[2]));
// Um único MapLibre e uma única árvore de controles: o DOM muda de lugar
// sem recriar mapa/canvas/WebGL nem gerar segunda camada de créditos.
const dashboardMapHost=document.querySelector('.center-column .map-card');
const sharedMapArea=dashboardMapHost.querySelector('.map-area');
function routeMapState(s){return view==='details'&&selectedOffer?{...s,mission:selectedOffer}:s}
function mountSharedMap(onDetails){
 const parent=onDetails?$('detail-map-slot'):dashboardMapHost;
 if(onDetails){
  if(sharedMapArea.parentElement!==parent)parent.append(sharedMapArea);
 }else if(sharedMapArea.parentElement!==dashboardMapHost){
  dashboardMapHost.insertBefore(sharedMapArea,dashboardMapHost.querySelector('.map-tabs'));
 }
 if(view==='dashboard'||view==='details')requestAnimationFrame(()=>requestAnimationFrame(()=>{
  window.FSCFreeMap?.resizeToContainer?.();
  renderMap(state);
 }));
}
function navigate(destination){
 if(destination==='market')destination='regional';
 if(!routeActions.has(destination)&&destination!=='details'&&destination!=='freelance')return;
 view=destination;
 const market=view==='regional'||view==='freelance',
       fleet=view==='fleet',
       aircraftMarket=view==='aircraft_market',
       module=!market&&!fleet&&!aircraftMarket&&view!=='dashboard'&&view!=='details';
 document.querySelector('.workspace').dataset.view=view;
 $('market-page').hidden=!market;$('fleet-page').hidden=!fleet;
 $('aircraft-market-page').hidden=!aircraftMarket;
 $('module-page').hidden=!module;$('details').hidden=view!=='details';
 document.querySelectorAll('.nav-item').forEach(button=>{
  const current=view==='details'?previousView:view;
  const selected=button.dataset.action===(current==='freelance'?'regional':current);
  button.classList.toggle('active',selected);
  if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
 });
 mountSharedMap(view==='details'&&!!selectedOffer);
 if(market)renderMarketView(state,true);
 if(fleet)renderFleetView(state,true);
 if(aircraftMarket)window.FSCAircraftMarket?.render(state,true);
 if(module)renderModuleView(state);
}
document.querySelector('.workspace').dataset.view=view;
document.addEventListener('click',e=>{
 const operation=e.target.closest('[data-fleet-operation]');
 if(operation){
   if(operation.disabled)return;
   const plane=(state.fleet?.owned||[]).find(x=>x.ref===selectedFleetRef);
   if(!plane){toast('Selecione uma aeronave de sua propriedade.');return;}
   if(operation.dataset.fleetOperation==='fleet_refuel'){
     if(!plane.is_active){toast('Defina esta aeronave como ativa antes de abastecer.');return;}
     openRefuelDialog();return;
   }
   command(operation.dataset.fleetOperation,plane.ref);return;
 }
 const item=e.target.closest('[data-fleet-ref]');
 if(item){
   selectedFleetRef=item.dataset.fleetRef;
   fleetViewKey='';
   renderFleetView(state,true);
   return;
 }
 const b=e.target.closest('[data-action]');
 if(b){const action=b.dataset.action;
  if(action==='refuel'){openRefuelDialog();return;}
  if(routeActions.has(action)||action==='market'){navigate(action);return;}
  command(action);return;}
 const tab=e.target.closest('[data-tab]');
 if(tab&&tab.dataset.tab==='weather')showDetails('METEOROLOGIA • MSFS / NOAA',weatherDetails());
});
function showDetails(title,body,offer){
 previousView=view==='details'?previousView:view;
 text('dialog-title',title);
 selectedOffer=offer||null;
 $('details-content').hidden=!selectedOffer;
 $('dialog-text').hidden=!!selectedOffer;
 if(!selectedOffer)text('dialog-text',body);
 if(selectedOffer){
  text('detail-origin',offer.origin);
  text('detail-destination',offer.destination);
  text('detail-mission-title',offer.title||offer.category||title);
  text('detail-nav-source',offer.nav_source==='MSFS'?'Coordenadas verificadas na base do MSFS':
    offer.nav_source==='MISTO'?'Coordenadas mistas: apenas um aeroporto confirmado pelo MSFS':
    'Posições do catálogo externo • aguardando consulta ao MSFS');
  text('detail-manifest-name',offer.manifest_label||'Manifesto não cadastrado');
  text('detail-payload',(offer.passenger_count?offer.passenger_count+' passageiro(s) • ':'Carga • ')+number(offer.payload_kg||0,1)+' kg');
  text('detail-distance',offer.distance==null?'—':number(offer.distance,1)+' NM');
  text('detail-duration',offer.minutes==null?'—':'~ '+Math.floor(offer.minutes/60)+'h'+String(offer.minutes%60).padStart(2,'0'));
  text('detail-cruise',offer.cruise_kts!=null?number(offer.cruise_kts)+' kt':'—');
  text('detail-reward',money(offer.reward));
  text('detail-aircraft',offer.aircraft_label||'Aeronave a definir');
  text('detail-requirements',(offer.allowed?'Disponível • ':'Bloqueado • ')+(offer.reason||'Verificação na contratação'));
  $('detail-requirements').className=offer.allowed?'eligible':'blocked';
 }
 $('dialog-accept').hidden=!offer;$('dialog-accept').disabled=!!offer&&!offer.allowed;
 navigate('details');
}
$('dialog-close').onclick=()=>navigate(previousView);
$('dialog-accept').onclick=()=>{
 if(selectedOffer?.allowed){command('offer',selectedOffer.id);navigate('dashboard')}
};
function bar(id,ratio){$(id).style.width=(Math.min(1,Math.max(0,ratio||0))*100)+'%'}
function renderOffers(s){const key=JSON.stringify([s.offers,s.mission?.id]);if(key===lastOfferKey)return;lastOfferKey=key;$('offers').replaceChildren();const offers=s.offers.slice(0,5);if(!offers.length){const empty=node('div','empty');empty.append(icon('globe'),node('span','',(s.mode!=='Demo'&&!s.airports?.ready)?'Aguardando inventário de aeroportos do MSFS; nenhuma oferta externa será mostrada.':
 s.pilot?'Sem propostas disponíveis. Atualize o mercado ou confira sua base e habilitações.':'Cadastre seu piloto para descobrir os contratos da região.'));$('offers').append(empty);return}
for(const o of offers){const b=node('button','offer'+(s.mission?.id===o.id?' active':'')+(!o.allowed?' locked':''));b.append(icon(o.category.toLowerCase().includes('carga')?'box':'plane'));const d=node('div');d.append(node('strong','',o.category));const meta=node('div','offer-meta');meta.append(node('span','',o.origin+' → '+o.destination),node('span','price',money(o.reward)));d.append(meta,node('small','duration',(o.minutes===null?'—':'~ '+Math.floor(o.minutes/60)+'h'+String(o.minutes%60).padStart(2,'0'))+(!o.allowed?' • Bloqueado':'')));b.append(d);b.onclick=()=>showDetails(o.category,o.origin+' → '+o.destination+'\nPagamento bruto: '+money(o.reward)+'\n'+(o.distance===null?'Distância indisponível':number(o.distance)+' NM • '+o.minutes+' min')+'\n\n'+o.reason,o);$('offers').append(b)}}


function openMarket(filter='regional'){navigate(filter==='freelance'?'freelance':'regional')}
function renderMarketView(s,force=false){
 if(!s?.offers||(view!=='regional'&&view!=='freelance'))return;
 const key=JSON.stringify([s.offers,s.mission?.id,view,$('market-search').value.trim()]);
 if(!force&&key===marketLastKey)return;
 marketLastKey=key;
 const freelance=view==='freelance',search=$('market-search').value.trim().toLocaleLowerCase('pt-BR');
 text('market-view-title',freelance?'MERCADO FREELANCER':'MERCADO REGIONAL');
 document.querySelectorAll('[data-market-view]').forEach(button=>{
  const selected=button.dataset.marketView===view;
  button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));
 });
 const base=s.market?s.market.icao+' • '+s.market.name:'Aguardando confirmação pelo MSFS';
 const inventory=s.mode==='Demo'?'DEMONSTRAÇÃO':s.airports?.ready?'MSFS • '+s.airports.count+' aeródromos verificados':'CONSULTANDO AEROPORTOS MSFS';
 text('market-dialog-base',base+'  |  '+inventory+' | Piloto '+(s.pilot?.callsign||'não cadastrado'));
 text('market-view-hint',freelance?'Aeronave fornecida pelo contratante. Sem custos de compra ou aluguel para este serviço.':'Serviços para o piloto autônomo com aeronave própria. Regras de nível, habilitação e local são verificadas no aceite.');
 const items=s.offers.filter(o=>Boolean(o.freelance)===freelance&&
  (!search||[o.title,o.category,o.origin,o.destination].join(' ').toLocaleLowerCase('pt-BR').includes(search)));
 text('market-count',items.length+' oferta'+(items.length===1?'':'s'));
 $('market-list').replaceChildren();
 if(!items.length){
  $('market-list').append(node('p','market-empty',
   (s.mode!=='Demo'&&!s.airports?.ready)?'Aguardando lista oficial do MSFS 2020. Nenhum aeroporto externo será usado.':
   search?'Nenhum contrato corresponde à busca.':
   freelance?'Nenhuma oferta freelancer nesta região e nível.':
   'Nenhuma missão disponível nos aeroportos confirmados pelo MSFS.'));
  return;
 }
 for(const o of items){
  const item=node('button','market-option'+(!o.allowed?' locked':''));
  item.type='button';item.dataset.offerId=o.id;
  const title=node('div','offer-line');
  title.append(node('strong','',o.origin+' → '+o.destination),node('span','market-pay',money(o.reward)));
  const chip=node('div','type-chip'+(freelance?' freelance':''),o.category+(freelance?' • FREELANCER':' • AERONAVE PARTICULAR'));
  item.append(title,chip,node('small','',o.title||'Missão regional'),
    node('small','manifest-preview',(o.manifest_label||'Manifesto pendente')+' • '+number(o.payload_kg||0,1)+' kg'));
  const plane=freelance?(' • Aeronave do contratante: '+(o.employer_plane||'conforme contrato')):'';
  const duration=o.minutes!=null?' • ~'+Math.floor(o.minutes/60)+'h'+String(o.minutes%60).padStart(2,'0'):'';
  item.append(node('small','',duration+plane));
  if(!o.allowed)item.append(node('small','',o.reason||'Requisitos do piloto insuficientes'));
  if(s.mission&&s.mission.id!==o.id)item.append(node('small','','Conclua ou cancele o contrato atual antes de aceitar outro.'));
  item.onclick=()=>showDetails(o.category+(freelance?' • Freelancer':''),
   o.origin+' → '+o.destination+'\nPagamento bruto: '+money(o.reward)+
   '\n'+(o.distance==null?'Distância indisponível':number(o.distance)+' NM')+
   plane+'\n\n'+(o.reason||'O aceite será validado pelo motor da carreira.'),
   Object.assign({},o,{allowed:o.allowed&&(!s.mission||s.mission.id===o.id)}));
  $('market-list').append(item);
 }
}
$('market-refresh').onclick=()=>command('refresh');
$('market-search').addEventListener('input',()=>renderMarketView(state,true));
document.querySelectorAll('[data-market-view]').forEach(button=>button.onclick=()=>navigate(button.dataset.marketView));

const moduleTitles={
 fleet:['FROTA / HANGAR','Situação da aeronave selecionada e operações de frota.'],
 planning:['PLANEJAMENTO DE VOO','Resumo operacional da missão e das condições antes do despacho.'],
 pilot:['MEU PILOTO','Identidade, experiência e habilitações registradas na carreira.'],
 finance:['FINANÇAS','Saldo e resultado financeiro da carreira.'],
 employment:['COMPANHIAS','Seu vínculo de trabalho e evolução profissional.'],
 history:['LOGBOOK','Últimos eventos e registros da sessão.'],
 reports:['ANÁLISE E RELATÓRIOS','Indicadores da carreira e histórico operacional.'],
 settings:['CONFIGURAÇÕES','Estado da integração com o MSFS e preferências.']
};
function fleetImage(plane){
 // Foto escolhida pelo piloto sempre prevalece sobre o showcase do catálogo.
 if(plane?.photo_url)return {src:plane.photo_url,kind:'custom'};
 if(plane?.code==='c152')return {src:'/c152.jpg',kind:'stock'};
 const showcase={
   c172:'/market-c172.jpg',g58:'/market-g58.jpg',
   kingair:'/market-kingair.jpg',cj4:'/market-cj4.jpg'
 };
 if(plane?.code&&showcase[plane.code])
   return {src:showcase[plane.code],kind:'showcase'};
 return {src:null,kind:'none'};
}
function setFleetImage(img,placeholder,plane){
 const image=fleetImage(plane);
 if(image.src){
   if(img.getAttribute('src')!==image.src)img.setAttribute('src',image.src);
   img.hidden=false;
   if(placeholder)placeholder.hidden=true;
   img.alt=image.kind==='custom'?'Fotografia cadastrada da aeronave '+plane.title:
      'Imagem ilustrativa de '+plane.title;
 }else{
   img.hidden=true;
   if(placeholder)placeholder.hidden=false;
   img.removeAttribute('src');
 }
 return image.kind;
}
function renderFleetView(s,force=false){
 if(view!=='fleet'||!s?.progress)return;
 const owned=s.fleet?.owned||[];
 if(!owned.some(x=>x.ref===selectedFleetRef)){
   selectedFleetRef=owned.find(x=>x.is_active)?.ref||owned[0]?.ref||null;
   force=true;
 }
 const selected=owned.find(x=>x.ref===selectedFleetRef);
 const listKey=JSON.stringify([selectedFleetRef,owned.map(x=>[x.ref,x.title,x.kind,x.photo_url,x.condition,x.airport,x.is_active])]);
 const key=JSON.stringify([selected,s.phase,s.connection]);
 if(!force&&key===fleetViewKey&&listKey===fleetListKey)return;
 const redrawList=force||listKey!==fleetListKey;
 fleetViewKey=key;
 if(redrawList){
 fleetListKey=listKey;
 text('fleet-count',owned.length+' '+(owned.length===1?'aeronave':'aeronaves'));
 text('fleet-list-count',owned.length+' adquiridas');
 const list=$('fleet-list');list.replaceChildren();
 if(!owned.length)list.append(node('p','fleet-empty','Nenhuma aeronave adquirida. O resgate do Cessna inicial e a compra de novos modelos ficam na futura área de aquisição, separada do Hangar.'));
 for(const plane of owned){
   const card=node('button','fleet-item'+(plane.ref===selectedFleetRef?' selected':''));
   card.type='button';card.dataset.fleetRef=plane.ref;
   card.setAttribute('aria-pressed',String(plane.ref===selectedFleetRef));
   const image=fleetImage(plane);
   if(image.src){
     const thumb=node('img','fleet-thumb');
     thumb.src=image.src;thumb.alt='';thumb.loading='lazy';card.append(thumb);
   }else{
     const placeholder=node('span','fleet-item-placeholder');
     placeholder.append(icon('plane'));card.append(placeholder);
   }
   const detail=node('span','fleet-item-copy');
   detail.append(node('strong','',plane.title||plane.code),
     node('small','',(plane.airport||'Sem localização')+' • '+number(plane.condition,1)+'%'));
   if(plane.is_active)detail.append(node('em','','EM USO'));
   card.append(detail);list.append(card);
 }
 }
 const has=!!selected;
 text('fleet-name',selected?.title||'Nenhuma aeronave');
 text('fleet-model',has?selected.ref+' • '+({starter:'Inicial',legacy:'Adquirida (legado)',new:'Comprada nova',used:'Comprada usada'}[selected.kind]||'Própria'):'Selecione sua aeronave da lista');
 $('fleet-active').hidden=!selected?.is_active;
 const imageKind=setFleetImage($('fleet-photo'),$('fleet-photo-placeholder'),selected);
 $('fleet-photo-credit').hidden=imageKind!=='stock';
 text('fleet-airport',selected?.airport||'—');
 text('fleet-hours',has?number(selected.hours,1)+' h':'—');
 text('fleet-condition',has?number(selected.condition,1)+'%':'—');
 const ratio=has&&selected.fuel_capacity?selected.fuel_gallons/selected.fuel_capacity:null;
 text('fleet-fuel',ratio!==null?number(selected.fuel_gallons,1)+' gal ('+number(ratio*100)+'%)':'Sem leitura');
 for(const [id,value]of [['fleet-conditionbar',has?selected.condition/100:0],['fleet-fuelbar',ratio]]){
   const el=$(id);el.style.width=Math.max(0,Math.min(100,(value||0)*100))+'%';
   el.style.background=value!==null&&value<=.2?'#f5836e':value!==null&&value<=.4?'#ffc400':'#26dce8';
 }
 text('fleet-photo-caption',imageKind==='custom'?'Fotografia personalizada salva no banco da carreira e exibida também na Dashboard.':
   imageKind==='stock'?'Foto ilustrativa padrão do Cessna 152. Use Adicionar / trocar foto para cadastrar seu próprio avião.':
   imageKind==='showcase'?'Imagem demonstrativa do modelo. Você pode substituí-la por uma foto do seu próprio avião no MSFS.':
   'Ainda sem imagem padrão deste modelo. Adicione uma foto do seu avião no MSFS.');
 text('fleet-operation-kind',selected?.code?.toUpperCase()||'Sem aeronave');
 text('fleet-insurance',has?(selected.insured?'Segurada':'Sem seguro'):'—');
 text('fleet-acquisition',has?({starter:'Aeronave inicial',legacy:'Frota legada',new:'Compra nova',used:'Compra usada'}[selected.kind]||selected.kind):'—');
 const airborne=s.phase==='EM VOO'||s.phase==='AIRBORNE';
 const active=!!selected?.is_active;
 const buttons={'fleet-use':!has||active||airborne,
  'fleet-refuel':!has||!active||airborne||s.connection!=='connected',
  'fleet-revise':!has||airborne||selected.condition>=99.9,
  'fleet-upload':!has,'fleet-remove-photo':!selected?.photo_url};
 for(const [id,disabled]of Object.entries(buttons))$(id).disabled=!!disabled;
 $('fleet-use').title=active?'Já é a aeronave ativa':airborne?'Não altere a aeronave em voo':'Definir esta aeronave como ativa';
 $('fleet-refuel').title=!active?'Ative esta aeronave antes do abastecimento':'Ajustar combustível em solo';
}
function renderModuleView(s){
 if(!moduleTitles[view]||!s?.progress)return;
 const [title,description]=moduleTitles[view];text('module-title',title);text('module-description',description);
 const rows={
 fleet:[['Aeronave',s.plane?.title||'Não selecionada'],['Localização',s.plane?.airport||'—'],['Estado',s.plane?.condition!=null?number(s.plane.condition,1)+'%':'Sem avaliação'],['Combustível',s.fuel?.quantity!=null?number(s.fuel.quantity,1)+' gal':'Sem leitura']],
 planning:[['Rota ativa',s.mission?s.mission.origin+' → '+s.mission.destination:'Nenhum contrato ativo'],['Distância',s.mission?.distance!=null?number(s.mission.distance,1)+' NM':'—'],['Aeronave',s.plane?.title||'—'],['Clima de origem',weatherSummary(s.weather?.origin)],['METAR destino',s.weather?.destination_metar?.raw||'Indisponível'],['Relógio UTC',s.audit?.clock==null?'Não verificável':s.audit.clock?'Sincronizado':'Não sincronizado'],['Assistências',s.audit?.assists==null?'Leitura indisponível':s.audit.assists?'Desativadas (itens monitorados)':'Ativas'],['Arremetidas',String(s.audit?.go_arounds??0)],['Toque e arremetida',String(s.audit?.touch_and_go??0)],['Excesso de velocidade no táxi',String(s.audit?.taxi_violations??0)],['Manobras extremas (G)',String(s.audit?.hard_g_events??0)],['Fase',s.phase||'—']],
 pilot:[['Indicativo',s.pilot?.callsign||'Não cadastrado'],['Nível',String(s.progress.level)],['Habilitações',s.summary?.qualifications?.join(', ')||'—'],['Reputação',s.summary?.reputation?.score!=null?s.summary.reputation.score+'%':'—']],
 finance:[['Caixa',money(s.balance)],['Resultado operacional',money(s.summary?.net||0)],['Bônus recebidos',money(s.summary?.bonus||0)]],
 employment:[['Modalidade',s.employment||'—'],['Piloto',s.pilot?.callsign||'—'],['Base',s.market?.icao||'—']],
 history:[['Voos realizados',String(s.summary?.flights??0)],['Horas registradas',number(s.summary?.hours||0,1)+' h'],['Eventos recentes',s.log?.slice(-12).join('\n')||'Sem eventos']],
 reports:[['Voos',String(s.summary?.flights??0)],['Horas',number(s.summary?.hours||0,1)+' h'],['Resultado',money(s.summary?.net||0)],['Reputação',s.summary?.reputation?.score!=null?s.summary.reputation.score+'%':'—']],
 settings:[['SimConnect',s.connection||'desconectado'],['Estado',s.status||'—'],['Modo',s.mode||'—']]
 }[view]||[];
 $('module-context').replaceChildren();
 for(const [label,value] of rows){const card=node('div','module-stat');card.append(node('small','',label),node('strong','',String(value)));$('module-context').append(card)}
 $('module-legacy').textContent='Abrir ferramentas clássicas de '+title.toLocaleLowerCase('pt-BR');
 $('module-legacy').onclick=()=>command(view);
}
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
 const w=state.weather||{},o=w.origin,n=w.destination_metar,d=w.destination_sim;
 const origin=state.mission?.origin||'—',dest=state.mission?.destination||'—';
 const useSim=!n||w.show_sim_with_noaa;
 return 'ORIGEM '+origin+' — MSFS (condições na aeronave)\n'+(o?weatherSummary(o):'Sem leitura na origem')+
  '\n\nDESTINO '+dest+' — NOAA METAR\n'+(n?(n.raw||weatherSummary(n)):'NOAA indisponível')+
  (n?.stale?'\nBoletim em cache; pode estar desatualizado.':'')+
  (useSim?'\n\nDESTINO — MSFS (fallback ou preferência)\n'+(d?weatherSummary(d):'Aguardando aproximação'):'')+
  '\n\nO MSFS não informa o METAR integral via SimVars.';
}
function renderWeather(s){
 const w=s.weather||{},o=w.origin,n=w.destination_metar,d=w.destination_sim;
 text('weather-origin','ORIGEM • MSFS '+(s.mission?.origin||'—'));
 text('weather-origin-values',o?weatherSummary(o):'Aguardando condições do MSFS na origem');
 if(n){
  text('weather-destination','DESTINO • NOAA '+(s.mission?.destination||'—'));
  text('weather-destination-values',(n.raw||weatherSummary(n)).slice(0,105)+
    (w.show_sim_with_noaa&&d?' • MSFS: '+weatherSummary(d):''));
 }else{
  text('weather-destination','DESTINO • '+(d?'MSFS':'NOAA')+' '+(s.mission?.destination||'—'));
  text('weather-destination-values',d?weatherSummary(d):'Aguardando METAR NOAA • MSFS ainda indisponível');
 }
}
function render(s){state=s;if(!s.progress)return;const p=s.pilot;const country=s.country==='BR'?'':s.country?' · '+s.country:'';text('callsign',(p?.callsign||'CADASTRAR PILOTO')+country);if(s.country==='BR'){const flag=node('span','flag-br');flag.title='Brasil • país da base';$('callsign').append(flag)}text('qualification',p?({autonomo:'Piloto autônomo',empregado:'Piloto empregado',proprietario:'Companhia própria'}[s.employment]||s.employment)+' • '+s.summary.qualifications.join(' / '):'Crie sua carreira');text('level',p?'NÍVEL '+s.progress.level:'NÍVEL —');text('xp',p?'XP '+s.progress.xp+' / '+s.progress.target+' ('+Math.round(s.progress.fraction*100)+'%)':'XP —');bar('xpbar',s.progress.fraction);text('balance',money(s.balance));text('connection',{connected:'Conectado',reconnecting:'Reconectando',disconnected:'Desconectado'}[s.connection]);$('led').style.background={connected:'#86fc24',reconnecting:'#ffc400',disconnected:'#e06a75'}[s.connection];$('avatar').hidden=!s.avatar;if(s.avatar&&$('avatar').src!==s.avatar)$('avatar').src=s.avatar;
text('market-base',s.market?s.market.icao+' — '+s.market.name:'Cadastre sua base');renderOffers(s);renderMarketView(s);renderModuleView(s);renderFleetView(s);window.FSCAircraftMarket?.render(s);renderSummary(s);
const m=s.mission;const bonus=s.bonus?.bonus_fraction||0;text('route',m?m.origin+' → '+m.destination:'Selecione uma missão');text('distance',m?'Distância: '+(m.distance===null?'—':number(m.distance)+' NM')+'  |  Prev. voo: '+(m.minutes===null?'—':m.minutes+' min'):'Explore o mercado regional para começar');text('category',m?.category||'');text('reward',m?money(m.reward):'—');text('bonus-value',m?'+'+number(bonus*100,1)+'%':'—');text('mission-status',m?(s.bonus?.frozen?'EM VOO • CONGELADO':'RESERVADO'):'');
for(const [key,, ,unit] of metricNames){const e=$('metric-'+key);if(key==='phase'){e.textContent=s.phase;e.style.color='#8df63e';continue}e.replaceChildren(document.createTextNode(s.telemetry?number(s.telemetry[key]):'—'),node('small','',' '+unit))}text('telemetry-status',s.mode==='Demo'?'DEMONSTRAÇÃO':s.telemetry?.stale?'ÚLTIMA LEITURA • SEM ATUALIZAÇÃO':s.connection==='connected'?'':'AGUARDANDO MSFS');renderWeather(s);text('log',s.log.slice(-8).join('\n'));$('log').scrollTop=$('log').scrollHeight;text('realism-total',m?'+'+number(bonus*100,1)+'%':'—');
const labels=['Relógio UTC verificado','Assistência de voo verificada','Pista / iluminação revisada','Rota revisada','Combustível adequado','Peso dentro do limite'];const components=Object.values(s.bonus?.components||{});$('checklist').replaceChildren();labels.forEach((label,i)=>{const sensor=i===0?s.audit?.clock:i===1?s.audit?.assists:undefined;
const ok=i<2?sensor===true:components[i]?.ok;
const e=node('div',ok?'ok':'');e.append(icon('check'),node('span','',label));
e.title=i<2?(sensor==null?'Sensor indisponível • sem bônus':sensor?'Verificado pelo MSFS':'Condição não atendida'):
 (components[i]?'+'+number(components[i].rate*100,1)+'% • ':'')+(i<4?'Conferência manual':'Telemetria/estimativa');$('checklist').append(e)});text('edit-plan',s.bonus?.frozen?'Congelado na decolagem • Ver despacho':'Revisar no despacho →');
const a=s.plane;const photoKind=setFleetImage($('aircraft-photo'),null,a);
 const photo=photoKind!=='none';
 $('photo-credit').hidden=photoKind!=='stock';
 document.querySelector('.aircraft-art').classList.toggle('has-photo',photo);
 document.querySelector('.aircraft-art>svg').style.display=photo?'none':'';
 document.querySelector('.aircraft-art>span').hidden=photo;text('aircraft-name',a?.title||'Nenhuma aeronave');text('aircraft-ref',a?a.ref+' • '+a.kind:'Selecione no Hangar');document.querySelectorAll('[data-action=refuel],[data-action=service]').forEach(b=>{b.disabled=!!a?.ref.startsWith('contract:');b.title=b.disabled?'Aeronave fornecida pelo contratante':''});text('location',a?.airport||'—');text('condition',a?.condition!==null&&a?number(a.condition,1)+'%':'Indisponível');bar('conditionbar',a?a.condition/100:0);$('conditionbar').style.background=a?.condition<40?'#ef6464':a?.condition<75?'#ffc400':'';const f=s.fuel;const q=f.quantity;const ratio=q!==null&&f.capacity?q/f.capacity:null;text('fuel-value',q!==null?number(q,1)+' gal'+(ratio!==null?' ('+number(ratio*100)+'%)':''):'Sem leitura validada');bar('fuelbar',ratio);text('fuel-title','Controle: '+(f.enabled?'ATIVO':'DESLIGADO'));text('fuel-status',f.enabled?(s.connection==='connected'?'Confira a confirmação no registro':'Aguardando MSFS • sem confirmação'):'Penalidade de 30% em R$ e XP');$('fuel-toggle').classList.toggle('on',f.enabled);const alerts=$('resource-alerts');alerts.replaceChildren();
if(s.maintenance_alerts?.fuel_low)alerts.append(node('div','alert-fuel','⚠ Combustível ≤20% • Abasteça antes de decolar'));
if(s.maintenance_alerts?.condition_low)alerts.append(node('div','alert-wear','⚠ Aeronave ≤20% de condição • Revisão recomendada'));
alerts.hidden=!alerts.childElementCount;
const ds=s.dispatch_state||{};
const routeNames={atc_sent:'Enviado ao ATC • GPS/VFR NÃO confirmado',
 waiting_navdata:'Aguardando aeroportos MSFS',invalid_airport:'Aeroporto ausente do MSFS',
 loading:'Solicitando plano ao MSFS',error:'Falha de importação'};
text('dispatch-progress',m?('Plano: '+(routeNames[ds.route]||ds.route||'não preparado')+
 ' • Carga: '+(ds.payload||'não preparada')+
 (ds.message?' • '+ds.message:'')):'Aceite uma missão para preparar plano e carga automaticamente.');
text('connection-hint',s.mode==='Demo'?'DEMONSTRAÇÃO • Telemetria simulada':s.connection==='connected'?s.status:'Conecte ao MSFS em Configurações.');if(view==='dashboard'||view==='details')renderMap(s)}
function svgNode(tag,attrs,textValue){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs||{}))e.setAttribute(k,v);if(textValue!==undefined)e.textContent=textValue;return e}
function headingDisplay(t){
 if(t?.stale)return 'POSIÇÃO DESATUALIZADA';
 if(Number.isFinite(t?.heading_magnetic_deg)){
  const mag=String(Math.round(t.heading_magnetic_deg)%360).padStart(3,'0');
  const tru=Number.isFinite(t.heading_deg)?' • '+String(Math.round(t.heading_deg)%360).padStart(3,'0')+'° TRUE':'';
  return 'PROA '+mag+'° MAG'+tru;
 }
 if(Number.isFinite(t?.heading_deg))return 'PROA '+String(Math.round(t.heading_deg)%360).padStart(3,'0')+'° TRUE';
 return t?'POSIÇÃO MSFS':'MAPA E ROTA';
}
function renderMap(s){
  s=routeMapState(s);
  window.FSCFreeMap?.render(s);
  if(window.FSCFreeMap?.isActive()){
    text('map-mode',headingDisplay(s.telemetry));
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
const nm=60*90/scale;svg.append(svgNode('path',{d:'M760 294v6h90v-6',stroke:'#b9dce8','stroke-width':2}));svg.append(svgNode('text',{x:805,y:288,'text-anchor':'middle',fill:'#c9e3ed',stroke:'none','font-size':12},number(nm,1)+' NM'));text('map-mode',s.mode==='Demo'?'DEMONSTRAÇÃO':headingDisplay(s.telemetry))}
$('zoom-in').onclick=()=>{if(window.FSCFreeMap?.zoomBy(1))return;zoom=Math.min(16,zoom*1.3);renderMap(state)};
$('zoom-out').onclick=()=>{if(window.FSCFreeMap?.zoomBy(-1))return;zoom=Math.max(.2,zoom/1.3);renderMap(state)};
$('recenter').onclick=()=>{if(window.FSCFreeMap?.recenter(routeMapState(state)))return;if(state.telemetry){recenterPlane=true}else{zoom=1;mapPanX=mapPanY=0;}renderMap(state)};
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

/* Abastecimento: popup intencional, separado da navegação por páginas. */
let refuelSnapshot=null;
const refuelDialog=$('refuel-dialog');
function openRefuelDialog(){
 const f=state.fuel||{},p=state.plane||{};
 if(!Number.isFinite(f.quantity)||!Number.isFinite(f.capacity)||f.capacity<=0){
  toast('Tanques não calibrados; conecte MSFS com o avião no solo.');return;
 }
 if(state.mission?.freelance){toast('Avião do contratante não pode ser abastecido com o caixa pessoal.');return}
 if(state.phase==='EM VOO'||state.connection!=='connected'){
  toast('Abastecimento exige MSFS conectado e aeronave no solo.');return}
 refuelSnapshot={current:f.quantity*3.785411784,capacity:f.capacity*3.785411784,
                 credit:f.refundable_liters||0,plane:p.title||'Aeronave'};
 text('refuel-aircraft',refuelSnapshot.plane+' • capacidade '+number(refuelSnapshot.capacity,1)+' L');
 text('refuel-current',number(refuelSnapshot.current,1)+' L');
 text('refuel-capacity',number(refuelSnapshot.capacity,1)+' L');
 $('refuel-target').max=String(refuelSnapshot.capacity);
 $('refuel-range').max=String(refuelSnapshot.capacity);
 $('refuel-target').value=refuelSnapshot.current.toFixed(1);
 $('refuel-range').value=refuelSnapshot.current.toFixed(1);
 updateRefuelEstimate();
 refuelDialog.showModal();
}
function updateRefuelEstimate(){
 if(!refuelSnapshot)return;
 const target=Math.max(0,Math.min(refuelSnapshot.capacity,Number($('refuel-target').value)||0));
 $('refuel-range').value=String(target);
 const delta=target-refuelSnapshot.current;
 text('refuel-delta',(delta>=0?'+':'')+number(delta,1)+' L');
 const refundable=Math.min(Math.max(0,-delta),refuelSnapshot.credit);
 const charge=delta>0?-Math.max(1,Math.round(delta*7)):Math.round(refundable*7);
 text('refuel-price',(charge<0?'Custo: ':'Crédito: ')+money(Math.abs(charge)));
 $('refuel-confirm').disabled=Math.abs(delta)<.2;
}
$('refuel-target').addEventListener('input',updateRefuelEstimate);
$('refuel-range').addEventListener('input',()=>{$('refuel-target').value=$('refuel-range').value;updateRefuelEstimate()});
$('refuel-max').onclick=()=>{$('refuel-target').value=refuelSnapshot.capacity.toFixed(1);updateRefuelEstimate()};
$('refuel-half').onclick=()=>{$('refuel-target').value=(refuelSnapshot.capacity/2).toFixed(1);updateRefuelEstimate()};
for(const id of ['refuel-cancel','refuel-cancel-top'])$(id).onclick=()=>refuelDialog.close();
$('refuel-confirm').onclick=()=>{
 if(!refuelSnapshot)return;
 const target=Number($('refuel-target').value);
 if(!Number.isFinite(target)||target<0||target>refuelSnapshot.capacity+.05){
  toast('Informe uma quantidade válida em litros.');return;
 }
 refuelDialog.close();
 command('refuel',target);
};
