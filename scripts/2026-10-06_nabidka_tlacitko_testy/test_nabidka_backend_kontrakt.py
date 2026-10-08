#!/opt/konfigurator/api/venv/bin/python
"""Kontrakt UI (webapp/js/stul-nabidka.js, bot16) <-> SKUTECNY backend nabidky z konfigurace (api/nabidka_z_konfigurace.py, bot5; kontrakt docs/KONTRAKT_NABIDKA_Z_KONFIGURACE.md), 2026-10-06.
Skutecna routa pres Flask test client (prihlaseny admin = session_transaction), skutecna DB jen ke CTENI. NIKDY nevola cestu, ktera nabidku zalozi: telo sestavene stejne jako v modulu
(product_id + configuration{selection, rules_version} + qty + montaz_pct + delivery_country + hash) se posila vzdy s ZAMERNE spatnym hashem (-> 409 configuration_changed PRED zapisem) nebo
s neplatnym polem (-> 400 pred zapisem); pocet radku scene_offers a audit_log se na zacatku a na konci porovna (musi byt stejny).
Overuje: sonda (200 {ok:true, verze:1} / 401 / 403), ze backend telo od UI PRIJME (projde validaci i vyresenim vyberu az k porovnani hashe), kody a tvar chyb, ktere UI mapuje na hlasky.
Spusteni (z izolovane kopie HEAD, DB pres systemd-run):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=<worktree HEAD> \
    /opt/konfigurator/api/venv/bin/python3 /opt/konfigurator/scripts/2026-10-06_nabidka_tlacitko_testy/test_nabidka_backend_kontrakt.py"""
import json
import os
import re
import sys
import threading

REPO = os.getcwd()                                           # pracovni adresar = izolovana kopie HEAD (api/ s backendem bota5)
API = os.path.join(REPO, "api")
MODUL_JS = os.environ.get("MODUL_JS") or os.path.join("/opt/konfigurator", "webapp", "js", "stul-nabidka.js")
if not os.path.exists(os.path.join(API, "nabidka_z_konfigurace.py")):
    print("CHYBA: v", API, "neni nabidka_z_konfigurace.py (spust z kopie HEAD s commitem 9c422069)")
    sys.exit(2)
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
try:
    import app as appmod  # noqa: E402
    import stul_shop as SH  # noqa: E402
finally:
    threading.Thread.start = _orig

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


def klient(uid):
    c = appmod.app.test_client()
    if uid:
        with c.session_transaction() as sess:
            sess["user_id"] = uid
    return c


def sql(q, args=()):
    c = appmod.get_conn()
    try:
        with c.cursor() as cur:
            cur.execute(q, args)
            return cur.fetchall()
    finally:
        c.rollback()
        c.close()


def uzivatel(role):
    r = sql("SELECT id FROM app_users WHERE role=%s AND COALESCE(active,1)=1 ORDER BY id LIMIT 1", (role,))
    return r[0]["id"] if r else None


def pocty():
    """(nabidky z konfigurace, audit zaznamy jejich vytvoreni) - jen to, co by testovane cesty zapsaly (ostatni provoz zapisuje do stejnych tabulek take)"""
    return (sql("SELECT COUNT(*) n FROM scene_offers WHERE JSON_UNQUOTE(JSON_EXTRACT(offer_options, '$.source'))='configurator'")[0]["n"],
            sql("SELECT COUNT(*) n FROM audit_log WHERE action='create_from_configuration'")[0]["n"])


def reset_limit():
    appmod._rate_limit_buckets.pop("konfig_nabidka:%s" % admin, None)


URL = "/api/admin/konfigurace/nabidka"
admin, zakaznik = uzivatel("admin"), uzivatel("user")
over("0 existuje aktivni admin", bool(admin))
pred = pocty()
A = klient(admin)


def POST(telo=None, **kw):
    """POST na nabidku s vynulovanym pametovym limitem (testy B/C jich delaji vic nez 30)"""
    reset_limit()
    return A.post(URL, json=telo, **kw) if telo is not None else A.post(URL, **kw)

