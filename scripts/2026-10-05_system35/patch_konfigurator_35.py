#!/usr/bin/env python3
"""Pridani SYSTEMU 35 do api/stul_konfigurator.py (bot10, 2026-10-05): vstup cesta ke zdroji, vystup cesta (nebo --inplace). Idempotentni (druhe spusteni nic nemeni).
Robert 2026-10-05: 'systém 35 ... kompatibilni s 30/40; pouzivaji se spojky systemu 30, vzdy vystredit na stred drazky'.
  api/venv/bin/python3 scripts/2026-10-05_system35/patch_konfigurator_35.py <zdroj.py> <vystup.py>"""
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()
if 'SABLONA_PATH_35' in s:
    open(dst, 'w', encoding='utf-8').write(s); print('system 35 uz je ve zdroji - beze zmeny'); sys.exit(0)
def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:90])
    s = s.replace(old, new)
rep('SABLONA_PATH_40 = os.path.join(_DIR, "stul_sablona_system40.json")\n',
    'SABLONA_PATH_40 = os.path.join(_DIR, "stul_sablona_system40.json")\nSABLONA_PATH_35 = os.path.join(_DIR, "stul_sablona_system35.json")\n')
rep('    40: {"system": 40, "profil": "Object_11", "profil_mm": 40.0,',
    '''    35: {"system": 35, "profil": "profil_35x35", "profil_mm": 35.0, "spojka": "product_3158", "sablona": SABLONA_PATH_35, "nazev_profilu": "profil 35×35",   # Robert 2026-10-05: spojky systemu 30, vystredene na stred drazky
         "zaslepka": "product_3090", "zaslepka_vyska": 3.3, "patka": "product_3251", "patka_delka": 75.0, "patka_zasun": 30.0,
         "deska_zkraceni": 5.0,                 # zadni hrana desek lezi na lici zadnich noh, ktere jsou o 2 x 2,5 mm vic vpredu
         "police_min_od_podlahy": 132.5,        # stejne spodni lico ramu police nad podlahou jako v 30 (osa o 2,5 mm vys)
         "vyrez_x": 105.0,                      # zavesy police pod vyrezem jsou o 5 mm sirsi (profil 35)
         "odstup_od_nohou": 30.0,               # rohove spojky 3158 (rameno 27 mm) u strednich noh sahaji 27 + 17,5 = 44,5 mm od osy nohy: box od lice nohy 30 mm = 47,5 mm od osy (3 mm za spojkou)
         "vzpery": True},                       # sikme vzpery ramen LED (spojka 3254 ze systemu 30, vystredena na stred drazky)
    40: {"system": 40, "profil": "Object_11", "profil_mm": 40.0,''')
rep('VZPERY_SPOJKY = tuple(s["vzpera_spojka"] for s in SYSTEMY.values())',
    'SYSTEMY[35].update(vzpera_spojka=VZPERA_SPOJKA, vzpera_sten=VZPERA_STEN, vzpera_celo_lat=VZPERA_CELO_STRED, vzpera_celo_osa=0.0, vzpera_lat_nativni="x", vzpera_sku="2.2.001.08.3030.06")      # spojka 3254 ze systemu 30\nVZPERY_SPOJKY = tuple(s["vzpera_spojka"] for s in SYSTEMY.values())')
# sdilene dily (spojka 3158, patka 3251, sikma spojka 3254 jsou v systemech 30 i 35) se v souhrnnych n-ticich nesmi opakovat (testy a kod, ktery scita pocty pres tyhle n-tice, by dily pocital dvakrat)
rep('SPOJKY_PARTS = tuple(s["spojka"] for s in SYSTEMY.values())           # rohove spojky vsech systemu',
    'SPOJKY_PARTS = tuple(dict.fromkeys(s["spojka"] for s in SYSTEMY.values()))           # rohove spojky vsech systemu (bez opakovani: 3158 je v systemech 30 i 35)')
rep('KONCE_PARTS = tuple(s["zaslepka"] for s in SYSTEMY.values()) + tuple(s["patka"] for s in SYSTEMY.values())      # zaslepky a patky vsech systemu',
    'KONCE_PARTS = tuple(dict.fromkeys([s["zaslepka"] for s in SYSTEMY.values()] + [s["patka"] for s in SYSTEMY.values()]))      # zaslepky a patky vsech systemu (bez opakovani)')
rep('VZPERY_SPOJKY = tuple(s["vzpera_spojka"] for s in SYSTEMY.values())          # sikme spojky vsech systemu',
    'VZPERY_SPOJKY = tuple(dict.fromkeys(s["vzpera_spojka"] for s in SYSTEMY.values()))          # sikme spojky vsech systemu (bez opakovani)')
# poznamka ke spojovacimu materialu: system 35 ma spojky 3158 a 3254 jako system 30 (M6x12 / matice drazka 8) - text pro 30 plati pro vse krome 40
rep('+ 2 ks 2.1.001.08.06 – Robert 2026-10-04; názvy jsou názvy karet z katalogu" if p["system"] == 30 else',
    '+ 2 ks 2.1.001.08.06 – Robert 2026-10-04; názvy jsou názvy karet z katalogu" if p["system"] != 40 else')
rep('_NAZVY = {"Object_7": "profil 30×30", "Object_11": "profil 40×40",', '_NAZVY = {"Object_7": "profil 30×30", "Object_11": "profil 40×40", "profil_35x35": "profil 35×35", "product_3090": "záslepka profilu 35×35",')
rep("  Parametr `system` (30 | 40, vychozi 30) vybira zaznam v SYSTEMY: profil (30: Object_7 = Light 30x30; 40: Object_11 = SuperLight S10 40x40), rohovou spojku (3158 / 3176), zmrazenou\n",
    "  Parametr `system` (30 | 35 | 40, vychozi 30) vybira zaznam v SYSTEMY: profil (30: Object_7 = Light 30x30; 35: profil_35x35 = 35x35 s drazkou 8 - od 2026-10-05 (Robert: 'spojky systemu 30, vzdy\n"
    "  vystredit na stred drazky': rohove spojky 3158, patky 3251 a sikme spojky 3254 jsou ze systemu 30, zaslepka 3090 je 35x35, sablona `stul_sablona_system35.json` z odvod_sablony_35.py); 40: Object_11 = SuperLight S10 40x40),\n"
    "  rohovou spojku (3158 / 3158 / 3176), zmrazenou\n")
open(dst, 'w', encoding='utf-8').write(s)
print('system 35 pridan:', dst)
