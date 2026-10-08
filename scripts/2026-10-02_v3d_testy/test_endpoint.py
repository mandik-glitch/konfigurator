#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermeticky test endpointu POST /api/admin/vandr-vyroba/<id>/nabidka (api/vandr_scene_offers.py) + modelu nabidky
(GET /api/public/offers/<token>/model v api/scene_offers.py), 2026-10-02.

Spusteni:  /opt/konfigurator/api/venv/bin/python scripts/2026-10-02_v3d_testy/test_endpoint.py     (~1,5 min)
Pozadavky: Blender /opt/blender-5.2/blender (jen -b, CPU), katalogove GLB karet ve webapp/katalog (jen CTENI).

CO JE SKUTECNE: Flask routing, SKUTECNY api/scene_offers.py (create_scene_offer_row, save_offer_model_bytes, model route)
a api/vandr_scene_offers.py, skutecny Blender build na jedne z 7 karet, skutecny v3d_glb a v3d_mark, skutecna cache a zamek.
CO JE ATRAPA: databaze (FakeDB v pameti - zapis do cizi tabulky = chyba testu), Flask modul `app`, vystup
`php artisan vandr:offer-data` (z fixtures/ctx), obrazky z Vandru (1x1 PNG). Nic se neodesila ven (zadny SMTP, zadna sit),
nic se nepise do repa ani do produkcni DB; soubory (obrazky, modely, cache) jdou do <OUT>/endpoint_*.
Klic znaceni se nastavuje JEN v os.environ procesu testu (testovaci hodnota), ne do zadneho souboru.
"""
import copy
import json
import logging
import math
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import _cesty as CE  # noqa: E402
import _fakes as F  # noqa: E402

KARTA = "4910"                       # Ford Transit L3H3 FWD (nejmensi z 7 karet po 4594; vice pohybu nez 4594)
TEST_KLIC = "test-klic-jen-v-procesu-testu-0123456789abcdef"      # NEPOUZIVAT jinde; neni v zadnem souboru krome tohoto testu
PROD_ENV_VARS = ("V3D_MARK_SECRET",)
BLENDER_OK = os.path.exists(CE.BLENDER)
LEGACY = None                        # bajty "dosavadniho statickeho modelu" (atrapa vystupu Blender geometrie)

S = {}                               # sdileny stav modulu (tmp, db, flask_app, vso, offer_model, v3d_glb, v3d_mark)


def _post(k, client=None):
    c = client or S["app"].test_client()
    r = c.post("/api/admin/vandr-vyroba/%s/nabidka" % k)
    return r.status_code, r.get_json()


def _stored_model(offer_id):
    o = next(x for x in S["db"].offers if x["id"] == offer_id)
    assert o["view_3d_model"], "nabidka %s nema ulozeny model" % offer_id
    with open(os.path.join(S["scene_offers"].OFFER_MODELS_DIR, o["view_3d_model"]), "rb") as fh:
        return fh.read()


def _token(online_url):
    return online_url.split("t=", 1)[1]


def _nova_cache():
    d = tempfile.mkdtemp(prefix="cache_", dir=S["tmp"])
    S["vso"].V3D_CACHE_DIR = d
    return d


def _legacy_geom():
    return {"overall_size": [100.0, 200.0, 300.0], "profily": [{}, {}, {}]}


def setUpModule():
    global LEGACY
    S["tmp"] = tempfile.mkdtemp(prefix="endpoint_", dir=CE.OUT)
    S["db"] = F.FakeDB([KARTA, "4594"])
    S["app"], S["audit"], vso = F.install_stubs(S["db"], S["tmp"])
    S["vso"] = vso
    import scene_offers
    import offer_model
    import build_ctx
    import v3d_glb
    S.update(scene_offers=scene_offers, offer_model=offer_model, build_ctx=build_ctx, v3d_glb=v3d_glb)
    # cesty na serveru shodne, v testu ukazuji na katalog (jen cteni) a na tmp
    vso.KATALOG_DIR = CE.KATALOG
    build_ctx.KATALOG_DIR = CE.KATALOG
    gs = os.path.join(CE.REPO, "scripts", "2026-09-28_vandr_offer_geometry.py")
    vso.GEOMETRY_SCRIPT = gs if os.path.exists(gs) else "/opt/konfigurator/scripts/2026-09-28_vandr_offer_geometry.py"
    vso._read_vandr_image = lambda rel: F.PNG1
    vso.CONTENT_FILES_DIR = CE.CONTENT_FILES
    with open(os.path.join(CE.FIX, "native_offer.glb"), "rb") as fh:
        LEGACY = fh.read()
    S["puvodni"] = {"spust_build": offer_model.spust_build, "staticky": vso._staticky_model, "artisan": vso._spust_artisan,
                    "offer_model": vso._offer_model}
    S["env_puvodni"] = {k: os.environ.get(k) for k in PROD_ENV_VARS}


def tearDownModule():
    for k, v in S.get("env_puvodni", {}).items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    F.uninstall_stubs()
    shutil.rmtree(S.get("tmp", ""), ignore_errors=True)


def reset():
    """cisty stav: puvodni funkce modulu, nova atrapa artisan, zadne nabidky, bez klice znaceni"""
    vso, om = S["vso"], S["offer_model"]
    vso._spust_artisan = F.artisan_nova(KARTA)
    vso._staticky_model = S["puvodni"]["staticky"]
    vso._offer_model = S["puvodni"]["offer_model"]
    om.spust_build = S["puvodni"]["spust_build"]
    os.environ.pop("V3D_MARK_SECRET", None)
    vso._znacka_vypnuto_zalogovano = False
    S["db"].offers.clear()
    S["db"].drive_files.clear()
    S["audit"].clear()


class Base(unittest.TestCase):
    """Kazdy test dostane cisty stav: nove nabidky v DB, vychozi atrapy, bez klice znaceni."""

    def setUp(self):
        reset()

    def staticky_atrapa(self):
        """dosavadni cesta (Blender geometrie) nahrazena atrapou - rychle testy selhani"""
        vyst = []

        def f(glb_path, t_start):
            vyst.append(glb_path)
            return LEGACY, _legacy_geom()
        S["vso"]._staticky_model = f
        return vyst


# ---------------------------------------------------------------------------
# can_create_offer + zachovani chovani 400/404
# ---------------------------------------------------------------------------

class TestCanCreateOffer(Base):
    def row(self, **z):
        r = dict(S["db"].shop_products[int(KARTA)])
        r.update(z)
        return r

    def test_ok(self):
        self.assertEqual(S["vso"].can_create_offer(self.row()), (True, None))

    def test_texty_a_poradi(self):
        can = S["vso"].can_create_offer
        T_GLB = "Karta ještě nemá hotový 3D model (konverze nedoběhla)."
        T_CENA = "Karta ještě nemá cenu."
        T_SKU = "SKU karty neodpovídá formátu VD-<uuid> - není to Vandr karta."
        self.assertEqual(can(None), (False, "Karta neexistuje."))
        self.assertEqual(can(self.row(glb_file=None)), (False, T_GLB))
        self.assertEqual(can(self.row(glb_file="")), (False, T_GLB))
        self.assertEqual(can(self.row(price_czk_placeholder=None)), (False, T_CENA))
        self.assertEqual(can(self.row(price_czk_placeholder=0))[0], True)          # 0 neni NULL (jako dosud)
        self.assertEqual(can(self.row(sku="DIL-123")), (False, T_SKU))
        self.assertEqual(can(self.row(sku=None)), (False, T_SKU))
        self.assertEqual(can(self.row(sku="vd-malym")), (False, T_SKU))            # presne prefix "VD-"
        self.assertEqual(can(self.row(glb_file="vandr/neexistuje.glb")), (False, "GLB soubor chybí na disku: vandr/neexistuje.glb"))
        # poradi kontrol jako v puvodnim endpointu: glb_file, cena, sku, soubor
        self.assertEqual(can(self.row(glb_file=None, price_czk_placeholder=None, sku="x")), (False, T_GLB))
        self.assertEqual(can(self.row(price_czk_placeholder=None, sku="x")), (False, T_CENA))
        self.assertEqual(can(self.row(sku="x", glb_file="vandr/neexistuje.glb")), (False, T_SKU))

    def test_katalog_dir_parametr(self):
        d = tempfile.mkdtemp(dir=S["tmp"])
        self.assertFalse(S["vso"].can_create_offer(self.row(), katalog_dir=d)[0])
        os.makedirs(os.path.join(d, "vandr"))
        open(os.path.join(d, self.row()["glb_file"]), "wb").close()
        self.assertEqual(S["vso"].can_create_offer(self.row(), katalog_dir=d), (True, None))

    def test_endpoint_stejne_statusy_a_texty(self):
        db = S["db"]
        stat, j = _post("999999")
        self.assertEqual((stat, j), (404, {"error": "Karta neexistuje."}))
        puvodni = dict(db.shop_products[int(KARTA)])
        try:
            for zmena, text in ((dict(glb_file=None), "Karta ještě nemá hotový 3D model (konverze nedoběhla)."),
                                (dict(price_czk_placeholder=None), "Karta ještě nemá cenu."),
                                (dict(sku="DIL-1"), "SKU karty neodpovídá formátu VD-<uuid> - není to Vandr karta."),
                                (dict(glb_file="vandr/neexistuje.glb"), "GLB soubor chybí na disku: vandr/neexistuje.glb")):
                db.shop_products[int(KARTA)] = dict(puvodni, **zmena)
                stat, j = _post(KARTA)
                self.assertEqual((stat, j), (400, {"error": text}), zmena)
        finally:
            db.shop_products[int(KARTA)] = puvodni
        self.assertEqual(db.offers, [], "pri odmitnuti nesmi vzniknout nabidka")


# ---------------------------------------------------------------------------
# Uspech: skutecny Blender build, GLB, model route, cache hit, znaceni
# ---------------------------------------------------------------------------

@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestUspech(Base):
    @classmethod
    def setUpClass(cls):
        reset()
        cls.cache = _nova_cache()
        vso, om = S["vso"], S["offer_model"]
        cls.volani_buildu = []
        orig = om.spust_build

        def pocitej(*a, **k):
            cls.volani_buildu.append(time.time())
            return orig(*a, **k)
        om.spust_build = pocitej
        try:
            t = time.time()
            cls.stat, cls.j = _post(KARTA)
            cls.sekundy = time.time() - t
        finally:
            om.spust_build = orig
        cls.model = _stored_model(cls.j["offer_id"]) if cls.stat == 201 else None
        cls.audit = list(S["audit"])
        cls.token = _token(cls.j["online_url"]) if cls.stat == 201 else None

    def setUp(self):
        # NEmazat nabidku z setUpClass; jen vychozi atrapy a cache tridy
        vso, om = S["vso"], S["offer_model"]
        vso._spust_artisan = F.artisan_nova(KARTA)
        vso._staticky_model = S["puvodni"]["staticky"]
        vso._offer_model = S["puvodni"]["offer_model"]
        om.spust_build = S["puvodni"]["spust_build"]
        os.environ.pop("V3D_MARK_SECRET", None)
        vso._znacka_vypnuto_zalogovano = False
        vso.V3D_CACHE_DIR = self.cache

    def test_odpoved(self):
        j = self.j
        self.assertEqual(self.stat, 201, j)
        self.assertEqual(j["status"], "ok")
        for k in ("offer_id", "offer_number", "online_url", "rozmer_mm", "pocet_profilu", "vandr_car_name"):
            self.assertIn(k, j)                                   # dosavadni klice kontraktu
        self.assertTrue(j["online_url"].startswith("/nabidka-online.html?t="))
        self.assertEqual(len(j["rozmer_mm"]), 3)
        self.assertGreater(j["pocet_profilu"], 0)
        self.assertEqual(j["obrazky_zdroj"], {"narys": "vandr", "view3d": "vandr"})      # Vandr obrazky maji prednost
        self.assertIsNone(j["poznamka"])
        self.assertIsNone(j["obrazky_rozmery_mm"])
        self.assertIs(j["v3d"], True)
        self.assertIsNone(j["v3d_duvod"])
        self.assertIs(j["v3d_cache"], False)                      # prvni sestaveni
        self.assertEqual(j["v3d_znacka"], "vypnuto")              # klic neni nastaven
        self.assertRegex(j["v3d_build"], r"^b\d+-[0-9a-f]{6}$")
        self.assertGreater(j["v3d_ms"], 1000)                     # skutecny Blender
        self.assertIsInstance(j["v3d_varovani"], list)
        self.assertTrue(all(isinstance(x, str) for x in j["v3d_varovani"]))
        self.assertEqual(len(self.volani_buildu), 1)
        self.assertLess(self.sekundy, 55, "pozadavek se musi vejit do 55 s")

    def test_glb_je_ciste_a_projde_kontrolami(self):
        v3d_glb = S["v3d_glb"]
        raw = self.model
        spec = v3d_glb.embedded_spec(raw)
        self.assertIsInstance(spec, dict)
        self.assertEqual(spec.get("v"), 1)
        self.assertGreater(len(spec.get("motions") or []), 0)
        out = v3d_glb.sanitize(raw, spec)                          # druhy pruchod = totez (idempotence)
        self.assertEqual(out, raw)
        g, b = v3d_glb.read_glb(raw)
        v3d_glb.final_check(g)
        v3d_glb.check_structure(g, b, "test")
        v3d_glb.check_bin(g, b)
        # bez textur
        for k in ("images", "textures", "samplers", "animations", "cameras", "skins"):
            self.assertFalse(g.get(k), k)
        for m in g.get("materials", []):
            pbr = m.get("pbrMetallicRoughness") or {}
            self.assertFalse(any(k.endswith("Texture") for k in list(m) + list(pbr)), "material s texturou")
        # jmena jen n/p/m, extras jen {g} a v3d
        for n in g["nodes"]:
            if "name" in n:
                self.assertRegex(n["name"], r"^(n|p)\d+$")
            if "extras" in n:
                self.assertEqual(set(n["extras"]), {"g"})
        for m in g.get("materials", []):
            if "name" in m:
                self.assertRegex(m["name"], r"^m\d+$")
        for me in g.get("meshes", []):
            self.assertNotIn("name", me)
            self.assertNotIn("extras", me)
        self.assertEqual(g["asset"], {"version": "2.0"})
        self.assertEqual(set(g["scenes"][0].get("extras", {})), {"v3d"})
        # zadny retezec z JSON nesmi odporovat zakazanemu regexu ani nest jmeno dilu/komponenty z Vandru
        retezce = []

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    retezce.append(str(k))
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
            elif isinstance(o, str):
                retezce.append(o)
        walk(g)
        for s in retezce:
            self.assertIsNone(v3d_glb.FORBIDDEN_RE.search(s), s)
        ctx = F.ctx_fixture(KARTA)
        unity = {k["unity_id"] for k in ctx["komponenty"]} | {d["unity_id"] for k in ctx["komponenty"] for d in k["dily"]}
        blob = json.dumps(g)
        for u in unity:
            self.assertNotIn(u, blob, "unity_id v zakaznickem GLB: %s" % u)
        # surove bajty (i BIN) jmena nenesou
        for u in list(unity)[:200]:
            if len(u) >= 6:
                self.assertNotIn(u.encode("utf-8"), raw)

    def test_varovani_jen_v_odpovedi_nikdy_v_glb(self):
        self.assertTrue(self.j["v3d_varovani"], "karta 4910 ma varovani buildu (nektera obsahuji unity_id) - jen pro admina")
        for w in self.j["v3d_varovani"]:
            if len(w) >= 8:
                self.assertNotIn(w.encode("utf-8"), self.model)

    def test_ulozeni_a_zaznam(self):
        db = S["db"]
        o = next(x for x in db.offers if x["id"] == self.j["offer_id"])
        self.assertTrue(o["view_3d_model"].endswith(".glb"))
        self.assertEqual(json.loads(o["offer_options"])["vandr_single_drawing"], True)    # beze zmeny
        slozka = next(f for f in db.folders if f["name"] == self.j["offer_number"])       # Modely nabidek/<cislo nabidky>
        zrcadlo = [f for f in db.drive_files if f["folder_id"] == slozka["id"]]
        self.assertEqual(len(zrcadlo), 1)                                                 # zrcadlo na Sdileny disk
        self.assertEqual(zrcadlo[0]["size_bytes"], len(self.model))
        akce = [a["action"] for a in self.audit]
        self.assertEqual(akce, ["create", "v3d_model"])
        d = json.loads(self.audit[1]["detail"])
        self.assertIs(d["v3d"], True)
        self.assertEqual(d["znacka"], "vypnuto")
        self.assertRegex(d["build"], r"^b\d+-[0-9a-f]{6}$")
        self.assertEqual(self.audit[1]["entity_id"], self.j["offer_id"])
        # 3D udaje nejsou verejne: offer_options zustava jen s dosavadnimi klici
        self.assertNotIn("v3d", json.loads(o["offer_options"]))
        # zadny dotaz mimo povolene tabulky (FakeDB by selhala), zadny DELETE
        self.assertFalse([q for q, _ in db.dotazy if q.upper().startswith("DELETE")])

    def test_model_pres_token(self):
        c = S["app"].test_client()
        r = c.get("/api/public/offers/%s/model" % self.token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "model/gltf-binary")
        self.assertEqual(r.headers["Cache-Control"], "private, no-cache")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.data, self.model)
        etag = r.headers["ETag"]
        self.assertTrue(etag)
        r2 = c.get("/api/public/offers/%s/model" % self.token, headers={"If-None-Match": etag})
        self.assertEqual(r2.status_code, 304)
        self.assertEqual(r2.data, b"")
        self.assertEqual(r2.headers["Cache-Control"], "private, no-cache")
        self.assertEqual(c.get("/api/public/offers/NEPLATNYTOKEN/model").status_code, 404)
        # zadny verejny pristup k /katalog/vandr/ pres tuto cestu: URL nese jen token, ne soubor
        self.assertNotIn("katalog", self.j["online_url"])

    def test_cache_hit_bez_blenderu(self):
        om = S["offer_model"]

        def nesmi(*a, **k):
            raise AssertionError("pri cache hit se nesmi spoustet Blender")
        om.spust_build = nesmi
        t = time.time()
        stat, j = _post(KARTA)
        dt = time.time() - t
        self.assertEqual(stat, 201, j)
        self.assertIs(j["v3d"], True)
        self.assertIs(j["v3d_cache"], True)
        self.assertLess(dt, 15)
        self.assertLess(j["v3d_ms"], 8000)
        self.assertNotEqual(j["offer_id"], self.j["offer_id"])        # nova nabidka (neni idempotentni)
        self.assertEqual(_stored_model(j["offer_id"]), self.model)    # bez klice je model stejny bajt po bajtu
        self.assertEqual(os.environ.get("V3D_MARK_SECRET"), None)

    def test_ctx_parita_se_snimkem(self):
        """ctx slozeny z atrapy vystupu artisan == snimek ctx (komponenty, instance, pozice, panel) -> stejny klic cache"""
        build_ctx = S["build_ctx"]
        conn = S["db"].conn()
        ctx = build_ctx.sestav_ctx(int(KARTA), konf_conn=conn, vandr_fetch=lambda u: F.vandr_output(KARTA), strict=True)
        snimek = F.ctx_fixture(KARTA)
        with open(os.path.join(CE.REPO, "scripts", "v3d", "pohyby-vychozi.json"), encoding="utf-8") as fh:
            snimek["pohyby_vychozi"] = json.load(fh)      # snimek je starsi nez soucasne pohyby-vychozi.json (stejne jako rebuild.py)
        for k in ("komponenty", "instance", "prirazeni_materialu", "kryci_listy_skryt", "glb_sha12", "vandr_predni_azimut_deg"):
            self.assertEqual(ctx[k], snimek[k], k)
        self.assertEqual(build_ctx.ctx_hash(ctx), build_ctx.ctx_hash(snimek))
        self.assertTrue(ctx["vandr_ok"])


@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestZnaceni(Base):
    """Cache rozehrata v TestUspech nemusi existovat (poradi testu) - tady si ji tvorime vlastni (jeden build)."""
    @classmethod
    def setUpClass(cls):
        reset()
        cls.cache = _nova_cache()
        cls.stat0, cls.j0 = _post(KARTA)                  # cold build, bez klice
        cls.nez = _stored_model(cls.j0["offer_id"])      # neoznaceny (cache) model

    def setUp(self):
        Base.setUp(self)
        S["vso"].V3D_CACHE_DIR = self.cache

    def test_vypnuto_bez_klice(self):
        self.assertEqual(self.stat0, 201)
        self.assertEqual(self.j0["v3d_znacka"], "vypnuto")
        v3d_mark = _mark()
        self.assertIsNone(v3d_mark.detect(self.nez, TEST_KLIC.encode())[0])      # nic k nalezeni

    def test_zapnuto_s_klicem_a_cte_se(self):
        os.environ["V3D_MARK_SECRET"] = TEST_KLIC
        S["offer_model"].spust_build = _nesmi_build
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertIs(j["v3d"], True)
        self.assertEqual(j["v3d_znacka"], "zapnuto")
        self.assertIs(j["v3d_cache"], True)
        oznaceny = _stored_model(j["offer_id"])
        self.assertNotEqual(oznaceny, self.nez)
        self.assertLess(abs(len(oznaceny) - len(self.nez)), 0.01 * len(self.nez))   # lisi se jen zapis min/max a POSITION
        v3d_mark, v3d_glb = _mark(), S["v3d_glb"]
        oid, jistota = v3d_mark.detect(oznaceny, TEST_KLIC.encode())
        self.assertEqual(oid, j["offer_id"])
        self.assertGreater(jistota, 1 - 1e-6)
        # krok navic proti neoznacenemu: lisi se jen POSITION a jejich min/max; model jde pres pojistku a final_check
        spec = v3d_glb.embedded_spec(oznaceny)
        self.assertEqual(v3d_glb.sanitize(oznaceny, spec), oznaceny)
        g, _b = v3d_glb.read_glb(oznaceny)
        v3d_glb.final_check(g)
        d = json.loads([a for a in S["audit"] if a["action"] == "v3d_model"][-1]["detail"])
        self.assertEqual(d["znacka"], "zapnuto")
        # jina nabidka = jina znacka
        stat2, j2 = _post(KARTA)
        o2 = _stored_model(j2["offer_id"])
        self.assertNotEqual(o2, oznaceny)
        self.assertEqual(v3d_mark.detect(o2, TEST_KLIC.encode())[0], j2["offer_id"])
        # jiny klic znacku neprecte jako tuto nabidku
        self.assertNotEqual(v3d_mark.detect(oznaceny, b"jiny-klic-0123456789abcdefghij")[0], j["offer_id"])
        # bez klice v prostredi se model zase neznaci a nema zadnou stopu
        os.environ.pop("V3D_MARK_SECRET")
        stat3, j3 = _post(KARTA)
        self.assertEqual(j3["v3d_znacka"], "vypnuto")
        self.assertEqual(_stored_model(j3["offer_id"]), self.nez)

    def test_flask_klic_se_nepouzije_jako_zaloha(self):
        # klic neni v prostredi, ale app.secret_key existuje -> znaceni se NEzapne
        S["offer_model"].spust_build = _nesmi_build
        self.assertTrue(S["app"].secret_key)
        stat, j = _post(KARTA)
        self.assertEqual(j["v3d_znacka"], "vypnuto")
        self.assertIsNone(_mark().detect(_stored_model(j["offer_id"]), _mark().derive_secret(S["app"].secret_key))[0])

    def test_kratky_klic_je_vypnuto_s_varovanim(self):
        os.environ["V3D_MARK_SECRET"] = "kratky"
        S["offer_model"].spust_build = _nesmi_build
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertIs(j["v3d"], True)
        self.assertEqual(j["v3d_znacka"], "vypnuto")
        self.assertTrue([w for w in j["v3d_varovani"] if "značení vypnuto" in w])
        self.assertEqual(_stored_model(j["offer_id"]), self.nez)

    def test_vypnuto_se_loguje_jednou(self):
        zaznamy = []

        class H(logging.Handler):
            def emit(self, rec):
                zaznamy.append(rec.getMessage())
        h = H(level=logging.WARNING)
        lg = S["app"].logger
        lg.addHandler(h)
        try:
            S["offer_model"].spust_build = _nesmi_build
            _post(KARTA)
            _post(KARTA)
        finally:
            lg.removeHandler(h)
        self.assertEqual(len([z for z in zaznamy if "VYPNUTO" in z]), 1)
        self.assertFalse([z for z in zaznamy if TEST_KLIC in z])

    def test_znaceni_selze_s_klicem_je_v3d_false(self):
        os.environ["V3D_MARK_SECRET"] = TEST_KLIC
        S["offer_model"].spust_build = _nesmi_build
        v3d_mark = _mark()
        orig = v3d_mark.mark

        def selze(*a, **k):
            raise S["v3d_glb"].V3DError("atrapa: vrchol mimo")
        v3d_mark.mark = selze
        vyst = self.staticky_atrapa()
        try:
            stat, j = _post(KARTA)
        finally:
            v3d_mark.mark = orig
        self.assertEqual(stat, 201, j)
        self.assertIs(j["v3d"], False)
        self.assertIn("nejde označit", j["v3d_duvod"])
        self.assertIn("atrapa: vrchol mimo", j["v3d_duvod"])
        self.assertEqual(_stored_model(j["offer_id"]), LEGACY)         # zakaznik NEdostane neoznaceny 3D model
        self.assertEqual(len(vyst), 1)
        d = json.loads([a for a in S["audit"] if a["action"] == "v3d_model"][-1]["detail"])
        self.assertIs(d["v3d"], False)
        self.assertNotIn(TEST_KLIC, json.dumps(j))


def _mark():
    import v3d_mark
    return v3d_mark


def _nesmi_build(*a, **k):
    raise AssertionError("tady se nesmi spoustet Blender (ocekavana cache)")


# ---------------------------------------------------------------------------
# Selhani: nabidka vznikne dosavadni cestou, v3d:false + duvod
# ---------------------------------------------------------------------------

class TestSelhani(Base):
    def over_nabidku_bez_3d(self, stat, j, duvod_obsahuje):
        self.assertEqual(stat, 201, j)
        self.assertIs(j["v3d"], False)
        self.assertIsNone(j["v3d_cache"])
        self.assertIsNone(j["v3d_znacka"])
        self.assertEqual(j["v3d_varovani"], [])
        self.assertIsInstance(j["v3d_duvod"], str)
        self.assertIn(duvod_obsahuje, j["v3d_duvod"])
        self.assertEqual(len(S["db"].offers), 1, "nabidka musi vzniknout")
        for k in ("offer_id", "offer_number", "online_url", "rozmer_mm", "pocet_profilu", "vandr_car_name"):
            self.assertIn(k, j)
        self.assertEqual(_stored_model(j["offer_id"]), LEGACY, "dosavadni cesta: staticky model beze zmeny")
        d = json.loads(S["audit"][-1]["detail"])
        self.assertEqual((S["audit"][-1]["action"], d["v3d"]), ("v3d_model", False))
        self.assertIn(duvod_obsahuje, d["duvod"])
        return d

    def test_build_selze(self):
        om = S["offer_model"]

        def pad(*a, **k):
            raise om.V3DBuildError("Sestaveni 3D modelu selhalo (rc=1): atrapa Blender pad")
        om.spust_build = pad
        _nova_cache()
        vyst = self.staticky_atrapa()
        stat, j = _post(KARTA)
        self.over_nabidku_bez_3d(stat, j, "atrapa Blender pad")
        self.assertEqual(len(vyst), 1)
        self.assertEqual([f for f in os.listdir(S["vso"].V3D_CACHE_DIR) if f.endswith((".glb", ".json"))], [],
                         "po selhani buildu se do cache nic nezapise")

    def test_modul_offer_model_nejde_nacist(self):
        def nejde():
            raise ImportError("atrapa: chybi build_ctx")
        S["vso"]._offer_model = nejde
        self.staticky_atrapa()
        stat, j = _post(KARTA)
        self.over_nabidku_bez_3d(stat, j, "nejde načíst")

    def test_neocekavana_chyba_buildu(self):
        om = S["offer_model"]
        orig = om.build_offer_model

        def boom(*a, **k):
            raise KeyError("atrapa")
        om.build_offer_model = boom
        try:
            self.staticky_atrapa()
            stat, j = _post(KARTA)
        finally:
            om.build_offer_model = orig
        self.over_nabidku_bez_3d(stat, j, "neočekávaná chyba")

    def test_prikaz_bez_v3d(self):
        art = F.artisan_stara(KARTA)
        S["vso"]._spust_artisan = art
        S["offer_model"].spust_build = _nesmi_build
        vyst = self.staticky_atrapa()
        stat, j = _post(KARTA)
        d = self.over_nabidku_bez_3d(stat, j, "Vandr příkaz bez --v3d")
        self.assertEqual(j["v3d_duvod"], "Vandr příkaz bez --v3d")
        self.assertEqual([("--v3d" in a) for a in art.volani], [True, False])    # zkusit nove, pak dosavadni
        self.assertEqual(len(vyst), 1)

    def test_klon_karty_bere_vandr_data_pod_uuid_zdroje(self):
        """bot5 2026-10-07 ("tataz karta jen pro jine auto"): klon Vandr karty (scripts/2026-10-07_vandr_klon_karty_jine_vozidlo.py) ma vlastni SKU, Vandr data jsou pod uuid ZDROJE
        (soubor private-files/vandr-klony.json {uuid klonu: uuid zdroje}); karta bez zaznamu pouziva uuid ze SKU jako dosud."""
        sku_uuid = F.SKU[KARTA][3:]
        zdroj = "2c24d107-6726-4b5b-af74-c6fb9affc661"
        soubor = os.path.join(S["tmp"], "vandr-klony.json")
        puv = S["vso"].VANDR_KLONY_SOUBOR
        try:
            S["vso"].VANDR_KLONY_SOUBOR = soubor
            S["vso"]._klony_cache["mtime"] = None
            art = F.artisan_bez_obrazku(KARTA)
            S["vso"]._spust_artisan = art
            _post(KARTA)
            self.assertEqual(art.volani[0][0], sku_uuid, "bez souboru mapovani: uuid ze SKU")
            with open(soubor, "w", encoding="utf-8") as fh:
                json.dump({sku_uuid.upper(): zdroj.upper()}, fh)                # velka pismena: mapovani je case-insensitive
            S["vso"]._klony_cache["mtime"] = None
            art2 = F.artisan_bez_obrazku(KARTA)
            S["vso"]._spust_artisan = art2
            stat, j = _post(KARTA)
            self.assertEqual(stat, 201, j)
            self.assertEqual(art2.volani[0][0], zdroj, "klon: vandr:offer-data se vola s uuid zdroje")
            self.assertEqual(S["vso"]._vandr_uuid_karty("VD-ffffffff-0000-0000-0000-000000000000"), "ffffffff-0000-0000-0000-000000000000", "karta bez zaznamu: uuid ze SKU")
            with open(soubor, "w", encoding="utf-8") as fh:
                fh.write("{rozbity json")
            S["vso"]._klony_cache["mtime"] = None
            self.assertEqual(S["vso"]._vandr_uuid_karty(F.SKU[KARTA]), sku_uuid, "rozbity soubor mapovani: uuid ze SKU, nic nespadne")
        finally:
            S["vso"].VANDR_KLONY_SOUBOR = puv
            S["vso"]._klony_cache["mtime"] = None

    def test_prikaz_s_v3d_selze_jinak(self):
        pocet = []

        def art(argumenty, timeout_s):
            pocet.append(list(argumenty))
            if "--v3d" in argumenty:
                return F.Proc(255, "", "SQLSTATE[42S02]: Base table or view not found: atrapa")
            return F.Proc(0, json.dumps(F.vandr_output(KARTA, False)))
        S["vso"]._spust_artisan = art
        S["offer_model"].spust_build = _nesmi_build
        self.staticky_atrapa()
        stat, j = _post(KARTA)
        self.over_nabidku_bez_3d(stat, j, "Vandr příkaz s --v3d selhal")
        self.assertIn("atrapa", j["v3d_duvod"])
        self.assertEqual(len(pocet), 2)

    def test_vypinac_soubor(self):
        vso = S["vso"]
        puvodni = vso.V3D_VYPNUTO_SOUBOR
        vso.V3D_VYPNUTO_SOUBOR = os.path.join(S["tmp"], "v3d-vypnuto")
        try:
            S["offer_model"].spust_build = _nesmi_build
            vyst = self.staticky_atrapa()
            with open(vso.V3D_VYPNUTO_SOUBOR, "w") as fh:
                fh.write("")
            stat, j = _post(KARTA)
            self.over_nabidku_bez_3d(stat, j, "vypnutý souborem")
            self.assertEqual(len(vyst), 1)
            os.remove(vso.V3D_VYPNUTO_SOUBOR)
            S["db"].offers.clear()
            S["audit"].clear()
            reset()
            vso.V3D_VYPNUTO_SOUBOR = os.path.join(S["tmp"], "v3d-vypnuto")
            self.assertFalse(os.path.exists(vso.V3D_VYPNUTO_SOUBOR))
            om = S["offer_model"]
            om.spust_build = lambda *a, **k: (_ for _ in ()).throw(om.V3DBuildError("atrapa - build se zkusil"))
            self.staticky_atrapa()
            _nova_cache()
            stat, j = _post(KARTA)
            self.assertIn("build se zkusil", j["v3d_duvod"])           # bez souboru se 3D zase zkousi
        finally:
            vso.V3D_VYPNUTO_SOUBOR = puvodni

    def test_oba_volani_artisan_selzou_je_500_jako_dosud(self):
        S["vso"]._spust_artisan = lambda argumenty, timeout_s: F.Proc(1, "", "stored_model nenalezen")
        stat, j = _post(KARTA)
        self.assertEqual(stat, 500)
        self.assertTrue(j["error"].startswith("Načtení dat z Vandru selhalo: "))
        self.assertEqual(S["db"].offers, [])

    def test_artisan_timeout_je_500_a_neopakuje_se(self):
        import subprocess
        volani = []

        def art(argumenty, timeout_s):
            volani.append(1)
            raise subprocess.TimeoutExpired("php", timeout_s)
        S["vso"]._spust_artisan = art
        stat, j = _post(KARTA)
        self.assertEqual(stat, 500)
        self.assertEqual(len(volani), 1)
        self.assertEqual(S["db"].offers, [])

    def test_staticky_model_selze_je_500_jako_dosud(self):
        _nova_cache()
        S["offer_model"].spust_build = lambda *a, **k: (_ for _ in ()).throw(S["offer_model"].V3DBuildError("atrapa"))

        def pad(glb_path, t_start):
            raise RuntimeError("Blender geometrie selhala: atrapa")
        S["vso"]._staticky_model = pad
        stat, j = _post(KARTA)
        self.assertEqual(stat, 500)
        self.assertTrue(j["error"].startswith("Výpočet geometrie selhal: "))
        self.assertEqual(S["db"].offers, [])

    def test_otravena_cache_se_nepousti_k_zakaznikovi(self):
        """cache je jen soubor na disku - po podvrhu (jmeno 'logo', textura, bez spec, poskozeny soubor) musi brana model
        odmitnout, zakaznik dostane dosavadni staticky model a polozka cache se smaze (dalsi pozadavek ji postavi znovu)"""
        if not BLENDER_OK:
            self.skipTest("Blender neni k dispozici")
        v3d_glb = S["v3d_glb"]
        cache = _nova_cache()
        stat, j = _post(KARTA)                       # cold build do teto cache
        self.assertEqual(stat, 201, j)
        self.assertIs(j["v3d"], True, j)
        glbs = [f for f in os.listdir(cache) if f.endswith(".glb")]
        self.assertEqual(len(glbs), 1)
        glb_p = os.path.join(cache, glbs[0])
        json_p = glb_p[:-4] + ".json"
        with open(glb_p, "rb") as fh:
            dobry = fh.read()
        with open(json_p, "rb") as fh:
            dobry_json = fh.read()
        g, b = v3d_glb.read_glb(dobry)

        def varianty():
            g1 = copy.deepcopy(g)
            nid = next(i for i, n in enumerate(g1["nodes"]) if "mesh" in n)
            g1["nodes"][nid]["name"] = "logo"
            yield "uzel logo", v3d_glb.write_glb(g1, b), "logo"
            g2 = copy.deepcopy(g)
            g2["scenes"][0].pop("extras", None)
            yield "bez spec", v3d_glb.write_glb(g2, b), "popis v3d"
            g3 = copy.deepcopy(g)
            g3["images"] = [{"uri": "data:image/png;base64,AAAA"}]
            yield "textura", v3d_glb.write_glb(g3, b), "obrazky"
            yield "poskozeny soubor", b"glTFposkozeny", "kratky"
        for nazev, data, kus_duvodu in varianty():
            with self.subTest(nazev):
                with open(glb_p, "wb") as fh:
                    fh.write(data)
                with open(json_p, "wb") as fh:
                    fh.write(dobry_json)
                S["db"].offers.clear()
                S["audit"].clear()
                S["offer_model"].spust_build = _nesmi_build
                self.staticky_atrapa()
                stat, j = _post(KARTA)
                self.assertEqual(stat, 201, j)
                self.assertIs(j["v3d"], False, j)
                self.assertIn("neprošel kontrolou", j["v3d_duvod"])
                self.assertIn(kus_duvodu, j["v3d_duvod"])
                self.assertEqual(_stored_model(j["offer_id"]), LEGACY)      # nic z podvrzenych dat se k nabidce nedostalo
                self.assertFalse([f for f in os.listdir(cache) if f.endswith((".glb", ".json"))],
                                 "odmitnuta polozka cache se musi smazat")
        # samoopravа: dalsi pozadavek postavi model znovu a zakaznik ho dostane
        reset()
        S["vso"].V3D_CACHE_DIR = cache
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertIs(j["v3d"], True, j)
        self.assertIs(j["v3d_cache"], False)
        self.assertEqual(_stored_model(j["offer_id"]), dobry)

    def test_neuplny_geom_z_cache(self):
        """valid JSON, ale bez overall_size/profily: nabidka nesmi spadnout na KeyError az po zalozeni, 3D se vypne a cache smaze"""
        if not BLENDER_OK:
            self.skipTest("Blender neni k dispozici")
        om = S["offer_model"]
        cache = _nova_cache()
        stat0, j0 = _post(KARTA)                     # postavi platny model
        self.assertIs(j0["v3d"], True, j0)
        jp = [f for f in os.listdir(cache) if f.endswith(".json")]
        self.assertEqual(len(jp), 1)
        cesta = os.path.join(cache, jp[0])
        with open(cesta, encoding="utf-8") as fh:
            g = json.load(fh)
        for klic in ("overall_size", "profily"):
            with self.subTest(chybi=klic):
                g2 = dict(g)
                g2.pop(klic)
                with open(cesta, "w", encoding="utf-8") as fh:
                    json.dump(g2, fh)
                om.spust_build = _nesmi_build
                S["db"].offers.clear()
                self.staticky_atrapa()
                stat, j = _post(KARTA)
                self.assertEqual(stat, 201, j)
                self.assertIs(j["v3d"], False)
                self.assertIn("neúplný", j["v3d_duvod"])
                self.assertFalse([f for f in os.listdir(cache) if f.endswith((".glb", ".json"))])
                # obnovit pro dalsi variantu: znovu postavit
                reset()
                S["vso"].V3D_CACHE_DIR = cache
                stat1, j1 = _post(KARTA)
                self.assertIs(j1["v3d"], True, j1)

    def test_casovy_rozpocet(self):
        om, vso = S["offer_model"], S["vso"]
        zachyt = {}

        def build(shop_product_id, conn, cache_dir, **k):
            zachyt.update(k, cache_dir=cache_dir)
            raise om.V3DBuildError("atrapa")
        orig = om.build_offer_model
        om.build_offer_model = build
        try:
            self.staticky_atrapa()
            _nova_cache()
            _post(KARTA)
        finally:
            om.build_offer_model = orig
        maximum = vso.CELKOVY_LIMIT_S - vso.REZERVA_PO_BUILDU_S - vso.REZERVA_STATICKY_MODEL_S
        self.assertEqual((vso.CELKOVY_LIMIT_S, vso.REZERVA_PO_BUILDU_S, vso.REZERVA_STATICKY_MODEL_S), (55, 8, 20))
        self.assertLessEqual(zachyt["celkovy_limit_s"], maximum)
        self.assertGreater(zachyt["celkovy_limit_s"], maximum - 10)
        self.assertEqual(zachyt["cache_dir"], vso.V3D_CACHE_DIR)
        self.assertIn("vandr_fetch", zachyt)
        # po vycerpani rozpoctu dostane staticky Blender aspon MIN_STATICKY_TIMEOUT_S, nikdy vic nez puvodnich 55 s
        casy = []
        puvodni_blender = vso._run_blender_geometry

        def atrapa_blender(g, j, c, timeout_s=None):
            casy.append(timeout_s)
            with open(c, "wb") as fh:
                fh.write(b"x")
            with open(j, "w") as fh:
                fh.write('{"overall_size":[1,2,3],"profily":[]}')
        vso._run_blender_geometry = atrapa_blender
        try:
            puvodni = S["puvodni"]["staticky"]
            puvodni("x.glb", time.time())            # cely rozpocet: nejvyse puvodnich 55 s
            puvodni("x.glb", time.time() - 50)       # zbyva 7 s -> podlaha 10 s
            puvodni("x.glb", time.time() - 500)      # rozpocet davno pryc -> podlaha 10 s
        finally:
            vso._run_blender_geometry = puvodni_blender
        self.assertEqual(casy, [55, vso.MIN_STATICKY_TIMEOUT_S, vso.MIN_STATICKY_TIMEOUT_S])


@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestStatickyBlender(Base):
    def test_dosavadni_cesta_realny_blender(self):
        """selhani 3D (atrapa) -> SKUTECNY dosavadni Blender krok scripts/2026-09-28_vandr_offer_geometry.py"""
        om = S["offer_model"]
        gs = S["vso"].GEOMETRY_SCRIPT
        if not os.path.exists(gs):
            self.skipTest("chybi %s" % gs)
        om.spust_build = lambda *a, **k: (_ for _ in ()).throw(om.V3DBuildError("atrapa"))
        _nova_cache()
        t = time.time()
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertIs(j["v3d"], False)
        self.assertEqual(j["v3d_duvod"], "atrapa")
        raw = _stored_model(j["offer_id"])
        self.assertEqual(raw[:4], b"glTF")
        self.assertEqual(len(j["rozmer_mm"]), 3)
        self.assertGreater(j["pocet_profilu"], 0)
        self.assertLess(time.time() - t, 55)
        g, _ = S["v3d_glb"].read_glb(raw)
        self.assertIsNone(S["v3d_glb"].embedded_spec(raw))                # staticky model je bez v3d


@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestSoubeh(Base):
    def test_dva_pozadavky_jeden_build(self):
        om, vso = S["offer_model"], S["vso"]
        _nova_cache()
        volani = []
        orig = om.spust_build

        def pocitej(*a, **k):
            volani.append(time.time())
            return orig(*a, **k)
        om.spust_build = pocitej
        vysl = [None, None]

        def beh(i):
            vysl[i] = _post(KARTA, S["app"].test_client())
        ts = [threading.Thread(target=beh, args=(i,)) for i in range(2)]
        t0 = time.time()
        for t in ts:
            t.start()
            time.sleep(0.3)
        for t in ts:
            t.join(120)
        dt = time.time() - t0
        self.assertEqual(len(volani), 1, "dva soubezne pozadavky na stejny klic = jediny Blender build")
        for stat, j in vysl:
            self.assertEqual(stat, 201, j)
            self.assertIs(j["v3d"], True, j)
        self.assertEqual(sorted(j["v3d_cache"] for _s, j in vysl), [False, True])     # jeden stavel, druhy vzal z cache
        self.assertNotEqual(vysl[0][1]["offer_id"], vysl[1][1]["offer_id"])
        self.assertEqual(_stored_model(vysl[0][1]["offer_id"]), _stored_model(vysl[1][1]["offer_id"]))
        self.assertLess(dt, 55)

    def test_zamek_neotevrelny_je_v3d_false_ne_500(self):
        om = S["offer_model"]
        d = _nova_cache()
        os.chmod(d, 0o500)
        try:
            if os.access(d, os.W_OK):
                self.skipTest("test bezi jako root - prava adresare nic nezakazuji")
            self.staticky_atrapa()
            stat, j = _post(KARTA)
            self.assertEqual(stat, 201, j)
            self.assertIs(j["v3d"], False)
        finally:
            os.chmod(d, 0o700)


# ---------------------------------------------------------------------------
# Nahradni obrazky (Vandr obrazky chybi; Robert 2026-10-02: tlacitko vracelo 400 u karet #4053, #4482)
# ---------------------------------------------------------------------------

SHOTS = os.environ.get("V3D_TEST_SHOTS") or os.path.join(CE.OUT, "shots_nahrada")
FRAMES = None


def _frames():
    global FRAMES
    if FRAMES is None:
        with open(os.path.join(CE.FIX, "frames_karty.json"), encoding="utf-8") as fh:
            FRAMES = json.load(fh)
    return FRAMES


def _obrazky_nabidky(offer_id):
    o = next(x for x in S["db"].offers if x["id"] == offer_id)
    out = {}
    for k, col in (("narys", "view_narys"), ("view3d_a", "view_3d_a"), ("view3d_b", "view_3d_b")):
        with open(os.path.join(S["scene_offers"].OFFER_IMAGES_DIR, o[col]), "rb") as fh:
            out[k] = fh.read()
    return out


def _uloz_ukazku(nazev, data, pripona):
    os.makedirs(SHOTS, exist_ok=True)
    with open(os.path.join(SHOTS, "%s.%s" % (nazev, pripona)), "wb") as fh:
        fh.write(data)


def _je(raw, mime):
    return raw[:3] == b"\xff\xd8\xff" if mime == "jpeg" else raw[:8] == b"\x89PNG\r\n\x1a\n"


def _rozmer_obrazku(raw):
    from PIL import Image
    import io
    return Image.open(io.BytesIO(raw)).size


class TestNahradniObrazky(Base):
    @classmethod
    def setUpClass(cls):
        if not BLENDER_OK:
            raise unittest.SkipTest("Blender neni k dispozici")
        reset()
        cls.cache = _nova_cache()
        S["vso"]._spust_artisan = F.artisan_nova(KARTA)
        stat, j = _post(KARTA)                        # postavi v3d model karty 4910 do cache teto tridy
        assert stat == 201 and j["v3d"] is True, j

    def setUp(self):
        reset()
        S["vso"].V3D_CACHE_DIR = self.cache
        S["offer_model"].spust_build = _nesmi_build
        S["db"].turntable_frames.clear()
        S["db"].gallery_items.clear()
        S["db"].shop_images.clear()
        S["vso"].CONTENT_FILES_DIR = CE.CONTENT_FILES

    def need(self, rel):
        if not os.path.isfile(os.path.join(CE.CONTENT_FILES, rel)):
            self.skipTest("chybi %s ve webapp/content-files (jen cteni)" % rel)

    def frame_bytes(self, karta, az, el=0, tier=None):
        rows = [r for r in _frames()[karta] if r["azimuth_deg"] == az and r["elevation_deg"] == el]
        vhodne = [x for x in rows if (x["tier_px"] == tier) if tier is not None] or [x for x in rows if x["bytes"] <= 1500 * 1024]
        r = max(vhodne, key=lambda x: x["tier_px"])
        self.need(r["filename"])
        with open(os.path.join(CE.CONTENT_FILES, r["filename"]), "rb") as fh:
            return fh.read()

    def test_v3d_karta_bez_vandr_obrazku_snimky_otocky(self):
        db = S["db"]
        db.turntable_frames[int(KARTA)] = _frames()[KARTA]
        S["vso"]._spust_artisan = F.artisan_bez_obrazku(KARTA)
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertIs(j["v3d"], True)
        # Robert 2026-10-06: Vandr 2D vykres se jen PREBIRA, nikdy nevyrabi - bez nej vznikne nabidka BEZ stranky Vykresy (offer_options.vandr_bez_vykresu), 3D pohledy zustavaji nahradou
        self.assertEqual(j["obrazky_zdroj"], {"narys": "chybi", "view3d": "nahrada"})
        self.assertTrue(j["poznamka"].startswith("Vandr u karty nemá kótovaný 2D výkres"), j["poznamka"])
        self.assertIn("snímek otočky", j["poznamka"])
        self.assertNotIn("vyrobil server", j["poznamka"])
        im = _obrazky_nabidky(j["offer_id"])
        self.assertEqual(_rozmer_obrazku(im["narys"]), (1, 1))                       # NOT NULL sloupec: prazdny zastupny PNG, stranka Vykresy se nezobrazuje
        self.assertIsNone(j["obrazky_rozmery_mm"])                                   # nic se uz z modelu nekotuje
        oo = json.loads(S["db"].offers[-1]["offer_options"])
        self.assertIs(oo.get("vandr_bez_vykresu"), True)
        self.assertIs(oo.get("vandr_single_drawing"), True)
        # 3D pohledy = snimky otocky: front +-35 -> nejblizsi azimut, elevace 0, nejvetsi tier do 1,5 MB
        front = F.ctx_fixture(KARTA)["vandr_predni_azimut_deg"]
        for slot, k in (("a", "view3d_a"), ("b", "view3d_b")):
            cil = (front + (35 if slot == "a" else -35)) % 360
            azy = sorted({x["azimuth_deg"] for x in _frames()[KARTA]}, key=lambda a: (min((a - cil) % 360, (cil - a) % 360), a))
            self.assertTrue(_je(im[k], "jpeg"))
            self.assertEqual(im[k], self.frame_bytes(KARTA, azy[0]), "slot %s: azimut %s" % (slot, azy[0]))
        self.assertNotEqual(im["view3d_a"], im["view3d_b"])
        d = json.loads([a for a in S["audit"] if a["action"] == "v3d_model"][-1]["detail"])
        self.assertEqual(d["obrazky"], {"narys": "chybi", "view3d": "nahrada"})
        self.assertEqual(S["db"].offers[-1]["view_3d_a"][-4:], ".jpg")                       # JPEG se uklada jako .jpg
        _uloz_ukazku("%s_v3d_pohled_a_zprava" % KARTA, im["view3d_a"], "jpg")
        _uloz_ukazku("%s_v3d_pohled_b_zleva" % KARTA, im["view3d_b"], "jpg")

    def test_kombinace_vandr_a_nahrada(self):
        S["db"].turntable_frames[int(KARTA)] = _frames()[KARTA]
        S["vso"]._spust_artisan = F.artisan_bez_obrazku(KARTA, jen=("image_2d_with_dim", "image_3d_primary"))
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertEqual(j["obrazky_zdroj"], {"narys": "vandr", "view3d": "kombinace"})
        self.assertIsNone(j["obrazky_rozmery_mm"])
        im = _obrazky_nabidky(j["offer_id"])
        self.assertEqual(im["narys"], F.PNG1)                       # Vandr ma prednost
        self.assertEqual(im["view3d_a"], F.PNG1)
        self.assertTrue(_je(im["view3d_b"], "jpeg"))                # jen chybejici je nahrada (slot b = zepredu doleva)
        self.assertIn("3D pohledy", j["poznamka"])
        self.assertNotIn("kótovaný výkres", j["poznamka"])

    def test_vsechno_vandr_beze_zmeny(self):
        S["db"].turntable_frames[int(KARTA)] = _frames()[KARTA]
        n0 = len(S["db"].dotazy)
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertEqual(j["obrazky_zdroj"], {"narys": "vandr", "view3d": "vandr"})
        self.assertIsNone(j["poznamka"])
        im = _obrazky_nabidky(j["offer_id"])
        self.assertEqual(set(im.values()), {F.PNG1})
        self.assertFalse([q for q, _p in S["db"].dotazy[n0:] if "product_turntable_frames" in q or "gallery" in q.lower()],
                         "pri Vandr obrazcich se nahrada ani nehleda")

    def test_bez_snimku_fotky_galerie_a_pohled_z_modelu(self):
        """zadne snimky otocky: 1. fotka z galerie (content_gallery_items pred shop_product_images), zbytek pohled z modelu"""
        self.need("gallery/vestavby-hover-t1024v2/product-4053-hover.jpg")
        S["db"].shop_images[int(KARTA)] = ["vestavby-hover-t1024v2/product-4053-hover.jpg"]
        S["vso"]._spust_artisan = F.artisan_bez_obrazku(KARTA)
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        im = _obrazky_nabidky(j["offer_id"])
        with open(os.path.join(CE.CONTENT_FILES, "gallery/vestavby-hover-t1024v2/product-4053-hover.jpg"), "rb") as fh:
            self.assertEqual(im["view3d_a"], fh.read())             # prvni fotka galerie
        self.assertTrue(_je(im["view3d_b"], "png"))
        self.assertEqual(_rozmer_obrazku(im["view3d_b"]), (1280, 960))   # druha: stinovany pohled z modelu
        self.assertIn("fotka z galerie karty", j["poznamka"])
        self.assertIn("pohled z modelu", j["poznamka"])
        self.assertEqual(j["obrazky_zdroj"]["view3d"], "nahrada")

    def test_galerie_poradi_zdroju(self):
        gi = os.path.join(CE.CONTENT_FILES, "gallery-items")
        if not os.path.isdir(gi) or not [f for f in os.listdir(gi) if f.lower().endswith((".jpg", ".png", ".jpeg"))]:
            self.skipTest("v content-files/gallery-items neni zadny obrazek")
        verejna = sorted(f for f in os.listdir(gi) if f.lower().endswith((".jpg", ".png", ".jpeg")))[0]
        self.need("gallery/vestavby-hover-t1024v2/product-4053-hover.jpg")
        S["db"].gallery_items[int(KARTA)] = [verejna]
        S["db"].shop_images[int(KARTA)] = ["vestavby-hover-t1024v2/product-4053-hover.jpg"]
        S["vso"]._spust_artisan = F.artisan_bez_obrazku(KARTA)
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        im = _obrazky_nabidky(j["offer_id"])
        with open(os.path.join(gi, verejna), "rb") as fh:
            raw = fh.read()
        from PIL import Image
        import io
        self.assertEqual(Image.open(io.BytesIO(im["view3d_a"])).size, Image.open(io.BytesIO(raw)).size)     # 1. = content_gallery_items
        with open(os.path.join(CE.CONTENT_FILES, "gallery/vestavby-hover-t1024v2/product-4053-hover.jpg"), "rb") as fh:
            self.assertEqual(im["view3d_b"], fh.read())             # 2. = shop_product_images
        self.assertNotIn("pohled z modelu", j["poznamka"])

    def test_bez_snimku_a_bez_galerie_oba_pohledy_z_modelu(self):
        S["vso"]._spust_artisan = F.artisan_bez_obrazku(KARTA)
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        im = _obrazky_nabidky(j["offer_id"])
        for k in ("view3d_a", "view3d_b"):
            self.assertTrue(_je(im[k], "png"))
            self.assertEqual(_rozmer_obrazku(im[k]), (1280, 960))
        self.assertNotEqual(im["view3d_a"], im["view3d_b"])
        self.assertEqual(j["poznamka"].count("pohled z modelu"), 2)
        self.assertEqual(j["obrazky_zdroj"], {"narys": "chybi", "view3d": "nahrada"})
        _uloz_ukazku("%s_v3d_pohled_z_modelu_a" % KARTA, im["view3d_a"], "png")
        _uloz_ukazku("%s_v3d_pohled_z_modelu_b" % KARTA, im["view3d_b"], "png")

    def test_soubor_snimku_chybi_pouzije_se_jiny_tier(self):
        """snimek v DB je, ale soubor na disku ne: dalsi kandidat (mensi tier), kdyz neni nic, pohled z modelu"""
        import shutil
        front = F.ctx_fixture(KARTA)["vandr_predni_azimut_deg"]
        rows = [r for r in _frames()[KARTA] if r["elevation_deg"] == 0 and r["azimuth_deg"] in (300, 240)]
        for r in rows:
            self.need(r["filename"])
        tmp = tempfile.mkdtemp(prefix="content_", dir=S["tmp"])
        for r in rows:
            if r["tier_px"] == 1024:                       # na disku jen tier 1024, 2048 chybi
                dst = os.path.join(tmp, r["filename"])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy(os.path.join(CE.CONTENT_FILES, r["filename"]), dst)
        S["vso"].CONTENT_FILES_DIR = tmp
        S["db"].turntable_frames[int(KARTA)] = _frames()[KARTA]
        S["vso"]._spust_artisan = F.artisan_bez_obrazku(KARTA)
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        im = _obrazky_nabidky(j["offer_id"])
        for slot, az in (("view3d_a", 300), ("view3d_b", 240)):
            r = next(x for x in rows if x["azimuth_deg"] == az and x["tier_px"] == 1024)
            with open(os.path.join(CE.CONTENT_FILES, r["filename"]), "rb") as fh:
                self.assertEqual(im[slot], fh.read())
        # nic na disku: snimky se nenajdou -> galerie prazdna -> pohled z modelu
        S["vso"].CONTENT_FILES_DIR = tempfile.mkdtemp(prefix="content_prazdny_", dir=S["tmp"])
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertEqual(j["poznamka"].count("pohled z modelu"), 2)

    def test_vandr_soubor_chybi_na_disku_je_nabidka_bez_vykresu_ne_500(self):
        S["db"].turntable_frames[int(KARTA)] = _frames()[KARTA]
        vso = S["vso"]
        puvodni = vso._read_vandr_image

        def cti(rel):
            if rel.endswith("_2d.png"):
                raise FileNotFoundError(2, "No such file", rel)
            return F.PNG1
        vso._read_vandr_image = cti
        try:
            stat, j = _post(KARTA)
        finally:
            vso._read_vandr_image = puvodni
        self.assertEqual(stat, 201, j)
        self.assertEqual(j["obrazky_zdroj"], {"narys": "chybi", "view3d": "vandr"})
        self.assertIn("soubor chybí na disku", j["poznamka"])
        self.assertIs(json.loads(S["db"].offers[-1]["offer_options"]).get("vandr_bez_vykresu"), True)

    def test_2d_vykres_se_nikdy_nevyrabi(self):
        """Robert 2026-10-06: Vandr 2D pohledy se nevyrabi, jen se prejimaji - kotovaci funkce se pri zalozeni nabidky vubec nevola (ani kdyz Vandr vykres nema)"""
        vk = S["vso"]._vykres_modul()
        puvodni = vk.vykres_nares
        volano = []
        vk.vykres_nares = lambda *a, **k: volano.append(1) or puvodni(*a, **k)
        try:
            S["vso"]._spust_artisan = F.artisan_bez_obrazku(KARTA)
            stat, j = _post(KARTA)
        finally:
            vk.vykres_nares = puvodni
        self.assertEqual(stat, 201, j)
        self.assertEqual(volano, [], "vykres_nares se nesmi volat - 2D se nevyrabi")
        self.assertEqual(j["obrazky_zdroj"]["narys"], "chybi")

    def test_s_vandr_vykresem_neni_priznak_bez_vykresu(self):
        S["db"].turntable_frames[int(KARTA)] = _frames()[KARTA]
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertEqual(j["obrazky_zdroj"]["narys"], "vandr")
        self.assertNotIn("vandr_bez_vykresu", json.loads(S["db"].offers[-1]["offer_options"]))
        self.assertEqual(_obrazky_nabidky(j["offer_id"])["narys"], F.PNG1)

    def test_400_zustava_jen_pro_vyjmenovane_pripady_obrazky_mezi_nimi_nejsou(self):
        S["vso"]._spust_artisan = F.artisan_bez_obrazku(KARTA)
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, "chybejici Vandr obrazky uz nejsou duvod ke 400")
        # parts uplne chybi (Vandr nema zadny dil)
        S["db"].offers.clear()

        def bez_dilu(argumenty, timeout_s):
            o = F.vandr_output(KARTA, "--v3d" in argumenty)
            o["parts"] = {}
            return F.Proc(0, json.dumps(o))
        S["vso"]._spust_artisan = bez_dilu
        stat, j = _post(KARTA)
        self.assertEqual(stat, 201, j)
        self.assertEqual(j["obrazky_zdroj"], {"narys": "chybi", "view3d": "nahrada"})


@unittest.skipUnless(BLENDER_OK, "Blender neni k dispozici")
class TestRealneKarty4053a4482(Base):
    """Robertovy karty: GLB z webapp/katalog/vandr, snimky otocky z webapp/content-files/turntable-frames, Vandr bez obrazku a bez
    v3d dat (jen FBX export) -> dosavadni staticky model + nahrada obrazku. Skutecny Blender (dosavadni krok), ~12 s na kartu."""
    KARTY = {"4053": ("VD-4d7c063e-77ae-4109-9a31-63e769e3f6b6", "vandr/vd_export_regalova_vestavba_peugeot_expert_l2_4d7c063e.glb", 90),
             "4482": ("VD-f543dc7a-04a0-4c9b-b3c7-a8c46a5bfd28", "vandr/vd_export_regalova_vestavba_vw_crafter_l3h3_fwd_f543dc7a.glb", 270)}

    def test_obe_karty(self):
        import test_vykres as TV
        for k, (sku, glb, front) in self.KARTY.items():
            with self.subTest(karta=k):
                if not os.path.isfile(os.path.join(CE.KATALOG, glb)):
                    self.skipTest("chybi katalogove GLB %s" % glb)
                reset()
                db = S["db"]
                db.pridej_vlastni_kartu(int(k), sku, glb, front)
                db.turntable_frames[int(k)] = _frames()[k]
                for r in _frames()[k]:
                    if not os.path.isfile(os.path.join(CE.CONTENT_FILES, r["filename"])):
                        self.skipTest("chybi snimek %s" % r["filename"])
                S["vso"]._spust_artisan = F.artisan_bez_obrazku(k)               # prazdne obrazky, vystup BEZ klice v3d
                t = time.time()
                stat, j = _post(k)
                self.assertLess(time.time() - t, 55)
                self.assertEqual(stat, 201, j)
                self.assertIs(j["v3d"], False)                                       # Vandr nema v3d data -> dosavadni staticky model
                self.assertIn("v3d", j["v3d_duvod"])
                self.assertEqual(j["obrazky_zdroj"], {"narys": "chybi", "view3d": "nahrada"})
                self.assertTrue(j["poznamka"].startswith("Vandr u karty nemá kótovaný 2D výkres"))
                im = _obrazky_nabidky(j["offer_id"])
                # 2D vykres se nevyrabi (Robert 2026-10-06): zastupny 1x1 PNG, nabidka bez stranky Vykresy
                self.assertEqual(_rozmer_obrazku(im["narys"]), (1, 1))
                self.assertIsNone(j["obrazky_rozmery_mm"])
                self.assertIs(json.loads(S["db"].offers[-1]["offer_options"]).get("vandr_bez_vykresu"), True)
                model = _stored_model(j["offer_id"])
                # 3D pohledy = snimky otocky (front +-35 -> 120/60 u 4053, 300/240 u 4482; elevace 0)
                a_az, b_az = {"4053": (120, 60), "4482": (300, 240)}[k]
                for slot, az in (("view3d_a", a_az), ("view3d_b", b_az)):
                    self.assertTrue(_je(im[slot], "jpeg"))
                    rows = [x for x in _frames()[k] if x["azimuth_deg"] == az and x["elevation_deg"] == 0 and x["bytes"] <= 1500 * 1024]
                    best = max(rows, key=lambda x: x["tier_px"])
                    with open(os.path.join(CE.CONTENT_FILES, best["filename"]), "rb") as fh:
                        self.assertEqual(im[slot], fh.read())
                _uloz_ukazku("%s_3d_pohled_a_zepredu_doprava" % k, im["view3d_a"], "jpg")
                _uloz_ukazku("%s_3d_pohled_b_zepredu_doleva" % k, im["view3d_b"], "jpg")
                _uloz_ukazku("%s_pohled_z_modelu_pro_srovnani" % k,
                             S["vso"]._vykres_modul().pohled_z_modelu(model, (front + 35) % 360, 17.5), "png")


if __name__ == "__main__":
    unittest.main(verbosity=2)
