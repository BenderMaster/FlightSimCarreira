"""Despacho pré-voo, verificações e bônus de realismo.

Verificações manuais são explicitamente DECLARADAS; não atribuir evidência do
MSFS ao estado de clima real/horário, pois SimConnect não o comprova aqui.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import isfinite
from .domain import Mission, distance_nm
from .finance import AIRCRAFT_ECONOMY, LITERS_PER_GALLON, estimated_minutes
from .contracts import aircraft_model


def aircraft_title_matches(planned: str | None, actual: str | None) -> bool:
    """Reconhece variantes do SimConnect sem aceitar modelos diferentes.

    O título do MSFS contém fabricante/pintura e nem sempre é idêntico
    ao título escolhido no despacho (ex. Cessna 152 vs Textron Cessna 152).
    """
    if not planned or not actual:
        return False
    if planned.strip().casefold() == actual.strip().casefold():
        return True
    planned_code, actual_code = aircraft_model(planned), aircraft_model(actual)
    return planned_code is not None and planned_code == actual_code


@dataclass(frozen=True)
class Preflight:
    mission_id: str
    aircraft_title: str
    real_weather_declared: bool = False
    real_time_declared: bool = False
    assists_realistic_declared: bool = False
    runway_checked: bool = False
    route_checked: bool = False
    fuel_checked: bool = False
    payload_checked: bool = False
    planned_fuel_gal: float | None = None
    planned_weight_lbs: float | None = None
    max_weight_lbs: float | None = None
    altitude_ft: int = 2500
    planned_distance_nm: float | None = None

    def snapshot(self):
        return asdict(self)


def inspect_preflight(mission: Mission, data: Preflight, cruise_kts: float = 90.0,
                      verified: dict | None = None) -> dict:
    if data.mission_id != mission.id:
        raise ValueError('Plano não corresponde ao contrato ativo.')
    if not (500 <= data.altitude_ft <= 45000):
        raise ValueError('Altitude planejada inválida')
    distance = None
    if None not in (mission.origin_lat, mission.origin_lon,mission.destination_lat,mission.destination_lon):
        distance = distance_nm(mission.origin_lat, mission.origin_lon,mission.destination_lat,mission.destination_lon)
    else:
        from .domain import AIRPORTS
        a,b = AIRPORTS.get(mission.origin),AIRPORTS.get(mission.destination)
        if a and b:
            distance = distance_nm(a.latitude,a.longitude,b.latitude,b.longitude)
    if data.planned_distance_nm is not None:
        planned = data.planned_distance_nm
        if type(planned) not in (float,int) or not isfinite(planned) or planned < 0:
            raise ValueError('Distância planejada inválida')
        # Desvios via waypoint aumentam a estimativa; nunca diminuem
        # a distância geodésica do contrato em busca de bônus.
        distance = max(distance or 0, planned)
    aircraft_code = aircraft_model(data.aircraft_title)
    if aircraft_code in AIRCRAFT_ECONOMY:
        cruise_kts = AIRCRAFT_ECONOMY[aircraft_code].cruise_kts
    minutes = estimated_minutes(distance, cruise_kts) if distance is not None else None
    model = AIRCRAFT_ECONOMY.get(aircraft_code or '')
    fuel_required = (model.fuel_lph * minutes / 60 / LITERS_PER_GALLON * 1.35) if model and minutes else None
    fuel_ok = bool(data.fuel_checked and data.planned_fuel_gal is not None and
                   isfinite(data.planned_fuel_gal) and data.planned_fuel_gal > 0 and
                   fuel_required is not None and data.planned_fuel_gal >= fuel_required and
                   data.planned_fuel_gal <= model.fuel_capacity_gal * 1.02)
    weight_ok = bool(data.payload_checked and data.planned_weight_lbs is not None and
                     data.max_weight_lbs is not None and isfinite(data.planned_weight_lbs) and
                     isfinite(data.max_weight_lbs) and 0 < data.planned_weight_lbs <= data.max_weight_lbs)
    # Preset meteorológico e opções globais NÃO são comprovados pelo
    # SimConnect externo. Declarações NÃO pontuam como dados automáticos.
    checked=verified or {}
    components = {
        # Nenhuma seleção ou prêmio de clima real: preset não verificável.
        'Relógio UTC sincronizado (telemetria)':(.03, checked.get('clock') is True),
        'Assistência de voo desativada (telemetria)':(.03, checked.get('assists') is True),
        'Pista e iluminação conferidas (declaração)':(.02, data.runway_checked),
        'Rota revisada (declaração)':(.02, data.route_checked),
        'Combustível e reserva conferidos (telemetria/estimativa)':(.025, fuel_ok),
        'Peso abaixo do MTOW (telemetria)':(.025, weight_ok),
    }
    bonus = round(sum(rate for rate, ok in components.values() if ok),4)
    return {'minutes':minutes, 'distance_nm':round(distance,1) if distance is not None else None,
            'fuel_required_gal':round(fuel_required,1) if fuel_required is not None else None,
            'fuel_ok':fuel_ok, 'weight_ok':weight_ok,
            'components': {key:{'rate':rate,'ok':bool(ok)} for key,(rate,ok) in components.items()},
            'bonus_fraction':bonus, 'manual_verified':False}
