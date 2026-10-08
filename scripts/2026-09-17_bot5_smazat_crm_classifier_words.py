#!/usr/bin/env python3
"""Smazani obsahu crm_classifier_words (bot5, 2026-09-17, Robert pres
bot3): chce prazdnou tabulku (1032 radku), ne par rucne upravenych.
Navazuje na rozhodnuti vypnout email-based Poptavky (support-email-sync
timer zustava vypnuty).

Overeno pred smazanim (api/crm.py::classify_incoming_email): s
prazdnou tabulkou SELECT ... WHERE word IN (...) vzdy vrati 0 radku,
jine_score=doklad_score=0, `if doklad_score > 0 and ...` je False ->
funkce vraci "jine" - presne jeji vlastni zdokumentovany "fail-open"
fallback ("bezpecnejsi vychozi stav je nezachytit nez zaplavit CRM/
Doklady omylem"), zadna vyjimka, zadny padek. train_words() take dal
funguje beze zmeny (jen zacne pocitat od nuly).

Zaloha do backups/ pred smazanim.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-17_bot5_smazat_crm_classifier_words.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-17_bot5_smazat_crm_classifier_words",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== smazani crm_classifier_words — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT word, poptavka_count, jine_count, doklad_count FROM crm_classifier_words ORDER BY word")
            radky = cur.fetchall()
        print(f"Radku v tabulce: {len(radky)}")

        os.makedirs(ZALOHA_DIR, exist_ok=True)
        zaloha_path = os.path.join(ZALOHA_DIR, "pred_smazanim.json")
        with open(zaloha_path, "w", encoding="utf-8") as f:
            json.dump(radky, f, ensure_ascii=False, indent=2, default=str)
        print(f"Zaloha zapsana: {zaloha_path}")

        if args.apply:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM crm_classifier_words")
                smazano = cur.rowcount
            conn.commit()
            print(f"COMMIT hotovy - smazano {smazano} radku.")
        else:
            print("DRY-RUN: nic nesmazano.")
    finally:
        conn.close()

    if args.apply:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM crm_classifier_words")
                print("OVERENI pocet radku:", cur.fetchone())
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
