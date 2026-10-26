"""Synthetic fixtures only; run: python3 -I -m unittest discover -s tools/tests -v."""
import contextlib
import importlib.util
import io
from pathlib import Path
import random
import struct
import tempfile
import unittest
import zlib

spec = importlib.util.spec_from_file_location('fl_archive', Path(__file__).parents[1] / 'fl_archive.py')
fl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fl)


def pack_member(name='data/test.scr', value=b'original member', alignment=4):
    out = bytearray(fl.PACK_MAGIC + struct.pack('<4I', 0, 0, 1 << 16, 0))
    out.extend(b'\0' * (fl.align(len(out), alignment) - len(out)))
    offset = len(out)
    out.extend(value)
    namepos = len(out)
    out.extend(name.encode() + b'\0')
    out.extend(b'\0' * (fl.align(len(out), 4) - len(out)))
    table = len(out)
    out.extend(struct.pack('<4B4I', 0, len(name), name.rfind('/') + 1,
                           name.rfind('.') + 1, alignment, len(value), namepos, offset))
    struct.pack_into('<I', out, 4, len(out) - 20)
    struct.pack_into('<I', out, 16, table)
    return bytes(out)


def fixture(member=b'original member'):
    index = bytearray(fl.INDEX_MAGIC + struct.pack('<IHHIII', 0, 5, 1, 0, 40, 28))
    index.extend(struct.pack('<HHIHHI', 3, 0, 2, 1, 4, 24))
    for group, role in [(65535, 0), (65535, 0), (0, 1), (0, 2), (65535, 0)]:
        index.extend(struct.pack('<HH', group, role))
    struct.pack_into('<I', index, 4, len(index) - 24)
    raw = [b'ztex' + b'A' * 300, bytes(index), pack_member(value=member), member, b'last resource']
    out = bytearray(struct.pack('<II', 5, 0) + b'\0' * 65)
    records = []
    for i, value in enumerate(raw):
        offset = fl.align(len(out))
        stored = value if i == 1 else fl.compress_lz11(value)
        records.append((offset, len(value), len(stored), int(i != 1)))
        if i != 3:
            # Deliberately nonzero padding must survive an unchanged round trip.
            out.extend(b'\xa5' * (offset - len(out)))
            out.extend(stored)
    out.extend(b'\xcd' * (fl.align(len(out)) - len(out)))
    for i, record in enumerate(records):
        for k in range(3):
            struct.pack_into('<I', out, 8 + k * 20 + i * 4, record[k])
        out[68 + i] = record[3]
    return bytes(out)


class Codecs(unittest.TestCase):
    def test_lz11_all_length_forms_and_overlap(self):
        # Independently hand-encoded short, medium and long references.
        for size, token in [(4, b'\x20\0'), (18, b'\0\0\0'), (274, b'\x10\0\0\0')]:
            stream = struct.pack('<I', size << 8 | 0x11) + b'\x40A' + token
            self.assertEqual(fl.decompress_nintendo(stream)[0], b'A' * size)

    def test_lz10_and_rle(self):
        self.assertEqual(fl.decompress_nintendo(b'\x10\x06\0\0\x10ABC\0\x02')[0], b'ABCABC')
        self.assertEqual(fl.decompress_nintendo(b'\x30\x07\0\0\x81A\x02BCD')[0], b'AAAABCD')

    def test_huffman_word_endianness_and_nibbles(self):
        tree = b'\x01\xc0AB'
        stream = b'\x28\x04\0\0' + tree + struct.pack('<I', 0x60000000)
        self.assertEqual(fl.decompress_nintendo(stream)[0], b'ABBA')
        stream = b'\x24\x02\0\0\x01\xc0\x01\x02' + struct.pack('<I', 0x60000000)
        self.assertEqual(fl.decompress_nintendo(stream)[0], b'\x21\x12')

    def test_encoder_roundtrip(self):
        rng = random.Random(413)
        for data in [b'', b'a', b'xyz' * 50000, bytes(range(256)) * 20,
                     bytes(rng.randrange(256) for _ in range(10000))]:
            self.assertEqual(fl.decompress_nintendo(fl.compress_lz11(data))[0], data)

    def test_level5_envelopes(self):
        self.assertEqual(fl.decompress_level5(struct.pack('<I', 24) + b'abc'), b'abc')
        self.assertEqual(fl.decompress_level5(struct.pack('<I', 3 << 3 | 5) + zlib.compress(b'abc')), b'abc')
        stream = b'\x10\x06\0\0\x10ABC\0\x02'
        self.assertEqual(fl.decompress_level5(struct.pack('<I', 6 << 3 | 1) + stream[4:]), b'ABCABC')

    def test_malformed_rejected(self):
        for stream in [b'\x11\x04\0\0\x80\x20\0', b'\x10\x04\0\0\0A',
                       b'\x30\x01\0\0\x80A', b'\x28\x01\0\0\xff']:
            with self.assertRaises(ValueError):
                fl.decompress_nintendo(stream)


