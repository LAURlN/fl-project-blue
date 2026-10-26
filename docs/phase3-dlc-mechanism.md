# Phase 3: how Fantasy Life (EU) detects and unlocks DLC

> **Note:** paths starting with `port/` (and `runtime/`) refer to the runtime's source code, which is not part of this package. They are kept as historical research context.

Static analysis of `extracted/fl_eu/exefs/code.bin` (decompressed, base `0x00100000`,
SHA-256 `a2e10e86…b35bb`). Addresses are virtual addresses in that image; names are in
`tools/re/symbols_fl_eu.txt`. "(inferred)" means deduced from data flow, not from a
symbol or string. Nothing here was run on hardware; the one runtime fact used is the
existing port adapter (`port/runtime/src/games/fantasylife/aoc.cpp`), which was only read.

## TL;DR

1. The game never opens `ID_ECFlag_0000.dat`. The string is not in `code.bin`, and no
   `ID_`/`ECFlag_` prefix or `%04d` composition exists. The DLC is detected through
   **`am:app` content infos for title `0004008C00113100`** (owned bit + installed bit).
   The file name is only a placeholder inside the add-on content.
2. Result: a 256-bit global bitset, `cAppECFlagData` at **`0x748a24`**. Bit `k` is set iff
   the `k`-th listed DLC content (TMD content index `k+1`) is owned and installed.
   Origin Island = bit 0 = TMD content index 1.
3. Bits do not unlock anything directly. Resource **5780** is a 4-byte-per-row table
   indexed by *event flag ID*; a row names the ECFlag bit that controls that event flag.
   `event_flag_test_with_ec` (`0x205da8`, ~150 callers) returns `ECFlag bit || save-file bit`.
   Event flag **1963** ("EX patch purchased", `200_0001`) and 1968 are bit 0.
4. Second DLC slot: yes, by design. Bits 0-30 and 40-45 already have event-flag rows, bits
   31-39 and 46-255 are free, and 18 unused "EX dummy flag" event flags (2213-2221,
   2253-2261) are available to map onto new bits with a table-only edit.
5. Resource archive: count `N` is read from the file header, not hard-coded. Appending IDs
   is possible but needs the relationship index (resource 1) extended as well; there is
   exactly one archive open site, and no built-in second-archive support.

## Tooling (no GUI)

| Script | Purpose |
| --- | --- |
| `tools/re/ghidra.sh --import` | One-time Ghidra 10.1.5 headless import of `code.bin` (`ARM:LE:32:v6`, raw, base `0x100000`; `ImportFl.java` splits text/rodata/data and adds `.bss` `0x6dc000+0xcca88`). Project lives in ignored `tools/build/ghidra-project`. JDK 17 + Ghidra are under ignored `tools/build/`. |
| `tools/re/ghidra.sh OUT ARGS…` | 4-second headless queries: `0xADDR` decompile function, `A:B` decompile range, `x:ADDR` xrefs, `X:ADDR` deep xrefs through literal pools. Writes `OUT/<addr>.c` and `OUT.log`, `OUT/query.txt`. |
| `tools/re/fl_inspect.py` | Capstone/regex helper: `strings`, `refs`, `calls` (BL/B scan, more complete than Ghidra's call graph), `disasm`, `words`. Needs `PYTHONPATH=tools/build/re-python` (capstone 5.0.6) for `disasm`. |
| `tools/re/ipc_scan.py` | Lists IPC command headers stored to TLS+0x80 (`--range LO HI`). |
| `tools/re/ecflag_table.py` | Dumps resource 5780 (event flag → ECFlag) with labels from 5417. |

Caveat: Ghidra's raw ARM auto-analysis misses many functions (e.g. only 1 of ~150 callers of
`0x205da8` was found). Use `fl_inspect.py calls ADDR` for caller lists.

## Call chain

