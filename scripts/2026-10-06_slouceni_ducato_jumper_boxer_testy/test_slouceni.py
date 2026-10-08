#!/opt/konfigurator/api/venv/bin/python
"""Test skriptu scripts/2026-10-06_slouceni_ducato_jumper_boxer.py nad DOCASNYMI tabulkami (bot16, 2026-10-06; Robert: slouceni kategorii Ducato / Jumper / Boxer).
Do ostre DB se NEZAPISUJE: skutecna data (kategorie, texty, sestavy) se jen PRECTOU druhym spojenim a vlozi do TEMPORARY tabulek stejnych jmen v ODDELENEM spojeni (docasna tabulka zastini
trvalou jen v tom spojeni). Po vytvoreni se overi, ze znackovy radek vlozeny do docasne tabulky ostre spojeni NEVIDI - jinak se test zastavi, nez cokoli zapise.
Overuje: vychozi stav (pocty), plan() zastavi pri zmenenem stavu (mutace), zaloha, zapis (kategorie pod 267, 116 sestav primarne v 233, sekundarni vazby na znacky, redirect, smazani 300, audit,
`active` beze zmeny, ostatni produkty nedotcene), atomicita (selhani uprostred = rollback vseho) a navrat ze zalohy (--rollback) na puvodni stav.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-06_slouceni_ducato_jumper_boxer_testy/test_slouceni.py"""
import copy
import importlib.util
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from _env import get_conn  # noqa: E402

