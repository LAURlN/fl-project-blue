#!/usr/bin/env python3
"""Regenerate tools/schemas/*.json from an extracted archive plus the curated names below.

The column layout (type, offset, array length, bit fields) is read from the real SCR
column tables, so it is exact. Names, confidence and notes are our inference: edit the
CURATED table below, rerun, and review the diff. Reads game data, writes only schemas.

    python3 -I tools/make_schemas.py extracted/fl_eu/archive

Confidence: "high" = confirmed by cross-table links or by game code reading the field;
"medium" = strong pattern but not proven; "uncertain" = a guess or just a label.
"""
import importlib.util
import json
from pathlib import Path
import sys


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scr = load('fl_scr')
H, M, U = 'high', 'medium', 'uncertain'
SLOTS9 = lambda base: list(range(base, base + 9))   # jp, es-LA?, fr-CA?, de, en, es, fr, it, en-GB

# Each entry: file name, resource IDs, {column key: (name, confidence, note)}.
# Column key: byte offset, or (offset, shift) for a bit field. Unlisted columns are named
# automatically ("u_<offset>" / "bits_<offset>_<shift>") and marked uncertain.
CURATED = [
    ('item_symbols', SLOTS9(6702), {
        0: ('symbolic_id', H, 'ID_Item_<group>_<serial>_<variant> string; same row order as items. '
                              'Some original IDs repeat; new IDs should be unique.')}),
    ('items', SLOTS9(6792), {
        0: ('name', H, 'Localised item name. Placeholder rows keep Japanese names even in Western slots.'),
        4: ('sort_key', M, 'Orders items inside a category (weapons 0..4 = weapon kind; others ascend).'),
        6: ('variant', U, 'Meaning unresolved; preserve.'),
        8: ('category', H, '0 weapons 153, 1 armour 750, 2 tools 175, 3 furniture 399, 4 consumables 623, '
                           '5 materials 459, 6 key items 30, 7 bounties 146. Rows are grouped by category; code '
                           'reads this byte at row+8.'),
        9: ('item_type', M, 'Sub-kind (85 sword, 105 helmet, 111 shield, 92 pickaxe, 26 water, 118 generic).'),
        10: ('required_level', M, '0 = none; 5..100 otherwise (Origin Island clothing uses 30-40).'),
        11: ('stack_limit', H, '1 for gear/furniture, 99 for consumables/materials.'),
        12: ('icon_index', H, 'Row in the icon table (ids 8686-8694, 4995 rows); code reads this halfword at row+12. '
                              'Placeholder items use 1 ("Dummy").'),
        14: ('quality_flag', U, '0 or 3.'),
        15: ('equip_slot', M, 'Equipment slot / tool kind (16 shield, 17 helmet, 33 talisman, 41 pickaxe); 255 = n/a.'),
        16: ('u_16', U, '1095/1096 (922 key items, 1145-1151 bounties). Not a DLC flag.'),
        18: ('related_index', U, '65535 none; furniture object index; mirrors u_16 for tools/key items.'),
        (20, 0): ('tier', U, '0..5, 5 on most placeholder/junk rows.'),
        (20, 4): ('flag_20_4', U, '1 on almost all real items.'),
        (20, 5): ('sell_price', H, 'Dosh, 27-bit packed. HP Potion 30, Healweed 5.'),
        (24, 0): ('buy_price', H, 'Dosh, 27-bit packed at byte 24 bit 0. HP Potion 60.'),
        (24, 27): ('flag_24_27', U, 'Set on key items.'),
        (24, 28): ('flag_24_28', U, '1 on real items; 0 on placeholders and bounties.'),
        (24, 29): ('flag_24_29', U, 'Observed 0 on part of equipment incl. Origin Island pieces.'),
        (24, 30): ('flag_24_30', U, '1 on real tradable items.'),
        (24, 31): ('flag_24_31', U, '1 on real tradable items.')}),
    ('item_sources', SLOTS9(6801), {
        0: ('source_count', U, ''),
        4: ('source_1', M, 'Acquisition / authoring text (shop, drop). Contains Japanese tags such as 5_神島 '
                           'on Origin Island gear.'),
        8: ('source_2', M, ''), 12: ('source_3', M, ''), 16: ('source_4', M, '')}),
    ('item_descriptions', SLOTS9(6810), {0: ('description', H, 'Same row order as items; \\n shown as control tokens.')}),
    ('weapon_stats', SLOTS9(6720), {0: ('attack', M, 'Squire/Bronze/Iron/Silver sword = 6/12/20/28; row order = weapon rows of items')}),
    ('armour_stats', SLOTS9(6729), {0: ('scale_f32_bits', U, 'Raw float bits (1.0).'), 4: ('defence', M, 'Value 2 on the first caps; exact physical/magic split unresolved.')}),
    ('tool_stats', SLOTS9(6738), {}),
    ('furniture_stats', SLOTS9(6747), {}),
    ('consumable_stats', SLOTS9(6756), {}),
    ('material_stats', SLOTS9(6765), {}),
    ('key_item_stats', SLOTS9(6774), {}),
    ('bounty_stats', SLOTS9(6783), {
        4: ('drop_rates', H, 'Percent chance of each drop slot; the three values sum to 100.'),
        12: ('drop_items', H, 'Item IDs dropped by this bounty target; 0xffffffff = none. Rows parallel the bounty block of items.')}),
    ('recipes', list(range(8388, 8393)), {
        0: ('recipe_key', U, 'Not unique (blacksmith filler rows repeat 33000); do not use as a primary key.'),
        2: ('difficulty', M, 'Crafting difficulty; grows with the rank/ingredient tier.'),
        4: ('u_04', U, '7/10/15/20.'), 6: ('u_06', U, ''), 8: ('u_08', U, ''), 10: ('u_0a', U, ''), 12: ('u_0c', U, ''),
        14: ('experience', M, 'Life experience for crafting.'),
        16: ('work_parameters', U, 'Two equal halfwords (minigame length?).'),
        20: ('u_14', U, ''),
        21: ('rank_requirement', M, 'Rank of the Life needed; 16 = no rank (default/filler rows), 15 = special.'),
        22: ('output_quantity', M, '1 in every row.'),
        23: ('quality_mode', M, '1 = row yields four quality tiers.'),
        24: ('allow_extra_material', M, ''),
        25: ('ingredient_quantities', H, 'Parallel to ingredients.'),
        28: ('output_items', H, 'Item IDs per quality tier (normal, good, great, perfect); 65535 = unused.'),
        36: ('seasoning_items', M, 'Cooking only: salt, ginger, butter, pepper... 65535 elsewhere.'),
        44: ('ingredients', H, 'Up to three item IDs; 65535 = unused.'),
        50: ('u_32', U, '169 default; otherwise 10-149 grouped by output kind.'),
        52: ('category_tags', U, 'Up to four tags (0 swords, 2/5 shields, 5 armour, 6/9 tools, 3/4/11 clothes); NOT Life IDs.'),
        60: ('workbench', M, 'Workbench / station variant (differs per recipe table).'),
        62: ('category_icon_index', H, 'Icon-table row 4593-4612 = crafting category icon ("Synthetic alchemy medicine"...).'),
        64: ('unlock_rank', M, 'Life rank at which the recipe is learned (1..10, 16 none).'),
        66: ('required_flag', H, 'Event flag (table 5417) that gates the recipe; 1963 = Origin Island expansion owned.')}),
    ('side_quests', [8715], {
        0: ('dialogue_base_resource', H, 'JP dialogue base = 29062 + 9*row; the per-language slot adds 0..8.'),
        4: ('chapter_group', M, '0..3 (3 = post-game / Ancient content).'),
        6: ('client_npc', U, 'NPC index; same for all quests of one client.'),
        8: ('start_map', U, 'Index into the map table (5966-5973).'),
        10: ('end_map', U, ''),
        12: ('requested_item', H, 'Item ID, 0xffffffff none.'),
        16: ('alternate_requested_item', M, 'Alternative acceptable item.'),
        20: ('requested_quality', H, '255 any, 1 good quality...'),
        22: ('requested_monster', U, 'Set instead of requested_item on slaying quests.'),
        24: ('requested_quantity', H, ''),
        28: ('reward_item', H, 'Item ID, 0xffffffff none.'),
        32: ('reward_quantity', H, ''),
        36: ('reward_dosh', H, '0xffffffff none.'),
        40: ('reward_points', U, '10..1520, grows with quest level (stars/bliss?).'),
        42: ('u_2a', U, 'Always 0.'),
        44: ('prerequisite_quest', H, 'Row index of the quest that must be done first, 65535 none.'),
        46: ('required_story_flag', H, 'Event flag (5417); 1931/1932 = chapter 8 completion labels.'),
        48: ('minimum_level', M, ''),
        49: ('u_31', U, '100/50/30/10/0.')}),
    ('side_quest_text', SLOTS9(32662), {0: ('title', H, ''), 4: ('request_text', H, 'Request dialogue summary.')}),
    ('life_challenges', [5810] + list(range(5820, 5828)), {
        0: ('title', H, ''),
        4: ('objective_type', M, '0 none, 7 craft item, 9 catch/bring item, 10 craft N of a group...'),
        6: ('objective_parameters', M, 'Type-dependent (item index or group id, count); 65535 unused.'),
        22: ('life_id', M, 'Life namespace 0..20 incl. cut Lives (1 Treasure Hunter, 20 Farmer).'),
        23: ('rank', M, '255 none.')}),
    ('life_challenge_descriptions', SLOTS9(5811), {
        0: ('objective_text', H, 'Objective sentence, e.g. "Make 5 items of Origin Island clothing".'),
        4: ('prerequisite', U, '65535 none.'),
        8: ('reward_points', M, '100..3000; 100 on placeholder rows.'),
        10: ('rank', M, 'Matches life_challenges.rank.'),
        12: ('active', U, '1 on real, localised challenges; 0 on cut placeholders.'),
        14: ('u_0e', U, ''),
        16: ('extra_text', U, 'Second text pointer (mostly empty).')}),
    ('story_progression_text', SLOTS9(5419), {0: ('chapter_label', H, '174 rows of chapter / debug event labels.')},
     lambda i: f'event_label_{i:02d}'),
    ('event_flags', [5417], {0: ('label', H, '4350 flag labels (debug text); row 1963 = Origin Island/EX patch purchased.')}),
    ('icons', SLOTS9(8686), {
        0: ('icon_id', U, 'Opaque id (13856...); equal across slots.'),
        4: ('name', H, 'Icon name; indexed by items.icon_index and recipes.category_icon_index.')}),
    ('map_spawn_index', [8695], {
        0: ('map_id', H, 'Map-name row ID; searched by 0x3d5ae0, not row-indexed.'),
        4: ('spawn_table_resource', H, 'Per-area monster spawn-group SCR. Loaded by 0x3d6174/0x3d5ae0.')}),
    ('spawn_groups', list(range(6957, 8055)), {
        0: ('label', H, 'Authoring label; bracketed levels and NIGHT are descriptive, not executable conditions.'),
        4: ('monsters', H, 'Eight monster-definition indexes (6920/6940-6947); 65535 unused.'),
        20: ('weights', H, 'Parallel selection weights; runtime 0x3d65d0 reads these.'),
        28: ('scale_f32_bits', M, 'Float bits, usually 1.0; precise application untraced.'),
        32: ('boss_slot', H, 'Signed byte; -1/255 normal, otherwise special boss slot (0x3d544c).'),
        33: ('u_21', U, 'Nonzero sets a spawned-unit flag at runtime; preserve.')}),
    ('monster_loot', [6930], {
        0: ('level_key', M, 'Level/special-variant key; entries grouped by monster_id.'),
        2: ('monster_id', H, 'Monster definition index; contiguous ascending blocks walked by 0x332904, which reads the '
                             'monster ID of the row after each row. 0xffff = terminator row (fl_mod appends one to a changed table).'),
        4: ('drop_threshold_0', M, 'Byte probability/threshold; 77/255 is about 30%, exact roll comparison untraced.'),
        5: ('drop_threshold_1', M, ''), 6: ('drop_threshold_2', M, ''),
        7: ('drop_threshold_3', M, ''), 8: ('drop_threshold_4', M, ''),
        9: ('bounty_threshold', U, 'Often 255 on bounty-carrying monsters.'),
        12: ('drop_item_0', H, 'Item ID, 0xffffffff none.'),
        16: ('drop_item_1', H, 'Item ID, 0xffffffff none.'),
        20: ('drop_item_2', H, 'Item ID, 0xffffffff none.'),
        24: ('drop_item_3', H, 'Item ID, 0xffffffff none.'),
        28: ('drop_item_4', H, 'Item ID, 0xffffffff none.'),
        32: ('bounty_item', M, 'Bounty item ID; category-local row in bounty_stats describes turn-in rewards.')}),
    ('monster_names', [6920] + list(range(6940, 6948)), {
        0: ('name', H, 'Monster definition name; row is the ID used by spawn groups. 6920 Japanese; 6940-6947 are '
                       'identical developer English/romanised names. Players see the unit name (unit_resources 8706-8713/8719).'),
        4: ('unit_index', H, 'Row in unit_resources; not necessarily monster ID + 1.'),
        6: ('u_06', U, '')}),
    ('unit_resources', list(range(8706, 8714)) + [8719], {
        0: ('resources', H, '17 resource IDs; slot meanings documented in phase2-maps-enemies.md.'),
        68: ('name', H, 'Display name; includes monsters, NPCs, props and other units. This is the name players see for a '
                        'monster (8706 es-419, 8707 fr-CA, 8708 de, 8709 en, 8710 es, 8711 fr, 8712 it, 8713 en-GB, 8719 ja).'),
        72: ('unit_kind', M, 'Observed 2 on mon, 4 on bnp, and other values for NPC/objects.'),
        73: ('u_49', U, ''), 74: ('u_4a', U, '')}),
    ('map_links', [5965], {
        0: ('map_pair', M, 'Two map table indexes the link joins.'),
        8: ('label', M, 'Route label such as "_001 <-> downtown".')}),
    ('map_names', list(range(5966, 5974)), {
        0: ('name', H, 'Localised map name; (unused) rows keep Japanese.'),
        4: ('map_label', H, 'NormalMap_NNN (field/dungeon) or HouseMap_NNN (interior) resource key.'),
        12: ('reserved', U, 'Four 0xffffffff.'),
        28: ('position_x_f32', U, 'IEEE-754 bits; with y/z a point such as (20, 0, -6) (entry/spawn?).'),
        32: ('position_y_f32', U, ''), 36: ('position_z_f32', U, ''),
        40: ('param_a_f32', U, 'Second float triple, e.g. (8, 30, 40) (camera/view limits?).'),
        44: ('param_b_f32', U, ''), 48: ('param_c_f32', U, ''),
        52: ('bundle_index', H, 'Row in map resource table 8716.'),
        55: ('bgm_day', M, 'Index in BGM table 8505 family; 255 none/inherit.'),
        56: ('bgm_night', M, 'Night BGM index; Castele 33, East Plains 34, shop 56.'),
        62: ('script_row', M, 'Usually map script association row minus one in 8697; 65535 occurs on special maps. Search explicit kind/map fields.')}),
    ('map_resources', [8716], {
        0: ('resources', H, 'Ten archive IDs per map (model, collision, ...); 0xffffffff absent.'),
        40: ('variants_pointer', U, 'Opaque nested record kept at its original section offset.'),
        44: ('related_map', U, '')}),
]


