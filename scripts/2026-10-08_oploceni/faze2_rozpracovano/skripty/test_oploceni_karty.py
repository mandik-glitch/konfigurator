#!/usr/bin/env python3
"""Test zapisu KARET (zaloz_kartu_oploceni.py, zaloz_karty_vyplni.py --apply) proti FALESNE DB (bot8, 2026-10-08, faze 2): zadne spojeni na produkcni DB, zadny dotaz ani zapis.

Proc: --apply obou skriptu poustí az koordinator na ZIVE DB; tenhle test projde jeho logiku predem: jaky SQL se posila (jen povolene prikazy; kazdy dalsi = chyba testu), sloupce a delky proti schematu
shop_products (snimek z 2026-10-08, ZNEJ jen pri behu s DB_* v prostredi se porovna i se zivym schematem, cte se jen SHOW COLUMNS), unikatni SKU a slug, NOT NULL, transakce (commit / rollback),
compare-and-set u app_settings, idempotence (druhy beh nic nezapise), cisty rollback (zadna karta, zadny audit, zadne nastaveni, GLB smazane), obnova po castecnem behu.
Spusteni (hermeticky, bez DB):  api/venv/bin/python3 scripts/2026-10-08_oploceni/test_oploceni_karty.py"""
import copy
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.environ.get("OPLOCENI_API") or os.path.join(REPO, "api")
sys.path.insert(0, HERE)
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.dont_write_bytecode = True
import oploceni_konfigurator as O  # noqa: E402
import zaloz_karty_vyplni as ZV  # noqa: E402
import zaloz_kartu_oploceni as ZK  # noqa: E402

vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)[:500]))
    if not p and os.environ.get("OPLOCENI_STOP_PRVNI"):                 # mutacni beh: staci prvni selhani (mutace je chycena)
        sys.exit(1)


# snimek schematu shop_products (SHOW COLUMNS, 2026-10-08): sloupec -> (typ, NULL?, default); jen to, co test potrebuje
SCHEMA = {"id": ("int", "NO", None), "category_id": ("int", "YES", None), "sku": ("varchar(150)", "NO", None), "name": ("varchar(200)", "NO", None), "slug": ("varchar(255)", "YES", None),
          "description": ("text", "YES", None), "unit": ("varchar(20)", "NO", "ks"), "price_czk_placeholder": ("decimal(10,2)", "YES", None), "stock_qty": ("int", "NO", "0"),
          "active": ("tinyint(1)", "NO", "1"), "is_archived": ("tinyint(1)", "NO", "0"), "availability_text": ("varchar(200)", "YES", "3 - 5 týdnů"), "price_visible_default": ("tinyint(1)", "NO", "1"),
          "hover_show_price": ("tinyint(1)", "NO", "1"), "hover_show_availability": ("tinyint(1)", "NO", "0"), "has_variants": ("tinyint(1)", "NO", "0"), "variant_count": ("int", "NO", "0"),
          "has_set_items": ("tinyint(1)", "NO", "0"), "glb_file": ("varchar(255)", "YES", None), "color_hex": ("varchar(7)", "YES", None), "is_board_material": ("tinyint(1)", "NO", "0"),
          "is_profile_material": ("tinyint(1)", "NO", "0"), "board_sheet_width_mm": ("int", "YES", None), "board_sheet_height_mm": ("int", "YES", None), "visible_in_scene": ("tinyint(1)", "NO", "0"),
          "is_supplier_item": ("tinyint(1)", "NO", "0"), "meta_title": ("varchar(255)", "YES", None), "meta_description": ("varchar(500)", "YES", None), "place_vertical": ("tinyint(1)", "NO", "0"),
          "attach_offset_mm": ("decimal(6,2)", "YES", "0.00"), "nativni_material": ("tinyint(1)", "NO", "0"), "render_material_key": ("varchar(40)", "YES", None)}


def zive_schema():
    """Zive schema shop_products (jen cte): {sloupec: (typ, NULL?, default)} nebo None, kdyz DB neni k dispozici."""
    if not os.environ.get("DB_HOST"):
        return None
    import threading
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    try:
        import app as appmod
    finally:
        threading.Thread.start = _o
    cur = appmod.get_conn().cursor()
    cur.execute("SHOW COLUMNS FROM shop_products")
    out = {c["Field"]: (c["Type"], c["Null"], c["Default"]) for c in cur.fetchall()}
    appmod.get_conn().rollback()
    return out


class DbChyba(Exception):
    pass


