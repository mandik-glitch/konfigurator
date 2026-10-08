#!/opt/konfigurator/api/venv/bin/python
"""Spusti existujici sadu testu stolu (bot8, scripts/2026-10-02_stul_testy/*.py) nad SYSTEMEM 35 S NAVLEKEM jako vychozim stavem (bot10, 2026-10-05): VYCHOZI["system"] = 35, VYCHOZI["navlek"] = True,
VYCHOZI["kolecka"] = False (navlek nahrazuje kolecka). Smysl maji sady, ktere hlidaji NEZAVISLE invarianty (napojeni, zive tazeni proti modelu ze serveru, ovladani ve 3D, vyrobni vypis, meze...);
testy s pevnymi cisly sablony nebo ocekavanim koleček jako vychozi koncovky muzou opravnene selhat.

  api/venv/bin/python scripts/2026-10-05_system35/spust_s_navlekem.py scripts/2026-10-02_stul_testy/test_stul_zive.py [delka_navleku]"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_konfigurator as S  # noqa: E402

if len(sys.argv) < 2:
    sys.exit("pouziti: spust_s_navlekem.py <test.py> [argumenty testu]")
S.VYCHOZI["system"] = 35
S.VYCHOZI["navlek"] = True
S.VYCHOZI["kolecka"] = False
S._SYSTEM.set(35)
test = os.path.abspath(sys.argv[1])
sys.argv = [test] + sys.argv[2:]
sys.path.insert(0, os.path.dirname(test))
runpy.run_path(test, run_name="__main__")
