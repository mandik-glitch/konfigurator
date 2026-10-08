#!/usr/bin/env python3
"""Zalozeni produktovych karet pricek (DILY z api/nabidka_pricky.py) + GLB do katalogu (bot8, 2026-10-07; Robert: "multiboxy maji moznost delicich pricek ... v online nabidce nejaky system pro priobjednani
pricek jako prislusenstvi ... at jsou videt ceny"; jen PRICNE pricky, sety vzdy pro celou polici / suplik; v5: "potom i pricky v suplíku", jen ocelove supliky s modrym celem).

Karty (SKU stabilni, podle nich je najde api/nabidka_pricky.py): MBX-PRICKA-PRICNA-186 (pricka do Multiboxu sirky 186 mm), MBX-PRICKA-PRICNA-91 (sirky 91 mm) a (v5) PET dilu pro podnosy
ocelovych supliku SUP-PRICKA-PRICNA-<hloubka>x<vyska> (332x137, 332x210, 384x101, 384x137, 384x210; pricka zepredu dozadu do slotu po 100 mm). Existujici karty se jen pouziji. Karty vznikaji NEAKTIVNI
(active=0, pravidlo 54 - aktivni ruce nepřepinat), bez kategorie (jako karty Multiboxu 3958 / 3959), mimo scenu (visible_in_scene=0; glb_file je jen pro nahled karty), material render `multibox`.
Pricky se verejnosti v online nabidce nabidnou az kdyz jsou OBE karty aktivni; admin je vidi v nabidce driv (odkaz "Zobrazit online"). CENA je ORIENTACNI (Robert ji nezadal): 39 Kc (186 mm)
a 29 Kc (91 mm) bez DPH za kus - Robert ji upravi v karte; cenu bere nabidka ZIVE z karty (price_czk_placeholder).

Id karet = dalsi volna (AUTO_INCREMENT), vlozi se vyslovne; GLB se zapise do webapp/katalog/product_<id>.glb PRED vlozenim karet. Idempotentni: existuje-li karta s SKU, pouzije se (GLB se jen dopise).

  api/venv/bin/python3 scripts/2026-10-07_multibox_pricky/zaloz_karty.py                        (nahled, jen cteni)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-07_multibox_pricky/zaloz_karty.py --apply            (webapp/katalog je guarded: pod zamkem + commit)
Zapis se overuje rowcountem a ctenim z NOVEHO spojeni, zaznam do audit_log."""
import os
import sys
import threading

import trimesh

REPO = os.environ.get("PRICKY_REPO", "/opt/konfigurator")
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.environ.get("PRICKY_API") or os.path.join(REPO, "api"))
apply = "--apply" in sys.argv
import nabidka_pricky as P  # noqa: E402

VZOR_ID = 3958                      # karta Multibox 296x93: jednotka, dostupnost, material a viditelnost ceny se berou odtud


def glb_bytes(klic):
    d = P.DILY[klic]["rozmer"]
    return trimesh.creation.box(extents=list(d)).export(file_type="glb")


