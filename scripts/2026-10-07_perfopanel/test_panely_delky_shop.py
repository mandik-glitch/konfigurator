#!/usr/bin/env python3
"""Test DELKY PANELU ve VEREJNEM API stolu (api/stul_shop.py; bot8, 2026-10-07; Robert: dalsi velikosti perforovanych panelu 1481 / 1671 / 1975 vedle 1190).
SKUTECNE routy pres Flask test_client BEZ prihlaseni. DB se jen CTE (ceny karet panelu); mapovani produktu se podstrci do cache modulu - nic se nezapisuje.

Hlida: schema (slot `panellen` = select o 4 volbach za slotem `panelcount`, zavisi na `panels`, texty cs/en/sk, SSE slot nema), resolve (vychozi 1190 = beze zmeny, volba delky, snizeni delky pri
zuzeni stolu + oznameni, zakazane delky s duvodem a nejmensi sirkou, bez panelu se delka zahodi), cena (rozdil = rozdil cen karet panelu), token (klic L jen u jine nez vychozi delky),
shrnuti vyberu (doklad / nabidka), odkaz na vyrobni list bez vychozi delky.
Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_perfopanel/test_panely_delky_shop.py
  (STUL_API_OVERRIDE=<adresar api> = kandidat; --setenv=STUL_API_OVERRIDE=... pri spusteni pres systemd-run)"""
import json
import math
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

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


PID, PID_SSE = 9876, 9879


def nastav_aktivni(delky):
    """Simulace aktivnich karet novych delek (cache SH.delky_verejne): verejnost vidi vychozi 1190 + `delky`; nic se nezapisuje do DB."""
    SH._DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset({S.PANEL_DELKA_VYCHOZI, *delky}))


nastav_aktivni({1481, 1671, 1975})                                    # zakladni testy bezi s uvolnenymi vsemi delkami; gating je zvlast (sekce GATE)
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PID): SH.RECEPT, str(PID_SSE): SH.RECEPT_SSE})
anon = appmod.app.test_client()


def post(sel, lang="cs", pid=PID):
    r = anon.post("/api/shop/configurator/resolve", json={"product_id": pid, "selection": sel, "lang": lang})
    return r.status_code, r.get_json()


def schema(lang="cs", pid=PID):
    return anon.get(f"/api/shop/products/{pid}/configurator?lang={lang}").get_json()


DELKY = ["1190", "1481", "1671", "1975"]
# ---- schema
for lang, label, popis in (("cs", "Délka panelu", "1190 mm"), ("en", "Panel length", "1190 mm"), ("sk", "Dĺžka panela", "1190 mm")):
    sc = schema(lang)
    slots = {s["id"]: s for s in sc["slots"]}
    sl = slots.get("panellen")
    check(sl is not None and sl["type"] == "select" and sl["group"] == "g_extras", f"schema {lang}: slot panellen je select ve skupine g_extras ({sl and (sl['type'], sl['group'])})")
    if sl:
        check([o["id"] for o in sl["options"]] == DELKY and [o["label"] for o in sl["options"]] == [f"{d} mm" for d in DELKY], f"schema {lang}: volby 1190 / 1481 / 1671 / 1975 mm ({[o['label'] for o in sl['options']]})")
        check(sl["label"] == label and sl["help"] and "{" not in sl["help"], f"schema {lang}: popisek '{label}' a napoveda ({sl['label']!r})")
        check(sl.get("depends_on") == ["panels"], f"schema {lang}: slot zavisi na panels ({sl.get('depends_on')})")
        ids = [s["id"] for s in sc["slots"]]
        check(ids.index("panellen") == ids.index("panelcount") + 1, f"schema {lang}: slot panellen je hned za panelcount")
    check(sc["default_selection"].get("panellen") == "1190" and set(sc["default_selection"]) == set(slots), f"schema {lang}: vychozi vyber ma panellen = 1190 a klic pro kazdy slot")
check("panellen" not in {s["id"] for s in schema("cs", PID_SSE)["slots"]}, "schema SSE (system 41): slot panellen neni")
check(sc["rules_version"] == G.RULES_VERSION, "rules_version ve schematu")

