"""Curated local demonstration catalog; not an authenticated remote repository."""
import json
from pathlib import Path

from .core import AssetError, IDENT, SEMVER, validate


class Catalog:
    def __init__(self, example_root, catalog_file=None):
        self.root = Path(example_root).resolve()
        self.path = Path(catalog_file) if catalog_file else self.root / "catalog.json"
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AssetError("invalid local catalog") from exc
        if data.get("schema") != "tavi.assets.catalog/v1" or not isinstance(data.get("items"), list):
            raise AssetError("unsupported local catalog")
        self.items = {}
        for item in data["items"]:
            if not isinstance(item, dict):
                raise AssetError("invalid catalog item")
            ident = item.get("id")
            if not isinstance(ident, str) or not IDENT.fullmatch(ident) or ident in self.items:
                raise AssetError("invalid or duplicate catalog ID")
            if not isinstance(item.get("title"), str) or not isinstance(item.get("summary"), str):
                raise AssetError("missing catalog presentation fields")
            price = item.get("priceGold")
            if type(price) is not int or price < 0:
                raise AssetError("invalid catalog price")
            versions = item.get("versions")
            if not isinstance(versions, list) or not versions:
                raise AssetError("empty catalog versions")
            seen = set()
            for release in versions:
                if not isinstance(release, dict):
                    raise AssetError("invalid release entry")
                version, source = release.get("version"), release.get("source")
                if not isinstance(version, str) or not SEMVER.fullmatch(version) or version in seen:
                    raise AssetError("invalid catalog version")
                seen.add(version)
                if not isinstance(source, str) or not source or "/" in source or "\\" in source or source in (".", ".."):
                    raise AssetError("invalid catalog source name")
                folder = self.root / source
                if not folder.resolve().is_relative_to(self.root) or folder.is_symlink():
                    raise AssetError("catalog source escapes root")
                manifest = validate(folder)
                if manifest["id"] != ident or manifest["version"] != version:
                    raise AssetError("catalog identity/version mismatch")
            self.items[ident] = item

    def item(self, ident):
        try:
            return self.items[ident]
        except (KeyError, TypeError) as exc:
            raise AssetError("unknown catalog item") from exc

    def latest(self, ident):
        return max(self.item(ident)["versions"], key=lambda r: tuple(map(int, r["version"].split("."))))

    def source(self, ident, version=None):
        release = self.latest(ident) if version is None else next(
            (r for r in self.item(ident)["versions"] if r["version"] == version), None)
        if not release:
            raise AssetError("unknown catalog release")
        folder = self.root / release["source"]
        # Check again: source content can change after catalog construction.
        manifest = validate(folder)
        if manifest["id"] != ident or manifest["version"] != release["version"]:
            raise AssetError("catalog source changed identity")
        return folder, manifest


class DenyPaidEntitlements:
    """Fail-closed development adapter. Free catalog items only."""
    def can_access(self, actor, pack_id, price_gold):
        return price_gold == 0


class NoPurchases:
    """There is no authenticated purchase API in this source preview."""
    def purchase(self, actor, sku, idempotency_key):
        raise AssetError("purchases unavailable; LoopRD/Wallet contracts not integrated")


class StoreService:
    def __init__(self, manager, catalog, entitlements=None, wallet=None):
        self.manager = manager
        self.catalog = catalog
        self.entitlements = entitlements if entitlements is not None else DenyPaidEntitlements()
        self.wallet = wallet if wallet is not None else NoPurchases()

    def describe(self, actor="local-preview"):
        installed = self.manager.list_installed()
        state = self.manager._load()
        output = []
        for item in self.catalog.items.values():
            ident = item["id"]
            current = installed.get(ident)
            latest = self.catalog.latest(ident)["version"]
            _, manifest = self.catalog.source(ident)
            output.append({
                "id": ident, "title": item["title"], "summary": item["summary"],
                "category": item.get("category", "Assets"), "priceGold": item["priceGold"],
                "latest": latest, "installed": current, "owned": bool(self.entitlements.can_access(actor, ident, item["priceGold"])),
                "updateAvailable": bool(current and tuple(map(int, latest.split("."))) > tuple(map(int, current.split(".")))),
                "preferences": state["preferences"].get(ident, {}),
                "resources": manifest["resources"],
                "objectCount": len(manifest.get("objects", {})),
                "collectionCount": len(manifest.get("collections", {})),
                "tags": manifest.get("tags", []),
                "display": manifest.get("display", {})
            })
        return output

    def install(self, actor, ident):
        item = self.catalog.item(ident)
        if not self.entitlements.can_access(actor, ident, item["priceGold"]):
            raise AssetError("pack requires server-authorized ownership")
        source, manifest = self.catalog.source(ident)
        return self.manager.install(source)

    def select(self, ident, capability, variant):
        self.catalog.item(ident)
        self.manager.select(ident, capability, variant)

    def uninstall(self, ident):
        self.catalog.item(ident)
        self.manager.uninstall(ident)

    def metadata(self, ident):
        """Catalog metadata preview only; NOT an authenticated host extension API."""
        self.catalog.item(ident)
        _, manifest = self.catalog.source(ident)
        from .metadata import public_object
        return {"schema": "tavi.assets.catalog-preview/v1", "packId": ident,
                "display": manifest.get("display", {}), "tags": manifest.get("tags", []),
                "taxonomy": manifest.get("taxonomy", {}),
                "collections": [{"id": key, **value} for key, value in sorted(manifest.get("collections", {}).items())],
                "objects": [public_object(key, value, set(manifest["resources"]))
                            for key, value in sorted(manifest.get("objects", {}).items())]}

    def preview(self, ident, capability, variant=None):
        _, manifest = self.catalog.source(ident)
        try:
            resource = manifest["resources"][capability]
        except (KeyError, TypeError) as exc:
            raise AssetError("unknown preview capability") from exc
        name = resource["default"]
        if variant is not None:
            try:
                name = resource["variants"][variant]
            except (KeyError, TypeError) as exc:
                raise AssetError("unknown preview variant") from exc
        from .core import MIME
        filename = self.catalog.source(ident)[0] / name
        return filename.read_bytes(), MIME[filename.suffix.lower()]
