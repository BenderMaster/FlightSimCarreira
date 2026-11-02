"""Regras locais da carreira de piloto (habilitações fictícias, não licenças ANAC)."""
from __future__ import annotations
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Qualification:
    code: str
    title: str
    description: str
    flights: int
    xp: int
    prerequisites: tuple[str, ...] = ()


QUALIFICATIONS = (
    Qualification("PPA", "Piloto Privado — avião (virtual)",
                  "Habilitação inicial para voos VFR simples no jogo.", 0, 0),
    Qualification("PCA", "Piloto Comercial — avião (virtual)",
                  "Abre caminho para contratos comerciais avançados.", 4, 160, ("PPA",)),
    Qualification("IFR", "Instrumentos (virtual)",
                  "Etapa futura de operações sob regras de voo por instrumentos.", 8, 320, ("PPA",)),
    Qualification("MLTE", "Multimotor terrestre (virtual)",
                  "Etapa futura para aeronaves multimotor.", 10, 450, ("PCA",)),
    Qualification("PLA", "Piloto de Linha Aérea (virtual)",
                  "Marco avançado de progressão no FlightSimCarreira.", 25, 1500,
                  ("PCA", "IFR", "MLTE")),
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
                              xp: int) -> tuple[bool, str]:
    if code not in QUAL_BY_CODE:
        raise ValueError("Habilitação desconhecida.")
    if code in owned:
        return False, "Já obtida"
    q = QUAL_BY_CODE[code]
    missing = [p for p in q.prerequisites if p not in owned]
    reasons = []
    if missing:
        reasons.append("pré-requisito: " + ", ".join(missing))
    if flights < q.flights:
        reasons.append(f"voos {flights}/{q.flights}")
    if xp < q.xp:
        reasons.append(f"XP {xp}/{q.xp}")
    return (not reasons, "Disponível" if not reasons else "Falta " + "; ".join(reasons))


def flight_xp(reward: int) -> int:
    """Pontua completar voos; pousos excessivamente suaves não recebem bônus."""
    return 25 + (15 if reward > 0 else 0)
