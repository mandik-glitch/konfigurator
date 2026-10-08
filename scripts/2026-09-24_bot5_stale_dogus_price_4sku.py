#!/usr/bin/env python3
"""Oprava 4 produktu nalezenych plosnym auditem bota3 po fixu kategorie
196 (WORKFLOW.md pravidlo "po nalezu korupce auditovat cely objekt").

DULEZITA OPRAVA VLASTNI DRIVEJSI CHYBY: v hlaseni k fixu kategorie 196
jsem tvrdil, ze "JS kalkulacka delka(mm)->cena/hmotnost" na strance
produktu (funkce go()/goCalculate(), "Please choose length in mm!") je
dukaz, ze produkt se prodava po metrech. To je SPATNE - ten kalkulator
("dvSehim"/"F (Load)"/"L (Profile length)"/"I = Moment of inertia") je
OBECNY prohybovy/staticky vypocet pritomny na VSECH strankach profilove
rodiny produktu, nezavisle na tom, jestli se dany produkt prodava na
delku nebo po kusech - overeno: je pritomny i na strankach #3172/#3386/
#3181 nize, ktere jsou jednoznacne KUSOVE zbozi (kolecko, matice).

SPRAVNY signal (dohledano znovu, tentokrat opravdu produkt-specificky):
skryte pole `hdnStockQuantityUnitValue` v tabulce variant na strance
produktu - u kategorie 196 (potvrzeno na 2713 slot-seal-6 i 5651
in-slot-u-seal) ma hodnotu "3000" (= 3m skladova jednotka, presne nase
"1 ks = 3000 mm"). U vsech 4 produktu nize ma hodnotu "0" (zadna delkova
skladova jednotka - kusove zbozi). Kategorie 196 zustava spravne
opravena (jiny fix, commit 0bda7d96) - tenhle skript ji nemeni.

a) #3172, #3173 (kategorie 203 "Plastové kluzáky", Dogus kategorie
   "slide-rails") - CHYBNE spocitane profilovym vzorcem (x3), ale
   StockQuantityUnitValue=0 rika, ze to je kusove zbozi. is_profile_material
   zustava 0 (uz spravne). Oprava: prepocet NA NE-profilovy vzorec
   (ceil(usd x kurz x koef), BEZ x3) s cerstvym zivym kurzem.

b) #3386 (kat. 177 "Vodící kolečka"), #3181 (kat. 204 "T Matice otočné") -
   stary/propadly kurz (21,6612 misto aktualne pouzivaneho 21,87637 u
   sousedu ve stejne kategorii), cena navic NESEDI ani na vlastni
   ulozene usd*rate*koef (napr. #3386: 5,39 x 21,6612 x 1,2 = 140,1 ->
   ceil 141, v DB 156 - neshoda i pri stare sazbe). Overeno
   `audit_log` - zadny rucni zasah na cenu techto SKU (jen jeden
   nesouvisejici zaznam scene_visibility u #3386), price_last_refreshed_at
   obou je O NĚCO DŘÍVĚJŠÍ nez u sousedu ve stejne kategorii ve stejnem
   dni (2026-09-20) - vypada na "propadlou polozku" z dřívější dílčí
   davky, ne zamerny override. Oprava: prepocet ne-profilovym vzorcem s
   cerstvym zivym kurzem (stejny vzorec jako predtim, jen aktualni kurz).

VZOREC (vsechny 4, stejny): cena_za_ks_czk = ceil(dogus_list_price_usd x
kurz_fio_zivy x koeficient_kategorie). dogus_list_price_usd se NEMENI
(neni zpochybnen, jen kurz+vysledek). is_profile_material, weight_g,
description se NEMENI u zadneho ze 4 (uz spravne, zadny "délka tyče"
narok v popisu).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-24_bot5_stale_dogus_price_4sku.py
    api/venv/bin/python3 scripts/2026-09-24_bot5_stale_dogus_price_4sku.py --apply
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api"))
from _env import get_conn  # noqa: E402
from fio_rate import fetch_fio_usd_czk_sell_rate  # noqa: E402

TARGET_IDS = (3172, 3173, 3386, 3181)
BACKUP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-24_stale_dogus_price_4sku_pred_zapisem.json",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== 4 SKU mimo cenovy vzorec - oprava — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    fio_rate = fetch_fio_usd_czk_sell_rate()
    print(f"Kurz Fio banka USD/CZK (prodej), živá hodnota: {fio_rate}\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(TARGET_IDS))
            cur.execute(
                f"SELECT p.id, p.sku, p.name, p.category_id, p.is_profile_material, p.price_czk_placeholder, "
                f"p.dogus_list_price_usd, p.dogus_price_rate_used, c.dogus_price_coefficient "
                f"FROM shop_products p JOIN content_categories c ON c.id=p.category_id "
                f"WHERE p.id IN ({placeholders})",
                TARGET_IDS,
            )
            rows = {r["id"]: r for r in cur.fetchall()}

            zmeny = []
            for pid in TARGET_IDS:
                r = rows.get(pid)
                if not r:
                    print(f"  ⛔ id={pid}: nenalezeno, přeskakuji")
                    continue
                usd = float(r["dogus_list_price_usd"])
                coef = float(r["dogus_price_coefficient"])
                novy = math.ceil(usd * fio_rate * coef)
                zmeny.append({
                    "id": pid, "sku": r["sku"], "name": r["name"],
                    "old_price_czk": float(r["price_czk_placeholder"]), "new_price_czk": novy,
                    "old_rate": float(r["dogus_price_rate_used"]), "new_rate": fio_rate,
                    "usd": usd, "coef": coef,
                })
                print(f"[{pid}] {r['sku']}: {usd} USD x {fio_rate} x {coef} = {usd*fio_rate*coef:.4f} -> "
                      f"ceil={novy} Kč (bylo {r['price_czk_placeholder']} Kč, kurz {r['dogus_price_rate_used']})")

            if args.apply and zmeny:
                os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
                with open(BACKUP_PATH, "w", encoding="utf-8") as f:
                    json.dump(zmeny, f, ensure_ascii=False, indent=2)
                print(f"\nZáloha zapsána do {BACKUP_PATH}")
                for z in zmeny:
                    cur.execute(
                        "UPDATE shop_products SET price_czk_placeholder=%s, dogus_price_rate_used=%s, "
                        "price_last_refreshed_at=NOW() WHERE id=%s",
                        (z["new_price_czk"], fio_rate, z["id"]),
                    )
                    if cur.rowcount != 1:
                        raise RuntimeError(f"UPDATE id={z['id']} zasáhl {cur.rowcount} řádků místo 1 - rollback")
                conn.commit()
                print(f"HOTOVO: zapsáno {len(zmeny)} produktů.")
            elif not args.apply:
                print(f"\nDRY-RUN: bylo by upraveno {len(zmeny)} produktů (spusť s --apply pro zápis).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
