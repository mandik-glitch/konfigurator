#!/usr/bin/env python3
"""Dávky k prekladu hlavniho webu (cs -> en + it). bot7, 2026-10-08.

Z docs/web_jazyky/*.json vybere polozky bez prekladu (nebo se zmenenym cs), sloučí stejne texty ve stejnem poli (preklad jednou)
a rozdeli je do davek <= --max-znaku. Kazda davka je soubor [{k, pole, typ, cs}], preklad se vraci jako [{k, en, it}]
(viz scripts/web_jazyk_slij.py). Do repa se nic nezapisuje, davky jdou do --vystup.

  python3 scripts/web_jazyk_davky.py --vystup /cesta/davky [--max-znaku 9000] [--sady 03_karty,02_stranky]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _web_jazyk as W  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--vystup", required=True)
    ap.add_argument("--max-znaku", type=int, default=9000)
    ap.add_argument("--max-polozek", type=int, default=70)
    ap.add_argument("--sady", default=",".join(W.SADY))
    a = ap.parse_args(argv)
    os.makedirs(a.vystup, exist_ok=True)
    cekajici = {}
    for s in a.sady.split(","):
        for p in W.nacti_sadu(s):
            if p.get("zastarale") or (p["en"] and p["it"] and not p.get("zmena")):
                continue
            pole = W.pole_z_id(p["id"])
            cekajici.setdefault(W.klic(pole, p["cs"]), {"k": W.klic(pole, p["cs"]), "pole": pole, "typ": p["typ"], "cs": p["cs"], "sada": s})
    # velke HTML texty (stranky) po jednom, ostatni po skupinach stejne sady a pole
    seznam = sorted(cekajici.values(), key=lambda x: (x["sada"], x["pole"], x["k"]))
    davky, cur, znaku = [], [], 0
    for p in seznam:
        d = len(p["cs"])
        if cur and (znaku + d > a.max_znaku or len(cur) >= a.max_polozek or cur[-1]["sada"] != p["sada"]):
            davky.append(cur)
            cur, znaku = [], 0
        cur.append(p)
        znaku += d
    if cur:
        davky.append(cur)
    for i, dv in enumerate(davky, 1):
        cesta = os.path.join(a.vystup, "davka_%03d.json" % i)
        with open(cesta, "w", encoding="utf-8") as f:
            json.dump([{k: v for k, v in p.items() if k != "sada"} for p in dv], f, ensure_ascii=False, indent=1)
            f.write("\n")
    print("%d unikatnich textu, %d znaku, %d davek -> %s" % (len(seznam), sum(len(p["cs"]) for p in seznam), len(davky), a.vystup))
    return 0


if __name__ == "__main__":
    sys.exit(main())
