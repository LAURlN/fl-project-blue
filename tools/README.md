# Phase 0 dump tools

`phase0_extract.py` uses Python 3.10+ and the standard library only. It opens the
input read-only, checks **every populated NCCH partition** before extraction, and
exits with status 2 without creating output if any partition lacks `NoCrypto`.
It has no decryption or key-loading functionality.

From the project root:

```sh
python3 tools/phase0_extract.py dumps/0004000000113100_v00.trim.3ds --inspect-only
python3 tools/phase0_extract.py dumps/0004000000113100_v00.trim.3ds --output extracted/fl_eu
python3 -m unittest discover -s tools -p 'test_phase0*.py' -v
```

Extraction requires a new or empty output directory. For another run, use a fresh
directory such as `extracted/fl_eu_check`; the tool refuses to mix new files with
old extraction results. Never put output under the source dump's directory.

Outputs include raw NCSD/NCCH headers; `exheader.bin` (0x800 bytes including the
access descriptor), `exheader-info.bin` (the hashed 0x400-byte information), parsed
`exheader.txt`; `plain.bin`, `logo.bin`; ExeFS files with compressed and decompressed
code retained separately; the complete RomFS file tree for each partition; per-file
SHA-256/size/first-four-byte manifests; ASCII executable strings with file offsets
and virtual addresses; selected ASCII/UTF-16 evidence in `analysis.json`; and the
full readable structured report `info.txt`. UTF-16 string scanning is heuristic.
The root is partition 0; `manual/`, `download_play/`, `update_n3ds/`, and
`update_o3ds/` correspond to partition indices 1, 2, 6, and 7 when present.

The tool validates partition/section/metadata bounds, safe names, BLZ bounds and
output length, NCCH exheader/logo/ExeFS/RomFS region hashes, individual ExeFS
hashes, and every extracted file against its original bytes. It checks the input
SHA-256 before and after extraction. It does not verify RSA signatures or the full
IVFC hash tree, unpack game-specific archives, or recursively process embedded
CIAs. Names and bounds checks are intended for this local dump workflow, not as a
general security boundary for untrusted images.

The report's format references are linked in
[`docs/phase0-dump-analysis.md`](../docs/phase0-dump-analysis.md). No downloaded
source is required to run the tool. Local reference sources and the independent C
decoder used for validation are confined to ignored `tools/build/`.

## Phase 1a resource archive

`fl_archive.py` unpacks/rebuilds the Fantasy Life EU `_file_archive.bin`, including
its virtual named-pack members, Nintendo LZ11 compression and nested BPAK files.
Run it in isolated Python mode (Python 3.10+, no dependencies):

```sh
python3 -I tools/fl_archive.py list extracted/fl_eu/romfs/_file_archive.bin
python3 -I tools/fl_archive.py extract extracted/fl_eu/romfs/_file_archive.bin extracted/fl_eu/archive
python3 -I tools/fl_archive.py build extracted/fl_eu/archive extracted/fl_eu/_file_archive.rebuilt.bin
python3 -I tools/fl_archive_catalog.py extracted/fl_eu/archive
python3 -I -m unittest discover -s tools/tests -v
```

Extraction requires a new/empty directory and keeps `.fl_archive/manifest.json`
and `.fl_archive/original.bin` for exact preservation of unchanged compressed
streams and padding. Edit extracted leaf files and keep these metadata files;
build supports resized resources and nested member edits. Adding/removing IDs or
named members is unsupported. Cataloging verifies original extracted hashes and
writes private `catalog.json`, `entries.tsv` and `scr-tables.tsv` under
`.fl_archive/`; run it before editing or after extracting the rebuilt archive.
The [Phase 1 format catalog](../docs/phase1-archive-formats.md) documents the
layout, verified round trips, important item/recipe/quest IDs and tool support.

## Phase 1b game data

`fl_scr.py` dumps any SCR table to editable JSON (or a readable CSV) and rebuilds it byte
for byte; `schemas/*.json` name the columns of the item, recipe, quest, challenge, map and
flag tables; `fl_data.py` validates cross-table links, reports Origin Island content and runs
an edit/rebuild/re-extract proof into a new directory; `make_schemas.py` regenerates the
schemas from an extraction. Isolated Python 3.10+, no dependencies:

