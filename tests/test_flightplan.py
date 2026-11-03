from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.etree import ElementTree as ET
from aerocarreira.domain import MISSIONS, Mission
from aerocarreira.flightplan import build_vfr_plan, export_vfr_plan, position

class FlightplanTests(unittest.TestCase):
    def test_pln_xml_schema_for_msfs2020(self):
        m=MISSIONS[-1]
        data=build_vfr_plan(m)
        root=ET.fromstring(data)
        self.assertEqual(root.attrib['Type'],'AceXML')
        fp=root.find('FlightPlan.FlightPlan')
        self.assertEqual(fp.findtext('FPType'),'VFR')
        self.assertEqual(fp.findtext('DepartureID'),'SIPE')
        self.assertEqual(fp.findtext('DestinationID'),'SIFC')
        self.assertEqual(fp.findtext('AppVersion/AppVersionMajor'),'10')
        self.assertEqual(len(fp.findall('ATCWaypoint')),2)
        self.assertTrue(fp.findtext('DepartureLLA').startswith('S7°'))
        self.assertIn('W34°',fp.findtext('DestinationLLA'))
        self.assertEqual(len(root.findall('.//ICAOIdent')),2)

    def test_export_does_not_write_outside_given_dir(self):
        with TemporaryDirectory() as tmp:
            path=export_vfr_plan(MISSIONS[0],tmp)
            self.assertEqual(path.parent,Path(tmp).resolve())
            self.assertEqual(path.suffix,'.pln')
            self.assertTrue(path.read_bytes().startswith(b'<?xml'))

    def test_invalid_coords_and_icao_and_altitude(self):
        with self.assertRaises(ValueError):position(91,30)
        with self.assertRaises(ValueError):build_vfr_plan(MISSIONS[0],499)
        m=Mission('xyz','../p','SIPE','bad',1)
        with self.assertRaises(ValueError):build_vfr_plan(m)
        with self.assertRaises(ValueError):build_vfr_plan(Mission('x','KZZZ','SIFC','missing',1))

    def test_dms_rounding(self):
        self.assertIn('N0°',position(0,0))
        self.assertIn('W180°',position(1,-180))

if __name__=='__main__':unittest.main()
