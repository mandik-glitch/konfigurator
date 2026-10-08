#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mutacni kontrola testu trasy kontrolni sceny (test_kontrola_route.py): v KANDIDATNIM stromu (kopie api/, symlinky na scripts/ a webapp/)
rozbije jednu vec v trase kontrolni_scena_v3d_model a overi, ze test selze (jinak by dane pravidlo hlidal jen komentar).
"!!!" = test mutaci nechytil (exit 1). Nic se nezapisuje do repa ani do DB. Spusteni: api/venv/bin/python scripts/2026-10-02_v3d_testy/_mutace_kontrola_route.py (~1,5 min)."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TEST = os.path.join(HERE, "test_kontrola_route.py")
PY = sys.executable

MUTACE = [
    ("bez @staff_required (trasa pusti kohokoli)", "@app.get(\"/api/kontrola-scena/v3d/<int:shop_product_id>.glb\")\n@staff_required\n",
     "@app.get(\"/api/kontrola-scena/v3d/<int:shop_product_id>.glb\")\n"),
    ("nekontroluje se SKU VD-", "    if not (karta.get(\"sku\") or \"\").startswith(\"VD-\"):\n        return jsonify({\"error\": \"SKU karty neodpovídá formátu VD-<uuid> - není to Vandr karta.\"}), 400\n    if not karta.get(\"glb_file\"):",
     "    if not karta.get(\"glb_file\"):"),
    ("nekontroluje se glb_file", "    if not karta.get(\"glb_file\"):\n        return jsonify({\"error\": \"Karta ještě nemá hotový 3D model (konverze nedoběhla).\"}), 400\n    if not os.path.isfile(os.path.join(KATALOG_DIR, karta[\"glb_file\"])):",
     "    if not os.path.isfile(os.path.join(KATALOG_DIR, karta[\"glb_file\"] or \"x\")):"),
    ("ignoruje se vypinac v3d-vypnuto", "    if os.path.exists(V3D_VYPNUTO_SOUBOR):\n        return jsonify({\"error\": \"3D model je vypnutý souborem private-files/v3d-vypnuto (smazáním souboru se zapne).\"}), 503\n    try:\n        vandr_data, v3d_duvod = _nacti_vandr_data(karta[\"sku\"][3:], t_start)",
     "    try:\n        vandr_data, v3d_duvod = _nacti_vandr_data(karta[\"sku\"][3:], t_start)"),
    ("v3d_duvod (stara verze Vandr prikazu) se ignoruje", "    if v3d_duvod is not None:\n        return jsonify({\"error\": \"3D model nevznikl: %s\" % v3d_duvod}), 502\n    try:\n        offer_glb, geom = _postav_v3d_model(karta[\"id\"], vandr_data, t_start)",
     "    try:\n        offer_glb, geom = _postav_v3d_model(karta[\"id\"], vandr_data, t_start)"),
    ("vyzaduje cenu karty (jako nabidka)", "    if not karta.get(\"glb_file\"):\n        return jsonify({\"error\": \"Karta ještě nemá hotový 3D model (konverze nedoběhla).\"}), 400\n    if not os.path.isfile(os.path.join(KATALOG_DIR, karta[\"glb_file\"])):\n        return jsonify({\"error\": \"GLB soubor chybí na disku: %s\" % karta[\"glb_file\"]}), 400\n",
     "    if not karta.get(\"glb_file\"):\n        return jsonify({\"error\": \"Karta ještě nemá hotový 3D model (konverze nedoběhla).\"}), 400\n    if not os.path.isfile(os.path.join(KATALOG_DIR, karta[\"glb_file\"])):\n        return jsonify({\"error\": \"GLB soubor chybí na disku: %s\" % karta[\"glb_file\"]}), 400\n    if not conn_cena_ok(karta):\n        return jsonify({\"error\": \"Karta ještě nemá cenu.\"}), 400\n"),
    ("chyba buildu se potichu nahradi (tichy 200)", "    except _V3DNevzniklo as e:\n        return jsonify({\"error\": \"3D model nevznikl: %s\" % e}), 500\n    resp = Response(offer_glb",
     "    except _V3DNevzniklo as e:\n        offer_glb, geom = b\"glTF\" + b\"\\0\" * 60000, {}\n    resp = Response(offer_glb"),
    ("model se znaci forenzni znackou", "    resp = Response(offer_glb, mimetype=\"model/gltf-binary\")\n    resp.headers[\"Cache-Control\"]",
     "    offer_glb = _oznac_model(offer_glb, 0)[0] or offer_glb\n    resp = Response(offer_glb, mimetype=\"model/gltf-binary\")\n    resp.headers[\"Cache-Control\"]"),
    ("bez Cache-Control no-store", "    resp.headers[\"Cache-Control\"] = \"private, no-store\"\n    resp.headers[\"X-V3D-Cache\"]", "    resp.headers[\"X-V3D-Cache\"]"),
    ("rozpocet casu se neposila (t_start = 0)", "def kontrolni_scena_v3d_model(shop_product_id):\n    \"\"\"KONTROLNI SCENA (rezim=nabidka)", "def kontrolni_scena_v3d_model(shop_product_id):\n    \"\"\"KONTROLNI SCENA (rezim=nabidka)"),
    ("zapisuje audit_log", "    resp = Response(offer_glb, mimetype=\"model/gltf-binary\")\n    resp.headers[\"Cache-Control\"]",
     "    log_audit(1, \"v3d_model\", \"shop_product\", karta[\"id\"], {})\n    resp = Response(offer_glb, mimetype=\"model/gltf-binary\")\n    resp.headers[\"Cache-Control\"]"),
]
# casovy rozpocet: t_start v trase = time.time() -> dostane build plny limit (t_start v budoucnosti)
MUTACE[9] = ("casovy rozpocet: t_start v budoucnosti (build dostane vic casu nez smi)", "    t_start = time.time()\n    conn = get_conn()\n    try:\n        with conn.cursor() as cur:\n            cur.execute(\"SELECT id, sku, glb_file, vandr_predni_azimut_deg",
             "    t_start = time.time() + 30\n    conn = get_conn()\n    try:\n        with conn.cursor() as cur:\n            cur.execute(\"SELECT id, sku, glb_file, vandr_predni_azimut_deg")

