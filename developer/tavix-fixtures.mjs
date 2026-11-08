/**
 * TEST-ONLY host context builder. This synthesizes a fake fixture extension
 * manifest and digest; it is NOT an authentication, entitlement or user
 * consent implementation. Production hosts must verify their actual sources.
 */
import {createHash} from 'node:crypto';
export function fixtureTavixContext({applicationId,packCapabilities,canCustomize=false,requirements=null,
  extensionVersion='0.1.0',optional=true,compatibility={min:'0.0.0',maxExclusive:'99.0.0'}}) {
  if(!packCapabilities||typeof packCapabilities!=='object')throw new TypeError('explicit pack grants required');
  const entries=Object.entries(packCapabilities);
  const permissionWrite=entries.some(([pack])=>typeof canCustomize==='boolean'?canCustomize:canCustomize[pack]===true);
  const isWritable=pack=>typeof canCustomize==='boolean'?canCustomize:canCustomize[pack]===true;
  const verifiedManifest={schema:'tavi.extension/v1',id:applicationId,version:extensionVersion,
    permissions:['ui.panel','assets.read',...(permissionWrite?['assets.preferences.write']:[])],
    assetDependencies:entries.map(([packId,capabilities])=>({packId,compatibility,capabilities:[...capabilities],
      optional,requestCustomization:isWritable(packId)}))};
  const verifiedManifestSha256=createHash('sha256').update(JSON.stringify(verifiedManifest)).digest('hex');
  const projection={schema:'tavix.asset-grants/v1',extensionId:applicationId,extensionVersion,
    manifestSha256:verifiedManifestSha256,scope:'host-session',
    grants:entries.map(([packId,capabilities])=>({packId,capabilities:[...capabilities],canCustomize:isWritable(packId)}))};
  return {projection,verifiedManifest,verifiedManifestSha256,...(requirements?{requirements}:{})};
}
