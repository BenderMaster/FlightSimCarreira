"""Airline Operations — career employment, weekly payroll, and ring-fenced companies.

Every credit is backed by completed MSFS flights or a prior explicit capital
transfer. No timer produces passive airline revenue. All writes run in the same
SQLite connection / transaction as the personal career.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from random import Random
from time import time
import re

from .employment import EMPLOYER_BY_CODE, weekly_period, OWN_INVESTMENT, vacancies
from .finance import AIRCRAFT_ECONOMY, flight_operating_cost, market_reward
from .domain import Mission

WEEK_SECONDS=7*86400
TIERS=(0,10,20)
GRADES=(
    ('trainee','Piloto em treinamento',0,0.0,0),
    ('junior','Primeiro Oficial Júnior',8,8.0,1),
    ('officer','Primeiro Oficial',25,32.0,2),
    ('captain','Comandante',65,90.0,3),
    ('senior','Comandante Sênior',145,220.0,4),
)
REQUIREMENTS={
    'nordeste':(10,5),'azul':(12,6),
    'gol':(14,7),'latam':(16,8),
}
# Base de emprego nos quatro níveis, antes dos multiplicadores reais.
BASE_SALARY={'nordeste':9000,'azul':30000,'gol':23000,'latam':17000}
PRESTIGE={'nordeste':1.00,'azul':1.50,'gol':1.33,'latam':1.18}

def company_grade(flights,hours):
    grade=GRADES[0]
    for row in GRADES[1:]:
        if flights>=row[2] or hours>=row[3]:
            grade=row
    return dict(code=grade[0],title=grade[1],index=grade[4])

def thresholds(company,tier):
    if company not in REQUIREMENTS or tier not in TIERS:
        raise ValueError('Companhia ou compromisso inválido.')
    hours,flights=REQUIREMENTS[company]
    if tier==10:
        return dict(hours=hours+5,flights=flights+3)
    if tier==20:
        return dict(hours=hours+10,flights=flights+7)
    return dict(hours=hours,flights=flights)

def rate(company,level,reputation,grade_index=0):
    """Independent of volume of flights, frozen when a payroll week is opened."""
    if company not in BASE_SALARY:raise ValueError('Companhia inválida')
    if not isfinite(float(reputation)):raise ValueError('Reputação inválida')
    employer=EMPLOYER_BY_CODE[company]
    level=max(1,min(100,int(level)))
    rep=max(0,min(100,float(reputation)))
    level_factor=min(2.0,1+max(0,level-employer.min_level)*.035)
    rep_factor=.75+rep*.005
    grade_factor=1+max(0,min(4,grade_index))*.07
    wage=BASE_SALARY[company]*level_factor*rep_factor*grade_factor
    xp=round((45+level*4+20*PRESTIGE[company])*grade_factor)
    return (round(wage/10)*10,max(15,xp))

def evaluate(tier,contract_flights,contract_hours,company,base_salary,base_xp):
    base=thresholds(company,0)
    chosen=thresholds(company,tier)
    basic=contract_flights>=base['flights'] or contract_hours>=base['hours']
    target=contract_flights>=chosen['flights'] or contract_hours>=chosen['hours']
    if not basic:factor=0.0;result='sem_meta'
    elif target:factor=1+tier/100;result='cumprido'
    else:factor=1-tier/100;result='penalizado'
    return dict(result=result,base_met=basic,chosen_met=target,
                salary=round(base_salary*factor),xp=round(base_xp*factor),
                factor=factor,base_target=base,chosen_target=chosen)

def init(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS airline_agreements(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          employer TEXT NOT NULL, hired_utc REAL NOT NULL,
          resigned_utc REAL, tier INTEGER NOT NULL DEFAULT 0 CHECK(tier IN (0,10,20)),
          status TEXT NOT NULL CHECK(status IN ('active','closed')));
        CREATE TABLE IF NOT EXISTS airline_work(
          flight_key TEXT PRIMARY KEY, agreement_id INTEGER NOT NULL,
          employer TEXT NOT NULL, week INTEGER NOT NULL,
          duration_seconds REAL NOT NULL CHECK(duration_seconds>=0),
          mission_id TEXT NOT NULL UNIQUE, completed_utc REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS ix_airline_work_week ON airline_work(agreement_id,week);
        CREATE TABLE IF NOT EXISTS airline_payroll(
          agreement_id INTEGER NOT NULL, week INTEGER NOT NULL,
          contract_flights INTEGER NOT NULL, seconds REAL NOT NULL,
          tier INTEGER NOT NULL, salary INTEGER NOT NULL, xp INTEGER NOT NULL,
          result TEXT NOT NULL, settled_utc REAL NOT NULL,
          PRIMARY KEY (agreement_id,week));
        CREATE TABLE IF NOT EXISTS airline_promotions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, agreement_id INTEGER NOT NULL,
          flight_key TEXT NOT NULL UNIQUE, grade TEXT NOT NULL,
          title TEXT NOT NULL, awarded_utc REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS airline_week_rates(
          agreement_id INTEGER NOT NULL, week INTEGER NOT NULL,
          base_salary INTEGER NOT NULL, base_xp INTEGER NOT NULL,
          tier INTEGER NOT NULL,
          PRIMARY KEY(agreement_id,week));
        CREATE TABLE IF NOT EXISTS airline_company(
          id INTEGER PRIMARY KEY CHECK(id=1),
          name TEXT NOT NULL, callsign TEXT NOT NULL,
          home_icao TEXT NOT NULL,
          founded_utc REAL NOT NULL,
          balance INTEGER NOT NULL, reputation INTEGER NOT NULL DEFAULT 50);
        CREATE TABLE IF NOT EXISTS airline_company_ledger(
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT UNIQUE NOT NULL,
          kind TEXT NOT NULL, amount INTEGER NOT NULL,
          balance_after INTEGER NOT NULL, description TEXT NOT NULL,
          created_utc REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS airline_company_aircraft(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT NOT NULL, title TEXT NOT NULL, airport TEXT NOT NULL,
          condition REAL NOT NULL DEFAULT 100, hours REAL NOT NULL DEFAULT 0,
          purchase_price INTEGER NOT NULL, bought_utc REAL NOT NULL);
    """)

