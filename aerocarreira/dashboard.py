"""Midnight presentation adapter. Only the Tk owner thread accesses the engine/SQLite."""
from __future__ import annotations
import base64
import os
import json
from pathlib import Path
from time import time
from .contracts import AirportCatalog, generate_offers, eligibility, TYPE_BY_CODE, next_level_xp, aircraft_model, PLANE_BY_CODE
from .employment import generate_employer_routes
from .pilot import level_progress
from .domain import AIRPORTS, Phase, distance_nm
from .planning import inspect_preflight
from .flight_audit import real_clock_verified, assistance_verified
from .finance import estimated_minutes, AIRCRAFT_ECONOMY
from .reputation import pilot_reputation
from .weather import MetarCache, sim_conditions, within_nm


def coordinates(m):
    a, b = AIRPORTS.get(m.origin), AIRPORTS.get(m.destination)
    start = [m.origin_lat, m.origin_lon] if m.origin_lat is not None else ([a.latitude,a.longitude] if a else None)
    end = [m.destination_lat, m.destination_lon] if m.destination_lat is not None else ([b.latitude,b.longitude] if b else None)
    return start,end


def mission_data(m, aircraft_code=None):
    """Tempo aproximado com a aeronave designada, nunca um número inventado pela interface."""
    a,b=coordinates(m)
    distance=distance_nm(*a,*b) if a and b else None
    chosen=m.employer_plane if m.freelance else aircraft_code
    model=AIRCRAFT_ECONOMY.get(chosen or '')
    cruise_kts=model.cruise_kts if model else 90
    name=model.title if model else 'Aeronave não identificada • referência 90 kt'
    return {'id':m.id,'origin':m.origin,'destination':m.destination,'title':m.title,
            'category': TYPE_BY_CODE[m.category].title if m.category in TYPE_BY_CODE else m.title,
            'reward':m.reward,'start':a,'end':b,'distance':distance,
            'minutes':estimated_minutes(distance,cruise_kts) if distance is not None else None,
            'cruise_kts':cruise_kts,'aircraft_label':name,
            'freelance':bool(m.freelance),
            'employer_plane':m.employer_plane,
            'company_code':m.company_code}


