#!/usr/bin/env python3
# Zapis vysledku sirokeho prepoctu kolizni rezervy (proc. id=11) na 12
# modelech (40 sestav, K-119 vynechano - uz hotovo drivejsi session).
# UPDATE primo na miste pro nechranene sestavy, INSERT (original NEDOTCEN)
# pro chranene (jen id=82 v tomhle davce).
import json, pymysql, sys, datetime

env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"], charset="utf8mb4",
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)

PROTECTED = {79, 82, 83, 116, 117, 134, 135, 151, 152, 173, 182, 189, 209, 219, 224, 250, 251,
             279, 289, 294, 320, 321, 332, 333, 334, 335, 336, 337}

# model -> car_model_id (pro pripadny INSERT vetev - jen K-293e/82 ji potrebuje v tomhle davce)
CAR_MODEL_ID = {
    "K-021": 284, "K-284": 301, "K-009": 52, "K-019": 283, "K-089": 235, "K-095e": 239,
    "K-125e": 46, "K-236": 261, "K-246e": 95, "K-253": 90, "K-286": 302, "K-293e": 188,
}

GROUPS = {
    "K-021": [126, 143, 144, 165, 166],
    "K-284": [118, 155, 156, 177, 178],
    "K-009": [94, 195, 265],
    "K-019": [125, 197, 267],
    "K-089": [72, 234, 304],
    "K-095e": [76, 242, 312],
    "K-125e": [188, 222, 292],
    "K-236": [104, 255, 325],
    "K-246e": [114, 211, 281],
    "K-253": [109, 205, 275],
    "K-286": [119, 252, 322],
    "K-293e": [82, 225, 295],
}

NOTE_SUFFIX = ("\n| PREPOCET KOLIZNI REZERVY 2026-09-12 (bot8, shape_geometry_methods.id=11): "
               "2/20mm -> 10/30mm. deltaZ=+8mm na noze u prepazky (empiricky overeno raycastingem "
               "proti realne car_body_B.glb geometrii), deltaY=+10mm na kazde vyrezove noze "
               "nezavisle na Z pozici. Dorovnani pater (krok 5-6) pocitano automaticky, strop na "
               "presne deltaY=10mm (viz reference_skript pro odduvodneni stropu u K-019). "
               "SAT proti realne karoserii + self-kolize overeno cisto pred zapisem "
               "(scripts/tmp_2026-09-12_bot8_wide_driver.js).")

results = []
cur = conn.cursor()

for model, ids in GROUPS.items():
    for aid in ids:
        with open(f"scripts/tmp_2026-09-12_bot8_wide_out_{aid}.json") as f:
            new_parts = json.load(f)

        cur.execute("SELECT id, name, kod_sestavy, category_id, data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        data = json.loads(row["data"])
        data["parts"] = new_parts
        data["bom"] = []
        data["price_summary"] = None
        old_note = data.get("_note") or ""
        data["_note"] = (old_note + NOTE_SUFFIX) if old_note else NOTE_SUFFIX.lstrip("\n| ")

        if aid in PROTECTED:
            new_name = row["name"] + " [10/30mm od kolize]"
            cur.execute("""
                INSERT INTO product_assemblies
                    (name, category_id, car_model_id, karoserie_kod, typologie_id, profil_mm, verze,
                     typologie_varianta_id, horni_blok_varianta_id, dodatek, kod_sestavy,
                     prepazka_rezerva_mm, podbeh_rezerva_mm, data, created_by, is_public,
                     technicky_ok, is_master)
                SELECT %s, 4, %s, karoserie_kod, typologie_id, profil_mm, verze,
                       typologie_varianta_id, horni_blok_varianta_id, dodatek, kod_sestavy,
                       10, 30, %s, created_by, is_public, 0, 0
                FROM product_assemblies WHERE id=%s
            """, (new_name, CAR_MODEL_ID[model], json.dumps(data, ensure_ascii=False), aid))
            new_id = cur.lastrowid
            results.append((model, aid, "INSERT", new_id))
        else:
            cur.execute("""
                UPDATE product_assemblies
                SET data=%s, prepazka_rezerva_mm=10, podbeh_rezerva_mm=30
                WHERE id=%s
            """, (json.dumps(data, ensure_ascii=False), aid))
            results.append((model, aid, "UPDATE", aid))

conn.commit()
print("ZAPSANO (commit proveden):")
for model, aid, op, target in results:
    print(f"  {model:8s} id={aid:4d} {op:6s} -> {target}")

# over po zapisu
print("\n--- overeni po zapisu ---")
for model, aid, op, target in results:
    cur.execute("SELECT id, prepazka_rezerva_mm, podbeh_rezerva_mm, category_id, JSON_LENGTH(data,'$.parts') as np FROM product_assemblies WHERE id=%s", (target,))
    r = cur.fetchone()
    print(f"  {model:8s} {op:6s} id={target}: prepazka={r['prepazka_rezerva_mm']} podbeh={r['podbeh_rezerva_mm']} category_id={r['category_id']} parts={r['np']}")

conn.close()
