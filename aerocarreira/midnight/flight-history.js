/* FlightSim v0.8.6 • Pilot Flight History.
   Read-only analytics from SQLite; only the separate annotations table is writable. */
'use strict';
window.FSCFlightHistory=(()=>{
 const el=id=>document.getElementById(id);
 const create=(tag,cls,value)=>{
  const x=document.createElement(tag);if(cls)x.className=cls;
  if(value!==undefined)x.textContent=String(value);return x;
 };
 const fmt=(n,d=0)=>Number(n).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
 const money=n=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL',maximumFractionDigits:0}).format(n);
 const date=(value,utc=false)=>{
  if(value==null)return 'Não registrado';
  return new Date(value*1000).toLocaleString('pt-BR',utc?
   {timeZone:'UTC',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}:
   {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'});
 };
 const names={particular:'Particular',regional:'Regional',freelancer:'Freelancer',
  emprego:'Empregadora',empresa:'Companhia própria',outro:'Legado / outros'};
 let current=null,lastStamp='',pageIndex=0,activeId=null;
 const all=()=>current?.flight_history?.flights||[];
 const valid=n=>typeof n==='number'&&Number.isFinite(n);
 const duration=f=>valid(f.hours)?fmt(f.hours,2)+' h':'—';
 const touchdown=f=>valid(f.touchdown_fpm)?fmt(f.touchdown_fpm)+' ft/min':'—';
 const coords=(lat,lon)=>valid(lat)&&valid(lon)?fmt(lat,4)+'°, '+fmt(lon,4)+'°':'Não registrado';
 const route=f=>f.departure_icao&&f.arrival_icao?
  f.departure_icao+' → '+f.arrival_icao:
  coords(f.from_lat,f.from_lon)+' → '+coords(f.to_lat,f.to_lon);
 function filtered(prefix,search=true){
  const period=el(prefix+'-period').value;
  const kind=el(prefix+'-kind').value;
  const plane=el(prefix+'-aircraft').value;
  const query=search&&prefix==='fh'?el('fh-search').value.toLocaleLowerCase('pt-BR').trim():'';
  const cutoff=period==='all'?null:Date.now()/1000-Number(period)*86400;
  return all().filter(f=>(cutoff===null||f.started_utc>=cutoff)&&
   (kind==='all'||f.kind===kind)&&(plane==='all'||f.aircraft===plane)&&
   (!query||[f.aircraft,f.mission_id,f.note,f.kind,route(f)].some(v=>String(v||'').toLocaleLowerCase('pt-BR').includes(query))));
 }
 function refreshAircraft(){
  const planes=[...new Set(all().map(f=>f.aircraft).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
  for(const id of ['fh-aircraft','fa-aircraft']){
   const select=el(id),previous=select.value;
   select.replaceChildren(new Option('Todas as aeronaves','all'));
   for(const plane of planes)select.append(new Option(plane,plane));
   select.value=planes.includes(previous)?previous:'all';
  }
 }
 function putStack(a,b){
  const x=create('span','fh-stack');
  x.append(create('strong','',a),create('small','',b));return x;
 }
 function renderLogbook(){
  const sorted=filtered('fh').sort((a,b)=>el('fh-sort').value==='old'?
   a.started_utc-b.started_utc:a.started_utc-b.started_utc);
  const pageSize=12,pages=Math.max(1,Math.ceil(sorted.length/pageSize));
  pageIndex=Math.min(Math.max(0,pageIndex),pages-1);
  const list=el('fh-list');list.replaceChildren();
  el('fh-total').textContent=fmt(all().length);
  el('fh-count').textContent=fmt(sorted.length)+' voo(s) nos filtros • '+fmt(all().length)+' na carreira';
  el('fh-page-number').textContent=(pageIndex+1)+' / '+pages;
  el('fh-prev').disabled=pageIndex===0;
  el('fh-next').disabled=pageIndex>=pages-1;
  if(!sorted.length){
   list.append(create('div','fh-empty',all().length?
    'Nenhum voo corresponde aos filtros.':'Nenhum voo registrado ainda. O Logbook será preenchido a cada voo concluído.'));
   return;
  }
  for(const f of sorted.slice(pageIndex*pageSize,(pageIndex+1)*pageSize)){
   const row=create('button','fh-entry');
   row.type='button';row.setAttribute('role','listitem');
   row.title='Abrir ficha do voo #'+f.id;
   row.append(putStack(date(f.started_utc),'Voo #'+f.id),
    putStack(f.aircraft||'Modelo não registrado',f.mission_id||'Sem contrato'),
    create('span','fh-accent',names[f.kind]||f.kind),
    create('span','',duration(f)),
    create('span','',touchdown(f)),
    putStack(valid(f.xp)?fmt(f.xp)+' XP':'XP não registrado',
      f.kind==='empresa'?(valid(f.business_net)?'Empresa: '+money(f.business_net):'Caixa da empresa: —'):
       (valid(f.personal_net)?'Pessoal: '+money(f.personal_net):'Sem lançamento associado')));
   row.onclick=()=>openDetail(f.id);
   list.append(row);
  }
 }
 function detailItem(label,value){
  const item=create('div','fh-detail-item');
  item.append(create('small','',label),create('strong','',value));return item;
 }
 function openDetail(id){
  const f=all().find(x=>x.id===id);if(!f)return;
  activeId=f.id;el('fh-detail-title').textContent='VOO #'+f.id+' • '+(f.aircraft||'Aeronave não registrada');
  const host=el('fh-detail-data');host.replaceChildren(
   detailItem('INÍCIO • HORA LOCAL',date(f.started_utc)),
   detailItem('INÍCIO • UTC',date(f.started_utc,true)),
   detailItem('FIM • UTC',date(f.ended_utc,true)),
   detailItem('DURAÇÃO',duration(f)),
   detailItem('MODALIDADE',names[f.kind]||f.kind),
   detailItem('MODELO',f.aircraft||'Não registrado'),
   detailItem('ORIGEM • COORDENADAS',coords(f.from_lat,f.from_lon)),
   detailItem('DESTINO • COORDENADAS',coords(f.to_lat,f.to_lon)),
   detailItem('DISTÂNCIA DIRETA ESTIMADA',valid(f.direct_nm)?fmt(f.direct_nm,1)+' NM':'Indisponível'),
   detailItem('TAXA DE POUSO',touchdown(f)),
   detailItem('ALERTAS DE ESTOL',valid(f.stalls)?fmt(f.stalls):'Não registrado'),
   detailItem('CONTRATO',f.mission_id||'Sem contrato'),
   detailItem('RECOMPENSA SALVA',valid(f.reward_recorded)?money(f.reward_recorded):'Não registrado'),
   detailItem('XP DO VOO',valid(f.xp)?fmt(f.xp)+' XP':'Não registrado'),
   detailItem('LANÇAMENTOS PESSOAIS',valid(f.personal_net)?money(f.personal_net):'Sem lançamento'),
   detailItem('RESULTADO EMPRESARIAL',valid(f.business_net)?money(f.business_net):'Sem lançamento')
  );
  el('fh-note').value=f.note||'';
  el('fh-note-hint').textContent='Somente a anotação é editável. Os dados do voo são imutáveis.';
  if(!el('fh-detail').open)el('fh-detail').showModal();
 }
 async function saveNote(){
  const f=all().find(x=>x.id===activeId);if(!f)return;
  const note=el('fh-note').value;
  const button=el('fh-note-save');button.disabled=true;
  try{
   const r=await fetch('/command',{method:'POST',headers:{
    'Content-Type':'application/json','X-Flight-Token':token},
    body:JSON.stringify({action:'flight_note',payload:{flight_id:f.id,note}})});
   if(!r.ok)throw Error('HTTP '+r.status);
   el('fh-note-hint').textContent='Anotação recebida e aguardando confirmação no SQLite...';
  }catch(e){el('fh-note-hint').textContent='Não foi possível salvar: '+e.message;}
  finally{button.disabled=false;}
 }
 function csvField(v){
  let text=v==null?'':String(v);
  if(/^[=+@\-]/.test(text)&&!/^-[0-9]+([.,][0-9]+)?$/.test(text))text="'"+text;
  return '"'+text.replaceAll('"','""')+'"';
 }
 function exportCsv(){
  const rows=filtered('fh').sort((a,b)=>a.started_utc-b.started_utc);
  const head=['ID','Início UTC','Fim UTC','Aeronave','Modalidade','Contrato',
   'Latitude origem','Longitude origem','Latitude destino','Longitude destino',
   'Duração (h)','Distância direta estimada (NM)','Pouso (ft/min)','Estol',
   'XP do voo','Resultado pessoal (R$)','Resultado empresarial (R$)','Anotação'];
  const cols=f=>[f.id,new Date(f.started_utc*1000).toISOString(),new Date(f.ended_utc*1000).toISOString(),
   f.aircraft,f.kind,f.mission_id,f.from_lat,f.from_lon,f.to_lat,f.to_lon,
   f.hours,f.direct_nm,f.touchdown_fpm,f.stalls,f.xp,f.personal_net,f.business_net,f.note];
  const content='\ufeff'+[head,...rows.map(cols)].map(line=>line.map(csvField).join(';')).join('\r\n');
  const url=URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='FlightSim-Logbook-'+
   new Date().toISOString().slice(0,10)+'.csv';document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),3000);
 }
 const metric=(label,value,detail,primary=false)=>{
  const card=create('article','fa-metric'+(primary?' primary':''));card.append(
   create('small','',label),create('strong','',value),create('em','',detail));return card;
 };
 function addBars(target,values,unit,limit=7){
  const host=el(target);host.replaceChildren();
  const entries=Object.entries(values).sort((a,b)=>b[1]-a[1]).slice(0,limit);
  if(!entries.length){host.append(create('div','fh-empty','Não há dados registrados para este filtro.'));return;}
  const max=Math.max(1,...entries.map(x=>x[1]));
  for(const [name,value] of entries){
   const row=create('div','fa-bar');
   const header=create('div','fa-bar-head');header.append(create('span','',name),
    create('strong','',fmt(value,unit===' h'?1:0)+unit));
   const track=create('div','fa-bar-track'),fill=create('i');
   fill.style.width=(value/max*100).toFixed(2)+'%';track.append(fill);
   row.append(header,track);host.append(row);
  }
 }
 function monthlyChart(data){
  const host=el('fa-month-chart');host.replaceChildren();
  const months=new Map();
  for(const f of data){
   const d=new Date(f.started_utc*1000),key=d.toISOString().slice(0,7);
   const item=months.get(key)||{flights:0,hours:0};
   item.flights++;item.hours+=f.hours||0;months.set(key,item);
  }
  const entries=[...months.entries()].sort((a,b)=>a[0].localeCompare(b[0])).slice(-12);
  if(!entries.length){host.append(create('div','fh-empty','Sem voos neste período.'));return;}
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 660 260');svg.setAttribute('role','img');
  svg.setAttribute('aria-label','Gráfico de voos e horas mensais');
  const element=(tag,props,value)=>{
   const x=document.createElementNS(ns,tag);
   for(const [k,v] of Object.entries(props))x.setAttribute(k,String(v));
   if(value!==undefined)x.textContent=value;svg.append(x);return x;
  };
  const maxFlights=Math.max(1,...entries.map(x=>x[1].flights)),maxHours=Math.max(.1,...entries.map(x=>x[1].hours));
  for(let j=0;j<=4;j++){
   const y=215-j*45;
   element('line',{x1:42,y1:y,x2:650,y2:y,stroke:'#2d5265','stroke-width':1});
   element('text',{x:34,y:y+4,'text-anchor':'end','font-size':12},fmt(maxFlights*j/4));
  }
  const step=608/entries.length,barWidth=Math.min(44,step*.52);
  const curve=[];
  entries.forEach(([month,v],i)=>{
   const x=42+(i+.5)*step,barHeight=180*v.flights/maxFlights;
   element('rect',{x:x-barWidth/2,y:215-barHeight,width:barWidth,height:barHeight,rx:5,
    fill:'#08c6df','fill-opacity':.83});
   element('text',{x,y:205-barHeight,'font-size':12,'text-anchor':'middle'},String(v.flights));
   element('text',{x,y:239,'font-size':11,'text-anchor':'middle'},month.slice(5)+'/'+month.slice(2,4));
   curve.push([x,215-180*v.hours/maxHours]);
  });
  element('polyline',{points:curve.map(p=>p.join(',')).join(' '),stroke:'#f4c46a',
   'stroke-width':3,fill:'none','stroke-linecap':'round','stroke-linejoin':'round'});
  for(const [x,y] of curve)element('circle',{cx:x,cy:y,r:4,fill:'#ffd385',stroke:'#3b2f0c','stroke-width':1});
  element('text',{x:50,y:18,'font-size':12,fill:'#c7ddef'},'Barras: voos • Linha dourada: horas (escala própria)');
  host.append(svg);
 }
 function renderAnalytics(){
  const items=filtered('fa',false),period=el('fa-period').value,kindFilter=el('fa-kind').value,
    aircraftFilter=el('fa-aircraft').value;
  const cutoff=period==='all'?null:Date.now()/1000-Number(period)*86400;
  const includeDate=e=>cutoff===null||e.at_utc>=cutoff;
  const keys=new Set(items.map(f=>f.flight_key).filter(Boolean));
  // Uma transação sem flight_key só pode entrar em relatório agregado de todas
  // as aeronaves; nunca a atribuímos arbitrariamente a um avião ou contrato.
  const matchFlight=e=>[...keys].some(key=>e.event_key?.startsWith(key+':'));
  const globalView=kindFilter==='all'&&aircraftFilter==='all';
  const personalEvents=(current?.flight_history?.finance_events||[]).filter(includeDate);
  const businessEvents=(current?.flight_history?.business_events||[]).filter(includeDate);
  const salaryEligible=aircraftFilter==='all'&&['all','emprego'].includes(kindFilter);
  const salaries=salaryEligible?personalEvents.filter(e=>e.kind==='salario')
    .reduce((a,e)=>a+e.amount,0):null;
  const operational=new Set(['combustivel','taxa_aeroporto','taxa_simulada','seguro',
    'abastecimento','manutencao','aluguel','penalidade_combustivel']);
  const labels={combustivel:'Combustível em voo',taxa_aeroporto:'Taxa de aeroporto',
    taxa_simulada:'Imposto opcional',seguro:'Seguro de aeronave',abastecimento:'Abastecimento',
    manutencao:'Manutenção',aluguel:'Aluguel',penalidade_combustivel:'Penalidade de combustível'};
  const expenses={};
  for(const [source,events] of [['Pessoal',personalEvents],['Empresa',businessEvents]]){
   for(const e of events){
    if(e.amount>=0||!operational.has(e.kind)||(!globalView&&!matchFlight(e)))continue;
    const label=source+' · '+(labels[e.kind]||e.kind);
    expenses[label]=(expenses[label]||0)-e.amount;
   }
  }
  const expenseTotal=Object.values(expenses).reduce((a,b)=>a+b,0);
  const hours=items.reduce((n,f)=>n+(f.hours||0),0);
  const landings=items.filter(f=>valid(f.touchdown_fpm));
  const xp=items.reduce((n,f)=>n+(f.xp||0),0);
  const personal=items.reduce((n,f)=>n+(f.personal_net||0),0);
  const business=items.reduce((n,f)=>n+(f.business_net||0),0);
  const host=el('fa-metrics');host.replaceChildren(
   metric('VOOS REGISTRADOS',fmt(items.length),'Operações no filtro',true),
   metric('HORAS DE VOO',fmt(hours,1)+' h','Tempo acumulado'),
   metric('MÉDIA DOS POUSOS',landings.length?
    fmt(landings.reduce((n,f)=>n+f.touchdown_fpm,0)/landings.length)+' ft/min':'—',
    fmt(landings.length)+' pousos com leitura'),
   metric('XP DOS VOOS',fmt(xp),'XP atrelado a voos, não folha'),
   metric('RESULTADO PESSOAL EM VOOS',money(personal),'Lançamentos financeiros do voo'),
   metric('RESULTADO EMPRESARIAL',money(business),'Separado do caixa pessoal'),
   metric('SALÁRIOS LIQUIDADOS',salaries===null?'—':money(salaries),
    salaries===null?'Não atribuível à aeronave':'Folhas realmente pagas no período'),
   metric('DESPESAS REGISTRADAS',money(expenseTotal),
    globalView?'Todos os custos operacionais no período':'Somente custos vinculados aos voos filtrados')
  );
  const aircraft={},kind={},landing={Suave:0,Moderado:0,Forte:0},models={};
  for(const f of items){
   const name=f.aircraft||'Modelo não registrado';
   aircraft[name]=(aircraft[name]||0)+(f.hours||0);
   kind[names[f.kind]||'Outros']=(kind[names[f.kind]||'Outros']||0)+1;
   const m=models[name]||(models[name]={flights:0,hours:0,landing:[],personal:0,business:0});
   m.flights++;m.hours+=f.hours||0;m.personal+=f.personal_net||0;m.business+=f.business_net||0;
   if(valid(f.touchdown_fpm)){
    m.landing.push(f.touchdown_fpm);
    const descent=Math.abs(f.touchdown_fpm);
    if(descent<150)landing.Suave++;
    else if(descent<=400)landing.Moderado++;
    else landing.Forte++;
   }
  }
  monthlyChart(items);
  addBars('fa-aircraft-chart',aircraft,' h');
  addBars('fa-kind-chart',kind,' voo(s)');
  if(!landings.length)el('fa-landing-chart').replaceChildren(create('div','fh-empty','Nenhum pouso com taxa registrada.'));
  else addBars('fa-landing-chart',landing,' pouso(s)');
  addBars('fa-cost-chart',expenses,' R$');
  const table=el('fa-model-comparison');table.replaceChildren();
  const entries=Object.entries(models).sort((a,b)=>b[1].hours-a[1].hours);
  if(!entries.length)table.append(create('div','fh-empty','Nenhuma aeronave pilotada neste período.'));
  else{
   for(const [name,m] of entries){
    const card=create('div','fa-compare-row');
    const data=create('div','fa-compare-meta');
    data.append(create('strong','',name),create('small','',fmt(m.flights)+' voos • '+
      fmt(m.hours,1)+' h • pouso médio '+(m.landing.length?
      fmt(m.landing.reduce((a,b)=>a+b,0)/m.landing.length)+' ft/min':'—')));
    card.append(data,create('span','',
      'Pessoal '+money(m.personal)+' • Empresa '+money(m.business)));
    table.append(card);
   }
  }
 }
 function render(s,force=false){
  current=s;
  const history=s?.flight_history||{};
  const stamp=JSON.stringify([history.count,history.notes_revision,
   history.flights?.[0]?.id,history.flights?.[0]?.ended_utc]);
  if(stamp!==lastStamp){
   lastStamp=stamp;
   refreshAircraft();
   force=true;
  }
  if(!force)return;
  if(document.querySelector('.workspace')?.dataset.view==='history')renderLogbook();
  if(document.querySelector('.workspace')?.dataset.view==='reports')renderAnalytics();
 }
 function show(){
  if(!current)return;
  if(document.querySelector('.workspace')?.dataset.view==='history')renderLogbook();
  if(document.querySelector('.workspace')?.dataset.view==='reports')renderAnalytics();
 }
 for(const page of ['fh','fa'])
  for(const kind of ['period','kind','aircraft'])
   el(page+'-'+kind).addEventListener('change',()=>{
    if(page==='fh'){pageIndex=0;renderLogbook();}else renderAnalytics();
   });
 el('fh-search').addEventListener('input',()=>{pageIndex=0;renderLogbook();});
 el('fh-sort').addEventListener('change',()=>{pageIndex=0;renderLogbook();});
 el('fh-prev').onclick=()=>{pageIndex--;renderLogbook();};
 el('fh-next').onclick=()=>{pageIndex++;renderLogbook();};
 el('fh-export').onclick=exportCsv;
 el('fh-detail-close').onclick=()=>el('fh-detail').close();
 el('fh-note-save').onclick=saveNote;
 return {render,show,filtered,openDetail};
})();
