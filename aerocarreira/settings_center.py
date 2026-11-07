"""Midnight Settings Center: validated preferences and safe profile archives.

Only Tk's owner thread accesses active SQLite. Backups use SQLite's online
backup API, not a raw copy of a WAL database. Restoration imports NEW profiles
and never replaces the active save.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone

DEFAULTS = {
    'autoconnect': True,
    'reconnect': True,
    'interface_scale': 100,
    'reduced_motion': False,
    'satellite_default': False,
    'notifications': True,
    'redact_diagnostics': True,
}
BOOL_KEYS = set(DEFAULTS)-{'interface_scale'}
MAX_ZIP = 384*1024*1024

def config_path(root: Path) -> Path:
    return Path(root)/'settings-v087.json'

def read_global(root: Path) -> dict:
    try:
        data=json.loads(config_path(root).read_text(encoding='utf-8'))
    except (OSError,ValueError,TypeError):
        return dict(DEFAULTS)
    if not isinstance(data,dict):
        return dict(DEFAULTS)
    return {key:(value if type(value) is type(default) and
                 (key!='interface_scale' or value in (80,90,100,110,125,150))
                 else default)
            for key,default in DEFAULTS.items()
            for value in [data.get(key,default)]}

def save_global(root: Path, key: str, value):
    if key not in DEFAULTS or (key in BOOL_KEYS and type(value) is not bool) or (
        key=='interface_scale' and (type(value) is not int or
        value not in (80,90,100,110,125,150))):
        raise ValueError('Preferência inválida.')
    settings=read_global(root)
    settings[key]=value
    path=config_path(root)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.new')
    try:
        with tmp.open('w',encoding='utf-8') as file:
            json.dump(settings,file,ensure_ascii=False,indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)
    return settings

def _sqlite_snapshot(conn: sqlite3.Connection, output: Path):
    target=sqlite3.connect(output)
    try:
        conn.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('Backup SQLite inconsistente.')
    finally:
        target.close()

def export_profiles(app, target: Path):
    """Archive all profiles; photos in fleet_photos travel inside each SQLite."""
    target=Path(target)
    if target.suffix.lower()!='.zip':
        raise ValueError('Backup deve ter extensão .zip.')
    target.parent.mkdir(parents=True,exist_ok=True)
    profiles=app.profiles.list()
    with tempfile.TemporaryDirectory(prefix='flightsim-backup-') as tmp:
        temp=Path(tmp)
        partial=target.with_suffix('.zip.partial')
        try:
            with zipfile.ZipFile(partial,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                manifest={'format':'flightsim-settings-087','created_utc':
                    datetime.now(timezone.utc).isoformat(),
                    'active':app.profiles.active()['id'],'profiles':profiles}
                z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
                for i,profile in enumerate(profiles):
                    source=app.profiles.database(profile['id'])
                    if not source.is_file():continue
                    shot=temp/f'profile-{i}.db'
                    if profile['id']==app.profiles.active()['id']:
                        _sqlite_snapshot(app.storage.conn,shot)
                    else:
                        src=sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True)
                        try:_sqlite_snapshot(src,shot)
                        finally:src.close()
                    z.write(shot,f"profiles/{profile['id']}/carreira.db")
                    avatar=app.profiles.path(profile['id'])/'pilot-avatar.png'
                    if avatar.is_file() and avatar.stat().st_size<=4*1024*1024:
                        z.write(avatar,f"profiles/{profile['id']}/pilot-avatar.png")
                prefs=config_path(app.profiles.root)
                if prefs.is_file() and prefs.stat().st_size<65536:
                    z.write(prefs,'settings-v087.json')
            if partial.stat().st_size>MAX_ZIP:raise ValueError('Backup excedeu o limite de segurança.')
            os.replace(partial,target)
        finally:partial.unlink(missing_ok=True)
    return len(profiles)

def import_profiles(app, source: Path):
    """Restore into distinct profiles; never alter currently open career."""
    source=Path(source)
    if not source.is_file() or source.stat().st_size>MAX_ZIP:
        raise ValueError('Arquivo de backup ausente ou grande demais.')
    restored=[]
    with zipfile.ZipFile(source,'r') as z:
        names=set(z.namelist())
        if (len(names)>150 or 'manifest.json' not in names or
                z.getinfo('manifest.json').file_size>100_000):
            raise ValueError('Pacote de backup não reconhecido.')
        if any(n.startswith('/') or '\\' in n or '..' in Path(n).parts
               for n in names):
            raise ValueError('Arquivo de backup contém caminhos inválidos.')
        manifest=json.loads(z.read('manifest.json'))
        profiles=manifest.get('profiles')
        if manifest.get('format')!='flightsim-settings-087' or not isinstance(profiles,list) or len(profiles)>30:
            raise ValueError('Formato de backup inválido.')
        # Validate every database before writing any profile.
        entries=[]
        with tempfile.TemporaryDirectory(prefix='flightsim-restore-') as tmp:
            for i,p in enumerate(profiles):
                if not isinstance(p,dict) or not re.fullmatch(r'(?:principal|[0-9a-f]{32})',str(p.get('id',''))):
                    raise ValueError('Identificador de perfil inválido no backup.')
                filename=f"profiles/{p['id']}/carreira.db"
                if filename not in names:continue
                info=z.getinfo(filename)
                if info.file_size>MAX_ZIP or info.compress_size==0:
                    raise ValueError('Banco grande demais ou inválido.')
                output=Path(tmp)/f'restore-{i}.db'
                with z.open(filename) as inp,output.open('wb') as dst:
                    total=0
                    while (chunk:=inp.read(1024*1024)):
                        total+=len(chunk)
                        if total>MAX_ZIP:raise ValueError('Banco excede o limite.')
                        dst.write(chunk)
                db=sqlite3.connect(f'file:{output.as_posix()}?mode=ro',uri=True)
                try:
                    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                        raise ValueError('Banco inconsistente.')
                    try:
                        pilot=db.execute('SELECT name,callsign,home_icao FROM pilot_profile WHERE id=1').fetchone()
                    except sqlite3.DatabaseError as exc:
                        raise ValueError('Backup sem estrutura de perfil FlightSim válida.') from exc
                finally:db.close()
                if not pilot:raise ValueError('Piloto ausente no backup.')
                entries.append((p,output,pilot))
            if not entries:raise ValueError('Nenhuma carreira restaurável encontrada.')
            for p,db_path,pilot in entries:
                # Unique new identity, not an update to existing save.
                is_test=p.get('kind')=='test'
                label='Teste' if is_test else ('Restaurado '+str(pilot[0]))[:50]
                created=app.profiles.create(label,pilot[1],pilot[2],test_admin=is_test)
                folder=app.profiles.path(created['id'])
                destination=folder/'carreira.db'
                os.replace(db_path,destination)
                photo_name=f"profiles/{p['id']}/pilot-avatar.png"
                avatar=folder/'pilot-avatar.png'
                avatar_ok=photo_name in names and z.getinfo(photo_name).file_size<=4*1024*1024
                if avatar_ok:
                    avatar.write_bytes(z.read(photo_name))
                # An old absolute portrait path cannot remain attached to the
                # newly imported profile (or point back to a different pilot).
                imported=sqlite3.connect(destination)
                try:
                    with imported:
                        imported.execute("INSERT INTO settings(key,value) VALUES('pilot_avatar_v1',?) "
                            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                            (str(avatar) if avatar_ok else '',))
                finally:imported.close()
                restored.append(created['name'])
    return restored

def sanitize_log(raw: str, redact=True) -> str:
    if not redact:return raw
    raw=re.sub(r'(?i)(?:[A-Z]:\\|/Users/|/home/)[^\s,;]+','[caminho omitido]',raw)
    raw=re.sub(r'(?i)(lat(?:itude)?|lon(?:gitude)?)\s*[:=]\s*-?\d+(?:\.\d+)?',r'\1=[omitido]',raw)
    return raw

def snapshot(app):
    from . import __version__, type_ratings
    root=app.profiles.root
    db=app.storage
    sample=app.last_sample
    available=set(getattr(app,'airline_available_codes',set()))
    return dict(version=__version__,mode=app.mode,connection='connected' if app.connected else
        ('reconnecting' if app.mode=='MSFS' else 'disconnected'),
        state=app.status_var.get(),airport_count=len(app.airport_catalog.locations)
        if app.msfs_airports_ready and app.airport_catalog else None,
        aircraft=sample.aircraft_title if sample and app.connected else None,
        telemetry_age=max(0,round(__import__('time').time()-sample.timestamp,1))
        if sample and app.connected else None,
        preferences=read_global(root),
        fuel=db.get_setting('fuel_control_enabled')=='1',
        tax=db.get_setting('income_tax_enabled')=='1',
        failures=db.get_setting('simulated_failures_enabled')=='1',
        flight_active=app.tracker.phase.value.lower()=='airborne',
        mission_active=bool(app.career.mission),
        profiles_count=len(app.profiles.list()),active_profile=app.profiles.active()['name'],
        training=type_ratings.progress(db,available),
        scan_count=getattr(app,'airline_scan_count',None),
        notice=getattr(app,'settings_notice',None))
