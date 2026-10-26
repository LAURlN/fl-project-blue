#!/usr/bin/env python3
"""Dump the event-flag -> ECFlag mapping table (archive resource 5780) with labels (5417).

Row layout (4 bytes, 4345 rows, row index == event flag ID):
  u16 ecflag   (0xffff = flag is not DLC-controlled; else bit index in the ECFlag bitset)
  u8  bits     bit0 = c01, bit1 = c02, bit2 = c03 (semantics partly unresolved, see docs)
Standard library only. Usage: ecflag_table.py [extracted/fl_eu/archive/_unnamed] [--all]
"""
import glob
import struct
import sys
from pathlib import Path

MAGIC = bytes.fromhex("1380031d")


def load(root, rid):
    return Path(glob.glob(str(Path(root) / f"{rid:05d}_*"))[0]).read_bytes()


def table_rows(data):
    assert data[:4] == MAGIC and struct.unpack_from("<I", data, 12)[0] == len(data) - 32
    info = struct.unpack_from("<I", data, 20)[0]
    count, width, rows = struct.unpack_from("<3I", data, info)
    return [data[rows + i * width:rows + (i + 1) * width] for i in range(count)]


def labels(data):
    """Column 0 is a utf16 string pointer; returns {row: label}."""
    info = struct.unpack_from("<I", data, 20)[0]
    count, width, rows = struct.unpack_from("<3I", data, info)
    out = {}
    for i in range(count):
        p = struct.unpack_from("<I", data, rows + i * width)[0]
        e = p
        while data[e:e + 2] != b"\0\0":
            e += 2
        out[i] = data[p:e].decode("utf-16le", "replace")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = args[0] if args else "extracted/fl_eu/archive/_unnamed"
    t = table_rows(load(root, 5780))
    lab = labels(load(root, 5417))
    for i, r in enumerate(t):
        ec, bits = struct.unpack_from("<HB", r)
        if ec != 0xFFFF or "--all" in sys.argv:
            print(f"flag {i:5d} ecflag {ec:5d} bits {bits & 7:03b}  {lab.get(i, '')}")


if __name__ == "__main__":
    main()
