#!/usr/bin/env python3
"""Hermeticky selftest univerzalniho importu FBX (api/universal_import.py).

!!! ROZPRACOVANO (2026-09-30, bot8) - NEDOKONCENA KOSTRA, ZATIM NIC NETESTUJE A NIKDY NEBEZELA !!!
Hotove jsou jen casti 1-2 (izolace prostredi + striktni FakeDB; jen syntakticky overeno).
Chybi: cast 3 (temp adresare, patch ui/lfi/appmod, Flask klient + login, GLB pomocnici,
fixtures katalogu), cast 4 (synteticka scena 18 meshu -> 13 dilu pres podstrceny
ui._run_extract_worker), testy (cisté funkce, matice opravneni, analyze/join/split/
merge-small/remove/draft, build vc. atomicity) a runner. Plan a ocekavane hodnoty:
handover bota8 "STAV bot8 k 2026-09-30" + skill import-fbx-scena. Test regrese
"varianta profilu" (profil_30x30_uzavreny -> scale 0.5, lic_peers) musi na kodu pred
opravou SELHAT.

Spusteni (z korene repa, VZDY pod venv - ma numpy/scipy/flask/pymysql):

    api/venv/bin/python3 scripts/2026-09-30_universal_import_selftest.py

Vystup: "N kontrol OK" a exit 0, jinak radky "CHYBA: ..." a exit 1.

PROC HERMETICKY (Robert: zadna testovaci data v produkci, nikdy):
  * env je dummy (DB_HOST=selftest.invalid ...), pymysql.connect je nahrazen
    funkci, ktera pokus o spojeni zaznamena a vyhodi chybu -> na pravou DB
    se nikdy nepripojime (kontroluje se, ze pokusu bylo 0);
  * "DB" je striktni FakeDB v tomto souboru: zna jen presne SQL, ktere import
    pouziva, kazdy jiny dotaz / neznamy sloupec je chyba. Emuluje sdilene
    pooled spojeni z app.get_conn() (close() = rollback, sekvence AUTO_INCREMENT
    se po rollbacku nevraci), DECIMAL (Decimal) a fetchall() jako tuple;
  * vsechny soubory (tokeny, GLB karet) jdou do temp adresare; repo se nemeni;
  * FBX worker je nahrazen synteticke scenou (13 dilu z 18 meshu), takze test
    nepotrebuje zadny FBX (volitelny smoke test s pravym workerem je na konci);
  * na pozadi se nespusti render-dozorce (vlakno z render_worker.py by po 60 s
    sahalo do DB) - pri importu app se Thread.start pro nej docasne potlaci.

STARE api/tmp_universal_import/selftest_*.py (bot8, 2026-09-2x) PISI DO PRODUKCNI
DB - nepouzivat, nevracet do gitu.

UIMP_API_OVERRIDE=<adresar> nacte api/*.py odjinud (pouziva mutacni skript
2026-09-30_universal_import_harness_mutace.py: zmutovana kopie universal_import.py).
"""
import os
import sys
import re
import io
import json
import copy
import math
import shutil
import struct
import tempfile
import threading
import traceback
import subprocess
from decimal import Decimal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.environ.get("UIMP_API_OVERRIDE") or os.path.join(REPO, "api")

try:
    import numpy as np
    import pymysql
except ImportError as _e:  # noqa: BLE001
    print(f"CHYBA: chybi zavislost ({_e}). Spust pod venv: api/venv/bin/python3 {sys.argv[0]}")
    sys.exit(2)

# --- izolace prostredi: dummy env (prebijeme i skutecne hodnoty) -------------
for _k, _v in {
    "FLASK_SECRET_KEY": "selftest-secret",
    "DB_HOST": "selftest.invalid", "DB_PORT": "3306",
    "DB_USER": "selftest", "DB_PASSWORD": "selftest", "DB_NAME": "selftest",
}.items():
    os.environ[_k] = _v

CONNECT_ATTEMPTS = []