base = schema("cs")["default_selection"]

# ---- vychozi stul 1280: delky nad 1190 jsou zakazane s duvodem a nejmensi sirkou
st, d = post(base)
check(st == 200 and d["valid"] and d["selection"]["panellen"] == "1190", f"vychozi vyber: platny, panellen 1190 ({st})")
op = d["options"]["panellen"]
check(set(op) == {"1481", "1671", "1975"} and all(op[k]["disabled"] and op[k]["reason"] for k in op), f"W=1280: zakazane 1481 / 1671 / 1975 s duvodem ({sorted(op)})")
P30 = 30
for k in ("1481", "1671", "1975"):
    pot = int(math.ceil(int(k) + 2 + 2 * P30))
    check(str(pot) in op[k]["reason"] and k in op[k]["reason"], f"W=1280: duvod u {k} uvadi nejmensi sirku {pot} mm ({op[k]['reason'][:90]})")
for lang in ("en", "sk"):
    st_, de = post(base, lang)
    ope = de["options"]["panellen"]
    check(set(ope) == set(op) and all("{" not in ope[k]["reason"] and "}" not in ope[k]["reason"] and ope[k]["reason"] for k in ope), f"W=1280 {lang}: duvody bez nevyplnenych znacek ({ope['1975']['reason'][:90]})")
    check(ope["1975"]["reason"] != op["1975"]["reason"], f"W=1280 {lang}: duvod je prelozeny")

# ---- siroky stul: vse se vejde, volba delky
sel = dict(base, w=2100)
st, d1190 = post(sel)
check(d1190["options"]["panellen"] == {} and d1190["valid"], f"W=2100: zadna delka neni zakazana ({d1190['options']['panellen']})")
ceny = {}
for k in DELKY:
    st, dk = post(dict(sel, panellen=k))
    check(st == 200 and dk["valid"] and dk["selection"]["panellen"] == k and not dk["errors"], f"W=2100 panellen={k}: platne, vybrano {k} ({st}, {dk.get('selection', {}).get('panellen')})")
    check(not [n for n in dk["notices"] if n["slot"] == "panellen"], f"W=2100 panellen={k}: zadne oznameni o snizeni delky")
    ceny[k] = (dk["price"]["net"], dk["hash"])
check(len({v[1] for v in ceny.values()}) == 4, f"W=2100: ruzne delky = ruzne hashe ({[v[1] for v in ceny.values()]})")
ctx = _stul_api._ctx_ceny()
karty = {k: ctx["parts"][S.PANEL_TYPY[int(k)]]["price_czk"] for k in DELKY}
check(all(v is not None for v in karty.values()), f"karty panelu maji cenu v katalogu ({karty})")
for k in DELKY:                                                          # polozka panelu v kusovniku = presne cena karty; zbytek rozdilu je Balne 3 % z dilu
    gen_k = S.sestav_stul(**SH.normalizuj(dict(sel, panellen=k), 30)[0])
    kus = _stul_api.cena_konfigurace(gen_k["dily"])["kusovnik"]["radky"]
    rad = [x for x in kus if f"[Perfopanel.{k}x" in x["nazev"]]
    check(len(rad) == 1 and rad[0]["mnozstvi"] == 1 and abs(rad[0]["cena_ks"] - karty[k]) < 0.005, f"W=2100: kusovnik ma 1 x panel {k} za cenu karty {karty[k]:.0f} ({rad and (rad[0]['mnozstvi'], rad[0]['cena_ks'])})")
    check(len([x for x in kus if "Perfopanel." in x["nazev"]]) == 1, f"W=2100 {k}: v kusovniku je jediny druh panelu")
for k in DELKY[1:]:
    dp = ceny[k][0] - ceny["1190"][0]
    check(abs(dp - 1.03 * (karty[k] - karty["1190"])) < 1.5, f"W=2100: cena delky {k} vs 1190 se lisi o rozdil cen karet panelu + Balne 3 % ({dp:.2f} vs {1.03 * (karty[k] - karty['1190']):.2f})")

