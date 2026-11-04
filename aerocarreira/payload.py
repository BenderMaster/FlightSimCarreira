"""Manifesto e alocação conservadora de carga do MSFS 2020.

Esta versão NÃO substitui piloto ou passageiros já existentes nas estações.
Exige estação vazia, simulação em solo e margem para MTOW.
"""
from __future__ import annotations
from math import isfinite

KG_TO_LBS = 2.20462262185

def choose_station(stations: dict[str,float] | None, count: int | None) -> int | None:
    if not isinstance(count,int) or count<2 or count>15 or not stations:
        return None
    # Estação 1 costuma ser piloto; nunca a modificar. Só estação vazia.
    for i in range(count,1,-1):
        value=stations.get(str(i))
        if isinstance(value,(int,float)) and isfinite(value) and 0<=value<=1:
            return i
    return None

def assess_payload(mission, sample, expected_model):
    if not sample or not sample.on_ground:
        raise ValueError('Carregamento somente no solo com leitura atualizada.')
    if not expected_model:
        raise ValueError('Modelo da aeronave não identificado.')
    from .contracts import aircraft_model
    if aircraft_model(sample.aircraft_title)!=expected_model:
        raise ValueError('Modelo do MSFS não corresponde à aeronave da missão.')
    kg=mission.payload_kg
    if not isinstance(kg,(int,float)) or not isfinite(kg) or not 0<kg<=1000:
        raise ValueError('Missão sem peso de carga confiável.')
    count=sample.payload_station_count
    station=choose_station(sample.payload_station_weights,count)
    if station is None:
        raise ValueError('Nenhuma estação de carga vazia disponível; ajuste os ocupantes no MSFS.')
    gross=sample.total_weight_lbs
    mtow=sample.max_gross_weight_lbs
    if any(x is None or not isinstance(x,(int,float)) or not isfinite(x) for x in (gross,mtow)):
        raise ValueError('Peso atual e MTOW não foram fornecidos pelo simulador.')
    add_lbs=kg*KG_TO_LBS
    if gross+add_lbs>mtow-1:
        raise ValueError(f'Carga ultrapassaria MTOW: {gross+add_lbs:.0f} > {mtow:.0f} lb. Reduza combustível ou carga.')
    return dict(station=station,weight_lbs=round(add_lbs,2),
                mission_id=mission.id,expected_model=expected_model,
                original_lbs=sample.payload_station_weights[str(station)],
                before_gross_lbs=gross,mtow_lbs=mtow,manifest=mission.manifest)
