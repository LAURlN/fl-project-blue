# Fantasy Life EU — Phase 1b: lifting the item, category-stat and recipe limits

> **Note:** paths starting with `port/` (and `runtime/`) refer to the runtime's source code, which is not part of this package. They are kept as historical research context.

Status: **implemented and offline-tested on EU v00; not boot-tested.** The runtime module is
`port/runtime/src/games/fantasylife/items.{h,cpp}`, registered through the universal hook registry
(`hooks.h`, branch `hook-registry`, base commit `db2e302`). Archive growth is in
`games/fantasylife/mods.cpp`. This document records the complete static audit behind both.

The goal is to let a mod **append** item rows past the vanilla 2,735 and recipe rows past the
vanilla 1,298 without renumbering any vanilla ID. Vanilla IDs `0..2734` keep their exact
category/stat/save meaning. Appended stat rows must follow the item ID order within each category;
the runtime derives their category-local stat rows from the item table's own category byte.

## Result

- Nine literal `0x00000aaf` words exist in EU v00 `.text`. All nine are patched to the live item
  table row count when it exceeds 2,735, so every validity check, collection loop, category
  histogram and menu counter sees appended IDs.
- Item table kinds `0..2` and category-stat kinds `3..10` can grow. The category-stat lookup
  `0x00204454` is replaced so appended items map to `vanilla category size + appended ordinal`,
  not to `item_id - category_start`.
- The fixed item collection bit set is not grown in guest RAM. Appended IDs alias the 20 existing
  weapon placeholder bits `58..77` (save bit `0xE48 + id`), so no guest index leaves its buffer.
  The real appended IDs are persisted in `fl-items.sidecar`; vanilla IDs are never written there.
- Recipe bit tests/sets for appended rows use the same sidecar. Vanilla recipe bits
  (`save+0x3b42`, 1,298 bits) are untouched.
- `tools/test-fl-items.cpp` covers the pinned digest, literal patching, stat mapping, bit alias,
  acquisition, recipes and sidecar reload against a scratch guest image. No game code is started.
- `tools/test-fl-mod.cpp` applies a synthetic overlay for **new archive ID 58,095** and verifies the
  grown header arrays, Resource 1 role table, payload and shifted original offsets.

## Why a row can be appended safely

Item ID = row index in every item-parallel table. The vanilla blocks are contiguous:

| category | block | start | size | stats table kinds |
| ---: | --- | ---: | ---: | --- |
| 0 weapons | `0–152` | 0 | 153 | 3 |
| 1 armour | `153–902` | 153 | 750 | 4 |
| 2 tools | `903–1077` | 903 | 175 | 5 |
| 3 furniture | `1078–1476` | 1078 | 399 | 6 |
| 4 consumables | `1477–2099` | 1477 | 623 | 7 |
| 5 materials | `2100–2558` | 2100 | 459 | 8 |
| 6 key items | `2559–2588` | 2559 | 30 | 9 |
| 7 bounties | `2589–2734` | 2589 | 146 | 10 |

Appending after row 2,734 and writing the item's real category byte keeps every vanilla ID and
every vanilla category-local index unchanged. **Do not insert** into a category block: that shifts
later IDs in every table, recipe, quest, shop, drop, save and code literal.

For appended row `id`, the runtime computes:

```
category = item_row(id).category                 # byte at row + 8
ordinal  = number of appended rows with the same category before `id`
stats_row = CATEGORY_SIZES[category] + ordinal
```

`stats_row` is then looked up in stats table `category + 3`. The statistics table must itself have
`CATEGORY_SIZES[category] + appended_count[category]` rows in every language slot (nine resources
per family, `6720–6791`). If it does not, the hook returns NULL, exactly like an out-of-range
vanilla stats row.

## Struct layouts

### Archive header (`_file_archive.bin`)

`N` is the u32 at offset 0. The four arrays are contiguous and each is `N` entries:

| Offset | Size | Meaning |
| --- | --- | --- |
| `0x00` | 4 | logical entry count `N` (58,095 vanilla) |
| `0x04` | 4 | reserved, zero |
| `0x08` | `4*N` | absolute offsets |
| `0x08+4*N` | `4*N` | uncompressed sizes |
| `0x08+8*N` | `4*N` | stored sizes |
| `0x08+12*N` | `N` | compression flags |
| `0x08+13*N` | … | padding, then physical data |

