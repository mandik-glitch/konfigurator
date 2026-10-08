#!/opt/konfigurator/api/venv/bin/python
"""dopravnik_shop (bot5, 2026-10-07): schema, resolve, cena z dilu, pro_objednavku, glb_bytes, token modelu a routy pres rozcestnik. Konfigurator (bot8) a GLB (bot10) jsou v testu ZASTUPNE
(zastupny_konfigurator.py = kontrakt; fake GLB), mapovani produktu se podstrci do cache stul_shop; DB se jen CTE (ceny dilu, 78 zivych karet dopravniku, zadny zapis).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-07_dopravnik_shop_testy/test_dopravnik_shop.py"""
import importlib.util
import json
import os
import re
import sys
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi - spust pres systemd-run --property=EnvironmentFile=api/.env")
    sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
try:
    import app as appmod  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import konfigurator_registr as R  # noqa: E402
finally:
    threading.Thread.start = _orig
import zastupny_konfigurator as ZK  # noqa: E402

_spec = importlib.util.spec_from_file_location("dcz", os.path.join(REPO, "scripts", "dopravniky_cena_z_komponent.py"))
DCZ = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DCZ)
sys.modules["dopravnik_konfigurator"] = ZK
fake_glb = types.ModuleType("dopravnik_glb")
VOLANI_GLB = []
fake_glb.model_pro_parametry = lambda p, razitka=False: (VOLANI_GLB.append((dict(p), razitka)), ("g" + str(sorted(p.items()))[:20], b"glTF-ZASTUPNY" + (b"-R" if razitka else b"")))[1]
sys.modules["dopravnik_glb"] = fake_glb
import dopravnik_shop as DS  # noqa: E402
assert os.path.abspath(DS.__file__).startswith(API), DS.__file__

vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)))


PID = 9877
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PID): R.RECEPT_DOPRAVNIK, "9876": SH.RECEPT})            # i jeden stul, at je stolova vetev zapnuta (T4)
R._HLEDANI.update(t=0.0, existuje=True)
c = appmod.app.test_client()

print("== schema")
sc = c.get(f"/api/shop/products/{PID}/configurator").get_json()
ids = [s["id"] for s in sc["slots"]]
over("S1 schema: skupiny, sloty (rtype, pitch, width, len, h, legs, frame), verze pravidel, vychozi vyber", [g["id"] for g in sc["groups"]] == ["g_valecky", "g_rozmery", "g_podvozek"] and ids == ["rtype", "pitch", "width", "len", "h", "legs", "frame"]
     and sc["rules_version"] == DS.RULES_VERSION and sc["default_selection"] == {"rtype": "alu", "width": 590, "len": 2000, "pitch": 150, "h": 800, "legs": "auto", "frame": "full", "guide": "none", "guidetype": "40"}, (ids, sc.get("default_selection")))
sl = {s["id"]: s for s in sc["slots"]}
over("S2 meze posuvniku: len 1000-6000/100, pitch 75-300/25, h 570-870/10, vsechno v mm", sl["len"]["slider"] == {"min": 1000, "max": 6000, "step": 100, "unit": "mm"} and sl["pitch"]["slider"] == {"min": 75, "max": 300, "step": 25, "unit": "mm"}
     and sl["h"]["slider"] == {"min": 570, "max": 870, "step": 10, "unit": "mm"}, {k: v["slider"] for k, v in sl.items() if "slider" in v})
over("S3 volby: typ valecku 3, sirky 290/440/590/790/990, nohy auto/4/6/8, ram full/cross/none", [o["id"] for o in sl["rtype"]["options"]] == ["alu", "knurl", "steel"] and [o["id"] for o in sl["width"]["options"]] == ["290", "440", "590", "790", "990"]
     and [o["id"] for o in sl["legs"]["options"]] == ["auto", "4", "6", "8"] and [o["id"] for o in sl["frame"]["options"]] == ["full", "cross", "none"])