class FalesnaDB:
    """Minimalni falesna DB: jen prikazy, ktere oba skripty posilaji (kazdy jiny = AssertionError), transakce se snimkem, unikatni sku / slug, NOT NULL, delky varcharu, AUTO_INCREMENT, ktery se pri rollbacku nevraci."""

    def __init__(self, produkty=None, nastaveni=None, kategorie=(149, 150, 207), auto_inc=5361, schema=None):
        self.schema = schema or SCHEMA
        self.produkty = copy.deepcopy(produkty) if produkty is not None else [self.radek(id=4933, sku="Laminodeska.SEDA.18", name="Laminovaná dřevotříska 18mm", unit="m2", category_id=207, availability_text="3 - 5 týdnů",
                                                                                      price_visible_default=1, hover_show_price=1, hover_show_availability=0, place_vertical=0, attach_offset_mm=0, is_board_material=1)]
        self.nastaveni = dict(nastaveni or {})
        self.audit = []
        self.kategorie = set(kategorie)
        self.auto_inc = auto_inc
        self.sql, self.commity, self.rollbacky = [], 0, 0
        self.hook_for_update = None                                  # funkce(db) zavolana po SELECT ... FOR UPDATE nad app_settings (simulace soubehu)
        self.selhani_insertu = None                                  # cislo INSERTu do shop_products (od 1), ktery vrati rowcount 0
        self.spojeni = []

    def radek(self, **kw):
        r = {c: (d if d is None else (int(d) if re.fullmatch(r"-?\d+", str(d)) else d)) for c, (t, n, d) in self.schema.items()}
        r.update(kw)
        return r

    def snimek(self):
        return copy.deepcopy((self.produkty, self.nastaveni, self.audit))

    def obnov(self, s):
        self.produkty, self.nastaveni, self.audit = copy.deepcopy(s)

    def conn(self):
        c = FalesneSpojeni(self)
        self.spojeni.append(c)
        return c

    def cizi_zapis(self, klic, hodnota):
        """Zapis z JINE relace (uz potvrzeny): vidi ho stav DB i snimky vsech spojeni, takze rollback tohohle spojeni ho nevrati."""
        self.nastaveni[klic] = hodnota
        for c in self.spojeni:
            c.s[1][klic] = hodnota


class FalesneSpojeni:
    def __init__(self, db):
        self.db, self.s = db, db.snimek()

    def cursor(self):
        return FalesnyKurzor(self.db)

    def commit(self):
        self.db.commity += 1
        self.s = self.db.snimek()

    def rollback(self):
        self.db.rollbacky += 1
        self.db.obnov(self.s)


class FalesnyKurzor:
    def __init__(self, db):
        self.db, self.rows, self.rowcount, self.lastrowid = db, [], 0, None

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    def _vyber(self, podm):
        return [copy.deepcopy(r) for r in self.db.produkty if podm(r)]

    def execute(self, sql, params=()):
        db = self.db
        s = re.sub(r"\s+", " ", sql.strip())
        db.sql.append((s, tuple(params)))
        self.rows, self.rowcount = [], 0
        m = None
        if s.startswith("SELECT AUTO_INCREMENT AS a FROM information_schema.TABLES"):
            self.rows = [{"a": db.auto_inc}]
        elif s == "SELECT id, sku, name, slug, active, is_archived FROM shop_products WHERE sku=%s":
            self.rows = self._vyber(lambda r: r["sku"] == params[0])
        elif s == "SELECT id, sku, name, active FROM shop_products WHERE sku=%s OR name=%s":
            self.rows = self._vyber(lambda r: r["sku"] == params[0] or r["name"] == params[1])
        elif s == "SELECT * FROM shop_products WHERE id=%s":
            self.rows = self._vyber(lambda r: r["id"] == params[0])
        elif s == "SELECT id, sku, name, slug, active FROM shop_products WHERE id=%s":
            self.rows = self._vyber(lambda r: r["id"] == params[0])
        elif s == "SELECT id, sku, active, is_board_material, visible_in_scene, glb_file, unit FROM shop_products WHERE id=%s":
            self.rows = self._vyber(lambda r: r["id"] == params[0])
        elif s == "SELECT id FROM content_categories WHERE id=%s":
            self.rows = [{"id": params[0]}] if params[0] in db.kategorie else []
        elif s in ("SELECT setting_value FROM app_settings WHERE setting_key=%s", "SELECT setting_value FROM app_settings WHERE setting_key=%s FOR UPDATE"):
            self.rows = [{"setting_value": db.nastaveni[params[0]]}] if params[0] in db.nastaveni else []
            if s.endswith("FOR UPDATE") and db.hook_for_update:
                db.hook_for_update(db)
        elif s.startswith("INSERT INTO shop_products ("):
            m = re.fullmatch(r"INSERT INTO shop_products \(([\w, ]+)\) VALUES \((.+)\)", s)
            assert m, f"neocekavany tvar INSERTu: {s[:120]}"
            sloupce = [c.strip() for c in m.group(1).split(",")]
            hodnoty = [h.strip() for h in m.group(2).split(",")]
            assert len(sloupce) == len(hodnoty) and hodnoty.count("%s") == len(params), (len(sloupce), len(hodnoty), len(params))
            it = iter(params)
            data = {c: (next(it) if h == "%s" else int(h)) for c, h in zip(sloupce, hodnoty)}
            assert len(set(sloupce)) == len(sloupce), "sloupec dvakrat v INSERTu"
            for c in data:
                assert c in db.schema, f"neexistujici sloupec shop_products.{c}"
            for c, (t, n, d) in db.schema.items():
                if n == "NO" and d is None and c != "id" and data.get(c) is None:
                    raise DbChyba(f"sloupec {c} je NOT NULL bez defaultu")
            for c, v in data.items():
                mm = re.fullmatch(r"varchar\((\d+)\)", db.schema[c][0])
                if mm and v is not None and len(str(v)) > int(mm.group(1)):
                    raise DbChyba(f"hodnota sloupce {c} ma {len(str(v))} znaku, limit {mm.group(1)}")
            if any(r["sku"] == data["sku"] for r in db.produkty):
                raise DbChyba(f"duplicitni sku {data['sku']}")
            if data.get("slug") is not None and any(r["slug"] == data["slug"] for r in db.produkty):
                raise DbChyba(f"duplicitni slug {data['slug']}")
            n_ins = sum(1 for q, _ in db.sql if q.startswith("INSERT INTO shop_products ("))
            novy = db.radek(**data)
            novy["id"] = db.auto_inc
            db.auto_inc += 1                                         # AUTO_INCREMENT se pri rollbacku nevraci
            if db.selhani_insertu == n_ins:
                self.rowcount = 0
                return
            db.produkty.append(novy)
            self.rowcount, self.lastrowid = 1, novy["id"]
        elif s == "UPDATE shop_products SET glb_file=%s WHERE id=%s":
            for r in db.produkty:
                if r["id"] == params[1]:
                    r["glb_file"] = params[0]
                    self.rowcount = 1
        elif s == "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)":
            assert len(params) == 5 and len(params[1]) <= 30 and len(params[2]) <= 40, params
            db.audit.append(tuple(params))
            self.rowcount = 1
        elif s == "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s)":
            if params[0] in db.nastaveni:
                raise DbChyba("duplicitni setting_key")
            db.nastaveni[params[0]] = params[1]
            self.rowcount = 1
        elif s == "UPDATE app_settings SET setting_value=%s WHERE setting_key=%s AND setting_value=%s":
            if db.nastaveni.get(params[1]) == params[2]:
                db.nastaveni[params[1]] = params[0]
                self.rowcount = 1
        else:
            raise AssertionError(f"POVOLENY JEN ZNAME SQL, ale skript poslal: {s[:200]}")


