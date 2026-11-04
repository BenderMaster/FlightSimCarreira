"""Sobreposição aditiva: coordenadas por ICAO confirmadas no MSFS 2020.

Nunca rotular dado airportsdata como MSFS. Guardar proveniência e validar faixa;
aeroportos fora da base do simulador continuam visíveis como 'catálogo externo'.
"""
from __future__ import annotations
from dataclasses import replace
import json
from math import isfinite
from .domain import Airport, Mission

def validated_airport(code, lat, lon):
    code=str(code).upper()
    if not(len(code)==4 and code.isalnum()):
        raise ValueError('ICAO inválido')
    lat=float(lat);lon=float(lon)
    if not(isfinite(lat) and isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
        raise ValueError('Coordenadas de aeroporto inválidas')
    return code,lat,lon


def remember_airport(db,code,lat,lon):
    code,lat,lon=validated_airport(code,lat,lon)
    db.set_setting('msfs_navdata:'+code,json.dumps({'lat':lat,'lon':lon,'source':'MSFS'}))


def stored_airport(db,code):
    raw=db.get_setting('msfs_navdata:'+str(code).upper())
    if not raw:return None
    try:
        data=json.loads(raw)
        _,lat,lon=validated_airport(code,data['lat'],data['lon'])
        if data.get('source')!='MSFS':return None
        return lat,lon
    except (ValueError,KeyError,TypeError):
        return None


def overlay_catalog(catalog, db):
    for key,value in db.conn.execute("SELECT key,value FROM settings WHERE key LIKE 'msfs_navdata:%'"):
        code=key.partition(':')[2]
        coords=stored_airport(db,code)
        if coords and code in catalog.locations:
            previous=catalog.locations[code]
            catalog.locations[code]=Airport(code,previous.name,*coords)


def overlay_mission(m:Mission,db):
    fields={}
    for key,latitude,longitude in (
        (m.origin,'origin_lat','origin_lon'),
        (m.destination,'destination_lat','destination_lon')):
        coords=stored_airport(db,key)
        if coords:
            fields[latitude],fields[longitude]=coords
    if len(fields)==4:fields['nav_source']='MSFS'
    elif fields:fields['nav_source']='MISTO'
    return replace(m,**fields) if fields else m
