"""Resolver rotas usando coordenadas aeronáuticas reportadas pelo MSFS."""
from __future__ import annotations
from dataclasses import replace

def resolve_mission_navdata(mission,catalog):
    if catalog is None:return mission
    overrides={}
    for icao,latkey,lonkey in (
        (mission.origin,'origin_lat','origin_lon'),
        (mission.destination,'destination_lat','destination_lon')):
        if icao in catalog.sim_codes and icao in catalog.locations:
            airport=catalog.locations[icao]
            overrides[latkey]=airport.latitude
            overrides[lonkey]=airport.longitude
    return replace(mission,**overrides) if overrides else mission

def official_route_ready(mission,catalog):
    return bool(catalog and mission.origin in catalog.sim_codes
                and mission.destination in catalog.sim_codes)
