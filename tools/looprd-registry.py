"""Operator-side LoopRD asset registry client. No credentials stored on disk.

Never grants itself privileges. Server independently validates verified service scopes;
this tool cannot impersonate a Tavi admin. Publication needs an exact manifest
SHA-256 receipt, distinct from the stage archive approval receipt.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PACK = re.compile(r'^[a-z0-9][a-z0-9._-]{0,126}$')
VERSION = re.compile(r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')
DIGEST = re.compile(r'^[a-f0-9]{64}$')


def endpoint(value):
    if not value.startswith('https://') or any(c in value for c in ('?', '#', '@')):
        raise ValueError('an approved HTTPS DAPI handler endpoint is required')
    return value


def request(url, token, op, **payload):
    if not token or len(token) < 32:
        raise ValueError('missing scoped runtime token')
    message=json.dumps({'op': op, **payload},separators=(',',':')).encode('utf8')
    req=urllib.request.Request(endpoint(url),data=message,headers={
        'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=60) as response:
        result=json.load(response)
    if not isinstance(result,dict) or result.get('ok') is not True:
        raise RuntimeError('LoopRD rejected '+op+': '+str(result.get('reason','invalid_response') if isinstance(result,dict) else 'invalid_response'))
    return result


def require_target(pack,version):
    if not PACK.fullmatch(pack) or not VERSION.fullmatch(version):
        raise ValueError('invalid pack/version')


def check_receipt(path, action, pack, version, digest, url):
    if path is None or not path.is_file():
        raise ValueError('separate exact-manifest operator receipt required')
    receipt=json.loads(path.read_text(encoding='utf8'))
    if (receipt.get('action')!=action or receipt.get('packId')!=pack or
        receipt.get('version')!=version or receipt.get('manifestSha256')!=digest or
        receipt.get('endpoint')!=url or not DIGEST.fullmatch(str(digest))):
        raise ValueError('operator receipt does not match this exact action, version, manifest and endpoint')
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description='Review LoopRD Assets registry; mutation always requires exact receipt and --execute')
    p.add_argument('operation',choices=('catalog','inspect','audit','publish','revoke','resource'))
    p.add_argument('--url',required=True,help='Reviewed /catalog or /admin DAPI endpoint as appropriate')
    p.add_argument('--pack-id');p.add_argument('--version');p.add_argument('--name')
    p.add_argument('--output',type=Path)
    p.add_argument('--approval-receipt',type=Path)
    p.add_argument('--execute',action='store_true')
    args=p.parse_args(argv)
    try:
        endpoint(args.url)
        if args.operation in ('publish','revoke','resource'):
            if args.pack_id is None or args.version is None:raise ValueError('pack/version required')
            require_target(args.pack_id,args.version)
        if args.operation in ('publish','revoke'):
            # Fetch the manifest digest from server; only exact staged versions may be promoted.
            if not args.execute:
                print(json.dumps({'ok':True,'action':'dry_run','operation':args.operation,
                                  'packId':args.pack_id,'version':args.version},indent=2));return 0
            token=os.environ.get('LOOPRD_ASSETS_PUBLISH_TOKEN','')
            versions=request(args.url,token,'inspect')['versions']
            row=next((r for r in versions if r['packId']==args.pack_id and r['version']==args.version),None)
            if row is None:raise ValueError('pack/version not found in operator inspection')
            if row['status']!=('ready' if args.operation=='publish' else 'published'):
                raise ValueError('invalid current status for requested transition')
            check_receipt(args.approval_receipt,args.operation,args.pack_id,args.version,
                          row['manifestSha256'],args.url)
            result=request(args.url,token,args.operation,packId=args.pack_id,version=args.version)
        elif args.operation=='resource':
            if not args.name or not args.output:raise ValueError('resource name and output path required')
            if args.output.exists():raise ValueError('refuse to overwrite existing output')
            token=os.environ.get('LOOPRD_ASSETS_READ_TOKEN','')
            chunks=[];offset=0;total=None;digest=None
            while total is None or offset<total:
                result=request(args.url,token,'resource',packId=args.pack_id,version=args.version,
                               name=args.name,offset=offset)
                if result.get('offset')!=offset or not isinstance(result.get('total'),int) or not 0<result['total']<=20*1024*1024:
                    raise ValueError('invalid response offset/size')
                if total is None:total=result['total'];digest=result['sha256']
                if total!=result['total'] or digest!=result['sha256'] or not DIGEST.fullmatch(str(digest)):
                    raise ValueError('resource changed during download')
                block=base64.b64decode(result['contentBase64'],validate=True)
                if not block or len(block)>96*1024 or offset+len(block)>total:raise ValueError('invalid resource chunk')
                chunks.append(block);offset+=len(block)
            data=b''.join(chunks)
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('resource integrity failed')
            args.output.parent.mkdir(parents=True,exist_ok=True)
            with args.output.open('xb') as out:out.write(data)
            result={'ok':True,'downloaded':str(args.output),'sha256':digest,'bytes':len(data)}
        else:
            token=os.environ.get('LOOPRD_ASSETS_READ_TOKEN' if args.operation=='catalog' else 'LOOPRD_ASSETS_INGEST_TOKEN','')
            result=request(args.url,token,args.operation)
        print(json.dumps(result,indent=2,sort_keys=True));return 0
    except (ValueError,RuntimeError,urllib.error.URLError,KeyError,TypeError) as exc:
        print('LoopRD registry operation failed: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
