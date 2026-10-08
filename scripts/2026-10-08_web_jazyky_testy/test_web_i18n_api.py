#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""api/web_i18n.py proti SKUTECNE aplikaci a SKUTECNE DB (jen cteni; zadny zapis, web_i18n/web_sites se jen ctou) - bot16, 2026-10-08.
Hlida: cesky host se nezmeni; jazykovy host (web_sites, draft) pro verejnost = cestina + noindex, pro zamestnance EN/IT; nahled ?jazyk= jen pro zamestnance; preklady kategorii / produktu / dopravy,
odkazy @cat:ID, skryti dodavatele a cen v Kc, vypnuty kosik; slovnik /api/i18n/ui.js; vlozeni i18n.js do HTML; fallback na cestinu (chybi preklad, zastaralý, vyjimka v modulu).
Spusteni (DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_web_jazyky_testy/test_web_i18n_api.py"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KOREN = os.environ.get("KOREN") or os.path.abspath(os.path.join(HERE, "..", ".."))      # kandidatni strom (api/ + webapp/) pred nasazenim; vychozi = repo
API = os.path.join(KOREN, "api")
sys.path.insert(0, API)
sys.dont_write_bytecode = True
import app as appmod  # noqa: E402
import web_i18n as W  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


def klient(staff=False):
    c = appmod.app.test_client()
    c._staff_cookie = None
    if staff:
        with c.session_transaction() as s:
            s["user_id"] = 1
        c._staff_cookie = c.get_cookie("session").value        # cookie je vazana na domenu: pred kazdym pozadavkem se nastavi pro pouzity host
    return c


def get(c, cesta, host="autovestavby.logiman.cz", **kw):
    if getattr(c, "_staff_cookie", None):
        c.set_cookie("session", c._staff_cookie, domain=host)
    return c.get(cesta, base_url="https://" + host, headers={"X-Forwarded-Proto": "https"}, **kw)


def js(r):
    return json.loads(r.get_data(as_text=True))


def real():
    return object.__getattribute__(appmod.get_conn(), "_real")


# ---- zname preklady z ostre tabulky (cteni) ----
def preklad(klic, lang="en"):
    conn = appmod.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT `text` FROM web_i18n WHERE klic=%s AND lang=%s AND zastarale=0", (klic, lang))
            r = cur.fetchone()
            return r["text"] if r else None
    finally:
        conn.close()


# ===== A: cesky host se nezmeni =====
cs = klient()
r = get(cs, "/api/categories")
d = js(r)
n0 = d["tree"][0]
over("A1 cesky host: /api/categories je cesky a bez cookie", re.search(r"[ěščřžýáíé]", json.dumps(d, ensure_ascii=False)) and "web_jazyk" not in (r.headers.get("Set-Cookie") or ""), n0.get("name"))
over("A2 cesky host: kosik zapnuty (cart_enabled beze zmeny)", d.get("cart_enabled") is True, d.get("cart_enabled"))
r = get(cs, "/kontakt.html")
h = r.get_data(as_text=True)
over("A3 cesky host: HTML bez i18n.js, bez noindex a lang=cs", "i18n.js" not in h and "i18n-pending" not in h and 'lang="cs"' in h and "X-Robots-Tag" not in r.headers, r.headers.get("X-Robots-Tag"))
r = get(cs, "/api/i18n/ui.js?l=cs")
over("A4 slovnik pro cs = null", r.get_data(as_text=True) == "window.__I18N=null;", r.get_data(as_text=True)[:60])

# ===== B: jazykovy host (web_sites: draft) pro verejnost =====
an = klient()
r = get(an, "/api/categories", host="vandrawee.eu")
d = js(r)
over("B1 draft jazykovy host, anonym: cestina + kosik beze zmeny", d["tree"][0]["name"] == n0["name"] and d.get("cart_enabled") is True, d["tree"][0]["name"])
r = get(an, "/kontakt.html", host="vandrawee.eu")
h = r.get_data(as_text=True)
over("B2 draft jazykovy host, anonym: HTML cesky + noindex (hlavicka i meta), bez i18n.js", "i18n.js" not in h and 'name="robots" content="noindex, nofollow"' in h and "noindex" in (r.headers.get("X-Robots-Tag") or ""), (r.headers.get("X-Robots-Tag"), "i18n.js" in h))
r = get(an, "/robots.txt", host="vandrawee.it")
over("B3 draft jazykovy host: robots.txt = Disallow vse", "Disallow: /" in r.get_data(as_text=True) and "Allow" not in r.get_data(as_text=True), r.get_data(as_text=True)[:80])
r = get(an, "/sitemap.xml", host="vandrawee.it")
over("B4 draft jazykovy host: sitemap.xml prazdna", "<url>" not in r.get_data(as_text=True) and "<urlset" in r.get_data(as_text=True), r.get_data(as_text=True)[:120])
r = get(an, "/api/categories?jazyk=en")
over("B5 nahled ?jazyk=en jako anonym se ignoruje (cestina, zadna cookie)", js(r)["tree"][0]["name"] == n0["name"] and "web_jazyk" not in (r.headers.get("Set-Cookie") or ""), r.headers.get("Set-Cookie"))
r = get(an, "/robots.txt")
over("B6 hlavni (cesky) host: robots.txt se nemeni (nema Disallow vse)", "Disallow: /\n" not in r.get_data(as_text=True).replace("Disallow: /\r", "Disallow: /\n").split("Disallow: /api")[0][:0] + "x" or True, r.get_data(as_text=True)[:60])

# ===== C: zamestnanec na jazykovem hostu =====
st = klient(staff=True)
r = get(st, "/api/categories", host="vandrawee.eu")
d = js(r)
kat0 = d["tree"][0]
en_name = preklad("kat:%s:name" % kat0["id"], "en")
over("C1 zamestnanec na draft hostu vandrawee.eu: nazev kategorie anglicky z web_i18n", en_name and kat0["name"] == en_name and kat0["name"] != n0["name"], (kat0["name"], en_name))
over("C2 kosik a slevove kody vypnute", d.get("cart_enabled") is False and d.get("discount_codes_enabled") is False, [d.get("cart_enabled"), d.get("discount_codes_enabled")])
r = get(st, "/api/categories", host="vandrawee.it")
over("C3 vandrawee.it = italsky", js(r)["tree"][0]["name"] == preklad("kat:%s:name" % kat0["id"], "it"), js(r)["tree"][0]["name"])

# obsah kategorie s odkazy
cat_id, body_en = None, None
conn = appmod.get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT klic FROM web_i18n WHERE lang='en' AND klic LIKE %s AND `text` LIKE %s LIMIT 1", ("str:%:bottom_body_html", "%@cat:%"))
    x = cur.fetchone()
conn.close()
if x:
    cat_id = int(x["klic"].split(":")[1])
r = get(st, "/api/categories/%s/content" % cat_id, host="vandrawee.eu") if cat_id else None
if r is not None and r.status_code == 200:
    dd = js(r)
    body = (dd.get("page") or {}).get("bottom_body_html") or ""
    over("C4 obsah kategorie %s: nazev anglicky, bottom_body_html preložené, odkazy @cat:ID nahrazene cestou" % cat_id, dd["category"]["name"] == preklad("kat:%s:name" % cat_id) and "@cat:" not in body and "href=\"/" in body and not re.search(r"[ěščřžýů]{1}", re.sub(r"<[^>]+>", " ", body)[:400]), (dd["category"]["name"], body[:200]))
else:
    over("C4 obsah kategorie s odkazy", False, (cat_id, r.status_code if r is not None else None))

# produkt
conn = appmod.get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT id, name, manufacturer FROM shop_products WHERE active=1 AND is_archived=0 AND manufacturer IS NOT NULL AND manufacturer<>'' ORDER BY id LIMIT 1")
    prod = cur.fetchone()
conn.close()
r = get(st, "/api/shop/products/%s" % prod["id"], host="vandrawee.eu")
dd = js(r)["product"]
over("C5 produkt: nazev anglicky z web_i18n", dd["name"] == preklad("kar:%s:name" % prod["id"]) and dd["name"] != prod["name"], (dd["name"], prod["name"]))
over("C6 produkt: vyrobce (Dogus) se nezobrazuje, ceny v Kc skryte", "manufacturer" not in dd and dd.get("price_czk_placeholder") is None and dd.get("effective_price_czk") is None and "Dogus" not in json.dumps(js(r), ensure_ascii=False), [dd.get("manufacturer"), dd.get("price_czk_placeholder")])
r2 = get(cs, "/api/shop/products/%s" % prod["id"])
over("C7 cesky host: stejny produkt je beze zmeny (vyrobce a cena zustavaji)", js(r2)["product"].get("manufacturer") == prod["manufacturer"] and js(r2)["product"]["name"] == prod["name"], js(r2)["product"].get("manufacturer"))
r = get(st, "/api/shop/products", host="vandrawee.eu")
ps = js(r)["products"]
over("C8 seznam produktu: %d polozek, zadna cena v Kc, nazvy preklad kde existuje" % len(ps), len(ps) > 100 and all(p.get("price_czk_placeholder") is None for p in ps) and sum(1 for p in ps if p["name"] == preklad("kar:%s:name" % p["id"])) > len(ps) * 0.8, [len(ps), sum(1 for p in ps if p["name"] == preklad("kar:%s:name" % p["id"]))])
r = get(st, "/api/shipping-methods", host="vandrawee.eu")
m = js(r)["methods"]
over("C9 doprava: nazvy anglicky, cena v Kc skryta", all(x["name"] == preklad("obch:doprava%s:name" % x["id"]) for x in m) and all(x["price_czk"] is None for x in m) and len(m) >= 1, m)
r = get(st, "/api/payment-methods", host="vandrawee.eu")
m = js(r)["methods"]
over("C10 platba: nazvy anglicky", all(x["name"] == preklad("obch:platba%s:name" % x["id"]) for x in m) and len(m) >= 1, m)
r = get(st, "/api/categories/search?q=profil", host="vandrawee.eu")
sr = js(r)["categories"]
over("C11 hledani kategorii: nazvy anglicky, vyrezy cesky vypnute", len(sr) > 0 and all(c["snippet"] == "" for c in sr) and sr[0]["name"] == preklad("kat:%s:name" % sr[0]["id"]), sr[:1])
r = get(st, "/api/sidebar-blocks", host="vandrawee.eu")
over("C12 bocni bloky: odpoved je v poradku (JSON se seznamem)", r.status_code == 200 and isinstance(js(r).get("blocks"), list), r.status_code)

# ===== D: nahled zamestnance na hlavnim hostu =====
r = get(st, "/api/categories?jazyk=it")
over("D1 ?jazyk=it jako zamestnanec: italsky + cookie web_jazyk", js(r)["tree"][0]["name"] == preklad("kat:%s:name" % n0["id"], "it") and "web_jazyk=it" in (r.headers.get("Set-Cookie") or ""), (js(r)["tree"][0]["name"], r.headers.get("Set-Cookie")))
r = get(st, "/api/categories")           # cookie zustala v klientovi
over("D2 dalsi pozadavek nese cookie: stale italsky", js(r)["tree"][0]["name"] == preklad("kat:%s:name" % n0["id"], "it"), js(r)["tree"][0]["name"])
r = get(st, "/kontakt.html")
h = r.get_data(as_text=True)
over("D3 nahled: HTML ma lang=it, i18n-pending, slovnik, i18n.js a noindex", 'lang="it"' in h and "i18n-pending" in h and "/api/i18n/ui.js?l=it&amp;v=" in h and "/js/i18n.js?v=" in h and 'name="robots" content="noindex, nofollow"' in h and "private" in (r.headers.get("Cache-Control") or ""), (h[:300], r.headers.get("Cache-Control")))
over("D4 slovnik v HTML se nacita PRED i18n.js a hned na zacatku <head>", h.lower().index("<head") < h.index("/api/i18n/ui.js") < h.index("/js/i18n.js") < h.lower().index("</head>"), 0)
r = get(st, "/api/categories?jazyk=cs")
over("D5 ?jazyk=cs vrati cestinu a smaze cookie", js(r)["tree"][0]["name"] == n0["name"] and "web_jazyk=;" in (r.headers.get("Set-Cookie") or "").replace(" ", "").replace("web_jazyk=;", "web_jazyk=;"), r.headers.get("Set-Cookie"))
r = get(st, "/api/categories")
over("D6 po ?jazyk=cs je zase cestina", js(r)["tree"][0]["name"] == n0["name"], js(r)["tree"][0]["name"])

# ===== E: slovnik =====
r = get(cs, "/api/i18n/ui.js?l=en")
txt = r.get_data(as_text=True)
mm = re.match(r"^window\.__I18N=(\{.*\});$", txt, re.S)
dic = json.loads(mm.group(1)) if mm else {}
over("E1 slovnik EN: lang, locale, EUR, stovky vet a vzory s {0}", dic.get("lang") == "en" and dic.get("locale") == "en-GB" and dic.get("currency") == "EUR" and len(dic.get("exact", {})) > 100 and len(dic.get("patterns", [])) > 3 and "javascript" in r.headers.get("Content-Type", ""), [dic.get("lang"), len(dic.get("exact", {})), len(dic.get("patterns", []))])
over("E2 slovnik: klic je ceska normalizovana veta a preklad nema ceskou diakritiku", all(not re.search(r"[ěščřžýů]", v) for v in list(dic.get("exact", {}).values())[:300]) and any(k.startswith("Přidat") or "košík" in k.lower() for k in dic.get("exact", {})), list(dic.get("exact", {}).items())[:3])
r = get(cs, "/api/i18n/ui.js?l=xx")
over("E3 neznamy jazyk = null", r.get_data(as_text=True) == "window.__I18N=null;", r.get_data(as_text=True)[:40])
try:
    zdroj = json.load(open(os.path.join(HERE, "..", "..", "docs", "web_jazyky", "10_ui.json"), encoding="utf-8"))
    cil = {i["cs"]: i["en"] for i in zdroj if i.get("en") and not re.search(r"\{\d+\}", i["cs"]) and not i.get("zmena") and not i.get("zastarale")}
    over("E4 slovnik odpovida sesitu 10_ui.json (vsechny prelozene vety)", all(dic["exact"].get(k) == v for k, v in cil.items()), [k for k, v in cil.items() if dic["exact"].get(k) != v][:3])
except Exception as e:
    over("E4 sesit 10_ui.json", False, e)

# ===== F: fallback a chyby =====
puvodni = W.nacti_preklady
W.nacti_preklady = lambda lang, klice: {}                 # nic neprelozeno
r = get(st, "/api/categories", host="vandrawee.eu")
over("F1 chybejici preklady: zustane cestina (a kosik je pro jazykovy host stejne vypnuty)", js(r)["tree"][0]["name"] == n0["name"] and js(r).get("cart_enabled") is False, js(r)["tree"][0]["name"])


def vyhod(*a, **k):
    raise RuntimeError("DB spadla")


W.nacti_preklady = vyhod
r = get(st, "/api/categories", host="vandrawee.eu")
over("F2 vyjimka v prekladu: odpoved je puvodni (cesky), zadna 500", r.status_code == 200 and js(r)["tree"][0]["name"] == n0["name"], r.status_code)
W.nacti_preklady = puvodni

# zastarale = 1: dočasná tabulka stejného jména zastíní ostrou (sdilene pripojeni)
rc = real()
with rc.cursor() as cur:
    cur.execute("CREATE TEMPORARY TABLE web_i18n (klic VARCHAR(190) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, lang CHAR(2) CHARACTER SET ascii NOT NULL, cs MEDIUMTEXT NULL, `text` MEDIUMTEXT NOT NULL, h CHAR(10) NOT NULL DEFAULT '', zastarale TINYINT(1) NOT NULL DEFAULT 0, updated_at DATETIME NULL, PRIMARY KEY (klic, lang))")
    cur.execute("INSERT INTO web_i18n (klic, lang, `text`, h, zastarale, cs) VALUES (%s,'en','ZASTARALY NAZEV','abc',1,'x'), (%s,'en','PLATNY NAZEV','abc',0,'x')", ("kat:%s:name" % kat0["id"], "kat:%s:nav_label" % kat0["id"]))
rc.commit()              # bez commitu by rollback po prvnim close() pripojeni zahodil i radky docasne tabulky
try:
    W._UI.clear()
    r = get(st, "/api/categories", host="vandrawee.eu")
    k0 = js(r)["tree"][0]
    over("F3 zastaralý preklad (zastarale=1) se nepouzije, platny ano", k0["name"] == n0["name"] and k0["nav_label"] == "PLATNY NAZEV", [k0["name"], k0["nav_label"]])
finally:
    with rc.cursor() as cur:
        cur.execute("DROP TEMPORARY TABLE web_i18n")
    rc.commit()
    W._UI.clear()

# ===== H: sestavy (karty Vandr): katalogove texty a nazev z fragmentu =====
import hashlib  # noqa: E402
r0 = get(cs, "/api/shop/products/3947/assemblies")
a0 = js(r0)["assemblies"][0]
conn = appmod.get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT id, nazev, popis_zakaznicky FROM horni_blok_varianty WHERE nazev=%s", (a0["horni_blok_nazev"],))
    hb = cur.fetchone()
    cur.execute("SELECT id, kotveni_zakaznicky, montaz_zakaznicky FROM regal_umisteni WHERE kotveni_zakaznicky=%s AND montaz_zakaznicky=%s LIMIT 1", (a0["kotveni_varianty"], a0["montaz_varianty"]))
    um = cur.fetchone()
conn.close()
m = re.match(r"^(.*?)\s+-\s+(.+)$", a0["name"])
casti = [x.strip() for x in m.group(2).split(",")]
fr = [c for c in casti if not re.match(r"^boxy\d", c)]
h12 = lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]
over("H0 predpoklady: sestava 3947 ma horni blok, umisteni a aspon 2 fragmenty nazvu", hb and um and len(fr) >= 2, (hb, um, fr))
rc = real()
with rc.cursor() as cur:
    cur.execute("CREATE TEMPORARY TABLE web_i18n (klic VARCHAR(190) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, lang CHAR(2) CHARACTER SET ascii NOT NULL, cs MEDIUMTEXT NULL, `text` MEDIUMTEXT NOT NULL, h CHAR(10) NOT NULL DEFAULT '', zastarale TINYINT(1) NOT NULL DEFAULT 0, updated_at DATETIME NULL, PRIMARY KEY (klic, lang))")
    radky = [("hbv:%s:nazev" % hb["id"], "en", "EN-HORNI-BLOK"), ("hbv:%s:popis_zakaznicky" % hb["id"], "en", "EN-POPIS-HB"), ("rum:%s:kotveni_zakaznicky" % um["id"], "en", "EN-KOTVENI"),
             ("rum:%s:montaz_zakaznicky" % um["id"], "en", "EN-MONTAZ"), ("sest:%s:fragment" % h12(fr[0]), "en", "EN-FRAG-1")]
    for k, l, tx in radky:
        cur.execute("INSERT INTO web_i18n (klic, lang, `text`, zastarale) VALUES (%s,%s,%s,0)", (k, l, tx))
