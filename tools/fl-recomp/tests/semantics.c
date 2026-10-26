/*
 * Ground-truth vectors for the runtime helpers used by generated code.
 *
 * This is an offline test: it never boots the game and never touches a real
 * 3DS image. Expected values are worked out from the ARMv6 ARM and the VFPv2
 * architecture reference, not by comparing two implementations of the same
 * helper.
 *
 * Build (from the fl-recomp crate):
 *   clang -std=c17 -O2 -ffp-contract=off \
 *     -I <repo>/port/runtime/include \
 *     tests/semantics.c <repo>/port/runtime/src/arm_ops.c -lm -o semantics
 *   ./semantics
 */
#include "recomp.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

uint8_t *recomp_mem;

static int failures;
static int checks;

#define CHECK(cond, ...)                                                     \
    do {                                                                     \
        checks++;                                                            \
        if (!(cond)) {                                                       \
            failures++;                                                      \
            fprintf(stderr, "FAIL %s:%d: ", __FILE__, __LINE__);             \
            fprintf(stderr, __VA_ARGS__);                                    \
            fputc('\n', stderr);                                             \
        }                                                                    \
    } while (0)

#define CHECK_TRUE(cond) CHECK(cond, "%s", #cond)

#define CHECK_U32(actual, expected)                                          \
    do {                                                                     \
        uint32_t a_ = (uint32_t)(actual), e_ = (uint32_t)(expected);         \
        CHECK(a_ == e_, "got %08x want %08x", a_, e_);                       \
    } while (0)

static void test_add_cv(void) {
    uint32_t c, v, r;

    r = add_cv(0, 0, 0, &c, &v);
    CHECK_U32(r, 0);
    CHECK_U32(c, 0);
    CHECK_U32(v, 0);

    r = add_cv(0xFFFFFFFFu, 1, 0, &c, &v);
    CHECK_U32(r, 0);
    CHECK_U32(c, 1);
    CHECK_U32(v, 0);

    r = add_cv(0x7FFFFFFFu, 1, 0, &c, &v);
    CHECK_U32(r, 0x80000000u);
    CHECK_U32(c, 0);
    CHECK_U32(v, 1);

    r = add_cv(0x80000000u, 0x80000000u, 0, &c, &v);
    CHECK_U32(r, 0);
    CHECK_U32(c, 1);
    CHECK_U32(v, 1);

    r = add_cv(0xFFFFFFFFu, 0xFFFFFFFFu, 1, &c, &v);
    CHECK_U32(r, 0xFFFFFFFFu);
    CHECK_U32(c, 1);
    CHECK_U32(v, 0);

    /* 0x7fffffff + 0xffffffff: carry out, no signed overflow. */
    r = add_cv(0x7FFFFFFFu, 0xFFFFFFFFu, 0, &c, &v);
    CHECK_U32(r, 0x7FFFFFFEu);
    CHECK_U32(c, 1);
    CHECK_U32(v, 0);

    /* negative + negative -> positive is signed overflow. */
    r = add_cv(0x80000000u, 0xFFFFFFFFu, 0, &c, &v);
    CHECK_U32(r, 0x7FFFFFFFu);
    CHECK_U32(c, 1);
    CHECK_U32(v, 1);

    /* ADC with carry-in. */
    r = add_cv(0xFFFFFFFFu, 0, 1, &c, &v);
    CHECK_U32(r, 0);
    CHECK_U32(c, 1);
    CHECK_U32(v, 0);
}

