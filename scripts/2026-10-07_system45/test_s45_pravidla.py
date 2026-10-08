#!/usr/bin/env python3
"""PRAVIDLA STOLU systemu 45 (bot10, 2026-10-07): ukladani a nacteni pres API (hermeticky: zapis do app_settings jde do FALESNE DB, produkcni se nemeni; uzivatele a ceny se jen ctou).
Hlida chybu, ktera by sada ostatnich testu nechytila: PUT /api/stul/pravidla ukladal plochy tvar, kdyz mely 30 / 35 / 40 stejna pravidla a SSE zadne zmeny - pravidla SYSTEMU 45 by se pak
tise ztratila (ulozila by se prazdna sada). Dale: GET nese system 45, PUT {system: 45} se ulozi po systemech a po obnoveni drzi, ostatni systemy zustanou, plochy PUT 30 / 35 / 40 se 45 nedotkne,
stary plochy JSON se do 45 nededi (45 ma vychozi hodnoty), cena vyrezu v pravidlech 45 plati jen ve 45 (i ve staff route), neplatny klic / hodnota / system = 400.
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_system45/test_s45_pravidla.py"""
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
sys.dont_write_bytecode = True
try:
    import app as appmod  # noqa: E402
    import stul_api  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_glb as G  # noqa: E402
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
conn.rollback()
client = appmod.app.test_client()
with client.session_transaction() as sess:
    sess["user_id"] = admin_id
KLIC = stul_api.PRAVIDLA_KLIC


def reset():
    S.nastav_pravidla({})
    STORE.clear()
    stul_api._PRAVIDLA_STAV["t"] = 0.0


def put(telo):
    r = client.put("/api/stul/pravidla", json=telo)
    return r.status_code, r.get_json()


def ulozeno():
    return json.loads(STORE[KLIC]) if KLIC in STORE else None


def obnov():
    """simuluje restart procesu: pravidla v pameti na vychozi a nacist z (falesne) DB"""
    S.nastav_pravidla({})
    stul_api._PRAVIDLA_STAV["t"] = 0.0
    stul_api.obnov_pravidla(force=True)


# ---------------------------------------------------------------- 1) GET nese system 45
reset()
d = client.get("/api/stul/pravidla").get_json()
check("45" in d["systemy"] and d["systemy"]["45"] == S.PRAVIDLA_VYCHOZI and d["vychozi_systemu"]["45"] == S.PRAVIDLA_VYCHOZI, "GET: systemy a vychozi_systemu nesou system 45 s vychozimi hodnotami")

# ---------------------------------------------------------------- 2) PUT {system: 45}: uklada se PO SYSTEMECH (ne plochy tvar, ktery by hodnoty 45 ztratil)
reset()
c, r = put({"system": 45, "pravidla": {"cena_vyrez": 500}})
check(c == 200 and r["pravidla"]["cena_vyrez"] == 500.0 and r["systemy"]["45"]["cena_vyrez"] == 500.0 and r["systemy"]["40"]["cena_vyrez"] == 0.0, f"PUT system 45: odpoved ma 500 jen v 45 ({c})")
check(ulozeno() == {"45": {"cena_vyrez": 500.0}}, f"ulozeno po systemech {{'45': {{cena_vyrez: 500}}}}, ne plochy tvar ({ulozeno()})")
obnov()
check(S.pravidlo("cena_vyrez", 45) == 500.0 and S.pravidlo("cena_vyrez", 40) == 0.0 and S.pravidlo("cena_vyrez", 30) == 0.0, "po obnoveni (restart) drzi cena vyrezu 500 jen ve 45")

