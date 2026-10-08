#!/usr/bin/env python3
"""Test Vandr systemu u nas (api/vandr_system.py, tabulky vd_*, prvni komponenta kufrik-3x43-vysuv-d459; bot10, 2026-10-05).

  api/venv/bin/python3 scripts/vandr_system/test_vandr_system.py                      (cast bez DB)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/vandr_system/test_vandr_system.py                  (+ cteni registru a zapis v transakci, ktera se VZDY vrati)

NEZAVISLE: cena se pocita znovu z JSON snimku ceniku (`scripts/2026-10-05_vandr_plato/kusovnik_plato.json`) pevnym vzorcem (cena0 + zmena x soucet cena_za_mm), delky dilu se meri z vrcholu GLB.
Izolace od 1. (nativni) vetve: SQL ve vsech modulech a skriptech Vandr systemu smi sahat JEN na tabulky `vd_*` (kontrola pres AST)."""
import ast
import copy
import json
import math
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts", "2026-10-05_vandr_plato"))
import vandr_system as VS  # noqa: E402
import vandr_param as VP  # noqa: E402
import vyrob_sirku as VY  # noqa: E402

OK, FAILS = 0, []
KOD = "kufrik-3x43-vysuv-d459"
TESTKOD = "test-vd-system-rollback"


