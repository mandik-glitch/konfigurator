#!/usr/bin/env python3
"""Zapise vysledky scripts/tmp_2026-09-12_bot8_wide_process.js (wide_out/<id>.json,
kazdy jiz overeny: ok=true, sat.collisions=0) do DB - shape_geometry_methods.id=11,
14 modelu (45 sestav) pridelenych tehle session.

Chranene ID (zakaz preulozeni 2026-09-11) dostavaji NOVY radek (INSERT, kopie
metadat, category_id=4, kod_sestavy+'-1030', nazev+' [10/30mm od kolize]') -
original NEDOTCEN. Nechranene ID -> primy UPDATE (data + prepazka/podbeh mm).

Pred zapisem zaloha puvodniho `data` do backups/2026-09-12_kolizni_rezerva_wide_bot8/
(sdileny adresar se soubeznou sesterskou session - kazda pise jen SVE ID, zadna kolize).
"""
import json
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402

PROTECTED = {79, 82, 83, 116, 117, 134, 135, 151, 152, 173, 182, 189, 209, 219, 224,
             250, 251, 279, 289, 294, 320, 321, 332, 333, 334, 335, 336, 337}

OUT_DIR = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/wide_out"
BACKUP_DIR = "/opt/konfigurator/backups/2026-09-12_kolizni_rezerva_wide_bot8"
os.makedirs(BACKUP_DIR, exist_ok=True)

MODELS = json.load(open("/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/models.json"))
ALL_IDS = [aid for m in MODELS for aid in m["ids"]]

conn = get_conn()
updated, inserted, skipped = [], [], []
try:
    with conn.cursor() as cur:
        for aid in ALL_IDS:
            outpath = f"{OUT_DIR}/{aid}.json"
            if not os.path.exists(outpath):
                skipped.append((aid, "chybi vystupni soubor"))
                continue
            result = json.load(open(outpath))
            rep = result["report"]
            if not rep.get("ok"):
                skipped.append((aid, rep.get("error")))
                continue
            new_data = result["data"]  # {"parts": [...], "join_groups":..., ...} - cely puvodni data, jen parts zmenene

            cur.execute(
                "SELECT name, category_id, car_model_id, karoserie_kod, typologie_id, profil_mm, verze, "
                "typologie_varianta_id, horni_blok_varianta_id, dodatek, kod_sestavy, data, is_public, is_master "
                "FROM product_assemblies WHERE id=%s", (aid,)
            )
            src = cur.fetchone()
            assert src is not None, f"id={aid} nenalezeno"

            # zaloha PRED zapisem
            with open(f"{BACKUP_DIR}/{aid}_before.json", "w", encoding="utf-8") as f:
                f.write(src["data"])

            new_data_json = json.dumps(new_data, ensure_ascii=False)

            if aid in PROTECTED:
                new_kod = (src["kod_sestavy"] + "-1030") if src["kod_sestavy"] else None
                new_name = src["name"] + " [10/30mm od kolize]"
                if new_kod:
                    cur.execute("SELECT id FROM product_assemblies WHERE kod_sestavy=%s", (new_kod,))
                    clash = cur.fetchone()
                    assert clash is None, f"kod_sestavy {new_kod} uz existuje (id={clash['id'] if clash else None})"
                cur.execute(
                    "INSERT INTO product_assemblies "
                    "(name, category_id, car_model_id, karoserie_kod, typologie_id, profil_mm, verze, "
                    " typologie_varianta_id, horni_blok_varianta_id, dodatek, kod_sestavy, "
                    " prepazka_rezerva_mm, podbeh_rezerva_mm, data, created_by, is_public, is_master) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s,%s,%s)",
                    (new_name, 4, src["car_model_id"], src["karoserie_kod"], src["typologie_id"],
                     src["profil_mm"], src["verze"], src["typologie_varianta_id"], src["horni_blok_varianta_id"],
                     src["dodatek"], new_kod, 10, 30, new_data_json, 1, src["is_public"], 0)
                )
                new_id = cur.lastrowid
                inserted.append((aid, new_id))
                print(f"id={aid} (CHRANENA): INSERT -> novy radek id={new_id}")
            else:
                cur.execute(
                    "UPDATE product_assemblies SET data=%s, prepazka_rezerva_mm=10, podbeh_rezerva_mm=30 WHERE id=%s",
                    (new_data_json, aid)
                )
                updated.append(aid)
                print(f"id={aid}: UPDATE OK")

    conn.commit()
    print(f"\nCOMMIT hotovo. updated={len(updated)} inserted={len(inserted)} skipped={len(skipped)}")
finally:
    conn.close()

if skipped:
    print("\nPRESKOCENO:")
    for aid, why in skipped:
        print(f"  id={aid}: {why}")

# over po zapisu
conn2 = get_conn()
try:
    with conn2.cursor() as cur:
        bad = 0
        for aid in updated:
            cur.execute("SELECT prepazka_rezerva_mm, podbeh_rezerva_mm, JSON_LENGTH(data,'$.parts') AS n FROM product_assemblies WHERE id=%s", (aid,))
            r = cur.fetchone()
            if r["prepazka_rezerva_mm"] != 10 or r["podbeh_rezerva_mm"] != 30:
                bad += 1
                print("PROBLEM (update) id=", aid, r)
        for old_aid, new_id in inserted:
            cur.execute("SELECT prepazka_rezerva_mm, podbeh_rezerva_mm, category_id, JSON_LENGTH(data,'$.parts') AS n FROM product_assemblies WHERE id=%s", (new_id,))
            r = cur.fetchone()
            if r["prepazka_rezerva_mm"] != 10 or r["podbeh_rezerva_mm"] != 30 or r["category_id"] != 4:
                bad += 1
                print("PROBLEM (insert) old=", old_aid, "new=", new_id, r)
            cur.execute("SELECT prepazka_rezerva_mm, podbeh_rezerva_mm, category_id FROM product_assemblies WHERE id=%s", (old_aid,))
            orig = cur.fetchone()
            if orig["prepazka_rezerva_mm"] != 2 or orig["podbeh_rezerva_mm"] != 20:
                bad += 1
                print("PROBLEM: puvodni chranena sestava SE ZMENILA! id=", old_aid, orig)
        print(f"\nOVERENI: {'VSE OK' if not bad else str(bad) + ' PROBLEMU'}")
finally:
    conn2.close()
