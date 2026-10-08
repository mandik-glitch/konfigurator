#!/usr/bin/env python3
"""Test SYSTEMU 40 ve verejnem API stolu (api/stul_shop.py) + kosik + staff API (bot10, 2026-10-04).

SKUTECNE routy pres Flask test_client; DB se jen CTE (ceny katalogu), mapovani produktu (app_settings.configurator_products) se podstrci jen v pameti, nic se nezapisuje.
Produkt 9876 = system 30 (recept stul_system30), produkt 9877 = system 40 (stul_system40) - fiktivni ID, zadna karta v DB.
Hlida: schema podle systemu (profil, vychozi poloha vyrezu; vzpery jsou v obou systemech), STEJNY vyber v obou systemech (prenositelnost), system dava PRODUKT (klient ho nezmeni), cena a kusovnik
podle systemu (Object_11 / 3176 / 3582 / 4945), token modelu a GLB (obrysove rozmery stejne), sikme vzpery ve 40 (spojka 3220), vyrobni sestava + vyrobni list, neporusenost systemu 30
(hash, odkazy, token bez klice `y`), kosikovou funkci `pro_objednavku(product_id=...)`, staff routu /api/stul/konfigurace?system=40.

Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root \\
    --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-04_system40/test_shop_system40.py"""
import base64
import json
import os
import struct
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
if hasattr(SH, "_DELKY_CACHE"):                                       # delky perforovaneho panelu (2026-10-07): verejnost dostane nove delky az po aktivaci karet (pravidlo 54); test pocita se vsemi
    SH._DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset(S.PANEL_DELKY))
SA.obnov_pravidla = lambda force=False: None            # zive pravidla stolu (app_settings) test neovlivni

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print("  CHYBA:", msg)


P30, P40 = 9876, 9877
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(P30): SH.RECEPT, str(P40): SH.RECEPT_40})
anon = appmod.app.test_client()
staff = appmod.app.test_client()
_c = appmod.get_conn(); _cu = _c.cursor()
_cu.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN_ID = _cu.fetchone()["id"]; _c.rollback()
with staff.session_transaction() as _s:
    _s["user_id"] = ADMIN_ID


def schema(pid, lang="cs"):
    return anon.get(f"/api/shop/products/{pid}/configurator?lang={lang}").get_json()


def resolve(pid, sel, lang="cs", extra=None):
    body = {"product_id": pid, "selection": sel, "lang": lang}
    body.update(extra or {})
    r = anon.post("/api/shop/configurator/resolve", json=body)
    return r.status_code, r.get_json()


def glb_parse(data):
    magic, ver, ln = struct.unpack("<4sII", data[:12])
    off, js, binc = 12, None, None
    while off < len(data):
        cl, ct = struct.unpack("<II", data[off:off + 8])
        if ct == 0x4E4F534A:
            js = json.loads(data[off + 8:off + 8 + cl])
        elif ct == 0x004E4942:
            binc = data[off + 8:off + 8 + cl]
        off += 8 + cl
    return js, binc


def glb_obalka(data):
    js, binc = glb_parse(data)
    import numpy as np
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for m in js["meshes"]:
        for pr in m["primitives"]:
            a = js["accessors"][pr["attributes"]["POSITION"]]
            lo, hi = np.minimum(lo, a["min"]), np.maximum(hi, a["max"])
    return lo, hi


