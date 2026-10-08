#!/opt/konfigurator/api/venv/bin/python
"""SHOP vrstva generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08, faze 2): api/oploceni_shop.py + rozcestnik api/konfigurator_registr.py + delegace v routach api/stul_shop.py + kosik
(api/konfigurace_kosik.py) a nabidka z konfigurace (api/nabidka_z_konfigurace.py) pro recept `oploceni_kryt`.

SKUTECNE routy pres Flask test_client, skutecny kod, DB se jen CTE (ceny dilu z katalogu, prihlaseny zamestnanec pro session); mapovani produktu (app_settings.configurator_products) se podstrci
jen do cache v pameti, nic se nezapisuje (kosik / objednavka / nabidka se vola jen cestami, ktere nezapisuji). Cena v testu se overuje NEZAVISLE: rozdily cen voleb proti znovu vyresenemu vyberu,
soucet kusovniku proti celkove cene, stavby jadra proti shop vrstve.
Casti: A schema (cs / en / sk) | B resolve vychozi konfigurace a kontrakt | C upravy vyberu na proveditelny (dvere, vyska, patky, rozsahy, oplocení) | D stavy voleb (options) | E blok pro zamestnance |
F pro_objednavku | G token a GLB (verejny i nabidkovy) | H rozcestnik a routy (stul beze zmeny) | I kosik a nabidka (jen cteni) | J meze, velikost a cas | K fuzz | L preklady a dalsi
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=<koren repa> /opt/konfigurator/api/venv/bin/python3 \\
  <koren repa>/scripts/2026-10-08_oploceni/test_oploceni_shop.py        (koren repa = /opt/konfigurator po nasazeni, nebo <kandidat>/repo; test bere moduly z api/ sveho korene)"""
import gzip
import json
import os
import random
import re
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.environ.get("OPLOCENI_API") or os.path.join(REPO, "api")
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi - spust pres systemd-run --property=EnvironmentFile=api/.env")
    sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.dont_write_bytecode = True
try:
    import app as appmod  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import stul_api as SA  # noqa: E402
    import konfigurator_registr as R  # noqa: E402
    import konfigurace_kosik as KK  # noqa: E402
    import nabidka_z_konfigurace as NZ  # noqa: E402
    import oploceni_shop as OS  # noqa: E402
    import oploceni_konfigurator as O  # noqa: E402
    import oploceni_cena as OC  # noqa: E402
    import oploceni_glb as OG  # noqa: E402
finally:
    threading.Thread.start = _orig
assert os.path.abspath(OS.__file__).startswith(os.path.abspath(API)), OS.__file__
SH.LIMIT_SCHEMA = (10 ** 6, 60)
SH.LIMIT_RESOLVE = (10 ** 6, 60)
SH.LIMIT_GLB = (10 ** 6, 60)
SH.HODINOVY_STROP.update({k: 10 ** 6 for k in SH.HODINOVY_STROP})

vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)[:400]))
    if not p and os.environ.get("OPLOCENI_STOP_PRVNI"):                 # mutacni beh: staci prvni selhani (mutace je chycena)
        sys.exit(1)


PID, PID_STUL, PID_X = 9990, 9991, 9992
SH._PRODUKTY.update(t=time.time() + 100_000, map={str(PID): R.RECEPT_OPLOCENI, str(PID_STUL): SH.RECEPT})
c = appmod.app.test_client()                                    # verejny navstevnik
cs = appmod.app.test_client()                                   # zamestnanec (session)
cur0 = appmod.get_conn().cursor()
cur0.execute("SELECT id FROM app_users WHERE role='admin' AND COALESCE(active, 1)=1 ORDER BY id LIMIT 1")
ADMIN = cur0.fetchone()["id"]
appmod.get_conn().rollback()
with cs.session_transaction() as _s:
    _s["user_id"] = ADMIN
VYCHOZI = OS.vychozi_vyber()
RV = OS.RULES_VERSION
HEX16 = re.compile(r"^[0-9a-f]{16}$")
SLOTY = ["w", "d", "h", "front", "right", "back", "left", "roof", "fill", "fill_front", "fill_right", "fill_back", "fill_left", "fill_roof", "door_w", "door_h", "door_pos", "door_hinge", "lock", "feet"]


def res(sel=None, lang="cs", **kw):
    return OS.resolve(dict(VYCHOZI, **(sel or {})), lang, **kw)


def net(sel=None):
    return res(sel)["price"]["net"]


def post(client, sel, **extra):
    return client.post("/api/shop/configurator/resolve", json=dict({"product_id": PID, "selection": sel, "rules_version": RV, "lang": "cs"}, **extra))


# ---------------------------------------------------------------------------------------------------------------------
print("== A schema (cs / en / sk)")
for lang in ("cs", "en", "sk"):
    sc = OS.schema(lang)
    over(f"A1 {lang}: sloty a poradi", [s["id"] for s in sc["slots"]] == SLOTY, [s["id"] for s in sc["slots"]])
    over(f"A2 {lang}: kazdy slot ma popisek, skupinu ze seznamu a znamy typ", all(s["label"] and s["group"] in {g["id"] for g in sc["groups"]} and s["type"] in ("slider", "chips", "select", "toggle") for s in sc["slots"]))
sc = OS.schema("cs")
over("A3 default_selection = sloty, hodnoty podle kontraktu", list(sc["default_selection"]) == SLOTY and sc["default_selection"]["door_h"] is None and sc["default_selection"]["feet"] is False
     and sc["default_selection"]["front"] == "door" and sc["default_selection"]["roof"] == "fill" and sc["default_selection"]["fill"] == "pc_clear", sc["default_selection"])
over("A4 rules_version, recept, profil", sc["rules_version"] == RV and sc["recipe"] == "oploceni_kryt" and sc["profile"] == "40x40")
over("A5 posuvniky: verejne meze a krok 10 mm", {s["id"]: (s["slider"]["min"], s["slider"]["max"], s["slider"]["step"], s["slider"]["unit"]) for s in sc["slots"] if s["type"] == "slider"}
     == {"w": (600, 4000, 10, "mm"), "d": (600, 4000, 10, "mm"), "h": (1000, 3000, 10, "mm"), "door_w": (600, 1200, 10, "mm"), "door_h": (1500, 2400, 10, "mm")})
volby = {s["id"]: [o["id"] for o in s["options"]] for s in sc["slots"] if s["type"] in ("chips", "select")}
over("A6 volby: strany, strecha, vyplne, dvere", volby["front"] == ["wall", "door", "open"] and volby["left"] == ["wall", "door", "open"] and volby["roof"] == ["none", "frame", "fill"]
     and volby["fill"] == ["pc_clear", "pc_smoke", "acrylic", "mesh", "solid"] and volby["fill_roof"] == ["auto", "pc_clear", "pc_smoke", "acrylic", "mesh", "solid"]
     and volby["door_pos"] == ["left", "center", "right"] and volby["door_hinge"] == ["left", "right"] and volby["lock"] == ["latch", "lock", "none"], volby)
over("A7 typy slotu: strany a strecha chips, vyplne select, patky toggle", {s["id"]: s["type"] for s in sc["slots"] if s["id"] in ("front", "roof", "fill", "fill_front", "feet", "door_pos", "lock")}
     == {"front": "chips", "roof": "chips", "fill": "select", "fill_front": "select", "feet": "toggle", "door_pos": "chips", "lock": "chips"})
over("A8 skupiny: velikost, strany, vyplne, vyplne po stranach, dvere, prislusenstvi", [g["id"] for g in sc["groups"]] == ["g_size", "g_sides", "g_fill", "g_fill_adv", "g_door", "g_extras"])
text = json.dumps(sc, ensure_ascii=False)
over("A9 schema neobsahuje interni nazvy (cisla dilu, SKU, navrh karty)", not re.search(r"product_\d|Object_\d|OPL-|navrh|OPLOCENI|3176|3644", text), re.findall(r"product_\d|Object_\d|OPL-|navrh|3176|3644", text))
cs_lab, en_lab, sk_lab = ({s["id"]: s["label"] for s in OS.schema(l)["slots"]} for l in ("cs", "en", "sk"))
over("A10 preklady se lisi od cestiny (en i sk), zadny prazdny", all(en_lab[k] and sk_lab[k] for k in SLOTY) and sum(en_lab[k] != cs_lab[k] for k in SLOTY) >= 15 and sum(sk_lab[k] != cs_lab[k] for k in SLOTY) >= 12,
     (sum(en_lab[k] != cs_lab[k] for k in SLOTY), sum(sk_lab[k] != cs_lab[k] for k in SLOTY)))
