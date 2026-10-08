#!/usr/bin/env python3
"""Dogeneruje `kod_sestavy` u vsech sestav, kde chybi (Robert pres bot3,
2026-09-24, URGENTNI - najdeno na karte 3956/regal-na-euroboxy-toyota-
proace-long-od-2016, sestavy 524/528). WORKFLOW.md pravidlo 52: resit
hned, ne odkladat.

STEJNA LOGIKA jako automaticky hook `_dopocti_kod_sestavy_pri_zarazeni()`
(api/product_assemblies.py) a drivejsi jednorazovy beh
scripts/2026-09-13_bot5_kod_sestavy_retroaktivne.py - vola tentyz
`sestavit_kod_sestavy()`, tutez sadu JOINu. Rozdil oproti tomu drivejsimu
skriptu: NEOMEZUJE se na `category_id IS NOT NULL` (dnesnich 283 chybejicich
prekracuje puvodni uzsi scenar "hook nestihl znovu-zarazeni"), bere VSECHNY
sestavy s kod_sestavy NULL/prazdne. Nikdy neprepisuje existujici odlisnou
hodnotu (jen NULL/prazdne -> vypocteny kod).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-24_bot5_kod_sestavy_backfill_283.py
    api/venv/bin/python3 scripts/2026-09-24_bot5_kod_sestavy_backfill_283.py --apply
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
    "backups", "2026-09-24_bot5_kod_sestavy_backfill_283",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== kod_sestavy backfill (vsechny chybejici) — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    doplneno, chybi_pole = [], []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pa.id, pa.name, pa.technicky_ok, pa.kod_sestavy AS stary,
                       pa.karoserie_kod, pa.profil_mm, pa.verze, pa.dodatek,
                       ru.kod AS umisteni_kod, rt.kod AS typologie_kod,
                       tv.kod AS varianta_kod, hb.kod AS horni_blok_kod
                FROM product_assemblies pa
                LEFT JOIN regal_umisteni ru ON ru.id = pa.umisteni_id
                LEFT JOIN regal_typologie rt ON rt.id = pa.typologie_id
                LEFT JOIN typologie_varianty tv ON tv.id = pa.typologie_varianta_id
                LEFT JOIN horni_blok_varianty hb ON hb.id = pa.horni_blok_varianta_id
                WHERE pa.kod_sestavy IS NULL OR pa.kod_sestavy=''
            """)
            for r in cur.fetchall():
                novy = sestavit_kod_sestavy(
                    karoserie_kod=r["karoserie_kod"], umisteni_kod=r["umisteni_kod"],
                    typologie_kod=r["typologie_kod"], profil_mm=r["profil_mm"],
                    verze=r["verze"], varianta_kod=r["varianta_kod"],
                    horni_blok_kod=r["horni_blok_kod"], dodatek=r["dodatek"],
                )
                if novy is None:
                    chybejici = [jmeno for jmeno, hodnota in [
                        ("karoserie_kod", r["karoserie_kod"]), ("umisteni_kod", r["umisteni_kod"]),
                        ("typologie_kod", r["typologie_kod"]), ("profil_mm", r["profil_mm"]),
                        ("verze", r["verze"]), ("varianta_kod", r["varianta_kod"]),
                        ("horni_blok_kod", r["horni_blok_kod"]),
                    ] if not hodnota]
                    chybi_pole.append((r["id"], r["technicky_ok"], r["name"], chybejici))
                    continue
                doplneno.append((r["id"], novy, r["name"]))
                print(f"  id={r['id']}: NULL -> {novy!r}  ({r['name'][:60]})")

            if args.apply and doplneno:
                os.makedirs(ZALOHA_DIR, exist_ok=True)
                with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                    json.dump([{"id": i, "novy_kod_sestavy": n, "name": nm} for i, n, nm in doplneno],
                              f, ensure_ascii=False, indent=2)
                for id_, novy, _ in doplneno:
                    cur.execute("UPDATE product_assemblies SET kod_sestavy=%s WHERE id=%s", (novy, id_))
        if args.apply:
            conn.commit()
    finally:
        conn.close()

    print(f"\n{'HOTOVO' if args.apply else 'DRY-RUN'}: {len(doplneno)} doplneno, {len(chybi_pole)} porad chybi zdrojova pole.")
    if chybi_pole:
        print(f"\nCHYBI ZDROJOVA POLE ({len(chybi_pole)}) - vyzaduje domluvu s bot8 nebo rucni dohledani:")
        for id_, ok, name, pole in chybi_pole:
            print(f"  id={id_} (technicky_ok={ok}) chybi: {', '.join(pole)} — {name[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
