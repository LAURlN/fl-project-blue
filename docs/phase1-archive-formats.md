# Fantasy Life EU — Phase 1a resource archive

> **Note:** paths starting with `port/` (and `runtime/`) refer to the runtime's source code, which is not part of this package. They are kept as historical research context.

## Result and reproduction

`_file_archive.bin` is an indexed Fantasy Life archive, **not XFSA**. The complete
372,881,344-byte archive has been extracted to `extracted/fl_eu/archive/`.
All game data, preservation metadata and research checkouts remain gitignored.
No downloaded build scripts or game code were executed.

The unchanged extraction rebuilds **byte for byte**, including compression choices,
alignment gaps and final padding. Original and rebuilt SHA-256:
`20570a9490821fcb7eaced47286041adadb7d36a946e0b6c84f5e036b1cdd9f6`.

```sh
python3 -I tools/fl_archive.py list extracted/fl_eu/romfs/_file_archive.bin
python3 -I tools/fl_archive.py list extracted/fl_eu/romfs/_file_archive.bin --json
python3 -I tools/fl_archive.py extract extracted/fl_eu/romfs/_file_archive.bin extracted/fl_eu/archive
python3 -I tools/fl_archive.py build extracted/fl_eu/archive extracted/fl_eu/_file_archive.rebuilt.bin
cmp extracted/fl_eu/romfs/_file_archive.bin extracted/fl_eu/_file_archive.rebuilt.bin
python3 -I tools/fl_archive_catalog.py extracted/fl_eu/archive
python3 -I -m unittest discover -s tools/tests -v
```

Extraction requires a new/empty directory. The existing extraction is complete;
use a different directory to repeat it. Python 3.10+ and the standard library are
sufficient. `list` reports every logical ID, role, offset and size; its JSON
output also exposes the complete parent/member relationship index.

The extraction has three representations:

- `_unnamed/<decimal-ID>_<SHA256-prefix>.<inferred-extension>`: 36,440 physical
  resources without stored names. The ID is authoritative; the 12-digit content
  hash is an extraction label, **not a game filename hash**.
- `_packs/<ID>_<SHA256-prefix>.bin`: 1,764 decompressed named pack containers.
  Their 19,891 members are also restored at their real `avatar/` and `unit/` paths.
- `*.unpacked/`: recursively expanded BPAK contents; member names here are
  generated from member ordinal and content hash. These are editable inputs too.

`.fl_archive/manifest.json` maps every ID to its path, original sizes, original
content hash and nested-member locations. `.fl_archive/original.bin` is an
explicit preservation cache of the source archive (373 MB), required for build.
An unchanged build verifies the extracted payload hashes and reuses those
original bytes. Edited builds reuse unchanged compressed streams, reconstruct
changed nested packs, encode changed physical resources as LZ11, and recalculate
outer offsets/sizes. Keep the entire manifest/cache directory with the extraction.

Edit a leaf resource or its packed parent. Conflicting edits to both are rejected.
Size changes are supported, including changes inside named packs and BPAK.
Adding/removing logical IDs or named members, changing their paths, and modifying
the relationship index remain unsupported by `fl_archive.py`: executable references
and other tables also use these IDs. The port's runtime overlay can present new
standalone physical IDs 58,095–65,534 by growing the virtual header and Resource 1
in memory (see `docs/phase1b-item-expansion.md` and `port/docs/fl/mods.md`); the
archive file itself is never rewritten. Repacking correctness here is structural and
byte/content validation; the modified archive has not been boot-tested on 3DS.

## Outer archive specification

All integers are little endian. Let `N` be the u32 at offset zero.
There is no ASCII magic and no filename/name-hash table in the outer header.

| Offset | Size | Meaning |
| --- | --- | --- |
| `0x00` | 4 | Logical entry count; `0xe2ef` = **58,095** |
| `0x04` | 4 | Reserved; zero in this dump |
| `0x08` | `4*N` | Absolute u32 archive offsets, indexed by resource ID |
| `0x08+4*N` | `4*N` | Uncompressed sizes |
| `0x08+8*N` | `4*N` | Stored/compressed sizes; advisory for virtual entries |
| `0x08+12*N` | `N` | Compression bytes; 0 raw, 1 Nintendo LZ11 |
| `0x08+13*N` | variable | Padding then physical data |

