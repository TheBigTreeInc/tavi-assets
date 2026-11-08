/** Tavi Assets portable reference runtime 0.1.6. Host-side only; NEVER bundle into a third-party extension. */
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
export interface TrustedGrant {applicationId:string;packs:string[];capabilities:string[];canCustomize?:boolean}
export declare class TrustedAssetHostBridge {
  constructor(service:AssetService, getTrustedGrant:(trustedSession:unknown)=>Promise<TrustedGrant|null>|TrustedGrant|null);
  dispatch(trustedSession:unknown,method:string,params:Record<string,unknown>):Promise<Record<string,unknown>>;
}
export declare class MemoryAssetStorage implements StorageAdapter { constructor(initial?:Record<string,unknown>);read():Promise<Record<string,unknown>>;transact<T>(cb:(state:any)=>T|Promise<T>):Promise<T>;exportForTesting():Record<string,unknown> }
export declare class AssetContractError extends Error {}
export declare function validateManifest(manifest:PackManifest):true;
export declare function validatePack(manifest:PackManifest,files:Record<string,Uint8Array>):Promise<true>;
export declare function manifestRevision(manifest:PackManifest):Promise<string>;
