"""Verificações de realismo feitas apenas com evidência SimConnect.

O MSFS 2020 não expõe o nome do preset meteorológico por SimConnect externo,
nem todos os itens da tela de assistências. Relógio sincronizado não prova
o preset "tempo real"; a interface apresenta só sincronismo observado.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite


def real_clock_verified(sample, wall_utc=None):
    zulu=sample.zulu_time_s
    rate=sample.sim_rate
    if zulu is None or rate is None or not (isfinite(zulu) and isfinite(rate)):
        return None
    if not 0.99 <= rate <= 1.01:
        return False
    now=datetime.now(timezone.utc) if wall_utc is None else wall_utc
    seconds=now.hour*3600+now.minute*60+now.second
    delta=abs((zulu%86400)-seconds)
    return min(delta,86400-delta)<=120


def assistance_verified(sample):
    required=(sample.assistance_landing,sample.assistance_takeoff,sample.ai_controls)
    if any(v is True for v in required) or sample.unlimited_fuel is True:
        return False
    if any(v is None for v in required) or sample.unlimited_fuel is None:
        return None
    return True


def flight_safety_xp(tracker, touchdown_fpm):
    """XP de desempenho: máximo +7 ou -15, somente ao registrar o pouso."""
    valid_touchdown=(touchdown_fpm is not None and isfinite(touchdown_fpm)
                     and -150.0 < touchdown_fpm < 0.0)
    smooth=4 if valid_touchdown and tracker.go_arounds==0 else 0
    lights=(int(tracker.light_beacon_taxi_ok)+int(tracker.light_taxi_ok)
            +int(tracker.light_landing_approach_ok))
    deductions=(3*min(2,tracker.stalls)+2*min(2,tracker.hard_g_events)
                +2*min(2,tracker.taxi_violations)
                +2*int(tracker.light_landing_approach_off)
                +int(tracker.light_beacon_taxi_off))
    return max(-15,min(7,smooth+lights-deductions))