```sh
python3 -I tools/fl_scr.py dump extracted/fl_eu/archive/_unnamed/06800_eadfc9eb2438.scr /tmp/items.json
python3 -I tools/fl_scr.py build /tmp/items.json /tmp/06800_new.scr
python3 -I tools/fl_data.py validate extracted/fl_eu/archive
python3 -I tools/fl_data.py proof extracted/fl_eu/archive extracted/fl_eu/mod_test
```

See [`docs/phase1b-data-tables.md`](../docs/phase1b-data-tables.md) for the format, schemas,
editing workflow, append limits and Origin Island findings.

## Phase 2 maps and enemies

`fl_map.py` inventories areas, door bones and monster bundles and losslessly
edits `0ff14033` placements. SCR schemas cover map-to-spawn resource 8695,
spawn groups, monster names/loot, unit bundles and battle parameters. Resource
8695 was previously misidentified as an icon atlas; its schema is now
`map_spawn_index`, replacing `icon_atlas`.

```sh
mkdir -p tools/build/maps
python3 -I tools/fl_map.py area extracted/fl_eu/archive 25 tools/build/maps/plains.json
python3 -I tools/fl_map.py doors extracted/fl_eu/archive 0 tools/build/maps/doors.json
python3 -I tools/fl_map.py monster extracted/fl_eu/archive 11 tools/build/maps/wolf.json
python3 -I tools/fl_map.py dump extracted/fl_eu/archive/_unnamed/23053_*.bin tools/build/maps/spawns.json
# Edit rows (coordinates, references, known warp/spawn payloads); preserve original.
python3 -I tools/fl_map.py build tools/build/maps/spawns.json tools/build/maps/spawns.bin
python3 -m unittest discover -s tools/tests
```

Appending same-document type-3/12 clones or changing map groups requires
`build --experimental-growth`. New clones need a unique UID and sequential
index; new spawns also need map-group membership. Keep cloned payloads unchanged
for this build, dump again, then edit the independently copied payload. Nested
point/condition arrays cannot resize, and opaque payloads cannot be relocated.
Unknown bytes and float bit patterns are preserved. `model INPUT OUTPUT.json`
inspects ZMDL metadata; it does not build models or collision.

See [Phase 2](../docs/phase2-maps-enemies.md) for the layouts, static evidence,
remaining script/runtime limits and concrete house/enemy plans;
[the modding guide](../docs/modding-guide.md) covers authoring and packaging.
`re/rtti.py NAME-SUBSTRING` lists simple Itanium RTTI/vtable candidates in
`code.bin`; previews are bounded, but require disassembly to establish table extent.

## Phase 1c event scripts

`fl_script.py` disassembles/assembles two-section VM/message wrappers and preserves
placement containers. Native command handlers/argument counts are in
`re/script_commands.json`; semantic names have separate confidence levels.

```sh
mkdir -p tools/build/scripts
python3 -I tools/fl_script.py disasm extracted/fl_eu/archive/_unnamed/21912_*.scr \
    --archive extracted/fl_eu/archive --language 8 -o tools/build/scripts/shop.fls
python3 -I tools/fl_script.py asm tools/build/scripts/shop.fls tools/build/scripts/shop.scr
python3 -I tools/fl_script.py find-flag extracted/fl_eu/archive 1963
python3 -I tools/fl_script.py check extracted/fl_eu/archive
python3 -m unittest discover -s tools/tests
```

Labels relocate branches, calls, entrypoints and shared global-function PCs.
Resolved comments are informational and conservative; message SCR text is edited
with `fl_scr.py`, typed placement fields with `fl_map.py`. The assembler checks
structure, not VM stack types or runtime capacity. See [Phase 1c](../docs/phase1c-scripts.md)
for the full specification, quest/shop/door examples, layer selection, purchase
flag consumers and headless research reproduction. No playable overlay is included.

## Textures, models and mod overlays