def slug_fn_pro(db):
    def slug(cur, nazev):
        zaklad = re.sub(r"[^a-z0-9]+", "-", nazev.lower()).strip("-") or "karta"
        s, i = zaklad, 1
        while any(r["slug"] == s for r in db.produkty):
            i += 1
            s = f"{zaklad}-{i}"
        return s
    return slug


# ======================================================================================================================================================================================================
print("== A zaloz_kartu_oploceni.py")
ZK_SQL_POVOLENE = True
db = FalesnaDB(nastaveni={"configurator_products": json.dumps({"4934": "stul_system30", "5353": "stul_system45"}, sort_keys=True)})
conn = db.conn()
cur = conn.cursor()
karta, mapa, ostatni = ZK.nacti_stav(cur)
over("A1 nacti_stav: karta neexistuje, mapa zustava, zadni jini nositele receptu", karta is None and mapa == {"4934": "stul_system30", "5353": "stul_system45"} and ostatni == {})
db_o = FalesnaDB(nastaveni={"configurator_products": json.dumps({"123": "oploceni_kryt", "4934": "stul_system30"})})
db_o.produkty.append(db_o.radek(id=5000, sku="OPLOCENI.KRYT.KONF", name="x", slug="x", active=0))
k_, m_, o_ = ZK.nacti_stav(db_o.conn().cursor())
over("A1b nacti_stav: jini nositele receptu jsou hlaseni (nova karta: #123; existujici #5000: take #123, ne ona sama)", o_ == {"123": "oploceni_kryt"} and k_["id"] == 5000
     and ZK.nacti_stav(FalesnaDB(nastaveni={"configurator_products": json.dumps({"123": "oploceni_kryt"})}).conn().cursor())[2] == {"123": "oploceni_kryt"}
     and ZK.nacti_stav(FalesnaDB(nastaveni={"configurator_products": json.dumps({"5000": "oploceni_kryt"})}, produkty=[db_o.produkty[1]]).conn().cursor())[2] == {})
