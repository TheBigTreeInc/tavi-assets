"""Post-run exact archive receipt gate; no network involved."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tavi_assets.tavia import create_tavia

class PostrunTests(unittest.TestCase):
    def test_default_dryrun_and_no_receipt_execution(self):
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/'cards.tavia'
            create_tavia(ROOT/'examples/cards-v1',archive)
            cmd=[sys.executable,str(ROOT/'tools/ziprunner-tavia-postrun.py'),str(archive)]
            dry=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(dry.returncode,0,dry.stderr)
            payload=json.loads(dry.stdout)
            self.assertEqual(payload['action'],'dry_run')
            self.assertEqual(payload['sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
            denied=subprocess.run(cmd+['--execute'],capture_output=True,text=True)
            self.assertNotEqual(denied.returncode,0)
    def test_receipt_with_wrong_digest_denied(self):
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/'cards.tavia'
            create_tavia(ROOT/'examples/cards-v1',archive)
            receipt=Path(d)/'approve.json'
            receipt.write_text(json.dumps({'action':'stage','approvedSha256':'0'*64,'endpoint':'https://example.invalid/dapi'}))
            result=subprocess.run([sys.executable,str(ROOT/'tools/ziprunner-tavia-postrun.py'),str(archive),'--execute','--approval-receipt',str(receipt)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('not valid',result.stderr)
if __name__=='__main__':unittest.main()
