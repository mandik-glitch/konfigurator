#!/usr/bin/env python3
"""Test SYSTEMU 35 ve verejnem API stolu (api/stul_shop.py) + kosik + staff API a PRENOSITELNOSTI vyberu mezi systemy 30 / 35 / 40 (bot10, 2026-10-05).

SKUTECNE routy pres Flask test_client; DB se jen CTE (ceny katalogu), mapovani produktu (app_settings.configurator_products) se podstrci jen v pameti, nic se nezapisuje.
Produkt 9876 = system 30 (stul_system30), 9878 = system 35 (stul_system35), 9877 = system 40 (stul_system40) - fiktivni ID, zadna karta v DB.
Hlida: schema 35 (profil 35x35, vychozi poloha vyrezu 105, vzpery), systems = [30, 35, 40], STEJNY vyber ve vsech trech systemech (prenositelnost), system dava PRODUKT (klient ho nezmeni),
cena a kusovnik podle systemu (profil_35x35, rohova spojka 3158 ze systemu 30, zaslepka 3090, sikme spojky 3254), token modelu (y = 35) a GLB (obrysove rozmery stejne), vyrobni sestava
+ vyrobni list (Generator stolu 03), neporusenost systemu 30 a 40 (hash, token), kosikovou funkci `pro_objednavku(product_id=...)`, staff routu /api/stul/konfigurace?system=35.

Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root \\
    --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-05_system35/test_shop_system35.py"""
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
SA.obnov_pravidla = lambda force=False: None            # zive pravidla stolu (app_settings) test neovlivni

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print("  CHYBA:", msg)


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


def resolve(pid, sel, lang="cs", extra=None):
    body = {"product_id": pid, "selection": sel, "lang": lang}
    body.update(extra or {})
    r = anon.post("/api/shop/configurator/resolve", json=body)
    return r.status_code, r.get_json()


def glb_obalka(data):
    import numpy as np
    off, js = 12, None
    while off < len(data):
        cl, ct = struct.unpack("<II", data[off:off + 8])
        if ct == 0x4E4F534A:
            js = json.loads(data[off + 8:off + 8 + cl])
        off += 8 + cl
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for m in js["meshes"]:
        for pr in m["primitives"]:
            a = js["accessors"][pr["attributes"]["POSITION"]]
            lo, hi = np.minimum(lo, a["min"]), np.maximum(hi, a["max"])
    return lo, hi


def token_telo(url):
    t = url.rsplit("/", 1)[1].split(".")[0]
    return json.loads(base64.urlsafe_b64decode(t + "=" * (-len(t) % 4)))


# ---------------------------------------------------------------- 1) schema podle systemu
s30, s35, s40 = schema(P30), schema(P35), schema(P40)
check(s35.get("system") == 35 and s35["profile"] == "35x35" and s35["profile_mm"] == 35, f"schema 35: system 35, profil 35x35 ({s35.get('system')}, {s35.get('profile')})")
ids30, ids35, ids40 = [x["id"] for x in s30["slots"]], [x["id"] for x in s35["slots"]], [x["id"] for x in s40["slots"]]
check(set(ids35) - {"sleeve", "sleevelen"} == set(ids30) == set(ids40) and {"sleeve", "sleevelen"} <= set(ids35), f"schema 35: stejne sloty jako 30 a 40, vcetne vzper, a navic navlek nohou ({sorted(set(ids35) ^ set(ids30))})")
check(s35["default_selection"]["cut1x"] == 105 and s35["default_selection"]["w"] == 1280 and "sys" not in s35["default_selection"], f"schema 35: vychozi vyrez x 105 ({s35['default_selection'].get('cut1x')}), vyber bez skryteho pole system")
check(any(d["id"] == "braces" and d.get("auto_on") for d in s35["slots"]) and any(d["id"] == "bracelen" and d.get("depends_on") == ["braces"] for d in s35["slots"]), "schema 35: vzpery maji slot, automaticke zapnuti a zavislost delky")
sy = {x["system"]: x for x in (s30.get("systems") or [])}
check(sorted(sy) == [30, 35, 40] and sy[30]["card_id"] == P30 and sy[35]["card_id"] == P35 and sy[40]["card_id"] == P40 and all(isinstance(x["active"], bool) for x in sy.values()), f"schema.systems: karty vsech tri systemu ({s30.get('systems')})")
check(s30.get("systems") == s35.get("systems") == s40.get("systems"), "schema.systems je u vsech karet stejne (prepnuti tehoz vyberu)")
check(not any("product_" in json.dumps(x, ensure_ascii=False) for x in (s30, s35, s40)), "schema vsech systemu neobsahuje interni slovo 'product_' (verejne texty)")
check(SH.konfigurovatelny(P35) is True and SH.system_pro_produkt(P35) == 35 and SH.system_pro_produkt(P30) == 30 and SH.system_pro_produkt(P40) == 40, "konfigurovatelny + system_pro_produkt (35)")