over("A2 plan_text popisuje INSERT neaktivni karty a compare-and-set", "INSERT neaktivni karty" in ZK.plan_text(None) and "compare-and-set" in ZK.plan_text(None) and "existujici kartu #7" in ZK.plan_text({"id": 7}))
pid = ZK.zapis(conn, cur, slug_fn_pro(db), karta)
nova = [r for r in db.produkty if r["id"] == pid][0]
over("A3 zapis: karta vznikla NEAKTIVNI (active=0), SKU, nazev, jednotka ks, bez kategorie a ceny, slug, popis a meta texty",
     nova["sku"] == "OPLOCENI.KRYT.KONF" and nova["active"] == 0 and nova["unit"] == "ks" and nova["category_id"] is None and nova["price_czk_placeholder"] is None and bool(nova["slug"])
     and nova["name"] == ZK.NAZEV and nova["description"] == ZK.POPIS and nova["meta_title"] == ZK.META_T and nova["meta_description"] == ZK.META_D and nova["is_archived"] == 0, nova)
over("A4 configurator_products: pribyl {id: oploceni_kryt}, ostatni recepty beze zmeny", json.loads(db.nastaveni["configurator_products"]) == {"4934": "stul_system30", "5353": "stul_system45", str(pid): "oploceni_kryt"})
over("A5 audit_log: 2 radky (vytvoreni karty, zmena nastaveni) s ID karty", [(a[1], a[2], a[3]) for a in db.audit] == [("create", "shop_product", pid), ("update", "app_settings", None)] and f'"{pid}": "oploceni_kryt"' in db.audit[1][4], db.audit)
over("A6 transakce: 1 commit, 0 rollbacku; zadny jiny SQL nez povoleny (fake by spadla)", db.commity == 1 and db.rollbacky == 0)
over("A7 over_zapis: neaktivni karta + recept v nastaveni", ZK.over_zapis(db.conn().cursor(), pid)[0]["active"] == 0)
n_sql = len(db.sql)
pid2 = ZK.zapis(conn, cur, slug_fn_pro(db), ZK.nacti_stav(cur)[0])
over("A8 idempotence: druhy beh pouzije stejnou kartu a nezapise nic (zadny INSERT / UPDATE / audit)", pid2 == pid and len(db.audit) == 2 and len([r for r in db.produkty if r["sku"] == ZK.SKU]) == 1
     and not [q for q, _ in db.sql[n_sql:] if q.startswith(("INSERT", "UPDATE"))])

db = FalesnaDB(nastaveni={"configurator_products": json.dumps({"4934": "stul_system30"})}, produkty=None)
db.produkty.append(db.radek(id=5000, sku="OPLOCENI.KRYT.KONF", name="Ruční karta", slug="rucni", active=0))
conn = db.conn(); cur = conn.cursor()
karta, mapa, ostatni = ZK.nacti_stav(cur)
pid = ZK.zapis(conn, cur, slug_fn_pro(db), karta)
over("A9 existujici karta bez zaznamu v nastaveni: nova se nezaklada, jen se doplni nastaveni (+1 audit), karta se nemeni", pid == 5000 and len([r for r in db.produkty if r["sku"] == ZK.SKU]) == 1
     and json.loads(db.nastaveni["configurator_products"]) == {"4934": "stul_system30", "5000": "oploceni_kryt"} and len(db.audit) == 1 and db.audit[0][1] == "update"
     and [r for r in db.produkty if r["id"] == 5000][0]["name"] == "Ruční karta")

db = FalesnaDB()                                            # nastaveni configurator_products vubec neexistuje
conn = db.conn(); cur = conn.cursor()
pid = ZK.zapis(conn, cur, slug_fn_pro(db), None)
over("A10 chybi nastaveni configurator_products: vytvori se (INSERT), obsahuje jen novy recept", json.loads(db.nastaveni["configurator_products"]) == {str(pid): "oploceni_kryt"})

db = FalesnaDB(nastaveni={"configurator_products": json.dumps({"4934": "stul_system30"})})
db.hook_for_update = lambda d: d.cizi_zapis("configurator_products", json.dumps({"4934": "stul_system30", "9999": "cizi"}))   # soubezny zapis jine relace po cteni
conn = db.conn(); cur = conn.cursor()
pred = db.snimek()
try:
    ZK.zapis(conn, cur, slug_fn_pro(db), None)
    chyba = None
except RuntimeError as e:
    chyba = str(e)
over("A11 compare-and-set: nastaveni zmenene mezi cteni a zapisem = chyba, ROLLBACK, zadna karta, zadny audit", chyba and "rowcount=0" in chyba and "ROLLBACK" in chyba and db.rollbacky == 1 and db.commity == 0
     and [r["sku"] for r in db.produkty] == ["Laminodeska.SEDA.18"] and db.audit == [] and json.loads(db.nastaveni["configurator_products"]) == {"4934": "stul_system30", "9999": "cizi"}, (chyba, db.audit))

db = FalesnaDB(nastaveni={"configurator_products": json.dumps({"4934": "stul_system30"})})
db.selhani_insertu = 1
conn = db.conn(); cur = conn.cursor()
try:
    ZK.zapis(conn, cur, slug_fn_pro(db), None)
    chyba = None
except RuntimeError as e:
    chyba = str(e)
