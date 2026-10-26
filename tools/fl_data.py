#!/usr/bin/env python3
"""Cross-table validation, Origin Island report and an editing proof for FL game data.

    fl_data.py validate <extraction>             check every inferred table link
    fl_data.py origin   <extraction> <report>    write the Origin Island / EX content report
    fl_data.py proof    <extraction> <new-dir>   edit SCRs, rebuild the archive, re-extract, verify

<extraction> is the output of fl_archive.py extract. The proof never writes to it: the new
directory shares files by hard link and replaces changed files instead of rewriting them.
Generated reports contain game text, so keep them in ignored directories.
"""
import argparse
import base64
import collections
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).parent


def local(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scr, archive = local('fl_scr'), local('fl_archive')
SLOTS = 9                                   # jp, es-LA?, fr-CA?, de, en, es, fr, it, en-GB
LANGS = ['jp', 'es-419', 'fr-CA', 'de', 'en', 'es', 'fr', 'it', 'en-GB']
CATEGORIES = ['weapon', 'armour', 'tool', 'furniture', 'consumable', 'material', 'key_item', 'bounty']
STAT_BASES = [6720, 6729, 6738, 6747, 6756, 6765, 6774, 6783]   # one stats table family per category
ITEM_BASES = [6702, 6792, 6801, 6810]                           # symbols, names, sources, descriptions
EN_SLOTS = (4, 8)
NONE16, NONE32 = 0xffff, 0xffffffff
EX_FLAGS = (1963, 2986)                     # event flags labelled 200_NNNN: the EX/Origin Island block
RECIPE_TABLES = list(range(8388, 8393))
ISLAND_MAP_LABELS = ['NormalMap_396', 'NormalMap_397', 'NormalMap_398', 'NormalMap_399', 'NormalMap_400']


class Data:
    def __init__(self, root):
        self.root = Path(root)
        self.manifest = json.loads((self.root / '.fl_archive/manifest.json').read_text())
        self.entries = {e['id']: e for e in self.manifest['entries']}
        self.cache = {}

    def path(self, id_):
        return archive.safe_path(self.root, self.entries[id_]['path'])

    def document(self, id_):
        if id_ not in self.cache:
            self.cache[id_] = scr.dump(self.path(id_).read_bytes(), id_)
        return self.cache[id_]

    def rows(self, id_):
        return self.document(id_)['sections'][0]['rows']

    def family(self, base, slot=EN_SLOTS[1]):
        return self.rows(base + slot)


def validate(data):
    checks, errors = collections.Counter(), []

    def check(ok, label, context):
        checks[label] += 1
        if not ok:
            errors.append(dict(check=label, context=context))

    items = data.family(6792)
    count = len(items)
    # Every language slot of every family has the same row count.
    families = {base: SLOTS for base in ITEM_BASES + [5811, 5419, 32662]}
    families[5966] = 8
    for base, slots in families.items():
        sizes = {len(data.rows(base + k)) for k in range(slots)}
        check(len(sizes) == 1, 'slot_row_counts', [base, sorted(sizes)])
    for id_ in [5810] + list(range(5820, 5828)) + list(range(5811, 5820)):
        check(len(data.rows(id_)) == 1522, 'challenge_rows', id_)
    for base in ITEM_BASES:
        check(len(data.rows(base + 4)) == count, 'parallel_item_rows', base)
    categories = [r['category'] for r in items]
    check(categories[:2735] == sorted(categories[:2735]), 'contiguous_category_blocks', count)
    check(all(type(c) is int and 0 <= c < 8 for c in categories), 'item_categories', count)
    for category, base in enumerate(STAT_BASES):
        expected = categories.count(category)
        for slot in range(SLOTS):
            check(len(data.rows(base + slot)) == expected, 'category_stats_rows', [base + slot, expected])
    for j, row in enumerate(data.family(STAT_BASES[7])):
        check(sum(row['drop_rates']) == 100, 'bounty_drop_rates', j)
        for item in row['drop_items']:
            check(item in (NONE16, NONE32) or item < count, 'bounty_drop_links', [j, item])
    icons = len(data.rows(8687))
    for i, row in enumerate(items):
        check(row['icon_index'] < icons, 'item_icon_links', i)
    flag_count = len(data.rows(5417))
    quest_count = len(data.rows(8715))
    for id_ in RECIPE_TABLES:
        for j, row in enumerate(data.rows(id_)):
            for column in ('output_items', 'seasoning_items', 'ingredients'):
                for value in row[column]:
                    if value != NONE16:
                        check(value < count, 'recipe_item_links', [id_, j, column, value])
            for item, quantity in zip(row['ingredients'], row['ingredient_quantities']):
                check((item == NONE16) == (quantity == 0), 'ingredient_quantities', [id_, j])
            check(row['required_flag'] == NONE16 or row['required_flag'] < flag_count, 'recipe_flag_links', [id_, j])
            check(row['category_icon_index'] < icons, 'recipe_category_icons', [id_, j])
    for id_ in range(8405, 8484):
        for j, row in enumerate(data.rows(id_)):
            check(row['item_id'] < count, 'shop_item_links', [id_, j, row['item_id']])
    maps = len(data.rows(5970))
    for j, row in enumerate(data.rows(8715)):
        for column in ('requested_item', 'alternate_requested_item', 'reward_item'):
            check(row[column] == NONE32 or row[column] < count, 'quest_item_links', [j, column, row[column]])
        check(row['prerequisite_quest'] == NONE16 or row['prerequisite_quest'] < j, 'quest_chain_links', j)
        check(row['required_story_flag'] == NONE16 or row['required_story_flag'] < flag_count, 'quest_flag_links', j)
        check(row['start_map'] < maps and row['end_map'] < maps, 'quest_map_links', j)
        base = row['dialogue_base_resource']
        check(all(base + k in data.entries for k in range(SLOTS)), 'quest_dialogue_links', j)
    for id_ in range(32662, 32671):
        check(len(data.rows(id_)) == quest_count, 'quest_text_rows', id_)
    return dict(item_rows=count, checks=dict(checks), errors=errors)


def contains_origin(raw):
    return any(term.encode('utf-16le') in raw for term in ('Origin', '神島', 'はじまりの島'))


def origin_report(data):
    """Facts behind docs/phase1b-data-tables.md; leads, not an ownership claim."""
    plain = scr.plain
    items = data.family(6792)
    sources = data.family(6801)
    names = [plain(r['name']) for r in items]
    flags = data.rows(5417)
    ex = [i for i, r in enumerate(flags) if plain(r['label']).startswith('200_')]
    recipes = {}
    for id_ in RECIPE_TABLES:
        gated = [(j, r['required_flag']) for j, r in enumerate(data.rows(id_))
                 if r['required_flag'] != NONE16 and EX_FLAGS[0] <= r['required_flag'] <= EX_FLAGS[1]]
        recipes[id_] = dict(rows=len(data.rows(id_)), ex_gated=len(gated),
                            by_flag=dict(collections.Counter(f for _, f in gated)))
    gated_outputs, open_outputs = set(), set()
    for id_ in RECIPE_TABLES:
        for row in data.rows(id_):
            gated = row['required_flag'] != NONE16 and EX_FLAGS[0] <= row['required_flag'] <= EX_FLAGS[1]
            (gated_outputs if gated else open_outputs).update(i for i in row['output_items'] if i != NONE16)
    ex_only = gated_outputs - open_outputs
    maps = data.family(5966, 7)   # en-GB slot of the 8-slot family (slots 1..8)
    island = [j for j, r in enumerate(maps) if r['map_label'] in ISLAND_MAP_LABELS or plain(r['name']).startswith('Origin')]
    bundles = data.rows(8716)
    quests = data.rows(8715)
    quest_titles = data.family(32662)
    island_quests = [j for j, q in enumerate(quests) if q['start_map'] in range(82, 87) or q['end_map'] in range(82, 87)]
    leads = []
    for id_, entry in sorted(data.entries.items()):
        path = data.path(id_)
        with path.open('rb') as f:
            magic = f.read(8)
        if magic[:4] != scr.MAGIC and magic != bytes.fromhex('0200000010000000'):
            continue
        if contains_origin(path.read_bytes()):
            leads.append(id_)
    return dict(
        ex_flag_block=dict(first=ex[0], last=ex[-1], count=len(ex), purchase_flag=1963,
                           purchase_label=plain(flags[1963]['label']), all_content_flag=2003,
                           all_content_label=plain(flags[2003]['label'])),
        items_tagged_origin=[dict(index=i, name=names[i]) for i, r in enumerate(sources)
                             if any('神島' in plain(r[k]) for k in ('source_1', 'source_2', 'source_3', 'source_4'))],
        items_named_origin=[dict(index=i, name=n) for i, n in enumerate(names) if 'Origin' in n],
        recipes_gated_by_ex_flags=recipes,
        items_only_craftable_via_ex_recipes=sorted(ex_only),
        island_maps=[dict(row=j, label=maps[j]['map_label'], name=plain(maps[j]['name']),
                          bundle=maps[j]['bundle_index'],
                          resources=[x for x in bundles[maps[j]['bundle_index']]['resources'] if x != NONE32])
                     for j in island],
        island_side_quests=dict(rows=island_quests, count=len(island_quests),
                                localised=sum(not any('぀' <= c <= '鿿' for c in plain(quest_titles[j]['title']))
                                              for j in island_quests)),
        origin_text_resource_ids=leads)


def _replace(path, data):
    """Write a new file and swap it in, so hard-linked originals stay untouched."""
    tmp = path.with_name(path.name + '.new')
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _clone_tree(source, target):
    def link_or_copy(src, dst):
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
    shutil.copytree(source, target, copy_function=link_or_copy)


def proof(source, output):
    source, output = source.resolve(), output.resolve()
    scr.require(not output.exists(), 'Proof output must be a new directory')
    scr.require(source != output and source not in output.parents and output not in source.parents,
                'Proof output must be separate from the source extraction')
    scr.require('dumps' not in output.parts, 'Proof output cannot be under dumps/')
    original = Data(source)
    baseline = validate(original)
    scr.require(not baseline['errors'], f'Original data validation failed: {baseline["errors"][:3]}')
    output.mkdir(parents=True)
    work = output / 'archive'
    _clone_tree(source, work)
    edited = Data(work)
    changed = set()

    def save(id_):
        raw = scr.build(edited.document(id_))
        scr.require(scr.build(scr.dump(raw, id_)) == raw, f'Edited SCR {id_} does not round-trip')
        _replace(edited.path(id_), raw)
        changed.add(id_)

    # 1. Rename an item (longer) and shorten its description, in both English slots.
    new_name, new_description = "DLC Author's Long Test Sword", 'A short DLC editing proof.'
    old_name = scr.plain(edited.rows(6800)[0]['name'])
    for slot in EN_SLOTS:
        edited.rows(6792 + slot)[0]['name'] = new_name
        edited.rows(6810 + slot)[0]['description'] = new_description
    # 2. A recipe ingredient: Healweed -> Vitalweed (both existing items).
    items = edited.family(6792)
    healweed, vitalweed = (next(i for i, r in enumerate(items) if scr.plain(r['name']) == n)
                           for n in ('Healweed', 'Vitalweed'))
    recipe = edited.rows(8388)[0]
    scr.require(recipe['ingredients'][0] == healweed, 'Unexpected first alchemy recipe')
    recipe['ingredients'][0] = vitalweed
    # 3. A quest reward: item and quantity.
    hp_potion = next(i for i, r in enumerate(items) if scr.plain(r['name']) == 'HP Potion')
    quest = edited.rows(8715)[0]
    old_reward = (quest['reward_item'], quest['reward_quantity'])
    quest['reward_item'], quest['reward_quantity'] = hp_potion, 3
    # 4. Append a new item (a bounty-category row, so every category-local index stays valid).
    new_index, symbol = len(items), 'ID_Item_901_00002_46'
    for base in ITEM_BASES:
        for slot in range(SLOTS):
            rows = edited.rows(base + slot)
            row = copy.deepcopy(rows[-1])        # keeps _raw, so padding bytes and unchanged strings carry over
            if base == 6702:
                scr.require(all(r['symbolic_id'] != symbol for r in rows), 'New symbolic ID already exists')
                row['symbolic_id'] = symbol
            elif base == 6792:
                row['name'] = 'DLC Test Relic'
            elif base == 6810:
                row['description'] = 'A newly appended test relic for DLC authors.'
            rows.append(row)
    for slot in range(SLOTS):
        edited.rows(STAT_BASES[7] + slot).append(copy.deepcopy(edited.rows(STAT_BASES[7] + slot)[-1]))
    for base in ITEM_BASES + [STAT_BASES[7]]:
        for slot in range(SLOTS):
            save(base + slot)
    save(8388)
    save(8715)
    after = validate(edited)
    scr.require(not after['errors'], f'Edited data validation failed: {after["errors"][:3]}')

    rebuilt = output / '_file_archive.bin'
    archive.build(work, rebuilt)
    verified_dir = output / 'verified'
    archive.extract(rebuilt, verified_dir)
    verified = Data(verified_dir)
    for id_, entry in original.entries.items():
        if id_ in changed:
            scr.require(verified.entries[id_]['sha256'] == archive.sha(edited.path(id_).read_bytes()),
                        f'Re-extracted edit mismatch: {id_}')
        else:
            scr.require(verified.entries[id_]['sha256'] == entry['sha256'], f'Unrelated resource changed: {id_}')
    for id_ in changed:
        scr.require(original.path(id_).read_bytes() == _original_bytes(original.document(id_)),
                    f'Original source changed: {id_}')
    final = validate(verified)
    scr.require(not final['errors'], 'Re-extracted links failed validation')
    scr.require(scr.plain(verified.rows(6800)[0]['name']) == new_name, 'Name edit lost')
    scr.require(scr.plain(verified.rows(6818)[0]['description']) == new_description, 'Description edit lost')
    scr.require(verified.rows(8388)[0]['ingredients'][0] == vitalweed, 'Recipe edit lost')
    scr.require((verified.rows(8715)[0]['reward_item'], verified.rows(8715)[0]['reward_quantity']) == (hp_potion, 3),
                'Quest reward edit lost')
    scr.require(scr.plain(verified.rows(6800)[new_index]['name']) == 'DLC Test Relic', 'Appended item lost')
    raw = rebuilt.read_bytes()
    report = dict(archive_sha256=hashlib.sha256(raw).hexdigest(), archive_bytes=len(raw),
                  changed_resource_ids=sorted(changed), unchanged_resources=len(original.entries) - len(changed),
                  renamed_item=dict(index=0, old=old_name, new=new_name),
                  recipe_edit=dict(table=8388, row=0, old_ingredient=healweed, new_ingredient=vitalweed),
                  quest_edit=dict(row=0, old_reward_item_and_quantity=old_reward, new=[hp_potion, 3]),
                  appended_item=dict(index=new_index, symbol=symbol, category=7),
                  validation=final, originals_untouched=True, runtime_tested=False)
    (output / 'proof-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def _original_bytes(document):
    sections = [base64.b64decode(s['original']) for s in document['sections']]
    if document['wrapper']:
        return struct.pack('<4I', 2, 16, 16 + len(sections[0]), 16 + sum(map(len, sections))) + b''.join(sections)
    return sections[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('validate', 'origin', 'proof'):
        p = sub.add_parser(command)
        p.add_argument('extraction', type=Path)
        if command != 'validate':
            p.add_argument('output', type=Path, help='report file (origin) or new directory (proof)')
    args = parser.parse_args()
    try:
        if args.command == 'proof':
            report = proof(args.extraction, args.output)
        elif args.command == 'origin':
            report = origin_report(Data(args.extraction))
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            print(f'wrote {args.output}')
            return
        else:
            report = validate(Data(args.extraction))
        print(json.dumps(report, indent=2))
        if report.get('errors'):
            parser.exit(1)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'fl_data: {exc}\n')


if __name__ == '__main__':
    main()
