"""Flight Operations: contratos e voo livre compartilham rota, não a economia."""
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from aerocarreira.contracts import AirportCatalog
from aerocarreira.domain import AIRPORTS, MISSIONS
from aerocarreira.storage import Storage
from aerocarreira.flightplan import build_vfr_plan
from aerocarreira.flight_operations import (
    draft, validated, save, read_saved, route_stats, to_mission
)


class FlightOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Storage(Path(self.tmp.name)/"career.db")
        self.catalog=AirportCatalog(locations=AIRPORTS)
        self.contract=MISSIONS[0]

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def free(self):
        return dict(draft(None,"SIPE"),destination="SIFC")

    def test_free_flight_is_pure_navigation_and_does_not_pay(self):
        before=self.db.get_setting("balance")
        plan=save(self.db,self.free(),self.catalog)
        mission=to_mission(plan,self.catalog)
        self.assertEqual(plan["mode"],"free")
        self.assertEqual(plan["mission_id"],None)
        self.assertEqual(mission.reward,0)
        self.assertEqual(mission.category,"legacy")
        self.assertEqual(self.db.get_setting("balance"),before)
        self.assertIsNotNone(read_saved(self.db))

    def test_contract_origin_and_destination_cannot_be_changed(self):
        p=draft(self.contract)
        validated(p,self.catalog,self.contract)
        p["destination"]="SBJP"
        with self.assertRaises(ValueError):
            validated(p,self.catalog,self.contract)

    def test_no_external_or_unverified_airports(self):
        with self.assertRaises(ValueError):
            validated(self.free(),None)
        p=self.free()
        p["destination"]="ZZZZ"
        with self.assertRaises(ValueError):
            validated(p,self.catalog)

    def test_waypoints_leg_metrics_and_pln_order(self):
        p=self.free()
        p["waypoints"]=[{"label":"A01","lat":-8.0,"lon":-35.0},
                        {"label":"B02","lat":-7.9,"lon":-35.0}]
        plan=save(self.db,p,self.catalog)
        route=route_stats(plan,self.catalog,"Cessna 152",18,None)
        self.assertEqual(len(route["legs"]),3)
        self.assertTrue(0<=route["legs"][0]["bearing_deg"]<360)
        self.assertGreater(route["legs"][0]["minutes"],0)
        self.assertGreater(route["distance_nm"],0)
        self.assertGreater(route["minutes"],0)
        self.assertGreater(route["fuel_required_gal"],0)
        raw=build_vfr_plan(to_mission(plan,self.catalog),
                           plan["altitude_ft"],waypoints=plan["waypoints"])
        points=ET.fromstring(raw).findall(".//ATCWaypoint")
        self.assertEqual([p.attrib["id"] for p in points],["SIPE","A01","B02","SIFC"])
        self.assertEqual([p.findtext("ATCWaypointType") for p in points],
                         ["Airport","User","User","Airport"])

    def test_reject_unbounded_nonfinite_and_malicious_data(self):
        p=self.free()
        p["waypoints"]=[{"label":"FIX","lat":float("nan"),"lon":-35.0}]
        with self.assertRaises(ValueError):
            validated(p,self.catalog)
        p["waypoints"]=[{"label":"../../x","lat":-8.0,"lon":-35.0}]
        with self.assertRaises(ValueError):
            validated(p,self.catalog)
        p["waypoints"]=[{"label":"FIX"+str(i),"lat":-8.0,"lon":-35.0} for i in range(9)]
        with self.assertRaises(ValueError):
            validated(p,self.catalog)
        p["waypoints"]=[]
        p["altitude_ft"]=True
        with self.assertRaises(ValueError):
            validated(p,self.catalog)
        p["altitude_ft"]=2500
        p["checks"]["route_checked"]="yes"
        with self.assertRaises(ValueError):
            validated(p,self.catalog)

    def test_longer_waypoint_route_increases_fuel_requirement_for_bonus(self):
        from aerocarreira.planning import Preflight, inspect_preflight
        mission=self.contract
        direct=Preflight(mission.id,"Cessna 152",fuel_checked=True,
                         planned_fuel_gal=20)
        baseline=inspect_preflight(mission,direct)
        route=Preflight(mission.id,"Cessna 152",fuel_checked=True,
                        planned_fuel_gal=20,
                        planned_distance_nm=baseline["distance_nm"]+30)
        longer=inspect_preflight(mission,route)
        self.assertGreater(longer["fuel_required_gal"],baseline["fuel_required_gal"])
        self.assertGreater(longer["distance_nm"],baseline["distance_nm"])

    def test_contract_stale_after_mission_changes(self):
        p=draft(self.contract)
        saved=save(self.db,p,self.catalog,self.contract)
        self.assertEqual(saved["mission_id"],self.contract.id)
        self.assertIsNotNone(read_saved(self.db,self.contract))
        self.assertIsNone(read_saved(self.db,None))
        self.assertEqual(to_mission(saved,self.catalog,self.contract).id,
                         self.contract.id)

    def test_free_plan_survives_db_restart(self):
        plan=save(self.db,self.free(),self.catalog)
        self.db.close()
        self.db=Storage(Path(self.tmp.name)/"career.db")
        self.assertEqual(read_saved(self.db)["destination"],plan["destination"])


if __name__=="__main__":
    unittest.main()
