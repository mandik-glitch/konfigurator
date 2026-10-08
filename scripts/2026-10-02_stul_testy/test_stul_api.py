#!/usr/bin/env python3
"""Test API konfiguratoru stolu (api/stul_api.py) - bot8, 2026-10-02.

SKUTECNA routa /api/stul/konfigurace pres Flask test_client. DB se jen CTE (prihlaseny zamestnanec pro @staff_required),
nic se nezapisuje; vse ostatni je cista funkce.
Hlida: parsovani query stringu (cisla, prepinace, chybny vstup -> 400 s kodem), odpoved je cisty JSON (zadne numpy typy),
vychozi dotaz = konfigurace #577 (50 dilu, 26 spoju), volby (dostupnost) a jejich duvody, bez prihlaseni 401/403,
mimo rozsah / neznamy parametr = 400, cache-buster `_` se ignoruje.

Spusteni (DB pres systemd kvuli prihlasovacim udajum):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
    --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_api.py
Vystup "N kontrol OK", exit 0; jinak radky CHYBA, exit 1.
"""
import json
import os
import sys
import threading

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
    import stul_api  # noqa: E402,F401 - registruje routu (v ostrem behu ji importuje app.py)
    import stul_konfigurator as S  # noqa: E402
finally:
    threading.Thread.start = _orig

# ZIVA PRAVIDLA NEOVLIVNI TEST: Robert nastavuje pravidla stolu (cena vyrezu, prah hloubky/sirky ...) v okne Pravidla -> app_settings `stul_pravidla`; routa je pri kazdem pozadavku nacte do
# generatoru (stul_api.obnov_pravidla). Test pocita s vychozimi pravidly, proto je pripne a obnovu z DB vypne (2026-10-04: Robertova cena vyrezu 2800 Kc shodila dve kontroly "vyrez cenu nemeni").
import stul_api as _stul_api  # noqa: E402
S.nastav_pravidla({})
_stul_api.obnov_pravidla = lambda force=False: None

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")



conn = appmod.get_conn()
cur = conn.cursor()
cur.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
admin_id = cur.fetchone()["id"]
conn.rollback()

client = appmod.app.test_client()
with client.session_transaction() as sess:
    sess["user_id"] = admin_id
anon = appmod.app.test_client()

r = anon.get("/api/stul/konfigurace")
check(r.status_code in (401, 403), f"bez prihlaseni odmitnuto ({r.status_code})")

r = client.get("/api/stul/konfigurace")
d = r.get_json()
check(r.status_code == 200, f"vychozi dotaz 200 ({r.status_code})")
check(len(d["dily"]) == 54 and d["pocet_spoju"] == 28 and d["problemy"] == [], f"vychozi (1280 mm, 1 vsazeny panel): 50 dilu + 4 zaslepky volnych koncu rampy LED (od 2026-10-06), 28 spoju, bez problemu ({len(d['dily'])}, {d['pocet_spoju']}, {d['problemy'][:1]})")
check(d["suplik_meze"] == {"hodnota": 0.0, "min": -500.0, "max": 30.0, "vejde": True}, f"odpoved nese presne meze posunu supliku ({d['suplik_meze']})")
t_s = next(x for x in d["vodici"]["ovladani"]["tahy"] if x["id"] == "suplik_posun")
check(t_s["min"] == -500.0 and t_s["max"] == 30.0 and t_s["hodnota"] == 0.0, f"3D tah posunu supliku bere meze z odpovedi ({t_s['min']}, {t_s['max']}, {t_s['hodnota']})")
check(set(d["volby"]) == set(S.PREPINACE) | {"vzpery"} and all(v is None for k, v in d["volby"].items() if k not in ("patky", "navlek")) and d["volby"]["patky"] and "systému 35" in d["volby"]["navlek"],
      "vychozi: vse zapnuto, zadna volba nema duvod (jen patky: jen bez koleček; navlek nohou je jen v systemu 35)")
