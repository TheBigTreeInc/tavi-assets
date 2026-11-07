"""Crash boundary recovery and OS lock integration tests (native Windows still required)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tavi_assets.core import AssetError, AssetManager, _lock

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples'
ID = 'org.tavi.cards.standard'


class RecoveryTests(unittest.TestCase):
    def test_interrupted_stage_does_not_change_active_version_or_preference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = AssetManager(root)
            manager.install(EXAMPLES / 'cards-v1')
            manager.select(ID, 'card.back', 'blue')
            staged = root / 'packs' / ID / '.stage-abc123xy'
            staged.mkdir()
            (staged / 'partial.json').write_text('{')
            (root / '.registry-abc123xy').write_text('{')
            resumed = AssetManager(root)
            self.assertEqual(resumed.recovery['discardedStages'], 1)
            self.assertEqual(resumed.recovery['discardedRegistryTemps'], 1)
            self.assertFalse(staged.exists())
            self.assertEqual(resumed.list_installed()[ID], '0.1.1')
            self.assertIn(b'3455aa', resumed.resolve(ID, 'card.back'))
            self.assertEqual(AssetManager(root).recovery['discardedStages'], 0)

    def test_finalized_but_uncommitted_release_is_not_activated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            AssetManager(root).install(EXAMPLES / 'cards-v1')
            # Simulate process death after stage -> final rename, before registry swap.
            orphan = root / 'packs' / ID / '0.1.2'
            shutil.copytree(EXAMPLES / 'cards-v2', orphan)
            reopened = AssetManager(root)
            self.assertEqual(reopened.recovery['inactiveVersions'], 1)
            self.assertEqual(reopened.list_installed()[ID], '0.1.1')
            self.assertTrue(orphan.exists())
            reopened.install(EXAMPLES / 'cards-v2')
            self.assertEqual(AssetManager(root).list_installed()[ID], '0.1.2')

    def test_corrupt_registry_does_not_trigger_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = AssetManager(root)
            staged = root / 'packs' / ID / '.stage-abc123xy'
            staged.mkdir(parents=True)
            (root / 'registry.json').write_text('{invalid')
            with self.assertRaises(AssetError):
                AssetManager(root)
            self.assertTrue(staged.exists())  # fail closed before mutations

    def test_unsafe_staging_symlink_is_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            AssetManager(root)
            stage = root / 'packs' / ID / '.stage-abc123xy'
            stage.parent.mkdir(parents=True)
            target = Path(outside) / 'keep.txt'
            target.write_text('not an asset')
            try:
                stage.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('symlink unavailable under current privileges')
            with self.assertRaisesRegex(AssetError, 'unsafe staged'):
                AssetManager(root)
            self.assertTrue(target.exists())

    def test_unsafe_packs_root_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            try:
                (root / 'packs').symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('symlink unavailable under current privileges')
            with self.assertRaisesRegex(AssetError, 'packs cache'):
                AssetManager(root)

    def test_interprocess_lock_contention_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / '.registry.lock'
            code = ('import sys,time\n'
                    'sys.path.insert(0,sys.argv[1])\n'
                    'from pathlib import Path\n'
                    'from tavi_assets.core import _lock\n'
                    'with _lock(Path(sys.argv[2])):\n'
                    ' print("HELD",flush=True)\n'
                    ' time.sleep(3)\n')
            proc = subprocess.Popen([sys.executable, '-c', code, str(ROOT / 'src'), str(lock)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                ready = proc.stdout.readline().strip()
                if ready != 'HELD':
                    self.fail('lock child could not start: ' + proc.stderr.read())
                with self.assertRaisesRegex(AssetError, 'locked'):
                    with _lock(lock, timeout=0.15):
                        pass
            finally:
                if proc.poll() is None:
                    proc.terminate()
                proc.communicate(timeout=5)
            with _lock(lock, timeout=1):
                self.assertTrue(lock.is_file())

    def test_recovery_idempotent_and_does_not_remove_other_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m = AssetManager(root)
            unrelated = root / '.registry-human-notes'  # does not match managed temp name
            unrelated.write_text('preserve')
            (root / '.registry-abc123xy').write_text('incomplete')
            one = m.recover()
            two = m.recover()
            self.assertEqual(one['discardedRegistryTemps'], 1)
            self.assertEqual(two['discardedRegistryTemps'], 0)
            self.assertEqual(unrelated.read_text(), 'preserve')


    def test_cli_doctor_reports_discarded_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            AssetManager(root)
            (root / '.registry-abc123xy').write_text('incomplete')
            result = subprocess.run([sys.executable, str(ROOT / 'tools' / 'asset.py'),
                                     '--root', str(root), 'doctor'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['discardedRegistryTemps'], 1)
            self.assertFalse((root / '.registry-abc123xy').exists())

    def test_unsafe_lock_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            target = Path(outside) / 'preserve.json'
            target.write_text('preserve')
            try:
                (root / '.registry.lock').symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('symlink unavailable under current privileges')
            with self.assertRaisesRegex(AssetError, 'lock symlink'):
                AssetManager(root)
            self.assertEqual(target.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
