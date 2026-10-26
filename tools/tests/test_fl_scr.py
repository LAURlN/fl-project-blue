"""Synthetic fixtures only; run: python3 -I -m unittest discover -s tools/tests -v."""
import contextlib
import copy
import os
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

TOOLS = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('fl_scr', TOOLS / 'fl_scr.py')
fl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fl)

FURIGANA = bytes.fromhex('f4ffffff10000000030008007830443057300000')   # control record: tag, size, payload
# type, array, bits, offset, shift
COLUMNS = [(10, 1, 0, 0, 0),     # name: UTF-16 pointer
           (5, 1, 0, 4, 0),      # key: ASCII pointer
           (2, 1, 0, 8, 0),      # u16
           (1, 2, 0, 10, 0),     # u8[2]
           (3, 1, 4, 12, 0),     # u32 bits 0..3
           (3, 1, 1, 12, 4),     # u32 bit 4
           (3, 1, 27, 12, 5),    # u32 bits 5..31
           (7, 1, 0, 16, 0)]     # resource id
WIDTH = 20


def utf16(text):
    return text.encode('utf-16le') + b'\0\0'


def table(rows, columns=COLUMNS, width=WIDTH, trailer=b''):
    """rows: list of (name_bytes, key, u16, (a, b), low4, flag, big27, resource)."""
    ncol = len(columns)
    info = (32 + 6 * ncol + 4 + 3) & ~3          # zero terminator, descriptor 4-aligned (as in the game files)
    start = info + 12
    pool, pointers = bytearray(), []
    base = start + len(rows) * width
    for name, key, *_ in rows:
        pointers.append((base + len(pool), None))
        pool.extend(name)
        pool.extend(b'\0' * (-len(pool) % 4))
        pointers[-1] = (pointers[-1][0], base + len(pool))
        pool.extend(key.encode() + b'\0')
        pool.extend(b'\0' * (-len(pool) % 4))
    body = bytearray()
    for (name, key, u16, pair, low4, flag, big, resource), (p_name, p_key) in zip(rows, pointers):
        word12 = low4 | flag << 4 | big << 5
        body.extend(struct.pack('<IIHBBII', p_name, p_key, u16, pair[0], pair[1], word12, resource))
    out = bytearray(b'\x13\x80\x03\x1d' + bytes(4) + bytes([0, ncol, 9, 0]) + bytes(4) + struct.pack('<II', 32, info))
    out.extend(bytes(8))
    for type_, array, bits, offset, shift in columns:
        out.extend(struct.pack('<BBHH', type_, array, bits, offset << 5 | shift))
    out.extend(bytes(info - 32 - 6 * ncol))
    out.extend(struct.pack('<3I', len(rows), width, start))
    out.extend(body)
    out.extend(pool)
    out.extend(trailer)
    struct.pack_into('<I', out, 12, len(out) - 32)
    return bytes(out)


def sample(trailer=b''):
    return table([
        (utf16('Sword'), 'ID_A', 7, (1, 2), 5, 1, 400, 11),
        (utf16('Shield'), 'ID_B', 65535, (3, 4), 0, 0, 0, 12),
        ('Hi'.encode('utf-16le') + FURIGANA + utf16('ya'), 'ID_C', 1, (0, 0), 15, 1, (1 << 27) - 1, 13)],
        trailer=trailer)


def wrapper(first, second=b'\x01\x00\x00\x00opaque script bytes'):
    return struct.pack('<4I', 2, 16, 16 + len(first), 16 + len(first) + len(second)) + first + second


def doc(data):
    return fl.dump(data)


