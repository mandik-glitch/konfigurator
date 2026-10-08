#!/usr/bin/env python3
"""SYSTEM 45 (hluboky stul az 2500 mm) ve verejnem API stolu (api/stul_shop.py) + kosik + vyrobni list + staff API (bot10, 2026-10-07).

SKUTECNE routy pres Flask test_client; DB se jen CTE (ceny katalogu), mapovani produktu (app_settings.configurator_products) se podstrci jen v pameti, nic se nezapisuje.
Produkt 9877 = system 40 (recept stul_system40), 9878 = system 45 (stul_system45) - fiktivni ID, zadna karta v DB.
Hlida: schema 45 (profil 40x40, sloupec hloubky 400-2500 mm, 40 zustava 400-1500), STEJNY vyber do hloubky 1500 mm dava v 40 i 45 stejnou cenu a kusovnik, hluboky stul (priznak, oznameni
v cs / en / sk, vice dilu a vyssi cena), orez hloubky podle systemu, system dava PRODUKT, token modelu s klicem y=45, GLB hlubokeho stolu, kosikovou funkci `vyres`, vyrobni sestavu a list
(cislo generatoru 05), staff blok a routu /api/stul/konfigurace?system=45, ovladani ve 3D (tah hloubky), cenu vyrezu podle PRAVIDEL SYSTEMU 45 (ne 40).

Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root \\
    --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_system45/test_s45_shop.py"""
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
sys.dont_write_bytecode = True
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
if hasattr(SH, "_DELKY_CACHE"):
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


P40, P45 = 9877, 9878
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(P40): SH.RECEPT_40, str(P45): SH.RECEPT_45})
SH._SYSTEMY_CACHE.update(t=0.0, list=[])
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


def slot(sc, sid):
    return next((x for x in sc["slots"] if x["id"] == sid), None)


def rozsah(sc, sid):
    x = slot(sc, sid)
    return (x["slider"]["min"], x["slider"]["max"], x["slider"]["step"]) if x and x.get("slider") else None


# ---------------------------------------------------------------- 1) schema
s40, s45 = schema(P40), schema(P45)
check(s45.get("system") == 45 and s45["profile"] == "40x40" and s45["profile_mm"] == 40, f"schema 45: system 45, profil 40x40 ({s45.get('system')}, {s45.get('profile')}, {s45.get('profile_mm')})")
check(s40.get("system") == 40 and s40["profile_mm"] == 40, "schema 40 beze zmeny")
ids40, ids45 = [x["id"] for x in s40["slots"]], [x["id"] for x in s45["slots"]]
check(set(ids40) == set(ids45), f"schema 45: stejne sloty jako schema 40 ({sorted(set(ids40) ^ set(ids45))})")
d40, d45 = slot(s40, "d"), slot(s45, "d")
check(rozsah(s40, "d") == (400, 1500, 10) and rozsah(s45, "d") == (400, 2500, 10), f"posuvnik hloubky: 40 -> {rozsah(s40, 'd')}, 45 -> {rozsah(s45, 'd')}")
for sid in ("cut1d", "cut1x", "cut2d", "cut3x"):
    a, b = rozsah(s40, sid), rozsah(s45, sid)
    check(a and b and b[1] > a[1] and b[0] == a[0] and b[2] == a[2], f"posuvnik {sid}: v 45 sahne dal nez ve 40 ({a} / {b})")
check(s45["default_selection"] == s40["default_selection"], "schema 45: vychozi vyber = vychozi vyber systemu 40 (kompatibilita)")
sy = {x["system"]: x for x in (s45.get("systems") or [])}
check(sorted(sy) == [40, 45] and sy[40]["card_id"] == P40 and sy[45]["card_id"] == P45 and all(isinstance(x["active"], bool) for x in sy.values()), f"schema.systems: karty obou systemu ({s45.get('systems')})")
check(SH.konfigurovatelny(P45) is True and SH.system_pro_produkt(P45) == 45 and SH.system_pro_produkt(P40) == 40, "konfigurovatelny / system_pro_produkt")
check(not any("product_" in json.dumps(x, ensure_ascii=False) for x in (s40, s45)), "schema neobsahuje interni slovo 'product_'")

