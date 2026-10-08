#!/usr/bin/env python3
"""KARTY VYPLNI generatoru OCHRANNY KRYT A OPLOCENI - nahled a zapis (bot8, 2026-10-08, faze 2).

Generator pocita vyplne (polykarbonat cira / kourova, plexisklo, svarovana sit, plna vyplne z hlinikoveho kompozitu) jako VIRTUALNI desky `navrh:<typ>` s ORIENTACNI cenou za m2
(oploceni_konfigurator.VYPLNE). V katalogu zadna karta takove desky zatim NENI (jsou jen drzaky plexiskla a tesneni na sklo). Skript:
  * BEZ prepinace jen CTE (DB se nemeni) a vypise navrh 5 NEAKTIVNICH karet desek (is_board_material=1, jednotka m2, cena orientacni bez DPH): SKU, nazev, popis, rozmer tabule, tloustku, GLB,
    existujici karty se stejnym SKU;
  * S `--apply` karty ZALOZI (idempotentne: karta se stejnym SKU se pouzije) a zapise mapovani typ -> id karty do app_settings `oploceni_karty_vyplni` - TIM SE CENA VYPLNI PREPNE z virtualnich desek
    na karty (oploceni_cena.cena bere product_<id> misto navrh:<typ>, jen kdyz je karta v cenovem kontextu), BEZ ZMENY KODU a API (cache cen 60-120 s). Ceny karet pak upravi Robert v adminu.
    Volitelne `--kategorie <id>` = kategorie karet (vychozi: zadna, jako karty konfigurovatelnych produktu; kategorie existuje-li, overi se).
Karty vznikaji NEAKTIVNI (active=0, pravidlo 54), viditelne ve scene (visible_in_scene=1 + glb_file = cenovy kontext bere jen takove) a s GLB 1000 x 1000 x tloustka (kvadr jako laminodesky; osa Z =
tloustka) v webapp/katalog/product_<id>.glb (GUARDED slozka: zapis jen pod zamkem). Zapis je jedna transakce; selze-li cokoli, ROLLBACK a vytvorene GLB se smazou. Po zapisu se cte z DB a overuje:
karty, soubory GLB, mapovani a ze jsou karty v cenovem kontextu (configurator_price.load_ctx).
Logika zapisu (`nacti_existujici`, `zapis`, `over_zapis`) je v funkcich bez vlastniho pripojeni - test_oploceni_karty.py ji zkousi proti FALESNE DB (zadny dotaz na produkcni DB).

  api/venv/bin/python3 scripts/2026-10-08_oploceni/zaloz_karty_vyplni.py                      (nahled, jen cte)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-08_oploceni/zaloz_karty_vyplni.py --apply [--kategorie <id>]       (zapis; pod zamkem, az po nasazeni kodu faze 2)
"""
import json
import os
import sys
import threading
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
import oploceni_konfigurator as O  # noqa: E402

VZOR_ID, VZOR_SKU = 4933, "Laminodeska.SEDA.18"             # laminodeska 18 mm: vzor poli (dostupnost, zobrazeni ceny, ...)
KLIC = "oploceni_karty_vyplni"
KATALOG = os.environ.get("OPLOCENI_KATALOG") or os.path.join(REPO, "webapp", "katalog")
# typ vyplne -> (nazev karty, tabule sirka x vyska mm, popis, barva pro vyber)
KARTY = {
    "pc_cira": ("Polykarbonátová deska čirá 4mm", (2050, 3050),
                "Polykarbonátová (PC) deska čirá, tloušťka 4 mm, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj desky se zasouvá do drážky profilu v těsnění na sklo.", "#d4e6ee"),
    "pc_koura": ("Polykarbonátová deska kouřová 4mm", (2050, 3050),
                 "Polykarbonátová (PC) deska kouřově šedá, tloušťka 4 mm, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj desky se zasouvá do drážky profilu v těsnění na sklo.", "#2c2c30"),
    "plexi": ("Plexisklo čiré 5mm", (2050, 3050),
              "Plexisklo (akrylátové sklo) čiré, tloušťka 5 mm, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj desky se zasouvá do drážky profilu v těsnění na sklo.", "#dbe8ee"),
    "sit": ("Svařovaná síť pozinkovaná – výplň do drážky", (1000, 2000),
            "Svařovaná pozinkovaná síť (drát 2–3 mm, oko 25 × 25 mm) ve formátu tabule, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj tabule se zasouvá do drážky profilu v měkkém těsnění.", "#8a8d91"),
    "plna": ("Hliníkový kompozitní panel 3mm", (1500, 3050),
             "Plná výplň z hliníkového kompozitního panelu (2 × 0,3 mm hliník, plastové jádro), tloušťka 3 mm, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj panelu se zasouvá do drážky profilu v měkkém těsnění.", "#a0a4a8"),
}
KATEGORIE_NAVRH = "nová podkategorie „Výplně krytů a oplocení“ pod kat. 149 (Hliníkové stavebnicové profily) nebo pod 150 (Příslušenství profilů, kde jsou Držáky plexiskla a Krycí lišty) - rozhodne Robert"


