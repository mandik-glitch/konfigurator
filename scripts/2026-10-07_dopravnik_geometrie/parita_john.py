"""Zlaty test (bot8, 2026-10-07): moje prepsane pravidla api_kandidat/dopravnik_konfigurator.py musi davat PRESNE stejny vysledek jako Johnuv resolve (~1600 vyberu: 78 hotovych karet, nahodne, nesmyslne vstupy).
Spusteni: python3 scripts/2026-10-07_dopravnik_geometrie/parita_john.py   (cte Johnuv vystup z /home/openai1/..., nic nezapisuje)"""
import csv, json, math, random, sys, importlib.util
import os
J = os.environ.get("JOHN_DIR", "/home/openai1/konfigurator/vystupy/generator_dopravniku")          # Johnuv vystup (jen cteni)
SUPPORT = os.environ.get("JOHN_PODKLADY", "/home/openai1/konfigurator/ukoly/podklady/dopravnik")
sys.path.insert(0, J)
import dopravnik_konfigurator as john
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("moje", os.path.join(HERE, "api_kandidat", "dopravnik_konfigurator.py"))
moje = importlib.util.module_from_spec(spec); spec.loader.exec_module(moje)
catalog = json.load(open(J + "/nahled/cenik.json")); geometry = json.load(open(J + "/nahled/geometrie.json"))
samples = []
for card in csv.DictReader(open(SUPPORT + "/hotove_dopravniky.csv")):
    rtype = {"Hliník hladký": "alu", "Hliník vroubkovaný": "knurl", "Ocel": "steel"}[card["typ_valecku"]]
    samples.append({"rtype": rtype, "width": int(card["sirka_valecku_mm"]), "len": int(card["delka_dopravniku_mm"]), "pitch": int(card["rozteč_mm"]), "h": int(card["vyska_mm"])})
rng = random.Random(7102026)
for i in range(1500):
    samples.append({"rtype": rng.choice(["alu", "knurl", "steel"]), "width": rng.choice([290, 440, 590, 790, 990]), "len": rng.randrange(1000, 6001, 100), "pitch": rng.randrange(75, 301, 25), "h": rng.randrange(570, 871, 10),
                    "legs": rng.choice(["auto", 4, 6, 8]), "frame": rng.choice(["full", "cross", "none"])})
samples += [{}, {"rtype": 5, "width": "abc", "len": None, "pitch": True, "h": [1], "legs": "x", "frame": "zzz", "guide": "both", "guidetype": "60", "nesmysl": 1}, {"len": 3333, "pitch": 111, "h": 1500}, {"len": 1050, "pitch": 87.5, "h": 575},
            {"rtype": "steel", "width": 1195, "len": 7000, "legs": 4}, {"width": "  ", "len": "0x20", "h": "NaN", "pitch": {}}, {"rtype": [], "frame": {}, "legs": True}, None, [], {"width": "<script>x</script>", "frame": "none"}]
def compare(a, b, path=""):
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), (path, sorted(a), sorted(b))
        for k in a: compare(a[k], b[k], path + "." + k)
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)): compare(x, y, path + "[%d]" % i)
    elif isinstance(a, (int, float)) and not isinstance(a, bool):
        assert isinstance(b, (int, float)) and (a == b or math.isclose(a, b, abs_tol=1e-9, rel_tol=1e-12)), (path, a, b)
    else:
        assert a == b, (path, a, b)
n = 0
for s in samples:
    a = john.resolve(s, catalog, geometry); b = moje.resolve(s, catalog, geometry)
    compare(a, b, "resolve"); n += 1
    c = moje.sestav_dopravnik(**(s if isinstance(s, dict) else {}))
    assert c["parametry"] == a["parametry"] and c["valid_geometry"] == a["valid"] and c["polohy_dilu"] == a["dily"], "sestav_dopravnik"
    assert [(d["sku"], d["mnozstvi"], d["jednotka"]) for d in c["dily"]] == [(d["sku"], d["mnozstvi"], d["jednotka"]) for d in a["bom"]], "BOM sestav"
# chybejici cena: oba hlasi DopravnikChyba
bad = dict(catalog); bad.pop("2.3.002.1050")
for mod in (john, moje):
    try:
        mod.resolve({}, bad, geometry); print("CHYBA: bez ceny nevyhodil", mod.__name__)
    except Exception as e:
        print(mod.__name__, "bez ceny ->", type(e).__name__, e)
print("PARITA OK: %d vyberu shodnych s Johnovym resolve (resolve + sestav_dopravnik)" % n)
