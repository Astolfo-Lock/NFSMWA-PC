from __future__ import annotations

PACKAGE_NAME = "com.ea.games.nfs13_row"
VERSION_NAME = "1.3.128"
VERSION_CODE = "1003128"
OBB_FILENAME = f"main.{VERSION_CODE}.{PACKAGE_NAME}.obb"
APK_DISPLAY_NAME = "NeedForSpeedMostWanted.apk"

X86_LIBRARIES = (
    "lib/x86/libc++_shared.so",
    "lib/x86/libfmodex.so",
    "lib/x86/libfmodevent.so",
    "lib/x86/libNimble.so",
    "lib/x86/libapp.so",
)

FONT_ASSETS = (
    "assets/published/fonts/gothamblack.ttf",
    "assets/published/fonts/gothambold.ttf",
    "assets/published/fonts/gothamboldita.ttf",
    "assets/published/fonts/gothambook.ttf",
    "assets/published/fonts/gothambook_mono.ttf",
    "assets/published/fonts/hawaiidigitalnumbers.ttf",
)

LIBRARY_FILENAMES = tuple(path.split("/")[-1] for path in X86_LIBRARIES)
FONT_FILENAMES = tuple(path.split("/")[-1] for path in FONT_ASSETS)

OBB_REQUIRED_PREFIXES = ("published.1x/", "published.2x/")

RUNTIME_FILES = (
    "nfsmwa_runtime.exe",
    "libEGL.dll",
    "libGLESv2.dll",
    "SDL2.dll",
    "simd_unaligned_addresses.bin",
)

OBB_CANDIDATE_PATHS = (
    f"/sdcard/Android/obb/{PACKAGE_NAME}/{OBB_FILENAME}",
    f"/storage/emulated/0/Android/obb/{PACKAGE_NAME}/{OBB_FILENAME}",
    f"/storage/self/primary/Android/obb/{PACKAGE_NAME}/{OBB_FILENAME}",
)

MANIFEST_NAME = "asset_import_manifest.json"
PATHS_SETTINGS_NAME = "nfsmw_paths.json"
BACKUP_DIRNAME = "importer_backups"
ELF_MACHINE_386 = 3
ELF_MACHINE_ARM = 40
APP_TITLE = "NFSMW Asset Importer"
GAME_TITLE = "Need for Speed Most Wanted"
