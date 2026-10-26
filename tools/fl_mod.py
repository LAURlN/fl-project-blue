#!/usr/bin/env python3
"""Build small Fantasy Life resource overlays from JSON row edits and local files.

No dump/extraction is modified. Output contains derived game resources: keep it private.
See docs/modding-guide.md for the source format and the Wooden Sword example.
"""
import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile

import importlib.util

ROOT = Path(__file__).parent


def local(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


data_tools = local('fl_data')
ztex, zmdl = local('fl_ztex'), local('fl_zmdl')
content = local('fl_mod_content')
scr, archive = data_tools.scr, data_tools.archive
require = scr.require


def fnv32(raw):
    value = 2166136261
    for byte in raw:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f'{value:08x}'


class ModData(data_tools.Data):
    def __init__(self, root):
        super().__init__(root)
        self.changed = set()
        self.original_cache = {}

    def original_document(self, id_):
        """The untouched extraction document; `copies` and allocation guards use this."""
        if id_ not in self.original_cache:
            self.original_cache[id_] = scr.dump(self.path(id_).read_bytes(), id_)
        return self.original_cache[id_]

    def original_rows(self, id_):
        return self.original_document(id_)['sections'][0]['rows']

    def original_bytes(self, id_):
        return self.path(id_).read_bytes()


VANILLA_ITEM_COUNT = 2735
CATEGORY_SIZES = [153, 750, 175, 399, 623, 459, 30, 146]
RECIPE_COUNTS = [171, 341, 229, 186, 371]


def validate_runtime_layout(data):
    """Validate the appended-row contract consumed by the EU item runtime hooks."""
    names = data.rows(6792)
    count = len(names)
    require(VANILLA_ITEM_COUNT <= count <= 65535, 'Invalid runtime item count')
    categories = [row['category'] for row in names]
    vanilla = [category for category, size in enumerate(CATEGORY_SIZES) for _ in range(size)]
    require(categories[:VANILLA_ITEM_COUNT] == vanilla, 'Vanilla item category blocks must stay unchanged')
    require(all(type(c) is int and 0 <= c < 8 for c in categories), 'Invalid appended item category')
    for base in data_tools.ITEM_BASES:
        for slot in range(9):
            rows = data.rows(base + slot)
            require(len(rows) == count, 'All item language tables must have matching item counts')
            if base == 6792:
                require([r['category'] for r in rows] == categories,
                        'Item categories must match across language slots')
    for category, base in enumerate(data_tools.STAT_BASES):
        expected = CATEGORY_SIZES[category] + categories[VANILLA_ITEM_COUNT:].count(category)
        for slot in range(9):
            require(len(data.rows(base + slot)) == expected,
                    f'Category stats must match appended items: {base + slot} needs {expected} rows')
    for id_, minimum in zip(data_tools.RECIPE_TABLES, RECIPE_COUNTS):
        require(minimum <= len(data.rows(id_)) <= 65535,
                f'Recipe table {id_} must preserve vanilla rows and fit 16-bit row IDs')


def resource_target(data, id_):
    """Check a replacement or new standalone ID; continuity is checked at publication."""
    require(type(id_) is int and 0 <= id_ < 65535 and id_ != 1,
            f'Invalid/protected resource {id_}')
    require(id_ in data.entries or id_ >= data.manifest['count'], f'Unknown resource {id_}')
    if id_ in data.entries:
        source_bytes(data, id_)


def validate_appended_resources(ids, count):
    appended = sorted(id_ for id_ in ids if id_ >= count)
    require(not appended or appended == list(range(count, appended[-1] + 1)),
            f'New physical archive IDs must be contiguous starting at {count}')


ITEM_NAMES, ICON_TABLES = 6792, 8686  # nine language slots each, same slot order
MONSTER_NAMES, MONSTER_LOOT, UNIT_NAMES = 6947, 6930, 8713
MONSTER_TABLES = [6920] + list(range(6940, 6948))
LOOT_END = 0xffff
APPEARANCE_TABLE = 8714
ITEM_TABLES = {ITEM_NAMES + slot for slot in range(9)} | {6702 + slot for slot in range(9)}
STAT_TABLES = {base + slot for base in data_tools.STAT_BASES for slot in range(9)}

# The verified dummy pools.  `output-update` names (item kinds symbols) map to
# (canonical pool, item category); the values are the game's own `ID_Item_*` kinds.
ITEM_POOLS = {
    'weapon': ('weapon', 0),
    'armour': ('guard', 1), 'armor': ('guard', 1),
    'tool': ('life', 2),
    'consumable': ('use', 4),
    'material': ('etc', 5),
}
ICON_POOLS = {'item_icon': 'item_icon', 'icon': 'item_icon'}
APPEARANCE_POOLS = {'weapon_appearance': 'weapon_appearance', 'gear_appearance': 'gear_appearance',
                    'appearance': 'gear_appearance'}
WEAPON_APPEARANCE_WORDS = ('片手剣', '両手剣', '短剣', '弓', 'ワンド')
RECIPE_POOLS = {
    'alchemy_recipe': 8388, 'alchemy': 8388,
    'blacksmith_recipe': 8389, 'blacksmith': 8389,
    'carpentry_recipe': 8390, 'carpentry': 8390,
    'cooking_recipe': 8391, 'cooking': 8391,
    'tailoring_recipe': 8392, 'tailoring': 8392,
    'recipe': None,
}
SYMBOL_TOKEN = re.compile(r'^\$([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?$')


def _plain(value):
    return scr.plain(value) if isinstance(value, list) else value


def _present(data, id_):
    entries = getattr(data, 'entries', None)
    return entries is None or id_ in entries


def _original_rows(data, id_):
    if hasattr(data, 'original_rows'):
        return data.original_rows(id_)
    return data.rows(id_)


def _original_bytes(data, id_):
    if hasattr(data, 'original_bytes'):
        return data.original_bytes(id_)
    return data.path(id_).read_bytes()


def item_references(data):
    """Items another table already consumes: recipes, shops, quests and bounty drops.

    A dummy slot is only a free slot while nothing references it.  Unknown/missing tables
    (synthetic tests, older extractions) are skipped rather than treated as references.
    """
    used = set()

    def scan(id_, keys):
        if not _present(data, id_):
            return
        try:
            rows = _original_rows(data, id_)
        except (KeyError, ValueError, OSError, struct.error):
            return
        for row in rows:
            for key in keys:
                value = row.get(key)
                for item in value if isinstance(value, list) else [value]:
                    if isinstance(item, int) and item not in (0xffff, 0xffffffff):
                        used.add(item)

    for table in data_tools.RECIPE_TABLES:
        scan(table, ('output_items', 'seasoning_items', 'ingredients'))
    for table in range(8405, 8484):
        scan(table, ('item_id',))
    scan(8715, ('requested_item', 'alternate_requested_item', 'reward_item'))
    for base in data_tools.STAT_BASES:
        for slot in range(9):
            scan(base + slot, ('drop_items',))
    return used


def _appearance_ids(raw, offset):
    """Decode the row's pointer: magic, model resource, magic, texture resource, -1, name."""
    try:
        magic, model, second, texture, end = struct.unpack_from('<5I', raw, offset)
    except struct.error:
        return None
    if magic != 0x01200000 or second != 0x01000000 or end != 0xffffffff or model == texture:
        return None
    return model, texture


class Allocation:
    """One `$symbol` reservation; the symbol itself is its primary row/index value."""

    def __init__(self, pool, name, value, properties, guards, resources=()):
        self.pool = pool
        self.name = name
        self.value = value
        self.properties = dict(properties)
        self.properties.setdefault('row', value)
        self.guards = list(guards)
        self.resources = tuple(resources)

    def resolve(self, property_=None):
        if property_ is None:
            return self.value
        if property_ in self.properties:
            return self.properties[property_]
        raise ValueError(f'Symbolic ID ${self.name} has no property .{property_}')

    def as_json(self, source):
        return dict(source=source, pool=self.pool, symbol='$' + self.name, value=self.value,
                    properties={k: v for k, v in self.properties.items() if k != 'row'},
                    resources=list(self.resources))


class Symbols:
    """Per-source namespace with lexical lookup into the earlier sources in the stack."""

    def __init__(self, parent=None):
        self.parent = parent
        self.local = {}

    def bind(self, name, allocation):
        require(name not in self.local, f'Symbolic ID ${name} is declared twice in one mod')
        self.local[name] = allocation

    def resolve(self, name, property_=None):
        if name in self.local:
            return self.local[name].resolve(property_)
        if self.parent is not None:
            return self.parent.resolve(name, property_)
        raise ValueError(f'Unknown symbolic ID ${name}')


def resolve_value(value, symbols):
    """Resolve exact `$symbol` / `$symbol.property` tokens anywhere in a JSON value."""
    if isinstance(value, str):
        match = SYMBOL_TOKEN.fullmatch(value)
        return symbols.resolve(match.group(1), match.group(2)) if match else value
    if isinstance(value, list):
        return [resolve_value(item, symbols) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            match = SYMBOL_TOKEN.fullmatch(key) if isinstance(key, str) else None
            if match:
                key = symbols.resolve(match.group(1), match.group(2))
                require(not isinstance(key, list), 'A symbolic list cannot be used as an object key')
            result[key] = resolve_value(item, symbols)
        return result
    return value


def normalize_pool(name):
    key = name.strip().lower().replace('-', '_')
    if key in ITEM_POOLS:
        kind_name, category = ITEM_POOLS[key]
        return f'item:{kind_name}', (kind_name, category)
    if key in ICON_POOLS:
        return ICON_POOLS[key], None
    if key in APPEARANCE_POOLS:
        return APPEARANCE_POOLS[key], None
    if key in RECIPE_POOLS:
        return key, RECIPE_POOLS[key]
    raise ValueError(f'Unknown allocation pool {name!r}')


def auto_symbol(pool, names):
    base = re.sub(r'[^A-Za-z0-9_]', '_', pool.lower())
    name, n = base, 2
    while '$' + name in names:
        name, n = f'{base}_{n}', n + 1
    return '$' + name


class Allocator:
    """Deterministic first-free assignment from the verified dummy pools."""

    def __init__(self, data):
        self.data = data
        self.used = collections.defaultdict(set)
        self.used_keys = set()
        self.reserved = set()
        self.resource_owners = {}
        self.reserved_rows = set()
        self.reserved_items = set()
        self.pools = {}
        self.icon_families = {}
        self.guards = {}
        self.allocations = []

    def reserve_resource(self, id_, owner=None):
        self.reserved.add(id_)
        if owner is not None:
            self.resource_owners.setdefault(id_, owner)

    def reserve_row(self, id_, row):
        self.reserved_rows.add((id_, row))

    def reserve_item(self, id_):
        self.reserved_items.add(id_)

    def _candidates(self, canonical, kind, detail):
        if canonical in self.pools:
            return self.pools[canonical]
        if kind == 'item':
            kind_name, category = detail
            symbols, items = _original_rows(self.data, 6702), _original_rows(self.data, ITEM_NAMES)
            referenced = item_references(self.data)
            result = []
            for index, row in enumerate(symbols):
                match = re.fullmatch(r'ID_Item_([A-Za-z0-9]+)_dummy(\d+)',
                                     _plain(row.get('symbolic_id', '')))
                if not match or match.group(1) != kind_name or index >= len(items):
                    continue
                if items[index].get('category') != category or index in referenced:
                    continue
                result.append(dict(key=index, value=index, resources=()))
        elif kind == 'item_icon':
            result = self._icon_candidates()
        elif kind in ('weapon_appearance', 'gear_appearance'):
            result = self._appearance_candidates(kind == 'weapon_appearance')
        else:
            tables = [detail] if detail is not None else list(data_tools.RECIPE_TABLES)
            result = []
            for table in tables:
                if not _present(self.data, table):
                    if detail is not None:
                        raise ValueError(f'Unknown recipe table {table}')
                    continue
                for index, row in enumerate(_original_rows(self.data, table)):
                    if row.get('rank_requirement') == 16 and row.get('unlock_rank') == 16:
                        result.append(dict(key=(table, index), global_key=('recipe', table, index),
                                           value=index, resources=(), table=table,
                                           recipe_key=row.get('recipe_key')))
        self.pools[canonical] = result
        return result

    def _icon_candidates(self):
        tables = [ICON_TABLES + slot for slot in range(9) if _present(self.data, ICON_TABLES + slot)]
        if not tables:
            raise ValueError('No icon tables in this extraction')
        rows = {table: _original_rows(self.data, table) for table in tables}
        referenced = set()
        for base in (ITEM_NAMES,):
            for slot in range(9):
                table = base + slot
                if _present(self.data, table):
                    try:
                        referenced.update(row['icon_index'] for row in _original_rows(self.data, table)
                                          if 'icon_index' in row)
                    except (KeyError, ValueError, OSError, struct.error):
                        pass
        for table in data_tools.RECIPE_TABLES:
            if _present(self.data, table):
                try:
                    referenced.update(row['category_icon_index'] for row in _original_rows(self.data, table)
                                      if 'category_icon_index' in row)
                except (KeyError, ValueError, OSError, struct.error):
                    pass
        ownership = collections.defaultdict(set)
        for table, values in rows.items():
            for index, icon in enumerate(values):
                ownership[icon.get('icon_id')].add(index)
        result = []
        entries = getattr(self.data, 'entries', None)
        for index in range(min(map(len, rows.values()))):
            ids = {values[index].get('icon_id') for values in rows.values()}
            if not ids or None in ids or index in referenced:
                continue
            if any(ownership[icon_id] != {index} for icon_id in ids):
                continue  # shared texture: replacing it would change another icon row
            if entries is not None and any(icon_id not in entries for icon_id in ids):
                continue
            family = {icon_id: self._icon_family(icon_id) for icon_id in ids}
            if any(value != 'itm' for value in family.values()):
                continue
            result.append(dict(key=index, value=index, resources=sorted(ids), icon_ids=sorted(ids)))
        return result

    def _icon_family(self, icon_id):
        if icon_id not in self.icon_families:
            try:
                self.icon_families[icon_id] = icon_family(_original_bytes(self.data, icon_id))
            except (KeyError, ValueError, OSError, struct.error):
                self.icon_families[icon_id] = None
        return self.icon_families[icon_id]

    def _appearance_candidates(self, weapon_only):
        if not _present(self.data, APPEARANCE_TABLE):
            raise ValueError('No appearance table in this extraction')
        rows = _original_rows(self.data, APPEARANCE_TABLE)
        raw = _original_bytes(self.data, APPEARANCE_TABLE)
        ownership = collections.defaultdict(set)
        decoded = {}
        for index, row in enumerate(rows):
            pointer = row.get('c00')
            if not isinstance(pointer, dict) or 'offset' not in pointer:
                continue
            ids = _appearance_ids(raw, pointer['offset'])
            if ids is None:
                continue
            decoded[index] = ids
            ownership[ids[0]].add(index)
            ownership[ids[1]].add(index)
        entries = getattr(self.data, 'entries', None)
        result = []
        for index, row in enumerate(rows):
            label = _plain(row.get('c01', ''))
            if '配信用ダミー' not in label:
                continue
            if weapon_only and not any(word in label for word in WEAPON_APPEARANCE_WORDS):
                continue
            if index not in decoded:
                continue
            model, texture = decoded[index]
            if ownership[model] != {index} or ownership[texture] != {index}:
                continue
            if entries is not None and (model not in entries or texture not in entries):
                continue
            result.append(dict(key=index, global_key=('appearance', index), value=index,
                               resources=(model, texture), model_id=model, texture_id=texture))
        return result

    def allocate_append(self, pool, name):
        extra_categories = {'furniture': 3, 'key_item': 6, 'bounty': 7}
        if pool in extra_categories:
            canonical, detail = 'item:' + pool, (pool, extra_categories[pool])
        else:
            canonical, detail = normalize_pool(pool)
        require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name), f'Invalid symbolic ID ${name}')
        if canonical.startswith('item:'):
            category = detail[1]
            rows = self.data.rows(ITEM_NAMES)
            value = max(VANILLA_ITEM_COUNT, len(rows))
            while value in self.reserved_items:
                value += 1
            require(value < 65535, 'No addressable appended item ID remains')
            pending = sum(a.properties.get('category') == category and a.pool.startswith('append:')
                          for a in self.allocations if a.value >= len(rows))
            stat_row = CATEGORY_SIZES[category] + sum(
                r['category'] == category for r in rows[VANILLA_ITEM_COUNT:]) + pending
            properties = dict(id=value, item_id=value, category=category, stat_row=stat_row,
                              stat_resources=[data_tools.STAT_BASES[category] + slot for slot in range(9)])
            self.reserve_item(value)
        else:
            require(canonical in RECIPE_POOLS and detail is not None,
                    'Append allocation requires an item pool or a specific crafting Life recipe pool')
            value = len(self.data.rows(detail))
            while (detail, value) in self.reserved_rows:
                value += 1
            require(value < 65535, 'No addressable appended recipe row remains')
            properties = dict(recipe_row=value, table=detail)
            self.reserve_row(detail, value)
        allocation = Allocation('append:' + canonical, name, value, properties, [])
        self.allocations.append(allocation)
        return allocation

    def allocate(self, pool, name, owner='mod'):
        if pool.startswith('append:'):
            return self.allocate_append(pool[7:], name)
        canonical, detail = normalize_pool(pool)
        require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name),
                f'Invalid symbolic ID ${name}; use letters, digits and underscores')
        kind = canonical if canonical in ('item_icon', 'weapon_appearance', 'gear_appearance') else (
            'item' if canonical.startswith('item:') else 'recipe')
        candidates = self._candidates(canonical, kind, detail)
        for candidate in candidates:
            slot_key = candidate.get('global_key', (canonical, candidate['key']))
            if slot_key in self.used_keys:
                continue
            if any(resource in self.reserved for resource in candidate['resources']):
                continue
            value = candidate['value']
            if kind == 'item':
                if value in self.reserved_items or any((base + slot, value) in self.reserved_rows
                                                       for base in (6702, ITEM_NAMES) for slot in range(9)):
                    continue
            elif kind == 'item_icon':
                if any((ICON_TABLES + slot, value) in self.reserved_rows for slot in range(9)):
                    continue
            elif kind in ('weapon_appearance', 'gear_appearance'):
                if (APPEARANCE_TABLE, value) in self.reserved_rows:
                    continue
            elif (candidate['table'], value) in self.reserved_rows:
                continue
            if kind == 'item':
                item_rows = _original_rows(self.data, ITEM_NAMES)
                category = item_rows[value].get('category')
                first = next(index for index, row in enumerate(item_rows)
                             if row.get('category') == category)
                properties = dict(id=value, item_id=value, category=category, stat_row=value - first,
                                  stat_resources=[base + slot for base in [data_tools.STAT_BASES[category]]
                                                  for slot in range(9) if _present(self.data, base + slot)])
                guards = []
                for slot in range(9):
                    if _present(self.data, 6702 + slot):
                        guards.append((6702 + slot, value, {'symbolic_id': _original_rows(self.data, 6702 + slot)[value]['symbolic_id']}))
                    if _present(self.data, ITEM_NAMES + slot):
                        guards.append((ITEM_NAMES + slot, value, {'category': category}))
            elif kind == 'item_icon':
                properties = dict(icon_index=value, icon_row=value, texture_ids=candidate['icon_ids'])
                if len(candidate['icon_ids']) == 1:
                    properties['texture_id'] = candidate['icon_ids'][0]
                guards = []
                for slot in range(9):
                    table = ICON_TABLES + slot
                    if _present(self.data, table):
                        guards.append((table, value, {'icon_id': _original_rows(self.data, table)[value]['icon_id']}))
            elif kind in ('weapon_appearance', 'gear_appearance'):
                properties = dict(appearance_row=value, model_id=candidate['model_id'],
                                  texture_id=candidate['texture_id'],
                                  model_resource=candidate['model_id'], texture_resource=candidate['texture_id'])
                name_value = _original_rows(self.data, APPEARANCE_TABLE)[value]['c01']
                guards = [(APPEARANCE_TABLE, value, {'c01': name_value})]
            else:
                properties = dict(recipe_row=value, table=candidate['table'],
                                  recipe_key=candidate.get('recipe_key'))
                guards = [(candidate['table'], value, {'rank_requirement': 16, 'unlock_rank': 16})]
            for id_, row, expect in guards:
                values = _original_rows(self.data, id_)
                require(row < len(values), f'Allocated slot {id_}:{row} is outside the verified pool')
                for key, expected in expect.items():
                    require(values[row].get(key) == expected,
                            f'Allocated slot {id_}:{row} no longer has the verified {key} guard')
            allocation = Allocation(canonical, name, value, properties, guards, candidate['resources'])
            self.used[canonical].add(candidate['key'])
            self.used_keys.add(slot_key)
            for resource in candidate['resources']:
                self.reserve_resource(resource, owner)
            for id_, row, expect in guards:
                self.guards.setdefault((id_, row), {}).update(expect)
            self.allocations.append(allocation)
            return allocation
        raise ValueError(f'No unused {pool} slot remains in the verified dummy pool')


