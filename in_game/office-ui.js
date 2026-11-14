/* FlightSim InGame v0.9.2 — Midnight Operations.
 * Coherent-compatible UI. All state and authority live in the existing Python
 * companion. DOM text is never trusted as a price or flight clearance.
 */
(function(){
'use strict';
var B=window.FlightSimOfficeBridge;
if(!B)return;
var E=B.element,money=B.money,val=B.value,ask=B.askAction,notice=B.feedback;
var latest={},office={},lastRevision=-1,tab='new',selectedFlight=null;
var planDirty=false,planLoaded=false,waypoints=[],noteDirty=false,loanOpen=false;
var checkKeys=['runway_checked','route_checked','fuel_checked','payload_checked'];
function put(id,text){var e=E(id);if(e)e.textContent=text;}
function fresh(id){var e=E(id);if(!e)return null;while(e.firstChild)e.removeChild(e.firstChild);return e;}
function node(tag,cls,text){
 var e=document.createElement(tag);
 if(cls)e.className=cls;
 if(text!==undefined&&text!==null)e.textContent=String(text);
 return e;
}
function add(parent,child){parent.appendChild(child);return child;}
function placeholder(host,message){if(host)add(host,node('div','office-placeholder',message));}
function ground(){
 return !!(latest.status==='connected'&&latest.telemetry&&
          latest.telemetry.on_ground===true&&latest.mode==='MSFS');
}
function canOperate(){return ground()&&E('confirm-yes')!==null;}
function safeNum(x){return typeof x==='number'&&isFinite(x)?x:0;}
function fmt(x,d){return typeof x==='number'&&isFinite(x)?x.toFixed(d||0):'—';}
function date(x){
 if(typeof x!=='number'||!isFinite(x))return '—';
 return new Date(x*1000).toLocaleDateString('pt-BR');
}
function metric(host,label,valueText,accent){
 var e=node('div','office-metric');
 add(e,node('small','',label));add(e,node('strong',accent?'accent':'',valueText));
 add(host,e);return e;
}
function entry(host,title,detail,extra){
 var e=node('div','office-entry');
 add(e,node('h4','',title));
 if(detail)add(e,node('small','',detail));
 if(extra)add(e,node('small','',extra));
 add(host,e);return e;
}
function actions(host){
 return add(host,node('div','op-actions'));
}
function button(host,text,fn,disabled,warning){
 var b=node('button',warning?'warning':'',text);
 b.type='button';b.disabled=!!disabled;b.addEventListener('click',fn);add(host,b);return b;
}
function requireGround(){
 if(!ground()){notice('Ação requer MSFS conectado e aeronave em solo.',true);return false;}
 return true;
}
function confirmAction(action,value,title,explanation){
 if(!requireGround())return;
 ask(action,value,title,explanation);
}
function picture(code,parent){
 var media={c172:'c172.jpg',g58:'g58.jpg',kingair:'kingair.jpg',cj4:'cj4.jpg'};
 var holder=add(parent,node('div','hangar-picture'));
 if(media[code]){
  var img=node('img');img.src='/media/'+media[code];img.alt='Aeronave '+code.toUpperCase();
  img.onerror=function(){img.style.display='none';add(holder,node('strong','hangar-silhouette',String(code||'FS').toUpperCase()));};
  add(holder,img);
 }else add(holder,node('strong','hangar-silhouette',(code||'FLIGHTSIM').toUpperCase()));
 return holder;
}
function renderPlanning(o){
 var p=o.planning||{},d=p.draft||{},route=p.route||{},ready=!!p.ready;
 put('planning-status',ready?'Catálogo MSFS confirmado':'Catálogo indisponível');
 if(!planLoaded||(!planDirty&&JSON.stringify(d)!==window.__fsIngamePlanLoaded)){
  E('plan-mode').value=d.mode||'free';
  E('plan-origin').value=d.origin||'';
  E('plan-destination').value=d.destination||'';
  E('plan-altitude').value=d.altitude_ft||2500;
  waypoints=Array.isArray(d.waypoints)?d.waypoints.slice(0,8):[];
  checkKeys.forEach(function(k){var cb=document.querySelector('[data-plan-check="'+k+'"]');if(cb)cb.checked=!!(d.checks&&d.checks[k]);});
  planLoaded=true;window.__fsIngamePlanLoaded=JSON.stringify(d);
  drawWaypoints();
 }
 var host=fresh('plan-metrics');
 metric(host,'DISTÂNCIA',route.distance_nm!==undefined?fmt(route.distance_nm,1)+' NM':'—');
 metric(host,'TEMPO PREVISTO',route.minutes!==undefined?fmt(route.minutes)+' min':'—');
 metric(host,'RESERVA ESTIMADA',route.fuel_required_gal!==undefined?fmt(route.fuel_required_gal,1)+' gal':'—');
 metric(host,'PESO / MTOW',route.weight_lbs!==undefined?fmt(route.weight_lbs)+' / '+fmt(route.mtow_lbs)+' lb':'—');
 var dispatch=p.dispatch||{};
 put('plan-dispatch-state',dispatch.message||'Rota: '+(dispatch.route||'não enviada')+' • Carga: '+(dispatch.payload||'pendente'));
 E('plan-save').disabled=!ground()||!ready;
 E('plan-clear').disabled=!ground();
 E('plan-send').disabled=!ground()||!ready||!route.origin;
 E('plan-export').disabled=!ready||!route.origin;
}
function drawWaypoints(){
 var host=fresh('waypoint-list');if(!host)return;
 if(!waypoints.length)placeholder(host,'Nenhum ponto intermediário.');
 waypoints.forEach(function(w,index){
  var row=entry(host,w.label,fmt(w.lat,5)+', '+fmt(w.lon,5));
  button(actions(row),'Editar ponto',function(){
   E('wp-label').value=w.label;E('wp-lat').value=w.lat;E('wp-lon').value=w.lon;
   waypoints.splice(index,1);planDirty=true;drawWaypoints();
   notice('Atualize os campos e clique Adicionar ponto.',false);
  },false);
  button(actions(row),'Remover ponto',function(){
   waypoints.splice(index,1);planDirty=true;drawWaypoints();
  },false,true);
 });
}
function planPayload(){
 var checks={};checkKeys.forEach(function(k){var el=document.querySelector('[data-plan-check="'+k+'"]');checks[k]=!!(el&&el.checked);});
 return {mode:E('plan-mode').value,origin:E('plan-origin').value.trim().toUpperCase(),
  destination:E('plan-destination').value.trim().toUpperCase(),
  altitude_ft:Number(E('plan-altitude').value),waypoints:waypoints.slice(),checks:checks};
}
function hookPlanning(){
 ['plan-mode','plan-origin','plan-destination','plan-altitude'].forEach(function(id){
  E(id).addEventListener('input',function(){planDirty=true;});
 });
 Array.prototype.forEach.call(document.querySelectorAll('[data-plan-check]'),function(c){
  c.addEventListener('change',function(){planDirty=true;});
 });
 E('wp-add').addEventListener('click',function(){
  var name=E('wp-label').value.trim().toUpperCase(),a=Number(E('wp-lat').value),b=Number(E('wp-lon').value);
  if(!/^[A-Z0-9_-]{1,12}$/.test(name)||!E('wp-lat').value||!E('wp-lon').value||
     !isFinite(a)||!isFinite(b)||Math.abs(a)>90||Math.abs(b)>180)
   return notice('Informe nome e coordenadas válidas.',true);
  if(waypoints.length>=8)return notice('Limite de oito waypoints.',true);
  if(waypoints.some(function(w){return w.label===name;}))return notice('Waypoint já utilizado.',true);
  waypoints.push({label:name,lat:a,lon:b});planDirty=true;drawWaypoints();
  E('wp-label').value='';E('wp-lat').value='';E('wp-lon').value='';
 });
 E('plan-save').addEventListener('click',function(){
  var p=planPayload();
  if(!/^[A-Z0-9]{4}$/.test(p.origin)||!/^[A-Z0-9]{4}$/.test(p.destination)||p.origin===p.destination||
     !Number.isInteger(p.altitude_ft)||p.altitude_ft<500||p.altitude_ft>45000)
   return notice('Confira ICAOs distintos e altitude de 500 a 45000 pés.',true);
  confirmAction('plan_save',p,'Salvar planejamento?',
   'O FlightSim vai validar aeroportos e waypoints na sessão MSFS antes de gravar.');
 });
 E('plan-export').addEventListener('click',function(){
  ask('plan_export',null,'Exportar plano .PLN?','O arquivo será salvo na pasta de planos da carreira.');
 });
 E('plan-send').addEventListener('click',function(){
  confirmAction('plan_send',null,'Enviar plano ao simulador?',
   'O motor solicitará o carregamento via SimConnect; aguarde confirmação e confira o mapa/ATC no MSFS.');
 });
 E('plan-clear').addEventListener('click',function(){
  confirmAction('plan_clear',null,'Apagar planejamento salvo?',
   'O contrato e a carreira não serão apagados; apenas o rascunho de voo será limpo.');
 });
}
function renderHangar(o){
 var f=o.fleet||{},m=f.market||{},host=fresh('hangar-owned'),market=fresh('hangar-market');
 var allowed=ground()&&m.ready;
 put('hangar-status',(f.owned||[]).length+' aeronave(s) • '+(m.airport||'sem aeroporto'));
 put('hangar-market-reason',m.ready?'Transações no aeroporto '+m.airport+' • confirmadas pelo motor':m.reason||'Mercado indisponível');
 if(!(f.owned||[]).length)placeholder(host,'Nenhuma aeronave no hangar.');
 (f.owned||[]).forEach(function(x){
  var card=node('article','hangar-card');picture(x.code,card);
  var info=add(card,node('div','hangar-info'));
  add(info,node('h4','',x.title||x.code));
  add(info,node('small','',(x.airport||'—')+' • '+fmt(x.condition,0)+'% de conservação • '+fmt(x.hours,1)+' h'));
  add(info,node('small','',x.kind==='starter'?'Aeronave inicial':x.kind==='rented'?'Alugada':'Aeronave do piloto'));
  if(x.is_active)add(info,node('span','office-tag','SELECIONADA'));
  var bar=actions(info);
  button(bar,'Selecionar',function(){
   confirmAction('fleet_select',x.ref,'Selecionar aeronave?',x.title+' • aeroporto '+x.airport+
     '. A seleção na carreira não troca automaticamente a aeronave no MSFS.');
  },!ground()||!!x.is_active);
  button(bar,'Revisão',function(){
   confirmAction('fleet_service',x.ref,'Revisar aeronave?',x.title+
     ' • A revisão tem custo calculado pelo motor e exige que a aeronave esteja no aeroporto correto.');
  },!allowed||!!latest.mission||x.condition>=99.9);
  button(bar,x.insured?'Desativar seguro':'Ativar seguro',function(){
   confirmAction('fleet_insurance',x.ref+'|'+(x.insured?'0':'1'),
    x.insured?'Desativar apólice?':'Contratar apólice?',
    x.title+' • '+(x.insured?'Remover cobertura virtual.':'Cobertura e custo serão calculados no motor.'));
  },!allowed||!!latest.mission||x.kind==='rented');
  add(host,card);
 });
 var rows=[];
 if(tab==='new')rows=(m.models||[]).map(function(x){return {kind:'new',ref:x.code,code:x.code,title:x.title,price:x.price,detail:'Novo • '+fmt(x.cruise_kts)+' kt de cruzeiro'};});
 if(tab==='used')rows=(m.used||[]).map(function(x){return {kind:'used',ref:x.id,code:x.code,title:x.title,price:x.price,detail:'Usado • '+fmt(x.condition)+'% • '+fmt(x.hours,1)+' h',sold:x.sold};});
 if(tab==='rent')rows=(m.models||[]).map(function(x){return {kind:'rent',ref:x.code,code:x.code,title:x.title,price:x.rental_prices&&x.rental_prices['24'],detail:'Aluguel inicial de 24 h',rates:x.rental_prices};});
 if(tab==='sell')rows=(m.owned||[]).filter(function(x){return x.saleable;}).map(function(x){return {kind:'sell',ref:x.ref,title:x.title,price:x.resale_price,detail:'Revenda • '+x.airport+' • '+fmt(x.condition)+'%'};});
 if(!rows.length)placeholder(market,'Nenhuma oferta disponível nesta categoria.');
 rows.slice(0,25).forEach(function(x){
  var card=node('article','hangar-card');picture(x.code,card);
  var body=add(card,node('div','hangar-info'));
  add(body,node('h4','',x.title));add(body,node('small','',x.detail));
  add(body,node('span','hangar-price',money(x.price)));
  var ba=actions(body);
  var names={new:'Comprar',used:'Comprar usado',rent:'Alugar',sell:'Vender'};
  var code={new:'fleet_buy_new',used:'fleet_buy_used',rent:'fleet_rent',sell:'fleet_sell'};
  var value=x.ref;
  if(x.kind==='rent'){
   var select=node('select','btn');
   [24,48,72,168].forEach(function(h){var option=node('option','',h+' horas • '+money(x.rates&&x.rates[String(h)]));option.value=String(h);add(select,option);});
   add(body,select);
  }
  button(ba,names[x.kind],function(){
   var v=value,desc=x.title+' • '+money(x.price);
   if(x.kind==='rent'){
    var h=select.value;v+='|'+h;
    desc=x.title+' por '+h+' horas • '+money(x.rates&&x.rates[h]);
   }
   confirmAction(code[x.kind],v,names[x.kind]+' '+x.title+'?',desc+
     '. O motor confirma saldo, localização e requisitos antes de efetuar.');
  },!allowed||!!latest.mission||!!x.sold);
  add(market,card);
 });
}
function renderAirlines(o){
 var a=o.airlines||{},f=o.fleet||{},host=fresh('airline-metrics');
 var mode=a.mode||'autonomo',employment=a.employment||{},business=a.business||{};
 put('airline-status',mode==='empregado'?'PILOTO CONTRATADO':mode==='empresario'?'EMPRESÁRIO':'PILOTO AUTÔNOMO');
 metric(host,'SITUAÇÃO',mode==='empregado'?'Empregado':mode==='empresario'?'Empresa própria':'Autônomo');
 metric(host,'EMPREGADORA',employment.employer||'—');
 metric(host,'SALÁRIO SEMANAL',employment.progress?money(employment.progress.salary):'—');
 metric(host,'CAIXA EMPRESARIAL',business.balance!==undefined?money(business.balance):'—');
 E('airline-review').disabled=!ground()||!!latest.mission;
 E('airline-resign').disabled=!ground()||!!latest.mission||mode!=='empregado';
 E('airline-found').disabled=!ground()||!!latest.mission||mode!=='autonomo';
 var jobs=fresh('airline-vacancies');
 if(mode==='empregado'){
  var p=employment.progress||{},req=p.required||{};
  entry(jobs,'Meta semanal',fmt(p.flights)+' / '+fmt(req.flights)+' voos • '+
   fmt(p.hours,1)+' / '+fmt(req.hours,1)+' h',
   'Salário condicionado ao cumprimento da meta semanal.');
 }
 if(mode==='autonomo'){
  if(!(a.vacancies||[]).length)placeholder(jobs,'Nenhuma vaga disponível no período.');
  (a.vacancies||[]).forEach(function(v){
   var row=entry(jobs,v.name||v.company,money(v.salary)+' por semana • nível '+fmt(v.min_level)+' • '+fmt(v.min_hours,1)+' h',
    v.allowed?'Elegível para candidatura':v.reason||'Requisitos insuficientes');
   var bar=actions(row);
   var s=node('select','btn');
   [0,10,20].forEach(function(t){var op=node('option','',t+'% de compromisso extra');op.value=String(t);add(s,op);});
   add(bar,s);
   button(bar,'Candidatar-se',function(){
    confirmAction('airline_apply',v.id+'|'+s.value,'Enviar candidatura?',
     v.name+' • compromisso semanal +'+s.value+'% • salário-base '+money(v.salary)+'.');
   },!ground()||!!latest.mission||!v.allowed);
  });
 }else if(mode==='empresario')placeholder(jobs,'Sua companhia está ativa. Consulte os contratos empresariais no Mercado.');
 var contracts=fresh('airline-contracts');
 var options=(mode==='empregado'?(a.employer_offers||[]):mode==='empresario'?(a.corporate_offers||[]):[]);
 if(!options.length)placeholder(contracts,'Nenhum contrato da empresa disponível para este período.');
 options.slice(0,18).forEach(function(x){
  var row=entry(contracts,x.title||x.origin+' → '+x.destination,
   (x.origin||'—')+' → '+(x.destination||'—')+' • '+money(x.reward));
  button(actions(row),'Aceitar trecho',function(){
   confirmAction('offer_accept',x.id,'Aceitar trecho da companhia?',
    (x.origin||'—')+' → '+(x.destination||'—')+'. O motor revalida habilitação, modelo e aeroporto.');
  },!ground()||!!latest.mission);
 });
 var rated=fresh('airline-ratings'),types=a.type_ratings||[];
 if(!types.length)placeholder(rated,'Habilitações ainda não disponíveis.');
 types.slice(0,25).forEach(function(t){
  var row=entry(rated,t.title||t.code,t.rated?'Habilitado':fmt(t.flights)+' / '+fmt(t.required)+' voos de treino');
  add(row,node('span',t.rated?'office-tag':'office-tag warn',t.installed?'Instalado no MSFS':'Instalação não confirmada'));
 });
 var own=fresh('airline-business');
 if(mode==='empresario'){
  entry(own,business.owner_company||business.name||'Minha companhia',
   'Saldo empresarial: '+money(business.balance)+' • '+fmt(business.reputation)+' reputação',
   fmt((business.planes||[]).length)+' aeronave(s) na empresa');
  var codes={};(business.planes||[]).forEach(function(p){codes[p.code]=true;});
  (f.market&&f.market.models||[]).slice(0,12).forEach(function(p){
   var row=entry(own,p.title||p.code,'Aeronave empresarial • preço validado pelo motor');
   button(actions(row),'Comprar para companhia',function(){
    confirmAction('airline_buy_plane',p.code,'Adquirir aeronave empresarial?',p.title+
     ' • investimento e elegibilidade calculados no motor.');
   },!ground()||!!latest.mission);
  });
 }else placeholder(own,'A fundação exige os requisitos de carreira e aporte inicial de '+money(a.investment)+'.');
}
function renderPilot(o){
 var p=o.pilot||{},host=fresh('pilot-office');
 if(!host)return;
 var banner=node('div','office-banner full'),top=node('div');
 add(top,node('span','eyebrow','PILOT CAREER'));
 add(top,node('h2','',p.name||'Piloto não cadastrado'));
 add(top,node('p','',String(p.callsign||'Sem indicativo')+' • '+String(p.home_icao||'Sem base')+
  ' • '+(p.rank&&p.rank.title||'Sem patente')));
 add(banner,top);add(banner,node('span','office-status','NÍVEL '+fmt(p.level)));
 add(host,banner);
 var m=add(host,node('div','office-metrics full'));
 metric(m,'EXPERIÊNCIA',fmt(p.xp)+' XP',true);
 metric(m,'REPUTAÇÃO',fmt(p.reputation)+'%',true);
 metric(m,'HORAS DE VOO',fmt(p.hours,1)+' h');
 metric(m,'CONTRATOS',fmt(p.contracts));
 var licenses=add(host,node('div','office-panel half'));add(licenses,node('h3','','Licenças e certificados'));
 var ls=add(licenses,node('div','office-stack'));
 (p.licenses||[]).forEach(function(q){
  var row=entry(ls,q.title||q.code,q.status==='earned'?'CONQUISTADA':q.status==='available'?'REQUISITOS ATENDIDOS':q.requirements||'Bloqueada');
  if(q.status==='available')button(actions(row),'Reivindicar licença',function(){
    confirmAction('pilot_license_claim',q.code,'Solicitar licença '+q.code+'?',
     'Todos os requisitos serão reavaliados no motor antes do registro.');
  },!ground());
 });
 if(!(p.licenses||[]).length)placeholder(ls,'Nenhum certificado disponível.');
 var medals=add(host,node('div','office-panel half'));add(medals,node('h3','','Conquistas da carreira'));
 var ms=add(medals,node('div','office-stack'));
 (p.medals||[]).forEach(function(q){
  var row=entry(ms,q.title||q.code,q.description||'');
  add(row,node('span',q.status==='earned'?'office-tag':'office-tag warn',
   q.status==='earned'?'CONQUISTADA':'BLOQUEADA'));
 });
 if(!(p.medals||[]).length)placeholder(ms,'Nenhuma conquista registrada.');
}
function renderLogbook(o){
 var data=o.logbook||{},flights=data.flights||[],list=fresh('logbook-list');
 put('logbook-total',fmt(data.count)+' voos');
 var m=fresh('logbook-metrics');
 metric(m,'VOOS REGISTRADOS',fmt(data.count));
 metric(m,'ÚLTIMO POUSO',flights.length&&typeof flights[0].touchdown_fpm==='number'?
  fmt(flights[0].touchdown_fpm)+' ft/min':'—');
 metric(m,'HORAS NA CARREIRA',fmt(o.pilot&&o.pilot.hours,1)+' h');
 metric(m,'CONTRATOS',fmt(o.pilot&&o.pilot.contracts));
 if(!flights.length)placeholder(list,'Nenhum voo registrado.');
 flights.forEach(function(f){
  var row=entry(list,f.aircraft||'Aeronave não identificada',
   date(f.started_utc)+' • '+fmt(f.hours,2)+' h • '+fmt(f.direct_nm,1)+' NM',
   (f.mission_id?'Contrato '+f.mission_id:'Voo livre')+' • '+money(f.personal_net));
  button(actions(row),'Detalhes',function(){chooseFlight(f);},false);
 });
 if(selectedFlight){
  var current=flights.filter(function(f){return f.id===selectedFlight.id;})[0];
  if(current&&(!noteDirty||current.id!==selectedFlight.id))chooseFlight(current);
  else if(current)selectedFlight=current;
 }
}
function chooseFlight(f){
 selectedFlight=f;noteDirty=false;
 var host=fresh('logbook-details');
 entry(host,'Voo #'+f.id+' • '+(f.aircraft||'Aeronave'),
  date(f.started_utc)+' • '+fmt(f.hours,2)+' h • '+fmt(f.direct_nm,1)+' NM');
 entry(host,'Avaliação','Toque '+(f.touchdown_fpm===null?'não registrado':fmt(f.touchdown_fpm)+' ft/min')+
  ' • Estóis '+fmt(f.stalls)+' • XP '+fmt(f.xp));
 E('logbook-note').value=f.note||'';
 E('logbook-save').disabled=false;
}
function renderFinances(o){
 var f=o.finances||{},m=fresh('finance-metrics');
 metric(m,'SALDO ATUAL',money(f.balance),true);
 metric(m,'RECEITA OPERACIONAL',money(f.income));
 metric(m,'DESPESAS OPERACIONAIS',money(f.expenses));
 metric(m,'PATRIMÔNIO LÍQUIDO',money(f.net_worth),true);
 var chart=fresh('finance-chart'),months=f.monthly||[],high=1;
 months.forEach(function(x){high=Math.max(high,safeNum(x.income),safeNum(x.expense));});
 if(!months.length)placeholder(chart,'Ainda não há movimentações mensais para exibir.');
 months.forEach(function(x){
  var col=add(chart,node('div','finance-month'));
  var bars=add(col,node('div','finance-bars'));
  ['income','expense'].forEach(function(k){
   var bar=add(bars,node('span','finance-bar '+(k==='income'?'in':'out')));
   bar.style.height=Math.max(2,Math.round(115*safeNum(x[k])/high))+'px';
   bar.title=(k==='income'?'Receitas: ':'Despesas: ')+money(x[k]);
  });
  add(col,node('small','',x.month));
 });
 put('finance-debt','Dívida atual '+money(f.debt)+' • Limite '+money(f.loan_limit)+
  ' • taxa simulada '+fmt(100*safeNum(f.loan_rate))+'%');
 var tr=fresh('finance-transactions');
 if(!(f.transactions||[]).length)placeholder(tr,'Sem movimentações registradas.');
 (f.transactions||[]).forEach(function(x){
  var row=entry(tr,x.label||x.kind,date(x.occurred_utc)+' • '+(x.description||''));
  add(row,node('strong','',money(x.amount)));
 });
 E('finance-loan').disabled=!ground();
 E('finance-repay').disabled=!ground()||!(f.debt>0);
 E('finance-tax').disabled=!ground();
 put('finance-tax',f.income_tax_enabled?'Desativar imposto virtual de 4%':'Ativar imposto virtual de 4%');
}
function render(o){
 latest=o;office=o.office||{};
 if(!E('hangar-owned'))return;
 var isFresh=(o.office_updated||0)!==lastRevision;
 if(isFresh){
  lastRevision=o.office_updated||0;
  renderPlanning(office);renderHangar(office);renderAirlines(office);
  renderPilot(office);renderLogbook(office);renderFinances(office);
 }else{
  // Live operational guards may change between slower office snapshots.
  ['plan-save','plan-send','plan-clear','finance-loan','finance-tax'].forEach(function(id){
   if(E(id)&&!ground())E(id).disabled=true;
  });
 }
}
function view(viewName){
 if(viewName==='planning'&&!planLoaded&&office.planning)renderPlanning(office);
}
function receipt(r){
 if(r.action==='plan_save'||r.action==='plan_clear'){planDirty=false;planLoaded=false;}
 if(r.action==='logbook_note'){noteDirty=false;}
}
function hook(){
 // Replace the v0.9.1 placeholder using only static trusted markup.
 var pilotPage=document.querySelector('[data-page="career"]');
 if(pilotPage){
  while(pilotPage.firstChild)pilotPage.removeChild(pilotPage.firstChild);
  add(pilotPage,node('div','full','')); // deliberate stable content container below
  var host=pilotPage.firstChild;host.id='pilot-office';
  host.className='page full';host.style.display='grid';host.style.gridTemplateColumns='repeat(12,minmax(0,1fr))';
  host.style.gap='12px';
 }
 hookPlanning();
 Array.prototype.forEach.call(document.querySelectorAll('[data-fleet-tab]'),function(x){
  x.addEventListener('click',function(){
   tab=x.getAttribute('data-fleet-tab');
   Array.prototype.forEach.call(document.querySelectorAll('[data-fleet-tab]'),function(b){
    b.setAttribute('aria-pressed',b===x?'true':'false');
   });
   renderHangar(office);
  });
 });
 E('airline-review').addEventListener('click',function(){confirmAction('airline_review',null,
   'Conferir seleção e folha?','O motor verificará candidaturas e pagamentos elegíveis do período.');});
 E('airline-resign').addEventListener('click',function(){confirmAction('airline_resign',null,
   'Encerrar vínculo empregatício?','A demissão preservará o histórico de carreira e as horas de voo.');});
 E('airline-found').addEventListener('click',function(){
  var name=E('company-name').value.trim();
  if(name.length<3||name.length>50)return notice('Nome de 3 a 50 caracteres obrigatório.',true);
  confirmAction('airline_found',name,'Fundar '+name+'?',
   'O motor verificará a elegibilidade e o investimento exigido antes de descontar o valor.');
 });
 E('logbook-note').addEventListener('input',function(){noteDirty=true;});
 E('logbook-save').addEventListener('click',function(){
  if(selectedFlight)ask('logbook_note',{flight_id:selectedFlight.id,note:E('logbook-note').value},
   'Salvar anotação do voo?', 'A anotação ficará no SQLite do piloto ativo.');
 });
 E('finance-loan').addEventListener('click',function(){
  var n=Number(E('finance-amount').value),f=office.finances||{};
  if(!Number.isInteger(n)||n<1||n>500000)return notice('Valor inteiro inválido.',true);
  confirmAction('finance_loan',n,'Contratar empréstimo de '+money(n)+'?',
   'Dívida atual '+money(f.debt)+'; o motor confirmará limites e juros.');
 });
 E('finance-repay').addEventListener('click',function(){
  var n=Number(E('finance-amount').value),f=office.finances||{};
  if(!Number.isInteger(n)||n<1||n>500000)return notice('Valor inteiro inválido.',true);
  confirmAction('finance_repay',n,'Amortizar '+money(n)+'?',
   'Dívida atual '+money(f.debt)+' • operação com débito confirmado no SQLite.');
 });
 E('finance-tax').addEventListener('click',function(){
  var next=!(office.finances&&office.finances.income_tax_enabled);
  confirmAction('finance_tax',next,next?'Ativar imposto?':'Desativar imposto?',
   'A preferência será aplicada aos próximos pagamentos elegíveis.');
 });
}
hook();
window.FlightSimOfficeUI={render:render,view:view,receipt:receipt};
})();
