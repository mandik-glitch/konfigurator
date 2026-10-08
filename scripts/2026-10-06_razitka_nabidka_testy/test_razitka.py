# -*- coding: utf-8 -*-
# Ochranna razitka LOGIMAN.CZ v 3D modelu online nabidky (bot4 2026-10-06; scripts/v3d/build_ctx.py + vandr_offer_build.py).
# A) _razitka_pro_ctx (atrapa kurzoru) a ctx_hash; B) SKUTECNY build karty 4454 (Blender, CPU) s razitky a bez nich + serverova
# pojistka v3d_glb.sanitize. Zadna DB, zadny zapis do repa (vystupy v $V3D_TEST_OUT / tmp).
# Spusteni: python3 test_razitka.py   (konci kodem 0 jen kdyz VSE prosla; ~40 s)
import copy
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2026-10-02_v3d_testy"))
sys.dont_write_bytecode = True
import _cesty as CE  # noqa: E402

sys.path.insert(0, os.path.join(CE.REPO, "scripts", "v3d"))
sys.path.insert(0, os.path.join(CE.REPO, "api"))
import build_ctx  # noqa: E402
import offer_model  # noqa: E402
import v3d_glb  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


# ---------------------------------------------------------------- A) ctx
class Kurzor:
    def __init__(self, razitka_json, glb=None, otisk="abc"):
        self.razitka_json, self.otisk = razitka_json, otisk
        self.glb = {"vypln_placka": "vypln_placka.glb", "logo_logiman_cz": "logo_logiman_cz.glb"} if glb is None else glb
        self._posl = None

    def execute(self, sql, params=None):
        self._posl = " ".join(sql.split())

    def fetchone(self):
        return {"vandr_razitka_json": self.razitka_json, "vandr_razitka_glb_otisk": self.otisk}

    def fetchall(self):
        return [{"id": k, "glb_file": v} for k, v in self.glb.items()]


def dil(pid="logo_logiman_cz", **kw):
    d = {"part_id": pid, "position": [1, 2, 3], "quaternion": [0, 0, 0, 1], "scale": [1, 1, 1], "role": "logo-ochrana-vandr-logo-0"}
    d.update(kw)
    return d


build_ctx.KATALOG_DIR = CE.KATALOG
va = []
ok = build_ctx._razitka_pro_ctx(Kurzor(json.dumps([dil("vypln_placka", base_color=[0.6, 0.6, 0.6], metalness=0.6, roughness=0.4), dil(), dil("jiny_dil")])), 1, va)
over("A1 platna data: jen razitkove dily (cizi part_id se zahodi), cesty a otisky katalogovych GLB, barva loga z razitkovac.py",
     ok and [d["part_id"] for d in ok["dily"]] == ["vypln_placka", "logo_logiman_cz"] and set(ok["glb"]) == {"vypln_placka", "logo_logiman_cz"}
     and all(g["sha12"] for g in ok["glb"].values()) and re.fullmatch(r"#[0-9A-Fa-f]{6}", ok["logo"]["hex"]) and not va, (ok, va))
over("A2 vypln nese barvu/kovovost/drsnost z dat, logo ne", ok["dily"][0].get("metalness") == 0.6 and "metalness" not in ok["dily"][1])
for nazev, kur in (("zadna data (NULL)", Kurzor(None)), ("prazdny seznam", Kurzor("[]")), ("neni JSON", Kurzor("{rozbite")),
                   ("neni seznam", Kurzor('{"a": 1}')), ("neplatna pozice", Kurzor(json.dumps([dil(position=[1, "x", 3])]))),
                   ("NaN v kvaternionu", Kurzor('[{"part_id": "logo_logiman_cz", "position": [0,0,0], "quaternion": [NaN,0,0,1], "scale": [1,1,1]}]')),
                   ("katalogove GLB chybi v DB", Kurzor(json.dumps([dil()]), glb={})),
                   ("soubor GLB neexistuje", Kurzor(json.dumps([dil()]), glb={"vypln_placka": "neni.glb", "logo_logiman_cz": "neni.glb"}))):
    va = []
    r = build_ctx._razitka_pro_ctx(kur, 1, va)
    over("A3 %s -> None, build bezi dal (varovani %s)" % (nazev, "ano" if nazev not in ("zadna data (NULL)", "prazdny seznam") else "ne"),
         r is None and (bool(va) == (nazev not in ("zadna data (NULL)", "prazdny seznam"))), (r, va))

base = json.load(open(os.path.join(HERE, "fixtures", "ctx_4454.json"), encoding="utf-8"))
h0 = build_ctx.ctx_hash(base)
k2 = copy.deepcopy(base); k2["razitka"]["logo"]["hex"] = "#112233"
k3 = copy.deepcopy(base); k3["razitka"]["dily"][0]["position"][0] += 1
k4 = copy.deepcopy(base); k4["razitka"]["glb"]["logo_logiman_cz"]["sha12"] = "ffffffffffff"
k5 = copy.deepcopy(base); k5["razitka"] = None
over("A4 klic cache (ctx_hash) se meni s barvou loga, pozici razitka, obsahem katalogoveho GLB i s vypnutim razitek",
     len({h0, build_ctx.ctx_hash(k2), build_ctx.ctx_hash(k3), build_ctx.ctx_hash(k4), build_ctx.ctx_hash(k5)}) == 5)
