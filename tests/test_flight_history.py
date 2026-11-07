"""Regression tests for FlightSim v0.8.6 SQLite flight history and notes."""
import tempfile
import unittest
from pathlib import Path

from aerocarreira.storage import Storage
from aerocarreira import flight_history


class FlightHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Storage(Path(self.tmp.name)/'pilot.db')
        self.db.create_pilot('Pilot QA','FSC-QA','SBRF')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def flight(self,id_,key,mission=None,model='Cessna 152',start=1790000000.0):
        with self.db.conn:
            self.db.conn.execute(
                """INSERT INTO flights(id,started_utc,ended_utc,from_lat,from_lon,
                   to_lat,to_lon,touchdown_fpm_est,stall_warnings,mission_id,
                   reward,flight_key,aircraft_title)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (id_,start,start+3600,-8.1,-34.9,-8.3,-35.0,-128.0,0,mission,0,key,model))

    def test_empty_profile_does_not_invent_flights(self):
        snap=flight_history.snapshot(self.db)
        self.assertEqual(snap['count'],0)
        self.assertEqual(snap['flights'],[])

    def test_flights_notes_and_legacy_unknown_airports(self):
        self.flight(1,'takeoff:1790000000:-8.1:-34.9','REG-X')
        flight_history.save_note(self.db,1,'Pouso visual e checklist completo')
        snap=flight_history.snapshot(self.db)
        self.assertEqual(snap['count'],1)
        item=snap['flights'][0]
        self.assertEqual(item['kind'],'regional')
        self.assertEqual(item['note'],'Pouso visual e checklist completo')
        self.assertIsNone(item['departure_icao'])
        self.assertIsNone(item['arrival_icao'])
        self.assertGreater(item['direct_nm'],0)
        self.assertEqual(item['touchdown_fpm'],-128)
        flight_history.save_note(self.db,1,'Revisado')
        self.assertEqual(flight_history.snapshot(self.db)['flights'][0]['note'],'Revisado')
        self.assertEqual(self.db.conn.execute('SELECT COUNT(*) FROM flight_notes').fetchone()[0],1)

    def test_reject_notes_for_other_profiles_and_oversized_payloads(self):
        self.flight(1,'takeoff:1790000000:-8.1:-34.9')
        with self.assertRaises(ValueError):
            flight_history.save_note(self.db,999,'Orfão')
        with self.assertRaises(ValueError):
            flight_history.save_note(self.db,1,'x'*1201)
        with self.assertRaises(ValueError):
            flight_history.save_note(self.db,1,'\x01malicioso')
        with self.assertRaises(ValueError):
            flight_history.save_note(self.db,True,'inválido')
        self.assertEqual(self.db.conn.execute('SELECT COUNT(*) FROM flight_notes').fetchone()[0],0)

    def test_finances_are_attributed_to_correct_ledger(self):
        personal_key='takeoff:1790000000:-8.1:-34.9'
        company_key='takeoff:1790007200:-8.2:-34.9'
        self.flight(1,personal_key,'REG-QA')
        self.flight(2,company_key,'OWN-QA',start=1790007200.0)
        with self.db.conn:
            self.db.conn.execute("""INSERT INTO pilot_xp_ledger(flight_key,xp,awarded_utc)
                VALUES(?,?,?)""",(personal_key,45,1790003600))
            for suffix,kind,amount in [('income','contrato',1500),('tax','taxa_simulada',-80)]:
                self.db.conn.execute("""INSERT INTO finance_ledger
                    (event_key,kind,amount,balance_after,description,occurred_utc)
                    VALUES(?,?,?,?,?,?)""",(personal_key+':'+suffix,kind,amount,6500,'QA',1790003600))
            self.db.conn.execute("""INSERT INTO airline_company(id,name,callsign,home_icao,
                founded_utc,balance,reputation) VALUES(1,'QA Air','QAA','SBRF',1790000000,10000,50)""")
            self.db.conn.execute("""INSERT INTO airline_company_ledger
                (event_key,kind,amount,balance_after,description,occurred_utc)
                VALUES(?,?,?,?,?,?)""",(company_key+':income,'operacao',2500,12500,'QA',1790010000))
        snap=flight_history.snapshot(self.db)
        company,personal=snap['flights']
        self.assertEqual(company['business_net'],2500)
        self.assertIsNone(company['personal_net'])
        self.assertEqual(company['xp'],None)
        self.assertEqual(personal['xp'],45)
        self.assertEqual(personal['personal_net'],1420)
        self.assertIsNone(personal['business_net'])

    def test_csv_protects_formula_cells_and_has_pt_br_bom(self):
        self.flight(1,'takeoff:1790000000:-8.1:-34.9')
        flight_history.save_note(self.db,1,'=HYPERLINK("bad")')
        csv=flight_history.csv_text(flight_history.snapshot(self.db)['flights'])
        self.assertTrue(csv.startswith('\ufeff'))
        self.assertIn("'=HYPERLINK",csv)
        self.assertIn(';',csv)
        self.assertIn('Distância direta estimada',csv)

    def test_mode_classification(self):
        self.assertEqual(flight_history.category('EMP-ABC'),'emprego')
        self.assertEqual(flight_history.category('OWN-ABC'),'empresa')
        self.assertEqual(flight_history.category('FREE-ABC'),'freelancer')
        self.assertEqual(flight_history.category(None),'particular')


if __name__=='__main__':
    unittest.main()
