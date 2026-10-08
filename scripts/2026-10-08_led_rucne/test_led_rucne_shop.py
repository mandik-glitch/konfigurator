#!/usr/bin/env python3
"""Test RUCNICH SVITIDEL LED ve VEREJNEM API stolu (api/stul_shop.py; bot8, 2026-10-08).
Robert: "svitidla v generatoru se pridavaji automaticky za sebe podle delky, ale chceme aby se pridavali jen rucne a mohli se posouvat podel profilu".
SKUTECNE routy pres Flask test_client (bez prihlaseni = verejnost, se session admina = zamestnanec). DB se jen CTE (ceny karet svitidel); mapovani produktu se podstrci do cache modulu.

Hlida: schema (sloty `ledcount` a `ledpos1..4` hned za `ledlen`, zavisi na posts + led + ledlight, texty cs/en/sk, SSE je nema, vychozi vyber), resolve (vychozi = 1 svitidlo i na siroke stolu,
pocet 1..max, cena = cena karty x pocet, kusovnik, orez poctu + oznameni, polohy, options s mezemi, shrnuti voleb), vstup (neplatne hodnoty), token (klic J), odkaz na vyrobni list,
klic cache resolve, 3D ovladani (verejna id `ledlamp<k>` / `ledpos<k>`, preklady, polozky nabidky NEJSOU orezane starymi mezemi options = simulace orezu v prohlizeci), staff API (`?led_pocet=`).
Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_led_rucne/test_led_rucne_shop.py
  (STUL_API_OVERRIDE=<adresar api> = kandidat; --setenv=STUL_API_OVERRIDE=... pri spusteni pres systemd-run; TEST_STOP_PRVNI=1 = prvni selhani konci)"""
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
        if os.environ.get("TEST_STOP_PRVNI"):
            sys.exit(1)


PID, PID_SSE = 9885, 9886
L1200, L600 = "product_4929", "product_5359"
LED_MAX = S.LED_MAX


def nastav_led(delky):
    SH._LED_DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset({S.LED_DELKA_VYCHOZI, *delky}))


nastav_led({600})
SH._DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset(S.PANEL_DELKY))
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
POPISKY = {"cs": ("Počet svítidel LED", "Poloha svítidla LED {k}"), "en": ("Number of LED lights", "LED light {k} position"), "sk": ("Počet svietidiel LED", "Poloha svietidla LED {k}")}
for lang, (p_count, p_pos) in POPISKY.items():
    sc = schema(lang)
    slots = {s["id"]: s for s in sc["slots"]}
    ids = [s["id"] for s in sc["slots"]]
    sl = slots.get("ledcount")
    check(sl is not None and sl["type"] == "slider" and sl["group"] == "g_extras" and sl["slider"] == {"min": 1, "max": LED_MAX, "step": 1, "unit": "ks"}, f"schema {lang}: ledcount je slider 1-{LED_MAX} ks v g_extras ({sl and sl.get('slider')})")
    if sl:
        check(sl["label"] == p_count and sl["help"] and "{" not in sl["help"] and sl.get("depends_on") == ["posts", "led", "ledlight"], f"schema {lang}: popisek '{p_count}', napoveda, zavislosti ({sl.get('depends_on')})")
    for k in range(1, LED_MAX + 1):
        sk = slots.get(f"ledpos{k}")
        check(sk is not None and sk["type"] == "slider" and sk["group"] == "g_extras" and sk["slider"]["unit"] == "mm" and sk["slider"]["step"] == 1 and sk["slider"]["min"] <= -1000 and sk["slider"]["max"] >= 1000,
              f"schema {lang}: ledpos{k} je slider v mm s dostatecnym rozsahem ({sk and sk.get('slider')})")
        if sk:
            check(sk["label"] == p_pos.format(k=k) and sk.get("depends_on") == ["posts", "led", "ledlight"], f"schema {lang}: ledpos{k}: popisek '{p_pos.format(k=k)}' ({sk['label']}), zavislosti")
            check((sk["help"] is not None) == (k == 1) and (k > 1 or "{" not in sk["help"]), f"schema {lang}: napoveda polohy je jen u prvniho slotu")
    poradi = ["ledlight", "ledlen", "ledcount"] + [f"ledpos{k}" for k in range(1, LED_MAX + 1)]
    check(ids[ids.index("ledlight"):ids.index("ledlight") + len(poradi)] == poradi, f"schema {lang}: poradi ledlight, ledlen, ledcount, ledpos1..{LED_MAX} ({ids[ids.index('ledlight'):ids.index('ledlight') + len(poradi)]})")
    d = sc["default_selection"]
    check(d.get("ledcount") == 1 and all(k in d and d[k] is None for k in [f"ledpos{j}" for j in range(1, LED_MAX + 1)]), f"schema {lang}: vychozi vyber ledcount 1, ledpos* None")
    check(set(d) == set(slots), f"schema {lang}: klic vychoziho vyberu pro kazdy slot")
    check("řadí se vedle sebe po šířce stolu" not in slots["ledlen"]["help"] and "side by side across the table width" not in slots["ledlen"]["help"] and "vedľa seba po šírke stola" not in slots["ledlen"]["help"],
          f"schema {lang}: napoveda delky svitidla uz netvrdi, ze se radi samy")
