#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Propíše ochranná razítka do dat sestav, které už jsou zařazené ve stromu.

PROČ EXISTUJE
-------------
Razítka se do `product_assemblies.data` propisují SPOUŠTĚČEM při zařazení
sestavy do složky stromu (`api/product_assemblies.py`, přechod
`category_id` NULL → složka). Jenže sestavy, které ve složce už dávno jsou,
ten přechod nikdy neudělají - a zůstaly by bez razítek napořád. Přesně ty,
kvůli kterým celá věc vznikla.

Tenhle skript je ta druhá polovina: dorovná stav sestav, které spouštěč
minul. Robert 2026-09-11 doslova: *„Razítkovač musí být skript
nerazítkujeme botem ručně."* - proto nástroj v `scripts/`, ne ad-hoc zápis
z konzole.

NENÍ TO JEDNORÁZOVKA. Spouští se znovu po každé změně pravidel razítkování
(zvednutí `razitkovac.OTISK_VERZE`): staré otisky tím přestanou platit,
skript to pozná a sestavy přerazítkuje. Opakované spuštění beze změny
pravidel neudělá nic - idempotenci drží týž otisk, jaký používá spouštěč,
ne zvláštní logika.

POUŽITÍ
-------
    # co by se stalo (nic nezapisuje):
    api/venv/bin/python3 scripts/orazitkovat_sestavy.py

    # ostrý běh:
    sudo -u www-data api/venv/bin/python3 scripts/orazitkovat_sestavy.py --zapsat

    # jiný rozsah:
    ... --sestavy 279,332,333 --zapsat
    ... --vse-zarazene --zapsat      (všechny s category_id != NULL)

