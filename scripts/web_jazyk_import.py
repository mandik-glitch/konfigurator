#!/usr/bin/env python3
"""Import prekladu ze sesitu docs/web_jazyky/*.json do tabulky web_i18n (bot16, 2026-10-08; architektura docs/web_jazyky/README.md, sesity bot7).

Zdroj pravdy jsou JEN sesity (01_..07_, 09_nastaveni, 10_ui; polozka {id, typ, cs, en, it, h, [zmena]}). Do DB jde jen to, co projde scripts/_web_jazyk.py::zkontroluj (stejna kontrola jako u bot7,
jedna verze pravdy); chybne polozky se vypisi a PRESKOCI. Prazdny preklad = v DB neni. Polozka se zmena:true se zapise se zastarale=1 (resolver ji nepouzije).
Synchronizace: radky web_i18n, ktere v sesitech uz nejsou (nebo ztratily preklad), se SMAZOU - jen s --apply. Bez --apply jen vypise, co by se stalo (nic se nezapise).

Pouziti (z korene repa):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/web_jazyk_import.py [--apply] [--lang en|it]
"""
import argparse
import json
import os
import re
import sys

import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _web_jazyk as W  # noqa: E402  (bot7: SADY, zkontroluj, hsh)

JAZYKY = ("en", "it")


def spoj():
    return pymysql.connect(host=os.environ.get("DB_HOST", "localhost"), port=int(os.environ.get("DB_PORT") or 3306), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                           database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def sesity():
    """Vsechny sesity NN_*.json ve slozce (bot7 doplnuje dalsi, napr. 08_slugy) - sady z _web_jazyk.SADY + cokoli, co vypada jako sesit (seznam polozek s id a cs)."""
    sady = list(W.SADY)
    for f in sorted(os.listdir(W.SLOZKA)):
        m = re.match(r"^(\d\d_[a-z0-9_]+)\.json$", f)
        if m and m.group(1) not in sady and not m.group(1).endswith("_kontext"):
            try:
                d = W.nacti_sadu(m.group(1))
            except Exception:
                continue
            if isinstance(d, list) and d and isinstance(d[0], dict) and "id" in d[0] and "cs" in d[0]:
                sady.append(m.group(1))
    return sady


def cil_radky(jazyky):
    """{(klic, lang): (text, h, zastarale)} z kontrolovanych sesitu + seznam chyb."""
    radky, chyby, preskoceno = {}, [], 0
    for s in sesity():
        for p in W.nacti_sadu(s):
            pole = W.pole_z_id(p["id"])
            for j in jazyky:
                t = (p.get(j) or "")
                if not t.strip():
                    continue
                if pole == "slug":                     # slug: jen a-z 0-9 - (bot7 si ho hlida sam; "shodny se zdrojem" u slugu nevadi)
                    ch = [] if re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", t) else ["slug musi byt a-z 0-9 a pomlcky"]
                else:
                    ch, _var = W.zkontroluj(pole, p["typ"], p["cs"], t, j)
                if ch:
                    chyby.append((s, p["id"], j, "; ".join(ch)))
                    preskoceno += 1
                    continue
                h = p.get("h") or ""
                radky[(p["id"], j)] = (t, h, 1 if (p.get("zmena") or p.get("zastarale") or (h and h != W.hsh(p["cs"]))) else 0, p["cs"])
    return radky, chyby


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--lang", choices=JAZYKY)
    a = ap.parse_args()
    jazyky = (a.lang,) if a.lang else JAZYKY
    cil, chyby = cil_radky(jazyky)
    c = spoj()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT klic, lang, `text`, h, zastarale, cs FROM web_i18n WHERE lang IN (%s)" % ",".join(["%s"] * len(jazyky)), jazyky)
            ted = {(r["klic"], r["lang"]): (r["text"], r["h"], r["zastarale"], r["cs"]) for r in cur.fetchall()}
            nove = [k for k in cil if k not in ted]
            zmenene = [k for k in cil if k in ted and ted[k] != cil[k]]
            smazat = [k for k in ted if k not in cil]
            print("sesity: %d radku k importu (%s), chybnych preskoceno: %d" % (len(cil), ", ".join("%s %d" % (j, sum(1 for k in cil if k[1] == j)) for j in jazyky), len(chyby)))
            print("novych: %d, zmenenych: %d, ke smazani: %d, beze zmeny: %d, zastaralych v importu: %d" % (len(nove), len(zmenene), len(smazat), len(cil) - len(nove) - len(zmenene), sum(1 for v in cil.values() if v[2])))
            for s, i, j, e in chyby[:25]:
                print("  CHYBA %s %s [%s]: %s" % (s, i, j, e))
            if len(chyby) > 25:
                print("  ... a dalsich %d chyb" % (len(chyby) - 25))
            if not a.apply:
                print("(bez --apply se nic nezapsalo)")
                return
            for i in range(0, len(nove) + len(zmenene), 500):
                davka = [(k[0], k[1]) + cil[k] for k in (nove + zmenene)[i:i + 500]]
                cur.executemany("INSERT INTO web_i18n (klic, lang, `text`, h, zastarale, cs) VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE `text`=VALUES(`text`), h=VALUES(h), zastarale=VALUES(zastarale), cs=VALUES(cs)", davka)
            for i in range(0, len(smazat), 500):
                cur.executemany("DELETE FROM web_i18n WHERE klic=%s AND lang=%s", smazat[i:i + 500])
        c.commit()
        print("zapsano")
    finally:
        c.close()


if __name__ == "__main__":
    main()
