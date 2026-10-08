#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zapise shop_products.umisteni_id pro Vandr karty (WORKFLOW.md pravidlo
51). Zdroj pravdy: vandrawee_work.stored_models.left_part_id /
right_part_id / bulkhead_part_id - PRAVE JEDEN z techto tri sloupcu byva
u realnych dat vyplneny (overeno primo v DB 2026-09-24, ne prevzato:
324 radku, 252 jen left, 56 jen right, 17 jen bulkhead, 1 ma left+right
soucasne = genuinne nejednoznacne, 0 radku ma vsechny tri NULL).

Mapovani (regal_umisteni.kod):
  jen left_part_id      -> RL (id 1, regal levy)
  jen right_part_id     -> RP (id 7, regal pravy)
  jen bulkhead_part_id  -> RK (id 2, kabina/za prepazkou)
  cokoli jineho (0 nebo 2+ z trech sloupcu vyplneno, nebo zadna shoda
  uuid ve stored_models) -> umisteni_id se NEMENI (zustava NULL nebo
  puvodni hodnota), karta se vypise do NEURCENO s duvodem - zadny tichy
  default (viz pamet "0 nalezu musi znamenat zmereno a cisto").

Idempotentni: znovuspusteni prepise stejne karty stejnou hodnotou.
Nemeni `active` ani nic jineho - jen umisteni_id.

