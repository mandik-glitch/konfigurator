#!/usr/bin/env python3
"""Oprava regrese: varianta "04" s mezerou u police <70mm nesmi byt
napojena na kartu (bot5, 2026-09-17).

Robertovo pravidlo (2026-09-15, PLAN_TVORBY_SESTAV.md Faze 4, doslova):
"pokud vychazi u sestavy a varianty 04, ze mezera mezi pricasti/profily
horniho bloku je mensi nez 70mm, tato varianta se nebude renderovat ani
zobrazovat na e-shopu, varianta 04 nebude ani v karte, jen jako ulozena
nepouzivana geometrie." K 2026-09-15 to platilo u vsech tehdejsich
takovych sestav (shop_product_id=NULL).

REGRESE: muj vlastni skript z dnesniho rana
(scripts/2026-09-17_bot5_dopojit_nove_schvalene_sestavy.py) napojil
technicky_ok=1 sestavy na existujici karty, ale NEKONTROLOVAL tuhle
dodatecnou geometrickou vyjimku (technicky_ok a "04+mezera<70mm" jsou
DVE NEZAVISLE podminky, viz PLAN_TVORBY_SESTAV.md Faze 2: "technicky_ok
je jedina pojistka - verejne API ji nekontroluje" + samostatna
mezera-podminka o par odstavcu niz). Nasel bot4 (pres bot3), nezavisle
overeno primo v DB pred timhle skriptem (hbv.kod='04' AND
mezera_police_mm<70 AND shop_product_id IS NOT NULL - CELY katalog,
ne jen tyhle 3 ID, zadne dalsi nalezeny).

Postizene: 405 (Jumpy L1 K-121e A-04, mezera 62mm, karta 3948), 409
(K-121e B-04, 47mm, karta 3948), 417 (Jumpy L2 K-122 A-04, 66mm, karta
3946). Zadna z nich neni is_master sve karty - vychozi zobrazeni karty
se nezmeni, zmizi jen nefunkcni volba "04" ze sliderů.

Zaloha pred-stavu uz existuje (bot4):
backups/2026-09-17_mezera04_shop_product_id_fix/pred_zapisem.json -
tenhle skript ji nezavisle overuje shodu a dela VLASTNI zapis zalohu
navic (transparentnost autorstvi zapisu, bot5 provadi UPDATE).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-17_bot5_fix_mezera04_shop_product_id.py
    api/venv/bin/python3 scripts/2026-09-17_bot5_fix_mezera04_shop_product_id.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-17_bot5_fix_mezera04_shop_product_id",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== fix mezera04 shop_product_id — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    try:
        with conn.cursor() as cur:
            # Katalog-siroky audit, ne jen 3 znama ID - presne to, co
            # bot4 doporucil zkontrolovat.
            cur.execute(
                "SELECT pa.id, pa.name, pa.shop_product_id, pa.is_master, pa.mezera_police_mm "
                "FROM product_assemblies pa "
                "JOIN horni_blok_varianty hb ON hb.id=pa.horni_blok_varianta_id "
                "WHERE hb.kod='04' AND pa.mezera_police_mm < 70 AND pa.shop_product_id IS NOT NULL "
                "ORDER BY pa.id"
            )
            rows = cur.fetchall()
            print(f"Nalezeno {len(rows)} porusujicich radku (celý katalog):")
            for r in rows:
                print(f"  id={r['id']} ({r['name']}) mezera={r['mezera_police_mm']}mm "
                      f"karta={r['shop_product_id']} is_master={r['is_master']}")
                zaloha.append(dict(r))
                if r["is_master"]:
                    print(f"    POZOR: is_master=1 - vynulovani by karte sebralo zastupce, "
                          f"NEPROVADIM automaticky, over rucne!")
                    continue
                if args.apply:
                    cur.execute(
                        "UPDATE product_assemblies SET shop_product_id=NULL WHERE id=%s",
                        (r["id"],),
                    )

        if args.apply:
            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
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
                print("\n=== OVERENI z noveho spojeni (mel by byt prazdny vysledek) ===")
                cur.execute(
                    "SELECT pa.id, pa.shop_product_id FROM product_assemblies pa "
                    "JOIN horni_blok_varianty hb ON hb.id=pa.horni_blok_varianta_id "
                    "WHERE hb.kod='04' AND pa.mezera_police_mm < 70 AND pa.shop_product_id IS NOT NULL"
                )
                zbyva = cur.fetchall()
                print(zbyva if zbyva else "OK - zadny zbyvajici porusujici radek.")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
