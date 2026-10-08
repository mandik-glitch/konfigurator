#!/usr/bin/env python3
"""Zaplata scripts/2026-10-02_stul_testy/run_all.sh: pridava kroky testu 'svitidla LED RUCNE' (bez cislovani "N/45", aby se nerozbilo cislovani dalsich zmen). Kotvena nahrada (assert count == 1:
posledni radek bez nahrady). Pouziti: patch_run_all.py <vstup run_all.sh> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''[ $rc -eq 0 ] && echo "VSE OK" || echo "NEKTERY TEST SELHAL"
'''
DB = "systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3"
b = f'''echo "== SVITIDLA LED RUCNE (led_pocet, led_z1..4; Robert 2026-10-08): generator, GLB, lux data, hash, led_info, 3D ovladani, zive tazeni, ZLATY OTISK 873 konfiguraci; mutace viz scripts/2026-10-08_led_rucne/mutace.py"; api/venv/bin/python3 scripts/2026-10-08_led_rucne/test_led_rucne.py | tail -3 || rc=1
echo "== SVITIDLA LED RUCNE ve verejnem API (schema, pocet, polohy, orez + oznameni, token J, shrnuti, cache, 3D ovladani cs/en/sk vc. simulace orezu hodnot starymi mezemi; DB jen cte)"; {DB} scripts/2026-10-08_led_rucne/test_led_rucne_shop.py 2>&1 | grep -v "WARNING in stul_api" | tail -3 || rc=1
echo "== SVITIDLA LED RUCNE na strance Generator stolu v prohlizeci (slider poctu a polohy, odkaz, uchyt ve 3D + tazeni, nabidka Pridat / Odebrat, mobil)"; {DB} scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-08_led_rucne/test_led_rucne_stranka.js 4934 | tail -4 || rc=1
{a}'''
assert s.count(a) == 1, "kotva: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, b))
print("OK ->", dst)
