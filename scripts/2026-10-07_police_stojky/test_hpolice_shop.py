#!/usr/bin/env python3
"""Test HORNI POLICE MEZI ZADNIMI STOJKAMI ve VEREJNEM API stolu (api/stul_shop.py; bot8, fork 3, 2026-10-07; Robert: ruzne typy polic mezi zadni stojky).
SKUTECNE routy pres Flask test_client BEZ prihlaseni (+ jedno prihlaseni zamestnance). DB se jen CTE (ceny karet, stav karet); mapovani produktu a nabidka karet se podstrcuji do cache modulu
- nic se nezapisuje.

Hlida: schema (sloty upshelf, upshelftype, upshelfboard, upshelfpos, upshelfdepth: poradi, typ, skupina, zavislosti, texty cs / en / sk, SSE slot nema, desky podle systemu), resolve (vychozi
= beze zmeny, kazdy typ, cena = rozdil cen karet, price_delta, options, vyber desky podle typu, oriznuti vysky a hloubky, automaticke odebrani + oznameni cs / en / sk), token (klic K + bit),
shrnuti vyberu, odkaz na vyrobni list, 3D menu ve verejne podobe, nabidka pro verejnost podle AKTIVNICH karet (pravidlo 54) × zamestnanec, klic cache, fuzz.
Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_police_stojky/test_hpolice_shop.py
  (STUL_API_OVERRIDE=<adresar api> = kandidat; --setenv=STUL_API_OVERRIDE=... pri spusteni pres systemd-run)"""
import json
import math
import os
import random
import sys
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
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
try:
    import stul_hpolice as HP  # noqa: E402
except ImportError:
    print("CHYBA: modul api/stul_hpolice.py neexistuje (horni police neni nasazena; test patri ke kandidatu)")
    sys.exit(1)

SH.LIMIT_RESOLVE = SH.LIMIT_SCHEMA = SH.LIMIT_GLB = (10 ** 6, 60)         # test posila stovky pozadavku z jedne IP: limity (429) se vypnou (hlidaji je jine testy)
SH.HODINOVY_STROP.update(resolve=10 ** 6, schema=10 ** 6, glb=10 ** 6, model=10 ** 6)
S.nastav_pravidla({})                                                    # zive Robertovy pravidla (cena vyrezu...) test neovlivni
_stul_api.obnov_pravidla = lambda force=False: None

OK, FAILS = 0, []


PRVNI_CHYBA = bool(os.environ.get("HPOL_PRVNI_CHYBA"))                   # mutacni testy: skonci na prvni chybe


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")
        if PRVNI_CHYBA:
            sys.exit(1)


PID, PID_SSE, PID_40, PID_35 = 9876, 9879, 9877, 9878
VSECHNY_KARTY = frozenset(HP.vsechny_party())


def nastav_karty(karty):
    """Simulace aktivnich karet police (cache SH.karty_police_verejne): verejnost vidi jen `karty` (+ laminodesku 18 mm); nic se nezapisuje do DB."""
    SH._KARTY_POLICE_CACHE.update(t=time.time() + 1e7, set=frozenset(set(karty) | {"product_4933"}))
    SH._RESOLVE_CACHE.clear()


nastav_karty(VSECHNY_KARTY)                                              # zakladni testy bezi s uvolnenymi vsemi kartami; gating je zvlast (sekce GATE)
SH._DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset(S.PANEL_DELKY))
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PID): SH.RECEPT, str(PID_SSE): SH.RECEPT_SSE, str(PID_40): SH.RECEPT_40, str(PID_35): SH.RECEPT_35})
anon = appmod.app.test_client()


def post(sel, lang="cs", pid=PID, cli=None):
    r = (cli or anon).post("/api/shop/configurator/resolve", json={"product_id": pid, "selection": sel, "lang": lang})
    return r.status_code, r.get_json()


def schema(lang="cs", pid=PID, cli=None):
    return (cli or anon).get(f"/api/shop/products/{pid}/configurator?lang={lang}").get_json()


TYPY_PUB = ["flat", "frame", "groove", "lip", "dividers", "slope"]
POPISKY = {"cs": {"upshelf": "Police mezi zadními stojkami", "upshelftype": "Typ police", "upshelfboard": "Deska police", "upshelfpos": "Výška police nad deskou stolu", "upshelfdepth": "Hloubka police",
                  "flat": "Rovná, deska na rámu", "frame": "Rámová, bez desky", "groove": "Rám s deskou v drážce", "lip": "S lemem na přední hraně", "dividers": "Rám s přepážkami z překližky", "slope": "Šikmá, na boxy (s lemem vpředu)", "upshelftilt": "Sklon police (vpředu níž)"},
           "en": {"upshelf": "Shelf between the rear uprights", "upshelftype": "Shelf type", "upshelfboard": "Shelf board", "upshelfpos": "Shelf height above the worktop", "upshelfdepth": "Shelf depth",
                  "flat": "Flat, board on the frame", "frame": "Frame only, no board", "groove": "Frame with a board in the slot", "lip": "With a lip on the front edge", "dividers": "Frame with plywood dividers", "slope": "Sloped, for boxes (with a front lip)", "upshelftilt": "Shelf slope (lower at the front)"},
           "sk": {"upshelf": "Polica medzi zadnými stojkami", "upshelftype": "Typ police", "upshelfboard": "Doska police", "upshelfpos": "Výška police nad doskou stola", "upshelfdepth": "Hĺbka police",
                  "flat": "Rovná, doska na ráme", "frame": "Rámová, bez dosky", "groove": "Rám s doskou v drážke", "lip": "S lemom na prednej hrane", "dividers": "Rám s priehradkami z preglejky", "slope": "Šikmá, na boxy (s lemom vpredu)", "upshelftilt": "Sklon police (vpredu nižšie)"}}

