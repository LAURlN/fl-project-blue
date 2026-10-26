#!/usr/bin/env python3
"""List RTTI typeinfo and vtables for classes in code.bin (read-only; stdlib).

usage: rtti.py NAME-SUBSTRING [--entries N]
Finds the Itanium-ABI mangled name string, its typeinfo, and every vtable whose
slot -1 points to the typeinfo, then prints the first N function pointers.
"""
import argparse
import re
import struct
from pathlib import Path

BASE = 0x100000


def find_vtables(data, name, entries=12):
    """Find simple Itanium class names and bounded vtable candidate previews.

    Cross-references are candidates, not proof of a table's full extent: function
    pointer validation and class attribution still require disassembly.
    """
    if entries < 0:
        raise ValueError('Entry count must be nonnegative')
    words = struct.unpack_from('<%dI' % (len(data) // 4), data)
    references = {}
    for i, value in enumerate(words):
        references.setdefault(value, []).append(BASE + i*4)
    for match in re.finditer(rb'(\d+)([A-Za-z_][A-Za-z_0-9]*)\x00', data):
        class_name = match[2].decode('ascii')
        if int(match[1]) != len(class_name) or name not in class_name:
            continue
        name_va = BASE + match.start()
        types = []
        for slot in references.get(name_va, []):
            if slot < BASE + 4:
                continue
            ti = slot - 4
            tables = []
            for ti_slot in references.get(ti, []):
                vt = ti_slot + 4
                start = (vt - BASE) // 4
                tables.append(dict(address=vt, entries=list(words[start:start + entries])))
            types.append(dict(address=ti, vtables=tables))
        yield dict(name=match[0][:-1].decode('ascii'), address=name_va, types=types)


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('name')
    p.add_argument('--entries', type=int, default=12)
    p.add_argument('--binary', type=Path, default=Path('extracted/fl_eu/exefs/code.bin'))
    a = p.parse_args()
    if a.entries < 0:
        p.error('--entries must be nonnegative')
    for found in find_vtables(a.binary.read_bytes(), a.name, a.entries):
        print(f'name {found["name"]} @0x{found["address"]:08x}')
        for ti in found['types']:
            print(f'  typeinfo 0x{ti["address"]:08x}')
            for vt in ti['vtables']:
                print(f'    vtable 0x{vt["address"]:08x}: ' +
                      ' '.join(f'{e:08x}' for e in vt['entries']))


if __name__ == '__main__':
    main()