# ---- zuzeni stolu: delka se snizi, ne odebere
for w, zad, ocek in ((1600, "1975", "1481"), (1800, "1975", "1671"), (1600, "1671", "1481"), (1300, "1481", "1190")):
    for lang in ("cs", "en", "sk"):
        st, dz = post(dict(base, w=w, panellen=zad), lang)
        nt = [n for n in dz["notices"] if n["slot"] == "panellen"]
        check(dz["valid"] and dz["selection"]["panels"] and dz["selection"]["panellen"] == ocek, f"W={w} {zad} ({lang}): delka snizena na {ocek}, panely zustavaji ({dz['selection']['panellen']}, panels {dz['selection']['panels']})")
        check(len(nt) == 1 and ocek in nt[0]["message"] and "{" not in nt[0]["message"], f"W={w} {zad} ({lang}): jedno oznameni o snizeni delky na {ocek} ({[n['message'][:70] for n in nt]})")
st, dz = post(dict(base, w=1100, panellen="1481"))                       # uz ani 1190 se nevejde: puvodni chovani (panely se odeberou s nabidkou roztazeni)
check(dz["selection"]["panels"] is False and dz["selection"]["panellen"] == "1190", f"W=1100: nevejde se ani 1190 = panely odebrany, panellen 1190 ({dz['selection']['panels']}, {dz['selection']['panellen']})")
check(not [n for n in dz["notices"] if n["slot"] == "panellen"], "W=1100: oznameni o snizeni delky se u odebranych panelu neukazuje")
check(dz["options"]["panellen"] == {}, "W=1100: bez panelu je options.panellen prazdne")

# ---- vypnute panely / neplatne hodnoty
st, dv = post(dict(sel, panels=False, panellen="1975"))
check(dv["selection"]["panellen"] == "1190" and dv["options"]["panellen"] == {}, f"vypnute panely: delka se zahodi na 1190 ({dv['selection']['panellen']})")
check(dv["hash"] == post(dict(sel, panels=False))[1]["hash"], "vypnute panely: delka hash nemeni")
for spatna in ("1200", "abc", None, 1191, [], {}, True, 1e99, -5):
    st, dn = post(dict(sel, panellen=spatna))
    check(st == 200 and dn["selection"]["panellen"] == "1190", f"neplatna delka {spatna!r} = vychozi 1190 ({st}, {dn.get('selection', {}).get('panellen')})")
st, dc = post(dict(sel, panellen=1671))
check(dc["selection"]["panellen"] == "1671" and dc["hash"] == ceny["1671"][1], f"cislo 1671 (misto textu) se prijme ({dc['selection']['panellen']})")
st, dc = post(dict(sel, panellen="1671.0"))
check(dc["selection"]["panellen"] == "1671", "text '1671.0' se prijme jako 1671")

# ---- systemy 40 a 35: tyz slot, jine nejmensi sirky (profil 40 / 35)
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PID): SH.RECEPT, str(PID_SSE): SH.RECEPT_SSE, "9877": SH.RECEPT_40, "9878": SH.RECEPT_35})
for pid, P_ in ((9877, 40), (9878, 35)):
    sc_ = schema("cs", pid)
    check("panellen" in {s["id"] for s in sc_["slots"]}, f"system {P_}: slot panellen je ve schematu")
    st, dd = post(dict(sc_["default_selection"], w=1400), pid=pid)
    op_ = dd["options"]["panellen"]
    pot = int(math.ceil(1481 + 2 + 2 * P_))
    check(st == 200 and str(pot) in op_.get("1481", {}).get("reason", "") and "1190" not in op_, f"system {P_} W=1400: 1481 zakazano s nejmensi sirkou {pot} ({op_.get('1481', {}).get('reason', '')[:80]})")

