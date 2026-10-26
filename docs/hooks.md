# Universal function hooks and native code mods

> **Note:** paths starting with `port/` (and `runtime/`) refer to the runtime's source code, which is not part of this package. They are kept as historical research context.

Stable reference for `runtime/src/hooks.{h,cpp}`, `runtime/include/fl_mod_api.h` and
`runtime/src/fl_mod_host.cpp`. The registry is game-agnostic; Fantasy Life's camera,
co-op, extended item/recipe tables and script-native support register themselves through
it. No generated C or guest code is patched (the item module only rewrites nine
literal-pool count words in guest memory at runtime).

## Hook registry

```cpp
#include "hooks.h"

uint64_t before  = hooks::add_before(addr, fn, user);
uint64_t after   = hooks::add_after(addr, fn, user);
uint64_t replace = hooks::add_replace(addr, fn, user);
hooks::remove(before);
```

`addr` is the recompiled guest function address; the ARM/Thumb bit is ignored. A
`before` hook can change `ctx->r[0..3]` / `ctx->s[0..15]` (and any other `Ctx` field)
before the original runs. `after` hooks run when the call is complete. A replacement
gets the original `RecompFn` and returns non-zero when it handled the call:

```cpp
int detour(Ctx *ctx, uint32_t addr, RecompFn original, void *) {
    ctx->r[0] = 0;
    if (want_original) original(ctx); // bypasses this detour once
    return 1;
}
```

If a replacement returns 0, the registry restores the `Ctx` it saw and falls through
to the next replacement/original. After hooks run after a replacement too. Hooks are
copy-on-write; registration is safe while guest threads run.

### Indirect calls

`kernel::recomp_call_indirect()` asks `hooks::dispatch(ctx, target, original)` first.
The registry runs the hooks and, unless a replacement took over, calls the original
itself. No per-game `if (camera::dispatch(...))` / `if (coop::dispatch(...))` remains in
`kernel.cpp`.

### Direct calls and the fast path

Generated functions start with:

```c
void fn_00123450(Ctx *ctx) {
    RECOMP_ENTER(ctx, 0x00123450u);
    ...
}
```

`RECOMP_ENTER` reads one byte from `recomp_hook_page_map` (one byte per 4 KiB guest
page). A page with no hooks costs a predicted pointer load, one byte load and a branch.
If a page has hooks, `recomp_hook_enter()` does the exact lookup. When a hooked direct
function has after/replace hooks, the registry calls the original through the host's
resolver and runs after hooks; the generated body is skipped. A before-only hook lets
the body run normally. The original call is protected by a one-shot bypass, so recursive
calls inside the body still see hooks.

`recomp_hook_page_map` is a pointer because a packaged build compiles generated C into
a separate game module. The module gets the host's page map and `recomp_hook_enter`
through `ClockworkHost` (`recomp_module.h`, version 2). The linked-game executables set
the same pointer in `hooks.cpp`. An old cached module is rejected and rebuilt because
the module version changed.

### Data-table hooks (Fantasy Life items)

`items::activate_digest()` registers a before hook on the item-table getter and replace
hooks on the category-stat lookup, save-bit index helper, inventory mutation and the two
recipe bit functions. Replacements that handle a call never touch the fixed save bit
sets; `items.md` records the exact addresses, sidecar format and limits.

### Level-5 Script VM native opcodes

```cpp
uint64_t id = hooks::add_script_native(453, handler, user);
// handler(Ctx*, uint32_t opcode, RecompFn original, void*) -> non-zero if handled
```

For Fantasy Life, `coop::activate_digest()` installs a VM locator. It reads the
executing instruction at thread+0x2c, requires opcode 7 (`native`), and verifies the
indirect target against the 700-slot member-function table at manager+4. Only then does
the registry dispatch the opcode handler, so helper calls made by a native are not
mistaken for the native itself. Other games can install their own locator with
`hooks::set_script_native_locator()`.

## Native code mods

The public ABI is `runtime/include/fl_mod_api.h`, version `FL_MOD_API_VERSION` (1) and
entry symbol `fl_mod_entry_v1`. It exposes:

| Field | Meaning |
| --- | --- |
| `recomp_mem`, `rd8/16/32`, `wr8/16/32`, `is_committed` | guest memory |
| `call_guest` | calls a guest function with r0-r3, returns r0 (0 before `on_init`) |
| `hook_before/after/replace`, `hook_remove` | the registry above |
| `script_native` | a Level-5 VM opcode handler |
| `on_init`, `on_frame` | lifecycle callbacks |
| `register_compatibility_tag` | adds a named value to the LAN compatibility digest |
| `log_info`, `log_error` | runtime stderr log |