sc_sse = schema("cs", PID_SSE)
check(not [s for s in sc_sse["slots"] if s["id"].startswith(("led", "ledcount", "ledpos"))], "schema SSE: sloty svitidel nejsou (vychozi vyber SSE nese i klice, ktere SSE ignoruje - stejne jako ledlen)")
for lang in [x for x in ("de", "hu") if x in SH.TEXTY]:
    check(all(k in SH.TEXTY[lang] for k in ("ledcount", "help_ledcount", "help_ledpos", "ledpos1", "ledpos4")) and lang in SH.LEDPOCET_OREZANO, f"dalsi jazyk {lang}: nove texty maji (anglickou) zalohu")

base = schema("cs")["default_selection"]

# ---- vychozi stul: jedno svitidlo, beze zmeny
st, d = post(base)
check(st == 200 and d["valid"] and d["selection"]["ledcount"] == 1 and all(d["selection"][f"ledpos{k}"] is None for k in range(1, LED_MAX + 1)), f"vychozi vyber: platny, ledcount 1, polohy None ({st})")
o = d["options"]
check(o["ledcount"] == {"min": 1, "max": 1, "value": 1}, f"vychozi stul (jedno svitidlo se vejde): options.ledcount = {o['ledcount']}")
check(o["ledpos1"]["auto"] is True and o["ledpos1"]["min"] < o["ledpos1"]["value"] < o["ledpos1"]["max"] and abs(o["ledpos1"]["value"] - (-31.7)) < 0.1 and all(o[f"ledpos{k}"] == {"hidden": True} for k in (2, 3, 4)),
      f"vychozi stul: options.ledpos1 = automaticka poloha s rozsahem, ledpos2-4 hidden ({o['ledpos1']})")
check(not [n for n in d["notices"] if n["slot"] == "ledcount"] and len(led_dily(base)) == 1, "vychozi stul: bez oznameni, 1 svitidlo")
sou = [x["id"] for x in SH._souhrn_voleb(d["selection"], "cs", 30)]
check("ledcount" not in sou and not [x for x in sou if x.startswith("ledpos")], f"vychozi shrnuti voleb bez radku svitidel ({[x for x in sou if x.startswith('led')]})")
p_def = SH.normalizuj(base, 30)[0]
check(d["hash"] == G.kanonicky_hash(S.sestav_stul(**p_def)["parametry"]), "vychozi vyber: hash = hash generatoru")

# ---- siroky stul: svitidla uz se nepridavaji sama; pocet 1..max, cena = cena karty x pocet
ctx = _stul_api._ctx_ceny()
c1200, c600 = ctx["parts"][L1200]["price_czk"], ctx["parts"][L600]["price_czk"]
check(c1200 is not None and c600 is not None and c600 > 0, f"karty svitidel maji cenu ({c1200}, {c600})")
st, w1 = post(dict(base, w=3000))
check(w1["valid"] and w1["selection"]["ledcount"] == 1 and len(led_dily(dict(base, w=3000))) == 1, f"sirka 3000, LED 1200: VYCHOZI JE 1 SVITIDLO (drive 2 automaticky) ({len(led_dily(dict(base, w=3000)))})")
check(w1["options"]["ledcount"] == {"min": 1, "max": 2, "value": 1}, f"sirka 3000 / 1200: options.ledcount max 2 ({w1['options']['ledcount']})")
st, w2 = post(dict(base, w=3000, ledcount=2))
check(w2["valid"] and w2["selection"]["ledcount"] == 2 and len(led_dily(dict(base, w=3000, ledcount=2))) == 2 and not [x for x in w2["notices"] if x["slot"] == "ledcount"], f"sirka 3000 / 1200, ledcount=2: dve svitidla bez oznameni o poctu ({len(led_dily(dict(base, w=3000, ledcount=2)))}, {w2['notices']})")
dp = w2["price"]["net"] - w1["price"]["net"]
check(abs(dp - 1.03 * c1200) < 2.0, f"sirka 3000: druhe svitidlo stoji cenu karty + Balne 3 % ({dp:.2f} vs {1.03 * c1200:.2f})")
sel6 = dict(base, w=3000, ledlen="600")
ceny = {}
for n in range(1, 5):
    st, dn = post(dict(sel6, ledcount=n))
    check(st == 200 and dn["valid"] and dn["selection"]["ledcount"] == n and len(led_dily(dict(sel6, ledcount=n))) == n and not [x for x in dn["notices"] if x["slot"] == "ledcount"], f"sirka 3000 / 600, ledcount={n}: {n} svitidel ({st})")
    kus = _stul_api.cena_konfigurace(S.sestav_stul(**SH.normalizuj(dict(sel6, ledcount=n), 30)[0])["dily"])["kusovnik"]["radky"]
    rad = [x for x in kus if "[LED600]" in x["nazev"]]
    check(len(rad) == 1 and rad[0]["mnozstvi"] == n and abs(rad[0]["cena_ks"] - c600) < 0.005, f"ledcount={n}: kusovnik {n} x LED600 za cenu karty {c600:.0f} ({rad and rad[0]['mnozstvi']})")
    bom = SH._neutralni_bom(S.sestav_stul(**SH.normalizuj(dict(sel6, ledcount=n), 30)[0])["dily"])
    led_b = [x for x in bom if x["nazev"].startswith("LED osvětlení")]
    check(len(led_b) == 1 and led_b[0]["nazev"] == "LED osvětlení 600 mm" and led_b[0]["mnozstvi"] == n, f"ledcount={n}: neutralni kusovnik '{n} x LED osvětlení 600 mm' ({led_b})")
    ceny[n] = dn["price"]["net"]
    check(dn["options"]["ledcount"] == {"min": 1, "max": 4, "value": n}, f"ledcount={n}: options.ledcount {dn['options']['ledcount']}")
    check(sorted(k for k, v in dn["options"].items() if k.startswith("ledpos") and v.get("hidden")) == [f"ledpos{k}" for k in range(n + 1, 5)], f"ledcount={n}: ledpos nad poctem jsou hidden")
