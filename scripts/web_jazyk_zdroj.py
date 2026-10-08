#!/usr/bin/env python3
"""Zdroj k prekladu HLAVNIHO webu do dalsich jazyku (en = vandrawee.eu, it = vandrawee.it). bot7, Robert 2026-10-08.

Z produkcni DB (jen SELECT) vytahne zakaznicky viditelne texty hlavniho webu a zapise je jako sesity
Polozka: {id, typ (text | html), cs, en, it, h, [zmena]}.
  id   = <tabulka>:<pk>:<pole> (kat = content_categories, str = content_pages, kar = shop_products, dom = homepage/sidebar, typ = typologie, gal = galerie, obch = doprava/platba, nast = app_settings)
  h    = sha1(cs)[:10] v okamziku prekladu; zmeni-li se cs, preklad ZUSTANE a polozka dostane "zmena": true (nutno znovu zkontrolovat)
  odkazy v HTML: href="/<slug>" -> href="@cat:<id kategorie>" (resolver doplni lokalizovanou cestu, preklad odkaz nemeni)
Opakovane spusteni je bezpecne: hotove preklady a rucni upravy zustanou, pridaji se nove polozky, zmizele se vypisou jako zastarale.

Pouziti (z korene repa, potrebuje api/.env pro cteni DB; nic se nezapisuje):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      /opt/konfigurator/api/venv/bin/python3 scripts/web_jazyk_zdroj.py [--vsechny-karty]
Kontrola a sestaveni: scripts/web_jazyk_kontrola.py. Postup: docs/web_jazyky/README.md.
"""
import argparse
import hashlib
import json
import os
import re
import sys

import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VYSTUP = os.path.join(ROOT, "docs", "web_jazyky")
JAZYKY = ("en", "it")


