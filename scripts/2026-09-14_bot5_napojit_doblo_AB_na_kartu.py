#!/usr/bin/env python3
"""Napoji 10 sestav Doblo K-075 A/B na existujici kartu 3943 (bot3, 2026-09-14).

Doblo K-075 je JEDNO vozidlo (WORKFLOW.md pravidlo 26 - "karta se ma
jmenovat po vozidle", jedna karta nese vic sestav) - verze A/B jsou jen
dalsi poloha posuvniku "verze" vedle uz napojene C (341-347). Blokuje
to renderovaci davku (bot4 potrebuje shop_product_id, aby mohl sestavy
zaradit do fronty) - Robert primo: "renderovat se bude za chvili".

ID: 369, 370, 374, 376, 379, 380, 382, 383, 384, 385
  369/370 = varianta 01 [ZÁKLAD], 374/376 = 00, 379/382 = 02,
  380/383 = 03, 384/385 = 04

POZOR: 374, 384, 385 jeste nemaji bom/price_summary (bot8 na nich
cenik zatim nedopocital, overeno primo v DB pred timhle skriptem) -
napojuji se STEJNE, cena dojde pozdeji (stejny vzor jako puvodni
scripts/2026-09-12_bot5_karty_10_30.py - "doplni se, az bot8 prepocita
snimek ze sceny"). Render davku to neblokuje, jen zobrazenou cenu na
webu (a ty karty stejne nejsou aktivni master, is_master zustava na 343).

Idempotentni (prepisuje jen tam, kde je shop_product_id NULL). Zaloha
do backups/.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-14_bot5_napojit_doblo_AB_na_kartu.py
    api/venv/bin/python3 scripts/2026-09-14_bot5_napojit_doblo_AB_na_kartu.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-14_bot5_napojit_doblo_AB_na_kartu",
)

KARTA_ID = 3943
ASSEMBLY_IDS = (369, 370, 374, 376, 379, 380, 382, 383, 384, 385)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== napojeni Doblo K-075 A/B na kartu {KARTA_ID} — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sku FROM shop_products WHERE id=%s", (KARTA_ID,))
            karta = cur.fetchone()
            if not karta:
                print(f"CHYBA: karta {KARTA_ID} neexistuje."); return 1
            print(f"Karta: {karta['id']} [{karta['sku']}]\n")

            for aid in ASSEMBLY_IDS:
                cur.execute("SELECT id, name, shop_product_id FROM product_assemblies WHERE id=%s", (aid,))
                r = cur.fetchone()
                if not r:
                    print(f"  id={aid}: sestava neexistuje, preskakuji"); continue
                if r["shop_product_id"] == KARTA_ID:
                    print(f"  id={aid} ({r['name']}): uz napojeno, preskakuji")
                    continue
                if r["shop_product_id"] is not None:
                    print(f"  id={aid} ({r['name']}): POZOR, uz ma jinou kartu ({r['shop_product_id']}), preskakuji!")
                    continue
                print(f"  id={aid} ({r['name']}): shop_product_id NULL -> {KARTA_ID}")
                zaloha.append({"id": aid, "puvodni_shop_product_id": r["shop_product_id"]})
                if args.apply:
                    cur.execute("UPDATE product_assemblies SET shop_product_id=%s WHERE id=%s", (KARTA_ID, aid))

        if args.apply and zaloha:
            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=2)
            conn.commit()
            print("\nCOMMIT hotovy.")
        else:
            print("\nDRY-RUN: nic nezapsano." if not args.apply else "\nNic k zapsani.")
    finally:
        conn.close()

    if args.apply and zaloha:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                print("\n=== OVERENI z noveho spojeni ===")
                cur.execute(
                    f"SELECT id, name, shop_product_id FROM product_assemblies "
                    f"WHERE id IN ({','.join(str(i) for i in ASSEMBLY_IDS)}) ORDER BY id"
                )
                for r in cur.fetchall():
                    znacka = "OK" if r["shop_product_id"] == KARTA_ID else "CHYBA"
                    print(f"  {r['id']} {r['name']}: shop_product_id={r['shop_product_id']} [{znacka}]")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
