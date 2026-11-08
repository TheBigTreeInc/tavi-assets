import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {AssetService,TrustedAssetHostBridge} from '../portable_service/service.mjs';
import {MemoryAssetStorage} from '../portable_service/storage.mjs';
import {NodeFileAssetStorage} from '../portable_service/node-file-storage.mjs';
import {validatePack,AssetContractError} from '../portable_service/validation.mjs';
import {createTaviAssetsClient} from '../sdk/client.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
async function fixture(dir='cards-v1') {
  const folder=path.join(root,'examples',dir);
  const manifest=JSON.parse(await fs.readFile(path.join(folder,'manifest.json'),'utf8'));
  const files={};for(const name of Object.keys(manifest.files))files[name]=new Uint8Array(await fs.readFile(path.join(folder,name)));
  return {manifest,files,origin:'approved-fixture'};
}
const v1=await fixture(),v2=await fixture('cards-v2'),story=await fixture('storybook-decks');
let checks=0;
async function test(name,fn){await fn();checks++;console.log('PASS',name);}
await test('validates three original fixture packs including 3 decks and 16 jokers',async()=>{
  await validatePack(v1.manifest,v1.files);await validatePack(v2.manifest,v2.files);await validatePack(story.manifest,story.files);
  assert.equal(Object.keys(story.manifest.collections).filter(k=>story.manifest.collections[k].kind==='deck').length,3);
  assert.equal(Object.keys(story.manifest.objects).filter(k=>story.manifest.objects[k].kind==='joker-card').length,16);
});
await test('fail closed on corrupt, unsafe path and active SVG',async()=>{
  const x=structuredClone(v1);x.files['back-blue.svg'][4]^=1;await assert.rejects(validatePack(x.manifest,x.files),AssetContractError);
  const y=structuredClone(v1);y.manifest.files['../escape.svg']=y.manifest.files['back-blue.svg'];await assert.rejects(validatePack(y.manifest,y.files),AssetContractError);
  const z=structuredClone(v1);z.files['back-blue.svg']=new TextEncoder().encode('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>');await assert.rejects(validatePack(z.manifest,z.files),AssetContractError);
  const dup=structuredClone(v1);dup.manifest.files['BACK-BLUE.svg']=dup.manifest.files['back-blue.svg'];await assert.rejects(validatePack(dup.manifest,dup.files),AssetContractError);
});
await test('host approval callback required; untrusted install rejected',async()=>{
  assert.throws(()=>new AssetService({storage:new MemoryAssetStorage()}),TypeError);
  const svc=new AssetService({storage:new MemoryAssetStorage(),authorizeInstall:async()=>false});
  await assert.rejects(svc.install(v1),AssetContractError);assert.deepEqual(await svc.listInstalled(),{});
});
await test('install and update retain preferences; corrupt update does not activate',async()=>{
  const storage=new MemoryAssetStorage();const svc=new AssetService({storage,authorizeInstall:async ({origin})=>origin==='approved-fixture'});
  await svc.install(v1);await svc.setGlobalPreference(v1.manifest.id,'card.back','green');
  const before=await svc.resolve(v1.manifest.id,'card.back');assert.equal(before.selected,'green');
  const broken=structuredClone(v2);broken.files['front.svg'][3]^=1;
  await assert.rejects(svc.install(broken),AssetContractError);assert.equal((await svc.describe(v1.manifest.id)).version,v1.manifest.version);
  await svc.install(v2);const after=await svc.resolve(v2.manifest.id,'card.back');assert.equal(after.selected,'green');
  await assert.rejects(svc.install(v1),AssetContractError);
  const restarted=new AssetService({storage,authorizeInstall:async()=>false});assert.equal((await restarted.resolve(v2.manifest.id,'card.back')).selected,'green');
});
await test('application override > global preference > pack default and scope isolation',async()=>{
  const svc=new AssetService({storage:new MemoryAssetStorage(),authorizeInstall:async()=>true});await svc.install(v1);
  const pack=v1.manifest.id;
  await svc.setGlobalPreference(pack,'card.back','blue');
  await svc.setApplicationPreference('game.one',pack,'card.back','green');
  assert.equal((await svc.resolve(pack,'card.back','game.one')).selected,'green');
  assert.equal((await svc.resolve(pack,'card.back','game.two')).selected,'blue');
  assert.equal((await svc.resolve(pack,'card.front.ace-spades','game.one')).selected,null);
});
await test('host denies spoofed grants, paths, ungranted capabilities and unapproved customization',async()=>{
  const svc=new AssetService({storage:new MemoryAssetStorage(),authorizeInstall:async()=>true});await svc.install(v1);
  const pack=v1.manifest.id;const session={token:'not-from-wire'};
  const bridge=new TrustedAssetHostBridge(svc,async trusted=>trusted===session?{applicationId:'game.one',packs:[pack],capabilities:['card.back'],canCustomize:true}:null);
  await assert.rejects(bridge.dispatch({},'assets.describe',{packId:pack}),AssetContractError);
  await assert.rejects(bridge.dispatch(session,'assets.resolve',{packId:pack,capability:'card.front'}),AssetContractError);
  await assert.rejects(bridge.dispatch(session,'assets.resolve',{packId:pack,capability:'card.back',path:'../registry.json'}),AssetContractError);
  await assert.rejects(bridge.dispatch(session,'assets.preferences.set',{packId:pack,capability:'card.back',variant:'green',callerId:'game.one'}),AssetContractError);
  assert.deepEqual((await bridge.dispatch(session,'assets.describe',{packId:pack})).capabilities,['card.back']);
  await bridge.dispatch(session,'assets.preferences.set',{packId:pack,capability:'card.back',variant:'green'});
  assert.equal((await bridge.dispatch(session,'assets.resolve',{packId:pack,capability:'card.back'})).selected,'green');
  assert.equal((await svc.resolve(pack,'card.back')).selected,null);
  const denied=new TrustedAssetHostBridge(svc,async()=>({applicationId:'game.one',packs:[pack],capabilities:['card.back'],canCustomize:false}));
  await assert.rejects(denied.dispatch(session,'assets.preferences.set',{packId:pack,capability:'card.back',variant:'blue'}),AssetContractError);
});
await test('reference consumer SDK calls portable host dispatcher through injected transport',async()=>{
  const svc=new AssetService({storage:new MemoryAssetStorage(),authorizeInstall:async()=>true});await svc.install(story);
  const trustedSession={};const bridge=new TrustedAssetHostBridge(svc,async s=>s===trustedSession?{applicationId:'game.one',packs:[story.manifest.id],capabilities:Object.keys(story.manifest.resources),canCustomize:false}:null);
  const consumer=createTaviAssetsClient({info:async()=>({features:['tavi.assets/v1'],api:'1.0.0'}),request:(method,params)=>bridge.dispatch(trustedSession,method,params)});
  await consumer.connect();const list=await consumer.listCollections(story.manifest.id,{kind:'deck'});assert.equal(list.items.length,3);
  const jokers=await consumer.listObjects(story.manifest.id,{kind:'joker-card'});assert.equal(jokers.total,16);
  await assert.rejects(consumer.select(story.manifest.id,'card.back','ochre'),AssetContractError);
});
await test('Node-only reference adapter persists installed assets and prefs across recreated instances',async()=>{
  const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'tavi-assets-portable-'));
  try {
    const a=new AssetService({storage:new NodeFileAssetStorage(tmp),authorizeInstall:async()=>true});
    await a.install(v1);await a.setGlobalPreference(v1.manifest.id,'card.back','green');
    const b=new AssetService({storage:new NodeFileAssetStorage(tmp),authorizeInstall:async()=>false});
    assert.equal((await b.resolve(v1.manifest.id,'card.back')).selected,'green');
    const evil=structuredClone(v2);evil.files['back-green.svg'][0]^=1;
    await assert.rejects(b.install(evil),AssetContractError);
    assert.equal((await b.describe(v1.manifest.id)).version,v1.manifest.version);
  } finally {await fs.rm(tmp,{recursive:true,force:true});}
});
await test('tampered persisted content is rejected on read; inherited object key is forbidden',async()=>{
  const base=new MemoryAssetStorage();const svc=new AssetService({storage:base,authorizeInstall:async()=>true});await svc.install(v1);
  const corrupt=base.exportForTesting();const id=v1.manifest.id;corrupt.installed[id].files['back-blue.svg']='PGltZyBvbmxvYWQ9ImV2aWwoKSI+PC9pbWc+';
  const reopened=new AssetService({storage:new MemoryAssetStorage(corrupt),authorizeInstall:async()=>true});
  await assert.rejects(reopened.resolve(id,'card.back'),AssetContractError);
  await assert.rejects(reopened.getManifest(id),AssetContractError);
  const forged=structuredClone(v1);forged.manifest.id='constructor';await assert.rejects(validatePack(forged.manifest,forged.files),AssetContractError);
});
await test('reference disk adapter retains existing state after rejected transaction and fails closed on abandoned lock',async()=>{
  const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'tavi-assets-lock-'));
  try{
    const storage=new NodeFileAssetStorage(tmp);const svc=new AssetService({storage,authorizeInstall:async()=>true});await svc.install(v1);
    const previous=await storage.read();
    await assert.rejects(storage.transact(async s=>{s.installed={};throw new Error('abort');}), /abort/);
    assert.deepEqual(await storage.read(),previous);
    await fs.mkdir(path.join(tmp,'.writer.lock'));
    await assert.rejects(storage.transact(s=>{s.installed={};}),AssetContractError);
    assert.deepEqual(await storage.read(),previous);
  }finally{await fs.rm(tmp,{recursive:true,force:true});}
});
console.log(`Portable Tavi Assets runtime smoke: ${checks}/${checks} scenarios passed`);
