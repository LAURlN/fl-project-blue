#!/usr/bin/env python3
"""Read-only, key-free NCSD/NCCH extraction and static inventory (Python 3.10+).

Format references (not runtime dependencies):
https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/exheader.h
https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/romfs.h
https://github.com/3DSGuy/Project_CTR/blob/master/ctrtool/deps/libnintendo-n3ds/include/ntd/n3ds/exheader.h
https://github.com/3DSGuy/Project_CTR/blob/master/ctrtool/src/lzss.c

No decryption, key discovery, execution, or recompiler functionality is provided.
All populated NCCH flags are checked before any output directory is created.
"""

import argparse
from collections import Counter
import hashlib
import json
import mmap
from pathlib import Path
import re
import struct


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unpack(fmt, data, offset=0):
    return struct.unpack_from('<' + fmt, data, offset)


def align(value, alignment):
    return (value + alignment - 1) & -alignment


def digest(data, start, size):
    require(0 <= start <= start + size <= len(data), 'Hash range outside input')
    h = hashlib.sha256()
    for pos in range(start, start + size, 4 * 1024 * 1024):
        h.update(data[pos:min(pos + 4 * 1024 * 1024, start + size)])
    return h.hexdigest()


def write_range(data, start, size, target):
    expected = digest(data, start, size)
    target.parent.mkdir(parents=True, exist_ok=True)
    require(not target.is_symlink(), f'Refusing output symlink: {target}')
    with target.open('wb') as f:
        for pos in range(start, start + size, 4 * 1024 * 1024):
            f.write(data[pos:min(pos + 4 * 1024 * 1024, start + size)])
    with target.open('rb') as f:
        verification = hashlib.sha256()
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            verification.update(block)
        actual = verification.hexdigest()
    require(actual == expected, f'Extracted file hash mismatch: {target}')
    return expected


def checked_name(raw, encoding):
    name = raw.decode(encoding)
    require(name not in ('', '.', '..') and '/' not in name and '\\' not in name
            and '\0' not in name, f'Unsafe entry name: {name!r}')
    return name


def parse_ncsd(data):
    require(data[0x100:0x104] == b'NCSD', 'Not an NCSD image')
    # NCSD media-unit exponent: flags[6]. NCCH uses its own flags[6].
    unit = 0x200 << data[0x18e]
    result = dict(file_size=len(data), media_id=f'{unpack("Q", data, 0x108)[0]:016x}',
                  media_unit=unit, media_size=unpack('I', data, 0x104)[0] * unit,
                  flags=data[0x188:0x190].hex(' '), partitions=[])
    for index in range(8):
        offset, size = unpack('II', data, 0x120 + 8 * index)
        if not size:
            continue
        base, size = offset * unit, size * unit
        require(base >= 0x200 and base + size <= len(data), 'Partition outside dump')
        require(data[base + 0x100:base + 0x104] == b'NCCH', 'Non-NCCH partition')
        h = data[base:base + 0x200]
        flags = h[0x188:0x190]
        ncch_unit = 0x200 << flags[6]
        p = dict(index=index, offset=base, size=size,
                 fs_type=data[0x110 + index], ncsd_crypto_type=data[0x118 + index],
                 partition_id=f'{unpack("Q", h, 0x108)[0]:016x}',
                 program_id=f'{unpack("Q", h, 0x118)[0]:016x}',
                 maker_code=h[0x110:0x112].decode('ascii'),
                 format_version=unpack('H', h, 0x112)[0],
                 product_code=h[0x150:0x160].rstrip(b'\0').decode('ascii'),
                 flags=flags.hex(' '), flags7=flags[7], crypto_method=flags[3],
                 no_crypto=bool(flags[7] & 4), media_unit=ncch_unit,
                 content_size=unpack('I', h, 0x104)[0] * ncch_unit,
                 exheader_size=unpack('I', h, 0x180)[0], sections={})
        require(p['content_size'] <= size, 'NCCH extends beyond NCSD partition')
        for name, pos in [('plain', 0x190), ('logo', 0x198), ('exefs', 0x1a0), ('romfs', 0x1b0)]:
            a, b = unpack('II', h, pos)
            require(a * ncch_unit + b * ncch_unit <= p['content_size'],
                    f'{name} exceeds NCCH')
            p['sections'][name] = dict(offset=a * ncch_unit, size=b * ncch_unit)
        result['partitions'].append(p)
    ranges = sorted((p['offset'], p['offset'] + p['size']) for p in result['partitions'])
    require(all(a[1] <= b[0] for a, b in zip(ranges, ranges[1:])), 'Overlapping partitions')
    return result


