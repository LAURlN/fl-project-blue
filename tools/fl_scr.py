#!/usr/bin/env python3
"""Lossless Fantasy Life SCR table editor (Python 3.10+, standard library).

JSON retains a base64 preservation image; edit sections[*].rows, not that image.
Strings are plain text or a list of text and {"control": "hex bytes"} tokens.
CSV is a readable export; build consumes JSON. See docs/phase1b-data-tables.md.
"""
import argparse
import base64
import csv
import functools
import json
from pathlib import Path
import re
import struct

MAGIC = bytes.fromhex('1380031d')
TYPES = {1: ('u8', 1), 2: ('u16', 2), 3: ('u32', 4),
         5: ('ascii', 4), 6: ('utf16', 4), 7: ('resource', 4),
         9: ('pointer', 4), 10: ('utf16', 4)}


def require(test, message):
    if not test:
        raise ValueError(message)


def span(data, offset, size):
    require(0 <= offset <= len(data) and 0 <= size <= len(data) - offset,
            f'Out of bounds: {offset:#x}+{size:#x} / {len(data):#x}')
    return data[offset:offset + size]


def u32(data, offset):
    return struct.unpack('<I', span(data, offset, 4))[0]


def read_string(data, offset, ascii_=False):
    """Length-prefixed controls may contain NULs; never NUL-scan their payloads."""
    require(offset < len(data), 'String pointer outside section')
    if ascii_:
        end = data.find(b'\0', offset)
        require(end >= 0, 'Unterminated ASCII string')
        return data[offset:end].decode('ascii')
    pos, text, tokens = offset, bytearray(), []
    def flush():
        if text:
            tokens.append(bytes(text).decode('utf-16le', errors='surrogatepass'))
            text.clear()
    while True:
        unit = span(data, pos, 2)
        if unit == b'\0\0':
            flush()
            return ''.join(tokens) if all(isinstance(x, str) for x in tokens) else tokens
        if unit == b'\xff\xff':
            flush()
            tokens.append({'control': 'ffff'})
            pos += 2
        elif 0xe0 <= data[pos] <= 0xfe and span(data, pos, 4)[1:] == b'\xff\xff\xff':
            flush()
            size = u32(data, pos + 4)
            require(size >= 4 and size % 2 == 0, 'Invalid FL control length')
            raw = span(data, pos, 4 + size)
            tokens.append({'control': raw.hex()})
            pos += len(raw)
        else:
            text.extend(unit)
            pos += 2


def write_string(value, ascii_=False):
    if ascii_:
        require(isinstance(value, str) and '\0' not in value, 'Invalid ASCII string')
        return value.encode('ascii') + b'\0'
    tokens = [value] if isinstance(value, str) else value
    require(isinstance(tokens, list), 'UTF-16 string must be text or token list')
    out = bytearray()
    for token in tokens:
        if isinstance(token, str):
            require('\0' not in token and '\uffff' not in token, 'Use control tokens for U+FFFF; NUL ends a string')
            out.extend(token.encode('utf-16le', errors='surrogatepass'))
        else:
            require(isinstance(token, dict) and set(token) == {'control'}, 'Invalid string token')
            raw = bytes.fromhex(token['control'])
            require(raw == b'\xff\xff' or (len(raw) >= 8 and raw[1:4] == b'\xff\xff\xff'
                    and u32(raw, 4) >= 4 and len(raw) == 4 + u32(raw, 4)
                    and len(raw) % 2 == 0), 'Invalid control record')
            out.extend(raw)
    return bytes(out) + b'\0\0'


def layout(data):
    require(span(data, 0, 4) == MAGIC, 'Not a table SCR section')
    require(len(data) >= 32 and u32(data, 12) == len(data) - 32, 'SCR size mismatch')
    columns, info = [], u32(data, 20)
    require(u32(data, 16) == 32, 'Unsupported column table offset')
    count, width, rows = struct.unpack('<3I', span(data, info, 12))
    require(count <= 1000000 and (width or not count), 'Invalid row dimensions')
    span(data, rows, count * width)
    require(rows >= info + 12 and info >= 32 + data[9] * 6, 'Overlapping SCR metadata')
    for i in range(data[9]):
        type_, array, bits, encoded = struct.unpack('<BBHH', span(data, 32 + i * 6, 6))
        require(type_ in TYPES and array > 0, f'Unsupported SCR type {type_}')
        name, size = TYPES[type_]
        offset, shift = encoded >> 5, encoded & 31
        require(not bits or type_ in (1, 2, 3), 'Bit field on noninteger')
        require(not bits or (array == 1 and bits + shift <= size * 8), 'Invalid bit field')
        require(bits or shift == 0, 'Unexpected bit offset')
        require(offset + size * array <= width, 'Column extends past row')
        columns.append(dict(name=f'c{i:02d}', type=name, type_id=type_, offset=offset,
                            count=array, bits=bits, shift=shift))
    return dict(info=info, count=count, width=width, rows=rows, columns=columns)


