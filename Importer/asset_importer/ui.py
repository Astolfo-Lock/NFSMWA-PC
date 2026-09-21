from __future__ import annotations

import os
import subprocess
import traceback
from pathlib import Path

from PyQt6.QtCore import QSettings, QThread, pyqtSignal
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
from .i18n import get_language, set_language, t, translate_message
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
        self.language = get_language()

    def cancel(self) -> None:
        self._cancel = True

    def _pipeline(self) -> Pipeline:
        return Pipeline(
            self.project,
            log=lambda msg: self.log_line.emit(translate_message(msg, self.language)),
            progress=lambda pct, msg: self.progress.emit(
                int(pct), translate_message(msg, self.language)
            ),
            set_device=lambda msg: self.device_text.emit(translate_message(msg, self.language)),
            set_version=self.version_text.emit,
            set_stage=lambda msg: self.stage_text.emit(translate_message(msg, self.language)),
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
            raise PipelineError(t(f"Acción desconocida: {self.action}", f"Unknown action: {self.action}"))
        except ImportCancelled as exc:
            self.failed.emit(translate_message(str(exc), self.language))
        except (PipelineError, OSError) as exc:
            self.failed.emit(translate_message(str(exc), self.language))
        except Exception:
            self.failed.emit(traceback.format_exc())

    def _run_build(self) -> None:
        script = self.project.build_script
        if not script.is_file():
            raise PipelineError(t(f"No se encontró build.ps1 en {script}", f"Could not find build.ps1 at {script}"))
        self.stage_text.emit(t("Ejecutando build.ps1", "Running build.ps1"))
        self.progress.emit(5, t("Compilando", "Building"))
        self.log_line.emit(t(f"Lanzando {script}", f"Launching {script}"))
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
                raise ImportCancelled(t("Compilación cancelada.", "Build cancelled."))
            text = line.rstrip()
            if text:
                self.log_line.emit(text)
        code = process.wait()
        if code != 0:
            raise PipelineError(t(
                f"build.ps1 terminó con código {code}.",
                f"build.ps1 finished with code {code}.",
            ))
        result = ImportResult(
            assets_ok=True,
            play_ready=True,
            message=t("build.ps1 terminó correctamente.", "build.ps1 finished successfully."),
        )
        self.progress.emit(100, t("Compilación lista", "Build complete"))
        self.succeeded.emit(result)


class ImporterWindow(QWidget):
    def __init__(self, project: ProjectPaths) -> None:
        super().__init__()
        self.project = project
        self.worker: Worker | None = None
        self.devices: list[AdbDevice] = []
        self.app_settings = QSettings("NFSMWA-PC", "Asset Importer")
        saved_language = str(self.app_settings.value("language", "es"))
        set_language(saved_language)
        self.setObjectName("importer")
        self.setWindowTitle(APP_TITLE)
        self.setStyleSheet("QWidget#importer { background: #3A4A52; }" + nfs_chrome_stylesheet())
        install_nfs_fonts(self.project.fonts)
        self._build_ui()
        fit_nfs_window(self, 560, 850, min_width=400, min_height=420)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        paint_nfs_body(self, painter)

    def _build_ui(self) -> None:
        self.header = NfsHeader("IMPORTADOR", "NEED FOR SPEED  MOST WANTED")

        self.language_row = NfsOptionRow("Idioma")
        self.language_row.set_items([("ESPAÑOL", "es"), ("ENGLISH", "en")])
        self.language_row.set_current_data(get_language())
        self.language_row.valueChanged.connect(self.language_changed)

        self.status_section = make_section_label("ESTADO")
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

        self.dest_section = make_section_label("CARPETA DEL JUEGO")
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

        self.hint = make_wrapping_label(
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
        content.addWidget(self.language_row)
        content.addSpacing(12)
        content.addWidget(self.status_section)
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
        content.addWidget(self.dest_section)
        content.addSpacing(8)
        content.addWidget(self.dest_info)
        content.addSpacing(8)
        content.addLayout(dest_btns)
        content.addSpacing(10)
        content.addWidget(self.progress)
        content.addSpacing(8)
        content.addWidget(self.log, 1)
        content.addSpacing(8)
        content.addWidget(self.hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(scroll, 1)
        layout.addLayout(actions)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.header.set_text(t("IMPORTADOR", "IMPORTER"), "NEED FOR SPEED  MOST WANTED")
        self.language_row.set_label(t("Idioma", "Language"))
        self.status_section.setText(t("ESTADO", "STATUS"))
        self.device_value.set_label(t("Dispositivo", "Device"))
        self.version_value.set_label(t("Versión", "Version"))
        self.stage_value.set_label(t("Etapa", "Stage"))
        self.result_value.set_label(t("Resultado", "Result"))
        self.device_row.set_label(t("Elegir dispositivo", "Choose device"))
        self.dest_section.setText(t("CARPETA DEL JUEGO", "GAME FOLDER"))
        self.dest_info.set_label(t("Destino", "Destination"))
        self.browse_button.setText(t("ELEGIR CARPETA", "CHOOSE FOLDER"))
        self.move_button.setText(t("MOVER ACTUAL AQUÍ", "MOVE CURRENT HERE"))
        self.log.setPlaceholderText(t(
            "El detalle de ADB, validación e instalación aparece aquí.",
            "ADB, validation, and installation details appear here.",
        ))
        self.hint.setText(t(
            "Activa Depuración USB, autoriza este PC y ten instalado "
            f"{GAME_TITLE} {VERSION_NAME} ({PACKAGE_NAME}). "
            "Si Android 11+ bloquea el OBB, selecciona el APK y el OBB copiados al PC. "
            "Usa únicamente tu copia legal.",
            "Enable USB debugging, authorize this PC, and make sure "
            f"{GAME_TITLE} {VERSION_NAME} ({PACKAGE_NAME}) is installed. "
            "If Android 11+ blocks the OBB, select the APK and OBB copied to the PC. "
            "Only use your legally owned copy.",
        ))
        self.detect_button.setText(t("DETECTAR TELÉFONO", "DETECT PHONE"))
        self.phone_button.setText(t("IMPORTAR DESDE TELÉFONO", "IMPORT FROM PHONE"))
        self.local_button.setText(t("ARCHIVOS LOCALES", "LOCAL FILES"))
        self.folder_button.setText(t("ABRIR CARPETA", "OPEN FOLDER"))
        self.build_button.setText(t("EJECUTAR BUILD.PS1", "RUN BUILD.PS1"))
        self.cancel_button.setText(t("CANCELAR", "CANCEL"))
        for row in (self.device_value, self.stage_value, self.result_value):
            row.setText(translate_message(row.text()))

    def language_changed(self) -> None:
        language = str(self.language_row.current_data() or "es")
        set_language(language)
        self.app_settings.setValue("language", language)
        self.retranslate_ui()

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
            self.language_row,
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
            # Keep the private ADB serial out of the visible widget data.
            self.device_row.set_items([(item.label, index) for index, item in enumerate(ready)])
            self.device_row.setVisible(True)
            self.append_log(t(
                "Hay varios dispositivos autorizados. Elige uno antes de importar.",
                "Several authorized devices were found. Choose one before importing.",
            ))
        else:
            self.device_row.setVisible(False)
        if not devices:
            self._set_result(t("Ningún dispositivo ADB detectado.", "No ADB device detected."), "warn")
        elif ready:
            self._set_result(t(
                f"{len(ready)} dispositivo(s) listo(s) para importar.",
                f"{len(ready)} device(s) ready to import.",
            ), "ok")
        else:
            self._set_result(t(
                "Hay un teléfono, pero no está autorizado o está offline.",
                "A phone was found, but it is unauthorized or offline.",
            ), "warn")

    def _on_success(self, result: object) -> None:
        assert isinstance(result, ImportResult)
        self.progress.setValue(100)
        self._set_result(translate_message(result.message), "ok" if result.play_ready else "warn")
        self.stage_value.setText(t("Completado", "Completed"))
        if result.version:
            self.version_value.setText(result.version)
        if result.device:
            self.device_value.setText(result.device)

    def _on_fail(self, message: str) -> None:
        self._set_result(message.splitlines()[0][:300], "err")
        self.stage_value.setText(t("Error", "Error"))
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
        index = int(self.device_row.current_data() or 0)
        if 0 <= index < len(ready):
            return ready[index]
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
        self.append_log(t(
            f"Carpeta del juego: {self.project.native_prototype}",
            f"Game folder: {self.project.native_prototype}",
        ))

    def browse_game_folder(self) -> None:
        start = self.project.native_prototype
        if not start.is_dir():
            start = self.project.root
        chosen = QFileDialog.getExistingDirectory(
            self,
            t(
                "Carpeta donde guardar .so, fuentes y OBB",
                "Folder where .so files, fonts, and OBB will be stored",
            ),
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
                t(
                    "No hay una carpeta anterior con recursos para mover. "
                    "Elige destino e importa el APK/OBB ahí.",
                    "There is no previous asset folder to move. "
                    "Choose a destination and import the APK/OBB there.",
                ),
            )
            return
        answer = QMessageBox.question(
            self,
            APP_TITLE,
            t(
                "¿Mover el paquete actual a esta carpeta?\n\n"
                f"Desde:\n{previous}\n\nHacia:\n{dest}\n\n"
                "Mueve .so, OBB, fuentes y el motor si están. No duplica el OBB.",
                "Move the current package to this folder?\n\n"
                f"From:\n{previous}\n\nTo:\n{dest}\n\n"
                "Moves .so files, the OBB, fonts, and the engine when present. It does not duplicate the OBB.",
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        dest.mkdir(parents=True, exist_ok=True)
        moved = relocate_game_package(previous, dest)
        save_game_root(self.project.root, dest)
        if moved:
            self.append_log(t("Movido: ", "Moved: ") + ", ".join(moved[:12]) + ("…" if len(moved) > 12 else ""))
        else:
            self.append_log(t(
                "No había archivos que mover; el destino ya está listo para importar.",
                "There were no files to move; the destination is ready for importing.",
            ))
        self._show_dest_path(dest)
        self._set_result(t(f"Carpeta del juego: {dest}", f"Game folder: {dest}"), "ok")

    def detect_phone(self) -> None:
        self.append_log(t("Detectando teléfono…", "Detecting phone…"))
        self.start_worker("detect")

    def import_from_phone(self) -> None:
        if not self.devices:
            self.detect_phone()
            QMessageBox.information(
                self,
                APP_TITLE,
                t(
                    "Primero se detectará el teléfono. Cuando aparezca autorizado, pulsa de nuevo "
                    "«Importar desde teléfono».",
                    "The phone will be detected first. Once it appears as authorized, press "
                    "“Import from phone” again.",
                ),
            )
            return
        ready = [item for item in self.devices if item.authorized]
        if not ready:
            QMessageBox.warning(
                self,
                APP_TITLE,
                t(
                    "No hay un dispositivo autorizado. Activa la depuración USB y acepta el diálogo RSA.",
                    "There is no authorized device. Enable USB debugging and accept the RSA prompt.",
                ),
            )
            return
        device = self.selected_device()
        if device is None:
            return
        self.append_log(t(f"Importando desde {device.label}…", f"Importing from {device.label}…"))
        self.start_worker("phone", device=device)

    def import_local(self) -> None:
        apk, _ = QFileDialog.getOpenFileName(
            self,
            t("Selecciona NeedForSpeedMostWanted.apk", "Select NeedForSpeedMostWanted.apk"),
            str(self.project.root),
            t("APK (*.apk);;Todos (*.*)", "APK (*.apk);;All files (*.*)"),
        )
        if not apk:
            return
        obb, _ = QFileDialog.getOpenFileName(
            self,
            t(f"Selecciona {OBB_FILENAME}", f"Select {OBB_FILENAME}"),
            str(Path(apk).parent),
            t("OBB (*.obb);;Todos (*.*)", "OBB (*.obb);;All files (*.*)"),
        )
        if not obb:
            return
        self.append_log(f"APK local: {apk}")
        self.append_log(f"OBB local: {obb}")
        self.device_value.setText(t("Archivos locales", "Local files"))
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
            t(
                "La importación no necesita compilar. ¿Ejecutar build.ps1 ahora?\n"
                "Puede tardar varios minutos y requiere el entorno nativo.",
                "Importing does not require a build. Run build.ps1 now?\n"
                "It may take several minutes and requires the native build environment.",
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.start_worker("build")

    def cancel_worker(self) -> None:
        if self.worker is not None:
            self.append_log(t("Cancelando…", "Cancelling…"))
            self.worker.cancel()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1500)
        super().closeEvent(event)
