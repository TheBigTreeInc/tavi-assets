"""Portable, declarative object/collection metadata for data-only asset packs.

No metadata field can carry executable behavior, an entitlement, an unvalidated
resource path, a server purchase instruction or a host caller identity.
"""
from __future__ import annotations

import json
import re

from .core import AssetError

MAX_OBJECTS = 2048
MAX_COLLECTIONS = 256
MAX_ENTRIES = 512
MAX_TAGS = 32
TOKEN = re.compile(r"^[a-z][a-z0-9._-]{0,126}$", re.ASCII)
UNSAFE_JS_KEYS = {"__proto__", "constructor", "prototype"}
DEFAULT_RARITIES = {"common", "uncommon", "rare", "epic", "legendary", "unique"}


def _token(value, label):
    if not isinstance(value, str) or not TOKEN.fullmatch(value) or value in UNSAFE_JS_KEYS:
        raise AssetError(f"invalid {label}")
    return value


def _text(value, label, max_length=160):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length or any(ord(c) < 32 for c in value):
        raise AssetError(f"invalid {label}")
    return value


def _tags(tags):
    if not isinstance(tags, list) or len(tags) > MAX_TAGS:
        raise AssetError("invalid object tags")
    result = [_token(tag, "tag") for tag in tags]
    if len(result) != len(set(result)):
        raise AssetError("duplicate tags")
    return result


