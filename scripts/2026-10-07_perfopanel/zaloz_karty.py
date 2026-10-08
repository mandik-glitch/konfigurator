#!/usr/bin/env python3
"""Zalozeni produktovych karet perforovanych panelu 1481 / 1671 / 1975 mm + GLB do katalogu (bot8, 2026-10-07; Robert: "integruj do generatoru dalsi velikosti perforovanych panelu ...
nejvetsi je 1975 x 460, ten si musis vyrobit"; rozmery po upresneni Roberta 1481 a 1671 mm).

Karty jsou kopie karty 4931 (Perforovany ocelovy panel na naradi 1190 x 460mm: kategorie 200, jednotka ks, material `grey`), jen rozmery v nazvu / SKU / popisu a cena.
Vznikaji NEAKTIVNI (active=0, pravidlo 54 - aktivni ruce nepřepinat), viditelne ve scene (visible_in_scene=1, glb_file): generator si cenu bere z karty
(configurator_price: shop_products WHERE visible_in_scene=1 AND glb_file IS NOT NULL), takze je ocení i neaktivni. CENA je ORIENTACNI (Robert ji nezadal): 1700 Kc (karta 4931) x pomer
plochy panelu k 1190 x 460 mm, zaokrouhleno na 10 Kc; Robert ji upravi v karte. GLB vyrabi gen_perfopanel.py (tvar odmereny na 4931 a na CAD od Roberta; 1975 dorobeno ve stylu 1671).

Id karet = dalsi volna (AUTO_INCREMENT), vlozi se vyslovne; GLB se zapise do webapp/katalog/product_<id>.glb PRED vlozenim karet (kdyz INSERT selze, GLB zustanou - smazat/prejmenovat).
Idempotentni: existuje-li karta s SKU, pouzije se (nic se nepise; GLB se jen dopise, kdyz chybi).

  api/venv/bin/python3 scripts/2026-10-07_perfopanel/zaloz_karty.py                        (nahled, jen cteni)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-07_perfopanel/zaloz_karty.py --apply            (webapp/katalog je guarded: pod zamkem + commit)
Zapis se overuje rowcountem a cteni z NOVEHO spojeni, zaznam do audit_log."""
import os
import sys
import threading

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
apply = "--apply" in sys.argv
import gen_perfopanel as GEN  # noqa: E402

VZOR_ID = 4931
CENA_VZOR = 1700.0
PLOCHA_VZOR = 1190.0 * 460.0
TYPY = (1481, 1671, 1975)


def cena(delka):
    p = GEN.TYPY[delka]
    return "%.2f" % (round(CENA_VZOR * (delka * p["vyska"]) / PLOCHA_VZOR / 10.0) * 10.0)


def texty(delka):
    v = int(GEN.TYPY[delka]["vyska"])
    return {
        "sku": f"Perfopanel.{delka}x{v}.seda",
        "name": f"Perforovaný ocelový panel na nářadí {delka} x {v}mm",
        "description": f"Perforovaný ocelový panel na nářadí o rozměrech {delka} × {v} mm. Volitelné příslušenství pracovních stolů z generátoru stolu; na panel se montuje také elektrožlab.",
        "meta_title": f"Perforovaný panel na nářadí {delka}×{v} mm",
        "meta_description": f"Perforovaný ocelový panel na nářadí {delka} × {v} mm: volitelné příslušenství pracovních stolů z generátoru stolu, na panel lze montovat i elektrožlab.",
    }


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
assert vzor and vzor["sku"] == "Perfopanel.1190x460.seda", "vzorova karta 4931 se zmenila"
cur.execute("SELECT AUTO_INCREMENT AS a FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_products'")
dalsi = int(cur.fetchone()["a"])
skus = [texty(t)["sku"] for t in TYPY]
cur.execute("SELECT id, sku, name, slug, active, glb_file FROM shop_products WHERE sku IN (%s,%s,%s)", tuple(skus))
existujici = {r["sku"]: r for r in cur.fetchall()}
plan = []
nid = dalsi
for t in TYPY:
    sku = texty(t)["sku"]
    if sku in existujici:
        plan.append((t, existujici[sku]["id"], True))
    else:
        plan.append((t, nid, False))
        nid += 1