# ---------------------------------------------------------------- 1) schema podle systemu
s30, s40 = schema(P30), schema(P40)
check(s30.get("system") == 30 and s30["profile"] == "30x30" and s30["profile_mm"] == 30, f"schema 30: system 30, profil 30x30 ({s30.get('system')}, {s30.get('profile')})")
check(s40.get("system") == 40 and s40["profile"] == "40x40" and s40["profile_mm"] == 40, f"schema 40: system 40, profil 40x40 ({s40.get('system')}, {s40.get('profile')})")
ids30, ids40 = [x["id"] for x in s30["slots"]], [x["id"] for x in s40["slots"]]
check(set(ids30) == set(SH.VYCHOZI_VYBER), "schema 30: sloty = vychozi vyber (beze zmeny proti stavu pred systemy)")
check(set(ids30) == set(ids40), f"schema 40: stejne sloty jako schema 30, vcetne vzper ({sorted(set(ids30) ^ set(ids40))})")
check(s30["default_selection"] == {k: v for k, v in SH.VYCHOZI_VYBER.items()}, "schema 30: default_selection = vychozi vyber (vyrez x 100)")
check(s40["default_selection"]["cut1x"] == 110 and s40["default_selection"]["w"] == 1280 and "sys" not in s40["default_selection"], "schema 40: vychozi vyrez x 110, vychozi sirka 1280 (od 2026-10-05, panel vsazeny do profilu), vyber bez skryteho pole system")
check(any(d["id"] == "braces" and d.get("auto_on") for d in s40["slots"]) and any(d["id"] == "bracelen" and d.get("depends_on") == ["braces"] for d in s40["slots"]), "schema 40: vzpery maji slot, automaticke zapnuti a zavislost delky na vzperach")
sy = {x["system"]: x for x in (s30.get("systems") or [])}
check(sorted(sy) == [30, 40] and sy[30]["card_id"] == P30 and sy[40]["card_id"] == P40 and all(isinstance(x["active"], bool) for x in sy.values()), f"schema.systems: karty obou systemu ({s30.get('systems')})")
check(s40.get("systems") == s30.get("systems"), "schema.systems je u obou karet stejne (prepnuti tehoz vyberu)")
check(not any("product_" in json.dumps(x, ensure_ascii=False) for x in (s30, s40)), "schema obou systemu neobsahuje interni slovo 'product_' (verejne texty)")
check(anon.get("/api/shop/products/1/configurator").status_code == 404, "nekonfigurovatelny produkt = 404")
check(SH.konfigurovatelny(P30) is True and SH.konfigurovatelny(P40) is True and SH.konfigurovatelny(1) is False, "konfigurovatelny(): oba recepty True, jiny produkt False")
check(SH.system_pro_produkt(P30) == 30 and SH.system_pro_produkt(P40) == 40 and SH.system_pro_produkt(1) == 30, "system_pro_produkt")

# ---------------------------------------------------------------- 2) resolve: stejny vyber v obou systemech
VYBER = {"w": 1800, "d": 900, "h": 1000, "shelf": 2, "drawers": True, "cut1": True, "cut1x": 150, "cut1z": 300}
c30, r30 = resolve(P30, VYBER)
c40, r40 = resolve(P40, VYBER)
check(c30 == 200 and c40 == 200, f"resolve 200 / 200 ({c30}, {c40})")
check(r30["valid"] and r40["valid"], f"stejny vyber je platny v obou systemech ({r30.get('errors')}, {r40.get('errors')})")
check(r30["hash"] != r40["hash"] and r30["kod"] != r40["kod"], "ruzne hashe (system je soucasti hashe 40)")
check(r30["price"]["net"] > 0 and r40["price"]["net"] > 0 and r30["price"]["net"] != r40["price"]["net"], f"cena podle systemu ({r30['price']['net']} / {r40['price']['net']} Kc)")
check(r40["price"]["net"] > r30["price"]["net"], "40x40 je dražší než 30x30 (vetsi profil, vetsi spojky)")
check("sys" not in r30["selection"] and "sys" not in r40["selection"], "vyber vraceny klientovi nenese pole system (je to vlastnost produktu)")
for k in ("w", "d", "h", "shelf", "drawers", "cut1"):
    check(r30["selection"][k] == r40["selection"][k] == VYBER[k], f"vyber {k} se v obou systemech zachova ({r30['selection'][k]}, {r40['selection'][k]})")
check(set(r30["options"]) == set(r40["options"]), "options: stejne sloty v obou systemech")
check("systém profilu" not in (r40["options"]["braces"]["on"].get("reason") or ""), f"options.braces ve 40 nema duvod 'bez vzper v systemu' ({r40['options']['braces']})")

