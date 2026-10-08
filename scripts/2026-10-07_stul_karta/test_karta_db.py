#!/opt/konfigurator/api/venv/bin/python
"""Test JADRA karty z konfigurace (api/stul_karta.py: plan() + vytvor()) nad DOCASNYMI tabulkami (bot10, 2026-10-07).

Nic se nezapisuje do ostrych dat: pro SOUBEZNE spojeni se vytvori TEMPORARY tabulky shop_products, app_settings, audit_log a content_categories (stini ostre), naplni se kopii potrebnych
radku (karty generatoru, registr configurator_products, pravidla, kategorie stolu) a jadro bezi nad nimi; GLB se pise do docasneho adresare. Na konci se na NOVEM spojeni overi, ze ostre
tabulky (pocty, registr, klice stul_karta_*) ani adresar webapp/katalog/stul/ se nezmenily. Registr produktu (konfigurator_registr) cte ostre `configurator_products` jen ke cteni.

Spusteni (DB pres systemd, ne cteni api/.env):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
    api/venv/bin/python3 scripts/2026-10-07_stul_karta/test_karta_db.py [--rychle]      (--rychle: bez stavby skutecnych modelu GLB)
Kandidat pred nasazenim: KARTA_DIR=<adresar s kandidatnim stul_karta.py> (pridan na zacatek sys.path). Konci kodem 0 jen kdyz VSE prosla."""
import json
import os
import re
import shutil
import sys
import tempfile
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
if os.environ.get("KARTA_DIR"):                                  # kandidatni moduly (stul_karta.py, products.py) maji prednost pred zivymi
    sys.path.insert(0, os.environ["KARTA_DIR"])
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
try:
    import app as appmod  # noqa: E402,F401
    import stul_karta as K  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import stul_glb  # noqa: E402
    import v3d_glb  # noqa: E402
finally:
    threading.Thread.start = _o

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _docasne import connect, KARTY, CIZI, stav_ostry, priprav  # noqa: E402

RYCHLE = "--rychle" in sys.argv
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


def vyber_vychozi(system):
    return SH.vychozi_vyber(system)


def radek(cur, sql, args=()):
    cur.execute(sql, args)
    return cur.fetchone()


def chyba_z(fn, *a, **k):
    try:
        fn(*a, **k)
    except K._Chyba as e:
        return e
    return None


def vstup(pid, sel, **extra):
    body = {"product_id": pid, "configuration": {"selection": sel, "rules_version": None}}
    body.update(extra)
    return K._vstup(body)