r = c.get(f"/api/shop/products/{PID}/configurator?lang=en")
j = r.get_json()
over("A11 routa schema: 200, anglicky popisek, systems [], env null, default_saved false", r.status_code == 200 and j["slots"][0]["label"] == "Width" and j["systems"] == [] and j["env"] is None and j["default_saved"] is False, (r.status_code, j.get("slots", [{}])[0]))
r = c.get(f"/api/shop/products/{PID}/configurator", headers={"Accept-Language": "sk-SK"})
over("A12 routa schema: bez ?lang= se jazyk bere z Accept-Language (sk)", r.get_json()["slots"][0]["label"] == "Šírka")
over("A13 routa schema: jiny produkt = 404, neznamy jazyk = cesky", c.get(f"/api/shop/products/{PID_X}/configurator").status_code == 404 and c.get(f"/api/shop/products/{PID}/configurator?lang=xx").get_json()["slots"][0]["label"] == "Šířka")

# ---------------------------------------------------------------------------------------------------------------------
print("== B resolve vychozi konfigurace")
r = post(c, VYCHOZI)
j = r.get_json()
over("B1 routa resolve: 200, valid, effektivni vyber = vychozi", r.status_code == 200 and j["valid"] is True and j["selection"] == VYCHOZI and j["errors"] == [], (r.status_code, j.get("errors")))
core = O.normalizuj(**OS._na_jadro(OS._zaklad(VYCHOZI)))
rj = O.sestav_oploceni(**core)
ctx = OS._kontext()
ocek = OC.cena(rj, ctx, montaz_pct=0)["price_summary"]["total_czk"]
over("B2 cena = cena jadra z price_entries (bez montaze), cele Kc", j["price"]["net"] == ocek and isinstance(j["price"]["net"], int) and j["price"]["currency"] == "CZK" and j["price"]["vat_rate"] == SA.SAZBA_DPH, (j["price"], ocek))
over("B3 gross = net x (1 + DPH) zaokrouhlene", j["price"]["gross"] == round(j["price"]["net"] * (1 + SA.SAZBA_DPH / 100.0)))
over("B4 hash a kod: 16 hex, OPL- + 6 hex velkymi", HEX16.match(j["hash"]) and j["kod"] == "OPL-" + j["hash"][:6].upper() and j["rules_version"] == RV, (j["hash"], j["kod"]))
over("B5 hash nezavisi na jazyce, stejny vyber = stejny hash, jiny vyber = jiny hash", res(lang="en")["hash"] == j["hash"] == res(lang="sk")["hash"] and res({"w": 1600})["hash"] != j["hash"])
over("B6 hash = sha256(parametry jadra + verze pravidel), nikoli hash jadra", j["hash"] == OS._hash(core) and j["hash"] != rj["hash"])
over("B7 rozmery obrysu", j["dims"] == {"width_mm": 1500, "depth_mm": 1500, "height_mm": 2200}, j["dims"])
over("B8 notices: info o norme (zakaznik ji vidi), zadna uprava", [n["action"] for n in j["notices"]] == ["info"] and "14120" in j["notices"][0]["message"] and j["offers"] == [], j["notices"])
over("B9 model: hotovo, odkaz s prefixem opl.", j["model"]["stav"] == "hotovo" and j["model"]["url"].startswith("/api/shop/configurator/glb/opl.") and j["model"]["odhad_ms"] == 0)
over("B10 verejna odpoved nema `staff` ani soukrome klice", "staff" not in j and not any(k.startswith("_") for k in j), sorted(j))
r2 = post(c, VYCHOZI, rules_version="stara-verze")
over("B11 jina verze pravidel = 409 rules_changed", r2.status_code == 409 and r2.get_json() == {"error": "rules_changed"})
rh = post(c, VYCHOZI, price="hidden")
jh = rh.get_json()
over("B12 skryta cena: bez price a bez price_delta ve vsech volbach", "price" not in jh and not any("price_delta" in st for o in jh["options"].values() if isinstance(o, dict) for st in o.values() if isinstance(st, dict)))
over("B13 resolve vraci novou kopii (zmena odpovedi nepoznamena cache)", (lambda a: (a["selection"].update(w=1), a["options"].clear(), True)[2] and res()["selection"]["w"] == 1500 and bool(res()["options"]))(res()))
rm = c.get("/api/shop/configurator/model/" + j["hash"])
over("B14 routa model znameho hashe: 200, hotovo, odkaz; neznamy hash = 404", rm.status_code == 200 and rm.get_json()["model"]["stav"] == "hotovo" and rm.get_json()["model"]["url"].startswith("/api/shop/configurator/glb/opl.")
     and c.get("/api/shop/configurator/model/0123456789abcdef").status_code == 404, rm.status_code)
over("B15 zasady: telo bez product_id / neznamy produkt = 404, telo bez vyberu = vychozi vyber", c.post("/api/shop/configurator/resolve", json={"selection": {}}).status_code == 404
     and c.post("/api/shop/configurator/resolve", json={"product_id": PID_X, "selection": {}}).status_code == 404 and c.post("/api/shop/configurator/resolve", json={"product_id": PID}).get_json()["selection"] == VYCHOZI)

# ---------------------------------------------------------------------------------------------------------------------
print("== C upravy vyberu na proveditelny")


def nt(r, slot=None):
    return [n for n in r["notices"] if n["action"] == "adjusted" and (slot is None or n["slot"] == slot)]


r = res({"w": 800})
over("C1 kratka strana: dvere se nevejdou -> zustane stena + oznameni s nejmensi delkou 876 mm", r["selection"]["front"] == "wall" and len(nt(r, "front")) == 1 and "876" in nt(r, "front")[0]["message"] and r["valid"], nt(r))
over("C2 stejne: v options je dvere zakazano s duvodem, ostatni volby ne", r["options"]["front"]["door"]["disabled"] is True and "876" in r["options"]["front"]["door"]["reason"] and r["options"]["front"]["wall"]["disabled"] is False
     and r["options"]["right"]["door"]["disabled"] is False)
r = res({"h": 1700})
over("C3 nizka konstrukce: dvere se nevejdou (potrebuji 1738 mm) -> stena + oznameni", r["selection"]["front"] == "wall" and "1738" in nt(r, "front")[0]["message"] and "1738" in r["options"]["front"]["door"]["reason"])
r = res({"w": 1100, "door_w": 900})
over("C4 sirka dveri se zkrati tak, aby vedle zustalo pole 150 mm (S0 - 196 = 824)", r["selection"]["door_w"] == 824 and "824" in nt(r, "door_w")[0]["message"] and r["options"]["door_w"]["max"] == 824, nt(r))
r = res({"door_pos": "center", "door_w": 1100})
over("C5 dvere uprostred: nejvic S0 - 386 = 1034", r["selection"]["door_w"] == 1034 and r["options"]["door_w"]["max"] == 1034)
over("C6 hranice sirky dveri: presne max projde bez upravy, o 1 mm vic se zkrati", not nt(res({"door_pos": "center", "door_w": 1034})) and res({"door_pos": "center", "door_w": 1035})["selection"]["door_w"] == 1034)
r = res({"door_h": 2300})
over("C7 vyska dveri nad nejvetsi mozne (1962) se zkrati a oznami", r["selection"]["door_h"] == 1962 and "1962" in nt(r, "door_h")[0]["message"] and r["options"]["door_h"]["max"] == 1962 and r["options"]["door_h"]["auto"] is False)
over("C8 vyska dveri automaticky (null) zustane null, options.value = skutecna vyska kridla 1962", res()["selection"]["door_h"] is None and res()["options"]["door_h"]["value"] == 1962 and res()["options"]["door_h"]["auto"] is True)
r = res({"feet": True, "h": 1000})
over("C9 patky: vyska se zvedne na 1079 (konstrukce aspon 1000 mm) a oznami; min posuvniku vysky 1079", r["selection"]["h"] == 1079 and "1079" in nt(r, "h")[0]["message"] and r["options"]["h"]["min"] == 1079
     and res({"feet": True, "h": 1079})["selection"]["h"] == 1079 and not nt(res({"feet": True, "h": 1079}), "h"))
