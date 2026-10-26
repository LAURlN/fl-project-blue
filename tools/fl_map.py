#!/usr/bin/env python3
"""Fantasy Life EU placement reader/editor and area resource inventory.

0x3340f10f is placement data, not event bytecode. Fixed-layout edits retain
all offsets. Append clones with --experimental-growth via JSON; old row addresses
then move, so this path needs a runtime test. See docs/phase2-maps-enemies.md.
"""
import argparse
import base64
import collections
import copy
import json
import importlib.util
import math
from pathlib import Path
import struct

spec = importlib.util.spec_from_file_location('fl_scr', Path(__file__).with_name('fl_scr.py'))
scr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scr)

spec_zmdl = importlib.util.spec_from_file_location('fl_zmdl', Path(__file__).with_name('fl_zmdl.py'))
zmdl = importlib.util.module_from_spec(spec_zmdl)
spec_zmdl.loader.exec_module(zmdl)

MAGIC = bytes.fromhex('0ff14033')
HEADER = 0xd4
ROW_SIZE = 0x34
TYPE_COUNT = 23
FIELDS = {'index': (0, 'h'), 'map_id': (2, 'h'), 'type': (4, 'B'),
          'subtype': (5, 'b'), 'flags': (6, 'H'), 'reference': (8, 'h'),
          'unknown_0a': (10, 'H'), 'uid': (12, 'I'), 'linked_uid': (16, 'I'),
          'position': (20, '3f'), 'extent': (32, '3f'), 'yaw': (44, 'f')}
WARP_FIELDS = {'arrival_position': (0, '3f'), 'arrival_yaw': (12, 'f'),
               'aux_position': (16, '3f'), 'aux_extent': (28, '3f'),
               'aux_yaw': (40, 'f'), 'flags': (44, 'I')}
SPAWN_FIELDS = {'unknown_00': (0, 'h'), 'count_max': (2, 'h'), 'count_min': (4, 'h'),
                'point_count': (6, 'h'), 'capacity': (8, 'h'), 'unknown_0a': (10, 'b'),
                'condition_count': (11, 'b'), 'flags': (12, 'B'), 'level': (13, 'b'),
                'unknown_0e': (14, 'H')}
POINT_FIELDS = {'position': (0, '3f'), 'yaw': (12, 'f'), 'variant': (16, 'b'),
                'unknown_11': (17, 'B'), 'flags': (18, 'B'), 'unknown_13': (19, 'B')}
BUNDLE_ROLES = ['model', 'collision', 'material_animation', 'textures', 'motion',
                'CB01', 'minimap_base', 'FB01', 'GB01', 'unknown_51d00202']
UNIT_ROLES = ['model', 'material_animation', 'textures', 'common_motion', 'battle_motion',
              'common_action_parameters', 'battle_action_parameters', 'common_parameters',
              'battle_parameters', 'ai_rules', 'ai_schedule', 'common_action_motion',
              'battle_action_motion', 'effects', 'sound_bank', 'battle_missiles', 'sound_ids']


def unpack(data, offset, fmt):
    values = struct.unpack('<' + fmt, scr.span(data, offset, struct.calcsize('<' + fmt)))
    return values[0] if len(values) == 1 else list(values)


def decode_fields(data, offset, fields):
    return {name: unpack(data, offset + off, fmt) for name, (off, fmt) in fields.items()}


def patch_fields(out, offset, fields, row, before):
    scr.require(set(row) == set(fields), 'Missing or unknown editable fields')
    for name, (off, fmt) in fields.items():
        code = fmt[-1]
        size = struct.calcsize('<' + code)
        count = struct.calcsize('<' + fmt) // size
        values = row[name] if count > 1 else [row[name]]
        previous = before[name] if count > 1 else [before[name]]
        scr.require(isinstance(values, list) and len(values) == count, f'Invalid {name} vector')
        for j, (value, old) in enumerate(zip(values, previous)):
            scr.require(type(value) in (int, float) if code == 'f' else type(value) is int,
                        f'Expected {"numeric" if code == "f" else "integer"} field: {name}')
            # Preserve untouched NaN payload bits even after a JSON round trip or
            # an edit to a neighbouring vector component. Allow signed-zero edits.
            same = value == old
            if code == 'f':
                same = (same and (value != 0 or math.copysign(1, value) == math.copysign(1, old))) or (
                    math.isnan(value) and math.isnan(old))
            if same:
                continue
            scr.require(code != 'f' or math.isfinite(value), 'Edited floats must be finite')
            try:
                raw = struct.pack('<' + code, value)
            except (struct.error, OverflowError) as exc:
                raise ValueError(f'Invalid {name}: {exc}') from exc
            pos = offset + off + j*size
            out[pos:pos + size] = raw