```
boot: fl_early_init 0x1056b0
   ├─ rom_mount_with_extra_patch 0x10a09c  (MountRom 16 dirs/16 files; "patch:" ROM skipped)
   ├─ archive_file_open 0x109f88           ("rom:/_file_archive.bin", count N read from file)
   └─ ec_flags_reset_and_init 0x107e00     (cAppECContents create, zero cAppECFlagData bitset)
         └─ nn_aoc_services_init 0x11312c  (am:app 0x1130d8, nim:aoc 0x1137fc)

title / slot select (state machine, handler table at 0x626100)  and  Payable-Content task
   ec_refresh_and_report 0x22bc5c
      ec_refresh_list 0x32ba5c(mgr, verify=0)
         nn_am_dlc_count_minus_one 0x5bd42c      → am:app 0x1001 GetDLCContentInfoCount, n-1
         nn_am_dlc_list_from_one   0x5bd3c0      → am:app 0x1003 ListDLCContentInfos, start+1
         ec_build_entries 0x32be88               (24-byte AM records → 16-byte entries, sorted by index)
      ec_flags_rebuild 0x5ab6bc                  (entries → bitset 0x748a24)
   later:  event_flag_test_with_ec 0x205da8(localFlags, eventFlagId)
              row = scr_table_row(g_event_flag_attr_table 0x7005c0, eventFlagId)   // resource 5780
              ecbit = row.u16;  ecbit != 0xffff && bitset[ecbit]  →  TRUE
              else local save-file flag bit
```

Only one `ec_refresh_list` call passes `verify=1`: the Payable-Content task (`0x28b590`).
All other refreshes (title/slot select, `0x22bc5c`) use `verify=0`, i.e. no `content:` mount.

### The IPC surface the game actually uses (EC/DLC)

| Service | Command | Wrapper | Notes |
| --- | --- | --- | --- |
| `am:app` | `0x1001` GetDLCContentInfoCount | `0x47dda8` | game subtracts 1 (skips content 0) |
| `am:app` | `0x1003` ListDLCContentInfos | `0x47dccc` | game passes start index + 1 |
| `am:app` | `0x1002`, `0x1004`, `0x1005`, `0x1007`, `0x1009`, `0x100a`, `0x100d` | headers at `0x47dc18…0x47dedc` | present in the SDK wrappers; only 0x1001/0x1003 are on the flag path |
| `fs:USER` | OpenArchive `0x2345678a` (NCCH archive) | `0x484600` via `0x48316c`/`0x483240` | binary path `{unique id (0x00113100 from the game's own program ID), 0x0004008C, media=1 (SD), content index}`, mounted as `content:` |
| `nim:aoc` | init only on this path | `0x1137fc` | shop/price data comes from the `ContentInfoArchive_*.bin` file instead (below) |

The DLC title ID is derived from the game's own program ID with high word `0x0004008C`
(`0x483188`, `0x4827c0`), so **any DLC for this game must live inside title
`0004008C00113100`**; it can only add *content indexes*, not a new title.

### Data layouts

* AM record (24 bytes, `ListDLCContentInfos`): `u16 index, u16 type, u32 id, u64 size,
  u8 ownership@0x10, pad`. `ownership & 2` = owned (`0x5bcd60`), `ownership & 1` = installed
  (`0x5bccc4`). The port adapter reports 3 for every content.
* `cAppECContents` entry (16 bytes, array at `mgr+0x5c`, count at `mgr+0x58`): `u16 index,
  u8 owned@2, u8 installed@3, u8 invalid@4, u32 size@8, u32 blocks@0xc`. Sorted ascending by
  `index` (`0x592528`).
* `cAppECFlagData` @ `0x748a24` (vtable `0x68dea8`, typeinfo name `0x67ef1d`): bitset words
  at `+4…+0x20` (8 words = 256 bits), word count `8` at `+0x24`. In `.bss`; it is **not**
  stored in the save. It is zeroed at boot and recomputed on every refresh.
* Bit rule, `ec_flags_rebuild` (`0x5ab6bc`, verified in raw ARM): for every entry `i`,
  `b = (s16)(entry[i].index - 1)`; `bit[b] = b < count && !entry[b].invalid && entry[b].owned
  && entry[b].installed`. Note it looks up **array position `b`**, not the entry whose index
  is `b+1`. This only agrees when the listed indexes are the contiguous run `1..count`
  (content 0 is dropped by `count-1` and `start+1`). Gaps in the TMD indexes give wrong bits.
* Resource **5780** (`SCR` table, magic `1380031d`, 4345 rows × 4 bytes; ID `0x1694`, loaded
  by `0x2cfd9c`): `u16 ecbit` (0xffff = none), then one byte with 1-bit fields `c01`, `c02`,
  `c03`. Row index = event flag ID, labels come from resource 5417 (`event_flags`).
  `c01` is tested at `0x371b94` and `0x371c14` (the latter sets the local bit unless `c01`
  is set); `c02`/`c03` consumers were not found.

### Current ECFlag assignments (`tools/re/ecflag_table.py`)