class MergeState:
    """Ownership and conflict bookkeeping shared by every source in a stack.

    Existing SCR rows are merged at cell level: two mods may change disjoint columns of
    the same row, but the same cell may not be given two different values.  Appends are
    new rows, and replacing one whole texture/model/file/pack member is exclusive.
    """

    def __init__(self, data):
        self.data = data
        self.base_counts = {}
        self.created = {}
        self.cell_claims = {}
        self.row_owners = collections.defaultdict(set)
        self.table_changed = {}
        self.table_copies = {}
        self.direct_updates = {}
        self.member_updates = {}
        self.member_owners = {}
        self.shared_placements = collections.defaultdict(set)
        self.placement_bases = {}
        self.placement_groups = {}
        self.updates = {}
        self.allocations = []
        self.symbols = Symbols()
        self.allocator = Allocator(data)

    def base_count(self, id_):
        if id_ not in self.base_counts:
            self.base_counts[id_] = len(_original_rows(self.data, id_))
        return self.base_counts[id_]

    @staticmethod
    def _conflict(what, id_, owner, previous):
        raise ValueError(f'{what} conflict {id_}: {previous} and {owner}')

    def claim_table_edit(self, id_, owner):
        if id_ in self.direct_updates:
            self._conflict('Resource', id_, owner, self.direct_updates[id_])
        if id_ in self.member_owners:
            self._conflict('Resource', id_, owner, self.member_owners[id_])
        parent = self.data.entries.get(id_, {}).get('parent')
        if parent is not None and parent in self.direct_updates:
            self._conflict('Resource', id_, owner, self.direct_updates[parent])
        if id_ in self.shared_placements:
            self._conflict('Resource', id_, owner, next(iter(self.shared_placements[id_])))
        if id_ in self.member_updates:
            self._conflict('Parent resource', id_, owner, 'a member replacement')
        if id_ in self.table_copies and self.table_copies[id_] != owner:
            self._conflict('Table edit', id_, owner, self.table_copies[id_])
        self.table_changed.setdefault(id_, owner)

    def claim_row(self, id_, row, before, after, owner):
        if self.created.get((id_, row), owner) != owner:
            # A later source deliberately extends a row an earlier source appended.
            self.row_owners[(id_, row)].add(owner)
            return
        self.row_owners[(id_, row)].add(owner)
        for key in set(before) | set(after):
            if key == '_raw':
                continue  # preserved bytes are not a semantic cell
            old, new = before.get(key), after.get(key)
            if old == new:
                continue
            prior = self.cell_claims.get((id_, row, key))
            if prior is not None and prior[0] != owner and prior[1] != new:
                raise ValueError(f'Row conflict {id_}:{row} column {key}: '
                                 f'{prior[0]} and {owner} disagree')
            self.cell_claims[(id_, row, key)] = (owner, new)

    def created_row(self, id_, row, owner):
        self.created[(id_, row)] = owner
        self.row_owners[(id_, row)].add(owner)

    def observe_row(self, id_, row, after):
        """Rows/items a hard-coded edit used become unavailable to later allocations."""
        self.allocator.reserve_row(id_, row)
        if id_ in ITEM_TABLES:
            self.allocator.reserve_item(row)
        if id_ in ITEM_TABLES and isinstance(after.get('icon_index'), int):
            for slot in range(9):
                self.allocator.reserve_row(ICON_TABLES + slot, after['icon_index'])
        if ICON_TABLES <= id_ < ICON_TABLES + 9:
            for slot in range(9):
                self.allocator.reserve_row(ICON_TABLES + slot, row)
        for key in ('item_id', 'output_items', 'seasoning_items', 'ingredients',
                    'requested_item', 'alternate_requested_item', 'reward_item'):
            value = after.get(key)
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, int) and item not in (0xffff, 0xffffffff):
                    self.allocator.reserve_item(item)
        if id_ in STAT_TABLES and isinstance(after.get('u_0a'), int):
            self.allocator.reserve_row(APPEARANCE_TABLE, after['u_0a'])

    def claim_table_copy(self, id_, owner):
        if id_ in self.direct_updates or id_ in self.member_owners or id_ in self.shared_placements:
            self._conflict('Table copy', id_, owner, 'a whole-resource replacement')
        if id_ in self.member_updates:
            self._conflict('Table copy', id_, owner, 'a member replacement')
        parent = self.data.entries.get(id_, {}).get('parent')
        if parent is not None and parent in self.direct_updates:
            self._conflict('Table copy', id_, owner, self.direct_updates[parent])
        if id_ in self.table_copies and self.table_copies[id_] != owner:
            self._conflict('Table copy', id_, owner, self.table_copies[id_])
        others = {who for (resource, _), owners in self.row_owners.items() if resource == id_
                  for who in owners if who != owner}
        if others:
            raise ValueError(f'Table copy conflict {id_}: {owner} would overwrite row edits from '
                             f'{sorted(others)[0]}')
        self.table_copies[id_] = owner
        self.table_changed.setdefault(id_, owner)

    def claim_resource(self, id_, owner, kind):
        entry = self.data.entries.get(id_, {})
        parent = entry.get('parent')
        if id_ in self.member_owners:
            self._conflict(kind, id_, owner, self.member_owners[id_])
        if parent is not None:
            if parent in self.direct_updates:
                self._conflict(kind, id_, owner, self.direct_updates[parent])
            if id_ in self.table_copies or id_ in self.table_changed:
                self._conflict(kind, id_, owner, 'row/table edits')
            self.member_owners[id_] = owner
            self.member_updates.setdefault(parent, {})
            return parent
        if id_ in self.member_updates:
            self._conflict(kind, id_, owner, 'a member replacement')
        if id_ in self.direct_updates:
            self._conflict(kind, id_, owner, self.direct_updates[id_])
        if id_ in self.table_copies or id_ in self.table_changed:
            self._conflict(kind, id_, owner, 'row/table edits')
        if id_ in self.shared_placements:
            self._conflict(kind, id_, owner, 'a placement merge')
        self.direct_updates[id_] = owner
        return None

    def add_resource(self, id_, raw, owner, kind):
        reserved_owner = self.allocator.resource_owners.get(id_)
        if reserved_owner is not None and reserved_owner != owner:
            self._conflict(kind, id_, owner, f'an allocation reserved by {reserved_owner}')
        parent = self.claim_resource(id_, owner, kind)
        if parent is None:
            self.updates[id_] = raw
        else:
            self.member_updates[parent][id_] = (owner, raw)
        self.allocator.reserve_resource(id_)

    def claim_placement(self, id_, owner):
        if id_ in self.direct_updates or id_ in self.table_copies or id_ in self.table_changed:
            self._conflict('Placement', id_, owner, self.direct_updates.get(id_, self.table_copies.get(
                id_, self.table_changed.get(id_))))
        if id_ in self.member_owners or id_ in self.member_updates:
            self._conflict('Placement', id_, owner, 'a member replacement')
        self.shared_placements[id_].add(owner)
        self.allocator.reserve_resource(id_)

    def add_placement(self, id_, raw, owner):
        if id_ not in self.shared_placements:
            self.claim_placement(id_, owner)
        self.updates[id_] = raw

    def claim_placement_doc(self, id_, before, after, owner):
        """Cell ownership for binary placement files, keyed by placement UID."""
        def key(row):
            return row.get('uid', row.get('index'))

        old = {key(row): row for row in before['rows']}
        ignored = {'_raw', 'index', 'payload_offset', 'points_offset', 'conditions_offset'}
        for row in after['rows']:
            row_key = key(row)
            previous = old.get(row_key)
            if previous is None:
                continue  # appended rows are owned by the appending source
            for field in set(previous) | set(row):
                if field in ignored or previous.get(field) == row.get(field):
                    continue
                claim_key = (id_, f'row:{row_key}', field)
                prior = self.cell_claims.get(claim_key)
                if prior is not None and prior[0] != owner and prior[1] != row.get(field):
                    raise ValueError(f'Placement row conflict {id_}:{row_key} field {field}: '
                                     f'{prior[0]} and {owner} disagree')
                self.cell_claims[claim_key] = (owner, row.get(field))
        # Placement appends may both add rows to one map group.  Row membership is
        # unioned by fl_mod_content; only incompatible forced choices conflict.
        old_groups = {(group['map_id'], index): entry
                      for group in before['map_groups'] for index, entry in enumerate(group.get('groups', []))}
        for group in after['map_groups']:
            for index, entry in enumerate(group.get('groups', [])):
                previous = old_groups.get((group['map_id'], index))
                if previous is None:
                    continue
                if (previous.get('choice') not in (None, -1) and entry.get('choice') not in (None, -1)
                        and previous.get('choice') != entry.get('choice')):
                    raise ValueError(f'Placement map-group conflict {id_} map {group["map_id"]}: '
                                     f'{owner} changed an existing forced choice')

    def inject_guards(self, operation):
        row = operation.get('row')
        if row == 'append' or not isinstance(row, int):
            return
        for id_ in entry_ids(operation):
            guard = self.allocator.guards.get((id_, row))
            if not guard:
                continue
            expect = operation.setdefault('expect', {})
            for key, value in guard.items():
                if key in expect and expect[key] != value:
                    raise ValueError(f'Automatic guard for {id_}:{row}.{key} disagrees with the mod expect')
                expect[key] = value

    def finalize_resources(self, table_updates=None):
        """Fold member replacements and edited member tables back into their packs."""
        result = dict(self.updates)
        pending = collections.defaultdict(dict)
        for parent, members in self.member_updates.items():
            pending[parent].update({self.data.entries[id_]['path']: raw
                                    for id_, (_, raw) in members.items()})
        for id_, raw in (table_updates or {}).items():
            entry = self.data.entries[id_]
            parent = entry.get('parent')
            if parent is None:
                require(id_ not in result, f'Conflicting table and whole-resource replacements: {id_}')
                result[id_] = raw
                continue
            if id_ in self.member_updates.get(parent, {}):
                raise ValueError(f'Conflicting table edit and whole-resource replacement: {id_}')
            pending[parent][entry['path']] = raw
        for parent, members in pending.items():
            require(parent not in result, f'Conflicting parent and member replacements: {parent}')
            original = self.data.path(parent).read_bytes()
            require(archive.sha(original) == self.data.entries[parent]['sha256'],
                    f'Modified source pack {parent}')
            result[parent] = rebuild_pack(original, members)
            self.allocator.reserve_resource(parent)
        return result


