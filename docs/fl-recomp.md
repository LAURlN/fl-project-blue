# fl-recomp: clean-room ARM11 AOT translator

> **Note:** paths starting with `port/` (and `runtime/`) refer to the runtime's source code, which is not part of this package. They are kept as historical research context.

[`tools/fl-recomp`](../tools/fl-recomp/README.md) is the first-party replacement
for Clockwork's `recomp`/`ctrx` path for Fantasy Life EU v00
(`0004000000113100`, `CTR-P-AFLP`). It consumes the ExeFS files produced by our
own `tools/phase0_extract.py` and emits portable C17 that links against the
runtime's `Ctx` contract.

The implementation is original. It was written from the public ARMv6K /
ARMv6 ARM and VFPv2 architecture rules plus this project's own extraction and
CFG/symbol audits. No Clockwork Rust source was copied or translated, and the
crate has no dependencies.

## Inputs

- `extracted/fl_eu/exheader.bin` — SCI segment table and entry point.
- `extracted/fl_eu/exefs/code.bin` — decompressed `.code` image, mapped at
  `0x00100000` (`text` ends at `0x0061cc68`).
- `port/runtime/src/games/fantasylife/eu-v00-entries.txt` — known entries and
  the ARM/Thumb bit convention.
- `port/runtime/src/games/fantasylife/eu-v00-polls.txt` — scheduler poll
  entries. A poll emits `recomp_svc(ctx, 0xFFFFFFFF, entry)` on entry.

Game data stays in the main checkout and is ignored by git. Generated C is
never committed.

## Commands

```sh
cd tools/fl-recomp
cargo +stable build --release

./target/release/fl-recomp analyze ../../extracted/fl_eu \
  --entries ../../port/runtime/src/games/fantasylife/eu-v00-entries.txt \
  --polls   ../../port/runtime/src/games/fantasylife/eu-v00-polls.txt

./target/release/fl-recomp emit ../../extracted/fl_eu ../../build/generated-fl-eu \
  --entries ../../port/runtime/src/games/fantasylife/eu-v00-entries.txt \
  --polls   ../../port/runtime/src/games/fantasylife/eu-v00-polls.txt
```

`analyze` exits non-zero if any *discovered* instruction is undecodable.
`emit` refuses to write C in that case. `analyze --json FILE` reports every
function, gap, rejected seed, switch and stub site.

## Discovery

Entries are deterministic and independent of any third-party recompiler:

1. the image entry point;
2. explicit entry and poll lists;
3. every direct ARM `BL`/`BLX` immediate target found by a word scan;
4. every direct Thumb `BL`/`BLX` target found while walking decoded functions;
5. aligned runs of text pointers in `.rodata`/`.data` (three or more);
6. ARM `STMDB sp!` / `SUB sp, sp` and T16 `PUSH` / `SUB sp` prologues in
   uncovered text;
7. the instruction after a decoded return, and starts of leftover gaps, with
   recursive recovery. A recovered walk is kept only if it is fully decodable
   and actually leaves the function (return, indirect branch or tail call).

Each function's internal CFG is recovered recursively. Conditional branches
always keep their fallthrough; unconditional branches end the linear extent.
Branches to an already-known entry are tail calls. Calls start new functions.

Switch tables are resolved for the two canonical ARM forms:

- `cmp rX, #N; add pc, pc, rX, lsl #2` with a run of case instructions directly
  after the `add`;
- `ldr pc, [pc, rX, lsl #2]` with an absolute-address table.

Case targets are fed back into discovery, so switch-only functions and their
case code are translated.

## Decoder and C17 output

`arm.rs` covers the ARMv6K A32 set needed by the image, including the media /
SIMD group (`SEL`, `UADD8`, `USAT`, `PKH`, `SXTAB16`, `USAD8`, …), the
LDREX/STREX family, TLS `MRC p15, 0, rX, c13, c0, 3`, and VFPv2 single/double
data processing, comparisons, conversions and load/store multiples. `thumb.rs`
covers Thumb-1 plus the 32-bit `BL`/`BLX` pair; Thumb-2 is rejected by design.

Every instruction becomes portable C operating on `Ctx`:

- registers `r[16]`, flags `n/z/c/v/q/ge`, VFP `s[32]`, `fpscr`, `tls`;
- memory through `rd8/16/32` and `wr8/16/32` on `recomp_mem`;
- `recomp_svc`, `recomp_call_indirect`, `recomp_unhandled`, `recomp_coproc`;
- `RECOMP_ENTER` (compiled out unless `RECOMP_TRACE_CALLS` is defined).

Flags use the runtime's `add_cv` / shift helpers. VFP single operations stay in
`float`; double operations stay in `double`; the build uses
`-ffp-contract=off` so no fused multiply-add is introduced.

## Measured results (EU v00, 2026-10-26)

| Metric | Value |
|---|---:|
| Discovered functions | 32,535 |
| Decoded instructions | 1,287,028 |
| Text bytes covered | 5,199,004 / 5,360,744 (**96.98%**) |
| Literal/table bytes | 189,592 |
| Switch-table bytes | 34,784 |
| Remaining gap bytes | 161,740 |
| Undecodable instructions | **0** |
| Functions emitted as aborting stubs | 15 |
| Indirect-control sites | 13,922 |
| Rejected seeds | 55 |
| Lookup-table entries | 32,550 |

