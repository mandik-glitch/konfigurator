#!/usr/bin/env python3
"""Test PRAVIDEL STOLU PO SYSTEMECH 30 / 35 / 40 + jen pro admina (bot8, 2026-10-05; Robert: "pravidla stolu konkretni hodnoty chci mit nastavitelne pro jednotlive systemy zvlast, 30/35/40,
kazdemu zadam individualne; tyto pravidla vidi jen admin"). Hermeticky jako test_stul_pravidla.py: zapis do app_settings jde do FALESNE DB (stul_api.get_conn je nahrazeno), produkcni app_settings
se nemeni; uzivatele (admin, nepravy staff) se jen ctou.
Hlida:
  A) generator: kazdy system ma vlastni sadu (PRAVIDLA_SYSTEMU), pohled PRAVIDLA patri aktivnimu systemu, nastav_pravidla(system=...) meni jen jeden, bez `system` vsechny (stare chovani),
     nastav_pravidla_po_systemech je atomicke, neplatne hodnoty = ValueError a beze zmeny,
  B) chovani: prah hloubky (svisle profily bocnic, podpery) a prah sirky (stredni nohy) plati JEN pro svuj system; odpoved nese prah systemu; vyrobni postup nese prah systemu,
  C) hash: prah systemu meni hash JEN konfigurace tohoto systemu; vychozi hodnoty hash nemeni,
  D) cena: cena vyrezu a navleku je pravidlo systemu (system se pozna z dilu sestavy),
  E) API: GET / PUT /api/stul/pravidla JEN ADMIN (bez prihlaseni 401, ne-admin 403, i kdyz ma pravo nastaveni), po systemech (PUT {system, pravidla}), plochy tvar jen kdyz maji vsechny systemy
     stejna pravidla (jinak 409 a nic se nezmeni), ulozeni plochy (stejne) / po systemech (ruzne), nacteni stareho plocheho JSON do vsech systemu, neplatny system / klic / hodnota = 400,
  F) verejne API (stul_shop): prahy, vzpery a cena vyrezu podle SYSTEMU produktu, hash a cache `resolve` nemichaji systemy.
Spusteni:  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_pravidla_systemy.py"""
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
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))          # STUL_API_OVERRIDE = izolovana kopie api/ (mutacni zkouska testu)
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


class FakeCur:
    """app_settings = slovnik v pameti; vsechno ostatni (ceny, katalog, uzivatele) se cte ze skutecne DB (jen SELECT)."""
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
cur.execute("SELECT id, role FROM app_users WHERE role IN ('manager', 'monter', 'skladnik', 'ucetni') AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")          # staff role s pristupem do generatoru (@staff_required), ale NE admin
staff_row = cur.fetchone()
conn.rollback()
client = appmod.app.test_client()
with client.session_transaction() as sess:
    sess["user_id"] = admin_id
anon = appmod.app.test_client()
staff = appmod.app.test_client()
if staff_row:
    with staff.session_transaction() as sess:
        sess["user_id"] = staff_row["id"]

SYSTEMY = tuple(S.SYSTEMY)                    # vsechny systemy (30, 35, 40, 41 = SSE od 2026-10-05)
STARE = tuple(S.SYSTEMY_PLOCHA)                # systemy 30 / 35 / 40: sdileji "plochy" tvar pravidel a jejich chovani popisuji bloky nize; SSE ma vlastni test (scripts/2026-10-05_sse)
V = S.PRAVIDLA_VYCHOZI


def reset():
    S.nastav_pravidla({})
    STORE.clear()
    stul_api._PRAVIDLA_STAV["t"] = 0.0


def bok_profily(r):
    return [k for k in r["klice"] if isinstance(k, list) and k[0] == "bok"]


def stredni_nohy(r):
    return [k for k in r["klice"] if k in ("FM", "RM")]


print("A) generator: sady po systemech")
reset()
check(set(S.PRAVIDLA_SYSTEMU) == set(SYSTEMY) and all(S.PRAVIDLA_SYSTEMU[x] == S.pravidla_vychozi(x) for x in SYSTEMY) and all(S.PRAVIDLA_SYSTEMU[x] == V for x in STARE)
      and S.pravidla_vychozi(41)["sirka_stredni_noha"] == 2000.0, "kazdy system ma vlastni sadu s vychozimi hodnotami (SSE: stredni noha od 2000 mm)")
