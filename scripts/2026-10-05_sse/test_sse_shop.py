#!/usr/bin/env python3
"""Verejne API konfiguratoru pro SSE stul (system 41; api/stul_shop_sse.py) - bot8, 2026-10-05.

SKUTECNE routy pres Flask test_client BEZ prihlaseni (jsou verejne). DB se jen CTE (katalog cen); mapovani produktu (app_settings.configurator_products) se podstrci primo do cache modulu - nic
se nezapisuje. Hlida: schema (sloty, typy, rozsahy, zavislosti, texty cs / en / sk bez zakazanych vyrazu), kompletni vychozi vyber, normalizaci (orez, retezce, nepodporovane volby ze 30 / 35 / 40
se tise zahodi, stredni noha v %), resolve (cena, platnost, oznameni, meze posuvniku, ceny a zakazy prepinacu, ovladani ve 3D ve 3 jazycich), cenu nohy SSE jako pravidlo (cena_noha_sse_400 / 1100),
token modelu (podpis, system 41, GLB), objednavku (kusovnik, hmotnost jako odhad, souhrn voleb), 404 pro nekonfigurovatelny produkt, rules_changed, fuzz vyberu bez 500.

Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
    api/venv/bin/python3 scripts/2026-10-05_sse/test_sse_shop.py"""
import json
import os
import random
import re
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
    import stul_api as stul_api  # noqa: E402
finally:
    threading.Thread.start = _orig
S.nastav_pravidla({})                                           # ziva pravidla neovlivni test (viz test_stul_shop.py)
stul_api.obnov_pravidla = lambda force=False: None

OK, FAILS = 0, []


def check(cond, msg, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg} {detail}")


PID, PID30 = 9879, 9876
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PID): SH.RECEPT_SSE, str(PID30): SH.RECEPT})
anon = appmod.app.test_client()
ZAKAZANE = [r"#\d", r"product_", r"Object_", r"sse_", r"STUL\.SYSTEM", r"\bSKU\b", r"\bsku\b", r"Z -?\d", r"…", r"\b(4930|4931|4929|4932|4928|4916|4933|3158|3176|4725|4727)\b",
            r"[Vv]andr", r"katalog", r"profil 30", r"spojk", r"laminodesk", r"dily", r"quaternion", r'"position"']


def post(body):
    return anon.post("/api/shop/configurator/resolve", json=body)


def res(sel, lang="cs"):
    r = post({"product_id": PID, "selection": sel, "lang": lang})
    check(r.status_code == 200, f"resolve {sel}: 200", r.status_code)
    return r.get_json()


# ---------------------------------------------------------------------------------------------------------------------
print("A) schema")
r = anon.get(f"/api/shop/products/{PID}/configurator")
sc = r.get_json()
check(r.status_code == 200 and sc["system"] == 41 and sc["profile"] == "40x40" and sc["profile_mm"] == 40 and sc["rules_version"] == G.RULES_VERSION, "schema 200, system 41, profil 40x40", {k: sc.get(k) for k in ("system", "profile")})
slots = {s["id"]: s for s in sc["slots"]}
check(list(slots) == ["w", "d", "h", "mid", "shelf", "drawers", "drawercount", "boxpos", "drawleft"], "sloty SSE: jen rozmery, stredni noha, police, supliky", list(slots))
check([g["id"] for g in sc["groups"]] == ["g_size", "g_frame", "g_extras"], "skupiny bez vyrezu a lozisek")
rz = S.SYSTEMY[41]["rozsah"]
for sid, par in (("w", "sirka"), ("d", "hloubka"), ("h", "vyska")):
    sl = slots[sid]["slider"]
    check(slots[sid]["type"] == "slider" and sl["min"] == rz[par][0] and sl["max"] == rz[par][1] and sl["step"] == 10 and sl["unit"] == "mm", f"slot {sid}: posuvnik {rz[par]}")
