#!/usr/bin/env python3
"""Zapise dopocitany joint_count/joint_czk do product_assemblies.data.
price_summary (bot10, zadani bot8 2026-09-11). MENI JEN joint_czk,
joint_count, total_czk + odstranuje joint_price_odhad_chybi_czk a
backfill_note - na 'parts'/'bom'/zbytek price_summary NESAHA.

Vstup: /tmp/.../scratchpad/batch_joint_results.json (id -> {jointCount,...})
       + zive nacte aktualni data z DB pro presne tyhle IDs.

Pouziti:
    python3 scripts/2026-09-11_joint_count_batch_apply.py            # jen report
    python3 scripts/2026-09-11_joint_count_batch_apply.py --apply    # + zapise + zaloha
"""
import argparse
import json
import os
import sys
from datetime import datetime

import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOINT_PRICE_CZK = 110
RESULTS_PATH = "/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/batch_joint_results.json"


def load_env():
    env = {}
    with open(os.path.join(ROOT, "api", ".env")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v
    return env


def get_conn():
    env = load_env()
    return pymysql.connect(
        host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
        password=env["DB_PASSWORD"], database=env["DB_NAME"], charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    results = json.load(open(RESULTS_PATH))
    ids = [int(k) for k in results.keys()]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, name, data FROM product_assemblies WHERE id IN ({','.join(['%s']*len(ids))})", ids)
            rows = {r["id"]: r for r in cur.fetchall()}
    finally:
        conn.close()

    print(f"Nacteno {len(rows)} sestav (ocekavano {len(ids)})")
    missing_ids = set(ids) - set(rows.keys())
    if missing_ids:
        print(f"POZOR: nenalezeny v DB: {missing_ids}")

    changes = []
    big_change_count = 0
    for aid, row in rows.items():
        r = results[str(aid)]
        d = json.loads(row["data"])
        ps = d.get("price_summary") or {}
        old_total = ps.get("total_czk", 0)
        old_joint_czk = ps.get("joint_czk", 0)

        joint_count = r["jointCount"]
        joint_czk = joint_count * JOINT_PRICE_CZK
        new_total = old_total - old_joint_czk + joint_czk

        ps["joint_count"] = joint_count
        ps["joint_czk"] = joint_czk
        ps["total_czk"] = new_total
        had_note = "backfill_note" in ps or "joint_price_odhad_chybi_czk" in ps
        ps.pop("joint_price_odhad_chybi_czk", None)
        ps.pop("backfill_note", None)
        d["price_summary"] = ps

        pct_change = abs(new_total - old_total) / old_total * 100 if old_total else 0
        if pct_change > 30:
            big_change_count += 1

        changes.append({
            "id": aid, "name": row["name"], "data": d,
            "old_total": old_total, "new_total": new_total, "joint_count": joint_count,
            "joint_czk": joint_czk, "had_note": had_note, "pct_change": round(pct_change, 1),
        })

    print(f"\nUkazka (prvnich 5):")
    for c in changes[:5]:
        print(f"  id={c['id']} joint_count={c['joint_count']} joint_czk={c['joint_czk']} "
              f"total {c['old_total']}->{c['new_total']} ({c['pct_change']}%) note_removed={c['had_note']}")

    print(f"\nCelkem ke zmene: {len(changes)}")
    print(f"Sestav se zmenou total_czk > 30%: {big_change_count}")

    if not args.apply:
        print("\n(jen report - spust s --apply pro zapis do DB)")
        return

    backup_dir = os.path.join(ROOT, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    # POZOR (nalezeno 2026-09-11 pri druhem behu tehoz dne): nazev bez
    # rozlisovaciho suffixu prepise zalohu predchoziho behu ze STEJNEHO
    # dne beze stopy - proto id-rozsah v nazvu.
    id_range = f"{min(c['id'] for c in changes)}-{max(c['id'] for c in changes)}_n{len(changes)}"
    backup_path = os.path.join(backup_dir, f"{datetime.now():%Y-%m-%d}_joint_count_batch_before_{id_range}.json")
    backup_payload = {aid: json.loads(row["data"]) for aid, row in rows.items()}
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup_payload, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nZaloha PUVODNIHO stavu (255 sestav): {backup_path}")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for c in changes:
                cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s", (json.dumps(c["data"], ensure_ascii=False), c["id"]))
        conn.commit()
    finally:
        conn.close()

    print(f"Hotovo - zapsano {len(changes)} sestav.")


if __name__ == "__main__":
    main()