# ---- token (klic L jen u jine delky) a model
p30, _ = SH.normalizuj(dict(base, w=2100, panellen="1481"), 30)
p_def, _ = SH.normalizuj(dict(base, w=2100), 30)
check(SH._zabal(S.sestav_stul(**p30)["parametry"]).get("L") == 1481 and "L" not in SH._zabal(S.sestav_stul(**p_def)["parametry"]), "token: klic L jen u jine nez vychozi delky")
pp, chyba = SH.over_model(SH.podepis_model(S.sestav_stul(**p30)["parametry"]))
check(chyba is None and pp["panely_delka"] == 1481.0, f"token: delka 1481 prezije podpis a rozbaleni ({chyba}, {pp and pp.get('panely_delka')})")
pp0, _ = SH.over_model(SH.podepis_model(S.sestav_stul(**p_def)["parametry"]))
check(pp0.get("panely_delka", float(S.PANEL_DELKA_VYCHOZI)) == float(S.PANEL_DELKA_VYCHOZI) and S._norm_parametry(pp0)["panely_delka"] == float(S.PANEL_DELKA_VYCHOZI), "token: starsi token bez klice L = 1190")
h_model, data = G.model_pro_parametry(S.sestav_stul(**p30)["parametry"])
check(len(data) > 100000 and h_model == G.kanonicky_hash(S.sestav_stul(**p30)["parametry"]), f"model GLB pro delku 1481 se slozi ({len(data)} B)")

# ---- shrnuti vyberu (doklad / nabidka)
for lang, popis in (("cs", "Délka panelu"), ("en", "Panel length"), ("sk", "Dĺžka panela")):
    sou = SH._souhrn_voleb(SH.normalizuj(dict(base, w=2100, panellen="1481"), 30)[1], lang, 30)
    radek = [x for x in sou if x["id"] == "panellen"]
    check(len(radek) == 1 and radek[0]["label"] == popis and radek[0]["value"] == "1481 mm", f"shrnuti {lang}: '{popis}: 1481 mm' ({radek})")
    sou0 = SH._souhrn_voleb(SH.normalizuj(dict(base, w=2100, panels=False), 30)[1], lang, 30)
    check(not [x for x in sou0 if x["id"] == "panellen"], f"shrnuti {lang}: bez panelu se delka v shrnuti neukazuje")

# ---- odkaz na vyrobni list (staff blok): vychozi delka v dotazu neni, jina ano a dotaz se da vratit na parametry
st, dk = post(dict(sel, panellen="1481"))
SH._STAV_PODLE_HASHE[dk["hash"]]
blok = SH._staff_blok(dk["hash"])
qs = dict(urllib.parse.parse_qsl(blok["vyrobni_list_url"].split("?", 1)[1]))
check(qs.get("panely_delka") == "1481.0", f"vyrobni list 1481: dotaz nese panely_delka ({qs.get('panely_delka')})")
check(S.parametry_z_dotazu(qs)["panely_delka"] == 1481.0, "vyrobni list: dotaz se da vratit na parametry generatoru")
blok0 = SH._staff_blok(post(sel)[1]["hash"])
check("panely_delka" not in blok0["vyrobni_list_url"], "vyrobni list 1190: vychozi delka v odkazu neni (odkazy beze zmeny)")
check(any(k_.startswith("Zvolit panel") for k_ in [m["text"] for c in S.ovladani_3d(S.sestav_stul(**p_def))["casti"] if c["id"] == "panely" for m in c["menu"]]), "3D menu panelu nabizi ostatni delky")

# ---- mapy dilu: kazdy dil panelu patri slotu `panels` (chybove hlasky) a prepinaci `panely` (automaticke odebrani)
check(all(SH.DIL_NA_SLOT.get(pid) == "panels" for pid in S.PANEL_PARTY), f"DIL_NA_SLOT: vsechny dily panelu -> panels ({ {pid: SH.DIL_NA_SLOT.get(pid) for pid in S.PANEL_PARTY} })")
check(all(S.PREPINAC_DILU.get(pid) == "panely" for pid in S.PANEL_PARTY), f"PREPINAC_DILU: vsechny dily panelu -> panely ({ {pid: S.PREPINAC_DILU.get(pid) for pid in S.PANEL_PARTY} })")

