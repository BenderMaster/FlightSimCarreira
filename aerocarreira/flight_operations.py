"""Flight Operations v0.8.2: planejamento VFR de voo livre ou contratado.

O estado é um rascunho persistido no SQLite da carreira, não uma missão nem
uma ordem de pagamento. Aeroportos devem existir no catálogo da sessão MSFS.
"""
from __future__ import annotations

import json
import math
import re
from .domain import Mission, distance_nm
from .finance import AIRCRAFT_ECONOMY, LITERS_PER_GALLON
from .contracts import aircraft_model

SETTING = "flight_operations_v1"
CHECKS = ("runway_checked", "route_checked", "fuel_checked", "payload_checked")
ICAO = re.compile(r"[A-Z0-9]{4}\Z")
FIX = re.compile(r"[A-Z0-9_-]{1,12}\Z")


def _coordinate(lat, lon):
    if type(lat) not in (float, int) or type(lon) not in (float, int):
        raise ValueError("Waypoint: coordenadas numéricas obrigatórias.")
    if not (math.isfinite(lat) and math.isfinite(lon) and
            -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Waypoint com latitude ou longitude inválida.")
    return round(float(lat), 7), round(float(lon), 7)


def validated(payload, catalog, mission=None):
    """Valida no motor, nunca no navegador, todos os pontos e aeroportos."""
    if not isinstance(payload, dict) or set(payload) != {
            "mode", "origin", "destination", "altitude_ft", "waypoints", "checks"}:
        raise ValueError("Formato de planejamento inválido.")
    mode = payload["mode"]
    if mode not in ("free", "contract"):
        raise ValueError("Modalidade desconhecida.")
    if mode == "contract" and mission is None:
        raise ValueError("Não existe contrato ativo para este planejamento.")
    origin, destination = payload["origin"], payload["destination"]
    if not all(isinstance(v, str) and ICAO.fullmatch(v) for v in (origin, destination)):
        raise ValueError("Informe ICAOs de quatro caracteres.")
    if origin == destination:
        raise ValueError("Origem e destino devem ser diferentes.")
    if mode == "contract" and (origin != mission.origin or destination != mission.destination):
        raise ValueError("Um contrato não pode ter origem/destino alterados.")
    locations = getattr(catalog, "locations", None)
    if not locations or origin not in locations or destination not in locations:
        raise ValueError("Origem/destino não confirmados no catálogo da sessão MSFS.")
    altitude = payload["altitude_ft"]
    if type(altitude) is not int or not 500 <= altitude <= 45000:
        raise ValueError("Altitude VFR deve ser um número inteiro de 500 a 45000 ft.")
    waypoints = payload["waypoints"]
    if not isinstance(waypoints, list) or len(waypoints) > 8:
        raise ValueError("Use no máximo oito waypoints intermediários.")
    clean_waypoints = []
    seen = set()
    for w in waypoints:
        if not isinstance(w, dict) or set(w) != {"label", "lat", "lon"}:
            raise ValueError("Waypoint inválido.")
        label = w["label"]
        if not isinstance(label, str) or not FIX.fullmatch(label):
            raise ValueError("Waypoint: nome de 1 a 12 caracteres A-Z/0-9/_/-.")
        if label in seen:
            raise ValueError("Nomes de waypoint devem ser únicos.")
        seen.add(label)
        lat, lon = _coordinate(w["lat"], w["lon"])
        clean_waypoints.append({"label": label, "lat": lat, "lon": lon})
    flags = payload["checks"]
    if not isinstance(flags, dict) or set(flags) != set(CHECKS) or any(type(v) is not bool for v in flags.values()):
        raise ValueError("Checklist inválido.")
    return {
        "version": 1, "mode": mode, "mission_id": mission.id if mode == "contract" else None,
        "origin": origin, "destination": destination, "altitude_ft": altitude,
        "waypoints": clean_waypoints, "checks": {k: flags[k] for k in CHECKS}
    }


def read_saved(db, mission=None):
    raw = db.get_setting(SETTING)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if data.get("version") != 1 or data.get("mode") not in ("free", "contract"):
            return None
        if data["mode"] == "contract" and (
                mission is None or data.get("mission_id") != mission.id):
            return None
        return data
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def draft(mission=None, origin=""):
    return {"mode": "contract" if mission else "free",
            "origin": mission.origin if mission else origin,
            "destination": mission.destination if mission else "",
            "altitude_ft": 2500, "waypoints": [],
            "checks": {key: False for key in CHECKS}}


def save(db, payload, catalog, mission=None):
    plan = validated(payload, catalog, mission)
    db.set_setting(SETTING, json.dumps(plan, ensure_ascii=False, separators=(",", ":")))
    return plan


def bearing_deg(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    east = math.sin(dlon) * math.cos(b)
    north = math.cos(a) * math.sin(b) - math.sin(a) * math.cos(b) * math.cos(dlon)
    return (math.degrees(math.atan2(east, north)) + 360) % 360


def route_stats(plan, catalog, aircraft_title=None, fuel_available=None, sample=None):
    """Uma única projeção do motor atende frontend e exportação."""
    origin = catalog.locations[plan["origin"]]
    destination = catalog.locations[plan["destination"]]
    coords = [(origin.latitude, origin.longitude, plan["origin"])]
    coords += [(w["lat"], w["lon"], w["label"]) for w in plan["waypoints"]]
    coords.append((destination.latitude, destination.longitude, plan["destination"]))
    legs = []
    for (a, b, name), (c, d, next_name) in zip(coords, coords[1:]):
        legs.append({"from": name, "to": next_name,
                     "nm": round(distance_nm(a, b, c, d), 1),
                     "bearing_deg": round(bearing_deg(a, b, c, d)) % 360})
    total = sum(distance_nm(a, b, c, d) for (a, b, _), (c, d, _) in zip(coords, coords[1:]))
    code = aircraft_model(aircraft_title or "")
    model = AIRCRAFT_ECONOMY.get(code or "")
    cruise = model.cruise_kts if model else 90
    duration = max(8, round(60 * total / cruise + 5))
    required = (model.fuel_lph * duration / 60 / LITERS_PER_GALLON * 1.35) if model else None
    reserve = (required * (0.35 / 1.35)) if required else None
    weight = getattr(sample, "total_weight_lbs", None)
    mtow = getattr(sample, "max_gross_weight_lbs", None)
    available = fuel_available if isinstance(fuel_available, (float, int)) and math.isfinite(fuel_available) else None
    return {
        "mode": plan["mode"], "origin": plan["origin"], "destination": plan["destination"],
        "mission_id": plan.get("mission_id"), "altitude_ft": plan["altitude_ft"],
        "waypoints": plan["waypoints"], "checks": plan["checks"],
        "route": [[a, b] for a, b, _ in coords], "legs": legs,
        "route_key": json.dumps([plan["origin"], plan["destination"], plan["waypoints"]], separators=(",", ":")),
        "distance_nm": round(total, 1), "minutes": duration, "cruise_kts": cruise,
        "fuel_required_gal": round(required, 1) if required is not None else None,
        "fuel_reserve_gal": round(reserve, 1) if reserve is not None else None,
        "fuel_available_gal": round(available, 1) if available is not None else None,
        "fuel_ok": available >= required if available is not None and required is not None else None,
        "weight_lbs": round(weight, 1) if isinstance(weight, (int, float)) and math.isfinite(weight) else None,
        "mtow_lbs": round(mtow, 1) if isinstance(mtow, (int, float)) and math.isfinite(mtow) else None,
        "weight_ok": weight <= mtow if isinstance(weight, (int, float)) and
                      isinstance(mtow, (int, float)) and math.isfinite(weight) and math.isfinite(mtow) else None
    }


def to_mission(plan, catalog, contract=None):
    """Voo livre gera somente um arquivo de navegação; nunca uma missão paga."""
    if plan["mode"] == "contract":
        if not contract or contract.id != plan["mission_id"]:
            raise ValueError("Contrato associado ao plano não está ativo.")
        return contract
    origin, destination = catalog.locations[plan["origin"]], catalog.locations[plan["destination"]]
    return Mission("FREE-PLAN", plan["origin"], plan["destination"], "Voo livre sem remuneração", 0,
                   origin_lat=origin.latitude, origin_lon=origin.longitude,
                   destination_lat=destination.latitude, destination_lon=destination.longitude,
                   nav_source="MSFS")
