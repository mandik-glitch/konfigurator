#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermeticky test trasy GET /api/kontrola-scena/v3d/<karta>.glb (api/vandr_scene_offers.py::kontrolni_scena_v3d_model), 2026-10-06.

Robert: "automatizovat proces bez zasahu rucne botem na kazdou FBX vyexportovanou sestavu" - kontrolni scena (rezim=nabidka) uz nectou
rucne udelane soubory webapp/katalog/vandr/v3d_nahled/<karta>.glb, model s pohyby se postavi pri otevreni karty (stejny build + cache + pojistka
jako pri zalozeni nabidky).

Spusteni:  /opt/konfigurator/api/venv/bin/python scripts/2026-10-02_v3d_testy/test_kontrola_route.py     (~40 s, jeden skutecny Blender build)
Co je skutecne: Flask routing, SKUTECNY api/vandr_scene_offers.py (trasa, build, cache, zamek, pojistka v3d_glb), Blender CPU, katalogove GLB (jen CTENI).
Co je atrapa: databaze (FakeDB - zapis = chyba testu), modul `app` (vc. staff_required s prepinacem staff_ok), vystup `php artisan vandr:offer-data`."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import _cesty as CE  # noqa: E402
import _fakes as F  # noqa: E402

KARTA = "4910"
BLENDER_OK = os.path.exists(CE.BLENDER)
S = {}
URL = "/api/kontrola-scena/v3d/%s.glb"


def get(k, client=None):
    c = client or S["app"].test_client()
    return c.get(URL % k)


def reset():
    vso, om = S["vso"], S["offer_model"]
    vso._spust_artisan = F.artisan_nova(KARTA)
    vso._postav_v3d_model = S["puvodni"]["postav"]
    vso._offer_model = S["puvodni"]["offer_model"]
    om.spust_build = S["puvodni"]["spust_build"]
    om.build_offer_model = S["puvodni"]["build_offer_model"]
    vso._oznac_model = S["puvodni"]["oznac"]
    vso.V3D_VYPNUTO_SOUBOR = os.path.join(S["tmp"], "v3d-vypnuto-neexistuje")
    S["appmod"].staff_ok = True
    S["db"].offers.clear()
    S["db"].drive_files.clear()
    S["db"].dotazy.clear()
    S["audit"].clear()
    os.environ.pop("V3D_MARK_SECRET", None)
    vso.V3D_CACHE_DIR = tempfile.mkdtemp(prefix="cache_", dir=S["tmp"])


def setUpModule():
    S["tmp"] = tempfile.mkdtemp(prefix="kontrola_route_", dir=CE.OUT)
    S["db"] = F.FakeDB([KARTA, "4594"])
    S["app"], S["audit"], vso = F.install_stubs(S["db"], S["tmp"])
    S["vso"] = vso
    S["appmod"] = sys.modules["app"]
    import offer_model
    import build_ctx
    import v3d_glb
    S.update(offer_model=offer_model, build_ctx=build_ctx, v3d_glb=v3d_glb)
    import scene_offers
    S["scene_offers"] = scene_offers
    vso.KATALOG_DIR = CE.KATALOG
    build_ctx.KATALOG_DIR = CE.KATALOG
    gs = os.path.join(CE.REPO, "scripts", "2026-09-28_vandr_offer_geometry.py")
    vso.GEOMETRY_SCRIPT = gs if os.path.exists(gs) else "/opt/konfigurator/scripts/2026-09-28_vandr_offer_geometry.py"
    vso._read_vandr_image = lambda rel: F.PNG1                 # jen pro test "cache sdilena s nabidkou" (POST nabidky cte obrazky Vandru)
    vso.CONTENT_FILES_DIR = CE.CONTENT_FILES
    S["puvodni"] = {"postav": vso._postav_v3d_model, "offer_model": vso._offer_model, "spust_build": offer_model.spust_build,
                    "build_offer_model": offer_model.build_offer_model, "oznac": vso._oznac_model}


def tearDownModule():
    F.uninstall_stubs()
    shutil.rmtree(S.get("tmp", ""), ignore_errors=True)


class Base(unittest.TestCase):
    def setUp(self):
        reset()


