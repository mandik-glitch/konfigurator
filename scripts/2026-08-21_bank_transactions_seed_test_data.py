#!/usr/bin/env python3
"""Testovaci data pro admin panel Bankovni vypisy (bot10, 2026-08-21) -
FIO_BANK_API_TOKEN zatim neni k dispozici (ceka se na Roberta, viz
TASKS.md), tenhle skript naplni par realistickych rádku primo do DB, at
jde UI (tabulka, hledani podle castky, filtr) overit driv, nez token
dorazi. VSECHNY radky maji `is_test_data=1` - snadno se poznaji a smazou.

Pouziti:
    api/venv/bin/python3 scripts/2026-08-21_bank_transactions_seed_test_data.py --apply
    (bez --apply = jen vypise, co by vlozil)

Uklid (az prijde skutecny token a bude zbytecne mit testovaci radky
namichane mezi realnymi): DELETE FROM bank_transactions WHERE is_test_data=1
"""
import argparse
import datetime
import json
import os
import sys

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "api", ".env")
for _line in open(_ENV_PATH, encoding="utf-8"):
    _line = _line.strip()
    if not _line or _line.startswith("#") or "=" not in _line:
        continue
    _k, _v = _line.split("=", 1)
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from app import get_conn  # noqa: E402

TODAY = datetime.date.today()

TEST_ROWS = [
    # (dny_zpet, castka, VS, nazev_protiuctu, cislo_protiuctu, zprava, typ)
    (0, 12500.00, "2026081001", "Jan Novák", "123456789/0800", "Objednávka 2026081001", "Bezhotovostní příjem"),
    (1, 3450.50, "2026081102", "Eshop zákazník s.r.o.", "987654321/0100", "Platba za fakturu FA-2026-0142", "Bezhotovostní příjem"),
    (2, 87200.00, "2026081205", "STAVBAKOV a.s.", "555666777/0300", "Úhrada zálohové faktury", "Bezhotovostní příjem"),
    (4, 990.00, "", "Petra Svobodová", "111222333/2010", "", "Bezhotovostní příjem"),
    (7, 15600.00, "2026080901", "Truhlářství Dvořák", "444555666/0600", "Doplatek objednávky", "Bezhotovostní příjem"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            inserted = 0
            for days_ago, amount, vs, name, acc, msg, typ in TEST_ROWS:
                tx_date = TODAY - datetime.timedelta(days=days_ago)
                fake_fio_id = int(f"9{days_ago:02d}{int(amount*100):010d}")
                raw = {"note": "testovaci data, is_test_data=1", "fake_fio_id": fake_fio_id}
                print(f"{tx_date} {amount:>10.2f} Kč  VS={vs or '-':12s} {name}")
                if args.apply:
                    cur.execute(
                        "INSERT IGNORE INTO bank_transactions "
                        "(fio_transaction_id, transaction_date, amount_czk, currency, "
                        "counter_account, counter_account_name, variable_symbol, "
                        "message_for_recipient, transaction_type, is_test_data, raw_json) "
                        "VALUES (%s,%s,%s,'CZK',%s,%s,%s,%s,%s,1,%s)",
                        (fake_fio_id, tx_date, amount, acc, name, vs or None, msg or None, typ,
                         json.dumps(raw, ensure_ascii=False)),
                    )
                    inserted += cur.rowcount
            if args.apply:
                conn.commit()
                print(f"\nOK - vloženo {inserted} testovacích záznamů (is_test_data=1).")
            else:
                print("\n[dry-run] Nic nezapsáno. Spusť s --apply pro skutečný zápis.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