# ---------------------------------------------------------------------------------------------------------------------
print("1) schema")
for lang in ("cs", "en", "sk"):
    sc = schema(lang)
    slots = {s["id"]: s for s in sc["slots"]}
    ids = [s["id"] for s in sc["slots"]]
    for k in ("upshelf", "upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt"):
        check(k in slots, f"schema {lang}: slot {k} je ve schematu")
    if "upshelf" not in slots:
        continue
    check(slots["upshelf"]["type"] == "toggle" and slots["upshelftype"]["type"] == "select" and slots["upshelfboard"]["type"] == "select"
          and slots["upshelfpos"]["type"] == "slider" and slots["upshelfdepth"]["type"] == "slider" and slots["upshelftilt"]["type"] == "slider", f"schema {lang}: typy slotu ({[slots[k]['type'] for k in ('upshelf', 'upshelftype', 'upshelfboard', 'upshelfpos', 'upshelfdepth', 'upshelftilt')]})")
    check(all(slots[k]["group"] == "g_extras" for k in ("upshelf", "upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt")), f"schema {lang}: vsechny sloty ve skupine g_extras")
    check(ids.index("upshelf") == ids.index("bracelen") + 1 and ids[ids.index("upshelf"):ids.index("upshelf") + 6] == ["upshelf", "upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt"], f"schema {lang}: poradi sloty za bracelen")
    for k in ("upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt"):
        check(slots[k].get("depends_on") == ["posts", "upshelf"], f"schema {lang}: {k} zavisi na posts + upshelf ({slots[k].get('depends_on')})")
    check(slots["upshelf"].get("depends_on") in (None, []), f"schema {lang}: samotny prepinac nezavisi na dalsim slotu ({slots['upshelf'].get('depends_on')})")
    for k in ("upshelf", "upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt"):
        check(slots[k]["label"] == POPISKY[lang][k], f"schema {lang}: popisek {k} = {POPISKY[lang][k]!r} ({slots[k]['label']!r})")
    check([o["id"] for o in slots["upshelftype"]["options"]] == TYPY_PUB and [o["label"] for o in slots["upshelftype"]["options"]] == [POPISKY[lang][t] for t in TYPY_PUB], f"schema {lang}: volby typu ({[o['id'] for o in slots['upshelftype']['options']]})")
    check(slots["upshelftype"]["help"] and "{" not in slots["upshelftype"]["help"] and len(slots["upshelftype"]["help"]) > 60, f"schema {lang}: napoveda typu police")
    check([o["id"] for o in slots["upshelfboard"]["options"]] == ["lam18", "lam12", "mdf8"], f"schema {lang}: desky systemu 30: 18, 12, MDF 8 ({[o['id'] for o in slots['upshelfboard']['options']]})")
    check((slots["upshelfpos"]["slider"]["min"], slots["upshelfpos"]["slider"]["max"], slots["upshelfpos"]["slider"]["step"], slots["upshelfpos"]["slider"]["unit"]) == (100, 1500, 10, "mm"), f"schema {lang}: posuvnik vysky 100..1500 po 10 mm ({slots['upshelfpos']['slider']})")
    check((slots["upshelfdepth"]["slider"]["min"], slots["upshelfdepth"]["slider"]["max"], slots["upshelfdepth"]["slider"]["step"]) == (150, 600, 10), f"schema {lang}: posuvnik hloubky 150..600 po 10 mm")
    check((slots["upshelftilt"]["slider"]["min"], slots["upshelftilt"]["slider"]["max"], slots["upshelftilt"]["slider"]["step"], slots["upshelftilt"]["slider"]["unit"]) == (5, 30, 5, "°"), f"schema {lang}: posuvnik sklonu 5..30 po 5 st. ({slots['upshelftilt']['slider']})")
    dflt = sc["default_selection"]
    check(dflt["upshelf"] is False and dflt["upshelftype"] == "flat" and dflt["upshelfboard"] == "lam18" and dflt["upshelfpos"] is None and dflt["upshelfdepth"] == 300 and dflt["upshelftilt"] == 15, f"schema {lang}: vychozi vyber (police vypnuta, rovna, lam18, vyska auto, hloubka 300): { {k: dflt.get(k) for k in slots if k.startswith('upshelf')} }")
    check(set(dflt) == set(slots), f"schema {lang}: default_selection ma klic pro kazdy slot")
# desky podle systemu
for pid, sy, desky in ((PID_35, 35, ["lam18", "lam12", "mdf8"]), (PID_40, 40, ["lam18", "pr10"])):
    sl = {s["id"]: s for s in schema("cs", pid)["slots"]}
    check([o["id"] for o in sl["upshelfboard"]["options"]] == desky, f"schema system {sy}: desky {desky} ({[o['id'] for o in sl['upshelfboard']['options']]})")
    check([o["label"] for o in sl["upshelfboard"]["options"]][-1] == {"mdf8": "MDF 8 mm (do drážky)", "pr10": "Překližka 10 mm (do drážky)"}[desky[-1]], f"schema system {sy}: popisek desky do drazky")
sse = {s["id"] for s in schema("cs", PID_SSE)["slots"]}
check(not [k for k in sse if k.startswith("upshelf")], f"schema SSE (system 41): zadny slot police ({[k for k in sse if k.startswith('upshelf')]})")
check(schema("cs")["rules_version"] == G.RULES_VERSION, "rules_version ve schematu")
base = schema("cs")["default_selection"]

# ---------------------------------------------------------------------------------------------------------------------
print("2) vychozi vyber: police vypnuta, nic se nezmenilo")
st, d0 = post(base)
check(st == 200 and d0["valid"] and d0["selection"]["upshelf"] is False and not d0["errors"], f"vychozi vyber platny, police vypnuta ({st})")
check(d0["selection"] == base, "normalizovany vyber = vychozi")
check(d0["options"]["upshelf"]["on"]["disabled"] is False and d0["options"]["upshelf"]["on"]["price_delta"] > 0, f"options.upshelf.on: lze zapnout, priplatek > 0 ({d0['options']['upshelf']})")
check(d0["options"]["upshelfpos"] == {"min": 0, "max": 0} and d0["options"]["upshelfdepth"] == {"min": 0, "max": 0} and d0["options"]["upshelftype"] == {} and set(d0["options"]) >= set(d0["selection"]), f"vypnuta police: posuvniky zamcene, typy bez omezeni, options pro kazdy slot ({d0['options']['upshelfpos']})")
p0, _ = SH.normalizuj(base, 30)
tok = SH._zabal(S.sestav_stul(**p0)["parametry"])
check("K" not in tok and not (tok.get("t", 0) >> 10) & 1, f"token vychoziho stolu nema police: {tok}")
check(G.kanonicky_hash(S.sestav_stul(**p0)["parametry"]) == d0["hash"], "hash vychoziho stolu = hash generatoru bez police")

# ---------------------------------------------------------------------------------------------------------------------
print("3) kazdy typ police: platne, options, cena = cena karet, price_delta")
ctx = _stul_api._ctx_ceny()
KARTA_CENA = {pid: v["price_czk"] for pid, v in ctx["parts"].items() if pid in HP.vsechny_party() and v.get("price_czk") is not None}
check(all(pid in KARTA_CENA for pid in ("product_4933", "product_3939", "product_3539", "product_3045", "product_3207")), f"karty desek a uhelniku maji v katalogu cenu ({sorted(KARTA_CENA)})")
cena_bez = d0["price"]["net"]
for lang in ("cs", "en", "sk"):
    st, dm = post(dict(base, upshelf=True), lang)
    check(dm["selection"]["upshelf"] is True and dm["valid"] and not dm["errors"], f"[{lang}] zapnuta police: platna")
ceny = {}
for typ in TYPY_PUB:
    sel = dict(base, upshelf=True, upshelftype=typ)
    st, d = post(sel)
    check(st == 200 and d["valid"] and not d["errors"] and d["selection"]["upshelf"] and d["selection"]["upshelftype"] == typ, f"typ {typ}: platne ({st}, {d.get('errors')})")
    if not d.get("valid"):
        continue
    ceny[typ] = d["price"]["net"]
    check(d["price"]["net"] > cena_bez, f"typ {typ}: cena s policí {d['price']['net']} > bez police {cena_bez}")
    delta0 = d0["options"]["upshelf"]["on"]["price_delta"]
    if typ == "flat":
        check(abs((d["price"]["net"] - cena_bez) - delta0) < 1.01, f"typ flat: options.upshelf.on.price_delta {delta0} == rozdil cen {d['price']['net'] - cena_bez}")
    op = d["options"]
    check({"upshelf", "upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth"} <= set(op) and set(op) >= set(d["selection"]), f"typ {typ}: options pro vsechny sloty")
    pos, dep = op["upshelfpos"], op["upshelfdepth"]
    check(pos["min"] < pos["max"] and pos["min"] % 10 == 0 and pos["max"] % 10 == 0 and pos["auto"] is True and pos["fits"] is True and pos["min"] <= pos["value"] + 9.99, f"typ {typ}: options.upshelfpos {pos}")
    check(dep["min"] == (150 if typ in ("flat", "frame", "lip") else dep["min"]) and dep["max"] == 600 and dep["value"] == 300 and dep["min"] <= 300, f"typ {typ}: options.upshelfdepth {dep}")
    ob = op["upshelfboard"]
    if typ == "frame":
        check(set(ob) == {"lam18", "lam12", "mdf8"} and all(v["disabled"] and v["reason"] == "Rámová police nemá desku." for v in ob.values()), f"typ frame: vsechny desky zakazane ({ob})")
    elif typ in ("groove", "dividers"):
        check(set(ob) == {"lam18", "lam12"} and all(v["disabled"] and "MDF 8 mm" in v["reason"] for v in ob.values()) and d["selection"]["upshelfboard"] == "mdf8", f"typ {typ}: do drazky jen MDF 8 ({ob}, vybrano {d['selection']['upshelfboard']})")
    else:
        check(set(ob) == {"mdf8"} and ob["mdf8"]["disabled"] and "drážk" in ob["mdf8"]["reason"] and d["selection"]["upshelfboard"] == "lam18", f"typ {typ}: MDF zakazan (jde jen do drazky) ({ob})")