over("S4 schema bez interniho obsahu (SKU, dodavatel) a v cs/en/sk jinak", not re.search(r"dogus|\d\.\d{3}\.\d", json.dumps(sc), re.I) and c.get(f"/api/shop/products/{PID}/configurator?lang=en").get_json()["slots"][0]["label"] == "Roller type"
     and c.get(f"/api/shop/products/{PID}/configurator?lang=sk").get_json()["slots"][0]["label"] == "Typ valčeka")

print("== resolve")
r = c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": sc["default_selection"], "rules_version": sc["rules_version"]})
j = r.get_json()
over("R1 resolve vychozi: 200, platne, kod DOP-xxxxxx, hash 16 znaku, cena bez DPH cele Kc a s DPH, rozmery modelu", r.status_code == 200 and j["valid"] is True and re.fullmatch(r"DOP-[0-9A-F]{6}", j["kod"]) and re.fullmatch(r"[0-9a-f]{16}", j["hash"])
     and isinstance(j["price"]["net"], int) and j["price"]["net"] > 0 and j["price"]["currency"] == "CZK" and j["price"]["gross"] == round(j["price"]["net"] * 1.21) and j["dims"] == {"length_mm": 2000, "width_mm": 636, "height_mm": 800}, j.get("price"))
over("R2 model: odkaz s prefixem dop., stav hotovo; token otevre GLB (200 model/gltf-binary)", j["model"]["stav"] == "hotovo" and j["model"]["url"].startswith("/api/shop/configurator/glb/dop."), j["model"])
g = c.get(j["model"]["url"])
over("R3 GLB pres routu stul_shop -> dopravnik_shop (200, model/gltf-binary, zastupne bajty, parametry efektivni a cislem)", g.status_code == 200 and g.mimetype == "model/gltf-binary" and g.data.startswith(b"glTF") and VOLANI_GLB and VOLANI_GLB[-1][0]["legs"] == 4 and VOLANI_GLB[-1][1] is True, (g.status_code, VOLANI_GLB[-1:]))
over("R4 model/<hash> vrati novy odkaz; neznamy hash 404", c.get("/api/shop/configurator/model/" + j["hash"]).get_json()["model"]["url"].startswith("/api/shop/configurator/glb/dop.") and c.get("/api/shop/configurator/model/0123456789abcdef").status_code == 404)
over("R5 hash/kod: stejny pro 'auto' a stejny explicitni pocet noh, jiny pri zmene rozteci", c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {**sc["default_selection"], "legs": 4}}).get_json()["hash"] == j["hash"]
     and c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {**sc["default_selection"], "pitch": 100}}).get_json()["hash"] != j["hash"])
over("R6 'auto' u poctu noh zustane ve vyberu, i kdyz se pocet urcil (po zmene delky se urci znovu)", j["selection"]["legs"] == "auto" and c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {**sc["default_selection"], "len": 5000}}).get_json()["selection"]["legs"] == "auto")
n = c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {**sc["default_selection"], "len": 5000, "legs": 4}}).get_json()
over("R7 4 nohy pri 5 m: zvyseno na 6 s upozornenim a zakazanou volbou (cs)", n["selection"]["legs"] == 6 and any("6" in x["message"] for x in n["notices"]) and n["options"]["legs"]["4"]["disabled"] is True and n["options"]["legs"]["6"]["disabled"] is False
     and n["options"]["legs"]["4"]["reason"], (n["selection"], n["notices"]))