check(all(S.PRAVIDLA_SYSTEMU[a] is not S.PRAVIDLA_SYSTEMU[b] for a in SYSTEMY for b in SYSTEMY if a != b), "sady systemu jsou ruzne objekty")
S.nastav_pravidla({"hloubka_stredni_profil": 700, "cena_vyrez": 3000}, system=35)
check(S.pravidlo("hloubka_stredni_profil", 35) == 700.0 and S.pravidlo("cena_vyrez", 35) == 3000.0 and S.pravidlo("hloubka_stredni_profil", 30) == 900.0 and S.pravidlo("hloubka_stredni_profil", 40) == 900.0,
      "nastav_pravidla(system=35) zmeni jen system 35")
check(S.prah_hloubky(35) == 700.0 and S.prah_hloubky(30) == 900.0 and S.prah_hloubky() == 900.0, "prah_hloubky(system); bez systemu a mimo kontext plati system 30")
with S._v_systemu(35):
    check(S.PRAVIDLA["hloubka_stredni_profil"] == 700.0 and S.prah_hloubky() == 700.0 and dict(S.PRAVIDLA) == S.pravidla_systemu(35) and S.PRAVIDLA.get("cena_vyrez") == 3000.0, "v kontextu systemu 35 ukazuje PRAVIDLA sadu systemu 35")
with S._v_systemu(40):
    check(S.PRAVIDLA == S.PRAVIDLA_VYCHOZI and S.prah_hloubky() == 900.0, "v kontextu systemu 40 vychozi sada")
check(S.PRAVIDLA == S.PRAVIDLA_VYCHOZI, "mimo kontext = sada systemu 30 (vychozi)")
S.nastav_pravidla({"sirka_stredni_noha": 1800})                                    # bez system = vsem (stare chovani)
check(all(S.prah_sirky(x) == 1800.0 for x in SYSTEMY) and S.pravidlo("hloubka_stredni_profil", 35) == 900.0, "nastav_pravidla bez systemu: vsem systemum, ostatni klice vychozi (jako dosud)")
S.nastav_pravidla_po_systemech({30: {"sirka_stredni_noha": 1200}, 40: {"hloubka_stredni_profil": 1000}})
check(S.prah_sirky(30) == 1200.0 and S.prah_sirky(35) == V["sirka_stredni_noha"] and S.prah_hloubky(40) == 1000.0 and S.prah_hloubky(30) == 900.0, "po_systemech: system, ktery chybi (35), dostane vychozi hodnoty")
pred = {x: S.pravidla_systemu(x) for x in SYSTEMY}
for spatne in ({30: {"cena_vyrez": 5}, 35: {"hloubka_stredni_profil": 399}}, {30: {"neznamy": 1}}, {36: {"cena_vyrez": 5}}, {"abc": {}}):
    try:
        S.nastav_pravidla_po_systemech(spatne)
        check(False, f"{spatne}: musi vyhodit ValueError")
    except ValueError:
        check({x: S.pravidla_systemu(x) for x in SYSTEMY} == pred, f"{spatne}: chyba a NIC se nezmenilo (atomicke)")
for spatne, kw in (({"hloubka_stredni_profil": 399}, {"system": 35}), ({"neznamy": 5}, {"system": 40}), ({"cena_vyrez": "x"}, {}), ({"cena_vyrez": 5}, {"system": 36})):
    try:
        S.nastav_pravidla(spatne, **kw)
        check(False, f"{spatne} {kw}: musi vyhodit chybu")
    except (ValueError, S.StulChyba):
        check({x: S.pravidla_systemu(x) for x in SYSTEMY} == pred, f"{spatne} {kw}: chyba a beze zmeny")
check(S.system_z_dilu(S.sestav_stul(system=35)["dily"]) == 35 and S.system_z_dilu(S.sestav_stul(system=40)["dily"]) == 40 and S.system_z_dilu(S.sestav_stul()["dily"]) == 30, "system_z_dilu pozna system sestavy")

print("B) chovani: prahy plati jen pro svuj system")
reset()
S.nastav_pravidla({"hloubka_stredni_profil": 700}, system=35)
for sy in STARE:
    r = S.sestav_stul(system=sy, sirka=1200, hloubka=800, suplik=False, police=1)
    check(bool(bok_profily(r)) == (sy == 35), f"prah hloubky 700 jen v systemu 35: system {sy}, hloubka 800 -> svisle profily bocnic {'ano' if bok_profily(r) else 'ne'}")
    check(all(i["hloubka_mm"] == (700 if sy == 35 else 900) for i in r["info"]), f"system {sy}: informace o podperach nese prah systemu ({[i.get('hloubka_mm') for i in r['info']]})")
    check(S.odpoved(S.parametry_z_dotazu({"system": str(sy), "hloubka": "800"}))["hloubka_bocni_profil"] == (700 if sy == 35 else 900), f"system {sy}: odpoved nese prah hloubky systemu")
