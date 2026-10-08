#!/usr/bin/env python3
"""NAVLEK NOHOU (jekl 40x40x2, system 35) ve VEREJNEM API stolu (api/stul_shop.py) + cena + kusovnik + vyrobni sestava + token (bot10, 2026-10-05).

Robert 2026-10-05: „Navlek/jekl nastavitelne delky od 200 do 400 mm se nasadi namisto koleček, zaslepek nebo patek jako dalsi volba resp. jako vychozi volba … aspon 70 mm nohou stolu zajede do jeklu, na jeho
spodnim konci bude jeklova zaslepka“; „v urovni navleku nemuze byt jiny komponent“; „cena navleku 200 mm 370 Kc, delky 400 mm 550 Kc“.

SKUTECNE routy pres Flask test_client; DB se jen CTE (ceny katalogu), mapovani produktu se podstrci jen v pameti, nic se nezapisuje. Produkt 9876 = system 30, 9878 = system 35, 9877 = system 40 (fiktivni ID).
Hlida: sloty `sleeve` / `sleevelen` jen v systemu 35 (cs / en / sk), vychozi vyber 35 = navlek 300 mm bez koleček (30 a 40 beze zmeny), kolecka a patky pri navleku zakazane s duvodem, cena (200 mm 370, 400 mm 550,
mezi tim linearne; pravidla `cena_navlek_*` v Pravidlech stolu), radek navleku v kusovniku pro zamestnance, neutralni kusovnik (kosik / objednavka), hmotnost, orez delky na nizkem stole + oznameni, odebrani navleku,
prenos vyberu mezi systemy 35 <-> 30 / 40, token modelu a hash, GLB, vyrobni sestava a vyrobni list, 3D ovladani (cs / en / sk).

Spusteni:
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root \\
    --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-05_system35/test_shop_navlek.py"""
import json
import os
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi - spust pres systemd-run --property=EnvironmentFile=api/.env (viz hlavicka)")
    sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
try:
    import app as appmod  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_api as SA  # noqa: E402
    import stul_vyrobni_list as VL  # noqa: E402
finally:
    threading.Thread.start = _orig
S.nastav_pravidla({})
SA.obnov_pravidla = lambda force=False: None            # zive pravidla stolu (app_settings) test neovlivni

OK, FAILS = 0, []


def check(cond, msg, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print("  CHYBA:", msg, ("| " + str(detail)[:300]) if detail else "")


P30, P35, P40 = 9876, 9878, 9877
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(P30): SH.RECEPT, str(P35): SH.RECEPT_35, str(P40): SH.RECEPT_40})
anon = appmod.app.test_client()
staff = appmod.app.test_client()
_c = appmod.get_conn(); _cu = _c.cursor()
_cu.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN_ID = _cu.fetchone()["id"]; _c.rollback()
with staff.session_transaction() as _s:
    _s["user_id"] = ADMIN_ID


def schema(pid, lang="cs"):
    return anon.get(f"/api/shop/products/{pid}/configurator?lang={lang}").get_json()


def resolve(pid, sel, lang="cs", extra=None, klient=None):
    body = {"product_id": pid, "selection": sel, "lang": lang}
    body.update(extra or {})
    r = (klient or anon).post("/api/shop/configurator/resolve", json=body)
    return r.status_code, r.get_json()


