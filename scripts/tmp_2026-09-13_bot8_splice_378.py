"""Chirurgicky splice oprava #378 (Doblo K-075 B, hbv=4) - nahrazuje rozdeleny
podelnik-celni/zadni-horni-0/-1 (spatna vyska Y=1175, split na 2 kusy) jednim
prubeznym kusem na spravne vysce Y=1205 (rozsah [1190,1220]) - presne stejny
vzor jako uz overene a hotove verze A (#381/382/383). Box-split (col0/col1)
se NEMENI (mimo rozsah teto opravy, viz rozhodnuti koordinatora).

Pricka-horni-0/1/2 (3 kusy, po jednom na kazde noze) se jen presunou na Y=1205.

Uhelnik-noha0/1/2 overeny: max Y=921.5, min 250mm pod podelnikem - nedotcene.

Zaloha PRED zapisem: backups/2026-09-13_horni_blok_oprava_378/pred_zapisem.json
"""
import copy
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402

AID = 378
DRY = "--dry-run" in sys.argv

conn = get_conn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (AID,))
        row = cur.fetchone()
        d = json.loads(row["data"])
        zaloha = copy.deepcopy(d)
        parts = d["parts"]

        # 1) najdi a smaz rozdelene podelniky
        split_roles = {"podelnik-celni-horni-0", "podelnik-celni-horni-1",
                        "podelnik-zadni-horni-0", "podelnik-zadni-horni-1"}
        removed = [p for p in parts if p.get("role") in split_roles]
        assert len(removed) == 4, f"cekal jsem 4 split podelniky, nasel {len(removed)}"
        parts = [p for p in parts if p.get("role") not in split_roles]

        celni_q = next(p["quaternion"] for p in removed if p["role"].startswith("podelnik-celni"))
        zadni_q = next(p["quaternion"] for p in removed if p["role"].startswith("podelnik-zadni"))
        celni_x = next(p["position"][0] for p in removed if p["role"].startswith("podelnik-celni"))
        zadni_x = next(p["position"][0] for p in removed if p["role"].startswith("podelnik-zadni"))

        # 2) Z-rozsah z krajnich noh (predni-svislice) - stejne vozidlo jako A/C,
        # overeno rucne shodne pozice pred timhle skriptem.
        svislice = sorted((p for p in parts if p.get("role") == "predni-svislice"),
                           key=lambda p: p["position"][2])
        z_front_center = svislice[0]["position"][2]
        z_back_center = svislice[-1]["position"][2]
        T = 30.0
        z0 = z_front_center + T / 2
        z1 = z_back_center - T / 2
        z_stred = (z0 + z1) / 2
        delka = z1 - z0
        Y_STRED = 1205.0

        parts.append({"part_id": "Object_7", "position": [celni_x, Y_STRED, z_stred],
                       "quaternion": celni_q, "scale": [1, delka / 1000, 1],
                       "role": "podelnik-celni-horni"})
        parts.append({"part_id": "Object_7", "position": [zadni_x, Y_STRED, z_stred],
                       "quaternion": zadni_q, "scale": [1, delka / 1000, 1],
                       "role": "podelnik-zadni-horni"})

        # 3) pricka-horni-* jen presunout Y 1175 -> 1205
        moved = 0
        for p in parts:
            if str(p.get("role", "")).startswith("pricka-horni"):
                assert abs(p["position"][1] - 1175) < 0.01, f"neocekavana Y u {p['role']}: {p['position'][1]}"
                p["position"][1] = Y_STRED
                moved += 1
        assert moved == 3, f"cekal jsem presunout 3 pricka-horni, presunul {moved}"

        d["parts"] = parts
        d["bom"] = []
        d["price_summary"] = None

        print(f"Z0={z0} Z1={z1} stred={z_stred} delka={delka} scale.y={delka/1000}")
        print(f"puvodne {len(zaloha['parts'])} dilu -> {len(parts)} dilu")
        print("novy podelnik-celni-horni:", [p for p in parts if p.get("role") == "podelnik-celni-horni"][0])
        print("novy podelnik-zadni-horni:", [p for p in parts if p.get("role") == "podelnik-zadni-horni"][0])

        if DRY:
            print("\n--DRY RUN-- nic nezapsano")
        else:
            import os
            os.makedirs("/opt/konfigurator/backups/2026-09-13_horni_blok_oprava_378", exist_ok=True)
            with open("/opt/konfigurator/backups/2026-09-13_horni_blok_oprava_378/pred_zapisem.json", "w", encoding="utf-8") as f:
                json.dump({"id": AID, "name": row["name"], "data": zaloha}, f, ensure_ascii=False, indent=1)
            cur.execute("UPDATE product_assemblies SET data=%s, kolize_pocet=NULL, kolize_checked_at=NULL WHERE id=%s",
                        (json.dumps(d, ensure_ascii=False), AID))
        conn.commit()
finally:
    conn.close()
print("HOTOVO" if not DRY else "DRY-RUN HOTOVO")
