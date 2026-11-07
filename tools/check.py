"""Cross-platform, zero-extra-dependency source-tree verification for ZipRunner."""
import sys
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
    print(f"Catalog/pack validation: passed; tests: {result.testsRun}, failures: {len(result.failures)}, errors: {len(result.errors)}", flush=True)
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