a = c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {**sc["default_selection"], "width": 990}}).get_json()
over("R8 sirka 990 u hlinikoveho valecku: upravena na 790 s upozornenim; volba 990 je zakazana", a["selection"]["width"] == 790 and a["notices"] and a["options"]["width"]["990"]["disabled"] is True and a["options"]["width"]["790"]["disabled"] is False, (a["selection"], a["options"]["width"]))
o2 = c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {**sc["default_selection"], "rtype": "steel", "width": 990}}).get_json()
over("R9 ocel: 990 je platna sirka bez upozorneni", o2["selection"]["width"] == 990 and not o2["notices"] and o2["options"]["width"]["990"]["disabled"] is False)
over("R10 price_delta voleb: aktualni 0, jina varianta se lisi o rozdil cen; typ valecku steel je drazsi", j["options"]["rtype"]["alu"]["price_delta"] == 0 and j["options"]["rtype"]["steel"]["price_delta"] > 0 and j["options"]["frame"]["none"]["price_delta"] < 0 and j["options"]["legs"]["8"]["price_delta"] > 0, j["options"]["rtype"])
sk = c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {}, "price": "hidden"}).get_json()
over("R11 skryta cena: zadne price ani price_delta", "price" not in sk and all("price_delta" not in st for o in sk["options"].values() for st in o.values() if isinstance(st, dict)))
smet = c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {"rtype": 5, "width": "abc", "len": None, "pitch": True, "h": [1], "legs": "x", "frame": "zzz", "guide": "both", "guidetype": "60", "nesmysl": 1}}).get_json()
over("R12 smetovy vyber -> vychozi hodnoty, voditka v 1. verzi vzdy vypnuta, platne", smet["valid"] and smet["selection"] == {**sc["default_selection"]} and smet["hash"] == j["hash"], smet.get("selection"))
over("R13 cizi rules_version = 409 rules_changed", c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {}, "rules_version": "stara"}).status_code == 409)
sd = c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {"len": 3333, "pitch": 111, "h": 1500}}).get_json()
over("R14 hodnoty mimo meze/krok se orizou (len 3300, pitch 100, h 870) s upozornenim", sd["selection"]["len"] == 3300 and sd["selection"]["pitch"] == 100 and sd["selection"]["h"] == 870 and len(sd["notices"]) == 3, (sd["selection"], sd["notices"]))

print("== cena = karty hotovych dopravniku")
cur = appmod.get_conn().cursor()
cur.execute("SELECT sku, price_czk_placeholder p, dogus_price_rate_used k FROM shop_products WHERE category_id=324 AND active=1 AND price_czk_placeholder IS NOT NULL ORDER BY sku")
karty = cur.fetchall()
recept = json.load(open(os.path.join(REPO, "docs", "dopravniky_recept.json"), encoding="utf-8"))
RTYP = {"16.10.01.050": "alu", "16.12.01.050": "knurl", "16.10.01.051": "steel"}
neshoda = []
for k in karty:
    rada, _s, L, W = DCZ.rozloz_kod(k["sku"], recept)
    ef, gen = DS._efektivni({"rtype": RTYP[rada], "width": W, "len": L, "pitch": 150, "h": 800, "legs": "auto", "frame": "full", "guide": "none", "guidetype": "40"})
    cena, bez = DS.cena_dilu(gen["dily"], kurz=float(k["k"]))
    if not cena or cena["net"] != int(k["p"]):
        neshoda.append((k["sku"], int(k["p"]), cena and cena["net"]))
over("C1 generator pro katalogovy rozmer = cena karty u vsech %d zivych dopravniku (stejny kurz)" % len(karty), len(karty) == 78 and not neshoda, neshoda[:3])
cena_zive, _ = DS.cena_dilu(DS._efektivni(DS._zaklad({}))[1]["dily"])
over("C2 zivy kurz z karet dilu: cena vychoziho dopravniku je kladna a v rozumnem rozsahu", cena_zive and 8000 < cena_zive["net"] < 40000, cena_zive and cena_zive["net"])

print("== pro_objednavku / glb_bytes")
po = DS.pro_objednavku({}, None, "cs", PID)
over("P1 tvar pro kosik: ok, selection, hash, kod, valid, price, bom, souhrn, hmotnost, cenovy souhrn", po["ok"] and po["valid"] and po["price"]["net"] == j["price"]["net"] and po["hash"] == j["hash"] and po["kod"] == j["kod"] and po["rules_version"] == DS.RULES_VERSION
     and po["pocet_spoju"] == 0 and po["cenovy_souhrn"]["material_czk"] == po["price"]["net"] and len(po["souhrn"]) == 7 and all({"id", "label", "value"} <= set(x) for x in po["souhrn"]), sorted(po))
