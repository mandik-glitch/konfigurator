#!/usr/bin/env python3
"""Odstrani vetu "Přesný obsah sestavy (kusovník) najdete v tabulce
specifikací níže." ze VSECH Vandr karet (bot5, 2026-09-23) - Robert:
"tuto větu nepouzivat".

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-23c_bot5_vandr_odstranit_vetu_tabulka.py
    api/venv/bin/python3 scripts/2026-09-23c_bot5_vandr_odstranit_vetu_tabulka.py --apply
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

VD_SKU_REGEXP = r"^VD-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

DESC_RE = re.compile(
    r"^Hliníková regálová vestavba do nákladového prostoru (?P<vehicle>.+?)\. "
    r"Přesný obsah sestavy \(kusovník\) najdete v tabulce specifikací níže\.$"
)


def _novy_popis(stary):
    m = DESC_RE.match(stary or "")
    if not m:
        return None
    return f"Hliníková regálová vestavba do nákladového prostoru {m.group('vehicle')}."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Vandr popis: odstranit vetu o tabulce specifikaci — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sku, description FROM shop_products WHERE sku REGEXP %s ORDER BY id",
                (VD_SKU_REGEXP,),
            )
            rows = cur.fetchall()
            zmeneno, neshoda = 0, []
            for r in rows:
                novy = _novy_popis(r["description"])
                if novy is None:
                    neshoda.append(r)
                    continue
                zmeneno += 1
                if args.apply:
                    cur.execute("UPDATE shop_products SET description=%s WHERE id=%s", (novy, r["id"]))
                else:
                    print(f"[{r['id']}] {r['sku']} -> {novy}")
        if args.apply:
            conn.commit()
            print(f"\nHOTOVO: upraveno {zmeneno}/{len(rows)} karet.")
        else:
            print(f"DRY-RUN: bylo by upraveno {zmeneno}/{len(rows)} karet.")
        if neshoda:
            print(f"\nNESEDÍ na očekávaný vzor (přeskočeno), {len(neshoda)} karet:")
            for r in neshoda:
                print(f"  [{r['id']}] {r['sku']} description={r['description']!r}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