def main():
    pred = stav_ostry(K)
    test = connect()
    karty, kategorie = priprav(test, K)
    cur = test.cursor()
    tmp = tempfile.mkdtemp(prefix="stul_karta_test_")
    try:
        # ---------------------------------------------------------------- 0) cisté funkce (texty, nazvy, vstup)
        print("\n## 0) texty, nazvy, vstup")
        over("0.1 zaklad nazvu: koncovka 'konfigurovatelny' se odrizne", K.zaklad_nazvu("Pracovní stůl systém 40 – konfigurovatelný") == "Pracovní stůl systém 40", K.zaklad_nazvu("Pracovní stůl systém 40 – konfigurovatelný"))
        over("0.2 zaklad nazvu: rozmery drivejsi karty se odriznou (karta z karty)", K.zaklad_nazvu("Pracovní stůl systém 40 – 1280 × 800 × 840 mm") == "Pracovní stůl systém 40")
        over("0.3 zaklad nazvu: prazdny/None = vychozi", K.zaklad_nazvu(None) == "Pracovní stůl" and K.zaklad_nazvu("") == "Pracovní stůl")
        over("0.4 auto nazev nese rozmery desky", K.auto_nazev("Pracovní stůl systém 40 – konfigurovatelný", {"w": 1280, "d": 800.0, "h": 840}) == "Pracovní stůl systém 40 – 1280 × 800 × 840 mm")
        over("0.5 auto nazev bez rozmeru (neplatny vyber) = jen zaklad", K.auto_nazev("Stůl", {"w": "x"}) == "Stůl")
        over("0.6 popis: text karty + parametry; opakovane volani blok parametru nezdvojuje",
             K.popis("Úvod.", [{"label": "Šířka", "value": "1 mm"}]) == "Úvod.\n\nParametry této konfigurace:\n- Šířka: 1 mm"
             and K.popis(K.popis("Úvod.", [{"label": "A", "value": "1"}]), [{"label": "B", "value": "2"}]) == "Úvod.\n\nParametry této konfigurace:\n- B: 2")
        over("0.7 popis: prazdne hodnoty se preskoci, text se zkrati na limit", K.popis(None, [{"label": "A", "value": ""}, {"label": "B", "value": "2"}]).endswith("- B: 2")
             and len(K.popis("x" * 5000, [])) <= K.MAX_POPIS)
        e = chyba_z(K._nazev, "Stůl [poznámka]")
        over("0.8 nazev se zavorkami je zamitnut (400 invalid_name)", e and e.status == 400 and e.code == "invalid_name", e and (e.status, e.code))
        over("0.9 nazev: mezery se sloucí, kratky/dlouhy zamitnut",
             K._nazev("  Stůl   1500  ") == "Stůl 1500" and chyba_z(K._nazev, "ab").code == "invalid_name" and chyba_z(K._nazev, "x" * 201).code == "invalid_name" and K._nazev("") is None)
        sel40 = vyber_vychozi(40)
        over("0.10 vstup: bez product_id / bez selection / hash prilis dlouhy / active neni bool = 400",
             all((chyba_z(K._vstup, b) or Exception()).__class__ is K._Chyba and chyba_z(K._vstup, b).status == 400 for b in (
                 None, {}, {"product_id": 1}, {"product_id": 1, "configuration": {"selection": {}}, "hash": "x" * 65}, {"product_id": 1, "configuration": {"selection": {}}, "active": "ano"},
                 {"product_id": 1, "configuration": {"selection": {}}, "category_id": "abc"})))
        v = vstup(KARTY[40], sel40, nahled=True, hash="abc")
        over("0.11 vstup: nahled, hash a defaulty (active True, name None, kategorie None)", v["nahled"] is True and v["hash"] == "abc" and v["active"] is True and v["name"] is None and v["category_id"] is None, v)

        # ---------------------------------------------------------------- 1) plan pro vsechny systemy
        print("\n## 1) plan() pro generatory 30 / 35 / 40 / 41 / 45")
        plany = {}
        for sy, pid in KARTY.items():
            p = K.plan(cur, vstup(pid, vyber_vychozi(sy)), True)
            plany[sy] = p
            hash_nezavisly = stul_glb.kanonicky_hash(SH.normalizuj(p["res"]["selection"], sy)[0])
            over(f"1.{sy}a system {sy}: SKU odpovida kontraktu bot4 (regex) a hash8 = prvnich 8 znaku kanonickeho hashe (nezavisly vypocet)",
                 K.SKU_RE.match(p["sku"]) and p["sku"] == f"STUL-S{sy}-{hash_nezavisly[:8]}" and p["res"]["hash"] == hash_nezavisly, (p["sku"], hash_nezavisly))
            over(f"1.{sy}b system {sy}: recept, nazev s rozmery, cena > 0 bez DPH a popis s parametry", p["system"] == sy and SH.RECEPTY[p["recept"]] == sy
                 and re.search(r" – \d+ × \d+ × \d+ mm$", p["nazev"]) and p["cena_net"] > 0 and K.POPIS_PARAMETRY in p["popis"], (p["nazev"], p["cena_net"]))
            over(f"1.{sy}c system {sy}: zatim neexistuje, pravo aktivovat -> aktivni", p["existujici"] is None and p["aktivni"] is True)
        over("1.6 kategorie: 30->206, 35->312, 40->311, 41->183, 45->330 (Robert 2026-10-08 zalozil kategorii Robustni balici stul system 45)",
             [plany[s]["kategorie_id"] for s in (30, 35, 40, 41, 45)] == [206, 312, 311, 183, 330], [plany[s]["kategorie_id"] for s in (30, 35, 40, 41, 45)])
        over("1.7 nabidka kategorii: korenova 182 prvni, pak potomci; vse viditelne", plany[40]["kategorie"][0]["id"] == 182 and {206, 311, 312, 183} <= {k["id"] for k in plany[40]["kategorie"]})
        over("1.8 ruzne systemy = ruzne SKU (prefix systemu)", len({p["sku"] for p in plany.values()}) == 5)
        p40 = plany[40]
        p40b = K.plan(cur, vstup(KARTY[40], vyber_vychozi(40)), False)
        over("1.9 bez prava upravovat karty se plan tvari neaktivni", p40b["aktivni"] is False and p40b["muze_aktivovat"] is False)
        p40c = K.plan(cur, vstup(KARTY[40], vyber_vychozi(40), active=False), True)
        over("1.10 active=false v pozadavku -> neaktivni i s pravem", p40c["aktivni"] is False)
        sel_w = dict(vyber_vychozi(40)); sel_w["w"] = 1500
        pw = K.plan(cur, vstup(KARTY[40], sel_w), True)
        over("1.11 jina konfigurace = jine SKU a rozmer v nazvu", pw["sku"] != p40["sku"] and "1500 ×" in pw["nazev"], pw["nazev"])
        pn = K.plan(cur, vstup(KARTY[40], vyber_vychozi(40), name="  Můj stůl  ", category_id=312), True)
        over("1.12 vlastni nazev (ocisteny) a vybrana kategorie z nabidky", pn["nazev"] == "Můj stůl" and pn["kategorie_id"] == 312, (pn["nazev"], pn["kategorie_id"]))

        # ---------------------------------------------------------------- 2) chyby planu
        print("\n## 2) chyby planu")
        e = chyba_z(K.plan, cur, vstup(CIZI, {"w": 1}), True)
        over("2.1 produkt, ktery neni konfigurovatelny stul = 404 not_configurable", e and (e.status, e.code) == (404, "not_configurable"), e and (e.status, e.code))
        e = chyba_z(K.plan, cur, vstup(99999999, {"w": 1}), True)
        over("2.2 neexistujici produkt = 404 not_configurable", e and (e.status, e.code) == (404, "not_configurable"))
        e = chyba_z(K.plan, cur, vstup(KARTY[40], vyber_vychozi(40), hash="0000000000000000"), True)
        over("2.3 hash ze stranky se lisi od serverova = 409 configuration_changed", e and (e.status, e.code) == (409, "configuration_changed"), e and (e.status, e.code))
        e = chyba_z(K.plan, cur, K._vstup({"product_id": KARTY[40], "configuration": {"selection": vyber_vychozi(40), "rules_version": "stara-verze"}}), True)
        over("2.4 stara verze pravidel = 409 rules_changed", e and (e.status, e.code) == (409, "rules_changed"), e and (e.status, e.code))
        e = chyba_z(K.plan, cur, vstup(KARTY[40], vyber_vychozi(40), category_id=1), True)
        over("2.5 kategorie mimo nabidku = 400 invalid_category", e and (e.status, e.code) == (400, "invalid_category"), e and (e.status, e.code))
        puvodni_vyres = K.kk.vyres
        def vyres_422(cur_, pid_, sel_, lang_="cs", rv_=None):
            raise K.kk.KonfiguraceChyba("invalid_configuration", "Tuto konfiguraci nelze vyrobit.", 422, errors=[{"slot": None, "message": "Police se nevejde."}])
        K.kk.vyres = vyres_422
        try:
            e = chyba_z(K.plan, cur, vstup(KARTY[40], vyber_vychozi(40)), True)
        finally:
            K.kk.vyres = puvodni_vyres
        over("2.6 nevyrobitelna konfigurace (vyres 422) = 422 invalid_configuration se seznamem duvodu, plan nevznikne", e and (e.status, e.code) == (422, "invalid_configuration") and e.extra.get("errors") == [{"slot": None, "message": "Police se nevejde."}], e and (e.status, e.code, e.extra))
        def vyres_cena(cur_, pid_, sel_, lang_="cs", rv_=None):
            raise K.kk.KonfiguraceChyba("price_on_request", "Cena konfigurace není k dispozici.", 409)
        K.kk.vyres = vyres_cena
        try:
            e = chyba_z(K.plan, cur, vstup(KARTY[40], vyber_vychozi(40)), True)
        finally:
            K.kk.vyres = puvodni_vyres
        over("2.7 cena na dotaz (vyres 409) = 409 price_on_request, karta bez ceny nevznikne", e and (e.status, e.code) == (409, "price_on_request"), e and (e.status, e.code))

        # ---------------------------------------------------------------- 3) zalozeni karty (rychly model)
        print("\n## 3) vytvor(): karta + registr + vychozi vyber + zaznam + audit (maly zastupny GLB)")
        def maly_model(selection, product_id):
            return b"glTFfake-" + str(sorted(selection.items()))[:50].encode()
        nove_id, slug, vyber = K.vytvor(cur, 1, p40, adresar_glb=tmp, model_fn=maly_model)
        test.commit()
        k = radek(cur, "SELECT * FROM shop_products WHERE id=%s", (nove_id,))
        over("3.1 karta vznikla: SKU, nazev, slug, cena, aktivni + activated_at, glb_file, kategorie",
             k and k["sku"] == p40["sku"] and k["name"] == p40["nazev"] and k["slug"] and float(k["price_czk_placeholder"]) == float(p40["cena_net"]) and k["active"] == 1 and k["activated_at"] is not None
             and k["glb_file"] == "stul/" + p40["sku"] + ".glb" and k["category_id"] == 311, k and {x: k[x] for x in ("sku", "name", "slug", "price_czk_placeholder", "active", "activated_at", "glb_file", "category_id")})
        zdroj = karty[KARTY[40]]
        over("3.2 jednotka, dostupnost, zobrazeni ceny a material renderu se kopiruji z karty generatoru",
             all(k[c] == zdroj[c] for c in ("unit", "availability_text", "price_visible_default", "hover_show_price", "hover_show_availability", "render_material_key")))
        over("3.3 popis = text karty generatoru + parametry konfigurace", (zdroj["description"] or "").strip() in k["description"] and K.POPIS_PARAMETRY in k["description"] and "Šířka desky" in k["description"], k["description"][:300])
        over("3.4 nedotcene sloupce zustaly na vychozich (bez dodavatele / Dogus / sceny)", k["visible_in_scene"] == 0 and k["stock_qty"] == 0 and k["is_archived"] == 0 and k["is_supplier_item"] == 0 and k["cfg_dily_id"] is None)
        over("3.5 GLB lezi v adresari, atomicky zapsany (zadny .tmp nezustal)", os.path.isfile(os.path.join(tmp, p40["sku"] + ".glb")) and not [f for f in os.listdir(tmp) if f.endswith(".tmp")], os.listdir(tmp))
        reg = json.loads(radek(cur, "SELECT setting_value v FROM app_settings WHERE setting_key='configurator_products'")["v"])
        puvodni = json.loads(radek(connect().cursor(), "SELECT setting_value v FROM app_settings WHERE setting_key='configurator_products'")["v"])
        over("3.6 registr: nova karta -> recept zdroje, vsechny dosavadni zaznamy beze zmeny", reg.get(str(nove_id)) == p40["recept"] and all(reg.get(a) == b for a, b in puvodni.items()) and len(reg) == len(puvodni) + 1, reg)
        vych = json.loads(radek(cur, "SELECT setting_value v FROM app_settings WHERE setting_key=%s", ("configurator_default_%d" % nove_id,))["v"])
        zaz = json.loads(radek(cur, "SELECT setting_value v FROM app_settings WHERE setting_key=%s", ("stul_karta_%d" % nove_id,))["v"])
        over("3.7 ulozeny vychozi vyber = efektivni vyber konfigurace", vych == p40["res"]["selection"] == vyber, (len(vych), len(p40["res"]["selection"])))
        over("3.8 zaznam stul_karta_<id>: system, vyber, rules_version, hash, kod, zdroj karty, SKU",
             zaz["system"] == 40 and zaz["selection"] == vych and zaz["hash"] == p40["res"]["hash"] and zaz["kod"] == p40["res"]["kod"] and zaz["zdroj_karta"] == KARTY[40] and zaz["sku"] == p40["sku"]
             and zaz["rules_version"] == p40["res"]["rules_version"] and zaz["v"] == K.VERZE, zaz)
        au = radek(cur, "SELECT * FROM audit_log WHERE entity_id=%s AND action='create_from_configuration'", (nove_id,))
        over("3.9 audit_log: create_from_configuration / shop_product, detail s SKU, hashem a zdrojem", au and au["entity_type"] == "shop_product" and p40["sku"] in au["detail"] and p40["res"]["hash"] in au["detail"], au)
        over("3.10 hash8 v SKU == prvnich 8 znaku hashe ulozeneho vyberu (podminka 'hotova k renderu' bot4)",
             K.SKU_RE.match(k["sku"]).group(2) == stul_glb.kanonicky_hash(SH.normalizuj(vych, 40)[0])[:8])

        # ---------------------------------------------------------------- 4) idempotence
        print("\n## 4) idempotence a soubeh")
        pdr = K.plan(cur, vstup(KARTY[40], vyber_vychozi(40)), True)
        over("4.1 stejna konfigurace: plan najde existujici kartu (odpoved existing, nic se nezaklada)", pdr["existujici"] and pdr["existujici"]["id"] == nove_id, pdr["existujici"])
        od = K.odpoved_existujici(pdr)
        over("4.2 odpoved existing: id, aktivni, url ze slugu", od["existing"] is True and od["id"] == nove_id and od["active"] is True and od["url"] == "/produkt/" + slug, od)
        e = chyba_z(K.vytvor, cur, 1, pdr, tmp, maly_model)
        test.rollback()
        over("4.3 soubezne zalozeni (SKU vzniklo mezi planem a zapisem) = 409 exists a zadny novy soubor", e and (e.status, e.code) == (409, "exists") and sorted(os.listdir(tmp)) == [p40["sku"] + ".glb"], (e and e.code, os.listdir(tmp)))
        po = radek(cur, "SELECT COUNT(*) n FROM shop_products WHERE sku=%s", (p40["sku"],))["n"]
        over("4.4 po neuspechu stale prave jedna karta s timhle SKU", po == 1, po)

        # ---------------------------------------------------------------- 5) neaktivni (bez prava)
        print("\n## 5) karta bez prava aktivovat")
        sel_n = dict(vyber_vychozi(40)); sel_n["w"] = 1400
        pn2 = K.plan(cur, vstup(KARTY[40], sel_n), False)
        id2, slug2, _ = K.vytvor(cur, 1, pn2, adresar_glb=tmp, model_fn=maly_model)
        test.commit()
        k2 = radek(cur, "SELECT active, activated_at, slug FROM shop_products WHERE id=%s", (id2,))
        over("5.1 vznikla NEAKTIVNI, bez activated_at; slug je jiny nez u prvni karty", k2["active"] == 0 and k2["activated_at"] is None and k2["slug"] != k["slug"], k2)
        o = K.odpoved_vytvoreno(pn2, id2, slug2)
        over("5.2 odpoved: active false + poznamka", o["active"] is False and "NEAKTIVNÍ" in (o["poznamka"] or ""), o)

        # ---------------------------------------------------------------- 6) rollback pri selhani po zapisu GLB
        print("\n## 6) selhani po zapisu GLB: soubor se smaze, DB se vrati")
        sel_f = dict(vyber_vychozi(40)); sel_f["w"] = 1600
        pf = K.plan(cur, vstup(KARTY[40], sel_f), True)
        puvodni_slug = K._product_slug_for_name
        K._product_slug_for_name = lambda c, n: (_ for _ in ()).throw(RuntimeError("slug selhal"))
        try:
            try:
                K.vytvor(cur, 1, pf, adresar_glb=tmp, model_fn=maly_model)
                vyj = None
            except RuntimeError as ex:
                vyj = ex
        finally:
            K._product_slug_for_name = puvodni_slug
        test.rollback()
        over("6.1 vyjimka se propusti, novy GLB se smazal, v DB po rollbacku nic neni",
             vyj is not None and not os.path.exists(os.path.join(tmp, pf["sku"] + ".glb")) and radek(cur, "SELECT COUNT(*) n FROM shop_products WHERE sku=%s", (pf["sku"],))["n"] == 0, (vyj, os.listdir(tmp)))
        # existujici soubor (predchozi pokus) se pri selhani NEsmaze
        K._zapis_glb(pf["sku"], b"stary", tmp)
        K._product_slug_for_name = lambda c, n: (_ for _ in ()).throw(RuntimeError("slug selhal"))
        try:
            try:
                K.vytvor(cur, 1, pf, adresar_glb=tmp, model_fn=maly_model)
            except RuntimeError:
                pass
        finally:
            K._product_slug_for_name = puvodni_slug
        test.rollback()
        over("6.2 soubor, ktery tam uz byl, se pri selhani nemaze (jen nove zapsany)", os.path.isfile(os.path.join(tmp, pf["sku"] + ".glb")))
        def spadly_model(selection, product_id):
            raise ValueError("model spadl")
        e = chyba_z(K.vytvor, cur, 1, pf, tmp, lambda s, p: K._model_pro_kartu(s, p) if False else (_ for _ in ()).throw(K._Chyba(500, "glb_failed", "x")))
        test.rollback()
        over("6.3 model nevznikl -> _Chyba bez zapisu do DB", e and e.code == "glb_failed" and radek(cur, "SELECT COUNT(*) n FROM shop_products WHERE sku=%s", (pf["sku"],))["n"] == 0, e and e.code)
        # registr nesmi zustat poskozeny po rollbacku
        reg2 = json.loads(radek(cur, "SELECT setting_value v FROM app_settings WHERE setting_key='configurator_products'")["v"])
        over("6.4 po rollbacku registr obsahuje jen zaznamy z vydanych karet", set(reg2) == set(puvodni) | {str(nove_id), str(id2)}, sorted(reg2))

        # ---------------------------------------------------------------- 7) skutecny model
        if RYCHLE:
            print("\n## 7) skutecny model GLB - PRESKOCENO (--rychle)")
        else:
            print("\n## 7) skutecny model GLB (stavba generatoru)")
            tmp2 = tempfile.mkdtemp(prefix="stul_karta_glb_")
            try:
                for sy, pid in KARTY.items():
                    sel = dict(vyber_vychozi(sy))
                    sel["w"] = 1300 + sy                                    # jina konfigurace pro kazdy system (zadna z predchozich karet)
                    ps = K.plan(cur, vstup(pid, sel), True)
                    nid, sl, _ = K.vytvor(cur, 1, ps, adresar_glb=tmp2)
                    test.commit()
                    cesta = os.path.join(tmp2, ps["sku"] + ".glb")
                    raw = open(cesta, "rb").read()
                    spec = v3d_glb.embedded_spec(raw)
                    gltf, _bin = v3d_glb.read_glb(raw)
                    over(f"7.{sy} system {sy}: GLB je platny (magic glTF), ma extras.v3d.front (3 cisla) a dims; velikost > 100 kB",
                         raw[:4] == b"glTF" and isinstance(spec.get("front"), list) and len(spec["front"]) == 3 and spec.get("dims") is not None and len(raw) > 100_000, (len(raw), spec and list(spec)[:8]))
                    over(f"7.{sy}b system {sy}: ulozeny model je S razitky loga (pravidlo 61: stejne bajty jako GLB s razitky, razitka=True)", raw == SH.glb_bytes(ps["res"]["selection"], sy, razitka=True))
                    k7 = radek(cur, "SELECT sku, glb_file FROM shop_products WHERE id=%s", (nid,))
                    over(f"7.{sy}c system {sy}: glb_file odpovida souboru", k7["glb_file"] == "stul/" + k7["sku"] + ".glb" and os.path.isfile(os.path.join(tmp2, os.path.basename(k7["glb_file"]))))
            finally:
                shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        test.rollback()
        test.close()
        shutil.rmtree(tmp, ignore_errors=True)

    po = stav_ostry(K)
    print("\n## 9) ostre tabulky a adresar se nezmenily")
    over("9.1 ostre shop_products (pocet, max id), registr, klice karet a audit_log beze zmeny", pred == po, {k: (pred[k], po[k]) for k in pred if pred[k] != po[k]})
    print("\n%d/%d OK" % (sum(vysl), len(vysl)))
    sys.exit(0 if all(vysl) else 1)


main()
