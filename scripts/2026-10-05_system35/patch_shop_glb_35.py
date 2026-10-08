#!/usr/bin/env python3
"""Pridani SYSTEMU 35 do api/stul_shop.py (recept stul_system35) a api/stul_glb.py (materialy dilu profil_35x35 a zaslepka 3090) - bot10, 2026-10-05. Idempotentni, edituje na miste.
  api/venv/bin/python3 scripts/2026-10-05_system35/patch_shop_glb_35.py [slozka_api]"""
import os
import sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'api')          # volitelne: jina slozka api (zkouska na kopii)
def edit(path, pairs):
    p = os.path.join(API, os.path.basename(path)); s = open(p, encoding='utf-8').read()
    if pairs[0][1] in s:
        print(path, ': system 35 uz je, beze zmeny'); return
    for old, new in pairs:
        assert s.count(old) == 1, (path, s.count(old), old[:90])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s); print(path, ': system 35 pridan')
edit('api/stul_shop.py', [
 ('RECEPT_40 = "stul_system40"                                   # druhy generator: profil SuperLight 40x40 (bot10, 2026-10-04)\nRECEPTY = {RECEPT: 30, RECEPT_40: 40}                         # recept -> system profilu (stul_konfigurator.SYSTEMY)',
  'RECEPT_40 = "stul_system40"                                   # druhy generator: profil SuperLight 40x40 (bot10, 2026-10-04)\nRECEPT_35 = "stul_system35"                                   # treti generator: profil 35x35, drazka 8, spojky ze systemu 30 (bot10, 2026-10-05)\nRECEPTY = {RECEPT: 30, RECEPT_35: 35, RECEPT_40: 40}          # recept -> system profilu (stul_konfigurator.SYSTEMY)'),
 ('JSON {"<shop_product_id>": "stul_system30" | "stul_system40"}', 'JSON {"<shop_product_id>": "stul_system30" | "stul_system35" | "stul_system40"}'),
 ('recept `stul_system30` = profil 30x30 (vychozi), `stul_system40` = SuperLight 40x40; kazdy ma vlastni produktovou kartu.',
  'recept `stul_system30` = profil 30x30 (vychozi), `stul_system35` = profil 35x35 (od 2026-10-05), `stul_system40` = SuperLight 40x40; kazdy ma vlastni produktovou kartu.'),
])
edit('api/stul_glb.py', [
 ('    "Object_11": "alu", "product_3176": "seda", "product_3091": "cerna", "product_3283": "ocel", "product_3220": "seda",          # 3220 = sikma spojka 45 st. pro 40 (vzpery)\n}',
  '    "Object_11": "alu", "product_3176": "seda", "product_3091": "cerna", "product_3283": "ocel", "product_3220": "seda",          # 3220 = sikma spojka 45 st. pro 40 (vzpery)\n'
  '    # SYSTEM 35 (bot10, 2026-10-05): profil 35x35 (cfg_dily profil_35x35), zaslepka 35x35 (3090); rohove spojky 3158, patky 3251 a sikme spojky 3254 jsou ze systemu 30 (Robert), materialy uz jsou vyse\n'
  '    "profil_35x35": "alu", "product_3090": "cerna",\n}'),
])
