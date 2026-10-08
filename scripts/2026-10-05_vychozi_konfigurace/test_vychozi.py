#!/usr/bin/env python3
"""Test VYCHOZI KONFIGURACE GENERATORU - admin tlacitko "Ulozit jako vychozi" (bot8, 2026-10-05; Robert: "postav mi admin tlacitko v generatoru, kterym ulozim konfiguraci jako vychozi").

Hermeticky: zapis do app_settings jde do FALESNE DB (stul_api.get_conn je nahrazeno), audit_log se zaznamenava do seznamu (stul_shop.log_audit je nahrazeno), produkcni DB se jen CTE (ceny, katalog,
admin uzivatel pro session). Produkty (fiktivni karty 9871 - 9874 = systemy 30 / 35 / 40 / 41) se podstrci primo do cache modulu.
Hlida: stul_api (vychozi_over - tvar a hodnoty, nic se neorezava potichu; ulozeni / cteni / cache / TTL / smazani; chybna ulozena hodnota = vestavene vychozi, kazdy produkt zvlast),
slij_vychozi (jen znamé klice a hodnoty stejneho typu), routy PUT / DELETE /api/shop/products/<id>/configurator/default (bez prihlaseni 401, bez prava 403, neznamy produkt 404, chybny tvar 400,
neplatna konfigurace 409, nepodporovana volba SSE 400, platna konfigurace 200 + zapis + audit), schema (default_saved, default_selection = vestavene vychozi prepsane ulozenym; jiny produkt
nedotcen), pevny bod (resolve(default_selection) vraci TENTYZ vyber), vestavene vychozi (vychozi_vyber, normalizuj chybejicich poli) se ulozenim NEMENI.
Spusteni:  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-05_vychozi_konfigurace/test_vychozi.py"""
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
    import stul_api  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_shop as SH  # noqa: E402
finally:
    threading.Thread.start = _orig
S.nastav_pravidla({})                                           # ziva pravidla neovlivni test
if hasattr(SH, "_DELKY_CACHE"):                                       # delky perforovaneho panelu (2026-10-07): verejnost dostane nove delky az po aktivaci karet (pravidlo 54); test pocita se vsemi
    SH._DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset(S.PANEL_DELKY))
stul_api.obnov_pravidla = lambda force=False: None
SH.LIMIT_SCHEMA = (10 ** 6, 60)                                    # test vola verejne schema desitky krat z jedne IP: omezeni poctu dotazu (429) by ho shodilo
SH.HODINOVY_STROP["schema"] = 10 ** 6

OK, FAILS = 0, []


def check(cond, msg, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg} {detail}")


# ---- falesna DB pro app_settings (zapis i cteni); vsechno ostatni (ceny, katalog, uzivatele) se cte ze skutecne DB (jen SELECT)
class FakeCur:
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

    def rollback(self):
        pass

    def close(self):
        pass


REAL_CONN = stul_api.get_conn
STORE = {}
stul_api.get_conn = lambda: FakeConn(STORE)
AUDIT = []
SH.log_audit = lambda uid, action, et, eid=None, detail=None: AUDIT.append((uid, action, et, eid, detail))

PIDS = {30: 9871, 35: 9872, 40: 9873, 41: 9874}
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PIDS[30]): SH.RECEPT, str(PIDS[35]): SH.RECEPT_35, str(PIDS[40]): SH.RECEPT_40, str(PIDS[41]): SH.RECEPT_SSE})
CESTA = "/api/shop/products/%d/configurator"

conn = appmod.get_conn()
cur = conn.cursor()
cur.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
admin_id = cur.fetchone()["id"]
cur.execute("SELECT id, role FROM app_users WHERE role<>'admin' AND COALESCE(active, 1)=1 ORDER BY id")
jini = cur.fetchall()
conn.rollback()
admin = appmod.app.test_client()
with admin.session_transaction() as sess:
    sess["user_id"] = admin_id
anon = appmod.app.test_client()


def reset():
    STORE.clear()
    AUDIT.clear()
    stul_api._VYCHOZI_CACHE.clear()


