// SPDX-License-Identifier: MIT
// Copyright (c) 2026 fl-project-blue contributors
//
// The ABI shared by generated game code and this runtime.
//
// Guest registers, flags and VFP state live in one Ctx value. Guest memory is a flat
// 4 GiB reservation reachable through recomp_mem, so a guest address is an ordinary
// byte offset. Everything here is C17 and compiles with clang or MSVC; no inline
// assembly, compiler intrinsics or non-standard extensions are used.

#ifndef RECOMP_H
#define RECOMP_H

#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if defined(_MSC_VER) || defined(__cplusplus)
#define RECOMP_RESTRICT __restrict
#else
#define RECOMP_RESTRICT restrict
#endif

/* Marks a generated function definition. Kept as a macro so a generator may give
   generated bodies translation-unit visibility without changing the call ABI. */
#ifndef RECOMP_FUNC
#define RECOMP_FUNC
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* The guest CPU state. The layout is part of the generated-code ABI and must not
   change: r0-r15, the four condition flags, Q/GE, s0-s31, FPSCR and the TLS word. */
typedef struct Ctx {
    uint32_t r[16];
    uint32_t n, z, c, v; /* condition flags, each stored as 0 or 1 */
    uint32_t q, ge;      /* sticky saturation flag; GE bits packed in `ge` */
    uint32_t s[32];      /* VFP single registers; d[n] is s[2n] (low) and s[2n+1] (high) */
    uint32_t fpscr;
    uint32_t tls;
} Ctx;

typedef void (*RecompFn)(Ctx *RECOMP_RESTRICT ctx);

/* Generated lookup table, sorted by guest address. */
typedef struct RecompEntry {
    uint32_t addr;
    RecompFn fn;
} RecompEntry;
extern const RecompEntry recomp_functions[];
extern const size_t recomp_function_count;

extern uint8_t *recomp_mem;

/* Runtime entry points called by generated code. */
void recomp_svc(Ctx *ctx, uint32_t imm, uint32_t addr);
void recomp_call_indirect(Ctx *ctx, uint32_t target);
void recomp_unhandled(Ctx *ctx, uint32_t addr, const char *what);
void recomp_coproc(Ctx *ctx, uint32_t addr, uint32_t raw);

/* One flag byte per 4 KiB guest page: non-zero when the page holds a hooked entry.
   This keeps the hot path to one load; the full registry lookup only runs on such
   pages. The pointer is exported so a separately loaded game module can share the
   host's table (see recomp_module.h). */
extern uint8_t *recomp_hook_page_map;
int recomp_hook_enter(Ctx *ctx, uint32_t addr);

#define RECOMP_HOOKED(addr) (recomp_hook_page_map[((addr) & ~1u) >> 12] != 0)

#ifdef RECOMP_TRACE_CALLS
void recomp_trace_enter(const Ctx *ctx, uint32_t addr);
#define RECOMP_ENTER(ctx, addr) do { \
    recomp_trace_enter((ctx), (addr)); \
    if (RECOMP_HOOKED(addr) && recomp_hook_enter((ctx), (addr))) return; \
} while (0)
#else
#define RECOMP_ENTER(ctx, addr) do { \
    if (RECOMP_HOOKED(addr) && recomp_hook_enter((ctx), (addr))) return; \
} while (0)
#endif

/* ---- guest memory (little-endian host, unaligned-safe) ---- */

static inline uint32_t rd32(uint32_t a) { uint32_t v; memcpy(&v, recomp_mem + a, 4); return v; }
static inline uint32_t rd16(uint32_t a) { uint16_t v; memcpy(&v, recomp_mem + a, 2); return v; }
static inline uint32_t rd8(uint32_t a) { return recomp_mem[a]; }
static inline uint32_t rds16(uint32_t a) { return (uint32_t)(int32_t)(int16_t)rd16(a); }
static inline uint32_t rds8(uint32_t a) { return (uint32_t)(int32_t)(int8_t)rd8(a); }
static inline void wr32(uint32_t a, uint32_t v) { memcpy(recomp_mem + a, &v, 4); }
static inline void wr16(uint32_t a, uint32_t v) { uint16_t h = (uint16_t)v; memcpy(recomp_mem + a, &h, 2); }
static inline void wr8(uint32_t a, uint32_t v) { recomp_mem[a] = (uint8_t)v; }

/* ---- shifts by register (amount is the register's low byte) ---- */

