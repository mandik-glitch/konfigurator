#!/opt/konfigurator/api/venv/bin/python
"""Prehled vyroby Vandr: stav razitek karty (bot5, 2026-10-06, nalez bot8): `_razitko_stav` cte shop_products.vandr_razitka_glb_otisk proti SOUCASNEMU GLB (stejne jako render dispatch),
ne product_assemblies (ktere Vandr karty nemaji -> drive VZDY "zadna" a panel psal "Ceka na razitko (bot4)" i u karet, ktere razitka davno maji). Falesny kurzor + docasny adresar
s GLB (zadna DB, nic se nezapisuje) + jen CTENI skutecnych karet z DB.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env [--setenv=VPO_PY=<kandidat>] --working-directory=/opt/konfigurator \
          /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-06_vandr_prehled_razitko_testy/test_razitko_stav.py"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.abspath(os.path.join(HERE, "..", "..", "api"))
VPO = os.environ.get("VPO_PY")
if VPO:
    tmp_kand = tempfile.mkdtemp(prefix="kand_vpo_")
    shutil.copy(VPO, os.path.join(tmp_kand, "vandr_production_overview.py"))
    sys.path.insert(0, tmp_kand)
sys.path.insert(1 if VPO else 0, API)
sys.path.insert(2, os.path.join(HERE, "..", "..", "scripts"))
sys.dont_write_bytecode = True
import app as appmod  # noqa: E402
import vandr_production_overview as vpo  # noqa: E402
import _vandr_razitka_otisk  # noqa: E402

if VPO:
    assert os.path.abspath(vpo.__file__).startswith(os.path.abspath(tmp_kand)), "nacetl se jiny modul: %s" % vpo.__file__
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


class Kurzor:
    def __init__(self, radky):
        self.radky, self._r = radky, None

    def execute(self, sql, params=()):
        assert "FROM shop_products WHERE id=%s" in sql and "product_assemblies" not in sql, sql
        self._r = self.radky.get(params[0])

    def fetchone(self):
        return self._r


tmp = tempfile.mkdtemp(prefix="vpo_katalog_")
vpo.KATALOG_GLB_DIR = tmp
glb = os.path.join(tmp, "a.glb")
open(glb, "wb").write(b"glTF" + b"\x01" * 100)
otisk = _vandr_razitka_otisk.otisk_glb(glb)
K = Kurzor({1: {"glb_file": "a.glb", "vandr_razitka_glb_otisk": otisk}, 2: {"glb_file": "a.glb", "vandr_razitka_glb_otisk": "0" * 64}, 3: {"glb_file": "a.glb", "vandr_razitka_glb_otisk": None},
            4: {"glb_file": None, "vandr_razitka_glb_otisk": otisk}, 5: {"glb_file": "chybi.glb", "vandr_razitka_glb_otisk": otisk}, 6: None})
print("== R _razitko_stav")
over("R1 otisk sedi na soucasny GLB = aktualni", vpo._razitko_stav(K, 1) == "aktualni", vpo._razitko_stav(K, 1))
over("R2 otisk jiny (GLB nebo pravidla se zmenily) = zastarala", vpo._razitko_stav(K, 2) == "zastarala", vpo._razitko_stav(K, 2))
over("R3 razitka se jeste nepocitala (otisk NULL) = zadna", vpo._razitko_stav(K, 3) == "zadna", vpo._razitko_stav(K, 3))
over("R4 karta bez GLB = zadna", vpo._razitko_stav(K, 4) == "zadna", vpo._razitko_stav(K, 4))
over("R5 GLB soubor chybi na disku (otisk je) = zastarala, nespadne", vpo._razitko_stav(K, 5) == "zastarala", vpo._razitko_stav(K, 5))
over("R6 karta neexistuje = zadna", vpo._razitko_stav(K, 6) == "zadna", vpo._razitko_stav(K, 6))
open(glb, "wb").write(b"glTF" + b"\x02" * 100)
over("R7 po zmene GLB souboru (cache podle mtime/velikosti) = zastarala", vpo._razitko_stav(K, 1) == "zastarala", vpo._razitko_stav(K, 1))
vola = []
orig = _vandr_razitka_otisk.otisk_glb
_vandr_razitka_otisk.otisk_glb = lambda c: vola.append(c) or orig(c)
vpo._OTISK_CACHE.clear()
vpo._razitko_stav(K, 2)
vpo._razitko_stav(K, 2)
vpo._razitko_stav(K, 2)
_vandr_razitka_otisk.otisk_glb = orig
over("R8 GLB se nehashuje pri kazdem nacteni panelu: 3 dotazy na stejny nezmeneny soubor = 1 vypocet otisku", len(vola) == 1, vola)
over("R9 _dalsi_krok: aktualni razitko u karty s GLB, cenou a kategorii dal NEhlasi 'Ceka na razitko'", "Čeká na razítko" not in vpo._dalsi_krok({"fbx_export": True, "karta": True, "cena": True, "kategorie": True, "glb": True, "razitko": "aktualni", "elevace": {0, 40}, "web": False}), None)

print("== S skutecne karty v DB (jen cteni)")
conn = appmod.get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT id, sku, glb_file, vandr_razitka_glb_otisk FROM shop_products WHERE sku REGEXP '^VD-[0-9a-f]{8}-' AND vandr_razitka_glb_otisk IS NOT NULL AND glb_file IS NOT NULL ORDER BY id DESC LIMIT 12")
    radky = cur.fetchall()
    vpo.KATALOG_GLB_DIR = appmod.KATALOG_GLB_DIR
    stavy = {r["id"]: vpo._razitko_stav(cur, r["id"]) for r in radky}
over("S1 existuji Vandr karty s razitky v DB (nahodny vzorek 12)", len(radky) > 0, len(radky))
over("S2 aspon jedna z nich je 'aktualni' (drive vsechny 'zadna')", any(v == "aktualni" for v in stavy.values()), stavy)
over("S3 zadna z karet s vypocitanymi razitky neni 'zadna'", all(v in ("aktualni", "zastarala") for v in stavy.values()), stavy)
print("   stavy:", stavy)
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
