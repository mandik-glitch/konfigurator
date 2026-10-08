#!/opt/konfigurator/api/venv/bin/python
"""Test ENDPOINTU karty z konfigurace (GET / POST /api/admin/konfigurace/karta v api/stul_karta.py) pres Flask test_client nad DOCASNYMI tabulkami (bot10, 2026-10-07).

Skutecna aplikace (RBAC dekoratory, cesty, JSON), ale DB zapisy jdou do TEMPORARY tabulek souvisleho spojeni (shop_products, app_settings, audit_log, content_categories - viz _docasne.py)
a GLB do docasneho adresare; ostre tabulky a webapp/katalog/stul/ se kontroluji PRED a PO. Prihlaseny admin = session s id skutecneho admina (jen cteni app_users). Model GLB je v tomhle testu
zastupny (skutecne modely testuje test_karta_db.py).

Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
            api/venv/bin/python3 scripts/2026-10-07_stul_karta/test_karta_route.py       (kandidat: KARTA_DIR=<adresar s kandidatnim stul_karta.py>)"""
import json
import os
import shutil
import sys
import tempfile
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
if os.environ.get("KARTA_DIR"):                                  # kandidatni moduly (stul_karta.py, products.py) maji prednost pred zivymi
    sys.path.insert(0, os.environ["KARTA_DIR"])
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
try:
    import app as appmod  # noqa: E402
    import stul_karta as K  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import products as PRODUCTS  # noqa: E402
finally:
    threading.Thread.start = _o
from _docasne import connect, KARTY, CIZI, stav_ostry, priprav  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


class SdileneSpojeni:
    """Atrapa get_conn(): vrati stale TO SAMO spojeni s temp tabulkami; close() dela rollback jako skutecne sdilene spojeni (pooled-conn past)."""
    def __init__(self, conn):
        self.c = conn

    def cursor(self):
        return self.c.cursor()

    def commit(self):
        self.c.commit()

    def rollback(self):
        self.c.rollback()

    def close(self):
        self.c.rollback()


