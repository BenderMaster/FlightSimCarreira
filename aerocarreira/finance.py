"""Economia fictícia em BRL para FlightSimCarreira.

Não faz conversão cambial ou cálculos de custo de aviação real. Valores são
unidades do jogo denominadas em reais (R$); cálculo em inteiros para ledger.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite


def brl(amount: int | float) -> str:
    value = int(round(amount))
    sign = '-' if value < 0 else ''
    return f'{sign}R$ {abs(value):,}'.replace(',', '.')


@dataclass(frozen=True)
class PlaneEconomy:
    code: str
    title: str
    purchase_price: int
    fuel_capacity_gal: float
    fuel_lph: float  # litros/hora fictícios, só para estimativas
    cruise_kts: float
    turnaround_fee: int
    hourly_wear: float
    service_cost: int
    insurance_price: int


AIRCRAFT_ECONOMY = {
    'c152': PlaneEconomy('c152', 'Cessna 152', 80000, 26, 23, 90, 65, 1.20, 750, 220),
    'c172': PlaneEconomy('c172', 'Cessna 172 Skyhawk', 145000, 53, 34, 112, 90, 1.1, 1000, 400),
    'g58': PlaneEconomy('g58', 'Baron G58', 480000, 194, 105, 175, 200, 1.6, 4200, 1300),
    'kingair': PlaneEconomy('kingair', 'King Air 350i', 1450000, 539, 360, 260, 550, 1.5, 12500, 3600),
    'cj4': PlaneEconomy('cj4', 'Citation CJ4', 3100000, 870, 780, 340, 850, 1.2, 22000, 7800),
}

# Cotação artificial de combustível no jogo, NÃO preço de posto real.
FUEL_BRL_PER_LITER = 7
LITERS_PER_GALLON = 3.785411784


def estimated_minutes(distance_nm: float, cruise_kts: float = 90) -> int:
    if not isfinite(distance_nm) or distance_nm < 0 or cruise_kts <= 0:
        raise ValueError('Distância ou velocidade inválida')
    return max(8, round((distance_nm / cruise_kts) * 60 + 5))


def market_reward(distance_nm: float, multiplier: float = 1.0, *, freelance: bool = False,
                  cruise_kts: float = 90, level: int = 1,
                  reputation: float = 50) -> int:
    """Referência: ~R$1500 por 20min, curta distância atrativa.

    Freelancer não possui ativo nem despesas de combustível do contratante;
    recebe honorários entre ~70-80% do valor bruto da tarefa.
    """
    if multiplier <= 0 or not isfinite(multiplier):
        raise ValueError('Multiplicador inválido')
    minutes = estimated_minutes(distance_nm, cruise_kts)
    # Valor cotado ANTES do aceite, persistido na oferta e no contrato.
    # No nível 1 com reputação neutra preservamos a tarifa de referência.
    if not isfinite(float(reputation)):
        raise ValueError("Reputação inválida")
    career_level = max(1, min(15, int(level)))
    score = max(0.0, min(100.0, float(reputation)))
    level_factor = 1.0 + 0.20 * (career_level - 1)
    reputation_factor = 0.75 + 0.005 * score
    # Rotas curtas: valorização do serviço, sem gratificar voo fictício.
    short_haul = 1.0
    if career_level >= 2:
        short_haul += 0.40 * max(0.0, (75.0 - distance_nm) / 75.0)
    gross = max(1050, 550 + 48 * minutes) * multiplier
    gross *= level_factor * reputation_factor * short_haul
    if freelance:
        gross *= .78
    return int(round(gross / 10) * 10)


def mission_radius_by_level(level: int) -> float:
    if level <= 2:
        return 55.0
    if level <= 5:
        return 90.0
    if level <= 9:
        return 130.0
    return 190.0


def flight_operating_cost(model_code: str | None, duration_s: float,
                          fuel_start: float | None, fuel_end: float | None,
                          insured: bool = False) -> dict:
    """Cobrança de custos operacionais apenas para aeronave própria cadastrada.

    O combustível é faturado pelo uso observado; se SimConnect não trouxe dados
    úteis, estima-se pelo tempo de voo. Não presume litros se há leitura negativa.
    """
    plane = AIRCRAFT_ECONOMY.get(model_code or '')
    if plane is None:
        return {'fuel_brl': 0, 'airport_brl': 0, 'insurance_brl': 0,
                'wear': 0.0, 'fuel_estimated': False, 'used_liters': 0.0}
    if duration_s < 0 or not isfinite(duration_s):
        raise ValueError('Duração inválida')
    hours = min(duration_s / 3600, 24.0)
    measured = (fuel_start is not None and fuel_end is not None and
                all(isfinite(v) for v in (fuel_start, fuel_end)) and
                0 <= fuel_end <= fuel_start <= plane.fuel_capacity_gal * 1.02)
    used_liters = ((fuel_start - fuel_end) * LITERS_PER_GALLON if measured else
                   plane.fuel_lph * hours)
    return {'fuel_brl': round(used_liters * FUEL_BRL_PER_LITER),
            'airport_brl': plane.turnaround_fee,
            'insurance_brl': 0,  # seguro: pago ao contratar, não por voo
            'wear': round(hours * plane.hourly_wear, 4),
            'fuel_estimated': not measured,
            'used_liters': round(used_liters, 2)}
