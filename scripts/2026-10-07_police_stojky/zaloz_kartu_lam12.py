#!/usr/bin/env python3
"""Zalozeni karty LAMINOVANE DREVOTRISKY 12 mm (bot8, fork 3, 2026-10-07; Robert: "u 30/35 krome laminodesky 18mm i 12mm") + GLB 1000 x 1000 x 12 mm do katalogu. Karta 12 mm v katalogu NEEXISTUJE.

Karta je kopie karty 4933 (Laminovana drevotriska 18mm: kategorie 207, jednotka m2, tabule 2070 x 2800, material `laminodeska`), jen tloustka v nazvu / SKU / popisu a cena. Vznika NEAKTIVNI
(active=0, pravidlo 54 - aktivni ruce nepřepinat), viditelna ve scene (visible_in_scene=1, glb_file): generator si cenu bere z karty (configurator_price: visible_in_scene=1 AND glb_file), takze ji ocení
i neaktivni; VEREJNOSTI se deska 12 mm nabidne az po aktivaci karty (stul_shop.karty_police_verejne). CENA je ORIENTACNI (Robert ji nezadal): 1 050 Kc/m2 bez DPH (~81 % ceny 18 mm = 1 300) - Robert upravi.
GLB vyrabi glb_lam12.py (kvadr 1000 x 1000 x 12, osa Z = tloustka, vycentrovany - stejna soustava jako MDF 8 / PR10 / deska 18).

VYCHOZI = NAHLED (jen cteni, nic se nezapisuje). Zapis (az po schvaleni, pod zamkem - webapp/katalog je guarded) JEN s --apply:
  api/venv/bin/python3 scripts/2026-10-07_police_stojky/zaloz_kartu_lam12.py                      (nahled)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-07_police_stojky/zaloz_kartu_lam12.py --apply          (tiskne ID karty; to se preda apply.sh jako --lam12-id)
Idempotentni: existuje-li karta se SKU Laminodeska.SEDA.12, pouzije se (nic se nepise; GLB se jen dopise, kdyz chybi). Zapis se overuje rowcountem a cteni z NOVEHO spojeni, zaznam do audit_log."""
import os
import sys
import threading

REPO = "/opt/konfigurator"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, HERE)
apply = "--apply" in sys.argv
import glb_lam12  # noqa: E402

VZOR_ID, SKU, CENA = 4933, "Laminodeska.SEDA.12", "1050.00"
NAZEV = "Laminovaná dřevotříska 12mm"
POPIS = ("Laminovaná dřevotříska tloušťky 12 mm, prodej na m². Slouží jako deska police stolů z hliníkových profilů (polici shora pokládáme na rám z profilů); "
         "nosnou funkci mají profily.")
META_T = "Laminovaná dřevotříska 12 mm – deska ke stolům"
META_D = "Laminovaná dřevotříska tloušťky 12 mm, prodej na m²: deska police stolů z hliníkových profilů, nosnou funkci mají profily a deska se na ně pokládá shora."

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
assert vzor and vzor["sku"] == "Laminodeska.SEDA.18", "vzorova karta 4933 se zmenila"
cur.execute("SELECT AUTO_INCREMENT AS a FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_products'")
dalsi = int(cur.fetchone()["a"])
cur.execute("SELECT id, sku, name, slug, active, glb_file FROM shop_products WHERE sku=%s", (SKU,))
ex = cur.fetchone()
pid = ex["id"] if ex else dalsi
glb = os.path.join(REPO, "webapp", "katalog", f"product_{pid}.glb")
print(f"deska 12 mm: karta #{pid} {SKU} \"{NAZEV}\" cena {CENA} Kc/m2 bez DPH (ORIENTACNI) {'EXISTUJE (active=%s)' % ex['active'] if ex else 'bude zalozena NEAKTIVNI'}; kategorie {vzor['category_id']}, tabule {vzor['board_sheet_width_mm']} x {vzor['board_sheet_height_mm']}; "
      f"GLB {glb} {'je' if os.path.isfile(glb) else 'bude vyroben (1000 x 1000 x 12 mm)'}")
print(f"-> apply.sh predat --lam12-id {pid}")
if not apply:
    print(f"\n(nahled, nic nezapsano; dalsi volne id = {dalsi}; zapis: --apply pres systemd-run, viz hlavicka)")
    sys.exit(0)
if not os.path.isfile(glb):                                   # 1) GLB do katalogu (pred kartou)
    glb_lam12.zapis(glb, *glb_lam12.kvadr())
    print("GLB zapsano:", glb)
if not ex:                                                    # 2) karta (neaktivni)
    cur.execute(
        "INSERT INTO shop_products (id, category_id, sku, name, slug, description, unit, price_czk_placeholder, stock_qty, active, is_archived, availability_text, price_visible_default, "
        "hover_show_price, hover_show_availability, has_variants, variant_count, has_set_items, glb_file, color_hex, is_board_material, board_sheet_width_mm, board_sheet_height_mm, "
        "is_profile_material, visible_in_scene, is_supplier_item, meta_title, meta_description, place_vertical, attach_offset_mm, nativni_material, render_material_key) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,0,0,%s,%s,%s,%s,0,0,0,%s,%s,1,%s,%s,0,1,0,%s,%s,%s,%s,0,%s)",
        (pid, vzor["category_id"], SKU, NAZEV, slug_fn(cur, NAZEV), POPIS, vzor["unit"], CENA, vzor["availability_text"], vzor["price_visible_default"], vzor["hover_show_price"],
         vzor["hover_show_availability"], f"product_{pid}.glb", vzor["color_hex"], vzor["board_sheet_width_mm"], vzor["board_sheet_height_mm"], META_T, META_D, vzor["place_vertical"],
         vzor["attach_offset_mm"], vzor["render_material_key"]))
    if cur.rowcount != 1:
        conn.rollback()
        raise SystemExit(f"CHYBA: INSERT karty {SKU} rowcount={cur.rowcount} - ROLLBACK")
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                (None, "create", "shop_product", pid, f"bot8: neaktivni karta laminodesky 12 mm ({SKU}) pro horni polici generatoru stolu (Robert 2026-10-07); orientacni cena {CENA} Kc/m2 bez DPH, Robert upravi"))
    conn.commit()
c2 = appmod.get_conn().cursor()
c2.execute("SELECT id, sku, name, slug, active, visible_in_scene, glb_file, price_czk_placeholder, category_id, render_material_key FROM shop_products WHERE id=%s", (pid,))
r2 = c2.fetchone()
assert r2 and r2["sku"] == SKU and r2["glb_file"] == f"product_{pid}.glb" and r2["visible_in_scene"] == 1, r2
print(f"zapsano a overeno z noveho spojeni: karta #{pid} {r2['sku']} \"{r2['name']}\" (active={r2['active']}, slug {r2['slug']}, cena {r2['price_czk_placeholder']}, material {r2['render_material_key']})")
print("LAM12_ID", pid)
