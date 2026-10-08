"""Zapise lic_peers/joint_count/hidden_end_conn/used_conn do sestavy 346
(product_assemblies.data.parts) podle vystupu
scripts/tmp_2026-09-13_bot8_joint_verify_346.js --apply.

Zaloha JIZ existuje: backups/2026-09-13_joint_verify_346/pred_zapisem.json
(zapsana pred timhle skriptem, primy SELECT z DB pred zmenou).

Meni JEN ctyri klice na kazdem dilu (lic_peers/joint_count/hidden_end_conn/
used_conn) - na position/quaternion/scale/part_id/role NESAHA.
"""
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402

WRITE_PATH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad/joint_write_346.json"
ASSEMBLY_ID = 346

payload = json.load(open(WRITE_PATH))  # {"idx": {lic_peers, joint_count, hidden_end_conn, used_conn}}

conn = get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (ASSEMBLY_ID,))
    row = cur.fetchone()
    data = json.loads(row["data"])
    parts = data["parts"]

    touched = 0
    for idx_str, v in payload.items():
        idx = int(idx_str)
        p = parts[idx]
        p["lic_peers"] = v["lic_peers"]
        p["joint_count"] = v["joint_count"]
        if v["hidden_end_conn"]:
            p["hidden_end_conn"] = v["hidden_end_conn"]
        if v["used_conn"]:
            p["used_conn"] = v["used_conn"]
        touched += 1

    total_jc = sum((p.get("joint_count") or 0) for p in parts)
    print(f"Upraveno dilu: {touched}, soucet joint_count po zapisu: {total_jc}")

    data["parts"] = parts
    cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                (json.dumps(data, ensure_ascii=False), ASSEMBLY_ID))
    conn.commit()
print("Zapsano do DB (id=346).")
conn.close()
