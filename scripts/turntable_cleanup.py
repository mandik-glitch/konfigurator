#!/usr/bin/env python3
"""Fyzicky sklidi turntable davky po grace periode (bot5, 2026-09-02, na
zadost bot3/Roberta - viz api/turntable.py hlavicka a _sweep_expired_batches).

Commit nove davky uz zavola sweep sam za sebe (jen pro dany produkt), takze
tenhle skript neni pro bezny provoz nutny - je pro pripad, ze by nejaky
produkt dlouho nemel dalsi commit (stara davka by jinak cekala na sweep
"navzdy") a pro budouci cron (zatim NENASTAVEN - jen pripraveno).

Pouziti:
    cd /opt/konfigurator && api/venv/bin/python3 scripts/turntable_cleanup.py

Bezpecne spoustet kdykoli a opakovane - maze jen davky neaktivni pres
GRACE_HOURS (24 h), kanonicke soubory aktualne aktivni davky kazdeho
produktu nikdy nesahne (viz _current_canonical_values).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "api", ".env")
for line in open(ENV_PATH):
    line = line.rstrip("\n")
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

import app as appmod  # noqa: F401 - inicializuje DB pool, ktery turntable.py pouziva
import turntable

if __name__ == "__main__":
    deleted = turntable._sweep_expired_batches()
    if not deleted:
        print("Nic k uklizeni (zadna davka neni po grace periode).")
    else:
        total = 0
        for pid, batches in deleted.items():
            print(f"produkt {pid}: smazano davek {len(batches)}: {', '.join(batches)}")
            total += len(batches)
        print(f"celkem smazano davek: {total}")