def entry_ids(entry):
    values = entry.get('resources', [entry.get('resource')])
    require(isinstance(values, list) and values, 'Invalid resources')
    result = []
    for value in values:
        result.extend(value if isinstance(value, list) else [value])
    require(result and all(type(id_) is int for id_ in result), 'Invalid resources')
    return result


def copy_tables(data, copies, claim=None, owner=None):
    """Whole-table donor copies (`copies` whose target is schema-backed).

    The target takes the donor's complete SCR document (every section, row and preserved
    byte), e.g. a monster's full battle-parameter file into a reserved unit's leaf. Row
    edits listed in `edits` then apply on top, and the result goes through the same
    validation and round trip as any edited table. Returns the remaining (raw) copies.
    """
    schemas, rest = scr.schemas(), []
    for entry in copies:
        id_, base = entry.get('resource'), entry.get('base')
        if id_ not in schemas:
            rest.append(entry)
            continue
        require(type(base) is int and base in data.entries and id_ in data.entries,
                f'Unknown table copy {base} -> {id_}')
        require(base in schemas and schemas[base]['name'] == schemas[id_]['name'],
                f'Table copy {base} -> {id_} needs donor and target with the same schema')
        require(id_ not in data.changed and id_ != base, f'Resource {id_} is copied twice or onto itself')
        if claim is not None:
            claim.claim_table_copy(id_, owner)
        source_bytes(data, id_)
        source_bytes(data, base)
        donor = (data.original_document(base) if hasattr(data, 'original_document')
                 else data.document(base))
        document = copy.deepcopy(donor)
        document['resource_id'] = id_
        data.cache[id_] = document
        data.changed.add(id_)
    return rest


