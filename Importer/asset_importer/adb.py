from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .constants import OBB_CANDIDATE_PATHS, OBB_FILENAME, PACKAGE_NAME, VERSION_CODE, VERSION_NAME

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class AdbError(RuntimeError):
    pass


class ObbAccessError(AdbError):
    pass


@dataclass(frozen=True)
class AdbDevice:
    serial: str
    state: str
    model: str = ""
    details: str = ""

    @property
    def authorized(self) -> bool:
        return self.state == "device"

    @property
    def label(self) -> str:
        extra = self.model or self.state
        return f"{self.serial} ({extra})" if extra else self.serial


@dataclass
class PhonePackage:
    apk_remote: str
    obb_remote: str
    version_name: str
    version_code: str
    device: AdbDevice


def _run(
    adb: Path,
    args: list[str],
    timeout: int = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [str(adb), *args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(Path(adb).parent),
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError as exc:
        raise AdbError(f"No se pudo ejecutar adb: {adb}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AdbError(f"Tiempo agotado al ejecutar: {' '.join(command)}") from exc
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise AdbError(detail or f"adb falló con código {completed.returncode}")
    return completed


def parse_devices(output: str) -> list[AdbDevice]:
    devices: list[AdbDevice] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        if line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state, *rest = parts
        extras = " ".join(rest)
        model_match = re.search(r"model:([^\s]+)", extras)
        model = model_match.group(1).replace("_", " ") if model_match else ""
        devices.append(AdbDevice(serial=serial, state=state, model=model, details=extras))
    return devices


def start_server(adb: Path) -> None:
    _run(adb, ["start-server"], timeout=20, check=False)


def list_devices(adb: Path) -> list[AdbDevice]:
    start_server(adb)
    completed = _run(adb, ["devices", "-l"], timeout=20)
    return parse_devices(completed.stdout)


def describe_device_state(devices: list[AdbDevice]) -> str:
    if not devices:
        return "Ningún dispositivo ADB. Activa la depuración USB y autoriza este equipo."
    unauthorized = [item for item in devices if item.state == "unauthorized"]
    offline = [item for item in devices if item.state == "offline"]
    ready = [item for item in devices if item.authorized]
    parts: list[str] = []
    if ready:
        parts.append(", ".join(item.label for item in ready))
    if unauthorized:
        parts.append(
            "No autorizado: "
            + ", ".join(item.serial for item in unauthorized)
            + ". Desbloquea el teléfono y acepta la huella RSA."
        )
    if offline:
        parts.append("Offline: " + ", ".join(item.serial for item in offline) + ".")
    return " ".join(parts)


def _serial_args(device: AdbDevice) -> list[str]:
    return ["-s", device.serial]


def shell(adb: Path, device: AdbDevice, command: str, timeout: int = 40) -> str:
    completed = _run(adb, [*_serial_args(device), "shell", command], timeout=timeout, check=False)
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise AdbError(output.strip() or f"Falló: adb shell {command}")
    return completed.stdout


def package_apk_path(adb: Path, device: AdbDevice) -> str:
    try:
        output = shell(adb, device, f"pm path {PACKAGE_NAME}", timeout=30)
    except AdbError as exc:
        raise AdbError(
            f"No está instalado {PACKAGE_NAME} en el teléfono. Instala Need for Speed "
            f"Most Wanted 1.3.128 desde tu copia legal."
        ) from exc
    paths: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            paths.append(line.split("package:", 1)[1].strip())
    if not paths:
        raise AdbError(
            f"pm path no devolvió el APK de {PACKAGE_NAME}. ¿El juego está instalado?"
        )
    for candidate in paths:
        if candidate.endswith("base.apk") or candidate.endswith(".apk"):
            return candidate
    return paths[0]


def package_version(adb: Path, device: AdbDevice) -> tuple[str, str]:
    dump = ""
    last_error = ""
    for command in (
        f"dumpsys package {PACKAGE_NAME}",
        f"pm dump {PACKAGE_NAME}",
    ):
        try:
            dump = shell(adb, device, command, timeout=60)
            break
        except AdbError as exc:
            last_error = str(exc)
            continue
    if not dump:
        raise AdbError(
            f"No se pudo leer la versión del paquete con pm/dumpsys. {last_error}".strip()
        )
    block = dump
    marker = f"Package [{PACKAGE_NAME}]"
    if marker in dump:
        start = dump.index(marker)
        nxt = dump.find("\n  Package [", start + len(marker))
        block = dump[start:] if nxt < 0 else dump[start:nxt]
    name_match = re.search(r"versionName=([^\s]+)", block)
    code_match = re.search(r"versionCode=(\d+)", block)
    version_name = name_match.group(1) if name_match else ""
    version_code = code_match.group(1) if code_match else ""
    if version_name != VERSION_NAME:
        found = version_name or "desconocida"
        raise AdbError(
            f"Se encontró la versión {found}, pero este port requiere {VERSION_NAME} "
            f"(versionCode {VERSION_CODE})."
        )
    if version_code and version_code != VERSION_CODE:
        raise AdbError(
            f"versionCode {version_code} incompatible. Se requiere {VERSION_CODE}."
        )
    return version_name, version_code or VERSION_CODE


def _looks_like_permission_denied(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "permission denied",
            "denied",
            "inaccessible",
            "not found",
            "no such file",
            "failed to stat",
            "security exception",
        )
    )


def find_obb_remote(adb: Path, device: AdbDevice) -> str:
    errors: list[str] = []
    for remote in OBB_CANDIDATE_PATHS:
        try:
            listing = shell(adb, device, f'ls -l "{remote}"', timeout=20)
        except AdbError as exc:
            errors.append(str(exc))
            if _looks_like_permission_denied(str(exc)):
                continue
            continue
        if _looks_like_permission_denied(listing):
            errors.append(listing.strip())
            continue
        if OBB_FILENAME in listing or "main." in listing or listing.strip():
            if "no such file" in listing.lower():
                continue
            return remote
    try:
        folder = shell(
            adb,
            device,
            f'ls -l "/sdcard/Android/obb/{PACKAGE_NAME}/"',
            timeout=20,
        )
        if OBB_FILENAME in folder:
            return f"/sdcard/Android/obb/{PACKAGE_NAME}/{OBB_FILENAME}"
        errors.append(folder.strip())
    except AdbError as exc:
        errors.append(str(exc))

    joined = "\n".join(item for item in errors if item)
    raise ObbAccessError(
        "Android no permitió leer el OBB por ADB (típico en Android 11+ con almacenamiento "
        "con ámbito). El importador no modifica el teléfono.\n\n"
        "Copia estos archivos al PC con el explorador de archivos USB y usa "
        "«Seleccionar archivos locales»:\n"
        f"  • APK de {PACKAGE_NAME}\n"
        f"  • {OBB_FILENAME}\n\n"
        f"Detalle ADB:\n{joined[:1500]}"
    )


def pull_file(
    adb: Path,
    device: AdbDevice,
    remote: str,
    local: Path,
    timeout: int = 3600,
    on_output: Callable[[str], None] | None = None,
    cancel_flag: Callable[[], bool] | None = None,
) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    command = [str(adb), "-s", device.serial, "pull", remote, str(local)]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(adb).parent),
        creationflags=CREATE_NO_WINDOW,
    )
    assert process.stdout is not None
    try:
        leftover = ""
        while True:
            if cancel_flag and cancel_flag():
                process.kill()
                raise AdbError("Transferencia ADB cancelada.")
            chunk = process.stdout.read(256)
            if not chunk:
                break
            leftover += chunk.replace("\r", "\n")
            while "\n" in leftover:
                line, leftover = leftover.split("\n", 1)
                if on_output and line.strip():
                    on_output(line.strip())
        if leftover.strip() and on_output:
            on_output(leftover.strip())
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        raise AdbError(f"Tiempo agotado al copiar {remote}.") from exc
    if code != 0 or not local.is_file() or local.stat().st_size == 0:
        raise AdbError(f"No se pudo copiar {remote} al PC.")


def inspect_phone(adb: Path, device: AdbDevice) -> PhonePackage:
    if device.state == "unauthorized":
        raise AdbError(
            "El teléfono está unauthorized. Desbloquéalo y acepta el diálogo "
            "«¿Permitir depuración USB?»."
        )
    if device.state == "offline":
        raise AdbError("El dispositivo está offline. Reconecta el cable USB y vuelve a detectar.")
    if not device.authorized:
        raise AdbError(f"Estado ADB no usable: {device.state}.")
    apk_remote = package_apk_path(adb, device)
    version_name, version_code = package_version(adb, device)
    obb_remote = find_obb_remote(adb, device)
    return PhonePackage(
        apk_remote=apk_remote,
        obb_remote=obb_remote,
        version_name=version_name,
        version_code=version_code,
        device=device,
    )
