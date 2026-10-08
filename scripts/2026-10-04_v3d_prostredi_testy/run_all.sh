#!/bin/bash
# Testy prostredi (HDRI) pro admina generatoru (bot10, 2026-10-04): viewer3d.js 1.9.0 (setEnvConfig, knihovna HDRI) a panel env-picker.js. Offline (SwiftShader), nic nezapisuje do repa ani DB.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-/opt/konfigurator/api/venv/bin/python}"
OUT="${TMPDIR:-/tmp}/v3d_prostredi_testy"
mkdir -p "$OUT"
export PYTHONDONTWRITEBYTECODE=1
"$PY" "$HERE/../2026-10-03_pripni_cokoli_testy/make_synth_glb.py" "$OUT/synth.glb" > /dev/null || exit 2
cd "$HERE" || exit 2
GLB="$OUT/synth.glb" node test_prostredi.js