print("== A) sonda a opravneni")
r = A.get(URL)
over("A1 admin: GET sonda 200 {ok:true, verze:1}", r.status_code == 200 and r.get_json() == {"ok": True, "verze": 1}, (r.status_code, r.get_json()))
r = klient(None).get(URL)
over("A2 bez prihlaseni: GET 401 (code unauthorized) -> UI tlacitko skryje", r.status_code == 401 and (r.get_json() or {}).get("code") == "unauthorized", (r.status_code, r.get_json()))
r = klient(None).post(URL, json={})
over("A3 bez prihlaseni: POST 401", r.status_code == 401, r.status_code)
if zakaznik:
    r = klient(zakaznik).get(URL)
    over("A4 zakaznik (role user): GET 403 (code forbidden) -> UI tlacitko skryje", r.status_code == 403 and (r.get_json() or {}).get("code") == "forbidden", (r.status_code, r.get_json()))
    r = klient(zakaznik).post(URL, json={})
    over("A5 zakaznik: POST 403", r.status_code == 403, r.status_code)

print("== B) telo sestavene jako v UI je backendem PRIJATO (zamerne spatny hash -> 409 pred zapisem)")
KARTY = [pid for pid in (4934, 4955, 4954, 4959) if SH.system_pro_produkt(pid) in (30, 35, 40, 41)]
over("B0 nalezena aspon jedna zivá karta generatoru (4934/4955/4954/4959)", len(KARTY) >= 1, KARTY)
telo_ui = {}
for pid in KARTY:
    system = SH.system_pro_produkt(pid)
    rr = A.post("/api/shop/configurator/resolve", json={"product_id": pid, "selection": {}, "staff": True, "lang": "cs"})
    res = rr.get_json() or {}
    over(f"B{system}.1 resolve (jako stranka) vrati vyber, hash a rules_version", rr.status_code == 200 and res.get("hash") and res.get("rules_version") and isinstance(res.get("selection"), dict), (rr.status_code, list(res)[:8]))
    if not res.get("hash"):
        continue
    # presne to, co sestavi modul: product_id + configuration{selection, rules_version} + qty + montaz_pct + delivery_country + hash (+ volitelne customer)
    telo = {"product_id": pid, "configuration": {"selection": res["selection"], "rules_version": res["rules_version"]}, "qty": 1, "montaz_pct": None, "delivery_country": "CZ", "hash": "0" * 40}
    telo_ui[pid] = telo
    r1 = POST(telo)
    j = r1.get_json() or {}
    over(f"B{system}.2 karta {pid}: telo UI projde validaci i vyresenim vyberu; spatny hash -> 409 configuration_changed (zadny zapis)", r1.status_code == 409 and j.get("error") == "configuration_changed" and isinstance(j.get("message"), str), (r1.status_code, j))
    t2 = dict(telo, qty=3, montaz_pct=15.5, delivery_country="PL", customer={"name": "Jan Novák", "email": "jan@firma.cz"})
    r2 = POST(t2)
    over(f"B{system}.3 karta {pid}: vsechna volitelna pole (qty 3, vlastni montaz 15,5, zeme PL, zakaznik) backend prijme (az k porovnani hashe)", r2.status_code == 409 and (r2.get_json() or {}).get("error") == "configuration_changed", (r2.status_code, r2.get_json()))
    t3 = dict(telo, qty=99, montaz_pct=0, delivery_country="cz")
    r3 = POST(t3)
    over(f"B{system}.4 karta {pid}: horni mez qty 99, montaz_pct 0 (= bez montaze) a zeme malymi pismeny jsou platne", r3.status_code == 409 and (r3.get_json() or {}).get("error") == "configuration_changed", (r3.status_code, r3.get_json()))
    # KLICOVE: hash a kod, ktere drzi stranka (z jejiho resolve), se musi ROVNAT hashi a kodu, ktere si pocita backend nabidky (kk.vyres) - jinak by KAZDA skutecna nabidka skoncila 409.
    # Skutecny uspech (zapis) se z testu nikdy nevola, proto se tady porovnava primo vysledek vyres (jen cteni DB).
    import konfigurace_kosik as kk
    c_ = appmod.get_conn()
    try:
        with c_.cursor() as cur_:
            v_ = kk.vyres(cur_, pid, res["selection"], "cs", res["rules_version"])
    finally:
        c_.rollback(); c_.close()
    over(f"B{system}.6 karta {pid}: hash a kod ze stranky (resolve) == hash a kod serveru nabidky (vyres): skutecna nabidka NEskonci 409 configuration_changed", v_["hash"] == res["hash"] and v_["kod"] == res["kod"] and v_["selection"] == res["selection"], (v_["hash"], res["hash"], v_["kod"], res["kod"]))
    # po zmene vyberu (sirka o 100 mm jinak) znovu to same: hash cesty "stranka" a cesty "nabidka" se musi shodovat i pro jinou konfiguraci
    sel2 = dict(res["selection"]); sel2["w"] = int(sel2.get("w", 1200)) + (100 if int(sel2.get("w", 1200)) < 1900 else -100)
    rr2 = A.post("/api/shop/configurator/resolve", json={"product_id": pid, "selection": sel2, "staff": True, "lang": "cs"}).get_json() or {}
    c_ = appmod.get_conn()
    try:
        with c_.cursor() as cur_:
            v2_ = kk.vyres(cur_, pid, rr2.get("selection") or sel2, "cs", rr2.get("rules_version"))
    finally:
        c_.rollback(); c_.close()
    over(f"B{system}.7 karta {pid}: totez po zmene sirky ({sel2['w']} mm): hash a kod ze stranky == hash a kod serveru nabidky", rr2.get("hash") and v2_["hash"] == rr2["hash"] and v2_["kod"] == rr2["kod"] and rr2["hash"] != res["hash"], (rr2.get("hash"), v2_["hash"], res["hash"]))
    t4 = dict(telo, configuration={"selection": res["selection"], "rules_version": "1900-01-01.0"})
    r4 = POST(t4)
    over(f"B{system}.5 karta {pid}: stara rules_version -> 409 rules_changed (UI ukaze hlasku a nacte konfiguraci znovu)", r4.status_code == 409 and (r4.get_json() or {}).get("error") == "rules_changed", (r4.status_code, r4.get_json()))

