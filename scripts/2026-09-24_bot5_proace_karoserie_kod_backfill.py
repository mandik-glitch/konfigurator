#!/usr/bin/env python3
"""Dopocita `product_assemblies.karoserie_kod` u vsech Toyota Proace
sestav (bot5, 2026-09-24, navazuje na kod_sestavy backfill - Robert pres
bot3, karta 3956/Proace Long, WORKFLOW.md pravidlo 52, resit hned).

Zdroj K-kodu: `car_models.name` uz kazdy Proace model obsahuje ve tvaru
"<popis karoserie> [K-XXX] — <rozmery>" (napr. id=274 "Proace Long 16-
[K-170] — 5309mm..."). `product_assemblies.name` u Proace sestav VZDY
zacina (pripadne za emoji prefixem) stejnym textem "<popis karoserie>"
jako car_models.name pred " [K-". Shoda overena RUCNE pred spustenim -
44 sestav, VSECHNY jednoznacne (presne 1 shodujici se prefix), 0
nejednoznacnych. `sql/3956 (regal-na-euroboxy-toyota-proace-long-od-2016)`
uz existujici SKU `K-170-RL-EB-30` potvrzuje spravnost K-170 pro
"Proace Long 16-".

Nikdy neprepisuje existujici odlisny karoserie_kod (jen NULL -> dohledany
kod). Po tomhle beh navazuje znovu
scripts/2026-09-24_bot5_kod_sestavy_backfill_283.py --apply, aby se
z nove vyplneneho karoserie_kod slozil i kod_sestavy.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-24_bot5_proace_karoserie_kod_backfill.py
    api/venv/bin/python3 scripts/2026-09-24_bot5_proace_karoserie_kod_backfill.py --apply
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-24_bot5_proace_karoserie_kod_backfill",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Proace karoserie_kod backfill — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zmeny = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM car_models WHERE name LIKE '%[K-%'")
            prefixy = []
            for r in cur.fetchall():
                m = re.match(r"^(.*?)\s*\[K-(\S+?)\]", r["name"])
                if m:
                    prefixy.append((m.group(1).strip(), "K-" + m.group(2)))
            prefixy.sort(key=lambda x: -len(x[0]))

            cur.execute(
                "SELECT id, name, karoserie_kod FROM product_assemblies "
                "WHERE karoserie_kod IS NULL AND name LIKE '%Proace%'"
            )
            for row in cur.fetchall():
                shody = {kod for prefix, kod in prefixy if prefix in row["name"]}
                if len(shody) != 1:
                    print(f"  ⛔ id={row['id']}: {len(shody)} shod ({shody}), PRESKAKUJI - {row['name'][:70]}")
                    continue
                kod = shody.pop()
                zmeny.append((row["id"], kod, row["name"]))
                print(f"  id={row['id']}: NULL -> {kod}  ({row['name'][:70]})")

            if args.apply and zmeny:
                os.makedirs(ZALOHA_DIR, exist_ok=True)
                with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                    json.dump([{"id": i, "novy_karoserie_kod": k, "name": nm} for i, k, nm in zmeny],
                              f, ensure_ascii=False, indent=2)
                for id_, kod, _ in zmeny:
                    cur.execute("UPDATE product_assemblies SET karoserie_kod=%s WHERE id=%s", (kod, id_))
        if args.apply:
            conn.commit()
    finally:
        conn.close()

    print(f"\n{'HOTOVO' if args.apply else 'DRY-RUN'}: {len(zmeny)} sestav {'doplneno' if args.apply else 'by bylo doplneno'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
