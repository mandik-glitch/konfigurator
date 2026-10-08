#!/usr/bin/env python3
"""Doplneni zrcadel UZ EXISTUJICICH produktovych sestav na Sdileny disk.

Robert 2026-09-09: "chci zrcadlit produktové sestavy, které nebudou
nezařazené". Zrcadleni od ted probiha pri kazdem ulozeni sestavy
(api/product_assemblies.py::zrcadli_sestavu_na_disk); tenhle skript je
JEDNORAZOVY dobeh pro sestavy, ktere vznikly driv.

Slozka se urcuje podle ZNACKY vozidla odvozene z nazvu sestavy - viz
komentar u zrcadli_sestavu_na_disk(). Sestava, u ktere znacku odvodit
nelze, se ZAMERNE nezrcadli vubec (misto aby spadla do "Nezarazenych") a
vypise se na konci jako seznam k reseni.

    api/venv/bin/python3 scripts/2026-09-09_zrcadlo_sestav_backfill.py          # jen ukaze, co by udelal
    api/venv/bin/python3 scripts/2026-09-09_zrcadlo_sestav_backfill.py --zapsat # opravdu zapise
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))

os.environ.setdefault("FLASK_SKIP_SCHEDULERS", "1")

import app as flask_app  # noqa: E402
import product_assemblies as pa  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Doplni zrcadla sestav na Sdileny disk.")
    p.add_argument("--zapsat", action="store_true",
                   help="opravdu zapsat (bez nej jen nahled, nic se nemeni)")
    p.add_argument("--vsechny", action="store_true",
                   help="prepsat i sestavy, ktere uz zrcadlo maji")
    args = p.parse_args()

    conn = flask_app.get_conn()
    hotovo, preskoceno, bez_znacky = 0, 0, []
    podle_znacky = collections.Counter()
    try:
        with conn.cursor() as cur:
            mapy = pa.nacti_mapy_znacek(cur)
            cur.execute("SELECT id, name, data, created_by, drive_file_id "
                        "FROM product_assemblies ORDER BY id")
            rows = cur.fetchall()
            print("sestav v DB: %d" % len(rows))
            for r in rows:
                if r["drive_file_id"] and not args.vsechny:
                    preskoceno += 1
                    continue
                znacka = pa.znacka_ze_jmena(r["name"], *mapy)
                if not znacka:
                    bez_znacky.append((r["id"], r["name"]))
                    continue
                podle_znacky[znacka] += 1
                if not args.zapsat:
                    hotovo += 1
                    continue
                try:
                    import json
                    payload = json.loads(r["data"])
                except (ValueError, TypeError):
                    print("  PRESKOCENO %s (%s): data nejsou platny JSON" % (r["id"], r["name"]))
                    continue
                fid = pa.zrcadli_sestavu_na_disk(cur, r["id"], r["name"], payload,
                                                 r["created_by"], mapy=mapy)
                if fid:
                    hotovo += 1
        if args.zapsat:
            conn.commit()
    finally:
        conn.close()

    print()
    print("%s: %d sestav, preskoceno (uz maji zrcadlo): %d"
          % ("ZAPSANO" if args.zapsat else "NAHLED (nic se nezmenilo)", hotovo, preskoceno))
    for znacka, n in sorted(podle_znacky.items(), key=lambda x: -x[1]):
        print("  %-14s %d" % (znacka, n))
    if bez_znacky:
        print()
        print("BEZ ZNACKY - nezrcadli se (Robert: zadne 'Nezarazene'): %d" % len(bez_znacky))
        for i, n in bez_znacky:
            print("  %s  %s" % (i, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
