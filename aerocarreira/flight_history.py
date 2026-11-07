"""FlightSim flight history: factual SQLite-only logbook and read-only analysis feed.

No airport ICAO is inferred from approximate coordinates; no historical telemetry
is fabricated. Personal and business ledgers remain distinct.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import asin, cos, isfinite, radians, sin, sqrt
from time import time


def init(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS flight_notes (
        flight_id INTEGER PRIMARY KEY REFERENCES flights(id),
        note TEXT NOT NULL DEFAULT '',
        updated_utc REAL NOT NULL,
        CHECK(length(note) <= 1200)
    )""")


def save_note(db, flight_id, note):
    if type(flight_id) is not int or flight_id < 1:
        raise ValueError('Identificador de voo inválido.')
    if not isinstance(note, str) or len(note) > 1200 or any(
            ord(ch) < 32 and ch not in '\n\t' for ch in note):
        raise ValueError('Anotação inválida: máximo de 1.200 caracteres.')
    if db.conn.execute('SELECT 1 FROM flights WHERE id=?', (flight_id,)).fetchone() is None:
        raise ValueError('Voo não encontrado no perfil ativo.')
    with db.conn:
        db.conn.execute("""INSERT INTO flight_notes(flight_id,note,updated_utc)
            VALUES(?,?,?) ON CONFLICT(flight_id) DO UPDATE SET
            note=excluded.note,updated_utc=excluded.updated_utc""",
            (flight_id, note, time()))


def _distance_nm(from_lat, from_lon, to_lat, to_lon):
    coords=(from_lat,from_lon,to_lat,to_lon)
    if any(x is None or not isfinite(float(x)) for x in coords):
        return None
    a,b,c,d=map(float,coords)
    if not (-90<=a<=90 and -90<=c<=90 and -180<=b<=180 and -180<=d<=180):
        return None
    p1,p2=radians(a),radians(c)
    delta=radians(c-a)
    h=sin(delta/2)**2+cos(p1)*cos(p2)*sin(radians(d-b)/2)**2
    return round(3440.065*2*asin(min(1,sqrt(max(0,h)))),1)


def category(mission_id):
    if not mission_id:
        return 'particular'
    if mission_id.startswith('EMP-'):
        return 'emprego'
    if mission_id.startswith('OWN-'):
        return 'empresa'
    if mission_id.startswith('FREE-'):
        return 'freelancer'
    if mission_id.startswith('REG-'):
        return 'regional'
    return 'outro'


def snapshot(db):
    """Read-only projection, always sourced from the active profile's SQLite."""
    init(db.conn)
    flight_rows=db.conn.execute("""SELECT id,started_utc,ended_utc,
        from_lat,from_lon,to_lat,to_lon,touchdown_fpm_est,stall_warnings,
        mission_id,reward,flight_key,aircraft_title
        FROM flights ORDER BY started_utc DESC,id DESC""").fetchall()
    notes={r[0]:r[1] for r in db.conn.execute('SELECT flight_id,note FROM flight_notes')}
    xp={r[0]:r[1] for r in db.conn.execute('SELECT flight_key,xp FROM pilot_xp_ledger')}
    personal=defaultdict(int)
    personal_exists=set()
    personal_category=defaultdict(lambda:defaultdict(int))
    for key,kind,amount in db.conn.execute(
            "SELECT event_key,kind,amount FROM finance_ledger WHERE event_key LIKE 'takeoff:%'"):
        flight_key=key.rsplit(':',1)[0]
        personal[flight_key]+=int(amount)
        personal_exists.add(flight_key)
        personal_category[flight_key][kind]+=int(amount)
    business=defaultdict(int)
    business_exists=set()
    for key,amount in db.conn.execute(
            "SELECT event_key,amount FROM airline_company_ledger WHERE event_key LIKE 'takeoff:%'"):
        flight_key=key.rsplit(':',1)[0]
        business[flight_key]+=int(amount)
        business_exists.add(flight_key)
    records=[]
    for (id_,started,ended,lat1,lon1,lat2,lon2,touchdown,stalls,mission,
         reward,key,aircraft) in flight_rows:
        duration=max(0,ended-started)
        records.append({
            'id':id_, 'started_utc':started, 'ended_utc':ended,
            'hours':round(duration/3600,4), 'duration_seconds':round(duration),
            'from_lat':lat1,'from_lon':lon1,'to_lat':lat2,'to_lon':lon2,
            'direct_nm':_distance_nm(lat1,lon1,lat2,lon2),
            'departure_icao':None,'arrival_icao':None,
            'touchdown_fpm':touchdown,'stalls':stalls,
            'mission_id':mission,'kind':category(mission),
            'aircraft':aircraft or None,'reward_recorded':reward,
            'xp':xp.get(key) if key else None,
            'personal_net':personal[key] if key in personal_exists else None,
            'business_net':business[key] if key in business_exists else None,
            'personal_costs':{k:v for k,v in personal_category[key].items() if v<0},
            'note':notes.get(id_,'')
        })
    return {'flights':records,'count':len(records),
            'notes_revision':db.conn.execute(
                'SELECT COUNT(*),COALESCE(MAX(updated_utc),0) FROM flight_notes').fetchone()}


def csv_text(records):
    """Excel pt-BR CSV; guard against formula injection from user annotations."""
    import csv
    import io
    output=io.StringIO()
    writer=csv.writer(output,delimiter=';',quoting=csv.QUOTE_ALL,lineterminator='\r\n')
    writer.writerow(('ID','Início UTC','Fim UTC','Aeronave','Modalidade','Contrato',
                     'Latitude origem','Longitude origem','Latitude destino','Longitude destino',
                     'Duração (h)','Distância direta estimada (NM)','Pouso (ft/min)',
                     'Alertas estol','XP voo','Resultado pessoal (R$)',
                     'Resultado empresarial (R$)','Anotações'))
    def safe(value):
        if value is None:return ''
        value=str(value)
        return "'"+value if value.startswith(('=','+','-','@')) and not value.replace('-','',1).replace('.','',1).isdigit() else value
    def date(ts):
        return datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if ts is not None else ''
    for r in records:
        writer.writerow([safe(x) for x in (
            r['id'],date(r['started_utc']),date(r['ended_utc']),r['aircraft'],
            r['kind'],r['mission_id'],r['from_lat'],r['from_lon'],r['to_lat'],r['to_lon'],
            r['hours'],r['direct_nm'],r['touchdown_fpm'],r['stalls'],r['xp'],
            r['personal_net'],r['business_net'],r['note'])])
    return '\ufeff'+output.getvalue()
