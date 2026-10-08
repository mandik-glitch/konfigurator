#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermeticky import vsech novych a zmenenych modulu (2026-10-02): bez DB, bez serveru, bez site.
api/app.py se NIKDY nenacita - kdo ho potrebuje (scene_offers, vandr_scene_offers), dostane atrapu z _fakes.py.

Chyba importu v api/*.py by po automatickem nasazeni (12:30/3:30) shodila sluzbu, proto je tahle kontrola povinna
pred commitem. Spusteni: /opt/konfigurator/api/venv/bin/python scripts/2026-10-02_v3d_testy/test_import.py
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import _cesty as CE  # noqa: E402

PY = sys.executable
API = os.path.join(CE.REPO, "api")
V3D = os.path.join(CE.REPO, "scripts", "v3d")


def cisty_beh(kod, cwd):
    """novy interpreter, prostredi jen PATH (+ lib adresar) - zadne DB_* ani V3D_MARK_SECRET, cwd = prazdny tmp"""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1"}
    if os.environ.get("V3D_LIB_DIR"):
        env["V3D_LIB_DIR"] = os.environ["V3D_LIB_DIR"]
    return subprocess.run([PY, "-c", kod], env=env, cwd=cwd, capture_output=True, text=True, timeout=120)


def vypis(adr):
    out = []
    for d, _dirs, files in os.walk(adr):
        out += [os.path.join(d, f) for f in files]
    return sorted(out)


class TestImportCisty(unittest.TestCase):
    def test_api_moduly_bez_zavislosti_na_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            pred = vypis(CE.REPO) if os.path.getsize(__file__) else []
            r = cisty_beh("import sys; sys.path.insert(0, %r)\n"
                          "import v3d_glb, v3d_mark, vandr_vykres_nahrada\n"
                          "assert 'app' not in sys.modules and 'pymysql' not in sys.modules\n"
                          "print('OK', v3d_glb.V3DError.__mro__[1].__name__, v3d_mark.VERZE)" % API, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("OK ValueError", r.stdout)
            self.assertEqual(vypis(CE.REPO), pred, "import nesmi vytvorit soubory (napr. __pycache__) v repu")

    def test_scripts_v3d_bez_db_a_bez_blenderu(self):
        with tempfile.TemporaryDirectory() as tmp:
            pred = vypis(CE.REPO)
            r = cisty_beh("import sys\nsys.path.insert(0, %r); sys.path.insert(0, %r)\n"
                          "import build_ctx, offer_model, vandr_motions, v3d_mark_detect\n"
                          "assert 'pymysql' not in sys.modules, 'import nesmi otevirat DB'\n"
                          "assert 'app' not in sys.modules\n"
                          "assert offer_model.V3DBuildError.__mro__[1] is RuntimeError\n"
                          "import os; assert os.path.isfile(build_ctx._najdi_pohyby() or '')\n"
                          "print('OK', offer_model.verze_buildu())" % (V3D, API), tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertRegex(r.stdout, r"OK b\d+-[0-9a-f]{6}")
            self.assertEqual(vypis(CE.REPO), pred, "import nesmi vytvorit soubory v repu")

    def test_build_skript_je_jen_pro_blender(self):
        """vandr_offer_build.py importuje bpy (jen uvnitr Blenderu) - mimo nej se jen kompiluje"""
        with open(os.path.join(V3D, "vandr_offer_build.py"), encoding="utf-8") as f:
            compile(f.read(), "vandr_offer_build.py", "exec")


class TestImportPodAtrapami(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import _fakes as F
        cls.F = F
        cls.tmp = tempfile.mkdtemp(prefix="import_", dir=CE.OUT)
        cls.db = F.FakeDB(["4910"])
        cls.app, cls.audit, cls.vso = F.install_stubs(cls.db, cls.tmp)

    @classmethod
    def tearDownClass(cls):
        cls.F.uninstall_stubs()

    def test_trasy_zaregistrovany(self):
        pravidla = {(r.rule, tuple(sorted(r.methods - {"HEAD", "OPTIONS"}))) for r in self.app.url_map.iter_rules()}
        self.assertIn(("/api/admin/vandr-vyroba/<int:shop_product_id>/nabidka", ("POST",)), pravidla)
        self.assertIn(("/api/public/offers/<token>/model", ("GET",)), pravidla)

    def test_import_nedela_dotazy_do_db(self):
        self.assertEqual(self.db.dotazy, [])
        self.assertEqual(self.db.spojeni_otevrena, 0)

    def test_funkce_pro_ostatni_boty(self):
        self.assertTrue(callable(self.vso.can_create_offer))
        import scene_offers
        self.assertTrue(callable(scene_offers.save_offer_model_bytes))
        self.assertIn("v3d_anim", scene_offers.CLICK_TARGETS)

    def test_v3d_moduly_se_nacitaji_az_pri_pouziti(self):
        """chybejici/vadny modul 3D nesmi shodit import (a tim start sluzby): v3d_glb, v3d_mark, offer_model, build_ctx"""
        F = self.F
        zakazano = {"offer_model", "build_ctx", "v3d_glb", "v3d_mark"}

        class Blokuj:
            def find_spec(self, name, path=None, target=None):
                if name in zakazano:
                    raise ImportError("atrapa: modul %s chybi" % name)
                return None
        blok = Blokuj()
        sys.meta_path.insert(0, blok)
        try:
            db = F.FakeDB(["4910"])
            tmp = tempfile.mkdtemp(prefix="import2_", dir=CE.OUT)
            app, _audit, vso = F.install_stubs(db, tmp)      # znovu cisty import scene_offers + vandr_scene_offers
            self.assertTrue(callable(vso.vandr_vyroba_vytvorit_nabidku))
            for n in zakazano:
                self.assertNotIn(n, sys.modules, "%s se nacetl pri importu" % n)
            with self.assertRaises(ImportError):
                vso._offer_model()
        finally:
            sys.meta_path.remove(blok)
            F.uninstall_stubs()
            # vratit stav pro ostatni testy v tomto souboru
            type(self).app, type(self).audit, type(self).vso = F.install_stubs(self.db, self.tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
