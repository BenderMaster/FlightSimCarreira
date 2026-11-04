"""Cobertura Nordeste e limites de alcance por aeronave do mercado freelancer."""
import unittest

from aerocarreira.contracts import (
    AirportCatalog, generate_offers, northeast_airport, freelance_range_nm)
from aerocarreira.domain import AIRPORTS, Airport, distance_nm


class NortheastFreelanceTests(unittest.TestCase):
    def setUp(self):
        self.airports={
            'SBRF':AIRPORTS['SBRF'],
            'SBJP':Airport('SBJP','João Pessoa',-7.148,-34.95),
            'SBMO':Airport('SBMO','Maceió',-9.511,-35.79),
            'SBFZ':Airport('SBFZ','Fortaleza',-3.776,-38.53),
            'SBSL':Airport('SBSL','São Luís',-2.585,-44.237),
            'SBSV':Airport('SBSV','Salvador',-12.91,-38.331),
            'SBPS':Airport('SBPS','Porto Seguro',-16.438,-39.08),
            'SBGR':Airport('SBGR','Guarulhos',-23.435,-46.47),
            'SBBE':Airport('SBBE','Belém',-1.38,-48.48),
        }
        self.catalog=AirportCatalog(self.airports)

    def test_geographic_coverage_and_exclusion(self):
        for code in ('SBRF','SBJP','SBMO','SBFZ','SBSL','SBSV','SBPS'):
            self.assertTrue(northeast_airport(self.airports[code]),code)
        for code in ('SBGR','SBBE'):
            self.assertFalse(northeast_airport(self.airports[code]),code)

    def test_freelancer_range_scales_by_model(self):
        self.assertTrue(200<freelance_range_nm('c152')<300)
        self.assertTrue(freelance_range_nm('c172')>freelance_range_nm('c152'))
        self.assertTrue(freelance_range_nm('g58')>freelance_range_nm('c172'))
        self.assertTrue(freelance_range_nm('kingair')>freelance_range_nm('g58'))

    def test_freelancer_explores_northeast_but_regional_stays_local(self):
        stats={'xp':25000,'hours':80,'level':35}
        quals={'PPA','PCA','IFR','MLTE','PLA'}
        families={'single':10,'twin':10,'turboprop':10,'jet':10,
                  'g58':4,'kingair':4,'cj4':4,'c172':4,'c152':4}
        offers=generate_offers(AIRPORTS['SBRF'],self.catalog,stats,quals,families,24642)
        regional=[o for o in offers if not o.freelance]
        freelancer=[o for o in offers if o.freelance]
        self.assertTrue(regional)
        self.assertTrue(freelancer)
        self.assertTrue(all(distance_nm(o.origin_lat,o.origin_lon,
                    o.destination_lat,o.destination_lon)<=190 for o in regional))
        self.assertTrue(any(distance_nm(o.origin_lat,o.origin_lon,
                    o.destination_lat,o.destination_lon)>190 for o in freelancer))
        for o in freelancer:
            self.assertTrue(northeast_airport(self.catalog.locations[o.destination]),o.destination)
            self.assertLessEqual(distance_nm(o.origin_lat,o.origin_lon,
                    o.destination_lat,o.destination_lon),freelance_range_nm(o.employer_plane)+1)
            self.assertEqual(o.origin,'SBRF')
        self.assertEqual(offers,generate_offers(AIRPORTS['SBRF'],self.catalog,
                                               stats,quals,families,24642))


if __name__=='__main__':
    unittest.main()
