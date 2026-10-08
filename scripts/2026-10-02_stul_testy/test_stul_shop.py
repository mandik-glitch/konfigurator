#!/usr/bin/env python3
"""Test verejneho API konfiguratoru stolu pro e-shop/mini-shop (api/stul_shop.py) - bot8, 2026-10-02.

SKUTECNE routy pres Flask test_client BEZ prihlaseni (jsou verejne). DB se jen CTE (katalog cen pro cenu konfigurace);
mapovani produktu (app_settings.configurator_products) se v testu podstrci primo do cache modulu - nic se nezapisuje.
Hlida kontrakt docs/KONTRAKT_KONFIGURATOR_UI.md: schema (sloty, typy, slidery, vychozi vyber), resolve (normalizace, cena, platnost,
chyby po slotech, stavy voleb vcetne meznich hodnot sliderů, model s podepsanym odkazem), rules_changed 409, 404 pro nekonfigurovatelny
produkt, podpis a platnost odkazu na GLB (403/410), rate limit 429 + Retry-After, anglicke texty.

Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
    --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_shop.py"""
import base64
import json
import os
import sys
import threading
import time

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
finally:
    threading.Thread.start = _orig

# ZIVA PRAVIDLA NEOVLIVNI TEST: Robert nastavuje pravidla stolu (cena vyrezu, prah hloubky/sirky ...) v okne Pravidla -> app_settings `stul_pravidla`; routa je pri kazdem pozadavku nacte do
# generatoru (stul_api.obnov_pravidla). Test pocita s vychozimi pravidly, proto je pripne a obnovu z DB vypne (2026-10-04: Robertova cena vyrezu 2800 Kc shodila dve kontroly "vyrez cenu nemeni").
import stul_api as _stul_api  # noqa: E402
S.nastav_pravidla({})
_stul_api.obnov_pravidla = lambda force=False: None
if hasattr(SH, "_DELKY_CACHE"):                                       # delky perforovaneho panelu (2026-10-07): verejnost dostane nove delky az po aktivaci karet (pravidlo 54); test pocita se vsemi (gating: test_panely_delky_shop.py)
    SH._DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset(S.PANEL_DELKY))

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


PID = 9876
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PID): SH.RECEPT})        # podstrceno: produkt PID je konfigurovatelny stul
anon = appmod.app.test_client()


def post(body, c=None):
    return (c or anon).post("/api/shop/configurator/resolve", json=body)


# --- schema ---
r = anon.get(f"/api/shop/products/{PID}/configurator")
sc = r.get_json()
check(r.status_code == 200, f"schema 200 bez prihlaseni ({r.status_code})")
slots = {s["id"]: s for s in sc["slots"]}
check(set(slots) == set(SH.VYCHOZI_VYBER), f"sloty = vychozi vyber ({sorted(slots)})")
check(set(sc["default_selection"]) == set(slots), "default_selection ma klic pro kazdy slot")
check(all(s["type"] in ("slider", "toggle", "select") for s in sc["slots"]) and {s["id"] for s in sc["slots"] if s["type"] == "select"} == {"petleg", "petface", "midsupport", "panellen", "ledlen", "upshelftype", "upshelfboard"}, "typy slotu: slider/toggle + selecty petleg, petface, midsupport, panellen (delka panelu), ledlen (delka svitidla LED, 2026-10-07)")
check(all(("slider" in s and s["slider"]["step"] > 0 and s["slider"]["min"] < s["slider"]["max"]) for s in sc["slots"] if s["type"] == "slider"), "slidery maji min < max a krok")
check(all(s["group"] in {g["id"] for g in sc["groups"]} for s in sc["slots"]), "kazdy slot ma existujici skupinu")
check(sc["rules_version"] == G.RULES_VERSION, "rules_version ve schematu")
check(slots["w"]["slider"]["min"] == 500 and slots["w"]["slider"]["max"] == 3000 and slots["h"]["slider"]["min"] == 140, "rozsahy z pozadavku Roberta")
check("Šířka" in slots["w"]["label"] and sc["groups"][0]["label"] == "Rozměry", "cesky texty")
sc_en = anon.get(f"/api/shop/products/{PID}/configurator?lang=en").get_json()
check({s["id"]: s for s in sc_en["slots"]}["w"]["label"] == "Worktop width", "anglicke texty (?lang=en)")
check(anon.get("/api/shop/products/1/configurator").status_code == 404, "nekonfigurovatelny produkt = 404")

# --- resolve: vychozi ---
r = post({"product_id": PID, "selection": sc["default_selection"], "rules_version": sc["rules_version"]})
d = r.get_json()
check(r.status_code == 200 and d["valid"] is True and d["errors"] == [], f"vychozi vyber je platny ({r.status_code} {d.get('errors')})")
check(d["price"]["net"] > 1000 and d["price"]["gross"] > d["price"]["net"] and d["price"]["currency"] == "CZK", f"cena ({d['price']})")
check(d["selection"] == sc["default_selection"], f"normalizovany vyber = vychozi ({d['selection']})")
check(len(d["hash"]) == 16 and d["kod"] == "STL-" + d["hash"][:6].upper(), "hash a kod")
check(d["model"]["stav"] == "hotovo" and d["model"]["url"].startswith("/api/shop/configurator/glb/"), "model: hotovo + podepsany odkaz")
check(set(d["options"]) == set(slots), "options pro kazdy slot")
check(all("min" in d["options"][k] and "max" in d["options"][k] for k in ("w", "d", "h", "mid", "boxpos")), "slidery nesou min/max")
check(all(d["options"][k]["on"]["disabled"] is False for k in SH.PREPINACE if k not in ("feet", "sleeve")) and d["options"]["feet"]["on"]["disabled"] and d["options"]["feet"]["on"]["reason"] and "sleeve" not in d["options"],
      "vse zapnuto = nic neni disabled (jen stavitelne patky: s kolecky nejdou); sikme vzpery se vejdou i s panelem (panel sedi mezi stojkami)")
check(d["options"]["braces"]["on"]["disabled"] is False and d["options"]["braces"]["on"]["price_delta"] > 0 and d["options"]["bracelen"] == {"min": 300, "max": 300}
      and (lambda ob: ob["min"] < ob["max"])(post({"product_id": PID, "selection": {"braces": True}}).get_json()["options"]["bracelen"]),
      f"vzpery u vychozi sirky 1280 s panelem jdou zapnout; posuvnik delky je zamceny, dokud nejsou zapnute, a pak ma rozsah ({d['options']['braces']['on']}, {d['options']['bracelen']})")
# konce noh: bez koleček zaslepky, patky jdou zapnout a meni cenu; s kolecky se patky ignoruji
nb = post({"product_id": PID, "selection": {"wheels": False}}).get_json()
check(nb["valid"] and nb["selection"]["feet"] is False and nb["options"]["feet"]["on"]["disabled"] is False and nb["options"]["feet"]["on"]["price_delta"] > 0, f"bez koleček: patky lze zapnout ({nb['options']['feet']['on']})")
pf = post({"product_id": PID, "selection": {"wheels": False, "feet": True}}).get_json()
check(pf["valid"] and pf["selection"]["feet"] is True and pf["hash"] != nb["hash"] and pf["price"]["net"] > nb["price"]["net"], "patky: jina konfigurace, drazsi nez zaslepky")
pk = post({"product_id": PID, "selection": {"wheels": True, "feet": True}}).get_json()
check(pk["selection"]["feet"] is False, "s kolecky se patky ignoruji (v efektivnim vyberu vypnute)")
pn = post({"product_id": PID, "selection": {"wheels": False, "feet": True, "h": 140}}).get_json()
check(pn["selection"]["feet"] is False and any(n["slot"] == "feet" for n in pn["notices"]), f"nizky stul: patky se samy odeberou a je upozorneni ({pn['notices']})")
tk = SH._zabal(SH.normalizuj({"wheels": False, "feet": True})[0])
check(SH._rozbal(tk)["patky"] is True and SH._rozbal(SH._zabal(SH.normalizuj({"wheels": False})[0]))["patky"] is False, "token: patky v bitu 7 (zpetne kompatibilni)")
check(d["options"]["mid"] == {"min": 50, "max": 50} and d["options"]["boxpos"] == {"min": -500, "max": 30, "value": 0, "fits": True},
      f"stredni noha pod 1500 je zafixovana; posun supliku ma PRESNE meze (od nohou aspon 30 mm), ne hrube -(w-700)..80 ({d['options']['mid']}, {d['options']['boxpos']})")
check(d["options"]["w"]["min"] == 500 and d["options"]["h"]["min"] == 140 and d["options"]["d"]["min"] == 400, f"slidery rozmeru nesou cely rozsah (kratsi rozmer = automaticke odebrani prislusenstvi, ne omezeni posuvniku) ({d['options']['w']}, {d['options']['h']}, {d['options']['d']})")

# --- resolve: normalizace a ceny voleb ---
r = post({"product_id": PID, "selection": {"w": 99999, "d": "x", "h": -5, "shelf": False, "nesmysl": 1}})
d2 = r.get_json()
check(r.status_code == 200 and d2["selection"]["w"] == 3000 and d2["selection"]["d"] == 800 and d2["selection"]["h"] == 140 and d2["selection"]["shelf"] == 0 and "nesmysl" not in d2["selection"],
      f"normalizace: orez, vychozi, zahozeni neznameho ({d2['selection']})")
off = {"shelf": False, "wheels": False, "panels": False, "led": False, "drawers": False, "socket": False, "pet": False}
d3 = post({"product_id": PID, "selection": dict(off)}).get_json()
check(d3["valid"] and d3["price"]["net"] < d["price"]["net"], f"holy stul je levnejsi ({d3['price']['net']} < {d['price']['net']})")
check(all(d3["options"][k]["on"]["price_delta"] > 0 for k in SH.PREPINACE if k not in ("socket", "posts", "braces", "drawleft", "ledlight", "shelfboard")), f"zapnuti kazde volby (drawleft je zrcadleni, ledlight bez led a shelfboard bez polic nic nemeni = cena se nemeni) ma kladny priplatek ({[d3['options'][k]['on']['price_delta'] for k in SH.PREPINACE]})")
check(d3["options"]["braces"]["on"]["disabled"] and d3["options"]["braces"]["on"]["reason"], "vzpery bez LED: disabled + duvod")
check(d3["options"]["socket"]["on"]["disabled"] and d3["options"]["socket"]["on"]["reason"], "elektrozlab bez panelu: disabled + duvod")
check(abs(d3["price"]["net"] + d3["options"]["panels"]["on"]["price_delta"] - post({"product_id": PID, "selection": {**off, "panels": True}}).get_json()["price"]["net"]) < 0.01, "priplatek panelu = rozdil cen")

# --- neplatne kombinace: chyby po slotech, platne=False, volby s duvodem ---
bad = post({"product_id": PID, "selection": {"w": 1100}}).get_json()   # panely + LED na stul uzsi nez 1200 = automaticky odebrany (Robert)
check(bad["valid"] is True and bad["errors"] == [] and bad["selection"]["panels"] is False and bad["selection"]["led"] is False and bad["selection"]["socket"] is False,
      f"w=1100: panely, LED a elektrozlab se automaticky odeberou, vyber je platny ({bad['selection']})")
check({n["slot"] for n in bad["notices"]} >= {"panels", "led"} and all(n["action"] == "removed" and n["message"] for n in bad["notices"]), f"w=1100: upozorneni na automaticke odebrani ({bad['notices']})")
check(bad["options"]["panels"]["on"]["disabled"] and bad["options"]["panels"]["on"].get("suggest") == {"w": 1260} and "1260" in bad["options"]["panels"]["on"]["suggest_label"] and "1252" in bad["options"]["panels"]["on"]["reason"],
      f"w=1100: panel (1190 + 2 x 1 mm + 2 x 30 mm = 1252) se nevejde, zapnuti panelu nabidne roztazeni na 1260 mm ({bad['options']['panels']['on']})")
# posun = nabidka smazani (offers), kolize zustane
pos = post({"product_id": PID, "selection": {"boxpos": 80}}).get_json()
check(pos["valid"] is False and any(o["slot"] == "drawers" and o["action"] == "remove" and o["label"] for o in pos["offers"]) and pos["selection"]["drawers"] is True,
      f"posun supliku do nohy: nabidka 'Odebrat suliky' (offers), supliky zustavaji ({pos['offers']}, valid {pos['valid']})")
nar = post({"product_id": PID, "selection": {**off, "w": 1100, "d": 600}}).get_json()
check(nar["valid"] and nar["options"]["panels"]["on"]["disabled"] and nar["options"]["panels"]["on"]["reason"], f"uzky stul: panely nejdou zapnout + duvod ({nar['options']['panels']['on']})")
check(nar["options"]["drawers"]["on"]["disabled"], "melky stul: supliky nejdou zapnout")

# --- zadni stojky ---
check("posts" in slots and slots["posts"]["type"] == "toggle", "schema ma prepinac Zadni stojky (posts)")
check(sc["default_selection"]["posts"] is True and d["selection"]["posts"] is True, "zadni stojky jsou ve vychozim vyberu zapnute")
nos = post({"product_id": PID, "selection": {**off, "posts": False}}).get_json()
check(nos["valid"] and nos["price"]["net"] < d3["price"]["net"], f"bez zadnich stojek (a bez panelu/LED): platne a levnejsi nez se stojkami ({nos['price']['net']} < {d3['price']['net']})")
check(nos["options"]["panels"]["on"]["disabled"] and "stojky" in nos["options"]["panels"]["on"]["reason"].lower(), f"bez stojek: panely nejdou zapnout + duvod ({nos['options']['panels']['on']['reason']})")
bad_p = post({"product_id": PID, "selection": {"posts": False}}).get_json()
check(bad_p["valid"] and bad_p["selection"]["panels"] is False and bad_p["selection"]["led"] is False and {n["slot"] for n in bad_p["notices"]} >= {"panels", "led", "socket"},
      f"stojky vypnute + panely zapnute: panely/LED/elektrozlab se automaticky odeberou ({bad_p['notices']})")
tok2 = nos["model"]["url"].rsplit("/", 1)[1]
check(SH.over_model(tok2)[0]["stojky"] is False, "token nese vypnute stojky")

# --- stredni noha, posun supliku ---
wd = post({"product_id": PID, "selection": {"w": 2400}}).get_json()
check(wd["valid"] and wd["options"]["mid"]["min"] < 50 < wd["options"]["mid"]["max"], f"nad 1500 mm: stredni noha ma rozsah ({wd['options']['mid']})")
mid = post({"product_id": PID, "selection": {"w": 2400, "mid": 20}}).get_json()
check(mid["valid"] and mid["selection"]["mid"] == 20 and mid["hash"] != wd["hash"], "poloha stredni nohy meni konfiguraci")
midc = post({"product_id": PID, "selection": {"w": 2400, "mid": 1}}).get_json()
check(midc["selection"]["mid"] == wd["options"]["mid"]["min"], f"poloha stredni nohy se orizne na minimum ({midc['selection']['mid']})")
bm = post({"product_id": PID, "selection": {"w": 2000}}).get_json()["options"]["boxpos"]            # presne meze posunu pro sirku 2000 se stredni nohou
bx = post({"product_id": PID, "selection": {"w": 2000, "boxpos": bm["min"]}}).get_json()
check(bx["valid"] and bx["selection"]["boxpos"] == bm["min"], f"posun supliku az na minimum z options ({bm}) jde")
bx3 = post({"product_id": PID, "selection": {"w": 2000, "boxpos": bm["min"] - 10}}).get_json()   # o krok pod minimum: box se priblizi stredni noze/uhelniku na mene nez 30 mm -> kolize
check(bx3["valid"] is False and any(o["slot"] == "drawers" and o["action"] == "remove" for o in bx3["offers"]),
      f"posun supliku o krok pod minimum je kolize a nabidne smazani supliku ({bx3['valid']}, {bx3['offers']})")
bx4 = post({"product_id": PID, "selection": {"w": 2000, "boxpos": bm["max"] + 10}}).get_json()
check(bx4["valid"] is False or bm["max"] + 10 > 80, "posun supliku o krok nad maximum je kolize")
check(post({"product_id": PID, "selection": {**off, "boxpos": -300}}).get_json()["selection"]["boxpos"] == 0, "bez supliku se posun vynuluje")

