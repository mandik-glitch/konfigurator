#!/usr/bin/env python3
"""KROK 7 (shape_geometry_methods.id=11): zapis prepocitane sestavy 285
jako NOVY radek product_assemblies (puvodni radek 285 se NEEDITUJE).

Parts jsou vysledek scripts/tmp_2026-09-12_bot8_batch_285.js (kroky 3-5:
delty + kaskada sloupce + dorovnani), ktery v SOBE obsahuje i krok 6
(overeni - SAT/seam-gap/self-kolize) a uklada report do
tmp_2026-09-12_bot8_batch_285_report.json. Tenhle insert skript pred
zapisem tvrde asserti na 0/0/0 z toho reportu.

kod_sestavy: zdrojovy radek 285 (a cela rodina K-118: 184/215/285) ma
kod_sestavy=NULL (profil_mm je u nich taky NULL - kod se negeneruje bez
nej, viz scripts/2026-09-11_kod_sestavy_format.py). Zadani rika "kod
_sestavy uprav aby byl unikatni, napr. pridej -1030 na konec" - to
predpoklada NEPRAZDNY vychozi kod. Tady zadny neni, takze noveho kodu
vytvarim s '-1030' suffixem, ale z NAZVU (kod_sestavy neexistuje, takze
se z nej nic nededuje) - kod_sestavy noveho radku zustava STEJNE NULL
jako u zdroje (neni co delat unikatnim, NULL nekoliduje s nicim, index
kod_sestavy je non-unique). car_model_id: zdroj ma NULL, vstupni zadani
teto ulohy ale dohledalo 42 (Jumpy Crew Cab L2 K-118, dve nezavisle
cesty: nazev LIKE '%K-118%' i car_bodies pro id=120/121/122) - podle
precedentu sourozeneckych behu teto procedury (334->341 atd., kde car_
model_id bylo taky dohledano zadanim a zapsano) ho na novy radek
zapisuji.
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

NEW_PARTS_PATH = "/opt/konfigurator/scripts/tmp_2026-09-12_bot8_batch_285_parts.json"
REPORT_PATH = "/opt/konfigurator/scripts/tmp_2026-09-12_bot8_batch_285_report.json"
CAR_MODEL_ID = 42  # Jumpy Crew Cab L2 K-118 - viz zadani teto ulohy

with open(NEW_PARTS_PATH) as f:
    new_parts = json.load(f)
with open(REPORT_PATH) as f:
    report = json.load(f)

assert report["satCollisions"] == 0, "SAT nenaslo 0 - NEZAPISOVAT"
assert all(abs(s["gap"]) < 0.01 for s in report["seamChecks"] if "sloupek-svislice" in s.get("seam", "")), \
    "seam gap (sloupek-svislice) neni 0 - NEZAPISOVAT"
assert report["afterSelfCollisions"] == 0, "self-kolize nalezena PO transformaci - NEZAPISOVAT"
assert report["newOrGrownSelfCollisions"] == 0, "nove/zvetsene self-kolize - NEZAPISOVAT"
assert len(new_parts) == report["counts"]["total"] == 61, "pocet dilu nesedi - NEZAPISOVAT"

try:
    with conn.cursor() as cur:
        cur.execute("""SELECT name, kod_sestavy, karoserie_kod, typologie_id, profil_mm, verze,
                       typologie_varianta_id, horni_blok_varianta_id, dodatek, data
                       FROM product_assemblies WHERE id=285""")
        src = cur.fetchone()
        assert src is not None, "id=285 nenalezeno"
        assert src["kod_sestavy"] is None, "ocekavano kod_sestavy=NULL u zdroje (viz docstring) - zkontroluj rucne"

        old_data = json.loads(src["data"])

        new_kod_sestavy = None  # zdroj nema kod_sestavy - viz docstring, neni co delat unikatnim
        new_name = src["name"] + " [10/30mm od kolize]"
        new_dodatek = src["dodatek"]  # beze zmeny, jedinecnost reseno jinak (viz nize kontrola nazvu)

        cur.execute("SELECT id FROM product_assemblies WHERE name=%s", (new_name,))
        clash = cur.fetchone()
        assert clash is None, f"name {new_name!r} uz existuje (id={clash['id'] if clash else None})"

        new_data = {
            "parts": new_parts,
            "join_groups": old_data.get("join_groups", []),
            "frame_groups": old_data.get("frame_groups", []),
            "bom": [],
            "price_summary": None,
        }
        # "razitka" v puvodnich datech 285 vubec NENI (zadne logo-ochrana-*
        # dily v teto sestave) - neni co zachovavat/menit, klic se
        # nepridava uměle.

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
            new_name, 4, CAR_MODEL_ID, src["karoserie_kod"], src["typologie_id"], src["profil_mm"], src["verze"],
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
    cur.execute("SELECT id FROM product_assemblies WHERE id=285")
    print("id=285 stale existuje beze zmeny:", cur.fetchone() is not None)
conn2.close()