over("A12 INSERT s rowcount 0 = ROLLBACK, nic se nezapsalo", chyba and "ROLLBACK" in chyba and db.commity == 0 and db.rollbacky == 1 and len(db.produkty) == 1 and db.audit == [], chyba)

db = FalesnaDB(nastaveni={"configurator_products": json.dumps({"4934": "stul_system30"})})
slug_kolize = slug_fn_pro(db)(None, ZK.NAZEV)
db.produkty.append(db.radek(id=4000, sku="JINE", name="x", slug=slug_kolize))                    # slug, ktery by karta dostala, uz nekdo ma
conn = db.conn(); cur = conn.cursor()
pid = ZK.zapis(conn, cur, slug_fn_pro(db), None)
over("A13 slug se vybira volny (kolize s cizim slugem nezpusobi chybu, karta dostane jiny)", [r for r in db.produkty if r["id"] == pid][0]["slug"] == slug_kolize + "-2", [r["slug"] for r in db.produkty])
over("A14 delky textu karty se vejdou do sloupcu (name <= 200, meta_title <= 255, meta_description <= 500, sku <= 150)", len(ZK.NAZEV) <= 200 and len(ZK.META_T) <= 255 and len(ZK.META_D) <= 500 and len(ZK.SKU) <= 150)

# main(): predpripraveny fake pripojovac
import io  # noqa: E402
from contextlib import redirect_stdout  # noqa: E402
db = FalesnaDB(nastaveni={"configurator_products": json.dumps({"4934": "stul_system30"})})
sdilene = db.conn()
ZK.pripoj = lambda: (lambda: sdilene, slug_fn_pro(db))
buf = io.StringIO()
with redirect_stdout(buf):
    rc_nahled = ZK.main(["x"])
over("A15 main() bez --apply: nahled, nic nezapsano (zadny INSERT / UPDATE), navratovy kod 0", rc_nahled == 0 and "nahled, nic nezapsano" in buf.getvalue() and not [q for q, _ in db.sql if q.startswith(("INSERT", "UPDATE"))] and db.commity == 0)
buf = io.StringIO()
with redirect_stdout(buf):
    rc = ZK.main(["x", "--apply"])
over("A16 main() --apply: zapsano a overeno po commitu, vypise OPLOCENI_KARTA_ID, kod 0", rc == 0 and "OPLOCENI_KARTA_ID" in buf.getvalue() and "zapsano a overeno po commitu" in buf.getvalue() and db.commity == 1, buf.getvalue()[-300:])
ZK.pripoj = lambda: (lambda: sdilene, None)
buf = io.StringIO()
with redirect_stdout(buf):
    rc = ZK.main(["x", "--apply"])
over("A17 main() --apply bez systemd-run (bez slug_fn / DB_*): odmitne, kod 2, nic nezapise", rc == 2 and "CHYBA" in buf.getvalue() and db.commity == 1)

# ======================================================================================================================================================================================================
print("== B zaloz_karty_vyplni.py")
tmp = tempfile.mkdtemp(prefix="test_karty_")


def glb_zapis_do(slozka, spadni_na=None):
    volani = []

    def f(cesta, tloustka):
        volani.append((cesta, tloustka))
        if spadni_na is not None and len(volani) == spadni_na:
            raise OSError("disk plny")
        with open(cesta, "wb") as fh:
            fh.write(b"glTF" + str(tloustka).encode())
    f.volani = volani
    return f


def soubory(slozka):
    return sorted(os.listdir(slozka))


db = FalesnaDB()
conn = db.conn(); cur = conn.cursor()
dalsi, existujici, radky = ZV.nacti_existujici(cur)
over("B1 nacti_existujici: dalsi ID z AUTO_INCREMENT, zadna z 5 karet neexistuje, vypis ma radek na kazdy typ", dalsi == 5361 and all(v == [] for v in existujici.values()) and len(existujici) == 5 and len([x for x in radky if "[NE]" in x]) == 5, radky[:2])
slozka = os.path.join(tmp, "b2"); os.makedirs(slozka)
gz = glb_zapis_do(slozka)
nove = ZV.zapis(conn, cur, slug_fn_pro(db), slozka, None, existujici, gz)
over("B2 zapis: 5 karet v poradi 5361..5365, mapa typ -> id", nove == {"pc_cira": 5361, "pc_koura": 5362, "plexi": 5363, "sit": 5364, "plna": 5365}, nove)
karty = {r["sku"]: r for r in db.produkty if r["sku"].startswith("OPL-")}
over("B3 karty NEAKTIVNI, deska, ve scene, GLB product_<id>.glb, jednotka m2, orientacni cena, bez kategorie, barva, tabule",
     len(karty) == 5 and all(k["active"] == 0 and k["is_board_material"] == 1 and k["visible_in_scene"] == 1 and k["unit"] == "m2" and k["category_id"] is None and k["is_archived"] == 0 and k["glb_file"] == f"product_{k['id']}.glb" for k in karty.values())
     and karty["OPL-PC-CIRY-04"]["price_czk_placeholder"] == "1150.00" and karty["OPL-SIT-03"]["board_sheet_width_mm"] == 1000 and karty["OPL-SIT-03"]["board_sheet_height_mm"] == 2000
     and karty["OPL-AL-KOMPOZIT-03"]["color_hex"] == "#a0a4a8" and all(k["render_material_key"] is None and k["nativni_material"] == 0 for k in karty.values()), {k: (v["active"], v["glb_file"]) for k, v in karty.items()})
