"""Aeroportos do MSFS 2020: inventário completo via SimConnect_RequestFacilitiesList.

Somente aeroportos realmente anunciados pelo MSFS entram no catálogo.
Nenhum lookup por airportsdata, arquivo CSV ou coordenadas inseridas pelo usuário.
O inventário é volátil por sessão de conexão. Nenhuma resposta => mercado vazio.
"""
from __future__ import annotations

import ctypes
import math
import re
import struct

ICAO = re.compile(r"^[A-Z0-9]{4}$")
AIRPORT_LIST_ID = 18   # SIMCONNECT_RECV_ID_AIRPORT_LIST, MSFS2020
REQUEST_ID = 6001


def decode_airport_list_packet(raw: bytes, request_id: int = REQUEST_ID):
    """Lê cabeçalho 7xDWORD + payload de aeroportos packed(1) de 33 bytes.

    SDK MSFS2020: ident[6], region[3], latitude, longitude, altitude (double).
    Valida a contagem, paginação, comprimento e números antes de retornar.
    """
    if len(raw) < 28:
        raise ValueError("Pacote SimConnect de aeroportos incompleto")
    size,version,kind,rid,count,part,parts=struct.unpack_from("<7I",raw)
    if kind!=AIRPORT_LIST_ID or rid!=request_id:
        raise ValueError("ID de pacote SimConnect inesperado")
    if size!=len(raw) or count>25000 or not 1<=parts<=5000 or part>=parts:
        raise ValueError("Cabeçalho do catálogo de aeroportos inválido")
    payload=raw[28:]
    if count==0:
        if payload:
            raise ValueError("Lista vazia com dados extras")
        return part,parts,{}
    if len(payload)%count:
        raise ValueError("Lista truncada: tamanho incompatível com contagem")
    stride=len(payload)//count
    if stride not in (33,36,40):
        raise ValueError(f"Formato de aeroporto não reconhecido: {stride} bytes")
    # 33 é o formato 2020; 36/40 também são aceitos para evitar falha
    # de leitura se o SDK acrescentar padding ou ident mais longo.
    lat_offset=stride-24
    airports={}
    for i in range(count):
        item=payload[i*stride:(i+1)*stride]
        ident=item[:6 if stride==33 else 9].split(b"\0",1)[0]
        try:code=ident.decode("ascii").strip().upper()
        except UnicodeDecodeError:continue
        if not ICAO.fullmatch(code):
            continue
        lat,lon,alt=struct.unpack_from("<ddd",item,lat_offset)
        if not (math.isfinite(lat) and math.isfinite(lon) and
                -90<=lat<=90 and -180<=lon<=180 and math.isfinite(alt)):
            continue
        airports[code]=(lat,lon)
    return part,parts,airports


class AirportCatalogCollector:
    """Só publica a lista depois de TODAS as partes do MSFS."""
    def __init__(self):
        self.pages={}
        self.total=None

    def feed(self,raw):
        part,parts,data=decode_airport_list_packet(raw)
        if self.total is None:self.total=parts
        if self.total!=parts:
            raise ValueError("Paginação inconsistênte do catálogo MSFS")
        self.pages[part]=data
        if len(self.pages)!=self.total:return None
        catalog={}
        for i in range(self.total):
            catalog.update(self.pages[i])
        if not catalog:
            raise ValueError("SimConnect retornou lista vazia de aeroportos")
        self.pages.clear()
        return catalog


def connection_class():
    from SimConnect import SimConnect

    class AirportFacilityConnection(SimConnect):
        def __init__(self,on_catalog, on_error=None):
            self._on_catalog=on_catalog
            self._on_error=on_error or (lambda msg:None)
            self._airport_collector=AirportCatalogCollector()
            self._catalog_requested=False
            super().__init__()
            try:
                func=self.dll.SimConnect.SimConnect_RequestFacilitiesList
                func.restype=ctypes.c_long
                func.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32]
                self._airport_list_function=func
            except (AttributeError,OSError) as exc:
                self._airport_list_function=None
                self._on_error("DLL SimConnect sem listagem de aeroportos: "+str(exc))

        def request_airport_catalog(self):
            if self._catalog_requested:return True
            if self._airport_list_function is None:return False
            self._airport_collector=AirportCatalogCollector()
            hr=self._airport_list_function(self.hSimConnect,0,REQUEST_ID)
            if hr!=0:
                self._on_error(f"SimConnect_RequestFacilitiesList recusou: HRESULT {hr}")
                return False
            self._catalog_requested=True
            return True

        def my_dispatch_proc(self,pData,cbData,pContext):
            if pData.contents.dwID==AIRPORT_LIST_ID:
                try:
                    length=int(pData.contents.dwSize)
                    if not (28<=length<=4*1024*1024 and length<=int(cbData)):
                        raise ValueError("Comprimento inválido do pacote de aeroportos")
                    buf=ctypes.string_at(pData,length)
                    airports=self._airport_collector.feed(buf)
                    if airports is not None:self._on_catalog(airports)
                except (ValueError,struct.error,ctypes.ArgumentError) as exc:
                    self._on_error(str(exc))
                return
            super().my_dispatch_proc(pData,cbData,pContext)

    return AirportFacilityConnection


# Leitor antigo de dados individuais mantido apenas para recuperação de
# testes/checkpoints legados. NÃO participa do mercado MSFS.
FACILITY_RECV_ID=29
FACILITY_END_ID=30
class FacilityDataPacket(ctypes.Structure):
    _fields_=[
        ('dwSize',ctypes.c_uint32),('dwVersion',ctypes.c_uint32),
        ('dwID',ctypes.c_uint32),('UserRequestId',ctypes.c_uint32),
        ('UniqueRequestId',ctypes.c_uint32),
        ('ParentUniqueRequestId',ctypes.c_uint32),('Type',ctypes.c_uint32),
        ('IsListItem',ctypes.c_uint8),('_pad',ctypes.c_ubyte*3),
        ('ItemIndex',ctypes.c_uint32),('ListSize',ctypes.c_uint32),
        ('Data',ctypes.c_uint32)]

def decode_airport_packet(ptr,nbytes,request_ids):
    if nbytes<ctypes.sizeof(FacilityDataPacket)+12:return None
    msg=ctypes.cast(ptr,ctypes.POINTER(FacilityDataPacket)).contents
    icao=request_ids.get(msg.UserRequestId)
    if not icao or msg.dwID!=FACILITY_RECV_ID or msg.dwSize>nbytes:return None
    offset=FacilityDataPacket.Data.offset
    if nbytes<offset+16:return None
    lat,lon=struct.unpack('<dd',ctypes.string_at(ctypes.addressof(msg)+offset,16))
    if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):return None
    return {'icao':icao,'lat':lat,'lon':lon,'source':'LEGACY: NAO USAR NO MERCADO'}
