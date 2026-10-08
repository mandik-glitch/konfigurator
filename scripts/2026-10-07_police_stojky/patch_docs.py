#!/usr/bin/env python3
"""Doplni docs/KONTRAKT_KONFIGURATOR_UI.md o sekci 'Horni police mezi zadnimi stojkami' (pred sekci 'Vychozi konfigurace generatoru'); idempotentni.   patch_docs.py <koren_repa>"""
import os
import sys

cil = os.path.join(sys.argv[1], "docs", "KONTRAKT_KONFIGURATOR_UI.md")
s = open(cil, encoding="utf-8").read()
SEKCE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "DOKUMENTACE_KONTRAKT.md"), encoding="utf-8").read().rstrip() + "\n\n"
if "## Horní police mezi zadními stojkami" not in s:
    kotva = "## Výchozí konfigurace generátoru – admin tlačítko"
    assert s.count(kotva) == 1, f"kotva dokumentace: {s.count(kotva)} vyskytu"
    s = s.replace(kotva, SEKCE + kotva)
open(cil, "w", encoding="utf-8").write(s)
