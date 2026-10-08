import json
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402

SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad"
BACKUP = "/opt/konfigurator/backups/2026-09-13_horni_blok_fix_379"
AID = 379

vysl = json.load(open(os.path.join(SCRATCH, "fix_379_output.json")))
assert len(vysl["kolize"]) == 0, "kolize nejsou 0!"

conn = get_conn()
try:
    with conn.cursor() as cur:
        os.makedirs(BACKUP, exist_ok=True)
        cur.execute("SELECT * FROM product_assemblies WHERE id=%s", (AID,))
        row = cur.fetchone()
        with open(os.path.join(BACKUP, "pred_zapisem.json"), "w", encoding="utf-8") as f:
            json.dump(row, f, ensure_ascii=False, indent=1, default=str)
        d = json.loads(row["data"])
        print(f"puvodne {len(d['parts'])} dilu -> {len(vysl['parts'])} dilu")
        d["parts"] = vysl["parts"]
        d["bom"] = []
        d["price_summary"] = None
        cur.execute(
            "UPDATE product_assemblies SET data=%s, kolize_pocet=NULL, kolize_checked_at=NULL WHERE id=%s",
            (json.dumps(d, ensure_ascii=False), AID),
        )
    conn.commit()
    print("COMMIT hotovy.")
finally:
    conn.close()

conn2 = get_conn()
try:
    with conn2.cursor() as cur:
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (AID,))
        d2 = json.loads(cur.fetchone()["data"])
        print(f"OVERENO: {len(d2['parts'])} dilu v DB")
finally:
    conn2.close()