static void test_shifts(void) {
    uint32_t c, r;

    /* A zero register-specified shift leaves C unchanged. */
    c = 1;
    r = lsl_rc(0x12345678u, 0, &c);
    CHECK_U32(r, 0x12345678u);
    CHECK_U32(c, 1);
    c = 0;
    r = lsr_rc(0x12345678u, 0, &c);
    CHECK_U32(r, 0); /* register shift by zero means 32 */
    CHECK_U32(c, 0);
    c = 0;
    r = lsr_rc(0x80000000u, 0, &c);
    CHECK_U32(r, 0);
    CHECK_U32(c, 1);
    c = 0;
    r = asr_rc(0x80000000u, 0, &c);
    CHECK_U32(r, 0xFFFFFFFFu);
    CHECK_U32(c, 1);

    CHECK_U32(lsr_r(0x12345678u, 0), 0);
    CHECK_U32(asr_r(0x80000000u, 0), 0xFFFFFFFFu);

    /* LSL carry-out is the last bit shifted out. */
    c = 0;
    r = lsl_rc(0x80000000u, 1, &c);
    CHECK_U32(r, 0);
    CHECK_U32(c, 1);
    c = 0;
    r = lsl_rc(1u, 31, &c);
    CHECK_U32(r, 0x80000000u);
    CHECK_U32(c, 0);
    c = 0;
    r = lsl_rc(0xFFFFFFFFu, 32, &c);
    CHECK_U32(r, 0);
    CHECK_U32(c, 1);
    c = 1;
    r = lsl_rc(0xFFFFFFFFu, 33, &c);
    CHECK_U32(r, 0);
    CHECK_U32(c, 0);

    /* LSR */
    c = 0;
    r = lsr_rc(1u, 1, &c);
    CHECK_U32(r, 0);
    CHECK_U32(c, 1);
    c = 0;
    r = lsr_rc(0x80000000u, 32, &c);
    CHECK_U32(r, 0);
    CHECK_U32(c, 1);
    c = 1;
    r = lsr_rc(0x80000000u, 33, &c);
    CHECK_U32(r, 0);
    CHECK_U32(c, 0);

    /* ASR sign-fills and carry is the last bit shifted out. */
    c = 1;
    r = asr_rc(0x80000000u, 1, &c);
    CHECK_U32(r, 0xC0000000u);
    CHECK_U32(c, 0);
    c = 0;
    r = asr_rc(0x80000000u, 32, &c);
    CHECK_U32(r, 0xFFFFFFFFu);
    CHECK_U32(c, 1);
    c = 0;
    r = asr_rc(0x7FFFFFFFu, 31, &c);
    CHECK_U32(r, 0);
    CHECK_U32(c, 1); /* carry is bit 30 of the source */

    /* ROR: n == 0 leaves C unchanged; n == 32 is ROR #0 with carry bit31. */
    c = 1;
    r = ror_rc(0x12345678u, 0, &c);
    CHECK_U32(r, 0x12345678u);
    CHECK_U32(c, 1);
    c = 0;
    r = ror_rc(1u, 1, &c);
    CHECK_U32(r, 0x80000000u);
    CHECK_U32(c, 1);
    c = 0;
    r = ror_rc(0x80000001u, 32, &c);
    CHECK_U32(r, 0x80000001u);
    CHECK_U32(c, 1);
    c = 0;
    r = ror_rc(0x80000001u, 33, &c);
    CHECK_U32(r, 0xC0000000u);
    CHECK_U32(c, 1);
}

static void test_vfp_flags(void) {
    Ctx ctx;
    memset(&ctx, 0, sizeof(ctx));
    ctx.fpscr = 0x00000040u; /* an unrelated sticky exception bit */

    vfp_cmp(&ctx, 1.0, 1.0);
    CHECK_U32(ctx.fpscr >> 28, 0x6); /* Z=1 C=1 */
    CHECK_U32(ctx.fpscr & 0x0FFFFFFFu, 0x40);

    vfp_cmp(&ctx, 1.0, 2.0);
    CHECK_U32(ctx.fpscr >> 28, 0x8); /* N=1 */
    vfp_cmp(&ctx, 2.0, 1.0);
    CHECK_U32(ctx.fpscr >> 28, 0x2); /* C=1 */
    vfp_cmp(&ctx, NAN, 1.0);
    CHECK_U32(ctx.fpscr >> 28, 0x3); /* unordered: C=1 V=1 */
    vfp_cmp(&ctx, 1.0, NAN);
    CHECK_U32(ctx.fpscr >> 28, 0x3);
    vfp_cmp(&ctx, -0.0, 0.0);
    CHECK_U32(ctx.fpscr >> 28, 0x6);
    vfp_cmp(&ctx, -1.0, 1.0);
    CHECK_U32(ctx.fpscr >> 28, 0x8);
}

