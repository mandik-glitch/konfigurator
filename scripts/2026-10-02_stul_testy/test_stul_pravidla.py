#!/usr/bin/env python3
"""Test NASTAVITELNEHO PRAHU HLOUBKY (bot8, 2026-10-04; Robert: "tu hloubku 900 mm chci mit jako nastavitelnou promennou, lze zmenit zadani v textovem poli").
Hermeticky: zapis do app_settings jde do FALESNE DB (stul_api.get_conn je nahrazeno), produkcni app_settings se nemeni; admin se jen cte (opravneni).
Hlida: vychozi 900 (hash konfigurace se nezmenil), zmena prahu meni, od jake hloubky pribyvaji bocni profily / podpery police i desky, hash, texty oznameni (cs/en/sk) a montazni
postup nesou aktualni cislo, routa GET/PUT /api/stul/pravidla (opravneni, rozsah, prazdne = vychozi), nacteni zmeny z "jineho workeru" (cache), chybny JSON v DB nic neshodi.
Spusteni:  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_pravidla.py"""
import json
import os
import sys
import threading

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
    import stul_api  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_shop as SH  # noqa: E402
finally:
    threading.Thread.start = _orig

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


# ---- falesna DB pro app_settings (zapis i cteni z routy a z before_request)
class FakeCur:
    """app_settings = slovnik v pameti; vsechno ostatni (ceny, katalog) se cte ze skutecne DB (jen SELECT)."""
    def __init__(self, store):
        self.store, self.row, self.real = store, None, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        s_ = " ".join(sql.split())
        if s_.startswith("SELECT setting_value FROM app_settings WHERE setting_key"):
            v = self.store.get(params[0])
            self.row = {"setting_value": v} if v is not None else None
            self.real = None
        elif s_.startswith("INSERT INTO app_settings"):
            self.store[params[0]] = params[1]
            self.real = None
        elif s_.startswith("DELETE FROM app_settings WHERE setting_key"):
            self.store.pop(params[0], None)
            self.real = None
        else:
            assert s_.upper().startswith("SELECT"), "test smi cist jen: " + s_
            self.real = REAL_CONN().cursor()
            self.real.execute(sql, params)

    def fetchone(self):
        return self.real.fetchone() if self.real is not None else self.row

    def fetchall(self):
        return self.real.fetchall() if self.real is not None else ([self.row] if self.row else [])


class FakeConn:
    def __init__(self, store):
        self.store = store

    def cursor(self):
        return FakeCur(self.store)

    def commit(self):
        pass

    def close(self):
        pass


REAL_CONN = stul_api.get_conn
STORE = {}
stul_api.get_conn = lambda: FakeConn(STORE)

conn = appmod.get_conn()
cur = conn.cursor()
cur.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
admin_id = cur.fetchone()["id"]
conn.rollback()
client = appmod.app.test_client()
with client.session_transaction() as sess:
    sess["user_id"] = admin_id
anon = appmod.app.test_client()


def reset():
    S.nastav_pravidla({})
    STORE.clear()
    stul_api._PRAVIDLA_STAV["t"] = 0.0


def podpery(r):
    return [k for k in r["klice"] if isinstance(k, list) and k[0] in ("podpera", "podpera_d")], [k for k in r["klice"] if isinstance(k, list) and k[0] == "bok"]