def schema(sys_, klient=None):
    r = (klient or anon).get(CESTA % PIDS[sys_] + "?lang=cs")
    assert r.status_code == 200, r.status_code
    return r.get_json()


def put(sys_, body, klient=None, raw=None):
    k = klient or admin
    if raw is not None:
        return k.put(CESTA % PIDS[sys_] + "/default", data=raw, content_type="application/json")
    return k.put(CESTA % PIDS[sys_] + "/default", json=body)


KLIC = {s: f"configurator_default_{PIDS[s]}" for s in PIDS}

# ---------------------------------------------------------------------------------------------------------------------
print("A) stul_api: vychozi_over, ulozeni, cteni, cache, smazani")
reset()
dobry = {"w": 1800, "shelf": True, "sh1": None, "petleg": "fl", "x": 1.5, "bearings": False}
kopie = stul_api.vychozi_over(dobry)
check(kopie == dobry and kopie is not dobry, "vychozi_over: platny vyber (cislo, ano/ne, text, null, desetinne) projde jako kopie")
spatne = [([], "pole"), ({}, "prazdny objekt"), ("abc", "text"), (None, "null"), ({"W": 1}, "velke pismeno v nazvu"), ({"a b": 1}, "mezera v nazvu"), ({"x" * 41: 1}, "nazev nad 40 znaku"),
          ({"": 1}, "prazdny nazev"), ({"w": [1]}, "pole jako hodnota"), ({"w": {"a": 1}}, "objekt jako hodnota"), ({"w": float("nan")}, "NaN"), ({"w": float("inf")}, "nekonecno"),
          ({"w": "x" * 41}, "text nad 40 znaku"), ({f"k{i}": 1 for i in range(201)}, "vic nez 200 poli"), ({1: 1}, "ciselny klic")]
for sel, popis in spatne:
    try:
        stul_api.vychozi_over(sel)
        check(False, f"vychozi_over musi odmitnout: {popis}")
    except ValueError:
        check(True, "")
r1 = stul_api.uloz_vychozi(11, dobry)
check(r1 == dobry and json.loads(STORE["configurator_default_11"]) == dobry, "uloz_vychozi: zapis do app_settings configurator_default_<id> jako JSON", STORE)
check(STORE["configurator_default_11"] == json.dumps(dobry, sort_keys=True), "uloz_vychozi: JSON je razeny podle klicu (stabilni zapis)")
check(stul_api.nacti_vychozi(11) == dobry, "nacti_vychozi: vraci ulozene")
x = stul_api.nacti_vychozi(11)
x["w"] = 1
check(stul_api.nacti_vychozi(11)["w"] == 1800, "nacti_vychozi vraci kopii (zmena volajiciho neposkodi cache)")
STORE["configurator_default_11"] = json.dumps({"w": 2200})
check(stul_api.nacti_vychozi(11)["w"] == 1800, "cache: zmena v DB se do VYCHOZI_TTL_S neprojevi")
check(stul_api.nacti_vychozi(11, force=True)["w"] == 2200, "force=True nacte novou hodnotu z DB")
STORE["configurator_default_11"] = json.dumps({"w": 1700})
stul_api._VYCHOZI_CACHE[11] = (time.time() - stul_api.VYCHOZI_TTL_S - 1, {"w": 2200})
check(stul_api.nacti_vychozi(11)["w"] == 1700, "po uplynuti TTL se zmena z jineho workeru nacte")
for spatna_hodnota in ("neni json", "[1, 2]", '{"w": [1]}', '{"W": 1}', "{}", "null", ""):
    STORE["configurator_default_12"] = spatna_hodnota
    stul_api._VYCHOZI_CACHE.clear()
    check(stul_api.nacti_vychozi(12) is None, f"chybna ulozena hodnota {spatna_hodnota!r} = vestavene vychozi (None), nic nespadne")
