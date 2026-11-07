/** Proposed host-bound Tavi Assets API, not yet implemented by production Tavi. */
export interface HostTransport {
  info(): Promise<{api?: string; features?: string[]}>;
  request(method: string, params: Record<string, unknown>): Promise<Record<string, unknown>>;
}
export interface AssetObject {
  id: string;
  kind: string;
  name: string;
  description: string;
  rarity: string;
  tags: string[];
  attributes: Record<string, unknown>;
  resources: string[];
  rulesRef: string | null;
  /** Declarative and inert until an approved game runtime opts into this exact profile. */
  modifiers: Array<{profile: 'tavi.cards.modifiers.v1'; trigger: string; conditions?: Array<{field: string; operator: string; value: string | number}>; effects: Array<{op: string; value: number}>}>;
}
export interface AssetCollection {
  schema: 'tavi.assets.collection/v1';
  packId: string;
  version: string;
  id: string;
  kind: string;
  name: string;
  description: string;
  tags: string[];
  entries: Array<{objectId: string; quantity: number}>;
}
export interface AssetList {
  schema: 'tavi.assets.object-list/v1';
  packId: string;
  version: string;
  total: number;
  nextOffset: number | null;
  items: AssetObject[];
}
export interface AssetResource {
  schema: 'tavi.assets.resource/v1';
  packId: string;
  version: string;
  capability: string;
  contentType: string;
  encoding: 'base64';
  data: string;
  selected: string | null;
}
export declare class AssetsUnavailableError extends Error {}
export declare function createTaviAssetsClient(transport: HostTransport): Readonly<{
  connect(): Promise<{feature: 'tavi.assets/v1'; api: string | null}>;
  describe(packId: string): Promise<Record<string, unknown>>;
  listObjects(packId: string, filters?: {kind?: string; rarity?: string; tags?: string[]; offset?: number; limit?: number}): Promise<AssetList>;
  getObject(packId: string, objectId: string): Promise<{schema: 'tavi.assets.object/v1'; packId: string; version: string; object: AssetObject}>;
  listCollections(packId: string, filters?: {kind?: string}): Promise<{schema: 'tavi.assets.collection-list/v1'; items: Array<{id: string; kind: string; name: string; tags: string[]; objectCount: number}>}>;
  getCollection(packId: string, collectionId: string): Promise<AssetCollection>;
  preferences(packId: string): Promise<Record<string, unknown>>;
  select(packId: string, capability: string, variant: string): Promise<Record<string, unknown>>;
  resolve(packId: string, capability: string): Promise<AssetResource>;
}>;