check(len(set(ceny.values())) >= 4, f"ruzne typy = ruzne ceny ({ceny})")
check(ceny["frame"] < ceny["flat"], f"ramova police bez desky je levnejsi nez rovna ({ceny['frame']} < {ceny['flat']})")
# vyber desky: lam12, mdf8 u rovne; neplatne se opravi
for typ, deska, ocek in (("flat", "lam12", "lam12"), ("flat", "mdf8", "lam18"), ("lip", "lam12", "lam12"), ("lip", "xxx", "lam18"), ("groove", "lam18", "mdf8"), ("frame", "lam12", "lam18"), ("dividers", "lam12", "mdf8")):
    st, d = post(dict(base, upshelf=True, upshelftype=typ, upshelfboard=deska))
    check(st == 200 and d["selection"]["upshelfboard"] == ocek, f"typ {typ} + deska {deska}: vybrano {ocek} ({d.get('selection', {}).get('upshelfboard')})")
for deska, ocek in (("lam18", "lam18"), ("pr10", "lam18")):
    st, d = post(dict(schema("cs", PID_40)["default_selection"], upshelf=True, upshelftype="flat", upshelfboard=deska), pid=PID_40)
    check(d["selection"]["upshelfboard"] == ocek, f"system 40: deska {deska} u rovne police -> {ocek}")
st, d = post(dict(schema("cs", PID_40)["default_selection"], upshelf=True, upshelftype="groove", upshelfboard="lam18"), pid=PID_40)
check(d["selection"]["upshelfboard"] == "pr10" and set(d["options"]["upshelfboard"]) == {"lam18"}, f"system 40: drazkova police ma PR10 ({d['selection']['upshelfboard']}, {sorted(d['options']['upshelfboard'])})")
# nezname hodnoty
for spatna in ("sikma", None, 5, [], {}, True, "", "FLAT"):
    st, d = post(dict(base, upshelf=True, upshelftype=spatna))
    check(st == 200 and d["selection"]["upshelftype"] == "flat", f"neplatny typ {spatna!r} = rovna ({st}, {d.get('selection', {}).get('upshelftype')})")
for spatna in ("abc", None, 1e99, -5, [], {}, True, float("nan")):
    st, d = post(dict(base, upshelf=True, upshelfdepth=spatna))
    check(st == 200 and 150 <= d["selection"]["upshelfdepth"] <= 600, f"neplatna hloubka {spatna!r} se orizne / vrati do rozsahu ({st}, {d.get('selection', {}).get('upshelfdepth')})")

# ---------------------------------------------------------------------------------------------------------------------
print("3b) sklon sikme police (slot upshelftilt)")
for sk in (5, 15, 25, 30):
    st, d = post(dict(base, upshelf=True, upshelftype="slope", upshelftilt=sk))
    check(st == 200 and d["valid"] and d["selection"]["upshelftype"] == "slope" and d["selection"]["upshelftilt"] == sk and d["options"]["upshelftilt"] == {"min": 5, "max": 30, "value": sk}, f"sklon {sk}: platny, vybrany, options.upshelftilt ({d.get('options', {}).get('upshelftilt')})")
for zad, ocek in ((22, (20, 25)), (100, (30,)), (-5, (5,)), ("abc", (15,)), (None, (15,))):
    st, d = post(dict(base, upshelf=True, upshelftype="slope", upshelftilt=zad))
    check(st == 200 and d["selection"]["upshelftilt"] in ocek, f"sklon {zad!r} se orizne / zaokrouhli na {ocek} ({d.get('selection', {}).get('upshelftilt')})")
p_t, _ = SH.normalizuj(dict(base, upshelf=True, upshelftype="slope", upshelftilt=25), 30)
r_t = S.sestav_stul(**p_t)
pp_t, err_t = SH.over_model(SH.podepis_model(r_t["parametry"]))
check(err_t is None and pp_t["hpolice_sklon"] == 25.0 and SH._zabal(r_t["parametry"])["R"][4] == 25.0 and S.sestav_stul(**pp_t)["parametry"]["hpolice_sklon"] == 25.0, f"token: sklon 25 prezije podpis a rozbaleni ({err_t}, {pp_t and pp_t.get('hpolice_sklon')})")
h15 = post(dict(base, upshelf=True, upshelftype="slope", upshelftilt=15))[1]["hash"]
h25 = post(dict(base, upshelf=True, upshelftype="slope", upshelftilt=25))[1]["hash"]
check(h15 != h25, "ruzny sklon sikme police = ruzny hash")
for typ in ("flat", "lip", "frame", "dividers"):
    d1 = post(dict(base, upshelf=True, upshelftype=typ, upshelftilt=25))[1]
    d0 = post(dict(base, upshelf=True, upshelftype=typ))[1]
    check(d1["hash"] == d0["hash"] and d1["selection"]["upshelftilt"] == 15 and d1["options"]["upshelftilt"] == {"min": 15, "max": 15}, f"typ {typ}: sklon se ignoruje (hash, selection 15, posuvnik zamceny) ({d1['selection']['upshelftilt']}, {d1['options']['upshelftilt']})")
d0 = post(dict(base, upshelf=False, upshelftype="slope", upshelftilt=25))[1]
check(d0["hash"] == post(base)[1]["hash"] and d0["selection"]["upshelftilt"] == 15, "vypnuta police: sklon se zahodi, hash = bez police")
for lang, txt in (("cs", "střední zadní nohou"), ("en", "rear centre leg"), ("sk", "strednou zadnou nohou")):
    st, d2 = post(dict(base, w=2100, midsupport="legs", panels=False, socket=False, upshelf=True, upshelftype="flat"), lang)
    o_s = d2["options"]["upshelftype"].get("slope")
    check(d2["selection"]["upshelf"] and o_s and o_s["disabled"] and txt in o_s["reason"], f"[{lang}] stul se strednimi zadnimi nohami: sikma zakazana s duvodem '{txt}' ({o_s})")
