"""Developer ingestion transport: create, inspect and stage TAVIA packs; no unattended publication."""
import argparse
import base64
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from tavi_assets.tavia import create_tavia,unpack_tavia

CHUNK_SIZE=96*1024

def send(url, token, message):
    body=json.dumps(message,separators=(',',':')).encode()
    req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+token},method='POST')
    with urllib.request.urlopen(req,timeout=60) as response:
        result=json.load(response)
    if not isinstance(result,dict) or not result.get('ok'):
        raise RuntimeError('LoopRD request rejected: '+str(result.get('reason','unknown')))
    return result

def stage(archive,url,token):
    with tempfile.TemporaryDirectory(prefix='tavia-stage-') as d:
        manifest=unpack_tavia(archive,d)
        pid,v=manifest['id'],manifest['version']
        send(url,token,{'op':'begin','manifest':manifest})
        for name in sorted(manifest['files']):
            path=Path(d)/name
            with path.open('rb') as source:
                offset=0
                while piece:=source.read(CHUNK_SIZE):
                    send(url,token,{'op':'chunk','packId':pid,'version':v,'name':name,
                         'offset':offset,'contentBase64':base64.b64encode(piece).decode('ascii')})
                    offset+=len(piece)
        return send(url,token,{'op':'finalize','packId':pid,'version':v})

def main():
    p=argparse.ArgumentParser(description='Developer-only TAVIA transport; never publishes automatically')
    sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('build');a.add_argument('source');a.add_argument('output')
    a=sub.add_parser('inspect');a.add_argument('archive')
    a=sub.add_parser('stage');a.add_argument('archive');a.add_argument('--url',required=True);a.add_argument('--execute',action='store_true')
    args=p.parse_args()
    if args.action=='build':
        m=create_tavia(args.source,args.output);print('Built',args.output,m['id'],m['version'])
    elif args.action=='inspect':
        with tempfile.TemporaryDirectory() as d:
            m=unpack_tavia(args.archive,d)
            print(json.dumps({'id':m['id'],'version':m['version'],'files':len(m['files']),'resources':len(m['resources'])},indent=2))
    else:
        with tempfile.TemporaryDirectory() as d:
            m=unpack_tavia(args.archive,d)
        print('Validated',m['id'],m['version'],'for',args.url)
        if not args.execute:
            print('DRY RUN: stage requires explicit --execute and LOOPRD_ASSETS_INGEST_TOKEN. No network request made.')
            return
        token=os.environ.get('LOOPRD_ASSETS_INGEST_TOKEN')
        if not token or len(token)<32:raise SystemExit('Missing LOOPRD_ASSETS_INGEST_TOKEN')
        print(json.dumps(stage(args.archive,args.url,token),indent=2))
        print('Staged only; publish requires separate assets:publish approval/action.')
if __name__=='__main__':main()
