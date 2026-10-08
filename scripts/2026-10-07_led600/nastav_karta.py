#!/usr/bin/env python3
"""Nastaveni modelu karty LED 600 (#5359, SKU LED600) - bot8, 2026-10-07; Robert: "pridal jsem nove LED 600, do karty, udelej mu 3D model zkracenim LED 1200" a "pridej to do generatoru".

Model: webapp/katalog/product_5359.glb (zkracena LED 1200, viz led_zkrat.py; stejna souradnicova soustava a stred jako product_4929.glb). Skript nastavi na karte glb_file + visible_in_scene=1 (jako LED 1200)
a OPRAVI texty zkopirovane z LED 1200 (1,2 m / 33 W / 3960 lm -> 600 mm / 16 W / 1920 lm; jen kdyz jsou presne puvodni zkopirovane - Robert je mohl mezitim upravit). `active` se NEMENI (pravidlo 54).
Zapis: porovnej-a-nastav (WHERE glb_file IS NULL ...), rowcount, kontrola z noveho spojeni, audit_log (s puvodnimi hodnotami textu).

  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-07_led600/nastav_karta.py [--apply]        (bez --apply jen cte a vypise plan)"""
import os
import sys
import threading

REPO = "/opt/konfigurator"
os.chdir(REPO)
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
sys.path.insert(0, REPO + "/api")
try:
    import app as appmod
finally:
    threading.Thread.start = _o

PID, VZOR = 5359, 4929
apply = "--apply" in sys.argv
GLB = f"product_{PID}.glb"
NAHRADY = (("délky 1,2 m", "délky 600 mm"), ("příkon 33 W", "příkon 16 W"), ("3960 lm", "1920 lm"), ("1,2 m 33 W", "600 mm 16 W"))


def oprav(t):
    for a, b in NAHRADY:
        t = t.replace(a, b)
    return t


conn = appmod.get_conn()
cur = conn.cursor()
cur.execute("SELECT id, sku, name, glb_file, visible_in_scene, active, description, meta_title, meta_description FROM shop_products WHERE id=%s", (PID,))
k = cur.fetchone()
cur.execute("SELECT description, meta_title, meta_description, visible_in_scene FROM shop_products WHERE id=%s", (VZOR,))
v = cur.fetchone()
conn.rollback()
assert k and k["sku"] == "LED600", k
if not os.path.isfile(os.path.join(REPO, "webapp", "katalog", GLB)):
    sys.exit(f"CHYBA: chybi webapp/katalog/{GLB} (GLB musi existovat PRED nastavenim karty)")
nove = {c: (oprav(k[c]) if k[c] == v[c] else k[c]) for c in ("description", "meta_title", "meta_description")}      # prepsat jen texty shodne se zkopirovanymi z LED 1200
print(f"karta #{PID} {k['sku']} \"{k['name']}\": glb_file {k['glb_file']!r} -> {GLB!r}, visible_in_scene {k['visible_in_scene']} -> 1, active {k['active']} (beze zmeny)")
for c in nove:
    print(f"  {c}: {'BEZE ZMENY' if nove[c] == k[c] else 'oprava'}\n     {k[c][:150]!r}\n  -> {nove[c][:150]!r}")
if not apply:
    sys.exit(0)
if k["glb_file"] is not None or k["visible_in_scene"]:
    sys.exit("karta uz ma glb_file / visible_in_scene - nic nezapisuji")
cur.execute("UPDATE shop_products SET glb_file=%s, visible_in_scene=1, description=%s, meta_title=%s, meta_description=%s "
            "WHERE id=%s AND sku='LED600' AND glb_file IS NULL AND visible_in_scene=0 AND description=%s AND meta_title=%s AND meta_description=%s",
            (GLB, nove["description"], nove["meta_title"], nove["meta_description"], PID, k["description"], k["meta_title"], k["meta_description"]))
if cur.rowcount != 1:
    conn.rollback()
    sys.exit(f"CHYBA: UPDATE rowcount={cur.rowcount} (karta se mezitim zmenila) - ROLLBACK")
cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
            (None, "update", "shop_product", PID, "bot8: LED600 - model product_5359.glb (zkracena LED 1200, scripts/2026-10-07_led600), visible_in_scene=1, opraveny texty zkopirovane z LED 1200; "
                                                    f"puvodni description={k['description']!r}, meta_title={k['meta_title']!r}, meta_description={k['meta_description']!r}"))
conn.commit()
c2 = appmod.get_conn().cursor()
c2.execute("SELECT glb_file, visible_in_scene, active, description, meta_title FROM shop_products WHERE id=%s", (PID,))
r = c2.fetchone()
assert r["glb_file"] == GLB and r["visible_in_scene"] == 1 and r["active"] == k["active"] and r["description"] == nove["description"], r
print("zapsano a overeno z noveho spojeni:", {kk: (str(vv)[:90]) for kk, vv in r.items()})
