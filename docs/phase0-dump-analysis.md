# Fantasy Life EU — Phase 0 cartridge dump analysis

## Result and scope

**The NCCH partitions are already decrypted.** All three populated partitions have
`flags[7] = 0x04` (`NoCrypto` set) and `flags[3] = 0x00` (crypto-method selector).
Readable structures and matching NCCH/ExeFS SHA-256 hashes corroborate the flags;
the selector alone would not establish that content was decrypted.

Only unpacking and static inspection were performed. No game code was executed,
no recompiler work was started, and no AES keys or bootroms were obtained or used.
The separate DLC CIA in `dumps/` was outside this task and was not processed.

- Input: `dumps/0004000000113100_v00.trim.3ds`, opened read-only.
- Size: **930,279,424 bytes** (`0x3772f000`); nominal NCSD medium: 1,073,741,824 bytes (1 GiB).
- Input SHA-256: `f9cf07eb836b78fca95182f72685edfc6dbaa6a8c1eae591fddb2b7439c5cba0`.
- Title/program ID: `0004000000113100`; game product code: **CTR-P-AFLP**.
- Extracted files and full structured report: `extracted/fl_eu/`, including `info.txt` and `analysis.json`.
- Reproducible implementation: [`tools/phase0_extract.py`](../tools/phase0_extract.py);
  usage and validation boundaries: [`tools/README.md`](../tools/README.md).
- `dumps/` and `extracted/` remain ignored; extracted game data is not committed.

## NCSD and NCCH layout

Offsets below are absolute within the dump unless explicitly labeled relative.
The NCSD and all three NCCH media units are `0x200` bytes. NCSD media ID is
`0004000000113100`; flags are `00 01 00 02 01 01 00 00`. All eight NCSD filesystem
and crypto-type table bytes are zero; the NCCH flags determine encryption status.

| Index | Content | Offset | Size | Partition ID | Product code | NCCH flags [0..7] |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | Game executable/RomFS | `0x00004000` | `0x351d2000` | `0004000000113100` | `CTR-P-AFLP` | `00 00 00 00 01 03 00 04` |
| 1 | Electronic manual | `0x351d6000` | `0x006a7000` | `0005000000113100` | `CTR-P-CTAP` | `00 00 00 00 01 09 00 04` |
| 7 | Old 3DS system update | `0x3587d000` | `0x01eb2000` | `2010000000113100` | `CTR-P-CTAP` | `00 00 00 00 01 05 00 04` |

Indices 2–6 are empty: **no download-play partition and no New 3DS update
partition**. All populated NCCHs have program ID `0004000000113100`; their declared
content sizes equal their NCSD partition sizes. Game maker code is `HF`, NCCH
format version 2; the other two use maker `00`, version 0. The last partition ends
exactly at the trimmed dump's end.

| Partition | Section | NCCH-relative offset | Absolute offset | Size |
| --- | --- | --- | --- | --- |
| 0 | NCCH header | `0x00000000` | `0x00004000` | `0x200` |
| 0 | Exheader plus access descriptor | `0x00000200` | `0x00004200` | `0x800` |
| 0 | Logo | `0x00000a00` | `0x00004a00` | `0x2000` |
| 0 | Plain region | `0x00002a00` | `0x00006a00` | `0x200` |
| 0 | ExeFS | `0x00002c00` | `0x00006c00` | `0x3a9200` |
| 0 | RomFS | `0x003ac000` | `0x003b0000` | `0x34e26000` |
| 1 | RomFS | `0x00001000` | `0x351d7000` | `0x6a6000` |
| 7 | RomFS | `0x00001000` | `0x3587e000` | `0x1eb1000` |

Partitions 1 and 7 have no exheader, plain region, logo, or ExeFS. Their complete
RomFS trees are under `manual/romfs/` and `update_o3ds/romfs/`. Partition 7 contains
65 CIA files and a 2,048-byte `cup_list`; these are preserved as files, without
attempting to decrypt or unpack embedded CIA contents. The outer NCCH's NoCrypto
flag does not establish encryption status for those embedded containers.

## Main executable and exheader

Process name **FLLINK**; remaster version 0. System-control flag byte `0x01` enables
compressed `.code`; the SD-application flag is clear. The NCCH exheader size field
is `0x400` (the hashed SCI/ACI information). `exheader.bin` preserves the full
`0x800` bytes including the access descriptor; `exheader-info.bin` preserves just
the first `0x400`. `exheader.txt` parses the effective SCI/ACI capabilities, rather
than the signed access descriptor's permission ceiling.