POUZITI: api/venv/bin/python3 scripts/2026-09-24_vandr_umisteni_backfill.py [--dry-run]
"""
import argparse
import sys
import pymysql

VANDR_ENV_PATH = "/opt/vandrawee/web/.env"
KONFIG_ENV_PATH = "/opt/konfigurator/api/.env"

sys.path.insert(0, "/opt/konfigurator/scripts")
from _vandr_umisteni import urcit_umisteni_id, RL_ID, RP_ID, RK_ID  # noqa: E402  sdileno s watcherem

# WORKFLOW.md pravidlo 52 (Robert: "nikdy nic se nesmi odkladat, ihned
# vyresit") - rucni doreseni dvou ze tri puvodne NEURCENYCH karet
# (2026-09-24 druhy beh), kazda s konkretnim overenym dukazem, ZADNY odhad:
#   4902 (VD-EXPORT-trafic-2f89b425): nema UUID SKU, nenajde se ve
#     stored_models vubec - ale VLASTNI NAZEV karty ("EXPORT (realny FBX
#     z appky): Renault Trafic L2H1 - leva police") rovnou rika stranu.
#   4277 (VD-3aa15dc3-...): take bez shody ve stored_models (UUID uz tam
#     neni), ale puvodni CSV import (bot7 2026-09-18, primy scrape
#     vandrawee.eu, backups/2026-09-18_vandrawee_seznam_pro_bot10/
#     vandrawee_uuid_seznam.csv) ma pro presne tohle UUID
#     `strana_raw=leva cast`.
# Treti puvodne neurcena karta (4366, VD-8db32bcb-...) NENI tady - jeji
# stored_models radek ma left_part_id I right_part_id VYPLNENE SOUCASNE
# (jedine takove ze 324), a rozbor obou dilu (537/538) ukazuje DVA
# realne kusovniky se zrcadlenym X (-0.6 / +0.6) = genuinne LEVA I PRAVA
# sestava v jednom stored_models radku, zadny z 7 kodu regal_umisteni na
# to nesedi 1:1. To NENI neco, co jde dopocitat - je to produktove
# rozhodnuti (novy kod? rozdelit kartu? vzit jen jednu stranu?), predano
# primo Robertovi pres bot3 rovnou v tehle session (2026-09-24), ne
# odlozeno - viz AGENTS_LOG.
RUCNI_PREPIS = {4902: RL_ID, 4277: RL_ID}


def _parse_env(path):
    vals = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def _format_uuid(hex32):
    # Port scripts/2026-09-22_vandr_fbx_watcher.py::_format_uuid - STEJNA
    # konverze jako pouziva watcher pri zakladani karty (shop_products.sku
    # = 'VD-' + tenhle format), aby se pary uuid<->karta nikde nerozesly.
    h = hex32.lower()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="jen spocitat a vypsat, nic nezapisovat")
    a = ap.parse_args()

    venv = _parse_env(VANDR_ENV_PATH)
    conn_w = pymysql.connect(host=venv.get("DB_HOST", "127.0.0.1"), port=int(venv.get("DB_PORT", "3306")),
                              user=venv["DB_USERNAME"], password=venv["DB_PASSWORD"],
                              database="vandrawee_work", cursorclass=pymysql.cursors.DictCursor)
    kenv = _parse_env(KONFIG_ENV_PATH)
    conn_k = pymysql.connect(host=kenv["DB_HOST"], port=int(kenv.get("DB_PORT", 3306)),
                              user=kenv["DB_USER"], password=kenv["DB_PASSWORD"],
                              database=kenv["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)

    with conn_w.cursor() as cur:
        cur.execute("SELECT LOWER(HEX(uuid)) AS uuid_hex, left_part_id, right_part_id, bulkhead_part_id "
                    "FROM stored_models")
        stored = {r["uuid_hex"]: r for r in cur.fetchall()}
    print("vandrawee_work.stored_models: %d radku nacteno" % len(stored))

    with conn_k.cursor() as cur:
        cur.execute("SELECT id, sku, umisteni_id FROM shop_products "
                    "WHERE sku LIKE 'VD-%%' AND sku NOT LIKE 'VD-TEST-%%' ORDER BY id")
        karty = cur.fetchall()
    print("shop_products Vandr karet (VD-, bez TEST): %d" % len(karty))

    urceno = {"RL": [], "RP": [], "RK": []}
    zmeneno = 0
    neurceno_zadna_shoda = []
    neurceno_nejednoznacne = []
    beze_zmeny_stejna_hodnota = 0

    for k in karty:
        if k["id"] in RUCNI_PREPIS:
            nova_hodnota = RUCNI_PREPIS[k["id"]]
        else:
            uuid_hex = k["sku"][3:].replace("-", "")  # 'VD-' + hex (uz s pomlckami z _format_uuid)
            row = stored.get(uuid_hex)
            if row is None:
                neurceno_zadna_shoda.append(k["sku"])
                continue
            nova_hodnota = urcit_umisteni_id(row)
            if nova_hodnota is None:
                vyplneno = [n for n in ("left_part_id", "right_part_id", "bulkhead_part_id") if row[n] is not None]
                neurceno_nejednoznacne.append((k["sku"], vyplneno))
                continue
        kod = {RL_ID: "RL", RP_ID: "RP", RK_ID: "RK"}[nova_hodnota]
        urceno[kod].append(k["id"])
        if k["umisteni_id"] == nova_hodnota:
            beze_zmeny_stejna_hodnota += 1
            continue
        zmeneno += 1
        if not a.dry_run:
            with conn_k.cursor() as cur:
                cur.execute("UPDATE shop_products SET umisteni_id=%s WHERE id=%s", (nova_hodnota, k["id"]))

    if not a.dry_run:
        conn_k.commit()
        # Overeni rowcount (feedback_verify_db_write_rowcount) - SELECT
        # zpet, ne jen spoleh na to, ze UPDATE "neshodil".
        with conn_k.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM shop_products WHERE id IN (%s) AND umisteni_id=1" %
                        ",".join(str(i) for i in urceno["RL"]) if urceno["RL"] else "SELECT 0 n")
            rl_overeno = cur.fetchone()["n"] if urceno["RL"] else 0
            cur.execute("SELECT COUNT(*) n FROM shop_products WHERE id IN (%s) AND umisteni_id=7" %
                        ",".join(str(i) for i in urceno["RP"]) if urceno["RP"] else "SELECT 0 n")
            rp_overeno = cur.fetchone()["n"] if urceno["RP"] else 0
            cur.execute("SELECT COUNT(*) n FROM shop_products WHERE id IN (%s) AND umisteni_id=2" %
                        ",".join(str(i) for i in urceno["RK"]) if urceno["RK"] else "SELECT 0 n")
            rk_overeno = cur.fetchone()["n"] if urceno["RK"] else 0
        assert rl_overeno == len(urceno["RL"]), "RL rowcount nesedi: %d != %d" % (rl_overeno, len(urceno["RL"]))
        assert rp_overeno == len(urceno["RP"]), "RP rowcount nesedi: %d != %d" % (rp_overeno, len(urceno["RP"]))
        assert rk_overeno == len(urceno["RK"]), "RK rowcount nesedi: %d != %d" % (rk_overeno, len(urceno["RK"]))

    print("\n%sVYSLEDEK:" % ("[DRY RUN] " if a.dry_run else ""))
    print("  RL (levy):  %d karet" % len(urceno["RL"]))
    print("  RP (pravy): %d karet" % len(urceno["RP"]))
    print("  RK (kabina/prepazka): %d karet" % len(urceno["RK"]))
    print("  zapsano/zmeneno: %d, uz melo spravnou hodnotu: %d" % (zmeneno, beze_zmeny_stejna_hodnota))
    print("  NEURCENO - zadna shoda uuid ve stored_models: %d %s" %
          (len(neurceno_zadna_shoda), neurceno_zadna_shoda if len(neurceno_zadna_shoda) <= 20 else neurceno_zadna_shoda[:20] + ["..."]))
    print("  NEURCENO - nejednoznacne (0 nebo 2+ z left/right/bulkhead vyplneno): %d %s" %
          (len(neurceno_nejednoznacne), neurceno_nejednoznacne))
    celkem_urceno = sum(len(v) for v in urceno.values())
    print("\nSOUHRN: %d/%d karet urceno, %d neurceno (zustava NULL/puvodni hodnota)"
          % (celkem_urceno, len(karty), len(karty) - celkem_urceno))
    if a.dry_run:
        print("\n[DRY RUN] nic se nezapsalo.")
    conn_w.close()
    conn_k.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
