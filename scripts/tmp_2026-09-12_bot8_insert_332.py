#!/usr/bin/env python3
"""Krok 7 procedury shape_geometry_methods.id=11 pro product_assemblies.id=332.
Precte puvodni radek 332 (metadata), nahradi data.parts vysledkem
scripts/tmp_2026-09-12_bot8_batch_332.js (overeno scripts/tmp_2026-09-12_bot8_verify_332.js:
SAT=0, self-kolize=0, presne 0.000mm mezery na vsech dotcenych svarech),
a vlozi NOVY radek (NIKDY needituje puvodni 332)."""
import json, pymysql, sys

SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad"

env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

conn = pymysql.connect(
    host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
    user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"],
    cursorclass=pymysql.cursors.DictCursor, autocommit=False,
)

try:
    with conn.cursor() as cur:
        # cerstve nacteni puvodniho radku (ne cachovana data) v ramci
        # stejne transakce jako insert - minimalizuje race window
        cur.execute("SELECT * FROM product_assemblies WHERE id=332 FOR SHARE")
        orig = cur.fetchone()
        if not orig:
            print("CHYBA: id=332 nenalezeno", file=sys.stderr); sys.exit(1)

        new_parts = json.loads(open(SCRATCH + "/332_10_30_parts.json").read())
        orig_data = json.loads(orig["data"])
        if len(new_parts) != len(orig_data["parts"]):
            print(f"CHYBA: pocet dilu se lisi ({len(new_parts)} vs {len(orig_data['parts'])})", file=sys.stderr)
            sys.exit(1)

        new_kod = orig["kod_sestavy"] + "-1030"
        cur.execute("SELECT id FROM product_assemblies WHERE kod_sestavy=%s", (new_kod,))
        clash = cur.fetchall()
        if clash:
            print("CHYBA: kod_sestavy uz existuje:", clash, file=sys.stderr); sys.exit(1)

        new_data = {
            "parts": new_parts,
            "join_groups": orig_data.get("join_groups", []),
            "frame_groups": orig_data.get("frame_groups", []),
            "bom": [],
            "price_summary": None,
            "razitka": orig_data.get("razitka"),
        }
        new_name = orig["name"] + " [10/30mm od kolize]"

        cur.execute(
            """INSERT INTO product_assemblies
               (name, category_id, car_model_id, karoserie_kod, typologie_id, profil_mm,
                verze, typologie_varianta_id, horni_blok_varianta_id, dodatek, kod_sestavy,
                prepazka_rezerva_mm, podbeh_rezerva_mm, data, created_by, is_public, is_master)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                new_name, 4, orig["car_model_id"], orig["karoserie_kod"], orig["typologie_id"],
                orig["profil_mm"], orig["verze"], orig["typologie_varianta_id"],
                orig["horni_blok_varianta_id"], orig["dodatek"], new_kod,
                10, 30, json.dumps(new_data), 1, 1, 0,
            ),
        )
        new_id = cur.lastrowid
        conn.commit()
        print(json.dumps({"ok": True, "new_id": new_id, "kod_sestavy": new_kod, "name": new_name}))
except Exception as e:
    conn.rollback()
    print("CHYBA, rollback proveden:", repr(e), file=sys.stderr)
    raise
finally:
    conn.close()