static inline uint32_t lsl_r(uint32_t v, uint32_t n) { n &= 0xFF; return n >= 32 ? 0 : v << n; }
static inline uint32_t lsr_r(uint32_t v, uint32_t n) { n &= 0xFF; return n >= 32 ? 0 : v >> n; }
static inline uint32_t asr_r(uint32_t v, uint32_t n) {
    n &= 0xFF;
    return (uint32_t)((int32_t)v >> (n >= 32 ? 31 : n));
}
static inline uint32_t ror_r(uint32_t v, uint32_t n) { n &= 31; return n ? (v >> n) | (v << (32 - n)) : v; }

/* Carry-out variants. A zero amount leaves *c untouched, matching ARM. */
static inline uint32_t lsl_rc(uint32_t v, uint32_t n, uint32_t *c) {
    n &= 0xFF;
    if (n == 0) return v;
    if (n < 32) { *c = (v >> (32 - n)) & 1; return v << n; }
    *c = n == 32 ? v & 1 : 0;
    return 0;
}
static inline uint32_t lsr_rc(uint32_t v, uint32_t n, uint32_t *c) {
    n &= 0xFF;
    if (n == 0) return v;
    if (n < 32) { *c = (v >> (n - 1)) & 1; return v >> n; }
    *c = n == 32 ? v >> 31 : 0;
    return 0;
}
static inline uint32_t asr_rc(uint32_t v, uint32_t n, uint32_t *c) {
    n &= 0xFF;
    if (n == 0) return v;
    if (n < 32) { *c = (v >> (n - 1)) & 1; return (uint32_t)((int32_t)v >> n); }
    *c = v >> 31;
    return (uint32_t)((int32_t)v >> 31);
}
static inline uint32_t ror_rc(uint32_t v, uint32_t n, uint32_t *c) {
    n &= 0xFF;
    if (n == 0) return v;
    n &= 31;
    if (n == 0) { *c = v >> 31; return v; }
    v = (v >> n) | (v << (32 - n));
    *c = v >> 31;
    return v;
}

/* ---- arithmetic with flags ---- */

/* a + b + carry_in, setting carry-out and signed overflow. */
static inline uint32_t add_cv(uint32_t a, uint32_t b, uint32_t cin, uint32_t *c, uint32_t *v) {
    uint64_t wide = (uint64_t)a + b + cin;
    uint32_t r = (uint32_t)wide;
    *c = (uint32_t)(wide >> 32);
    *v = ((a ^ r) & (b ^ r)) >> 31;
    return r;
}

/* Carry/borrow predicates used by code generators. They are expressions, not
   statements, so a generator can embed them directly in an assignment. */
#define ADD_CARRY(a, b, cin) \
    ((uint32_t)(((uint64_t)(uint32_t)(a) + (uint32_t)(b) + (uint32_t)(cin)) >> 32))
#define SUB_BORROW(a, b, cin) \
    ((uint32_t)((uint64_t)(uint32_t)(a) < ((uint64_t)(uint32_t)(b) + (uint32_t)(cin))))

/* ---- saturation ---- */

static inline uint32_t sat_s32(int64_t x, uint32_t *q) {
    if (x > INT32_MAX) { *q = 1; return (uint32_t)INT32_MAX; }
    if (x < INT32_MIN) { *q = 1; return (uint32_t)INT32_MIN; }
    return (uint32_t)(int32_t)x;
}
/* Signed saturate into `bits` bits (1..32). */
static inline uint32_t ssat(int32_t x, unsigned bits, uint32_t *q) {
    int64_t hi = ((int64_t)1 << (bits - 1)) - 1, lo = -((int64_t)1 << (bits - 1));
    if (x > hi) { *q = 1; return (uint32_t)hi; }
    if (x < lo) { *q = 1; return (uint32_t)lo; }
    return (uint32_t)x;
}
/* Unsigned saturate into `bits` bits (0..31). */
static inline uint32_t usat(int32_t x, unsigned bits, uint32_t *q) {
    int64_t hi = ((int64_t)1 << bits) - 1;
    if (x > hi) { *q = 1; return (uint32_t)hi; }
    if (x < 0) { *q = 1; return 0; }
    return (uint32_t)x;
}

/* ---- packed SIMD-within-a-register operations ---- */

uint32_t recomp_parallel(Ctx *ctx, int prefix, int op, uint32_t a, uint32_t b);
uint32_t recomp_usad8(uint32_t a, uint32_t b);

/* Exclusive monitor and atomic swap operations. The guest is cooperatively
   scheduled, so a single in-runtime monitor is enough; a store clears it. */
