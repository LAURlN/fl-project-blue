#!/usr/bin/env python3
"""Verify an fl_archive extraction and inventory entry, nested and SCR formats.

Writes private metadata under .fl_archive, never copies text/dialogue into a repo.
Usage: python3 -I tools/fl_archive_catalog.py extracted/fl_eu/archive
"""
import argparse
from collections import Counter
import csv
import importlib.util
import json
from pathlib import Path
import struct

# Explicit local source load works under python3 -I (which omits script sys.path).
spec = importlib.util.spec_from_file_location('fl_archive', Path(__file__).with_name('fl_archive.py'))
fl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fl)


def scr_tables(data):
    """Return section-relative row metadata; do not infer column semantics."""
    sections = [(0, data)]
    if data[:8] == b'\x02\0\0\0\x10\0\0\0':
        offsets = list(struct.unpack_from('<3I', data, 4))
        fl.require(offsets[0] == 16 and offsets == sorted(offsets) and offsets[-1] == len(data),
                   'Invalid two-section SCR wrapper')
        sections = [(offsets[i], data[offsets[i]:offsets[i + 1]]) for i in range(2)]
    result = []
    for base, section in sections:
        if section[:4] != b'\x13\x80\x03\x1d':
            continue
        info = fl.u32(section, 20)
        count, width, offset = struct.unpack('<3I', fl.span(section, info, 12))
        fl.require((width > 0 or count == 0) and count < 1000000, 'Invalid SCR rows')
        fl.span(section, offset, count * width)
        result.append(dict(section=base, rows=count, row_size=width, table_offset=offset))
    return result


def catalog(root):
    meta = fl.safe_path(root, fl.META + '/manifest.json')
    manifest = json.loads(meta.read_text())
    paths, nested_kinds = {}, Counter()
    for r in manifest['entries']:
        paths[r['path']] = dict(id=r['id'], scope='entry', sha256=r['sha256'])

    def walk(nested):
        nested_kinds[nested['kind']] += 1
        for r in nested['members']:
            paths.setdefault(r['path'], dict(id='', scope='nested', sha256=r['sha256']))
            if 'nested' in r:
                walk(r['nested'])
    for r in manifest['entries']:
        if 'nested' in r:
            walk(r['nested'])
    counts, sizes, magics, exts, extra_magics, joint = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    rows, scripts, combined_ext = [], [], Counter()
    unsupported_scr = []
    for name, r in sorted(paths.items()):
        data = fl.safe_path(root, name).read_bytes()
        fl.require(fl.sha(data) == r['sha256'], f'Extraction hash mismatch: {name}')
        magic = data[:4].hex()
        ext = Path(name).suffix or '(none)'
        combined_ext[ext] += 1
        if r['scope'] == 'entry':
            top = name.split('/')[0]
            counts[top] += 1
            sizes[top] += len(data)
            magics[magic] += 1
            exts[ext] += 1
            joint[(ext, magic)] += 1
        else:
            extra_magics[magic] += 1
        rows.append([r['id'], r['scope'], name, len(data), magic, r['sha256']])
        if magic in ('1380031d', '02000000'):
            try:
                tables = scr_tables(data)
            except (ValueError, struct.error) as exc:
                unsupported_scr.append(dict(path=name, reason=str(exc)))
                tables = []
            for table in tables:
                scripts.append([r['id'], name, table['section'], table['rows'], table['row_size'], table['table_offset']])
    target = root / fl.META
    for filename, header, records in [
        ('entries.tsv', ['id', 'scope', 'path', 'size', 'magic', 'sha256'], rows),
        ('scr-tables.tsv', ['id', 'path', 'section', 'rows', 'row_size', 'table_offset'], scripts)]:
        with (target / filename).open('w', newline='') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(header)
            writer.writerows(records)
    physical = [manifest['entries'][i] for i in manifest['physical_ids']]
    report = dict(archive_sha256=manifest['archive_sha256'], entries=manifest['count'],
                  physical=len(physical), virtual=manifest['count'] - len(physical),
                  physical_decoded_bytes=sum(r['size'] for r in physical),
                  physical_stored_bytes=sum(r['stored_size'] for r in physical),
                  logical_decoded_bytes=sum(r['size'] for r in manifest['entries']),
                  compression=dict(Counter('LZ11' if r['compressed'] else 'raw' for r in physical)),
                  directories={k: dict(files=counts[k], bytes=sizes[k]) for k in sorted(counts)},
                  extensions=dict(exts.most_common()), magics=dict(magics.most_common()),
                  extension_magics=[dict(extension=e, magic=m, files=n) for (e, m), n in joint.most_common()],
                  nested_containers=dict(nested_kinds), nested_extra_files=sum(extra_magics.values()),
                  nested_extra_magics=dict(extra_magics.most_common()),
                  all_payload_files=len(paths), all_payload_bytes=sum(r[3] for r in rows),
                  scr_sections=len(scripts), unsupported_scr=unsupported_scr, scr_shapes=[dict(rows=n, row_size=w, files=c)
                      for (n, w), c in Counter((r[3], r[4]) for r in scripts).most_common()])
    (target / 'catalog.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('scr_shapes', 'extension_magics')}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    catalog(args.directory)