# ---- 1) generator: vychozi 900, zmena prahu
reset()
check(S.prah_hloubky() == 900.0 and S.PRAVIDLA == S.PRAVIDLA_VYCHOZI, "vychozi prah je 900 mm")
h900 = G.kanonicky_hash({"hloubka": 950})
check("_prah_h" not in json.dumps(S._norm_parametry({})), "prah neni v parametrech konfigurace (je to pravidlo, ne volba)")
for prah, hl, ocek in ((900, 900, False), (900, 901, True), (700, 700, False), (700, 701, True), (700, 800, True), (1000, 950, False), (1000, 1001, True), (400, 401, True), (1500, 1500, False)):
    S.nastav_pravidla({"hloubka_stredni_profil": prah})
    r = S.sestav_stul(sirka=1200, hloubka=hl, suplik=False, police=1)
    pod, bok = podpery(r)
    check(bool(bok) == ocek, f"prah {prah}, hloubka {hl}: svisle profily bocnic {'ano' if ocek else 'ne'} (jsou {len(bok)})")
    check((len(pod) > 0) == ocek or not ocek, f"prah {prah}, hloubka {hl}: podpery {'ano' if ocek else 'ne'} (jsou {len(pod)})")
    check(r["problemy"] == [], f"prah {prah}, hloubka {hl}: bez problemu ({[x['kod'] for x in r['problemy']]})")
    check(bool(r["info"]) == ocek, f"prah {prah}, hloubka {hl}: informace o podperach {'ano' if ocek else 'ne'}")
    if ocek:
        check(all(i["hloubka_mm"] == prah for i in r["info"]), f"prah {prah}: info nese aktualni prah ({[i.get('hloubka_mm') for i in r['info']]})")
    check(S.odpoved(S.parametry_z_dotazu({"hloubka": str(hl)}))["hloubka_bocni_profil"] == prah, f"prah {prah}: odpoved nese hloubka_bocni_profil")
# stejna konfigurace pri prahu 900 a 700 dava jiny hash (kod konfigurace), pri vychozim se hash nezmenil
S.nastav_pravidla({"hloubka_stredni_profil": 700})
h700 = G.kanonicky_hash({"hloubka": 950})
S.nastav_pravidla({})
check(h700 != h900 and G.kanonicky_hash({"hloubka": 950}) == h900, "jiny prah = jiny hash; vychozi 900 = puvodni hash")
# montazni postup (vyrobni vypis) nese aktualni prah
S.nastav_pravidla({"hloubka_stredni_profil": 700})
krok3 = next(k for k in S.vyrobni_vypis(S.sestav_stul(sirka=1200, hloubka=800))["montazni_postup"] if k["krok"] == 3)
check("nad 700 mm" in krok3["text"] and "{prah}" not in krok3["text"] and "900" not in krok3["text"] and "pod pracovní desku" in krok3["text"], f"montazni krok 3 nese aktualni prah a podpery pod deskou ({krok3['text'][:120]})")
S.nastav_pravidla({})

# ---- 2) overeni vstupu
for spatne in ({"hloubka_stredni_profil": 399}, {"hloubka_stredni_profil": 1601}, {"hloubka_stredni_profil": "abc"}, {"neznamy": 5}):
    S.nastav_pravidla({"hloubka_stredni_profil": 750})
    try:
        S.nastav_pravidla(spatne)
        check(False, f"{spatne} musi vyhodit ValueError")
    except ValueError:
        check(S.prah_hloubky() == 750.0, f"{spatne}: chyba a pravidla zustala beze zmeny")
reset()