# ---------------------------------------------------------------- 2) resolve: stejny vyber ve vsech systemech
VYBER = {"w": 1800, "d": 900, "h": 1000, "shelf": 2, "drawers": True, "cut1": True, "cut1x": 150, "cut1z": 300, "wheels": True, "sleeve": False}          # 2026-10-05: vychozi koncovka systemu 35 je navlek; pro srovnani se systemy 30 a 40 kolecka a bez navleku
res = {s: resolve(p, VYBER) for s, p in ((30, P30), (35, P35), (40, P40))}
check(all(res[s][0] == 200 for s in res), f"resolve 200 ve vsech systemech ({[res[s][0] for s in res]})")
r30, r35, r40 = res[30][1], res[35][1], res[40][1]
check(r30["valid"] and r35["valid"] and r40["valid"], f"stejny vyber je platny ve vsech trech systemech ({r35.get('errors')})")
check(len({r30["hash"], r35["hash"], r40["hash"]}) == 3 and len({r30["kod"], r35["kod"], r40["kod"]}) == 3, "tri ruzne hashe a kody (system je soucasti hashe 35 i 40)")
p30_, p35_, p40_ = r30["price"]["net"], r35["price"]["net"], r40["price"]["net"]
check(p30_ > 0 and p30_ < p35_ < p40_, f"cena roste s profilem: 30 < 35 < 40 ({p30_} / {p35_} / {p40_} Kc)")
check("sys" not in r35["selection"], "vyber vraceny klientovi nenese pole system (je to vlastnost produktu)")
for k in ("w", "d", "h", "shelf", "drawers", "cut1"):
    check(r30["selection"][k] == r35["selection"][k] == r40["selection"][k] == VYBER[k], f"vyber {k} se ve vsech systemech zachova")
check(set(r30["options"]) == set(r35["options"]) - {"sleeve", "sleevelen"} == set(r40["options"]) and {"sleeve", "sleevelen"} <= set(r35["options"]), "options: stejne sloty ve vsech systemech (35 navic navlek nohou)")
c1, rx = resolve(P35, {**VYBER, "sys": 30, "system": 40})
check(c1 == 200 and rx["hash"] == r35["hash"], "pole sys/system ve vyberu se u produktu 35 ignoruje (hash stejny)")

# ---------------------------------------------------------------- 3) systemy 30 a 40 nedotceny: hash a token
p30, _ = SH.normalizuj(VYBER, 30)
p30 = S.sestav_stul(**p30)["parametry"]
check(G.kanonicky_hash(p30) == r30["hash"], "hash systemu 30 = kanonicky hash bez klice system")
t30, t35, t40 = (token_telo(r["model"]["url"]) for r in (r30, r35, r40))
check("y" not in t30 and t35.get("y") == 35 and t40.get("y") == 40, f"token: 30 bez klice y, 35 y=35, 40 y=40 ({t30.get('y')}, {t35.get('y')}, {t40.get('y')})")
pp, chyba = SH.over_model(r35["model"]["url"].rsplit("/", 1)[1])
check(chyba is None and pp["system"] == 35, "over_model(token 35) -> system 35")

# ---------------------------------------------------------------- 4) GLB: obrysove rozmery stolu stejne
g35, g30 = anon.get(r35["model"]["url"]), anon.get(r30["model"]["url"])
check(g35.status_code == 200 and g35.data[:4] == b"glTF", "GLB systemu 35 200")
lo30, hi30 = glb_obalka(g30.data)
lo35, hi35 = glb_obalka(g35.data)
r30_, r35_ = hi30 - lo30, hi35 - lo35
check(abs(r35_[1] - r30_[1]) <= 6.0 and abs(r35_[0] - r30_[0]) <= 6.0 and abs(r35_[2] - r30_[2]) <= 6.0, f"obalka stolu 35 = obalka stolu 30 (rozdil max 2,5 mm na kolecka/rameno): {r30_.round(1)} / {r35_.round(1)}")