r = res({"front": "open", "right": "open", "back": "open", "left": "open", "roof": "none"})
over("C10 vsechny strany otevrene a bez strechy -> strecha 'jen ram' + oznameni; moznost 'bez strechy' je zakazana", r["selection"]["roof"] == "frame" and len(nt(r, "roof")) == 1 and r["valid"]
     and res({"front": "open", "right": "open", "back": "open", "left": "open", "roof": "frame"})["options"]["roof"]["none"]["disabled"] is True and res()["options"]["roof"]["none"]["disabled"] is False)
r = res({"w": 99999, "d": -5, "h": "abc"})
over("C11 mimo rozsah: sirka 4000, hloubka 600 (oznameni), nesmyslna vyska = vychozi 2200", r["selection"]["w"] == 4000 and r["selection"]["d"] == 600 and r["selection"]["h"] == 2200 and len(nt(r)) == 2 and r["valid"], nt(r))
over("C12 nesmysly (None, seznam, neznamy klic, spatne typy): vychozi vyber, zadna vyjimka", all(OS.resolve(x, "cs")["selection"] == VYCHOZI for x in (None, [], "x", 5, {}, {"zzz": 1}, {"front": "kulate", "roof": 5, "fill": None, "feet": "ano", "door_pos": [], "w": None, "lock": {}})))
fe = {"front": "wall", "right": "open", "back": "open", "left": "open", "roof": "none", "w": 4000, "h": 1800, "fill": "mesh"}
a, b = res(dict(fe, d=800)), res(dict(fe, d=3000))
over("C13 oploceni (jedna strana bez strechy): hloubka nema vliv - stejny hash, cena, canonicka hodnota, options.d.hidden", a["hash"] == b["hash"] and a["price"] == b["price"] and a["selection"]["d"] == 1500 and a["options"]["d"].get("hidden") is True
     and "hidden" not in a["options"]["w"] and a["dims"]["depth_mm"] is None, (a["selection"]["d"], a["options"]["d"]))
over("C14 jedna strana vpravo: sirka nema vliv (options.w.hidden), hloubka ano", res({"front": "open", "right": "wall", "back": "open", "left": "open", "roof": "none"})["options"]["w"].get("hidden") is True
     and "hidden" not in res({"front": "open", "right": "wall", "back": "open", "left": "open", "roof": "none"})["options"]["d"])
r = res({"right": "open", "fill_right": "mesh", "fill_roof": "plexi", "roof": "frame"})
over("C15 prepis vyplne u otevrene strany a u strechy bez vyplne se zahodi (auto) a skryje", r["selection"]["fill_right"] == "auto" and r["selection"]["fill_roof"] == "auto" and r["options"]["fill_right"].get("hidden") is True
     and r["options"]["fill_roof"].get("hidden") is True and "hidden" not in res()["options"]["fill_front"] and "hidden" not in res()["options"]["fill_roof"])
r = res({"front": "wall", "door_w": 1000, "door_h": 1700, "door_pos": "center", "door_hinge": "left", "lock": "lock"})
over("C16 bez dveri se parametry dveri vraci na vychozi a volby dveri jsou skryte", r["selection"]["door_w"] == 800 and r["selection"]["door_h"] is None and r["selection"]["door_pos"] == "right" and r["selection"]["lock"] == "latch"
     and all(r["options"][k].get("hidden") is True for k in ("door_w", "door_h", "door_pos", "door_hinge", "lock")) and r["hash"] == res({"front": "wall"})["hash"])
r = res({"w": 700, "front": "door", "back": "door", "door_pos": "center"})
over("C17 dvere uprostred, ktere se nevejdou na kratsi stranu, se vrati na polohu vpravo (oznameni) nebo na stenu", r["selection"]["door_pos"] in ("right",) and len(nt(r)) >= 1, (r["selection"]["door_pos"], nt(r)))
r = res({"front": "door", "right": "door", "w": 1500, "d": 1000})
over("C18 dvere na dvou stranach ruzne dlouhych: sirka podle KRATSI strany (S0 - 196 = 724)", r["selection"]["door_w"] == 724 and r["selection"]["front"] == "door" and r["selection"]["right"] == "door" and r["options"]["door_w"]["max"] == 724, (r["selection"]["door_w"], r["options"]["door_w"]))
over("C19 uprava je pevny bod: vyres(efektivni vyber) = stejny efektivni vyber a hash (pro 14 tezkych vstupu)", all(
    res(s)["selection"] == res(res(s)["selection"])["selection"] and res(s)["hash"] == res(res(s)["selection"])["hash"] for s in (
        {"w": 800}, {"h": 1700}, {"w": 1100, "door_w": 900}, {"door_pos": "center", "door_w": 1100}, {"door_h": 2300}, {"feet": True, "h": 1000}, {"front": "open", "right": "open", "back": "open", "left": "open", "roof": "none"},
        {"w": 99999, "d": -5}, fe, dict(fe, d=800), {"w": 700, "front": "door", "back": "door", "door_pos": "center"}, {"front": "door", "right": "door", "d": 1000}, {"fill_left": "mesh", "left": "open"}, {"feet": True, "h": 1500, "front": "door"})))

# ---------------------------------------------------------------------------------------------------------------------
print("== D stavy voleb (options) proti nezavisle znovu vyresenemu vyberu")
base = res()
op = base["options"]
over("D1 vyplne: rozdil ceny kazde volby = rozdil znovu vyresene konfigurace (vsechna pole, vcetne tesneni)", all(op["fill"][t]["price_delta"] == net({"fill": t}) - base["price"]["net"] for t in OS.VYPLN), {t: (op["fill"][t]["price_delta"], net({"fill": t}) - base["price"]["net"]) for t in OS.VYPLN})
over("D2 aktualni vyplne ma rozdil 0, plexi je nejdrazsi, sit nejlevnejsi", op["fill"]["pc_clear"]["price_delta"] == 0 and op["fill"]["acrylic"]["price_delta"] == max(v["price_delta"] for v in op["fill"].values())
     and op["fill"]["mesh"]["price_delta"] == min(v["price_delta"] for v in op["fill"].values()))
b2 = res({"fill_left": "mesh", "left": "wall", "roof": "frame"})
over("D3 rozdil ceny vyplne s prepisy stran: prepsana strana se nemeni (delta = rozdil znovu vyreseneho vyberu)", all(b2["options"]["fill"][t]["price_delta"] == net({"fill": t, "fill_left": "mesh", "roof": "frame"}) - b2["price"]["net"] for t in OS.VYPLN))
over("D4 patky: rozdil ceny zapnuti = rozdil znovu vyresene konfigurace", op["feet"]["on"]["price_delta"] == net({"feet": True}) - base["price"]["net"] and op["feet"]["on"]["disabled"] is False, (op["feet"], net({"feet": True}) - base["price"]["net"]))
over("D5 zapnute patky: price_delta u `on` je null (uz jsou zapnute)", res({"feet": True})["options"]["feet"]["on"]["price_delta"] is None)
over("D6 meze posuvniku (verejne) a krok", op["w"] == {"min": 600, "max": 4000} and op["d"] == {"min": 600, "max": 4000} and op["h"] == {"min": 1000, "max": 3000})
over("D7 sirka dveri: min 600, max podle strany a polohy; dvere o max sirce projdou beze zmeny", op["door_w"] == {"min": 600, "max": 1200} and not nt(res({"door_w": 1200})) and len(nt(res({"door_w": 1210}), "door_w")) == 1 and res({"door_w": 1210})["selection"]["door_w"] == 1200)
over("D8 vyska dveri: options {min 1500, max 1962, value 1962, auto true}", op["door_h"] == {"min": 1500, "max": 1962, "value": 1962, "auto": True}, op["door_h"])
over("D9 strany: u stavu stena / otevreno zadna zakaz, dvere povolene na dost dlouhe strane", all(op[s][o]["disabled"] is False for s in OS.STRANY for o in ("wall", "open")) and all(op[s]["door"]["disabled"] is False for s in OS.STRANY))
over("D10 vyplne po stranach: u steny dostupne (bez hidden), prepis nema rozdil ceny", all("hidden" not in op[k] for k in ("fill_front", "fill_right", "fill_back", "fill_left", "fill_roof")))
over("D11 volby dveri viditelne (bez hidden), pri zadnych dverich skryte", all("hidden" not in op[k] for k in ("door_w", "door_h", "door_pos", "door_hinge", "lock")))
over("D12 jedina otevrena strana: vsechny ostatni mozne, 'otevreno' u vsech 4 stran se zablokuje jen strechou (roof.none)", res({"front": "open", "right": "open", "back": "open", "left": "wall", "roof": "none"})["selection"]["roof"] == "none")

