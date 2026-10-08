#!/usr/bin/env python3
"""Zapise zakaznicky montazni text (`regal_umisteni.montaz_zakaznicky`).

Doplneni TEXT_FILTR.md pravidla 13 (Robert pres bot9, 2026-09-13: "Stejné
pravidlo platí i pro popis ohledně montáže."). Psano JEN pro umisteni, kde
je zpusob kotveni skutecne OVERENY - RL/RP (bocnice + podlaha, viz
TEXT_FILTR.md pravidlo 9a, uz drive schvaleny text). Ostatni umisteni
(RK/DP/VZ/VB/VP) maji v `regal_umisteni.popis` doslova "obsah/detaily
zatim neurceny" - montazni text pro ne NEPISU, zustava NULL, dokud
nekdo neurci skutecny zpusob kotveni (radsi chybejici nez uhodnuty).

Text pro RL/RP je STEJNA VETA, ktera dnes visi STATICKY v popisu karty
3943 - jen se presouva do dynamickeho mechanismu (viz
`scripts/2026-09-13_bot5_odstranit_staticky_montaz_z_karty.py`, ktery tu
duplicitu z karty odstranuje).

Idempotentni (prepisuje jen NULL). Zaloha do backups/.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-13_bot5_montaz_zakaznicky_umisteni.py
    api/venv/bin/python3 scripts/2026-09-13_bot5_montaz_zakaznicky_umisteni.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-13_bot5_montaz_zakaznicky_umisteni",
)

# klic = regal_umisteni.id. JEN RL(1)/RP(7) - overeny fakt. Ostatni se
# NEPISI, dokud se neurci skutecny zpusob kotveni.
MONTAZ_TEXT = {
    1: "Konstrukce se kotví do zpevněných částí karoserie (bočnice a "
       "podlaha). Montáž zahrnuje vrtání do těchto částí, v souladu s "
       "požadavky na homologaci.",
    7: "Konstrukce se kotví do zpevněných částí karoserie (bočnice a "
       "podlaha). Montáž zahrnuje vrtání do těchto částí, v souladu s "
       "požadavky na homologaci.",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== montaz_zakaznicky (regal_umisteni) — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    try:
        with conn.cursor() as cur:
            for id_, text in MONTAZ_TEXT.items():
                cur.execute("SELECT id, kod, nazev, montaz_zakaznicky FROM regal_umisteni WHERE id=%s", (id_,))
                r = cur.fetchone()
                if not r:
                    print(f"  id={id_}: neexistuje, preskakuji"); continue
                if r["montaz_zakaznicky"] is not None:
                    print(f"  id={id_} ({r['kod']}): uz ma text, preskakuji")
                    continue
                print(f"  id={id_} ({r['kod']} {r['nazev']}): {text[:60]}...")
                zaloha.append({"id": id_, "kod": r["kod"], "novy": text})
                if args.apply:
                    cur.execute("UPDATE regal_umisteni SET montaz_zakaznicky=%s WHERE id=%s", (text, id_))

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
                cur.execute("SELECT id, kod, montaz_zakaznicky FROM regal_umisteni ORDER BY sort_order")
                for r in cur.fetchall():
                    print(f"  {r['id']} {r['kod']}: {r['montaz_zakaznicky'] or '(prazdne)'}")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
