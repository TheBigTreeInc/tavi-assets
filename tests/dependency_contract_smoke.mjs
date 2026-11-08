import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {createFixtureGameHost, readFixture} from '../developer/fixture-host.mjs';
import {fixtureTavixContext} from '../developer/tavix-fixtures.mjs';
import {AssetService, MemoryAssetStorage, TrustedAssetHostBridge, validateAssetRequirements,resolveAssetRequirements} from '../portable_service/index.mjs';
import {createTaviAssetsClient,AssetsUnavailableError} from '../sdk/client.mjs';

const deck=await readFixture(join('examples','cards-v1'));
const story=await readFixture(join('examples','storybook-decks'));
const req=JSON.parse(await readFile('examples/developer/klondike-asset-requirements.json','utf8'));
const companion=JSON.parse(await readFile('examples/developer/companion-asset-requirements.json','utf8'));
let tests=0;
async function check(name,fn){await fn();tests++;console.log(`PASS ${name}`);}
const grant=fixtureTavixContext({applicationId:req.applicationId,packCapabilities:{
  [deck.manifest.id]:['card.back'],[story.manifest.id]:['card.back','card.face.spades.ace']},requirements:req});
const updated=(change)=>{const c=structuredClone(grant);change(c);return c;};
await check('validated game feature declarations, no rarity or price required',()=>{
  assert.equal(validateAssetRequirements(req),true);
  assert.equal(validateAssetRequirements(companion),true);
  assert.equal(req.features[0].fallback,'bundled');
});
await check('required cosmetic capability ready, optional missing leaves feature ready',()=>{
  const out=resolveAssetRequirements(req,[deck.manifest,story.manifest],grant);
  assert.equal(out.schema,'tavi.assets.dependency-status/v1');
  assert.equal(out.features[0].ready,true);
  assert.equal(out.features[0].required[0].selected.packId,deck.manifest.id);
  assert.equal(out.features[0].optional[0].available,true);
  assert.equal(out.features[1].ready,true);
  assert.equal(out.features[1].optional[0].available,false);
});
await check('no granted pack, stale version and missing capability deny readiness',()=>{
  const unavailable=resolveAssetRequirements(req,[deck.manifest],updated(g=>{g.projection.grants=[];}));
  assert.equal(unavailable.features[0].ready,false);
  assert.equal(unavailable.features[0].fallback,'bundled');
  const stale=structuredClone(req);
  stale.features[0].required[0].version={min:'9.0.0',maxExclusive:'10.0.0'};
  assert.equal(resolveAssetRequirements(stale,[deck.manifest],grant).features[0].ready,false);
  assert.equal(resolveAssetRequirements(req,[deck.manifest],updated(g=>{g.projection.grants=[{packId:story.manifest.id,capabilities:['card.face.spades.ace'],canCustomize:false}];})).features[0].ready,false);
});
await check('deterministic choice across multiple granted packs and restricted visibility',()=>{
  const any={schema:'tavi.assets.requirements/v1',applicationId:req.applicationId,features:[
    {id:'backs',required:[{capability:'card.back'}],optional:[],fallback:'none'}]};
  const out=resolveAssetRequirements(any,[story.manifest,deck.manifest],grant);
  assert.equal(out.features[0].required[0].selected.packId,[story.manifest.id,deck.manifest.id].sort()[0]);
  assert.equal(resolveAssetRequirements(any,[story.manifest,deck.manifest],updated(g=>{g.projection.grants=g.projection.grants.filter(x=>x.packId===story.manifest.id);})).features[0].required[0].selected.packId,story.manifest.id);
});
await check('declarations reject duplicates, unknown keys, spoofing and broken range',async()=>{
  const bads=[];
  const copied=()=>structuredClone(req);
  let a=copied();a.features[0].wallet={gold:123};bads.push(a);
  a=copied();a.features.push(structuredClone(a.features[0]));bads.push(a);
  a=copied();a.features[0].required.push(structuredClone(a.features[0].required[0]));bads.push(a);
  a=copied();a.features[0].required[0].path='../../private';bads.push(a);
  a=copied();a.features[0].required[0].version={min:'1.0.0',maxExclusive:'1.0.0'};bads.push(a);
  a=copied();a.features[0].required[0].version={min:'1.0.0',maxExclusive:'0.1.0'};bads.push(a);
  a=copied();a.features[0].optional[0].packId='../private';bads.push(a);
  for(const bad of bads)assert.throws(()=>validateAssetRequirements(bad));
  assert.throws(()=>resolveAssetRequirements(req,[deck.manifest],updated(g=>{g.projection.extensionId='org.example.other.game';})));
});
await check('bridge uses host-derived verified declaration only, no request-supplied requirements',async()=>{
  const svc=new AssetService({storage:new MemoryAssetStorage(),authorizeInstall:async()=>true});
  await svc.install(deck);await svc.install(story);
  const session={};
  const bridge=new TrustedAssetHostBridge(svc,async caller=>caller===session?grant:null);
  const client=createTaviAssetsClient({info:async()=>({features:['tavi.assets/v1','tavi.assets.dependencies/v1']}),request:(m,p)=>bridge.dispatch(session,m,p)});
  await client.connect();
  const status=await client.dependencyStatus();assert.equal(status.features[0].ready,true);
  await assert.rejects(bridge.dispatch(session,'assets.dependencies.status',{requirements:req}));
  await assert.rejects(bridge.dispatch({},'assets.dependencies.status',{}));
  assert.equal(client.purchase,undefined);
});
await check('dependency status feature must be separately negotiated',async()=>{
  let sent=0;
  const client=createTaviAssetsClient({info:async()=>({features:['tavi.assets/v1']}),request:async()=>{sent++;return {};}});
  await client.connect();
  assert.throws(()=>client.dependencyStatus(),AssetsUnavailableError);
  assert.equal(sent,0);
});
await check('developer fixture host supports offline dependency status, optional content falls back',async()=>{
  const client=await createFixtureGameHost({fixtures:[deck,story],applicationId:req.applicationId,capabilities:['card.back','card.face.spades.ace'],requirements:req});
  const status=await client.dependencyStatus();
  assert.equal(status.features[0].ready,true);
  assert.equal(status.features[1].optional[0].available,false);
  const basic=await createFixtureGameHost({fixtures:[deck],applicationId:'org.tavi.other',capabilities:['card.back']});
  assert.throws(()=>basic.dependencyStatus(),AssetsUnavailableError);
});
await check('storefront inventory or synthetic wallet data cannot create entitlement or install',()=>{
  const noPaid=req.features[0].required[0];
  assert.equal(noPaid.price,undefined);assert.equal(noPaid.entitlement,undefined);
  assert.equal(noPaid.install,undefined);
});
console.log(`Dependency contract scenarios: ${tests}/${tests} passed`);
