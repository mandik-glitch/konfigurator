"""Zapise vysledek chirurgicke opravy horniho pasma (viz
tmp_2026-09-13_bot8_splice_horni_blok_a.js) pro Doblo K-075 verze A
(381,382,383) - nahrazuje jen data.parts, zbytek data (join_groups/
frame_groups) necha byt, bom/price_summary vynuluje (geometrie se
zmenila, dopocita backfill skript). Zaloha PRED zapisem.
"""
import json
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402

SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad"
BACKUP = "/opt/konfigurator/backups/2026-09-13_horni_blok_splice_a"

splice = json.load(open(os.path.join(SCRATCH, "splice_a_output.json")))
DRY = "--dry-run" in sys.argv

conn = get_conn()
try:
    with conn.cursor() as cur:
        os.makedirs(BACKUP, exist_ok=True)
        zaloha = {}
        for aid_str in splice:
            aid = int(aid_str)
            cur.execute("SELECT * FROM product_assemblies WHERE id=%s", (aid,))
            row = cur.fetchone()
            zaloha[aid_str] = row
        with open(os.path.join(BACKUP, "pred_zapisem.json"), "w", encoding="utf-8") as f:
            json.dump(zaloha, f, ensure_ascii=False, indent=1, default=str)
        print(f"Zaloha: {BACKUP}/pred_zapisem.json ({len(zaloha)} sestav)")

        for aid_str, vysl in splice.items():
            aid = int(aid_str)
            d = json.loads(zaloha[aid_str]["data"])
            d["parts"] = vysl["parts"]
            d["bom"] = []
            d["price_summary"] = None
            if not DRY:
                cur.execute(
                    "UPDATE product_assemblies SET data=%s, kolize_pocet=NULL, kolize_checked_at=NULL WHERE id=%s",
                    (json.dumps(d, ensure_ascii=False), aid),
                )
            print(f"{'BY SE ZAPSALO' if DRY else 'ZAPSANO'}: #{aid} - {len(d['parts'])} dilu"
                  f" (puvodne {len(json.loads(zaloha[aid_str]['data'])['parts'])})")
    if not DRY:
        conn.commit()
        print("\nCOMMIT hotovy.")
    else:
        print("\nDRY-RUN, nic nezapsano.")
finally:
    conn.close()

if not DRY:
    conn2 = get_conn()
    try:
        with conn2.cursor() as cur:
            for aid_str in splice:
                cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (int(aid_str),))
                d2 = json.loads(cur.fetchone()["data"])
                print(f"OVERENO #{aid_str}: {len(d2['parts'])} dilu v DB")
    finally:
        conn2.close()
