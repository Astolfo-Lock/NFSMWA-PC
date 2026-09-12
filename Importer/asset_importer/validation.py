from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .axml import parse_manifest
from .constants import (
    ELF_MACHINE_386,
    ELF_MACHINE_ARM,
    FONT_ASSETS,
    OBB_FILENAME,
    OBB_REQUIRED_PREFIXES,
    PACKAGE_NAME,
    VERSION_CODE,
    VERSION_NAME,
    X86_LIBRARIES,
)
from .zip_safe import ZipSafetyError, is_safe_zip_name, normalize_zip_name


class ValidationError(ValueError):
    pass


@dataclass
class FileReport:
    path: str
    size: int
    sha256: str | None = None


@dataclass
class ValidationReport:
    apk: Path
    obb: Path
    version_name: str
    version_code: str
    package: str
    apk_members: tuple[str, ...]
    obb_has_1x: bool
    obb_has_2x: bool
    warnings: list[str] = field(default_factory=list)


def open_zip(path: Path, label: str) -> zipfile.ZipFile:
    if not path.is_file():
        raise ValidationError(f"No existe el {label}: {path}")
    if path.stat().st_size < 4:
        raise ValidationError(f"El {label} está incompleto o vacío.")
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValidationError(f"El {label} no es un ZIP válido (corrupto o incompleto).") from exc
    return archive


def inspect_elf_machine(data: bytes) -> int | None:
    if len(data) < 20 or data[:4] != b"\x7fELF":
        return None
    return int.from_bytes(data[18:20], "little")


def require_x86_library(archive: zipfile.ZipFile, name: str) -> None:
    names = {normalize_zip_name(item) for item in archive.namelist()}
    if name not in names:
        arm_guess = name.replace("lib/x86/", "lib/armeabi-v7a/")
        if arm_guess in names:
            raise ValidationError(
                f"El APK no incluye {name}. Solo aparece la variante armeabi-v7a, "
                "que este port no puede usar."
            )
        raise ValidationError(f"El APK está incompleto: falta {name}.")
    payload = archive.read(name)
    machine = inspect_elf_machine(payload)
    if machine == ELF_MACHINE_ARM:
        raise ValidationError(f"{name} es ARM, no x86. Se rechaza la arquitectura incorrecta.")
    if machine not in (None, ELF_MACHINE_386):
        raise ValidationError(f"{name} no es una biblioteca ELF x86 (máquina {machine}).")
    if len(payload) < 16:
        raise ValidationError(f"{name} está vacío o truncado.")


def validate_apk(path: Path) -> tuple[str, str, str, tuple[str, ...]]:
    with open_zip(path, "APK") as archive:
        for info in archive.infolist():
            if info.filename and not is_safe_zip_name(info.filename):
                raise ZipSafetyError(f"El APK contiene una ruta ZIP insegura: {info.filename}")
        names = tuple(normalize_zip_name(item) for item in archive.namelist())
        for library in X86_LIBRARIES:
            require_x86_library(archive, library)
        missing_fonts = [font for font in FONT_ASSETS if font not in names]
        if missing_fonts:
            raise ValidationError(
                "El APK está incompleto; faltan fuentes:\n  " + "\n  ".join(missing_fonts)
            )
        if "AndroidManifest.xml" not in names:
            raise ValidationError("El APK no contiene AndroidManifest.xml.")
        manifest = parse_manifest(archive.read("AndroidManifest.xml"))
        if manifest.package and manifest.package != PACKAGE_NAME:
            raise ValidationError(
                f"Paquete incompatible: {manifest.package}. Se esperaba {PACKAGE_NAME}."
            )
        if manifest.version_name and manifest.version_name != VERSION_NAME:
            raise ValidationError(
                f"Versión incompatible: {manifest.version_name}. Se requiere {VERSION_NAME}."
            )
        if manifest.version_code and manifest.version_code != VERSION_CODE:
            raise ValidationError(
                f"versionCode incompatible: {manifest.version_code}. Se requiere {VERSION_CODE}."
            )
        if not manifest.version_name:
            raise ValidationError(
                f"No se pudo confirmar que el APK sea la versión {VERSION_NAME}."
            )
        version_code = manifest.version_code or VERSION_CODE
        package = manifest.package or PACKAGE_NAME
        return manifest.version_name, version_code, package, names


def validate_obb(path: Path) -> tuple[bool, bool]:
    if path.name != OBB_FILENAME:
        raise ValidationError(
            f"El OBB debe llamarse {OBB_FILENAME}. Recibido: {path.name}."
        )
    with open_zip(path, "OBB") as archive:
        for info in archive.infolist():
            if info.filename and not is_safe_zip_name(info.filename):
                raise ZipSafetyError(f"El OBB contiene una ruta ZIP insegura: {info.filename}")
        names = [normalize_zip_name(item) for item in archive.namelist()]
        has_1x = any(name.startswith(OBB_REQUIRED_PREFIXES[0]) for name in names)
        has_2x = any(name.startswith(OBB_REQUIRED_PREFIXES[1]) for name in names)
        if not has_1x or not has_2x:
            raise ValidationError(
                "El OBB no contiene los datos published.1x y published.2x requeridos."
            )
        bad = archive.testzip()
        if bad is not None:
            raise ValidationError(f"El OBB está corrupto (CRC inválido en {bad}).")
    return has_1x, has_2x


def validate_pair(apk: Path, obb: Path) -> ValidationReport:
    version_name, version_code, package, members = validate_apk(apk)
    has_1x, has_2x = validate_obb(obb)
    return ValidationReport(
        apk=apk,
        obb=obb,
        version_name=version_name,
        version_code=version_code,
        package=package,
        apk_members=members,
        obb_has_1x=has_1x,
        obb_has_2x=has_2x,
    )
