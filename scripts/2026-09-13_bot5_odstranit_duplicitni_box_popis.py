#!/usr/bin/env python3
"""Odstrani ze statickeho popisu karty vse, co uz rika DYNAMICKA cast.

Robert (screenshot detailu 3943): "text popisu sestavy se duplikuje", pak
zpresnil obecnym pravidlem: "ve statické části nemůže být to, co je v
dynamické." Tedy NE jen jedna nahodna duplicita - staticky popis
(shop_products.description) NESMI restatovat NIC, co uz rika dynamicka
cast (typologie_varianty/horni_blok_varianty.popis_zakaznicky nebo
regal_umisteni.kotveni_zakaznicky/montaz_zakaznicky).

Na karte 3943 to byly DVE mista, ne jedno:
  1. Veta o konfiguraci boxu - skoro identicke zneni jako
     `typologie_varianty.popis_zakaznicky` (presna duplicita).
  2. Priklady konkretnich provedeni horniho bloku ("od samotneho ramu po
     plnou vypln s policí") - PARAFRAZOVANY vycet toho, co uz rikaji
     jednotliva `horni_blok_varianty.popis_zakaznicky` (id=2 "jednoduchý
     rám", id=7 "plné opláštění a policí"). Neni to doslovna shoda, ale
     porusuje to stejne pravidlo - obecna veta "vyberete si z nekolika
     provedeni" smi zustat (rika, ze VOLBA existuje, coz dynamicka cast
     nerika), ale VYPIS KONKRETNICH PRIKLADU z ni musi pryc - to uz je
     obsah, ktery patri vyhradne dynamicke casti.

Stejny bezpecnostni vzor jako drivejsi odstraneni duplicitni montazni
vety (`2026-09-13_bot5_odstranit_staticky_montaz_z_karty.py`) - hleda
PRESNY znamy text, pri neshode kartu PRESKOCI (nikdy needituje
priblizne).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-13_bot5_odstranit_duplicitni_box_popis.py
    api/venv/bin/python3 scripts/2026-09-13_bot5_odstranit_duplicitni_box_popis.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-13_bot5_odstranit_duplicitni_box_popis",
)

# karta_id -> seznam PRESNYCH useku textu k odstraneni (kazdy zvlast
# overeny presnou shodou pred zapisem)
OPRAVY = {
    3943: [
        # 1) presna duplicita s typologie_varianty.popis_zakaznicky
        " Základní skladba nese osm euroboxů ve dvou výškových "
        "pásmech – 3× box výšky 220 mm, 3× 170 mm a 2× 120 mm.",
        # 2) parafrazovany vycet konkretnich provedeni horniho bloku -
        # tohle uz rikaji jednotliva horni_blok_varianty.popis_zakaznicky
        " – od samotného rámu po plnou výplň s policí",
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== odstraneni duplicitni vety o konfiguraci boxu — "
          f"{'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    try:
        with conn.cursor() as cur:
            for pid, useky in OPRAVY.items():
                cur.execute("SELECT id, sku, description FROM shop_products WHERE id=%s", (pid,))
                r = cur.fetchone()
                if not r:
                    print(f"  {pid}: karta neexistuje, preskakuji"); continue
                popis = r["description"] or ""
                novy = popis
                nalezeno = 0
                for usek in useky:
                    if usek in novy:
                        novy = novy.replace(usek, "")
                        nalezeno += 1
                    else:
                        print(f"  {pid} [{r['sku']}]: usek nenalezen, preskakuji jen jej: {usek[:50]!r}")
                if not nalezeno:
                    print(f"  {pid} [{r['sku']}]: ZADNY usek nenalezen, karta beze zmeny")
                    continue
                print(f"  {pid} [{r['sku']}]: odstraneno useku: {nalezeno}/{len(useky)} "
                      f"({len(popis)} -> {len(novy)} znaku)")
                print(f"       PO OPRAVE:\n{novy}")
                zaloha.append({"id": pid, "puvodni_description": popis})
                if args.apply:
                    cur.execute("UPDATE shop_products SET description=%s WHERE id=%s", (novy, pid))

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
                for pid, useky in OPRAVY.items():
                    cur.execute("SELECT description FROM shop_products WHERE id=%s", (pid,))
                    d = cur.fetchone()["description"] or ""
                    zbyle = [u for u in useky if u in d]
                    print(f"  {pid}: usek porad pritomny? {'ANO - CHYBA: ' + repr(zbyle) if zbyle else 'ne, OK'}")
                    print(f"       {d}")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
