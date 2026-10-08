#!/usr/bin/env python3
"""KROK 7 (shape_geometry_methods.id=11): zapis prepocitane sestavy 185
jako NOVY radek product_assemblies (puvodni radek 185 se NEEDITUJE).

Parts jsou vysledek scripts/tmp_2026-09-12_bot8_batch_185.js (kroky 3-5),
overeny timtez skriptem (krok 6 - 0 SAT kolizi s realnou karoserii, 0
mimo-toleranci svaru [leg1 sloupek/svislice + leg0 nosnik/svislice], 0
self-prekryvu).

Original id=185 ma kod_sestavy=NULL (na rozdil od K-075 sourozencu
332-337, kteri meli existujici kod_sestavy) - proto misto "puvodni +
'-1030'" se pouzije synteticky kod "K-119-A-1030" (karoserie_kod + verze
+ suffix), overeno pred insertem na unikatnost. car_model_id je v
puvodnim radku take NULL (nikdy nebyl dopocitan) - dosazen 43, odvozeno
primo ze zadani teto ulohy (car_bodies 123/124/125 -> car_models.id=43,
"Jumpy Crew Cab L3 16- [K-119]"), stejna konvence jako K-075 insert
skripty (car_model_id hardcoded z externe zjisteneho faktu, ne prevzat
z puvodniho radku).
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

NEW_PARTS_PATH = "/opt/konfigurator/scripts/tmp_2026-09-12_bot8_batch_185_parts.json"
VERIFY_REPORT_PATH = "/opt/konfigurator/scripts/tmp_2026-09-12_bot8_batch_185_report.json"

with open(NEW_PARTS_PATH) as f:
    new_parts = json.load(f)
with open(VERIFY_REPORT_PATH) as f:
    verify = json.load(f)

assert verify["satCollisions"] == 0, "SAT nenulo 0 - NEZAPISOVAT"
assert verify["gaps_bad"] == 0, "gap-check ma odchylku - NEZAPISOVAT"
assert verify["self_collisions"] == 0, "self-kolize nalezena - NEZAPISOVAT"
assert verify["legsPresent"]["leg0"] and verify["legsPresent"]["leg1"], "chybi ocekavana noha - NEZAPISOVAT"

NEW_CAR_MODEL_ID = 43  # Jumpy Crew Cab L3 16- [K-119], viz zadani ulohy
NEW_KOD_SESTAVY = "K-119-A-1030"

try:
    with conn.cursor() as cur:
        cur.execute("""SELECT name, kod_sestavy, karoserie_kod, typologie_id, profil_mm, verze,
                       typologie_varianta_id, horni_blok_varianta_id, dodatek, data
                       FROM product_assemblies WHERE id=185""")
        src = cur.fetchone()
        assert src is not None, "id=185 nenalezeno"
        assert src["kod_sestavy"] is None, "ocekavany NULL kod_sestavy zmenen mezitim - over rucne"

        old_data = json.loads(src["data"])

        # uzivatelnost kodu overit pred insertem (i kdyz uz overeno driv v
        # session, over znovu tesne pred zapisem kvuli soubezne bezicim botum)
        cur.execute("SELECT id FROM product_assemblies WHERE kod_sestavy=%s", (NEW_KOD_SESTAVY,))
        clash = cur.fetchone()
        assert clash is None, f"kod_sestavy {NEW_KOD_SESTAVY} uz existuje (id={clash['id'] if clash else None})"

        new_name = src["name"] + " [10/30mm od kolize]"

        new_data = {
            "parts": new_parts,
            "join_groups": old_data.get("join_groups", []),
            "frame_groups": old_data.get("frame_groups", []),
            "bom": [],
            "price_summary": None,
        }
        if "razitka" in old_data:
            new_data["razitka"] = old_data["razitka"]

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
            new_name, 4, NEW_CAR_MODEL_ID, src["karoserie_kod"], src["typologie_id"], src["profil_mm"], src["verze"],
            src["typologie_varianta_id"], src["horni_blok_varianta_id"], src["dodatek"], NEW_KOD_SESTAVY,
            10, 30, json.dumps(new_data, ensure_ascii=False), 1, 1, 0,
        ))
        new_id = cur.lastrowid
    conn.commit()
    print(f"OK: novy radek id={new_id}, kod_sestavy={NEW_KOD_SESTAVY}")
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
conn2.close()