st, d2 = post(dict(base, w=2100, midsupport="legs", panels=False, socket=False, upshelf=True, upshelftype="slope"))
check(d2["selection"]["upshelf"] is False and any(n["slot"] == "upshelf" for n in d2["notices"]), "stul se strednimi zadnimi nohami: zvolena sikma police se odebere s oznamenim")
st, d3 = post(dict(base, w=2100, midsupport="frame", upshelf=True, upshelftype="slope", panels=False, socket=False))
check(d3["selection"]["upshelf"] and d3["valid"], f"vestaveny ram (jeden usek): sikma police jde ({d3['selection']['upshelf']}, {d3['valid']})")
for lang in ("cs", "en", "sk"):
    sou = {x["id"]: x for x in SH._souhrn_voleb(SH.normalizuj(dict(base, upshelf=True, upshelftype="slope", upshelftilt=25), 30)[1], lang, 30)}
    sou2 = {x["id"] for x in SH._souhrn_voleb(SH.normalizuj(dict(base, upshelf=True, upshelftype="lip", upshelftilt=25), 30)[1], lang, 30)}
    check(sou.get("upshelftilt", {}).get("value") == "25 °" and "upshelftilt" not in sou2, f"shrnuti {lang}: sklon '25 °' jen u sikme police ({sou.get('upshelftilt')}, {'upshelftilt' in sou2})")
st, dk = post(dict(base, upshelf=True, upshelftype="slope", upshelftilt=25))
qs_s = dict(urllib.parse.parse_qsl(SH._staff_blok(dk["hash"])["vyrobni_list_url"].split("?", 1)[1]))
st, dk2 = post(dict(base, upshelf=True, upshelftype="lip", upshelftilt=25))
qs_l = dict(urllib.parse.parse_qsl(SH._staff_blok(dk2["hash"])["vyrobni_list_url"].split("?", 1)[1]))
check(qs_s.get("hpolice_sklon") == "25.0" and "hpolice_sklon" not in qs_l and S.parametry_z_dotazu(qs_s)["hpolice_sklon"] == 25.0, f"vyrobni list: hpolice_sklon jen u sikme police ({qs_s.get('hpolice_sklon')}, {qs_l.get('hpolice_sklon')})")

print("4) cena = soucet cen karet (nezavisly vypocet z kusovniku)")
for typ, deska in (("flat", "lam18"), ("frame", "lam18"), ("groove", "lam18"), ("lip", "lam18"), ("dividers", "lam18"), ("slope", "lam18"), ("flat", "lam12")):
    if deska == "lam12" and "product_5360" not in ctx["parts"] and HP.LAM12_PART not in ctx["parts"]:
        continue                                                         # karta desky 12 mm jeste neexistuje (zaloz_kartu_lam12.py)
    p, _ = SH.normalizuj(dict(base, upshelf=True, upshelftype=typ, upshelfboard=deska), 30)
    gen = S.sestav_stul(**p)
    kus = _stul_api.cena_konfigurace(gen["dily"])["kusovnik"]["radky"]
    gen0 = S.sestav_stul(**SH.normalizuj(base, 30)[0])
    kus0 = _stul_api.cena_konfigurace(gen0["dily"])["kusovnik"]["radky"]
    n1 = {x["nazev"]: x for x in kus}
    n0 = {x["nazev"]: x for x in kus0}
    nove = [x for k, x in n1.items() if k not in n0 or n0[k]["mnozstvi"] != x["mnozstvi"] or abs(n0[k]["cena_ks"] - x["cena_ks"]) > 1e-9]
    check(len(nove) >= 1, f"{typ}/{deska}: kusovnik obsahuje nove / zmenene radky ({[x['nazev'] for x in nove][:5]})")
    desky_d = [d for d in gen["dily"] if d.get("deska_id", "").startswith("hpol") and d["part_id"] in HP.DESKA_PARTY]
    for part in {d["part_id"] for d in desky_d}:
        plocha = sum(float(d["scale"][0]) * float(d["scale"][1]) for d in desky_d if d["part_id"] == part)
        cena_m2 = ctx["parts"][part]["price_czk"]
        if part == "product_4933":
            plocha += sum(float(d["scale"][0]) * float(d["scale"][1]) for d in gen0["dily"] if d["part_id"] == part and not d.get("deska_kus"))
        radky = [x for x in kus if ctx["parts"][part]["name"] in x["nazev"] or (ctx["parts"][part].get("sku") or "###") in x["nazev"]]
        check(len(radky) >= 1, f"{typ}/{deska}: kusovnik ma radek karty {part}")
    # prisl: uhelniky
    n_uh = sum(1 for d in gen["dily"] if d["part_id"] in (HP.UHELNIK[30],) and str(d.get("part_id")) == "product_3045")
    if n_uh:
        r_uh = [x for x in kus if "Úhelníková spojka 30x30" in x["nazev"]]
        check(len(r_uh) == 1 and r_uh[0]["mnozstvi"] == n_uh and abs(r_uh[0]["cena_ks"] - ctx["parts"]["product_3045"]["price_czk"]) <= 0.51, f"{typ}/{deska}: {n_uh} x uhelnik 30x30 za cenu karty vcetne koeficientu sceny, zaokrouhleno na Kc ({r_uh and (r_uh[0]['mnozstvi'], r_uh[0]['cena_ks'])} vs {ctx['parts']['product_3045']['price_czk']})")
        fix = [x for x in kus if "Šroub imbus s válcovou hlavou M6x12" in x["nazev"] or "Ozubená matice M6 - drážka 8" in x["nazev"]]
        check(len(fix) >= 2, f"{typ}/{deska}: spojovaci material k uhelnikum je v kusovniku (sroub M6x12 a matice) ({[x['nazev'] for x in fix]})")
    # cena z kusovniku: souhrn ceny
    c = _stul_api.cena_konfigurace(gen["dily"])
    check(c is not None and abs(sum(x["celkem"] for x in kus) - c["kusovnik"].get("soucet_dilu", sum(x["celkem"] for x in kus))) < 1.0, f"{typ}/{deska}: soucet radku kusovniku sedi")

# ---------------------------------------------------------------------------------------------------------------------
print("4b) cena sikme police: konzoly #3323 v kusovniku")
p_s, _ = SH.normalizuj(dict(base, upshelf=True, upshelftype="slope"), 30)
kus_s = _stul_api.cena_konfigurace(S.sestav_stul(**p_s)["dily"])["kusovnik"]["radky"]
r_k = [x for x in kus_s if "Úhlová naklápěcí konzole" in x["nazev"]]
check(len(r_k) == 1 and r_k[0]["mnozstvi"] == 2 and abs(r_k[0]["cena_ks"] - ctx["parts"]["product_3323"]["price_czk"]) <= 0.51, f"sikma police: 2 x naklapeci konzola za cenu karty ({r_k and (r_k[0]['mnozstvi'], r_k[0]['cena_ks'])} vs {ctx['parts']['product_3323']['price_czk']})")
cs_l = _stul_api.cena_konfigurace(S.sestav_stul(**SH.normalizuj(dict(base, upshelf=True, upshelftype="lip"), 30)[0])["dily"])
cs_s = _stul_api.cena_konfigurace(S.sestav_stul(**p_s)["dily"])
check(cs_s["souhrn"]["joint_count"] == cs_l["souhrn"]["joint_count"] and cs_s["souhrn"]["joint_czk"] == cs_l["souhrn"]["joint_czk"], f"sikma police: prace za spoje jako u police s lemem (2 x stojka - bok misto 2 x pricka - stojka) ({cs_s['souhrn']['joint_count']}, {cs_l['souhrn']['joint_count']})")
ucet_s = {x["nazev"]: x["mnozstvi"] for x in cs_s["kusovnik"]["radky"]}
ucet_l = {x["nazev"]: x["mnozstvi"] for x in cs_l["kusovnik"]["radky"]}
check(cs_s["bez_dph"] > cs_l["bez_dph"] and ucet_s.get("Rohová spojka 30 x 30 [2.2.001.08.3030.33] (produkt)") == ucet_l.get("Rohová spojka 30 x 30 [2.2.001.08.3030.33] (produkt)", 0) - 2, f"sikma police je o konzoly + sroubky drazsi nez police s lemem, o 2 rohove spojky mene ({cs_s['bez_dph']} > {cs_l['bez_dph']})")