Growing `N` relocates all four arrays. `mods.cpp` rebuilds them at the new strides rather than
resizing the old header blob; the original payload area shifts by
`delta = 8 + 13*N_new - (8 + 13*N_old)`, and every nonzero original offset gets `+delta`.

### Resource 1: relationship index

| Offset | Type | Meaning |
| --- | --- | --- |
| `0x00` | u32 | magic `0x530e30c3` |
| `0x04` | u32 | total size minus 24 |
| `0x08` | u16 | logical count (`N`) |
| `0x0a` | u16 | named-pack count (1,764) |
| `0x0c` | u32 | reserved, zero |
| `0x10` | u32 | role-table offset (`0xf570`) |
| `0x14` | u32 | pack-descriptor offset (`0xa2c0`) |
| `0x18` | variable | member-ID lists |
| `0xa2c0` | `12*1764` | pack descriptors |
| `0xf570` | `4*N` | role records |

Role record: `<u16 pack-ordinal, u16 kind>`. Kind 0 standalone (`ordinal 0xffff`), kind 1
physical named pack, kind 2 virtual member. The role table ends the index, so `mods.cpp` appends
`4*(N_new-N_old)` zero bytes, rewrites every new record to `0xffff,0`, updates the u16 count and
the “size minus 24” field, and points Resource 1 at this appended raw index. Original role records
are bytes unchanged.

### Item manager (`0x00704a94`)

`item_tables_get` (`0x001fd520`) returns this address. It holds twelve `0x3c`-byte SCR table
objects:

| Kind | Table |
| ---: | --- |
| 0 | item names/metadata (28-byte rows) |
| 1 | item sources (20-byte rows) |
| 2 | item descriptions (4-byte rows) |
| 3..10 | category stats for categories 0..7 (24/48/…-byte rows) |

Each table object:

| Offset | Type | Meaning |
| --- | --- | --- |
| `0x00` | u32 | magic `0x031c6040` |
| `0x04` | u32 | descriptor pointer |
| `0x14` | u8 | type `2` for an SCR table |
| descriptor+`0x00` | u32 | row count |
| descriptor+`0x04` | u32 | row width |
| descriptor+`0x08` | u32 | row-array address |

`item_table_row` (`0x001fd52c`) computes `mgr + kind*0x3c` and bounds-checks through
`scr_table_row` (`0x001fb74c`). It has no item-count literal, so appended rows are already
addressable once the SCR descriptor says so.

### Item row (28 bytes)

| Offset | Type | Meaning |
| ---: | --- | --- |
| `0x08` | s8 | category `0..7` (read by `0x204454`) |
| `0x0c` | u16 | icon row (read by category histograms) |

The other fields are documented in `phase1b-data-tables.md` and are unchanged by this module.
Row width is fixed; append complete 28-byte rows, never a partial or different-width row.

### Category starts (`mgr+0x2d0`)

Eight u32 block starts, vanilla
`[0, 153, 903, 1078, 1477, 2100, 2559, 2589]`. `0x00204454` reads the category byte from the item
row, subtracts `starts[category]`, and indexes the category's stats table. The replacement skips
that subtraction for appended IDs.

### Save item flags (`save+0x21f20`)

`0x005b7130` maps `(saveBits, kind, id)` to a bit index. For kind 9 (items) the table entry at
`0x005b71c0` returns `0xE48 + id`. The item bit set starts at `save+0x21f20`; the next known save
field begins at `save+0x22244`, so there are only five spare bytes after bit `0xE48+2734`. Guest
code cannot represent thousands of new item bits in place.

The module therefore maps appended IDs to the existing placeholder bits:

```
bit = 0xE48 + 58 + ((id - 2735) mod 20)
```

All 20 aliases (`58..77`) are weapon placeholder rows with existing save bits. This is an
**aliasing guard, not a second save format**: the authoritative appended collection state is the
sidecar. The alias deliberately means an appended item and its placeholder share one guest bit;
do not use `58..77` as authored items in a mod that also needs distinct extended collection flags.

### Recipe save flags (`save+0x3b42`)

`0x002e06b0` tests and `0x002e07d4` sets recipe bits. Their bit index is a fixed prefix sum of
`[171, 341, 229, 186, 371]` plus the row within the life. The total is 1,298 bits, ending exactly
at the next save field. Appended rows would alias the following Life's bits. The replacement
handles any row `>= vanilla_count[life]` through the sidecar; vanilla rows still run the original
instruction sequence (or are passed through unchanged).

