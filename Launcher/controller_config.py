from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from nfs_chrome import (
    NfsActionButton,
    NfsHeader,
    NfsOptionRow,
    fit_nfs_window,
    make_nfs_page_scroll,
    make_section_label,
    make_wrapping_label,
    nfs_chrome_stylesheet,
    paint_nfs_body,
)


XINPUT_BUTTONS: dict[str, int] = {
    "DPAD_UP": 0x0001,
    "DPAD_DOWN": 0x0002,
    "DPAD_LEFT": 0x0004,
    "DPAD_RIGHT": 0x0008,
    "START": 0x0010,
    "BACK": 0x0020,
    "LS": 0x0040,
    "RS": 0x0080,
    "LB": 0x0100,
    "RB": 0x0200,
    "A": 0x1000,
    "B": 0x2000,
    "X": 0x4000,
    "Y": 0x8000,
}

PHYSICAL_LABELS = {
    "NONE": "SIN ASIGNAR",
    "A": "A",
    "B": "B",
    "X": "X",
    "Y": "Y",
    "LB": "LB",
    "RB": "RB",
    "LT": "LT",
    "RT": "RT",
    "START": "START",
    "BACK": "SELECT / BACK",
    "LS": "L3",
    "RS": "R3",
    "DPAD_UP": "CRUCETA ARRIBA",
    "DPAD_DOWN": "CRUCETA ABAJO",
    "DPAD_LEFT": "CRUCETA IZQUIERDA",
    "DPAD_RIGHT": "CRUCETA DERECHA",
}

MAPPING_DEFINITIONS = (
    ("moga_a", "MOGA A / aceptar", "A"),
    ("moga_b", "MOGA B / atrás", "B"),
    ("moga_x", "MOGA X", "X"),
    ("moga_y", "MOGA Y", "Y"),
    ("moga_l1", "MOGA L1", "LB"),
    ("moga_r1", "MOGA R1", "RB"),
    ("moga_l2", "MOGA L2", "LT"),
    ("moga_r2", "MOGA R2", "RT"),
    ("moga_start", "Pausa / Start", "START"),
    ("moga_select", "Select", "BACK"),
    ("moga_left_thumb", "Pulsar stick izquierdo", "LS"),
    ("moga_right_thumb", "Pulsar stick derecho", "RS"),
    ("moga_dpad_up", "Cruceta arriba", "DPAD_UP"),
    ("moga_dpad_down", "Cruceta abajo", "DPAD_DOWN"),
    ("moga_dpad_left", "Cruceta izquierda", "DPAD_LEFT"),
    ("moga_dpad_right", "Cruceta derecha", "DPAD_RIGHT"),
)


class XInputGamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XInputState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", XInputGamepad)]


class JoyInfoEx(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("dwXpos", wintypes.DWORD),
        ("dwYpos", wintypes.DWORD),
        ("dwZpos", wintypes.DWORD),
        ("dwRpos", wintypes.DWORD),
        ("dwUpos", wintypes.DWORD),
        ("dwVpos", wintypes.DWORD),
        ("dwButtons", wintypes.DWORD),
        ("dwButtonNumber", wintypes.DWORD),
        ("dwPOV", wintypes.DWORD),
        ("dwReserved1", wintypes.DWORD),
        ("dwReserved2", wintypes.DWORD),
    ]


class JoyCapsW(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("szPname", wintypes.WCHAR * 32),
        ("wXmin", wintypes.UINT),
        ("wXmax", wintypes.UINT),
        ("wYmin", wintypes.UINT),
        ("wYmax", wintypes.UINT),
        ("wZmin", wintypes.UINT),
        ("wZmax", wintypes.UINT),
        ("wNumButtons", wintypes.UINT),
        ("wPeriodMin", wintypes.UINT),
        ("wPeriodMax", wintypes.UINT),
        ("wRmin", wintypes.UINT),
        ("wRmax", wintypes.UINT),
        ("wUmin", wintypes.UINT),
        ("wUmax", wintypes.UINT),
        ("wVmin", wintypes.UINT),
        ("wVmax", wintypes.UINT),
        ("wCaps", wintypes.UINT),
        ("wMaxAxes", wintypes.UINT),
        ("wNumAxes", wintypes.UINT),
        ("wMaxButtons", wintypes.UINT),
        ("szRegKey", wintypes.WCHAR * 32),
        ("szOEMVxD", wintypes.WCHAR * 260),
    ]


