#!/usr/bin/env python3
"""Slugy (adresy) pro EN a IT z prelozenych nazvu -> docs/web_jazyky/08_slugy.json. bot7, 2026-10-08.

Polozky: kat:<id>:slug (z prelozeneho nazvu kategorie), kar:<id>:slug (nazev karty), dom:blok<N>:slug (nadpis bloku homepage); cs = dnesni cesky slug z DB.
Pravidla: a-z 0-9 -, bez diakritiky, max 80 znaku (rez na pomlcce), jedinecny v ramci (kod, jazyk); kolize a rezervovane cesty -> priponka -<id>.
Rerun bezpecny: uz zapsane slugy zustanou (kdyz se zmeni nazev, slug se NEMENI - kvuli odkazum a indexaci; prepsat jen rucne v souboru).
Pouziti (potrebuje api/.env, jen SELECT):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      /opt/konfigurator/api/venv/bin/python3 scripts/web_jazyk_slugy.py
"""
import json
import os
import re
import sys
import unicodedata

import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _web_jazyk as W  # noqa: E402

REZERVOVANE = {
    "basket", "cart", "carrello", "contact", "contatti", "my-orders", "i-miei-ordini", "projects", "realizzazioni",
    "category", "categoria", "product", "prodotto", "block", "blocco", "panel", "pannello", "login", "register", "registrazione",
    "admin", "api", "search", "sitemap", "robots", "scene", "content-files", "static", "forgot-password", "reset-password", "verify-email",
}
ZNAKY = {"ø": "o", "Ø": "o", "×": "x", "²": "2", "³": "3", "&": " and ", "ß": "ss", "æ": "ae", "œ": "oe", "đ": "d", "ł": "l"}


def slugify(t, jazyk="en"):
    for a, b in ZNAKY.items():
        t = t.replace(a, b if not (a == "&" and jazyk == "it") else " e ")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    if len(t) > 80:
        t = t[:80].rsplit("-", 1)[0] if "-" in t[:80] else t[:80]
    return t


def main():
    con = pymysql.connect(host=os.environ.get("DB_HOST", "localhost"), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                          database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    cur = con.cursor()
    cur.execute("SELECT id, slug FROM content_categories")
    cs_kat = {r["id"]: r["slug"] for r in cur.fetchall()}
    cur.execute("SELECT id, slug FROM shop_products WHERE active=1 AND is_archived=0")
    cs_kar = {r["id"]: r["slug"] for r in cur.fetchall()}
    cur.execute("SELECT id, slug FROM homepage_blocks")
    cs_dom = {"blok%d" % r["id"]: r["slug"] for r in cur.fetchall()}
    con.close()

    nazvy = {}
    for s, kod, pole in (("01_kategorie", "kat", "name"), ("03_karty", "kar", "name"), ("04_homepage", "dom", "title")):
        for p in W.nacti_sadu(s):
            m = W.KOD_V_ID.match(p["id"])
            if m and m.group("tbl") == kod and m.group("pole") == pole:
                nazvy[(kod, m.group("pk"))] = p

    cesta = os.path.join(W.SLOZKA, "08_slugy.json")
    stare = {p["id"]: p for p in json.load(open(cesta, encoding="utf-8"))} if os.path.exists(cesta) else {}
    pouzite = {(kod, j): set() for kod in ("kat", "kar", "dom") for j in W.JAZYKY}
    for p in stare.values():
        kod = p["id"].split(":")[0]
        for j in W.JAZYKY:
            if p.get(j):
                pouzite[(kod, j)].add(p[j])
    ven, nove, chybi = [], 0, 0
    for kod, cs_map in (("kat", cs_kat), ("kar", cs_kar), ("dom", cs_dom)):
        for pk in sorted(cs_map, key=lambda x: (str(x).zfill(8))):
            iid = "%s:%s:slug" % (kod, pk)
            s = stare.get(iid) or {"id": iid, "typ": "slug", "cs": cs_map[pk], "en": "", "it": ""}
            s["cs"] = cs_map[pk]
            n = nazvy.get((kod, str(pk)))
            for j in W.JAZYKY:
                if s.get(j):
                    continue
                if not n or not n.get(j):
                    chybi += 1
                    continue
                sl = slugify(n[j], j)
                num = re.sub(r"\D", "", str(pk)) or str(pk)
                if not sl:
                    sl = "%s-%s" % (kod, num)
                if sl in pouzite[(kod, j)] or (kod == "kat" and sl in REZERVOVANE):
                    sl = "%s-%s" % (sl, num)
                pouzite[(kod, j)].add(sl)
                s[j] = sl
                nove += 1
            if n and s.get("en") and s.get("it"):
                s["h"] = W.hsh(s["cs"])
            s.setdefault("h", "")
            ven.append(s)
    with open(cesta, "w", encoding="utf-8") as f:
        json.dump(ven, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("08_slugy.json: %d polozek, nove slugy %d, bez nazvu (zatim) %d" % (len(ven), nove, chybi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
