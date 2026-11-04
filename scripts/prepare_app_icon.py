"""Reaproveita a arte do ícone aprovada pelo piloto, sem redesenhar a marca.

Executar antes do PyInstaller. A origem PNG vem da imagem aprovada (64x64)
e o arquivo .ICO contém tamanhos para Windows 11, taskbar e Explorer.
"""
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"assets"/"flight_sim_carreira_approved.png"
OUTPUT=ROOT/"assets"/"flight_sim_carreira.ico"

def main():
    if not SOURCE.is_file():raise FileNotFoundError(SOURCE)
    with Image.open(SOURCE) as im:
        icon=im.convert("RGBA").resize((256,256),Image.Resampling.LANCZOS)
        icon.save(OUTPUT,format="ICO",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    if OUTPUT.stat().st_size<500:raise RuntimeError("Ícone Windows inválido")
    print("Ícone Windows aprovado:",OUTPUT,OUTPUT.stat().st_size,"bytes")

if __name__=="__main__":
    main()
