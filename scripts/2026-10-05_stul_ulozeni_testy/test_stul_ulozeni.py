#!/usr/bin/env python3
"""Test "Ulozit konfiguraci" (api/stul_ulozeni.py; bot16 2026-10-05) nad SKUTECNYM kodem (konfigurace_kosik.vyres, miniweb) a docasnymi tabulkami: stul_ulozene_konfigurace, crm_leads,
crm_lead_messages jsou na jednom spojeni TEMPORARY (kontrola pred kazdym dotazem), registry (ARES, RPO) a DNS (DoH, dig) jsou podstrcene - test NEVOLA zadnou externi sluzbu a NEODESILA
e-mail. Ostre tabulky se jen CTOU druhym spojenim a na konci se porovna jejich stav (zadny zivy lead / ulozena konfigurace nezustane).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
  api/venv/bin/python3 scripts/2026-10-05_stul_ulozeni_testy/test_stul_ulozeni.py"""
import json, os, re, sys, threading
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi"); sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "api"))
try:
    import pymysql
    import app as appmod
    import stul_shop
    import stul_ulozeni as U
finally:
    threading.Thread.start = _orig

bad = total = 0


def ok(cond, text):
    global bad, total
    total += 1
    bad += 0 if cond else 1
    print("[%s] %s" % ("OK   " if cond else "CHYBA", text))


TABULKY = ("stul_ulozene_konfigurace", "crm_leads", "crm_lead_messages")


def ostre():
    c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("crm_leads", "crm_lead_messages"):
                cur.execute(f"CHECKSUM TABLE `{t}`"); out[t] = list(cur.fetchone().values())[1]
            cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='stul_ulozene_konfigurace'"); out["tabulka_existuje"] = cur.fetchone()["n"]
            return out
    finally:
        c.close()


PRED = ostre()
wrap = appmod.get_conn(); real = object.__getattribute__(wrap, "_real")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        return cur.fetchall()


