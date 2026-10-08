#!/usr/bin/env python3
"""Robert 2026-10-06: "vestavby sestavy techto 3 modelu a jejich kategorie musime sloucit, tzn ve stromu Vestavby podle auta ty kategorie zmizi jako jednotlive a vytvori se slucena
vcetne 3 log u sebe. a tato kategorie se smaze > /vestavby-pro-ducato-jumper-boxer". Volba Roberta (klik, 2026-10-06): "Presunout stavajici stranku do stromu".

CO SKRIPT DELA (jedna transakce, se zalohou a kontrolou poctu zmenenych radku):
  1) kategorie 233 "Vestavby pro Ducato, Jumper, Boxer" (dnes prazdna, primo pod korenem 184 "Vestavby do dodavek, aut") se PRESUNE pod 267 "Vestavby podle vozidla" (sort_order 0 =
     prvni mezi znackami); slug (/vestavby-pro-ducato-jumper-boxer), jeji text a SEO pole zustavaji - odkazuji na ni ostatni kategorie a ma navstevnost (category_views).
  2) vsechny sestavy Vandr (SKU VD-%) pro Fiat Ducato / Citroen Jumper / Peugeot Boxer dostanou PRIMARNI category_id = 233: dnes 12 v kat. 300 (Fiat Ducato), 95 "Ducato" na urovni znacky
     269 (Fiat), 6 "Jumper" v 268 (Citroen), 3 "Boxer" v 288 (Peugeot) = 116 produktu; testovaci VD-TEST-% a bez kategorie se nechavaji. `active` se NIKDY nemeni (pravidlo 54).
  3) kazda presunuta sestava dostane SEKUNDARNI vazbu (shop_product_categories) na svou znackovou kategorii (Ducato -> 269 Fiat, Jumper -> 268 Citroen, Boxer -> 288 Peugeot), at se
     na strankach znacek porad zobrazuje (slucena kategorie neni jejich potomek, pravidlo 52 dedi jen z potomku).
  4) 301: stary slug "vestavby-pro-fiat-ducato" -> kategorie 233 (content_category_redirects).
  5) kategorie 300 "Vestavby pro Fiat Ducato" se SMAZE (FK CASCADE smaze i jeji content_pages; zaloha je v JSON).
  6) audit_log zaznamy (user_id NULL = skript).
ZALOHA PRED ZMENOU: backups/2026-10-06_slouceni_ducato_jumper_boxer_pred_zmenou.json (kategorie 233 a 300 vcetne textu, primary category_id vsech dotcenych produktu, sekundarni vazby, redirecty).
NAVRAT: python3 scripts/2026-10-06_slouceni_ducato_jumper_boxer.py --rollback backups/2026-10-06_slouceni_ducato_jumper_boxer_pred_zmenou.json

Pouziti:
  python3 scripts/2026-10-06_slouceni_ducato_jumper_boxer.py              # dry-run (jen cteni, vypise plan)
  python3 scripts/2026-10-06_slouceni_ducato_jumper_boxer.py --apply      # zapis
  python3 scripts/2026-10-06_slouceni_ducato_jumper_boxer.py --rollback <zaloha.json>
Testovano nad DOCASNYMI tabulkami (scripts/2026-10-06_slouceni_ducato_jumper_boxer_testy/test_slouceni.py): apply i rollback, do ostre DB se pri testu nezapisuje.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SLOUCENA = 233            # "Vestavby pro Ducato, Jumper, Boxer"
SLOUCENA_SLUG = "vestavby-pro-ducato-jumper-boxer"
PUVODNI_RODIC = 184       # "Vestavby do dodavek, aut" (koren)
CIL_RODIC = 267           # "Vestavby podle vozidla"
DUCATO_KAT = 300          # "Vestavby pro Fiat Ducato" (smaze se)
DUCATO_SLUG = "vestavby-pro-fiat-ducato"
DUCATO_RODIC = 269        # Fiat
ZNACKY = {"Ducato": 269, "Jumper": 268, "Boxer": 288}     # model -> znackova kategorie (Fiat, Citroen, Peugeot): zustane jako sekundarni vazba
OCEKAVANE_POCTY = {"Ducato": 107, "Jumper": 6, "Boxer": 3}  # 12 v kat. 300 + 95 v 269; stav 2026-10-06 - kdyz se lisi, skript se zastavi (nekdo mezitim neco zmenil)
ZALOHA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups", "2026-10-06_slouceni_ducato_jumper_boxer_pred_zmenou.json")


class Chyba(Exception):
    pass


def over(podminka, zprava):
    if not podminka:
        raise Chyba(zprava)


def vyber_produkty(cur):
    """[(id, sku, nazev, kategorie, active, model)] - sestavy Vandr (VD-%, ne VD-TEST-%, ne archivovane) pro 3 modely podle kategorie + nazvu"""
    cur.execute(
        "SELECT id, sku, name, category_id, active FROM shop_products "
        "WHERE sku LIKE 'VD-%%' AND sku NOT LIKE 'VD-TEST-%%' AND COALESCE(is_archived,0)=0 AND ("
        " category_id=%s OR (category_id=269 AND name LIKE '%%Ducato%%') OR (category_id=268 AND name LIKE '%%Jumper%%') OR (category_id=288 AND name LIKE '%%Boxer%%')"
        ") ORDER BY id", (DUCATO_KAT,))
    out = []
    for r in cur.fetchall():
        n = r["name"] or ""
        model = "Ducato" if r["category_id"] == DUCATO_KAT or "Ducato" in n else "Jumper" if "Jumper" in n else "Boxer" if "Boxer" in n else None
        over(model, f"produkt {r['id']} ({n}) nejde zaradit k Ducato/Jumper/Boxer")
        out.append((r["id"], r["sku"], n, r["category_id"], r["active"], model))
    return out


def plan(cur):
    """Overi vychozi stav a vrati plan; vyhodi Chyba, kdyz se stav lisi od ocekavani."""
    cur.execute("SELECT id, parent_id, name, slug, sort_order FROM content_categories WHERE id IN (%s,%s,%s,%s)", (SLOUCENA, DUCATO_KAT, CIL_RODIC, PUVODNI_RODIC))
    kat = {r["id"]: r for r in cur.fetchall()}
    over(SLOUCENA in kat and kat[SLOUCENA]["slug"] == SLOUCENA_SLUG and kat[SLOUCENA]["parent_id"] == PUVODNI_RODIC, "kategorie 233 neni tam, kde se ocekava (slug / rodic 184) - uz nekdo sloucil?")
    over(DUCATO_KAT in kat and kat[DUCATO_KAT]["slug"] == DUCATO_SLUG and kat[DUCATO_KAT]["parent_id"] == DUCATO_RODIC, "kategorie 300 neni tam, kde se ocekava (slug / rodic 269)")
    over(CIL_RODIC in kat, "kategorie 267 Vestavby podle vozidla neexistuje")
    cur.execute("SELECT COUNT(*) AS n FROM content_categories WHERE parent_id=%s", (DUCATO_KAT,))
    over(cur.fetchone()["n"] == 0, "kategorie 300 ma podkategorie - smazani by je smazalo (CASCADE)")
    cur.execute("SELECT COUNT(*) AS n FROM shop_products WHERE category_id=%s", (SLOUCENA,))
    over(cur.fetchone()["n"] == 0, "kategorie 233 uz ma produkty (mela byt prazdna)")
    produkty = vyber_produkty(cur)
    pocty = {m: sum(1 for p in produkty if p[5] == m) for m in ZNACKY}
    over(pocty == OCEKAVANE_POCTY, f"pocty sestav {pocty} se lisi od ocekavanych {OCEKAVANE_POCTY} - nekdo mezitim upravil produkty, skript se zastavuje")
    cur.execute("SELECT COUNT(*) AS n FROM shop_products WHERE category_id=%s", (DUCATO_KAT,))
    over(cur.fetchone()["n"] == sum(1 for p in produkty if p[3] == DUCATO_KAT), "v kat. 300 jsou i produkty mimo vyber (nejsou VD- / jsou archivovane) - po smazani by zustaly viset")
    return {"kategorie": kat, "produkty": produkty, "pocty": pocty}


def zaloha(cur, pl):
    ids = [p[0] for p in pl["produkty"]]
    fm = ",".join(["%s"] * len(ids))
    def radky(sql, args=()):
        cur.execute(sql, args)
        return [{k: (v.isoformat() if isinstance(v, (datetime.datetime, datetime.date)) else (v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else (float(v) if hasattr(v, "as_tuple") else v))) for k, v in r.items()} for r in cur.fetchall()]
    return {
        "vytvoreno": datetime.datetime.now().isoformat(timespec="seconds"),
        "popis": "stav PRED slouceni Ducato/Jumper/Boxer (kategorie 233 + 300 vcetne textu, primarni kategorie dotcenych produktu, sekundarni vazby, redirecty)",
        "content_categories": radky("SELECT * FROM content_categories WHERE id IN (%s,%s)", (SLOUCENA, DUCATO_KAT)),
        "content_pages": radky("SELECT * FROM content_pages WHERE category_id IN (%s,%s)", (SLOUCENA, DUCATO_KAT)),
        "produkty": radky(f"SELECT id, category_id FROM shop_products WHERE id IN ({fm})", ids),
        "sekundarni_vazby": radky(f"SELECT product_id, category_id FROM shop_product_categories WHERE product_id IN ({fm})", ids),
        "redirecty": radky("SELECT old_slug, category_id FROM content_category_redirects WHERE old_slug=%s OR category_id IN (%s,%s)", (DUCATO_SLUG, SLOUCENA, DUCATO_KAT)),
    }


def zapis(cur, pl):
    """vlastni zmeny; po kazdem kroku se kontroluje pocet zmenenych radku (vyhodi Chyba -> volajici udela rollback)"""
    produkty = pl["produkty"]
    ids = [p[0] for p in produkty]
    fm = ",".join(["%s"] * len(ids))
    n = cur.execute("UPDATE content_categories SET parent_id=%s, sort_order=0 WHERE id=%s AND parent_id=%s", (CIL_RODIC, SLOUCENA, PUVODNI_RODIC))
    over(n == 1, f"presun kategorie 233: zmeneno {n} radku (ocekavano 1)")
    n = cur.execute(f"UPDATE shop_products SET category_id=%s WHERE id IN ({fm})", [SLOUCENA] + ids)
    over(n == len(ids), f"presun sestav: zmeneno {n} radku (ocekavano {len(ids)})")
    vazby = [(p[0], ZNACKY[p[5]]) for p in produkty]
    # jeden INSERT s vice radky misto executemany (pymysql executemany posila bytes a _StrazniCursor z scripts/_env.py na nich padne)
    cur.execute("INSERT IGNORE INTO shop_product_categories (product_id, category_id) VALUES " + ",".join(["(%s,%s)"] * len(vazby)), [x for v in vazby for x in v])
    cur.execute(f"SELECT COUNT(*) AS n FROM shop_product_categories WHERE product_id IN ({fm}) AND category_id IN (268,269,288)", ids)
    over(cur.fetchone()["n"] == len(ids), "sekundarni vazby na znackove kategorie se nezapsaly vsechny")
    cur.execute("INSERT INTO content_category_redirects (old_slug, category_id) VALUES (%s,%s) ON DUPLICATE KEY UPDATE category_id=VALUES(category_id), created_at=NOW()", (DUCATO_SLUG, SLOUCENA))
    cur.execute("SELECT COUNT(*) AS n FROM shop_products WHERE category_id=%s", (DUCATO_KAT,))
    over(cur.fetchone()["n"] == 0, "v kategorii 300 jeste zustaly produkty - nemazu")
    n = cur.execute("DELETE FROM content_categories WHERE id=%s AND slug=%s", (DUCATO_KAT, DUCATO_SLUG))
    over(n == 1, f"smazani kategorie 300: smazano {n} radku (ocekavano 1)")
    cur.execute("SELECT COUNT(*) AS n FROM content_category_redirects WHERE old_slug=%s AND category_id=%s", (DUCATO_SLUG, SLOUCENA))
    over(cur.fetchone()["n"] == 1, "redirect na 233 po smazani 300 chybi")
    pocty = pl["pocty"]
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'update','category',%s,%s)",
                (SLOUCENA, f"slouceni Ducato/Jumper/Boxer (Robert 2026-10-06): kategorie presunuta pod {CIL_RODIC}, primarni category_id sestav -> {SLOUCENA}: {json.dumps(pocty)}; sekundarne ve znackovych kategoriich"))
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'delete','category',%s,%s)",
                (DUCATO_KAT, f"Vestavby pro Fiat Ducato - slouceno do {SLOUCENA}, 301 {DUCATO_SLUG} -> {SLOUCENA}"))


def kontrola_po(cur, pl):
    """konecny stav (vraci slovnik pro vypis a testy)"""
    cur.execute("SELECT id, parent_id, sort_order, slug FROM content_categories WHERE id=%s", (SLOUCENA,))
    k = cur.fetchone()
    cur.execute("SELECT COUNT(*) AS n, SUM(active=1) AS aktivnich FROM shop_products WHERE category_id=%s", (SLOUCENA,))
    p = cur.fetchone()
    cur.execute("SELECT COUNT(*) AS n FROM content_categories WHERE id=%s", (DUCATO_KAT,))
    return {"233": k, "produktu_v_233": p["n"], "aktivnich_v_233": int(p["aktivnich"] or 0), "300_existuje": cur.fetchone()["n"]}


def rollback(cur, zal):
    """vrati stav z JSON zalohy (kategorie 300 + jeji text znovu vlozi, produkty zpet, vazby a redirect smaze)"""
    k = {r["id"]: r for r in zal["content_categories"]}
    over(SLOUCENA in k and DUCATO_KAT in k, "zaloha neobsahuje kategorie 233 a 300")
    cur.execute("UPDATE content_categories SET parent_id=%s, sort_order=%s WHERE id=%s", (k[SLOUCENA]["parent_id"], k[SLOUCENA]["sort_order"], SLOUCENA))
    cur.execute("SELECT COUNT(*) AS n FROM content_categories WHERE id=%s", (DUCATO_KAT,))
    if cur.fetchone()["n"] == 0:
        r = k[DUCATO_KAT]
        sloupce = [c for c in r.keys()]
        cur.execute("INSERT INTO content_categories (" + ",".join(f"`{c}`" for c in sloupce) + ") VALUES (" + ",".join(["%s"] * len(sloupce)) + ")", [r[c] for c in sloupce])
        for s in zal["content_pages"]:
            if s["category_id"] == DUCATO_KAT:
                cur.execute("SELECT COUNT(*) AS n FROM content_pages WHERE category_id=%s", (DUCATO_KAT,))
                if cur.fetchone()["n"] == 0:
                    sl = list(s.keys())
                    cur.execute("INSERT INTO content_pages (" + ",".join(f"`{c}`" for c in sl) + ") VALUES (" + ",".join(["%s"] * len(sl)) + ")", [s[c] for c in sl])
    for p in zal["produkty"]:
        cur.execute("UPDATE shop_products SET category_id=%s WHERE id=%s", (p["category_id"], p["id"]))
    pred = {(v["product_id"], v["category_id"]) for v in zal["sekundarni_vazby"]}
    for p in zal["produkty"]:
        for kat in (268, 269, 288):
            if (p["id"], kat) not in pred:
                cur.execute("DELETE FROM shop_product_categories WHERE product_id=%s AND category_id=%s", (p["id"], kat))
    stare = [r for r in zal["redirecty"] if r["old_slug"] == DUCATO_SLUG]
    if not stare:
        cur.execute("DELETE FROM content_category_redirects WHERE old_slug=%s", (DUCATO_SLUG,))
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'update','category',%s,%s)", (SLOUCENA, "navrat slouceni Ducato/Jumper/Boxer ze zalohy (skript --rollback)"))


def main(argv):
    from _env import get_conn
    apply_ = "--apply" in argv
    roll = argv[argv.index("--rollback") + 1] if "--rollback" in argv else None
    conn = get_conn()
    cur = conn.cursor()
    try:
        if roll:
            zal = json.load(open(roll, encoding="utf-8"))
            rollback(cur, zal)
            conn.commit()
            print("rollback hotovy ze zalohy", roll)
            return 0
        pl = plan(cur)
        print(f"Plan: kategorie 233 pod {CIL_RODIC}; sestav k presunu {len(pl['produkty'])} ({pl['pocty']}); 301 {DUCATO_SLUG} -> 233; smazat kategorii 300.")
        akt = sum(1 for p in pl["produkty"] if p[4])
        print(f"  z toho aktivnich {akt} (zustavaji aktivni), neaktivnich {len(pl['produkty']) - akt} (zustavaji neaktivni)")
        if not apply_:
            print("(dry-run - nic nezapsano; spust s --apply)")
            return 0
        os.makedirs(os.path.dirname(ZALOHA), exist_ok=True)
        if os.path.exists(ZALOHA):
            raise Chyba("zaloha uz existuje (" + ZALOHA + ") - uz se slucovalo? smaz/premenuj ji, az to vis jistě")
        z = zaloha(cur, pl)
        with open(ZALOHA, "w", encoding="utf-8") as f:
            json.dump(z, f, ensure_ascii=False, indent=1)
        print("zaloha zapsana:", ZALOHA)
        zapis(cur, pl)
        konec = kontrola_po(cur, pl)
        over(konec["produktu_v_233"] == len(pl["produkty"]) and konec["300_existuje"] == 0 and konec["233"]["parent_id"] == CIL_RODIC, f"kontrola po zapisu selhala: {konec}")
        conn.commit()
        print("ZAPSANO a commitnuto:", json.dumps(konec, default=str))
        return 0
    except Chyba as e:
        conn.rollback()
        print("ZASTAVENO, nic se nezapsalo (rollback):", e)
        return 2
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
