"""Financial Center 0.8.4 — read-only accounting projections over the career ledger.

Never derive a new wallet: cash stays in settings.balance and every mutation
continues through Storage's transactional ledger. All figures are game BRL.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timezone
from .fleet import resale_price

INCOME_KINDS = frozenset(('contrato', 'bonus_realismo', 'penalidade_combustivel',
                          'salario', 'pagamento_empresa'))
OPERATING_COSTS = frozenset(('combustivel', 'taxa_aeroporto', 'taxa_simulada',
                              'seguro', 'abastecimento', 'manutencao', 'aluguel'))
CAPITAL_KINDS = frozenset(('compra_aviao', 'venda_aviao', 'financiamento',
                            'parcela', 'fundacao'))
LABELS = {
    'contrato':'Contrato', 'bonus_realismo':'Bônus de realismo',
    'penalidade_combustivel':'Penalidade de combustível',
    'salario':'Salário', 'pagamento_empresa':'Companhia',
    'combustivel':'Combustível em voo', 'abastecimento':'Abastecimento',
    'taxa_aeroporto':'Taxa de aeroporto', 'taxa_simulada':'Imposto opcional',
    'seguro':'Seguro de aeronave', 'manutencao':'Manutenção',
    'aluguel':'Aluguel', 'compra_aviao':'Compra de aeronave',
    'venda_aviao':'Venda de aeronave', 'financiamento':'Financiamento',
    'parcela':'Pagamento de dívida', 'fundacao':'Investimento em companhia',
}

def category(kind):
    if kind in INCOME_KINDS:
        return 'receita'
    if kind in OPERATING_COSTS:
        return 'operacional'
    if kind in CAPITAL_KINDS:
        return 'patrimonio'
    return 'outros'

def records(db, *, limit=None):
    sql = """SELECT id,event_key,kind,amount,balance_after,description,occurred_utc
             FROM finance_ledger ORDER BY id DESC"""
    if limit is not None:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Limite inválido")
        sql += " LIMIT ?"
        rows = db.conn.execute(sql, (limit,)).fetchall()
    else:
        rows = db.conn.execute(sql).fetchall()
    return [
        dict(id=r[0],event_key=r[1],kind=r[2],label=LABELS.get(r[2],r[2]),
             category=category(r[2]),amount=r[3],balance_after=r[4],
             description=r[5],occurred_utc=r[6])
        for r in rows
    ]

def snapshot(db):
    """Read-only finance state for the Midnight interface; never estimates history."""
    balance=int(db.get_setting('balance') or 0)
    totals=defaultdict(int)
    by_month=defaultdict(lambda:defaultdict(int))
    costs_by_kind=defaultdict(int)
    for kind,amount,timestamp in db.conn.execute(
            "SELECT kind,amount,occurred_utc FROM finance_ledger ORDER BY id"):
        if kind in INCOME_KINDS:
            totals['income'] += amount
        elif kind in OPERATING_COSTS:
            totals['expense'] += -amount
            costs_by_kind[kind] += -amount
        if kind in INCOME_KINDS or kind in OPERATING_COSTS:
            month=datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m')
            by_month[month]['income' if kind in INCOME_KINDS else 'expense'] += (
                amount if kind in INCOME_KINDS else -amount)
    units=[p for p in db.fleet_manager().all() if p['kind'] in ('new','used')]
    fleet_value=sum(resale_price(p) for p in units)
    invested=sum(int(p['price_paid']) for p in units)
    debt=db.outstanding_loan()
    contracts=db.conn.execute("SELECT COUNT(*) FROM completed_contracts").fetchone()[0]
    # Explicitly no sale estimate for starter / old non-sellable aircraft or rentals.
    assets=[dict(ref=p['ref'],title=p['title'],kind=p['kind'],
                 purchase_price=p['price_paid'],resale_price=resale_price(p),
                 condition=p['condition'],airport=p['airport'],insured=bool(p['insured']))
            for p in units]
    legacy=[p for p in db.fleet_manager().all() if p['kind'] in ('starter','legacy')]
    assets.extend(dict(ref=p['ref'],title=p['title'],kind=p['kind'],
                       purchase_price=None,resale_price=None,condition=p['condition'],
                       airport=p['airport'],insured=bool(p['insured']))
                  for p in legacy)
    # Financial operation breakdown by actual flight ledger key; no speculative data.
    operations=[]
    flights=db.conn.execute(
        """SELECT id,flight_key,started_utc,ended_utc,mission_id,aircraft_title
           FROM flights ORDER BY id DESC LIMIT 100""").fetchall()
    for flight_id,key,start,end,mission,aircraft in flights:
        amounts=defaultdict(int)
        if key:
            for kind,amount in db.conn.execute(
                "SELECT kind,amount FROM finance_ledger WHERE event_key LIKE ?",
                (key+':%',)):
                amounts[kind]+=amount
        income=sum(v for k,v in amounts.items() if k in INCOME_KINDS)
        expense=-sum(v for k,v in amounts.items() if k in OPERATING_COSTS)
        operations.append(dict(id=flight_id,flight_key=key,mission=mission,
                               aircraft=aircraft or 'Não identificado',
                               started_utc=start,ended_utc=end,
                               gross=income,expenses=expense,net=income-expense,
                               bonus=amounts.get('bonus_realismo',0),
                               fuel=-amounts.get('combustivel',0),
                               airport=-amounts.get('taxa_aeroporto',0),
                               tax=-amounts.get('taxa_simulada',0),
                               paid=bool(income or expense)))
    month_items=[dict(month=m,income=v['income'],expense=v['expense'],
                      net=v['income']-v['expense'])
                 for m,v in sorted(by_month.items())[-12:]]
    expenses=[dict(kind=k,label=LABELS.get(k,k),value=v)
              for k,v in sorted(costs_by_kind.items(),key=lambda item:-item[1]) if v>0]
    return {
        'balance':balance,'income':totals['income'],'expenses':totals['expense'],
        'operating_net':totals['income']-totals['expense'],
        'assets_value':fleet_value,'invested':invested,'debt':debt,
        'net_worth':balance+fleet_value-debt,
        'assets':assets,'transactions':records(db,limit=500),
        'total_transactions':db.conn.execute(
            "SELECT COUNT(*) FROM finance_ledger").fetchone()[0],
        'operations':operations,'monthly':month_items,'expense_categories':expenses,
        'contracts_completed':contracts,
        'income_tax_enabled':db.get_setting('income_tax_enabled')=='1',
        'loan_limit':150000,'loan_rate':0.08,
        'loan_open':debt>0,
        'notice':None
    }

def export_csv(db):
    """All ledger rows, without silently truncating to the UI's recent 500."""
    buffer=io.StringIO(newline='')
    writer=csv.writer(buffer,delimiter=';')
    writer.writerow(('ID','Data UTC','Categoria','Tipo','Descrição',
                     'Valor (R$)','Saldo após (R$)','Chave do evento'))
    for event in reversed(records(db)):
        writer.writerow((
            event['id'],
            datetime.fromtimestamp(event['occurred_utc'],tz=timezone.utc).strftime(
                '%Y-%m-%d %H:%M:%S UTC'),
            event['category'],event['label'],event['description'],event['amount'],
            event['balance_after'],event['event_key']))
    return ('\ufeff'+buffer.getvalue()).encode('utf-8')
