#!/usr/bin/env python3
"""Krok 7 procedury shape_geometry_methods.id=11 pro product_assemblies.id=286
(K-119, Jumpy Crew Cab L3, verze C). NEZAPISUJE do puvodniho radku 286 (nikdy,
viz procedura) - vklada NOVY radek se stejnymi metadaty, novou kolizni
rezervou (10/30mm) a transformovanymi dily ze
scripts/tmp_2026-09-12_bot8_batch_286.js, JEN po overeni verdikt=="OK" v
assembly286_verify_report.json (SAT 0 kolizi, seam gap 0.000mm, 0 novych
self-kolizi).

Spustit: api/venv/bin/python3 scripts/tmp_2026-09-12_bot8_insert_286.py
"""
import json
import sys

SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad"

env = {}
with open("/opt/konfigurator/api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

import pymysql

conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"],
                        cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

# --- over verifikacni report je OK, precti ho jako podminku sine qua non ---
with open(SCRATCH + "/assembly286_verify_report.json") as f:
    report = json.load(f)
if report["assembly_id"] != 286:
    sys.exit(f"verify report je pro jine id ({report['assembly_id']}), ne 286 - STOP")
if report["verdict"] != "OK":
    sys.exit(f"verify report verdikt={report['verdict']} (sat={report['sat_collisions']}, "
              f"seam_gap={report['seam_gap_mm']}, new_self={len(report['newProblems'])}) - NEZAPISOVAT, STOP")

# --- nacti puvodni radek 286 (cerstve, primo z DB - ne z cache) ---
cur.execute("SELECT * FROM product_assemblies WHERE id=286")
orig = cur.fetchone()
if not orig:
    sys.exit("product_assemblies.id=286 nenalezen - STOP")

orig_data = json.loads(orig["data"])

with open(SCRATCH + "/assembly286_parts_new.json") as f:
    new_parts = json.load(f)

if len(new_parts) != len(orig_data["parts"]):
    sys.exit(f"pocet dilu nesedi: puvodni {len(orig_data['parts'])} vs transformovane {len(new_parts)} - STOP")

# kod_sestavy: puvodni radek ma NULL (cela rodina K-119 nema vygenerovany
# formatovany kod - chybi profil_mm, viz scripts/2026-09-11_kod_sestavy_format.py
# docstring). "Pridej -1030 na konec" se tedy doslovne neda aplikovat (nic
# k pridani). Presny precedent (product_assemblies.id=184, K-118 - stejna
# situace, kod_sestavy=NULL) resil unikatnost pres NAME (pridal suffix
# "[10/30mm od kolize]"), kod_sestavy nechal NULL. Stejny postup tady.
new_kod_sestavy = orig["kod_sestavy"]
if new_kod_sestavy is not None:
    new_kod_sestavy = new_kod_sestavy + "-1030"
    if len(new_kod_sestavy) > 32:
        sys.exit(f"novy kod_sestavy delsi nez 32 znaku: {new_kod_sestavy!r} ({len(new_kod_sestavy)}) - STOP")
    cur.execute("SELECT id FROM product_assemblies WHERE kod_sestavy=%s", (new_kod_sestavy,))
    if cur.fetchone():
        sys.exit(f"kod_sestavy {new_kod_sestavy!r} uz existuje - STOP (kolize nazvu)")

new_name = orig["name"] + " [10/30mm od kolize]"
cur.execute("SELECT id FROM product_assemblies WHERE name=%s", (new_name,))
if cur.fetchone():
    sys.exit(f"name {new_name!r} uz existuje - STOP (kolize nazvu)")

new_data = {
    "parts": new_parts,
    "join_groups": orig_data.get("join_groups", []),
    "frame_groups": orig_data.get("frame_groups", []),
    "bom": [],
    "price_summary": None,
    "_note": (orig_data.get("_note") or "") +
        " | PREPOCET KOLIZNI REZERVY 2026-09-12 (bot8, shape_geometry_methods.id=11): "
        "2/20mm -> 10/30mm. Delty: deltaZ=+8mm na plne noze Z=-1522.500114440918 "
        "(predni-svislice/cap/spojnice-dolni/spojnice-horni/zadni-svislice-dolni/zaslepka x3, "
        "8 dilu, + uhelnik-noha0 x7 cele) a na sloupci sloupec0 (nosnik/spojnice/eurobox, rozpeti "
        "leg0..leg1, stred +4mm=deltaZ/2, nosnik delka -8mm). Na sdilenem Z=-260.50011444091797 "
        "(soucasne plna+vyrezova noha) zustava plna cast (predni-svislice/cap/spojnice-dolni/"
        "spojnice-horni/zaslepka x3, 7 dilu) BEZE ZMENY (overeno empiricky na hotovem paru "
        "product_assemblies 279->340 a znovu na 184->348, K-118, stejna topologie), meni se jen "
        "vyrezova trojice (sloupek-pred-podbehem/zadni-svislice-nad-zarezem/pricka-uzavreni-vyrezu, "
        "Y podle vzorce shape_geometry_methods.id=6) a uhelnik-noha1 (5 z 12 kusu, ty na svaru "
        "Y=141.0002/171.0002mm). Krok 4 (dorovnani pater): NEBYLO POTREBA - spodni hrana "
        "nejnizsiho patra (nosnik-sloupec0-patro0, Y=320.0002mm) ma po delte porad 168.9996mm "
        "kladnou rezervu nad novym Y_new nohy1 (151.0002mm), puvodni rezerva byla 179mm. "
        "Overeno: SAT test 0/64 kolizi s realnou GLB karoserii Citroën_Jumpy_CI19_2016- "
        "(_L/_R_D/_B), gap na posunutem svaru = 0.000000mm presne, self-kolize 0 novych "
        "(baseline puvodniho 286 mela taky 0 z 2016 testovanych paru). Skripty: "
        "scripts/tmp_2026-09-12_bot8_batch_286.js (transform, znovupouziva genericka "
        "transformAssembly() z tmp_2026-09-12_bot8_batch_184.js - stejna topologie jako K-118 "
        "184->348, + overeni krok 6 v jednom souboru).",
}

row = {
    "name": new_name,
    "category_id": 4,
    "car_model_id": 43,  # z zadani (family K-119 input data), orig mel NULL
    "karoserie_kod": orig["karoserie_kod"],
    "typologie_id": orig["typologie_id"],
    "profil_mm": orig["profil_mm"],
    "verze": orig["verze"],
    "typologie_varianta_id": orig["typologie_varianta_id"],
    "horni_blok_varianta_id": orig["horni_blok_varianta_id"],
    "dodatek": orig["dodatek"],
    "kod_sestavy": new_kod_sestavy,
    "prepazka_rezerva_mm": 10,
    "podbeh_rezerva_mm": 30,
    "data": json.dumps(new_data, ensure_ascii=False),
    "created_by": 1,
    "is_public": 1,
    "technicky_ok": 0,
    "is_master": 0,
}

cols = list(row.keys())
placeholders = ", ".join(["%s"] * len(cols))
sql = f"INSERT INTO product_assemblies ({', '.join(cols)}) VALUES ({placeholders})"
cur.execute(sql, [row[c] for c in cols])
new_id = cur.lastrowid
conn.commit()

print(f"OK: vlozen novy radek product_assemblies.id={new_id} kod_sestavy={new_kod_sestavy!r} name={new_name!r}")

# kontrola cerstvym spojenim
conn2 = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=env["DB_USER"],
                         password=env["DB_PASSWORD"], database=env["DB_NAME"],
                         cursorclass=pymysql.cursors.DictCursor)
cur2 = conn2.cursor()
cur2.execute("SELECT id, name, kod_sestavy, category_id, car_model_id, prepazka_rezerva_mm, podbeh_rezerva_mm, "
             "is_public, created_by, is_master, technicky_ok, JSON_LENGTH(data, '$.parts') n_parts "
             "FROM product_assemblies WHERE id=%s", (new_id,))
print("Kontrola (cerstve spojeni):", cur2.fetchone())

# over ze 286 zustalo nedotcene
cur2.execute("SELECT prepazka_rezerva_mm, podbeh_rezerva_mm, category_id, JSON_LENGTH(data, '$.parts') n_parts "
             "FROM product_assemblies WHERE id=286")
print("286 (puvodni, kontrola nezmeneno):", cur2.fetchone())
conn2.close()
print(f"\nNEW_ID={new_id}")
