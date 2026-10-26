#!/usr/bin/env bash
# Run Ghidra headless against the already-imported FL EU project (ignored, under tools/build).
# usage: tools/re/ghidra.sh OUT_DIR ARG...   (ARG syntax: see QueryFl.java)
# First-time import: tools/re/ghidra.sh --import   (FL_GHIDRA_PROJ=dir overrides the project location)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
B="$ROOT/tools/build"
export JAVA_HOME="$B/jdk" PATH="$B/jdk/bin:$PATH"
GH="$B/ghidra_10.1.5_PUBLIC/support/analyzeHeadless"
PROJ="${FL_GHIDRA_PROJ:-$B/ghidra-project}"
if [ "${1:-}" = "--import" ]; then
  rm -rf "$PROJ"; mkdir -p "$PROJ"
  exec "$GH" "$PROJ" fl_eu -import "$ROOT/extracted/fl_eu/exefs/code.bin" \
    -processor ARM:LE:32:v6 -loader BinaryLoader -loader-baseAddr 0x00100000 \
    -scriptPath "$ROOT/tools/re" -preScript ImportFl.java
fi
OUT="$1"; shift
"$GH" "$PROJ" fl_eu -process code.bin -noanalysis -scriptPath "$ROOT/tools/re" \
  -postScript QueryFl.java "$OUT" "$@" > "$OUT.log" 2>&1 || { tail -20 "$OUT.log"; exit 1; }
