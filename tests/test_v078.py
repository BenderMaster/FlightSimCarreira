"""v0.7.8 — somente aeroportos do MSFS, refuel numérico e plano ATC."""
import json
import struct
import unittest
import urllib.error
import urllib.request

from aerocarreira.domain import Mission
from aerocarreira.msfs_airports import catalog_from_msfs,strict_mission,restricted_mission
from aerocarreira.sim_facilities import (decode_airport_list_packet,AirportCatalogCollector,
                                          AIRPORT_LIST_ID,REQUEST_ID)
from aerocarreira.midnight_server import DashboardServer


def packet(part,parts,airports):
    data=b''
    for code,lat,lon in airports:
        data+=code.encode('ascii').ljust(6,b'\0')+b'BR\0'+struct.pack('<ddd',lat,lon,100.)
    return struct.pack('<7I',28+len(data),0,AIRPORT_LIST_ID,
                       REQUEST_ID,len(airports),part,parts)+data


def packet_aligned(part, parts, airports, stride=36, array_offset=32):
    """Reproduz a estrutura de memória SDK (header padding + item alignment)."""
    latitude_offset={33:9,36:12,40:16}[stride]
    raw=bytearray(array_offset+stride*len(airports))
    struct.pack_into("<7I",raw,0,len(raw),0,AIRPORT_LIST_ID,
                     REQUEST_ID,len(airports),part,parts)
    for index,(ident,lat,lon) in enumerate(airports):
        at=array_offset+index*stride
        raw[at:at+6]=ident.encode('ascii').ljust(6,b'\x00')
        raw[at+6:at+9]=b'BR\x00'
        struct.pack_into("<ddd",raw,at+latitude_offset,lat,lon,100.)
    return bytes(raw)