# ---------------------------------------------------------------------------------------------------------------------
print("== E blok pro zamestnance")
rs = post(cs, VYCHOZI, staff=True)
js = rs.get_json()
st = js.get("staff") or {}
k = st.get("kusovnik") or {}
over("E1 zamestnanec s staff: true dostane blok staff (kusovnik, cena, kod, hash, pocet spoju)", rs.status_code == 200 and st and st["kod"] == js["kod"] and st["hash"] == js["hash"] and st["pocet_spoju"] == rj["pocet_spoju"], sorted(st))
over("E2 cena v bloku = verejna cena; s DPH", st["cena"]["bez_dph"] == js["price"]["net"] and st["cena"]["s_dph"] == js["price"]["gross"] and st["cena"]["mena"] == "CZK")
soucet = sum(x["celkem"] for x in k["radky"]) + sum(x["celkem"] for x in k["prace"])
over("E3 kusovnik: soucet radku (dily + prace + zaokrouhleni) = celkem bez DPH = cena", soucet == k["celkem"]["bez_dph"] == js["price"]["net"], (soucet, k["celkem"]))
over("E4 kusovnik obsahuje profily s delkou, vyplne s rozmerem, spojky, tesneni (extra prace) a balne", any(re.match(r"^Profil ", x["nazev"]) and (x["rozmer"] or "").endswith("mm") for x in k["radky"])
     and any("výplň" in x["nazev"].lower() or "polykarbon" in x["nazev"].lower() for x in k["radky"]) and any("spojka" in x["nazev"].lower() for x in k["radky"]) and any("Těsnění" in x["nazev"] for x in k["prace"])
     and any(x["nazev"].startswith("Balné") for x in k["prace"]), [x["nazev"] for x in k["radky"]][:6])
over("E5 montaz se u oploceni nenabizi (pct 0) a vyroba bez odkazu v1", k["montaz"]["pct"] == 0 and k["montaz"]["czk"] == 0 and st["vyrobni_list_url"] is None and st["problemy"] == [])
over("E6 hmotnost v kusovniku = hmotnost z pro_objednavku", k["hmotnost_kg"] == OS.pro_objednavku(VYCHOZI)["hmotnost_kg"] and k["hmotnost_kg"] > 50, k["hmotnost_kg"])
over("E7 varovani kusovniku nesou upozorneni generatoru (ISO 14120)", any("14120" in w for w in k["varovani"]), k["varovani"])
rp = post(c, VYCHOZI, staff=True)
over("E8 verejny navstevnik s staff: true blok NEDOSTANE", rp.status_code == 200 and "staff" not in rp.get_json())
rp2 = post(cs, VYCHOZI)
over("E9 zamestnanec bez staff: true blok nedostane (jen kdyz o nej pozada)", "staff" not in rp2.get_json())
over("E10 blok staff u jine konfigurace nese jeji cenu (fence)", post(cs, fe, staff=True).get_json()["staff"]["cena"]["bez_dph"] == res(fe)["price"]["net"])

# ---------------------------------------------------------------------------------------------------------------------
print("== F pro_objednavku (kosik, objednavka, nabidka)")
po = OS.pro_objednavku(VYCHOZI, RV, "cs", PID)
over("F1 tvar odpovedi jako stul / dopravnik", po["ok"] is True and all(k_ in po for k_ in ("selection", "hash", "kod", "rules_version", "valid", "errors", "notices", "price", "bom", "pocet_spoju", "souhrn", "hmotnost_kg", "hmotnost_uplna", "hmotnost_chybi",
                                                                                      "cenovy_souhrn", "rozmery_text")), sorted(po))
over("F2 shoduje se s resolve (vyber, hash, kod, cena)", po["selection"] == VYCHOZI and po["hash"] == base["hash"] and po["kod"] == base["kod"] and po["price"] == base["price"] and po["valid"] is True and po["errors"] == [])
over("F3 jina verze pravidel = {ok: false, chyba: rules_changed}", OS.pro_objednavku(VYCHOZI, "stara", "cs", PID) == {"ok": False, "chyba": "rules_changed", "rules_version": RV})
over("F4 rules_version None / spravna projde", OS.pro_objednavku(VYCHOZI, None, "cs", PID)["ok"] and OS.pro_objednavku(VYCHOZI, RV)["ok"])
bom = po["bom"]
over("F5 neutralni kusovnik: profily podle delky (35 ks), spojky 80 ks, vyplne podle rozmeru tabule, tesneni v metrech; zadna cisla dilu", sum(x["mnozstvi"] for x in bom if x["nazev"].startswith("Profil")) == 35
     and any(x["nazev"].startswith("Rohov") and x["mnozstvi"] == 80 for x in bom) and any(x["rozmer"] and "×" in x["rozmer"] for x in bom) and any(x["rozmer"] == "m" for x in bom)
     and not re.search(r"product_|Object_|SKU|\d\.\d\.\d{3}", json.dumps(bom, ensure_ascii=False)), bom[:4])
over("F6 pocet spoju a souhrn voleb (id, label, value)", po["pocet_spoju"] == 54 and [s["id"] for s in po["souhrn"]][:7] == ["dims", "front", "right", "back", "left", "roof", "fill"] and po["souhrn"][0]["value"] == "1500 × 1500 × 2200 mm"
     and {s["id"] for s in po["souhrn"]} >= {"door_w", "door_h", "door_pos", "door_hinge", "lock"}, po["souhrn"][:3])
over("F7 souhrn v anglictine a slovenstine", OS.pro_objednavku(VYCHOZI, None, "en")["souhrn"][1]["label"] == "Front" and OS.pro_objednavku(VYCHOZI, None, "sk")["souhrn"][1]["value"] == "Dvere")
over("F8 rozmery_text: kryt 'sirka x hloubka x vyska', oploceni jen relevantni rozmery", po["rozmery_text"] == "1500 × 1500 × 2200" and OS.pro_objednavku(dict(VYCHOZI, **fe), None)["rozmery_text"] == "4000 × 1800")
over("F9 cenovy souhrn: klice jako u stolu + extra_work a hmotnost; soucet casti odpovida cene", all(k_ in po["cenovy_souhrn"] for k_ in ("material_czk", "cut_czk", "joint_czk", "accessory_czk", "packaging_czk", "joint_count", "weight_kg"))
     and po["cenovy_souhrn"]["material_czk"] + po["cenovy_souhrn"]["cut_czk"] + po["cenovy_souhrn"]["joint_czk"] + po["cenovy_souhrn"]["accessory_czk"] + po["cenovy_souhrn"]["extra_work_czk"] + po["cenovy_souhrn"]["packaging_czk"]
     + (po["cenovy_souhrn"].get("profile_flat_fee_czk") or 0) in range(po["price"]["net"] - 200, po["price"]["net"] + 200), po["cenovy_souhrn"])
over("F10 hmotnost: soucet katalogovych dilu + odhad vyplni (plocha x kg/m2) a tesneni; dil bez hmotnosti v seznamu", po["hmotnost_kg"] > 60 and isinstance(po["hmotnost_uplna"], bool) and isinstance(po["hmotnost_chybi"], list) and po["hmotnost_uplna"] == (not po["hmotnost_chybi"]), (po["hmotnost_kg"], po["hmotnost_chybi"]))
kg_vyplni = O.hmotnost_vyplni_kg(rj)
over("F11 odhad hmotnosti vyplni: plocha kusu x 4,8 kg/m2 (PC 4 mm) + tesneni 0,082 kg/m", abs(kg_vyplni - (sum(k_["e1"] * k_["e2"] for v in rj["vyplne"] for k_ in v["kusy"]) / 1e6 * 4.8 + sum(t["mnozstvi"] for t in rj["kusovnik"]["tesneni"]) * 0.082)) < 0.01 and 50 < kg_vyplni < 90, kg_vyplni)
mut = OS.pro_objednavku(VYCHOZI)
mut["bom"].clear(); mut["selection"]["w"] = 1
over("F12 vzdy hluboka kopie (zmena vysledku neovlivni dalsi volani)", OS.pro_objednavku(VYCHOZI)["bom"] and OS.pro_objednavku(VYCHOZI)["selection"]["w"] == 1500)
nd = OS.pro_objednavku({"w": 99999, "front": "xx"})
over("F13 neplatny vyber se oreze (ok true, valid true), nevyhodi", nd["ok"] and nd["valid"] and nd["selection"]["w"] == 4000 and nd["notices"], nd["notices"])