print("5) vyska a hloubka: meze, orezani, automaticka vyska")
st, dv = post(dict(base, upshelf=True))
pos = dv["options"]["upshelfpos"]
dep = dv["options"]["upshelfdepth"]
check(dv["selection"]["upshelfpos"] is None, "automaticka vyska: selection.upshelfpos = null")
sel = dict(base, upshelf=True, upshelfpos=pos["max"])
st, dmax = post(sel)
check(dmax["valid"] and dmax["selection"]["upshelfpos"] == float(pos["max"]) and dmax["options"]["upshelfpos"]["auto"] is False, f"nejvyssi vyska {pos['max']}: platna, vybrana ({dmax['selection']['upshelfpos']})")
st, dnad = post(dict(base, upshelf=True, upshelfpos=pos["max"] + 300))
check(dnad["valid"] and dnad["selection"]["upshelfpos"] == float(pos["max"]) or dnad["selection"]["upshelfpos"] <= pos["max"] + 10, f"vyska nad nejvyssi se orizne ({dnad['selection']['upshelfpos']} vs {pos['max']})")
st, dnic = post(dict(base, upshelf=True, upshelfpos=100))
check(dnic["valid"] and dnic["selection"]["upshelfpos"] >= dv["options"]["upshelfpos"]["min"] - 0.01, f"vyska pod nejnizsi se zvedne ({dnic['selection']['upshelfpos']} vs {dv['options']['upshelfpos']['min']})")
for h in (300, 450, 600):
    st, dh = post(dict(base, upshelf=True, upshelfdepth=h))
    check(dh["selection"]["upshelfdepth"] == h and dh["options"]["upshelfdepth"]["value"] == h and dh["valid"], f"hloubka {h}: platna a vybrana ({dh['selection']['upshelfdepth']})")
st, dh2 = post(dict(base, upshelf=True, upshelfdepth=155))
check(dh2["selection"]["upshelfdepth"] in (150, 160), f"hloubka 155 se zaokrouhli na krok 10 ({dh2['selection']['upshelfdepth']})")
st, dg = post(dict(base, upshelf=True, upshelftype="groove", upshelfdepth=150))
check(dg["valid"] and dg["selection"]["upshelfdepth"] >= dg["options"]["upshelfdepth"]["min"] > 150, f"drazkova police: hloubka 150 se zvedne na nejmensi moznou ({dg['selection']['upshelfdepth']}, min {dg['options']['upshelfdepth']['min']})")
st, d3 = post(dict(base, upshelf=True, upshelfpos=pos["min"] + 100, upshelftype="dividers"))
check(d3["valid"] and d3["selection"]["upshelfpos"] == float(pos["min"] + 100), f"zadana vyska u prepazek: {d3['selection']['upshelfpos']}")
# vypnuti: vyska a hloubka se zahodi
st, dvyp = post(dict(base, upshelf=False, upshelfpos=500, upshelfdepth=500, upshelftype="lip", upshelfboard="lam12"))
check(dvyp["selection"]["upshelfpos"] is None and dvyp["selection"]["upshelfdepth"] == 300 and dvyp["selection"]["upshelftype"] == "flat" and dvyp["hash"] == d0["hash"], f"vypnuta police: ostatni volby se zahodi, hash = bez police ({dvyp['selection']['upshelfpos']}, {dvyp['selection']['upshelfdepth']})")

# ---------------------------------------------------------------------------------------------------------------------
print("6) nevejde se: automaticke odebrani, oznameni cs / en / sk, nabidka")
for lang, txt in (("cs", "Automaticky odebráno"), ("en", "Automatically removed"), ("sk", "Automaticky odstránené")):
    st, dn = post(dict(base, upshelf=True, posth=400), lang)
    nt = [n for n in dn["notices"] if n["slot"] == "upshelf"]
    check(dn["valid"] and dn["selection"]["upshelf"] is False and len(nt) == 1 and txt in nt[0]["message"] and "{" not in nt[0]["message"], f"[{lang}] nizke stojky: police odebrana s oznamenim ({[n['message'][:80] for n in nt]})")
st, dn = post(dict(base, upshelf=True, panelcount=2, posth=700))
check(dn["valid"] and not dn["errors"], f"dva panely + police + nizke stojky: stul zustane platny (police {dn['selection']['upshelf']}, panely {dn['selection']['panelcount']})")
# zapnuti police, ktera se nevejde: options.upshelf.on je zakazan s duvodem a nabidkou zvyseni stojek (bez panelu; nejnizsi stojky, na ktere se police vejde, urci generator)
def nejnizsi_stojky(typ="rovna"):
    for sv in range(200, 900, 10):
        if S.sestav_stul(stojky_vyska=float(sv), panely=False, elektrozlab=False, hpolice=True, hpolice_typ=typ)["parametry"]["hpolice"]:
            return sv
    return None


nej = nejnizsi_stojky("rovna")
check(nej is not None and nej > 200, f"nejnizsi stojky pro rovnou polici bez panelu: {nej}")
st, doff = post(dict(base, panels=False, socket=False, posth=nej - 10))
on = doff["options"]["upshelf"]["on"]
check(on["disabled"] is True and on["reason"] and "stojky" in on["reason"].lower(), f"stojky {nej - 10}: zapnuti police zakazano s duvodem ({on})")
sg = on.get("suggest")
check(sg is not None and sg.get("posth") == nej and on.get("suggest_label") and str(nej) in on["suggest_label"], f"stojky {nej - 10}: nabidka zvyseni stojek na {nej} ({sg}, {on.get('suggest_label')})")
if sg and "posth" in sg:
    st, dz = post(dict(base, panels=False, socket=False, posth=sg["posth"], upshelf=True, upshelftype="flat"))
    check(dz["selection"]["upshelf"] is True and dz["valid"], f"po nabidnutem zvyseni stojek ({sg['posth']}) se police vejde")
for lang, txt in (("en", "Raise the rear uprights"), ("sk", "Zvýšiť zadné stojky")):
    on_l = post(dict(base, panels=False, socket=False, posth=nej - 10), lang)[1]["options"]["upshelf"]["on"]
    check(txt in (on_l.get("suggest_label") or ""), f"[{lang}] stojky {nej - 10}: popisek nabidky '{txt}...' ({on_l.get('suggest_label')})")
