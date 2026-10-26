#!/usr/bin/env python3
"""Read-only Fantasy Life EU raw ARM inspection. Output is dump-derived: keep ignored.

Install capstone into tools/build/re-python; run with PYTHONPATH set to that path.
Pointer scans are candidates, not proven instruction references.
"""
import argparse
import re
import struct
from pathlib import Path

BASE = 0x100000
SEGMENTS = [("text", 0x100000, 0x51cc68), ("rodata", 0x61d000, 0x862e8),
            ("data", 0x6a4000, 0x371b4), ("bss", 0x6dc000, 0xcca88)]


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--binary", type=Path, default=Path("extracted/fl_eu/exefs/code.bin"))
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("strings")
    s.add_argument("pattern", nargs="?", default="ECFlag|aoc|Payable|ext:/|dlc:|cont:|am:app|PackBin|ResourceDataManager|Purchase")
    x = sub.add_parser("refs")
    x.add_argument("address", type=lambda s: int(s, 0))
    c = sub.add_parser("calls", help="ARM B/BL immediate references (candidates, includes literal data)")
    c.add_argument("address", type=lambda s: int(s, 0))
    d = sub.add_parser("disasm")
    d.add_argument("address", type=lambda s: int(s, 0))
    d.add_argument("--size", type=lambda s: int(s, 0), default=0x100)
    d.add_argument("--thumb", action="store_true")
    w = sub.add_parser("words")
    w.add_argument("address", type=lambda s: int(s, 0))
    w.add_argument("--count", type=int, default=32)
    args = p.parse_args()
    b = args.binary.read_bytes()
    if args.command == "strings":
        for encoding, regex in [("ascii", rb"[ -~]{4,}"), ("utf-16le", rb"(?:[ -~]\x00){4,}")]:
            for m in re.finditer(regex, b):
                text = m[0].decode(encoding)
                if re.search(args.pattern, text, re.I):
                    print(f"0x{BASE + m.start():08x} {encoding}: {text}")
    elif args.command == "refs":
        for m in re.finditer(re.escape(struct.pack("<I", args.address)), b):
            print(f"0x{BASE + m.start():08x}")
    elif args.command == "calls":
        for offset in range(0, SEGMENTS[0][2] - 3, 4):
            word = struct.unpack_from("<I", b, offset)[0]
            if word & 0x0e000000 != 0x0a000000:
                continue
            displacement = (word & 0xffffff) << 2
            if displacement & 0x2000000:
                displacement -= 0x4000000
            if BASE + offset + 8 + displacement == args.address:
                print(f"0x{BASE + offset:08x} {'BL' if word & 0x1000000 else 'B'} cond={word >> 28:x}")
    elif args.command == "words":
        for a in range(args.address, args.address + args.count * 4, 4):
            v = struct.unpack_from("<I", b, a - BASE)[0]
            print(f"0x{a:08x}: 0x{v:08x}")
    else:
        from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
        from capstone.arm import ARM_OP_MEM, ARM_REG_PC
        cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB if args.thumb else CS_MODE_ARM)
        cs.detail = True
        cs.skipdata = True
        for i in cs.disasm(b[args.address - BASE:args.address - BASE + args.size], args.address):
            note = ""
            if i.id:
                for op in i.operands:
                    if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
                        lit = ((i.address + (4 if args.thumb else 8)) & ~3) + op.mem.disp
                        if BASE <= lit <= BASE + len(b) - 4:
                            v = struct.unpack_from("<I", b, lit - BASE)[0]
                            note = f" ; [0x{lit:08x}] = 0x{v:08x}"
            print(f"{i.address:08x}: {i.bytes.hex():10} {i.mnemonic:8} {i.op_str}{note}")


if __name__ == "__main__":
    main()