print("== C) neplatne vstupy: 400 (kody, ktere UI mapuje) a 404")
pid0 = KARTY[0] if KARTY else 4934
dobre = dict(telo_ui.get(pid0) or {"product_id": pid0, "configuration": {"selection": {}, "rules_version": None}, "qty": 1}, hash="0" * 40)   # spatny hash = ani platne telo nikdy nedojde k zapisu
PRIPADY = [
    ("qty 0", dict(dobre, qty=0), 400, "items_invalid"), ("qty 100 (max 99)", dict(dobre, qty=100), 400, "items_invalid"), ("qty text", dict(dobre, qty="abc"), 400, "items_invalid"),
    ("qty 1.5", dict(dobre, qty=1.5), 400, "items_invalid"), ("montaz_pct 101", dict(dobre, montaz_pct=101), 400, "items_invalid"), ("montaz_pct -1", dict(dobre, montaz_pct=-1), 400, "items_invalid"),
    ("montaz_pct text", dict(dobre, montaz_pct="x"), 400, "items_invalid"), ("zeme CZE", dict(dobre, delivery_country="CZE"), 400, "items_invalid"), ("zeme 12", dict(dobre, delivery_country="12"), 400, "items_invalid"),
    ("customer text", dict(dobre, customer="Jan"), 400, "items_invalid"), ("customer e-mail bez zavinace", dict(dobre, customer={"email": "abc"}), 400, "items_invalid"),
    ("hash prilis dlouhy", dict(dobre, hash="x" * 65), 400, "items_invalid"),
    ("bez selection", dict(dobre, configuration={"rules_version": "x"}), 400, "invalid_selection"), ("bez configuration", {k: v for k, v in dobre.items() if k != "configuration"}, 400, "invalid_selection"),
    ("bez product_id", {k: v for k, v in dobre.items() if k != "product_id"}, 400, "invalid_selection"), ("product_id text", dict(dobre, product_id="abc"), 400, "invalid_selection"),
]
for nazev, telo, st, kod in PRIPADY:
    r = POST(telo)
    j = r.get_json() or {}
    over(f"C {nazev}: {st} {kod} se zpravou", r.status_code == st and j.get("error") == kod and isinstance(j.get("message"), str) and j["message"], (r.status_code, j))
