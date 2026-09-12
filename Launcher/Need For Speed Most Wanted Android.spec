# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

_here = Path(SPEC).resolve().parent


def _find_sdl():
    env_root = os.environ.get("NFSMW_PROJECT_ROOT")
    starts = [_here]
    if env_root:
        starts.append(Path(env_root))
    seen: set[Path] = set()
    current = _here
    for _ in range(6):
        if current in seen:
            break
        seen.add(current)
        starts.append(current)
        if current.parent == current:
            break
        current = current.parent
    for start in starts:
        direct = start / "third_party" / "SDL2" / "x64" / "SDL2.dll"
        if direct.is_file():
            return direct
        try:
            children = list(start.iterdir())
        except OSError:
            continue
        for child in children[:40]:
            if not child.is_dir():
                continue
            nested = child / "third_party" / "SDL2" / "x64" / "SDL2.dll"
            if nested.is_file():
                return nested
    return None


_sdl = _find_sdl()
_binaries = [(str(_sdl), ".")] if _sdl else []

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=_binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Need For Speed Most Wanted Android',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