`fl_ztex.py` decodes/encodes ZTEX textures (all PICA200 formats incl. ETC1/ETC1A4, mips,
multi-image containers with their extra records) to and from PNG; `fl_zmdl.py` inspects
ZMDL models, exports OBJ and standard glTF 2.0 (`.glb`), imports glTF 2.0 into donor models
with skinning/palette splitting and smooth outline normals, and renders offline toon previews
(`--up y` for units/monsters); `fl_map.py` inspects placement containers and exports area maps to `.glb`;
`fl_mod.py` builds a mod source folder (`mods/<name>/mod.json`: table edits, `textures`, `models`
via `.glb` or `.json`, `placements`, `scripts`, `files`) into a port overlay and checks
monster, spawn-group, loot-order and spawn-region links.
`build-stack` merges source mods; `allocate` reserves dummy slots with symbolic IDs.
Isolated Python 3.10+, no dependencies:

```sh
python3 -I tools/fl_ztex.py decode extracted/fl_eu/archive/_unnamed/16418_*.tex /tmp/icon.png
python3 -I tools/fl_ztex.py encode my_icon.png /tmp/icon.ztex --name icn_test --format etc1a4
python3 -I tools/fl_zmdl.py info extracted/fl_eu/archive/_unnamed/03804_*.mdl
python3 -I tools/fl_zmdl.py gltf extracted/fl_eu/archive/_unnamed/03804_*.mdl /tmp/sword.glb \
    --ztex extracted/fl_eu/archive/_unnamed/03805_*.tex --up z
python3 -I tools/fl_zmdl.py import-glb extracted/fl_eu/archive/_unnamed/03804_*.mdl \
    /tmp/custom_sword.glb /tmp/out.mdl --bone R_tool --up z
python3 -I tools/fl_map.py gltf extracted/fl_eu/archive 150 /tmp/general_goods.glb
python3 -I tools/fl_zmdl.py render extracted/fl_eu/archive/_unnamed/03804_*.mdl \
    extracted/fl_eu/archive/_unnamed/03805_*.tex /tmp/sword.png
python3 -I tools/fl_zmdl.py render extracted/fl_eu/archive/unit/mon/mon004/0001/model/mon004_0001.mdl \
    extracted/fl_eu/archive/unit/mon/mon004/0001/model/mon004_0001.texa /tmp/red-wolf.png --up y --yaw -40
python3 -I tools/fl_mod.py build extracted/fl_eu/archive mods/wooden-sword \
    port/build/fl-data/yw2-recomp/mods/fantasylife/wooden-sword --replace
python3 -I tools/fl_mod.py build-stack extracted/fl_eu/archive tools/build/overlays/combined \
    mods/sword-a mods/sword-b --replace
```

Formats, free icon/model slots and the art workflow are in the
[modding guide](../docs/modding-guide.md#custom-icons-textures-and-models).
## Free Life / story-skip audit

`fl_story_skip.py <absolute extraction> <ignored report.json>` derives the base
post-story flag set from SYS003's completion switch and verifies the **8000 Bliss**
story/Flutter ledger. `fl_mod.py build` invokes it for the source-only
`mods/story-skip/` preset. See `docs/story-skip.md` and
`docs/testing/story-skip.md` in the main repository for design and user acceptance.
No game is run by either tool.

From a task worktree, all real-data unit checks can read the original extraction
by absolute path without copying it or creating data symlinks:

```sh
FL_EU_ARCHIVE=/home/laurin/.t3/projects/fl-project-blue/extracted/fl_eu/archive \
  python3 -m unittest discover -s tools/tests
```

## Co-op freedom sites

`fl_coop_gates.py` pins the multiplayer-gate call sites the runtime co-op hooks lift
([docs/coop-freedom.md](../docs/coop-freedom.md)). It edits no resource.

```sh
python -I tools/fl_coop_gates.py check <absolute>/extracted/fl_eu/archive tools/build/merged-mods/*
python -I tools/fl_coop_gates.py generate <absolute>/extracted/fl_eu/archive port/runtime/src/games/fantasylife/coop_sites.inc
```

`check` proves every pattern matches only its gate's sites in the whole corpus and reports
where each site sits inside stacked overlays (story-skip replaces 21172/27679). After any
change, update `GENERATED_SHA256` and regenerate the port table.