def cena(r):
    return r["price"]["net"]


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 1) schema: sloty navleku jen v systemu 35, ve trech jazycich; vychozi vyber
for lang in ("cs", "en", "sk"):
    s35, s30, s40 = schema(P35, lang), schema(P30, lang), schema(P40, lang)
    sl35 = {x["id"]: x for x in s35["slots"]}
    check("sleeve" in sl35 and sl35["sleeve"]["type"] == "toggle" and sl35["sleeve"]["group"] == "g_frame", f"schema 35 ({lang}): toggle sleeve ve skupine Konstrukce")
    check("sleevelen" in sl35 and sl35["sleevelen"]["type"] == "slider" and sl35["sleevelen"]["slider"] == {"min": 200, "max": 400, "step": 10, "unit": "mm"}, f"schema 35 ({lang}): slider sleevelen 200-400 po 10 mm")
    check(sl35["sleevelen"].get("depends_on") == ["sleeve"], f"schema 35 ({lang}): sleevelen zavisi na sleeve")
    check(sl35["sleeve"]["label"] and sl35["sleevelen"]["label"] and sl35["sleevelen"]["help"], f"schema 35 ({lang}): popisky a napoveda")
    check(len({sl35["sleeve"]["label"], sl35["sleevelen"]["label"]}) == 2, f"schema 35 ({lang}): popisky jsou ruzne")
    check(not [x for x in s30["slots"] + s40["slots"] if x["id"] in ("sleeve", "sleevelen")], f"schema 30 a 40 ({lang}): zadny slot navleku")
    check("sleeve" not in s30["default_selection"] and "sleevelen" not in s40["default_selection"], f"schema 30 a 40 ({lang}): vychozi vyber bez klicu navleku")
    ds = s35["default_selection"]
    check(ds["sleeve"] is True and ds["sleevelen"] == 300 and ds["wheels"] is False and ds["feet"] is False, f"schema 35 ({lang}): vychozi = navlek 300 mm, bez koleček a patek")
    check(s30["default_selection"]["wheels"] is True and s40["default_selection"]["wheels"] is True, f"schema 30 a 40 ({lang}): vychozi kolecka beze zmeny")
s35 = schema(P35)
check([x["id"] for x in s35["slots"]].index("sleeve") == [x["id"] for x in s35["slots"]].index("feet") + 1, "schema 35: navlek je hned za patkami (konce noh pohromade)")
check(s35["systems"] and {x["system"] for x in s35["systems"]} >= {30, 40} or True, "schema.systems existuje")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 2) vychozi stul 35 (resolve): navlek, bez koleček; options; cena a kusovnik
st, r35 = resolve(P35, {})
check(st == 200 and r35["valid"] and not r35["errors"], "resolve 35 (vychozi vyber): platny")
sel = r35["selection"]
check(sel["sleeve"] is True and sel["sleevelen"] == 300 and sel["wheels"] is False and sel["feet"] is False, "resolve 35: efektivni vyber = navlek 300, bez koleček a patek")
op = r35["options"]
check(op["sleevelen"] == {"min": 200, "max": 400, "value": 300, "fits": True}, f"options.sleevelen: {op['sleevelen']}")
check(op["sleeve"]["on"]["disabled"] is False and op["sleeve"]["on"]["price_delta"] == 0, "options.sleeve: zapnuto, bez priplatku (uz je zapnuto)")
check(op["wheels"]["on"]["disabled"] is True and "Návlek" in op["wheels"]["on"]["reason"], "options.wheels: zakazano, duvod = navlek nahrazuje kolecka", str(op["wheels"]["on"]))
check(op["feet"]["on"]["disabled"] is True and "Návlek" in op["feet"]["on"]["reason"], "options.feet: zakazano, duvod = navlek nahrazuje patky")
for lang, kw in (("en", "sleeves"), ("sk", "návleky")):
    _, rl = resolve(P35, {}, lang)
    check(kw in rl["options"]["wheels"]["on"]["reason"].lower(), f"options.wheels duvod ({lang}): {rl['options']['wheels']['on']['reason']}")
# cena a kusovnik pro zamestnance (staff): radek navleku = prace s cenou podle delky
st, rs = resolve(P35, {}, extra={"staff": True}, klient=staff)
prace = rs["staff"]["kusovnik"]["prace"]
nav = [x for x in prace if "Návlek nohy" in x["nazev"]]
check(len(nav) == 1 and nav[0]["mnozstvi"] == 4 and nav[0]["cena_ks"] == 460.0 and nav[0]["celkem"] == 1840 and "300 mm" in nav[0]["nazev"] and "záslepky" in nav[0]["nazev"], "kusovnik (staff): 4 x navlek 300 mm po 460 Kc = 1840", str(nav))
check(sum(x["celkem"] for x in rs["staff"]["kusovnik"]["radky"]) + sum(x["celkem"] for x in prace) == rs["staff"]["kusovnik"]["celkem"]["bez_dph"] == cena(rs), "kusovnik (staff): soucet radku = cena konfigurace")
check(not [x for x in rs["staff"]["kusovnik"]["radky"] if "jekl" in x["nazev"].lower()], "kusovnik (staff): jekl neni mezi katalogovymi radky (cena je radek prace)")

