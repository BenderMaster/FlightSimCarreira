"""Plano VFR para MSFS 2020 sem alterar o estado da aeronave.

Exportação XML .PLN baseada no SDK da Microsoft. Carregamento no simulador
é solicitado somente por ação explícita do piloto e não prova sincronismo do
mapa VFR, GPS ou mudança de aeronave até validação física.
"""
from __future__ import annotations
from pathlib import Path
from xml.etree import ElementTree as ET
import re
from .domain import Mission, AIRPORTS


def _dms(value: float, latitude: bool) -> str:
    if not (-90 <= value <= 90 if latitude else -180 <= value <= 180):
        raise ValueError('Coordenadas inválidas')
    hemi = ('N' if value >= 0 else 'S') if latitude else ('E' if value >= 0 else 'W')
    amount = abs(value)
    degrees = int(amount)
    minutes_decimal = (amount-degrees)*60
    minutes = int(minutes_decimal)
    seconds = round((minutes_decimal-minutes)*60, 2)
    if seconds >= 60:
        seconds -= 60; minutes += 1
    if minutes >= 60:
        minutes -= 60; degrees += 1
    return f'{hemi}{degrees}° {minutes:02d}\' {seconds:05.2f}"'


def position(lat: float, lon: float) -> str:
    return f'{_dms(lat, True)},{_dms(lon, False)},+000000.00'


def build_vfr_plan(mission: Mission, cruising_altitude_ft: int = 2500, *, waypoints=None) -> bytes:
    if not 500 <= cruising_altitude_ft <= 45000:
        raise ValueError('Altitude de cruzeiro inválida')
    if not all(re.fullmatch(r'[A-Z0-9]{4}', s) for s in (mission.origin, mission.destination)):
        raise ValueError('ICAO inválido')
    from_ap = AIRPORTS.get(mission.origin)
    to_ap = AIRPORTS.get(mission.destination)
    if (mission.origin_lat is None or mission.origin_lon is None) and from_ap is None:
        raise ValueError('Coordenadas da origem ausentes')
    if (mission.destination_lat is None or mission.destination_lon is None) and to_ap is None:
        raise ValueError('Coordenadas do destino ausentes')
    from_pos = position(mission.origin_lat if mission.origin_lat is not None else from_ap.latitude,
                        mission.origin_lon if mission.origin_lon is not None else from_ap.longitude)
    to_pos = position(mission.destination_lat if mission.destination_lat is not None else to_ap.latitude,
                      mission.destination_lon if mission.destination_lon is not None else to_ap.longitude)
    root = ET.Element('SimBase.Document', {'Type':'AceXML', 'version':'1,0'})
    ET.SubElement(root,'Descr').text='AceXML Document'
    fp = ET.SubElement(root,'FlightPlan.FlightPlan')
    fields={'Title':f'{mission.origin} to {mission.destination}', 'FPType':'VFR',
            'CruisingAlt':str(cruising_altitude_ft), 'DepartureID':mission.origin,
            'DepartureLLA':from_pos, 'DestinationID':mission.destination, 'DestinationLLA':to_pos,
            'Descr':f'{mission.origin} to {mission.destination}',
            'DepartureName':from_ap.name if from_ap else mission.origin,
            'DestinationName':to_ap.name if to_ap else mission.destination}
    for k,v in fields.items():
        ET.SubElement(fp,k).text=v
    ET.SubElement(ET.SubElement(fp,'AppVersion'),'AppVersionMajor').text='10'
    for icao, world in ((mission.origin,from_pos),(mission.destination,to_pos)):
        wp=ET.SubElement(fp,'ATCWaypoint',{'id':icao})
        ET.SubElement(wp,'ATCWaypointType').text='Airport'
        ET.SubElement(wp,'WorldPosition').text=world
        ET.SubElement(ET.SubElement(wp,'ICAO'),'ICAOIdent').text=icao
    # Pontos USER coordenados; não inferir ICAO ou procedimentos de navegação.
    stops = list(waypoints or ())
    if len(stops) > 8:
        raise ValueError('Máximo de oito pontos intermediários.')
    for fix in stops:
        from math import isfinite
        if not isinstance(fix, dict) or set(fix) != {'label', 'lat', 'lon'}:
            raise ValueError('Formato de waypoint inválido.')
        label = fix['label']
        if not isinstance(label, str) or not re.fullmatch(r'[A-Z0-9_-]{1,12}', label):
            raise ValueError('Nome de waypoint inválido.')
        lat, lon = fix['lat'], fix['lon']
        if type(lat) not in (float, int) or type(lon) not in (float, int) or not (
                isfinite(lat) and isfinite(lon)):
            raise ValueError('Waypoint sem coordenadas válidas.')
        world = position(lat, lon)
        waypoint = ET.Element('ATCWaypoint', {'id':label})
        ET.SubElement(waypoint, 'ATCWaypointType').text = 'User'
        ET.SubElement(waypoint, 'WorldPosition').text = world
        # Inserir entre os dois ATCWaypoint aeroportuários.
        fp.insert(list(fp).index(fp.findall('ATCWaypoint')[-1]), waypoint)
    return ET.tostring(root, encoding='utf-8',xml_declaration=True)


def export_vfr_plan(mission: Mission, directory: str | Path, cruising_altitude_ft: int = 2500, *, waypoints=None) -> Path:
    data=build_vfr_plan(mission,cruising_altitude_ft,waypoints=waypoints)
    folder=Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    # O identificador fica fora do nome do arquivo para evitar path traversal.
    path=folder / f'FlightSimCarreira_{mission.origin}_{mission.destination}.pln'
    path.write_bytes(data)
    return path.resolve()
