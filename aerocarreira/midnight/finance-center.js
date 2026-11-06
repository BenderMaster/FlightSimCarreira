/* FlightSim Financial Center — v0.8.4 Alpha.1
 * Presentation-only adapter. The backend ledger is authoritative.
 */
(()=>{
'use strict';
const $=id=>document.getElementById(id);
const money=v=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL',maximumFractionDigits:0}).format(Number(v)||0);
const num=v=>Number(v||0).toLocaleString('pt-BR',{maximumFractionDigits:0});
const text=(id,value)=>{$(id).textContent=value==null?'—':String(value)};
const el=(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=value;return e};
let tab='overview',snapshot=null,lastSignature='',lastNotice=0,pending=null,currentState=null;
let fullExportRequested=false;
const kindColor=amount=>amount>=0?'fin-positive':'fin-negative';
function date(t){
 if(!Number.isFinite(t))return '—';
 return new Date(t*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric',
   hour:'2-digit',minute:'2-digit'});
}
function setTab(which){
 tab=which;
 document.querySelectorAll('[data-fin-tab]').forEach(button=>{
  const active=button.dataset.finTab===tab;
  button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));
 });
 for(const name of ['overview','statement','flights','assets','bank']){
  $('fin-'+name).hidden=name!==tab;
 }
 if(currentState)render(currentState,true);
}
document.querySelectorAll('[data-fin-tab]').forEach(b=>b.onclick=()=>setTab(b.dataset.finTab));
function row(pairs){
 const item=el('div','fin-receipt-attribute');
 for(const [a,b] of [pairs]){item.append(el('span','',a),el('strong','',b));}
 return item;
}
function showReceipt(item){
 const dialog=$('fin-receipt'),body=$('fin-receipt-body');
 body.replaceChildren();
 const attrs=[
  ['Identificador','#'+item.id],['Registro',date(item.occurred_utc)],
  ['Categoria',item.label],['Descrição',item.description],
  ['Valor',money(item.amount)],['Saldo após',money(item.balance_after)],
  ['Referência',item.event_key]
 ];
 for(const pair of attrs)body.append(row(pair));
 dialog.showModal();
}
$('fin-receipt-close').onclick=()=>$('fin-receipt').close();
$('fin-receipt-close-top').onclick=()=>$('fin-receipt').close();
$('fin-receipt').onclick=e=>{if(e.target===$('fin-receipt'))$('fin-receipt').close();};
function confirmOperation(title,lines,action,value){
 const dialog=$('fin-confirm');
 text('fin-confirm-title',title);
 const body=$('fin-confirm-body');body.replaceChildren();
 for(const line of lines)body.append(el('p','',line));
 $('fin-confirm-yes').onclick=()=>{
  dialog.close();
  send(action,value);
 };
 dialog.showModal();
}
$('fin-confirm-close-top').onclick=()=>$('fin-confirm').close();
$('fin-confirm-cancel').onclick=()=>$('fin-confirm').close();
$('fin-confirm').onclick=e=>{if(e.target===$('fin-confirm'))$('fin-confirm').close();};
function uuid(){
 if(globalThis.crypto?.randomUUID)return crypto.randomUUID();
 const a=crypto.getRandomValues(new Uint8Array(16));a[6]=(a[6]&15)|64;a[8]=(a[8]&63)|128;
 const h=[...a].map(v=>v.toString(16).padStart(2,'0')).join('');
 return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20);
}
async function send(action,value){
 if(pending){text('fin-message','Aguardando confirmação da operação anterior.');return;}
 pending=action;
 fullExportRequested=action==='finance_export';
 text('fin-message','Solicitação enviada. Aguardando confirmação do motor financeiro...');
 try{
  const payload=value===undefined?{action}:{action,id:value};
  const r=await fetch('/command',{method:'POST',
    headers:{'Content-Type':'application/json','X-Flight-Token':token},
    body:JSON.stringify(payload)});
  if(!r.ok)throw Error('HTTP '+r.status);
 }catch(err){
  text('fin-message','Falha na comunicação: '+err.message);
  pending=null;fullExportRequested=false;
 }
}
async function downloadCSV(){
 try{
  const r=await fetch('/finance-export',{headers:{'X-Flight-Token':token}});
  if(!r.ok)throw Error('HTTP '+r.status);
  const blob=await r.blob(),url=URL.createObjectURL(blob);
  const link=document.createElement('a');
  link.href=url;link.download='FlightSim-extrato-'+new Date().toISOString().slice(0,10)+'.csv';
  document.body.append(link);link.click();link.remove();
  // Objeto temporário: descarte após o evento de download, sem retenção do CSV.
  window.setTimeout(()=>URL.revokeObjectURL(url),30000);
 }catch(e){text('fin-message','O extrato foi preparado, mas o download falhou: '+e.message);}
}
function render(s,force=false){
 currentState=s;
 const f=s?.financial_center;
 if(!f)return;
 if(f.notice?.seq && f.notice.seq!==lastNotice){
  lastNotice=f.notice.seq;
  text('fin-message',f.notice.message);
  if(f.notice.ok&&f.notice.action==='finance_export'&&fullExportRequested){
   downloadCSV();
  }
  fullExportRequested=false;pending=null;
 }
 const signature=JSON.stringify([
  f.balance,f.income,f.expenses,f.debt,f.assets_value,
  f.total_transactions,f.transactions?.[0]?.id,f.notice?.seq,
  f.operations?.length,f.income_tax_enabled
 ]);
 if(!force&&signature===lastSignature)return;
 lastSignature=signature;snapshot=f;
 text('fin-balance',money(f.balance));
 text('fin-income',money(f.income));
 text('fin-expenses',money(f.expenses));
 text('fin-net',money(f.operating_net));
 text('fin-worth',money(f.net_worth));
 $('fin-net').className=kindColor(f.operating_net);
 text('fin-aircraft-count',num((f.assets||[]).filter(x=>x.kind==='new'||x.kind==='used').length));
 text('fin-resale-short',money(f.assets_value));
 text('fin-completed',num(f.contracts_completed));
 text('fin-insurance-paid',money((f.expense_categories||[]).find(x=>x.kind==='seguro')?.value||0));
 text('fin-debt-short',money(f.debt));
 text('fin-debt',money(f.debt));
 text('fin-loan-status',f.debt>0?'Financiamento ativo • quite antes de solicitar outro':'Crédito disponível até R$ 150.000');
 text('fin-invested',money(f.invested));
 text('fin-resale',money(f.assets_value));
 text('fin-assets-total',money(f.net_worth));
 text('fin-repay-cash',money(f.balance));
 $('fin-tax').checked=!!f.income_tax_enabled;
 $('fin-loan-value').disabled=!!f.loan_open;
 $('fin-take-loan').disabled=!!f.loan_open;
 $('fin-repay-value').disabled=!f.loan_open;
 $('fin-repay').disabled=!f.loan_open;
 updateLoanMath();updateRepayMath();
 renderMonthly(f);renderExpenses(f);renderStatement(f);renderOperations(f);renderAssets(f);
}
function svgNode(name,attrs={},value){
 const svg=document.createElementNS('http://www.w3.org/2000/svg',name);
 for(const [k,v] of Object.entries(attrs))svg.setAttribute(k,String(v));
 if(value!==undefined)svg.textContent=value;
 return svg;
}
function chartEmpty(where,message){
 const root=$(where);root.replaceChildren();
 root.append(el('p','fin-empty',message));
}
function renderMonthly(f){
 const data=(f.monthly||[]).slice(-8);
 if(!data.length){chartEmpty('fin-monthly-chart','Os primeiros contratos registrarão os dados neste gráfico.');return;}
 const root=$('fin-monthly-chart');root.replaceChildren();
 const svg=svgNode('svg',{viewBox:'0 0 690 300',role:'img',
   'aria-label':'Receitas e despesas mensais em reais'});
 const max=Math.max(1,...data.flatMap(x=>[x.income,x.expense]));
 const step=Math.ceil(max/4/100)*100||1, ceiling=step*4;
 const left=85,bottom=240,top=28,span=bottom-top,area=570;
 const y=v=>bottom-v/ceiling*span;
 for(let n=0;n<=4;n++){
  const yy=bottom-n*span/4;
  svg.append(svgNode('path',{d:'M'+left+' '+yy+'H660',stroke:'#3b6173',
   'stroke-width':1,'stroke-dasharray':n?'4 5':'none'}));
  svg.append(svgNode('text',{x:78,y:yy+4,'text-anchor':'end',fill:'#9ec6d5',
   'font-size':12},num(n*step)));
 }
 const width=area/data.length;
 for(const [i,d] of data.entries()){
  const x=left+i*width+width/2,w=Math.min(26,width*.25);
  const bars=[{value:d.income,dx:-w-3,color:'#17c9d6'},
              {value:d.expense,dx:3,color:'#e1b86b'}];
  for(const bar of bars){
   const h=bar.value/ceiling*span,xx=x+bar.dx;
   const rect=svgNode('rect',{x:xx,y:bottom-h,width:w,height:Math.max(.1,h),rx:3,fill:bar.color});
   rect.append(svgNode('title',{},(bar.color==='#17c9d6'?'Receita: ':'Despesa: ')+money(bar.value)));
   svg.append(rect);
   if(bar.value>0)svg.append(svgNode('text',{x:xx+w/2,y:Math.max(top+12,bottom-h-8),
    'text-anchor':'middle',fill:'#f8e3b3','font-size':11,'font-weight':700},
    num(bar.value)));
  }
  svg.append(svgNode('text',{x,y:260,'text-anchor':'middle',fill:'#c2dbe5','font-size':12},
   d.month.slice(5)+'/'+d.month.slice(2,4)));
 }
 root.append(svg);
 const legend=el('div','fin-chart-legend');
 for(const [name,color] of [['Receita operacional','#17c9d6'],['Despesa operacional','#e1b86b']]){
  const item=el('span');const square=el('i');square.style.background=color;
  item.append(square,document.createTextNode(name));legend.append(item);
 }
 root.append(legend);
}
function renderExpenses(f){
 const data=(f.expense_categories||[]).slice(0,7),root=$('fin-expense-chart');
 root.replaceChildren();
 if(!data.length){root.append(el('p','fin-empty','Ainda não há despesas operacionais registradas.'));return;}
 const max=Math.max(1,...data.map(d=>d.value));
 for(const item of data){
  const bar=el('div','fin-expense-item');
  const label=el('div','fin-expense-label');
  label.append(el('span','',item.label),el('strong','',money(item.value)));
  const track=el('div','fin-expense-track'),fill=el('i');
  fill.style.width=Math.min(100,item.value/max*100)+'%';
  fill.title=item.label+' • '+money(item.value);
  track.append(fill);bar.append(label,track);root.append(bar);
 }
 root.append(el('p','fin-note','Seguros, abastecimentos, manutenção e aluguéis são despesas efetivamente registradas.'));
}
function filteredTransactions(f){
 const query=$('fin-search').value.trim().toLocaleLowerCase('pt-BR'),
   category=$('fin-category').value,days=$('fin-period').value;
 const cutoff=days==='all'?null:Date.now()/1000-Number(days)*86400;
 return (f.transactions||[]).filter(item=>
   (category==='all'||category===item.category)&&
   (cutoff===null||item.occurred_utc>=cutoff)&&
   (!query||(item.description+' '+item.label+' '+item.event_key).toLocaleLowerCase('pt-BR').includes(query)));
}
function renderStatement(f){
 const tbody=$('fin-transactions');tbody.replaceChildren();
 const items=filteredTransactions(f);
 text('fin-count',num(items.length)+' exibidas · '+num(f.total_transactions)+' registradas');
 if(!items.length){
  const r=el('tr'),c=el('td','fin-empty','Nenhuma transação corresponde aos filtros.');
  c.colSpan=5;r.append(c);tbody.append(r);
 }else for(const item of items){
  const r=el('tr','fin-transaction');
  r.tabIndex=0;r.title='Abrir comprovante';
  const cells=[date(item.occurred_utc),item.description,item.label,money(item.amount),
               money(item.balance_after)];
  cells.forEach((content,i)=>{
   const c=el('td',i===3?kindColor(item.amount):'',content);
   r.append(c);
  });
  r.onclick=()=>showReceipt(item);
  r.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();showReceipt(item);}};
  tbody.append(r);
 }
 text('fin-list-note',f.total_transactions>500?
  'Mostrando os 500 movimentos mais recentes. O CSV exporta TODOS os registros do banco, sem esse limite.':
  'Clique em qualquer linha para abrir o comprovante. Os dados vêm do ledger original.');
}
for(const id of ['fin-search','fin-category','fin-period']){
 $(id).addEventListener(id==='fin-search'?'input':'change',()=>{
   if(snapshot)renderStatement(snapshot);
 });
}
$('fin-export').onclick=()=>send('finance_export');
function renderOperations(f){
 const root=$('fin-operation-list');root.replaceChildren();
 const flights=f.operations||[];
 if(!flights.length){root.append(el('p','fin-empty','Ainda não existem voos registrados nesta carreira.'));return;}
 for(const flight of flights){
  const card=el('details','fin-operation fin-panel');
  const top=el('summary');
  const heading=el('div','fin-operation-name');
  heading.append(el('strong','',flight.aircraft),el('small','',date(flight.started_utc)+
   ' • '+(flight.mission||'Voo livre')));
  top.append(heading,el('strong',kindColor(flight.net),money(flight.net)));
  card.append(top);
  const breakdown=el('div','fin-operation-breakdown');
  const lines=[['Remuneração e bônus',flight.gross],
   ['Combustível em voo',-flight.fuel],['Taxas aeroportuárias',-flight.airport],
   ['Imposto do voo',-flight.tax],['Despesas operacionais',-flight.expenses],
   ['Resultado do voo',flight.net]];
  for(const [name,value] of lines)breakdown.append(row([name,money(value)]));
  if(!flight.paid)breakdown.append(el('p','fin-note',
   'Sem movimentação financeira registrada para este voo.'));
  card.append(breakdown);root.append(card);
 }
 root.append(el('p','fin-note','Seguros e revisões pagos fora de voo estão no Extrato e no Resumo. O lucro por voo não os cobra duas vezes.'));
}
function renderAssets(f){
 const root=$('fin-assets-list');root.replaceChildren();
 const assets=f.assets||[];
 if(!assets.length){root.append(el('p','fin-empty','Nenhuma aeronave própria cadastrada.'));return;}
 for(const asset of assets){
  const card=el('div','fin-asset-item');
  const heading=el('div','fin-asset-name');
  heading.append(el('strong','',asset.title),
    el('small','',(asset.airport||'Sem localização')+' • Condição '+Number(asset.condition).toFixed(1)+'%'+
      (asset.insured?' • Segurada':' • Sem seguro')));
  const prices=el('div','fin-asset-prices');
  prices.append(el('span','','Investido: '+(asset.purchase_price==null?'Cortesia / legado':money(asset.purchase_price))),
   el('strong','',asset.resale_price==null?'Sem revenda cadastrada':money(asset.resale_price)));
  card.append(heading,prices);root.append(card);
 }
}
function updateLoanMath(){
 const input=Number($('fin-loan-value').value),valid=Number.isInteger(input)&&input>=1000&&input<=150000;
 text('fin-loan-principal',valid?money(input):'Valor fora do limite');
 text('fin-loan-fee',valid?money(Math.round(input*.08)):'—');
 text('fin-loan-total',valid?money(Math.round(input*1.08)):'—');
 if(snapshot)$('fin-take-loan').disabled=!!snapshot.loan_open||!valid||!!pending;
}
function updateRepayMath(){
 const input=Number($('fin-repay-value').value),f=snapshot;
 const valid=!!f&&Number.isInteger(input)&&input>0&&input<=f.debt&&input<=f.balance;
 text('fin-repay-after',valid?money(f.debt-input):'—');
 if(f)$('fin-repay').disabled=!valid||!!pending;
}
$('fin-loan-value').addEventListener('input',updateLoanMath);
$('fin-repay-value').addEventListener('input',updateRepayMath);
document.querySelectorAll('[data-fin-loan-preset]').forEach(b=>b.onclick=()=>{
 $('fin-loan-value').value=b.dataset.finLoanPreset;updateLoanMath();
});
$('fin-take-loan').onclick=()=>{
 const principal=Number($('fin-loan-value').value),f=snapshot;
 if(!f||f.loan_open||!Number.isInteger(principal)||principal<1000||principal>150000)return;
 confirmOperation('REVISAR EMPRÉSTIMO',[
  'Crédito imediato: '+money(principal),
  'Custo fixo de 8%: '+money(Math.round(principal*.08)),
  'Dívida total: '+money(Math.round(principal*1.08)),
  'O valor do empréstimo aumenta o caixa, mas NÃO conta como receita operacional.'
 ],'finance_loan',String(principal)+'|'+uuid());
};
$('fin-repay').onclick=()=>{
 const value=Number($('fin-repay-value').value),f=snapshot;
 if(!f||!Number.isInteger(value)||value<=0||value>f.debt||value>f.balance)return;
 confirmOperation('REVISAR PAGAMENTO',[
  'Valor a debitar: '+money(value),
  'Caixa após pagamento: '+money(f.balance-value),
  'Dívida restante: '+money(f.debt-value)
 ],'finance_repay',String(value)+'|'+uuid());
};
$('fin-tax').onchange=()=>{
 if(!snapshot)return;
 send('finance_tax',$('fin-tax').checked?'1':'0');
};
window.FSCFinancialCenter={render,show:()=>currentState&&render(currentState,true)};
})();