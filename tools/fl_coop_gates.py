#!/usr/bin/env python3
"""Co-op freedom: the multiplayer gates the runtime may lift, pinned to their EU v00 script sites.

The game asks one script native, 453 (handler 0x003a86c0), "am I in multiplayer, and as what?"
(0 solo, 1 host with visitors, 2 host with the portal open and nobody in yet, 3 visitor). Every
script gate in docs/coop-freedom.md is a `native 453; push 0; alu ne; jump_zero <solo path>` at one
call site. The runtime hook (port runtime/src/games/fantasylife/coop.cpp) recognises a site by the
script bytes around the executing instruction and answers 0 there, so the script takes its solo
path; at every other call of native 453 the game's own answer stands.

This tool is the single source of those sites. `check` verifies against the extracted archive that
every pattern matches exactly the declared sites and nothing else, and reports how the sites look
in other enabled overlays (story-skip replaces 21172 and 27679). `generate` writes the C++ table
the runtime compiles in. Nothing here edits a game resource; no overlay is needed.

Usage:
  python -I tools/fl_coop_gates.py check <extracted/fl_eu/archive> [overlay dirs...]
  python -I tools/fl_coop_gates.py generate <out coop_sites.inc>
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parent


def local(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = local('fl_script')
fl_scr = script.fl_scr
fl_archive = local('fl_archive')

VERSION = 1
MP_ROLE = 453          # native: multiplayer role, handler 0x003a86c0
BEFORE, AFTER = 8, 8   # instructions compared before the call, and from the call on
BRANCHES = {10, 15, 16}  # call/jump/jump_zero: operands are PCs, which move when a mod inserts code
WIDTH = 5              # every gated script uses <u8 opcode, u32 operand>

# Gate id (runtime enum order), settings key, roles the gate is lifted for, sites (resource, pc, why).
# Roles: 1 host with visitors, 2 host with the portal open, 3 visitor. See docs/coop-freedom.md.
GATES = [
    ('change_life', 'fl_coop_change_life', (1, 2, 3), [
        (21172, 5516, 'global 46, Guild Master Life change (all three Guild Offices); 21908 row 9'),
    ]),
    ('report', 'fl_coop_report', (1, 2), [
        (21172, 9418, 'global 55, report to master; 21180 row 59'),
        (21290, 1652, 'master: Cook (map 152) routes multiplayer talk to global 31'),
        (21924, 1541, 'master routing (map 214)'),
        (21984, 51, 'master routing (map 219)'),
        (21996, 1875, 'master routing (map 220)'),
        (22312, 7302, 'master routing (map 249)'),
        (22336, 7763, 'master routing (map 251)'),
        (22352, 2959, 'master routing (map 253), first master'),
        (22352, 2983, 'master routing (map 253), second master'),
        (22352, 3007, 'master routing (map 253), third master'),
        (22376, 1985, 'master routing (map 255)'),
        (23133, 6220, 'master routing (map 32)'),
        (23145, 7160, 'master routing (map 33), first master'),
        (23145, 7184, 'master routing (map 33), second master'),
        (22440, 6270, 'Goddess ship (map 261): all-God-rank promotion; 22448 row 63'),
        (22440, 6367, 'Goddess ship: Legend promotion; 22448 row 63'),
        (22440, 6492, 'Goddess ship: report beyond Legend; 22448 row 63'),
    ]),
    ('makeover', 'fl_coop_makeover', (1, 2, 3), [
        (21172, 2604, 'global 37, Salon de Florina hair styling'),
        (23735, 35, 'Timeless Beauty avatar remake; 23743 row 133'),
        (27679, 9330, 'Angelic Mirror avatar remodel; SYS003 row 289'),
        (27679, 9377, 'Demonic Mirror stat reset; SYS003 row 295'),
    ]),
]
GATE_IDS = {name: i for i, (name, _, _, _) in enumerate(GATES)}


def require(cond, message):
    if not cond:
        raise ValueError(message)


def vm(data):
    """(layout, code bytes) of a VM wrapper, or None for anything else."""
    if data[:8] != script.WRAPPER:
        return None
    first, second = script.sections(data)
    if first[:4] in (fl_scr.MAGIC, b'MSG '):
        return None
    layout = script.vm_layout(first, second)
    return layout, second


def window(layout, code, pc):
    """Masked byte pattern for the call at `pc`: (instructions before, bytes, mask)."""
    require(layout['width'] == WIDTH, 'gated scripts use 5-byte instructions')
    ops = layout['ops']
    require(ops[pc] == (7, MP_ROLE << 8), f'pc {pc} is not native {MP_ROLE}')
    lo, hi = max(0, pc - BEFORE), min(len(ops), pc + AFTER)
    raw = bytes(code[lo * WIDTH:hi * WIDTH])
    mask = bytearray(b'\xff' * len(raw))
    for i in range(lo, hi):
        if ops[i][0] in BRANCHES:
            at = (i - lo) * WIDTH
            mask[at + 1:at + 5] = b'\0\0\0\0'
    return pc - lo, raw, bytes(mask)


def matches(pattern, code, ops, pc):
    before, raw, mask = pattern
    start = (pc - before) * WIDTH
    if start < 0 or start + len(raw) > len(ops) * WIDTH:
        return False
    return all((code[start + i] ^ raw[i]) & mask[i] == 0 for i in range(len(raw)))


def is_refusal(ops, pc):
    """`native 453; push 0; alu ne; jump_zero <solo>`: answering 0 takes the solo branch."""
    return ops[pc + 1:pc + 3] == [(1, 0), (17, script.ALU_NAMES.index('ne'))] and ops[pc + 3][0] == 16


def archive_resources(root):
    for rid, path in script.corpus(root):
        yield rid, path.read_bytes()


def overlay_resources(folder):
    manifest = json.loads((Path(folder) / 'overlay.json').read_text(encoding='utf-8'))
    for entry in manifest['resources']:
        stored = (Path(folder) / entry['file']).read_bytes()
        raw = fl_archive.decompress_nintendo(stored)[0] if entry.get('compression') else stored
        yield entry['id'], raw, manifest['name']


def patterns(root):
    """[(gate, rid, pc, why, pattern)] from the original archive."""
    resolver = script.Resolver(root)
    out = []
    for gate, _, _, sites in GATES:
        for rid, pc, why in sites:
            parsed = vm(resolver.entries[rid].read_bytes())
            require(parsed, f'{rid} is not a VM script')
            layout, code = parsed
            require(is_refusal(layout['ops'], pc), f'{rid} pc {pc} is not a multiplayer refusal branch')
            out.append((gate, rid, pc, why, window(layout, code, pc)))
    return out


def scan(pats, resources):
    """Every (rid, pc) where some pattern matches a native 453 call, with the pattern's index."""
    found = []
    for rid, data in resources:
        parsed = vm(data)
        if not parsed or parsed[0]['width'] != WIDTH:
            continue
        layout, code = parsed
        ops = layout['ops']
        for pc, op in enumerate(ops):
            if op != (7, MP_ROLE << 8):
                continue
            for i, p in enumerate(pats):
                if matches(p[4], code, ops, pc):
                    found.append((i, rid, pc))
    return found