| Segment | Virtual address | Actual size | Pages | Page allocation | Offset in decompressed code.bin |
| --- | --- | --- | --- | --- | --- |
| text | `0x00100000` | `0x0051cc68` (5,360,744) | `0x51d` | `0x51d000` | `0x000000` |
| rodata | `0x0061d000` | `0x000862e8` (549,608) | `0x87` | `0x087000` | `0x51d000` |
| data | `0x006a4000` | `0x000371b4` (225,716) | `0x38` | `0x038000` | `0x5a4000` |

- BSS: `0x000cca88` = **838,280 bytes**; stack: `0x00040000` = **262,144 bytes**.
- Core version: `0x00000002` (firmware/core title selector, not an SDK version).
- SDK plain-region marker: **CTR SDK 5.2.1.200**, suffix `none`.
- Plain-region firmware marker: **02.36.00**; ARM11 release-kernel descriptor:
  **2.35** (`0xfc000223`). These are distinct recorded fields.
- Old 3DS system mode **0 / production**, 64 MiB application-memory mode.
- New 3DS mode **0 / legacy**; no L2-cache or 804 MHz request; core flags
  `00 00 04 30`. Ideal processor 0, affinity mask 1, main-thread priority 48.
- Resource-limit category 0 (application); descriptors `[0x009e, 0, …, 0]`
  (16 entries total; first descriptor retained raw, not interpreted as a percentage).
- Declared ordinary save-data size: **0 bytes**; jump ID `0004000000113100`.
- Extdata ID: **`0x0000000000001131`**. System save-data IDs are both zero;
  accessible-save raw field `0x1000000000000000` sets the other-variation flag.
  Storage attributes byte is zero; filesystem access bytes
  `80 00 00 00 00 00 00` permit direct SDMC access.
- ARM9 access bytes `00 02 00 00 00 00 00 00 00 00 00 00 00 00 00` grant SDMC
  read/write access; ARM9 descriptor version 2.

The zero ordinary save-data size is an exheader observation, not a claim that the
game never saves. Extdata is explicitly authorized, and executable paths include
`data:/fantasylife.fsd` and `ext:/fl_ext0.fsd`; actual save behavior was not traced.

### Service access control — all 30 populated entries, in header order

```text
APT:U       $hioFIO     $hostio0    $hostio1    ac:u
boss:U      cam:u       cecd:u      cfg:u       dlp:FKCL
dlp:SRVR    dsp::DSP    frd:u       fs:USER     gsp::Gpu
hid:USER    http:C      mic:u       ndm:u       news:u
nwm::UDS    ptm:u       pxi:dev     soc:U       ssl:C
y2r:u       ldr:ro      ir:USER     nim:aoc     am:app
```

The remaining service slots are empty. Permissions such as `ldr:ro` and the DLP
services do not prove that dynamic modules or download-play content are shipped.

### Dependency modules — all 30 nonzero title IDs, in header order

```text
0004013000002402  0004013000001502  0004013000003402
0004013000001602  0004013000002602  0004013000001702
0004013000001802  0004013000002702  0004013000002802
0004013000001a02  0004013000003202  0004013000001b02
0004013000001c02  0004013000001d02  0004013000002902
0004013000001e02  0004013000003302  0004013000001f02
0004013000002002  0004013000002b02  0004013000003502
0004013000002c02  0004013000002d02  0004013000002102
0004013000003102  0004013000002202  0004013000003702
0004013000002e02  0004013000002302  0004013000002f02
```

The other 18 dependency slots are zero. These are system-module dependencies,
separate from any game-provided CRO modules.

### ARM11 kernel capabilities

All 12 active raw descriptors, followed by 16 unused `0xffffffff` entries:

```text
f0fa9f4e f1ffbfff f2003fe7 ff81ff50 ff81ff58 ff81ff70
ff81ff78 ff91f000 ff91f600 ff000101 fe000200 fc000223
```

Allowed SVC numbers (51 total):

```text
01 02 03 06 08 09 0a 0b 0c 0f 11 13 14 15 16 17
18 19 1a 1b 1c 1d 1e 1f 20 21 22 23 24 25 27 28
29 2a 2b 2c 2d 2e 2f 30 31 32 35 36 37 38 39 3a
3b 3c 3d
```

Handle-table size **512** (`0x200`); release kernel **2.35**. No interrupt-list
descriptors. Address ranges use an exclusive end:

- Read/write I/O: `[0x1ff50000, 0x1ff58000)` and `[0x1ff70000, 0x1ff78000)`.
- Read-only static mapping: `[0x1f000000, 0x1f600000)`.
- Kernel flags `0xff000101`: application memory type 1 and **allow-debug** set.
  Force-debug, non-alphanumeric names, shared-page writing, privileged priority,
  main arguments, shared device memory, runnable-on-sleep, special memory layout,
  and core-2 access are clear. Allow-debug is a permission, not proof of a debug build.

