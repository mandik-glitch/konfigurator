#!/usr/bin/env python3
"""Zalozeni produktovych karet ocelovych supliku s 1 a 3 supliky (bot8, 2026-10-05; Robert odpovedel v generatoru stolu: skutecne vnejsi vysky, SKU a ceny od dodavatele).

  1 suplik : SKU Suplik.ocel.440136   , vyska 180 mm, 3 900 Kc bez DPH   -> "Ocelove supliky 1ks ke stolum"
  2 supliky: SKU Dvojsuplik.ocel.440137 (karta #4930, uz existuje)
  3 supliky: SKU Trojsuplik.ocel.440138, vyska 450 mm, 5 900 Kc bez DPH   -> "Ocelove supliky 3ks ke stolum"

Karty vznikaji NEAKTIVNI (active=0, pravidlo 54 - aktivni ruce nepřepinat), jako 4930 s viditelnosti ve scene (visible_in_scene=1, glb_file) - cena v generatoru se bere z karty
(configurator_price: shop_products WHERE visible_in_scene=1 AND glb_file IS NOT NULL), takze generator je ocení i neaktivni. Pole podle karty 4930 (kategorie 200, jednotka ks,
dostupnost "3 - 5 tydnu", material `bila`). Hmotnost chybi stejne jako u 4930 (kusovnik ji hlasi jako neuplnou).
GLB musi lezet v webapp/katalog/product_<id>.glb PRED zapisem (vyrobi je scripts/2026-10-05_suplik_varianty_final.py s temi samymi id); id karet = dalsi volna (AUTO_INCREMENT) a skript
je vlozi vyslovne (kdyz mezitim nekdo jiny zalozil kartu a id je obsazene, INSERT selze a nic se nezapise - pak GLB prejmenovat na nova id).

  api/venv/bin/python3 scripts/2026-10-05_suplik_karty.py                      (nahled, jen cteni)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-05_suplik_karty.py --apply

Idempotentni: existuje-li uz karta se SKU, pouzije se (nic se nepise). Zapis se overuje rowcountem a cteni z NOVEHO spojeni, zaznam do audit_log."""
import os
import sys
import threading

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
apply = "--apply" in sys.argv

KARTY = [
    {"n": 1, "sku": "Suplik.ocel.440136", "nazev": "Ocelové šuplíky 1ks ke stolům", "cena": "3900.00", "vyska": 180},
    {"n": 3, "sku": "Trojsuplik.ocel.440138", "nazev": "Ocelové šuplíky 3ks ke stolům", "cena": "5900.00", "vyska": 450},
]
VZOR_ID = 4930

if not os.environ.get("DB_HOST"):
    from _env import get_conn  # nahled bez systemd-run (cte jen)
    conn = get_conn()
    slug_fn = None
else:
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    import app as appmod  # noqa: E402
    threading.Thread.start = _o
    conn = appmod.get_conn()
    slug_fn = appmod._product_slug_for_name
cur = conn.cursor()
cur.execute("SELECT * FROM shop_products WHERE id=%s", (VZOR_ID,))
vzor = cur.fetchone()
assert vzor and vzor["sku"] == "Dvojsuplik.ocel.440137", "vzorova karta 4930 se zmenila"
cur.execute("SELECT AUTO_INCREMENT AS a FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_products'")
dalsi = int(cur.fetchone()["a"])
cur.execute("SELECT id, sku, name, slug, active, glb_file FROM shop_products WHERE sku IN (%s,%s)", (KARTY[0]["sku"], KARTY[1]["sku"]))
existujici = {r["sku"]: r for r in cur.fetchall()}
plan = []
nid = dalsi
for k in KARTY:
    if k["sku"] in existujici:
        plan.append((k, existujici[k["sku"]]["id"], True))
    else:
        plan.append((k, nid, False))
        nid += 1
for k, pid, ex in plan:
    glb = os.path.join(REPO, "webapp", "katalog", f"product_{pid}.glb")
    print(f"{k['n']} suplik: karta #{pid} {k['sku']} {'EXISTUJE' if ex else 'bude zalozena (neaktivni)'}; GLB {glb} {'je' if os.path.isfile(glb) else 'CHYBI'}")
if not apply:
    print(f"\n(nahled, nic nezapsano; dalsi volne id = {dalsi}; zapis: --apply pres systemd-run, viz hlavicka)")
    sys.exit(0)

for k, pid, ex in plan:
    if ex:
        continue
    if not os.path.isfile(os.path.join(REPO, "webapp", "katalog", f"product_{pid}.glb")):
        raise SystemExit(f"CHYBA: chybi webapp/katalog/product_{pid}.glb - nejdriv scripts/2026-10-05_suplik_varianty_final.py --id1 .. --id3 ..")
    cur.execute(
        "INSERT INTO shop_products (id, category_id, sku, name, slug, unit, price_czk_placeholder, stock_qty, active, is_archived, availability_text, price_visible_default, "
        "hover_show_price, hover_show_availability, has_variants, variant_count, has_set_items, glb_file, is_board_material, is_profile_material, visible_in_scene, is_supplier_item, "
        "place_vertical, attach_offset_mm, nativni_material, render_material_key) VALUES (%s,%s,%s,%s,%s,%s,%s,0,0,0,%s,%s,%s,%s,0,0,0,%s,0,0,1,0,%s,%s,0,%s)",
        (pid, vzor["category_id"], k["sku"], k["nazev"], slug_fn(cur, k["nazev"]), vzor["unit"], k["cena"], vzor["availability_text"], vzor["price_visible_default"],
         vzor["hover_show_price"], vzor["hover_show_availability"], f"product_{pid}.glb", vzor["place_vertical"], vzor["attach_offset_mm"], vzor["render_material_key"]))
    if cur.rowcount != 1:
        conn.rollback()
        raise SystemExit(f"CHYBA: INSERT karty {k['sku']} rowcount={cur.rowcount} - ROLLBACK")
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                (None, "create", "shop_product", pid, f"bot8: neaktivni karta ocelovych supliku {k['n']} ks ({k['sku']}, vyska {k['vyska']} mm, {k['cena']} Kc bez DPH) pro generator stolu; udaje od Roberta 2026-10-05"))
conn.commit()
c2 = appmod.get_conn().cursor()
for k, pid, ex in plan:
    c2.execute("SELECT id, sku, name, slug, active, visible_in_scene, glb_file, price_czk_placeholder, category_id FROM shop_products WHERE id=%s", (pid,))
    r2 = c2.fetchone()
    assert r2 and r2["sku"] == k["sku"] and r2["active"] == 0 and r2["visible_in_scene"] == 1 and r2["glb_file"] == f"product_{pid}.glb", r2
    print(f"zapsano a overeno z noveho spojeni: karta #{pid} {r2['sku']} \"{r2['name']}\" (active=0, visible_in_scene=1, slug {r2['slug']}, cena {r2['price_czk_placeholder']})")