uint32_t recomp_swp(Ctx *ctx, int byte, uint32_t addr, uint32_t value);
uint32_t recomp_ldrex(Ctx *ctx, int bits, uint32_t addr);
uint32_t recomp_strex(Ctx *ctx, int bits, uint32_t addr, uint32_t value);
uint32_t recomp_ldrexd(Ctx *ctx, uint32_t addr, uint32_t *high);
uint32_t recomp_strexd(Ctx *ctx, uint32_t addr, uint32_t low, uint32_t high);
void recomp_clrex(Ctx *ctx);

/* ARM helper operations implemented in src/arm_ops.c. `q` is the sticky
   saturation flag; byte-lane helpers update it only when a lane saturates. */
uint32_t arm_qadd(uint32_t a, uint32_t b, uint32_t *q);
uint32_t arm_qsub(uint32_t a, uint32_t b, uint32_t *q);
uint32_t arm_ssat(int32_t value, unsigned bits, uint32_t *q);
uint32_t arm_usat(int32_t value, unsigned bits, uint32_t *q);
uint32_t arm_sadd8(uint32_t a, uint32_t b, uint32_t *q);
uint32_t arm_ssub8(uint32_t a, uint32_t b, uint32_t *q);
uint32_t arm_uadd8(uint32_t a, uint32_t b, uint32_t *q);
uint32_t arm_usub8(uint32_t a, uint32_t b, uint32_t *q);
uint32_t arm_sel(uint32_t ge, uint32_t a, uint32_t b);
uint32_t arm_clz(uint32_t value);
uint32_t arm_ror(uint32_t value, uint32_t amount);

static inline uint32_t sel(uint32_t ge, uint32_t a, uint32_t b) {
    uint32_t r = 0;
    for (int i = 0; i < 4; i++) r |= (((ge >> i) & 1) ? a : b) & (0xFFu << (8 * i));
    return r;
}

static inline uint32_t clz32(uint32_t v) {
    uint32_t n = 0;
    if (!v) return 32;
    while (!(v & 0x80000000u)) { v <<= 1; n++; }
    return n;
}

static inline uint32_t rev32(uint32_t v) {
    return (v >> 24) | ((v >> 8) & 0xFF00) | ((v << 8) & 0xFF0000) | (v << 24);
}

/* ---- VFP ---- */

static inline float get_f32(const Ctx *ctx, int n) { float f; memcpy(&f, &ctx->s[n], 4); return f; }
static inline void set_f32(Ctx *ctx, int n, float f) { memcpy(&ctx->s[n], &f, 4); }
static inline double get_f64(const Ctx *ctx, int n) {
    uint64_t bits = (uint64_t)ctx->s[2 * n] | ((uint64_t)ctx->s[2 * n + 1] << 32);
    double d;
    memcpy(&d, &bits, 8);
    return d;
}
static inline void set_f64(Ctx *ctx, int n, double d) {
    uint64_t bits;
    memcpy(&bits, &d, 8);
    ctx->s[2 * n] = (uint32_t)bits;
    ctx->s[2 * n + 1] = (uint32_t)(bits >> 32);
}

/* VCMP: unordered is 0011, equal 0110, less than 1000, greater than 0010. */
static inline void vfp_cmp(Ctx *ctx, double a, double b) {
    uint32_t nzcv;
    if (a != a || b != b) nzcv = 0x3;
    else if (a == b) nzcv = 0x6;
    else if (a < b) nzcv = 0x8;
    else nzcv = 0x2;
    ctx->fpscr = (ctx->fpscr & 0x0FFFFFFFu) | (nzcv << 28);
}

/* Float-to-integer conversion with ARM semantics: NaN to zero, saturate the range. */
static inline uint32_t vfp_to_s32(double x, int round_zero) {
    if (x != x) return 0;
    x = round_zero ? trunc(x) : nearbyint(x);
    if (x >= 2147483647.0) return 0x7FFFFFFFu;
    if (x <= -2147483648.0) return 0x80000000u;
    return (uint32_t)(int32_t)x;
}
static inline uint32_t vfp_to_u32(double x, int round_zero) {
    if (x != x) return 0;
    x = round_zero ? trunc(x) : nearbyint(x);
    if (x >= 4294967295.0) return 0xFFFFFFFFu;
    if (x <= 0.0) return 0;
    return (uint32_t)x;
}

#ifdef __cplusplus
}
#endif

#endif
