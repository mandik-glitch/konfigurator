#!/usr/bin/env python3
"""Zaplata scripts/2026-10-02_stul_testy/run_all.sh: pridava kroky testu 'LED 600 v generatoru' (bez cislovani "N/45", aby se nerozbilo cislovani dalsich zmen). Kotvena nahrada
(assert count == 1: posledni radek bez nahrady). Pouziti: patch_run_all.py <vstup run_all.sh> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''[ $rc -eq 0 ] && echo "VSE OK" || echo "NEKTERY TEST SELHAL"
'''
DB = "systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3"
b = f'''echo "== LED 600 (delka svitidla 1200 / 600): generator, GLB, lux data, ZLATY OTISK 465 konfiguraci proti stavu pred zavedenim volby, geometrie z vrcholu meshe, hash, led_info, 3D menu; mutace viz scripts/2026-10-07_led600_generator/mutace.py"; api/venv/bin/python3 scripts/2026-10-07_led600_generator/test_led_delka.py | tail -3 || rc=1
echo "== LED 600: zive tazeni ramene LED se svitidly 600 (nezavisle proti modelu ze serveru)"; api/venv/bin/python3 scripts/2026-10-07_led600_generator/test_led_delka_zive.py | tail -3 || rc=1
echo "== LED 600 ve verejnem API (schema, volba, cena karty x pocet, kusovnik, nabidka kratsiho svitidla, gating aktivni karty, token, shrnuti, cache, 3D menu, lux payload; DB jen cte)"; {DB} scripts/2026-10-07_led600_generator/test_led_delka_shop.py 2>&1 | grep -v "WARNING in stul_api" | tail -3 || rc=1
echo "== LED 600 a pocitadlo luxu (katalog LED600, LuxCore v Node, linearita, srovnani s LED 1200; pouze po nasazeni statickeho JS: apply_js.sh)"; api/venv/bin/python3 scripts/2026-10-07_led600_generator/test_led_delka_lux.py | tail -3 || rc=1
echo "== LED 600 na strance Generator stolu v prohlizeci + pocitadlo luxu (select delky, nabidka kratsiho svitidla, stupne podle typu svitidla, mobil)"; {DB} scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-07_led600_generator/test_led_delka_stranka.js 4934 | tail -4 || rc=1
{a}'''
assert s.count(a) == 1, "kotva: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, b))
print("OK ->", dst)