# --- vyrezy v pracovni desce (Robert): cut1..cut3 + cut<n>w/d/x/z ---
CUT_SLOTY = [f"cut{n}{s}" for n in (1, 2, 3) for s in ("", "w", "d", "x", "z")]
check(all(s in slots for s in CUT_SLOTY) and "g_cuts" in {g_["id"] for g_ in sc["groups"]}, "schema: sloty vyrezu a skupina g_cuts")
check(all(slots[f"cut{n}"]["type"] == "toggle" and slots[f"cut{n}w"]["type"] == "slider" and slots[f"cut{n}w"]["group"] == "g_cuts" for n in (1, 2, 3)), "vyrez: toggle + slidery ve skupine g_cuts")
check(sc["default_selection"]["cut1"] is False and sc["default_selection"]["cut1w"] == 200 and sc["default_selection"]["cut2z"] == 360, "vyrezy jsou ve vychozim vyberu vypnute")
cd0 = post({"product_id": PID, "selection": {}}).get_json()
check(cd0["selection"]["cut1"] is False and cd0["valid"] and cd0["options"]["cut1"]["on"] == {"price_delta": 0, "disabled": False, "reason": None}, "vychozi: vyrez vypnuty, lze zapnout, cena se nemeni")
check(cd0["options"]["cut1w"]["min"] == cd0["options"]["cut1w"]["max"] == 200, f"vypnuty vyrez: posuvniky zamcene ({cd0['options']['cut1w']})")
cd1 = post({"product_id": PID, "selection": {"cut1": True}}).get_json()
check(cd1["valid"] and cd1["selection"]["cut1"] is True and cd1["selection"]["cut1w"] == 200 and cd1["selection"]["cut1x"] == 100 and cd1["selection"]["cut1z"] == 100, f"zapnuty vyrez ma vychozi rozmery ({cd1['selection']})")
check(cd1["hash"] != cd0["hash"] and cd1["price"]["net"] == cd0["price"]["net"], f"vyrez meni model (hash), ne cenu desky ({cd0['price']['net']} -> {cd1['price']['net']})")
check(cd1["options"]["cut1w"] == {"min": 50, "max": 1220} and cd1["options"]["cut1d"] == {"min": 50, "max": 740} and cd1["options"]["cut1x"] == {"min": 30, "max": 620} and cd1["options"]["cut1z"] == {"min": 30, "max": 1050},
      f"meze posuvniku vyrezu podle desky 1280 x 800 a rozmeru vyrezu ({ {k: cd1['options'][k] for k in ('cut1w', 'cut1d', 'cut1x', 'cut1z')} })")
g_vyr = anon.get(cd1["model"]["url"])
g_zakl = anon.get(cd0["model"]["url"])
check(g_vyr.status_code == 200 and g_vyr.data[:4] == b"glTF" and g_vyr.data != g_zakl.data, "GLB s vyrezem se sklada a lisi se od zakladniho")
h_vyr, data_vyr = G.model_pro_parametry(SH.normalizuj({"cut1": True})[0])
check(g_vyr.data == data_vyr, "GLB z odkazu == GLB z generatoru (vyrez)")
tok_c = cd1["model"]["url"].rsplit("/", 1)[1].split(".")[0]
pay_c = json.loads(base64.urlsafe_b64decode(tok_c + "=" * (-len(tok_c) % 4)))
check(pay_c.get("c") == [[200.0, 150.0, 100.0, 100.0], 0, 0], f"token nese vyrezy jako cisla ({pay_c.get('c')})")
# vypnuty vyrez nema vliv na hash (stejna konfigurace = stejny hash), zapnuty ano
check(post({"product_id": PID, "selection": {"cut2": False, "cut2w": 700, "cut3x": 400}}).get_json()["hash"] == cd0["hash"], "vypnute vyrezy s jinymi rozmery = stejny hash")
check(post({"product_id": PID, "selection": {"cut1": True, "cut1w": 300}}).get_json()["hash"] != cd1["hash"], "rozmer zapnuteho vyrezu meni hash")
# round trip tokenu
pc, _ = SH.normalizuj({"cut1": True, "cut3": True, "cut3x": 250, "cut3w": 120})
pc2 = SH._rozbal(json.loads(SH._unb64(SH.podepis_model(pc).split(".")[0])))
check(G.kanonicky_hash(pc2) == G.kanonicky_hash(pc) and pc2.get("vyrez3") and not pc2.get("vyrez2"), "token -> parametry: vyrezy se zachovaji (stejny hash)")
check(not SH._rozbal({"w": 1200, "d": 800, "h": 840, "t": 126, "p": 1}).get("vyrez1"), "stary token bez klice c = zadne vyrezy")
# oriznuti na desku
cd2 = post({"product_id": PID, "selection": {"w": 500, "d": 400, "cut1": True, "cut1w": 900, "cut1d": 900}}).get_json()
check(cd2["selection"]["cut1w"] == 440 and cd2["selection"]["cut1d"] == 340 and cd2["options"]["cut1x"] == {"min": 30, "max": 30}, f"vyrez se zmensi na desku minus 2 x 30 mm ({cd2['selection']['cut1w']}, {cd2['selection']['cut1d']}, {cd2['options']['cut1x']})")
# prekryv: valid false + nabidka odebrani + hlaska u slotu
cd3 = post({"product_id": PID, "selection": {"cut1": True, "cut2": True, "cut2z": 150}}).get_json()
check(cd3["valid"] is False and any(e["slot"] == "cut2" and "30 mm" in e["message"] for e in cd3["errors"]), f"prekryv vyrezu: chyba u slotu cut2 ({cd3['errors']})")
check(any(o["slot"] == "cut2" and o["action"] == "remove" and o["label"] == "Odebrat výřez 2" for o in cd3["offers"]), f"prekryv vyrezu: nabidka odebrani ({cd3['offers']})")
cd3b = post({"product_id": PID, "selection": {**cd3["selection"], "cut2": False}}).get_json()
check(cd3b["valid"] and cd3b["selection"]["cut2"] is False, "po odebrani druheho vyrezu je konfigurace zase platna")
cd4 = post({"product_id": PID, "selection": {"cut1": True, "cut2": True, "cut2z": 150}, "lang": "en"}).get_json()
check(any(o["label"] == "Remove cutout 2" for o in cd4["offers"]) and any(e["message"].startswith("The cutouts overlap") for e in cd4["errors"]), f"anglicke texty vyrezu ({cd4['offers']})")
cd5 = post({"product_id": PID, "selection": {"cut1": True, "cut2": True, "cut2z": 330}}).get_json()
check(cd5["valid"] and cd5["selection"]["cut2z"] == 330, "dva vyrezy s mezerou 30 mm jsou platne")
check(slots["cut1"]["label"] == "Výřez 1" and sc_en["slots"][[s_["id"] for s_ in sc_en["slots"]].index("cut2w")]["label"].startswith("Cutout 2"), "popisky vyrezu cs/en")

# --- police pod vyrezem (cut<n>shelf) a loziskove jednotky (bearings/bearpitch/bearedge) ---
check(all(f"cut{n}shelf" in slots and slots[f"cut{n}shelf"]["type"] == "toggle" and slots[f"cut{n}shelf"]["group"] == "g_cuts" for n in (1, 2, 3)), "schema: toggle police pod vyrezem ve skupine g_cuts")
check("g_bearings" in {g_["id"] for g_ in sc["groups"]} and slots["bearings"]["type"] == "toggle" and slots["bearings"]["group"] == "g_bearings", "schema: toggle loziskovych jednotek ve skupine g_bearings")
check(slots["bearpitch"]["slider"] == {"min": 40, "max": 1000, "step": 10, "unit": "mm"} and slots["bearedge"]["slider"] == {"min": 30, "max": 500, "step": 10, "unit": "mm"},
      f"schema: slidery rozteče a okraje ({slots['bearpitch']['slider']}, {slots['bearedge']['slider']})")
ds = sc["default_selection"]
check(ds["cut1shelf"] is False and ds["bearings"] is False and ds["bearpitch"] == 200 and ds["bearedge"] == 100, "vychozi vyber: police a jednotky vypnute, 200 / 100 mm")
check(cd0["selection"]["bearings"] is False and cd0["selection"]["cut1shelf"] is False and cd0["valid"], "vychozi: police ani jednotky nejsou zapnute")
check(cd0["options"]["cut1shelf"]["on"]["disabled"] and "výřez" in cd0["options"]["cut1shelf"]["on"]["reason"], f"police bez zapnuteho vyrezu je zakazana s duvodem ({cd0['options']['cut1shelf']})")
check(cd0["options"]["bearpitch"] == {"min": 200, "max": 200} and cd0["options"]["bearedge"] == {"min": 100, "max": 100}, "vypnute jednotky: posuvniky zamcene (min = max)")
b0 = cd0["options"]["bearings"]
check(b0["on"]["disabled"] is False and 24 * 50 <= b0["on"]["price_delta"] <= 24 * 80 and b0["count"] == {"placed": 24, "omitted": 0}, f"jednotky vypnute: price_delta ~ 24 x cena karty, count 24 ({b0})")
bd = post({"product_id": PID, "selection": {"bearings": True}}).get_json()
check(bd["valid"] and bd["selection"]["bearings"] is True and bd["hash"] != cd0["hash"] and bd["options"]["bearings"]["count"] == {"placed": 24, "omitted": 0}, "jednotky zapnute: platne, jiny hash, 24 ks")
check(bd["options"]["bearpitch"] == {"min": 40, "max": 1000} and bd["options"]["bearedge"] == {"min": 30, "max": 500}, f"zapnute jednotky: posuvniky odemcene ({bd['options']['bearpitch']}, {bd['options']['bearedge']})")
check(abs((bd["price"]["net"] - cd0["price"]["net"]) - b0["on"]["price_delta"]) < 0.01 and bd["options"]["bearings"]["on"]["price_delta"] == 0, "price_delta zapnuti == skutecny rozdil ceny")
bp = post({"product_id": PID, "selection": {"bearings": True, "bearpitch": 150, "bearedge": 60}}).get_json()
check(bp["valid"] and bp["selection"]["bearpitch"] == 150 and bp["selection"]["bearedge"] == 60 and bp["hash"] != bd["hash"] and bp["options"]["bearings"]["count"]["placed"] > 24, f"rozteč a okraj meni pocet a hash ({bp['options']['bearings']['count']})")
check(post({"product_id": PID, "selection": {"bearings": False, "bearpitch": 90, "bearedge": 250}}).get_json()["hash"] == cd0["hash"], "vypnute jednotky s jinou roztecí = stejny hash")
bo = post({"product_id": PID, "selection": {"bearings": True, "cut1": True}}).get_json()
check(bo["valid"] and bo["options"]["bearings"]["count"]["omitted"] > 0 and bo["options"]["bearings"]["count"]["placed"] + bo["options"]["bearings"]["count"]["omitted"] == 24, f"u otvoru se jednotky vynechaji ({bo['options']['bearings']['count']})")
bm = post({"product_id": PID, "selection": {"bearings": True, "bearpitch": 40, "bearedge": 30, "w": 3000, "d": 1500}}).get_json()
check(bm["valid"] is False and any(e["slot"] == "bearpitch" and "Příliš mnoho" in e["message"] for e in bm["errors"]) and bm["options"]["bearings"]["count"]["placed"] == 0, f"nad 500 jednotek: chyba u bearpitch ({bm['errors']})")
bm_en = post({"product_id": PID, "selection": {"bearings": True, "bearpitch": 40, "bearedge": 30, "w": 3000, "d": 1500}, "lang": "en"}).get_json()
check(any(e["slot"] == "bearpitch" and e["message"].startswith("Too many ball transfer units") for e in bm_en["errors"]), "anglicka chyba jednotek")
check(slots["bearings"]["label"] == "Ložiskové jednotky (kuličkové)" and sc_en["slots"][[s_["id"] for s_ in sc_en["slots"]].index("bearings")]["label"] == "Ball transfer units"
      and slots["cut1shelf"]["label"] == "Police pod výřezem 1" and sc_en["slots"][[s_["id"] for s_ in sc_en["slots"]].index("cut2shelf")]["label"] == "Shelf under cutout 2", "popisky police a jednotek cs/en")
# police pod vyrezem
sp0 = post({"product_id": PID, "selection": {"cut1": True}}).get_json()
check(sp0["options"]["cut1shelf"]["on"]["disabled"] is False and sp0["options"]["cut1shelf"]["on"]["price_delta"] > 0, f"zapnuty vyrez: police lze zapnout, price_delta > 0 ({sp0['options']['cut1shelf']})")
sp = post({"product_id": PID, "selection": {"cut1": True, "cut1shelf": True}}).get_json()
check(sp["valid"] and sp["errors"] == [] and sp["selection"]["cut1shelf"] is True and sp["hash"] != sp0["hash"], "police pod vyrezem: platna, jiny hash")
check(abs((sp["price"]["net"] - sp0["price"]["net"]) - sp0["options"]["cut1shelf"]["on"]["price_delta"]) < 0.01 and sp["price"]["net"] > sp0["price"]["net"], "price_delta police == skutecny rozdil ceny (deska + profily)")
check(post({"product_id": PID, "selection": {"cut1": False, "cut1shelf": True}}).get_json()["hash"] == cd0["hash"], "police pri vypnutem vyrezu se ignoruje (stejny hash)")
check(post({"product_id": PID, "selection": {"cut1": False, "cut1shelf": True}}).get_json()["selection"]["cut1shelf"] is False, "police pri vypnutem vyrezu je v efektivnim vyberu vypnuta")
sk = post({"product_id": PID, "selection": {"cut1": True, "cut1shelf": True, "cut1x": 30}}).get_json()
check(sk["valid"] is False and [e["slot"] for e in sk["errors"]] == ["cut1shelf"] and sk["selection"]["drawers"] is True, f"kolize police: chyba u cut1shelf, supliky zustavaji ({sk['errors']})")
check(any(o["slot"] == "cut1shelf" and o["action"] == "remove" and o["label"] == "Odebrat polici pod výřezem 1" for o in sk["offers"]), f"kolize police: nabidka odebrani police ({sk['offers']})")
sk2 = post({"product_id": PID, "selection": {**sk["selection"], "cut1shelf": False}}).get_json()
check(sk2["valid"] and sk2["selection"]["cut1"] is True and sk2["selection"]["cut1shelf"] is False, "po odebrani police je konfigurace zase platna (vyrez zustava)")
sk_en = post({"product_id": PID, "selection": {"cut1": True, "cut1shelf": True, "cut1x": 30}, "lang": "en"}).get_json()
check(any(o["label"] == "Remove the shelf under cutout 1" for o in sk_en["offers"]) and any(e["message"].startswith("The shelf under the cutout") for e in sk_en["errors"]), "anglicke texty police")
sn = post({"product_id": PID, "selection": {"cut1": True, "cut1shelf": True, "h": 300}}).get_json()
check(sn["valid"] is False and any(e["slot"] == "cut1shelf" for e in sn["errors"]), f"nizky stul: police se nevejde ({[e['slot'] for e in sn['errors']]})")
# token a model: police i jednotky se prenaseji, GLB je shodne s generatorem
sel_tok = {"cut1": True, "cut1shelf": True, "bearings": True, "bearpitch": 150, "bearedge": 60}
st = post({"product_id": PID, "selection": sel_tok}).get_json()
ptok = SH.over_model(st["model"]["url"].rsplit("/", 1)[1])[0]
check(ptok["loz"] is True and ptok["loz_rozteca"] == 150.0 and ptok["loz_okraj"] == 60.0 and ptok["vyrez1_police"] is True and ptok["vyrez1"] is True, f"token nese police a jednotky ({ptok.get('loz')}, {ptok.get('vyrez1_police')})")
stok = SH._zabal(SH.normalizuj(sel_tok)[0])
check(stok["l"] == [150.0, 60.0] and stok["c"][0][-1] == 1 and len(stok["c"][0]) == 5, f"kompaktni token: klic l a pate cislo police ({stok})")
stary_tok = {**SH._zabal(SH.normalizuj({"cut1": True})[0])}
check(len(stary_tok["c"][0]) == 4 and "l" not in stary_tok and SH._rozbal(stary_tok)["vyrez1_police"] is False and not SH._rozbal(stary_tok).get("loz"), "starsi token (4 cisla, bez l) = bez police a bez jednotek")
check(G.model_pro_parametry(ptok)[0] == G.kanonicky_hash(SH.normalizuj(sel_tok)[0]), "hash modelu z tokenu == hash vyberu")
gst = anon.get(st["model"]["url"])
check(gst.status_code == 200 and gst.data == G.model_pro_parametry(SH.normalizuj(sel_tok)[0])[1], "GLB z odkazu (police + jednotky) == GLB z generatoru")

# --- rules_version, produkt, limity ---
r = post({"product_id": PID, "selection": {}, "rules_version": "stara"})
check(r.status_code == 409 and r.get_json()["error"] == "rules_changed", f"stara rules_version = 409 ({r.status_code})")
check(post({"product_id": 1, "selection": {}}).status_code == 404, "resolve pro nekonfigurovatelny produkt = 404")
d_en = post({"product_id": PID, "selection": {"w": 1100}, "lang": "en"}).get_json()
check(d_en["notices"] and d_en["notices"][0]["message"].startswith("Automatically removed"), f"lang=en funguje ({d_en['notices'][:1]})")

