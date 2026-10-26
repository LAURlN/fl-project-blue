"""Co-op freedom site table: synthetic pattern/masking checks, plus the private EU v00 corpus.

No game or guest code runs. The corpus checks need FL_EU_ARCHIVE (extracted/fl_eu/archive in the
main checkout); the stacked-overlay check also uses tools/build/merged-mods next to it, and the
generated C++ table is compared with the port source when FL_PORT_SRC points at a port checkout.
"""
import hashlib
import os
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fl_coop_gates as cg
import fl_script as fs


def wrapper(first, second):
    return fs.WRAPPER + struct.pack('<II', 16 + len(first), 16 + len(first) + len(second)) + first + second


def script(ops):
    meta = b''.join(x.to_bytes(4, 'little') for x in (1, 0)) + struct.pack('<H', 0)
    code = b''.join(struct.pack('<BI', op, val) for op, val in ops)
    return wrapper(meta, code + b'\0' * ((-len(code)) % 4))


NE = fs.ALU_NAMES.index('ne')


def gate_ops(flag):
    """flag_test(flag) ...; native 453; push 0; alu ne; jump_zero solo; refusal; solo: ..."""
    return [(1, flag), (7, 66 << 8), (17, NE), (16, 20 << 8),
            (1, 7), (7, 90 << 8), (7, cg.MP_ROLE << 8), (1, 0), (17, NE), (16, 14 << 8),
            (1, 59), (7, 91 << 8), (8, 9 << 8), (12, 0), (7, 101 << 8), (1, 3), (7, 90 << 8),
            (8, 9 << 8), (12, 0), (12, 0), (12, 0)]


def parse(data):
    return cg.vm(data)


class SyntheticTests(unittest.TestCase):
    def test_window_masks_only_branch_operands(self):
        layout, code = parse(script(gate_ops(16)))
        before, raw, mask = cg.window(layout, code, 6)
        self.assertEqual(before, 6)
        self.assertEqual(len(raw), len(mask))
        for i, (op, _) in enumerate(layout['ops'][0:6 + cg.AFTER]):
            want = b'\xff' + (b'\0' * 4 if op in cg.BRANCHES else b'\xff' * 4)
            self.assertEqual(mask[i * 5:i * 5 + 5], want, i)
        self.assertTrue(cg.is_refusal(layout['ops'], 6))
        self.assertFalse(cg.is_refusal(layout['ops'], 5))

    def test_match_survives_relocation_but_not_other_code(self):
        layout, code = parse(script(gate_ops(16)))
        pattern = cg.window(layout, code, 6)
        # a mod inserts two instructions at the top: every branch target moves by 2
        moved = [(1, 0x42), (17, fs.ALU_NAMES.index('drop'))] + [
            (op, ((val >> 8) + 2) << 8 | (val & 0xff)) if op in cg.BRANCHES else (op, val)
            for op, val in gate_ops(16)]
        layout2, code2 = parse(script(moved))
        self.assertTrue(cg.matches(pattern, code2, layout2['ops'], 8))
        self.assertFalse(cg.matches(pattern, code2, layout2['ops'], 6))
        # a different flag before the call is a different site
        layout3, code3 = parse(script(gate_ops(17)))
        self.assertFalse(cg.matches(pattern, code3, layout3['ops'], 6))
        # a different refusal row after the call too
        other = gate_ops(16)
        other[10] = (1, 60)
        layout4, code4 = parse(script(other))
        self.assertFalse(cg.matches(pattern, code4, layout4['ops'], 6))

    def test_scan_and_cxx(self):
        data = script(gate_ops(16))
        layout, code = parse(data)
        pats = [('report', 1, 6, 'why', cg.window(layout, code, 6))]
        self.assertEqual(cg.scan(pats, [(1, data), (2, script(gate_ops(17)))]), [(0, 1, 6)])
        text = cg.cxx(pats)
        self.assertIn('{Gate::Report, 1, 6, 6, "', text)
        self.assertIn('// why', text)

    def test_window_rejects_wrong_site(self):
        layout, code = parse(script(gate_ops(16)))
        with self.assertRaises(ValueError):
            cg.window(layout, code, 5)

    def test_gate_table_contract(self):
        # The order is the runtime enum (coop.h: ChangeLife, Report, Makeover).
        self.assertEqual([g[0] for g in cg.GATES], ['change_life', 'report', 'makeover'])
        self.assertEqual([g[1] for g in cg.GATES], ['fl_coop_change_life', 'fl_coop_report', 'fl_coop_makeover'])
        sites = [(rid, pc) for _, _, _, s in cg.GATES for rid, pc, _ in s]
        self.assertEqual(len(sites), 22)
        self.assertEqual(len(set(sites)), 22)
        self.assertEqual(dict((g[0], g[2]) for g in cg.GATES)['report'], (1, 2))  # host only
        self.assertEqual(cg.camel('change_life'), 'ChangeLife')


ARCHIVE = os.environ.get('FL_EU_ARCHIVE')


@unittest.skipUnless(ARCHIVE, 'Set FL_EU_ARCHIVE for private corpus checks')
class PrivateCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        merged = Path(ARCHIVE).resolve().parents[2] / 'tools' / 'build' / 'merged-mods'
        cls.overlays = sorted(p for p in merged.iterdir() if (p / 'overlay.json').exists()) if merged.is_dir() else []
        cls.report = cg.check(ARCHIVE, cls.overlays)

    def test_every_pattern_is_exact_in_the_shipped_corpus(self):
        self.assertEqual(self.report['sites'], 22)

    def test_sites_survive_stacked_overlays(self):
        # story-skip ("Free Life") replaces 21172 and 27679; every gate site in them must still
        # match exactly once, wherever its PC moved to. Other overlays do not touch gated scripts.
        for name, status in self.report['overlays'].items():
            for site, pc in status.items():
                self.assertIsNotNone(pc, f'{name}: {site} no longer matches')

    def test_generated_table_is_pinned(self):
        text = cg.cxx(cg.patterns(ARCHIVE))
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), cg.GENERATED_SHA256)
        port = os.environ.get('FL_PORT_SRC')
        if port:
            inc = Path(port) / 'runtime/src/games/fantasylife/coop_sites.inc'
            self.assertEqual(inc.read_text(encoding='utf-8').replace('\r\n', '\n'), text)


if __name__ == '__main__':
    unittest.main()