check(all(abs((ceny[n + 1] - ceny[n]) - 1.03 * c600) < 2.0 for n in (1, 2, 3)), f"cena roste o cenu karty svitidla + Balne 3 % za kazde svitidlo ({[round(ceny[n + 1] - ceny[n], 2) for n in (1, 2, 3)]} vs {1.03 * c600:.2f})")
check(len({post(dict(sel6, ledcount=n))[1]["hash"] for n in range(1, 5)}) == 4, "ruzne pocty = ruzne hashe")

# ---- pozadovany pocet vyssi nez se vejde: orez + oznameni (cs / en / sk)
OREZ = {"cs": "Počet svítidel LED snížen na 1 – víc se jich sem nevejde vedle sebe (užší stůl nebo delší svítidla).",
        "en": "Number of LED lights reduced to 1 – more will not fit side by side (a narrower table or longer lights).",
        "sk": "Počet svietidiel LED znížený na 1 – viac sa ich sem nezmestí vedľa seba (užší stôl alebo dlhšie svietidlá)."}
for lang, text in OREZ.items():
    st, do = post(dict(base, ledcount=3), lang)
    nn = [x for x in do["notices"] if x["slot"] == "ledcount"]
    check(do["valid"] and do["selection"]["ledcount"] == 1 and len(nn) == 1 and nn[0]["message"] == text and nn[0]["action"] == "info", f"stul 1280, ledcount=3 ({lang}): orez na 1 + oznameni ({nn})")
st, do = post(dict(base, ledcount=1))
check(not [x for x in do["notices"] if x["slot"] == "ledcount"], "ledcount=1: zadne oznameni")
st, d3 = post(dict(sel6, w=1500, ledcount=3))
check(d3["selection"]["ledcount"] == 2 and [x for x in d3["notices"] if x["slot"] == "ledcount"] and "2" in [x for x in d3["notices"] if x["slot"] == "ledcount"][0]["message"], "stul 1500 / 600, ledcount=3: orez na 2")
st, d2 = post(dict(sel6, w=1500, ledcount=2))
check(not [x for x in d2["notices"] if x["slot"] == "ledcount"], "stul 1500 / 600, ledcount=2: bez oznameni (klic cache nese POZADOVANY pocet, odpoved s oznamenim se nesdili)")
st, d3b = post(dict(sel6, w=1500, ledcount=3))
check([x for x in d3b["notices"] if x["slot"] == "ledcount"], "stul 1500 / 600, ledcount=3 podruhe: oznameni zustava (cache)")