def build_schema(root, name, ids, curated, namer=None):
    manifest = json.loads((root / '.fl_archive/manifest.json').read_text())
    entry = next(e for e in manifest['entries'] if e['id'] == ids[0])
    dumped = scr.dump((root / entry['path']).read_bytes())['sections'][0]
    used, columns = set(), []
    for col in dumped['columns']:
        key = (col['offset'], col['shift']) if col['bits'] else col['offset']
        if key in curated:
            label, confidence, note = curated[key]
            used.add(key)
        elif namer:
            label, confidence, note = namer(len(columns)), U, 'Unnamed.'
        elif col['bits']:
            label, confidence, note = f'bits_{col["offset"]}_{col["shift"]}', U, 'Unnamed.'
        else:
            label, confidence, note = f'u_{col["offset"]:02x}', U, 'Unnamed.'
        columns.append(dict(name=label, **{k: col[k] for k in ('type', 'type_id', 'offset', 'count', 'bits', 'shift')},
                            confidence=confidence, note=note))
    missing = set(curated) - used
    scr.require(not missing, f'{name}: curated column keys not in layout: {sorted(map(str, missing))}')
    # Several columns can share a byte offset (bit fields); a plain offset key then matches the first.
    scr.require(len({c['name'] for c in columns}) == len(columns), f'{name}: duplicate column names')
    return dict(name=name, resource_ids=ids, row_size=dumped['row_size'], columns=columns)


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('extracted/fl_eu/archive')
    out = Path(__file__).with_name('schemas')
    out.mkdir(exist_ok=True)
    manifest = json.loads((root / '.fl_archive/manifest.json').read_text())
    battle_ids = [e['id'] for e in manifest['entries']
                  if e['path'].startswith(('unit/mon/', 'unit/bnp/')) and e['path'].endswith('.uparm01')]
    families = CURATED + [('monster_battle_parameters', battle_ids, {
        0: ('level_key', M, 'Level interpolation key; usually rows at 1 and 100, some special keys above 100.'),
        2: ('hp', M, 'HP endpoint; Bunny 15 at key 1, 1280 at key 100. Runtime interpolation untraced.'),
        4: ('sp', M, 'Likely SP endpoint (normally 100).'),
        6: ('physical_attack', M, 'Likely attack endpoint; Red Wolf 26 at key 1.'),
        8: ('physical_defence', M, 'Likely defence endpoint; Red Wolf 20 at key 1.'),
        10: ('magic_attack', M, 'Likely magic endpoint; often equals physical attack.'),
        12: ('magic_defence', M, 'Likely magic defence endpoint.'),
        64: ('u_40', U, 'Scales with HP at key 1 (Baja Ha 4, Red Wolf 8, Coyote 12, Ghost 15), 256 at key 100; likely a reward '
                        '(Dosh?) endpoint. Thistle Wolf: 10.'),
        70: ('u_46', U, 'Constant across level keys (Red Wolf 10, Coyote 15); meaning unknown, keep the donor value.'),
        102: ('experience', M, 'Not XP: 65534 in every shipped row (Bunny, Red Wolf, Shadow Dragon). The XP-like reward is u_68.'),
        104: ('u_68', U, 'Scales with HP at key 1 (about HP/4: Baja Ha 6, Red Wolf 12, Coyote 18, Ghost 22), 384 at key 100; '
                         'likely the experience reward endpoint. Thistle Wolf: 16.')})]
    for name, ids, curated, *namer in families:
        schema = build_schema(root, name, ids, curated, *namer)
        (out / f'{name}.json').write_text(json.dumps(schema, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
        print(f'{name}: {len(schema["columns"])} columns')


if __name__ == '__main__':
    main()
