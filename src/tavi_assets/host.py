"""Proposed restricted host-side adapter; NOT an implemented TaviX wire method.

Production host MUST derive the trusted caller and grants from its own authenticated
extension session. It MUST NOT read caller IDs/grants out of extension messages.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from .core import AssetError
from .metadata import public_object


@dataclass(frozen=True)
class HostGrant:
    """A trusted Tavi host creates grants from the authenticated extension session."""
    packs: frozenset[str]
    capabilities: frozenset[str]
    can_customize: bool = False


class HostAssetService:
    def __init__(self, manager, trusted_grants):
        self.manager = manager
        self.grants = dict(trusted_grants)

    def _authorized(self, caller, pack_id):
        grant = self.grants.get(caller)
        if grant is None or pack_id not in grant.packs:
            raise AssetError("host access denied")
        return grant, self.manager.manifest_for(pack_id)

    def describe(self, trusted_caller_id, pack_id):
        grant, manifest = self._authorized(trusted_caller_id, pack_id)
        return {"schema": "tavi.assets.pack-info/v1", "packId": pack_id,
                "version": manifest["version"], "type": manifest["type"],
                "display": manifest.get("display", {}), "tags": list(manifest.get("tags", [])),
                "taxonomy": manifest.get("taxonomy", {}),
                "capabilities": sorted(set(manifest["resources"]) & grant.capabilities),
                "objectCount": len(manifest.get("objects", {})),
                "collectionCount": len(manifest.get("collections", {}))}

    def list_objects(self, trusted_caller_id, pack_id, *, kind=None, rarity=None, tags=(), offset=0, limit=100):
        grant, manifest = self._authorized(trusted_caller_id, pack_id)
        if not isinstance(tags, (list, tuple)) or len(tags) > 32 or not all(isinstance(tag, str) for tag in tags):
            raise AssetError("invalid metadata filter")
        if kind is not None and not isinstance(kind, str) or rarity is not None and not isinstance(rarity, str):
            raise AssetError("invalid metadata filter")
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise AssetError("invalid pagination")
        matches = [(key, obj) for key, obj in sorted(manifest.get("objects", {}).items())
                   if (kind is None or obj["kind"] == kind)
                   and (rarity is None or obj.get("rarity") == rarity)
                   and set(tags).issubset(obj.get("tags", []))]
        page = matches[offset:offset + limit]
        next_offset = offset + limit if offset + limit < len(matches) else None
        return {"schema": "tavi.assets.object-list/v1", "packId": pack_id,
                "version": manifest["version"], "total": len(matches), "nextOffset": next_offset,
                "items": [public_object(key, obj, grant.capabilities) for key, obj in page]}

    def get_object(self, trusted_caller_id, pack_id, object_id):
        grant, manifest = self._authorized(trusted_caller_id, pack_id)
        obj = manifest.get("objects", {}).get(object_id) if isinstance(object_id, str) else None
        if obj is None:
            raise AssetError("unknown object")
        return {"schema": "tavi.assets.object/v1", "packId": pack_id,
                "version": manifest["version"],
                "object": public_object(object_id, obj, grant.capabilities)}

    def list_collections(self, trusted_caller_id, pack_id, *, kind=None):
        _, manifest = self._authorized(trusted_caller_id, pack_id)
        if kind is not None and not isinstance(kind, str):
            raise AssetError("invalid collection filter")
        return {"schema": "tavi.assets.collection-list/v1", "packId": pack_id,
                "version": manifest["version"],
                "items": [{"id": key, "kind": value["kind"], "name": value["name"],
                           "tags": value.get("tags", []), "objectCount": len(value["entries"])}
                          for key, value in sorted(manifest.get("collections", {}).items())
                          if kind is None or value["kind"] == kind]}

    def get_collection(self, trusted_caller_id, pack_id, collection_id):
        _, manifest = self._authorized(trusted_caller_id, pack_id)
        collection = manifest.get("collections", {}).get(collection_id) if isinstance(collection_id, str) else None
        if collection is None:
            raise AssetError("unknown collection")
        return {"schema": "tavi.assets.collection/v1", "packId": pack_id,
                "version": manifest["version"], "id": collection_id,
                "kind": collection["kind"], "name": collection["name"],
                "description": collection.get("description", ""),
                "tags": collection.get("tags", []), "entries": collection["entries"]}

    def preferences(self, trusted_caller_id, pack_id):
        grant, manifest = self._authorized(trusted_caller_id, pack_id)
        current = self.manager._load()["preferences"].get(pack_id, {})
        return {"schema": "tavi.assets.preferences/v1", "packId": pack_id,
                "items": [{"capability": key, "available": sorted(value.get("variants", {})),
                           "selected": current.get(key) if current.get(key) in value.get("variants", {}) else None}
                          for key, value in sorted(manifest["resources"].items())
                          if key in grant.capabilities]}

    def select(self, trusted_caller_id, pack_id, capability, variant):
        grant, _ = self._authorized(trusted_caller_id, pack_id)
        if not grant.can_customize or capability not in grant.capabilities:
            raise AssetError("host customization denied")
        # Caller session is trusted; production host additionally owns consent/UI policy.
        self.manager.select(pack_id, capability, variant)
        return self.preferences(trusted_caller_id, pack_id)

    def resolve(self, trusted_caller_id, pack_id, capability):
        grant, _ = self._authorized(trusted_caller_id, pack_id)
        if capability not in grant.capabilities:
            raise AssetError("host access denied")
        # No paths, directory enumeration or unrestricted raw file API.
        return self.manager.resolved(pack_id, capability)

    def dispatch(self, trusted_caller_id, method, params):
        """Demo-only named host contract dispatcher, with strict request shape.

        Caller identity is a separate trusted argument. Unknown methods or
        unapproved payload keys fail closed, including callerId/path overrides.
        Tavi must own any real postMessage integration independently.
        """
        requests = {
            "assets.describe": ({"packId"}, set()),
            "assets.objects.list": ({"packId"}, {"kind", "rarity", "tags", "offset", "limit"}),
            "assets.objects.get": ({"packId", "objectId"}, set()),
            "assets.collections.list": ({"packId"}, {"kind"}),
            "assets.collections.get": ({"packId", "collectionId"}, set()),
            "assets.preferences.get": ({"packId"}, set()),
            "assets.preferences.set": ({"packId", "capability", "variant"}, set()),
            "assets.resolve": ({"packId", "capability"}, set()),
        }
        if not isinstance(method, str) or method not in requests or not isinstance(params, dict):
            raise AssetError("unsupported host assets request")
        required, optional = requests[method]
        if not required.issubset(params) or set(params) - required - optional:
            raise AssetError("invalid or unauthorized host request fields")
        pack = params["packId"]
        if method == "assets.describe":
            return self.describe(trusted_caller_id, pack)
        if method == "assets.objects.list":
            return self.list_objects(trusted_caller_id, pack,
                                     **{k:v for k,v in params.items() if k != "packId"})
        if method == "assets.objects.get":
            return self.get_object(trusted_caller_id, pack, params["objectId"])
        if method == "assets.collections.list":
            return self.list_collections(trusted_caller_id, pack, kind=params.get("kind"))
        if method == "assets.collections.get":
            return self.get_collection(trusted_caller_id, pack, params["collectionId"])
        if method == "assets.preferences.get":
            return self.preferences(trusted_caller_id, pack)
        if method == "assets.preferences.set":
            return self.select(trusted_caller_id, pack, params["capability"], params["variant"])
        return self.resolve_wire(trusted_caller_id, pack, params["capability"])

    def resolve_wire(self, trusted_caller_id, pack_id, capability):
        """Bounded JSON transport proposal; not a live TaviX bridge."""
        result = self.resolve(trusted_caller_id, pack_id, capability)
        if len(result["bytes"]) > 2 * 1024 * 1024:
            raise AssetError("resource too large for inline host transport")
        return {"schema": "tavi.assets.resource/v1", "packId": pack_id,
                "version": result["version"], "capability": capability,
                "contentType": result["content_type"], "encoding": "base64",
                "data": base64.b64encode(result["bytes"]).decode("ascii"),
                "selected": result["selected"]}
