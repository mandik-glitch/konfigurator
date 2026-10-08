#!/usr/bin/env python3
"""Test DELKY LED SVITIDLA ve VEREJNEM API stolu (api/stul_shop.py; bot8, 2026-10-07; Robert: "LED 600 doplnit do generatoru"; karta #5359 LED600).
SKUTECNE routy pres Flask test_client (bez prihlaseni = verejnost, se session admina = zamestnanec). DB se jen CTE (ceny karet svitidel); mapovani produktu se podstrci do cache modulu - nic se nezapisuje.

Hlida: schema (slot `ledlen` = select 600 | 1200 mm hned za `ledlight`, zavisi na posts + led + ledlight, texty cs/en/sk, SSE slot nema), resolve (vychozi 1200 = beze zmeny, volba 600, pocet svitidel,
cena = cena karty x pocet, kusovnik), zakazane delky s duvodem a nejmensi sirkou, nabidka "Zapnout kratsi LED 600 mm" u zakazaneho prepinace LED, nabidka verejnosti (karta aktivni, neni archivovana, ma GLB
a je ve scene; zamestnanec vsechny; chyba DB = jen 1200), token (klic K jen u jine nez vychozi delky), shrnuti voleb, odkaz na vyrobni list, klic cache resolve, 3D ovladani (menu + preklady),
data pro pocitadlo luxu, staff API (`?led_delka=`).
Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_led600_generator/test_led_delka_shop.py
  (STUL_API_OVERRIDE=<adresar api> = kandidat; --setenv=STUL_API_OVERRIDE=... pri spusteni pres systemd-run)"""
import json
import os
import sys
import threading
import time
import urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi - spust pres systemd-run --property=EnvironmentFile=api/.env (viz hlavicka)")
    sys.exit(2)

_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
try:
    import app as appmod  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_api as _stul_api  # noqa: E402
finally:
    threading.Thread.start = _orig

S.nastav_pravidla({})                                                    # zive Robertovy pravidla (cena vyrezu...) test neovlivni
_stul_api.obnov_pravidla = lambda force=False: None
SH.LIMIT_SCHEMA = (10 ** 6, 60)                                          # test vola verejne API desitky krat z jedne IP: omezeni poctu dotazu (429) by ho shodilo
SH.LIMIT_RESOLVE = (10 ** 6, 60)
SH.HODINOVY_STROP["schema"] = SH.HODINOVY_STROP["resolve"] = 10 ** 6

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")
        if os.environ.get("TEST_STOP_PRVNI"):                  # rychly beh pro mutace: prvni selhani konci (mutace.py)
            sys.exit(1)


PID, PID_SSE = 9885, 9886
L1200, L600 = "product_4929", "product_5359"


def nastav_led(delky):
    """Simulace aktivnich karet svitidel (cache SH.led_delky_verejne): verejnost vidi vychozi 1200 + `delky`; nic se nezapisuje do DB."""
    SH._LED_DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset({S.LED_DELKA_VYCHOZI, *delky}))


nastav_led({600})                                                        # zakladni testy bezi s uvolnenou delkou 600; gating je zvlast (sekce GATE)
SH._DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset(S.PANEL_DELKY))   # delky panelu nezavisi na teto sade
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PID): SH.RECEPT, str(PID_SSE): SH.RECEPT_SSE})
anon = appmod.app.test_client()
c_adm = appmod.get_conn()
cu_adm = c_adm.cursor()
cu_adm.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN_ID = cu_adm.fetchone()["id"]
c_adm.rollback()
staff = appmod.app.test_client()
with staff.session_transaction() as _s:
    _s["user_id"] = ADMIN_ID


def post(sel, lang="cs", pid=PID, klient=None):
    r = (klient or anon).post("/api/shop/configurator/resolve", json={"product_id": pid, "selection": sel, "lang": lang})
    return r.status_code, r.get_json()


def schema(lang="cs", pid=PID, klient=None):
    return (klient or anon).get(f"/api/shop/products/{pid}/configurator?lang={lang}").get_json()


def led_dily(sel):
    return [d for d in S.sestav_stul(**SH.normalizuj(sel, 30)[0])["dily"] if d["part_id"] in (L1200, L600)]