spec = importlib.util.spec_from_file_location("slouceni", os.path.join(REPO, "scripts", "2026-10-06_slouceni_ducato_jumper_boxer.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


real = get_conn()
rc = real.cursor()


def cti(sql, args=()):
    rc.execute(sql, args or None)           # prazdny tuple by pymysql bral jako argumenty a '%Ducato%' by pad na formatovani
    return rc.fetchall()


# ---- 1) nacist skutecna data (jen SELECT)
KAT = cti("SELECT * FROM content_categories")
STR = cti("SELECT * FROM content_pages WHERE category_id IN (233, 300)")
PROD = cti("SELECT id, sku, name, category_id, active, COALESCE(is_archived,0) AS is_archived FROM shop_products WHERE name LIKE '%Ducato%' OR name LIKE '%Jumper%' OR name LIKE '%Boxer%' OR category_id IN (273, 272, 310, 301) ORDER BY id")
SEK = cti("SELECT product_id, category_id FROM shop_product_categories")
RED = cti("SELECT old_slug, category_id FROM content_category_redirects")
real.rollback()

# ---- 2) dve oddelena spojeni: tmp = docasne tabulky
tmp = get_conn()
tc = tmp.cursor()


import re


def ddl_docasna(tabulka):
    """DDL ostre tabulky prevedene na TEMPORARY: bez CONSTRAINT (cizi klice) a FULLTEXT, zbytek (sloupce, PK, unikatni a bezne indexy) stejny"""
    rc.execute("SHOW CREATE TABLE `" + tabulka + "`")
    ddl = rc.fetchone()["Create Table"]
    ddl = ddl.decode("utf-8") if isinstance(ddl, (bytes, bytearray)) else ddl
    radky = [l for l in ddl.split("\n") if not l.strip().startswith(("CONSTRAINT", "FULLTEXT"))]
    text = re.sub(r",\s*\n\)", "\n)", "\n".join(radky))
    return text.replace("CREATE TABLE", "CREATE TEMPORARY TABLE", 1)


DDL_DOCASNA = {t: ddl_docasna(t) for t in ("content_categories", "content_pages", "shop_product_categories", "content_category_redirects", "audit_log")}
real.rollback()


def sloupce_insert(tabulka, radky):
    if not radky:
        return
    cols = list(radky[0].keys())
    for i in range(0, len(radky), 50):          # davky; executemany se nepouziva (posila bytes, _StrazniCursor na nich padne)
        d = radky[i:i + 50]
        tc.execute("INSERT INTO `" + tabulka + "` (" + ",".join(f"`{c}`" for c in cols) + ") VALUES " + ",".join(["(" + ",".join(["%s"] * len(cols)) + ")"] * len(d)), [r[c] for r in d for c in cols])


def vytvor_docasne():
    for t in ("content_categories", "content_pages", "shop_product_categories", "content_category_redirects", "audit_log", "shop_products"):
        tc.execute("DROP TEMPORARY TABLE IF EXISTS `" + t + "`")
    for t in ("content_categories", "content_pages", "shop_product_categories", "content_category_redirects", "audit_log"):
        tc.execute(DDL_DOCASNA[t])          # "CREATE TEMPORARY TABLE x LIKE x" MySQL nepovoli (1066) - pouzije se DDL ostre tabulky bez cizich klicu a FULLTEXT
    tc.execute("CREATE TEMPORARY TABLE shop_products (id INT PRIMARY KEY, sku VARCHAR(80), name VARCHAR(255), category_id INT NULL, active TINYINT, is_archived TINYINT) ENGINE=InnoDB")
    sloupce_insert("content_categories", KAT)
    sloupce_insert("content_pages", STR)
    sloupce_insert("shop_products", [{k: v for k, v in p.items()} for p in PROD])
    sloupce_insert("shop_product_categories", SEK)
    sloupce_insert("content_category_redirects", RED)
    tmp.commit()


vytvor_docasne()
tc.execute("INSERT INTO content_categories (id, parent_id, name, slug, sort_order) VALUES (999999, NULL, 'TMP-ZNACKA', 'tmp-znacka-test', 0)")
tmp.commit()
rc.execute("SELECT COUNT(*) AS n FROM content_categories WHERE id=999999")
videt = rc.fetchone()["n"]
real.rollback()
if videt:
    print("STOP: docasna tabulka nezastinila trvalou - test by psal do ostre DB! Konec bez zapisu.")
    sys.exit(3)
tc.execute("DELETE FROM content_categories WHERE id=999999")
tmp.commit()
print("(docasne tabulky ok - ostre spojeni znackovy radek nevidi)")


def stav(c):
    """kompletni snimek relevantnich dat v docasnych tabulkach"""
    c.execute("SELECT id, parent_id, name, slug, sort_order FROM content_categories ORDER BY id"); k = c.fetchall()
    c.execute("SELECT id, category_id, active FROM shop_products ORDER BY id"); p = c.fetchall()
    c.execute("SELECT product_id, category_id FROM shop_product_categories ORDER BY product_id, category_id"); s = c.fetchall()
    c.execute("SELECT old_slug, category_id FROM content_category_redirects ORDER BY old_slug"); r = c.fetchall()
    c.execute("SELECT id, category_id, title, LENGTH(intro_html) AS il, LENGTH(body_html) AS bl FROM content_pages ORDER BY id"); st = c.fetchall()
    return {"kat": k, "prod": p, "sek": s, "red": r, "str": st}


print("== A) vychozi stav a plan()")
puvodni = stav(tc)
pl = S.plan(tc)
over("A1 plan() projde nad kopii skutecnych dat", True)
over("A2 pocty sestav: Ducato 107, Jumper 6, Boxer 3 (celkem 116)", pl["pocty"] == {"Ducato": 107, "Jumper": 6, "Boxer": 3} and len(pl["produkty"]) == 116, pl["pocty"])
aktivni_pred = {p[0] for p in pl["produkty"] if p[4]}
over("A3 aktivnich sestav je 14 (12 v kat. 300 + 2 Ducato v 269), zbytek neaktivni", len(aktivni_pred) == 14, len(aktivni_pred))
over("A4 testovaci VD-TEST produkt a produkty mimo vyber plan nezahrnuje", all("TEST" not in (p[1] or "") for p in pl["produkty"]))

print("== B) plan() se zastavi, kdyz se stav lisi (mutace)")
def zkus_mutaci(nazev, sql, args=()):
    vytvor_docasne()
    tc.execute(sql, args); tmp.commit()
    try:
        S.plan(tc)
        over(f"B {nazev}: plan() mel vyhodit Chyba", False)
    except S.Chyba as e:
        over(f"B {nazev}: plan() se zastavil ({str(e)[:70]}…)", True)
zkus_mutaci("233 uz presunuta pod 267", "UPDATE content_categories SET parent_id=267 WHERE id=233")
def min_id(podm):
    vytvor_docasne(); tc.execute("SELECT MIN(id) AS i FROM shop_products WHERE " + podm.replace('%', '%%')); return tc.fetchone()["i"]     # docasnou tabulku nelze v jednom dotazu cist dvakrat
zkus_mutaci("233 ma uz produkt", "UPDATE shop_products SET category_id=233 WHERE id=%s", (min_id("category_id=300"),))
zkus_mutaci("chybi jedna sestava Ducato (pocty se lisi)", "DELETE FROM shop_products WHERE id=%s", (min_id("category_id=269 AND name LIKE '%Ducato%'"),))
zkus_mutaci("300 ma podkategorii", "INSERT INTO content_categories (id, parent_id, name, slug, sort_order) VALUES (999998, 300, 'podkat', 'podkat-test', 0)")
zkus_mutaci("v 300 je nesouvisejici produkt (neni VD-)", "INSERT INTO shop_products (id, sku, name, category_id, active, is_archived) VALUES (999997, 'K-123', 'Ruzny dil', 300, 1, 0)")
zkus_mutaci("slug 300 neodpovida", "UPDATE content_categories SET slug='jiny-slug' WHERE id=300")

print("== C) zaloha + zapis")
vytvor_docasne()
puvodni = stav(tc)
pl = S.plan(tc)
zal = S.zaloha(tc, pl)
over("C1 zaloha obsahuje kategorie 233+300, jejich texty, 116 produktu, redirecty", {r["id"] for r in zal["content_categories"]} == {233, 300} and {r["category_id"] for r in zal["content_pages"]} == {233, 300} and len(zal["produkty"]) == 116, {k: len(v) if isinstance(v, list) else v for k, v in zal.items()})
over("C2 zaloha jde serializovat do JSON (datumy, desetinna cisla)", bool(json.dumps(zal, ensure_ascii=False)))
S.zapis(tc, pl)
konec = S.kontrola_po(tc, pl)
tmp.commit()
po = stav(tc)
k = {r["id"]: r for r in po["kat"]}
over("C3 kategorie 233 je pod 267 na prvnim miste (sort_order 0), slug a nazev beze zmeny", k[233]["parent_id"] == 267 and k[233]["sort_order"] == 0 and k[233]["slug"] == "vestavby-pro-ducato-jumper-boxer" and k[233]["name"] == "Vestavby pro Ducato, Jumper, Boxer", k[233])
over("C4 kategorie 300 je smazana", 300 not in k)
prim = {p["id"]: p for p in po["prod"]}
vybrane = {p[0]: p for p in pl["produkty"]}
over("C5 vsech 116 sestav ma primarni kategorii 233", all(prim[i]["category_id"] == 233 for i in vybrane), [i for i in vybrane if prim[i]["category_id"] != 233][:5])
over("C6 `active` se u zadne sestavy nezmenilo (14 aktivnich zustalo aktivnich, ostatni neaktivni)", all(prim[i]["active"] == vybrane[i][4] for i in vybrane) and {i for i in vybrane if prim[i]["active"]} == aktivni_pred)
puv = {p["id"]: p for p in puvodni["prod"]}
nedotcene = [i for i in puv if i not in vybrane]
over(f"C7 ostatni produkty ({len(nedotcene)}) jsou NEDOTCENE (kategorie i active)", all(prim[i]["category_id"] == puv[i]["category_id"] and prim[i]["active"] == puv[i]["active"] for i in nedotcene))
sek = {(s["product_id"], s["category_id"]) for s in po["sek"]}
ocek = {(i, S.ZNACKY[vybrane[i][5]]) for i in vybrane}
over("C8 kazda sestava ma sekundarni vazbu na svou znackovou kategorii (Ducato->269, Jumper->268, Boxer->288)", ocek <= sek, sorted(ocek - sek)[:5])
over("C9 zadne jine nove sekundarni vazby nevznikly", sek - {(s["product_id"], s["category_id"]) for s in puvodni["sek"]} == ocek)
over("C10 redirect vestavby-pro-fiat-ducato -> 233 existuje, puvodni redirecty zustaly", {"old_slug": "vestavby-pro-fiat-ducato", "category_id": 233} in po["red"] and all(r in po["red"] for r in puvodni["red"]))
tc.execute("SELECT COUNT(*) AS n, MIN(action) AS a FROM audit_log"); au = tc.fetchone()
over("C11 zapsany 2 audit zaznamy (update 233 + delete 300), user_id NULL", au["n"] == 2, au)
over("C12 kontrola_po: 116 sestav (14 aktivnich) v 233, 300 neexistuje", konec["produktu_v_233"] == 116 and konec["aktivnich_v_233"] == 14 and konec["300_existuje"] == 0, konec)

print("== D) navrat ze zalohy (--rollback)")
tc.execute("DELETE FROM content_pages WHERE category_id=300"); tmp.commit()     # v ostre DB to udela FK CASCADE pri DELETE kategorie 300; v docasnych tabulkach bez FK doplnime rucne
S.rollback(tc, json.loads(json.dumps(zal)))
tmp.commit()
po2 = stav(tc)
over("D1 kategorie 233 je zpet pod 184 s puvodnim poradim", {r["id"]: r for r in po2["kat"]}[233] == {r["id"]: r for r in puvodni["kat"]}[233], {r["id"]: r for r in po2["kat"]}[233])
over("D2 kategorie 300 je zpet (stejny rodic, slug, nazev, poradi)", {r["id"]: r for r in po2["kat"]}.get(300) == {r["id"]: r for r in puvodni["kat"]}[300], {r["id"]: r for r in po2["kat"]}.get(300))
over("D3 text kategorie 300 je zpet (stejna delka uvodu i obsahu)", [s for s in po2["str"] if s["category_id"] == 300] == [s for s in puvodni["str"] if s["category_id"] == 300])
over("D4 vsechny produkty maji puvodni primarni kategorii a active", po2["prod"] == puvodni["prod"])
over("D5 sekundarni vazby jsou jako pred zmenou", po2["sek"] == puvodni["sek"])
over("D6 redirect na 233 je pryc, ostatni redirecty zustaly", po2["red"] == puvodni["red"])
over("D7 po navratu se vsechny kategorie rovnaji puvodnimu stavu", po2["kat"] == puvodni["kat"])

print("== E) atomicita: selhani uprostred zapisu = rollback celeho zapisu")
vytvor_docasne()
puvodni = stav(tc)
pl = S.plan(tc)
puv_slug = S.DUCATO_SLUG
S.DUCATO_SLUG = "jiny-slug-ktery-neexistuje"      # DELETE kategorie 300 trefi 0 radku -> Chyba az PO presunu produktu a vazbach
try:
    S.zapis(tc, pl)
    over("E1 zapis mel selhat na smazani 300", False)
except S.Chyba as e:
    over(f"E1 zapis selhal uprostred ({str(e)[:60]}…)", True)
    tmp.rollback()
S.DUCATO_SLUG = puv_slug
over("E2 po rollbacku je stav IDENTICKY puvodnimu (nic z castecneho zapisu nezustalo)", stav(tc) == puvodni)

print("== F) skript sam neobsahuje nebezpecne veci")
zdroj = open(os.path.join(REPO, "scripts", "2026-10-06_slouceni_ducato_jumper_boxer.py"), encoding="utf-8").read()
over("F1 skript nemeni `active` (zadny UPDATE ... active)", "SET active" not in zdroj and "active=%s" not in zdroj.replace("COALESCE", ""))
over("F2 vychozi rezim je dry-run (zapis jen s --apply)", 'apply_ = "--apply" in argv' in zdroj and "if not apply_" in zdroj)
over("F3 zaloha se zapisuje PRED zmenami (zaloha() je volana drive nez zapis())", zdroj.index("z = zaloha(cur, pl)") < zdroj.index("zapis(cur, pl)\n        konec"))

tmp.rollback()
for t in ("content_categories", "content_pages", "shop_product_categories", "content_category_redirects", "audit_log", "shop_products"):
    tc.execute("DROP TEMPORARY TABLE IF EXISTS `" + t + "`")
tmp.close(); real.close()
print(f"\n==> {sum(vysl)}/{len(vysl)} kontrol OK")
sys.exit(0 if all(vysl) else 1)
