"""Manifestos determinísticos, ficcionais e fisicamente conservadores.

Cada ID de contrato retorna sempre o mesmo passageiro, carga e massa.
Nenhum passageiro representa pessoa real, e peso é da missão (não do piloto).
"""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
from .domain import Mission

PEOPLE=("Flávia Martins","Mariana Costa","Eduardo Ribeiro","Rafael Almeida",
        "Ana Beatriz Souza","Paulo Henrique Lima","Juliana Carvalho","Luísa Ferreira",
        "André Oliveira","Camila Nascimento","Ricardo Moura","Beatriz Vasconcelos")
CARGO=(
    ("Engradado de vinhos",18),
    ("Equipamento fotográfico",12),
    ("Peças de manutenção aeronáutica",23),
    ("Documentos jurídicos lacrados",6),
    ("Caixas de medicamentos",14),
    ("Componentes de rádio",17),
    ("Amostras laboratoriais",8),
    ("Peças eletrônicas",11),
    ("Malote de correspondências",9),
    ("Materiais de pesquisa científica",15))
SPECIAL=(("Equipamento de radiocomunicação",26),("Ferramentas de inspeção",21),
         ("Sensores ambientais",17),("Instrumentos de navegação",24))
MEDICAL=(("Paciente e equipe de apoio",140),("Paciente em transferência",75),
         ("Vacinas sob refrigeração",18))
AID=(("Kits de primeiros socorros",20),("Cestas de alimentos",27),
     ("Suprimentos de emergência",25))

def mission_manifest(m: Mission) -> Mission:
    if m.manifest_label is not None and m.payload_kg>=0:
        return m
    seed=int.from_bytes(sha256((m.id+':manifest-v1').encode()).digest()[:8],'big')
    kind=m.category
    if kind in ('tourism','passenger','airtaxi','executive'):
        name=PEOPLE[seed%len(PEOPLE)]
        mass=61+(seed//17)%25
        text=('Voo turístico' if kind=='tourism' else 'Transporte de passageiro')+' — '+name
        return replace(m,title=text,manifest_label=name,payload_kg=float(mass),
                       passenger_count=1,manifest_kind='passenger')
    goods=MEDICAL if kind=='medical' else (AID if kind=='humanitarian'
          else SPECIAL if kind in ('special','rescue') else CARGO)
    label,mass=goods[seed%len(goods)]
    prefix='Transporte médico' if kind=='medical' else ('Apoio humanitário' if kind=='humanitarian' else
           'Operação especial' if kind in ('special','rescue') else 'Transporte de carga')
    return replace(m,title=prefix+' — '+label,manifest_label=label,
                   payload_kg=float(mass),passenger_count=0,manifest_kind='cargo')
