"""Cross-platform, zero-extra-dependency source-tree verification for ZipRunner."""
import sys
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tavi_assets.catalog import Catalog
from tavi_assets.core import validate
from verify_contracts import check_contracts


def main():
    print(check_contracts(ROOT), flush=True)
    validate(ROOT / "examples" / "cards-v1")
    validate(ROOT / "examples" / "cards-v2")
    validate(ROOT / "examples" / "storybook-decks")
    Catalog(ROOT / "examples")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        node = shutil.which("node")
        if not node:
            print("Node.js unavailable: portable runtime and consumer SDK are unverified", flush=True)
            return 1
        for script in ("tests/consumer_sdk_smoke.mjs", "tests/runtime_portable_smoke.mjs", "examples/portable-runtime-demo.mjs"):
            print(f"Running Node source check: {script}", flush=True)
            proc = subprocess.run([node, str(ROOT / script)], cwd=ROOT, check=False)
            if proc.returncode:
                print(f"Node test failed ({proc.returncode}): {script}", flush=True)
                return 1
    print(f"Catalog/pack validation: passed; tests: {result.testsRun}, failures: {len(result.failures)}, errors: {len(result.errors)}", flush=True)
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
