"""Manifestos determinísticos e limites de carga para contratos de carreira.

Os nomes são personagens fictícios e os pesos operacionais são estimativas
simuladas, não dados biométricos de pessoas reais. Nunca exceder MTOW nem
modificar o peso do piloto na estação 1.
"""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
from math import isfinite

KG_TO_LB=2.20462262185
LB_TO_KG=1/KG_TO_LB

# Um item/passageiro por missão por enquanto. O assento 2 ou primeiro slot
# livre deve ser conferido pelo MSFS antes de qualquer escrita.
CARGO_ITEMS=(
    ('Engradado de vinhos',26),('Caixa de equipamentos fotográficos',18),
    ('Medicamentos refrigerados',22),('Peças de manutenção aeronáutica',32),
    ('Instrumentos musicais',29),('Documentos e encomendas',12),
    ('Equipamentos de informática',38),('Pequena carga de suprimentos',42),
)
PASSENGERS=(
    ('Flávia Martins',72),('Marcos Andrade',82),('Renata Carvalho',65),
    ('João Ribeiro',78),('Aline Fernandes',68),('Gabriel Oliveira',84),
    ('Cecília Duarte',70),('Bruno Nascimento',86),
)
PROFILES={
    'cargo':('Transporte de carga',CARGO_ITEMS,'cargo'),
    'tourism':('Voo turístico',PASSENGERS,'passageiro'),
    'passenger':('Transporte de passageiro',PASSENGERS,'passageiro'),
    'airtaxi':('Táxi aéreo',PASSENGERS,'passageiro'),
    'humanitarian':('Ajuda humanitária',(('Kits de primeiros socorros',30),('Doações para comunidade',35)),'cargo'),
    'medical':('Transporte médico',(('Maleta médica e insumos',24),('Oxigênio e equipamentos portáteis',35)),'cargo'),
    'executive':('Voo executivo',PASSENGERS,'passageiro'),
    'rescue':('Busca e resgate',(('Kit de resgate e rádio',38),('Materiais de busca',31)),'cargo'),
    'special':('Operação especial',(('Amostras de pesquisa',21),('Instrumentos de medição',34)),'cargo'),
}
MODEL_STATION_LIMIT_KG={'c152':95,'c172':160,'g58':220,'kingair':420,'cj4':550}


def assign_manifest(mission):
    """Mesma missão gera sempre mesmo nome/peso; dados antigos preservados."""
    if getattr(mission,'payload_kg',0)>0 and getattr(mission,'manifest_description',''):
        return mission
    category=getattr(mission,'category','cargo')
    label,options,kind=PROFILES.get(category,PROFILES['cargo'])
    digest=sha256(mission.id.encode('utf-8')).digest()
    name,kg=options[int.from_bytes(digest[:4],'big')%len(options)]
    # Manifestações leves regionais cabem potencialmente em aviação geral;
    # a verificação MTOW/CG definitiva fica para SimConnect.
    plane=getattr(mission,'employer_plane',None)
    limit=MODEL_STATION_LIMIT_KG.get(plane or 'c152',95)
    kg=min(float(kg),limit)
    return replace(mission,
        title=f'{label} • {name}',
        manifest_description=name,payload_kind=kind,payload_kg=kg)


def payload_limits(sample, mission, station=2):
    """Valida aeronave, ocupação e peso antes de liberar comando físico."""
    kg=float(getattr(mission,'payload_kg',0) or 0)
    if not isfinite(kg) or not 0<kg<2500:
        raise ValueError('Manifesto sem peso válido; carga recusada.')
    if not sample.on_ground:
        raise ValueError('Carregamento de peso permitido apenas em solo.')
    count=sample.payload_station_count
    if count is None or not (2 <= count <= 15):
        raise ValueError('Estação de carga indisponível no MSFS; nenhuma escrita realizada.')
    if not (1 < station <= count):
        raise ValueError('Estação de passageiros/carga não existe na aeronave.')
    from .contracts import aircraft_model
    code=aircraft_model(sample.aircraft_title)
    if code is None:
        raise ValueError('Modelo da aeronave não reconhecido para carga segura.')
    if kg>MODEL_STATION_LIMIT_KG.get(code,0):
        raise ValueError('Carga supera limite conservador da estação selecionada.')
    current=sample.payload_station_2_lbs if station==2 else None
    if current is None or not isfinite(current) or current<0:
        raise ValueError('Peso atual da estação indisponível; não sobrescrever passageiros.')
    total=sample.total_weight_lbs
    mtow=sample.max_gross_weight_lbs
    if total is None or mtow is None or not isfinite(total) or not isfinite(mtow) or mtow<=0:
        raise ValueError('MTOW/peso da aeronave indisponível no SimConnect.')
    target=round(kg*KG_TO_LB,2)
    projected=total-current+target
    if projected>mtow:
        raise ValueError(
            f'Peso de decolagem estimado {projected:.0f} lb excede MTOW {mtow:.0f} lb. '
            'Reduza combustível pelo abastecimento antes de aceitar ou despachar.')
    return {'station':station,'current_lbs':current,'target_lbs':target,
            'projected_lbs':round(projected,2),'max_lbs':mtow,
            'weight_ok':True,'payload_kg':kg}