The 15 stubs are functions whose bytes include data or non-Thumb-1 encodings;
they call `recomp_unhandled` with their exact guest address instead of emitting
wrong C. Remaining gaps are chiefly literal pools, fill/data and unreached
islands, not accepted instructions.

Performance on the development machine:

- `analyze`: about 2.3 s;
- `emit`: 5–9 s for 32,535 functions / 1.29 M instructions / 286 MB of C;
- full parallel clang compile: about 25 s (132 generated C files: 131 chunks
  plus `fl_recomp_lookup.c`) and 133 objects including the runtime
  `arm_ops.c` helpers.

## Verification

All checks are offline; the game is never launched.

```sh
# Decoder + discovery + emitted-code ground truth (9 tests)
cargo +stable test --release

# Runtime helper vectors (137 checks): NZCV, shifter carry, VFP compare,
# single/double storage, conversions, SIMD, exclusive monitor
R=../../port/runtime
clang -std=c17 -O2 -ffp-contract=off -I "$R/include" \
  tests/semantics.c "$R/src/arm_ops.c" -lm -o /tmp/semantics && /tmp/semantics

# Emitted C compile + link contract
R=../../port/runtime
clang -std=c17 -O0 -I "$R/include" -I ../../build/generated-fl-eu \
  tests/link_stub.c ../../build/obj-fl-eu/*.o -lm -o /tmp/link_stub
/tmp/link_stub     # linked 32550 functions; first 00100000

# One real leaf function executed against the loaded image
clang -std=c17 -O0 -I "$R/include" -I ../../build/generated-fl-eu \
  tests/execute_smoke.c ../../build/obj-fl-eu/*.o -lm -o /tmp/execute_smoke
/tmp/execute_smoke ../../extracted/fl_eu/exefs/code.bin
# fn_00100024 zeroed 838280 bytes: ok
```

The generated C compiles with clang 22 using
`-Werror=implicit-function-declaration -Werror=incompatible-pointer-types
-Werror=int-conversion` and produces no diagnostics. `link_stub.c` provides
the runtime entry points and checks the generated lookup table; it is not a
game runtime.

Decoder vectors use encodings produced by clang's integrated ARMv6K assembler
as independent ground truth. Semantics vectors are calculated from the
architecture rules. No expected value is obtained by calling the code under
test.

The emitted-code test builds a synthetic image, translates it, compiles the
result with clang and executes it. It checks ARM NZCV, register-specified LSR
by zero, `vmla`/`vnmla`/`vnmls`, double division and `vcmp` against hand-written
expected values.

Real bugs found and fixed by these tests:

- T16 conditional branches lost their condition and were emitted
  unconditionally;
- T16 `rsbs rd, rm, #0` read the destination instead of the source;
- `vcmp #0` was conflated with a register compare, and VCVT
  float/integer operands were initially treated as ARM core registers;
- `VNMLA`/`VNMLS` negated the combined result instead of the accumulator;
- register-specified `LSR`/`ASR` by zero returned the input instead of shifting
  by 32;
- VFP load/store single-register numbers and double-register ranges used the
  wrong field mapping, which could index past `Ctx::s[32]`; and
- the lookup table appended stubs after sorted functions, breaking the
  runtime's binary search.

## Runtime contract additions

The committed tool expects the `Ctx` contract in `port/runtime/include/recomp.h`.
The local Clockwork runtime needed these additions, which are currently in the
git-ignored `/port/` copy and must be carried into the first-party runtime:

- `Ctx` fields `exclusive_addr`, `exclusive_lo`, `exclusive_hi`,
  `exclusive_valid` — one pending reservation is enough for cooperative
  scheduling;
- helpers `recomp_ldrex`, `recomp_strex`, `recomp_ldrexd`, `recomp_strexd`,
  `recomp_clrex`, `recomp_swp`;
- `recomp_parallel` (ADD16/ASX/SAX/SUB16/ADD8/SUB8, plain/saturating/halving,
  signed/unsigned) and `recomp_usad8`;
- the register-shift helpers must treat a shift amount of zero as 32 for
  `LSR`/`ASR` (not as "no shift"), and `recomp_functions` must stay strictly
  sorted by guest address because `recomp_call_indirect` binary-searches it.

`port/` is a private, ignored fork; nothing under it is published.

## Limitations

- Only the main `.text` segment is translated. CROs, relocation processing and
  loader-time fixups are out of scope for this pass.
- Exception returns (`MOVS pc, lr` in privileged modes) are treated as ordinary
  PC writes. `CPS`, `SETEND`, `PLD` and barriers are no-ops; unmodelled
  coprocessor accesses abort with `recomp_coproc`.
- VFP fixed-point conversions abort at runtime (`VFP fixed-point conversion`).
- VFPv2 only: D16–D31 and VFPv3-only encodings are rejected, never indexed past
  `Ctx::s[32]`.
- No self-modifying code support; guest code bytes are translated once.
- 15 discovered functions are data-bearing stubs, and about 3.0% of text is
  unattributed. Discovery is conservative by design: it would rather leave a
  gap than emit a function that is actually data.