stul_api.uloz_vychozi(13, {"w": 1000})
check(stul_api.nacti_vychozi(13) == {"w": 1000} and stul_api.nacti_vychozi(11) == {"w": 1700}, "kazdy produkt ma vlastni vychozi konfiguraci (klic podle id)")
check(stul_api.uloz_vychozi(13, None) is None and "configurator_default_13" not in STORE and stul_api.nacti_vychozi(13) is None, "uloz_vychozi(None) smaze klic a cteni vrati None")
try:
    stul_api.uloz_vychozi(14, {"w": [1]})
    check(False, "uloz_vychozi s neplatnou hodnotou musi vyhodit ValueError")
except ValueError:
    check("configurator_default_14" not in STORE, "neplatny vyber se neulozi")
check(stul_api.vychozi_klic(9871) == "configurator_default_9871", "klic app_settings")

# ---------------------------------------------------------------------------------------------------------------------
print("B) slij_vychozi")
zaklad = {"w": 1200, "d": 800, "shelf": 1, "drawers": True, "sh1": None, "petleg": "fl", "cut1": False}
check(SH.slij_vychozi(zaklad, None) == zaklad and SH.slij_vychozi(zaklad, {}) == zaklad, "bez ulozene konfigurace = vestavene vychozi")
m = SH.slij_vychozi(zaklad, {"w": 1800, "shelf": 2, "drawers": False, "sh1": 400, "petleg": "rr", "cut1": True})
check(m == {"w": 1800, "d": 800, "shelf": 2, "drawers": False, "sh1": 400, "petleg": "rr", "cut1": True}, "prepsou se hodnoty stejneho typu (vc. null -> cislo u vysky police)", m)
check(SH.slij_vychozi(zaklad, {"w": "abc", "d": True, "drawers": 1, "petleg": 5, "cut1": "ano", "shelf": None})["w"] == 1200, "hodnota jineho typu se ignoruje (text pro cislo)")
m2 = SH.slij_vychozi(zaklad, {"w": "abc", "d": True, "drawers": 1, "petleg": 5, "cut1": "ano", "shelf": None})
check(m2 == zaklad, "ano/ne jen ano/ne, cislo jen cislo (ne bool), text jen text, null pro cislo se ignoruje", m2)
check(SH.slij_vychozi(zaklad, {"sh1": "x"})["sh1"] is None and SH.slij_vychozi(zaklad, {"sh1": True})["sh1"] is None, "vestavene null (automatika): jen null nebo cislo")
m3 = SH.slij_vychozi(zaklad, {"neznamy": 5, "w": 1500})
check("neznamy" not in m3 and m3["w"] == 1500 and set(m3) == set(zaklad), "neznamy klic se zahodi, schema ma porad stejne klice")
check(zaklad["w"] == 1200, "slij_vychozi nemeni vstup")

# ---------------------------------------------------------------------------------------------------------------------
print("C) schema bez ulozene konfigurace + vestavene vychozi")
reset()
vestavene = {}
for sy in PIDS:
    sc = schema(sy)
    vestavene[sy] = sc["default_selection"]
    check(sc["default_saved"] is False and sc["default_selection"] == SH.vychozi_vyber(sy) and sc["system"] == sy, f"system {sy}: default_saved false, default_selection = vestavene vychozi")
    check(sc["rules_version"] == G.RULES_VERSION, f"system {sy}: verze pravidel beze zmeny")

# ---------------------------------------------------------------------------------------------------------------------
print("D) opravneni a tvar vstupu (nic se nezapise)")
reset()
sel30 = dict(vestavene[30])
for popis, odp in (("PUT bez prihlaseni", anon.put(CESTA % PIDS[30] + "/default", json={"selection": sel30})), ("DELETE bez prihlaseni", anon.delete(CESTA % PIDS[30] + "/default"))):
    check(odp.status_code == 401 and not STORE and not AUDIT, f"{popis}: 401, nic se nezapise", odp.status_code)
