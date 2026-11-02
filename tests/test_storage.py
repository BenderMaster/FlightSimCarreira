import unittest
import tempfile
from pathlib import Path
from aerocarreira.storage import Storage

class StorageTests(unittest.TestCase):
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'carreira.db'
            db=Storage(p)
            self.assertEqual(db.get_setting('balance'),'5000')
            db.set_setting('balance','5850')
            db.save_flight({'timestamp':100,'lat':-8.12,'lon':-34.92},{'timestamp':200,'lat':-7.65,'lon':-34.85},-155,0,'REC-ITA',850)
            self.assertEqual(len(db.list_flights()),1)
            db.close()
            db=Storage(p)
            self.assertEqual(db.get_setting('balance'),'5850')
            self.assertEqual(db.list_flights()[0][-1],850)
            db.close()