class TestRouting(Base):
    def test_trasa_je_zaregistrovana_jen_pro_get(self):
        pravidla = {r.rule: sorted(r.methods - {"HEAD", "OPTIONS"}) for r in S["app"].url_map.iter_rules()}
        self.assertEqual(pravidla.get("/api/kontrola-scena/v3d/<ids>.glb"), ["GET"])

    def test_spatna_cesta_je_404_a_post_405(self):
        c = S["app"].test_client()
        self.assertEqual(c.get("/api/kontrola-scena/v3d/abc.glb").status_code, 404)
        self.assertEqual(c.get("/api/kontrola-scena/v3d/%s" % KARTA).status_code, 404)           # bez .glb
        self.assertEqual(c.get("/api/kontrola-scena/v3d/-1.glb").status_code, 404)
        self.assertEqual(c.post(URL % KARTA).status_code, 405)
        self.assertEqual(S["db"].dotazy, [], "spatna cesta nesmi sahnout do DB")

    def test_jen_zamestnanci(self):
        S["appmod"].staff_ok = False
        vso = S["vso"]
        vso._spust_artisan = F.artisan_nova(KARTA)
        r = get(KARTA)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["code"], "unauthorized")
        self.assertEqual(vso._spust_artisan.volani, [], "bez prihlaseni se nesmi spustit Vandr ani Blender")
        self.assertEqual(S["db"].dotazy, [], "bez prihlaseni se nesmi cist DB")


class TestOdmitnuti(Base):
    """Kazde odmitnuti = JSON {"error": cesky text}, zadny GLB, zadny Blender, zadny zapis."""

    def setUp(self):
        super().setUp()
        self.puvodni = dict(S["db"].shop_products[int(KARTA)])
        S["vso"]._spust_artisan = F.artisan_nova(KARTA)
        self.buildy = []
        S["offer_model"].spust_build = lambda *a, **k: self.buildy.append(a)

    def tearDown(self):
        S["db"].shop_products[int(KARTA)] = self.puvodni

    def over(self, r, stav, text_obsahuje):
        self.assertEqual(r.status_code, stav, r.get_data(as_text=True)[:200])
        self.assertTrue(r.mimetype == "application/json", r.mimetype)
        j = r.get_json()
        self.assertEqual(list(j), ["error"])
        self.assertIn(text_obsahuje, j["error"])
        self.assertEqual(self.buildy, [], "pri odmitnuti se Blender nesmi spustit")
        self.assertEqual(S["db"].offers, [])
        self.assertEqual(S["audit"], [])

    def test_karta_neexistuje(self):
        self.over(get("999999"), 404, "Karta neexistuje.")

    def test_neni_vandr_karta(self):
        for sku in ("DIL-123", None, "vd-malym", "STUL.SYSTEM30.KONF", ""):
            S["db"].shop_products[int(KARTA)] = dict(self.puvodni, sku=sku)
            self.over(get(KARTA), 400, "není to Vandr karta")

    def test_bez_glb(self):
        for g in (None, ""):
            S["db"].shop_products[int(KARTA)] = dict(self.puvodni, glb_file=g)
            self.over(get(KARTA), 400, "ještě nemá hotový 3D model")

    def test_glb_chybi_na_disku(self):
        S["db"].shop_products[int(KARTA)] = dict(self.puvodni, glb_file="vandr/neexistuje.glb")
        self.over(get(KARTA), 400, "GLB soubor chybí na disku: vandr/neexistuje.glb")

    def test_vypnuto_souborem(self):
        soubor = os.path.join(S["tmp"], "v3d-vypnuto")
        open(soubor, "w").close()
        S["vso"].V3D_VYPNUTO_SOUBOR = soubor
        r = get(KARTA)
        self.over(r, 503, "vypnutý souborem")
        self.assertEqual(S["vso"]._spust_artisan.volani, [], "vypnuto = ani Vandr se nevola")

    def test_vandr_selze(self):
        def artisan(argumenty, timeout_s):
            artisan.volani.append(list(argumenty))
            return F.Proc(2, "", "SQLSTATE[HY000] Connection refused")
        artisan.volani = []
        S["vso"]._spust_artisan = artisan
        self.over(get(KARTA), 502, "Načtení dat z Vandru selhalo")

    def test_vandr_timeout(self):
        def artisan(argumenty, timeout_s):
            raise subprocess.TimeoutExpired(argumenty, timeout_s)
        S["vso"]._spust_artisan = artisan
        self.over(get(KARTA), 502, "Načtení dat z Vandru selhalo")

    def test_stara_verze_vandr_prikazu_bez_v3d(self):
        S["vso"]._spust_artisan = F.artisan_stara(KARTA)
        self.over(get(KARTA), 502, "3D model nevznikl: Vandr příkaz bez --v3d")

    def test_vystup_bez_klice_v3d(self):
        S["vso"]._spust_artisan = F.artisan_bez_obrazku(KARTA, s_v3d=False)
        r = get(KARTA)                      # klic v3d chybi: odhali to az build (strict ctx) -> 500, ne cteni Vandru (502); dulezite je hlasity duvod
        self.assertEqual(r.status_code, 500, r.get_data(as_text=True)[:200])
        self.assertIn("3D model nevznikl", r.get_json()["error"])
        self.assertIn("nevratil klic v3d", r.get_json()["error"])
        self.assertEqual(self.buildy, [], "Blender se nesmi spustit")

    def test_build_selze_hlasite(self):
        om = S["offer_model"]

        def spadne(*a, **k):
            raise om.V3DBuildError("Blender: chybí materiál X (unity_id Y)")
        om.spust_build = spadne
        r = get(KARTA)
        self.assertEqual(r.status_code, 500)
        self.assertIn("3D model nevznikl: ", r.get_json()["error"])
        self.assertIn("chybí materiál X", r.get_json()["error"])
        self.assertNotIn(b"glTF", r.get_data()[:4], "pri chybe nesmi prijit zadny (nahradni) model")

    def test_neocekavana_chyba_buildu_neni_tichy_model(self):
        om = S["offer_model"]
        om.spust_build = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("neocekavane"))
        r = get(KARTA)
        self.assertEqual(r.status_code, 500)
        self.assertIn("3D model nevznikl", r.get_json()["error"])

    def test_casovy_rozpocet_se_predava_buildu(self):
        om = S["offer_model"]
        videno = {}
        orig = om.build_offer_model

        def sleduj(*a, **k):
            videno.update(k)
            raise om.V3DBuildError("jen zjistuji rozpocet")
        om.build_offer_model = sleduj
        get(KARTA)
        self.assertIn("celkovy_limit_s", videno)
        self.assertLessEqual(videno["celkovy_limit_s"], S["vso"].CELKOVY_LIMIT_S - S["vso"].REZERVA_PO_BUILDU_S - S["vso"].REZERVA_STATICKY_MODEL_S + 0.01)
        self.assertGreater(videno["celkovy_limit_s"], 0)
        om.build_offer_model = orig