# --- model: GET model/<hash>, podepsany odkaz ---
m = anon.get(f"/api/shop/configurator/model/{d['hash']}")
check(m.status_code == 200 and m.get_json()["model"]["stav"] == "hotovo", f"GET model/<hash> ({m.status_code})")
check(anon.get("/api/shop/configurator/model/deadbeefdeadbeef").status_code == 404, "neznamy hash = 404")
url = d["model"]["url"]
g = anon.get(url)
check(g.status_code == 200 and g.mimetype == "model/gltf-binary" and g.data[:4] == b"glTF", f"GLB pres podepsany odkaz bez prihlaseni ({g.status_code})")
check(g.headers.get("Content-Disposition") == "inline" and "private" in g.headers.get("Cache-Control", "") and g.headers.get("X-Robots-Tag") == "noindex", "hlavicky GLB (inline, private, noindex)")
# kompresi GLB (Robert 2026-10-04: "model stolu se tam nacita dlouho" - 4,7 MB, gzip ~20 %, brotli ~14 %): podle Accept-Encoding br > gzip, dekomprimovane == surove, Vary, stabilni bytes z cache
import gzip as _gzip  # noqa: E402
try:
    import brotli as _brotli  # noqa: E402
except ImportError:
    _brotli = None
gz = anon.get(url, headers={"Accept-Encoding": "gzip"})
check(gz.status_code == 200 and gz.headers.get("Content-Encoding") == "gzip" and "Accept-Encoding" in gz.headers.get("Vary", "") and _gzip.decompress(gz.data) == g.data, "GLB: Accept-Encoding gzip -> gzip, po rozbaleni stejne bytes, Vary")
check(len(gz.data) < 0.35 * len(g.data), f"GLB: gzip je vyrazne mensi ({len(gz.data)} z {len(g.data)} B)")
check(anon.get(url, headers={"Accept-Encoding": "gzip"}).data == gz.data, "GLB: komprimovane bytes jsou z cache stejne")
check(g.headers.get("Content-Encoding") is None and "Accept-Encoding" in g.headers.get("Vary", ""), "GLB: bez Accept-Encoding surove bytes, Vary")
check(anon.get(url, headers={"Accept-Encoding": "identity"}).headers.get("Content-Encoding") is None, "GLB: identity -> surove")
check(anon.get(url, headers={"Accept-Encoding": "br;q=0, gzip;q=0.5"}).headers.get("Content-Encoding") == "gzip", "GLB: br;q=0 -> gzip")
check(anon.get(url, headers={"Accept-Encoding": "gzip;q=0"}).headers.get("Content-Encoding") is None, "GLB: gzip;q=0 -> surove")
if _brotli is not None:
    br = anon.get(url, headers={"Accept-Encoding": "gzip, deflate, br, zstd"})
    check(br.headers.get("Content-Encoding") == "br" and _brotli.decompress(br.data) == g.data and len(br.data) < len(gz.data), f"GLB: prohlizec (gzip, deflate, br) dostane brotli, je mensi nez gzip ({len(br.data)} B)")
else:
    check(anon.get(url, headers={"Accept-Encoding": "gzip, deflate, br"}).headers.get("Content-Encoding") == "gzip", "GLB: bez modulu brotli -> gzip")
tok = url.rsplit("/", 1)[1]
telo, exp, sig = tok.split(".")
check(anon.get(f"/api/shop/configurator/glb/{telo}.{exp}.{sig[:-2]}AA").status_code == 403, "pozmeneny podpis = 403")
check(anon.get(f"/api/shop/configurator/glb/{telo}x.{exp}.{sig}").status_code == 403, "pozmenene parametry = 403")
check(anon.get(f"/api/shop/configurator/glb/{telo}.{int(exp) + 999999}.{sig}").status_code == 403, "pozmenena platnost = 403")
stary = SH.podepis_model(SH.normalizuj({})[0], ted=time.time() - SH.MODEL_PLATNOST_S - 5)
check(anon.get(f"/api/shop/configurator/glb/{stary}").status_code == 410, "vyprseny odkaz = 410")
check(anon.get("/api/shop/configurator/glb/nesmysl").status_code == 403, "nesmyslny token = 403")
check(SH.over_model(tok)[0]["stojky"] is True and SH.over_model(tok)[0]["police"] == 1, "token se zapnutymi stojkami a 1 policou")
p_ok = SH.over_model(tok)[0]
check(p_ok and p_ok["sirka"] == float(S.VYCHOZI["sirka"]), "over_model vrati parametry (vychozi sirka)")
# model je ten, ktery vraci generator pro dane parametry
h_gen, data_gen = G.model_pro_parametry(SH.normalizuj({})[0])
check(g.data == data_gen, "GLB z odkazu == GLB z generatoru pro stejne parametry")

# --- zadne technicke udaje v odpovedich (bot3: bez dodavatele, SKU a internich nazvu dilu) ---
import re  # noqa: E402
ZAKAZANE = [r"#\d", r"product_", r"Object_", r"STUL\.SYSTEM30", r"\bSKU\b", r"\bsku\b", r"Z -?\d", r"…", r"\b(4930|4931|4929|4932|4928|4916|4933|3158)\b",
            r"[Vv]andr", r"katalog", r"profil 30", r"spojk", r"laminodesk", r"dily", r"quaternion", r'"position"']
vzorky = [{}, {"w": 1100}, {"w": 3000, "d": 1500, "h": 1200}, {"h": 150}, {"h": 450}, {"d": 600}, {**off, "socket": True}, {"w": 2400, "mid": 20, "boxpos": -300},
          {"w": 700, "d": 400, "h": 140}, {"w": 1500, "h": 180, "d": 901, "shelf": False},
          {"cut1": True}, {"cut1": True, "cut2": True, "cut2z": 150}, {"cut1": True, "cut1w": 900, "cut1d": 900, "w": 500, "d": 400},
          {"cut1": True, "cut1shelf": True}, {"cut1": True, "cut1shelf": True, "cut1x": 30}, {"cut1": True, "cut1shelf": True, "h": 300}, {"cut1shelf": True},
          {"bearings": True}, {"bearings": True, "cut1": True}, {"bearings": True, "bearpitch": 40, "bearedge": 30, "w": 3000, "d": 1500},
          {"braces": True}, {"braces": True, "w": 1400}, {"braces": True, "w": 1400, "bracelen": 700}, {"braces": True, "w": 1400, "arm": 200}, {"braces": True, "w": 1400, "posts": False},
          {"braces": True, "w": 2000, "panels": False, "socket": False, "bracelen": 450}]
for lang in ("cs", "en"):
    for v in vzorky:
        txt = json.dumps(post({"product_id": PID, "selection": v, "lang": lang}).get_json(), ensure_ascii=False)
        # model.url je podepsany token (base64) - nepocita se jako text, kontrolujeme ho zvlast
        txt = re.sub(r'"url": "[^"]*"', '"url": ""', txt)
        spatne = [z for z in ZAKAZANE if re.search(z, txt)]
        check(not spatne, f"[{lang}] {v}: v odpovedi nejsou technicke udaje ({spatne})")
for lang in ("cs", "en"):
    txt = json.dumps(anon.get(f"/api/shop/products/{PID}/configurator?lang={lang}").get_json(), ensure_ascii=False)
    spatne = [z for z in ZAKAZANE if re.search(z, txt)]
    check(not spatne, f"[{lang}] schema bez technickych udaju ({spatne})")
# GLB: zadne nazvy dilu, jen ploske uzly (kontrola primo v GLB z odkazu)
glb_txt = g.data[20:20 + int.from_bytes(g.data[12:16], "little")].decode("utf-8", "replace")
check(all(not re.search(z, glb_txt) for z in (r"product_", r"Object_", r"katalog", r"generator", r"profil", r"STUL", r"[Vv]andr")), "GLB (JSON cast) nema nazvy dilu, katalog ani generator")
uzly_jmena = re.findall(r'"name":"([^"]+)"', glb_txt)
check(uzly_jmena[:8] == ["n0", "n1", "n2", "n3", "n4", "n5", "n6", "p1"] and all(re.fullmatch(r"n\d+", x) for x in uzly_jmena[8:]) and len(uzly_jmena) > 8,
      f"uzly maji jen ploska jmena (n0..n6, pivot p1 horniho supliku boxu a razitka loga n<i> na konci - WORKFLOW pravidlo 61, od 2026-10-08 jsou na verejnem modelu; {uzly_jmena})")
# kompaktni token: jen cisla, zadne nazvy parametru
import base64  # noqa: E402
payload = json.loads(base64.urlsafe_b64decode(telo + "=" * (-len(telo) % 4)))
check(set(payload) <= {"w", "d", "h", "o", "r", "p", "t", "b", "m", "s", "c", "l", "v"}, f"token nese jen kratke klice ({sorted(payload)})")
check(not any(k in base64.urlsafe_b64decode(telo + "=" * (-len(telo) % 4)).decode() for k in ("sirka", "suplik", "kolecka", "panely", "elektrozlab", "drzak")), "token neprozrazuje nazvy parametru")

# --- sikme vzpery ramen LED (Robert 2026-10-03): sloty braces (prepinac) a bracelen (delka 100-1000 mm), texty cs/en/sk, cena, automaticke odebrani, token, vyroba ---
sch = anon.get(f"/api/shop/products/{PID}/configurator?lang=cs").get_json()
sl = {x["id"]: x for x in sch["slots"]}
check(sl["braces"]["type"] == "toggle" and sl["braces"]["group"] == "g_extras" and sl["bracelen"]["type"] == "slider" and sl["bracelen"]["slider"] == {"min": 100, "max": 1000, "step": 10, "unit": "mm"} and sl["bracelen"]["help"],
      "schema: slot braces (prepinac) a bracelen (100-1000 mm po 10 s napovedou) v Prislusenstvi")
check(sch["default_selection"]["braces"] is False and sch["default_selection"]["bracelen"] == 300, "vychozi vyber: vzpery vypnute, delka 300")
for lg in ("cs", "en", "sk"):
    sg = anon.get(f"/api/shop/products/{PID}/configurator?lang={lg}").get_json()
    sgl = {x["id"]: x for x in sg["slots"]}
    check(sgl["braces"]["label"] and sgl["bracelen"]["label"] and sgl["bracelen"]["help"] and SH.DUVODY[lg].get("braces") and SH.NAZVY_SLOTU[lg].get("braces"), f"[{lg}] vzpery: popisky, napoveda, duvod a nazev slotu")
check(len({anon.get(f"/api/shop/products/{PID}/configurator?lang={lg}").get_json()["slots"][-1]["label"] for lg in ("cs",)}) == 1, "schema se nacte")
b0 = post({"product_id": PID, "selection": {"w": 1400}}).get_json()
b1 = post({"product_id": PID, "selection": {"w": 1400, "braces": True, "bracelen": 420}}).get_json()
bm = post({"product_id": PID, "selection": {"w": 1400, "braces": True}}).get_json()
check(b1["valid"] and b1["selection"]["braces"] is True and b1["selection"]["bracelen"] == 420 and not b1["notices"] and not b1["errors"], f"vzpery 1400/420: platne, vyber ponechan ({b1['selection'].get('braces')}, {b1['notices']})")
check(bm["price"]["net"] > b0["price"]["net"] and abs((bm["price"]["net"] - b0["price"]["net"]) - b0["options"]["braces"]["on"]["price_delta"]) < 0.01 and b0["options"]["braces"]["on"]["price_delta"] > 0
      and not b0["options"]["braces"]["on"]["disabled"], f"vzpery (vychozi delka) zdrazuji o skutecny rozdil, volba lze zapnout ({b0['options']['braces']['on']})")
check(b1["price"]["net"] > bm["price"]["net"], f"delsi vzpery jsou dražší ({bm['price']['net']} -> {b1['price']['net']})")
check(b0["options"]["bracelen"] == {"min": 300, "max": 300} and b1["options"]["bracelen"] == {"min": 100, "max": 630}, f"posuvnik delky: zamceny pri vypnutych vzperach, PRESNE meze pri zapnutych (rameno 560 -> 100-630; {b1['options']['bracelen']})")
bx = post({"product_id": PID, "selection": {"w": 1400, "braces": True, "bracelen": 1000}}).get_json()
check(bx["valid"] and not bx["errors"] and bx["selection"]["braces"] is True and bx["selection"]["bracelen"] == 630 and bx["options"]["bracelen"] == {"min": 100, "max": 630},
      f"bracelen 1000 u ramene 560: orezano na nejvetsi platnou delku 630 (vzpery zustavaji, platne; {bx['selection'].get('bracelen')})")
bd = post({"product_id": PID, "selection": {"w": 1400, "braces": True, "bracelen": 1000, "arm": 1000}}).get_json()
check(bd["valid"] and bd["selection"]["bracelen"] == 1000 and bd["options"]["bracelen"] == {"min": 100, "max": 1000}, f"rameno 1000: vzpera 1000 mm se vejde, meze 100-1000 ({bd['selection'].get('bracelen')}, {bd['options']['bracelen']})")
bk = post({"product_id": PID, "selection": {"w": 1400, "braces": True, "bracelen": 100}}).get_json()
check(bk["valid"] and bk["selection"]["bracelen"] == 100 and bk["price"]["net"] < bm["price"]["net"], f"vzpera 100 mm: platna a levnejsi nez 300 mm ({bk['selection'].get('bracelen')})")
bn = post({"product_id": PID, "selection": {"w": 1400, "braces": True, "bracelen": 50}}).get_json()
check(bn["selection"]["bracelen"] == 100, f"bracelen 50 (pod rozsah) se zarovna na 100 ({bn['selection'].get('bracelen')})")
check(b1["hash"] != b0["hash"] and b1["kod"] != b0["kod"], "vzpery meni hash/kod konfigurace")
for lg in ("cs", "en", "sk"):
    r12 = post({"product_id": PID, "lang": lg, "selection": {"w": 1200, "braces": True}}).get_json()
    check(r12["valid"] and r12["selection"]["braces"] is True and r12["selection"]["panels"] is False and any(n["slot"] == "panels" and n["action"] == "removed" for n in r12["notices"]) and not any(n["slot"] == "braces" for n in r12["notices"]),
          f"[{lg}] u sirky 1200 se odebere panel (nevejde se), vzpery zustavaji ({[n['message'][:60] for n in r12['notices']]})")
    check(r12["options"]["braces"]["on"]["disabled"] is False and r12["options"]["panels"]["on"]["disabled"] and r12["options"]["panels"]["on"]["reason"] and "1252" in r12["options"]["panels"]["on"]["reason"], f"[{lg}] u sirky 1200: vzpery jdou, panel ma duvod (1252 mm)")
