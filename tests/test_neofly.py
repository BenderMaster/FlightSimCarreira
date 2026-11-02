import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from aerocarreira.neo_inspect import inspect_neofly


class NeoFlySafetyTests(unittest.TestCase):
    def test_sqlite_schema_only_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'common.db'
            con=sqlite3.connect(p)
            con.execute('CREATE TABLE pilots (id INTEGER PRIMARY KEY, name TEXT, private_note TEXT)')
            con.execute('INSERT INTO pilots(name,private_note) VALUES(?,?)',('Aviation User','very private'))
            con.commit(); con.close()
            before=p.read_bytes()
            report=inspect_neofly(p,Path(folder)/'analysis')
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual(report['format'],'SQLite')
            self.assertEqual(report['tables'][0]['table'],'pilots')
            self.assertTrue('private_note' in json.dumps(report))
            self.assertFalse('Aviation User' in json.dumps(report))
            self.assertFalse('very private' in json.dumps(report))
            self.assertTrue((Path(folder)/'analysis'/'neofly_copia_local.db').exists())

    def test_unknown_format_stops_cleanly(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'common.db'; p.write_bytes(b'other format xxx')
            r=inspect_neofly(p,Path(folder)/'out')
            self.assertEqual(r['format'],'desconhecido')
            self.assertEqual(r['tables'],[])

    def test_same_source_and_copy_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            p=d/'neofly_copia_local.db';p.write_bytes(b'abc')
            with self.assertRaises(ValueError):inspect_neofly(p,d)

    def test_non_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):inspect_neofly(Path(folder)/'not.db',Path(folder)/'out')

class NeoFlyDiscoveryTests(unittest.TestCase):
    def test_find_both_known_filenames_in_standard_roots(self):
        from aerocarreira.neo_inspect import discover_neofly_databases
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            program = root / 'ProgramData' / 'NeoFly'
            local = root / 'Local' / 'Programs' / 'NeoFly'
            program.mkdir(parents=True)
            local.mkdir(parents=True)
            db = program / 'common.db'
            binfile = local / 'std.bin'
            db.write_bytes(b'old db')
            binfile.write_bytes(b'unknown bin')
            outside = root / 'Other' / 'std.bin'
            outside.parent.mkdir()
            outside.write_bytes(b'not a candidate')
            env = {'PROGRAMDATA': str(root / 'ProgramData'),
                   'LOCALAPPDATA': str(root / 'Local'),
                   'APPDATA': str(root / 'Roaming')}
            found = discover_neofly_databases(env=env, home=root / 'Home')
            self.assertEqual(set(found), {db.resolve(), binfile.resolve()})
            self.assertEqual(db.read_bytes(), b'old db')
            self.assertEqual(binfile.read_bytes(), b'unknown bin')

    def test_no_candidate_is_not_an_error(self):
        from aerocarreira.neo_inspect import discover_neofly_databases
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = discover_neofly_databases(
                env={'PROGRAMDATA':str(root / 'P'),
                     'LOCALAPPDATA':str(root / 'L'),
                     'APPDATA':str(root / 'R')}, home=root / 'H')
            self.assertEqual(result, [])

    def test_std_bin_unknown_format_does_not_rewrite_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = root / 'std.bin'
            candidate.write_bytes(b'NeoFly opaque content')
            report = inspect_neofly(candidate, root / 'analysis')
            self.assertEqual(report['format'], 'desconhecido')
            self.assertEqual(report['tables'], [])
            self.assertEqual(candidate.read_bytes(), b'NeoFly opaque content')