def active_agreement(db):
    row=db.conn.execute("""SELECT id,employer,hired_utc,resigned_utc,tier
        FROM airline_agreements WHERE status='active' ORDER BY id DESC LIMIT 1""").fetchone()
    if row:
        return dict(id=row[0],employer=row[1],hired_utc=row[2],
                    resigned_utc=row[3],tier=row[4])
    return None

def ensure_agreement(db,now):
    """Upgrade pre-v0.8.5 employed saves; the existing employment is preserved."""
    state=db.employment_state()
    if state['mode']!='empregado':
        return None
    active=active_agreement(db)
    if active:return active
    employer=state['employer_code']
    if employer not in EMPLOYER_BY_CODE:return None
    with db.conn:
        db.conn.execute("""INSERT INTO airline_agreements
            (employer,hired_utc,resigned_utc,tier,status)
            VALUES (?,?,NULL,0,'active')""",(employer,now))
    return active_agreement(db)

def hire(db,company,now,tier):
    if company not in EMPLOYER_BY_CODE or tier not in TIERS:
        raise ValueError('Compromisso de contratação inválido.')
    with db.conn:
        db.conn.execute("""UPDATE airline_agreements SET status='closed',resigned_utc=?
                           WHERE status='active'""",(now,))
        db.conn.execute("""INSERT INTO airline_agreements
            (employer,hired_utc,tier,status) VALUES (?,?,?,'active')""",
            (company,now,tier))

