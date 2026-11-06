"""Painel de carreira: patentes, licenças, conquistas e linha do tempo.

Persistência de medalhas no SQLite da carreira. Variáveis podem ser perdidas e
recuperadas; as permanentes nunca são revogadas por mera queda de pontuação.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from math import isfinite
import json
import time
from .pilot import QUALIFICATIONS, qualification_eligibility, level_progress
from .contracts import next_level_xp
from .reputation import pilot_reputation

RANKS = (
    ("soldado2", "Soldado 2ª Classe", 1, 4),
    ("soldado1", "Soldado 1ª Classe", 5, 9),
    ("cabo", "Cabo", 10, 14),
    ("sargento3", "3º Sargento", 15, 19),
    ("sargento2", "2º Sargento", 20, 24),
    ("sargento1", "1º Sargento", 25, 29),
    ("suboficial", "Suboficial", 30, 34),
    ("aspirante", "Aspirante", 35, 39),
    ("tenente2", "2º Tenente", 40, 44),
    ("tenente1", "1º Tenente", 45, 49),
    ("capitao", "Capitão", 50, 54),
    ("major", "Major", 55, 59),
    ("tenente_coronel", "Tenente-Coronel", 60, 64),
    ("coronel", "Coronel", 65, 69),
    ("brigadeiro", "Brigadeiro do Ar", 70, 74),
    ("major_brigadeiro", "Major-Brigadeiro do Ar", 75, 79),
    ("tenente_brigadeiro", "Tenente-Brigadeiro do Ar", 80, 89),
    ("marechal", "Marechal do Ar", 90, 100),
)
ACHIEVEMENTS = (
    ("first_flight", "Primeiro Voo", "Uma carreira começa no ar", "flight", 1, False),
    ("ten_flights", "10 Voos", "Dez operações registradas", "flight", 10, False),
    ("twentyfive_flights", "25 Voos", "Vinte e cinco voos concluídos", "flight", 25, False),
    ("veteran", "Veterano", "Cinquenta voos registrados", "flight", 50, False),
    ("hundred_hours", "100 Horas", "Cem horas registradas", "hours", 100, False),
    ("first_contract", "Primeiro Contrato", "Primeiro serviço concluído", "contracts", 1, False),
    ("ten_contracts", "10 Contratos", "Dez serviços concluídos", "contracts", 10, False),
    ("reputation70", "Reputação 70", "Prestígio sustentado", "reputation", 70, True),
    ("reputation90", "Reputação 90", "Excelência sustentada", "reputation", 90, True),
    ("first_job", "Primeiro Emprego", "Contratado por uma companhia", "jobs", 1, False),
    ("first_plane", "Primeira Aeronave", "Primeira aeronave adquirida", "purchases", 1, False),
    ("three_planes", "Frota Estabelecida", "Três aeronaves próprias", "fleet", 3, True),
    ("first_license", "Habilitação Avançada", "Obter licença além da PPA", "licenses", 1, False),
)
BY_CODE = {a[0]: a for a in ACHIEVEMENTS}
SHOWCASE_KEY = "pilot_showcase_v1"
EQUIPPED_KEY = "pilot_equipped_medal_v1"


def rank_for_level(level):
    return next((r for r in RANKS if r[2] <= level <= r[3]), RANKS[-1])


def init(db):
    if getattr(db, '_pilot_career_initialized', False):
        return
    db.conn.executescript("""
      CREATE TABLE IF NOT EXISTS pilot_medals (
        code TEXT PRIMARY KEY, first_awarded REAL NOT NULL, active INTEGER NOT NULL,
        changed_at REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS pilot_career_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT UNIQUE NOT NULL,
        occurred_utc REAL, kind TEXT NOT NULL, code TEXT NOT NULL, title TEXT NOT NULL);
    """)
    db._pilot_career_initialized = True


def event(db, key, moment, kind, code, title):
    db.conn.execute("""INSERT OR IGNORE INTO pilot_career_events
        (event_key,occurred_utc,kind,code,title) VALUES(?,?,?,?,?)""",
                    (key, moment, kind, code, title))


def counts(db):
    rows = db.conn.execute("""SELECT id, started_utc, ended_utc, touchdown_fpm_est,
      mission_id, aircraft_title FROM flights ORDER BY started_utc,id""").fetchall()
    contracts = [r for r in rows if r[4]]
    hours = sum(max(0, r[2]-r[1]) for r in rows)/3600
    # A aeronave inicial é cortesia, independentemente do uso ou das horas.
    # As unidades adquiridas pelo mercado ficam em fleet_units (inclusive
    # Cessna 152 adicionais); aluguel nunca entra nessa tabela.
    # Manter também o log de aquisições para que Primeira Aeronave continue
    # conquistada mesmo depois de vender o exemplar pago.
    bought_legacy = db.conn.execute(
        "SELECT COUNT(*) FROM owned_aircraft WHERE code != 'c152'").fetchone()[0]
    purchased_now = {"unit:" + str(r[0]) for r in db.conn.execute(
        "SELECT id FROM fleet_units")}
    purchased_history = {str(r[0]) for r in db.conn.execute(
        """SELECT description FROM fleet_log
           WHERE kind IN ('new_purchase','used_purchase')
           AND description LIKE 'unit:%'""")}
    purchased = bought_legacy + len(purchased_now | purchased_history)
    # Frota Estabelecida é patrimônio ATUAL comprado. O starter gratuito e
    # unidades alugadas não contam; a venda pode fazer a medalha ficar inativa.
    paid_fleet = bought_legacy + len(purchased_now)
    job_rows = db.conn.execute("""SELECT decided_utc FROM job_applications WHERE status='hired'
                               ORDER BY decided_utc""").fetchall()
    licenses = db.conn.execute("""SELECT code,awarded_utc FROM pilot_qualifications
                                ORDER BY awarded_utc""").fetchall()
    rep = pilot_reputation(db.conn)
    return dict(rows=rows, contracts=contracts, hours=hours,
                flights=len(rows), contract_count=len(contracts),
                reputation=rep["score"], jobs=len(job_rows),
                purchases=purchased, fleet=paid_fleet,
                licenses=sum(1 for code,_ in licenses if code!="PPA"),
                license_rows=licenses, hired=job_rows)


def _achieved_when(source, requirement, data):
    if source=="flight" and len(data["rows"])>=requirement:
        return data["rows"][requirement-1][2]
    if source=="contracts" and len(data["contracts"])>=requirement:
        return data["contracts"][requirement-1][2]
    if source=="hours" and data["hours"]>=requirement:
        acc=0
        for row in data["rows"]:
            acc+=max(0,row[2]-row[1])/3600
            if acc>=requirement:return row[2]
    if source=="jobs" and data["jobs"]>=requirement:
        return data["hired"][requirement-1][0]
    if source=="licenses" and data["licenses"]>=requirement:
        return [time_ for code,time_ in data["license_rows"] if code!="PPA"][requirement-1]
    # Sem eventos históricos documentados para patrimônio ou reputação:
    # primeira detecção é registrada na data presente, não inventada.
    return None


def _override(db, active_profile):
    if not active_profile or active_profile.get("kind")!="test":
        return {}
    if db.get_setting("pilot_test_guard_v1")!="1":
        return {}
    try:
        data=json.loads(db.get_setting(SHOWCASE_KEY) or "{}")
        return data if isinstance(data,dict) else {}
    except (ValueError,TypeError):
        return {}


def set_showcase(db, active_profile, payload):
    if not _override_allowed(db,active_profile):
        raise ValueError("Admin disponível somente no perfil Teste.")
    if not isinstance(payload,dict) or set(payload)!={"level","xp","reputation","licenses","achievements","rank"}:
        raise ValueError("Formato de showcase inválido.")
    level=payload["level"]
    xp=payload["xp"]
    rep=payload["reputation"]
    if (type(level) is not int or not 1<=level<=100
            or type(xp) is not int or not 0<=xp<=5_000_000
            or type(rep) is not int or not 0<=rep<=100):
        raise ValueError("Nível/reputação inválido.")
    licenses=payload["licenses"];achievements=payload["achievements"];rank=payload["rank"]
    if not isinstance(licenses,dict) or not isinstance(achievements,dict):
        raise ValueError("Estados inválidos.")
    if set(licenses)-{q.code for q in QUALIFICATIONS} or set(achievements)-set(BY_CODE):
        raise ValueError("Código de medalha/licença desconhecido.")
    if any(v not in ("locked","available","earned") for v in
           list(licenses.values())+list(achievements.values())):
        raise ValueError("Estado de desbloqueio inválido.")
    if rank is not None and rank not in {r[0] for r in RANKS}:
        raise ValueError("Patente desconhecida.")
    db.set_setting(SHOWCASE_KEY,json.dumps(payload,ensure_ascii=False))
    return "Prévia do perfil Teste atualizada, sem modificar o histórico do voo."


def _override_allowed(db, profile):
    return (bool(profile) and profile.get("kind")=="test" and
            db.get_setting("pilot_test_guard_v1")=="1")


def equip(db, profile, code, active_codes):
    if code and code not in BY_CODE:
        raise ValueError("Medalha desconhecida.")
    if code and code not in active_codes:
        raise ValueError("Essa medalha ainda não está ativa.")
    db.set_setting(EQUIPPED_KEY,code or "")
    return "Medalha equipada." if code else "Medalha removida."


def snapshot(db, profile=None):
    init(db)
    pilot=db.get_pilot()
    stats=db.pilot_stats()
    base=counts(db)
    timestamp=time.time()
    data={**base,"flight":base["flights"],"contracts":base["contract_count"],"reputation":base["reputation"]}
    with db.conn:
        for code,title,description,source,limit,variable in ACHIEVEMENTS:
            actual=data.get(source,0) >= limit
            row=db.conn.execute("SELECT first_awarded,active FROM pilot_medals WHERE code=?",(code,)).fetchone()
            if actual and row is None:
                when=_achieved_when(source,limit,base) or timestamp
                db.conn.execute("INSERT INTO pilot_medals VALUES(?,?,?,?)",(code,when,1,timestamp))
                event(db,f"medal:{code}:first",when,"gain",code,title)
            elif row and variable and bool(row[1])!=actual:
                # Mudança de reputação: anotar perda ou recuperação uma única vez.
                sequence=db.conn.execute("""SELECT COUNT(*) FROM pilot_career_events
                                            WHERE code=? AND kind IN ('gain','loss')""",(code,)).fetchone()[0]
                kind="gain" if actual else "loss"
                db.conn.execute("UPDATE pilot_medals SET active=?,changed_at=? WHERE code=?",
                                (int(actual),timestamp,code))
                event(db,f"medal:{code}:{sequence+1}",timestamp,kind,code,title)
    rows=db.conn.execute("SELECT code,first_awarded,active FROM pilot_medals").fetchall()
    awarded={code:(since,bool(active)) for code,since,active in rows}
    showcase=_override(db,profile)
    preview=bool(showcase)
    rank=rank_for_level(stats["level"])
    level=stats["level"]
    rep=base["reputation"]
    xp=stats["xp"]
    if preview:
        level=showcase.get("level",level);rep=showcase.get("reputation",rep)
        xp=showcase.get("xp",xp)
        rank=next((r for r in RANKS if r[0]==showcase.get("rank")),rank_for_level(level))
    active_codes=set()
    medal_items=[]
    for code,title,desc,source,target,variable in ACHIEVEMENTS:
        row=awarded.get(code)
        actual=bool(row and row[1])
        status="earned" if actual else "locked"
        if preview:
            # O laboratório também simula perda/recuperação por reputação,
            # preservando sobreposições explícitas do Admin para cada medalha.
            if variable and source=="reputation":
                status="earned" if rep>=target else "locked"
            status=showcase.get("achievements",{}).get(code,status)
        if status=="earned":active_codes.add(code)
        medal_items.append(dict(code=code,title=title,description=desc,
            status=status,variable=variable,target=target,current=rep if source=="reputation"
            else data.get(source,0),awarded_utc=row[0] if row else None))
    equipped=db.get_setting(EQUIPPED_KEY) or None
    equipped=equipped if equipped in active_codes else None
    qualifies={code:when for code,when in base["license_rows"]}
    certificates=[]
    for q in QUALIFICATIONS:
        eligible,reason=qualification_eligibility(
            q.code,set(qualifies),stats["flights"],stats["xp"],stats["hours"])
        status="earned" if q.code in qualifies else "available" if eligible else "locked"
        if preview:status=showcase.get("licenses",{}).get(q.code,status)
        certificates.append(dict(code=q.code,title=q.title.replace(" (virtual)","").replace(" — avião (virtual)"," — avião"),
            description=q.description,date=qualifies.get(q.code),status=status,
            requirements=reason,flights=q.flights,hours=q.hours,xp=q.xp,
            prerequisites=list(q.prerequisites)))
    level_start=0 if level==1 else next_level_xp(level-1)
    level_end=next_level_xp(level)
    # XP do Admin é apenas visual, jamais ajusta pilot_xp_ledger.
    fraction=max(0.0,min(1.0,(xp-level_start)/max(1,level_end-level_start)))
    progress=level_progress(stats["xp"]) if not preview else dict(
        level=level,next_level=level+1 if level<100 else None,
        fraction=fraction,remaining=max(0,level_end-xp))
    timeline=[]
    def add(key,when,kind,title,code=None):
        if when is not None:timeline.append(dict(key=key,when=when,kind=kind,title=title,code=code))
    if pilot:add("creation",pilot["created_utc"],"start","Início da carreira")
    for index in (1,10,25,50):
        if base["flights"]>=index:add(f"flight-{index}",base["rows"][index-1][2],"flight",
            f"{index}º voo registrado" if index>1 else "Primeiro voo")
    for index in (1,10):
        if base["contract_count"]>=index:add(f"contract-{index}",base["contracts"][index-1][2],
                                            "contract",f"{index}º contrato concluído")
    for code,when in base["license_rows"]:
        add("qualification:"+code,when,"license","Certificado "+code,code)
    xp_rows=db.conn.execute("""SELECT xp,awarded_utc FROM pilot_xp_ledger
                               ORDER BY awarded_utc,flight_key""").fetchall()
    accumulated=0
    achieved_at={}
    for gained,when in xp_rows:
        accumulated+=gained
        for entry in RANKS[1:]:
            if entry[0] not in achieved_at and accumulated>=next_level_xp(entry[2]-1):
                achieved_at[entry[0]]=when
    with db.conn:
        for entry in RANKS[1:]:
            if stats["level"]>=entry[2]:
                moment=achieved_at.get(entry[0]) or timestamp
                event(db,"rank:"+entry[0],moment,"promotion",entry[0],
                      "Promoção a "+entry[1])
    for id_,when in db.conn.execute("""SELECT id,acquired_utc FROM fleet_units ORDER BY acquired_utc"""):
        add("aircraft-purchased:"+str(id_),when,"purchase","Aeronave adquirida")
    for (when,) in base["hired"]:
        add("employment:"+str(when),when,"employment","Contratação por companhia")
    for id_,when,kind,code,title in db.conn.execute("""SELECT event_key,occurred_utc,kind,code,title
                                          FROM pilot_career_events ORDER BY id DESC LIMIT 100"""):
        add(id_,when,kind,("Conquista perdida: " if kind=="loss" else
                         "Promoção: " if kind=="promotion" else
                         "Conquista: ")+title,code)
    timeline.sort(key=lambda x:x["when"] or 0,reverse=True)
    landings=[dict(when=row[2],fpm=row[3]) for row in base["rows"]
              if row[3] is not None and isinstance(row[3],(int,float)) and isfinite(row[3])][-100:]
    contracts_by_month=defaultdict(int)
    hours_by_plane=defaultdict(float)
    for row in base["contracts"]:
        contracts_by_month[datetime.fromtimestamp(row[2],timezone.utc).strftime("%Y-%m")]+=1
    for row in base["rows"]:
        if row[5]:hours_by_plane[row[5]]+=max(0,row[2]-row[1])/3600
    return dict(name=pilot["name"] if pilot else None,level=level,rank={
        "code":rank[0],"title":rank[1],"min":rank[2],"max":rank[3]},
        rank_gallery=[dict(code=r[0],title=r[1],min=r[2],max=r[3],
                           state="earned" if level>=r[2] else "locked") for r in RANKS],
        reputation=rep,xp=xp,medals=medal_items,equipped=equipped,
        licenses=certificates,progress=progress,flights=stats["flights"],
        hours=round(stats["hours"],1),contracts=base["contract_count"],
        aircraft_types=len(hours_by_plane),earned_money=db.conn.execute(
             "SELECT COALESCE(SUM(amount),0) FROM finance_ledger WHERE kind='contrato'").fetchone()[0],
        timeline=timeline[:100],events_seq=db.conn.execute("SELECT COALESCE(MAX(id),0) FROM pilot_career_events").fetchone()[0],
        graphs={"landings":landings,"contracts":sorted(contracts_by_month.items())[-18:],
                "hours_by_aircraft":sorted(hours_by_plane.items(),key=lambda x:-x[1])[:10]},
        is_test=_override_allowed(db,profile),
        showcase=showcase,
        profiles=[],
    )