over("B4 vzor poli z laminodesky #4933 (dostupnost, zobrazeni ceny, place_vertical, attach_offset)", all(k["availability_text"] == "3 - 5 týdnů" and k["price_visible_default"] == 1 and k["hover_show_price"] == 1 and k["hover_show_availability"] == 0 for k in karty.values()))
over("B5 soubory GLB vznikly (5 ks, jmeno podle id) a maji tloustku podle typu", soubory(slozka) == [f"product_{i}.glb" for i in range(5361, 5366)] and [t for _, t in gz.volani] == [4.0, 4.0, 5.0, 3.0, 3.0], gz.volani)
over("B6 audit_log: 5x create karty vyplne + 1x update nastaveni; nastaveni oploceni_karty_vyplni = mapa", [(a[1], a[2]) for a in db.audit] == [("create", "shop_product")] * 5 + [("update", "app_settings")] and json.loads(db.nastaveni["oploceni_karty_vyplni"]) == nove)
over("B7 transakce: jeden commit, zadny rollback; nazvy karet a SKU jsou unikatni (fake unikatnost hlida)", db.commity == 1 and db.rollbacky == 0 and len({k["slug"] for k in karty.values()}) == 5)
fake_ctx = lambda c: {"parts": {f"product_{i}": {"is_board_material": True} for i in nove.values()}}
mapa_db = ZV.over_zapis(db.conn().cursor(), nove, slozka, fake_ctx)
over("B8 over_zapis: karty, soubory a cenovy kontext sedi, vrati mapu z DB", mapa_db == nove)
try:
    ZV.over_zapis(db.conn().cursor(), nove, slozka, lambda c: {"parts": {}})
    chyba = None
except AssertionError as e:
    chyba = str(e)
over("B9 over_zapis: karta mimo cenovy kontext = chyba overeni", chyba and "cenovem kontextu" in chyba, chyba)
import os as _os  # noqa: E402
_os.remove(_os.path.join(slozka, f"product_{nove['sit']}.glb"))
try:
    ZV.over_zapis(db.conn().cursor(), nove, slozka, fake_ctx)
    chyba = None
except AssertionError as e:
    chyba = str(e)
over("B9b over_zapis: chybejici soubor GLB = chyba overeni", chyba and "product_" in chyba, chyba)
with open(_os.path.join(slozka, f"product_{nove['sit']}.glb"), "wb") as fh:
    fh.write(b"glTF")
n_sql = len(db.sql)
d2, ex2, _ = ZV.nacti_existujici(db.conn().cursor())
nove2 = ZV.zapis(conn, cur, slug_fn_pro(db), slozka, None, ex2, glb_zapis_do(slozka))
over("B10 idempotence: druhy beh nic nezalozi ani nezapise (zadny INSERT / UPDATE), vrati stejne ID, soubory beze zmeny", nove2 == nove and not [q for q, _ in db.sql[n_sql:] if q.startswith(("INSERT", "UPDATE"))] and len(db.audit) == 6 and len(soubory(slozka)) == 5)

# castecny beh: 2 karty uz existuji (spravne SKU), 3 chybi; nastaveni ma stary zaznam jineho typu
db = FalesnaDB(nastaveni={"oploceni_karty_vyplni": json.dumps({"pc_cira": 100, "sit": 101})})
db.produkty.append(db.radek(id=100, sku="OPL-PC-CIRY-04", name="Polykarbonátová deska čirá 4mm", slug="pc", active=0, unit="m2"))
db.produkty.append(db.radek(id=101, sku="OPL-SIT-03", name="Svařovaná síť pozinkovaná – výplň do drážky", slug="sit", active=0, unit="m2"))
conn = db.conn(); cur = conn.cursor()
dalsi, existujici, radky = ZV.nacti_existujici(cur)
over("B11 castecny stav: nacti_existujici najde 2 karty podle SKU", [bool(existujici[t]) for t in ("pc_cira", "pc_koura", "plexi", "sit", "plna")] == [True, False, False, True, False] and len([x for x in radky if "ANO:" in x]) == 2)
slozka = os.path.join(tmp, "b11"); os.makedirs(slozka)
nove = ZV.zapis(conn, cur, slug_fn_pro(db), slozka, None, existujici, glb_zapis_do(slozka))
over("B12 castecny beh: zaklada jen chybejici 3 karty, existujici zustanou (100, 101), mapa obsahuje vsech 5", nove["pc_cira"] == 100 and nove["sit"] == 101 and sorted(nove.values())[2:] == [5361, 5362, 5363]
     and len(soubory(slozka)) == 3 and json.loads(db.nastaveni["oploceni_karty_vyplni"]) == nove, nove)

