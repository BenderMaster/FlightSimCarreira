"""Preparação de carga/passageiro em estações de peso do MSFS 2020.

Nunca escreve antes de calcular o peso total e manter o piloto da estação 1.
A detecção da estação é opcional; se indisponível, bloqueia com erro explícito.
"""
from __future__ import annotations
from math import isfinite
from .domain import FlightSample, Mission

LB_PER_KG=2.20462262185
FUEL_KG_PER_LITER=.72


def load_plan(sample: FlightSample, mission: Mission):
    if not sample.on_ground:
        raise ValueError('A aeronave deve estar no solo para preparar passageiros e carga.')
    if mission.payload_kg<=0 or not isfinite(mission.payload_kg) or mission.payload_kg>650:
        raise ValueError('Manifesto sem peso válido.')
    stations=sample.payload_station_weights
    count=sample.payload_station_count
    if not isinstance(stations,dict) or not count or count<2:
        raise ValueError('O MSFS ainda não informou as estações de peso desta aeronave.')
    if not all(i in stations and isfinite(stations[i]) and stations[i]>=0 for i in range(1,count+1)):
        raise ValueError('Pesos das estações incompletos; carregamento cancelado.')
    if sample.total_weight_lbs is None or sample.max_gross_weight_lbs is None:
        raise ValueError('MSFS não informou peso atual e MTOW.')
    if not (isfinite(sample.total_weight_lbs) and isfinite(sample.max_gross_weight_lbs)
            and 0<sample.total_weight_lbs<350000 and 0<sample.max_gross_weight_lbs<350000):
        raise ValueError('Peso ou MTOW inválido.')
    # Mantém estação 1 (piloto). As demais estações são controladas pela
    # missão; nenhuma escrita é feita se a soma ultrapassar limites.
    target={i:0.0 for i in range(2,count+1)}
    cargo_lbs=mission.payload_kg*LB_PER_KG
    per=cargo_lbs/len(target)
    for index in target:target[index]=round(per,3)
    old_aux=sum(stations[i] for i in target)
    new_total=sample.total_weight_lbs-old_aux+sum(target.values())
    if new_total>sample.max_gross_weight_lbs-1:
        raise ValueError('Excesso de peso: %.1f lb projetados para MTOW %.1f lb. Reduza o combustível no abastecimento.'%(new_total,sample.max_gross_weight_lbs))
    if new_total<=0:
        raise ValueError('Distribuição de peso inconsistentes com a aeronave.')
    return {'stations':target,'total_lbs':round(new_total,1),
            'max_lbs':sample.max_gross_weight_lbs,
            'payload_kg':mission.payload_kg,
            'remaining_lbs':round(sample.max_gross_weight_lbs-new_total,1)}


def load_confirmed(observed, expected, tolerance_lbs=1.5):
    if not isinstance(observed,dict) or not expected:return False
    # Amostras podem ser serializadas em JSON e recuperar índices como string.
    return all((index in observed or str(index) in observed) and
        abs(float(observed.get(index,observed.get(str(index))))-value)<=tolerance_lbs
        for index,value in expected.items())