def pointer_list(data, count, offset, fmt='I'):
    scr.require(count >= 0, 'Negative count')
    scr.require(bool(offset) or not count, 'Nonempty array has NULL offset')
    return [unpack(data, offset + i * struct.calcsize('<' + fmt), fmt) for i in range(count)]


def dump(data):
    scr.require(data[:4] == MAGIC, 'Not FL 0ff14033 placement data')
    scr.span(data, 0, HEADER)
    scr.require(unpack(data, 4, 'I') == len(data) - HEADER, 'Placement length mismatch')
    count, maps = unpack(data, 10, 'h'), unpack(data, 12, 'h')
    rows_offset, maps_offset = unpack(data, 16, 'I'), unpack(data, 20, 'I')
    scr.require(count >= 0 and maps >= 0, 'Negative placement/map count')
    scr.require(rows_offset >= HEADER, 'Rows overlap header')
    scr.span(data, rows_offset, count * ROW_SIZE)
    scr.require(maps_offset >= HEADER or not maps, 'Map groups overlap header')
    scr.span(data, maps_offset, maps * 8)
    rows = []
    for i in range(count):
        off = rows_offset + i * ROW_SIZE
        row = decode_fields(data, off, FIELDS)
        scr.require(row['index'] == i, 'Nonsequential placement ordinal')
        scr.require(row['type'] < TYPE_COUNT, 'Unknown placement type')
        row['payload_offset'] = p = unpack(data, off + 48, 'I')
        if p:
            scr.span(data, p, 1)
        if row['type'] == 3 and p:
            row['warp'] = decode_fields(data, p, WARP_FIELDS)
        if row['type'] == 12 and p:
            spawn = decode_fields(data, p, SPAWN_FIELDS)
            spawn['conditions_offset'] = cp = unpack(data, p + 16, 'I')
            spawn['points_offset'] = pp = unpack(data, p + 20, 'I')
            scr.require(spawn['point_count'] >= 0 and spawn['condition_count'] >= 0,
                        'Negative spawn array count')
            spawn['conditions'] = [scr.span(data, cp + 8*j, 8).hex()
                                   for j in range(spawn['condition_count'])]
            spawn['points'] = [decode_fields(data, pp + 20*j, POINT_FIELDS)
                               for j in range(spawn['point_count'])]
            scr.require(cp or not spawn['conditions'], 'NULL conditions')
            scr.require(pp or not spawn['points'], 'NULL spawn points')
            row['spawn'] = spawn
        rows.append(row)
    # Validate the two indexes that the runtime uses (all offsets are file absolute).
    for type_ in range(TYPE_COUNT):
        n = unpack(data, 28 + 8*type_, 'h')
        p = unpack(data, 32 + 8*type_, 'I')
        offsets = pointer_list(data, n, p)
        expected = [rows_offset + i*ROW_SIZE for i, r in enumerate(rows) if r['type'] == type_]
        scr.require(offsets == expected, f'Type {type_} pointer index disagrees with rows')
    groups = []
    for i in range(maps):
        map_id, n, p = unpack(data, maps_offset + 8*i, 'hhI')
        scr.require(n >= 0 and (p or not n), 'Invalid spawn-group count/pointer')
        groups_for_map = []
        for j in range(n):
            size, choice, q = unpack(data, p + 8*j, 'hhI')
            offsets = pointer_list(data, size, q)
            indices = []
            for off in offsets:
                scr.require(off >= rows_offset and (off-rows_offset) % ROW_SIZE == 0,
                            'Spawn group points outside row array')
                index = (off-rows_offset)//ROW_SIZE
                scr.require(index < count and rows[index]['type'] == 12 and
                            rows[index]['map_id'] == map_id, 'Invalid spawn group member')
                indices.append(index)
            groups_for_map.append(dict(choice=choice, rows=indices))
        groups.append(dict(map_id=map_id, groups=groups_for_map))
    return dict(format='fl-map-v1', original=base64.b64encode(data).decode(),
                rows=rows, map_groups=groups)


