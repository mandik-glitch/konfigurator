#!/bin/bash
# Spusti vsechny testy panelu "Rendering -> HDRi", hlasite chyby automatu a vyberu stroje (Logiman2 / notebook). Konci nenulove, kdyz cokoli selze.
cd "$(dirname "$0")" || exit 1
rc=0
node test_panel_svetla.js || rc=1
node test_panel_sestaveni.js || rc=1
node test_admin_nacteni.js || rc=1
/opt/konfigurator/api/venv/bin/python3 test_automat_hlasita_chyba.py || rc=1
/opt/konfigurator/api/venv/bin/python3 test_vyber_stroje.py || rc=1
/opt/konfigurator/api/venv/bin/python3 test_opakovani_automatu.py || rc=1
[ $rc -eq 0 ] && echo "VSE OK" || echo "NEKTERY TEST SELHAL"
exit $rc
