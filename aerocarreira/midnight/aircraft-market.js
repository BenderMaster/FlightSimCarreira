'use strict';
/* Mercado de aeronaves: só apresenta preços calculados no backend.
 * Nenhuma ação de carteira ocorre antes da confirmação explícita. */
(()=>{
 const el=id=>document.getElementById(id);
 const fmt=n=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL',maximumFractionDigits:0}).format(n||0);
 const dec=(n,d=0)=>Number(n||0).toLocaleString('pt-BR',{maximumFractionDigits:d});
 const element=(tag,cls,value)=>{
  const node=document.createElement(tag);if(cls)node.className=cls;
  if(value!==undefined)node.textContent=value;return node;
 };
 let tab='new',duration=24,chosen={new:null,used:null,rent:null,sell:null},
     lastKey='',pending=false,lastNotice=0,quote=null;
 const titles={new:'AERONAVES NOVAS',used:'SEMINOVAS / USADAS',rent:'MODELOS PARA ALUGUEL',sell:'MINHA FROTA / REVENDA'};
 const labels={new:'COMPRA NOVA',used:'COMPRA USADA',rent:'ALUGUEL',sell:'VENDA'};
 const actions={new:'aircraft_buy_new',used:'aircraft_buy_used',rent:'aircraft_rent',sell:'aircraft_sell'};
 const ids=item=>item?(item.ref||item.id||item.code):null;
 const options=(market)=>tab==='new'||tab==='rent'?market.models:tab==='used'?market.used:market.owned;

 function imageFor(item,s){
  if(!item)return null;
  if(tab==='sell'){
   const owned=s.fleet?.owned?.find(p=>p.ref===item.ref);
   if(owned?.photo_url)return {url:owned.photo_url,credit:false};
  }
  if(item.code==='c152')return {url:'/c152.jpg',credit:true};
  const art={c172:'/market-c172.jpg',g58:'/market-g58.jpg',
             kingair:'/market-kingair.jpg',cj4:'/market-cj4.jpg'};
  return art[item.code]?{url:art[item.code],credit:false}:null;
 }
 function quoteFor(item,market){
  if(!item)return null;
  const balance=market.balance||0;
  const fee=tab==='new'?item.price:tab==='used'?item.price:
            tab==='rent'?item.rental_prices?.[String(duration)]:item.resale_price;
  const amount=Number(fee);
  const gain=tab==='sell';
  const valid=Number.isFinite(amount)&&amount>=0;
  const after=balance+(gain?amount:-amount);
  const sold=tab==='used'&&item.sold;
  const unsellable=tab==='sell'&&!item.saleable;
  const remote=tab==='sell'&&market.airport!==item.airport;
  const affordable=gain||balance>=amount;
  const selectable=market.ready&&valid&&!pending&&!sold&&!unsellable&&!remote&&affordable;
  const reason=!market.ready?market.reason:
     sold?'Esta oferta já foi comprada.':
     unsellable?'Aeronaves iniciais/legadas não estão disponíveis para revenda.':
     remote?'A aeronave está em '+item.airport+'; só pode ser vendida nesse aeroporto.':
     !affordable?'Saldo insuficiente para esta operação.':
     pending?'Aguardando confirmação da operação anterior.':
     tab==='rent'?'O aluguel termina automaticamente após o prazo selecionado.':
     tab==='sell'?'Venda definitiva: o exemplar e a foto cadastrada serão retirados da Frota.':
     'Após a compra, o exemplar será adicionado à sua Frota.';
  return {item,amount,after,gain,allowed:selectable,reason,
   action:actions[tab],payload:tab==='rent'?item.code+'|'+duration:ids(item),
   caption:tab==='rent'?duration+' h de utilização':tab==='sell'?'Crédito pela revenda':
     tab==='used'?dec(item.condition,1)+'% de condição • '+dec(item.hours,0)+' h':'Aeronave nova • condição 100%'};
 }
 function render(s,force=false){
  const market=s?.aircraft_market;
  if(!market)return;
  const notice=market.notice;
  if(notice?.seq>lastNotice){
   lastNotice=notice.seq;pending=false;
   const message=(notice.ok?'Concluído: ':'Atenção: ')+notice.message;
   if(typeof toast==='function')toast(message);
   force=true;
  }
  if(typeof view!=='undefined'&&view!=='aircraft_market')return;
  const items=options(market)||[];
  if(!items.find(i=>ids(i)===chosen[tab])){chosen[tab]=ids(items[0]);force=true;}
  const key=JSON.stringify([tab,chosen[tab],duration,pending,market,
    s.fleet?.owned?.map(i=>[i.ref,i.photo_url])]);
  if(!force&&key===lastKey)return;
  lastKey=key;
  const item=items.find(i=>ids(i)===chosen[tab]);
  quote=quoteFor(item,market);
  const buttonTabs=document.querySelectorAll('[data-aircraft-market-tab]');
  buttonTabs.forEach(btn=>{
   const selected=btn.dataset.aircraftMarketTab===tab;
   btn.classList.toggle('selected',selected);
   btn.setAttribute('aria-pressed',String(selected));
  });
  el('am-balance').textContent=fmt(market.balance);
  el('am-airport').textContent=market.airport?'NEGOCIAÇÃO • '+market.airport:'AEROPORTO NÃO VERIFICADO';
  const warning=el('am-lock');warning.hidden=!!market.ready;
  warning.textContent=market.reason||'Aguarde o aeródromo confirmado no MSFS.';
  el('am-list-title').textContent=titles[tab];
  el('am-list-count').textContent=items.length+' '+(items.length===1?'opção':'opções');
  const list=el('am-list');list.replaceChildren();
  if(!items.length)list.append(element('p','aircraft-market-empty',
    tab==='used'?'Nenhuma oferta usada disponível. Conecte o MSFS para consultar o mercado semanal do aeródromo.':
    tab==='sell'?'Sem aeronaves próprias para revenda.':'Nenhuma opção disponível.'));
  for(const offer of items){
   const btn=element('button','aircraft-market-item'+(ids(offer)===chosen[tab]?' selected':'')+
      (offer.sold?' sold':''));btn.type='button';btn.dataset.amItem=ids(offer);
   btn.setAttribute('aria-pressed',String(ids(offer)===chosen[tab]));
   const badge=element('span','');badge.append(
      element('strong','',offer.title),
      element('small','',tab==='used'?dec(offer.condition,1)+'% • '+dec(offer.hours)+' h':
        tab==='sell'?offer.airport+' • '+dec(offer.condition,1)+'%':
        tab==='rent'?'Prazo configurável':'Nova • 100%'));
   const price=tab==='rent'?offer.rental_prices?.['24']:
     tab==='sell'?offer.resale_price:offer.price;
   badge.append(element('b','',offer.sold?'VENDIDA':offer.saleable===false?'NÃO VENDÁVEL':fmt(price)));
   const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
   const use=document.createElementNS(svg.namespaceURI,'use');use.setAttribute('href',tab==='new'?'#i-new-tag':'#i-plane');
   svg.append(use);btn.append(svg,badge);list.append(btn);
  }
  el('am-kind').textContent=labels[tab];
  el('am-name').textContent=item?.title||'Selecione uma aeronave';
  el('am-model').textContent=item?.code?.toUpperCase()||'';
  const photo=imageFor(item,s),img=el('am-photo');
  if(photo){
   img.hidden=false;if(img.getAttribute('src')!==photo.url)img.setAttribute('src',photo.url);
   img.alt='Imagem da aeronave '+item.title;
  }else{img.hidden=true;img.removeAttribute('src');}
  el('am-placeholder').hidden=!!photo;
  el('am-credit').hidden=!photo?.credit;
  el('am-condition').textContent=item?(tab==='rent'?'100%':dec(item.condition,1)+'%'):'—';
  el('am-hours').textContent=item?(tab==='new'||tab==='rent'?'0 h':dec(item.hours,1)+' h'):'—';
  const model=market.models.find(p=>p.code===item?.code);
  el('am-spec-third').textContent='CRUZEIRO DE REFERÊNCIA';
  el('am-cruise').textContent=model?dec(model.cruise_kts)+' kt':'—';
  el('am-spec-fourth').textContent='CAPACIDADE DE TANQUES';
  el('am-tanks').textContent=model?dec(model.fuel_capacity_gal)+' gal':'—';
  const extra=tab==='new'?'Nova • zero horas.':
   tab==='used'?'Oferta local renovada semanalmente.':
   tab==='rent'?'Aluguel temporário; não entra na Frota própria.':
   'Revenda definitiva de exemplar adquirido.';
  el('am-description').textContent=extra+' Selecione o modelo no MSFS antes de voar.';
  el('am-quote-kind').textContent=labels[tab];
  el('am-price').textContent=quote?fmt(quote.amount):'—';
  el('am-price-note').textContent=quote?.caption||'Selecione uma aeronave';
  el('am-duration-control').hidden=tab!=='rent';
  el('am-duration').value=String(duration);
  el('am-before').textContent=fmt(market.balance);
  el('am-change-label').textContent=tab==='sell'?'Crédito na conta':'Custo da operação';
  el('am-change').textContent=quote?(quote.gain?'+':'−')+fmt(quote.amount):'—';
  el('am-after').textContent=quote?fmt(quote.after):'—';
  el('am-after').classList.toggle('insufficient',!!quote&&quote.after<0);
  el('am-availability').textContent=quote?.reason||market.reason||'Selecione uma aeronave.';
  const buy=el('am-confirm-open');
  buy.disabled=!quote?.allowed;
  buy.textContent=tab==='sell'?'Revisar venda':tab==='rent'?'Revisar aluguel':'Revisar compra';
  const rentals=el('am-rentals');rentals.replaceChildren();
  if(!market.rentals.length)rentals.textContent='Nenhum aluguel em andamento';
  else for(const r of market.rentals){
   const date=new Date(r.expires*1000).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'});
   rentals.append(element('div','rented-row',r.title+' • '+r.airport+' • até '+date));
  }
 }
 el('am-list').addEventListener('click',event=>{
  const btn=event.target.closest('[data-am-item]');
  if(!btn)return;
  chosen[tab]=btn.dataset.amItem;lastKey='';
  render(state,true);
 });
 document.querySelectorAll('[data-aircraft-market-tab]').forEach(btn=>{
  btn.addEventListener('click',()=>{
   tab=btn.dataset.aircraftMarketTab;lastKey='';
   render(state,true);
  });
 });
 el('am-duration').addEventListener('change',event=>{
  duration=Number(event.target.value);
  if(![24,48,72,168].includes(duration))duration=24;
  lastKey='';render(state,true);
 });
 const dialog=el('aircraft-checkout-dialog');
 function close(){if(dialog.open)dialog.close();}
 el('am-cancel-top').onclick=close;el('am-cancel').onclick=close;
 el('am-confirm-open').onclick=()=>{
  const market=state.aircraft_market;
  if(!market||!quote?.allowed||pending)return;
  const items=options(market)||[],current=items.find(i=>ids(i)===chosen[tab]);
  const currentQuote=quoteFor(current,market);
  if(!currentQuote?.allowed){render(state,true);return;}
  quote=currentQuote;
  el('aircraft-checkout-title').textContent=tab==='sell'?'Confirmar venda':tab==='rent'?'Confirmar aluguel':'Confirmar compra';
  el('aircraft-checkout-description').textContent=
    'Você está prestes a '+(tab==='sell'?'vender':tab==='rent'?'alugar':'comprar')+
    ' '+current.title+'. Confira os valores antes de continuar.';
  el('am-confirm-plane').textContent=current.title;
  el('am-confirm-value').textContent=(quote.gain?'+':'−')+fmt(quote.amount);
  el('am-confirm-balance').textContent=fmt(quote.after);
  dialog.showModal();
 };
 el('am-commit').onclick=async()=>{
  if(pending||!quote?.allowed)return;
  const market=state.aircraft_market;
  if(!market?.ready){close();render(state,true);return;}
  const action=quote.action;
  const value=quote.payload+'|'+crypto.randomUUID();
  pending=true;close();render(state,true);
  try{
   const response=await fetch('/command',{method:'POST',headers:{
     'X-Flight-Token':token,'Content-Type':'application/json'},
     body:JSON.stringify({action,id:value})});
   if(!response.ok)throw Error('Comando não foi recebido pelo aplicativo ('+response.status+').');
   toast('Solicitação enviada. Aguardando confirmação no caixa da carreira.');
  }catch(err){
   pending=false;render(state,true);
   toast('Não foi possível enviar a negociação: '+err.message);
  }
 };
 window.FSCAircraftMarket={render};
})();