# ---- klic cache resolve nese POZADOVANOU delku (jinak by snizena 1975 -> 1481 a primo zvolena 1481 sdilely odpoved i s oznamenim)
for poradi in (("1975", "1481"), ("1481", "1975")):
    SH._RESOLVE_CACHE.clear()
    out = {}
    for k in poradi:
        st, dd = post(dict(base, w=1600, panellen=k))
        out[k] = [n["slot"] for n in dd["notices"] if n["slot"] == "panellen"]
        check(dd["selection"]["panellen"] == "1481", f"cache {poradi}: w=1600 panellen={k} -> vybrano 1481 ({dd['selection']['panellen']})")
    check(out["1975"] == ["panellen"] and out["1481"] == [], f"cache {poradi}: oznameni o snizeni JEN u pozadovane 1975, ne u prime 1481 ({out})")

# ---- nazvy dilu v neutralnim kusovniku (kosik / nabidka) rozlisuji delky panelu
for k in DELKY:
    gen_k = S.sestav_stul(**SH.normalizuj(dict(sel, panellen=k), 30)[0])
    bom = SH._neutralni_bom(gen_k["dily"])
    pan = [x for x in bom if x["nazev"].startswith("perforovaný panel")]
    ocek = "perforovaný panel" if k == "1190" else f"perforovaný panel {k} mm"
    check(len(pan) == 1 and pan[0]["nazev"] == ocek and pan[0]["mnozstvi"] == 1, f"bom {k}: polozka '{ocek}' x 1 ({pan})")

# ---- nizke zadni stojky: panel 1671 (455 mm) se vejde na nizsi stojky nez ostatni (451 mm rozdil 5), volba delky to zohlednuje
st, dh = post(dict(base, w=2100, panellen="1975", posth=521))
typ = {"1190": None}
check(dh["selection"]["panellen"] == "1671" and dh["valid"], f"stojky 521 + 1975: snizeno na 1671 ({dh['selection']['panellen']})")
opd = dh["options"]["panellen"]
check(set(opd) == {"1481", "1975", "1190"} and all(("524" in opd[k]["reason"]) for k in opd), f"stojky 521: ostatni delky zakazane s duvodem 'stojky aspon 524 mm' ({ {k: v['reason'][:60] for k, v in opd.items()} })")
check(any("1671" in n["message"] for n in dh["notices"] if n["slot"] == "panellen"), "stojky 521: oznameni o snizeni na 1671")

# ---- GATE: verejnost vidi nove delky az po aktivaci karty (pravidlo 54), zamestnanec vsechny
c_adm = appmod.get_conn()
cu_adm = c_adm.cursor()
cu_adm.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN_ID = cu_adm.fetchone()["id"]
c_adm.rollback()
staff = appmod.app.test_client()
with staff.session_transaction() as _s:
    _s["user_id"] = ADMIN_ID