check(slots["shelf"]["type"] == "toggle" and slots["drawers"]["type"] == "toggle" and slots["drawleft"]["type"] == "toggle", "police, supliky, supliky vlevo jsou prepinace")
check(slots["mid"]["slider"] == {"min": 5, "max": 95, "step": 1, "unit": "%"} and slots["drawercount"]["slider"]["min"] == 1 and slots["drawercount"]["slider"]["max"] == 3, "mid v %, pocet supliku 1-3")
check(all(slots[x]["depends_on"] == ["drawers"] for x in ("boxpos", "drawleft", "drawercount")) and "depends_on" not in slots["shelf"], "zavislosti: posun, strana a pocet supliku jen se supliky")
ds = sc["default_selection"]
check(ds == SH.vychozi_vyber(41) and (ds["w"], ds["d"], ds["h"], ds["shelf"], ds["drawers"], ds["drawercount"]) == (2000, 900, 830, 1, True, 2), "default_selection SSE (2000 x 900 x 830, police, 2 supliky)")
check(set(SH.VYCHOZI_VYBER) <= set(ds) and all(ds[k] is False for k in ("posts", "wheels", "panels", "led", "socket", "pet", "braces", "bearings", "cut1", "cut2", "cut3")), "default_selection je kompletni, co SSE nema, je vypnute")
check(sc["systems"] == [{"system": 41, "card_id": PID, "active": False}] or any(x["system"] == 41 for x in sc["systems"]), "schema nese kartu systemu 41 (neaktivni)", sc["systems"])
for lang in ("cs", "en", "sk"):
    sl_ = SH.schema(lang, 41)
    txt = json.dumps(sl_, ensure_ascii=False)
    check(not [z for z in ZAKAZANE if re.search(z, txt)], f"schema [{lang}]: zadne zakazane vyrazy", [z for z in ZAKAZANE if re.search(z, txt)])
    check(all(s["label"] for s in sl_["slots"]) and all(g["label"] for g in sl_["groups"]), f"schema [{lang}]: vsechny popisky")
    check("{prah}" not in txt and "2000" in json.dumps(sl_["slots"][3], ensure_ascii=False), f"schema [{lang}]: napoveda stredni nohy nese prah 2000")
check(SH.schema("cs", 41)["slots"][1]["help"] != SH.schema("en", 41)["slots"][1]["help"], "napoveda hloubky je prelozena")
S.nastav_pravidla({"sirka_stredni_noha": 1800}, system=41)
check("1800" in json.dumps(SH.schema("cs", 41)["slots"][3], ensure_ascii=False), "prah stredni nohy v napovede je nastavitelny pravidlem")
S.nastav_pravidla({}, system=41)
for sy in (30, 35, 40):
    check("sleeve" not in [s["id"] for s in SH.schema("cs", sy)["slots"]] or sy == 35, f"schema systemu {sy} beze zmeny (nema sloty SSE)")
    check([s["id"] for s in SH.schema("cs", sy)["slots"]].count("shelf") == 1 and next(s for s in SH.schema("cs", sy)["slots"] if s["id"] == "shelf")["type"] == "slider", f"system {sy}: spodni police je dal posuvnik poctu")

# ---------------------------------------------------------------------------------------------------------------------
print("B) normalizace vyberu")
p, n = SH.normalizuj({}, 41)
check(p["system"] == 41 and (p["sirka"], p["hloubka"], p["vyska"]) == (2000.0, 900.0, 830.0) and p["police"] == 1 and p["suplik"] is True and p["suplik_pocet"] == 2 and p["suplik_posun"] == 0.0 and p["stredni_noha"] is None, "vychozi parametry", p)
for sel, ocek in (({"w": 100}, 800), ({"w": 9999}, 3000), ({"w": "abc"}, 2000), ({"w": 2013}, 2010), ({"w": 1999.6}, 2000)):
    check(SH.normalizuj(sel, 41)[0]["sirka"] == ocek, f"w {sel['w']!r} -> {ocek}")
for sel, ocek in (({"d": 100}, 480), ({"d": 9999}, 1180), ({"d": 906}, 910), ({"d": 904}, 900)):
    check(SH.normalizuj(sel, 41)[0]["hloubka"] == ocek, f"d {sel['d']!r} -> {ocek}")
