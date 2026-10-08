#!/opt/konfigurator/api/venv/bin/python
"""Mini-shop (Packstations), FAZE 1b: import textu jako draft a klikaci schvalovani (bot5, 2026-10-02; schvalil bot3).

SKUTECNY kod (nebo kandidati MINIWEB_PY a MINIWEB_ADMIN_PY) nad DOCASNYMI tabulkami (storefronty, miniweb_*, audit_log). Ostre tabulky se jen ctou (app_users pro session, shop_products pro existenci karty).
Cast A  opravneni: jen admin (anonym 401, jina role 403), na vsech 3 endpointech
Cast B  import: nahled bez zapisu, zapis jako DRAFT, opakovani nic nemeni, schvaleny text se neprepise (az revise_approved), vse nebo nic pri chybe, ocisteni, jazyky a rodiny se nemichaji
Cast B2 CLI scripts/miniweb_import.py: nahled, zapis se zalohou, chyby, spatne argumenty, prepinace
Cast C  prehled: tvar, text tak, jak ho uvidi zakaznik, otisk obsahu, priznaky problemu a "bude verejne", filtr jazyka
Cast D  schvaleni a vraceni: otisk obsahu (zmeneny text se neschvali), znacka a prazdny nazev blokuji, spatne pozadavky, audit, a end-to-end: schvaleno = verejne API to ukaze
Cast E  pravni dokumenty (podminky, soukromi, vraceni): import jako draft, validace (druh, duplicita, limity, znacka s vyjimkou zakonneho nazvu prodejce), zastupne znacky [DOPLNIT]/[OVERIT] blokuji
        schvaleni, prehled, schvaleni s otiskem, vraceni, end-to-end /api/miniweb/legal
Cast M  mutace klicovych ochran
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_miniweb_testy/test_miniweb_admin.py
"""
import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")


def _cesta(env, jmeno):
    return os.environ.get(env) or (os.path.join(API, jmeno) if os.path.exists(os.path.join(API, jmeno)) else os.path.join(HERE, "nasazeni", jmeno))


tmp = tempfile.mkdtemp(prefix="kand_miniweb_adm_")
shutil.copy(_cesta("MINIWEB_PY", "miniweb.py"), os.path.join(tmp, "miniweb.py"))
shutil.copy(_cesta("MINIWEB_ADMIN_PY", "miniweb_admin.py"), os.path.join(tmp, "miniweb_admin.py"))
sys.path.insert(0, API)
sys.path.insert(0, tmp)                    # kandidati PRED importem app (app.py importuje nasazene moduly, jinak by kandidaty vyhrala kopie z cache modulu)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

import miniweb as mw  # noqa: E402
import miniweb_admin as mwa  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


TEMP_LIKE = ("car_storefronts", "storefront_hosts", "miniweb_shops", "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_documents", "audit_log")
OSTRE = TEMP_LIKE + ("app_users",)


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in OSTRE:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            return out
    finally:
        c.close()


PRED_OSTRE = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
BRAND = re.compile(r"logiman|konfigur[aá]tor|vandrawee|vandr|dogus", re.I)

