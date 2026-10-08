#!/usr/bin/env python3
"""Doplni docs/KONTRAKT_KONFIGURATOR_UI.md o podsekci 'Sikma police na boxy' (hned za sekci 'Horni police mezi zadnimi stojkami', pred 'Vychozi konfigurace generatoru') a opravi vetu
'Sikma police na boxy zatim NENI'; idempotentni.   patch_docs_v2.py <koren_repa>"""
import os
import sys

cil = os.path.join(sys.argv[1], "docs", "KONTRAKT_KONFIGURATOR_UI.md")
s = open(cil, encoding="utf-8").read()
SEKCE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "DOKUMENTACE_SIKMA.md"), encoding="utf-8").read().rstrip() + "\n\n"
stara = "**Šikmá police na boxy zatím NENÍ** (šikmá deska vyžaduje šikmé profily a naklápěcí konzole; generátor má jen osové kolize)."
nova = "**Šikmá police na boxy** je šestý typ (`sikma`) – viz podsekce níže."
if stara in s:
    assert s.count(stara) == 1
    s = s.replace(stara, nova)
if "### Šikmá police na boxy" not in s:
    kotva = "## Výchozí konfigurace generátoru – admin tlačítko"
    assert s.count(kotva) == 1, f"kotva dokumentace: {s.count(kotva)} vyskytu"
    s = s.replace(kotva, SEKCE + kotva)
open(cil, "w", encoding="utf-8").write(s)
