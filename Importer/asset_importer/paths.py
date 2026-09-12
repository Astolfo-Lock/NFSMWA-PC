from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from .constants import (
    BACKUP_DIRNAME,
    LIBRARY_FILENAMES,
    MANIFEST_NAME,
    PATHS_SETTINGS_NAME,
    RUNTIME_FILES,
)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def program_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def settings_path(root: Path) -> Path:
    return root / PATHS_SETTINGS_NAME


def load_saved_game_root(root: Path) -> Path | None:
    path = settings_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    raw = data.get("game_root") if isinstance(data, dict) else None
    if not raw:
        return None
    candidate = Path(str(raw))
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def save_game_root(root: Path, game_root: Path) -> None:
    game_root = game_root.resolve()
    root = root.resolve()
    try:
        stored = os.path.relpath(game_root, root).replace("\\", "/")
    except ValueError:
        stored = str(game_root)
    settings_path(root).write_text(
        json.dumps({"game_root": stored}, indent=2) + "\n",
        encoding="utf-8",
    )


def suggested_game_roots(root: Path) -> list[tuple[str, Path]]:
    return [
        ("native_prototype (raíz del port)", root / "native_prototype"),
        ("NFSMWA\\Juego", root / "NFSMWA" / "Juego"),
        ("Juego (junto al pack)", root / "Juego"),
        ("NFSMWA\\Motor", root / "NFSMWA" / "Motor"),
        ("Motor (junto al pack)", root / "Motor"),
    ]


