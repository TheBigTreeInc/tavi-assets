"""Verify reference SDK with Node when installed; no Node dependency for Python users."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class JSContractTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node not available: verify sdk on Windows acceptance machine')
    def test_consumer_sdk_with_mocked_transport(self):
        result = subprocess.run(['node', str(ROOT/'tests/consumer_sdk_smoke.mjs')], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('smoke passed', result.stdout)

if __name__ == '__main__': unittest.main()
