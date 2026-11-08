"""Dependency proposal source invariants; no imported jsonschema dependency on Windows."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestDependencyContract(unittest.TestCase):
    def test_proposals_versioned_and_no_wallet_authority(self):
        schema = json.loads((ROOT / "contracts/tavi-assets-requirements-v1.schema.json").read_text())
        self.assertEqual(schema["properties"]["schema"]["const"], "tavi.assets.requirements/v1")
        feature = schema["$defs"]["feature"]
        self.assertEqual(set(feature["required"]), {"id", "required", "optional", "fallback"})
        self.assertFalse(feature["additionalProperties"])
        self.assertNotIn("price", schema["$defs"]["dependency"]["properties"])
        self.assertNotIn("rarity", schema["$defs"]["dependency"]["properties"])

    def test_fixtures_and_status_contract(self):
        for name in ("klondike", "companion"):
            item = json.loads((ROOT / f"examples/developer/{name}-asset-requirements.json").read_text())
            self.assertEqual(item["schema"], "tavi.assets.requirements/v1")
            self.assertTrue(item["features"])
            self.assertTrue(all(f["fallback"] in ("none", "bundled") for f in item["features"]))
        contract = json.loads((ROOT / "contracts/tavi-assets-consumer-v1.json").read_text())
        self.assertEqual(contract["dependencies"]["feature"], "tavi.assets.dependencies/v1")
        self.assertIn("assets.dependencies.status", {entry["method"] for entry in contract["requests"]})

    def test_api_never_allows_requirement_or_grant_params(self):
        data = json.loads((ROOT / "contracts/tavi-assets-host-request-v1.schema.json").read_text())
        methods = [x for x in data["oneOf"] if x.get("properties", {}).get("method", {}).get("const") == "assets.dependencies.status"]
        self.assertEqual(len(methods), 1)
        self.assertEqual(methods[0]["properties"]["params"]["maxProperties"], 0)
        self.assertFalse(methods[0]["properties"]["params"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