def terminate_monster_loot(data):
    """Keep the loot table in the shape its loader expects.

    0x332904 walks 6930 once: for monster IDs 0..274 it counts the rows of that monster's
    contiguous block, reading the monster ID of the row after each row. Blocks must stay
    in ascending (monster, level key) order. The shipped table ends with monster 271, so
    after its last row the loader already reads two bytes past the table; a block for
    272..274 appended at the end would let those bytes decide where it ends. A changed
    table therefore ends with exactly one terminator row (monster_id 0xffff, no drops),
    which no monster ID matches.
    """
    if MONSTER_LOOT not in data.changed:
        return
    rows = data.rows(MONSTER_LOOT)
    while rows and rows[-1]['monster_id'] == LOOT_END:
        rows.pop()
    require(rows, 'Loot table is empty')
    monsters = len(data.rows(MONSTER_NAMES))
    previous = (-1, -1)
    for n, row in enumerate(rows):
        key = (row['monster_id'], row['level_key'])
        require(key[0] < monsters, f'Loot row {n}: unknown monster {key[0]}')
        require(key > previous, f'Loot row {n}: {key} after {previous}; keep blocks contiguous and '
                'ascending by monster, then level key')
        previous = key
    end = copy.deepcopy(rows[-1])
    end.update(level_key=255, monster_id=LOOT_END, bounty_threshold=0, bounty_item=0xffffffff,
               **{f'drop_threshold_{i}': 0 for i in range(5)}, **{f'drop_item_{i}': 0xffffffff for i in range(5)})
    rows.append(end)


