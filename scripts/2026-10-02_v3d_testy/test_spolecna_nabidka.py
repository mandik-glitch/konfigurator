#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermeticky test SPOLECNE online nabidky z vice karet Vandr (leva + prava + prepazka) a kontrolni sceny s vice kartami (bot10, 2026-10-06).

  POST /api/admin/vandr-vyroba/nabidka-spolecna   (api/vandr_scene_offers.py::vandr_vyroba_vytvorit_spolecnou_nabidku)
  GET  /api/kontrola-scena/v3d/<a>+<b>+<c>.glb     (kontrolni_scena_v3d_model s vice kartami)
  api/v3d_merge.py::sluc_glb                        (slouceni zakaznickych GLB)

Spusteni:  V3D_TEST_REPO=<kandidatni strom> /opt/konfigurator/api/venv/bin/python scripts/2026-10-02_v3d_testy/test_spolecna_nabidka.py     (~1 min, skutecny Blender)
Co je skutecne: Flask routing, SKUTECNY vandr_scene_offers.py + v3d_merge.py + scene_offers.py (create_scene_offer_row, save_offer_model_bytes), skutecny Blender build, v3d_glb, v3d_mark.
Co je atrapa: databaze (FakeDB), modul `app`, vystup `php artisan vandr:offer-data` (z fixtures/ctx; druha karta dostane "pravou" stranu a stejne jmeno vozu - kombinace levy 4910 + pravy 4918)."""
import copy
import base64
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import _cesty as CE  # noqa: E402
import _fakes as F  # noqa: E402

L, R, B = "4910", "4918", "4594"                  # leva, prava (relabeled), prepazka (relabeled)
JMENO = "Atrapa vozu spolecna"
TEST_KLIC = "test-klic-jen-v-procesu-testu-0123456789abcdef"
BLENDER_OK = os.path.exists(CE.BLENDER)
S = {}
URL_NAB = "/api/admin/vandr-vyroba/nabidka-spolecna"


def artisan_strany(mapa, car=JMENO):
    """Atrapa `_spust_artisan`: mapa karta -> strana (left|right|bulkhead); jmeno vozu stejne u vsech (kdyz `car` je str) nebo podle mapy (dict)."""
    def f(argumenty, timeout_s):
        f.volani.append(list(argumenty))
        k = next(k for k, sku in F.SKU.items() if sku[3:] == argumenty[0])
        o = F.vandr_output(k, "--v3d" in argumenty)
        o["car_name"] = car[k] if isinstance(car, dict) else car
        v = o.get("v3d")
        st = mapa[k]
        if v and st != "left":
            v["strany"][st] = v["strany"].pop("left")
        return F.Proc(0, json.dumps(o))
    f.volani = []
    return f


def reset():
    vso = S["vso"]
    vso._spust_artisan = artisan_strany({L: "left", R: "right", B: "bulkhead"})
    vso._postav_v3d_model = S["puvodni"]["postav"]
    vso._oznac_model = S["puvodni"]["oznac"]
    vso.V3D_VYPNUTO_SOUBOR = os.path.join(S["tmp"], "v3d-vypnuto-neexistuje")
    S["appmod"].staff_ok = True
    S["db"].offers.clear()
    S["db"].drive_files.clear()
    S["db"].dotazy.clear()
    S["audit"].clear()
    for k in (L, R, B):
        S["db"].shop_products[int(k)] = dict(S["radky"][k], price_czk_placeholder=int(k) * 10, sku=F.SKU[k])         # vzdy cisty radek (testy meni glb_file, sku, cenu)
    S["db"].umisteni.clear()
    S["db"].umisteni.update({L: "Regál levý", R: "Regál pravý", B: "Regál — kabina (za přepážkou)"})
    os.environ.pop("V3D_MARK_SECRET", None)
    vso._znacka_vypnuto_zalogovano = False


def setUpModule():
    S["tmp"] = tempfile.mkdtemp(prefix="spolecna_", dir=CE.OUT)
    S["db"] = F.FakeDB([L, R, B])
    S["app"], S["audit"], vso = F.install_stubs(S["db"], S["tmp"])
    S["vso"] = vso
    S["appmod"] = sys.modules["app"]
    import scene_offers
    import offer_model
    import build_ctx
    import v3d_glb
    import v3d_merge
    S.update(scene_offers=scene_offers, offer_model=offer_model, build_ctx=build_ctx, v3d_glb=v3d_glb, v3d_merge=v3d_merge)
    vso.KATALOG_DIR = CE.KATALOG
    build_ctx.KATALOG_DIR = CE.KATALOG
    gs = os.path.join(CE.REPO, "scripts", "2026-09-28_vandr_offer_geometry.py")
    vso.GEOMETRY_SCRIPT = gs if os.path.exists(gs) else "/opt/konfigurator/scripts/2026-09-28_vandr_offer_geometry.py"
    vso._read_vandr_image = lambda rel: F.PNG1
    vso.CONTENT_FILES_DIR = CE.CONTENT_FILES
    vso.V3D_CACHE_DIR = tempfile.mkdtemp(prefix="cache_", dir=S["tmp"])
    S["puvodni"] = {"postav": vso._postav_v3d_model, "oznac": vso._oznac_model}
    S["radky"] = {k: dict(S["db"].shop_products[int(k)]) for k in (L, R, B)}


def tearDownModule():
    os.environ.pop("V3D_MARK_SECRET", None)
    F.uninstall_stubs()
    shutil.rmtree(S.get("tmp", ""), ignore_errors=True)


def post(body, raw=None):
    c = S["app"].test_client()
    if raw is not None:
        return c.post(URL_NAB, data=raw, content_type="application/json")
    return c.post(URL_NAB, data=json.dumps(body), content_type="application/json")


def ctrl(ids):
    return S["app"].test_client().get("/api/kontrola-scena/v3d/%s.glb" % ids)


class Base(unittest.TestCase):
    def setUp(self):
        reset()

    def zadna_nabidka(self, r=None):
        self.assertEqual(S["db"].offers, [], "pri odmitnuti nesmi vzniknout nabidka")
        self.assertEqual(S["db"].drive_files, [])
        self.assertEqual([a for a in S["audit"] if a["action"] != "v3d_model"], [])


class TestVstup(Base):
    """Odmitnuti jeste PRED stavbou (rychle, bez Blenderu): 400 / 404 / 502, JSON {error}, zadna nabidka."""

    def over(self, r, stav, text):
        self.assertEqual(r.status_code, stav, r.get_data(as_text=True)[:300])
        j = r.get_json()
        self.assertEqual(list(j), ["error"])
        self.assertIn(text, j["error"])
        self.zadna_nabidka()
        self.assertEqual([x for x in S["db"].dotazy if not x[0].startswith("SELECT")], [], "pri odmitnuti zadny zapis")

    def test_telo(self):
        for nazev, body, raw in (("bez tela", None, ""), ("neJSON", None, "{nejson"), ("karty chybi", {}, None), ("karty neni seznam", {"karty": "4910"}, None), ("jedna karta", {"karty": [4910]}, None),
                                 ("ctyri karty", {"karty": [1, 2, 3, 4]}, None), ("text misto cisla", {"karty": [4910, "4918"]}, None), ("bool", {"karty": [4910, True]}, None),
                                 ("zaporne", {"karty": [4910, -4918]}, None), ("nula", {"karty": [4910, 0]}, None), ("float", {"karty": [4910, 4918.0]}, None), ("pole misto objektu", [4910, 4918], None)):
            with self.subTest(case=nazev):
                r = post(body, raw=raw) if raw is not None else post(body)
                self.assertEqual(r.status_code, 400, (nazev, r.get_data(as_text=True)[:200]))
                self.assertIn("karty", r.get_json()["error"])
                self.zadna_nabidka()

    def test_duplicita(self):
        self.over(post({"karty": [int(L), int(L)]}), 400, "víckrát")

    def test_karta_neexistuje_a_neni_vandr(self):
        self.over(post({"karty": [int(L), 999999]}), 404, "Karta 999999: Karta neexistuje.")
        S["db"].shop_products[int(R)]["sku"] = "DIL-123"
        self.over(post({"karty": [int(L), int(R)]}), 400, "Karta %s: SKU karty neodpovídá" % R)

    def test_bez_glb_bez_souboru_bez_ceny(self):
        S["db"].shop_products[int(R)]["glb_file"] = None
        self.over(post({"karty": [int(L), int(R)]}), 400, "Karta %s: Karta ještě nemá hotový 3D model" % R)
        S["db"].shop_products[int(R)]["glb_file"] = "vandr/neexistuje.glb"
        self.over(post({"karty": [int(L), int(R)]}), 400, "GLB soubor chybí na disku")
        reset()
        S["db"].shop_products[int(R)]["price_czk_placeholder"] = None
        self.over(post({"karty": [int(L), int(R)]}), 400, "Karta %s: Karta ještě nemá cenu." % R)

    def test_ruzna_vozidla(self):
        S["vso"]._spust_artisan = artisan_strany({L: "left", R: "right"}, car={L: "Renault Master", R: "Ford Transit"})
        self.over(post({"karty": [int(L), int(R)]}), 400, "různá vozidla")

    def test_stejna_strana_dvakrat(self):
        S["vso"]._spust_artisan = artisan_strany({L: "left", R: "left"})
        self.over(post({"karty": [int(L), int(R)]}), 400, "Karty %s a %s jsou obě levá strana" % (L, R))

    def test_karta_nema_jednu_stranu(self):
        base = artisan_strany({L: "left", R: "right"})

        def dve_strany(argumenty, timeout_s):
            p = base(argumenty, timeout_s)
            o = json.loads(p.stdout)
            if o.get("v3d") and F.SKU[R][3:] == argumenty[0]:
                o["v3d"]["strany"]["left"] = copy.deepcopy(o["v3d"]["strany"]["right"])         # kombinace: obe strany v jednom modelu
            return F.Proc(0, json.dumps(o))
        S["vso"]._spust_artisan = dve_strany
        self.over(post({"karty": [int(L), int(R)]}), 400, "Karta %s nemá jednu určitou stranu" % R)

    def test_stara_verze_vandr_prikazu(self):
        S["vso"]._spust_artisan = F.artisan_stara(L)
        self.over(post({"karty": [int(L), int(R)]}), 502, "3D model nevznikl: Vandr příkaz bez --v3d")

    def test_vypnuto_souborem(self):
        soubor = os.path.join(S["tmp"], "v3d-vypnuto")
        open(soubor, "w").close()
        S["vso"].V3D_VYPNUTO_SOUBOR = soubor
        self.over(post({"karty": [int(L), int(R)]}), 503, "se bez 3D nezakládá")

    def test_bez_opravneni_a_jen_post(self):
        c = S["app"].test_client()
        self.assertEqual(c.get(URL_NAB).status_code, 405)
        pravidla = {r.rule: sorted(r.methods - {"HEAD", "OPTIONS"}) for r in S["app"].url_map.iter_rules() if "nabidka-spolecna" in r.rule}
        self.assertEqual(pravidla, {URL_NAB: ["POST"]})


class TestControlniSceneVstup(Base):
    def over(self, ids, stav, text):
        r = ctrl(ids)
        self.assertEqual(r.status_code, stav, r.get_data(as_text=True)[:200])
        self.assertIn(text, r.get_json()["error"])

    def test_chyby_s_predponou_karty(self):
        self.over("4910+999999", 404, "Karta 999999: Karta neexistuje.")
        self.over("4910+4910", 400, "víckrát")
        S["vso"]._spust_artisan = artisan_strany({L: "left", R: "left"})
        self.over("%s+%s" % (L, R), 400, "obě levá strana")
        S["vso"]._spust_artisan = artisan_strany({L: "left", R: "right"}, car={L: "A", R: "B"})
        self.over("%s+%s" % (L, R), 400, "různá vozidla")

    def test_neplatny_tvar_je_404_a_max_tri(self):
        c = S["app"].test_client()
        for ids in ("1+2+3+4", "+4910", "4910+", "4910++4918", "a+b", "4910%2B4918x", "4910 4918", "-1+2", "1+-2", "12345678901"):
            self.assertEqual(c.get("/api/kontrola-scena/v3d/%s.glb" % ids).status_code, 404, ids)

    def test_staff(self):
        S["appmod"].staff_ok = False
        self.assertEqual(ctrl("%s+%s" % (L, R)).status_code, 401)


@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestUspech(Base):
    """Skutecny Blender: leva 4910 + prava 4918 -> jedna nabidka, jedna scena."""

    @classmethod
    def setUpClass(cls):
        reset()
        vso = S["vso"]
        cls.vstupy = {}
        for k in (L, R):
            d, duvod = vso._nacti_vandr_data(F.SKU[k][3:])
            cls.vstupy[k] = (d, duvod)
        # ocekavane pocty z jednotlivych modelu (stejna cache jako spolecne stavby)
        cls.single = {}
        for k in (L, R):
            glb, geom = vso._postav_v3d_model(int(k), cls.vstupy[k][0], __import__("time").time())
            cls.single[k] = (glb, geom, S["v3d_glb"].embedded_spec(glb))
        cls.r = post({"karty": [int(R), int(L)]})                     # zamerne v obracenem poradi: server serazuje leva, prava, prepazka
        cls.j = cls.r.get_json()
        cls.offer = S["db"].offers[-1] if S["db"].offers else None
        cls.audit = list(S["audit"])
        o = cls.offer
        cls.model = None
        if o and o.get("view_3d_model"):
            with open(os.path.join(S["scene_offers"].OFFER_MODELS_DIR, o["view_3d_model"]), "rb") as fh:
                cls.model = fh.read()

    def setUp(self):
        S["vso"]._spust_artisan = artisan_strany({L: "left", R: "right", B: "bulkhead"})

    def test_odpoved(self):
        j = self.j
        self.assertEqual(self.r.status_code, 201, j)
        self.assertEqual(j["status"], "ok")
        self.assertEqual(j["karty"], [int(L), int(R)], "kanonicke poradi: leva, prava")
        self.assertEqual(j["strany"], ["left", "right"])
        self.assertEqual(j["cena_celkem"], int(L) * 10 + int(R) * 10)
        self.assertIs(j["v3d"], True)
        self.assertIsNone(j["v3d_duvod"])
        self.assertTrue(j["online_url"].startswith("/nabidka-online.html?t="))
        self.assertEqual(j["vandr_car_name"], JMENO)
        self.assertEqual(len(j["rozmer_mm"]), 3)
        self.assertEqual(j["obrazky_zdroj"][0], {"narys": "vandr", "view3d": "vandr"})
        self.assertEqual(len(j["obrazky_zdroj"]), 2)

    def test_radky_a_cena(self):
        o = self.offer
        items = json.loads(o["items"])
        self.assertEqual(len(items), 2)
        self.assertEqual([i["total"] for i in items], [int(L) * 10, int(R) * 10])
        self.assertEqual(float(o["total_price"]), int(L) * 10 + int(R) * 10)
        self.assertIn("Regál levý", items[0]["name"])
        self.assertIn("Regál pravý", items[1]["name"])
        self.assertIn(F.SKU[L], items[0]["name"])
        self.assertIn(F.SKU[R], items[1]["name"])
        self.assertTrue(all(i["qty"] == 1 and i["unit_price"] == i["total"] for i in items))

    def test_nastaveni_nabidky_a_obrazky(self):
        opt = json.loads(self.offer["offer_options"])
        self.assertIs(opt["vandr_single_drawing"], True)
        self.assertNotIn("vandr_cards", opt, "ID karet nejsou ve verejnych volbach nabidky (jsou v audit_logu)")
        self.assertEqual(opt["vandr_drawings"], [{"slot": "narys", "label": "Levá strana"}, {"slot": "bokorys", "label": "Pravá strana"}])
        self.assertEqual(opt["hidden_payment_method"], "dobirka")
        o = self.offer
        self.assertTrue(o["view_narys"] and o["view_bokorys"], "vykres leve i prave strany")
        self.assertFalse(o["view_pudorys"], "prepazka v teto nabidce neni")
        self.assertTrue(o["view_3d_a"] and o["view_3d_b"])

    def test_model_je_sloucena_scena_s_pohyby(self):
        v3d_glb = S["v3d_glb"]
        self.assertIsNotNone(self.model, "model nabidky se musi ulozit")
        sp = v3d_glb.embedded_spec(self.model)
        sl, sr = self.single[L][2], self.single[R][2]
        self.assertEqual(len(sp["motions"]), len(sl["motions"]) + len(sr["motions"]), "vsechny pohyby obou stran")
        self.assertEqual(sp["dims"], sl["dims"] + sr["dims"], "kóty: každá strana si drží své vlastní (ne jedna obálka celé sestavy), bez změny souřadnic")
        self.assertEqual(len(sp["dims"]), 6, "levá 3 + pravá 3 kóty")
        self.assertEqual(sp["front"], sl["front"], "front z leve (prvni) strany")
        for a in range(3):
            self.assertAlmostEqual(sp["box"]["min"][a], min(sl["box"]["min"][a], sr["box"]["min"][a]), places=1)
            self.assertAlmostEqual(sp["box"]["max"][a], max(sl["box"]["max"][a], sr["box"]["max"][a]), places=1)
        ids = [m["id"] for m in sp["motions"]]
        self.assertEqual(len(ids), len(set(ids)), "id pohybu jsou jedinecna")
        piv = [p for m in sp["motions"] for s in m["steps"] for p in [s["p"]]]
        g, _b = v3d_glb.read_glb(self.model)
        nazvy = [n.get("name") for n in g["nodes"] if str(n.get("name", "")).startswith("p")]
        self.assertEqual(len(nazvy), len(set(nazvy)), "pivoty jsou jedinecne")
        self.assertTrue(set(piv) <= set(nazvy), "kazdy pivot pohybu v modelu existuje")
        v3d_glb.final_check(g)
        stav = {}
        for m in sp["motions"]:
            stav[(m.get("g"), m["k"], m.get("sub"))] = stav.get((m.get("g"), m["k"], m.get("sub")), []) + [m["n"]]          # cislovani je v ramci strany (g) a druhu
        for fam, ns in stav.items():
            self.assertEqual(sorted(ns), list(range(1, len(ns) + 1)), "n pohybu %s (strana, druh, sub) je souvisla rada 1..N" % (fam,))

    def test_audit_a_nic_navic(self):
        a = [x for x in self.audit if x["action"] == "v3d_model"]
        self.assertEqual(len(a), 1)
        d = a[0]["detail"] if isinstance(a[0]["detail"], dict) else json.loads(a[0]["detail"])
        self.assertIs(d["v3d"], True)
        self.assertEqual(d["karty"], [int(L), int(R)])
        self.assertEqual(d["strany"], ["left", "right"])
        self.assertEqual(len([o for o in S["db"].offers if o["offer_number"] == self.offer["offer_number"]]), 1)

    def test_kontrolni_scena_slouceny_model_stejny_jako_v_nabidce(self):
        r = ctrl("%s+%s" % (R, L))                                  # poradi v adrese je jedno
        self.assertEqual(r.status_code, 200, repr(r.get_data()[:200]))
        self.assertEqual(r.mimetype, "model/gltf-binary")
        self.assertEqual(r.headers["X-V3D-Karty"], "%s+%s" % (L, R))
        self.assertEqual(r.headers["X-V3D-Cache"], "hit", "oba modely uz jsou v cache po stavbe nabidky")
        self.assertEqual(r.headers["Cache-Control"], "private, no-store")
        sp = S["v3d_glb"].embedded_spec(r.get_data())
        self.assertEqual(len(sp["motions"]), len(self.single[L][2]["motions"]) + len(self.single[R][2]["motions"]))
        self.assertEqual(S["db"].offers[-1]["offer_number"], self.offer["offer_number"], "kontrolni scena nezaklada nabidku")

    def test_jedna_karta_v_kontrolni_scene_je_beze_zmeny(self):
        r = ctrl(L)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["X-V3D-Karty"], L)
        self.assertEqual(len(S["v3d_glb"].embedded_spec(r.get_data())["motions"]), len(self.single[L][2]["motions"]))


@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestSelhani(Base):
    def test_jedna_karta_se_nepostavi_nic_nevznikne(self):
        puvodni = S["vso"]._postav_v3d_model

        def selze(shop_product_id, vandr_data, t_start):
            if shop_product_id == int(R):
                raise S["vso"]._V3DNevzniklo("Blender: chybí materiál X")
            return puvodni(shop_product_id, vandr_data, t_start)
        S["vso"]._postav_v3d_model = selze
        r = post({"karty": [int(L), int(R)]})
        self.assertEqual(r.status_code, 500)
        self.assertEqual(list(r.get_json()), ["error"])
        self.assertIn("(karta %s)" % R, r.get_json()["error"])
        self.assertIn("chybí materiál X", r.get_json()["error"])
        self.assertEqual(S["db"].offers, [], "bez 3D se spolecna nabidka nezaklada")
        self.assertEqual([a for a in S["audit"]], [])
        r2 = ctrl("%s+%s" % (L, R))
        self.assertEqual(r2.status_code, 500)
        self.assertNotEqual(r2.get_data()[:4], b"glTF", "pri chybe zadny (nahradni) model")

    def test_slouceni_selze_hlasite(self):
        vm = S["v3d_merge"]
        puvodni = vm.sluc_glb

        def spadne(glbs, geoms=None):
            raise S["v3d_glb"].V3DError("look se lisi")
        vm.sluc_glb = spadne
        try:
            r = post({"karty": [int(L), int(R)]})
        finally:
            vm.sluc_glb = puvodni
        self.assertEqual(r.status_code, 500)
        self.assertIn("sloučení modelů stran selhalo: look se lisi", r.get_json()["error"])
        self.assertEqual(S["db"].offers, [])


@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestVykresyJenPrevzit(Base):
    """Robert 2026-10-06 (pres bot9): Vandr 2D vykresy se jen PREBIRAJI, nikdy nevyrabi. Strana bez Vandr vykresu se z vykresu spolecne nabidky VYNECHA (sloty se prideluji jen
    stranam s vykresem), kdyz nema zadna, nabidka je bez stranky Vykresy (offer_options.vandr_bez_vykresu + zastupny 1x1 PNG v NOT NULL sloupci view_narys)."""

    @staticmethod
    def bez_vykresu(mapa, karty_bez):
        zaklad = artisan_strany(mapa)

        def f(argumenty, timeout_s):
            pr = zaklad(argumenty, timeout_s)
            k = next(k for k, sku in F.SKU.items() if sku[3:] == argumenty[0])
            if k in karty_bez:
                o = json.loads(pr.stdout)
                o["parts"]["left_part"]["image_2d_with_dim"] = ""
                return F.Proc(0, json.dumps(o))
            return pr
        f.volani = zaklad.volani
        return f

    def obrazek(self, sloupec):
        cesta = S["db"].offers[-1][sloupec]
        if not cesta:
            return None
        with open(os.path.join(S["scene_offers"].OFFER_IMAGES_DIR, cesta), "rb") as fh:
            return fh.read()

    def test_leva_bez_vykresu_zustane_jen_prava(self):
        vk = S["vso"]._vykres_modul()
        puvodni = vk.vykres_nares
        volano = []
        vk.vykres_nares = lambda *a, **k: volano.append(1) or puvodni(*a, **k)
        S["vso"]._spust_artisan = self.bez_vykresu({L: "left", R: "right"}, {L})
        try:
            r = post({"karty": [int(L), int(R)]})
        finally:
            vk.vykres_nares = puvodni
        j = r.get_json()
        self.assertEqual(r.status_code, 201, j)
        self.assertEqual(volano, [], "2D vykres se nesmi vyrabet")
        self.assertEqual([z["narys"] for z in j["obrazky_zdroj"]], ["chybi", "vandr"])
        opt = json.loads(S["db"].offers[-1]["offer_options"])
        self.assertEqual(opt["vandr_drawings"], [{"slot": "narys", "label": "Pravá strana"}])
        self.assertNotIn("vandr_bez_vykresu", opt)
        self.assertEqual(self.obrazek("view_narys"), F.PNG1, "vykres PRAVE strany (atrapa Vandr PNG) je v prvnim slotu")
        self.assertIsNone(self.obrazek("view_bokorys"))
        self.assertTrue(S["db"].offers[-1]["view_3d_a"] and S["db"].offers[-1]["view_3d_b"], "3D pohledy zustavaji")
        self.assertIn("Levá strana: Vandr u karty nemá kótovaný 2D výkres", j["poznamka"])

    def test_prava_bez_vykresu_zustane_jen_leva(self):
        S["vso"]._spust_artisan = self.bez_vykresu({L: "left", R: "right"}, {R})
        r = post({"karty": [int(L), int(R)]})
        self.assertEqual(r.status_code, 201, r.get_json())
        opt = json.loads(S["db"].offers[-1]["offer_options"])
        self.assertEqual(opt["vandr_drawings"], [{"slot": "narys", "label": "Levá strana"}])
        self.assertEqual([z["narys"] for z in r.get_json()["obrazky_zdroj"]], ["vandr", "chybi"])

    def test_zadna_strana_nema_vykres_nabidka_bez_vykresu(self):
        S["vso"]._spust_artisan = self.bez_vykresu({L: "left", R: "right"}, {L, R})
        r = post({"karty": [int(L), int(R)]})
        j = r.get_json()
        self.assertEqual(r.status_code, 201, j)
        opt = json.loads(S["db"].offers[-1]["offer_options"])
        self.assertIs(opt.get("vandr_bez_vykresu"), True)
        self.assertIs(opt.get("vandr_single_drawing"), True)
        self.assertNotIn("vandr_drawings", opt)
        self.assertEqual(self.obrazek("view_narys"), base64.b64decode(S["vso"]._PRAZDNY_PNG.split(",", 1)[1]), "NOT NULL sloupec: zastupny 1x1 PNG, ne Vandr vykres")
        self.assertNotEqual(self.obrazek("view_narys"), F.PNG1)
        self.assertEqual([z["narys"] for z in j["obrazky_zdroj"]], ["chybi", "chybi"])
        self.assertIs(j["v3d"], True, "3D model vznika dal")

    def test_obe_maji_vykres_beze_zmeny(self):
        r = post({"karty": [int(L), int(R)]})
        self.assertEqual(r.status_code, 201, r.get_json())
        opt = json.loads(S["db"].offers[-1]["offer_options"])
        self.assertEqual(opt["vandr_drawings"], [{"slot": "narys", "label": "Levá strana"}, {"slot": "bokorys", "label": "Pravá strana"}])
        self.assertNotIn("vandr_bez_vykresu", opt)


@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestZnacka(Base):
    def test_zapnute_znaceni_oznaci_slouceny_model_cislem_nabidky(self):
        os.environ["V3D_MARK_SECRET"] = TEST_KLIC
        r = post({"karty": [int(L), int(R)]})
        self.assertEqual(r.status_code, 201, repr(r.get_data()[:300]))
        j = r.get_json()
        self.assertEqual(j["v3d_znacka"], "zapnuto")
        o = S["db"].offers[-1]
        with open(os.path.join(S["scene_offers"].OFFER_MODELS_DIR, o["view_3d_model"]), "rb") as fh:
            m = fh.read()
        S["v3d_glb"].final_check(S["v3d_glb"].read_glb(m)[0])
        import v3d_mark
        oid, jistota = v3d_mark.detect(m, TEST_KLIC.encode())
        self.assertEqual(oid, j["offer_id"], "znacka nese cislo nabidky (stejne jako u nabidky z jedne karty)")
        self.assertIsNone(v3d_mark.detect(m, b"jiny-klic-0123456789abcdefghij")[0] if v3d_mark.detect(m, b"jiny-klic-0123456789abcdefghij")[0] != oid else None)


class TestSlucovaniJednotka(unittest.TestCase):
    """v3d_merge.sluc_glb bez Flasku a DB: nad hotovymi zakaznickymi GLB (v3d_nahled/*.glb), nezavisle kontroly vystupu."""

    @classmethod
    def setUpClass(cls):
        if "v3d_merge" not in S:
            for p in (os.path.join(CE.REPO, "api"),):
                if p not in sys.path:
                    sys.path.insert(0, p)
        import v3d_glb
        import v3d_merge
        cls.g, cls.m = v3d_glb, v3d_merge
        d = os.path.join(CE.KATALOG, "vandr", "v3d_nahled")
        cls.glbs = {k: open(os.path.join(d, k + ".glb"), "rb").read() for k in ("4918", "4921", "4594")}

    def test_dva_a_tri_modely(self):
        for ks in (("4918", "4921"), ("4918", "4921", "4594")):
            with self.subTest(karty=ks):
                out, gm = self.m.sluc_glb([self.glbs[k] for k in ks])
                sp = self.g.embedded_spec(out)
                zdroje = [self.g.embedded_spec(self.glbs[k]) for k in ks]
                self.assertEqual(len(sp["motions"]), sum(len(z["motions"]) for z in zdroje))
                self.assertEqual(sp["dims"], [d for z in zdroje for d in z["dims"]], "kóty všech zdrojů za sebou, každá strana zvlášť")
                self.assertEqual(sp["front"], zdroje[0]["front"])
                self.assertEqual([m["id"] for m in sp["motions"]], ["m%d" % i for i in range(1, len(sp["motions"]) + 1)])
                g, _b = self.g.read_glb(out)
                self.g.final_check(g)
                self.assertEqual(len(g["meshes"]), sum(len(self.g.read_glb(self.glbs[k])[0]["meshes"]) for k in ks))
                self.assertEqual(gm["overall_size"], [round(sp["box"]["max"][a] - sp["box"]["min"][a], 1) for a in range(3)])

    def test_nevalidni_vstupy(self):
        V3DError = self.g.V3DError
        with self.assertRaises(V3DError):
            self.m.sluc_glb([self.glbs["4918"]])                                   # jeden model
        with self.assertRaises(V3DError):
            self.m.sluc_glb([self.glbs["4918"]] * 4)                               # ctyri
        with self.assertRaises(V3DError):
            self.m.sluc_glb([self.glbs["4918"], b"neni glb"])
        with self.assertRaises(V3DError):
            self.m.sluc_glb([self.glbs["4918"], open(os.path.join(CE.FIX, "native_offer.glb"), "rb").read()])      # nativni model bez v3d

    def test_strany_g_a_cislovani_po_stranach(self):
        klice = ("4918", "4921", "4594")
        out, _gm = self.m.sluc_glb([self.glbs[k] for k in klice], strany=["left", "right", "bulkhead"])
        sp = self.g.embedded_spec(out)
        zdroje = [self.g.embedded_spec(self.glbs[k]) for k in klice]
        n1, n2, n3 = (len(z["motions"]) for z in zdroje)
        self.assertEqual([m["g"] for m in sp["motions"]], ["left"] * n1 + ["right"] * n2 + ["bulkhead"] * n3, "kazdy pohyb nese stranu sveho zdroje")
        porad = {}
        for m in sp["motions"]:
            porad.setdefault((m["g"], m["k"], m.get("sub")), []).append(m["n"])
        for fam, ns in porad.items():
            self.assertEqual(sorted(ns), list(range(1, len(ns) + 1)), "cislovani v ramci strany a druhu zacina od 1: %s" % (fam,))
        self.assertEqual([m["n"] for m in sp["motions"][:n1]], [m["n"] for m in zdroje[0]["motions"]], "leva strana: n beze zmeny")
        self.assertEqual([m["n"] for m in sp["motions"][n1:n1 + n2]], [m["n"] for m in zdroje[1]["motions"]], "prava strana: n beze zmeny (zacina znovu od 1)")
        self.assertEqual([m["id"] for m in sp["motions"]], ["m%d" % i for i in range(1, n1 + n2 + n3 + 1)], "id zustavaji jedinecna")

    def test_strany_nevalidni_a_odhad(self):
        V3DError, A, B = self.g.V3DError, self.glbs["4918"], self.glbs["4921"]
        for spatne in (["left"], ["left", "nahoru"], "left", ["left", 5], ["left", "right", "bulkhead"]):
            with self.assertRaises(V3DError, msg=repr(spatne)):
                self.m.sluc_glb([A, B], strany=spatne)
        out, _gm = self.m.sluc_glb([A, B], strany=[None, "right"])
        sp = self.g.embedded_spec(out)
        self.assertNotIn("g", sp["motions"][0], "strana None = pohyb bez g")
        self.assertEqual(sp["motions"][-1]["g"], "right")
        od = self.m._odhad_strany
        box = lambda a, b: {"min": [a, 0, 0], "max": [b, 1, 1]}
        self.assertEqual(od({"front": [-1, 0, 0], "box": box(10, 830)}), "left")
        self.assertEqual(od({"front": [1, 0, 0], "box": box(-830, -10)}), "right")
        self.assertIsNone(od({"front": [0, 0, 1], "box": box(10, 830)}), "front podel z (prepazka) se nehada")
        self.assertIsNone(od({"front": [-1, 0, 0], "box": box(-400, 400)}), "box na ose vozu se nehada")
        self.assertIsNone(od({}) and None)
        self.assertIsNone(od({"front": "x", "box": 5}), "rozbity spec se nehada, nevyhodi")

    def test_pivoty_a_pohyby_druheho_modelu_jsou_precislovane(self):
        out, _gm = self.m.sluc_glb([self.glbs["4918"], self.glbs["4921"]])
        sp = self.g.embedded_spec(out)
        n1 = len(self.g.embedded_spec(self.glbs["4918"])["motions"])
        druhe = sp["motions"][n1:]
        prvni_piv = {s["p"] for m in sp["motions"][:n1] for s in m["steps"]}
        druhe_piv = {s["p"] for m in druhe for s in m["steps"]}
        self.assertFalse(prvni_piv & druhe_piv, "pivoty druheho modelu se neprekryvaji s prvnim")


if __name__ == "__main__":
    unittest.main(verbosity=2)