def nacti_existujici(cur):
    """(dalsi volne ID karty, {typ: [existujici karty se stejnym SKU]}, [radky vypisu]): jen cte."""
    cur.execute("SELECT AUTO_INCREMENT AS a FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_products'")
    dalsi = int(cur.fetchone()["a"])
    existujici, radky = {}, [f"{'typ':9s} {'SKU':22s} {'cena Kc/m2':>10s} {'tloustka':>8s} {'tabule mm':>12s}  nazev  [existuje?]"]
    for typ, (nazev, (tw, th), popis, _barva) in KARTY.items():
        info = O.VYPLNE[typ]
        cur.execute("SELECT id, sku, name, active FROM shop_products WHERE sku=%s OR name=%s", (info["sku"], nazev))
        ex = cur.fetchall()
        existujici[typ] = [r for r in ex if r["sku"] == info["sku"]]
        stav = "NE" if not ex else "ANO: " + ", ".join(f"#{r['id']} {r['sku']} (active={r['active']})" for r in ex)
        radky.append(f"{typ:9s} {info['sku']:22s} {info['cena_m2']:10.0f} {info['tloustka']:6.0f}mm {tw:5d}x{th:<5d}  {nazev}  [{stav}]")
        radky.append(f"          popis: {popis}")
    return dalsi, existujici, radky


def radek_karty(typ, kategorie, vzor, slug):
    """Sloupce INSERTu karty vyplne `typ` (OrderedDict sloupec -> hodnota); `vzor` = radek vzorove karty (dostupnost, zobrazeni ceny)."""
    nazev, (tw, th), popis, barva = KARTY[typ]
    info = O.VYPLNE[typ]
    return OrderedDict([("category_id", kategorie), ("sku", info["sku"]), ("name", nazev), ("slug", slug), ("description", popis), ("unit", "m2"),
                        ("price_czk_placeholder", f"{info['cena_m2']:.2f}"), ("stock_qty", 0), ("active", 0), ("is_archived", 0), ("availability_text", vzor["availability_text"]),
                        ("price_visible_default", vzor["price_visible_default"]), ("hover_show_price", vzor["hover_show_price"]), ("hover_show_availability", vzor["hover_show_availability"]),
                        ("has_variants", 0), ("variant_count", 0), ("has_set_items", 0), ("color_hex", barva), ("is_board_material", 1), ("board_sheet_width_mm", tw), ("board_sheet_height_mm", th),
                        ("is_profile_material", 0), ("visible_in_scene", 1), ("is_supplier_item", 0), ("meta_title", nazev + " – výplň krytů a oplocení"), ("meta_description", popis[:300]),
                        ("place_vertical", vzor["place_vertical"]), ("attach_offset_mm", vzor["attach_offset_mm"]), ("nativni_material", 0), ("render_material_key", None)])


