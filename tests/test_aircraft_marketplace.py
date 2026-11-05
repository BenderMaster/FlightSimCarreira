"""Mercado de aeronaves: economia, origem MSFS, integridade e reconexão."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import unittest

from aerocarreira.aircraft_marketplace import market_state, execute_market, market_location
from aerocarreira.connection_notices import ReconnectWarningFilter
from aerocarreira.domain import AIRPORTS, Career, FlightTracker, Phase
from aerocarreira.fleet import rental_fee, used_market
from aerocarreira.finance import AIRCRAFT_ECONOMY
from aerocarreira.storage import Storage


def token():
    return str(uuid4())


class AircraftMarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.folder=TemporaryDirectory()
        self.db=Storage(Path(self.folder.name)/'save.db')
        self.db.create_pilot('Piloto QA','QA123','SBRF')
        self.db.claim_starter()
        self.db.fleet_manager().select('legacy:c152')
        self.db.set_setting('balance','10000000')
        self.app=SimpleNamespace(
            storage=self.db,career=Career(),tracker=FlightTracker(),
            mode='Demo',connected=False,last_sample=None,airport_catalog=None,
            msfs_airports_ready=False,balance_var=Mock())
        self.center=AIRPORTS['SBRF']
        self.now=time()

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def snapshot(self):
        return market_state(self.app,self.center,self.now)

    def transact(self,action,request):
        return execute_market(self.app,self.center,action,request,self.now)

    def test_new_purchase_is_applied_once_and_separate_from_rental(self):
        balance=self.snapshot()['balance']
        key=token()
        msg=self.transact('aircraft_buy_new','c172|'+key)
        self.assertIn('Compra concluída',msg)
        new=self.db.fleet_manager().selected()
        self.assertEqual(new['code'],'c172')
        self.assertTrue(new['ref'].startswith('unit:'))
        self.assertEqual(new['kind'],'new')
        self.assertEqual(int(self.db.get_setting('balance')),
                         balance-AIRCRAFT_ECONOMY['c172'].purchase_price)
        with self.assertRaisesRegex(ValueError,'já foi processada'):
            self.transact('aircraft_buy_new','c172|'+key)
        self.assertEqual(len([p for p in self.db.fleet_manager().all()
                              if p['kind']=='new']),1)

    def test_unaffordable_purchase_has_no_debit_no_request_tombstone(self):
        self.db.set_setting('balance','25')
        key=token()
        with self.assertRaisesRegex(ValueError,'Saldo insuficiente'):
            self.transact('aircraft_buy_new','c152|'+key)
        self.assertEqual(self.db.conn.execute('SELECT COUNT(*) FROM fleet_market_requests').fetchone()[0],0)
        self.assertEqual(self.db.get_setting('balance'),'25')
        self.db.set_setting('balance','100000')
        self.transact('aircraft_buy_new','c152|'+key)
        self.assertEqual(self.db.conn.execute('SELECT COUNT(*) FROM fleet_market_requests').fetchone()[0],1)

    def test_used_offer_single_sale_verified_price_week_and_origin(self):
        offer=used_market('SBRF',self.snapshot()['week'])[0]
        initial=int(self.db.get_setting('balance'))
        key=token()
        self.transact('aircraft_buy_used',offer.offer_id+'|'+key)
        self.assertEqual(int(self.db.get_setting('balance')),initial-offer.price)
        purchased=self.db.fleet_manager().selected()
        self.assertEqual((purchased['kind'],purchased['condition'],purchased['hours']),
                         ('used',offer.condition,offer.hours))
        sold=next(o for o in self.snapshot()['used'] if o['id']==offer.offer_id)
        self.assertTrue(sold['sold'])
        with self.assertRaises(ValueError):
            self.transact('aircraft_buy_used',offer.offer_id+'|'+token())
        self.assertEqual(int(self.db.get_setting('balance')),initial-offer.price)
        self.center=AIRPORTS['SBJP']
        with self.assertRaises(ValueError):
            self.transact('aircraft_buy_used',offer.offer_id+'|'+token())

    def test_rent_quote_and_expiration_and_repeat_protection(self):
        snap=self.snapshot()
        price=snap['models'][0]['rental_prices']['48']
        self.assertEqual(price,rental_fee('c152',48))
        balance=snap['balance']
        key=token()
        self.transact('aircraft_rent','c152|48|'+key)
        rented=self.db.fleet_manager().selected()
        self.assertEqual(rented['kind'],'rented')
        self.assertEqual(int(self.db.get_setting('balance')),balance-price)
        self.assertEqual(len(self.snapshot()['rentals']),1)
        with self.assertRaises(ValueError):
            self.transact('aircraft_rent','c152|48|'+key)
        with self.assertRaises(ValueError):
            self.transact('aircraft_rent','c152|1000|'+token())
        self.assertEqual(len(market_state(self.app,self.center,self.now+49*3600)['rentals']),0)
        self.assertNotIn(rented['ref'],[p['ref'] for p in self.db.fleet_manager().all(self.now+49*3600)
                                      if p['kind']=='rented'])

    def test_sale_only_of_purchased_unit_at_its_airport(self):
        new=self.db.fleet_manager().purchase('c172','SBRF')
        initial=int(self.db.get_setting('balance'))
        before=self.snapshot()
        sale=next(p for p in before['owned'] if p['ref']==new['ref'])
        self.assertTrue(sale['saleable'])
        self.assertGreater(sale['resale_price'],0)
        self.assertFalse(next(p for p in before['owned'] if p['ref']=='legacy:c152')['saleable'])
        with self.assertRaisesRegex(ValueError,'não podem ser vendidas'):
            self.transact('aircraft_sell','legacy:c152|'+token())
        self.center=AIRPORTS['SBJP']
        with self.assertRaisesRegex(ValueError,'aeródromo'):
            self.transact('aircraft_sell',new['ref']+'|'+token())
        self.center=AIRPORTS['SBRF']
        self.transact('aircraft_sell',new['ref']+'|'+token())
        self.assertEqual(int(self.db.get_setting('balance')),initial+sale['resale_price'])
        self.assertIsNone(self.db.fleet_manager().get(new['ref']))

    def test_career_with_mission_or_airborne_blocks_all_market_payments(self):
        self.app.tracker.phase=Phase.AIRBORNE
        self.assertFalse(self.snapshot()['ready'])
        with self.assertRaises(ValueError):
            self.transact('aircraft_buy_new','c152|'+token())
        self.app.tracker.phase=Phase.GROUND
        self.app.career.mission=SimpleNamespace(id='mission')
        self.assertFalse(self.snapshot()['ready'])
        with self.assertRaises(ValueError):
            self.transact('aircraft_rent','c152|24|'+token())
        self.assertEqual(self.db.conn.execute('SELECT COUNT(*) FROM fleet_market_requests').fetchone()[0],0)

    def test_msfs_airport_must_be_official_and_grounded_and_nearby(self):
        self.app.mode='MSFS'
        self.app.connected=True
        self.app.last_sample=SimpleNamespace(latitude=self.center.latitude,
           longitude=self.center.longitude,timestamp=self.now,on_ground=True)
        self.assertFalse(self.snapshot()['ready'])
        self.app.msfs_airports_ready=True
        self.app.airport_catalog=SimpleNamespace(locations={'SBJP':AIRPORTS['SBJP']})
        self.assertFalse(self.snapshot()['ready'])
        self.app.airport_catalog.locations['SBRF']=self.center
        self.assertTrue(self.snapshot()['ready'])
        self.app.last_sample.latitude=0
        self.assertFalse(self.snapshot()['ready'])
        self.app.last_sample.latitude=self.center.latitude
        self.app.last_sample.on_ground=False
        self.assertFalse(self.snapshot()['ready'])
        self.app.last_sample.on_ground=True
        self.app.last_sample.timestamp=self.now-12
        self.assertFalse(self.snapshot()['ready'])

    def test_invalid_commands_do_not_touch_ledger(self):
        before=self.db.conn.execute('SELECT COUNT(*) FROM finance_ledger').fetchone()[0]
        for action,value in [('aircraft_buy_new','c172|invalid'),
                             ('aircraft_buy_new','hack|'+token()),
                             ('aircraft_buy_used','USED-OTHER|'+token()),
                             ('aircraft_rent','c172|-1|'+token()),
                             ('aircraft_sell','rent:1|'+token())]:
            with self.subTest(action=action,value=value):
                with self.assertRaises(ValueError):
                    self.transact(action,value)
        self.assertEqual(self.db.conn.execute('SELECT COUNT(*) FROM finance_ledger').fetchone()[0],before)


class ConnectionNoticeTests(unittest.TestCase):
    def test_warning_only_once_per_outage_and_again_after_connect(self):
        gate=ReconnectWarningFilter()
        self.assertTrue(gate.should_log('Conexão interrompida: MSFS não aberto. Tentando reconectar...'))
        self.assertFalse(gate.should_log('Conexão interrompida: MSFS não aberto. Tentando reconectar...'))
        self.assertFalse(gate.should_log('Conexão interrompida: socket timeout. Tentando reconectar...'))
        self.assertTrue(gate.should_log('Telemetria temporariamente incompleta: posição'))
        gate.reset()
        self.assertTrue(gate.should_log('Conexão interrompida: outra queda. Tentando reconectar...'))


if __name__=='__main__':
    unittest.main()