@dataclass
class ControllerReading:
    name: str
    backend: str
    active_inputs: set[str]


class XInputBackend:
    def __init__(self) -> None:
        self.library_name = ""
        self._library = None
        self._get_state = None
        if os.name != "nt":
            return
        for library_name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                library = ctypes.WinDLL(library_name)
                get_state = library.XInputGetState
                get_state.argtypes = [wintypes.DWORD, ctypes.POINTER(XInputState)]
                get_state.restype = wintypes.DWORD
            except (AttributeError, OSError):
                continue
            self.library_name = library_name
            self._library = library
            self._get_state = get_state
            break

    @property
    def available(self) -> bool:
        return self._get_state is not None

    def state(self, player: int) -> XInputState | None:
        if self._get_state is None:
            return None
        state = XInputState()
        return state if self._get_state(player, ctypes.byref(state)) == 0 else None

    @staticmethod
    def active_inputs(state: XInputState | None) -> set[str]:
        if state is None:
            return set()
        active = {
            name for name, mask in XINPUT_BUTTONS.items() if state.Gamepad.wButtons & mask
        }
        if state.Gamepad.bLeftTrigger >= 30:
            active.add("LT")
        if state.Gamepad.bRightTrigger >= 30:
            active.add("RT")
        return active


class WinMMBackend:
    """Architecture-independent fallback for DirectInput/HID joysticks.

    This is important for the bundled runtime: its SDL2.dll is 32-bit, while
    the PyQt launcher may be 64-bit and therefore cannot load that DLL.
    """

    JOY_RETURNALL = 0x000000FF
    JOY_POVCENTERED = 0xFFFF
    BUTTONS = (
        "A", "B", "X", "Y", "LB", "RB", "LT", "RT",
        "BACK", "START", "LS", "RS",
    )

    def __init__(self) -> None:
        self.library_name = ""
        self.error = ""
        self._get_pos = None
        self._get_caps = None
        self._num_devices = None
        if os.name != "nt":
            return
        try:
            library = ctypes.WinDLL("winmm.dll")
            self._get_pos = library.joyGetPosEx
            self._get_pos.argtypes = [wintypes.UINT, ctypes.POINTER(JoyInfoEx)]
            self._get_pos.restype = wintypes.UINT
            self._get_caps = library.joyGetDevCapsW
            self._get_caps.argtypes = [wintypes.UINT, ctypes.POINTER(JoyCapsW), wintypes.UINT]
            self._get_caps.restype = wintypes.UINT
            self._num_devices = library.joyGetNumDevs
            self._num_devices.argtypes = []
            self._num_devices.restype = wintypes.UINT
            self.library_name = "WinMM/HID"
        except (AttributeError, OSError) as exc:
            self.error = str(exc)
            self._get_pos = None

    @property
    def available(self) -> bool:
        return self._get_pos is not None

    def _state(self, device_id: int) -> JoyInfoEx | None:
        if self._get_pos is None:
            return None
        state = JoyInfoEx()
        state.dwSize = ctypes.sizeof(state)
        state.dwFlags = self.JOY_RETURNALL
        return state if self._get_pos(device_id, ctypes.byref(state)) == 0 else None

    def device_indexes(self) -> list[int]:
        if self._num_devices is None:
            return []
        indexes = []
        for index in range(min(16, self._num_devices())):
            caps = self._caps(index)
            # Some Windows installations expose a placeholder joystick with
            # zero controls. It must not occupy a visible controller slot.
            if self._state(index) and caps and (caps.wNumButtons or caps.wNumAxes):
                indexes.append(index)
        return indexes

    def _caps(self, device_id: int) -> JoyCapsW | None:
        if self._get_caps is None:
            return None
        caps = JoyCapsW()
        if self._get_caps(device_id, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
            return caps
        return None

    def _name(self, device_id: int) -> str:
        caps = self._caps(device_id)
        return caps.szPname if caps and caps.szPname else "Mando HID"

    def device_names(self) -> list[str]:
        return [self._name(index) for index in self.device_indexes()]

    def reading(self, player: int) -> ControllerReading | None:
        indexes = self.device_indexes()
        if player >= len(indexes):
            return None
        device_id = indexes[player]
        state = self._state(device_id)
        if state is None:
            return None
        active = {
            name for button, name in enumerate(self.BUTTONS)
            if state.dwButtons & (1 << button)
        }
        pov = state.dwPOV
        if pov != self.JOY_POVCENTERED:
            # Values are hundredths of a degree. Include both directions for
            # diagonals, using broad sectors to tolerate imperfect devices.
            if pov >= 31500 or pov <= 4500:
                active.add("DPAD_UP")
            if 4500 <= pov <= 13500:
                active.add("DPAD_RIGHT")
            if 13500 <= pov <= 22500:
                active.add("DPAD_DOWN")
            if 22500 <= pov <= 31500:
                active.add("DPAD_LEFT")
        return ControllerReading(
            name=self._name(device_id),
            backend="WinMM/HID",
            active_inputs=active,
        )


class SDL2Backend:
    INIT_JOYSTICK = 0x00000200
    INIT_GAMECONTROLLER = 0x00002000
    BUTTONS = {
        "A": 0,
        "B": 1,
        "X": 2,
        "Y": 3,
        "BACK": 4,
        "START": 6,
        "LS": 7,
        "RS": 8,
        "LB": 9,
        "RB": 10,
        "DPAD_UP": 11,
        "DPAD_DOWN": 12,
        "DPAD_LEFT": 13,
        "DPAD_RIGHT": 14,
    }

    def __init__(self, runtime_root: Path | None = None) -> None:
        self.library_name = ""
        self.error = ""
        self._library = None
        self._controller: int | None = None
        self._controller_player = -1
        self._available = False
        if os.name != "nt":
            return
        candidates: list[Path] = []
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            candidates.append(Path(bundle_root) / "SDL2.dll")
        if runtime_root is not None:
            candidates.append(Path(runtime_root) / "SDL2.dll")
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / "SDL2.dll")
        source_root = Path(__file__).resolve().parent
        candidates.extend((
            source_root / "SDL2.dll",
            source_root.parent / "Motor" / "SDL2.dll",
            source_root / "third_party" / "SDL2" / "x64" / "SDL2.dll",
        ))
        seen: set[Path] = set()
        for candidate in candidates:
            try:
                candidate = candidate.resolve()
            except OSError:
                pass
            if candidate in seen:
                continue
            seen.add(candidate)
            if not candidate.is_file():
                continue
            try:
                self._library = ctypes.WinDLL(str(candidate))
                self.library_name = f"SDL2/HID · {candidate.name}"
                self._bind_functions()
                self._set_hint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1")
                if self._init(self.INIT_JOYSTICK | self.INIT_GAMECONTROLLER) != 0:
                    self.error = self._error_text()
                    self._library = None
                    continue
                self.error = ""
                self._available = True
                break
            except (AttributeError, OSError) as exc:
                self.error = str(exc)
                self._library = None
        if not self._available and not self.error:
            self.error = "SDL2.dll no encontrada"

    def _bind_functions(self) -> None:
        assert self._library is not None
        self._set_hint = self._library.SDL_SetHint
        self._set_hint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self._set_hint.restype = ctypes.c_int
        self._init = self._library.SDL_Init
        self._init.argtypes = [ctypes.c_uint32]
        self._init.restype = ctypes.c_int
        self._quit = self._library.SDL_Quit
        self._quit.argtypes = []
        self._quit.restype = None
        self._num_joysticks = self._library.SDL_NumJoysticks
        self._num_joysticks.argtypes = []
        self._num_joysticks.restype = ctypes.c_int
        self._is_controller = self._library.SDL_IsGameController
        self._is_controller.argtypes = [ctypes.c_int]
        self._is_controller.restype = ctypes.c_int
        self._name_for_index = self._library.SDL_GameControllerNameForIndex
        self._name_for_index.argtypes = [ctypes.c_int]
        self._name_for_index.restype = ctypes.c_char_p
        self._open = self._library.SDL_GameControllerOpen
        self._open.argtypes = [ctypes.c_int]
        self._open.restype = ctypes.c_void_p
        self._close = self._library.SDL_GameControllerClose
        self._close.argtypes = [ctypes.c_void_p]
        self._close.restype = None
        self._attached = self._library.SDL_GameControllerGetAttached
        self._attached.argtypes = [ctypes.c_void_p]
        self._attached.restype = ctypes.c_int
        self._name = self._library.SDL_GameControllerName
        self._name.argtypes = [ctypes.c_void_p]
        self._name.restype = ctypes.c_char_p
        self._button = self._library.SDL_GameControllerGetButton
        self._button.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._button.restype = ctypes.c_ubyte
        self._axis = self._library.SDL_GameControllerGetAxis
        self._axis.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._axis.restype = ctypes.c_int16
        self._update = self._library.SDL_GameControllerUpdate
        self._update.argtypes = []
        self._update.restype = None
        self._pump_events = self._library.SDL_PumpEvents
        self._pump_events.argtypes = []
        self._pump_events.restype = None
        self._get_error = self._library.SDL_GetError
        self._get_error.argtypes = []
        self._get_error.restype = ctypes.c_char_p

    @property
    def available(self) -> bool:
        return self._available

    def _error_text(self) -> str:
        if not self._library:
            return self.error
        value = self._get_error()
        return value.decode("utf-8", errors="replace") if value else "error desconocido"

    def device_indexes(self) -> list[int]:
        if not self.available:
            return []
        # SDL only refreshes its hot-plug device list while its event loop is
        # pumped.  The launcher has a Qt event loop, not an SDL one.
        self._pump_events()
        self._update()
        return [index for index in range(max(0, self._num_joysticks())) if self._is_controller(index)]

    def device_names(self) -> list[str]:
        names: list[str] = []
        for index in self.device_indexes():
            value = self._name_for_index(index)
            names.append(value.decode("utf-8", errors="replace") if value else "Mando HID")
        return names

    def _close_controller(self) -> None:
        if self._controller:
            self._close(self._controller)
        self._controller = None
        self._controller_player = -1

    def reading(self, player: int) -> ControllerReading | None:
        if not self.available:
            return None
        self._update()
        if self._controller and not self._attached(self._controller):
            self._close_controller()
        indexes = self.device_indexes()
        if player >= len(indexes):
            self._close_controller()
            return None
        if not self._controller or self._controller_player != player:
            self._close_controller()
            self._controller = self._open(indexes[player])
            self._controller_player = player if self._controller else -1
        if not self._controller or not self._attached(self._controller):
            return None
        active = {
            name for name, button in self.BUTTONS.items() if self._button(self._controller, button)
        }
        if self._axis(self._controller, 4) > 8000:
            active.add("LT")
        if self._axis(self._controller, 5) > 8000:
            active.add("RT")
        value = self._name(self._controller)
        name = value.decode("utf-8", errors="replace") if value else "Mando HID"
        return ControllerReading(name=name, backend="SDL2/HID", active_inputs=active)

    def close(self) -> None:
        self._close_controller()
        if self.available:
            self._quit()
        self._available = False


