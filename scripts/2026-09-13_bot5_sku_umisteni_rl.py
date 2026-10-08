#!/usr/bin/env python3
"""Doplni segment umisteni (RL) do SKU karty 3943.

Navazuje na `2026-09-13_bot5_sku_do_konvence.py` (ten srovnal SKU na
karoserie-typologie-profil). Mezitim pribyl novy sloupec
`product_assemblies.umisteni_id` (viz `regal_umisteni`, komentar bot9) a
Robert potvrdil umisteni vsech sedmi sestav vzoru Doblo C (341-347) jako
**RL** (regal levy) - `kod_sestavy` uz to nese (commit `c82465e9`):
`K-075-EB-30-C-0063-03-0` -> `K-075-RL-EB-30-C-0063-03-0`.

PROC SE SKU MENI ZNOVU
----------------------
Pravidlo pro SKU karty je "spolecny (levy) prefix kod_sestavy vsech
navazanych sestav, v KANONICKEM PORADI segmentu" (karoserie-umisteni-
typologie-profil-verze-rozpis-blok-dodatek). Umisteni je ted SOUCASTI
tohoto poradi, hned za karoserii - a je spolecne vsem sedmi sestavam na
karte 3943 (vsechny maji umisteni_id=1/RL). Podle stejneho pravidla, podle
ktereho SKU obsahuje karoserii/typologii/profil, proto MUSI obsahovat i
umisteni.

Bez teto zmeny by SKU `K-075-EB-30` KOLIDOVALO, kdyz casem vznikne
i pravostranny regal (RP) se stejnou typologii/profilem - obe karty by
chtely totez SKU. `K-075-RL-EB-30` tomu predchazi.

ROZSAH: JEN karta 3943
-----------------------
Sestavy karet 3944/3945 (Jumpy) maji `umisteni_id IS NULL` (a taky
`kod_sestavy IS NULL`, chybi profil_mm) - na ne se tohle netyka, dokud
Robert jejich umisteni neurci.

BEZPECNOST
----------
Stejne pojistky jako predchozi SKU skript: kontrola `shop_order_items`
(SKU se nemeni, kdyz na produktu visi objednavka), kontrola kolize SKU,
idempotence, zaloha do `backups/`.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-13_bot5_sku_umisteni_rl.py
    api/venv/bin/python3 scripts/2026-09-13_bot5_sku_umisteni_rl.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-13_bot5_sku_umisteni_rl",
)

PRODUCT_ID = 3943
STARE_SKU = "K-075-EB-30"
NOVE_SKU = "K-075-RL-EB-30"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== SKU + umisteni (RL) — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sku, active, is_archived FROM shop_products WHERE id=%s",
                (PRODUCT_ID,),
            )
            r = cur.fetchone()
            if not r:
                print(f"  karta {PRODUCT_ID} neexistuje, koncim"); return 1
            if r["sku"] == NOVE_SKU:
                print(f"  karta {PRODUCT_ID} uz ma {NOVE_SKU}, nic k udelani"); return 0
            if r["sku"] != STARE_SKU:
                print(f"  ⛔ karta {PRODUCT_ID} ma neocekavane SKU {r['sku']!r} "
                      f"(cekal jsem {STARE_SKU!r}), koncim bez zasahu")
                return 1

            # Sanity: vsechny navazane sestavy opravdu maji umisteni RL a
            # kod_sestavy uz to nese - jinak by prejmenovani karty predbihalo
            # data na sestavach.
            cur.execute(
                "SELECT id, kod_sestavy, umisteni_id FROM product_assemblies "
                "WHERE shop_product_id=%s", (PRODUCT_ID,),
            )
            sestavy = cur.fetchall()
            spatne = [s for s in sestavy if s["umisteni_id"] != 1
                      or not (s["kod_sestavy"] or "").startswith("K-075-RL-")]
            if spatne:
                print(f"  ⛔ {len(spatne)} sestav nema umisteni RL / kod_sestavy s RL, koncim:")
                for s in spatne: print("     ", s)
                return 1
            print(f"  {len(sestavy)} navazanych sestav, vsechny umisteni RL — OK")

            cur.execute("SELECT COUNT(*) n FROM shop_order_items WHERE product_id=%s", (PRODUCT_ID,))
            pocet = cur.fetchone()["n"]
            if pocet:
                print(f"  ⛔ na karte visi {pocet} polozek objednavek, koncim bez zasahu")
                return 1

            cur.execute("SELECT id FROM shop_products WHERE sku=%s", (NOVE_SKU,))
            kolize = cur.fetchone()
            if kolize:
                print(f"  ⛔ SKU {NOVE_SKU} uz ma karta {kolize['id']}, koncim bez zasahu")
                return 1

            print(f"  {PRODUCT_ID}: {STARE_SKU} -> {NOVE_SKU}")
            if args.apply:
                os.makedirs(ZALOHA_DIR, exist_ok=True)
                with open(os.path.join(ZALOHA_DIR, "pred_zmenou.json"), "w", encoding="utf-8") as f:
                    json.dump({"product_id": PRODUCT_ID, "puvodni_sku": STARE_SKU,
                               "nove_sku": NOVE_SKU}, f, ensure_ascii=False, indent=2)
                cur.execute("UPDATE shop_products SET sku=%s WHERE id=%s", (NOVE_SKU, PRODUCT_ID))
                cur.execute(
                    "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) "
                    "VALUES (NULL,'update','shop_product',%s,%s)",
                    (PRODUCT_ID, f"bot5 skript 2026-09-13: SKU {STARE_SKU} -> {NOVE_SKU} "
                                 f"(doplneno umisteni RL, potvrzeno Robertem, viz commit c82465e9)"),
                )
        if args.apply:
            conn.commit()
            print("\nCOMMIT hotovy.")
        else:
            print("\nDRY-RUN: nic nezapsano.")
    finally:
        conn.close()

    if args.apply:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute("SELECT id, sku FROM shop_products WHERE id=%s", (PRODUCT_ID,))
                print("\n=== OVERENI z noveho spojeni ===")
                print(" ", cur.fetchone())
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