class StrictMsfsTests(unittest.TestCase):
    def test_airport_list_pagination_and_coordinates(self):
        data=packet(0,2,[('SNRU',-8.285,-36.0)])
        part,pages,result=decode_airport_list_packet(data)
        self.assertEqual((part,pages),(0,2))
        self.assertAlmostEqual(result['SNRU'][0],-8.285)
        collector=AirportCatalogCollector()
        self.assertIsNone(collector.feed(data))
        complete=collector.feed(packet(1,2,[('SIRF',-8.89,-35.97)]))
        self.assertEqual(set(complete),{'SNRU','SIRF'})
        self.assertTrue(len(complete)==2)

    def test_msfs_native_padding_before_airport_array(self):
        # Bug real da v0.7.8: tamanho = 32 + N*36, mas leitor
        # anterior subtraía sempre 28 e rejeitava por contagem.
        raw=packet_aligned(0,1,[('SBRF',-8.126,-34.922),
                                ('SNRU',-8.285,-36.00),
                                ('SIRF',-8.89,-35.97)],stride=36,array_offset=32)
        self.assertNotEqual((len(raw)-28)%3,0)
        part,parts,airports=decode_airport_list_packet(raw)
        self.assertEqual((part,parts),(0,1))
        self.assertEqual(set(airports),{'SBRF','SNRU','SIRF'})
        self.assertAlmostEqual(airports['SNRU'][0],-8.285)
        self.assertAlmostEqual(airports['SIRF'][1],-35.97)

    def test_supported_native_stride_combinations(self):
        for header in (28,32):
            for stride in (33,36,40):
                with self.subTest(header=header,stride=stride):
                    raw=packet_aligned(0,1,[('SNRU',-8.285,-36.0),
                                           ('SBRF',-8.126,-34.922)],
                                       stride=stride,array_offset=header)
                    _,_,airports=decode_airport_list_packet(raw)
                    self.assertEqual(set(airports),{'SNRU','SBRF'})
                    self.assertAlmostEqual(airports['SNRU'][1],-36.0)

    def test_single_record_ambiguity_is_resolved_using_coordinates(self):
        # 28+40 e 32+36 têm o mesmo tamanho total quando N=1.
        raw=packet_aligned(0,1,[('SNRU',-8.285,-36.0)],
                           stride=36,array_offset=32)
        self.assertEqual(len(raw),68)
        self.assertEqual(decode_airport_list_packet(raw)[2]['SNRU'],(-8.285,-36.0))

    def test_padding_does_not_let_invalid_airports_into_market(self):
        raw=packet_aligned(0,1,[('SNRU',-8.285,-36.0),
                                ('SNBJ',300.,-36.)],stride=36,array_offset=32)
        part,parts,airports=decode_airport_list_packet(raw)
        self.assertIn('SNRU',airports)
        self.assertNotIn('SNBJ',airports)
        broken=bytearray(raw)
        broken[0:4]=struct.pack('<I',len(raw)-1)
        with self.assertRaises(ValueError):
            decode_airport_list_packet(bytes(broken))

    def test_corrupted_and_wrong_request_packets_fail_closed(self):
        good=packet(0,1,[('SBRF',-8.1,-34.9)])
        with self.assertRaises(ValueError):decode_airport_list_packet(good[:-2])
        with self.assertRaises(ValueError):decode_airport_list_packet(good,REQUEST_ID+1)
        with self.assertRaises(ValueError):decode_airport_list_packet(good[:28]+b'broken')

    def test_nonexistent_airports_never_injected_from_default_or_sqlite(self):
        current=catalog_from_msfs({'SNRU':(-8.285,-36.0),'SIRF':(-8.89,-35.97)})
        self.assertEqual(set(current.locations),{'SNRU','SIRF'})
        legacy=Mission('old','SNRU','SNBJ','Transporte',1600,
                       origin_lat=-8.9,origin_lon=-35.3,
                       destination_lat=-8.3,destination_lon=-35.8,
                       nav_source='MSFS')
        self.assertIsNone(strict_mission(legacy,current))
        unverified=restricted_mission(legacy,current)
        self.assertIsNone(unverified.origin_lat)
        self.assertIsNone(unverified.destination_lon)
        self.assertEqual(unverified.nav_source,'NAO_VERIFICADO')
        current_valid=Mission('ok','SNRU','SIRF','Passageiro',1200,
                              destination_lat=40.,destination_lon=40.)
        fixed=strict_mission(current_valid,current)
        self.assertEqual(fixed.destination_lat,-8.89)
        self.assertEqual(fixed.nav_source,'MSFS')

    def test_invalid_catalog_is_not_used(self):
        for invalid in ({},{'SNBJ':(float('nan'),0.)},
                        {'SNBJ':(200.,0.)},{'SNBJ':('x',30.)}):
            with self.assertRaises(ValueError):
                catalog_from_msfs(invalid)

    def test_refuel_accepts_json_number_but_no_other_action_does(self):
        server=DashboardServer()
        server.start()
        def request(action,identifier=None):
            body={'action':action}
            if identifier is not None:body['id']=identifier
            req=urllib.request.Request(server.origin+'/command',method='POST',
                data=json.dumps(body).encode(),headers={'Content-Type':'application/json',
                'X-Flight-Token':server.token,'Origin':server.origin})
            try:
                with urllib.request.urlopen(req,timeout=3) as resp:
                    return resp.status
            except urllib.error.HTTPError as exc:
                return exc.code
        try:
            self.assertEqual(request('refuel',40.5),202)
            self.assertEqual(request('refuel',0),202)
            self.assertEqual(request('offer',40.5),400)
            self.assertEqual(request('refuel',True),400)
            self.assertEqual(request('refuel',-1.),400)
            self.assertEqual(request('refuel',float('inf')),400)
            self.assertEqual(request('refuel',float('nan')),400)
            self.assertEqual(request('prepare'),202)
            first=server.commands.get_nowait()
            self.assertEqual(first,{'action':'refuel','id':40.5})
        finally:
            server.stop()


if __name__=='__main__':
    unittest.main()
