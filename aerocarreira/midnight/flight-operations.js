/* FlightSimCarreira Flight Operations v0.8.2 — UI sem estado financeiro. */
(()=>{
'use strict';
const el=id=>document.getElementById(id);
let mode='free',fixes=[],draftKey='',dirty=false,noticeSeq=null,currentState=null,lastSuccessful=null;
const ids=['origin','destination','altitude'];
const checkKeys={runway_checked:'fo-check-runway',route_checked:'fo-check-route',
                 fuel_checked:'fo-check-fuel',payload_checked:'fo-check-payload'};
const text=(id,value)=>{el(id).textContent=value==null?'—':String(value)};
const number=(n,d=0)=>n==null?'—':Number(n).toLocaleString('pt-BR',{maximumFractionDigits:d});
function markDirty(){
 dirty=true;text('fo-status','ALTERAÇÕES NÃO SALVAS');
 text('fo-message','Salve o plano para recalcular e atualizar o mapa.');
 renderLegs(null);
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
 showMode();renderFixes();dirty=false;lastSuccessful=JSON.stringify(collect());
}
function renderFixes(){
 const box=el('fo-waypoints');box.replaceChildren();
 if(!fixes.length){const e=document.createElement('small');e.textContent='Rota direta • sem waypoints';box.append(e);return;}
 fixes.forEach((w,i)=>{
  const row=document.createElement('div'),name=document.createElement('span'),remove=document.createElement('button');
  name.textContent=(i+1)+'. '+w.label+' • '+number(w.lat,4)+'°, '+number(w.lon,4)+'°';
  remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remover '+w.label);
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
async function send(action,payload){
 const body=payload?{action,payload}:{action};
 try{
  const r=await fetch('/command',{method:'POST',headers:{
    'X-Flight-Token':token,'Content-Type':'application/json'
   },body:JSON.stringify(body)});
  if(!r.ok)throw Error('HTTP '+r.status);
  text('fo-message','Solicitação recebida pelo motor. Aguardando confirmação.');
 }catch(err){text('fo-message','Falha ao comunicar com o motor: '+err.message);}
}
function renderLegs(r){
 const parent=el('fo-legs');parent.replaceChildren();
 if(!r){parent.textContent='Revisão necessária • salve para calcular.';return;}
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
  if(data.notice.ok && data.notice.action==='flightops_save'){
   dirty=false;draftKey='';lastSuccessful=JSON.stringify(collect());
  }
 }
 el('fo-contract').disabled=!data.contract;
 el('fo-save').disabled=!data.ready||s?.phase==='EM VOO';
 el('fo-export').disabled=!data.ready||dirty||!data.route;
 el('fo-send').disabled=!data.ready||dirty||!data.route||s?.connection!=='connected'||s?.telemetry?.stale||!(s?.phase!=='EM VOO'&&s?.phase!=='AIRBORNE');
 text('fo-airport-source',data.ready?'ICAOs confirmados pelo MSFS':'Aguardando catálogo MSFS');
 const r=dirty?null:data.route;
 if(!dirty)text('fo-status',r?'ROTA VFR SALVA':'AGUARDANDO ROTA');
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
 if(!dirty)renderLegs(r);
}
function show(){if(currentState)render(currentState);}
function mapState(s){
 const route=(!dirty && s?.flight_operations?.route)||null;
 if(!route?.route||route.route.length<2)return {...s,mission:null};
 const points=route.route;
 return {...s,mission:{id:'flightops:'+route.route_key,origin:route.origin,
  destination:route.destination,start:points[0],end:points[points.length-1],
  route_points:points,waypoints:route.waypoints}};
}
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
window.FSCFlightOps={render,show,mapState};
})();