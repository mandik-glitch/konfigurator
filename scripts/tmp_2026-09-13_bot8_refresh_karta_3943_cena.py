#!/usr/bin/env python3
"""Prepis shop_products.price_czk_placeholder pro kartu 3943 na aktualni
total_czk zastupce (#343), po oprave joint_czk=0 gapu v
2026-09-06_backfill_bom_price.js (viz AGENTS_LOG.md 2026-09-13).

Stara hodnota (15247 Kc) pochazela z bot5 scripts/2026-09-13_bot5_cena_karty_
ze_zastupce.py, zapsana PRED touhle opravou - byla podhodnocena o celou cenu
spoju zastupce (#343 mela drive joint_czk=0). Ten skript uz existujici cenu
neprepise (jen NULL->cena), proto tenhle jednorazovy prepis - odsouhlaseno
bot5 (SendMessage 2026-09-13, "Prepis... je v poradku, diky za info").

Karty 3944/3945 se NEDOTYKA (zadny zastupce, price_czk_placeholder=NULL,
mimo scope - viz bot5 skript).

    api/venv/bin/python3 scripts/tmp_2026-09-13_bot8_refresh_karta_3943_cena.py [--apply]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-13_bot8_refresh_karta_3943_cena",
)
PRODUCT_ID = 3943


def main():
    apply = "--apply" in sys.argv
    print(f"=== Refresh cena karty {PRODUCT_ID} ze zastupce (po oprave joint gapu) — "
          f"{'APPLY' if apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sku, price_czk_placeholder FROM shop_products WHERE id=%s", (PRODUCT_ID,))
            karta = cur.fetchone()
            if not karta:
                print("Karta nenalezena."); return 1

            cur.execute(
                "SELECT id, data FROM product_assemblies WHERE shop_product_id=%s AND is_master=1",
                (PRODUCT_ID,),
            )
            rows = cur.fetchall()
            if len(rows) != 1:
                print(f"Ocekaval jsem 1 zastupce, mam {len(rows)} - koncim."); return 1
            zid = rows[0]["id"]
            d = json.loads(rows[0]["data"])
            nova = d.get("price_summary", {}).get("total_czk")
            if nova is None:
                print("Zastupce nema spocitanou cenu."); return 1
            nova = round(float(nova))

            stara = karta["price_czk_placeholder"]
            print(f"Karta {PRODUCT_ID} [{karta['sku']}]: {stara} Kc -> {nova} Kc (ze zastupce #{zid})")

            if not apply:
                print("\nDRY-RUN: nic nezapsano.")
                return 0

            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump({"product_id": PRODUCT_ID, "sku": karta["sku"],
                           "puvodni_price_czk_placeholder": str(stara) if stara is not None else None,
                           "nova": nova, "ze_sestavy": zid}, f, ensure_ascii=False, indent=2)

            cur.execute("UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s", (nova, PRODUCT_ID))
            cur.execute(
                "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) "
                "VALUES (NULL,'update','shop_product',%s,%s)",
                (PRODUCT_ID, f"bot8 skript 2026-09-13: cena prepsana {stara} -> {nova} Kc "
                              f"(oprava joint_czk=0 gapu v backfillu, viz AGENTS_LOG.md)"),
            )
        conn.commit()
        print("COMMIT hotovy.")
    finally:
        conn.close()

    if apply:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute("SELECT id, sku, price_czk_placeholder FROM shop_products WHERE id=%s", (PRODUCT_ID,))
                r = cur.fetchone()
                print(f"OVERENO z noveho spojeni: {r['id']} [{r['sku']}] = {r['price_czk_placeholder']} Kc")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
