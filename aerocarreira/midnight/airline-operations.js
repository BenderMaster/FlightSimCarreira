/* FlightSim 0.8.5 Airline Operations. Backend remains authoritative. */
(()=>{
'use strict';
const $=id=>document.getElementById(id);
const node=(tag,cls,value)=>{const x=document.createElement(tag);x.className=cls||'';if(value!==undefined)x.textContent=value;return x};
const money=x=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL',maximumFractionDigits:0}).format(x||0);
const fmt=x=>Number(x||0).toLocaleString('pt-BR',{maximumFractionDigits:1});
const names={nordeste:'AeroNordeste',azul:'Azul',gol:'GOL',latam:'LATAM'};
let current=null,tab='overview',lastNotice=0,tiers={},signature='';
function button(label,fn,disabled=false){const b=node('button','button',label);b.type='button';b.disabled=!!disabled;b.onclick=fn;return b}
function panel(title){const p=node('section','airline-panel');p.append(node('h2','',title));return p}
function metric(label,value){const p=node('div','airline-metric');p.append(node('small','',label),node('strong','',value));return p}
function message(value){return node('p','airline-description',value)}
function confirmAction(title,lines,action,id){
 const d=$('airline-confirm');$('airline-confirm-title').textContent=title;
 $('airline-confirm-body').replaceChildren(...lines.map(x=>message(x)));
 $('airline-confirm-yes').onclick=()=>{d.close();command(action,id)};
 d.showModal();
}
$('airline-confirm-cancel').onclick=()=>$('airline-confirm').close();
$('airline-confirm-x').onclick=()=>$('airline-confirm').close();
$('airline-review').onclick=()=>command('airline_review');
function choose(next){
 tab=next;
 document.querySelectorAll('[data-airline-tab]').forEach(b=>{
  const yes=b.dataset.airlineTab===next;b.classList.toggle('active',yes);
  b.setAttribute('aria-pressed',String(yes));
 });
 render(current,true);
}
document.querySelectorAll('[data-airline-tab]').forEach(b=>b.onclick=()=>choose(b.dataset.airlineTab));
function header(title,subtitle){const p=node('div','airline-subhead');p.append(node('h2','',title),message(subtitle));return p}
function overview(a,root){
 const banner=panel(a.mode==='empresario'?'PROPRIETÁRIO DE COMPANHIA':
  a.mode==='empregado'?'PILOTO CONTRATADO':'SUA CARREIRA AERONÁUTICA');
 banner.append(message(a.mode==='empregado'?'Salário e XP são pagos após cumprir a meta e encerrar a semana.':
  a.mode==='empresario'?'A empresa possui seu próprio caixa, aviões e livro financeiro.':
  'Comece no recrutamento e evolua até comandar sua própria companhia.'));
 const grid=node('div','airline-metrics');
 if(a.mode==='empregado'){
  const p=a.employment.progress||{},req=p.required||{};
  grid.append(metric('EMPREGADORA',names[a.employment.employer]||a.employment.employer),
   metric('CARGO',p.grade?.title||'Em treinamento'),
   metric('SALÁRIO-BASE SEMANAL',money(p.salary)),
   metric('COMPROMISSO','+'+a.employment.tier+'%'));
  const progress=panel('META DA SEMANA');
  progress.append(node('strong','airline-big',p.flights+' / '+req.flights+' VOOS • '+fmt(p.hours)+' / '+req.hours+' HORAS'));
  const bar=node('div','airline-bar'),fill=node('i');
  fill.style.width=Math.max(0,Math.min(100,100*Math.max(p.flights/(req.flights||1),p.hours/(req.hours||1))))+'%';
  bar.append(fill);progress.append(bar);
  progress.append(message('Basta cumprir uma das exigências. Meta básica: '+
   p.basic?.flights+' voos ou '+p.basic?.hours+' h. Fecha em '+
   new Date(p.ends_utc*1000).toLocaleString('pt-BR')+'.'));
  progress.append(button('Ver contratos da empresa',()=>choose('schedule')));
  root.append(banner,grid,progress);return;
 }
 if(a.mode==='empresario'){
  const c=a.business||{};
  grid.append(metric('CAIXA EMPRESARIAL',money(c.balance)),
   metric('REPUTAÇÃO EMPRESARIAL',fmt(c.reputation)+'/100'),
   metric('AVIÕES DA EMPRESA',(c.planes||[]).length),
   metric('OPERAÇÕES CONCLUÍDAS',c.operations||0));
  banner.append(button('Administrar companhia',()=>choose('business')));
 }else{
  grid.append(metric('VAGAS DA SEMANA',a.vacancies?.length||0),
   metric('COMPROMISSOS','0% / 10% / 20%'),
   metric('CAPITAL DE FUNDAÇÃO',money(a.investment)),
   metric('MODALIDADE','AUTÔNOMO'));
  banner.append(button('Ver recrutamento',()=>choose('jobs')),
   button('Treinar habilitações',()=>choose('training')));
 }
 root.append(banner,grid);
}
function training(a,root){
 root.append(header('HABILITAÇÕES DE TIPO / MODELO',
  'Treinamento registrado somente em voos reais do MSFS, nunca pela Demo nem por um clique.'));
 const summary=panel('COMO OBTER UMA HABILITAÇÃO');
 summary.append(message('Use no MSFS uma aeronave instalada, mesmo que não seja de sua propriedade na carreira. Realize 2 voos de pelo menos 10 minutos cada, sem aviso de estol e com pouso registrado entre -650 e -30 ft/min.'),
  message('O FlightSim verifica modelo, duração e pousos salvos. A habilitação é concedida automaticamente no SQLite após o segundo voo válido. PPA/PCA/IFR/MLTE continuam separados.'),
  button('Verificar aeronaves instaladas',()=>command('settings_scan')));
 root.append(summary);
 const candidates=a.type_ratings||[];
 for(const company of ['nordeste','latam','gol','azul']){
  const p=panel('FROTA AUTORIZADA • '+(names[company]||company));
  p.append(message(company==='nordeste'?
   'AeroNordeste: operações de entrada e aeronaves compatíveis. Modelos avançados exigem habilitação.':
   'Para candidatura, tenha ao menos um modelo habilitado desta frota.'));
  const list=node('div','airline-cards');
  const allowed=a.fleets?.[company]||[];
  for(const t of candidates.filter(t=>allowed.includes(t.code))){
   const item=node('div','airline-metric');
   item.append(node('strong','',t.title),
    node('small','',t.rated?'HABILITADO':
      t.flights+' / '+t.required+' voos de treinamento'),
    node('small','',t.installed?'INSTALAÇÃO VERIFICADA':'Instalação não confirmada'));
   list.append(item);
  }
  if(company==='nordeste')
   p.append(message('A frota clássica C152, C172, Baron G58, King Air 350i e CJ4 também permanece disponível conforme progressão.'));
  p.append(list);root.append(p);
 }
}
function jobs(a,root){
 root.append(header('RECRUTAMENTO SEMANAL','Escolha a meta de trabalho ANTES da candidatura.'));
 if(a.mode!=='autonomo'){root.append(message('É necessário retornar à carreira autônoma para concorrer a vagas.'));return;}
 const grid=node('div','airline-cards');
 for(const v of a.vacancies||[]){
  const box=panel(v.name);
  box.append(node('span','airline-prestige','PRESTÍGIO '+Math.round(v.employer_prestige*100)+'%'),
   node('strong','airline-big',money(v.salary)),
   message('Salário-base estimado por semana • Frota: '+(v.fleet||[v.aircraft]).join(', ')),
   message('Candidatura exige uma habilitação de modelo da frota. Treinamento gratuito em aeronave disponível no MSFS.'),
   message('Nível '+v.min_level+' • '+v.min_hours+' horas • '+v.qualifications.join(' / ')));
  const label=node('label','airline-form-label','Seu compromisso na contratação');
  const sel=node('select','');
  for(const t of v.targets){
   const option=new Option(t.tier+'% • '+t.flights+' voos OU '+t.hours+' horas',String(t.tier));
   sel.append(option);
  }
  sel.value=String(tiers[v.id]||0);
  const outcome=node('p','airline-description');
  const update=()=>{
   const tier=Number(sel.value);tiers[v.id]=tier;
   outcome.textContent='Meta cumprida: '+money(Math.round(v.salary*(1+tier/100)))+
    '. Só meta básica cumprida: '+money(Math.round(v.salary*(1-tier/100)))+
    '. Meta básica não cumprida: R$ 0 e 0 XP.';
  };
  sel.onchange=update;update();label.append(sel);
  box.append(label,outcome);
  const applied=(a.applications||[]).some(x=>x.vacancy_id===v.id);
  box.append(button(applied?'Candidatura enviada':'Candidatar-se',()=>{
    const tier=Number(sel.value),target=v.targets.find(x=>x.tier===tier);
    confirmAction('COMPROMISSO SEMANAL',[
     'Companhia: '+v.name,
     'Salário-base: '+money(v.salary)+' • adicional escolhido: '+tier+'%',
     'Obrigação: '+target.flights+' voos OU '+target.hours+' horas por semana.',
     'Se cumprir só a meta básica sem honrar o adicional, salário e XP sofrem desconto de '+tier+'%.',
     'Abaixo da meta básica não haverá salário nem XP.'],
     'airline_apply',v.id+'|'+tier);
  },!v.allowed||applied));
  if(!v.allowed)box.append(node('small','airline-warning',v.reason));
  grid.append(box);
 }
 if(!grid.childElementCount)root.append(message('Nenhuma vaga disponível nesta região.'));
 else root.append(grid);
}
function schedule(a,root){
 const isJob=a.mode==='empregado';
 const isOwn=a.mode==='empresario';
 root.append(header(isJob?'CONTRATOS DA EMPREGADORA':'ROTAS COMERCIAIS',
  isJob?'R$ 0 e 0 XP por voo. O trabalho é contado para salário e XP semanais.':
  'Receita e custo registrados SOMENTE na conta empresarial.'));
 if(!isJob&&!isOwn){root.append(message('Contratos de companhia exigem emprego ou empresa própria.'));return;}
 const list=isJob?a.employer_offers:a.corporate_offers;
 if(!list?.length){root.append(message('Sem rotas neste aeroporto. Confira o catálogo MSFS e a aeronave disponível.'));return;}
 const grid=node('div','airline-cards');
 for(const r of list){
  const pane=panel(r.origin+'  →  '+r.destination);
  const line=node('div','airline-plane-mark');
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  const use=document.createElementNS(svg.namespaceURI,'use');
  use.setAttribute('href','#i-plane');svg.append(use);line.append(svg);
  pane.append(line,message('Modelo: '+r.employer_plane+' • '+fmt(r.distance)+' NM • '+r.minutes+' min'),
   node('strong','airline-big',isJob?'SALÁRIO SEMANAL':money(r.reward)));
  pane.append(message(isJob?'Esta conclusão acumula horas e contratos para a meta.':
   'O caixa pessoal não recebe esta receita.'));
  pane.append(button('Aceitar rota',()=>{
   confirmAction('CONFIRMAR ROTA',[
    r.origin+' → '+r.destination+' • '+r.employer_plane,
    isJob?'Sem pagamento e XP imediato: conta para a folha semanal.':
     'Resultado financeiro entra somente no caixa da empresa.',
    'O MSFS deve estar conectado em solo com o modelo de avião indicado.'],
   'offer',r.id);
  },!r.allowed||!!a.active_mission));
  if(!r.allowed)pane.append(node('small','airline-warning',r.reason||'Bloqueada'));
  grid.append(pane);
 }
 root.append(grid);
}
function business(a,root){
 if(a.mode!=='empresario'){
  root.append(header('FUNDAÇÃO DE COMPANHIA PRÓPRIA',
    'Nível 18, 25 h, PLA e investimento inicial de '+money(a.investment)));
  const box=panel('NOVO NEGÓCIO');
  box.append(message('Os R$ 400 mil são transferidos do caixa pessoal para uma conta empresarial independente. Sem receita passiva.'));
  const label=node('label','airline-form-label','Nome da companhia');
  const input=node('input','');input.maxLength=60;input.placeholder='Nome da nova companhia';
  label.append(input);box.append(label);
  box.append(button('Revisar fundação',()=>{
   if(input.value.trim().length<3){$('airline-message').textContent='Informe um nome válido.';return;}
   confirmAction('FUNDAR COMPANHIA',[
    'Nome: '+input.value.trim(),'Aporte pessoal: '+money(a.investment),
    'Os R$ 400 mil entram no caixa empresarial, e não são duplicados no pessoal.'],
    'airline_found',input.value.trim());
  },a.mode!=='autonomo'));
  root.append(box);return;
 }
 const c=a.business||{},grid=node('div','airline-metrics');
 root.append(header(c.name,'Sede '+c.home_icao+' • Indicativo '+c.callsign));
 grid.append(metric('CAIXA DA EMPRESA',money(c.balance)),
  metric('REPUTAÇÃO CORPORATIVA',fmt(c.reputation)+'/100'),
  metric('FROTA EMPRESARIAL',(c.planes||[]).length),
  metric('VOOS OPERADOS',c.operations||0));root.append(grid);
 const buy=panel('MERCADO DE AERONAVES DA EMPRESA');
 buy.append(message('Compras debitam exclusivamente o caixa empresarial.'));
 for(const [code,name,price] of [
  ['c152','Cessna 152',80000],['c172','Cessna 172 Skyhawk',145000],
  ['g58','Baron G58',480000],['kingair','King Air 350i',1450000],
  ['cj4','Citation CJ4',3100000]]){
  const item=node('div','airline-aircraft');
  item.append(node('strong','',name),node('span','',money(price)),
   button('Comprar',()=>confirmAction('COMPRA EMPRESARIAL',[
    'Modelo: '+name,'Preço: '+money(price),
    'Caixa empresarial após compra: '+money(c.balance-price)],
    'airline_buy_plane',code),c.balance<price));
  buy.append(item);
 }root.append(buy);
 const fleet=panel('AERONAVES DA COMPANHIA');
 for(const p of c.planes||[]){
  const item=node('div','airline-aircraft');item.append(
   node('strong','',p.title+' • '+p.airport),
   node('span','','Condição '+fmt(p.condition)+'%'),
   node('span','',fmt(p.hours)+' h'));fleet.append(item);
 }
 if(!c.planes?.length)fleet.append(message('Sua companhia ainda não possui aeronaves.'));
 fleet.append(button('Abrir rotas comerciais',()=>choose('schedule'),!c.planes?.length));
 root.append(fleet);
}
function history(a,root){
 const jobs=panel('HISTÓRICO DE RECRUTAMENTO');
 for(const p of a.applications||[])jobs.append(message(
   (names[p.company_code]||p.company_code)+' • '+p.vacancy_id+' • '+p.status));
 if(!a.applications?.length)jobs.append(message('Sem candidaturas anteriores.'));
 root.append(jobs);
 const sheets=panel('FOLHA SALARIAL');
 for(const p of a.employment?.history||[])sheets.append(
  message('Semana '+(p.week+1)+' • '+p.flights+' voos • '+fmt(p.hours)+
   ' horas • '+money(p.salary)+' • '+p.xp+' XP • '+p.result));
 if(!a.employment?.history?.length)sheets.append(message('Ainda não há folhas encerradas.'));
 root.append(sheets);
 if(a.business){
  const log=panel('LIVRO EMPRESARIAL');
  for(const p of a.business.transactions||[])log.append(message(
   p.description+' • '+money(p.amount)+' • saldo '+money(p.balance_after)));
  root.append(log);
 }
}
function render(s,force=false){
 current=s;const a=s?.airline_operations;if(!a)return;
 if(a.notice?.seq&&a.notice.seq!==lastNotice){
  lastNotice=a.notice.seq;$('airline-message').textContent=a.notice.message;
 }
 $('airline-mode').textContent=({autonomo:'AUTÔNOMO',empregado:'PILOTO CONTRATADO',
  empresario:'EMPRESÁRIO'})[a.mode]||a.mode;
 const k=JSON.stringify([a.mode,a.employment,a.applications,a.vacancies,
  a.business,a.employer_offers,a.corporate_offers,a.active_mission,a.type_ratings,a.notice?.seq,tab]);
 if(!force&&k===signature)return;signature=k;
 const root=$('airline-content');root.replaceChildren();
 ({overview,jobs,training,schedule,business,history}[tab]||overview)(a,root);
}
window.FSCAirlineOperations={render,show:()=>current&&render(current,true)};
})();