The table ends at `0xb862b` (755,243); the first physical resource starts at
`0xb8640` (755,264). All physical starts are aligned to **32 bytes**.
Physical stored payloads total **371,506,422 bytes**. The physical uncompressed
sum is **1,639,112,887 bytes**. Summing all logical rows gives **1,900,180,109**
bytes, which counts named-pack members again and is not a unique-content total.

Only **38,204** table rows own physical payloads: **38,203 LZ11 + 1 raw**.
The other **19,891** rows are virtual named-pack members. Their outer offsets
follow the next physical allocation position in table order and often point to
an unrelated compressed pack; their sizes are individual-member metadata.
**Do not seek/decompress every logical row independently.** The older xfsatool
reader does this and consequently warns, truncates or returns the wrong resource
for virtual entries. Parent IDs need not precede their members; for example,
parent 58094 owns virtual IDs 58091–58093.

### Entry 1: authoritative relationship index

The sole raw entry is ID **1**, size **295,212**, magic `c3 30 0e 53`
(u32 `0x530e30c3`). Its structure was established from this dump and cross-checked
against every outer row and every named-pack member.

| Offset | Type | Meaning / observed value |
| --- | --- | --- |
| `0x00` | u32 | Magic |
| `0x04` | u32 | Total size minus 24: 295,188 |
| `0x08` | u16 | Logical file count: 58,095 |
| `0x0a` | u16 | Named-pack count: 1,764 |
| `0x0c` | u32 | Reserved: zero |
| `0x10` | u32 | Per-ID role-table offset: `0xf570` (62,832) |
| `0x14` | u32 | Pack-descriptor offset: `0xa2c0` (41,664) |
| `0x18` | variable | Lists of u16 member resource IDs, padded to 4 bytes |
| `0xa2c0` | `12*1764` | Pack descriptors |
| `0xf570` | `4*58095` | Per-ID role records |

A pack descriptor is `<u32 parent-ID, u16 member-count, u16 alignment,
u32 member-ID-list-offset>`. Member IDs correspond **in order** to the named
pack's file table. All 19,891 uncompressed member sizes agree with the outer rows.
A role record is `<u16 pack-ordinal, u16 kind>`: kind 0 is standalone
(ordinal `0xffff`), kind 1 is a physical named pack, kind 2 is a virtual member.
There are respectively 36,440 / 1,764 / 19,891 records. The codec validates the
whole mapping, not just adjacency or coincidental repeated offsets.

### Compression

Every physical compressed resource in this dump starts with Nintendo **LZ11**
(`0x11`, followed by a 24-bit decoded size; zero size uses the extended u32).
Flags are consumed high bit first. Literal flags are zero; match flags are one.
Distances are 12-bit encoded values plus one (1–4096 bytes). LZ11 has three
match-length forms: 3–16, 17–272 and 273–65,808. Overlapping references are valid.
The zero-byte physical resource, ID 9539, has an 8-byte extended-size stream.

The tool also implements Nintendo LZ10, RLE and 4/8-bit Huffman, plus Level-5
`decoded-size<<3 | codec` envelopes (raw/LZ10/Huffman4/Huffman8/RLE/zlib).
These additional codecs have synthetic tests; they are **not** claimed to occur
among this archive's physical streams. LZ decoding validates source bounds,
backreference distances, decoded-size bounds and exact output lengths.
Original streams are retained because a new compressor can choose different
matches while producing identical content. Unchanged repacking therefore does
not depend on reproducing Nintendo's original compression decisions.

## Nested containers

### Fantasy Life named pack: `52 20 0d 43` (`R`, space, CR, `C`)

All **1,764** named packs use this format. The 20-byte header has u32 magic at
0, total size minus 20 at 4, a reserved word at 8, a u32 with member count in its
upper 16 bits at 12 (lower bits observed zero), and an absolute table offset at
16. The table is at EOF; member count also equals `(file-size-table-offset)/20`.
Payloads and NUL-terminated ASCII paths are interleaved before that table.

Each 20-byte record is `<4B4I>`:

| Record offset | Meaning |
| --- | --- |
| 0 | Reserved byte, observed zero |
| 1 | Path length excluding NUL |
| 2 | Basename start (one past final `/`) |
| 3 | Extension start (one past final `.`) |
| 4 | Payload alignment, typically 4 or 128 |
| 8 | Payload byte length |
| 12 | Absolute path offset |
| 16 | Absolute payload offset |

