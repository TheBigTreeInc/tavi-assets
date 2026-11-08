/** Exact regression for cross-pack capability leakage under flat grants. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {AssetService,MemoryAssetStorage,TrustedAssetHostBridge,validateTavixHostContext,
  validateTavixAssetDependencies,requirementsFromTavix} from '../portable_service/index.mjs';
import {createTaviAssetsClient} from '../sdk/client.mjs';
import {readFixture} from '../developer/fixture-host.mjs';
import {fixtureTavixContext} from '../developer/tavix-fixtures.mjs';
const deck=await readFixture(join('examples','cards-v1'));
const story=await readFixture(join('examples','storybook-decks'));
const A=deck.manifest.id,B=story.manifest.id;
const app='org.tavi.example.game';
const context=fixtureTavixContext({applicationId:app,packCapabilities:{[A]:['card.back'],[B]:['card.face.spades.ace']},canCustomize:{[A]:true,[B]:false}});
const service=new AssetService({storage:new MemoryAssetStorage(),authorizeInstall:async()=>true});
await service.install(deck);await service.install(story);
const session={};let current=context;
const bridge=new TrustedAssetHostBridge(service,async s=>s===session?current:null);
const client=createTaviAssetsClient({info:async()=>({features:['tavi.assets/v1','tavi.assets.dependencies/v1']}),
  request:(method,params)=>bridge.dispatch(session,method,params)});
await client.connect();
let count=0;
async function check(title,fn){await fn();count++;console.log('PASS',title);}
await check('TaviX v1 host projection and manifest request subset validated',()=>{
  assert.equal(validateTavixHostContext(context).byPack.size,2);
  assert.equal(validateTavixAssetDependencies(context.verifiedManifest).length,2);
  assert.equal(requirementsFromTavix(context.verifiedManifest).features.length,2);
});
await check('listPacks exposes per-pack capabilities without cross-product grants',async()=>{
  const out=await client.listPacks();assert.equal(out.total,2);
  assert.deepEqual(Object.fromEntries(out.items.map(x=>[x.packId,x.capabilities])),{[A]:['card.back'],[B]:['card.face.spades.ace']});
  assert.equal((await client.describe(B)).objectCount,1);
});
await check('B card.back prohibited although A grants card.back and B is installed',async()=>{
  await assert.rejects(client.resolve(B,'card.back'));
  await assert.rejects(client.resolveComposition([{slot:'back',packId:B,capability:'card.back'}]));
  await assert.rejects(client.resolve(A,'card.face.spades.ace'));
});
await check('collection and object metadata filtered before totals and pagination',async()=>{
  const list=await client.listObjects(B,{kind:'playing-card'});
  assert.equal(list.total,1);assert.equal(list.items.length,1);assert.deepEqual(list.items[0].resources,['card.face.spades.ace']);
  assert.equal((await client.discoverObjects({kind:'playing-card'})).total,1);
  await assert.rejects(client.getObject(B,'playing.spades.two'));
  const decks=await client.listCollections(B,{kind:'deck'});assert.equal(decks.items.length,1);
  assert.equal(decks.items[0].objectCount,1);
  const detail=await client.getCollection(B,'deck.playing.classic');assert.equal(detail.entries.length,1);
  const prefs=await client.preferences(B);assert.deepEqual(prefs.items.map(x=>x.capability),['card.face.spades.ace']);
});
await check('only approved pack can customize, never cross-pack privilege',async()=>{
  await client.select(A,'card.back','green');
  assert.equal((await client.resolve(A,'card.back')).selected,'green');
  await assert.rejects(client.select(B,'card.back','indigo'));
  await assert.rejects(client.select(B,'card.face.spades.ace','indigo'));
});
await check('approved composition works across packs',async()=>{
  const c=await client.resolveComposition([{slot:'back',packId:A,capability:'card.back'},
    {slot:'front',packId:B,capability:'card.face.spades.ace'}]);
  assert.deepEqual(c.items.map(x=>x.slot),['back','front']);
});
await check('TaviX-granted dependencies produce status without caller supplied requirements',async()=>{
  const result=await client.dependencyStatus();
  assert.equal(result.applicationId,app);assert.equal(result.features.length,2);
  assert.equal(result.features.every(x=>x.ready),true);
  await assert.rejects(bridge.dispatch(session,'assets.dependencies.status',{grants:context.projection}));
});
await check('revocation rechecked each operation, no cached old grant',async()=>{
  current=structuredClone(context);current.projection.grants=[];
  assert.equal((await client.listPacks()).total,0);
  await assert.rejects(client.resolve(A,'card.back'));
  current=context;
});
await check('invalid identities, digests and client-supplied grants denied',async()=>{
  const bad=fn=>{const c=structuredClone(context);fn(c);return c;};
  for(const variant of [
    bad(c=>{c.projection.manifestSha256='0'.repeat(64)}),
    bad(c=>{c.projection.extensionId='org.tavi.fake.game'}),
    bad(c=>{c.projection.extensionVersion='9.0.0'}),
    bad(c=>{c.projection.scope='untrusted'}),
    bad(c=>{c.projection.grants.push(structuredClone(c.projection.grants[0]))}),
    bad(c=>{c.projection.grants[1].capabilities.push('card.back')}),
    bad(c=>{c.projection.grants[1].canCustomize=true}),
    bad(c=>{c.projection.grants[0].packId='org.private.undeclared'}),
    bad(c=>{c.projection.grants[0].capabilities=['card.*']}),
    bad(c=>{c.projection.grants[0].capabilities.push('card.face.spades.ace')})
  ])assert.throws(()=>validateTavixHostContext(variant));
  await assert.rejects(bridge.dispatch(session,'assets.resolve',{packId:A,capability:'card.back',grant:context.projection}));
  await assert.rejects(bridge.dispatch({},'assets.resolve',{packId:A,capability:'card.back'}));
});
await check('stale installed pack fails closed under requested version bounds',async()=>{
  const temp=fixtureTavixContext({applicationId:app,packCapabilities:{[A]:['card.back']},compatibility:{min:'9.0.0',maxExclusive:'10.0.0'}});
  current=temp;
  assert.equal((await client.listPacks()).total,0);
  await assert.rejects(client.describe(A));
  current=context;
});
await check('flat legacy grants cannot bypass TaviX scope checks',async()=>{
  current={applicationId:app,packs:[A,B],capabilities:['card.back','card.face.spades.ace']};
  await assert.rejects(client.resolve(B,'card.back'));
  current=context;
});
await check('TaviX 0.1.11 sample extension dependency declaration parses',async()=>{
  const manifest=JSON.parse(await readFile('examples/developer/tavix-011-asset-consumer.json','utf8'));
  assert.equal(validateTavixAssetDependencies(manifest).length,1);
  assert.equal(manifest.assetDependencies[0].packId,A);
});
console.log(`Scoped TaviX asset grants: ${count}/${count} scenarios passed`);