def build(doc, experimental_growth=False):
    scr.require(set(doc) == {'format', 'original', 'rows', 'map_groups'}, 'Unknown or missing document fields')
    scr.require(doc['format'] == 'fl-map-v1', 'Wrong document format')
    data = base64.b64decode(doc['original'], validate=True)
    before = dump(data)
    rows = doc['rows']
    scr.require(len({r['uid'] for r in rows}) == len(rows), 'Duplicate placement UIDs')
    scr.require(len(doc['map_groups']) <= 32767, 'Too many map groups')
    for group in doc['map_groups']:
        scr.require(set(group) == {'map_id', 'groups'} and type(group['map_id']) is int and
                    -32768 <= group['map_id'] <= 32767, 'Invalid map group')
        scr.require(len(group['groups']) <= 32767, 'Too many spawn groups')
        for g in group['groups']:
            scr.require(set(g) == {'choice', 'rows'} and type(g['choice']) is int and
                        -1 <= g['choice'] <= 32767 and len(g['rows']) <= 32767,
                        'Invalid spawn selection group')
            for i in g['rows']:
                scr.require(type(i) is int and 0 <= i < len(rows) and rows[i]['type'] == 12 and
                            rows[i]['map_id'] == group['map_id'], 'Invalid group row')
    growth = len(rows) != len(before['rows']) or doc['map_groups'] != before['map_groups']
    scr.require(not growth or experimental_growth, 'Row/group changes require --experimental-growth')
    scr.require(len(rows) >= len(before['rows']), 'Removing placements is unsupported')
    scr.require(len(rows) <= 32767, 'Too many placements')
    out = bytearray(data)
    old_start = unpack(data, 16, 'I')
    # Existing records stay at their original offsets for ordinary edits.
    start = old_start
    if growth:
        out.extend(b'\0' * (-len(out) % 4))
        start = len(out)
        out.extend(scr.span(data, old_start, len(before['rows'])*ROW_SIZE))
        out.extend(b'\0' * ((len(rows)-len(before['rows']))*ROW_SIZE))
    def append(raw):
        out.extend(b'\0' * (-len(out) % 4))
        offset = len(out)
        out.extend(raw)
        return offset
    pending = {}
    def shared_patch(offset, raw):
        # Shared payloads must not be edited inconsistently through two records.
        for k, value in enumerate(raw, offset):
            scr.require(k not in pending or pending[k] == value, 'Conflicting shared payload edits')
            pending[k] = value
    for i, row in enumerate(rows):
        is_new = i >= len(before['rows'])
        if is_new:
            # Clone the known payload too, so a new warp/spawn can be edited independently.
            candidates = [r for r in before['rows'] if r['type'] == row['type'] and
                          r['payload_offset'] == row['payload_offset']]
            scr.require(candidates, 'Append an existing record clone (payload/type must match)')
            old = candidates[0]
            scr.require(row.get('warp') == old.get('warp') and row.get('spawn') == old.get('spawn'),
                        'Append the unchanged payload clone, build, then dump again to edit its new payload')
            source_off = old_start + old['index']*ROW_SIZE
            out[start+i*ROW_SIZE:start+(i+1)*ROW_SIZE] = data[source_off:source_off+ROW_SIZE]
        else:
            old = before['rows'][i]
            scr.require(row['type'] == old['type'] and row['payload_offset'] == old['payload_offset'],
                        'Changing record type or payload offset is unsupported')
        scr.require(set(row) == set(old), 'Unknown or missing row fields')
        scr.require(row['index'] == i, 'Set appended index to its new ordinal')
        patch_fields(out, start+i*ROW_SIZE, FIELDS,
                     {k: row[k] for k in FIELDS}, {k: old[k] for k in FIELDS})
        p = old['payload_offset']
        if is_new and p and row['type'] in (3, 12):
            raw = bytearray(data[p:p+(48 if row['type'] == 3 else 24)])
            if row['type'] == 12:
                spawn = old['spawn']
                cp = append(scr.span(data, spawn['conditions_offset'], 8*spawn['condition_count'])) if spawn['condition_count'] else 0
                pp = append(scr.span(data, spawn['points_offset'], 20*spawn['point_count'])) if spawn['point_count'] else 0
                struct.pack_into('<II', raw, 16, cp, pp)
            new_p = append(raw)
            struct.pack_into('<I', out, start+i*ROW_SIZE+48, new_p)
        elif is_new and p:
            raise ValueError('Only warps/spawns with known payloads can be appended')
        if 'warp' in row and not is_new:
            raw = bytearray(data[p:p+48])
            patch_fields(raw, 0, WARP_FIELDS, row['warp'], old['warp'])
            shared_patch(p, raw)
        if 'spawn' in row and not is_new:
            new, prev = row['spawn'], old['spawn']
            scr.require(set(new) == set(prev), 'Unknown or missing spawn fields')
            for key in ('point_count', 'condition_count', 'points_offset', 'conditions_offset'):
                scr.require(new[key] == prev[key], 'Resizing or moving spawn arrays is unsupported')
            raw = bytearray(data[p:p+24])
            patch_fields(raw, 0, SPAWN_FIELDS, {k:new[k] for k in SPAWN_FIELDS}, prev)
            shared_patch(p, raw)
            scr.require(len(new['points']) == len(prev['points']) and
                        len(new['conditions']) == len(prev['conditions']), 'Spawn array length changed')
            for j, point in enumerate(new['points']):
                off = prev['points_offset'] + j*20
                raw = bytearray(data[off:off+20])
                patch_fields(raw, 0, POINT_FIELDS, point, prev['points'][j])
                shared_patch(off, raw)
            for j, condition in enumerate(new['conditions']):
                raw = bytes.fromhex(condition)
                scr.require(len(raw) == 8, 'Condition is eight opaque bytes')
                shared_patch(prev['conditions_offset']+j*8, raw)
    for offset, value in pending.items():
        out[offset] = value
    if growth:
        struct.pack_into('<h', out, 10, len(rows))
        struct.pack_into('<I', out, 16, start)
        for t in range(TYPE_COUNT):
            offsets = [start+i*ROW_SIZE for i,r in enumerate(rows) if r['type'] == t]
            p = append(struct.pack('<'+'I'*len(offsets), *offsets)) if offsets else 0
            struct.pack_into('<h', out, 28+8*t, len(offsets))
            struct.pack_into('<I', out, 32+8*t, p)
        map_records = []
        for group in doc['map_groups']:
            records = []
            for g in group['groups']:
                offsets = [start+i*ROW_SIZE for i in g['rows']]
                p = append(struct.pack('<'+'I'*len(offsets), *offsets)) if offsets else 0
                records.append(struct.pack('<hhI', len(offsets), g['choice'], p))
            p = append(b''.join(records)) if records else 0
            map_records.append(struct.pack('<hhI', group['map_id'], len(records), p))
        p = append(b''.join(map_records)) if map_records else 0
        struct.pack_into('<h', out, 12, len(map_records))
        struct.pack_into('<I', out, 20, p)
        struct.pack_into('<I', out, 4, len(out)-HEADER)
    dump(bytes(out))  # Structural validation, including rebuilt indexes.
    return bytes(out)