def main():
    pred = stav_ostry(K)
    test = connect()
    priprav(test, K)
    tmp = tempfile.mkdtemp(prefix="stul_karta_route_")
    puv_dir, K.KATALOG_STUL_DIR = K.KATALOG_STUL_DIR, tmp          # puvodni adresar se na konci VRACI: stav_ostry() v 9.1 jinak cte uz smazany tmp (do 2026-10-08 to prochazelo jen proto, ze ostry adresar neexistoval)
    puv_get_conn, puv_model, puv_has = K.get_conn, K._model_pro_kartu, K.has_permission
    K.get_conn = lambda: SdileneSpojeni(test)
    K._model_pro_kartu = lambda selection, product_id: b"glTF-zastupny-model"
    client = appmod.app.test_client()
    pc = connect(); cu = pc.cursor()
    cu.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
    admin_id = cu.fetchone()["id"]; pc.rollback(); pc.close()
    cur = test.cursor()
    sel = SH.vychozi_vyber(40)

    def post(body, **kw):
        r = client.post("/api/admin/konfigurace/karta", data=json.dumps(body), content_type="application/json", **kw)
        return r.status_code, (r.get_json(silent=True) or {})

    def telo(sel_, **extra):
        t = {"product_id": KARTY[40], "configuration": {"selection": sel_, "rules_version": None}}
        t.update(extra)
        return t

    def pocet(sku=None):
        cur.execute("SELECT COUNT(*) n FROM shop_products" + (" WHERE sku=%s" if sku else ""), (sku,) if sku else ())
        return cur.fetchone()["n"]

    vychozi_pocet = pocet()
    try:
        # ---------------------------------------------------------------- 1) pristup
        print("\n## 1) pristup (RBAC)")
        r = client.get("/api/admin/konfigurace/karta")
        over("1.1 anonym: GET sonda = 401", r.status_code == 401, r.status_code)
        r = client.post("/api/admin/konfigurace/karta", data=json.dumps(telo(sel)), content_type="application/json")
        over("1.2 anonym: POST = 401 a nic se nezalozilo", r.status_code == 401 and pocet() == vychozi_pocet, (r.status_code, pocet(), vychozi_pocet))
        puv_cu = appmod.current_user
        appmod.current_user = lambda: {"id": 4242, "role": "user", "active": 1, "email": "z@example.test", "name": "Zakaznik"}
        try:
            r1 = client.get("/api/admin/konfigurace/karta"); r2 = client.post("/api/admin/konfigurace/karta", data=json.dumps(telo(sel)), content_type="application/json")
        finally:
            appmod.current_user = puv_cu
        over("1.3 bezny zakaznik (role user): GET i POST = 403", r1.status_code == 403 and r2.status_code == 403, (r1.status_code, r2.status_code))
        with client.session_transaction() as s:
            s["user_id"] = admin_id
        r = client.get("/api/admin/konfigurace/karta")
        j = r.get_json(silent=True) or {}
        over("1.4 admin: GET sonda 200 {ok, verze 1, muze_aktivovat true, kategorie, vychozi_kategorie}", r.status_code == 200 and j.get("ok") is True and j.get("verze") == K.VERZE and j.get("muze_aktivovat") is True
             and j["kategorie"][0]["id"] == 182 and j["vychozi_kategorie"].get("40") == 311 and j["vychozi_kategorie"].get("45") == 330, j)

        import stul_api as SA
        volani_pravidel, puv_obnov = [], SA.obnov_pravidla
        SA.obnov_pravidla = lambda force=False: volani_pravidel.append(force)
        try:
            client.get("/api/admin/konfigurace/karta")
            client.get("/api/admin/konfigurace/nabidka")
        finally:
            SA.obnov_pravidla = puv_obnov
        over("1.5 pred trasou karty i nabidky z konfigurace se nacitaji ulozena pravidla stolu (_STUL_CESTY v stul_api.py): 2 volani obnov_pravidla", len(volani_pravidel) == 2, volani_pravidel)

        # ---------------------------------------------------------------- 2) nahled
        print("\n## 2) nahled (nic nezapisuje)")
        pred_n = pocet()
        st, j = post(telo(sel, nahled=True))
        over("2.1 nahled: 200, SKU / nazev / cena / kategorie 311 / aktivni, existing null", st == 200 and j.get("nahled") is True and K.SKU_RE.match(j.get("sku", "")) and j["name"].endswith(" mm") and j["price"]["net_czk"] > 0
             and j["price"]["gross_czk"] > j["price"]["net_czk"] and j["category_id"] == 311 and j["active"] is True and j["existing"] is None, (st, j))
        over("2.2 nahled nic nezapsal (shop_products, soubory, rate limit)", pocet() == pred_n and os.listdir(tmp) == [], (pocet(), pred_n, os.listdir(tmp)))
        sku = j["sku"]

        # ---------------------------------------------------------------- 3) vytvoreni
        print("\n## 3) vytvoreni a idempotence")
        st, j = post(telo(sel, name="  Testovací stůl  ", category_id=312))
        over("3.1 POST: 201, ok, existing false, id, SKU, nazev ocisteny, aktivni, kategorie 312, odkaz /produkt/<slug>", st == 201 and j.get("ok") is True and j["existing"] is False and j["sku"] == sku and j["name"] == "Testovací stůl"
             and j["active"] is True and j["category_id"] == 312 and j["url"].startswith("/produkt/") and j["price"]["net_czk"] > 0 and j["glb_file"] == "stul/" + sku + ".glb", (st, j))
        nid = j.get("id")
        cur.execute("SELECT active, category_id, name, glb_file FROM shop_products WHERE id=%s", (nid,))
        k = cur.fetchone()
        over("3.2 v (docasne) DB je aktivni karta s vybranou kategorii a nazvem; GLB lezi v adresari", k and k["active"] == 1 and k["category_id"] == 312 and k["name"] == "Testovací stůl" and os.path.isfile(os.path.join(tmp, sku + ".glb")), (k, os.listdir(tmp)))
        st, j2 = post(telo(sel))
        over("3.3 znovu stejna konfigurace: 200 existing true, stejne id, nic noveho", st == 200 and j2.get("existing") is True and j2["id"] == nid and pocet(sku) == 1, (st, j2))
        st, j3 = post(telo(sel, nahled=True))
        over("3.4 nahled po vzniku: existing nese id a aktivni", st == 200 and j3["existing"] and j3["existing"]["id"] == nid and j3["existing"]["active"] is True, j3)

        # ---------------------------------------------------------------- 4) chyby
        print("\n## 4) chyby (JSON s kodem, stav, nic se nezapise)")
        pred_c = pocet()
        for nazev, body, ocek in (
                ("4.1 telo neni objekt", [1, 2], (400, "invalid_selection")),
                ("4.2 chybi konfigurace", {"product_id": KARTY[40]}, (400, "invalid_selection")),
                ("4.3 produkt neni konfigurovatelny stul (priprava Multiboxu)", telo(sel, product_id=CIZI), (404, "not_configurable")),
                ("4.4 hash ze stranky se lisi", telo(sel, hash="0000000000000000"), (409, "configuration_changed")),
                ("4.5 nazev se zavorkami", telo(sel, name="Stůl [x]"), (400, "invalid_name")),
                ("4.6 kategorie mimo nabidku", telo(sel, category_id=1), (400, "invalid_category")),
                ("4.7 active neni bool", telo(sel, active="ano"), (400, "invalid_selection"))):
            st, j = post(body)
            over(nazev + f" = {ocek[0]} {ocek[1]}", (st, j.get("error")) == ocek, (st, j))
        over("4.8 po chybach se nezalozila zadna dalsi karta", pocet() == pred_c, (pocet(), pred_c))
        r = client.post("/api/admin/konfigurace/karta", data="not json", content_type="application/json")
        over("4.9 nevalidni JSON = 400", r.status_code == 400, r.status_code)

        # ---------------------------------------------------------------- 5) bez prava aktivovat
        print("\n## 5) uzivatel bez prava upravovat karty")
        K.has_permission = lambda user, section, action: action == "vytvorit"
        try:
            r = client.get("/api/admin/konfigurace/karta"); sonda = r.get_json(silent=True) or {}
            sel2 = dict(sel); sel2["w"] = 1450
            st, j = post(telo(sel2))
        finally:
            K.has_permission = puv_has
        over("5.1 sonda: muze_aktivovat false", r.status_code == 200 and sonda.get("muze_aktivovat") is False, sonda)
        over("5.2 POST s active=true: karta vznikne NEAKTIVNI (server rozhoduje, ne klient) + poznamka", st == 201 and j.get("active") is False and "NEAKTIVNÍ" in (j.get("poznamka") or ""), (st, j))
        cur.execute("SELECT active, activated_at FROM shop_products WHERE id=%s", (j.get("id"),))
        k2 = cur.fetchone()
        over("5.3 v DB active=0 a activated_at NULL", k2 and k2["active"] == 0 and k2["activated_at"] is None, k2)

        # ---------------------------------------------------------------- 6) limit
        print("\n## 6) limit zalozeni (nahled se nepocita)")
        puv_lim, puv_cu2, puv_cu_k = K.LIMIT_NA_UZIVATELE, appmod.current_user, K.current_user
        K.LIMIT_NA_UZIVATELE = (2, 3600)
        fake = lambda: {"id": 777001, "role": "admin", "active": 1, "email": "limit@example.test", "name": "Limit"}          # jiny uzivatel = cisty citac limitu (klic stul_karta:<id>)
        appmod.current_user = fake
        K.current_user = fake
        try:
            kody = []
            for w in (1460, 1470, 1480):
                s3 = dict(sel); s3["w"] = w
                kody.append(post(telo(s3))[0])
            nahled = post(telo(dict(sel, w=1490), nahled=True))[0]
        finally:
            K.LIMIT_NA_UZIVATELE, appmod.current_user, K.current_user = puv_lim, puv_cu2, puv_cu_k
        over("6.1 treti zalozeni v okne = 429 rate_limited; nahled je dal povolen", kody[2] == 429 and nahled == 200 and kody[:2] == [201, 201], (kody, nahled))

        # ---------------------------------------------------------------- 7) verejne API produktu
        print("\n## 7) detail produktu: model karty se verejne nevraci")
        cur.execute("DROP TEMPORARY TABLE content_categories")          # detail dotazuje content_categories dvakrat (rekurzivne) - TEMP tabulku MySQL nepusti (1137); cte se ostra kopie, kategorie 312 existuje i tam
        puv_pg = PRODUCTS.get_conn
        PRODUCTS.get_conn = lambda: SdileneSpojeni(test)
        try:
            r = client.get("/api/shop/products/%d" % nid)
            d = r.get_json(silent=True) or {}
            p = d.get("product", d)
            r2 = client.get("/api/shop/products/%d" % KARTY[40])
        finally:
            PRODUCTS.get_conn = puv_pg
        cur.execute("SELECT glb_file FROM shop_products WHERE id=%s", (nid,))
        over("7.1 v DB karta glb_file ma (pro render), ale detail produktu ho vraci jako null (jako u Vandr karet)", cur.fetchone()["glb_file"] == "stul/" + sku + ".glb" and r.status_code == 200 and p.get("sku") == sku and p.get("glb_file") is None,
             (r.status_code, p.get("sku"), p.get("glb_file")))
        over("7.2 karta generatoru dopadne dal beze zmeny (detail 200)", r2.status_code == 200, r2.status_code)

        # ---------------------------------------------------------------- 8) stranka karty = konfigurator s ulozenou konfiguraci
        print("\n## 8) schema konfiguratoru NOVE karty se otevira s ulozenou konfiguraci")
        sel8 = dict(sel); sel8["w"] = 1333; sel8["d"] = 777
        st, j8 = post(telo(sel8))
        nid8 = j8.get("id")
        puv_prod = SH._produkty
        mapa_ostra = dict(puv_prod())
        SH._produkty = lambda: {**mapa_ostra, str(nid8): "stul_system40"}              # registr jen v pameti (zapis registru je v TEMP tabulce, ostre schema ho nevidi)
        try:
            r = client.get("/api/shop/products/%d/configurator?lang=cs" % nid8)
            sch = r.get_json(silent=True) or {}
            rg = client.get("/api/shop/products/%d/configurator?lang=cs" % KARTY[40])
            sg = rg.get_json(silent=True) or {}
        finally:
            SH._produkty = puv_prod
        cur.execute("SELECT setting_value v FROM app_settings WHERE setting_key=%s", ("configurator_default_%d" % nid8,))
        ulozeny = json.loads(cur.fetchone()["v"])
        over("8.1 schema nove karty: 200 a vychozi vyber = ulozena (normalizovana) konfigurace, jina nez vestavena vychozi, default_saved", r.status_code == 200 and sch.get("default_selection") == ulozeny and ulozeny["w"] != SH.vychozi_vyber(40)["w"]
             and sch.get("default_saved") is True, (r.status_code, sch.get("default_selection", {}).get("w"), ulozeny.get("w"), sch.get("default_saved")))
        over("8.2 karta generatoru zustava na vestavenem vychozim (nezavisla na nove karte)", rg.status_code == 200 and sg.get("default_selection", {}).get("w") != 1333, (rg.status_code, sg.get("default_selection", {}).get("w")))
    finally:
        K.get_conn, K._model_pro_kartu, K.has_permission = puv_get_conn, puv_model, puv_has
        K.KATALOG_STUL_DIR = puv_dir
        test.rollback()
        test.close()
        shutil.rmtree(tmp, ignore_errors=True)

    po = stav_ostry(K)
    print("\n## 9) ostre tabulky a adresar se nezmenily")
    over("9.1 ostre shop_products, registr, klice karet, audit_log i webapp/katalog/stul beze zmeny", pred == po, {k: (pred[k], po[k]) for k in pred if pred[k] != po[k]})
    print("\n%d/%d OK" % (sum(vysl), len(vysl)))
    sys.exit(0 if all(vysl) else 1)


main()
