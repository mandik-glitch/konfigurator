#!/opt/konfigurator/api/venv/bin/python
"""QA kontrola miniweb_text_brand_leak (bot5, 2026-10-02): znacka/dodavatel v textech mini-shopu.

Patch scriptu nasazeni/patch_qa_checks.py se pouzije na KOPII api/qa_checks.py (nebo kandidata QA_CHECKS_PY), kopie se nacte jako modul a kontrola se spusti nad DOCASNYMI tabulkami.
Ostre tabulky se nemeni. Testuje se: nalezy ve vsech polich (kategorie, produkt, parametry, kontakt, domena), cista data bez nalezu, koncepty se kontroluji take, tvar nalezu,
registrace ve vsech 3 registrech (CHECKS, CHECK_CATEGORY, CHECK_ADDED) a ze check_qa_registration_incomplete nic nehlasi, opakovane pouziti patche nic neduplikuje, mutace regexu.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_miniweb_testy/test_qa_miniweb.py
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
PATCH = os.path.join(HERE, "nasazeni", "patch_qa_checks.py")
SRC = os.environ.get("QA_CHECKS_PY") or os.path.join(API, "qa_checks.py")
tmp = tempfile.mkdtemp(prefix="kand_qa_miniweb_")
os.makedirs(os.path.join(tmp, "api"))
cand = os.path.join(tmp, "api", "qa_checks.py")
shutil.copy(SRC, cand)
sys.path.insert(0, API)

import pymysql  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


def patch(cesta):
    return subprocess.run([sys.executable, PATCH, cesta], capture_output=True, text=True)


uz_patchnuty = "check_miniweb_text_brand_leak" in open(SRC, encoding="utf-8").read()                # po nasazeni je kontrola v ostrem souboru, patch pak nema co delat
r1 = patch(cand)
after1 = open(cand, encoding="utf-8").read()
r2 = patch(cand)
after2 = open(cand, encoding="utf-8").read()
over("P1 patch kontrolu pridal (nebo uz v souboru byla) a je opakovatelny (druhe pouziti nic nezmeni a nic neduplikuje)", r1.returncode == 0 and (("pridana" in r1.stdout) != uz_patchnuty) and r2.returncode == 0 and "uz je" in r2.stdout and after1 == after2
     and after2.count("def check_miniweb_text_brand_leak") == 1 and after2.count('"miniweb_text_brand_leak"') == 3, (r1.stdout, r1.stderr, r2.stdout))
over("P2 patchnuty soubor jde zkompilovat", subprocess.run([sys.executable, "-m", "py_compile", cand], capture_output=True).returncode == 0, None)
spec = importlib.util.spec_from_file_location("qa_checks_kand", cand)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
over("P3 kontrola je zaregistrovana ve vsech 3 registrech a check_qa_registration_incomplete o ni nic nehlasi",
     "miniweb_text_brand_leak" in qa.CHECKS and qa.CHECK_CATEGORY.get("miniweb_text_brand_leak") == "opravit" and qa.CHECK_ADDED.get("miniweb_text_brand_leak") == "2026-10-02"
     and qa.CHECKS["miniweb_text_brand_leak"][1] is qa.check_miniweb_text_brand_leak and not [x for x in qa.check_qa_registration_incomplete(None) if "miniweb" in str(x)], None)


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


TABULKY = ("car_storefronts", "miniweb_shops", "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts")


def pocty():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in TABULKY:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            return out
    finally:
        c.close()


PRED = pocty()
real = ostre()
try:
    with real.cursor() as cur:
        for t in TABULKY:
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

    def kat(slug, name, lang="en", status="approved"):
        sql("INSERT INTO miniweb_categories (slug) VALUES (%s)", (slug,))
        cid = sql("SELECT id FROM miniweb_categories WHERE slug=%s", (slug,))[0]["id"]
        sql("INSERT INTO miniweb_category_texts (miniweb_category_id, lang, name, status) VALUES (%s,%s,%s,%s)", (cid, lang, name, status))
        return cid

    CAT = kat("tables", "Tables")
    kat("clean-two", "Packing stations")
    kat("logiman-tables", "Tables for logistics")                              # znacka ve slugu
    kat("storage", "Dogus storage", status="draft")                          # znacka v nazvu, koncept se kontroluje take
    kat("racks", "Regale", lang="de")                                        # cisty text v jine nez anglictine

    def prod(slug, sku, name, summary="S", description="D", delivery="3 weeks", specs=None, lang="en", status="approved"):
        sql("INSERT INTO miniweb_products (category_id, slug, public_sku) VALUES (%s,%s,%s)", (CAT, slug, sku))
        pid = sql("SELECT id FROM miniweb_products WHERE slug=%s", (slug,))[0]["id"]
        sql("INSERT INTO miniweb_product_texts (miniweb_product_id, lang, name, summary, description, delivery, specs_json, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (pid, lang, name, summary, description, delivery, json.dumps(specs) if specs is not None else None, status))
        return pid

    prod("clean-product", "PS-1", "Clean product", specs=[{"name": "Load", "value": "150 kg"}])
    P_NAME = prod("p-name", "PS-2", "Table by Logiman")
    P_SUM = prod("p-summary", "PS-3", "Plain", summary="Built with Vandrawee")
    P_DESC = prod("p-desc", "PS-4", "Plain two", description="Made in the Konfigurator")
    P_DEL = prod("p-delivery", "PS-5", "Plain three", delivery="from Dogus stock")
    P_SPEC = prod("p-specs", "PS-6", "Plain four", specs=[{"name": "Profile", "value": "Vandr 40x40"}])
    P_SLUG = prod("logiman-slug", "PS-7", "Plain five")
    P_SKU = prod("p-sku", "LOGIMAN-8", "Plain six")
    P_DRAFT = prod("p-draft", "PS-9", "Draft with Logiman", status="draft", lang="de")

    def sf(slug, host):
        sql("INSERT INTO car_storefronts (name, slug, primary_domain, status, lang) VALUES (%s,%s,%s,'live','en')", (slug, slug, host))
        return sql("SELECT id FROM car_storefronts WHERE slug=%s", (slug,))[0]["id"]

    S_OK = sf("packstations-en", "packstations.example.top")
    S_CONTACT = sf("packstations-de", "packstationen.example.top")
    S_DOMAIN = sf("packstations-fr", "logiman-packstations.example.top")
    S_SLUG = sf("logiman-pl", "pl.packstations.example.top")
    for sid, contact in ((S_OK, {"email": "hello@packstations.example", "phone": "+353 1 555 0100"}), (S_CONTACT, {"email": "info@logiman.cz"}), (S_DOMAIN, None), (S_SLUG, None)):
        sql("INSERT INTO miniweb_shops (storefront_id, family, contact_json) VALUES (%s,'packstations',%s)", (sid, json.dumps(contact) if contact else None))

    with real.cursor() as cur:
        rows = qa.check_miniweb_text_brand_leak(cur)
    real.rollback()
    ids = {r[0] for r in rows}
    ocekavane = {
        f"kategorie:{sql('SELECT id FROM miniweb_categories WHERE slug=%s', ('logiman-tables',))[0]['id']}:en:slug",
        f"kategorie:{sql('SELECT id FROM miniweb_categories WHERE slug=%s', ('storage',))[0]['id']}:en:name",
        f"produkt:{P_NAME}:en:name", f"produkt:{P_SUM}:en:summary", f"produkt:{P_DESC}:en:description", f"produkt:{P_DEL}:en:delivery", f"produkt:{P_SPEC}:en:specs_json",
        f"produkt:{P_SLUG}:en:slug", f"produkt:{P_SKU}:en:public_sku", f"produkt:{P_DRAFT}:de:name",
        f"shop:{S_CONTACT}:contact_json", f"shop:{S_DOMAIN}:primary_domain", f"shop:{S_SLUG}:slug",
    }
    over("Q1 kontrola najde PRESNE znacku/dodavatele: kategorie (nazev, slug, koncept), produkt (nazev, shrnuti, popis, dodani, parametry, slug, verejny kod, koncept v jinem jazyce), kontakt, domena a slug shopu - nic navic a nic mene",
         ids == ocekavane, (sorted(ids - ocekavane), sorted(ocekavane - ids)))
    cista = ("miniweb_category_texts:tables", "miniweb_category_texts:clean-two", "miniweb_category_texts:racks", "miniweb_product_texts:clean-product", "miniweb_shops:packstations-en")
    over("Q2 cista data (cista kategorie, nemecka kategorie, cisty produkt s parametry, cisty shop s kontaktem) nenesou zadny nalez", not [r for r in rows if r[1] in cista] and len(rows) == len(ocekavane), [r for r in rows if r[1] in cista])
    over("Q3 tvar nalezu: (id, popisek, text), text jmenuje pole, jazyk a pravidlo, zadny nalez nenese samotny text se znackou (do adminu se nepise znovu)", all(len(r) == 3 and "pravidlo 5" in r[2] and "'" in r[2] for r in rows)
         and not any(re.search(r"Logiman by|Vandrawee|Konfigurator|Dogus stock", r[2]) for r in rows), rows[:2])
    with real.cursor() as cur:
        full = qa.run_checks(cur, only=["miniweb_text_brand_leak"])
    real.rollback()
    over("Q4 pres run_checks (jako v adminu) kontrola bezi bez chyby a vraci stejny pocet nalezu", "error" not in full["miniweb_text_brand_leak"] and len(full["miniweb_text_brand_leak"]["rows"]) == len(rows) == len(ocekavane), full["miniweb_text_brand_leak"].get("error"))
    for t_ in ("miniweb_product_texts", "miniweb_category_texts", "miniweb_shops"):
        sql(f"DELETE FROM `{t_}`")
    with real.cursor() as cur:
        prazdne = qa.check_miniweb_text_brand_leak(cur)
    real.rollback()
    over("Q5 prazdne tabulky (mini-shop jeste nema data) -> zadne nalezy a zadna chyba", prazdne == [], prazdne)

    # mutace: kdyby kontrola brala jen slovo logiman, ostatni dodavatele by prosli
    zdroj = open(cand, encoding="utf-8").read()
    mut = zdroj.replace("    hit = dealers._brand_hit\n", '    hit = lambda *t: any(x and re.search("logiman", str(x), re.I) for x in t)\n')
    assert mut != zdroj
    mpath = os.path.join(tmp, "api", "qa_mut.py")
    open(mpath, "w", encoding="utf-8").write(mut)
    spec2 = importlib.util.spec_from_file_location("qa_mut", mpath)
    qam = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(qam)
    sql("INSERT INTO miniweb_product_texts (miniweb_product_id, lang, name, summary, description, delivery, status) VALUES (%s,'en','Vandrawee product','S','D','3 weeks','approved')", (P_NAME,))
    with real.cursor() as cur:
        puvodni, mutovana = qa.check_miniweb_text_brand_leak(cur), qam.check_miniweb_text_brand_leak(cur)
    real.rollback()
    over("M1 mutace: kdyby kontrola hlidala jen slovo logiman, text s Vandrawee by prosel (spravne nalez) - test Q1 ji zachyti", len(puvodni) == 1 and mutovana == [], (puvodni, mutovana))
finally:
    with real.cursor() as cur:
        for t in TABULKY:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    real.commit()
    real.close()

over("ostre tabulky mini-shopu a storefrontu jsou po testu beze zmeny", pocty() == PRED, (PRED, pocty()))
ok = sum(vysl)
print(f"\nVYSLEDEK QA kontrola miniweb_text_brand_leak: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
