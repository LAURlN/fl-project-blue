#!/usr/bin/env python3
"""Fantasy Life EU resource archive reader/writer; Python 3.10+, standard library.

Run with python3 -I. The manifest is part of the editable extraction: it preserves
entry IDs, unnamed-file mappings, original compressed streams and opaque padding.
No game data, third-party modules, or executable game code is needed by this tool.
See docs/phase1-archive-formats.md for the measured format and its limitations.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import zlib

MAX_OUTPUT = 256 * 1024 * 1024
META = '.fl_archive'
PACK_MAGIC = b'R \rC'
INDEX_MAGIC = b'\xc3\x30\x0e\x53'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def u32(data, pos=0):
    require(0 <= pos <= len(data) - 4, 'Truncated integer')
    return struct.unpack_from('<I', data, pos)[0]


def span(data, pos, size):
    require(0 <= pos <= pos + size <= len(data), 'Range outside input')
    return data[pos:pos + size]


def align(n, a=32):
    require(a > 0 and a & (a - 1) == 0, 'Invalid alignment')
    return (n + a - 1) & -a


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_name(name):
    require(isinstance(name, str) and '\\' not in name and '\x00' not in name,
            'Unsafe path')
    p = PurePosixPath(name)
    require(name and not p.is_absolute() and all(x not in ('', '.', '..') for x in name.split('/'))
            and ':' not in name, f'Unsafe path: {name!r}')
    return p


def safe_path(root, name):
    p = validate_name(name)
    path = root.joinpath(*p.parts)
    require(not root.is_symlink() and all(not x.is_symlink() for x in (path, *path.parents)),
            f'Symlink in output path: {path}')
    return path


def put(root, name, data):
    path = safe_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f'Duplicate output path: {name}')
    path.write_bytes(data)


def decompress_nintendo(data):
    """Strict LZ10/LZ11, RLE and 4/8-bit Huffman; returns (bytes, consumed)."""
    require(len(data) >= 4, 'Missing compression header')
    kind = data[0]
    require(kind in (0x10, 0x11, 0x24, 0x28, 0x30), 'Unknown Nintendo codec')
    size, pos = u32(data) >> 8, 4
    if size == 0 and kind == 0x11:
        size, pos = u32(data, pos), pos + 4
    require(size <= MAX_OUTPUT, 'Compression output limit exceeded')
    out = bytearray()

    def take(n):
        nonlocal pos
        part = span(data, pos, n)
        pos += n
        return part

    if kind in (0x24, 0x28):
        bits = kind & 15
        tree_size = (take(1)[0] + 1) * 2
        tree = data[pos - 1:pos - 1 + tree_size]
        require(len(tree) == tree_size, 'Truncated Huffman tree')
        pos += tree_size - 1
        node, word, remaining, nibble = 1, 0, 0, None
        while len(out) < size:
            if not remaining:
                word = int.from_bytes(take(4), 'little')
                remaining = 32
            remaining -= 1
            branch = word >> remaining & 1
            descriptor = tree[node]
            child = (node & ~1) + ((descriptor & 63) + 1) * 2 + branch
            require(child < len(tree), 'Huffman child outside tree')
            if descriptor & (0x80 >> branch):
                value = tree[child]
                require(bits == 8 or value < 16, 'Invalid Huffman nibble')
                if bits == 8:
                    out.append(value)
                elif nibble is None:
                    nibble = value
                else:
                    out.append(nibble | value << 4)
                    nibble = None
                node = 1
            else:
                node = child
        return bytes(out), pos
    if kind == 0x30:
        while len(out) < size:
            control = take(1)[0]
            length = (control & 127) + (3 if control & 128 else 1)
            require(len(out) + length <= size, 'RLE exceeds output size')
            out.extend(take(1) * length if control & 128 else take(length))
        return bytes(out), pos
    while len(out) < size:
        flags = take(1)[0]
        for bit in range(7, -1, -1):
            if len(out) == size:
                break
            if not (flags >> bit & 1):
                out.extend(take(1))
                continue
            a, b = take(2)
            tag = a >> 4
            if kind == 0x10:
                length, distance = tag + 3, ((a & 15) << 8 | b) + 1
            elif tag == 0:
                c = take(1)[0]
                length, distance = ((a & 15) << 4 | b >> 4) + 17, ((b & 15) << 8 | c) + 1
            elif tag == 1:
                c, e = take(2)
                length = ((a & 15) << 12 | b << 4 | c >> 4) + 273
                distance = ((c & 15) << 8 | e) + 1
            else:
                length, distance = tag + 1, ((a & 15) << 8 | b) + 1
            require(distance <= len(out), 'LZ reference before output')
            require(len(out) + length <= size, 'LZ exceeds output size')
            # Repeat a slice to handle overlapping references without a byte loop.
            chunk = out[-distance:]
            out.extend((chunk * ((length + distance - 1) // distance))[:length])
    return bytes(out), pos


def decompress_level5(data):
    """Level-5 size<<3|codec envelope: raw, LZ10, Huffman4/8, RLE, zlib."""
    header = u32(data)
    size, kind = header >> 3, header & 7
    require(size <= MAX_OUTPUT, 'Level-5 output limit exceeded')
    if kind == 0:
        return span(data, 4, size)
    if kind == 5:
        obj = zlib.decompressobj()
        out = obj.decompress(data[4:], size + 1)
        require(obj.eof and len(out) == size, 'Invalid Level-5 zlib stream')
        return out
    require(kind in (1, 2, 3, 4) and size <= 0xffffff, 'Unknown Level-5 codec')
    tag = {1: 0x10, 2: 0x24, 3: 0x28, 4: 0x30}[kind]
    return decompress_nintendo(struct.pack('<I', size << 8 | tag) + data[4:])[0]


def compress_lz11(data):
    """Deterministic greedy LZ11 encoder for edited resources (4 KiB window)."""
    size = len(data)
    require(size <= MAX_OUTPUT, 'Resource too large')
    out = bytearray(struct.pack('<I', size << 8 | 0x11) if 0 < size <= 0xffffff
                    else b'\x11\0\0\0' + struct.pack('<I', size))
    pos, matches = 0, {}
    while pos < size:
        flag_pos = len(out)
        out.append(0)
        for bit in range(7, -1, -1):
            if pos == size:
                break
            best, distance = 0, 0
            key = data[pos:pos + 3]
            candidates = matches.get(key, [])
            for previous in reversed(candidates[-32:]):
                dist = pos - previous
                if dist > 4096:
                    break
                limit = min(size - pos, 65808)
                length = 3
                while length < limit and data[previous + length] == data[pos + length]:
                    length += 1
                if length > best:
                    best, distance = length, dist
                if best == limit:
                    break
            step = 1
            if best >= 3 and len(key) == 3:
                out[flag_pos] |= 1 << bit
                step, d = best, distance - 1
                if best <= 16:
                    out.extend(((best - 1) << 4 | d >> 8, d & 255))
                elif best <= 272:
                    v = best - 17
                    out.extend((v >> 4, (v & 15) << 4 | d >> 8, d & 255))
                else:
                    v = best - 273
                    out.extend((0x10 | v >> 12, v >> 4 & 255, (v & 15) << 4 | d >> 8, d & 255))
            else:
                out.append(data[pos])
            for at in range(pos, pos + step):
                k = data[at:at + 3]
                chain = matches.setdefault(k, [])
                chain.append(at)
                if len(chain) > 64:
                    del chain[:-32]
            pos += step
    return bytes(out)


MAGICS = {b'zmdl': 'mdl', b'ztex': 'tex', b'zmta': 'mta', b'BPAK': 'bpak',
          b'CB01': 'cb', b'GB01': 'gb', b'FB01': 'fb', b'CSAR': 'bcsar',
          b'CGFX': 'bcres', b'CFNT': 'bcfnt', b'CLIM': 'bclim', b'MOTA': 'mota',
          b'COL0': 'col', PACK_MAGIC: 'bin', b'ARC0': 'arc', b'XFSA': 'xfsa',
          b'XPCK': 'xpck', b'\x13\x80\x03\x1d': 'scr', b'\x02\0\0\0': 'scr',
          INDEX_MAGIC: 'index'}


def extension(data):
    return MAGICS.get(data[:4], 'bin')


def parse_pack(data):
    """Fantasy Life named R-space-CR-C packs; offsets are absolute."""
    require(data[:4] == PACK_MAGIC and len(data) >= 20, 'Not an FL pack')
    require(u32(data, 4) + 20 == len(data), 'FL pack size mismatch')
    table = u32(data, 16)
    require(20 <= table <= len(data) and (len(data) - table) % 20 == 0, 'Invalid pack table')
    result = []
    for pos in range(table, len(data), 20):
        zero, length, basename, ext, alignment, size, namepos, offset = struct.unpack_from('<4B4I', data, pos)
        name = span(data, namepos, length).decode('ascii')
        validate_name(name)
        require(span(data, namepos + length, 1) == b'\0', 'Unterminated pack name')
        require(basename == name.rfind('/') + 1 and ext == name.rfind('.') + 1,
                'Pack name component offsets disagree')
        require(offset >= 20 and offset + size <= table and namepos + length < table,
                'Pack member outside data region')
        align(0, alignment)
        require(offset % alignment == 0, 'Unaligned pack member')
        result.append(dict(name=name, offset=offset, size=size, alignment=alignment,
                           record=pos, zero=zero))
    require(len({r['name'] for r in result}) == len(result), 'Duplicate pack names')
    return result


def parse_index(data, count):
    require(data[:4] == INDEX_MAGIC and len(data) >= 24, 'Missing resource relationship index')
    require(u32(data, 4) + 24 == len(data), 'Index size mismatch')
    files, packs = struct.unpack_from('<HH', data, 8)
    flagspos, packpos = struct.unpack_from('<II', data, 16)
    require(files == count and flagspos + files * 4 == len(data), 'Index file count mismatch')
    require(packpos + packs * 12 == flagspos, 'Index pack table mismatch')
    roles = list(struct.iter_unpack('<HH', data[flagspos:]))
    relations = []
    seen = set()
    for i in range(packs):
        parent, members, alignment, idspos = struct.unpack_from('<IHHI', data, packpos + 12 * i)
        ids = list(struct.unpack('<' + 'H' * members, span(data, idspos, members * 2)))
        require(parent < count and roles[parent] == (i, 1), 'Invalid pack parent role')
        for child in ids:
            require(child < count and roles[child] == (i, 2) and child not in seen,
                    'Invalid pack child role')
            seen.add(child)
        relations.append(dict(parent=parent, children=ids, alignment=alignment))
    require(all(kind in (0, 1, 2) and (kind != 0 or group == 65535)
                for group, kind in roles), 'Unknown resource role')
    require(seen == {i for i, (_, kind) in enumerate(roles) if kind == 2}, 'Unmapped virtual entries')
    return roles, relations


def parse_archive(data):
    require(len(data) >= 8, 'Truncated archive')
    count, reserved = struct.unpack_from('<II', data)
    require(2 <= count <= 65535 and 8 + 13 * count <= len(data), 'Invalid archive count')
    arrays = [struct.unpack_from(f'<{count}I', data, 8 + k * 4 * count) for k in range(3)]
    flags = span(data, 8 + 12 * count, count)
    require(set(flags) <= {0, 1}, 'Invalid compression flags')
    entries = [dict(id=i, offset=arrays[0][i], size=arrays[1][i], stored_size=arrays[2][i],
                    compressed=flags[i]) for i in range(count)]
    idx = entries[1]
    require(not idx['compressed'], 'Compressed relationship index unsupported')
    roles, relations = parse_index(span(data, idx['offset'], idx['stored_size']), count)
    physical = [r for r in entries if roles[r['id']][1] != 2]
    end = 8 + 13 * count
    for r in physical:
        require(r['offset'] >= end and r['offset'] % 32 == 0, 'Overlapping/unaligned physical entry')
        require(r['size'] <= MAX_OUTPUT, 'Entry output limit exceeded')
        span(data, r['offset'], r['stored_size'])
        require(r['compressed'] or r['stored_size'] == r['size'], 'Raw entry size mismatch')
        end = r['offset'] + r['stored_size']
    return dict(version=1, count=count, reserved=reserved, entries=entries,
                physical_ids=[r['id'] for r in physical], relations=relations,
                archive_size=len(data), archive_sha256=sha(data))


def decode_entry(data, r):
    stored = span(data, r['offset'], r['stored_size'])
    raw = decompress_nintendo(stored)[0] if r['compressed'] else stored
    require(len(raw) == r['size'], f"Entry {r['id']} size mismatch")
    return raw


def parse_bpak(data):
    count = u32(data, 4)
    require(count <= 65535 and 8 + count * 8 <= len(data), 'Invalid BPAK count')
    # BPAK has a u32 offset AND u32 size for each member.
    result = []
    for i in range(count):
        offset, size = struct.unpack_from('<II', data, 8 + i * 8)
        require(offset >= 8 + count * 8, 'BPAK member overlaps table')
        raw = span(data, offset, size)
        result.append(dict(name=f'{i:05d}_{sha(raw)[:12]}.{extension(raw)}', offset=offset,
                           size=size, record=8 + i * 8))
    return result


def parse_level5_archive(data):
    """Read ARC0/XFSA/XPCK using CRC32 names; no such files occur in EU dump."""
    magic = data[:4]
    if magic == b'XPCK':
        require(len(data) >= 20, 'Truncated XPCK')
        count = int.from_bytes(data[4:6], 'little') & 0xfff
        info, namespos, base, infosize, nameslen = struct.unpack_from('<5H', data, 6)
        info, namespos, base, infosize, nameslen = [x * 4 for x in (info, namespos, base, infosize, nameslen)]
        names = decompress_level5(span(data, namespos, nameslen))
        table = span(data, info, count * 12)
    else:
        _, _, info, namespos, base = struct.unpack_from('<5I', data, 4)
        require(24 <= info <= namespos <= base <= len(data), 'Invalid Level-5 tables')
        names = decompress_level5(span(data, namespos, base - namespos))
        table = decompress_level5(span(data, info, namespos - info))
    mapping, folder = {}, ''
    for name in names.split(b'\0'):
        if not name:
            continue
        decoded = name.decode('utf-8')
        if decoded.endswith('/'):
            folder = decoded
        else:
            crc = zlib.crc32(name)
            require(crc not in mapping, 'Ambiguous Level-5 CRC32')
            mapping[crc] = folder + decoded
    result = []
    width = 16 if magic == b'ARC0' else 12
    require(len(table) % width == 0, 'Invalid Level-5 table size')
    if magic == b'XFSA' and data[info + 4:info + 5] == b'\x0f':
        table = bytes((x << 4 & 255) | x >> 4 for x in table)
    for i in range(0, len(table), width):
        if magic == b'ARC0':
            crc, _, offset, size = struct.unpack_from('<4I', table, i)
        else:
            crc, a, b = struct.unpack_from('<3I', table, i)
            offset, size = ((a >> 16) * 4, b) if magic == b'XPCK' else ((a & 0xffffff) * 16, b & 0x7fffff)
        name = mapping.get(crc, f'{crc:08x}.bin')
        validate_name(name)
        span(data, base + offset, size)
        result.append(dict(name=name, offset=base + offset, size=size, crc32=crc))
    return result


def unpack_nested(root, raw, prefix, depth=0):
    require(depth <= 12, 'Nested container depth limit')
    magic = raw[:4]
    if magic == PACK_MAGIC:
        kind, members = 'flpack', parse_pack(raw)
    elif magic == b'BPAK':
        kind, members = 'bpak', parse_bpak(raw)
    elif magic in (b'ARC0', b'XFSA', b'XPCK'):
        kind, members = magic.decode(), parse_level5_archive(raw)
    else:
        return None
    for r in members:
        value = span(raw, r['offset'], r['size'])
        r['path'] = (prefix + '/' if prefix else '') + r['name']
        r['sha256'] = sha(value)
        put(root, r['path'], value)
        nested = unpack_nested(root, value, r['path'] + '.unpacked', depth + 1)
        if nested:
            r['nested'] = nested
        elif r['name'].lower().endswith('.lz'):
            decoded = decompress_nintendo(value)[0]
            r['decoded_path'] = r['path'] + '.decoded'
            r['decoded_sha256'] = sha(decoded)
            put(root, r['decoded_path'], decoded)
    return dict(kind=kind, members=members)


def extract(archive, outdir):
    require(not outdir.is_symlink() and (not outdir.exists() or not any(outdir.iterdir())),
            'Extraction requires a new or empty directory')
    data = archive.read_bytes()
    manifest = parse_archive(data)
    outdir.mkdir(parents=True, exist_ok=True)
    put(outdir, META + '/original.bin', data)
    relation_map = {g['parent']: g for g in manifest['relations']}
    for i in manifest['physical_ids']:
        r = manifest['entries'][i]
        raw = decode_entry(data, r)
        r['sha256'] = sha(raw)
        r['path'] = f"{'_packs' if i in relation_map else '_unnamed'}/{i:05d}_{r['sha256'][:12]}.{extension(raw)}"
        put(outdir, r['path'], raw)
        if i in relation_map:
            members = parse_pack(raw)
            group = relation_map[i]
            require(len(members) == len(group['children']), 'Relationship member count mismatch')
            for child, member in zip(group['children'], members):
                c = manifest['entries'][child]
                require(c['size'] == member['size'], f'Virtual entry {child} size mismatch')
                member['id'] = child
                c['path'] = member['name']
                c['parent'] = i
                c['member_offset'] = member['offset']
            # Named pack children are restored at archive root, with exact original names.
            r['nested'] = unpack_nested(outdir, raw, '')
            for member, actual in zip(members, r['nested']['members']):
                manifest['entries'][member['id']]['sha256'] = actual['sha256']
        else:
            nested = unpack_nested(outdir, raw, r['path'] + '.unpacked')
            if nested:
                r['nested'] = nested
        if i % 2000 == 0:
            print(f'Extracted physical entry {i}/{manifest["count"]}', file=sys.stderr)
    put(outdir, META + '/manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
    print(f"Extracted {len(manifest['physical_ids'])} physical + "
          f"{manifest['count'] - len(manifest['physical_ids'])} virtual entries")
    return manifest


def rebuild_nested(root, template, nested):
    members, values, changed = nested['members'], [], False
    for r in members:
        raw = safe_path(root, r['path']).read_bytes()
        direct_changed = sha(raw) != r['sha256']
        if 'nested' in r:
            rebuilt = rebuild_nested(root, span(template, r['offset'], r['size']), r['nested'])
            if rebuilt != span(template, r['offset'], r['size']):
                require(not direct_changed or raw == rebuilt, 'Conflicting parent and nested edits')
                raw = rebuilt
        if 'decoded_path' in r:
            decoded = safe_path(root, r['decoded_path']).read_bytes()
            if sha(decoded) != r['decoded_sha256']:
                require(not direct_changed, 'Conflicting .lz and decoded edits')
                raw = compress_lz11(decoded)
        values.append(raw)
        changed |= sha(raw) != r['sha256']
    if not changed:
        return template
    kind = nested['kind']
    require(kind in ('flpack', 'bpak'), f'Editing nested {kind} is not implemented')
    if all(len(raw) == r['size'] for r, raw in zip(members, values)):
        out = bytearray(template)
        for r, raw in zip(members, values):
            out[r['offset']:r['offset'] + r['size']] = raw
        return bytes(out)
    if kind == 'bpak':
        out = bytearray(8 + len(members) * 8)
        out[:8] = template[:8]
        alignment = min((r['offset'] & -r['offset'] for r in members if r['size']), default=4)
        for i, raw in enumerate(values):
            out.extend(b'\0' * (align(len(out), alignment) - len(out)))
            struct.pack_into('<II', out, 8 + i * 8, len(out), len(raw))
            out.extend(raw)
        return bytes(out)
    out = bytearray(template[:20])
    records = bytearray()
    for r, raw in zip(members, values):
        out.extend(b'\0' * (align(len(out), r['alignment']) - len(out)))
        offset = len(out)
        out.extend(raw)
        namepos = len(out)
        out.extend(r['name'].encode('ascii') + b'\0')
        out.extend(b'\0' * (align(len(out), 4) - len(out)))
        record = bytearray(template[r['record']:r['record'] + 20])
        struct.pack_into('<III', record, 8, len(raw), namepos, offset)
        records.extend(record)
    table = len(out)
    out.extend(records)
    struct.pack_into('<I', out, 4, len(out) - 20)
    struct.pack_into('<I', out, 16, table)
    return bytes(out)


def nested_changed(root, nested):
    """Check editable leaves before paying to decompress the original parent."""
    for r in nested['members']:
        if sha(safe_path(root, r['path']).read_bytes()) != r['sha256']:
            return True
        if 'decoded_path' in r and sha(safe_path(root, r['decoded_path']).read_bytes()) != r['decoded_sha256']:
            return True
        if 'nested' in r and nested_changed(root, r['nested']):
            return True
    return False


def build(indir, archive):
    manifest = json.loads(safe_path(indir, META + '/manifest.json').read_text())
    original = safe_path(indir, META + '/original.bin').read_bytes()
    require(sha(original) == manifest['archive_sha256'], 'Preserved source hash mismatch')
    parsed = parse_archive(original)
    require(manifest['count'] == parsed['count'] and manifest['physical_ids'] == parsed['physical_ids'],
            'Manifest structure changed; adding/removing IDs is unsupported')
    entries = manifest['entries']
    # Validate the format-owned entry table, then use it rather than editable offsets.
    for r, p in zip(entries, parsed['entries']):
        require(all(r[k] == p[k] for k in ('id', 'offset', 'size', 'stored_size', 'compressed')),
                'Manifest entry table was modified')
    updates, virtual_sizes = {}, {}
    for i in manifest['physical_ids']:
        r = entries[i]
        raw = safe_path(indir, r['path']).read_bytes()
        direct_changed = sha(raw) != r['sha256']
        if 'nested' in r and nested_changed(indir, r['nested']):
            template = decode_entry(original, r)
            rebuilt = rebuild_nested(indir, template, r['nested'])
            if rebuilt != template:
                require(not direct_changed or raw == rebuilt, f'Conflicting parent and nested edits: {i}')
                raw = rebuilt
        if sha(raw) != r['sha256']:
            require(i != 1, 'Editing the relationship index is unsupported')
            updates[i] = (raw, compress_lz11(raw) if r['compressed'] else raw)
            if raw[:4] == PACK_MAGIC and i in {g['parent'] for g in manifest['relations']}:
                members = parse_pack(raw)
                group = next(g for g in manifest['relations'] if g['parent'] == i)
                require(len(members) == len(group['children']), 'Adding/removing pack members is unsupported')
                for child, member in zip(group['children'], members):
                    require(member['name'] == entries[child]['path'], 'Changing member paths is unsupported')
                    content = span(raw, member['offset'], member['size'])
                    if sha(content) != entries[child]['sha256']:
                        virtual_sizes[child] = len(content)
    require(archive.resolve() != safe_path(indir, META + '/original.bin').resolve(), 'Cannot overwrite preserved source')
    require(not archive.is_symlink(), 'Refusing output symlink')
    # Exact original layout, padding and compression are retained for an unchanged tree.
    if not updates:
        archive.write_bytes(original)
        print(f'Byte-identical rebuild: {len(original)} bytes, SHA-256 {sha(original)}')
        return
    count = manifest['count']
    out = bytearray(original[:8 + 13 * count])
    updated_records = [dict(r) for r in entries]
    physical_set = set(manifest['physical_ids'])
    for r in updated_records:
        if r['id'] in physical_set:
            out.extend(b'\0' * (align(len(out)) - len(out)))
            source = entries[r['id']]
            if r['id'] in updates:
                raw, stored = updates[r['id']]
                r['size'], r['stored_size'] = len(raw), len(stored)
            else:
                stored = span(original, source['offset'], source['stored_size'])
            r['offset'] = len(out)
            out.extend(stored)
        else:
            # Virtual offsets point at the next physical allocation, not their parent.
            r['offset'] = align(len(out))
            if r['id'] in virtual_sizes:
                r['size'] = virtual_sizes[r['id']]
                parent = next(g['parent'] for g in manifest['relations'] if r['id'] in g['children'])
                raw = updates[parent][0]
                member = next(m for m in parse_pack(raw) if m['name'] == r['path'])
                r['stored_size'] = len(compress_lz11(span(raw, member['offset'], member['size'])))
    out.extend(b'\0' * (align(len(out)) - len(out)))
    for r in updated_records:
        for k, field in enumerate(('offset', 'size', 'stored_size')):
            struct.pack_into('<I', out, 8 + k * count * 4 + r['id'] * 4, r[field])
    parse_archive(out)
    archive.write_bytes(out)
    print(f"Rebuilt {len(updates)} edited physical entries; {len(out)} bytes, SHA-256 {sha(out)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    listing = subs.add_parser('list', help='List entry IDs, roles, sizes and physical offsets')
    listing.add_argument('archive', type=Path)
    listing.add_argument('--json', action='store_true')
    extracting = subs.add_parser('extract', help='Extract named and unnamed resources plus preservation manifest')
    extracting.add_argument('archive', type=Path)
    extracting.add_argument('outdir', type=Path)
    building = subs.add_parser('build', help='Repack an extraction, applying nested edits')
    building.add_argument('indir', type=Path)
    building.add_argument('archive', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'extract':
            extract(args.archive, args.outdir)
        elif args.command == 'build':
            build(args.indir, args.archive)
        else:
            m = parse_archive(args.archive.read_bytes())
            if args.json:
                print(json.dumps(m, indent=2))
            else:
                children = {c: g['parent'] for g in m['relations'] for c in g['children']}
                print('id\toffset\tdecoded\tstored\tcodec\trole')
                for r in m['entries']:
                    role = f"member of {children[r['id']]}" if r['id'] in children else 'physical'
                    print(f"{r['id']}\t{r['offset']:#x}\t{r['size']}\t{r['stored_size']}\t"
                          f"{'LZ11' if r['compressed'] else 'raw'}\t{role}")
    except (ValueError, OSError, struct.error, UnicodeError, KeyError) as exc:
        parser.exit(2, f'fl_archive: {exc}\n')


if __name__ == '__main__':
    main()
