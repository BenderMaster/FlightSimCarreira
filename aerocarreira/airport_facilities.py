"""Verified MSFS 2020 SimConnect airport details, never synthetic airport metadata.

SimConnect_RequestFacilitiesList provides only airport ICAO/co-ordinates. This
module issues opt-in per-airport facility queries with native packet validation.
Fuel service itself is not exposed by the facility API; a FUEL parking spot is
not proof of staffed refuelling.
"""
from __future__ import annotations

import re
import struct

ICAO=re.compile(r'[A-Z0-9]{4}\Z')
DATA_ID=29
DATA_END_ID=30
DEFINE_ID=6051
REQUEST_START=6200
MAX_PACKET=65536
# The definition is shared across all requests in one SimConnect connection.
FIELDS=(
 'OPEN AIRPORT','N_RUNWAYS','N_TAXI_PARKINGS',
 'OPEN RUNWAY','PRIMARY_ILS_ICAO','SECONDARY_ILS_ICAO','EDGE_LIGHTS','CENTER_LIGHTS',
 'OPEN PRIMARY_LEFT_VASI','TYPE','CLOSE PRIMARY_LEFT_VASI',
 'OPEN PRIMARY_RIGHT_VASI','TYPE','CLOSE PRIMARY_RIGHT_VASI',
 'OPEN SECONDARY_LEFT_VASI','TYPE','CLOSE SECONDARY_LEFT_VASI',
 'OPEN SECONDARY_RIGHT_VASI','TYPE','CLOSE SECONDARY_RIGHT_VASI',
 'OPEN PRIMARY_APPROACH_LIGHTS','SYSTEM','CLOSE PRIMARY_APPROACH_LIGHTS',
 'OPEN SECONDARY_APPROACH_LIGHTS','SYSTEM','CLOSE SECONDARY_APPROACH_LIGHTS',
 'CLOSE RUNWAY',
 'OPEN TAXI_PARKING','TYPE','CLOSE TAXI_PARKING',
 'CLOSE AIRPORT'
)
# From SIMCONNECT_FACILITY_DATA_TYPE, MSFS 2020.
AIRPORT=0
RUNWAY=1
PARKING=15
APPROACH_LIGHTS=24
VASI=25
PAPI_TYPES={7,8}


def parse_facility_packet(raw, expected_request):
    """Decode one SDK packet; reject all odd sizes, missing or wrong IDs.

    SDK struct SIMCONNECT_RECV_FACILITY_DATA has Data at offset 40.
    Its DWORD Data is the beginning of a variable-size payload, not a pointer.
    """
    if not isinstance(raw,bytes) or not 44<=len(raw)<=MAX_PACKET:
        raise ValueError('Tamanho inválido da resposta de instalação.')
    size,version,kind,rid,uid,parent,ty=struct.unpack_from('<7I',raw)
    if size!=len(raw) or kind!=DATA_ID or rid!=expected_request:
        raise ValueError('Pacote ou solicitação de aeroporto inesperado.')
    item_flag=raw[28]
    if item_flag not in (0,1):
        raise ValueError('Flag de instalação inválida.')
    index,count=struct.unpack_from('<2I',raw,32)
    if count>10000 or index>count or ty not in (AIRPORT,RUNWAY,PARKING,APPROACH_LIGHTS,VASI):
        raise ValueError('Tipo ou índice de instalação inválido.')
    payload=raw[40:]
    parsed={'request_id':rid,'unique_id':uid,'parent_id':parent,
            'type':ty,'item_index':index,'list_size':count}
    if ty==AIRPORT:
        if len(payload)<8:raise ValueError('Cabeçalho de aeroporto incompleto.')
        nrun,npark=struct.unpack_from('<2i',payload)
        if not 0<=nrun<=300 or not 0<=npark<=10000:
            raise ValueError('Quantidade de pistas/estacionamentos inválida.')
        parsed.update(runways=nrun,parkings=npark)
    elif ty==RUNWAY:
        if len(payload)<16:raise ValueError('Código de ILS incompleto.')
        def text8(raw):
            value=raw.split(b'\0',1)[0].decode('ascii','ignore').strip().upper()
            return value if value.isalnum() and len(value)<=8 else ''
        parsed['ils']=bool(text8(payload[:8]) or text8(payload[8:16]))
        # Native INT8 fields follow the two CHAR[8] identifiers. Unknown
        # packing or unexpected enumerations remain unverified.
        parsed['runway_lights']=(bool(payload[16] or payload[17])
             if len(payload)>=18 and payload[16] in (0,1,2,3)
             and payload[17] in (0,1,2,3) else None)
    else:
        if len(payload)<4:raise ValueError('Campo da instalação incompleto.')
        number=struct.unpack_from('<i',payload)[0]
        if not 0<=number<=1000:raise ValueError('Tipo desconhecido de instalação.')
        parsed['number']=number
    return parsed


def parse_facility_end(raw, expected_request):
    if len(raw)<16:raise ValueError('Fim de instalações incompleto.')
    size,version,kind,request=struct.unpack_from('<4I',raw)
    if size>len(raw) or kind!=DATA_END_ID or request!=expected_request:
        raise ValueError('Fim da lista de instalações inconsistente.')
    return True


class DetailCollector:
    def __init__(self, icao):
        if not ICAO.fullmatch(icao):raise ValueError('ICAO inválido')
        self.icao=icao
        self.header=None
        self.runways={}
        self.runway_lights={}
        self.parkings={}
        self.papis={}
        self.lights={}

    def feed(self,raw,request):
        packet=parse_facility_packet(raw,request)
        ty=packet['type']
        if ty==AIRPORT:
            self.header=(packet['runways'],packet['parkings'])
        elif ty==RUNWAY:
            self.runways[packet['unique_id']]=packet['ils']
            self.runway_lights[packet['unique_id']]=packet['runway_lights']
        elif ty==PARKING:
            self.parkings[packet['unique_id']]=packet['number']==12
        elif ty==VASI:
            self.papis[packet['unique_id']]=packet['number'] in PAPI_TYPES
        elif ty==APPROACH_LIGHTS:
            self.lights[packet['unique_id']]=packet['number']>0

    def finish(self):
        header=self.header
        nrun,npark=header if header is not None else (None,None)
        # Absence of a message must remain UNKNOWN, never inferred as False.
        ils=(any(self.runways.values()) if nrun is not None and
             len(self.runways)>=nrun and nrun>0 else None)
        fuel_spot=(any(self.parkings.values()) if npark is not None and
                   len(self.parkings)>=npark and npark>0 else None)
        valid_lights=[v for v in self.runway_lights.values() if v is not None]
        lights_known=nrun is not None and nrun>0 and len(valid_lights)>=nrun
        return {'icao':self.icao,'source':'MSFS2020_SIMCONNECT_FACILITY',
                'runways':nrun,'parkings':npark,
                'runway_lights':any(valid_lights) if lights_known else None,
                'ils':ils,
                'papi':any(self.papis.values()) if self.papis else None,
                'approach_lights':any(self.lights.values()) if self.lights else None,
                'fuel_spot':fuel_spot,'fuel_service':None}
