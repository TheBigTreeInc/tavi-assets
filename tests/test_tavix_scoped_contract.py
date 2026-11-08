"""Author-side no-extra-dependency source checks for TaviX grant integration."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TaviXScopedGrantContractTests(unittest.TestCase):
    def test_scoped_grant_contract_is_not_a_wallet_or_entitlement(self):
        contract = json.loads((ROOT / 'contracts/tavi-assets-tavix-grant-adapter-v1.json').read_text())
        self.assertEqual(contract['tavixProjection'], 'tavix.asset-grants/v1')
        self.assertFalse(contract['compatibility']['prefixOrWildcardEscalation'])
        self.assertIn('not', contract['trustBoundary'].lower())

    def test_reference_manifest_contains_explicit_pack_only(self):
        fixture = json.loads((ROOT / 'examples/developer/tavix-011-asset-consumer.json').read_text())
        self.assertEqual(fixture['schema'], 'tavi.extension/v1')
        self.assertTrue(fixture['assetDependencies'])
        self.assertTrue(all('packId' in d and 'capabilities' in d for d in fixture['assetDependencies']))
        self.assertNotIn('grants', fixture)

    def test_workboard_preserves_old_reviews_and_new_grouping_gate(self):
        board = json.loads((ROOT / '.ziprunner-workboard-update.json').read_text())
        self.assertIn('TA-022', {x['id'] for x in board['implemented']})
        remains = {x['id'] for x in board['remaining']}
        self.assertTrue({'TA-023', 'TA-012', 'define-next-pass', 'TA-016'} <= remains)

    def test_architecture_references_owned_validator(self):
        model = (ROOT / 'docs/architecture/workspace.dsl').read_text()
        self.assertIn('TaviX Scoped Grant Validator', model)
        self.assertIn('portable_service/grants.mjs', model)
        self.assertIn('portableBridge -> grantValidator', model)


if __name__ == '__main__':
    unittest.main()