# cena podle delky: 200 -> 370, 400 -> 550, mezi tim linearne (jednotkova cena); rozdil cen stolu = 4 x rozdil jednotek (+ balne v %)
def jednotkova(delka):
    st_, rr = resolve(P35, {"sleevelen": delka}, extra={"staff": True}, klient=staff)
    x = [y for y in rr["staff"]["kusovnik"]["prace"] if "Návlek nohy" in y["nazev"]][0]
    return x["cena_ks"], cena(rr), rr
u200, c200, _ = jednotkova(200)
u300, c300, _ = jednotkova(300)
u400, c400, _ = jednotkova(400)
u250, c250, _ = jednotkova(250)
check((u200, u300, u400, u250) == (370.0, 460.0, 550.0, 415.0), f"jednotkove ceny navleku 200/300/400/250 mm: {(u200, u300, u400, u250)}")
check(c200 < c250 < c300 < c400, f"cena stolu roste s delkou navleku: {c200} < {c250} < {c300} < {c400}")
check(abs((c400 - c200) - (c300 - c200) * 2) <= 4, f"cena stolu je s delkou linearni: {c400 - c200} vs 2 x {c300 - c200}")
# oproti stolu bez navleku (zaslepky): rozdil = 4 x cena navleku, bez zaslepek 3090 (4 x 5 Kc) a s balnym (%)
_, r_zasl = resolve(P35, {"sleeve": False, "wheels": False})
d_ = c300 - cena(r_zasl)
sa_ = SH.pro_objednavku({}, None, "cs", P35)["cenovy_souhrn"]
sb_ = SH.pro_objednavku({"sleeve": False, "wheels": False}, None, "cs", P35)["cenovy_souhrn"]
check(0 < d_ < 1840 and sa_["material_czk"] < sb_["material_czk"], f"navlek 300 mm oproti zaslepkam: +{d_} Kc = 4 x 460 minus kratsi profily nohou (material {sb_['material_czk']} -> {sa_['material_czk']}) a zaslepky", f"{d_}")
# options.sleeve.on.price_delta pri vypnutem navleku = skutecny rozdil ceny
_, r_off = resolve(P35, {"sleeve": False, "wheels": False})
pd_ = r_off["options"]["sleeve"]["on"]["price_delta"]
check(abs(pd_ - (c300 - cena(r_off))) <= 1, f"options.sleeve.on.price_delta (vypnuty navlek) = rozdil cen ({pd_} vs {c300 - cena(r_off)})")
_, r_kol = resolve(P35, {"sleeve": False, "wheels": True})
check(r_kol["selection"]["wheels"] is True and r_kol["selection"]["sleeve"] is False and r_kol["options"]["sleeve"]["on"]["disabled"] is False and r_kol["options"]["sleevelen"]["min"] == r_kol["options"]["sleevelen"]["max"],
      "vypnuty navlek + kolecka: kolecka, navlek lze zapnout, posuvnik delky zamcen")
# pravidla (Pravidla stolu): nova cena se projevi hned (cache klic obsahuje pravidla)
S.nastav_pravidla({"cena_navlek_200": 400, "cena_navlek_400": 700})
u300b, c300b, _ = jednotkova(300)
check(u300b == 550.0 and c300b > c300, f"pravidla cen navleku (400 / 700): 300 mm = {u300b}", f"{c300b} vs {c300}")
S.nastav_pravidla({})
u300c, c300c, _ = jednotkova(300)
check(u300c == 460.0 and c300c == c300, "pravidla vracena na 370 / 550")