# bez zadnich stojek
st, dp = post(dict(base, posts=False, panels=False, led=False, socket=False, upshelf=True))
check(dp["selection"]["upshelf"] is False and dp["options"]["upshelf"]["on"]["disabled"] and dp["options"]["upshelf"]["on"]["reason"], f"bez zadnich stojek je police zakazana ({dp['options']['upshelf']['on']})")
# nevejde se typ, jiny ano: stojky, na ktere se vejde rovna police, ale ne prepazky (240 mm navic) ani lem (40 mm navic)
nej_r = nejnizsi_stojky("rovna")
st, dt = post(dict(base, panels=False, socket=False, upshelf=True, upshelftype="flat", posth=nej_r))
ot = dt["options"]["upshelftype"]
ocek_ne = {t_ for t_ in TYPY_PUB if nejnizsi_stojky(HP.TYP_ID[t_]) > nej_r}
check(dt["valid"] and dt["selection"]["upshelf"] and "dividers" in ocek_ne and set(ot) == ocek_ne, f"stojky {nej_r} (rovna se vejde): zakazane typy {sorted(ocek_ne)} ({sorted(ot)})")
check(all(v["disabled"] and "nevejde" in v["reason"] and "{" not in v["reason"] for v in ot.values()), f"stojky {nej_r}: zakazane typy maji duvod 'nevejde' ({ {k: v['reason'][:50] for k, v in ot.items()} })")
for lang, txt in (("en", "does not fit"), ("sk", "nezmestí")):
    ot_l = post(dict(base, panels=False, socket=False, upshelf=True, upshelftype="flat", posth=nej_r), lang)[1]["options"]["upshelftype"]
    check(ot_l and all(txt in v["reason"] for v in ot_l.values()), f"[{lang}] stojky {nej_r}: duvod zakazaneho typu prelozen ({[v['reason'][:50] for v in ot_l.values()][:1]})")
st, dt2 = post(dict(base, panels=False, socket=False, upshelf=True, upshelftype="dividers", posth=nej_r))
check(dt2["selection"]["upshelf"] is False and any(n["slot"] == "upshelf" for n in dt2["notices"]), f"stojky {nej_r}: zvolene prepazky se nevejdou -> police odebrana s oznamenim")

# ---------------------------------------------------------------------------------------------------------------------
print("7) token, model a vyrobni list")
for typ in TYPY_PUB:
    for sy, pid in ((30, PID), (40, PID_40)):
        dflt = schema("cs", pid)["default_selection"]
        p1, _ = SH.normalizuj(dict(dflt, upshelf=True, upshelftype=typ, upshelfdepth=400, upshelfpos=None), sy)
        r1 = S.sestav_stul(**p1)
        tk = SH._zabal(r1["parametry"])
        check(tk.get("R", [None])[0] == p1["hpolice_typ"] and (tk.get("t", 0) >> 10) & 1 and len(tk["R"]) == (5 if typ == "slope" else 4), f"token {typ}/s{sy}: klic R (u sikme i sklon) a bit 10 ({tk})")
        pp, chyba = SH.over_model(SH.podepis_model(r1["parametry"]))
        check(chyba is None and pp["hpolice"] and pp["hpolice_typ"] == p1["hpolice_typ"] and pp["hpolice_deska"] == r1["parametry"]["hpolice_deska"] and pp["hpolice_hloubka"] == r1["parametry"]["hpolice_hloubka"]
              and pp["hpolice_vyska"] == r1["parametry"]["hpolice_vyska"], f"token {typ}/s{sy}: police prezije podpis a rozbaleni ({chyba}, {pp and {k: v for k, v in pp.items() if k.startswith('hpolice')}})")
        check(typ != "slope" or pp["hpolice_sklon"] == r1["parametry"]["hpolice_sklon"] == 15.0, f"token {typ}/s{sy}: sklon sikme police prezije podpis")
        r2 = S.sestav_stul(**S._norm_parametry(pp)) if False else S.sestav_stul(**pp)
        check(G.kanonicky_hash(r2["parametry"]) == G.kanonicky_hash(r1["parametry"]), f"token {typ}/s{sy}: rozbaleny token da stejny hash")
        h_model, data = G.model_pro_parametry(r1["parametry"])
        check(len(data) > 100000 and h_model == G.kanonicky_hash(r1["parametry"]), f"model GLB {typ}/s{sy} se slozi ({len(data)} B)")
p1, _ = SH.normalizuj(dict(base, upshelf=True, upshelfpos=620), 30)
tk = SH._zabal(S.sestav_stul(**p1)["parametry"])
check(tk["R"][2] == 620.0, f"token: zadana vyska je v klici R ({tk['R']})")
p1, _ = SH.normalizuj(dict(base, upshelf=True), 30)
tk = SH._zabal(S.sestav_stul(**p1)["parametry"])
check(tk["R"][2] is None, f"token: automaticka vyska je null ({tk['R']})")
# starsi token bez K
pp0, _ = SH.over_model(SH.podepis_model(S.sestav_stul(**SH.normalizuj(base, 30)[0])["parametry"]))
check(not pp0.get("hpolice") and S._norm_parametry(pp0)["hpolice"] is False, "token: starsi token bez klice K = bez police")
# odkaz na vyrobni list (staff blok)
st, dk = post(dict(base, upshelf=True, upshelftype="lip", upshelfboard="lam12" if HP.LAM12_PART in ctx["parts"] else "lam18", upshelfdepth=350, upshelfpos=640))
SH._STAV_PODLE_HASHE[dk["hash"]]
blok = SH._staff_blok(dk["hash"])
qs = dict(urllib.parse.parse_qsl(blok["vyrobni_list_url"].split("?", 1)[1]))
check(qs.get("hpolice") in ("True", "true", "1") and qs.get("hpolice_typ") == "lem" and qs.get("hpolice_hloubka") == "350.0" and qs.get("hpolice_vyska") == "640.0", f"vyrobni list: dotaz nese parametry police ({ {k: v for k, v in qs.items() if k.startswith('hpolice')} })")
pq = S.parametry_z_dotazu(qs)
check(pq["hpolice"] is True and pq["hpolice_typ"] == "lem" and pq["hpolice_hloubka"] == 350.0 and pq["hpolice_vyska"] == 640.0, "vyrobni list: dotaz se da vratit na parametry generatoru")
blok0 = SH._staff_blok(post(base)[1]["hash"])
check("hpolice" not in blok0["vyrobni_list_url"], "vyrobni list bez police: v odkazu zadny parametr police (odkazy beze zmeny)")

# ---------------------------------------------------------------------------------------------------------------------
print("8) shrnuti vyberu (doklad / nabidka) a neutralni kusovnik")
for lang in ("cs", "en", "sk"):
    sou = SH._souhrn_voleb(SH.normalizuj(dict(base, upshelf=True, upshelftype="lip", upshelfpos=640, upshelfdepth=350), 30)[1], lang, 30)
    ids = {x["id"]: x for x in sou}
    check({"upshelf", "upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth"} <= set(ids), f"shrnuti {lang}: vsechny volby police ({sorted(k for k in ids if k.startswith('upshelf'))})")
    if "upshelf" in ids:
        check(ids["upshelftype"]["value"] == POPISKY[lang]["lip"] and ids["upshelfpos"]["value"] == "640 mm" and ids["upshelfdepth"]["value"] == "350 mm", f"shrnuti {lang}: hodnoty ({ids['upshelftype']['value']}, {ids['upshelfpos']['value']}, {ids['upshelfdepth']['value']})")
    sou0 = SH._souhrn_voleb(SH.normalizuj(base, 30)[1], lang, 30)
    ids0 = {x["id"]: x for x in sou0}
    check(not [k for k in ids0 if k.startswith("upshelf")], f"shrnuti {lang}: bez police zadny radek police (ani prepinac 'ne', ani podvolby; Robert 2026-10-08: jen to, co stul obsahuje) ({sorted(k for k in ids0 if k.startswith('upshelf'))})")
    sou1 = SH._souhrn_voleb(SH.normalizuj(dict(base, upshelf=True, upshelftype="frame"), 30)[1], lang, 30)
    k1 = {x["id"] for x in sou1}
    check("upshelf" in k1 and "upshelfboard" not in k1 and "upshelfpos" not in k1, f"shrnuti {lang}: ramova police bez desky a bez automaticke vysky ({sorted(k for k in k1 if k.startswith('upshelf'))})")
