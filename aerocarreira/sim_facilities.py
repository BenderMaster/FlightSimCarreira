"""Aeroportos diretamente do banco de instalações do MSFS 2020 via SimConnect.

O wrapper Python-SimConnect despacha AIRPORT_LIST aos objetos em sm.Facilities,
mas seu dump padrão só imprime dados e usa a estrutura de ICAO do MSFS 2024.
Implementamos decodificação explícita do pacote 2020 (ident[6]+region[3]+3x
double = 33 bytes) sem depender do banco externo airportsdata.

Em caso de indisponibilidade, retorna falha e NÃO declara coordenadas externas
como sendo fornecidas pelo simulador.
"""
from __future__ import annotations
import ctypes
import re
import struct
from types import SimpleNamespace


def decode_airport_packet(raw: bytes) -> tuple[dict, list[tuple[str,float,float]]]:
    """Decodifica pacote SIMCONNECT_RECV_AIRPORT_LIST MSFS 2020."""
    if not isinstance(raw,(bytes,bytearray)) or len(raw)<28:
        raise ValueError('Cabeçalho SimConnect incompleto')
    size,version,event_id,request_id,count,entry_number,total_packets=struct.unpack_from('<7I',raw,0)
    if size!=len(raw) or count>10000 or total_packets>10000 or total_packets==0:
        raise ValueError('Tamanho do pacote/contadores inválidos')
    needed=28+count*33
    if needed>len(raw):
        raise ValueError('Pacote de aeroportos truncado')
    airports=[]
    for i in range(count):
        at=28+i*33
        icao=bytes(raw[at:at+6]).split(b'\0',1)[0].decode('ascii','ignore').upper()
        if not re.fullmatch(r'[A-Z0-9]{4}',icao):
            continue
        lat,lon,_height=struct.unpack_from('<ddd',raw,at+9)
        if -20.0<=lat<=1.0 and -51.0<=lon<=-33.0:
            airports.append((icao,round(lat,8),round(lon,8)))
    return dict(request_id=request_id,packet=entry_number,total=total_packets),airports


class AirportFeed:
    def __init__(self,sm,callback):
        self.sm=sm
        self.REQUEST_ID=sm.new_request_id()
        self.parent=SimpleNamespace(dump=lambda raw:None)
        self.callback=callback
        self.pending={}
        self.received=set()
        self.done=False

    def dump(self,p_data):
        if self.done:return
        try:
            n=int(p_data.contents.dwSize)
            if n<28 or n>400000:return
            raw=ctypes.string_at(p_data,n)
            header,arr=decode_airport_packet(raw)
            if header['request_id']!=self.REQUEST_ID.value:return
            self.received.add(header['packet'])
            for icao,lat,lon in arr:self.pending[icao]=(lat,lon)
            if len(self.received)>=header['total']:
                self.done=True
                # Lista reduzida à região coberta pelo mercado atual;
                # não retorna milhares de aeroportos não utilizados.
                self.callback([(key,*self.pending[key]) for key in sorted(self.pending)])
        except (AttributeError,ValueError,OverflowError,struct.error,OSError):
            # Uma mensagem inválida nunca derruba telemetria de voo.
            return


def register_airport_listener(sm,callback):
    from SimConnect.Enum import SIMCONNECT_FACILITY_LIST_TYPE
    item=AirportFeed(sm,callback)
    sm.Facilities.append(item)
    response=sm.dll.RequestFacilitiesList(
        sm.hSimConnect,
        SIMCONNECT_FACILITY_LIST_TYPE.SIMCONNECT_FACILITY_LIST_TYPE_AIRPORT,
        item.REQUEST_ID.value)
    if response not in (0,None):
        sm.Facilities.remove(item)
        raise RuntimeError('SimConnect recusou enumeração de aeroportos')
    return item