def validate_monsters(data):
    """Links fl_data.validate does not cover: monster -> unit row, spawn group -> monster."""
    schemas = scr.schemas()
    groups = [id_ for id_ in data.changed if schemas.get(id_, {}).get('name') == 'spawn_groups']
    if any(id_ in data.changed for id_ in MONSTER_TABLES):
        units = len(data.rows(UNIT_NAMES))
        require(len({len(data.rows(id_)) for id_ in MONSTER_TABLES}) == 1,
                'All monster name slots need the same row count')
        for id_ in MONSTER_TABLES:
            for n, row in enumerate(data.rows(id_)):
                require(row['unit_index'] < units or row['unit_index'] == 0xffff,   # 0xffff: no unit (cut rows)
                        f'Monster {n} in {id_}: unit {row["unit_index"]} out of range')
    if groups:
        monsters = len(data.rows(MONSTER_NAMES))
        for id_ in groups:
            for n, row in enumerate(data.rows(id_)):
                for monster, weight in zip(row['monsters'], row['weights']):
                    require(monster == 0xffff and weight == 0 or monster < monsters,
                            f'Spawn group {id_}:{n}: invalid monster {monster} (weight {weight})')


def icon_family(raw):
    """'itm' for icn_itm401_0001_10default: the UI draws each icon family with its own cell
    geometry (items 64x64, command prompts 128x32, ...), whatever the texture header says."""
    name = ztex.parse(raw)['images'][0]['name']
    return name[4:7] if name.startswith('icn_') else None


