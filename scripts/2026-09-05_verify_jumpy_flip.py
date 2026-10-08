#!/usr/bin/env python3
"""Overeni 180-flipu rodiny Jumpy - GLB orientace + shoda sestav s predpocitanym cilem.

Read-only. Dve NEZAVISLE kontroly (obe musi projit):
  1. GLB: B_midZ kazde z 8 Jumpy karoserii musi byt < -50 (kriterium
     KAROSERIE_UMISTENI.md - "divam se do zadnich dveri auta").
  2. DB vs. predpocitany cil: sestavy 181/183/184/185/186/188 se musi shodovat
     s backups/2026-09-03_car_body_jumpy_l1_l3_crew_180_flip/assemblies_post/
     - to je nezavisle spocitany cilovy stav z 2026-09-03, ktery se nikdy
     neaplikoval. Shoda dvou nezavisle odvozenych vysledku = silny dukaz.
     (Overeno 2026-09-05: predpocitany 184.json sedi na dnesni zivy stav
     sestavy 184 s odchylkou 0,000000000.)

bot8 2026-09-05.
"""
import json
import os
import sys

sys.path.insert(0, "/opt/konfigurator/api")
os.chdir("/opt/konfigurator/api")
for _l in open(".env"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
import app as A  # noqa: E402

KAT = "/opt/konfigurator/webapp/katalog/car_bodies/"
POST = "/opt/konfigurator/backups/2026-09-03_car_body_jumpy_l1_l3_crew_180_flip/assemblies_post"
MODELY = [
    ("CI13", "Citroën_Jumpy_CI13_2016-", 181),
    ("CI14", "Citroën_Jumpy_CI14_2016-", 182),
    ("CI15", "Citroën_Jumpy_CI15_2016-", 183),
    ("CI18", "Citroën_Jumpy_CI18_2016-", 184),
    ("CI19", "Citroën_Jumpy_CI19_2016-", 185),
    ("CI24", "Citroën_Jumpy_CI24_2021-", 186),
    ("CI25", "Citroën_Jumpy_CI25_2021-", 187),
    ("CI26", "Citroën_Jumpy_CI26_2021-", 188),
]


def b_midz(path):
    """B_midZ primo z hlavicky GLB (accessors[].min/max), bez dekodovani bin chunku."""
    import struct
    b = open(path, "rb").read()
    off = 12
    while off < len(b):
        ln, ty = struct.unpack_from("<II", b, off)
        if ty == 0x4E4F534A:
            j = json.loads(b[off + 8:off + 8 + ln].decode("utf8"))
            for mesh in j["meshes"]:
                for prim in mesh["primitives"]:
                    acc = j["accessors"][prim["attributes"]["POSITION"]]
                    return (acc["min"][2] + acc["max"][2]) / 2.0
        off += 8 + ln
    raise ValueError("POSITION accessor nenalezen: " + path)


fail = 0

print("=== 1/2 GLB orientace (kriterium B_midZ < -50) ===")
for kod, base, _asm in MODELY:
    p = KAT + base + "_B.glb"
    if not os.path.exists(p):
        print(f"  {kod}  CHYBI {p}")
        fail += 1
        continue
    mid = b_midz(p)
    ok = mid < -50
    print(f"  {kod}  B_midZ = {mid:9.1f}  {'OK' if ok else '>>> STALE SPATNE <<<'}")
    if not ok:
        fail += 1

print()
print("=== 2/2 sestavy vs. nezavisle predpocitany cil (2026-09-03) ===")
conn = A.get_conn()
cur = conn.cursor()
for _kod, _base, asm in MODELY:
    pre_path = os.path.join(POST, f"{asm}.json")
    if not os.path.exists(pre_path):
        continue  # 182/187 (CI14/CI25) predpocitane nemaji - byly opravene driv
    cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (asm,))
    row = cur.fetchone()
    if not row:
        print(f"  id={asm}  sestava v DB NEEXISTUJE")
        fail += 1
        continue
    live = json.loads(row["data"])
    pre = json.load(open(pre_path))
    pre = pre.get("data", pre)
    lp, pp = live.get("parts", []), pre.get("parts", [])
    if len(lp) != len(pp):
        print(f"  id={asm}  ROZDILNY POCET DILU: live {len(lp)} vs cil {len(pp)}")
        fail += 1
        continue
    maxd, bad = 0.0, 0
    for a, b in zip(lp, pp):
        if a["part_id"] != b["part_id"]:
            bad += 1
            continue
        for i in range(3):
            maxd = max(maxd, abs(a["position"][i] - b["position"][i]))
        for i in range(4):
            maxd = max(maxd, abs(a["quaternion"][i] - b["quaternion"][i]))
    ok = bad == 0 and maxd < 1e-6
    print(f"  id={asm}  dilu={len(lp):3d}  neshod_part_id={bad}  max_odchylka={maxd:.9f}  "
          f"{'OK' if ok else '>>> NESHODA <<<'}")
    if not ok:
        fail += 1

print()
print("VYSLEDEK:", "VSE OK" if fail == 0 else f"{fail} PROBLEMU - necommitovat, resit")
sys.exit(1 if fail else 0)