# ---- polohy
st, dp1 = post(dict(base, ledpos1=50))
check(dp1["valid"] and dp1["selection"]["ledpos1"] == 50 and isinstance(dp1["selection"]["ledpos1"], int), f"ledpos1=50 -> echo 50 (int) ({dp1['selection']['ledpos1']!r})")
o1 = dp1["options"]["ledpos1"]
check(o1["auto"] is False and o1["value"] == 50 and o1["min"] <= -140 and o1["max"] >= 140 and o1["fits"] is True, f"options.ledpos1 po zadani: auto False, value 50, rozsah ({o1})")
check(dp1["hash"] != post(base)[1]["hash"], "poloha svitidla meni hash")
sou = {x["id"]: x for x in SH._souhrn_voleb(dp1["selection"], "cs", 30)}
check(sou.get("ledpos1", {}).get("value") == "50 mm" and sou["ledpos1"]["label"] == "Poloha svítidla LED 1" and "ledcount" not in sou, f"shrnuti: 'Poloha svítidla LED 1: 50 mm' ({sou.get('ledpos1')})")
st, dpa = post(dict(base, ledpos1=-31.7))
check(dpa["selection"]["ledpos1"] is None and dpa["hash"] == post(base)[1]["hash"], f"poloha shodna s automatickou (-31.7) = automaticka (None), stejny hash ({dpa['selection']['ledpos1']!r})")
st, dpb = post(dict(base, ledpos1=9999))
check(dpb["valid"] and abs(dpb["selection"]["ledpos1"] - dpb["options"]["ledpos1"]["max"]) <= 1 and not dpb["errors"], f"ledpos1=9999: orizne se na mez ({dpb['selection']['ledpos1']} / {dpb['options']['ledpos1']['max']})")
st, dpc = post(dict(sel6, w=1500, ledcount=2, ledpos2=400))
check(dpc["selection"]["ledpos2"] == 400 and dpc["selection"]["ledpos1"] is None and dpc["options"]["ledpos2"]["auto"] is False and dpc["options"]["ledpos1"]["auto"] is True, f"2 svitidla, jen druhe posunute: ledpos2 400, ledpos1 auto ({dpc['selection']['ledpos1']!r}, {dpc['selection']['ledpos2']!r})")
sou2 = [x["id"] for x in SH._souhrn_voleb(dpc["selection"], "cs", 30)]
check("ledcount" in sou2 and "ledpos2" in sou2 and "ledpos1" not in sou2, f"shrnuti: pocet 2 a poloha druheho ({[x for x in sou2 if x.startswith('led')]})")
for lang, popisek, hodnota in (("en", "Number of LED lights", "2 ks"), ("sk", "Počet svietidiel LED", "2 ks")):
    sou_l = {x["id"]: x for x in SH._souhrn_voleb(dpc["selection"], lang, 30)}
    check(sou_l["ledcount"]["label"] == popisek and sou_l["ledcount"]["value"] == hodnota, f"shrnuti {lang}: '{popisek}: {hodnota}' ({sou_l['ledcount']})")
# polohy nad poctem se zahodi, bez svitidla se zahodi vse
st, dpd = post(dict(base, ledpos3=100, ledpos2=100))
check(dpd["selection"]["ledpos2"] is None and dpd["selection"]["ledpos3"] is None and dpd["hash"] == post(base)[1]["hash"], "polohy neexistujicich svitidel se zahodi (a nemeni hash)")
for kw in (dict(led=False), dict(ledlight=False), dict(posts=False)):
    st, dv = post(dict(sel6, w=1500, ledcount=2, ledpos1=-300, **kw))
    s_ = dv["selection"]
    check(s_["ledcount"] == 1 and all(s_[f"ledpos{k}"] is None for k in range(1, 5)) and dv["options"]["ledcount"] == {"min": 1, "max": 1} and all(dv["options"][f"ledpos{k}"] == {"hidden": True} for k in range(1, 5)),
          f"{kw}: pocet a polohy se zahodi, options zamcene / hidden")
    check(dv["hash"] == post(dict(sel6, w=1500, **kw))[1]["hash"], f"{kw}: hash jako bez pozadavku na svitidla")

# ---- vstup: neplatne hodnoty
for spatny in (0, -3, 99, 2.6, "3", "abc", None, True, False, [], {}, 1e99, float("inf"), "2.5"):
    try:
        st, dn = post(dict(sel6, w=3000, ledcount=spatny))
    except Exception as e:  # noqa: BLE001
        check(False, f"ledcount={spatny!r}: vyjimka {type(e).__name__}: {e}")
        continue
    check(st == 200 and dn["selection"]["ledcount"] in (1, 2, 3, 4) and dn["valid"], f"ledcount={spatny!r}: platna odpoved, pocet {dn.get('selection', {}).get('ledcount')} ({st})")
check(post(dict(sel6, w=3000, ledcount="3"))[1]["selection"]["ledcount"] == 3 and post(dict(sel6, w=3000, ledcount=99))[1]["selection"]["ledcount"] == 4 and post(dict(sel6, w=3000, ledcount=0))[1]["selection"]["ledcount"] == 1, "ledcount: text '3' se prijme, 99 -> 4, 0 -> 1")
for spatny in ("abc", [], {}, True, float("nan"), float("inf"), "", None):
    st, dn = post(dict(base, ledpos1=spatny))
    check(st == 200 and dn["selection"]["ledpos1"] is None, f"ledpos1={spatny!r}: neplatne = automaticka poloha ({st}, {dn.get('selection', {}).get('ledpos1')!r})")
