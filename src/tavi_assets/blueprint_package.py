"""TAVIB v1 author-side packaging and inspection; no host or publisher authority.

The Studio blueprint payload is intentionally opaque after its schema marker: the
Studio owner must approve its field semantics before claiming integration.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from .core import AssetError

PACKAGE_SCHEMA = 'tavi.assets.blueprint-package/v1'
BLUEPRINT_SCHEMA = 'tavix.studio.asset-blueprint/v1'
IDENT = re.compile(r'^[a-z0-9][a-z0-9._-]{0,126}$')
VERSION = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_BLUEPRINT_BYTES = 2 * 1024 * 1024
MAX_PREVIEW_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 18 * 1024 * 1024
MAX_FILES = 12


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(data, label, max_size=MAX_BLUEPRINT_BYTES):
    if len(data) > max_size:
        raise AssetError(f'oversized {label}')
    try:
        obj = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise AssetError(f'invalid {label} JSON') from exc
    if not isinstance(obj, dict):
        raise AssetError(f'invalid {label} object')
    return obj


def _check_blueprint(data):
    content = _json(data, 'blueprint')
    if content.get('schema') != BLUEPRINT_SCHEMA:
        raise AssetError('unsupported Studio blueprint payload schema')
    return content


def _valid_entry(name):
    return (name in ('manifest.json', 'blueprint.json', 'README.md') or
            bool(re.fullmatch(r'previews/[A-Za-z0-9][A-Za-z0-9._-]{0,90}\.webp', name)))


def _manifest(ident, version, files):
    return {'schema': PACKAGE_SCHEMA, 'id': ident, 'version': version,
            'blueprintSchema': BLUEPRINT_SCHEMA,
            'files': {name: {'sha256': _sha(data), 'bytes': len(data)}
                      for name, data in sorted(files.items())}}


def create_tavib(blueprint, destination, ident, version, readme=None, previews=()):
    """Create a deterministic ZIP from explicitly supplied, non-executable files."""
    if not isinstance(ident, str) or not IDENT.fullmatch(ident) or not isinstance(version, str) or not VERSION.fullmatch(version):
        raise AssetError('invalid blueprint ID/version')
    raw = Path(blueprint).read_bytes()
    _check_blueprint(raw)
    files = {'blueprint.json': raw}
    if readme is not None:
        data = Path(readme).read_bytes()
        if not data or len(data) > 32768:
            raise AssetError('README size invalid')
        try:
            data.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise AssetError('README requires UTF-8') from exc
        files['README.md'] = data
    for preview in previews:
        p = Path(preview)
        name = 'previews/' + p.name
        if not _valid_entry(name) or name in files or name.casefold() in (k.casefold() for k in files):
            raise AssetError('invalid or duplicate preview filename')
        data = p.read_bytes()
        if not data.startswith(b'RIFF') or data[8:12] != b'WEBP' or len(data) > MAX_PREVIEW_BYTES:
            raise AssetError('invalid/oversized WebP preview')
        files[name] = data
    if len(files) + 1 > MAX_FILES or sum(map(len, files.values())) > MAX_TOTAL_BYTES:
        raise AssetError('TAVIB content limits exceeded')
    manifest = _manifest(ident, version, files)
    files['manifest.json'] = (json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode()
    destination = Path(destination)
    if destination.suffix.lower() != '.tavib':
        raise AssetError('output must end in .tavib')
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = destination.with_name(destination.name + '.pending')
    try:
        with zipfile.ZipFile(scratch, 'w') as z:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED if name.endswith('.webp') else zipfile.ZIP_DEFLATED
                z.writestr(info, data, compresslevel=8)
        if scratch.stat().st_size > MAX_ARCHIVE_BYTES:
            raise AssetError('TAVIB archive too large')
        inspect_tavib(scratch)
        scratch.replace(destination)
    finally:
        scratch.unlink(missing_ok=True)
    return manifest


def inspect_tavib(path):
    """Verify archive layout, integrity and digest-bound payloads without extraction."""
    path = Path(path)
    if not path.is_file() or path.suffix.lower() not in ('.tavib', '.pending') or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise AssetError('invalid/oversized TAVIB file')
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            names = [entry.filename for entry in infos]
            if not 2 <= len(infos) <= MAX_FILES or len({n.casefold() for n in names}) != len(names):
                raise AssetError('invalid/duplicate TAVIB entries')
            if 'manifest.json' not in names or 'blueprint.json' not in names:
                raise AssetError('missing TAVIB manifest/blueprint')
            total = 0
            values = {}
            for entry in infos:
                name = entry.filename
                mode = (entry.external_attr >> 16) & 0o170000
                if (not _valid_entry(name) or entry.is_dir() or entry.flag_bits & 1 or
                        mode not in (0, 0o100000) or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise AssetError('unsupported/unsafe TAVIB entry')
                size_limit = MAX_BLUEPRINT_BYTES if name in ('manifest.json', 'blueprint.json') else (32768 if name == 'README.md' else MAX_PREVIEW_BYTES)
                if not 0 < entry.file_size <= size_limit:
                    raise AssetError('invalid TAVIB entry size')
                total += entry.file_size
                if total > MAX_TOTAL_BYTES:
                    raise AssetError('TAVIB extraction limit exceeded')
                content = z.read(entry)
                if len(content) != entry.file_size:
                    raise AssetError('TAVIB entry size mismatch')
                values[name] = content
            manifest = _json(values.pop('manifest.json'), 'manifest')
            if set(manifest) != {'schema', 'id', 'version', 'blueprintSchema', 'files'} or manifest['schema'] != PACKAGE_SCHEMA or manifest['blueprintSchema'] != BLUEPRINT_SCHEMA:
                raise AssetError('invalid TAVIB manifest')
            if not isinstance(manifest['id'], str) or not IDENT.fullmatch(manifest['id']) or not isinstance(manifest['version'], str) or not VERSION.fullmatch(manifest['version']):
                raise AssetError('invalid TAVIB identity')
            entries = manifest['files']
            if not isinstance(entries, dict) or set(entries) != set(values):
                raise AssetError('TAVIB entry manifest mismatch')
            for name, data in values.items():
                info = entries[name]
                if not isinstance(info, dict) or set(info) != {'sha256', 'bytes'} or info['sha256'] != _sha(data) or type(info['bytes']) is not int or info['bytes'] != len(data):
                    raise AssetError('TAVIB hash/size mismatch')
                if name.startswith('previews/') and (not data.startswith(b'RIFF') or data[8:12] != b'WEBP'):
                    raise AssetError('invalid TAVIB WebP preview')
            _check_blueprint(values['blueprint.json'])
            if 'README.md' in values:
                values['README.md'].decode('utf-8')
            return manifest
    except (zipfile.BadZipFile, OSError, EOFError, RuntimeError, UnicodeDecodeError, KeyError, TypeError) as exc:
        raise AssetError('invalid TAVIB archive') from exc
