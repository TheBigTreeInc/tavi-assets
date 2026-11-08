"""Optional operator-invoked post-run intake. Does not publish or upload by default.

For an approved stage, provide an operator receipt bound to the exact archive SHA256,
a configured DAPI endpoint, and LOOPRD_ASSETS_INGEST_TOKEN from the secret store.
A successful stage never implies publication approval.
"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from tavia import stage
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from tavi_assets.tavia import unpack_tavia


def inspect_file(path):
    path=Path(path)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as temp:
        m=unpack_tavia(path,temp)
    return {'archive':path.name,'sha256':sha,'packId':m['id'],'version':m['version'],'files':len(m['files'])}


def main():
    parser=argparse.ArgumentParser(description='Validate an exact TAVIA candidate; optional separately approved stage only')
    parser.add_argument('archive',type=Path)
    parser.add_argument('--approval-receipt',type=Path,help='Operator-provided JSON: {approvedSha256, endpoint, action:"stage"}')
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    details=inspect_file(args.archive)
    details['action']='dry_run'
    if args.execute:
        if not args.approval_receipt or not args.approval_receipt.is_file():
            parser.error('exact-file approval receipt required for --execute')
        approval=json.loads(args.approval_receipt.read_text(encoding='utf-8'))
        if approval.get('action')!='stage' or approval.get('approvedSha256')!=details['sha256']:
            parser.error('approval receipt not valid for this exact candidate')
        endpoint=approval.get('endpoint')
        if not isinstance(endpoint,str) or not endpoint.startswith('https://') or '?' in endpoint or '#' in endpoint:
            parser.error('approved HTTPS endpoint required')
        token=os.environ.get('LOOPRD_ASSETS_INGEST_TOKEN')
        if not token or len(token)<32:
            parser.error('missing scoped runtime LOOPRD_ASSETS_INGEST_TOKEN')
        response=stage(args.archive,endpoint,token)
        details['action']='staged_only';details['result']=response
    print(json.dumps(details,sort_keys=True,indent=2))

if __name__=='__main__':main()
