"""Domínio independente de interface, simulador e banco de dados."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from math import radians, cos, sin, asin, sqrt
from typing import Optional
from .taxi import DepartureTaxi


@dataclass(frozen=True)
class Airport:
    icao: str
    name: str
    latitude: float
    longitude: float


# Referências ARP (latitude/longitude), não pontos de toque na pista.
AIRPORTS = {
    "SBRF": Airport("SBRF", "Recife / Guararapes", -8.126388889, -34.922777778),
    "SIPE": Airport("SIPE", "Itapessoca", -7.656666667, -34.856944444),
    "SBJP": Airport("SBJP", "João Pessoa / Castro Pinto", -7.148333333, -34.950277778),
    "SIFC": Airport("SIFC", "Coroa do Avião / Igarassu", -7.844444444, -34.891388889),
}


def distance_nm(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Grande círculo; 1 MN = 1852 m. Apenas distância geométrica."""
    phi1, phi2 = radians(a_lat), radians(b_lat)
    dphi = radians(b_lat-a_lat)
    dlon = radians(b_lon-a_lon)
    h = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlon/2)**2
    return (6371008.8 * 2 * asin(min(1.0, sqrt(h)))) / 1852


@dataclass(frozen=True)
class Mission:
    id: str
    origin: str
    destination: str
    title: str
    reward: int
    category: str = "legacy"
    freelance: bool = False
    employer_plane: str | None = None
    origin_lat: float | None = None
    origin_lon: float | None = None
    destination_lat: float | None = None
    destination_lon: float | None = None
    company_code: str | None = None
    # v0.7.7: manifesto persistente no próprio contrato, retrocompatível.
    manifest_description: str = ''
    payload_kind: str = ''
    payload_kg: float = 0.0


MISSIONS = (
    Mission("REC-ITA", "SBRF", "SIPE", "Encomenda expressa", 850),
    Mission("REC-JPA", "SBRF", "SBJP", "Documentos comerciais", 1450),
    Mission("ITA-JPA", "SIPE", "SBJP", "Peças de manutenção", 1050),
    Mission("ITA-IGA", "SIPE", "SIFC", "Teste local — Coroa do Avião", 420),
)


@dataclass(frozen=True)
class FlightSample:
    timestamp: float  # segundos UTC; para testes, relógio monotônico sintético
    latitude: float
    longitude: float
    altitude_ft: float
    agl_ft: float
    ias_kt: float
    groundspeed_kt: float
    vs_fpm: float
    on_ground: bool
    engine_running: Optional[bool] = None
    fuel_gallons: Optional[float] = None
    stall_warning: Optional[bool] = None
    groundspeed_estimated: bool = False
    aircraft_title: str | None = None
    total_weight_lbs: float | None = None
    max_gross_weight_lbs: float | None = None
    wind_kt: float | None = None
    ambient_temperature_c: float | None = None
    sim_rate: float | None = None
    fuel_tanks: dict[str, float] | None = None
    fuel_tank_capacities: dict[str, float] | None = None
    unlimited_fuel: bool | None = None
    wind_direction_deg: float | None = None
    visibility_m: float | None = None
    sea_level_pressure_hpa: float | None = None
    heading_true_deg: float | None = None  # proa geográfica real, graus, opcional
    heading_magnetic_deg: float | None = None  # proa magnética do cockpit
    on_any_runway: bool | None = None  # nenhum dado = None, não falsa
    # None indica dado indisponível; nunca significa opção desligada.
    assistance_landing: bool | None = None
    assistance_takeoff: bool | None = None
    ai_controls: bool | None = None
    zulu_time_s: float | None = None
    light_beacon: bool | None = None
    light_nav: bool | None = None
    light_taxi: bool | None = None
    light_landing: bool | None = None
    light_strobe: bool | None = None
    g_force: float | None = None
    payload_station_count: int | None = None
    payload_station_2_lbs: float | None = None


class Phase(str, Enum):
    WAITING = "aguardando"
    GROUND = "solo"
    AIRBORNE = "em voo"
    LANDED = "pousado"


