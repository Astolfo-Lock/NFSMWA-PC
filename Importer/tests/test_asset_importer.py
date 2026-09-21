from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from asset_importer.adb import describe_device_state, parse_devices
from asset_importer.constants import (
    FONT_ASSETS,
    FONT_FILENAMES,
    LIBRARY_FILENAMES,
    OBB_FILENAME,
    PACKAGE_NAME,
    X86_LIBRARIES,
)
from asset_importer.paths import ProjectPaths
from asset_importer.i18n import set_language, t, translate_message
from asset_importer.pipeline import Pipeline, PipelineError
from asset_importer.validation import ValidationError, validate_apk, validate_obb, validate_pair
from asset_importer.zip_safe import ZipSafetyError, is_safe_zip_name, safe_destination


class TranslationTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_language("es")

    def test_language_switch_and_dynamic_messages(self) -> None:
        set_language("en")
        self.assertEqual(t("Etapa", "Stage"), "Stage")
        message = "El OBB no contiene los datos published.1x y published.2x requeridos."
        self.assertEqual(
            translate_message(message),
            "The OBB does not contain the required published.1x and published.2x data.",
        )

    def test_spanish_remains_default(self) -> None:
        set_language("es")
        self.assertEqual(t("Resultado", "Result"), "Resultado")


def elf_x86() -> bytes:
    data = bytearray(64)
    data[0:4] = b"\x7fELF"
    data[4] = 1
    data[5] = 1
    data[6] = 1
    data[18:20] = (3).to_bytes(2, "little")
    return bytes(data)


def elf_arm() -> bytes:
    data = bytearray(64)
    data[0:4] = b"\x7fELF"
    data[4] = 1
    data[5] = 1
    data[6] = 1
    data[18:20] = (40).to_bytes(2, "little")
    return bytes(data)


def manifest_bytes(version: str = "1.3.128", package: str = PACKAGE_NAME, code: str = "1003128") -> bytes:
    text = f"package {package} versionName {version} versionCode {code}"
    return text.encode("utf-16le")