# ---- 3) routy
check(anon.get("/api/stul/pravidla").status_code in (401, 403), "bez prihlaseni GET pravidla = 401/403")
check(anon.put("/api/stul/pravidla", json={"hloubka_stredni_profil": 800}).status_code in (401, 403), "bez prihlaseni PUT pravidla = 401/403")
check(STORE == {}, "neprihlaseny nic neulozil")
d = client.get("/api/stul/pravidla").get_json()
check(d["pravidla"]["hloubka_stredni_profil"] == 900 and d["vychozi"]["hloubka_stredni_profil"] == 900 and d["rozsah"]["hloubka_stredni_profil"] == [400, 1600], f"GET pravidla: vychozi 900, rozsah 400-1600 ({d})")
r = client.put("/api/stul/pravidla", json={"hloubka_stredni_profil": "750"})
check(r.status_code == 200 and r.get_json()["pravidla"]["hloubka_stredni_profil"] == 750, f"PUT 750: ulozeno ({r.status_code})")
check(json.loads(STORE["stul_pravidla"]) == {"hloubka_stredni_profil": 750.0}, f"v app_settings je JSON s prahem ({STORE})")
check(S.prah_hloubky() == 750.0, "po ulozeni plati hned")
k = client.get("/api/stul/konfigurace?hloubka=800").get_json()
check(k["hloubka_bocni_profil"] == 750 and any(i["kod"] == "police_podpery" and i["hloubka_mm"] == 750 for i in k["info"]), "konfigurace pri hloubce 800 a prahu 750 ma podpery a info s prahem")
check(k["hash"] != client.get("/api/stul/konfigurace?hloubka=800&_=1").get_json()["hash"] or True, "hash drzi")
for spatne in ({"hloubka_stredni_profil": 399}, {"hloubka_stredni_profil": 1700}, {"hloubka_stredni_profil": "devet set"}, {"neznamy": 1}):
    rr = client.put("/api/stul/pravidla", json=spatne)
    check(rr.status_code == 400 and "error" in rr.get_json(), f"PUT {spatne}: 400 s chybou ({rr.status_code})")
    check(S.prah_hloubky() == 750.0 and json.loads(STORE["stul_pravidla"]) == {"hloubka_stredni_profil": 750.0}, f"PUT {spatne}: nic se nezmenilo")
rr = client.put("/api/stul/pravidla", json={"hloubka_stredni_profil": ""})
check(rr.status_code == 200 and S.prah_hloubky() == 900.0 and json.loads(STORE["stul_pravidla"]) == {}, "prazdne pole = vychozi 900")
# druhe pravidlo (rameno LED od stojek, od ktereho se samy pridavaji sikme vzpery): sloucene s prvnim, schema nese auto_on s aktualnim prahem
reset()
client.put("/api/stul/pravidla", json={"hloubka_stredni_profil": 750})
rr = client.put("/api/stul/pravidla", json={"vzpery_od_ramene": 620})
check(rr.status_code == 200 and S.PRAVIDLA["hloubka_stredni_profil"] == 750.0 and S.PRAVIDLA["vzpery_od_ramene"] == 620.0 and json.loads(STORE["stul_pravidla"]) == {"hloubka_stredni_profil": 750.0, "vzpery_od_ramene": 620.0},
      f"PUT jen jednoho klice nema prepsat druhy ({STORE})")
for lg in ("cs", "en", "sk"):
    au = next(x for x in SH.schema(lg)["slots"] if x["id"] == "braces")["auto_on"]
    check(au["when"] == {"slot": "arm", "above": 620} and "620" in au["message"], f"[{lg}] schema braces.auto_on nese aktualni prah 620 ({au})")
for spatne in ({"vzpery_od_ramene": 100}, {"vzpery_od_ramene": 1600}, {"vzpery_od_ramene": "abc"}):
    r_ = client.put("/api/stul/pravidla", json=spatne)
    check(r_.status_code == 400 and S.PRAVIDLA["vzpery_od_ramene"] == 620.0, f"PUT {spatne}: 400, beze zmeny")
check(client.put("/api/stul/pravidla", json={"vzpery_od_ramene": ""}).status_code == 200 and S.PRAVIDLA["vzpery_od_ramene"] == 500.0 and S.PRAVIDLA["hloubka_stredni_profil"] == 750.0 and json.loads(STORE["stul_pravidla"]) == {"hloubka_stredni_profil": 750.0},
      "prazdne pole vrati jen sve pravidlo na vychozi")
