#!/usr/bin/env python3
"""Oprava: `availability_text` na kartach 3943/3944/3945 bylo bez diakritiky.

Chyba bot5 z tehez dne. V `scripts/2026-09-12_bot5_karty_10_30.py` byla
konstanta `DOSTUPNOST = "3 - 5 tydnu"` napsana bez diakritiky, takze vsechny
tri nove karty dostaly zakaznicky viditelny text "3 - 5 tydnu" misto
"3 - 5 týdnů". Stara karta 3942 ma spravnou podobu, takze to nebyla zmena
konvence - proste preklep.

Zbytek textu karet (name, short_description, description, meta_*) diakritiku
ma; proslo kontrolou vsech zakaznicky viditelnych poli, jedine
`availability_text` bylo spatne.

Zdrojova konstanta je opravena ve stejnem commitu, takze pripadny dalsi beh
zakladaciho skriptu uz zapise spravnou hodnotu.

Idempotentni: prepisuje jen presnou chybnou hodnotu, jine hodnoty necha byt.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-12_bot5_oprava_dostupnost_diakritika.py
    api/venv/bin/python3 scripts/2026-09-12_bot5_oprava_dostupnost_diakritika.py --apply
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

SPATNE = "3 - 5 tydnu"
SPRAVNE = "3 - 5 týdnů"
KARTY = (3943, 3944, 3945)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Oprava availability_text — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    n = 0
    try:
        with conn.cursor() as cur:
            ph = ",".join(["%s"] * len(KARTY))
            cur.execute(
                f"SELECT id, availability_text FROM shop_products WHERE id IN ({ph})",
                KARTY,
            )
            for r in cur.fetchall():
                if r["availability_text"] == SPRAVNE:
                    print(f"  {r['id']}: uz je spravne, preskakuji")
                elif r["availability_text"] != SPATNE:
                    print(f"  {r['id']}: necekana hodnota {r['availability_text']!r}, NECHAVAM BYT")
                else:
                    print(f"  {r['id']}: {r['availability_text']!r} -> {SPRAVNE!r}")
                    if args.apply:
                        cur.execute(
                            "UPDATE shop_products SET availability_text=%s "
                            "WHERE id=%s AND availability_text=%s",
                            (SPRAVNE, r["id"], SPATNE),
                        )
                        cur.execute(
                            "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) "
                            "VALUES (NULL,'update','shop_product',%s,%s)",
                            (r["id"], "bot5 skript 2026-09-12: oprava availability_text "
                                      "(chybela diakritika)"),
                        )
                    n += 1
        if args.apply:
            conn.commit()
            print(f"\nCOMMIT hotovy, opraveno {n}.")
        else:
            print(f"\nDRY-RUN: nic nezapsano, k oprave {n}.")
    finally:
        conn.close()

    if args.apply:
        print("\n=== OVERENI z noveho spojeni ===")
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                ph = ",".join(["%s"] * len(KARTY))
                cur.execute(
                    f"SELECT id, availability_text FROM shop_products WHERE id IN ({ph})",
                    KARTY,
                )
                for r in cur.fetchall():
                    ok = r["availability_text"] == SPRAVNE
                    print(f"  {r['id']}: {r['availability_text']!r} {'OK' if ok else 'NESEDI'}")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