def check(root, overlays=()):
    pats = patterns(root)
    found = scan(pats, archive_resources(root))
    # A pattern may also match another declared site of the same gate (identical shipped code in
    # two master scripts); it must never match an undeclared call or another gate's site.
    sites = {(p[1], p[2]): p[0] for p in pats}
    stray = sorted((pats[i][0], rid, pc) for i, rid, pc in found if sites.get((rid, pc)) != pats[i][0])
    missing = sorted((p[1], p[2]) for i, p in enumerate(pats) if (i, p[1], p[2]) not in set(found))
    require(not stray and not missing, f'patterns are not exact: stray {stray}, missing {missing}')
    report = dict(sites=len(pats), overlays={})
    for folder in overlays:
        items = list(overlay_resources(folder))
        name = items[0][2] if items else str(folder)
        replaced = {rid for rid, _, _ in items}
        hits = scan(pats, ((rid, raw) for rid, raw, _ in items))
        status = {}
        for i, p in enumerate(pats):
            if p[1] in replaced:
                where = [pc for j, rid, pc in hits if j == i and rid == p[1]]
                require(len(where) <= 1, f'{name}: pattern {i} matches {p[1]} at {where}')
                status[f'{p[1]}@{p[2]}'] = where[0] if where else None
        report['overlays'][name] = status
    return report


def cxx(pats):
    lines = [
        '// Generated by tools/fl_coop_gates.py (version %d). Do not edit: regenerate and re-run' % VERSION,
        '// `fl_coop_gates.py check` against the EU v00 archive. Each row: gate, resource, pc, how many',
        '// 5-byte instructions precede the native 453 call, the bytes, and the mask (00 = branch operand,',
        '// ignored so a mod that inserts code elsewhere in the script does not hide the site).',
    ]
    for gate, rid, pc, why, (before, raw, mask) in pats:
        lines.append(f'// {why}')
        lines.append(f'{{Gate::{camel(gate)}, {rid}, {pc}, {before}, "{raw.hex()}", "{mask.hex()}"}},')
    return '\n'.join(lines) + '\n'


def camel(name):
    return ''.join(part.capitalize() for part in name.split('_'))


# SHA-256 of `generate` output for the pinned EU v00 archive; changes only on purpose.
GENERATED_SHA256 = 'd12ce0519e09e1189b49390dcf7a948b9a986443b4a80a3439d302b028098c99'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('archive')
    c.add_argument('overlays', nargs='*')
    g = sub.add_parser('generate')
    g.add_argument('archive')
    g.add_argument('output')
    a = ap.parse_args(argv)
    if a.cmd == 'check':
        print(json.dumps(check(a.archive, a.overlays), indent=2))
    else:
        text = cxx(patterns(a.archive))
        Path(a.output).write_text(text, encoding='utf-8', newline='\n')
        print(a.output, hashlib.sha256(text.encode()).hexdigest())


if __name__ == '__main__':
    sys.exit(main())