# ---------------------------------------------------------------------------------------------------------------------
print("== G token modelu a GLB")
tok = base["model"]["url"].rsplit("/", 1)[1]
p_tok, chyba = OS.over_model(tok)
over("G1 token: odpovida parametrum jadra efektivniho vyberu, nese vsechny klice jadra", chyba is None and p_tok == {k_: core[k_] for k_ in O.VYCHOZI} and OS.over_model(tok, ted=time.time() + 100)[1] is None)
over("G2 token: pozmeneny = podpis, vyprsely = vyprsel, cizi prefix / smeti = podpis", OS.over_model(tok[:-3] + "AAA")[1] == "podpis" and OS.over_model(tok, ted=time.time() + 10 ** 6)[1] == "vyprsel" and OS.over_model("dop.x.1.y")[1] == "podpis"
     and OS.over_model("opl.x")[1] == "podpis" and OS.over_model("")[1] == "podpis" and OS.over_model("opl.....")[1] == "podpis")
over("G3 token neni platny pro stul (nema stolovy tvar) a stolovy token neni platny pro oploceni", OS.over_model(SH.podepis_model(__import__("stul_konfigurator").sestav_stul(**SH.normalizuj({}, 30)[0])["parametry"]))[1] == "podpis")
rg = c.get("/api/shop/configurator/glb/" + tok)
over("G4 routa glb: 200 model/gltf-binary, GLB, hlavicky (noindex, private cache, Vary)", rg.status_code == 200 and rg.mimetype == "model/gltf-binary" and rg.data[:4] == b"glTF" and rg.headers.get("X-Robots-Tag") == "noindex"
     and "private" in rg.headers.get("Cache-Control", "") and "Accept-Encoding" in rg.headers.get("Vary", ""), (rg.status_code, rg.headers.get("Cache-Control")))
rb = c.get("/api/shop/configurator/glb/" + tok, headers={"Accept-Encoding": "br"})
rz = c.get("/api/shop/configurator/glb/" + tok, headers={"Accept-Encoding": "gzip"})
import brotli  # noqa: E402
over("G5 komprese: br -> brotli, gzip -> gzip, bez nich puvodni bajty; obsah stejny", rb.headers.get("Content-Encoding") == "br" and rz.headers.get("Content-Encoding") == "gzip" and brotli.decompress(rb.data) == rg.data
     == gzip.decompress(rz.data) and len(rb.data) < len(rg.data) / 2, (len(rg.data), len(rb.data), len(rz.data)))
over("G6 routa glb: spatny token 403, vyprsely 410, neznamy prefix tokenu stolu 403", c.get("/api/shop/configurator/glb/" + tok[:-3] + "AAA").status_code == 403 and c.get("/api/shop/configurator/glb/opl.zzz.1.sig").status_code == 403
     and c.get("/api/shop/configurator/glb/" + OS.podepis_model(core, ted=time.time() - 2 * OS.MODEL_PLATNOST_S)).status_code == 410)
gb = OS.glb_bytes(VYCHOZI)
over("G7 glb_bytes(vyber) = GLB, stejne bajty jako routa (verejny model); razitka=True = model do nabidky", gb[:4] == b"glTF" and gb == rg.data and OS.glb_bytes(VYCHOZI, razitka=True)[:4] == b"glTF")
sit_sel = dict(VYCHOZI, fill="mesh", front="wall", feet=True, lock="lock", **{"right": "door"})
g_pub, g_nab = OS.glb_bytes(sit_sel), OS.glb_bytes(sit_sel, razitka=True)
import struct  # noqa: E402


def json_glb(g):
    off, js = 12, None
    while off < len(g):
        ln, typ = struct.unpack("<II", g[off:off + 8])
        if typ == 0x4E4F534A:
            js = json.loads(g[off + 8:off + 8 + ln])
        off += 8 + ln
    return js


jp, jn = json_glb(g_pub), json_glb(g_nab)
over("G8 verejny model: textura site + zjednoduseny zamek a patky (mensi); model do nabidky: bez obrazku, plne dily", "images" in jp and "images" not in jn and len(g_pub) < len(g_nab) - 500000, (len(g_pub), len(g_nab)))
over("G9 model do nabidky: sit je prusvitna sedá bez textury (alfa v baseColorFactor)", any(m.get("alphaMode") == "BLEND" and abs(m["pbrMetallicRoughness"]["baseColorFactor"][3] - 0.5) < 1e-6 for m in jn["materials"]) and not any("baseColorTexture" in m["pbrMetallicRoughness"] for m in jn["materials"]))
spec = jp["scenes"][0]["extras"]["v3d"]
over("G10 spec v3d: mm, nahoru Y, celo +Z, koty (sirka, hloubka, vyska), look nat, bez pohybu", spec["u"] == "mm" and spec["up"] == [0, 1, 0] and spec["front"] == [0, 0, 1] and [d["t"] for d in spec["dims"]] == ["1 500", "1 500", "2 200"] and spec["motions"] == [], spec["dims"])
fence_spec = json_glb(OS.glb_bytes(dict(VYCHOZI, **fe)))["scenes"][0]["extras"]["v3d"]
over("G11 koty oploceni: sirka a vyska, bez hloubky", [d["t"] for d in fence_spec["dims"]] == ["4 000", "1 800"], fence_spec["dims"])
import v3d_glb  # noqa: E402
ok_san = []
for nazev, sel in (("vychozi", VYCHOZI), ("sit + zamek + patky", sit_sel), ("oploceni", dict(VYCHOZI, **fe)), ("dvoje dvere", dict(VYCHOZI, right="door", w=2600, d=1800))):
    try:
        raw = OS.glb_bytes(sel, razitka=True)
        out = v3d_glb.sanitize(raw, v3d_glb.embedded_spec(raw))
        g_, _b = v3d_glb.read_glb(out)
        v3d_glb.final_check(g_)
        ok_san.append((nazev, True))
    except Exception as e:                                           # noqa: BLE001
        ok_san.append((nazev, repr(e)[:120]))
over("G12 model do nabidky projde zakaznickou kontrolou (v3d_glb.sanitize + final_check) ve 4 konfiguracich", all(v is True for _n, v in ok_san), ok_san)
try:
    import v3d_mark  # noqa: E402
    sekret = v3d_mark.derive_secret(b"test-oploceni-klic")
    znac = []
    for nazev, sel in (("vychozi", VYCHOZI), ("sit + zamek + patky", sit_sel), ("oploceni", dict(VYCHOZI, **fe))):
        raw = OS.glb_bytes(sel, razitka=True)
        try:
            san = v3d_glb.sanitize(raw, v3d_glb.embedded_spec(raw))                       # jako nabidka_z_konfigurace: nejdriv zakaznicka kontrola, az pak znaceni
            out = v3d_mark.mark(san, 4242, sekret)
            nalez = v3d_mark.detect(out, sekret)                                           # (cislo nabidky, jistota): znacku jde z modelu precist
            znac.append((nazev, out[:4] == b"glTF" and nalez[0] == 4242))
        except Exception as e:                                       # noqa: BLE001
            znac.append((nazev, repr(e)[:120]))
    over("G13 model do nabidky jde neviditelne oznacit cislem nabidky a znacka se z nej precte (v3d_mark.mark + detect) ve 3 konfiguracich", all(v is True for _n, v in znac), znac)
except ImportError as e:
    over("G13 v3d_mark se nenacetl", False, str(e))

# ---------------------------------------------------------------------------------------------------------------------
print("== H rozcestnik a routy (stul beze zmeny)")
over("H1 modul pro produkt: oploceni -> oploceni_shop, stul / neznamy -> None", R.modul_pro(PID) is OS and R.modul_pro(PID_STUL) is None and R.modul_pro(PID_X) is None and R.modul_pro(None) is None and R.modul_pro("abc") is None)
over("H2 recepty a stare funkce: konfigurovatelny, je_dopravnik, dopravnik_pro, bez_montaze, mimo_stul", R.konfigurovatelny(PID) and R.konfigurovatelny(PID_STUL) and not R.konfigurovatelny(PID_X) and not R.je_dopravnik(PID)
     and R.dopravnik_pro(PID) is None and R.bez_montaze(PID) and not R.bez_montaze(PID_STUL) and R.mimo_stul(PID) and not R.mimo_stul(PID_STUL) and R.je_oploceni(PID) and not R.je_oploceni(PID_STUL))