POZOR NA UŽIVATELE: ostrý běh pouštěj jako `www-data`, pod kterým běží
služba. Tenhle skript sice píše jen do DB, ale záloha jde na disk a
soubor založený rootem by pak web nemusel přepsat ani smazat.
"""
import argparse
import json
import os
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import razitkovac as rz  # noqa: E402

KATALOG_DIR = os.path.join(REPO, "webapp", "katalog")
ZALOHY = os.path.join(REPO, "backups")

# Sestavy, které Robert chce vidět orazítkované (schválené a zařazené), plus
# 134 - ta jediná nese v datech stará razítka bez výplní z ručního dema
# 2026-09-08, tedy jediný dnes vadný stav.
VYCHOZI = [134, 279, 332, 333, 334, 335, 336, 337]


def _conn():
    from app import get_conn
    return get_conn()


def _zaloha_hotova(cesta, data):
    """Zápis zálohy jako DOKONČENÝ krok, ne jako 'soubor se otevřel'.

    fsync + kontrola velikosti + zpětné načtení. Bez toho by se při pádu
    uprostřed zápisu tvářila jako hotová záloha nekompletní soubor - a
    zjistilo by se to až ve chvíli, kdy by byla potřeba.
    """
    syrove = json.dumps(data, ensure_ascii=False, indent=1)
    tmp = cesta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(syrove)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, cesta)
    # adresář taky, jinak přejmenování nemusí přežít pád stroje
    d = os.open(os.path.dirname(cesta), os.O_RDONLY)
    try:
        os.fsync(d)
    finally:
        os.close(d)
    vel = os.path.getsize(cesta)
    if vel != len(syrove.encode("utf-8")):
        raise SystemExit("ZÁLOHA NEÚPLNÁ: %s má %d B, čekám %d B"
                         % (cesta, vel, len(syrove.encode("utf-8"))))
    with open(cesta, encoding="utf-8") as fh:
        zpet = json.load(fh)
    if len(zpet) != len(data):
        raise SystemExit("ZÁLOHA NEČITELNÁ: zpětné načtení dalo %d položek místo %d"
                         % (len(zpet), len(data)))
    return vel


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sestavy", default=None,
                    help="čárkou oddělená ID (výchozí: schválené a zařazené + 134)")
    ap.add_argument("--vse-zarazene", action="store_true", dest="vse",
                    help="všechny sestavy s category_id != NULL")
    ap.add_argument("--zapsat", action="store_true",
                    help="bez tohohle se JEN vypíše, co by se stalo")
    a = ap.parse_args()

    conn = _conn()
    try:
        with conn.cursor() as cur:
            if a.vse:
                cur.execute("SELECT id, name, category_id, data FROM product_assemblies "
                            "WHERE category_id IS NOT NULL ORDER BY id")
            else:
                ids = [int(x) for x in a.sestavy.split(",")] if a.sestavy else VYCHOZI
                cur.execute("SELECT id, name, category_id, data FROM product_assemblies "
                            "WHERE id IN (%s) ORDER BY id" % ",".join(["%s"] * len(ids)), ids)
            radky = cur.fetchall()
            # Presne rozmery vc. produktu (eurobox aj.) pro blokovaci/exponovani
            # kontrolu razitek - bez tohohle padaji VSECHNY product_* dily na
            # hruby odhad ROZMER_NEZNAMY (viz razitkovac.rozmery_z_katalogu).
            rozmery = rz.rozmery_z_katalogu(cur, KATALOG_DIR)
    finally:
        conn.close()

    if not radky:
        raise SystemExit("Žádná sestava neodpovídá zadání.")

    print("=" * 78)
    print("RAZÍTKOVÁNÍ SESTAV  (pravidla verze %d)   %s"
          % (rz.OTISK_VERZE, "OSTRÝ ZÁPIS" if a.zapsat else "NÁHLED - nic se nezapíše"))
    print("=" * 78)
    print("%-5s %-34s %-6s %-11s %s" % ("id", "název", "dílů", "stav", "změna"))

    plan, zaloha = [], []
    for r in radky:
        try:
            data = json.loads(r["data"]) if r["data"] else {}
        except (ValueError, TypeError):
            print("%-5s %-34s  DATA NEJDOU PŘEČÍST - přeskočeno" % (r["id"], r["name"][:34]))
            continue
        pred = len(data.get("parts") or [])
        stav = rz.stav_razitek(data)
        if stav == "aktualni":
            print("%-5s %-34s %-6d %-11s beze změny" % (r["id"], r["name"][:34], pred, stav))
            continue
        nova, zprava = rz.prerazitkuj(data, r["id"], KATALOG_DIR, rozmery=rozmery)
        if nova is None:
            print("%-5s %-34s %-6d %-11s PŘESKOČENO: %s"
                  % (r["id"], r["name"][:34], pred, stav, zprava))
            continue
        stara_raz = sum(1 for p in (data.get("parts") or []) if rz.je_razitko(p.get("role")))
        nova_raz = sum(1 for p in nova["parts"] if rz.je_razitko(p.get("role")))
        print("%-5s %-34s %-6d %-11s -%d +%d razítkových dílů (%d -> %d)"
              % (r["id"], r["name"][:34], pred, stav, stara_raz, nova_raz,
                 pred, len(nova["parts"])))
        plan.append((r["id"], nova))
        zaloha.append({"id": r["id"], "name": r["name"], "category_id": r["category_id"],
                       "data": data})

    print("-" * 78)
    print("KE ZMĚNĚ: %d sestav z %d, razítkových dílů celkem po zápisu: %d"
          % (len(plan), len(radky),
             sum(sum(1 for p in d["parts"] if rz.je_razitko(p.get("role"))) for _i, d in plan)))

    if not a.zapsat:
        print("\nNÁHLED - nic se nezapsalo. Ostrý běh: přidej --zapsat")
        return
    if not plan:
        print("Není co zapisovat.")
        return

    os.makedirs(ZALOHY, exist_ok=True)
    cesta = os.path.join(ZALOHY, "%s_razitkovani_pred_zapisem.json"
                         % datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    vel = _zaloha_hotova(cesta, zaloha)
    print("ZÁLOHA HOTOVA (fsync + ověřená velikost + zpětné načtení): %s (%d kB)"
          % (cesta, vel // 1024))

    conn = _conn()
    try:
        with conn.cursor() as cur:
            for aid, nova in plan:
                cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                            (json.dumps(nova, ensure_ascii=False), aid))
        conn.commit()
    finally:
        conn.close()
    print("ZAPSÁNO: %d sestav" % len(plan))

    # Kontrola ČERSTVÝM spojením - ne z toho, přes které se zapisovalo.
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, data FROM product_assemblies WHERE id IN (%s)"
                        % ",".join(["%s"] * len(plan)), [i for i, _d in plan])
            zpet = {r["id"]: json.loads(r["data"]) for r in cur.fetchall()}
    finally:
        conn.close()
    chyby = 0
    for aid, nova in plan:
        d = zpet.get(aid) or {}
        stav = rz.stav_razitek(d)
        pocet = sum(1 for p in (d.get("parts") or []) if rz.je_razitko(p.get("role")))
        ceka = sum(1 for p in nova["parts"] if rz.je_razitko(p.get("role")))
        ok = stav == "aktualni" and pocet == ceka
        if not ok:
            chyby += 1
        print("  kontrola #%-5s stav=%-10s razítek=%-3d %s"
              % (aid, stav, pocet, "OK" if ok else "NESEDÍ (čekám %d)" % ceka))
    print("\n%s" % ("VŠE OVĚŘENO" if not chyby else "POZOR: %d sestav nesedí" % chyby))
    sys.exit(1 if chyby else 0)


if __name__ == "__main__":
    main()
