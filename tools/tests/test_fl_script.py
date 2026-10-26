"""Invented bytecode/containers only; optional real corpus is checked by the CLI."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fl_script as fs
from test_fl_map import fixture as placement_fixture


def wrapper(first, second):
    return fs.WRAPPER + struct.pack('<II', 16+len(first), 16+len(first)+len(second)) + first + second


def vm(label_width=4, code_width=5):
    # Two entries, absent and PC zero; two global functions at PCs zero and six.
    sentinel = (1 << (label_width*8))-1
    meta = b''.join(x.to_bytes(label_width, 'little') for x in (2, sentinel, 0))
    meta += struct.pack('<3H', 2, 0, 6) + b'debug\x00\xff\x00'
    instructions = [(1, 11), (7, 66 << 8), (16, 6 << 8 | 3),
                    (10, 6 << 8 | 2), (15, 6 << 8), (17, 22), (12, 0)]
    code = b''.join(struct.pack('<BI' if code_width == 5 else '<HI', *i) for i in instructions)
    return wrapper(meta, code+b'\0\0')


class ScriptTests(unittest.TestCase):
    def test_all_encodings_round_trip(self):
        for lw, cw in ((4, 5), (2, 6), (2, 5)):
            with self.subTest(label_width=lw, code_width=cw):
                data = vm(lw, cw)
                self.assertEqual(fs.assemble(fs.disassemble(data)), data)

    def test_branch_entry_and_global_relocation(self):
        text = fs.disassemble(vm())
        # Insert before a target label: branches, entry, and globals must all move.
        text = text.replace('L00000:\n', '  push 0x42\nL00000:\n')
        first, code = fs.sections(fs.assemble(text))
        layout = fs.vm_layout(first, code)
        self.assertEqual(layout['labels'][1], 1)
        self.assertEqual(layout['globals'], [1, 7])
        self.assertEqual(layout['ops'][3], (16, 7 << 8 | 3))
        self.assertEqual(layout['ops'][4], (10, 7 << 8 | 2))

    def test_edit_native_and_operand(self):
        text = fs.disassemble(vm()).replace('push 0x0000000b', 'push 0x0000000c')
        text = text.replace('native flag_test', 'native 66')
        first, code = fs.sections(fs.assemble(text))
        self.assertEqual(fs.vm_layout(first, code)['ops'][:2], [(1, 12), (7, 66 << 8)])

    def test_catalog_integrity(self):
        commands = fs.commands()
        self.assertEqual([x['id'] for x in commands], list(range(700)))
        self.assertEqual(len({x['name'] for x in commands}), 700)
        for command in commands:
            self.assertEqual(len(command['operands']), command['argc'])
            self.assertIn(command['confidence'], ('unknown', 'medium', 'high'))
            self.assertEqual(int(command['handler'], 16) % 4, 0)

    def test_resolved_flag_and_local_message(self):
        resolver = fs.Resolver()
        resolver.cache[5417] = [{'_raw': '', 'label': 'SYNTHETIC_FLAG'}]
        resolver.cache[8697] = [{'c00': [42, 100]+[0xffffffff]*6, 'c01': 1}]
        resolver.cache[109] = [{'_raw': '', 'c00': 'Synthetic dialogue'}]
        ops = [(1, 0), (7, 66 << 8), (1, 0), (7, 90 << 8)]
        notes = fs.call_comments(ops, fs.commands(), resolver, 42)
        self.assertIn('SYNTHETIC_FLAG', notes[1])
        self.assertIn('Synthetic dialogue', notes[3])
        resolver.cache[8697].append({'c00': [77, 100]+[0xffffffff]*6, 'c01': 0})
        self.assertEqual(resolver.local_text(77, 0), '')
        self.assertEqual(resolver.local_text(77, 0, global_=True), 'Synthetic dialogue')
        # The NPC parameter of command 95 must never be treated as a resource ID.
        resolver.cache[123] = [{'_raw': '', 'c00': 'WRONG RESOURCE'}]
        notes = fs.call_comments([(1, 123), (1, 0), (1, 0), (1, 0), (7, 95 << 8)],
                                 fs.commands(), resolver, 42)
        self.assertNotIn('WRONG RESOURCE', notes[4])

    def test_dynamic_arguments_are_not_falsely_resolved(self):
        self.assertEqual(fs.call_comments([(0, 11), (7, 66 << 8)], fs.commands(), fs.Resolver()), {})

    def test_raw_message_attributes_round_trip(self):
        # MSG is preserved, with the table bytes exposed as editable hex.
        data = wrapper(b'MSG '+b'\xff\0'*5, struct.pack('<I', 2)+bytes(range(120)))
        text = fs.disassemble(data)
        self.assertEqual(text.count('.attribute '), 2)
        self.assertEqual(fs.assemble(text), data)

    def test_field_round_trip_and_correct_record_annotation(self):
        data = placement_fixture()
        text = fs.disassemble(data)
        self.assertIn('map=7 type=3 flags=0x0 subtype=-1 uid=0x4000000 reference=5', text)
        self.assertEqual(fs.assemble(text), data)

    def test_reject_invalid_bytecode(self):
        data = vm()
        first, code = fs.sections(data)
        for bad_first, bad_code in [(first, bytes([18])+code[1:]),
                                    (first, code[:-1]+b'\xff'),
                                    (first, code[:-9]), (b'\xff'*4, code)]:
            with self.subTest(first=bad_first[:4], code=bad_code[:4]), self.assertRaises(ValueError):
                fs.disassemble(wrapper(bad_first, bad_code))
        # Out-of-range global entry.
        bad = bytearray(first)
        struct.pack_into('<H', bad, 14, 65535)
        with self.assertRaisesRegex(ValueError, 'Global function target'):
            fs.disassemble(wrapper(bad, code))

    def test_reject_malformed_assembly(self):
        source = fs.disassemble(vm())
        for old, new in [('L00006 0x3', 'MISSING 0x3'),
                         ('native flag_test 0x0', 'native flag_test 256'),
                         ('push 0x0000000b', 'push 0x100000000'),
                         ('.padding 0000', '.padding 0100'),
                         ('.global L00006', '.global MISSING'),
                         ('.labels 4', '.labels 3'),
                         ('.code 5', '.code 7')]:
            self.assertIn(old, source)
            with self.subTest(new=new), self.assertRaises(ValueError):
                fs.assemble(source.replace(old, new))

    def test_container_bounds_and_unknown_magic(self):
        for data in (b'', b'nope', fs.WRAPPER+b'\0'*8, fs.FIELD_MAGIC+b'\0'*208):
            with self.subTest(data=data[:8]), self.assertRaises(ValueError):
                fs.disassemble(data)

    def test_manifest_corpus_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'.fl_archive').mkdir()
            entries = []
            for i, data in enumerate((vm(), placement_fixture(), b'unrelated')):
                (root/str(i)).write_bytes(data)
                entries.append({'id': i, 'path': str(i)})
            (root/'.fl_archive/manifest.json').write_text(json.dumps({'entries': entries}))
            self.assertEqual([i for i, _ in fs.corpus(root)], [0, 1])
            refs = list(fs.flag_references(root, 11))
            self.assertEqual([(x['resource_id'], x['instruction'], x['command']) for x in refs],
                             [(0, 1, 66)])
            self.assertEqual(list(fs.flag_references(root, 12)), [])


if __name__ == '__main__':
    unittest.main()
