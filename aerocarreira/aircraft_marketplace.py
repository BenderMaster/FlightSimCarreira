"""Mercado fictício de aeronaves: somente catálogo econômico conhecido.

Os aeroportos de transação vêm EXCLUSIVAMENTE da lista da sessão MSFS ou
do catálogo artificial do modo Demo. Preços e transações são validados no
backend; HTML nunca determina valor, estado, existência ou propriedade.
"""
from __future__ import annotations
import re
from time import time

from .domain import Phase, distance_nm
from .finance import AIRCRAFT_ECONOMY
from .fleet import rental_fee, resale_price, used_market
from .fleet_photos import owned_fleet

DURATIONS=(24,48,72,168)
REQUEST_RE=re.compile(r'[a-f0-9-]{36}\Z')


def market_location(app, center, now=None):
    now=time() if now is None else now
    if app.storage.get_pilot() is None:return None,'Cadastre o piloto para negociar aeronaves.'
    if app.mode=='Demo':
        return (center.icao,None) if center else (None,'Aguardando aeroporto da demonstração.')
    if app.mode!='MSFS' or not app.connected:
        return None,'Conecte o MSFS para confirmar o aeródromo da negociação.'
    if not getattr(app,'msfs_airports_ready',False) or not app.airport_catalog:
        return None,'Aguardando a lista oficial de aeródromos desta sessão do MSFS.'
    if not center or center.icao not in app.airport_catalog.locations:
        return None,'Nenhum aeródromo verificado próximo à aeronave.'
    sample=app.last_sample
    if (not sample or now-sample.timestamp>10 or not sample.on_ground):
        return None,'A aeronave precisa estar conectada e em solo com telemetria recente.'
    if distance_nm(sample.latitude,sample.longitude,center.latitude,center.longitude)>6:
        return None,'Aproxime-se de um aeródromo confirmado pelo MSFS para negociar.'
    return center.icao,None


def market_state(app,center,now=None):
    now=time() if now is None else now
    icao,reason=market_location(app,center,now)
    in_flight=app.tracker.phase==Phase.AIRBORNE
    if in_flight:reason='Operações financeiras indisponíveis durante o voo.'
    elif app.career.mission is not None:reason='Conclua ou cancele o contrato ativo antes de negociar aeronaves.'
    ready=bool(icao and not reason)
    week=int(now//(7*86400))
    db=app.storage
    models=[dict(code=p.code,title=p.title,price=p.purchase_price,
                 fuel_capacity_gal=p.fuel_capacity_gal,cruise_kts=p.cruise_kts,
                 service_cost=p.service_cost,condition=100,hours=0,
                 rental_prices={str(h):rental_fee(p.code,h) for h in DURATIONS})
            for p in AIRCRAFT_ECONOMY.values()]
    used=[]
    if icao:
        for offer in used_market(icao,week):
            sold=bool(db.conn.execute("""SELECT 1 FROM fleet_log WHERE aircraft_ref=?
                 AND kind='used_purchase' LIMIT 1""",(offer.offer_id,)).fetchone())
            used.append(dict(id=offer.offer_id,code=offer.code,title=offer.title,
                price=offer.price,condition=offer.condition,hours=offer.hours,
                airport=offer.airport,sold=sold))
    mine=[]
    for plane in owned_fleet(db):
        saleable=plane['ref'].startswith('unit:')
        mine.append(dict(ref=plane['ref'],title=plane['title'],code=plane['code'],
            airport=plane['airport'],condition=plane['condition'],hours=plane['hours'],
            kind=plane['kind'],saleable=saleable,
            resale_price=resale_price(plane) if saleable else 0,
            is_active=db.get_setting('active_aircraft_ref')==plane['ref']))
    rentals=[dict(ref=p['ref'],title=p['title'],airport=p['airport'],
                  expires=p['expires'],code=p['code'])
             for p in db.fleet_manager().all(now) if p['kind']=='rented']
    return dict(airport=icao,ready=ready,reason=reason or '',
                week=week,balance=int(db.get_setting('balance') or 0),
                models=models,used=used,owned=mine,rentals=rentals,
                hours=list(DURATIONS),mission_active=app.career.mission is not None,
                in_flight=in_flight,notice=getattr(app,'aircraft_market_notice',None))


def execute_market(app,center,action,raw,now=None):
    """Executa apenas intenção já confirmada pelo usuário, validando tudo."""
    now=time() if now is None else now
    if not isinstance(raw,str) or len(raw)>200:
        raise ValueError('Solicitação inválida.')
    chunks=raw.split('|')
    if len(chunks)<2 or REQUEST_RE.fullmatch(chunks[-1]) is None:
        raise ValueError('Identificador da operação inválido.')
    request_id=chunks[-1]
    snapshot=market_state(app,center,now)
    if not snapshot['ready']:
        raise ValueError(snapshot['reason'] or 'Mercado indisponível.')
    airport=snapshot['airport']
    fm=app.storage.fleet_manager()
    if action=='aircraft_buy_new':
        if len(chunks)!=2 or chunks[0] not in AIRCRAFT_ECONOMY:
            raise ValueError('Modelo não encontrado no catálogo.')
        purchased=fm.purchase(chunks[0],airport,request_id=request_id)
        outcome='Compra concluída: '+purchased['title']
    elif action=='aircraft_buy_used':
        if len(chunks)!=2:
            raise ValueError('Oferta inválida.')
        offers={o.offer_id:o for o in used_market(airport,snapshot['week'])}
        offer=offers.get(chunks[0])
        if not offer:
            raise ValueError('Oferta usada indisponível neste aeroporto ou semana.')
        purchased=fm.purchase(offer.code,airport,offer=offer,request_id=request_id)
        outcome='Compra usada concluída: '+purchased['title']
    elif action=='aircraft_rent':
        if len(chunks)!=3 or chunks[0] not in AIRCRAFT_ECONOMY:
            raise ValueError('Modelo de aluguel inválido.')
        try:hours=int(chunks[1])
        except ValueError:raise ValueError('Duração inválida.') from None
        if str(hours)!=chunks[1] or hours not in DURATIONS:
            raise ValueError('Prazo não ofertado pelo mercado.')
        rented=fm.rent(chunks[0],airport,hours,request_id=request_id)
        outcome='Aluguel de '+rented['title']+' por '+str(hours)+'h confirmado'
    elif action=='aircraft_sell':
        if len(chunks)!=2 or not chunks[0].startswith('unit:'):
            raise ValueError('Somente aeronaves adquiridas novas/usadas podem ser vendidas.')
        ref=chunks[0]
        plane=next((p for p in snapshot['owned'] if p['ref']==ref and p['saleable']),None)
        if not plane:
            raise ValueError('Aeronave não pertence à sua frota ou não pode ser vendida.')
        # Não permitir venda remota nem enquanto estiver no ar.
        if plane['airport']!=airport:
            raise ValueError('Aeronave está em '+plane['airport']+'; negocie no aeródromo onde ela está.')
        value=fm.sell(ref,request_id=request_id)
        outcome='Venda concluída: '+plane['title']+' por R$ '+format(value,',').replace(',','.')
    else:
        raise ValueError('Operação desconhecida.')
    app.career.balance=int(app.storage.get_setting('balance') or 0)
    app.balance_var.set(__import__('aerocarreira.finance',fromlist=['brl']).brl(app.career.balance))
    return outcome
