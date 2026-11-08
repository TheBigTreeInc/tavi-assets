/** Memory reference adapter. A real host MUST supply a durable, atomic storage adapter. */
import {cloneJSON} from './validation.mjs';
export const EMPTY_STATE = () => ({schema:'tavi.assets.runtime-store/v1', installed:{}, preferences:{global:{}, applications:{}}});
export class MemoryAssetStorage {
  #state;
  #tail=Promise.resolve();
  constructor(initial=EMPTY_STATE()) { this.#state=cloneJSON(initial); }
  async read() { await this.#tail; return cloneJSON(this.#state); }
  async transact(callback) {
    let release;
    const previous=this.#tail;
    this.#tail=new Promise(resolve=>{release=resolve;});
    await previous;
    try { const next=cloneJSON(this.#state); const result=await callback(next); this.#state=cloneJSON(next); return result; }
    finally { release(); }
  }
  exportForTesting() { return cloneJSON(this.#state); }
}
