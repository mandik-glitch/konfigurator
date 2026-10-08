#!/bin/bash
# Prvky generatoru NAPRIC MISTY (Robert 2026-10-05; bot16): koty, okno Hlavni profil, okno Pripni cokoli - interni stranky Generator stolu, mini-shopy, vlozeny generator. Spusteni z korene repa (jako root):
#   bash scripts/2026-10-05_prvky_napric_testy/run_all.sh        (~8 min; DB se jen cte, nic se nezapisuje)
cd /opt/konfigurator || exit 2
SD="systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator"
rc=0
echo "== 1/3 prvky napric misty (embed + interni stranky 01-03 + mini-shop demo x systemy 30/35/40, uzke okno)"
$SD --setenv=BRIDGE_CARDS=real api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge.py scripts/2026-10-05_prvky_napric_testy/test_prvky_napric_misty.js 9001 | tail -4 || rc=1
echo "== 2/3 mini-shop SK nad skutecnymi daty (produkty 1 / 2 / 3: koty v jazyce obchodu, Hlavni profil, Pripni cokoli)"
$SD api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge_miniweb.py scripts/2026-10-05_prvky_napric_testy/test_prvky_minishop.js | tail -4 || rc=1
echo "== 3/3 koty na verejnych strankach (mini-shop demo; siroke i uzke okno)"
$SD api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge.py scripts/2026-10-02_stul_testy/test_stul_koty_verejne.js 9001 | tail -4 || rc=1
exit $rc
