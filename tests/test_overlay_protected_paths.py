"""TA-019 regression: 0.1.5 source placed under protected runtime/** was silently excluded.

This test intentionally simulates the protected subset of the Windows ZipRunner
source overlay without writing to any operator-owned path. Real Windows acceptance
still needs an independent ZipRunner job receipt.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_contracts import ContractError, check_contracts, protected_source_path


class ProtectedOverlayRegression(unittest.TestCase):
    def setUp(self):
        self.recipe = json.loads((ROOT / "project.zr").read_text(encoding="utf-8"))
        self.patterns = self.recipe["protected_paths"]

    def test_protect_runtime_but_not_portable_service(self):
        self.assertIn("runtime/**", self.patterns)
        self.assertTrue(protected_source_path("runtime/service.mjs", self.patterns))
        self.assertTrue(protected_source_path("RUNTIME/service.mjs", self.patterns))
        self.assertFalse(protected_source_path("portable_service/service.mjs", self.patterns))
        self.assertFalse(protected_source_path("portable_service/node-file-storage.mjs", self.patterns))
        self.assertTrue(protected_source_path("../runtime/service.mjs", self.patterns))
        self.assertTrue(protected_source_path("C:/tmp/pack.mjs", self.patterns))
        self.assertTrue(protected_source_path("runtime\\service.mjs", self.patterns))

    def test_only_real_source_outside_protected_directories(self):
        manifest = json.loads((ROOT / "ziprunner-manifest.json").read_text(encoding="utf-8"))
        for task in manifest["done_work"]:
            for evidence in task["evidence"]:
                p = evidence["ref"]
                with self.subTest(path=p):
                    self.assertFalse(protected_source_path(p, self.patterns))
                    self.assertTrue((ROOT / p).is_file())
        for path in ROOT.joinpath("portable_service").rglob("*"):
            if path.is_file():
                relative = path.relative_to(ROOT).as_posix()
                with self.subTest(path=relative):
                    self.assertFalse(protected_source_path(relative, self.patterns))

    def test_simulated_protected_source_overlay_passes_contract(self):
        # Copy without source entries under protected paths, just as a Windows
        # source overlay would. This verifies the *effective* installed source,
        # not merely the completeness of the input ZIP.
        with tempfile.TemporaryDirectory(prefix="ta-019-overlay-") as temporary:
            dst = Path(temporary)
            for source in ROOT.rglob("*"):
                if not source.is_file():
                    continue
                relative = source.relative_to(ROOT)
                if protected_source_path(relative.as_posix(), self.patterns):
                    continue
                target = dst / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            self.assertFalse((dst / "runtime" / "service.mjs").exists())
            self.assertTrue((dst / "portable_service" / "service.mjs").is_file())
            self.assertIn("Workboard IDs", check_contracts(dst))
            # The filtered install also executes Node code successfully, not only
            # metadata lookup. Running the full Python suite here would recurse.
            node = shutil.which("node")
            self.assertIsNotNone(node, "Node must be present for this source build")
            result = subprocess.run(
                [node, str(dst / "tests" / "runtime_portable_smoke.mjs")],
                cwd=dst, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
            self.assertIn("10/10 scenarios passed", result.stdout)
            # A poisoned source manifest referring back to a protected path must
            # fail before any build or release acceptance.
            mp = dst / "ziprunner-manifest.json"
            altered = json.loads(mp.read_text(encoding="utf-8"))
            altered["done_work"][0]["evidence"][0]["ref"] = "runtime/service.mjs"
            mp.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "excluded by ZipRunner protected paths"):
                check_contracts(dst)


if __name__ == "__main__":
    unittest.main()