def validate_item_icons(data):
    """Every item's icon must be an item-family (icn_itm) icon texture; a square texture in
    another family's slot is drawn with that family's cell and comes out distorted."""
    families = {}
    for slot in range(9):
        if ITEM_NAMES + slot not in data.changed:
            continue
        icons = data.rows(ICON_TABLES + slot)
        for n, row in enumerate(data.rows(ITEM_NAMES + slot)):
            icon_id = icons[row['icon_index']]['icon_id']
            if icon_id not in families:
                families[icon_id] = icon_family(data.path(icon_id).read_bytes())
            require(families[icon_id] == 'itm', f'Item {n} uses icon row {row["icon_index"]} (texture {icon_id}, '
                    f'family {families[icon_id]!r}); item icons must be icn_itm textures')


def edit(data, operation, claim=None, owner=None):
    values = operation.get('resources', [operation.get('resource')])
    require(isinstance(values, list) and values, 'Invalid resources')
    ids = []
    for value in values:
        ids.extend(value if isinstance(value, list) else [value])
    require(ids and all(type(i) is int for i in ids), 'Invalid resources')
    localized = operation.get('localized', {})
    require(all(isinstance(v, list) and len(v) == len(ids) for v in localized.values()),
            'Each localized column needs exactly one value per listed resource')
    for n, id_ in enumerate(ids):
        rows = data.rows(id_)
        at = operation['row']
        at = len(rows) if at == 'append' else at
        require(type(at) is int and 0 <= at <= len(rows), f'Invalid row {at} in {id_}')
        append = at == len(rows)
        for key, value in operation.get('expect', {}).items():
            require(not append and rows[at].get(key) == value, f'Expectation failed: {id_}:{at}:{key}')
        source = operation.get('copy_from', at)
        require(type(source) is int and 0 <= source < len(rows), f'Invalid template in {id_}')
        row = copy.deepcopy(rows[source])
        values = dict(operation.get('set', {}))
        values.update((key, column[n]) for key, column in localized.items())
        for key, value in values.items():
            require(key in row and key != '_raw', f'Unknown/edit-protected column {id_}:{key}')
            row[key] = value
        if append:
            if claim is not None:
                claim.claim_table_edit(id_, owner)
            rows.append(row)
            if claim is not None:
                claim.created_row(id_, at, owner)
                claim.observe_row(id_, at, row)
        else:
            if claim is not None:
                claim.claim_table_edit(id_, owner)
                claim.claim_row(id_, at, rows[at], row, owner)
            rows[at] = row
            if claim is not None:
                claim.observe_row(id_, at, row)
        data.changed.add(id_)


def rebuild_pack(raw, replacements):
    """Rebuild one named FL pack, preserving paths, alignment and record metadata."""
    members = archive.parse_pack(raw)
    values = [replacements.get(m['name'], archive.span(raw, m['offset'], m['size'])) for m in members]
    out, records = bytearray(raw[:20]), bytearray()
    for member, value in zip(members, values):
        out.extend(b'\0' * (archive.align(len(out), member['alignment']) - len(out)))
        offset = len(out)
        out.extend(value)
        name_offset = len(out)
        out.extend(member['name'].encode('ascii') + b'\0')
        out.extend(b'\0' * (archive.align(len(out), 4) - len(out)))
        record = bytearray(raw[member['record']:member['record'] + 20])
        struct.pack_into('<III', record, 8, len(value), name_offset, offset)
        records.extend(record)
    struct.pack_into('<I', out, 16, len(out))
    out.extend(records)
    struct.pack_into('<I', out, 4, len(out) - 20)
    archive.parse_pack(out)
    return bytes(out)


def source_bytes(data, id_):
    raw = data.path(id_).read_bytes()
    require(archive.sha(raw) == data.entries[id_]['sha256'], f'Source resource {id_} was modified')
    return raw


def build_texture(data, source, spec, base_id, cache):
    """A ZTEX built from a base container (names, flags, dye-colour records kept) with every
    image replaced by the mod's PNG (own art), encoded in the base image's or the given format."""
    raw = source_bytes(data, base_id)
    info = ztex.parse(raw)
    width, height, rgba = ztex.png_read(archive.safe_path(source, spec['png']))
    images = []
    for image in info['images']:
        if image['name'].startswith('icn_'):
            require((width, height) == (image['width'], image['height']),
                    f'Icon {image["name"]} is {image["width"]}x{image["height"]}; the UI cell has that size')
        fmt = spec.get('format', image['format'])
        mips = spec.get('mips', image['mips'])
        require(fmt in ztex.FORMAT_IDS, f'Unknown texture format {fmt}')
        key = (spec['png'], fmt, mips)
        if key not in cache:  # ETC1 encoding is slow; encode each variant once
            cache[key] = ztex.image_data(rgba, width, height, fmt, mips)
        images.append(dict(name=image['name'], width=width, height=height, format=fmt, mips=mips, data=cache[key]))
    built = ztex.build(images, info['flags'], info['extra'])
    require(ztex.decode(built)[:2] == (width, height), 'Texture verification failed')
    return built


