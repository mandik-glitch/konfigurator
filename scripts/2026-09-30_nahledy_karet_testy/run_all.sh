#!/bin/bash
# Testy jednotne dlazdice karet (scripts/_nahled_dlazdice.py) a jejiho napojeni v api/turntable.py.
# Konci nenulove, kdyz cokoli selze. Bez DB a site.
cd "$(dirname "$0")" || exit 1
rc=0
/opt/konfigurator/api/venv/bin/python3 test_nahled_dlazdice.py || rc=1
/opt/konfigurator/api/venv/bin/python3 test_turntable_galerie.py || rc=1
[ $rc -eq 0 ] && echo "VSE OK" || echo "NEKTERY TEST SELHAL"
exit $rc