# ---------------------------------------------------------------- 2) STEJNY vyber do hloubky 1500: stejne dily a cena v 40 i 45
VYBER = {"w": 1800, "d": 1500, "h": 1000, "shelf": 2, "drawers": True, "cut1": True, "cut1x": 150, "cut1z": 300}
c40, r40 = resolve(P40, VYBER)
c45, r45 = resolve(P45, VYBER)
check(c40 == 200 and c45 == 200 and r40["valid"] and r45["valid"], f"stejny vyber (d 1500) je platny v obou systemech ({r40.get('errors')}, {r45.get('errors')})")
check(r40["hash"] != r45["hash"] and r40["kod"] != r45["kod"], "ruzne hashe a kody (system je soucasti hashe)")
check(r45["price"]["net"] == r40["price"]["net"] > 0, f"cena stolu do hloubky 1500 je v 45 stejna jako v 40 ({r45['price']['net']} / {r40['price']['net']} Kc)")
for k in ("w", "d", "h", "shelf", "drawers", "cut1"):
    check(r45["selection"][k] == r40["selection"][k] == VYBER[k], f"vyber {k} se zachova v obou systemech ({r40['selection'][k]}, {r45['selection'][k]})")
check(not [n for n in r45["notices"] if n["slot"] == "d" and "nad 1500 mm" in n["message"]], f"d=1500: zadne oznameni o stredni rade noh ({[n['message'] for n in r45['notices'] if n['slot'] == 'd']})")
check([n["message"] for n in r45["notices"] if n["slot"] == "d"] == [n["message"] for n in r40["notices"] if n["slot"] == "d"], "d=1500: stejna oznameni ke hloubce v 45 jako ve 40")
o40 = SH.pro_objednavku(VYBER, None, "cs", P40)
o45 = SH.pro_objednavku(VYBER, None, "cs", P45)
check(o40["ok"] and o45["ok"] and o45["valid"], "pro_objednavku obou systemu ok")
check(sorted((b["nazev"], b["mnozstvi"]) for b in o45["bom"]) == sorted((b["nazev"], b["mnozstvi"]) for b in o40["bom"]), "kusovnik 45 (d 1500) == kusovnik 40 (stejne polozky i mnozstvi)")

# ---------------------------------------------------------------- 3) hluboky stul
DEEP = {**VYBER, "d": 2000}
cd, rd = resolve(P45, DEEP)
check(cd == 200 and rd["valid"] and rd["selection"]["d"] == 2000, f"hluboky stul (d 2000) je platny a hloubka se zachova ({rd.get('errors')}, {rd['selection'].get('d')})")
check(rd["price"]["net"] > r45["price"]["net"], f"hlubsi stul je dražší ({rd['price']['net']} > {r45['price']['net']} Kc)")
nd = [n for n in rd["notices"] if n["slot"] == "d" and n["action"] == "info" and "nad 1500 mm" in n["message"]]
check(len(nd) == 1 and "střední noha" in nd[0]["message"], f"oznameni o stredni rade noh (cs): {nd}")
_, rde = resolve(P45, DEEP, "en")
_, rds = resolve(P45, DEEP, "sk")
check([n for n in rde["notices"] if n["slot"] == "d" and "middle leg" in n["message"] and "1500" in n["message"]], f"oznameni o stredni rade noh (en): {[n['message'] for n in rde['notices'] if n['slot'] == 'd']}")
check([n for n in rds["notices"] if n["slot"] == "d" and "stredná noha" in n["message"] and "1500" in n["message"]], f"oznameni o stredni rade noh (sk): {[n['message'] for n in rds['notices'] if n['slot'] == 'd']}")
_, rdd = resolve(P45, DEEP, "de")
check([n for n in rdd["notices"] if n["slot"] == "d" and "middle leg" in n["message"]], "jazyk bez sablony (de): oznameni se vrati anglicky, ne vyjimkou")
od = SH.pro_objednavku(DEEP, None, "cs", P45)
qty = lambda o, nazev: sum(b["mnozstvi"] for b in o["bom"] if b["nazev"] == nazev)  # noqa: E731
check(od["ok"] and od["valid"], "pro_objednavku hlubokeho stolu ok")
check(qty(od, "profil 40×40") > qty(o45, "profil 40×40"), f"hluboky stul ma vic profilu 40x40 ({qty(od, 'profil 40×40')} vs {qty(o45, 'profil 40×40')})")
check(qty(od, "rohová spojka 40×40") > qty(o45, "rohová spojka 40×40"), f"hluboky stul ma vic rohovych spojek ({qty(od, 'rohová spojka 40×40')} vs {qty(o45, 'rohová spojka 40×40')})")
kolecka = [b for b in od["bom"] if "kole" in b["nazev"].lower()]
kolecka_o = [b for b in o45["bom"] if "kole" in b["nazev"].lower()]
check(kolecka and kolecka_o and sum(b["mnozstvi"] for b in kolecka) == sum(b["mnozstvi"] for b in kolecka_o) + 2, f"kolecek je o 2 vic (stredni rada): {[(b['nazev'], b['mnozstvi']) for b in kolecka]} vs {[(b['nazev'], b['mnozstvi']) for b in kolecka_o]}")
# orez hloubky podle systemu
for d_in, pid, ocek in ((3000, P45, 2500), (2500, P45, 2500), (2490, P45, 2490), (100, P45, 400), (2500, P40, 1500), (1500, P40, 1500)):
    cc, rr = resolve(pid, {**VYBER, "d": d_in, "shelf": 0, "drawers": False, "cut1": False})
    check(cc == 200 and rr["selection"]["d"] == ocek, f"orez hloubky: d={d_in} v produktu {pid} -> {ocek} ({rr['selection'].get('d')})")
