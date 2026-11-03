"""Regras locais da carreira de piloto (habilitações fictícias, não licenças ANAC)."""
from __future__ import annotations
from dataclasses import dataclass
import re
from .contracts import pilot_level, next_level_xp


@dataclass(frozen=True)
class Qualification:
    code: str
    title: str
    description: str
    flights: int
    xp: int
    prerequisites: tuple[str, ...] = ()
    hours: float = 0.0


QUALIFICATIONS = (
    Qualification("PPA", "Piloto Privado — avião (virtual)",
                  "Habilitação inicial para voos VFR simples no jogo.", 0, 0),
    Qualification("PCA", "Piloto Comercial — avião (virtual)",
                  "Abre caminho para contratos comerciais avançados.", 8, 160, ("PPA",), 10.0),
    Qualification("IFR", "Instrumentos (virtual)",
                  "Etapa futura de operações sob regras de voo por instrumentos.", 16, 320, ("PPA",), 20.0),
    Qualification("MLTE", "Multimotor terrestre (virtual)",
                  "Etapa futura para aeronaves multimotor.", 24, 450, ("PCA",), 30.0),
    Qualification("PLA", "Piloto de Linha Aérea (virtual)",
                  "Marco avançado de progressão no FlightSimCarreira.", 50, 1500,
                  ("PCA", "IFR", "MLTE"), 60.0),
)
QUAL_BY_CODE = {q.code: q for q in QUALIFICATIONS}


def validate_pilot(name: str, callsign: str, home_icao: str) -> tuple[str, str, str]:
    if any(ord(c) < 32 for c in name):
        raise ValueError("Nome do piloto contém caracteres de controle.")
    name = " ".join(name.strip().split())
    callsign = callsign.strip().upper()
    home_icao = home_icao.strip().upper()
    if not (2 <= len(name) <= 50) or any(ord(c) < 32 for c in name):
        raise ValueError("Nome do piloto: informe entre 2 e 50 caracteres válidos.")
    if not re.fullmatch(r"[A-Z0-9-]{3,12}", callsign):
        raise ValueError("Indicativo: use 3 a 12 letras, números ou hífen.")
    if not re.fullmatch(r"[A-Z]{4}", home_icao):
        raise ValueError("Base: informe um código ICAO de quatro letras (ex.: SBRF).")
    return name, callsign, home_icao


def qualification_eligibility(code: str, owned: set[str], flights: int,
                              xp: int, hours: float = 0.0) -> tuple[bool, str]:
    if code not in QUAL_BY_CODE:
        raise ValueError("Habilitação desconhecida.")
    if code in owned:
        return False, "Já obtida"
    q = QUAL_BY_CODE[code]
    missing = [p for p in q.prerequisites if p not in owned]
    reasons = []
    if missing:
        reasons.append("pré-requisito: " + ", ".join(missing))
    if hours + 1e-9 < q.hours:
        reasons.append(f"horas {hours:.1f}/{q.hours:g} h")
    if flights < q.flights:
        reasons.append(f"voos {flights}/{q.flights}")
    if xp < q.xp:
        reasons.append(f"XP {xp}/{q.xp}")
    return (not reasons, "Disponível" if not reasons else "Falta " + "; ".join(reasons))


def flight_xp(reward: int) -> int:
    """Pontua completar voos; pousos excessivamente suaves não recebem bônus."""
    return 25 + (15 if reward > 0 else 0)


def progress_fraction(current: float, target: float) -> float:
    """Percentual limitado entre 0 e 1; metas nulas já estão cumpridas."""
    if target <= 0:
        return 1.0
    return min(1.0, max(0.0, float(current) / float(target)))


def level_progress(xp: int) -> dict:
    """Faixa do nível ATUAL, não XP total desde o nível 1.

    Interface pode exibir percentual sem expor XP numérico no cabeçalho.
    """
    xp = max(0, int(xp))
    level = pilot_level(xp)
    if level >= 100:
        return {"level": level, "next_level": None, "fraction": 1.0, "remaining": 0}
    start = 0 if level == 1 else next_level_xp(level - 1)
    finish = next_level_xp(level)
    return {"level": level, "next_level": level + 1,
            "fraction": progress_fraction(xp - start, finish - start),
            "remaining": max(0, finish - xp)}