krok35 = next(k for k in S.vyrobni_vypis(S.sestav_stul(system=35, hloubka=800))["montazni_postup"] if k["krok"] == 3)["text"]
krok30 = next(k for k in S.vyrobni_vypis(S.sestav_stul(system=30, hloubka=800))["montazni_postup"] if k["krok"] == 3)["text"]
check("700" in krok35 and "900" not in krok35 and "{prah}" not in krok35, "montazni postup systemu 35 nese prah 700")
check("700" not in krok30, "montazni postup systemu 30 nese vychozi prah (beze zmeny)")
reset()
S.nastav_pravidla({"sirka_stredni_noha": 1200}, system=40)
for sy in STARE:
    r = S.sestav_stul(system=sy, sirka=1300, panely=False, led=False, stojky=False, suplik=False)
    check(bool(stredni_nohy(r)) == (sy == 40), f"prah sirky 1200 jen v systemu 40: system {sy}, sirka 1300 -> stredni nohy {'ano' if stredni_nohy(r) else 'ne'}")
    check(S.odpoved(S.parametry_z_dotazu({"system": str(sy), "sirka": "1300"}))["sirka_stredni_noha"] == (1200 if sy == 40 else 1500), f"system {sy}: odpoved nese prah sirky systemu")
reset()

print("C) hash")
h = {sy: G.kanonicky_hash({"system": sy, "hloubka": 800, "sirka": 1300}) for sy in SYSTEMY}
check(len(set(h.values())) == len(SYSTEMY), "kazdy system = jiny hash (jako dosud)")
for klic_, hodn_ in (("hloubka_stredni_profil", 700), ("sirka_stredni_noha", 1200)):          # kazdy prah zvlast (jinak by jeden zakryl druhy)
    S.nastav_pravidla({klic_: hodn_}, system=35)
    h2 = {sy: G.kanonicky_hash({"system": sy, "hloubka": 800, "sirka": 1300}) for sy in SYSTEMY}
    check(h2[35] != h[35] and h2[30] == h[30] and h2[40] == h[40], f"{klic_} = {hodn_} v systemu 35 zmeni hash JEN konfigurace systemu 35")
    S.nastav_pravidla({klic_: hodn_}, system=40)
    h3 = {sy: G.kanonicky_hash({"system": sy, "hloubka": 800, "sirka": 1300}) for sy in SYSTEMY}
    check(h3[40] != h[40] and h3[30] == h[30], f"{klic_} = {hodn_} v systemu 40 zmeni hash konfigurace systemu 40, ne 30")
    S.nastav_pravidla({}, system=35)
    S.nastav_pravidla({}, system=40)
S.nastav_pravidla({"hloubka_stredni_profil": 900, "sirka_stredni_noha": 1500, "cena_vyrez": 777, "vzpery_od_ramene": 600}, system=35)
check({sy: G.kanonicky_hash({"system": sy, "hloubka": 800, "sirka": 1300}) for sy in SYSTEMY} == h, "cena vyrezu a vzper hash nemeni; vychozi prahy = puvodni hash")
check(G.kanonicky_hash({}) == "87a80526a7ae21aa" or S.aktivni_system() != 30, "hash vychoziho stolu systemu 30 beze zmeny")
reset()

print("D) cena: pravidla ceny jsou po systemech")
reset()
S.nastav_pravidla({"cena_vyrez": 2800}, system=30)
S.nastav_pravidla({"cena_vyrez": 3500, "cena_navlek_200": 400, "cena_navlek_400": 800}, system=35)
S.nastav_pravidla({"cena_vyrez": 4100}, system=40)
for sy, cena in ((30, 2800), (35, 3500), (40, 4100)):
    d = S.sestav_stul(system=sy, sirka=1600, vyrez1=True)["dily"]
    ex = [x for x in stul_api.extra_prace(d) if "Výřez" in x["name"]]
    check(len(ex) == 1 and ex[0]["unit_czk"] == cena and ex[0]["qty"] == 1, f"system {sy}: cena vyrezu {cena} Kc (je {[(x['qty'], x['unit_czk']) for x in ex]})")
    cena_s = stul_api.cena_konfigurace(d)
    cena_b = stul_api.cena_konfigurace(S.sestav_stul(system=sy, sirka=1600)["dily"])
    check(cena_s and cena_b and abs((cena_s["bez_dph"] - cena_b["bez_dph"]) - cena) < 200 and cena_s["bez_dph"] > cena_b["bez_dph"], f"system {sy}: cena konfigurace s vyrezem je vyssi o ~{cena} Kc ({cena_s and cena_b and round(cena_s['bez_dph'] - cena_b['bez_dph'])})")