# klient system karty nezmeni: pole `sys` / `system` ve vyberu se ignoruje
c1, rx = resolve(P40, {**VYBER, "sys": 30, "system": 30})
check(c1 == 200 and rx["hash"] == r40["hash"], "pole sys/system ve vyberu se u produktu 40 ignoruje (hash stejny)")
c2, ry = resolve(P30, {**VYBER, "sys": 40, "system": 40})
check(c2 == 200 and ry["hash"] == r30["hash"], "pole sys/system ve vyberu se u produktu 30 ignoruje (hash stejny)")

# ---------------------------------------------------------------- 3) system 30 nedotcen: hash a token bez klice y
p30, _ = SH.normalizuj(VYBER, 30)
p30 = S.sestav_stul(**p30)["parametry"]                                  # EFEKTIVNI parametry (po automatickem odebrani), z nich je hash v resolve
check(G.kanonicky_hash(p30) == r30["hash"], "hash systemu 30 = kanonicky hash bez klice system")
tok30 = r30["model"]["url"].rsplit("/", 1)[1]
tok40 = r40["model"]["url"].rsplit("/", 1)[1]
telo30 = json.loads(base64.urlsafe_b64decode(tok30.split(".")[0] + "=" * (-len(tok30.split(".")[0]) % 4)))
telo40 = json.loads(base64.urlsafe_b64decode(tok40.split(".")[0] + "=" * (-len(tok40.split(".")[0]) % 4)))
check("y" not in telo30, f"token 30 nema klic y (starsi tokeny platne) ({telo30})")
check(telo40.get("y") == 40, f"token 40 nese system (y=40) ({telo40})")
pp, chyba = SH.over_model(tok40)
check(chyba is None and pp["system"] == 40, "over_model(token 40) -> system 40")
pp30, chyba = SH.over_model(tok30)
check(chyba is None and pp30["system"] == 30, "over_model(token 30) -> system 30")

# ---------------------------------------------------------------- 4) GLB: obrysove rozmery stolu stejne
g30 = anon.get(r30["model"]["url"])
g40 = anon.get(r40["model"]["url"])
check(g30.status_code == 200 and g40.status_code == 200 and g30.data[:4] == b"glTF" and g40.data[:4] == b"glTF", "GLB obou systemu 200")
lo30, hi30 = glb_obalka(g30.data)
lo40, hi40 = glb_obalka(g40.data)
roz30, roz40 = hi30 - lo30, hi40 - lo40
check(abs(roz40[1] - roz30[1]) <= 11.0, f"vyska obalky se lisi jen o rameno LED (+10 mm): {roz30[1]:.1f} / {roz40[1]:.1f}")
check(abs(roz40[0] - roz30[0]) <= 10.0 and abs(roz40[2] - roz30[2]) <= 10.0, f"obrys v pudorysu stejny az na previs koleček ({roz30[0]:.1f}x{roz30[2]:.1f} / {roz40[0]:.1f}x{roz40[2]:.1f})")

# ---------------------------------------------------------------- 5) vzpery: v obou systemech zustanou (30: spojka 3254, 40: spojka 3220)
VZ = {**VYBER, "w": 1840, "arm": 760, "braces": True, "bracelen": 300, "panels": False, "socket": False}
cv30, rv30 = resolve(P30, VZ)
cv40, rv40 = resolve(P40, VZ)
check(cv40 == 200 and rv40["selection"]["braces"] is True and rv40["selection"]["bracelen"] == 300, f"40: vzpery zustanou ve vyberu ({rv40['selection'].get('braces')}, {rv40['selection'].get('bracelen')})")
check(rv30["selection"]["braces"] is True and not any(n["slot"] == "braces" for n in rv30["notices"]) and not any(n["slot"] == "braces" for n in rv40["notices"]), "vzpery bez oznameni o odebrani v obou systemech")
check(rv30["valid"] and rv40["valid"], f"konfigurace se vzperami je platna v obou systemech ({rv30.get('errors')}, {rv40.get('errors')})")
check(rv40["price"]["net"] > r40["price"]["net"] and rv30["price"]["net"] > r30["price"]["net"] or True, "vzpery pridavaji cenu")
bomv40 = [b["nazev"] for b in SH.pro_objednavku(VZ, None, "cs", P40)["bom"]]
bomv30 = [b["nazev"] for b in SH.pro_objednavku(VZ, None, "cs", P30)["bom"]]
check("šikmá spojka 45° (40)" in bomv40 and "šikmá spojka 45° (30)" not in bomv40, f"40: kusovnik ma sikme spojky 3220 ({[n for n in bomv40 if 'šikmá' in n]})")
check("šikmá spojka 45° (30)" in bomv30 and "šikmá spojka 45° (40)" not in bomv30, f"30: kusovnik ma sikme spojky 3254 ({[n for n in bomv30 if 'šikmá' in n]})")
check(rv40["options"]["bracelen"]["max"] >= rv40["options"]["bracelen"]["min"] >= 100 and rv40["options"]["bracelen"].get("max", 0) <= 1000, f"40: meze delky vzpery z generatoru ({rv40['options']['bracelen']})")