def build_model(data, source, spec, base_id):
    """A ZMDL built from a base model (skeleton, attachment bones, material kept): `mesh`
    replaces its geometry with the mod's mesh JSON (own data, see mods/wooden-sword/art),
    `glb` imports a binary glTF 2.0 scene (.glb) into the donor model,
    `texture_names` ({old: new}) points its materials at other texture names, e.g. a donor
    model copied for a reserved unit that should use that unit's own texture name."""
    raw = source_bytes(data, base_id)
    require('mesh' in spec or 'glb' in spec or 'texture_names' in spec,
            'A model entry needs mesh and/or texture_names (or glb)')
    built = raw
    if 'mesh' in spec:
        mesh = json.loads(archive.safe_path(source, spec['mesh']).read_text(encoding='utf-8'))
        require(mesh.get('format') == 'fl-mesh-v1', 'Unsupported mesh format')
        built = zmdl.replace_mesh(built, spec.get('mesh_index', 0), mesh['vertices'], mesh['triangles'])
        model = zmdl.parse(built)
        require(model['meshes'][spec.get('mesh_index', 0)]['vertex_count'] == len(mesh['vertices']),
                'Model verification failed')
    if 'glb' in spec:
        glb_data = archive.safe_path(source, spec['glb']).read_bytes()
        built, report = zmdl.import_gltf(built, glb_data, mesh_map=spec.get('mesh_map'),
                                         bone=spec.get('bone'), unmapped=spec.get('unmapped', 'hide'),
                                         up=spec.get('up'))
    if 'texture_names' in spec:
        built = zmdl.rename_textures(built, spec['texture_names'])
        textures = {m['texture'] for m in zmdl.parse(built)['materials']}
        require(set(spec['texture_names'].values()) <= textures, 'Model verification failed')
    return built


def output_paths(extraction, output, replace):
    extraction, output = Path(extraction).resolve(), Path(output).resolve()
    require(not output.exists() or (replace and (output / 'overlay.json').is_file()),
            'Output must be a new directory (or an earlier overlay build, with --replace)')
    require(output != extraction and extraction not in output.parents and output not in extraction.parents,
            'Output must be separate from the source extraction')
    require('dumps' not in output.parts, 'Output cannot be under dumps/')
    return extraction, output