# ---------------------------------------------------------------- 5) vzpery: v 35 nese spojka 3254 (ze systemu 30)
VZ = {**VYBER, "w": 1840, "arm": 760, "braces": True, "bracelen": 300, "panels": False, "socket": False}
cv35, rv35 = resolve(P35, VZ)
check(cv35 == 200 and rv35["selection"]["braces"] is True and rv35["selection"]["bracelen"] == 300 and rv35["valid"], f"35: vzpery zustanou ve vyberu a konfigurace je platna ({rv35['selection'].get('braces')}, {rv35.get('errors')})")
check(not any(n["slot"] == "braces" for n in rv35["notices"]), "35: vzpery bez oznameni o odebrani")
bomv35 = [b["nazev"] for b in SH.pro_objednavku(VZ, None, "cs", P35)["bom"]]
check("šikmá spojka 45° (30)" in bomv35 and "šikmá spojka 45° (40)" not in bomv35, f"35: kusovnik ma sikme spojky 3254 ze systemu 30 ({[n for n in bomv35 if 'šikmá' in n]})")
check(rv35["options"]["bracelen"]["max"] >= rv35["options"]["bracelen"]["min"] >= 100 and rv35["options"]["bracelen"]["max"] <= 1000, f"35: meze delky vzpery z generatoru ({rv35['options']['bracelen']})")

# ---------------------------------------------------------------- 6) texty: supliky v 35 maji prahy z generatoru
SMALL = {"w": 650, "d": 900, "drawers": True}
cs, rs = resolve(P35, SMALL, "cs")
txt = [n["message"] for n in rs["notices"] if n["slot"] == "drawers"]
d35, w35 = SH._prahy_suplik(35)
check(txt and f"{d35} mm" in txt[0] and f"{w35} mm" in txt[0], f"35: duvod odebrani supliku nese prahy z generatoru ({d35}/{w35}): {txt}")
ce, re_ = resolve(P35, SMALL, "en")
check([n["message"] for n in re_["notices"] if n["slot"] == "drawers" and f"{w35} mm" in n["message"]], "35: anglicky text s prahy")
csk, rsk = resolve(P35, SMALL, "sk")
check([n["message"] for n in rsk["notices"] if n["slot"] == "drawers" and f"{w35} mm" in n["message"]], "35: slovensky text s prahy")

# ---------------------------------------------------------------- 7) kosik / objednavka: pro_objednavku(product_id=...)
o35 = SH.pro_objednavku(VYBER, None, "cs", P35)
check(o35["ok"] and o35["valid"] and o35["hash"] == r35["hash"] and o35["price"]["net"] == p35_, "pro_objednavku 35: ok, platne, hash a cena = resolve")
nazvy35 = [b["nazev"] for b in o35["bom"]]
check("profil 35×35" in nazvy35 and "rohová spojka" in nazvy35 and "profil 30×30" not in nazvy35 and "profil 40×40" not in nazvy35, f"35: neutralni kusovnik ({nazvy35})")
check(any("M6x12" in n for n in nazvy35) and any("drážka 8" in n for n in nazvy35), f"35: spojovaci material jako v systemu 30 (M6x12, drazka 8) ({[n for n in nazvy35 if 'M6' in n]})")
check(SH.pro_objednavku(VYBER, None, "cs", None, 35)["hash"] == o35["hash"], "pro_objednavku(system=35) = hash karty 35")
check(SH.pro_objednavku({**VYBER, "sys": 40}, None, "cs", P35)["hash"] == o35["hash"], "pro_objednavku: produkt 35 prebije cokoli ve vyberu")
import konfigurace_kosik as KK  # noqa: E402
_kc = appmod.get_conn(); _kcur = _kc.cursor()
try:
    k35 = KK.vyres(_kcur, P35, VYBER)
    check(k35["hash"] == r35["hash"] and k35["net_czk"] == p35_, f"kosik: vyres() pro kartu 35: hash a cena = resolve ({k35['net_czk']} / {p35_})")
    check(any(b["nazev"] == "profil 35×35" for b in k35["bom"]), "kosik: kusovnik radku podle systemu karty 35")
finally:
    _kc.rollback()

# ---------------------------------------------------------------- 8) vyrobni sestava + vyrobni list
vs35 = SH.vyrobni_sestava(VYBER, None, "cs", P35)
check(vs35["ok"] and vs35["vypis"]["system"] == 35 and vs35["vypis"]["spojka_karta"] == 3158 and vs35["parametry"]["system"] == 35, "vyrobni sestava 35: system a karta spojky (3158 ze systemu 30)")
check(all(d["part_id"] != "Object_7" for d in vs35["dily"]) and any(d["part_id"] == "profil_35x35" for d in vs35["dily"]), "vyrobni sestava 35: profily profil_35x35")
html35 = VL.html_list(vs35)
check("systém 35" in html35 and "Generátor stolu 03" in html35 and "profilů 35×35" in html35 and ">3158<" in html35, "vyrobni list 35: Generator stolu 03, system, profil, spojka")
sm35 = vs35["vypis"]["spojovaci_material"]["ke_spojkam"]
check({"2.1.21.0612", "2.1.001.08.06"} <= {m["sku"] for m in sm35 if m["sku"]}, f"vyrobni sestava 35: spojovaci material SKU jako u 30 ({[m['sku'] for m in sm35]})")
check(vs35["cena_celkem_czk"] == p35_, f"vyrobni sestava 35: cena = cena z resolve ({vs35['cena_celkem_czk']} / {p35_})")

