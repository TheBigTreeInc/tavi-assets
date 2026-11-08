/** Strict local fixture host for game developers. Never use as a production Tavi host. */
import {readFile} from 'node:fs/promises';
import {join, resolve, sep} from 'node:path';
import {AssetService, MemoryAssetStorage, TrustedAssetHostBridge} from '../portable_service/index.mjs';
import {createTaviAssetsClient} from '../sdk/client.mjs';
import {fixtureTavixContext} from './tavix-fixtures.mjs';

export async function readFixture(directory) {
  const base=resolve(directory);
  const manifest=JSON.parse(await readFile(join(base,'manifest.json'),'utf8'));
  const files={};
  for (const path of Object.keys(manifest.files)) {
    // Fixture reader must not become a generic arbitrary file-read API.
    const absolute=resolve(base,path);
    if(!absolute.startsWith(base+sep)||path.includes('\\'))throw new Error('unsafe fixture path');
    files[path]=new Uint8Array(await readFile(absolute));
  }
  return {manifest,files,origin:'explicit-local-fixture'};
}

/** Explicit fixtures and grants only; no Wallet/LoopRD fake-success results. */
export async function createFixtureGameHost({fixtures, applicationId, capabilities, packCapabilities=null, requirements=null}) {
  if(!Array.isArray(fixtures)||!fixtures.length||typeof applicationId!=='string'||(!Array.isArray(capabilities)&&!packCapabilities))throw new TypeError('explicit fixtures and grants required');
  const ids=fixtures.map(x=>x.manifest.id);
  if(new Set(ids).size!==ids.length)throw new Error('duplicate fixture pack');
  const allowedVersions=new Set(fixtures.map(x=>`${x.manifest.id}@${x.manifest.version}`));
  const service=new AssetService({storage:new MemoryAssetStorage(),authorizeInstall:async({packId,version,origin})=>origin==='explicit-local-fixture'&&allowedVersions.has(`${packId}@${version}`)});
  for(const fixture of fixtures)await service.install(fixture);
  const session=Object.freeze({});
  const scoped=packCapabilities??Object.fromEntries(fixtures.map(x=>[x.manifest.id,
    capabilities.filter(cap=>Object.hasOwn(x.manifest.resources,cap))]).filter(([,caps])=>caps.length));
  const context=fixtureTavixContext({applicationId,packCapabilities:scoped,canCustomize:true,requirements});
  const bridge=new TrustedAssetHostBridge(service,async current=>current===session?context:null);
  const client=createTaviAssetsClient({
    info:async()=>({api:'1.0.0',features:['tavi.assets/v1',...(requirements?['tavi.assets.dependencies/v1']:[])]}),
    request:(method,params)=>bridge.dispatch(session,method,params)
  });
  await client.connect();
  // Only client exposed to game code. Trusted service deliberately not returned.
  return client;
}
