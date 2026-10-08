#!/usr/bin/env python3
"""Zapise zakaznicky text (`popis_zakaznicky`) do katalogovych tabulek
`horni_blok_varianty` a `typologie_varianty`.

TEXT_FILTR.md pravidlo 13: popis produktu musi byt dynamicky podle vybrane
varianty. Text tady napsany se sklada serverem (viz `product_assemblies_
public()` v api/product_assemblies.py) do per-variantniho odstavce na
produktove strance - psano JEDNOU na katalogovou variantu, znovupouzite na
kazde budouci karte, co tu kombinaci pouzije.

DULEZITE: tenhle text NENI kopie `horni_blok_varianty.lisi_se` /
`typologie_varianty.nazev` - ty jsou INTERNI (admin/bot voice, zminuji
interni oznaceni jako "ZÁKLAD", cisla dilu, poznamky "Robertem oznaceno").
Zakaznicky text je psany podle TEXT_FILTR.md - zadny K-XXX, zadne interni
znacky, popisuje FUNKCI/VZHLED provedeni z pohledu zakaznika.

Idempotentni (prepisuje jen tam, kde je NULL - existujici rucne upraveny
text se neprepisuje). Zaloha do backups/.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-13_bot5_popis_zakaznicky_katalog.py
    api/venv/bin/python3 scripts/2026-09-13_bot5_popis_zakaznicky_katalog.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-13_bot5_popis_zakaznicky_katalog",
)

# klic = horni_blok_varianty.id (podle kod 00-06, sort_order)
HORNI_BLOK_TEXT = {
    1: "Regál je bez horního bloku — celý prostor nad euroboxy zůstává volný.",
    2: "Nad euroboxy je jednoduchý rám jednoho patra, bez desek — lehčí "
       "provedení pro menší zátěž.",
    3: "Nad euroboxy je jedno patro s pevným dnem z MDF desky — hodí se "
       "na odkládání delších nebo plochých předmětů.",
    4: "Nad euroboxy jsou dvě patra rámové konstrukce bez desek a bez "
       "police — otevřený prostor pro dlouhé předměty uložené volně.",
    5: "Nad euroboxy jsou dvě patra s policí v polovině výšky — police "
       "tvoří jen nosné příčky, bez vlastní desky.",
    6: "Nad euroboxy je uzavřený horní prostor s plným opláštěním (dno, "
       "záda, čelo), bez police uprostřed.",
    7: "Nad euroboxy je uzavřený horní prostor s plným opláštěním a policí "
       "uprostřed — dvě oddělená patra k uskladnění, nejbohatší provedení.",
}

# klic = typologie_varianty.id
TYPOLOGIE_VARIANTA_TEXT = {
    63: "Osm euroboxů ve dvou výškových pásmech: 3× box výšky 220 mm, "
        "3× 170 mm a 2× 120 mm.",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== popis_zakaznicky katalogu — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = {"horni_blok_varianty": [], "typologie_varianty": []}
    try:
        with conn.cursor() as cur:
            print("--- horni_blok_varianty ---")
            for id_, text in HORNI_BLOK_TEXT.items():
                cur.execute("SELECT id, nazev, popis_zakaznicky FROM horni_blok_varianty WHERE id=%s", (id_,))
                r = cur.fetchone()
                if not r:
                    print(f"  id={id_}: neexistuje, preskakuji"); continue
                if r["popis_zakaznicky"] is not None:
                    print(f"  id={id_} ({r['nazev']}): uz ma text, preskakuji")
                    continue
                print(f"  id={id_} ({r['nazev']}): {text[:60]}...")
                zaloha["horni_blok_varianty"].append({"id": id_, "puvodni": None, "novy": text})
                if args.apply:
                    cur.execute("UPDATE horni_blok_varianty SET popis_zakaznicky=%s WHERE id=%s", (text, id_))

            print("\n--- typologie_varianty ---")
            for id_, text in TYPOLOGIE_VARIANTA_TEXT.items():
                cur.execute("SELECT id, nazev, popis_zakaznicky FROM typologie_varianty WHERE id=%s", (id_,))
                r = cur.fetchone()
                if not r:
                    print(f"  id={id_}: neexistuje, preskakuji"); continue
                if r["popis_zakaznicky"] is not None:
                    print(f"  id={id_} ({r['nazev']}): uz ma text, preskakuji")
                    continue
                print(f"  id={id_} ({r['nazev']}): {text[:60]}...")
                zaloha["typologie_varianty"].append({"id": id_, "puvodni": None, "novy": text})
                if args.apply:
                    cur.execute("UPDATE typologie_varianty SET popis_zakaznicky=%s WHERE id=%s", (text, id_))

        if args.apply:
            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=2)
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
                cur.execute("SELECT id, popis_zakaznicky FROM horni_blok_varianty ORDER BY sort_order")
                for r in cur.fetchall(): print(" ", r)
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