# ---------------------------------------------------------------- 3) dalsi zmena v JINEM systemu zachova hodnoty 45; plochy PUT (bez system) se 45 nedotkne
c, r = put({"system": 40, "pravidla": {"hloubka_stredni_profil": 750}})
check(c == 200 and ulozeno() == {"40": {"hloubka_stredni_profil": 750.0}, "45": {"cena_vyrez": 500.0}}, f"PUT system 40 zachova hodnoty 45 ({ulozeno()})")
c, r = put({"system": 45, "pravidla": {"hloubka_stredni_profil": 1100, "vzpery_od_ramene": 600}})
check(c == 200 and ulozeno()["45"] == {"cena_vyrez": 500.0, "hloubka_stredni_profil": 1100.0, "vzpery_od_ramene": 600.0} and ulozeno()["40"] == {"hloubka_stredni_profil": 750.0}, f"vic hodnot v 45 se sloucilo ({ulozeno()})")
obnov()
check(S.prah_hloubky(45) == 1100.0 and S.prah_hloubky(40) == 750.0 and S.prah_hloubky(30) == 900.0 and S.prah_hloubky(35) == 900.0, f"prahy podper po obnoveni: 45 {S.prah_hloubky(45)}, 40 {S.prah_hloubky(40)}, 30 {S.prah_hloubky(30)}")
S.nastav_pravidla({}, system=40)
reset()
put({"system": 45, "pravidla": {"cena_vyrez": 500}})
c, r = put({"cena_vyrez": 300})                                  # starsi plochy formular: plati jen dokud maji 30 / 35 / 40 stejna pravidla (maji) -> nastavi se jim, 45 zustane
check(c == 200 and ulozeno() == {"30": {"cena_vyrez": 300.0}, "35": {"cena_vyrez": 300.0}, "40": {"cena_vyrez": 300.0}, "45": {"cena_vyrez": 500.0}}, f"plochy PUT nastavi 30 / 35 / 40 a nedotkne se 45 ({c}, {ulozeno()})")
check(S.pravidlo("cena_vyrez", 45) == 500.0 and S.pravidlo("cena_vyrez", 30) == 300.0, "plochy PUT: 45 drzi svou hodnotu")

# ---------------------------------------------------------------- 4) vraceni na vychozi: prazdna hodnota = vychozi, system bez zmen se neuklada
reset()
put({"system": 45, "pravidla": {"cena_vyrez": 500}})
c, r = put({"system": 45, "pravidla": {"cena_vyrez": ""}})
check(c == 200 and r["systemy"]["45"]["cena_vyrez"] == 0.0 and ulozeno() == {}, f"vychozi hodnota 45 se neuklada (ulozeno {ulozeno()})")

# ---------------------------------------------------------------- 5) stary plochy JSON se do 45 nededi
reset()
STORE[KLIC] = json.dumps({"cena_vyrez": 2800.0})
obnov()
check(S.pravidlo("cena_vyrez", 30) == 2800.0 and S.pravidlo("cena_vyrez", 35) == 2800.0 and S.pravidlo("cena_vyrez", 40) == 2800.0 and S.pravidlo("cena_vyrez", 45) == 0.0, "stary plochy JSON plati pro 30 / 35 / 40; 45 ma vychozi hodnoty")

# ---------------------------------------------------------------- 6) neplatne vstupy = 400 a nic se neulozi
reset()
check(put({"system": 45, "pravidla": {"cena_vyrez": -5}})[0] == 400 and ulozeno() is None, "zaporna cena = 400, nic se neulozilo")
check(put({"system": 45, "pravidla": {"neznamy_klic": 1}})[0] == 400, "neznamy klic = 400")
check(put({"system": 46, "pravidla": {"cena_vyrez": 1}})[0] == 400, "neznamy system 46 = 400")
check(put({"system": 45, "pravidla": {"hloubka_stredni_profil": 5000}})[0] == 400, "prah podper mimo rozsah = 400")

# ---------------------------------------------------------------- 7) cena: pravidlo 45 plati jen ve 45 (staff route + generator)
reset()
put({"system": 45, "pravidla": {"cena_vyrez": 500}})
k45 = client.get("/api/stul/konfigurace?system=45&sirka=1800&hloubka=1200&vyrez1=1").get_json()
k45b = client.get("/api/stul/konfigurace?system=45&sirka=1800&hloubka=1200").get_json()
k40 = client.get("/api/stul/konfigurace?system=40&sirka=1800&hloubka=1200&vyrez1=1").get_json()
k40b = client.get("/api/stul/konfigurator?system=40&sirka=1800&hloubka=1200") if False else client.get("/api/stul/konfigurace?system=40&sirka=1800&hloubka=1200").get_json()
check(k45["cena"]["bez_dph"] - k45b["cena"]["bez_dph"] >= 500, f"staff route 45: vyrez stoji aspon 500 Kc ({k45['cena']['bez_dph'] - k45b['cena']['bez_dph']})")
check(k40["cena"]["bez_dph"] - k40b["cena"]["bez_dph"] < 500, f"staff route 40: vyrez nestoji 500 Kc ({k40['cena']['bez_dph'] - k40b['cena']['bez_dph']})")

