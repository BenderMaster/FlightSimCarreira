/* FlightSim Midnight Settings Center v0.8.7.
 * No direct SQLite/filesystem access from WebView2. All changes use the
 * authenticated backend queue and are refreshed from confirmed snapshots.
 */
(()=>{
'use strict';
const el=id=>document.getElementById(id);
const elem=(tag,cls,content)=>{
 const n=document.createElement(tag);if(cls)n.className=cls;
 if(content!==undefined)n.textContent=String(content);return n;
};
let current=null,tab='sim',signature='',lastNotice=null,lastAppliedSatellite=null;
const titles={sim:'SIMULADOR E CONEXÃO',career:'CARREIRA E REALISMO',
 ui:'INTERFACE MIDNIGHT',data:'DADOS E BACKUPS',
 diagnostics:'DIAGNÓSTICO E FERRAMENTAS',about:'SOBRE O FLIGHTSIM'};
async function send(action,payload){
 try{
  const body=payload===undefined?{action}:{action,payload};
  const res=await fetch('/command',{method:'POST',
   headers:{'Content-Type':'application/json','X-Flight-Token':token},
   body:JSON.stringify(body)});
  if(!res.ok)throw Error('HTTP '+res.status);
  el('sc-message').textContent='Solicitação enviada. Aguardando confirmação do aplicativo.';
 }catch(e){
  el('sc-message').textContent='Não foi possível enviar a solicitação: '+e.message;
 }
}
function command(action){
 if(typeof window.command==='function')window.command(action);
 else send(action);
}
function section(title,desc){
 const box=elem('section','sc-panel');
 const head=elem('div','sc-panel-head');
 head.append(elem('h2','',title));
 if(desc)head.append(elem('p','',desc));
 box.append(head);return box;
}
function line(label,value,kind=''){
 const r=elem('div','sc-line '+kind);
 r.append(elem('span','',label),elem('strong','',value??'—'));
 return r;
}
function button(label,onClick,style=''){
 const b=elem('button','button '+style,label);
 b.type='button';b.onclick=onClick;return b;
}
function actionRow(...items){
 const r=elem('div','sc-actions');r.append(...items);return r;
}
function setting(label,desc,checked,key,disabled=false){
 const wrap=elem('label','sc-setting'+(disabled?' unavailable':''));
 const body=elem('div','sc-setting-copy');
 body.append(elem('strong','',label),elem('small','',desc));
 const input=elem('input','sc-switch');
 input.type='checkbox';input.checked=!!checked;input.disabled=disabled;
 input.onchange=()=>send('settings_set',{key,value:input.checked});
 wrap.append(body,input);return wrap;
}
function scaleRow(prefs){
 const wrap=elem('label','sc-setting');
 const body=elem('div','sc-setting-copy');
 body.append(elem('strong','','Escala do painel'),
  elem('small','','Ajusta proporcionalmente textos, cartões e comandos. Recomendado: 100%.'));
 const sel=elem('select','sc-select');
 for(const value of [80,90,100,110,125,150]){
  const opt=new Option(value+'%',String(value));sel.append(opt);
 }
 sel.value=String(prefs.interface_scale||100);
 sel.onchange=()=>send('settings_set',{key:'interface_scale',value:Number(sel.value)});
 wrap.append(body,sel);return wrap;
}
function notice(text,severity='normal'){
 return elem('p','sc-note '+severity,text);
}
function sim(s,root){
 const p=s.preferences;
 const connection=section('SIMCONNECT / MSFS 2020',
  'A conexão é automática quando habilitada. Um estado conectado exige leitura efetiva do simulador.');
 connection.append(line('Conexão',s.connection==='connected'?'CONECTADO':
  s.connection==='reconnecting'?'RECONECTANDO':'DESCONECTADO',
  s.connection==='connected'?'positive':''),
 line('Estado',s.state),line('Aeronave detectada',s.aircraft||'Sem confirmação atual'),
 line('Telemetria',s.telemetry_age==null?'Aguardando dados':'Última leitura há '+s.telemetry_age+' s'),
 line('Catálogo de aeroportos MSFS',s.airport_count==null?'Aguardando MSFS':
  s.airport_count.toLocaleString('pt-BR')+' aeródromos'));
 connection.append(actionRow(
  button('Conectar MSFS',()=>command('connect'),'primary'),
  button('Desconectar',()=>command('disconnect')),
  button('Reconectar / atualizar aeroportos',()=>command('connect'))));
 root.append(connection);
 const options=section('INICIALIZAÇÃO E RECUPERAÇÃO','Preferências gerais, mantidas entre perfis.');
 options.append(setting('Conectar ao iniciar','Tenta conexão quando o FlightSim é aberto.',p.autoconnect,'autoconnect'),
  setting('Reconexão automática','Quando houver queda, tentar recuperar o SimConnect sem inundar o log.',p.reconnect,'reconnect'));
 root.append(options);
 const tools=section('AMBIENTE DE TESTES','Modo Demo separado da carreira MSFS.');
 tools.append(actionRow(button('Iniciar demonstração',()=>command('demo')),
  button('Avançar demonstração',()=>command('demo_next'))));
 tools.append(notice('A demo não pode conceder habilitações de modelo. O mercado real utiliza somente aeroportos confirmados pelo MSFS.'));
 root.append(tools);
}
function career(s,root){
 const controls=section('REGRAS DA CARREIRA','As alterações são persistidas somente no piloto ativo.');
 controls.append(setting('Combustível controlado pelo FlightSim',
  'Desativar aplica penalidade de 30% em R$ e XP nos voos seguintes. Não pode mudar em voo.',
  s.fuel,'fuel',s.flight_active));
 controls.append(setting('Tributação virtual de 4%',
  'Imposto opcional sobre contratos, aplicado somente nos lançamentos futuros.',
  s.tax,'tax',s.flight_active));
 controls.append(setting('Preferência para falhas simuladas',
  'Preparação para uma versão futura: ainda NÃO injeta falhas no avião.',
  s.failures,'failures',s.flight_active));
 controls.append(notice('O modo de combustível do voo atual é congelado na decolagem. Configurações não alteram saldos ou XP históricos.','warning'));
 root.append(controls);
}
function ui(s,root){
 const p=s.preferences;
 const panel=section('EXPERIÊNCIA MIDNIGHT','Ajustes locais da interface, sem custo ou mudança na carreira.');
 panel.append(scaleRow(p),
  setting('Reduzir animações','Menos movimentos e transições visuais.',p.reduced_motion,'reduced_motion'),
  setting('Satélite ao iniciar','Camada EOxCloudless sujeita à disponibilidade da internet; créditos permanecem visíveis.',p.satellite_default,'satellite_default'),
  setting('Animações e notificações de conquistas','Eventos permanecem pendentes até a janela estar em foco e a opção estar ativada.',p.notifications,'notifications'));
 panel.append(notice('O tema Midnight permanece como padrão. A resolução e o dimensionamento interno podem variar com o DPI do Windows.'));
 root.append(panel);
}
function data(s,root){
 const p=section('SALVAR E RESTAURAR CARREIRAS',
  'Um backup reúne os perfis e seus dados SQLite, incluindo fotos de frota; a cópia mantém consistência mesmo com WAL.');
 p.append(line('Perfil ativo',s.active_profile||'—'),
  line('Quantidade de perfis',s.profiles_count??0));
 p.append(actionRow(
  button('Fazer backup completo (.zip)',()=>send('settings_backup'),'primary'),
  button('Importar backup',()=>send('settings_restore'))));
 p.append(notice('Restaurações são importadas como novos perfis e nunca sobrescrevem uma carreira existente. Para alternar, use Meu Piloto.','warning'));
 p.append(actionRow(button('Abrir pasta de dados no Windows',()=>send('settings_open_data'))));
 root.append(p);
}
function diagnostics(s,root){
 const scan=section('AERONAVES INSTALADAS','Leitura local de arquivos aircraft.cfg nas pastas Community e Official; não altera addons.');
 scan.append(line('Variações lidas',s.scan_count==null?'Ainda não verificado':s.scan_count),
  actionRow(button('Escanear aeronaves instaladas',()=>send('settings_scan'),'primary')));
 scan.append(notice('A varredura pode ser parcial quando o Marketplace protege arquivos. Um nome encontrado não comprova que você possui a licença do modelo.'));
 root.append(scan);
 const logs=section('REGISTRO DE EVENTOS','Eventos recentes da sessão; caminhos e coordenadas podem ser omitidos no arquivo exportado.');
 const log=elem('pre','sc-log',(current?.log||[]).slice(-25).join('\n')||'Sem eventos recentes.');
 logs.append(log,setting('Ocultar caminhos e coordenadas no diagnóstico',
  'Proteção básica ao exportar. Revise o arquivo antes de compartilhar.',
  s.preferences.redact_diagnostics,'redact_diagnostics'));
 logs.append(actionRow(button('Exportar diagnóstico',()=>send('settings_export_log'),'primary')));
 root.append(logs);
 const advanced=section('FERRAMENTAS AVANÇADAS','Utilitários herdados, usados somente quando solicitados.');
 advanced.append(actionRow(button('Analisar NeoFly',()=>command('analyze')),
  button('Localizar NeoFly',()=>command('locate')),
  button('Painel experimental',()=>command('local_panel')),
  button('Contratos legados',()=>command('legacy'))));
 root.append(advanced);
}
function about(s,root){
 const p=section('FLIGHTSIM / MIDNIGHT OPS','Gerenciador de carreira para Microsoft Flight Simulator 2020.');
 p.append(line('Versão',s.version),line('Interface','Midnight Ops • WebView2'),
  line('Armazenamento','SQLite local, carreiras isoladas'),
  line('Motor','Python / SimConnect'),
  line('Companhias','Regras internas de jogo; não há vínculo com as empresas.'));
 const a=document.createElement('a');a.href='https://github.com/BenderMaster/FlightSimCarreira';
 a.target='_blank';a.rel='noopener noreferrer';a.textContent='Abrir repositório FlightSimCarreira';
 a.className='sc-link';p.append(a);
 p.append(notice('Créditos do mapa: OpenFreeMap, OpenStreetMap e EOxCloudless, conforme a camada. Fotografia C152 conforme créditos originais. O FlightSim não é um addon oficial do MSFS.'));
 root.append(p);
}
const renderers={sim,career,ui,data,diagnostics,about};
function render(snapshot,force=false){
 if(!snapshot?.settings_center)return;
 current=snapshot;const s=snapshot.settings_center,p=s.preferences||{};
 // Preferences are applied outside the settings page and work on any screen.
 const scale=p.interface_scale||100;
 if(document.documentElement.dataset.flightScale!==String(scale)){
  document.documentElement.dataset.flightScale=String(scale);
  document.documentElement.style.zoom=String(scale/100);
 }
 document.documentElement.dataset.reducedMotion=String(!!p.reduced_motion);
 if(window.FSCFreeMap&&lastAppliedSatellite===null){
  lastAppliedSatellite=!!p.satellite_default;
  if(!!window.FSCFreeMap.satelliteEnabled()!==lastAppliedSatellite)
   window.FSCFreeMap.toggleSatellite();
 }
 if(s.notice?.seq!=null && s.notice.seq!==lastNotice){
  lastNotice=s.notice.seq;el('sc-message').textContent=s.notice.message;
  el('sc-message').classList.toggle('sc-error',!s.notice.ok);
 }
 if(document.querySelector('.workspace')?.dataset.view!=='settings')return;
 const key=JSON.stringify([tab,p,s.fuel,s.tax,s.failures,s.mode,s.connection,
  s.aircraft,s.airport_count,s.flight_active,s.scan_count,s.active_profile,
  s.profiles_count,s.notice?.seq,s.state,s.version]);
 if(!force&&key===signature)return;
 signature=key;
 el('sc-status').textContent=titles[tab];
 document.querySelectorAll('[data-sc-tab]').forEach(x=>{
  x.classList.toggle('selected',x.dataset.scTab===tab);
  x.setAttribute('aria-current',x.dataset.scTab===tab?'page':'false');
 });
 const root=el('sc-content');root.replaceChildren();
 renderers[tab](s,root);
}
function init(){
 document.querySelectorAll('[data-sc-tab]').forEach(b=>b.onclick=()=>{
  tab=b.dataset.scTab;signature='';if(current)render(current,true);
 });
}
init();
window.FSCSettings={render,show:()=>current&&render(current,true)};
})();