d12 = client.get("/api/stul/konfigurace?sirka=1200").get_json()
check(d12["volby"]["panely"] and "1252" in d12["volby"]["panely"] and d12["volby"]["vzpery"] is None, f"sirka 1200: panel se nevejde (od 1252 mm), vzpery jdou ({d12['volby']['panely']})")
check(d["rozsah"] == {"sirka": [500, 3000], "hloubka": [400, 1500], "vyska": [140, 1200], "presah": [0, 100], "led_rameno": [200, 1500],
                      "loz_rozteca": [40, 1000], "loz_okraj": [25, 500], "vzpera_delka": [100, 1000], "stojky_vyska": [200, 1500], "navlek_delka": [200, 400]}, "rozsah v odpovedi")
check(d["sirka_stredni_noha"] == 1500 and d["hloubka_bocni_profil"] == 900, "prahy v odpovedi")
json.dumps(d)  # cisty JSON (zadne numpy typy) - jinak by jsonify uz spadl

r = client.get("/api/stul/konfigurace?sirka=2000&hloubka=1000&vyska=900&police=0&kolecka=true&_=123")
d = r.get_json()
check(r.status_code == 200 and d["parametry"]["sirka"] == 2000 and d["parametry"]["police"] == 0 and d["parametry"]["kolecka"] is True,
      f"dotaz s parametry ({r.status_code})")
check(len(d["dily"]) > 50 and d["problemy"] == [], f"2000x1000x900 bez police: stredni nohy + profily bocnic, bez problemu ({len(d['dily'])}, {d['problemy'][:1]})")
check(d["max_polic"] == 1, f"se supliky max 1 police ({d.get('max_polic')})")

r = client.get("/api/stul/konfigurace?sirka=1100&hloubka=600&panely=0&led=0&suplik=0&elektrozlab=0&drzak_pet=0&police=0&kolecka=0")
d = r.get_json()
check(r.status_code == 200 and d["problemy"] == [], f"uzky stul bez prislusenstvi bez problemu ({d.get('problemy', [])[:1]})")
check(d["volby"]["panely"] and "panel" in d["volby"]["panely"] and d["volby"]["suplik"], f"volby maji duvody pro uzky/melky stul: {d['volby']}")
check(d["volby"]["kolecka"] is None and d["volby"]["stojky"] is None, "kolecka a stojky lze zapnout")

r = client.get("/api/stul/konfigurace?stredni_noha=600&sirka=2400")
check(r.status_code == 200 and r.get_json()["parametry"]["stredni_noha"] == 600.0, "stredni_noha jako cislo")
r = client.get("/api/stul/konfigurace?stredni_noha=stred&sirka=2400")
check(r.status_code == 200 and r.get_json()["parametry"]["stredni_noha"] is None, "stredni_noha=stred -> uprostred")

for q, kod in (("sirka=499", "mimo_rozsah"), ("sirka=abc", "neplatny_vstup"), ("nesmysl=1", "neznamy_parametr"),
               ("police=maybe", "neplatny_vstup"), ("vyska=1201", "mimo_rozsah"), ("sirka=2000&stredni_noha=100", "mimo_rozsah")):
    r = client.get("/api/stul/konfigurace?" + q)
    d = r.get_json()
    check(r.status_code == 400 and d.get("kod") == kod, f"{q}: 400 {kod} ({r.status_code} {d})")
r = client.post("/api/stul/konfigurace")
check(r.status_code == 405, f"POST neni povolen ({r.status_code})")

