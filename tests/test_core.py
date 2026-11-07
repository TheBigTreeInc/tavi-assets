import json, tempfile, unittest
from pathlib import Path
from tavi_assets.core import AssetManager, AssetError, validate
EXAMPLES=Path(__file__).resolve().parents[1]/'examples'
class TestAssets(unittest.TestCase):
 def test_install_restart_customize_update(self):
  with tempfile.TemporaryDirectory() as d:
   a=AssetManager(d); a.install(EXAMPLES/'cards-v1'); a.select('org.tavi.cards.standard','card.back','blue')
   b=AssetManager(d); self.assertIn(b'3455aa',b.resolve('org.tavi.cards.standard','card.back'))
   b.install(EXAMPLES/'cards-v2'); self.assertIn(b'3455aa',AssetManager(d).resolve('org.tavi.cards.standard','card.back'))
 def test_corrupt_update_keeps_previous(self):
  with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as bad:
   a=AssetManager(d); a.install(EXAMPLES/'cards-v1')
   import shutil
   shutil.copytree(EXAMPLES/'cards-v2',Path(bad)/'pack'); (Path(bad)/'pack'/'front.svg').write_text('corrupt')
   with self.assertRaises(AssetError): a.install(Path(bad)/'pack')
   self.assertEqual(a.state['installed']['org.tavi.cards.standard'],'0.1.1')
 def test_path_traversal(self):
  with tempfile.TemporaryDirectory() as d:
   import shutil
   shutil.copytree(EXAMPLES/'cards-v1',Path(d)/'pack')
   m=json.loads((Path(d)/'pack'/'manifest.json').read_text()); m['files']['../evil']='0'*64
   (Path(d)/'pack'/'manifest.json').write_text(json.dumps(m))
   with self.assertRaises(AssetError): validate(Path(d)/'pack')
if __name__=='__main__': unittest.main()
