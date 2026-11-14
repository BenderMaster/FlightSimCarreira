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
from . import airport_facilities as detail

ICAO = re.compile(r"^[A-Z0-9]{4}$")
AIRPORT_LIST_ID = 18   # SIMCONNECT_RECV_ID_AIRPORT_LIST, MSFS2020
REQUEST_ID = 6001


def decode_airport_list_packet(raw: bytes, request_id: int = REQUEST_ID):
    """Decodifica uma página recebida do MSFS, respeitando alinhamento nativo.

    Cabeçalho SIMCONNECT_RECV_FACILITIES_LIST: 28 bytes; dependendo do
    alinhamento do SDK, o array rgData começa no offset 28 OU 32.
    Cada entrada MSFS 2020 contém ident[6], region[3], três doubles:
    offsets de latitude 9 (33 bytes), 12 (36 bytes) ou 16 (40 bytes).
    Não se usam aeroportos de fontes externas como fallback.
    """
    if len(raw) < 28:
        raise ValueError("Pacote SimConnect de aeroportos incompleto")
    size, version, kind, rid, count, part, parts = struct.unpack_from("<7I", raw)
    if kind != AIRPORT_LIST_ID or rid != request_id:
        raise ValueError("ID de pacote SimConnect inesperado")
    if size != len(raw) or count > 25000 or not 1 <= parts <= 5000 or part >= parts:
        raise ValueError("Cabeçalho do catálogo de aeroportos inválido")
    if not count:
        # Bytes adicionais de alinhamento podem existir mesmo numa página vazia.
        if len(raw) > 32:
            raise ValueError("Lista vazia com dados extras")
        return part, parts, {}

    candidates = []
    for start in (28, 32):
        for stride, latitude_offset in ((33, 9), (36, 12), (40, 16)):
            remaining = size - start - count * stride
            # O MSFS 2020 pode declarar dwArraySize=N, mas dwSize inclui
            # rgData[1] de tamanho 33 ALÉM dos N registros enumerados.
            # Caso real reportado: 20.587 = 28 + 622*33 + 33.
            # Esse único registro extra pertence ao envelope C; jamais
            # deve ser promovido a aeroporto nem corrigir dwArraySize.
            has_extra_sdk_slot = remaining == stride
            pad_only = 0 <= remaining <= 7 and (
                not remaining or not any(raw[size - remaining:]))
            if not (has_extra_sdk_slot or pad_only):
                continue
            plausible = 0
            airports = {}
            for index in range(count):
                item = raw[start + index * stride:start + (index + 1) * stride]
                try:
                    ident = item[:6].split(b"\x00", 1)[0].decode("ascii").strip().upper()
                    lat, lon, altitude = struct.unpack_from("<ddd", item, latitude_offset)
                except (UnicodeDecodeError, struct.error):
                    continue
                if (not 1 <= len(ident) <= 6 or not ident.isalnum()
                        or not math.isfinite(lat) or not math.isfinite(lon)
                        or not math.isfinite(altitude)
                        or not -90 <= lat <= 90 or not -180 <= lon <= 180
                        or not -1500 <= altitude <= 12000):
                    continue
                plausible += 1
                if ICAO.fullmatch(ident):
                    airports[ident] = (lat, lon)
            # Verificação forte: o layout correto deve decodificar uma
            # fração substancial das coordenadas, inclusive ICAOs não-4.
            if plausible >= max(1, count // 2):
                candidates.append((plausible, len(airports),
                                   1 if remaining==0 else 0, start,
                                   stride, airports))
    if not candidates:
        raise ValueError(
            f"Layout do catálogo MSFS não reconhecido: pacote={size} bytes, "
            f"registros={count}; esperados offsets 28/32, entradas 33/36/40")
    candidates.sort(reverse=True, key=lambda x: x[:3])
    if len(candidates) > 1 and candidates[0][:3] == candidates[1][:3]:
        # Melhor bloquear o mercado que confundir coordenadas entre layouts.
        raise ValueError("Layout de aeroportos MSFS ambíguo; nenhum dado externo será usado")
    return part, parts, candidates[0][-1]


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
            self._airport_errors_seen=set()
            self._catalog_requested=False
            self._detail_defined=False
            self._detail_requests={}
            self._detail_next=detail.REQUEST_START
            self.detail_callbacks=(lambda icao,values:None,lambda icao,error:None)
            super().__init__()
            try:
                func=self.dll.SimConnect.SimConnect_RequestFacilitiesList
                func.restype=ctypes.c_long
                func.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32]
                self._airport_list_function=func
            except (AttributeError,OSError) as exc:
                self._airport_list_function=None
                self._report_airport_error("DLL SimConnect sem listagem de aeroportos: "+str(exc))

        def request_airport_detail(self,icao):
            """One trusted ICAO from the live MSFS catalog, never arbitrary URL."""
            if not isinstance(icao,str) or not detail.ICAO.fullmatch(icao):
                return False
            try:
                add=self.dll.SimConnect.SimConnect_AddToFacilityDefinition
                request=self.dll.SimConnect.SimConnect_RequestFacilityData
                add.restype=request.restype=ctypes.c_long
                add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_char_p]
                request.argtypes=[ctypes.c_void_p,ctypes.c_uint32,
                                 ctypes.c_uint32,ctypes.c_char_p,ctypes.c_char_p]
                if not self._detail_defined:
                    for field in detail.FIELDS:
                        hr=add(self.hSimConnect,detail.DEFINE_ID,field.encode('ascii'))
                        if hr!=0:
                            raise ValueError('Definição de instalações rejeitada: '+field)
                    self._detail_defined=True
                if self._detail_next>detail.REQUEST_START+1000:
                    return False
                rid=self._detail_next
                self._detail_next+=1
                collector=detail.DetailCollector(icao)
                hr=request(self.hSimConnect,detail.DEFINE_ID,rid,icao.encode('ascii'),b'')
                if hr!=0:
                    raise ValueError('Instalações '+icao+': HRESULT '+str(hr))
                self._detail_requests[rid]=collector
                return True
            except (AttributeError,OSError,TypeError,ValueError,RuntimeError) as exc:
                self.detail_callbacks[1](icao,str(exc))
                return False

        def _report_airport_error(self, message):
            if message not in self._airport_errors_seen:
                self._airport_errors_seen.add(message)
                self._on_error(message)

        def request_airport_catalog(self):
            if self._catalog_requested:return True
            if self._airport_list_function is None:return False
            self._airport_collector=AirportCatalogCollector()
            hr=self._airport_list_function(self.hSimConnect,0,REQUEST_ID)
            if hr!=0:
                self._report_airport_error(f"SimConnect_RequestFacilitiesList recusou: HRESULT {hr}")
                return False
            self._catalog_requested=True
            return True

        def my_dispatch_proc(self,pData,cbData,pContext):
            kind=pData.contents.dwID
            if kind in (detail.DATA_ID,detail.DATA_END_ID):
                try:
                    size=int(pData.contents.dwSize)
                    if not (16<=size<=detail.MAX_PACKET and size<=int(cbData)):
                        raise ValueError('Pacote de instalações grande ou incompleto.')
                    raw=ctypes.string_at(pData,size)
                    rid=struct.unpack_from('<I',raw,12)[0]
                    collector=self._detail_requests.get(rid)
                    if not collector:
                        return super().my_dispatch_proc(pData,cbData,pContext)
                    if kind==detail.DATA_ID:
                        collector.feed(raw,rid)
                    else:
                        detail.parse_facility_end(raw,rid)
                        self._detail_requests.pop(rid,None)
                        self.detail_callbacks[0](collector.icao,collector.finish())
                except (ValueError,TypeError,struct.error,ctypes.ArgumentError) as exc:
                    if 'collector' in locals() and collector is not None:
                        self._detail_requests.pop(rid,None)
                        self.detail_callbacks[1](collector.icao,str(exc))
                return
            if kind==AIRPORT_LIST_ID:
                try:
                    length=int(pData.contents.dwSize)
                    if not (28<=length<=4*1024*1024 and length<=int(cbData)):
                        raise ValueError("Comprimento inválido do pacote de aeroportos")
                    buf=ctypes.string_at(pData,length)
                    airports=self._airport_collector.feed(buf)
                    if airports is not None:self._on_catalog(airports)
                except (ValueError,struct.error,ctypes.ArgumentError) as exc:
                    self._report_airport_error(str(exc))
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