def check(cond, name, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(name)
        print("  CHYBA:", name, detail)


def vyhodi(fn, typ=ValueError):
    try:
        fn()
    except typ:
        return True
    except Exception as e:  # jina vyjimka = spatne
        print("    jina vyjimka:", type(e).__name__, e)
    return False


# ----------------------------------------------------------------------------------------------------------- 1. nazvy, SKU, cesty
check(VS.kod_na_sku(KOD) == "VDK-KUFRIK-3X43-VYSUV-D459", "kod -> SKU velkymi pismeny s predponou VDK-")
check(not VS.kod_na_sku(KOD).startswith("VD-"), "SKU VDK- se nechyta na `LIKE 'VD-%'` automatu Vandru (sestavy z FBX)")
for zly in ("", "Kufrik", "kufrik_3x43", "kufrik--x", "-kufrik", "kufrik-", "kufrik 3x43", "kufrik/../x", None):
    check(vyhodi(lambda z=zly: VS.kod_na_sku(z)), f"neplatny kod {zly!r} = ValueError")
check(VS.glb_cesta({"glb_soubor": None}) is None, "bez souboru modelu = None")
check(VS.glb_cesta({"glb_soubor": KOD + ".glb"}) == os.path.join(os.path.realpath(VS.GLB_DIR), KOD + ".glb"), "cesta modelu lezi v webapp/katalog/vandr/komponenty/")
check(os.path.realpath(VS.GLB_DIR).endswith(os.path.join("webapp", "katalog", "vandr", "komponenty")), "slozka modelu je pod chranenou predponou /katalog/vandr/")
for zly in ("../../app.py", "../param/plato_vysuvne.glb", "/etc/passwd", "a/../../b.glb"):
    check(vyhodi(lambda z=zly: VS.glb_cesta({"glb_soubor": z})), f"soubor modelu mimo slozku ({zly}) = ValueError")

# ----------------------------------------------------------------------------------------------------------- 2. cena z JSON snimku (nezavisly vzorec)
KUS = json.load(open(os.path.join(REPO, "scripts", "2026-10-05_vandr_plato", "kusovnik_plato.json"), encoding="utf-8"))
SVET0, SVMIN, SVMAX = 967.0, 359.0, 1589.0
DELKOVE = ("20x40x908_Zx4", "CUB6_917x413")


def komp_z_json():
    """Komponenta v tom tvaru, v jakem ji vraci nacti_komponentu (bez DB), ze snimku ceniku; delkove zavisle dily podle pevneho seznamu."""
    dily = []
    for i, r in enumerate(KUS["radky"], 1):
        dp = None
        if r["dil"] in DELKOVE:
            m = r["material"]
            c0 = re.match(r"[0-9.]+", r["dil"][len(m["jmeno"]):]).group(0)
            dp = {"sablona": r["dil"].replace(c0, "{L}", 1), "delka0": float(c0), "cena_za_mm": m["cena_za_mm"], "vaha_za_mm": m["vaha_za_mm"]}
        dily.append({"poradi": i, "dil": r["dil"], "ks": r["ks"], "cena_ks": r["cena"], "vaha_ks_g": r["vaha"], "delka_pravidlo": dp})
    par = {"verze": 1, "typ": "natazeni_podle_roviny", "os": 2, "rovina": 0.0, "w0_vnejsi_mm": 1057.0,
           "parametry": [{"id": "sirka_svetla", "nazev_cs": "x", "jednotka": "mm", "min": SVMIN, "max": SVMAX, "vychozi": SVET0, "krok": 1, "vnejsi_pricist_mm": 90.0}]}
    return {"kod": KOD, "mena": "CZK", "cena0": KUS["cena0"], "vaha0_g": KUS["vaha0_g"], "cenik_snimek": KUS["snimek"], "parametrizace": par, "dily": dily}


K = komp_z_json()
check(abs(sum(d["cena_ks"] * d["ks"] for d in K["dily"]) - 4677.59) < 0.005, "snimek ceniku: soucet dilu = 4 677,59 Kc (cena komponentu ve Vandru)")
SKLON = sum(r["ks"] * r["material"]["cena_za_mm"] for r in KUS["radky"] if r["dil"] in DELKOVE)
VSKLON = sum(r["ks"] * r["material"]["vaha_za_mm"] for r in KUS["radky"] if r["dil"] in DELKOVE)
check(abs(SKLON - 1.32814) < 0.00005, f"cena za 1 mm sirky = {SKLON:.5f} Kc (2 x profil 20x40 + 1 x deska CUB6 6 mm)")
check(VS.cena(K) == 4677.59 and VS.cena(K, {}) == 4677.59 and VS.cena(K, {"sirka_svetla": 967}) == 4677.59, "vychozi sirka 967 mm = 4 677,59 Kc (vychozi hodnota, prazdne i explicitni zadani)")
for S in (359, 360, 500, 700.5, 967, 1000, 1357, 1588, 1589):
    ocek = round(4677.59 + (S - SVET0) * SKLON, 2)
    check(abs(VS.cena(K, {"sirka_svetla": S}) - ocek) <= 0.011, f"cena pri svetle sirce {S} mm = {ocek} Kc", str(VS.cena(K, {"sirka_svetla": S})))
    kv = VS.kusovnik(K, {"sirka_svetla": S})
    check(abs(kv["vaha_g"] - round(7363.94 + (S - SVET0) * VSKLON, 2)) <= 0.011, f"vaha pri {S} mm")
    check(abs(sum(r["cena"] for r in kv["radky"]) - kv["cena"]) <= 0.011, f"soucet radku kusovniku = cena pri {S} mm")
check(VS.cena(K, {"sirka_svetla": 359}) < VS.cena(K) < VS.cena(K, {"sirka_svetla": 1589}), "cena roste se sirkou")
kv = VS.kusovnik(K, {"sirka_svetla": 359})
check([r["dil"] for r in kv["radky"] if r["zmena"]] == ["20x40x300_Zx4", "CUB6_309x413"], "nazvy protazenych dilu pri 359 mm (profil 300, deska 309)", str([r["dil"] for r in kv["radky"] if r["zmena"]]))
kv = VS.kusovnik(K, {"sirka_svetla": 1589})
check([r["dil"] for r in kv["radky"] if r["zmena"]] == ["20x40x1530_Zx4", "CUB6_1539x413"], "nazvy protazenych dilu pri 1589 mm (profil 1530, deska 1539)")
kv = VS.kusovnik(K, {"sirka_svetla": 700.5})
check([r["dil"] for r in kv["radky"] if r["zmena"]][0] == "20x40x641.5_Zx4", "desetinna delka v nazvu dilu (700,5 -> 641,5)", str([r["dil"] for r in kv["radky"] if r["zmena"]]))
fixni = [r for r in VS.kusovnik(K, {"sirka_svetla": 400})["radky"] if not r["zmena"]]
check(len(fixni) == 9 and all(abs(r["cena_ks"] - d["cena_ks"]) < 1e-9 for r, d in zip(fixni, [d for d in K["dily"] if not d["delka_pravidlo"]])), "pevne dily (9) se pri zmene sirky nemeni")
check(abs(VS.kusovnik(K, {"sirka_svetla": 500})["radky"][3]["cena_ks"] - (774.22 + (500 - 967) * KUS["radky"][3]["material"]["cena_za_mm"])) < 0.011, "profil se Zx4: operace (490 Kc) zustava, meni se jen material")
check(VS.kusovnik(K)["cenik_snimek"] == KUS["snimek"] and VS.kusovnik(K)["mena"] == "CZK", "kusovnik nese datum ceniku a menu")

# hodnoty parametru
check(VS.hodnoty_vychozi(K) == {"sirka_svetla": 967.0}, "vychozi hodnoty parametru")
check(VS.hodnoty_vychozi({"dily": [], "parametrizace": None}) == {}, "pevna komponenta nema parametry")
check(VS.over_hodnoty(K, None) == {"sirka_svetla": 967.0} and VS.over_hodnoty(K, {"sirka_svetla": 400}) == {"sirka_svetla": 400}, "over_hodnoty doplni vychozi a vrati hodnoty")
for zle in ({"sirka_svetla": 358.9}, {"sirka_svetla": 1589.1}, {"sirka_svetla": 0}, {"sirka_svetla": -5}, {"sirka_svetla": "900"}, {"sirka_svetla": None}, {"sirka_svetla": True},
            {"sirka_svetla": float("nan")}, {"sirka_svetla": [900]}, {"vyska": 100}, {"sirka_svetla": 900, "vyska": 100}):
    check(vyhodi(lambda z=zle: VS.cena(K, z)), f"neplatne hodnoty {zle!r} = ValueError")
check(VS.delta_mm(K, {"sirka_svetla": 1000}) == 33.0 and VS.delta_mm(K) == 0.0, "delta proti vychozi sirce")
K2 = copy.deepcopy(K)
K2["parametrizace"]["typ"] = "jiny_typ"
check(vyhodi(lambda: VS.cena(K2)), "neznamy typ parametrizace = ValueError")
check(VS.cena({"dily": [{"poradi": 1, "dil": "a", "ks": 2, "cena_ks": 10.0, "vaha_ks_g": 1.0, "delka_pravidlo": None}], "parametrizace": None, "mena": "CZK"}) == 20.0, "pevna komponenta: cena = soucet dilu")

# vedlejsi efekt: vypocet nemeni vstup (komponenta se cte z DB a sdili mezi pozadavky)
snap = json.dumps(K, sort_keys=True)
for S in (400, 1500):
    VS.kusovnik(K, {"sirka_svetla": S})
check(json.dumps(K, sort_keys=True) == snap, "vypocet ceny nemeni vstupni komponentu")

# ----------------------------------------------------------------------------------------------------------- 3. shoda s drivejsi implementaci kontrolni sceny (vyrob_sirku.kusovnik z GLB plata s nohama)
par_stary = VP.cti_glb(open(VY.VYCHOZI_GLB, "rb").read())[0]["scenes"][0]["extras"]["vandrParam"]
for S in (359, 800, 1589):
    W = S + 90.0
    stary = VY.kusovnik(par_stary, W - par_stary["w0"])
    novy = VS.kusovnik(K, {"sirka_svetla": S})
    check(abs(stary["cena"] - novy["cena"]) <= 0.011 and abs(stary["vaha_g"] - novy["vaha_g"]) <= 0.011, f"cena a vaha = kontrolni scena (plato_vysuvne.glb) pri svetle {S} mm", f"{stary['cena']} vs {novy['cena']}")
    check([r["dil"] for r in stary["radky"]] == [r["dil"] for r in novy["radky"]], f"nazvy dilu = kontrolni scena pri svetle {S} mm")

# ----------------------------------------------------------------------------------------------------------- 4. model GLB komponenty
GLB = os.path.join(VS.GLB_DIR, KOD + ".glb")
check(os.path.isfile(GLB) and 20000 < os.path.getsize(GLB) < 400000, "model komponenty existuje (jen plato, ne nohy: radove desitky KB)", str(os.path.getsize(GLB)) if os.path.isfile(GLB) else "chybi")
if os.path.isfile(GLB):
    data = open(GLB, "rb").read()
    js, blob = VP.cti_glb(data)
    par = js["scenes"][0]["extras"]["vandrParam"]
    casti = VP.sber_mesh(js, blob, "")
    check(len(casti) == 15, "model ma 15 casti (plato bez noh)", str(len(casti)))
    check(not any(c["jmeno"].startswith("45x45x1700") for c in casti), "v modelu nejsou nohy (45x45x1700)")
    check((par["w0"], par["wmin"], par["wmax"], par["svetlost0"]) == (1057.0, 449.0, 1679.0, 967.0), "vandrParam: w0 1057, rozsah 449-1679, svetlost 967", str((par["w0"], par["wmin"], par["wmax"], par["svetlost0"])))
    check(par["svetlost0"] == SVET0 and par["w0"] - par["svetlost0"] == 90.0, "svetla sirka = vnejsi - 90 mm")
    check(par["kusovnik"] is not None and abs(par["kusovnik"]["cena0"] - 4677.59) < 0.005, "GLB nese kusovnik s cenou 4 677,59")
    check(sorted(n["dil"] for n in par["natahovane"]) == ["20x40x908_Zx4", "CUB6_915x413"], "protahuji se prave 2 dily (jmena casti v modelu): profil 20x40x908 a deska CUB6_915x413", str([n["dil"] for n in par["natahovane"]]))
    spec = js["scenes"][0]["extras"].get("v3d") or js["scenes"][0]["extras"].get("v3dSpec")
    check(spec is not None or "v3d" in json.dumps(js["scenes"][0]["extras"]), "GLB nese v3d obalku pro kameru")
    # GLB vs registr: stejna cena pro stejnou sirku (vychozi i krajni)
    for S in (359, 967, 1589):
        gk = VY.kusovnik(par, (S + 90.0) - par["w0"])
        check(abs(gk["cena"] - VS.cena(K, {"sirka_svetla": S})) <= 0.011, f"cena z kusovniku v GLB = cena z registru pri svetle {S} mm", f"{gk['cena']} vs {VS.cena(K, {'sirka_svetla': S})}")
    # geometrie po natazeni na krajni sirky: delka profilu 20x40 = 300 / 1530 mm
    for W, L in ((449, 300.0), (1679, 1530.0), (1057, 908.0)):
        glb_w, bom = VY.vyrob(data, W)
        js2, blob2 = VP.cti_glb(glb_w)
        c2 = VP.sber_mesh(js2, blob2, "")
        prof = [c for c in c2 if c["jmeno"].startswith("20x40x")]
        dl = sorted(round(float(c["P"][:, 2].max() - c["P"][:, 2].min()), 1) for c in prof)
        check(len(prof) == 2 and all(abs(x - L) <= 0.2 for x in dl), f"sirka {W} mm: podelne profily 20x40 maji {L:g} mm", str(dl))
        vse = [c["P"][:, 2] for c in c2]
        check(abs(max(v.max() for v in vse) - min(v.min() for v in vse) - W) <= 0.2, f"sirka {W} mm: celkova sirka modelu", "")
        check(abs(bom["cena"] - VS.cena(K, {"sirka_svetla": W - 90})) <= 0.011, f"vyrob_sirku na GLB komponenty: cena pri {W} mm = registr", f"{bom['cena']}")

# ----------------------------------------------------------------------------------------------------------- 5. izolace od 1. vetve: SQL smi sahat jen na vd_*
TABULKA = re.compile(r"\b(?:FROM|INTO|UPDATE|JOIN|TABLE(?:\s+IF\s+NOT\s+EXISTS)?|REFERENCES)\s+`?([A-Za-z_][A-Za-z0-9_]*)`?", re.I)


def sql_retezce(cesta):
    strom = ast.parse(open(cesta, encoding="utf-8").read())
    out = []
    for n in ast.walk(strom):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.match(r"\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|SHOW|TRUNCATE|REPLACE)\b", n.value, re.I):
            out.append(n.value)
    return out


soubory = [os.path.join(REPO, "api", "vandr_system.py")] + [os.path.join(HERE, f) for f in sorted(os.listdir(HERE)) if f.endswith(".py") and f != os.path.basename(__file__)]
DOVOLENO = {"zaloz_kartu.py": {"shop_products", "audit_log"}}              # jediny skript, ktery zaklada kartu (neaktivni, bez ceny); nic jineho mimo vd_* tam neni
pocet = 0
for f in soubory:
    for sql in sql_retezce(f):
        for t in TABULKA.findall(sql):
            if t.upper() == "CURRENT_TIMESTAMP":                       # `ON UPDATE CURRENT_TIMESTAMP` v DDL neni tabulka
                continue
            pocet += 1
            check(t.lower().startswith("vd_") or t.lower() in DOVOLENO.get(os.path.basename(f), ()), f"{os.path.basename(f)}: SQL sahne na tabulku {t} (smi jen vd_*)", sql[:80].replace("\n", " "))
check(pocet >= 8, "kontrola izolace nasla SQL (vd_komponenty, vd_komponenty_dily)", str(pocet))
vse_sql = " ".join(s for f in soubory if os.path.basename(f) not in DOVOLENO for s in sql_retezce(f)).lower()
zk = " ".join(sql_retezce(os.path.join(HERE, "zaloz_kartu.py"))).lower()
check("insert into shop_products" in zk and "active" in zk and "update shop_products" not in zk and "delete" not in zk, "zaloz_kartu.py: jen INSERT neaktivni karty (zadny UPDATE ani DELETE produktu)")
ins = [x for x in sql_retezce(os.path.join(HERE, "zaloz_kartu.py")) if x.lower().startswith("insert into shop_products")]
sloupce_karty = [c.strip() for c in re.search(r"\(([^)]*)\)\s*VALUES", ins[0], re.I).group(1).split(",")] if len(ins) == 1 else None
check(sloupce_karty == ["sku", "name", "slug", "unit", "active"], "zaloz_kartu.py: karta se zaklada jen se SKU, nazvem, slugem, jednotkou a active=0 (bez ceny, modelu a kategorie)", str(sloupce_karty))
check(re.search(r"VALUES \(%s,%s,%s,%s,0\)", ins[0]) is not None if len(ins) == 1 else False, "zaloz_kartu.py: active je pevne 0 (neaktivni)")
check("vd_komponenty_dily" in vse_sql and "shop_products" not in vse_sql and "app_settings" not in vse_sql and "audit_log" not in vse_sql, "registr nesaha na shop_products / app_settings / audit_log (karta se zaklada zvlast)")
check("komponenty_varianty" not in vse_sql and "komponenta_profil_recept" not in vse_sql and "product_assemblies" not in vse_sql and "cfg_dily" not in vse_sql, "registr nesaha na nativni tabulky 1. vetve")

# ----------------------------------------------------------------------------------------------------------- 6. DB: cteni registru a zapis v transakci (VZDY rollback)
if os.environ.get("DB_HOST"):
    import pymysql
    conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 3306)), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                           database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    cur = conn.cursor()
    try:
        # schema
        cur.execute("SHOW TABLES LIKE 'vd\\_%'")
        check(sorted(list(r.values())[0] for r in cur.fetchall()) == ["vd_komponenty", "vd_komponenty_dily"], "v DB jsou prave tabulky vd_komponenty a vd_komponenty_dily")
        cur.execute("SELECT TABLE_NAME, REFERENCED_TABLE_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'vd\\_%%' AND REFERENCED_TABLE_NAME IS NOT NULL")
        fk = [(r["TABLE_NAME"], r["REFERENCED_TABLE_NAME"]) for r in cur.fetchall()]
        check(fk == [("vd_komponenty_dily", "vd_komponenty")], "jediny cizi klic: dily -> komponenty (zadna vazba na nativni tabulky)", str(fk))
        # zaregistrovana komponenta
        d = VS.nacti_komponentu(cur, KOD)
        check(d is not None, "komponenta kufrik-3x43-vysuv-d459 je v registru")
        if d:
            check(d["typ"] == "parametricky" and d["mena"] == "CZK" and abs(d["cena0"] - 4677.59) < 0.005 and abs(d["vaha0_g"] - 7363.94) < 0.005, "typ, mena, vychozi cena a vaha")
            check(d["vandr_unity_id"] == "Kufrik.3x43.vysuv.1057.459" and d["vandr_component_id"] == 2 and d["glb_soubor"] == KOD + ".glb", "odkaz na Vandr (unity_id, id) a soubor modelu")
            check(isinstance(d["hloubka_mm"], float) and d["hloubka_mm"] == 459.0 and isinstance(d["cenik_snimek"], str), "typy z DB prevedeny (Decimal -> float, date -> text)")
            json.dumps(d)                                              # musi jit serializovat (API)
            p = d["parametrizace"]["parametry"][0]
            check((p["id"], p["min"], p["vychozi"], p["max"], p["vnejsi_pricist_mm"]) == ("sirka_svetla", 359.0, 967.0, 1589.0, 90.0), "parametr sirka_svetla 359 / 967 / 1589, vnejsi = svetla + 90")
            check(d["parametrizace"]["rozsah_zdroj"]["od"] == 300.0 and d["parametrizace"]["rozsah_zdroj"]["do"] == 1530.0, "rozsah zadal Robert: delka profilu 20x40 300-1530")
            check(len(d["dily"]) == 11 and [x["poradi"] for x in d["dily"]] == list(range(1, 12)), "11 radku kusovniku v poradi")
            check(sum(1 for x in d["dily"] if x["delka_pravidlo"]) == 2, "dva delkove zavisle dily")
            for S in (359, 967, 1589):
                check(abs(VS.cena(d, {"sirka_svetla": S}) - VS.cena(K, {"sirka_svetla": S})) <= 0.011, f"cena z DB = cena ze snimku ceniku pri {S} mm")
                check(VS.kusovnik(d, {"sirka_svetla": S})["radky"] == VS.kusovnik(K, {"sirka_svetla": S})["radky"], f"kusovnik z DB = kusovnik ze snimku pri {S} mm")
            check(d["sku"] is None or d["sku"] == VS.kod_na_sku(KOD), "SKU komponenty je prazdne nebo VDK-KUFRIK-3X43-VYSUV-D459", str(d["sku"]))
        check(VS.nacti_komponentu(cur, "neexistuje-xyz") is None, "neexistujici kod = None")
        # zapis v transakci
        zaklad = {"kod": TESTKOD, "nazev_cs": "Testovaci komponenta", "typ": "pevny", "cena0": 30.0, "vaha0_g": 5.0, "cenik_snimek": "2026-10-05",
                  "dily": [{"dil": "a", "ks": 2, "cena_ks": 10.0, "vaha_ks_g": 1.0}, {"dil": "b", "ks": 1, "cena_ks": 10.0, "vaha_ks_g": 3.0}]}
        kid = VS.zaregistruj(cur, zaklad)
        t = VS.nacti_komponentu(cur, TESTKOD)
        check(t and t["id"] == kid and t["stav"] == "koncept" and t["parametrizace"] is None and VS.cena(t) == 30.0 and len(t["dily"]) == 2, "zaregistruj: nova pevna komponenta (koncept) a cena 30")
        zaklad2 = dict(zaklad, nazev_cs="Jiny nazev", cena0=25.0, vaha0_g=4.0, dily=[{"dil": "c", "ks": 5, "cena_ks": 5.0, "vaha_ks_g": 0.8}])
        check(VS.zaregistruj(cur, zaklad2) == kid, "zaregistruj podle kodu je upsert (stejne id)")
        t = VS.nacti_komponentu(cur, TESTKOD)
        check(t["nazev_cs"] == "Jiny nazev" and [x["dil"] for x in t["dily"]] == ["c"] and VS.cena(t) == 25.0, "upsert nahradi hlavicku i kusovnik")
        cur.execute("SELECT COUNT(*) AS n FROM vd_komponenty_dily WHERE komponenta_id=%s", (kid,))
        check(cur.fetchone()["n"] == 1, "stare dily se smazaly (1 radek)")
        for nazev, zle in (("soucet dilu nesedi s cenou", dict(zaklad, cena0=99.0)), ("soucet vah nesedi", dict(zaklad, vaha0_g=1.0)),
                           ("parametricka bez parametrizace", dict(zaklad, typ="parametricky")), ("neplatny typ", dict(zaklad, typ="x")),
                           ("neplatny stav", dict(zaklad, stav="aktivni")), ("neplatny kod", dict(zaklad, kod="Spatny Kod"))):
            check(vyhodi(lambda z=zle: VS.zaregistruj(cur, z)), f"zaregistruj: {nazev} = ValueError")
        cur.execute("SELECT COUNT(*) AS n FROM vd_komponenty WHERE kod=%s", (TESTKOD,))
        check(cur.fetchone()["n"] == 1, "neplatne zapisy nic nezmenily")
        cur.execute("DELETE FROM vd_komponenty WHERE id=%s", (kid,))
        cur.execute("SELECT COUNT(*) AS n FROM vd_komponenty_dily WHERE komponenta_id=%s", (kid,))
        check(cur.fetchone()["n"] == 0, "smazani komponenty smaze i jeji dily (ON DELETE CASCADE)")
        kid = VS.zaregistruj(cur, zaklad)
    finally:
        conn.rollback()                                                # nic z testu se nikdy nezapise
    cur.execute("SELECT COUNT(*) AS n FROM vd_komponenty WHERE kod=%s", (TESTKOD,))
    check(cur.fetchone()["n"] == 0, "po rollbacku testovaci komponenta v DB neni")
    conn.rollback()
    conn.close()
else:
    print("  (bez DB_HOST: cast 6 - registr v DB - preskocena; spust pres systemd-run s .env)")

# ----------------------------------------------------------------------------------------------------------- 7. verejne nedostupne (nginx 401 na cele predponu /katalog/vandr/)
try:
    for cesta in (f"/katalog/vandr/komponenty/{KOD}.glb", "/katalog/vandr/komponenty/"):
        try:
            r = urllib.request.urlopen(urllib.request.Request("https://autovestavby.logiman.cz" + cesta, method="HEAD"), timeout=15)
            kod = r.status
        except urllib.error.HTTPError as e:
            kod = e.code
        check(kod == 401, f"verejne {cesta} = 401", str(kod))
except Exception as e:  # bez site test neselhava
    print("  (sit nedostupna, kontrola 401 preskocena:", e, ")")

print(f"\n{OK} kontrol OK" + ("" if not FAILS else f"; SELHALO {len(FAILS)}"))
sys.exit(1 if FAILS else 0)