@functools.lru_cache(maxsize=1)
def schemas():
    """All schemas in tools/schemas/, keyed by archive resource ID."""
    by_id = {}
    for path in sorted(Path(__file__).with_name('schemas').glob('*.json')):
        schema = json.loads(path.read_text(encoding='utf-8'))
        for id_ in schema['resource_ids']:
            require(id_ not in by_id, f'Resource {id_} is claimed by two schemas')
            by_id[id_] = schema
    return by_id


def schema_for(resource_id):
    return schemas().get(resource_id)


def plain(value):
    """Flatten a string cell (text or token list) to its visible text."""
    if isinstance(value, str):
        return value
    return ''.join(token for token in value if isinstance(token, str))


def decode_section(data, schema=None):
    if data[:4] != MAGIC:
        return dict(kind='opaque', original=base64.b64encode(data).decode())
    meta = layout(data)
    columns = meta['columns']
    if schema:
        require(schema['row_size'] == meta['width'] and len(schema['columns']) == len(columns),
                f'Schema {schema["name"]} does not match this table layout')
        for col, entry in zip(columns, schema['columns']):
            require(all(col[k] == entry[k] for k in ('type_id', 'offset', 'count', 'bits', 'shift')),
                    f'Schema {schema["name"]} column {entry["name"]} disagrees with the file')
            col.update({k: v for k, v in entry.items() if k in ('name', 'confidence', 'note')})
    rows, cache = [], {}
    for index in range(meta['count']):
        raw = span(data, meta['rows'] + index * meta['width'], meta['width'])
        row = {'_raw': raw.hex()}
        for col in columns:
            size = TYPES[col['type_id']][1]
            values = []
            for j in range(col['count']):
                val = int.from_bytes(raw[col['offset'] + j * size:col['offset'] + (j + 1) * size], 'little')
                if col['bits']:
                    val = val >> col['shift'] & ((1 << col['bits']) - 1)
                elif col['type_id'] in (5, 6, 10):
                    key = (val, col['type_id'] == 5)
                    if key not in cache:
                        cache[key] = read_string(data, *key)
                    val = cache[key]
                elif col['type_id'] == 9:
                    require(val < len(data), 'Nested pointer outside section')
                    val = {'offset': val}
                values.append(val)
            row[col['name']] = values[0] if col['count'] == 1 else values
        rows.append(row)
    return dict(kind='table', original=base64.b64encode(data).decode(), row_size=meta['width'],
                columns=columns, rows=rows)


def dump(data, resource_id=None):
    if data[:4] == MAGIC:
        sections, wrapper = [data], False
    else:
        require(span(data, 0, 8) == bytes.fromhex('0200000010000000'), 'Unsupported SCR magic')
        a, b, end = struct.unpack('<3I', span(data, 4, 12))
        require(a <= b <= end == len(data), 'Invalid two-section wrapper offsets')
        sections, wrapper = [data[a:b], data[b:end]], True
    schema = schema_for(resource_id) if resource_id is not None else None
    return dict(format='fl-scr-v1', resource_id=resource_id, wrapper=wrapper,
                sections=[decode_section(s, schema if i == 0 else None) for i, s in enumerate(sections)])


def build_section(section):
    original = base64.b64decode(section['original'], validate=True)
    if section['kind'] == 'opaque':
        return original
    require(section['kind'] == 'table', 'Unknown section kind')
    meta = layout(original)
    columns, rows = section['columns'], section['rows']
    require(len(columns) == len(meta['columns']) and section['row_size'] == meta['width'], 'Schema layout changed')
    for a, b in zip(columns, meta['columns']):
        require(all(a[k] == b[k] for k in ('type', 'type_id', 'offset', 'count', 'bits', 'shift')), 'Column layout changed')
    names = [c['name'] for c in columns]
    require(len(set(names)) == len(names) and '_raw' not in names, 'Duplicate/reserved column name')
    out, encoded_rows, pool = bytearray(original), bytearray(), {}
    for row in rows:
        require(set(row) - {'_raw'} == set(names), 'Missing or unknown row column')
        raw = bytearray.fromhex(row['_raw']) if '_raw' in row else bytearray(meta['width'])
        require(len(raw) == meta['width'], 'Wrong raw row width')
        for col in columns:
            size, offset = TYPES[col['type_id']][1], col['offset']
            values = [row[col['name']]] if col['count'] == 1 else row[col['name']]
            require(isinstance(values, list) and len(values) == col['count'], 'Wrong column array length')
            for j, val in enumerate(values):
                pos = offset + j * size
                previous = int.from_bytes(raw[pos:pos + size], 'little')
                if col['type_id'] in (5, 6, 10):
                    string = write_string(val, col['type_id'] == 5)
                    # Retain aliases, suffix-sharing, padding and control bytes when unchanged.
                    if '_raw' in row and previous < len(original) and \
                            read_string(original, previous, col['type_id'] == 5) == val:
                        val = previous
                    else:
                        if string not in pool:
                            alignment = 1 if col['type_id'] == 5 else 4
                            out.extend(b'\0' * (-len(out) % alignment))
                            pool[string] = len(out)
                            out.extend(string)
                        val = pool[string]
                elif col['type_id'] == 9:
                    require(isinstance(val, dict) and set(val) == {'offset'}, 'Invalid opaque pointer')
                    val = val['offset']
                    require(isinstance(val, int) and 0 <= val < len(original), 'Pointer outside preserved section')
                limit = col['bits'] or size * 8
                require(type(val) is int and 0 <= val < (1 << limit), f'Value outside {limit}-bit range: {col["name"]}')
                if col['bits']:
                    mask = ((1 << limit) - 1) << col['shift']
                    val = (previous & ~mask) | (val << col['shift'])
                raw[pos:pos + size] = val.to_bytes(size, 'little')
        encoded_rows.extend(raw)
    # Nothing already in the section ever moves, so no string/nested pointer needs a fixup:
    # new or changed strings are appended to the pool and a longer row array is re-placed
    # at the end (the table descriptor carries its absolute offset). Superseded strings
    # and the old row array stay as unreferenced bytes; only the descriptor is rewritten.
    start = meta['rows']
    if len(rows) > meta['count']:
        out.extend(b'\0' * (-len(out) % 4))
        start = len(out)
        out.extend(encoded_rows)
    else:
        out[start:start + meta['count'] * meta['width']] = encoded_rows.ljust(meta['count'] * meta['width'], b'\0')
    if len(out) != len(original):
        out.extend(b'\0' * (-len(out) % 4))
    struct.pack_into('<3I', out, meta['info'], len(rows), meta['width'], start)
    struct.pack_into('<I', out, 12, len(out) - 32)
    return bytes(out)


