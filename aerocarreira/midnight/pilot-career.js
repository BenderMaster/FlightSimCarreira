/* Midnight Ops — Pilot Career v0.8.3.
 * Emblemas vetoriais locais; nenhuma mídia externa nem alteração de ledger pela UI.
 */
(()=>{
'use strict';
const el=id=>document.getElementById(id);
let current=null,activeTab='overview',lastSeq=null,noticeSeq=null,lastSignature='',adminDraft=null,lastRenderedSignature='';
const tabs=['overview','achievements','licenses','graphs','timeline','admin'];
const xns='http://www.w3.org/2000/svg', fmt=(n,d=0)=>
 Number(n||0).toLocaleString('pt-BR',{maximumFractionDigits:d});
const set=(id,t)=>{if(el(id))el(id).textContent=t??'—'};
const n=(tag,cls,text)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(text!=null)x.textContent=text;return x};
const make=(tag,attrs={},text)=>{const s=document.createElementNS(xns,tag);for(const [k,v] of Object.entries(attrs))s.setAttribute(k,String(v));if(text!=null)s.textContent=text;return s};
const add=(p,...c)=>{c.forEach(x=>p.append(x));return p};
function rankSvg(rank,dim='normal'){
 const key=rank?.code||'soldado2', names=['soldado2','soldado1','cabo','sargento3','sargento2','sargento1','suboficial','aspirante',
  'tenente2','tenente1','capitao','major','tenente_coronel','coronel','brigadeiro','major_brigadeiro','tenente_brigadeiro','marechal'];
 const idx=Math.max(0,names.indexOf(key)),officer=idx>=7;
 const svg=make('svg',{viewBox:'0 0 140 116',role:'img','aria-label':rank?.title||'Distintivo',class:'pc-rank-svg '+dim});
 const g=make('g',{});
 add(g,make('path',{d:officer?'M13 33L32 14H128V92L108 105H13Z':'M14 12H126V90L70 110L14 90Z',
  fill:'#08213B',stroke:'#c1d4dc','stroke-width':3.5}),
  make('path',{d:officer?'M21 37L36 22H118V86L105 96H21Z':'M24 23H116V85L70 100L24 85Z',
  fill:'#103d65',stroke:'#416a88','stroke-width':1.5}),
  make('path',{d:'M30 30H110',stroke:'#ffffff','stroke-opacity':'.24','stroke-width':2}));
 if(!officer){
  const bars=Math.min(6,1+idx);
  for(let i=0;i<bars;i++){
   const yy=35+i*9;
   g.append(make('path',{d:'M28 '+yy+'L70 '+(yy+16)+'L112 '+yy,fill:'none',
    stroke:idx>4?'#D5B976':'#DAE8EF','stroke-width':5,'stroke-linejoin':'round'}));
  }
 } else {
  if(idx>=12){g.append(make('path',{d:'M28 23L43 95M50 23L65 95',stroke:'#d6b876','stroke-width':4}));}
  const stars=idx===7?1:idx===8?1:idx===9?2:idx===10?3:idx===11?1:idx===12?2:idx===13?3:idx===14?1:idx===15?2:idx===16?3:4;
  for(let i=0;i<stars;i++){
   const col=i%3,row=Math.floor(i/3);
   const cx=41+col*29,cy=idx>=14?52+row*23:57+row*23;
   const points=Array.from({length:10},(_,j)=>{
    const a=-Math.PI/2+j*Math.PI/5,r=j%2?5.5:12;
    return (cx+Math.cos(a)*r)+','+(cy+Math.sin(a)*r);
   }).join(' ');
   g.append(make('polygon',{points,fill:'#F7E8B4',stroke:'#a37e37','stroke-width':1}));
  }
 }
 svg.append(g);return svg;
}
function medalSvg(code,state='earned'){
 const svg=make('svg',{viewBox:'0 0 118 126',role:'img','aria-label':'Medalha '+code,class:'pc-medal-svg'});
 const variant=['#f7cb6c','#6de2ee','#e9ad9f','#bbd0ec'][Math.abs(Array.from(code||'').reduce((s,c)=>s+c.charCodeAt(0),0))%4];
 add(svg,make('path',{d:'M35 3H55L69 45H48Z',fill:'#124c75',stroke:'#6bbdd6','stroke-width':2}),
 make('path',{d:'M63 3H83L67 45H49Z',fill:'#742e42',stroke:'#dc8e88','stroke-width':2}),
 make('circle',{cx:59,cy:78,r:41,fill:'#0e2b41',stroke:variant,'stroke-width':5}),
 make('circle',{cx:59,cy:78,r:32,fill:'#123c5a',stroke:'#f5e4ad','stroke-width':1.7}),
 make('path',{d:'M59 49L67 69L89 71L72 85L78 105L59 92L40 105L46 85L29 71L51 69Z',
 fill:variant,stroke:'#fff3c9','stroke-width':1.2}),
 make('circle',{cx:59,cy:78,r:6,fill:'#153a53'}));
 if(state!=='earned')svg.setAttribute('opacity',state==='available'?'.72':'.38');
 return svg;
}
function stateLabel(status){return {earned:'CONQUISTADA',available:'DISPONÍVEL',locked:'BLOQUEADA'}[status]||status;}
async function act(action,payload,id){
 let body={action};
 if(payload!==undefined)body.payload=payload;
 if(id!==undefined)body.id=id;
 try{
  const r=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json','X-Flight-Token':token},body:JSON.stringify(body)});
  if(!r.ok)throw Error('HTTP '+r.status);
  set('pc-message','Solicitação enviada. Aguarde a confirmação do motor.');
 }catch(e){set('pc-message','Falha ao executar operação: '+e.message);}
}
function showTab(tab){
 activeTab=tabs.includes(tab)?tab:'overview';
 document.querySelectorAll('[data-pc-tab]').forEach(b=>{
  const active=b.dataset.pcTab===activeTab;
  b.classList.toggle('selected',active);
  b.setAttribute('aria-pressed',String(active));
 });
 for(const t of tabs){const x=el('pc-tab-'+t);if(x)x.hidden=t!==activeTab;}
}
function avatar(state){
 const img=el('pc-portrait');
 img.hidden=!state.avatar;
 if(state.avatar&&img.src!==state.avatar)img.src=state.avatar;
 el('pc-portrait-fallback').hidden=!!state.avatar;
}
function fillRank(host,rank,klass){
 host.replaceChildren(rankSvg(rank,klass));
 host.title=(rank?.title||'Distintivo')+' • FlightSimCarreira';
}
function profileHeader(state){
 const pc=state.pilot_career,p=state.pilot||{};
 set('pc-name',p.name||'Piloto não cadastrado');set('pc-callsign',p.callsign||'—');
 set('pc-base',p.home_icao||'—');set('pc-joined',p.created_utc?
  new Date(p.created_utc*1000).toLocaleDateString('pt-BR'):'—');
 set('pc-employment',({autonomo:'Piloto autônomo',empregado:'Piloto contratado',empresario:'Companhia própria'})[state.employment]||state.employment);
 set('pc-level','NÍVEL '+pc.level);set('pc-rank-name',pc.rank.title);
 const prog=pc.progress;
 set('pc-progress-label',prog.next_level?
  'Próximo nível '+prog.next_level+' • '+Math.round(prog.fraction*100)+'%':'Nível máximo');
 el('pc-xpbar').style.width=(100*Math.max(0,Math.min(1,prog.fraction)))+'%';
 fillRank(el('pc-main-rank'),pc.rank,'large');
 const med=el('pc-main-medal');
 med.replaceChildren();
 if(pc.equipped)med.append(medalSvg(pc.equipped));
 med.hidden=!pc.equipped;
 avatar(state);
 const vals=[['Voos realizados',pc.flights,'plane'],['Horas de voo',fmt(pc.hours,1)+' h','clock'],
 ['Contratos',pc.contracts,'file-text'],['Reputação',pc.reputation+'/100','shield'],
 ['Aeronaves pilotadas',pc.aircraft_types,'plane'],['Ganhos em contratos','R$ '+fmt(pc.earned_money),'coins']];
 const host=el('pc-statistics');host.replaceChildren();
 vals.forEach(([label,value,icon])=>{
  const card=n('div','pc-stat');card.append(n('small','',label),n('strong','',String(value)));host.append(card);
 });
 el('pc-tab-button-admin').hidden=!pc.is_test;
}
function overview(pc){
 const badges=el('pc-rank-track');badges.replaceChildren();
 const ranks=pc.rank_gallery;
 const currentIndex=ranks.findIndex(r=>r.code===pc.rank.code);
 const lo=Math.max(0,currentIndex-2),hi=Math.min(ranks.length,Math.max(5,currentIndex+3));
 ranks.slice(lo,hi).forEach(r=>{
  const cell=n('div','pc-track-rank '+(r.code===pc.rank.code?'current':'')+' '+r.state);
  add(cell,rankSvg(r,'small'),n('small','',r.title));badges.append(cell);
 });
 const medals=el('pc-featured-medals');medals.replaceChildren();
 const fav=pc.medals.filter(x=>x.status==='earned').slice(-4).reverse();
 if(!fav.length)medals.append(n('p','pc-empty','As primeiras medalhas aparecerão depois dos seus voos.'));
 fav.forEach(m=>{
  const div=n('div','pc-featured');div.append(medalSvg(m.code),n('strong','',m.title));medals.append(div);
 });
}
function achievements(pc){
 const root=el('pc-medal-gallery');root.replaceChildren();
 pc.medals.forEach(m=>{
  const card=n('article','pc-achievement '+m.status+(pc.equipped===m.code?' equipped':''));
  const label=n('small','pc-achievement-status',stateLabel(m.status));
  const name=n('h3','',m.title),descr=n('p','',m.description);
  const counter=n('small','',fmt(Math.min(m.current||0,m.target),1)+' / '+fmt(m.target));
  const art=n('div','pc-achievement-art');art.append(medalSvg(m.code,m.status));
  add(card,art,label,name,descr,counter);
  if(m.variable)card.append(n('small','pc-conditional','Conquista condicionada à reputação atual'));
  if(m.awarded_utc)card.append(n('small','pc-date','Desde '+new Date(m.awarded_utc*1000).toLocaleDateString('pt-BR')));
  if(m.status==='earned'){
   const b=n('button','button pc-equip',pc.equipped===m.code?'Retirar da foto':'Equipar na foto');
   b.onclick=()=>act('pilot_medal_equip',undefined,pc.equipped===m.code?'':m.code);
   card.append(b);
  }
  root.append(card);
 });
}
function licenses(pc){
 const root=el('pc-license-grid');root.replaceChildren();
 pc.licenses.forEach((q,i)=>{
  const card=n('article','pc-license '+q.status);
  const header=n('div','pc-license-head');
  const badge=n('div','pc-license-seal');badge.append(rankSvg({code:['aspirante','tenente2','tenente1','capitao','major'][i]},'small'));
  header.append(n('small','pc-license-brand','FLIGHTSIMCARREIRA  •  PILOT CAREER'),badge);
  add(card,header,n('div','pc-license-code',q.code),n('h3','',q.title),
   n('p','',q.description));
  const footer=n('div','pc-license-foot');
  footer.append(n('span','',q.status==='earned'?'EMITIDA':q.status==='available'?'REQUISITOS ATENDIDOS':'EM PROGRESSO'));
  footer.append(n('strong','',q.date?new Date(q.date*1000).toLocaleDateString('pt-BR'):q.requirements));
  card.append(footer);root.append(card);
 });
}
function graphSvg(title,data,kind){
 const box=n('section','pc-chart-card');box.append(n('h3','',title));
 const svg=make('svg',{viewBox:'0 0 620 245',role:'img','aria-label':title,preserveAspectRatio:'xMidYMid meet'});
 add(svg,make('path',{d:'M40 18V214H608',fill:'none',stroke:'#426074','stroke-width':2}));
 for(let i=0;i<4;i++)svg.append(make('path',{d:'M40 '+(30+i*55)+'H608',stroke:'#38566a','stroke-width':1,'stroke-dasharray':'4 7'}));
 if(data.length){
  const use=data.slice(-42);
  if(kind==='landing'){
   const max=Math.max(300,...use.map(x=>Math.abs(x.fpm)));
   const pts=use.map((v,i)=>[50+(540*i)/Math.max(1,use.length-1),214-Math.min(180,Math.abs(v.fpm)/max*180)]);
   svg.append(make('polyline',{points:pts.map(p=>p.join(',')).join(' '),fill:'none',stroke:'#11def2','stroke-width':3}));
   pts.forEach(([x,y],i)=>{const dot=make('circle',{cx:x,cy:y,r:4.3,fill:'#f2cf7e'});dot.append(make('title',{},fmt(use[i].fpm)+' ft/min'));svg.append(dot);});
  }else{
   const values=use.map(x=>Number(Array.isArray(x)?x[1]:0));
   const max=Math.max(1,...values);const step=545/use.length;
   use.forEach((d,i)=>{
    const h=values[i]/max*168;
    const rect=make('rect',{x:49+i*step,y:211-h,width:Math.max(3,step-9),height:h,rx:4,fill:i%2?'#14c2db':'#deb96c'});
    rect.append(make('title',{},String(d[0])+': '+fmt(values[i],1)));svg.append(rect);
   });
  }
 }else svg.append(make('text',{x:310,y:120,'text-anchor':'middle',fill:'#a2c4d6','font-size':17},'Ainda sem dados registrados'));
 box.append(svg);return box;
}
function graphs(pc){
 const g=el('pc-graphs');g.replaceChildren();
 g.append(graphSvg('SENSIBILIDADE DE POUSO • FT/MIN',pc.graphs.landings,'landing'),
 graphSvg('CONTRATOS CONCLUÍDOS POR MÊS',pc.graphs.contracts,'bar'),
 graphSvg('HORAS POR AERONAVE',pc.graphs.hours_by_aircraft,'bar'));
}
function timeline(pc){
 const root=el('pc-timeline-list');root.replaceChildren();
 const list=pc.timeline;
 if(!list.length){root.append(n('p','pc-empty','Nenhum marco registrado por enquanto.'));return;}
 list.forEach(e=>{
  const row=n('div','pc-timeline-event '+e.kind);
  const icon=n('div','pc-timeline-icon',e.kind==='loss'?'✕':e.kind==='gain'?'✦':'✈');
  const content=n('div','pc-timeline-content');
  content.append(n('strong','',e.title),n('small','',new Date(e.when*1000).toLocaleString('pt-BR')));
  row.append(icon,content);
  if(['gain','loss'].includes(e.kind)){
   const b=n('button','button','Reproduzir');
   b.onclick=()=>showUnlock(e.kind,e.title,e.code);row.append(b);
  }
  root.append(row);
 });
}
function admin(pc){
 const show=pc.showcase||{},root=el('pc-admin-states');
 if(!adminDraft || lastSignature!==pc.active_profile){
  adminDraft={level:show.level||pc.level,reputation:show.reputation??pc.reputation,
    licenses:{...show.licenses},achievements:{...show.achievements},rank:show.rank||null};
 }
 set('pc-admin-warning','Ambiente de testes isolado. Mudanças de prévia não alteram voos, saldo nem o piloto principal.');
 el('pc-admin-level').value=String(adminDraft.level);
 el('pc-admin-rep').value=String(adminDraft.reputation);
 const select=el('pc-admin-rank');select.replaceChildren();
 select.append(new Option('Automático pelo nível',''));
 pc.rank_gallery.forEach(r=>select.append(new Option(r.title,r.code)));
 select.value=adminDraft.rank||'';
 root.replaceChildren();
 function section(title,items,key){
  root.append(n('h3','pc-admin-title',title));
  items.forEach(item=>{
   const row=n('div','pc-admin-item');
   const left=n('span','',item.title||item.code),sel=n('select','');
   for(const [text,value] of [['Bloqueado','locked'],['Disponível','available'],['Conquistado','earned']]){
    sel.append(new Option(text,value));
   }
   sel.value=adminDraft[key][item.code]||item.status;
   sel.onchange=()=>adminDraft[key][item.code]=sel.value;
   row.append(left,sel);root.append(row);
  });
 }
 section('Medalhas / conquistas',pc.medals,'achievements');
 section('Licenças premium',pc.licenses,'licenses');
 const gallery=el('pc-admin-rank-gallery');gallery.replaceChildren();
 pc.rank_gallery.forEach(r=>{
  const card=n('div','pc-gallery-rank '+r.state);
  card.append(rankSvg(r,'small'),n('small','',r.title));
  card.onclick=()=>{adminDraft.rank=r.code;el('pc-admin-rank').value=r.code;};
  gallery.append(card);
 });
 lastSignature=pc.active_profile;
}
function profiles(pc,state){
 const sel=el('pc-profile-select'),old=sel.value;
 sel.replaceChildren();
 (pc.profiles||[]).forEach(p=>sel.append(new Option(
  p.name+(p.kind==='test'?' • Teste/Admin':''),p.id)));
 sel.value=(pc.profiles||[]).some(p=>p.id===old)?old:pc.active_profile;
 el('pc-profile-switch').disabled=sel.value===pc.active_profile;
 const pilot=state.pilot||{};
 if(!el('pc-profile-editor').dataset.loaded || el('pc-profile-editor').dataset.active!==pc.active_profile){
  el('pc-profile-name').value=pilot.name||'';
  el('pc-profile-callsign').value=pilot.callsign||'';
  el('pc-profile-base').value=pilot.home_icao||'';
  el('pc-profile-editor').dataset.loaded='true';
  el('pc-profile-editor').dataset.active=pc.active_profile;
 }
}
function render(s){
 if(!s?.pilot_career)return;
 current=s;const pc=s.pilot_career;
 const signature=JSON.stringify([pc.active_profile,pc.events_seq,pc.level,pc.rank.code,
   pc.reputation,pc.equipped,pc.flights,pc.hours,pc.contracts,pc.medals.map(x=>x.status),
   pc.licenses.map(x=>x.status),pc.showcase,pc.profiles,s.pilot,s.avatar?.length||0]);
 if(signature!==lastRenderedSignature){
  profileHeader(s);overview(pc);achievements(pc);licenses(pc);graphs(pc);timeline(pc);
  profiles(pc,s);if(pc.is_test)admin(pc);
  lastRenderedSignature=signature;
 }
 if(pc.notice?.seq!=null&&noticeSeq!==pc.notice.seq){
  noticeSeq=pc.notice.seq;set('pc-message',pc.notice.message);
 }
 if(lastSeq==null){lastSeq=pc.events_seq;}
 else if(pc.events_seq>lastSeq){
  const newest=pc.timeline.find(e=>e.kind==='gain'||e.kind==='loss');
  if(newest)showUnlock(newest.kind,newest.title,newest.code);
  lastSeq=pc.events_seq;
 }
 showTab(activeTab);
}
function showUnlock(kind,label,code){
 const dialog=el('pc-unlock');
 const art=el('pc-unlock-art');art.replaceChildren();
 if(kind==='loss'){
  const left=medalSvg(code||'veteran'),right=medalSvg(code||'veteran');
  left.classList.add('pc-fragment-left');right.classList.add('pc-fragment-right');
  art.append(left,right);
 }else art.append(medalSvg(code||'veteran'));
 dialog.dataset.kind=kind;
 set('pc-unlock-kicker',kind==='loss'?'CONQUISTA PERDIDA':kind==='promotion'?'NOVA PATENTE':'NOVA CONQUISTA');
 set('pc-unlock-title',label||'Conquista');
 if(!dialog.open)dialog.showModal();
 window.clearTimeout(showUnlock.timeout);
 showUnlock.timeout=window.setTimeout(()=>dialog.close(),2500);
}
function init(){
 document.querySelectorAll('[data-pc-tab]').forEach(b=>b.onclick=()=>showTab(b.dataset.pcTab));
 el('pc-manage-profiles').onclick=()=>{if(!el('pc-profiles-dialog').open)el('pc-profiles-dialog').showModal();};
 el('pc-close-profiles').onclick=()=>el('pc-profiles-dialog').close();
 el('pc-profile-select').onchange=()=>{
  el('pc-profile-switch').disabled=el('pc-profile-select').value===current?.pilot_career?.active_profile;
 };
 el('pc-profile-switch').onclick=()=>{
  if(!confirm('Trocar perfil? O aplicativo vai reiniciar. Desconecte o MSFS antes.'))return;
  act('pilot_profile_switch',undefined,el('pc-profile-select').value);
 };
 el('pc-profile-create').onclick=()=>{
  const p={name:el('pc-new-name').value.trim(),callsign:el('pc-new-callsign').value.trim().toUpperCase(),
   home_icao:el('pc-new-base').value.trim().toUpperCase(),test_admin:el('pc-new-admin').checked};
  act('pilot_profile_create',p);
 };
 el('pc-profile-save').onclick=()=>act('pilot_profile_update',{
  name:el('pc-profile-name').value.trim(),
  callsign:el('pc-profile-callsign').value.trim().toUpperCase(),
  home_icao:el('pc-profile-base').value.trim().toUpperCase()});
 el('pc-profile-photo').onclick=()=>act('avatar');
 el('pc-profile-reset').onclick=()=>{
  if(!confirm('RESETAR o perfil TESTE atual? Será feito um backup do banco de teste.'))return;
  act('pilot_profile_reset');
 };
 el('pc-new-admin').onchange=()=>{
  if(el('pc-new-admin').checked){
   el('pc-new-name').value='Teste';
   el('pc-new-callsign').value='TESTE';
  }
 };
 el('pc-admin-save').onclick=()=>{
  if(!current?.pilot_career?.is_test)return;
  adminDraft.level=Number(el('pc-admin-level').value);
  adminDraft.reputation=Number(el('pc-admin-rep').value);
  adminDraft.rank=el('pc-admin-rank').value||null;
  act('pilot_showcase',adminDraft);
 };
 el('pc-admin-reset').onclick=()=>{
  adminDraft={level:1,reputation:50,rank:null,achievements:{},licenses:{}};
  act('pilot_showcase',adminDraft);
 };
 el('pc-admin-preset').onchange=()=>{
  const lv=Number(el('pc-admin-preset').value);
  if(lv){el('pc-admin-level').value=lv;el('pc-admin-rep').value=lv>=80?95:lv>=30?75:50;}
 };
 el('pc-admin-preview-gain').onclick=()=>showUnlock('gain','Veterano • 50 Voos','veteran');
 el('pc-admin-preview-loss').onclick=()=>showUnlock('loss','Reputação 90','reputation90');
 el('pc-admin-preview-promotion').onclick=()=>showUnlock('promotion','Nova patente','major');
 el('pc-close-unlock').onclick=()=>el('pc-unlock').close();
 el('pc-unlock').addEventListener('click',e=>{if(e.target===el('pc-unlock'))el('pc-unlock').close();});
}
init();
window.FSCPilotCareer={render,show:()=>current&&render(current),rankSvg,medalSvg,showUnlock};
})();