class HybridControllerBackend:
    def __init__(self, runtime_root: Path | None = None) -> None:
        self.xinput = XInputBackend()
        self.sdl = SDL2Backend(runtime_root)
        self.winmm = WinMMBackend()

    @property
    def library_name(self) -> str:
        backends = []
        if self.xinput.available:
            backends.append(self.xinput.library_name)
        if self.sdl.available:
            backends.append("SDL2/HID")
        if self.winmm.available:
            backends.append(self.winmm.library_name)
        return " + ".join(backends) or self.sdl.error or self.winmm.error or "sin backend disponible"

    def reading(self, player: int) -> ControllerReading | None:
        xinput_state = self.xinput.state(player)
        if xinput_state is not None:
            return ControllerReading(
                name=f"Mando XInput {player + 1}",
                backend="XInput",
                active_inputs=self.xinput.active_inputs(xinput_state),
            )
        return self.sdl.reading(player) or self.winmm.reading(player)

    def slot_labels(self) -> list[str]:
        sdl_names = self.sdl.device_names()
        winmm_names = self.winmm.device_names()
        labels = []
        for player in range(4):
            if self.xinput.state(player) is not None:
                labels.append(f"Mando XInput {player + 1}")
            elif player < len(sdl_names):
                labels.append(f"{sdl_names[player]} · HID/SDL")
            elif player < len(winmm_names):
                labels.append(f"{winmm_names[player]} · HID/Windows")
            else:
                labels.append(f"Mando {player + 1} · no detectado")
        return labels

    def close(self) -> None:
        self.sdl.close()