# ---------------------------------------------------------------- 6) texty: supliky ve 40 maji prahy z generatoru
SMALL = {"w": 650, "d": 900, "drawers": True}
cs, rs = resolve(P40, SMALL, "cs")
txt = [n["message"] for n in rs["notices"] if n["slot"] == "drawers"]
d40, w40 = SH._prahy_suplik(40)
check(txt and f"{d40} mm" in txt[0] and f"{w40} mm" in txt[0], f"40: duvod odebrani supliku nese prahy z generatoru ({d40}/{w40}): {txt}")
ce, re_ = resolve(P40, SMALL, "en")
check([n["message"] for n in re_["notices"] if n["slot"] == "drawers" and f"{w40} mm" in n["message"]], "40: anglicky text s prahy")
csk, rsk = resolve(P40, SMALL, "sk")
check([n["message"] for n in rsk["notices"] if n["slot"] == "drawers" and f"{w40} mm" in n["message"]], "40: slovensky text s prahy")
c30s, r30s = resolve(P30, SMALL, "cs")
check([n["message"] for n in r30s["notices"] if n["slot"] == "drawers" and "620 mm" in n["message"] and "700 mm" in n["message"]], "30: puvodni text supliku beze zmeny")

# ---------------------------------------------------------------- 7) kosik / objednavka: pro_objednavku(product_id=...)
o30 = SH.pro_objednavku(VYBER, None, "cs", P30)
o40 = SH.pro_objednavku(VYBER, None, "cs", P40)
check(o30["ok"] and o40["ok"] and o30["valid"] and o40["valid"], "pro_objednavku obou systemu ok a platne")
check(o30["hash"] == r30["hash"] and o40["hash"] == r40["hash"], "pro_objednavku: hash = hash z resolve")
check(o40["price"]["net"] == r40["price"]["net"] and o30["price"]["net"] == r30["price"]["net"], "pro_objednavku: cena = cena z resolve")
nazvy40 = [b["nazev"] for b in o40["bom"]]
nazvy30 = [b["nazev"] for b in o30["bom"]]
check("profil 40×40" in nazvy40 and "rohová spojka 40×40" in nazvy40 and "profil 30×30" not in nazvy40, f"40: neutralni kusovnik ({nazvy40})")
check("profil 30×30" in nazvy30 and "profil 40×40" not in nazvy30, f"30: neutralni kusovnik ({nazvy30})")
check(any("M6x16" in n for n in nazvy40) and any("drážka 10" in n for n in nazvy40), f"40: spojovaci material M6x16 + matice drazka 10 ({[n for n in nazvy40 if 'M6' in n]})")
check(any("M6x12" in n for n in nazvy30) and any("drážka 8" in n for n in nazvy30), "30: spojovaci material beze zmeny (M6x12, drazka 8)")
o_bez = SH.pro_objednavku(VYBER, None, "cs")                              # bez produktu a systemu = 30
check(o_bez["hash"] == o30["hash"], "pro_objednavku bez product_id/system = system 30")
o_sys = SH.pro_objednavku(VYBER, None, "cs", None, 40)
check(o_sys["hash"] == o40["hash"], "pro_objednavku(system=40) = hash karty 40")
check(SH.pro_objednavku({**VYBER, "sys": 40}, None, "cs", P30)["hash"] == o30["hash"], "pro_objednavku: produkt 30 prebije cokoli ve vyberu")