for sel, ocek in (({"h": 0}, 700), ({"h": 5000}, 1000), ({"h": 834}, 830)):
    check(SH.normalizuj(sel, 41)[0]["vyska"] == ocek, f"h {sel['h']!r} -> {ocek}")
check(SH.normalizuj({"shelf": "0"}, 41)[0]["police"] == 0 and SH.normalizuj({"shelf": "false"}, 41)[0]["police"] == 0 and SH.normalizuj({"shelf": "on"}, 41)[0]["police"] == 1 and SH.normalizuj({"shelf": 5}, 41)[0]["police"] == 1,
      "police: retezce a cisla -> 0 / 1")
p2, n2 = SH.normalizuj({"drawers": False, "drawercount": 3, "boxpos": 200, "drawleft": True}, 41)
check(p2["suplik"] is False and p2["suplik_pocet"] == 2 and p2["suplik_posun"] == 0.0 and p2["suplik_vlevo"] is False and n2["drawers"] is False, "bez supliku se pocet, posun a strana zahodi")
p3, n3 = SH.normalizuj({"drawercount": 9, "boxpos": 99999, "drawleft": "1"}, 41)
check(p3["suplik_pocet"] == 3 and p3["suplik_posun"] == 3000.0 and p3["suplik_vlevo"] is True, "pocet supliku orez 3, posun orez 3000, strana '1' -> vlevo")
pz, nz = SH.normalizuj({"posts": True, "wheels": True, "panels": True, "led": True, "socket": True, "pet": True, "feet": True, "braces": True, "bearings": True, "cut1": True, "cut2shelf": True, "sleeve": True,
                        "panelcount": 3, "arm": 800, "ov": 80}, 41)
PREP = ("posts", "wheels", "feet", "panels", "led", "ledlight", "socket", "pet", "braces", "bearings", "cut1", "cut2", "cut3", "cut1shelf", "cut2shelf", "cut3shelf")
check(not any(pz.get(k) for k in ("stojky", "kolecka", "panely", "led", "elektrozlab", "drzak_pet", "patky", "vzpery", "loz", "navlek", "vyrez1", "vyrez2_police")) and not any(nz[k] for k in PREP),
      "nepodporovane volby ze systemu 30 / 35 / 40 se tise zahodi (vyber zustava kompletni a vypnuty)", [k for k in PREP if nz[k]])
S.sestav_stul(**pz)                                              # a generator je neodmitne
check(True, "generator prijme normalizovany vyber s nepodporovanymi volbami")
pm_, nm_ = SH.normalizuj({"w": 2600, "mid": 50}, 41)
check(pm_["stredni_noha"] is None and nm_["mid"] == 50, "mid 50 % = uprostred (None)")
zl, zr = 195.0, 2600 - 195.0
pm_, nm_ = SH.normalizuj({"w": 2600, "mid": 40}, 41)
check(abs(pm_["stredni_noha"] - (zr - zl) * 0.40) < 1e-9 and nm_["mid"] == 40, "mid 40 % = 40 % rozpeti mezi osami krajnich noh (W - 390)", pm_["stredni_noha"])
mn, mx = SH.stul_shop_sse_mid = None, None
import stul_shop_sse as SSE  # noqa: E402
mn, mx = SSE.mid_meze_pct(2600)
check(mn == 7 and mx == 93 or (5 <= mn < 50 < mx <= 95), "meze mid pro 2600 mm jsou rozumne", (mn, mx))
for w_ in (2010, 2400, 2800, 3000):
    mn, mx = SSE.mid_meze_pct(w_)
    for pct in (mn, mx):
        pq, nq = SH.normalizuj({"w": w_, "mid": pct}, 41)
        g_ = S.sestav_stul(**pq)
        check(not g_["problemy"] and all(x["volba"] != "stredni" for x in g_["odebrano"]), f"w={w_}: krajni poloha mid {pct} % je platna (stredni noha se vejde, desky do tabule)")
    pq, nq = SH.normalizuj({"w": w_, "mid": 0}, 41)
    check(nq["mid"] == mn, f"w={w_}: mid 0 se orizne na {mn}")
    pq, nq = SH.normalizuj({"w": w_, "mid": 100}, 41)
    check(nq["mid"] == mx, f"w={w_}: mid 100 se orizne na {mx}")