# ---------------------------------------------------------------- 9) staff blok (odkazy) a staff routa
rs_staff = staff.post("/api/shop/configurator/resolve", json={"product_id": P35, "selection": VYBER, "staff": True}).get_json()
blok = rs_staff.get("staff") or {}
check("system=35" in (blok.get("vyrobni_list_url") or ""), f"staff blok 35: odkaz na vyrobni list nese system=35 ({blok.get('vyrobni_list_url')})")
vl = staff.get(blok["vyrobni_list_url"])
check(vl.status_code == 200 and "systém 35" in vl.get_data(as_text=True), "odkaz na vyrobni list 35 funguje")
kfg = staff.get("/api/stul/konfigurace?system=35&sirka=1800&hloubka=900")
kj = kfg.get_json()
check(kfg.status_code == 200 and kj["system"] == 35 and kj["profil_mm"] == 35 and kj["parametry"]["system"] == 35 and kj["cena"], f"staff routa system=35 ({kfg.status_code})")
check(set(kj["systemy"]) >= {"30", "35", "40"} and kj["systemy"]["35"]["vzpery"] is True, "staff routa: popis systemu 35")
kods = {s: staff.get(f"/api/stul/konfigurace?system={s}&sirka=1800&hloubka=900").get_json()["kod"] for s in (30, 35, 40)}
check(len(set(kods.values())) == 3, f"staff routa: jiny kod pro kazdy system ({kods})")
mg = staff.get(kj["model_url"])
check(mg.status_code == 200 and mg.data[:4] == b"glTF", "staff model.glb system=35")

# ---------------------------------------------------------------- 10) ovladani ve 3D: stredni noha v % ze skutecneho rozpeti
BIG = {"w": 2200, "d": 800, "mid": 40}
cb, rb = resolve(P35, BIG)
tahy = {t["id"]: t for t in ((rb.get("vodici") or {}).get("ovladani") or {}).get("tahy", [])}
mid = tahy.get("mid")
check(mid is not None and abs(mid["mm_na_jednotku"] - (2200 - 35) / 100.0) < 1e-6, f"tah mid v 35: rozpeti = sirka - 35 ({mid and mid['mm_na_jednotku']})")

# ---------------------------------------------------------------- 11) prenositelnost: konfigurace z kazdeho systemu do kazdeho jineho (hodnoty zustanou, neplatne se opravi)
NAHODNE = [{"w": 1500, "d": 700, "h": 900}, {"w": 2400, "d": 1000, "h": 1100, "shelf": 3}, {"w": 900, "d": 600, "h": 760, "drawers": False}, {"w": 1200, "d": 800, "braces": True, "bracelen": 250}]
for sel in NAHODNE:
    hs = {}
    for s, p in ((30, P30), (35, P35), (40, P40)):
        c, r = resolve(p, sel)
        hs[s] = (c, r["valid"], {k: r["selection"][k] for k in ("w", "d", "h") if k in sel})
    check(all(v[0] == 200 and v[1] for v in hs.values()) and len({tuple(sorted(v[2].items())) for v in hs.values()}) == 1, f"vyber {sel} se prenese do vsech systemu platne a s tymiz rozmery ({hs})")

# ---------------------------------------------------------------- 12) model/<hash> a rules_version
check(anon.get(f"/api/shop/configurator/model/{r35['hash']}").status_code == 200, "model/<hash> 35")
check(anon.post("/api/shop/configurator/resolve", json={"product_id": P35, "selection": VYBER, "rules_version": "x"}).status_code == 409, "rules_version jina = 409")
cpl, rpl = resolve(P35, {"w": "abc", "d": None, "h": 99999, "shelf": "x"})
check(cpl == 200 and rpl["selection"]["h"] == S.ROZSAH["vyska"][1], "nesmyslny vyber se orizne (system 35)")

print(f"\n{OK} kontrol OK" + ("" if not FAILS else f"; SELHALO {len(FAILS)}"))
sys.exit(1 if FAILS else 0)