nenalezen = False
for u in jini:
    k = appmod.app.test_client()
    with k.session_transaction() as sess:
        sess["user_id"] = u["id"]
    o = put(30, {"selection": sel30}, klient=k)
    if o.status_code == 403:
        nenalezen = True
        d = k.delete(CESTA % PIDS[30] + "/default")
        check(d.status_code == 403 and not STORE and not AUDIT, f"uzivatel role {u['role']} bez prava nastaveni: PUT i DELETE 403, nic se nezapise", (o.status_code, d.status_code))
        break
    reset()                                                     # tenhle uzivatel pravo ma (zapsalo se jen do falesne DB)
if not nenalezen:
    print("  (v DB neni aktivni uzivatel bez prava nastaveni/upravit - kontrola 403 preskocena)")
reset()
for popis, odp in (("bez tela", put(30, None, raw="")), ("neplatny JSON", put(30, None, raw="abc")), ("prazdny objekt", put(30, {})), ("selection pole", put(30, {"selection": []})),
                   ("selection text", put(30, {"selection": "x"})), ("selection prazdny", put(30, {"selection": {}})), ("hodnota pole", put(30, {"selection": {"w": [1]}})),
                   ("velke pismeno v nazvu", put(30, {"selection": {"W": 1}})), ("text nad 40 znaku", put(30, {"selection": {"w": "x" * 41}})), ("selection null", put(30, {"selection": None}))):
    check(odp.status_code == 400 and not STORE and not AUDIT and "error" in (odp.get_json() or {}), f"PUT {popis}: 400 s chybou, nic se nezapise", (odp.status_code, odp.get_data(as_text=True)[:100]))
for popis, odp in (("bez selection", put(30, {})), ("selection pole", put(30, {"selection": []})), ("selection prazdny", put(30, {"selection": {}})), ("selection null", put(30, {"selection": None}))):
    check("selection" in (odp.get_json() or {}).get("error", ""), f"PUT {popis}: chyba rika, ze telo ma byt {{\"selection\": ...}}", odp.get_json())
o404 = admin.put("/api/shop/products/12345678/configurator/default", json={"selection": sel30})
d404 = admin.delete("/api/shop/products/12345678/configurator/default")
check(o404.status_code == 404 and d404.status_code == 404 and not STORE and not AUDIT, "neznamy / nekonfigurovatelny produkt: 404")

# ---------------------------------------------------------------------------------------------------------------------
print("E) neplatna konfigurace (409) a volby jineho systemu (SSE)")
neplatna = {**sel30, "cut1": True, "cut2": True, "cut2z": 150}
o = put(30, {"selection": neplatna})
j = o.get_json()
check(o.status_code == 409 and not STORE and not AUDIT and j.get("errors") and "30 mm" in " ".join(j["errors"]) and "nen" in j["error"], "neplatna konfigurace (prekryv vyrezu) se jako vychozi NEULOZI: 409 s duvodem", (o.status_code, j))
o = put(41, {"selection": {**vestavene[41], "panels": True, "led": True, "w": 2400}})
j = o.get_json()
check(o.status_code == 200 and j["default_selection"]["panels"] is False and j["default_selection"]["led"] is False and j["default_selection"]["w"] == 2400
      and json.loads(STORE[KLIC[41]])["panels"] is False, "SSE: volby jineho systemu (panely, LED) se normalizuji na vypnuto (jako v resolve) a vypnute se ulozi; rozmer se ulozi", (o.status_code, j))
reset()