# ---- schema
for lang, label, popis in (("cs", "Délka LED svítidla", "mm"), ("en", "LED light length", "mm"), ("sk", "Dĺžka LED svietidla", "mm")):
    sc = schema(lang)
    slots = {s["id"]: s for s in sc["slots"]}
    sl = slots.get("ledlen")
    check(sl is not None and sl["type"] == "select" and sl["group"] == "g_extras", f"schema {lang}: slot ledlen je select ve skupine g_extras ({sl and (sl['type'], sl['group'])})")
    if sl:
        check([o["id"] for o in sl["options"]] == ["600", "1200"] and [o["label"] for o in sl["options"]] == ["600 mm", "1200 mm"], f"schema {lang}: volby 600 / 1200 mm ({[o['label'] for o in sl['options']]})")
        check(sl["label"] == label and sl["help"] and "{" not in sl["help"], f"schema {lang}: popisek '{label}' a napoveda ({sl['label']!r})")
        check(sl.get("depends_on") == ["posts", "led", "ledlight"], f"schema {lang}: slot zavisi na posts + led + ledlight ({sl.get('depends_on')})")
        ids = [s["id"] for s in sc["slots"]]
        check(ids.index("ledlen") == ids.index("ledlight") + 1, f"schema {lang}: slot ledlen je hned za ledlight")
    check(sc["default_selection"].get("ledlen") == "1200" and set(sc["default_selection"]) == set(slots), f"schema {lang}: vychozi vyber ma ledlen = 1200 a klic pro kazdy slot")
check("ledlen" not in {s["id"] for s in schema("cs", PID_SSE)["slots"]}, "schema SSE (system 41): slot ledlen neni")
for lang in [x for x in ("de", "hu") if x in SH.TEXTY]:
    check(all(k in SH.TEXTY[lang] for k in ("ledlen", "ledlen_600", "ledlen_1200", "help_ledlen")) and lang in SH.LEDLEN_NEVEJDE and lang in SH.LED_NENI_V_NABIDCE and "led_kratsi" in SH.TEXTY_AKCI[lang],
          f"dalsi jazyk {lang}: nove texty maji (anglickou) zalohu")

base = dict(schema("cs")["default_selection"], ledcount=S.LED_MAX)           # od 2026-10-08 je pocet svitidel RUCNI (vychozi 1): tyto kontroly overuji svitidla podle sirky = nejvic, co se vejde

# ---- vychozi stul: beze zmeny, obe delky se vejdou
st, d = post(base)
check(st == 200 and d["valid"] and d["selection"]["ledlen"] == "1200" and d["options"]["ledlen"] == {}, f"vychozi vyber: platny, ledlen 1200, nic zakazaneho ({st}, {d['options'].get('ledlen')})")
p_def = SH.normalizuj(base, 30)[0]
check(d["hash"] == G.kanonicky_hash(S.sestav_stul(**p_def)["parametry"]) and p_def["led_delka"] == 1200.0 and len(led_dily(base)) == 1, "vychozi vyber: hash = hash generatoru, jedno svitidlo 1200")
check(post(dict(base, ledlen="1200"))[1]["hash"] == d["hash"], "ledlen=1200 explicitne = vychozi (stejny hash)")
check(not [n for n in d["notices"] if n["slot"] == "ledlen"], "vychozi vyber: zadne oznameni o delce svitidla")

