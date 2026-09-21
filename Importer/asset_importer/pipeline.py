from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import adb as adbmod
from .constants import APK_DISPLAY_NAME, OBB_FILENAME, PACKAGE_NAME, VERSION_NAME
from .installer import install_assets, runtime_status
from .i18n import t
from .paths import ProjectPaths, find_adb
from .validation import ValidationError, validate_pair
from .zip_safe import ZipSafetyError


class ImportCancelled(RuntimeError):
    pass


class PipelineError(RuntimeError):
    pass


ProgressCb = Callable[[int, str], None]
LogCb = Callable[[str], None]


@dataclass
class ImportResult:
    assets_ok: bool
    play_ready: bool
    message: str
    device: str = ""
    version: str = ""
    backup: str = ""
    missing_runtime: tuple[str, ...] = ()
    manifest_path: str = ""


class Pipeline:
    def __init__(
        self,
        project: ProjectPaths,
        log: LogCb | None = None,
        progress: ProgressCb | None = None,
        set_device: LogCb | None = None,
        set_version: LogCb | None = None,
        set_stage: LogCb | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self.project = project
        self._log = log or (lambda _msg: None)
        self._progress = progress or (lambda _pct, _msg: None)
        self._set_device = set_device or (lambda _msg: None)
        self._set_version = set_version or (lambda _msg: None)
        self._set_stage = set_stage or (lambda _msg: None)
        self._cancelled = cancelled or (lambda: False)

    def check_cancel(self) -> None:
        if self._cancelled():
            raise ImportCancelled(t("Operación cancelada.", "Operation cancelled."))

    def log(self, message: str) -> None:
        self._log(message)

    def stage(self, name: str, percent: int | None = None) -> None:
        self.check_cancel()
        self._set_stage(name)
        if percent is not None:
            self._progress(percent, name)
        self.log(name)

    def locate_adb(self) -> Path:
        path = find_adb(self.project)
        if path is None:
            raise PipelineError(
                t(
                    "No se encontró adb.exe. Colócalo junto al importador, en "
                    "platform-tools del proyecto, o en el PATH. Este programa no descarga "
                    "Platform Tools automáticamente.",
                    "Could not find adb.exe. Place it next to the importer, in the project's "
                    "platform-tools folder, or in PATH. This program does not download "
                    "Platform Tools automatically.",
                )
            )
        self.log(t("ADB disponible.", "ADB available."))
        return path

    def detect_devices(self) -> list[adbmod.AdbDevice]:
        adb = self.locate_adb()
        self.stage(t("Detectando dispositivos ADB", "Detecting ADB devices"), 5)
        devices = adbmod.list_devices(adb)
        summary = adbmod.describe_device_state(devices)
        self._set_device(summary or t("Ningún dispositivo", "No device"))
        self.log(summary)
        return devices

    def import_from_files(self, apk: Path, obb: Path, source_label: str = "local") -> ImportResult:
        apk = Path(apk)
        obb = Path(obb)
        self.stage(t("Validando APK y OBB", "Validating APK and OBB"), 10)
        try:
            report = validate_pair(apk, obb)
        except (ValidationError, ZipSafetyError) as exc:
            raise PipelineError(str(exc)) from exc
        self._set_version(f"{report.version_name} (versionCode {report.version_code})")
        self.log(
            t(
                f"Paquete {report.package} {report.version_name} confirmado. "
                "El OBB incluye published.1x y published.2x.",
                f"Package {report.package} {report.version_name} verified. "
                "The OBB includes published.1x and published.2x.",
            )
        )
        self.stage(t("Instalando recursos validados", "Installing validated assets"), 40)

        def on_stage(name: str) -> None:
            self.stage(name)

        def on_progress(done: int, total: int, label: str) -> None:
            self.check_cancel()
            pct = 40 + int((done / max(total, 1)) * 50)
            self._progress(min(pct, 92), f"{label} ({done}/{total})")

        payload = install_assets(
            report,
            self.project,
            source_label=source_label,
            check_cancel=self.check_cancel,
            on_stage=on_stage,
            on_progress=on_progress,
        )
        return self._finish(payload, device_text="")

    def import_from_phone(self, device: adbmod.AdbDevice) -> ImportResult:
        adb = self.locate_adb()
        self._set_device(device.label)
        self.stage(t("Consultando paquete instalado", "Checking installed package"), 8)
        try:
            info = adbmod.inspect_phone(adb, device)
        except adbmod.ObbAccessError as exc:
            raise PipelineError(str(exc)) from exc
        except adbmod.AdbError as exc:
            raise PipelineError(str(exc)) from exc
        self._set_version(f"{info.version_name} (versionCode {info.version_code})")
        self.log(t(f"APK remoto: {info.apk_remote}", f"Remote APK: {info.apk_remote}"))
        self.log(t(f"OBB remoto: {info.obb_remote}", f"Remote OBB: {info.obb_remote}"))

        with tempfile.TemporaryDirectory(prefix="nfsmw_adb_") as raw:
            tmp = Path(raw)
            local_apk = tmp / APK_DISPLAY_NAME
            local_obb = tmp / OBB_FILENAME
            self.stage(t(
                "Copiando APK desde el teléfono (solo lectura)",
                "Copying APK from phone (read-only)",
            ), 15)
            try:
                adbmod.pull_file(
                    adb,
                    device,
                    info.apk_remote,
                    local_apk,
                    on_output=self.log,
                    cancel_flag=self._cancelled,
                )
                self.stage(t(
                    "Copiando OBB intacto desde el teléfono (solo lectura)",
                    "Copying intact OBB from phone (read-only)",
                ), 28)
                adbmod.pull_file(
                    adb,
                    device,
                    info.obb_remote,
                    local_obb,
                    on_output=self.log,
                    cancel_flag=self._cancelled,
                )
            except adbmod.AdbError as exc:
                message = str(exc)
                if adbmod._looks_like_permission_denied(message):
                    raise PipelineError(
                        t(
                            "Android bloqueó la copia del OBB. Usa «Seleccionar archivos locales» "
                            f"con {APK_DISPLAY_NAME} y {OBB_FILENAME}.",
                            "Android blocked the OBB copy. Use “Select local files” with "
                            f"{APK_DISPLAY_NAME} and {OBB_FILENAME}.",
                        )
                    ) from exc
                raise PipelineError(message) from exc
            # Persist the import method, never the private ADB identifier.
            result = self.import_from_files(local_apk, local_obb, source_label="adb")
            result.device = device.label
            result.version = f"{info.version_name} (versionCode {info.version_code})"
            return result

    def _finish(self, payload: dict[str, object], device_text: str) -> ImportResult:
        present, missing = runtime_status(self.project)
        assets_ok = True
        play_ready = not missing
        if play_ready:
            message = t("Paquete completo listo para jugar.", "Complete package ready to play.")
        else:
            missing_list = ", ".join(missing)
            message = t(
                "Recursos originales importados correctamente. "
                f"Aún falta para jugar: {missing_list}. "
                "Puedes ejecutar build.ps1 si tienes el entorno de compilación.",
                "Original assets imported successfully. "
                f"Still required to play: {missing_list}. "
                "You can run build.ps1 if you have the build environment.",
            )
        self.stage(message, 100)
        self.log(t("Manifiesto actualizado.", "Manifest updated."))
        if payload.get("backup"):
            self.log(t("Respaldo local creado.", "Local backup created."))
        return ImportResult(
            assets_ok=assets_ok,
            play_ready=play_ready,
            message=message,
            device=device_text,
            version=f"{payload.get('version_name', VERSION_NAME)}",
            backup=str(payload.get("backup", "")),
            missing_runtime=tuple(missing),
            manifest_path=str(self.project.manifest),
        )


def open_game_folder(project: ProjectPaths) -> None:
    folder = project.native_prototype
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(folder))  # type: ignore[attr-defined]
        return
    raise PipelineError(t(
        f"Abre manualmente la carpeta del juego: {folder}",
        f"Open the game folder manually: {folder}",
    ))
