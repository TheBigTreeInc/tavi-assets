import assert from 'node:assert/strict';
import {join} from 'node:path';
import {createFixtureGameHost,readFixture} from '../developer/fixture-host.mjs';
import {fixtureTavixContext} from '../developer/tavix-fixtures.mjs';
import {AssetService,MemoryAssetStorage,TrustedAssetHostBridge} from '../portable_service/index.mjs';
import {createTaviAssetsClient} from '../sdk/client.mjs';

const one=await readFixture(join('examples','cards-v1'));
const two=await readFixture(join('examples','storybook-decks'));
const all=[one,two];
let checks=0;
async function test(label,fn){await fn();checks++;console.log('PASS '+label);}
const caps=['card.back','card.front.ace-spades',...Object.keys(two.manifest.resources).filter(c=>c.startsWith('card.face.spades.')).slice(0,4),...Object.keys(two.manifest.resources).filter(c=>c.startsWith('card.face.joker.'))];
const client=await createFixtureGameHost({fixtures:all,applicationId:'org.tavi.example.game',capabilities:caps});
await test('discover across installed and authorized packs without hardcoded pack ID',async()=>{
  const packs=await client.listPacks();assert.equal(packs.total,2);
  const a=await client.discoverObjects({kind:'playing-card',limit:2});
  assert.equal(a.total,4);assert.equal(a.items.length,2);assert.equal(a.nextOffset,2);
  assert.deepEqual([...new Set(a.items.map(x=>x.packId))],[two.manifest.id]);
  assert.ok(a.items.every(x=>x.object.resources.every(cap=>caps.includes(cap))));
  const next=await client.discoverObjects({kind:'playing-card',offset:2,limit:2});
  assert.notEqual(a.items[0].object.id,next.items[0].object.id);
});
await test('cross-pack customization slots resolve without combining bytes or metadata',async()=>{
  const out=await client.resolveComposition([
    {slot:'front',packId:two.manifest.id,capability:'card.face.spades.ace'},
    {slot:'back',packId:one.manifest.id,capability:'card.back'}]);
  assert.equal(out.schema,'tavi.assets.composition/v1');assert.deepEqual(out.items.map(x=>x.slot),['front','back']);
  assert.ok(out.items.every(x=>x.contentType==='image/svg+xml'&&x.encoding==='base64'));
});
await test('ungranted packs/capabilities and unknown methods fail closed',async()=>{
  await assert.rejects(client.resolveComposition([{slot:'private',packId:'org.private.assets',capability:'card.back'}]));
  await assert.rejects(client.resolveComposition([{slot:'other',packId:one.manifest.id,capability:'card.face.spades.ace'}]));
  await assert.rejects(client.resolveComposition([{slot:'a',packId:one.manifest.id,capability:'card.back'},{slot:'a',packId:one.manifest.id,capability:'card.back'}]));
  await assert.rejects(client.resolveComposition([{slot:'a',packId:one.manifest.id,capability:'card.back',path:'../../private'}]));
  assert.equal(client.purchase,undefined);
});
await test('no default rarity in cross-pack discovery',async()=>{
  const m=await client.discoverObjects({kind:'joker-card',limit:100});assert.equal(m.total,16);
  const info=await client.listPacks({type:'playing-cards'});assert.equal(info.total,1);
});
await test('host request rejects caller-supplied identity and privilege',async()=>{
  const service=new AssetService({storage:new MemoryAssetStorage(),authorizeInstall:async()=>true});
  await service.install(one);const trusted={};
  const bridge=new TrustedAssetHostBridge(service,async sess=>sess===trusted?fixtureTavixContext({applicationId:'org.example.game.a',packCapabilities:{[one.manifest.id]:['card.back']},canCustomize:false}):null);
  const transport={info:async()=>({features:['tavi.assets/v1']}),request:(method,params)=>bridge.dispatch(trusted,method,params)};
  const c=createTaviAssetsClient(transport);await c.connect();
  await assert.rejects(c.listPacks({callerId:'trusted'}));
  await assert.rejects(c.discoverObjects({grants:['org.private.assets']}));
  await assert.rejects(c.resolveComposition([{slot:'a',packId:one.manifest.id,capability:'card.front.ace-spades'}]));
  const rows=await c.listPacks();assert.deepEqual(rows.items[0].capabilities,['card.back']);
});
await test('unauthorized pack cannot be discovered, even if installed',async()=>{
  const service=new AssetService({storage:new MemoryAssetStorage(),authorizeInstall:async()=>true});
  for(const pack of all)await service.install(pack);
  const sess={};const bridge=new TrustedAssetHostBridge(service,async cur=>cur===sess?fixtureTavixContext({applicationId:'org.example.game.a',packCapabilities:{[one.manifest.id]:['card.back']},canCustomize:false}):null);
  const c=createTaviAssetsClient({info:async()=>({features:['tavi.assets/v1']}),request:(method,params)=>bridge.dispatch(sess,method,params)});await c.connect();
  assert.equal((await c.listPacks()).total,1);
  assert.equal((await c.discoverObjects({kind:'joker-card'})).total,0);
});
console.log(`Developer asset contract: ${checks}/${checks} scenarios passed`);