zdroj = open(os.path.join(REPO, "api", "vandr_scene_offers.py"), encoding="utf-8").read()
vysledky = []
for nazev, a, b in MUTACE:
    if zdroj.count(a) != 1:
        print("CHYBA PRIPRAVY mutace '%s': vzor nalezen %d x" % (nazev, zdroj.count(a)))
        vysledky.append((nazev, None))
        continue
    cand = tempfile.mkdtemp(prefix="mutace_route_")
    try:
        shutil.copytree(os.path.join(REPO, "api"), os.path.join(cand, "api"), ignore=shutil.ignore_patterns("__pycache__", "venv", "*.pyc", "*.sock", "*.log", "*.pid"))
        os.symlink(os.path.join(REPO, "scripts"), os.path.join(cand, "scripts"))
        os.symlink(os.path.join(REPO, "webapp"), os.path.join(cand, "webapp"))
        with open(os.path.join(cand, "api", "vandr_scene_offers.py"), "w", encoding="utf-8") as fh:
            fh.write(zdroj.replace(a, b))
        env = dict(os.environ, V3D_TEST_REPO=cand, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([PY, "-B", TEST], env=env, capture_output=True, text=True, timeout=300)
        vysledky.append((nazev, r.returncode))
        print(("chyceno " if r.returncode != 0 else "!!! NECHYCENO ") + "| " + nazev)
    finally:
        shutil.rmtree(cand, ignore_errors=True)
nechyceno = [n for n, rc in vysledky if rc in (0, None)]
print("\n%d mutaci, chyceno %d, nechyceno/chyba pripravy %d" % (len(MUTACE), len(MUTACE) - len(nechyceno), len(nechyceno)))
sys.exit(1 if nechyceno else 0)
