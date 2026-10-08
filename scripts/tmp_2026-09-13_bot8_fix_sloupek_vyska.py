"""Natahuje sloupek-pred-podbehem na vysku KRAJNICH (outer) nohou (predni-
svislice/cap) - Robert: "dorovnej jenom stredove nohy tech dvou sestav
podle krajnich, jdes nahoru ne dolu". Jen #134 (A) a #209 (B). Zadna
kolizni kontrola. Pridava zaslepku na novy volny konec."""
import json
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402

BACKUP = "/opt/konfigurator/backups/2026-09-13_sloupek_vyska_fix"
ZASLEPKA_PART_ID = "product_3071"
IDS = [374]


def top_of(part):
    return part["position"][1] + part.get("scale", [1, 1, 1])[1] * 500


def main():
    dry = "--dry-run" in sys.argv
    conn = get_conn()
    zaloha = {}
    zapsano = []
    try:
        with conn.cursor() as cur:
            for aid in IDS:
                cur.execute("SELECT id, name, data FROM product_assemblies WHERE id=%s", (aid,))
                row = cur.fetchone()
                d = json.loads(row["data"])
                parts = d["parts"]
                # krajni (outer) vyska = MAX top mezi vsemi predni-svislice/cap v cele sestave
                krajni_top = max(
                    top_of(p) for p in parts if p.get("role") in ("predni-svislice", "cap")
                )

                zmeny = 0
                nove_zaslepky = []
                for p in parts:
                    if p.get("role") != "sloupek-pred-podbehem":
                        continue
                    dolni = p["position"][1] - p.get("scale", [1, 1, 1])[1] * 500
                    if abs(top_of(p) - krajni_top) < 1:
                        continue
                    novy_stred = (dolni + krajni_top) / 2
                    novy_scale = (krajni_top - dolni) / 1000
                    p["position"][1] = novy_stred
                    if "scale" not in p or not p["scale"]:
                        p["scale"] = [1, 1, 1]
                    p["scale"][1] = novy_scale
                    zmeny += 1
                    nove_zaslepky.append({
                        "part_id": ZASLEPKA_PART_ID,
                        "position": [p["position"][0], krajni_top, p["position"][2]],
                        "quaternion": [0.7071067811865475, 0, 0, 0.7071067811865475],
                        "scale": [1, 1, 1],
                        "role": "zaslepka-sloupek-pred-podbehem",
                    })

                if zmeny == 0:
                    print(f"#{aid}: nic ke zmene (uz sedi na krajni_top={krajni_top})")
                    continue
                zaloha[str(aid)] = row
                parts.extend(nove_zaslepky)
                d["parts"] = parts
                d["bom"] = []
                d["price_summary"] = None
                if not dry:
                    cur.execute(
                        "UPDATE product_assemblies SET data=%s, kolize_pocet=NULL, kolize_checked_at=NULL WHERE id=%s",
                        (json.dumps(d, ensure_ascii=False), aid),
                    )
                zapsano.append(aid)
                print(f"{'BY SE ZAPSALO' if dry else 'ZAPSANO'}: #{aid} {row['name'][:50]} - "
                      f"{zmeny} sloupku natazeno na top={krajni_top}, {len(nove_zaslepky)} zaslepek pridano")

        if not dry:
            os.makedirs(BACKUP, exist_ok=True)
            with open(os.path.join(BACKUP, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=1, default=str)
            conn.commit()
            print(f"\nCOMMIT hotovy, {len(zapsano)} sestav upraveno. Zaloha: {BACKUP}/pred_zapisem.json")
        else:
            print(f"\nDRY-RUN: {len(zapsano)} sestav by se upravilo.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
