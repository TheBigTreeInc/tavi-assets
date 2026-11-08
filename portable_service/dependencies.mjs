/** Pure reference resolver for host-verified TaviX asset declarations.
 * Never performs downloads, grants, purchases, wallet operations, or catalog lookups.
 * Input manifests must already have been verified by the Tavi Assets pack validator.
 */
import {AssetContractError} from './validation.mjs';
import {validateTavixHostContext,validateTavixAssetDependencies,withinVersion} from './grants.mjs';
const fail = reason => {throw new AssetContractError(reason);};
const ID = /^[a-z0-9][a-z0-9._-]{0,126}$/;
const VERSION = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
const plain = x => x !== null && typeof x === 'object' && !Array.isArray(x) && Object.getPrototypeOf(x) === Object.prototype;
const exact = (value, keys, required) => plain(value) && Object.keys(value).every(key => keys.includes(key)) && required.every(key => Object.hasOwn(value, key));
function id(x) { if(typeof x!=='string' || !ID.test(x)) fail('invalid requirements identifier'); }
function version(x) { if(typeof x!=='string'||x.length>64||!VERSION.test(x))fail('invalid version'); }
function cmp(a,b) {
  const av=a.split('.').map(BigInt),bv=b.split('.').map(BigInt);
  for(let i=0;i<3;i++) {if(av[i]<bv[i])return -1;if(av[i]>bv[i])return 1;}
  return 0;
}
const dependencyKey = d => `${d.packId??'*'}|${d.capability}`;
export function validateAssetRequirements(input) {
  if(!exact(input,['schema','applicationId','features'],['schema','applicationId','features'])||input.schema!=='tavi.assets.requirements/v1')fail('invalid dependency declaration');
  id(input.applicationId);
  if(!Array.isArray(input.features)||input.features.length<1||input.features.length>32)fail('invalid dependency features');
  const featureIds=new Set();
  for(const feature of input.features) {
    if(!exact(feature,['id','required','optional','fallback'],['id','required','optional','fallback']))fail('invalid dependency feature');
    id(feature.id);
    if(featureIds.has(feature.id))fail('duplicate dependency feature');
    featureIds.add(feature.id);
    if(!['bundled','none'].includes(feature.fallback))fail('invalid dependency fallback');
    const keys=new Set();
    for(const group of ['required','optional']) {
      if(!Array.isArray(feature[group])||feature[group].length>16)fail('invalid dependency group');
      for(const dep of feature[group]) {
        if(!exact(dep,['capability','packId','version'],['capability']))fail('invalid dependency entry');
        id(dep.capability);
        if(Object.hasOwn(dep,'packId'))id(dep.packId);
        if(Object.hasOwn(dep,'version')) {
          if(!exact(dep.version,['min','maxExclusive'],['min','maxExclusive']))fail('invalid dependency range');
          version(dep.version.min);version(dep.version.maxExclusive);
          if(cmp(dep.version.min,dep.version.maxExclusive)>=0)fail('invalid dependency range order');
        }
        const key=dependencyKey(dep);
        if(keys.has(key))fail('duplicate dependency');
        keys.add(key);
      }
    }
    if(feature.required.length+feature.optional.length===0)fail('empty dependency feature');
  }
  return true;
}
/**
 * Inventory and grant are trusted host inputs. The result is only a readiness report,
 * not an entitlement, purchase, install plan, executable feature or access token.
 */
/**
 * When the verified extension only declares TaviX 0.1.11 dependencies,
 * expose one feature per declared pack. Required is per feature and cannot
 * prevent launching a game with bundled graphics.
 */
export function requirementsFromTavix(verifiedManifest) {
  const entries=validateTavixAssetDependencies(verifiedManifest);
  if(!entries.length)fail('verified dependency declaration unavailable');
  return {schema:'tavi.assets.requirements/v1',applicationId:verifiedManifest.id,
    features:entries.map(entry=>{
      const dependencies=entry.capabilities.map(capability=>({capability,packId:entry.packId,version:entry.compatibility}));
      return {id:entry.packId,required:entry.optional?[]:dependencies,
        optional:entry.optional?dependencies:[],fallback:'bundled'};
    })};
}
/**
 * Pure readiness calculation from validated pack manifests and host-issued
 * TaviX scoped grants; no price, ownership, download or install side effects.
 */
export function resolveAssetRequirements(declaration, installedManifests, context) {
  validateAssetRequirements(declaration);
  const {applicationId,byPack}=validateTavixHostContext(context);
  if(declaration.applicationId!==applicationId)fail('dependency application identity mismatch');
  if(!Array.isArray(installedManifests)||installedManifests.length>256)fail('invalid trusted dependency inventory');
  const manifests=new Map();
  for(const manifest of installedManifests) {
    if(!plain(manifest)||typeof manifest.id!=='string'||!ID.test(manifest.id)||
      typeof manifest.version!=='string'||!VERSION.test(manifest.version)||!plain(manifest.resources))fail('invalid installed manifest');
    if(manifests.has(manifest.id))fail('duplicate installed manifest');
    manifests.set(manifest.id,manifest);
  }
  const candidates=[...manifests.values()].filter(m=>byPack.has(m.id)&&withinVersion(m.version,byPack.get(m.id).compatibility))
    .sort((a,b)=>a.id.localeCompare(b.id));
  const match=dep=>{
    for(const manifest of candidates) {
      if(dep.packId!==undefined&&manifest.id!==dep.packId)continue;
      const grant=byPack.get(manifest.id);
      if(!grant.capabilities.has(dep.capability)||!Object.hasOwn(manifest.resources,dep.capability))continue;
      if(dep.version&&!withinVersion(manifest.version,dep.version))continue;
      return {packId:manifest.id,version:manifest.version,capability:dep.capability};
    }
    return null;
  };
  const features=declaration.features.map(feature=>{
    const dependencies={};
    for(const group of ['required','optional'])dependencies[group]=feature[group].map(dep=>{
      const selected=match(dep);
      return {capability:dep.capability,packId:dep.packId??null,available:!!selected,selected};
    });
    return {id:feature.id,ready:dependencies.required.every(x=>x.available),fallback:feature.fallback,...dependencies};
  });
  return {schema:'tavi.assets.dependency-status/v1',applicationId,features};
}
