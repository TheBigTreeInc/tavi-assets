/** DEVELOPMENT-ONLY Node reference adapter. Tavi must use its own secure device adapter.
 * Single-document storage is bounded to 8 MiB and NOT suited for production asset packs.
 * Exclusive lock directory fails closed after a crash; operator must review before repair.
 * No background stale-lock removal, no publisher/authentication implementation.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {EMPTY_STATE} from './storage.mjs';
import {cloneJSON,AssetContractError} from './validation.mjs';
export class NodeFileAssetStorage {
  #root; #tail=Promise.resolve();
  constructor(root) { if(typeof root!=='string'||!path.isAbsolute(root))throw new TypeError('absolute trusted storage path required');this.#root=root; }
  async #init() {
    await fs.mkdir(this.#root,{recursive:true,mode:0o700});
    const info=await fs.lstat(this.#root);if(info.isSymbolicLink()||!info.isDirectory())throw new AssetContractError('unsafe storage root');
  }
  async #read() {
    const file=path.join(this.#root,'snapshot.json');
    try {const st=await fs.lstat(file);if(st.isSymbolicLink()||!st.isFile()||st.size>8*1024*1024)throw new AssetContractError('unsafe snapshot');return JSON.parse(await fs.readFile(file,'utf8'));}
    catch(err){if(err?.code==='ENOENT')return EMPTY_STATE();throw err;}
  }
  async read() { await this.#tail;await this.#init();return cloneJSON(await this.#read()); }
  async transact(fn) {
    let release;const prev=this.#tail;this.#tail=new Promise(resolve=>{release=resolve;});await prev;
    const lock=path.join(this.#root,'.writer.lock');let acquired=false;
    try {
      await this.#init();
      try {await fs.mkdir(lock);acquired=true;} catch(err){if(err?.code==='EEXIST')throw new AssetContractError('storage busy or interrupted; operator review required');throw err;}
      const state=await this.#read(),next=cloneJSON(state),result=await fn(next);
      const content=JSON.stringify(next);if(Buffer.byteLength(content,'utf8')>8*1024*1024)throw new AssetContractError('reference storage quota exceeded');
      const temp=path.join(this.#root,`.snapshot-${process.pid}-${crypto.randomUUID()}.tmp`);
      try {
        const handle=await fs.open(temp,'wx',0o600);
        try {await handle.writeFile(content,'utf8');await handle.sync();}finally{await handle.close();}
        await fs.rename(temp,path.join(this.#root,'snapshot.json'));
      } finally {await fs.rm(temp,{force:true});}
      return result;
    } finally {try {if(acquired)await fs.rmdir(lock);} finally {release();}}
  }
}
