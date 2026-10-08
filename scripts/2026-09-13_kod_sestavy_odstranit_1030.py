#!/usr/bin/env python3
"""Odstrani prebytecny segment "-1030" z product_assemblies.kod_sestavy.

Robert 2026-09-13 v chatu, po digit-po-digitu revizi kodu sestavy: "10/30
budou vsechny regaly, tato informace v SKU je k nicemu" - kolizni rezerva
10/30mm uz neni rozlisujici udaj (bude platit univerzalne pro vsechny
regaly), takze nepatri do kodu. Stejnou vadu uz opravil bot5 na urovni
SKU KARTY (shop_products.sku, viz scripts/2026-09-13_bot5_sku_do_konvence.py)
- tenhle skript resi stejnou vadu na urovni `kod_sestavy` JEDNOTLIVE
SESTAVY, coz bot5uv skript nemenil.

Rozsah: dnes presne 7 radku (341-347, Doblo C vzor) - jsou to jedine
sestavy v cele tabulce, ktere maji kod_sestavy vubec vyplneny.

Bezpecnost: kod_sestavy neni FK cil odjinud (shop_order_items dnes vazbu
na konkretni sestavu vubec nema - samostatna otevrena otazka u bot5),
takze zmena stringu nic jineho nerozbiji. Idempotentni, zaloha do
backups/, kontrola kolize po odstraneni suffixu pred zapisem.

Pouziti:
    python3 scripts/2026-09-13_kod_sestavy_odstranit_1030.py            # dry-run
    python3 scripts/2026-09-13_kod_sestavy_odstranit_1030.py --apply    # zapis
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_PATH = os.path.join(REPO_ROOT, "backups", "2026-09-13_kod_sestavy_pred_odstranenim_1030.json")

APPLY = "--apply" in sys.argv
SUFFIX = "-1030"


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, kod_sestavy FROM product_assemblies WHERE kod_sestavy LIKE %s ORDER BY id",
                (f"%{SUFFIX}",))
    radky = cur.fetchall()
    print(f"[nalezeno {len(radky)} sestav s '{SUFFIX}' na konci kod_sestavy]")

    zaloha = []
    zmeny = []
    for r in radky:
        stary = r["kod_sestavy"]
        if not stary.endswith(SUFFIX):
            continue
        novy = stary[: -len(SUFFIX)]
        cur.execute("SELECT id FROM product_assemblies WHERE kod_sestavy=%s AND id<>%s", (novy, r["id"]))
        kolize = cur.fetchone()
        if kolize:
            print(f"  [{r['id']}] ⛔ KOLIZE - '{novy}' už má sestava {kolize['id']}, přeskočeno")
            continue
        print(f"  [{r['id']}] {stary} -> {novy}")
        zaloha.append({"id": r["id"], "puvodni_kod_sestavy": stary, "novy_kod_sestavy": novy})
        zmeny.append((novy, r["id"]))

    if APPLY and zmeny:
        os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
        with open(BACKUP_PATH, "w", encoding="utf-8") as f:
            json.dump(zaloha, f, ensure_ascii=False, indent=2)
        for novy, pid in zmeny:
            cur.execute("UPDATE product_assemblies SET kod_sestavy=%s WHERE id=%s", (novy, pid))
        conn.commit()
        print(f"\nAPLIKOVÁNO, změněno {len(zmeny)} sestav. Záloha: {BACKUP_PATH}")
    elif APPLY:
        print("\nNic ke změně.")
    else:
        conn.rollback()
        print(f"\nDRY-RUN, nic nezapsáno. Ke změně: {len(zmeny)}. Spusť s --apply pro zápis.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
