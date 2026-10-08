#!/opt/konfigurator/api/venv/bin/python
"""Spusti existujici sadu testu stolu (bot8, scripts/2026-10-02_stul_testy/*.py) nad JINYM SYSTEMEM profilu (bot10, 2026-10-04).

  api/venv/bin/python scripts/2026-10-04_system40/spust_v_systemu.py 40 scripts/2026-10-02_stul_testy/test_stul_zive.py

Nastavi `stul_konfigurator.VYCHOZI["system"]` (vychozi hodnota parametru `system`) pred spustenim testu, takze KAZDE volani generatoru bez explicitniho `system` bezi ve zvolenem systemu.
Testy s pevnymi cisly sablony #577 (zlaty test, konkretni delky) muzou v systemu 40 oprávněně selhat - smysl maji sady, ktere hlidaji NEZAVISLE invarianty (napojeni, zive tazeni proti modelu
ze serveru, ovladani ve 3D, vyrobni vypis...). Co selhalo a proc, je v README.md (oddil "Sady testu nad systemem 40")."""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_konfigurator as S  # noqa: E402

if len(sys.argv) < 3:
    sys.exit("pouziti: spust_v_systemu.py <30|40> <test.py> [argumenty testu]")
S.VYCHOZI["system"] = S.over_system(sys.argv[1])
S._SYSTEM.set(S.VYCHOZI["system"])                       # i kod mimo generator (S.sablona(), S._aabb...) bezi ve zvolenem systemu
test = os.path.abspath(sys.argv[2])
sys.argv = [test] + sys.argv[3:]
sys.path.insert(0, os.path.dirname(test))
runpy.run_path(test, run_name="__main__")
