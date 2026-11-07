"""Airline fleets and per-model ratings, separate from PPA/PCA/IFR/MLTE/PLA.

Ratings are awarded only for recorded, verified MSFS practice flights. No
career purchase, employer selection, Demo flight or UI toggle grants a rating.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class AircraftType:
    code: str
    title: str
    pattern: str
    family: str = "jet"

TYPES = (
    AircraftType("a320neo", "Airbus A320neo", r"\ba320[\s_-]*(?:neo|n[eé]o|251n|271n)\b"),
    AircraftType("a320200", "Airbus A320-200", r"\ba320[\s_-]*(?:200|2[0-9]{2}|ceo)\b"),
    AircraftType("a319100", "Airbus A319-100", r"\ba319(?:[\s_-]*(?:100|1[0-9]{2}))?\b"),
    AircraftType("a321neo", "Airbus A321neo", r"\ba321[\s_-]*(?:neo|251n|271n)\b"),
    AircraftType("a321p2f", "Airbus A321P2F", r"\ba321[\s_-]*(?:p2f|pcf|freighter)\b"),
    AircraftType("a321xlr", "Airbus A321XLR", r"\ba321[\s_-]*xlr\b"),
    AircraftType("a321200", "Airbus A321-200", r"\ba321[\s_-]*(?:200|2[0-9]{2}|ceo)\b"),
    AircraftType("a330200", "Airbus A330-200", r"\ba330[\s_-]*(?:200|2[0-9]{2}|ceo)\b"),
    AircraftType("a330900neo", "Airbus A330-900neo", r"\ba330[\s_-]*(?:900|9[0-9]{2}|neo)\b"),
    AircraftType("e195e2", "Embraer E195-E2", r"\b(?:e[\s_-]*195|embraer[\s_-]*195)[\s_-]*e2\b"),
    AircraftType("e195e1", "Embraer E195 E1", r"\b(?:e[\s_-]*195|embraer[\s_-]*195)(?:[\s_-]*e1)?\b", "regional"),
    AircraftType("atr72600", "ATR 72-600", r"\batr[\s_-]*72[\s_-]*(?:600|6[0-9]{2})\b", "turboprop"),
    AircraftType("c208b", "Cessna 208B Grand Caravan", r"\b(?:cessna[\s_-]*)?(?:c[\s_-]*)?208b\b|\bgrand[\s_-]*caravan\b", "turboprop"),
    AircraftType("c408", "Cessna 408 SkyCourier", r"\b(?:cessna[\s_-]*)?(?:c[\s_-]*)?408\b|\bskycourier\b", "turboprop"),
    AircraftType("b737max8", "Boeing 737 MAX 8", r"\b(?:b[\s_-]*)?737[\s_-]*(?:max[\s_-]*8|8[\s_-]*max)\b"),
    AircraftType("b737700", "Boeing 737-700", r"\b(?:b[\s_-]*)?737[\s_-]*700\b"),
    AircraftType("b737800", "Boeing 737-800", r"\b(?:b[\s_-]*)?737[\s_-]*800\b"),
    AircraftType("b767300er", "Boeing 767-300ER", r"\b(?:b[\s_-]*)?767[\s_-]*300[\s_-]*(?:er)?\b"),
    AircraftType("b777300er", "Boeing 777-300ER", r"\b(?:b[\s_-]*)?777[\s_-]*300[\s_-]*(?:er)?\b"),
    AircraftType("b7878", "Boeing 787-8", r"\b(?:b[\s_-]*)?787[\s_-]*8\b"),
    AircraftType("b7879", "Boeing 787-9", r"\b(?:b[\s_-]*)?787[\s_-]*9\b"),
)
BY_CODE = {plane.code: plane for plane in TYPES}
FLEETS = {
    "azul": ("a320neo","a321neo","a321p2f","a330200","a330900neo",
             "e195e1","e195e2","atr72600","c208b","c408"),
    "gol": ("b737700","b737800","b737max8","a330900neo","a320neo"),
    "latam": ("a319100","a320200","a320neo","a321200","a321neo",
              "a321xlr","b767300er","b777300er","b7878","b7879"),
}
FLEETS["nordeste"] = tuple(BY_CODE)

def detect_model(title: str | None) -> str | None:
    """Reject ambiguity; e.g. "A320" is not proof of neo vs ceo."""
    if not isinstance(title, str) or not title or len(title) > 256:
        return None
    text=title.casefold()
    # A title naming multiple aircraft families is not reliable evidence of
    # a single installed model, even if just one generation is recognized.
    families=set(re.findall(
        r"\b(?:a3(?:19|20|21|30)|b?(?:737|767|777|787)|e195|atr[\s_-]*72|c?(?:208b|408))",
        text,re.I))
    if len(families)>1:
        return None
    found={p.code for p in TYPES if re.search(p.pattern,text,re.I)}
    # E195 E2 contains E195; prefer explicit generation only.
    if "e195e2" in found:
        found.discard("e195e1")
    if len(found)!=1:
        return None
    return next(iter(found))

def init(conn):
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS airline_type_training(
        flight_key TEXT PRIMARY KEY, code TEXT NOT NULL,
        duration_seconds REAL NOT NULL, completed_utc REAL NOT NULL);
      CREATE INDEX IF NOT EXISTS idx_type_training_code
        ON airline_type_training(code);
      CREATE TABLE IF NOT EXISTS airline_type_ratings(
        code TEXT PRIMARY KEY, awarded_utc REAL NOT NULL);
    """)

def owned(db) -> set[str]:
    return {row[0] for row in db.conn.execute(
        "SELECT code FROM airline_type_ratings") if row[0] in BY_CODE}

def record_training(conn, flight_key: str, title: str | None, start: float,
                    end: float, touchdown_fpm: float | None,
                    stalls: int, *, msfs_verified: bool) -> bool:
    """Call inside the finalized-flight transaction; retries are idempotent."""
    code=detect_model(title)
    duration=end-start
    if not msfs_verified or code is None or not 600 <= duration <= 86400:
        return False
    if stalls != 0 or touchdown_fpm is None or not -650 <= touchdown_fpm <= -30:
        return False
    result=conn.execute("""INSERT OR IGNORE INTO airline_type_training
        (flight_key,code,duration_seconds,completed_utc) VALUES(?,?,?,?)""",
        (flight_key,code,duration,end))
    if result.rowcount!=1:
        return False
    count,total=conn.execute("""SELECT COUNT(*),COALESCE(SUM(duration_seconds),0)
        FROM airline_type_training WHERE code=?""",(code,)).fetchone()
    if count>=2 and total>=1200:
        conn.execute("""INSERT OR IGNORE INTO airline_type_ratings(code,awarded_utc)
                        VALUES(?,?)""",(code,end))
    return True

def progress(db, available=()):
    qualified=owned(db)
    available=set(available)
    rows=dict(db.conn.execute("""SELECT code,COUNT(*)
        FROM airline_type_training GROUP BY code""").fetchall())
    return [dict(code=p.code,title=p.title,airlines=[
        company for company,planes in FLEETS.items() if p.code in planes],
        flights=min(2,int(rows.get(p.code,0))),required=2,
        rated=p.code in qualified,installed=p.code in available)
        for p in TYPES]

def valid_for_company(company: str, code: str, ratings: set[str]) -> bool:
    if company=="nordeste":
        return (code in ("c152","c172","g58","kingair","cj4")
                or (code in BY_CODE and code in ratings))
    return code in FLEETS.get(company,()) and code in ratings
