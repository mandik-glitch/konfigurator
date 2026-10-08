#!/usr/bin/env python3
"""Sjednoti terminologii v prelozenych sesitech podle docs/web_jazyky/glosar.json -> "sjednotit" (hledat = regex, nahradit = cil, velikost prvniho pismene se zachova).
Pouziti: python3 scripts/web_jazyk_sjednot.py [--apply]   (bez --apply jen spocita zmeny). bot7, 2026-10-08."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _web_jazyk as W  # noqa: E402


def zamen(text, rx, cil):
    def r(m):
        t = cil
        if m.group(0)[:1].isupper() and t[:1].islower():
            t = t[:1].upper() + t[1:]
        elif m.group(0)[:1].islower() and t[:1].isupper() and cil.upper() != cil:
            t = t[:1].lower() + t[1:]
        return t
    return rx.subn(r, text)


def main():
    apply = "--apply" in sys.argv
    pravidla = json.load(open(os.path.join(W.SLOZKA, "glosar.json"), encoding="utf-8")).get("sjednotit", [])
    celkem = 0
    for s in W.SADY:
        d = W.nacti_sadu(s)
        zmen = 0
        for p in d:
            for pr in pravidla:
                j = pr["jazyk"]
                if not p.get(j):
                    continue
                novy, n = zamen(p[j], re.compile(pr["hledat"], re.I), pr["nahradit"])
                if n and novy != p[j]:
                    zmen += 1
                    if apply:
                        p[j] = novy
        if zmen:
            print("%-14s %d zmen" % (s, zmen))
            celkem += zmen
            if apply:
                W.uloz_sadu(s, d)
    print("Celkem %d zmen%s" % (celkem, "" if apply else " (bez --apply nezapsano)"))


if __name__ == "__main__":
    main()