dn = S.sestav_stul(system=35, navlek=True, navlek_delka=300.0)["dily"]
nv = [x for x in stul_api.extra_prace(dn) if "Návlek" in x["name"]]
check(nv and abs(nv[0]["unit_czk"] - round(400 + (800 - 400) * (300 - 200) / 200.0, 2)) < 0.01, f"navlek 300 mm v systemu 35: linearne mezi 400 a 800 Kc ({nv and nv[0]['unit_czk']})")
check(stul_api.cena_navleku(300, 35) == 600.0 and stul_api.cena_navleku(300, 30) == round(370 + (550 - 370) * 100 / 200.0, 2), "cena_navleku(delka, system): kazdy system svoje ceny")
reset()

print("E) API: jen admin, po systemech")
reset()
check(anon.get("/api/stul/pravidla").status_code == 401 and anon.put("/api/stul/pravidla", json={"system": 35, "pravidla": {"cena_vyrez": 5}}).status_code == 401, "bez prihlaseni GET i PUT = 401")
if staff_row:
    g_ = staff.get("/api/stul/pravidla")
    p_ = staff.put("/api/stul/pravidla", json={"system": 35, "pravidla": {"cena_vyrez": 5}})
    check(g_.status_code == 403 and p_.status_code == 403, f"prihlaseny NE-admin (role {staff_row['role']}) nesmi GET ani PUT ({g_.status_code}, {p_.status_code})")
else:
    print("   (v DB neni zadny aktivni ne-admin staff: kontrola 403 preskocena)")
check(STORE == {} and S.PRAVIDLA_SYSTEMU[35]["cena_vyrez"] == 0.0, "neprihlaseny ani ne-admin nic neulozil")
d = client.get("/api/stul/pravidla").get_json()
check(set(d["systemy"]) == {"30", "35", "40", "41", "45"} and d["navlek_systemy"] == [35] and d["sse_systemy"] == [41] and d["vychozi_systemu"]["41"]["sirka_stredni_noha"] == 2000.0 and d["vychozi"] == V and "hloubka_stredni_profil" in d["rozsah"] and d["system"] == 30 and d["pravidla"] == V,
      f"GET: pravidla (plochy, system 30), systemy, navlek_systemy, vychozi, rozsah ({sorted(d)})")
d35 = client.get("/api/stul/pravidla?system=35").get_json()
check(d35["system"] == 35 and d35["pravidla"] == d35["systemy"]["35"], "GET ?system=35: plochy `pravidla` patri systemu 35")
check(client.get("/api/stul/pravidla?system=36").status_code == 400, "GET ?system=36 = 400")
r = client.put("/api/stul/pravidla", json={"system": 35, "pravidla": {"hloubka_stredni_profil": "750", "cena_navlek_200": 410}})
j = r.get_json()
check(r.status_code == 200 and j["systemy"]["35"]["hloubka_stredni_profil"] == 750 and j["systemy"]["35"]["cena_navlek_200"] == 410 and j["systemy"]["30"]["hloubka_stredni_profil"] == 900 and j["systemy"]["40"]["hloubka_stredni_profil"] == 900 and j["system"] == 35,
      f"PUT {{system 35}}: ulozeno jen pro 35 ({r.status_code})")