### ExeFS contents

| Entry | Extracted path under extracted/fl_eu/ | Size |
| --- | --- | --- |
| `.code`, stored BLZ | `exefs/code.compressed.bin` | 3,476,532 (`0x350c34`) |
| `.code`, decompressed | `exefs/code.bin` | **6,144,000 (`0x5dc000`)** |
| `banner` | `exefs/banner.bin` | 346,448 (`0x54950`) |
| `icon` | `exefs/icon.bin` | 14,016 (`0x36c0`) |

The logo is a separate NCCH region, saved as `logo.bin` (8,192 bytes). No ExeFS
logo entry exists. Decompressed code length exactly equals the sum of all three
page allocations; BSS is not appended to it.

Decompressed SHA-256:
`a2e10e861c49220070b74d2b3c1d6f8cc7e253bfa837a4b7543f87e0166b35bb`.

## RomFS overview

The game's complete outer RomFS has **228 files**, totaling **880,288,301 bytes**.
It has five root files and directories `movie/`, `sound/`, and `sound/stream/`.
Directory totals include descendants:

| Location | Files | Bytes |
| --- | --- | --- |
| Root files | 5 | 372,906,756 |
| `movie/` | 6 | 61,780,164 |
| `sound/` | 217 | 445,601,381 |

All extension groups and their first-four-byte histograms:

| Extension | Files | First four bytes (hex) | Interpretation |
| --- | --- | --- | --- |
| `.bcstm` | 213 | `43 53 54 4d` | `CSTM` audio stream |
| `.moflex` | 6 | `4c 32 aa ab` | Mobiclip/Moflex video |
| `.shbin` | 2 | `44 56 4c 42` | `DVLB` shader binary |
| `.bcsar` | 2 | `43 53 41 52` | `CSAR` sound archive |
| `.csid` | 2 | `ef bb bf 2f` | UTF-8 BOM followed by `/`; text sound-ID definitions |
| `.icn` | 1 | `53 4d 44 48` | `SMDH` icon metadata |
| `.bcsdr` | 1 | `43 47 46 58` | `CGFX` graphics container |
| `.bin` | 1 | `ef e2 00 00` | `_file_archive.bin`; game-specific packed archive |

Each extension group here has exactly the listed prefix, so this is also the
complete game RomFS first-four-byte frequency histogram. These are observed
prefixes, not a claim that every prefix is a formal magic signature.

Notable files:

- **`_file_archive.bin`: 372,881,344 bytes**. Preserved intact. Its first word is
  `0x0000e2ef`; no internal archive structure or entry count was assumed.
- `DSR_Shader.shbin` (5,020), `nnfont_RectDrawerShader.shbin` (964),
  `shaders.bcsdr` (5,412), `fl_ex_save_banner.icn` (14,016).
- `movie/logo_l5.moflex` and `movie/mov000.moflex` through `mov004.moflex`.
- `sound/stream.bcsar`, `sound/stream_se.bcsar`, matching `.csid` files,
  and 213 `.bcstm` streams under `sound/stream/`.
- **Zero loose `*.fa`, `*.scr`, `*.xi`, or `*.cfg.bin` files**. Their existence
  inside the packed archive has not been established; outer RomFS extraction
  does not unpack game-specific archive members.

Other partition trees:

| Partition | Files | Total bytes | Extension histogram | First-four-byte histogram |
| --- | --- | --- | --- | --- |
| Manual | 1 | 6,902,600 | `.bcma`: 1 | `64 61 72 63` (`darc`): 1 |
| Old 3DS update | 66 | 31,916,416 | `.cia`: 65; no extension: 1 | `20 20 00 00`: 65; `00 20 02 00`: 1 |

The manual file is `Manual.bcma`; its internal DARC archive remains intact.
Every outer RomFS file's path, size, first four bytes, and SHA-256 is recorded in
the corresponding `romfs-manifest.json` and in the full `info.txt`.

## Quick static executable inspection

The scan found **9,096 ASCII strings of at least six printable characters**.
Full strings with byte offsets and mapped virtual addresses are in
`analysis/code-strings.tsv`; selected middleware/framework evidence is in
`analysis/code-evidence.tsv` and `analysis.json`. These are string/RTTI observations,
not a recovered linker map or function-symbol table.

Representative strings below use **offsets in decompressed `code.bin`**. For these
three contiguous segments, the corresponding virtual address is offset + `0x100000`.