def zapis(conn, cur, slug_fn, katalog, kategorie, existujici, glb_zapis):
    """Zapis v JEDNE transakci (commit na konci; pri jakekoli chybe rollback, smazani vytvorenych GLB a RuntimeError): -> {typ: id karty}. `glb_zapis(cesta, tloustka_mm)` vytvori soubor GLB desky."""
    vytvorene_soubory = []
    try:
        cur.execute("SELECT * FROM shop_products WHERE id=%s", (VZOR_ID,))
        vzor = cur.fetchone()
        if not vzor or vzor["sku"] != VZOR_SKU:
            raise RuntimeError(f"vzorova karta #{VZOR_ID} se zmenila (ocekavano SKU {VZOR_SKU})")
        if kategorie is not None:
            cur.execute("SELECT id FROM content_categories WHERE id=%s", (kategorie,))
            if not cur.fetchone():
                raise RuntimeError(f"kategorie #{kategorie} neexistuje")
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s FOR UPDATE", (KLIC,))
        row = cur.fetchone()
        puvodni = row["setting_value"] if row else None
        mapovani = json.loads(puvodni) if puvodni else {}
        nove_karty = {}
        for typ in KARTY:
            info = O.VYPLNE[typ]
            if existujici[typ]:
                nove_karty[typ] = existujici[typ][0]["id"]
                continue
            sl = radek_karty(typ, kategorie, vzor, slug_fn(cur, KARTY[typ][0]))
            cur.execute("INSERT INTO shop_products (" + ", ".join(sl) + ") VALUES (" + ", ".join(["%s"] * len(sl)) + ")", tuple(sl.values()))
            if cur.rowcount != 1:
                raise RuntimeError(f"INSERT karty {info['sku']} rowcount={cur.rowcount}")
            pid = cur.lastrowid
            glb = os.path.join(katalog, f"product_{pid}.glb")
            glb_zapis(glb, float(info["tloustka"]))
            vytvorene_soubory.append(glb)
            cur.execute("UPDATE shop_products SET glb_file=%s WHERE id=%s", (f"product_{pid}.glb", pid))
            if cur.rowcount != 1:
                raise RuntimeError(f"UPDATE glb_file karty #{pid} rowcount={cur.rowcount}")
            cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                        (None, "create", "shop_product", pid, f"bot8: neaktivni karta vyplne krytu a oploceni ({info['sku']}), orientacni cena {info['cena_m2']:.2f} Kc/m2 bez DPH, Robert upravi (2026-10-08)"))
            nove_karty[typ] = pid
        nove_mapovani = dict(mapovani, **nove_karty)
        if nove_mapovani != mapovani:
            nova = json.dumps(nove_mapovani, sort_keys=True)
            if puvodni is None:
                cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s)", (KLIC, nova))
            else:
                cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s AND setting_value=%s", (nova, KLIC, puvodni))
            if cur.rowcount != 1:
                raise RuntimeError(f"zapis {KLIC} rowcount={cur.rowcount} (hodnota se mezitim zmenila?)")
            cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                        (None, "update", "app_settings", None, f"bot8: {KLIC} = {nova} (puvodne: {puvodni}); cena vyplni oploceni se bere z karet"))
        conn.commit()
        return nove_karty
    except Exception as e:                                              # noqa: BLE001 - nic se nezapise napul
        conn.rollback()
        for f in vytvorene_soubory:
            try:
                os.remove(f)
            except OSError:
                pass
        raise RuntimeError(f"{e} - ROLLBACK (vytvorene GLB smazany), nic se nezapsalo") from e


