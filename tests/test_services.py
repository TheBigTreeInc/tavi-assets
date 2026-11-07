import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from tavi_assets.catalog import Catalog, StoreService, NoPurchases
from tavi_assets.core import AssetManager, AssetError, validate
from tavi_assets.host import HostAssetService, HostGrant

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
ID = "org.tavi.cards.standard"


class AllowForTests:
    # Only tests may inject this in-memory entitlement stand-in.
    def can_access(self, actor, pack_id, price_gold):
        return actor == "test-owner" and pack_id == ID


class TestServices(unittest.TestCase):
    def test_catalog_install_and_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = StoreService(AssetManager(tmp), Catalog(EXAMPLES))
            before = service.describe()[0]
            self.assertTrue(before["owned"])
            self.assertEqual(before["priceGold"], 0)
            self.assertIsNone(before["installed"])
            service.install("local-preview", ID)
            after = service.describe()[0]
            self.assertEqual(after["installed"], "0.1.2")
            self.assertFalse(after["updateAvailable"])
            service.select(ID, "card.back", "blue")
            self.assertEqual(service.describe()[0]["preferences"]["card.back"], "blue")

    def test_uninstall_deletes_files_preserves_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = StoreService(AssetManager(tmp), Catalog(EXAMPLES))
            s.install("local-preview", ID)
            s.select(ID, "card.back", "blue")
            s.uninstall(ID)
            self.assertFalse((Path(tmp) / "packs" / ID).exists())
            self.assertEqual(s.manager.list_installed(), {})
            self.assertEqual(s.manager._load()["preferences"][ID]["card.back"], "blue")
            s.install("local-preview", ID)
            self.assertIn(b"3455aa", s.manager.resolve(ID, "card.back"))

    def test_paid_needs_entitlement_and_purchase_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(EXAMPLES / "cards-v1", root / "cards-v1")
            (root / "catalog.json").write_text(json.dumps({
                "schema": "tavi.assets.catalog/v1",
                "items": [{"id": ID, "title": "Premium test pack", "summary": "Test only",
                           "priceGold": 25, "versions": [{"version": "0.1.1", "source": "cards-v1"}]}]}))
            catalog = Catalog(root)
            normal = StoreService(AssetManager(root / "cache"), catalog)
            self.assertFalse(normal.describe()[0]["owned"])
            with self.assertRaisesRegex(AssetError, "server-authorized"):
                normal.install("local-preview", ID)
            with self.assertRaisesRegex(AssetError, "unavailable"):
                NoPurchases().purchase("local-preview", "premium", "request-1")
            mock = StoreService(AssetManager(root / "cache"), catalog, entitlements=AllowForTests())
            self.assertFalse(mock.describe(actor="other")[0]["owned"])
            mock.install("test-owner", ID)
            self.assertIn(ID, mock.manager.list_installed())

    def test_host_authorization_for_pack_and_capability(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AssetManager(tmp)
            manager.install(EXAMPLES / "cards-v1")
            host = HostAssetService(manager, {
                "trusted-klondike-session": HostGrant(frozenset({ID}), frozenset({"card.back"}))
            })
            data = host.resolve("trusted-klondike-session", ID, "card.back")
            self.assertEqual(data["content_type"], "image/svg+xml")
            self.assertNotIn("path", data)
            for args in [("wrong-client", ID, "card.back"),
                         ("trusted-klondike-session", ID, "card.front.ace-spades"),
                         ("trusted-klondike-session", "another.pack", "card.back")]:
                with self.assertRaisesRegex(AssetError, "denied"):
                    host.resolve(*args)

    def test_catalog_rejects_wrong_source_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(EXAMPLES / "cards-v1", root / "cards-v1")
            (root / "catalog.json").write_text(json.dumps({
                "schema": "tavi.assets.catalog/v1", "items": [{
                    "id": ID, "title": "Cards", "summary": "Example", "priceGold": 0,
                    "versions": [{"version": "99.0.0", "source": "cards-v1"}]
                }]}))
            with self.assertRaisesRegex(AssetError, "mismatch"):
                Catalog(root)

    def test_stale_manager_instances_do_not_lose_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = AssetManager(tmp)
            first.install(EXAMPLES / "cards-v1")
            second = AssetManager(tmp)
            first.select(ID, "card.back", "blue")
            second.select(ID, "card.back", "green")
            self.assertEqual(AssetManager(tmp)._load()["preferences"][ID]["card.back"], "green")
            self.assertEqual(first._load()["preferences"][ID]["card.back"], "green")

    def test_upgrade_keeps_selected_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AssetManager(tmp)
            manager.install(EXAMPLES / "cards-v1")
            manager.select(ID, "card.back", "blue")
            manager.install(EXAMPLES / "cards-v2")
            fresh = AssetManager(tmp)
            self.assertEqual(fresh._load()["installed"][ID], "0.1.2")
            self.assertIn(b"3455aa", fresh.resolve(ID, "card.back"))

    def test_downgrade_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = AssetManager(tmp)
            manager.install(EXAMPLES / "cards-v2")
            with self.assertRaisesRegex(AssetError, "downgrade"):
                manager.install(EXAMPLES / "cards-v1")

    def test_immutable_version_replaced_data_denied(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as edit:
            manager = AssetManager(tmp)
            manager.install(EXAMPLES / "cards-v1")
            source = Path(edit) / "pack"
            shutil.copytree(EXAMPLES / "cards-v1", source)
            file = source / "back-green.svg"
            file.write_bytes(file.read_bytes().replace(b"green", b"green"))
            # Valid but different byte-level version can't replace an installed version.
            modified = file.read_bytes().replace(b"#", b"#") + b"\n"
            file.write_bytes(modified)
            manifest = json.loads((source / "manifest.json").read_text())
            import hashlib
            manifest["files"]["back-green.svg"] = hashlib.sha256(modified).hexdigest()
            (source / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(AssetError, "immutable"):
                manager.install(source)

    def test_corrupt_installed_content_not_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = AssetManager(tmp)
            a.install(EXAMPLES / "cards-v1")
            (Path(tmp) / "packs" / ID / "0.1.1" / "back-blue.svg").write_text("evil")
            with self.assertRaisesRegex(AssetError, "integrity"):
                a.resolve(ID, "card.back")


if __name__ == "__main__":
    unittest.main()
