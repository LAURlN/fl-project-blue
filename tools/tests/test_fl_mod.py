"""Synthetic mod sources only; generated game resources never belong in Git."""
import base64
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import test_fl_archive as fixtures

spec = importlib.util.spec_from_file_location('fl_mod', Path(__file__).parents[1] / 'fl_mod.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Edits(unittest.TestCase):
    def setUp(self):
        class Data:
            changed = set()
            values = [{'_raw': '00', 'name': 'Template', 'price': 10},
                      {'_raw': 'ff', 'name': 'Unused', 'price': 0}]

            def rows(self, id_):
                return self.values
        self.data = Data()

    def test_copy_into_reserved_slot_preserves_other_ids(self):
        before = copy.deepcopy(self.data.values)
        mod.edit(self.data, dict(resource=5, row=1, copy_from=0,
                                expect={'name': 'Unused'}, set={'name': 'Custom', 'price': 80}))
        self.assertEqual(self.data.values[0], before[0])
        self.assertEqual(len(self.data.values), 2)
        self.assertEqual(self.data.values[1], {'_raw': '00', 'name': 'Custom', 'price': 80})

    def test_append_and_reject_stale_or_unknown_edits(self):
        mod.edit(self.data, dict(resource=5, row='append', copy_from=0, set={'name': 'New'}))
        self.assertEqual(len(self.data.values), 3)
        for op in [dict(resource=5, row=1, expect={'name': 'Wrong'}),
                   dict(resource=5, row=0, set={'typo': 1}),
                   dict(resource=5, row=0, set={'_raw': 'ff'}),
                   dict(resource=5, row=99), dict(resource=5, row=0, copy_from=-1)]:
            with self.subTest(op=op), self.assertRaises(ValueError):
                mod.edit(self.data, op)

    def test_localized_values_follow_resource_order(self):
        tables = {5: [{'_raw': '00', 'name': 'A'}], 6: [{'_raw': '00', 'name': 'B'}]}
        self.data.rows = lambda id_: tables[id_]
        mod.edit(self.data, dict(resources=[5, 6], row=0, localized={'name': ['Holzschwert', 'Wooden Sword']}))
        self.assertEqual([tables[5][0]['name'], tables[6][0]['name']], ['Holzschwert', 'Wooden Sword'])
        with self.assertRaises(ValueError):
            mod.edit(self.data, dict(resources=[5, 6], row=0, localized={'name': ['only one']}))

    def test_runtime_layout_rejects_incomplete_growth(self):
        data = type('Data', (), {})()
        categories = [dict(category=c) for c, size in enumerate(mod.CATEGORY_SIZES) for _ in range(size)]
        tables = {base + slot: copy.deepcopy(categories) for base in mod.data_tools.ITEM_BASES
                  for slot in range(9)}
        for base, count in zip(mod.data_tools.STAT_BASES, mod.CATEGORY_SIZES):
            tables.update({base + slot: [{}] * count for slot in range(9)})
        tables.update({id_: [{}] * count for id_, count in zip(mod.data_tools.RECIPE_TABLES, mod.RECIPE_COUNTS)})
        data.rows = lambda id_: tables[id_]
        mod.validate_runtime_layout(data)
        tables[8388].append({})  # each Life may grow independently
        mod.validate_runtime_layout(data)
        tables[6800].append(dict(category=0))
        with self.assertRaisesRegex(ValueError, 'matching item counts'):
            mod.validate_runtime_layout(data)
        for base in mod.data_tools.ITEM_BASES:
            for slot in range(9):
                if base + slot != 6800:
                    tables[base + slot].append(dict(category=0))
        with self.assertRaisesRegex(ValueError, 'Category stats'):
            mod.validate_runtime_layout(data)
        for slot in range(9):
            tables[6720 + slot].append({})
        mod.validate_runtime_layout(data)
        tables[6793][-1]['category'] = 1
        with self.assertRaisesRegex(ValueError, 'categories must match'):
            mod.validate_runtime_layout(data)


class Builds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / 'source.bin'
        self.archive.write_bytes(fixtures.fixture())
        self.tree = self.root / 'tree'
        with contextlib.redirect_stdout(io.StringIO()):
            self.original = fixtures.fl.extract(self.archive, self.tree)
        self.source = self.root / 'mod'
        self.source.mkdir()
        (self.source / 'replacement.bin').write_bytes(b'New member of a different size' * 20)
        self.spec = dict(format='fl-mod-source-v1', name='Synthetic', files={'data/test.scr': 'replacement.bin'})

    def build(self, target='output'):
        (self.source / 'mod.json').write_text(json.dumps(self.spec))
        # The fixture has five resources, not the game's hundreds of typed tables.
        with patch.object(mod.data_tools, 'validate', return_value={'errors': []}), \
                patch.object(mod, 'validate_runtime_layout'):
            return mod.build(self.tree, self.source, self.root / target)

    def test_virtual_member_rebuild_and_source_immutability(self):
        result = self.build()
        self.assertEqual([r['id'] for r in result['resources']], [2])
        entry = result['resources'][0]
        raw = mod.archive.decompress_nintendo((self.root / 'output' / entry['file']).read_bytes())[0]
        member = mod.archive.parse_pack(raw)[0]
        self.assertEqual(mod.archive.span(raw, member['offset'], member['size']),
                         (self.source / 'replacement.bin').read_bytes())
        self.assertEqual(result['virtual_sizes']['3'], member['size'])
        self.assertEqual((self.tree / 'data/test.scr').read_bytes(), b'original member')
        self.assertEqual((self.tree / '.fl_archive/original.bin').read_bytes(), self.archive.read_bytes())
        for original in self.original['entries']:
            self.assertEqual(mod.archive.sha((self.tree / original['path']).read_bytes()), original['sha256'])
        with self.assertRaises(ValueError):
            self.build()  # no overwriting an active overlay
        with patch.object(mod.data_tools, 'validate', return_value={'errors': []}), \
                patch.object(mod, 'validate_runtime_layout'):
            mod.build(self.tree, self.source, self.root / 'output', replace=True)
        self.assertTrue((self.root / 'output' / 'overlay.json').is_file())
        (self.root / 'other').mkdir()
        with self.assertRaises(ValueError):
            self.build('other')  # --replace never overwrites a directory that is not an overlay

    def test_reject_parent_conflict_index_and_path_escape(self):
        for files in [{'2': 'replacement.bin', '3': 'replacement.bin'},
                      {'1': 'replacement.bin'}, {'0': '../source.bin'}]:
            self.spec['files'] = files
            with self.subTest(files=files), self.assertRaises(ValueError):
                self.build()
            self.assertFalse((self.root / 'output').exists())

    def test_textures_and_models_from_base_resources(self):
        import test_fl_zmdl
        ztex = mod.ztex
        tree = self.root / 'assets'
        tree.mkdir()
        base_tex = ztex.build([dict(name=n, width=8, height=8, format='rgb565', mips=1, data=bytes(128))
                               for n in ('at_a', 'tex_b')], flags=2, extra=bytes.fromhex('ffffffff03000000'))
        base_model = test_fl_zmdl.make_zmdl()
        files = {10: base_tex, 11: base_model}
        for id_, raw in files.items():
            (tree / f'{id_}.bin').write_bytes(raw)
        data = type('Data', (), dict(
            entries={id_: dict(sha256=mod.archive.sha(raw)) for id_, raw in files.items()},
            path=lambda _, id_: tree / f'{id_}.bin'))()
        image = bytes(c for _ in range(16 * 16) for c in (220, 150, 80, 255))
        ztex.png_write(self.source / 'art.png', 16, 16, image)
        built = mod.build_texture(data, self.source, dict(png='art.png', format='etc1'), 10, {})
        info = ztex.parse(built)
        self.assertEqual([i['name'] for i in info['images']], ['at_a', 'tex_b'])
        self.assertEqual(info['extra'], bytes.fromhex('ffffffff03000000'))
        self.assertEqual({(i['width'], i['format']) for i in info['images']}, {(16, 'etc1')})
        self.assertLess(max(abs(a - b) for a, b in zip(ztex.decode(built, 1)[2], image)), 6)
        mesh = dict(format='fl-mesh-v1', triangles=[[0, 1, 2]], vertices=[
            dict(position=p, normal=(0, 0, 1), uv0=(0, 0), outline_normal=(0, 0, 1))
            for p in ((0, 0, 0), (1, 0, 0), (0, 1, 0))])
        (self.source / 'mesh.json').write_text(json.dumps(mesh))
        model = mod.build_model(data, self.source, dict(mesh='mesh.json'), 11)
        self.assertEqual(mod.zmdl.parse(model)['meshes'][0]['vertex_count'], 3)
        glb_data = mod.zmdl.export_gltf(base_model)
        (self.source / 'model.glb').write_bytes(glb_data)
        model_glb = mod.build_model(data, self.source, dict(glb='model.glb'), 11)
        self.assertEqual(mod.zmdl.parse(model_glb)['meshes'][0]['vertex_count'], 4)
        copy_ = mod.build_model(data, self.source, dict(texture_names={'tex_test': 'tex_own'}), 11)
        self.assertEqual(mod.zmdl.parse(copy_)['materials'][0]['texture'], 'tex_own')
        with self.assertRaisesRegex(ValueError, 'mesh and/or texture_names'):
            mod.build_model(data, self.source, {}, 11)
        (tree / '11.bin').write_bytes(base_model + b'x')  # modified source is refused
        with self.assertRaisesRegex(ValueError, 'modified'):
            mod.build_model(data, self.source, dict(mesh='mesh.json'), 11)

    def test_item_icons_must_come_from_the_item_icon_family(self):
        ztex = mod.ztex
        tree = self.root / 'icons'
        tree.mkdir()
        for id_, name, size in ((100, 'icn_itm401_0001_10default', 8), (101, 'icn_cmd029', 8)):
            (tree / f'{id_}.bin').write_bytes(ztex.build([dict(name=name, width=size, height=size, format='a8',
                                                                mips=1, data=bytes(size * size))]))
        icons = [{'icon_id': 100}, {'icon_id': 101}]
        items = [{'icon_index': 0}]
        data = type('Data', (), dict(changed={mod.ITEM_NAMES}, path=lambda _, id_: tree / f'{id_}.bin',
                                     rows=lambda _, id_: icons if id_ == mod.ICON_TABLES else items))()
        mod.validate_item_icons(data)
        items[0]['icon_index'] = 1   # a command-prompt slot: drawn with a 128x32 cell in game
        with self.assertRaisesRegex(ValueError, 'icn_itm'):
            mod.validate_item_icons(data)
        # replacing an icon texture with a different size is refused (fixed UI cell)
        entries = {100: dict(sha256=mod.archive.sha((tree / '100.bin').read_bytes()))}
        data = type('Data', (), dict(entries=entries, path=lambda _, id_: tree / f'{id_}.bin'))()
        ztex.png_write(self.source / 'big.png', 16, 16, bytes(16 * 16 * 4))
        with self.assertRaisesRegex(ValueError, 'UI cell'):
            mod.build_texture(data, self.source, dict(png='big.png'), 100, {})
        ztex.png_write(self.source / 'ok.png', 8, 8, bytes(8 * 8 * 4))
        mod.build_texture(data, self.source, dict(png='ok.png'), 100, {})

    def test_fingerprint_changes_with_base_header(self):
        self.assertNotEqual(mod.fnv32(b'abc'), mod.fnv32(b'abd'))
        self.assertEqual(mod.fnv32(b''), '811c9dc5')


class MonsterTables(unittest.TestCase):
    """Whole-table donor copies and the loot-table contract of 0x332904 (synthetic rows)."""

    def loot_row(self, monster, key, item=2204):
        return {'_raw': '00' * 36, 'level_key': key, 'monster_id': monster, 'bounty_threshold': 0,
                'bounty_item': 0xffffffff, **{f'drop_threshold_{i}': 77 if i == 0 else 0 for i in range(5)},
                **{f'drop_item_{i}': item if i == 0 else 0xffffffff for i in range(5)}}

    def loot_data(self, rows, monsters=275):
        tables = {mod.MONSTER_LOOT: rows, mod.MONSTER_NAMES: [{}] * monsters}
        return type('Data', (), {'changed': {mod.MONSTER_LOOT}, 'rows': lambda _, id_: tables[id_]})()

    def test_new_last_block_gets_one_terminator(self):
        rows = [self.loot_row(11, 1), self.loot_row(11, 100), self.loot_row(271, 1), self.loot_row(274, 1),
                self.loot_row(274, 100)]
        data = self.loot_data(rows)
        mod.terminate_monster_loot(data)
        self.assertEqual(len(rows), 6)
        end = rows[-1]
        self.assertEqual((end['monster_id'], end['level_key'], end['bounty_item']), (0xffff, 255, 0xffffffff))
        self.assertEqual([end[f'drop_item_{i}'] for i in range(5)], [0xffffffff] * 5)
        self.assertEqual([end[f'drop_threshold_{i}'] for i in range(5)], [0] * 5)
        mod.terminate_monster_loot(data)            # idempotent: still exactly one terminator
        self.assertEqual([r['monster_id'] for r in rows], [11, 11, 271, 274, 274, 0xffff])
        # the loader's walk (0x332904): each block ends at a row of another monster, inside the table
        blocks, at = {}, 0
        for monster in range(275):
            count = 0
            while rows[at]['monster_id'] == monster:
                count, at = count + 1, at + 1
            blocks[monster] = count
        self.assertEqual((blocks[11], blocks[271], blocks[274], at), (2, 1, 2, 5))

    def test_unchanged_table_is_left_alone(self):
        rows = [self.loot_row(271, 1)]
        data = self.loot_data(rows)
        data.changed = set()
        mod.terminate_monster_loot(data)
        self.assertEqual(len(rows), 1)

    def test_loot_order_and_monster_range(self):
        for rows in ([self.loot_row(274, 1), self.loot_row(11, 1)],      # block out of order
                     [self.loot_row(11, 100), self.loot_row(11, 1)],     # level keys out of order
                     [self.loot_row(11, 1), self.loot_row(11, 1)],       # duplicate key
                     [self.loot_row(275, 1)]):                           # no such monster
            with self.subTest(rows=[(r['monster_id'], r['level_key']) for r in rows]), \
                    self.assertRaises(ValueError):
                mod.terminate_monster_loot(self.loot_data(rows))

    def test_table_copy_takes_the_whole_donor_document(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = {10: b'donor battle file', 11: b'reserve battle file', 12: b'other table', 13: b'model'}
            for id_, value in raw.items():
                (root / f'{id_}').write_bytes(value)
            documents = {10: {'format': 'fl-scr-v1', 'resource_id': 10, 'sections': [{'rows': [{'hp': 46}]}]}}
            data = type('Data', (), dict(
                entries={id_: dict(sha256=mod.archive.sha(v)) for id_, v in raw.items()},
                cache={}, changed=set(), path=lambda _, id_: root / f'{id_}',
                document=lambda _, id_: documents[id_]))()
            schemas = {10: {'name': 'monster_battle_parameters'}, 11: {'name': 'monster_battle_parameters'},
                       12: {'name': 'spawn_groups'}}
            with patch.object(mod.scr, 'schemas', return_value=schemas):
                rest = mod.copy_tables(data, [dict(resource=11, base=10), dict(resource=13, base=10)])
                self.assertEqual(rest, [dict(resource=13, base=10)])     # raw copies stay for content.apply
                self.assertEqual(data.changed, {11})
                self.assertEqual(data.cache[11]['sections'], documents[10]['sections'])
                self.assertEqual(data.cache[11]['resource_id'], 11)
                data.cache[11]['sections'][0]['rows'][0]['hp'] = 60      # later edits never touch the donor
                self.assertEqual(documents[10]['sections'][0]['rows'][0]['hp'], 46)
                for copies, message in (([dict(resource=11, base=10)], 'twice'),
                                        ([dict(resource=12, base=10)], 'same schema'),
                                        ([dict(resource=11, base=99)], 'Unknown')):
                    with self.subTest(copies=copies), self.assertRaisesRegex(ValueError, message):
                        mod.copy_tables(data, copies)
                data.changed = set()
                (root / '10').write_bytes(b'modified donor')
                with self.assertRaisesRegex(ValueError, 'modified'):
                    mod.copy_tables(data, [dict(resource=11, base=10)])

    def test_spawn_groups_and_monster_units_are_checked(self):
        groups = [{'monsters': [274, 11] + [0xffff] * 6, 'weights': [40, 60] + [0] * 6}]
        monsters = [{'unit_index': 12}] * 275
        tables = {mod.MONSTER_NAMES: monsters, mod.UNIT_NAMES: [{}] * 1582, 7290: groups}
        tables.update({id_: monsters for id_ in mod.MONSTER_TABLES})
        data = type('Data', (), {'changed': {7290, 6920}, 'rows': lambda _, id_: tables[id_]})()
        mod.validate_monsters(data)
        groups[0]['monsters'][1] = 275
        with self.assertRaisesRegex(ValueError, 'invalid monster 275'):
            mod.validate_monsters(data)
        groups[0]['monsters'][1] = 11
        tables[6941] = [{'unit_index': 1582}] * 275
        with self.assertRaisesRegex(ValueError, 'out of range'):
            mod.validate_monsters(data)



def make_table(columns, rows, pointer_records=None):
    """Build a minimal, valid SCR table from named columns/rows for stack tests.

    `columns` is [(name, type_id, count, bits, shift)].  Offset allocation is synthetic;
    the real schema layouts are irrelevant to allocation/merge behaviour.  Pointer
    columns get records appended after the row array, so an appearance row can point
    at its model/texture pair exactly like the shipped table.
    """
    types = mod.scr.TYPES
    width, laid_out = 0, []
    for name, type_id, count, bits, shift in columns:
        laid_out.append(dict(name=name, type=types[type_id][0], type_id=type_id, offset=width,
                             count=count, bits=bits, shift=shift))
        width += types[type_id][1] * count
    info = 32 + 6 * len(laid_out)
    rows_offset = info + 12
    table_end = rows_offset + width * len(rows)
    extras = bytearray()
    extra_offsets = {}
    for index, record in (pointer_records or {}).items():
        extra_offsets[index] = table_end + len(extras)
        extras.extend(record)
    string_pool = bytearray()
    string_offsets = {}
    for index, row in enumerate(rows):
        for column in laid_out:
            if column['type_id'] not in (5, 6, 10):
                continue
            require_value = row[column['name']]
            encoded = mod.scr.write_string(require_value, column['type_id'] == 5)
            string_offsets[(index, column['name'])] = table_end + len(extras) + len(string_pool)
            string_pool.extend(encoded)
            if column['type_id'] == 6:
                string_pool.extend(b'\0' * (-len(string_pool) % 4))
    raw = bytearray(table_end)
    raw[:4] = mod.scr.MAGIC
    raw[9] = len(laid_out)
    struct.pack_into('<I', raw, 16, 32)
    struct.pack_into('<I', raw, 20, info)
    struct.pack_into('<3I', raw, info, len(rows), width, rows_offset)
    for index, column in enumerate(laid_out):
        struct.pack_into('<BBHH', raw, 32 + 6 * index, column['type_id'], column['count'],
                         column['bits'], column['offset'] * 32 + column['shift'])
    encoded_rows = []
    for index, row in enumerate(rows):
        encoded = bytearray(width)
        for column in laid_out:
            value = row[column['name']]
            size = types[column['type_id']][1]
            if column['type_id'] in (5, 6, 10):
                value = string_offsets[(index, column['name'])]
            elif column['type_id'] == 9:
                value = extra_offsets.get(index, 0)
            values = value if column['count'] > 1 else [value]
            for j, item in enumerate(values):
                encoded[column['offset'] + j * size:column['offset'] + (j + 1) * size] = \
                    int(item).to_bytes(size, 'little')
        raw[rows_offset + index * width:rows_offset + (index + 1) * width] = encoded
        encoded_rows.append(bytes(encoded))
    raw.extend(extras)
    raw.extend(string_pool)
    struct.pack_into('<I', raw, 12, len(raw) - 32)
    document_rows = []
    for index, row in enumerate(rows):
        document = dict(row)
        for column in laid_out:
            if column['type_id'] == 9:
                document[column['name']] = {'offset': extra_offsets.get(index, 0)}
        document['_raw'] = encoded_rows[index].hex()
        document_rows.append(document)
    document = dict(format='fl-scr-v1', resource_id=None, wrapper=False,
                    sections=[dict(kind='table', original=base64.b64encode(bytes(raw)).decode(),
                                   row_size=width, columns=copy.deepcopy(laid_out), rows=document_rows)])
    return bytes(raw), document


def make_pack(members):
    """Build a minimal named FL pack from [(path, payload)] for member-merge tests."""
    body, records = bytearray(), []
    for name, payload in members:
        offset = 20 + len(body)
        body.extend(payload)
        namepos = 20 + len(body)
        body.extend(name.encode('ascii') + b'\0')
        body.extend(b'\0' * (-len(body) % 4))
        records.append((name, len(payload), namepos, offset))
    table = 20 + len(body)
    raw = bytearray(table + 20 * len(records))
    raw[:4] = mod.archive.PACK_MAGIC
    struct.pack_into('<I', raw, 4, len(raw) - 20)
    struct.pack_into('<I', raw, 16, table)
    raw[20:table] = body
    for index, (name, size, namepos, offset) in enumerate(records):
        struct.pack_into('<4B4I', raw, table + 20 * index, 0, len(name), name.rfind('/') + 1,
                         name.rfind('.') + 1, 1, size, namepos, offset)
    return bytes(raw)


class FakeModData:
    """The subset of ModData the builder needs, backed by a synthetic extraction directory."""

    def __init__(self, root):
        self.root = Path(root)
        self.entries, self.paths, self.original_docs, self.cache = {}, {}, {}, {}
        self.changed = set()
        count = 9000
        header = bytearray(8 + 13 * count)
        struct.pack_into('<I', header, 0, count)
        metadata = self.root / '.fl_archive'
        metadata.mkdir(parents=True)
        (metadata / 'original.bin').write_bytes(header)
        self.manifest = dict(count=count, archive_size=len(header), physical_ids=[], relations=[], entries=[])

    def add(self, id_, raw, document=None):
        path = self.root / f'{id_:05d}.bin'
        path.write_bytes(raw)
        self.entries[id_] = dict(id=id_, path=str(path), sha256=mod.archive.sha(raw))
        self.paths[id_] = path
        if document is not None:
            self.original_docs[id_] = document
            self.cache[id_] = copy.deepcopy(document)
        self.manifest['physical_ids'].append(id_)
        return self.entries[id_]

    def path(self, id_):
        return self.paths[id_]

    def document(self, id_):
        return self.cache[id_]

    def rows(self, id_):
        return self.document(id_)['sections'][0]['rows']

    def original_document(self, id_):
        return self.original_docs[id_]

    def original_rows(self, id_):
        return self.original_docs[id_]['sections'][0]['rows']

    def original_bytes(self, id_):
        return self.paths[id_].read_bytes()


def synthetic_weapon_data(base):
    """Two dummy weapons/icons/appearances/recipes and all art resources they replace."""
    data = FakeModData(base / 'extraction')
    schemas = {}

    def table(id_, name, columns, rows, pointer_records=None):
        raw, document = make_table(columns, rows, pointer_records)
        document['resource_id'] = id_
        data.add(id_, raw, document)
        schemas[id_] = dict(name=name, row_size=document['sections'][0]['row_size'],
                            columns=document['sections'][0]['columns'], resource_ids=[id_])

    table(6702, 'item_symbols', [('symbolic_id', 6, 1, 0, 0)], [
        {'symbolic_id': 'ID_Item_weapon_real000001'},
        {'symbolic_id': 'ID_Item_weapon_real000002'},
        {'symbolic_id': 'ID_Item_weapon_dummy000001'},
        {'symbolic_id': 'ID_Item_weapon_dummy000002'}])
    table(6792, 'items', [('name', 6, 1, 0, 0), ('category', 1, 1, 0, 0),
                          ('icon_index', 2, 1, 0, 0), ('buy_price', 3, 1, 0, 0)], [
        {'name': 'Template', 'category': 0, 'icon_index': 0, 'buy_price': 10},
        {'name': 'Other', 'category': 0, 'icon_index': 0, 'buy_price': 20},
        {'name': 'ぶき', 'category': 0, 'icon_index': 0, 'buy_price': 0},
        {'name': 'ぶき', 'category': 0, 'icon_index': 0, 'buy_price': 0}])
    table(6720, 'weapon_stats', [('attack', 2, 1, 0, 0)], [
        {'attack': 1}, {'attack': 2}, {'attack': 0}, {'attack': 0}])
    table(8686, 'icons', [('icon_id', 3, 1, 0, 0), ('name', 6, 1, 0, 0)], [
        {'icon_id': 8000, 'name': 'icn_itm000'},
        {'icon_id': 8001, 'name': 'icn_itm001'},
        {'icon_id': 8002, 'name': 'icn_itm002'},
        {'icon_id': 8003, 'name': 'icn_itm003'}])
    table(8390, 'recipes', [('recipe_key', 2, 1, 0, 0), ('rank_requirement', 1, 1, 0, 0),
                            ('unlock_rank', 2, 1, 0, 0),
                            ('output_items', 2, 4, 0, 0), ('category_icon_index', 2, 1, 0, 0)], [
        {'recipe_key': 10, 'rank_requirement': 2, 'unlock_rank': 2,
         'output_items': [0, 65535, 65535, 65535], 'category_icon_index': 0},
        {'recipe_key': 11, 'rank_requirement': 16, 'unlock_rank': 16,
         'output_items': [1, 65535, 65535, 65535], 'category_icon_index': 0},
        {'recipe_key': 12, 'rank_requirement': 16, 'unlock_rank': 16,
         'output_items': [1, 65535, 65535, 65535], 'category_icon_index': 0}])
    table(8405, 'shop_inventory', [('stock_tier', 2, 1, 0, 0), ('item_id', 3, 1, 0, 0)], [
        {'stock_tier': 1, 'item_id': 0}])

    appearance_columns = [('c00', 9, 1, 0, 0), ('c01', 6, 1, 0, 0), ('c02', 3, 1, 0, 0),
                          ('c03', 3, 1, 0, 0), ('c04', 3, 1, 0, 0), ('c05', 3, 1, 0, 0)]
    records = {}
    for index, (label, model, texture) in enumerate([
            ('配信用ダミー・片手剣　１', 8100, 8102), ('配信用ダミー・片手剣　２', 8101, 8103),
            ('配信用ダミー・上半身　１', 8104, 8105)]):
        record = struct.pack('<5I', 0x01200000, model, 0x01000000, texture, 0xffffffff)
        record += (label.replace('配信用ダミー', 'dummy')).encode('utf-16le') + b'\0\0'
        records[index] = record
    table(8714, 'appearance', appearance_columns, [
        {'c00': 0, 'c01': label, 'c02': 0, 'c03': 0, 'c04': 0, 'c05': 0}
        for label in ('配信用ダミー・片手剣　１', '配信用ダミー・片手剣　２',
                      '配信用ダミー・上半身　１')], records)

    import test_fl_zmdl
    model = test_fl_zmdl.make_zmdl()
    texture = mod.ztex.build([dict(name='tex_dummy', width=8, height=8, format='rgb565', mips=1,
                                   data=bytes(128))], flags=0, extra=b'')
    for id_ in (8100, 8101, 8104):
        data.add(id_, model)
    for id_ in (8102, 8103, 8105):
        data.add(id_, texture)
    for index in range(4):
        data.add(8000 + index, mod.ztex.build([dict(name=f'icn_itm{index:03d}', width=8, height=8,
                                                     format='a8', mips=1, data=bytes(64))],
                                              flags=0, extra=b''))
    return data, schemas


def write_weapon_mod(folder, title, dummy_symbol, new_symbol, texture_index):
    folder.mkdir()
    mod.ztex.png_write(folder / 'icon.png', 8, 8,
                       bytes(c for _ in range(64) for c in (200, 100, 50, 255)))
    mod.ztex.png_write(folder / 'model.png', 8, 8,
                       bytes(c for _ in range(64) for c in (80, 140, 200, 255)))
    mesh = dict(format='fl-mesh-v1', triangles=[[0, 1, 2]], vertices=[
        dict(position=p, normal=(0, 0, 1), uv0=(0, 0), outline_normal=(0, 0, 1))
        for p in ((0, 0, 0), (1, 0, 0), (0, 1, 0))])
    (folder / 'mesh.json').write_text(json.dumps(mesh))
    spec = dict(format='fl-mod-source-v1', name=title,
                allocate=dict(weapon='$sword', item_icon='$icon', weapon_appearance='$slot',
                              carpentry_recipe='$recipe'),
                edits=[
                    dict(resource=6702, row='$sword', expect={'symbolic_id': dummy_symbol},
                         set={'symbolic_id': new_symbol}),
                    dict(resource=6792, row='$sword', copy_from=0, expect={'category': 0},
                         set={'name': title, 'category': 0, 'icon_index': '$icon', 'buy_price': 100}),
                    dict(resource=6720, row='$sword.stat_row', copy_from=0,
                         set={'attack': 10 + texture_index}),
                    dict(resource=8405, row='append', copy_from=0,
                         set={'stock_tier': 1, 'item_id': '$sword'}),
                    dict(resource=8390, row='$recipe', copy_from=0,
                         set={'recipe_key': 100 + texture_index,
                              'output_items': ['$sword', 65535, 65535, 65535],
                              'rank_requirement': 2, 'unlock_rank': 2})],
                textures=[dict(resources='$icon.texture_ids', png='icon.png'),
                          dict(resource='$slot.texture_id', png='model.png')],
                models=[dict(resource='$slot.model_id', base='$slot.model_id', mesh='mesh.json')])
    (folder / 'mod.json').write_text(json.dumps(spec))
    return folder


class StackBuilds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data, self.schemas = synthetic_weapon_data(self.root)
        self.mods = [write_weapon_mod(self.root / 'sword-a', 'Sword A',
                                      'ID_Item_weapon_dummy000001', 'ID_Item_SwordA', 1),
                     write_weapon_mod(self.root / 'sword-b', 'Sword B',
                                      'ID_Item_weapon_dummy000002', 'ID_Item_SwordB', 2)]

    def build(self, mods=None):
        with patch.object(mod, 'ModData', return_value=self.data), \
                patch.object(mod.scr, 'schemas', return_value=self.schemas), \
                patch.object(mod.data_tools, 'validate', return_value={'errors': []}), \
                patch.object(mod, 'validate_runtime_layout'), \
                patch.object(mod, 'validate_item_icons'):
            return mod.build_stack(self.root / 'extraction', self.root / 'overlay',
                                   mods or self.mods)

    def test_two_weapon_mods_merge_into_one_overlay(self):
        manifest = self.build()
        self.assertEqual([entry['order'] for entry in manifest['sources']], [0, 1])
        self.assertEqual([entry['name'] for entry in manifest['sources']], ['Sword A', 'Sword B'])
        self.assertEqual(len({entry['digest'] for entry in manifest['sources']}), 2)
        for pool in ('item:weapon', 'item_icon', 'weapon_appearance', 'carpentry_recipe'):
            values = [entry['value'] for entry in manifest['allocations'] if entry['pool'] == pool]
            self.assertEqual(len(values), 2, pool)
            self.assertEqual(len(set(values)), 2, pool)
        self.assertEqual([row['name'] for row in self.data.rows(6792)[2:]], ['Sword A', 'Sword B'])
        self.assertEqual([row['icon_index'] for row in self.data.rows(6792)[2:]], [1, 2])
        self.assertEqual([row['attack'] for row in self.data.rows(6720)[2:]], [11, 12])
        self.assertEqual([row['item_id'] for row in self.data.rows(8405)[1:]], [2, 3])
        self.assertEqual([row['output_items'][0] for row in self.data.rows(8390)[1:]], [2, 3])
        self.assertTrue((self.root / 'overlay' / 'overlay.json').is_file())
        resource_ids = {entry['id'] for entry in manifest['resources']}
        self.assertEqual(len(resource_ids), len(manifest['resources']))
        self.assertTrue({8001, 8002, 8100, 8101, 8102, 8103} <= resource_ids)

    def test_auto_allocation_is_distinct_and_guarded(self):
        weapons = [allocation for allocation in self.data.rows(6702)[2:]]
        self.assertEqual([row['symbolic_id'] for row in weapons],
                         ['ID_Item_weapon_dummy000001', 'ID_Item_weapon_dummy000002'])
        allocator = mod.Allocator(self.data)
        first = allocator.allocate('weapon', 'a', 'A')
        second = allocator.allocate('weapon', 'b', 'B')
        self.assertNotEqual(first.value, second.value)
        self.assertNotEqual(first.resolve('stat_row'), second.resolve('stat_row'))
        icon_a = allocator.allocate('item_icon', 'ia', 'A')
        icon_b = allocator.allocate('item_icon', 'ib', 'B')
        self.assertNotEqual(icon_a.value, icon_b.value)
        self.assertNotEqual(icon_a.resolve('texture_ids'), icon_b.resolve('texture_ids'))
        appearance_a = allocator.allocate('weapon_appearance', 'ma', 'A')
        appearance_b = allocator.allocate('weapon_appearance', 'mb', 'B')
        self.assertNotEqual(appearance_a.value, appearance_b.value)
        self.assertNotEqual(appearance_a.resolve('model_id'), appearance_b.resolve('model_id'))
        self.assertNotEqual(appearance_a.resolve('texture_id'), appearance_b.resolve('texture_id'))
        gear = allocator.allocate('gear_appearance', 'mg', 'A')
        self.assertNotIn(gear.value, (appearance_a.value, appearance_b.value))
        self.assertEqual((gear.resolve('model_id'), gear.resolve('texture_id')), (8104, 8105))
        recipe_a = allocator.allocate('carpentry_recipe', 'ra', 'A')
        recipe_b = allocator.allocate('carpentry_recipe', 'rb', 'B')
        self.assertNotEqual(recipe_a.value, recipe_b.value)
        self.assertEqual(recipe_a.resolve('table'), 8390)
        self.assertEqual(first.pool, 'item:weapon')
        self.assertIn((6702, first.value), allocator.guards)
        self.assertEqual(allocator.guards[(6702, first.value)]['symbolic_id'],
                         'ID_Item_weapon_dummy000001')
        self.assertEqual(allocator.guards[(8390, recipe_a.value)]['rank_requirement'], 16)

    def test_later_source_can_reference_an_earlier_symbol(self):
        first = self.root / 'first'
        first.mkdir()
        (first / 'mod.json').write_text(json.dumps(dict(
            format='fl-mod-source-v1', name='First', allocate={'weapon': '$shared'},
            edits=[dict(resource=6702, row='$shared', set={'symbolic_id': 'ID_Item_Shared'}),
                   dict(resource=6792, row='$shared', copy_from=0,
                        set={'name': 'Shared Sword', 'category': 0, 'icon_index': 0, 'buy_price': 50})])))
        second = self.root / 'second'
        second.mkdir()
        (second / 'mod.json').write_text(json.dumps(dict(
            format='fl-mod-source-v1', name='Second',
            edits=[dict(resource=8405, row='append', copy_from=0,
                        set={'stock_tier': 1, 'item_id': '$shared'})])))
        manifest = self.build([first, second])
        self.assertEqual([entry['value'] for entry in manifest['allocations']], [2])
        self.assertEqual(self.data.rows(8405)[-1]['item_id'], 2)

    def test_member_table_and_whole_member_replacements_share_pack(self):
        data = FakeModData(self.root / 'pack-extraction')
        parent, edited, replaced = 9900, 9901, 9902
        edited_name, replaced_name = 'unit/mon/x/parm/edit.scr', 'unit/mon/x/art/replace.tex'
        data.add(edited, b'old-edited')
        data.add(replaced, b'old-tex')
        data.add(parent, make_pack([(edited_name, b'old-edited'), (replaced_name, b'old-tex')]))
        data.entries[edited].update(parent=parent, path=edited_name)
        data.entries[replaced].update(parent=parent, path=replaced_name)
        state = mod.MergeState(data)
        state.claim_table_edit(edited, 'Table mod')
        state.add_resource(replaced, b'new-tex', 'Texture mod', 'Texture')
        updates = state.finalize_resources({edited: b'new-edited'})
        self.assertEqual(set(updates), {parent})
        values = {member['name']: mod.archive.span(updates[parent], member['offset'], member['size'])
                  for member in mod.archive.parse_pack(updates[parent])}
        self.assertEqual(values, {edited_name: b'new-edited', replaced_name: b'new-tex'})

    def test_table_copy_and_foreign_row_edit_conflict(self):
        state = mod.MergeState(self.data)
        state.claim_table_copy(6792, 'Copy mod')
        state.claim_table_edit(6792, 'Copy mod')
        with self.assertRaisesRegex(ValueError, 'Table edit conflict 6792'):
            state.claim_table_edit(6792, 'Edit mod')

    def test_disjoint_cells_of_one_row_merge(self):
        for folder, values in ((self.root / 'name', {'name': 'Shared Name'}),
                               (self.root / 'price', {'buy_price': 999})):
            folder.mkdir()
            spec = dict(format='fl-mod-source-v1', name=folder.name,
                        edits=[dict(resource=6792, row=0, set=values)])
            (folder / 'mod.json').write_text(json.dumps(spec))
        self.build([self.root / 'name', self.root / 'price'])
        row = self.data.rows(6792)[0]
        self.assertEqual((row['name'], row['buy_price']), ('Shared Name', 999))

    def test_same_row_incompatible_edits_conflict(self):
        for folder, name in ((self.root / 'one', 'One'), (self.root / 'two', 'Two')):
            folder.mkdir()
            spec = dict(format='fl-mod-source-v1', name=name,
                        edits=[dict(resource=6792, row=0, copy_from=0, set={'name': name})])
            (folder / 'mod.json').write_text(json.dumps(spec))
        with self.assertRaisesRegex(ValueError, 'Row conflict 6792:0.*name'):
            self.build([self.root / 'one', self.root / 'two'])
        self.assertFalse((self.root / 'overlay').exists())


if __name__ == '__main__':
    unittest.main()


class ExpansionBuilds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = FakeModData(self.root / 'extraction')
        count = 58095
        header = struct.pack('<II', count, 0) + bytes(13 * count)
        (self.data.root / '.fl_archive/original.bin').write_bytes(header)
        self.data.manifest.update(count=count, archive_size=len(header))
        self.schemas = {}
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'payload.bin').write_bytes(b'new standalone resource')

    def table(self, id_, rows):
        raw, doc = make_table([('category', 1, 1, 0, 0)], rows)
        doc['resource_id'] = id_
        self.data.add(id_, raw, doc)
        self.schemas[id_] = dict(name='synthetic', row_size=doc['sections'][0]['row_size'],
                                columns=doc['sections'][0]['columns'], resource_ids=[id_])

    def item_tables(self):
        categories = [dict(category=c) for c, size in enumerate(mod.CATEGORY_SIZES) for _ in range(size)]
        for base in mod.data_tools.ITEM_BASES:
            for slot in range(9):
                self.table(base + slot, categories)
        for base, count in zip(mod.data_tools.STAT_BASES, mod.CATEGORY_SIZES):
            for slot in range(9):
                self.table(base + slot, [dict(category=0)] * count)
        for id_, count in zip(mod.data_tools.RECIPE_TABLES, mod.RECIPE_COUNTS):
            self.table(id_, [dict(category=0)] * count)

    def build(self, spec, layout=True):
        (self.source / 'mod.json').write_text(json.dumps(dict(
            format='fl-mod-source-v1', name='Expansion', **spec)))
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(mod, 'ModData', return_value=self.data))
            stack.enter_context(patch.object(mod.scr, 'schemas', return_value=self.schemas))
            stack.enter_context(patch.object(mod.data_tools, 'validate', return_value={'errors': []}))
            stack.enter_context(patch.object(mod, 'validate_item_icons'))
            if not layout:
                stack.enter_context(patch.object(mod, 'validate_runtime_layout'))
            return mod.build(self.data.root, self.source, self.root / 'overlay')

    def test_append_item_and_recipe_overlay(self):
        self.item_tables()
        edits = [dict(resources=list(range(base, base + 9)), row='$weapon', copy_from=0)
                 for base in mod.data_tools.ITEM_BASES]
        edits += [dict(resources=list(range(6720, 6729)), row='$weapon.stat_row', copy_from=0),
                  dict(resource=8388, row='$recipe', copy_from=0)]
        manifest = self.build(dict(allocate=dict(weapon=dict(symbol='$weapon', append=True),
                                               alchemy_recipe=dict(symbol='$recipe', append=True)), edits=edits))
        self.assertEqual(len(manifest['resources']), 46)
        for entry in manifest['resources']:
            raw = mod.archive.decompress_nintendo((self.root / 'overlay' / entry['file']).read_bytes())[0]
            with patch.object(mod.scr, 'schemas', return_value=self.schemas):
                rows = mod.scr.dump(raw, entry['id'])['sections'][0]['rows']
            expected = 172 if entry['id'] == 8388 else 154 if 6720 <= entry['id'] < 6729 else 2736
            self.assertEqual(len(rows), expected)
            self.assertEqual(rows[:-1], self.data.original_rows(entry['id']))

    def test_append_standalone_archive_resource(self):
        manifest = self.build(dict(files={'58095': 'payload.bin'}), layout=False)
        self.assertEqual(manifest['archive_count'], 58095)
        self.assertEqual([r['id'] for r in manifest['resources']], [58095])
        entry = manifest['resources'][0]
        raw = mod.archive.decompress_nintendo((self.root / 'overlay' / entry['file']).read_bytes())[0]
        self.assertEqual(raw, b'new standalone resource')
        self.assertEqual(mod.check_stack([self.root / 'overlay'])['resources'], 1)

    def test_append_raw_copy(self):
        self.data.add(100, b'donor resource')
        manifest = self.build(dict(copies=[dict(resource=58095, base=100)]), layout=False)
        self.assertEqual(manifest['resources'][0]['id'], 58095)

    def test_reject_gap_and_protected_ids(self):
        for id_ in (58096, 65535, 1, -1):
            with self.subTest(id_=id_), self.assertRaises(ValueError):
                self.build(dict(files={str(id_): 'payload.bin'}), layout=False)
            self.assertFalse((self.root / 'overlay').exists())

    def test_check_stack_rejects_appended_gap(self):
        self.build(dict(files={'58095': 'payload.bin'}), layout=False)
        path = self.root / 'overlay/overlay.json'
        manifest = json.loads(path.read_text())
        manifest['resources'][0]['id'] = 58096
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            mod.check_stack([path.parent])

    def test_append_texture_and_model(self):
        import test_fl_zmdl
        self.data.add(100, mod.ztex.build([dict(name='tex_new', width=8, height=8,
            format='rgb565', mips=1, data=bytes(128))], flags=0, extra=b''))
        self.data.add(101, test_fl_zmdl.make_zmdl())
        mod.ztex.png_write(self.source / 'art.png', 8, 8, bytes([80, 120, 160, 255]) * 64)
        manifest = self.build(dict(
            textures=[dict(resource=58095, base=100, png='art.png')],
            models=[dict(resource=58096, base=101, texture_names={'tex_test': 'tex_new'})]), layout=False)
        self.assertEqual([r['id'] for r in manifest['resources']], [58095, 58096])
        for entry in manifest['resources']:
            raw = mod.archive.decompress_nintendo((self.root / 'overlay' / entry['file']).read_bytes())[0]
            if entry['id'] == 58095:
                self.assertEqual(mod.ztex.parse(raw)['images'][0]['name'], 'tex_new')
            else:
                self.assertEqual(mod.zmdl.parse(raw)['materials'][0]['texture'], 'tex_new')