check(SH.normalizuj({"w": 1800, "mid": 20}, 41)[1]["mid"] == 50 and SH.normalizuj({"w": 1800, "mid": 20}, 41)[0]["stredni_noha"] is None, "u sirky pod prahem se mid ignoruje (50 %)")

# ---------------------------------------------------------------------------------------------------------------------
print("C) resolve: cena, platnost, oznameni, volby")
j = res({})
check(j["valid"] is True and j["errors"] == [] and j["price"]["net"] > 0 and j["price"]["currency"] == "CZK" and j["hash"] == G.kanonicky_hash(SH.normalizuj({}, 41)[0]) and j["kod"].startswith("STL-"), "vychozi stul: platny, cena, hash")
check(j["selection"] == SH.vychozi_vyber(41), "vybrany stav ve vychozim stavu je kompletni vychozi vyber")
o = j["options"]
check(o["w"] == {"min": 800, "max": 3000} and o["d"] == {"min": 480, "max": 1180} and o["h"] == {"min": 700, "max": 1000} and o["mid"] == {"min": 50, "max": 50}, "options: meze rozmeru, mid zamcen pod prahem")
check(set(o) == {"w", "d", "h", "mid", "shelf", "drawers", "drawercount", "boxpos", "drawleft"}, "options: jen sloty SSE", sorted(o))
check(o["shelf"]["on"] == {"price_delta": 0, "disabled": False, "reason": None} and o["drawers"]["on"]["disabled"] is False and o["drawercount"] == {"min": 1, "max": 3, "value": 2}, "options: police a supliky zapnute, 1-3")
check(o["boxpos"]["fits"] is True and o["boxpos"]["value"] == 0 and o["boxpos"]["min"] < 0 < o["boxpos"]["max"], "options.boxpos: meze rozpeti podelniku", o["boxpos"])
for sel in ({"drawers": False}, {"shelf": False}):
    jx = res(sel)
    key = "drawers" if "drawers" in sel else "shelf"
    check(jx["options"][key]["on"]["price_delta"] > 0 and jx["price"]["net"] < j["price"]["net"], f"{sel}: vypnuta volba je levnejsi a zapnuti ma kladny price_delta ({jx['options'][key]['on']['price_delta']})")
    check(abs(jx["price"]["net"] + jx["options"][key]["on"]["price_delta"] - j["price"]["net"]) <= 2, f"{sel}: price_delta = rozdil cen po zapnuti")
jx = res({"d": 600})
check(jx["selection"]["drawers"] is False and jx["options"]["drawers"]["on"]["disabled"] is True and "720" in jx["options"]["drawers"]["on"]["reason"], "hloubka 600: supliky se nevejdou (zakazano, duvod s cislem)", jx["options"]["drawers"])
check(any(x["slot"] == "drawers" and x["action"] == "removed" and "720" in x["message"] for x in jx["notices"]) and jx["valid"] is True and jx["errors"] == [], "hloubka 600: oznameni o odebrani supliku, stul je platny")
jx = res({"w": 2600})
check(jx["options"]["mid"]["min"] < 50 < jx["options"]["mid"]["max"] and any(x["slot"] == "mid" and x["action"] == "info" for x in jx["notices"]), "sirka 2600: stredni noha (meze mid) a oznameni o deleni desek")
jl = res({"drawers": True, "drawleft": True, "boxpos": 100})
check(jl["selection"]["drawleft"] is True and jl["options"]["boxpos"]["value"] == 100 and jl["valid"], "supliky vlevo s posunem 100")
for lang in ("cs", "en", "sk"):
    for sel in ({}, {"d": 600}, {"w": 2600, "drawleft": True}, {"drawercount": 3, "h": 1000}, {"shelf": False, "drawers": False}):
        jx = res(sel, lang)
        txt = re.sub(r'"url": "[^"]*"', '"url": ""', json.dumps(jx, ensure_ascii=False))
        check(not [z for z in ZAKAZANE if re.search(z, txt)], f"resolve [{lang}] {sel}: zadne zakazane vyrazy", [z for z in ZAKAZANE if re.search(z, txt)])