class DashboardPresenter:
    def __init__(self, app):
        self.app=app
        self.offers={}
        self.center=None
        self.market_key=None
        self.avatar_key=None
        self.avatar=None
        self.reputation_stamp=None
        self.reputation_value=None
        self.metars=MetarCache()
        self.origin_observation=None
        self.weather_mission_id=None
        self.country_cache={}
        self.position_lookup=None
        self.position_center=None
        self.position_lookup_at=0.0

    def country(self, home):
        if home in self.country_cache:return self.country_cache[home]
        country=None
        try:
            import airportsdata
            country=airportsdata.load('ICAO').get(home,{}).get('country')
        except (ImportError,ValueError,OSError):pass
        if home in AIRPORTS:country='BR'
        self.country_cache[home]=country
        return country

    def refresh_market(self, force=False):
        app=self.app; db=app.storage
        pilot=db.get_pilot()
        if not pilot:
            self.offers={};self.center=None;return
        if app.airport_catalog is None:app.airport_catalog=AirportCatalog()
        cat=app.airport_catalog;s=app.last_sample
        center=None
        if s and app.connected:
            position=(s.latitude,s.longitude)
            moved=self.position_lookup is None or abs(position[0]-self.position_lookup[0])>.02 or abs(position[1]-self.position_lookup[1])>.02
            if force or self.position_lookup is None or (moved and time()-self.position_lookup_at>=10):
                self.position_center=cat.nearest(*position,6)
                self.position_lookup=position;self.position_lookup_at=time()
            center=self.position_center
        center=center or cat.locations.get(pilot['home_icao'])
        self.center=center
        if not center:self.offers={};return
        stats=db.pilot_stats(); emp=db.employment_state();now=time();day=int(now//86400)
        generator_version='nordeste-v1'
        key=(center.icao,day,stats['xp'],tuple(sorted(stats['qualifications'])),emp['mode'],
             emp['employer_code'],generator_version)
        if key==self.market_key and not force:
            self.offers={k:v for k,v in self.offers.items() if not db.contract_completed(k)}
            return
        self.market_key=key
        if force or db.get_setting('offer_generator')!=generator_version or not db.offer_cache_valid(center.icao,now):
            offers=generate_offers(center,cat,stats,db.owned_qualifications(),db.family_experience(),day)
            if emp['mode']=='empregado':
                offers+=generate_employer_routes(emp['employer_code'],center,cat,stats,db.owned_qualifications(),db.family_experience(),day)
            db.save_offers(center.icao,offers,now=now,valid_s=(day+1)*86400-now)
            db.set_setting('offer_generator',generator_version)
        self.offers={m.id:m for m in db.active_offers(center.icao,now)
                     if not m.company_code or (emp['mode']=='empregado' and emp['employer_code']==m.company_code)}

    def snapshot(self):
        app=self.app;db=app.storage
        self.refresh_market()
        pilot=db.get_pilot();stats=db.pilot_stats();progress=level_progress(stats['xp'])
        start=0 if progress['level']==1 else next_level_xp(progress['level']-1)
        stats['qualifications']=sorted(stats['qualifications'])
        progress.update(xp=stats['xp']-start,target=stats['next_level_xp']-start)
        plane=db.fleet_manager().selected()
        fuel=app.fuel_manager.get(plane['ref']) if plane else None
        s=app.last_sample;m=app.career.mission;plan=app._saved_preflight()
        if m and m.freelance and m.employer_plane in PLANE_BY_CODE:
            assigned=PLANE_BY_CODE[m.employer_plane]
            plane={'ref':'contract:'+m.id,'code':m.employer_plane,'title':assigned.name,
                   'condition':None,'airport':m.origin,'kind':'Aeronave do contratante'}
            fuel=app.fuel_manager.get(plane['ref'])
        verified=({'clock':real_clock_verified(s),'assists':assistance_verified(s)}
                  if s and app.mode=='MSFS' and app.connected and time()-s.timestamp<10 else {})
        bonus=inspect_preflight(m,plan,verified=verified) if m and plan else None
        if app.tracker.phase==Phase.AIRBORNE:
            bonus= dict(bonus or {},bonus_fraction=app.realism_frozen,frozen=True)
        rows=db.conn.execute("SELECT kind, SUM(amount) FROM finance_ledger GROUP BY kind").fetchall()
        ledger=dict(rows)
        # Only flight revenues/expenses, excluding starting cash, loans, purchases and sales.
        flight_kinds=('contrato','bonus_realismo','penalidade_combustivel','combustivel','taxa_aeroporto','taxa_simulada','seguro','abastecimento','manutencao','aluguel')
        # O Dashboard consulta a cada 250 ms: recalcular apenas quando entra voo novo.
        flight_stamp=db.conn.execute('SELECT COALESCE(MAX(id),0),COUNT(*) FROM flights').fetchone()
        if self.reputation_stamp!=flight_stamp:
            self.reputation_value=pilot_reputation(db.conn)
            self.reputation_stamp=flight_stamp
        summary=dict(stats,net=sum(ledger.get(k,0) for k in flight_kinds),bonus=ledger.get('bonus_realismo',0),
                     reputation=self.reputation_value)
        offers=[]
        for offer in self.offers.values():
            allowed,reason=eligibility(offer,stats,db.owned_qualifications(),db.family_experience())
            offers.append(dict(mission_data(offer, plane['code'] if plane else None),
                               allowed=allowed,reason=reason))
        avatar_path=db.get_setting('pilot_avatar_v1')
        if avatar_path!=self.avatar_key:
            self.avatar_key=avatar_path;self.avatar=None
            if avatar_path:
                try:self.avatar='data:image/png;base64,'+base64.b64encode(Path(avatar_path).read_bytes()).decode()
                except OSError:pass
        capacity=sum(fuel['capacities'].values()) if fuel and fuel['capacities'] else None
        quantity=sum(fuel['tanks'].values()) if fuel else None
        if (m.id if m else None)!=self.weather_mission_id:
            self.weather_mission_id=m.id if m else None
            self.origin_observation=None
        reading=sim_conditions(s) if app.mode=='MSFS' and app.connected and s and time()-s.timestamp<10 else None
        close_origin=bool(reading and m and within_nm(s.latitude,s.longitude,m.origin_lat,m.origin_lon,m.origin))
        close_destination=bool(reading and m and within_nm(s.latitude,s.longitude,m.destination_lat,m.destination_lon,m.destination))
        if close_origin:
            self.origin_observation=dict(reading,icao=m.origin,source='MSFS • aeronave na origem')
        destination_metar=self.metars.get(m.destination) if m and app.mode!='Demo' else None
        weather=dict(origin=self.origin_observation if m else None,
                     nearby_origin=close_origin,nearby_destination=close_destination,
                     destination_sim=dict(reading,icao=m.destination,source='MSFS • aeronave perto do destino') if close_destination else None,
                     destination_metar=destination_metar,
                     source_note='SimConnect lê condições na aeronave; não o METAR integral do aeroporto.')
        telemetry=None if s is None else dict(ias=s.ias_kt,gs=s.groundspeed_kt,alt=s.altitude_ft,agl=s.agl_ft,vs=s.vs_fpm,
            lat=s.latitude,lon=s.longitude,heading_deg=s.heading_true_deg,
            heading_magnetic_deg=s.heading_magnetic_deg,
            on_any_runway=s.on_any_runway,
            stale=app.mode!='Demo' and (not app.connected or time()-s.timestamp>10))
        return dict(pilot=pilot,country=self.country(pilot['home_icao']) if pilot else None,avatar=self.avatar,
            employment=db.employment_state()['mode'],progress=progress,balance=int(db.get_setting('balance') or 0),
            connection='connected' if app.connected else ('reconnecting' if app.mode=='MSFS' else 'disconnected'),
            status=app.status_var.get(),mode=app.mode,weather=weather,summary=summary,
            mission=mission_data(m, plane['code'] if plane else None) if m else None,
            market=dict(icao=self.center.icao,name=self.center.name,lat=self.center.latitude,lon=self.center.longitude) if self.center else None,offers=offers,
            plane=plane,fuel=dict(enabled=db.get_setting('fuel_control_enabled')=='1',quantity=quantity,
            capacity=capacity,
            refundable_liters=app.fuel_manager.refundable_liters(plane['ref']) if plane else 0.0,
            live=s.fuel_gallons if s else None),telemetry=telemetry,phase=app.phase_var.get(),bonus=bonus,
            payload=dict(confirmed=getattr(app,'payload_confirmed',None)==m.id if m else False,
                         pending=bool(getattr(app,'payload_pending',None)) if m else False,
                         kg=m.payload_kg if m else 0,manifest=m.manifest if m else ''),
            alerts=([dict(kind='fuel',message=f'Combustível em {quantity/capacity:.0%}. Abasteça em breve.')
                     for _ in [0] if capacity and quantity is not None and quantity/capacity<=.20] +
                    [dict(kind='wear',message=f'Integridade da aeronave em {plane["condition"]:.1f}%. Faça manutenção.')
                     for _ in [0] if plane and plane.get('condition') is not None and plane['condition']<=20]),
            log=app.log_text.get('1.0','end').splitlines()[-50:],
            audit=dict(clock=verified.get('clock'),assists=verified.get('assists'),
                weather=None,go_arounds=app.tracker.go_arounds,
                touch_and_go=app.tracker.touch_and_go,
                taxi_violations=app.tracker.taxi_violations,
                hard_g_events=app.tracker.hard_g_events))