# velmi hluboky stul 2500 s nejvetsi sirkou je platny
cmax, rmax = resolve(P45, {"w": 3000, "d": 2500, "h": 840, "shelf": 2, "drawers": True})
check(cmax == 200 and rmax["valid"] and rmax["selection"]["d"] == 2500 and rmax["selection"]["w"] == 3000, f"nejvetsi stul 3000 x 2500 je platny ({rmax.get('errors')})")

# ---------------------------------------------------------------- 4) token modelu a GLB
tok45 = rd["model"]["url"].rsplit("/", 1)[1]
import base64  # noqa: E402
telo = json.loads(base64.urlsafe_b64decode(tok45.split(".")[0] + "=" * (-len(tok45.split(".")[0]) % 4)))
check(telo.get("y") == 45, f"token 45 nese system (y=45) ({telo})")
pp, chyba = SH.over_model(tok45)
check(chyba is None and pp["system"] == 45 and pp["hloubka"] == 2000, f"over_model(token 45) -> system 45, hloubka 2000 ({chyba})")
g = anon.get(rd["model"]["url"])
check(g.status_code == 200 and g.data[:4] == b"glTF", "GLB hlubokeho stolu 200")
lo, hi = glb_obalka(g.data)
roz = hi - lo
check(max(roz[0], roz[2]) >= 2000 and max(roz[0], roz[2]) <= 2200, f"obalka GLB hlubokeho stolu: delsi vodorovny rozmer ~ hloubka 2000 mm ({roz[0]:.0f} x {roz[2]:.0f})")
gm = anon.get(rmax["model"]["url"])
lo, hi = glb_obalka(gm.data)
check(gm.status_code == 200 and max(hi[0] - lo[0], hi[2] - lo[2]) >= 3000, "GLB nejvetsiho stolu 200")
check(anon.get(f"/api/shop/configurator/model/{rd['hash']}").status_code == 200, "model/<hash> hlubokeho stolu")

# ---------------------------------------------------------------- 5) kosik
import konfigurace_kosik as KK  # noqa: E402
_kc = appmod.get_conn(); _kcur = _kc.cursor()
try:
    k45 = KK.vyres(_kcur, P45, DEEP)
    check(k45["hash"] == rd["hash"] and k45["net_czk"] == rd["price"]["net"], f"kosik: vyres() hlubokeho stolu == resolve ({k45['net_czk']} / {rd['price']['net']})")
    check(any(b["nazev"] == "profil 40×40" for b in k45["bom"]), "kosik: kusovnik radku nese profil 40x40")
finally:
    _kc.rollback()

# ---------------------------------------------------------------- 6) vyrobni sestava + vyrobni list
vs = SH.vyrobni_sestava(DEEP, None, "cs", P45)
check(vs["ok"] and vs["vypis"]["system"] == 45 and vs["vypis"]["spojka_karta"] == 3176 and vs["parametry"]["system"] == 45, "vyrobni sestava 45: system a karta spojky (3176 jako 40)")
check(all(d["part_id"] != "Object_7" for d in vs["dily"]) and any(d["part_id"] == "Object_11" for d in vs["dily"]), "vyrobni sestava 45: profily Object_11")
html = VL.html_list(vs)
check("systém 45" in html and "profilů 40×40" in html and ">3176<" in html, "vyrobni list 45: system, profil, spojka")
check("05" in html, "vyrobni list 45: cislo generatoru 05")
check(vs["cena_celkem_czk"] == rd["price"]["net"], f"vyrobni sestava 45: cena = cena z resolve ({vs['cena_celkem_czk']} / {rd['price']['net']})")
check(VL._CISLO_GENERATORU[45] == "05" and VL._CISLO_GENERATORU[40] == "02", "cisla generatoru 02 / 05")

