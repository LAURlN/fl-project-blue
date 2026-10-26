#!/usr/bin/env python3
"""Read-only structural inspector for a 3DS CIA (stdlib only; no keys)."""
import argparse
import hashlib
import struct
from pathlib import Path


def align64(n):
    return (n + 63) & ~63


def u16(data, off):
    return struct.unpack_from(">H", data, off)[0]


def u32(data, off):
    return struct.unpack_from(">I", data, off)[0]


def u64(data, off):
    return struct.unpack_from(">Q", data, off)[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cia", type=Path)
    args = ap.parse_args()
    data = args.cia.read_bytes()
    if len(data) < 0x2020:
        raise SystemExit("file too short for CIA header")

    header_size, cia_type, version = struct.unpack_from("<IHH", data, 0)
    cert_size, ticket_size, tmd_size, meta_size = struct.unpack_from("<IIII", data, 8)
    content_size = struct.unpack_from("<Q", data, 0x18)[0]
    # CIA header contains a 0x2000-byte content-index bitset at offset 0x20.
    index = data[0x20:0x2020]
    cert_off = align64(header_size)
    ticket_off = align64(cert_off + cert_size)
    tmd_off = align64(ticket_off + ticket_size)
    content_off = align64(tmd_off + tmd_size)
    meta_off = align64(content_off + content_size)
    if meta_off + meta_size > len(data):
        raise SystemExit("declared sections extend beyond file")

    print(f"File: {args.cia} ({len(data)} bytes)")
    print(f"CIA header: size=0x{header_size:x}, type=0x{cia_type:04x}, version={version}")
    print(f"Sections: cert={cert_size} @0x{cert_off:x}; ticket={ticket_size} @0x{ticket_off:x}; "
          f"TMD={tmd_size} @0x{tmd_off:x}; content={content_size} @0x{content_off:x}; meta={meta_size}")
    # Bit zero is the most significant bit of byte zero in Nintendo's bitmap.
    enabled = [i for i in range(len(index) * 8) if index[i // 8] & (0x80 >> (i % 8))]
    print(f"CIA content-index bitset: enabled indexes={enabled}")

    cert = data[cert_off:cert_off + cert_size]
    print(f"Certificate chain: {cert_size} bytes, SHA-256={hashlib.sha256(cert).hexdigest()}")
    pos = 0
    while pos + 4 <= len(cert):
        sig = u32(cert, pos)
        sig_len = {0x00010000: 0x200, 0x00010001: 0x100, 0x00010003: 0x400,
                   0x00010004: 0x100}.get(sig)
        if sig_len is None or pos + 4 + sig_len + 0x40 > len(cert):
            print(f"  trailing/unparsed certificate bytes at +0x{pos:x}: {len(cert)-pos}")
            break
        name = cert[pos + 4 + sig_len:pos + 4 + sig_len + 0x40].split(b"\0", 1)[0].decode("ascii", "replace")
        print(f"  certificate: signature=0x{sig:08x}, subject={name!r}")
        pos += 4 + sig_len + 0x40

    ticket = data[ticket_off:ticket_off + ticket_size]
    tsig = u32(ticket, 0)
    t_siglen = {0x00010000: 0x400, 0x00010001: 0x200, 0x00010003: 0x240,
                0x00010004: 0x140}.get(tsig, 0)
    tp = t_siglen
    issuer = ticket[tp:tp + 0x40].split(b"\0", 1)[0].decode("ascii", "replace")
    title_key = ticket[tp + 0x7f:tp + 0x8f]
    ticket_id = u64(ticket, tp + 0x90)
    console_id = u32(ticket, tp + 0x98)
    ticket_title = u64(ticket, tp + 0x9c)
    license_type = ticket[tp + 0xb0]
    ticket_ci = ticket[tp + 0x200:tp + 0x2ac] if len(ticket) >= tp + 0x2ac else b""
    print(f"Ticket: signature=0x{tsig:08x}, issuer={issuer!r}, title_id={ticket_title:016X}, "
          f"console_id=0x{console_id:08X}, ticket_id=0x{ticket_id:016X}, license_type=0x{license_type:02x}")
    print(f"  title key bytes all-FF={bool(title_key) and set(title_key)=={255}}; "
          f"ticket-class indicators: issuer/signature only (signature authenticity not verified)")
    if ticket_ci:
        ti = [i for i in range(len(ticket_ci) * 8) if ticket_ci[i // 8] & (0x80 >> (i % 8))]
        print(f"  ticket content-index bitset: enabled indexes={ti}")

    tmd = data[tmd_off:tmd_off + tmd_size]
    msig = u32(tmd, 0)
    m_siglen = {0x00010000: 0x400, 0x00010001: 0x200, 0x00010003: 0x240,
                0x00010004: 0x140}.get(msig, 0)
    mp = m_siglen
    m_issuer = tmd[mp:mp + 0x40].split(b"\0", 1)[0].decode("ascii", "replace")
    title_id = u64(tmd, mp + 0x4c)
    count = u16(tmd, mp + 0x9e)
    print(f"TMD: signature=0x{msig:08x}, issuer={m_issuer!r}, title_id={title_id:016X}, content_count={count}")
    records_off = mp + 0xc4 + 64 * 0x24
    contents = []
    for n in range(count):
        off = records_off + n * 0x30
        cid, cindex, ctype = struct.unpack_from(">IHH", tmd, off)
        size = u64(tmd, off + 8)
        digest = tmd[off + 0x10:off + 0x30]
        contents.append((cid, cindex, ctype, size, digest))
        print(f"  TMD content[{n}]: id={cid:08X}, index={cindex}, type=0x{ctype:04x} "
              f"(encrypted={bool(ctype & 1)}), size={size}, sha256={digest.hex()}")

    cursor = content_off
    for cid, cindex, ctype, expected_size, digest in contents:
        # CIA stores each present content in ascending TMD order, padded to 64-byte boundaries.
        if cindex not in enabled:
            print(f"  present content[{cindex}]: omitted (index not enabled in CIA bitset)")
            continue
        chunk = data[cursor:cursor + expected_size]
        if len(chunk) != expected_size:
            print(f"  present content[{cindex}]: truncated, expected={expected_size}, got={len(chunk)}")
            break
        magic = chunk[0x100:0x104] if len(chunk) >= 0x104 else b""
        print(f"  present content[{cindex}]: id={cid:08X}, offset=0x{cursor:x}, size={len(chunk)}, "
              f"sha256_matches_tmd={hashlib.sha256(chunk).digest()==digest}, "
              f"NCCH@+0x100={magic!r} ({magic.hex()})")
        cursor = align64(cursor + expected_size)
    print(f"Content section consumed through 0x{cursor:x}; declared end=0x{content_off+content_size:x}")


if __name__ == "__main__":
    main()
