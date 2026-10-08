#!/opt/konfigurator/api/venv/bin/python
"""Cena konfigurace: paritni test proti scene.html + jednotkove testy + mutacni kontrola (bot5, 2026-10-02).

CO SE OVERUJE
  A) jednotkove testy configurator_price.py (JS Math.round proti skutecnemu Node, jmena dilu, chybove stavy, id dilu,
     nemennost ctx, prebiti sazby montaze, pravidlo koeficientu sceny).
  B) PARITA: >= 400 scenaru (pevny seed) z REALNYCH dilu katalogu (fixture z /api/katalog) + syntetickych hranovych dilu
     (cena .5, deska bez ceny, profil bez ceny, ...) - Python price_entries musi dat PRESNE totez co SKUTECNA funkce
     computeAssemblyBomAndPrice ze scene.html (reference_scena.js ji pousti v Node; jen mereni geometrie je nahrazeno
     hodnotami scenare). Porovnava se cely `bom` (radek po radku) a vsechna pole `price_summary`, bez tolerance.
  C) MUTACE: umyslne pozmenene verze modulu (Python round, balne pred zaokrouhlenim, koeficient i na rez, ...) MUSI selhat.
Bez DB, bez Flasku, nic nezapisuje. Fixture se obnovuje obnov_fixture.py (DB jen cteni).

Spusteni: api/venv/bin/python3 scripts/2026-10-02_konfigurator_cena_testy/test_cena_parita.py
Kandidat pred nasazenim: CFG_PRICE_PY=/cesta/k/configurator_price.py  (volitelne SCENE_HTML=..., SHARED_JS=... pro jinou scenu)
Rychle:                   POCET_SCENARU=100        Zatez (jine nahodne scenare): POCET_SCENARU=3000 SEED=1
"""
import copy
import importlib.util
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
CFG_PY = os.environ.get("CFG_PRICE_PY", os.path.join(REPO, "api", "configurator_price.py"))
FIXTURE = os.path.join(HERE, "katalog_fixture.json")
REFERENCE = os.path.join(HERE, "reference_scena.js")
POCET = int(os.environ.get("POCET_SCENARU", "400"))
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


