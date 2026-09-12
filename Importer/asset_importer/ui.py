from __future__ import annotations

import os
import subprocess
import traceback
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QTextCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .nfs_chrome import (
    NfsActionButton,
    NfsHeader,
    NfsInfoRow,
    NfsOptionRow,
    NfsProgressBar,
    fit_nfs_window,
    install_nfs_fonts,
    make_nfs_page_scroll,
    make_section_label,
    make_wrapping_label,
    nfs_chrome_stylesheet,
    paint_nfs_body,
)

from .adb import AdbDevice
from .constants import APP_TITLE, GAME_TITLE, OBB_FILENAME, PACKAGE_NAME, VERSION_NAME
from .paths import (
    ProjectPaths,
    relocate_game_package,
    save_game_root,
    suggested_game_roots,
)
from .pipeline import ImportCancelled, ImportResult, Pipeline, PipelineError, open_game_folder


class Worker(QThread):
    progress = pyqtSignal(int, str)
    log_line = pyqtSignal(str)
    device_text = pyqtSignal(str)
    version_text = pyqtSignal(str)
    stage_text = pyqtSignal(str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    devices_ready = pyqtSignal(object)

    def __init__(self, project: ProjectPaths, action: str, **kwargs: object) -> None:
        super().__init__()
        self.project = project
        self.action = action
        self.kwargs = kwargs
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def _pipeline(self) -> Pipeline:
        return Pipeline(
            self.project,
            log=self.log_line.emit,
            progress=lambda pct, msg: self.progress.emit(int(pct), msg),
            set_device=self.device_text.emit,
            set_version=self.version_text.emit,
            set_stage=self.stage_text.emit,
            cancelled=lambda: self._cancel,
        )

    def run(self) -> None:
        try:
            pipeline = self._pipeline()
            if self.action == "detect":
                devices = pipeline.detect_devices()
                self.devices_ready.emit(devices)
                return
            if self.action == "phone":
                device = self.kwargs["device"]
                assert isinstance(device, AdbDevice)
                result = pipeline.import_from_phone(device)
                self.succeeded.emit(result)
                return
            if self.action == "local":
                apk = Path(str(self.kwargs["apk"]))
                obb = Path(str(self.kwargs["obb"]))
                result = pipeline.import_from_files(apk, obb, source_label="local")
                self.succeeded.emit(result)
                return
            if self.action == "build":
                self._run_build()
                return
            raise PipelineError(f"Acción desconocida: {self.action}")
        except ImportCancelled as exc:
            self.failed.emit(str(exc))
        except (PipelineError, OSError) as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit(traceback.format_exc())

    def _run_build(self) -> None:
        script = self.project.build_script
        if not script.is_file():
            raise PipelineError(f"No se encontró build.ps1 en {script}")
        self.stage_text.emit("Ejecutando build.ps1")
        self.progress.emit(5, "Compilando")
        self.log_line.emit(f"Lanzando {script}")
        creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            cwd=str(self.project.root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation,
        )
        assert process.stdout is not None
        for line in process.stdout:
            if self._cancel:
                process.kill()
                raise ImportCancelled("Compilación cancelada.")
            text = line.rstrip()
            if text:
                self.log_line.emit(text)
        code = process.wait()
        if code != 0:
            raise PipelineError(f"build.ps1 terminó con código {code}.")
        result = ImportResult(
            assets_ok=True,
            play_ready=True,
            message="build.ps1 terminó correctamente.",
        )
        self.progress.emit(100, "Compilación lista")
        self.succeeded.emit(result)


class ImporterWindow(QWidget):
    def __init__(self, project: ProjectPaths) -> None:
        super().__init__()
        self.project = project
        self.worker: Worker | None = None
        self.devices: list[AdbDevice] = []
        self.setObjectName("importer")
        self.setWindowTitle(APP_TITLE)
        self.setStyleSheet("QWidget#importer { background: #3A4A52; }" + nfs_chrome_stylesheet())
        install_nfs_fonts(self.project.fonts)
        self._build_ui()
        fit_nfs_window(self, 560, 780, min_width=400, min_height=420)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        paint_nfs_body(self, painter)

    def _build_ui(self) -> None:
        self.header = NfsHeader("IMPORTADOR", "NEED FOR SPEED  MOST WANTED")

        status_section = make_section_label("ESTADO")
        self.device_value = NfsInfoRow("Dispositivo")
        self.device_value.setText("Sin detectar")
        self.version_value = NfsInfoRow("Versión")
        self.version_value.setText("—")
        self.stage_value = NfsInfoRow("Etapa")
        self.stage_value.setText("En espera")
        self.result_value = NfsInfoRow("Resultado")
        self.result_value.setText("Aún no se ha importado nada.")

        self.device_row = NfsOptionRow("Elegir dispositivo")
        self.device_row.setVisible(False)

        dest_section = make_section_label("CARPETA DEL JUEGO")
        self.dest_info = NfsInfoRow("Destino")
        self.dest_info.setText("")
        self.browse_button = NfsActionButton("ELEGIR CARPETA", compact=True)
        self.browse_button.clicked.connect(self.browse_game_folder)
        self.move_button = NfsActionButton("MOVER ACTUAL AQUÍ", compact=True)
        self.move_button.clicked.connect(self.move_game_folder)
        dest_btns = QHBoxLayout()
        dest_btns.setContentsMargins(0, 0, 0, 0)
        dest_btns.setSpacing(8)
        dest_btns.addWidget(self.browse_button)
        dest_btns.addWidget(self.move_button)

        self.progress = NfsProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.log = QTextEdit()
        self.log.setObjectName("nfsLog")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(72)
        self.log.setPlaceholderText("El detalle de ADB, validación e instalación aparece aquí.")

        hint = make_wrapping_label(
            "Activa Depuración USB, autoriza este PC y ten instalado "
            f"{GAME_TITLE} {VERSION_NAME} ({PACKAGE_NAME}). "
            "Si Android 11+ bloquea el OBB, selecciona el APK y el OBB copiados al PC. "
            "Usa únicamente tu copia legal.",
            "hint",
        )

        self.detect_button = NfsActionButton("DETECTAR TELÉFONO", compact=True)
        self.detect_button.clicked.connect(self.detect_phone)
        self.phone_button = NfsActionButton("IMPORTAR DESDE TELÉFONO")
        self.phone_button.clicked.connect(self.import_from_phone)
        self.local_button = NfsActionButton("ARCHIVOS LOCALES")
        self.local_button.clicked.connect(self.import_local)
        self.folder_button = NfsActionButton("ABRIR CARPETA", compact=True)
        self.folder_button.clicked.connect(self.open_folder)
        self.build_button = NfsActionButton("EJECUTAR BUILD.PS1", compact=True)
        self.build_button.setEnabled(self.project.build_script.is_file())
        self.build_button.clicked.connect(self.run_build)
        self.cancel_button = NfsActionButton("CANCELAR", compact=True)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_worker)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(self.detect_button)
        row1.addWidget(self.phone_button, 1)
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(self.local_button, 1)
        row2.addWidget(self.folder_button)
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        row3.addWidget(self.build_button)
        row3.addWidget(self.cancel_button)
        actions = QVBoxLayout()
        actions.setContentsMargins(24, 0, 24, 14)
        actions.setSpacing(8)
        actions.addLayout(row1)
        actions.addLayout(row2)
        actions.addLayout(row3)

        scroll, body = make_nfs_page_scroll()
        content = QVBoxLayout(body)
        content.setContentsMargins(24, 12, 24, 14)
        content.setSpacing(0)
        content.addWidget(status_section)
        content.addSpacing(8)
        content.addWidget(self.device_value)
        content.addSpacing(6)
        content.addWidget(self.device_row)
        content.addSpacing(6)
        content.addWidget(self.version_value)
        content.addSpacing(6)
        content.addWidget(self.stage_value)
        content.addSpacing(6)
        content.addWidget(self.result_value)
        content.addSpacing(12)
        content.addWidget(dest_section)
        content.addSpacing(8)
        content.addWidget(self.dest_info)
        content.addSpacing(8)
        content.addLayout(dest_btns)
        content.addSpacing(10)
        content.addWidget(self.progress)
        content.addSpacing(8)
        content.addWidget(self.log, 1)
        content.addSpacing(8)
        content.addWidget(hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(scroll, 1)
        layout.addLayout(actions)

    def append_log(self, message: str) -> None:
        self.log.append(message)
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def set_busy(self, busy: bool) -> None:
        for button in (
            self.detect_button,
            self.phone_button,
            self.local_button,
            self.folder_button,
            self.build_button,
            self.browse_button,
            self.move_button,
        ):
            button.setEnabled(not busy)
        if not busy:
            self.build_button.setEnabled(self.project.build_script.is_file())
        self.cancel_button.setEnabled(busy)
        self.device_row.setEnabled(not busy)

    def start_worker(self, action: str, **kwargs: object) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.set_busy(True)
        self.progress.setValue(0)
        worker = Worker(self.project, action, **kwargs)
        worker.progress.connect(self._on_progress)
        worker.log_line.connect(self.append_log)
        worker.device_text.connect(self.device_value.setText)
        worker.version_text.connect(self.version_value.setText)
        worker.stage_text.connect(self.stage_value.setText)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_fail)
        worker.devices_ready.connect(self._on_devices)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        worker.start()

    def _on_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(max(0, min(100, percent)))
        if message:
            self.stage_value.setText(message)

    def _set_result(self, text: str, tone: str) -> None:
        self.result_value.set_tone(tone)
        self.result_value.setText(text)

    def _on_devices(self, devices: object) -> None:
        assert isinstance(devices, list)
        self.devices = devices
        ready = [item for item in devices if item.authorized]
        if len(ready) > 1:
            self.device_row.set_items([(item.label, item.serial) for item in ready])
            self.device_row.setVisible(True)
            self.append_log("Hay varios dispositivos autorizados. Elige uno antes de importar.")
        else:
            self.device_row.setVisible(False)
        if not devices:
            self._set_result("Ningún dispositivo ADB detectado.", "warn")
        elif ready:
            self._set_result(f"{len(ready)} dispositivo(s) listo(s) para importar.", "ok")
        else:
            self._set_result("Hay un teléfono, pero no está autorizado o está offline.", "warn")

    def _on_success(self, result: object) -> None:
        assert isinstance(result, ImportResult)
        self.progress.setValue(100)
        self._set_result(result.message, "ok" if result.play_ready else "warn")
        self.stage_value.setText("Completado")
        if result.version:
            self.version_value.setText(result.version)
        if result.device:
            self.device_value.setText(result.device)

    def _on_fail(self, message: str) -> None:
        self._set_result(message.splitlines()[0][:300], "err")
        self.stage_value.setText("Error")
        self.append_log(message)
        QMessageBox.critical(self, APP_TITLE, message[:2000])

    def _on_worker_finished(self) -> None:
        self.set_busy(False)
        self.worker = None

    def selected_device(self) -> AdbDevice | None:
        ready = [item for item in self.devices if item.authorized]
        if not ready:
            return None
        if len(ready) == 1:
            return ready[0]
        serial = str(self.device_row.current_data() or "")
        for item in ready:
            if item.serial == serial:
                return item
        return ready[0]

    def _short_path(self, path: Path) -> str:
        path = path.resolve()
        parts = path.parts
        if len(parts) <= 3:
            return str(path)
        return "…\\" + str(Path(*parts[-2:]))

    def _show_dest_path(self, path: Path) -> None:
        resolved = path.resolve()
        self.dest_info.setText(self._short_path(resolved))
        self.dest_info.setToolTip(str(resolved))

    def _apply_game_root(self, path: Path, persist: bool = True) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.project.set_game_root(path)
        if persist:
            save_game_root(self.project.root, path)
        self._show_dest_path(self.project.native_prototype)
        self.append_log(f"Carpeta del juego: {self.project.native_prototype}")

    def browse_game_folder(self) -> None:
        start = self.project.native_prototype
        if not start.is_dir():
            start = self.project.root
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Carpeta donde guardar .so, fuentes y OBB",
            str(start),
        )
        if not chosen:
            return
        self._apply_game_root(Path(chosen))

    def move_game_folder(self) -> None:
        dest = self.project.native_prototype
        sources: list[Path] = []
        seen: set[Path] = set()
        for path in (
            self.project.root / "native_prototype",
            *(item for _label, item in suggested_game_roots(self.project.root)),
        ):
            resolved = path.resolve()
            if resolved in seen or resolved == dest.resolve() or not path.is_dir():
                continue
            seen.add(resolved)
            if (
                (path / "libapp.so").is_file()
                or (path / "game_data").is_dir()
                or (path / "nfsmwa_runtime.exe").is_file()
            ):
                sources.append(path)
        previous = sources[0] if sources else None
        if previous is None:
            QMessageBox.information(
                self,
                APP_TITLE,
                "No hay una carpeta anterior con recursos para mover. "
                "Elige destino e importa el APK/OBB ahí.",
            )
            return
        answer = QMessageBox.question(
            self,
            APP_TITLE,
            "¿Mover el paquete actual a esta carpeta?\n\n"
            f"Desde:\n{previous}\n\nHacia:\n{dest}\n\n"
            "Mueve .so, OBB, fuentes y el motor si están. No duplica el OBB.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        dest.mkdir(parents=True, exist_ok=True)
        moved = relocate_game_package(previous, dest)
        save_game_root(self.project.root, dest)
        if moved:
            self.append_log("Movido: " + ", ".join(moved[:12]) + ("…" if len(moved) > 12 else ""))
        else:
            self.append_log("No había archivos que mover; el destino ya está listo para importar.")
        self._show_dest_path(dest)
        self._set_result(f"Carpeta del juego: {dest}", "ok")

    def detect_phone(self) -> None:
        self.append_log("Detectando teléfono…")
        self.start_worker("detect")

    def import_from_phone(self) -> None:
        if not self.devices:
            self.detect_phone()
            QMessageBox.information(
                self,
                APP_TITLE,
                "Primero se detectará el teléfono. Cuando aparezca autorizado, pulsa de nuevo "
                "«Importar desde teléfono».",
            )
            return
        ready = [item for item in self.devices if item.authorized]
        if not ready:
            QMessageBox.warning(
                self,
                APP_TITLE,
                "No hay un dispositivo autorizado. Activa la depuración USB y acepta el diálogo RSA.",
            )
            return
        device = self.selected_device()
        if device is None:
            return
        self.append_log(f"Importando desde {device.label}…")
        self.start_worker("phone", device=device)

    def import_local(self) -> None:
        apk, _ = QFileDialog.getOpenFileName(
            self,
            "Selecciona NeedForSpeedMostWanted.apk",
            str(self.project.root),
            "APK (*.apk);;Todos (*.*)",
        )
        if not apk:
            return
        obb, _ = QFileDialog.getOpenFileName(
            self,
            f"Selecciona {OBB_FILENAME}",
            str(Path(apk).parent),
            "OBB (*.obb);;Todos (*.*)",
        )
        if not obb:
            return
        self.append_log(f"APK local: {apk}")
        self.append_log(f"OBB local: {obb}")
        self.device_value.setText("Archivos locales")
        self.start_worker("local", apk=apk, obb=obb)

    def open_folder(self) -> None:
        try:
            open_game_folder(self.project)
        except (OSError, PipelineError) as exc:
            QMessageBox.warning(self, APP_TITLE, str(exc))

    def run_build(self) -> None:
        answer = QMessageBox.question(
            self,
            APP_TITLE,
            "La importación no necesita compilar. ¿Ejecutar build.ps1 ahora?\n"
            "Puede tardar varios minutos y requiere el entorno nativo.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.start_worker("build")

    def cancel_worker(self) -> None:
        if self.worker is not None:
            self.append_log("Cancelando…")
            self.worker.cancel()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1500)
        super().closeEvent(event)