class Codec(unittest.TestCase):
    def test_round_trip_is_byte_identical(self):
        for raw in (sample(), sample(b'trailing footer bytes'), wrapper(sample()),
                    wrapper(sample(), b''), wrapper(b'\x05\x00\x00\x00unknown first section')):
            with self.subTest(size=len(raw)):
                self.assertEqual(fl.build(doc(raw)), raw)
                # JSON survives serialisation untouched.
                self.assertEqual(fl.build(json.loads(json.dumps(doc(raw)))), raw)

    def test_decoded_values_and_controls(self):
        rows = doc(sample())['sections'][0]['rows']
        self.assertEqual([r['c00'] for r in rows][:2], ['Sword', 'Shield'])
        self.assertEqual(rows[2]['c00'], ['Hi', {'control': FURIGANA.hex()}, 'ya'])
        self.assertEqual(rows[0]['c01'], 'ID_A')
        self.assertEqual((rows[2]['c04'], rows[2]['c05'], rows[2]['c06']), (15, 1, (1 << 27) - 1))
        self.assertEqual(rows[0]['c03'], [1, 2])
        self.assertEqual(rows[1]['c02'], 65535)

    def test_strings_can_grow_shrink_and_keep_other_pointers(self):
        raw = sample()
        d = doc(raw)
        rows = d['sections'][0]['rows']
        rows[0]['c00'] = 'A considerably longer sword name than before, with ünïcode ✓'
        rows[1]['c00'] = ''
        rows[2]['c01'] = 'ID_C_RENAMED_LONGER'
        out = fl.build(d)
        again = fl.dump(out)['sections'][0]['rows']
        self.assertEqual(again[0]['c00'], 'A considerably longer sword name than before, with ünïcode ✓')
        self.assertEqual(again[1]['c00'], '')
        self.assertEqual(again[2]['c01'], 'ID_C_RENAMED_LONGER')
        self.assertEqual(again[2]['c00'], ['Hi', {'control': FURIGANA.hex()}, 'ya'])   # untouched row intact
        self.assertEqual(out[12:16], struct.pack('<I', len(out) - 32))
        self.assertEqual(len(out) % 4, 0)
        self.assertEqual(fl.build(fl.dump(out)), out)
        # Unchanged cells keep their original pointer (no needless pool growth).
        self.assertEqual(out[fl.layout(out)['rows'] + WIDTH * 2:][:4], raw[fl.layout(raw)['rows'] + WIDTH * 2:][:4])

    def test_control_tokens_are_editable_and_validated(self):
        d = doc(sample())
        d['sections'][0]['rows'][0]['c00'] = ['New ', {'control': 'ffff'}, {'control': FURIGANA.hex()}, ' end']
        out = fl.build(d)
        self.assertEqual(fl.dump(out)['sections'][0]['rows'][0]['c00'],
                         ['New ', {'control': 'ffff'}, {'control': FURIGANA.hex()}, ' end'])
        for bad in ('a\0b', 'a￿b', [{'control': 'f4ffffff0900000000'}], [{'control': 'zz'}], [{'oops': 1}], 5):
            with self.subTest(bad=bad):
                d = doc(sample())
                d['sections'][0]['rows'][0]['c00'] = bad
                with self.assertRaises((ValueError, TypeError)):
                    fl.build(d)

    def test_append_rows_with_and_without_raw(self):
        d = doc(sample())
        rows = d['sections'][0]['rows']
        clone = copy.deepcopy(rows[0])
        clone['c00'] = 'Cloned'
        fresh = {k: v for k, v in clone.items() if k != '_raw'}
        fresh.update(c00='Fresh', c01='ID_F', c02=9, c03=[7, 8], c04=3, c05=0, c06=123456, c07=99)
        rows.extend([clone, fresh])
        out = fl.build(d)
        info = fl.layout(out)
        self.assertEqual(info['count'], 5)
        self.assertEqual(info['rows'] + 5 * WIDTH <= len(out), True)
        again = fl.dump(out)['sections'][0]['rows']
        self.assertEqual([r['c00'] for r in again[:3]], ['Sword', 'Shield', ['Hi', {'control': FURIGANA.hex()}, 'ya']])
        self.assertEqual(again[3]['c00'], 'Cloned')
        self.assertEqual((again[3]['c01'], again[3]['c06']), ('ID_A', 400))
        self.assertEqual((again[4]['c00'], again[4]['c01'], again[4]['c03'], again[4]['c06'], again[4]['c07']),
                         ('Fresh', 'ID_F', [7, 8], 123456, 99))
        self.assertEqual(fl.build(fl.dump(out)), out)

    def test_remove_rows_shrinks_in_place(self):
        d = doc(sample())
        del d['sections'][0]['rows'][1]
        out = fl.build(d)
        self.assertEqual(fl.layout(out)['count'], 2)
        self.assertEqual([r['c00'] for r in fl.dump(out)['sections'][0]['rows']][0], 'Sword')

    def test_bit_fields_do_not_clobber_neighbours_and_are_range_checked(self):
        d = doc(sample())
        row = d['sections'][0]['rows'][1]
        row['c04'], row['c05'], row['c06'] = 9, 1, 5
        out = fl.build(d)
        r = fl.dump(out)['sections'][0]['rows'][1]
        self.assertEqual((r['c04'], r['c05'], r['c06'], r['c02']), (9, 1, 5, 65535))
        for column, value in (('c04', 16), ('c05', 2), ('c06', 1 << 27), ('c02', 65536), ('c02', -1), ('c02', '7'), ('c03', [1])):
            with self.subTest(column=column, value=value):
                d = doc(sample())
                d['sections'][0]['rows'][0][column] = value
                with self.assertRaises(ValueError):
                    fl.build(d)

    def test_wrapper_offsets_follow_growing_first_section(self):
        raw = wrapper(sample())
        d = doc(raw)
        d['sections'][0]['rows'][0]['c00'] = 'x' * 99
        out = fl.build(d)
        magic, first, second, end = struct.unpack('<4I', out[:16])
        self.assertEqual((magic, first, end), (2, 16, len(out)))
        self.assertEqual(out[second:], raw[struct.unpack('<I', raw[8:12])[0]:])   # opaque section unchanged
        self.assertEqual(out[first:second][:4], fl.MAGIC)

    def test_rejects_malformed_input(self):
        raw = sample()
        for bad in (b'', b'XXXX' + raw[4:], raw[:-5], raw[:31],
                    raw[:12] + struct.pack('<I', 3) + raw[16:],
                    bytes.fromhex('0200000010000000') + b'\xff' * 8):
            with self.subTest(size=len(bad)):
                with self.assertRaises((ValueError, struct.error)):
                    fl.build(fl.dump(bad))
        d = doc(raw)
        d['format'] = 'other'
        with self.assertRaises(ValueError):
            fl.build(d)
        d = doc(raw)
        d['sections'][0]['rows'][0]['bogus'] = 1
        with self.assertRaises(ValueError):
            fl.build(d)
        d = doc(raw)
        d['sections'][0]['columns'][2]['offset'] = 9
        with self.assertRaises(ValueError):
            fl.build(d)

    def test_pointer_columns_are_preserved_opaquely(self):
        raw = table([(utf16('n'), 'k', 0, (0, 0), 0, 0, 0, 40)], columns=COLUMNS[:7] + [(9, 1, 0, 16, 0)])
        d = doc(raw)
        self.assertEqual(d['sections'][0]['rows'][0]['c07'], {'offset': 40})
        self.assertEqual(fl.build(d), raw)
        d['sections'][0]['rows'][0]['c07'] = {'offset': len(raw) + 100}
        with self.assertRaises(ValueError):
            fl.build(d)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(err):
            try:
                old, sys.argv = sys.argv, ['fl_scr.py', *map(str, args)]
                try:
                    fl.main()
                finally:
                    sys.argv = old
            except SystemExit as exc:
                return exc.code, out.getvalue(), err.getvalue()
        return 0, out.getvalue(), err.getvalue()

    def test_dump_edit_build_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = tmp / '00001_sample.scr'
            source.write_bytes(sample())
            code, *_ = self.run_cli('dump', source, tmp / 'out.json')
            self.assertEqual(code, 0)
            code, *_ = self.run_cli('build', tmp / 'out.json', tmp / 'rebuilt.scr')
            self.assertEqual(code, 0)
            self.assertEqual((tmp / 'rebuilt.scr').read_bytes(), source.read_bytes())
            document = json.loads((tmp / 'out.json').read_text())
            document['sections'][0]['rows'][0]['c00'] = 'Edited'
            (tmp / 'edited.json').write_text(json.dumps(document))
            self.assertEqual(self.run_cli('build', tmp / 'edited.json', tmp / 'edited.scr')[0], 0)
            self.assertEqual(fl.dump((tmp / 'edited.scr').read_bytes())['sections'][0]['rows'][0]['c00'], 'Edited')
            code, _, err = self.run_cli('dump', source, tmp / 'out.txt')
            self.assertNotEqual(code, 0)
            self.assertIn('.json or .csv', err)
            code, _, err = self.run_cli('build', tmp / 'out.json', tmp / 'out.json')
            self.assertNotEqual(code, 0)

    def test_csv_export_and_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / '00002_sample.scr'
            source.write_bytes(wrapper(sample()))
            self.assertEqual(self.run_cli('dump', source, Path(tmp) / 'out.csv')[0], 0)
            lines = (Path(tmp) / 'out.csv').read_text(encoding='utf-8').splitlines()
            self.assertEqual(lines[0], 'row,c00,c01,c02,c03,c04,c05,c06,c07')
            self.assertEqual(lines[1].split(',')[:3], ['0', 'Sword', 'ID_A'])
            self.assertEqual(len(lines), 4)
            code, out, _ = self.run_cli('info', source)
            self.assertEqual(code, 0)
            self.assertIn('section 0: table, 3 rows x 20 bytes', out)
            self.assertIn('section 1: opaque', out)
            self.assertIn('bits=27@5', out)