def game_package_dir(root: Path, explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("NFSMW_GAME_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    saved = load_saved_game_root(root)
    if saved is not None:
        return saved
    prototype = root / "native_prototype"
    motor = root / "NFSMWA" / "Motor"
    if (motor / "libapp.so").is_file():
        return motor.resolve()
    return prototype


def relocate_game_package(src: Path, dest: Path) -> list[str]:
    src = src.resolve()
    dest = dest.resolve()
    if src == dest:
        return []
    dest.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    names = (
        *LIBRARY_FILENAMES,
        *RUNTIME_FILES,
        "Need For Speed Most Wanted Android.exe",
        "LICENSE.txt",
        "SDL2_LICENSE.txt",
        "CONTROLES.txt",
        "README.md",
        "controller.ini",
        "launcher_settings.json",
        MANIFEST_NAME,
    )
    for name in names:
        from_path = src / name
        if not from_path.is_file():
            continue
        to_path = dest / name
        to_path.parent.mkdir(parents=True, exist_ok=True)
        if to_path.exists():
            to_path.unlink()
        shutil.move(str(from_path), str(to_path))
        moved.append(name)
    for folder in ("fonts", "game_data"):
        from_dir = src / folder
        if not from_dir.is_dir():
            continue
        to_dir = dest / folder
        if not to_dir.exists():
            shutil.move(str(from_dir), str(to_dir))
            moved.append(folder + "/")
            continue
        for child in from_dir.iterdir():
            target = to_dir / child.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.move(str(child), str(target))
            moved.append(f"{folder}/{child.name}")
    return moved


def looks_like_project_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    names = {child.name.lower() for child in path.iterdir()}
    if {"launcher", "importer", "motor", "exesimple"} <= names or (
        "launcher" in names and "importer" in names
    ):
        return True
    if "exesimple" in names and ("motor" in names or "importer" in names):
        return True
    has_port = (
        (path / "build.ps1").is_file()
        or (path / "native_analysis").is_dir()
        or (path / "native_runtime").is_dir()
        or (path / "asset_importer").is_dir()
        or (path / "Importer" / "asset_importer").is_dir()
    )
    has_place = (
        (path / "native_prototype").is_dir()
        or (path / "NFSMWA").is_dir()
        or (path / "Motor").is_dir()
        or settings_path(path).is_file()
        or (path / "asset_importer").is_dir()
    )
    return has_port and has_place


def discover_project_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if looks_like_project_root(candidate):
            return candidate
        raise FileNotFoundError(f"No parece la raíz del port nativo: {candidate}")

    env = os.environ.get("NFSMW_PROJECT_ROOT")
    if env:
        candidate = Path(env).expanduser().resolve()
        if looks_like_project_root(candidate):
            return candidate

    starts = [Path.cwd().resolve(), program_dir()]
    if not is_frozen():
        starts.append(Path(__file__).resolve().parent.parent)

    seen: set[Path] = set()
    for start in starts:
        current = start
        for _ in range(8):
            if current in seen:
                break
            seen.add(current)
            if looks_like_project_root(current):
                return current
            if current.name.lower() in {
                "para github",
                "paragithub",
                "dist",
                "native_prototype",
                "nfsmwa",
                "launcher",
                "motor",
                "importer",
                "exesimple",
            }:
                parent = current.parent
                if looks_like_project_root(parent):
                    return parent
            current = current.parent

    raise FileNotFoundError(
        "No se encontró la raíz del proyecto. Ejecuta el importador junto a "
        "native_prototype o indica --project-root."
    )


def fallback_bundle_root() -> Path:
    start = program_dir()
    if start.name.lower() in {"exesimple", "dist", "launcher", "importer"}:
        return start.parent
    return start


class ProjectPaths:
    def __init__(self, root: Path, game_root: str | Path | None = None) -> None:
        self.root = root.resolve()
        self.native_analysis_apk = self.root / "native_analysis" / "apk"
        self.build_script = self.root / "build.ps1"
        self.backups = self.root / BACKUP_DIRNAME
        self.platform_tools = next(
            (
                candidate
                for candidate in (
                    self.root / "platform-tools",
                    self.root / "Importer" / "platform-tools",
                    program_dir() / "platform-tools",
                )
                if candidate.is_dir()
            ),
            self.root / "platform-tools",
        )
        self.set_game_root(game_package_dir(self.root, game_root))

    def set_game_root(self, path: Path) -> None:
        self.native_prototype = Path(path).expanduser().resolve()
        self.fonts = self.native_prototype / "fonts"
        self.game_data = self.native_prototype / "game_data"
        self.manifest = self.native_prototype / MANIFEST_NAME

    def ensure_destination_dirs(self) -> None:
        self.native_analysis_apk.mkdir(parents=True, exist_ok=True)
        self.native_prototype.mkdir(parents=True, exist_ok=True)
        self.fonts.mkdir(parents=True, exist_ok=True)
        self.game_data.mkdir(parents=True, exist_ok=True)


def _meipass() -> Path | None:
    raw = getattr(sys, "_MEIPASS", None)
    return Path(raw) if raw else None


def materialize_bundled_adb() -> Path | None:
    mei = _meipass()
    if mei is None:
        return None
    sources = [mei / "platform-tools", mei]
    src = next((folder for folder in sources if (folder / "adb.exe").is_file()), None)
    if src is None:
        return None
    dest = program_dir() / "platform-tools"
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.suffix.lower() not in {".exe", ".dll"} and item.name.lower() != "adb.exe":
            continue
        target = dest / item.name
        if not target.is_file() or target.stat().st_size != item.stat().st_size:
            shutil.copy2(item, target)
    adb = dest / "adb.exe"
    return adb if adb.is_file() else None


def find_adb(project: ProjectPaths) -> Path | None:
    bundled = materialize_bundled_adb()
    candidates = [
        bundled,
        program_dir() / "adb.exe",
        program_dir() / "platform-tools" / "adb.exe",
        project.platform_tools / "adb.exe",
        project.root / "adb.exe",
        project.root / "Importer" / "platform-tools" / "adb.exe",
    ]
    mei = _meipass()
    if mei is not None:
        candidates.extend([mei / "adb.exe", mei / "platform-tools" / "adb.exe"])
    for path in candidates:
        if path is not None and path.is_file():
            return path.resolve()
    found = shutil.which("adb.exe") or shutil.which("adb")
    return Path(found).resolve() if found else None
