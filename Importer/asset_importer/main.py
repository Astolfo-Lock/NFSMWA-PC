from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path


def _boot_log(message: str) -> None:
    try:
        path = Path(os.environ.get("TEMP", ".")).joinpath("nfsmw_asset_importer_cli.log")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        return


try:
    from .constants import APP_TITLE
    from .paths import ProjectPaths, discover_project_root, fallback_bundle_root, save_game_root
    from .pipeline import ImportCancelled, Pipeline, PipelineError
    from . import ui as _ui_module
except Exception:
    _boot_log(traceback.format_exc())
    raise


def set_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def safe_print(message: str) -> None:
    stream = sys.stdout
    if stream is None:
        return
    try:
        print(message, flush=True)
    except OSError:
        return


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=APP_TITLE,
        description="Importa el APK x86 y el OBB intacto de NFS Most Wanted Android 1.3.128.",
    )
    parser.add_argument("--project-root", help="Raíz del port nativo (carpeta con native_prototype).")
    parser.add_argument("--game-root", help="Carpeta destino de .so, fuentes y OBB (por ejemplo NFSMWA\\Juego).")
    parser.add_argument("--detect", action="store_true", help="Detectar dispositivos ADB y salir.")
    parser.add_argument("--import-local", nargs=2, metavar=("APK", "OBB"),
                        help="Importar desde archivos locales y salir.")
    parser.add_argument("--serial", help="Número de serie ADB para importar desde el teléfono.")
    return parser.parse_args(argv)


def run_cli(args: argparse.Namespace, project: ProjectPaths) -> int:
    pipeline = Pipeline(
        project,
        log=safe_print,
        progress=lambda pct, msg: safe_print(f"[{pct:3d}%] {msg}"),
        set_device=lambda msg: safe_print(f"Dispositivo: {msg}"),
        set_version=lambda msg: safe_print(f"Versión: {msg}"),
        set_stage=lambda msg: safe_print(f"Etapa: {msg}"),
    )
    try:
        if args.detect:
            devices = pipeline.detect_devices()
            if not devices:
                return 2
            return 0
        if args.import_local:
            apk, obb = args.import_local
            result = pipeline.import_from_files(Path(apk), Path(obb), source_label="local")
            safe_print(result.message)
            return 0 if result.assets_ok else 1
        if args.serial:
            from .adb import AdbDevice

            devices = pipeline.detect_devices()
            match = next((item for item in devices if item.serial == args.serial), None)
            if match is None:
                match = AdbDevice(serial=args.serial, state="device")
            result = pipeline.import_from_phone(match)
            safe_print(result.message)
            return 0 if result.assets_ok else 1
    except ImportCancelled as exc:
        safe_print(str(exc))
        return 130
    except PipelineError as exc:
        safe_print(str(exc))
        try:
            _cli_error_log().write_text(str(exc), encoding="utf-8")
        except OSError:
            pass
        return 1
    return 0


def run_gui(project: ProjectPaths) -> int:
    set_dpi_awareness()
    from PyQt6.QtWidgets import QApplication

    from .ui import ImporterWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = ImporterWindow(project)
    window.show()
    return app.exec()


def _cli_error_log() -> Path:
    return Path(os.environ.get("TEMP", ".")).expanduser() / "nfsmw_asset_importer_cli.log"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cli_mode = bool(args.detect or args.import_local or args.serial)
    if cli_mode:
        try:
            _cli_error_log().write_text(
                "CLI iniciada. Los argumentos se omiten por privacidad.\n",
                encoding="utf-8",
            )
        except OSError:
            pass
    try:
        root = discover_project_root(args.project_root)
    except FileNotFoundError as exc:
        if cli_mode:
            safe_print(str(exc))
            return 2
        root = fallback_bundle_root()
    project = ProjectPaths(root, game_root=args.game_root)
    if args.game_root:
        save_game_root(project.root, project.native_prototype)
    if cli_mode:
        try:
            return run_cli(args, project)
        except Exception:
            detail = traceback.format_exc()
            try:
                _cli_error_log().write_text(detail, encoding="utf-8")
            except OSError:
                pass
            safe_print(detail)
            return 1
    try:
        return run_gui(project)
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
