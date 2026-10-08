#!/opt/konfigurator/api/venv/bin/python
"""scripts/miniweb_shop.py - zalozeni a uprava mini-shopu (storefront + radek miniweb_shops) bez rucniho SQL (bot5, 2026-10-02; Robert pres bot3: nejdriv slovenska verze).

SKUTECNY skript pres main(argv, conn) nad DOCASNYMI tabulkami car_storefronts, storefront_hosts a miniweb_shops; ostre tabulky se jen ctou a po testu se porovnavaji pocty.
Cast A  nahled (nic se nezapise) a zalozeni slovenskeho shopu: storefront jen draft, radek shopu, kontakt jen telefon a doba
Cast B  opakovane spusteni, uprava jen zadanych poli, e-mail se nikdy neuklada, existujici storefront (i live) se nemeni
Cast C  chyby: nic se nezapise (slug, host, jazyk, mena, zeme, barva, znacka, e-mail v kontaktu, kolize hosta, jiny host/jazyk existujiciho storefrontu, chybejici family)
Cast G  spusteni a vypnuti (--go-live, --take-offline): podminky (nginx vhost domeny, zeme, poptavky, verejny katalog ze schvaleneho textu, schvalena ochrana osobnich udaju a identifikace prodejce), nahled, vypnuti
Cast D  mutace: bez kontroly znacky, bez nahledu (zapis bez --apply), prepnuti do live, spusteni bez podminek
Kandidat: MINIWEB_PY=/cesta/miniweb.py (skript pouziva _visible_products a _documents z miniweb.py)
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_miniweb_testy/test_miniweb_shop.py
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
sys.path.insert(0, API)
tmp = tempfile.mkdtemp(prefix="kand_miniweb_shop_")
shutil.copy(os.environ.get("MINIWEB_PY") or os.path.join(API, "miniweb.py"), os.path.join(tmp, "miniweb.py"))
sys.path.insert(0, tmp)                    # kandidat PRED importem app (app.py importuje nasazeny miniweb, jinak by kandidat vyhrala kopie z cache modulu)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import company_info as firma_mod  # noqa: E402
import miniweb  # noqa: E402,F401  (skript si ho importuje sam; tady jen overeni, ze je nasazeny)
import dealers  # noqa: E402,F401

SKRIPT = os.path.join(REPO, "scripts", "miniweb_shop.py")
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


def nacti(zdroj=None):
    ns = {"__name__": "miniweb_shop_test", "__file__": SKRIPT}
    exec(compile(zdroj if zdroj is not None else open(SKRIPT, encoding="utf-8").read(), SKRIPT, "exec"), ns)
    return ns


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


TABULKY = ("car_storefronts", "storefront_hosts", "miniweb_shops", "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_documents")


def stav_ostrych():
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


PRED = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith("SELECT") else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


def pocty():
    return tuple(sql(f"SELECT COUNT(*) AS n FROM `{t}`")[0]["n"] for t in TABULKY)


NGX_TMP = tempfile.mkdtemp(prefix="nginx_enabled_")                      # misto /etc/nginx/sites-enabled: vhost "nainstaluje" test


def spust(argv, ns=None):
    """-> (navratovy kod, vystup)."""
    ns = ns or MAIN
    ns["NGINX_ENABLED"] = NGX_TMP
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ns["main"](argv, conn=real)
    return rc, buf.getvalue()


MAIN = nacti()
try:
    with real.cursor() as cur:
        for t in TABULKY:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
    real.commit()

    over("A0 testovany miniweb je kandidat, ne nasazena kopie z cache modulu", miniweb.__file__.startswith(tmp), miniweb.__file__)
    SK = ["--slug", "packstations-sk", "--host", "baliace-stoly.top", "--lang", "sk", "--family", "packstations", "--currency", "EUR", "--locale", "sk-SK", "--countries", "sk, cz,AT,sk",
          "--phone", "+421 2 5555 0100", "--hours", "Po-Pi 9:00-17:00", "--name", "Baliace stoly (SK)"]

    # ============================================================================================================ A) nahled a zalozeni
    print("== A nahled a zalozeni")
    rc, out = spust(SK)
    over("A1 bez --apply je to NAHLED: nic se nezapise (zadny storefront ani radek shopu), vypise co by se stalo", rc == 0 and pocty()[:3] == (0, 0, 0) and "NÁHLED" in out and "vytvořit storefront packstations-sk" in out
         and "vytvořit řádek shopu" in out, (rc, out, pocty()))
    rc, out = spust(SK + ["--apply"])
    sf = jedno("SELECT * FROM car_storefronts WHERE slug='packstations-sk'")
    sh = jedno("SELECT * FROM miniweb_shops WHERE storefront_id=%s", (sf["id"],)) if sf else None
    over("A2 --apply zalozi storefront (domena, jazyk sk, kind miniweb, VZDY draft, sloupec certifikacni skupiny = miniweb: mini-shopy maji vlastni vhost a sdileny certifikat) a radek shopu (rodina, EUR, sk-SK, zeme bez duplicit a velkymi pismeny, kontakt jen telefon a doba)",
         rc == 0 and sf is not None and sf["primary_domain"] == "baliace-stoly.top" and sf["lang"] == "sk" and sf["kind"] == "miniweb" and sf["status"] == "draft" and sf["origin_cert_group"] == "miniweb"
         and sf["name"] == "Baliace stoly (SK)" and sh["family"] == "packstations" and sh["currency"] == "EUR" and sh["locale"] == "sk-SK" and sh["countries"] == "SK,CZ,AT" and sh["price_mode"] == "hidden" and sh["inquiry_enabled"] == 1
         and json.loads(sh["contact_json"]) == {"phone": "+421 2 5555 0100", "hours": "Po-Pi 9:00-17:00"} and "ZAPSÁNO" in out, (rc, out, sf, sh))
    over("A3 radek shopu je propojen se storefrontem (JOIN podle domeny najde shop; storefront zustava koncept, jen pro staff)",
         jedno("SELECT s.status, m.currency FROM car_storefronts s JOIN miniweb_shops m ON m.storefront_id = s.id WHERE s.primary_domain='baliace-stoly.top'") == {"status": "draft", "currency": "EUR"}, None)

    # ============================================================================================================ B) opakovani a uprava
    print("== B opakovani a uprava")
    rc, out = spust(SK + ["--apply"])
    over("B1 stejny prikaz podruhe: beze zmeny, nic se neduplikuje, zadna chyba", rc == 0 and pocty()[:3] == (1, 0, 1) and "beze změny" in out, (rc, out, pocty()))
    rc, out = spust(["--slug", "packstations-sk", "--accent", "#2dd4bf", "--apply"])
    sh = jedno("SELECT * FROM miniweb_shops")
    over("B2 uprava jen zadaneho pole: barva se zmeni, vsechno ostatni (mena, locale, zeme, kontakt) zustane", rc == 0 and sh["accent"] == "#2dd4bf" and sh["currency"] == "EUR" and sh["locale"] == "sk-SK" and sh["countries"] == "SK,CZ,AT"
         and json.loads(sh["contact_json"]) == {"phone": "+421 2 5555 0100", "hours": "Po-Pi 9:00-17:00"}, (rc, out, sh))
    rc, out = spust(["--slug", "packstations-sk", "--phone", "+421 900 111 222", "--apply"])
    over("B3 uprava telefonu zachova dobu (kontakt se slucuje po polich)", rc == 0 and json.loads(jedno("SELECT contact_json FROM miniweb_shops")["contact_json"]) == {"phone": "+421 900 111 222", "hours": "Po-Pi 9:00-17:00"}, out)
    sql("UPDATE miniweb_shops SET contact_json=%s", (json.dumps({"email": "info@neco.example", "phone": "1", "hours": "x"}),))
    rc, out = spust(["--slug", "packstations-sk", "--hours", "Po-Pi 8:00-16:00", "--apply"])
    over("B4 e-mail se v kontaktu NIKDY nenechava (API zadny e-mail nevydava): po uprave kontaktu je v JSON jen telefon a doba", rc == 0 and json.loads(jedno("SELECT contact_json FROM miniweb_shops")["contact_json"]) == {"phone": "1", "hours": "Po-Pi 8:00-16:00"}, out)
    rc, out = spust(["--slug", "packstations-sk", "--contact-from-company", "on", "--apply"])
    k_on = json.loads(jedno("SELECT contact_json FROM miniweb_shops")["contact_json"])
    rc2, out2 = spust(["--slug", "packstations-sk", "--contact-from-company", "off", "--apply"])
    k_off = json.loads(jedno("SELECT contact_json FROM miniweb_shops")["contact_json"])
    over("B4b --contact-from-company on prida do kontaktu priznak use_company (telefon a doba zustanou), off ho odebere; jmeno, adresu ani telefon spolecnosti skript do databaze nekopiruje (cte je API ze zdroje na serveru)",
         rc == 0 and k_on == {"phone": "1", "hours": "Po-Pi 8:00-16:00", "use_company": True} and rc2 == 0 and k_off == {"phone": "1", "hours": "Po-Pi 8:00-16:00"}, (k_on, k_off))
    rc, out = spust(["--slug", "packstations-sk", "--inquiry", "off", "--price-mode", "indicative", "--apply"])
    sh = jedno("SELECT * FROM miniweb_shops")
    over("B5 poptavku a rezim ceny lze prepnout (inquiry off, indicative)", rc == 0 and sh["inquiry_enabled"] == 0 and sh["price_mode"] == "indicative", (rc, out, sh))
    sql("UPDATE car_storefronts SET status='live', origin_cert_group='jina-skupina' WHERE slug='packstations-sk'")
    rc, out = spust(SK + ["--apply"])
    over("B6 skript uz existujici storefront NEMENI: stav live a certifikacni skupina zustanou (do live ho nikdy neprepina a nikdy ho neprepisuje)",
         rc == 0 and jedno("SELECT status, origin_cert_group FROM car_storefronts WHERE slug='packstations-sk'") == {"status": "live", "origin_cert_group": "jina-skupina"}, (rc, out))
    rc, out = spust(["--slug", "packstations-en", "--host", "packstations.top", "--lang", "en", "--family", "packstations", "--apply"])
    en = jedno("SELECT * FROM car_storefronts WHERE slug='packstations-en'")
    over("B7 druhy jazyk stejne rodiny = dalsi storefront na jine domene (bez zasahu do kodu); nazev bez --name = slug; mena zatim NULL (nerozhodnuto)",
         rc == 0 and en["primary_domain"] == "packstations.top" and en["lang"] == "en" and en["status"] == "draft" and en["origin_cert_group"] == "miniweb" and en["name"] == "packstations-en"
         and jedno("SELECT family, currency FROM miniweb_shops WHERE storefront_id=%s", (en["id"],)) == {"family": "packstations", "currency": None}, (rc, out, en))

    # ============================================================================================================ C) chyby
    print("== C chyby (nic se nezapise)")
    pred = pocty()
    stav = sql("SELECT * FROM car_storefronts ORDER BY id"), sql("SELECT * FROM miniweb_shops ORDER BY storefront_id")

    def chyba(popis, argv, ocekavany_text):
        rc, out = spust(argv + ["--apply"])
        return rc == 2 and ocekavany_text in out and pocty() == pred and (sql("SELECT * FROM car_storefronts ORDER BY id"), sql("SELECT * FROM miniweb_shops ORDER BY storefront_id")) == stav

    nove = ["--host", "novy-shop.top", "--lang", "de", "--family", "packstations"]
    pripady = {
        "slug s velkymi pismeny": (["--slug", "Novy_Shop"] + nove, "slug:"),
        "host s protokolem a cestou": (["--slug", "novy-shop"] + ["--host", "https://novy-shop.top/x", "--lang", "de", "--family", "packstations"], "host:"),
        "jazyk s velkymi pismeny": (["--slug", "novy-shop", "--host", "novy-shop.top", "--lang", "DE_x", "--family", "packstations"], "lang:"),
        "mena": (["--slug", "novy-shop"] + nove + ["--currency", "eur"], "currency:"),
        "zeme": (["--slug", "novy-shop"] + nove + ["--countries", "SK,XYZ"], "countries:"),
        "barva": (["--slug", "novy-shop"] + nove + ["--accent", "modra"], "accent:"),
        "locale": (["--slug", "novy-shop"] + nove + ["--locale", "sk SK!"], "locale:"),
        "znacka v nazvu": (["--slug", "novy-shop"] + nove + ["--name", "Stoly Logiman"], "name: obsahuje značku"),
        "znacka v domene": (["--slug", "novy-shop", "--host", "logiman-stoly.top", "--lang", "de", "--family", "packstations"], "host: obsahuje značku"),
        "e-mail v telefonu": (["--slug", "novy-shop"] + nove + ["--phone", "info@neco.example"], "phone:"),
        "html v dobe": (["--slug", "novy-shop"] + nove + ["--hours", "<b>Po</b>"], "hours:"),
        "novy storefront bez hosta a jazyka": (["--slug", "novy-shop", "--family", "packstations"], "--host a --lang"),
        "novy shop bez rodiny": (["--slug", "novy-shop", "--host", "novy-shop.top", "--lang", "de"], "--family je povinná"),
        "host uz pouziva jiny storefront": (["--slug", "novy-shop", "--host", "baliace-stoly.top", "--lang", "de", "--family", "packstations"], "už používá jiný storefront"),
        "existujici storefront s jinou domenou": (["--slug", "packstations-sk", "--host", "jina-domena.top"], "má doménu baliace-stoly.top"),
        "existujici storefront s jinym jazykem": (["--slug", "packstations-sk", "--lang", "de"], "má jazyk sk"),
        "neznama volba": (["--slug", "novy-shop", "--status", "live"], ""),
    }
    sql("INSERT INTO storefront_hosts (storefront_id, host) VALUES (%s,%s)", (jedno("SELECT id FROM car_storefronts WHERE slug='packstations-en'")["id"], "alias-en.top"))
    pripady["host uz je alias jineho storefrontu"] = (["--slug", "novy-shop", "--host", "alias-en.top", "--lang", "de", "--family", "packstations"], "už používá jiný storefront")
    pred = pocty()
    nesedi = []
    for popis, (argv, text) in pripady.items():
        if popis == "neznama volba":
            rc, out = spust(argv)
            if not (rc == 2 and pocty() == pred):
                nesedi.append(popis)
        elif not chyba(popis, argv, text):
            nesedi.append(popis)
    over("C1 chybne vstupy koncí kodem 2 a NIC se nezapise (ani storefront ani radek): " + ", ".join(pripady), not nesedi, nesedi)
    over("C2 zadna volba status (skript nikdy neprepina do live) a e-mail se do kontaktu neukladat neda", "--status" not in open(SKRIPT, encoding="utf-8").read().split("def main")[1].split("ap.parse_args")[0]
         and '"email"' not in open(SKRIPT, encoding="utf-8").read().split("def _pole")[1].split("def main")[0], None)

    # ============================================================================================================ G) spusteni a vypnuti
    print("== G spusteni a vypnuti")
    sql("DELETE FROM car_storefronts WHERE slug='packstations-en'")
    sql("DELETE FROM miniweb_shops WHERE storefront_id NOT IN (SELECT id FROM car_storefronts)")
    sql("UPDATE car_storefronts SET status='draft' WHERE slug='packstations-sk'")
    sql("UPDATE miniweb_shops SET inquiry_enabled=0, countries=NULL")
    rc, out = spust(["--slug", "packstations-sk", "--go-live", "--apply"])
    over("G1 spusteni bez podminek: NESPUSTENO (exit 2), vypise nesplnene podminky (nginx vhost domeny, zeme, poptavky, verejny katalog, informace o ochrane osobnich udaju); identifikace prodejce je ANO; storefront zustane draft",
         rc == 2 and "NESPUŠTĚNO" in out and out.count("  NE    ") == 5 and out.count("  ANO   ") == 1 and "nginx vhost" in out and "země dodání" in out and "přijímá poptávky" in out and "veřejná kategorie a produkt" in out
         and "identifikace prodejce" in out.split("  ANO   ")[1] and "ochrana osobních údajů" in out and "obchodní podmínky" not in out and jedno("SELECT status FROM car_storefronts WHERE slug='packstations-sk'")["status"] == "draft", (rc, out))
    open(os.path.join(NGX_TMP, "miniweb-baliace-stoly.top"), "w").close()                               # vhost je nainstalovany
    sql("UPDATE miniweb_shops SET inquiry_enabled=1, countries='SK'")
    cid = sql("INSERT INTO miniweb_categories (family, slug, sort_order) VALUES ('packstations','tables',1)") and jedno("SELECT id FROM miniweb_categories WHERE slug='tables'")["id"]
    sql("INSERT INTO miniweb_category_texts (miniweb_category_id, lang, name, status) VALUES (%s,'sk','Stoly','draft')", (cid,))
    sql("INSERT INTO miniweb_products (category_id, slug, public_sku) VALUES (%s,'baliaci-stol','PWB-001')", (cid,))
    pid = jedno("SELECT id FROM miniweb_products WHERE slug='baliaci-stol'")["id"]
    sql("INSERT INTO miniweb_product_texts (miniweb_product_id, lang, name, status) VALUES (%s,'sk','Baliaci stôl','draft')", (pid,))
    rc, out = spust(["--slug", "packstations-sk", "--go-live"])
    over("G2 schvalovani se nepocita jako hotove, dokud text neni SCHVALENY: draft kategorie a produktu = verejny katalog chybi; vhost, zeme, poptavky a identifikace prodejce jsou v poradku (4 ANO), zbyva katalog a privacy",
         rc == 2 and out.count("  ANO   ") == 4 and out.count("  NE    ") == 2, (rc, out))
    sql("UPDATE miniweb_category_texts SET status='approved'")
    sql("UPDATE miniweb_product_texts SET status='approved'")
    for kind, tel in (("terms", "Podmienky objednávky."), ("privacy", "Údaje spracúvame na vybavenie dopytu."), ("returns", "Tovar [DOPLNIŤ: lehota] dní.")):
        sql("INSERT INTO miniweb_documents (family, kind, lang, title, body, status, approved_at) VALUES ('packstations',%s,'sk',%s,%s,'draft',NULL)", (kind, kind.upper(), tel))
    rc, out = spust(["--slug", "packstations-sk", "--go-live"])
    over("G3 schvaleny katalog, ale privacy jen jako draft: stale NESPUSTENO (chybi jedine ochrana osobnich udaju), katalog uz je ANO; obchodni podminky ani vraceni se nevyzaduji",
         rc == 2 and out.count("  NE    ") == 1 and "ochrana osobních údajů" in out.split("  NE    ")[1] and out.count("  ANO   ") == 5, (rc, out))
    sql("UPDATE miniweb_documents SET body='Údaje [DOPLNIŤ: doba uchovania] spracúvame na vybavenie dopytu.', status='approved', approved_at=NOW() WHERE kind='privacy'")
    sql("UPDATE miniweb_documents SET status='approved', approved_at=NOW() WHERE kind='terms'")
    rc, out = spust(["--slug", "packstations-sk", "--go-live"])
    over("G4 dokument se zastupnou znackou se nepocita ani kdyz je oznaceny jako schvaleny (verejne API ho nevyda): privacy chybi, NESPUSTENO", rc == 2 and out.count("  NE    ") == 1 and "ochrana osobních údajů" in out.split("  NE    ")[1], (rc, out))
    sql("UPDATE miniweb_documents SET body='Údaje spracúvame na vybavenie dopytu.' WHERE kind='privacy'")
    rc, out = spust(["--slug", "packstations-sk", "--go-live"])
    over("G5 staci identifikace prodejce a schvalena ochrana osobnich udaju (podminky jsou schvalene, vraceni jen draft se zastupnou znackou a spusteni nezdrzuje): NAHLED (bez --apply) nic nezmeni a pripomene DNS domeny", rc == 0 and out.count("  NE    ") == 0 and out.count("  ANO   ") == 6 and "NÁHLED" in out and "DNS domény" in out
         and "returns" not in out and jedno("SELECT status FROM car_storefronts WHERE slug='packstations-sk'")["status"] == "draft", (rc, out))
    rc5, out5 = spust(["--slug", "packstations-sk", "--go-live", "--require-docs", "terms,privacy,returns"])
    rc5b, out5b = spust(["--slug", "packstations-sk", "--go-live", "--require-docs", "terms,nesmysl"])
    rc5c, out5c = spust(["--slug", "packstations-sk", "--go-live", "--require-docs", "terms,privacy"])
    over("G5b dalsi dokumenty jdou volitelne vyzadat (--require-docs): terms, privacy a returns = NESPUSTENO (returns ma zastupnou znacku), jen terms a privacy = lze; neznamy druh dokumentu = chyba bez zmeny",
         rc5 == 2 and out5.count("  NE    ") == 1 and "reklamace a záruka" in out5.split("  NE    ")[1] and rc5b == 2 and "--require-docs" in out5b and rc5c == 0 and out5c.count("  NE    ") == 0, (rc5, out5, rc5b, out5b, rc5c))
    rc, out = spust(["--slug", "packstations-sk", "--go-live", "--apply"])
    over("G6 --go-live --apply: storefront je live, hlaska SPUSTENO; druhe spusteni = beze zmeny (exit 0)", rc == 0 and "SPUŠTĚNO" in out and jedno("SELECT status FROM car_storefronts WHERE slug='packstations-sk'")["status"] == "live"
         and spust(["--slug", "packstations-sk", "--go-live", "--apply"]) == (0, "== beze změny: packstations-sk je už ve stavu live\n"), (rc, out))
    rc, out = spust(["--slug", "packstations-sk", "--take-offline"])
    over("G7 --take-offline bez --apply je nahled (zustane live); s --apply vrati do konceptu BEZ podminek; druhe vypnuti = beze zmeny",
         rc == 0 and "NÁHLED" in out and jedno("SELECT status FROM car_storefronts WHERE slug='packstations-sk'")["status"] == "live"
         and spust(["--slug", "packstations-sk", "--take-offline", "--apply"])[0] == 0 and jedno("SELECT status FROM car_storefronts WHERE slug='packstations-sk'")["status"] == "draft"
         and spust(["--slug", "packstations-sk", "--take-offline", "--apply"]) == (0, "== beze změny: packstations-sk je už ve stavu draft\n"), (rc, out))
    sql("UPDATE miniweb_shops SET countries='SK'")
    spust(["--slug", "packstations-sk", "--contact-from-company", "on", "--apply"])
    puvodni_fn = firma_mod._get_company_info
    firma_mod._get_company_info = lambda cur: {**puvodni_fn(cur), "phone": ""}
    try:
        rc9, out9 = spust(["--slug", "packstations-sk", "--go-live", "--apply"])
    finally:
        firma_mod._get_company_info = puvodni_fn
    rc9b, out9b = spust(["--slug", "packstations-sk", "--go-live"])
    over("G9 kontakt z nastaveni spolecnosti: kdyz v nastaveni chybi telefon, shop se NESPUSTI (podminka 'telefon spolecnosti je vyplneny' je NE); s telefonem je podminka ANO a spusteni nahled projde",
         rc9 == 2 and "telefon společnosti" in out9 and out9.count("  NE    ") == 1 and rc9b == 0 and "  ANO   telefon společnosti" in out9b and out9b.count("  NE    ") == 0, (rc9, out9, out9b))
    spust(["--slug", "packstations-sk", "--contact-from-company", "off", "--apply"])
    sql("UPDATE miniweb_shops SET countries=NULL")
    rc1, out1 = spust(["--slug", "packstations-sk", "--go-live", "--take-offline", "--apply"])
    rc2, out2 = spust(["--slug", "neexistuje", "--go-live", "--apply"])
    sql("UPDATE miniweb_shops SET countries=NULL")
    rc3, out3 = spust(["--slug", "packstations-sk", "--go-live", "--apply"])
    over("G8 chyby: --go-live spolu s --take-offline (exit 2), neexistujici shop (exit 2), shop bez zemi dodani se nespusti; nic se nezapise", rc1 == 2 and rc2 == 2 and "neexistuje" in out2 and rc3 == 2 and out3.count("  NE    ") == 1 and "země dodání" in out3
         and jedno("SELECT status FROM car_storefronts WHERE slug='packstations-sk'")["status"] == "draft", (rc1, rc2, rc3, out3))
    sql("UPDATE miniweb_shops SET countries='SK'")

    # ============================================================================================================ D) mutace
    print("== D mutace klicovych ochran")
    zdroj = open(SKRIPT, encoding="utf-8").read()

    def mutant(stare, nove):
        assert zdroj.count(stare) == 1, f"'{stare[:50]}' nalezeno {zdroj.count(stare)}x"
        return nacti(zdroj.replace(stare, nove))

    pred = pocty()
    rc, out = spust(["--slug", "znacka-test", "--host", "znacka-test.top", "--lang", "de", "--family", "packstations", "--name", "Stoly Logiman", "--apply"], mutant("if hodnota and dealers._brand_hit(hodnota):", "if False:"))
    zapsano_m1 = pocty() != pred
    sql("DELETE FROM miniweb_shops WHERE storefront_id IN (SELECT id FROM car_storefronts WHERE slug='znacka-test')")
    sql("DELETE FROM car_storefronts WHERE slug='znacka-test'")
    over("M1 mutace: bez kontroly znacky by se zalozil shop se znackou v nazvu (spravne chyba) - test C1 ji zachyti", rc == 0 and zapsano_m1, (rc, out))
    pred = pocty()
    rc, out = spust(["--slug", "nahled-test", "--host", "nahled-test.top", "--lang", "de", "--family", "packstations"], mutant('if not args.apply:\n            conn.rollback()\n            print("== NÁHLED (nic se nezapsalo)")', 'if False:\n            conn.rollback()\n            print("== NÁHLED (nic se nezapsalo)")'))
    zapsano_m2 = pocty() != pred
    sql("DELETE FROM miniweb_shops WHERE storefront_id IN (SELECT id FROM car_storefronts WHERE slug='nahled-test')")
    sql("DELETE FROM car_storefronts WHERE slug='nahled-test'")
    over("M2 mutace: kdyby se nahled bral jako zapis, shop by vznikl i bez --apply (spravne ne) - test A1 ji zachyti", zapsano_m2, (rc, out))
    pred = pocty()
    rc, out = spust(["--slug", "live-test", "--host", "live-test.top", "--lang", "de", "--family", "packstations", "--apply"], mutant("'draft',%s)\"", "'live',%s)\""))
    over("M3 mutace: kdyby se storefront zakladal jako live, shop by byl hned verejny (spravne draft) - test A2 ji zachyti", jedno("SELECT status FROM car_storefronts WHERE slug='live-test'") == {"status": "live"}, (rc, out))
    sql("DELETE FROM miniweb_documents")
    rc, out = spust(["--slug", "packstations-sk", "--go-live", "--apply"], mutant("if not all(ok for ok, _ in podminky):", "if False:"))
    over("M4 mutace: kdyby se spusteni nezastavilo pri nesplnenych podminkach, shop bez schvalene ochrany osobnich udaju by sel do provozu (spravne NESPUSTENO) - test G1/G3 ji zachyti", jedno("SELECT status FROM car_storefronts WHERE slug='packstations-sk'")["status"] == "live", (rc, out))
    sql("UPDATE car_storefronts SET status='draft' WHERE slug='packstations-sk'")
finally:
    with real.cursor() as cur:
        for t in TABULKY:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (storefronty, aliasy, mini-shopy) jsou po testu beze zmeny", po == PRED, (PRED, po))
ok = sum(vysl)
print(f"\nVYSLEDEK scripts/miniweb_shop.py: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