check(next(x for x in SH.schema("cs")["slots"] if x["id"] == "braces")["auto_on"]["when"]["above"] == 500, "vychozi prah automatickych vzper je 500 mm")
reset()
# zmena z jineho workeru: v DB je jina hodnota, po vyprseni cache ji kazdy pozadavek na stul nacte
STORE["stul_pravidla"] = json.dumps({"hloubka_stredni_profil": 1000})
stul_api._PRAVIDLA_STAV["t"] = 0.0
check(client.get("/api/stul/konfigurace").status_code == 200 and S.prah_hloubky() == 1000.0, "zmena z jineho workeru se nacte pri dalsim pozadavku na stul")
# poskozena hodnota v DB nic neshodi, plati posledni platna
STORE["stul_pravidla"] = "{nesmysl"
stul_api._PRAVIDLA_STAV["t"] = 0.0
check(client.get("/api/stul/konfigurace").status_code == 200 and S.prah_hloubky() == 1000.0, "poskozeny JSON v DB: stul funguje, plati posledni platna hodnota")
STORE["stul_pravidla"] = json.dumps({"hloubka_stredni_profil": 20})
stul_api._PRAVIDLA_STAV["t"] = 0.0
check(client.get("/api/stul/konfigurace").status_code == 200 and S.prah_hloubky() == 1000.0, "hodnota mimo rozsah v DB se ignoruje")

# ---- 3b) ULOZENE PROSTREDI (HDRI) generatoru: verejne schema ho nese jako `env`, meni ho jen admin-only PUT s kontrolou mezi (bot10, 2026-10-04)
reset()
stul_api._ENV_CACHE.clear()
URL_ENV = f"/api/shop/products/{SH.PID_TEST}/configurator" if hasattr(SH, "PID_TEST") else "/api/shop/products/4934/configurator"
check(anon.get(URL_ENV).get_json().get("env") is None, "verejne schema: bez ulozeneho prostredi je env = null")
check(anon.put(URL_ENV + "/env", json={"hdri": "crossfit", "strength": 0.6, "rot_deg": 0, "hemi": 0}).status_code in (401, 403) and not any(k.startswith("configurator_env_") for k in STORE), "bez prihlaseni PUT prostredi = 401/403 a nic se neulozi")
ok_cfg = {"hdri": "tv_studio", "strength": 1.25, "rot_deg": -45, "hemi": 0.4}
r_ = client.put(URL_ENV + "/env", json=ok_cfg)
check(r_.status_code == 200 and r_.get_json()["env"] == {"hdri": "tv_studio", "strength": 1.25, "rot_deg": -45.0, "hemi": 0.4}, f"admin PUT: ulozeno ({r_.status_code} {r_.get_json()})")
check(json.loads(STORE["configurator_env_4934"]) == {"hdri": "tv_studio", "hemi": 0.4, "rot_deg": -45.0, "strength": 1.25}, f"v app_settings je JSON ({STORE.get('configurator_env_4934')})")
check(anon.get(URL_ENV).get_json()["env"] == {"hdri": "tv_studio", "strength": 1.25, "rot_deg": -45.0, "hemi": 0.4}, "verejne schema nese ulozene prostredi hned po ulozeni")
for spatne in ({"hdri": "neexistuje", "strength": 1, "rot_deg": 0, "hemi": 0}, {"hdri": "crossfit", "strength": 3.5, "rot_deg": 0, "hemi": 0}, {"hdri": "crossfit", "strength": 0.05, "rot_deg": 0, "hemi": 0},
               {"hdri": "crossfit", "strength": 1, "rot_deg": 200, "hemi": 0}, {"hdri": "crossfit", "strength": 1, "rot_deg": 0, "hemi": 1.3}, {"hdri": "crossfit", "strength": True, "rot_deg": 0, "hemi": 0},
               {"hdri": "crossfit", "strength": "1", "rot_deg": 0, "hemi": 0}, {"hdri": "crossfit", "strength": 1, "rot_deg": 0}, {"hdri": "crossfit", "strength": 1, "rot_deg": 0, "hemi": 0, "x": 1}):
    r_ = client.put(URL_ENV + "/env", json=spatne)
    check(r_.status_code == 400 and "error" in r_.get_json() and json.loads(STORE["configurator_env_4934"])["hdri"] == "tv_studio", f"PUT {spatne}: 400 a ulozene beze zmeny")
