"""Reputação virtual calculada exclusivamente do diário de bordo persistido.

Começa neutra (50/100). Não altera XP, dinheiro ou o desempenho da aeronave.
Voos antigos entram no cálculo; UNIQUE(flight_key) impede crédito duplicado.
"""
from __future__ import annotations
from math import isfinite


def reputation_from_flights(rows) -> dict:
    """rows: (reward, stall_warnings, touchdown_fpm_est) persistidos."""
    score = 50
    count = 0
    for reward, stalls, touchdown in rows:
        count += 1
        score += 1
        if reward is not None and int(reward) > 0:
            score += 2
        score -= 6 * min(4, max(0, int(stalls or 0)))
        try:
            descent = abs(float(touchdown))
        except (ValueError, TypeError, OverflowError):
            continue
        if not isfinite(descent):
            continue
        if descent >= 650:
            score -= 5
        elif descent >= 400:
            score -= 2
    score = max(0, min(100, score))
    return {'score': score, 'flights_scored': count,
            'band': 'good' if score >= 70 else 'neutral' if score >= 45 else
                    'warning' if score >= 25 else 'critical'}


def pilot_reputation(conn) -> dict:
    return reputation_from_flights(conn.execute(
        'SELECT reward, stall_warnings, touchdown_fpm_est FROM flights ORDER BY id'))