The two bytes at offsets 2–3 are **path-component offsets, not a hash**. Both
match every recovered path. Named member payloads are uncompressed inside the
pack; the physical parent is LZ11 compressed as a whole. Member data alignment,
path metadata and EOF table are rebuilt on resize; original opaque fields and
same-size padding are preserved. Example real path:
`avatar/skeleton/common/AvaterB_body/model/AvaterB_body.mdl`.

### BPAK

**5,584** containers occur as physical resources or named members. Header:
`BPAK`, u32 count, then `count` pairs `<u32 absolute-offset, u32 byte-size>`.
They hold animation and effect members; zero-sized members are common and are
preserved. The extractor expands every BPAK and build propagates leaf edits
through BPAK and the enclosing named pack. An edited BPAK that needs resizing
retains the common power-of-two alignment observed in its original member
offsets; unchanged layouts are retained exactly. The observed common alignments
are 4 (3,511 packs), 8 (66), 16 (848), and 128 (1,159).

BPAK adds **17,842** leaf payloads beyond the 58,095 outer logical rows:

| Inner magic | Files | Interpretation |
| --- | ---: | --- |
| `zanm` | 13,413 | Fantasy Life skeletal/transform animation |
| `CGFX` | 3,462 | NintendoWare graphics/effect resources |
| `zmta` | 372 | Material/texture animation |
| empty | 595 | Zero-length members, not decoding failures |

No ARC0, XPCK, XFSA or `.lz` members occur in the completed extraction. Readers
for the prior-art ARC0/XFSA/XPCK layouts and automatic Nintendo `.lz` sidecars
are included and tested synthetically. ARC0/XFSA/XPCK names use CRC32 lookup;
this is distinct from Fantasy Life's index-based archive. Editing these unused
Level-5 container variants is explicitly rejected; FL named packs and BPAK
support rebuilding. All nested containers actually encountered were unpacked.

## Directory tree and file census

The census below counts the **58,095 logical resources**, including pack parents
and their members. It excludes the preservation cache, generated TSV/JSON and
BPAK sidecars. The entire expanded payload tree contains **75,937 files**,
**2,040,215,465 bytes**, before the preservation cache and metadata. These are
representation totals, not deduplicated storage requirements.

<!-- GENERATED CENSUS -->
| Top-level directory | Files | Decoded bytes |
| --- | ---: | ---: |
| `_packs/` | 1,764 | 262,876,792 |
| `_unnamed/` | 36,440 | 1,376,236,095 |
| `avatar/` | 1,020 | 18,070,488 |
| `unit/` | 18,871 | 242,996,734 |

Real named `unit/` subdirectories (prefixes are preserved, meanings tentative):

| Directory | Files | Bytes |
| --- | ---: | ---: |
| `avatar/skeleton/` | 1,020 | 18,070,488 |
| `unit/ava/` | 1 | 520 |
| `unit/bnp/` | 4,723 | 68,660,358 |
| `unit/cry/` | 135 | 523,380 |
| `unit/eff/` | 215 | 1,405,984 |
| `unit/fnt/` | 2,323 | 8,129,196 |
| `unit/itm/` | 9 | 8,640 |
| `unit/lit/` | 389 | 2,100,808 |
| `unit/mon/` | 4,666 | 100,290,700 |
| `unit/mpg/` | 808 | 8,023,836 |
| `unit/npc/` | 3,692 | 33,274,154 |
| `unit/obj/` | 9 | 8,640 |
| `unit/pic/` | 1,725 | 18,043,360 |
| `unit/vic/` | 173 | 2,521,168 |
| `unit/vis/` | 3 | 5,990 |

Extension histogram. Extensions under `_unnamed/` are **inferred**, while named
members retain their original extensions. Thus `.bin` also includes unknown
formats, fonts, UI binaries and named packs; it does not mean a single format.