r = POST(data="neni json", content_type="application/json")
over("C telo neni JSON: 400 invalid_selection", r.status_code == 400 and (r.get_json() or {}).get("error") == "invalid_selection", (r.status_code, r.get_json()))
nekonf = sql("SELECT id FROM shop_products WHERE id NOT IN (4934, 4954, 4955, 4959) ORDER BY id LIMIT 1")
if nekonf:
    r = POST(dict(dobre, product_id=nekonf[0]["id"]))
    over(f"C karta {nekonf[0]['id']} (bezny produkt): 404 not_configurable", r.status_code == 404 and (r.get_json() or {}).get("error") == "not_configurable", (r.status_code, r.get_json()))
r = POST(dict(dobre, product_id=999999999))
over("C neexistujici product_id: 404 not_configurable", r.status_code == 404 and (r.get_json() or {}).get("error") == "not_configurable", (r.status_code, r.get_json()))

print("== D) limit 30 za hodinu na uzivatele (pametovy citac procesu, izolovany od provozu)")
reset_limit()
kody = [A.post(URL, json=dict(dobre, qty=0)).status_code for _ in range(32)]
r = A.post(URL, json=dict(dobre, qty=0))
over("D1 po 30 pozadavcich dalsi dostane 429 rate_limited (i neplatne se pocitaji); UI mapuje na hlasku o limitu", kody[:30] == [400] * 30 and kody[30] == 429 and r.status_code == 429 and (r.get_json() or {}).get("error") == "rate_limited", (kody[28:], r.status_code, r.get_json()))
reset_limit()

print("== E) UI mapuje KAZDY kod chyby, ktery backend umi vratit")
mod = open(MODUL_JS, encoding="utf-8").read()
m = re.search(r"var MSG = \{(.*?)\n  \};", mod, re.S)
klice = set(re.findall(r"^\s*([a-z_]+):", m.group(1), re.M)) if m else set()
zdroj = open(os.path.join(API, "nabidka_z_konfigurace.py"), encoding="utf-8").read() + open(os.path.join(API, "konfigurace_kosik.py"), encoding="utf-8").read()
kody_be = set(re.findall(r'_Chyba\(\d+, "([a-z_]+)"', zdroj)) | set(re.findall(r'KonfiguraceChyba\("([a-z_]+)"', zdroj)) | {"rate_limited"}
kody_be -= {"configuration_required"}                          # jen kosik (tady se neposila)
over("E1 v modulu je tabulka hlasek (MSG) a obsahuje klice net, fail", {"net", "fail"} <= klice, sorted(klice))
over("E2 kazdy chybovy kod backendu ma v UI vlastni hlasku", kody_be <= klice, sorted(kody_be - klice))
over("E3 hlasky pro 401/403 z vrstvy opravneni (code unauthorized / forbidden) existuji", {"unauthorized", "forbidden"} <= klice, sorted(klice))

po = pocty()
over("Z NIC se nezapsalo: pocet nabidek z konfigurace a jejich audit zaznamu je stejny jako na zacatku", po == pred, (pred, po))
print(f"\n==> {sum(vysl)}/{len(vysl)} kontrol OK")
sys.exit(0 if all(vysl) else 1)