| ECFlag bit | TMD index | Event flags (label) |
| --- | --- | --- |
| 0 | 1 | **1963** `200_0001 EXパッチ課金済み` (EX patch purchased), **1968** `200_0006 LINKキット購入者` |
| 1 | 2 | 1964 `200_0002 EXダミーフラグ02(テスト)`, 2183 `200_0221 ECコンテンツ購入01/エモーションセット` |
| 2-30 | 3-31 | 2184-2212 `ECコンテンツ購入02…30` (2184 = avatar parts set) |
| 31-39 | 32-40 | unassigned |
| 40-44 | 41-45 | 2062-2066 avatar hairstyle pages 13-17 |
| 45 | 46 | 2112-2123 `ID_EmotionAct_020…031` |
| 46-255 | 47+ | unassigned |

Unmapped placeholder flags: 2213-2221 (`EXダミーフラグ251-259`) and 2253-2261
(`291-299`); 2222-2252 are `ECコンテンツコイン受け取り00-30` (EC coin receipt, 0xffff).

Other direct consumers of bit 0 / flag 1963: `0x371a90` (called from `0x26fea0`) sets
bit `0x800` in a player/field flag word when flag 1963 is EC-controlled; `0x5ab7fc`
returns 2 when the first listed content (`g_ec_state.short@+2 == 0`) is owned. That value
feeds the `"VERSION"`/`"FL_LINK"` record in `0x22bc5c` and save-slot UI states at
`0x316a98`/`0x317000` (a save marked with EX state while the content is missing is
handled there; exact messages not traced).

### Files inside the add-on content

* Content index 0 (the 56 KiB NCCH): `ContentInfoArchive_EUR_{de,en,es,fr,it,nl,pt,ru}.bin`
  and `MetaDataContentHeader.bin`. `ec_read_content_info_archive` (`0x4800c8`) formats
  `"/ContentInfoArchive_%s_%s.bin"` (region, language), reads 200-byte records at
  `8 + 200*contentIndex` (`u16 index`, `0x40` title, `0x80` description, `u32` flag at
  `+0xc4`; a record with `[0xc4]==0` yields an error). This is shop/menu text only.
* Content index 1 (20 KiB): the single file `ID_ECFlag_0000.dat` (never opened by name).
  The game only needs the NCCH to be listed, owned and installed (and, in the Payable
  Content task only, mountable as `content:` via `0x32c428`).

## Resource archive (item 2)

* `archive_file_open` (`0x109f88`) reads the first 8 bytes of `rom:/_file_archive.bin`
  (`u32 N`, reserved), allocates `13*N` bytes and reads the table: offsets `4N` (`+0x4c`),
  sizes `4N` (`+0x50`), compression bytes `N` (`+0x58`). Matches the layout in
  `docs/phase1-archive-formats.md`. No constant near 58095 (`0xe2ef`) appears in code or
  literal pools (scanned as 32-bit words, `movw`, `cmp`/`mov` immediates).
* `archive_lookup_offset` (`0x1b2dc8`): `id >= N` → NULL. If the relationship-index object
  (`archive +100`, container magic `0x530e30c3` = resource 1, fixed up at `0x13ac54`) is
  present, it also requires `id < u32 at index+4` (295,188 in this dump) and uses the
  per-ID 4-byte role record (bit 20 = virtual pack member, else low 20 bits = physical
  slot). So **a new ID needs a role record in resource 1**, which also holds the `u16`
  file count (`0x08`), i.e. IDs are limited to 65,535 (7,440 spare IDs).
* `resource_load_core` (`0x13d3d8`) has a second "loose override" path
  (`DAT_0013d764` flag byte `==1` plus `archive_override_lookup` `0x1b2d64`), likely a
  development path; not investigated.
* Only one archive is opened (`0x10572c`, path from the `.data` table at `0x6abcc0`). There
  is no second-archive mechanism. The `"patch:"` ExtraRom mount in `0x10a09c` is disabled
  by the size arguments `-1,-1` at its single call (`0x105718`). That is for the ROM
  file system, not for resource IDs.

## Proposal: custom DLC that plugs into the same mechanism

The goal is "same mechanism" = **DLC content index → ECFlag bit → table 5780 row → event
flag → scripts/tables**. Everything except the first arrow is data.

### Data-only parts (no change to recompiled C)

1. **Pick a bit and a flag.** Use ECFlag 31 and event flag 2213 (`EXダミーフラグ251`). Edit
   row 2213 of resource 5780: `ecbit = 31`, keep `c01 = c02 = 0`, `c03 = 1` (as the other
   dummy rows). Size is unchanged, so `tools/fl_scr.py` + `tools/fl_archive.py` can rebuild it.
   Additional DLC packs use 32-39 and flags 2214-2221 / 2253-2261.
