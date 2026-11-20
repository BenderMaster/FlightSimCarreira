/* FlightSim InGame 0.9.3 — optional MapLibre, same free sources as desktop.
 * Load only on selecting Map. Native MSFS VFR map is not embedded or controlled.
 * Coherent GT may lack WebGL2/network; original offline SVG always remains.
 */
(function(){
'use strict';
var map=null,booted=false,ready=false,failed=false,mode='street';
var data={},routeKey='',planeMarker=null,waypointMarkers=[],timer=null;
var container=document.getElementById('ingame-real-map');
var svg=document.getElementById('map');
var status=document.getElementById('map-status');
var BASE='https://tiles.openfreemap.org/styles/dark';
var SAT='https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg';
function info(message){if(status)status.textContent=message;}
function fallback(message){
 failed=true;ready=false;
 if(timer){clearTimeout(timer);timer=null;}
 if(container)container.style.display='none';
 if(svg)svg.style.display='block';
 info('Mapa SVG disponível • '+message);
 if(map){try{map.remove();}catch(e){}map=null;}
}
function coords(){
 var office=data.office||{},plan=office.planning||{},r=plan.route||{};
 var raw=Array.isArray(r.route)?r.route:[];
 var route=raw.filter(function(v){return Array.isArray(v)&&typeof v[0]==='number'&&
  typeof v[1]==='number'&&isFinite(v[0])&&isFinite(v[1]);}).map(function(v){return [v[1],v[0]];});
 if(!route.length){
  var m=data.mission||{};
  if(typeof m.origin_lat==='number'&&typeof m.origin_lon==='number'&&
     typeof m.destination_lat==='number'&&typeof m.destination_lon==='number')
   route=[[m.origin_lon,m.origin_lat],[m.destination_lon,m.destination_lat]];
 }
 return route;
}
function featureLine(line){
 return {type:'FeatureCollection',features:line.length>1?
  [{type:'Feature',properties:{},geometry:{type:'LineString',coordinates:line}}]:[]};
}
function setupSources(){
 if(!map||!ready)return;
 if(!map.getSource('flight-route')){
  map.addSource('flight-route',{type:'geojson',data:featureLine([])});
  map.addLayer({id:'flight-route-line',type:'line',source:'flight-route',
   paint:{'line-color':'#67dce8','line-width':3,'line-dasharray':[2,2]}});}
 if(!map.getSource('eox-satellite')){
  map.addSource('eox-satellite',{type:'raster',tiles:[SAT],tileSize:256,
    attribution:'EOX s2cloudless',maxzoom:14});
  map.addLayer({id:'eox-satellite-layer',source:'eox-satellite',type:'raster',
    layout:{visibility:'none'}},'flight-route-line');
 }
 if(map.getLayer('eox-satellite-layer'))map.setLayoutProperty('eox-satellite-layer','visibility',mode==='satellite'?'visible':'none');
}
function makePin(label,color){
 var el=document.createElement('div');
 el.style.cssText='padding:5px 7px;border:1px solid '+color+
   ';border-radius:7px;background:#091e2de8;color:#e7f7fd;font:600 12px Arial;white-space:nowrap;box-shadow:0 3px 8px #0009';
 el.textContent=label;
 return el;
}
function markers(route){
 if(!map||!ready)return;
 waypointMarkers.forEach(function(m){m.remove();});waypointMarkers=[];
 route.forEach(function(pos,index){
  var names=data.office&&data.office.planning&&data.office.planning.route;
  var labels=names&&names.legs||[];
  var label=index===0?(data.mission&&data.mission.origin||names&&names.origin||'ORIGEM'):
   index===route.length-1?(data.mission&&data.mission.destination||names&&names.destination||'DESTINO'):
    labels[index-1]&&labels[index-1].to||'FIX'+index;
  var pin=new maplibregl.Marker({element:makePin(label,index===0?'#e0bd76':index===route.length-1?'#78e6b0':'#67dce8')})
   .setLngLat(pos).addTo(map);
  waypointMarkers.push(pin);
 });
}
function redraw(){
 if(!map||!ready)return;
 var line=coords(),key=JSON.stringify(line);
 if(map.getSource('flight-route'))map.getSource('flight-route').setData(featureLine(line));
 if(key!==routeKey){
  routeKey=key;markers(line);
  if(line.length>1){
   var bounds=new maplibregl.LngLatBounds();
   line.forEach(function(p){bounds.extend(p);});
   map.fitBounds(bounds,{padding:45,maxZoom:11,duration:0});
  }
 }
 var pos=data.position||{},h=data.telemetry&&data.telemetry.heading_deg;
 if(typeof pos.lat==='number'&&typeof pos.lon==='number'){
  if(!planeMarker){
   var aircraft=makePin('AVIÃO','#f5ffff');
   planeMarker=new maplibregl.Marker({element:aircraft,rotationAlignment:'map'})
    .setLngLat([pos.lon,pos.lat]).addTo(map);
   if(line.length<2)map.jumpTo({center:[pos.lon,pos.lat],zoom:10});
  }else planeMarker.setLngLat([pos.lon,pos.lat]);
  if(typeof h==='number')planeMarker.setRotation(h);
 }
}
function connect(){
 if(booted||failed||!container)return;
 booted=true;
 var probe=document.createElement('canvas'),gl=null;
 try{gl=probe.getContext('webgl')||probe.getContext('experimental-webgl');}
 catch(e){}
 if(!gl)return fallback('WebGL não é compatível com este navegador Coherent.');
 if(!window.maplibregl){
  var script=document.createElement('script');
  script.src='/maplibre-gl.js';
  script.onload=initialize;
  script.onerror=function(){fallback('Biblioteca MapLibre local indisponível.');};
  document.head.appendChild(script);
 }else initialize();
}
function initialize(){
 if(failed)return;
 try{
  if(typeof maplibregl.supported==='function'&&!maplibregl.supported())
   return fallback('Renderizador WebGL não suportado.');
  container.style.display='block';
  map=new maplibregl.Map({container:container,style:BASE,
   center:[-34.92,-8.12],zoom:8,attributionControl:false,
   dragRotate:false,pitchWithRotate:false,renderWorldCopies:false});
  map.addControl(new maplibregl.AttributionControl({compact:true}),'bottom-left');
  map.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
  timer=setTimeout(function(){if(!ready)fallback('Fonte cartográfica indisponível ou não suportada no MSFS.');},12000);
  map.on('load',function(){
   ready=true;
   if(timer){clearTimeout(timer);timer=null;}
   setupSources();
   if(svg)svg.style.display='none';
   info('OpenFreeMap • mapa livre, com rota e posição do SimConnect. Não substitui o mapa VFR nativo.');
   redraw();
  });
  map.on('error',function(err){
   if(!ready&&err&&err.error)info('MapLibre: esperando mapa / tiles.');
  });
 }catch(err){fallback('Falha ao carregar MapLibre: '+String(err.message||err).slice(0,100));}
}
function toggle(next){
 mode=next;
 ['street','satellite'].forEach(function(x){
  var el=document.getElementById('map-'+x);
  if(el)el.setAttribute('aria-pressed',x===mode?'true':'false');
 });
 if(ready){setupSources();redraw();}
}
function view(name){
 if(name==='route'){
  if(!booted)connect();
  if(map)setTimeout(function(){try{map.resize();}catch(e){}},80);
 }
}
function render(snapshot){data=snapshot;if(ready)redraw();}
var street=document.getElementById('map-street'),satellite=document.getElementById('map-satellite');
if(street)street.addEventListener('click',function(){toggle('street');});
if(satellite)satellite.addEventListener('click',function(){toggle('satellite');});
window.FlightSimGeographicMap={view:view,render:render};
})();