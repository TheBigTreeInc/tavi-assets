/** Data-only portable validation. No file-system access, eval, downloads or code execution. */
export class AssetContractError extends Error {
  constructor(message) { super(message); this.name = 'AssetContractError'; }
}
const fail = (message) => { throw new AssetContractError(message); };
const ident = /^[a-z0-9][a-z0-9._-]{0,126}$/;
const token = /^[a-z][a-z0-9._-]{0,126}$/;
const defaultRarities = new Set(['common','uncommon','rare','epic','legendary','unique']);
const version = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
const sha = /^[a-f0-9]{64}$/;
export const formats = Object.freeze({svg:'image/svg+xml',png:'image/png',webp:'image/webp',jpg:'image/jpeg',jpeg:'image/jpeg',ogg:'audio/ogg',wav:'audio/wav',mp3:'audio/mpeg',json:'application/json'});
export function assertId(id, label='ID') { if (typeof id !== 'string' || !ident.test(id) || ['__proto__','constructor','prototype'].includes(id)) fail(`invalid ${label}`); return id; }
export function assertCapability(id, label='capability') { if (typeof id !== 'string' || !token.test(id) || ['__proto__','constructor','prototype'].includes(id)) fail(`invalid ${label}`); return id; }
const record = (o) => o !== null && typeof o === 'object' && !Array.isArray(o) && (Object.getPrototypeOf(o) === Object.prototype || Object.getPrototypeOf(o) === null);
function keys(o, allowed, label) { if (!record(o) || Object.keys(o).some(k=>!allowed.includes(k))) fail(`invalid ${label}`); }
const allowedTags = new Set(['svg','g','rect','circle','ellipse','path','line','polyline','polygon','text']);
const allowedAttrs = new Set(['xmlns','viewBox','width','height','x','y','x1','y1','x2','y2','cx','cy','r','rx','ry','d','fill','stroke','stroke-width','opacity','points','transform','font-size','font-family','text-anchor','id']);
/** Conservative SVG allowlist for sample vector art; not a general SVG sanitizer. */
export function validateSvg(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length > 2*1024*1024) fail('unsupported SVG');
  let s;
  try { s = new TextDecoder('utf-8', {fatal:true}).decode(bytes); } catch { fail('invalid SVG UTF-8'); }
  if (/<!|<\?|[\\]|&(?!(?:amp|lt|gt|quot|apos);)/.test(s)) fail('unsupported SVG markup');
  const stack=[]; let pos=0, root=false;
  const tags = /<\/?[A-Za-z][A-Za-z0-9-]*(?:\s+[^<>]*?)?\s*\/?>/g;
  let match;
  while ((match=tags.exec(s))!==null) {
    const text=s.slice(pos,match.index);
    if (text.includes('<') || (text.trim() && (!root || !stack.length))) fail('malformed SVG content');
    pos=tags.lastIndex;
    const raw=match[0], closing=raw.startsWith('</'), selfClosing=/\/\s*>$/.test(raw);
    const head=raw.match(/^<\/?([A-Za-z][A-Za-z0-9-]*)/);
    const tag=head?.[1];
    if (!allowedTags.has(tag)) fail('unsupported SVG element');
    if (closing) {
      if (selfClosing || raw.slice(head[0].length,-1).trim() || stack.pop()!==tag) fail('invalid SVG closing tag');
      continue;
    }
    if (stack.length===0) { if (root || tag!=='svg') fail('invalid SVG root'); root=true; }
    const afterHead = raw.slice(head[0].length, raw.length - (selfClosing?2:1));
    let rest=afterHead; const seen=new Set(); let namespace=false;
    while (rest.trim()) {
      const attr=rest.match(/^\s+([A-Za-z][A-Za-z0-9-]*)\s*=\s*"([^"]*)"/);
      if (!attr || !allowedAttrs.has(attr[1]) || seen.has(attr[1]) || /url\(|javascript:|data:|@import|[<>]/i.test(attr[2])) fail('unsafe SVG attribute');
      seen.add(attr[1]);
      if (attr[1]==='xmlns') { if (attr[2]!=='http://www.w3.org/2000/svg' || tag!=='svg') fail('invalid SVG namespace'); namespace=true; }
      rest=rest.slice(attr[0].length);
    }
    if (tag==='svg' && !namespace) fail('missing SVG namespace');
    if (!selfClosing) stack.push(tag);
  }
  if (!root || stack.length || s.slice(pos).trim()) fail('invalid SVG structure');
}
function validPath(path) {
  if (typeof path!=='string' || path.length>230 || !path || /[\\:\u0000-\u001f]/.test(path) || path.startsWith('/')) fail('unsafe asset path');
  for (const part of path.split('/')) {
    if (!part || part==='.' || part==='..' || /[ .]$/.test(part) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part)) fail('unsafe asset path');
  }
  const suffix=path.split('.').pop().toLowerCase();
  if (!Object.hasOwn(formats,suffix)) fail('unsupported asset suffix');
  return suffix;
}
function magic(bytes,suffix) {
  const eq=(a,offset=0)=>a.every((v,i)=>bytes[i+offset]===v);
  if (suffix==='svg') return validateSvg(bytes);
  if (suffix==='png'&&!eq([137,80,78,71,13,10,26,10])) fail('bad PNG');
  if (suffix==='webp'&&!(eq([82,73,70,70])&&eq([87,69,66,80],8))) fail('bad WebP');
  if (['jpg','jpeg'].includes(suffix)&&!eq([255,216,255])) fail('bad JPEG');
  if (suffix==='ogg'&&!eq([79,103,103,83])) fail('bad OGG');
  if (suffix==='wav'&&!(eq([82,73,70,70])&&eq([87,65,86,69],8))) fail('bad WAV');
  if (suffix==='mp3'&&!(eq([73,68,51])||(bytes[0]===255&&(bytes[1]&224)===224))) fail('bad MP3');
  if (suffix==='json') { try { JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes)); } catch { fail('bad JSON resource'); } }
}
const tagsValid = (a) => Array.isArray(a) && a.length<=32 && new Set(a).size===a.length && a.every(t=>typeof t==='string'&&token.test(t));
function validateModifiers(modifiers) {
  const triggers=new Set(['hand.scored','card.played','round.started','round.ended']);
  const operations=new Set(['chips.add','mult.add','mult.multiply','draw.add','discard.add']);
  const predicates=new Set(['equals','at-least','contains']);
  if(!Array.isArray(modifiers)||modifiers.length>8)fail('bad modifiers');
  for(const block of modifiers) {
    keys(block,['profile','trigger','conditions','effects'],'modifier');
    if(block.profile!=='tavi.cards.modifiers.v1'||!triggers.has(block.trigger))fail('unsupported modifier profile');
    if(!Array.isArray(block.conditions??[])||(block.conditions??[]).length>8)fail('bad conditions');
    for(const c of block.conditions??[]){
      keys(c,['field','operator','value'],'modifier condition');
      if(Object.keys(c).length!==3)fail('incomplete condition');
      assertCapability(c.field,'condition');
      if(!predicates.has(c.operator)||!(typeof c.value==='string'&&token.test(c.value)||Number.isInteger(c.value)&&c.value>=0&&c.value<=1000))fail('unsupported condition');
    }
    if(!Array.isArray(block.effects)||!block.effects.length||block.effects.length>8)fail('bad effects');
    for(const e of block.effects){
      keys(e,['op','value'],'effect');
      if(Object.keys(e).length!==2||!operations.has(e.op)||typeof e.value!=='number'||!Number.isFinite(e.value)||e.value< -1000||e.value>1000||(e.op==='mult.multiply'&&(e.value<0||e.value>100)))fail('unsupported effect');
    }
  }
}
export function validateManifest(m) {
  keys(m,['schema','id','version','type','compatibility','files','resources','display','tags','taxonomy','objects','collections'],'manifest');
  if (m.schema!=='tavi.assets.pack/v1') fail('unsupported pack schema');
  assertId(m.id,'pack ID'); if (typeof m.version!=='string'||!version.test(m.version)) fail('invalid pack version');
  assertCapability(m.type,'pack type');
  if (!record(m.compatibility) || Object.keys(m.compatibility).length!==1 || m.compatibility.host!=='tavi-assets/v1') fail('unsupported compatibility');
  if (m.display!==undefined) { keys(m.display,['name','description','style'],'display'); if (typeof m.display.name!=='string') fail('bad display name'); }
  if (!tagsValid(m.tags??[])) fail('bad pack tags');
  if (!record(m.files)||!Object.keys(m.files).length||Object.keys(m.files).length>512) fail('bad files');
  if (!record(m.resources)||!Object.keys(m.resources).length||Object.keys(m.resources).length>512) fail('bad resources');
  const seen=new Set();
  for (const [path,digest] of Object.entries(m.files)) {
    validPath(path);
    if (seen.has(path.toLowerCase())) fail('case-colliding asset paths'); seen.add(path.toLowerCase());
    if(typeof digest!=='string'||!sha.test(digest)) fail('bad digest');
  }
  for (const [id,resource] of Object.entries(m.resources)) {
    assertCapability(id);
    keys(resource,['default','variants'],'resource');
    if (typeof resource.default!=='string'||!Object.hasOwn(m.files,resource.default)) fail('missing default resource');
    if(resource.variants!==undefined&&!record(resource.variants)) fail('invalid variants');
    if(Object.keys(resource.variants??{}).length>64) fail('excessive variants');
    const paths=[resource.default];
    for (const [variant,path] of Object.entries(resource.variants??{})) { assertCapability(variant,'variant'); if(!Object.hasOwn(m.files,path)) fail('unknown variant file'); paths.push(path); }
    if(new Set(paths.map(p=>formats[validPath(p)])).size!==1) fail('variant MIME mismatch');
  }
  if (m.taxonomy!==undefined) keys(m.taxonomy,['rarities','tags'],'taxonomy');
  const rarities=m.taxonomy?.rarities??{};
  if (!record(rarities)||Object.keys(rarities).length>32) fail('invalid rarities');
  for(const [k,v] of Object.entries(rarities)) { assertCapability(k); keys(v,['label','tier'],'rarity'); if(typeof v.label!=='string'||(v.tier!==undefined&&(!Number.isInteger(v.tier)||v.tier<0||v.tier>100))) fail('bad rarity'); }
  const tagDefs=m.taxonomy?.tags??{}; if(!record(tagDefs)||Object.keys(tagDefs).length>256)fail('bad tag taxonomy');
  for(const [name,v] of Object.entries(tagDefs)){assertCapability(name,'tag');keys(v,['label','description'],'tag');if(typeof v.label!=='string'||!v.label.trim())fail('bad tag label');}
  const objects=m.objects??{}, collections=m.collections??{};
  if(!record(objects)||Object.keys(objects).length>2048||!record(collections)||Object.keys(collections).length>256) fail('bad metadata');
  for(const [id,obj] of Object.entries(objects)) {
    assertCapability(id,'object ID');
    keys(obj,['kind','name','description','rarity','tags','attributes','resources','rulesRef','modifiers'],'object');
    assertCapability(obj.kind,'object kind');
    if(typeof obj.name!=='string'||!obj.name.trim()||obj.name.length>160||!tagsValid(obj.tags??[])) fail('bad object metadata');
    const rarity=obj.rarity??'common';
    if(!(Object.keys(rarities).length?Object.hasOwn(rarities,rarity):defaultRarities.has(rarity))) fail('unknown rarity');
    if(!Array.isArray(obj.resources??[])||(obj.resources??[]).length>32||new Set(obj.resources??[]).size!==(obj.resources??[]).length||(obj.resources??[]).some(r=>!Object.hasOwn(m.resources,r))) fail('unknown object resource');
    if(obj.rulesRef!==undefined) assertCapability(obj.rulesRef,'rules ref');
    if(obj.modifiers!==undefined)validateModifiers(obj.modifiers);
    if(JSON.stringify(obj).length>20000) fail('excessive object metadata');
  }
  for(const [id,col] of Object.entries(collections)) {
    assertCapability(id,'collection ID');
    keys(col,['kind','name','description','tags','entries'],'collection');
    assertCapability(col.kind,'collection kind');
    if(typeof col.name!=='string'||!tagsValid(col.tags??[])||!Array.isArray(col.entries)||!col.entries.length||col.entries.length>512) fail('bad collection');
    const ids=new Set();
    for(const e of col.entries) { if(!record(e)||Object.keys(e).sort().join(',')!=='objectId,quantity'||!Object.hasOwn(objects,e.objectId)||ids.has(e.objectId)||!Number.isInteger(e.quantity)||e.quantity<1||e.quantity>99) fail('bad collection entry'); ids.add(e.objectId); }
  }
  return true;
}
export async function validatePack(manifest, files) {
  validateManifest(manifest);
  if (!record(files) || Object.keys(files).length!==Object.keys(manifest.files).length) fail('file inventory mismatch');
  let total=0;
  for (const [path,digest] of Object.entries(manifest.files)) {
    const bytes=files[path];
    if (!(bytes instanceof Uint8Array)||bytes.length===0||bytes.length>20*1024*1024) fail('missing or oversized file');
    total+=bytes.length; if(total>128*1024*1024) fail('oversized pack');
    magic(bytes,validPath(path));
    if (!globalThis.crypto?.subtle) fail('secure SHA-256 unavailable');
    const actual=Array.from(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes))).map(n=>n.toString(16).padStart(2,'0')).join('');
    if (actual!==digest) fail('integrity mismatch');
  }
  for (const path of Object.keys(files)) if (!Object.hasOwn(manifest.files,path)) fail('unexpected file');
  return true;
}
export function encodeBase64(bytes) {
  let text=''; for(let i=0;i<bytes.length;i+=16384) text+=String.fromCharCode(...bytes.subarray(i,i+16384));
  return btoa(text);
}
export function decodeBase64(text) {
  if(typeof text!=='string'||text.length>30*1024*1024) fail('invalid resource encoding');
  const s=atob(text); return Uint8Array.from(s,c=>c.charCodeAt(0));
}
export function cloneJSON(o) { return JSON.parse(JSON.stringify(o)); }

/** Manifest revision for trusted host approval checks; distinct from a TaviX archive SHA-256. */
export async function manifestRevision(manifest) {
  validateManifest(manifest);
  if(!globalThis.crypto?.subtle)fail('secure SHA-256 unavailable');
  function stable(v) {if(Array.isArray(v))return v.map(stable);if(record(v))return Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]));return v;}
  const bytes=new TextEncoder().encode(JSON.stringify(stable(manifest)));
  return Array.from(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes))).map(n=>n.toString(16).padStart(2,'0')).join('');
}
