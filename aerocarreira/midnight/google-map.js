/* Google Maps JavaScript API • satélite e marcadores do FlightSimCarreira.
 * Imagens exibidas apenas pelo SDK oficial; sem baixar tiles fora da API.
 * Sem chave, o mapa offline por coordenadas permanece operacional.
 */
(() => {
'use strict';
const PATH='M284 44 L273 41 L253 49 L199 99 L180 95 L189 84 L182 74 L160 92 L142 89 L153 74 L146 63 L122 85 L41 72 L28 86 L153 143 L84 218 L75 220 L42 215 L28 228 L66 244 L95 291 L107 280 L103 241 L182 168 L236 290 L251 275 L244 217 L265 195 L256 186 L241 198 L238 176 L260 155 L251 145 L234 156 L230 123 L275 77 L285 58 Z';
const get=()=>document.getElementById('google-map'),area=()=>document.querySelector('.map-area');
const validKey=k=>typeof k==='string'&&/^[A-Za-z0-9_-]{16,120}$/.test(k);
const validCoords=c=>Array.isArray(c)&&c.length===2&&c.every(Number.isFinite)&&Math.abs(c[0])<=90&&Math.abs(c[1])<=180;
const ll=c=>({lat:c[0],lng:c[1]});
const bearing=(a,b)=>{const r=Math.PI/180,lat1=a.lat*r,lat2=b.lat*r,d=(b.lng-a.lng)*r;
return(Math.atan2(Math.sin(d)*Math.cos(lat2),Math.cos(lat1)*Math.sin(lat2)-Math.sin(lat1)*Math.cos(lat2)*Math.cos(d))*180/Math.PI+360)%360};
const moved=(a,b)=>Math.hypot((a.lat-b.lat)*111000,(a.lng-b.lng)*111000*Math.cos(a.lat*Math.PI/180))>25;
let map=null,keyUsed='',pending=null,missionId=null,route=null,originMarker=null,destMarker=null,planeMarker=null;
let lastPosition=null,heading=0,active=false,nextTry=0,lastError='';
let recentState=null;
function fallback(message){
  active=false;area()?.classList.remove('google-active');if(get())get().style.display='none';
  if(message&&message!==lastError){lastError=message;console.warn('FlightSimCarreira Maps:',message);}
}
function fail(message){nextTry=Date.now()+60000;pending=null;fallback(message);}
function load(key){
  if(pending)return pending;
  if(Date.now()<nextTry)return Promise.reject(new Error('Aguarde antes de tentar carregar o mapa novamente.'));
  if(keyUsed&&keyUsed!==key)return Promise.reject(new Error('Chave alterada: reinicie a janela para recarregar o Google Maps.'));
  keyUsed=key;
  pending=new Promise((resolve,reject)=>{
    let settled=false;const script=document.createElement('script');
    const finish=err=>{if(settled)return;settled=true;clearTimeout(timeout);
      if(err){fail(err.message);reject(err);}else resolve(window.google.maps);};
    window.__fscMapsLoaded=()=>finish(null);
    window.gm_authFailure=()=>finish(new Error('Google Maps rejeitou a chave. Confira faturamento e restrições.'));
    script.async=true;
    script.src='https://maps.googleapis.com/maps/api/js?key='+encodeURIComponent(key)+'&v=weekly&loading=async&callback=__fscMapsLoaded';
    script.onerror=()=>finish(new Error('Mapa Google indisponível: conexão ou API.'));
    const timeout=setTimeout(()=>finish(new Error('Tempo limite ao carregar o Google Maps.')),15000);
    document.head.append(script);
  });
  return pending;
}
function pin(pos,label){
  return new google.maps.Marker({position:pos,map,title:label,label:{text:label,color:'#f2fbff',fontWeight:'bold',fontSize:'12px'},
    icon:{path:google.maps.SymbolPath.CIRCLE,scale:7,fillColor:'#00d6ed',fillOpacity:1,strokeColor:'#f0ffff',strokeWeight:2}});
}
function planeIcon(){
  const px=Math.max(21,Math.min(33,Math.round((get()?.clientWidth||700)*.042)));
  return {path:PATH,fillColor:'#35d6ff',fillOpacity:1,strokeColor:'#d9fcff',strokeWeight:.65,scale:px/260,
    anchor:new google.maps.Point(157,160),rotation:(heading-45+360)%360};
}
function clearRoute(){
  for(const obj of [route,originMarker,destMarker])if(obj)obj.setMap(null);
  route=originMarker=destMarker=null;
}
function update(s){
  if(!map||!s)return;
  const m=s.mission,id=m?.id||('BASE:'+ (s.market?.icao||''));
  const start=validCoords(m?.start)?ll(m.start):null,end=validCoords(m?.end)?ll(m.end):null;
  if(id!==missionId){
    missionId=id;clearRoute();
    if(start&&end){
      originMarker=pin(start,m.origin);destMarker=pin(end,m.destination);
      route=new google.maps.Polyline({map,path:[start,end],geodesic:true,strokeColor:'#00e9f9',strokeOpacity:1,strokeWeight:3});
      const bounds=new google.maps.LatLngBounds();bounds.extend(start);bounds.extend(end);
      map.fitBounds(bounds,Math.max(24,Math.min(60,map.getDiv().clientWidth*.05)));
    }else if(validCoords(s.telemetry?[s.telemetry.lat,s.telemetry.lon]:null)){
      map.setCenter({lat:s.telemetry.lat,lng:s.telemetry.lon});map.setZoom(12);
    }else if(validCoords(s.market?[s.market.lat,s.market.lon]:null)){
      map.setCenter({lat:s.market.lat,lng:s.market.lon});map.setZoom(12);
    }
  }
  const t=s.telemetry;
  if(t&&validCoords([t.lat,t.lon])){
    const pos={lat:t.lat,lng:t.lon};
    if(lastPosition&&moved(lastPosition,pos))heading=bearing(lastPosition,pos);
    lastPosition=pos;
    if(!planeMarker)planeMarker=new google.maps.Marker({map,position:pos,title:'Posição da aeronave MSFS',zIndex:100});
    planeMarker.setPosition(pos);planeMarker.setIcon(planeIcon());planeMarker.setOpacity(t.stale?0.5:1);
  }else if(planeMarker){planeMarker.setMap(null);planeMarker=null;lastPosition=null;}
}
function render(s){
  recentState=s;
  const key=s?.google_maps_key||'';
  if(!validKey(key)){fallback();return;}
  if(map&&active){update(s);return;}
  if(Date.now()<nextTry)return;
  load(key).then(()=>{
    if(!map)map=new google.maps.Map(get(),{center:{lat:-8.05,lng:-34.9},zoom:9,
      mapTypeId:'satellite',gestureHandling:'greedy',scrollwheel:true,zoomControl:false,
      fullscreenControl:false,mapTypeControl:false,streetViewControl:false,rotateControl:false,
      keyboardShortcuts:true,tilt:0,backgroundColor:'#071624'});
    active=true;get().style.display='block';area().classList.add('google-active');update(recentState);
  }).catch(e=>fallback(e.message));
}
function zoomBy(delta){if(!active||!map)return false;map.setZoom(Math.max(2,Math.min(21,(map.getZoom()||9)+delta)));return true;}
function recenter(s){if(!active||!map)return false;
  if(validCoords(s.mission?.start)&&validCoords(s.mission?.end)){
    const bounds=new google.maps.LatLngBounds();bounds.extend(ll(s.mission.start));bounds.extend(ll(s.mission.end));map.fitBounds(bounds,40);
  }else if(s.telemetry&&validCoords([s.telemetry.lat,s.telemetry.lon]))map.panTo({lat:s.telemetry.lat,lng:s.telemetry.lon});
  else if(s.market&&validCoords([s.market.lat,s.market.lon]))map.panTo({lat:s.market.lat,lng:s.market.lon});
  return true;
}
window.FSCGoogleMap={render,zoomBy,recenter,validKey,isActive:()=>active,aircraftPath:PATH,bearing};
})();
