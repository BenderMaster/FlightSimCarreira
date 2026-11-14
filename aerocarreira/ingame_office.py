"""Safe, bounded snapshots for the MSFS Coherent InGame office.

Always called on the Tk/SQLite owner thread. JSON returned to the toolbar is
read-only; it cannot be used to authorize a transaction or verify flight state.
"""
from __future__ import annotations


def _fields(value, keys):
    if not isinstance(value, dict):
        return {}
    return {k: value[k] for k in keys if k in value}


def project(state):
    """Project existing desktop domain snapshots without copying private paths.

    Each collection is deliberately bounded to keep 1.5-second polling fast.
    The snapshot must come from DashboardPresenter.snapshot() on the Tk thread.
    """
    p=state.get('pilot_career') or {}
    f=state.get('financial_center') or {}
    h=state.get('flight_history') or {}
    a=state.get('airline_operations') or {}
    ops=state.get('flight_operations') or {}
    market=state.get('aircraft_market') or {}
    fleet=state.get('fleet') or {}
    plane=state.get('plane') or {}
    pilot=state.get('pilot') or {}

    return {
        'planning': {
            'draft':_fields(ops.get('draft'),('mode','origin','destination','altitude_ft','waypoints','checks')),
            'route':_fields(ops.get('route'),('origin','destination','altitude_ft','waypoints','checks','route',
                'legs','distance_nm','minutes','cruise_kts','fuel_required_gal','fuel_available_gal',
                'fuel_ok','weight_lbs','mtow_lbs','weight_ok')),
            'ready':bool(ops.get('ready')),
            'notice':_fields(ops.get('notice'),('ok','message','action','seq')),
            'dispatch':_fields(ops.get('dispatch'),('route','payload','message')),
        },
        'fleet': {
            'active_ref':fleet.get('active_ref'),
            'owned':[_fields(x,('ref','code','title','kind','condition','hours','airport','insured',
                'fuel_gallons','fuel_capacity','is_active')) for x in (fleet.get('owned') or [])[:40]],
            'selected':_fields(plane,('ref','code','title','condition','hours','airport','kind','insured')),
            'market':{
                'ready':bool(market.get('ready')),
                'reason':str(market.get('reason') or '')[:180],
                'airport':market.get('airport'),
                'models':[_fields(x,('code','title','price','service_cost','cruise_kts',
                    'fuel_capacity_gal','rental_prices')) for x in (market.get('models') or [])[:20]],
                'used':[_fields(x,('id','code','title','price','condition','hours','airport','sold'))
                        for x in (market.get('used') or [])[:20]],
                'owned':[_fields(x,('ref','title','airport','condition','resale_price','saleable','is_active'))
                         for x in (market.get('owned') or [])[:40]],
                'rentals':[_fields(x,('ref','title','code','airport','expires'))
                           for x in (market.get('rentals') or [])[:20]],
            }
        },
        'airlines': {
            'mode':a.get('mode'),
            'employment':_fields(a.get('employment'),('active','employer','tier','progress','started_utc')),
            'vacancies':[_fields(x,('id','name','company','fleet','salary','allowed','reason','targets',
                                    'min_level','min_hours')) for x in (a.get('vacancies') or [])[:20]],
            'type_ratings':[_fields(x,('code','title','rated','flights','required','installed'))
                            for x in (a.get('type_ratings') or [])[:60]],
            'business':_fields(a.get('business'),('balance','name','owner_company','reputation','planes','operations')),
            'applications':[_fields(x,('id','company','status','result','commitment','created_utc'))
                            for x in (a.get('applications') or [])[:15]],
            'corporate_offers':[_fields(x,('id','origin','destination','title','reward','allowed'))
                                for x in (a.get('corporate_offers') or [])[:15]],
            'employer_offers':[_fields(x,('id','origin','destination','title','reward','allowed'))
                               for x in (a.get('employer_offers') or [])[:15]],
            'investment':a.get('investment'),
        },
        'pilot':{
            'name':p.get('name') or pilot.get('name'),
            'callsign':pilot.get('callsign'),
            'home_icao':pilot.get('home_icao'),
            'level':p.get('level'),
            'rank':_fields(p.get('rank'),('title','code','min','max')),
            'reputation':p.get('reputation'),
            'xp':p.get('xp'),
            'progress':_fields(p.get('progress'),('fraction','remaining','level','next_level')),
            'flights':p.get('flights'),
            'hours':p.get('hours'),
            'contracts':p.get('contracts'),
            'medals':[_fields(x,('code','title','status','description','current','target'))
                      for x in (p.get('medals') or [])[:60]],
            'licenses':[_fields(x,('code','title','status','requirements','description'))
                        for x in (p.get('licenses') or [])[:30]],
            'type_ratings':[_fields(x,('code','title','rated','flights','required'))
                            for x in (a.get('type_ratings') or [])[:60]],
            'profiles':[_fields(x,('id','name','kind')) for x in (p.get('profiles') or [])[:20]],
            'active_profile':p.get('active_profile'),
        },
        'logbook':{
            'count':h.get('count',0),
            'flights':[_fields(x,('id','started_utc','ended_utc','hours','direct_nm','aircraft',
                'mission_id','touchdown_fpm','stalls','xp','personal_net','note'))
                for x in (h.get('flights') or [])[:35]],
        },
        'finances':{
            'balance':f.get('balance',0),
            'income':f.get('income',0),
            'expenses':f.get('expenses',0),
            'operating_net':f.get('operating_net',0),
            'assets_value':f.get('assets_value',0),
            'debt':f.get('debt',0),
            'net_worth':f.get('net_worth',0),
            'loan_limit':f.get('loan_limit',150000),
            'loan_rate':f.get('loan_rate',0.08),
            'income_tax_enabled':bool(f.get('income_tax_enabled')),
            'total_transactions':f.get('total_transactions',0),
            'transactions':[_fields(x,('id','label','kind','amount','balance_after','description','occurred_utc'))
                            for x in (f.get('transactions') or [])[:35]],
            'monthly':[_fields(x,('month','income','expense','net')) for x in (f.get('monthly') or [])[-12:]],
            'expense_categories':[_fields(x,('label','value')) for x in (f.get('expense_categories') or [])[:12]]
        }
    }
