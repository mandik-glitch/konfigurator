#!/usr/bin/env python3
"""Krok 7 procedury shape_geometry_methods.id=11 pro product_assemblies.id=279.

NEZAPISUJE do puvodniho radku 279 (nikdy, viz procedura) - vklada NOVY radek
se stejnymi metadaty, novou kolizni rezervou (10/30mm) a transformovanymi
dily z scripts/tmp_2026-09-12_bot8_batch_279.js (jen po overeni 0 kolizi -
tenhle skript sam o sobe zadnou geometrii nepocita ani neoveruje).

Spustit: api/venv/bin/python3 scripts/tmp_2026-09-12_bot8_insert_279.py
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

conn = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"],
                        cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

# --- over verifikacni report je OK, precti ho jako podminku sine qua non ---
with open(SCRATCH + "/assembly279_verify_report.json") as f:
    report = json.load(f)
if report["assembly_id"] != 279:
    sys.exit(f"verify report je pro jine id ({report['assembly_id']}), ne 279 - STOP")
if report["verdict"] != "OK":
    sys.exit(f"verify report verdikt={report['verdict']} (sat={report['sat_collisions']}, "
              f"seam_fail={report['seam_fail']}, self={report['self_collisions']}) - NEZAPISOVAT, STOP")

# --- nacti puvodni radek 279 (cerstve, primo z DB - ne z cache) ---
cur.execute("SELECT * FROM product_assemblies WHERE id=279")
orig = cur.fetchone()
if not orig:
    sys.exit("product_assemblies.id=279 nenalezen - STOP")

orig_data = json.loads(orig["data"])

with open(SCRATCH + "/assembly279_transformed_parts.json") as f:
    new_parts = json.load(f)

if len(new_parts) != len(orig_data["parts"]):
    sys.exit(f"pocet dilu nesedi: puvodni {len(orig_data['parts'])} vs transformovane {len(new_parts)} - STOP")

new_kod_sestavy = orig["kod_sestavy"] + "-1030"
if len(new_kod_sestavy) > 32:
    sys.exit(f"novy kod_sestavy delsi nez 32 znaku: {new_kod_sestavy!r} ({len(new_kod_sestavy)}) - STOP")

cur.execute("SELECT id FROM product_assemblies WHERE kod_sestavy=%s", (new_kod_sestavy,))
if cur.fetchone():
    sys.exit(f"kod_sestavy {new_kod_sestavy!r} uz existuje - STOP (kolize nazvu)")

new_data = {
    "parts": new_parts,
    "join_groups": orig_data.get("join_groups", []),
    "frame_groups": orig_data.get("frame_groups", []),
    "bom": [],
    "price_summary": None,
    "razitka": orig_data.get("razitka", {}),
}

row = {
    "name": orig["name"],  # zkopirovano beze zmeny (POSTUP bod 5)
    "category_id": 4,
    "car_model_id": None,  # neni v seznamu kopirovanych metadat - nekopirovat puvodni NULL jinak nez NULL
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
    "is_master": 0,
}

cols = list(row.keys())
placeholders = ", ".join(["%s"] * len(cols))
sql = f"INSERT INTO product_assemblies ({', '.join(cols)}) VALUES ({placeholders})"
cur.execute(sql, [row[c] for c in cols])
new_id = cur.lastrowid
conn.commit()

print(f"OK: vlozen novy radek product_assemblies.id={new_id} kod_sestavy={new_kod_sestavy!r}")

# kontrola cerstvym spojenim
conn2 = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                         password=env["DB_PASSWORD"], database=env["DB_NAME"],
                         cursorclass=pymysql.cursors.DictCursor)
cur2 = conn2.cursor()
cur2.execute("SELECT id, name, kod_sestavy, category_id, prepazka_rezerva_mm, podbeh_rezerva_mm, "
             "is_public, created_by, is_master, JSON_LENGTH(data, '$.parts') n_parts "
             "FROM product_assemblies WHERE id=%s", (new_id,))
print("Kontrola (cerstve spojeni):", cur2.fetchone())
conn2.close()
print(f"\nNEW_ID={new_id}")
