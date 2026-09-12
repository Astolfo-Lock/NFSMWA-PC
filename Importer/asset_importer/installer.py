from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from .constants import (
    APK_DISPLAY_NAME,
    FONT_ASSETS,
    FONT_FILENAMES,
    LIBRARY_FILENAMES,
    OBB_FILENAME,
    PACKAGE_NAME,
    RUNTIME_FILES,
    VERSION_NAME,
    X86_LIBRARIES,
)
from .paths import ProjectPaths
from .validation import ValidationReport
from .zip_safe import extract_named, iter_safe_members, safe_destination

CHUNK = 1024 * 1024
ProgressFn = Callable[[str, int, str], None]
CancelFn = Callable[[], None]


class InstallError(RuntimeError):
    pass


def sha256_file(path: Path, on_progress: Callable[[int, int], None] | None = None,
                check_cancel: CancelFn | None = None) -> str:
    digest = hashlib.sha256()
    total = max(path.stat().st_size, 1)
    done = 0
    with path.open("rb") as handle:
        while True:
            if check_cancel:
                check_cancel()
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            done += len(chunk)
            if on_progress:
                on_progress(done, total)
    return digest.hexdigest()


def copy_file(src: Path, dest: Path, on_progress: Callable[[int, int], None] | None = None,
              check_cancel: CancelFn | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = max(src.stat().st_size, 1)
    done = 0
    with src.open("rb") as reader, dest.open("wb") as writer:
        while True:
            if check_cancel:
                check_cancel()
            chunk = reader.read(CHUNK)
            if not chunk:
                break
            writer.write(chunk)
            done += len(chunk)
            if on_progress:
                on_progress(done, total)


def _backup_existing(path: Path, backup_root: Path, project_root: Path) -> Path | None:
    if not path.exists():
        return None
    try:
        relative = path.resolve().relative_to(project_root.resolve())
    except ValueError:
        relative = Path(path.name)
    target = backup_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir():
        return None
    shutil.copy2(path, target)
    return target


def _replace_file(src: Path, dest: Path, backup_root: Path, project_root: Path,
                  check_cancel: CancelFn | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _backup_existing(dest, backup_root, project_root)
    tmp = dest.with_name(dest.name + ".importing")
    copy_file(src, tmp, check_cancel=check_cancel)
    os.replace(tmp, dest)


def extract_apk_tree(apk: Path, dest: Path, check_cancel: CancelFn | None = None,
                     on_progress: Callable[[int, int, str], None] | None = None) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk) as archive:
        members = iter_safe_members(archive)
        total = max(len(members), 1)
        for index, info in enumerate(members, start=1):
            if check_cancel:
                check_cancel()
            target = safe_destination(dest, info.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=CHUNK)
            if on_progress:
                on_progress(index, total, info.filename)


def extract_allowed_assets(apk: Path, staging: Path, check_cancel: CancelFn | None = None) -> None:
    libs = staging / "libs"
    fonts = staging / "fonts"
    libs.mkdir(parents=True, exist_ok=True)
    fonts.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk) as archive:
        names = set(archive.namelist())
        for item in (*X86_LIBRARIES, *FONT_ASSETS):
            if item not in names:
                raise InstallError(f"No se pudo extraer {item}.")
            if check_cancel:
                check_cancel()
            folder = libs if item in X86_LIBRARIES else fonts
            extract_named(archive, item, folder)


def write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def runtime_status(project: ProjectPaths) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for name in RUNTIME_FILES:
        target = project.native_prototype / name
        if target.is_file():
            present.append(name)
        else:
            missing.append(name)
    return present, missing


def install_assets(
    report: ValidationReport,
    project: ProjectPaths,
    source_label: str,
    check_cancel: CancelFn | None = None,
    on_stage: Callable[[str], None] | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, object]:
    project.ensure_destination_dirs()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = project.backups / stamp
    backup_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="nfsmw_import_") as raw_tmp:
        tmp = Path(raw_tmp)
        extracted = tmp / "apk"
        staging = tmp / "staging"
        extracted.mkdir()
        staging.mkdir()

        if on_stage:
            on_stage("Extrayendo el APK en un directorio temporal")
        extract_apk_tree(
            report.apk,
            extracted,
            check_cancel=check_cancel,
            on_progress=on_progress,
        )

        if on_stage:
            on_stage("Extrayendo bibliotecas x86 y fuentes permitidas")
        extract_allowed_assets(report.apk, staging, check_cancel=check_cancel)

        staged_obb = staging / OBB_FILENAME
        if on_stage:
            on_stage("Copiando el OBB intacto (sin descomprimir)")
        copy_file(
            report.obb,
            staged_obb,
            on_progress=lambda done, total: on_progress(done, total, OBB_FILENAME) if on_progress else None,
            check_cancel=check_cancel,
        )

        hashes: dict[str, dict[str, object]] = {}

        def remember(label: str, path: Path) -> None:
            if on_stage:
                on_stage(f"Calculando SHA-256 de {label}")
            digest = sha256_file(
                path,
                on_progress=lambda done, total: on_progress(done, total, label) if on_progress else None,
                check_cancel=check_cancel,
            )
            hashes[label] = {"sha256": digest, "size": path.stat().st_size}

        remember(APK_DISPLAY_NAME, report.apk)
        remember(OBB_FILENAME, staged_obb)
        for filename in LIBRARY_FILENAMES:
            remember(filename, staging / "libs" / filename)
        for filename in FONT_FILENAMES:
            remember(filename, staging / "fonts" / filename)

        if on_stage:
            on_stage("Instalando archivos con respaldo de copias existentes")

        for info in extracted.rglob("*"):
            if not info.is_file():
                continue
            if check_cancel:
                check_cancel()
            relative = info.relative_to(extracted)
            dest = project.native_analysis_apk / relative
            important = relative.as_posix() in X86_LIBRARIES or relative.as_posix() in FONT_ASSETS
            if important:
                _replace_file(info, dest, backup_root, project.root, check_cancel)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp_dest = dest.with_name(dest.name + ".importing")
                shutil.copy2(info, tmp_dest)
                os.replace(tmp_dest, dest)

        for filename in LIBRARY_FILENAMES:
            _replace_file(
                staging / "libs" / filename,
                project.native_prototype / filename,
                backup_root,
                project.root,
                check_cancel,
            )
        for filename in FONT_FILENAMES:
            _replace_file(
                staging / "fonts" / filename,
                project.fonts / filename,
                backup_root,
                project.root,
                check_cancel,
            )
        _replace_file(
            staged_obb,
            project.game_data / OBB_FILENAME,
            backup_root,
            project.root,
            check_cancel,
        )

        present, missing = runtime_status(project)
        payload = {
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "source": source_label,
            "package": PACKAGE_NAME,
            "version_name": report.version_name or VERSION_NAME,
            "version_code": report.version_code,
            "files": hashes,
            "backup": str(backup_root),
            "runtime_present": present,
            "runtime_missing": missing,
            "note": (
                "Manifiesto informativo. No se exigen hashes previos. "
                "Cada usuario debe importar su propia copia legal."
            ),
        }
        write_manifest(project.manifest, payload)
        return payload
