/* FlightSim Flight Operations v0.8.2 — UI sem estado financeiro. */
(()=>{
'use strict';
const el=id=>document.getElementById(id);
let mode='free',fixes=[],draftKey='',dirty=false,noticeSeq=null,currentState=null,projection=null;
let previewSerial=0,previewRequest='',previewTimer=null,lastPreviewRoute=null;
const radians=Math.PI/180;
function distanceNm(a,b){
 const x=a[0]*radians,y=b[0]*radians,d=(b[0]-a[0])*radians,l=(b[1]-a[1])*radians;
 const z=Math.sin(d/2)**2+Math.cos(x)*Math.cos(y)*Math.sin(l/2)**2;
 return 3440.065*2*Math.asin(Math.min(1,Math.sqrt(Math.max(0,z))));
}
function bearing(a,b){
 const x=a[0]*radians,y=b[0]*radians,d=(b[1]-a[1])*radians;
 return (Math.atan2(Math.sin(d)*Math.cos(y),Math.cos(x)*Math.sin(y)-Math.sin(x)*Math.cos(y)*Math.cos(d))/radians+360)%360;
}
function localRoute(base){
 // Visualização imediata; ICAOs e coordenadas das extremidades são validados pelo motor.
 if(!base||base.origin!==el('fo-origin').value.trim().toUpperCase()||
    base.destination!==el('fo-destination').value.trim().toUpperCase()||
    !Array.isArray(base.route)||base.route.length<2)return null;
 const coords=[base.route[0],...fixes.map(w=>[w.lat,w.lon]),base.route[base.route.length-1]];
 if(!coords.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))return null;
 const names=[base.origin,...fixes.map(w=>w.label),base.destination],cruise=Number(base.cruise_kts)||90;
 let total=0;
 const legs=coords.slice(0,-1).map((p,i)=>{
  const nm=distanceNm(p,coords[i+1]);total+=nm;
  return {from:names[i],to:names[i+1],nm:Math.round(nm*10)/10,
    bearing_deg:Math.round(bearing(p,coords[i+1]))%360,minutes:Math.round(60*nm/cruise*10)/10};
 });
 return {...base,route:coords,waypoints:fixes.map(w=>({...w})),legs,
  distance_nm:Math.round(total*10)/10,minutes:Math.max(8,Math.round(60*total/cruise+5)),
  route_key:JSON.stringify([base.origin,base.destination,fixes])};
}
function visibleRoute(data){
 if(!dirty)return data?.route||null;
 const preview=data?.preview;
 if(preview?.id===previewRequest){
  if(preview.error)return null;
  if(preview.route){lastPreviewRoute=preview.route;return preview.route;}
 }
 return localRoute(lastPreviewRoute)||localRoute(data?.route);
}
function refreshMap(){
 if(currentState)render(currentState);
 window.dispatchEvent(new Event('flightops-preview-changed'));
}
function schedulePreview(delay=120){
 previewRequest=String(++previewSerial);
 if(previewTimer)clearTimeout(previewTimer);
 previewTimer=setTimeout(()=>{
  previewTimer=null;
  if(!currentState?.flight_operations?.ready)return;
  const p=collect();
  if(!/^[A-Z0-9]{4}$/.test(p.origin)||!/^[A-Z0-9]{4}$/.test(p.destination)||
     !Number.isInteger(p.altitude_ft)||p.altitude_ft<500||p.altitude_ft>45000)return;
  send('flightops_preview',p,previewRequest);
 },delay);
}

const ids=['origin','destination','altitude'];
const checkKeys={runway_checked:'fo-check-runway',route_checked:'fo-check-route',
                 fuel_checked:'fo-check-fuel',payload_checked:'fo-check-payload'};
const text=(id,value)=>{el(id).textContent=value==null?'—':String(value)};
const number=(n,d=0)=>n==null?'—':Number(n).toLocaleString('pt-BR',{maximumFractionDigits:d});
function markDirty(){
 dirty=true;text('fo-status','PRÉVIA • NÃO SALVA');
 text('fo-message','Rota em prévia; salve somente quando estiver pronta.');
 schedulePreview();refreshMap();
}
function showMode(){
 el('fo-free').classList.toggle('primary',mode==='free');
 el('fo-contract').classList.toggle('primary',mode==='contract');
 el('fo-origin').disabled=mode==='contract';
 el('fo-destination').disabled=mode==='contract';
}
function useDraft(p){
 mode=p.mode||'free';
 el('fo-origin').value=p.origin||'';
 el('fo-destination').value=p.destination||'';
 el('fo-altitude').value=p.altitude_ft??2500;
 fixes=(p.waypoints||[]).map(w=>({...w}));
 for(const [key,id] of Object.entries(checkKeys))el(id).checked=!!p.checks?.[key];
 showMode();renderFixes();dirty=false;
 if(previewTimer)clearTimeout(previewTimer);
 previewTimer=null;previewRequest='';lastPreviewRoute=null;
}
function renderFixes(){
 const box=el('fo-waypoints');box.replaceChildren();
 if(!fixes.length){const e=document.createElement('small');e.textContent='Rota direta • sem waypoints';box.append(e);return;}
 fixes.forEach((w,i)=>{
  const row=document.createElement('div'),name=document.createElement('span'),remove=document.createElement('button');
  row.className='fo-waypoint-row';row.dataset.index=String(i);
  name.textContent=(i+1)+'. '+w.label+' • '+number(w.lat,4)+'°, '+number(w.lon,4)+'°';
  remove.type='button';remove.className='fo-waypoint-remove';remove.textContent='×';
  remove.title='Excluir waypoint '+w.label;remove.setAttribute('aria-label','Excluir waypoint '+w.label);
  remove.onclick=()=>{fixes.splice(i,1);renderFixes();markDirty();};
  row.append(name,remove);box.append(row);
 });
}
function collect(){
 const altitude=Number(el('fo-altitude').value);
 return {mode,origin:el('fo-origin').value.trim().toUpperCase(),
  destination:el('fo-destination').value.trim().toUpperCase(),
  altitude_ft:altitude,waypoints:fixes.map(w=>({...w})),
  checks:Object.fromEntries(Object.entries(checkKeys).map(([key,id])=>[key,el(id).checked]))};
}
async function send(action,payload,id=null){
 const body=payload?{action,payload}:{action};
 if(id!==null)body.id=id;
 try{
  const r=await fetch('/command',{method:'POST',headers:{
    'X-Flight-Token':token,'Content-Type':'application/json'
   },body:JSON.stringify(body)});
  if(!r.ok)throw Error('HTTP '+r.status);
  if(action!=='flightops_preview')text('fo-message','Solicitação recebida pelo motor. Aguardando confirmação.');
 }catch(err){
  text('fo-message',(action==='flightops_preview'?'Falha ao calcular prévia: ':'Falha ao comunicar com o motor: ')+err.message);
 }
}
function renderLegs(r){
 const parent=el('fo-legs');parent.replaceChildren();
 if(!r){parent.textContent='Informe os aeroportos e clique em Planejar rota.';return;}
 (r.legs||[]).forEach(leg=>{
  const line=document.createElement('div');line.className='flightops-leg';
  const desc=document.createElement('span');desc.textContent=leg.from+' → '+leg.to;
  const metric=document.createElement('b');metric.textContent=number(leg.nm,1)+' NM • '+number(leg.bearing_deg)+'° • '+number(leg.minutes,1)+' min';
  line.append(desc,metric);parent.append(line);
 });
}
function metar(w){
 if(!w)return 'Indisponível';
 const summary=w.raw||[w.wind_direction!=null?number(w.wind_direction)+'°':'',
  w.wind_kt!=null?number(w.wind_kt)+' kt':'',w.visibility_m!=null?number(w.visibility_m)+' m':''].filter(Boolean).join(' / ');
 return summary.slice(0,180)||'Sem dados de estação';
}
function render(s){
 currentState=s;
 const data=s?.flight_operations||{};
 const saved=data.draft||{mode:'free',origin:'',destination:'',altitude_ft:2500,waypoints:[],checks:{}};
 const key=JSON.stringify(saved);
 if(!dirty && key!==draftKey){useDraft(saved);draftKey=key;}
 if(data.notice?.seq!=null && data.notice.seq!==noticeSeq){
  noticeSeq=data.notice.seq;text('fo-message',data.notice.message);
  if(data.notice.ok && ['flightops_save','flightops_clear'].includes(data.notice.action)){
   dirty=false;draftKey='';lastPreviewRoute=null;
  }
 }
 el('fo-contract').disabled=!data.contract;
 el('fo-save').disabled=!data.ready||s?.phase==='EM VOO';
 el('fo-clear').disabled=s?.phase==='EM VOO';
 el('fo-export').disabled=!data.ready||dirty||!data.route;
 el('fo-send').disabled=!data.ready||dirty||!data.route||s?.connection!=='connected'||s?.telemetry?.stale||!(s?.phase!=='EM VOO'&&s?.phase!=='AIRBORNE');
 text('fo-airport-source',data.ready?'ICAOs confirmados pelo MSFS':'Aguardando catálogo MSFS');
 const r=visibleRoute(data);
 if(!dirty)text('fo-status',r?'ROTA VFR SALVA':'AGUARDANDO ROTA');
 else text('fo-status',r?'PRÉVIA • NÃO SALVA':'AGUARDANDO CÁLCULO');
 if(dirty&&data.preview?.id===previewRequest&&data.preview.error)
  text('fo-message','Prévia não disponível: '+data.preview.error);
 text('fo-distance',r?number(r.distance_nm,1)+' NM':'—');
 text('fo-duration',r?number(r.minutes)+' min':'—');
 text('fo-aircraft',data.aircraft_title||'Aeronave não selecionada');
 text('fo-fuel-available',r?.fuel_available_gal!=null?number(r.fuel_available_gal,1)+' gal':'Sem leitura');
 text('fo-fuel-required',r?.fuel_required_gal!=null?number(r.fuel_required_gal,1)+' gal':'Não calculado');
 text('fo-fuel-status',r?.fuel_ok===true?'Estimativa compatível com o combustível disponível':
  r?.fuel_ok===false?'ALERTA: combustível abaixo do estimado com reserva':'Sem confirmação de combustível');
 text('fo-payload',data.contract&&mode==='contract'?(data.contract.manifest||'Contrato ativo')+
   (data.contract.payload_kg!=null?' • '+number(data.contract.payload_kg,1)+' kg':''):'Voo livre • sem manifesto de contrato');
 text('fo-weight',r?.weight_lbs!=null&&r?.mtow_lbs!=null?number(r.weight_lbs,1)+' / '+number(r.mtow_lbs,1)+' lb':'Sem leitura MSFS');
 text('fo-weight-status',r?.weight_ok===true?'Abaixo do MTOW':'Peso não confirmado ou acima do limite');
 text('fo-weather-origin','ORIGEM — '+metar(s?.weather?.origin));
 text('fo-weather-destination','DESTINO — '+metar(s?.weather?.destination_metar||s?.weather?.destination_sim));
 const bonus=s?.bonus?.bonus_fraction;
 text('fo-bonus',mode==='contract'&&data.contract?
   'Bônus de realismo previsto: +'+number((bonus||0)*100,1)+'% (congelado na decolagem).':
   'Voo livre: sem bônus, XP ou pagamento de contrato.');
 const statuses={pending:'Aguardando preparação',waiting_navdata:'Aguardando aeroportos',
   waiting_sim:'Aguardando SimConnect',loading:'Enviado: aguardando resposta ATC',
   atc_sent:'ATC recebeu o plano (GPS não confirmado)',error:'Falha no envio',
   invalid_airport:'Aeroporto de contrato não verificado'};
 text('fo-dispatch-state',mode==='contract'&&data.contract?
   statuses[data.dispatch?.route]||'Não preparado': 'Voo livre: exportação/ATC opcional');
 renderLegs(r);
}
function show(){if(currentState)render(currentState);}
function mapState(s){
 const route=visibleRoute(s?.flight_operations);
 if(!route?.route||route.route.length<2)return {...s,mission:null};
 const points=route.route;
 return {...s,mission:{id:'flightops:'+route.route_key,origin:route.origin,
  destination:route.destination,start:points[0],end:points[points.length-1],
  route_points:points,waypoints:route.waypoints}};
}
el('fo-plan').onclick=()=>{
 dirty=true;lastPreviewRoute=visibleRoute(currentState?.flight_operations)||lastPreviewRoute;
 text('fo-message','Calculando rota com os waypoints atuais...');
 schedulePreview(0);refreshMap();
};
el('fo-free').onclick=()=>{mode='free';showMode();markDirty();};
el('fo-contract').onclick=()=>{
 const m=currentState?.flight_operations?.contract;
 if(!m){text('fo-message','Aceite um contrato antes de usar a modalidade contratada.');return;}
 mode='contract';el('fo-origin').value=m.origin;el('fo-destination').value=m.destination;
 showMode();markDirty();
};
ids.forEach(x=>el('fo-'+x).addEventListener('input',markDirty));
Object.values(checkKeys).forEach(id=>el(id).addEventListener('change',markDirty));
el('fo-add-fix').onclick=()=>{
 const label=el('fo-fix-label').value.trim().toUpperCase(),
       lat=Number(el('fo-fix-lat').value),lon=Number(el('fo-fix-lon').value);
 if(fixes.length>=8||!(/^[A-Z0-9_-]{1,12}$/.test(label))||
    !el('fo-fix-lat').value||!el('fo-fix-lon').value||
    !Number.isFinite(lat)||!Number.isFinite(lon)||
    Math.abs(lat)>90||Math.abs(lon)>180||fixes.some(w=>w.label===label)){
  text('fo-message','Waypoint inválido, duplicado ou acima do limite de oito.');return;
 }
 fixes.push({label,lat,lon});renderFixes();markDirty();
 for(const id of ['fo-fix-label','fo-fix-lat','fo-fix-lon'])el(id).value='';
};
el('fo-clear').onclick=()=>{
 if(!confirm(mode==='contract'?
    'Limpar waypoints e checklist? Origem/destino e contrato permanecem.':
    'Limpar destino, waypoints, altitude e checklist do voo livre?'))return;
 send('flightops_clear');
};
el('fo-save').onclick=()=>{
 const draft=collect();
 if(!Number.isInteger(draft.altitude_ft)||draft.altitude_ft<500||draft.altitude_ft>45000||
    !/^[A-Z0-9]{4}$/.test(draft.origin)||!/^[A-Z0-9]{4}$/.test(draft.destination)){
  text('fo-message','Confira ICAOs e altitude (500–45000 ft).');return;
 }
 send('flightops_save',draft);
};
el('fo-export').onclick=()=>{if(dirty)return;text('fo-message','Exportando arquivo de navegação...');send('flightops_export');};
el('fo-send').onclick=()=>{if(dirty)return;text('fo-message','Solicitando envio ao ATC...');send('flightops_send');};
function proposeWaypoint(lat,lon){
 if(document.querySelector('.workspace')?.dataset.view!=='planning')return false;
 if(fixes.length>=8){text('fo-message','Limite de oito waypoints atingido.');return false;}
 if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)return false;
 let i=1;while(fixes.some(w=>w.label==='FSC'+String(i).padStart(2,'0')))i++;
 fixes.push({label:'FSC'+String(i).padStart(2,'0'),lat:+lat.toFixed(7),lon:+lon.toFixed(7)});
 renderFixes();markDirty();return true;
}
function moveWaypoint(index,lat,lon){
 if(document.querySelector('.workspace')?.dataset.view!=='planning'||!Number.isInteger(index)||
    index<0||index>=fixes.length||!Number.isFinite(lat)||!Number.isFinite(lon)||
    Math.abs(lat)>90||Math.abs(lon)>180)return false;
 fixes[index]={...fixes[index],lat:+lat.toFixed(7),lon:+lon.toFixed(7)};
 renderFixes();markDirty();return true;
}
function fallbackCoords(e){
 if(!projection||document.querySelector('.workspace')?.dataset.view!=='planning')return null;
 const svg=el('route-map');
 let x,y;
 try{
  const point=svg.createSVGPoint();point.x=e.clientX;point.y=e.clientY;
  const transformed=point.matrixTransform(svg.getScreenCTM().inverse());x=transformed.x;y=transformed.y;
 }catch{return null;}
 const p=projection;
 return {lon:p.lon0+(x-450-p.panX)/(p.cos*p.scale),lat:p.lat0-(y-170-p.panY)/p.scale};
}
function fromSvgEvent(e){
 const p=fallbackCoords(e);
 return p?proposeWaypoint(p.lat,p.lon):false;
}
function registerMapGestures(){
 const svg=el('route-map');
 svg.addEventListener('contextmenu',e=>{if(document.querySelector('.workspace')?.dataset.view!=='planning')return;e.preventDefault();fromSvgEvent(e);});
 svg.addEventListener('click',e=>{if(e.shiftKey && document.querySelector('.workspace')?.dataset.view==='planning'){e.preventDefault();fromSvgEvent(e);}});
 let touchTimer=null,started=null;
 svg.addEventListener('pointerdown',e=>{
  if(e.pointerType!=='touch'||document.querySelector('.workspace')?.dataset.view!=='planning')return;
  started={x:e.clientX,y:e.clientY};
  touchTimer=setTimeout(()=>{fromSvgEvent(e);touchTimer=null;},800);
 });
 svg.addEventListener('pointermove',e=>{
  if(started&&Math.hypot(e.clientX-started.x,e.clientY-started.y)>12){
   clearTimeout(touchTimer);touchTimer=null;started=null;
  }
 });
 for(const eventName of ['pointerup','pointercancel','pointerleave'])
  svg.addEventListener(eventName,()=>{clearTimeout(touchTimer);touchTimer=null;started=null;});
}
// Clique direito/Shift+clique adicionam diretamente, sem diálogo de confirmação.
for(const id of ['fo-map-cancel','fo-map-cancel-top'])
 if(el(id))el(id).onclick=()=>el('fo-map-point-dialog').close();
registerMapGestures();
window.FSCFlightOps={render,show,mapState,proposeWaypoint,moveWaypoint,fallbackCoords,
  setFallbackProjection:p=>{projection=p;}};

})();