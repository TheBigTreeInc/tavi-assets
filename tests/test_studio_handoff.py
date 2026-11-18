import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from tavi_assets.studio_handoff import make_submission, validate_submission

class StudioSubmissionTests(unittest.TestCase):
    def test_staging_only_and_digest(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"cards.tavia"; p.write_bytes(b"test pack")
            result=make_submission(p,"org.example.cards","1.2.3")
            self.assertEqual(validate_submission(result),result)
            self.assertEqual(result["destination"],"staging")
            with self.assertRaises(ValueError):make_submission(p,"org.example.cards","1.2.3","published")
    def test_reject_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"cards.tavia";p.write_bytes(b"test")
            data=make_submission(p,"org.example.cards","1.0.0")
            for change in ({"requiresHostApproval":False},{"operation":"publish"},{"archiveBytes":True},{"extra":"admin"}):
                candidate={**data,**change}
                with self.assertRaises(ValueError):validate_submission(candidate)
    def test_reject_bad_path(self):
        with self.assertRaises(ValueError):make_submission("missing.tavia","org.example","1.0.0")
if __name__=="__main__":unittest.main()