| File offset | Evidence | Interpretation |
| --- | --- | --- |
| `0x15c064` | `2014/7/25 12:14 <mst>` | Embedded build-like timestamp, not independently authenticated |
| `0x154e5c` | `data:/fantasylife.fsd` | Runtime save path, not a developer source path |
| `0x028c28` | `nn::fs::Unmount()` | Nintendo SDK filesystem diagnostic |
| `0x160124` | `nn::applet::RestartApplication` | Nintendo SDK applet diagnostic |
| `0x3a891c` | `NEX_3_4_2` | NEX version marker |
| `0x5857cb` | `N2mw2mo8mobiclip7DecoderE` | Mobiclip decoder RTTI |
| `0x585f60` | `N2nn3nex10ZLibPluginE` | NEX zlib component RTTI |
| `0x58b5a1` | `N2nw3gfx13SkeletalModelE` | NintendoWare graphics RTTI |
| `0x58bcaf` | `N2nw3snd18SoundArchivePlayerE` | NintendoWare sound RTTI |
| `0x59df8e` | `Nw4cRoot` | NW4C-associated marker |
| `0x57e979` | `11cLibPackBin` | Game framework packed-resource class |
| `0x57fd2a` | `17cFwkScriptUtility` | Game framework scripting class |
| `0x5849cf` | `N2ds19ResourceDataManagerE` | Game framework resource-manager RTTI |

There are 119 ASCII strings containing `N2nw`, 629 containing `N2nn`, and 148
containing `N2ds`. Numerous `cFwk*`, `cLib*`, and `cApp*` type names survive.
Together with the RTTI above, this supports NintendoWare and a game-specific
framework using `ds`/`cFwk`/`cLib` names; it does **not** establish a branded Level-5
engine name. No convincing CRI/CRIWARE, ADX, or HCA marker was found in the quick
printable-string scan. No obvious developer `.cpp`/`.cxx` source paths were found;
runtime paths should not be mistaken for source paths. Absence of these strings
does not establish absence of the corresponding implementation.

The separate NCCH `plain.bin` provides stronger explicit version declarations:

```text
CTR_SDK-5_2_1_200_none
Firmware-02_36_00
NEX_3_4_2
NEX_MM_3_4_2
NEX_DS_3_4_2
PIA_3_1_0
Mobiclip: Deblocker_1_5_0, MobiclipDec_1_5_0, MoflexDemuxer_1_5_0,
          FastAudioDec_1_5_0, ImaAdpcmDec_1_5_0
OSS: zlib
```

**CRO/CRR:** no `.cro` or `.crr` filenames, `.crr` directory, or `CRO0`/`CRR0`
magic at offset `0x80` was found among the outer RomFS files in any partition.
A raw scan of `_file_archive.bin` also found zero `CRO0`/`CRR0` byte sequences.
This does not rule out compressed or otherwise encoded modules inside archives;
no game-specific archive unpacking was performed. `ldr:ro` is nevertheless present
in the service access list.

## Validation and format references

- Input SHA-256 was identical before and after extraction.
- All NCCH exheader/logo/ExeFS/RomFS region hashes and all three ExeFS file hashes
  matched the stored header hashes. Every extracted raw region and RomFS file was
  rehashed from disk and compared with its exact bytes in the source dump.
- BLZ decoding was independently cross-checked against Project_CTR's C `lzss.c`:
  all **6,144,000 output bytes matched**, including the SHA-256 reported above.
- Five synthetic regression tests passed: BLZ backreferences, invalid BLZ footer,
  filename traversal rejection, mixed decrypted/encrypted NCCH preflight with no
  output writes, and partition bounds against a trimmed input.
- RSA signatures, the full IVFC integrity tree, embedded CIA internals, and the
  game-specific packed archive's internals were not verified.

The extractor has no third-party runtime dependency. Header layouts and capability
encodings were checked against primary implementation sources:

- [libctru exheader definitions](https://github.com/devkitPro/libctru/blob/1f8d386e375ce734e11a3199eb51b8c98cc7e93a/libctru/include/3ds/exheader.h)
  and [RomFS definitions](https://github.com/devkitPro/libctru/blob/1f8d386e375ce734e11a3199eb51b8c98cc7e93a/libctru/include/3ds/romfs.h).
- [Project_CTR capability descriptors](https://github.com/3DSGuy/Project_CTR/blob/d52c2b0e788c2d085763d7c5dcc4b2edd9ffb7d8/ctrtool/deps/libnintendo-n3ds/include/ntd/n3ds/exheader.h)
  and [exheader interpretation](https://github.com/3DSGuy/Project_CTR/blob/d52c2b0e788c2d085763d7c5dcc4b2edd9ffb7d8/ctrtool/src/ExHeaderProcess.cpp).
- [Project_CTR BLZ decoder used for the independent comparison](https://github.com/3DSGuy/Project_CTR/blob/d52c2b0e788c2d085763d7c5dcc4b2edd9ffb7d8/ctrtool/src/lzss.c).