def write_zip(path: Path, entries: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return path


def valid_apk_entries(**overrides: bytes) -> dict[str, bytes]:
    entries: dict[str, bytes] = {
        "AndroidManifest.xml": manifest_bytes(),
        **{name: elf_x86() for name in X86_LIBRARIES},
        **{name: b"ttf-" + name.encode() for name in FONT_ASSETS},
        "lib/armeabi-v7a/libapp.so": elf_arm(),
        "res/layout/main.xml": b"<xml/>",
    }
    entries.update(overrides)
    return entries


def valid_obb_entries() -> dict[str, bytes]:
    return {
        "published.1x/texturepacks_ui/menu.sba": b"one-x",
        "published.2x/texturepacks_ui/menu.sba": b"two-x",
        "published/flow/dummy.sb": b"flow",
    }


class ZipSafeTests(unittest.TestCase):
    def test_rejects_traversal_and_absolute(self) -> None:
        self.assertFalse(is_safe_zip_name("../evil.so"))
        self.assertFalse(is_safe_zip_name("lib/x86/../../windows/evil.dll"))
        self.assertFalse(is_safe_zip_name("C:/Windows/evil.dll"))
        self.assertFalse(is_safe_zip_name("/tmp/evil"))
        self.assertTrue(is_safe_zip_name("lib/x86/libapp.so"))

    def test_safe_destination_stays_inside(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            dest = safe_destination(root, "lib/x86/libapp.so")
            self.assertTrue(str(dest).startswith(str(root.resolve())))
            with self.assertRaises(ZipSafetyError):
                safe_destination(root, "../outside.so")


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_apk_and_obb(self) -> None:
        apk = write_zip(self.dir / "NeedForSpeedMostWanted.apk", valid_apk_entries())
        obb = write_zip(self.dir / OBB_FILENAME, valid_obb_entries())
        report = validate_pair(apk, obb)
        self.assertEqual(report.version_name, "1.3.128")
        self.assertTrue(report.obb_has_1x)
        self.assertTrue(report.obb_has_2x)

    def test_rejects_missing_x86_library(self) -> None:
        entries = valid_apk_entries()
        del entries["lib/x86/libapp.so"]
        apk = write_zip(self.dir / "game.apk", entries)
        with self.assertRaises(ValidationError) as ctx:
            validate_apk(apk)
        self.assertIn("lib/x86/libapp.so", str(ctx.exception))

    def test_rejects_arm_instead_of_x86(self) -> None:
        entries = valid_apk_entries()
        del entries["lib/x86/libapp.so"]
        apk = write_zip(self.dir / "game.apk", entries)
        with self.assertRaises(ValidationError) as ctx:
            validate_apk(apk)
        self.assertIn("armeabi-v7a", str(ctx.exception))

    def test_rejects_x86_file_that_is_actually_arm(self) -> None:
        apk = write_zip(self.dir / "game.apk", valid_apk_entries(**{"lib/x86/libapp.so": elf_arm()}))
        with self.assertRaises(ValidationError) as ctx:
            validate_apk(apk)
        self.assertIn("ARM", str(ctx.exception))

    def test_rejects_missing_font(self) -> None:
        entries = valid_apk_entries()
        del entries[FONT_ASSETS[0]]
        apk = write_zip(self.dir / "game.apk", entries)
        with self.assertRaises(ValidationError) as ctx:
            validate_apk(apk)
        self.assertIn("gothamblack.ttf", str(ctx.exception))

    def test_rejects_wrong_version(self) -> None:
        apk = write_zip(
            self.dir / "game.apk",
            valid_apk_entries(**{"AndroidManifest.xml": manifest_bytes(version="1.3.127")}),
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_apk(apk)
        self.assertIn("1.3.127", str(ctx.exception))

    def test_rejects_obb_without_published_layers(self) -> None:
        obb = write_zip(self.dir / OBB_FILENAME, {"published/flow/dummy.sb": b"x"})
        with self.assertRaises(ValidationError) as ctx:
            validate_obb(obb)
        self.assertIn("published.1x", str(ctx.exception))

    def test_rejects_wrong_obb_name(self) -> None:
        obb = write_zip(self.dir / "main.other.obb", valid_obb_entries())
        with self.assertRaises(ValidationError):
            validate_obb(obb)

    def test_rejects_corrupt_zip(self) -> None:
        apk = self.dir / "broken.apk"
        apk.write_bytes(b"this is not a zip")
        with self.assertRaises(ValidationError) as ctx:
            validate_apk(apk)
        self.assertIn("ZIP", str(ctx.exception))

    def test_rejects_zip_slip_in_apk(self) -> None:
        apk = self.dir / "slip.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            for name, payload in valid_apk_entries().items():
                archive.writestr(name, payload)
            info = zipfile.ZipInfo("../../evil.so")
            archive.writestr(info, b"evil")
        with self.assertRaises(ZipSafetyError):
            validate_apk(apk)


class AdbParseTests(unittest.TestCase):
    def test_parse_mixed_states(self) -> None:
        output = (
            "List of devices attached\n"
            "R58M123\tdevice product:star2lte model:SM_G965F device:star2lte\n"
            "emulator-5554\tunauthorized\n"
            "ABC\toffline\n"
        )
        devices = parse_devices(output)
        self.assertEqual(len(devices), 3)
        self.assertTrue(devices[0].authorized)
        self.assertEqual(devices[0].model, "SM G965F")
        self.assertEqual(devices[1].state, "unauthorized")
        self.assertEqual(devices[2].state, "offline")
        summary = describe_device_state(devices)
        self.assertIn("No autorizado", summary)
        self.assertIn("Offline", summary)

    def test_no_devices(self) -> None:
        devices = parse_devices("List of devices attached\n")
        self.assertEqual(devices, [])
        self.assertIn("Ningún dispositivo", describe_device_state(devices))


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "native_prototype" / "game_data").mkdir(parents=True)
        (self.root / "native_analysis").mkdir()
        (self.root / "build.ps1").write_text("# dummy\n", encoding="utf-8")
        self.project = ProjectPaths(self.root)
        self.apk = write_zip(self.root / "NeedForSpeedMostWanted.apk", valid_apk_entries())
        self.obb = write_zip(self.root / OBB_FILENAME, valid_obb_entries())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_simulated_full_import(self) -> None:
        previous = self.project.native_prototype / "libapp.so"
        previous.write_bytes(b"old-lib")
        pipeline = Pipeline(self.project)
        result = pipeline.import_from_files(self.apk, self.obb, source_label="local")
        self.assertTrue(result.assets_ok)
        self.assertFalse(result.play_ready)
        self.assertIn("Recursos originales importados correctamente", result.message)
        for name in LIBRARY_FILENAMES:
            self.assertTrue((self.project.native_prototype / name).is_file())
            self.assertEqual((self.project.native_prototype / name).read_bytes(), elf_x86())
        for name in FONT_FILENAMES:
            self.assertTrue((self.project.fonts / name).is_file())
        obb_dest = self.project.game_data / OBB_FILENAME
        self.assertTrue(obb_dest.is_file())
        self.assertTrue(zipfile.is_zipfile(obb_dest))
        self.assertFalse((self.project.game_data / "published.1x").exists())
        self.assertTrue((self.project.native_analysis_apk / "lib" / "x86" / "libapp.so").is_file())
        self.assertTrue((self.project.native_analysis_apk / "AndroidManifest.xml").is_file())
        self.assertFalse((self.project.native_prototype / "lib" / "armeabi-v7a").exists())
        backup_lib = next(self.project.backups.rglob("libapp.so"))
        self.assertEqual(backup_lib.read_bytes(), b"old-lib")
        manifest = json.loads(self.project.manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version_name"], "1.3.128")
        self.assertIn("libapp.so", manifest["files"])
        self.assertIn("sha256", manifest["files"]["libapp.so"])

    def test_play_ready_when_runtime_present(self) -> None:
        for name in (
            "nfsmwa_runtime.exe",
            "libEGL.dll",
            "libGLESv2.dll",
            "SDL2.dll",
            "simd_unaligned_addresses.bin",
        ):
            (self.project.native_prototype / name).write_bytes(b"stub")
        pipeline = Pipeline(self.project)
        result = pipeline.import_from_files(self.apk, self.obb)
        self.assertTrue(result.play_ready)
        self.assertEqual(result.message, "Paquete completo listo para jugar.")

    def test_does_not_copy_save_data(self) -> None:
        saves = self.project.game_data / "var" / "nfstr_save.sb"
        saves.parent.mkdir(parents=True)
        saves.write_bytes(b"keep-me")
        log = self.project.game_data / "runtime.log"
        log.write_text("old log", encoding="utf-8")
        pipeline = Pipeline(self.project)
        pipeline.import_from_files(self.apk, self.obb)
        self.assertEqual(saves.read_bytes(), b"keep-me")
        self.assertEqual(log.read_text(encoding="utf-8"), "old log")

    def test_same_validation_used_before_install(self) -> None:
        bad = write_zip(self.root / "bad.apk", valid_apk_entries(**{"lib/x86/libapp.so": elf_arm()}))
        pipeline = Pipeline(self.project)
        with self.assertRaises(PipelineError):
            pipeline.import_from_files(bad, self.obb)
        self.assertFalse((self.project.native_prototype / "libapp.so").exists())


class PathDiscoveryTests(unittest.TestCase):
    def test_looks_like_project_root(self) -> None:
        from asset_importer.paths import looks_like_project_root

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.assertFalse(looks_like_project_root(root))
            (root / "native_prototype").mkdir()
            (root / "native_analysis").mkdir()
            self.assertTrue(looks_like_project_root(root))

    def test_clean_pack_layout_is_a_root(self) -> None:
        from asset_importer.paths import looks_like_project_root

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "Launcher").mkdir()
            (root / "Importer").mkdir()
            (root / "Motor").mkdir()
            (root / "ExeSimple").mkdir()
            self.assertTrue(looks_like_project_root(root))

    def test_custom_game_root_and_relocate(self) -> None:
        from asset_importer.paths import ProjectPaths, relocate_game_package, save_game_root, load_saved_game_root

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "native_prototype").mkdir()
            (root / "native_analysis").mkdir()
            (root / "build.ps1").write_text("# dummy\n", encoding="utf-8")
            old = root / "native_prototype"
            (old / "libapp.so").write_bytes(b"lib")
            (old / "game_data").mkdir()
            (old / "game_data" / "main.1003128.com.ea.games.nfs13_row.obb").write_bytes(b"obb")
            dest = root / "NFSMWA" / "Juego"
            project = ProjectPaths(root, game_root=dest)
            self.assertEqual(project.native_prototype, dest.resolve())
            save_game_root(root, dest)
            self.assertEqual(load_saved_game_root(root), dest.resolve())
            saved_text = (root / "nfsmw_paths.json").read_text(encoding="utf-8")
            self.assertNotIn(":\\", saved_text)
            self.assertIn("NFSMWA/Juego", saved_text)
            moved = relocate_game_package(old, dest)
            self.assertIn("libapp.so", moved)
            self.assertTrue((dest / "libapp.so").is_file())
            self.assertTrue((dest / "game_data" / "main.1003128.com.ea.games.nfs13_row.obb").is_file())
            self.assertFalse((old / "libapp.so").exists())


if __name__ == "__main__":
    unittest.main()
