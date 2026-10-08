#!/bin/bash
# Znovu spustí všechna ověření průzkumu (jen čtení: SELECT + čtení katalogových GLB; zapisuje jen do tohoto adresáře).
# Použití: bash run_all.sh      (venv Python z /opt/konfigurator/api/venv, Node z /usr/bin)
cd "$(dirname "$0")" || exit 1
PY=/opt/konfigurator/api/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1
set -e
echo "### 1) složení GLB + AABB vs three + sanitizer + spoje (custom_shapes #577)"; $PY prototyp_compose_glb.py --shape 577 --repeat 3
echo; echo "### 2) totéž na největší uložené sestavě (product_assemblies #664, 168 dílů)"; $PY prototyp_compose_glb.py --assembly 664 --repeat 3
echo; echo "### 3) počet spojů: Python vs kód scene.html v Node vs uložený price_summary (všech 530 sestav)"; $PY batch_node_vs_py.py
echo; echo "### 4) parametrické varianty (rovinný rozklad) + invarianty"; $PY prototyp_parametric_morph.py
echo; echo "### 5) compose_entries bez čtení vrcholů + export variant"; $PY varianty_demo.py
echo; echo "### 6) náhled v kandidátním prohlížeči (offline Chromium)"; node viewer_smoke.js out/shape577_export.glb stul577