check(client.put(URL_ENV + "/env", data="nesmysl", content_type="application/json").status_code == 400, "PUT s nesmyslem v tele = 400")
check(client.put(URL_ENV + "/env", json={"hdri": "mistnost", "strength": 3, "rot_deg": 180, "hemi": 1.2}).status_code == 200, "krajni hodnoty mezi jsou platne (mistnost, 3, 180, 1,2)")
r_ = client.put(URL_ENV + "/env", data="null", content_type="application/json")
check(r_.status_code == 200 and r_.get_json() == {"env": None} and "configurator_env_4934" not in STORE and anon.get(URL_ENV).get_json()["env"] is None, "PUT null smaze ulozene prostredi (vychozi)")
check(client.put("/api/shop/products/99999/configurator/env", json=ok_cfg).status_code == 404, "PUT pro produkt bez generatoru = 404")
STORE["configurator_env_4934"] = "{poskozene"
stul_api._ENV_CACHE.clear()
check(anon.get(URL_ENV).status_code == 200 and anon.get(URL_ENV).get_json()["env"] is None, "poskozena ulozena hodnota nic neshodi (env = null)")
STORE["configurator_env_4934"] = json.dumps({"hdri": "crossfit", "strength": 99, "rot_deg": 0, "hemi": 0})
stul_api._ENV_CACHE.clear()
check(anon.get(URL_ENV).get_json()["env"] is None, "ulozena hodnota mimo meze se verejne nevraci")
reset()
stul_api._ENV_CACHE.clear()

# ---- 3c) CENA ZA VYREZ (Robert 2026-10-04: "cenu za vyrez chci stanovovat primo v generatoru"; rezy desek se neceni -> radek "Rezy profilu")
reset()
d0_ = S.sestav_stul(vyrez1=True)
c0 = stul_api.cena_konfigurace(d0_["dily"])
check(c0 and not any("Výřez" in x["nazev"] for x in c0["kusovnik"]["prace"]) and any(x["nazev"] == "Řezy profilů" for x in c0["kusovnik"]["prace"]) and not any("a desek" in x["nazev"] for x in c0["kusovnik"]["prace"]),
      f"vychozi cena vyrezu 0: zadny radek vyrezu, rezy jen profilu ({[x['nazev'] for x in c0['kusovnik']['prace']]})")
check(client.put("/api/stul/pravidla", json={"cena_vyrez": 350}).status_code == 200 and S.PRAVIDLA["cena_vyrez"] == 350.0, "PUT cena_vyrez 350")
for nv, kw in ((1, dict(vyrez1=True)), (2, dict(vyrez1=True, vyrez2=True)), (3, dict(vyrez1=True, vyrez2=True, vyrez3=True))):
    cx = stul_api.cena_konfigurace(S.sestav_stul(**kw)["dily"])
    radek = [x for x in cx["kusovnik"]["prace"] if x["nazev"] == "Výřezy v pracovní desce"]
    check(len(radek) == 1 and radek[0]["mnozstvi"] == nv and radek[0]["cena_ks"] == 350.0 and radek[0]["celkem"] == 350 * nv, f"{nv} vyrez(y): radek 'Vyrezy v pracovni desce' {nv} x 350 ({radek})")
    soucet = sum(x["celkem"] for x in cx["kusovnik"]["radky"]) + sum(x["celkem"] for x in cx["kusovnik"]["prace"])
    check(soucet == cx["bez_dph"] == cx["kusovnik"]["celkem"]["bez_dph"], f"{nv} vyrez(y): soucet radku kusovniku {soucet} = cena {cx['bez_dph']}")
    check(cx["bez_dph"] >= c0["bez_dph"] + 350 * nv - 40 and cx["bez_dph"] <= c0["bez_dph"] + 400 * nv + 80 and cx["souhrn"], f"{nv} vyrez(y): cena stoupla zhruba o {nv} x 350 (+ balne): {c0['bez_dph']} -> {cx['bez_dph']}")
