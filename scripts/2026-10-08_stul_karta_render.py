#!/usr/bin/env python3
"""Zarazeni otockoveho renderu karty stolu z generatoru (STUL-S<sys>-<hash8>) JAKO DRZITEL RENDEROVACIHO KLICE (bot4, Robert 2026-10-08).
Model se postavi znovu z ulozeneho vyberu S RAZITKY (scripts/stul_karta_glb.py --razitka; kontrola hashe se NEOBCHAZI), celo z extras.v3d.front,
material a pozadi z panelu Rendering.
  seznam                  aktivni karty STUL-S* bez aktivnich snimku otocky a bez davky zarazene v poslednich 6 h
  zaradit ID [ID ...]     zaradi otocku techto karet (bez ID = vsechny ze seznamu)
Nic nemeni v DB (snimky se zapisi po dokonceni ingestem jako u kazde karty); active se NEDOTYKA.
Spusteni (root): api/venv/bin/python3 scripts/2026-10-08_stul_karta_render.py seznam"""
import json
import math
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
import _env  # noqa: E402

os.environ.update(_env.load_env())
CLI = os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py")
GLB_DIR = os.path.join(REPO, "private-files", "blender-renders", "stul_glb")
STAV = os.path.join(REPO, "backups", "2026-10-08_stul_karty_rendery", "joby.json")
KLIC = "/root/.konfigurator_render_klic"
SQL = ("SELECT sp.id, sp.sku FROM shop_products sp WHERE sp.active=1 AND sp.sku REGEXP '^STUL-S(30|35|40|41|45)-[0-9a-f]{8}$' "
       "AND NOT EXISTS (SELECT 1 FROM product_turntable_frames f WHERE f.shop_product_id=sp.id AND f.is_active=1) ORDER BY sp.id")


def stav():
    try:
        return json.load(open(STAV, encoding="utf-8"))
    except (OSError, ValueError):
        return {"joby": []}


def ulozit(st):
    os.makedirs(os.path.dirname(STAV), exist_ok=True)
    json.dump(st, open(STAV, "w", encoding="utf-8"), indent=1)


def kandidati():
    c = _env.get_conn()
    try:
        with c.cursor() as cur:
            cur.execute(SQL)
            radky = cur.fetchall()
    finally:
        c.close()
    ve_fronte = {j["karta"] for j in stav()["joby"] if time.time() - j["zarazeno"] < 6 * 3600}
    return [r for r in radky if r["id"] not in ve_fronte]


def zarad(karta, sku):
    import stul_karta_glb as G
    moduly = G._nacti_moduly()
    c = moduly[0].get_conn()
    try:
        with c.cursor() as cur:
            raw, info = G.postav(cur, karta, razitka=True, moduly=moduly)      # CliChyba (hash nesedi apod.) = nezaradit
    finally:
        c.rollback()
        c.close()
    os.makedirs(GLB_DIR, exist_ok=True)
    cesta = os.path.join(GLB_DIR, "%s_razitka.glb" % sku)
    G.zapis_atomicky(cesta, raw)
    fx, fz = info["front"][0], info["front"][2]
    az_otocky = (math.degrees(math.atan2(-fz, fx)) + 90.0) % 360.0        # scena -> otocka, viz azimut_sceny_na_otocku
    import _render_prirazeni_lib as lib
    c = _env.get_conn()
    try:
        with c.cursor() as cur:
            panel = list(lib.nacti_nastaveni_pro_automat(cur))
    finally:
        c.close()
    env = dict(os.environ, KONFIGURATOR_RENDER_KLIC_SOUBOR=KLIC, BOT_ID="bot4")
    env.pop("KONFIGURATOR_NABIDKA_Z_API", None)
    p = subprocess.run([sys.executable, CLI, "--shop-product-id", str(karta), "--glb-override", cesta,
                        "--predni-azimut", repr(az_otocky)] + panel, env=env, capture_output=True, text=True, timeout=600)
    print((p.stdout + p.stderr)[-900:])
    if p.returncode != 0:
        raise SystemExit("zarazeni karty %s selhalo (kod %s)" % (karta, p.returncode))
    st = stav()
    st["joby"].append({"karta": karta, "sku": sku, "zarazeno": time.time(), "predni_azimut": az_otocky})
    ulozit(st)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "seznam"
    k = kandidati()
    if cmd == "seznam":
        print("karet stolu k renderu: %d" % len(k))
        for r in k:
            print("  %d %s" % (r["id"], r["sku"]))
    elif cmd == "zaradit":
        ids = [int(x) for x in sys.argv[2:]]
        for r in k:
            if not ids or r["id"] in ids:
                zarad(r["id"], r["sku"])


if __name__ == "__main__":
    main()
