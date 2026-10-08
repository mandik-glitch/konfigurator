#!/usr/bin/env python3
"""KROK 7 (shape_geometry_methods.id=11): zapis prepocitane sestavy 337
jako NOVY radek product_assemblies (puvodni radek 337 se NEEDITUJE).

Parts jsou vysledek scripts/tmp_2026-09-12_bot8_batch_337.js (kroky 3-5 +
krok 6 overeni VSE V JEDNOM SOUBORU, viz report): 0 SAT kolizi s realnou
karoserii, 0.000mm mezery na vsech dotcenych svarech, 0 self-kolizi (baseline
i po transformaci - vcetne 12 paru, ktere v prvni verzi skriptu vysly jako
nove/zvetsene, po prevzeti opraveneho vzorce ze sourozence 336
(scripts/tmp_2026-09-12_bot8_batch_336.js, uspesne vlozen jako id=345) uz
vychazi cistě).
"""
import json
import pymysql

env = {}
with open("/opt/konfigurator/api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

conn = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"],
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)

NEW_PARTS_PATH = "/opt/konfigurator/scripts/tmp_2026-09-12_bot8_batch_337_parts.json"
REPORT_PATH = "/opt/konfigurator/scripts/tmp_2026-09-12_bot8_batch_337_report.json"

with open(NEW_PARTS_PATH) as f:
    new_parts = json.load(f)
with open(REPORT_PATH) as f:
    report = json.load(f)

assert report["satCollisions"] == 0, "SAT nenulove - NEZAPISOVAT"
assert all(abs(s["gap"]) < 0.01 or s.get("gap", 999) > 100 for s in report["seamChecks"]), \
    "gap-check ma odchylku na dotcenem svaru - NEZAPISOVAT"
assert report["newOrGrownSelfCollisions"] == 0, "nove/zvetsene self-kolize nalezeny - NEZAPISOVAT"

try:
    with conn.cursor() as cur:
        cur.execute("""SELECT name, kod_sestavy, karoserie_kod, typologie_id, profil_mm, verze,
                       typologie_varianta_id, horni_blok_varianta_id, dodatek, data
                       FROM product_assemblies WHERE id=337""")
        src = cur.fetchone()
        assert src is not None, "id=337 nenalezeno"

        old_data = json.loads(src["data"])

        new_kod_sestavy = src["kod_sestavy"] + "-1030"
        new_name = src["name"] + " [10/30mm od kolize]"

        cur.execute("SELECT id FROM product_assemblies WHERE kod_sestavy=%s", (new_kod_sestavy,))
        clash = cur.fetchone()
        assert clash is None, f"kod_sestavy {new_kod_sestavy} uz existuje (id={clash['id'] if clash else None})"

        new_data = {
            "parts": new_parts,
            "join_groups": old_data.get("join_groups", []),
            "frame_groups": old_data.get("frame_groups", []),
            "bom": [],
            "price_summary": None,
            "razitka": old_data.get("razitka"),
        }

        cur.execute("""
            INSERT INTO product_assemblies
                (name, category_id, car_model_id, karoserie_kod, typologie_id, profil_mm, verze,
                 typologie_varianta_id, horni_blok_varianta_id, dodatek, kod_sestavy,
                 prepazka_rezerva_mm, podbeh_rezerva_mm, data, created_by, is_public, is_master)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s)
        """, (
            new_name, 4, 7, src["karoserie_kod"], src["typologie_id"], src["profil_mm"], src["verze"],
            src["typologie_varianta_id"], src["horni_blok_varianta_id"], src["dodatek"], new_kod_sestavy,
            10, 30, json.dumps(new_data, ensure_ascii=False), 1, 1, 0,
        ))
        new_id = cur.lastrowid
    conn.commit()
    print(f"OK: novy radek id={new_id}, kod_sestavy={new_kod_sestavy}")
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()

# cerstve overeni zapisu novym spojenim
conn2 = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                         password=env["DB_PASSWORD"], database=env["DB_NAME"],
                         cursorclass=pymysql.cursors.DictCursor)
with conn2.cursor() as cur:
    cur.execute("""SELECT id, name, kod_sestavy, category_id, car_model_id, prepazka_rezerva_mm,
                   podbeh_rezerva_mm, is_public, is_master, created_by, dodatek,
                   JSON_LENGTH(data, '$.parts') n_parts FROM product_assemblies WHERE id=%s""", (new_id,))
    print(cur.fetchone())
    cur.execute("SELECT id, name, kod_sestavy, prepazka_rezerva_mm, podbeh_rezerva_mm FROM product_assemblies WHERE id=337")
    print("original 337 unchanged check:", cur.fetchone())
conn2.close()
