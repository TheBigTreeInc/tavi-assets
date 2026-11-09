"""Generate an importable LoopRD v1 component descriptor from reviewed source.
Run --check to confirm generated artifact freshness. No deployment side effects.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent


def schema():
    return [
        'CREATE TABLE "AssetPackVersion" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "packId" TEXT NOT NULL, "version" TEXT NOT NULL, "status" TEXT NOT NULL, "manifest" TEXT NOT NULL, "manifestSha256" TEXT NOT NULL, "created" INTEGER NOT NULL, UNIQUE ("packId","version"))',
        'CREATE TABLE "AssetBlob" ("digest" TEXT PRIMARY KEY, "content" BLOB NOT NULL, "byteSize" INTEGER NOT NULL, "created" INTEGER NOT NULL)',
        'CREATE TABLE "AssetPackResource" ("packId" TEXT NOT NULL, "version" TEXT NOT NULL, "filename" TEXT NOT NULL, "digest" TEXT NOT NULL, PRIMARY KEY ("packId","version","filename"))',
        'CREATE INDEX "AssetPackResource_digest" ON "AssetPackResource" ("digest")',
        'CREATE TABLE "AssetUploadChunk" ("packId" TEXT NOT NULL, "version" TEXT NOT NULL, "filename" TEXT NOT NULL, "offset" INTEGER NOT NULL, "content" BLOB NOT NULL, PRIMARY KEY ("packId","version","filename","offset"))',
        'CREATE TABLE "AssetPublicationAudit" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "packId" TEXT NOT NULL, "version" TEXT NOT NULL, "action" TEXT NOT NULL, "actor" TEXT NOT NULL, "created" INTEGER NOT NULL)',
        'CREATE INDEX "AssetPublicationAudit_pack" ON "AssetPublicationAudit" ("packId","version")',
    ]

def descriptor():
    core=(ROOT/'src/tavi_assets/core.py').read_text(encoding='utf8')
    # LoopRD compiles one Python handler source, with no access to repository modules.
    handler=(HERE/'handler.py').read_text(encoding='utf8')
    source=core+'\n\n'+handler
    models={
       'AssetPackVersion':{'fields':{
        'id':{'type':'integer','primaryKey':True,'generated':True},
        'packId':{'type':'string','maxLength':127,'required':True},
        'version':{'type':'string','maxLength':64,'required':True},
        'status':{'type':'string','maxLength':16,'required':True},
        'manifestSha256':{'type':'string','maxLength':64,'required':True},
        'created':{'type':'integer','required':True}}},
       'AssetPublicationAudit':{'fields':{
        'id':{'type':'integer','primaryKey':True,'generated':True},
        'packId':{'type':'string','maxLength':127,'required':True},
        'version':{'type':'string','maxLength':64,'required':True},
        'action':{'type':'string','maxLength':16,'required':True},
        'actor':{'type':'string','maxLength':128,'required':True},
        'created':{'type':'integer','required':True}}},
    }
    return {'apiVersion':'looprd/v1','component':'tavi-assets','release':'0.1.15','api':{'version':'v1'},
       'requires':['auth.verified','management.data','service.contracts','reports.bugs'],
       'auth':{'mode':'database','scopes':['assets:read','assets:ingest','assets:publish']},
       'database':{'backend':'sqlite','schemaVersion':2,'migrations':[{'version':2,'statements':schema()}]},
       'limits':{'requestsPerMinute':600,'burstPerSecond':12,'maxInFlight':12},
       'models':models,
       'resources':{
          'asset-versions':{'model':'AssetPackVersion','path':'/operator-asset-versions','operations':['list','get'],
              'permissions':{'list':['assets:publish'],'get':['assets:publish']},
              'projection':['id','packId','version','status','manifestSha256','created']},
          'asset-audit':{'model':'AssetPublicationAudit','path':'/operator-asset-audit','operations':['list','get'],
              'permissions':{'list':['assets:publish'],'get':['assets:publish']},
              'projection':['id','packId','version','action','actor','created']},
        },
       'management':{'resources':{
          'asset-versions':{'label':'Asset packs and publication status','titleField':'packId',
             'fields':{key:{'label':{'id':'ID','packId':'Pack ID','version':'Version','status':'Status','manifestSha256':'Manifest SHA-256','created':'Created'}[key]} for key in ('id','packId','version','status','manifestSha256','created')}},
          'asset-audit':{'label':'Asset publication audit','titleField':'packId',
             'fields':{key:{'label':{'id':'ID','packId':'Pack ID','version':'Version','action':'Action','actor':'Actor','created':'Created'}[key]} for key in ('id','packId','version','action','actor','created')}}},
          'actions':{}},
       'handlers':[
          {'path':'/catalog','method':'POST','kind':'python','scopes':['assets:read'],'source':source,
            'contract':{'name':'tavi-assets-catalog','version':1}},
          {'path':'/admin','method':'POST','kind':'python','scopes':['assets:ingest','assets:publish'],'source':source,
            'contract':{'name':'tavi-assets-registry-admin','version':1,'serviceOnly':True}},
       ]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');a=parser.parse_args()
    dest=HERE/'looprd.yaml';generated='# Generated from looprd/generate.py; do not edit by hand. JSON is YAML 1.2 compatible.\n'+json.dumps(descriptor(),indent=2,ensure_ascii=True)+'\n'
    if a.check:
        if not dest.is_file() or dest.read_text(encoding='utf8')!=generated:raise SystemExit('LoopRD descriptor is stale')
        print('LoopRD descriptor: current')
    else:
        dest.write_text(generated,encoding='utf8');print('Generated',dest)
if __name__=='__main__': main()