# ---------------------------------------------------------------- 7) staff blok a staff routa
blok = staff.post("/api/shop/configurator/resolve", json={"product_id": P45, "selection": DEEP, "staff": True}).get_json().get("staff") or {}
check("system=45" in (blok.get("vyrobni_list_url") or ""), f"staff blok 45: odkaz na vyrobni list nese system=45 ({blok.get('vyrobni_list_url')})")
vl = staff.get(blok["vyrobni_list_url"])
check(vl.status_code == 200 and "systém 45" in vl.get_data(as_text=True), "odkaz na vyrobni list 45 funguje")
kfg = staff.get("/api/stul/konfigurace?system=45&sirka=1800&hloubka=2000")
kj = kfg.get_json()
check(kfg.status_code == 200 and kj["system"] == 45 and kj["profil_mm"] == 40 and kj["parametry"]["system"] == 45 and kj["parametry"]["hloubka"] == 2000 and kj["cena"], f"staff routa system=45 hloubka 2000 ({kfg.status_code})")
check("45" in kj["systemy"] and kj["systemy"]["45"]["vzpery"] is True, "staff routa: popis systemu 45")
check(staff.get("/api/stul/konfigurace?system=45&sirka=1800&hloubka=2600").status_code == 400, "staff routa: hloubka 2600 v systemu 45 = 400")
check(staff.get("/api/stul/konfigurace?system=40&sirka=1800&hloubka=2000").status_code == 400, "staff routa: hloubka 2000 v systemu 40 = 400 (beze zmeny)")
check(staff.get("/api/stul/konfigurace?system=50").status_code == 400, "staff routa: neplatny system = 400")
mg = staff.get(kj["model_url"])
check(mg.status_code == 200 and mg.data[:4] == b"glTF", "staff model.glb system=45")
# cena podle pravidel SYSTEMU 45 (ne 40): cena vyrezu
puv = {s_: dict(S.PRAVIDLA_SYSTEMU[s_]) for s_ in S.SYSTEMY}
try:
    S.nastav_pravidla({"cena_vyrez": 500}, system=45)
    _, rv45 = resolve(P45, DEEP)
    _, rv40 = resolve(P40, VYBER)
    check(500 <= rv45["price"]["net"] - rd["price"]["net"] <= 530 and rv40["price"]["net"] == r40["price"]["net"],          # + balne (procento z celku)
          f"cena vyrezu 500 Kc v pravidlech systemu 45 plati jen v 45 ({rv45['price']['net'] - rd['price']['net']} / {rv40['price']['net'] - r40['price']['net']})")
    vs_r = SH.vyrobni_sestava(DEEP, None, "cs", P45)
    po_r = SH.pro_objednavku(DEEP, None, "cs", P45)
    check(vs_r["cena_celkem_czk"] == rv45["price"]["net"] and po_r["price"]["net"] == rv45["price"]["net"], f"cena vyrezu: vyrobni sestava ({vs_r['cena_celkem_czk']}) a objednavka ({po_r['price']['net']}) = resolve ({rv45['price']['net']})")
    kj2 = staff.get("/api/stul/konfigurace?system=45&sirka=1800&hloubka=2000&vyrez1=1").get_json()
    kj3 = staff.get("/api/stul/konfigurace?system=45&sirka=1800&hloubka=2000").get_json()
    check(kj2["cena"]["bez_dph"] - kj3["cena"]["bez_dph"] >= 500, f"staff routa: cena vyrezu podle pravidel systemu 45 ({kj2['cena']['bez_dph'] - kj3['cena']['bez_dph']})")
finally:
    for s_, sada in puv.items():
        S.PRAVIDLA_SYSTEMU[s_] = sada

# ---------------------------------------------------------------- 8) ovladani ve 3D
vod = (rd.get("vodici") or {}).get("ovladani") or {}
tahy = {t["id"]: t for t in vod.get("tahy", [])}
print("  (ovladani: tahy", sorted(tahy), ")")
td = tahy.get("d")
check(td is not None, f"ovladani ve 3D: tah hloubky 'd' existuje ({sorted(tahy)})")
if td:
    print("  (tah d:", {k: td[k] for k in td if k in ("min", "max", "krok", "step", "mm_na_jednotku", "od", "do")}, ")")
    check(float(td.get("max", 0)) >= 2500, f"ovladani ve 3D: tah hloubky 45 sahne az na 2500 mm ({td.get('max')})")
    _, r40d = resolve(P40, {**VYBER, "d": 1200})
    t40 = {t["id"]: t for t in (r40d["vodici"]["ovladani"]["tahy"])}.get("d")
    check(t40 is not None and float(t40.get("max", 0)) <= 1500, f"ovladani ve 3D: tah hloubky 40 zustava do 1500 mm ({t40 and t40.get('max')})")

print(f"\n{OK} kontrol OK" + ("" if not FAILS else f"; SELHALO {len(FAILS)}"))
sys.exit(1 if FAILS else 0)
