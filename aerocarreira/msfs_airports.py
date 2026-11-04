"""Única autoridade de navegação no modo MSFS: aeroportos da sessão atual.

Não confia em airportsdata, AIRPORTS, cache de outro dia, simulação Demo ou
ofertas SQLite antigas para validar aeroporto/rota no simulador.
"""
from __future__ import annotations

from dataclasses import replace
from math import isfinite
import re

from .contracts import AirportCatalog
from .domain import Airport, Mission

ICAO=re.compile(r'^[A-Z0-9]{4}$')


def catalog_from_msfs(raw):
    """Somente dados originados da mensagem SIMCONNECT_RECV_ID_AIRPORT_LIST."""
    if not isinstance(raw,dict):
        raise ValueError('Catálogo MSFS inválido')
    airports={}
    for code,coordinate in raw.items():
        if not isinstance(code,str) or not ICAO.fullmatch(code):
            continue
        if not isinstance(coordinate,(tuple,list)) or len(coordinate)!=2:
            continue
        lat,lon=coordinate
        if (type(lat) not in (float,int) or type(lon) not in (float,int)
            or not isfinite(lat) or not isfinite(lon)
            or not -90<=lat<=90 or not -180<=lon<=180):
            continue
        airports[code]=Airport(code,code,float(lat),float(lon))
    if not airports:
        raise ValueError('Nenhum aeroporto válido foi entregue pelo MSFS')
    # Argumento explícito impede carregar o airportsdata / AIRPORTS local.
    result=AirportCatalog(locations={})
    result.locations=airports
    result.global_catalog=True
    return result


def strict_mission(mission:Mission,catalog:AirportCatalog|None):
    """Resolve origem e destino exclusivamente no inventário desta sessão."""
    if not catalog:return None
    a=catalog.locations.get(mission.origin)
    b=catalog.locations.get(mission.destination)
    if a is None or b is None:return None
    return replace(mission,origin_lat=a.latitude,origin_lon=a.longitude,
                   destination_lat=b.latitude,destination_lon=b.longitude,
                   nav_source='MSFS')


def restricted_mission(mission:Mission,catalog:AirportCatalog|None):
    """Missão histórica permanece visível sem falsificar rota fora do MSFS."""
    resolved=strict_mission(mission,catalog)
    if resolved:return resolved
    return replace(mission,origin_lat=None,origin_lon=None,
                   destination_lat=None,destination_lon=None,
                   nav_source='NAO_VERIFICADO')