rp = post({"product_id": PID, "selection": {"w": 1400, "braces": True, "posts": False}}).get_json()
check(rp["valid"] and rp["selection"]["braces"] is False and rp["selection"]["posts"] is False, "bez zadnich stojek se vzpery odeberou")
# token: tam a zpet (vzpery + delka), starsi token bez klice v = bez vzper
pz, _ = SH.normalizuj({"w": 1400, "braces": True, "bracelen": 420})
bk = SH._rozbal(SH._zabal(pz))
check(bk["vzpery"] is True and bk["vzpera_delka"] == 420.0 and bk["sirka"] == 1400, f"token: vzpery a delka tam a zpet ({bk.get('vzpery')}, {bk.get('vzpera_delka')})")
check(SH._rozbal({"w": 1200, "d": 800, "h": 840, "t": 14}).get("vzpery") is False, "starsi token bez bitu vzper = vzpery vypnute")
check(SH._rozbal(SH._zabal(SH.normalizuj({"w": 1400})[0]))["vzpery"] is False and "v" not in SH._zabal(SH.normalizuj({"w": 1400})[0]), "vypnute vzpery: token je beze zmeny (zadny novy klic)")
# GLB z odkazu obsahuje vzpery (jiny, vetsi model nez bez nich)
g1 = anon.get(b1["model"]["url"])
g0 = anon.get(b0["model"]["url"])
check(g1.status_code == 200 and g0.status_code == 200 and g1.data != g0.data and len(g1.data) > len(g0.data), "GLB z odkazu se vzperami je vetsi nez bez nich")
# pro objednavku / vyrobu: neutralni kusovnik, souhrn voleb, vyrobni sestava (rezy a montazni krok)
po1 = SH.pro_objednavku({"w": 1400, "braces": True, "bracelen": 420})
check(any(x["nazev"] == "šikmá spojka 45° (30)" and x["mnozstvi"] == 4 for x in po1["bom"]) and any(x["rozmer"] == "420 mm" and x["mnozstvi"] == 2 for x in po1["bom"]), f"neutralni kusovnik: 4x sikma spojka, 2x profil 420 mm ({[x for x in po1['bom'] if 'spojka' in x['nazev']]})")
check(any(x["id"] == "braces" and x["value"] == "ano" for x in po1["souhrn"]) and any(x["id"] == "bracelen" and x["value"] == "420 mm" for x in po1["souhrn"]), "souhrn voleb obsahuje vzpery a jejich delku")
check(not any(x["id"] == "bracelen" for x in SH.pro_objednavku({"w": 1400})["souhrn"]), "souhrn bez vzper: delka vzper se neuvadi")
vs = SH.vyrobni_sestava({"w": 1400, "braces": True, "bracelen": 420})
check(vs["ok"] and any(q["delka_mm"] == 420.0 and q["pocet"] == 2 for q in vs["vypis"]["rezny_plan"]) and any(k["krok"] == 10 for k in vs["vypis"]["montazni_postup"]), "vyrobni sestava: rez 2x 420 mm a montazni krok vzper")
check(any("Spojka úhel 45° systém 30" in x["nazev"] and x["mnozstvi"] == 4 for x in vs["kusovnik_katalog"]) and vs["hmotnost_kg"], "vyrobni sestava: katalogovy kusovnik (se SKU) obsahuje 4x spojku 3254")
check(vs["parametry"]["vzpery"] is True and vs["parametry"]["vzpera_delka"] == 420.0, "vyrobni sestava: parametry nesou vzpery a delku")
# verejne 3D ovladani: cast braces + nabidka, texty cs/en/sk
for lg in ("cs", "en", "sk"):
    dd = post({"product_id": PID, "lang": lg, "selection": {"w": 1400, "braces": True}}).get_json()
    ov = (dd.get("vodici") or {}).get("ovladani") or {}
    cb = next((c for c in ov.get("casti", []) if c["id"] == "braces"), None)
    check(cb and cb["param"] == ["braces", "bracelen"] and cb["menu"][0]["nastav"] == {"braces": False} and cb["menu"][1]["nastav"] == {"bracelen": 350}, f"[{lg}] verejne ovladani: cast braces s nabidkou odebrat / delsi / kratsi")

# --- vypnuti jednou volbou: prazdne configurator_products = vsechno 404 ---
puvodni = dict(SH._PRODUKTY["map"])
SH._PRODUKTY["map"] = {}
check(anon.get(f"/api/shop/products/{PID}/configurator").status_code == 404, "vypnuto: schema 404")
check(post({"product_id": PID, "selection": {}}).status_code == 404, "vypnuto: resolve 404")
check(anon.get(f"/api/shop/configurator/model/{d['hash']}").status_code == 404, "vypnuto: model/<hash> 404")
check(anon.get(url).status_code == 404, "vypnuto: i drive vydany odkaz na GLB je 404")
SH._PRODUKTY["map"] = puvodni
check(anon.get(url).status_code == 200, "zapnuto zpet: odkaz opet plati")

# --- rate limit ---
SH.LIMIT_RESOLVE = (5, 60)
appmod._rate_limit_buckets.clear()
kody = [post({"product_id": PID, "selection": {}}).status_code for _ in range(8)]
check(kody[:5] == [200] * 5 and 429 in kody[5:], f"rate limit resolve: 429 po 5 pozadavcich ({kody})")
rl = post({"product_id": PID, "selection": {}})
check(rl.status_code == 429 and rl.headers.get("Retry-After") and rl.get_json()["error"] == "rate_limited", "429 nese Retry-After a error")

SH.LIMIT_RESOLVE = (1000, 60)
SH.HODINOVY_STROP["resolve"] = 4
appmod._rate_limit_buckets.clear()
kody = [post({"product_id": PID, "selection": {}}).status_code for _ in range(6)]
check(kody[:4] == [200] * 4 and kody[4:] == [429, 429], f"hodinovy strop na IP: 429 po 4 pozadavcich ({kody})")

# --- slovencina (bot7) a skryta cena pro mini-shop (bot3) ---
SH.LIMIT_RESOLVE = (100000, 60)                                   # limity z predchozi zkousky se musi zrusit
SH.HODINOVY_STROP["resolve"] = 100000
SH.HODINOVY_STROP["schema"] = 100000
appmod._rate_limit_buckets.clear()
def _vsechny_klice(o, out=None):
    out = set() if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            out.add(k); _vsechny_klice(v, out)
    elif isinstance(o, list):
        for v in o:
            _vsechny_klice(v, out)
    return out


sk_s = anon.get(f"/api/shop/products/{PID}/configurator?lang=sk").get_json()
cs_s = anon.get(f"/api/shop/products/{PID}/configurator?lang=cs").get_json()
check([x["id"] for x in sk_s["slots"]] == [x["id"] for x in cs_s["slots"]] and all(x["label"] for x in sk_s["slots"]) and sk_s["slots"][0]["label"] == "Šírka dosky",
      f"schema lang=sk: stejne sloty jako cs, vsechny popisky ({sk_s['slots'][0]['label']})")
check(all(g["label"] for g in sk_s["groups"]) and {g["id"] for g in sk_s["groups"]} == {g["id"] for g in cs_s["groups"]}, "schema lang=sk: skupiny")
r_sk = post({"product_id": PID, "lang": "sk", "selection": {"w": 700, "feet": False}}).get_json()
check(r_sk["notices"] and r_sk["notices"][0]["message"].startswith("Automaticky odstránené: "), f"sk: oznameni o odebrani ({r_sk['notices'][:1]})")
check(all(isinstance(o["on"].get("reason"), (str, type(None))) for o in r_sk["options"].values() if "on" in o), "sk: duvody jsou texty")
r_sk2 = post({"product_id": PID, "lang": "sk", "selection": {"w": 3000, "vyrez1": True, "cut1": True, "cut1w": 3000, "cut2": True, "cut2w": 3000}}).get_json()
check(any("výrez" in (e["message"] or "").lower() for e in r_sk2["errors"]) or r_sk2["valid"] is False, "sk: chyba prekryvu vyrezu je slovensky")
sk_txt = json.dumps([sk_s, r_sk, r_sk2], ensure_ascii=False)
for zakaz in ("konfigur", "Dogus", "product_", "Object_"):
    check(zakaz not in sk_txt, f"sk: zakazane slovo '{zakaz}' neni ve verejnych textech")
sk_klice = set(SH.TEXTY["sk"]) - {"cs"}
check(set(SH.TEXTY["en"]) <= sk_klice and set(SH.DUVODY["en"]) <= set(SH.DUVODY["sk"]), f"sk ma vsechny klice jako en (TEXTY {len(sk_klice)}, DUVODY {len(SH.DUVODY['sk'])})")
with appmod.app.test_request_context(headers={"Accept-Language": "sk-SK,sk;q=0.9"}):
    check(SH._lang("sk") == "sk" and SH._lang("SK-sk") == "sk" and SH._lang(None) == "sk" and SH._lang("xx") == "sk", "_lang rozpozna sk (parametr i Accept-Language; neznamy jazyk 'xx' = Accept-Language, ne 'de': jazyky ze sad api/jazyky jsou od 2026-10-07 podporovane)")

r_pr = post({"product_id": PID, "selection": {"w": 1500}}).get_json()
r_hid = post({"product_id": PID, "selection": {"w": 1500}, "price": "hidden"}).get_json()
check(r_pr["price"] and r_pr["price"]["net"] > 0 and "price_delta" in json.dumps(r_pr["options"]), "bez price=hidden: cena je")
check("price" not in r_hid and "price_delta" not in _vsechny_klice(r_hid) and "net" not in _vsechny_klice(r_hid) and r_hid["valid"] and r_hid["hash"] == r_pr["hash"],
      "price=hidden: odpoved neobsahuje zadnou cenu (price ani price_delta), jinak shodna")
check("price" not in post({"product_id": PID, "selection": {"w": 1500}, "lang": "sk", "price": "HIDDEN"}).get_json(), "price=HIDDEN (velikost pismen) skryva")
rq = appmod.app.test_client().post("/api/shop/configurator/resolve?price=hidden", json={"product_id": PID, "selection": {}}, headers={"X-Forwarded-For": "10.7.7.7"}).get_json()
check("price" not in rq, "?price=hidden v dotazu skryva cenu")
SH._HOSTY_BEZ_CENY.update(t=time.time() + 10_000, hosty={"minishop.test"})
rh = appmod.app.test_client().post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {}}, base_url="http://minishop.test", headers={"X-Forwarded-For": "10.7.7.8"}).get_json()
check("price" not in rh and "price_delta" not in _vsechny_klice(rh), "host z configurator_hide_price_hosts: cena se NIKDY nevraci (klient nemusi nic posilat)")
rn = post({"product_id": PID, "selection": {}}).get_json()
check(rn["price"] and rn["price"]["net"] > 0, "jiny host: cena zustava (e-shop, zamestnanci)")
SH._HOSTY_BEZ_CENY.update(t=0.0, hosty=set())
check("price" not in SH.resolve({}, "cs", skryt_cenu=True) and SH.resolve({}, "cs")["price"], "resolve(skryt_cenu=True) funkcne")
check(SH.pro_objednavku({"w": 1500})["price"] is not None, "pro_objednavku (server-side kosik) cenu dal nese")

# --- stabilni verejna funkce pro kosik/objednavku/nabidku (bot5): pro_objednavku + glb_bytes + hluboka kopie z resolve ---
import copy  # noqa: E402
r_a = SH.resolve({"w": 1500, "bearings": True, "cut1": True})
r_a["price"]["net"] = -1
r_a["selection"]["w"] = 1
r_a["options"]["w"]["min"] = -5
r_b = SH.resolve({"w": 1500, "bearings": True, "cut1": True})
check(r_b["price"]["net"] > 0 and r_b["selection"]["w"] == 1500 and r_b["options"]["w"]["min"] > 0, "resolve() vraci kopii: zmena vysledku neposkodi cache")
po = SH.pro_objednavku({"w": 1500, "bearings": True, "cut1": True, "cut1shelf": True}, rules_version=SH.stul_glb.RULES_VERSION)
check(po["ok"] and po["valid"] and po["price"]["net"] > 0 and po["hash"] and po["kod"].startswith("STL-") and po["rules_version"] == SH.stul_glb.RULES_VERSION, f"pro_objednavku: ok, cena, hash, kod ({ {k: po[k] for k in ('ok', 'valid', 'kod')} })")
check(po["selection"]["bearings"] is True and po["selection"]["cut1"] is True and po["selection"]["cut1shelf"] is True, "pro_objednavku nese efektivni vyber")
check({"nazev", "mnozstvi", "rozmer"} == set(po["bom"][0]) and sum(r["mnozstvi"] for r in po["bom"] if r["nazev"] == "ložisková jednotka") > 0, f"neutralni kusovnik ma jednotky ({[r for r in po['bom'] if 'ložisk' in r['nazev']]})")
bom_txt = json.dumps(po["bom"], ensure_ascii=False)
check("product_" not in bom_txt and "Object_" not in bom_txt and "Dogus" not in bom_txt and "Pirkl" not in bom_txt, "kusovnik je neutralni (zadna cisla dilu ani dodavatele)")
check(any(r["nazev"] == "profil 30×30" and r["rozmer"] and r["rozmer"].endswith("mm") for r in po["bom"]) and any(r["nazev"] == "laminodeska" and "×" in (r["rozmer"] or "") for r in po["bom"]), "kusovnik: profily podle delky, desky podle rozmeru")
ids = [s["id"] for s in po["souhrn"]]
check("w" in ids and "cut1w" in ids and "cut2w" not in ids and "bearpitch" in ids and "mid" not in ids, f"souhrn voleb: jen smysluplne volby ({ids})")
check(isinstance(po["hmotnost_kg"], float) and po["hmotnost_kg"] > 5, f"pro_objednavku: hmotnost (soucet dilu s hmotnosti v katalogu) ({po['hmotnost_kg']})")
check(po["hmotnost_uplna"] is False and "laminodeska" not in po["hmotnost_chybi"] and "šuplíkový box" in po["hmotnost_chybi"] and "profil 30×30" not in po["hmotnost_chybi"],
      f"hmotnost je stale NEUPLNA (chybi supliky, LED...), laminodeska uz se pocita ({po['hmotnost_chybi']})")
_gen_po = SH.S.sestav_stul(**SH.normalizuj(po["selection"])[0])
_lam = SH.S.hmotnost_lamino_kg(_gen_po["dily"])
check(abs(SH.S.LAMINO_KG_NA_M2 * 2.8 * 2.07 - 65.0) < 1e-9 and _lam > 5, f"lamino: 65 kg na plech 2800 x 2070 = {SH.S.LAMINO_KG_NA_M2:.3f} kg/m2, stul ma {_lam:.1f} kg desek")
check(abs(po["hmotnost_kg"] - (po["cenovy_souhrn"]["weight_kg"] + _lam)) < 0.01, "hmotnost_kg = katalogovy soucet + lamino ze skutecne plochy")
_bez = SH.pro_objednavku({"w": 1500, "bearings": True})
_vyr = SH.pro_objednavku({"w": 1500, "bearings": True, "cut1": True, "cut1w": 600, "cut1d": 400})
check(abs((_bez["hmotnost_kg"] - _vyr["hmotnost_kg"]) - 0.6 * 0.4 * SH.S.LAMINO_KG_NA_M2) < 0.05, f"vyrez 600 x 400 snizi vahu o plochu otvoru x 11,2 kg/m2 ({_bez['hmotnost_kg'] - _vyr['hmotnost_kg']:.2f} kg)")
check(set(po["cenovy_souhrn"]) >= {"material_czk", "cut_czk", "joint_czk", "accessory_czk", "packaging_czk", "joint_count", "weight_kg"} and po["cenovy_souhrn"]["weight_kg"] < po["hmotnost_kg"], f"cenovy souhrn (katalogova vaha) je mensi nez hmotnost_kg s lamino ({po['cenovy_souhrn']})")
check(po["cenovy_souhrn"]["joint_count"] == po["pocet_spoju"], "pocet spoju v souhrnu == pocet_spoju")
po_lehky = SH.pro_objednavku({"w": 800, "d": 500})
check(po_lehky["hmotnost_kg"] < po["hmotnost_kg"], f"mensi stul je lehci ({po_lehky['hmotnost_kg']} < {po['hmotnost_kg']})")
po["cenovy_souhrn"]["material_czk"] = -1
check(SH.pro_objednavku({"w": 1500, "bearings": True, "cut1": True, "cut1shelf": True})["cenovy_souhrn"]["material_czk"] != -1, "cenovy souhrn je kopie")
check(SH.konfigurovatelny(PID) is True and SH.konfigurovatelny(1) is False and SH.konfigurovatelny("neexistuje") is False, "konfigurovatelny(product_id): True jen pro konfigurovatelny stul")
po2 = SH.pro_objednavku({"w": 800}, rules_version="stara-verze")
check(po2 == {"ok": False, "chyba": "rules_changed", "rules_version": SH.stul_glb.RULES_VERSION}, f"jina rules_version -> rules_changed ({po2})")
po3 = SH.pro_objednavku({"w": 700, "led": True})
check(po3["ok"] and po3["selection"]["led"] is False and po3["notices"], f"automaticky odebrane prislusenstvi je v efektivnim vyberu a v notices ({po3['notices']})")
po["bom"].append("x"); po["selection"]["w"] = 1
check("x" not in SH.pro_objednavku({"w": 1500, "bearings": True, "cut1": True, "cut1shelf": True})["bom"] and SH.pro_objednavku({"w": 1500})["selection"]["w"] == 1500, "pro_objednavku vraci kopii")
g = SH.glb_bytes({"w": 1500, "cut1": True})
check(g[:4] == b"glTF" and g == SH.stul_glb.model_pro_parametry(SH.S.sestav_stul(**SH.normalizuj({"w": 1500, "cut1": True})[0])["parametry"])[1], "glb_bytes: GLB shodny s modelem pro efektivni parametry")
check(SH.glb_bytes({"w": 700, "led": True}) == SH.glb_bytes({"w": 700, "led": False}), "glb_bytes pouziva EFEKTIVNI vyber (odebrane prislusenstvi se nekresli)")