for t in ("crm_leads", "crm_lead_messages"):
    sql(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`"); sql(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
sql(U.DDL.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMPORARY TABLE", 1))
real.commit()


def docasne(bez=()):
    for t in [x for x in TABULKY if x not in bez]:
        r = sql(f"SHOW CREATE TABLE `{t}`")
        assert list(r[0].values())[1].startswith("CREATE TEMPORARY TABLE"), t + " neni docasna - STOP"


docasne()
client = appmod.app.test_client()
MAIN = "https://autovestavby.logiman.cz"
SKSHOP = "https://baliace-stoly.top"

# ---- podstrceni externich sluzeb
VOLANI = []
SCEN = {"ares": (200, {"obchodniJmeno": "LOGIMAN s.r.o.", "dic": "CZ28337638", "sidlo": {"textovaAdresa": "Praha"}}), "rpo": (200, {"results": [{"identifiers": [{"value": "35757442"}], "fullNames": [{"value": "VOLKSWAGEN SLOVAKIA, a.s.", "validFrom": "1999-10-15"}]}]}),
        "doh": {"MX": (200, {"Status": 0, "Answer": [{"type": 15, "data": "10 mx.example.cz."}]})}, "dig": "ok"}


def fake_http(url, timeout, headers=None):
    VOLANI.append(url)
    if "ares.gov.cz" in url:
        return SCEN["ares"]
    if "statistics.sk" in url:
        return SCEN["rpo"]
    if "cloudflare-dns.com" in url:
        typ = re.search(r"type=([A-Z]+)", url).group(1)
        return SCEN["doh"].get(typ, (200, {"Status": 0}))
    raise AssertionError("neocekavane volani site: " + url)


U._http_json = fake_http
U._mx_dig = lambda domain: SCEN["dig"]
U._rate_limited = lambda *a, **k: False                  # limity IP vypnute (zkousi se zvlast nize)
sch = stul_shop.schema("cs", 30)
SEL, RV = sch["default_selection"], sch["rules_version"]
VALID = {"product_id": 4934, "configuration": {"selection": SEL, "rules_version": RV}, "ico": "28337638", "email": "Test.Zakaznik@Example.CZ", "phone": "603 230 059", "consent": True}


def post(body, base=MAIN, path="/api/shop/configurator/ulozit", bez=()):
    docasne(bez)
    r = client.post(path, json=body, base_url=base)
    return r.status_code, (r.get_json(silent=True) or {})


def nove(**kw):
    b = json.loads(json.dumps(VALID)); b.update(kw); return b


def n_rows(t):
    return sql(f"SELECT COUNT(*) AS n FROM `{t}`")[0]["n"]


# ---- vstupy a pravidla
st, d = post(nove(website="http://spam"))
ok(st == 201 and d == {"status": "ok"} and n_rows("stul_ulozene_konfigurace") == 0 and n_rows("crm_leads") == 0, "U1 honeypot: tváří se, že uloženo, nic se neuloží")
st, d = post({"product_id": 4934, "ico": "28337638", "email": "a@b.cz", "phone": "603230059", "consent": True})
ok(st == 400 and d.get("error") == "configuration_required", "U2 bez konfigurace: 400 configuration_required")
st, d = post(nove(consent=False))
ok(st == 400 and d.get("error") == "consent_required", "U3 bez souhlasu: 400 consent_required")
st, d = post(nove(ico="123"))
ok(st == 400 and d.get("error") == "ico_invalid" and d.get("field") == "ico", "U4 krátké IČO: ico_invalid")
st, d = post(nove(ico="12345678"))
ok(st == 400 and d.get("error") == "ico_invalid" and not any("ares" in u for u in VOLANI), "U5 IČO se špatnou kontrolní číslicí: ico_invalid, ARES se ani nevolá")
SCEN["ares"] = (404, {"kod": "NENALEZENO"})
st, d = post(nove())
ok(st == 422 and d.get("error") == "ico_not_found", "U6 IČO s platnou číslicí, které ARES nezná: 422 ico_not_found")
SCEN["ares"] = (200, {"obchodniJmeno": "ZANIKLA s.r.o.", "datumZaniku": "2020-01-01"})
st, d = post(nove())
ok(st == 422 and d.get("error") == "ico_not_found", "U7 zaniklý subjekt: ico_not_found")
SCEN["ares"] = (None, None)
st, d = post(nove())
ok(st == 503 and d.get("error") == "registry_unavailable" and n_rows("stul_ulozene_konfigurace") == 0, "U8 ARES nedostupný: 503 registry_unavailable a nic se neuloží")
SCEN["ares"] = (200, {"obchodniJmeno": "LOGIMAN s.r.o.", "dic": "CZ28337638", "sidlo": {"textovaAdresa": "Praha"}})
for em in ("x", "a@b", "a..b@example.cz", "a b@example.cz", "<script>@example.cz"):
    st, d = post(nove(email=em))
    ok(st == 400 and d.get("error") == "email_invalid" and d.get("field") == "email", "U9 neplatný formát e-mailu „%s“: email_invalid" % em)
SCEN["doh"] = {"MX": (200, {"Status": 3})}
st, d = post(nove())
ok(st == 422 and d.get("error") == "email_domain", "U10 neexistující doména (NXDOMAIN): 422 email_domain")
SCEN["doh"] = {"MX": (200, {"Status": 0, "Answer": [{"type": 15, "data": "0 ."}]})}
st, d = post(nove())
ok(st == 422 and d.get("error") == "email_domain", "U11 doména s „null MX“ (nepřijímá poštu): email_domain")
SCEN["doh"] = {"MX": (200, {"Status": 0}), "A": (200, {"Status": 0, "Answer": [{"type": 1, "data": "1.2.3.4"}]})}
st, d = post(nove())
ok(st == 201, "U12 doména bez MX, ale s A záznamem (implicitní MX podle RFC 5321): projde")
SCEN["doh"] = {"MX": (None, None)}; SCEN["dig"] = "unknown"
st, d = post(nove())
ok(st == 503 and d.get("error") == "email_unverifiable", "U13 DNS nejde ověřit (DoH i dig selhaly): 503 email_unverifiable, uloží se až po ověření")
SCEN["dig"] = "ok"
st, d = post(nove())
ok(st == 201, "U14 DoH nedostupné, ale záložní dig doménu potvrdí: projde")
SCEN["doh"] = {"MX": (200, {"Status": 0, "Answer": [{"type": 15, "data": "10 mx.example.cz."}]})}
for ph in ("12345", "abc", "+12 3"):
    st, d = post(nove(phone=ph))
    ok(st == 400 and d.get("error") == "phone_invalid" and d.get("field") == "phone", "U15 neplatný telefon „%s“: phone_invalid" % ph)
st, d = post(nove(product_id=1))
ok(st == 422 and d.get("error") == "product_not_available", "U16 jiný produkt než konfigurovatelná karta: product_not_available")
sel_bad = dict(SEL); sel_bad["w"] = 99999
st, d = post(nove(configuration={"selection": sel_bad, "rules_version": RV}, email="orez@example.cz"))
radek_orez = (sql("SELECT selection_json FROM stul_ulozene_konfigurace WHERE email='orez@example.cz'") or [{}])[0]
ok(st == 201 and json.loads(radek_orez.get("selection_json") or "{}").get("w", 99999) <= 3000, "U17 šířka 99 999: server výběr OŘÍZNE na platné meze (jako v košíku) a uloží EFEKTIVNÍ výběr, ne klientův")
_vyres = U.kk.vyres
def _nejde(*a, **k):
    raise U.kk.KonfiguraceChyba("invalid_configuration", "Tuto konfiguraci nelze vyrobit.", 422, errors=[{"slot": None, "message": "x"}])
U.kk.vyres = _nejde
st, d = post(nove(email="neide@example.cz"))
U.kk.vyres = _vyres
ok(st == 422 and d.get("error") == "config_invalid" and (sql("SELECT COUNT(*) AS n FROM stul_ulozene_konfigurace WHERE email='neide@example.cz'")[0]["n"] == 0), "U17b konfigurace, kterou konfigurátor odmítne: 422 config_invalid a nic se neuloží")
sql("DELETE FROM stul_ulozene_konfigurace"); sql("DELETE FROM crm_lead_messages"); sql("DELETE FROM crm_leads")
st, d = post(nove(configuration={"selection": SEL, "rules_version": "stara"}))
ok(st == 409 and d.get("error") == "rules_changed", "U18 stará verze pravidel: 409 rules_changed")

# ---- uspech: zaznam, lead, obnoveni
sql("DELETE FROM stul_ulozene_konfigurace"); sql("DELETE FROM crm_lead_messages"); sql("DELETE FROM crm_leads")
VOLANI.clear()
st, d = post(nove())
tok = d.get("token", "")
ok(st == 201 and re.fullmatch(r"[A-Za-z0-9_-]{22}", tok) and d.get("kod", "").startswith("STL-") and d.get("firma") == "LOGIMAN s.r.o." and d.get("odkaz_platnost_dni") == 90, "S1 uloženo: 201, token 22 znaků, kód %s, firma z registru" % d.get("kod"))
radek = (sql("SELECT * FROM stul_ulozene_konfigurace") or [{}])[0]
ok(radek.get("token_hash") and tok not in json.dumps(radek, default=str) and radek.get("karta_id") == 4934 and radek.get("ico") == "28337638" and radek.get("email") == "test.zakaznik@example.cz" and radek.get("phone") == "+420603230059",
   "S2 v tabulce je token jen jako hash, e-mail malými písmeny, telefon normalizovaný (+420603230059), IČO 28337638, karta 4934")
sel_ulozeny = json.loads(radek.get("selection_json") or "{}")
ok(sel_ulozeny.get("w") == SEL.get("w") and float(radek.get("net_czk") or 0) > 1000, "S3 uložen EFEKTIVNÍ výběr ověřený serverem a cena bez DPH (%s Kč)" % radek.get("net_czk"))
lead = (sql("SELECT * FROM crm_leads") or [{}])[0]
msg = (sql("SELECT body FROM crm_lead_messages") or [{}])[0].get("body", "")
ok(lead.get("source") == "stul_ulozeni" and lead.get("contact_email") == "test.zakaznik@example.cz" and lead.get("company_name") == "LOGIMAN s.r.o." and float(lead.get("estimated_value") or 0) > 1000 and lead.get("unread_by_admin") == 1 and radek.get("crm_lead_id") == lead.get("id"),
   "S4 vznikl lead v CRM (source stul_ulozeni, firma z registru, odhad ceny, nepřečtený) a je svázán se záznamem")
ok("Odkaz pro návrat" in msg and tok in msg and "IČO 28337638 (ověřeno v ARES)" in msg and "Kód konfigurace: " + d.get("kod", "?") in msg, "S5 zpráva pro zaměstnance nese kód, firmu s IČO a odkaz pro návrat")
ok(not any("smtp" in u.lower() or "mail" in u.lower() and "dns-query" not in u for u in VOLANI), "S6 žádný e-mail se neodeslal (volala se jen registr a DNS)")
st, g = (lambda r: (r.status_code, r.get_json()))(client.get("/api/shop/configurator/ulozena/" + tok, base_url=MAIN))
ok(st == 200 and g.get("product_id") == 4934 and g.get("selection", {}).get("w") == SEL.get("w") and g.get("kod") == d.get("kod") and g.get("rules_version") == RV, "S7 odkaz vrátí uloženou konfiguraci (karta, výběr, kód, verze pravidel)")
for zly in ("neexistuje0123456789ab", "x", "../../etc/passwd", "A" * 40):
    ok(client.get("/api/shop/configurator/ulozena/" + zly, base_url=MAIN).status_code == 404, "S8 neplatný / neexistující token „%s“: 404" % zly[:24])
sql("UPDATE stul_ulozene_konfigurace SET expires_at = NOW() - INTERVAL 1 DAY")
ok(client.get("/api/shop/configurator/ulozena/" + tok, base_url=MAIN).status_code == 404, "S9 vypršený odkaz: 404 (záznam v CRM zůstává)")
sql("UPDATE stul_ulozene_konfigurace SET expires_at = NOW() + INTERVAL 90 DAY")

# ---- limity
sql("DELETE FROM stul_ulozene_konfigurace")
for i in range(5):
    st, d = post(nove(email="limit@example.cz"))
st, d = post(nove(email="limit@example.cz"))
ok(st == 429 and d.get("error") == "too_many", "L1 šestá uložená konfigurace téhož e-mailu za den: 429 too_many")
U._rate_limited = appmod._rate_limited
cnt = 0
for i in range(8):
    st, d = post(nove(email="ip%d@example.cz" % i, consent=False))
    cnt += st == 429
ok(cnt >= 1 and d.get("error") in ("rate_limited", "consent_required"), "L2 limit IP (6 / 10 min) funguje: po sérii požadavků přijde 429 rate_limited")
U._rate_limited = lambda *a, **k: False

# ---- mini-shop (SK): zeme z shopu, registr RPO, jen verejne produkty shopu
sql("DELETE FROM stul_ulozene_konfigurace"); sql("DELETE FROM crm_lead_messages"); sql("DELETE FROM crm_leads")
VOLANI.clear()
st, d = post(nove(ico="35757442", email="sk@example.sk", phone="0903 123 456", product_id=4934), base=SKSHOP)
ok(st == 201 and any("statistics.sk" in u for u in VOLANI) and not any("ares" in u for u in VOLANI) and d.get("firma", "").startswith("VOLKSWAGEN"), "M1 SK mini-shop: IČO se ověří v registru RPO (ne v ARES), firma %s" % d.get("firma"))
r2 = (sql("SELECT * FROM stul_ulozene_konfigurace") or [{}])[0]
ok(r2.get("country") == "SK" and r2.get("phone") == "+421903123456" and r2.get("shop_host") == "baliace-stoly.top", "M2 země SK a slovenské číslo +421903123456, host shopu uložen")
SCEN["rpo"] = (200, {"results": []})
st, d = post(nove(ico="35757442", product_id=4934), base=SKSHOP)
ok(st == 422 and d.get("error") == "ico_not_found", "M3 RPO IČO nezná: 422 ico_not_found")
st, d = post(nove(ico="35757442", product_id=99999), base=SKSHOP)
ok(st == 422 and d.get("error") == "product_not_available", "M4 produkt, který shop nenabízí: product_not_available")

# ---- bez tabulky (DDL jeste nebezel) = funkce vypnuta
sql("DROP TEMPORARY TABLE stul_ulozene_konfigurace")
st, d = post(nove(), base=MAIN, bez=("stul_ulozene_konfigurace",))
ok(st == 503 and d.get("error") == "unavailable", "T1 bez tabulky (DDL nespuštěn): ukládání vrací 503 unavailable, žádné DDL za běhu")
r = client.get("/api/shop/configurator/ulozena/AAAAAAAAAAAAAAAAAAAAAA", base_url=MAIN)
ok(r.status_code == 503, "T2 bez tabulky i čtení vrací 503 (UI podle toho tlačítko vůbec neukáže)")
sql(U.DDL.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMPORARY TABLE", 1))
r = client.get("/api/shop/configurator/ulozena/AAAAAAAAAAAAAAAAAAAAAA", base_url=MAIN)
ok(r.status_code == 404 and (r.get_json() or {}) == {"error": "not_found", "ulozeni": 1}, "T3 s tabulkou probe vrací 404 se značkou {error: not_found, ulozeni: 1} (= funkce zapnutá; obecné 404 starého serveru značku nemá)")
src = open(os.path.join(REPO, "sql", "2026-10-05_stul_ulozene_konfigurace.py"), encoding="utf-8").read()
ok("karta_id" in U.DDL and "product_id" not in U.DDL and "shop_product_id" not in U.DDL and "token_hash" in U.DDL, "T4 tabulka nemá sloupec product_id / shop_product_id (QA product_duplicate_unclassified_table) a drží token jen jako hash")
ok('re.search(r\'DDL = """(CREATE TABLE IF NOT EXISTS stul_ulozene_konfigurace' in src and re.search(r'DDL = """(CREATE TABLE IF NOT EXISTS stul_ulozene_konfigurace .*?)"""', open(os.path.join(REPO, "api", "stul_ulozeni.py"), encoding="utf-8").read(), re.S), "T5 migrační skript bere DDL z modulu (jedna verze)")

PO = ostre()
ok(PO == PRED, "K ostré tabulky crm_leads / crm_lead_messages se testem nezměnily a tabulka stul_ulozene_konfigurace v ostré DB NEvznikla (existuje: %s)" % PO["tabulka_existuje"])
print("\n==> %d/%d kontrol OK" % (total - bad, total))
sys.exit(1 if bad else 0)