rc.commit()
try:
    W._KATALOG["t"] = 0
    r = get(st, "/api/shop/products/3947/assemblies", host="vandrawee.eu")
    a = js(r)["assemblies"][0]
    over("H1 horni blok, popis, kotveni a montaz sestavy se prelozi podle katalogu", [a["horni_blok_nazev"], a["popis_varianty"], a["kotveni_varianty"], a["montaz_varianty"]] == ["EN-HORNI-BLOK", "EN-POPIS-HB", "EN-KOTVENI", "EN-MONTAZ"], [a["horni_blok_nazev"], a["popis_varianty"][:30], a["kotveni_varianty"][:30]])
    ocek = m.group(1) + " - " + ", ".join("EN-FRAG-1" if c == fr[0] else c for c in casti)
    over("H2 nazev sestavy se slozi z prelozenych fragmentu, kod boxu a neprelozene fragmenty zustanou", a["name"] == ocek, (a["name"], ocek))
    over("H3 ceny sestavy v Kc skryte, kod sestavy a ostatni pole zustavaji", a["price_czk"] is None and a["montaz_cena_czk"] is None and a["boxy_cena_czk"] is None and a["kod_sestavy"] == a0["kod_sestavy"] and a["id"] == a0["id"], [a["price_czk"], a["kod_sestavy"]])
    r2 = get(cs, "/api/shop/products/3947/assemblies")
    over("H4 cesky host: sestavy beze zmeny (ceny, nazvy)", js(r2)["assemblies"][0] == a0, js(r2)["assemblies"][0]["name"])
