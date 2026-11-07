import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from tavi_assets.core import AssetError, validate

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "pack"
        shutil.copytree(EXAMPLES / "cards-v1", self.root)

    def manifest(self):
        return json.loads((self.root / "manifest.json").read_text())

    def update(self, manifest):
        (self.root / "manifest.json").write_text(json.dumps(manifest))

    def test_duplicate_manifest_keys_denied(self):
        text = (self.root / "manifest.json").read_text()
        (self.root / "manifest.json").write_text(text.replace('"id":', '"id": "attacker", "id":', 1))
        with self.assertRaisesRegex(AssetError, "duplicate"):
            validate(self.root)

    def test_script_svg_denied_even_when_digest_correct(self):
        unsafe = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        self.assertUnsafeSvg(unsafe)

    def test_svg_external_reference_denied(self):
        unsafe = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/file"/></svg>'
        self.assertUnsafeSvg(unsafe)

    def test_svg_event_attribute_denied(self):
        unsafe = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'
        self.assertUnsafeSvg(unsafe)

    def assertUnsafeSvg(self, contents):
        p = self.root / "front.svg"; p.write_bytes(contents)
        manifest = self.manifest()
        manifest["files"]["front.svg"] = hashlib.sha256(contents).hexdigest()
        self.update(manifest)
        with self.assertRaises(AssetError):
            validate(self.root)

    def test_file_symlink_denied(self):
        (self.root / "front.svg").unlink()
        try:
            (self.root / "front.svg").symlink_to(self.root / "back-blue.svg")
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable")
        with self.assertRaisesRegex(AssetError, "symlink"):
            validate(self.root)

    def test_bad_variant_denied(self):
        manifest = self.manifest()
        manifest["resources"]["card.back"]["variants"]["evil"] = "../secret.svg"
        self.update(manifest)
        with self.assertRaisesRegex(AssetError, "invalid variant"):
            validate(self.root)

    def test_incompatible_host_rejected(self):
        manifest = self.manifest()
        manifest["compatibility"] = {"host": "tavi-assets/v2"}
        self.update(manifest)
        with self.assertRaisesRegex(AssetError, "compatibility"):
            validate(self.root)

    def test_invalid_pack_version(self):
        manifest = self.manifest(); manifest["version"] = "0.1.1-rc1"
        self.update(manifest)
        with self.assertRaisesRegex(AssetError, "version"):
            validate(self.root)

    def test_win_drive_or_backslash_escape(self):
        for unsafe in ("C:/windows.svg", "..\\escape.svg", "../escape.svg", "nested//asset.svg"):
            manifest = self.manifest()
            manifest["files"][unsafe] = "0" * 64
            self.update(manifest)
            with self.assertRaises(AssetError, msg=unsafe):
                validate(self.root)
            (self.root / "manifest.json").write_text((EXAMPLES / "cards-v1" / "manifest.json").read_text())

    def test_html_in_svg_filename_rejected(self):
        manifest = self.manifest()
        manifest["files"]["index.html"] = "0" * 64
        self.update(manifest)
        with self.assertRaises(AssetError):
            validate(self.root)


if __name__ == "__main__":
    unittest.main()

class TestWindowsPathSafety(unittest.TestCase):
    def test_reject_reserved_name_and_case_collision(self):
        from tavi_assets.core import _inside
        for unsafe in ("CON.svg", "path/NUL.png", "com1.svg", "LPT9.json"):
            with self.assertRaises(AssetError):
                _inside(unsafe)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "pack"
            shutil.copytree(EXAMPLES / "cards-v1", folder)
            manifest = json.loads((folder / "manifest.json").read_text())
            (folder / "FRONT.SVG").write_bytes((folder / "front.svg").read_bytes())
            manifest["files"]["FRONT.SVG"] = manifest["files"]["front.svg"]
            (folder / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(AssetError, "case-colliding"):
                validate(folder)
