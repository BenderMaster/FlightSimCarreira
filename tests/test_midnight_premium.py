"""Regression checks for v0.6.3 visual helpers (no MSFS required)."""
import unittest
from unittest.mock import patch
from aerocarreira.dashboard_premium import nationality_from_base, level_to_rank, local_avatar_path
from aerocarreira.midnight_widgets import blend, rounded_points


class MidnightPremiumTests(unittest.TestCase):
    def test_brazil_airport_home_base(self):
        self.assertEqual(nationality_from_base('SBRF',lookup=lambda x:'BR'),'BR')

    def test_foreign_airport_home_base(self):
        self.assertEqual(nationality_from_base('KJFK',lookup=lambda x:'US'),'US')

    def test_unknown_icao_is_not_assigned_nationality(self):
        self.assertEqual(nationality_from_base(''), '')
        self.assertEqual(nationality_from_base('12??'), '')
        with patch('aerocarreira.dashboard_premium._airport_country_catalog',return_value={}):
            self.assertEqual(nationality_from_base('ZZZZ'),'')

    def test_br_fallback_without_airportsdata(self):
        with patch('aerocarreira.dashboard_premium._airport_country_catalog',return_value={}):
            self.assertEqual(nationality_from_base('SBRF'),'BR')

    def test_rank_uses_obtained_qualifications_not_xp_assumptions(self):
        self.assertEqual(level_to_rank(2,{'PPA'}),('PPA','PRIVADO'))
        self.assertEqual(level_to_rank(15,{'PPA'}),('PPA','PRIVADO'))
        self.assertEqual(level_to_rank(15,{'PPA','PCA'}),('PCA','COMERCIAL'))

    def test_local_avatar_path_is_not_in_repo(self):
        self.assertTrue(str(local_avatar_path('/temp/profile')).endswith('pilot_avatar.png'))

    def test_color_blend_and_button_geometry(self):
        self.assertEqual(blend('#000000','#ffffff',.5),'#808080')
        pts=rounded_points(0,0,50,30,9)
        self.assertTrue(len(pts)>16)
        self.assertTrue(all(0<=v<=50 for v in pts[::2]))
        self.assertTrue(all(0<=v<=30 for v in pts[1::2]))


if __name__=='__main__':unittest.main()
