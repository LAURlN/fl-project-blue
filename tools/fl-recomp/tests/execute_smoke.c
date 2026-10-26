/* Offline execution smoke test for one generated leaf function. */
#include "fl_recomp.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

uint8_t *recomp_mem;
/* Offline harness: no hooks are registered, but generated entry checks use the ABI. */
static uint8_t hook_pages[1u << 20];
uint8_t *recomp_hook_page_map = hook_pages;
int recomp_hook_enter(Ctx *ctx, uint32_t addr) { (void)ctx; (void)addr; return 0; }


void recomp_svc(Ctx *ctx, uint32_t imm, uint32_t addr) { (void)ctx; (void)imm; (void)addr; }
void recomp_call_indirect(Ctx *ctx, uint32_t target) { (void)ctx; (void)target; }
void recomp_unhandled(Ctx *ctx, uint32_t addr, const char *what) {
    (void)ctx;
    fprintf(stderr, "unhandled %08x: %s\n", addr, what);
    abort();
}
void recomp_coproc(Ctx *ctx, uint32_t addr, uint32_t raw) {
    (void)ctx;
    fprintf(stderr, "coproc %08x: %08x\n", addr, raw);
    abort();
}

int main(int argc, char **argv) {
    const uint32_t begin = 0x006db1b4u;
    const uint32_t end = 0x007a7c3cu;
    recomp_mem = malloc(0x800000);
    if (!recomp_mem) return 2;
    memset(recomp_mem, 0xA5, 0x800000);
    if (argc > 1) {
        FILE *f = fopen(argv[1], "rb");
        if (!f) return 2;
        size_t n = fread(recomp_mem + 0x100000, 1, 0x520000, f);
        fclose(f);
        if (n < 0x100) return 2;
    }

    Ctx ctx;
    memset(&ctx, 0, sizeof(ctx));
    fn_00100024(&ctx);

    int ok = 1;
    for (uint32_t a = begin; a < end; a += 4) {
        if (rd32(a) != 0) {
            fprintf(stderr, "not zero at %08x: %08x\n", a, rd32(a));
            ok = 0;
            break;
        }
    }
    if (rd32(begin - 4) != 0xA5A5A5A5u || rd32(end) != 0xA5A5A5A5u) {
        fprintf(stderr, "range boundary overwritten\n");
        ok = 0;
    }
    printf("fn_00100024 zeroed %u bytes: %s\n", end - begin, ok ? "ok" : "FAIL");
    free(recomp_mem);
    return ok ? 0 : 1;
}
