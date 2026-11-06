"""Financial Center v0.8.4: ledger integrity, loans, premiums and export."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from aerocarreira.storage import Storage
from aerocarreira.financial_center import snapshot, records, export_csv, category
from aerocarreira.domain import AIRPORTS


class FinancialCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Storage(Path(self.temp.name)/'carreira.db')
        self.db.create_pilot('Finance Tester','FIN001','SIPE')
        self.db.set_setting('balance','300000')

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_bank_allows_150_thousand_and_preserves_eight_percent(self):
        cash=self.db.take_loan(150000)
        self.assertEqual(cash,450000)
        self.assertEqual(self.db.outstanding_loan(),162000)
        with self.assertRaises(ValueError):
            self.db.take_loan(150001)
        with self.assertRaises(ValueError):
            self.db.take_loan(1000)
        self.assertEqual(self.db.repay_loan(62000),388000)
        self.assertEqual(self.db.outstanding_loan(),100000)
        self.assertEqual(self.db.repay_loan(100000),288000)
        self.assertEqual(self.db.outstanding_loan(),0)
        self.assertEqual(len([r for r in records(self.db) if r['kind']=='financiamento']),1)

    def test_money_actions_are_idempotent_with_persistent_request_id(self):
        req='11111111-2222-4333-8444-555555555555'
        self.db.take_loan(50000,request_id=req)
        cash=self.db.get_setting('balance')
        with self.assertRaises(ValueError):
            self.db.take_loan(50000,request_id=req)
        self.assertEqual(self.db.get_setting('balance'),cash)
        repay='aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
        self.db.repay_loan(20000,request_id=repay)
        debt=self.db.outstanding_loan()
        with self.assertRaises(ValueError):
            self.db.repay_loan(20000,request_id=repay)
        self.assertEqual(self.db.outstanding_loan(),debt)
        self.assertEqual(len([r for r in records(self.db) if r['kind']=='parcela']),1)
        self.db.close()
        self.db=Storage(Path(self.temp.name)/'carreira.db')
        with self.assertRaises(ValueError):
            self.db.repay_loan(20000,request_id=repay)
        self.assertEqual(self.db.outstanding_loan(),debt)

    def test_insurance_is_operating_expense_and_loan_not_income(self):
        self.db.claim_starter()
        self.db.set_insurance('c152',True)
        self.db.take_loan(10000)
        report=snapshot(self.db)
        self.assertEqual(report['income'],0)
        self.assertEqual(report['expenses'],220)
        self.assertEqual(report['operating_net'],-220)
        self.assertEqual(report['debt'],10800)
        self.assertEqual(report['balance'],309780)
        self.assertEqual(report['net_worth'],report['balance']-10800)
        self.assertEqual(next(x for x in report['expense_categories'] if x['kind']=='seguro')['value'],220)
        self.assertEqual(next(x for x in report['assets'] if x['kind']=='starter')['resale_price'],None)
        self.assertEqual(category('seguro'),'operacional')
        self.assertEqual(category('financiamento'),'patrimonio')

    def test_purchased_aircraft_is_asset_but_not_operating_expense(self):
        plane=self.db.fleet_manager().purchase('c172','SBRF')
        report=snapshot(self.db)
        self.assertEqual(report['balance'],155000)
        self.assertEqual(report['operating_net'],0)
        self.assertEqual(report['invested'],145000)
        self.assertGreater(report['assets_value'],0)
        self.assertLess(report['assets_value'],report['invested'])
        self.assertEqual(len(report['assets']),1)
        self.assertEqual(report['assets'][0]['ref'],plane['ref'])

    def test_full_export_not_truncated_to_last_five_hundred(self):
        for i in range(515):
            with self.db.conn:
                self.db._money_movement(f'insurance-test:{i}','seguro',-1,f'Apólice {i}')
        report=snapshot(self.db)
        self.assertEqual(report['total_transactions'],515)
        self.assertEqual(len(report['transactions']),500)
        exported=export_csv(self.db)
        self.assertTrue(exported.startswith(b'\xef\xbb\xbf'))
        content=exported.decode('utf-8-sig')
        rows=list(csv.reader(io.StringIO(content),delimiter=';'))
        self.assertEqual(len(rows),516)
        self.assertEqual(report['expenses'],515)
        self.assertIn('Apólice 0',content)
        self.assertIn('Apólice 514',content)

    def test_net_by_flight_uses_actual_entries_without_duplicate_costs(self):
        self.db.claim_starter()
        start={'timestamp':10000.0,'lat':AIRPORTS['SIPE'].latitude,
               'lon':AIRPORTS['SIPE'].longitude}
        end={'timestamp':11200.0,'lat':AIRPORTS['SIFC'].latitude,
             'lon':AIRPORTS['SIFC'].longitude}
        checkpoint={'version':1,'career':{'mission_id':None},'tracker':{'phase':'solo'}}
        applied=self.db.finalize_flight(start,end,-180,0,'REG-SIPE-2100-01',1600,checkpoint,
                                        aircraft_title='Cessna 152',fuel_start=15,fuel_end=13)
        self.assertTrue(applied)
        result=snapshot(self.db)
        paid=next(v for v in result['operations'] if v['paid'])
        self.assertEqual(paid['gross'],1600)
        self.assertGreater(paid['fuel'],0)
        self.assertGreater(paid['expenses'],0)
        self.assertEqual(paid['net'],paid['gross']-paid['expenses'])
        count=result['total_transactions']
        self.assertFalse(self.db.finalize_flight(start,end,-180,0,'REG-SIPE-2100-01',
                                                  1600,checkpoint,aircraft_title='Cessna 152',
                                                  fuel_start=15,fuel_end=13))
        self.assertEqual(snapshot(self.db)['total_transactions'],count)


if __name__=='__main__':
    unittest.main()
