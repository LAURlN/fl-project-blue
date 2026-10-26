#!/usr/bin/env bash
# Build and run the runtime semantic vectors against the local runtime sources.
#
#   tests/run_semantics.sh [path-to-port/runtime]
#
# The default is ../../port/runtime relative to this crate (i.e. the main
# checkout's private Clockwork fork). Nothing is written outside the build dir.
set -euo pipefail

crate=$(cd "$(dirname "$0")/.." && pwd)
runtime=${1:-"$crate/../../port/runtime"}
cc=${CC:-clang}
out="$crate/build/semantics${EXEEXT:-}"

mkdir -p "$crate/build"
"$cc" -std=c17 -O2 -ffp-contract=off \
    -I "$runtime/include" \
    "$crate/tests/semantics.c" "$runtime/src/arm_ops.c" -lm \
    -o "$out"
exec "$out"