| Extension | Files |
| --- | ---: |
| `.scr` | 12,877 |
| `.tex` | 11,612 |
| `.bin` | 9,028 |
| `.uparm00` | 4,760 |
| `.mdl` | 4,463 |
| `.pack00` | 1,584 |
| `.texa` | 1,551 |
| `.mata_pack` | 1,169 |
| `.effpack` | 1,166 |
| `.actparm00` | 1,097 |
| `.bpak` | 1,001 |
| `.actmot00` | 969 |
| `.bcsar` | 856 |
| `.sebin` | 828 |
| `.uparm02` | 691 |
| `.uparm03` | 691 |
| `.uparm01` | 512 |
| `.pack01` | 504 |
| `.actparm01` | 498 |
| `.actmot01` | 492 |
| `.missile01` | 487 |
| `.cb` | 250 |
| `.fb` | 243 |
| `.gb` | 242 |
| `.pack03` | 158 |
| `.actmot03` | 158 |
| `.actparm03` | 158 |
| `.mta` | 26 |
| `.mota` | 17 |
| `.pack02` | 2 |
| `.actmot02` | 2 |
| `.actparm02` | 2 |
| `.index` | 1 |

Magic histogram over the same logical resources. `COL` is a three-byte signature;
its varying fourth byte is payload, so all 245 collision resources are grouped.
Every other nonempty row below is an exact four-byte prefix. Numeric prefixes
are observations, not asserted formal magic/version definitions.

| Magic / hex prefix | Files |
| --- | ---: |
| `1380031d` | 16,675 |
| `ztex` | 13,163 |
| `02000000` | 5,926 |
| `BPAK` | 5,584 |
| `zmdl` | 4,463 |
| `60100040` | 2,290 |
| `af00b101` | 2,290 |
| `52 20 0d 43 (named pack)` | 1,764 |
| `actm` | 1,622 |
| `0ff14033` | 1,015 |
| `01000000` | 896 |
| `CSAR` | 856 |
| `0202d051` | 259 |
| `CB01` | 250 |
| `COL` | 245 |
| `FB01` | 243 |
| `GB01` | 242 |
| `00000100` | 239 |
| `zmta` | 26 |
| `MOTA` | 17 |
| `FNT ` | 12 |
| `07a14033` | 4 |
| `1280031d` | 3 |
| `SMDH` | 2 |
| `ffffffff` | 2 |
| `c3300e53` | 1 |
| `empty` | 1 |
| `003bd02c` | 1 |
| `0aa14033` | 1 |
| `06a14033` | 1 |
| `ac01a103` | 1 |
| `MSG ` | 1 |

Complete exact first-four-byte and extension/magic joint histograms are in
`extracted/fl_eu/archive/.fl_archive/catalog.json`. The accompanying `entries.tsv`
contains every payload path, size, magic and SHA-256; `scr-tables.tsv` lists
section-relative row counts, widths and offsets. Regenerate both with
`fl_archive_catalog.py`, which checks every payload against the extraction manifest.
All files classified as SCR were inspected structurally; an empty zero-width
table at ID 8565 is valid.

## Resource identification and existing tools

These are identifications from actual signatures, nested relationships and
content, with uncertain semantics marked explicitly. A format reader's presence
in another project is evidence of likely compatibility, not a successful GUI
import test performed here.