# --- vyrobni sestava (bot8, 2026-10-03): kompletni vycet dilu pro vyrobu, snimek pro ulozeni pri objednani ---
vs = SH.vyrobni_sestava({"w": 1500, "d": 800, "cut1": True, "cut1shelf": True, "bearings": True, "wheels": False, "drawers": False})
check(vs["ok"] and vs["valid"] and vs["hash"] and vs["kod"].startswith("STL-") and vs["rules_version"] == SH.stul_glb.RULES_VERSION, "vyrobni_sestava: ok, hash, kod, verze pravidel")
check(len(vs["dily"]) > 50 and all({"part_id", "position", "quaternion", "scale"} <= set(d) for d in vs["dily"]), f"snimek dilu ve formatu custom_shapes.data.parts ({len(vs['dily'])} dilu)")
json.dumps(vs)                                                                       # cisty JSON (ulozitelny do DB)
check(vs["vypis"]["desky"][0]["vyrezy"] and any(d["role"].startswith("police pod výřezem") for d in vs["vypis"]["desky"]) and vs["vypis"]["rezny_plan"], "vypis: rezny plan, deska s vyrezem, police pod vyrezem")
check(any("Laminodeska" in b["nazev"] for b in vs["kusovnik_katalog"]) and any("Profil" in b["nazev"] for b in vs["kusovnik_katalog"]) and vs["cena_celkem_czk"] > 1000,
      f"katalogovy kusovnik se SKU a cenou ({len(vs['kusovnik_katalog'])} radku, {vs['cena_celkem_czk']} Kc)")
check(any("3071" in b["nazev"] or "Zaslepka" in b["nazev"] or "Záslepka" in b["nazev"] for b in vs["kusovnik_katalog"]), "kusovnik obsahuje zaslepky (bez koleček)")
vs2 = SH.vyrobni_sestava({"w": 1500, "cut1": True})
vs["dily"].append("x"); vs["vypis"]["rezny_plan"].clear()
check(len(SH.vyrobni_sestava({"w": 1500, "d": 800, "cut1": True, "cut1shelf": True, "bearings": True, "wheels": False, "drawers": False})["vypis"]["rezny_plan"]) > 0, "vyrobni_sestava vraci vzdy novou kopii")
check(SH.vyrobni_sestava({"w": 800}, rules_version="stara")["chyba"] == "rules_changed", "vyrobni_sestava: jina verze pravidel -> rules_changed")
check(SH.vyrobni_sestava({"w": 3000, "d": 1500, "bearings": True, "bearpitch": 40, "bearedge": 30})["chyba"] == "invalid_configuration", "vyrobni_sestava: nevalidni konfigurace (moc jednotek) -> invalid_configuration")
# routy pro zamestnance
r_a = anon.get("/api/stul/vyrobni-list")
check(r_a.status_code in (401, 403), f"vyrobni list bez prihlaseni odmitnut ({r_a.status_code})")
check(anon.get("/api/stul/vyrobni-sestava").status_code in (401, 403), "vyrobni sestava bez prihlaseni odmitnuta")
with appmod.app.test_client() as _stf:
    _c = appmod.get_conn().cursor()
    _c.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
    _uid = _c.fetchone()["id"]
    appmod.get_conn().rollback()
    with _stf.session_transaction() as _s:
        _s["user_id"] = _uid
    rl = _stf.get("/api/stul/vyrobni-list?vyrez1=1&loz=1&kolecka=0")
    html_ = rl.get_data(as_text=True)
    check(rl.status_code == 200 and rl.mimetype == "text/html" and "Řezný plán" in html_ and "<svg" in html_ and "Montážní postup" in html_ and "spojovací materiál" in html_, "vyrobni list (HTML) ma rezny plan, vykres desky, spojovaci material, postup")
    check("výřez 1" in html_ and "ložiskové jednotky" in html_.lower() and "<script" not in html_.lower(), "vyrobni list: vyrez a jednotky na vykresu, bez skriptu")
    rj = _stf.get("/api/stul/vyrobni-sestava?vyrez1=1")
    check(rj.status_code == 200 and rj.get_json()["vypis"]["desky"][0]["vyrezy"] and rj.get_json()["dily"], "vyrobni sestava (JSON) pro zamestnance")
    check(_stf.get("/api/stul/vyrobni-sestava?sirka=1").status_code == 400, "vyrobni sestava: mimo rozsah = 400")

# --- ovladani ve 3D, verejna podoba (bot8, 2026-10-03): verejne nazvy slotu, texty cs/en/sk, bez indexu dilu ---
import re  # noqa: E402
SH._RESOLVE_CACHE.clear()                                    # drivejsi bloky mohly cachovat odpoved s podmenenym skladacem (vodici None)
SLOTY = {s_["id"] for s_ in SH.schema("cs")["slots"]}
KONF_OVL = ({"w": 2000, "d": 1000, "cut1": True, "cut1shelf": True, "bearings": True, "wheels": False, "feet": True},
            {"w": 1200}, {"w": 2400, "cut1": True, "cut2": True, "cut3": True, "drawers": False, "posts": False, "panels": False, "led": False, "socket": False})
for lg in ("cs", "en", "sk"):
    for sel in KONF_OVL:
        d_ = post({"product_id": PID, "lang": lg, "selection": sel}).get_json()
        ov = (d_.get("vodici") or {}).get("ovladani")
        n_ = f"{lg} {sel}"
        check(ov and ov["casti"] and ov["tahy"], f"{n_}: verejne vodici.ovladani existuje")
        if not ov:
            continue
        json.dumps(ov)
        check(len({c["id"] for c in ov["casti"]}) == len(ov["casti"]) and all(re.fullmatch(r"[a-z]+\d*[a-z]*\d*", c["id"]) for c in ov["casti"]), f"{n_}: id casti jsou verejna a unikatni ({[c['id'] for c in ov['casti']][:6]})")
        check(all(q in SLOTY for c in ov["casti"] for q in c["param"]), f"{n_}: propojeni s panelem jen na existujici sloty")
        for c in ov["casti"]:
            for m in c["menu"]:
                check(all(k in SLOTY for k in (m["nastav"] or {})), f"{n_}: nabidka {c['id']} / {m['text']}: nastavuje jen sloty ({list((m['nastav'] or {}))})")
        check(all(t.get("param", t.get("param_x")) in SLOTY and all(m["param"] in SLOTY for m in t["mereni"]) for t in ov["tahy"]) and not any(t["id"] == "stredni_noha" for t in ov["tahy"]),
              f"{n_}: tahy na sloty, stredni noha se nepreda (je ve vodici.stredni_noha)")
        zr = ov.get("zive_rozsahy")
        check(zr is not None and any(t_.get("zive") for t_ in ov["tahy"]), f"{n_}: verejne ovladani nese zive_rozsahy a zive operace")
        check(all(op["ix"] and all(0 <= i < len(zr) for i in op["ix"]) for t_ in ov["tahy"] for op in t_.get("zive", [])), f"{n_}: zive operace odkazuji na existujici dily")
        ex_ = ov.get("zive_rozsahy_extra")                     # SPODNI suplik boxu je vlastni uzel GLB (pohyb na klik): jeho rozsah musi dojit i do verejneho ovladani, jinak se pri tazeni sirky / posunu boxu odtrhne od skrine (Robert 2026-10-06)
        nohy_ = sum(1 for c_ in S.sestav_stul(**SH.normalizuj(sel)[0])["dily"] if c_["part_id"] in getattr(G, "KUZEL_PATKY", {}))      # plastove kuzely stavitelnych patek (cerny plast, bot10 2026-10-08) jsou DALSI rozsah dilu patky
        if sel.get("drawers") is False:
            check((ex_ is None) if not nohy_ else (ex_ is not None and len(ex_) == nohy_), f"{n_}: bez boxu (supliky vypnute) zadne zive_rozsahy_extra krome kuzelu patek ({nohy_} patek; {ex_})")
        else:
            check(ex_ is not None and len(ex_) == 1 + nohy_ and all(k.isdigit() and 0 <= int(k) < len(zr) and ex_[k] and all(len(r_) == 3 for r_ in ex_[k]) for k in ex_),
                  f"{n_}: verejne ovladani nese zive_rozsahy_extra pro dil boxu (suplik je vlastni uzel; bez nich by se pri tazeni suplik odtrhl od boxu) + kuzely patek ({nohy_}) ({ex_})")
            check(all(any(int(k) in op["ix"] for t_ in ov["tahy"] for op in t_.get("zive", [])) for k in (ex_ or {})), f"{n_}: dil boxu s extra rozsahem je v nejake zive operaci")
        txt = json.dumps(ov, ensure_ascii=False)
        check("product_" not in txt and "Object_" not in txt and not re.search(r'"(noha|konec)_\d+"', txt), f"{n_}: zadny index ani cislo dilu")
        if lg == "en":
            check(not re.search(r"[^\x00-\x7f−·]", txt), f"{n_}: anglicke texty bez ceskych znaku ({set(re.findall(r'[^\x00-\x7f−·]', txt))})")
        if lg == "sk":
            check(not re.search(r"[ěřů]", txt) and "Odebrat" not in txt and "výřez" not in txt.lower() and "šuplík" not in txt.lower(), f"{n_}: slovenske texty bez ceskych znaku a slov")
        # kazda povolena polozka nabidky jde provest pres resolve (vysledek je platny vyber)
        zakl = d_["selection"]
        for c in ov["casti"]:
            for m in c["menu"]:
                if m["zakazano"] or not m["nastav"]:
                    continue
                r2 = post({"product_id": PID, "selection": {**zakl, **m["nastav"]}})
                check(r2.status_code == 200, f"{n_}: {c['id']} / {m['text']}: resolve po provedeni polozky = 200")
# --- stredni noha ve verejnem ovladani: tah `mid` v % (jednotka, faktor, meze, zakazana pasma, mereni v mm), staff tah v mm je ten samy ---
for lg_, w_, mid_ in (("cs", 2000, 40), ("en", 2400, 50), ("sk", 1800, 70)):
    dm_ = post({"product_id": PID, "lang": lg_, "selection": {"w": w_, "mid": mid_, "midsupport": "legs"}}).get_json()          # stredni NOHY (u sirokeho stolu s panelem by `auto` zvolilo vestaveny ram)
    ovm = dm_["vodici"]["ovladani"]
    tm_ = next((t_ for t_ in ovm["tahy"] if t_["id"] == "mid"), None)
    span_ = w_ - 30.0
    check(tm_ is not None and tm_["param"] == "mid" and tm_["jednotka"] == "%" and abs(tm_["faktor"] - 100.0 / span_) < 1e-6 and abs(tm_["mm_na_jednotku"] - span_ / 100.0) < 1e-6, f"[{lg_}] tah mid: jednotka %, faktor 100/rozpeti ({tm_ and (tm_.get('faktor'), tm_.get('jednotka'))})")
    if tm_:
        check(abs(tm_["hodnota"] - mid_) <= 0.6 and 5 <= tm_["min"] < tm_["hodnota"] < tm_["max"] <= 95, f"[{lg_}] tah mid: hodnota {tm_['hodnota']} v mezich {tm_['min']}..{tm_['max']} (slot mid 5-95 %)")
        mm0 = tm_["mereni"][0]["add"] + tm_["mereni"][0]["mul"] * tm_["hodnota"]
        mm1 = tm_["mereni"][1]["add"] + tm_["mereni"][1]["mul"] * tm_["hodnota"]
        check(abs(mm0 - tm_["hodnota"] * span_ / 100.0) < 0.1 and abs(mm0 + mm1 - span_) < 0.1, f"[{lg_}] tah mid: mereni v mm (od leve {mm0:.0f} + od prave {mm1:.0f} = rozpeti {span_:.0f})")
        check(all(a_ < b_ for a_, b_ in tm_["zakazano"]) and any(0 < a_ < 100 or 0 < b_ < 100 for a_, b_ in tm_["zakazano"]) and tm_["odstup_od_prekazky"] > 0, f"[{lg_}] tah mid: zakazana pasma v % ({len(tm_['zakazano'])} ks), odstup > 0")
        check(any(o_["op"] == "posun" for o_ in tm_.get("zive", [])), f"[{lg_}] tah mid nese zive operace (posun stredni nohy)")
        check(all(c_ in {x_["id"] for x_ in ovm["casti"]} for c_ in tm_["casti"]) and tm_["label"] and all(m_["label"] for m_ in tm_["mereni"]), f"[{lg_}] tah mid: casti existuji, texty preloženy")
d_nomid = post({"product_id": PID, "selection": {"w": 1200}}).get_json()["vodici"]["ovladani"]
check(not any(t_["id"] == "mid" for t_ in d_nomid["tahy"]), "uzky stul (bez stredni nohy): zadny tah mid")
# cesky text se v en/sk nikdy nevraci neprelozeny: generator v nekterem stavu vrati neznamy text -> preklad musi spadnout v TESTU, ne za provozu
import stul_ovladani_verejne as OV  # noqa: E402
try:
    OV.ovladani_verejne({"casti": [{"id": "deska", "label": "Neznamy cesky text", "param": [], "aabb": [[0, 0, 0], [1, 1, 1]], "priorita": 1, "menu": []}], "tahy": []}, "en")
    check(False, "neznamy text ma vyhodit ChybiPreklad")
except OV.ChybiPreklad:
    check(True, "")
check(OV.ovladani_verejne({"casti": [{"id": "deska", "label": "Neznamy cesky text", "param": [], "aabb": [[0, 0, 0], [1, 1, 1]], "priorita": 1, "menu": []}], "tahy": []}, "cs")["casti"][0]["label"] == "Neznamy cesky text", "cs: text se nemeni")

# --- zavislosti slotu (`depends_on`, Robert: volba bez nadrazene zapnute volby neexistuje) ---
for lg in ("cs", "en", "sk"):
    sc_ = SH.schema(lg)
    ids_ = {s_["id"]: s_ for s_ in sc_["slots"]}
    dep_ = {i_: s_["depends_on"] for i_, s_ in ids_.items() if "depends_on" in s_}
    check(all(isinstance(v_, list) and v_ and all(q in ids_ and ids_[q]["type"] == "toggle" for q in v_) for v_ in dep_.values()), f"[{lg}] depends_on odkazuje jen na existujici toggle sloty")
    check(all(i_ not in v_ for i_, v_ in dep_.items()), f"[{lg}] slot nezavisi sam na sobe")
    def _hloubka(i_, seen=()):
        return 0 if i_ not in dep_ else 1 + max(_hloubka(q, seen + (i_,)) for q in dep_[i_]) if i_ not in seen else 99
    check(max(_hloubka(i_) for i_ in dep_) < 6, f"[{lg}] zavislosti nemaji cyklus")
    check(dep_.get("bracelen") == ["braces"] and dep_.get("braces") == ["posts", "led"] and dep_.get("boxpos") == ["drawers"] and dep_.get("bearpitch") == ["bearings"] and dep_.get("bearedge") == ["bearings"], f"[{lg}] vzpery, suplik a loziska maji nadrazenou volbu")
    check(all(dep_.get(f"cut{n}{sfx}") == [f"cut{n}"] for n in (1, 2, 3) for sfx in ("w", "d", "x", "z", "shelf")) and dep_.get("cut2") == ["cut1"] and dep_.get("cut3") == ["cut2"] and "cut1" not in dep_, f"[{lg}] vyrezy: rozmery a police zavisi na vyrezu, dalsi vyrez na predchozim")
# nadrazena volba vypnuta -> zavisla hodnota nema vliv na model (stejny hash)
def _hash(sel):
    return post({"product_id": PID, "selection": sel}).get_json()["hash"]
check(_hash({"braces": False, "bracelen": 900}) == _hash({"braces": False, "bracelen": 300}), "vzpery vypnute: delka vzpery nema vliv na model")
check(_hash({"bearings": False, "bearpitch": 90, "bearedge": 300}) == _hash({"bearings": False}), "loziska vypnuta: rozteč a okraj nemaji vliv na model")
check(_hash({"cut1": False, "cut1w": 400, "cut1shelf": True}) == _hash({"cut1": False}), "vyrez vypnuty: rozmery ani police nemaji vliv na model")
check(_hash({"drawers": False, "boxpos": -200}) == _hash({"drawers": False}), "suplik vypnuty: posun nema vliv na model")

# --- hloubka > 900: informace o zkraceni desky police a podperach (notices action "info"), cs/en/sk, ovladani ve 3D bez chybejiciho prekladu ---
SH._RESOLVE_CACHE.clear()
for lg, klic_text in (("cs", "podpěrný profil"), ("en", "supporting profile"), ("sk", "podperný profil")):
    dI = post({"product_id": PID, "lang": lg, "selection": {"d": 1000}}).get_json()
    inf = [n_ for n_ in dI["notices"] if n_.get("action") == "info"]
    check(len(inf) == 1 and inf[0]["slot"] == "d" and "900" in inf[0]["message"] and "31" in inf[0]["message"] and klic_text in inf[0]["message"], f"[{lg}] hloubka 1000: informace o zkraceni desky a podpere ({inf})")
    check(dI["valid"] and not dI["errors"], f"[{lg}] hloubka 1000: platna konfigurace")
    ovI = (dI.get("vodici") or {}).get("ovladani") or {}
    check(any(c["id"].startswith("supports") for c in ovI.get("casti", [])), f"[{lg}] hloubka 1000: ovladani ve 3D ma cast podper (verejne id supports1)")
    d8 = post({"product_id": PID, "lang": lg, "selection": {"d": 800}}).get_json()
    check(not [n_ for n_ in d8["notices"] if n_.get("action") == "info"], f"[{lg}] hloubka 800: zadna informace o podperach")
