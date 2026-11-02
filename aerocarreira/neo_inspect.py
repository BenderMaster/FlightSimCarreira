"""Descoberta e inspeção segura dos dados NeoFly, sem escrever na origem.

Aceita candidatos common.db e std.bin. Alguns NeoFly 4 usam std.bin,
que NÃO deve ser presumido SQLite; formatos desconhecidos não são decifrados.
"""
from __future__ import annotations
import json
import os
import shutil
import sqlite3
from pathlib import Path
from collections.abc import Mapping


NEOFLY_NAMES = ("common.db", "std.bin")


def discover_neofly_databases(
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
) -> list[Path]:
    """Procura nomes conhecidos apenas em pastas habituais do NeoFly.

    Não varre o disco inteiro, não abre conteúdos, não altera arquivos.
    Um NeoFly extraído em pasta personalizada pode exigir seleção manual.
    """
    env = os.environ if env is None else env
    home_path = Path(home).expanduser() if home is not None else Path.home()
    programdata = Path(env.get("PROGRAMDATA") or "C:/ProgramData")
    localappdata = Path(env.get("LOCALAPPDATA") or home_path / "AppData" / "Local")
    roaming = Path(env.get("APPDATA") or home_path / "AppData" / "Roaming")
    roots: list[Path] = []
    for parent in (programdata, localappdata / "Programs", localappdata, roaming,
                   home_path / "Documents", home_path / "Downloads"):
        for name in ("NeoFly", "NeoFly4", "NeoFly 4"):
            roots.append(parent / name)
    results: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            continue
        try:
            # Caminhos diretos e subpastas limitadas à instalação NeoFly.
            matches = (candidate for filename in NEOFLY_NAMES
                       for candidate in root.rglob(filename))
            for candidate in matches:
                if candidate.is_file() and not candidate.is_symlink():
                    resolved = candidate.resolve()
                    results[os.path.normcase(str(resolved))] = resolved
        except (PermissionError, OSError):
            continue
    return sorted(results.values(), key=lambda x: str(x).lower())


def inspect_neofly(source: str | Path, workspace: str | Path) -> dict:
    src = Path(source).expanduser().resolve(strict=True)
    out_dir = Path(workspace).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        raise ValueError("Selecione um arquivo (common.db ou std.bin), não uma pasta.")
    if src.stat().st_size > 2 * 1024**3:
        raise ValueError("Arquivo maior que 2 GiB: inspeção recusada por segurança.")
    safe_copy = out_dir / "neofly_copia_local.db"
    if src == safe_copy.resolve():
        raise ValueError("Selecione o banco original, não a cópia de análise.")
    shutil.copy2(src, safe_copy)  # sempre uma cópia separada
    with safe_copy.open("rb") as stream:
        header = stream.read(16)
    report = {
        "kind": "neofly-schema-report",
        "format": "SQLite" if header == b"SQLite format 3\x00" else "desconhecido",
        "size_bytes": safe_copy.stat().st_size,
        "read_only": True,
        "source_modified": False,
        "contains_personal_records": False,
        "tables": [],
    }
    if report["format"] == "SQLite":
        # immutable=1 evita journal/WAL sobre a cópia. NeoFly deve estar FECHADO.
        uri = safe_copy.as_uri() + "?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        try:
            conn.execute("PRAGMA query_only=ON")
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            for (table,) in rows:
                quoted_table = '"' + table.replace('"','""') + '"'
                columns = conn.execute(f'PRAGMA table_info({quoted_table})').fetchall()
                report["tables"].append({"table": table, "columns": [
                    {"name": col[1], "sqlite_type": col[2], "primary_key": bool(col[5])}
                    for col in columns]})
        finally:
            conn.close()
    else:
        report["note"] = "Formato não SQLite reconhecido. Nenhuma tentativa de leitura, extração ou decriptação foi feita. std.bin pode usar outro formato."
    report_path = out_dir / "neofly_schema_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