check(json.loads(STORE["stul_pravidla"]) == {"35": {"cena_navlek_200": 410.0, "hloubka_stredni_profil": 750.0}}, f"v app_settings je JSON po systemech, jen odlisne hodnoty ({STORE})")
check(S.prah_hloubky(35) == 750.0 and S.prah_hloubky(30) == 900.0, "po ulozeni plati hned a jen v systemu 35")
k35 = client.get("/api/stul/konfigurace?system=35&hloubka=800").get_json()
k30 = client.get("/api/stul/konfigurace?system=30&hloubka=800").get_json()
check(k35["hloubka_bocni_profil"] == 750 and any(i["kod"] == "police_podpery" and i["hloubka_mm"] == 750 for i in k35["info"]) and k30["hloubka_bocni_profil"] == 900 and not k30["info"], "konfigurace: system 35 ma podpery podle 750, system 30 ne")
# dalsi PUT jineho systemu nesmi prepsat prvni
r = client.put("/api/stul/pravidla", json={"system": 40, "pravidla": {"sirka_stredni_noha": 1200}})
check(r.status_code == 200 and json.loads(STORE["stul_pravidla"]) == {"35": {"cena_navlek_200": 410.0, "hloubka_stredni_profil": 750.0}, "40": {"sirka_stredni_noha": 1200.0}} and S.prah_hloubky(35) == 750.0 and S.prah_sirky(40) == 1200.0,
      f"PUT systemu 40 neprepise 35 ({STORE})")
# prazdna hodnota = vychozi jen u toho klice a systemu
r = client.put("/api/stul/pravidla", json={"system": 35, "pravidla": {"hloubka_stredni_profil": ""}})
check(r.status_code == 200 and S.prah_hloubky(35) == 900.0 and S.pravidlo("cena_navlek_200", 35) == 410.0 and S.prah_sirky(40) == 1200.0, "prazdna hodnota vrati vychozi jen svuj klic v tomto systemu")
# neplatne
pred_store = STORE["stul_pravidla"]
for spatne in ({"system": 36, "pravidla": {"cena_vyrez": 5}}, {"system": None, "pravidla": {"cena_vyrez": 5}}, {"system": "abc", "pravidla": {}}, {"system": 35, "pravidla": {"hloubka_stredni_profil": 399}},
               {"system": 35, "pravidla": {"neznamy": 1}}, {"system": 35, "pravidla": {"cena_vyrez": "x"}}, {"system": 40, "pravidla": {"sirka_stredni_noha": 3001}}):
    rr = client.put("/api/stul/pravidla", json=spatne)
    check(rr.status_code == 400 and "error" in rr.get_json() and STORE["stul_pravidla"] == pred_store, f"PUT {spatne}: 400 a nic se neulozilo ({rr.status_code})")
# plochy (stary) tvar: jen kdyz jsou vsechny systemy stejne
rr = client.put("/api/stul/pravidla", json={"cena_vyrez": 999})
check(rr.status_code == 409 and rr.get_json().get("code") == "po_systemech" and STORE["stul_pravidla"] == pred_store, f"plochy PUT pri ruznych systemech = 409 a nic se nezmeni ({rr.status_code})")
reset()
rr = client.put("/api/stul/pravidla", json={"cena_vyrez": 999})
check(rr.status_code == 200 and all(S.pravidlo("cena_vyrez", x) == 999.0 for x in STARE) and S.pravidlo("cena_vyrez", 41) == 0.0 and json.loads(STORE["stul_pravidla"]) == {"cena_vyrez": 999.0}, f"plochy PUT pri stejnych systemech = vsem a ulozi se plochy tvar ({STORE})")
rr = client.put("/api/stul/pravidla", json={"cena_vyrez": 999, "hloubka_stredni_profil": 801})
check(rr.status_code == 200 and json.loads(STORE["stul_pravidla"]) == {"cena_vyrez": 999.0, "hloubka_stredni_profil": 801.0}, "plochy PUT: dalsi klic se sloucil, tvar zustal plochy")
rr = client.put("/api/stul/pravidla", json={"system": 30, "pravidla": {"cena_vyrez": 111}})
check(rr.status_code == 200 and json.loads(STORE["stul_pravidla"]) == {"30": {"cena_vyrez": 111.0, "hloubka_stredni_profil": 801.0}, "35": {"cena_vyrez": 999.0, "hloubka_stredni_profil": 801.0}, "40": {"cena_vyrez": 999.0, "hloubka_stredni_profil": 801.0}},
      f"po-systemovy PUT po plochem: ostatni systemy zdedily puvodni hodnoty (zadna ztrata) ({STORE})")
