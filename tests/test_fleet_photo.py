"""Bloco 1 — isolamento da frota, fotos por exemplar e transporte local."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import urllib.error
import urllib.request
import unittest

from PIL import Image

from aerocarreira.storage import Storage
from aerocarreira.fleet_photos import (normalize_photo,save_photo,delete_photo,
                                       photo_stamps,photo_bytes,owned_fleet)
from aerocarreira.midnight_server import DashboardServer
from aerocarreira.dashboard import DashboardPresenter
from aerocarreira.fuel import FuelManager
from aerocarreira.domain import Career,FlightTracker
from types import SimpleNamespace
from unittest.mock import Mock


class FleetPhotoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.path=Path(self.tmp.name)/'pilot.db'
        self.db=Storage(self.path)
        self.db.create_pilot('Piloto QA','QA001','SBRF')
        self.db.claim_starter()
        self.db.set_setting('balance','500000')
        self.new=self.db.fleet_manager().purchase('c172','SBRF')
        self.db.fleet_manager().select('legacy:c152')
        self.rented=self.db.fleet_manager().rent('g58','SBRF',hours=24)
        self.db.fleet_manager().select('legacy:c152')
        self.image_path=Path(self.tmp.name)/'portrait.png'
        Image.new('RGB',(380,900),(10,42,65)).save(self.image_path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_owned_fleet_excludes_rented_aircraft(self):
        owned=owned_fleet(self.db)
        self.assertEqual({x['ref'] for x in owned},{'legacy:c152',self.new['ref']})
        self.assertTrue(all(x['kind']!='rented' for x in owned))

    def test_normalize_portrait_and_persist_in_same_sqlite(self):
        jpeg=normalize_photo(self.image_path)
        self.assertTrue(jpeg.startswith(bytes.fromhex('ffd8')))
        self.assertTrue(jpeg.endswith(bytes.fromhex('ffd9')))
        with Image.open(BytesIO(jpeg)) as im:
            self.assertLessEqual(im.width,1600)
            self.assertLessEqual(im.height,1100)
            self.assertLess(im.width,im.height)
        stamp=save_photo(self.db,'legacy:c152',jpeg)
        self.assertEqual(photo_stamps(self.db)['legacy:c152'],stamp)
        self.assertEqual(photo_bytes(self.db)['legacy:c152'],jpeg)
        self.db.close()
        self.db=Storage(self.path)
        self.assertEqual(photo_bytes(self.db)['legacy:c152'],jpeg)

    def test_each_identical_model_instance_has_independent_photo(self):
        twin=self.db.fleet_manager().purchase('c172','SBRF')
        a=normalize_photo(self.image_path)
        source=Path(self.tmp.name)/'landscape.jpg'
        Image.new('RGB',(1200,400),(210,130,40)).save(source)
        b=normalize_photo(source)
        save_photo(self.db,self.new['ref'],a)
        save_photo(self.db,twin['ref'],b)
        self.assertNotEqual(photo_bytes(self.db)[self.new['ref']],
                            photo_bytes(self.db)[twin['ref']])
        self.assertTrue(delete_photo(self.db,twin['ref']))
        self.assertIn(self.new['ref'],photo_bytes(self.db))
        self.assertNotIn(twin['ref'],photo_bytes(self.db))
        self.assertFalse(delete_photo(self.db,twin['ref']))

    def test_rented_and_unowned_planes_cannot_get_photo(self):
        jpeg=normalize_photo(self.image_path)
        for ref in (self.rented['ref'],'unit:9999','contract:123','bogus'):
            with self.subTest(ref=ref):
                with self.assertRaises(ValueError):
                    save_photo(self.db,ref,jpeg)

    def test_image_input_validation_does_not_mutate_database(self):
        invalid=Path(self.tmp.name)/'invalid.png'
        invalid.write_bytes(b'not an image')
        with self.assertRaises(ValueError):
            normalize_photo(invalid)
        self.assertEqual(photo_stamps(self.db),{})

    def test_loopback_photo_requires_unpredictable_valid_key(self):
        jpeg=normalize_photo(self.image_path)
        save_photo(self.db,'legacy:c152',jpeg)
        server=DashboardServer()
        server.set_photos(photo_bytes(self.db))
        server.start()
        try:
            url=server.origin+server.photo_url('legacy:c152',photo_stamps(self.db)['legacy:c152'])
            with urllib.request.urlopen(url,timeout=5) as response:
                self.assertEqual(response.status,200)
                self.assertEqual(response.headers.get('Content-Type'),'image/jpeg')
                self.assertEqual(response.read(),jpeg)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(server.origin+'/fleet-photo/'+'0'*64+'.jpg',timeout=5)
            self.assertEqual(caught.exception.code,404)
            server.remove_photo('legacy:c152')
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(url,timeout=5)
            self.assertEqual(caught.exception.code,404)
        finally:
            server.stop()

    def test_presenter_uses_same_selected_aircraft_image(self):
        jpeg=normalize_photo(self.image_path)
        save_photo(self.db,'legacy:c152',jpeg)
        app=SimpleNamespace(storage=self.db,fuel_manager=FuelManager(self.db),
            last_sample=None,airport_catalog=None,connected=False,
            mode='Desconectado',career=Career(),tracker=FlightTracker(),
            realism_frozen=0,status_var=Mock(get=lambda:'offline'),
            phase_var=Mock(get=lambda:'SOLO'),log_text=Mock(get=lambda *a:''),
            _saved_preflight=lambda:None)
        p=DashboardPresenter(app)
        server=DashboardServer()
        p.photo_url_for=server.photo_url
        snap=p.snapshot()
        self.assertEqual(snap['fleet']['count'],2)
        self.assertNotIn(self.rented['ref'],[x['ref'] for x in snap['fleet']['owned']])
        self.assertEqual(snap['plane']['photo_url'],
            next(x['photo_url'] for x in snap['fleet']['owned'] if x['is_active']))
        self.assertTrue(snap['plane']['photo_url'].startswith('/fleet-photo/'))
        self.assertNotIn(str(self.image_path),str(snap))
        self.assertNotIn('jpeg',snap['plane'])


if __name__=='__main__':
    unittest.main()