def decode_kernel(raw):
    result = dict(raw=[f'0x{x:08x}' for x in raw], syscalls=[], mappings=[], interrupts=[])
    pending = None
    for x in raw:
        prefix = 32 - ((~x) & 0xffffffff).bit_length()
        if prefix == 32:
            continue
        if prefix == 4:
            result['syscalls'].extend(f'0x{((x >> 24) & 7) * 24 + bit:02x}'
                                      for bit in range(24) if x & (1 << bit))
        elif prefix == 3:
            result['interrupts'].extend((x >> shift) & 127 for shift in (0, 7, 14, 21)
                                        if (x >> shift) & 127)
        elif prefix == 6:
            result['release_kernel_version'] = f'{(x >> 8) & 255}.{x & 255}'
        elif prefix == 7:
            result['handle_table_size'] = x & 0xffff
        elif prefix == 8:
            names = ['allow_debug', 'force_debug', 'allow_non_alphanumeric',
                     'write_shared_page', 'privileged_priority', 'main_arguments',
                     'share_device_memory', 'runnable_on_sleep']
            result['other_capabilities'] = {name: bool(x & (1 << i)) for i, name in enumerate(names)}
            result['other_capabilities'].update(memory_type=(x >> 8) & 15,
                                                special_memory_layout=bool(x & 0x1000),
                                                access_core2=bool(x & 0x2000))
        elif prefix == 9:
            if pending is None:
                pending = x
            else:
                result['mappings'].append(dict(start=(pending & 0xfffff) << 12,
                                               end_exclusive=(x & 0xfffff) << 12,
                                               read_only=bool(pending & 0x100000),
                                               kind='static' if x & 0x100000 else 'io'))
                pending = None
        elif prefix == 11:
            result['mappings'].append(dict(start=(x & 0xfffff) << 12,
                                           end_exclusive=((x & 0xfffff) + 1) << 12,
                                           read_only=False, kind='io'))
        else:
            result.setdefault('unknown', []).append(f'0x{x:08x}')
    require(pending is None, 'Unpaired kernel mapping descriptor')
    return result


def parse_exheader(h):
    require(len(h) >= 0x400, 'Truncated exheader')
    result = dict(name=h[:8].rstrip(b'\0').decode('ascii'), sci_flags=h[0xd],
                  compressed_code=bool(h[0xd] & 1), sd_application=bool(h[0xd] & 2),
                  remaster_version=unpack('H', h, 0xe)[0], segments={},
                  stack_size=unpack('I', h, 0x1c)[0], bss_size=unpack('I', h, 0x3c)[0],
                  dependencies=[f'{x:016x}' for x in unpack('48Q', h, 0x40) if x],
                  save_data_size=unpack('Q', h, 0x1c0)[0], jump_id=f'{unpack("Q", h, 0x1c8)[0]:016x}',
                  program_id=f'{unpack("Q", h, 0x200)[0]:016x}',
                  core_version=unpack('I', h, 0x208)[0],
                  core_flags_raw=h[0x20c:0x210].hex(' '),
                  new3ds_enable_l2_cache=bool(h[0x20c] & 1),
                  new3ds_804mhz=bool(h[0x20c] & 2), new3ds_system_mode=h[0x20d] & 15,
                  old3ds_system_mode=h[0x20e] >> 4, ideal_processor=h[0x20e] & 3,
                  affinity_mask=(h[0x20e] >> 2) & 3, priority=h[0x20f],
                  resource_limits=list(unpack('16H', h, 0x210)),
                  extdata_id=f'{unpack("Q", h, 0x230)[0]:016x}',
                  system_savedata_ids=list(unpack('II', h, 0x238)),
                  accessible_savedata_raw=f'{unpack("Q", h, 0x240)[0]:016x}',
                  filesystem_access_raw=h[0x248:0x24f].hex(' '), storage_attributes=h[0x24f],
                  services=[h[o:o + 8].rstrip(b'\0').decode('ascii') for o in range(0x250, 0x360, 8)
                            if h[o:o + 8].strip(b'\0')],
                  resource_limit_category=h[0x36f], kernel=decode_kernel(unpack('28I', h, 0x370)),
                  arm9_access_control=h[0x3f0:0x3ff].hex(' '), arm9_descriptor_version=h[0x3ff])
    file_offset = 0
    for name, pos in [('text', 0x10), ('rodata', 0x20), ('data', 0x30)]:
        address, pages, size = unpack('III', h, pos)
        result['segments'][name] = dict(address=address, pages=pages, size=size,
                                       allocated_size=pages * 0x1000, code_file_offset=file_offset)
        require(size <= pages * 0x1000, f'{name} exceeds page allocation')
        file_offset += pages * 0x1000
    return result


