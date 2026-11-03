"""Checks for Midnight Ops rendering data without changing game state."""
import unittest
from aerocarreira.dashboard_ui import safe_coords, normalized_progress
from aerocarreira.domain import MISSIONS, Mission, AIRPORTS


class DashboardDataTests(unittest.TestCase):
    def test_known_airport_coords_are_real(self):
        first=next(m for m in MISSIONS if m.id=='REC-ITA')
        a,b=safe_coords(first)
        self.assertEqual(a,(AIRPORTS['SBRF'].latitude,AIRPORTS['SBRF'].longitude))
        self.assertEqual(b,(AIRPORTS['SIPE'].latitude,AIRPORTS['SIPE'].longitude))

    def test_dynamic_coords_without_known_airports(self):
        m=Mission('custom','XXXX','YYYY','Teste',1000,origin_lat=-8.2,origin_lon=-35.2,
                  destination_lat=-8.6,destination_lon=-36.3)
        self.assertEqual(safe_coords(m),((-8.2,-35.2),(-8.6,-36.3)))

    def test_no_invented_coordinates(self):
        m=Mission('custom','XXXX','YYYY','Teste',1000)
        self.assertEqual(safe_coords(m),(None,None))

    def test_xp_progress_clamped(self):
        self.assertEqual(normalized_progress(-10),normalized_progress(0))
        self.assertEqual(normalized_progress(0)['level'],1)


if __name__=='__main__': unittest.main()
