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
 const names=['soldado2','soldado1','cabo','sargento3','sargento2','sargento1','suboficial','aspirante',
  'tenente2','tenente1','capitao','major','tenente_coronel','coronel','brigadeiro','major_brigadeiro','tenente_brigadeiro','marechal'];
 const key=rank?.code||'soldado2',idx=Math.max(0,names.indexOf(key)),officer=idx>=7;
 // Prancha vertical estreita, sem esticar o SVG: preserva as estrelas e os galões.
 const svg=make('svg',{viewBox:'0 0 110 128',role:'img','aria-label':rank?.title||'Distintivo',class:'pc-rank-svg '+dim});
 const g=make('g',{});
 const rim=officer?'M23 33L40 13H86V108L69 116H23Z':'M24 13H86V90L55 113L24 90Z';
 const inner=officer?'M30 37L44 22H78V103L66 108H30Z':'M31 22H79V85L55 102L31 85Z';
 add(g,make('path',{d:rim,fill:'#071b32',stroke:idx>=14?'#dcb973':'#b3cedc','stroke-width':2.7,'stroke-linejoin':'round'}),
  make('path',{d:inner,fill:'#103956',stroke:'#45748c','stroke-width':1.5}),
  make('path',{d:'M34 27H75',stroke:'#d9f5ff','stroke-opacity':'.23','stroke-width':1.4}));
 if(!officer){
  const bars=Math.min(6,idx+1);
  for(let i=0;i<bars;i++){
   const y=34+i*10;
   g.append(make('path',{d:'M35 '+y+'L55 '+(y+12)+'L75 '+y,fill:'none',
    stroke:idx>=5?'#d9bc82':'#deedf3','stroke-width':4,'stroke-linecap':'round','stroke-linejoin':'round'}));
  }
  if(idx===6)g.append(make('circle',{cx:55,cy:29,r:4.5,fill:'#e7d7a7',stroke:'none'}));
 }else{
  const stars=idx===7?1:idx===8?1:idx===9?2:idx===10?3:idx===11?1:idx===12?2:idx===13?3:idx===14?1:idx===15?2:idx===16?3:4;
  if(idx>=11&&idx<=13)g.append(make('path',{d:'M36 45V94M41 45V94',stroke:'#d6bb80','stroke-width':2}));
  if(idx>=14)g.append(make('path',{d:'M33 38H75M33 43H75',stroke:'#d1ae64','stroke-width':2}));
  for(let i=0;i<stars;i++){
   const cx=stars===1?55:(stars===2?43+i*24:stars===3?39+i*16:42+(i%2)*25);
   const cy=stars===4?59+Math.floor(i/2)*25:stars===3?69:65;
   const points=Array.from({length:10},(_,j)=>{
    const a=-Math.PI/2+j*Math.PI/5,r=j%2?3.5:8;
    return (cx+Math.cos(a)*r).toFixed(1)+','+(cy+Math.sin(a)*r).toFixed(1);
   }).join(' ');
   g.append(make('polygon',{points,fill:'#f5df9e',stroke:'#957546','stroke-width':.9}));
  }
 }
 svg.append(g);return svg;
}
let medalSerial=0;
function medalSvg(code,state='earned'){
 const titles={
 first_flight:'Primeiro Voo',ten_flights:'10 Voos',twentyfive_flights:'25 Voos',
 veteran:'Veterano',hundred_hours:'100 Horas',first_contract:'Primeiro Contrato',
 ten_contracts:'10 Contratos',reputation70:'Reputação 70',reputation90:'Reputação 90',
 first_job:'Primeiro Emprego',first_plane:'Primeira Aeronave',
 three_planes:'Frota Estabelecida',first_license:'Habilitação Avançada'
 };
 const themes={
 first_flight:['#67d9ee','#d5edf5','#164d67'],ten_flights:['#a3cfed','#dceef4','#174461'],
 twentyfive_flights:['#cbb7f0','#f3e6fc','#433f7a'],veteran:['#edc476','#fff0b3','#765223'],
 hundred_hours:['#92d9e6','#edf8f4','#235568'],
 first_contract:['#95bcdf','#e3edf8','#264969'],ten_contracts:['#dfb574','#fff1d0','#6a482c'],
 reputation70:['#8be2c8','#e1fff0','#165f55'],reputation90:['#f9d66b','#fff9cd','#8b5515'],
 first_job:['#a5bedb','#ecf4ff','#234b7c'],first_plane:['#e7bf7e','#fff2c8','#6e512e'],
 three_planes:['#c5d4f6','#f2f7ff','#2b4c76'],first_license:['#d9c8e7','#fff2f4','#65486e']
 };
 const [metal,light,dark]=themes[code]||['#f1c87a','#fff7d5','#6e522e'];
 const id='pc-medal-gradient-'+(++medalSerial);
 const svg=make('svg',{viewBox:'0 0 118 126',role:'img','aria-label':'Medalha: '+(titles[code]||code),class:'pc-medal-svg pc-medal-'+code});
 const defs=make('defs'),gradient=make('linearGradient',{id,x1:'0',x2:'1',y1:'0',y2:'1'});
 gradient.append(make('stop',{offset:'0%', 'stop-color':light}),make('stop',{offset:'52%','stop-color':metal}),make('stop',{offset:'100%','stop-color':dark}));
 defs.append(gradient);svg.append(defs);
 const fillMetal='url(#'+id+')';
 const path=(d,fill='none',stroke='none',width=2)=>svg.append(make('path',{d,fill,stroke,'stroke-width':width,'stroke-linecap':'round','stroke-linejoin':'round'}));
 const line=(d,color=metal,width=2)=>path(d,'none',color,width);
 const text=(s,x,y,size=15,color=light,weight=800)=>svg.append(make('text',{x,y,'font-family':'Arial,sans-serif','font-size':size,'font-weight':weight,'text-anchor':'middle',fill:color,stroke:'none'},String(s)));
 const circle=(cx,cy,r,fill,stroke='none',w=1)=>svg.append(make('circle',{cx,cy,r,fill,stroke,'stroke-width':w}));
 const plane=(x,y,scale=1)=>svg.append(make('path',{d:'M'+(x-18*scale)+' '+(y+5*scale)+'l'+(15*scale)+' '+(-6*scale)+'v'+(-10*scale)+'q'+(3*scale)+' '+(-5*scale)+' '+(6*scale)+' 0v'+(10*scale)+'l'+(15*scale)+' '+(6*scale)+'v'+(6*scale)+'l'+(-15*scale)+' '+(-3*scale)+'v'+(10*scale)+'l'+(6*scale)+' '+(4*scale)+'v'+(4*scale)+'l'+(-10*scale)+' '+(-2*scale)+'l'+(-10*scale)+' '+(2*scale)+'v'+(-4*scale)+'l'+(6*scale)+' '+(-4*scale)+'v'+(-10*scale)+'l'+(-15*scale)+' '+(3*scale)+'Z',fill:light,stroke:dark,'stroke-width':1,'stroke-linejoin':'round'}));
 // Fita e aro compartilhados; o interior é diferente para cada conquista.
 path('M34 3H54L67 42H48Z','#16435e',metal,1.5);
 path('M64 3H84L70 42H51Z','#803948',metal,1.5);
 circle(59,80,40,'#092537',metal,4.4);
 circle(59,80,33,fillMetal,light,1.3);
 circle(59,80,29,dark,metal,1.2);
 line('M40 56Q59 44 78 56',light,1.15);
 line('M40 103Q59 114 78 103',light,1.15);
 switch(code){
  case 'first_flight':
   path('M31 97L87 97', 'none',light,2);
   line('M37 92L76 63',metal,2.5);plane(61,73,.75);text('1º',59,99,16);break;
  case 'ten_flights':case 'twentyfive_flights':case 'veteran':
   line('M35 92Q26 72 42 57M83 92Q92 72 76 57',metal,3);
   for(const y of [65,75,85]){path('M39 '+y+'l-8 -4 3 10Z',metal);path('M79 '+y+'l8 -4 -3 10Z',metal);}
   text(code==='ten_flights'?'10':code==='twentyfive_flights'?'25':'50',59,88,25);
   text(code==='veteran'?'VET': 'VOOS',59,100,8);break;
  case 'hundred_hours':
   circle(59,76,22,'#132f43',light,2);
   for(const a of [0,90,180,270]){const rad=a*Math.PI/180;line('M'+(59+18*Math.cos(rad))+' '+(76+18*Math.sin(rad))+'L'+(59+21*Math.cos(rad))+' '+(76+21*Math.sin(rad)),metal,2);}
   line('M59 76L59 61M59 76L71 83',light,2.7);text('100h',59,108,12);break;
  case 'first_contract':case 'ten_contracts':
   path('M42 58H69L78 67V99H42Z','#e3e8e3',metal,2);
   path('M69 58V67H78',dark,metal,1);
   line('M48 75H69M48 80H66',dark,2);
   text(code==='first_contract'?'1º':'10',60,95,16,dark);break;
  case 'reputation70':case 'reputation90':
   circle(59,73,19,code==='reputation90'?'#6e4818':'#1a554c',light,2);
   path('M48 73L56 81L72 65','none',light,4);
   text(code==='reputation90'?'90%':'70%',59,107,18,light);
   if(code==='reputation90'){for(const x of [35,83]){path('M'+x+' 61l3 7 -3 7 -3 -7Z',light);}}
   break;
  case 'first_job':
   path('M39 69H79V96H39Z','#193d56',light,2);
   path('M50 69V63Q59 56 68 63V69','none',metal,3);
   line('M39 78Q59 91 79 78',light,2.3);
   circle(59,81,5,fillMetal,light,1);break;
  case 'first_plane':
   // Aeronave em solo, trem de pouso e marca inaugural.
   path('M35 87Q44 84 51 83L70 83L84 88L78 92H42Z',light,dark,1.5);
   line('M49 84L52 73L56 74L56 84',metal,2.5);
   line('M41 94H81',light,2.5);circle(47,93,3,'#071d2c');circle(75,93,3,'#071d2c');
   text('1º',59,69,17,light);break;
  case 'three_planes':
   path('M33 92V69L59 56L85 69V92Z','#153c56',light,2);
   path('M40 90V74H78V90', 'none',metal,2);
   for(const x of [47,59,71]){
    path('M'+x+' 72v14m-5 -6h10m-8 10h6','none',light,2.6);
    circle(x,88,1.6,metal);
   }
   line('M36 95H82',light,2);break;
  case 'first_license':
   path('M42 57H76V94H42Z','#e9e2d4',metal,2);
   line('M48 64H70M48 70H67',dark,2);
   circle(60,82,9,fillMetal,dark,1);
   path('M55 83L59 87L66 78','none',dark,2.5);
   path('M55 91L52 103L60 99L68 103L65 91',metal);break;
  default:plane(59,81,.8);
 }
 // A medalha bloqueada fica fosca, mas preserva o motivo para revisão de design.
 if(state!=='earned')svg.classList.add(state==='available'?'pc-medal-available':'pc-medal-locked');
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
  card.append(footer);
  if(q.status==='available'&&!pc.is_test){
   const button=n('button','button pc-license-claim','Conquistar certificado');
   button.onclick=()=>act('pilot_license_claim',undefined,q.code);
   card.append(button);
  }
  root.append(card);
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
  adminDraft={level:show.level||pc.level,xp:show.xp??pc.xp,reputation:show.reputation??pc.reputation,
    licenses:{...show.licenses},achievements:{...show.achievements},rank:show.rank||null};
 }
 set('pc-admin-warning','Ambiente de testes isolado. Mudanças de prévia não alteram voos, saldo nem o piloto principal.');
 el('pc-admin-level').value=String(adminDraft.level);
 el('pc-admin-xp').value=String(adminDraft.xp||0);
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
  adminDraft.xp=Number(el('pc-admin-xp').value);
  adminDraft.reputation=Number(el('pc-admin-rep').value);
  adminDraft.rank=el('pc-admin-rank').value||null;
  act('pilot_showcase',adminDraft);
 };
 el('pc-admin-reset').onclick=()=>{
  adminDraft={level:1,xp:0,reputation:50,rank:null,achievements:{},licenses:{}};
  act('pilot_showcase',adminDraft);
 };
 el('pc-admin-preset').onchange=()=>{
  const lv=Number(el('pc-admin-preset').value);
  if(lv){
   el('pc-admin-level').value=lv;
   el('pc-admin-xp').value=lv*100;
   el('pc-admin-rep').value=lv>=80?95:lv>=30?75:50;
   // Presets para aprovação de TODOS os estados visuais. É somente prévia.
   const pc=current?.pilot_career;
   if(pc){
    const state=lv>=100?'earned':lv>=55?'available':'locked';
    adminDraft.achievements=Object.fromEntries(pc.medals.map(m=>[m.code,state]));
    adminDraft.licenses=Object.fromEntries(pc.licenses.map(q=>[q.code,state]));
    const n=Math.max(0,pc.rank_gallery.findIndex(r=>r.min<=lv&&r.max>=lv));
    adminDraft.rank=pc.rank_gallery[n]?.code||null;
    el('pc-admin-rank').value=adminDraft.rank;
    document.querySelectorAll('#pc-admin-states select').forEach(sel=>{
     sel.value=state;
     sel.dispatchEvent(new Event('change'));
    });
   }
  }
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