"""Data-only pack validation, locked activation and persistent preferences.

This library deliberately provides no entitlement authority. Only call install() on
approved, entitlement-checked sources, or from an explicit local developer CLI.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path


class AssetError(Exception):
    """Rejected pack or local registry operation."""


IDENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,126}$", re.ASCII)
RESOURCE = re.compile(r"^[a-z][a-z0-9._-]{0,126}$", re.ASCII)
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$", re.ASCII)
SHA256 = re.compile(r"^[a-f0-9]{64}$", re.ASCII)
SUFFIXES = {".svg", ".png", ".webp", ".jpg", ".jpeg", ".ogg", ".wav", ".mp3", ".json"}
MAX_MANIFEST = 256 * 1024
MAX_FILE = 20 * 1024 * 1024
MAX_PACK = 128 * 1024 * 1024
MAX_FILES = 512
SVG_NS = "http://www.w3.org/2000/svg"
SVG_TAGS = {"svg", "g", "rect", "circle", "ellipse", "path", "line", "polyline", "polygon", "text"}
SVG_ATTRS = {"xmlns", "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2",
             "cx", "cy", "r", "rx", "ry", "d", "fill", "stroke", "stroke-width", "opacity",
             "points", "transform", "font-size", "font-family", "text-anchor", "id"}
MIME = {".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".ogg": "audio/ogg",
        ".wav": "audio/wav", ".mp3": "audio/mpeg", ".json": "application/json"}


def _no_duplicate_keys(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise AssetError("duplicate JSON key")
        result[k] = v
    return result


def _read_json(path, max_bytes=MAX_MANIFEST):
    try:
        with Path(path).open("rb") as f:
            data = f.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise AssetError("oversized JSON document")
        return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise AssetError("invalid JSON document") from exc


def _inside(name):
    if not isinstance(name, str) or not name or name.startswith("/") or "\\" in name or ":" in name:
        raise AssetError("unsafe path")
    if any(s in ("", ".", "..") or s.endswith(".") or s.endswith(" ") for s in name.split("/")):
        raise AssetError("unsafe path")
    if any(ord(c) < 32 for c in name):
        raise AssetError("unsafe path")
    # Protect Windows cache paths against DOS device aliases, even on Linux QA.
    for component in name.split("/"):
        stem = component.split(".", 1)[0].upper()
        if stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise AssetError("reserved Windows asset path")
    p = Path(name)
    if p.is_absolute() or p.suffix.lower() not in SUFFIXES or len(name) > 230:
        raise AssetError("unsafe or unsupported asset path")
    return p


def _svg_is_safe(contents):
    if len(contents) > 2 * 1024 * 1024 or b"<!" in contents or b"<?" in contents:
        raise AssetError("unsafe SVG markup")
    try:
        root = ET.fromstring(contents)
    except ET.ParseError as exc:
        raise AssetError("invalid SVG") from exc
    if root.tag != f"{{{SVG_NS}}}svg":
        raise AssetError("invalid SVG namespace")
    for item in root.iter():
        if not isinstance(item.tag, str) or item.tag not in {f"{{{SVG_NS}}}{t}" for t in SVG_TAGS}:
            raise AssetError("active or unsupported SVG element")
        for key, value in item.attrib.items():
            if key not in SVG_ATTRS or any(token in value.lower() for token in
                                            ("url(", "javascript:", "data:", "@import", "<", ">", "\\")):
                raise AssetError("active or unsupported SVG attribute")


def _check_magic(path, suffix):
    if suffix == ".svg":
        _svg_is_safe(path.read_bytes())
        return
    with path.open("rb") as f:
        head = f.read(16)
    matched = {
        ".png": head.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webp": head.startswith(b"RIFF") and head[8:12] == b"WEBP",
        ".jpeg": head.startswith(b"\xff\xd8\xff"),
        ".jpg": head.startswith(b"\xff\xd8\xff"),
        ".ogg": head.startswith(b"OggS"),
        ".wav": head.startswith(b"RIFF") and head[8:12] == b"WAVE",
        ".mp3": head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xff and head[1] & 0xe0 == 0xe0),
    }
    if suffix in matched and not matched[suffix]:
        raise AssetError("content type does not match asset file")
    if suffix == ".json":
        _read_json(path, MAX_FILE)


def validate(folder):
    """Verify a source directory fully, fail closed and return its manifest."""
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise AssetError("asset source must be a directory")
    manifest = _read_json(folder / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("schema") != "tavi.assets.pack/v1":
        raise AssetError("unsupported manifest schema")
    ident, version = manifest.get("id"), manifest.get("version")
    if not isinstance(ident, str) or not IDENT.fullmatch(ident) or ident in (".", ".."):
        raise AssetError("invalid pack ID")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise AssetError("invalid pack version")
    if manifest.get("compatibility") != {"host": "tavi-assets/v1"}:
        raise AssetError("unsupported host compatibility")
    if not isinstance(manifest.get("type"), str) or not RESOURCE.fullmatch(manifest["type"]):
        raise AssetError("invalid pack type")
    files, resources = manifest.get("files"), manifest.get("resources")
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
        raise AssetError("missing or excessive files")
    if not isinstance(resources, dict) or not resources or len(resources) > MAX_FILES:
        raise AssetError("missing or excessive resources")
    total = 0
    seen_platform_names = set()
    for name, digest in files.items():
        rel = _inside(name)
        platform_name = name.casefold()
        if platform_name in seen_platform_names:
            raise AssetError("case-colliding asset names")
        seen_platform_names.add(platform_name)
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise AssetError("invalid file digest")
        p = folder / rel
        if p.is_symlink() or any(parent.is_symlink() for parent in p.parents if parent != folder):
            raise AssetError("symlink in asset path")
        if not p.is_file() or not p.resolve().is_relative_to(folder.resolve()):
            raise AssetError("missing or escaped file")
        size = p.stat().st_size
        if size > MAX_FILE or size <= 0:
            raise AssetError("invalid file size")
        total += size
        if total > MAX_PACK:
            raise AssetError("oversized asset pack")
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != digest:
            raise AssetError("integrity failure")
        _check_magic(p, rel.suffix.lower())
    for resource, entry in resources.items():
        if not isinstance(resource, str) or not RESOURCE.fullmatch(resource):
            raise AssetError("invalid capability name")
        if not isinstance(entry, dict) or set(entry) - {"default", "variants"}:
            raise AssetError("invalid resource declaration")
        if not isinstance(entry.get("default"), str) or entry["default"] not in files:
            raise AssetError("missing resource default")
        variants = entry.get("variants", {})
        if not isinstance(variants, dict) or len(variants) > 64:
            raise AssetError("invalid variants")
        for name, filename in variants.items():
            if not isinstance(name, str) or not RESOURCE.fullmatch(name) or not isinstance(filename, str) or filename not in files:
                raise AssetError("invalid variant")
        used = [entry["default"], *variants.values()]
        if len({MIME[Path(file).suffix.lower()] for file in used}) != 1:
            raise AssetError("variants must have one media type")
    from .metadata import validate_metadata
    validate_metadata(manifest)
    return manifest


@contextlib.contextmanager
def _lock(path, timeout=7):
    """OS-held interprocess lock for Windows and POSIX, never delete lock file."""
    import errno
    path = Path(path)
    if path.is_symlink():
        raise AssetError("unsafe registry lock symlink")
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    held = False
    try:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"0")
        deadline = time.monotonic() + timeout
        while not held:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held = True
            except OSError as exc:
                if os.name != "nt" and exc.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() >= deadline:
                    raise AssetError("asset registry is locked") from exc
                time.sleep(0.04)
        yield
    finally:
        if held:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


class AssetManager:
    def __init__(self, root):
        self.root = Path(root)
        if self.root.is_symlink():
            raise AssetError("managed asset root may not be a symlink")
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = self.root / "registry.json"
        # Recover only while holding the same writer lock used by installation.
        # This cannot mistake an active installer's stage for abandoned work.
        with _lock(self.root / ".registry.lock"):
            self.state = self._load()
            self.recovery = self._recover_locked(self.state)

    def _load(self):
        if self.registry.is_symlink():
            raise AssetError("unsafe registry symlink")
        state = _read_json(self.registry) if self.registry.exists() else {"installed": {}, "preferences": {}}
        if not isinstance(state, dict) or set(state) != {"installed", "preferences"}:
            raise AssetError("invalid registry")
        if not all(isinstance(state[k], dict) for k in state):
            raise AssetError("invalid registry")
        for ident, version in state["installed"].items():
            if not isinstance(ident, str) or not IDENT.fullmatch(ident) or not isinstance(version, str) or not SEMVER.fullmatch(version):
                raise AssetError("invalid installed pack record")
        for ident, resources in state["preferences"].items():
            if not isinstance(ident, str) or not IDENT.fullmatch(ident) or not isinstance(resources, dict):
                raise AssetError("invalid preference record")
            for key, variant in resources.items():
                if not isinstance(key, str) or not RESOURCE.fullmatch(key) or not isinstance(variant, str) or not RESOURCE.fullmatch(variant):
                    raise AssetError("invalid preference value")
        return state

    def _recover_locked(self, state):
        """Discard exclusively named incomplete scratch state under the registry lock.

        Finalized releases missing from the registry are *not* activated and are
        deliberately retained: they may be safe to reuse after revalidation.
        Never derive ownership/entitlements from filesystem content.
        """
        report = {"discardedStages": 0, "discardedRegistryTemps": 0,
                  "inactiveVersions": 0}
        for entry in self.root.iterdir():
            if re.fullmatch(r"\.registry-[a-z0-9_]{8}", entry.name):
                if entry.is_symlink() or not entry.is_file():
                    raise AssetError("unsafe registry scratch entry")
                entry.unlink()
                report["discardedRegistryTemps"] += 1

        packs = self.root / "packs"
        if packs.is_symlink() or (packs.exists() and not packs.is_dir()):
            raise AssetError("unsafe packs cache directory")
        if not packs.exists():
            return report
        for pack in packs.iterdir():
            if not IDENT.fullmatch(pack.name):
                # Preserve unknown user data; don't guess ownership of the path.
                continue
            if pack.is_symlink() or not pack.is_dir():
                raise AssetError("unsafe cached pack directory")
            for version in pack.iterdir():
                if version.name.startswith(".stage-"):
                    if not re.fullmatch(r"\.stage-[a-z0-9_]{8}", version.name):
                        raise AssetError("unrecognized staging entry")
                    if version.is_symlink() or not version.is_dir():
                        raise AssetError("unsafe staged directory")
                    shutil.rmtree(version)
                    report["discardedStages"] += 1
                elif SEMVER.fullmatch(version.name):
                    if version.is_symlink() or not version.is_dir():
                        raise AssetError("unsafe cached release directory")
                    if state["installed"].get(pack.name) != version.name:
                        report["inactiveVersions"] += 1
        return report

    def recover(self):
        """Run bounded recovery on demand, returning observable cleanup counts."""
        with _lock(self.root / ".registry.lock"):
            state = self._load()  # Corrupt registries block cleanup (fail closed).
            report = self._recover_locked(state)
            self.state, self.recovery = state, report
            return dict(report)

    def _save(self, state):
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".registry-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.registry)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        self.state = state

    def install(self, source):
        """Install an already-approved local source; never checks remote entitlement."""
        source = Path(source)
        manifest = validate(source)
        ident, version = manifest["id"], manifest["version"]
        with _lock(self.root / ".registry.lock"):
            state = self._load()
            previous = state["installed"].get(ident)
            if previous and tuple(map(int, version.split("."))) < tuple(map(int, previous.split("."))):
                raise AssetError("downgrade not permitted")
            packs_root = self.root / "packs"
            if packs_root.is_symlink() or (packs_root.exists() and not packs_root.is_dir()):
                raise AssetError("unsafe packs cache directory")
            if (packs_root / ident).is_symlink():
                raise AssetError("unsafe cached pack directory")
            target = packs_root / ident / version
            if target.exists() or target.is_symlink():
                installed_manifest = validate(target)
                if installed_manifest != manifest:
                    raise AssetError("immutable version has different contents")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=target.parent))
                try:
                    for name in manifest["files"]:
                        dest = stage / _inside(name)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source / name, dest)
                    (stage / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
                    validate(stage)
                    os.replace(stage, target)
                finally:
                    if stage.exists():
                        shutil.rmtree(stage)
            state["installed"][ident] = version
            self._save(state)
            return manifest

    def manifest_for(self, ident):
        """Return validated active manifest; never treat cache-only files as active."""
        if not isinstance(ident, str) or not IDENT.fullmatch(ident):
            raise AssetError("invalid pack ID")
        state = self._load()
        version = state["installed"].get(ident)
        if not version:
            raise AssetError("pack not installed")
        manifest = validate(self.root / "packs" / ident / version)
        if manifest["id"] != ident or manifest["version"] != version:
            raise AssetError("active release identity mismatch")
        return manifest

    def list_installed(self):
        return dict(self._load()["installed"])

    def select(self, ident, resource, variant):
        with _lock(self.root / ".registry.lock"):
            state = self._load()
            entry = self._resource(state, ident, resource)
            if variant not in entry.get("variants", {}):
                raise AssetError("unknown variant")
            state["preferences"].setdefault(ident, {})[resource] = variant
            self._save(state)

    def _resource(self, state, ident, resource):
        version = state["installed"].get(ident)
        if not version:
            raise AssetError("pack not installed")
        manifest = validate(self.root / "packs" / ident / version)
        try:
            return manifest["resources"][resource]
        except KeyError as exc:
            raise AssetError("unknown capability") from exc

    def resolved(self, ident, resource):
        state = self._load()
        entry = self._resource(state, ident, resource)
        variant = state["preferences"].get(ident, {}).get(resource)
        name = entry.get("variants", {}).get(variant, entry["default"])
        path = self.root / "packs" / ident / state["installed"][ident] / name
        return {"bytes": path.read_bytes(), "content_type": MIME[path.suffix.lower()],
                "pack": ident, "version": state["installed"][ident], "resource": resource,
                "selected": variant if variant in entry.get("variants", {}) else None}

    def resolve(self, ident, resource):
        return self.resolved(ident, resource)["bytes"]

    def uninstall(self, ident):
        with _lock(self.root / ".registry.lock"):
            state = self._load()
            if ident not in state["installed"]:
                raise AssetError("pack not installed")
            state["installed"].pop(ident)
            self._save(state)
            # The registry is deactivated first; a failed delete never restores access.
            cached = self.root / "packs" / ident
            try:
                if cached.is_symlink():
                    raise AssetError("unexpected symlink in local cache")
                if cached.is_dir():
                    shutil.rmtree(cached)
            except OSError as exc:
                raise AssetError("pack deactivated but cache cleanup failed") from exc
        # Variant preferences intentionally survive a later reinstallation.