class FlightTracker:
    """Detecta um voo por mudanças no estado on_ground (não controla a aeronave).

    Para evitar contar toques rápidos/bounces, confirma pouso somente depois de
    2s contínuos no solo. A razão vertical do toque é a última amostra aérea
    válida nos 2s antes do primeiro contato (não é dado de sensor perfeito).
    """

    def __init__(self, min_airborne_s: float = 5.0, ground_confirm_s: float = 2.0):
        self.phase = Phase.WAITING
        self.min_airborne_s = min_airborne_s
        self.ground_confirm_s = ground_confirm_s
        self.last: Optional[FlightSample] = None
        self.takeoff_sample: Optional[FlightSample] = None
        self.pending_landing: Optional[FlightSample] = None
        self.pending_vs_fpm: Optional[float] = None
        self.last_airborne_vs: Optional[float] = None
        self.last_airborne_timestamp: Optional[float] = None
        self.events: list[dict] = []
        self.stalls = 0
        self._stall_active = False
        self._last_event_timestamp: Optional[float] = None
        # Indicadores de segurança acumulados no voo e serializados no checkpoint.
        self.go_arounds = 0
        self.touch_and_go = 0
        self._max_agl = 0.0
        self._approach_min_agl: Optional[float] = None
        self.taxi_violations = 0
        self._taxi_fast_since: Optional[float] = None
        self._taxi_fast_marked = False
        self._taxi_suspects: list[float] = []  # legado checkpoint v0.7.5
        self.departure_taxi = DepartureTaxi()
        self.hard_g_events = 0
        self._g_since: Optional[float] = None
        self._g_counted = False
        self.light_beacon_taxi_ok = False
        self.light_taxi_ok = False
        self.light_landing_approach_ok = False
        self.light_landing_approach_off = False
        self.light_beacon_taxi_off = False
        self._seen_beacon_on = False
        self._seen_landing_on = False
        self._beacon_off_since: Optional[float] = None
        self._landing_off_since: Optional[float] = None

    def update(self, s: FlightSample) -> list[dict]:
        if self.last and s.timestamp <= self.last.timestamp:
            return []
        out: list[dict] = []
        if self.phase == Phase.GROUND and s.on_ground:
            self.departure_taxi.observe(s)
            # Monitoramento das luzes independente da infração de táxi.
            if not s.groundspeed_estimated and s.engine_running is True and 2<=s.groundspeed_kt<=22:
                self._seen_beacon_on |= s.light_beacon is True
                if s.light_beacon is True:self.light_beacon_taxi_ok=True
                if s.light_taxi is True:self.light_taxi_ok=True
                if self._seen_beacon_on and s.light_beacon is False:
                    if self._beacon_off_since is None:self._beacon_off_since=s.timestamp
                    if s.timestamp-self._beacon_off_since>=4:self.light_beacon_taxi_off=True
                else:self._beacon_off_since=None
        if self.phase == Phase.AIRBORNE and not s.on_ground:
            self._max_agl=max(self._max_agl,s.agl_ft)
            # Arremetida: aeronave já atingiu 800 ft AGL, aproximou
            # descendo abaixo de 600 ft e retomou subida >=170 ft.
            if self._max_agl>=800 and 30<=s.agl_ft<=600 and s.vs_fpm<=-150:
                if self._approach_min_agl is None:self._approach_min_agl=s.agl_ft
                self._approach_min_agl=min(self._approach_min_agl,s.agl_ft)
            if (self._approach_min_agl is not None and s.vs_fpm>=250
                    and s.agl_ft>=self._approach_min_agl+170):
                self.go_arounds+=1
                self._approach_min_agl=None
                out.append({"type":"go_around","timestamp":s.timestamp})
            if s.g_force is not None and s.agl_ft>200 and (s.g_force>=2.2 or s.g_force<=-0.2):
                if self._g_since is None:self._g_since=s.timestamp
                if not self._g_counted and s.timestamp-self._g_since>=1:
                    self.hard_g_events+=1;self._g_counted=True
                    out.append({"type":"hard_maneuver","timestamp":s.timestamp})
            else:
                self._g_since=None;self._g_counted=False
            if 30<=s.agl_ft<=600 and s.vs_fpm<0:
                if s.light_landing is True:
                    self._seen_landing_on=True
                    self.light_landing_approach_ok=True
                    self._landing_off_since=None
                elif s.light_landing is False and self._seen_landing_on:
                    if self._landing_off_since is None:self._landing_off_since=s.timestamp
                    if s.timestamp-self._landing_off_since>=4:
                        self.light_landing_approach_off=True
            if s.light_landing is True:self._seen_landing_on=True
        if self.phase == Phase.WAITING:
            if s.on_ground:
                self.phase = Phase.GROUND
        elif self.phase == Phase.GROUND:
            if not s.on_ground and s.agl_ft >= 3 and s.groundspeed_kt >= 25:
                self.phase = Phase.AIRBORNE
                self.takeoff_sample = s
                self.taxi_violations=self.departure_taxi.takeoff(s)
                self._taxi_suspects.clear()
                self._taxi_fast_since=None
                out.append({"type": "takeoff", "timestamp": s.timestamp,
                            "lat": s.latitude, "lon": s.longitude})
        elif self.phase == Phase.AIRBORNE:
            if not s.on_ground:
                if (self.pending_landing is not None and self.last is not None
                        and self.last.on_ground and
                        self.last.timestamp-self.pending_landing.timestamp>=1
                        and s.agl_ft>=15):
                    self.touch_and_go+=1
                    out.append({"type":"touch_and_go","timestamp":s.timestamp})
                self.last_airborne_vs = s.vs_fpm
                self.last_airborne_timestamp = s.timestamp
                self.pending_landing = None
                self.pending_vs_fpm = None
            elif self.takeoff_sample and s.timestamp - self.takeoff_sample.timestamp >= self.min_airborne_s:
                if self.pending_landing is None:
                    self.pending_landing = s
                    self.pending_vs_fpm = (self.last_airborne_vs
                                           if self.last_airborne_timestamp is not None
                                           and s.timestamp - self.last_airborne_timestamp <= 2.0
                                           else None)
                if s.timestamp - self.pending_landing.timestamp >= self.ground_confirm_s:
                    self.phase = Phase.LANDED
                    descent = self.pending_vs_fpm
                    out.append({"type": "landing", "timestamp": s.timestamp,
                                "lat": s.latitude, "lon": s.longitude,
                                "touchdown_fpm_est": descent,
                                "go_arounds": self.go_arounds,
                                "touch_and_go": self.touch_and_go})
        if self.phase == Phase.AIRBORNE and s.stall_warning is True and not self._stall_active:
            self.stalls += 1
            out.append({"type": "stall_warning", "timestamp": s.timestamp})
        self._stall_active = bool(s.stall_warning)
        self.last = s
        self.events.extend(out)
        return out

    def snapshot(self) -> dict:
        """Checkpoint local sem objetos dependentes de UI; permite retomar voo em curso."""
        return {
            "phase": self.phase.value,
            "last": asdict(self.last) if self.last else None,
            "takeoff_sample": asdict(self.takeoff_sample) if self.takeoff_sample else None,
            "pending_landing": asdict(self.pending_landing) if self.pending_landing else None,
            "pending_vs_fpm": self.pending_vs_fpm,
            "last_airborne_vs": self.last_airborne_vs,
            "last_airborne_timestamp": self.last_airborne_timestamp,
            "events": list(self.events), "stalls": self.stalls,
            "stall_active": self._stall_active,
            "taxi_v2":self.departure_taxi.snapshot(),
            "safety_v1": {
                k:getattr(self,k) for k in (
                    "go_arounds","touch_and_go","_max_agl","_approach_min_agl",
                    "taxi_violations","_taxi_fast_since","_taxi_fast_marked",
                    "_taxi_suspects","hard_g_events","_g_since","_g_counted",
                    "light_beacon_taxi_ok","light_taxi_ok","light_landing_approach_ok",
                    "light_landing_approach_off","light_beacon_taxi_off",
                    "_seen_beacon_on","_seen_landing_on",
                    "_beacon_off_since","_landing_off_since")
            },
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> "FlightTracker":
        tr = cls()
        tr.phase = Phase(data["phase"])
        for key in ("last", "takeoff_sample", "pending_landing"):
            raw = data.get(key)
            if raw is not None:
                setattr(tr, key, FlightSample(**raw))
        tr.pending_vs_fpm = data.get("pending_vs_fpm")
        tr.last_airborne_vs = data.get("last_airborne_vs")
        tr.last_airborne_timestamp = data.get("last_airborne_timestamp")
        tr.events = list(data.get("events", []))
        tr.stalls = int(data.get("stalls", 0))
        tr._stall_active = bool(data.get("stall_active", False))
        tr.departure_taxi=DepartureTaxi.from_snapshot(data.get('taxi_v2'))
        safety=data.get("safety_v1") or {}
        for key in tr.snapshot()["safety_v1"]:
            if key in safety:setattr(tr,key,safety[key])
        return tr

    def reset(self):
        self.__init__(self.min_airborne_s, self.ground_confirm_s)


class Career:
    """Economia própria; missões simples vinculadas a aeroportos reais."""
    def __init__(self, balance: int = 5000):
        self.balance = balance
        self.mission: Optional[Mission] = None
        self.origin_confirmed = False
        self.employer_aircraft_confirmed = False
        self.completed_ids: list[str] = []

    def accept(self, mission: Mission, sample: Optional[FlightSample] = None):
        if self.mission is not None:
            raise ValueError("Conclua ou cancele a missão ativa.")
        lat = mission.origin_lat if mission.origin_lat is not None else AIRPORTS[mission.origin].latitude
        lon = mission.origin_lon if mission.origin_lon is not None else AIRPORTS[mission.origin].longitude
        if sample and distance_nm(sample.latitude, sample.longitude, lat, lon) > 3:
            raise ValueError(f"Sua aeronave não está próxima de {mission.origin}.")
        self.mission = mission
        self.origin_confirmed = sample is not None and sample.on_ground
        self.employer_aircraft_confirmed = False

    def snapshot(self) -> dict:
        return {"mission_id": self.mission.id if self.mission else None,
                "mission_data": asdict(self.mission) if self.mission else None,
                "origin_confirmed": self.origin_confirmed,
                "employer_aircraft_confirmed": self.employer_aircraft_confirmed}

    def restore(self, data: dict):
        mission_id = data.get("mission_id")
        self.mission = next((m for m in MISSIONS if m.id == mission_id), None)
        if self.mission is None and mission_id and data.get("mission_data"):
            candidate = Mission(**data["mission_data"])
            if candidate.id != mission_id:
                raise ValueError("ID inconsistente no contrato salvo")
            self.mission = candidate
        if mission_id and self.mission is None:
            raise ValueError(f"Missão desconhecida no checkpoint: {mission_id}")
        self.origin_confirmed = bool(data.get("origin_confirmed", False)) and self.mission is not None
        self.employer_aircraft_confirmed = bool(data.get("employer_aircraft_confirmed", False)) and self.mission is not None

    def cancel(self):
        self.mission = None
        self.origin_confirmed = False
        self.employer_aircraft_confirmed = False

    def evaluate(self, events: list[dict], aircraft_title: str | None = None) -> Optional[dict]:
        """Crédito somente com decolagem na origem e pouso no destino."""
        if not self.mission:
            return None
        for e in events:
            if e["type"] == "takeoff":
                a_lat = self.mission.origin_lat if self.mission.origin_lat is not None else AIRPORTS[self.mission.origin].latitude
                a_lon = self.mission.origin_lon if self.mission.origin_lon is not None else AIRPORTS[self.mission.origin].longitude
                self.origin_confirmed = distance_nm(e["lat"], e["lon"], a_lat, a_lon) <= 3
                if self.mission.freelance:
                    from .contracts import matches_aircraft
                    self.employer_aircraft_confirmed = matches_aircraft(aircraft_title, self.mission.employer_plane)
            if e["type"] == "landing" and self.origin_confirmed:
                if self.mission.freelance:
                    from .contracts import matches_aircraft
                    if not self.employer_aircraft_confirmed or not matches_aircraft(aircraft_title, self.mission.employer_plane):
                        continue
                b_lat = self.mission.destination_lat if self.mission.destination_lat is not None else AIRPORTS[self.mission.destination].latitude
                b_lon = self.mission.destination_lon if self.mission.destination_lon is not None else AIRPORTS[self.mission.destination].longitude
                dist = distance_nm(e["lat"], e["lon"], b_lat, b_lon)
                if dist <= 3:
                    mission = self.mission
                    self.balance += mission.reward
                    self.completed_ids.append(mission.id)
                    self.cancel()
                    return {"mission": mission.id, "reward": mission.reward, "distance_nm_to_dest": round(dist,2)}
        return None
