#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mutacni kontrola test_vzhled_api.py: rozbije jednu vec v api/v3d_vzhled.py (kopie v docasne slozce) a overi, ze test selze. "!!!" = mutaci test nechytil (exit 1).
Nic se nezapisuje do repa ani do DB.  api/venv/bin/python scripts/2026-10-06_v3d_vzhled_testy/_mutace_vzhled.py"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TEST = os.path.join(HERE, "test_vzhled_api.py")
ZDROJ = open(os.environ.get("V3D_VZHLED_ZDROJ") or os.path.join(REPO, "api", "v3d_vzhled.py"), encoding="utf-8").read()          # V3D_VZHLED_ZDROJ = kandidat modulu pred nasazenim

MUTACE = [
    ("PUT bez opravneni", '@require_permission("nastaveni", "upravit")\n', ""),
    ("meze strength rozsirene (30 misto 3)", '"strength": (0.1, 3.0)', '"strength": (0.1, 30.0)'),
    ("nezname klice nahore se prijmou", '    cizi = set(body) - {"env", "alu", "ao", "sat", "barvy", "lesk", "ao_mat", "alu_cfg", "ao_cfg"}\n    if cizi:\n        raise ValueError("neznamy klic " + ", ".join(sorted(map(str, cizi))))\n', ""),
    ("hlinik: navic nezname 'zlaty'", 'ALU = ("puvodni", "satin", "matny", "eloxovany", "bez")', 'ALU = ("puvodni", "satin", "matny", "eloxovany", "bez", "zlaty")'),
    ("PUT bez auditu", '    log_audit(u["id"] if u else None, "update", "v3d_vzhled", None, {"vzhled": ulozeno})\n', ""),
    ("GET vyzaduje opravneni", '@app.get("/api/public/v3d-vzhled")\n', '@app.get("/api/public/v3d-vzhled")\n@require_permission("nastaveni", "zobrazit")\n'),
    ("null neresetuje (vzdy INSERT)", '    if v == prazdny():\n        sql, args = "DELETE FROM app_settings WHERE setting_key=%s", (KLIC,)\n    else:\n',
     '    if True:\n'),
    ("poskozena ulozena hodnota shodi GET (bez try/except)", "    except Exception as e:                                      # noqa: BLE001\n        app.logger.warning(\"v3d vzhled nabidek: ulozenou hodnotu nejde nacist, plati vychozi: %s\", e)\n        v = prazdny()\n",
     "    except ZeroDivisionError:\n        v = prazdny()\n"),
    ("PUT neaktualizuje cache", '    _cache["t"], _cache["v"] = time.time(), dict(v)\n    return dict(v)\n', "    return dict(v)\n"),
    ("GET bez Cache-Control no-cache", '    resp.headers["Cache-Control"] = "no-cache"\n', ""),
    ("hdri 'mistnost' chybi", 'ENV_HDRI = ("crossfit", "tv_studio", "berg_inner", "teufelsberg", "mistnost")', 'ENV_HDRI = ("crossfit", "tv_studio", "berg_inner", "teufelsberg")'),
    ("zapis do jineho klice", 'KLIC = "v3d_nabidka_vzhled"', 'KLIC = "v3d_nabidka_vzhled2"'),
    ("sat: horni mez 20 misto 2", 'SAT_MEZE = (0.0, 2.0)', 'SAT_MEZE = (0.0, 20.0)'),
    ("barvy: limit 400 misto 40", 'BARVY_MAX = 40 ', 'BARVY_MAX = 400 '),
    ("barvy: hex se nevaliduje", '_HEX6.fullmatch(k) and _HEX6.fullmatch(v)', 'True'),
    ("barvy: hex se neuklada malymi pismeny", 'out[k.lower()] = v.lower()', 'out[k] = v'),
    ("sat 1 se uklada misto null", 'out["sat"] = None if v == 1.0 else v', 'out["sat"] = v'),
    ("nezname klice (sat/barvy) se nepovoli", '{"env", "alu", "ao", "sat", "barvy", "lesk", "ao_mat", "alu_cfg", "ao_cfg"}', '{"env", "alu", "ao"}'),
    # odlesky, hlinik a AO (api/v3d_vzhled.py 5j) a doplnena HDRI (5k)
    ("lesk: horni mez 20 misto 2", 'LESK_MEZE = (0.0, 2.0)', 'LESK_MEZE = (0.0, 20.0)'),
    ("lesk 1 se neodstrani", '        if v != 1.0:\n            out[k.lower()] = v\n', '        out[k.lower()] = v\n'),
    ("lesk: klic se nevaliduje", 'if not (isinstance(k, str) and _HEX6.fullmatch(k)):', 'if False:'),
    ("lesk: limit materialu zrusen", '        raise ValueError("%s: nejvyse %d materialu" % (jmeno, BARVY_MAX))\n', '        pass\n'),
    ("hlinik: odrazy nad mez (15)", '"refl": (0.0, 1.5)', '"refl": (0.0, 15.0)'),
    ("hlinik: matnost pod mez (0,05)", '"rough": (0.5, 2.0)', '"rough": (0.05, 2.0)'),
    ("AO: dosah pod mez (0,025)", '"r": (0.25, 3.0)', '"r": (0.025, 3.0)'),
    ("AO: sila nad mez (20)", '"k": (0.0, 2.0)', '"k": (0.0, 20.0)'),
    ("nasobky: nezname klice se prijmou", '    cizi = set(cfg) - set(meze)\n    if cizi:\n        raise ValueError("%s: neznamy klic %s" % (jmeno, ", ".join(sorted(map(str, cizi)))))\n', ''),
    ("nasobky: same 1 se ulozi misto null", '    return None if all(v == 1.0 for v in out.values()) else out\n', '    return out\n'),
    ("nasobky: chybejici klic = 0 misto 1", 'v = cfg.get(k, 1.0)', 'v = cfg.get(k, 0.0)'),
    ("doplnena HDRI se pri ulozeni nepripousti (ani po obnoveni cache)", '    klice = ENV_HDRI + v3d_env_import.extra_klice()\n    if cfg.get("hdri") not in klice:\n        klice = ENV_HDRI + v3d_env_import.extra_klice(force=True)        # prave doplnene HDRI jeste nemusi byt v cache tohoto workeru\n', '    klice = ENV_HDRI\n'),
    ("doplnena HDRI: bez opakovaneho overeni s force", '    if cfg.get("hdri") not in klice:\n        klice = ENV_HDRI + v3d_env_import.extra_klice(force=True)', '    if False:\n        klice = ENV_HDRI + v3d_env_import.extra_klice(force=True)'),
    ("verejny GET bez hdri_extra", '    d["hdri_extra"] = v3d_env_import.public_extra()', '    pass'),
    # AO po komponentech (ao_mat, alu_cfg.ao; viewer3d.js 1.16.0)
    ("ao_mat: horni mez 20 misto 2", 'AO_MAT_MEZE = (0.0, 2.0)', 'AO_MAT_MEZE = (0.0, 20.0)'),
    ("ao_mat se z tela PUT neuklada", '    if body.get("ao_mat") is not None:\n        out["ao_mat"] = over_ao_mat(body["ao_mat"])\n', ''),
    ("alu_cfg.ao: horni mez 20 misto 2", '"ao": (0.0, 2.0)}        # hlinik', '"ao": (0.0, 20.0)}        # hlinik'),
    ("alu_cfg.ao: v mezich chybi (neznamy klic)", ', "ao": (0.0, 2.0)}        # hlinik', '}        # hlinik'),
    ("vychozi vzhled bez klice ao_mat", '"lesk": None, "ao_mat": None, "alu_cfg": None, "ao_cfg": None}', '"lesk": None, "alu_cfg": None, "ao_cfg": None}'),
    ("ao_mat: hodnota se nevaliduje (jen lesk)", '        if not _cislo(v) or not meze[0] <= v <= meze[1]:', '        if not _cislo(v):'),
]
vysl = []
for nazev, a, b in MUTACE:
    if ZDROJ.count(a) != 1:
        print("CHYBA PRIPRAVY '%s': vzor nalezen %d x" % (nazev, ZDROJ.count(a)))
        vysl.append((nazev, None))
        continue
    with tempfile.TemporaryDirectory(prefix="mutace_vzhled_") as d:
        cesta = os.path.join(d, "v3d_vzhled.py")
        open(cesta, "w", encoding="utf-8").write(ZDROJ.replace(a, b))
        r = subprocess.run([sys.executable, "-B", TEST], env=dict(os.environ, V3D_VZHLED_MODUL=cesta, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True, timeout=120)
    vysl.append((nazev, r.returncode))
    print(("chyceno " if r.returncode != 0 else "!!! NECHYCENO ") + "| " + nazev)
spatne = [n for n, rc in vysl if rc in (0, None)]
print("\n%d mutaci, chyceno %d, nechyceno/chyba pripravy %d" % (len(MUTACE), len(MUTACE) - len(spatne), len(spatne)))
sys.exit(1 if spatne else 0)