def default_controller_settings() -> dict[str, object]:
    return {
        "enabled": True,
        "player": 0,
        "deadzone": 0.18,
        "bindings": {key: default for key, _label, default in MAPPING_DEFINITIONS},
    }


def load_controller_settings(path: Path) -> dict[str, object]:
    settings = default_controller_settings()
    bindings = dict(settings["bindings"])
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", ";")) or "=" not in line:
                continue
            key, value = (part.strip() for part in line.split("=", 1))
            if key == "enabled":
                settings["enabled"] = value != "0"
            elif key == "player":
                settings["player"] = min(3, max(0, int(value)))
            elif key == "deadzone":
                settings["deadzone"] = min(0.4, max(0.0, float(value)))
            elif key in bindings and value.upper() in PHYSICAL_LABELS:
                bindings[key] = value.upper()
    except (OSError, ValueError):
        pass
    settings["bindings"] = bindings
    return settings


def save_controller_settings(path: Path, settings: dict[str, object]) -> None:
    bindings = dict(settings["bindings"])
    lines = [
        "# Perfil XInput/HID -> MOGA para NFS Most Wanted",
        f"enabled={1 if settings['enabled'] else 0}",
        f"player={int(settings['player'])}",
        f"deadzone={float(settings['deadzone']):.2f}",
    ]
    lines.extend(f"{key}={bindings[key]}" for key, _label, _default in MAPPING_DEFINITIONS)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ControllerSettingsDialog(QDialog):
    def __init__(
        self,
        config_path: Path,
        parent: QWidget | None = None,
        *,
        language: str = "es",
    ) -> None:
        super().__init__(parent)
        self.language = "en" if language == "en" else "es"
        self.config_path = config_path
        # controller.ini lives beside the native runtime and its SDL2.dll.
        # Passing that directory avoids depending on the launcher's current
        # working directory (and also works for the packaged executable).
        self.backend = HybridControllerBackend(config_path.parent)
        self.settings = load_controller_settings(config_path)
        self.bindings = dict(self.settings["bindings"])
        self.binding_buttons: dict[str, NfsActionButton] = {}
        self.awaiting_binding: str | None = None
        self.capture_baseline: set[str] = set()

        self.setObjectName("controllerDialog")
        self.setWindowTitle(self.tr("Mando MOGA", "MOGA Controller"))
        self.setModal(True)
        self.setStyleSheet("QDialog#controllerDialog { background: #3A4A52; }" + nfs_chrome_stylesheet())
        self._build_ui()
        self._restore_ui()
        fit_nfs_window(self, 540, 720, min_width=400, min_height=420)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(35)
        self.poll_timer.timeout.connect(self._poll_controller)
        self.poll_timer.start()
        self.finished.connect(lambda _result: self.backend.close())

    def tr(self, spanish: str, english: str) -> str:
        return english if self.language == "en" else spanish

    def physical_label(self, name: str) -> str:
        label = PHYSICAL_LABELS.get(name, "SIN ASIGNAR")
        if self.language != "en":
            return label
        translations = {
            "SIN ASIGNAR": "UNASSIGNED",
            "CRUCETA ARRIBA": "D-PAD UP",
            "CRUCETA ABAJO": "D-PAD DOWN",
            "CRUCETA IZQUIERDA": "D-PAD LEFT",
            "CRUCETA DERECHA": "D-PAD RIGHT",
        }
        return translations.get(label, label)

    def mapping_label(self, label: str) -> str:
        if self.language != "en":
            return label
        translations = {
            "MOGA A / aceptar": "MOGA A / accept",
            "MOGA B / atrás": "MOGA B / back",
            "Pausa / Start": "Pause / Start",
            "Pulsar stick izquierdo": "Press left stick",
            "Pulsar stick derecho": "Press right stick",
            "Cruceta arriba": "D-pad up",
            "Cruceta abajo": "D-pad down",
            "Cruceta izquierda": "D-pad left",
            "Cruceta derecha": "D-pad right",
        }
        return translations.get(label, label)

    def controller_label(self, label: str) -> str:
        if self.language != "en":
            return label
        return label.replace("Mando", "Controller").replace("no detectado", "not detected")

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        paint_nfs_body(self, painter)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.awaiting_binding and event.key() == Qt.Key.Key_Escape:
            self.awaiting_binding = None
            self.capture_baseline.clear()
            self._refresh_binding_buttons()
            self.status.setText(self.tr("Asignación cancelada.", "Assignment cancelled."))
            event.accept()
            return
        if self.awaiting_binding and event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
            logical = self.awaiting_binding
            self.bindings[logical] = "NONE"
            self.awaiting_binding = None
            self.capture_baseline.clear()
            self._refresh_binding_buttons()
            self.status.setText(self.tr("Entrada dejada sin asignar.", "Input left unassigned."))
            event.accept()
            return
        super().keyPressEvent(event)

    def _build_ui(self) -> None:
        header = NfsHeader(
            self.tr("MANDO MOGA", "MOGA CONTROLLER"),
            self.tr("XINPUT + HID/SDL · CONFIGURACIÓN Y MAPEO", "XINPUT + HID/SDL · SETUP AND MAPPING"),
        )

        self.enabled_row = NfsOptionRow(self.tr("Soporte de mando", "Controller support"))
        self.enabled_row.set_items([
            (self.tr("ACTIVADO", "ON"), True),
            (self.tr("DESACTIVADO", "OFF"), False),
        ])

        self.device_row = NfsOptionRow(self.tr("Dispositivo", "Device"))
        self.device_row.set_items([
            (self.controller_label(label), player)
            for player, label in enumerate(self.backend.slot_labels())
        ])
        self.device_row.valueChanged.connect(self._device_changed)

        self.deadzone_row = NfsOptionRow(self.tr("Zona muerta de sticks", "Stick dead zone"))
        self.deadzone_row.set_items([(f"{percent}%", percent) for percent in range(0, 41)])

        mapping_section = make_section_label(self.tr("ASIGNACIÓN DE BOTONES", "BUTTON MAPPING"))
        mapping_hint = make_wrapping_label(
            self.tr(
                "Pulsa una asignación y después el botón físico deseado. Los sticks permanecen "
                "analógicos; LT y RT también pueden utilizarse como botones. Esc cancela y Supr "
                "deja la entrada sin asignar.",
                "Select an assignment and then press the desired physical button. The sticks "
                "remain analog; LT and RT can also be used as buttons. Esc cancels and Delete "
                "leaves the input unassigned.",
            ),
            "hint",
        )

        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        for row, (key, label, _default) in enumerate(MAPPING_DEFINITIONS):
            action_label = make_wrapping_label(self.mapping_label(label).upper(), "hint")
            button = NfsActionButton("", compact=True)
            button.clicked.connect(lambda _checked=False, mapping_key=key: self._begin_capture(mapping_key))
            self.binding_buttons[key] = button
            grid.addWidget(action_label, row, 0)
            grid.addWidget(button, row, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(1, 120)

        self.status = make_wrapping_label("", "status")

        reset_button = NfsActionButton(self.tr("RESTABLECER", "RESET"), compact=True)
        reset_button.clicked.connect(self._reset_defaults)
        save_button = NfsActionButton(self.tr("GUARDAR", "SAVE"))
        save_button.clicked.connect(self._save)
        back_button = NfsActionButton(self.tr("VOLVER", "BACK"), compact=True)
        back_button.clicked.connect(self.reject)
        actions = QHBoxLayout()
        actions.setContentsMargins(24, 0, 24, 16)
        actions.setSpacing(8)
        actions.addWidget(back_button)
        actions.addWidget(reset_button)
        actions.addWidget(save_button, 1)

        scroll, body = make_nfs_page_scroll()
        content = QVBoxLayout(body)
        content.setContentsMargins(24, 14, 24, 16)
        content.setSpacing(0)
        content.addWidget(self.enabled_row)
        content.addSpacing(8)
        content.addWidget(self.device_row)
        content.addSpacing(8)
        content.addWidget(self.deadzone_row)
        content.addSpacing(12)
        content.addWidget(mapping_section)
        content.addSpacing(8)
        content.addWidget(mapping_hint)
        content.addSpacing(8)
        content.addWidget(grid_wrap)
        content.addSpacing(8)
        content.addWidget(self.status)
        content.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(scroll, 1)
        layout.addLayout(actions)

    def _restore_ui(self) -> None:
        self.enabled_row.set_current_data(bool(self.settings["enabled"]))
        self.device_row.set_current_data(int(self.settings["player"]))
        self.deadzone_row.set_current_data(round(float(self.settings["deadzone"]) * 100))
        self._refresh_binding_buttons()
        self._poll_controller()

    def _refresh_binding_buttons(self) -> None:
        for key, button in self.binding_buttons.items():
            button.setText(self.physical_label(self.bindings.get(key, "NONE")))

    def _device_changed(self) -> None:
        self.awaiting_binding = None
        self.capture_baseline.clear()
        self._refresh_binding_buttons()
        self._poll_controller()

    def _begin_capture(self, mapping_key: str) -> None:
        self.awaiting_binding = mapping_key
        reading = self.backend.reading(int(self.device_row.current_data() or 0))
        self.capture_baseline = reading.active_inputs if reading else set()
        self._refresh_binding_buttons()
        self.binding_buttons[mapping_key].setText(self.tr("PULSA UN BOTÓN…", "PRESS A BUTTON…"))
        self.status.setText(self.tr(
            "Esperando una entrada del mando. Pulsa el botón físico que quieras asignar.",
            "Waiting for controller input. Press the physical button you want to assign.",
        ))

    def _poll_controller(self) -> None:
        player = int(self.device_row.current_data() or 0)
        labels = [self.controller_label(label) for label in self.backend.slot_labels()]
        existing = self.device_row.item_labels()
        if existing != labels:
            self.device_row.blockSignals(True)
            self.device_row.set_items([(label, index) for index, label in enumerate(labels)])
            self.device_row.set_current_data(player)
            self.device_row.blockSignals(False)
        reading = self.backend.reading(player)
        active = reading.active_inputs if reading else set()
        if self.awaiting_binding:
            if not active:
                self.capture_baseline.clear()
            new_inputs = active - self.capture_baseline
            if new_inputs:
                physical = next(name for name in PHYSICAL_LABELS if name in new_inputs)
                logical = self.awaiting_binding
                self.bindings[logical] = physical
                self.awaiting_binding = None
                self.capture_baseline.clear()
                self._refresh_binding_buttons()
                self.status.setText(self.tr(
                    f"Asignado: {self.physical_label(physical)}.",
                    f"Assigned: {self.physical_label(physical)}.",
                ))
                return
        if reading is None:
            backend = self.backend.library_name or self.tr("XInput no disponible", "XInput unavailable")
            self.status.setText(self.tr(
                f"Mando {player + 1} no detectado · backend: {backend}.",
                f"Controller {player + 1} not detected · backend: {backend}.",
            ))
        else:
            pressed = ", ".join(self.physical_label(name) for name in PHYSICAL_LABELS if name in active)
            self.status.setText(
                f"{self.controller_label(reading.name)} conectado mediante {reading.backend}"
                + (
                    self.tr(f" · entrada: {pressed}", f" · input: {pressed}")
                    if pressed
                    else self.tr(" · esperando entrada", " · waiting for input")
                )
            )
            if self.language == "en":
                self.status.setText(self.status.text().replace(" conectado mediante ", " connected through "))

    def _reset_defaults(self) -> None:
        defaults = default_controller_settings()
        self.enabled_row.set_current_data(True)
        self.device_row.set_current_data(0)
        self.deadzone_row.set_current_data(18)
        self.bindings = dict(defaults["bindings"])
        self.awaiting_binding = None
        self._refresh_binding_buttons()
        self.status.setText(self.tr(
            "Asignaciones estándar restauradas. Pulsa GUARDAR para aplicarlas.",
            "Default assignments restored. Press SAVE to apply them.",
        ))

    def _save(self) -> None:
        settings = {
            "enabled": bool(self.enabled_row.current_data()),
            "player": int(self.device_row.current_data() or 0),
            "deadzone": int(self.deadzone_row.current_data() or 18) / 100.0,
            "bindings": self.bindings,
        }
        try:
            save_controller_settings(self.config_path, settings)
        except OSError as exc:
            QMessageBox.critical(
                self,
                self.tr("Mando MOGA", "MOGA Controller"),
                self.tr(f"No se pudo guardar el perfil.\n\n{exc}", f"Could not save the profile.\n\n{exc}"),
            )
            return
        self.settings = settings
        self.status.setText(self.tr(
            "Perfil MOGA guardado. Se aplicará al iniciar el juego.",
            "MOGA profile saved. It will be applied when the game starts.",
        ))
