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
function licenseSealSvg(code,tier){
 const svg=make('svg',{viewBox:'0 0 100 100',role:'img','aria-label':'Selo '+code,class:'pc-license-seal-svg'});
 const colors=['#cad9e6','#c9a574','#85d4e7','#e8c779','#ffecb2'];
 const metal=colors[tier]||colors[0];
 svg.append(make('circle',{cx:50,cy:50,r:44,fill:'#09233b',stroke:metal,'stroke-width':3}));
 svg.append(make('circle',{cx:50,cy:50,r:37,fill:'#123951',stroke:metal,'stroke-width':.9,'stroke-dasharray':'3 4'}));
 svg.append(make('path',{d:'M12 49L37 40L44 45L16 55ZM88 49L63 40L56 45L84 55Z',
  fill:metal,stroke:'#0d3349','stroke-width':1.5}));
 svg.append(make('path',{d:'M17 56L40 49M83 56L60 49',fill:'none',stroke:metal,'stroke-width':3}));
 if(code==='IFR'){
  svg.append(make('circle',{cx:50,cy:50,r:19,fill:'#092538',stroke:metal,'stroke-width':2}));
  svg.append(make('path',{d:'M50 30L57 49L50 70L43 49Z',fill:metal,stroke:'#f2f6ea','stroke-width':1}));
 }else if(code==='MLTE'){
  svg.append(make('circle',{cx:42,cy:51,r:10,fill:'#092538',stroke:metal,'stroke-width':2}));
  svg.append(make('circle',{cx:59,cy:51,r:10,fill:'#092538',stroke:metal,'stroke-width':2}));
  svg.append(make('path',{d:'M30 63L50 53L70 63M50 35V70',fill:'none',stroke:metal,'stroke-width':3}));
 }else if(code==='PLA'){
  svg.append(make('path',{d:'M50 25L56 41L73 41L60 52L65 69L50 59L35 69L40 52L27 41L44 41Z',
   fill:metal,stroke:'#fff5d6','stroke-width':1.5}));
 }else{
  svg.append(make('path',{d:'M50 29L57 45L75 49L58 56L54 73L46 56L25 49L43 45Z',fill:metal,stroke:'#0c283a','stroke-width':1.6}));
 }
 svg.append(make('text',{x:50,y:89,'text-anchor':'middle','font-family':'Arial,sans-serif','font-size':10,
  'font-weight':800,fill:metal,stroke:'none'},code));
 return svg;
}
function licenses(pc){
 const root=el('pc-license-grid');root.replaceChildren();
 const subtitles=[
  'PRIMEIROS HORIZONTES','OPERAÇÕES COMERCIAIS','NAVEGAÇÃO POR INSTRUMENTOS',
  'QUALIFICAÇÃO MULTIMOTOR','COMANDO DE LINHA AÉREA'
 ];
 pc.licenses.forEach((q,i)=>{
  const tier=i+1,card=n('article','pc-license pc-license-tier-'+tier+' '+q.status);
  const metadata=n('div','pc-license-meta');
  metadata.append(n('small','pc-license-brand','FLIGHTSIMCARREIRA   /   PILOT CREDENTIALS'),
   n('span','pc-license-serial','SÉRIE 0'+tier+' / 05'));
  const top=n('div','pc-license-top');
  const emblem=n('div','pc-license-emblem');emblem.append(licenseSealSvg(q.code,i));
  const identity=n('div','pc-license-identity');
  identity.append(n('small','pc-license-subtitle',subtitles[i]),n('strong','pc-license-code',q.code),n('h3','',q.title));
  top.append(identity,emblem);
  const accent=n('div','pc-license-filigree');
  accent.append(n('span',''),n('span',''),n('span',''));
  const premiumDescriptions={
   PPA:'Fundamentos de navegação visual e comando de aeronaves leves.',
   PCA:'Progressão profissional e operações comerciais de maior responsabilidade.',
   IFR:'Disciplina de instrumentos, precisão e navegação avançada.',
   MLTE:'Especialização em operações multimotor e gestão de sistemas.',
   PLA:'O mais alto marco de prestígio e experiência na carreira.'
  };
  const desc=n('p','pc-license-description',premiumDescriptions[q.code]||q.description);
  const ribbon=n('div','pc-license-stamp',q.status==='earned'?'CONQUISTADA':q.status==='available'?'ELEGÍVEL':'A CONQUISTAR');
  const footer=n('div','pc-license-foot');
  const status=n('span','pc-license-state',q.status==='earned'?'EMITIDA':q.status==='available'?'REQUISITOS ATENDIDOS':'EM PROGRESSO');
  const when=n('strong','',q.date?'EMITIDA EM '+new Date(q.date*1000).toLocaleDateString('pt-BR'):q.requirements);
  footer.append(status,when);
  card.append(metadata,top,accent,desc,ribbon,footer);
  if(q.status==='available'&&!pc.is_test){
   const button=n('button','button pc-license-claim','Conquistar certificado');
   button.onclick=()=>act('pilot_license_claim',undefined,q.code);
   card.append(button);
  }
  root.append(card);
 });
}
function graphSvg(title,data,kind){
 const card=n('section','pc-chart-card');
 const isLanding=kind==='landing',isContracts=kind==='contracts';
 const unit=isLanding?'ft/min':isContracts?'contratos':'horas';
 const highlight=isLanding?'#17d9ee':'#e3c27d';
 const heading=n('div','pc-chart-heading');
 heading.append(n('h3','',title),n('small','pc-chart-unit',unit.toUpperCase()));
 card.append(heading);
 const svg=make('svg',{viewBox:'0 0 760 315',role:'img','aria-label':title,preserveAspectRatio:'xMidYMid meet'});
 svg.append(make('title',{},title));
 const left=89,right=733,top=21,bottom=238,W=right-left,H=bottom-top;
 const rows=isLanding?(data||[]).slice(-18):(data||[]).slice(isContracts?-12:-8);
 const values=rows.map(x=>isLanding?Math.abs(Number(x.fpm)||0):Math.max(0,Number(x[1])||0));
 const highest=Math.max(1,...values);
 const roundedStep=(max)=>{
  if(isContracts)return Math.max(1,Math.ceil(max/4));
  const pow=Math.pow(10,Math.floor(Math.log10(Math.max(1,max/4))));
  const part=max/4/pow;
  return (part<=1?1:part<=2?2:part<=5?5:10)*pow;
 };
 const step=roundedStep(highest),max=4*step;
 const yValue=value=>bottom-Math.max(0,Math.min(max,value))/max*H;
 const formatValue=v=>isLanding?(v===0?'0':'-'+fmt(v,0)):isContracts?fmt(v,0):fmt(v,1);
 const labelFor=(x,i)=>isLanding?String((data||[]).length-rows.length+i+1):
  isContracts?String(x[0]).slice(5,7)+'/'+String(x[0]).slice(2,4):String(x[0]).slice(0,12);
 for(let k=0;k<=4;k++){
  const tick=k*step,y=yValue(tick);
  svg.append(make('path',{d:'M'+left+' '+y+'H'+right,stroke:'#315569',
   'stroke-width':1,'stroke-dasharray':k===0?'none':'4 7',fill:'none'}));
  svg.append(make('text',{x:left-10,y:y+4,'text-anchor':'end','font-family':'Arial,sans-serif',
   'font-size':13,fill:'#b4cfdf',stroke:'none'},formatValue(tick)));
 }
 svg.append(make('path',{d:'M'+left+' '+top+'V'+bottom+'H'+right,stroke:'#7193a4','stroke-width':1.6,fill:'none'}));
 if(rows.length){
  if(isLanding){
   const points=rows.map((x,i)=>[rows.length===1?(left+right)/2:left+(W*i)/(rows.length-1),yValue(values[i])]);
   const average=values.reduce((a,b)=>a+b,0)/values.length,meanY=yValue(average);
   svg.append(make('path',{d:'M'+left+' '+meanY+'H'+right,stroke:'#eac77c','stroke-width':2,
    'stroke-dasharray':'8 5',fill:'none',opacity:.95}));
   svg.append(make('text',{x:right-4,y:Math.max(top+13,meanY-7),'text-anchor':'end',
    'font-family':'Arial,sans-serif','font-size':12,fill:'#f5d795',stroke:'none'},
    'MÉDIA -'+fmt(average,0)+' ft/min'));
   svg.append(make('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',
    stroke:highlight,'stroke-width':3,'stroke-linejoin':'round','stroke-linecap':'round'}));
   points.forEach(([x,y],i)=>{
    const dot=make('circle',{cx:x,cy:y,r:5,fill:'#ffe4a6',stroke:'#0b3044','stroke-width':1.5});
    dot.append(make('title',{},'Pouso '+labelFor(rows[i],i)+' • '+fmt(rows[i].fpm)+' ft/min'));
    svg.append(dot);
    if(i%Math.max(1,Math.ceil(rows.length/9))===0||i===rows.length-1){
     svg.append(make('text',{x,y:bottom+20,'text-anchor':'middle','font-family':'Arial,sans-serif',
      'font-size':12,fill:'#a0bed1',stroke:'none'},labelFor(rows[i],i)));
    }
   });
   card.append(n('p','pc-chart-summary',
    'Últimos '+rows.length+' pousos • Média: -'+fmt(average,0)+' ft/min • Melhor registro: '+fmt(rows.reduce((a,b)=>Math.abs(b.fpm)<Math.abs(a.fpm)?b:a).fpm)+' ft/min'));
  }else{
   const slot=W/rows.length,barW=Math.min(68,Math.max(12,slot*.62));
   rows.forEach((item,i)=>{
    const x=left+i*slot+slot/2,barHeight=values[i]/max*H;
    const rect=make('rect',{x:x-barW/2,y:bottom-barHeight,width:barW,height:barHeight,rx:4,
     fill:i%2?'#13b9d2':'#dfbe79',stroke:'#d7e9ed','stroke-width':1.1});
    rect.append(make('title',{},String(item[0])+' • '+formatValue(values[i])+' '+unit));
    svg.append(rect);
    svg.append(make('text',{x,y:Math.max(top+12,bottom-barHeight-8),'text-anchor':'middle',
     'font-family':'Arial,sans-serif','font-size':15,'font-weight':700,fill:'#fff0c7',stroke:'none'},
     formatValue(values[i])));
    svg.append(make('text',{x,y:bottom+23,'text-anchor':'middle','font-family':'Arial,sans-serif',
     'font-size':12,fill:'#acc9d8',stroke:'none'},labelFor(item,i)));
   });
   card.append(n('p','pc-chart-summary',isContracts?
    'Total no período mostrado: '+fmt(values.reduce((a,b)=>a+b,0))+' contratos em '+rows.length+' mês(es).':
    fmt(values.reduce((a,b)=>a+b,0),1)+' horas registradas entre '+rows.length+' modelo(s) exibidos.'));
   const detail=n('div','pc-chart-breakdown');
   rows.forEach((item,i)=>{
    const line=n('div','pc-chart-breakdown-item');
    line.append(n('span','',isContracts?String(item[0]).slice(5,7)+'/'+String(item[0]).slice(0,4):String(item[0])),
     n('strong','',formatValue(values[i])+' '+unit));
    detail.append(line);
   });
   card.append(detail);
  }
 }else{
  svg.append(make('text',{x:(left+right)/2,y:136,'text-anchor':'middle','font-family':'Arial,sans-serif',
   'font-size':17,fill:'#b7d5e0',stroke:'none'},'Ainda sem registros suficientes'));
  card.append(n('p','pc-chart-summary','O gráfico será preenchido conforme os voos forem registrados.'));
 }
 const caption=n('div','pc-chart-legend');
 caption.append(n('i',isLanding?'pc-legend-line':'pc-legend-bar'),
  n('span','',isLanding?'Ciano: taxa vertical em cada toque • Dourado tracejado: média':
   isContracts?'Cada barra: contratos efetivamente concluídos no mês':
   'Cada barra: horas computadas dos voos de um modelo'));
 card.insertBefore(svg,card.querySelector('.pc-chart-summary')||null);
 card.append(caption);
 return card;
}
function graphs(pc){
 const g=el('pc-graphs');g.replaceChildren();
 g.replaceChildren(
  graphSvg('SENSIBILIDADE DE POUSO • FT/MIN',pc.graphs.landings,'landing'),
  graphSvg('CONTRATOS CONCLUÍDOS POR MÊS',pc.graphs.contracts,'contracts'),
  graphSvg('HORAS POR AERONAVE',pc.graphs.hours_by_aircraft,'hours')
 );
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
  if(['gain','loss','promotion'].includes(e.kind)){
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
  const newest=pc.timeline.find(e=>['gain','loss','promotion'].includes(e.kind));
  if(newest){
   const kind=newest.kind==='gain'&&newest.key?.startsWith('medal:')&&
    !newest.key.endsWith(':first')?'recovery':newest.kind;
   showUnlock(kind,newest.title,newest.code);
  }
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
 }else if(kind==='promotion')art.append(rankSvg({code:code||'major',title:label||'Nova patente'},'large'));
 else art.append(medalSvg(code||'veteran'));
 dialog.dataset.kind=kind;
 set('pc-unlock-kicker',kind==='loss'?'CONQUISTA PERDIDA':
  kind==='promotion'?'NOVA PATENTE':kind==='recovery'?'CONQUISTA RECUPERADA':'NOVA CONQUISTA');
 set('pc-unlock-title',label||'Conquista');
 if(!dialog.open)dialog.showModal();
 // A animação termina, mas o diálogo continua aberto até o piloto fechar.
 // Reabrir um diálogo visível não reinicia automaticamente nenhum prêmio.
 el('pc-close-unlock').focus({preventScroll:true});
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
 el('pc-unlock-dismiss').onclick=()=>el('pc-unlock').close();
 el('pc-unlock').addEventListener('click',e=>{if(e.target===el('pc-unlock'))el('pc-unlock').close();});
}
init();
window.FSCPilotCareer={render,show:()=>current&&render(current),rankSvg,medalSvg,showUnlock};
})();