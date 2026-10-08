#!/usr/bin/env python3
"""Doplni `product_assemblies.profil_mm = 30` u vsech sestav, kde je NULL.

Robert 2026-09-13 v chatu, primo: "vsechny dosavadni sestavy jsou z
profilu 30". Overeno pred zapisem: DNES nema ZADNA sestava profil_mm
nastaveny na jinou hodnotu nez 30 nebo NULL (0 vyjimek) - Robertovo
tvrzeni tedy nekoliduje se zadnymi jiz zapsanymi daty.

PROC PLOSNE, NE JEN U JUMPY: Robert to rekl jako obecny fakt o CELEM
dosavadnim katalogu ("vsechny dosavadni sestavy"), ne jen o dvou kartach,
kolem kterych se zrovna resil SKU. Zuzit to jen na Jumpy by bylo mensi
zadani, nez jake padlo.

PROC NA TOM ZALEZI (WORKFLOW.md pravidlo o SKU/kod_sestavy, 2026-09-11):
"profil se nehada z geometrie, urcuje ho admin" - dosud radeji chybejici
nez uhodnuty. Ted uz neni uhodnuty, je RECENY primo adminem (Robertem) -
tim padem prestava byt duvod nechat ho prazdny. profil_mm je JEDNA z
podminek, aby se `product_assemblies.kod_sestavy` vubec vygeneroval
(viz scripts/_kod_sestavy.py::sestavit_kod_sestavy - vraci None, kdyz
chybi karoserie/umisteni/typologie/profil NEBO verze/varianta/blok).
Doplnenim profil_mm se tedy NEKTERYM sestavam kod_sestavy rozgeneruje
poprve - ale jen tem, kde uz jsou vyplnene i OSTATNI vstupy (typologie,
umisteni, verze...). Tenhle skript sam kod_sestavy NEPOCITA ani
NEZAPISUJE - to dela az bot8uv `_generate_kod_sestavy_column()`/vlastni
prepocet po tomhle zapisu (nebo `_kod_sestavy.py` znovu spusteny nad
aktualizovanymi radky), tenhle skript jen doplnuje ten JEDEN sloupec.

BEZPECNOST
----------
Zapisuje POUZE tam, kde je `profil_mm IS NULL` - existujici hodnotu
(dnes vsude 30 nebo NULL, zadna jina) nikdy neprepise. Idempotentni,
zaloha do `backups/`.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-13_bot5_profil_mm_30_dosavadni.py
    api/venv/bin/python3 scripts/2026-09-13_bot5_profil_mm_30_dosavadni.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-13_bot5_profil_mm_30_dosavadni",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== profil_mm = 30 u dosavadnich sestav — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Sanity pred zapisem: opravdu nikde neni jina hodnota nez
            # NULL/30? Kdyby ano, koncim bez zasahu - tvrzeni "vsechny
            # dosavadni" by pak neplatilo bezvyjimecne.
            cur.execute(
                "SELECT COUNT(*) n FROM product_assemblies "
                "WHERE profil_mm IS NOT NULL AND profil_mm <> 30"
            )
            jine = cur.fetchone()["n"]
            if jine:
                print(f"  ⛔ {jine} sestav ma profil_mm JINY nez 30 - koncim bez zasahu, "
                      "over rozpor s Robertem")
                return 1

            cur.execute("SELECT id, name FROM product_assemblies WHERE profil_mm IS NULL ORDER BY id")
            k_doplneni = cur.fetchall()
            print(f"  sestav k doplneni (profil_mm NULL -> 30): {len(k_doplneni)}")

            if args.apply and k_doplneni:
                os.makedirs(ZALOHA_DIR, exist_ok=True)
                with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                    json.dump([{"id": r["id"], "name": r["name"]} for r in k_doplneni],
                              f, ensure_ascii=False, indent=2)
                cur.execute("UPDATE product_assemblies SET profil_mm=30 WHERE profil_mm IS NULL")
                zmeneno = cur.rowcount
                print(f"  UPDATE ovlivnil {zmeneno} radku")

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
                cur.execute("SELECT profil_mm, COUNT(*) n FROM product_assemblies GROUP BY profil_mm")
                print("\n=== OVERENI z noveho spojeni ===")
                for r in cur.fetchall(): print("  ", r)
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