# ---------------------------------------------------------------------------------------------------------------------
print("F) platne ulozeni pro kazdy system, schema, pevny bod, audit")
ZMENY = {30: {"w": 1800, "d": 900, "h": 920, "shelf": 0}, 35: {"w": 1600, "d": 700, "h": 900, "shelf": 1}, 40: {"w": 1400, "d": 800, "h": 880, "shelf": 0}, 41: {"w": 2200, "d": 800, "h": 860, "drawers": False}}
for sy in PIDS:
    reset()
    vyber = {**vestavene[sy], **ZMENY[sy]}
    o = put(sy, {"selection": vyber})
    j = o.get_json()
    check(o.status_code == 200 and j["default_saved"] is True and all(j["default_selection"][k] == v for k, v in ZMENY[sy].items()), f"system {sy}: PUT 200, default_saved true, default_selection nese zmeny", (o.status_code, j))
    check(KLIC[sy] in STORE and len(STORE) == 1 and json.loads(STORE[KLIC[sy]]) == {k: v for k, v in j["default_selection"].items()}, f"system {sy}: zapsan JEDEN klic {KLIC[sy]} s uplnym vyberem", list(STORE))
    check(set(json.loads(STORE[KLIC[sy]])) == set(vestavene[sy]), f"system {sy}: ulozeny vyber ma stejne klice jako schema (kompletni)")
    check(len(AUDIT) == 1 and AUDIT[0][0] == admin_id and AUDIT[0][1] == "update" and AUDIT[0][2] == "configurator_default" and AUDIT[0][3] == PIDS[sy] and AUDIT[0][4]["system"] == sy
          and AUDIT[0][4]["kod"] == j["kod"], f"system {sy}: audit_log (kdo, update, configurator_default, id produktu, system, kod)", AUDIT)
    sc = schema(sy)
    check(sc["default_saved"] is True and sc["default_selection"] == j["default_selection"], f"system {sy}: schema nese default_saved a ulozenou default_selection")
    check(set(sc["default_selection"]) == set(vestavene[sy]) and all(sc["default_selection"][k] == v for k, v in ZMENY[sy].items()), f"system {sy}: klice schematu beze zmeny, hodnoty ze zmeny")
    for druhy in PIDS:
        if druhy != sy:
            check(schema(druhy)["default_selection"] == vestavene[druhy] and schema(druhy)["default_saved"] is False, f"system {sy} ulozen: system {druhy} nedotcen")
    r = SH.resolve(sc["default_selection"], "cs", system=sy)
    check(r["valid"] and r["selection"] == sc["default_selection"], f"system {sy}: PEVNY BOD - resolve(default_selection) vraci tentyz vyber a je platny", {k: (v, r["selection"].get(k)) for k, v in sc["default_selection"].items() if r["selection"].get(k) != v})
    check(j["hash"] == r["hash"] and j["kod"] == r["kod"], f"system {sy}: hash a kod v odpovedi = hash a kod ulozene konfigurace")
    check(SH.vychozi_vyber(sy) == vestavene[sy], f"system {sy}: vestavene vychozi (vychozi_vyber) se ulozenim nemeni")
    check(SH.normalizuj({}, sy)[1]["w"] == vestavene[sy]["w"], f"system {sy}: chybejici pole se dal doplnuji VESTAVENYM vychozim (server-side normalizace nezavisi na ulozene konfiguraci)")
    # smazani
    d = admin.delete(CESTA % PIDS[sy] + "/default")
    dj = d.get_json()
    check(d.status_code == 200 and dj["default_saved"] is False and dj["default_selection"] == vestavene[sy] and KLIC[sy] not in STORE, f"system {sy}: DELETE 200, zpet na vestavene vychozi, klic smazan", (d.status_code, dj))
    check(len(AUDIT) == 2 and AUDIT[1][1] == "delete" and AUDIT[1][2] == "configurator_default" and AUDIT[1][3] == PIDS[sy], f"system {sy}: audit smazani", AUDIT)
    sc2 = schema(sy)
    check(sc2["default_saved"] is False and sc2["default_selection"] == vestavene[sy], f"system {sy}: po smazani schema znovu nese vestavene vychozi")