d0 = post({"product_id": PID, "lang": "cs", "selection": {"w": 600, "d": 1000}}).get_json()
check([n_["message"] for n_ in d0["notices"] if n_.get("action") == "info"] and "nejsou potřeba" in [n_["message"] for n_ in d0["notices"] if n_.get("action") == "info"][0], "uzky stul (600): podpery nejsou potreba - informace to rika")
# podpery pod PRACOVNI DESKOU (hloubka > 900): bez suplíku se doplni, se supliky se jejich pricky pocitaji jako podpera; oznameni cs/en/sk
for lg, klic_text, sup_text in (("cs", "pod pracovní desku", "příčky šuplíků"), ("en", "under the work surface", "drawer rails"), ("sk", "pod pracovnú dosku", "priečky zásuviek")):
    dd = post({"product_id": PID, "lang": lg, "selection": {"w": 1200, "d": 1000, "drawers": False}}).get_json()
    msg = [n_["message"] for n_ in dd["notices"] if n_.get("action") == "info" and klic_text in n_["message"]]
    check(len(msg) == 1 and sup_text not in msg[0], f"[{lg}] hloubka 1000 bez suplíku: oznameni o podpere pod pracovni deskou ({msg})")
    dd2 = post({"product_id": PID, "lang": lg, "selection": {"w": 2000, "d": 1000}}).get_json()
    msg2 = [n_["message"] for n_ in dd2["notices"] if n_.get("action") == "info" and klic_text in n_["message"]]
    check(len(msg2) == 1 and sup_text in msg2[0], f"[{lg}] sirka 2000, hloubka 1000 se supliky: oznameni ma poznamku o pricich supliku ({msg2})")
    dd3 = post({"product_id": PID, "lang": lg, "selection": {"w": 1200, "d": 1000}}).get_json()
    check(not [n_ for n_ in dd3["notices"] if n_.get("action") == "info" and klic_text in n_["message"]], f"[{lg}] sirka 1200 se supliky: zadna podpera pod deskou (pricky supliku podpiraji) - zadne oznameni")
    ov_d = ((dd.get("vodici") or {}).get("ovladani") or {}).get("casti", [])
    check(any(c["id"] == "desk_supports" for c in ov_d) or any("deska" in c["id"] or "desk" in c["id"] for c in ov_d if "support" in c["id"]), f"[{lg}] ovladani ve 3D ma cast podper pod deskou ({[c['id'] for c in ov_d]})")
d4 = post({"product_id": PID, "selection": {"w": 1200, "d": 1000, "h": 1200, "drawers": False, "shelf": 4}}).get_json()
check(((d4.get("vodici") or {}).get("ovladani") or {}).get("casti") and d4["selection"]["shelf"] == 4, f"4 police: ovladani ve 3D se preklada i pro cisla police > 3 (shelf {d4['selection']['shelf']})")

check(SH.schema("cs")["profile"] == "30x30" and SH.schema("cs")["profile_mm"] == 30, "schema nese profil stolu (30x30, 30) pro parovani animace Pripni cokoli")
d_sch = anon.get(f"/api/shop/products/{PID}/configurator").get_json()
check(d_sch.get("profile") == "30x30" and d_sch.get("profile_mm") == 30, f"verejna trasa schematu nese profile ({d_sch.get('profile')})")
# --- spojovaci material ke spojkam: NAZVY jsou nazvy KARET z katalogu (Robert: "nazvy jsou prece dany v kartach"), ne text z generatoru
_po = SH.pro_objednavku({})
_bom = {x["nazev"]: x["mnozstvi"] for x in _po["bom"]}
_nazvy = SH.stul_api.nazvy_karet()
check(_nazvy.get("2.1.001.08.06") and _bom.get(_nazvy["2.1.001.08.06"]) == 40 and not any("Otočná matice" in n for n in _bom), f"neutralni BOM nese matice pod nazvem karty ({_nazvy.get('2.1.001.08.06')!r}, 40 ks): {[n for n in _bom if 'matice' in n.lower()]}")
_v = S.vyrobni_vypis(S.sestav_stul(), _nazvy)["spojovaci_material"]["ke_spojkam"]
check(any(m["sku"] == "2.1.001.08.06" and m["nazev"] == _nazvy["2.1.001.08.06"] and m["mnozstvi"] == 40 for m in _v), f"vyrobni vypis: nazev spojovaciho materialu je nazev karty ({[(m['sku'], m['nazev']) for m in _v]})")
_v0 = S.vyrobni_vypis(S.sestav_stul())["spojovaci_material"]["ke_spojkam"]
check(any(m["sku"] == "2.1.001.08.06" and m["nazev"] for m in _v0), "bez nazvu karet (cista funkce) je nahradni text, nic nespadne")
# --- vyrobni list / sestava: radky kusovniku z katalogu + prace (rezy, spoje, balne, zaokrouhleni) = CELKOVA CENA (Robert 2026-10-04: "jakto ze je cena s balnym, kdyz tam neni videt")
_vs = SH.vyrobni_sestava({})
_sum = sum(x["celkem_czk"] for x in _vs["kusovnik_katalog"]) + sum(x["celkem_czk"] for x in _vs["kusovnik_prace"])
check(_vs["ok"] and _sum == _vs["cena_celkem_czk"], f"sestava: soucet radku kusovniku z katalogu + prace {_sum} = cena celkem {_vs['cena_celkem_czk']}")
check(any("Balné" in x["nazev"] for x in _vs["kusovnik_prace"]) and any("Spoje" in x["nazev"] for x in _vs["kusovnik_prace"]) and any("Řezy" in x["nazev"] for x in _vs["kusovnik_prace"]), f"sestava: prace obsahuje rezy, spoje a balne ({[x['nazev'] for x in _vs['kusovnik_prace']]})")
_html = SH.stul_vyrobni_list.html_list(_vs) if hasattr(SH, "stul_vyrobni_list") else ""
check("Práce, spoje a balné" in _html and "Balné (" in _html, "vyrobni list ukazuje radky prace, spoju a balneho v kusovniku z katalogu")
# --- VYSKA POLIC (sloty sh1..sh10; Robert 2026-10-04): schema, options (hidden pro neexistujici police), normalizace, token modelu, 3D tahy, texty cs/en/sk
for lg in ("cs", "en", "sk"):
    sc = {x["id"]: x for x in SH.schema(lg)["slots"]}
    check(all(sc[f"sh{k}"]["type"] == "slider" and sc[f"sh{k}"]["label"] for k in range(1, 11)) and sc["sh1"]["help"] and sc["sh2"]["label"] != sc["sh1"]["label"], f"[{lg}] schema: slidery sh1..sh10 s popisky a napovedou u sh1")
check(SH.schema("cs")["default_selection"]["sh1"] is None and SH.schema("cs")["default_selection"]["sh10"] is None, "vychozi vyber: vsechny vysky polic automaticky (None)")
rs = SH.resolve({"shelf": 2, "h": 1000})
check(rs["selection"]["sh1"] is None and rs["options"]["sh1"]["auto"] and rs["options"]["sh1"]["value"] > 0 and rs["options"]["sh3"].get("hidden") is True and not rs["options"]["sh2"].get("hidden"), f"options: sh1/sh2 s hodnotou (auto), sh3 skryte ({rs['options']['sh1']}, {rs['options']['sh3']})")
rv = SH.resolve({"shelf": 2, "h": 1000, "sh1": rs["options"]["sh1"]["value"] + 50, "sh2": 130})
check(rv["valid"] and rv["selection"]["sh1"] == round(rs["options"]["sh1"]["value"] + 50, 1) and rv["selection"]["sh2"] == 130.0 and not rv["options"]["sh1"]["auto"], f"zadane vysky polic: platne, vraceny ve vyberu, auto=False ({rv['selection']['sh1']}, {rv['selection']['sh2']})")
check(rv["hash"] != rs["hash"] and any(t["id"] == "sh1" and t["osa"] == [0.0, -1.0, 0.0] for t in rv["vodici"]["ovladani"]["tahy"]), "jina vyska polic = jiny hash; ve 3D je tah sh1 (osa dolu)")
rbad = SH.resolve({"shelf": 2, "h": 1000, "sh1": 50})
check(not rbad["valid"] and rbad["errors"], f"vyska mimo meze: neplatna konfigurace s hlaskou ({[e['message'][:50] for e in rbad['errors']]})")
pp_, _n = SH.normalizuj({"shelf": 2, "h": 1000, "sh1": 480, "sh2": 130})
rr_ = SH._rozbal(SH._zabal(pp_))
check(rr_.get("police_h1") == 480.0 and rr_.get("police_h2") == 130.0 and "H" in SH._zabal(pp_) and "H" not in SH._zabal(SH.normalizuj({})[0]), "token modelu nese vysky polic (H); vychozi token beze zmeny")
check(SH.resolve({"shelf": 1, "sh1": 450})["selection"]["sh2"] is None, "sh2 bez 2. police zustava None")
# --- DRZAK PET: na ktere noze (petleg) a ktere strane profilu (petface) - selecty, normalizace, options, token, hlasky cs/en/sk
for lg in ("cs", "en", "sk"):
    sc = {x["id"]: x for x in SH.schema(lg)["slots"]}
    check(sc["petleg"]["type"] == "select" and [o["id"] for o in sc["petleg"]["options"]] == ["fl", "fr", "rl", "rr", "fm", "rm"] and sc["petface"]["type"] == "select"
          and [o["id"] for o in sc["petface"]["options"]] == ["right", "left", "front", "back"] and all(o["label"] for o in sc["petleg"]["options"] + sc["petface"]["options"]) and sc["petleg"]["depends_on"] == ["pet"], f"[{lg}] schema: selecty petleg a petface s popisky, zavisi na pet")
check(SH.schema("cs")["default_selection"]["petleg"] == "fl" and SH.schema("cs")["default_selection"]["petface"] == "right", "vychozi umisteni drzaku PET: predni leva noha, vpravo")
rp = SH.resolve({"petleg": "rr", "petface": "back"})
check(rp["valid"] and rp["selection"]["petleg"] == "rr" and rp["selection"]["petface"] == "back" and rp["hash"] != SH.resolve({})["hash"], "drzak PET na zadni prave noze zezadu: platne, jiny hash")
rm_ = SH.resolve({"petleg": "fm"})
check(not rm_["valid"] and rm_["errors"][0]["message"] == SH.PET_NOHA_NENI["cs"] and rm_["options"]["petleg"]["fm"]["disabled"], "stredni noha u uzkeho stolu: chyba srozumitelnou vetou, volba zakazana")
check(SH.resolve({"w": 2000, "panels": False, "petleg": "fm", "petface": "left"})["valid"] and not SH.resolve({"w": 2000, "panels": False})["options"]["petleg"], "u sirsiho stolu (bez panelu) jsou stredni nohy dostupne")
rpm_ = SH.resolve({"w": 2000, "petleg": "fm", "petface": "left"})
check(not rpm_["valid"] and rpm_["selection"]["panels"] is True and any(o["slot"] == "panels" and o["action"] == "remove" for o in rpm_["offers"]) and "střední nohy dělí" in rpm_["errors"][0]["message"] and "vestavěný rám" in rpm_["errors"][0]["message"],
      f"drzak PET na stredni noze u 2000 s panelem: v automatu stredni nohy (ne ram), panel se mezi ne nevejde = chyba s duvodem a nabidkou odebrat panely, nic se neodebere samo ({[e['message'][:50] for e in rpm_['errors']]})")
rk = SH.resolve({"petleg": "fr", "petface": "left"})
check(not rk["valid"] and rk["errors"][0]["message"] == SH.KOLIZE_PET["cs"] and any(o["message"] == SH.KOLIZE_PET["cs"] for o in rk["offers"]), f"kolize drzaku PET s boxem: hlaska o kolizi a nabidka odebrat ({[e['message'][:40] for e in rk['errors']]})")
pp_, _n = SH.normalizuj({"petleg": "rl", "petface": "front"})
check(SH._rozbal(SH._zabal(pp_))["pet_noha"] == "ZL" and SH._rozbal(SH._zabal(pp_))["pet_strana"] == "vpredu" and "P" not in SH._zabal(SH.normalizuj({})[0]), "token modelu nese umisteni drzaku PET; vychozi token beze zmeny")
check(SH.normalizuj({"petleg": "xx", "petface": "yy"})[0]["pet_noha"] == "PL" and SH.normalizuj({"pet": False, "petleg": "rr"})[0]["pet_noha"] == "PL", "neznama hodnota / bez drzaku = vychozi")
# --- SUPLIKY VLEVO (slot drawleft) a VYSKA DRZAKU PET (slot petpos): schema, zavislosti, normalizace, options, 3D ovladani, zpravy o kolizi, token modelu (cs/en/sk) ---
sch = SH.schema("cs")
sl_ = {x["id"]: x for x in sch["slots"]}
check(sl_["drawleft"]["type"] == "toggle" and sl_["drawleft"]["depends_on"] == ["drawers"] and sl_["petpos"]["type"] == "slider" and sl_["petpos"]["depends_on"] == ["pet"], "schema: drawleft (toggle, zavisi na drawers) a petpos (slider, zavisi na pet)")
check(sch["default_selection"]["drawleft"] is False and sch["default_selection"]["petpos"] == 0, "vychozi vyber: supliky vpravo, drzak PET v sablone")
for lg in ("cs", "en", "sk"):
    sc = SH.schema(lg)
    check(all(next(x for x in sc["slots"] if x["id"] == i)["label"] for i in ("drawleft", "petpos")), f"[{lg}] nove sloty maji popisky")
dL = post({"product_id": PID, "selection": {"drawleft": True, "petpos": -120}}).get_json()
check(dL["valid"] and not dL["errors"] and dL["selection"]["drawleft"] is True and dL["selection"]["petpos"] == -120, f"supliky vlevo + drzak PET o 120 mm niz: platne ({dL['errors']})")
check(dL["options"]["petpos"]["max"] == -120 and dL["options"]["petpos"]["min"] < -120 and dL["options"]["petpos"]["fits"], f"options.petpos: s supliky vlevo jde drzak jen pod ne ({dL['options']['petpos']})")
check(dL["options"]["boxpos"]["fits"] and dL["options"]["boxpos"]["min"] < 0 < dL["options"]["boxpos"]["max"] + 1, f"options.boxpos pro supliky vlevo ({dL['options']['boxpos']})")
for lg in ("cs", "en", "sk"):
    dK = post({"product_id": PID, "lang": lg, "selection": {"drawleft": True}}).get_json()
    check(not dK["valid"] and any(e["message"] == SH.KOLIZE_PET[lg] for e in dK["errors"]) and any(o["slot"] == "pet" and o["message"] == SH.KOLIZE_PET[lg] for o in dK["offers"]),
          f"[{lg}] supliky vlevo bez snizeni drzaku PET: srozumitelna hlaska o kolizi + nabidka odebrat ({[e['message'][:40] for e in dK['errors']]})")
    ovL = ((dL.get("vodici") or {}).get("ovladani") or {})
    tL = {t["id"]: t for t in ovL.get("tahy", [])}
    check("petpos" in tL and tL["petpos"]["param"] == "petpos" and tL["petpos"]["osa"] == [0.0, 1.0, 0.0] and tL["boxpos"]["osa"] == [0.0, 0.0, -1.0], f"3D ovladani: tah petpos (svisle) a boxpos s osou k leve strane ({[(i, t['osa']) for i, t in tL.items()][:6]})")
# token modelu nese stranu supliku i posun PET (model = to, co se spocitalo)
pp_, _ = SH.normalizuj({"drawleft": True, "petpos": -120})
check(SH._rozbal(SH._zabal(pp_))["suplik_vlevo"] is True and SH._rozbal(SH._zabal(pp_))["pet_posun"] == -120.0, "token modelu nese suplik_vlevo a pet_posun")
check(SH._rozbal(SH._zabal(SH.normalizuj({})[0]))["suplik_vlevo"] is False and "f" not in SH._zabal(SH.normalizuj({})[0]) and "q" not in SH._zabal(SH.normalizuj({})[0]), "vychozi token je beze zmeny (bez novych klicu)")
check(SH.normalizuj({"drawleft": True, "drawers": False})[0]["pet_posun"] == 0.0 and SH._rozbal(SH._zabal(SH.normalizuj({"drawleft": True, "drawers": False})[0]))["suplik_vlevo"] is False, "bez supliku strana neexistuje")
check(post({"product_id": PID, "selection": {"pet": False, "petpos": -100}}).get_json()["selection"]["petpos"] == 0, "bez drzaku PET je petpos 0")