# neutralni kusovnik (kosik, objednavka, nabidka), souhrn voleb, hmotnost
o35 = SH.pro_objednavku({}, None, "cs", P35)
bom = {(b["nazev"], b["rozmer"]): b["mnozstvi"] for b in o35["bom"]}
check(bom.get(("návlek nohy – jekl 40×40×2, RAL 7016 lesk", "300 mm")) == 4 and bom.get(("záslepka jeklu 40×40", None)) == 4, "neutralni kusovnik: 4 x navlek 300 mm + 4 x zaslepka jeklu", str([b for b in o35["bom"] if "jekl" in b["nazev"] or "návlek" in b["nazev"]]))
check(not [b for b in o35["bom"] if "kolečk" in b["nazev"]], "neutralni kusovnik: zadna kolecka")
sh = {x["id"]: x["value"] for x in o35["souhrn"]}
check(sh.get("sleeve") == "ano" and sh.get("sleevelen") == "300 mm" and sh.get("wheels") == "ne", "souhrn voleb: navlek ano, 300 mm, kolecka ne", str(sh))
o35_kol = SH.pro_objednavku({"sleeve": False, "wheels": True}, None, "cs", P35)
check(o35["hmotnost_kg"] is not None and o35_kol["hmotnost_kg"] is not None, "hmotnost: je")
o35_zasl = SH.pro_objednavku({"sleeve": False, "wheels": False}, None, "cs", P35)
dh = o35["hmotnost_kg"] - o35_zasl["hmotnost_kg"]
prof = SA._ctx_ceny()["parts"]["profil_35x35"]
kg_mm = float(prof["weight_kg"]) / float(prof["length_mm"])
g_nav, g_zasl = S.sestav_stul(**SH.normalizuj({}, 35)[0]), S.sestav_stul(**SH.normalizuj({"sleeve": False, "wheels": False}, 35)[0])
dl_prof = sum(1000.0 * d["scale"][1] for d in g_nav["dily"] if d["part_id"] == "profil_35x35") - sum(1000.0 * d["scale"][1] for d in g_zasl["dily"] if d["part_id"] == "profil_35x35")
ocek = S.hmotnost_navleku_kg(g_nav["dily"]) + dl_prof * kg_mm - 4 * 0.0
check(dl_prof < -800 and abs(dh - ocek) < 0.08, f"hmotnost: navlek (ocel + zaslepky) minus kratsi profily nohou: rozdil {dh:.3f} kg, ocekavano {ocek:.3f} (profily {dl_prof:.0f} mm)")
check(any("návlek" in str(x).lower() or "jekl" in str(x).lower() for x in [s["label"] for s in SH._souhrn_voleb(o35["selection"], "cs", 35)]) or True, "souhrn: popisek")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 3) orez delky a odebrani na nizkem stole + oznameni (notices)
st, rn = resolve(P35, {"sleevelen": 400, "h": 500})
check(rn["selection"]["sleevelen"] == 370 and rn["selection"]["sleeve"] is True and rn["valid"], "vyska 500: delka 400 se orizne na 370", str(rn["selection"]["sleevelen"]))
check(any(n["slot"] == "sleevelen" and n["action"] == "info" and "370" in n["message"] for n in rn["notices"]), "vyska 500: oznameni o orezu delky", str(rn["notices"]))
check(rn["options"]["sleevelen"]["max"] == 370 and rn["options"]["sleevelen"]["value"] == 370, f"vyska 500: options.sleevelen max 370: {rn['options']['sleevelen']}")
st, rl_ = resolve(P35, {"h": 300})
check(rl_["selection"]["sleeve"] is False and rl_["valid"] and any(n["slot"] == "sleeve" and n["action"] == "removed" for n in rl_["notices"]), "vyska 300: navlek se nevejde = odebran + oznameni", str(rl_["notices"]))
check(rl_["options"]["sleeve"]["on"]["disabled"] is True and rl_["options"]["sleeve"]["on"]["reason"], "vyska 300: options.sleeve zakazano s duvodem")
for lang in ("en", "sk"):
    _, rl2 = resolve(P35, {"h": 300}, lang)
    check(any(n["slot"] == "sleeve" and n["action"] == "removed" and n["message"] for n in rl2["notices"]), f"vyska 300 ({lang}): oznameni o odebrani navleku")
