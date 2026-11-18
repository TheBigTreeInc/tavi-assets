"""Source-controlled public artifact index. Never a purchase or publish authority.

Catalog generation is read-only by default and local --write never uploads or
publishes. Only independently approved PUBLIC artifacts can be indexed.
"""
from __future__ import annotations
import hashlib
import json
import re
import tempfile
from pathlib import Path

from .core import AssetError
from .blueprint_package import IDENT, VERSION, inspect_tavib
from .tavia import unpack_tavia

SOURCE_SCHEMA = 'tavi.assets.repository-source/v1'
INDEX_SCHEMA = 'tavi.assets.repository-index/v1'
SHA = re.compile(r'^[a-f0-9]{64}$')
APPROVAL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/-]{4,199}$')
MAX_PUBLIC_ARTIFACT = 140 * 1024 * 1024


def _sha_bytes(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while buf := stream.read(1024 * 1024):
            h.update(buf)
    return h.hexdigest()


def _load(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError) as exc:
        raise AssetError('missing or invalid repository JSON') from exc
    if not isinstance(data, dict):
        raise AssetError('repository JSON must be an object')
    return data


def _entry(root, item, kind):
    keys = {'id', 'version', 'artifact', 'sha256', 'visibility', 'status', 'approvalReference'}
    if kind == 'packs':
        keys.add('blueprintId')
    if not isinstance(item, dict) or set(item) - keys or not {'id', 'version', 'artifact', 'visibility', 'status'} <= set(item):
        raise AssetError('invalid repository source entry')
    ident, version = item['id'], item['version']
    if not isinstance(ident, str) or not IDENT.fullmatch(ident) or not isinstance(version, str) or not VERSION.fullmatch(version):
        raise AssetError('invalid repository identity/version')
    if kind == 'packs' and 'blueprintId' in item and (not isinstance(item['blueprintId'], str) or not IDENT.fullmatch(item['blueprintId'])):
        raise AssetError('invalid blueprint reference')
    if item['visibility'] not in ('public', 'restricted') or item['status'] not in ('draft', 'approved'):
        raise AssetError('invalid publication state')
    if item['status'] != 'approved':
        return None  # local draft; deliberately excluded from public index
    if item['visibility'] != 'public':
        raise AssetError('restricted/paid content must not enter a public Git catalog')
    if not isinstance(item.get('sha256'), str) or not SHA.fullmatch(item['sha256']):
        raise AssetError('approved artifact requires pinned SHA-256')
    if not isinstance(item.get('approvalReference'), str) or not APPROVAL.fullmatch(item['approvalReference']):
        raise AssetError('approved artifact requires an auditable approval reference')
    artifact = f'{"schematics" if kind == "schematics" else "packs"}/{ident}/{version}/{"blueprint.tavib" if kind == "schematics" else "package.tavia"}'
    if item['artifact'] != artifact:
        raise AssetError('noncanonical repository artifact path')
    p = root / artifact
    for candidate in (p, *p.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            raise AssetError('symlink in repository artifact path')
    if not p.is_file() or not p.resolve().is_relative_to(root.resolve()) or p.stat().st_size > MAX_PUBLIC_ARTIFACT:
        raise AssetError('missing, unsafe or oversized repository artifact')
    if _sha_bytes(p) != item['sha256']:
        raise AssetError('public artifact digest does not match approved source pin')
    if kind == 'schematics':
        m = inspect_tavib(p)
    else:
        with tempfile.TemporaryDirectory(prefix='tavi-public-index-') as tmp:
            m = unpack_tavia(p, tmp)
    if m['id'] != ident or m['version'] != version:
        raise AssetError('public artifact identity/version differs from source record')
    result = {'id': ident, 'version': version, 'artifact': artifact,
              'bytes': p.stat().st_size, 'sha256': item['sha256'], 'status': 'approved',
              'approvalReference': item['approvalReference']}
    if kind == 'schematics':
        result['blueprintSchema'] = m['blueprintSchema']
    else:
        result['compatibility'] = m['compatibility']
        if 'blueprintId' in item:
            result['blueprintId'] = item['blueprintId']
    return result


def build_index(root):
    root = Path(root)
    source = _load(root / 'catalog.source.json')
    if set(source) != {'schema', 'schematics', 'packs'} or source['schema'] != SOURCE_SCHEMA:
        raise AssetError('unknown repository source schema')
    out = {'schema': INDEX_SCHEMA, 'schematics': [], 'packs': []}
    all_ids = {'schematics': set(), 'packs': set()}
    for kind in ('schematics', 'packs'):
        entries = source[kind]
        if not isinstance(entries, list) or len(entries) > 2000:
            raise AssetError('invalid repository source collection')
        for item in entries:
            if not isinstance(item, dict):
                raise AssetError('invalid repository source item')
            pair = (item.get('id'), item.get('version'))
            if pair in all_ids[kind]:
                raise AssetError('duplicate catalog identity/version')
            all_ids[kind].add(pair)
            result = _entry(root, item, kind)
            if result is not None:
                out[kind].append(result)
        out[kind].sort(key=lambda item: (item['id'], tuple(map(int, item['version'].split('.')))))
    # The blueprint identity can be referenced even if its package is staged separately:
    # consumer always treats it as optional development metadata, not entitlement.
    return out


def index_bytes(index):
    return (json.dumps(index, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def verify_index(root):
    root = Path(root)
    generated = index_bytes(build_index(root))
    try:
        stored = (root / 'catalog.json').read_bytes()
    except OSError as exc:
        raise AssetError('missing repository catalog.json') from exc
    if stored != generated:
        raise AssetError('catalog.json out of date; run explicit local generation')
    return json.loads(stored)


def write_index(root):
    root = Path(root)
    payload = index_bytes(build_index(root))
    # Local source-file update only, no remote publication or permissions transition.
    target = root / 'catalog.json'
    pending = root / 'catalog.json.pending'
    try:
        pending.write_bytes(payload)
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    return json.loads(payload)