| Resource | Evidence and locations | Likely tooling / confidence |
| --- | --- | --- |
| Models | 4,463 `zmdl`; named `.mdl` under `unit/{mon,npc,bnp,pic,...}/.../model/` and avatar skeletons; many unnamed avatar/field models | **Ohana3DS Rebirth has a dedicated Fantasy Life ZMDL importer**. These are proprietary ZMDL, not ordinary BCMDL/CGFX or XMPR. High confidence. |
| Textures | 13,163 `ztex`, including 1,551 named `.texa` and 11,612 inferred `.tex`; embedded image names and tiled 3DS formats | **Kuriimu2 Ztex supports load/save**, and Ohana3DS Rebirth has a ZTEX loader. High confidence. Texture names/CRC32 and mipmaps belong to ZTEX, not the outer archive. |
| Animation | 13,413 `zanm` in BPAK motion packs; 398 total `zmta` (26 direct + 372 nested); `actmot` metadata and 17 `MOTA` resources | ZANM/ZMTA are Fantasy Life formats. A custom importer/converter is likely needed; do not assume generic NW4C animation import works. `.actmotNN` is an action/motion association format, not the vertex animation itself. |
| Effects | 1,166 named `.effpack` plus other BPAK; **3,462 actual `CGFX` members** | NW4C BCRES family. Ohana3DS, SPICA or Every File Explorer are appropriate first inspection tools for supported CGFX sections. Particle-specific behavior and export/reimport support remain unverified. |
| Maps/fields | 245 `COL` resources; 250 `CB01`, 242 `GB01`, 243 `FB01`, and recurring field-data bundles from ID ~8721 onward | `COL` is collision; CB/GB/FB are likely camera/ground/field companions (tentative). Proprietary field structures need custom work. Extracted ZMDL/ZTEX companions can be inspected independently in Ohana3DS. |
| SCR tables | `13 80 03 1d` appears in 16,675 logical rows, including named `.uparmNN`, `.sebin`, `.actparmNN` and inferred `.scr` | **RainThunder SCR/table code is the closest existing reader**. They are schema-driven row tables, not automatically Level-5 `cfg.bin`. Kuriimu2/CfgBin editors require a demonstrated matching schema or a new plugin. |
| Event/script data | 5,926 resources start with `02 00 00 00`; 1,015 with `0f f1 40 33`; smaller variants also occur | The `02` family is often a two-section SCR wrapper. The `0f f1...` family is a candidate field/script bytecode format; semantics/opcodes not decoded in Phase 1a. No proof of t2b use. |
| Text/dialogue | UTF-16LE string pools and control sequences inside SCR; one small `MSG ` resource (ID 33012, 558 bytes) | RainThunder's `SCR.getstring` documents several FL control sequences. Kuriimu2 would need a matching FL SCR text plugin/schema. The lone MSG file is not the main dialogue archive. |
| Fonts | **12 `FNT ` files**, IDs 5414–5416 and 5428–5436, with character maps and glyph data | Custom font format, not a `CFNT`/BCFNT signature. Every File Explorer/Kuriimu2 font tools may help inspect/convert components, but direct compatibility is unproven. `unit/fnt/` is a resource-category name and should not be equated with these twelve font binaries. |
| UI | **2,290 pairs** with prefixes `60 10 00 40` and `af 00 b1 01`, starting IDs 33045/33046; embedded `ui000_arrow` and layout/animation labels | Likely custom UI image/layout pairs (`cFwkUILayout*` also appears in code RTTI). They lack CLYT/CLAN/CLIM headers. Existing standard NW4C layout editors are not established as compatible. |
| Sound | 856 `CSAR` named sound banks, plus `.sebin` SCR tables | NintendoWare sound tooling (e.g. Every File Explorer's supported audio formats) is a starting point. These supplement the separate outer RomFS BCSAR/BCSTM streams. |

There are **no detected first-level or BPAK-member XI/IMGC, XMPR, XPCK, XFSA,
CLYT/CLAN, CFNT or BCH signatures** in the completed census. This is a statement
about the parsed payload boundaries, not an exhaustive scan of every internal
subsection. The existing outer RomFS `shaders.bcsdr` is CGFX, independently of the
3,462 nested effect resources above.

## DLC-relevant tables and dialogue: concrete locations

All IDs below are **decimal outer resource IDs**. For unnamed files, glob
`_unnamed/<five-digit-ID>_*` or consult `.fl_archive/manifest.json`. No original
basename exists for these rows; semantic labels below are analysis labels.

| Purpose | IDs / exact representative file | Rows × bytes | Evidence / interpretation |
| --- | --- | --- | --- |
| Stable item identifier strings | **6702**: `_unnamed/06702_d4b5faa2a06d.scr` (followed by variant slots through 6710) | 2,735 × 4 | UTF-16 pointers to `ID_Item_401_00001_00`-style symbolic IDs. |
| Item names and base metadata | **6792–6800**; English variant 6796, UK-style English **6800**: `_unnamed/06800_eadfc9eb2438.scr` | 2,735 × 28 | First u32 in each row points to an item name; first rows are Squire's/Bronze/Iron swords. Contains equipment, materials, consumables and other items. Numeric column semantics remain partly unknown. |
| Further item records | **6801–6809**; `_unnamed/06801_bb5151f8894d.scr` | 2,735 × 20 | Same cardinality as item names; numeric fields and pointers. Candidate extended item metadata; not fully mapped. |
| Item descriptions | **6810–6818**; English 6814; UK-style **6818**: `_unnamed/06818_312b14f0d418.scr` | 2,735 × 4 | UTF-16 description pointers in the same item order as names. |
| Alchemy recipes | **8388**: `_unnamed/08388_437acdc24504.scr` | 171 × 68 | First output is item 1638 (HP Potion); ingredient IDs include 1485 (Healweed), 1477 (Spring Water). |
| Blacksmith recipes | **8389**: `_unnamed/08389_aab31abd132b.scr` | 341 × 68 | Bronze Ingot from Castele Copper, then Iron Ingot from Plains Iron. |
| Carpentry recipes | **8390**: `_unnamed/08390_67405d214ac5.scr` | 229 × 68 | Oak Beam from Oak Log, then Pine Beam from Pine Log. |
| Cooking recipes | **8391**: `_unnamed/08391_e90fe7221281.scr` | 186 × 68 | Carrot Soup / Apple Juice outputs, matching vegetable/fruit ingredients. |
| Tailoring recipes | **8392**: `_unnamed/08392_d9cdae20cae0.scr` | 371 × 68 | Dandelion Cotton from Dandelion Puff; then Woven Straw Fabric. |
| Side-quest definitions | **8715**: `_unnamed/08715_7d96dfc3b2d3.scr` | 400 × 52 | Numeric request/reward/condition records; first u32 values also resemble dialogue-resource IDs. Matching 400-row quest text below corroborates purpose; not every column is named. |
| Side-quest titles/descriptions | **32662–32670**; English 32666, UK-style **32670**: `_unnamed/32670_576e979b9179.scr` | 400 × 8 | Two UTF-16 pointers per row, beginning with the Big Egg request. |
| Life challenge parameters/titles | Base **5810**, title variants **5820–5827**; English title 5823, UK-style **5827** | 1,522 × 24 | Fishing, crafting and combat challenge records/titles. |
| Life challenge descriptions | **5811–5819**; English 5815, UK-style **5819**: `_unnamed/05819_0efafb2a4522.scr` | 1,522 × 20 | Challenge objectives and explanatory text. Separate from the 24-byte title/parameter family. |
| Story/event progression | **5419–5427**; `_unnamed/05419_68330e7ef321.scr` | 174 × 204 | Event/progression metadata and debug labels such as `Event_000`; associated localized story text occurs around 6013–6021. |

The title/parameter family uses **base 5810 plus localized 5820–5827**;
5811–5819 is the separate description family. Check row cardinality/schema
alongside ID ranges when following these interleaved language families.

For the recipe records, u16 values at row offset **`0x1c`** match output item
indices, and **`0x2c`, `0x2e`, `0x30`** match ingredient slots where populated.
The item-name table at ID 6800 resolves these values directly. Quality-output
slots, counts, unlock/rank fields, workbench parameters and sentinels still need
full column mapping before an editor can safely add recipes. The five tables
contain **1,298 recipe records**, including quality/unlock variants rather than
1,298 necessarily distinct crafts.

Main dialogue is distributed through many unnamed SCR resources, especially
IDs **~21100–32670**. For a concrete UK-style English side-quest conversation,
ID **29232**, `_unnamed/29232_dee329a0a4b8.scr`, is a two-section wrapper whose
first table has 1 row × 28 bytes and dialogue about delivering Castele Apples.
ID 29228 is the corresponding other English variant. This proves dialogue
localization lives in SCR pools, not merely inferred filenames or the small MSG.
Other NPC, story, challenge, tutorial and UI text tables also occur earlier.

The common standalone SCR starts with `13 80 03 1d`. A u32 at `0x14` locates a
12-byte table descriptor `<u32 row-count, u32 row-width, u32 rows-offset>`.
Offsets are relative to that SCR section. Strings are UTF-16LE with NUL endings
and embedded `ffff` control sequences; naive NUL-string replacement is not a
complete dialogue editor. The common `02 00 00 00` wrapper has a 16-byte header
`<u32 section-count=2, u32 first-offset=16, u32 second-offset, u32 EOF>`;
embedded sections have their own relative offsets. The catalog records both
sections separately. Some second sections are not ordinary row tables.

Repeated language families include Japanese, two English variants, German,
Italian and repeated Spanish/French variants. RainThunder's helper labels its
nine slots `jp, ae, af, de, en, es, fr, it, uk`; the textual contents support
English/UK-style identifications used here. A complete runtime language-selection
map has not been recovered, so an eventual DLC editor should retain every slot.

## Verification and limits

- **14 synthetic tests passed**: all three LZ11 length forms and overlap, LZ10,
  RLE, Huffman4/8 word/nibble order, random/repetitive encoder round trips,
  Level-5 raw/zlib/LZ10 envelopes, malformed streams, actual parent/virtual ID
  relationships, opaque-padding identity, resized standalone and virtual members,
  deeper BPAK edits, `.lz` sidecar edits, basic ARC0/XFSA/XPCK reading, conflicting
  parent/leaf edits, traversal/symlinks, bounds and nonempty-output refusal.
- All five existing Phase 0 tests still passed.
- Full dump extraction decoded every **38,204 physical resource** and validated
  every **19,891 virtual member size** using the authoritative relationship index.
  The catalog rehashed all **75,937** payload files against their manifest hashes.
- Unchanged build plus `cmp`: **byte-identical**, with the archive SHA-256 above.
  This validates real repack preservation, including source compression/padding;
  the synthetic resized tests separately exercise actual container reconstruction.
- A full-dump edited test changed the first item name in ID **6800** without
  changing its length and grew virtual member **58091** by four bytes. Build
  correctly reconstructed physical parent **58094** and updated the virtual
  row. Only physical streams 6800 and 58094 changed; all other physical stored
  streams were compared byte for byte, and every member of 58094 was compared
  against its intended content. The source extraction was restored afterward.
  Edited test archive: **372,881,920** bytes, SHA-256
  `7d95ea0bc4ec4313a2530e105cc31cae33c53efcb0fe11ea97026724128e271f`.
- The implementation intentionally retains unknown application data and reserved
  fields. It does not decompile script opcodes, decode all table columns, import
  models into a PC runtime, or prove that arbitrary edited resources are accepted
  by the game. Those are later phases, independent of archive round-trip success.

## Primary references and prior art

Sources were cloned into ignored `third_party/` and read as format evidence;
no upstream build scripts were run. This implementation has no dependency on them.

- [3ds-xfsatool Fantasy Life reader](https://github.com/mhvuze/3ds-xfsatool/blob/d0df7405bf8081bbab08385ab0ea7b003f0d2139/3ds-xfsatool/fantasylife.cpp),
  commit `d0df7405bf8081bbab08385ab0ea7b003f0d2139`: establishes the outer arrays
  and LZ11 dispatch. Its virtual-member limitation is addressed above.
- [RainThunder archive reader](https://github.com/RainThunder/fantasylife_tools/blob/6bbc648e0229c93cbc4be76915321d16c14c4e51/arc.py)
  and [SCR reader](https://github.com/RainThunder/fantasylife_tools/blob/6bbc648e0229c93cbc4be76915321d16c14c4e51/scr.py),
  commit `6bbc648e0229c93cbc4be76915321d16c14c4e51`;
  [File formats wiki](https://github.com/RainThunder/fantasylife_tools/wiki/File-formats),
  wiki checkout `c83a79e21b4c24aef98e66576db8c4c5dba7c297`.
  The wiki's `_file_archive.bin` and SCR sections are empty; its named-pack table
  leaves fields unknown. Path-component offsets and the entry-1 relationship
  index in this document are additional findings from the user's dump.
- [Ohana3DS ZMDL importer](https://github.com/gdkchan/Ohana3DS-Rebirth/blob/c50635e82763fad9d1bcc30a905523a1b92d7d1f/Ohana3DS%20Rebirth/Ohana/Models/ZMDL.cs)
  and [ZTEX importer](https://github.com/gdkchan/Ohana3DS-Rebirth/blob/c50635e82763fad9d1bcc30a905523a1b92d7d1f/Ohana3DS%20Rebirth/Ohana/Textures/ZTEX.cs).
- [Kuriimu2 Ztex load/save implementation](https://github.com/FanTranslatorsInternational/Kuriimu2/blob/6babcdc3562975f445f258f0b7f1d9bd8e5e2a83/plugins/Level5/plugin_level5/N3DS/Image/Ztex.cs)
  and [Level-5 codec enum](https://github.com/FanTranslatorsInternational/Kuriimu2/blob/6babcdc3562975f445f258f0b7f1d9bd8e5e2a83/plugins/Level5/plugin_level5/Common/Compression/Level5CompressionMethod.cs).
- [SPICA](https://github.com/gdkchan/SPICA) and
  [Every File Explorer](https://github.com/Gericom/EveryFileExplorer) are additional
  NintendoWare inspection candidates; no compatibility beyond their documented
  format families is asserted for Fantasy Life's custom binaries.