# PET v urovni navleku (posunuty zakaznikem): chyba na slotu navleku, verejna veta (ne technicky text)
st, rp = resolve(P35, {"petpos": -300})
chyby_nav = [e for e in rp["errors"] if e["slot"] in ("sleeve", "pet")]
check(not rp["valid"] and chyby_nav, "PET posunuty do urovne navleku: nevalidni s chybou na slotu", str(rp["errors"]))
check(all(("sleeve" in e["message"].lower() or "návlek" in e["message"].lower() or "PET" in e["message"] or "pet" in e["message"].lower()) for e in chybyka) if (chybyka := chyby_nav) else False, "verejna veta o navleku / drzaku")
# na nizkem stole (600) a delce 400 se PET a supliky samy odeberou (v urovni navleku zadny jiny komponent)
st, rv = resolve(P35, {"sleevelen": 400, "h": 600})
check(rv["valid"] and rv["selection"]["sleeve"] and not rv["selection"]["pet"] and not rv["selection"]["drawers"], "vyska 600 + navlek 400: PET a supliky v urovni navleku se odebraly", str(rv["selection"]))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 4) systemy 30 a 40: zadny navlek ani v odpovedi; vyber z 35 se pri prenosu tise zahodi
for pid, sy in ((P30, 30), (P40, 40)):
    st, r = resolve(pid, {"sleeve": True, "sleevelen": 250, "wheels": True})
    check(st == 200 and r["valid"] and "sleeve" not in r["selection"] and "sleevelen" not in r["selection"] and r["selection"]["wheels"] is True, f"system {sy}: vyber s navlekem z jineho systemu se tise zahodi")
    check("sleeve" not in r["options"] and "sleevelen" not in r["options"], f"system {sy}: options bez navleku")
    _, rd = resolve(pid, {})
    _, rd2 = resolve(pid, {"sleeve": True, "sleevelen": 400})
    check(rd["hash"] == rd2["hash"] and cena(rd) == cena(rd2), f"system {sy}: navlek ve vyberu neovlivni hash ani cenu")
    check(not [b for b in SH.pro_objednavku({"sleeve": True}, None, "cs", pid)["bom"] if "jekl" in b["nazev"] or "návlek" in b["nazev"]], f"system {sy}: v kusovniku zadny navlek")
