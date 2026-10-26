# Fantasy Life PC - Modding Workspace

This package is the normal game release **plus** everything needed to make mods for it.
It contains **no game data**: you supply your own legally dumped EU `.3ds` (and optional DLC `.cia`)
in the `game/` folder (see README.txt). Playing works exactly as described in `README.txt`.

## What is in the box

| Path | Purpose |
|---|---|
| `tools/phase0_extract.py`, `inspect_cia.py`, `fl_3ds.py` | Read a decrypted ROM / CIA read-only and extract ExeFS + RomFS. |
| `tools/fl_archive.py`, `fl_archive_catalog.py` | List, extract and rebuild `_file_archive.bin`. |
| `tools/fl_scr.py`, `fl_data.py`, `fl_map.py`, `fl_script.py` | Data tables (`.scr`), maps/enemies, event-script disassembler/assembler. |
| `tools/fl_ztex.py`, `fl_zmdl.py` | Textures and models: decode to PNG/OBJ/glTF, rebuild from art. |
| `tools/fl_mod.py`, `fl_mod_content.py` | **Mod builder**: `mod.json` source -> resource overlay; `build-stack` / `check-stack`. |
| `tools/schemas/` | Column schemas for the game's data tables. |
| `tools/re/` | Reverse engineering: `symbols_fl_eu.txt` (function names/addresses), `script_commands.json`, Ghidra headless scripts (`ghidra.sh`, `ImportFl.java`, `QueryFl.java`), RTTI/IPC/flag scanners. |
| `tools/fl-recomp/` | Clean-room ARM11 -> C translator (Rust, `cargo build --release`). Needs the unpublished runtime's `Ctx` contract to produce a playable build; useful as an analysis/decoding tool (`fl-recomp decode <hex>`). |
| `tools/tests/` | Unit tests (`python -m unittest discover -s tools -p "test_*.py"`). |
| `modding/native/include/` | `fl_mod_api.h` + `recomp.h`: C headers for native plugins (`mod.dll`). |
| `docs/` | Format documentation and the full modding guide (start with `docs/modding-guide.md`). |
| `mods/` | Source projects of the shipped mods (`mod.json` + original art), as reference. |

## Quick start

Requirements: Python 3.10+ (standard library only). Rust, Ghidra and a C compiler are optional.

1. **Extract once** (put your decrypted EU `.3ds` in `game/` or anywhere you like):
   ```
   python -I tools/phase0_extract.py <your.3ds> --output extracted/fl_eu
   python -I tools/fl_archive.py extract extracted/fl_eu/romfs/_file_archive.bin extracted/fl_eu/archive
   ```
   Everything under `extracted/` is derived game data: never share or publish it.
2. **Pick a mod type**
   - **Data / art mod** (items, recipes, shops, enemies, maps, textures, models, scripts):
     write `mods/<name>/mod.json`, then
     ```
     python -I tools/fl_mod.py build extracted/fl_eu/archive mods/<name> data/yw2-recomp/mods/fantasylife/<name> --replace
     ```
     Use `mods/wooden-sword` as the reference. Details: `docs/modding-guide.md`.
   - **Lua script mod** (no compiler, hot reload with Ctrl+R): put `script.lua` or `scripts/*.lua` in a folder
     under `data/yw2-recomp/mods/fantasylife/<name>/`. API: `docs/hooks.md`.
   - **Native plugin** (advanced): `mod.dll` built against `modding/native/include/`, loaded only when
     `FL_NATIVE_MODS=1`. API: `docs/hooks.md`.
3. **Test** by playing with the launcher's mod chips; use a copy of your save profile.
4. **Package** (see below).

## Publishing to GameBanana

- The launcher installs from GameBanana (game ID 22668) and imports `.zip` files containing an overlay
  folder (`overlay.json` + `resources/`), `script.lua`/`scripts/`, `mod.dll` (the launcher also accepts `plugin.dll`/`plugins/*.dll`), or a multi-mod pack with
  `modpack.json` (`{"format":"fl-modpack-v1","name":"...","mods":["a","b"]}`).
- A built overlay contains **derived game data**. Prefer publishing your **source project**
  (`mod.json` + your own art/scripts, no game bytes): players with the build tools can add it as a source
  mod. Only publish built overlays if you are comfortable with that.
- Never include `extracted/`, ROMs, `.cia` files or game resources in a zip.
- State required base: EU v00, and note conflicts: two mods replacing the same resource block Play.

## Legal

You need your own legal copy of the game. This package ships no Nintendo or Level-5 assets, and the tools
never decrypt anything. Fan project, not affiliated with Level-5 or Nintendo.