# --- cena, hash, odkaz na model ---
r = client.get("/api/stul/konfigurace")
d = r.get_json()
c = d.get("cena")
check(c is not None and c["bez_dph"] > 1000 and c["s_dph"] > c["bez_dph"] and c["mena"] == "CZK", f"cena konfigurace vypoctena ({c and (c['bez_dph'], c['s_dph'])})")
check(c and c["souhrn"]["joint_count"] == 28, f"cena pocita 28 spoju vychoziho stolu ({c and c['souhrn']})")
check(len(d["hash"]) == 16 and d["kod"] == "STL-" + d["hash"][:6].upper() and d["rules_version"], f"hash/kod/verze pravidel ({d.get('hash')}, {d.get('kod')})")
check(d["model_url"] == "/api/stul/model.glb", f"model_url bez parametru ({d['model_url']})")
r2 = client.get("/api/stul/konfigurace?sirka=2000&hloubka=1000")
d2 = r2.get_json()
check(d2["model_url"] == "/api/stul/model.glb?sirka=2000&hloubka=1000" and d2["hash"] != d["hash"], "model_url nese parametry, jina konfigurace = jiny hash")
check(d2["cena"]["bez_dph"] > c["bez_dph"], f"vetsi stul je dražší ({c['bez_dph']} -> {d2['cena']['bez_dph']})")
# --- kusovnik s cenami (Robert 2026-10-03): soucet radku = cena bez DPH, vsechny radky maji nazev/mnozstvi/cenu, DPH sedi ---
for nazev_, dd_ in (("vychozi", d), ("2000x1000", d2)):
    k_ = dd_["cena"].get("kusovnik")
    check(k_ is not None and k_["radky"] and k_["prace"], f"{nazev_}: kusovnik existuje (radky + prace)")
    if not k_:
        continue
    soucet_ = sum(x["celkem"] for x in k_["radky"]) + sum(x["celkem"] for x in k_["prace"])
    check(soucet_ == dd_["cena"]["bez_dph"] == k_["celkem"]["bez_dph"], f"{nazev_}: soucet radku kusovniku {soucet_} = cena bez DPH {dd_['cena']['bez_dph']}")
    check(k_["celkem"]["bez_dph"] + k_["celkem"]["dph"] == k_["celkem"]["s_dph"] == dd_["cena"]["s_dph"], f"{nazev_}: DPH sedi ({k_['celkem']})")
    check(all(x["nazev"] and x["mnozstvi"] > 0 and x["cena_ks"] is not None and x["celkem"] == round(x["mnozstvi"] * x["cena_ks"]) or abs(x["celkem"] - x["mnozstvi"] * x["cena_ks"]) <= x["mnozstvi"] for x in k_["radky"] if "karta chybí" not in x["nazev"]),
          f"{nazev_}: radek dilu = mnozstvi x cena za kus (do zaokrouhleni)")
    # spojovaci material ke spojkam (Robert 2026-10-04): na kazdou rohovou spojku 2 sroubu M6x12 + 2 otocne matice, na kazdy uhel 45 st. 2 zapustne sroubu M6x14 + 2 matice
    n_roh = sum(1 for d_ in dd_["dily"] if d_["part_id"] == "product_3158")
    n_uhel = sum(1 for d_ in dd_["dily"] if d_["part_id"] == "product_3254")
    mat_ = sum(x["mnozstvi"] for x in k_["radky"] if "Ozubená matice M6" in x["nazev"])
    check(mat_ == 2 * (n_roh + n_uhel), f"{nazev_}: kusovnik ma {2 * (n_roh + n_uhel)} otocnych matic M6 (2 na kazdou spojku), je {mat_}")
    valc_ = sum(x["mnozstvi"] for x in k_["radky"] if "[2.1.21.0612]" in x["nazev"])                              # karta v katalogu, nebo radek "karta chybi" - SKU je v nazvu v obou pripadech
    zap_ = sum(x["mnozstvi"] for x in k_["radky"] if "zápustnou hlavou M6×14" in x["nazev"])                       # SKU zapustneho sroubu Robert nezadal: radek bez karty
    check(valc_ == 2 * n_roh and zap_ == 2 * n_uhel, f"{nazev_}: kusovnik ma {2 * n_roh} sroubu M6x12 [2.1.21.0612] a {2 * n_uhel} zapustnych M6x14 (je {valc_} / {zap_})")
    check(all(x["celkem"] == 0 for x in k_["radky"] if "karta chybí" in x["nazev"]), f"{nazev_}: polozky bez karty v katalogu jsou bez ceny a ve varovanich")
    check(any("Laminodeska" in x["nazev"] for x in k_["radky"]) and any("Profil" in x["nazev"] for x in k_["radky"]) and any("Spoje" in x["nazev"] for x in k_["prace"]), f"{nazev_}: kusovnik obsahuje desky, profily a spoje")
    check(sum(x["mnozstvi"] for x in k_["radky"] if "Profil 30x30" in x["nazev"]) + 0 > 0 and abs(sum(x["celkem"] for x in k_["prace"] if "Zaokrouhlení" in x["nazev"])) < 40 + 0.5 * sum(x["mnozstvi"] for x in k_["radky"] if "[2.1." in x["nazev"]),
          f"{nazev_}: zaokrouhlovaci radek je male cislo (jednotkove ceny drobneho spojovaciho materialu se zaokrouhluji na cele Kc: az 0,5 Kc na kus)")
    check(k_["hmotnost_kg"] and k_["hmotnost_kg"] > 5 and k_["montaz"]["czk"] > 0, f"{nazev_}: hmotnost a montaz ({k_['hmotnost_kg']}, {k_['montaz']})")
