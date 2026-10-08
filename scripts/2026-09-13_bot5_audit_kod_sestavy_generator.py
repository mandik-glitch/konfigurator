#!/usr/bin/env python3
"""Over, ze ULOZENY `kod_sestavy` odpovida cerstve VYGENEROVANEMU podle
kanonickeho generatoru `scripts/_kod_sestavy.py::sestavit_kod_sestavy()`.

Vznik (Robert, 2026-09-13): "pouzij generator SKU na stavajici schvalene
sestavy". Pruzkumem se zjistilo, ze v tu chvili UZ VSECH 7 schvalenych
sestav (technicky_ok=1) melo kartu - zadny "backlog bez karty" k
zalozeni neexistoval. Ukol se tedy zmenil na OVERENI: sedi ulozeny
kod_sestavy s tim, co by generator vyrobil TEDY, po dnesnich zmenach
formatu (umisteni segment, dvojciferny horni blok, zmizely -1030)?

Vysledek 2026-09-13: 0 neshod ze 7 (341-347) - bot8 uz prepocital drive,
nez sem tenhle ukol dorazil.

ZNOVUPOUZITELNE: az pribudou dalsi schvalene sestavy (nebo se format
generatoru zase zmeni), spustit znovu - jen CTE a hlasi, nic nezapisuje.
Kdyz najde neshodu, je to signal pro precteni s bot8 (kdo kod_sestavy
zapisuje), ne pro tichou automatickou opravu odsud.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-13_bot5_audit_kod_sestavy_generator.py
    api/venv/bin/python3 scripts/2026-09-13_bot5_audit_kod_sestavy_generator.py --vse   # i neschvalene
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402
from _kod_sestavy import sestavit_kod_sestavy  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vse", action="store_true",
                     help="i neschvalene sestavy (vychozi jen technicky_ok=1)")
    args = ap.parse_args()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = "" if args.vse else "WHERE pa.technicky_ok=1"
            cur.execute(f"""
                SELECT pa.id, pa.kod_sestavy AS ulozeny, pa.karoserie_kod, pa.profil_mm,
                       pa.verze, pa.dodatek, pa.shop_product_id,
                       ru.kod AS umisteni_kod, rt.kod AS typologie_kod,
                       tv.kod AS varianta_kod, hb.kod AS horni_blok_kod
                FROM product_assemblies pa
                LEFT JOIN regal_umisteni ru ON ru.id = pa.umisteni_id
                LEFT JOIN regal_typologie rt ON rt.id = pa.typologie_id
                LEFT JOIN typologie_varianty tv ON tv.id = pa.typologie_varianta_id
                LEFT JOIN horni_blok_varianty hb ON hb.id = pa.horni_blok_varianta_id
                {where}
                ORDER BY pa.id
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    print(f"=== audit kod_sestavy vs. kanonicky generator ({'vsechny' if args.vse else 'jen schvalene'}, {len(rows)} sestav) ===\n")
    neshody = []
    for r in rows:
        novy = sestavit_kod_sestavy(
            karoserie_kod=r["karoserie_kod"], umisteni_kod=r["umisteni_kod"],
            typologie_kod=r["typologie_kod"], profil_mm=r["profil_mm"],
            verze=r["verze"], varianta_kod=r["varianta_kod"],
            horni_blok_kod=r["horni_blok_kod"], dodatek=r["dodatek"],
        )
        if novy != r["ulozeny"]:
            neshody.append((r["id"], r["ulozeny"], novy, r["shop_product_id"]))

    if not neshody:
        print(f"  0 neshod z {len(rows)} — vse sedi s aktualnim generatorem.")
        return 0

    print(f"  {len(neshody)} neshod:")
    for aid, ulozeny, novy, pid in neshody:
        print(f"    id={aid:>4}  karta={pid}")
        print(f"       ulozeny={ulozeny!r}")
        print(f"       novy   ={novy!r}")
    print("\n  Nic se nezapisuje - kod_sestavy zapisuje bot8. Nahlas neshody jemu.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
