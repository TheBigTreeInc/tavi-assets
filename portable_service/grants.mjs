/**
 * TaviX 0.1.11 host-session grant contract validation (reference JS parity).
 * A successful validation is NOT an entitlement, source approval, or proof that
 * the manifest digest is genuine. Only the trusted Tavi host may supply this
 * context after authenticating the session, checking the verified manifest,
 * entitlements, account state, revocations and user approvals.
 */
import {AssetContractError} from './validation.mjs';
const fail = msg => {throw new AssetContractError(msg);};
const plain=x=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.getPrototypeOf(x)===Object.prototype;
const exact=(obj,keys,required=keys)=>plain(obj)&&Object.keys(obj).every(x=>keys.includes(x))&&required.every(x=>Object.hasOwn(obj,x));
const PACK=/^[a-z0-9][a-z0-9._-]{0,126}$/;
const CAP=/^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$/;
const VER=/^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/;
const EXT=/^[a-z][a-z0-9]*(?:[.-][a-z0-9]+){2,}$/;
const SHA=/^[a-f0-9]{64}$/;
const cmp=(a,b)=>{const x=a.split('.').map(BigInt),y=b.split('.').map(BigInt);for(let i=0;i<3;i++){if(x[i]<y[i])return -1;if(x[i]>y[i])return 1;}return 0;};
export function validateTavixAssetDependencies(manifest) {
  if(!plain(manifest))fail('invalid verified extension manifest');
  const permissions=manifest.permissions;
  if(!Array.isArray(permissions)||permissions.length>10||permissions.some(x=>typeof x!=='string')||new Set(permissions).size!==permissions.length||
     !permissions.includes('ui.panel')||permissions.some(x=>!['ui.panel','ui.toast','storage.private','assets.read','assets.preferences.write'].includes(x)))fail('invalid extension permissions');
  if(!Object.hasOwn(manifest,'assetDependencies')) {
    if(permissions.includes('assets.read')||permissions.includes('assets.preferences.write'))fail('asset permissions without declarations');
    return [];
  }
  const deps=manifest.assetDependencies;
  if(!Array.isArray(deps)||deps.length<1||deps.length>16||!permissions.includes('assets.read'))fail('invalid asset dependency declarations');
  const packs=new Set(),allCaps=new Set();let wantsCustomization=false;
  for(const dep of deps) {
    if(!exact(dep,['packId','compatibility','capabilities','optional','requestCustomization'],['packId','compatibility','capabilities','optional']))fail('invalid asset dependency fields');
    if(typeof dep.packId!=='string'||!PACK.test(dep.packId)||packs.has(dep.packId))fail('duplicate or unsafe pack ID');
    packs.add(dep.packId);
    const v=dep.compatibility;
    if(!exact(v,['min','maxExclusive'])||typeof v.min!=='string'||typeof v.maxExclusive!=='string'||!VER.test(v.min)||!VER.test(v.maxExclusive)||cmp(v.min,v.maxExclusive)>=0)fail('invalid asset compatibility range');
    if(!Array.isArray(dep.capabilities)||!dep.capabilities.length||dep.capabilities.length>32||new Set(dep.capabilities).size!==dep.capabilities.length||
       dep.capabilities.some(c=>typeof c!=='string'||!CAP.test(c)))fail('invalid requested asset capabilities');
    dep.capabilities.forEach(c=>allCaps.add(c));
    if(allCaps.size>256)fail('too many requested capabilities');
    if(typeof dep.optional!=='boolean'||(dep.requestCustomization!==undefined&&typeof dep.requestCustomization!=='boolean'))fail('invalid dependency flags');
    wantsCustomization||=dep.requestCustomization===true;
  }
  if(wantsCustomization!==permissions.includes('assets.preferences.write'))fail('asset customization permission disagreement');
  return deps;
}
/** Fail closed on malformed, wrong-extension, wrong-revision, or excessive grants. */
export function validateTavixHostContext(context) {
  if(!exact(context,['projection','verifiedManifest','verifiedManifestSha256','requirements'],['projection','verifiedManifest','verifiedManifestSha256']))fail('trusted host context required');
  const {projection:g,verifiedManifest:manifest,verifiedManifestSha256:digest}=context;
  const deps=validateTavixAssetDependencies(manifest);
  if(!exact(g,['schema','extensionId','extensionVersion','manifestSha256','scope','grants'])||
     g.schema!=='tavix.asset-grants/v1'||g.scope!=='host-session'||
     typeof g.extensionId!=='string'||g.extensionId.length>120||!EXT.test(g.extensionId)||
     typeof g.extensionVersion!=='string'||!VER.test(g.extensionVersion)||
     typeof digest!=='string'||!SHA.test(digest)||g.manifestSha256!==digest||
     g.extensionId!==manifest.id||g.extensionVersion!==manifest.version)fail('host asset grant identity or digest mismatch');
  if(!Array.isArray(g.grants)||g.grants.length>16)fail('invalid per-pack grant list');
  const requested=new Map(deps.map(d=>[d.packId,d]));
  const byPack=new Map();
  for(const item of g.grants) {
    if(!exact(item,['packId','capabilities','canCustomize'])||typeof item.packId!=='string'||!PACK.test(item.packId)||
       byPack.has(item.packId)||!requested.has(item.packId))fail('undeclared or duplicate pack grant');
    if(item.capabilities===requested.get(item.packId).capabilities||!Array.isArray(item.capabilities)||item.capabilities.length<1||item.capabilities.length>32||
       new Set(item.capabilities).size!==item.capabilities.length||
       item.capabilities.some(cap=>typeof cap!=='string'||!CAP.test(cap)||!requested.get(item.packId).capabilities.includes(cap)))fail('unrequested capability grant');
    if(typeof item.canCustomize!=='boolean'||(item.canCustomize&&
       (!requested.get(item.packId).requestCustomization||!manifest.permissions.includes('assets.preferences.write'))))fail('unrequested customization grant');
    byPack.set(item.packId,{capabilities:new Set(item.capabilities),canCustomize:item.canCustomize,compatibility:requested.get(item.packId).compatibility});
  }
  if(Object.hasOwn(context,'requirements')) {
    if(!plain(context.requirements)||context.requirements.applicationId!==g.extensionId)fail('requirements identity mismatch');
  }
  return {applicationId:g.extensionId,byPack,requirements:context.requirements??null};
}
export function withinVersion(version,range) {
  return typeof version==='string'&&VER.test(version)&&cmp(version,range.min)>=0&&cmp(version,range.maxExclusive)<0;
}