def nacti_modul(cesta, jmeno="configurator_price_pod_testem"):
    spec = importlib.util.spec_from_file_location(jmeno, cesta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def nacti_mutant(zdroj, nahrady, jmeno):
    """Modul z pozmeneneho zdrojoveho textu; kazda nahrada se musi trefit PRAVE JEDNOU (jinak test hlasi chybu mutace)."""
    for stare, nove in nahrady:
        if zdroj.count(stare) != 1:
            raise SystemExit(f"CHYBA TESTU: mutaci {jmeno} nelze aplikovat, vzor nalezen {zdroj.count(stare)}x:\n{stare}")
        zdroj = zdroj.replace(stare, nove)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(zdroj)
        cesta = f.name
    try:
        return nacti_modul(cesta, jmeno)
    finally:
        os.unlink(cesta)


def node(skript_nebo_soubor, vstup, env_extra=None):
    """Spusti Node s CISTYM prostredim (zadne DB promenne) a vrati stdout."""
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}
    for k in ("SCENE_HTML", "SHARED_JS"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    env.update(env_extra or {})
    r = subprocess.run(skript_nebo_soubor, input=vstup, capture_output=True, text=True, env=env, timeout=300)
    if r.returncode != 0:
        raise SystemExit("CHYBA TESTU: Node selhal:\n" + r.stderr[:1500])
    return r.stdout


if not os.path.exists(CFG_PY):
    over(f"0 modul configurator_price.py existuje ({CFG_PY})", False, "soubor chybi - nastav CFG_PRICE_PY na kandidata")
    print("\nVYSLEDEK cena konfigurace - parita se scenou: 0/1 OK")
    sys.exit(1)
if not os.path.exists(FIXTURE):
    raise SystemExit("CHYBA TESTU: chybi katalog_fixture.json - spust obnov_fixture.py")

CFG = nacti_modul(CFG_PY)
ZDROJ = open(CFG_PY, encoding="utf-8").read()
FIX = json.load(open(FIXTURE, encoding="utf-8"))

# ------------------------------------------------------------------------------------------------------------ katalog
DILY = {p["id"]: copy.deepcopy(p) for p in FIX["parts"]}


def syntet(id_, nazev, **kw):
    d = {"id": id_, "name": nazev, "layer": "produkt", "sku": None, "length_mm": None, "cross_section_mm": [None, None],
         "weight_kg": None, "price_czk": None, "price_per_cut_czk": None, "is_board_material": False, "scene_coef": False,
         "source": "syntet", "unit": None, "price_basis": None}
    d.update(kw)
    return d


SYNT = [
    syntet("synt_dil_2_5", "Syntet dil 2,5", price_czk=2.5, weight_kg=0.0105),
    syntet("synt_dil_3_5", "Syntet dil 3,5", price_czk=3.5, weight_kg=0.02),
    syntet("synt_dil_0_5", "Syntet dil 0,5", price_czk=0.5),
    syntet("synt_dil_10", "Syntet dil 10", price_czk=10.0, weight_kg=1.0),
    syntet("synt_dil_nula", "Syntet dil zdarma", price_czk=0.0, weight_kg=0.5),
    syntet("synt_dil_bez_ceny", "Syntet dil bez ceny", price_czk=None, weight_kg=1.5),
    syntet("synt_dil_sku", "Syntet dil se SKU", sku="SK-1", price_czk=7.75, weight_kg=0.3),
    syntet("synt_dil_sku_v_nazvu", "Syntet SK-2 dil", sku="SK-2", price_czk=8.25),
    syntet("synt_dil_rez", "Syntet dil s rezem", price_czk=4.0, price_per_cut_czk=3.5),
    syntet("synt_profil_1m", "Syntet profil 1 m", layer="alu", length_mm=1000.0, cross_section_mm=[30.0, 30.0],
           price_czk=1000.0, weight_kg=1.0, price_per_cut_czk=7.5, scene_coef=True, source="syntet"),
    syntet("synt_profil_3m", "Profil Syntet 3 m", layer="alu", length_mm=3000.0, cross_section_mm=[40.0, 40.0],
           price_czk=1234.57, weight_kg=3.333, price_per_cut_czk=12.5, scene_coef=True),
    syntet("synt_profil_bez_ceny", "Syntet profil bez ceny", layer="alu", length_mm=3000.0, cross_section_mm=[20.0, 20.0],
           price_czk=None, weight_kg=2.0),
    syntet("synt_deska_m2", "Syntet deska", is_board_material=True, price_czk=1000.0, weight_kg=2.5, unit="m2"),
    syntet("synt_deska_1234", "Syntet deska 2", is_board_material=True, price_czk=1234.5678, weight_kg=None, unit="m2"),
    syntet("synt_deska_bez_ceny", "Syntet deska bez ceny", is_board_material=True, price_czk=None, weight_kg=1.0),
]
for d in SYNT:
    DILY[d["id"]] = d


def je_profil(p):
    cs = p.get("cross_section_mm")
    return bool(p.get("length_mm")) and bool(cs) and cs[0] is not None


REAL = [p for p in FIX["parts"]]
PROFILY = [p for p in REAL if je_profil(p)]
DESKY = [p for p in REAL if p["is_board_material"]]
OSTATNI_S_CENOU = [p for p in REAL if not je_profil(p) and not p["is_board_material"] and p["price_czk"] is not None]
OSTATNI_BEZ_CENY = [p for p in REAL if not je_profil(p) and not p["is_board_material"] and p["price_czk"] is None]
SYNT_DILY = [p for p in SYNT if not je_profil(p) and not p["is_board_material"]]
SYNT_PROFILY = [p for p in SYNT if je_profil(p)]
SYNT_DESKY = [p for p in SYNT if p["is_board_material"]]

ZIVE_SAZBY = copy.deepcopy(FIX["pricing"])
SAZBY = [
    ZIVE_SAZBY,
    {"joint_price_czk": 110.0, "profile_flat_fee_czk": 5.0, "packaging_pct": 0.0, "montaz_pct": 0.0, "scene_price_coefficient": 1.0, "accessories": []},
    {"joint_price_czk": 0.0, "profile_flat_fee_czk": 0.0, "packaging_pct": 5.0, "montaz_pct": 5.0, "scene_price_coefficient": 1.5,
     "accessories": [{"id": 1, "name": "a", "price_czk": 3.5, "qty_per_joint": 2.0}, {"id": 2, "name": "b", "price_czk": 12.25, "qty_per_joint": 0.5}]},
    {"joint_price_czk": 99.9, "profile_flat_fee_czk": 7.3, "packaging_pct": 3.0, "montaz_pct": 12.5, "scene_price_coefficient": 1.25,
     "accessories": [{"id": 3, "name": "c", "price_czk": 0.85, "qty_per_joint": 3.0}]},
    {},                                    # nic nastaveno: vsude || 0 a koeficient || 1
    {"accessories": None, "joint_price_czk": 10, "packaging_pct": 10, "montaz_pct": 10},
]


def ctx_pro(sazby):
    return {"parts": DILY, "pricing": sazby, "joint_rule_version": FIX["joint_rule_version"]}


def id_pro_vstup(rnd, p):
    """product_id v podobe, jakou muze poslat compose: cislo (shop_products.id), text 'product_N' nebo cfg id."""
    if p["id"].startswith("product_"):
        return int(p["id"].split("_", 1)[1]) if rnd.random() < 0.5 else p["id"]
    return p["id"]


def nahodna_delka(rnd, p):
    druh = rnd.choice(["katalog", "pul", "cela", "int", "float", "pul_mm", "mala", "velka", "desetina"])
    dl = p["length_mm"]
    return {"katalog": dl, "pul": dl / 2, "cela": 3000.0, "int": float(rnd.randint(10, 3200)),
            "float": round(rnd.uniform(10, 3200), 3), "pul_mm": rnd.randint(10, 3200) + 0.5, "mala": 0.4,
            "velka": 5000.0, "desetina": rnd.randint(10, 3200) + 0.1}[druh]


def nahodny_rozmer(rnd):
    return rnd.choice([float(rnd.randint(50, 2800)), rnd.randint(50, 2800) + 0.5, round(rnd.uniform(50, 2800), 2), 50.0, 0.4])


def nahodny_dil(rnd):
    r = rnd.random()
    if r < 0.28:
        return rnd.choice(PROFILY)
    if r < 0.34:
        return rnd.choice(DESKY)
    if r < 0.50:
        return rnd.choice(OSTATNI_S_CENOU)
    if r < 0.52:
        return rnd.choice(OSTATNI_BEZ_CENY)
    if r < 0.66:
        return rnd.choice(SYNT_DILY)
    if r < 0.84:
        return rnd.choice(SYNT_PROFILY)
    return rnd.choice(SYNT_DESKY)


def vstup_dilu(rnd, p, nulove_spoje):
    e = {"product_id": id_pro_vstup(rnd, p)}
    if p["is_board_material"]:
        e["width_mm"], e["height_mm"] = nahodny_rozmer(rnd), nahodny_rozmer(rnd)
    elif je_profil(p):
        e["length_mm"] = nahodna_delka(rnd, p)
    e["joint_count"] = 0 if nulove_spoje else rnd.choice([0, 0, 1, 2, 3, 4, 5, 8])
    e["custom_color"] = rnd.choice([None, None, None, "", "#ff0000", "#00aa00"])
    return e


def nahodny_scenar(rnd):
    sazby = rnd.choice(SAZBY)
    nulove_spoje = rnd.random() < 0.3
    n = rnd.choice([0, 1, 2, 3, 5, 8, 12, 20, 30])
    entries = []
    while len(entries) < n:
        p = nahodny_dil(rnd)
        e = vstup_dilu(rnd, p, nulove_spoje)
        entries.append(e)
        if rnd.random() < 0.25 and len(entries) < n:            # opakovani dilu -> seskupeni radku kusovniku
            e2 = dict(e)
            if "length_mm" in e2 and rnd.random() < 0.5:
                e2["length_mm"] = round(e2["length_mm"] + rnd.choice([0.0, 0.2, -0.2, 0.3]), 3)     # blizka delka (stejne zaokrouhleni?)
            if rnd.random() < 0.3:
                e2["custom_color"] = rnd.choice([None, "#ff0000"])
            entries.append(e2)
    return {"pricing": sazby, "entries": entries}


def ruzne(prvni, ods):
    return {"pricing": prvni, "entries": ods}


RUCNI = [
    ruzne(ZIVE_SAZBY, []),
    ruzne({}, []),
    ruzne(ZIVE_SAZBY, [{"product_id": PROFILY[0]["id"], "length_mm": PROFILY[0]["length_mm"], "joint_count": 2}]),
    # zaokrouhleni .5: cena dilu 2,5 / 3,5 / 0,5 (JS nahoru, Python banker's k sudemu)
    ruzne(SAZBY[1], [{"product_id": "synt_dil_2_5"}, {"product_id": "synt_dil_3_5"}, {"product_id": "synt_dil_0_5"}]),
    # profil 1000 mm za 1000 Kc: delka 2,5 mm = 2,5 Kc, 3,5 mm = 3,5 Kc, cena rezu 7,5
    ruzne(SAZBY[1], [{"product_id": "synt_profil_1m", "length_mm": 2.5}, {"product_id": "synt_profil_1m", "length_mm": 3.5}]),
    # balne .5 (10 Kc x 5 % = 0,5) a montaz .5 (11 x 5 % = 0,55 / z jine zakladny x,5)
    ruzne({"packaging_pct": 5.0, "montaz_pct": 5.0}, [{"product_id": "synt_dil_10"}]),
    ruzne({"packaging_pct": 5.0, "montaz_pct": 50.0}, [{"product_id": "synt_dil_10"}, {"product_id": "synt_dil_3_5"}]),
    ruzne({"packaging_pct": 10.0, "montaz_pct": 10.0}, [{"product_id": "synt_dil_3_5"}, {"product_id": "synt_dil_2_5"}]),
    # deska 50 x 50 mm za 1000 Kc/m2 = 2,5 Kc, deska bez ceny, deska s dlouhym desetinnym cislem
    ruzne(SAZBY[1], [{"product_id": "synt_deska_m2", "width_mm": 50, "height_mm": 50}, {"product_id": "synt_deska_bez_ceny", "width_mm": 100, "height_mm": 100},
                     {"product_id": "synt_deska_1234", "width_mm": 333.3, "height_mm": 777.7}]),
    # stejny profil: shodna delka (seskupit), blizka delka (stejny radek, cena prvniho), jina delka, jina barva
    ruzne(ZIVE_SAZBY, [{"product_id": "synt_profil_3m", "length_mm": 1000.1}, {"product_id": "synt_profil_3m", "length_mm": 1000.4},
                       {"product_id": "synt_profil_3m", "length_mm": 1000.1, "custom_color": "#ff0000"}, {"product_id": "synt_profil_3m", "length_mm": 1500},
                       {"product_id": "synt_profil_3m", "length_mm": 1000.1}]),
    # dily bez ceny, bez vahy, bez profilu, bez spoju
    ruzne(SAZBY[2], [{"product_id": "synt_dil_bez_ceny"}, {"product_id": "synt_profil_bez_ceny", "length_mm": 900}, {"product_id": "synt_dil_sku"},
                     {"product_id": "synt_dil_sku_v_nazvu"}, {"product_id": "synt_dil_nula"}]),
    # prislusenstvi na spoj (qty_per_joint x spoje x cena) a cena rezu u ne-profilu
    ruzne(SAZBY[2], [{"product_id": "synt_dil_rez", "joint_count": 3}, {"product_id": "synt_profil_1m", "length_mm": 1234.5, "joint_count": 4}]),
    ruzne(SAZBY[3], [{"product_id": "synt_dil_rez", "joint_count": 7}] * 3),
]

# ------------------------------------------------------------------------------------------------------------ A) jednotkove testy
print("== A jednotkove testy")
ctx = ctx_pro(ZIVE_SAZBY)

# A1: _js_round proti SKUTECNEMU Math.round v Node (vc. .5 a zapornych cisel)
rnd = random.Random(7)
hodnoty = [0.5, 1.5, 2.5, -0.5, -1.5, -2.5, 0.49999999999999994, 1e15 + 0.5, 12345.5, 0.0, -0.0, 4.4999999999999, 99999.5]
hodnoty += [rnd.randint(0, 100000) + 0.5 for _ in range(300)] + [round(rnd.uniform(-1000, 100000), 3) for _ in range(300)]
js = json.loads(node(["node", "-e", "let a=JSON.parse(require('fs').readFileSync(0,'utf8'));console.log(JSON.stringify(a.map(x=>Math.round(x))))"],
                     json.dumps(hodnoty)))
nesedi = [(h, j, CFG._js_round(h)) for h, j in zip(hodnoty, js) if CFG._js_round(h) != j]
over(f"A1 _js_round == JS Math.round na {len(hodnoty)} hodnotach (.5, zaporna, hranove)", not nesedi, nesedi[:5])
over("A1b Python round() by dalo jinak (test ma smysl): round(2.5) != Math.round(2.5)", round(2.5) != 3, None)

# A2: jmeno dilu
over("A2 nazev dilu: bez SKU = nazev, SKU mimo nazev se pripoji, SKU uz v nazvu se nezdvojuje, chybi nazev = 'díl'",
     CFG._part_display_name({"name": "Deska"}) == "Deska" and CFG._part_display_name({"name": "Deska", "sku": "PR10"}) == "Deska [PR10]"
     and CFG._part_display_name({"name": "Deska PR10", "sku": "PR10"}) == "Deska PR10" and CFG._part_display_name({}) == "díl", None)

# A3: chybove stavy (zadne tiche vyrazeni dilu)
def chyba(entries, ocekavany_kod, **kw):
    try:
        CFG.price_entries(entries, ctx, **kw)
    except CFG.ConfiguratorPriceError as e:
        return e.code == ocekavany_kod and bool(str(e)), (e.code, str(e))
    except Exception as e:                       # noqa: BLE001
        return False, repr(e)
    return False, "bez vyjimky"


PRF = "synt_profil_3m"
for popis, entries, kod in [
    ("neznamy dil (text)", [{"product_id": "neexistuje_xyz"}], "neznamy_dil"),
    ("neznamy dil (cislo)", [{"product_id": 999999999}], "neznamy_dil"),
    ("polozka bez product_id", [{"length_mm": 100}], "chybi_dil"),
    ("profil bez delky", [{"product_id": PRF}], "chybi_rozmer"),
    ("profil s delkou 0", [{"product_id": PRF, "length_mm": 0}], "neplatne_cislo"),
    ("profil se zapornou delkou", [{"product_id": PRF, "length_mm": -5}], "neplatne_cislo"),
    ("profil s delkou NaN", [{"product_id": PRF, "length_mm": float("nan")}], "neplatne_cislo"),
    ("profil s delkou 'abc'", [{"product_id": PRF, "length_mm": "abc"}], "neplatne_cislo"),
    ("profil s delkou True", [{"product_id": PRF, "length_mm": True}], "chybi_rozmer"),
    ("deska bez rozmeru", [{"product_id": "synt_deska_m2"}], "chybi_rozmer"),
    ("deska jen se sirkou", [{"product_id": "synt_deska_m2", "width_mm": 100}], "chybi_rozmer"),
    ("deska s nulovou vyskou", [{"product_id": "synt_deska_m2", "width_mm": 100, "height_mm": 0}], "neplatne_cislo"),
    ("zaporny pocet spoju", [{"product_id": "synt_dil_10", "joint_count": -1}], "neplatne_cislo"),
    ("necely pocet spoju", [{"product_id": "synt_dil_10", "joint_count": 1.5}], "neplatne_cislo"),
    ("pocet spoju text", [{"product_id": "synt_dil_10", "joint_count": "dva"}], "neplatne_cislo"),
]:
    ok, detail = chyba(entries, kod)
    over(f"A3 chyba: {popis} -> ConfiguratorPriceError({kod}) s ceskou zpravou", ok, detail)
ok, detail = chyba([{"product_id": "synt_dil_bez_ceny"}], "chybi_cena", strict_prices=True)
over("A3b strict_prices=True: dil bez ceny je chyba", ok, detail)
r0 = CFG.price_entries([{"product_id": "synt_dil_bez_ceny"}, {"product_id": "synt_deska_bez_ceny", "width_mm": 10, "height_mm": 10}], ctx)
over("A3c strict_prices=False (jako scena): dil bez ceny = 0 Kc a varovani (2 dily -> 2 varovani, cena 0)",
     len(r0["warnings"]) == 2 and r0["price_summary"]["total_czk"] == 0, r0)

# A4: id dilu
ids = {
    "cislo": {"product_id": 3671, "width_mm": 100, "height_mm": 100}, "text": {"product_id": "product_3671", "width_mm": 100, "height_mm": 100},
    "cislo_text": {"product_id": "3671", "width_mm": 100, "height_mm": 100}, "alias": {"part_id": "product_3671", "width_mm": 100, "height_mm": 100},
}
if "product_3671" in DILY:
    vys = {k: CFG.price_entries([v], ctx)["bom"] for k, v in ids.items()}
    over("A4 id dilu: cislo, 'product_N', '3671' i alias part_id vedou na stejny dil a stejny kusovnik", len({json.dumps(v) for v in vys.values()}) == 1, vys)
else:
    over("A4 id dilu (product_3671 v katalogu chybi - test preskocen)", True)
over("A4b id cfg dilu (text) funguje", bool(CFG.price_entries([{"product_id": PROFILY[0]["id"], "length_mm": PROFILY[0]["length_mm"]}], ctx)["bom"]), None)

# A5: nemennost ctx a opakovatelnost
pred = copy.deepcopy(ctx)
vstup = [{"product_id": PROFILY[0]["id"], "length_mm": 1234.5, "joint_count": 2}, {"product_id": "synt_deska_m2", "width_mm": 300, "height_mm": 400}]
vstup_pred = copy.deepcopy(vstup)
a, b = CFG.price_entries(vstup, ctx), CFG.price_entries(vstup, ctx)
over("A5 price_entries nemeni ctx ani vstup a je deterministicka (2 volani = totez)", pred == ctx and a == b and vstup == vstup_pred, None)

# A6: prebiti sazby montaze
zakl = CFG.price_entries(vstup, ctx)["price_summary"]
prebit = CFG.price_entries(vstup, ctx, montaz_pct=10)["price_summary"]
shoda_bez_montaze = {k: v for k, v in zakl.items() if k not in ("montaz_czk", "montaz_pct_applied")} == {k: v for k, v in prebit.items() if k not in ("montaz_czk", "montaz_pct_applied")}
over("A6 montaz_pct=10 meni JEN montaz_czk a montaz_pct_applied (total a ostatni pole beze zmeny)",
     shoda_bez_montaze and prebit["montaz_pct_applied"] == 10 and prebit["montaz_czk"] == CFG._js_round(prebit["total_czk"] * 10 / 100)
     and CFG.price_entries(vstup, ctx, montaz_pct=0)["price_summary"]["montaz_czk"] == 0, (zakl, prebit))

# A7: typy vysledku (cele Kc jako int, kusovnik)
ps = CFG.price_entries(vstup, ctx)
over("A7 castky jsou cele Kc (int), BOM radek ma name/dim/qty/unit_price/total",
     all(isinstance(ps["price_summary"][k], int) for k in ("material_czk", "cut_czk", "joint_czk", "accessory_czk", "packaging_czk", "total_czk", "montaz_czk"))
     and all(set(r) == {"name", "dim", "qty", "unit_price", "total"} for r in ps["bom"]), ps)
over("A7b prazdna konfigurace = nulovy souhrn a prazdny kusovnik (count 0, total 0, weight 0)",
     CFG.price_entries([], ctx)["bom"] == [] and CFG.price_entries([], ctx)["price_summary"]["total_czk"] == 0 and CFG.price_entries([], ctx)["price_summary"]["count"] == 0, None)

# A8: koeficient sceny (pravidlo jako /api/katalog): jen scene_coef, rez se nenasobi, None se nemeni, koef 1.0 nic nemeni
tst = [syntet("k1", "A", price_czk=100.0, scene_coef=True, price_per_cut_czk=10.0), syntet("k2", "B", price_czk=100.0, scene_coef=False, price_per_cut_czk=10.0),
       syntet("k3", "C", price_czk=None, scene_coef=True), syntet("k4", "D", price_czk=1.005, scene_coef=True), syntet("k5", "E", price_czk=0.0, scene_coef=True)]
kopie = copy.deepcopy(tst)
CFG.apply_scene_coefficient(tst, 1.0)
over("A8a koeficient 1.0 nic nemeni", tst == kopie, tst)
CFG.apply_scene_coefficient(tst, 1.25)
oc = [round(100.0 * 1.25, 2), 100.0, None, round(1.005 * 1.25, 2), 0.0]
over("A8b koeficient 1.25: jen scene_coef dily (125.0), ostatni a None beze zmeny, cena rezu se nenasobi (10.0)",
     [p["price_czk"] for p in tst] == oc and [p["price_per_cut_czk"] for p in tst[:2]] == [10.0, 10.0], [p["price_czk"] for p in tst])

# ------------------------------------------------------------------------------------------------------------ B) parita se scenou
print(f"== B parita proti scene.html ({POCET} nahodnych + {len(RUCNI)} rucnich scenaru, pevny seed)")
rnd = random.Random(int(os.environ.get("SEED", "20261002")))
scenare = RUCNI + [nahodny_scenar(rnd) for _ in range(POCET)]

# vstup do Node: dily po rozresenem id (reference zna jen id dilu ze sceny), scenare s id
js_scenare = []
for sc in scenare:
    js_entries = []
    for e in sc["entries"]:
        pid = e["product_id"]
        key = str(pid)
        if key not in DILY:
            key = f"product_{int(pid)}"
        js_entries.append({"id": key, "length_mm": e.get("length_mm"), "width_mm": e.get("width_mm"), "height_mm": e.get("height_mm"),
                           "joint_count": e.get("joint_count"), "custom_color": e.get("custom_color")})
    js_scenare.append({"pricing": sc["pricing"], "entries": js_entries})
js_dily = {k: {kk: vv for kk, vv in v.items()} for k, v in DILY.items()}
odpoved = json.loads(node(["node", REFERENCE], json.dumps({"parts": js_dily, "scenarios": js_scenare})))
over(f"B0 JOINT_RULE_VERSION ve scene.html ({odpoved['joint_rule_version']}) == verze v katalogu pravidel/fixture ({FIX['joint_rule_version']})",
     odpoved["joint_rule_version"] == FIX["joint_rule_version"], odpoved["joint_rule_version"])


def porovnej(py, js_res):
    chyby = []
    if py["bom"] != js_res["bom"]:
        chyby.append(("bom", py["bom"], js_res["bom"]))
    pk, jk = py["price_summary"], js_res["price_summary"]
    if set(pk) != set(jk):
        chyby.append(("klice", sorted(pk), sorted(jk)))
    for k in jk:
        if k in pk and pk[k] != jk[k]:
            chyby.append((k, pk[k], jk[k]))
    return chyby


def spust_parita(modul):
    """-> (pocet scenaru bez rozdilu, prvni rozdily, pocet porovnanych radku kusovniku, pocet porovnanych poli souhrnu)"""
    shod, rozdily, radku, poli = 0, [], 0, 0
    for i, (sc, js_res) in enumerate(zip(scenare, odpoved["vysledky"])):
        try:
            py = modul.price_entries(sc["entries"], {"parts": DILY, "pricing": sc["pricing"], "joint_rule_version": FIX["joint_rule_version"]})
        except Exception as e:             # noqa: BLE001 - mutant muze padnout; to je take zachyceni
            rozdily.append((i, "VYJIMKA", repr(e)))
            continue
        radku += len(js_res["bom"])
        poli += len(js_res["price_summary"])
        ch = porovnej(py, js_res)
        if ch:
            if len(rozdily) < 3:
                rozdily.append((i, ch[0]))
        else:
            shod += 1
    return shod, rozdily, radku, poli


shod, rozdily, radku, poli = spust_parita(CFG)
over(f"B1 PARITA: vsech {len(scenare)} scenaru shodne se scenou (bom radek po radku + vsechna pole price_summary, bez tolerance); "
     f"porovnano {radku} radku kusovniku a {poli} poli souhrnu", shod == len(scenare), rozdily)
over("B2 pokryti: scenare obsahuji profily, desky, dily bez ceny, spoje, balne i montazi, nulove a prazdne konfigurace (nenulove castky ve vysledcich scény)",
     any(r["price_summary"]["joint_czk"] > 0 for r in odpoved["vysledky"]) and any(r["price_summary"]["packaging_czk"] > 0 for r in odpoved["vysledky"])
     and any(r["price_summary"]["montaz_czk"] > 0 for r in odpoved["vysledky"]) and any(r["price_summary"]["profile_flat_fee_czk"] > 0 for r in odpoved["vysledky"])
     and any(r["price_summary"]["cut_czk"] > 0 for r in odpoved["vysledky"]) and any(r["price_summary"]["accessory_czk"] > 0 for r in odpoved["vysledky"])
     and any(r["price_summary"]["count"] == 0 for r in odpoved["vysledky"]) and any(r["price_summary"]["joint_count"] == 0 and r["price_summary"]["count"] > 0 for r in odpoved["vysledky"])
     and any(any("×" in b["dim"] for b in r["bom"]) for r in odpoved["vysledky"]) and any(any(b["qty"] > 1 for b in r["bom"]) for r in odpoved["vysledky"]),
     None)

# ------------------------------------------------------------------------------------------------------------ C) mutace
print("== C mutace (pozmenene verze modulu MUSI selhat)")
MUTACE = [
    ("M1 Python round() misto JS Math.round", [("return fl + 1 if (x - fl) >= 0.5 else fl", "return round(x)")]),
    ("M2 balne z nezaokrouhlenych slozek (ne z uz zaokrouhlenych)",
     [("packaging_czk = _js_round(subtotal_czk * packaging_pct / 100)",
       "packaging_czk = _js_round((total_material + total_cut + total_profile_flat_fee + total_joint_price + total_accessory) * packaging_pct / 100)")]),
    ("M4 cena skupiny kusovniku z POSLEDNIHO dilu misto prvniho", [('            group["qty"] += 1', '            group["qty"] += 1\n            group["unit_price"] = _js_round(values["price"]) if values["price"] is not None else 0')]),
    ("M5 montaz z mezisouctu bez balneho misto z ceny po balnem", [("montaz_czk = _js_round(grand_total * montaz_pct / 100)", "montaz_czk = _js_round(subtotal_czk * montaz_pct / 100)")]),
    ("M6 desky se nepocitaji jako material (ale jako prislusenstvi)", [('return _is_profile(part) or bool(part.get("is_board_material"))', "return _is_profile(part)")]),
    ("M7 cena profilu podle delky / 1000 misto delky / delka dilu v katalogu", [('factor = length_mm / part["length_mm"]', "factor = length_mm / 1000")]),
    ("M8 cena rezu jen u profilu (scena ji bere u kazdeho dilu)", [('total_cut = total_cut + (part.get("price_per_cut_czk") or 0)', 'total_cut = total_cut + ((part.get("price_per_cut_czk") or 0) if _is_profile(part) else 0)')]),
    ("M9 prislusenstvi na spoj bez qty_per_joint", [('(acc.get("qty_per_joint") or 0) * total_joints * (acc.get("price_czk") or 0)', '1 * total_joints * (acc.get("price_czk") or 0)')]),
    ("M10 hmotnost zaokrouhlena Python round(x, 3)", [("_js_round(total_w * 1000) / 1000", "round(total_w, 3)")]),
    ("M11 seskupeni kusovniku bez barvy", [("key = f\"{part['id']}|{len_rounded}|{board_key}|{color}\"", "key = f\"{part['id']}|{len_rounded}|{board_key}\"")]),
    ("M12 balne se nepripocte k total", [("grand_total = subtotal_czk + packaging_czk", "grand_total = subtotal_czk")]),
    ("M13 paušal za profil se pocita ze vsech dilu (ne jen z profilu)", [("total_profiles = total_profiles + (1 if _is_profile(part) else 0)", "total_profiles = total_profiles + 1")]),
]
for popis, nahrady in MUTACE:
    mut = nacti_mutant(ZDROJ, nahrady, "mutant_" + popis[:3].strip())
    m_shod, m_rozdily, _r, _p = spust_parita(mut)
    over(f"C {popis}: parita selze ({len(scenare) - m_shod} z {len(scenare)} scenaru se lisi) -> mutace ZACHYCENA", m_shod < len(scenare), None)

# M3 (koeficient i na cenu rezu) zasahuje apply_scene_coefficient, ne price_entries -> zachyti ho jednotkovy test A8
mut3 = nacti_mutant(ZDROJ, [('part["price_czk"] = round(base * coef, 2)', 'part["price_czk"] = round(base * coef, 2)\n            part["price_per_cut_czk"] = round((part.get("price_per_cut_czk") or 0) * coef, 2)')], "mutant_M3")
tst3 = [syntet("k1", "A", price_czk=100.0, scene_coef=True, price_per_cut_czk=10.0)]
mut3.apply_scene_coefficient(tst3, 1.25)
over("C M3 koeficient sceny i na cenu rezu: jednotkovy test A8b ho zachyti (rez 10.0 -> 12.5) -> mutace ZACHYCENA", tst3[0]["price_per_cut_czk"] != 10.0, tst3)

ok = sum(vysl)
print(f"\nVYSLEDEK cena konfigurace - parita se scenou: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