def texty(klic):
    d = P.DILY[klic]
    r = d["rozmer"]
    if klic.startswith("ps"):                                     # v5: pricka do oceloveho supliku (hloubka x vyska podnosu)
        hl, vy = klic[2:].split("v")
        return {
            "sku": d["sku"], "name": d["nazev"],
            "description": f"Dělicí příčka do ocelového šuplíku s modrým čelem (hloubka podnosu {hl} mm, výška {vy} mm; rozměr příčky {r[2]:g} × {r[1]:g} × {r[0]:g} mm). Příslušenství šuplíků – v online nabídce se přiobjednává jako set "
                           f"pro celý sloupec šuplíků; příčky jdou zepředu dozadu a zasouvají se do slotů po 100 mm napříč šířkou podnosu (4 / 6 / 9 podle šířky).",
            "meta_title": f"Příčka do šuplíku {hl} × {vy} mm",
            "meta_description": f"Dělicí příčka do ocelového šuplíku (hloubka {hl} mm, výška {vy} mm): příslušenství šuplíků, zasouvá se do slotů po 100 mm.",
        }
    sirka = "186" if klic == "p186" else "91"
    return {
        "sku": d["sku"], "name": d["nazev"],
        "description": f"Dělicí příčka do Multiboxu šířky {sirka} mm (rozměr {r[2]:g} × {r[1]:g} × {r[0]:g} mm). Příslušenství Multiboxů – v online nabídce se přiobjednává jako set pro celou polici nebo šuplík s multiboxy; "
                       f"příčky se zasouvají do slotů (4 / 6 / 8 podle délky boxu).",
        "meta_title": f"Příčka do Multiboxu {sirka} mm",
        "meta_description": f"Dělicí příčka do Multiboxu šířky {sirka} mm: příslušenství Multiboxů, zasouvá se do slotů v boxu.",
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
assert vzor and vzor["sku"] == "multibox_296x93", "vzorova karta 3958 se zmenila"
cur.execute("SELECT AUTO_INCREMENT AS a FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_products'")
dalsi = int(cur.fetchone()["a"])
cur.execute("SELECT id, sku, name, slug, active, glb_file FROM shop_products WHERE sku IN (%s)" % ",".join(["%s"] * len(P.DILY)), tuple(d["sku"] for d in P.DILY.values()))
existujici = {r["sku"]: r for r in cur.fetchall()}
plan, nid = [], dalsi
for klic in P.DILY:
    sku = P.DILY[klic]["sku"]
    if sku in existujici:
        plan.append((klic, existujici[sku]["id"], True))
    else:
        plan.append((klic, nid, False))
        nid += 1
for klic, pid, ex in plan:
    glb = os.path.join(REPO, "webapp", "katalog", f"product_{pid}.glb")
    print(f"{klic}: karta #{pid} {P.DILY[klic]['sku']} cena {P.DILY[klic]['cena0']:g} Kc bez DPH {'EXISTUJE' if ex else 'bude zalozena (neaktivni, bez kategorie)'}; GLB {glb} {'je' if os.path.isfile(glb) else 'bude vyroben'}")
if not apply:
    print(f"\n(nahled, nic nezapsano; dalsi volne id = {dalsi}; zapis: --apply pres systemd-run, viz hlavicka)")
    sys.exit(0)

for klic, pid, ex in plan:                                      # 1) GLB do katalogu (pred kartou)
    glb = os.path.join(REPO, "webapp", "katalog", f"product_{pid}.glb")
    if not os.path.isfile(glb):
        data = glb_bytes(klic)
        with open(glb, "wb") as f:
            f.write(data)
        print("GLB:", glb, len(data), "B")
for klic, pid, ex in plan:                                      # 2) karty
    if ex:
        continue
    x = texty(klic)
    cur.execute(
        "INSERT INTO shop_products (id, category_id, sku, name, slug, description, unit, price_czk_placeholder, stock_qty, active, is_archived, availability_text, price_visible_default, "
        "hover_show_price, hover_show_availability, has_variants, variant_count, has_set_items, glb_file, is_board_material, is_profile_material, visible_in_scene, is_supplier_item, "
        "meta_title, meta_description, place_vertical, attach_offset_mm, nativni_material, render_material_key) "
        "VALUES (%s,NULL,%s,%s,%s,%s,%s,%s,0,0,0,%s,%s,%s,%s,0,0,0,%s,0,0,0,0,%s,%s,%s,%s,0,%s)",
        (pid, x["sku"], x["name"], slug_fn(cur, x["name"]), x["description"], vzor["unit"], "%.2f" % P.DILY[klic]["cena0"], vzor["availability_text"], vzor["price_visible_default"],
         vzor["hover_show_price"], vzor["hover_show_availability"], f"product_{pid}.glb", x["meta_title"], x["meta_description"], vzor["place_vertical"], vzor["attach_offset_mm"],
         vzor["render_material_key"]))
    if cur.rowcount != 1:
        conn.rollback()
        raise SystemExit(f"CHYBA: INSERT karty {x['sku']} rowcount={cur.rowcount} - ROLLBACK")
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                (None, "create", "shop_product", pid, f"bot8: neaktivni karta pricky do {'ocelovych supliku' if klic.startswith('ps') else 'Multiboxu'} ({x['sku']}) pro online nabidku (Robert 2026-10-07: sety pricek pro celou polici / suplik), "
                                                      f"orientacni cena {P.DILY[klic]['cena0']:g} Kc bez DPH, Robert upravi a aktivuje"))
conn.commit()
c2 = appmod.get_conn().cursor()
for klic, pid, ex in plan:
    c2.execute("SELECT id, sku, name, slug, active, visible_in_scene, glb_file, price_czk_placeholder, category_id, render_material_key FROM shop_products WHERE id=%s", (pid,))
    r2 = c2.fetchone()
    assert r2 and r2["sku"] == P.DILY[klic]["sku"] and r2["glb_file"] == f"product_{pid}.glb", r2
    print(f"zapsano a overeno z noveho spojeni: karta #{pid} {r2['sku']} \"{r2['name']}\" (active={r2['active']}, slug {r2['slug']}, cena {r2['price_czk_placeholder']}, material {r2['render_material_key']})")
print("IDS", {k: pid for k, pid, ex in plan})
