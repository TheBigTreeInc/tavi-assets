/** MOCK DEMONSTRATION ONLY. Never use this transport as a production Tavi bridge. */
import {createTaviAssetsClient} from '../sdk/client.mjs';
const fake = {
  info: async () => ({features:['tavi.assets/v1'],api:'1.0.0'}),
  request: async (method, params) => {
    if (method==='assets.collections.list') {
      return {schema:'tavi.assets.collection-list/v1',packId:params.packId,version:'0.1.0',items:[
        {id:'deck.playing.classic',kind:'deck',name:'Candlelit Playing Deck',tags:[],objectCount:52},
        {id:'deck.arcana.lantern',kind:'deck',name:'Lantern Arcana Deck',tags:[],objectCount:12},
        {id:'deck.astral.compass',kind:'deck',name:'Night Compass Deck',tags:[],objectCount:9}
      ]};
    }
    throw new Error('This example transport supports only collection listing');
  }
};
const assets=createTaviAssetsClient(fake);
await assets.connect();
const catalog=await assets.listCollections('org.tavi.examples.storybook-decks',{kind:'deck'});
console.log(catalog.items.map(deck=>`${deck.name}: ${deck.objectCount} cards`).join('\n'));
