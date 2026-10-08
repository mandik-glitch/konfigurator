#!/usr/bin/env python3
"""Obrazky PRED / PO pro Roberta (bot8, 2026-10-08): razitka pri zivem tazeni. Stejny stul a stejne tazeni police nahoru (+delta), jednou jako DOSUD (dily se pohnou, razitka zustanou stat) a jednou NOVE (razitka jedou
s dilem, na kterem sedi). GLB z generatoru -> operace `zive` (kopie pravidel z v3d-ovladani.js, viz test_razitka_tazeni.py) -> prepsane vrcholy / polohy loga -> three.js (scripts/2026-10-08_oploceni/render_glb.js) -> PNG.
Pouziti: api/venv/bin/python3 scripts/2026-10-08_razitka_tazeni/render_obrazky.py [vystupni_adresar]      (STUL_API_OVERRIDE = kandidat; node + playwright + internet pro three.js z jsdelivr)"""
import json
import math
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2026-10-08_led_rucne"))
import _spolecne as C  # noqa: E402

S, G = C.nacti_generator()
import numpy as np  # noqa: E402
import stul_razitka as RZ  # noqa: E402

sys.path.insert(0, HERE)
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("tt", os.path.join(HERE, "test_razitka_tazeni.py"))
_src = open(os.path.join(HERE, "test_razitka_tazeni.py"), encoding="utf-8").read()
_fn = _src[_src.index("def gltf_a_uzly"):_src.index("def konfigurace")]                    # funkce gltf_a_uzly a klient_tazeni z testu (jedna kopie pravidel)
_ns = {"np": np, "json": json, "struct": struct}
exec(compile(_fn, "test_razitka_tazeni.py", "exec"), _ns)
gltf_a_uzly, klient_tazeni = _ns["gltf_a_uzly"], _ns["klient_tazeni"]

VYST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("SP", "/tmp"), "tazeni", "img")
os.makedirs(VYST, exist_ok=True)


def sestav_glb(orig, js, poz, logo):
    """GLB z puvodniho s prepsanymi vrcholy uzlu a polohami loga (accessor min / max se prepocte, aby se pohnute dily neoriznuly)."""
    dj = struct.unpack("<I", orig[12:16])[0]
    bin0 = 20 + dj + 8
    blob = bytearray(orig[bin0:])
    js = json.loads(json.dumps(js))
    for i, n in enumerate(js["nodes"]):
        if "mesh" in n and poz[i] is not None and "translation" not in n:
            acc = js["accessors"][js["meshes"][n["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
            bv = js["bufferViews"][acc["bufferView"]]
            a = np.asarray(poz[i], "<f4")
            blob[bv["byteOffset"]:bv["byteOffset"] + a.nbytes] = a.tobytes()
            acc["min"], acc["max"] = [float(x) for x in a.min(axis=0)], [float(x) for x in a.max(axis=0)]
    for uzel, p in logo.items():
        js["nodes"][uzel]["translation"] = [round(float(v), 4) for v in p]
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    celkem = 12 + 8 + len(jb) + 8 + len(blob)
    return struct.pack("<III", 0x46546C67, 2, celkem) + struct.pack("<II", len(jb), 0x4E4F534A) + jb + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob)


p = dict(system=30, sirka=2000, hloubka=800)
r = S.sestav_stul(**p)
r["ovladani_scena"] = S.ovladani_3d(r)
par = r["parametry"]
h = G.kanonicky_hash(par)
v = G.vodici(par, r)
ov = v["ovladani"]
rz = ov["razitka"]
glb = G.model_pro_parametry(par)[1]
js, poz = gltf_a_uzly(glb)
logo0 = {z["uzel"]: np.array(js["nodes"][z["uzel"]]["translation"], float) for z in rz}
tah = next(t for t in ov["tahy"] if t["id"] == "police_h1")
zmena = 220.0                                                                         # police o 22 cm nahoru
delta = zmena / tah["faktor"]
print("tah", tah["id"], "zmena", zmena, "razitek", len(rz), "hostitele pohybu:", sorted({z["dil"] for z in rz} & {i for o in tah["zive"] for i in o["ix"]}))
hybane = {i for o in tah["zive"] for i in o["ix"]}
jobs, popisky = [], {}
for nazev, pohybuj, titulek in (("pred", False, "PŘED – díly jedou, razítka zůstanou stát"), ("po", True, "PO – razítka jedou s dílem, na kterém sedí")):
    poz1, logo1 = klient_tazeni(poz, logo0, ov["zive_rozsahy"], ov.get("zive_rozsahy_extra"), tah, delta, rz, pohybuj)
    cesta = os.path.join(VYST, f"tazeni_{nazev}.glb")
    open(cesta, "wb").write(sestav_glb(glb, js, poz1, logo1))
    hosty = [z for z in rz if z["dil"] in hybane]
    z0 = hosty[0]                                                                     # razitko na hybanem dile pro detail
    Rm = S.kvat_na_matici(js["nodes"][z0["uzel"]]["rotation"])
    n = Rm @ [0.0, 0.0, 1.0]
    for jm, az, el, vz, cil in (("celek", -38, 14, 0, None), ("detail", math.degrees(math.atan2(n[0], n[2])), 14.0, 900.0, [float(x) for x in logo1[z0["uzel"]]])):
        out = os.path.join(VYST, f"tazeni_{nazev}_{jm}.png")
        jobs.append({"glb": cesta, "out": out, "az": az, "el": el, "w": 1400, "h": 900, "vzdal": vz, "cil": cil})
        popisky[out] = f"{titulek} (police o {zmena:.0f} mm výš)"
par2 = dict(par)                                                                       # po PUSTENI: presny model pro novou hodnotu (razitka se na novem hashi rozmisti znovu)
par2[tah["param"]] = tah["hodnota"] + zmena
glb2 = G.model_pro_parametry(S.sestav_stul(**par2)["parametry"])[1]
cesta2 = os.path.join(VYST, "tazeni_po_pusteni.glb")
open(cesta2, "wb").write(glb2)
out2 = os.path.join(VYST, "tazeni_po_pusteni_celek.png")
jobs.append({"glb": cesta2, "out": out2, "az": -38, "el": 14, "w": 1400, "h": 900, "vzdal": 0, "cil": None})
popisky[out2] = f"PO PUŠTĚNÍ – přesný model (razítka se rozmístí znovu; police o {zmena:.0f} mm výš)"
jp = os.path.join(VYST, "jobs.json")
json.dump(jobs, open(jp, "w"))
subprocess.run(["node", os.path.join(os.path.dirname(HERE), "2026-10-08_oploceni", "render_glb.js"), jp], check=False)
try:
    from PIL import Image, ImageDraw, ImageFont
    pismo = None
    for cesta in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(cesta):
            pismo = ImageFont.truetype(cesta, 28)
    for out, popis in popisky.items():
        im = Image.open(out).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, im.width, 52], fill=(255, 255, 255))
        d.text((16, 9), popis, fill=(20, 30, 45), font=pismo)
        im.save(out)
except Exception as e:                                                                  # noqa: BLE001
    print("popisky nepridany:", e)
