#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermeticky test api/v3d_vzhled.py (vzhled online nabidek: HDRI, hlinik, AO; bot10, 2026-10-06).

  /opt/konfigurator/api/venv/bin/python scripts/2026-10-06_v3d_vzhled_testy/test_vzhled_api.py        (V3D_VZHLED_MODUL=<cesta> = kandidat, viz _mutace_vzhled.py)

SKUTECNY modul + skutecny Flask routing; atrapa: modul `app` (get_conn = slovnik app_settings v pameti, require_permission s prepinacem, log_audit zaznam), zadna DB, zadna sit.
Shoda klicu a mezi s prohlizecem (webapp/js/v3d/viewer3d.js) a s generatorem (api/stul_api.py) se kontroluje ze ZDROJOVYCH TEXTU - zmena v jednom a ne v druhem shodi test."""
import importlib.util
import json
import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MODUL = os.environ.get("V3D_VZHLED_MODUL") or os.path.join(REPO, "api", "v3d_vzhled.py")
sys.dont_write_bytecode = True
S = {}


class FakeCursor:
    def __init__(self, db):
        self.db, self._row = db, None

    def execute(self, sql, args=None):
        q = re.sub(r"\s+", " ", sql.strip())
        self.db.dotazy.append((q, args))
        if q == "SELECT setting_value FROM app_settings WHERE setting_key=%s":
            v = self.db.nastaveni.get(args[0])
            self._row = {"setting_value": v} if v is not None else None
        elif q == "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=%s":
            assert args[1] == args[2]
            self.db.nastaveni[args[0]] = args[1]
        elif q == "DELETE FROM app_settings WHERE setting_key=%s":
            self.db.nastaveni.pop(args[0], None)
        else:
            raise AssertionError("FakeDB: nepovoleny dotaz: " + q[:160])

    def fetchone(self):
        return self._row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return FakeCursor(self.db)

    def commit(self):
        self.db.commity += 1

    def close(self):
        pass


class FakeDB:
    def __init__(self):
        self.nastaveni, self.dotazy, self.commity = {}, [], 0


def setUpModule():
    from flask import Flask, jsonify
    db = FakeDB()
    appmod = types.ModuleType("app")
    appmod.app = Flask("vzhled_atrapa")
    appmod.get_conn = lambda: FakeConn(db)
    appmod.perm = {"ok": True, "volano": []}
    audit = []

    def require_permission(res, akce):
        def deko(fn):
            def w(*a, **k):
                appmod.perm["volano"].append((res, akce))
                if not appmod.perm["ok"]:
                    return jsonify({"error": "Nedostatecna opravneni.", "code": "forbidden"}), 403
                return fn(*a, **k)
            w.__name__ = fn.__name__
            return w
        return deko
    appmod.require_permission = require_permission
    appmod.current_user = lambda: {"id": 1, "username": "admin"}
    appmod.log_audit = lambda uid, action, et, eid=None, detail=None: audit.append({"uid": uid, "action": action, "et": et, "eid": eid, "detail": detail})
    sys.modules["app"] = appmod
    envmod = types.ModuleType("v3d_env_import")                  # doplnena HDRI ze Sdileneho disku (skutecny modul testuje scripts/2026-10-07_v3d_env_testy)
    S["extra"], S["extra_force"] = [], []
    envmod.extra_klice = lambda force=False: tuple(S["extra"]) + (tuple(S["extra_force"]) if force else ())
    envmod.public_extra = lambda: [{"key": k, "label": k.upper(), "mul0": 1.0, "rot0_deg": 0.0, "url": "/api/public/v3d-env/%s_1024.hdr" % k, "lo": "/api/public/v3d-env/%s_256.hdr" % k} for k in S["extra"]]
    sys.modules["v3d_env_import"] = envmod
    spec = importlib.util.spec_from_file_location("v3d_vzhled_pod_testem", MODUL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.TTL_S = 0.0                                   # test cte vzdy z "DB" (cache ma vlastni test)
    S.update(db=db, app=appmod, audit=audit, m=m)


def tearDownModule():
    sys.modules.pop("app", None)
    sys.modules.pop("v3d_env_import", None)


def klient():
    return S["app"].app.test_client()


def bez_extra(j):
    j = dict(j)
    j.pop("hdri_extra", None)
    return j


def verejny():
    """Verejny GET vzhledu bez hdri_extra (doplnena HDRI maji vlastni testy; stary modul ho nema)."""
    j = klient().get("/api/public/v3d-vzhled").get_json()
    j.pop("hdri_extra", None)
    return j


def reset():
    S["extra"], S["extra_force"] = [], []
    S["db"].nastaveni.clear()
    S["db"].dotazy.clear()
    S["db"].commity = 0
    S["audit"].clear()
    S["app"].perm.update(ok=True, volano=[])
    S["m"]._cache.update(t=0.0, v=None)
    S["m"].TTL_S = 0.0


def put(body, raw=None):
    c = klient()
    if raw is not None:
        return c.put("/api/admin/v3d-vzhled", data=raw, content_type="application/json")
    return c.put("/api/admin/v3d-vzhled", data=json.dumps(body), content_type="application/json")


ENV = {"hdri": "tv_studio", "strength": 0.8, "rot_deg": 45, "hemi": 0.3}


def D(**kw):
    """Ocekavany vzhled: vsechno vychozi (null) + zadane klice."""
    d = {"env": None, "alu": None, "ao": None, "sat": None, "barvy": None, "lesk": None, "ao_mat": None, "alu_cfg": None, "ao_cfg": None}
    d.update(kw)
    return d


class Base(unittest.TestCase):
    def setUp(self):
        reset()


class TestRouting(Base):
    def test_trasy(self):
        pravidla = {r.rule: sorted(r.methods - {"HEAD", "OPTIONS"}) for r in S["app"].app.url_map.iter_rules() if "vzhled" in r.rule}
        self.assertEqual(pravidla, {"/api/public/v3d-vzhled": ["GET"], "/api/admin/v3d-vzhled": ["PUT"]})

    def test_put_ma_opravneni_nastaveni_upravit(self):
        put({"alu": "satin"})
        self.assertEqual(S["app"].perm["volano"], [("nastaveni", "upravit")])


class TestCteni(Base):
    def test_vychozi(self):
        r = klient().get("/api/public/v3d-vzhled")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(bez_extra(r.get_json()), D())
        self.assertEqual(r.headers["Cache-Control"], "no-cache")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.mimetype, "application/json")

    def test_verejne_bez_opravneni(self):
        S["app"].perm["ok"] = False
        r = klient().get("/api/public/v3d-vzhled")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(S["app"].perm["volano"], [], "cteni nesmi vyzadovat opravneni")

    def test_poskozena_ulozena_hodnota_je_vychozi_a_neshodi(self):
        for spatne in ("{nejson", "[1,2]", '{"env": {"hdri": "neexistuje", "strength": 1, "rot_deg": 0, "hemi": 0}}', '{"alu": "zlaty"}', '{"cizi": 1}', "null", "42"):
            with self.subTest(hodnota=spatne):
                S["db"].nastaveni[S["m"].KLIC] = spatne
                S["m"]._cache.update(t=0.0, v=None)
                r = klient().get("/api/public/v3d-vzhled")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(bez_extra(r.get_json()), D())

    def test_db_vypadek_je_vychozi(self):
        puvodni = S["app"].get_conn
        def spadne():
            raise RuntimeError("DB neni")
        S["app"].get_conn = spadne
        S["m"].get_conn = spadne
        try:
            r = klient().get("/api/public/v3d-vzhled")
            self.assertEqual((r.status_code, bez_extra(r.get_json())), (200, D()))
        finally:
            S["app"].get_conn = puvodni
            S["m"].get_conn = puvodni

    def test_cache_ttl(self):
        S["m"].TTL_S = 1000.0
        put({"alu": "matny"})
        S["db"].nastaveni[S["m"].KLIC] = json.dumps({"env": None, "alu": "bez", "ao": None})      # zmena "mimo" (jiny worker)
        self.assertEqual(verejny()["alu"], "matny", "v ramci TTL se cte z cache")
        S["m"].TTL_S = 0.0
        self.assertEqual(verejny()["alu"], "bez", "po TTL se cte znovu z DB")


class TestZapis(Base):
    def test_plny_vzhled(self):
        r = put({"env": ENV, "alu": "satin", "ao": "stredni"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        ocek = D(env={"hdri": "tv_studio", "strength": 0.8, "rot_deg": 45.0, "hemi": 0.3}, alu="satin", ao="stredni")
        self.assertEqual(r.get_json(), ocek)
        self.assertEqual(json.loads(S["db"].nastaveni[S["m"].KLIC]), ocek)
        self.assertEqual(verejny(), ocek)
        self.assertGreaterEqual(S["db"].commity, 1)

    def test_jen_cast_a_zaokrouhleni(self):
        self.assertEqual(put({"alu": "eloxovany"}).get_json(), D(alu="eloxovany"))
        r = put({"env": {"hdri": "crossfit", "strength": 0.123456, "rot_deg": -12.3456, "hemi": 1.2}}).get_json()
        self.assertEqual(r["env"], {"hdri": "crossfit", "strength": 0.12, "rot_deg": -12.35, "hemi": 1.2})
        self.assertEqual(put({"ao": "vyp"}).get_json(), D(ao="vyp"), "zapis staveny od nuly z tela (chybejici klic = vychozi)")

    def test_sytost_a_barvy(self):
        r = put({"sat": 1.5, "barvy": {"#1E50FF": "#0A3AD0", "#FFFFFF": "#EEEEEE"}})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json(), D(sat=1.5, barvy={"#1e50ff": "#0a3ad0", "#ffffff": "#eeeeee"}), "hex se uklada malymi pismeny")
        self.assertEqual(json.loads(S["db"].nastaveni[S["m"].KLIC]), D(sat=1.5, barvy={"#1e50ff": "#0a3ad0", "#ffffff": "#eeeeee"}))
        self.assertEqual(verejny(), D(sat=1.5, barvy={"#1e50ff": "#0a3ad0", "#ffffff": "#eeeeee"}))
        self.assertEqual(put({"sat": 1.2349}).get_json(), D(sat=1.23), "zaokrouhleni na 2 mista")
        self.assertEqual(put({"sat": 1}).get_json(), D(), "sat 1 = beze zmeny = vychozi (null)")
        self.assertNotIn(S["m"].KLIC, S["db"].nastaveni, "jen sat 1 = vsechno vychozi -> radek se smaze")
        self.assertEqual(put({"sat": 0}).get_json(), D(sat=0.0), "0 = cernobile je platne")
        self.assertEqual(put({"sat": 2}).get_json(), D(sat=2.0))
        self.assertEqual(put({"barvy": {"#AABBCC": "#aabbcc"}}).get_json(), D(), "dvojice se stejnou barvou se zahodi")
        self.assertEqual(put({"barvy": {}}).get_json(), D(), "prazdne barvy = vychozi")
        r = put({"barvy": {"#%06x" % i: "#%06x" % (i + 1) for i in range(40)}})
        self.assertEqual((r.status_code, len(r.get_json()["barvy"])), (200, 40), "presne 40 dvojic je v poradku")
        self.assertEqual(put({"env": ENV, "alu": "matny", "ao": "jemne", "sat": 0.8, "barvy": {"#112233": "#445566"}}).get_json(),
                         D(env={"hdri": "tv_studio", "strength": 0.8, "rot_deg": 45.0, "hemi": 0.3}, alu="matny", ao="jemne", sat=0.8, barvy={"#112233": "#445566"}))

    def test_stary_ulozeny_radek_bez_sat_a_barev_se_cte(self):
        S["db"].nastaveni[S["m"].KLIC] = json.dumps({"env": None, "alu": "satin", "ao": "jemne"})
        S["m"]._cache.update(t=0.0, v=None)
        self.assertEqual(verejny(), D(alu="satin", ao="jemne"))

    def test_lesk_hlinik_ao(self):
        r = put({"lesk": {"#1E50FF": 0.5, "#FFFFFF": 1.0, "#000000": 2}, "alu_cfg": {"refl": 0.6, "rough": 1.4}, "ao_cfg": {"k": 1.5, "r": 2}})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        ocek = D(lesk={"#1e50ff": 0.5, "#000000": 2.0}, alu_cfg={"refl": 0.6, "rough": 1.4, "ao": 1.0}, ao_cfg={"k": 1.5, "r": 2.0})
        self.assertEqual(r.get_json(), ocek, "hex male, lesk 1 se zahodi")
        self.assertEqual(json.loads(S["db"].nastaveni[S["m"].KLIC]), ocek)
        self.assertEqual(verejny(), ocek)
        self.assertEqual(put({"alu_cfg": {"refl": 0.5}}).get_json(), D(alu_cfg={"refl": 0.5, "rough": 1.0, "ao": 1.0}), "chybejici klic = 1")
        self.assertEqual(put({"ao_cfg": {"r": 0.25}}).get_json(), D(ao_cfg={"k": 1.0, "r": 0.25}))
        self.assertEqual(put({"alu_cfg": {"refl": 1, "rough": 1}, "ao_cfg": {"k": 1, "r": 1}, "lesk": {"#112233": 1}}).get_json(), D(), "same 1 = vychozi (null)")
        self.assertNotIn(S["m"].KLIC, S["db"].nastaveni, "same vychozi -> radek se smaze")
        self.assertEqual(put({"lesk": {}}).get_json(), D(), "prazdny lesk = vychozi")
        self.assertEqual(put({"lesk": {"#112233": 1.2349}}).get_json(), D(lesk={"#112233": 1.23}), "zaokrouhleni na 2 mista")
        r = put({"lesk": {"#%06x" % i: 0.5 for i in range(40)}})
        self.assertEqual((r.status_code, len(r.get_json()["lesk"])), (200, 40), "presne 40 materialu je v poradku")
        for body, ocekavano in (({"lesk": {"#112233": 0}}, D(lesk={"#112233": 0.0})), ({"lesk": {"#112233": 2}}, D(lesk={"#112233": 2.0})),
                                ({"alu_cfg": {"refl": 0, "rough": 0.5}}, D(alu_cfg={"refl": 0.0, "rough": 0.5, "ao": 1.0})), ({"alu_cfg": {"refl": 1.5, "rough": 2}}, D(alu_cfg={"refl": 1.5, "rough": 2.0, "ao": 1.0})),
                                ({"ao_cfg": {"k": 0, "r": 3}}, D(ao_cfg={"k": 0.0, "r": 3.0})), ({"ao_cfg": {"k": 2, "r": 0.25}}, D(ao_cfg={"k": 2.0, "r": 0.25}))):
            with self.subTest(body=body):
                self.assertEqual(put(body).get_json(), ocekavano, "meze jsou platne hodnoty")
        self.assertEqual(put({"env": ENV, "alu": "matny", "ao": "jemne", "sat": 0.8, "barvy": {"#112233": "#445566"}, "lesk": {"#112233": 0.4}, "alu_cfg": {"refl": 0.7}, "ao_cfg": {"k": 0.5}}).get_json(),
                         D(env={"hdri": "tv_studio", "strength": 0.8, "rot_deg": 45.0, "hemi": 0.3}, alu="matny", ao="jemne", sat=0.8, barvy={"#112233": "#445566"}, lesk={"#112233": 0.4}, alu_cfg={"refl": 0.7, "rough": 1.0, "ao": 1.0}, ao_cfg={"k": 0.5, "r": 1.0}))

    def test_ao_po_komponentech(self):
        """Robert 2026-10-07 ("nenasel jsem AO pro jednotlive komponenty"): ao_mat {"#puvodni": vaha AO 0-2} + alu_cfg.ao (vaha AO hliniku 0-2)."""
        r = put({"ao_mat": {"#1E50FF": 0.5, "#FFFFFF": 1.0, "#000000": 2}, "alu_cfg": {"ao": 0.3}})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        ocek = D(ao_mat={"#1e50ff": 0.5, "#000000": 2.0}, alu_cfg={"refl": 1.0, "rough": 1.0, "ao": 0.3})
        self.assertEqual(r.get_json(), ocek, "hex male, vaha 1 se zahodi, alu_cfg dostane chybejici klice = 1")
        self.assertEqual(json.loads(S["db"].nastaveni[S["m"].KLIC]), ocek)
        self.assertEqual(verejny(), ocek)
        self.assertEqual(put({"alu_cfg": {"refl": 1, "rough": 1, "ao": 1}, "ao_mat": {"#112233": 1}}).get_json(), D(), "same 1 = vychozi (null)")
        self.assertNotIn(S["m"].KLIC, S["db"].nastaveni)
        self.assertEqual(put({"ao_mat": {}}).get_json(), D(), "prazdny ao_mat = vychozi")
        self.assertEqual(put({"ao_mat": {"#112233": 0.12345}}).get_json(), D(ao_mat={"#112233": 0.12}), "zaokrouhleni na 2 mista")
        for body, ocekavano in (({"ao_mat": {"#112233": 0}}, D(ao_mat={"#112233": 0.0})), ({"ao_mat": {"#112233": 2}}, D(ao_mat={"#112233": 2.0})),
                                ({"alu_cfg": {"ao": 0}}, D(alu_cfg={"refl": 1.0, "rough": 1.0, "ao": 0.0})), ({"alu_cfg": {"ao": 2}}, D(alu_cfg={"refl": 1.0, "rough": 1.0, "ao": 2.0}))):
            with self.subTest(body=body):
                self.assertEqual(put(body).get_json(), ocekavano, "meze jsou platne hodnoty")
        r = put({"ao_mat": {"#%06x" % i: 0.5 for i in range(40)}})
        self.assertEqual((r.status_code, len(r.get_json()["ao_mat"])), (200, 40), "presne 40 materialu je v poradku")
        # lesk a AO jsou na sobe nezavisle (stejny hex smi mit oboje)
        self.assertEqual(put({"lesk": {"#112233": 0.4}, "ao_mat": {"#112233": 1.5}}).get_json(), D(lesk={"#112233": 0.4}, ao_mat={"#112233": 1.5}))
        # stary ulozeny radek bez ao_mat / s alu_cfg bez ao se cte (alu_cfg.ao = 1, ao_mat = null)
        S["db"].nastaveni[S["m"].KLIC] = json.dumps({"env": None, "alu": None, "ao": "stredni", "alu_cfg": {"refl": 0.5, "rough": 1.5}, "lesk": {"#112233": 0.4}})
        S["m"]._cache.update(t=0.0, v=None)
        self.assertEqual(verejny(), D(ao="stredni", alu_cfg={"refl": 0.5, "rough": 1.5, "ao": 1.0}, lesk={"#112233": 0.4}))

    def test_hdri_extra_ve_verejnem_get(self):
        j = klient().get("/api/public/v3d-vzhled").get_json()
        self.assertEqual(j["hdri_extra"], [])
        S["extra"] = ["sky", "cloud"]
        j = klient().get("/api/public/v3d-vzhled").get_json()
        self.assertEqual([h["key"] for h in j["hdri_extra"]], ["sky", "cloud"])
        self.assertEqual(set(j["hdri_extra"][0]), {"key", "label", "mul0", "rot0_deg", "url", "lo"})
        self.assertEqual(j["hdri_extra"][0]["url"], "/api/public/v3d-env/sky_1024.hdr")
        self.assertEqual({k: v for k, v in j.items() if k != "hdri_extra"}, D(), "ostatni pole beze zmeny")
        self.assertNotIn("hdri_extra", put({"alu": "satin"}).get_json(), "odpoved PUT hdri_extra nenese")
        self.assertEqual(put({"hdri_extra": []}).status_code, 400, "hdri_extra se nikdy nezapisuje")

    def test_env_hdri_z_doplnenych(self):
        env = lambda k: {"env": {"hdri": k, "strength": 1, "rot_deg": 0, "hemi": 0}}
        r = put(env("sky"))
        self.assertEqual(r.status_code, 400, "klic, ktery nikdo nedoplnil")
        self.assertIn("crossfit", r.get_json()["error"])
        S["extra"] = ["sky"]
        r = put(env("sky"))
        self.assertEqual((r.status_code, r.get_json()["env"]["hdri"]), (200, "sky"))
        self.assertEqual(verejny()["env"]["hdri"], "sky", "ulozeny vzhled s doplnenym klicem se cte")
        self.assertIn("sky", put(env("nic")).get_json()["error"], "hlaska nabizi i doplnene klice")
        S["extra"] = []
        S["extra_force"] = ["pozde"]
        self.assertEqual(put(env("pozde")).status_code, 200, "klic, ktery cache tohoto workeru jeste nezna, se overi znovu s force")
        self.assertEqual(put(env("Sky")).status_code, 400, "velikost pismen")

    def test_ulozeny_vzhled_s_odstranenym_klicem_je_vychozi_a_neshodi(self):
        S["extra"] = ["sky"]
        put({"env": {"hdri": "sky", "strength": 1, "rot_deg": 0, "hemi": 0}, "alu": "satin"})
        S["extra"] = []
        S["m"]._cache.update(t=0.0, v=None)
        self.assertEqual(verejny(), D(), "poskozeny / nevalidni ulozeny vzhled = vychozi (stejne pravidlo jako u ostatnich poskozeni)")

    def test_stary_radek_s_barvami_ale_bez_lesku_se_cte(self):
        S["db"].nastaveni[S["m"].KLIC] = json.dumps({"env": None, "alu": "satin", "ao": "jemne", "sat": 1.4, "barvy": {"#112233": "#445566"}})
        S["m"]._cache.update(t=0.0, v=None)
        self.assertEqual(verejny(), D(alu="satin", ao="jemne", sat=1.4, barvy={"#112233": "#445566"}))

    def test_meze_jsou_platne_hodnoty(self):
        for env in ({"hdri": "mistnost", "strength": 0.1, "rot_deg": -180, "hemi": 0}, {"hdri": "teufelsberg", "strength": 3, "rot_deg": 180, "hemi": 1.2}):
            with self.subTest(env=env):
                self.assertEqual(put({"env": env}).status_code, 200)

    def test_null_vrati_vychozi_a_smaze_radek(self):
        put({"env": ENV, "alu": "satin"})
        self.assertIn(S["m"].KLIC, S["db"].nastaveni)
        r = put(None, raw="null")
        self.assertEqual((r.status_code, r.get_json()), (200, D()))
        self.assertNotIn(S["m"].KLIC, S["db"].nastaveni)
        r = put({"env": None, "alu": None, "ao": None})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(S["m"].KLIC, S["db"].nastaveni, "same null = taky smazat, ne ukladat prazdny objekt")

    def test_odmitnute_hodnoty(self):
        nan = '{"env": {"hdri": "crossfit", "strength": NaN, "rot_deg": 0, "hemi": 0}}'
        pripady = [
            ("env neexistujici hdri", {"env": dict(ENV, hdri="neexistuje")}), ("env bez hdri", {"env": {"strength": 1, "rot_deg": 0, "hemi": 0}}),
            ("strength moc male", {"env": dict(ENV, strength=0.05)}), ("strength moc velke", {"env": dict(ENV, strength=3.01)}),
            ("rot_deg mimo", {"env": dict(ENV, rot_deg=181)}), ("rot_deg mimo zaporne", {"env": dict(ENV, rot_deg=-180.5)}),
            ("hemi mimo", {"env": dict(ENV, hemi=1.21)}), ("hemi zaporne", {"env": dict(ENV, hemi=-0.01)}),
            ("strength text", {"env": dict(ENV, strength="0.8")}), ("strength bool", {"env": dict(ENV, strength=True)}), ("strength null", {"env": dict(ENV, strength=None)}),
            ("chybi hemi", {"env": {"hdri": "crossfit", "strength": 1, "rot_deg": 0}}), ("env cizi klic", {"env": dict(ENV, jas=1)}),
            ("env neni objekt", {"env": "crossfit"}), ("env seznam", {"env": [ENV]}),
            ("alu neznamy", {"alu": "zlaty"}), ("alu cislo", {"alu": 1}), ("alu seznam", {"alu": ["satin"]}), ("alu prazdny retezec", {"alu": ""}),
            ("ao neznamy", {"ao": "extra"}), ("ao bool", {"ao": True}),
            ("sat zaporna", {"sat": -0.01}), ("sat nad 2", {"sat": 2.01}), ("sat text", {"sat": "1.5"}), ("sat bool", {"sat": True}), ("sat seznam", {"sat": [1]}),
            ("lesk nad 2", {"lesk": {"#112233": 2.01}}), ("lesk zaporny", {"lesk": {"#112233": -0.1}}), ("lesk text", {"lesk": {"#112233": "1"}}), ("lesk bool", {"lesk": {"#112233": True}}), ("lesk null hodnota", {"lesk": {"#112233": None}}),
            ("lesk klic kratky hex", {"lesk": {"#123": 1.5}}), ("lesk klic bez #", {"lesk": {"112233": 1.5}}), ("lesk seznam", {"lesk": [1]}), ("lesk text misto objektu", {"lesk": "1"}),
            ("lesk 41 materialu", {"lesk": {"#%06x" % i: 0.5 for i in range(41)}}),
            ("alu_cfg refl nad meze", {"alu_cfg": {"refl": 1.51}}), ("alu_cfg refl zaporne", {"alu_cfg": {"refl": -0.1}}), ("alu_cfg rough pod meze", {"alu_cfg": {"rough": 0.49}}), ("alu_cfg rough nad meze", {"alu_cfg": {"rough": 2.01}}),
            ("alu_cfg cizi klic", {"alu_cfg": {"refl": 1, "lesk": 1}}), ("alu_cfg text", {"alu_cfg": {"refl": "1"}}), ("alu_cfg bool", {"alu_cfg": {"rough": True}}), ("alu_cfg neni objekt", {"alu_cfg": 1}), ("alu_cfg seznam", {"alu_cfg": [1, 1]}),
            ("ao_cfg k nad meze", {"ao_cfg": {"k": 2.01}}), ("ao_cfg k zaporne", {"ao_cfg": {"k": -0.1}}), ("ao_cfg r pod meze", {"ao_cfg": {"r": 0.24}}), ("ao_cfg r nad meze", {"ao_cfg": {"r": 3.01}}),
            ("ao_cfg cizi klic", {"ao_cfg": {"k": 1, "bias": 0.1}}), ("ao_cfg null hodnota", {"ao_cfg": {"k": None}}), ("ao_cfg neni objekt", {"ao_cfg": "silne"}), ("ao_cfg seznam", {"ao_cfg": [1]}),
            ("ao_mat nad 2", {"ao_mat": {"#112233": 2.01}}), ("ao_mat zaporna", {"ao_mat": {"#112233": -0.1}}), ("ao_mat text", {"ao_mat": {"#112233": "1"}}), ("ao_mat bool", {"ao_mat": {"#112233": True}}), ("ao_mat null hodnota", {"ao_mat": {"#112233": None}}),
            ("ao_mat klic kratky hex", {"ao_mat": {"#123": 1.5}}), ("ao_mat klic bez #", {"ao_mat": {"112233": 1.5}}), ("ao_mat seznam", {"ao_mat": [1]}), ("ao_mat text misto objektu", {"ao_mat": "1"}), ("ao_mat 41 materialu", {"ao_mat": {"#%06x" % i: 0.5 for i in range(41)}}),
            ("alu_cfg ao nad meze", {"alu_cfg": {"ao": 2.01}}), ("alu_cfg ao zaporne", {"alu_cfg": {"ao": -0.1}}), ("alu_cfg ao text", {"alu_cfg": {"ao": "1"}}), ("alu_cfg ao bool", {"alu_cfg": {"ao": True}}), ("alu_cfg ao null", {"alu_cfg": {"ao": None}}),
            ("barvy seznam", {"barvy": [["#112233", "#445566"]]}), ("barvy text", {"barvy": "#112233"}), ("barvy klic bez #", {"barvy": {"112233": "#445566"}}), ("barvy kratky hex", {"barvy": {"#123": "#445566"}}),
            ("barvy neplatny znak", {"barvy": {"#11223g": "#445566"}}), ("barvy hodnota cislo", {"barvy": {"#112233": 5}}), ("barvy hodnota objekt", {"barvy": {"#112233": {"a": 1}}}),
            ("barvy nazev barvy", {"barvy": {"#112233": "red"}}), ("barvy 41 dvojic", {"barvy": {"#%06x" % i: "#%06x" % (i + 1) for i in range(41)}}), ("barvy alfa 8 znaku", {"barvy": {"#11223344": "#445566"}}), ("cizi klic nahore", {"material": "x"}), ("cizi klic vedle platnych", {"alu": "satin", "extra": 1}),
        ]
        for nazev, body in pripady:
            with self.subTest(case=nazev):
                S["db"].nastaveni.clear(); S["audit"].clear()
                r = put(body)
                self.assertEqual(r.status_code, 400, (nazev, r.get_data(as_text=True)))
                self.assertIn("error", r.get_json())
                self.assertEqual(S["db"].nastaveni, {}, "nic se nesmi ulozit")
                self.assertEqual(S["audit"], [], "chyba se nezapisuje do auditu")
        for nazev, raw in (("NaN v JSON", nan), ("nejson", "{nejson"), ("seznam", "[1]"), ("cislo", "42"), ("retezec", '"satin"'), ("prazdne telo", ""), ("true", "true")):
            with self.subTest(case=nazev):
                r = put(None, raw=raw)
                self.assertEqual(r.status_code, 400, (nazev, r.get_data(as_text=True)))
                self.assertEqual(S["db"].nastaveni, {})

    def test_opravneni_bez_prava_nic_neulozi(self):
        S["app"].perm["ok"] = False
        r = put({"alu": "satin"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(S["db"].nastaveni, {})
        self.assertEqual(S["audit"], [])
        self.assertFalse([q for q, _ in S["db"].dotazy if not q.startswith("SELECT")], "bez prava zadny zapis do DB")

    def test_audit(self):
        put({"alu": "satin", "ao": "silne"})
        self.assertEqual(len(S["audit"]), 1)
        a = S["audit"][0]
        self.assertEqual((a["uid"], a["action"], a["et"]), (1, "update", "v3d_vzhled"))
        self.assertEqual(a["detail"], {"vzhled": D(alu="satin", ao="silne")})

    def test_zapisuje_jen_do_sveho_klice(self):
        put({"env": ENV, "alu": "satin", "ao": "jemne"})
        put(None, raw="null")
        zapisy = [(q, a) for q, a in S["db"].dotazy if not q.startswith("SELECT")]
        self.assertTrue(zapisy)
        self.assertTrue(all(a[0] == "v3d_nabidka_vzhled" for q, a in zapisy), zapisy)


class TestShodaSVieweremAGeneratorem(Base):
    """Klice a meze ze ZDROJOVYCH textu prohlizece a generatoru (zmena na jednom miste bez druheho shodi test)."""

    @classmethod
    def setUpClass(cls):
        cls.viewer = open(os.environ.get("VIEWER_JS") or os.path.join(REPO, "webapp/js/v3d/viewer3d.js"), encoding="utf-8").read()          # kandidat: VIEWER_JS=<viewer3d.js>
        cls.stul = open(os.path.join(REPO, "api/stul_api.py"), encoding="utf-8").read()

    def klice(self, nazev_pole):
        m = re.search(r"var %s = \[(.*?)\n\s*\];" % nazev_pole, self.viewer, re.S)
        self.assertTrue(m, nazev_pole)
        return tuple(re.findall(r"key: '([a-z_0-9]+)'", m.group(1)))

    def test_meze_materialu_jako_v_prohlizeci(self):
        m = re.search(r"var MAT_SAT_MAX = ([0-9.]+), MAT_COLORS_MAX = (\d+);", self.viewer)
        self.assertIsNotNone(m, "viewer3d.js: chybi var MAT_SAT_MAX = ..., MAT_COLORS_MAX = ...;")
        self.assertEqual((float(m.group(1)), int(m.group(2))), (S["m"].SAT_MEZE[1], S["m"].BARVY_MAX))
        self.assertEqual(S["m"].SAT_MEZE[0], 0.0)

    def test_meze_lesku_hliniku_a_ao_jako_v_prohlizeci(self):
        m = re.search(r"var GLOSS_MAX = ([0-9.]+);", self.viewer)
        self.assertIsNotNone(m, "viewer3d.js: chybi var GLOSS_MAX = ...;")
        self.assertEqual((0.0, float(m.group(1))), S["m"].LESK_MEZE)
        m = re.search(r"var ALU_REFL_MAX = ([0-9.]+), ALU_ROUGH_MIN = ([0-9.]+), ALU_ROUGH_MAX = ([0-9.]+);", self.viewer)
        self.assertIsNotNone(m, "viewer3d.js: chybi var ALU_REFL_MAX = ..., ALU_ROUGH_MIN = ..., ALU_ROUGH_MAX = ...;")
        ao_max = re.search(r"var AO_MAT_MAX = ([0-9.]+);", self.viewer)
        self.assertIsNotNone(ao_max, "viewer3d.js: chybi var AO_MAT_MAX = ...;")
        self.assertEqual({"refl": (0.0, float(m.group(1))), "rough": (float(m.group(2)), float(m.group(3))), "ao": (0.0, float(ao_max.group(1)))}, S["m"].ALU_CFG_MEZE)
        self.assertEqual((0.0, float(ao_max.group(1))), S["m"].AO_MAT_MEZE)
        m = re.search(r"var AO_K_MAX = ([0-9.]+), AO_R_MIN = ([0-9.]+), AO_R_MAX = ([0-9.]+);", self.viewer)
        self.assertIsNotNone(m, "viewer3d.js: chybi var AO_K_MAX = ..., AO_R_MIN = ..., AO_R_MAX = ...;")
        self.assertEqual({"k": (0.0, float(m.group(1))), "r": (float(m.group(2)), float(m.group(3)))}, S["m"].AO_CFG_MEZE)

    def test_hlinik(self):
        self.assertEqual(self.klice("ALU_VARIANTS"), S["m"].ALU)

    def test_ao(self):
        self.assertEqual(self.klice("AO_VARIANTS"), S["m"].AO)

    def test_hdri(self):
        lib = self.klice("HDRI_LIBRARY")
        self.assertEqual(lib + ("mistnost",), S["m"].ENV_HDRI)

    def test_meze_prostredi_jako_v_prohlizeci(self):
        self.assertIn("num(c.strength, 0.6, 0.1, 3)", self.viewer)
        self.assertIn("num(c.hemi, 0, 0, 1.2)", self.viewer)
        self.assertEqual(S["m"].ENV_MEZE, {"strength": (0.1, 3.0), "rot_deg": (-180.0, 180.0), "hemi": (0.0, 1.2)})

    def test_shodne_s_generatorem_stolu(self):
        m = re.search(r'ENV_HDRI = \(([^)]*)\)', self.stul)
        self.assertTrue(m)
        self.assertEqual(tuple(re.findall(r'"([a-z_]+)"', m.group(1))), S["m"].ENV_HDRI)
        m = re.search(r'ENV_MEZE = (\{[^}]*\})', self.stul)
        self.assertTrue(m)
        self.assertEqual(eval(m.group(1)), S["m"].ENV_MEZE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