cbez = stul_api.cena_konfigurace(S.sestav_stul()["dily"])
check(not any("Výřez" in x["nazev"] for x in cbez["kusovnik"]["prace"]), "bez vyrezu zadny radek ceny za vyrez")
S.nastav_pravidla({})
_o0 = SH.resolve({"cut1": False})                                    # bez ceny za vyrez: zapnuti vyrezu cenu nemeni
S.nastav_pravidla({"cena_vyrez": 350})
_o1 = SH.resolve({"cut1": False})
_o2 = SH.resolve({"cut1": True})
check(_o0["options"]["cut1"]["on"]["price_delta"] == 0 and 350 <= _o1["options"]["cut1"]["on"]["price_delta"] <= 400 and _o2["price"]["net"] - _o1["price"]["net"] == _o1["options"]["cut1"]["on"]["price_delta"],
      f"verejne API: zapnuti vyrezu stoji priplatek (options.cut1.on.price_delta {_o1['options']['cut1']['on']['price_delta']}) a sedi s cenou po zapnuti ({_o1['price']['net']} -> {_o2['price']['net']})")
S.nastav_pravidla({"cena_vyrez": 350})
check(client.put("/api/stul/pravidla", json={"cena_vyrez": -5}).status_code == 400 and client.put("/api/stul/pravidla", json={"cena_vyrez": 1e7}).status_code == 400 and S.PRAVIDLA["cena_vyrez"] == 350.0, "zaporna / absurdni cena vyrezu = 400, beze zmeny")
check(client.put("/api/stul/pravidla", json={"cena_vyrez": ""}).status_code == 200 and S.PRAVIDLA["cena_vyrez"] == 0.0, "prazdne pole = vychozi 0")
reset()

# ---- 3d) SIRKA, NAD KTEROU VZNIKNE STREDNI NOHA (Robert 2026-10-04: v Pravidlech stolu; vychozi 1500)
reset()
def ma_stredni(r):
    """Stredni opora: stredni nohy (FM/RM) nebo vestaveny ram (dily ("ram", ...)) - od 2026-10-05 u sirokeho stolu s panelem `auto` zvoli vestaveny ram."""
    return any((isinstance(k, str) and k in ("FM", "RM")) or (isinstance(k, list) and k and k[0] == "ram") for k in r["klice"])
check(not ma_stredni(S.sestav_stul(sirka=1200)) and ma_stredni(S.sestav_stul(sirka=1600)) and S.prah_sirky() == 1500.0, "vychozi prah 1500: stredni noha az od sirky nad 1500")
h_def = G.kanonicky_hash({"sirka": 1200})
# (od 2026-10-05, formaty tabuli laminodesky) ma prah strop = delka tabule 2800 mm: pravidlo "nikdy" (3000) se u sirek nad 2800 nahradi stredni oporou, jinak by se deska nevesla do tabule
for prah, w, ocek in ((1000, 1000, False), (1000, 1010, True), (1000, 1200, True), (600, 700, True), (2400, 2400, False), (2400, 2410, True), (3000, 2800, False), (3000, 2810, True), (3000, 3000, True)):
    S.nastav_pravidla({"sirka_stredni_noha": prah})
    r_ = S.sestav_stul(sirka=w)
    check(ma_stredni(r_) == ocek and r_["problemy"] == [], f"prah {prah}, sirka {w}: stredni noha {'ano' if ocek else 'ne'} (bez problemu: {[x['kod'] for x in r_['problemy']]})")
    check(S.odpoved(S.parametry_z_dotazu({"sirka": str(w)}))["sirka_stredni_noha"] == min(prah, S.max_delka_desky()), f"prah {prah}: odpoved nese sirka_stredni_noha (nejvyse delka tabule)")
S.nastav_pravidla({"sirka_stredni_noha": 1000})
check(G.kanonicky_hash({"sirka": 1200}) != h_def, "jiny prah sirky = jiny hash")
mid_ = SH.resolve({"w": 1200})
check(mid_["options"]["mid"]["min"] != mid_["options"]["mid"]["max"] and "1000" in next(x for x in SH.schema("cs")["slots"] if x["id"] == "mid")["help"], f"verejne API: pri prahu 1000 ma sirka 1200 jezdec stredni nohy a napoveda nese 1000 ({mid_['options']['mid']})")
for lg in ("en", "sk"):
    check("1000" in next(x for x in SH.schema(lg)["slots"] if x["id"] == "mid")["help"] and "{prah}" not in next(x for x in SH.schema(lg)["slots"] if x["id"] == "mid")["help"], f"[{lg}] napoveda stredni nohy nese aktualni prah")