# karta se stejnym NAZVEM, ale jinym SKU se nepouzije (nazvy nejsou unikatni; vypis ji ale ukaze)
db = FalesnaDB()
db.produkty.append(db.radek(id=300, sku="CIZI-SKU", name="Plexisklo čiré 5mm", slug="plexi-cizi", active=1, unit="m2"))
conn = db.conn(); cur = conn.cursor()
dalsi, existujici, radky = ZV.nacti_existujici(cur)
slozka = os.path.join(tmp, "b11b"); os.makedirs(slozka)
nove = ZV.zapis(conn, cur, slug_fn_pro(db), slozka, None, existujici, glb_zapis_do(slozka))
over("B11b karta se stejnym nazvem a jinym SKU: ve vypisu je (ANO), ale nepouzije se - vznikne nova karta se spravnym SKU; cizi karta se nemeni", existujici["plexi"] == [] and any("plexi" in x and "ANO: #300" in x for x in radky)
     and nove["plexi"] != 300 and [r for r in db.produkty if r["id"] == 300][0]["active"] == 1 and [r for r in db.produkty if r["id"] == nove["plexi"]][0]["sku"] == "OPL-PLEXI-CIRE-05")

# selhani uprostred: 3. karta - GLB nejde zapsat; vse se vrati a vytvorene GLB se smazou
db = FalesnaDB()
conn = db.conn(); cur = conn.cursor()
dalsi, existujici, _ = ZV.nacti_existujici(cur)
slozka = os.path.join(tmp, "b13"); os.makedirs(slozka)
try:
    ZV.zapis(conn, cur, slug_fn_pro(db), slozka, None, existujici, glb_zapis_do(slozka, spadni_na=3))
    chyba = None
except RuntimeError as e:
    chyba = str(e)
over("B13 selhani 3. GLB: ROLLBACK, zadna nova karta, zadny audit ani nastaveni, vytvorene GLB (2) smazany", chyba and "ROLLBACK" in chyba and db.commity == 0 and db.rollbacky == 1 and len(db.produkty) == 1 and db.audit == []
     and "oploceni_karty_vyplni" not in db.nastaveni and soubory(slozka) == [], (chyba, soubory(slozka)))
db = FalesnaDB()
db.selhani_insertu = 2
conn = db.conn(); cur = conn.cursor()
dalsi, existujici, _ = ZV.nacti_existujici(cur)
slozka = os.path.join(tmp, "b14"); os.makedirs(slozka)
try:
    ZV.zapis(conn, cur, slug_fn_pro(db), slozka, None, existujici, glb_zapis_do(slozka))
    chyba = None
except RuntimeError as e:
    chyba = str(e)
over("B14 INSERT 2. karty s rowcount 0: ROLLBACK, 1. GLB smazany, nic neprislo", chyba and "rowcount=0" in chyba and db.commity == 0 and len(db.produkty) == 1 and soubory(slozka) == [])
# compare-and-set u nastaveni (soubezny zapis)
db = FalesnaDB(nastaveni={"oploceni_karty_vyplni": json.dumps({"pc_cira": 7})})
db.hook_for_update = lambda d: d.cizi_zapis("oploceni_karty_vyplni", json.dumps({"pc_cira": 8}))
conn = db.conn(); cur = conn.cursor()
dalsi, existujici, _ = ZV.nacti_existujici(cur)
slozka = os.path.join(tmp, "b15"); os.makedirs(slozka)
try:
    ZV.zapis(conn, cur, slug_fn_pro(db), slozka, None, existujici, glb_zapis_do(slozka))
    chyba = None
except RuntimeError as e:
    chyba = str(e)
over("B15 compare-and-set: nastaveni zmenene soubezne = ROLLBACK (karty i GLB pryc), nastaveni zustane soubezne zapsane", chyba and "oploceni_karty_vyplni rowcount=0" in chyba and len(db.produkty) == 1 and soubory(slozka) == []
     and json.loads(db.nastaveni["oploceni_karty_vyplni"]) == {"pc_cira": 8}, chyba)
# vzorova karta se zmenila / kategorie neexistuje / kategorie existuje
db = FalesnaDB()
db.produkty[0]["sku"] = "JINA"
conn = db.conn(); cur = conn.cursor()
dalsi, existujici, _ = ZV.nacti_existujici(cur)
try:
    ZV.zapis(conn, cur, slug_fn_pro(db), os.path.join(tmp, "b16"), None, existujici, glb_zapis_do(tmp))
    chyba = None
except RuntimeError as e:
    chyba = str(e)