def _data(value, depth=0):
    """Constrain arbitrary descriptive attributes to portable non-executable JSON."""
    if depth > 5:
        raise AssetError("attribute nesting too deep")
    if value is None or isinstance(value, (str, bool)) or type(value) in (int, float):
        if isinstance(value, str) and (len(value) > 256 or any(ord(c) < 32 for c in value)):
            raise AssetError("invalid attribute text")
        if type(value) is float and (value != value or abs(value) == float("inf")):
            raise AssetError("non-finite attribute number")
        return
    if isinstance(value, list):
        if len(value) > 64:
            raise AssetError("attribute list too long")
        for child in value:
            _data(child, depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 64:
            raise AssetError("too many attribute keys")
        for key, child in value.items():
            _token(key, "attribute key")
            _data(child, depth + 1)
        return
    raise AssetError("unsupported attribute value")


MODIFIER_PROFILE = "tavi.cards.modifiers.v1"
ALLOWED_TRIGGERS = {"hand.scored", "card.played", "round.started", "round.ended"}
ALLOWED_OPERATIONS = {"chips.add", "mult.add", "mult.multiply", "draw.add", "discard.add"}
ALLOWED_PREDICATES = {"equals", "at-least", "contains"}


def _modifiers(modifiers):
    """Validate *non-executable* game-rule declarations; game owns interpreter."""
    if not isinstance(modifiers, list) or len(modifiers) > 8:
        raise AssetError("invalid modifiers")
    for block in modifiers:
        if not isinstance(block, dict) or set(block) - {"profile", "trigger", "conditions", "effects"}:
            raise AssetError("invalid modifier block")
        if block.get("profile") != MODIFIER_PROFILE or block.get("trigger") not in ALLOWED_TRIGGERS:
            raise AssetError("unknown modifier profile or trigger")
        conditions = block.get("conditions", [])
        if not isinstance(conditions, list) or len(conditions) > 8:
            raise AssetError("invalid modifier conditions")
        for c in conditions:
            if not isinstance(c, dict) or set(c) != {"field", "operator", "value"}:
                raise AssetError("invalid modifier condition")
            _token(c["field"], "condition field")
            if c["operator"] not in ALLOWED_PREDICATES:
                raise AssetError("unsupported predicate")
            if not (isinstance(c["value"], str) and TOKEN.fullmatch(c["value"]) or
                    type(c["value"]) is int and 0 <= c["value"] <= 1000):
                raise AssetError("invalid condition value")
        effects = block.get("effects")
        if not isinstance(effects, list) or not 1 <= len(effects) <= 8:
            raise AssetError("invalid effects")
        for e in effects:
            if not isinstance(e, dict) or set(e) != {"op", "value"}:
                raise AssetError("invalid effect declaration")
            if e["op"] not in ALLOWED_OPERATIONS or type(e["value"]) not in (int, float):
                raise AssetError("unsupported effect operator or value")
            value = e["value"]
            if value != value or not (-1000 <= value <= 1000):
                raise AssetError("invalid effect magnitude")
            if e["op"] == "mult.multiply" and not 0 <= value <= 100:
                raise AssetError("invalid multiplier factor")


def validate_metadata(manifest):
    """Validate optional object graph; v1 packs without metadata remain valid."""
    if not set(manifest).issubset({"schema", "id", "version", "type", "compatibility", "files",
                                    "resources", "display", "tags", "taxonomy", "objects", "collections"}):
        raise AssetError("unknown manifest field")
    display = manifest.get("display", {})
    if not isinstance(display, dict) or set(display) - {"name", "description", "style"}:
        raise AssetError("invalid pack display")
    if "name" in display:
        _text(display["name"], "pack name")
    if "description" in display:
        _text(display["description"], "pack description", 1024)
    if "style" in display:
        _token(display["style"], "style")
    _tags(manifest.get("tags", []))

    taxonomy = manifest.get("taxonomy", {})
    if not isinstance(taxonomy, dict) or set(taxonomy) - {"rarities", "tags"}:
        raise AssetError("invalid taxonomy")
    rarities = taxonomy.get("rarities", {})
    if not isinstance(rarities, dict) or len(rarities) > 32:
        raise AssetError("invalid rarity taxonomy")
    for ident, definition in rarities.items():
        _token(ident, "rarity")
        if not isinstance(definition, dict) or set(definition) - {"label", "tier"}:
            raise AssetError("invalid rarity definition")
        _text(definition.get("label"), "rarity label")
        if "tier" in definition and (type(definition["tier"]) is not int or not 0 <= definition["tier"] <= 100):
            raise AssetError("invalid rarity tier")
    available_rarities = set(rarities) if rarities else DEFAULT_RARITIES
    tag_defs = taxonomy.get("tags", {})
    if not isinstance(tag_defs, dict) or len(tag_defs) > 256:
        raise AssetError("invalid tag taxonomy")
    for ident, definition in tag_defs.items():
        _token(ident, "tag")
        if not isinstance(definition, dict) or set(definition) - {"label", "description"}:
            raise AssetError("invalid tag definition")
        _text(definition.get("label"), "tag label")
        if "description" in definition:
            _text(definition["description"], "tag description", 512)

    objects = manifest.get("objects", {})
    collections = manifest.get("collections", {})
    if not isinstance(objects, dict) or len(objects) > MAX_OBJECTS:
        raise AssetError("invalid object table")
    if not isinstance(collections, dict) or len(collections) > MAX_COLLECTIONS:
        raise AssetError("invalid collection table")
    for object_id, obj in objects.items():
        _token(object_id, "object ID")
        if not isinstance(obj, dict) or set(obj) - {"kind", "name", "description", "rarity", "tags", "attributes", "resources", "rulesRef", "modifiers"}:
            raise AssetError("invalid object definition")
        _token(obj.get("kind"), "object kind")
        _text(obj.get("name"), "object name")
        if "description" in obj:
            _text(obj["description"], "object description", 1024)
        rarity = _token(obj.get("rarity", "common"), "rarity")
        if rarity not in available_rarities:
            raise AssetError("object references unknown rarity")
        _tags(obj.get("tags", []))
        resources = obj.get("resources", [])
        if not isinstance(resources, list) or len(resources) > 32 or len(set(map(str, resources))) != len(resources):
            raise AssetError("invalid object resources")
        for capability in resources:
            if not isinstance(capability, str) or capability not in manifest["resources"]:
                raise AssetError("object references unknown capability")
        attributes = obj.get("attributes", {})
        if not isinstance(attributes, dict):
            raise AssetError("object attributes must be a map")
        _data(attributes)
        if len(json.dumps(attributes, ensure_ascii=True)) > 8192:
            raise AssetError("object attributes too large")
        if "rulesRef" in obj:
            _token(obj["rulesRef"], "opaque rules reference")
        if "modifiers" in obj:
            _modifiers(obj["modifiers"])
    for collection_id, collection in collections.items():
        _token(collection_id, "collection ID")
        if not isinstance(collection, dict) or set(collection) - {"kind", "name", "description", "tags", "entries"}:
            raise AssetError("invalid collection definition")
        _token(collection.get("kind"), "collection kind")
        _text(collection.get("name"), "collection name")
        if "description" in collection:
            _text(collection["description"], "collection description", 1024)
        _tags(collection.get("tags", []))
        entries = collection.get("entries")
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
            raise AssetError("collection requires bounded entries")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"objectId", "quantity"}:
                raise AssetError("invalid collection entry")
            ref = entry["objectId"]
            if not isinstance(ref, str) or ref not in objects or ref in seen:
                raise AssetError("unknown/duplicate collection reference")
            seen.add(ref)
            if type(entry["quantity"]) is not int or not 1 <= entry["quantity"] <= 99:
                raise AssetError("invalid collection quantity")
        if sum(e["quantity"] for e in entries) > 4096:
            raise AssetError("collection too large")
    return True


def public_object(object_id, obj, allowed_capabilities):
    """Never expose source file paths, private registry paths, hashes or hidden capabilities."""
    return {"id": object_id, "kind": obj["kind"], "name": obj["name"],
            "description": obj.get("description", ""), "rarity": obj.get("rarity", "common"),
            "tags": list(obj.get("tags", [])), "attributes": obj.get("attributes", {}),
            "resources": [r for r in obj.get("resources", []) if r in allowed_capabilities],
            "rulesRef": obj.get("rulesRef"), "modifiers": obj.get("modifiers", [])}