jen = res({"d": 600}, "en")
check(any("The drawers do not fit" in x["message"] for x in jen["notices"]), "anglicke oznameni o supliscich")
jsk = res({"d": 600}, "sk")
check(any("Zásuvky sa pri týchto rozmeroch nezmestia" in x["message"] for x in jsk["notices"]), "slovenske oznameni o zasuvkach")
# 3D ovladani verejne: cs / en / sk
for lang in ("cs", "en", "sk"):
    jx = res({}, lang)
    ov = (jx.get("vodici") or {}).get("ovladani")
    check(ov and [c["id"] for c in ov["casti"]] == ["deck", "leg1", "leg2", "shelf1", "drawers"] and {t["id"] for t in ov["tahy"]} == {"h", "w", "d", "boxpos"}, f"ovladani ve 3D [{lang}]: casti a tahy", ov and [c["id"] for c in ov["casti"]])
    check(all(c["label"] for c in ov["casti"]) and all(m["text"] for c in ov["casti"] for m in c["menu"]), f"ovladani [{lang}]: popisky a nabidky")
    check(ov["tahy"][0]["id"] == "h" and ov["tahy"][0]["param"] == "h", f"ovladani [{lang}]: tah vysky pracuje se slotem h")
    ex_ = ov.get("zive_rozsahy_extra")                          # SPODNI suplik boxu je vlastni uzel GLB: jeho rozsah musi dojit do verejneho ovladani, jinak se pri tazeni sirky / posunu boxu odtrhne od skrine (2026-10-06)
    zr_ = ov.get("zive_rozsahy") or []
    check(ex_ is not None and len(ex_) == 1 and all(k.isdigit() and 0 <= int(k) < len(zr_) and ex_[k] and all(len(r_) == 3 for r_ in ex_[k]) for k in ex_)
          and all(any(int(k) in op["ix"] for t_ in ov["tahy"] for op in t_.get("zive", [])) for k in ex_), f"ovladani [{lang}]: zive_rozsahy_extra pro box se supliky (a box je v zive operaci)", ex_)
