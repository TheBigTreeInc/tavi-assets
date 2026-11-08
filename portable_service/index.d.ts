/** Tavi Assets portable reference runtime. Host-side only; NEVER bundle into a third-party extension. */
export interface PackManifest {
  schema: 'tavi.assets.pack/v1'; id: string; version: string; type: string;
  compatibility: {host: 'tavi-assets/v1'};
  files: Record<string,string>;
  resources: Record<string,{default:string;variants?:Record<string,string>}>;
  display?: {name?: string;description?: string;style?: string}; tags?: string[];
  taxonomy?: Record<string,unknown>;
  objects?: Record<string,unknown>; collections?: Record<string,unknown>;
}
export interface ApprovedLocalSource {manifest:PackManifest;files:Record<string,Uint8Array>;origin:string}
export interface StorageAdapter {
  read():Promise<Record<string,unknown>>;
  /** Must be a serialized, atomic transaction; reject without committing on error. */
  transact<T>(callback:(state:any)=>T|Promise<T>):Promise<T>;
}
export interface InstallAuthorizationInput {packId:string;version:string;origin:string;manifestSha256:string}
export declare class AssetService {
  constructor(options:{storage:StorageAdapter;authorizeInstall(input:InstallAuthorizationInput):Promise<boolean>|boolean});
  install(source:ApprovedLocalSource):Promise<{packId:string;version:string;changed:boolean}>;
  describe(packId:string):Promise<Record<string,unknown>>;
  listInstalled():Promise<Record<string,string>>;
  getManifest(packId:string):Promise<PackManifest>;
  listObjects(packId:string,filters?:{kind?:string;rarity?:string;tags?:string[];offset?:number;limit?:number}):Promise<Record<string,unknown>>;
  getObject(packId:string,objectId:string):Promise<Record<string,unknown>>;
  listCollections(packId:string,filters?:{kind?:string}):Promise<Record<string,unknown>>;
  getCollection(packId:string,collectionId:string):Promise<Record<string,unknown>>;
  /** Privileged Tavi Settings UI only; not an extension operation. */
  setGlobalPreference(packId:string,capability:string,variant:string):Promise<Record<string,unknown>>;
  setApplicationPreference(appId:string,packId:string,capability:string,variant:string):Promise<Record<string,unknown>>;
  preferences(packId:string,appId?:string|null):Promise<Record<string,unknown>>;
  resolve(packId:string,capability:string,appId?:string|null):Promise<{schema:'tavi.assets.resource/v1';packId:string;version:string;capability:string;contentType:string;encoding:'base64';data:string;selected:string|null}>;
  uninstall(packId:string):Promise<{removed:string}>;
}
/** TaviX 0.1.11 host-issued, per-pack grant; NOT an extension manifest field. */
export interface TavixAssetGrantProjection {
  schema:'tavix.asset-grants/v1';extensionId:string;extensionVersion:string;
  manifestSha256:string;scope:'host-session';
  grants:Array<{packId:string;capabilities:string[];canCustomize:boolean}>;
}
/** The real trusted host supplies the verified manifest and matching digest. */
export interface TrustedAssetHostContext {
  projection:TavixAssetGrantProjection;
  verifiedManifest:{id:string;version:string;permissions:string[];assetDependencies?:Array<{
    packId:string;compatibility:{min:string;maxExclusive:string};capabilities:string[];
    optional:boolean;requestCustomization?:boolean
  }>};
  verifiedManifestSha256:string;
  /** Additional application-feature groupings from verified host metadata only. */
  requirements?:AssetRequirements;
}
export declare class TrustedAssetHostBridge {
  constructor(service:AssetService, getTrustedContext:(trustedSession:unknown)=>Promise<TrustedAssetHostContext|null>|TrustedAssetHostContext|null);
  dispatch(trustedSession:unknown,method:string,params:Record<string,unknown>):Promise<Record<string,unknown>>;
}
export declare class MemoryAssetStorage implements StorageAdapter { constructor(initial?:Record<string,unknown>);read():Promise<Record<string,unknown>>;transact<T>(cb:(state:any)=>T|Promise<T>):Promise<T>;exportForTesting():Record<string,unknown> }
export declare class AssetContractError extends Error {}
export declare function validateManifest(manifest:PackManifest):true;
export declare function validatePack(manifest:PackManifest,files:Record<string,Uint8Array>):Promise<true>;
export declare function manifestRevision(manifest:PackManifest):Promise<string>;

/** TaviX proposal only: not an accepted TaviX extension manifest field. */
export interface AssetDependency {capability:string;packId?:string;version?:{min:string;maxExclusive:string}}
export interface AssetFeatureRequirement {id:string;required:AssetDependency[];optional:AssetDependency[];fallback:'bundled'|'none'}
export interface AssetRequirements {schema:'tavi.assets.requirements/v1';applicationId:string;features:AssetFeatureRequirement[]}
export declare function validateAssetRequirements(requirements:AssetRequirements):true;
export declare function resolveAssetRequirements(requirements:AssetRequirements,installedManifests:PackManifest[],context:TrustedAssetHostContext):{schema:'tavi.assets.dependency-status/v1';applicationId:string;features:Array<{id:string;ready:boolean;fallback:'bundled'|'none';required:unknown[];optional:unknown[]}>};

/** Syntactic and manifest-subset checks, not permission issuance or proof of publisher trust. */
export declare function validateTavixAssetDependencies(manifest:TrustedAssetHostContext['verifiedManifest']):Array<unknown>;
export declare function validateTavixHostContext(context:TrustedAssetHostContext):{applicationId:string;byPack:Map<string,{capabilities:Set<string>;canCustomize:boolean;compatibility:{min:string;maxExclusive:string}}>};
export declare function requirementsFromTavix(manifest:TrustedAssetHostContext['verifiedManifest']):AssetRequirements;
export declare function withinVersion(version:string,range:{min:string;maxExclusive:string}):boolean;