def quit_employment(db,now):
    with db.conn:
        db.conn.execute("""UPDATE airline_agreements SET status='closed',resigned_utc=?
            WHERE status='active'""",(now,))

def work_stats(db,agreement):
    row=db.conn.execute("""SELECT COUNT(*),COALESCE(SUM(duration_seconds),0)
        FROM airline_work WHERE agreement_id=?""",(agreement['id'],)).fetchone()
    return dict(flights=row[0],hours=round(row[1]/3600,2),
                grade=company_grade(row[0],row[1]/3600))

def weekly_progress(db,agreement,now):
    if not agreement:return None
    week=max(0,int((now-agreement['hired_utc'])//WEEK_SECONDS))
    row=db.conn.execute("""SELECT COUNT(*),COALESCE(SUM(duration_seconds),0)
        FROM airline_work WHERE agreement_id=? AND week=?""",
        (agreement['id'],week)).fetchone()
    stats=work_stats(db,agreement)
    salary=rate(agreement['employer'],db.pilot_stats()['level'],
                db.pilot_stats()['reputation'],stats['grade']['index'])[0]
    chosen=thresholds(agreement['employer'],agreement['tier'])
    frozen=db.conn.execute("""SELECT base_salary,base_xp FROM airline_week_rates
        WHERE agreement_id=? AND week=?""",(agreement['id'],week)).fetchone()
    return dict(week=week,flights=row[0],hours=round(row[1]/3600,2),
        required=chosen,basic=thresholds(agreement['employer'],0),
        tier=agreement['tier'],salary=frozen[0] if frozen else salary,
        ends_utc=agreement['hired_utc']+(week+1)*WEEK_SECONDS,
        grade=stats['grade'],all_flights=stats['flights'],
        all_hours=stats['hours'])

def _freeze_rate(db,agreement,week):
    stored=db.conn.execute("""SELECT base_salary,base_xp,tier
        FROM airline_week_rates WHERE agreement_id=? AND week=?""",
        (agreement['id'],week)).fetchone()
    if stored:return stored
    stats=work_stats(db,agreement)
    pilot=db.pilot_stats()
    base_salary,base_xp=rate(agreement['employer'],pilot['level'],
                             pilot['reputation'],stats['grade']['index'])
    db.conn.execute("""INSERT OR IGNORE INTO airline_week_rates
        (agreement_id,week,base_salary,base_xp,tier)
        VALUES(?,?,?,?,?)""",
        (agreement['id'],week,base_salary,base_xp,agreement['tier']))
    return (base_salary,base_xp,agreement['tier'])

def record_employee_flight(db,mission_id,flight_key,start,end):
    if not mission_id or not mission_id.startswith('EMP-'):return False
    active=active_agreement(db)
    if not active or db.employment_state()['mode']!='empregado':return False
    if not mission_id.startswith('EMP-'+active['employer']+'-'):return False
    if start<active['hired_utc'] or (active['resigned_utc'] and start>=active['resigned_utc']):return False
    duration=float(end-start)
    if not isfinite(duration) or not 60<=duration<=24*3600:return False
    week=int((start-active['hired_utc'])//WEEK_SECONDS)
    # A flight spanning a week boundary belongs to takeoff week's roster.
    previous_grade=work_stats(db,active)['grade']
    _freeze_rate(db,active,week)
    cursor=db.conn.execute("""INSERT OR IGNORE INTO airline_work(
        flight_key,agreement_id,employer,week,duration_seconds,mission_id,completed_utc)
        VALUES (?,?,?,?,?,?,?)""",
        (flight_key,active['id'],active['employer'],week,duration,mission_id,end))
    if cursor.rowcount==1:
        new_grade=work_stats(db,active)['grade']
        if new_grade['index']>previous_grade['index']:
            db.conn.execute("""INSERT OR IGNORE INTO airline_promotions
                (agreement_id,flight_key,grade,title,awarded_utc)
                VALUES(?,?,?,?,?)""",
                (active['id'],flight_key,new_grade['code'],new_grade['title'],end))
    return cursor.rowcount==1

def promotions(db,agreement):
    return [dict(id=r[0],grade=r[1],title=r[2],when=r[3])
            for r in db.conn.execute("""SELECT id,grade,title,awarded_utc
                 FROM airline_promotions WHERE agreement_id=?
                 ORDER BY id DESC LIMIT 30""",(agreement['id'],))]

def migrate_legacy_company(db):
    """Pre-v0.8.5 foundations stay valid without inventing a new R$400k."""
    state=db.employment_state()
    if state['mode']!='empresario' or company_account(db):return
    pilot=db.get_pilot()
    if not pilot:return
    with db.conn:
        db.conn.execute("""INSERT OR IGNORE INTO airline_company
           (id,name,callsign,home_icao,founded_utc,balance,reputation)
           VALUES(1,?,?,?,?,0,50)""",
           (state['owner_company'] or 'Minha Companhia',
            pilot['callsign'],pilot['home_icao'],time()))
        db.conn.execute("""INSERT OR IGNORE INTO airline_company_ledger
           (event_key,kind,amount,balance_after,description,created_utc)
           VALUES('legacy:foundation','migracao',0,0,
                  'Companhia anterior à conta empresarial — capital histórico não presumido',?)""",
           (time(),))

def payroll(db,now):
    """Only completed employment weeks; exactly-once salary+XP settlement."""
    if not isfinite(now) or now<0:raise ValueError('Data inválida.')
    result=[]
    agreements=db.conn.execute("""SELECT id,employer,hired_utc,resigned_utc,tier FROM airline_agreements
        ORDER BY id""").fetchall()
    for aid,company,hired,left,tier in agreements:
        cutoff=now if left is None else min(now,left)
        maxweek=int((cutoff-hired)//WEEK_SECONDS)-1
        if maxweek<0:continue
        # Only weeks with actual company flights need rows; no passive income.
        weeks=db.conn.execute("""SELECT week,COUNT(*),COALESCE(SUM(duration_seconds),0)
             FROM airline_work WHERE agreement_id=? AND week<=?
             GROUP BY week ORDER BY week""",(aid,maxweek)).fetchall()
        for week,flights,seconds in weeks:
            with db.conn:
                if db.conn.execute("""SELECT 1 FROM airline_payroll
                   WHERE agreement_id=? AND week=?""",(aid,week)).fetchone():continue
                frozen=db.conn.execute("""SELECT base_salary,base_xp,tier FROM airline_week_rates
                    WHERE agreement_id=? AND week=?""",(aid,week)).fetchone()
                if frozen is None:continue
                calculated=evaluate(frozen[2],flights,seconds/3600,company,
                                    frozen[0],frozen[1])
                db.conn.execute("""INSERT INTO airline_payroll VALUES(?,?,?,?,?,?,?,?,?)""",
                    (aid,week,flights,seconds,frozen[2],calculated['salary'],
                     calculated['xp'],calculated['result'],now))
                if calculated['salary']:
                    db._money_movement('salary:'+str(aid)+':'+str(week),'salario',
                        calculated['salary'],'Salário semanal • '+EMPLOYER_BY_CODE[company].name)
                if calculated['xp']:
                    db.conn.execute("""INSERT OR IGNORE INTO pilot_xp_ledger
                        (flight_key,xp,awarded_utc) VALUES(?,?,?)""",
                        ('salary:'+str(aid)+':'+str(week),calculated['xp'],now))
                result.append(dict(company=company,week=week,**calculated))
    return result

def company_account(db):
    row=db.conn.execute("""SELECT name,callsign,home_icao,founded_utc,balance,reputation
        FROM airline_company WHERE id=1""").fetchone()
    if row:
        return dict(zip(('name','callsign','home_icao','founded_utc','balance','reputation'),row))
    return None

def _company_move(db,key,kind,amount,description,now):
    account=company_account(db)
    if account is None:raise ValueError('Companhia inexistente.')
    if db.conn.execute("SELECT 1 FROM airline_company_ledger WHERE event_key=?",(key,)).fetchone():
        raise ValueError('Movimentação empresarial já lançada.')
    newbalance=account['balance']+int(amount)
    db.conn.execute("UPDATE airline_company SET balance=? WHERE id=1",(newbalance,))
    db.conn.execute("""INSERT INTO airline_company_ledger(
        event_key,kind,amount,balance_after,description,created_utc)
        VALUES(?,?,?,?,?,?)""",(key,kind,int(amount),newbalance,description,now))
    return newbalance

def found_company(db,name,home,now):
    from .employment import valid_company_name
    from .finance import brl
    name=valid_company_name(name)
    if not re.fullmatch(r'[A-Z0-9]{4}',home):raise ValueError('ICAO da sede inválido')
    if db.employment_state()['mode']!='autonomo':
        raise ValueError('Para fundar, encerre o vínculo profissional.')
    pilot=db.get_pilot()
    if pilot is None:raise ValueError('Cadastre o piloto primeiro.')
    stats=db.pilot_stats()
    if stats['level']<18 or stats['hours']<25 or 'PLA' not in stats['qualifications']:
        raise ValueError('Requisitos: nível 18, 25 horas e habilitação PLA.')
    if company_account(db) is not None:raise ValueError('Companhia já fundada.')
    with db.conn:
        if int(db.get_setting('balance') or 0)<OWN_INVESTMENT:
            raise ValueError('Capital mínimo: '+brl(OWN_INVESTMENT)+'.')
        # Transfer, not a fictitious expense; corporate equity belongs to a
        # separate account and cannot pay personal loans or aircraft.
        db._money_movement('company:capital:1','fundacao',-OWN_INVESTMENT,
                           'Aporte inicial da companhia '+name)
        db.conn.execute("""INSERT INTO airline_company VALUES(1,?,?,?,?,?,50)""",
                        (name,pilot['callsign'],home,now,OWN_INVESTMENT))
        _company_move_from_founding(db,OWN_INVESTMENT,now)
        db.conn.execute("""UPDATE career_status SET
            mode='empresario',employer_code=NULL,owner_company=?,updated_utc=?
            WHERE id=1""",(name,now))
    return company_account(db)

def _company_move_from_founding(db,amount,now):
    db.conn.execute("""INSERT INTO airline_company_ledger(
        event_key,kind,amount,balance_after,description,created_utc)
        VALUES ('equity:founding','aporte',?,?,?,?)""",
        (amount,amount,'Capital próprio transferido na fundação',now))

def purchase_company_aircraft(db,code,now):
    plane=AIRCRAFT_ECONOMY.get(code)
    company=company_account(db)
    if not company or db.employment_state()['mode']!='empresario':
        raise ValueError('Companhia própria não está ativa.')
    if not plane:raise ValueError('Modelo de aeronave inválido.')
    if company['balance']<plane.purchase_price:
        raise ValueError('Caixa empresarial insuficiente para comprar esta aeronave.')
    with db.conn:
        cursor=db.conn.execute("""INSERT INTO airline_company_aircraft(
            code,title,airport,condition,hours,purchase_price,bought_utc)
            VALUES(?,?,?,100,0,?,?)""",
            (code,plane.title,company['home_icao'],plane.purchase_price,now))
        _company_move(db,'plane:'+str(cursor.lastrowid),'compra_aviao',
                      -plane.purchase_price,'Aquisição empresarial '+plane.title,now)
    return cursor.lastrowid

def business_planes(db):
    return [dict(id=r[0],code=r[1],title=r[2],airport=r[3],
                 condition=r[4],hours=r[5],purchase_price=r[6])
        for r in db.conn.execute("""SELECT id,code,title,airport,condition,hours,purchase_price
            FROM airline_company_aircraft ORDER BY id""")]

def company_routes(db,center,catalog,period):
    company=company_account(db)
    if not company or db.employment_state()['mode']!='empresario' or not center or not catalog:
        return []
    owned=[x for x in business_planes(db) if x['airport']==center.icao and x['condition']>=15]
    if not owned:return []
    choices=[(a,d) for a,d in catalog.around(center,180) if 12<=d<=165]
    rng=Random(int.from_bytes(sha256(
        ('own:'+str(period)+':'+center.icao).encode()).digest()[:8],'big'))
    rng.shuffle(choices)
    missions=[]
    for plane in owned[:3]:
        for i,(airport,distance) in enumerate(choices[:2]):
            reward=market_reward(distance,1.7+company['reputation']/175,
                                 level=db.pilot_stats()['level'],
                                 reputation=db.pilot_stats()['reputation'])
            missions.append(Mission(
                'OWN-'+str(plane['id'])+'-'+center.icao+'-'+str(period)+'-'+str(i),
                center.icao,airport.icao,company['name']+' • operação comercial',
                reward,category='cargo',freelance=True,employer_plane=plane['code'],
                origin_lat=center.latitude,origin_lon=center.longitude,
                destination_lat=airport.latitude,destination_lon=airport.longitude,
                company_code='OWN'))
    return missions[:6]

def settle_company_flight(db,mission_id,flight_key,reward,start,end,model,arrival,fuel_start,fuel_end):
    if not mission_id or not mission_id.startswith('OWN-'):return False
    account=company_account(db)
    if not account or db.employment_state()['mode']!='empresario':return False
    match=re.fullmatch(r'OWN-([0-9]+)-([A-Z0-9]{4})-[0-9]+-[0-9]+',mission_id)
    if not match or start<account['founded_utc']:return False
    plane=db.conn.execute("""SELECT code,condition,hours,airport
        FROM airline_company_aircraft WHERE id=?""",(int(match[1]),)).fetchone()
    if not plane or plane[0]!=model or plane[3]!=match[2]:return False
    if not arrival or not re.fullmatch(r'[A-Z0-9]{4}',arrival):return False
    if db.conn.execute("SELECT 1 FROM airline_company_ledger WHERE event_key=?",
                       (flight_key+':income',)).fetchone():return False
    costs=flight_operating_cost(model,end-start,fuel_start,fuel_end)
    total=int(costs['fuel_brl'])+int(costs['airport_brl'])
    if reward<=0:return False
    _company_move(db,flight_key+':income','operacao',reward,
                  'Receita de voo '+mission_id,end)
    for key,label in [('fuel_brl','combustivel'),('airport_brl','taxa_aeroporto')]:
        amount=int(costs[key])
        if amount:
            _company_move(db,flight_key+':'+label,label,-amount,
                          'Custo do voo '+mission_id,end)
    db.conn.execute("""UPDATE airline_company_aircraft SET airport=?,
        condition=max(0,condition-?),hours=hours+? WHERE id=?""",
        (arrival,costs['wear'],(end-start)/3600,int(match[1])))
    db.conn.execute("""UPDATE airline_company SET reputation=min(100,reputation+1)
        WHERE id=1""")
    return True

def business_snapshot(db):
    account=company_account(db)
    if not account:return None
    log=[dict(kind=r[0],amount=r[1],balance_after=r[2],
              description=r[3],when=r[4]) for r in db.conn.execute(
        """SELECT kind,amount,balance_after,description,created_utc
        FROM airline_company_ledger ORDER BY id DESC LIMIT 60""")]
    flown=db.conn.execute("""SELECT COUNT(*) FROM airline_company_ledger
                            WHERE kind='operacao'""").fetchone()[0]
    return dict(**account,planes=business_planes(db),operations=flown,transactions=log)