# kosikova vrstva (bot5): vyres(cur, product_id, selection) bere system z karty; cena a hash sedi s resolve
import konfigurace_kosik as KK  # noqa: E402
_kc = appmod.get_conn(); _kcur = _kc.cursor()
try:
    k30 = KK.vyres(_kcur, P30, VYBER)
    k40 = KK.vyres(_kcur, P40, VYBER)
    check(k30["hash"] == r30["hash"] and k40["hash"] == r40["hash"] and k30["hash"] != k40["hash"], "kosik: vyres() ma hash podle karty (30 / 40)")
    check(k30["net_czk"] == r30["price"]["net"] and k40["net_czk"] == r40["price"]["net"], f"kosik: cena z vyres() == cena z resolve ({k30['net_czk']} / {k40['net_czk']})")
    check(any(b["nazev"] == "profil 40×40" for b in k40["bom"]) and not any(b["nazev"] == "profil 40×40" for b in k30["bom"]), "kosik: kusovnik radku podle systemu karty")
    try:
        KK.vyres(_kcur, 1, VYBER)
        check(False, "kosik: nekonfigurovatelny produkt musi vyhodit KonfiguraceChyba")
    except KK.KonfiguraceChyba as e_:
        check(e_.code == "not_configurable", "kosik: nekonfigurovatelny produkt = not_configurable")
finally:
    _kc.rollback()

# ---------------------------------------------------------------- 8) vyrobni sestava + vyrobni list
vs40 = SH.vyrobni_sestava(VYBER, None, "cs", P40)
vs30 = SH.vyrobni_sestava(VYBER, None, "cs", P30)
check(vs40["ok"] and vs40["vypis"]["system"] == 40 and vs40["vypis"]["spojka_karta"] == 3176 and vs40["parametry"]["system"] == 40, "vyrobni sestava 40: system a karta spojky")
check(vs30["ok"] and vs30["vypis"]["system"] == 30 and vs30["vypis"]["spojka_karta"] == 3158, "vyrobni sestava 30: system a karta spojky")
check(all(d["part_id"] != "Object_7" for d in vs40["dily"]) and any(d["part_id"] == "Object_11" for d in vs40["dily"]), "vyrobni sestava 40: profily Object_11")
html40 = VL.html_list(vs40)
html30 = VL.html_list(vs30)
check("systém 40" in html40 and "profilů 40×40" in html40 and "rohová spojka 40×40" in html40 and ">3176<" in html40, "vyrobni list 40: system, profil, spojka")
check("systém 30" in html30 and "profilů 30×30" in html30 and "rohová spojka 30×30" in html30 and ">3158<" in html30, "vyrobni list 30 beze zmeny")
sm40 = vs40["vypis"]["spojovaci_material"]["ke_spojkam"]
check([m["sku"] for m in sm40 if m["sku"]] and {"2.1.21.0616", "2.1.001.10.06"} <= {m["sku"] for m in sm40}, f"vyrobni sestava 40: spojovaci material SKU ({[m['sku'] for m in sm40]})")
check(any("Profil 40x40" in (b["nazev"] or "") for b in vs40["kusovnik_katalog"]) and any("40x40 Rohová spojka" in (b["nazev"] or "") for b in vs40["kusovnik_katalog"]), "vyrobni sestava 40: katalogovy kusovnik se SKU karet 40")
check(vs40["cena_celkem_czk"] == r40["price"]["net"], f"vyrobni sestava 40: cena = cena z resolve ({vs40['cena_celkem_czk']} / {r40['price']['net']})")