over("H3 tokeny: opl. -> oploceni, dop. -> dopravnik, token stolu a smeti -> None", R.recept_z_tokenu("opl.a.1.b") == "oploceni_kryt" and R.recept_z_tokenu("dop.a.1.b") == "dopravnik_valeckovy" and R.recept_z_tokenu("eyJ.1.sig") is None
     and R.recept_z_tokenu("") is None and R.modul_z_tokenu("opl.a.1.b") is OS and R.modul_z_tokenu("xyz") is None)
over("H4 modul podle hashe: znamy hash -> oploceni_shop, neznamy -> None", R.modul_pro_hash(base["hash"]) is OS and R.modul_pro_hash("0123456789abcdef") is None)
over("H5 registr: pro_objednavku a glb_bytes pro oploceni jdou pres modul", R.pro_objednavku(VYCHOZI, None, "cs", PID)["kod"] == base["kod"] and R.glb_bytes(VYCHOZI, PID) == gb and R.glb_bytes(VYCHOZI, PID, razitka=True)[:4] == b"glTF")
rr = c.get("/api/shop/configurator/recepty/oploceni_kryt")
over("H6 routa recept -> id karty: verejnost 403", rr.status_code == 403 and rr.get_json() == {"error": "forbidden"})
rr = cs.get("/api/shop/configurator/recepty/oploceni_kryt")
over("H7 zamestnanec: 200 {recept, product_id, active (neexistujici karta = false)}", rr.status_code == 200 and rr.get_json() == {"recept": "oploceni_kryt", "product_id": PID, "active": False}, rr.get_json())
over("H8 routa recept: neznamy recept / recept bez karty = 404, recept stolu najde kartu stolu", cs.get("/api/shop/configurator/recepty/neexistuje").status_code == 404 and cs.get("/api/shop/configurator/recepty/dopravnik_valeckovy").status_code == 404
     and cs.get("/api/shop/configurator/recepty/" + SH.RECEPT).get_json()["product_id"] == PID_STUL)
rs_stul = c.get(f"/api/shop/products/{PID_STUL}/configurator")
js_stul = rs_stul.get_json()
over("H9 schema stolu beze zmeny (sloty stolu, vlastni rules_version, systems)", rs_stul.status_code == 200 and "recipe" not in js_stul and js_stul["slots"] and js_stul["rules_version"] != RV and "systems" in js_stul)
rst = c.post("/api/shop/configurator/resolve", json={"product_id": PID_STUL, "selection": {}})
jst = rst.get_json()
over("H10 resolve stolu beze zmeny (cena, platnost, model s tokenem stolu bez prefixu opl.)", rst.status_code == 200 and jst["valid"] and jst["price"] and not jst["model"]["url"].rsplit("/", 1)[1].startswith("opl."))
tok_stul = jst["model"]["url"].rsplit("/", 1)[1]
over("H11 GLB stolu s tokenem stolu = 200 a token stolu nema prefix oploceni", c.get("/api/shop/configurator/glb/" + tok_stul).status_code == 200 and R.recept_z_tokenu(tok_stul) is None)
over("H12 model stolu podle hashe stolu = 200 (rozcestnik neprebije stul)", c.get("/api/shop/configurator/model/" + jst["hash"]).status_code == 200)
over("H13 resolve: 409 pri jine verzi pravidel i u oploceni; produkt bez receptu 404", post(c, VYCHOZI, rules_version="x").status_code == 409 and c.post("/api/shop/configurator/resolve", json={"product_id": PID_X, "selection": {}}).status_code == 404)

# ---------------------------------------------------------------------------------------------------------------------
print("== I kosik a nabidka (jen cteni, nic se nezapisuje)")
cur = appmod.get_conn().cursor()
over("I1 kosik: konfigurovatelny, montaz se nenabizi (typ_produktu None), stul beze zmeny (STUL_SKLAD)", KK.je_konfigurovatelny(PID) and KK.typ_produktu(PID) is None and KK.typ_produktu(PID_STUL) == KK.TYP_SESTAVY and KK.typ_produktu(None) == KK.TYP_SESTAVY)
vy = KK.vyres(cur, PID, VYCHOZI, "cs", RV)
over("I2 vyres: cena ze serveru = resolve, hash, kod, bez montaze, rozmery_text, souhrn, kusovnik, hmotnost", vy["net_czk"] == base["price"]["net"] and vy["hash"] == base["hash"] and vy["kod"] == base["kod"] and vy["montaz_pct"] is None and vy["montaz_czk"] is None
     and vy["rozmery_text"] == "1500 × 1500 × 2200" and vy["selection"] == VYCHOZI and vy["bom"] == po["bom"] and vy["pocet_spoju"] == 54 and vy["weight_kg"] == po["hmotnost_kg"] and vy["price_summary"]["total_czk"] == base["price"]["net"], {k_: vy[k_] for k_ in ("net_czk", "montaz_pct", "rozmery_text")})
try:
    KK.vyres(cur, PID, VYCHOZI, "cs", "stara")
    over("I3 vyres s jinou verzi pravidel = rules_changed", False)
except KK.KonfiguraceChyba as e:
    over("I3 vyres s jinou verzi pravidel = rules_changed (409)", e.code == "rules_changed" and e.status == 409)
over("I4 nazev radku: rozmery z modulu (kryt 3 rozmery, oploceni 2) a kod; stary tvar pro stul a dopravnik beze zmeny", KK.jmeno_radku("Ochranný kryt", vy["selection"], vy["kod"], vy["rozmery_text"]) == f"Ochranný kryt – 1500 × 1500 × 2200 mm ({vy['kod']})"
     and KK.jmeno_radku("Oplocení", {}, "OPL-X", "4000 × 1800") == "Oplocení – 4000 × 1800 mm (OPL-X)" and KK.jmeno_radku("Stůl", {"w": 1500, "d": 800, "h": 750}, "STL-1") == "Stůl – 1500 × 800 × 750 mm (STL-1)"
     and KK.jmeno_radku("Dopravník", {"len": 2000, "width": 590}, "DOP-1") == "Dopravník – 2000 × 590 mm (DOP-1)" and KK.jmeno_radku("Něco", {}, "X-1") == "Něco (X-1)")
vyf = KK.vyres(cur, PID, dict(VYCHOZI, **fe), "cs", None)
over("I5 oploceni v kosiku: rozmery_text jen relevantni rozmery a nazev radku", vyf["rozmery_text"] == "4000 × 1800" and "4000 × 1800 mm" in KK.jmeno_radku("Oplocení", vyf["selection"], vyf["kod"], vyf["rozmery_text"]))


class Chyba(Exception):
    pass


def chyba_fn(zprava, status):
    return Chyba(f"{status}: {zprava}")


produkt = {"id": PID, "name": "Ochranný kryt a oplocení – konfigurovatelný"}
radek, kg, uplna = KK.radek_objednavky(cur, produkt, {"qty": 2, "configuration": {"selection": VYCHOZI, "rules_version": RV}, "montaz_zvolena": False}, None, chyba_fn)
over("I6 radek objednavky: product_id NULL (vyroba na zakazku), cena ze serveru x mnozstvi, nazev s rozmery a kodem, snimek s kusovnikem a vyberem", radek["product_id"] is None and radek["unit_price_czk"] == base["price"]["net"] and radek["line_total_czk"] == 2 * base["price"]["net"]
     and radek["product_name_snapshot"] == f"{produkt['name']} – 1500 × 1500 × 2200 mm ({base['kod']})" and radek["configuration_code"] == base["kod"] and json.loads(radek["configuration_json"])["selection"] == VYCHOZI
     and json.loads(radek["configuration_json"])["bom"] == po["bom"] and "_montaz_radek" not in radek and abs(kg - 2 * po["hmotnost_kg"]) < 1e-6 and uplna == po["hmotnost_uplna"], radek["product_name_snapshot"])