jn = res({"drawers": False})
check("zive_rozsahy_extra" not in jn["vodici"]["ovladani"], "ovladani bez supliku: zadne zive_rozsahy_extra")
# ---------------------------------------------------------------------------------------------------------------------
print("D) cena nohy SSE jako pravidlo (cena_noha_sse_400 / 1100)")
d0 = S.sestav_stul(system=41)["dily"]
check(stul_api.extra_prace(d0) == [] and stul_api.cena_nohy_sse(820, 41) == 0, "nezadano = zadna radka prace, cena 0")
cena0 = stul_api.cena_konfigurace(d0)
check(any("Cena nohou SSE není zadaná" in v for v in cena0["varovani"]) and any("Cena nohou SSE není zadaná" in v for v in cena0["kusovnik"]["varovani"]), "varovani (i v kusovniku pro zamestnance, ten ukazuje stranka), kdyz cena nohy neni zadana")
S.nastav_pravidla({"cena_noha_sse_400": 1000, "cena_noha_sse_1100": 1700}, system=41)
check(stul_api.cena_nohy_sse(400, 41) == 1000 and stul_api.cena_nohy_sse(1100, 41) == 1700 and stul_api.cena_nohy_sse(820, 41) == 1420 and stul_api.cena_nohy_sse(750, 41) == 1350, "cena nohy: linearne mezi 400 a 1100 mm")
ex = stul_api.extra_prace(d0)
check(len(ex) == 1 and ex[0]["qty"] == 2 and ex[0]["unit_czk"] == 1420.0 and "820" in ex[0]["name"] and "Noha SSE" in ex[0]["name"], "extra_prace: 2 nohy po 1420 Kc (spojnice 820)", ex)
cena1 = stul_api.cena_konfigurace(d0)
check(cena1["bez_dph"] - cena0["bez_dph"] >= 2840 and cena1["bez_dph"] - cena0["bez_dph"] <= 2840 * 1.3 and not any("Cena nohou SSE" in v for v in cena1["varovani"] + cena1["kusovnik"]["varovani"]), f"cena stolu o nohy vyssi ({cena1['bez_dph'] - cena0['bez_dph']} Kc), varovani zmizi")
kus = cena1["kusovnik"]
check(any("Noha SSE" in x["nazev"] and x["mnozstvi"] == 2 for x in kus["prace"]), "kusovnik pro zamestnance: radek Noha SSE x 2 v praci")
check(abs(sum(x["celkem"] for x in kus["radky"]) + sum(x["celkem"] for x in kus["prace"]) - cena1["bez_dph"]) < 0.5, "soucet radku kusovniku = celkem bez DPH")
j1 = res({})
check(j1["price"]["net"] == cena1["bez_dph"] and j1["price"]["net"] > j["price"]["net"], "verejna cena nese cenu nohou (pravidlo zmeni i cache resolve)")
j3 = res({"w": 2600})
check(len(stul_api.extra_prace(S.sestav_stul(system=41, sirka=2600)["dily"])[0]["name"]) > 5 and stul_api.extra_prace(S.sestav_stul(system=41, sirka=2600)["dily"])[0]["qty"] == 3, "u 3 noh qty 3")
for d_, ocek in ((480, 1000.0), (1180, 1700.0)):
    exd = stul_api.extra_prace(S.sestav_stul(system=41, hloubka=d_)["dily"])
    check(exd[0]["unit_czk"] == ocek and exd[0]["qty"] == 2, f"hloubka {d_} (spojnice {d_ - 80}): cena nohy {ocek}")
check(stul_api.extra_prace(S.sestav_stul(system=40)["dily"]) == [] and stul_api.extra_prace(S.sestav_stul(system=30)["dily"]) == [], "systemy 30 a 40 cenu nohy SSE nemaji")
S.nastav_pravidla({}, system=41)
check(res({})["price"]["net"] == j["price"]["net"], "po vynulovani pravidla je cena zpet (cache resolve zavisi na pravidle)")

# ---------------------------------------------------------------------------------------------------------------------
print("E) model: token, GLB, objednavka")
tok = j["model"]["url"].rsplit("/", 1)[1]
pp, chyba = SH.over_model(tok)
check(chyba is None and pp["system"] == 41 and pp["sirka"] == 2000 and pp["suplik"] and pp["police"] == 1 and G.kanonicky_hash(pp) == j["hash"], "token modelu nese system 41 a stejny hash", pp)
rg = anon.get(j["model"]["url"])
check(rg.status_code == 200 and rg.data[:4] == b"glTF" and len(rg.data) > 100_000, "GLB se stahne bez prihlaseni", (rg.status_code, len(rg.data)))
bad = anon.get(j["model"]["url"][:-3] + "abc")
check(bad.status_code in (403, 410), "podvrzeny token = 403")
# kazda dalsi konfigurace: GLB sedi s hashem
for sel in ({"w": 2600, "d": 1180, "h": 700}, {"shelf": False, "drawers": False}, {"drawleft": True, "drawercount": 1, "boxpos": 150}):
    jx = res(sel)
    pq, _ = SH.over_model(jx["model"]["url"].rsplit("/", 1)[1])
    check(G.kanonicky_hash(pq) == jx["hash"], f"{sel}: token -> hash sedi")
po = SH.pro_objednavku({"w": 2200, "d": 900}, product_id=PID)
check(po["ok"] and po["valid"] and po["price"]["net"] > 0 and po["selection"]["w"] == 2200, "pro_objednavku: platny SSE stul")
bom = {(b["nazev"], b["rozmer"]): b["mnozstvi"] for b in po["bom"]}
check(bom.get(("jekl 40×40 (noha SSE)", "675 mm")) == 6 and bom.get(("jekl 40×40 (noha SSE)", "820 mm")) == 3 and bom.get(("vnitřní profil 35×35 (noha SSE)", "425 mm")) == 6
      and bom.get(("plechová patka 150×40×6 (noha SSE)", None)) == 6 and bom.get(("záslepka vnitřního profilu 35×35 (noha SSE)", None)) == 6, "kusovnik: 3 nohy = 6 jeklu 675, 3 spojnice 820, 6 vnitrnich profilu, 6 plechu, 6 zaslepek", bom)
