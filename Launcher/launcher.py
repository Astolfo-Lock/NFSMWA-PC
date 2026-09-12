from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from controller_config import ControllerSettingsDialog
from nfs_chrome import (
    NfsActionButton,
    NfsHeader,
    NfsOptionRow,
    fit_nfs_window,
    install_nfs_fonts,
    make_nfs_page_scroll,
    make_section_label,
    make_wrapping_label,
    nfs_chrome_stylesheet,
    paint_nfs_body,
)


APP_TITLE = "Need for Speed Most Wanted"
RUNTIME_NAME = "nfsmwa_runtime.exe"
CONFIG_NAME = "launcher_settings.json"
ENUM_CURRENT_SETTINGS = 0xFFFFFFFF


class PointL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class PrinterFields(ctypes.Structure):
    _fields_ = [
        ("dmOrientation", ctypes.c_short),
        ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short),
        ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short),
        ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short),
        ("dmPrintQuality", ctypes.c_short),
    ]


class DisplayFields(ctypes.Structure):
    _fields_ = [
        ("dmPosition", PointL),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
    ]


class ModeFields(ctypes.Union):
    _fields_ = [("printer", PrinterFields), ("display", DisplayFields)]


class DisplayFlags(ctypes.Union):
    _fields_ = [("dmDisplayFlags", wintypes.DWORD), ("dmNup", wintypes.DWORD)]


class DevModeW(ctypes.Structure):
    _anonymous_ = ("mode_fields", "display_flags")
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("mode_fields", ModeFields),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("display_flags", DisplayFlags),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


def _is_game_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    has_runtime = (path / RUNTIME_NAME).is_file()
    has_game_lib = (path / "libapp.so").is_file()
    if has_runtime and has_game_lib:
        return True
    return path.name.lower() == "native_prototype"


def _game_dir_candidates(current: Path) -> tuple[Path, ...]:
    return (
        current,
        current / "native_prototype",
        current / "Motor",
        current / "NFSMWA" / "Motor",
        current / "NFSMWA" / "native_prototype",
    )


def _saved_game_root() -> Path | None:
    starts: list[Path] = []
    if getattr(sys, "frozen", False):
        starts.append(Path(sys.executable).resolve().parent)
    else:
        starts.append(Path(__file__).resolve().parent)
    try:
        starts.append(Path.cwd().resolve())
    except OSError:
        pass
    seen: set[Path] = set()
    for start in starts:
        current = start
        for _ in range(8):
            if current in seen:
                break
            seen.add(current)
            config = current / "nfsmw_paths.json"
            if config.is_file():
                try:
                    data = json.loads(config.read_text(encoding="utf-8"))
                    raw = data.get("game_root") if isinstance(data, dict) else None
                except (OSError, json.JSONDecodeError, TypeError):
                    raw = None
                if raw:
                    path = Path(str(raw))
                    if not path.is_absolute():
                        path = current / path
                    if path.is_dir():
                        return path.resolve()
            current = current.parent
    return None


def bundle_root() -> Path:
    env = os.environ.get("NFSMW_GAME_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    saved = _saved_game_root()
    if saved is not None:
        return saved

    starts: list[Path] = []
    if getattr(sys, "frozen", False):
        starts.append(Path(sys.executable).resolve().parent)
    else:
        here = Path(__file__).resolve().parent
        starts.append(here)
        starts.append(here.parent)
    try:
        starts.append(Path.cwd().resolve())
    except OSError:
        pass

    seen: set[Path] = set()
    for start in starts:
        current = start
        for _ in range(8):
            if current in seen:
                break
            seen.add(current)
            for candidate in _game_dir_candidates(current):
                if _is_game_root(candidate):
                    return candidate
            current = current.parent

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    packaged = Path(__file__).resolve().parent / "native_prototype"
    return packaged if packaged.is_dir() else Path(__file__).resolve().parent


def set_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def windows_display_modes() -> tuple[list[tuple[int, int]], tuple[int, int]]:
    if os.name != "nt":
        return [(1280, 720), (1600, 900), (1920, 1080)], (1920, 1080)
    enum_modes = ctypes.windll.user32.EnumDisplaySettingsW
    enum_modes.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DevModeW)]
    enum_modes.restype = wintypes.BOOL

    current_mode = DevModeW()
    current_mode.dmSize = ctypes.sizeof(DevModeW)
    if enum_modes(None, ENUM_CURRENT_SETTINGS, ctypes.byref(current_mode)):
        current = (int(current_mode.dmPelsWidth), int(current_mode.dmPelsHeight))
    else:
        current = (1280, 720)

    found: set[tuple[int, int]] = set()
    index = 0
    while True:
        mode = DevModeW()
        mode.dmSize = ctypes.sizeof(DevModeW)
        if not enum_modes(None, index, ctypes.byref(mode)):
            break
        width, height = int(mode.dmPelsWidth), int(mode.dmPelsHeight)
        is_widescreen = height > 0 and abs(width / height - 16 / 9) < 0.035
        if mode.dmBitsPerPel >= 24 and width >= 1024 and height >= 576 and is_widescreen:
            found.add((width, height))
        index += 1

    if current[1] and abs(current[0] / current[1] - 16 / 9) < 0.035:
        found.add(current)
    if not found:
        found.add(current)
    return sorted(found, key=lambda size: (size[0] * size[1], size[0])), current


class LauncherWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.root = bundle_root()
        self.runtime = self.root / RUNTIME_NAME
        self.config_path = self.root / CONFIG_NAME
        self.exclusive_modes, self.desktop_resolution = windows_display_modes()
        extra_windowed_modes = {(960, 540), (1024, 576), (1280, 720), (1600, 900)}
        self.windowed_modes = sorted(
            set(self.exclusive_modes).union(
                resolution
                for resolution in extra_windowed_modes
                if resolution[0] <= self.desktop_resolution[0]
                and resolution[1] <= self.desktop_resolution[1]
            ),
            key=lambda size: (size[0] * size[1], size[0]),
        )
        self.process: subprocess.Popen[bytes] | None = None
        self.active_display_mode: str | None = None
        self.last_windowed_resolution = (1280, 720)
        self.last_fullscreen_resolution = self.desktop_resolution
        self.settings = self.load_settings()

        self.setObjectName("launcher")
        self.setWindowTitle(APP_TITLE)
        self.setStyleSheet("QWidget#launcher { background: #3A4A52; }" + nfs_chrome_stylesheet())

        install_nfs_fonts(self.root / "fonts")
        self.build_ui()
        self.restore_controls()
        fit_nfs_window(self, 540, 710, min_width=400, min_height=420)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        paint_nfs_body(self, painter)

    def build_ui(self) -> None:
        self.header = NfsHeader("CONFIGURACIÓN", "NEED FOR SPEED  MOST WANTED")

        section = make_section_label("GRÁFICOS")

        self.resolution_row = NfsOptionRow("Resolución")
        self.resolution_row.setToolTip("Tamaño de la imagen de salida.")

        self.mode_row = NfsOptionRow("Modo de pantalla")
        self.mode_row.set_items([
            ("Ventana", "windowed"),
            ("Pantalla completa sin bordes", "borderless"),
            ("Pantalla completa exclusiva", "fullscreen"),
        ])
        self.mode_row.valueChanged.connect(self.display_mode_changed)

        self.quality_row = NfsOptionRow("Calidad gráfica")
        self.quality_row.set_items([
            ("Compatible (estable)", "low", True),
            ("Alto (híbrido)", "hybrid", True),
            ("Alto (nativo)", "native", True),
        ])
        self.quality_row.setToolTip(
            "Híbrido mejora el filtrado de texturas sobre la ruta estable. Nativo activa "
            "el nivel 4 móvil original con la corrección de renderizado para Windows."
        )
        self.quality_row.valueChanged.connect(self.quality_changed)

        self.msaa_row = NfsOptionRow("Antialiasing")
        self.msaa_row.set_items([
            ("Desactivado", 0),
            ("MSAA 2x", 2),
            ("MSAA 4x", 4),
        ])
        self.msaa_row.setToolTip("Suaviza los bordes mediante multisampling real del framebuffer.")

        self.fps_row = NfsOptionRow("Límite de FPS")
        self.fps_row.set_items([
            ("30 FPS", 30),
            ("60 FPS", 60),
            ("60 menú / libre en carrera", 0),
        ])
        self.fps_row.setToolTip(
            "Mantiene la interfaz a 60 FPS para evitar fallos de desplazamiento y libera "
            "el límite durante la conducción. Con VSync activo, la frecuencia del monitor "
            "sigue siendo el límite superior de la carrera."
        )

        self.vsync_row = NfsOptionRow("Sincronización vertical")
        self.vsync_row.set_items([
            ("ACTIVADA", True),
            ("DESACTIVADA", False),
        ])
        self.vsync_row.setAccessibleName("Sincronización vertical")
        self.vsync_row.setToolTip("Evita cortes horizontales sincronizando cada imagen con el monitor.")

        self.hint = make_wrapping_label("", "hint")
        self.graphics_notice = make_wrapping_label("", "notice")
        self.status = make_wrapping_label("Opciones guardadas al jugar.", "status")
        self.controller_button = NfsActionButton("MANDO")
        self.controller_button.clicked.connect(self.open_controller_settings)
        self.play_button = NfsActionButton("JUGAR")
        self.play_button.clicked.connect(self.launch_game)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(24, 0, 24, 16)
        action_row.setSpacing(10)
        action_row.addWidget(self.controller_button)
        action_row.addWidget(self.play_button, 1)

        scroll, body = make_nfs_page_scroll()
        content = QVBoxLayout(body)
        content.setContentsMargins(24, 14, 24, 16)
        content.setSpacing(0)
        content.addWidget(section)
        content.addSpacing(10)
        for row in (
            self.resolution_row,
            self.mode_row,
            self.quality_row,
            self.msaa_row,
            self.fps_row,
            self.vsync_row,
        ):
            content.addWidget(row)
            content.addSpacing(8)
        content.addSpacing(4)
        content.addWidget(self.hint)
        content.addSpacing(6)
        content.addWidget(self.graphics_notice)
        content.addSpacing(10)
        content.addWidget(self.status)
        content.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(scroll, 1)
        layout.addLayout(action_row)

    def load_settings(self) -> dict[str, object]:
        defaults: dict[str, object] = {
            "width": 1280,
            "height": 720,
            "display_mode": "windowed",
            "vsync": True,
            "graphics_quality": "low",
            "msaa": 0,
            "fps_limit": 0,
        }
        try:
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                defaults.update(loaded)
        except (OSError, ValueError):
            pass
        return defaults

    def restore_controls(self) -> None:
        wanted = (int(self.settings.get("width", 1280)), int(self.settings.get("height", 720)))
        mode = str(self.settings.get("display_mode", "windowed"))
        if mode not in {"windowed", "borderless", "fullscreen"}:
            mode = "windowed"
        if mode == "windowed":
            if wanted not in self.windowed_modes:
                wanted = (1280, 720) if (1280, 720) in self.windowed_modes else self.windowed_modes[-1]
            self.last_windowed_resolution = wanted
        elif mode == "fullscreen":
            if wanted not in self.exclusive_modes:
                wanted = self.desktop_resolution if self.desktop_resolution in self.exclusive_modes else self.exclusive_modes[-1]
            self.last_fullscreen_resolution = wanted
        else:
            wanted = self.desktop_resolution

        self.mode_row.blockSignals(True)
        self.mode_row.set_current_data(mode)
        self.mode_row.blockSignals(False)
        self.apply_display_mode(wanted)

        quality = str(self.settings.get("graphics_quality", "low"))
        try:
            msaa = int(self.settings.get("msaa", 0))
            fps_limit = int(self.settings.get("fps_limit", 0))
        except (TypeError, ValueError):
            msaa, fps_limit = 0, 0
        if quality == "high":
            quality = "hybrid"
        if quality not in {"low", "hybrid", "native"}:
            quality = "low"
        self.msaa_row.set_current_data(msaa)
        self.quality_row.set_current_data(quality)
        self.quality_changed()
        self.fps_row.set_current_data(fps_limit)
        self.vsync_row.set_current_data(bool(self.settings.get("vsync", True)))
        self.resolution_row.setFocus(Qt.FocusReason.OtherFocusReason)

    def quality_changed(self) -> None:
        quality = str(self.quality_row.current_data() or "low")
        if quality == "hybrid":
            self.graphics_notice.setText(
                "ALTO HÍBRIDO · Renderer estable con filtrado anisotrópico de texturas hasta 16×; "
                "puede combinarse con MSAA."
            )
        elif quality == "native":
            self.graphics_notice.setText(
                "ALTO NATIVO · Activa el nivel 4 móvil original con framebuffers adaptados a "
                "ANGLE. MSAA se desactiva para preservar esta ruta de postprocesado."
            )
        else:
            self.graphics_notice.setText(
                "COMPATIBLE · Nivel 0 original y máxima estabilidad sobre ANGLE."
            )
        if self.quality_row.isEnabled():
            self.msaa_row.setEnabled(quality != "native")

    def selected_resolution(self) -> tuple[int, int]:
        value = str(self.resolution_row.current_data() or "1280x720")
        width, height = value.split("x", 1)
        return int(width), int(height)

    def select_resolution(self, resolution: tuple[int, int]) -> None:
        self.resolution_row.set_current_data(f"{resolution[0]}x{resolution[1]}")

    def display_mode_changed(self) -> None:
        if self.active_display_mode == "windowed" and self.resolution_row.isEnabled():
            self.last_windowed_resolution = self.selected_resolution()
        elif self.active_display_mode == "fullscreen" and self.resolution_row.isEnabled():
            self.last_fullscreen_resolution = self.selected_resolution()

        mode = str(self.mode_row.current_data())
        if mode == "borderless":
            preferred = self.desktop_resolution
        elif mode == "fullscreen":
            preferred = self.last_fullscreen_resolution
        else:
            preferred = self.last_windowed_resolution
        self.apply_display_mode(preferred)

    def apply_display_mode(self, preferred: tuple[int, int]) -> None:
        mode = str(self.mode_row.current_data())
        if mode == "borderless":
            choices = [self.desktop_resolution]
        elif mode == "fullscreen":
            choices = self.exclusive_modes
        else:
            choices = self.windowed_modes
        if preferred not in choices:
            preferred = self.desktop_resolution if self.desktop_resolution in choices else choices[-1]

        self.resolution_row.blockSignals(True)
        self.resolution_row.set_items(
            [(f"{width}X{height}", f"{width}x{height}") for width, height in choices]
        )
        self.select_resolution(preferred)
        self.resolution_row.blockSignals(False)

        if mode == "borderless":
            self.resolution_row.setEnabled(False)
            self.hint.setText("Sin bordes usa la resolución actual del escritorio para ocupar la pantalla sin cambiar el modo del monitor.")
        else:
            self.resolution_row.setEnabled(True)
            if mode == "fullscreen":
                self.hint.setText("El modo exclusivo cambia temporalmente la resolución del monitor y la restaura al cerrar el juego.")
            else:
                self.hint.setText("La ventana mantiene el tamaño elegido y puede minimizarse desde su barra de título.")
        self.active_display_mode = mode

    def validate_package(self) -> list[Path]:
        required = [
            self.runtime,
            self.root / "libEGL.dll",
            self.root / "libGLESv2.dll",
            self.root / "SDL2.dll",
            self.root / "libapp.so",
            self.root / "libc++_shared.so",
            self.root / "libfmodex.so",
            self.root / "libfmodevent.so",
            self.root / "libNimble.so",
            self.root / "game_data" / "main.1003128.com.ea.games.nfs13_row.obb",
        ]
        return [path for path in required if not path.is_file()]

    def save_settings(self, width: int, height: int, mode: str, vsync: bool,
                      quality: str, msaa: int, fps_limit: int) -> None:
        data = {
            "width": width,
            "height": height,
            "display_mode": mode,
            "vsync": vsync,
            "graphics_quality": quality,
            "msaa": msaa,
            "fps_limit": fps_limit,
        }
        self.config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def open_controller_settings(self) -> None:
        dialog = ControllerSettingsDialog(self.root / "controller.ini", self)
        dialog.exec()
        self.status.setText("Perfil de mando listo. Se aplicará al iniciar el juego.")

    def set_controls_enabled(self, enabled: bool) -> None:
        self.controller_button.setEnabled(enabled)
        self.play_button.setEnabled(enabled)
        self.mode_row.setEnabled(enabled)
        self.quality_row.setEnabled(enabled)
        self.msaa_row.setEnabled(enabled)
        self.fps_row.setEnabled(enabled)
        self.vsync_row.setEnabled(enabled)
        if enabled:
            self.display_mode_changed()
            self.quality_changed()
        else:
            self.resolution_row.setEnabled(False)

    def launch_game(self) -> None:
        missing = self.validate_package()
        if missing:
            names = "\n".join(f"• {path.name}" for path in missing)
            QMessageBox.critical(self, APP_TITLE, f"Faltan componentes del port nativo:\n\n{names}")
            return

        width, height = self.selected_resolution()
        mode = str(self.mode_row.current_data())
        vsync = bool(self.vsync_row.current_data())
        quality = str(self.quality_row.current_data())
        msaa = int(self.msaa_row.current_data())
        fps_limit = int(self.fps_row.current_data())
        try:
            self.save_settings(width, height, mode, vsync, quality, msaa, fps_limit)
            log_path = self.root / "game_data" / "runtime.log"
            log_stream = log_path.open("w", encoding="utf-8")
            command = [
                str(self.runtime),
                "--play",
                str(width),
                str(height),
                mode,
                "1" if vsync else "0",
                quality,
                str(msaa),
                str(fps_limit),
                str(self.root),
            ]
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.process = subprocess.Popen(
                command,
                cwd=str(self.root),
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            log_stream.close()
        except OSError as exc:
            QMessageBox.critical(self, APP_TITLE, f"No se pudo iniciar el motor nativo.\n\n{exc}")
            return

        self.set_controls_enabled(False)
        self.status.setText("Iniciando el motor nativo…")
        QTimer.singleShot(1200, self.finish_launch)

    def finish_launch(self) -> None:
        if self.process is not None and self.process.poll() is not None:
            try:
                log_text = (self.root / "game_data" / "runtime.log").read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                log_text = "No se pudo leer runtime.log."
            excerpt = log_text[-2500:] if log_text else "El motor terminó sin dejar información."
            QMessageBox.critical(
                self,
                APP_TITLE,
                f"El motor nativo se cerró durante el arranque.\n\n{excerpt}",
            )
            self.set_controls_enabled(True)
            self.status.setText("Corrige el problema e inténtalo nuevamente.")
            return
        self.close()


def main() -> int:
    set_dpi_awareness()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = LauncherWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