for t, pid, ex in plan:
    glb = os.path.join(REPO, "webapp", "katalog", f"product_{pid}.glb")
    print(f"panel {t}: karta #{pid} {texty(t)['sku']} cena {cena(t)} Kc bez DPH {'EXISTUJE' if ex else 'bude zalozena (neaktivni)'}; GLB {glb} {'je' if os.path.isfile(glb) else 'bude vyroben'}")
if not apply:
    print(f"\n(nahled, nic nezapsano; dalsi volne id = {dalsi}; zapis: --apply pres systemd-run, viz hlavicka)")
    sys.exit(0)

for t, pid, ex in plan:                                       # 1) GLB do katalogu (pred kartou)
    glb = os.path.join(REPO, "webapp", "katalog", f"product_{pid}.glb")
    if not os.path.isfile(glb):
        info = GEN.vyrob(t, glb)
        print("GLB:", info["soubor"], info["bajtu"], "B,", info["trojuhelniku"], "trojuhelniku, rozmer", info["rozmer"], "vodotesny po svareni overen v testu")
for t, pid, ex in plan:                                       # 2) karty
    if ex:
        continue
    x = texty(t)
    cur.execute(
        "INSERT INTO shop_products (id, category_id, sku, name, slug, description, unit, price_czk_placeholder, stock_qty, active, is_archived, availability_text, price_visible_default, "
        "hover_show_price, hover_show_availability, has_variants, variant_count, has_set_items, glb_file, is_board_material, is_profile_material, visible_in_scene, is_supplier_item, "
        "meta_title, meta_description, place_vertical, attach_offset_mm, nativni_material, render_material_key) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,0,0,%s,%s,%s,%s,0,0,0,%s,0,0,1,0,%s,%s,%s,%s,0,%s)",
        (pid, vzor["category_id"], x["sku"], x["name"], slug_fn(cur, x["name"]), x["description"], vzor["unit"], cena(t), vzor["availability_text"], vzor["price_visible_default"],
         vzor["hover_show_price"], vzor["hover_show_availability"], f"product_{pid}.glb", x["meta_title"], x["meta_description"], vzor["place_vertical"], vzor["attach_offset_mm"],
         vzor["render_material_key"]))
    if cur.rowcount != 1:
        conn.rollback()
        raise SystemExit(f"CHYBA: INSERT karty {x['sku']} rowcount={cur.rowcount} - ROLLBACK")
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                (None, "create", "shop_product", pid, f"bot8: neaktivni karta perforovaneho panelu {t} x {int(GEN.TYPY[t]['vyska'])} mm ({x['sku']}) pro generator stolu (Robert 2026-10-07: dalsi velikosti panelu); "
                                                      f"orientacni cena {cena(t)} Kc bez DPH = poměr plochy ke karte 4931 (1700 Kc), Robert upravi"))
conn.commit()
c2 = appmod.get_conn().cursor()
for t, pid, ex in plan:
    c2.execute("SELECT id, sku, name, slug, active, visible_in_scene, glb_file, price_czk_placeholder, category_id, render_material_key FROM shop_products WHERE id=%s", (pid,))
    r2 = c2.fetchone()
    assert r2 and r2["sku"] == texty(t)["sku"] and r2["glb_file"] == f"product_{pid}.glb" and r2["visible_in_scene"] == 1, r2
    print(f"zapsano a overeno z noveho spojeni: karta #{pid} {r2['sku']} \"{r2['name']}\" (active={r2['active']}, visible_in_scene=1, slug {r2['slug']}, cena {r2['price_czk_placeholder']}, material {r2['render_material_key']})")
print("IDS", {t: pid for t, pid, ex in plan})
