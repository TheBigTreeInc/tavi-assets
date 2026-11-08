"""Source-level developer contract, README and marketplace boundary checks."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tavi_assets.metadata import validate_metadata, public_object


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class DeveloperContractTests(unittest.TestCase):
    def test_evergreen_root_readme_and_changelog(self):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        changes = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('# Tavi Assets\n'))
        self.assertIsNone(re.search(r'^##\s+0\.\d+\.\d+', text, re.MULTILINE))
        self.assertNotIn('77/77', text)
        self.assertNotIn('TA-019', text)
        self.assertIn('docs/developer-guide.adoc', text)
        self.assertIn('CHANGELOG.md', text)
        self.assertIn('No', text)
        self.assertIn('## 0.1.7', changes)
        self.assertIn('## 0.1.6', changes)
        self.assertTrue((ROOT / 'docs/developer-guide.adoc').is_file())

    def test_host_methods_declared_and_not_wallet_methods(self):
        contract = load('contracts/tavi-assets-consumer-v1.json')
        schema = load('contracts/tavi-assets-host-request-v1.schema.json')
        names = {entry['method'] for entry in contract['requests']}
        declared = {branch['properties']['method']['const'] for branch in schema['oneOf']}
        expected = {'assets.packs.list', 'assets.objects.discover', 'assets.composition.resolve'}
        self.assertTrue(expected.issubset(names & declared))
        self.assertTrue(all(not k.startswith('wallet.') for k in names))
        sdk = (ROOT / 'sdk/client.mjs').read_text(encoding='utf-8')
        for marker in ('listPacks:', 'discoverObjects:', 'resolveComposition:'):
            self.assertIn(marker, sdk)
        self.assertNotIn('purchase:', sdk)
        self.assertEqual(contract['status'], 'proposed-not-implemented-in-Tavi')

    def test_rarity_optional_not_implied_common_for_object(self):
        m = load('examples/storybook-decks/manifest.json')
        example = next(iter(m['objects']))
        for obj in m['objects'].values():
            obj.pop('rarity', None)
        self.assertTrue(validate_metadata(m))
        public = public_object(example, m['objects'][example], set(m['resources']))
        self.assertNotIn('rarity', public)
        self.assertNotIn('rarity', m['objects'][example])

    def test_customization_bundle_is_not_authorization(self):
        schema = load('contracts/tavi-assets-customization-bundle-v1.schema.json')
        example = load('examples/developer/customization-bundle.json')
        self.assertEqual(schema['properties']['schema']['const'], example['schema'])
        slots = example['slots']
        self.assertEqual(len(slots), 2)
        self.assertEqual(len({slot['slot'] for slot in slots}), 2)
        self.assertNotIn('price', example)
        self.assertNotIn('entitlements', example)
        self.assertNotIn('wallet', example)
        self.assertTrue(all({'slot','packId','capability'} <= set(s) for s in slots))

    def test_store_offer_is_display_only_not_wallet_grant(self):
        schema = load('contracts/tavi-assets-store-offer-v1.schema.json')
        example = load('examples/developer/store-offer-preview.json')
        self.assertEqual(schema['properties']['schema']['const'], example['schema'])
        self.assertIn('displayGoldPrice', example)
        self.assertNotIn('purchaseAuthorized', schema['properties'])
        self.assertNotIn('owned', schema['properties'])
        self.assertNotIn('spendableGold', schema['properties'])
        self.assertIn('never authorize', schema['properties']['displayGoldPrice']['description'])

    def test_proposal_schemas_validate_when_jsonschema_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('Optional JSON Schema package absent; independent conformance check not run')
        for kind, source in [('customization-bundle','customization-bundle'),('store-offer','store-offer-preview')]:
            schema = load(f'contracts/tavi-assets-{kind}-v1.schema.json')
            fixture = load(f'examples/developer/{source}.json')
            with self.subTest(kind=kind):
                jsonschema.Draft202012Validator.check_schema(schema)
                jsonschema.validate(fixture,schema)
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate({**fixture,'purchaseAuthorized':True},schema)

    def test_host_schema_rejects_privilege_input_when_jsonschema_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('Optional JSON Schema package absent')
        schema = load('contracts/tavi-assets-host-request-v1.schema.json')
        for request in [
            {'method':'assets.packs.list','params':{}},
            {'method':'assets.objects.discover','params':{'kind':'playing-card','limit':20}},
            {'method':'assets.composition.resolve','params':{'components':[{'slot':'face','packId':'org.tavi.cards.standard','capability':'card.back'}]}}
        ]:
            with self.subTest(request=request['method']):
                jsonschema.validate(request,schema)
                malicious={'method':request['method'],'params':{**request['params'],'callerId':'elevated'}}
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(malicious,schema)

if __name__ == '__main__':
    unittest.main()
