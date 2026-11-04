"""METAR público NOAA e observação de ambiente do MSFS.

Não confundir SimVars no avião com o texto do boletim METAR de estação.
Sem consultas na thread Tk: requisições HTTPS correm num worker daemon,
com cache e backoff por ICAO, e sem dependência de chaves/cartão.
"""
from __future__ import annotations
import json
import re
import threading
import urllib.error
import urllib.request
from time import time
from .domain import AIRPORTS, distance_nm

ICAO=re.compile(r'^[A-Z0-9]{4}$')
URL='https://aviationweather.gov/api/data/metar?ids={icao}&format=json'
REFRESH_S=600
RETRY_S=180
AGENT='FlightSimCarreira/0.7.2 (+local simulator addon; NOAA METAR client)'


def metar_data(payload, icao):
    if not isinstance(payload,list):
        return None
    for record in payload[:10]:
        if not isinstance(record,dict):
            continue
        station=str(record.get('icaoId','')).upper()
        if station!=icao:
            continue
        raw=record.get('rawOb') or record.get('raw_text') or ''
        if not isinstance(raw,str):
            raw=''
        return {'icao':icao,'raw':raw[:350],
                'observed':record.get('reportTime') or record.get('obsTime'),
                'wind_direction':record.get('wdir'),
                'wind_kt':record.get('wspd'),
                'visibility':record.get('visib'),
                'temperature_c':record.get('temp'),
                'altimeter_hpa':record.get('altim'),
                'source':'NOAA Aviation Weather • METAR oficial'}
    return None


def fetch_metar(icao, timeout=5):
    icao=icao.strip().upper()
    if not ICAO.fullmatch(icao):
        raise ValueError('ICAO inválido')
    req=urllib.request.Request(URL.format(icao=icao),headers={'User-Agent':AGENT,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            if response.status==204:
                return None
            data=response.read(131072)
    except urllib.error.HTTPError as ex:
        if ex.code==204:
            return None
        raise
    return metar_data(json.loads(data),icao)


class MetarCache:
    def __init__(self,request=fetch_metar,clock=time):
        self.request=request
        self.clock=clock
        self.entries={}
        self.pending=set()
        self.lock=threading.RLock()

    def get(self,icao):
        if not icao or not ICAO.fullmatch(str(icao).upper()):
            return None
        code=str(icao).upper();now=self.clock()
        with self.lock:
            value,expiry=self.entries.get(code,(None,0))
            if now>=expiry and code not in self.pending:
                self.pending.add(code)
                threading.Thread(target=self._refresh,args=(code,),daemon=True,name='metar-noaa-'+code).start()
            return dict(value) if isinstance(value,dict) else None

    def _refresh(self,icao):
        try:
            value=self.request(icao)
            validity=REFRESH_S if value else RETRY_S
        except (OSError,ValueError,TypeError,json.JSONDecodeError):
            value=None;validity=RETRY_S
        now=self.clock()
        with self.lock:
            # Retém último boletim válido, mas identifica dados antigos no UI.
            old=self.entries.get(icao,(None,0))[0]
            if isinstance(value,dict):
                value=dict(value,fetched_at=now)
            elif isinstance(old,dict):
                value=dict(old,stale=True)
            self.entries[icao]=(value,now+validity)
            self.pending.discard(icao)


def within_nm(lat,lon,airport_lat,airport_lon,icao,max_nm=10):
    if lat is None or lon is None:
        return False
    airport=AIRPORTS.get(icao)
    a=airport_lat if airport_lat is not None else (airport.latitude if airport else None)
    b=airport_lon if airport_lon is not None else (airport.longitude if airport else None)
    if a is None or b is None:
        return False
    return distance_nm(lat,lon,a,b)<=max_nm


def sim_conditions(sample):
    if sample is None:
        return None
    def clean(v,lo,hi):
        try:
            f=float(v)
            return round(f,1) if lo<=f<=hi else None
        except (ValueError,TypeError,OverflowError):
            return None
    return {'wind_direction':clean(sample.wind_direction_deg,0,360),
            'wind_kt':clean(sample.wind_kt,0,250),
            'temperature_c':clean(sample.ambient_temperature_c,-100,80),
            'visibility_m':clean(sample.visibility_m,0,200000),
            'sea_level_pressure_hpa':clean(sample.sea_level_pressure_hpa,800,1100),
            'source':'MSFS • condições na posição da aeronave',
            'captured_at':time()}
