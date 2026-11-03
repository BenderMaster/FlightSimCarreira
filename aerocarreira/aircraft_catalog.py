"""Leitura LOCAL de aeronaves instaladas no MSFS 2020.

Não consulta propriedade/licença da conta Microsoft e não modifica arquivos do jogo.
Os arquivos da instalação de addons são tratados como dados não confiáveis.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import configparser
import os
import re


@dataclass(frozen=True)
class InstalledAircraft:
    title: str
    aircraft_folder: str
    source: str
    ui_manufacturer: str = ""
    ui_type: str = ""
    ui_variation: str = ""
    texture: str = ""

    def to_dict(self):
        return asdict(self)


def packages_root_from_cfg(path: Path) -> Path | None:
    """Lê InstalledPackagesPath do UserCfg.opt, sem depender da pasta Steam."""
    try:
        if not path.is_file() or path.stat().st_size > 2_000_000:
            return None
        raw = path.read_text(encoding='utf-8-sig', errors='replace')
        candidates = re.findall(r'^\s*InstalledPackagesPath\s+"([^"]+)"\s*$', raw, re.M | re.I)
        if not candidates:
            return None
        folder = Path(candidates[-1]).expanduser()
        return folder if folder.is_dir() else None
    except (OSError, ValueError):
        return None


def detect_package_roots(env: dict | None = None) -> list[Path]:
    env = os.environ if env is None else env
    appdata = Path(env.get('APPDATA') or Path.home() / 'AppData' / 'Roaming')
    local = Path(env.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    options = (
        appdata / 'Microsoft Flight Simulator' / 'UserCfg.opt',
        local / 'Packages' / 'Microsoft.FlightSimulator_8wekyb3d8bbwe' / 'LocalCache' / 'UserCfg.opt',
    )
    result = []
    for option in options:
        folder = packages_root_from_cfg(option)
        if folder is not None and folder not in result:
            result.append(folder)
    return result


def _parse_file(path: Path, source: str) -> list[InstalledAircraft]:
    try:
        if path.stat().st_size > 2_000_000 or path.is_symlink():
            return []
        # configparser não aceita linhas soltas em alguns configs de addons.
        data = path.read_text(encoding='utf-8-sig', errors='replace')
        cfg = configparser.ConfigParser(interpolation=None, strict=False)
        cfg.read_string(data)
    except (OSError, configparser.Error, UnicodeError, ValueError):
        return []
    items = []
    for section in cfg.sections():
        if not re.fullmatch(r'FLTSIM\.\d+', section, re.I):
            continue
        title = cfg.get(section, 'title', fallback='').strip().strip('"')
        if not title or len(title) > 180 or any(ord(ch) < 32 for ch in title):
            continue
        # Configs falsos não podem produzir código nem caminho executável.
        def field(name):
            return cfg.get(section, name, fallback='').strip().strip('"')[:180]
        items.append(InstalledAircraft(title, path.parent.name, source,
            field('ui_manufacturer'),field('ui_type'),field('ui_variation'),field('texture')))
    return items


def scan_installed_aircraft(roots: list[Path] | None = None, *, max_packages: int = 2500,
                            max_cfg: int = 6000) -> list[InstalledAircraft]:
    """Descobre only Official/Community, com limite fixo, sem varrer disco inteiro.

    Pasta protegida/cifrada do Marketplace pode não ser legível: resultado parcial.
    """
    roots = detect_package_roots() if roots is None else roots
    entries: dict[str, InstalledAircraft] = {}
    seen_cfg = 0
    for root in roots:
        root = Path(root)
        for parent_name in ('Community', 'Official'):
            parent = root / parent_name
            if not parent.is_dir():
                continue
            if parent_name == 'Community':
                sources = [(parent, 'Community')]
            else:
                try:
                    sources = [(p, f'Official/{p.name}') for p in sorted(parent.iterdir()) if p.is_dir()][:10]
                except OSError:
                    continue
            for folder, source in sources:
                try:
                    packages = sorted((x for x in folder.iterdir() if x.is_dir()), key=lambda x:x.name.lower())[:max_packages]
                except (PermissionError, OSError):
                    continue
                for package in packages:
                    # Algumas aeronaves usam estrutura SimObjects/Airplanes e outras Aircrafts.
                    for container in ('SimObjects/Airplanes','SimObjects/Helicopters'):
                        root_aircraft = package / container
                        if not root_aircraft.is_dir():
                            continue
                        try:
                            models = [p for p in root_aircraft.iterdir() if p.is_dir()][:250]
                        except OSError:
                            continue
                        for model in models:
                            cfg_file = model / 'aircraft.cfg'
                            if not cfg_file.is_file():
                                continue
                            for found in _parse_file(cfg_file, source):
                                # Prioridade Community se título repetido, útil para livery.
                                existing=entries.get(found.title.casefold())
                                if existing is None or (found.source=='Community' and existing.source!='Community'):
                                    entries[found.title.casefold()] = found
                            seen_cfg += 1
                            if seen_cfg >= max_cfg:
                                return sorted(entries.values(), key=lambda x:x.title.casefold())
    return sorted(entries.values(), key=lambda x:x.title.casefold())