for typ, ocek_nazvy in (("flat", {"laminovaná dřevotříska 18 mm"}), ("dividers", {"MDF deska 8 mm (police)", "překližka PR10 10 mm (police)", "úhelníková spojka 30×30"}), ("lip", {"překližka PR10 10 mm (police)", "úhelníková spojka 30×30"})):
    gen_k = S.sestav_stul(**SH.normalizuj(dict(base, upshelf=True, upshelftype=typ), 30)[0])
    bom = SH._neutralni_bom(gen_k["dily"])
    nazvy = {x["nazev"] for x in bom}
    check(all(("product_" not in n) for n in nazvy), f"bom {typ}: zadne cislo karty v nazvech")
    check(ocek_nazvy <= nazvy or {n for n in ocek_nazvy if "laminovaná" not in n} <= nazvy, f"bom {typ}: nazvy novych dilu {sorted(ocek_nazvy)} v {sorted(nazvy)}")

# ---------------------------------------------------------------------------------------------------------------------
print("9) 3D ovladani ve verejne podobe")
for lang in ("cs", "en", "sk"):
    st, dm = post(dict(base, upshelf=True, upshelftype="dividers"), lang)
    ov = ((dm.get("vodici") or {}).get("ovladani") or {})
    c = next((x for x in ov.get("casti", []) if x["id"] == "upshelf"), None)
    check(c is not None and c["menu"], f"[{lang}] 3D cast 'upshelf' s menu")
    if not c:
        continue
    nast = [m["nastav"] for m in c["menu"] if m.get("nastav")]
    check(all(set(n) <= {"upshelf", "upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt"} for n in nast), f"[{lang}] 3D menu police nastavuje jen sloty upshelf* ({nast[:3]})")
    check(any(n.get("upshelf") is False for n in nast) and any(n.get("upshelftype") == "flat" for n in nast) and any("upshelfpos" in n for n in nast) and any("upshelfdepth" in n for n in nast), f"[{lang}] 3D menu: odebrat, typ, vyska, hloubka")
    texty = [m["text"] for m in c["menu"]]
    check(all(t and "{" not in t for t in texty), f"[{lang}] 3D menu: texty bez znacek ({texty[:2]})")
    if lang == "en":
        check("Remove the shelf between the uprights" in texty and "Shelf: flat, board on the frame" in texty, f"[en] 3D menu police anglicky ({texty[:3]})")
    if lang == "sk":
        check("Odstrániť policu medzi stojkami" in texty, f"[sk] 3D menu police slovensky ({texty[:2]})")
    # kazda polozka (ne zakazana) se da poslat zpet do resolve a vrati platny vysledek
    for m in c["menu"]:
        if m.get("zakazano") or not m.get("nastav"):
            continue
        st, dd = post(dict(dm["selection"], **m["nastav"]), lang)
        check(st == 200 and dd["valid"] and not dd["errors"], f"[{lang}] 3D '{m['text']}' -> platny vysledek ({dd.get('errors')})")
        if m["nastav"].get("upshelf") is False:
            check(dd["selection"]["upshelf"] is False and dd["hash"] == d0["hash"], f"[{lang}] 3D '{m['text']}' -> stul bez police")
        if "upshelftype" in m["nastav"]:
            check(dd["selection"]["upshelftype"] == m["nastav"]["upshelftype"], f"[{lang}] 3D '{m['text']}' -> typ {m['nastav']['upshelftype']}")

# ---------------------------------------------------------------------------------------------------------------------
print("10) NABIDKA PRO VEREJNOST podle aktivnich karet (pravidlo 54) x zamestnanec")
c_adm = appmod.get_conn()
cu_adm = c_adm.cursor()
cu_adm.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN_ID = cu_adm.fetchone()["id"]
c_adm.rollback()
staff = appmod.app.test_client()
with staff.session_transaction() as _s:
    _s["user_id"] = ADMIN_ID
LAM = "product_4933"
ZDROJ = {"jen lamino 18 (nic dalsiho)": ({LAM}, ["flat", "frame"], ["lam18"]),
         "bez desky 12 mm": (VSECHNY_KARTY - {HP.LAM12_PART}, TYPY_PUB, ["lam18", "mdf8"]),
         "bez PR10 (lem, prepazky pryc)": (VSECHNY_KARTY - {HP.LAM12_PART, HP.PREPAZKA_PART}, ["flat", "frame", "groove"], ["lam18", "mdf8"]),
         "bez MDF 8 (drazka, prepazky pryc)": (VSECHNY_KARTY - {HP.LAM12_PART, "product_3939"}, ["flat", "frame", "lip", "slope"], ["lam18"]),
         "bez konzoly 3323 (sikma pryc)": (VSECHNY_KARTY - {HP.LAM12_PART, "product_3323"}, ["flat", "frame", "groove", "lip", "dividers"], ["lam18", "mdf8"]),
         "bez uhelniku 30x30 (lem, prepazky pryc)": (VSECHNY_KARTY - {HP.LAM12_PART, "product_3045"}, ["flat", "frame", "groove"], ["lam18", "mdf8"]),
         "vsechny karty": (VSECHNY_KARTY, TYPY_PUB, ["lam18", "lam12", "mdf8"])}