over("P2 hmotnost uplna a kladna (vsechny dily maji hmotnost v katalogu)", po["hmotnost_uplna"] is True and po["hmotnost_kg"] > 5 and po["hmotnost_chybi"] == [], (po["hmotnost_kg"], po["hmotnost_chybi"]))
over("P3 neutralni kusovnik: bez cisel dilu a dodavatele, profily jako kusy o delce", all(set(x) == {"nazev", "mnozstvi", "rozmer"} for x in po["bom"]) and not re.search(r"dogus|\d\.\d{3}\.\d", json.dumps(po["bom"], ensure_ascii=False), re.I)
     and any(x["rozmer"] == "2000 mm" and x["mnozstvi"] == 2 for x in po["bom"]), po["bom"])
over("P4 jina verze pravidel = ok False rules_changed", DS.pro_objednavku({}, "stara", "cs", PID) == {"ok": False, "chyba": "rules_changed", "rules_version": DS.RULES_VERSION})
over("P5 pres rozcestnik: pro_objednavku a glb_bytes (vychozi S razitky podle pravidla 61, bez nich jen vyslovne)", R.pro_objednavku({}, None, "cs", PID)["kod"] == j["kod"] and R.glb_bytes({}, PID) == b"glTF-ZASTUPNY-R" and R.glb_bytes({}, PID, razitka=False) == b"glTF-ZASTUPNY" and DS.glb_bytes({}) == b"glTF-ZASTUPNY-R" and R.konfigurovatelny(PID))
over("P6 anglicka konfigurace: souhrn a upozorneni anglicky", DS.pro_objednavku({"len": 5000, "legs": 4}, None, "en", PID)["notices"][0].startswith("The number of legs") and DS.pro_objednavku({}, None, "en", PID)["souhrn"][0]["label"] == "Roller type")

print("== chybejici cena, token, nepripraveny modul")
puv = DS._ceny_dilu
DS._ceny_dilu = lambda skus: {s: ({"usd": None, "kurz": None, "weight_g": None} if s == "3.004.03.01" else puv([s])[s]) for s in skus}
bc = DS._spocti(DS._zaklad({}), "cs")[0]
DS._ceny_dilu = puv
over("M1 dil bez ceny = cena neni a konfigurace neplatna (zadna cena 0)", bc["price"] is None and bc["valid"] is False and bc["errors"], bc.get("price"))
p0 = DS._efektivni(DS._zaklad({}))[0]
tok = DS.podepis_model(p0)
over("T1 token: podpis a overeni (parametry zpet), prefix dop.", tok.startswith("dop.") and DS.over_model(tok) == (p0, None))
over("T2 poskozeny, cizi a stolovy token = podpis; prosly = vyprsel", DS.over_model(tok[:-3] + "xyz")[1] == "podpis" and DS.over_model("neco.1.2")[1] == "podpis" and DS.over_model(DS.podepis_model(p0, ted=time.time() - 10_000))[1] == "vyprsel")
over("T3 routa: prosly token 410, poskozeny 403", c.get("/api/shop/configurator/glb/" + DS.podepis_model(p0, ted=time.time() - 10_000)).status_code == 410 and c.get("/api/shop/configurator/glb/dop.x.1.y").status_code == 403)
over("T4 stolovy token se dopravnikem nezpracuje (prefix) a stolova routa dal vraci 403 pro cizi token", c.get("/api/shop/configurator/glb/neco.123.sig").status_code == 403)
del sys.modules["dopravnik_konfigurator"]
DS._RESOLVE_CACHE.clear()                                    # jinak by resolve vratil vysledek z cache
sc503 = c.get(f"/api/shop/products/{PID}/configurator")
rs503 = c.post("/api/shop/configurator/resolve", json={"product_id": PID, "selection": {}})
over("N1 bez konfiguratoru (bot8) je dopravnik 503 not_ready, ne 500", sc503.status_code == 503 and sc503.get_json() == {"error": "not_ready"} and rs503.status_code == 503, (sc503.status_code, rs503.status_code))
sys.modules["dopravnik_konfigurator"] = ZK
over("N2 po doruceni modulu zase 200", c.get(f"/api/shop/products/{PID}/configurator").status_code == 200)
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
