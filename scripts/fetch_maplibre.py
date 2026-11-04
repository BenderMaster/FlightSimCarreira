"""Baixa MapLibre GL JS/CSS com versão fixa durante o build (sem tokens).

O usuário final não precisa de CDN para carregar o motor visual do mapa.
Os tiles continuam online e o mapa geométrico offline não depende dele.
"""
from pathlib import Path
from urllib.request import urlopen, Request

VERSION='5.24.0'
ROOT=Path(__file__).resolve().parents[1]/'aerocarreira'/'midnight'/'vendor'
BASE='https://cdn.jsdelivr.net/npm/maplibre-gl@'+VERSION+'/dist/'
FILES={'maplibre-gl.js':150000,'maplibre-gl.css':4000}


def fetch():
    ROOT.mkdir(parents=True,exist_ok=True)
    for name,minimum in FILES.items():
        dest=ROOT/name
        if dest.exists() and dest.stat().st_size>=minimum:
            continue
        req=Request(BASE+name,headers={'User-Agent':'FlightSimCarreiraBuild/0.7.2'})
        with urlopen(req,timeout=45) as response:
            content=response.read(8*1024*1024)
        if len(content)<minimum:
            raise RuntimeError('Arquivo MapLibre incompleto: '+name)
        dest.write_bytes(content)
        print('Obtido:',name,len(content),'bytes')
    assert all((ROOT/n).is_file() for n in FILES)

if __name__=='__main__':fetch()
