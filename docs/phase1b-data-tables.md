# Fantasy Life EU — Phase 1b: editable game data

Phase 1a made the archive repackable. Phase 1b makes the **data inside it editable**:
a lossless SCR table codec, named-column schemas for the tables a DLC needs (items,
recipes, side quests, life challenges, maps, flags), cross-table validation, an end-to-end
edit→rebuild→re-extract proof, and a map of what the Origin Island expansion owns.

All game data, dumps and proof outputs stay in ignored directories. Nothing here ships
game bytes: tests use synthetic fixtures, and schemas only describe layouts and names.

**Phase 2 correction:** resource **8695** is a map → monster spawn-table index,
not an icon atlas. The `icon_atlas` schema has been replaced by `map_spawn_index`.
[Phase 2](phase2-maps-enemies.md) also identifies ordinary monster loot (6930),
placement containers and enemy/unit tables; historical Phase 1b counts below
describe that phase's original scope.

## Result

- `tools/fl_scr.py` dumps any SCR to JSON/CSV and rebuilds it. **All 22,601 SCR
  resources in the EU dump (16,675 plain tables, 5,926 two-section wrappers) rebuild
  byte for byte**, with schemas applied. **1,024,350 distinct string cells in 22,059
  table sections** re-encode to their original bytes, so control sequences are parsed
  correctly (not merely consistently).
- `tools/schemas/*.json` name the columns of 24 table families (171 tables). Only
  `high`-confidence columns are confirmed by cross-table links or by game code;
  everything else is marked `medium`/`uncertain` and keeps its raw value.
- `tools/fl_data.py validate` checks **18,193 cross-table links** with zero errors
  (item/icon/flag/map/dialogue links, ingredient quantities, category block sizes, ...).
- `tools/fl_data.py proof` edited an item name+description, a recipe ingredient and a quest
  reward, **appended a new item across all 45 item-parallel tables**, rebuilt
  `_file_archive.bin` into `extracted/fl_eu/mod_test/` and re-extracted it to verify
  every logical resource (details below). It is a structural proof only, **not boot-tested**.
