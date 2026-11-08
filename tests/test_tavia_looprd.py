"""End-to-end local LoopRD protocol simulation. No network, no external service."""
import base64
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
# The production LoopRD handler uses SQLAlchemy, but ZipRunner source checks
# must run on a stock Windows Python without pip installing server packages.
try:
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    SQL_BACKEND = 'sqlalchemy'
except ImportError:
    import sqlite_test_adapter as sa
    from sqlite_test_adapter import sessionmaker
    SQL_BACKEND = 'sqlite3-test-adapter'

# Importing LoopRD's production handler requires its server dependencies.
# For source checks only, load the exact source against the stdlib SQLite
# adapter without injecting fake modules into global sys.modules.

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tavi_assets.tavia import create_tavia,unpack_tavia
from tavi_assets.core import AssetError
spec=importlib.util.spec_from_file_location('assets_looprd_handler', ROOT/'looprd'/'handler.py')
h=importlib.util.module_from_spec(spec)
if SQL_BACKEND == 'sqlalchemy':
    spec.loader.exec_module(h)
else:
    # Execute the actual handler unchanged, replacing only its import lines
    # in an isolated module namespace; production source is not modified.
    source = (ROOT/'looprd'/'handler.py').read_text(encoding='utf8')
    source = source.replace('import sqlalchemy as sa', '')
    source = source.replace('from starlette.concurrency import run_in_threadpool', '')
    h.__dict__['sa'] = sa
    exec(compile(source, str(ROOT/'looprd'/'handler.py'), 'exec'), h.__dict__)
from tavi_assets.core import validate
h.validate=validate;h.AssetError=AssetError;h.MAX_FILE=20*1024*1024
spec=importlib.util.spec_from_file_location('assets_looprd_generator', ROOT/'looprd'/'generate.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)

class TaviaLoopRDTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.db=self.base/'db.sqlite'
        self.engine=sa.create_engine('sqlite:///'+str(self.db))
        with self.engine.begin() as conn:
            for stmt in g.schema():conn.execute(sa.text(stmt))
        self.Session=sessionmaker(bind=self.engine)
        self.source=ROOT/'examples/cards-v1'
        self.archive=self.base/'cards.tavia'
        self.manifest=create_tavia(self.source,self.archive)
        self.m= self.manifest
    def ctx(self,op,scopes=('assets:ingest',),kind='service',**kw):
        return SimpleNamespace(body={'op':op,**kw},session_factory=self.Session,
             principal=SimpleNamespace(kind=kind,subject='test-uploader',scopes=scopes))
    def call(self,op,scopes=('assets:ingest',),kind='service',**kw):
        return h._dispatch(self.ctx(op,scopes,kind,**kw))
    def upload(self):
        self.assertTrue(self.call('begin',manifest=self.m)['ok'])
        for name in self.m['files']:
            b=(self.source/name).read_bytes()
            for offset in range(0,len(b),h.CHUNK_SIZE):
                chunk=b[offset:offset+h.CHUNK_SIZE]
                self.assertTrue(self.call('chunk',packId=self.m['id'],version=self.m['version'],name=name,offset=offset,contentBase64=base64.b64encode(chunk).decode())['ok'])
        return self.call('finalize',packId=self.m['id'],version=self.m['version'])
    def test_archive_build_unpack_and_reproducible(self):
        a=self.archive.read_bytes();create_tavia(self.source,self.archive);self.assertEqual(a,self.archive.read_bytes())
        target=self.base/'unpacked';self.assertEqual(unpack_tavia(self.archive,target),self.manifest)
    def test_manifest_traversal_rejected_before_upload(self):
        compromised=json.loads(json.dumps(self.m))
        compromised['files']={'../outside.png':'0'*64}
        self.assertEqual(self.call('begin',manifest=compromised)['reason'],'bad_manifest')
        self.assertFalse((self.base/'outside.png').exists())

    def test_forged_admin_body_cannot_publish(self):
        self.upload()
        self.assertEqual(self.call('publish',kind='user',scopes=('assets:publish',),isAdmin=True,packId=self.m['id'],version=self.m['version'])['reason'],'publisher_approval_required')

    def test_tavia_traversal_rejected(self):
        import zipfile
        b=self.base/'evil.tavia'
        with zipfile.ZipFile(b,'w') as z:z.writestr('../evil.png',b'a')
        with self.assertRaises(AssetError):unpack_tavia(b,self.base/'dest')
    def test_tavia_extra_content_rejected(self):
        import zipfile
        with zipfile.ZipFile(self.archive,'a') as z:z.writestr('bad.py','print(1)')
        with self.assertRaises(AssetError):unpack_tavia(self.archive,self.base/'dest')
    def test_authorization_fail_closed(self):
        self.assertFalse(self.call('begin',scopes=(),manifest=self.m)['ok'])
        self.assertFalse(self.call('begin',kind='user',manifest=self.m)['ok'])
        self.assertFalse(self.call('publish',packId=self.m['id'],version=self.m['version'])['ok'])
        self.assertFalse(self.call('catalog',scopes=())['ok'])
    def test_stage_publish_read_revoke(self):
        result=self.upload();self.assertEqual(result,{'ok':True,'status':'ready'})
        self.assertEqual(self.call('catalog',scopes=('assets:read',))['packs'],[])
        self.assertFalse(self.call('publish',packId=self.m['id'],version=self.m['version'])['ok'])
        self.assertTrue(self.call('publish',scopes=('assets:publish',),packId=self.m['id'],version=self.m['version'])['ok'])
        self.assertEqual(len(self.call('catalog',scopes=('assets:read',))['packs']),1)
        name=next(iter(self.m['files']))
        resource=self.call('resource',scopes=('assets:read',),packId=self.m['id'],version=self.m['version'],name=name,offset=0)
        self.assertTrue(resource['ok']);self.assertEqual(resource['sha256'],self.m['files'][name])
        self.assertFalse(self.call('begin',manifest=self.m)['ok'])
        self.assertTrue(self.call('revoke',scopes=('assets:publish',),packId=self.m['id'],version=self.m['version'])['ok'])
        self.assertEqual(self.call('catalog',scopes=('assets:read',))['packs'],[])
        self.assertFalse(self.call('resource',scopes=('assets:read',),packId=self.m['id'],version=self.m['version'],name=name,offset=0)['ok'])
    def test_incomplete_and_invalid_chunk(self):
        self.assertTrue(self.call('begin',manifest=self.m)['ok'])
        self.assertFalse(self.call('finalize',packId=self.m['id'],version=self.m['version'])['ok'])
        self.assertFalse(self.call('chunk',packId=self.m['id'],version=self.m['version'],name='bad',offset=0,contentBase64='YQ==')['ok'])
    def test_descriptor_contract_and_management(self):
        d=g.descriptor();self.assertIn('management.data',d['requires']);self.assertEqual(d['database']['backend'],'sqlite')
        self.assertEqual(d['database']['schemaVersion'],1)
        self.assertIn('asset-versions',d['management']['resources'])
        self.assertFalse('create' in d['resources']['asset-versions']['operations'])
        import subprocess
        subprocess.run([sys.executable,str(ROOT/'looprd'/'generate.py'),'--check'],check=True,capture_output=True)

if __name__=='__main__': unittest.main()