# ---------------------------------------------------------------------------------------------------------------------
print("G) mimo rozsah se oreze, opakovane ulozeni, odolnost schematu")
reset()
o = put(30, {"selection": {**vestavene[30], "w": 99999}})
mx = int(S.ROZSAH["sirka"][1])
check(o.status_code == 200 and o.get_json()["default_selection"]["w"] == mx and json.loads(STORE[KLIC[30]])["w"] == mx, f"sirka mimo rozsah se orizne na maximum {mx} (stejne jako v resolve) a ulozi se orezana", o.get_json())
o1 = put(30, {"selection": {**vestavene[30], "w": 1500}})
o2 = put(30, {"selection": {**vestavene[30], "w": 1500}})
check(o1.status_code == 200 and o2.status_code == 200 and o1.get_json() == o2.get_json(), "opakovane ulozeni stejne konfigurace je idempotentni")
# cizi / zastarale klice a typy v ulozene hodnote (napr. po pridani slotu nebo rucni zasah) schema neshodi a slot nezmeni
STORE[KLIC[30]] = json.dumps({"w": 1700, "neexistuje": 5, "d": "abc", "drawers": 7})
stul_api._VYCHOZI_CACHE.clear()
sc = schema(30)
check(sc["default_selection"]["w"] == 1700 and sc["default_selection"]["d"] == vestavene[30]["d"] and sc["default_selection"]["drawers"] == vestavene[30]["drawers"] and "neexistuje" not in sc["default_selection"]
      and set(sc["default_selection"]) == set(vestavene[30]), "schema: neznamy klic a hodnoty spatneho typu se ignoruji, platne pole se pouzije")
STORE[KLIC[30]] = "tohle neni json"
stul_api._VYCHOZI_CACHE.clear()
sc = schema(30)
check(sc["default_saved"] is False and sc["default_selection"] == vestavene[30], "schema: poskozena ulozena hodnota = vestavene vychozi, 200")
STORE[KLIC[30]] = json.dumps({"w": 1700})
stul_api._VYCHOZI_CACHE.clear()
sc = schema(30)
check(sc["default_saved"] is True and sc["default_selection"]["w"] == 1700 and set(sc["default_selection"]) == set(vestavene[30]), "schema: castecne ulozeny vyber se doplni vestavenymi hodnotami (slot pridany pozdeji)")
r = SH.resolve(sc["default_selection"], "cs", system=30)
check(r["valid"], "doplneny vyber je platny")

# ---------------------------------------------------------------------------------------------------------------------
print("H) pravidlo auto_on (sikme vzpery) a ulozena vychozi konfigurace (Robert 2026-10-07: vychozi stul si sam nasazoval vzpery, i kdyz byl vychozi ulozen bez nich)")


def brace_slot(sc):
    b = [s_ for s_ in sc["slots"] if s_["id"] == "braces"]
    return b[0] if b else None