check(sum(1 for x in d2["cena"]["kusovnik"]["radky"] if "Profil 30x30" in x["nazev"]) >= 4 and d2["cena"]["kusovnik"]["celkem"]["bez_dph"] > d["cena"]["kusovnik"]["celkem"]["bez_dph"], "vetsi stul ma dražší kusovník")
# --- hloubka > 900: deska spodni police o 62 mm uzsi + podperny profil v kusovniku, cena sedi (Robert 2026-10-03) ---
r9 = client.get("/api/stul/konfigurace?hloubka=900&sirka=1200").get_json()
rK = client.get("/api/stul/konfigurace?hloubka=1000&sirka=1200").get_json()
kK = rK["cena"]["kusovnik"]
check(sum(x["celkem"] for x in kK["radky"]) + sum(x["celkem"] for x in kK["prace"]) == rK["cena"]["bez_dph"], "hloubka 1000: soucet kusovniku = cena bez DPH")
check(any("Laminodeska" in x["nazev"] and x["rozmer"] == "850 × 1138 mm" for x in kK["radky"]), f"hloubka 1000: deska police v kusovniku 850 x 1138 mm (o 62 mm uzsi): {[x['rozmer'] for x in kK['radky'] if 'Laminodeska' in x['nazev']]}")
check(any("Profil" in x["nazev"] and x["rozmer"] == "792 mm" and x["mnozstvi"] == 1 for x in kK["radky"]), "hloubka 1000: kusovnik ma 1 podpernu pricku 792 mm (mezi podelniky police)")
check(rK["cena"]["bez_dph"] > r9["cena"]["bez_dph"] and rK["cena"]["souhrn"]["joint_count"] > r9["cena"]["souhrn"]["joint_count"], "hloubka 1000 je dražší nez 900 (delsi profily, podpera, spoje)")
check(rK["info"] and rK["info"][0]["kod"] == "police_podpery" and r9["info"] == [], "informace police_podpery jen pri hloubce nad 900")
r3 = client.get("/api/stul/konfigurace?panely=0&led=0&elektrozlab=0&suplik=0&drzak_pet=0&police=0&kolecka=0")
d3 = r3.get_json()
check(d3["cena"]["bez_dph"] < c["bez_dph"], f"holy stul je levnejsi nez plne vybaveny ({d3['cena']['bez_dph']} < {c['bez_dph']})")

