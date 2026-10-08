#!/usr/bin/env python3
"""Rozsiri kotveni_zakaznicky/montaz_zakaznicky (regal_umisteni) na VSECHNA
umisteni, ne jen RL/RP.

Robert, 2026-09-14, doslova (u screenshotu Kotveni/Montaz textu karty
3943): "toto budou společné popisy u vsech sestav." Puvodni text
(2026-09-13, scripts/2026-09-13_bot5_montaz_zakaznicky_umisteni.py +
2026-09-13_bot5_kotveni_zakaznicky_split - viz backups) byl ZAMERNE jen
pro RL/RP ("radsi chybejici nez vymyslany" - zpusob kotveni u
RK/DP/VZ/VB/VP nebyl tehdy overeny). Robert ted primo urcuje, ze text
plati SPOLECNE pro vsechna umisteni - prepisuje puvodni opatrnost jako
domenova autorita, ne odhad.

Idempotentni (prepisuje jen tam, kde je NULL - RL/RP uz maji text
z 2026-09-13, nedotcen). Zaloha do backups/.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-14_bot5_kotveni_montaz_spolecne_vsude.py
    api/venv/bin/python3 scripts/2026-09-14_bot5_kotveni_montaz_spolecne_vsude.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-14_bot5_kotveni_montaz_spolecne_vsude",
)

KOTVENI_TEXT = "Konstrukce se kotví do zpevněných částí karoserie (bočnice a podlaha)."
MONTAZ_TEXT = "Montáž zahrnuje vrtání do těchto částí, v souladu s požadavky na homologaci."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== kotveni/montaz spolecne pro vsechna umisteni — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, kod, nazev, kotveni_zakaznicky, montaz_zakaznicky "
                "FROM regal_umisteni ORDER BY sort_order"
            )
            for r in cur.fetchall():
                chybi_kotveni = r["kotveni_zakaznicky"] is None
                chybi_montaz = r["montaz_zakaznicky"] is None
                if not chybi_kotveni and not chybi_montaz:
                    print(f"  {r['id']} ({r['kod']} {r['nazev']}): uz ma oboji, preskakuji")
                    continue
                print(f"  {r['id']} ({r['kod']} {r['nazev']}): doplnim "
                      f"{'kotveni ' if chybi_kotveni else ''}{'montaz' if chybi_montaz else ''}")
                zaloha.append({
                    "id": r["id"], "kod": r["kod"],
                    "puvodni_kotveni": r["kotveni_zakaznicky"],
                    "puvodni_montaz": r["montaz_zakaznicky"],
                })
                if args.apply:
                    if chybi_kotveni:
                        cur.execute("UPDATE regal_umisteni SET kotveni_zakaznicky=%s WHERE id=%s",
                                    (KOTVENI_TEXT, r["id"]))
                    if chybi_montaz:
                        cur.execute("UPDATE regal_umisteni SET montaz_zakaznicky=%s WHERE id=%s",
                                    (MONTAZ_TEXT, r["id"]))

        if args.apply and zaloha:
            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=2)
            conn.commit()
            print("\nCOMMIT hotovy.")
        else:
            print("\nDRY-RUN: nic nezapsano." if not args.apply else "\nNic k zapsani.")
    finally:
        conn.close()

    if args.apply and zaloha:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                print("\n=== OVERENI z noveho spojeni ===")
                cur.execute("SELECT id, kod, kotveni_zakaznicky, montaz_zakaznicky FROM regal_umisteni ORDER BY sort_order")
                for r in cur.fetchall():
                    print(f"  {r['id']} {r['kod']}: kotveni={r['kotveni_zakaznicky']!r}")
                    print(f"           montaz={r['montaz_zakaznicky']!r}")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
