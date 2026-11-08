import type {StorageAdapter} from './index.d.ts';
/** Development-only Node adapter (8 MiB cap; incomplete-crash lock requires manual review). */
export declare class NodeFileAssetStorage implements StorageAdapter {
  constructor(absoluteTrustedRoot:string);
  read():Promise<Record<string,unknown>>;
  transact<T>(callback:(state:any)=>T|Promise<T>):Promise<T>;
}