over("B16 vzorova karta #4933 s jinym SKU = odmitnuto pred zapisem (zadny INSERT)", chyba and "vzorova karta" in chyba and not [q for q, _ in db.sql if q.startswith("INSERT")])
db = FalesnaDB()
conn = db.conn(); cur = conn.cursor()
dalsi, existujici, _ = ZV.nacti_existujici(cur)
try:
    ZV.zapis(conn, cur, slug_fn_pro(db), os.path.join(tmp, "b17"), 99999, existujici, glb_zapis_do(tmp))
    chyba = None
except RuntimeError as e:
    chyba = str(e)
over("B17 neexistujici kategorie = odmitnuto pred zapisem", chyba and "kategorie #99999 neexistuje" in chyba and not [q for q, _ in db.sql if q.startswith("INSERT")])
db = FalesnaDB()
conn = db.conn(); cur = conn.cursor()
dalsi, existujici, _ = ZV.nacti_existujici(cur)
slozka = os.path.join(tmp, "b18"); os.makedirs(slozka)
ZV.zapis(conn, cur, slug_fn_pro(db), slozka, 150, existujici, glb_zapis_do(slozka))
over("B18 --kategorie: vsech 5 karet dostane kategorii 150", all(r["category_id"] == 150 for r in db.produkty if r["sku"].startswith("OPL-")))
# radek_karty vs. schema
sl = ZV.radek_karty("plexi", None, {"availability_text": "x", "price_visible_default": 1, "hover_show_price": 1, "hover_show_availability": 0, "place_vertical": 0, "attach_offset_mm": 0}, "slug")
over("B19 radek_karty: vsechny sloupce existuji ve schematu a vejdou se (vcetne povinnych sku / name)", all(c in SCHEMA for c in sl) and "sku" in sl and "name" in sl and all(len(str(v)) <= int(re.fullmatch(r"varchar\((\d+)\)", SCHEMA[c][0]).group(1)) for c, v in sl.items() if v is not None and re.fullmatch(r"varchar\(\d+\)", SCHEMA[c][0])))
zs = zive_schema()
if zs is None:
    print("INFO zive schema: preskoceno (bez DB_* v prostredi; pro kontrolu spust pres systemd-run s api/.env - cte jen SHOW COLUMNS)")
else:
    over("B20 zive schema shop_products: kazdy sloupec INSERTu obou skriptu existuje, povinne (NOT NULL bez defaultu) jsou jen sku a name", all(c in zs for c in sl) and [c for c, (t, n, d) in zs.items() if n == "NO" and d is None and c != "id"] == ["sku", "name"]
         and all(c in zs for c in ("sku", "name", "slug", "description", "unit", "active", "meta_title", "meta_description", "glb_file")), [c for c in sl if c not in zs])
    over("B21 zive schema: typy a delky sloupcu odpovidaji snimku v testu (zmena schematu = aktualizovat snimek)", all(zs[c][0] == SCHEMA[c][0] for c in SCHEMA), [(c, zs.get(c), SCHEMA[c]) for c in SCHEMA if zs.get(c, (None,))[0] != SCHEMA[c][0]])

# main() s fake pripojenim: glb_lam12 se skutecne zapise do docasne slozky a load_ctx je falesny
db = FalesnaDB()
sdilene = db.conn()
slozka = os.path.join(tmp, "b22"); os.makedirs(slozka)
ZV.pripoj = lambda: (lambda: sdilene, slug_fn_pro(db))
ZV.KATALOG = slozka
import configurator_price  # noqa: E402
configurator_price.load_ctx = lambda c: {"parts": {f"product_{r['id']}": {"is_board_material": bool(r["is_board_material"])} for r in db.produkty}}
buf = io.StringIO()
with redirect_stdout(buf):
    rc = ZV.main(["x", "--apply", "--kategorie", "150"])
vystup = buf.getvalue()
over("B22 main() --apply: 5 karet, kategorie 150, skutecne GLB z glb_lam12 (soubory na disku, hlavicka glTF), overeni po commitu, radek KARTY_VYPLNI", rc == 0 and "KARTY_VYPLNI" in vystup and vystup.count("zapsano a overeno po commitu") == 5
     and len(soubory(slozka)) == 5 and all(open(os.path.join(slozka, f), "rb").read(4) == b"glTF" for f in soubory(slozka)) and db.commity == 1, vystup[-400:])
buf = io.StringIO()
with redirect_stdout(buf):
    rc = ZV.main(["x"])
over("B23 main() bez --apply = nahled (5 radku vypisu, zadny zapis), kod 0", rc == 0 and "nahled, nic nezapsano" in buf.getvalue() and db.commity == 1)
ZV.pripoj = lambda: (lambda: sdilene, None)
buf = io.StringIO()
with redirect_stdout(buf):
    rc = ZV.main(["x", "--apply"])
over("B24 main() --apply bez systemd-run: odmitne (kod 2)", rc == 2 and "CHYBA" in buf.getvalue())
shutil.rmtree(tmp, ignore_errors=True)

print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