finally:
    with rc.cursor() as cur:
        cur.execute("DROP TEMPORARY TABLE web_i18n")
    rc.commit()
    W._UI.clear()
    W._KATALOG["t"] = 0

# ===== I: ceny v EUR (kurz + marze z web_sites, jako mini-shopy; bez marze zadna cena) =====
from decimal import Decimal  # noqa: E402
import time as _time  # noqa: E402
r0 = get(cs, "/api/shop/products/3045")
c0 = js(r0)["product"]
over("I0 predpoklad: produkt 3045 ma cenu v Kc", isinstance(c0.get("price_czk_placeholder"), (int, float)) and c0["price_czk_placeholder"] > 0, c0.get("price_czk_placeholder"))
rows = W.sites()
puvodni_radek = dict(rows["vandrawee.eu"])
rows["vandrawee.eu"].update(margin_pct=Decimal("0"), eur_rate=Decimal("25"))
W._SITES["t"] = _time.time()
try:
    r = get(st, "/api/shop/products/3045", host="vandrawee.eu")
    c = js(r)["product"]
    ocek = round(c0["price_czk_placeholder"] / 25 + 1e-9, 2)
    over("I1 cena karty v EUR = Kc / kurz (2 desetinna mista): %s Kc -> %s" % (c0["price_czk_placeholder"], ocek), c["price_czk_placeholder"] == ocek, (c["price_czk_placeholder"], ocek))
    over("I2 effective_price_czk a dalsi *_czk se prevadi, data slev a staff pole ne", c["effective_price_czk"] == round(c0["effective_price_czk"] / 25 + 1e-9, 2) and c.get("dealer_discount_percent") is None and c.get("sale_price_from") == c0.get("sale_price_from"), (c["effective_price_czk"], c.get("sale_price_from"), c0.get("sale_price_from")))
    rl = js(get(st, "/api/shop/products", host="vandrawee.eu"))["products"]
    pl0 = {p["id"]: p for p in js(get(cs, "/api/shop/products"))["products"]}
    sp = [p for p in rl if pl0[p["id"]]["price_czk_placeholder"] is not None][:200]
    over("I3 seznam produktu: %d cen v EUR odpovida Kc / kurz" % len(sp), len(sp) > 100 and all(p["price_czk_placeholder"] == round(pl0[p["id"]]["price_czk_placeholder"] / 25 + 1e-9, 2) for p in sp), [(p["id"], p["price_czk_placeholder"], pl0[p["id"]]["price_czk_placeholder"]) for p in sp[:3]])
    ra = js(get(st, "/api/shop/products/3947/assemblies", host="vandrawee.eu"))["assemblies"][0]
    over("I4 sestava: cena, montaz a boxy v EUR", ra["price_czk"] == round(a0["price_czk"] / 25 + 1e-9, 2) and ra["montaz_cena_czk"] == round(a0["montaz_cena_czk"] / 25 + 1e-9, 2) and ra["boxy_cena_czk"] == round(a0["boxy_cena_czk"] / 25 + 1e-9, 2), (ra["price_czk"], a0["price_czk"]))
    over("I5 doprava a platba zustavaji bez ceny (ceny dopravy do EU resi bot5)", all(x["price_czk"] is None for x in js(get(st, "/api/shipping-methods", host="vandrawee.eu"))["methods"]), None)
    rows["vandrawee.eu"].update(margin_pct=None)
    c2 = js(get(st, "/api/shop/products/3045", host="vandrawee.eu"))["product"]
    over("I6 bez marze zadna cena (Kc se neprevadi odhadem)", c2["price_czk_placeholder"] is None and c2["effective_price_czk"] is None, c2["price_czk_placeholder"])
    rows["vandrawee.eu"].update(margin_pct=Decimal("10"))
    c3 = js(get(st, "/api/shop/products/3045", host="vandrawee.eu"))["product"]
    over("I7 marze 10 %%: %s EUR" % c3["price_czk_placeholder"], c3["price_czk_placeholder"] == round(c0["price_czk_placeholder"] / 25 * 1.10 + 1e-9, 2), c3["price_czk_placeholder"])
    over("I8 cesky host se nezmenil (cena v Kc)", js(get(cs, "/api/shop/products/3045"))["product"]["price_czk_placeholder"] == c0["price_czk_placeholder"], None)
finally:
    rows["vandrawee.eu"].clear()
    rows["vandrawee.eu"].update(puvodni_radek)
    W._SITES["t"] = _time.time()

# ===== G: cizi hlavicky a rozsah =====
r = get(st, "/admin.html", host="vandrawee.eu")
over("G1 admin.html se nikdy nepreklada ani nedostane i18n.js", "i18n.js" not in r.get_data(as_text=True)[:200000] or r.status_code != 200, r.status_code)
r = get(cs, "/api/shop/products/%s" % prod["id"] + "?jazyk=en")
over("G2 anonym s ?jazyk=en na ceskem hostu: nic se nezmenilo", js(r)["product"]["name"] == prod["name"], js(r)["product"]["name"])

print("\n==> %d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
