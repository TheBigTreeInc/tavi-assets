/** Host-owned embeddable Tavi Assets reference service. Do NOT expose this privileged object to extensions. */
import {AssetContractError,assertId,assertCapability,validatePack,manifestRevision,formats,decodeBase64,encodeBase64,cloneJSON} from './validation.mjs';
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
    if(!Array.isArray(tags)||tags.some(t=>typeof t!=='string')||!Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1||limit>100)fail('invalid metadata filter');
    const m=await this.getManifest(packId);
    const rows=Object.entries(m.objects??{}).filter(([,o])=>(kind===undefined||o.kind===kind)&&(rarity===undefined||(o.rarity??'common')===rarity)&&tags.every(tag=>(o.tags??[]).includes(tag))).sort((a,b)=>a[0].localeCompare(b[0]));
    return {schema:'tavi.assets.object-list/v1',packId,version:m.version,total:rows.length,nextOffset:offset+limit<rows.length?offset+limit:null,items:rows.slice(offset,offset+limit).map(([id,o])=>({...o,id}))};
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
/** Authorized host adapter; never accepts grants, caller identity or arbitrary paths from params. */
export class TrustedAssetHostBridge {
  #service; #grants;
  constructor(service,getTrustedGrant) { if(!(service instanceof AssetService)||typeof getTrustedGrant!=='function')throw new TypeError('trusted grant resolver required');this.#service=service;this.#grants=getTrustedGrant; }
  async dispatch(trustedSession,method,params) {
    if(!params||typeof params!=='object'||Array.isArray(params)||typeof method!=='string')fail('invalid request');
    const shapes={
      'assets.describe': [['packId'],[]], 'assets.objects.list':[['packId'],['kind','rarity','tags','offset','limit']],
      'assets.objects.get':[['packId','objectId'],[]], 'assets.collections.list':[['packId'],['kind']],
      'assets.collections.get':[['packId','collectionId'],[]], 'assets.preferences.get':[['packId'],[]],
      'assets.preferences.set':[['packId','capability','variant'],[]], 'assets.resolve':[['packId','capability'],[]]};
    const shape=shapes[method];if(!shape||shape[0].some(k=>!Object.hasOwn(params,k))||Object.keys(params).some(k=>!shape[0].includes(k)&&!shape[1].includes(k)))fail('unsupported or unsafe request');
    const grant=await this.#grants(trustedSession);
    if(!grant || !Array.isArray(grant.packs) || !grant.packs.includes(params.packId))fail('host access denied');
    const pack=params.packId,cap=params.capability;
    const allowed=new Set(grant.capabilities??[]);
    const scoped=(value)=>{
      if(method==='assets.describe')return {...value,capabilities:value.capabilities.filter(x=>allowed.has(x))};
      if(method==='assets.objects.list')return {...value,items:value.items.map(o=>({...o,resources:(o.resources??[]).filter(x=>allowed.has(x))}))};
      if(method==='assets.objects.get')return {...value,object:{...value.object,resources:(value.object.resources??[]).filter(x=>allowed.has(x))}};
      if(method==='assets.preferences.get')return {...value,items:value.items.filter(o=>allowed.has(o.capability))};
      return value;
    };
    if(['assets.resolve','assets.preferences.set'].includes(method) && !allowed.has(cap))fail('host access denied');
    switch(method){
      case 'assets.describe':return scoped(await this.#service.describe(pack));
      case 'assets.objects.list':return scoped(await this.#service.listObjects(pack,params));
      case 'assets.objects.get':return scoped(await this.#service.getObject(pack,params.objectId));
      case 'assets.collections.list':return this.#service.listCollections(pack,params);
      case 'assets.collections.get':return this.#service.getCollection(pack,params.collectionId);
      case 'assets.preferences.get':return scoped(await this.#service.preferences(pack,grant.applicationId));
      case 'assets.preferences.set':
        if(grant.canCustomize!==true||grant.applicationId===undefined)fail('host customization denied');
        await this.#service.setApplicationPreference(grant.applicationId,pack,cap,params.variant);
        return scoped(await this.#service.preferences(pack,grant.applicationId));
      case 'assets.resolve':return this.#service.resolve(pack,cap,grant.applicationId??null);
      default:fail('unsupported method');
    }
  }
}