def source_digest(source):
    """Stable digest of every input file, so a stack records exactly what it built."""
    digest = hashlib.sha256()
    for path in sorted(p for p in source.rglob('*') if p.is_file() and not p.is_symlink()):
        digest.update(path.relative_to(source).as_posix().encode('utf-8') + b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def allocation_requests(spec):
    """`allocate` entries in declaration order: (pool, '$symbol' or 'auto')."""
    allocate = spec.get('allocate', {})
    if isinstance(allocate, list):
        require(all(isinstance(pool, str) for pool in allocate), 'Invalid allocate list')
        return [(pool, 'auto') for pool in allocate]
    require(isinstance(allocate, dict), '`allocate` must be an object or a list of pool names')
    result = []
    for pool, values in allocate.items():
        for value in values if isinstance(values, list) else [values]:
            if value is True or value == 'auto':
                result.append((pool, 'auto'))
            elif isinstance(value, str) and value.startswith('$'):
                result.append((pool, value))
            elif isinstance(value, dict) and isinstance(value.get('symbol'), str):
                require(type(value.get('append', False)) is bool, 'Allocation append must be a boolean')
                result.append(('append:' + pool if value.get('append') else pool, value['symbol']))
            else:
                raise ValueError(f'Invalid allocation {pool!r}: use "$symbol", "auto" or true')
    return result


def _source_spec(source):
    spec = json.loads((source / 'mod.json').read_text(encoding='utf-8'))
    require(isinstance(spec, dict) and spec.get('format') == 'fl-mod-source-v1',
            'Unsupported mod source format')
    return spec


def _apply_source(state, source, order):
    spec = _source_spec(source)
    owner = f"{spec.get('name', source.name)} ({source.name}, source {order + 1})"
    data = state.data
    symbols = Symbols(state.symbols)
    state.symbols = symbols
    local_names = set()
    before = len(state.allocator.allocations)
    for pool, value in allocation_requests(spec):
        if value == 'auto':
            value = auto_symbol(pool, local_names)
        require(value.startswith('$'), f'Invalid symbolic ID {value!r}')
        name = value[1:]
        symbols.bind(name, state.allocator.allocate(pool, name, owner))
        local_names.add(value)
    record = dict(order=order, name=spec['name'], format=spec['format'],
                  folder=source.name, digest=source_digest(source))
    state.allocations.extend(allocation.as_json(order) for allocation in
                             state.allocator.allocations[before:])

    resolved = resolve_value({key: value for key, value in spec.items() if key != 'allocate'}, symbols)
    raw_copies = copy_tables(data, resolved.get('copies', []), claim=state, owner=owner)
    for operation in resolved.get('edits', []):
        state.inject_guards(operation)
        edit(data, operation, claim=state, owner=owner)

    texture_cache = {}
    for entry in resolved.get('textures', []):
        for id_ in entry_ids(entry):
            resource_target(data, id_)
            require(id_ not in scr.schemas(), 'Only whole non-table resources can be replaced')
            base = entry.get('base', id_)
            require(type(base) is int, f'Invalid texture base for {id_}')
            state.add_resource(id_, build_texture(data, source, entry, base, texture_cache),
                               owner, 'Texture')
    for entry in resolved.get('models', []):
        for id_ in entry_ids(entry):
            resource_target(data, id_)
            require(id_ not in scr.schemas(), 'Only whole non-table resources can be replaced')
            base = entry.get('base', id_)
            require(type(base) is int, f'Invalid model base for {id_}')
            state.add_resource(id_, build_model(data, source, entry, base), owner, 'Model')

    content.apply_merged(data, source, dict(resolved, copies=raw_copies), state, owner, source_bytes)

    paths = {entry['path']: id_ for id_, entry in data.entries.items()}
    for key, filename in resolved.get('files', {}).items():
        if isinstance(key, int):
            id_ = key
        elif isinstance(key, str) and key.isdecimal():
            id_ = int(key)
        elif key in paths:
            id_ = paths[key]
        else:
            raise ValueError(f'Unknown resource {key!r}')
        resource_target(data, id_)
        require(id_ not in scr.schemas(), 'Use row edits for schema-backed SCR tables so validation cannot be bypassed')
        state.add_resource(id_, archive.safe_path(source, filename).read_bytes(), owner, 'File')
    return record


def _finish_build(state, extraction, output, sources, name):
    data = state.data
    terminate_monster_loot(data)
    validate_runtime_layout(data)
    validate_item_icons(data)
    validate_monsters(data)
    validation = data_tools.validate(data)
    require(not validation['errors'], f'Cross-table validation failed: {validation["errors"][:5]}')
    table_updates = {}
    for id_ in sorted(data.changed):
        original = data.path(id_).read_bytes()
        require(archive.sha(original) == data.entries[id_]['sha256'], f'Source resource {id_} was modified')
        raw = scr.build(data.document(id_))
        require(scr.build(scr.dump(raw, id_)) == raw, f'SCR round trip failed: {id_}')
        if raw != original:
            table_updates[id_] = raw
    require(not (set(table_updates) & (set(state.updates) | set(state.member_updates))),
            'A table has both row edits and a whole-resource replacement')
    updates = state.finalize_resources(table_updates)
    require(1 not in updates, 'Relationship-index edits are runtime-owned')
    validate_appended_resources(updates, data.manifest['count'])
    virtual_sizes = {}
    for group in data.manifest['relations']:
        if group['parent'] in updates:
            members = archive.parse_pack(updates[group['parent']])
            require(len(members) == len(group['children']), 'Cannot add/remove pack members')
            for id_, member in zip(group['children'], members):
                require(member['name'] == data.entries[id_]['path'], 'Cannot rename pack members')
                virtual_sizes[str(id_)] = member['size']
    count = data.manifest['count']
    with (extraction / '.fl_archive/original.bin').open('rb') as preserved:
        header = preserved.read(8 + 13 * count)
        preserved.seek(0, 2)
        original_size = preserved.tell()
    require(original_size == data.manifest['archive_size'], 'Source archive size mismatch')
    manifest = dict(format='fl-resource-overlay-v1', name=name, program_id='0004000000113100',
                    archive_count=count, archive_size=original_size, header_fnv32=fnv32(header),
                    resources=[], virtual_sizes=virtual_sizes, validation=validation,
                    sources=sources, allocations=state.allocations)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only a complete build, never a half-written overlay directory.
    with tempfile.TemporaryDirectory(prefix='.fl-mod-', dir=output.parent) as temp:
        staging = Path(temp) / 'overlay'
        (staging / 'resources').mkdir(parents=True)
        for id_, raw in sorted(updates.items()):
            require(id_ in data.manifest['physical_ids'] or data.manifest['count'] <= id_ < 65535,
                    'Replacement is not a physical archive resource')
            stored = archive.compress_lz11(raw)
            require(archive.decompress_nintendo(stored)[0] == raw, 'Compression verification failed')
            filename = f'resources/{id_:05d}.lz'
            (staging / filename).write_bytes(stored)
            manifest['resources'].append(dict(id=id_, size=len(raw), stored_size=len(stored),
                                               compression=1, file=filename, sha256=archive.sha(raw)))
        (staging / 'overlay.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            staging_old = Path(temp) / 'previous'
            output.rename(staging_old)  # removed with the temporary directory
        staging.rename(output)
    return manifest


def build_stack(extraction, output, sources, replace=False):
    """Build one merged `fl-resource-overlay-v1` from several source mods, in load order."""
    extraction, output = output_paths(extraction, output, replace)
    sources = [Path(source).resolve() for source in sources]
    require(sources, 'build-stack needs at least one mod source')
    data = ModData(extraction)
    state = MergeState(data)
    records = []
    for order, source in enumerate(sources):
        records.append(_apply_source(state, source, order))
    name = ' + '.join(record['name'] for record in records)
    return _finish_build(state, extraction, output, records, name)


def build(extraction, source, output, replace=False):
    return build_stack(extraction, output, [source], replace)


def check_stack(folders):
    """Check independently built overlays; resources never silently override each other."""
    owners, virtual, base, names = {}, {}, None, []
    roots = sorted(Path(p).resolve() for p in folders)
    require(len(set(roots)) == len(roots), 'Duplicate overlay directory')
    for root in roots:
        manifest = json.loads((root / 'overlay.json').read_text(encoding='utf-8'))
        require(manifest.get('format') == 'fl-resource-overlay-v1', f'Unsupported overlay: {root}')
        fingerprint = tuple(manifest[k] for k in ('program_id', 'archive_count', 'archive_size', 'header_fnv32'))
        require(base is None or fingerprint == base, f'Overlay base mismatch: {root}')
        base = fingerprint
        owner = f"{manifest['name']} ({root})"
        require(isinstance(manifest.get('resources'), list) and manifest['resources'], f'Empty overlay: {root}')
        for entry in manifest['resources']:
            id_ = entry['id']
            require(type(id_) is int and 0 <= id_ < 65535 and id_ != 1,
                    f'Invalid/protected resource {id_}: {owner}')
            require(id_ not in owners and id_ not in virtual,
                    f'Resource conflict {id_}: {owners.get(id_, virtual.get(id_))} and {owner}')
            owners[id_] = owner
        validate_appended_resources([entry['id'] for entry in manifest['resources']], manifest['archive_count'])
        for key in manifest['virtual_sizes']:
            id_ = int(key)
            require(id_ not in virtual and id_ not in owners,
                    f'Virtual resource conflict {id_}: {virtual.get(id_, owners.get(id_))} and {owner}')
            virtual[id_] = owner
        names.append(manifest['name'])
    return dict(names=names, resources=len(owners))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('build')
    command.add_argument('extraction', type=Path)
    command.add_argument('source', type=Path)
    command.add_argument('output', type=Path)
    command.add_argument('--replace', action='store_true', help='overwrite an earlier overlay build at output')
    command = commands.add_parser('build-stack', help='merge several source mods into one overlay')
    command.add_argument('extraction', type=Path)
    command.add_argument('output', type=Path)
    command.add_argument('sources', type=Path, nargs='+')
    command.add_argument('--replace', action='store_true', help='overwrite an earlier overlay build at output')
    command = commands.add_parser('check-stack', help='check multiple overlay manifests for resource conflicts')
    command.add_argument('overlays', type=Path, nargs='+')
    args = parser.parse_args()
    if args.command == 'check-stack':
        result = check_stack(args.overlays)
        print(f"Stack OK: {', '.join(result['names'])}; {result['resources']} resources (path order)")
        return
    if args.command == 'build-stack':
        manifest = build_stack(args.extraction, args.output, args.sources, args.replace)
    else:
        manifest = build(args.extraction, args.source, args.output, args.replace)
    print(f"Built {manifest['name']}: {len(manifest['resources'])} resources; "
          f"{sum(r['stored_size'] for r in manifest['resources']):,} bytes; validation passed")


if __name__ == '__main__':
    main()