- Origin Island: a flag block (`200_NNNN`, IDs 1963–2986), five field maps, one house,
  115 side quests, 274 gated recipes (299 items) and ~430 text resources are identified;
  see [Origin Island](#origin-island-content).

## Tools and editing workflow

```sh
# one SCR: edit, rebuild
python3 -I tools/fl_scr.py info  extracted/fl_eu/archive/_unnamed/06800_eadfc9eb2438.scr
python3 -I tools/fl_scr.py dump  extracted/fl_eu/archive/_unnamed/06800_eadfc9eb2438.scr /tmp/items.json   # or .csv
#   ...edit rows in /tmp/items.json with any editor/script...
python3 -I tools/fl_scr.py build /tmp/items.json /tmp/06800_new.scr

# whole-project checks and the proof (new, separate output directory required)
python3 -I tools/fl_data.py validate extracted/fl_eu/archive
python3 -I tools/fl_data.py origin   extracted/fl_eu/archive /tmp/origin-report.json
python3 -I tools/fl_data.py proof    extracted/fl_eu/archive extracted/fl_eu/mod_test
python3 -I tools/make_schemas.py     extracted/fl_eu/archive          # regenerate tools/schemas/
python3 -I -m unittest discover -s tools/tests -v
```

Workflow for a DLC edit: (1) `dump` the SCR (the leading digits of the file name select the
schema; use `--id` otherwise); (2) edit `sections[0].rows[...]` in the JSON; (3) `build`;
(4) write the result over the matching file in a **copy** of the extraction; (5)
`fl_archive.py build <copy> <archive>`; (6) re-extract and `fl_data.py validate`. The
proof (`fl_data.py proof`) automates exactly this and clones the tree by hard links, replacing
(never rewriting) changed files, so the original extraction cannot be modified.

JSON format (`format: "fl-scr-v1"`):

```json
{"format": "fl-scr-v1", "resource_id": 6800, "wrapper": false,
 "sections": [{"kind": "table", "row_size": 28, "original": "<base64 preservation image>",
               "columns": [{"name": "name", "type": "utf16", "type_id": 10, "offset": 0, "count": 1,
                            "bits": 0, "shift": 0, "confidence": "high", "note": "..."}, ...],
               "rows": [{"_raw": "<hex of the original row>", "name": "Squire's Sword", "category": 0, ...}]}]}
```

- **Edit `rows` only.** `original` is the preservation image that keeps everything not
  expressed as rows (unreferenced bytes, aliasing, trailers); `columns` must stay as dumped.
- A string is plain text or a token list: `["Hi", {"control": "f4ffffff1000..."}, "ya"]`.
  Controls are opaque length-prefixed records (below); copy them from existing strings.
- Multi-value columns are lists (`ingredients: [1485, 1477, 65535]`). Pointer columns
  (type 9) are `{"offset": n}` and only valid for offsets that already exist.
- Rows are appended by adding objects. `_raw` is optional: omitted bytes start as zero;
  a deep copy of an existing row keeps its `_raw` (padding bytes, unchanged strings).
  Deleting rows works too. Every column must be present in every row.
- Columns with bit fields (`bits`/`shift`) are edited as plain integers and range-checked;
  neighbouring bits in the same word are preserved.
- `"wrapper": true` files are the two-section container; only section 0 (table) is editable.
- CSV export (`.csv`) is a one-way readable view of the first table section.

## SCR container format

One **table section** is self-describing. All integers are little endian and every offset is
**relative to the start of the section**.

| Offset | Size | Meaning |
| --- | --- | --- |
| `0x00` | 4 | Magic `13 80 03 1d` |
| `0x04` | 4 | Zero |
| `0x08` | 1+1+2 | Zero, **column count**, constant `0x0009` (meaning unknown); identical in all 22,059 table sections |
| `0x0c` | 4 | Section length − 32 |
| `0x10` | 4 | `0x20`: offset of the column records |
| `0x14` | 4 | Offset of the table descriptor = `align4(0x20 + 6·columns + 4)` (true for all 22,059) |
| `0x18` | 8 | Zero |
| `0x20` | 6·columns | Column records, then zero padding up to the descriptor (a 4-byte terminator plus alignment) |
| descriptor | 12 | `<u32 row count, u32 row width, u32 rows offset>` |
| rows | count·width | Fixed-width rows (always directly after the descriptor in the dump) |
| pool | … | After the rows: the strings of all columns in row order (4-byte aligned) and the nested records that type-9 pointers target |

Column record `<u8 type, u8 array, u16 bits, u16 pos>`: `pos = byte_offset << 5 | bit_shift`.
`array` is the number of consecutive values. If `bits ≠ 0` the column is a bit field of that
width at `bit_shift` inside the integer at `byte_offset` (type u8/u16/u32, `array = 1`); one
word can host many columns (the item table packs a 4-bit tier, a flag, a 27-bit sell price at
byte 20 and a 27-bit buy price plus five flags at byte 24).

| Type | Meaning | Count in dump |
| --- | --- | ---: |
| 1 / 2 / 3 | u8 / u16 / u32 | 64,418 / 69,488 / 108,365, plus 2,520 u8 and 158,602 u32 bit fields |
| 10 | pointer to a UTF-16LE string — **localised text** (names, descriptions, titles) | 36,658 |
| 6 | pointer to a UTF-16LE string — **non-localised** (symbolic IDs, flag labels, icon names) | 3,031 |
| 5 | pointer to a NUL-terminated ASCII string (map labels) | 64 |
| 7 | u32 archive resource ID | 3 |
| 9 | opaque nested pointer (record not parsed; kept at its original offset) | 10 |

Counts are over all column records in the dump. Type 6 and 10 decode identically; the schemas
record which one a column uses.

### Strings and control sequences

Strings are UTF-16LE, NUL-terminated, and may contain **control records**:

- `ff ff` — a bare 2-byte control (≈165k occurrences in a one-third sample; meaning unknown).
- `<tag> ff ff ff <u32 size> <payload>`, record length `4 + size`, tag `0xe4–0xf9`. A NUL
  inside the payload does not end the string, so NUL-scanning is wrong.

| Tag | Seen (⅓ sample) | Size field | Meaning (evidence) |
| --- | ---: | --- | --- |
| `f0` | 122k | 4 | line break |
| `f1` | 48k | 4 | page break / wait for A |
| `f4` | 91k | 12–22+ | ruby/furigana: two u16 counts, then the UTF-16 annotation |
| `f7` | 25k | 8 | text colour (RainThunder: 0 black, 3 red, 4 green) |
| `f6` | 12k | 8 | variable substitution (two u32 arguments) |
| `e9` | 4.5k | 48–64+ | two-way branch (alternative texts) |
| `f5` | 3.6k | 52–88+ | choice list (count and per-choice records) |
| `f9` | 0.5k | 8 | button glyph (id: 0 A, 1 B, 2 X, 3 D-pad, 4 Circle Pad, 5/7 L, 6/8 R, 9/10 Y) |
| `e8`, `e4`, `e5` | 0.4k / 85 / 85 | 4 | unknown |

Meanings other than the sizes come from RainThunder's `SCR.getstring`; the codec only needs
the length prefix and never interprets payloads. A pool dump check confirms the parse: 325,192
consecutive pooled strings end exactly where the next one starts (≤3 bytes of alignment).
One caveat: text containing a character in U+FFE0–U+FFFE directly followed by a bare `ffff`
control would be re-read as a tagged record; no such string exists in the data.

### Wrapper and non-table sections

`02 00 00 00 10 00 00 00 <u32 second offset> <u32 end>` wraps two sections; the first is
normally a table (the localised text or parameters), the second is **event data**. In the dump:

| Shape | Files |
| --- | ---: |
| plain table section | 16,675 |
| wrapper: table + opaque second section | 5,384 |
| wrapper: opaque + opaque (e.g. 80 files start with `MSG `) | 542 |

Second sections start with a u32 count/size (e.g. `0x28` followed by `ffffffff` slots, or a
`0e 03 00 00 / 00 07 00 7f` bytecode-looking stream). They are preserved as `opaque` base64
and are **not** decoded: this is the event/script format (candidate for a later phase).

## What `build` guarantees and its limits

- An **unmodified document rebuilds byte for byte** (22,601/22,601 in the dump).
- Nothing already in a section ever moves. A changed or new string is **appended to the pool**
  (4-aligned, de-duplicated within the build); an unchanged cell keeps its original pointer.
  A grown row array is re-placed at the end of the section and the descriptor is rewritten (a
  shrunk one is written in place). So **no pointer needs a fixup**: type 9 pointers, string
  aliases and suffix sharing all keep working. Strings can freely grow, shrink or become empty.
- The cost is dead bytes: replaced strings and the old row array remain as unreferenced bytes.
  Section length (`0x0c`) and, for wrappers, the offsets/length in the 16-byte header are
  recomputed; sections are padded to 4 bytes when they grew.
- Row width, column layout and the number of columns are fixed (`build` rejects edits).
  Values are range-checked per column width/bit width; strings may not contain NUL or U+FFFF.
- Opaque sections are returned verbatim; the JSON `original` image must not be edited.
- Whether the **game** accepts the relocated row array and the extended pool has never been
  tested (no boot test yet). It follows the descriptor's absolute offset and string pointers
  that the original files already use, so it should; verify in the first runtime test.

## Language slots

Most text families repeat once per language in **nine consecutive resource IDs** (`base + slot`):

| Slot | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Text | ja | es (variant 1) | fr (variant 1) | de | en | es | fr | it | en (UK) |

Evidence: item 0 reads `兵士の剣`, `Espada de escudero`, `Épée de l'écuyer`, `Knappen-Schwert`,
`Squire's Sword`, `Espada de escudero`, `Épée de l'écuyer`, `Spada da scudiero`, `Squire's Sword`.
RainThunder labels the slots `jp, ae, af, de, en, es, fr, it, uk`; slots 1/2 and 5/6 carry
the same Spanish/French text here. The EU build presumably selects 3, 4/8, 5, 6, 7 by system
language (runtime selection not traced), so a DLC must fill **all nine** slots of each family.
Some families split the Japanese slot off (life challenge titles are base `5810` plus
`5820–5827` = slots 1–8; map names are `5966–5973` = slots 1–8 with no Japanese table
found; the 16-byte table `5965` is route labels, not the map-name table).
Placeholder content that was never localised keeps its Japanese text in every slot
(e.g. items 76–77 `ぶき`, quest rows 333–399).

## Schemas

`tools/schemas/<name>.json` holds, per table family: `resource_ids` (all language slots),
`row_size`, and for every column its `name`, `type`/`type_id`/`offset`/`count`/`bits`/`shift`
(exact; copied from the file's own column table and **verified against the data on every
`dump`**), plus `confidence` and `note`. `tools/make_schemas.py` regenerates them from the
extraction plus its curated name table, so a name change is a one-line edit followed by a rerun.

Confidence: **high** = confirmed by cross-table links, game code or text; **medium** = strong
pattern, not proven; **uncertain** = a label or a guess (raw values are preserved either way).

| Schema | IDs | Rows × width | What it is |
| --- | --- | --- | --- |
| `item_symbols` | 6702–6710 | 2,735 × 4 | symbolic item IDs `ID_Item_…` |
| `items` | 6792–6800 | 2,735 × 28 | names + base metadata |
| `item_sources` | 6801–6809 | 2,735 × 20 | acquisition/authoring text |
| `item_descriptions` | 6810–6818 | 2,735 × 4 | descriptions |
| `weapon_stats`, `armour_stats`, `tool_stats`, `furniture_stats`, `consumable_stats`, `material_stats`, `key_item_stats`, `bounty_stats` | 6720–6791 (9 each) | 153 / 750 / 175 / 399 / 623 / 459 / 30 / 146 | per-category stats; row *n* = *n*-th item of that category |
| `recipes` | 8388–8392 | 171 / 341 / 229 / 186 / 371 × 68 | alchemy, blacksmith, carpentry, cooking, tailoring |
| `side_quests` | 8715 | 400 × 52 | quest parameters |
| `side_quest_text` | 32662–32670 | 400 × 8 | title + request text |
| `life_challenges` / `_descriptions` | 5810, 5820–5827 / 5811–5819 | 1,522 × 24 / × 20 | challenge parameters + titles / objective text |
| `story_progression_text` | 5419–5427 | 174 × 204 | chapter/event labels (not bytecode) |
| `event_flags` | 5417 | 4,350 × 4 | flag labels (debug text); flag ID = row |
| `icons` | 8686–8694 | 4,995 × 8 | icon table (name per icon); texture association not established here |
| `map_spawn_index` (Phase 2) | 8695 | 122 × 8 | map ID → monster spawn-table resource |
| `map_names`, `map_resources`, `map_links` | 5966–5973, 8716, 5965 | 287 × 72, 253 × 48, 218 × 16 | maps, per-map resource bundles, routes |

### Items, recipes, side quests

#### `items` — IDs 6792–6800, 28-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | utf16 | `name` | high | Localised item name. Placeholder rows keep Japanese names even in Western slots. |
| `0x04` | u16 | `sort_key` | medium | Orders items inside a category (weapons 0..4 = weapon kind; others ascend). |
| `0x06` | u16 | `variant` | uncertain | Meaning unresolved; preserve. |
| `0x08` | u8 | `category` | high | 0 weapons 153, 1 armour 750, 2 tools 175, 3 furniture 399, 4 consumables 623, 5 materials 459, 6 key items 30, 7 bounties 146. Rows are grouped by category; code reads this byte at row+8. |
| `0x09` | u8 | `item_type` | medium | Sub-kind (85 sword, 105 helmet, 111 shield, 92 pickaxe, 26 water, 118 generic). |
| `0x0a` | u8 | `required_level` | medium | 0 = none; 5..100 otherwise (Origin Island clothing uses 30-40). |
| `0x0b` | u8 | `stack_limit` | high | 1 for gear/furniture, 99 for consumables/materials. |
| `0x0c` | u16 | `icon_index` | high | Row in the icon table (ids 8686-8694, 4995 rows); code reads this halfword at row+12. Placeholder items use 1 ("Dummy"). |
| `0x0e` | u8 | `quality_flag` | uncertain | 0 or 3. |
| `0x0f` | u8 | `equip_slot` | medium | Equipment slot / tool kind (16 shield, 17 helmet, 33 talisman, 41 pickaxe); 255 = n/a. |
| `0x10` | u16 | `u_16` | uncertain | 1095/1096 (922 key items, 1145-1151 bounties). Not a DLC flag. |
| `0x12` | u16 | `related_index` | uncertain | 65535 none; furniture object index; mirrors u_16 for tools/key items. |
| `0x14.0` | u32:4b | `tier` | uncertain | 0..5, 5 on most placeholder/junk rows. |
| `0x14.4` | u32:1b | `flag_20_4` | uncertain | 1 on almost all real items. |
| `0x14.5` | u32:27b | `sell_price` | high | Dosh, 27-bit packed. HP Potion 30, Healweed 5. |
| `0x18.0` | u32:27b | `buy_price` | high | Dosh, 27-bit packed at byte 24 bit 0. HP Potion 60. |
| `0x18.27` | u32:1b | `flag_24_27` | uncertain | Set on key items. |
| `0x18.28` | u32:1b | `flag_24_28` | uncertain | 1 on real items; 0 on placeholders and bounties. |
| `0x18.29` | u32:1b | `flag_24_29` | uncertain | Observed 0 on part of equipment incl. Origin Island pieces. |
| `0x18.30` | u32:1b | `flag_24_30` | uncertain | 1 on real tradable items. |
| `0x18.31` | u32:1b | `flag_24_31` | uncertain | 1 on real tradable items. |

#### `recipes` — IDs 8388–8392, 68-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | u16 | `recipe_key` | uncertain | Not unique (blacksmith filler rows repeat 33000); do not use as a primary key. |
| `0x02` | u16 | `difficulty` | medium | Crafting difficulty; grows with the rank/ingredient tier. |
| `0x04` | u16 | `u_04` | uncertain | 7/10/15/20. |
| `0x06` | u16 | `u_06` | uncertain |  |
| `0x08` | u16 | `u_08` | uncertain |  |
| `0x0a` | u16 | `u_0a` | uncertain |  |
| `0x0c` | u16 | `u_0c` | uncertain |  |
| `0x0e` | u16 | `experience` | medium | Life experience for crafting. |
| `0x10` | u16[2] | `work_parameters` | uncertain | Two equal halfwords (minigame length?). |
| `0x14` | u8 | `u_14` | uncertain |  |
| `0x15` | u8 | `rank_requirement` | medium | Rank of the Life needed; 16 = no rank (default/filler rows), 15 = special. |
| `0x16` | u8 | `output_quantity` | medium | 1 in every row. |
| `0x17` | u8 | `quality_mode` | medium | 1 = row yields four quality tiers. |
| `0x18` | u8 | `allow_extra_material` | medium |  |
| `0x19` | u8[3] | `ingredient_quantities` | high | Parallel to ingredients. |
| `0x1c` | u16[4] | `output_items` | high | Item IDs per quality tier (normal, good, great, perfect); 65535 = unused. |
| `0x24` | u16[4] | `seasoning_items` | medium | Cooking only: salt, ginger, butter, pepper... 65535 elsewhere. |
| `0x2c` | u16[3] | `ingredients` | high | Up to three item IDs; 65535 = unused. |
| `0x32` | u16 | `u_32` | uncertain | 169 default; otherwise 10-149 grouped by output kind. |
| `0x34` | u16[4] | `category_tags` | uncertain | Up to four tags (0 swords, 2/5 shields, 5 armour, 6/9 tools, 3/4/11 clothes); NOT Life IDs. |
| `0x3c` | u16 | `workbench` | medium | Workbench / station variant (differs per recipe table). |
| `0x3e` | u16 | `category_icon_index` | high | Icon-table row 4593-4612 = crafting category icon ("Synthetic alchemy medicine"...). |
| `0x40` | u16 | `unlock_rank` | medium | Life rank at which the recipe is learned (1..10, 16 none). |
| `0x42` | u16 | `required_flag` | high | Event flag (table 5417) that gates the recipe; 1963 = Origin Island expansion owned. |

#### `side_quests` — IDs 8715–8715, 52-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | u32 | `dialogue_base_resource` | high | JP dialogue base = 29062 + 9*row; the per-language slot adds 0..8. |
| `0x04` | u8 | `chapter_group` | medium | 0..3 (3 = post-game / Ancient content). |
| `0x06` | u16 | `client_npc` | uncertain | NPC index; same for all quests of one client. |
| `0x08` | u16 | `start_map` | uncertain | Index into the map table (5966-5973). |
| `0x0a` | u16 | `end_map` | uncertain |  |
| `0x0c` | u32 | `requested_item` | high | Item ID, 0xffffffff none. |
| `0x10` | u32 | `alternate_requested_item` | medium | Alternative acceptable item. |
| `0x14` | u8 | `requested_quality` | high | 255 any, 1 good quality... |
| `0x16` | u16 | `requested_monster` | uncertain | Set instead of requested_item on slaying quests. |
| `0x18` | u8 | `requested_quantity` | high |  |
| `0x1c` | u32 | `reward_item` | high | Item ID, 0xffffffff none. |
| `0x20` | u8 | `reward_quantity` | high |  |
| `0x24` | u32 | `reward_dosh` | high | 0xffffffff none. |
| `0x28` | u16 | `reward_points` | uncertain | 10..1520, grows with quest level (stars/bliss?). |
| `0x2a` | u8 | `u_2a` | uncertain | Always 0. |
| `0x2c` | u16 | `prerequisite_quest` | high | Row index of the quest that must be done first, 65535 none. |
| `0x2e` | u16 | `required_story_flag` | high | Event flag (5417); 1931/1932 = chapter 8 completion labels. |
| `0x30` | u8 | `minimum_level` | medium |  |
| `0x31` | u8 | `u_31` | uncertain | 100/50/30/10/0. |

Notes that matter for authoring:

- **Item ID = row index** in every item-parallel table. Category blocks are contiguous
  (weapons 0–152, armour 153–902, tools 903–1077, furniture 1078–1476, consumables 1477–2099,
  materials 2100–2558, key items 2559–2588, bounties 2589–2734). Stats row *n* of category *c*
  is the *n*-th item of that block (all eight block sizes match their stats tables exactly).
- `icon_index` indexes the **icon table** (`icons`, 4,995 rows, name per icon): 1,533 of 2,461
  Japanese names equal the item's own name, the rest are earlier/alternate names of the same
  object. Game code reads this halfword at row+12 and the category byte at row+8 (see below).
- Recipes: one *craft* is several rows (different unlock stage/quality mode); rows with
  `rank_requirement = 16`, key `33000` or repeated outputs are tutorial/filler rows.
  `output_items` are the four quality tiers, `seasoning_items` the cooking spices, and
  `category_icon_index` (4593–4612 → "Synthetic alchemy 'medicine'", "Blacksmith synthetic
  'iron weapon'", …) resolves in the icon table for all 1,298 rows. `category_tags` look like
  equipment-class tags, **not** Life IDs. Ingredient IDs are checked against the item names
  (`ingredient_quantities > 0` exactly where an ingredient is set).
- Side quests: `dialogue_base_resource = 29062 + 9·row`, and dialogue lives in resources
  `base + slot`; `prerequisite_quest` always points to an earlier row (chains);
  `required_story_flag` 1931/1932 are the chapter-8 completion flags.

### Other schemas

#### `bounty_stats` — IDs 6783–6791, 28-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x04` | u16[3] | `drop_rates` | high | Percent chance of each drop slot; the three values sum to 100. |
| `0x0c` | u32[3] | `drop_items` | high | Item IDs dropped by this bounty target; 0xffffffff = none. Rows parallel the bounty block of items. |
| | | *22 further columns* | uncertain | Named `u_<offset>` / `bits_<offset>_<shift>`; see the JSON. |

#### `weapon_stats` — IDs 6720–6728, 24-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | u16 | `attack` | medium | Squire/Bronze/Iron/Silver sword = 6/12/20/28; row order = weapon rows of items |
| | | *36 further columns* | uncertain | Named `u_<offset>` / `bits_<offset>_<shift>`; see the JSON. |

#### `armour_stats` — IDs 6729–6737, 48-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | u32 | `scale_f32_bits` | uncertain | Raw float bits (1.0). |
| `0x04` | u16 | `defence` | medium | Value 2 on the first caps; exact physical/magic split unresolved. |
| | | *45 further columns* | uncertain | Named `u_<offset>` / `bits_<offset>_<shift>`; see the JSON. |

#### `life_challenges` — IDs 5810–5827, 24-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | utf16 | `title` | high |  |
| `0x04` | u16 | `objective_type` | medium | 0 none, 7 craft item, 9 catch/bring item, 10 craft N of a group... |
| `0x06` | u16[8] | `objective_parameters` | medium | Type-dependent (item index or group id, count); 65535 unused. |
| `0x16` | u8 | `life_id` | medium | Life namespace 0..20 incl. cut Lives (1 Treasure Hunter, 20 Farmer). |
| `0x17` | u8 | `rank` | medium | 255 none. |

#### `life_challenge_descriptions` — IDs 5811–5819, 20-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | utf16 | `objective_text` | high | Objective sentence, e.g. "Make 5 items of Origin Island clothing". |
| `0x04` | u32 | `prerequisite` | uncertain | 65535 none. |
| `0x08` | u16 | `reward_points` | medium | 100..3000; 100 on placeholder rows. |
| `0x0a` | u16 | `rank` | medium | Matches life_challenges.rank. |
| `0x0c` | u16 | `active` | uncertain | 1 on real, localised challenges; 0 on cut placeholders. |
| `0x0e` | u16 | `u_0e` | uncertain |  |
| `0x10` | utf16 | `extra_text` | uncertain | Second text pointer (mostly empty). |

#### `icons` — IDs 8686–8694, 8-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | u32 | `icon_id` | uncertain | Opaque id (13856...); equal across slots. |
| `0x04` | utf16 | `name` | high | Icon name; indexed by items.icon_index and recipes.category_icon_index. |

#### `map_names` — IDs 5966–5973, 72-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | utf16 | `name` | high | Localised map name; (unused) rows keep Japanese. |
| `0x04` | ascii | `map_label` | high | NormalMap_NNN (field/dungeon) or HouseMap_NNN (interior) resource key. |
| `0x08` | ascii | `u_08` | uncertain | Unnamed. |
| `0x0c` | u32[4] | `reserved` | uncertain | Four 0xffffffff. |
| `0x1c` | u32 | `position_x_f32` | uncertain | IEEE-754 bits; with y/z a point such as (20, 0, -6) (entry/spawn?). |
| `0x20` | u32 | `position_y_f32` | uncertain |  |
| `0x24` | u32 | `position_z_f32` | uncertain |  |
| `0x28` | u32 | `param_a_f32` | uncertain | Second float triple, e.g. (8, 30, 40) (camera/view limits?). |
| `0x2c` | u32 | `param_b_f32` | uncertain |  |
| `0x30` | u32 | `param_c_f32` | uncertain |  |
| `0x34` | u16 | `bundle_index` | medium | Row in the map resource table 8716 (10 archive IDs per map). |
| `0x36` | u8 | `u_36` | uncertain | Unnamed. |
| `0x37` | u8 | `u_37` | uncertain | Unnamed. |
| `0x38` | u8 | `u_38` | uncertain | Unnamed. |
| `0x39` | u8 | `u_39` | uncertain | Unnamed. |
| `0x3a` | u8 | `u_3a` | uncertain | Unnamed. |
| `0x3b` | u8 | `u_3b` | uncertain | Unnamed. |
| `0x3c` | u8 | `u_3c` | uncertain | Unnamed. |
| `0x3e` | u16 | `u_3e` | uncertain | Unnamed. |
| `0x40` | u16 | `u_40` | uncertain | Unnamed. |
| `0x42` | u8 | `u_42` | uncertain | Unnamed. |
| `0x43` | u8 | `u_43` | uncertain | Unnamed. |
| `0x44` | u8 | `u_44` | uncertain | Unnamed. |
| `0x45` | u8 | `u_45` | uncertain | Unnamed. |
| `0x46` | u8 | `u_46` | uncertain | Unnamed. |
| `0x47` | u8 | `u_47` | uncertain | Unnamed. |

#### `map_resources` — IDs 8716–8716, 48-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | u32[10] | `resources` | high | Ten archive IDs per map (model, collision, ...); 0xffffffff absent. |
| `0x28` | pointer | `variants_pointer` | uncertain | Opaque nested record kept at its original section offset. |
| `0x2c` | u16 | `related_map` | uncertain |  |

#### `item_sources` — IDs 6801–6809, 20-byte rows

| Offset | Type | Column | Conf. | Notes |
| --- | --- | --- | --- | --- |
| `0x00` | u8 | `source_count` | uncertain |  |
| `0x01` | u8 | `u_01` | uncertain | Unnamed. |
| `0x02` | u8 | `u_02` | uncertain | Unnamed. |
| `0x04` | utf16 | `source_1` | medium | Acquisition / authoring text (shop, drop). Contains Japanese tags such as 5_神島 on Origin Island gear. |
| `0x08` | utf16 | `source_2` | medium |  |
| `0x0c` | utf16 | `source_3` | medium |  |
| `0x10` | utf16 | `source_4` | medium |  |

Bounty stats are the **monster-bounty drop tables**: three drop items with percentages that sum
to 100 (e.g. Killer Bunny: 60% Animal Droppings, 30% Monster Dung, 10% Criticaline).

## Cross-table validation (`fl_data.py validate`)

Zero errors on the unmodified dump; the same checks passed on the modified/rebuilt data.

| Check | Count |
| --- | ---: |
| slot row counts equal in every language family | 8 families |
| challenge table row counts (1,522 in all 18 tables) | 18 |
| parallel item tables have equal row counts / contiguous category blocks | 4 / 1 |
| category block size = stats table rows (8 categories × 9 slots) | 72 |
| item icon index < icon rows | 2,735 |
| recipe item links (outputs, seasonings, ingredients) | 5,472 |
| ingredient item set ⇔ quantity > 0 | 3,894 |
| recipe flag links / category icon links | 1,298 / 1,298 |
| quest item links (requested, alternate, reward) | 1,200 |
| quest chain, flag, map and dialogue links | 400 each |
| bounty drop rates sum to 100 / drop items resolve | 146 / 438 |
| quest text tables have 400 rows | 9 |

## Editing proof

`fl_data.py proof extracted/fl_eu/archive extracted/fl_eu/mod_test` (5 minutes, ~3.4 GB extra disk,
all under ignored `extracted/`). The output directory must be new and may not be inside the
source extraction or under `dumps/`; it holds `archive/` (a hard-linked clone in which only the
47 changed SCRs are replaced files), `_file_archive.bin` (the rebuilt archive), `verified/` (a
full re-extraction of it) and `proof-report.json`.

| Edit | Where | Before → after |
| --- | --- | --- |
| Item name (longer) | `items` row 0, en + en-GB slots (6796, 6800) | `Squire's Sword` → `DLC Author's Long Test Sword` |
| Item description (shorter) | `item_descriptions` row 0, slots 6814, 6818 | → `A short DLC editing proof.` |
| Recipe ingredient | alchemy `8388` row 0, `ingredients[0]` | 1485 Healweed → 1486 Vitalweed |
| Quest reward | `side_quests` `8715` row 0 | item 29 ×1 → 1638 (HP Potion) ×3 |
| Appended item | row **2735** in all 36 item tables (names, descriptions, sources, symbols; 9 slots each) + a copy of the last row in `bounty_stats` 6783–6791 | `DLC Test Relic`, symbol `ID_Item_901_00002_46`, category 7 |

Result:

- 47 SCRs changed (36 item + 9 bounty-stat + `8388` + `8715`); every other one of the **58,048**
  logical resources has the original SHA-256 after re-extraction (`fl_archive.build` reuses all
  unchanged compressed streams and re-encodes the 47 as LZ11).
- Rebuilt `_file_archive.bin`: 373,681,120 bytes (original 372,881,344), SHA-256
  `9f840ee7f427ed42a777dc4b586b0a80e20c01e82caa5056063a9cb510d96f8c`. Re-extraction decodes all
  38,204 physical and 19,891 virtual entries.
- Every changed SCR round-trips (`build(dump(x)) == x`), and `validate` passes on the edited
  tree and on the **re-extracted** tree (18,198 checks, 0 errors; the appended item adds icon,
  drop-rate and drop-link checks).
- Re-extracted values equal the edits: names, descriptions, ingredient, reward, the new item at
  index 2,735 and its bounty stats row.
- The source extraction is untouched: the 47 original files still match the manifest hashes, and
  `extracted/fl_eu/romfs/_file_archive.bin` still has the Phase 1a SHA-256 `20570a94…cdd9f6`.
- **Not tested:** that the game boots or displays any of it.


## Appending items and hard-coded limits

**Item-parallel tables** (every table with exactly 2,735 rows; the scan of all 22,601 SCRs
finds no others): `6702–6710` (symbols), `6792–6800` (names), `6801–6809` (sources),
`6810–6818` (descriptions) = **36 tables**, plus the nine slots of the stats family of the
new item's category (**9 tables**) = 45 to extend per new item.

Why the proof appends a **bounty**: the stats tables are indexed per category, and the
loaders (inferred) rely on the contiguous category blocks. Appending after the last row with
category 7 keeps every existing item ID and category-local index valid and needs exactly one
new `bounty_stats` row per slot. A new weapon/armour/material would have to be **inserted**
into its block, shifting the IDs of everything after it; recipes, quests, bounty drops,
challenge parameters, saves and code literals all reference raw item IDs. Options: (a)
renumber every referencing table (feasible for the tables we know, which `validate`
enumerates), (b) append with the real category and test whether the loader needs contiguity
(untested), or (c) use the port to relax the loader. The port now implements (c) for
appended rows; see [phase1b-item-expansion.md](phase1b-item-expansion.md). It still does
not make insertion/renumbering safe.

Other places that know about a new item:

- **Icons.** `icon_index` points into the 4,995-row icon table (`icons`, resources
  8686–8694). Its texture association remains untraced; 8695 indexes map spawn
  tables, as corrected in Phase 2. A new icon needs a new row in all nine slots plus a texture; reusing an
  existing icon index needs nothing. (The proof reuses icon 1, the dummy.)
- **Recipes/quests/drops** reference items by ID only; add rows there to make an item obtainable
  (`recipes`, `side_quests.reward_item`, `bounty_stats.drop_items`).
- **Shop lists / loot / treasure tables: not located.** Candidate item-ID columns exist
  in several unlabelled tables (e.g. 5440, 5450–5455, 5528–5573 — fixed-size lists of IDs below
  2,735); event scripts (opaque second sections) probably hold shop inventories.
- **code.bin (EU, ARM, text loaded at 0x100000) has hard-coded 2,735.** Nine
  `0x00000aaf` literal words remain in EU v00 `.text` (a full scan finds no other
  immediate/literal 2,735): `0x239680` and `0x438524` (item collection/recipe list
  builders that test the per-item save bit through `0x5b7130` kind 9), `0x38f1cc`
  (category histogram, twice in one function), `0x4392ac` (crafting category counter),
  `0x39b964`/`0x3aaaf4` (native item-validity checks) and `0x5673a0`/`0x567818`/
  `0x567880` (inventory/validity wrappers and `script_inventory_change`). Anything past
  index 2,734 is rejected or skipped; the **save item/recipe bit sets cannot grow in
  place**, which the recompiled port handles with aliases plus a sidecar. The exact
  addresses, layouts, category-stat mapping, hooks and offline test are in
  [phase1b-item-expansion.md](phase1b-item-expansion.md).
- Other hard-coded counts found the same way: **4,350 event flags** (0x25a3b4, 0x39f69c,
  0x3a0498) and **1,522 life challenges** (0x3a6528, 0x3a76e4); the 400 quests probably
  likewise (the literal exists; its users were not traced).
  New flags (a DLC flag block) therefore also need code/save support.

## Origin Island content

Findings (from `fl_data.py origin`; leads, not an ownership claim). Phase 0 established that
the DLC CIA only sets an unlock flag (`ID_ECFlag_0000.dat`), so everything is in the base game.

**How the data marks DLC content: there is no per-row "is DLC" column** in items, quests or
maps. The marks are:

1. **A flag block.** Event flags `1963–2986` (1,024 flags, labels `200_0001`–`200_1024`, the
   `EX` group) belong to the expansion: `1963 EXパッチ課金済み` (EX patch purchased, the
   purchase flag), `1965` link mode, `1966` screenshot function, `1976–1987` the twelve-trials
   completions, `1989–1997` nine extra mounts (horses, unicorn, alpaca, sky turtle, deer,
   crab), `1998–2002` goddess-lottery unlocks (`2002` はじまりの島 = Origin Island), `2003` all
   paid content purchased, `2005–2014` recipe-acquired flags for the twelve-trials and
   hero-legend gear. Labels are the authoring debug text in `5417`.
2. **Recipes gated by those flags** (`recipes.required_flag`): 274 of 1,298 rows
   (alchemy 23, blacksmith 94, carpentry 44, cooking 21, tailoring 92), yielding **299 items
   craftable only through EX recipes** (149 armour, 56 consumables, 39 tools, 29 weapons,
   20 furniture, 6 materials), e.g. Champion's Blade, Shogun Armour, Athena's Needle. The five
   Origin Island clothing pieces (`Cap`, `Armour`, `Bottoms`, `Gloves`, `Boots` = items 599, 612,
   622, 657, 665; tailoring, rank 9) are gated by `1963`, and the only items whose source text
   carries the Japanese tag `5_神島`.
3. **Maps and resources.** Field maps `NormalMap_396–400` (map rows 82–86: Central Grassland,
   Penguin Beach, Forest Shrine, Rocky Hill Shrine, Fluffkin Grotto) use resource bundles 48–52
   of table `8716` = **archive IDs 11677–11801** (25 per map: one `CB01`, one `COL`
   collision plus one `0202d051` blob, two BPAK, one `GB01`, one `FB01`, one `zmdl` model and
   17 `ztex` textures). `HouseMap_188` "Origin Island
   Holiday Home" (row 240) uses bundle 195 = IDs 10616–10624. The Ancient Tower/Trial maps
   (rows 38–44, 48–79, 97–100; `NormalMap_311–352`, `911–914`) have no Origin tag and are likely
   base post-game content (not established).
4. **Side quests.** Rows **285–399** (115 quests, `chapter_group = 3`) all start on the five island
   maps (`start_map` 82–86); 48 have localised text (Furcasso's Humble Beginnings, New Thread,
   From a Lady to a Lord, …) and 67 (rows 333–399) still carry Japanese placeholder text. They also require
   chapter-8 completion (`1931`/`1932`). Other quests only mention the island in dialogue.
5. **Life challenges.** "God-in-Training Challenge" rows mention Origin Island locations
   (e.g. row 652 "Origin Island Couture", rows 196, 280, 728, 1323, 1393).
6. **Text** (UK English slot unless noted; ID = slot 0 base in parentheses): expansion
   prompts — connection errors that need the expansion (`6268–6275`), "expansion not applied"
   start prompt (`6385–6392`), "update available" (`12425–12432`), purchase info on the title
   screen (`21173–21180`), "thank you for purchasing" (`21937–21944`), shop NPC dialogue
   (`22323–22331`), menu entries "Travel to Origin Island" (`6352–6356`), Goddess Statue prizes
   (`6658–6662`), home display text (`6649–6653`), achievement lines (`5805–5809` rows 220–230),
   item names and descriptions (`6796–6818` rows 599–665, 1912), map names (`5969–5973` row 240),
   story chapter titles (`6013–6021` rows 159, 160, 166 "— Origin Island —"), and 300
   NPC conversation resources in `22300–32060`. In total **430 SCR resources** contain "Origin"/`神島`
   (`origin_text_resource_ids` in the report).
7. **Code.** `ID_ECFlag_0000.dat` is the unlock file (Phase 0); the code reads flags like `1963`
   from save data. How the two are connected was not traced.

## Open questions

1. **Runtime acceptance** of rebuilt SCRs and archive (appended pool, relocated row array,
   bigger sections, new LZ11 streams). Needs a boot test (Azahar, or the port).
2. Meaning of every `uncertain` column: item `variant`, `u_16`, the flag bits and `tier`;
   recipe `u_04`–`u_14`, `u_32`, `category_tags`, `workbench`; quest `client_npc`,
   `reward_points`, `u_31`; map parameters; the bounty and weapon/armour stat columns.
3. Is the category-local stats index derived from contiguous blocks, or by counting? This decides
   whether new non-bounty items can be appended (see above).
4. Shop inventories, drop/treasure tables and the NPC placement for a new island: probably in
   the **event/script sections** (5,926 wrapper second sections, plus `0f f1 40 33` resources).
5. Type 6 vs 10 behaviour, header constant `0x0009`, controls `e4/e5/e8` and bare `ffff`.
6. Which language slot the EU build reads for each system language; where Japanese map names live.
7. Whether the 1,024-flag EX block is validated by code against `ID_ECFlag_0000.dat`, and
   whether new flags/saves need enlarging (the port can; the 4,350/1,522/2,735 counts are literals).
8. Ancient Tower/Trial content: base game or expansion? Nothing in the data marks it.