st, dn = post(dict(base, ledpos1="40"))
check(dn["selection"]["ledpos1"] == 40, "ledpos1='40' (text) se prijme")

check(SH._ledpos("40.04") == 40.0 and SH._ledpos(99999) == 3000.0 and SH._ledpos(-99999) == -3000.0 and SH._ledpos(None) is None and SH._ledpos("") is None, "_ledpos: zaokrouhleni na 0,1 mm, orez na +-3000, None / prazdne = automaticky")
pn_, _ = SH.normalizuj(dict(base, ledcount=1, ledpos2=100, ledpos3=50), 30)
check(pn_["led_pocet"] == 1 and pn_["led_z2"] is None and pn_["led_z3"] is None, "normalizuj: polohy svitidel nad poctem se zahodi uz ve vstupu")

# ---- token (klic J jen u nevychozich) a model
def zab(sel):
    return SH._zabal(S.sestav_stul(**SH.normalizuj(sel, 30)[0])["parametry"])


check("J" not in zab(base) and "J" not in zab(dict(base, w=3000)), "token: vychozi svitidlo bez klice J")
check(zab(dict(sel6, ledcount=2)).get("J") == [2, None, None], f"token: pocet 2, polohy auto: J = [2, None, None] ({zab(dict(sel6, ledcount=2)).get('J')})")
check(zab(dict(sel6, w=1500, ledcount=2, ledpos2=400)).get("J") == [2, None, 400.0], f"token: J = [2, None, 400.0] ({zab(dict(sel6, w=1500, ledcount=2, ledpos2=400)).get('J')})")
check(zab(dict(base, ledpos1=50)).get("J") == [1, 50.0], f"token: jedno svitidlo posunute: J = [1, 50.0] ({zab(dict(base, ledpos1=50)).get('J')})")
check("J" not in zab(dict(base, led=False, ledcount=3)) and "J" not in zab(dict(base, ledlight=False, ledcount=3)), "token: bez svitidla klic J neni")
for sel_t in (dict(sel6, w=3000, ledcount=4), dict(sel6, w=3000, ledcount=3, ledpos1=-1000, ledpos2=0, ledpos3=900), dict(sel6, w=1500, ledcount=2, ledpos2=400), dict(base, ledpos1=50), dict(base, w=3000, ledcount=2)):
    pg = S.sestav_stul(**SH.normalizuj(sel_t, 30)[0])["parametry"]
    pp, chyba = SH.over_model(SH.podepis_model(pg))
    check(chyba is None and S._norm_parametry(pp)["led_pocet"] == pg["led_pocet"] and [S._norm_parametry(pp)[k] for k in S.LED_PARAMETRY_Z] == [pg[k] for k in S.LED_PARAMETRY_Z], f"token: pocet a polohy prezijou podpis a rozbaleni ({sel_t.get('ledcount')}, {pg['led_pocet']})")
    h_m, data = G.model_pro_parametry(S._norm_parametry(pp))
    check(h_m == G.kanonicky_hash(pg) and len(data) > 100000, f"token: model z rozbaleneho tokenu = stejny hash a GLB se slozi ({len(data)} B)")
pp0, _ = SH.over_model(SH.podepis_model(S.sestav_stul(**SH.normalizuj(base, 30)[0])["parametry"]))
check(S._norm_parametry(pp0)["led_pocet"] == 1 and all(S._norm_parametry(pp0)[k] is None for k in S.LED_PARAMETRY_Z), "token: starsi token bez klice J = jedno svitidlo, polohy auto")

# ---- odkaz na vyrobni list (staff blok)
st, dk = post(dict(sel6, w=1500, ledcount=2, ledpos2=400))
blok = SH._staff_blok(dk["hash"])
qs = dict(urllib.parse.parse_qsl(blok["vyrobni_list_url"].split("?", 1)[1]))
check(qs.get("led_pocet") == "2" and qs.get("led_z2") == "400.0" and "led_z1" not in qs, f"vyrobni list: dotaz nese led_pocet=2 a led_z2=400.0, ne led_z1 ({ {k: v for k, v in qs.items() if k.startswith('led')} })")
pq = S.parametry_z_dotazu(qs)
check(G.kanonicky_hash(S.sestav_stul(**pq)["parametry"]) == dk["hash"], "vyrobni list: dotaz vrati stejnou konfiguraci (stejny hash)")
blok0 = SH._staff_blok(post(base)[1]["hash"])
check("led_pocet" not in blok0["vyrobni_list_url"] and "led_z" not in blok0["vyrobni_list_url"], "vyrobni list vychoziho stolu: zadne led_pocet / led_z v odkazu (odkazy beze zmeny)")