def apply_edits(data, edits, map_groups=None, experimental_growth=False):
    """Apply source-only placement operations, relocating clones before payload edits.

    An appended row copies a row in this document. Build/dump gives its payload an
    independent address before applying `warp`/`spawn` changes. No extracted bytes
    or pointer offsets need to appear in a mod source.
    """
    doc = dump(data)
    for edit in edits:
        scr.require(set(edit) <= {'row', 'copy_from', 'expect', 'set', 'warp', 'spawn'},
                    'Unknown placement operation')
        at = edit['row']
        if at == 'append':
            source = edit['copy_from']
            scr.require(type(source) is int and 0 <= source < len(doc['rows']), 'Invalid placement template')
            row = copy.deepcopy(doc['rows'][source])
            at = len(doc['rows'])
            row['index'] = at
        else:
            scr.require(type(at) is int and 0 <= at < len(doc['rows']), 'Invalid placement row')
            scr.require('copy_from' not in edit, 'copy_from is only supported for appended placements')
            row = doc['rows'][at]
        for key, value in edit.get('expect', {}).items():
            scr.require(row.get(key) == value, f'Placement expectation failed: {at}:{key}')
        for key, value in edit.get('set', {}).items():
            scr.require(key in FIELDS and key not in ('index', 'type'), f'Protected placement field: {key}')
            row[key] = copy.deepcopy(value)
        if edit['row'] == 'append':
            doc['rows'].append(row)
            doc = dump(build(doc, experimental_growth))
            row = doc['rows'][at]
        for kind in ('warp', 'spawn'):
            if kind in edit:
                scr.require(kind in row and set(edit[kind]) <= set(row[kind]), f'Invalid {kind} edit')
                row[kind].update(copy.deepcopy(edit[kind]))
        doc = dump(build(doc, experimental_growth))
    if map_groups is not None:
        doc['map_groups'] = copy.deepcopy(map_groups)
    result = build(doc, experimental_growth)
    scr.require(build(dump(result)) == result, 'Edited placement round trip failed')
    return result


