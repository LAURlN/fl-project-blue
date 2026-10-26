#!/usr/bin/env python3
"""List 3DS IPC command headers written to the TLS command buffer (str rX,[rY,#0x80]{!}).

Scans code.bin for `ldr rt,[pc,#imm]` literals stored to TLS+0x80. Output: address,
header, command id, normal/translate param counts, containing 4-byte-aligned hint.
Candidates only: a header might be built by arithmetic instead of a literal.
usage: ipc_scan.py [code.bin] [--range 0xLO 0xHI]
"""
import struct, sys
from pathlib import Path
BASE = 0x100000
def main():
    args = sys.argv[1:]
    path = Path("extracted/fl_eu/exefs/code.bin")
    lo, hi = 0x100000, 0x61d000
    if args and not args[0].startswith("--"):
        path = Path(args.pop(0))
    if args[:1] == ["--range"]:
        lo, hi = int(args[1], 0), int(args[2], 0)
    b = path.read_bytes()
    for a in range(lo, hi, 4):
        w = struct.unpack_from("<I", b, a - BASE)[0]
        if w & 0xFFD00FFF != 0xE5800080:
            continue
        rt = (w >> 12) & 0xF
        for back in range(1, 9):
            p = a - 4 * back
            if p < BASE:
                break
            v = struct.unpack_from("<I", b, p - BASE)[0]
            if v & 0xFFFF0000 == 0xE59F0000 and (v >> 12) & 0xF == rt:
                lit = p + 8 + (v & 0xFFF) if v & 0x00800000 else p + 8 - (v & 0xFFF)
                h = struct.unpack_from("<I", b, lit - BASE)[0]
                print(f"{p:08x} hdr={h:08x} cmd={h >> 16:04x} norm={(h >> 6) & 0x3f} trans={h & 0x3f}")
                break
if __name__ == "__main__":
    main()