for stav, (karty, typy_ok, desky_ok) in ZDROJ.items():
    nastav_karty(karty)
    sc_v = anon.get(f"/api/shop/products/{PID}/configurator").get_json()
    sl_v = {x["id"]: x for x in sc_v["slots"]}
    sc_s = staff.get(f"/api/shop/products/{PID}/configurator").get_json()
    sl_s = {x["id"]: x for x in sc_s["slots"]}
    check([o["id"] for o in sl_v["upshelftype"]["options"]] == typy_ok, f"GATE schema verejnost ({stav}): typy {typy_ok} ({[o['id'] for o in sl_v['upshelftype']['options']]})")
    check([o["id"] for o in sl_v["upshelfboard"]["options"]] == desky_ok, f"GATE schema verejnost ({stav}): desky {desky_ok} ({[o['id'] for o in sl_v['upshelfboard']['options']]})")
    check([o["id"] for o in sl_s["upshelftype"]["options"]] == TYPY_PUB and [o["id"] for o in sl_s["upshelfboard"]["options"]] == ["lam18", "lam12", "mdf8"], f"GATE schema zamestnanec ({stav}): vsechny typy a desky")
    for typ in TYPY_PUB:
        st, dg = post(dict(base, upshelf=True, upshelftype=typ))
        ocek = typ if typ in typy_ok else "flat"
        check(st == 200 and dg["selection"]["upshelftype"] == ocek, f"GATE verejnost ({stav}) typ {typ}: vybrano {ocek} ({dg.get('selection', {}).get('upshelftype')})")
        for t_ in TYPY_PUB:
            if t_ not in typy_ok:
                o_ = dg["options"]["upshelftype"].get(t_)
                check(o_ and o_["disabled"] and o_["reason"], f"GATE verejnost ({stav}) typ {typ}: volba {t_} je zakazana s duvodem ({o_})")
        if "lam12" not in desky_ok:
            st, dl = post(dict(base, upshelf=True, upshelftype="flat", upshelfboard="lam12"))
            check(dl["selection"]["upshelfboard"] == "lam18", f"GATE verejnost ({stav}): deska 12 mm se verejnosti nedostane ({dl['selection']['upshelfboard']})")
            ol = dl["options"]["upshelfboard"].get("lam12")
            check(ol and ol["disabled"] and "není v nabídce" in ol["reason"], f"GATE verejnost ({stav}): lam12 zakazano s duvodem ({ol})")
        # zamestnanec dostane vse
        rs = staff.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": dict(base, upshelf=True, upshelftype=typ), "lang": "cs", "staff": True})
        ds = rs.get_json()
        check(rs.status_code == 200 and ds["selection"]["upshelftype"] == typ and not [1 for v in ds["options"]["upshelftype"].values() if "není v nabídce" in v["reason"]], f"GATE zamestnanec ({stav}) typ {typ}: vybrano {typ}")
    nastav_karty(karty)
    # ceny: verejnost s nenabizenym typem dostane cenu rovne police
    if "lip" not in typy_ok:
        pl = post(dict(base, upshelf=True, upshelftype="lip"))[1]["price"]["net"]
        pf = post(dict(base, upshelf=True, upshelftype="flat"))[1]["price"]["net"]
        check(pl == pf, f"GATE verejnost ({stav}): nenabizeny lem = cena rovne police ({pl} vs {pf})")
# kosik / objednavka jdou pres normalizuj: pozadavek verejnosti s nenabizenym typem dostane rovnou polici
nastav_karty({LAM})
with appmod.app.test_request_context("/"):
    pv, _ = SH.normalizuj(dict(base, upshelf=True, upshelftype="dividers"), 30)
check(pv["hpolice_typ"] == "rovna", f"GATE: normalizuj v pozadavku verejnosti zahodi nenabizeny typ ({pv['hpolice_typ']})")
pk, _ = SH.normalizuj(dict(base, upshelf=True, upshelftype="dividers"), 30)
check(pk["hpolice_typ"] == "prepazky", f"GATE: normalizuj mimo pozadavek (skripty, testy) bere vsechny typy ({pk['hpolice_typ']})")
# klic cache: nabidka je v klici (jinak by verejnost dostala odpoved zamestnance a naopak)
nastav_karty(VSECHNY_KARTY - {HP.PREPAZKA_PART})
st, dc1 = post(dict(base, upshelf=True, upshelftype="lip"))
nastav_karty(VSECHNY_KARTY)
st, dc2 = post(dict(base, upshelf=True, upshelftype="lip"))
check(dc1["selection"]["upshelftype"] == "flat" and dc2["selection"]["upshelftype"] == "lip", f"cache: zmena nabidky karet meni odpoved ({dc1['selection']['upshelftype']} -> {dc2['selection']['upshelftype']})")
nastav_karty(VSECHNY_KARTY)
# chyba cteni DB = jen laminodeska 18 (stul nesmi spadnout)
SH._KARTY_POLICE_CACHE.update(t=0.0, set=frozenset({LAM}))
orig_conn = SH.get_conn
SH.get_conn = lambda: (_ for _ in ()).throw(RuntimeError("DB nedostupna (test)"))
with appmod.app.test_request_context("/"):
    karty_chyba = SH.karty_police_verejne()
SH.get_conn = orig_conn
check(karty_chyba == frozenset({LAM}), f"chyba DB: nabidnuta jen laminodeska 18 mm ({sorted(karty_chyba)})")
nastav_karty(VSECHNY_KARTY)
# skutecny stav karet v DB: vsechny dily kromě desky 12 mm jsou aktivni; (cteni)
SH._KARTY_POLICE_CACHE.update(t=0.0, set=frozenset({LAM}))
with appmod.app.test_request_context("/"):
    skutecne = SH.karty_police_verejne()
check(LAM in skutecne, f"skutecna DB: laminodeska 18 mm je v nabidce verejnosti ({sorted(skutecne)})")
print(f"   (skutecne aktivni karty police v DB: {sorted(skutecne)})")
nastav_karty(VSECHNY_KARTY)

# ---------------------------------------------------------------------------------------------------------------------
print("11) cache resolve a fuzz")
for poradi in (("lip", "flat"), ("flat", "lip")):
    SH._RESOLVE_CACHE.clear()
    out = {}
    for t_ in poradi:
        st, dd = post(dict(base, upshelf=True, upshelftype=t_))
        out[t_] = dd["hash"]
    check(len(set(out.values())) == 2, f"cache {poradi}: ruzne typy = ruzne odpovedi")
rng = random.Random(20261008)
sc = schema("cs")
vyj = []
n_platnych = 0
for _i in range(160):
    sel = {}
    for s_ in sc["slots"]:
        if s_["id"].startswith("upshelf") or rng.random() < 0.15:
            if rng.random() < 0.3 and not s_["id"] == "upshelf":
                continue
            if s_["type"] == "toggle":
                sel[s_["id"]] = rng.random() < 0.7 if s_["id"] == "upshelf" else rng.random() < 0.5
            elif s_["type"] == "select":
                sel[s_["id"]] = rng.choice([o["id"] for o in s_["options"]] + ["xx"])
            else:
                lo, hi, stp = s_["slider"]["min"], s_["slider"]["max"], s_["slider"]["step"]
                sel[s_["id"]] = rng.choice([lo, hi, lo + stp * rng.randint(0, int((hi - lo) // stp)), hi + 700, lo - 700, None]) if s_["id"] in ("upshelfpos",) else rng.choice([lo, hi, lo + stp * rng.randint(0, int((hi - lo) // stp)), hi + 700, lo - 700])
    lg, sy = rng.choice(("cs", "en", "sk")), rng.choice((PID, PID_35, PID_40))
    try:
        st, rr = post(sel, lg, sy)
        ok = (st == 200 and isinstance(rr["valid"], bool) and len(rr["hash"]) == 16 and set(rr["options"]) >= set(rr["selection"]) and all(e["message"] and "slot" in e for e in rr["errors"])
              and all(n["message"] for n in rr["notices"]) and (not rr["valid"] or (rr["vodici"] and rr["vodici"].get("ovladani"))))
        if not ok:
            vyj.append((sel, lg, sy, "neuplna odpoved"))
        n_platnych += 1 if rr.get("valid") else 0
    except Exception as e:      # noqa: BLE001
        vyj.append((sel, lg, sy, f"{type(e).__name__}: {e}"))
check(not vyj, f"fuzz 160 nahodnych vyberu s policí (cs/en/sk, system 30/35/40): zadna vyjimka ani neuplna odpoved ({len(vyj)}: {str(vyj[:1])[:300]}); platnych {n_platnych}")

print()
if FAILS:
    print(f"CHYBA: {len(FAILS)} kontrol selhalo, {OK} OK")
    sys.exit(1)
print(f"{OK} kontrol OK")