class Archive:
    def __init__(self, root):
        self.root = Path(root)
        self.entries = {e['id']:e for e in json.loads((self.root/'.fl_archive/manifest.json').read_text())['entries']}

    def data(self, id_):
        return (self.root/self.entries[id_]['path']).read_bytes()

    def table(self, id_):
        return scr.dump(self.data(id_), id_)['sections'][0]['rows']

    def monster(self, monster_id):
        names = self.table(6947)
        scr.require(0 <= monster_id < len(names), 'Monster ID out of bounds')
        name = names[monster_id]
        unit = self.table(8713)[name['unit_index']]
        return dict(monster_id=monster_id, definition=name, unit_index=name['unit_index'],
                    unit_name=unit['name'], unit_kind=unit['unit_kind'],
                    resources={k:self.resource(n) for k,n in zip(UNIT_ROLES,unit['resources'])},
                    loot=[dict(row=i, **{k:v for k,v in r.items() if k != '_raw'})
                          for i,r in enumerate(self.table(6930)) if r['monster_id'] == monster_id])

    def doors(self, map_id):
        area = self.area(map_id)
        model = area['resources']['model']
        scr.require(model is not None, 'Area has no model')
        bones = inspect_model(self.data(model['id']))['bones']
        warps = []
        for placement in area['placements']:
            for row in dump(self.data(placement['id']))['rows']:
                if row['type'] == 3 and row['map_id'] == map_id:
                    warps.append(dict(resource=placement['id'], row=row['index'],
                                      route=row['reference'], position=row['position']))
        result = []
        for bone in bones:
            if 'door' not in bone['name'].lower():
                continue
            # These are local bone translations, not a general world-transform solver.
            def distance(w):
                return math.hypot(w['position'][0]-bone['translation'][0],
                                  w['position'][2]-bone['translation'][2])
            nearest = min(warps, key=distance) if warps else None
            result.append(dict(name=bone['name'], translation=bone['translation'], parent=bone['parent'],
                               nearest_warp=nearest, distance_xz=distance(nearest) if nearest else None))
        return dict(map_id=map_id, model=model, doors=result,
                    note='Local bone positions versus placement positions; proximity is a static lead, not a runtime accessibility test.')

    def resource(self, id_):
        if id_ == 0xffffffff:
            return None
        data = self.data(id_)
        return dict(id=id_, path=self.entries[id_]['path'], size=len(data), magic=data[:4].hex())

    def gltf(self, map_id, out_path=None):
        area = self.area(map_id)
        model = area['resources']['model']
        scr.require(model is not None, f'Map {map_id} has no 3D model')
        raw_model = self.data(model['id'])
        textures = []
        tex_res = area['resources']['textures']
        if tex_res is not None:
            textures.append(self.data(tex_res['id']))
        glb_data = zmdl.export_gltf(raw_model, textures, up='y')
        if out_path:
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(glb_data)
        return glb_data

    def area(self, map_id):
        maps = self.table(5973)
        scr.require(0 <= map_id < len(maps), 'Map ID out of bounds')
        row = maps[map_id]
        bundle = self.table(8716)[row['bundle_index']]
        index = self.table(8695)
        spawn = next((r['spawn_table_resource'] for r in index if r['map_id'] == map_id), None)
        script_rows = scr.dump(self.data(8697))['sections'][0]['rows']
        scripts = [dict(row=i, resources=[self.resource(n) for n in r['c00']])
                   for i,r in enumerate(script_rows) if r['c01'] == 1 and r['c02'] == map_id]
        placements = []
        for s in scripts:
            for resource in s['resources']:
                if resource and self.data(resource['id'])[:4] == MAGIC:
                    doc = dump(self.data(resource['id']))
                    placements.append(dict(id=resource['id'], rows=len(doc['rows']),
                                           types=dict(collections.Counter(r['type'] for r in doc['rows']))))
        return dict(map_id=map_id, name=scr.plain(row['name']), label=row['map_label'],
                    bundle_index=row['bundle_index'],
                    resources={k:self.resource(n) for k,n in zip(BUNDLE_ROLES,bundle['resources'])},
                    spawn_groups=self.resource(spawn) if spawn is not None else None,
                    script_resources=scripts, placements=placements,
                    routes=[dict(row=i, **{k:v for k,v in r.items() if k != '_raw'})
                            for i,r in enumerate(self.table(5965)) if map_id in r['map_pair']])


