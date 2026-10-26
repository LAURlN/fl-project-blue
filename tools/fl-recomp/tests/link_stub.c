/* Offline link check for generated Fantasy Life code.  No game is booted. */
#include "recomp.h"

#include <stdio.h>
#include <stdlib.h>

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

int main(void) {
    recomp_mem = calloc(1, 0x800000);
    if (!recomp_mem) return 2;
    if (recomp_function_count == 0) return 3;
    for (size_t i = 1; i < recomp_function_count; i++) {
        if (recomp_functions[i - 1].addr >= recomp_functions[i].addr) {
            fprintf(stderr, "lookup not strictly sorted at %zu: %08x then %08x\n",
                    i, recomp_functions[i - 1].addr, recomp_functions[i].addr);
            return 4;
        }
    }
    printf("linked %zu sorted functions; first %08x\n", recomp_function_count, recomp_functions[0].addr);
    free(recomp_mem);
    return 0;
}