static void test_vfp_convert(void) {
    CHECK_U32(vfp_to_s32(NAN, 0), 0);
    CHECK_U32(vfp_to_s32(INFINITY, 0), 0x7FFFFFFFu);
    CHECK_U32(vfp_to_s32(-INFINITY, 0), 0x80000000u);
    CHECK_U32(vfp_to_s32(1e30, 0), 0x7FFFFFFFu);
    CHECK_U32(vfp_to_s32(-1e30, 0), 0x80000000u);
    CHECK_U32(vfp_to_s32(1.9, 1), 1);
    CHECK_U32(vfp_to_s32(1.9, 0), 2);
    CHECK_U32(vfp_to_s32(-1.5, 0), 0xFFFFFFFEu); /* nearest-even -> -2 */
    CHECK_U32(vfp_to_s32(-1.5, 1), 0xFFFFFFFFu); /* toward zero   -> -1 */
    CHECK_U32(vfp_to_s32(2147483520.0, 0), 0x7FFFFF80u);

    CHECK_U32(vfp_to_u32(NAN, 0), 0);
    CHECK_U32(vfp_to_u32(-1.0, 0), 0);
    CHECK_U32(vfp_to_u32(4294967296.0, 0), 0xFFFFFFFFu);
    CHECK_U32(vfp_to_u32(4294967040.0, 0), 0xFFFFFF00u);
    CHECK_U32(vfp_to_u32(1.9, 1), 1);
    CHECK_U32(vfp_to_u32(1.9, 0), 2);
}

static void test_vfp_storage(void) {
    Ctx ctx;
    memset(&ctx, 0, sizeof(ctx));

    set_f32(&ctx, 3, 1.5f);
    CHECK_U32(ctx.s[3], 0x3FC00000u);
    CHECK_TRUE(get_f32(&ctx, 3) == 1.5f);

    /* NaNs must survive the store/load round trip bit for bit. */
    ctx.s[4] = 0x7FC12345u;
    float f = get_f32(&ctx, 4);
    set_f32(&ctx, 5, f);
    CHECK_U32(ctx.s[5], 0x7FC12345u);

    set_f64(&ctx, 2, -2.25);
    CHECK_U32(ctx.s[4], 0);
    CHECK_U32(ctx.s[5], 0xC0020000u);
    CHECK_TRUE(get_f64(&ctx, 2) == -2.25);
    CHECK_U32(ctx.s[0], 0); /* d2 does not alias s0 */

    set_f64(&ctx, 0, 1.0);
    CHECK_U32(ctx.s[0], 0);
    CHECK_U32(ctx.s[1], 0x3FF00000u);
}

static void test_simd(void) {
    Ctx ctx;
    memset(&ctx, 0, sizeof(ctx));

    /* UADD8: modulo 256 per lane; GE is the carry out of each lane. */
    CHECK_U32(recomp_parallel(&ctx, 3, 4, 0x01020304u, 0x01020304u), 0x02040608u);
    CHECK_U32(ctx.ge, 0x0); /* no lane carried */
    CHECK_U32(recomp_parallel(&ctx, 3, 4, 0xFF000000u, 0x01000000u), 0);
    CHECK_U32(ctx.ge, 0x8); /* lane 3 (the MSB) carried */
    CHECK_U32(recomp_parallel(&ctx, 3, 4, 0xFE010203u, 0x01020304u), 0xFF030507u);
    CHECK_U32(ctx.ge, 0x0);

    /* QADD8 saturates signed bytes and clears GE. */
    ctx.ge = 0xF;
    CHECK_U32(recomp_parallel(&ctx, 1, 4, 0x7F0180FFu, 0x01020101u), 0x7F038100u);
    CHECK_U32(ctx.ge, 0);

    /* UQADD8 saturates unsigned bytes. */
    CHECK_U32(recomp_parallel(&ctx, 4, 4, 0x7F0180FFu, 0x01020101u), 0x800381FFu);

    /* SADD8 sets GE when the signed lane result is non-negative. */
    CHECK_U32(recomp_parallel(&ctx, 0, 4, 0x80010203u, 0x80010203u), 0x00020406u);
    CHECK_U32(ctx.ge, 0x7); /* the three positive lanes; lane 3 overflowed negative */

    /* SHADD16 halves the exact sum (not each operand). */
    CHECK_U32(recomp_parallel(&ctx, 2, 0, 0x00010003u, 0x00030001u), 0x00020002u);

    /* USAD8 sums absolute byte differences. */
    CHECK_U32(recomp_usad8(0x01020304u, 0x04030201u), 3 + 1 + 1 + 3);
    CHECK_U32(recomp_usad8(0, 0), 0);

    /* SEL selects bytes under GE. */
    CHECK_U32(sel(0x5, 0x11223344u, 0xAABBCCDDu), 0xAA22CC44u);
    CHECK_U32(sel(0x0, 0x11223344u, 0xAABBCCDDu), 0xAABBCCDDu);
    CHECK_U32(sel(0xF, 0x11223344u, 0xAABBCCDDu), 0x11223344u);

    CHECK_U32(clz32(0), 32);
    CHECK_U32(clz32(1), 31);
    CHECK_U32(clz32(0x80000000u), 0);
    CHECK_U32(rev32(0x11223344u), 0x44332211u);
}

