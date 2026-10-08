#!/usr/bin/env python3
"""KROK 7 (shape_geometry_methods.id=11): zapis prepocitane sestavy 215
jako NOVY radek product_assemblies (puvodni radek 215 se NEEDITUJE).

Parts jsou vysledek scripts/tmp_2026-09-12_bot8_batch_215.js (krok 3-5,
self-check bit-presne proti jiz overenemu sourozenci 184->348), overeny
scripts/tmp_2026-09-12_bot8_verify_215.js (krok 6 - 0/65 SAT kolizi s realnou
karoserii K-118, gap 0.000mm na vyrezovem svaru, 0 self-prekryvu z 2080 paru).
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

NEW_PARTS_PATH = "/opt/konfigurator/scripts/tmp_2026-09-12_215_parts_new.json"
VERIFY_REPORT_PATH = "/opt/konfigurator/scripts/tmp_2026-09-12_215_verify_report.json"

with open(NEW_PARTS_PATH) as f:
    new_parts = json.load(f)
with open(VERIFY_REPORT_PATH) as f:
    verify = json.load(f)

assert verify["sat_collisions"] == 0, "SAT nenalo 0 - NEZAPISOVAT"
assert verify["gaps_bad"] == 0, "gap-check ma odchylku - NEZAPISOVAT"
assert verify["self_collisions"] == 0, "self-kolize nalezena - NEZAPISOVAT"

try:
    with conn.cursor() as cur:
        cur.execute("""SELECT name, kod_sestavy, karoserie_kod, typologie_id, profil_mm, verze,
                       typologie_varianta_id, horni_blok_varianta_id, dodatek, data
                       FROM product_assemblies WHERE id=215""")
        src = cur.fetchone()
        assert src is not None, "id=215 nenalezeno"

        old_data = json.loads(src["data"])

        # kod_sestavy u 215 (a celeho K-118) je NULL - nelze pridat "-1030"
        # suffix na neexistujici retezec. Sourozenec 184->348 (uz hotovo,
        # overeno v teto session) ponechal kod_sestavy taky NULL - sloupec
        # nema UNIQUE constraint (jen index), takze NULL nekoliduje.
        # Sjednoceno se stejnym precedentem.
        new_kod_sestavy = src["kod_sestavy"]  # None, stejne jako u 348
        new_name = src["name"] + " [10/30mm od kolize]"
        new_dodatek = src["dodatek"]

        if new_kod_sestavy is not None:
            cur.execute("SELECT id FROM product_assemblies WHERE kod_sestavy=%s", (new_kod_sestavy,))
            clash = cur.fetchone()
            assert clash is None, f"kod_sestavy {new_kod_sestavy} uz existuje (id={clash['id'] if clash else None})"

        new_data = {
            "parts": new_parts,
            "join_groups": old_data.get("join_groups", []),
            "frame_groups": old_data.get("frame_groups", []),
            "bom": [],
            "price_summary": None,
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
            new_name, 4, 42, src["karoserie_kod"], src["typologie_id"], src["profil_mm"], src["verze"],
            src["typologie_varianta_id"], src["horni_blok_varianta_id"], new_dodatek, new_kod_sestavy,
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
    # over, ze puvodni 215 zustal nedotceny
    cur.execute("""SELECT prepazka_rezerva_mm, podbeh_rezerva_mm, category_id,
                   JSON_LENGTH(data, '$.parts') n_parts FROM product_assemblies WHERE id=215""")
    print("puvodni 215 (musi zustat 2/20mm, category_id NULL):", cur.fetchone())
conn2.close()