2. **Gate content with the event flag.** New quests/NPCs/shops/maps test event flag 2213
   through the normal script/table conditions, so they follow `event_flag_test_with_ec`
   exactly like flag 1963.
3. **Content payload.** Either replace existing leaf resources (same ID, size may change;
   supported by the current repacker) or append new IDs (below).
4. **AOC catalog.** Provide a DLC description to the port's AOC adapter (today a single
   CIA via `FL_DLC_CIA`). For ECFlag 31 the adapter must report TMD content indexes
   `1…32` with no gaps (see the bit rule). Indexes you do not own are reported with
   `ownership = 0` (they only need to exist; owned bit clear gives bit clear). Index 32's
   RomFS can be a stub; it is not read on the flag path.

### Minimal code patch (recommended for the first prototype)

The contiguity constraint makes step 4 ugly. A tiny patch in the recompiled C avoids it:
wrap `f_005ab6bc` (`ec_flags_rebuild`; `port/build/generated-fl_eur/funcs.h`,
`lookup.c` entry `{0x005ab6bcu, f_005ab6bc}`) so that after the original runs it ORs in
host-controlled extra bits into `g_ECFlagData` (`+4`, bit `k` = word `k>>5`, mask
`1<<(k&31)`). The bits come from a user-data manifest (for example one JSON file per custom
DLC with `ecflag`, `title`, `files`). This also needs no fake TMD indexes and keeps the
original DLC working. Only `ec_flags_reset_and_init` zeroes the bitset (boot), and rebuild
touches only bits `< count`, so bits ≥ 31 survive until the next boot.
`event_flag_test_with_ec` and every script that reads the event flag work unchanged.

### New resource IDs (only if the DLC needs new assets)

Option A, offline: extend `tools/fl_archive.py` to add IDs `≥ 58095` (increase `N`, append
13 bytes/ID to the tables, give the new IDs role records `{0xffff, 0}` at the end of
resource 1 and bump its count fields). The table grows, so all base offsets shift; unchanged
resources stay byte-identical. Option B, runtime: serve a virtual
`rom:/_file_archive.bin` from the port's RomFS layer (base + DLC delta rewritten on open),
which keeps the base archive pristine and lets users add/remove DLC packs. Option C: patch
`archive_lookup_offset` to consult a second table; more invasive and needs a hook in the
resource-load path (`0x13d3d8`).

### Risks and unknowns

* **Gating of Origin Island is not traced to the script level.** I verified the engine path
  to event flag 1963 (and flag 1968, the `0x800` feature bit, `ec_check_first_content`), not
  which scripts/maps test it. Verify at runtime by logging `f_00205da8` results with the DLC
  CIA on/off before relying on "unlock = flag only".
* Contiguity rule of `ec_flags_rebuild`: bit `k` depends on array position `k`, so sparse
  TMD indexes silently fail (or read past the array if `count` is small).
* Bits 1-30 and 40-45 have live event-flag rows; granting those contents would unlock
  existing features (emotion set, avatar parts, hairstyle pages) unintentionally.
* `ContentInfoArchive_*.bin` is only needed for the shop UI; the Payable-Content menu will
  show no entry for a custom index unless a 200-byte record exists, and its `verify=1`
  path mounts `content:` and marks failures `invalid` (the next rebuild clears the bit).
* The 256-bit bitset has no bounds check in `0x1b8404`; bit indexes must stay `< 256`.
* Appending resources: resource 1 and the 65,535-ID ceiling; named-pack members use `u16`
  member IDs. The loose-override path and the `+100` object were read, not run. Expect to
  confirm by a boot test with a trivially appended resource.
* Event flags live in save data (`local` bitset); an event flag that was set before the
  DLC existed is not removed when the DLC is withdrawn. ECFlag-controlled rows are read
  through, but `0x371c14` refuses to write only rows with `c01` set.
* Not tested on hardware or in the port; everything above is static.

## Reproduction

```sh
tools/re/ghidra.sh --import            # one time (already done in this workspace)
tools/re/ghidra.sh tools/build/q 0x5ab6bc 0x205da8 X:0x748a24
PYTHONPATH=tools/build/re-python python3 tools/re/fl_inspect.py disasm 0x5ab6bc --size 0xc8
python3 -I tools/re/ecflag_table.py
python3 tools/re/ipc_scan.py --range 0x47d000 0x486000
```