def inspect_model(data):
    """Metadata only; follows Ohana3DS Rebirth's Fantasy Life ZMDL reader."""
    scr.require(data[:4] == b'zmdl', 'Not ZMDL')
    mat, bone, mesh, nm, nb, no, unknown = unpack(data, 32, 'IIIHHHH')
    def name(off):
        return scr.span(data, off, 64).split(b'\0')[0].decode('ascii', errors='replace')
    scr.span(data, mat, nm*180)
    scr.span(data, bone, nb*204)
    scr.span(data, mesh, no*196)
    return dict(materials=[name(mat+i*180) for i in range(nm)], mesh_count=no,
                bones=[dict(name=name(bone+i*204),
                            translation=unpack(data,bone+i*204+164,'3f'),
                            rotation=unpack(data,bone+i*204+176,'3f'),
                            scale=unpack(data,bone+i*204+188,'3f'),
                            parent=unpack(data,bone+i*204+200,'h')) for i in range(nb)])


def main():
    p = argparse.ArgumentParser(__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('dump','build','model'):
        a = sub.add_parser(command)
        a.add_argument('input', type=Path)
        a.add_argument('output', type=Path)
        if command == 'build':
            a.add_argument('--experimental-growth', action='store_true')
    for command in ('area', 'doors', 'monster', 'gltf'):
        a = sub.add_parser(command)
        a.add_argument('root', type=Path)
        a.add_argument('id', type=int)
        a.add_argument('output', type=Path)
    args = p.parse_args()
    if args.command == 'build':
        args.output.write_bytes(build(json.loads(args.input.read_text()), args.experimental_growth))
        return
    if args.command == 'dump':
        result = dump(args.input.read_bytes())
    elif args.command == 'model':
        result = inspect_model(args.input.read_bytes())
    elif args.command == 'gltf':
        Archive(args.root).gltf(args.id, args.output)
        return
    else:
        result = getattr(Archive(args.root), args.command)(args.id)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