Recipe manager `0x006ffe88` holds five `0x3c`-byte table objects (resource IDs `8388–8392`:
alchemy, blacksmith, carpentry, cooking, tailoring). Their row count is dynamic through
`crafting_recipe_count` (`0x005af414`), so the SCR tables may grow without a code literal patch.

## The nine hard-coded sites

All nine are literal-pool words `0x00000aaf`; there are no other `0xAAF` immediate/literal
encodings in the EU v00 `.text` scan. Each is patched only after the live item table is known to
have `> 2,735` rows; if any word is not `0xAAF` (or the module's previous count), activation fails
closed and all literals stay at 2,735.

| literal word | user / range | what it bounds | runtime action |
| ---: | --- | --- | --- |
| `0x00239680` | `0x00239570–0x0023966c` collection/recipe list builder | first loop `id < 2,735`; tests save item bit kind 9, skips category 7, calls `0x24d920` | patch count |
| `0x00438524` | `0x00438408–0x00438510` same builder in the other menu path | same item loop | patch count |
| `0x0038f1cc` | `0x0038ee38–0x0038f1c8` category histogram (`fp` and `r5`) | loops every item and increments eight per-category counters at `mgr+0x8400` | patch count |
| `0x004392ac` | `0x00439070–0x00439290` crafting menu category counts | item loop before the five recipe loops | patch count |
| `0x0039b964` | `0x0039b91c–0x0039b960` item-validity helper | `id >= 2,735` returns 0 before `0x2295d8`/`0x242ff4` | patch count |
| `0x003aaaf4` | `0x003aaaac–0x003aaaf0` native item-validity helper | `id >= 2,735` suppresses the result write | patch count |
| `0x005673a0` | `0x00567370–0x0056739c` inventory/validity wrapper | `id < 2,735` before `0x25c9dc` | patch count |
| `0x00567818` | `0x0056774c–0x00567814` `script_inventory_change` | positive/negative item IDs must be `< 2,735` | patch count |
| `0x00567880` | `0x00567850–0x0056787c` second inventory/validity wrapper | `id < 2,735` before `0x25c9dc` | patch count |

Correction to the earlier Phase 1b note: `0x239680`/`0x438524` are **item collection** loops, not
recipe loops. The recipe loops in the same functions begin later at `0x2395f8`/`0x4384a4` and use
`0x005af414` plus `0x002e06b0`; they do not use `0xAAF`.

### Save/load path

No code patched the save serializer. A modded save's **inventory rows** carry ordinary u16 item IDs
and are unaffected. The fixed collection and recipe **bit sets** are the overflow risk, and those
are handled by the bit-index hook plus the sidecar:

- acquisition of appended item `id` is recorded after `0x0056774c` returns success for a positive
  delta; removal does not clear the collection flag;
- vanilla item IDs never enter the sidecar;
- the sidecar is `fl-items.sidecar` in the game's save folder, profile-keyed (`FL_ITEM_PROFILE`,
  default `profile-1`), written atomically through a `.tmp` rename;
- extended recipe set/clear uses the same file.

This is deliberately **additive state**: without the mod, vanilla still sees its own save and its
own bits. With the mod, the sidecar restores the extended IDs. A future UI that needs to show the
real extended collection/recipe state should read `items::collected()`/`items::recipe_known()` or a
future bridge, not assume the guest aliases are a one-to-one record.

## Runtime hooks

`port/runtime/src/games/fantasylife/items.cpp` refuses any code image other than
`a2e10e861c49220070b74d2b3c1d6f8cc7e253bfa837a4b7543f87e0166b35bb` and registers:

| address | kind | replacement behavior |
| ---: | --- | --- |
| `0x001fd520` | before | refresh the live item table before any item lookup |
| `0x00204454` | replace | appended item → appended category-stat row |
| `0x005b7130` | replace | kind 9, appended ID → placeholder bit `0xE48+58..77` |
| `0x0056774c` | replace | call original; on positive success record appended ID |
| `0x002e06b0` | replace | appended recipe row → sidecar test |
| `0x002e07d4` | replace | appended recipe row → sidecar set/clear |

