#!/usr/bin/env python3
"""Migruje existujici product_assemblies radky (dnes vsechny, po smazani
671/672 - viz scripts/2026-09-26_delete_671_672_vandr_export_scratch.py -
je jich 530) na sestava_typ_id=AUTO.

Kontext: nova osa "typ sestavy" (viz sql/2026-09-26_sestava_typ_tabulka.sql,
api/sestava_typ.py). Bot8 (product_assemblies, vlastnik) potvrdil: VSECHNY
zbyvajici radky jsou AUTO (vestavby do vozidel) - 260/530 ma car_model_id
NULL jen z historicke diry v datech, ne proto ze nejsou AUTO. Zadny
existujici radek dnes nepatri stolove/skladove lince (bot10 potvrdil -
scena 2 nema zatim zadnou skutecnou zakaznicky viditelnou sestavu, jen
interni geometrickou sablonu bez vazby na product_assemblies).

Bot3 pozadoval dry-run vystup PRED spustenim (stejna disciplina jako u
schematu a smazani 671/672).

Idempotentni: WHERE sestava_typ_id IS NULL - opakovane spusteni po
prvnim --apply uz nic nenajde k zapisu.

Pouziti:
    python3 scripts/2026-09-26_sestava_typ_migrace_auto.py            # dry-run
    python3 scripts/2026-09-26_sestava_typ_migrace_auto.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM sestava_typ WHERE kod='AUTO'")
    row = cur.fetchone()
    if not row:
        print("CHYBA: sestava_typ 'AUTO' neexistuje - spusť nejdřív "
              "scripts/2026-09-26_sestava_typ_zapsat.py --apply")
        cur.close()
        conn.close()
        sys.exit(1)
    auto_id = row["id"]
    print(f"[sestava_typ AUTO] id={auto_id}")

    cur.execute("SELECT COUNT(*) AS n FROM product_assemblies WHERE sestava_typ_id IS NULL")
    to_migrate = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM product_assemblies WHERE sestava_typ_id IS NOT NULL")
    already_set = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM product_assemblies")
    total = cur.fetchone()["n"]
    print(f"[product_assemblies] celkem={total}, uz ma typ={already_set}, "
          f"k migraci na AUTO={to_migrate}")

    cur.execute(
        "SELECT COUNT(*) AS n FROM product_assemblies WHERE sestava_typ_id IS NULL AND car_model_id IS NULL"
    )
    null_car_model = cur.fetchone()["n"]
    print(f"  z toho s car_model_id NULL (historická díra v datech, "
          f"přesto AUTO): {null_car_model}")

    if APPLY:
        cur.execute(
            "UPDATE product_assemblies SET sestava_typ_id=%s WHERE sestava_typ_id IS NULL",
            (auto_id,),
        )
        print(f"[apply] aktualizováno řádků: {cur.rowcount}")
        conn.commit()
        print("\nAPLIKOVÁNO.")
    else:
        print(f"\n[dry-run] aktualizovalo by se {to_migrate} řádků na "
              f"sestava_typ_id={auto_id} (AUTO). Nic nezapsáno.")
        print("Spusť s --apply pro zápis.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
