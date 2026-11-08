"""LoopRD asset-registry operations; merged with the canonical pack validator at descriptor generation.

All upload/publish actions require a LoopRD VERIFIED SERVICE principal with scope
assets:ingest or assets:publish. Public reads disclose only published versions.
No authentication token is accepted in a request body.
"""
import base64
import hashlib
import json
import re
import tempfile
import time
from pathlib import Path
import sqlalchemy as sa
from starlette.concurrency import run_in_threadpool

PACK = re.compile(r'^[a-z0-9][a-z0-9._-]{0,126}$')
VERSION = re.compile(r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')
DIGEST = re.compile(r'^[a-f0-9]{64}$')
CHUNK_SIZE=96*1024
MAX_CHUNKS=230  # each resource at most 20 MB

def _safe_filename(name):
    return (isinstance(name,str) and 1 <= len(name) <= 240 and not name.startswith("/")
            and "\\" not in name and ":" not in name
            and all(x not in ("", ".", "..") for x in name.split("/")))


def _service(ctx, scope):
    principal=getattr(ctx,'principal',None)
    return (getattr(principal,'kind',None)=='service' and scope in (getattr(principal,'scopes',[]) or []))


def _sql(session_factory, op, payload):
    now=int(time.time())
    with session_factory() as db:
        if op == 'catalog':
            rows=db.execute(sa.text('SELECT packId,version,manifestSha256,manifest FROM "AssetPackVersion" WHERE status=:s ORDER BY packId,version LIMIT 500'),{'s':'published'}).mappings().all()
            return {'ok':True,'packs':[{'packId':r['packId'],'version':r['version'],'manifestSha256':r['manifestSha256'],'manifest':json.loads(r['manifest'])} for r in rows]}
        if op == 'resource':
            pid=payload.get('packId'); v=payload.get('version'); name=payload.get('name'); offset=payload.get('offset',0)
            if not isinstance(pid,str) or not PACK.fullmatch(pid) or not isinstance(v,str) or not VERSION.fullmatch(v) or not _safe_filename(name) or not isinstance(offset,int) or not 0<=offset<=MAX_FILE:
                return {'ok':False,'reason':'bad_request'}
            row=db.execute(sa.text('SELECT b.content,b.digest FROM "AssetPackResource" r JOIN "AssetBlob" b ON b.digest=r.digest JOIN "AssetPackVersion" p ON p.packId=r.packId AND p.version=r.version WHERE p.status=:published AND r.packId=:id AND r.version=:v AND r.filename=:name'),{'published':'published','id':pid,'v':v,'name':name}).mappings().first()
            if row is None:return {'ok':False,'reason':'not_found'}
            data=row['content']; part=data[offset:offset+CHUNK_SIZE]
            return {'ok':True,'sha256':row['digest'],'offset':offset,'total':len(data),'contentBase64':base64.b64encode(part).decode('ascii')}
        if op == 'begin':
            manifest=payload.get('manifest')
            if not isinstance(manifest,dict) or manifest.get('schema')!='tavi.assets.pack/v1':return {'ok':False,'reason':'bad_manifest'}
            pid,v=manifest.get('id'),manifest.get('version')
            if not isinstance(pid,str) or not PACK.fullmatch(pid) or not isinstance(v,str) or not VERSION.fullmatch(v):return {'ok':False,'reason':'bad_manifest'}
            raw=json.dumps(manifest,sort_keys=True,separators=(',',':'))
            if len(raw)>262144 or not isinstance(manifest.get('files'),dict) or len(manifest['files'])>512:return {'ok':False,'reason':'bad_manifest'}
            for name,digest in manifest['files'].items():
                if not _safe_filename(name) or not isinstance(digest,str) or not DIGEST.fullmatch(digest):return {'ok':False,'reason':'bad_manifest'}
            existing=db.execute(sa.text('SELECT status,manifestSha256 FROM "AssetPackVersion" WHERE packId=:id AND version=:v'),{'id':pid,'v':v}).mappings().first()
            mh=hashlib.sha256(raw.encode('utf8')).hexdigest()
            if existing:
                return {'ok':False,'reason':'immutable_version_exists'}
            db.execute(sa.text('INSERT INTO "AssetPackVersion" (packId,version,status,manifest,manifestSha256,created) VALUES (:id,:v,:status,:m,:sha,:now)'),{'id':pid,'v':v,'status':'staging','m':raw,'sha':mh,'now':now})
            db.commit()
            return {'ok':True,'packId':pid,'version':v,'manifestSha256':mh}
        if op == 'chunk':
            pid,v,name=payload.get('packId'),payload.get('version'),payload.get('name')
            offset=payload.get('offset'); encoded=payload.get('contentBase64')
            if not all(isinstance(x,str) for x in (pid,v,name,encoded)) or not isinstance(offset,int) or offset<0 or offset%CHUNK_SIZE or len(encoded)>140000:return {'ok':False,'reason':'bad_chunk'}
            status=db.execute(sa.text('SELECT manifest,status FROM "AssetPackVersion" WHERE packId=:id AND version=:v'),{'id':pid,'v':v}).mappings().first()
            if not status or status['status']!='staging':return {'ok':False,'reason':'not_staging'}
            manifest=json.loads(status['manifest'])
            if not _safe_filename(name) or name not in manifest['files']:return {'ok':False,'reason':'unlisted_resource'}
            try: content=base64.b64decode(encoded,validate=True)
            except Exception:return {'ok':False,'reason':'bad_chunk'}
            if not 0<len(content)<=CHUNK_SIZE or offset//CHUNK_SIZE>=MAX_CHUNKS:return {'ok':False,'reason':'bad_chunk'}
            old=db.execute(sa.text('SELECT content FROM "AssetUploadChunk" WHERE packId=:id AND version=:v AND filename=:name AND offset=:off'),{'id':pid,'v':v,'name':name,'off':offset}).scalar()
            if old is not None:
                return {'ok':old==content,'reason':'already_staged' if old==content else 'chunk_conflict'}
            db.execute(sa.text('INSERT INTO "AssetUploadChunk" (packId,version,filename,offset,content) VALUES (:id,:v,:name,:off,:content)'),{'id':pid,'v':v,'name':name,'off':offset,'content':content})
            db.commit();return {'ok':True,'offset':offset}
        if op == 'finalize':
            pid,v=payload.get('packId'),payload.get('version')
            row=db.execute(sa.text('SELECT manifest,status FROM "AssetPackVersion" WHERE packId=:id AND version=:v'),{'id':pid,'v':v}).mappings().first()
            if not row or row['status']!='staging':return {'ok':False,'reason':'not_staging'}
            manifest=json.loads(row['manifest']); material={}
            for name, digest in manifest['files'].items():
                chunks=db.execute(sa.text('SELECT offset,content FROM "AssetUploadChunk" WHERE packId=:id AND version=:v AND filename=:name ORDER BY offset'),{'id':pid,'v':v,'name':name}).mappings().all()
                actual=0;parts=[]
                for c in chunks:
                    if c['offset']!=actual:return {'ok':False,'reason':'incomplete_resource'}
                    parts.append(c['content']);actual+=len(c['content'])
                data=b''.join(parts)
                if not data or len(data)>MAX_FILE or hashlib.sha256(data).hexdigest()!=digest:return {'ok':False,'reason':'resource_digest_mismatch'}
                material[name]=data
            # Recheck the full canonical validator at the trusted server boundary.
            try:
                with tempfile.TemporaryDirectory(prefix='tavi-asset-ingest-') as tmp:
                    base=Path(tmp);(base/'manifest.json').write_text(row['manifest'],encoding='utf8')
                    for name,data in material.items():
                        f=base/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
                    validate(base)
            except (AssetError,OSError,ValueError):return {'ok':False,'reason':'invalid_pack'}
            for name,data in material.items():
                digest=manifest['files'][name]
                if db.execute(sa.text('SELECT 1 FROM "AssetBlob" WHERE digest=:d'),{'d':digest}).scalar() is None:
                    db.execute(sa.text('INSERT INTO "AssetBlob" (digest,content,byteSize,created) VALUES (:d,:data,:size,:now)'),{'d':digest,'data':data,'size':len(data),'now':now})
                db.execute(sa.text('INSERT INTO "AssetPackResource" (packId,version,filename,digest) VALUES (:id,:v,:name,:d)'),{'id':pid,'v':v,'name':name,'d':digest})
            db.execute(sa.text('UPDATE "AssetPackVersion" SET status=:ready WHERE packId=:id AND version=:v'),{'ready':'ready','id':pid,'v':v})
            db.execute(sa.text('DELETE FROM "AssetUploadChunk" WHERE packId=:id AND version=:v'),{'id':pid,'v':v})
            db.commit();return {'ok':True,'status':'ready'}
        if op in ('publish','revoke'):
            pid,v=payload.get('packId'),payload.get('version')
            if not isinstance(pid,str) or not PACK.fullmatch(pid) or not isinstance(v,str) or not VERSION.fullmatch(v):return {'ok':False,'reason':'bad_request'}
            target='published' if op=='publish' else 'revoked'
            expected='ready' if op=='publish' else 'published'
            result=db.execute(sa.text('UPDATE "AssetPackVersion" SET status=:target WHERE packId=:id AND version=:v AND status=:expected'),{'target':target,'id':pid,'v':v,'expected':expected})
            if result.rowcount!=1:return {'ok':False,'reason':'invalid_transition'}
            actor=payload.get('_verified_actor','unknown')
            db.execute(sa.text('INSERT INTO "AssetPublicationAudit" (packId,version,action,actor,created) VALUES (:id,:v,:op,:actor,:now)'),{'id':pid,'v':v,'op':op,'actor':actor,'now':now})
            db.commit();return {'ok':True,'status':target}
        if op == 'audit':
            rows=db.execute(sa.text('SELECT packId,version,action,actor,created FROM "AssetPublicationAudit" ORDER BY id DESC LIMIT 200')).mappings().all()
            return {'ok':True,'events':[dict(x) for x in rows]}
        if op == 'inspect':
            rows=db.execute(sa.text('SELECT packId,version,status,manifestSha256,created FROM "AssetPackVersion" ORDER BY created DESC LIMIT 200')).mappings().all()
            return {'ok':True,'versions':[dict(x) for x in rows]}
    return {'ok':False,'reason':'unsupported_operation'}


def _dispatch(ctx):
    body=getattr(ctx,'body',None)
    if not isinstance(body,dict):return {'ok':False,'reason':'bad_request'}
    op=body.get('op')
    if op not in {'catalog','resource','begin','chunk','finalize','publish','revoke','inspect','audit'}:return {'ok':False,'reason':'unsupported_operation'}
    if op in {'catalog','resource'} and not (getattr(getattr(ctx,'principal',None),'scopes',None) and 'assets:read' in ctx.principal.scopes):
        return {'ok':False,'reason':'read_auth_required'}
    if op in {'begin','chunk','finalize'} and not _service(ctx,'assets:ingest'):
        return {'ok':False,'reason':'service_auth_required'}
    if op in {'inspect','audit'} and not (_service(ctx,'assets:publish') or _service(ctx,'assets:ingest')):
        return {'ok':False,'reason':'operator_auth_required'}
    if op in {'publish','revoke'} and not _service(ctx,'assets:publish'):
        return {'ok':False,'reason':'publisher_approval_required'}
    payload=dict(body)
    principal=getattr(ctx,'principal',None)
    payload['_verified_actor']=getattr(principal,'subject','') if principal is not None else ''
    return _sql(ctx.session_factory,op,payload)

async def handle(ctx):
    return await run_in_threadpool(_dispatch,ctx)