The item table row count is read from the SCR descriptor at `0x00704a94`, not from a literal. A
count `<= 2,735` leaves all literals at vanilla; a count `> 65,535` leaves the module idle (item
IDs are 16-bit). A count in range but with an invalid category byte fails closed: the literals
are restored to 2,735 before any extended hook can run.

## Test evidence (offline)

`port/tools/test-fl-items.cpp` builds a scratch guest image with 2,738 item rows, three appended
stats rows and two appended recipes. It asserts:

- wrong digest refused; nine literals untouched;
- correct digest patches all nine literals to 2,738;
- appended weapon/armour stats rows `153`, `750`, `154`; vanilla/out-of-range IDs stay unmapped;
- item bit aliases `0xE48+58/59/60`, out-of-range alias stays in the buffer;
- vanilla stats and bit calls still reach their originals;
- positive acquisition records an appended ID, removal does not clear it, vanilla IDs are ignored;
- appended recipe test/set/read-back and out-of-table safety;
- sidecar contents (`profile=test`, `item=2735`, `recipe=0,171`) and reload with no guest bits.

`port/tools/test-fl-mod.cpp` additionally applies a synthetic overlay for archive ID **58,095**:
the count grows to 58,096, all four header arrays move, Resource 1 gains a standalone role and a
new index, ID 58,095's payload matches its donor, and untouched original payloads shift by the
13-byte header growth. The real Wooden Sword overlay still composes and reads back.

The Windows build uses the workspace LLVM-MinGW UCRT compilers, Ninja and
`port/build/win-deps/prefix` (not the host compiler's default dependency search).
With `build/items-test` configured in the hook-registry worktree:

```powershell
cmake --build build/items-test --target test-fl-items test-fl-mod test-fl-hooks runtime
ctest --test-dir build/items-test -R "fl-items|fl-mod|fl-hooks" --output-on-failure
```

The `fl-mod` CTest is registered when the local EU dump and Wooden Sword overlay
exist; override `FL_TEST_DUMP` and `FL_TEST_OVERLAY` to use another private location.
Python integration is in `tools/fl_mod.py`: explicit `append:true` allocations or
literal row edits grow all item/stat language families and individual recipe tables.
Standalone `files`, `textures`, `models` and raw donor `copies` may add contiguous
IDs from 58,095. The base `archive_count` stays 58,095 in the overlay fingerprint;
the runtime grows the archive and Resource 1. Run from the mod-stack worktree:

```powershell
python -m unittest discover -s tools/tests -t .
```

Synthetic tests cover item 2735, weapon stat row 153 in all nine slots, an appended
alchemy recipe, resource 58095 and rejection of gaps/protected IDs. No game is launched.

## What is still untested / open

1. **Boot test.** Nothing here has run the guest CPU or the game. The first runtime test should
   append one weapon and one bounty, verify acquisition and category stats, then save/reload.
2. **UI bridge for extended collection/recipes.** Guest lists use the 20 placeholder bits; the
   sidecar is authoritative but not yet rendered. Appended items may appear collected when their
   alias placeholder is collected, and vice versa.
3. **Save profile identity.** The default profile is `profile-1`; `FL_ITEM_PROFILE` can separate
   experiments. Binding the sidecar to the game's actual save slot requires the T4 save audit.
4. **Alias collisions.** Reusing items `58..77` as authored content in the same mod makes their
   collection flags indistinguishable from appended items. Use other rows or accept the shared
   flag.
5. **Stats tables must be extended together.** An appended item without appended stats rows maps
   to NULL (no stats), not to another category's row. This is safe but may make equipment unusable.
6. **Recipe UI count.** The five recipe table row counts drive the recipe loops; the sidecar only
   answers bit test/set. The recipe list's other fields still need valid appended 68-byte rows.
7. **Item IDs above 65,534** are not supported. The archive side supports IDs up to 65,534 because
   the index count is 16-bit; item rows above that are left vanilla.
8. **Language slots.** Every appended item row must be present in all 36 item-parallel tables and
   every stats slot; the runtime does not fill missing language variants.

## References

- `docs/phase1-archive-formats.md` — outer header and Resource 1 layout.
- `docs/phase1b-data-tables.md` — item/recipe/stats schemas and category block sizes.
- `port/docs/fl/items.md` — runtime module, settings and sidecar contract.
- `port/docs/fl/mods.md` — archive overlay format and new-ID rules.
- `tools/re/symbols_fl_eu.txt` — named addresses used above.