A plugin is a shared library inside an enabled mod folder:

- Windows: `mod.dll` (also `mod-<arch>-windows.dll`, `mod-windows.dll`, `mod-<arch>.dll`)
- Linux: `mod.so` (the same arch/OS variants)
- macOS: `mod.dylib`

Loading is opt-in: `FL_NATIVE_MODS=1` (or `true`/`yes`/`on`). Without it the runtime
does not load any native code. `mods::apply()` loads plugins after resource overlays and
after guest memory is reserved; `mods::start()` runs `on_init` after the game code/module
and kernel are ready; `perf::frame()` calls `mods::frame()` when the top screen hands over
a completed frame. `on_frame` can run on the VBlank timer thread, so do not call guest
functions from it; use a hook or `on_init` for `call_guest`.

The plugin file's bytes are hashed into the multiplayer compatibility digest before
loading. `register_compatibility_tag(name, data, size)` adds another value under
`native-mod/<name>`; peers with different plugins, settings or hashes are rejected by
the normal LAN handshake. Register the tag during entry (before `air_start`).

### Minimal plugin

```cpp
#include "fl_mod_api.h"

static const FLModAPI_v1 *api;

static void before(Ctx *ctx, uint32_t, void *) {
    api->wr32(0x00300000, api->rd32(0x00300000) + 1);
}

extern "C" FL_MOD_EXPORT int fl_mod_entry_v1(const FLModAPI_v1 *table) {
    if (!table || table->version != FL_MOD_API_VERSION ||
        table->size < sizeof(FLModAPI_v1)) return 1;
    api = table;
    if (!api->hook_before(0x00123450, before, nullptr)) return 2;
    api->register_compatibility_tag("example", "v1", 2);
    return 0;
}
```

## Text script mods (Lua 5.4)

Text mods use the same hooks and guest-memory access as native plugins but run from a
sandboxed Lua 5.4.7 interpreter. They need no compiler, no native plugin and no
`FL_NATIVE_MODS` opt-in. The runtime is `runtime/src/script_mod.{h,cpp}` with the Lua
implementation compiled once from `runtime/third_party/minilua/minilua.h` (MIT).

### Discovery and load order

An active mod folder may contain `script.lua`, `scripts/*.lua`, or both. Scripts run
once when the game starts, after resource overlays and guest-memory setup, in this
order:

1. `FL_MOD_DIRS` folders in the listed order, else `FL_MOD_DIR` (empty disables), else
   the enabled `<data>/mods/fantasylife/<mod>/` folders in folder-name order. Folders
   with a `disabled` marker are skipped. Script-only folders are accepted; the resource
   overlay loader logs them and ignores their missing `overlay.json`.
2. `script.lua` first, then `scripts/*.lua` sorted by filename.

Each file gets its own Lua state and its own copy of the environment; scripts cannot
see each other's globals. The load log names the file as `<mod>/<script>`.

### Hot reload

Press **Ctrl+R** (Cmd+R on macOS) in game, or call `mods::reload_scripts()` /
`fl_mod_host::reload_scripts()` / `script_mod::reload_all()`. The runtime removes every
hook and frame callback registered by scripts, re-reads the files from disk and runs
them again without restarting the game. Native plugins stay loaded. A reload requested
from inside a Lua callback is deferred to the next frame rather than closing the state
under the running callback.

### The `fl` table

```lua
fl.log("loaded", 1)              -- runtime log, prefixed [FL Script Mod <name>]
fl.warn("careful")

local value = fl.read_u32(0x00300000)       -- nil when the address is not mapped
fl.write_u32(0x00300000, value + 1)         -- false when the address is not mapped
fl.read_u8(addr) / fl.write_u8(addr, v)
fl.read_u16(addr) / fl.write_u16(addr, v)
fl.read_u32(addr) / fl.write_u32(addr, v)
fl.read_f32(addr) / fl.write_f32(addr, v)
local bytes = fl.read_bytes(addr, len)      -- nil when the range is not fully mapped

local before = fl.hook_before(0x00123450, function(ctx)
  ctx:set_r(0, ctx:r(0) + 1)
  fl.log("sp", ctx:sp(), "lr", ctx:lr())
end)

local after = fl.hook_after(0x00123450, function(ctx)
  fl.log("result", ctx:r(0))
end)

local replace = fl.hook_replace(0x00123450, function(ctx, call_original)
  ctx:set_r(1, 7)
  call_original()            -- runs the original recompiled function once
  -- return false to decline; returning nothing (or true) means handled
end)

fl.unhook(before)            -- true once; false if it was already removed

fl.on_frame(function(frame_index)   -- starts at 1
  fl.log("frame", frame_index)
end)

local result = fl.call_guest(0x00123450, {r0 = 1, r1 = 2, sp = 0x003ff000})
```