# --- loziskove jednotky: cena karty 3025 (neaktivni karta bez GLB, doplnena do ctx), jednotky zdrazuji konfiguraci ---
rl = client.get("/api/stul/konfigurace?loz=1&loz_rozteca=200&loz_okraj=100")
dl = rl.get_json()
check(rl.status_code == 200 and dl["loz"] and dl["loz"]["pocet"] == 24 and dl["cena"] is not None, f"cena s loziskovymi jednotkami se spocitala ({rl.status_code}, {dl.get('loz')}, {dl.get('cena') and dl['cena']['bez_dph']})")
d0 = client.get("/api/stul/konfigurace").get_json()
rozdil = dl["cena"]["bez_dph"] - d0["cena"]["bez_dph"] if dl.get("cena") and d0.get("cena") else None
check(rozdil is not None and 24 * 50 <= rozdil <= 24 * 70, f"24 jednotek po ~57 Kc (cena karty 3025) zdrazuje o {rozdil}")
rv = client.get("/api/stul/konfigurace?vyrez1=1&vyrez1_police=1")
dv = rv.get_json()
check(rv.status_code == 200 and not dv["problemy"] and dv["cena"]["bez_dph"] > d0["cena"]["bez_dph"], f"police pod vyrezem zdrazuje (profily, deska): {dv['cena']['bez_dph']} > {d0['cena']['bez_dph']}")
rvv = client.get("/api/stul/konfigurace?vyrez1=1")
check(abs(rvv.get_json()["cena"]["bez_dph"] - d0["cena"]["bez_dph"]) < 0.01, "samotny vyrez cenu nemeni (cena cele desky)")

# --- sikme vzpery ramen LED (Robert 2026-10-03): cena = profil vzpery (delka, rez) + 2 spojky 3254 + 2 spoje na vzperu; kusovnik drzi soucet; model/GLB; dotaz ---
d14 = client.get("/api/stul/konfigurace?sirka=1400").get_json()
rz = client.get("/api/stul/konfigurace?sirka=1400&vzpery=1&vzpera_delka=420")
dz = rz.get_json()
check(rz.status_code == 200 and dz["parametry"]["vzpery"] and not dz["problemy"] and dz["parametry"]["vzpera_delka"] == 420.0 and len(dz["dily"]) == len(d14["dily"]) + 6, f"vzpery: dotaz ?vzpery=1&vzpera_delka=420 ({rz.status_code}, {len(dz['dily'])} dilu)")
check(dz["pocet_spoju"] == d14["pocet_spoju"] + 4 and dz["cena"]["souhrn"]["joint_count"] == d14["cena"]["souhrn"]["joint_count"] + 4, f"vzpery: +4 spoje v poctu i v cene ({dz['pocet_spoju']}, {dz['cena']['souhrn']['joint_count']})")
check(dz["cena"]["bez_dph"] > d14["cena"]["bez_dph"], f"vzpery zdrazuji ({d14['cena']['bez_dph']} -> {dz['cena']['bez_dph']})")
kz = dz["cena"]["kusovnik"]
check(any("Spojka úhel 45° systém 30" in x["nazev"] and "2.2.001.08.3030.06" in x["nazev"] and x["mnozstvi"] == 4 for x in kz["radky"]), f"kusovnik: 4x Spojka uhel 45 systém 30 se SKU ({[x['nazev'][:40] + ' x' + str(x['mnozstvi']) for x in kz['radky'] if 'ojka' in x['nazev']]})")
check(any(x["rozmer"] == "420 mm" and x["mnozstvi"] == 2 and "Profil" in x["nazev"] for x in kz["radky"]), "kusovnik: 2x profil 420 mm (vzpery)")
check(sum(x["celkem"] for x in kz["radky"]) + sum(x["celkem"] for x in kz["prace"]) == dz["cena"]["bez_dph"] == kz["celkem"]["bez_dph"], "kusovnik se vzperami: soucet radku = cena bez DPH")
check(kz["hmotnost_kg"] > d14["cena"]["kusovnik"]["hmotnost_kg"], f"hmotnost se vzperami je vetsi ({d14['cena']['kusovnik']['hmotnost_kg']} -> {kz['hmotnost_kg']})")
check(dz["hash"] != d14["hash"] and "vzpery=1" in dz["model_url"] and "vzpera_delka=420" in dz["model_url"], "vzpery: jiny hash a model_url nese parametry")
check(any(c_["id"] == "vzpery" for c_ in dz["vodici"]["ovladani"]["casti"]) and dz["volby"]["vzpery"] is None, "vzpery: cast pro 3D ovladani a volba bez duvodu u sirky 1400")
rzz = client.get("/api/stul/konfigurace?sirka=1400&vzpery=1&vzpera_delka=1000")
jz = rzz.get_json()
check(rzz.status_code == 200 and jz["parametry"]["vzpery"] and jz["parametry"]["vzpera_delka"] == 630.0 and not jz["odebrano"] and not jz["problemy"], f"vzpery 1000 mm u ramene 560: orezano na nejvetsi platnou delku 630, vzpery zustavaji ({jz['parametry']['vzpera_delka']})")
check(jz["vzpera_meze"] == {"hodnota": 630.0, "min": 100.0, "max": 630.0, "vejde": True}, f"odpoved nese presne meze delky vzpery ({jz['vzpera_meze']})")
check(any(c_["id"] == "vzpery" and c_["menu"][1]["zakazano"] for c_ in jz["vodici"]["ovladani"]["casti"]), "3D nabidka: delsi vzpera zakazana na skutecne mezi")
check(dz["vzpera_meze"]["min"] == 100.0 and dz["vzpera_meze"]["max"] == 630.0 and client.get("/api/stul/konfigurace?sirka=1400").get_json()["vzpera_meze"] is None, "vzpera_meze: u zapnutych vzper 100-630, u vypnutych None")
check(client.get("/api/stul/konfigurace?vzpery=1&vzpera_delka=99").status_code == 400 and client.get("/api/stul/konfigurace?vzpery=1&vzpera_delka=1001").status_code == 400, "vzpera_delka mimo rozsah 100-1000: 400")
check(client.get("/api/stul/konfigurace?vzpery=zzz").status_code == 400, "neplatny prepinac vzpery: 400")
rg = client.get("/api/stul/model.glb?sirka=1400&vzpery=1&vzpera_delka=420")
check(rg.status_code == 200 and rg.data[:4] == b"glTF" and len(rg.data) > 1_000_000, f"model.glb se vzperami ({rg.status_code}, {len(rg.data)} B)")

