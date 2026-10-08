# -*- coding: utf-8 -*-
"""Atrapy pro hermeticke testy endpointu Vytvorit online nabidku z karty Vandr (2026-10-02).

Co je atrapa (NIC z toho nesaha na produkci):
  FakeDB          databaze v pameti: shop_products, app_settings, shared_drive_*, scene_offers. Rozumi jen
                  presne dotazum, ktere endpoint a scene_offers.py pouzivaji; JAKYKOLI jiny dotaz (zapis do cizi
                  tabulky, DELETE...) = AssertionError. Zadne spojeni na MySQL se neotevira.
  install_stubs   do sys.modules vlozi atrapy modulu `app`, `quotes`, `drive`, `documents`, `orders`,
                  `product_assemblies`, `weasyprint`, aby sel nacist SKUTECNY api/scene_offers.py a
                  api/vandr_scene_offers.py bez DB a bez spusteni serveru (api/app.py se nikdy nenacita).
  vandr_output    napodoba vystup `php artisan vandr:offer-data <uuid> [--v3d]` ze snimku ctx (fixtures/ctx);
                  ctx se z neho zpet slozi stejne (shoda ctx_sha8 se snimkem je test).
Soubory (obrazky nabidek, modely, cache) jdou do docasneho adresare, ne do repa.
"""
import base64
import functools
import hashlib
import itertools
import json
import os
import re
import sys
import threading
import types
import uuid as uuidlib

import _cesty as CE