ceny_g = {}
for stav, aktivni in (("zadna nova karta aktivni", set()), ("jen 1481 aktivni", {1481}), ("vsechny aktivni", {1481, 1671, 1975})):
    nastav_aktivni(aktivni)
    SH._RESOLVE_CACHE.clear()
    # schema: verejnost jen nabizene delky (bez nich slot vubec neni, ani ve vychozim vyberu), zamestnanec vsechny
    sc_v = anon.get(f"/api/shop/products/{PID}/configurator").get_json()
    sl_v = {x["id"]: x for x in sc_v["slots"]}
    sc_s = staff.get(f"/api/shop/products/{PID}/configurator").get_json()
    sl_s = {x["id"]: x for x in sc_s["slots"]}
    nabizene = sorted({1190, *aktivni})
    if aktivni:
        check([o["id"] for o in sl_v["panellen"]["options"]] == [str(d) for d in nabizene], f"GATE schema verejnost ({stav}): volby {nabizene} ({[o['id'] for o in sl_v.get('panellen', {}).get('options', [])]})")
        check("panellen" in sc_v["default_selection"], f"GATE schema verejnost ({stav}): vychozi vyber ma panellen")
    else:
        check("panellen" not in sl_v and "panellen" not in sc_v["default_selection"], f"GATE schema verejnost ({stav}): slot panellen neni (ani ve vychozim vyberu) - verejne se nic nezmeni")
    check(set(sl_v) == set(sc_v["default_selection"]), f"GATE schema verejnost ({stav}): klice vychoziho vyberu == sloty")
    check([o["id"] for o in sl_s["panellen"]["options"]] == DELKY and "panellen" in sc_s["default_selection"], f"GATE schema zamestnanec ({stav}): vsechny 4 delky")
    for k in DELKY:
        st, dg = post(dict(sel, panellen=k))
        ocek = k if int(k) in ({S.PANEL_DELKA_VYCHOZI} | aktivni) else "1190"
        check(st == 200 and dg["valid"] and dg["selection"]["panellen"] == ocek, f"GATE verejnost ({stav}) panellen={k}: vybrano {ocek} ({dg.get('selection', {}).get('panellen')})")
        ceny_g[(stav, k)] = dg["price"]["net"]
        if k == "1975":
            opg = dg["options"]["panellen"]
            if not aktivni:
                check(opg == {"hidden": True}, f"GATE verejnost ({stav}): options.panellen = hidden ({opg})")
            elif aktivni == {1481}:
                check(set(opg) == {"1671", "1975"} and all(o["disabled"] and o["reason"] for o in opg.values()), f"GATE verejnost ({stav}): neaktivni delky zakazane s duvodem ({sorted(opg)})")
                for lang, txt in (("cs", "není v nabídce"), ("en", "not available"), ("sk", "nie je v ponuke")):
                    stl, dl = post(dict(sel, panellen="1975"), lang)
                    check(txt in dl["options"]["panellen"]["1975"]["reason"], f"GATE verejnost ({stav}) {lang}: duvod '{txt}' ({dl['options']['panellen']['1975']['reason']})")
            else:
                check(opg == {}, f"GATE verejnost ({stav}): vse v nabidce, na 2100 mm vse se vejde ({opg})")
    # zamestnanec vidi vsechny delky vzdy
    for k in DELKY:
        rs = staff.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": dict(sel, panellen=k), "lang": "cs", "staff": True})
        ds = rs.get_json()
        check(rs.status_code == 200 and ds["selection"]["panellen"] == k, f"GATE zamestnanec ({stav}) panellen={k}: vybrano {k} ({ds.get('selection', {}).get('panellen')})")
        check(ds["options"]["panellen"] == {}, f"GATE zamestnanec ({stav}): vsechny delky v nabidce ({ds['options']['panellen']})")
check(ceny_g[("zadna nova karta aktivni", "1975")] == ceny_g[("zadna nova karta aktivni", "1190")], "GATE: neaktivni delka 1975 = cena panelu 1190 (verejnost ji nedostane)")
check(ceny_g[("vsechny aktivni", "1975")] > ceny_g[("vsechny aktivni", "1190")], "GATE: po aktivaci je 1975 dražší než 1190")
# kosik / objednavka: bot5 funkce jde pres normalizuj -> pozadavek verejnosti s neaktivni delkou dostane 1190
nastav_aktivni(set())
with appmod.app.test_request_context("/"):
    pv, _ = SH.normalizuj(dict(sel, panellen="1975"), 30)
check(pv["panely_delka"] == float(S.PANEL_DELKA_VYCHOZI), f"GATE: normalizuj v pozadavku verejnosti zahodi neaktivni delku ({pv['panely_delka']})")
pk, _ = SH.normalizuj(dict(sel, panellen="1975"), 30)
check(pk["panely_delka"] == 1975.0, f"GATE: normalizuj mimo pozadavek (skripty, testy) bere vsechny delky ({pk['panely_delka']})")
nastav_aktivni({1481, 1671, 1975})

print()
if FAILS:
    print(f"CHYBA: {len(FAILS)} kontrol selhalo, {OK} OK")
    sys.exit(1)
print(f"{OK} kontrol OK")
