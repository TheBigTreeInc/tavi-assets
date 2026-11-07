"""Object graph and consumer contract tests for heterogeneous card libraries."""
import base64
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tavi_assets.core import AssetManager, AssetError, validate
from tavi_assets.host import HostGrant, HostAssetService
from tavi_assets.catalog import Catalog, StoreService
from tavi_assets.metadata import validate_metadata

SAMPLE = ROOT / 'examples' / 'storybook-decks'
ID = 'org.tavi.examples.storybook-decks'


class ObjectContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = validate(SAMPLE)

    def test_sample_has_three_distinct_decks_and_joker_pool(self):
        m = self.source
        self.assertEqual(len(m['objects']), 89)
        self.assertEqual(len(m['collections']), 4)
        self.assertEqual({x['kind'] for x in m['objects'].values()},
                         {'playing-card', 'arcana-card', 'astral-card', 'joker-card'})
        decks = [x for x in m['collections'].values() if x['kind'] == 'deck']
        self.assertEqual(sorted(len(x['entries']) for x in decks), [9, 12, 52])
        self.assertEqual(len(m['collections']['pool.jokers.storybook']['entries']), 16)
        self.assertTrue(all(obj['rulesRef'].startswith('rules.') for obj in m['objects'].values()))
        self.assertEqual(len(m['files']), 91)

    def bad(self, modifier):
        m = copy.deepcopy(self.source)
        modifier(m)
        with self.assertRaises(AssetError):
            validate_metadata(m)

    def test_unknown_collection_item(self):
        self.bad(lambda m: m['collections']['deck.arcana.lantern']['entries'][0].update(objectId='unknown.object'))

    def test_duplicate_collection_member(self):
        self.bad(lambda m: m['collections']['deck.arcana.lantern']['entries'].append(
            copy.deepcopy(m['collections']['deck.arcana.lantern']['entries'][0])))

    def test_invalid_item_quantity(self):
        self.bad(lambda m: m['collections']['deck.arcana.lantern']['entries'][0].update(quantity=True))

    def test_unrecognized_resource_ref(self):
        self.bad(lambda m: m['objects']['joker.ashkeeper'].update(resources=['private/path.svg']))

    def test_unknown_rarity(self):
        self.bad(lambda m: m['objects']['joker.ashkeeper'].update(rarity='ultramythic'))

    def test_custom_rarity_is_supported_when_declared(self):
        m = copy.deepcopy(self.source)
        m['taxonomy']['rarities']['mythic'] = {'label':'Mythic','tier':55}
        m['objects']['joker.ashkeeper']['rarity'] = 'mythic'
        validate_metadata(m)

    def test_invalid_tag_and_duplicate_tag_rejected(self):
        self.bad(lambda m: m['objects']['joker.ashkeeper'].update(tags=['__proto__']))
        self.bad(lambda m: m['objects']['joker.ashkeeper'].update(tags=['card.joker','card.joker']))

    def test_declarative_metadata_forbids_executable_payload(self):
        self.bad(lambda m: m['objects']['joker.ashkeeper'].update(script='alert(1)'))
        self.bad(lambda m: m['objects']['joker.ashkeeper'].update(rulesRef='javascript:alert(1)'))
        self.bad(lambda m: m['objects']['joker.ashkeeper']['attributes'].update(__proto__={'unsafe': True}))

    def test_oversized_and_nested_attributes_rejected(self):
        self.bad(lambda m: m['objects']['joker.ashkeeper']['attributes'].update(huge='x' * 9000))
        self.bad(lambda m: m['objects']['joker.ashkeeper']['attributes'].update(nested={'a':{'b':{'c':{'d':{'e':{'f':1}}}}}}))

    def test_unknown_manifest_field_rejected(self):
        self.bad(lambda m: m.update(executable=True))

    def test_custom_jokers_have_declarative_inert_effects(self):
        jokers = [o for o in self.source['objects'].values() if o['kind']=='joker-card']
        self.assertEqual(len(jokers),16)
        self.assertTrue(all(o['modifiers'][0]['profile']=='tavi.cards.modifiers.v1' for o in jokers))
        self.assertTrue(all(o['modifiers'][0]['effects'] for o in jokers))
        self.assertTrue(all('script' not in o and 'code' not in o for o in jokers))

    def test_modifier_script_and_unrecognized_effect_rejected(self):
        self.bad(lambda m: m['objects']['joker.ashkeeper']['modifiers'][0].update(code='eval(1)'))
        self.bad(lambda m: m['objects']['joker.ashkeeper']['modifiers'][0]['effects'][0].update(op='wallet.gold.add'))
        self.bad(lambda m: m['objects']['joker.ashkeeper']['modifiers'][0]['effects'][0].update(value=True))
        self.bad(lambda m: m['objects']['joker.ashkeeper']['modifiers'][0]['effects'][0].update(value=99999))

    def test_legacy_pack_stays_valid(self):
        self.assertTrue(validate(ROOT / 'examples' / 'cards-v1'))

    def test_schema_files_machine_readable(self):
        schema = json.loads((ROOT/'contracts/tavi-assets-pack-v1.schema.json').read_text())
        self.assertIn('objects', schema['properties'])
        self.assertIn('collections', schema['properties'])
        host = json.loads((ROOT/'contracts/tavi-assets-consumer-v1.json').read_text())
        self.assertEqual(host['feature'], 'tavi.assets/v1')
        self.assertIn('assets.objects.list', [m['method'] for m in host['requests']])


class HostMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manager = AssetManager(self.tmp.name)
        self.manager.install(SAMPLE)
        grants = {'game': HostGrant(frozenset({ID}), frozenset({'card.back','card.face.joker.ashkeeper'})),
                  'editor': HostGrant(frozenset({ID}), frozenset({'card.back'}), True),
                  'no-pack': HostGrant(frozenset({'org.tavi.other'}), frozenset({'card.back'}))}
        self.host = HostAssetService(self.manager, grants)

    def test_describe_and_object_filter(self):
        d = self.host.describe('game', ID)
        self.assertEqual(d['objectCount'], 89)
        self.assertEqual(d['capabilities'], ['card.back', 'card.face.joker.ashkeeper'])
        objs = self.host.list_objects('game', ID, kind='joker-card', rarity='rare', limit=5)
        self.assertEqual(objs['schema'], 'tavi.assets.object-list/v1')
        self.assertTrue(all(o['kind']=='joker-card' and o['rarity']=='rare' for o in objs['items']))
        self.assertTrue(all(set(o['resources']) <= {'card.back','card.face.joker.ashkeeper'} for o in objs['items']))
        self.assertGreater(objs['total'], 0)

    def test_three_deck_discovery_and_membership(self):
        found = self.host.list_collections('game', ID, kind='deck')
        self.assertEqual(len(found['items']), 3)
        for d in found['items']:
            item = self.host.get_collection('game', ID, d['id'])
            self.assertGreater(len(item['entries']), 0)
            self.assertIsNotNone(self.host.get_object('game', ID, item['entries'][0]['objectId']))

    def test_tag_filter_uses_all_of_semantics(self):
        jokers = self.host.list_objects('game', ID, tags=['card.joker', 'game.roguelike-poker'])
        self.assertEqual(jokers['total'], 16)
        no_match = self.host.list_objects('game', ID, tags=['card.joker', 'card.astral'])
        self.assertEqual(no_match['total'], 0)

    def test_paginated_object_search(self):
        p1 = self.host.list_objects('game', ID, kind='playing-card', offset=0, limit=30)
        p2 = self.host.list_objects('game', ID, kind='playing-card', offset=p1['nextOffset'], limit=30)
        self.assertEqual(len(p1['items']), 30)
        self.assertEqual(len(p2['items']), 22)
        self.assertIsNone(p2['nextOffset'])
        self.assertNotEqual(p1['items'][0]['id'], p2['items'][0]['id'])

    def test_no_grant_and_unknown_ids_fail(self):
        for fn in [lambda: self.host.describe('unknown', ID),
                   lambda: self.host.list_objects('no-pack', ID),
                   lambda: self.host.get_object('game', ID, 'joker.missing'),
                   lambda: self.host.get_collection('game', ID, 'deck.unknown')]:
            with self.assertRaises(AssetError): fn()

    def test_bad_filter_and_pagination_denied(self):
        for kwargs in [{'limit':101},{'limit':True},{'offset':-1},{'tags':'card.joker'}]:
            with self.assertRaises(AssetError): self.host.list_objects('game', ID, **kwargs)

    def test_metadata_never_contains_local_paths(self):
        doc = self.host.get_object('game', ID, 'joker.ashkeeper')
        blob = json.dumps(doc)
        self.assertNotIn('cards/jokers/', blob)
        self.assertNotIn(self.tmp.name, blob)
        self.assertNotIn('sha256', blob)

    def test_separate_customization_authorization(self):
        with self.assertRaises(AssetError): self.host.select('game', ID, 'card.back', 'indigo')
        with self.assertRaises(AssetError): self.host.select('editor', ID, 'card.face.joker.ashkeeper', 'indigo')
        response = self.host.select('editor', ID, 'card.back', 'indigo')
        self.assertEqual(response['items'][0]['selected'], 'indigo')
        self.manager = AssetManager(self.tmp.name)
        self.assertEqual(self.manager.resolved(ID,'card.back')['selected'], 'indigo')

    def test_host_wire_is_bounded_and_read_only(self):
        result = self.host.resolve_wire('editor', ID, 'card.back')
        self.assertEqual(result['encoding'], 'base64')
        self.assertTrue(base64.b64decode(result['data']).startswith(b'<svg '))
        self.assertEqual(result['contentType'], 'image/svg+xml')
        self.assertNotIn('path', json.dumps(result))
        with self.assertRaises(AssetError): self.host.resolve_wire('game', ID, 'card.face.playing.hearts.ace')

    def test_catalog_metadata_preview_and_install(self):
        catalog=Catalog(ROOT/'examples')
        preview=StoreService(self.manager, catalog)
        data=preview.metadata(ID)
        self.assertEqual(len(data['objects']),89)
        self.assertEqual(len(data['collections']),4)
        self.assertNotIn('files',data)
        self.assertTrue(any(x['id']==ID for x in preview.describe()))

    def test_named_contract_dispatch_without_caller_override(self):
        response = self.host.dispatch('game','assets.objects.list',{'packId':ID,'kind':'joker-card','limit':5})
        self.assertEqual(response['total'],16)
        self.assertEqual(len(response['items']),5)
        self.assertEqual(self.host.dispatch('game','assets.collections.get',{'packId':ID,'collectionId':'deck.astral.compass'})['kind'],'deck')
        for method, data in [
            ('assets.describe',{'packId':ID,'callerId':'editor'}),
            ('assets.resolve',{'packId':ID,'path':'private/file.svg','capability':'card.back'}),
            ('wallet.purchase',{'packId':ID}),
            ('assets.preferences.set',{'packId':ID,'capability':'card.back','variant':'indigo','force':True}),
        ]:
            with self.assertRaises(AssetError):
                self.host.dispatch('game',method,data)
        with self.assertRaises(AssetError):
            self.host.dispatch('unknown','assets.describe',{'packId':ID})

    def test_removed_pack_stays_inaccessible(self):
        self.manager.uninstall(ID)
        with self.assertRaises(AssetError): self.host.list_objects('game', ID)


if __name__ == '__main__': unittest.main()