def over_zapis(cur2, nove_karty, katalog, load_ctx):
    """Overeni po commitu (`cur2`): karty (neaktivni, deska, ve scene, GLB), soubory GLB, mapovani a ze jsou karty v cenovem kontextu (`load_ctx(cur2)`). -> mapovani z DB."""
    cur2.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC,))
    mapa_db = json.loads(cur2.fetchone()["setting_value"])
    ctx = load_ctx(cur2)
    for typ, pid in nove_karty.items():
        cur2.execute("SELECT id, sku, active, is_board_material, visible_in_scene, glb_file, unit FROM shop_products WHERE id=%s", (pid,))
        k = cur2.fetchone()
        assert k and k["sku"] == O.VYPLNE[typ]["sku"] and k["active"] == 0 and k["is_board_material"] == 1 and k["visible_in_scene"] == 1 and k["glb_file"] == f"product_{pid}.glb" and mapa_db.get(typ) == pid, (typ, k, mapa_db)
        assert os.path.isfile(os.path.join(katalog, k["glb_file"])), k["glb_file"]
        assert f"product_{pid}" in ctx["parts"] and ctx["parts"][f"product_{pid}"].get("is_board_material"), f"karta #{pid} neni v cenovem kontextu"
    return mapa_db


def pripoj():
    """(get_conn, slug_fn): v systemd-run s DB_* z .env pres app.py, jinak (nahled) pres scripts/_env.py."""
    if not os.environ.get("DB_HOST"):
        from _env import get_conn  # noqa: E402  (nahled bez systemd-run, jen cte)
        return get_conn, None
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    import app as appmod  # noqa: E402
    threading.Thread.start = _o
    return appmod.get_conn, appmod._product_slug_for_name


def main(argv):
    apply = "--apply" in argv
    kategorie = int(argv[argv.index("--kategorie") + 1]) if "--kategorie" in argv else None
    get_conn, slug_fn = pripoj()
    conn = get_conn()
    cur = conn.cursor()
    print(("ZAPIS" if apply else "NAVRH") + " 5 NEAKTIVNICH karet vyplni (is_board_material=1, jednotka m2, ceny ORIENTACNI bez DPH)\n")
    dalsi, existujici, radky = nacti_existujici(cur)
    print("\n".join(radky))
    print("\nspolecne: unit=m2, is_board_material=1, active=0 (pravidlo 54), visible_in_scene=1 + glb_file=product_<id>.glb (kvadr 1000 x 1000 x tloustka, glb_lam12.kvadr; cenovy kontext bere jen karty s GLB),")
    print("          render_material_key=NULL (Blender material pro rendery nabidky urci Robert / bot10), kategorie: " + (f"#{kategorie}" if kategorie else KATEGORIE_NAVRH))
    print(f"dalsi volne ID karty = {dalsi} (karty by dostaly {dalsi}..{dalsi + len(KARTY) - 1}, pokud mezitim nikdo nezalozi jinou)")
    print("po zapisu se cena vyplni bere z karet (app_settings " + KLIC + " = {typ: id}), bez zmeny kodu; ceny karet pak upravi Robert v adminu")
    if not apply:
        print("\n(nahled, nic nezapsano - zapis: --apply pres systemd-run, viz hlavicka)")
        return 0
    if slug_fn is None:
        print("CHYBA: --apply jen pres systemd-run s DB_* z api/.env (viz hlavicka)")
        return 2
    sys.path.insert(0, os.path.join(REPO, "scripts", "2026-10-07_police_stojky"))
    try:
        import glb_lam12  # noqa: E402
    except ImportError as e:
        print(f"CHYBA: chybi scripts/2026-10-07_police_stojky/glb_lam12.py ({e})")
        return 1
    import configurator_price  # noqa: E402
    try:
        nove_karty = zapis(conn, cur, slug_fn, KATALOG, kategorie, existujici, lambda cesta, tl: glb_lam12.zapis(cesta, *glb_lam12.kvadr(1000.0, 1000.0, tl)))
    except RuntimeError as e:
        print(f"CHYBA: {e}")
        return 1
    mapa_db = over_zapis(get_conn().cursor(), nove_karty, KATALOG, configurator_price.load_ctx)
    for typ, pid in nove_karty.items():
        print(f"zapsano a overeno po commitu: {typ} -> karta #{pid} {O.VYPLNE[typ]['sku']} (active=0, glb product_{pid}.glb, v cenovem kontextu)")
    print(f"{KLIC} = {json.dumps(mapa_db, sort_keys=True)}")
    print("KARTY_VYPLNI", json.dumps(nove_karty, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