reset()
SE_VZPERAMI = [sy for sy in PIDS if brace_slot(schema(sy)) is not None]          # SSE (41) vzpery nema
check({30, 35, 40} <= set(SE_VZPERAMI), "systemy 30 / 35 / 40 maji slot vzper", SE_VZPERAMI)
for sy in SE_VZPERAMI:
    reset()
    prah = int(S.pravidlo("vzpery_od_ramene", sy))
    sc_pred = schema(sy)
    ao = brace_slot(sc_pred).get("auto_on")
    check(sc_pred["default_saved"] is False and ao and ao["when"] == {"slot": "arm", "above": prah} and vestavene[sy]["arm"] > prah,
          f"system {sy}: bez ulozene vychozi konfigurace schema nese auto_on vzper (vychozi rameno {vestavene[sy]['arm']} > prah {prah}) - beze zmeny", ao)
    # ulozeno BEZ vzper pri rameni nad prahem (= tam, kde by pravidlo vzpery zapnulo) = rozhodnuti admina: pravidlo se u produktu nepouzije
    o = put(sy, {"selection": {**vestavene[sy], "braces": False}})
    check(o.status_code == 200 and o.get_json()["default_selection"]["braces"] is False and o.get_json()["default_selection"]["arm"] > prah,
          f"system {sy}: vychozi bez vzper pri rameni nad prahem se ulozi (server vzpery sam nepridava)", (o.status_code, o.get_json()))
    sc = schema(sy)
    b = brace_slot(sc)
    check(sc["default_saved"] is True and sc["default_selection"]["braces"] is False and b is not None and "auto_on" not in b,
          f"system {sy}: ulozena vychozi BEZ vzper (rameno nad prahem) = schema u produktu auto_on NEPOSILA (stul po nacteni vzpery nezapne)", b)
    check([s_ for s_ in sc["slots"] if s_["id"] != "braces"] == [s_ for s_ in sc_pred["slots"] if s_["id"] != "braces"]
          and b == {k: v for k, v in brace_slot(sc_pred).items() if k != "auto_on"}, f"system {sy}: nic jineho se ve schematu nezmenilo (ostatni sloty, slot vzper krome auto_on)")
    for druhy in SE_VZPERAMI:
        if druhy != sy:
            check("auto_on" in brace_slot(schema(druhy)), f"system {sy} ulozen bez vzper: produkt systemu {druhy} pravidlo auto_on dal ma")
    # ulozeno bez vzper, ale rameno je v ulozeni NA prahu nebo pod nim: vychozi do zony pravidla nepatri, pravidlo zustava (zakaznik, ktery rameno prodlouzi, vzpery dostane)
    for arm_ in (prah, prah - 50):
        reset()
        o = put(sy, {"selection": {**vestavene[sy], "braces": False, "arm": arm_}})
        sc = schema(sy)
        check(o.status_code == 200 and o.get_json()["default_selection"]["arm"] == arm_ and sc["default_selection"]["braces"] is False and "auto_on" in brace_slot(sc),
              f"system {sy}: ulozeno bez vzper s ramenem {arm_} (prah {prah}, pravidlo plati az NAD prahem): auto_on zustava", (o.status_code, o.get_json()))
    # ulozeno SE vzperami: pravidlo zustava (vzpery uz jsou zapnute, zakaznik je muze vypnout)
    reset()
    o = put(sy, {"selection": {**vestavene[sy], "braces": True}})
    sc = schema(sy)
    check(o.status_code == 200 and sc["default_selection"]["braces"] is True and "auto_on" in brace_slot(sc), f"system {sy}: ulozena vychozi SE vzperami: auto_on zustava", (o.status_code, o.get_json()))
    # starsi ulozeni bez klice braces (slot pridany pozdeji): vestavene False NENI rozhodnuti admina, pravidlo zustava
    reset()
    STORE[KLIC[sy]] = json.dumps({"w": 1700})
    sc = schema(sy)
    check(sc["default_saved"] is True and sc["default_selection"]["braces"] is False and "auto_on" in brace_slot(sc), f"system {sy}: ulozeni bez klice braces (starsi ulozeni): pravidlo auto_on zustava")
    # hodnota jineho typu (rucni zasah do DB; 0 neni vypnuto) rozhodnutim admina neni
    STORE[KLIC[sy]] = json.dumps({"w": 1700, "braces": 0, "arm": 700})
    stul_api._VYCHOZI_CACHE.clear()
    sc = schema(sy)
    check("auto_on" in brace_slot(sc), f"system {sy}: ulozena hodnota jineho typu (braces: 0) pravidlo nevypina")
    # rameno v ulozeni jineho typu (text) zonu pravidla nepotvrzuje: pravidlo zustava
    STORE[KLIC[sy]] = json.dumps({"w": 1700, "braces": False, "arm": "700"})
    stul_api._VYCHOZI_CACHE.clear()
    sc = schema(sy)
    check("auto_on" in brace_slot(sc), f"system {sy}: ulozene rameno jineho typu (text) pravidlo nevypina")
    # "Vratit puvodni" (DELETE) pravidlo vraci
    reset()
    put(sy, {"selection": {**vestavene[sy], "braces": False}})
    check("auto_on" not in brace_slot(schema(sy)), f"system {sy}: pred smazanim je pravidlo vypnute")
    d = admin.delete(CESTA % PIDS[sy] + "/default")
    sc = schema(sy)
    check(d.status_code == 200 and sc["default_saved"] is False and brace_slot(sc).get("auto_on") == ao, f"system {sy}: po 'Vratit puvodni' (DELETE) je pravidlo auto_on zpet, shodne s puvodnim")
reset()

print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:5]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
