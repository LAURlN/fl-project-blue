// SPDX-License-Identifier: MIT
// Copyright (c) 2026 fl-project-blue contributors
#pragma once
// Native code-mod plugin API, version 1.
//
// A plugin is a shared library (mod.dll / mod.so / mod.dylib) inside an enabled mod folder. The
// runtime loads it only when the user opts in with FL_NATIVE_MODS=1. The plugin exports
//
//     FL_MOD_EXPORT int fl_mod_entry_v1(const FLModAPI_v1 *api);
//
// and returns 0 on success. The table is valid for the process lifetime. Register hooks and
// lifecycle callbacks during the entry call; on_init callbacks run after the game's code and guest
// memory are ready, and on_frame callbacks run when the top screen hands over a completed frame
// (perf::frame). on_frame can run on the VBlank timer thread, so do not call guest functions from
// it; use a hook or on_init for call_guest.
//
// The API is deliberately C-only and versioned by both `version` and `size`, so a plugin built
// against a future table can reject an older host instead of reading past the end.
#include <stddef.h>
#include <stdint.h>

#include "recomp.h"

#define FL_MOD_API_VERSION 1u
#define FL_MOD_ENTRY_NAME "fl_mod_entry_v1"

#if defined(_WIN32)
#define FL_MOD_EXPORT __declspec(dllexport)
#else
#define FL_MOD_EXPORT __attribute__((visibility("default")))
#endif

typedef struct FLModAPI_v1 FLModAPI_v1;

typedef void (*FLModBeforeFn)(Ctx *ctx, uint32_t addr, void *user);
typedef void (*FLModAfterFn)(Ctx *ctx, uint32_t addr, void *user);
// Return non-zero if the replacement handled the call. `original` is the recompiled function;
// calling it bypasses this hook once, so a replacement can wrap the original without recursing.
typedef int (*FLModReplaceFn)(Ctx *ctx, uint32_t addr, RecompFn original, void *user);
// Level-5 Script VM native opcode handler: return non-zero to replace the game's native handler.
typedef int (*FLModScriptNativeFn)(Ctx *ctx, uint32_t opcode, RecompFn original, void *user);
typedef void (*FLModInitFn)(void *user);
typedef void (*FLModFrameFn)(uint64_t frame, void *user);

struct FLModAPI_v1 {
    // Must be checked by the plugin before using anything after these two fields.
    uint32_t size;    // sizeof(FLModAPI_v1) as provided by the host
    uint32_t version; // FL_MOD_API_VERSION

    // Guest memory (recomp_mem is the 4 GiB reserved block). Reads/writes do not bounds-check;
    // call is_committed first for memory that may not be mapped.
    uint8_t *recomp_mem;
    uint32_t (*rd8)(uint32_t addr);
    uint32_t (*rd16)(uint32_t addr);
    uint32_t (*rd32)(uint32_t addr);
    void (*wr8)(uint32_t addr, uint32_t value);
    void (*wr16)(uint32_t addr, uint32_t value);
    void (*wr32)(uint32_t addr, uint32_t value);
    int (*is_committed)(uint32_t addr);

    // Call a guest function like generated code does: r0-r3 are set, the result is returned in r0.
    // `ctx` is updated in place. Returns 0 before on_init (the game is not ready). Call this from
    // a hook or on_init; on_frame can be the VBlank timer thread, so do not call guest code there.
    uint32_t (*call_guest)(Ctx *ctx, uint32_t addr, uint32_t r0, uint32_t r1, uint32_t r2, uint32_t r3);

    // Hook a recompiled function by guest address. Returns an id > 0, or 0 on failure. The
    // ARM/Thumb bit is ignored. The lifetime is the process (hook_remove can release it early).
    uint64_t (*hook_before)(uint32_t addr, FLModBeforeFn fn, void *user);
    uint64_t (*hook_after)(uint32_t addr, FLModAfterFn fn, void *user);
    uint64_t (*hook_replace)(uint32_t addr, FLModReplaceFn fn, void *user);
    int (*hook_remove)(uint64_t id);

    // Replace a Level-5 Script VM native opcode (0..699 in the shipped VM). The host exposes the
    // VM's current opcode when the game provides a locator; otherwise the handler is dormant.
    uint64_t (*script_native)(uint32_t opcode, FLModScriptNativeFn fn, void *user);

    // Lifecycle. Register during entry; on_init runs once the game is loaded, on_frame when the
    // top screen hands over a completed frame (possibly on the VBlank timer thread). Returns 1 on
    // success.
    int (*on_init)(FLModInitFn fn, void *user);
    int (*on_frame)(FLModFrameFn fn, void *user);

    // Add a value to the multiplayer compatibility fingerprint. Peers must register the same
    // name and bytes to share a session. Keep this stable across versions of your mod.
    void (*register_compatibility_tag)(const char *name, const void *data, size_t size);

    // Logging goes to the runtime's stderr log (and the launcher's log view). log_error does not
    // abort the process; return failure from the entry call for fatal setup errors.
    void (*log_info)(const char *fmt, ...);
    void (*log_error)(const char *fmt, ...);
};

typedef int (*FLModEntryFn)(const FLModAPI_v1 *api);

#ifdef __cplusplus
extern "C" {
#endif
// Convenience typedef for plugins; the host looks the symbol up by FL_MOD_ENTRY_NAME.
typedef FLModEntryFn (*FLModGetEntryFn)(void);
#ifdef __cplusplus
}
#endif