def decompress_blz(source):
    """Decode backward LZ with strict source, destination, and trailer bounds."""
    require(len(source) >= 8, 'BLZ trailer missing')
    footer, growth = unpack('II', source, len(source) - 8)
    header_size, compressed_span = footer >> 24, footer & 0xffffff
    require(8 <= header_size <= compressed_span <= len(source), 'Invalid BLZ trailer')
    require(0 < growth <= 128 * 1024 * 1024, 'Unreasonable BLZ output size')
    stop = len(source) - compressed_span
    src, dst = len(source) - header_size, len(source) + growth
    out = bytearray(source) + bytearray(growth)
    while src > stop:
        src -= 1
        control = source[src]
        for bit in range(7, -1, -1):
            if src <= stop:
                break
            if control & (1 << bit):
                require(src - 2 >= stop, 'BLZ backreference outside source')
                src -= 2
                token = unpack('H', source, src)[0]
                length, distance = (token >> 12) + 3, (token & 0xfff) + 3
                require(dst - length >= stop, 'BLZ backreference outside destination')
                for _ in range(length):
                    dst -= 1
                    require(dst + distance < len(out), 'BLZ reference past output')
                    out[dst] = out[dst + distance]
            else:
                src -= 1
                dst -= 1
                require(dst >= stop, 'BLZ literal outside destination')
                out[dst] = source[src]
    require(src == dst == stop, 'BLZ input/output boundary mismatch')
    return bytes(out)


def extract_exefs(data, p, target, exheader):
    s = p['sections']['exefs']
    base = p['offset'] + s['offset']
    h = data[base:base + 0x200]
    write_range(data, base, 0x200, target / 'header.bin')
    entries = []
    for i in range(10):
        raw_name = h[i * 16:i * 16 + 8].rstrip(b'\0')
        if not raw_name:
            continue
        name = checked_name(raw_name, 'ascii')
        offset, size = unpack('II', h, i * 16 + 8)
        require(offset + 0x200 + size <= s['size'], 'ExeFS entry out of range')
        expected = h[0x1e0 - i * 32:0x200 - i * 32].hex()
        require(digest(data, base + 0x200 + offset, size) == expected, f'ExeFS hash: {name}')
        output_name = 'code.compressed.bin' if name == '.code' and exheader['compressed_code'] else 'code.bin' if name == '.code' else name + '.bin'
        sha = write_range(data, base + 0x200 + offset, size, target / output_name)
        entry = dict(name=name, offset=offset, size=size, sha256=sha, output=output_name)
        if name == '.code' and exheader['compressed_code']:
            code = decompress_blz(data[base + 0x200 + offset:base + 0x200 + offset + size])
            (target / 'code.bin').write_bytes(code)
            entry.update(decompressed_size=len(code), decompressed_sha256=hashlib.sha256(code).hexdigest())
        entries.append(entry)
    return entries