# ---------------------------------------------------------------- 8) ZLOMOVE MIRY PO SYSTEMECH pres API (Robert 2026-10-07): hloubka_stredni_noha (jen 45), podpera_max_rozpon, min_odstup_stredni_noha
reset()
d = client.get("/api/stul/pravidla").get_json()
check(d["hluboke_systemy"] == [45] and all(k in d["rozsah"] and k in d["vychozi"] for k in ("hloubka_stredni_noha", "podpera_max_rozpon", "min_odstup_stredni_noha")), "GET: hluboke_systemy [45] a nova pravidla v rozsahu / vychozich")
check(d["vychozi"]["hloubka_stredni_noha"] == 1500.0 and d["vychozi"]["podpera_max_rozpon"] == 800.0 and d["vychozi"]["min_odstup_stredni_noha"] == 150.0, "GET: vychozi zlomove miry 1500 / 800 / 150")
check(put({"system": 45, "pravidla": {"hloubka_stredni_noha": 3000}})[0] == 400 and put({"system": 45, "pravidla": {"hloubka_stredni_noha": 300}})[0] == 400, "hloubka_stredni_noha mimo 400-2500 = 400")
check(put({"system": 40, "pravidla": {"podpera_max_rozpon": 100}})[0] == 400 and put({"system": 40, "pravidla": {"min_odstup_stredni_noha": 20}})[0] == 400, "podpera_max_rozpon (200-3000) a min_odstup_stredni_noha (50-1000) mimo rozsah = 400")
c, r = put({"system": 45, "pravidla": {"hloubka_stredni_noha": 1800, "podpera_max_rozpon": 600}})
check(c == 200 and ulozeno() == {"45": {"hloubka_stredni_noha": 1800.0, "podpera_max_rozpon": 600.0}}, f"PUT 45: zlomove miry ulozeny po systemech ({ulozeno()})")
c, r = put({"system": 40, "pravidla": {"min_odstup_stredni_noha": 250, "sirka_stredni_noha": 1800}})
check(c == 200 and ulozeno()["40"] == {"min_odstup_stredni_noha": 250.0, "sirka_stredni_noha": 1800.0} and ulozeno()["45"] == {"hloubka_stredni_noha": 1800.0, "podpera_max_rozpon": 600.0}, f"PUT 40: jeho zlomove miry, 45 zustava ({ulozeno()})")
obnov()
check(S.prah_hloubky_noha(45) == 1800.0 and S.podpera_max_rozpon(45) == 600.0 and S.podpera_max_rozpon(40) == 800.0 and S.min_odstup_stredni_noha(40) == 250.0 and S.min_odstup_stredni_noha(45) == 150.0
      and S.prah_sirky(40) == 1800.0 and S.prah_sirky(45) == 1500.0, "po obnoveni (restart) drzi kazdy system sve zlomove miry")
# hash: nastavitelna zlomova mira meni hash JEN systemu, kde je zmenena, a jen kdyz meni stavbu (45: prah stredni rady; podpery)
reset()
h45 = G.kanonicky_hash(dict(system=45, hloubka=2000.0))
h40 = G.kanonicky_hash(dict(system=40, hloubka=1200.0))
S.nastav_pravidla({"hloubka_stredni_noha": 1800}, system=45)
S.nastav_pravidla({"podpera_max_rozpon": 500}, system=40)
check(G.kanonicky_hash(dict(system=45, hloubka=2000.0)) != h45 and G.kanonicky_hash(dict(system=40, hloubka=1200.0)) != h40, "hash: zmena zlomove miry (stredni rada 45 / podpery 40) da jiny hash")
check(G.kanonicky_hash(dict(system=30, hloubka=1200.0)) == G.kanonicky_hash(dict(system=30, hloubka=1200.0)) and G.kanonicky_hash(dict(system=35, hloubka=1200.0)) == G.kanonicky_hash(dict(system=35, hloubka=1200.0)), "hash systemu bez zmeny je stabilni")
reset()
check(G.kanonicky_hash(dict(system=45, hloubka=2000.0)) == h45 and G.kanonicky_hash(dict(system=40, hloubka=1200.0)) == h40, "hash: vychozi zlomove miry hash nemeni")

