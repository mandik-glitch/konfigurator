#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermeticky test doplneni HDRI ze Sdileneho disku (api/v3d_env_import.py + api/v3d_env_prevod.py; bot10, 2026-10-07; Robert: "moznost pridat dalsi hdri ze sdileneho disku").

  /opt/konfigurator/api/venv/bin/python scripts/2026-10-07_v3d_env_testy/test_env_import_api.py        (V3D_ENV_DIR=<slozka s v3d_env_import.py a v3d_env_prevod.py> = kandidat)

SKUTECNE moduly + skutecny Flask routing + SKUTECNY prevod v podprocesu (syntetice HDRI 2048x1024 vyrobena zapisovacem z v3d_env_prevod); atrapy: modul `app` (get_conn = slovnik app_settings +
tabulky Sdileneho disku v pameti, require_permission s prepinacem, current_user, log_audit zaznam), `quotes` (PRIVATE_FILES_DIR = tmp), `drive` (DRIVE_FILES_DIR = tmp, pristup ke slozkam
podle testu). Zadna DB, zadna sit, nic mimo tmp. Shoda s api/render_hdri.py (zakazana HDRI) a s api/v3d_vzhled.py (vestavena HDRI) se kontroluje ze ZDROJOVYCH TEXTU."""
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
KAND = os.environ.get("V3D_ENV_DIR") or os.path.join(REPO, "api")
sys.dont_write_bytecode = True
S = {}


class FakeCursor:
    def __init__(self, db):
        self.db, self._rows = db, []

    def execute(self, sql, args=None):
        q = re.sub(r"\s+", " ", sql.strip())
        self.db.dotazy.append((q, args))
        if q == "SELECT setting_value FROM app_settings WHERE setting_key=%s":
            v = self.db.nastaveni.get(args[0])
            self._rows = [{"setting_value": v}] if v is not None else []
        elif q == "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=%s":
            assert args[1] == args[2]
            if self.db.padni_zapis:
                raise RuntimeError("DB zapis selhal")
            self.db.nastaveni[args[0]] = args[1]
        elif q == "DELETE FROM app_settings WHERE setting_key=%s":
            self.db.nastaveni.pop(args[0], None)
        elif q == "SELECT id, filename, folder_id, size_bytes FROM shared_drive_files ORDER BY filename":
            self._rows = sorted(({k: r[k] for k in ("id", "filename", "folder_id", "size_bytes")} for r in self.db.soubory), key=lambda r: r["filename"])
        elif q == "SELECT id, filename, stored_filename, folder_id, size_bytes FROM shared_drive_files WHERE id=%s":
            self._rows = [dict(r) for r in self.db.soubory if r["id"] == args[0]]
        elif q == "SELECT name, parent_folder_id FROM shared_drive_folders WHERE id=%s":
            self._rows = [{"name": self.db.slozky[args[0]][0], "parent_folder_id": self.db.slozky[args[0]][1]}] if args[0] in self.db.slozky else []
        else:
            raise AssertionError("FakeDB: nepovoleny dotaz: " + q[:160])

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

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
        self.nastaveni, self.dotazy, self.commity, self.padni_zapis = {}, [], 0, False
        self.soubory, self.slozky = [], {1: ("Rendering", None), 2: ("HDRi", 1), 3: ("Tajne", None)}


def setUpModule():
    tmp = tempfile.mkdtemp(prefix="env_import_test_")
    S["tmp"] = tmp
    S["priv"], S["drive"] = os.path.join(tmp, "private"), os.path.join(tmp, "private", "shared-drive")
    os.makedirs(S["drive"])
    db = FakeDB()
    S["db"] = db
    from flask import Flask, jsonify
    flask_app = Flask("fake")
    audit, perm = [], {"ok": True, "volano": [], "user": {"id": 7, "role": "admin", "active": True}}

    def require_permission(section, action):
        def deco(fn):
            import functools

            @functools.wraps(fn)
            def w(*a, **k):
                perm["volano"].append((section, action))
                if not perm["ok"]:
                    return jsonify({"error": "Nemate opravneni k teto akci.", "code": "forbidden"}), 403
                return fn(*a, **k)
            return w
        return deco

    appmod = types.ModuleType("app")
    appmod.app, appmod.get_conn = flask_app, lambda: FakeConn(db)
    appmod.require_permission, appmod.current_user = require_permission, lambda: perm["user"]
    appmod.log_audit = lambda uid, akce, typ, eid=None, detail=None: audit.append((uid, akce, typ, eid, detail))
    quotes = types.ModuleType("quotes")
    quotes.PRIVATE_FILES_DIR = S["priv"]
    drive = types.ModuleType("drive")
    drive.DRIVE_FILES_DIR = S["drive"]
    zakazane_slozky = {3}
    drive._user_can_access_folder = lambda cur, user, folder_id: folder_id not in zakazane_slozky or user["role"] == "admin"
    sys.modules.update(app=appmod, quotes=quotes, drive=drive)
    sys.path.insert(0, KAND)
    spec = importlib.util.spec_from_file_location("v3d_env_import_pod_testem", os.path.join(KAND, "v3d_env_import.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.REF_HDRI = os.path.join(REPO, "webapp", "js", "v3d", "env", "crossfit_1024.hdr")
    m.TTL_S = 0.0
    spec2 = importlib.util.spec_from_file_location("v3d_env_prevod_pod_testem", os.path.join(KAND, "v3d_env_prevod.py"))
    prevod = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(prevod)
    S.update(app=appmod, audit=audit, perm=perm, m=m, prevod=prevod, zakazane_slozky=zakazane_slozky)
    import numpy as np
    rng = np.random.default_rng(7)
    rgb = (rng.random((1024, 2048, 3), dtype=np.float32) * 0.8).astype(np.float32)
    rgb[100:120, 300:330] = 800.0
    S["syn"] = os.path.join(tmp, "syn_2048.hdr")
    prevod.write_rgbe(S["syn"], rgb)


def tearDownModule():
    for k in ("app", "quotes", "drive"):
        sys.modules.pop(k, None)
    if KAND in sys.path:
        sys.path.remove(KAND)
    shutil.rmtree(S["tmp"], ignore_errors=True)


def klient():
    return S["app"].app.test_client()


def pridej_soubor(fid, filename, folder=2, obsah=None, stored=None, velikost=None):
    """Zaradi soubor do atrapy Sdileneho disku; obsah None = syntetice HDRI."""
    stored = stored or ("stored_%d.bin" % fid)
    cesta = os.path.join(S["drive"], os.path.basename(stored))
    if obsah is None:
        shutil.copy(S["syn"], cesta)
    elif obsah is not False:
        open(cesta, "wb").write(obsah)
    S["db"].soubory.append({"id": fid, "filename": filename, "stored_filename": stored, "folder_id": folder, "size_bytes": velikost if velikost is not None else (os.path.getsize(cesta) if os.path.exists(cesta) else 0)})


def reset():
    m = S["m"]
    S["db"].nastaveni.clear(); S["db"].dotazy.clear(); S["db"].soubory.clear(); S["db"].commity = 0; S["db"].padni_zapis = False
    S["audit"].clear()
    S["perm"].update(ok=True, volano=[], user={"id": 7, "role": "admin", "active": True})
    for f in os.listdir(m.ENV_DIR):
        p = os.path.join(m.ENV_DIR, f)
        shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
    for f in os.listdir(S["drive"]):
        os.remove(os.path.join(S["drive"], f))
    m._cache.update(t=0.0, v=None)
    m.MAX_EXTRA, m.ZDROJ_MAX_B, m.TIMEOUT_S = 12, 150 * 1024 * 1024, 50


def post(body, raw=None):
    c = klient()
    if raw is not None:
        return c.post("/api/admin/v3d-env/import", data=raw, content_type="application/json")
    return c.post("/api/admin/v3d-env/import", data=json.dumps(body), content_type="application/json")


def zbytky():
    m = S["m"]
    return sorted(f for f in os.listdir(m.ENV_DIR) if f != ".import.lock")


class Base(unittest.TestCase):
    def setUp(self):
        reset()


class TestRouting(Base):
    def test_trasy(self):
        pravidla = {(r.rule, tuple(sorted(r.methods - {"HEAD", "OPTIONS"}))) for r in S["app"].app.url_map.iter_rules()}
        for r in (("/api/admin/v3d-env/zdroje", ("GET",)), ("/api/admin/v3d-env/import", ("POST",)), ("/api/admin/v3d-env/<klic>", ("DELETE",)), ("/api/public/v3d-env/<fname>", ("GET",))):
            self.assertIn(r, pravidla)

    def test_admin_trasy_maji_opravneni_nastaveni_upravit(self):
        klient().get("/api/admin/v3d-env/zdroje"); post({"file_id": 1}); klient().delete("/api/admin/v3d-env/neco")
        self.assertEqual(S["perm"]["volano"], [("nastaveni", "upravit")] * 3)

    def test_bez_opravneni_nic_nedela(self):
        pridej_soubor(1, "sky_4k.hdr")
        S["perm"]["ok"] = False
        for r in (klient().get("/api/admin/v3d-env/zdroje"), post({"file_id": 1}), klient().delete("/api/admin/v3d-env/neco")):
            self.assertEqual(r.status_code, 403)
        self.assertEqual(S["db"].nastaveni, {})
        self.assertEqual(zbytky(), [])

    def test_verejny_soubor_nema_opravneni(self):
        klient().get("/api/public/v3d-env/neco_1024.hdr")
        self.assertEqual(S["perm"]["volano"], [])


class TestZdroje(Base):
    def test_vypis(self):
        pridej_soubor(1, "Old_Hall_4k.hdr"); pridej_soubor(2, "crossfit_gym_2k.exr", obsah=b"x"); pridej_soubor(3, "render.jpg", obsah=b"x"); pridej_soubor(4, "modern_buildings_4k.hdr")
        pridej_soubor(5, "Tajny_8k.hdr", folder=3); pridej_soubor(6, "obri_16k.hdr", velikost=400 * 1024 * 1024); pridej_soubor(7, "BEZ_PRIPONY", obsah=b"x")
        j = klient().get("/api/admin/v3d-env/zdroje").get_json()
        nazvy = [z["filename"] for z in j["zdroje"]]
        self.assertEqual(nazvy, ["Old_Hall_4k.hdr", "Tajny_8k.hdr", "obri_16k.hdr"], "jen .hdr, bez zakazane HDRI; admin vidi i tajnou slozku")
        z = {z["filename"]: z for z in j["zdroje"]}
        self.assertEqual((z["Old_Hall_4k.hdr"]["folder"], z["Old_Hall_4k.hdr"]["navrh_label"], z["Old_Hall_4k.hdr"]["moc_velke"]), ("Rendering / HDRi", "Old hall", False))
        self.assertTrue(z["obri_16k.hdr"]["moc_velke"])
        self.assertEqual((j["max"], j["pocet"], j["extra"]), (12, 0, []))

    def test_uzivatel_bez_pristupu_ke_slozce_ji_nevidi(self):
        pridej_soubor(1, "Old_Hall_4k.hdr"); pridej_soubor(5, "Tajny_8k.hdr", folder=3)
        S["perm"]["user"] = {"id": 8, "role": "obchodnik", "active": True}
        self.assertEqual([z["filename"] for z in klient().get("/api/admin/v3d-env/zdroje").get_json()["zdroje"]], ["Old_Hall_4k.hdr"])

    def test_uz_doplnene_se_nenabizi_znovu(self):
        pridej_soubor(1, "Old_Hall_4k.hdr"); pridej_soubor(2, "sky_2k.hdr")
        self.assertEqual(post({"file_id": 1}).status_code, 200)
        j = klient().get("/api/admin/v3d-env/zdroje").get_json()
        self.assertEqual([z["filename"] for z in j["zdroje"]], ["sky_2k.hdr"])
        self.assertEqual([(e["key"], e["source_name"]) for e in j["extra"]], [("old_hall", "Old_Hall_4k.hdr")])
        self.assertNotIn("source_id", j["extra"][0])


class TestImport(Base):
    def test_uspesny_import(self):
        pridej_soubor(1, "Old_Hall_4k.hdr")
        r = post({"file_id": 1, "label": "  Stará   hala  "})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        p = r.get_json()["polozka"]
        self.assertEqual((p["key"], p["label"], p["rot0_deg"]), ("old_hall", "Stará hala", 0.0), "mezery v nazvu se sjednoti")
        self.assertEqual((p["url"], p["lo"]), ("/api/public/v3d-env/old_hall_1024.hdr", "/api/public/v3d-env/old_hall_256.hdr"))
        self.assertTrue(0.05 <= p["mul0"] <= 20)
        self.assertEqual(zbytky(), ["old_hall_1024.hdr", "old_hall_256.hdr"], "jen dva soubory, zadna .tmp-* slozka")
        self.assertEqual(os.path.getsize(os.path.join(S["m"].ENV_DIR, "old_hall_1024.hdr")), 2115634)
        self.assertEqual(os.path.getsize(os.path.join(S["m"].ENV_DIR, "old_hall_256.hdr")), 132657)
        mf = json.loads(S["db"].nastaveni[S["m"].KLIC_EXTRA])
        self.assertEqual(len(mf), 1)
        self.assertEqual({k: mf[0][k] for k in ("key", "label", "source_id", "source_name", "w", "h", "by", "rot0_deg")}, {"key": "old_hall", "label": "Stará hala", "source_id": 1, "source_name": "Old_Hall_4k.hdr", "w": 2048, "h": 1024, "by": 7, "rot0_deg": 0.0})
        self.assertEqual(S["audit"][-1][1:3], ("create", "v3d_env"))
        self.assertEqual(S["audit"][-1][4]["key"], "old_hall")

    def test_label_podle_nazvu_souboru(self):
        pridej_soubor(1, "Old_Hall_4k.hdr")
        self.assertEqual(post({"file_id": 1}).get_json()["polozka"]["label"], "Old hall")

    def test_vystup_je_cten_vieweru(self):
        pridej_soubor(1, "Old_Hall_4k.hdr")
        post({"file_id": 1})
        img, W, H = S["prevod"].read_rgbe(os.path.join(S["m"].ENV_DIR, "old_hall_1024.hdr"))
        self.assertEqual((W, H), (1024, 512))
        img, W, H = S["prevod"].read_rgbe(os.path.join(S["m"].ENV_DIR, "old_hall_256.hdr"), w_max=256, w_min=256)
        self.assertEqual((W, H), (256, 128))

    def test_kolize_klicu(self):
        pridej_soubor(1, "sky_4k.hdr"); pridej_soubor(2, "sky_8k.hdr"); pridej_soubor(3, "crossfit_4k.hdr"); pridej_soubor(4, "123abc.hdr"); pridej_soubor(5, "mistnost.hdr")
        klice = [post({"file_id": i}).get_json()["polozka"]["key"] for i in (1, 2, 3, 4, 5)]
        self.assertEqual(klice[:2], ["sky", "sky_2"])
        self.assertEqual(klice[2], "crossfit_2", "vestavene klice se neprepisuji")
        self.assertEqual(klice[3], "hdri_123abc", "klic musi zacinat pismenem")
        self.assertEqual(klice[4], "mistnost_2")
        self.assertEqual(len(set(klice)), 5)

    def test_neplatne_telo(self):
        pridej_soubor(1, "sky_4k.hdr")
        for nazev, body in (("neni objekt", [1]), ("cizi klic", {"file_id": 1, "jas": 2}), ("bez file_id", {}), ("file_id text", {"file_id": "1"}), ("file_id bool", {"file_id": True}),
                            ("file_id desetinne", {"file_id": 1.5}), ("label prazdny", {"file_id": 1, "label": "  "}), ("label dlouhy", {"file_id": 1, "label": "x" * 61}), ("label cislo", {"file_id": 1, "label": 5})):
            with self.subTest(case=nazev):
                r = post(body)
                self.assertEqual(r.status_code, 400, (nazev, r.get_data(as_text=True)))
                self.assertEqual((S["db"].nastaveni, zbytky()), ({}, []))
        self.assertEqual(post(None, raw="nejson").status_code, 400)
        self.assertEqual(post(None, raw="").status_code, 400)

    def test_neplatny_zdroj(self):
        pridej_soubor(1, "x_4k.exr", obsah=open(S["syn"], "rb").read()); pridej_soubor(2, "modern_buildings_4k.hdr"); pridej_soubor(3, "tajny.hdr", folder=3); pridej_soubor(4, "chybi.hdr", obsah=False, velikost=10)
        pridej_soubor(5, "text.hdr", obsah=b"to neni hdr\n" * 100); pridej_soubor(6, "pasti.hdr", obsah=b"x", stored="../../../etc/passwd")
        S["perm"]["user"] = {"id": 8, "role": "obchodnik", "active": True}
        self.assertEqual(post({"file_id": 999}).status_code, 404, "soubor v DB neni")
        r = post({"file_id": 1})
        self.assertEqual((r.status_code, "EXR zatím nejde" in r.get_json()["error"]), (400, True), ".exr zatim ne (i kdyz obsahuje platne HDRI)")
        r = post({"file_id": 2})
        self.assertEqual((r.status_code, r.get_json()["error"]), (400, "HDRI modern_buildings je zakázaná, nepoužívat."))
        self.assertEqual(post({"file_id": 3}).status_code, 403, "slozka bez pristupu")
        self.assertEqual(post({"file_id": 4}).status_code, 404, "soubor na disku chybi")
        r = post({"file_id": 5})
        self.assertEqual((r.status_code, r.get_json()["error"]), (400, "Soubor není Radiance .hdr (chybí hlavička #?RADIANCE)."), "kontrola hlavicky pred spustenim prevodu")
        self.assertIn(post({"file_id": 6}).status_code, (400, 404), "stored_filename mimo adresar disku se nikdy nectou")
        self.assertEqual((S["db"].nastaveni, zbytky()), ({}, []), "po vsech odmitnutich nic neulozeno")

    def test_zakazana_hdri_i_pro_admina(self):
        pridej_soubor(2, "Modern_Buildings_2k.hdr")
        self.assertEqual(post({"file_id": 2}).status_code, 400)

    def test_cesta_mimo_disk_se_nikdy_nectou(self):
        tajne = os.path.join(S["priv"], "tajne.hdr")                          # o uroven vyse nez adresar Sdileneho disku
        shutil.copy(S["syn"], tajne)
        pridej_soubor(1, "unik.hdr", obsah=False, stored="../tajne.hdr", velikost=10)
        r = post({"file_id": 1})
        self.assertNotEqual(r.status_code, 200)
        self.assertEqual((S["db"].nastaveni, zbytky()), ({}, []))
        os.symlink(tajne, os.path.join(S["drive"], "odkaz.hdr"))
        pridej_soubor(2, "odkaz.hdr", obsah=False, stored="odkaz.hdr", velikost=10)
        self.assertNotEqual(post({"file_id": 2}).status_code, 200, "symlink mimo adresar disku se nenasleduje")
        self.assertEqual((S["db"].nastaveni, zbytky()), ({}, []))

    def test_moc_velky_soubor(self):
        pridej_soubor(1, "sky_4k.hdr")
        S["m"].ZDROJ_MAX_B = 1000
        r = post({"file_id": 1})
        self.assertEqual(r.status_code, 400)
        self.assertIn("moc velký", r.get_json()["error"])

    def test_duplicita_zdroje_a_limit(self):
        pridej_soubor(1, "sky_4k.hdr"); pridej_soubor(2, "cloud_4k.hdr")
        self.assertEqual(post({"file_id": 1}).status_code, 200)
        r = post({"file_id": 1})
        self.assertEqual((r.status_code, "už je doplněné" in r.get_json()["error"]), (409, True))
        S["m"].MAX_EXTRA = 1
        r = post({"file_id": 2})
        self.assertEqual(r.status_code, 409)
        self.assertIn("maximum", r.get_json()["error"])
        self.assertEqual(len(json.loads(S["db"].nastaveni[S["m"].KLIC_EXTRA])), 1)

    def test_jiny_import_bezi(self):
        import fcntl
        pridej_soubor(1, "sky_4k.hdr")
        f = open(os.path.join(S["m"].ENV_DIR, ".import.lock"), "a+")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            r = post({"file_id": 1})
            self.assertEqual((r.status_code, "běží jiný import" in r.get_json()["error"]), (409, True))
            self.assertEqual(klient().delete("/api/admin/v3d-env/sky").status_code, 409)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN); f.close()
        self.assertEqual(post({"file_id": 1}).status_code, 200, "po uvolneni zamku to jde")

    def test_selhani_prevodu_nic_nezanecha(self):
        zle = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1024 +X 3072\n" + b"\0" * 5000
        pridej_soubor(1, "tri_ku_jedne_4k.hdr", obsah=zle)
        r = post({"file_id": 1})
        self.assertEqual(r.status_code, 400)
        self.assertIn("equirectangular 2:1", r.get_json()["error"])
        self.assertEqual((S["db"].nastaveni, zbytky(), S["audit"]), ({}, [], []))
        data = open(S["syn"], "rb").read()
        pridej_soubor(2, "useknuty_4k.hdr", obsah=data[:len(data) // 3])
        r = post({"file_id": 2})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Převod HDRI selhal", r.get_json()["error"])
        self.assertEqual((S["db"].nastaveni, zbytky()), ({}, []))

    def test_casovy_limit_prevodu(self):
        pridej_soubor(1, "sky_4k.hdr")
        S["m"].TIMEOUT_S = 0.05
        r = post({"file_id": 1})
        self.assertEqual(r.status_code, 400)
        self.assertIn("trval déle", r.get_json()["error"])
        self.assertEqual((S["db"].nastaveni, zbytky()), ({}, []))

    def test_chyba_zapisu_evidence_neponecha_sirotky(self):
        pridej_soubor(1, "sky_4k.hdr")
        S["db"].padni_zapis = True
        self.assertEqual(post({"file_id": 1}).status_code, 500, "chyba DB je 500 (Flask), ne tichy uspech")
        self.assertEqual((S["db"].nastaveni, zbytky()), ({}, []), "soubory se pri selhani evidence odstrani")
        S["db"].padni_zapis = False
        self.assertEqual(post({"file_id": 1}).status_code, 200, "zamek se po chybe uvolnil")


class TestSmazani(Base):
    def test_smazani(self):
        pridej_soubor(1, "sky_4k.hdr"); pridej_soubor(2, "cloud_4k.hdr")
        post({"file_id": 1}); post({"file_id": 2})
        self.assertEqual(len(zbytky()), 4)
        r = klient().delete("/api/admin/v3d-env/sky")
        self.assertEqual((r.status_code, r.get_json()), (200, {"ok": True}))
        self.assertEqual(zbytky(), ["cloud_1024.hdr", "cloud_256.hdr"])
        self.assertEqual([z["key"] for z in json.loads(S["db"].nastaveni[S["m"].KLIC_EXTRA])], ["cloud"])
        self.assertEqual(S["audit"][-1][1:3], ("delete", "v3d_env"))
        self.assertEqual(klient().delete("/api/admin/v3d-env/cloud").status_code, 200)
        self.assertNotIn(S["m"].KLIC_EXTRA, S["db"].nastaveni, "posledni smazane = radek zmizi")
        self.assertEqual(zbytky(), [])

    def test_neznamy_a_neplatny_klic(self):
        self.assertEqual(klient().delete("/api/admin/v3d-env/neexistuje").status_code, 404)
        for k in ("..", "Velke", "a", "x" * 41, "klic-s-pomlckou"):
            with self.subTest(klic=k):
                self.assertIn(klient().delete("/api/admin/v3d-env/" + k).status_code, (400, 404))
        self.assertEqual(klient().delete("/api/admin/v3d-env/crossfit").status_code, 404, "vestavene HDRI nejde smazat")

    def test_pouzite_ve_vzhledu_nejde_smazat(self):
        pridej_soubor(1, "sky_4k.hdr")
        post({"file_id": 1})
        S["db"].nastaveni["v3d_nabidka_vzhled"] = json.dumps({"env": {"hdri": "sky", "strength": 1, "rot_deg": 0, "hemi": 0}, "alu": None})
        r = klient().delete("/api/admin/v3d-env/sky")
        self.assertEqual(r.status_code, 409)
        self.assertIn("uložené ve vzhledu", r.get_json()["error"])
        self.assertEqual(zbytky(), ["sky_1024.hdr", "sky_256.hdr"])
        S["db"].nastaveni["v3d_nabidka_vzhled"] = json.dumps({"env": {"hdri": "tv_studio", "strength": 1, "rot_deg": 0, "hemi": 0}})
        self.assertEqual(klient().delete("/api/admin/v3d-env/sky").status_code, 200)
        S["db"].nastaveni["v3d_nabidka_vzhled"] = "{nejson"
        pridej_soubor(2, "cloud_4k.hdr"); post({"file_id": 2})
        self.assertEqual(klient().delete("/api/admin/v3d-env/cloud").status_code, 200, "poskozeny ulozeny vzhled mazani neblokuje")


class TestVerejne(Base):
    def setUp(self):
        super().setUp()
        pridej_soubor(1, "sky_4k.hdr")
        post({"file_id": 1})

    def test_soubor(self):
        r = klient().get("/api/public/v3d-env/sky_1024.hdr")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.headers["Content-Type"], r.headers["X-Content-Type-Options"]), ("application/octet-stream", "nosniff"))
        self.assertIn("max-age=3600", r.headers["Cache-Control"])
        self.assertEqual(len(r.data), 2115634)
        self.assertTrue(r.data.startswith(b"#?RADIANCE"))
        etag = r.headers["ETag"]
        self.assertEqual(klient().get("/api/public/v3d-env/sky_1024.hdr", headers={"If-None-Match": etag}).status_code, 304)
        self.assertEqual(len(klient().get("/api/public/v3d-env/sky_256.hdr").data), 132657)

    def test_jen_evidovane_klice_a_presny_tvar(self):
        for n in ("crossfit_1024.hdr", "tv_studio_1024.hdr", "neznamy_1024.hdr", "sky_512.hdr", "sky_1024.exr", "SKY_1024.hdr", "sky_1024.hdr.bak", "..%2f..%2fetc%2fpasswd", ".import.lock", "sky_1024.HDR"):
            with self.subTest(fname=n):
                self.assertEqual(klient().get("/api/public/v3d-env/" + n).status_code, 404)

    def test_soubor_mimo_evidenci_se_nesluzi(self):
        for n in ("stray_1024.hdr", "sky_1024.hdr.bak", "tv_studio_256.hdr"):
            shutil.copy(os.path.join(S["m"].ENV_DIR, "sky_1024.hdr"), os.path.join(S["m"].ENV_DIR, n))
            with self.subTest(fname=n):
                self.assertEqual(klient().get("/api/public/v3d-env/" + n).status_code, 404, "existuje na disku, ale neni v evidenci / nema presny tvar nazvu")

    def test_chybejici_soubor_je_404(self):
        os.remove(os.path.join(S["m"].ENV_DIR, "sky_256.hdr"))
        self.assertEqual(klient().get("/api/public/v3d-env/sky_256.hdr").status_code, 404)
        self.assertEqual(klient().get("/api/public/v3d-env/sky_1024.hdr").status_code, 200)

    def test_public_extra_bez_zdroje(self):
        pe = S["m"].public_extra()
        self.assertEqual(len(pe), 1)
        self.assertEqual(set(pe[0]), {"key", "label", "mul0", "rot0_deg", "url", "lo"})
        self.assertEqual((pe[0]["key"], pe[0]["rot0_deg"]), ("sky", 0.0))
        self.assertNotIn("sky_4k", json.dumps(pe), "nazev zdrojoveho souboru se verejne neukazuje")


class TestEvidence(Base):
    def put_manifest(self, data):
        S["db"].nastaveni[S["m"].KLIC_EXTRA] = data if isinstance(data, str) else json.dumps(data)
        S["m"]._cache.update(t=0.0, v=None)

    def test_neplatne_zaznamy_se_preskoci(self):
        ok = {"key": "dobre", "label": "Dobré", "mul0": 1.2}
        self.put_manifest([ok, dict(ok, key="crossfit"), dict(ok, key="Velke"), dict(ok, key="ab"), dict(ok, key="x" * 41), dict(ok, key="a_b", label=""), dict(ok, key="a_c", label="x" * 61),
                           dict(ok, key="a_d", mul0=0.01), dict(ok, key="a_e", mul0=25), dict(ok, key="a_f", mul0="1"), dict(ok, key="a_g", mul0=True), ok, "text", None, 5, {"key": "bez_labelu"}])
        self.assertEqual(S["m"].extra_klice(), ("dobre",), "duplicitni klic jen jednou, vestavene a neplatne se zahodi")

    def test_poskozena_evidence_je_prazdna_a_neshodi(self):
        for hodnota in ("{nejson", '{"key": "a"}', "42", '"text"', "null", ""):
            with self.subTest(hodnota=hodnota):
                self.put_manifest(hodnota)
                self.assertEqual(S["m"].extra_klice(), ())

    def test_vypadek_db_je_prazdny_seznam(self):
        orig = S["app"].get_conn
        S["m"].get_conn = lambda: (_ for _ in ()).throw(RuntimeError("DB nejede"))
        try:
            S["m"]._cache.update(t=0.0, v=None)
            self.assertEqual(S["m"].extra_klice(), ())
        finally:
            S["m"].get_conn = orig

    def test_cache_ttl(self):
        self.put_manifest([{"key": "dobre", "label": "D", "mul0": 1}])
        S["m"].TTL_S = 60.0
        self.assertEqual(S["m"].extra_klice(), ("dobre",))
        S["db"].nastaveni.clear()
        self.assertEqual(S["m"].extra_klice(), ("dobre",), "z cache")
        self.assertEqual(S["m"].extra_klice(force=True), (), "force cte znovu")
        S["m"].TTL_S = 0.0


class TestKlic(unittest.TestCase):
    def test_navrh_klice(self):
        m = S["m"]
        for nazev, obsazene, ocek in (("Old_Hall_4k.hdr", set(), "old_hall"), ("berg_inner_8k.hdr", {"berg_inner"}, "berg_inner_2"), ("My Nice HDRI-2k.hdr", set(), "my_nice_hdri"),
                                       ("2k_sky.hdr", set(), "hdri_2k_sky"), ("a.hdr", set(), "a_hdri"), ("", set(), "hdri"), ("ZIMA__sníh_16k.hdr", set(), "zima_sn_h"),
                                       ("x" * 80 + ".hdr", set(), "x" * 34), ("sky.hdr", {"sky", "sky_2", "sky_3"}, "sky_4")):
            with self.subTest(nazev=nazev):
                k = m.navrh_klice(nazev, obsazene)
                self.assertEqual(k, ocek)
                self.assertRegex(k, r"^[a-z][a-z0-9_]{2,39}$")


class TestShoda(unittest.TestCase):
    def test_zakazane_hdri_jako_v_render_hdri(self):
        zdroj = open(os.path.join(REPO, "api", "render_hdri.py"), encoding="utf-8").read()
        m = re.search(r"ZAKAZANE_HDRI = \(([^)]*)\)", zdroj)
        self.assertTrue(m)
        self.assertEqual(tuple(re.findall(r'"([a-z_]+)"', m.group(1))), S["m"].ZAKAZANE)
        m = re.search(r'CHYBA_ZAKAZANA_HDRI = "([^"]+)"', zdroj)
        self.assertEqual(m.group(1), S["m"].CHYBA_ZAKAZANA)

    def test_vestavena_hdri_jako_v_v3d_vzhled(self):
        zdroj = open(os.path.join(REPO, "api", "v3d_vzhled.py"), encoding="utf-8").read()
        m = re.search(r"ENV_HDRI = \(([^)]*)\)", zdroj)
        self.assertEqual(tuple(re.findall(r'"([a-z_]+)"', m.group(1))), S["m"].BUILTIN)

    def test_vestavena_hdri_jako_ve_vieweru(self):
        viewer = open(os.environ.get("VIEWER_JS") or os.path.join(REPO, "webapp/js/v3d/viewer3d.js"), encoding="utf-8").read()
        blok = viewer[viewer.index("var HDRI_LIBRARY = ["):]
        blok = blok[:blok.index("];")]
        self.assertEqual(tuple(re.findall(r"key: '([a-z_]+)'", blok)) + ("mistnost",), S["m"].BUILTIN)

    def test_meze_mul0_jako_ve_vieweru(self):
        viewer = open(os.environ.get("VIEWER_JS") or os.path.join(REPO, "webapp/js/v3d/viewer3d.js"), encoding="utf-8").read()
        m = re.search(r"var ENV_MUL0_MIN = ([0-9.]+), ENV_MUL0_MAX = ([0-9.]+);", viewer)
        self.assertIsNotNone(m, "viewer3d.js: chybi var ENV_MUL0_MIN = ..., ENV_MUL0_MAX = ...;")
        self.assertEqual((float(m.group(1)), float(m.group(2))), S["m"].MUL0_MEZE)

    def test_vystupni_nazvy_odpovidaji_url_ve_vieweru(self):
        viewer = open(os.environ.get("VIEWER_JS") or os.path.join(REPO, "webapp/js/v3d/viewer3d.js"), encoding="utf-8").read()
        self.assertIn("/api/public/v3d-env/", viewer)
        self.assertIn("_1024.hdr", viewer)


class TestPrevod(unittest.TestCase):
    def test_cteni_a_zapis_je_shodny_s_knihovnou(self):
        P = S["prevod"]
        env = os.path.join(REPO, "webapp", "js", "v3d", "env")
        tmp = tempfile.mkdtemp(dir=S["tmp"])
        r = P.prevod(os.path.join(env, "tv_studio_1024.hdr"), tmp, "tvs", os.path.join(env, "crossfit_1024.hdr"))
        self.assertAlmostEqual(r["mul0"], 0.53, delta=0.53 * 0.05, msg="stejny vypocet dava u tv_studio to, co drive rucne zmereno (do 5 %)")
        self.assertEqual(open(os.path.join(tmp, "tvs_256.hdr"), "rb").read(), open(os.path.join(env, "tv_studio_256.hdr"), "rb").read(), "256 nahled je byte po bytu jako v knihovne")

    def test_neni_nasobek_1024_a_zachova_energii(self):
        import numpy as np
        P = S["prevod"]
        rng = np.random.default_rng(3)
        rgb = (rng.random((1500, 3000, 3), dtype=np.float32) * 0.5).astype(np.float32)
        rgb[100:140, 200:240] = 5000.0
        tmp = tempfile.mkdtemp(dir=S["tmp"])
        zdroj = os.path.join(tmp, "z.hdr")
        P.write_rgbe(zdroj, rgb)
        r = P.prevod(zdroj, tmp, "k", os.path.join(REPO, "webapp", "js", "v3d", "env", "crossfit_1024.hdr"))
        img, W, H = P.read_rgbe(os.path.join(tmp, "k_1024.hdr"))
        self.assertEqual((W, H), (1024, 512))
        self.assertAlmostEqual(P.mean_lum(P.to_float(img)) / P.mean_lum(rgb), 1.0, delta=0.01)
        self.assertGreater(r["mul0"], 0)

    def test_mul0_je_nezavisle_na_jasu_zdroje(self):
        import numpy as np
        P = S["prevod"]
        rng = np.random.default_rng(4)
        rgb = (rng.random((1024, 2048, 3), dtype=np.float32) * 0.4 + 0.1).astype(np.float32)
        tmp = tempfile.mkdtemp(dir=S["tmp"])
        ref = os.path.join(REPO, "webapp", "js", "v3d", "env", "crossfit_1024.hdr")
        out = []
        for nasobek in (1.0, 2.0):
            z = os.path.join(tmp, "z%d.hdr" % nasobek)
            P.write_rgbe(z, rgb * nasobek)
            out.append(P.prevod(z, tmp, "k%d" % nasobek, ref)["mul0"])
        self.assertAlmostEqual(out[1], out[0] / 2, delta=out[0] * 0.02, msg="dvojnasobne jasne HDRI = polovicni mul0")

    def test_chyby_vstupu(self):
        P = S["prevod"]
        tmp = tempfile.mkdtemp(dir=S["tmp"])

        def chyba(data):
            p = os.path.join(tmp, "c.hdr")
            open(p, "wb").write(data)
            with self.assertRaises(P.Chyba) as cm:
                P.read_rgbe(p)
            return str(cm.exception)
        hlavicka = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n"
        self.assertIn("chybi hlavicka", chyba(b"ahoj\n" * 30))
        self.assertIn("2:1", chyba(hlavicka + b"-Y 1024 +X 3072\n" + b"\0" * 64))
        self.assertIn("moc velke", chyba(hlavicka + b"-Y 8192 +X 16384\n" + b"\0" * 64))
        self.assertIn("moc male", chyba(hlavicka + b"-Y 256 +X 512\n" + b"\0" * 64))
        self.assertIn("nepodporovany format", chyba(b"#?RADIANCE\nFORMAT=32-bit_rle_xyze\n\n-Y 1024 +X 2048\n" + b"\0" * 64))
        self.assertIn("orientace", chyba(hlavicka + b"-Y 1024 -X 2048\n" + b"\0" * 64))
        self.assertIn("hlavicka", chyba(b"#?RADIANCE" + b"x" * 200))
        data = open(S["syn"], "rb").read()
        self.assertTrue(chyba(data[:len(data) // 2]), "useknuty soubor je Chyba s ceskym duvodem, ne vyjimka")

    def test_cerna_hdri(self):
        import numpy as np
        P = S["prevod"]
        tmp = tempfile.mkdtemp(dir=S["tmp"])
        z = os.path.join(tmp, "cerna.hdr")
        P.write_rgbe(z, np.zeros((1024, 2048, 3), np.float32))
        with self.assertRaises(P.Chyba) as cm:
            P.prevod(z, tmp, "k", os.path.join(REPO, "webapp", "js", "v3d", "env", "crossfit_1024.hdr"))
        self.assertIn("cerna", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