try:
    with real.cursor() as cur:
        for t in TEMP_LIKE:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
    real.commit()

    def sql(q, params=None):
        with real.cursor() as cur:
            cur.execute(q, params or ())
            out = cur.fetchall() if q.lstrip().upper().startswith("SELECT") else cur.rowcount
        real.commit()
        return out

    def jedno(q, params=None):
        r = sql(q, params)
        return r[0] if r else None

    TAB = ("miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts")

    def pocty():
        return {t: jedno(f"SELECT COUNT(*) AS n FROM `{t}`")["n"] for t in TAB}

    def snimek():
        return {t: sql(f"SELECT * FROM `{t}` ORDER BY 1, 2") for t in TAB}

    REAL_SP = jedno("SELECT id FROM shop_products ORDER BY id LIMIT 1")["id"]            # skutecna karta sestavy (jen cteni)
    S_EN = None
    sql("INSERT INTO car_storefronts (name, slug, primary_domain, status, lang) VALUES ('packstations-en','packstations-en','packstations.example.top','live','en')")
    S_EN = jedno("SELECT * FROM car_storefronts WHERE slug='packstations-en'")
    sql("INSERT INTO miniweb_shops (storefront_id, family, price_mode, currency) VALUES (%s,'packstations','hidden','EUR')", (S_EN["id"],))
    H = "packstations.example.top"

    def zaklad(lang="en", family="packstations"):
        return {"version": 1, "family": family, "lang": lang,
                "categories": [{"slug": "tables", "parent": None, "sort": 1, "name": "Tables"}, {"slug": "packing-stations", "parent": "tables", "sort": 1, "name": "Packing stations"}],
                "products": [{"slug": "packing-station-ps120", "sku": "PS-120", "category": "packing-stations", "sort": 1,
                              "configurator": {"available": True, "shop_product_id": REAL_SP, "default_view": "configurator"},
                              "name": "Packing station PS-120", "summary": "Height-adjustable packing table", "description": "<p>Robust <b>aluminium</b> frame.</p>\n<p>Second paragraph &amp; more.</p>",
                              "delivery": "3-4 weeks", "specs": [{"name": "Width", "value": "1200 mm"}, {"name": "Load", "value": "150 kg"}]},
                             {"slug": "work-table-wt100", "sku": "WT-100", "category": "tables", "sort": 2, "name": "Work table WT-100", "summary": "Sturdy work table", "description": "Plain description.", "delivery": "2 weeks"}]}

    def imp(data, **kw):
        """import_catalog nad skutecnym kurzorem; zapis jen kdyz apply a bez chyb (jako CLI), jinak rollback."""
        with real.cursor() as cur:
            rep = mwa.import_catalog(cur, data, **kw)
        if kw.get("apply") and not rep["errors"]:
            real.commit()
        else:
            real.rollback()
        return rep

    uzivatele = {r["role"]: r["id"] for r in sql("SELECT role, MIN(id) AS id FROM app_users WHERE active=1 GROUP BY role")}
    admin_id = uzivatele["admin"]
    jine_role = {k: v for k, v in uzivatele.items() if k != "admin"}
    _si = SecureCookieSessionInterface()
    cl = appmod.app.test_client(use_cookies=False)

    def cookie(uid):
        return {"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid})} if uid else {}

    def get(cesta, uid=None, host="spolecna.example.org", **params):
        return cl.get(cesta, base_url=f"http://{host}", query_string=params or None, headers=cookie(uid))

    def post(cesta, body, uid=admin_id, raw=None, ctype="application/json"):
        appmod._rate_limit_buckets.clear()
        if raw is not None:
            return cl.post(cesta, base_url="http://spolecna.example.org", headers=cookie(uid), data=raw, content_type=ctype)
        return cl.post(cesta, base_url="http://spolecna.example.org", headers=cookie(uid), json=body)

    OV, AP, UN = "/api/admin/miniweb/overview", "/api/admin/miniweb/approve", "/api/admin/miniweb/unapprove"

    # ============================================================================================================ A) opravneni
    print("== A opravneni")
    anonym = [get(OV).status_code, post(AP, {"items": []}, uid=None).status_code, post(UN, {"items": []}, uid=None).status_code]
    over("A1 anonym: 401 na prehledu, schvaleni i vraceni", anonym == [401, 401, 401], anonym)
    role_kody = {r: [get(OV, uid=u).status_code, post(AP, {"items": []}, uid=u).status_code, post(UN, {"items": []}, uid=u).status_code] for r, u in jine_role.items()}
    over(f"A2 kazda jina role ({', '.join(sorted(jine_role))}): 403 na vsech trech (schvaluje jen admin)", jine_role and all(v == [403, 403, 403] for v in role_kody.values()), role_kody)
    over("A3 admin: 200 na prehledu, prazdny seznam polozek schvaleni = 400 (ne 403)", get(OV, uid=admin_id).status_code == 200 and post(AP, {"items": []}).status_code == 400, None)

    # ============================================================================================================ B) import
    print("== B import")
    pred = snimek()
    r = imp(zaklad())
    over("B1 NAHLED (bez apply): report ukaze co by se stalo (2 kategorie, 2 produkty, 4 texty) a v databazi se nezmeni NIC",
         not r["errors"] and r["applied"] is False and r["categories"]["created"] == 2 and r["products"]["created"] == 2 and r["texts"]["created"] == 4 and snimek() == pred, r)
    r = imp(zaklad(), apply=True)
    over("B2 zapis: vse vznikne jako DRAFT (zadny approved), schvalovatel prazdny, rodina z souboru", not r["errors"] and r["applied"] is True and pocty() == {"miniweb_categories": 2, "miniweb_category_texts": 2, "miniweb_products": 2, "miniweb_product_texts": 2}
         and {x["status"] for x in sql("SELECT status FROM miniweb_category_texts UNION ALL SELECT status FROM miniweb_product_texts")} == {"draft"}
         and all(x["approved_by"] is None and x["approved_at"] is None for x in sql("SELECT approved_by, approved_at FROM miniweb_product_texts")) and {x["family"] for x in sql("SELECT family FROM miniweb_categories")} == {"packstations"}, r)
    prod = jedno("SELECT p.*, t.* FROM miniweb_products p JOIN miniweb_product_texts t ON t.miniweb_product_id = p.id WHERE p.slug='packing-station-ps120'")
    cat2 = jedno("SELECT * FROM miniweb_categories WHERE slug='packing-stations'")
    cat2["parent_slug"] = jedno("SELECT slug FROM miniweb_categories WHERE id=%s", (cat2["parent_id"],))["slug"]          # dve dotazy: dockasna tabulka se v jednom dotazu neda pouzit dvakrat
    over("B3 katalog a konfigurator: kod, poradi, odkaz na kartu sestavy, dostupnost, rodic kategorie; text je OCISTENY uz pri importu (HTML pryc, odstavce zustaly, parametry jako JSON)",
         prod["public_sku"] == "PS-120" and prod["sort_order"] == 1 and prod["shop_product_id"] == REAL_SP and prod["configurator_available"] == 1 and cat2["parent_slug"] == "tables"
         and prod["description"] == "Robust aluminium frame.\n\nSecond paragraph & more." and json.loads(prod["specs_json"]) == [{"name": "Width", "value": "1200 mm"}, {"name": "Load", "value": "150 kg"}], (prod, cat2))
    after1 = snimek()
    r = imp(zaklad(), apply=True)
    over("B4 opakovany import stejneho souboru je no-op: vse unchanged, v databazi se nezmeni nic", not r["errors"] and r["texts"]["unchanged"] == 4 and r["texts"]["created"] == 0 and r["categories"]["unchanged"] == 2 and r["products"]["unchanged"] == 2 and snimek() == after1, r)
    d = zaklad()
    d["products"][1]["description"] = "Plain description, now longer."
    r = imp(d, apply=True)
    wt = jedno("SELECT t.* FROM miniweb_product_texts t JOIN miniweb_products p ON p.id = t.miniweb_product_id WHERE p.slug='work-table-wt100'")
    over("B5 zmeneny DRAFT se prepise (zustane draft)", r["texts"]["updated"] == 1 and wt["description"] == "Plain description, now longer." and wt["status"] == "draft", r)
    # schvaleny text
    sql("UPDATE miniweb_product_texts SET status='approved', approved_by=%s, approved_at=NOW() WHERE miniweb_product_id=%s", (admin_id, wt["miniweb_product_id"]))
    d2 = copy.deepcopy(d)
    d2["products"][1]["description"] = "Completely rewritten by source."
    r = imp(d2, apply=True)
    wt2 = jedno("SELECT * FROM miniweb_product_texts WHERE miniweb_product_id=%s", (wt["miniweb_product_id"],))
    over("B6 SCHVALENY text se importem NEPREPISE (zustane approved a puvodni obsah), report to hlasi jako skipped_approved a varovani", r["texts"]["skipped_approved"] == 1 and wt2["status"] == "approved" and wt2["description"] == "Plain description, now longer."
         and any("NEPŘEPSÁNO" in w for w in r["warnings"]), r)
    r = imp(d, apply=True)
    over("B7 schvaleny text shodny se souborem zustane schvaleny (unchanged)", r["texts"]["skipped_approved"] == 0 and jedno("SELECT status FROM miniweb_product_texts WHERE miniweb_product_id=%s", (wt["miniweb_product_id"],))["status"] == "approved", r)
    r = imp(d2, apply=True, revise_approved=True)
    wt3 = jedno("SELECT * FROM miniweb_product_texts WHERE miniweb_product_id=%s", (wt["miniweb_product_id"],))
    over("B8 s revise_approved se schvaleny text prepise a VRATI do draftu (schvalovatel pryc), report to pocita jako revised", r["texts"]["revised"] == 1 and wt3["status"] == "draft" and wt3["description"] == "Completely rewritten by source."
         and wt3["approved_by"] is None and wt3["approved_at"] is None, r)
    d3 = copy.deepcopy(d2)
    d3["products"][1]["sort"] = 7
    d3["categories"][1]["sort"] = 5
    r = imp(d3, apply=True)
    over("B9 katalogove zmeny existujici polozky (poradi) se bez update_catalog jen HLASI (differs + varovani), v databazi zustanou", r["products"]["differs"] == 1 and r["categories"]["differs"] == 1 and len(r["warnings"]) >= 2
         and jedno("SELECT sort_order FROM miniweb_products WHERE slug='work-table-wt100'")["sort_order"] == 2, r)
    r = imp(d3, apply=True, update_catalog=True)
    over("B10 s update_catalog se katalogove zmeny zapisou", r["products"]["updated"] == 1 and r["categories"]["updated"] == 1 and jedno("SELECT sort_order FROM miniweb_products WHERE slug='work-table-wt100'")["sort_order"] == 7, r)
    de = zaklad("de")
    de["categories"][0]["name"] = "Tische"
    de["categories"][1]["name"] = "Packstationen"
    de["products"][0]["name"] = "Packstation PS-120"
    de["products"][1]["name"] = "Arbeitstisch WT-100"
    r = imp(de, apply=True)
    over("B11 druhy jazyk: katalog se nenapodobi, jen pribudou nemecke texty (draft), anglicke zustanou netknute", not r["errors"] and r["categories"]["created"] == 0 and r["products"]["created"] == 0 and r["texts"]["created"] == 4
         and jedno("SELECT COUNT(*) AS n FROM miniweb_product_texts WHERE lang='en'")["n"] == 2 and jedno("SELECT COUNT(*) AS n FROM miniweb_categories")["n"] == 2, r)
    other = zaklad("en", family="worktables")
    other["products"][0]["configurator"] = {"available": False}
    other["products"][0]["sku"], other["products"][1]["sku"] = "XW-1", "XW-2"
    other["products"][0]["slug"], other["products"][1]["slug"] = "x-one", "x-two"
    r = imp(other, apply=True)
    over("B12 jina RODINA se stejnymi slugy kategorii: vznikne vedle (kategorie 'tables' v obou), rodina packstations je beze zmeny", not r["errors"] and r["categories"]["created"] == 2
         and jedno("SELECT COUNT(*) AS n FROM miniweb_categories WHERE slug='tables'")["n"] == 2 and jedno("SELECT COUNT(*) AS n FROM miniweb_categories WHERE family='packstations'")["n"] == 2, r)

    # chyby: vse nebo nic
    pred = snimek()

    def chyba(uprava, fragment, nazev=None):
        d_ = zaklad("en")
        uprava(d_)
        rr = imp(d_, apply=True)
        return bool(rr["errors"]) and any(fragment in e for e in rr["errors"]) and rr["applied"] is False and snimek() == pred, (nazev or fragment, rr["errors"][:3])

    pripady = [
        (lambda d_: d_.update(version=2), "version"), (lambda d_: d_.update(family="Bad Family"), "family"), (lambda d_: d_.update(lang="EN"), "lang"), (lambda d_: d_.update(preklep=1), "neznámé klíče"),
        (lambda d_: d_["categories"][0].pop("name"), "chybí povinné pole 'name'"), (lambda d_: d_["products"][0].update(name="Table by Logiman"), "značku"), (lambda d_: d_["products"][0].update(description="Made with Dogus profile"), "značku"),
        (lambda d_: d_["products"][0]["specs"].append({"name": "Profile", "value": "Vandr 40"}), "značku"), (lambda d_: d_["categories"][0].update(slug="logiman-tables"), "slug"), (lambda d_: d_["products"][0].update(sku="LOGIMAN-1"), "sku"),
        (lambda d_: d_["products"][0].update(name="x" * 201), "limit"), (lambda d_: d_["products"][0].update(slug="Bad Slug"), "slug"), (lambda d_: d_["products"][1].update(slug="packing-station-ps120"), "dvakrát"),
        (lambda d_: d_["products"][1].update(sku="PS-120"), "dvakrát"), (lambda d_: d_["products"][0].update(category="neexistuje"), "neexistuje"), (lambda d_: d_["categories"][1].update(parent="neexistuje"), "neexistuje"),
        (lambda d_: (d_.update(family="cykl"), d_["categories"][0].update(parent="packing-stations")), "cyklus"), (lambda d_: d_["products"][0]["configurator"].update(shop_product_id=2147483000), "neexistuje"),
        (lambda d_: d_["products"][0]["configurator"].update(shop_product_id=None), "vyžaduje shop_product_id"), (lambda d_: d_["products"][0]["configurator"].update(preklep=1), "neznámé klíče"),
        (lambda d_: d_["products"][0].update(specs=[{"name": "A", "value": ""}]), "specs[0]"), (lambda d_: d_["products"][0].update(specs="x"), "specs"), (lambda d_: d_["products"][0].update(sort="1"), "sort"),
        (lambda d_: d_["products"][0].update(name="<b></b>"), "prázdné"), (lambda d_: d_.update(categories="x"), "seznamy"), (lambda d_: d_["products"].append(5), "musí být objekt"),
    ]
    res = [chyba(u, f) for u, f in pripady]
    over("B13 VSE NEBO NIC: kazda z 24 chyb v souboru (verze, rodina, jazyk, neznamy klic, chybejici nazev, znacka v nazvu/popisu/parametrech/slugu/kodu, limit, duplicity, neexistujici kategorie/rodic, cyklus, karta sestavy, parametry, razeni, prazdny nazev po vycisteni) zastavi import a v databazi nezustane nic",
         all(x[0] for x in res), [x[1] for x in res if not x[0]])
    d_x = zaklad("en")
    d_x["products"][0]["slug"] = "other-slug"                                       # sku PS-120 uz ma jiny produkt
    r = imp(d_x, apply=True)
    d_y = zaklad("en", family="packstations")
    d_y["products"][0]["slug"] = "x-one"                                            # slug uz patri produktu jine rodiny
    r2 = imp(d_y, apply=True)
    over("B14 kolize s databazi: sku, ktere uz ma jiny produkt, a slug produktu jine rodiny jsou chyby", any("už má produkt" in e for e in r["errors"]) and any("jiné rodiny" in e for e in r2["errors"]) and snimek() == pred, (r["errors"], r2["errors"]))
    over("B15 vlozeny HTML a skripty v textu se cisti (stejnou funkci jako verejne API), znaky < a > ve vete zustanou", imp({**zaklad("en", "xss"), "categories": [{"slug": "c", "name": "<script>alert(1)</script>Safe"}],
         "products": [{"slug": "p-xss", "sku": "XS-1", "category": "c", "name": "Load > 100 kg", "description": "<img src=x onerror=alert(1)>Text"}]}, apply=True)["errors"] == []
         and jedno("SELECT name FROM miniweb_category_texts t JOIN miniweb_categories c ON c.id=t.miniweb_category_id WHERE c.family='xss'")["name"] == "Safe"
         and jedno("SELECT name, description FROM miniweb_product_texts t JOIN miniweb_products p ON p.id=t.miniweb_product_id WHERE p.slug='p-xss'") == {"name": "Load > 100 kg", "description": "Text"}, None)

    # ---- CLI
    spec = importlib.util.spec_from_file_location("miniweb_import_cli", os.path.join(REPO, "scripts", "miniweb_import.py"))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    zaloha_dir = tempfile.mkdtemp(prefix="mw_zaloha_")
    vstup_dir = tempfile.mkdtemp(prefix="mw_vstup_")

    def spust(argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            kod = cli.main(argv, conn=wrap)
        return kod, out.getvalue()

    def zapis_json(d_):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8", dir=vstup_dir)
        json.dump(d_, f, ensure_ascii=False)
        f.close()
        return f.name

    cli_data = {"version": 1, "family": "cli", "lang": "en", "categories": [{"slug": "cli-cat", "name": "Cli category"}], "products": [{"slug": "cli-prod", "sku": "CL-1", "category": "cli-cat", "name": "Cli product", "description": "Text"}]}
    soubor = zapis_json(cli_data)
    pred = snimek()
    kod, vystup = spust([soubor])
    over("B16 CLI vychozi je NAHLED: zvaliduje, vypise co by se stalo, nic nezapise a nic nezalohuje", kod == 0 and "NÁHLED" in vystup and "nové 1" in vystup and snimek() == pred and os.listdir(zaloha_dir) == [], vystup)
    predtim = pocty()
    kod, vystup = spust([soubor, "--apply", "--backup-dir", zaloha_dir])
    zalohy = [f for f in os.listdir(zaloha_dir) if "miniweb_pred_importem" in f]
    zaloha_obsah = json.load(open(os.path.join(zaloha_dir, zalohy[0]), encoding="utf-8")) if zalohy else {}
    over("B17 CLI --apply: zapise jako DRAFT a PRED zapisem zazalohuje stavajici radky (zaloha ma presne ty radky, ktere tam byly pred importem)", kod == 0 and "ZAPSÁNO" in vystup and len(zalohy) == 1
         and {k: len(v) for k, v in zaloha_obsah.items()} == predtim and pocty()["miniweb_categories"] == predtim["miniweb_categories"] + 1 and jedno("SELECT status FROM miniweb_product_texts t JOIN miniweb_products p ON p.id=t.miniweb_product_id WHERE p.slug='cli-prod'")["status"] == "draft", (vystup, zalohy))
    pred = snimek()
    spatny = zapis_json({**cli_data, "products": [{"slug": "cli-bad", "sku": "CL-2", "category": "cli-cat", "name": "Table by Logiman"}]})
    n_zaloh = len(os.listdir(zaloha_dir))
    kod, vystup = spust([spatny, "--apply", "--backup-dir", zaloha_dir])
    over("B18 CLI soubor s chybou: navratovy kod 2, chyba vypsana, NIC se nezapise a nevznikne ani zaloha", kod == 2 and "CHYBA" in vystup and "značku" in vystup and snimek() == pred and len(os.listdir(zaloha_dir)) == n_zaloh, (kod, vystup))
    bad_json = os.path.join(vstup_dir, "bad.json")
    with open(bad_json, "w", encoding="utf-8") as f_:
        f_.write("{nejson")
    kody = [spust([os.path.join(vstup_dir, "neexistuje.json")])[0], spust([bad_json])[0], spust([])[0], spust([soubor, "--neznama-volba"])[0]]
    over("B19 CLI spatne vstupy (neexistujici soubor, neplatny JSON, chybejici argument, neznama volba) -> kod 2 a nic se nezmeni", kody == [2, 2, 2, 2] and snimek() == pred, kody)
    sql("UPDATE miniweb_product_texts SET status='approved', approved_by=%s, approved_at=NOW() WHERE miniweb_product_id=(SELECT id FROM miniweb_products WHERE slug='cli-prod')", (admin_id,))
    zmena = zapis_json({**cli_data, "products": [{**cli_data["products"][0], "description": "Changed text"}]})
    kod1, vystup1 = spust([zmena, "--apply", "--backup-dir", zaloha_dir])
    st1 = jedno("SELECT status, description FROM miniweb_product_texts t JOIN miniweb_products p ON p.id=t.miniweb_product_id WHERE p.slug='cli-prod'")
    kod2, vystup2 = spust([zmena, "--apply", "--revise-approved", "--backup-dir", zaloha_dir])
    st2 = jedno("SELECT status, description FROM miniweb_product_texts t JOIN miniweb_products p ON p.id=t.miniweb_product_id WHERE p.slug='cli-prod'")
    over("B20 CLI: schvaleny text se bez --revise-approved neprepise (vypise to), s prepinacem se prepise a vrati do draftu", kod1 == 0 and "NEPŘEPSÁNO" in vystup1 and st1 == {"status": "approved", "description": "Text"} and kod2 == 0 and st2 == {"status": "draft", "description": "Changed text"}, (vystup1, st1, st2))

    # ============================================================================================================ C) prehled
    print("== C prehled")
    ov = get(OV, uid=admin_id).get_json()
    pe = [i for i in ov["items"] if i["lang"] == "en" and i["family"] == "packstations"]
    ps = next(i for i in pe if i["slug"] == "packing-station-ps120")
    over("C1 prehled: shopy (domena, stav, jazyk, rodina), polozky se vsemi texty, pocty a jazyky; hlavicka no-store",
         set(ov) == {"shops", "items", "counts", "langs"} and ov["shops"][0]["domain"] == H and ov["shops"][0]["status"] == "live" and ov["langs"] == ["de", "en"] and ov["counts"]["draft"] >= 10 and ov["counts"]["approved"] == 0
         and get(OV, uid=admin_id).headers["Cache-Control"] == "no-store", ov["counts"])
    over("C2 text je TAK, JAK HO UVIDI ZAKAZNIK (cisty, bez HTML), nese kod, kategorii v jazyce, otisk obsahu a stav; kategorie nema kod ani popis",
         ps["description"] == "Robust aluminium frame.\n\nSecond paragraph & more." and ps["sku"] == "PS-120" and ps["category"] == "Packing stations" and ps["status"] == "draft" and re.match(r"^[0-9a-f]{16}$", ps["rev"])
         and ps["rev"] == mwa.text_rev(ps["name"], ps["summary"], ps["description"], ps["delivery"], ps["specs"]) and [i for i in pe if i["kind"] == "category"][0]["sku"] is None, ps)
    over("C3 filtr jazyka (?lang=de) vrati jen nemecke polozky", {i["lang"] for i in get(OV, uid=admin_id, lang="de").get_json()["items"]} == {"de"}, None)
    over("C4 'verejne' je false u vseho, dokud nic neni schvaleno (i kdyz je shop live), nic neni blokovano", all(i["public"] is False for i in ov["items"]) and ov["counts"]["public"] == 0 and ov["counts"]["blocked"] == 0, ov["counts"])
    wt_id = jedno("SELECT id FROM miniweb_products WHERE slug='work-table-wt100'")["id"]
    sql("INSERT INTO miniweb_product_texts (miniweb_product_id, lang, name, description, status) VALUES (%s,'fr','Table by Logiman','<p>Bonjour</p>','draft')", (wt_id,))
    sql("INSERT INTO miniweb_product_texts (miniweb_product_id, lang, name, status) VALUES (%s,'es','   ','draft')", (wt_id,))
    ov2 = get(OV, uid=admin_id).get_json()
    fr = next(i for i in ov2["items"] if i["lang"] == "fr")
    es = next(i for i in ov2["items"] if i["lang"] == "es")
    over("C5 problemy: znacka v textu (zapsana primo do DB mimo import) = blokujici 'brand', prazdny nazev = 'no_name', chybejici popis = informace, vycisteny HTML = informace 'cleaned'",
         fr["blocking"] == ["brand"] and "cleaned" in fr["info"] and es["blocking"] == ["no_name"] and ov2["counts"]["blocked"] == 2, (fr, es))
    sql("DELETE FROM miniweb_product_texts WHERE lang IN ('fr','es')")

    # ============================================================================================================ D) schvaleni
    print("== D schvaleni")
    ov = get(OV, uid=admin_id).get_json()
    pe = {(i["kind"], i["slug"]): i for i in ov["items"] if i["lang"] == "en" and i["family"] == "packstations"}
    cat_t, cat_ps, prod_ps, prod_wt = pe[("category", "tables")], pe[("category", "packing-stations")], pe[("product", "packing-station-ps120")], pe[("product", "work-table-wt100")]

    def polozka(i):
        return {"kind": i["kind"], "id": i["id"], "lang": i["lang"], "rev": i["rev"]}

    pred = snimek()
    r = post(AP, {"items": [polozka(prod_ps)]})
    over("D1 produkt s nesvalenou kategorii se da schvalit, ale NENI verejny: 'verejne' je false, dokud neni schvalena i kategorie (a jeji rodic)",
         r.status_code == 200 and r.get_json()["changed"] == 1 and r.get_json()["skipped"] == []
         and next(i for i in get(OV, uid=admin_id).get_json()["items"] if i["kind"] == "product" and i["slug"] == "packing-station-ps120" and i["lang"] == "en")["public"] is False
         and get("/api/miniweb/products", host=H).get_json()["total"] == 0, r.get_json())
    row = jedno("SELECT * FROM miniweb_product_texts WHERE miniweb_product_id=%s AND lang='en'", (prod_ps["id"],))
    audit = sql("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1")[0]
    over("D2 schvaleni zapise schvalovatele a cas, a do audit_logu jednu radku s akci, poctem a polozkami", row["status"] == "approved" and row["approved_by"] == admin_id and row["approved_at"] is not None
         and audit["entity_type"] == "miniweb_text" and audit["user_id"] == admin_id and json.loads(audit["detail"])["akce"] == "approve" and json.loads(audit["detail"])["zmeneno"] == 1
         and f"product:{prod_ps['id']}:en" in json.loads(audit["detail"])["polozky"], audit)
    r = post(AP, {"items": [polozka(cat_t), polozka(cat_ps)]})
    pub = get("/api/miniweb/products", host=H).get_json()
    over("D3 END-TO-END: po schvaleni produktu i obou kategorii (rodic i potomek) je produkt VEREJNY v API shopu a 'verejne' je true; nemecke texty a druhy produkt (draft) zustavaji skryte",
         r.get_json()["changed"] == 2 and [p["sku"] for p in pub["products"]] == ["PS-120"] and next(i for i in get(OV, uid=admin_id).get_json()["items"] if i["kind"] == "product" and i["slug"] == "packing-station-ps120" and i["lang"] == "en")["public"] is True
         and pub["products"][0]["name"] == "Packing station PS-120" and [c["slug"] for c in get("/api/miniweb/categories", host=H).get_json()["categories"]] == ["tables", "packing-stations"], pub)
    over("D4 schvaleni NEZVEREJNUJE shop: stav storefrontu zustal beze zmeny (live/draft se meni jinde)", jedno("SELECT status FROM car_storefronts WHERE id=%s", (S_EN["id"],))["status"] == "live", None)
    # zmeneny text po zobrazeni: otisk nesedi
    d4 = zaklad()
    d4["products"][1]["summary"] = "Changed after the admin looked at it"
    imp(d4, apply=True)
    r = post(AP, {"items": [polozka(prod_wt)]})
    over("D5 OTISK OBSAHU: text se mezitim zmenil (import po zobrazeni) -> NESCHVALI se (skipped changed), v databazi zustane draft; po novem nacteni prehledu s novym otiskem se schvalit da",
         r.get_json()["changed"] == 0 and r.get_json()["skipped"] == [{"kind": "product", "id": prod_wt["id"], "lang": "en", "reason": "changed"}]
         and jedno("SELECT status FROM miniweb_product_texts WHERE miniweb_product_id=%s AND lang='en'", (prod_wt["id"],))["status"] == "draft"
         and post(AP, {"items": [polozka(next(i for i in get(OV, uid=admin_id).get_json()["items"] if i["kind"] == "product" and i["slug"] == "work-table-wt100" and i["lang"] == "en"))]}).get_json()["changed"] == 1, r.get_json())
    sql("UPDATE miniweb_product_texts SET description=%s WHERE miniweb_product_id=%s AND lang='de'", ("Made by Logiman", prod_ps["id"]))
    ov3 = get(OV, uid=admin_id).get_json()
    de_ps = next(i for i in ov3["items"] if i["kind"] == "product" and i["slug"] == "packing-station-ps120" and i["lang"] == "de")
    r = post(AP, {"items": [polozka(de_ps)]})
    over("D6 text se ZNACKOU (zapsany mimo import) nejde schvalit (skipped blocked), v databazi zustane draft", r.get_json()["changed"] == 0 and r.get_json()["skipped"][0]["reason"] == "blocked"
         and jedno("SELECT status FROM miniweb_product_texts WHERE miniweb_product_id=%s AND lang='de'", (prod_ps["id"],))["status"] == "draft", r.get_json())
    r = post(AP, {"items": [polozka(prod_ps), {"kind": "product", "id": 999999, "lang": "en", "rev": "0" * 16}]})
    over("D7 uz schvaleny = skipped already, neexistujici = not_found (zbytek davky se zpracuje)", r.get_json()["changed"] == 0 and {s["reason"] for s in r.get_json()["skipped"]} == {"already", "not_found"}, r.get_json())
    pred = snimek()
    spatne = [{"items": "x"}, {"items": []}, {"items": [{"kind": "product", "id": 1, "lang": "en"}]}, {"items": [{"kind": "product", "id": "1", "lang": "en", "rev": "0" * 16}]}, {"items": [{"kind": "product", "id": True, "lang": "en", "rev": "0" * 16}]},
              {"items": [{"kind": "stuff", "id": 1, "lang": "en", "rev": "0" * 16}]}, {"items": [{"kind": "product", "id": 1, "lang": "EN!", "rev": "0" * 16}]}, {"items": [{"kind": "product", "id": 1, "lang": "en", "rev": "XYZ"}]},
              {"items": [{"kind": "product", "id": 1, "lang": "en", "rev": "0" * 16}] * 301}, [1, 2], {}]
    kody = [post(AP, b).status_code for b in spatne] + [post(AP, None, raw=json.dumps({"items": [polozka(prod_wt)]}), ctype="text/plain").status_code, post(AP, None, raw="nejson").status_code,
                                                         post(AP, None, raw="items=1", ctype="application/x-www-form-urlencoded").status_code]
    over("D8 spatne pozadavky (chybi/prazdne/prilis mnoho polozek, spatny typ nebo id nebo jazyk nebo otisk, cizi content-type vcetne formulare) -> 400 a v databazi se nezmeni nic", set(kody) == {400} and snimek() == pred, kody)
    r = post(UN, {"items": [{"kind": "category", "id": cat_ps["id"], "lang": "en"}, {"kind": "category", "id": cat_ps["id"], "lang": "en"}]})
    over("D9 vraceni do draftu (bez otisku): schvaleny se vrati do draftu, schvalovatel pryc, produkt z teto kategorie prestane byt verejny (druhy zustava); druhy pokus o totez v davce = already",
         r.get_json()["changed"] == 1 and [s["reason"] for s in r.get_json()["skipped"]] == ["already"] and jedno("SELECT status, approved_by FROM miniweb_category_texts WHERE miniweb_category_id=%s AND lang='en'", (cat_ps["id"],)) == {"status": "draft", "approved_by": None}
         and [p["sku"] for p in get("/api/miniweb/products", host=H).get_json()["products"]] == ["WT-100"] and json.loads(sql("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1")[0]["detail"])["akce"] == "unapprove", r.get_json())

    # ============================================================================================================ E) pravni dokumenty
    print("== E pravni dokumenty")
    DOCS = [{"kind": "terms", "title": "Terms and conditions", "body": "<p>The seller is LOGiMAN  s.r.o., ID 28337638.</p>\n<p>Orders are made to order.</p><script>x()</script>"},
            {"kind": "privacy", "title": "Privacy", "body": "We process personal data only to answer your inquiry."},
            {"kind": "returns", "title": "Returns", "body": "Goods may be returned within 14 days."}]

    def doc_soubor(docs=None, lang="en", family="packstations", **extra):
        d = {"version": 1, "family": family, "lang": lang, "documents": DOCS if docs is None else docs}
        d.update(extra)
        return d

    pred_cat = snimek()
    r = imp(doc_soubor())
    over("E1 NAHLED importu dokumentu: 3 nove dokumenty, nic se nezapise (ani dokumenty, ani katalog); soubor jen s dokumenty (bez kategorii a produktu) je v poradku", not r["errors"] and r["documents"]["created"] == 3
         and jedno("SELECT COUNT(*) AS n FROM miniweb_documents")["n"] == 0 and snimek() == pred_cat, r)
    r = imp(doc_soubor(), apply=True)
    rows = {x["kind"]: x for x in sql("SELECT * FROM miniweb_documents ORDER BY id")}
    over("E2 zapis: 3 dokumenty jako DRAFT (nikdy approved), text ocisteny (HTML a script pryc, odstavce zachovany, zakonny nazev prodejce v textu zustava), druh+jazyk+rodina jednoznacne; katalog beze zmeny",
         not r["errors"] and set(rows) == {"terms", "privacy", "returns"} and all(x["status"] == "draft" and x["approved_by"] is None and x["lang"] == "en" and x["family"] == "packstations" for x in rows.values())
         and rows["terms"]["body"] == "The seller is LOGiMAN s.r.o., ID 28337638.\n\nOrders are made to order." and snimek() == pred_cat, (r, rows))
    r = imp(doc_soubor(), apply=True)
    over("E3 opakovani stejneho souboru nic nemeni (3x beze zmeny), zadna duplicita", r["documents"] == {"created": 0, "updated": 0, "unchanged": 3, "skipped_approved": 0, "revised": 0} and jedno("SELECT COUNT(*) AS n FROM miniweb_documents")["n"] == 3, r["documents"])
    ov = get(OV, uid=admin_id).get_json()
    d_items = {i["slug"]: i for i in ov["items"] if i["kind"] == "document" and i["lang"] == "en"}
    over("E4 prehled: dokumenty jsou polozky druhu 'document' (slug = druh, nazev = nadpis, popis = cely text, otisk, blokace, 'verejne' false pro draft), soucasti poctu navrhu a filtru jazyka",
         set(d_items) == {"terms", "privacy", "returns"} and d_items["terms"]["name"] == "Terms and conditions" and d_items["terms"]["description"] == rows["terms"]["body"] and re.match(r"^[0-9a-f]{16}$", d_items["terms"]["rev"])
         and all(i["status"] == "draft" and i["blocking"] == [] and i["public"] is False for i in d_items.values()) and len({i["rev"] for i in d_items.values()}) == 3
         and {i["kind"] for i in get(OV, uid=admin_id, lang="en").get_json()["items"]} >= {"document", "product", "category"} and not any(i["kind"] == "document" for i in get(OV, uid=admin_id, lang="de").get_json()["items"]), d_items)
    # schvaleni
    def dpol(i):
        return {"kind": "document", "id": i["id"], "lang": i["lang"], "rev": i["rev"]}
    r = post(AP, {"items": [dpol(d_items["terms"]), dpol(d_items["returns"])]})
    over("E5 schvaleni dokumentu: 2 schvaleny (schvalovatel a cas v databazi), privacy zustava draft; END-TO-END: verejny /api/miniweb/legal anglickeho shopu vydava schvalene dokumenty v poradi terms, returns s textem",
         r.status_code == 200 and r.get_json()["changed"] == 2 and r.get_json()["skipped"] == [] and jedno("SELECT status, approved_by FROM miniweb_documents WHERE kind='terms'") == {"status": "approved", "approved_by": admin_id}
         and [d["kind"] for d in get("/api/miniweb/legal", host=H).get_json()["documents"]] == ["terms", "returns"]
         and get("/api/miniweb/legal", host=H).get_json()["documents"][0]["body"] == rows["terms"]["body"], r.get_json())
    r = post(UN, {"items": [{"kind": "document", "id": d_items["returns"]["id"], "lang": "en"}]})
    over("E6 vraceni dokumentu do draftu: verejne zmizi, schvalovatel pryc, audit nese akci unapprove", r.get_json()["changed"] == 1 and [d["kind"] for d in get("/api/miniweb/legal", host=H).get_json()["documents"]] == ["terms"]
         and jedno("SELECT status, approved_by FROM miniweb_documents WHERE kind='returns'") == {"status": "draft", "approved_by": None} and json.loads(sql("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1")[0]["detail"])["akce"] == "unapprove", r.get_json())
    # otisk, jazyk, schvaleny se neprepise
    d2 = [dict(DOCS[0], body="The seller is LOGiMAN s.r.o. Changed terms."), DOCS[1], DOCS[2]]
    r = imp(doc_soubor(d2), apply=True)
    over("E7 schvaleny dokument se importem NEPREPISE (skipped_approved + varovani), draft dokumenty ano; s revise_approved se prepise a vrati do draftu (verejne zmizi do dalsiho schvaleni)",
         r["documents"]["skipped_approved"] == 1 and any("NEPŘEPSÁNO" in w for w in r["warnings"]) and jedno("SELECT body FROM miniweb_documents WHERE kind='terms'")["body"] == rows["terms"]["body"]
         and imp(doc_soubor(d2), apply=True, revise_approved=True)["documents"]["revised"] == 1 and jedno("SELECT status FROM miniweb_documents WHERE kind='terms'")["status"] == "draft"
         and "Changed" in jedno("SELECT body FROM miniweb_documents WHERE kind='terms'")["body"] and get("/api/miniweb/legal", host=H).get_json()["documents"] == [], r)
    r = post(AP, {"items": [dpol(d_items["terms"])]})
    over("E8 OTISK: dokument se po zobrazeni zmenil (revise import) -> stary otisk se NESCHVALI (changed); novy otisk z noveho prehledu se schvalit da; jazyk, ktery k id nepatri, = not_found",
         r.get_json()["changed"] == 0 and r.get_json()["skipped"][0]["reason"] == "changed" and post(AP, {"items": [{"kind": "document", "id": d_items["terms"]["id"], "lang": "de", "rev": d_items["terms"]["rev"]}]}).get_json()["skipped"][0]["reason"] == "not_found"
         and post(AP, {"items": [dpol(next(i for i in get(OV, uid=admin_id).get_json()["items"] if i["kind"] == "document" and i["slug"] == "terms" and i["lang"] == "en"))]}).get_json()["changed"] == 1, r.get_json())
    # validace
    pred_docs = sql("SELECT * FROM miniweb_documents ORDER BY id")
    spatne = {
        "neznamy druh": doc_soubor([{"kind": "imprint", "title": "T", "body": "B"}]),
        "druh dvakrat": doc_soubor([DOCS[1], DOCS[1]]),
        "neznamy klic": doc_soubor([dict(DOCS[1], slug="x")]),
        "chybi nadpis": doc_soubor([{"kind": "privacy", "body": "B"}]),
        "prazdny text po vycisteni": doc_soubor([{"kind": "privacy", "title": "T", "body": "<p> </p>"}]),
        "text neni retezec": doc_soubor([{"kind": "privacy", "title": "T", "body": ["a"]}]),
        "prilis dlouhy text": doc_soubor([{"kind": "privacy", "title": "T", "body": "x" * (mw.DOC_MAX_BODY + 1)}]),
        "prilis dlouhy nadpis": doc_soubor([{"kind": "privacy", "title": "x" * (mw.DOC_MAX_TITLE + 1), "body": "B"}]),
        "znacka v textu": doc_soubor([{"kind": "privacy", "title": "T", "body": "Data go to Logiman Prague."}]),
        "znacka v nadpisu": doc_soubor([{"kind": "privacy", "title": "Vandr terms", "body": "B"}]),
        "slovo konfigurator": doc_soubor([{"kind": "privacy", "title": "T", "body": "Use the konfigurátor."}]),
        "documents neni seznam": doc_soubor("x"),
        "dokument neni objekt": doc_soubor(["x"]),
        "prilis mnoho dokumentu": doc_soubor([DOCS[1]] * (mwa.MAX_DOCUMENTS + 1)),
    }
    kod = {}
    for jmeno, soubor in spatne.items():
        rr = imp(soubor, apply=True)
        kod[jmeno] = bool(rr["errors"])
    over("E9 chybne dokumenty (" + ", ".join(spatne) + ") = chyba a VSE NEBO NIC (zadny zapis, ani zbytek souboru)", all(kod.values()) and sql("SELECT * FROM miniweb_documents ORDER BY id") == pred_docs and snimek() == pred_cat, kod)
    over("E10 zakonny nazev prodejce v dokumentu projde importem (identifikace prodejce), jakykoli jiny vyskyt znacky ne; E2 to uz dokazuje na LOGiMAN s.r.o. s jinou velikosti pismen a mezerami",
         not imp(doc_soubor([{"kind": "cookies", "title": "Cookies", "body": "Seller: logiman S.R.O."}]))["errors"] and imp(doc_soubor([{"kind": "cookies", "title": "Cookies", "body": "Seller: logiman S.R.O. and Logiman team"}]))["errors"], None)
    # zastupne znacky
    rp = imp(doc_soubor([{"kind": "shipping", "title": "Doprava", "body": "Dodanie [DOPLNIŤ: lehota] dní.\nNÁVRH k právnej kontrole"}]), apply=True)
    ovp = get(OV, uid=admin_id).get_json()
    d_ship = next(i for i in ovp["items"] if i["kind"] == "document" and i["slug"] == "shipping")
    r = post(AP, {"items": [dpol(d_ship)]})
    over("E11 dokument se zastupnymi znackami [DOPLNIT]/[OVERIT] nebo oznacenim navrhu k pravni kontrole: import projde jako DRAFT s varovanim, v prehledu je blokovany (placeholder), NEJDE schvalit (blocked) a nikdy se verejne nevydava",
         not rp["errors"] and any("zástupné značky" in w for w in rp["warnings"]) and d_ship["blocking"] == ["placeholder"] and r.get_json()["changed"] == 0 and r.get_json()["skipped"][0]["reason"] == "blocked"
         and jedno("SELECT status FROM miniweb_documents WHERE kind='shipping'")["status"] == "draft", (rp, d_ship["blocking"], r.get_json()))
    sql("UPDATE miniweb_documents SET status='approved', approved_by=%s, approved_at=NOW() WHERE kind='shipping'", (admin_id,))
    over("E12 i kdyby byl dokument se zastupnou znackou nejak oznacen jako schvaleny (zapis mimo import), verejne API ho NEVYDA (druha pojistka)", "shipping" not in [d["kind"] for d in get("/api/miniweb/legal", host=H).get_json()["documents"]], None)
    sql("DELETE FROM miniweb_documents WHERE kind='shipping'")

    # ============================================================================================================ M) mutace
    print("== M mutace klicovych ochran")
    zdroj = open(mwa.__file__, encoding="utf-8").read()

    def mutant(funkce, stare, nove, n=1):
        node = next(n_ for n_ in ast.parse(zdroj).body if isinstance(n_, ast.FunctionDef) and n_.name == funkce)
        src = ast.get_source_segment(zdroj, node)
        assert src.count(stare) == n, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x, ocekavano {n}x"
        ns = dict(vars(mwa))
        exec(src.replace(stare, nove), ns)
        return ns[funkce]

    def mutant_vic(funkce, dvojice):
        """Vice nahrad najednou (pojistka je v kodu na vic mistech, mutace jedne by nic neprokazala): [(stare, nove, pocet), ...]."""
        node = next(n_ for n_ in ast.parse(zdroj).body if isinstance(n_, ast.FunctionDef) and n_.name == funkce)
        src = ast.get_source_segment(zdroj, node)
        for stare, nove, n in dvojice:
            assert src.count(stare) == n, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x, ocekavano {n}x"
            src = src.replace(stare, nove)
        ns = dict(vars(mwa))
        exec(src, ns)
        return ns[funkce]

    def cerstve(slug, lang="en", kind="product"):
        return next(i for i in get(OV, uid=admin_id).get_json()["items"] if i["kind"] == kind and i["slug"] == slug and i["lang"] == lang and i["family"] == "packstations")

    # M1: bez kontroly otisku
    orig = mwa.apply_status_change
    mwa.apply_status_change = mutant("apply_status_change", 'elif rev_now != it["rev"]:', "elif False:")
    try:
        sql("UPDATE miniweb_product_texts SET status='draft', approved_by=NULL, approved_at=NULL WHERE miniweb_product_id=%s AND lang='en'", (prod_wt["id"],))
        r_m = post(AP, {"items": [{"kind": "product", "id": prod_wt["id"], "lang": "en", "rev": "f" * 16}]})
    finally:
        mwa.apply_status_change = orig
    over("M1 mutace: bez kontroly otisku by se schvalil text, ktery admin nevidel (spravne skipped changed) - testy D5 a tahle ji zachyti", r_m.get_json()["changed"] == 1, r_m.get_json())
    sql("UPDATE miniweb_product_texts SET status='draft', approved_by=NULL, approved_at=NULL WHERE miniweb_product_id=%s AND lang='en'", (prod_wt["id"],))
    # M2: bez blokovani znacky
    orig_p = mwa._problems
    mwa._problems = mutant("_problems", "if dealers._brand_hit(*texts):", "if False:")
    try:
        r_m = post(AP, {"items": [polozka(cerstve("packing-station-ps120", "de"))]})
    finally:
        mwa._problems = orig_p
    over("M2 mutace: bez blokovani znacky by se schvalil text se znackou (spravne blocked) - test D6 ji zachyti", r_m.get_json()["changed"] == 1, r_m.get_json())
    sql("UPDATE miniweb_product_texts SET description='Safe' WHERE miniweb_product_id=%s AND lang='de'", (prod_ps["id"],))
    # M3: bez kontroly role
    vf = appmod.app.view_functions["admin_miniweb_overview"]
    appmod.app.view_functions["admin_miniweb_overview"] = mutant("admin_miniweb_overview", "lang = miniweb._clean_lang", "lang = miniweb._clean_lang")
    try:
        r_m = get(OV, uid=None)
    finally:
        appmod.app.view_functions["admin_miniweb_overview"] = vf
    over("M3 mutace: bez dekoratoru admin_required by prehled cetl i anonym (spravne 401) - test A1 ji zachyti", r_m.status_code == 200, r_m.status_code)
    # M4: import by prepsal schvaleny text
    sql("UPDATE miniweb_product_texts SET status='approved', approved_by=%s, approved_at=NOW() WHERE miniweb_product_id=%s AND lang='en'", (admin_id, prod_wt["id"]))
    orig_u = mwa._upsert_text
    mwa._upsert_text = mutant("_upsert_text", 'if row["status"] == "approved" and not revise_approved:', "if False:")
    try:
        d5 = zaklad()
        d5["products"][1]["description"] = "Overwritten silently"
        d5["products"][1]["summary"] = "Changed after the admin looked at it"
        imp(d5, apply=True)
        prepsano = jedno("SELECT description FROM miniweb_product_texts WHERE miniweb_product_id=%s AND lang='en'", (prod_wt["id"],))["description"] == "Overwritten silently"
    finally:
        mwa._upsert_text = orig_u
    over("M4 mutace: bez ochrany by import tise prepsal schvaleny text (spravne skipped_approved) - test B6 ji zachyti", prepsano, None)
    # M5: import by zapsal approved
    orig_w = mwa._write_text_core
    mwa._write_text_core = mutant("_write_text_core", "'draft'", "'approved'", n=4)
    try:
        imp({**zaklad("en", "m5"), "categories": [{"slug": "c5", "name": "Cat five"}], "products": []}, apply=True)
        status_m5 = jedno("SELECT t.status FROM miniweb_category_texts t JOIN miniweb_categories c ON c.id=t.miniweb_category_id WHERE c.family='m5'")["status"]
    finally:
        mwa._write_text_core = orig_w
    over("M5 mutace: kdyby import zapisoval approved, text by byl verejny bez schvaleni Robertem (spravne draft) - test B2 ji zachyti", status_m5 == "approved", status_m5)
    # M6: pri chybe se zapisuje
    pred = snimek()
    orig_i = mwa.import_catalog
    mwa.import_catalog = mutant_vic("import_catalog", [('if parsed is None or report["errors"]:', "if parsed is None:", 1), ('    if report["errors"]:\n        return report\n', "    if False:\n        return report\n", 1)])
    try:
        d6 = zaklad("en", "m6")
        d6["categories"] = [{"slug": "ok-cat", "name": "Fine"}]
        d6["products"] = [{"slug": "bad-prod", "sku": "BP-1", "category": "ok-cat", "name": "Table by Logiman"}]
        with real.cursor() as cur:
            rr = mwa.import_catalog(cur, d6, apply=True)
        real.commit()
        zapsano = jedno("SELECT COUNT(*) AS n FROM miniweb_categories WHERE family='m6'")["n"]
    finally:
        mwa.import_catalog = orig_i
    over("M6 mutace: kdyby chyby (v souboru i proti databazi) import nezastavily, zapsalo by se i zbytek (spravne NIC) - test B13 ji zachyti", zapsano == 1 and rr["errors"], (zapsano, rr["errors"]))
    # M7: dokument se zastupnou znackou by se dal schvalit
    sql("INSERT INTO miniweb_documents (family, kind, lang, title, body) VALUES ('packstations','shipping','en','Shipping','Delivery in [DOPLNIT: days] days.')")
    ds = next(i for i in get(OV, uid=admin_id).get_json()["items"] if i["kind"] == "document" and i["slug"] == "shipping")
    orig_dp = mwa._doc_problems
    mwa._doc_problems = mutant("_doc_problems", 'if miniweb._doc_placeholder(title, body):', "if False:")
    try:
        r_m = post(AP, {"items": [dpol(ds)]})
    finally:
        mwa._doc_problems = orig_dp
    over("M7 mutace: bez blokace zastupnych znacek by se schvalil nedokonceny pravni text (spravne blocked) - test E11 ji zachyti", r_m.get_json()["changed"] == 1, r_m.get_json())
    sql("DELETE FROM miniweb_documents WHERE kind='shipping'")
    # M8: bez kontroly otisku u dokumentu
    dt = next(i for i in get(OV, uid=admin_id).get_json()["items"] if i["kind"] == "document" and i["slug"] == "privacy" and i["lang"] == "en")
    orig_asc = mwa.apply_status_change
    mwa.apply_status_change = mutant("apply_status_change", "elif rev_now != it[\"rev\"]:", "elif False:")
    try:
        r_m = post(AP, {"items": [{"kind": "document", "id": dt["id"], "lang": "en", "rev": "f" * 16}]})
    finally:
        mwa.apply_status_change = orig_asc
    over("M8 mutace: bez kontroly otisku by se schvalil dokument, ktery admin nevidel (spravne changed) - test E8 ji zachyti", r_m.get_json()["changed"] == 1, r_m.get_json())
    sql("UPDATE miniweb_documents SET status='draft', approved_by=NULL, approved_at=NULL WHERE kind='privacy'")
    # M9: import by prijal znacku v dokumentu
    orig_parse = mwa._parse
    mwa._parse = mutant("_parse", "if miniweb._doc_brand_hit(text):", "if False:")
    try:
        with real.cursor() as cur:
            rep_m = mwa.import_catalog(cur, doc_soubor([{"kind": "cookies", "title": "Cookies", "body": "Data go to Logiman Prague."}]))
        real.rollback()
    finally:
        mwa._parse = orig_parse
    over("M9 mutace: bez filtru znacky by import prijal dokument se znackou (spravne chyba) - test E9 ji zachyti", not rep_m["errors"], rep_m["errors"])
finally:
    with real.cursor() as cur:
        for t in TEMP_LIKE:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (storefronty, mini-shopy, katalog, texty, audit, uzivatele) jsou po testu beze zmeny", po == PRED_OSTRE, (PRED_OSTRE, po))
ok = sum(vysl)
print(f"\nVYSLEDEK mini-shop faze 1b - import a schvalovani textu: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
