"""Source-only map, whole-resource and script operations for fl_mod.py."""
import copy
import importlib.util
from pathlib import Path


def local(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


maps, scripts, archive = local('fl_map'), local('fl_script'), local('fl_archive')
require = maps.scr.require


def apply(data, source, spec, updates, source_bytes):
    """Return validated additions to the builder's logical resource replacements."""
    def reserve(entry):
        id_ = entry['resource']
        require(type(id_) is int and id_ in data.entries and id_ not in updates,
                f'Unknown/conflicting resource {id_}')
        require(id_ not in maps.scr.schemas(), 'Use row edits for schema-backed tables')
        source_bytes(data, id_)
        return id_

    if 'story_skip' in spec:
        replacements, _ = local('fl_story_skip').apply(data, spec['story_skip'])
        for id_, raw in replacements.items():
            reserve(dict(resource=id_))
            updates[id_] = raw

    for entry in spec.get('copies', []):
        id_ = reserve(entry)
        require(entry['base'] not in maps.scr.schemas(), 'Use row edits for schema-backed donor tables')
        updates[id_] = source_bytes(data, entry['base'])
    for entry in spec.get('placements', []):
        id_ = reserve(entry)
        raw = source_bytes(data, entry.get('base', id_))
        updates[id_] = maps.apply_edits(raw, entry.get('edits', []), entry.get('map_groups'),
                                       entry.get('experimental_growth', False))
    for entry in spec.get('placements', []):
        validate_spawns(data, maps.dump(updates[entry['resource']]), entry['resource'])
    for entry in spec.get('scripts', []):
        id_ = reserve(entry)
        raw = scripts.assemble(archive.safe_path(source, entry['assembly']).read_text(encoding='utf-8'))
        require(scripts.assemble(scripts.disassemble(raw)) == raw, f'Script round trip failed: {id_}')
        updates[id_] = raw

    # A walk-in route must have exactly one enabled, unlinked endpoint in each
    # supplied layer, and each layer must be selected by that map's association.
    for entry in spec.get('transitions', []):
        route = entry['route']
        routes = data.rows(5965)
        require(type(route) is int and 0 <= route < len(routes), f'Invalid route {route}')
        endpoints = []
        uids = set()
        for endpoint in entry['endpoints']:
            id_ = endpoint['resource']
            raw = updates.get(id_)
            doc = maps.dump(raw if raw is not None else source_bytes(data, id_))
            matches = [r for r in doc['rows'] if r['uid'] == endpoint['uid']]
            require(len(matches) == 1, f'Missing/duplicate endpoint UID in {id_}')
            row = matches[0]
            require(row['type'] == 3 and row['reference'] == route and not row['flags'] & 17 and
                    row['linked_uid'] == 0xffffffff and all(v > 0 for v in row['extent']) and 'warp' in row,
                    f'Invalid walk-in endpoint in {id_}')
            require(row['uid'] not in uids and ((row['uid'] >> 10) & 31) == 3,
                    'Duplicate endpoint UID or incorrect UID type')
            uids.add(row['uid'])
            require(any(g['map_id'] == row['map_id'] for g in doc['map_groups']), 'Missing endpoint map group')
            require(any(r['c01'] == 1 and r['c02'] == row['map_id'] and id_ in r['c00'][4:8]
                        for r in data.rows(8697)), f'Endpoint layer {id_} is not associated with its map')
            endpoints.append(row['map_id'])
        require(len(endpoints) == 2 and sorted(endpoints) == sorted(routes[route]['map_pair']),
                f'Route {route} needs paired endpoints matching map_pair')


def apply_merged(data, source, spec, state, owner, source_bytes):
    """Apply content operations into a shared stack state.

    Whole resources are exclusive, while placement files may be extended by later mods
    when they append rows.  The state decides whether an operation is a true conflict.
    """
    if 'story_skip' in spec:
        replacements, _ = local('fl_story_skip').apply(data, spec['story_skip'])
        for id_, raw in replacements.items():
            check_resource(data, id_, source_bytes)
            state.add_resource(id_, raw, owner, 'Story-skip')

    for entry in spec.get('copies', []):
        id_ = entry['resource']
        check_resource(data, id_, source_bytes, allow_append=True)
        require(entry['base'] not in maps.scr.schemas(), 'Use row edits for schema-backed donor tables')
        state.add_resource(id_, source_bytes(data, entry['base']), owner, 'Copy')

    placement_ids = set()
    for entry in spec.get('placements', []):
        id_ = entry['resource']
        require(type(id_) is int and id_ in data.entries, f'Unknown placement resource {id_}')
        require(id_ not in maps.scr.schemas(), 'Use row edits for schema-backed tables')
        explicit_base = entry.get('base')
        existing = id_ in state.placement_bases
        if existing:
            if explicit_base is not None:
                require(explicit_base == state.placement_bases[id_],
                        f'Placement base conflict {id_}: {explicit_base} and {state.placement_bases[id_]}')
            current = state.updates[id_]
        else:
            base = explicit_base if explicit_base is not None else id_
            require(type(base) is int and base in data.entries, f'Unknown placement base {base}')
            source_bytes(data, id_)
            source_bytes(data, base)
            current = source_bytes(data, base)
            state.claim_placement(id_, owner)
            state.placement_bases[id_] = base
        groups = entry.get('map_groups')
        if groups is not None and existing:
            groups = merge_map_groups(maps.dump(current)['map_groups'], groups)
        before = maps.dump(current)
        state.updates[id_] = maps.apply_edits(current, entry.get('edits', []),
                                               groups, entry.get('experimental_growth', False))
        state.claim_placement_doc(id_, before, maps.dump(state.updates[id_]), owner)
        placement_ids.add(id_)
    for id_ in sorted(placement_ids):
        validate_spawns(data, maps.dump(state.updates[id_]), id_)

    for entry in spec.get('scripts', []):
        id_ = entry['resource']
        check_resource(data, id_, source_bytes)
        raw = scripts.assemble(archive.safe_path(source, entry['assembly']).read_text(encoding='utf-8'))
        require(scripts.assemble(scripts.disassemble(raw)) == raw, f'Script round trip failed: {id_}')
        state.add_resource(id_, raw, owner, 'Script')

    validate_transitions(data, spec, state.updates, source_bytes)


def merge_map_groups(current, provided):
    """Union placement-group rows from both sources, rejecting conflicting choices."""
    by_map = {group['map_id']: group for group in current}
    result, seen = [], set()
    for group in provided:
        merged = copy.deepcopy(group)
        base = by_map.get(group['map_id'])
        if base is not None and len(base.get('groups', [])) == len(merged.get('groups', [])):
            for own, other in zip(merged['groups'], base['groups']):
                if (own.get('choice') not in (None, -1) and other.get('choice') not in (None, -1)
                        and own.get('choice') != other.get('choice')):
                    raise ValueError(f'Placement map-group conflict for map {group["map_id"]}: '
                                     'different forced choices')
                rows = list(own.get('rows', []))
                rows.extend(row for row in other.get('rows', []) if row not in rows)
                own['rows'] = sorted(rows)
                if own.get('choice') in (None, -1):
                    own['choice'] = other.get('choice', -1)
        result.append(merged)
        seen.add(group['map_id'])
    result.extend(copy.deepcopy(group) for group in current if group['map_id'] not in seen)
    return result


def check_resource(data, id_, source_bytes, allow_append=False):
    """Validate a whole-resource target before the stack state claims it."""
    require(type(id_) is int and id_ != 1 and (id_ in data.entries or
            (allow_append and data.manifest['count'] <= id_ < 65535)), f'Unknown resource {id_}')
    require(id_ not in maps.scr.schemas(), 'Use row edits for schema-backed tables')
    if id_ in data.entries:
        source_bytes(data, id_)


def validate_transitions(data, spec, updates, source_bytes):
    """A walk-in route needs one enabled, unlinked type-3 endpoint in each layer."""
    for entry in spec.get('transitions', []):
        route = entry['route']
        routes = data.rows(5965)
        require(type(route) is int and 0 <= route < len(routes), f'Invalid route {route}')
        endpoints = []
        uids = set()
        for endpoint in entry['endpoints']:
            id_ = endpoint['resource']
            raw = updates.get(id_)
            doc = maps.dump(raw if raw is not None else source_bytes(data, id_))
            matches = [r for r in doc['rows'] if r['uid'] == endpoint['uid']]
            require(len(matches) == 1, f'Missing/duplicate endpoint UID in {id_}')
            row = matches[0]
            require(row['type'] == 3 and row['reference'] == route and not row['flags'] & 17 and
                    row['linked_uid'] == 0xffffffff and all(v > 0 for v in row['extent']) and 'warp' in row,
                    f'Invalid walk-in endpoint in {id_}')
            require(row['uid'] not in uids and ((row['uid'] >> 10) & 31) == 3,
                    'Duplicate endpoint UID or incorrect UID type')
            uids.add(row['uid'])
            require(any(g['map_id'] == row['map_id'] for g in doc['map_groups']), 'Missing endpoint map group')
            require(any(r['c01'] == 1 and r['c02'] == row['map_id'] and id_ in r['c00'][4:8]
                        for r in data.rows(8697)), f'Endpoint layer {id_} is not associated with its map')
            endpoints.append(row['map_id'])
        require(len(endpoints) == 2 and sorted(endpoints) == sorted(routes[route]['map_pair']),
                f'Route {route} needs paired endpoints matching map_pair')


def validate_spawns(data, doc, id_):
    """Type-12 monster regions: group, point selectors, counts and map-group membership.

    The region's reference is a row of its map's spawn-group table (8695 → per-area SCR,
    as edited by this mod); a point with flag 4 forces that group member. Every shipped
    region keeps min <= max <= points, max <= capacity and is listed in a map group,
    without which the field never processes it.
    """
    members = {i for g in doc['map_groups'] for group in g['groups'] for i in group['rows']}
    tables = {r['map_id']: r['spawn_table_resource'] for r in data.rows(8695)}
    for row in doc['rows']:
        if row['type'] != 12:
            continue
        where = f'{id_} row {row["index"]}'
        require(row['map_id'] in tables, f'{where}: map {row["map_id"]} has no spawn table')
        groups = data.rows(tables[row['map_id']])
        require(0 <= row['reference'] < len(groups), f'{where}: spawn group {row["reference"]} out of range')
        filled = sum(m != 0xffff for m in groups[row['reference']]['monsters'])
        spawn = row['spawn']
        require(spawn['count_min'] <= spawn['count_max'] <= spawn['point_count'] and
                spawn['count_max'] <= spawn['capacity'], f'{where}: inconsistent spawn counts')
        for point in spawn['points']:
            require(not point['flags'] & 4 or 0 <= point['variant'] < filled,
                    f'{where}: forced member {point["variant"]} outside group {row["reference"]}')
        require(row['index'] in members, f'{where}: region is in no map group and would never spawn')

