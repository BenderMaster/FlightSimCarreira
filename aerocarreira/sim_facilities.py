"""Consulta opcional ao banco de aeroportos do MSFS 2020 pelo SimConnect SDK.

Solicita coordenadas por ICAO (nunca catálogo global de ~40 mil instalações).
Se o wrapper ou a DLL não exportarem a API, não substitui silenciosamente
as coordenadas nem finge que foram fornecidas pelo simulador.
"""
from __future__ import annotations
import ctypes
import math
import re
import struct

ICAO=re.compile(r'^[A-Z0-9]{4}$')
FACILITY_RECV_ID=29  # SIMCONNECT_RECV_ID_FACILITY_DATA, enum MSFS 2020
FACILITY_END_ID=30
FACILITY_DEF_ID=999
REQUEST_BASE=5000


class FacilityDataPacket(ctypes.Structure):
    _fields_=[
        ('dwSize',ctypes.c_uint32),('dwVersion',ctypes.c_uint32),('dwID',ctypes.c_uint32),
        ('UserRequestId',ctypes.c_uint32),('UniqueRequestId',ctypes.c_uint32),
        ('ParentUniqueRequestId',ctypes.c_uint32),('Type',ctypes.c_uint32),
        ('IsListItem',ctypes.c_uint8),('_pad',ctypes.c_ubyte*3),
        ('ItemIndex',ctypes.c_uint32),('ListSize',ctypes.c_uint32),
        ('Data',ctypes.c_uint32)]


def decode_airport_packet(ptr, nbytes, request_ids):
    """Verifica o tipo, ID, tamanho e coordenadas antes de confiar na DLL."""
    if nbytes < ctypes.sizeof(FacilityDataPacket)+12:
        return None
    msg=ctypes.cast(ptr,ctypes.POINTER(FacilityDataPacket)).contents
    icao=request_ids.get(msg.UserRequestId)
    if not icao or msg.dwID!=FACILITY_RECV_ID or msg.dwSize>nbytes:
        return None
    # Duas propriedades FLOAT64 em sequência: LATITUDE, LONGITUDE.
    offset=FacilityDataPacket.Data.offset
    if nbytes < offset+16:return None
    lat,lon=struct.unpack('<dd',ctypes.string_at(ctypes.addressof(msg)+offset,16))
    if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
        return None
    return {'icao':icao,'lat':lat,'lon':lon,'source':'MSFS 2020 SimConnect facility'}


def connection_class():
    """Wrapper base carregado apenas no Windows, dentro do worker."""
    from SimConnect import SimConnect

    class AirportFacilityConnection(SimConnect):
        def __init__(self, callback):
            self._airport_callback=callback
            self._airport_pending={}
            self._next_airport_request=REQUEST_BASE
            self._airport_available=False
            super().__init__()
            try:
                dll=self.dll.SimConnect
                add=dll.SimConnect_AddToFacilityDefinition
                request=dll.SimConnect_RequestFacilityData
                add.restype=ctypes.c_long
                add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_char_p]
                request.restype=ctypes.c_long
                request.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,
                                  ctypes.c_char_p,ctypes.c_char_p]
                for field in (b'OPEN AIRPORT',b'LATITUDE',b'LONGITUDE',b'CLOSE AIRPORT'):
                    if add(self.hSimConnect,FACILITY_DEF_ID,field)!=0:
                        raise OSError('Definição de aeroporto recusada')
                self._facility_request=request
                self._airport_available=True
            except (AttributeError,OSError,ValueError):
                self._airport_available=False

        def request_airport(self, code):
            code=str(code).strip().upper()
            if not self._airport_available or not ICAO.fullmatch(code):
                return False
            rid=self._next_airport_request
            self._next_airport_request+=1
            if self._next_airport_request>500000:self._next_airport_request=REQUEST_BASE
            self._airport_pending[rid]=code
            ok=self._facility_request(self.hSimConnect,FACILITY_DEF_ID,rid,code.encode('ascii'),b'')
            if ok!=0:
                self._airport_pending.pop(rid,None)
                return False
            return True

        def my_dispatch_proc(self,pData,cbData,pContext):
            dwid=pData.contents.dwID
            if dwid==FACILITY_RECV_ID:
                try:
                    item=decode_airport_packet(pData,cbData,self._airport_pending)
                    if item:self._airport_callback(item)
                except (ValueError,TypeError,OverflowError,ctypes.ArgumentError):
                    pass
                return
            if dwid==FACILITY_END_ID:
                return
            super().my_dispatch_proc(pData,cbData,pContext)

    return AirportFacilityConnection
