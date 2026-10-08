#!/usr/bin/env python3
"""Zpetny backfill popisu VSECH Vandr karet (bot5, 2026-09-23):
  1) odstranit "vanDrawee" z ceskeho zakaznickeho textu (TEXT_FILTR.md
     pravidlo 15 - Robert: "v ceskych textech ho nebudeme pouzivat").
  2) pridat blok "Cena obsahuje:" (Robert, doslova: "výrobu stavebnice"
     / "dodáváno ve zcela rozloženém stavu, profily v ochranné folii" /
     "zákazník obdrží všeobecný návod v PDF a ručně doplněné popisy ve
     3d náhledech").

Vsech 323 Vandr karet melo pred timhle skriptem UNIFORMNI text (overeno
primo v DB) - bud z bot7ova CSV importu (321), nebo z watcheru (2,
4903/4904), oba zdroje pouzivaly stejnou vetu jen s jinym vozidlem.
Backfill proto NEPOTREBUJE zdroj metadat znovu - jen regex nad uz
ulozenym textem, vozidlo se preberi z toho, co uz v popisu je.

description vzor (presne, overeno 323/323):
  "Hliníková regálová vestavba do nákladového prostoru {vehicle} vanDrawee. Přesný obsah sestavy (kusovník) najdete v tabulce specifikací níže."
short_description vzor (jen odstranit " vanDrawee", zbytek beze zmeny -
kazda karta ma jiny seznam komponent od bot7, nechceme ho zahodit).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-23_bot5_vandr_popis_cena_blok.py
    api/venv/bin/python3 scripts/2026-09-23_bot5_vandr_popis_cena_blok.py --apply
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

VD_SKU_REGEXP = r"^VD-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

DESC_RE = re.compile(
    r"^Hliníková regálová vestavba do nákladového prostoru (?P<vehicle>.+?) vanDrawee\. "
    r"Přesný obsah sestavy \(kusovník\) najdete v tabulce specifikací níže\.$"
)

CENA_BLOK = "\n".join([
    "Cena obsahuje:",
    "- výrobu stavebnice",
    "- dodání ve zcela rozloženém stavu, profily v ochranné fólii",
    "- obecný montážní návod v PDF a ručně doplněné popisy ve 3D náhledech",
])


def _novy_popis(stary):
    m = DESC_RE.match(stary or "")
    if not m:
        return None
    vehicle = m.group("vehicle")
    return (
        f"Hliníková regálová vestavba do nákladového prostoru {vehicle}.\n\n"
        f"{CENA_BLOK}\n\n"
        f"Přesný obsah sestavy (kusovník) najdete v tabulce specifikací níže."
    )


def _novy_kratky_popis(stary):
    if not stary or " vanDrawee" not in stary:
        return None
    return stary.replace(" vanDrawee", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Vandr popis: odstranit vanDrawee + pridat blok Cena obsahuje — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sku, description, short_description FROM shop_products WHERE sku REGEXP %s ORDER BY id",
                (VD_SKU_REGEXP,),
            )
            rows = cur.fetchall()
            zmeneno, neshoda = 0, []
            for r in rows:
                novy_popis = _novy_popis(r["description"])
                novy_kratky = _novy_kratky_popis(r["short_description"])
                if novy_popis is None and novy_kratky is None:
                    neshoda.append(r)
                    continue
                zmeneno += 1
                if args.apply:
                    sets, params = [], []
                    if novy_popis is not None:
                        sets.append("description=%s")
                        params.append(novy_popis)
                    if novy_kratky is not None:
                        sets.append("short_description=%s")
                        params.append(novy_kratky)
                    params.append(r["id"])
                    cur.execute(f"UPDATE shop_products SET {', '.join(sets)} WHERE id=%s", params)
                else:
                    print(f"[{r['id']}] {r['sku']}")
                    if novy_popis is not None:
                        print(f"  description -> {novy_popis[:80]}...")
                    if novy_kratky is not None:
                        print(f"  short_description -> {novy_kratky}")
        if args.apply:
            conn.commit()
            print(f"\nHOTOVO: upraveno {zmeneno}/{len(rows)} karet.")
        else:
            print(f"DRY-RUN: bylo by upraveno {zmeneno}/{len(rows)} karet.")
        if neshoda:
            print(f"\nNESEDÍ na očekávaný vzor (přeskočeno, needitováno), {len(neshoda)} karet:")
            for r in neshoda:
                print(f"  [{r['id']}] {r['sku']} description={r['description']!r}")
    finally:
        conn.close()

    if args.apply:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) c FROM shop_products WHERE sku REGEXP %s AND (description LIKE '%%vanDrawee%%' OR short_description LIKE '%%vanDrawee%%')",
                    (VD_SKU_REGEXP,),
                )
                print(f"\nOVĚŘENÍ: karet se stále \"vanDrawee\" v popisu: {cur.fetchone()['c']} (očekáváno 0)")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