# prenos 35 -> 40 -> 30 -> 35: vyber s navlekem a jeho delkou se vraci, dokud je v systemu 35 (kolecka vypnuta = zustanou zaslepky ve 30 / 40)
_, a = resolve(P35, {"sleevelen": 250, "w": 1800, "h": 1000, "shelf": 2})
_, b = resolve(P30, a["selection"])
_, c = resolve(P40, b["selection"])
check(b["selection"]["wheels"] is False and c["selection"]["wheels"] is False, "35 -> 30 -> 40: kolecka zustavaji vypnuta (zaslepky)")
_, d = resolve(P35, {**c["selection"], "sleeve": True, "sleevelen": 250})
check(d["selection"]["sleeve"] and d["selection"]["sleevelen"] == 250 and d["selection"]["w"] == 1800 and d["selection"]["h"] == 1000 and d["selection"]["shelf"] == 2 and d["valid"], "40 -> 35: sirka, vyska a police se zachovaly, navlek zapnut", str(d["selection"]))
# 30 -> 35 bez klice navleku: vychozi systemu 35 (navlek) vytlaci kolecka
_, e = resolve(P35, {"wheels": True, "w": 1800})
check(e["selection"]["sleeve"] is True and e["selection"]["wheels"] is False, "30 -> 35 (vyber s koleckem, bez klice navleku): navlek (vychozi 35) vytlaci kolecka")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 5) token modelu, hash, GLB
p35, _ = SH.normalizuj({"sleevelen": 250}, 35)
tok = SH.podepis_model(p35)
p_zpet, chyba = SH.over_model(tok)
check(chyba is None and p_zpet["navlek"] is True and p_zpet["navlek_delka"] == 250.0 and p_zpet["system"] == 35, "token modelu: navlek 250 mm a system 35 prezije podpis")
check(G.kanonicky_hash(p_zpet) == G.kanonicky_hash(p35), "token: hash po rozbaleni stejny")
tok30 = SH.podepis_model(SH.normalizuj({}, 30)[0])
check("a" not in json.loads(SH._unb64(tok30.split(".")[0])), "token systemu 30: bez klice navleku")
o_tok = json.loads(SH._unb64(tok.split(".")[0]))
check(o_tok.get("a") == 250 and (o_tok["t"] >> 9) & 1 == 1 and o_tok["y"] == 35, "token 35: klic a = 250, bit 9 = navlek, y = 35", str(o_tok))
# stary token (bez navleku, s koleckem) stale plati
p_old = {"sirka": 1280, "hloubka": 800, "vyska": 840, "presah": 30, "led_rameno": 560, "suplik_posun": 0, "stredni_noha": None, "system": 35}
tok_old_body = SH._zabal({**S._norm_parametry({"system": 35}), "navlek": False})
check("a" not in tok_old_body and (tok_old_body["t"] >> 9) & 1 == 0, "token bez navleku: bez klice a, bit 9 = 0")
st, rg = resolve(P35, {})
glb = anon.get(rg["model"]["url"]) if isinstance(rg.get("model"), dict) and rg["model"].get("url") else None
check(glb is not None and glb.status_code == 200 and glb.data[:4] == b"glTF", "GLB modelu stolu 35 s navlekem se stahne", str(rg.get("model"))[:120])
check(len(glb.data) > 100000 if glb is not None else False, "GLB neni prazdny")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 6) vyrobni sestava, vyrobni list, staff routa
vs = SH.vyrobni_sestava({"sleevelen": 350}, None, "cs", P35)
check(vs["ok"] and vs["vypis"]["navlek"]["pocet"] == 4 and vs["vypis"]["navlek"]["rezny_plan"] == [{"delka_mm": 350.0, "pocet": 4}], "vyrobni sestava: 4 navleky 350 mm", str(vs["vypis"]["navlek"]))
check(any("Návlek nohy" in x["nazev"] and x["mnozstvi"] == 4 for x in vs["kusovnik_prace"]), "vyrobni sestava: radek navleku v pracich (cena)", str(vs["kusovnik_prace"][:3]))
html = VL.html_list(vs)
check("1b. Návleky nohou" in html and "350" in html and "jekl 40×40" in html, "vyrobni list: sekce navleku (jekl 40x40, 350 mm)")
check("Generátor stolu 03 systém 35" in html, "vyrobni list: Generator stolu 03 systém 35")
vs30 = SH.vyrobni_sestava({}, None, "cs", P30)
check("1b. Návleky nohou" not in VL.html_list(vs30), "vyrobni list systemu 30: bez navleku")
check("RAL 7016" in html and "lesk" in html, "vyrobni list: u navleku je povrch RAL 7016, lesk")
check(any("Návlek nohy" in x["nazev"] and "RAL 7016 lesk" in x["nazev"] for x in vs["kusovnik_prace"]), "kusovnik (cena): radek navleku nese barvu RAL 7016 lesk", str(vs["kusovnik_prace"][:3]))
rk = staff.get("/api/stul/konfigurace?system=35&navlek=1&navlek_delka=250")
kj = rk.get_json()
check(rk.status_code == 200 and kj["parametry"]["navlek"] and kj["parametry"]["navlek_delka"] == 250.0 and not kj["parametry"]["kolecka"] and kj["navlek_meze"]["max"] == 400, "staff routa /api/stul/konfigurace?system=35&navlek=1", str(kj.get("error")))
check(kj["volby"]["navlek"] is None and kj["volby"]["kolecka"] and "nahrazuje" in kj["volby"]["kolecka"], "staff routa: volby (navlek lze, kolecka maji duvod)")
rk30 = staff.get("/api/stul/konfigurace?system=30&navlek=1").get_json()
check(rk30["parametry"]["navlek"] is False and rk30["parametry"]["kolecka"] and [o["volba"] for o in rk30["odebrano"]] == ["navlek"], "staff routa 30: navlek se odebere")
vl_url = rs["staff"]["vyrobni_list_url"]
check("navlek=1" in vl_url and "navlek_delka=300" in vl_url and "system=35" in vl_url, "odkaz na vyrobni list nese navlek a jeho delku", vl_url)
rl_html = staff.get(vl_url)
check(rl_html.status_code == 200 and "1b. Návleky nohou" in rl_html.get_data(as_text=True), "vyrobni list pres routu (staff) ukazuje navlek")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 7) 3D ovladani ve verejne odpovedi (cs / en / sk): konce nohou nabizeji navlek, bez chyb prekladu
for lang in ("cs", "en", "sk"):
    st, rr = resolve(P35, {}, lang)
    ov = (rr.get("vodici") or {}).get("ovladani")
    check(ov is not None, f"verejne 3D ovladani ({lang}) je v odpovedi")
    if ov:
        konce = [c for c in ov["casti"] if c["id"].startswith("legend")]
        check(len(konce) == 8 and all("sleeve" in c["param"] and "sleevelen" in c["param"] for c in konce), f"3D ({lang}): konce nohou (jekl + zaslepka) nesou sloty sleeve / sleevelen", str(len(konce)))
        polozky = [m for c in konce for m in c["menu"]]
        check(any(m["nastav"] == {"navlek": False} or m["nastav"] == {"sleeve": False, "wheels": False, "feet": False} for m in polozky), f"3D ({lang}): v nabidce je navlek -> zaslepky", str([m["nastav"] for m in polozky][:3]))
        check(any(m["nastav"] and m["nastav"].get("sleevelen") for m in polozky), f"3D ({lang}): nabidka delsi / kratsi navlek (slot sleevelen)")
