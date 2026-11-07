"""Mercado regional, elegibilidade de contratos e propostas freelancer.

Somente contratos próximos ao avião são materializados. Catálogo externo: airportsdata
(MIT); dados locais mínimos independentes da disponibilidade do pacote.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import isfinite
from random import Random
import hashlib
from .domain import Airport, AIRPORTS, Mission, distance_nm
from .finance import market_reward, mission_radius_by_level, AIRCRAFT_ECONOMY
from .manifest import mission_manifest


@dataclass(frozen=True)
class ContractType:
    code: str
    title: str
    min_level: int
    qualifications: tuple[str, ...]
    min_hours: float
    pay_factor: float
    min_nm: float = 5.0
    max_nm: float = 180.0


TYPES = (
    ContractType("cargo", "Carga leve", 1, ("PPA",), 0, 1.0),
    ContractType("tourism", "Voo turístico", 2, ("PPA",), 0.25, 1.20, 5, 90),
    ContractType("passenger", "Transporte de passageiros", 2, ("PPA",), 0.25, 1.35),
    ContractType("airtaxi", "Táxi aéreo", 3, ("PCA",), 0.7, 1.65),
    ContractType("humanitarian", "Ajuda humanitária", 4, ("PCA",), 1, 1.65),
    ContractType("medical", "Transporte médico", 6, ("PCA",), 2.0, 2.4),
    ContractType("executive", "Voo executivo", 8, ("PCA", "IFR"), 3.0, 2.9),
    ContractType("rescue", "Busca e resgate", 10, ("PCA", "IFR"), 5.0, 3.4, 5, 120),
    ContractType("special", "Operação especial", 12, ("PLA",), 8.0, 4.3),
)
TYPE_BY_CODE = {t.code: t for t in TYPES}


# Os modelos são sugestões de aeronaves disponibilizadas pelo contratante, não
# uma alteração automática do inventário/estado da aeronave no simulador.
@dataclass(frozen=True)
class EmployerPlane:
    code: str
    name: str
    keywords: tuple[str, ...]
    min_level: int
    qualifications: tuple[str, ...]
    min_hours: float
    min_family_flights: int
    family: str
    min_model_flights: int = 0


EMPLOYER_FLEET = (
    EmployerPlane("c152", "Cessna 152", ("cessna 152", "c152"), 1, ("PPA",), 0.0, 0, "single"),
    EmployerPlane("c172", "Cessna 172 Skyhawk", ("cessna 172", "skyhawk", "c172"), 2, ("PPA",), 0.25, 1, "single"),
    EmployerPlane("g58", "Beechcraft Baron G58", ("baron", "g58"), 6, ("MLTE",), 2.0, 3, "twin", 1),
    EmployerPlane("kingair", "Beechcraft King Air 350i", ("king air", "kingair"), 8, ("PCA", "IFR", "MLTE"), 4.0, 3, "turboprop", 1),
    EmployerPlane("cj4", "Cessna Citation CJ4", ("citation cj4", "cj4"), 11, ("PCA", "IFR", "MLTE"), 7.0, 3, "jet", 1),
)
FREELANCER_FLEET = EMPLOYER_FLEET
from .type_ratings import TYPES as AIRLINE_TYPES, detect_model
# Modelos das companhias mantidos separados das cinco aeronaves clássicas.
EMPLOYER_FLEET = EMPLOYER_FLEET + tuple(
    EmployerPlane(p.code, p.title, (p.code,), 5,
                  ("PCA","IFR") if p.family=="jet" else ("PCA",),
                  0.0, 0, p.family) for p in AIRLINE_TYPES)
PLANE_BY_CODE = {p.code: p for p in EMPLOYER_FLEET}


def aircraft_model(title: str | None) -> str | None:
    if not title:
        return None
    airline_code=detect_model(title)
    if airline_code:
        return airline_code
    title = title.casefold()
    for plane in EMPLOYER_FLEET:
        if any(token in title for token in plane.keywords):
            return plane.code
    return None


def aircraft_family(title: str | None) -> str | None:
    model = aircraft_model(title)
    return PLANE_BY_CODE[model].family if model else None


def matches_aircraft(title: str | None, plane_code: str | None) -> bool:
    plane = PLANE_BY_CODE.get(plane_code or "")
    return bool(plane and aircraft_model(title)==plane.code)


def pilot_level(xp: int) -> int:
    """Crescimento moderadamente não linear; nível inicial 1, sem teto arbitrário."""
    level = 1
    while xp >= (100 * level + 15 * level * level) and level < 100:
        level += 1
    return level


def next_level_xp(level: int) -> int:
    return 100 * level + 15 * level * level


def eligibility(mission: Mission, stats: dict, qualifications: set[str],
                family_flights: dict[str, int] | None = None) -> tuple[bool, str]:
    if mission.category == "legacy":
        return True, "Contrato legado"
    kind = TYPE_BY_CODE.get(mission.category)
    if kind is None:
        return False, "Tipo de missão desconhecido"
    level = pilot_level(int(stats.get("xp", 0)))
    missing = [q for q in kind.qualifications if q not in qualifications]
    reasons = []
    if level < kind.min_level:
        reasons.append(f"nível {kind.min_level} (atual {level})")
    if float(stats.get("hours", 0)) < kind.min_hours:
        reasons.append(f"{kind.min_hours:g} h de voo")
    if missing:
        reasons.append("habilitação " + ", ".join(missing))
    if mission.freelance:
        plane = PLANE_BY_CODE.get(mission.employer_plane or "")
        if plane is None:
            return False, "Aeronave do contratante não cadastrada"
        if level < plane.min_level:
            reasons.append(f"nível {plane.min_level} para {plane.name}")
        if float(stats.get("hours", 0)) < plane.min_hours:
            reasons.append(f"{plane.min_hours:g} h para {plane.name}")
        absent = [q for q in plane.qualifications if q not in qualifications]
        if absent:
            reasons.append("habilitação aeronave: " + ", ".join(absent))
        if (family_flights or {}).get(plane.family, 0) < plane.min_family_flights:
            reasons.append(f"experiência {plane.family}: {plane.min_family_flights} voos")
        if (family_flights or {}).get(plane.code, 0) < plane.min_model_flights:
            reasons.append(f"experiência no modelo {plane.name}: {plane.min_model_flights} voo(s)")
    return not reasons, "Disponível" if not reasons else "Falta " + "; ".join(reasons)


class AirportCatalog:
    """Catálogo de aeroportos: airportsdata, quando instalado, mais fallback local.

    Importa coordenadas públicas; NÃO garante que o aeroporto exista na instalação
    do MSFS. Dados aeronáuticos e iluminação devem ser validados separadamente.
    """
    def __init__(self, locations: dict[str, Airport] | None = None):
        self.locations: dict[str, Airport] = {}
        self.global_catalog = False
        if locations is not None:
            self.locations.update(locations)
            self.global_catalog = True
        else:
            try:
                import airportsdata
                data = airportsdata.load("ICAO")
                for code, record in data.items():
                    if (len(code) == 4 and code.isalpha() and
                        isinstance(record.get("lat"), (int, float)) and
                        isinstance(record.get("lon"), (int, float))):
                        lat, lon = float(record["lat"]), float(record["lon"])
                        if isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                            self.locations[code.upper()] = Airport(code.upper(), record.get("name", code), lat, lon)
                self.global_catalog = bool(self.locations)
            except (ImportError, OSError, ValueError, KeyError):
                pass
        self.locations.update(AIRPORTS)  # parâmetros testados localmente prevalecem

    def nearest(self, lat: float, lon: float, max_nm: float = 5.0) -> Airport | None:
        if not isfinite(lat) or not isfinite(lon):
            return None
        candidates = ((distance_nm(lat, lon, a.latitude, a.longitude), a) for a in self.locations.values())
        nearest_distance, closest = min(candidates, key=lambda item: item[0], default=(float('inf'), None))
        return closest if nearest_distance <= max_nm else None

    def around(self, origin: Airport, max_nm: float = 180.0) -> list[tuple[Airport, float]]:
        around = []
        for ap in self.locations.values():
            if ap.icao == origin.icao:
                continue
            if abs(ap.latitude - origin.latitude) > max_nm / 55:
                continue
            d = distance_nm(origin.latitude, origin.longitude, ap.latitude, ap.longitude)
            if 5 <= d <= max_nm:
                around.append((ap, d))
        return sorted(around, key=lambda x: (x[1], x[0].icao))



# Recorte geográfico aproximado do Nordeste brasileiro; não é limite legal de
# estados. Usar ICAO brasileiro e alcance por modelo evita rotas globais irreais.
_NORDESTE_POLYGON=((-45.9,-1.0),(-42.0,-1.0),(-38.0,-2.0),
    (-34.0,-4.0),(-34.0,-11.3),(-37.7,-14.4),(-39.0,-18.5),
    (-41.7,-19.0),(-45.3,-16.1),(-46.8,-12.2),(-48.2,-7.0),
    (-47.5,-3.5))

def northeast_airport(airport: Airport) -> bool:
    """Ponto aproximado em Nordeste; depende de catálogo com ICAO/coord válidos."""
    if not airport.icao.startswith('S') or len(airport.icao)!=4:
        return False
    x,y=airport.longitude,airport.latitude
    vertices=_NORDESTE_POLYGON
    inside=False
    for i in range(len(vertices)):
        ax,ay=vertices[i]
        bx,by=vertices[(i+1)%len(vertices)]
        if (ay>y)!=(by>y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside=not inside
    return inside

def freelance_range_nm(model_code: str) -> float:
    """Estimativa conservadora com 30% de reserva do tanque no motor do jogo."""
    p=AIRCRAFT_ECONOMY[model_code]
    endurance_h=p.fuel_capacity_gal*3.785411784/p.fuel_lph
    return round(min(1300,endurance_h*p.cruise_kts*.70),1)

def generate_offers(origin: Airport, catalog: AirportCatalog, stats: dict,
                    qualifications: set[str], family_flights: dict[str, int],
                    period: int, max_regional: int = 10, max_freelance: int = 6) -> list[Mission]:
    """Regional permanece local; Freelancer procura o Nordeste por alcance realista.

    Ambas modalidades partem do aeroporto de posição/base do piloto, pois
    aceitar a missão requer estar em solo na origem (sem teleporte).
    """
    choices=catalog.around(origin,mission_radius_by_level(
        int(stats.get("level",pilot_level(int(stats.get("xp",0)))))))
    broad=[(a,distance_nm(origin.latitude,origin.longitude,a.latitude,a.longitude))
           for a in catalog.locations.values() if a.icao!=origin.icao and northeast_airport(a)]
    seed = int.from_bytes(hashlib.sha256(f"{origin.icao}:{period}:nordeste-v1".encode()).digest()[:8], 'big')
    rng = Random(seed)
    reward_level = int(stats.get('level', pilot_level(int(stats.get('xp', 0)))))
    reward_rep = float(stats.get('reputation', 50))
    allowed = [t for t in TYPES if eligibility(Mission("x",origin.icao,origin.icao,"",0,
                  category=t.code),stats,qualifications,family_flights)[0]]
    offers: list[Mission] = []
    # Evita criar centenas de contratos quando somente carga está desbloqueada.
    seen: set[tuple[str,str,bool]] = set()
    for slot in range(max_regional):
        if not allowed:
            break
        kind = allowed[slot % len(allowed)]
        options = [(a,d) for a,d in choices if kind.min_nm <= d <= kind.max_nm]
        if not options:
            continue
        rng.shuffle(options)
        found = next(((a,d) for a,d in options if (kind.code,a.icao,False) not in seen), None)
        if not found:
            continue
        target, dist = found
        seen.add((kind.code,target.icao,False))
        reward = market_reward(dist, kind.pay_factor, level=reward_level, reputation=reward_rep)
        offers.append(Mission(f"REG-{origin.icao}-{period}-{slot:02}",origin.icao,target.icao,
            f"{kind.title} • {target.name[:24]}",reward,category=kind.code,
            origin_lat=origin.latitude,origin_lon=origin.longitude,
            destination_lat=target.latitude,destination_lon=target.longitude))
    allowed_planes = [p for p in FREELANCER_FLEET if eligibility(
        Mission("x",origin.icao,origin.icao,"",0,category="cargo",freelance=True,employer_plane=p.code),
        stats,qualifications,family_flights)[0]]
    freelance_kinds = [k for k in allowed if k.code not in ("rescue", "special")]
    if not freelance_kinds:
        freelance_kinds = [TYPE_BY_CODE['cargo']] if allowed_planes else []
    rng.shuffle(allowed_planes)
    rng.shuffle(freelance_kinds)
    for slot in range(max_freelance):
        if not allowed_planes or not freelance_kinds:
            break
        kind = freelance_kinds[slot % len(freelance_kinds)]
        plane = allowed_planes[slot % len(allowed_planes)]
        range_limit=freelance_range_nm(plane.code)
        choices_for_type=[(a,d) for a,d in broad if kind.min_nm<=d<=range_limit]
        if not choices_for_type:
            continue
        # Distribuir destinos pelo Nordeste em vez de somente os mais próximos.
        choices_for_type.sort(key=lambda pair:pair[1])
        bucket=min(2,slot%3)
        lo=bucket*len(choices_for_type)//3
        hi=max(lo+1,(bucket+1)*len(choices_for_type)//3)
        target,dist=rng.choice(choices_for_type[lo:hi])
        salary=market_reward(dist,1+kind.min_level*.09,freelance=True,
                             cruise_kts=AIRCRAFT_ECONOMY[plane.code].cruise_kts,
                             level=reward_level, reputation=reward_rep)
        offers.append(Mission(f"FREE-{origin.icao}-{period}-{slot:02}",origin.icao,target.icao,
            f"Freelancer • {kind.title} • {plane.name}",salary,category=kind.code,freelance=True,
            employer_plane=plane.code,origin_lat=origin.latitude,origin_lon=origin.longitude,
            destination_lat=target.latitude,destination_lon=target.longitude))
    return [mission_manifest(m) for m in offers]
