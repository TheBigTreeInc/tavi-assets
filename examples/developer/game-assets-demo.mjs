/** Run from project root: node examples/developer/game-assets-demo.mjs */
import {fileURLToPath} from 'node:url';
import {join,dirname} from 'node:path';
import {createFixtureGameHost,readFixture} from '../../developer/fixture-host.mjs';

const root=join(dirname(fileURLToPath(import.meta.url)),'../..');
const original=await readFixture(join(root,'examples/cards-v1'));
const story=await readFixture(join(root,'examples/storybook-decks'));
const assets=await createFixtureGameHost({fixtures:[original,story],applicationId:'org.tavi.example.game',
  capabilities:['card.back','card.front.ace-spades','card.face.spades.ace']});
const packs=await assets.listPacks();
const playing=await assets.discoverObjects({kind:'playing-card',limit:3});
const combo=await assets.resolveComposition([
  {slot:'front',packId:story.manifest.id,capability:'card.face.spades.ace'},
  {slot:'back',packId:original.manifest.id,capability:'card.back'}
]);
if(packs.total!==2||playing.total!==1||combo.items.length!==2)throw new Error('fixture integration mismatch');
console.log(JSON.stringify({packs:packs.items.map(p=>p.packId),discoveredPlayingCards:playing.total,
  slots:combo.items.map(item=>({slot:item.slot,packId:item.packId,contentType:item.contentType})),
  note:'Artwork resolution only; no purchase, rule execution, ownership grant or real Tavi bridge.'},null,2));
