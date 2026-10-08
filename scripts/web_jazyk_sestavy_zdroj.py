#!/usr/bin/env python3
"""Zdroj k prekladu textu SESTAV (karty Vandr / skladane vestavby) pro EN/IT verzi webu: docs/web_jazyky/11_sestavy.json - bot16, 2026-10-08.
Stejny tvar jako sesity bot7 ({id, typ, cs, en, it, h, [zmena]}), rerun je BEZPECNY (preklady, h a zmena zustanou, pridaji se nove vety, zmizele s prekladem dostanou zastarale: true).
Texty sestav nejsou ve sloupcich obsahu, ktere cte web_jazyk_zdroj.py, ale v katalogovych tabulkach (zakaznicky text se pise jednou na variantu) a v nazvu sestavy:
  hbv:<id>:nazev | popis_zakaznicky   horni_blok_varianty   (horni blok: "Jedno pasmo - ram + dna", popis varianty)
  rum:<id>:nazev | montaz_zakaznicky | kotveni_zakaznicky   regal_umisteni   (kam se regal kotvi, jak se montuje)
  sest:<sha1(cs)[:12]>:fragment       cast verejneho nazvu sestavy za " - " (po cisteni verejny_popisek_sestavy): "dve pasma", "plne vyplne", "bez police" ...; kody boxu (boxy43-170x3-120x6) a nazev vozidla se neprekladaji
Preklad se pri cteni uplatni v api/web_i18n.py (JSON /api/shop/products/<id>/assemblies): text z katalogu najde sve klice podle cestiny, nazev se slozi z prelozenych fragmentu.
Pouziti (z korene repa):  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/web_jazyk_sestavy_zdroj.py"""
import hashlib
import json
import os
import re
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VYSTUP = os.path.join(ROOT, "docs", "web_jazyky", "11_sestavy.json")

_orig_start = threading.Thread.start
threading.Thread.start = lambda s, *a, **k: None if getattr(s, "name", "") == "render-dozorce" else _orig_start(s, *a, **k)   # import app nesmi spustit dozorce renderu
sys.path.insert(0, os.path.join(ROOT, "api"))
sys.dont_write_bytecode = True
from app import get_conn, verejny_popisek_sestavy  # noqa: E402


def hsh(s, n=10):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


def sber():
    polozky = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nazev, popis_zakaznicky FROM horni_blok_varianty ORDER BY id")
            for r in cur.fetchall():
                for p in ("nazev", "popis_zakaznicky"):
                    if (r[p] or "").strip():
                        polozky.append(("hbv:%s:%s" % (r["id"], p), r[p]))
            cur.execute("SELECT id, nazev, montaz_zakaznicky, kotveni_zakaznicky FROM regal_umisteni WHERE aktivni=1 ORDER BY id")
            for r in cur.fetchall():
                for p in ("nazev", "montaz_zakaznicky", "kotveni_zakaznicky"):
                    if (r[p] or "").strip():
                        polozky.append(("rum:%s:%s" % (r["id"], p), r[p]))
            cur.execute("SELECT name FROM product_assemblies WHERE technicky_ok=1")
            frag = set()
            for r in cur.fetchall():
                m = re.match(r"^(.*?)\s+-\s+(.+)$", verejny_popisek_sestavy(r["name"]))
                if not m:
                    continue
                for f in [x.strip() for x in m.group(2).split(",")]:
                    if f and not re.match(r"^boxy\d", f):
                        frag.add(f)
            for f in sorted(frag):
                polozky.append(("sest:%s:fragment" % hsh(f, 12), f))
    finally:
        conn.close()
    return polozky


def main():
    stare = {}
    if os.path.exists(VYSTUP):
        for it in json.load(open(VYSTUP, encoding="utf-8")):
            stare[it["id"]] = it
    nove, videno = [], set()
    for id_, cs in sber():
        videno.add(id_)
        st = stare.get(id_)
        it = {"id": id_, "typ": "text", "cs": cs, "en": "", "it": "", "h": ""}
        if st:
            it.update({k: st.get(k, "") for k in ("en", "it", "h")})
            if st.get("cs") != cs and (st.get("en") or st.get("it")):
                it["zmena"] = True                       # cestina se od prekladu zmenila: preklad zustane, ale je nutno ho zkontrolovat (import ho bere jako zastaraly)
            elif st.get("zmena"):
                it["zmena"] = True
        nove.append(it)
    zastarale = [dict(it, zastarale=True) for k, it in stare.items() if k not in videno and (it.get("en") or it.get("it"))]
    json.dump(nove + zastarale, open(VYSTUP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("zapsano %d vet do %s (%d s prekladem, %d zastaralych)" % (len(nove), os.path.relpath(VYSTUP, ROOT), sum(1 for i in nove if i["en"] or i["it"]), len(zastarale)))


if __name__ == "__main__":
    main()