over("A5 stejny vstup -> stejny klic", build_ctx.ctx_hash(copy.deepcopy(base)) == h0)
over("A6 klic cache nese verzi buildu z obsahu kodu (zmena vandr_offer_build.py = novy model, stare bez razitek se nepouziji)",
     offer_model.verze_buildu().startswith("b3-"))


# ---------------------------------------------------------------- B) skutecny build
def ctx_s(razitka):
    c = copy.deepcopy(base)
    c["glb"] = os.path.join(CE.KATALOG, c["glb_file"])
    with open(os.path.join(CE.REPO, "scripts", "v3d", "pohyby-vychozi.json"), encoding="utf-8") as f:
        c["pohyby_vychozi"] = json.load(f)
    if razitka is None:
        c["razitka"] = None
    else:
        for pid, g in c["razitka"]["glb"].items():
            g["cesta"] = os.path.join(CE.KATALOG, os.path.basename(g["cesta"]))
    return c


if not os.path.exists(CE.BLENDER) or not os.path.isfile(ctx_s(True)["glb"]):
    print("SKIP B: Blender nebo katalogove GLB karty nenalezeny")
else:
    clean0, g0 = offer_model.spust_build(ctx_s(None)["glb"], ctx_s(None), 55)
    clean1, g1 = offer_model.spust_build(ctx_s(True)["glb"], ctx_s(True), 55)
    s0, s1 = g0["stats"], g1["stats"]
    over("B1 bez razitek: stats.razitka == 0", s0.get("razitka") == 0, s0.get("razitka"))
    over("B2 s razitky: vlozeno 22 (11 vyplni + 11 loga), 2 v pohyblivych skupinach", s1.get("razitka") == 22 and s1.get("razitka_pohyblivych") == 2, (s1.get("razitka"), s1.get("razitka_pohyblivych")))
    over("B3 rozmery modelu (overall_size) a kot se razitky NEZMENI", g0["overall_size_mm"] == g1["overall_size_mm"], (g0["overall_size_mm"], g1["overall_size_mm"]))
    pridano = s1["triangles"] - s0["triangles"]
    over("B4 pocet trojuhelniku roste jen o zjednodusena razitka (logo <= ~1000 tri, vypln 12): %d" % pridano, 11 * 8 <= pridano <= 11 * (1000 + 60) + 11 * 12 + 200, pridano)
    over("B5 velikost GLB zustava rozumna (< 1,5x zakladu + 1 MB): %d -> %d B" % (len(clean0), len(clean1)), len(clean1) < 1.5 * len(clean0) + 1_000_000, (len(clean0), len(clean1)))
    over("B6 pocet pohybu/pivotu stejny (razitka nevyrobila novy pohyb)", s0["pivots"] == s1["pivots"] and s0["motions"] == s1["motions"], (s0["pivots"], s1["pivots"], s0["motions"], s1["motions"]))
    over("B7 profily pro koty stejne (razitka do kot nepatri)", (g0["v3d"].get("profily") or g0["v3d"].get("profiles")) == (g1["v3d"].get("profily") or g1["v3d"].get("profiles")) if (g0["v3d"].get("profily") or g0["v3d"].get("profiles")) else True)
    over("B8 zadne varovani o razitkach", not [w for w in g1["warnings"] if "razitk" in w.lower()], g1["warnings"])
    try:
        offer = v3d_glb.sanitize(clean1, g1["v3d"])
        over("B9 serverova pojistka (sanitize) model s razitky PRIJME", offer[:4] == b"glTF", offer[:4])
    except Exception as e:  # noqa: BLE001
        offer = None
        over("B9 serverova pojistka (sanitize) model s razitky PRIJME", False, repr(e)[:300])
    if offer:
        l = struct.unpack("<I", offer[12:16])[0]
        js = json.loads(offer[20:20 + l])
        jmena = [n.get("name", "") for n in js.get("nodes", [])] + [m.get("name", "") for m in js.get("materials", [])] + [m.get("name", "") for m in js.get("meshes", [])]
        over("B10 v zakaznickem GLB nezustalo zadne jmeno logo/vandr/collider (razitka pod neutralnim jmenem)", not [j for j in jmena if re.search(r"logo|vandr|collider|fixarea", j, re.I)], [j for j in jmena if re.search(r"logo|vandr|collider|fixarea", j, re.I)][:5])
        lin = lambda c: ((c / 255.0) / 12.92 if c / 255.0 <= 0.04045 else (((c / 255.0) + 0.055) / 1.055) ** 2.4)
        cil = [lin(0xEB), lin(0x8E), lin(0x23)]
        barvy = [m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [0, 0, 0])[:3] for m in js.get("materials", [])]
        over("B11 v modelu je material barvy loga (oranzova #EB8E23 z razitkovac.py)", any(all(abs(a - b) < 0.02 for a, b in zip(b3, cil)) for b3 in barvy), [[round(x, 3) for x in b] for b in barvy][:8])

print("\nVYSLEDEK razitka v modelu nabidky: %d/%d OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
