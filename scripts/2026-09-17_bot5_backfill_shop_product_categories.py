#!/usr/bin/env python3
"""Backfill sekundarnich kategorii pro existujici aktivni regalove
karty (bot5, 2026-09-17, Robert pres bot7: "kategorie eshopu je
potreba osadit sestavama, at je to videt, takze 1 sestava muze byt na
vice kategoriich").

Bot7 dnes rano postavil a nasadil KATEGORIE_VESTAVBY_ARCHITEKTURA.md -
dva soubezne stromy (podle vozidla / podle typologie) pod kategorii 184.
category_id (primarni, breadcrumb/canonical) zustava u vsech NEZMENENO
(247) - tenhle skript jen PRIDAVA sekundarni kategorie pres novou
shop_product_categories (sql/2026-09-17_shop_product_categories.sql).

Rozsah SIRSI nez bot7 hlasil (overeno nezavisle primo v DB) - bot7
znal jen 6 starsich karet (3943-3948), ale aktivnich regalovych karet
je dnes 9 (pribyly Ford Connect/Vito/Caddy/ProAce z teto session).

Typologie (274 "Regál na euroboxy") je pripravena a plati univerzalne
pro VSECHNY EB karty - pridano vsem 9.

Vozidlo-osa jde priradit JEN tam, kde uz existuje odpovidajici list:
  273 "Vestavby pro Fiat Doblò" (pod 269 Fiat)   -> 3943
  272 "Vestavby pro Citroën Jumpy" (pod 268)     -> 3946, 3947, 3948
Pro Ford (3952/3953)/Mercedes (3954)/VW (3955)/Toyota (3956) ZATIM
neexistuje vhodny list (Ford/Toyota nemaji vubec uzel v 267 vetvi,
Mercedes/VW maji jen znackovy uzel 270/271 bez modeloveho listu) -
VYNECHANO, nehadam/nezakladam nove kategorie sam (cizi domena, bot7).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-17_bot5_backfill_shop_product_categories.py
    api/venv/bin/python3 scripts/2026-09-17_bot5_backfill_shop_product_categories.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-17_bot5_backfill_shop_product_categories",
)

TYPOLOGIE_EB_CATEGORY_ID = 274  # "Regál na euroboxy"

# product_id -> extra sekundarni kategorie (kromě 274, ktera jde vsem)
VOZIDLO_SEKUNDARNI = {
    3943: 273,  # Fiat Doblò
    3946: 272,  # Citroën Jumpy
    3947: 272,
    3948: 272,
    # bot7, 2026-09-17 (dodatek): doplnil chybejici vozidlo-osa uzly
    3952: 280,  # Ford Transit Connect L1
    3953: 280,  # Ford Transit Connect L2
    3954: 283,  # Mercedes Vito
    3955: 284,  # Volkswagen Caddy
    3956: 282,  # Toyota Proace Long
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== backfill shop_product_categories — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sku, name FROM shop_products WHERE sku LIKE 'K-%' AND active=1 ORDER BY id")
            karty = cur.fetchall()
            for k in karty:
                pary = [(k["id"], TYPOLOGIE_EB_CATEGORY_ID)]
                if k["id"] in VOZIDLO_SEKUNDARNI:
                    pary.append((k["id"], VOZIDLO_SEKUNDARNI[k["id"]]))
                for product_id, category_id in pary:
                    cur.execute(
                        "SELECT 1 FROM shop_product_categories WHERE product_id=%s AND category_id=%s",
                        (product_id, category_id),
                    )
                    if cur.fetchone():
                        print(f"  {product_id} ({k['sku']}) -> kategorie {category_id}: uz existuje, preskakuji")
                        continue
                    print(f"  {product_id} ({k['sku']}, {k['name']}) -> kategorie {category_id}")
                    zaloha.append({"product_id": product_id, "category_id": category_id})
                    if args.apply:
                        cur.execute(
                            "INSERT INTO shop_product_categories (product_id, category_id) VALUES (%s,%s)",
                            (product_id, category_id),
                        )

        if args.apply:
            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pridano.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=2, default=str)
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
                print("\n=== OVERENI z noveho spojeni ===")
                cur.execute(
                    "SELECT spc.product_id, sp.sku, spc.category_id, cc.name AS kategorie "
                    "FROM shop_product_categories spc "
                    "JOIN shop_products sp ON sp.id=spc.product_id "
                    "JOIN content_categories cc ON cc.id=spc.category_id "
                    "ORDER BY spc.product_id, spc.category_id"
                )
                for r in cur.fetchall():
                    print(" ", r)
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
