"""Regression for public content home: no network, no editor application changes."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tavi_assets.core import AssetError
from tavi_assets.blueprint_package import create_tavib, inspect_tavib
from tavi_assets.repository_index import build_index, verify_index, write_index, SOURCE_SCHEMA, INDEX_SCHEMA
from tavi_assets.tavia import create_tavia


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class BlueprintTests(unittest.TestCase):
    def setUp(self):
        self.context = tempfile.TemporaryDirectory()
        self.addCleanup(self.context.cleanup)
        self.root = Path(self.context.name)
        self.blueprint = self.root / 'blueprint.json'
        self.blueprint.write_text(json.dumps({'schema': 'tavix.studio.asset-blueprint/v1', 'groups': []}))
        self.output = self.root / 'blueprint.tavib'

    def create(self):
        return create_tavib(self.blueprint, self.output, 'tarot-standard-78', '1.0.0')

    def test_blueprint_roundtrip_and_reproducible(self):
        m = self.create()
        self.assertEqual(inspect_tavib(self.output), m)
        before = digest(self.output)
        self.create()
        self.assertEqual(digest(self.output), before)

    def test_readme_and_webp_preview(self):
        readme = self.root / 'README.md'
        readme.write_text('Designer guidance', encoding='utf-8')
        preview = self.root / 'sample.webp'
        preview.write_bytes(b'RIFF\x04\x00\x00\x00WEBP')
        m = create_tavib(self.blueprint, self.output, 'tarot-standard-78', '1.0.0', readme, [preview])
        self.assertIn('previews/sample.webp', m['files'])
        self.assertEqual(inspect_tavib(self.output), m)

    def test_blueprint_payload_version_must_be_explicit(self):
        self.blueprint.write_text('{"schema":"unexpected/v1"}')
        with self.assertRaises(AssetError):
            self.create()

    def test_reject_bad_package_identity(self):
        for ident, ver in [('A', '1.0.0'), ('foo/bar', '1.0.0'), ('good', '01.0.0'), ('good', '1.2.x')]:
            with self.subTest(ident=ident, version=ver), self.assertRaises(AssetError):
                create_tavib(self.blueprint, self.output, ident, ver)

    def test_reject_duplicate_preview_names(self):
        preview = self.root / 'a.webp'
        preview.write_bytes(b'RIFF\x04\x00\x00\x00WEBP')
        with self.assertRaises(AssetError):
            create_tavib(self.blueprint, self.output, 'good', '1.0.0', previews=[preview, preview])

    def test_reject_unapproved_preview_file_format(self):
        preview = self.root / 'a.webp'
        preview.write_bytes(b'not actually an image')
        with self.assertRaises(AssetError):
            create_tavib(self.blueprint, self.output, 'good', '1.0.0', previews=[preview])

    def _tamper(self, alter):
        self.create()
        with zipfile.ZipFile(self.output) as arc:
            entries = {n: arc.read(n) for n in arc.namelist()}
        alter(entries)
        with zipfile.ZipFile(self.output, 'w') as arc:
            for name, content in entries.items():
                arc.writestr(name, content)
        with self.assertRaises(AssetError):
            inspect_tavib(self.output)

    def test_reject_hash_mismatch(self):
        self._tamper(lambda entries: entries.update({'blueprint.json': b'{}'}))

    def test_reject_path_traversal_entry(self):
        self._tamper(lambda entries: entries.update({'../escape': b'bad'}))

    def test_reject_unlisted_executable(self):
        self._tamper(lambda entries: entries.update({'run.js': b'alert(1)'}))

    def test_reject_missing_manifest_file(self):
        self._tamper(lambda entries: entries.pop('manifest.json'))

    def test_reject_symlink(self):
        self.create()
        with zipfile.ZipFile(self.output) as arc:
            entries = [(entry.filename, arc.read(entry.filename)) for entry in arc.infolist()]
        with zipfile.ZipFile(self.output, 'w') as arc:
            for name, data in entries:
                if name == 'blueprint.json':
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = 0o120777 << 16
                    arc.writestr(info, data)
                else:
                    arc.writestr(name, data)
        with self.assertRaises(AssetError):
            inspect_tavib(self.output)


class RepositoryIndexTests(unittest.TestCase):
    def setUp(self):
        self.context = tempfile.TemporaryDirectory()
        self.addCleanup(self.context.cleanup)
        self.root = Path(self.context.name)
        self.source = {'schema': SOURCE_SCHEMA, 'schematics': [], 'packs': []}
        self.save_source()
        write_index(self.root)

    def save_source(self):
        (self.root / 'catalog.source.json').write_text(json.dumps(self.source))

    def make_blueprint(self, ident='tarot-standard-78', version='1.0.0'):
        source = self.root / 'designer.json'
        source.write_text(json.dumps({'schema': 'tavix.studio.asset-blueprint/v1', 'resources': []}))
        out = self.root / 'schematics' / ident / version / 'blueprint.tavib'
        create_tavib(source, out, ident, version)
        return out

    def make_pack(self):
        ident, version = 'org.tavi.cards.standard', '0.1.1'
        out = self.root / 'packs' / ident / version / 'package.tavia'
        create_tavia(ROOT / 'examples' / 'cards-v1', out)
        return out

    def approved(self, kind, ident, version, artifact, **kw):
        entry = {'id': ident, 'version': version,
                 'artifact': artifact.relative_to(self.root).as_posix(),
                 'sha256': digest(artifact), 'visibility': 'public', 'status': 'approved',
                 'approvalReference': 'review/QA-0001', **kw}
        self.source[kind].append(entry)
        self.save_source()
        return entry

    def test_empty_canonical_catalog_is_valid(self):
        self.assertEqual(verify_index(self.root)['schema'], INDEX_SCHEMA)

    def test_public_approved_blueprint_and_pack(self):
        blueprint = self.make_blueprint()
        self.approved('schematics', 'tarot-standard-78', '1.0.0', blueprint)
        pack = self.make_pack()
        self.approved('packs', 'org.tavi.cards.standard', '0.1.1', pack, blueprintId='tarot-standard-78')
        catalog = build_index(self.root)
        self.assertEqual(len(catalog['packs']), 1)
        self.assertEqual(len(catalog['schematics']), 1)
        self.assertEqual(catalog['packs'][0]['compatibility'], {'host': 'tavi-assets/v1'})
        self.assertEqual(catalog['packs'][0]['blueprintId'], 'tarot-standard-78')
        write_index(self.root)
        self.assertEqual(verify_index(self.root), catalog)

    def test_stale_catalog_detected(self):
        bp = self.make_blueprint()
        self.approved('schematics', 'tarot-standard-78', '1.0.0', bp)
        with self.assertRaises(AssetError):
            verify_index(self.root)

    def test_draft_never_visible_in_catalog(self):
        self.source['schematics'].append({'id': 'draft', 'version': '1.0.0', 'artifact': 'schematics/draft/1.0.0/blueprint.tavib', 'visibility': 'public', 'status': 'draft'})
        self.save_source()
        self.assertFalse(build_index(self.root)['schematics'])

    def test_restricted_approved_pack_fails_closed(self):
        p = self.make_pack()
        entry = self.approved('packs', 'org.tavi.cards.standard', '0.1.1', p)
        entry['visibility'] = 'restricted'
        self.save_source()
        with self.assertRaises(AssetError):
            build_index(self.root)

    def test_forged_approval_status_is_not_accepted_without_ref(self):
        p = self.make_blueprint()
        entry = self.approved('schematics', 'tarot-standard-78', '1.0.0', p)
        del entry['approvalReference']
        self.save_source()
        with self.assertRaises(AssetError):
            build_index(self.root)

    def test_changed_archive_rejected_after_approval(self):
        p = self.make_blueprint()
        self.approved('schematics', 'tarot-standard-78', '1.0.0', p)
        with p.open('ab') as f:
            f.write(b'modified')
        with self.assertRaises(AssetError):
            build_index(self.root)

    def test_wrong_path_rejected(self):
        p = self.make_blueprint()
        entry = self.approved('schematics', 'tarot-standard-78', '1.0.0', p)
        entry['artifact'] = '../blueprint.tavib'
        self.save_source()
        with self.assertRaises(AssetError):
            build_index(self.root)

    def test_duplicate_rejected(self):
        p = self.make_blueprint()
        entry = self.approved('schematics', 'tarot-standard-78', '1.0.0', p)
        self.source['schematics'].append(dict(entry))
        self.save_source()
        with self.assertRaises(AssetError):
            build_index(self.root)

    def test_blueprint_identity_mismatch(self):
        p = self.make_blueprint('other-id')
        entry = self.approved('schematics', 'other-id', '1.0.0', p)
        entry['id'] = 'different-id'
        entry['artifact'] = 'schematics/different-id/1.0.0/blueprint.tavib'
        self.save_source()
        with self.assertRaises(AssetError):
            build_index(self.root)

    def test_public_pack_manifest_tamper_rejected(self):
        p = self.make_pack()
        self.approved('packs', 'org.tavi.cards.standard', '0.1.1', p)
        with zipfile.ZipFile(p, 'a') as arc:
            arc.writestr('evil.txt', 'bad')
        self.source['packs'][0]['sha256'] = digest(p)
        self.save_source()
        with self.assertRaises(AssetError):
            build_index(self.root)

if __name__ == '__main__':
    unittest.main()