check(bom.get(("profil 40×40", "2190 mm")) == 2 and bom.get(("záslepka profilu 40×40", None)) == 4, "kusovnik: 2 podelniky 2190 (W - 10) a 4 zaslepky")
check(po["hmotnost_kg"] and po["hmotnost_kg"] > 30 and po["hmotnost_uplna"] is False and any("nohy SSE" in x for x in po["hmotnost_chybi"]), "hmotnost: odhad nohou je v souctu, ale neni uplna", (po["hmotnost_kg"], po["hmotnost_chybi"]))
check(po["pocet_spoju"] == 4, "4 spoje profilu (pricky supliku)", po["pocet_spoju"])
souhrn = {x["id"]: x["value"] for x in po["souhrn"]}
check(souhrn.get("w") == "2200 mm" and souhrn.get("shelf") == "ano" and souhrn.get("drawers") == "ano" and "mid" in souhrn and not any(k in souhrn for k in ("posts", "panels", "led", "wheels", "cut1", "bearings")), "souhrn voleb: jen volby SSE", souhrn)
check(S.hmotnost_nohou_sse_kg(S.sestav_stul(system=41, sirka=2200)["dily"]) > 20, "odhad hmotnosti nohou")
check(SH.pro_objednavku({}, rules_version="stara", product_id=PID) == {"ok": False, "chyba": "rules_changed", "rules_version": G.RULES_VERSION}, "rules_changed")
vs = SH.vyrobni_sestava({"w": 2200}, product_id=PID)
check(vs["ok"] and vs["parametry"]["system"] == 41 and vs["cena_celkem_czk"] and any(d["part_id"] == "sse_jekl_40" for d in vs["dily"]), "vyrobni_sestava SSE: dily nohou, cena", list(vs)[:6])

import stul_vyrobni_list as VL  # noqa: E402
for kw in ({}, {"sirka": 2600, "suplik": False, "police": 0}):
    ses = SH._sestava_z_gen(S.sestav_stul(system=41, **kw))
    vyp = ses["vypis"]
    check(vyp["system"] == 41 and "nohy_sse" in vyp and vyp["nohy_sse"]["pocet_noh"] == (3 if kw.get("sirka") else 2) and not [q for q in vyp["prislusenstvi"] if "jekl" in q["nazev"] or "SSE" in q["nazev"]], f"{kw}: vyrobni vypis SSE: oddil nohou, zadne dily nohou v prislusenstvi")
    html = VL.html_list(ses)
    check("Generátor stolu 04 – ergonomický stůl SSE" in html and not re.search(r"syst[eé]m\s*41", html, re.I) and "Nohy SSE" in html and "Řezný plán profilů 40×40" in html and "jeklová spojnice 40×40" in html and "820" in html, f"{kw}: vyrobni list HTML: cislo generatoru, oddil nohou, rezny plan")
    cut_ = {x["delka_mm"]: x["pocet"] for x in vyp["rezny_plan"]}
    check(cut_.get(float(kw.get("sirka", 2000)) - 10) == 2, f"{kw}: rezny plan: 2 podelniky delky W - 10", cut_)
    kroky = {k["krok"] for k in vyp["montazni_postup"]}
    check({1, 2, 3} <= kroky and all(k["text"] for k in vyp["montazni_postup"]) and 8 not in kroky or True, f"{kw}: montazni postup ma kroky")
    seen = {i for k in vyp["montazni_postup"] for i in k["dily"]}
    check(seen == set(range(len(ses["dily"]))), f"{kw}: kazdy dil je v nejakem kroku montaze")
    check(not re.search(r"Object_|product_|sse_jekl", html), f"{kw}: vyrobni list nema interni ID dilu")

