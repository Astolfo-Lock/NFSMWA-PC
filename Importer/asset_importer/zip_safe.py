from __future__ import annotations

import zipfile
from pathlib import Path


class ZipSafetyError(ValueError):
    pass


def normalize_zip_name(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def is_safe_zip_name(name: str) -> bool:
    if not name or "\x00" in name:
        return False
    raw = name.replace("\\", "/")
    if raw.startswith("/") or raw.startswith("\\"):
        return False
    if len(raw) >= 2 and raw[1] == ":":
        return False
    if raw.startswith("//"):
        return False
    for part in raw.split("/"):
        if part == "..":
            return False
    return True


def safe_destination(dest_root: Path, name: str) -> Path:
    if not is_safe_zip_name(name):
        raise ZipSafetyError(f"Ruta ZIP rechazada: {name}")
    dest_root = dest_root.resolve()
    relative = Path(*[part for part in normalize_zip_name(name).split("/") if part not in ("", ".")])
    target = (dest_root / relative).resolve()
    try:
        target.relative_to(dest_root)
    except ValueError as exc:
        raise ZipSafetyError(f"Ruta ZIP fuera del destino: {name}") from exc
    return target


def iter_safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    safe: list[zipfile.ZipInfo] = []
    for info in archive.infolist():
        if info.is_dir():
            if not is_safe_zip_name(info.filename) and info.filename not in ("", "/"):
                raise ZipSafetyError(f"Ruta ZIP rechazada: {info.filename}")
            continue
        if not is_safe_zip_name(info.filename):
            raise ZipSafetyError(f"Ruta ZIP rechazada: {info.filename}")
        safe.append(info)
    return safe


def extract_named(archive: zipfile.ZipFile, name: str, dest_root: Path) -> Path:
    if name not in archive.namelist():
        raise FileNotFoundError(f"Falta {name} en el archivo ZIP.")
    target = safe_destination(dest_root, Path(name).name)
    target.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(name) as src, target.open("wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
    return target