try:
    KK.radek_objednavky(cur, produkt, {"qty": 1, "configuration": {"selection": VYCHOZI, "rules_version": RV}, "montaz_zvolena": True}, None, chyba_fn)
    over("I7 montaz u oploceni se nenabizi = chyba objednavky", False)
except Chyba as e:
    over("I7 montaz u oploceni se nenabizi = chyba objednavky 409", str(e).startswith("409") and "Montáž" in str(e), str(e))
over("I8 montaz_pct_pro_typ(None) = None (bez typu sestavy); typ stolu beze zmeny", KK.montaz_pct_pro_typ(cur, None) is None and KK.montaz_pct_pro_typ(cur, KK.typ_produktu(PID)) is None)
over("I9 nabidka z konfigurace: oploceni je 'mimo stul' (bez systemu stolu a bez montaze), stul ne", R.mimo_stul(PID) and not R.mimo_stul(PID_STUL))
try:
    glb_n = NZ._zakaznicky_glb(vy["selection"], PID)
    over("I10 nabidka: zakaznicky model (razitka + sanitize + final_check) se postavi a je v limitu nabidky", glb_n[:4] == b"glTF" and len(glb_n) <= __import__("scene_offers").MAX_MODEL_BYTES, len(glb_n))
except Exception as e:                                                  # noqa: BLE001
    over("I10 nabidka: zakaznicky model se postavi", False, repr(e))

# ---------------------------------------------------------------------------------------------------------------------
print("== J meze, velikost a cas")
MAXK = dict(VYCHOZI, w=4000, d=4000, h=3000, front="door", right="door", back="door", left="door", door_pos="center", feet=True, lock="lock", fill="mesh")
t0 = time.time()
rm_ = res(MAXK)
t_res = time.time() - t0
over("J1 nejvetsi verejna konfigurace: valid, cena, model hotovo", rm_["valid"] and rm_["price"]["net"] > 100000 and rm_["model"]["stav"] == "hotovo", (rm_["valid"], rm_["errors"], rm_["model"]))
rmj = O.sestav_oploceni(**O.normalizuj(**OS._na_jadro(OS._zaklad(MAXK))))
over("J2 pocet dilu nejvetsi verejne konfigurace je pod stropem modelu", len(rmj["dily"]) <= OS.MAX_DILU_MODEL and len(rmj["dily"]) > 300, len(rmj["dily"]))
t0 = time.time()
g_max = OS.glb_bytes(MAXK)
t_glb = time.time() - t0
g_max_full = OS.glb_bytes(MAXK, razitka=True)
over("J3 verejny GLB nejvetsi konfigurace < 12 MB, brotli < 3 MB (puvodni plne dily bez zjednoduseni by byly vetsi)", len(g_max) < 12e6 and len(brotli.compress(g_max, quality=5, lgwin=24)) < 3e6 and len(g_max) < len(g_max_full), (len(g_max), len(brotli.compress(g_max, quality=5, lgwin=24)), len(g_max_full)))
over("J4 cas: resolve nejvetsi konfigurace < 3 s, stavba GLB < 6 s (na zatizenem stroji s rezervou)", t_res < 3.0 and t_glb < 6.0, (round(t_res, 2), round(t_glb, 2)))
over("J5 jadro umi vic nez verejnost (6000 x 6000), shop mezi ale oreze na 4000", O.sestav_oploceni(sirka=6000, hloubka=6000)["rozmery"]["sirka_mm"] == 6000.0 and res({"w": 6000, "d": 6000})["selection"]["w"] == 4000)
old = OS.MAX_DILU_MODEL
OS.MAX_DILU_MODEL = 100
try:
    rq = res(MAXK)
    glb_chyba = None
    try:
        OS.glb_bytes(MAXK)
    except O.OploceniChyba as e:
        glb_chyba = e.kod
    tok_q = OS.podepis_model(O.normalizuj(**OS._na_jadro(OS._zaklad(MAXK))))
    rq_glb = c.get("/api/shop/configurator/glb/" + tok_q)
    over("J6 strop poctu dilu modelu: resolve ma model 'chyba / prilis_velky' (cena a platnost zustanou), glb_bytes vyhodi, routa 413", rq["model"] == {"stav": "chyba", "url": None, "odhad_ms": 0, "kod": "prilis_velky"} and rq["valid"] and rq["price"]
         and glb_chyba == "prilis_velky" and rq_glb.status_code == 413, (rq["model"], glb_chyba, rq_glb.status_code))
finally:
    OS.MAX_DILU_MODEL = old
over("J7 nejmensi konfigurace 600 x 600 x 1000 a nejvetsi vyska 3000: valid", res({"w": 600, "d": 600, "h": 1000, "front": "wall"})["valid"] and res({"h": 3000})["valid"])
over("J8 cache resolve: opakovany dotaz je rychly (< 50 ms)", (lambda t: (res(MAXK), time.time() - t)[1] < 0.05)(time.time()))

# ---------------------------------------------------------------------------------------------------------------------
print("== K fuzz (300 nahodnych a nesmyslnych vyberu)")
rnd = random.Random(20261008)
VAL = {"w": [100, 599, 600, 777, 1500, 4000, 4001, 9e9, -1, "1500", "x", None, True, 1500.4], "d": [100, 600, 1234, 4000, 5000, None, "a"], "h": [500, 1000, 1079, 1700, 2200, 3000, 9999, None, "z"],
       "front": ["wall", "door", "open", "xx", None], "right": ["wall", "door", "open", "xx"], "back": ["wall", "door", "open"], "left": ["wall", "door", "open"],
       "roof": ["none", "frame", "fill", "xx", 3], "fill": list(OS.VYPLN) + ["xx", None], "door_w": [100, 600, 800, 1200, 1300, "q", None], "door_h": [None, "auto", 1000, 1500, 2000, 2400, 3000],
       "door_pos": ["left", "center", "right", "xx"], "door_hinge": ["left", "right", "xx"], "lock": ["latch", "lock", "none", "xx"], "feet": [True, False, 0, 1, "ano", None]}
for k_ in ("fill_front", "fill_right", "fill_back", "fill_left", "fill_roof"):
    VAL[k_] = ["auto"] + list(OS.VYPLN) + ["xx"]
zle = []
t0 = time.time()
for i in range(300):
    sel = {k_: rnd.choice(v) for k_, v in VAL.items() if rnd.random() < 0.6}
    try:
        r1 = OS.resolve(sel, rnd.choice(("cs", "en", "sk")))
        ef = r1["selection"]
        r2 = OS.resolve(ef, "cs")
        ok = (list(ef) == SLOTY and isinstance(r1["valid"], bool) and r1["valid"] and r1["price"] and r1["price"]["net"] > 0 and r2["selection"] == ef and r2["hash"] == r1["hash"] and r1["model"]["stav"] in ("hotovo", "chyba")
              and HEX16.match(r1["hash"]) and r1["dims"]["width_mm"] > 0)
        if not ok:
            zle.append((sel, "nepruchod"))
    except Exception as e:                                           # noqa: BLE001
        zle.append((sel, repr(e)[:100]))
over("K1 300 nahodnych vyberu: nikdy vyjimka, vzdy platny efektivni vyber (pevny bod), cena > 0, hash 16 hex", not zle, zle[:2])
over("K2 fuzz do 90 s", time.time() - t0 < 90, round(time.time() - t0, 1))
rr = c.post("/api/shop/configurator/resolve", data="{nesmysl", content_type="application/json")
over("K3 routa resolve s rozbitym JSON = 404 (bez produktu) a nikdy 500; telo s nesmyslnym vyberem = 200", rr.status_code == 404 and post(c, "nesmysl").status_code == 200 and post(c, {"w": {"a": 1}}).status_code == 200)

# ---------------------------------------------------------------------------------------------------------------------
print("== L preklady a dalsi")
for lang in ("en", "sk"):
    r1, r2 = res({"w": 800, "feet": True, "h": 1000, "front": "door"}, lang), res({"w": 800, "feet": True, "h": 1000, "front": "door"}, "cs")
    over(f"L1 {lang}: oznameni o uprave a duvody jsou v jazyce (ne cesky), maji stejny pocet", len(nt(r1)) == len(nt(r2)) == 2 and not any(re.search(r"nevejdou|upravena|zvýšena|Zůstala", n["message"]) for n in nt(r1))
         and not re.search(r"musí mít|nevejdou", r1["options"]["front"]["door"]["reason"] or "") and (r1["notices"][-1]["message"] != r2["notices"][-1]["message"]), [n["message"] for n in nt(r1)])