class Schemas(unittest.TestCase):
    def test_every_schema_is_internally_consistent(self):
        fl.schemas.cache_clear()
        by_id = fl.schemas()          # raises if two schemas claim one resource ID
        self.assertGreater(len(by_id), 100)
        for path in sorted((TOOLS / 'schemas').glob('*.json')):
            schema = json.loads(path.read_text(encoding='utf-8'))
            with self.subTest(schema=path.name):
                self.assertEqual(schema['name'], path.stem)
                names = [c['name'] for c in schema['columns']]
                self.assertEqual(len(set(names)), len(names))
                self.assertNotIn('_raw', names)
                for col in schema['columns']:
                    self.assertIn(col['confidence'], ('high', 'medium', 'uncertain'))
                    self.assertIn(col['type_id'], fl.TYPES)
                    self.assertEqual(fl.TYPES[col['type_id']][0], col['type'])
                    size = fl.TYPES[col['type_id']][1] * col['count']
                    self.assertLessEqual(col['offset'] + size, schema['row_size'])
                self.assertEqual(sorted(schema['resource_ids']), schema['resource_ids'])

    def test_schema_names_apply_and_layout_mismatch_is_rejected(self):
        raw = sample()
        schema = {'name': 'test', 'row_size': WIDTH, 'resource_ids': [1],
                  'columns': [dict(name=f'col{i}', type=fl.TYPES[t][0], type_id=t, offset=o, count=a,
                                   bits=b, shift=s, confidence='high', note='')
                              for i, (t, a, b, o, s) in enumerate(COLUMNS)]}
        columns = fl.decode_section(raw, schema)['columns']
        self.assertEqual([c['name'] for c in columns][:2], ['col0', 'col1'])
        broken = copy.deepcopy(schema)
        broken['columns'][2]['offset'] = 6
        with self.assertRaises(ValueError):
            fl.decode_section(raw, broken)
        broken = copy.deepcopy(schema)
        broken['row_size'] = 24
        with self.assertRaises(ValueError):
            fl.decode_section(raw, broken)

    def test_schemas_match_real_tables_when_an_extraction_exists(self):
        root = Path(os.environ.get('FL_EU_ARCHIVE', TOOLS.parent / 'extracted/fl_eu/archive'))
        manifest = root / '.fl_archive/manifest.json'
        if not manifest.exists():
            self.skipTest('no extracted game data')
        entries = {e['id']: e for e in json.loads(manifest.read_text())['entries']}
        for id_, schema in fl.schemas().items():
            if id_ != schema['resource_ids'][0]:
                continue
            with self.subTest(schema=schema['name']):
                data = (root / entries[id_]['path']).read_bytes()
                section = fl.dump(data, id_)['sections'][0]
                self.assertEqual([c['name'] for c in section['columns']], [c['name'] for c in schema['columns']])
                self.assertEqual(fl.build(fl.dump(data, id_)), data)


if __name__ == '__main__':
    unittest.main()