# ---- 3D ovladani: verejna id, preklady, polozky nabidky nesmeji byt orezane starymi mezemi options
def klamp(patch, d):
    """Simulace product-configurator.js applyOvPatch: null -> vychozi (None), jinak orez na options.<slot> {min,max} (a kdyz je slot hidden / bez mezi, na rozsah ze schematu)."""
    out = {}
    for slot, v in patch.items():
        if v is None or isinstance(v, bool):
            out[slot] = v
            continue
        o = d["options"].get(slot) or {}
        sl = next((s for s in SCH["slots"] if s["id"] == slot), None)
        lo = o["min"] if isinstance(o.get("min"), (int, float)) else (sl["slider"]["min"] if sl and sl.get("slider") else None)
        hi = o["max"] if isinstance(o.get("max"), (int, float)) else (sl["slider"]["max"] if sl and sl.get("slider") else None)
        x = v
        if lo is not None and x < lo:
            x = lo
        if hi is not None and x > hi:
            x = hi
        out[slot] = x
    return out


SCH = schema("cs")
for lang in ("cs", "en", "sk"):
    st, dd = post(dict(sel6, w=3000, ledcount=3, ledpos1=-1000, ledpos2=0, ledpos3=900), lang)
    ov = (dd.get("vodici") or {}).get("ovladani")
    check(ov is not None, f"3D ovladani {lang}: neni vynechano (chybi-li preklad, vynecha se cele)")
    if not ov:
        continue
    casti = {c["id"]: c for c in ov["casti"]}
    tahy = {t["id"]: t for t in ov["tahy"]}
    check(all(f"ledlamp{k}" in casti for k in (1, 2, 3)) and "ledlamp4" not in casti and not [c for c in casti if c.startswith("led_")], f"3D {lang}: casti ledlamp1..3 (verejna id bez led_<k>) ({[c for c in casti if c.startswith('led')]})")
    check(all(f"ledpos{k}" in tahy for k in (1, 2, 3)) and not [t for t in tahy if t.startswith("led_z")], f"3D {lang}: tahy ledpos1..3 ({[t for t in tahy if t.startswith('led')]})")
    for k in (1, 2, 3):
        t = tahy[f"ledpos{k}"]
        check(t["param"] == f"ledpos{k}" and t["casti"] == [f"ledlamp{k}"] and all(m["param"] == f"ledpos{k}" for m in t["mereni"]), f"3D {lang}: tah ledpos{k}: parametr, cast, mereni na verejny slot")
        check(t["hodnota"] == dd["options"][f"ledpos{k}"]["value"] and t["min"] >= dd["options"][f"ledpos{k}"]["min"] - 1 and t["max"] <= dd["options"][f"ledpos{k}"]["max"] + 1, f"3D {lang}: tah ledpos{k}: hodnota = options.value, meze uvnitr options ({t['min']}, {t['hodnota']}, {t['max']})")
        check(casti[f"ledlamp{k}"]["param"] == ["ledcount", f"ledpos{k}"], f"3D {lang}: cast ledlamp{k}: parametry ledcount, ledpos{k}")
        for m in casti[f"ledlamp{k}"]["menu"]:
            if m["nastav"]:
                check(all(s in dd["options"] or s in {x['id'] for x in SCH['slots']} for s in m["nastav"]), f"3D {lang}: polozka '{m['text']}' nastavuje jen existujici sloty ({sorted(m['nastav'])})")
    if lang == "en":
        check(casti["ledlamp1"]["label"] == "LED light 1" and tahy["ledpos2"]["label"] == "LED light 2 position" and [m["text"] for m in casti["ledlamp2"]["menu"]] == ["Remove this light", "Move the light back to its default place"], f"3D en: popisky ({casti['ledlamp1']['label']!r})")
        check("from the left edge of the table" in [m["label"] for m in tahy["ledpos1"]["mereni"]], "3D en: mereni 'from the left edge of the table'")
    if lang == "sk":
        check(casti["ledlamp1"]["label"] == "Svietidlo LED 1" and [m["text"] for m in casti["ledlamp2"]["menu"]][0] == "Odstrániť toto svietidlo" and tahy["ledpos2"]["label"] == "Posun svietidla LED 2", "3D sk: popisky (cast, menu, tah)")
    # polozky nabidky: po orezu starymi mezemi options (jako v prohlizeci) musi vyjit TOTEZ, co server vypocital
    for k in (1, 2, 3):
        odeb = [m for m in casti[f"ledlamp{k}"]["menu"] if m["nastav"] and "ledcount" in m["nastav"]][0]
        patch = klamp(odeb["nastav"], dd)
        check(patch == odeb["nastav"], f"3D {lang}: 'Odebrat svitidlo {k}' neni orezano starymi mezemi options ({odeb['nastav']} -> {patch})")
        sel_po = dict(dd["selection"])
        sel_po.update(patch)
        st, dr = post(sel_po, lang)
        zbyt = [x for i, x in enumerate([dd["options"][f"ledpos{j}"]["value"] for j in (1, 2, 3)]) if i != k - 1]
        vys = [dr["options"][f"ledpos{j}"]["value"] for j in (1, 2)]
        check(dr["selection"]["ledcount"] == 2 and all(abs(a - b) < 0.2 for a, b in zip(vys, zbyt)), f"3D {lang}: po odebrani svitidla {k} zustala dalsi dve na miste ({vys} vs {zbyt})")
    pridat = [m for m in casti["led"]["menu"] if m["nastav"] and "ledcount" in m["nastav"]]
    check(len(pridat) == 1 and not pridat[0]["zakazano"], f"3D {lang}: nabidka 'Pridat svitidlo' u 3 svitidel z 4 mozných")
    patch = klamp(pridat[0]["nastav"], dd)
    check(patch == pridat[0]["nastav"], f"3D {lang}: 'Pridat svitidlo' neni orezano starymi mezemi options ({pridat[0]['nastav']} -> {patch})")
    st, dr = post(dict(dd["selection"], **patch), lang)
    check(dr["selection"]["ledcount"] == 4 and not [x for x in dr["notices"] if x["slot"] == "ledcount"], f"3D {lang}: po pridani je 4 svitidla bez oznameni ({dr['selection']['ledcount']})")
    # pridani a odebrani na uzkem stole (1 svitidlo) a presun mezi stavy: sada klic -> vzdy konzistentni