# --- model GLB ---
r = anon.get("/api/stul/model.glb")
check(r.status_code in (401, 403), f"model bez prihlaseni odmitnut ({r.status_code})")
r = client.get("/api/stul/model.glb?sirka=1500")
check(r.status_code == 200 and r.mimetype == "model/gltf-binary" and r.data[:4] == b"glTF", f"model.glb: GLB ({r.status_code} {r.mimetype})")
check(r.headers.get("ETag") and r.headers.get("Content-Disposition") == "inline" and "private" in r.headers.get("Cache-Control", ""), "hlavicky ETag/inline/private")
check(len(r.data) > 1_000_000, f"model ma rozumnou velikost ({len(r.data)} B)")
import gzip as _gzip  # noqa: E402
rz = client.get("/api/stul/model.glb?sirka=1500", headers={"Accept-Encoding": "gzip"})
check(rz.status_code == 200 and rz.headers.get("Content-Encoding") == "gzip" and _gzip.decompress(rz.data) == r.data and len(rz.data) < 0.35 * len(r.data) and "Accept-Encoding" in rz.headers.get("Vary", ""),
      f"model.glb: gzip (Content-Encoding, po rozbaleni stejne bytes, Vary; {len(rz.data)} z {len(r.data)} B)")
check(rz.headers.get("ETag") != r.headers.get("ETag") and r.headers.get("Content-Encoding") is None, "model.glb: ETag komprimovane verze je jiny nez surove")
r = client.get("/api/stul/model.glb?sirka=100")
check(r.status_code == 400 and r.get_json().get("kod") == "mimo_rozsah", "model: mimo rozsah 400")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