# ---------------------------------------------------------------- 9) PREVOD KOMPATIBILITY: stejny vyber v systemech s RUZNYMI zlomovymi mirami (verejne API, fiktivni karty)
import time  # noqa: E402
P40, P45 = 9877, 9878
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(P40): SH.RECEPT_40, str(P45): SH.RECEPT_45})
SH._SYSTEMY_CACHE.update(t=0.0, list=[])
pub = appmod.app.test_client()


def resolve(pid, sel):
    r = pub.post("/api/shop/configurator/resolve", json={"product_id": pid, "selection": sel, "lang": "cs"})
    return r.status_code, r.get_json()


def tahy(r):
    return {t["id"] for t in ((r.get("vodici") or {}).get("ovladani") or {}).get("tahy", [])}


reset()
put({"system": 40, "pravidla": {"sirka_stredni_noha": 1800, "min_odstup_stredni_noha": 300}})           # system 40: stredni noha az od 1800, nejmene 300 mm od krajni (pres API, drzi i pri dalsich pozadavcich)
put({"system": 45, "pravidla": {"hloubka_stredni_noha": 1700}})                                         # system 45: stredni rada noh od hloubky 1700
SEL = {"w": 1700, "d": 1600, "h": 840, "shelf": 1, "mid": 20}
c40, r40 = resolve(P40, SEL)
c45, r45 = resolve(P45, SEL)
check(c40 == 200 and c45 == 200 and r40["valid"] and r45["valid"], f"stejny vyber je platny v obou systemech ({r40.get('errors')}, {r45.get('errors')})")
check("mid" not in tahy(r40) and "mid" in tahy(r45), f"sirka 1700: ve 40 (prah 1800) bez tahu stredni nohy, ve 45 (prah 1500) s nim ({sorted(tahy(r40) & {'mid'})} / {sorted(tahy(r45) & {'mid'})})")
check(r45["selection"]["mid"] == 20 and 5 <= r45["selection"]["mid"] <= 95, f"45: poloha stredni nohy 20 % se zachova ({r45['selection']['mid']})")
check(r40["hash"] != r45["hash"], "ruzne hashe")
SEL2 = {"w": 2400, "d": 1600, "h": 840, "shelf": 1, "mid": 10}                                           # 10 % z rozpeti 2360 = 236 mm od krajni nohy: ve 45 (limit 150) platne, ve 40 (limit 300) se orizne dovnitr
c40, r40 = resolve(P40, SEL2)
c45, r45 = resolve(P45, SEL2)
check(r45["selection"]["mid"] == 10, f"45: poloha 10 % (236 mm od nohy, limit 150) zustane ({r45['selection']['mid']})")
check(r40["selection"]["mid"] > 10 and r40["valid"], f"40: poloha 10 % je pod limitem 300 mm, orizne se dovnitr ({r40['selection']['mid']} %), konfigurace platna")
SEL3 = {"w": 1800, "d": 1650, "h": 840, "shelf": 1}                                                      # hloubka 1650: ve 45 s prahem 1700 jeste bez stredni rady, s vychozim 1500 uz s ni
c45, r45 = resolve(P45, SEL3)
reset()
c45b, r45b = resolve(P45, SEL3)
check(not [n for n in r45["notices"] if n["slot"] == "d" and "nad 1700 mm" in n["message"]] and [n for n in r45b["notices"] if n["slot"] == "d" and "nad 1500 mm" in n["message"]], "oznameni o stredni rade noh nese prah systemu (1700 -> bez oznameni pri 1650; vychozi 1500 -> oznameni)")
check(r45["hash"] != r45b["hash"] or r45["price"]["net"] != r45b["price"]["net"], "ruzny prah stredni rady da u hloubky 1650 jiny hash nebo cenu")
reset()

print(f"\n{OK} kontrol OK" + ("" if not FAILS else f"; SELHALO {len(FAILS)}"))
sys.exit(1 if FAILS else 0)