st, d1 = post(dict(sel6, w=1500))
ov1 = d1["vodici"]["ovladani"]
pr = [m for m in [c for c in ov1["casti"] if c["id"] == "led"][0]["menu"] if m["nastav"] and "ledcount" in m["nastav"]]
check(len(pr) == 1, "3D: u 1 svitidla na stole 1500 / 600 je nabidka Pridat")
pt = klamp(pr[0]["nastav"], d1)
check(pt == pr[0]["nastav"], f"3D: Pridat u 1 svitidla neni orezano starymi mezemi ({pr[0]['nastav']} -> {pt})")
st, d2 = post(dict(d1["selection"], **pt))
check(d2["selection"]["ledcount"] == 2 and abs(d2["options"]["ledpos1"]["value"] + 355.2) < 0.2 and abs(d2["options"]["ledpos2"]["value"] - 291.8) < 0.2, f"3D: na stole 1500 se po pridani 2. svitidla (nevejde se vedle prvniho) obe vystredi ({d2['options']['ledpos1']['value']}, {d2['options']['ledpos2']['value']})")
# jedno svitidlo 600 na stole 3000: "Pridat" da druhe tesne vedle prvniho a VYSLOVNE nese polohu i pro nove (dosud skryte, options.ledpos2 = hidden) svitidlo
st, e1 = post(dict(sel6, w=3000))
pr3 = [m for m in [c for c in e1["vodici"]["ovladani"]["casti"] if c["id"] == "led"][0]["menu"] if m["nastav"] and "ledcount" in m["nastav"]][0]
check(pr3["nastav"]["ledcount"] == 2 and pr3["nastav"]["ledpos1"] is not None and pr3["nastav"]["ledpos2"] is not None and e1["options"]["ledpos2"] == {"hidden": True},
      f"3D: Pridat u 1 svitidla na stole 3000 nese vyslovne polohy obou svitidel, druhy slot je zatim hidden ({pr3['nastav']}, {e1['options']['ledpos2']})")
check(klamp(pr3["nastav"], e1) == pr3["nastav"], f"3D: Pridat s polohou noveho (skryteho) svitidla neni orezano ({pr3['nastav']} -> {klamp(pr3['nastav'], e1)})")
st, e2 = post(dict(e1["selection"], **klamp(pr3["nastav"], e1)))
check(e2["selection"]["ledcount"] == 2 and abs(e2["options"]["ledpos1"]["value"] - e1["options"]["ledpos1"]["value"]) < 0.2 and abs(e2["options"]["ledpos2"]["value"] - (e1["options"]["ledpos1"]["value"] + 647.0)) < 0.5,
      f"3D: po pridani zustalo 1. svitidlo na miste a 2. je tesne vedle nej ({e2['options']['ledpos1']['value']}, {e2['options']['ledpos2']['value']})")