def _no_connect(*a, **kw):
    CONNECT_ATTEMPTS.append((a, kw))
    raise RuntimeError("selftest: pokus o spojeni s databazi je zakazan")


pymysql.connect = _no_connect


def _listing(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return None


REPO_TMP_DIR = os.path.join(REPO, "api", "tmp_universal_import")
REPO_KAT_DIR = os.path.join(REPO, "webapp", "katalog")
REPO_SNAPSHOT = (_listing(REPO_TMP_DIR), _listing(REPO_KAT_DIR))

# render_worker.py pri importu startuje daemon "render-dozorce" (po 60 s sahne
# do DB/souboru) - pro selftest ho nechceme
_orig_thread_start = threading.Thread.start


def _guarded_start(self, *a, **kw):
    if self.name == "render-dozorce":
        return None
    return _orig_thread_start(self, *a, **kw)


threading.Thread.start = _guarded_start
try:
    sys.path.insert(0, API)
    import app as appmod
    import universal_import as ui
    import leg_fbx_import as lfi
    import dimension_match_fbx as dmf
finally:
    threading.Thread.start = _orig_thread_start

BASELINE_THREADS = sorted(t.name for t in threading.enumerate())
_S2 = math.sqrt(0.5)

# --- mini framework ---------------------------------------------------------
OK = 0
FAILS = []
SECTIONS = []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
        return True
    FAILS.append(msg)
    print(f"  CHYBA: {msg}")
    return False


def eq(actual, expected, msg):
    if actual == expected:
        return check(True, msg)
    return check(False, f"{msg}\n      ocekavano: {expected!r}\n      skutecne:  {actual!r}")


def near(actual, expected, tol, msg):
    try:
        good = all(abs(float(a) - float(b)) <= tol for a, b in zip(actual, expected)) and len(actual) == len(expected)
    except (TypeError, ValueError):
        good = False
    if good:
        return check(True, msg)
    return check(False, f"{msg}\n      ocekavano: {list(expected)!r} (+-{tol})\n      skutecne:  {actual!r}")


def section(name):
    def deco(fn):
        SECTIONS.append((name, fn))
        return fn
    return deco


# === FakeDB: striktni nahrada MySQL (jen SQL, ktere import skutecne pouziva) ===
CFG_COLS = ["id", "name", "layer", "material_label", "dim_x_mm", "dim_y_mm", "dim_z_mm", "weight_kg_approx",
            "price_czk_approx", "glb_file", "thumbnail_file", "price_source_url", "price_per_cut_czk",
            "color_hex", "visible_in_scene"]
PRODUCT_COLS = ["id", "name", "sku", "category_id", "category_path", "weight_g", "price_czk_placeholder",
                "glb_file", "thumbnail_file", "color_hex", "unit", "is_board_material", "board_sheet_width_mm",
                "board_sheet_height_mm", "accessory_conn_enabled", "uhelnik_pose", "stock_qty", "place_vertical",
                "attach_mode", "attach_offset_mm", "geo_faces_json", "attach_pose",
                # sloupce, ktere dotazy nevybiraji, ale DB je ma
                "slug", "visible_in_scene", "active", "is_archived", "cfg_dily_id", "length_mm", "width_mm",
                "height_mm", "dogus_image_schema_url"]


def _norm_sql(sql):
    sql = re.sub(r"--[^\n]*", "", sql)
    return re.sub(r"\s+", " ", sql).strip().rstrip(";").strip()


class FakeDB:
    INSERT_COLS = {
        "shop_products": {"category_id", "sku", "name", "slug", "unit", "visible_in_scene", "active", "glb_file"},
        "custom_shapes": {"name", "category_id", "data", "created_by", "is_public"},
        "audit_log": {"user_id", "action", "entity_type", "entity_id", "detail"},
    }

    def __init__(self):
        self.violations = []
        self.executed = []
        self.seq = {"shop_products": 5000, "custom_shapes": 700, "audit_log": 1}
        self.committed = {t: {} for t in ("app_users", "role_permissions", "cfg_dily", "shop_products",
                                          "custom_shapes", "audit_log")}
        self.pending = None
        self.conn = FakeConn(self)

    # --- transakce (kopie pri prvnim zapisu; sekvence se po rollbacku nevraci) ---
    def view(self):
        return self.pending if self.pending is not None else self.committed

    def write_view(self):
        if self.pending is None:
            self.pending = copy.deepcopy(self.committed)
        return self.pending

    def commit(self):
        if self.pending is not None:
            self.committed = self.pending
            self.pending = None

    def rollback(self):
        self.pending = None

    def next_id(self, table):
        self.seq[table] += 1
        return self.seq[table]

    def violation(self, msg):
        self.violations.append(msg)
        raise AssertionError("FakeDB: " + msg)

    def snapshot(self):
        return json.dumps(self.committed, sort_keys=True, default=str)

    def get_conn(self):
        return self.conn

    # --- fixtures (zapisuji primo do committed) ---
    def add_user(self, uid, role, active=1):
        self.committed["app_users"][uid] = {
            "id": uid, "email": f"u{uid}@selftest.invalid", "name": f"Uzivatel {uid}", "role": role,
            "active": active, "theme_admin": "light", "theme_shop": "light", "party_id": None}

    def set_perm(self, role, sect, action, allowed=1):
        self.committed["role_permissions"][(role, sect, action)] = {"allowed": allowed}

    def clear_perms(self):
        self.committed["role_permissions"] = {}

    def add_cfg(self, **kw):
        row = {c: None for c in CFG_COLS}
        row.update(layer="alu", visible_in_scene=1)
        row.update(kw)
        for c in ("dim_x_mm", "dim_y_mm", "dim_z_mm"):
            if row[c] is not None:
                row[c] = Decimal(str(row[c]))
        unknown = set(row) - set(CFG_COLS)
        if unknown:
            raise KeyError(unknown)
        self.committed["cfg_dily"][row["id"]] = row

    def add_product(self, **kw):
        row = {c: None for c in PRODUCT_COLS}
        row.update(is_archived=0, active=1, visible_in_scene=0, is_board_material=0, place_vertical=0)
        row.update(kw)
        for c in ("length_mm", "width_mm", "height_mm"):
            if row[c] is not None:
                row[c] = Decimal(str(row[c]))
        unknown = set(row) - set(PRODUCT_COLS)
        if unknown:
            raise KeyError(unknown)
        if row["id"] is None:
            row["id"] = self.next_id("shop_products")
        self.committed["shop_products"][row["id"]] = row
        return row["id"]

    def rows(self, table, where=None):
        out = [copy.deepcopy(r) for r in self.view()[table].values()]
        return [r for r in out if where is None or where(r)]

    # --- dispatch SQL ---
    @staticmethod
    def _project(cols, source, db):
        out = {}
        for expr in cols.split(","):
            m = re.match(r"^([\w.]+)(?: AS (\w+))?$", expr.strip())
            if not m:
                db.violation(f"nerozpoznany vyraz ve SELECT: {expr!r}")
            src, alias = m.group(1), m.group(2)
            if src not in source:
                db.violation(f"SELECT vybira neexistujici sloupec {src!r}")
            out[alias or src.split(".")[-1]] = copy.deepcopy(source[src])
        return out

    def run(self, cur, sql, params):
        q = _norm_sql(sql)
        self.executed.append(q)
        if params is None:
            p = ()
        elif isinstance(params, (list, tuple)):
            p = tuple(params)
        else:
            self.violation(f"parametry musi byt list/tuple, ne {type(params).__name__}: {q[:80]}")
        for x in p:
            if isinstance(x, (dict, set, np.ndarray, np.generic)):
                self.violation(f"nepovoleny typ parametru {type(x).__name__} v: {q[:80]}")
        if q.count("%s") != len(p):
            self.violation(f"pocet %s ({q.count('%s')}) != pocet parametru ({len(p)}): {q[:100]}")
        cur.rows, cur.rowcount = [], -1
        v = self.view()

        m = re.match(r"^SELECT (id, email, name, role, active, theme_admin, theme_shop, party_id) FROM app_users WHERE id=%s$", q)
        if m:
            u = v["app_users"].get(p[0])
            cur.rows = [self._project(m.group(1), u, self)] if u else []
            return
        if re.match(r"^SELECT allowed FROM role_permissions WHERE role=%s AND section=%s AND action=%s$", q):
            r = v["role_permissions"].get(tuple(p))
            cur.rows = [copy.deepcopy(r)] if r else []
            return
        m = re.match(r"^SELECT (.+?) FROM cfg_dily d LEFT JOIN \( SELECT cfg_dily_id, MIN\(id\) AS shop_product_id "
                     r"FROM shop_products WHERE active=1 AND is_archived=0 AND cfg_dily_id IS NOT NULL GROUP BY cfg_dily_id \) "
                     r"spm ON spm\.cfg_dily_id = d\.id LEFT JOIN shop_products sp ON sp\.id = spm\.shop_product_id "
                     r"ORDER BY d\.layer, d\.name$", q)
        if m:
            cfg = sorted(v["cfg_dily"].values(), key=lambda r: ((r["layer"] or "").lower(), (r["name"] or "").lower()))
            for d in cfg:
                twins = [s for s in v["shop_products"].values()
                         if s["cfg_dily_id"] == d["id"] and s["active"] == 1 and s["is_archived"] == 0]
                twin = min(twins, key=lambda s: s["id"]) if twins else None
                src = {f"d.{c}": d[c] for c in CFG_COLS}
                src["spm.shop_product_id"] = twin["id"] if twin else None
                for c in PRODUCT_COLS:
                    src[f"sp.{c}"] = twin[c] if twin else None
                cur.rows.append(self._project(m.group(1), src, self))
            cur.rowcount = len(cur.rows)
            return
        m = re.match(r"^SELECT (.+?) FROM shop_products WHERE visible_in_scene=1 AND glb_file IS NOT NULL ORDER BY name$", q)
        if m:
            prods = [s for s in v["shop_products"].values() if s["visible_in_scene"] == 1 and s["glb_file"] is not None]
            for s in sorted(prods, key=lambda r: (r["name"] or "").lower()):
                cur.rows.append(self._project(m.group(1), {c: s[c] for c in PRODUCT_COLS}, self))
            cur.rowcount = len(cur.rows)
            return
        if q.startswith("SELECT cb.id, cb.name AS body_name") and "FROM car_bodies cb" in q:
            return
        m = re.match(r"^SELECT id FROM shop_products WHERE slug=%s( AND id<>%s)?$", q)
        if m:
            cur.rows = [{"id": s["id"]} for s in v["shop_products"].values()
                        if s["slug"] == p[0] and (not m.group(1) or s["id"] != p[1])]
            return
        if re.match(r"^SELECT sku FROM shop_products WHERE sku IN \(%s(,%s)*\)$", q):
            want = {str(x).lower() for x in p}
            cur.rows = [{"sku": s["sku"]} for s in v["shop_products"].values() if (s["sku"] or "").lower() in want]
            return
        if re.match(r"^SELECT id, length_mm, width_mm, height_mm FROM shop_products WHERE id IN \(%s(,%s)*\)$", q):
            cur.rows = [{c: copy.deepcopy(s[c]) for c in ("id", "length_mm", "width_mm", "height_mm")}
                        for s in v["shop_products"].values() if s["id"] in p]
            return
        if q.startswith("INSERT INTO "):
            self._insert(cur, q, p)
            return
        if re.match(r"^UPDATE shop_products SET glb_file=%s WHERE id=%s$", q):
            w = self.write_view()
            row = w["shop_products"].get(p[1])
            cur.rowcount = 1 if row else 0
            if row:
                row["glb_file"] = p[0]
            return
        self.violation(f"nepovoleny SQL (selftest zna jen dotazy importu): {q[:160]}")

    def _insert(self, cur, q, p):
        m = re.match(r"^INSERT INTO (\w+) \(([\w, ]+)\) VALUES \((.+)\)$", q)
        if not m:
            self.violation(f"nerozpoznany INSERT: {q[:120]}")
        table = m.group(1)
        cols = [c.strip() for c in m.group(2).split(",")]
        vals = [x.strip() for x in m.group(3).split(",")]
        if table not in self.INSERT_COLS:
            self.violation(f"INSERT do nezname tabulky {table}")
        if set(cols) - self.INSERT_COLS[table]:
            self.violation(f"INSERT {table}: neznamy sloupec {sorted(set(cols) - self.INSERT_COLS[table])}")
        if len(cols) != len(vals):
            self.violation(f"INSERT {table}: {len(cols)} sloupcu, {len(vals)} hodnot")
        it = iter(p)
        row = {}
        for c, tok in zip(cols, vals):
            if tok == "%s":
                val = next(it)
            elif re.match(r"^'[^']*'$", tok):
                val = tok[1:-1]
            elif re.match(r"^-?\d+$", tok):
                val = int(tok)
            elif tok.upper() == "NULL":
                val = None
            else:
                self.violation(f"INSERT {table}: neznamy literal {tok!r}")
            row[c] = val
        if next(it, self) is not self:
            self.violation(f"INSERT {table}: zbyly parametry")
        w = self.write_view()
        if table == "shop_products":
            for c in ("sku", "name", "slug", "glb_file", "unit"):
                if not isinstance(row.get(c), str) or not row[c]:
                    self.violation(f"shop_products.{c} musi byt neprazdny retezec, je {row.get(c)!r}")
            if row.get("category_id") is not None and not isinstance(row["category_id"], int):
                self.violation(f"shop_products.category_id musi byt int/None, je {row['category_id']!r}")
            for s in w["shop_products"].values():
                if (s["sku"] or "").lower() == row["sku"].lower():
                    raise pymysql.err.IntegrityError(1062, f"Duplicate entry '{row['sku']}' for key 'sku'")
                if s["slug"] is not None and s["slug"] == row["slug"]:
                    raise pymysql.err.IntegrityError(1062, f"Duplicate entry '{row['slug']}' for key 'slug'")
            full = {c: None for c in PRODUCT_COLS}
            full.update(is_archived=0, is_board_material=0, place_vertical=0)
            full.update(row)
            full["id"] = self.next_id(table)
            w[table][full["id"]] = full
        elif table == "custom_shapes":
            if not isinstance(row.get("name"), str) or not row["name"]:
                self.violation("custom_shapes.name musi byt neprazdny retezec")
            if not isinstance(row.get("data"), str):
                self.violation("custom_shapes.data musi byt JSON retezec (ne dict/list)")
            json.loads(row["data"])
            full = dict(row)
            full["id"] = self.next_id(table)
            w[table][full["id"]] = full
        else:
            if row.get("detail") is not None and not isinstance(row["detail"], str):
                self.violation("audit_log.detail musi byt str/None (dict/list se musi predem prevest na JSON)")
            full = dict(row)
            full["id"] = self.next_id(table)
            w[table][full["id"]] = full
        cur.lastrowid = full["id"]
        cur.rowcount = 1


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.rows = []
        self.lastrowid = 0
        self.rowcount = -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def execute(self, sql, params=None):
        self.db.run(self, sql, params)
        return self.rowcount

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        out, self.rows = tuple(self.rows), []   # pymysql vraci tuple, ne list
        return out


class FakeConn:
    """Sdilene pooled spojeni: close() = rollback (viz app._PooledConn)."""

    def __init__(self, db):
        self._db = db

    def cursor(self, *a, **kw):
        return FakeCursor(self._db)

    def commit(self):
        self._db.commit()

    def rollback(self):
        self._db.rollback()

    def close(self):
        self._db.rollback()

    def ping(self, *a, **kw):
        return None
