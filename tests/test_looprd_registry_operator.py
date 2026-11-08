"""No-network tests of the operator controls and read-only actions."""
import importlib.util
import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('registry_operator',ROOT/'tools'/'looprd-registry.py')
operator=importlib.util.module_from_spec(spec);spec.loader.exec_module(operator)

class RegistryOperatorTests(unittest.TestCase):
    def test_reject_http_url_and_embedded_credentials(self):
        for url in ('http://localhost/api','https://bad@example.org/api','https://example.org/api?token=xx'):
            with self.assertRaises(ValueError):operator.endpoint(url)
    def test_default_publish_dry_run_without_credentials(self):
        self.assertEqual(operator.main(['publish','--url','https://looprd.test/admin','--pack-id','org.example.cards','--version','1.0.0']),0)
    def test_exact_receipt_match_and_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'approval.json';digest='a'*64
            rec={'action':'publish','packId':'org.example.cards','version':'1.0.0',
                 'manifestSha256':digest,'endpoint':'https://looprd.test/admin'}
            path.write_text(json.dumps(rec))
            operator.check_receipt(path,'publish','org.example.cards','1.0.0',digest,'https://looprd.test/admin')
            with self.assertRaises(ValueError):operator.check_receipt(path,'revoke','org.example.cards','1.0.0',digest,'https://looprd.test/admin')
            with self.assertRaises(ValueError):operator.check_receipt(path,'publish','org.example.cards','1.0.1',digest,'https://looprd.test/admin')
    def test_publish_requires_exact_receipt_before_mutation(self):
        with patch.dict('os.environ',{'LOOPRD_ASSETS_PUBLISH_TOKEN':'x'*40}):
            calls=[]
            def fake(url,token,op,**payload):
                calls.append(op)
                if op=='inspect':return {'ok':True,'versions':[{'packId':'org.example.cards','version':'1.0.0','status':'ready','manifestSha256':'a'*64}]}
                raise AssertionError('mutating operation was attempted')
            with patch.object(operator,'request',side_effect=fake):
                self.assertEqual(operator.main(['publish','--execute','--url','https://looprd.test/admin','--pack-id','org.example.cards','--version','1.0.0']),1)
            self.assertEqual(calls,['inspect'])
    def test_resource_download_digest_verified_before_write(self):
        import base64
        data=b'hello assets';digest=hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'icon.png'
            with patch.dict('os.environ',{'LOOPRD_ASSETS_READ_TOKEN':'x'*40}):
                with patch.object(operator,'request',return_value={'ok':True,'offset':0,'total':len(data),'sha256':digest,'contentBase64':base64.b64encode(data).decode()}):
                    self.assertEqual(operator.main(['resource','--url','https://looprd.test/catalog','--pack-id','org.example.cards','--version','1.0.0','--name','icon.png','--output',str(dest)]),0)
                self.assertEqual(dest.read_bytes(),data)
                with patch.object(operator,'request',return_value={'ok':True,'offset':0,'total':len(data),'sha256':'0'*64,'contentBase64':base64.b64encode(data).decode()}):
                    self.assertEqual(operator.main(['resource','--url','https://looprd.test/catalog','--pack-id','org.example.cards','--version','1.0.0','--name','icon.png','--output',str(Path(d)/'bad.png')]),1)
                    self.assertFalse((Path(d)/'bad.png').exists())
if __name__=='__main__':unittest.main()