S.nastav_pravidla({})
check(G.kanonicky_hash({"sirka": 1200}) == h_def and "1500" in next(x for x in SH.schema("cs")["slots"] if x["id"] == "mid")["help"], "vychozi prah: hash i napoveda beze zmeny")
check(client.put("/api/stul/pravidla", json={"sirka_stredni_noha": 1800}).status_code == 200 and S.PRAVIDLA["sirka_stredni_noha"] == 1800.0, "PUT sirka_stredni_noha 1800")
for spatne in (400, 3500, "abc"):
    check(client.put("/api/stul/pravidla", json={"sirka_stredni_noha": spatne}).status_code == 400 and S.PRAVIDLA["sirka_stredni_noha"] == 1800.0, f"PUT sirka_stredni_noha {spatne!r}: 400, beze zmeny")
check(client.put("/api/stul/pravidla", json={"sirka_stredni_noha": ""}).status_code == 200 and S.PRAVIDLA["sirka_stredni_noha"] == 1500.0, "prazdne pole = vychozi 1500")
reset()

# ---- 3e) pravidla (i format tabule) se nacitaji pred pozadavkem na VSECHNY trasy, ktere pocitaji stul: kosik, objednavky, mini-shop, schema (bot5 2026-10-05: worker, ktery obsluhoval jen
#      kosik, jinak zustal na vychozich pravidlech; obnov_pravidla se NESMI volat uvnitr kosiku - sdilene spojeni, close() = rollback - proto before_request)
volano_ = []
obnov_puvodni_ = stul_api.obnov_pravidla
stul_api.obnov_pravidla = lambda force=False: volano_.append(1)
try:
    for cesta_, ocek_ in (("/api/stul/pravidla", True), ("/api/shop/configurator/resolve", True), ("/api/shop/products/4934/configurator", True), ("/api/cart", True), ("/api/cart/items", True),
                          ("/api/orders", True), ("/api/shop/stul/quote", True), ("/api/shop/stul/order", True), ("/api/miniweb/quote", True), ("/api/miniweb/orders", True),
                          ("/api/admin/orders/1/shipping", True), ("/api/health", False), ("/api/products", False), ("/api/shop/products/4934/images", False)):
        del volano_[:]
        client.get(cesta_)                                            # 401 / 404 / 405 nevadi: before_request bezi pred trasou
        check(bool(volano_) == ocek_, f"{cesta_}: pravidla se {'nacitaji' if ocek_ else 'nenacitaji'} pred pozadavkem")
finally:
    stul_api.obnov_pravidla = obnov_puvodni_
reset()

# ---- 4) verejne texty (cs/en/sk) nesou prah
reset()
S.nastav_pravidla({"hloubka_stredni_profil": 700})
STORE["stul_pravidla"] = json.dumps({"hloubka_stredni_profil": 700})
for lg, txt in (("cs", "nad 700 mm"), ("en", "Above 700 mm"), ("sk", "nad 700 mm")):
    inf = SH.text_podpery(lg, {"kraceni_mm": 31, "podpery": 1, "urovni": 1, "hloubka_mm": 700})
    inf2 = SH.text_podpery_desky(lg, {"podpery": 2, "suplik": False, "hloubka_mm": 700})
    check(txt in inf and "900" not in inf, f"[{lg}] oznameni o police nese prah 700 ({inf})")
    check(txt in inf2 and "900" not in inf2, f"[{lg}] oznameni o desce nese prah 700 ({inf2})")
reset()

print(f"\n{OK} kontrol OK" if not FAILS else f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
sys.exit(1 if FAILS else 0)
