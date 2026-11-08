"""Developer-only TAVIA archive transport. Not a user-facing installer."""
from __future__ import annotations
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from .core import AssetError, MAX_PACK, MAX_FILES, MAX_FILE, validate

MAX_ARCHIVE = 140 * 1024 * 1024

def unpack_tavia(archive, target):
    archive, target = Path(archive), Path(target)
    if not archive.is_file() or archive.stat().st_size > MAX_ARCHIVE:
        raise AssetError('missing or oversized TAVIA archive')
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if not infos or len(infos) > MAX_FILES + 1:
            raise AssetError('invalid TAVIA entry count')
        paths, total = set(), 0
        for item in infos:
            name = item.filename
            if item.is_dir() or item.flag_bits & 1 or item.file_size > MAX_FILE or item.file_size < 1:
                raise AssetError('unsupported TAVIA entry')
            if (not name or name.startswith('/') or '\\' in name or ':' in name or
                any(x in ('', '.', '..') for x in name.split('/')) or
                name.casefold() in paths or item.external_attr >> 16 & 0o170000 == 0o120000):
                raise AssetError('unsafe TAVIA entry')
            paths.add(name.casefold())
            total += item.file_size
            if total > MAX_PACK + 262144:
                raise AssetError('TAVIA unpack limit exceeded')
            if name != 'manifest.json' and not name.lower().endswith(('.svg','.png','.webp','.jpg','.jpeg','.ogg','.wav','.mp3','.json')):
                raise AssetError('unsupported TAVIA resource type')
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(item) as src, dest.open('wb') as out:
                copied=0
                while True:
                    chunk=src.read(65536)
                    if not chunk: break
                    copied+=len(chunk)
                    if copied>item.file_size: raise AssetError('TAVIA entry size mismatch')
                    out.write(chunk)
                if copied!=item.file_size: raise AssetError('TAVIA incomplete entry')
        manifest=validate(target)
        expected={'manifest.json', *manifest['files']}
        if {p.casefold() for p in expected} != paths:
            raise AssetError('TAVIA has missing or unexpected files')
        return manifest

def create_tavia(source, destination):
    source, destination=Path(source),Path(destination)
    manifest=validate(source)
    expected=['manifest.json', *sorted(manifest['files'])]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in expected:
            info=zipfile.ZipInfo(name, (2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            z.writestr(info,(source/name).read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return manifest