# nacteni: stary plochy JSON do vsech systemu, po systemech
reset()
STORE["stul_pravidla"] = json.dumps({"cena_vyrez": 2800.0})
stul_api._PRAVIDLA_STAV["t"] = 0.0
check(client.get("/api/stul/konfigurace").status_code == 200 and all(S.pravidlo("cena_vyrez", x) == 2800.0 for x in STARE) and S.pravidla_systemu(41) == S.pravidla_vychozi(41), "stary plochy JSON {cena_vyrez} plati pro systemy 30 / 35 / 40 (SSE ma vychozi hodnoty)")
STORE["stul_pravidla"] = json.dumps({"35": {"sirka_stredni_noha": 1800}, "40": {"cena_vyrez": 1}})
stul_api._PRAVIDLA_STAV["t"] = 0.0
check(client.get("/api/stul/konfigurace").status_code == 200 and S.prah_sirky(35) == 1800.0 and S.prah_sirky(30) == 1500.0 and S.pravidlo("cena_vyrez", 40) == 1.0 and S.pravidlo("cena_vyrez", 35) == 0.0, "JSON po systemech: kazdy system svoje, chybejici system vychozi")
STORE["stul_pravidla"] = json.dumps({"35": {"hloubka_stredni_profil": 20}})
stul_api._PRAVIDLA_STAV["t"] = 0.0
check(client.get("/api/stul/konfigurace").status_code == 200 and S.prah_sirky(35) == 1800.0, "po-systemovy JSON s hodnotou mimo rozsah se ignoruje (plati posledni platne)")
STORE["stul_pravidla"] = json.dumps({"35": 5})
stul_api._PRAVIDLA_STAV["t"] = 0.0
check(client.get("/api/stul/konfigurace").status_code == 200 and S.prah_sirky(35) == 1800.0, "po-systemovy JSON s nesmyslnym tvarem se ignoruje")
check(stul_api.pravidla_z_json(None) == {x: {} for x in SYSTEMY} and stul_api.pravidla_z_json("{}") == {x: {} for x in SYSTEMY} and stul_api.pravidla_z_json('{"35": {"cena_vyrez": 1}}')[35] == {"cena_vyrez": 1}, "pravidla_z_json: prazdne = vychozi, po systemech")
reset()

print("F) verejne API po systemech")
reset()
S.nastav_pravidla({"sirka_stredni_noha": 1200, "vzpery_od_ramene": 650, "cena_vyrez": 3300}, system=35)
r30 = SH.resolve({"w": 1300}, system=30)
r35 = SH.resolve({"w": 1300}, system=35)
check(r30["options"]["mid"] == {"min": 50, "max": 50} and r35["options"]["mid"]["max"] > 50, f"stredni noha u 1300 mm: v systemu 35 (prah 1200) ano, v 30 (prah 1500) ne ({r30['options']['mid']} / {r35['options']['mid']})")
check(r30["hash"] != r35["hash"], "systemy se nemichaji (jiny hash)")
for sy, ocek in ((30, 500), (35, 650), (40, 500)):
    au = next(x for x in SH.schema("cs", sy)["slots"] if x["id"] == "braces")
    check((au.get("auto_on") or {}).get("when", {}).get("above") == ocek or not S.SYSTEMY[sy]["vzpery"], f"schema systemu {sy}: automaticke vzpery od {ocek} mm ({(au.get('auto_on') or {}).get('when')})")
for sy, prah_ in ((30, 1500), (35, 1200), (40, 1500)):
    h_mid = next(x for x in SH.schema("cs", sy)["slots"] if x["id"] == "mid")["help"]
    check(f"Nad {prah_} mm" in h_mid and "{prah}" not in h_mid, f"napoveda stredni nohy systemu {sy} nese prah systemu ({h_mid[:30]})")
d_v = {sy: SH.resolve({"w": 1500, "cut1": True}, system=sy) for sy in (30, 35)}
check(d_v[30]["valid"] and d_v[35]["valid"], "vyrez v obou systemech platny")
o30 = SH.resolve({"w": 1500}, system=30)["options"]["cut1"]["on"]["price_delta"]
o35 = SH.resolve({"w": 1500}, system=35)["options"]["cut1"]["on"]["price_delta"]
check(o30 == 0 and o35 > 3000, f"priplatek za vyrez: system 30 bez (0), system 35 podle pravidla 3 300 Kc ({o30} / {o35})")
SH.resolve({"w": 1400}, system=35)
for n_ in range(3):
    check(SH.resolve({"w": 1300}, system=30)["options"]["mid"] == {"min": 50, "max": 50}, "cache resolve nemici systemy (opakovane volani 30 po 35)")
reset()

print(f"\n{OK} kontrol OK" + (f", {len(FAILS)} CHYB" if FAILS else ""))
sys.exit(1 if FAILS else 0)