sady = [set(OS.TEXTY[l]) for l in ("cs", "en", "sk")]
over("L2 texty: stejne klice ve vsech jazycich, zadny prazdny", sady[0] == sady[1] == sady[2] and all(v for l in OS.TEXTY.values() for v in l.values()))
over("L3 oznameni a duvody: stejne klice a stejne zastupne symboly {x} ve vsech jazycich", all(set(OS.UPRAVA["cs"]) == set(OS.UPRAVA[l]) and all(set(re.findall(r"\{(\w+)\}", OS.UPRAVA["cs"][k_])) == set(re.findall(r"\{(\w+)\}", OS.UPRAVA[l][k_])) for k_ in OS.UPRAVA["cs"]) for l in ("en", "sk"))
     and all(set(OS.DUVOD["cs"]) == set(OS.DUVOD[l]) and set(OS.INFO["cs"]) == set(OS.INFO[l]) and set(OS.CHYBA["cs"]) == set(OS.CHYBA[l]) for l in ("en", "sk")))
over("L4 info upozorneni (norma, kotveni, dvere_siroke, sit) se ukazou zakaznikovi podle konfigurace a jazyka", [n["message"][:20] for n in res({"h": 2600, "door_w": 1100, "fill": "mesh"}, "en")["notices"] if n["action"] == "info"]
     == [OS.INFO["en"][i][:20] for i in ("norma", "kotveni", "dvere_siroke", "sit")], [n["message"][:20] for n in res({"h": 2600, "door_w": 1100, "fill": "mesh"}, "en")["notices"]])
over("L5 verejne texty nenesou interni nazvy ani jmena dodavatelu (BOM, souhrn, upozorneni)", not re.search(r"Dogus|Etial|product_|Object_|OPL-PC|OPL-SIT", json.dumps([po["bom"], po["souhrn"], base["notices"]], ensure_ascii=False)))
over("L6 verejna odpoved resolve a schema nenese tajne klice (HMAC, secret)", not re.search(r"secret|hmac|password", json.dumps([base, sc]).lower()))
over("L7 rules_version modulu = RULES_VERSION, verze pravidel jadra v pravidlech zustava", OS.RULES_VERSION == "2026-10-08.1" and O.VERZE_PRAVIDEL == "2026-10-08.1")

# ---------------------------------------------------------------------------------------------------------------------
print("== M karty vyplni v cene (prepnuti z virtualnich desek na karty bez zmeny kodu a API)")
ctx_zive = OS._kontext()
KARTA_ID = 990001
ctx_karty = dict(ctx_zive)
ctx_karty["parts"] = dict(ctx_zive["parts"], **{f"product_{KARTA_ID}": {"id": f"product_{KARTA_ID}", "name": "Testovaci deska PC cira (KARTA)", "layer": "produkt", "sku": "TEST-PC", "length_mm": None,
                                                                         "cross_section_mm": [None, None], "weight_kg": None, "price_czk": 1000.0, "price_per_cut_czk": None, "is_board_material": True,
                                                                         "source": "product", "scene_coef": False, "unit": "m2", "price_basis": None}})
ctx_karty["karty_vyplni"] = {"pc_cira": KARTA_ID}
orig_kontext = OS._kontext
OS._RESOLVE_CACHE.clear()
try:
    p_virt = res()
    st_virt = OS.staff_blok(VYCHOZI)
    po_virt = OS.pro_objednavku(VYCHOZI, RV, "cs", PID)
    d_virt = {t: res({"fill": t})["price"]["net"] for t in OS.VYPLN}
    OS._kontext = lambda: ctx_karty
    OS._RESOLVE_CACHE.clear()
    p_karta = res()
    jadro_v = OS._uprav(OS._zaklad(VYCHOZI))[1]
    r_v = O.sestav_oploceni(**jadro_v)
    plocha = sum(v["rozmer_tabule"][0] * v["rozmer_tabule"][1] / 1e6 for v in r_v["vyplne"] if v["typ"] == "pc_cira")
    pk = ctx_zive["pricing"]["packaging_pct"]
    over("M1 cena s kartou = cena jadra v kontextu s kartou a je nizsi nez s virtualni deskou", p_karta["price"]["net"] == int(OC.cena(r_v, ctx_karty, montaz_pct=0)["price_summary"]["total_czk"]) and p_karta["price"]["net"] < p_virt["price"]["net"],
         (p_karta["price"]["net"], p_virt["price"]["net"]))
    over("M2 rozdil ceny = plocha pc_cira x (cena karty - orientacni cena) vcetne balneho (nezavisly vypocet)", abs((p_karta["price"]["net"] - p_virt["price"]["net"]) - (-plocha * (O.VYPLNE["pc_cira"]["cena_m2"] - 1000.0) * (1 + pk / 100.0))) <= 3,
         (p_karta["price"]["net"] - p_virt["price"]["net"], -plocha * 150 * (1 + pk / 100.0)))
    over("M3 stejna konfigurace = stejny hash a kod, stejny tvar odpovedi (klice), stejne volby i texty", p_karta["hash"] == p_virt["hash"] and p_karta["kod"] == p_virt["kod"] and set(p_karta) == set(p_virt)
         and {k_: v for k_, v in p_karta.items() if k_ not in ("price", "options", "model")} == {k_: v for k_, v in p_virt.items() if k_ not in ("price", "options", "model")})
    d_karta = {t: res({"fill": t})["price"]["net"] for t in OS.VYPLN}
    over("M4 price_delta voleb vyplne s kartou = rozdil nezavisle znovu vyresenych cen (vybrana volba 0)", all(p_karta["options"]["fill"][t]["price_delta"] == d_karta[t] - p_karta["price"]["net"] for t in OS.VYPLN) and p_karta["options"]["fill"]["pc_clear"]["price_delta"] == 0,
         {t: (p_karta["options"]["fill"][t]["price_delta"], d_karta[t] - p_karta["price"]["net"]) for t in OS.VYPLN})
    over("M5 typ bez karty se cení dal virtualni deskou (stejne ceny jako bez karet), pc_clear (core pc_cira) z karty", all(d_karta[t] == d_virt[t] for t in OS.VYPLN if t != "pc_clear") and d_karta["pc_clear"] == p_karta["price"]["net"] and d_karta["pc_clear"] != d_virt["pc_clear"],
         (d_karta, d_virt))
    st_karta = OS.staff_blok(VYCHOZI)
    txt = json.dumps(st_karta["kusovnik"], ensure_ascii=False)
    over("M6 blok pro zamestnance: kusovnik ukazuje kartu a cena = cena resolve, bez karty virtualni deska (navrh karty)", "Testovaci deska PC cira (KARTA)" in txt and "OPL-PC-CIRY-04" not in txt and st_karta["cena"]["bez_dph"] == p_karta["price"]["net"]
         and "OPL-PC-CIRY-04" in json.dumps(st_virt["kusovnik"], ensure_ascii=False) and "KARTA" not in json.dumps(st_virt["kusovnik"], ensure_ascii=False))
    po_karta = OS.pro_objednavku(VYCHOZI, RV, "cs", PID)
    over("M7 pro_objednavku: cena z karty, verejny kusovnik beze zmeny (neutralni nazvy, bez nazvu karty)", po_karta["price"]["net"] == p_karta["price"]["net"] and po_karta["bom"] == po_virt["bom"] and "KARTA" not in json.dumps(po_karta, ensure_ascii=False))
    over("M8 hmotnost a dalsi udaje pro objednavku se kartou nemeni (karta vyplne hmotnost nema, odhad z plochy)", po_karta["hmotnost_kg"] == po_virt["hmotnost_kg"] and po_karta["souhrn"] == po_virt["souhrn"] and po_karta["rozmery_text"] == po_virt["rozmery_text"])
    r_post = post(c, VYCHOZI)
    over("M9 routa resolve vraci stejnou cenu jako modul (cache nema stare virtualni ceny)", r_post.status_code == 200 and r_post.get_json()["price"]["net"] == p_karta["price"]["net"], (r_post.status_code, r_post.get_json().get("price")))
finally:
    OS._kontext = orig_kontext
    OS._RESOLVE_CACHE.clear()
over("M10 po navratu kontextu bez karet je cena zase virtualni (nic se nezapise ani nezustane v cache)", res()["price"]["net"] == p_virt["price"]["net"])

print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