st, d3_ = post(dict(sel6, w=1500, ledcount=2))
odeb = [m for m in [c for c in d3_["vodici"]["ovladani"]["casti"] if c["id"] == "ledlamp1"][0]["menu"] if m["nastav"] and "ledcount" in m["nastav"]][0]
check(klamp(odeb["nastav"], d3_) == odeb["nastav"], f"3D: Odebrat 1. ze 2 svitidel neni orezano starymi mezemi ({odeb['nastav']} -> {klamp(odeb['nastav'], d3_)})")
# nabidka vychozi polohy: patch {ledposK: None} -> vychozi vyber (null)
vr = [m for m in [c for c in d2["vodici"]["ovladani"]["casti"] if c["id"] == "ledlamp2"][0]["menu"] if m["nastav"] and list(m["nastav"]) == ["ledpos2"]]
check(len(vr) == 1 and vr[0]["nastav"] == {"ledpos2": None}, "3D: 'Vratit svitidlo na vychozi misto' nastavuje null")

# ---- staff API: ?led_pocet=&led_z1=
r = staff.get("/api/stul/konfigurace?sirka=1500&led_delka=600&led_pocet=2&led_z1=-300")
j = r.get_json()
check(r.status_code == 200 and j["parametry"]["led_pocet"] == 2 and abs(j["parametry"]["led_z1"] + 300.0) < 1e-9 and sum(1 for dl in j["dily"] if dl["part_id"] == L600) == 2 and not j["problemy"], f"staff API ?led_pocet=2&led_z1=-300: dve svitidla ({r.status_code})")
check(j["led_info"]["pocet"] == 2 and j["led_info"]["max"] == 2 and j["led_info"]["pridat"] is None, f"staff API: led_info v odpovedi ({j['led_info']['pocet']}, {j['led_info']['max']})")
r = staff.get("/api/stul/konfigurace?sirka=2600")
j0 = r.get_json()
check(r.status_code == 200 and sum(1 for dl in j0["dily"] if dl["part_id"] == L1200) == 1, "staff API bez led_pocet na sirce 2600: JEDNO svitidlo (drive 2)")
for dotaz in ("led_pocet=9", "led_pocet=0", "led_pocet=1.5", "led_pocet=abc", "led_z1=abc", "led_z1=nan"):
    r = staff.get("/api/stul/konfigurace?sirka=1500&led_delka=600&" + dotaz)
    check(r.status_code == 400, f"staff API ?{dotaz} -> 400 ({r.status_code})")
r = staff.get("/api/stul/konfigurace?sirka=1500&led_delka=600&led_z2=null&led_z1=auto&led_pocet=2")
check(r.status_code == 200 and r.get_json()["parametry"]["led_z1"] is None, f"staff API: led_z1=auto / led_z2=null = automaticka poloha ({r.status_code})")

# ---- pro_objednavku (kosik / nabidka): vyber s rucnimi svitidly
po = SH.pro_objednavku(dict(sel6, w=3000, ledcount=3, ledpos1=-1000, ledpos2=0, ledpos3=900), lang="cs")
check(po["ok"] and po["valid"] and po["selection"]["ledcount"] == 3 and po["selection"]["ledpos1"] == -1000, f"pro_objednavku: efektivni vyber nese pocet a polohy ({po.get('selection', {}).get('ledcount')})")
led_b = [x for x in po["bom"] if x["nazev"].startswith("LED osvětlení")]
check(len(led_b) == 1 and led_b[0]["mnozstvi"] == 3 and led_b[0]["nazev"] == "LED osvětlení 600 mm", f"pro_objednavku: kusovnik 3 x LED osvětlení 600 mm ({led_b})")
check([x["id"] for x in po["souhrn"] if x["id"].startswith("led")][:2] == ["led", "ledlight"] and {"ledcount", "ledpos1", "ledpos2", "ledpos3"} <= {x["id"] for x in po["souhrn"]}, "pro_objednavku: souhrn nese pocet a polohy svitidel")
po1 = SH.pro_objednavku(dict(base, w=3000), lang="cs")
check(po1["ok"] and [x for x in po1["bom"] if x["nazev"].startswith("LED osvětlení")][0]["mnozstvi"] == 1, "pro_objednavku: vychozi siroky stul = 1 svitidlo")

# ---- klic cache resolve: pozadovany pocet (viz oznameni) a polohy
SH._RESOLVE_CACHE.clear()
a = post(dict(base, w=1500, ledlen="600", ledcount=2))[1]
b = post(dict(base, w=1500, ledlen="600", ledcount=2, ledpos1=-300))[1]
c = post(dict(base, w=1500, ledlen="600"))[1]
check(len({a["hash"], b["hash"], c["hash"]}) == 3 and a["selection"]["ledpos1"] is None and b["selection"]["ledpos1"] == -300 and c["selection"]["ledcount"] == 1, "cache: ruzne pocty a polohy nesdili odpoved")

print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:8]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
