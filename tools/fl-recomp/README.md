# fl-recomp

Clean-room ARM11 (ARMv6K A32 + Thumb-1 + VFPv2) ahead-of-time translator for
Fantasy Life EU v00 (`0004000000113100`, `CTR-P-AFLP`). It replaces Clockwork's
`ctrx` + `recomp` path with a first-party crate that consumes our own
`exheader.bin` and `exefs/code.bin` and emits portable C17 for the runtime's
`Ctx` contract.

The implementation is original and has no third-party dependencies. It was
written from the public ARMv6K / VFPv2 architecture rules and this project's
extraction, symbol and CFG audits; no Clockwork Rust source was copied or
translated. See [docs/fl-recomp.md](../../docs/fl-recomp.md) for the full design,
measured coverage, runtime contract and limitations.

## Build

```sh
cargo +stable build --release
```

## Use

```sh
./target/release/fl-recomp analyze ../../extracted/fl_eu \
  --entries ../../port/runtime/src/games/fantasylife/eu-v00-entries.txt \
  --polls   ../../port/runtime/src/games/fantasylife/eu-v00-polls.txt

./target/release/fl-recomp emit ../../extracted/fl_eu ../../build/generated-fl-eu \
  --entries ../../port/runtime/src/games/fantasylife/eu-v00-entries.txt \
  --polls   ../../port/runtime/src/games/fantasylife/eu-v00-polls.txt
```

`analyze` fails if a discovered instruction cannot be decoded. `emit` writes
one header (`fl_recomp.h`), a sorted lookup table (`lookup.c`) and chunked
`fl_recomp_NNN.c` files; it never writes game data.

`fl-recomp decode <hex-word> [arm|thumb]` decodes a single instruction, which is
handy when triaging a report.

## Verification

```sh
cargo +stable test --release                 # 9 decoder/discovery/emit tests
bash tests/run_semantics.sh ../../port/runtime  # 137 runtime-helper checks
```

The C tests in [`tests/`](tests) check ARM arithmetic/flags, shifter carry-out,
VFP single/double storage and comparison, conversions, SIMD and the exclusive
monitor against hand-derived ground-truth vectors. `link_stub.c` checks the
generated lookup table and link contract; `execute_smoke.c` runs one generated
leaf function against the real `code.bin` without booting the game.

All generated C is excluded from version control and must be rebuilt locally.
