"""Carreiras virtuais: autonomia, emprego e empresa própria no endgame.

Vagas geradas para o jogo. Empresas citadas não anunciam vagas reais e não
mantêm relação comercial com FlightSimCarreira. Nenhuma marca/livery é incluída.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from random import Random
import re


@dataclass(frozen=True)
class Employer:
    code: str
    name: str
    callsign: str
    home_icao: str
    min_level: int
    min_hours: float
    qualifications: tuple[str, ...]
    plane: str
    weekly_salary: int
    real_name_reference: bool = False


EMPLOYERS = (
    Employer('nordeste', 'AeroNordeste (fictícia)', 'NORDESTE', 'SBRF', 2, 0.4, ('PPA',), 'c172', 650),
    Employer('azul', 'Azul (simulação)', 'AZUL', 'SBRF', 7, 3.0, ('PCA','IFR'), 'kingair', 2200, True),
    Employer('gol', 'GOL (simulação)', 'GLO', 'SBRF', 9, 5.0, ('PCA','IFR','MLTE'), 'cj4', 2900, True),
    Employer('latam', 'LATAM (simulação)', 'TAM', 'SBGR', 11, 8.0, ('PCA','IFR','MLTE'), 'cj4', 3600, True),
)
EMPLOYER_BY_CODE = {c.code: c for c in EMPLOYERS}


@dataclass(frozen=True)
class Vacancy:
    id: str
    company: str
    title: str
    opens_period: int
    closes_period: int
    airport: str
    plane: str
    min_level: int
    min_hours: float
    qualifications: tuple[str, ...]
    salary: int


def weekly_period(now_utc: float) -> int:
    return int(now_utc // (7 * 86400))


def vacancies(period: int, region_icao: str = 'SBRF') -> list[Vacancy]:
    """No máximo 4 vagas por semana, geradas sob demanda.

    Rendimento/status previsíveis para mesma semana; sem carregar mercados globais.
    """
    region = region_icao.upper()
    if not re.fullmatch('[A-Z0-9]{4}', region):
        raise ValueError('Região ICAO inválida.')
    rng = Random(int.from_bytes(sha256(f'jobs:{period}:{region}:v1'.encode()).digest()[:8], 'big'))
    selected = list(EMPLOYERS)
    rng.shuffle(selected)
    result = []
    for company in selected:
        post_id = f'JOB-{period}-{region}-{company.code}'
        result.append(Vacancy(post_id, company.code, f'Piloto contratado • {company.name}',
            period, period + 1, region, company.plane, company.min_level,
            company.min_hours, company.qualifications, company.weekly_salary))
    return result


def employment_eligibility(v: Vacancy, stats: dict, qualifications: set[str]) -> tuple[bool, str]:
    why = []
    if int(stats.get('level', 1)) < v.min_level:
        why.append(f'nível {v.min_level}')
    if float(stats.get('hours', 0)) < v.min_hours:
        why.append(f'{v.min_hours:g} h')
    missing = set(v.qualifications) - set(qualifications)
    if missing:
        why.append('habilitações ' + ', '.join(sorted(missing)))
    return (not why, 'Elegível' if not why else 'Requisitos: ' + '; '.join(why))


def selection_result(v: Vacancy, pilot_stats: dict, application_key: str) -> bool:
    """Seleção fictícia, estável; qualificados têm chance crescente, sem pay-to-win."""
    level_diff = max(0, int(pilot_stats.get('level',1)) - v.min_level)
    bonus = min(20, level_diff * 5)
    threshold = min(85, 55 + bonus)
    draw = int.from_bytes(sha256(f'select:{v.id}:{application_key}'.encode()).digest()[:4], 'big') % 100
    return draw < threshold


def valid_company_name(name: str) -> str:
    name = ' '.join(name.strip().split())
    if not 3 <= len(name) <= 60:
        raise ValueError('Nome da companhia: de 3 a 60 caracteres.')
    if any(ord(c) < 32 or c in '<>\\/' for c in name):
        raise ValueError('Nome contém caracteres inválidos.')
    return name


OWN_MIN_LEVEL = 18
OWN_MIN_HOURS = 25.0
OWN_INVESTMENT = 100000


def generate_employer_routes(company_code: str, origin, catalog, stats: dict,
                             qualifications: set[str], family_flights: dict[str,int], period: int):
    """Tarefas de voo locais para empregado contratado, máx. 2 por dia.

    Aeronave virtual fornecida pela companhia, não adquirida pelo usuário.
    """
    from .contracts import eligibility, mission_manifest
    from .domain import Mission
    company=EMPLOYER_BY_CODE.get(company_code)
    if company is None:
        return []
    choices=[(a,d) for a,d in catalog.around(origin,180) if 10<=d<=160]
    if not choices:
        return []
    rng=Random(int.from_bytes(sha256(f'roster:{company.code}:{origin.icao}:{period}'.encode()).digest()[:8],'big'))
    rng.shuffle(choices)
    routes=[]
    for i,(destination,distance) in enumerate(choices[:2]):
        from .finance import market_reward
        reward=market_reward(distance, max(1.0,company.min_level*.15), freelance=True)
        identifier=f'EMP-{company.code}-{origin.icao}-{period}-{i:02}'
        manifest,kg=mission_manifest('cargo',identifier,company.plane)
        m=Mission(identifier,origin.icao,destination.icao,
                  f'{company.name} • {manifest}',reward,
                  category='cargo',freelance=True,employer_plane=company.plane,
                  origin_lat=origin.latitude,origin_lon=origin.longitude,
                  destination_lat=destination.latitude,destination_lon=destination.longitude,
                  company_code=company.code,manifest=manifest,payload_kg=kg)
        if eligibility(m,stats,qualifications,family_flights)[0]:
            routes.append(m)
    return routes
