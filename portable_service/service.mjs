/** Host-owned embeddable Tavi Assets reference service. Do NOT expose this privileged object to extensions. */
import {AssetContractError,assertId,assertCapability,validatePack,manifestRevision,formats,decodeBase64,encodeBase64,cloneJSON} from './validation.mjs';
import {resolveAssetRequirements, requirementsFromTavix} from './dependencies.mjs';
import {validateTavixHostContext,withinVersion} from './grants.mjs';
const fail=(s)=>{throw new AssetContractError(s);};
const semver=(s)=>s.split('.').map(Number);
const compare=(a,b)=>{const x=semver(a),y=semver(b);for(let i=0;i<3;i++)if(x[i]!==y[i])return x[i]-y[i];return 0;};
const appId=(s)=>assertId(s,'application ID');
function ensureState(s) { if(s?.schema!=='tavi.assets.runtime-store/v1'||!s.installed||!s.preferences?.global||!s.preferences?.applications)fail('invalid storage state'); }
function getRecord(s,packId) { const item=Object.hasOwn(s.installed,packId)?s.installed[packId]:null;if(!item)fail('pack not installed');return item; }
function prefs(s,scope,packId,app) { return scope==='app'?s.preferences.applications[app]?.[packId]??{}:s.preferences.global[packId]??{}; }
function selected(s,packId,capability,app) {
  const resource=getRecord(s,packId).manifest.resources[capability]; if(!resource)fail('unknown capability');
  const variants=resource.variants??{};
  for(const value of [app?prefs(s,'app',packId,app)[capability]:null,prefs(s,'global',packId)[capability]]) {
    if(typeof value==='string'&&Object.hasOwn(variants,value))return {file:variants[value],selected:value};
  }
  return {file:resource.default, selected:null};
}
export class AssetService {
  #storage; #approve;
  constructor({storage,authorizeInstall}) {
    if(!storage||typeof storage.read!=='function'||typeof storage.transact!=='function')throw new TypeError('Atomic storage adapter required');
    if(typeof authorizeInstall!=='function')throw new TypeError('Trusted install authorizer required (default deny)');
    this.#storage=storage;this.#approve=authorizeInstall;
  }
  async install({manifest,files,origin}) {
    // Caller MUST be trusted host code, never the extension wire interface.
    // Take defensive copies before async verification: caller buffers cannot mutate after validation.
    const safeManifest=cloneJSON(manifest);
    const safeFiles=Object.fromEntries(Object.entries(files).map(([name,bytes])=>[name,bytes.slice()]));
    await validatePack(safeManifest,safeFiles);
    const allowed=await this.#approve({packId:safeManifest.id,version:safeManifest.version,origin,manifestSha256:await manifestRevision(safeManifest)});
    if(allowed!==true)fail('installation authorization denied');
    const encoded={};for(const [path,bytes] of Object.entries(safeFiles)) encoded[path]=encodeBase64(bytes);
    return this.#storage.transact(s=>{
      ensureState(s);const previous=s.installed[safeManifest.id];
      if(previous&&compare(previous.manifest.version,safeManifest.version)>0)fail('downgrade blocked');
      if(previous&&previous.manifest.version===safeManifest.version) {
        if(JSON.stringify(previous.manifest)!==JSON.stringify(safeManifest)||Object.keys(encoded).some(k=>previous.files[k]!==encoded[k]))fail('immutable version conflict');
        return {packId:safeManifest.id,version:safeManifest.version,changed:false};
      }
      s.installed[safeManifest.id]={manifest:safeManifest,files:encoded};
      return {packId:safeManifest.id,version:safeManifest.version,changed:true};
    });
  }
  async #validated(packId) {
    const s=await this.#storage.read();ensureState(s);
    const pack=getRecord(s,assertId(packId));
    const files={};
    for(const [name,encoded] of Object.entries(pack.files))files[name]=decodeBase64(encoded);
    await validatePack(pack.manifest,files);
    return {s,pack};
  }
  async describe(packId) {
    assertId(packId,'pack ID');const {pack}=await this.#validated(packId);
    const m=pack.manifest;
    return {schema:'tavi.assets.pack-info/v1',packId,version:m.version,type:m.type,display:m.display??{},tags:m.tags??[],taxonomy:m.taxonomy??{},capabilities:Object.keys(m.resources),objectCount:Object.keys(m.objects??{}).length,collectionCount:Object.keys(m.collections??{}).length};
  }
  async listInstalled() { const s=await this.#storage.read();ensureState(s);return Object.fromEntries(Object.entries(s.installed).map(([id,v])=>[id,v.manifest.version])); }
  async getManifest(packId) { const {pack}=await this.#validated(packId);return cloneJSON(pack.manifest); }
  async listObjects(packId,{kind,rarity,tags=[],offset=0,limit=100}={}) {
    if(!Array.isArray(tags)||tags.length>32||tags.some(t=>typeof t!=='string')||(kind!==undefined&&typeof kind!=='string')||(rarity!==undefined&&typeof rarity!=='string')||!Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1||limit>100)fail('invalid metadata filter');
    const m=await this.getManifest(packId);
    const rows=Object.entries(m.objects??{}).filter(([,o])=>(kind===undefined||o.kind===kind)&&(rarity===undefined||o.rarity===rarity)&&tags.every(tag=>(o.tags??[]).includes(tag))).sort((a,b)=>a[0].localeCompare(b[0]));
    return {schema:'tavi.assets.object-list/v1',packId,version:m.version,total:rows.length,nextOffset:offset+limit<rows.length?offset+limit:null,items:rows.slice(offset,offset+limit).map(([id,o])=>({...o,id}))};
  }
  // Trust-bound cross-pack discovery. This is metadata ONLY, not an entitlement oracle.
  async discoverObjects(packIds,{kind,tags=[],offset=0,limit=100}={}) {
    if(!Array.isArray(packIds)||packIds.length>32||!Array.isArray(tags)||tags.length>32||
       tags.some(t=>typeof t!=='string')||(kind!==undefined&&typeof kind!=='string')||
       !Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1||limit>100)fail('invalid discovery filter');
    const rows=[];
    for(const packId of [...new Set(packIds)].sort()) {
      assertId(packId);
      const m=await this.getManifest(packId);
      for(const [objectId,obj] of Object.entries(m.objects??{})) {
        if((kind!==undefined&&obj.kind!==kind)||!tags.every(t=>(obj.tags??[]).includes(t)))continue;
        rows.push({packId,version:m.version,object:{id:objectId,...obj}});
      }
    }
    rows.sort((a,b)=>a.packId.localeCompare(b.packId)||a.object.id.localeCompare(b.object.id));
    return {schema:'tavi.assets.discovery/v1',total:rows.length,nextOffset:offset+limit<rows.length?offset+limit:null,items:rows.slice(offset,offset+limit)};
  }
  async getObject(packId,objectId) { const m=await this.getManifest(packId);const obj=m.objects?.[objectId];if(!obj)fail('unknown object');return {schema:'tavi.assets.object/v1',packId,version:m.version,object:{id:objectId,...obj}}; }
  async listCollections(packId,{kind}={}) { const m=await this.getManifest(packId);return {schema:'tavi.assets.collection-list/v1',packId,version:m.version,items:Object.entries(m.collections??{}).filter(([,o])=>!kind||o.kind===kind).map(([id,o])=>({id,kind:o.kind,name:o.name,tags:o.tags??[],objectCount:o.entries.length}))}; }
  async getCollection(packId,collectionId) { const m=await this.getManifest(packId);const col=m.collections?.[collectionId];if(!col)fail('unknown collection');return {schema:'tavi.assets.collection/v1',packId,version:m.version,id:collectionId,...col}; }
  async setGlobalPreference(packId,capability,variant) { return this.#setPreference(packId,capability,variant,null); }
  async setApplicationPreference(app,packId,capability,variant) { appId(app);return this.#setPreference(packId,capability,variant,app); }
  async #setPreference(packId,capability,variant,app) {
    assertId(packId);assertCapability(capability);assertCapability(variant,'variant');
    return this.#storage.transact(s=>{ensureState(s);const resource=getRecord(s,packId).manifest.resources[capability];
      if(!resource||!Object.hasOwn(resource.variants??{},variant))fail('unknown variant');
      const target=app?(s.preferences.applications[app]??={}):s.preferences.global;
      (target[packId]??={})[capability]=variant;
      return {packId,capability,variant,scope:app?'application':'global'};
    });
  }
  async preferences(packId,app=null) { assertId(packId);if(app!==null)appId(app);const {s,pack}=await this.#validated(packId);const m=pack.manifest;
    return {schema:'tavi.assets.preferences/v1',packId,items:Object.entries(m.resources).map(([capability,v])=>({capability,available:Object.keys(v.variants??{}),selected:selected(s,packId,capability,app).selected}))};
  }
  async resolve(packId,capability,app=null) { assertId(packId);assertCapability(capability);if(app!==null)appId(app);const {s,pack}=await this.#validated(packId);
    const {file,selected:variant}=selected(s,packId,capability,app);const bytes=decodeBase64(pack.files[file]);
    if(bytes.length>2*1024*1024)fail('resource too large for inline host transport');
    const suffix=file.split('.').pop().toLowerCase();return {schema:'tavi.assets.resource/v1',packId,version:pack.manifest.version,capability,contentType:formats[suffix],encoding:'base64',data:encodeBase64(bytes),selected:variant};
  }
  async uninstall(packId) { assertId(packId);return this.#storage.transact(s=>{ensureState(s);if(!s.installed[packId])fail('pack not installed');delete s.installed[packId];return {removed:packId};}); }
}
/**
 * Host-only dispatcher. getTrustedContext MUST use the authenticated Tavi
 * session to return {projection, verifiedManifest, verifiedManifestSha256,
 * requirements?}. The projection is the reviewed TaviX grant schema, never
 * request parameters or data from the asset pack. Host policy MUST also
 * check account entitlements, user consent and revocation on each call.
 */
export class TrustedAssetHostBridge {
  #service; #trustedContext;
  constructor(service,getTrustedContext) {
    if(!(service instanceof AssetService)||typeof getTrustedContext!=='function')throw new TypeError('trusted TaviX host context resolver required');
    this.#service=service;this.#trustedContext=getTrustedContext;
  }
  async dispatch(trustedSession,method,params) {
    if(!params||typeof params!=='object'||Array.isArray(params)||typeof method!=='string')fail('invalid request');
    const shapes={
      'assets.describe':[['packId'],[]], 'assets.objects.list':[['packId'],['kind','rarity','tags','offset','limit']],
      'assets.objects.get':[['packId','objectId'],[]], 'assets.collections.list':[['packId'],['kind']],
      'assets.collections.get':[['packId','collectionId'],[]], 'assets.preferences.get':[['packId'],[]],
      'assets.preferences.set':[['packId','capability','variant'],[]], 'assets.resolve':[['packId','capability'],[]],
      'assets.packs.list':[[],['type','tags','offset','limit']],
      'assets.objects.discover':[[],['kind','tags','offset','limit']],
      'assets.composition.resolve':[['components'],[]],
      'assets.dependencies.status':[[],[]]
    };
    const shape=shapes[method];
    if(!shape||shape[0].some(k=>!Object.hasOwn(params,k))||Object.keys(params).some(k=>!shape[0].includes(k)&&!shape[1].includes(k)))fail('unsupported or unsafe request');
    // Refresh the grant every request. A cached grant would survive revocation.
    const context=await this.#trustedContext(trustedSession);
    const auth=validateTavixHostContext(context);
    const packGrant=packId=>{
      assertId(packId);const entry=auth.byPack.get(packId);
      if(!entry)fail('host access denied');
      return entry;
    };
    const allowed=async packId=>{
      const grant=packGrant(packId);
      const manifest=await this.#service.getManifest(packId);
      if(!withinVersion(manifest.version,grant.compatibility))fail('host access denied: incompatible pack version');
      return {manifest,grant};
    };
    const canUse=(object,grant)=>Array.isArray(object.resources)&&object.resources.some(cap=>grant.capabilities.has(cap));
    const visibleObject=(id,obj,grant)=>({id,...obj,resources:obj.resources.filter(c=>grant.capabilities.has(c))});
    const visibleEntries=(m,collection,grant)=>collection.entries.filter(e=>canUse(m.objects[e.objectId],grant));
    const filter=(list,fields)=>{
      const {offset=0,limit=100}=params;
      if(!Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1||limit>100)fail('invalid metadata pagination');
      return {total:list.length,nextOffset:offset+limit<list.length?offset+limit:null,items:list.slice(offset,offset+limit),...fields};
    };
    const requireCapability=(grant,capability)=>{
      assertCapability(capability);
      if(!grant.capabilities.has(capability))fail('host access denied');
    };
    const listGranted=async()=>{
      const items=[];
      for(const packId of [...auth.byPack.keys()].sort()) {
        try {const {manifest,grant}=await allowed(packId);items.push({packId,manifest,grant});}
        catch(e) {if(e instanceof AssetContractError)continue;throw e;}
      }
      return items;
    };
    if(Object.hasOwn(params,'packId'))await allowed(params.packId);
    switch(method) {
      case 'assets.dependencies.status': {
        const requirements=auth.requirements??requirementsFromTavix(context.verifiedManifest);
        const manifests=(await listGranted()).map(x=>x.manifest);
        return resolveAssetRequirements(requirements,manifests,context);
      }
      case 'assets.packs.list': {
        const {type,tags=[]}=params;
        if((type!==undefined&&typeof type!=='string')||!Array.isArray(tags)||tags.length>32||tags.some(t=>typeof t!=='string'))fail('invalid discovery filter');
        const items=[];
        for(const {packId,manifest,grant} of await listGranted()) {
          if((type!==undefined&&manifest.type!==type)||!tags.every(t=>(manifest.tags??[]).includes(t)))continue;
          items.push({schema:'tavi.assets.pack-info/v1',packId,version:manifest.version,type:manifest.type,
            display:manifest.display??{},tags:manifest.tags??[],taxonomy:manifest.taxonomy??{},
            capabilities:Object.keys(manifest.resources).filter(c=>grant.capabilities.has(c)),
            objectCount:Object.values(manifest.objects??{}).filter(o=>canUse(o,grant)).length,
            collectionCount:Object.values(manifest.collections??{}).filter(c=>visibleEntries(manifest,c,grant).length>0).length});
        }
        return {schema:'tavi.assets.pack-list/v1',...filter(items)};
      }
      case 'assets.objects.discover': {
        const {kind,tags=[]}=params;
        if((kind!==undefined&&typeof kind!=='string')||!Array.isArray(tags)||tags.length>32||tags.some(t=>typeof t!=='string'))fail('invalid discovery filter');
        const rows=[];
        for(const {packId,manifest,grant} of await listGranted())for(const [id,obj] of Object.entries(manifest.objects??{})) {
          if(!canUse(obj,grant)||(kind!==undefined&&obj.kind!==kind)||!tags.every(t=>(obj.tags??[]).includes(t)))continue;
          rows.push({packId,version:manifest.version,object:visibleObject(id,obj,grant)});
        }
        rows.sort((a,b)=>a.packId.localeCompare(b.packId)||a.object.id.localeCompare(b.object.id));
        return {schema:'tavi.assets.discovery/v1',...filter(rows)};
      }
      case 'assets.composition.resolve': {
        const components=params.components;
        if(!Array.isArray(components)||!components.length||components.length>12)fail('invalid composition');
        const slots=new Set(),results=[];let totalBytes=0;
        for(const part of components) {
          if(!part||typeof part!=='object'||Array.isArray(part)||Object.keys(part).sort().join(',')!=='capability,packId,slot')fail('invalid composition component');
          const {slot,packId,capability}=part;
          assertCapability(slot,'slot');assertId(packId);
          const {grant}=await allowed(packId);requireCapability(grant,capability);
          if(slots.has(slot))fail('duplicate composition slot');slots.add(slot);
          const resource=await this.#service.resolve(packId,capability,auth.applicationId);
          totalBytes+=Math.ceil(resource.data.length*3/4);
          if(totalBytes>4*1024*1024)fail('composition response too large');
          results.push({slot,...resource});
        }
        return {schema:'tavi.assets.composition/v1',items:results};
      }
      case 'assets.describe': {
        const {manifest:m,grant}=await allowed(params.packId);
        return {schema:'tavi.assets.pack-info/v1',packId:params.packId,version:m.version,type:m.type,
          display:m.display??{},tags:m.tags??[],taxonomy:m.taxonomy??{},
          capabilities:Object.keys(m.resources).filter(c=>grant.capabilities.has(c)),
          objectCount:Object.values(m.objects??{}).filter(o=>canUse(o,grant)).length,
          collectionCount:Object.values(m.collections??{}).filter(c=>visibleEntries(m,c,grant).length>0).length};
      }
      case 'assets.objects.list': {
        const {manifest:m,grant}=await allowed(params.packId);
        const {kind,rarity,tags=[]}=params;
        if((kind!==undefined&&typeof kind!=='string')||(rarity!==undefined&&typeof rarity!=='string')||
           !Array.isArray(tags)||tags.length>32||tags.some(t=>typeof t!=='string'))fail('invalid metadata filter');
        const rows=Object.entries(m.objects??{}).filter(([,o])=>canUse(o,grant)&&
          (kind===undefined||o.kind===kind)&&(rarity===undefined||o.rarity===rarity)&&
          tags.every(t=>(o.tags??[]).includes(t))).sort((a,b)=>a[0].localeCompare(b[0])).map(([id,o])=>visibleObject(id,o,grant));
        return {schema:'tavi.assets.object-list/v1',packId:params.packId,version:m.version,...filter(rows)};
      }
      case 'assets.objects.get': {
        const {manifest:m,grant}=await allowed(params.packId);
        const obj=m.objects?.[params.objectId];if(!obj||!canUse(obj,grant))fail('unknown or unauthorized object');
        return {schema:'tavi.assets.object/v1',packId:params.packId,version:m.version,object:visibleObject(params.objectId,obj,grant)};
      }
      case 'assets.collections.list': {
        const {manifest:m,grant}=await allowed(params.packId);
        return {schema:'tavi.assets.collection-list/v1',packId:params.packId,version:m.version,
          items:Object.entries(m.collections??{}).filter(([,c])=>(!params.kind||c.kind===params.kind)&&visibleEntries(m,c,grant).length>0)
          .map(([id,c])=>({id,kind:c.kind,name:c.name,tags:c.tags??[],objectCount:visibleEntries(m,c,grant).length}))};
      }
      case 'assets.collections.get': {
        const {manifest:m,grant}=await allowed(params.packId);
        const c=m.collections?.[params.collectionId];if(!c)fail('unknown collection');
        const entries=visibleEntries(m,c,grant);if(!entries.length)fail('unknown or unauthorized collection');
        return {schema:'tavi.assets.collection/v1',packId:params.packId,version:m.version,id:params.collectionId,...c,entries};
      }
      case 'assets.preferences.get': {
        const {grant}=await allowed(params.packId);
        const out=await this.#service.preferences(params.packId,auth.applicationId);
        return {...out,items:out.items.filter(x=>grant.capabilities.has(x.capability))};
      }
      case 'assets.preferences.set': {
        const {grant}=await allowed(params.packId);
        requireCapability(grant,params.capability);
        if(!grant.canCustomize)fail('host customization denied');
        await this.#service.setApplicationPreference(auth.applicationId,params.packId,params.capability,params.variant);
        const out=await this.#service.preferences(params.packId,auth.applicationId);
        return {...out,items:out.items.filter(x=>grant.capabilities.has(x.capability))};
      }
      case 'assets.resolve': {
        const {grant}=await allowed(params.packId);requireCapability(grant,params.capability);
        return this.#service.resolve(params.packId,params.capability,auth.applicationId);
      }
      default:fail('unsupported method');
    }
  }
}
