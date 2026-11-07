'use strict';
let items = [], previewToken = '', tab = 'discover';
const $ = id => document.getElementById(id);
function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = String(text);
  return el;
}
function notice(message, error = false) {
  const toast = $('toast');
  toast.textContent = message;
  toast.className = 'toast show' + (error ? ' error' : '');
}
function assetImage(id, capability, variant) {
  const u = new URL('/api/preview', window.location.origin);
  u.searchParams.set('id', id);
  u.searchParams.set('capability', capability);
  if (variant) u.searchParams.set('variant', variant);
  const img = element('img'); img.src = u.toString(); img.alt = capability; img.loading = 'lazy';
  return img;
}
async function reload() {
  const response = await fetch('/api/state', {cache: 'no-store'});
  if (!response.ok) throw new Error('Cannot load local catalog');
  const data = await response.json();
  items = data.items; previewToken = data.token;
  const category = $('category'), selected = category.value;
  category.replaceChildren(element('option', null, 'All categories'));
  category.firstChild.value = '';
  for (const value of new Set(items.map(item => item.category))) {
    const option = element('option', null, value); option.value = value; category.append(option);
  }
  category.value = selected;
  render();
}
async function mutate(path, body, confirmation) {
  try {
    const response = await fetch(path, {method: 'POST', headers: {
      'Content-Type': 'application/json', 'X-Tavi-Preview-Token': previewToken
    }, body: JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Operation rejected');
    await reload(); notice(confirmation);
  } catch (error) { notice(error.message, true); }
}
function renderCard(item) {
  const card = element('article', 'asset');
  const preview = element('div', 'preview');
  const pill = element('span', 'pill', item.priceGold ? item.priceGold + ' gold · unavailable' : 'FREE');
  preview.append(pill);
  const backs = item.resources['card.back']?.variants || {};
  const variant = item.preferences['card.back'] && backs[item.preferences['card.back']] ? item.preferences['card.back'] : null;
  const face = Object.keys(item.resources).find(name => name.startsWith('card.front.') || name.startsWith('card.face.'));
  if (face) preview.append(assetImage(item.id, face));
  if (item.resources['card.back']) preview.append(assetImage(item.id, 'card.back', variant));
  card.append(preview);
  const body = element('div', 'asset-body');
  body.append(element('div', 'category', item.category), element('h3', null, item.title), element('p', null, item.summary));
  const status = element('div', 'status');
  status.append(element('span', null, item.installed ? 'Installed · v' + item.installed : 'Available on this device'),
                element('span', null, item.updateAvailable ? 'Update available' : 'v' + item.latest));
  body.append(status);
  const actions = element('div', 'actions');
  if (!item.installed) {
    const install = element('button', 'action', item.owned ? 'Install pack' : 'Ownership required');
    install.disabled = !item.owned;
    install.addEventListener('click', () => mutate('/api/install', {id: item.id}, 'Installed and verified'));
    actions.append(install);
  } else {
    if (item.updateAvailable) {
      const update = element('button', 'action', 'Update to v' + item.latest);
      update.addEventListener('click', () => mutate('/api/install', {id: item.id}, 'Update verified and activated'));
      actions.append(update);
    } else {
      const installed = element('button', 'action secondary', 'Installed ✓');
      installed.disabled = true; actions.append(installed);
    }
    const remove = element('button', 'action tertiary', 'Remove');
    remove.title = 'Remove device installation (keep variant preferences)';
    remove.addEventListener('click', () => {
      if (window.confirm('Remove this pack from this device?'))
        mutate('/api/uninstall', {id: item.id}, 'Removed from device');
    });
    actions.append(remove);
  }
  body.append(actions);
  if (item.objectCount) {
    const inventory = element('details', 'inventory');
    const summary = element('summary', null, `Inspect contents · ${item.objectCount} objects / ${item.collectionCount} collections`);
    inventory.append(summary);
    inventory.addEventListener('toggle', async () => {
      if (!inventory.open || inventory.dataset.loaded) return;
      const contents = element('div', 'inventory-content', 'Loading typed metadata…');
      inventory.append(contents);
      try {
        const response = await fetch(`/api/metadata?id=${encodeURIComponent(item.id)}`);
        if (!response.ok) throw new Error('Cannot inspect pack');
        const data = await response.json();
        inventory.dataset.loaded = '1';
        contents.replaceChildren();
        for (const group of data.collections) {
          const groupLabel = element('div', 'inventory-group', `${group.name} · ${group.kind} · ${group.entries.length} entries`);
          contents.append(groupLabel);
        }
        const filters = element('div', 'inventory-filters');
        const kindSelect = element('select');
        kindSelect.setAttribute('aria-label', 'Object type');
        const allKinds = element('option', null, 'All object types'); allKinds.value = ''; kindSelect.append(allKinds);
        for (const kind of [...new Set(data.objects.map(object => object.kind))].sort()) {
          const option = element('option', null, kind); option.value = kind; kindSelect.append(option);
        }
        const raritySelect = element('select');
        raritySelect.setAttribute('aria-label', 'Rarity');
        const allRarities = element('option', null, 'All rarities'); allRarities.value = ''; raritySelect.append(allRarities);
        for (const rarity of [...new Set(data.objects.map(object => object.rarity))].sort()) {
          const option = element('option', null, rarity); option.value = rarity; raritySelect.append(option);
        }
        filters.append(kindSelect, raritySelect); contents.append(filters);
        const results = element('div', 'inventory-results'); contents.append(results);
        function draw() {
          results.replaceChildren();
          const filtered = data.objects.filter(obj => (!kindSelect.value || obj.kind === kindSelect.value) &&
            (!raritySelect.value || obj.rarity === raritySelect.value));
          for (const obj of filtered.slice(0, 40)) {
            const line = element('div', 'inventory-object');
            if (obj.resources.length) line.append(assetImage(item.id, obj.resources[0]));
            const description = element('div');
            description.append(element('strong', null, obj.name),
              element('small', null, `${obj.kind} · ${obj.rarity} · ${obj.tags.join(', ')}`));
            line.append(description); results.append(line);
          }
          if (filtered.length > 40) results.append(element('p', null, `Showing the first 40 of ${filtered.length} matches. Narrow by type or rarity.`));
        }
        kindSelect.addEventListener('change', draw);
        raritySelect.addEventListener('change', draw);
        draw();
      } catch (error) { contents.textContent = error.message; }
    });
    body.append(inventory);
  }
  if (item.installed && item.resources['card.back']) {
    const row = element('div', 'variants');
    row.append(element('span', null, 'Card back:'));
    const values = item.resources['card.back'].variants || {};
    for (const name of Object.keys(values)) {
      const button = element('button', 'swatch' + (name === variant ? ' selected' : ''), name);
      button.setAttribute('aria-pressed', name === variant ? 'true' : 'false');
      button.addEventListener('click', () => mutate('/api/select', {id:item.id, capability:'card.back', variant:name}, 'Preference saved'));
      row.append(button);
    }
    body.append(row);
  }
  card.append(body);
  return card;
}
function render() {
  document.querySelectorAll('.nav').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tab));
  $('section-title').textContent = tab === 'installed' ? 'My assets' : 'Browse assets';
  $('section-kicker').textContent = tab === 'installed' ? 'ON THIS DEVICE' : 'CURATED COLLECTION';
  const query = $('search').value.trim().toLowerCase(), category = $('category').value;
  const visible = items.filter(item => (tab !== 'installed' || item.installed) &&
    (!category || item.category === category) &&
    (!query || (item.title + ' ' + item.summary + ' ' + item.category).toLowerCase().includes(query)));
  $('asset-count').textContent = visible.length + ' pack' + (visible.length === 1 ? '' : 's');
  const collection = $('collection'); collection.replaceChildren();
  if (!visible.length) collection.append(element('div', 'empty', 'No matching assets. Try the Browse tab or a different search.'));
  else visible.forEach(item => collection.append(renderCard(item)));
}
document.querySelectorAll('.nav').forEach(btn => btn.addEventListener('click', () => { tab = btn.dataset.tab; render(); }));
$('search').addEventListener('input', render);
$('category').addEventListener('change', render);
reload().catch(error => notice(error.message, true));
