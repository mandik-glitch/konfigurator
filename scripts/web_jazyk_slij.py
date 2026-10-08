#!/usr/bin/env python3
"""Zkontroluje vystupy prekladu (davka_NNN.out.json = [{k, en, it}]) a sloucí je do sesitu docs/web_jazyky. bot7, 2026-10-08.

  python3 scripts/web_jazyk_slij.py --davky /cesta/davky            # jen kontrola (nic se nezapise), vypise chyby
  python3 scripts/web_jazyk_slij.py --davky /cesta/davky --apply     # zapise jen bezchybne preklady (en i it zvlast)
  python3 scripts/web_jazyk_slij.py --stav                           # kolik je prelozeno / s chybou / ceka (cele sesity)
Davku s chybami lze znovu zadat: chybne kliče se vypisou do <davky>/chyby.json (format davky) k opravnemu pruchodu.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _web_jazyk as W  # noqa: E402


def stav():
    tot = {j: 0 for j in W.JAZYKY}
    vse = 0
    for s in W.SADY:
        d = W.nacti_sadu(s)
        radek = {j: 0 for j in W.JAZYKY}
        chyb = {j: 0 for j in W.JAZYKY}
        zm = 0
        for p in d:
            pole = W.pole_z_id(p["id"])
            for j in W.JAZYKY:
                if p[j]:
                    radek[j] += 1
                    if W.zkontroluj(pole, p["typ"], p["cs"], p[j], j)[0]:
                        chyb[j] += 1
            zm += 1 if p.get("zmena") else 0
        print("%-14s %5d polozek | en %5d (chyb %d) | it %5d (chyb %d) | zmenene cs %d" % (s, len(d), radek["en"], chyb["en"], radek["it"], chyb["it"], zm))
        vse += len(d)
        for j in W.JAZYKY:
            tot[j] += radek[j]
    print("CELKEM %d | en %d | it %d" % (vse, tot["en"], tot["it"]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--davky")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--stav", action="store_true")
    a = ap.parse_args(argv)
    if a.stav:
        stav()
        return 0
    if not a.davky:
        ap.error("--davky nebo --stav")
    vstup = {}
    jeden = os.path.isfile(a.davky)
    vstupy = [a.davky] if jeden else sorted(glob.glob(os.path.join(a.davky, "davka_*.json")))
    for f in vstupy:
        if f.endswith(".out.json"):
            continue
        for p in json.load(open(f, encoding="utf-8")):
            vstup[p["k"]] = p
    vystup = {}
    vystupy = [a.davky[:-5] + ".out.json"] if jeden else sorted(glob.glob(os.path.join(a.davky, "davka_*.out.json")))
    for f in vystupy:
        if not os.path.exists(f):
            continue
        try:
            data = json.load(open(f, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print("CHYBA cteni %s: %s" % (os.path.basename(f), e))
            continue
        for p in data:
            vystup[p.get("k")] = p
    bez = [k for k in vstup if k not in vystup]
    dobre = {}  # (k, jazyk) -> text
    chyby = {}
    for k, p in vstup.items():
        o = vystup.get(k)
        if not o:
            continue
        for j in W.JAZYKY:
            ch, var = W.zkontroluj(p["pole"], p["typ"], p["cs"], o.get(j, ""), j)
            if ch:
                chyby.setdefault(k, []).append((j, ch))
            else:
                dobre[(k, j)] = o[j]
    for k, lst in list(chyby.items())[:60]:
        for j, ch in lst:
            print("CHYBA %s %s [%s] %s | %s" % (k, j, vstup[k]["pole"], "; ".join(ch), vstup[k]["cs"][:70].replace("\n", " ")))
    print("vstup %d, bez vystupu %d, s chybou %d (en/it zvlast), bezchybnych prekladu %d" % (len(vstup), len(bez), len(chyby), len(dobre)))
    if (chyby or bez) and not jeden:
        with open(os.path.join(a.davky, "chyby.json"), "w", encoding="utf-8") as f:
            json.dump([vstup[k] for k in list(chyby) + bez if k in vstup], f, ensure_ascii=False, indent=1)
            f.write("\n")
    if not a.apply:
        return 1 if chyby else 0
    zapsano = 0
    for s in W.SADY:
        d = W.nacti_sadu(s)
        zmen = False
        for p in d:
            k = W.klic(W.pole_z_id(p["id"]), p["cs"])
            for j in W.JAZYKY:
                t = dobre.get((k, j))
                if t is not None and k in vstup and (not p[j] or p.get("zmena")):
                    p[j] = t
                    zmen = True
                    zapsano += 1
            if p["en"] and p["it"] and any((k, j) in dobre for j in W.JAZYKY):
                p["h"] = W.hsh(p["cs"])
                p.pop("zmena", None)
        if zmen:
            W.uloz_sadu(s, d)
    print("zapsano %d prekladu do sesitu" % zapsano)
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
