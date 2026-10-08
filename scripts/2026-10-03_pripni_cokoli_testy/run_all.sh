#!/bin/bash
# Testy prvku "Připni cokoli" (bot10, 2026-10-03): háček pluginů ve vieweru, plugin demo-stavebnice.js, stránka pripni-cokoli.html.
# Offline (SwiftShader, bez sítě), nic nezapisuje do repa ani do DB; syntetické GLB jdou do $TMPDIR. Běh cca 3-6 min (podle zatížení).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-/opt/konfigurator/api/venv/bin/python}"
OUT="${TMPDIR:-/tmp}/pripni_cokoli_testy"
mkdir -p "$OUT"
export PYTHONDONTWRITEBYTECODE=1
"$PY" "$HERE/make_synth_glb.py" "$OUT/synth_demo.glb" > /dev/null || exit 2
"$PY" "$HERE/make_synth_glb2.py" "$OUT/synth_demo2.glb" > /dev/null || exit 2
cd "$HERE" || exit 2
rc=0
echo "=== háček opts.plugins";      node test_plugin_hook.js || rc=1
echo "=== plugin demo-stavebnice";  GLB="$OUT/synth_demo.glb" node test_demo_plugin.js || rc=1
echo "=== stránka pripni-cokoli";   GLB="$OUT/synth_demo2.glb" node test_stranka.js || rc=1
echo "=== popisky v pruhu (skutečný model z webapp/pripni-cokoli)"; GLB="${GLB_REAL:-/opt/konfigurator/webapp/pripni-cokoli/stavebnice-demo.glb}" node test_popisky.js || rc=1
echo "=== prvek do mřížky (pripni-cokoli-tile.js, cesty jako whitelist mini-shopu)"; GLB="${GLB_REAL:-/opt/konfigurator/webapp/pripni-cokoli/stavebnice-demo.glb}" node test_tile.js || rc=1
echo "=== náhled s vlastními texty (nahled/<id>/texty.json, skutečný model spoj-sroubem-v1)"; node test_nahled_texty.js || rc=1
if [ "$rc" = 0 ]; then echo "VSE OK"; else echo "NEKTERY TEST SELHAL"; fi
exit $rc