# SKU Vandr karet (verejne udaje shop_products; stejne jako v produkci)
SKU = {
    "4453": "VD-49048eff-7563-40d5-a36e-b0afdf42b650",
    "4474": "VD-2e1bc1a8-3da6-410f-a150-3a1725080050",
    "4594": "VD-2a600088-9f42-4ae7-96cc-328e7e562c7b",
    "4910": "VD-4155e003-fc0b-427f-8f82-55c8fbcd5022",
    "4917": "VD-e59b6431-c972-43c7-893e-7cff976c853c",
    "4918": "VD-1958c629-f467-4cf6-bd47-59791b82d094",
    "4921": "VD-68ef91f0-6590-421a-8edc-5594bc8f0dd4",
}
PNG1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def ctx_fixture(k):
    with open(os.path.join(CE.FIX, "ctx", "ctx_%s.json" % k), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Vandr: vystup artisan prikazu ze snimku ctx
# ---------------------------------------------------------------------------

def vandr_output(k, s_v3d=True):
    """dict jako json.loads(stdout) prikazu vandr:offer-data <uuid> [--v3d]."""
    out = {"car_name": "Atrapa vozu %s" % k,
           "parts": {"left_part": {"image_2d_with_dim": "images/%s_2d.png" % k, "image_3d_primary": "images/%s_a.png" % k,
                                   "image_3d_secondary": "images/%s_b.png" % k}}}
    if not s_v3d or not os.path.exists(os.path.join(CE.FIX, "ctx", "ctx_%s.json" % k)):
        return out
    ctx = ctx_fixture(k)
    skupiny = {}
    for i in ctx["instance"]:                       # poradi z ctx = poradi v datech
        skupiny.setdefault(i["strana"], {}).setdefault(i["nohy"], []).append(i)

    def vec(v):
        return {"x": v[0], "y": v[1], "z": v[2]} if v else None

    strany = {}
    for strana, nohy_d in skupiny.items():
        data = []
        for nohy, inst in nohy_d.items():
            data.append({"unity_id": nohy, "components": [
                {"unity_id": i["unity_id"], "position": vec(i["pozice"]), "rotation": vec(i["rotace"]),
                 "extensions": list(i["rozsireni"])} for i in inst]})
        strany[strana] = {"id": ctx["strany"][strana], "data": json.dumps(data)}
    komponenty, rozsireni = [], {}
    for kk in ctx["komponenty"]:
        komponenty.append({"unity_id": kk["unity_id"], "category_id": kk["category_id"], "kategorie": kk["kategorie"],
                           "is_universal": kk["is_universal"], "is_top": kk["is_top"], "dily": kk["dily"]})
        for e in kk["rozsireni"]:
            rozsireni[e["unity_id"]] = {"unity_id": e["unity_id"], "dily": e["dily"]}
    out["v3d"] = {"v": 1, "strany": strany, "komponenty": komponenty,
                  "rozsireni": sorted(rozsireni.values(), key=lambda r: r["unity_id"]),
                  "chybi_komponenty": [], "chybi_dily": 0, "smazane_dily": []}
    return out


class Proc:
    def __init__(self, rc=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = rc, stdout, stderr


def artisan_nova(k):
    """Atrapa `_spust_artisan` - NOVA verze prikazu (zna --v3d). Pocita volani v .volani."""
    def f(argumenty, timeout_s):
        f.volani.append(list(argumenty))
        return Proc(0, json.dumps(vandr_output(k, "--v3d" in argumenty)))
    f.volani = []
    return f


def artisan_bez_obrazku(k, s_v3d=True, nova=True, jen=()):
    """Vandr vraci prazdne retezce u obrazku (jen FBX export, Unity klient nikdy neulozil obrazky). jen = klice obrazku, ktere
    PRESTO existuji (napr. ("image_2d_with_dim",)). nova=False: prikaz bez --v3d (rc 1 pri volani s --v3d). s_v3d=False: klic v3d
    chybi (vystup bez v3d dat)."""
    def f(argumenty, timeout_s):
        f.volani.append(list(argumenty))
        if "--v3d" in argumenty and not nova:
            return Proc(1, "", '\n  The "--v3d" option does not exist.\n')
        o = vandr_output(k, "--v3d" in argumenty and s_v3d)
        for sl in ("image_2d_with_dim", "image_3d_primary", "image_3d_secondary"):
            if sl not in jen:
                o["parts"]["left_part"][sl] = ""
        return Proc(0, json.dumps(o))
    f.volani = []
    return f


def artisan_stara(k):
    """Atrapa STARE verze (bez volby --v3d): Symfony hlasi neznamou volbu, rc 1."""
    def f(argumenty, timeout_s):
        f.volani.append(list(argumenty))
        if "--v3d" in argumenty:
            return Proc(1, "", '\n  The "--v3d" option does not exist.\n')
        return Proc(0, json.dumps(vandr_output(k, False)))
    f.volani = []
    return f


# ---------------------------------------------------------------------------
# DB v pameti
# ---------------------------------------------------------------------------

def _ws(sql):
    return re.sub(r"\s+", " ", sql.strip())


class FakeDB:
    def __init__(self, karty=None):
        self.lock = threading.RLock()
        self.shop_products = {}
        self.app_settings = {}
        self.folders, self.drive_files, self.offers = [], [], []
        self.audit = []
        self.turntable_frames = {}      # karta -> [radky product_turntable_frames]
        self.gallery_items = {}         # karta -> [filename] (content_gallery_items, verejne)
        self.umisteni = {}              # karta -> nazev umisteni v aute (regal_umisteni.nazev, polozky spolecne nabidky)
        self.shop_images = {}           # karta -> [filename] (shop_product_images)
        self.dotazy = []
        self._id = itertools.count(1)
        self.spojeni_otevrena = 0
        for k in (karty or ()):
            self.pridej_kartu(k)

    def pridej_kartu(self, k, **zmeny):
        ctx = ctx_fixture(k)
        row = {"id": int(k), "name": "Atrapa vozu %s" % k, "sku": SKU[k], "description": "Hliníková regálová vestavba (atrapa)",
               "glb_file": ctx["glb_file"], "price_czk_placeholder": 123456,
               "vandr_predni_azimut_deg": ctx["vandr_predni_azimut_deg"]}
        row.update(zmeny)
        self.shop_products[int(k)] = row
        self.app_settings["render_prirazeni_materialu"] = json.dumps(ctx["prirazeni_materialu"])
        return row

    def pridej_vlastni_kartu(self, id_, sku, glb_file, azimut, name="Atrapa", cena=62540):
        row = {"id": int(id_), "name": name, "sku": sku, "description": "Hliníková regálová vestavba (atrapa)",
               "glb_file": glb_file, "price_czk_placeholder": cena, "vandr_predni_azimut_deg": azimut}
        self.shop_products[int(id_)] = row
        return row

    def conn(self):
        with self.lock:
            self.spojeni_otevrena += 1
        return FakeConn(self)

    # -- dotazy --
    def execute(self, cur, sql, params):
        q = _ws(sql)
        params = tuple(params or ())
        with self.lock:
            self.dotazy.append((q, params))
            for rx, fn in self._handlery:
                m = rx.match(q)
                if m:
                    return fn(self, cur, m, params)
        raise AssertionError("FakeDB: nepovoleny/neznamy dotaz (zapis do produkce by byl chyba): %s" % q[:200])

    def _sel_karta_endpoint(self, cur, m, p):
        r = self.shop_products.get(p[0])
        cur._rows = [{k: r[k] for k in ("id", "name", "sku", "description", "glb_file", "price_czk_placeholder",
                                        "vandr_predni_azimut_deg")}] if r else []

    def _sel_umisteni(self, cur, m, p):
        cur._rows = [{"nazev": self.umisteni.get(str(p[0]))}] if int(p[0]) in self.shop_products else []

    def _sel_frames(self, cur, m, p):
        cur._rows = [dict(r) for r in self.turntable_frames.get(p[0], [])]

    def _sel_gallery_items(self, cur, m, p):
        cur._rows = [{"filename": f} for f in self.gallery_items.get(p[0], [])]

    def _sel_shop_images(self, cur, m, p):
        cur._rows = [{"filename": f} for f in self.shop_images.get(p[0], [])]

    def _sel_karta_ctx(self, cur, m, p):
        r = self.shop_products.get(p[0])
        cur._rows = [{k: r[k] for k in ("id", "sku", "glb_file", "vandr_predni_azimut_deg")}] if r else []

    def _sel_setting(self, cur, m, p):
        v = self.app_settings.get(p[0])
        cur._rows = [{"setting_value": v}] if v is not None else []

    def _sel_folder_root(self, cur, m, p):
        cur._rows = [{"id": f["id"]} for f in self.folders if f["parent"] is None and f["name"] == p[0]][:1]

    def _sel_folder_child(self, cur, m, p):
        cur._rows = [{"id": f["id"]} for f in self.folders if f["parent"] == p[0] and f["name"] == p[1]][:1]

    def _ins_folder(self, cur, m, p):
        if "NULL" in m.group(0).split("VALUES")[1].split(",")[0]:
            parent, name = None, p[0]
        else:
            parent, name = p[0], p[1]
        fid = next(self._id)
        self.folders.append({"id": fid, "parent": parent, "name": name})
        cur.lastrowid = fid

    def _sel_drive_files(self, cur, m, p):
        cur._rows = []

    def _ins_drive_file(self, cur, m, p):
        fid = next(self._id)
        self.drive_files.append({"id": fid, "folder_id": p[0], "filename": p[1], "stored_filename": p[2],
                                 "content_type": p[3], "size_bytes": p[4], "uploaded_by": p[5]})
        cur.lastrowid = fid

    def _ins_offer(self, cur, m, p):
        cols = [c.strip() for c in m.group(1).split(",")]
        assert len(cols) == len(p), "INSERT scene_offers: pocet sloupcu != parametru"
        row = dict(zip(cols, p))
        row.update({"id": next(self._id), "is_active": 1, "admin_view_token_hash": None, "view_3d_model": None,
                    "drive_model_file_id": None, "revision_number": 1})
        self.offers.append(row)
        cur.lastrowid = row["id"]

    def _sel_offer_id(self, cur, m, p):
        cur._rows = [dict(o) for o in self.offers if o["id"] == p[0]][:1]

    def _upd_offer_model(self, cur, m, p):
        for o in self.offers:
            if o["id"] == p[2]:
                o["view_3d_model"], o["drive_model_file_id"] = p[0], p[1]

    def _sel_offer_token(self, cur, m, p):
        cur._rows = [dict(o) for o in self.offers if o["view_token_hash"] == p[0] or o["admin_view_token_hash"] == p[0]][:1]


FakeDB._handlery = [
    (re.compile(r"^SELECT id, name, sku, description, glb_file, price_czk_placeholder, vandr_predni_azimut_deg FROM shop_products WHERE id=%s$"),
     FakeDB._sel_karta_endpoint),
    (re.compile(r"^SELECT ru.nazev AS nazev FROM shop_products sp LEFT JOIN regal_umisteni ru ON ru.id = sp.umisteni_id WHERE sp.id=%s$"), FakeDB._sel_umisteni),
    (re.compile(r"^SELECT elevation_deg, azimuth_deg, tier_px, filename, bytes FROM product_turntable_frames WHERE shop_product_id=%s AND is_active=1$"),
     FakeDB._sel_frames),
    (re.compile(r"^SELECT filename FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s AND is_public=1 ORDER BY sort_order, id$"),
     FakeDB._sel_gallery_items),
    (re.compile(r"^SELECT filename FROM shop_product_images WHERE product_id=%s ORDER BY sort_order, id$"), FakeDB._sel_shop_images),
    (re.compile(r"^SELECT id, sku, glb_file, vandr_predni_azimut_deg FROM shop_products WHERE id=%s$"), FakeDB._sel_karta_ctx),
    (re.compile(r"^SELECT setting_value FROM app_settings WHERE setting_key=%s$"), FakeDB._sel_setting),
    (re.compile(r"^SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s$"), FakeDB._sel_folder_root),
    (re.compile(r"^SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s$"), FakeDB._sel_folder_child),
    (re.compile(r"^INSERT INTO shared_drive_folders \(parent_folder_id, name, created_by\) VALUES \((?:NULL|%s),%s(?:,NULL|,%s)\)$"), FakeDB._ins_folder),
    (re.compile(r"^SELECT stored_filename FROM shared_drive_files WHERE folder_id=%s AND filename=%s ORDER BY id DESC LIMIT 1$"), FakeDB._sel_drive_files),
    (re.compile(r"^INSERT INTO shared_drive_files \(folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by\) VALUES \(%s,%s,%s,%s,%s,%s\)$"), FakeDB._ins_drive_file),
    (re.compile(r"^INSERT INTO scene_offers \(([a-z_0-9, ]+)\) VALUES \((?:%s,?)+\)$"), FakeDB._ins_offer),
    (re.compile(r"^SELECT id, offer_number, customer_name FROM scene_offers WHERE id=%s$"), FakeDB._sel_offer_id),
    (re.compile(r"^UPDATE scene_offers SET view_3d_model=%s, drive_model_file_id=%s WHERE id=%s$"), FakeDB._upd_offer_model),
    (re.compile(r"^SELECT \* FROM scene_offers WHERE view_token_hash=%s OR admin_view_token_hash=%s$"), FakeDB._sel_offer_token),
]


class FakeCursor:
    def __init__(self, db):
        self.db, self._rows, self.lastrowid = db, [], None

    def execute(self, sql, params=None):
        self._rows = []
        self.db.execute(self, sql, params)
        return len(self._rows)

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        r, self._rows = self._rows, []
        return r

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
        pass

    def rollback(self):
        pass

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Atrapy modulu
# ---------------------------------------------------------------------------

_STUB_NAMES = ("app", "quotes", "drive", "documents", "orders", "product_assemblies", "weasyprint")
_OWN_MODULES = ("scene_offers", "vandr_scene_offers", "offer_model", "build_ctx", "v3d_glb", "v3d_mark")


def install_stubs(db, tmp):
    """-> (flask_app, audit_list). Nacte nova SKUTECNA scene_offers a vandr_scene_offers z repa (REPO/api)."""
    from flask import Flask, jsonify
    for n in _STUB_NAMES + _OWN_MODULES:
        sys.modules.pop(n, None)
    priv = os.path.join(tmp, "private-files")
    drive = os.path.join(tmp, "drive-files")
    os.makedirs(priv, exist_ok=True)
    os.makedirs(drive, exist_ok=True)

    flask_app = Flask("v3d_atrapa")
    flask_app.secret_key = "atrapa-flask-klic-NEPOUZIVAT-ke-znaceni"
    audit = db.audit

    appmod = types.ModuleType("app")
    appmod.app = flask_app
    appmod.get_conn = db.conn
    appmod.require_permission = lambda resource, action: (lambda fn: fn)
    appmod.current_user = lambda: {"id": 7, "username": "tester"}
    # staff_required (trasy jen pro zamestnance, napr. kontrolni scena): vychozi = prihlaseny zamestnanec; test muze nastavit
    # appmod.staff_ok = False a overit 401 (= trasa je opravdu ozdobena dekoratorem, ne jen "projde")
    appmod.staff_ok = True

    def staff_required(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not appmod.staff_ok:
                return jsonify({"error": "Neprihlaseno.", "code": "unauthorized"}), 401
            return fn(*args, **kwargs)
        return wrapper
    appmod.staff_required = staff_required

    def log_audit(user_id, action, entity_type, entity_id=None, detail=None):
        if isinstance(detail, (dict, list)):
            detail = json.dumps(detail, ensure_ascii=False)
        audit.append({"user_id": user_id, "action": action, "entity_type": entity_type, "entity_id": entity_id,
                      "detail": detail})
    appmod.log_audit = log_audit
    for n in ("get_pagination_args", "paginated_query", "parse_bulk_ids", "get_setting", "_rate_limited", "send_email"):
        setattr(appmod, n, lambda *a, **k: None)
    appmod.APP_BASE_URL = "https://atrapa.invalid"
    appmod.KATALOG_GLB_DIR = CE.KATALOG                    # scene_offers.py (bot8, 702ca64a: rucni polozky) ho importuje z app; jen cteni
    sys.modules["app"] = appmod

    q = types.ModuleType("quotes")
    cnt = itertools.count(1)
    q.safe_stored_filename = lambda name: "%s%s" % (uuidlib.uuid4().hex, os.path.splitext(name)[1] or "")
    q._next_quote_number = lambda cur: next(cnt)
    q.QUOTE_PREFIX = "N-TEST-"
    q.PRIVATE_FILES_DIR = priv
    sys.modules["quotes"] = q
    d = types.ModuleType("drive")
    d.DRIVE_FILES_DIR = drive
    sys.modules["drive"] = d
    doc = types.ModuleType("documents")
    doc.SUPPLIER, doc.VAT_RATE, doc.SPAYD_CURRENCY_CODE = {}, 0.21, "CZK"
    sys.modules["documents"] = doc
    o = types.ModuleType("orders")
    o._resolve_toptrans_price = lambda *a, **k: None
    o._OrderCreateError = type("_OrderCreateError", (Exception,), {})
    o.create_order_from_scene_offer = lambda *a, **k: None
    sys.modules["orders"] = o
    pa = types.ModuleType("product_assemblies")
    pa._montaz_mista_map = lambda *a, **k: {}
    sys.modules["product_assemblies"] = pa
    w = types.ModuleType("weasyprint")
    w.HTML = None
    sys.modules["weasyprint"] = w

    for p in (os.path.join(CE.REPO, "api"), os.path.join(CE.REPO, "scripts", "v3d")):
        while p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
    sys.dont_write_bytecode = True
    import scene_offers  # noqa: F401
    import vandr_scene_offers
    return flask_app, audit, vandr_scene_offers


def uninstall_stubs():
    for n in _STUB_NAMES + _OWN_MODULES:
        sys.modules.pop(n, None)


def sha(b):
    return hashlib.sha256(b).hexdigest()
