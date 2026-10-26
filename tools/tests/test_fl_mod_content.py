"""Synthetic placement/stack tests; no game process or copyrighted fixtures."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_fl_map import fixture, fm
from test_fl_mod import mod
from test_fl_script import vm


class Placements(unittest.TestCase):
    def test_appended_payload_edit_does_not_change_donor(self):
        original = fixture()
        before = fm.dump(original)
        operation = dict(row='append', copy_from=0, expect={'reference': 5},
                         set={'uid': 0x04000ffe, 'reference': 218},
                         warp={'arrival_position': [9, 0, 8]})
        with self.assertRaisesRegex(ValueError, 'experimental-growth'):
            fm.apply_edits(original, [operation])
        result = fm.apply_edits(original, [operation], experimental_growth=True)
        after = fm.dump(result)
        self.assertEqual(after['rows'][:2], before['rows'])
        self.assertNotEqual(after['rows'][0]['payload_offset'], after['rows'][2]['payload_offset'])
        self.assertEqual(after['rows'][2]['warp']['arrival_position'], [9, 0, 8])
        self.assertEqual(fm.build(after), result)

    def test_guards_duplicates_protected_fields_and_bad_payload(self):
        for operation in [dict(row=0, expect={'reference': 99}),
                          dict(row=0, set={'payload_offset': 0}),
                          dict(row=0, warp={'typo': 0}),
                          dict(row='append', copy_from=0)]:
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                fm.apply_edits(fixture(), [operation], experimental_growth=True)

    def test_room_remap_and_empty_group(self):
        doc = fm.dump(fixture())
        # Keep a valid synthetic spawn group in map 8 while remapping the exit.
        groups = copy.deepcopy(doc['map_groups'])
        groups[0]['map_id'] = 154
        result = fm.apply_edits(fixture(), [dict(row=0, set={'map_id': 154})],
                                map_groups=groups, experimental_growth=True)
        after = fm.dump(result)
        self.assertEqual(after['rows'][0]['map_id'], 154)
        self.assertEqual(after['map_groups'][0], dict(map_id=154, groups=[]))


class StackPlacements(unittest.TestCase):
    def test_appends_merge_and_map_group_rows_are_unioned(self):
        original = fixture()
        base_groups = fm.dump(original)['map_groups']

        class Data:
            entries = {10: {}}

            def rows(self, id_):
                return {8695: [dict(map_id=8, spawn_table_resource=200)],
                        200: [dict(monsters=[1] + [0xffff] * 7)]}[id_]

        data = Data()
        state = mod.MergeState(data)

        def operation(uid):
            return dict(row='append', copy_from=1, set={'uid': uid})

        def groups(extra):
            result = copy.deepcopy(base_groups)
            result[1]['groups'][0]['rows'] = [1, extra]
            return result

        first = dict(format='fl-mod-source-v1', name='A', placements=[
            dict(resource=10, edits=[operation(0x04000ffe)], experimental_growth=True,
                 map_groups=groups(2))])
        second = dict(format='fl-mod-source-v1', name='B', placements=[
            dict(resource=10, edits=[operation(0x04080ffe)], experimental_growth=True,
                 map_groups=groups(3))])
        mod.content.apply_merged(data, Path('.'), first, state, 'A', lambda _, id_: original)
        mod.content.apply_merged(data, Path('.'), second, state, 'B', lambda _, id_: original)
        document = fm.dump(state.updates[10])
        self.assertEqual([row['uid'] for row in document['rows']],
                         [row['uid'] for row in fm.dump(original)['rows']] + [0x04000ffe, 0x04080ffe])
        self.assertEqual(document['map_groups'][1]['groups'][0]['rows'], [1, 2, 3])


class Content(unittest.TestCase):
    def test_resource_copies_scripts_and_conflict_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'test.fls').write_text(mod.content.scripts.disassemble(vm()))
            data = type('Data', (), {'entries': {10: {}, 11: {}, 12: {}}})()
            raw = {10: b'old target', 11: b'donor', 12: b'old script'}
            updates = {}
            source = dict(copies=[dict(resource=10, base=11)],
                          scripts=[dict(resource=12, assembly='test.fls')])
            mod.content.apply(data, root, source, updates, lambda _, id_: raw[id_])
            self.assertEqual(updates, {10: b'donor', 12: vm()})
            with self.assertRaisesRegex(ValueError, 'conflicting'):
                mod.content.apply(data, root, source, updates, lambda _, id_: raw[id_])
            data.entries[5965] = {}
            with self.assertRaisesRegex(ValueError, 'schema-backed'):
                mod.content.apply(data, root, dict(copies=[dict(resource=5965, base=11)]), {},
                                  lambda _, id_: raw[id_])

    def test_paired_route_and_layer_validation(self):
        layers = {}
        for resource, map_id, uid in ((10, 7, 0x04000ffe), (11, 8, 0x04040ffe)):
            doc = fm.dump(fixture())
            doc['rows'][0].update(map_id=map_id, uid=uid)
            layers[resource] = fm.build(doc)
        associations = [{'c01': 1, 'c02': map_id, 'c00': [0]*4+[resource, 0, 0, 0]}
                        for resource, map_id in ((10, 7), (11, 8))]
        tables = {5965: [dict(map_pair=[7, 8])]*6, 8697: associations}
        data = type('Data', (), {'rows': lambda _, id_: tables[id_]})()
        spec = dict(transitions=[dict(route=5, endpoints=[dict(resource=10, uid=0x04000ffe),
                                                          dict(resource=11, uid=0x04040ffe)])])
        mod.content.apply(data, None, spec, layers, None)
        tables[5965][5] = dict(map_pair=[7, 9])
        with self.assertRaisesRegex(ValueError, 'paired endpoints'):
            mod.content.apply(data, None, spec, layers, None)
        tables[5965][5] = dict(map_pair=[7, 8])
        associations.pop()
        with self.assertRaisesRegex(ValueError, 'not associated'):
            mod.content.apply(data, None, spec, layers, None)

    def test_spawn_region_validation(self):
        doc = fm.dump(fixture())
        groups = [{'monsters': [274, 11] + [0xffff] * 6}]
        tables = {8695: [dict(map_id=8, spawn_table_resource=7290)], 7290: groups}
        data = type('Data', (), {'rows': lambda _, id_: tables[id_]})()
        mod.content.validate_spawns(data, doc, 23053)
        for change, message in ((lambda d: d['rows'][1].update(reference=1), 'out of range'),
                                (lambda d: d['rows'][1]['spawn']['points'][1].update(variant=2), 'forced member'),
                                (lambda d: d['rows'][1]['spawn'].update(count_max=3), 'counts'),
                                (lambda d: d['map_groups'][1]['groups'][0]['rows'].clear(), 'no map group'),
                                (lambda d: d['rows'][1].update(map_id=9), 'no spawn table')):
            broken = copy.deepcopy(doc)
            change(broken)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                mod.content.validate_spawns(data, broken, 23053)


class Stacks(unittest.TestCase):
    def test_order_conflicts_base_mismatch_and_virtual_pack_conflicts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            folders = [root / 'b', root / 'a']
            manifests = []
            for path, id_ in zip(folders, (4, 2)):
                path.mkdir()
                manifests.append(dict(format='fl-resource-overlay-v1', name=path.name,
                                      program_id='test', archive_count=10, archive_size=123,
                                      header_fnv32='12345678', resources=[dict(id=id_)], virtual_sizes={}))
            def write():
                for path, manifest in zip(folders, manifests):
                    (path / 'overlay.json').write_text(json.dumps(manifest))
            write()
            self.assertEqual(mod.check_stack(folders), dict(names=['a', 'b'], resources=2))
            with self.assertRaisesRegex(ValueError, 'Duplicate overlay'):
                mod.check_stack(folders*2)
            manifests[0]['resources'][0]['id'] = 2
            write()
            with self.assertRaisesRegex(ValueError, 'Resource conflict 2:.*a.*b'):
                mod.check_stack(folders)
            manifests[0]['resources'][0]['id'] = 4
            manifests[0]['header_fnv32'] = 'different'
            write()
            with self.assertRaisesRegex(ValueError, 'base mismatch'):
                mod.check_stack(folders)
            manifests[0]['header_fnv32'] = '12345678'
            for m in manifests:
                m['virtual_sizes'] = {'7': 123}
            write()
            with self.assertRaisesRegex(ValueError, 'Virtual resource conflict 7'):
                mod.check_stack(folders)


if __name__ == '__main__':
    unittest.main()