# --- blok pro zamestnance ve verejnem resolve (`staff: true`): spolecny modul ovladani slouzi mini-shopu i strance stolu; zakaznik/host blok nikdy nedostane ---
_conn = appmod.get_conn(); _cur = _conn.cursor()
_cur.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
_admin = _cur.fetchone()["id"]; _conn.rollback()
adm = appmod.app.test_client()
with adm.session_transaction() as sess_:
    sess_["user_id"] = _admin
d_anon = post({"product_id": PID, "selection": {"w": 1400}, "staff": True}).get_json()
check("staff" not in d_anon, "host/zakaznik: ani s `staff: true` nedostane blok pro zamestnance")
d_adm0 = post({"product_id": PID, "selection": {"w": 1400}}, adm).get_json()
check("staff" not in d_adm0, "zamestnanec bez `staff: true`: blok se nepridava (stejna odpoved jako verejna)")
d_adm = post({"product_id": PID, "selection": {"w": 1400, "braces": True}, "staff": True}, adm).get_json()
sb = d_adm.get("staff") or {}
check(bool(sb) and sb["kusovnik"] and sb["kusovnik"]["radky"] and sb["kusovnik"]["prace"], "zamestnanec: staff blok nese kusovnik (radky + prace)")
if sb:
    k_ = sb["kusovnik"]
    check(sum(r["celkem"] for r in k_["radky"]) + sum(r["celkem"] for r in k_["prace"]) == k_["celkem"]["bez_dph"] == sb["cena"]["bez_dph"], f"staff: soucet radku kusovniku = cena bez DPH ({sb['cena']})")
    check(sb["hash"] == d_adm["hash"] and sb["kod"] == d_adm["kod"] and isinstance(sb["problemy"], list) and not sb["problemy"], "staff: hash a kod sedi s verejnou odpovedi, bez problemu")
    check(sb["vyrobni_list_url"].startswith("/api/stul/vyrobni-list?") and "sirka=1400" in sb["vyrobni_list_url"] and "vzpery=1" in sb["vyrobni_list_url"], f"staff: odkaz na vyrobni list nese parametry ({sb['vyrobni_list_url'][:80]})")
    r_vl = adm.get(sb["vyrobni_list_url"])
    check(r_vl.status_code == 200, f"staff: odkaz na vyrobni list funguje ({r_vl.status_code})")
d_bad = post({"product_id": PID, "selection": {"w": 1400}, "staff": True}, appmod.app.test_client()).get_json()
check("staff" not in d_bad, "anonymni klient s `staff: true` (jiny test_client): bez bloku")

# --- PANELY VSAZENE DO PROFILU, STREDNI OPORA, VYSKA STOJEK, ELEKTROZLAB (Robert 2026-10-05): sloty panelcount, panelpos, midsupport, posth, socketup, socketside
NOVE_SLOTY = ("panelcount", "panelpos", "midsupport", "posth", "socketup", "socketside")
for lg in ("cs", "en", "sk"):
    sc_ = {x["id"]: x for x in SH.schema(lg)["slots"]}
    check(set(NOVE_SLOTY) <= set(sc_) and all(sc_[k]["label"] for k in NOVE_SLOTY), f"[{lg}] schema: nove sloty maji popisky")
    check(sc_["panelcount"]["type"] == "slider" and sc_["panelcount"]["slider"]["min"] == 1 and sc_["panelcount"]["slider"]["max"] == S.PANELY_MAX and sc_["panelcount"]["depends_on"] == ["panels"], f"[{lg}] panelcount: slider 1-{S.PANELY_MAX}, zavisi na panelech")
    check(sc_["panelpos"]["depends_on"] == ["panels"] and sc_["posth"]["depends_on"] == ["posts"] and sc_["socketup"]["depends_on"] == ["socket"] and sc_["socketside"]["depends_on"] == ["socket"], f"[{lg}] zavislosti panelpos/posth/socketup/socketside")
    check(sc_["midsupport"]["type"] == "select" and [o["id"] for o in sc_["midsupport"]["options"]] == ["auto", "legs", "frame"] and all(o["label"] for o in sc_["midsupport"]["options"]), f"[{lg}] midsupport: select auto/legs/frame s popisky")
    check(sc_["posth"]["slider"]["min"] == S.ROZSAH["stojky_vyska"][0] and sc_["posth"]["slider"]["max"] == S.ROZSAH["stojky_vyska"][1], f"[{lg}] posth: rozsah stojek {S.ROZSAH['stojky_vyska']}")
sc_cs, sc_en = {x["id"]: x for x in SH.schema("cs")["slots"]}, {x["id"]: x for x in SH.schema("en")["slots"]}
check(all(sc_cs[k]["label"] != sc_en[k]["label"] for k in NOVE_SLOTY), "nove sloty: cesky a anglicky popisek se lisi")
ds_ = SH.schema("cs")["default_selection"]
check(ds_["w"] == 1280 and ds_["panelcount"] == 1 and ds_["panelpos"] == 0 and ds_["midsupport"] == "auto" and ds_["posth"] == 1073 and ds_["socketup"] == 0 and ds_["socketside"] == 0, f"vychozi vyber: 1280, 1 panel, opora auto, stojky 1073 ({ {k: ds_[k] for k in ('w',) + NOVE_SLOTY} })")
# vychozi stul: options novych slotu
rd = SH.resolve({})
od = rd["options"]
check(rd["valid"] and od["panelcount"] == {"min": 1, "max": 2, "value": 1} and od["panelpos"]["min"] == 0 and od["panelpos"]["max"] == 540 and od["midsupport"] == {"hidden": True}, f"vychozi: options panelcount 1-2, panelpos 0-540, midsupport skryta ({od['panelcount']}, {od['panelpos']}, {od['midsupport']})")
check(od["posth"] == {"min": 530, "max": 1500, "value": 1073.0} and od["socketup"]["min"] == -100 and od["socketup"]["max"] == 400 and od["socketside"]["min"] == -50 and od["socketside"]["max"] == 620 and od["socketup"]["fits"] is True, f"vychozi: options posth a elektrozlab ({od['posth']}, {od['socketup']}, {od['socketside']})")
check(all(not any(x["id"] == k for x in rd["souhrn"]) for k in ("panelpos", "midsupport", "socketup", "socketside")) if "souhrn" in rd else True, "souhrn: nepouzite volby se neukazuji")
# pocet panelu po jednom kuse: cena, hash, orez nad kapacitu s upozornenim
r2 = SH.resolve({"panelcount": 2})
check(r2["valid"] and r2["selection"]["panelcount"] == 2 and r2["price"]["net"] > rd["price"]["net"] and r2["hash"] != rd["hash"], f"2 panely: platne, drazsi, jiny hash ({rd['price']['net']} -> {r2['price']['net']})")
r4 = SH.resolve({"panelcount": 4})
check(r4["valid"] and r4["selection"]["panelcount"] == 2 and any(n["slot"] == "panelcount" and n["action"] == "info" for n in r4["notices"]), f"4 panely na uzkem stole: orez na kapacitu 2 + upozorneni ({[n['message'][:60] for n in r4['notices']]})")
check(SH.resolve({"panelcount": 0})["selection"]["panelcount"] == 1 and SH.resolve({"panelcount": 99})["selection"]["panelcount"] == 2, "panelcount mimo rozsah: oriznuto do 1..kapacita")
# posun panelu a elektrozlabu
rp = SH.resolve({"panelpos": 300, "socketup": 50, "socketside": 40})
check(rp["valid"] and rp["selection"]["panelpos"] == 300 and rp["selection"]["socketup"] == 50 and rp["selection"]["socketside"] == 40 and rp["hash"] != rd["hash"], "posun panelu 300 a elektrozlabu (50, 40) se prevezme")
check(SH.resolve({"panelpos": 5000})["selection"]["panelpos"] == 540 or SH.resolve({"panelpos": 5000})["selection"]["panelpos"] == 549, f"posun panelu nad mez se orizne ({SH.resolve({'panelpos': 5000})['selection']['panelpos']})")
rbad = SH.resolve({"socketup": 9999})
check(not rbad["valid"] and rbad["errors"] and rbad["errors"][0]["slot"] in ("socketup", "socket") and rbad["errors"][0]["message"], f"elektrozlab mimo meze: chyba u posuvniku, ne vyjimka ({[e['slot'] for e in rbad['errors']]})")
for lg in ("en", "sk"):
    rb_ = SH.resolve({"socketup": 9999}, lang=lg)
    check(not rb_["valid"] and rb_["errors"][0]["message"] and rb_["errors"][0]["message"] != rbad["errors"][0]["message"], f"[{lg}] chyba elektrozlabu je prelozena")
# stredni opora: auto = ram, jen kdyz by se panel jinak nevesel; viditelnost, duvod, hash
ra = SH.resolve({"w": 2000})
check(ra["valid"] and ra["selection"]["midsupport"] == "auto" and ra["options"]["midsupport"]["effective"] == "frame" and any(n["slot"] == "midsupport" for n in ra["notices"]) and ra["selection"]["panels"] is True, f"w=2000: auto zvolilo vestaveny ram + upozorneni, panel zustal ({ra['options']['midsupport']})")
rl_ = SH.resolve({"w": 2000, "midsupport": "legs"})
check(rl_["valid"] and rl_["selection"]["panels"] is False and rl_["options"]["midsupport"]["effective"] == "legs" and any(n["slot"] == "panels" and n["action"] == "removed" for n in rl_["notices"]), "w=2000 + stredni nohy: panel se mezi ne nevejde = automaticky odebran s upozornenim")
rf_ = SH.resolve({"w": 2000, "midsupport": "frame", "shelf": 0})
check(rf_["valid"] and rf_["options"]["midsupport"]["frame"]["disabled"] and rf_["options"]["midsupport"]["frame"]["reason"] and rf_["options"]["midsupport"]["effective"] == "legs", "vestaveny ram bez spodni police: volba zakazana s duvodem, vysledek = stredni nohy")
check(SH.resolve({"w": 2000, "midsupport": "frame"})["hash"] != SH.resolve({"w": 2000, "midsupport": "legs"})["hash"] and SH.resolve({"w": 1400, "midsupport": "frame"})["hash"] == SH.resolve({"w": 1400})["hash"], "hash: ram a nohy se lisi; u uzkeho stolu se opora do hashe nepocita")
rwide = SH.resolve({"w": 2600, "panelcount": 2})
check(rwide["valid"] and rwide["options"]["midsupport"]["effective"] == "legs" and rwide["selection"]["panelcount"] == 2, "w=2600, 2 panely: auto = stredni nohy (panel se vejde do kazdeho useku)")
# vyska zadnich stojek: nizke stojky = panel se odebere a nabidne se zvyseni
rh = SH.resolve({"posth": 500})
check(rh["valid"] and rh["selection"]["panels"] is False and rh["options"]["panels"]["on"].get("suggest") == {"posth": 530} and "530" in rh["options"]["panels"]["on"]["suggest_label"], f"posth 500: panel se nevejde, nabidka zvysit stojky na 530 ({rh['options']['panels']['on'].get('suggest')})")
check(SH.resolve({"posth": 900})["selection"]["posth"] == 900.0 and SH.resolve({"posth": 99999})["selection"]["posth"] == 1500.0, "posth: platna hodnota se prevezme, nad mez se orizne")
# token modelu: tam a zpet; vychozi hodnoty = zadny novy klic
pz, _ = SH.normalizuj({"panelcount": 2, "panelpos": 120, "midsupport": "frame", "w": 2000, "posth": 900, "socketup": 20, "socketside": 30})
tz = SH._rozbal(SH._zabal(pz))
check(tz["panely_pocet"] == 2 and tz["panely_posun"] == 120.0 and tz["stredni_opora"] == "ram" and tz["stojky_vyska"] == 900.0 and tz["elzlab_y"] == 20.0 and tz["elzlab_z"] == 30.0, f"token: nove parametry tam a zpet ({ {k: tz[k] for k in ('panely_pocet', 'panely_posun', 'stredni_opora', 'stojky_vyska', 'elzlab_y', 'elzlab_z')} })")
tk0 = SH._zabal(SH.normalizuj({})[0])
check(not any(k in tk0 for k in ("N", "Q", "M", "Z", "E")), f"vychozi token nema zadny novy klic ({tk0})")
check(SH._rozbal({"w": 1280, "d": 800, "h": 840, "t": 255}).get("panely_pocet", 1) == 1, "token bez novych klicu = vychozi hodnoty")
# vsechny verejne texty a ovladani ve 3D ve vsech jazycich a systemech (zadny chybejici preklad)
bez = 0
for sel_, lg_, sy_ in [(x, y, z) for x in ({}, {"w": 2000}, {"w": 2000, "midsupport": "legs"}, {"w": 2600, "panelcount": 2}, {"panelcount": 2, "panelpos": 100, "socketup": 50}, {"posth": 700, "w": 1600, "braces": True}) for y in ("cs", "en", "sk") for z in (30, 40)]:
    rr_ = SH.resolve(sel_, lang=lg_, system=sy_)
    if not (rr_.get("vodici") and rr_["vodici"].get("ovladani")):
        bez += 1
        print(f"  (info) bez ovladani: {sel_} {lg_} {sy_}")
check(bez == 0, f"3D ovladani se vraci pro vsechny konfigurace, jazyky a systemy (bez: {bez})")
ov_ = SH.resolve({"w": 2000})["vodici"]["ovladani"]
check("frame" in {c["id"] for c in ov_["casti"]} and any(t["id"] == "mid" and t["casti"] == ["frame"] for t in ov_["tahy"]), "3D: cast `frame` a tah `mid` patri ramu")
ov2_ = SH.resolve({"panelcount": 2, "panelpos": 100})["vodici"]["ovladani"]
check({"panelpos", "posth", "socketup", "socketside"} <= {t["id"] for t in ov2_["tahy"]}, f"3D: tahy panelpos, posth, socketup, socketside ({sorted(t['id'] for t in ov2_['tahy'])})")
# objednavka: neutralni kusovnik (panel, profily panelu), souhrn voleb
po_ = SH.pro_objednavku({"panelcount": 2, "panelpos": 40, "socketup": 20})          # 2 rady na vychozich stojkach: posun nejvyse 57 mm
check(any(x["nazev"] == "perforovaný panel" and x["mnozstvi"] == 2 for x in po_["bom"]) and any(x["nazev"].startswith("profil") and x["rozmer"] == "1220 mm" and x["mnozstvi"] >= 3 for x in po_["bom"]), f"objednavka: 2 panely a 3 profily panelu 1220 mm ({[ (x['nazev'], x['mnozstvi'], x.get('rozmer')) for x in po_['bom'] if 'panel' in x['nazev'] or x.get('rozmer') == '1220 mm'][:4]})")
sv_ = {x["id"]: x["value"] for x in po_["souhrn"]}
check(sv_.get("panelcount") == "2 ks" and sv_.get("panelpos") == "40 mm" and sv_.get("socketup") == "20 mm" and "midsupport" not in sv_, f"souhrn objednavky: pocet panelu, posun panelu a elektrozlabu ({ {k: sv_.get(k) for k in ('panelcount', 'panelpos', 'socketup')} })")
sw_ = {x["id"]: x["value"] for x in SH.pro_objednavku({"w": 2000, "midsupport": "frame"})["souhrn"]}
check(sw_.get("midsupport") == "Vestavěný rám", f"souhrn: stredni opora uvedena u sirokeho stolu ({sw_.get('midsupport')})")

# --- FORMATY TABULI LAMINODESKY, DELENI DESEK u stredni opory (bot8 2026-10-05) ---
for lg_, txt_ in (("cs", "dělí na dvě desky"), ("en", "split into two boards"), ("sk", "delia na dve dosky")):
    rd_ = SH.resolve({"w": 2000, "midsupport": "legs"}, lang=lg_)
    nd_ = [n for n in rd_["notices"] if n["slot"] == "midsupport" and n["action"] == "info" and txt_ in n["message"]]
    check(len(nd_) == 1 and "2070" in nd_[0]["message"] and "2800" in nd_[0]["message"] and "laminodesk" not in nd_[0]["message"], f"[{lg_}] stul se strednimi nohami: oznameni o deleni desek (tabule 2070 x 2800)")
    rr_ = SH.resolve({"w": 2000, "midsupport": "frame", "shelf": True}, lang=lg_)
    nr_ = [n["message"] for n in rr_["notices"] if txt_ in n["message"]]
    check(len(nr_) == 1 and ("32" in nr_[0]), f"[{lg_}] vestaveny ram: oznameni nese mezeru 32 mm u spodnich polic ({nr_})")
