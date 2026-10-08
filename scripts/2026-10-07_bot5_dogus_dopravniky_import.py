#!/opt/konfigurator/api/venv/bin/python
"""Import zakladnich dilu jednoduchych dopravniku BEZ POHONU z Dogusu (bot5, 2026-10-07; zadani Robert pres bot9: "vse krome elektrickych komponent a navaznych").

FAZE 2 = `--kategorie` / `--produkty` [`--apply`] (viz blok nize; bez --apply je to dry-run v transakci s rollbackem).
FAZE 1 = `--report`: jen CTENI z Dogusu (GET verejnych stranek) + jen CTENI z nasi DB (co uz existuje) -> JSON v backups/ a textovy prehled; nic se nezapisuje. Faze 2 (`--apply`: nove karty
NEAKTIVNI, pravidlo 54) se prida az po schvaleni reportu Robertem (rozsah, hranice vyrazeni, cilove kategorie).

Zdroj dat, parser a crawl funkce: scripts/2026-08-11_dogus_dynamic_shelving_import.py (NACITAJI se beze zmeny, jako u importu srouboveho zbozi 2026-10-04).
Kategorie (ID Dogus): VSE z 161 Roller Conveyor Systems, 195 Idle Rollers, 190 Plastics Roller Head, 191 Bottom Return Roller Bearings, 217 Roller Rails, 198 Connection Plates,
199 Angular Joints and Rolls, 200 Angular Metal Feet, 201 Triple Feet Group, 202 Conveyor U-Plate, 204 Consol Fittings, 203 Side Barrier Profile and Friction Plastics, 230 Ball Transfer Units,
227 Transport Trolleys, 99 Wheels, 160 Flat-Belt, 162 Elevator, 163 Special, 221 90 Transfer. NE: 205 Sensor Fittings, 197 Torque Arms, 193 Tension & Drive Plates, 194 Tension & Drive Drums.
Uvnitr vybranych kategorii se vyrazuje pohon/elektrika: skupina 1320 drive-roller-conveyors, retezova kola 3831/5397, 7000 ball-screw-desktop-carriage; u pasovych dopravniku (160/162/163/221)
se kazda skupina PRIZNAKOVE kontroluje (motor, napeti, vykon, otacky, senzor ...) - priznaky jdou do reportu, rozhodnuti o vyrazeni je explicitni (seznam skupin VYRADIT_SKUPINY nize).
Uz existujici dily (SKU = Dogus Stock Code) se oznaci "existuje" a nevytvareji se znovu.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_bot5_dogus_dopravniky_import.py --report
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("dogus_import_base", os.path.join(HERE, "2026-08-11_dogus_dynamic_shelving_import.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

KATEGORIE = {  # Dogus ID -> (nazev, skupina rozhodnuti)
    "161": "Roller Conveyor Systems", "195": "Idle Rollers", "190": "Plastics Roller Head", "191": "Bottom Return Roller Bearings", "217": "Roller Rails",
    "198": "Connection Plates", "199": "Angular Joints and Rolls", "200": "Angular Metal Feet", "201": "Triple Feet Group", "202": "Conveyor U-Plate", "204": "Consol Fittings",
    "203": "Side Barrier Profile and Friction Plastics", "230": "Ball Transfer Units", "227": "Transport Trolleys", "99": "Wheels",
    "160": "Flat-Belt", "162": "Elevator", "163": "Special", "221": "90 Transfer",
}
PASOVE = ("160", "162", "163", "221")                       # kompletni pasove dopravniky: kontrola pohonu/elektriky podle stranky produktu
VYRADIT_SKUPINY = {                                         # explicitni vyrazeni skupin (Dogus product ID -> duvod); rozsiri se po schvaleni reportu
    "1320": "drive-roller-conveyors = pohon",
}
HRANICE_OVERIT = ("3831", "5397", "7000")                   # retezova kola (pohon valecku) a ball-screw carriage: overit, zda jsou v nekter z kategorii
POHON_RE = re.compile(r"\b(motor|motorized|driven|drive|reducer|gear ?box|geared|kw|voltage|volt|power|frequency|inverter|electric\w*|sensor|photocell|rpm|chain|sprocket|ball[- ]?screw)\b", re.I)
UA_DELAY = M.REQUEST_DELAY_S


def fetch_retry(fn, *a, tries=4):
    for pokus in range(tries):
        try:
            return fn(*a)
        except Exception as e:                                   # noqa: BLE001 - sit
            print(f"  pokus {pokus + 1}/{tries} {a}: {e}", file=sys.stderr)
            time.sleep(3 * (pokus + 1))
    sys.exit(f"CHYBA: {a} se nepodarilo nacist, crawl neni uplny")


def crawl():
    out = {}
    for cid, nazev in KATEGORIE.items():
        prods = fetch_retry(M.discover_products, f"/Urunler/{cid}/x")
        print(f"[{cid}] {nazev}: {len(prods)} skupin produktu", file=sys.stderr)
        skupiny = []
        for pid, href in prods:
            variants, render, schema = fetch_retry(M.parse_product, href)
            skupiny.append({"group_id": pid, "href": href, "render": render, "schema": schema, "variants": variants})
        out[cid] = {"nazev": nazev, "skupiny": skupiny}
    return out


def priznaky(skupina):
    """Radky/hodnoty specifikaci skupiny, ktere vypadaji na pohon/elektriku (pro lidskou kontrolu)."""
    nalezy = set()
    text = skupina["href"].rsplit("/", 1)[-1]
    for m in POHON_RE.finditer(text):
        nalezy.add(f"nazev: {m.group(0).lower()}")
    for v in skupina["variants"][:400]:
        for k, hod in (v["specs"] or {}).items():
            if k in ("Stock Code",):
                continue
            for m in POHON_RE.finditer(f"{k} {hod}"):
                nalezy.add(f"{k}={str(hod)[:25]} ({m.group(0).lower()})")
    return sorted(nalezy)[:12]


def vyhodnot(data, existujici_sku):
    radky, vyrazeno, prehled = [], [], []
    nalezene_hranice = {}
    for cid, k in data.items():
        for s in k["skupiny"]:
            gid = s["group_id"]
            if gid in HRANICE_OVERIT:
                nalezene_hranice[gid] = (cid, s["href"], len(s["variants"]))
            flagy = priznaky(s)
            duvod = VYRADIT_SKUPINY.get(gid)
            kody = [v["stock_code"] for v in s["variants"]]
            nove = [c for c in kody if c not in existujici_sku]
            prehled.append({"kategorie": cid, "kategorie_nazev": k["nazev"], "group_id": gid, "slug": s["href"].rsplit("/", 1)[-1], "variant": len(kody), "existuje_v_db": len(kody) - len(nove),
                            "nove": len(nove), "vyrazeno": duvod, "priznaky_pohonu": flagy, "pasovy": cid in PASOVE,
                            "stock_name_vzorek": s["variants"][0]["stock_name"] if s["variants"] else None})
            (vyrazeno if duvod else radky).append((cid, gid, len(kody)))
    return prehled, nalezene_hranice


# ======================================================================================================================================================================
# FAZE 2 (--kategorie / --produkty): schvaleno Robertem 2026-10-07 (rozsah 188 dilu bez 7000 klik v okne bot9; strom kategorii klik v okne bot5 i bot7). Nove karty NEAKTIVNI (pravidlo 54),
# kategorie nove SKRYTE (is_visible=0; texty a zviditelneni bot7), obe faze jedna transakce s kontrolou poctu radku, zaloha dotcenych radku do backups/.
# ======================================================================================================================================================================
TOP = ("Dopravníky bez pohonu", "dopravniky-bez-pohonu")
DETI = (("Válečkové dopravníky", "valeckove-dopravniky"), ("Válečky a hlavice válečků", "valecky-a-hlavice-valecku"), ("Podvozky a nohy dopravníků", "podvozky-a-nohy-dopravniku"),
        ("Spoje a konzoly dopravníků", "spoje-a-konzoly-dopravniku"), ("Boční vodítka dopravníků", "bocni-voditka-dopravniku"), ("Kuličkové přepravní jednotky", "kulickove-prepravni-jednotky"))
PRESUN = {225: ("Válečkové dráhy", 156), 264: ("Dopravníkové profily", 149)}          # id -> (ocekavany nazev, ocekavany puvodni rodic)
PREJMENOVAT = (214, "Pojezdové kola", "Pojezdová kola")                           # id, puvodni nazev, novy nazev (slug beze zmeny)
KOEFICIENT, SALE_UNIT = "1.200", "kus"                                            # jako sousedni kategorie 150/157/191/263 (Robert upravi)
VYRADIT_SKU = {"3.012.04": "dil motoroveho vytahoveho dopravniku (bot7)", "2.3.004.100.02": "zdroj bez udaju: nosnost, material, hmotnost (bot7)"}
SLUG_EXISTUJICI = {"valeckove-drahy": 225, "pojezdova-kola": 214}                  # nase_kategorie z dokumentu bot7, ktera uz existuje
NAZVY_SOUBOR = os.path.join(REPO, "docs", "dopravniky_nazvy_popisy_2026-10-07.json")
CENY_SOUBOR = os.path.join(REPO, "backups", "2026-10-07_dogus_dopravniky_ceny_jednotky.json")
CRAWL_SOUBOR = os.path.join(REPO, "backups", "2026-10-07_dogus_dopravniky_crawl.json")


def nacti_radky(nazvy=NAZVY_SOUBOR, ceny=CENY_SOUBOR, crawl=CRAWL_SOUBOR):
    """Radky k importu: texty z dokumentu bot7 (nazev, popis, hmotnost, cilova kategorie) + specifikace/adresy/obrazky z crawlu + cena/jednotka z prihlaseneho cteni. ->(radky, vyrazeno)
    Cenu pocita noc (dogus_url + dogus_stock_code); polozky BEZ pouzitelne ceny (Dogus 0,00 USD) nebo s DELKOVOU jednotkou (6000/2500 mm - nocni prepocet umi jen kus/3 m/metraz) se na Dogus
    NEnavazou (dogus_url = NULL), aby jim noc nezapsala spatnou cenu; zustanou "cena na dotaz" do rozhodnuti Roberta."""
    doc = json.load(open(nazvy, encoding="utf-8"))
    cn = json.load(open(ceny, encoding="utf-8"))
    cr = json.load(open(crawl, encoding="utf-8"))
    info = {}
    for cid, k in cr.items():
        for g in k["skupiny"]:
            for v in g["variants"]:
                info[v["stock_code"]] = {"specs": v["specs"], "href": g["href"], "render": g["render"], "schema": g["schema"]}
    radky, vyrazeno = [], []
    for x in doc["polozky"]:
        if x["sku"] in VYRADIT_SKU:
            vyrazeno.append((x["sku"], VYRADIT_SKU[x["sku"]]))
            continue
        i, c = info[x["sku"]], cn[x["sku"]]
        cena, unit = c.get("cena_usd"), c.get("unit")
        bez_cenoveho_navazani = None
        if not cena:
            bez_cenoveho_navazani = "Dogus List Price 0,00 USD (cena na dotaz)"
        elif unit not in (None, "0"):
            bez_cenoveho_navazani = f"delkova jednotka prodeje {unit} mm (nocni prepocet ji neumi)"
        radky.append({"sku": x["sku"], "name": x["name"], "description": x["description"], "weight_g": x.get("weight_g"), "kategorie_slug": x["nase_kategorie"], "specs": i["specs"],
                      "dogus_url": None if bez_cenoveho_navazani else M.BASE + i["href"], "dogus_url_zdroj": M.BASE + i["href"], "render": i["render"], "schema": i["schema"],
                      "bez_cenoveho_navazani": bez_cenoveho_navazani})
    if len({r["sku"] for r in radky}) != len(radky) or len({r["name"] for r in radky}) != len(radky):
        raise SystemExit("CHYBA: duplicitni SKU nebo nazev v dokumentu")
    return radky, vyrazeno


def strom_zapis(cur, zalohuj=None):
    """Zalozi strom + presuny + prejmenovani (nekomituje). -> {slug: id}. zalohuj(rows) dostane puvodni radky dotcenych kategorii."""
    cur.execute("SELECT * FROM content_categories WHERE id IN (%s,%s,%s)", (*PRESUN.keys(), PREJMENOVAT[0]))
    puvodni = {r["id"]: r for r in cur.fetchall()}
    for kid, (nazev, rodic) in PRESUN.items():
        if kid not in puvodni or puvodni[kid]["name"] != nazev or puvodni[kid]["parent_id"] != rodic:
            raise SystemExit(f"CHYBA: kategorie {kid} neni '{nazev}' pod {rodic} ({puvodni.get(kid) and (puvodni[kid]['name'], puvodni[kid]['parent_id'])}) - nekdo ji mezitim zmenil")
    pk = puvodni.get(PREJMENOVAT[0])
    if not pk or pk["name"] != PREJMENOVAT[1]:
        raise SystemExit(f"CHYBA: kategorie {PREJMENOVAT[0]} neni '{PREJMENOVAT[1]}'")
    slugy = [TOP[1]] + [d[1] for d in DETI]
    cur.execute("SELECT slug FROM content_categories WHERE slug IN (" + ",".join(["%s"] * len(slugy)) + ")", slugy)
    if cur.fetchall():
        raise SystemExit("CHYBA: nektery ze slugu noveho stromu uz existuje - strom se nezaklada podruhe")
    if zalohuj:
        zalohuj(list(puvodni.values()))
    cur.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM content_categories WHERE parent_id IS NULL")
    poradi = cur.fetchone()["n"]
    cur.execute("INSERT INTO content_categories (parent_id, name, slug, sort_order, is_visible, nav_label) VALUES (NULL,%s,%s,%s,0,%s)", (TOP[0], TOP[1], poradi, TOP[0]))
    top_id = cur.lastrowid
    ids = {TOP[1]: top_id}
    for n, (nazev, slug) in enumerate(DETI):
        cur.execute("INSERT INTO content_categories (parent_id, name, slug, sort_order, is_visible, nav_label, dogus_price_coefficient, dogus_sale_unit) VALUES (%s,%s,%s,%s,0,%s,%s,%s)",
                    (top_id, nazev, slug, n, nazev, KOEFICIENT, SALE_UNIT))
        ids[slug] = cur.lastrowid
    for n, kid in enumerate(PRESUN):
        r = cur.execute("UPDATE content_categories SET parent_id=%s, sort_order=%s WHERE id=%s AND parent_id=%s", (top_id, len(DETI) + n, kid, PRESUN[kid][1]))
        if r != 1:
            raise SystemExit(f"CHYBA: presun kategorie {kid} zmenil {r} radku (ocekavan 1)")
        ids[puvodni[kid]["slug"]] = kid
    r = cur.execute("UPDATE content_categories SET name=%s, nav_label=IF(nav_label=%s,%s,nav_label) WHERE id=%s AND name=%s", (PREJMENOVAT[2], PREJMENOVAT[1], PREJMENOVAT[2], PREJMENOVAT[0], PREJMENOVAT[1]))
    if r != 1:
        raise SystemExit(f"CHYBA: prejmenovani kategorie {PREJMENOVAT[0]} zmenilo {r} radku")
    ids.update(SLUG_EXISTUJICI)              # nase_kategorie z dokumentu bot7 ("pojezdova-kola") -> #214, jejiz skutecny slug je (beze zmeny) "pojezdove-kola"
    for kid in (225, PREJMENOVAT[0]):                     # sousedni kategorie maji koeficient 1,2 / kus; prazdnou hodnotu doplnit (nocni prepocet bez koeficientu cenu nepocita)
        cur.execute("UPDATE content_categories SET dogus_price_coefficient=%s, dogus_sale_unit=%s WHERE id=%s AND dogus_price_coefficient IS NULL", (KOEFICIENT, SALE_UNIT, kid))
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'create','category',%s,%s)",
                (top_id, f"strom Dopravniky bez pohonu (Robert 2026-10-07): top-level {top_id}, podkategorie {[ids[d[1]] for d in DETI]}, presun {list(PRESUN)} pod {top_id}, prejmenovana {PREJMENOVAT[0]}; vse skryte (is_visible=0), koeficient {KOEFICIENT}/{SALE_UNIT}"))
    return ids


def produkty_zapis(cur, radky, kat_ids):
    """INSERT novych NEAKTIVNICH karet (existujici SKU se preskoci). Nekomituje. -> [(id, radek)]"""
    cur.execute("SELECT sku FROM shop_products WHERE sku IN (" + ",".join(["%s"] * len(radky)) + ")", [r["sku"] for r in radky])
    existuje = {x["sku"] for x in cur.fetchall()}
    cur.execute("SELECT slug FROM shop_products WHERE slug IS NOT NULL")
    taken = {x["slug"] for x in cur.fetchall()}
    vytvoreno = []
    for r in radky:
        if r["sku"] in existuje:
            continue
        kid = kat_ids.get(r["kategorie_slug"])
        if kid is None:
            raise SystemExit(f"CHYBA: cilova kategorie '{r['kategorie_slug']}' neexistuje")
        slug = M._unique_product_slug(cur, M._slugify(r["name"]), taken)
        taken.add(slug)
        cur.execute("""INSERT INTO shop_products (category_id, sku, name, slug, description, unit, active, is_archived, manufacturer, is_profile_material, dogus_url, dogus_stock_code,
                       dogus_image_render_url, dogus_image_schema_url, product_specs_json, dogus_matched_at, price_visible_default, weight_g, visible_in_scene)
                       VALUES (%s,%s,%s,%s,%s,'ks',0,0,'Dogus',0,%s,%s,%s,%s,%s,NOW(),0,%s,0)""",
                    (kid, r["sku"], r["name"], slug, r["description"], r["dogus_url"], r["sku"] if r["dogus_url"] else None, r["render"], r["schema"],
                     json.dumps(r["specs"], ensure_ascii=False), r["weight_g"]))
        if cur.rowcount != 1:
            raise RuntimeError(f"INSERT {r['sku']} nezapsal radek")
        vytvoreno.append((cur.lastrowid, r))
    return vytvoreno


def obrazky_zapis(conn, vytvoreno, stahni=None, img_dir_tpl=None, chown=True):
    """Obrazky karet (schema, render; stejna URL jen jednou; soubor se stahuje jednou na URL a pro dalsi karty se kopiruje). -> (ok, chyb)"""
    import shutil
    stahni = stahni or M.download_image
    img_dir_tpl = img_dir_tpl or M.IMG_DIR_TPL
    ok = bad = 0
    cache = {}
    with conn.cursor() as cur:
        for pid, r in vytvoreno:
            d = img_dir_tpl.format(id=pid)
            os.makedirs(d, exist_ok=True)
            cur.execute("SELECT source_url, sort_order FROM shop_product_images WHERE product_id=%s", (pid,))
            uz = cur.fetchall()                                   # opakovani po vypadku spojeni: uz ulozene obrazky se nedublují
            seen, order = {x["source_url"] for x in uz}, (max([x["sort_order"] for x in uz]) + 1 if uz else 0)
            for url in (r["schema"], r["render"]):
                if not url or url in seen:
                    continue
                seen.add(url)
                fn = f"{order + 1}{os.path.splitext(M.urllib.parse.urlsplit(url).path)[1] or '.jpg'}"
                cil = os.path.join(d, fn)
                try:
                    if url in cache and os.path.exists(cache[url]):
                        shutil.copyfile(cache[url], cil)
                    else:
                        stahni(url, cil)
                        cache[url] = cil
                except Exception as e:                                        # noqa: BLE001
                    print(f"  CHYBA obrazek {pid}: {e}", file=sys.stderr)
                    bad += 1
                    continue
                cur.execute("INSERT INTO shop_product_images (product_id, filename, source_url, sort_order) VALUES (%s,%s,%s,%s)", (pid, f"products/{pid}/{fn}", url, order))
                ok += 1
                order += 1
    conn.commit()
    if chown:
        import grp
        import pwd
        uid, gid = pwd.getpwnam("www-data").pw_uid, grp.getgrnam("www-data").gr_gid
        for pid, _ in vytvoreno:
            d = img_dir_tpl.format(id=pid)
            if os.path.isdir(d):
                os.chown(d, uid, gid)
                for f in os.listdir(d):
                    os.chown(os.path.join(d, f), uid, gid)
    return ok, bad


def faze2(a):
    radky, vyrazeno = nacti_radky()
    print(f"K importu {len(radky)} dilu; vyrazeno {vyrazeno}; bez cenoveho navazani: {sum(1 for r in radky if r['bez_cenoveho_navazani'])}", file=sys.stderr)
    conn = M.get_db_conn()
    try:
        with conn.cursor() as cur:
            zaloha = os.path.join(REPO, "backups", "2026-10-07_dopravniky_kategorie_pred_zmenou.json")
            ids = {}
            if a.kategorie:
                def zalohuj(rows):
                    if os.path.exists(zaloha):
                        raise SystemExit(f"CHYBA: zaloha {zaloha} uz existuje - strom se uz zakladal?")
                    if a.apply:
                        json.dump(rows, open(zaloha, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
                ids = strom_zapis(cur, zalohuj)
                print("strom:", ids, file=sys.stderr)
            else:
                cur.execute("SELECT id, slug FROM content_categories WHERE slug IN (" + ",".join(["%s"] * (len(DETI) + 1)) + ")", [d[1] for d in DETI] + [TOP[1]])
                ids = {x["slug"]: x["id"] for x in cur.fetchall()}
                ids.update(SLUG_EXISTUJICI)
            vytvoreno = produkty_zapis(cur, radky, ids) if a.produkty else []
            if a.produkty:
                print(f"karet k vytvoreni/vytvoreno: {len(vytvoreno)}", file=sys.stderr)
                from collections import Counter
                print("  po kategoriich:", dict(Counter(r["kategorie_slug"] for _, r in vytvoreno)), file=sys.stderr)
            if not a.apply:
                conn.rollback()
                print("(dry-run: nic nezapsano; --apply pro zapis)", file=sys.stderr)
                return
            cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'create','shop_product',NULL,%s)",
                        (f"import Dogus dopravniky bez pohonu (Robert 2026-10-07): {len(vytvoreno)} NEAKTIVNICH karet, id {[i for i, _ in vytvoreno][:5]}...{[i for i, _ in vytvoreno][-3:]}",)) if vytvoreno else None
        conn.commit()
    finally:
        conn.close()
    if vytvoreno:
        json.dump([{"id": i, "sku": r["sku"], "slug_kategorie": r["kategorie_slug"], "bez_cenoveho_navazani": r["bez_cenoveho_navazani"]} for i, r in vytvoreno],
                  open(os.path.join(REPO, "backups", "2026-10-07_dopravniky_vytvorene_karty.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        conn = M.get_db_conn()
        try:
            ok, bad = obrazky_zapis(conn, vytvoreno)
        finally:
            conn.close()
        print(f"Obrazky: {ok} ulozeno, {bad} chyb.", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="crawl + porovnani s DB, JSON do backups/, nic se nezapisuje")
    ap.add_argument("--from-json", help="misto crawlu nacist drive ulozeny JSON")
    ap.add_argument("--kategorie", action="store_true", help="FAZE 2: zalozit strom kategorii + presuny + prejmenovani (skryte)")
    ap.add_argument("--produkty", action="store_true", help="FAZE 2: naimportovat nove NEAKTIVNI karty (kategorie musi existovat)")
    ap.add_argument("--apply", action="store_true", help="u faze 2: skutecny zapis (bez nej dry-run)")
    ap.add_argument("--doplnit-obrazky", action="store_true", help="dostahnout chybejici obrazky uz vytvorenych karet (po vypadku spojeni s Dogusem)")
    a = ap.parse_args()
    if a.doplnit_obrazky:
        radky, _ = nacti_radky()
        po_sku = {r["sku"]: r for r in radky}
        vytv = json.load(open(os.path.join(REPO, "backups", "2026-10-07_dopravniky_vytvorene_karty.json"), encoding="utf-8"))
        conn = M.get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, sku FROM shop_products WHERE id IN (" + ",".join(["%s"] * len(vytv)) + ")", [v["id"] for v in vytv])
                sku_podle_id = {x["id"]: x["sku"] for x in cur.fetchall()}
            ok, bad = obrazky_zapis(conn, [(i, po_sku[sku]) for i, sku in sku_podle_id.items()])
        finally:
            conn.close()
        print(f"Obrazky doplneny: {ok} ulozeno, {bad} chyb.", file=sys.stderr)
        return
    if a.kategorie or a.produkty:
        return faze2(a)
    if not a.report:
        sys.exit("pouzij --report, nebo faze 2: --kategorie / --produkty [--apply]")
    zaloha = os.path.join(REPO, "backups", "2026-10-07_dogus_dopravniky_crawl.json")
    if a.from_json:
        data = json.load(open(a.from_json, encoding="utf-8"))
    else:
        data = crawl()
        os.makedirs(os.path.dirname(zaloha), exist_ok=True)
        json.dump(data, open(zaloha, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("crawl ulozen:", zaloha, file=sys.stderr)
    sys.path.insert(0, HERE)
    from _env import get_conn
    conn = get_conn()
    cur = conn.cursor()
    kody = sorted({v["stock_code"] for k in data.values() for s in k["skupiny"] for v in s["variants"]})
    existujici = set()
    for i in range(0, len(kody), 500):
        part = kody[i:i + 500]
        cur.execute("SELECT sku FROM shop_products WHERE sku IN (" + ",".join(["%s"] * len(part)) + ")", part)
        existujici |= {r["sku"] for r in cur.fetchall()}
    cur.execute("SELECT id, name, parent_id FROM content_categories WHERE id IN (264,191,99,157,192,263,97,52) OR name LIKE '%opravn%' OR name LIKE '%alec%' OR name LIKE '%kol%' OR name LIKE '%dopravn%'")
    nase_kat = cur.fetchall()
    conn.rollback()
    conn.close()
    prehled, hranice = vyhodnot(data, existujici)
    out = {"prehled": prehled, "hranice": hranice, "nase_kategorie": nase_kat, "celkem_variant": len(kody), "existuje_v_db": len(existujici)}
    json.dump(out, open(os.path.join(REPO, "backups", "2026-10-07_dogus_dopravniky_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"Celkem skupin {len(prehled)}, variant (stock code) {len(kody)}, uz v DB {len(existujici)}")
    for r in prehled:
        print(f"[{r['kategorie']:>3}] {r['kategorie_nazev'][:30]:30} #{r['group_id']:>5} {r['slug'][:38]:38} var {r['variant']:3} nove {r['nove']:3} {'VYRADIT:' + r['vyrazeno'] if r['vyrazeno'] else ''} {'; '.join(r['priznaky_pohonu'][:4]) if r['priznaky_pohonu'] else ''}")
    print("hranice (3831/5397/7000):", hranice)
    print("nase kategorie:", [(c["id"], c["name"], c["parent_id"]) for c in nase_kat])


if __name__ == "__main__":
    main()