def build(document):
    require(document['format'] == 'fl-scr-v1', 'Unknown JSON format')
    sections = [build_section(s) for s in document['sections']]
    require(len(sections) == (2 if document['wrapper'] else 1), 'Wrong section count')
    if document['wrapper']:
        return struct.pack('<4I', 2, 16, 16 + len(sections[0]), 16 + sum(map(len, sections))) + b''.join(sections)
    return sections[0]


def write_csv(document, path):
    """Readable wide export, one file for the first table section; build never reads it.

    Strings with controls and multi-value columns are written as JSON text.
    """
    section = next((x for x in document['sections'] if x['kind'] == 'table'), None)
    require(section is not None, 'No table section to export')
    names = [c['name'] for c in section['columns']]
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['row'] + names)
        for j, row in enumerate(section['rows']):
            writer.writerow([j] + [v if isinstance(v, (str, int)) else json.dumps(v, ensure_ascii=False)
                                   for v in (row[n] for n in names)])


def info(data, resource_id=None):
    lines = []
    for i, section in enumerate(dump(data, resource_id)['sections']):
        if section['kind'] == 'opaque':
            lines.append(f'section {i}: opaque, {len(base64.b64decode(section["original"]))} bytes')
            continue
        lines.append(f'section {i}: table, {len(section["rows"])} rows x {section["row_size"]} bytes')
        for col in section['columns']:
            bits = f' bits={col["bits"]}@{col["shift"]}' if col['bits'] else ''
            array = f'[{col["count"]}]' if col['count'] > 1 else ''
            lines.append(f'  {col["offset"]:#05x} {col["type"]}{array}{bits}  {col["name"]}'
                         + (f'  ({col["confidence"]})' if 'confidence' in col else ''))
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    dumping = subs.add_parser('dump', help='SCR -> editable JSON (or readable CSV)')
    dumping.add_argument('scr', type=Path)
    dumping.add_argument('output', type=Path)
    listing = subs.add_parser('info', help='print sections and column layout')
    listing.add_argument('scr', type=Path)
    for p in (dumping, listing):
        p.add_argument('--id', type=int, help='Archive resource ID for schema selection '
                                              '(default: leading digits of the file name)')
    building = subs.add_parser('build', help='JSON -> SCR')
    building.add_argument('json', type=Path)
    building.add_argument('scr', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'build':
            require(args.scr.resolve() != args.json.resolve(), 'Input and output paths must differ')
            args.scr.write_bytes(build(json.loads(args.json.read_text(encoding='utf-8'))))
            return
        match = re.match(r'^(\d+)_', args.scr.name)
        resource_id = args.id if args.id is not None else int(match[1]) if match else None
        if args.command == 'info':
            print(info(args.scr.read_bytes(), resource_id))
            return
        require(args.output.resolve() != args.scr.resolve(), 'Input and output paths must differ')
        require(args.output.suffix.lower() in ('.json', '.csv'), 'Output must be .json or .csv')
        document = dump(args.scr.read_bytes(), resource_id)
        if args.output.suffix.lower() == '.csv':
            write_csv(document, args.output)
        else:
            args.output.write_text(json.dumps(document, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    except (ValueError, KeyError, TypeError, struct.error, OSError) as exc:
        parser.exit(1, f'fl_scr: {exc}\n')


if __name__ == '__main__':
    main()
