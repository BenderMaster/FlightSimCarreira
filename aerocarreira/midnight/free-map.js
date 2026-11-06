/* FlightSimCarreira FreeMap — OpenFreeMap + MapLibre, sem chave nem cartão.
 * Sentinel-2 2016 EOxCloudless: CC BY 4.0; créditos na área do mapa.
 * Rotas e posição vêm do domínio/SimConnect, nunca de uma rota fabricada.
 */
(() => {
'use strict';
const AIRCRAFT_PATH=document.querySelector('#i-plane path')?.getAttribute('d')||'M12 1L10 9 1 15 1 17 10 15 10 19 6 21 6 22 12 21 18 22 18 21 14 19 14 15 23 17 23 15 14 9 12 1Z';
const SAT_TILES='https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg';
const SAT_CREDIT='EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2016 & 2017)';
const BASE='https://tiles.openfreemap.org/styles/dark';
const CDN='https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/dist/maplibre-gl.js';
let map=null,loading=null,active=false,sat=false,missionKey=null,routeSourceReady=false;
let airportMarkers=[],planeMarker=null,previousPosition=null,bearingDeg=45,latest=null,retryAfter=0;
let resizeObserver=null,lastWidth=0,lastHeight=0;
const elem=id=>document.getElementById(id),valid=c=>Array.isArray(c)&&c.length===2&&c.every(Number.isFinite)&&Math.abs(c[0])<=90&&Math.abs(c[1])<=180;
const latlng=c=>({lat:c[0],lng:c[1]});
const bearing=(a,b)=>{
 const r=Math.PI/180,p1=a.lat*r,p2=b.lat*r,d=(b.lng-a.lng)*r;
 return (Math.atan2(Math.sin(d)*Math.cos(p2),Math.cos(p1)*Math.sin(p2)-Math.sin(p1)*Math.cos(p2)*Math.cos(d))*180/Math.PI+360)%360;
};
function loadScript(url){
 return new Promise((resolve,reject)=>{
  const sc=document.createElement('script');sc.src=url;sc.async=true;
  const alarm=setTimeout(()=>{sc.remove();reject(new Error('tempo limite'))},9000);
  sc.onload=()=>{clearTimeout(alarm);resolve()};
  sc.onerror=()=>{clearTimeout(alarm);reject(new Error('falha de carregamento'))};
  document.head.append(sc);
 });
}
function libraries(){
 if(window.maplibregl)return Promise.resolve(window.maplibregl);
 if(loading)return loading;
 if(Date.now()<retryAfter)return Promise.reject(new Error('mapa temporariamente indisponível'));
 loading=loadScript('/vendor/maplibre-gl.js').catch(()=>loadScript(CDN)).then(()=>{
  if(!window.maplibregl)throw new Error('MapLibre indisponível');
  return window.maplibregl;
 }).catch(error=>{loading=null;retryAfter=Date.now()+60000;throw error});
 return loading;
}
function resizeToContainer(){
 if(!map||!active)return;
 const el=elem('free-map');
 if(!el||!el.clientWidth||!el.clientHeight)return;
 // O WebView2 inicia o HTML oculto; redimensionar só após torná-lo visível.
 const w=el.clientWidth,h=el.clientHeight;
 if(w!==lastWidth||h!==lastHeight){lastWidth=w;lastHeight=h;map.resize();}
}
function setupResize(){
 const target=elem('free-map');
 if(!target)return;
 if(typeof ResizeObserver!=='undefined'){
  resizeObserver=new ResizeObserver(()=>resizeToContainer());
  resizeObserver.observe(target);
 }
 window.addEventListener('resize',resizeToContainer);
 requestAnimationFrame(()=>{resizeToContainer();requestAnimationFrame(resizeToContainer)});
}
function updateCredit(){
 const el=elem('satellite-credit');
 if(el){el.hidden=!(sat&&map&&routeSourceReady&&map.getLayer('eox-satellite-layer'));if(!sat)el.open=false;el.title=SAT_CREDIT}
 const btn=elem('satellite-toggle');if(btn)btn.textContent=sat?'Satélite: ON':'Satélite: OFF';
}
function setSatellite(){
 updateCredit();
 if(!map||!routeSourceReady)return;
 if(sat&&!map.getSource('eox-satellite')){
  map.addSource('eox-satellite',{type:'raster',tiles:[SAT_TILES],tileSize:256,maxzoom:14,
   attribution:'EOxCloudless · CC BY 4.0'});
  map.addLayer({id:'eox-satellite-layer',type:'raster',source:'eox-satellite',paint:{'raster-opacity':1}},'route-glow');
 }
 if(map.getLayer('eox-satellite-layer')){
  map.setLayoutProperty('eox-satellite-layer','visibility',sat?'visible':'none');
 }
 updateCredit();
}
function toggleSatellite(){sat=!sat;setSatellite();return sat}
function updateMarkers(s){
 if(!map||!routeSourceReady)return;
 const m=s?.mission;
 const key=m?.id||('base:'+ (s?.market?.icao||''));
 if(key!==missionKey){
  missionKey=key;
  for(const item of airportMarkers)item.remove();airportMarkers=[];
  const start=valid(m?.start)?latlng(m.start):null,end=valid(m?.end)?latlng(m.end):null;
  const via=Array.isArray(m?.route_points)&&m.route_points.length>=2?
     m.route_points.filter(valid).map(latlng):null;
  const path=via?.length>=2?via:[start,end].filter(Boolean);
  const line=start&&end?{type:'Feature',properties:{},
   geometry:{type:'LineString',coordinates:path.map(p=>[p.lng,p.lat])}}:
   {type:'FeatureCollection',features:[]};
  map.getSource('fsc-route').setData(line);
  if(start&&end){
   const markerPoints=[[start,m.origin],...((via||[]).slice(1,-1).map((p,i)=>[p,m.waypoints?.[i]?.label||('FIX'+(i+1))])),[end,m.destination]];
   for(const [p,label] of markerPoints){
    const el=document.createElement('div');el.className='fsc-airport-marker';el.textContent=label;
    airportMarkers.push(new maplibregl.Marker({element:el,anchor:'bottom'}).setLngLat([p.lng,p.lat]).addTo(map));
   }
   const bounds=new maplibregl.LngLatBounds();
   for(const p of path)bounds.extend([p.lng,p.lat]);
   map.fitBounds(bounds,{padding:35,maxZoom:12,duration:0});
  }else if(s?.telemetry&&Number.isFinite(s.telemetry.lat)&&Number.isFinite(s.telemetry.lon)){
   map.jumpTo({center:[s.telemetry.lon,s.telemetry.lat],zoom:11});
  }else if(s?.market&&Number.isFinite(s.market.lat)&&Number.isFinite(s.market.lon)){
   map.jumpTo({center:[s.market.lon,s.market.lat],zoom:11});
  }
 }
 const t=s?.telemetry;
 if(t&&Number.isFinite(t.lat)&&Number.isFinite(t.lon)&&Math.abs(t.lat)<=90&&Math.abs(t.lon)<=180){
  const pos={lat:t.lat,lng:t.lon};
  if(previousPosition){
   const meters=111000*Math.hypot(pos.lat-previousPosition.lat,(pos.lng-previousPosition.lng)*Math.cos(pos.lat*Math.PI/180));
   if(meters>25)bearingDeg=bearing(previousPosition,pos);
  }
  previousPosition=pos;
  if(!planeMarker){
   const el=document.createElement('div');el.className='fsc-plane-marker';
   el.innerHTML='<svg viewBox="0 0 24 24" aria-label="Aeronave"><path d="'+AIRCRAFT_PATH+'"/></svg>';
   planeMarker=new maplibregl.Marker({element:el,anchor:'center',rotationAlignment:'map'}).setLngLat([pos.lng,pos.lat]).addTo(map);
  }
  planeMarker.setLngLat([pos.lng,pos.lat]);
  // Proa verdadeira lida do SimConnect: funciona parado no pátio.
  // Recorre ao rumo derivado de posições apenas se a SimVar estiver ausente.
  if(Number.isFinite(t.heading_deg)&&t.heading_deg>=0&&t.heading_deg<360)
    bearingDeg=t.heading_deg;
  const svg=planeMarker.getElement().querySelector('svg');
  if(svg)svg.style.transform='rotate('+bearingDeg+'deg)';
  planeMarker.getElement().title='Proa magnética (painel): '+(Number.isFinite(t.heading_magnetic_deg)?Math.round(t.heading_magnetic_deg)+'°':'indisponível')+' • proa verdadeira (mapa): '+(Number.isFinite(t.heading_deg)?Math.round(t.heading_deg)+'°':'indisponível');
  planeMarker.getElement().style.opacity=t.stale?'0.5':'1';
 }else{
  if(planeMarker)planeMarker.remove();
  planeMarker=null;previousPosition=null;
 }
}
function start(){
 if(map||!window.maplibregl)return;
 try{
  if(typeof maplibregl.supported==='function'&&!maplibregl.supported())return;
  // Tornar o contêiner visível ANTES de construir o canvas WebGL.
  const mapArea=document.querySelector('.map-area'),mapNode=elem('free-map');
  mapArea?.classList.add('free-active');
  if(mapNode){mapNode.style.display='block';mapNode.style.width='100%';mapNode.style.height='100%';}
  map=new maplibregl.Map({container:'free-map',style:BASE,center:[-34.92,-8.12],zoom:9,
    antialias:false,renderWorldCopies:false,
   scrollZoom:true,dragPan:true,touchZoomRotate:true,keyboard:true,
   pitchWithRotate:false,dragRotate:false,maxPitch:0,attributionControl:false,fadeDuration:0});
  map.addControl(new maplibregl.AttributionControl({compact:true}),'bottom-left');
  map.on('load',()=>{
   map.addSource('fsc-route',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
   map.addLayer({id:'route-glow',type:'line',source:'fsc-route',
    paint:{'line-color':'#35d6ff','line-width':10,'line-opacity':0.2}});
   map.addLayer({id:'route-main',type:'line',source:'fsc-route',
    paint:{'line-color':'#35d6ff','line-width':3,'line-opacity':0.95}});
   routeSourceReady=true;
   resizeToContainer();setSatellite();updateMarkers(latest);
  });
  // Apenas na aba Planejamento: clique direito, Shift+clique ou toque longo.
  const activePlan=()=>document.querySelector('.workspace')?.dataset.view==='planning';
  const addPoint=e=>{
   if(!activePlan()||!e?.lngLat)return;
   e.originalEvent?.preventDefault?.();
   window.FSCFlightOps?.proposeWaypoint?.(e.lngLat.lat,e.lngLat.lng);
  };
  map.on('contextmenu',e=>addPoint(e));
  map.on('click',e=>{if(e.originalEvent?.shiftKey)addPoint(e);});
  let held=null;
  const cancelHeld=()=>{if(held){clearTimeout(held);held=null;}};
  map.on('touchstart',e=>{
   cancelHeld();
   if(!activePlan()||!e?.lngLat||e.originalEvent?.touches?.length!==1)return;
   const lat=e.lngLat.lat,lon=e.lngLat.lng;
   held=setTimeout(()=>{held=null;window.FSCFlightOps?.proposeWaypoint?.(lat,lon);},800);
  });
  for(const evt of ['touchend','touchcancel','dragstart','zoomstart','movestart'])
   map.on(evt,cancelHeld);
  map.on('error',e=>{if(e?.error)console.warn('FreeMap: tile/style',e.error.message||e.error)});
  active=true;
  setupResize();
 }catch(error){
   console.warn('FreeMap: WebGL indisponível',error);map=null;active=false;
   document.querySelector('.map-area')?.classList.remove('free-active');
   const mapNode=elem('free-map');if(mapNode)mapNode.style.display='none';
 }
}
function render(s){
 latest=s;
 if(active&&map){resizeToContainer();updateMarkers(s);return}
 if(Date.now()<retryAfter)return;
 libraries().then(()=>start()).catch(()=>{active=false});
}
function zoomBy(dir){if(!active||!map)return false;map.zoomTo(Math.max(2,Math.min(20,map.getZoom()+dir)),{duration:120});return true}
function recenter(s){
 if(!active||!map)return false;
 const current=s||latest,t=current?.telemetry;
 if(t&&Number.isFinite(t.lat)&&Number.isFinite(t.lon)&&Math.abs(t.lat)<=90&&Math.abs(t.lon)<=180){
   // Não acompanha a câmera automaticamente; recentraliza só ao clicar.
   map.easeTo({center:[t.lon,t.lat],duration:250});
 }else{
   missionKey=null;
   updateMarkers(current);
 }
 return true;
}
window.FSCFreeMap={render,isActive:()=>active,zoomBy,recenter,toggleSatellite,resizeToContainer,
 satelliteEnabled:()=>sat,aircraftPath:AIRCRAFT_PATH,bearing};
})();