check(not [n for n in SH.resolve({"w": 1200})["notices"] if "dvě desky" in n["message"]], "uzky stul bez stredni opory: zadne oznameni o deleni desek")
check(SH.resolve({"w": 2000})["options"]["mid"] == {"min": 8, "max": 92} and SH.resolve({"w": 3000})["options"]["mid"] == {"min": 7, "max": 93} and SH.resolve({"w": 1200})["options"]["mid"] == {"min": 50, "max": 50},
      f"options.mid: meze polohy stredni nohy z delky desky a odstupu od noh (2000: 8-92, 3000: 7-93 %) ({SH.resolve({'w': 3000})['options']['mid']})")
check(SH.resolve({"w": 3000, "mid": 5})["selection"]["mid"] == 7 and SH.resolve({"w": 3000, "mid": 95})["selection"]["mid"] == 93, "mid mimo meze (3000 mm) se upravi na 7 / 93 %")
try:
    S.nastav_tabuli(1250, 2500)                                      # mensi tabule z karty: hloubka nad 1250 se nevejde
    rt_ = SH.resolve({"d": 1300})
    et_ = [e for e in rt_["errors"] if e["slot"] == "d"]
    check(not rt_["valid"] and len(et_) == 1 and "formátu desky" in et_[0]["message"] and "1250" in et_[0]["message"] and "laminodesk" not in et_[0]["message"], f"mensi tabule: hloubka 1300 = chyba u slotu d s duvodem ({et_})")
finally:
    S.nastav_tabuli(None, None)
check(SH.resolve({"d": 1300})["valid"], "vychozi tabule: hloubka 1300 je v poradku")

# --- POCET SUPLIKU v ocelovem boxu 1 / 2 / 3 (bot8 2026-10-05; Robert: vnejsi vysky 180 / 280 / 450 mm, ceny 3 900 / 5 800 / 5 900 Kc bez DPH) ---
sl_dc = slots.get("drawercount")
check(sl_dc and sl_dc["type"] == "slider" and sl_dc["depends_on"] == ["drawers"] and sl_dc["slider"] == {"min": 1, "max": 3, "step": 1, "unit": "ks"} and sc["default_selection"]["drawercount"] == 2,
      f"slot drawercount: posuvnik 1-3 ks zavisly na drawers, vychozi 2 ({sl_dc and sl_dc.get('slider')})")
for lg_ in ("cs", "en", "sk"):
    sl_ = {x["id"]: x for x in SH.schema(lg_)["slots"]}["drawercount"]
    check(sl_["label"] and sl_["help"] and "{" not in sl_["help"] and "laminodesk" not in sl_["help"], f"[{lg_}] drawercount: popisek a napoveda")
ceny_dc = {}
for n_ in (1, 2, 3):
    rd_ = SH.resolve({"h": 1000, "drawercount": n_})
    check(rd_["valid"] and rd_["selection"]["drawercount"] == n_ and rd_["options"]["drawercount"] == {"min": 1, "max": 3, "value": n_} and not [x for x in rd_["notices"] if x["slot"] == "drawercount"],
          f"{n_} supliky na stole 1000 mm: platne, vyber i options drawercount = {n_} (horni mez 3), bez oznameni")
    ceny_dc[n_] = rd_["price"]["net"]
check(ceny_dc[1] < ceny_dc[2] < ceny_dc[3], f"cena roste s poctem supliku ({ceny_dc})")
for lg_, txt_ in (("cs", "Počet šuplíků snížen na 2"), ("en", "Number of drawers reduced to 2"), ("sk", "Počet zásuviek znížený na 2")):
    rc_ = SH.resolve({"drawercount": 3}, lang=lg_)                                    # vychozi stul 840 mm s policí: 3 supliky se nevejdou -> 2 + oznameni
    nc_ = [x for x in rc_["notices"] if x["slot"] == "drawercount" and x["action"] == "info"]
    check(rc_["selection"]["drawercount"] == 2 and len(nc_) == 1 and txt_ in nc_[0]["message"] and not rc_["errors"], f"[{lg_}] 3 supliky na vychozim stole: snizeno na 2 s oznamenim ({[x['message'][:50] for x in nc_]})")
check(SH.resolve({"drawercount": 3})["hash"] == SH.resolve({})["hash"] and SH.resolve({"drawercount": 3, "drawers": False})["selection"]["drawercount"] == 2, "orez na 2 = tentyz stav (hash) jako vychozi; bez supliku se pocet nepocita")
check(SH.resolve({"h": 600})["selection"]["drawercount"] == 1 and SH.resolve({"h": 600, "drawers": False})["options"]["drawercount"] == {"min": 2, "max": 2}, "nizky stul 600 mm: vychozi 2 supliky se snizi na 1")
check(SH.resolve({})["options"]["drawercount"] == {"min": 1, "max": 3, "value": 2} and SH.resolve({"h": 600})["options"]["drawercount"] == {"min": 1, "max": 3, "value": 1},
      "options.drawercount: posuvnik 1-3 vzdy, value = efektivni pocet (oriznuty pocet nese oznameni, posuvnik se nezamyka)")
p_dc, _ = SH.normalizuj({"h": 1000, "drawercount": 3})
check(SH.over_model(SH.podepis_model(p_dc))[0]["suplik_pocet"] == 3 and "D" not in SH._zabal(SH.normalizuj({})[0]) and SH._zabal(p_dc).get("D") == 3, "token modelu nese pocet supliku (klic D; vychozi 2 bez klice)")
for n_, nazev_ in ((1, "šuplíkový box (1 šuplík)"), (2, "šuplíkový box"), (3, "šuplíkový box (3 šuplíky)")):
    po_ = SH.pro_objednavku({"h": 1000, "drawercount": n_})
    check([x["nazev"] for x in po_["bom"] if "uplík" in x["nazev"]] == [nazev_] and {x["id"]: x["value"] for x in po_["souhrn"]}.get("drawercount") == f"{n_} ks", f"{n_} supliky: objednavka nese '{nazev_}' a souhrn '{n_} ks'")
for v_ in ({"drawercount": 3}, {"drawercount": 3, "h": 1000}, {"drawercount": 1, "h": 600}):          # zadne technicke udaje ve verejne odpovedi (viz ZAKAZANE vyse; mimo hlavni smycku, ta je u hranice limitu pozadavku)
    for lg_ in ("cs", "en", "sk"):
        txt_ = re.sub(r'"url": "[^"]*"', '"url": ""', json.dumps(post({"product_id": PID, "selection": v_, "lang": lg_}).get_json(), ensure_ascii=False))
        spatne_ = [z for z in ZAKAZANE if re.search(z, txt_)]
        check(not spatne_, f"[{lg_}] {v_}: v odpovedi nejsou technicke udaje ({spatne_})")
ov_dc = SH.resolve({"h": 1000})["vodici"]["ovladani"]
cast_dc = next(c for c in ov_dc["casti"] if c["id"] == "drawers")
check("drawercount" in cast_dc["param"] and sorted(m["nastav"]["drawercount"] for m in cast_dc["menu"] if m.get("nastav") and "drawercount" in m["nastav"]) == [1, 3], f"3D: cast drawers nabizi box s 1 a 3 supliky ({[m['text'] for m in cast_dc['menu']]})")
for lg_, txt_ in (("en", "Unit with 1 drawer"), ("sk", "Box s 1 zásuvkou")):                  # chybejici preklad by 3D ovladani v jazyce POTICHU vynechal (log "ovladani ve 3D vynechano")
    ov_l = (SH.resolve({"h": 1000}, lang=lg_).get("vodici") or {}).get("ovladani") or {}
    cast_l = next((c for c in ov_l.get("casti", []) if c["id"] == "drawers"), None)
    check(cast_l is not None and any(txt_ in m["text"] for m in cast_l["menu"]), f"[{lg_}] 3D menu sufliku je prelozene ({txt_})")

# --- PANELY DO STRAN (bot8 2026-10-05; Robert: "panely chceme pohyblive, pokud maji mezi nohama mezeru") ---
sl_ps = slots.get("panelside")
check(sl_ps and sl_ps["type"] == "slider" and sl_ps["depends_on"] == ["panels"] and sl_ps["slider"]["step"] == 1 and sl_ps["slider"]["unit"] == "mm" and sc["default_selection"]["panelside"] == 0,
      f"slot panelside: posuvnik po 1 mm zavisly na panels, vychozi 0 ({sl_ps and sl_ps.get('slider')})")
for lg_ in ("cs", "en", "sk"):
    sl_ = {x["id"]: x for x in SH.schema(lg_)["slots"]}["panelside"]
    check(sl_["label"] and sl_["help"] and "{" not in sl_["help"] and "laminodesk" not in sl_["help"] and "spojk" not in sl_["help"], f"[{lg_}] panelside: popisek a napoveda ({sl_['label']})")
r_ps = SH.resolve({})
lim_ps = r_ps["options"]["panelside"]["max"]
check(r_ps["options"]["panelside"] == {"min": -lim_ps, "max": lim_ps, "value": 0} and lim_ps >= 1 and r_ps["selection"]["panelside"] == 0, f"vychozi stul: options.panelside = ±{lim_ps} mm (mezera u noh minus 1 mm), value 0")
rv_ = SH.resolve({"panelside": 7})
check(rv_["selection"]["panelside"] == 7 and rv_["options"]["panelside"]["value"] == 7 and rv_["valid"] and rv_["hash"] != r_ps["hash"], "posun 7 mm: vyber i value 7, platne, jiny hash")
check(SH.resolve({"panelside": 10 ** 4})["selection"]["panelside"] == lim_ps and SH.resolve({"panelside": -10 ** 4})["selection"]["panelside"] == -lim_ps, f"mimo meze se orizne na ±{lim_ps} (server vraci efektivni hodnotu)")
check(SH.resolve({"panelside": 7, "panels": False})["selection"]["panelside"] == 0 and SH.resolve({"panelside": 7, "panels": False})["options"]["panelside"] == {"min": 0, "max": 0}
      and SH.resolve({"panelside": 7, "panels": False})["hash"] == SH.resolve({"panels": False})["hash"], "bez panelu se posun nepocita (vyber 0, options bez rozsahu, stejny hash)")
check(SH.resolve({"w": 1500})["options"]["panelside"]["max"] > lim_ps and SH.resolve({"w": 2600, "panelcount": 2, "midsupport": "legs"})["options"]["panelside"]["max"] >= 1, "sirsi stul: vetsi mezera = vetsi rozsah; dva useky u stredni nohy maji spolecny rozsah")
p_ps, _ = SH.normalizuj({"panelside": 7})
tok_ = SH.over_model(SH.podepis_model(S.sestav_stul(**p_ps)["parametry"]))[0]
check(tok_["panely_z"] == 7.0 and "X" not in SH._zabal(SH.normalizuj({})[0]) and SH._zabal(S.sestav_stul(**p_ps)["parametry"]).get("X") == 7.0, "token modelu nese posun panelu (klic X; vychozi 0 bez klice)")
check({x["id"]: x["value"] for x in SH.pro_objednavku({"panelside": 7})["souhrn"]}.get("panelside") == "7 mm" and "panelside" not in {x["id"] for x in SH.pro_objednavku({})["souhrn"]}, "objednavka: souhrn ukaze posun panelu jen kdyz je nenulovy")
ov_ps = SH.resolve({"panelside": 3})["vodici"]["ovladani"]
t_ps = next((t for t in ov_ps["tahy"] if t["id"] == "panelside"), None)
check(t_ps and t_ps["param"] == "panelside" and t_ps["min"] == -lim_ps and t_ps["max"] == lim_ps and t_ps["krok"] == 1.0 and len(t_ps["mereni"]) == 2 and t_ps.get("zive"), f"3D: tah panelside (meze, krok 1, mereni od obou noh, zive operace) ({t_ps and (t_ps['min'], t_ps['max'], [m['label'] for m in t_ps['mereni']])})")
cast_ps = next(c for c in ov_ps["casti"] if c["id"] == "panels")
check("panelside" in cast_ps["param"] and any(m.get("nastav") == {"panelside": 0} for m in cast_ps["menu"]), "3D: cast panels ma polozku 'vratit doprostred' (panelside = 0)")
for lg_, lab_, mer_ in (("en", "Panels sideways", ["from the left leg", "from the right leg"]), ("sk", "Panely do strán", ["od ľavej nohy", "od pravej nohy"])):
    ov_l = (SH.resolve({"panelside": 3}, lang=lg_).get("vodici") or {}).get("ovladani") or {}
    t_l = next((t for t in ov_l.get("tahy", []) if t["id"] == "panelside"), None)
    check(t_l is not None and t_l["label"] == lab_ and [m["label"] for m in t_l["mereni"]] == mer_, f"[{lg_}] 3D tah panelside je prelozeny ({t_l and t_l['label']}, {t_l and [m['label'] for m in t_l['mereni']]})")
r2_ps = SH.resolve({"w": 2600, "panelcount": 2, "midsupport": "legs", "panelside": 3}, lang="sk")
t2_ps = next(t for t in r2_ps["vodici"]["ovladani"]["tahy"] if t["id"] == "panelside")
check([m["label"] for m in t2_ps["mereni"]] == ["ľavý panel od ľavej nohy", "ľavý panel od strednej nohy", "pravý panel od strednej nohy", "pravý panel od pravej nohy"], f"dva panely: mereni od vsech noh ({[m['label'] for m in t2_ps['mereni']]})")
for v_ in ({"panelside": 7}, {"panelside": -9, "w": 1500}):                                   # zadne technicke udaje ve verejne odpovedi (viz ZAKAZANE vyse)
    for lg_ in ("cs", "en", "sk"):
        txt_ = re.sub(r'"url": "[^"]*"', '"url": ""', json.dumps(post({"product_id": PID, "selection": v_, "lang": lg_}).get_json(), ensure_ascii=False))
        spatne_ = [z for z in ZAKAZANE if re.search(z, txt_)]
        check(not spatne_, f"[{lg_}] {v_}: v odpovedi nejsou technicke udaje ({spatne_})")

# --- NAHODNY VYBER (fuzz, pevne semeno): zadna kombinace voleb nesmi shodit resolve (vyjimka = 500 na produkci); vzdy hash, cele options/selection, chyby s textem, 3D ovladani u platnych
import random as _random
_rng = _random.Random(20261005)
_sc = SH.schema("cs")
_vyj, _n_platnych = [], 0
for _i in range(120):
    _sel = {}
    for _s in _sc["slots"]:
        if _rng.random() < 0.5:
            continue
        if _s["type"] == "toggle":
            _sel[_s["id"]] = _rng.random() < 0.5
        elif _s["type"] == "select":
            _sel[_s["id"]] = _rng.choice([o["id"] for o in _s["options"]])
        else:
            _lo, _hi, _st = _s["slider"]["min"], _s["slider"]["max"], _s["slider"]["step"]
            _sel[_s["id"]] = _rng.choice([_lo, _hi, _lo + _st * _rng.randint(0, int((_hi - _lo) // _st)), _lo + _st * _rng.randint(0, int((_hi - _lo) // _st)), _hi + 700 if _rng.random() < 0.1 else _lo - 700])
    _lg, _sy = _rng.choice(("cs", "en", "sk")), _rng.choice((30, 40))
    try:
        _r = SH.resolve(_sel, lang=_lg, system=_sy)
        _ok = (isinstance(_r["valid"], bool) and len(_r["hash"]) == 16 and set(_r["selection"]) == set(slots) and set(_r["options"]) >= set(slots)
               and all(e["message"] and "slot" in e for e in _r["errors"]) and all(n["message"] for n in _r["notices"]) and all(o["message"] and o["label"] for o in _r["offers"])
               and (not _r["valid"] or (_r["vodici"] and _r["vodici"].get("ovladani"))))
        if not _ok:
            _vyj.append((_sel, _lg, _sy, "neuplna odpoved"))
        _n_platnych += 1 if _r["valid"] else 0
    except Exception as _e:               # noqa: BLE001
        _vyj.append((_sel, _lg, _sy, f"{type(_e).__name__}: {_e}"))
check(not _vyj, f"fuzz 120 nahodnych vyberu (cs/en/sk, system 30/40): zadna vyjimka ani neuplna odpoved ({len(_vyj)}: {str(_vyj[:1])[:300]}); platnych {_n_platnych}")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
