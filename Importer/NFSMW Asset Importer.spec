# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

_here = Path(SPEC).resolve().parent


def _find_platform_tools():
    current = _here
    for _ in range(6):
        for candidate in (
            current / "platform-tools",
            current / "Importer" / "platform-tools",
        ):
            if (candidate / "adb.exe").is_file():
                return candidate
        try:
            children = list(current.iterdir())
        except OSError:
            children = []
        for child in children[:40]:
            if not child.is_dir():
                continue
            nested = child / "platform-tools"
            if (nested / "adb.exe").is_file():
                return nested
            nested = child / "Importer" / "platform-tools"
            if (nested / "adb.exe").is_file():
                return nested
        if current.parent == current:
            break
        current = current.parent
    return None


_adb_binaries = []
_tools = _find_platform_tools()
if _tools is not None:
    for name in ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "libwinpthread-1.dll"):
        item = _tools / name
        if item.is_file():
            _adb_binaries.append((str(item), "platform-tools"))

a = Analysis(
    ['NFSMW_Asset_Importer.py'],
    pathex=[],
    binaries=_adb_binaries,
    datas=[],
    hiddenimports=collect_submodules('asset_importer'),
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
    name='NFSMW Asset Importer',
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