def spoj():
    return pymysql.connect(host=os.environ.get("DB_HOST", "localhost"), user=os.environ["DB_USER"],
                           password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def hsh(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]


def najdi(cur, sql):
    cur.execute(sql)
    return cur.fetchall()


def odkazy(html, slug2id):
    """href=\"/slug\" -> href=\"@cat:ID\" (jen odkazy na kategorie; nezname zustanou beze zmeny a hlasi se)."""
    nezname = []

    def r(m):
        slug = m.group(1)
        if slug in slug2id:
            return 'href="@cat:%d"' % slug2id[slug]
        nezname.append(slug)
        return m.group(0)

    return re.sub(r'href="/([a-z0-9-]+)"', r, html), nezname


def sber(cur, vsechny_karty):
    nezname = []
    sady = {k: [] for k in ("01_kategorie", "02_stranky", "03_karty", "04_homepage", "05_typologie", "06_galerie", "07_obchod", "09_nastaveni")}
    nezname = []
    kat = najdi(cur, "SELECT id, slug FROM content_categories")
    slug2id = {r["slug"]: r["id"] for r in kat}

    def pridej(sada, tbl, pk, pole, hodnota, typ="text"):
        if hodnota is None or not str(hodnota).strip():
            return
        h = str(hodnota)
        if typ == "html":
            h, nz = odkazy(h, slug2id)
            nezname.extend((tbl, pk, pole, s) for s in nz)
        sady[sada].append({"id": "%s:%s:%s" % (tbl, pk, pole), "typ": typ, "cs": h})

    for r in najdi(cur, "SELECT id,name,nav_label,menu_group_label,meta_title,meta_description,focus_keyword FROM content_categories ORDER BY id"):
        for p in ("name", "nav_label", "menu_group_label", "meta_title", "meta_description", "focus_keyword"):
            pridej("01_kategorie", "kat", r["id"], p, r[p])
    for r in najdi(cur, "SELECT category_id,title,intro_html,body_html,bottom_body_html FROM content_pages ORDER BY category_id"):
        pridej("02_stranky", "str", r["category_id"], "title", r["title"])
        for p in ("intro_html", "body_html", "bottom_body_html"):
            pridej("02_stranky", "str", r["category_id"], p, r[p], "html")
    kde = "" if vsechny_karty else "WHERE active=1 AND is_archived=0"
    for r in najdi(cur, "SELECT id,name,short_description,description,meta_title,meta_description,availability_text FROM shop_products %s ORDER BY id" % kde):
        for p in ("name", "short_description", "description", "meta_title", "meta_description", "availability_text"):
            pridej("03_karty", "kar", r["id"], p, r[p])
    for r in najdi(cur, "SELECT id,title,meta_description,body_html FROM homepage_blocks ORDER BY id"):
        pridej("04_homepage", "dom", "blok%d" % r["id"], "title", r["title"])
        pridej("04_homepage", "dom", "blok%d" % r["id"], "meta_description", r["meta_description"])
        pridej("04_homepage", "dom", "blok%d" % r["id"], "body_html", r["body_html"], "html")
    for r in najdi(cur, "SELECT id,caption_text FROM homepage_carousel_slides ORDER BY id"):
        pridej("04_homepage", "dom", "slide%d" % r["id"], "caption_text", r["caption_text"])
    for r in najdi(cur, "SELECT id,title,meta_description,body_html FROM sidebar_blocks ORDER BY id"):
        pridej("04_homepage", "dom", "bocni%d" % r["id"], "title", r["title"])
        pridej("04_homepage", "dom", "bocni%d" % r["id"], "meta_description", r["meta_description"])
        pridej("04_homepage", "dom", "bocni%d" % r["id"], "body_html", r["body_html"], "html")
    for r in najdi(cur, "SELECT id,nazev,popis_html FROM content_typologie WHERE aktivni=1 ORDER BY id"):
        pridej("05_typologie", "typ", r["id"], "nazev", r["nazev"])
        pridej("05_typologie", "typ", r["id"], "popis_html", r["popis_html"], "html")
    for r in najdi(cur, "SELECT id,nazev,popis_zakaznicky FROM typologie_varianty WHERE aktivni=1 ORDER BY id"):
        pridej("05_typologie", "var", r["id"], "nazev", r["nazev"])
        pridej("05_typologie", "var", r["id"], "popis_zakaznicky", r["popis_zakaznicky"])
    for r in najdi(cur, "SELECT id,caption FROM content_gallery_items WHERE is_public=1 ORDER BY id"):
        pridej("06_galerie", "gal", r["id"], "caption", r["caption"])
    for r in najdi(cur, "SELECT id,name FROM shop_shipping_methods WHERE active=1 ORDER BY id"):
        pridej("07_obchod", "obch", "doprava%d" % r["id"], "name", r["name"])
    for r in najdi(cur, "SELECT id,name FROM shop_payment_methods WHERE active=1 ORDER BY id"):
        pridej("07_obchod", "obch", "platba%d" % r["id"], "name", r["name"])
    for r in najdi(cur, "SELECT DISTINCT unit FROM shop_products WHERE unit IS NOT NULL AND unit<>''"):
        pridej("07_obchod", "obch", "jednotka", "unit:" + r["unit"], r["unit"])
    # app_settings: jen verejne texty (bot16 2026-10-08); JSON hodnoty se rozlozi na retezce s cestou, dodavatele (manufacturer) se nepreklada
    for r in najdi(cur, "SELECT setting_key, setting_value FROM app_settings WHERE setting_key IN ('homepage_intro_html','vandrawee_cena_obsahuje_text','product_field_labels','product_field_options') ORDER BY setting_key"):
        k, v = r["setting_key"], r["setting_value"] or ""
        if v.lstrip().startswith("{"):
            def plochy(o, cesta=""):
                if isinstance(o, dict):
                    for kk, vv in o.items():
                        if kk == "manufacturer":
                            continue
                        yield from plochy(vv, (cesta + "." if cesta else "") + str(kk))
                elif isinstance(o, list):
                    for i, vv in enumerate(o):
                        yield from plochy(vv, cesta + "." + str(i))
                elif isinstance(o, str):
                    yield cesta, o
            for cesta, text in plochy(json.loads(v)):
                pridej("09_nastaveni", "nast", k, cesta, text)
        else:
            pridej("09_nastaveni", "nast", k, "html" if k.endswith("_html") else "text", v, "html" if k.endswith("_html") else "text")
    return sady, nezname


def nacti(cesta):
    if not os.path.exists(cesta):
        return {}
    with open(cesta, encoding="utf-8") as f:
        return {p["id"]: p for p in json.load(f)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vsechny-karty", action="store_true", help="i neaktivni a archivovane karty (vychozi: jen aktivni)")
    ap.add_argument("--vystup", default=VYSTUP)
    a = ap.parse_args(argv)
    os.makedirs(a.vystup, exist_ok=True)
    con = spoj()
    try:
        sady, nezname = sber(con.cursor(), a.vsechny_karty)
    finally:
        con.close()
    celkem = nove = zmeny = zastarale = 0
    for nazev, polozky in sady.items():
        cesta = os.path.join(a.vystup, nazev + ".json")
        stare = nacti(cesta)
        ven = []
        for p in polozky:
            s = stare.pop(p["id"], None)
            hc = hsh(p["cs"])
            if s is None:
                ven.append({"id": p["id"], "typ": p["typ"], "cs": p["cs"], "en": "", "it": "", "h": ""})
                nove += 1
                continue
            o = {"id": p["id"], "typ": p["typ"], "cs": p["cs"]}
            for j in JAZYKY:
                o[j] = s.get(j, "")
            prelozeno = any(o[j] for j in JAZYKY)
            o["h"] = s.get("h", "") if prelozeno else ""
            if prelozeno and o["h"] and o["h"] != hc:
                o["zmena"] = True
                zmeny += 1
            elif s.get("zmena") and o["h"] == hc:
                pass
            ven.append(o)
        zastarale += len(stare)
        if stare:
            print("ZASTARALE v %s: %s" % (nazev, ", ".join(list(stare)[:8]) + (" ..." if len(stare) > 8 else "")))
        with open(cesta, "w", encoding="utf-8") as f:
            json.dump(ven, f, ensure_ascii=False, indent=1)
            f.write("\n")
        znaku = sum(len(p["cs"]) for p in ven)
        print("%-16s %5d polozek, %8d znaku cs" % (nazev, len(ven), znaku))
        celkem += len(ven)
    print("Celkem %d polozek (nove %d, zmenene cs %d, zastarale %d)." % (celkem, nove, zmeny, zastarale))
    if nezname:
        print("POZOR: %d odkazu na neexistujici kategorii (zustaly beze zmeny): %s" % (len(nezname), nezname[:5]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