@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestUspech(Base):
    """Skutecny Blender build na karte 4910: GLB s pohyby, cache, sdileni cache s nabidkou, zadne zapisy."""

    @classmethod
    def setUpClass(cls):
        reset()
        vso, om = S["vso"], S["offer_model"]
        cls.cache = vso.V3D_CACHE_DIR
        cls.buildy = []
        orig = om.spust_build

        def pocitej(*a, **k):
            cls.buildy.append(time.time())
            return orig(*a, **k)
        om.spust_build = pocitej
        S["db"].shop_products[int(KARTA)] = dict(S["db"].shop_products[int(KARTA)], price_czk_placeholder=None)   # kontrola nepotrebuje cenu
        vso._oznac_model = lambda *a, **k: (_ for _ in ()).throw(AssertionError("kontrolni scena nesmi znacit model"))
        os.environ["V3D_MARK_SECRET"] = "test-klic-jen-v-procesu-testu-0123456789abcdef"
        try:
            t = time.time()
            cls.r1 = get(KARTA)
            cls.sekundy = time.time() - t
            cls.r2 = get(KARTA)
        finally:
            om.spust_build = orig
            os.environ.pop("V3D_MARK_SECRET", None)
        cls.dotazy = list(S["db"].dotazy)
        cls.offers = list(S["db"].offers)
        cls.audit = list(S["audit"])

    def setUp(self):
        vso = S["vso"]
        vso._spust_artisan = F.artisan_nova(KARTA)
        vso.V3D_CACHE_DIR = self.cache
        vso._oznac_model = S["puvodni"]["oznac"]                  # past-atrapa ze setUpClass plati jen pro volani trasy; nabidka znaci standardne
        S["appmod"].staff_ok = True

    @classmethod
    def tearDownClass(cls):
        S["db"].shop_products[int(KARTA)] = dict(S["db"].shop_products[int(KARTA)], price_czk_placeholder=123456)

    def test_prvni_volani_postavi_model(self):
        r = self.r1
        self.assertEqual(r.status_code, 200, repr(r.get_data()[:300]))
        self.assertEqual(r.mimetype, "model/gltf-binary")
        self.assertEqual(r.headers["Cache-Control"], "private, no-store")
        self.assertEqual(r.headers["X-V3D-Cache"], "miss")
        self.assertRegex(r.headers["X-V3D-Warnings"], r"^\d+$")
        self.assertEqual(r.get_data()[:4], b"glTF")
        self.assertGreater(len(r.get_data()), 50000)
        self.assertEqual(len(self.buildy), 1, "prave jeden Blender build")
        self.assertLess(self.sekundy, 55, "musi se vejit do limitu pozadavku")

    def test_druhe_volani_z_cache_bez_blenderu(self):
        self.assertEqual(self.r2.status_code, 200)
        self.assertEqual(self.r2.headers["X-V3D-Cache"], "hit")
        self.assertEqual(self.r2.get_data(), self.r1.get_data(), "z cache stejne bajty")
        self.assertEqual(len(self.buildy), 1, "druhe volani nesmi spustit Blender")

    def test_model_ma_pohyby_a_prosel_pojistkou(self):
        v3d_glb = S["v3d_glb"]
        raw = self.r1.get_data()
        spec = v3d_glb.embedded_spec(raw)
        self.assertIsInstance(spec, dict)
        self.assertGreater(len(spec.get("motions") or []), 0, "kontrola je kvuli pohybum komponent")
        S["vso"]._over_zakaznicky_glb(raw)                       # tatez brana jako pri zalozeni nabidky (sanitize + final_check + limit)
        gltf, _ = v3d_glb.read_glb(raw)
        v3d_glb.final_check(gltf)

    def test_nic_se_nezapisuje(self):
        self.assertTrue(self.dotazy, "trasa musi cist kartu")
        self.assertTrue(all(q.startswith("SELECT") for q, _ in self.dotazy), [q[:60] for q, _ in self.dotazy if not q.startswith("SELECT")])
        self.assertEqual(self.offers, [], "nevznikla zadna nabidka")
        self.assertEqual(self.audit, [], "zadny audit_log")
        self.assertEqual(S["db"].drive_files, [])

    def test_bez_ceny_karty_funguje(self):
        self.assertIsNone(S["db"].shop_products[int(KARTA)]["price_czk_placeholder"])
        self.assertEqual(self.r1.status_code, 200)

    def test_bez_forenzniho_znaceni_i_pri_nastavenem_klici(self):
        # _oznac_model by v setUpClass vyhodil AssertionError (-> 500); 200 znamena, ze se nezavolal
        self.assertEqual(self.r1.status_code, 200)
        self.assertEqual(self.r1.get_data(), S["offer_model"].build_offer_model(
            int(KARTA), S["db"].conn(), self.cache, vandr_fetch=lambda _u: S["vso"]._fetch_vandr_offer_data(
                S["db"].shop_products[int(KARTA)]["sku"][3:], v3d=True))[0], "stejne bajty jako cache buildu (bez znacky)")

    def test_cache_je_sdilena_s_nabidkou(self):
        """po otevreni karty v kontrolni scene vznikne nabidka z karty BEZ Blenderu (v3d_cache: true)."""
        om, vso = S["offer_model"], S["vso"]
        S["db"].shop_products[int(KARTA)] = dict(S["db"].shop_products[int(KARTA)], price_czk_placeholder=123456)
        buildy = []
        orig = om.spust_build
        om.spust_build = lambda *a, **k: buildy.append(a) or orig(*a, **k)
        vso._staticky_model = lambda glb_path, t_start: (_ for _ in ()).throw(AssertionError("nabidka ma pouzit cache, ne staticky model"))
        try:
            c = S["app"].test_client()
            r = c.post("/api/admin/vandr-vyroba/%s/nabidka" % KARTA)
        finally:
            om.spust_build = orig
            S["db"].shop_products[int(KARTA)] = dict(S["db"].shop_products[int(KARTA)], price_czk_placeholder=None)
            S["db"].offers.clear()
            S["db"].drive_files.clear()
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True)[:300])
        j = r.get_json()
        self.assertIs(j["v3d"], True)
        self.assertIs(j["v3d_cache"], True, "nabidka ma vzit model z cache po kontrolni scene")
        self.assertEqual(buildy, [], "zadny dalsi Blender build")


if __name__ == "__main__":
    unittest.main(verbosity=2)