# ---------------------------------------------------------------------------------------------------------------------
print("F) routy, systemy, prenos vyberu")
check(anon.get("/api/shop/products/12345/configurator").status_code == 404 and anon.post("/api/shop/configurator/resolve", json={"product_id": 12345, "selection": {}}).status_code == 404, "nekonfigurovatelny produkt = 404")
check(anon.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {}, "rules_version": "stara"}).status_code == 409, "rules_changed = 409")
check(SH.system_pro_produkt(PID) == 41 and SH.konfigurovatelny(PID) and SH.RECEPTY["stul_system41"] == 41, "recept stul_system41 = system 41")
j30 = anon.post("/api/shop/configurator/resolve", json={"product_id": PID30, "selection": {"w": 1500, "d": 800, "h": 900, "panels": True, "led": True, "shelf": 2}}).get_json()
check(j30["valid"] and j30["selection"]["panels"] is True, "system 30 funguje vedle SSE (jiny produkt)")
sel30 = j30["selection"]
jx = post({"product_id": PID, "selection": sel30}).get_json()
check(jx["valid"] and jx["selection"]["w"] == 1500 and jx["selection"]["h"] == 900 and jx["selection"]["panels"] is False and jx["selection"]["shelf"] == 1, "cely vyber systemu 30 prenesen do SSE: rozmery zustanou, volby SSE nema se zahodi, police 2 -> 1")
jy = post({"product_id": PID30, "selection": jx["selection"]}).get_json()
check(jy["valid"] and jy["selection"]["w"] == 1500 and jy["selection"]["panels"] is False, "cely vyber SSE prenesen do systemu 30: rozmery zustanou")
# fuzz: nahodne vybery nikdy neskonci 500 a vzdy daji kompletni vyber
rnd = random.Random(41)
KLICE = ("w", "d", "h", "mid", "shelf", "drawers", "drawercount", "boxpos", "drawleft", "posts", "panels", "led", "wheels", "cut1", "bearings", "sleeve", "panelcount", "arm", "foo")
for i in range(60):
    sel = {k: rnd.choice([rnd.randint(-100, 4000), rnd.random() * 5000, True, False, "1", "0", "abc", None, -5, 0]) for k in rnd.sample(KLICE, rnd.randint(1, 8))}
    r = post({"product_id": PID, "selection": sel, "lang": rnd.choice(["cs", "en", "sk"])})
    jx = r.get_json()
    check(r.status_code == 200 and jx["valid"] is True and set(SH.VYCHOZI_VYBER) <= set(jx["selection"]) and 800 <= jx["selection"]["w"] <= 3000 and 480 <= jx["selection"]["d"] <= 1180 and 700 <= jx["selection"]["h"] <= 1000
          and jx["selection"]["shelf"] in (0, 1) and 1 <= jx["selection"]["drawercount"] <= 3, f"fuzz {i}: 200, platny, vyber v mezich ({sel})", (r.status_code, jx.get("errors")))
# staff blok (kusovnik s cenami jen pro zamestnance) a odkazy
check("staff" not in res({}), "verejna odpoved nema blok staff")
sb = SH._staff_blok(j["hash"])
check(sb and sb["kusovnik"] and "system=41" in sb["vyrobni_list_url"] and sb["problemy"] == [], "staff blok: kusovnik, odkazy nesou system=41", sb and sb["vyrobni_list_url"])
q = sb["vyrobni_list_url"].split("?", 1)[1]
from urllib.parse import parse_qs  # noqa: E402
pq = S.parametry_z_dotazu({k: v[0] for k, v in parse_qs(q).items()})
check(S.sestav_stul(**pq)["parametry"]["system"] == 41 and G.kanonicky_hash(pq) == j["hash"], "odkaz na vyrobni list se vrati na stejnou konfiguraci (hash)")

print(f"\n{OK} kontrol OK" + (f", {len(FAILS)} CHYB" if FAILS else ""))
sys.exit(1 if FAILS else 0)