All addresses are guest addresses; the ARM/Thumb bit is ignored by the hook registry.
Reads return `nil` and writes return `false` when the range is not committed. Reads
and writes use the host's `is_committed`/`rd*`/`wr*` accessors, so an unmapped address
never dereferences guest memory. `read_bytes` is capped at 16 MiB.

`ctx` methods: `ctx:r(i)` and `ctx:set_r(i, v)` for `r0..r15` (values are unsigned
32-bit), `ctx:sp()` for `r13` and `ctx:lr()` for `r14`. The context and the
`call_original` function are valid only for the duration of their callback; keeping
them and using them later raises a Lua error instead of touching freed guest state.

`fl.hook_replace` follows the native replacement contract: return `false` to decline
(the registry restores the context and runs the original), or return nothing/`true` to
take the call. Calling `call_original()` marks the call handled even if the Lua function
later returns `false`, so the original never runs twice. If `call_original()` is
unavailable (the host could not resolve the address), calling it raises an error.

`fl.on_frame` callbacks run when the top screen hands over a completed frame, possibly
on the VBlank timer thread. Do not call guest code (`fl.call_guest`) from them; the
runtime rejects it and logs an error. Use a before/after hook or `on_init`-time work
for guest calls. Frame callbacks are serialized with hook callbacks; a slow callback
delays the others.

`fl.call_guest(addr, ctx_table)` sets `r0..r3` from the table (optional `sp`/`lr`
aliases for `r13`/`r14`), calls the guest function through `FLModAPI_v1::call_guest`,
returns its `r0`, and writes the resulting `r0..r15`, `sp` and `lr` back into the
table. It returns 0 before the game is ready. `addr` must name a recompiled guest
function; an unknown target follows the host's normal indirect-call error path. Calling
it from `on_frame` or while a script is loading is rejected (logs an error and returns
`nil`) because neither runs on the guest thread.

### Sandbox and errors

Each state opens only the pure Lua libraries: base, `table`, `string`, `math`, `utf8`
and `coroutine`. `io`, `os`, `package`, `debug`, `dofile`, `loadfile` and `require` are
not present, so scripts cannot execute processes, load native libraries or read/write
the filesystem. `print` and `warn` are routed to `fl.log`/`fl.warn`. Scripts run with
Lua's normal memory allocator; a pathological allocation can still exhaust host memory.
There is no instruction budget: an infinite loop in a callback stalls the game, and
callbacks are serialized, so wait for that hook to return before reloading.

Every chunk and callback runs under `lua_pcall`. A syntax/load error skips only that
file; a runtime error logs

```
[FL Script Mod <mod>/<file>] error: <message>
```

and unregisters only the failing hook or frame callback. The original guest function
still runs for a failing `before`/`after` hook; a failing `replace` hook falls back to
the original unless it had already called `call_original()`. The rest of the game and
the other scripts keep running.

### Tests

`test-fl-script-mod` (CTest `fl-script-mod`, host-only) loads a scratch mod folder and
covers safe memory access, `hook_before`, `hook_after`, `hook_replace` with
`call_original()`, declining replacements, `unhook`, `on_frame`, `call_guest`, sandbox
removal, syntax/runtime error recovery, and live `reload_all()` changing a hook after
editing `script.lua` on disk. It never boots a guest, opens a window or creates a GPU.

## Tests

`test-fl-hooks` (CTest `fl-hooks`, host-only) covers direct and indirect before/after/
replace hooks, replacements calling the original, the one-shot bypass, script-native
opcode dispatch, and the plugin API loaded from a real `fl-test-mod-plugin.dll`:
memory access, `call_guest`, `on_init`, `on_frame`, hook registration and logging.
`test-fl-camera` and `test-fl-coop` exercise the refactored game features. None of these
start a game, window or GPU.
