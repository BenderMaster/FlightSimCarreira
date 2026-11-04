"""Fotografias de aeronaves do piloto, persistidas no próprio SQLite.

Uma imagem por exemplar, nunca compartilhada por modelo. As fotos são
normalizadas para JPEG portátil com orientação EXIF e tamanho limitado;
URLs são opacas por sessão e não expõem caminho de arquivo do Windows.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from time import time_ns

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SOURCE_BYTES=16 * 1024 * 1024
MAX_PIXELS=36_000_000
MAX_OUTPUT_BYTES=2 * 1024 * 1024
Image.MAX_IMAGE_PIXELS=MAX_PIXELS


def init_photos(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS fleet_photos (
        aircraft_ref TEXT PRIMARY KEY,
        jpeg BLOB NOT NULL,
        updated_ns INTEGER NOT NULL)""")
    conn.commit()


def normalize_photo(path: Path) -> bytes:
    path=Path(path)
    if not path.is_file() or path.stat().st_size>MAX_SOURCE_BYTES:
        raise ValueError('Arquivo deve ser uma imagem de até 16 MB.')
    try:
        with Image.open(path) as source:
            source.load()
            if source.width*source.height>MAX_PIXELS:
                raise ValueError('Imagem grande demais (limite de 36 megapixels).')
            image=ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((1600,1100),Image.Resampling.LANCZOS)
            out=BytesIO()
            image.save(out,format='JPEG',quality=85,optimize=True,progressive=True)
            data=out.getvalue()
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError) as exc:
        raise ValueError('Imagem inválida ou não suportada.') from exc
    if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9') or len(data)>MAX_OUTPUT_BYTES:
        raise ValueError('Não foi possível compactar a foto para o Hangar.')
    return data


def _ensure_owned(storage, ref):
    plane=storage.fleet_manager().get(ref)
    if not plane or plane['kind']=='rented' or not (ref.startswith('legacy:') or ref.startswith('unit:')):
        raise ValueError('Foto permitida somente para aeronave adquirida nesta carreira.')
    return plane


def save_photo(storage, ref, jpeg_bytes):
    _ensure_owned(storage,ref)
    if not isinstance(jpeg_bytes,bytes) or len(jpeg_bytes)>MAX_OUTPUT_BYTES or not (
            jpeg_bytes.startswith(b'\xff\xd8') and jpeg_bytes.endswith(b'\xff\xd9')):
        raise ValueError('Foto JPEG inválida.')
    stamp=time_ns()
    with storage.conn:
        storage.conn.execute("""INSERT INTO fleet_photos(aircraft_ref,jpeg,updated_ns)
            VALUES(?,?,?) ON CONFLICT(aircraft_ref) DO UPDATE
            SET jpeg=excluded.jpeg,updated_ns=excluded.updated_ns""",
            (ref,jpeg_bytes,stamp))
    return stamp


def delete_photo(storage,ref):
    _ensure_owned(storage,ref)
    with storage.conn:
        return bool(storage.conn.execute('DELETE FROM fleet_photos WHERE aircraft_ref=?',(ref,)).rowcount)


def photo_stamps(storage):
    return {row[0]:row[1] for row in storage.conn.execute(
        'SELECT aircraft_ref,updated_ns FROM fleet_photos')}


def photo_bytes(storage):
    return {row[0]:bytes(row[1]) for row in storage.conn.execute(
        'SELECT aircraft_ref,jpeg FROM fleet_photos')}


def owned_fleet(storage):
    """Retorna apenas exemplares do jogador, sem aluguel nem empregador."""
    return [p for p in storage.fleet_manager().all() if
            p['kind']!='rented' and (p['ref'].startswith('legacy:') or p['ref'].startswith('unit:'))]