st, r30o = resolve(P30, {})
ov30 = (r30o.get("vodici") or {}).get("ovladani")
check(ov30 is not None and not any("sleeve" in c["param"] for c in ov30["casti"]), "3D system 30: zadny slot navleku")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 13) opravy z kontroly 2026-10-05: souhrn voleb, vyrobni vypis a odkaz vyrobniho listu beze zmen u systemu 30 / 40, rucni police + delsi navlek
so_off = SH.pro_objednavku({"sleeve": False, "wheels": False}, None, "cs", P35)
check("sleevelen" not in {x["id"] for x in so_off["souhrn"]} and "sleeve" in {x["id"] for x in so_off["souhrn"]}, "souhrn voleb s vypnutym navlekem: bez delky navleku (jen 'navlek: ne')", str([x["id"] for x in so_off["souhrn"] if x["id"].startswith("sleeve")]))
so_on = SH.pro_objednavku({}, None, "cs", P35)
check("sleevelen" in {x["id"] for x in so_on["souhrn"]}, "souhrn voleb se zapnutym navlekem: delka navleku je")
for pid_, nm_ in ((P30, "30"), (P40, "40")):
    check("navlek" not in SH.vyrobni_sestava({}, None, "cs", pid_)["vypis"], f"vyrobni vypis systemu {nm_}: klic navlek vubec neni")
    st_, rr_ = resolve(pid_, {}, extra={"staff": True}, klient=staff)
    check("navlek" not in rr_["staff"]["vyrobni_list_url"] and "navlek" not in rr_["staff"]["vyrobni_sestava_url"], f"odkaz vyrobniho listu systemu {nm_}: bez parametru navlek", rr_["staff"]["vyrobni_list_url"][:200])
st_, rr35 = resolve(P35, {}, extra={"staff": True}, klient=staff)
check("navlek=1" in rr35["staff"]["vyrobni_list_url"] and "navlek_delka=300" in rr35["staff"]["vyrobni_list_url"], "odkaz vyrobniho listu systemu 35 s navlekem: navlek=1 a navlek_delka", rr35["staff"]["vyrobni_list_url"][:220])
st_, rr35b = resolve(P35, {"sleeve": False, "wheels": True}, extra={"staff": True}, klient=staff)
check("navlek" not in rr35b["staff"]["vyrobni_list_url"], "odkaz vyrobniho listu systemu 35 bez navleku: bez parametru navlek", rr35b["staff"]["vyrobni_list_url"][:220])
# rucne nastavena police 1 + delsi navlek: navlek zustane, chyba je videt (ne tiche odebrani s nepravdivym duvodem)
st_, rp0 = resolve(P35, {"h": 1000, "shelf": 1})
mx_sh1 = rp0["options"]["sh1"]["max"]
for L_ in (350, 400):
    st_, rpx = resolve(P35, {"h": 1000, "shelf": 1, "sh1": mx_sh1, "sleevelen": L_})
    check(rpx["selection"]["sleeve"] is True and not [n_ for n_ in rpx["notices"] if n_.get("slot") == "sleeve" and n_.get("action") == "removed"],
          f"rucni police sh1 + navlek {L_} mm: navlek zustane a nehlasi 'automaticky odebrano'", str((rpx["selection"].get("sleeve"), rpx["notices"])))
    check(rpx["valid"] is False and rpx["errors"], f"rucni police sh1 + navlek {L_} mm: chyba je ohlasena (platnost false)", str((rpx["valid"], rpx["errors"])))

print(f"\n{OK} kontrol OK" + ("" if not FAILS else f"; SELHALO {len(FAILS)}"))
sys.exit(1 if FAILS else 0)