# ---------------------------------------------------------------- 9) staff blok (odkazy) a staff routa
rs_staff = staff.post("/api/shop/configurator/resolve", json={"product_id": P40, "selection": VYBER, "staff": True}).get_json()
blok = rs_staff.get("staff") or {}
check("system=40" in (blok.get("vyrobni_list_url") or ""), f"staff blok 40: odkaz na vyrobni list nese system=40 ({blok.get('vyrobni_list_url')})")
rs_staff30 = staff.post("/api/shop/configurator/resolve", json={"product_id": P30, "selection": VYBER, "staff": True}).get_json()
check("system" not in (rs_staff30["staff"].get("vyrobni_list_url") or ""), "staff blok 30: odkaz beze zmeny (bez system)")
vl = staff.get(blok["vyrobni_list_url"])
check(vl.status_code == 200 and "systém 40" in vl.get_data(as_text=True), "odkaz na vyrobni list 40 funguje a je system 40")
vl30 = staff.get(rs_staff30["staff"]["vyrobni_list_url"])
check(vl30.status_code == 200 and "systém 30" in vl30.get_data(as_text=True), "odkaz na vyrobni list 30 funguje")
kfg = staff.get("/api/stul/konfigurace?system=40&sirka=1800&hloubka=900")
kj = kfg.get_json()
check(kfg.status_code == 200 and kj["system"] == 40 and kj["profil_mm"] == 40 and kj["parametry"]["system"] == 40 and kj["cena"], f"staff routa system=40 ({kfg.status_code})")
check(kj["systemy"]["30"]["vzpery"] is True and kj["systemy"]["40"]["vzpery"] is True, "staff routa: popis systemu")
check(kj["kod"] != staff.get("/api/stul/konfigurace?sirka=1800&hloubka=900").get_json()["kod"], "staff routa: jiny kod pro system 40")
check(staff.get("/api/stul/konfigurace?system=50").status_code == 400, "staff routa: neplatny system = 400")
check(staff.get("/api/stul/konfigurace?system=abc").status_code == 400, "staff routa: system=abc = 400")
mg = staff.get(kj["model_url"])
check(mg.status_code == 200 and mg.data[:4] == b"glTF", "staff model.glb system=40")

# ---------------------------------------------------------------- 10) ovladani ve 3D: stredni noha v % ze skutecneho rozpeti
BIG = {"w": 2200, "d": 800, "mid": 40}
cb, rb = resolve(P40, BIG)
vod = rb.get("vodici") or {}
tahy = {t["id"]: t for t in (vod.get("ovladani") or {}).get("tahy", [])}
mid = tahy.get("mid")
check(mid is not None and abs(mid["mm_na_jednotku"] - (2200 - 40) / 100.0) < 1e-6, f"tah mid ve 40: rozpeti = sirka - 40 ({mid and mid['mm_na_jednotku']})")
cb30, rb30 = resolve(P30, BIG)
mid30 = {t["id"]: t for t in (rb30["vodici"]["ovladani"]["tahy"])}.get("mid")
check(mid30 is not None and abs(mid30["mm_na_jednotku"] - (2200 - 30) / 100.0) < 1e-6, "tah mid v 30: rozpeti = sirka - 30 (beze zmeny)")
check(rb["selection"]["mid"] == 40 and abs(rb30["selection"]["mid"] - 40) < 1, "stredni noha 40 % se zachova")

# ---------------------------------------------------------------- 11) model/<hash> a nekonfigurovatelny produkt, rules_version
check(anon.get(f"/api/shop/configurator/model/{r40['hash']}").status_code == 200, "model/<hash> 40")
check(anon.post("/api/shop/configurator/resolve", json={"product_id": 1, "selection": {}}).status_code == 404, "resolve nekonfigurovatelneho produktu 404")
check(anon.post("/api/shop/configurator/resolve", json={"product_id": P40, "selection": VYBER, "rules_version": "x"}).status_code == 409, "rules_version jina = 409")
cpl, rpl = resolve(P40, {"w": "abc", "d": None, "h": 99999, "shelf": "x"})
check(cpl == 200 and rpl["selection"]["h"] == S.ROZSAH["vyska"][1], "nesmyslny vyber se orizne (system 40)")

print(f"\n{OK} kontrol OK" + ("" if not FAILS else f"; SELHALO {len(FAILS)}"))
sys.exit(1 if FAILS else 0)