class OtherContainers(unittest.TestCase):
    def test_level5_archives_crc_names_and_offsets(self):
        names = b'folder/\0a.bin\0'
        names = struct.pack('<I', len(names) << 3) + names
        names += b'\0' * (fl.align(len(names), 4) - len(names))
        crc = zlib.crc32(b'a.bin')
        for magic in (b'ARC0', b'XFSA', b'XPCK'):
            if magic == b'XPCK':
                base = 32 + len(names)
                header = struct.pack('<4s6HI', magic, 1, 5, 8, base // 4, 3, len(names) // 4, 1)
                data = header + struct.pack('<III', crc, 0, 3) + names + b'abc'
            else:
                table = (struct.pack('<4I', crc, 0, 0, 3) if magic == b'ARC0'
                         else struct.pack('<3I', crc, 0, 3))
                table = struct.pack('<I', len(table) << 3) + table
                namespos = 24 + len(table)
                base = namespos + len(names)
                data = magic + struct.pack('<5I', 24, 24, 24, namespos, base) + table + names + b'abc'
            r = fl.parse_level5_archive(data)[0]
            self.assertEqual(r['name'], 'folder/a.bin')
            self.assertEqual(fl.span(data, r['offset'], r['size']), b'abc')

    def test_lz_sidecar_edit_rebuilds_member(self):
        value = fl.compress_lz11(b'original')
        pack = pack_member(name='data/test.lz', value=value)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = fl.unpack_nested(root, pack, '')
            r = nested['members'][0]
            (root / r['decoded_path']).write_bytes(b'edited decoded content')
            rebuilt = fl.rebuild_nested(root, pack, nested)
            r = fl.parse_pack(rebuilt)[0]
            self.assertEqual(fl.decompress_nintendo(fl.span(rebuilt, r['offset'], r['size']))[0],
                             b'edited decoded content')


class Archive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input.bin'
        self.source.write_bytes(fixture())
        self.tree = self.root / 'tree'
        with contextlib.redirect_stdout(io.StringIO()):
            self.manifest = fl.extract(self.source, self.tree)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        target = self.root / 'rebuilt.bin'
        with contextlib.redirect_stdout(io.StringIO()):
            fl.build(self.tree, target)
        return target.read_bytes()

    def test_exact_roundtrip_with_opaque_padding(self):
        self.assertEqual(self.build(), self.source.read_bytes())
        self.assertEqual((self.tree / 'data/test.scr').read_bytes(), b'original member')
        self.assertEqual(self.manifest['entries'][3]['parent'], 2)

    def test_resize_virtual_member_and_standalone(self):
        member = b'Changed table row\0' * 100
        (self.tree / 'data/test.scr').write_bytes(member)
        standalone = self.tree / self.manifest['entries'][0]['path']
        standalone.write_bytes(b'ztexCHANGED')
        data = self.build()
        m = fl.parse_archive(data)
        self.assertEqual(m['entries'][3]['size'], len(member))
        raw = fl.decode_entry(data, m['entries'][2])
        entry = fl.parse_pack(raw)[0]
        self.assertEqual(fl.span(raw, entry['offset'], entry['size']), member)
        self.assertEqual(fl.decode_entry(data, m['entries'][0]), b'ztexCHANGED')
        self.assertEqual(fl.decode_entry(data, m['entries'][4]), b'last resource')
        self.assertEqual(m['entries'][3]['offset'], m['entries'][4]['offset'])
        # A second extraction proves the output can be read by a fresh tool state.
        with contextlib.redirect_stdout(io.StringIO()):
            target = self.root / 'edited.bin'
            target.write_bytes(data)
            fl.extract(target, self.root / 'edited')
        self.assertEqual((self.root / 'edited/data/test.scr').read_bytes(), member)

    def test_deep_bpak_resize(self):
        bpak = b'BPAK' + struct.pack('<III', 1, 16, 3) + b'ABC'
        source = self.root / 'deep.bin'
        source.write_bytes(fixture(bpak))
        tree = self.root / 'deep'
        with contextlib.redirect_stdout(io.StringIO()):
            m = fl.extract(source, tree)
        r = m['entries'][2]['nested']['members'][0]['nested']['members'][0]
        (tree / r['path']).write_bytes(b'NEW MEMBER SIZE')
        output = self.root / 'deep-repacked.bin'
        with contextlib.redirect_stdout(io.StringIO()):
            fl.build(tree, output)
        data = output.read_bytes()
        m = fl.parse_archive(data)
        pack = fl.decode_entry(data, m['entries'][2])
        member = fl.parse_pack(pack)[0]
        bpak = fl.span(pack, member['offset'], member['size'])
        inner = fl.parse_bpak(bpak)[0]
        self.assertEqual(fl.span(bpak, inner['offset'], inner['size']), b'NEW MEMBER SIZE')

    def test_conflicting_parent_edit(self):
        pack = self.tree / self.manifest['entries'][2]['path']
        pack.write_bytes(b'conflicting pack')
        (self.tree / 'data/test.scr').write_bytes(b'other edit')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.build()

    def test_paths_and_bounds(self):
        for name in ['../escape', '/absolute', 'a/../../escape', 'a\\b', 'a//b', 'C:/a']:
            with self.assertRaises(ValueError):
                fl.safe_path(self.root, name)
        try:
            (self.root / 'link').symlink_to(self.tree, target_is_directory=True)
        except OSError:
            # Windows without SeCreateSymbolicLinkPrivilege raises WinError 1314
            # here; skip only the symlink sub-assertion, not the whole test.
            pass
        else:
            with self.assertRaises(ValueError):
                fl.safe_path(self.root, 'link/file')
        with self.assertRaises(ValueError):
            fl.parse_pack(pack_member('../evil.scr'))
        bad = bytearray(self.source.read_bytes())
        struct.pack_into('<I', bad, 8, len(bad) + 32)
        with self.assertRaises(ValueError):
            fl.parse_archive(bad)

    def test_nonempty_output_refused(self):
        with self.assertRaisesRegex(ValueError, 'empty'):
            fl.extract(self.source, self.tree)


if __name__ == '__main__':
    unittest.main()
