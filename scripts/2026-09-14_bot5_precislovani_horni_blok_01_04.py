#!/usr/bin/env python3
"""Precislovani horni_blok_varianty na cistou radu 01-04 pro K-075 (bot5,
2026-09-14, mapovani navrzeno a overeno bot8, potvrzeno primo Robertem:
"jestli ze nyni delame varianty hor bloku 01 a 04 musi mit v SKU na
prislusnem segmentu cisla 01 - 04").

Kontext: Doblo K-075 A/B/C horni-blokove varianty dnes drzi kody
04,05,06,07 (viz scripts/2026-09-14_bot5_doraz_deska_horni_blok.py) -
neformalni nazvy sestav uz rikaji "01".."04" (product_assemblies.name),
ale technicky kod_sestavy segment horniho bloku tomu neodpovidal. Kody
00-03 byly obsazene jinym obsahem (00=bez bloku [269 univerzalnich
uzivatelu, NEMENI SE], 01=stary "jen ram" [0 zivych uzivatelu], 02=Jumpy
K-118/K-119 "jen ram+dna bez dorazu" [6 zivych sestav, karty 3944/3945],
03=stary "dve pasma jen ram" [0 zivych uzivatelu]) - proto novy radek
kod=07 pri drivejsim opravnem kroku.

Robert dnes: "Jumpy horni bloky me nezajimaji... prevezmou to vsichni
dalsi vcetne tveho Jumpy" (Doblo A/B horni blok = nova norma pro male
dodavky do budoucna) + primo potvrdil, ze SKU MA cislovat 01-04. Reseni
(bot8): Jumpy NEMAZAT/NEROZBIT - jen presunout na nove volne cislo "08"
(OBSAH/geometrie beze zmeny, len kod), stejne 0-uzivatelove radky 01/03
presunout na 09/10 (jen aby neblokovaly cilova cisla).

ZMENA JEN SLOUPCE `kod` v horni_blok_varianty (8 radku, id=1 kod
00->00 se NEMENI/preskakuje) + prepocet `kod_sestavy` (jen segment
horniho bloku, ostatnich 7 segmentu beze zmeny) u 18 sestav (12 K-075 +
6 Jumpy) pres kanonicky _kod_sestavy.py::sestavit_kod_sestavy().
`horni_blok_varianta_id` FK se NEMENI (stale stejne radky, jen jine
`kod` cislo na nich).

Poradi UPDATE na `kod` (UNIQUE) je zvoleno tak, aby zadny mezikrok
nekolidoval s jeste neuvolnenou cilovou hodnotou:
  2(01->09), 3(02->08), 4(03->10), 8(07->01), 5(04->02), 6(05->03), 7(06->04)

Zaloha do backups/, idempotentni (dry-run porovnava aktualni kod proti
cilovemu stavu).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-14_bot5_precislovani_horni_blok_01_04.py
    api/venv/bin/python3 scripts/2026-09-14_bot5_precislovani_horni_blok_01_04.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402
from _kod_sestavy import sestavit_kod_sestavy  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-14_bot5_precislovani_horni_blok_01_04",
)

# (id, novy_kod) - v BEZPECNEM poradi (vacating pred occupying, viz docstring)
KOD_ZMENY = [
    (2, "09"),
    (3, "08"),
    (4, "10"),
    (8, "01"),
    (5, "02"),
    (6, "03"),
    (7, "04"),
]

# assembly_id -> cilovy novy horni_blok kod (pro prepocet kod_sestavy)
ASSEMBLY_NOVY_BLOK_KOD = {
    344: "01", 369: "01", 370: "01",
    343: "02", 379: "02", 382: "02",
    345: "03", 380: "03", 383: "03",
    347: "04", 384: "04", 385: "04",
    348: "08", 349: "08", 350: "08", 351: "08", 353: "08", 354: "08",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== precislovani horni_blok_varianty na 01-04 (K-075) + 08 (Jumpy) — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = {"kod_zmeny": [], "kod_sestavy_zmeny": []}
    try:
        with conn.cursor() as cur:
            print("--- krok 1: horni_blok_varianty.kod ---")
            for hid, novy_kod in KOD_ZMENY:
                cur.execute("SELECT id, kod, nazev FROM horni_blok_varianty WHERE id=%s", (hid,))
                r = cur.fetchone()
                if not r:
                    print(f"  id={hid}: neexistuje, preskakuji"); continue
                if r["kod"] == novy_kod:
                    print(f"  id={hid} ({r['nazev']}): uz ma kod={novy_kod}, preskakuji")
                    continue
                print(f"  id={hid} ({r['nazev']}): kod {r['kod']} -> {novy_kod}")
                zaloha["kod_zmeny"].append({"id": hid, "puvodni_kod": r["kod"], "novy_kod": novy_kod})
                if args.apply:
                    cur.execute("UPDATE horni_blok_varianty SET kod=%s WHERE id=%s", (novy_kod, hid))

            print("\n--- krok 2: kod_sestavy (18 sestav) ---")
            for aid, novy_blok_kod in ASSEMBLY_NOVY_BLOK_KOD.items():
                cur.execute(
                    "SELECT pa.id, pa.name, pa.kod_sestavy, "
                    "       pa.karoserie_kod, pa.profil_mm, pa.verze, pa.dodatek, "
                    "       ru.kod AS umisteni_kod, rt.kod AS typologie_kod, tv.kod AS varianta_kod "
                    "FROM product_assemblies pa "
                    "LEFT JOIN regal_umisteni ru ON ru.id = pa.umisteni_id "
                    "LEFT JOIN regal_typologie rt ON rt.id = pa.typologie_id "
                    "LEFT JOIN typologie_varianty tv ON tv.id = pa.typologie_varianta_id "
                    "WHERE pa.id=%s", (aid,),
                )
                r = cur.fetchone()
                if not r:
                    print(f"  id={aid}: sestava neexistuje, preskakuji"); continue
                novy_kod_sestavy = sestavit_kod_sestavy(
                    karoserie_kod=r["karoserie_kod"], umisteni_kod=r["umisteni_kod"],
                    typologie_kod=r["typologie_kod"], profil_mm=r["profil_mm"],
                    verze=r["verze"], varianta_kod=r["varianta_kod"],
                    horni_blok_kod=novy_blok_kod, dodatek=r["dodatek"] or 0,
                )
                if novy_kod_sestavy == r["kod_sestavy"]:
                    print(f"  id={aid} ({r['name']}): kod_sestavy uz aktualni, preskakuji")
                    continue
                print(f"  id={aid} ({r['name']}): {r['kod_sestavy']} -> {novy_kod_sestavy}")
                zaloha["kod_sestavy_zmeny"].append({
                    "id": aid, "puvodni_kod_sestavy": r["kod_sestavy"], "novy_kod_sestavy": novy_kod_sestavy,
                })
                if args.apply:
                    cur.execute("UPDATE product_assemblies SET kod_sestavy=%s WHERE id=%s", (novy_kod_sestavy, aid))

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
                cur.execute("SELECT id, kod, nazev FROM horni_blok_varianty WHERE id IN (1,2,3,4,5,6,7,8) ORDER BY id")
                for r in cur.fetchall():
                    print(" ", r)
                print()
                for aid in sorted(ASSEMBLY_NOVY_BLOK_KOD):
                    cur.execute("SELECT id, name, kod_sestavy FROM product_assemblies WHERE id=%s", (aid,))
                    r = cur.fetchone()
                    ocekavany = ASSEMBLY_NOVY_BLOK_KOD[aid]
                    skutecny = r["kod_sestavy"].split("-")[7] if r else None
                    znacka = "OK" if skutecny == ocekavany else "CHYBA"
                    print(f"  [{znacka}] id={aid} kod_sestavy={r['kod_sestavy'] if r else None}")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