static void test_exclusive(void) {
    Ctx ctx;
    memset(&ctx, 0, sizeof(ctx));
    memset(recomp_mem, 0, 0x1000);

    wr32(0x100, 0x11223344u);
    CHECK_U32(recomp_ldrex(&ctx, 32, 0x100), 0x11223344u);
    CHECK_U32(recomp_strex(&ctx, 32, 0x100, 0x55667788u), 0);
    CHECK_U32(rd32(0x100), 0x55667788u);

    /* The reservation is consumed even when the store fails. */
    CHECK_U32(recomp_strex(&ctx, 32, 0x100, 0x99AABBCCu), 1);
    CHECK_U32(rd32(0x100), 0x55667788u);

    CHECK_U32(recomp_ldrex(&ctx, 32, 0x100), 0x55667788u);
    wr32(0x100, 0xDEADBEEFu); /* another agent wrote the line */
    CHECK_U32(recomp_strex(&ctx, 32, 0x100, 0), 1);
    CHECK_U32(rd32(0x100), 0xDEADBEEFu);

    /* Byte reservation only compares the addressed byte. */
    wr32(0x200, 0x11223344u);
    CHECK_U32(recomp_ldrex(&ctx, 8, 0x200), 0x44);
    CHECK_U32(recomp_strex(&ctx, 8, 0x200, 0xAA), 0);
    CHECK_U32(rd32(0x200), 0x112233AAu);

    /* LDREXD/STREXD compare both words. */
    wr32(0x300, 1);
    wr32(0x304, 2);
    uint32_t hi = 0;
    CHECK_U32(recomp_ldrexd(&ctx, 0x300, &hi), 1);
    CHECK_U32(hi, 2);
    CHECK_U32(recomp_strexd(&ctx, 0x300, 3, 4), 0);
    CHECK_U32(rd32(0x300), 3);
    CHECK_U32(rd32(0x304), 4);

    recomp_clrex(&ctx);
    CHECK_U32(recomp_strex(&ctx, 32, 0x300, 0), 1);

    /* SWP returns the old value and writes the new one. */
    wr32(0x400, 0xCAFEBABEu);
    CHECK_U32(recomp_swp(&ctx, 0, 0x400, 0x12345678u), 0xCAFEBABEu);
    CHECK_U32(rd32(0x400), 0x12345678u);
    wr8(0x401, 0x77);
    CHECK_U32(recomp_swp(&ctx, 1, 0x401, 0x99u), 0x77);
    CHECK_U32(rd8(0x401), 0x99);
}

int main(void) {
    recomp_mem = calloc(1, 0x1000);
    if (!recomp_mem) {
        fprintf(stderr, "out of memory\n");
        return 2;
    }

    test_add_cv();
    test_shifts();
    test_vfp_flags();
    test_vfp_convert();
    test_vfp_storage();
    test_simd();
    test_exclusive();

    free(recomp_mem);
    printf("%d checks, %d failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