def extract_romfs(data, p, target):
    s = p['sections']['romfs']
    base = p['offset'] + s['offset']
    require(data[base:base + 4] == b'IVFC', 'RomFS IVFC magic missing')
    master_size = unpack('I', data, base + 8)[0]
    levels = []
    for i in range(3):
        offset, size, log2 = unpack('QQI', data, base + 0xc + i * 0x18)
        require(9 <= log2 <= 20, 'Invalid IVFC block size')
        levels.append(dict(logical_offset=offset, size=size, block_log2=log2))
    # Level 3 is stored first, after the aligned IVFC header and master hashes.
    lv3_offset = align(0x60 + master_size, 1 << levels[2]['block_log2'])
    require(lv3_offset + levels[2]['size'] <= s['size'], 'IVFC level 3 outside RomFS')
    lv3 = base + lv3_offset
    fields = unpack('10I', data, lv3)
    require(fields[0] == 0x28, 'Invalid RomFS level-3 header')
    _, dh_off, dh_size, dt_off, dt_size, fh_off, fh_size, ft_off, ft_size, data_off = fields
    for offset, size in [(dh_off, dh_size), (dt_off, dt_size), (fh_off, fh_size), (ft_off, ft_size)]:
        require(offset >= 0x28 and offset + size <= levels[2]['size'], 'RomFS metadata outside level 3')
    require(data_off == align(ft_off + ft_size, 16), 'RomFS data offset mismatch')
    files, dirs, seen_files, seen_dirs = [], [], set(), set()
    target.mkdir(parents=True, exist_ok=True)

    def visit(entry_offset, parent):
        require(entry_offset not in seen_dirs, 'RomFS directory cycle')
        seen_dirs.add(entry_offset)
        require(entry_offset + 24 <= dt_size, 'Directory record out of range')
        pos = lv3 + dt_off + entry_offset
        _, sibling, child, first_file, _, name_len = unpack('6I', data, pos)
        require(entry_offset + 24 + name_len <= dt_size, 'Directory name out of range')
        name = checked_name(data[pos + 24:pos + 24 + name_len], 'utf-16le') if entry_offset else ''
        path = parent / name if name else parent
        (target / path).mkdir(parents=True, exist_ok=True)
        dirs.append(path.as_posix())
        off = first_file
        while off != 0xffffffff:
            require(off not in seen_files and off + 32 <= ft_size, 'Invalid/cyclic file record')
            seen_files.add(off)
            pos = lv3 + ft_off + off
            _, nxt, content_off, size, _, name_len = unpack('IIQQII', data, pos)
            require(off + 32 + name_len <= ft_size, 'File name outside metadata')
            name = checked_name(data[pos + 32:pos + 32 + name_len], 'utf-16le')
            require(data_off + content_off + size <= levels[2]['size'], 'File outside RomFS data')
            rel = path / name
            sha = write_range(data, lv3 + data_off + content_off, size, target / rel)
            magic = data[lv3 + data_off + content_off:lv3 + data_off + content_off + min(4, size)]
            probe = data[lv3 + data_off + content_off + 0x80:lv3 + data_off + content_off + 0x84] if size >= 0x84 else b''
            files.append(dict(path=rel.as_posix(), size=size, sha256=sha, magic4=magic.hex(),
                              cro_crr_magic_at_0x80=probe.decode('ascii') if probe in (b'CRO0', b'CRR0') else None))
            off = nxt
        off = child
        while off != 0xffffffff:
            off = visit(off, path)
        return sibling

    visit(0, Path())
    ext = Counter(Path(f['path']).suffix.lower() or '<none>' for f in files)
    magic = Counter(f['magic4'] for f in files)
    compounds = Counter(''.join(Path(f['path']).suffixes).lower() or '<none>' for f in files)
    dynamic = dict(by_extension=[f['path'] for f in files if Path(f['path']).suffix.lower() in ('.cro', '.crr')],
                   by_magic_at_0x80=[f['path'] for f in files if f['cro_crr_magic_at_0x80']],
                   raw_archive_magic_counts={})
    # A raw signature scan is only a heuristic; compressed members may hide it.
    for entry in files:
        if Path(entry['path']).name != '_file_archive.bin':
            continue
        counts = {'CRO0': 0, 'CRR0': 0}
        archive = target / entry['path']
        if archive.stat().st_size:
            with archive.open('rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as content:
                for signature in (b'CRO0', b'CRR0'):
                    count, position = 0, 0
                    while True:
                        position = content.find(signature, position)
                        if position == -1:
                            break
                        count += 1
                        position += 1
                    counts[signature.decode()] = count
        dynamic['raw_archive_magic_counts'][entry['path']] = counts
    return dict(ivfc_levels=levels, level3_physical_offset=lv3_offset, directories=dirs,
                file_count=len(files), total_size=sum(f['size'] for f in files),
                extensions=dict(ext.most_common()), compound_extensions=dict(compounds.most_common()),
                magic4_histogram=dict(magic.most_common()), dynamic_modules=dynamic, files=files)


def scan_code(path, target, exheader):
    code = path.read_bytes()
    expected = sum(s['allocated_size'] for s in exheader['segments'].values())
    require(len(code) == expected, f'Code size {len(code)} differs from exheader allocation {expected}')
    pattern = re.compile(r'NintendoWare|NW4C|NW4F|Nintendo|Level.?5|FLLINK|Mobiclip|NEX|PIA|'
                         r'N2nw|N2nn|N2ds|cLib|cFwk|\d{4}/\d{1,2}/\d{1,2}|'
                         r'\bCRI\b|CriWare|ADX|HCA|nn::|nw::|\bSDK\b|CTR_SDK|zlib|'
                         r'GCC|ARM C|RVCT|version|[A-Za-z]:[\\/]|[\\/][\w.-]+\.(?:cpp|c|h)\b', re.I)
    strings, evidence = [], []
    for m in re.finditer(rb'[\x20-\x7e]{6,}', code):
        value = m.group().decode('ascii')
        entry = dict(file_offset=m.start(), text=value)
        for s in exheader['segments'].values():
            if s['code_file_offset'] <= m.start() < s['code_file_offset'] + s['size']:
                entry['virtual_address'] = s['address'] + m.start() - s['code_file_offset']
        strings.append(entry)
        if pattern.search(value):
            evidence.append(entry)
    # Wide strings are reported separately; ASCII offsets above are byte-exact.
    wide = []
    for m in re.finditer(rb'(?:[\x20-\x7e]\x00){6,}', code):
        value = m.group().decode('utf-16le')
        if pattern.search(value):
            wide.append(dict(file_offset=m.start(), text=value))
    target.mkdir(parents=True, exist_ok=True)
    for name, rows in [('code-strings.tsv', strings), ('code-evidence.tsv', evidence)]:
        (target / name).write_text('file_offset\tvirtual_address\ttext\n' + ''.join(
            f'0x{r["file_offset"]:08x}\t{hex(r["virtual_address"]) if "virtual_address" in r else ""}\t{r["text"]}\n'
            for r in rows), encoding='utf-8')
    return dict(size=len(code), sha256=hashlib.sha256(code).hexdigest(), ascii_strings=len(strings),
                evidence=evidence, wide_evidence=wide)


def json_text(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def extract(data, layout, output):
    output.mkdir(parents=True, exist_ok=True)
    write_range(data, 0, 0x200, output / 'ncsd-header.bin')
    for p in layout['partitions']:
        name = {0: '.', 1: 'manual', 2: 'download_play', 6: 'update_n3ds', 7: 'update_o3ds'}.get(p['index'], f'partition_{p["index"]}')
        target = output / name
        p['output_directory'] = name
        target.mkdir(parents=True, exist_ok=True)
        base = p['offset']
        write_range(data, base, 0x200, target / 'ncch-header.bin')
        checks = {}
        if p['exheader_size']:
            require(p['exheader_size'] == 0x400, 'Unsupported exheader size')
            checks['exheader_sha256'] = digest(data, base + 0x200, 0x400)
            require(checks['exheader_sha256'] == data[base + 0x160:base + 0x180].hex(), 'Exheader hash mismatch')
            write_range(data, base + 0x200, 0x800, target / 'exheader.bin')
            write_range(data, base + 0x200, 0x400, target / 'exheader-info.bin')
            p['exheader'] = parse_exheader(data[base + 0x200:base + 0xa00])
            (target / 'exheader.txt').write_text(json_text(p['exheader']), encoding='utf-8')
        for section in ('plain', 'logo'):
            s = p['sections'][section]
            if s['size']:
                sha = write_range(data, base + s['offset'], s['size'], target / (section + '.bin'))
                if section == 'logo':
                    require(sha == data[base + 0x130:base + 0x150].hex(), 'Logo hash mismatch')
                    checks['logo_sha256'] = sha
                else:
                    p['plain_strings'] = [m.group().decode('ascii') for m in re.finditer(rb'[\x20-\x7e]{6,}', data[base + s['offset']:base + s['offset'] + s['size']])]
        for section, pos, hash_pos in [('exefs', 0x1a8, 0x1c0), ('romfs', 0x1b8, 0x1e0)]:
            s = p['sections'][section]
            if not s['size']:
                continue
            hash_size = unpack('I', data, base + pos)[0] * p['media_unit']
            require(0 < hash_size <= s['size'], 'Invalid NCCH hashed region size')
            sha = digest(data, base + s['offset'], hash_size)
            require(sha == data[base + hash_pos:base + hash_pos + 32].hex(), f'{section} superblock hash mismatch')
            checks[section + '_superblock_sha256'] = sha
            checks[section + '_superblock_hash_size'] = hash_size
        if p['sections']['exefs']['size']:
            p['exefs'] = extract_exefs(data, p, target / 'exefs', p['exheader'])
            p['code'] = scan_code(target / 'exefs/code.bin', target / 'analysis', p['exheader'])
        if p['sections']['romfs']['size']:
            p['romfs'] = extract_romfs(data, p, target / 'romfs')
            (target / 'romfs-manifest.json').write_text(json_text(p['romfs']), encoding='utf-8')
        p['verified_hashes'] = checks
        print(f'Partition {p["index"]}: extracted to {target}; ' +
              (f'{p["romfs"]["file_count"]} RomFS files' if 'romfs' in p else 'no RomFS'), flush=True)
    (output / 'analysis.json').write_text(json_text(layout), encoding='utf-8')
    # info.txt is complete readable structured text; the committed Markdown report
    # adds interpretation without committing any extracted assets or strings dump.
    (output / 'info.txt').write_text('Fantasy Life EU — Phase 0 dump analysis\n\n' + json_text(layout), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump', type=Path)
    parser.add_argument('--output', type=Path, default=Path('extracted/fl_eu'))
    parser.add_argument('--inspect-only', action='store_true')
    args = parser.parse_args()
    source, output = args.dump.resolve(), args.output.resolve()
    require(source.parent != output and source.parent not in output.parents and output not in source.parents,
            'Output must be separate from input directory')
    require(not args.output.is_symlink(), 'Output must not be a symlink')
    # Existing nonempty destinations may contain stale files or symlinked subdirs.
    require(args.inspect_only or not output.exists() or not any(output.iterdir()),
            'Output already contains files; choose a fresh output directory')
    with source.open('rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        layout = parse_ncsd(data)
        layout['source'] = str(args.dump)
        print(json_text(layout), flush=True)
        if any(not p['no_crypto'] for p in layout['partitions']):
            print('ENCRYPTED NCCH CONTENT: stopped; no extraction or decryption attempted.')
            return 2
        print('All populated NCCH partitions have NoCrypto set.', flush=True)
        if args.inspect_only:
            return 0
        layout['source_sha256'] = digest(data, 0, len(data))
        extract(data, layout, output)
        require(digest(data, 0, len(data)) == layout['source_sha256'], 'Source changed during extraction')
        print('Verified: source SHA-256 unchanged; NCCH region hashes, ExeFS file hashes, '
              'and all extracted file bytes match. RSA signatures and full IVFC tree not checked.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