# ---- volba 600: pocet svitidel, cena, kusovnik
ctx = _stul_api._ctx_ceny()
c1200, c600 = ctx["parts"][L1200]["price_czk"], ctx["parts"][L600]["price_czk"]
check(c1200 is not None and c600 is not None and c600 > 0, f"karty svitidel maji cenu v katalogu (4929: {c1200}, 5359: {c600})")
ceny = {}
for w in (1280, 2000, 3000):
    st, d6 = post(dict(base, w=w, ledlen="600"))
    n6 = max(1, int((w + 47) // 647))
    check(st == 200 and d6["valid"] and d6["selection"]["ledlen"] == "600" and not d6["errors"], f"W={w} ledlen=600: platne, vybrano 600 ({st}, {d6.get('selection', {}).get('ledlen')})")
    check(len(led_dily(dict(base, w=w, ledlen="600"))) == n6 and all(x["part_id"] == L600 for x in led_dily(dict(base, w=w, ledlen="600"))), f"W={w} ledlen=600: {n6} svitidel product_5359")
    kus = _stul_api.cena_konfigurace(S.sestav_stul(**SH.normalizuj(dict(base, w=w, ledlen="600"), 30)[0])["dily"])["kusovnik"]["radky"]
    rad = [x for x in kus if "[LED600]" in x["nazev"]]
    check(len(rad) == 1 and rad[0]["mnozstvi"] == n6 and abs(rad[0]["cena_ks"] - c600) < 0.005 and not [x for x in kus if "[LED1200]" in x["nazev"]], f"W={w} ledlen=600: kusovnik {n6} x LED600 za cenu karty {c600:.0f} ({rad and (rad[0]['mnozstvi'], rad[0]['cena_ks'])})")
    bom6 = SH._neutralni_bom(S.sestav_stul(**SH.normalizuj(dict(base, w=w, ledlen="600"), 30)[0])["dily"])
    led_b = [x for x in bom6 if x["nazev"].startswith("LED osvětlení")]
    check(len(led_b) == 1 and led_b[0]["nazev"] == "LED osvětlení 600 mm" and led_b[0]["mnozstvi"] == n6, f"W={w} ledlen=600: neutralni kusovnik (kosik / nabidka) '{n6} x LED osvětlení 600 mm' ({led_b})")
    bom12 = SH._neutralni_bom(S.sestav_stul(**SH.normalizuj(dict(base, w=w), 30)[0])["dily"])
    led_b12 = [x for x in bom12 if x["nazev"].startswith("LED osvětlení")]
    check(len(led_b12) == 1 and led_b12[0]["nazev"] == "LED osvětlení" and led_b12[0]["mnozstvi"] == max(1, int((w + 47) // 1247)), f"W={w} ledlen=1200: neutralni kusovnik 'LED osvětlení' beze zmeny ({led_b12})")
    ceny[w] = d6["price"]["net"]
    st, d12 = post(dict(base, w=w))
    n12 = max(1, int((w + 47) // 1247))
    kus12 = _stul_api.cena_konfigurace(S.sestav_stul(**SH.normalizuj(dict(base, w=w), 30)[0])["dily"])["kusovnik"]["radky"]
    rad12 = [x for x in kus12 if "[LED1200]" in x["nazev"]]
    check(len(rad12) == 1 and rad12[0]["mnozstvi"] == n12 and abs(rad12[0]["cena_ks"] - c1200) < 0.005, f"W={w} ledlen=1200: kusovnik {n12} x LED1200 za cenu karty {c1200:.0f}")
    dp = d6["price"]["net"] - d12["price"]["net"]
    check(abs(dp - 1.03 * (n6 * c600 - n12 * c1200)) < 2.0, f"W={w}: rozdil ceny 600 vs 1200 = rozdil cen karet svitidel + Balne 3 % ({dp:.2f} vs {1.03 * (n6 * c600 - n12 * c1200):.2f})")
    check(d6["hash"] != d12["hash"], f"W={w}: ruzne delky = ruzne hashe")

# ---- uzky stul: delka, ktera se nevejde, je zakazana s duvodem a nejmensi sirkou (cs / en / sk), svitidlo 600 zustava
for lang in ("cs", "en", "sk"):
    st, d9 = post(dict(base, w=900, ledlen="600"), lang)
    op = d9["options"]["ledlen"]
    check(d9["valid"] and d9["selection"]["led"] and d9["selection"]["ledlen"] == "600" and set(op) == {"1200"} and op["1200"]["disabled"], f"W=900 ({lang}): LED 600 zustava, 1200 zakazana ({sorted(op)})")
    ocek_duvod = {"cs": "LED svítidlo 1200 mm se sem nevejde – potřebuje stůl široký aspoň 1200 mm.", "en": "A 1200 mm LED light does not fit here – it needs a table at least 1200 mm wide.",
                  "sk": "LED svietidlo 1200 mm sa sem nezmestí – potrebuje stôl široký aspoň 1200 mm."}[lang]
    check(op["1200"]["reason"] == ocek_duvod, f"W=900 ({lang}): duvod = '{ocek_duvod}' (nejmensi sirka = delka telesa - presah, ne delka telesa; {op['1200']['reason'][:90]})")
check(post(dict(base, w=900, ledlen="600"), "cs")[1]["options"]["ledlen"]["1200"]["reason"] != post(dict(base, w=900, ledlen="600"), "en")[1]["options"]["ledlen"]["1200"]["reason"], "duvod je prelozeny")
st, d9 = post(dict(base, w=900))                                           # vychozi 1200 se na 900 nevejde: LED se odebere jako dosud (beze zmeny chovani)
check(d9["valid"] and d9["selection"]["led"] is False and d9["selection"]["ledlen"] == "1200" and d9["options"]["ledlen"] == {}, f"W=900 ledlen=1200: LED se odebere jako dosud, ledlen 1200 ({d9['selection']['led']}, {d9['selection']['ledlen']})")
check(any(n["slot"] == "led" for n in d9["notices"]), "W=900 ledlen=1200: oznameni o automatickem odebrani LED zustava")
st, d5 = post(dict(base, w=500, ledlen="600"))                           # ani 600 se nevejde: LED se odebere, delka se vrati na 1200
check(d5["valid"] and d5["selection"]["led"] is False and d5["selection"]["ledlen"] == "1200", f"W=500 ledlen=600: LED se odebere, ledlen 1200 ({d5['selection']['led']}, {d5['selection']['ledlen']})")
st, d6 = post(dict(base, w=640, ledlen="600"))
check(d6["valid"] and d6["selection"]["led"] and d6["selection"]["ledlen"] == "600", f"W=640 ledlen=600: svitidlo 600 se vejde ({d6['selection']['led']})")

# ---- normalizace vyberu: delka svitidla se bez LED zahodi uz ve vstupu (nezavisle na generatoru)
pn, nn = SH.normalizuj(dict(base, w=2000, ledlen="600", led=False), 30)
check(pn["led_delka"] == 1200.0 and nn["ledlen"] == "1200", f"normalizuj: bez LED se delka svitidla zahodi na 1200 ({pn['led_delka']}, {nn['ledlen']})")
pn, nn = SH.normalizuj(dict(base, w=2000, ledlen="600"), 30)
check(pn["led_delka"] == 600.0 and nn["ledlen"] == "600", f"normalizuj: s LED je delka 600 ({pn['led_delka']}, {nn['ledlen']})")

# ---- nabidka u zakazaneho prepinace LED: kratsi svitidlo misto roztazeni stolu
for lang, stitek in (("cs", "Zapnout kratší LED 600 mm"), ("en", "Switch on the shorter 600 mm LED light"), ("sk", "Zapnúť kratšie LED 600 mm")):
    st, dv = post(dict(base, w=900, led=False), lang)
    on = dv["options"]["led"]["on"]
    check(on["disabled"] and on.get("suggest") == {"ledlen": "600"} and on.get("suggest_label") == stitek, f"W=900 LED vypnuta ({lang}): zakazano s nabidkou '{stitek}' ({on.get('suggest')}, {on.get('suggest_label')})")
st, dv = post(dict(base, w=900, led=False))
st, dz = post(dict(base, w=900, led=True, ledlen="600"))
check(dz["valid"] and dz["selection"]["led"] and dz["selection"]["ledlen"] == "600" and len(led_dily(dict(base, w=900, led=True, ledlen="600"))) == 1, "pouziti nabidky (ledlen=600 + led zapnuto): na stole 900 je svitidlo 600")
st, dv5 = post(dict(base, w=500, led=False))
on5 = dv5["options"]["led"]["on"]
check(on5["disabled"] and on5.get("suggest") == {"w": 1200}, f"W=500 LED vypnuta: ani kratsi svitidlo se nevejde = dosavadni nabidka roztazeni stolu na 1200 mm beze zmeny ({on5.get('suggest')})")
st, dl = post(dict(base, w=1500, led=False))
check(dl["options"]["led"]["on"]["disabled"] is False and "suggest" not in dl["options"]["led"]["on"], "W=1500 LED vypnuta uzivatelem: lze zapnout, zadna nabidka")
st, dr = post(dict(base, w=1100, led=False))
check(dr["options"]["led"]["on"].get("suggest") == {"ledlen": "600"}, f"W=1100 LED vypnuta: nabidka kratsiho svitidla ({dr['options']['led']['on'].get('suggest')})")
st, ds = post(dict(base, w=900, led=False, posts=False))
check("ledlen" not in (ds["options"]["led"]["on"].get("suggest") or {}), "bez zadnich stojek se kratsi svitidlo nenabizi (LED potrebuje stojky)")

# ---- vypnute svitidlo / LED / stojky: delka se zahodi na 1200 a hash nemeni
sel = dict(base, w=2000)
h_bez = {k: post(dict(sel, **{k_: v_ for k_, v_ in kw.items()}))[1]["hash"] for k, kw in (("led", {"led": False}), ("ledlight", {"ledlight": False}), ("posts", {"posts": False}))}
for k, kw in (("led", {"led": False}), ("ledlight", {"ledlight": False}), ("posts", {"posts": False})):
    st, dv = post(dict(sel, ledlen="600", **kw))
    check(dv["selection"]["ledlen"] == "1200" and dv["hash"] == h_bez[k], f"{kw}: delka 600 se zahodi na 1200, hash nemeni ({dv['selection']['ledlen']})")
    check(dv["options"]["ledlen"] == {}, f"{kw}: options.ledlen je prazdne")
for spatna in ("900", "abc", None, 601, [], {}, True, 1e99, -5, "600.0x"):
    st, dn = post(dict(sel, ledlen=spatna))
    check(st == 200 and dn["selection"]["ledlen"] == "1200", f"neplatna delka {spatna!r} = vychozi 1200 ({st}, {dn.get('selection', {}).get('ledlen')})")
st, dc = post(dict(sel, ledlen=600))
check(dc["selection"]["ledlen"] == "600" and dc["hash"] == post(dict(sel, ledlen="600"))[1]["hash"], f"cislo 600 (misto textu) se prijme ({dc['selection']['ledlen']})")
st, dc = post(dict(sel, ledlen="600.0"))
check(dc["selection"]["ledlen"] == "600", "text '600.0' se prijme jako 600")

# ---- systemy 40 a 35
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PID): SH.RECEPT, str(PID_SSE): SH.RECEPT_SSE, "9887": SH.RECEPT_40, "9888": SH.RECEPT_35})
for pid, P_ in ((9887, 40), (9888, 35)):
    sc_ = schema("cs", pid)
    check("ledlen" in {s["id"] for s in sc_["slots"]}, f"system {P_}: slot ledlen je ve schematu")
    st, dd = post(dict(sc_["default_selection"], w=900, ledlen="600"), pid=pid)
    check(st == 200 and dd["selection"]["led"] and "1200" in dd["options"]["ledlen"], f"system {P_} W=900: LED 600 zustava, 1200 zakazana")

# ---- token (klic K jen u jine delky) a model
p6, _ = SH.normalizuj(dict(sel, ledlen="600"), 30)
check(SH._zabal(S.sestav_stul(**p6)["parametry"]).get("K") == 600 and "K" not in SH._zabal(S.sestav_stul(**SH.normalizuj(sel, 30)[0])["parametry"]), "token: klic K jen u jine nez vychozi delky")
pp, chyba = SH.over_model(SH.podepis_model(S.sestav_stul(**p6)["parametry"]))
check(chyba is None and pp["led_delka"] == 600.0, f"token: delka 600 prezije podpis a rozbaleni ({chyba}, {pp and pp.get('led_delka')})")
pp0, _ = SH.over_model(SH.podepis_model(S.sestav_stul(**SH.normalizuj(sel, 30)[0])["parametry"]))
check(S._norm_parametry(pp0)["led_delka"] == 1200.0, "token: starsi token bez klice K = 1200")
p6_off, _ = SH.normalizuj(dict(sel, ledlen="600", led=False), 30)
check("K" not in SH._zabal(S.sestav_stul(**p6_off)["parametry"]), "token: bez LED klic K neni")
h_model, data = G.model_pro_parametry(S.sestav_stul(**p6)["parametry"])
check(len(data) > 100000 and h_model == G.kanonicky_hash(S.sestav_stul(**p6)["parametry"]), f"model GLB pro LED 600 se slozi ({len(data)} B)")

# ---- shrnuti voleb (doklad / nabidka): delka svitidla jen kdyz neni vychozi
for lang, popis in (("cs", "Délka LED svítidla"), ("en", "LED light length"), ("sk", "Dĺžka LED svietidla")):
    sou = SH._souhrn_voleb(SH.normalizuj(dict(base, w=2000, ledlen="600"), 30)[1], lang, 30)
    radek = [x for x in sou if x["id"] == "ledlen"]
    check(len(radek) == 1 and radek[0]["label"] == popis and radek[0]["value"] == "600 mm", f"shrnuti {lang}: '{popis}: 600 mm' ({radek})")
    sou0 = SH._souhrn_voleb(SH.normalizuj(dict(base, w=2000), 30)[1], lang, 30)
    check(not [x for x in sou0 if x["id"] == "ledlen"], f"shrnuti {lang}: u vychozi delky 1200 se radek neukazuje (shrnuti dosavadnich stolu beze zmeny)")
    sou1 = SH._souhrn_voleb(SH.normalizuj(dict(base, w=2000, ledlen="600", led=False), 30)[1], lang, 30)
    check(not [x for x in sou1 if x["id"] == "ledlen"], f"shrnuti {lang}: bez LED se delka neukazuje")

# ---- odkaz na vyrobni list (staff blok)
st, dk = post(dict(sel, ledlen="600"))
blok = SH._staff_blok(dk["hash"])
qs = dict(urllib.parse.parse_qsl(blok["vyrobni_list_url"].split("?", 1)[1]))
check(qs.get("led_delka") == "600.0", f"vyrobni list 600: dotaz nese led_delka ({qs.get('led_delka')})")
check(S.parametry_z_dotazu(qs)["led_delka"] == 600.0, "vyrobni list: dotaz se da vratit na parametry generatoru")
blok0 = SH._staff_blok(post(sel)[1]["hash"])
check("led_delka" not in blok0["vyrobni_list_url"], "vyrobni list 1200: vychozi delka v odkazu neni (odkazy beze zmeny)")

# ---- mapy dilu
check(all(SH.DIL_NA_SLOT.get(pid) == "led" for pid in S.LED_PARTY), f"DIL_NA_SLOT: oba dily svitidel -> led ({ {pid: SH.DIL_NA_SLOT.get(pid) for pid in S.LED_PARTY} })")
check(all(S.PREPINAC_DILU.get(pid) == "led" for pid in S.LED_PARTY), "PREPINAC_DILU: oba dily svitidel -> led")

# ---- klic cache resolve nese delku svitidla i nabizene delky
SH._RESOLVE_CACHE.clear()
h1 = post(dict(base, w=2000))[1]
h2 = post(dict(base, w=2000, ledlen="600"))[1]
check(h1["selection"]["ledlen"] == "1200" and h2["selection"]["ledlen"] == "600" and h1["hash"] != h2["hash"] and h1["price"] != h2["price"], "cache: 1200 a 600 nesdili odpoved")
nastav_led(set())
check(post(dict(base, w=2000))[1]["options"]["ledlen"] == {"hidden": True}, "cache: po zmene nabizenych delek se vraci options.ledlen hidden (klic cache nese nabizene delky)")
nastav_led({600})
check(post(dict(base, w=2000))[1]["options"]["ledlen"] == {}, "cache: po opetovne aktivaci zase {}")

# ---- 3D ovladani: menu delky svitidla a jeho preklady
for lang, ocek, txt1200 in (("cs", ["Zvolit LED 600 mm"], "Zvolit LED 1200 mm"), ("en", ["Use the 600 mm LED light"], "Use the 1200 mm LED light"), ("sk", ["Zvoliť LED 600 mm"], "Zvoliť LED 1200 mm")):
    st, dd = post(dict(base, w=1500), lang)
    casti = [c for c in dd["vodici"]["ovladani"]["casti"] if c["id"] == "led"][0]
    tx = [m["text"] for m in casti["menu"]]
    pol = [m for m in casti["menu"] if m["text"] in ocek]
    check(len(pol) == 1 and pol[0]["nastav"] == {"ledlen": "600"} and not pol[0]["zakazano"], f"3D menu {lang}: '{ocek[0]}' nastavuje slot ledlen=600 ({tx})")
    check("ledlen" in casti["param"], f"3D {lang}: cast led nese slot ledlen ({casti['param']})")
    st, d6m = post(dict(base, w=900, ledlen="600"), lang)
    c6 = [c for c in d6m["vodici"]["ovladani"]["casti"] if c["id"] == "led"][0]
    p12 = [m for m in c6["menu"] if m["text"] == txt1200]
    check(len(p12) == 1 and p12[0]["zakazano"] and p12[0]["duvod"] and "{" not in p12[0]["duvod"], f"3D menu {lang}: '{txt1200}' je na uzkem stole zakazano s duvodem ({p12 and p12[0]['duvod']})")
    check(all(not any(ord(ch) > 127 and lang == "en" and ch in "ěščřžýáíéúůťďň" for ch in m["text"]) for m in c6["menu"]), f"3D menu en: bez ceskych znaku")

# ---- data pro pocitadlo luxu ve verejne odpovedi
for sirka, lenv, typ, n in ((1500, "600", "led_600", 2), (1500, "1200", "led_1200", 1), (2000, "600", "led_600", 3)):
    st, dl = post(dict(base, w=sirka, ledlen=lenv))
    lt = dl["vodici"]["osvetleni"]["lights"]
    check(len(lt) == n and all(x["typ"] == typ and x["nominalLengthMm"] == float(lenv) for x in lt), f"lux {sirka}/{lenv}: {n} svitidel typu {typ} ({[(x['typ'], x['nominalLengthMm']) for x in lt]})")
    txt = json.dumps(dl["vodici"]["osvetleni"])
    check("4929" not in txt and "5359" not in txt and "LED600" not in txt and "LED1200" not in txt and "sku" not in txt.lower(), f"lux {sirka}/{lenv}: verejny payload nenese SKU ani cisla produktu")

# ---- staff API: ?led_delka=
r = staff.get("/api/stul/konfigurace?sirka=1500&led_delka=600&led_pocet=4")
j = r.get_json()
check(r.status_code == 200 and j["parametry"]["led_delka"] == 600.0 and sum(1 for d in j["dily"] if d["part_id"] == L600) == 2 and not j["problemy"], f"staff API ?led_delka=600: 2 svitidla product_5359 ({r.status_code})")
r = staff.get("/api/stul/konfigurace?sirka=1500")
check(r.status_code == 200 and r.get_json()["parametry"]["led_delka"] == 1200.0 and sum(1 for d in r.get_json()["dily"] if d["part_id"] == L1200) == 1, "staff API bez led_delka: 1 svitidlo 1200 (vychozi)")
r = staff.get("/api/stul/konfigurace?sirka=1500&led_delka=900")
check(r.status_code == 400, f"staff API ?led_delka=900 -> 400 ({r.status_code})")

# ---- GATE: verejnost vidi delku 600 az po aktivaci karty (pravidlo 54), zamestnanec vzdy
for stav, aktivni in (("karta 600 neaktivni", set()), ("karta 600 aktivni", {600})):
    nastav_led(aktivni)
    SH._RESOLVE_CACHE.clear()
    sc_v = anon.get(f"/api/shop/products/{PID}/configurator").get_json()
    sc_s = staff.get(f"/api/shop/products/{PID}/configurator").get_json()
    sl_v = {x["id"]: x for x in sc_v["slots"]}
    sl_s = {x["id"]: x for x in sc_s["slots"]}
    if aktivni:
        check([o["id"] for o in sl_v["ledlen"]["options"]] == ["600", "1200"] and "ledlen" in sc_v["default_selection"], f"GATE schema verejnost ({stav}): obe volby, ledlen ve vychozim vyberu")
    else:
        check("ledlen" not in sl_v and "ledlen" not in sc_v["default_selection"], f"GATE schema verejnost ({stav}): slot ledlen neni (ani ve vychozim vyberu) - verejne se nic nezmeni")
    check(set(sl_v) == set(sc_v["default_selection"]), f"GATE schema verejnost ({stav}): klice vychoziho vyberu == sloty")
    check([o["id"] for o in sl_s["ledlen"]["options"]] == ["600", "1200"] and "ledlen" in sc_s["default_selection"], f"GATE schema zamestnanec ({stav}): obe volby")
    st, dg = post(dict(sel, ledlen="600"))
    ocek = "600" if aktivni else "1200"
    check(st == 200 and dg["valid"] and dg["selection"]["ledlen"] == ocek, f"GATE verejnost ({stav}) ledlen=600: vybrano {ocek} ({dg.get('selection', {}).get('ledlen')})")
    check(len(led_dily(dict(sel, ledlen="600"))) >= 1, "GATE: generator mimo pozadavek bere vsechny delky")
    if not aktivni:
        check(dg["options"]["ledlen"] == {"hidden": True}, f"GATE verejnost ({stav}): options.ledlen = hidden ({dg['options']['ledlen']})")
    else:
        check(dg["options"]["ledlen"] == {}, f"GATE verejnost ({stav}): na 2000 mm se vejdou obe ({dg['options']['ledlen']})")
        st, dgu = post(dict(sel, w=900, ledlen="600"))
        check(set(dgu["options"]["ledlen"]) == {"1200"}, "GATE verejnost (karta aktivni): na 900 mm je 1200 zakazana")
    rs = staff.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": dict(sel, ledlen="600"), "lang": "cs", "staff": True})
    ds = rs.get_json()
    check(rs.status_code == 200 and ds["selection"]["ledlen"] == "600" and ds["options"]["ledlen"] == {}, f"GATE zamestnanec ({stav}): vidi 600 vzdy ({ds.get('selection', {}).get('ledlen')})")
    # nabidka kratsiho svitidla jen kdyz je delka v nabidce
    st, dv = post(dict(base if aktivni else {k: v for k, v in base.items() if k != "ledlen"}, w=900, led=False))
    sug = dv["options"]["led"]["on"].get("suggest") or {}
    check(("ledlen" in sug) == bool(aktivni), f"GATE verejnost ({stav}): nabidka kratsiho svitidla {'je' if aktivni else 'NENI'} ({sug})")
nastav_led({600})

# ---- led_delky_verejne: cteni karet z DB (simulace), chyba DB = jen vychozi
class FakeCur:
    def __init__(self, radky, chyba=False):
        self.radky, self.chyba = radky, chyba

    def execute(self, sql, params=()):
        if self.chyba:
            raise RuntimeError("test: DB nedostupna")
        assert sql.startswith("SELECT id, active, is_archived, glb_file, visible_in_scene FROM shop_products") and params == (5359,), (sql, params)

    def fetchall(self):
        return self.radky


class FakeConn:
    def __init__(self, radky, chyba=False):
        self.c = FakeCur(radky, chyba)

    def cursor(self):
        return self.c


orig_conn = SH.get_conn
try:
    for popis, radky, chyba, ocek in (("aktivni, ve scene, s GLB", [{"id": 5359, "active": 1, "is_archived": 0, "glb_file": "product_5359.glb", "visible_in_scene": 1}], False, {1200, 600}),
                                      ("neaktivni", [{"id": 5359, "active": 0, "is_archived": 0, "glb_file": "product_5359.glb", "visible_in_scene": 1}], False, {1200}),
                                      ("archivovana", [{"id": 5359, "active": 1, "is_archived": 1, "glb_file": "product_5359.glb", "visible_in_scene": 1}], False, {1200}),
                                      ("bez GLB", [{"id": 5359, "active": 1, "is_archived": 0, "glb_file": None, "visible_in_scene": 1}], False, {1200}),
                                      ("mimo scenu", [{"id": 5359, "active": 1, "is_archived": 0, "glb_file": "product_5359.glb", "visible_in_scene": 0}], False, {1200}),
                                      ("karta neexistuje", [], False, {1200}), ("chyba DB", [], True, {1200})):
        SH.get_conn = lambda radky=radky, chyba=chyba: FakeConn(radky, chyba)
        SH._LED_DELKY_CACHE.update(t=0.0, set=frozenset({1200}))
        check(SH.led_delky_verejne() == frozenset(ocek), f"led_delky_verejne ({popis}): {sorted(ocek)} ({sorted(SH.led_delky_verejne())})")
    SH.get_conn = lambda: FakeConn([{"id": 5359, "active": 1, "is_archived": 0, "glb_file": "x", "visible_in_scene": 1}])
    SH._LED_DELKY_CACHE.update(t=time.time(), set=frozenset({1200}))
    check(SH.led_delky_verejne() == frozenset({1200}), "led_delky_verejne: cache (30 s) se pred vyprsenim nevola do DB")
finally:
    SH.get_conn = orig_conn
    nastav_led({600})
with appmod.app.test_request_context("/"):
    nastav_led(set())
    pv, _ = SH.normalizuj(dict(sel, ledlen="600"), 30)
check(pv["led_delka"] == float(S.LED_DELKA_VYCHOZI), f"normalizuj v pozadavku verejnosti zahodi neaktivni delku ({pv['led_delka']})")
nastav_led(set())                                                           # i kdyz verejnost 600 nema, kod mimo pozadavek (skripty, testy) bere vsechny delky
pk, _ = SH.normalizuj(dict(sel, ledlen="600"), 30)
check(pk["led_delka"] == 600.0, f"normalizuj mimo pozadavek bere vsechny delky ({pk['led_delka']})")
nastav_led({600})

print()
if FAILS:
    print(f"CHYBA: {len(FAILS)} kontrol selhalo, {OK} OK")
    sys.exit(1)
print(f"{OK} kontrol OK")
