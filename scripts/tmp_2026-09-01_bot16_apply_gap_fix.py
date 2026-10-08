#!/usr/bin/env python3
"""Applies the Y-shift gap fix (bot16, 2026-09-01) computed by
tmp_2026-09-01_bot16_gap_fix_compute.js to each product_assemblies row's
data.parts, and emits a single SQL file with UPDATE statements.

Does NOT touch the DB itself - a separate `mysql ... < out.sql` step does
that, after review of the emitted SQL / summary.
"""
import json
import sys

SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad"

plan = json.load(open(f"{SCRATCH}/gap_fix.json"))

sql_lines = []
summary = []

for row_plan in plan["rows"]:
    rid = row_plan["id"]
    data = json.load(open(f"{SCRATCH}/rows/{rid}.json"))
    parts = data["parts"]

    n_shifted_parts = 0
    n_levels_shifted = 0
    max_abs_delta = 0.0
    for col in row_plan["columns"]:
        for lv in col["levels"]:
            d = lv["delta"]
            if abs(d) < 1e-6:
                continue
            n_levels_shifted += 1
            max_abs_delta = max(max_abs_delta, abs(d))
            all_idx = lv["railIdx"] + lv["connIdx"] + lv["boxIdx"]
            for idx in all_idx:
                parts[idx]["position"][1] = round(parts[idx]["position"][1] + d, 4)
                n_shifted_parts += 1

    if n_levels_shifted == 0:
        continue  # nothing to do for this row (shouldn't happen - all 93 had violations)

    new_data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # SQL-escape for a single-quoted string literal: backslash and single quote
    escaped = new_data_json.replace("\\", "\\\\").replace("'", "\\'")
    sql_lines.append(f"UPDATE product_assemblies SET data='{escaped}' WHERE id={rid};")

    summary.append({
        "id": rid, "n_levels_shifted": n_levels_shifted,
        "n_parts_shifted": n_shifted_parts, "max_abs_delta": round(max_abs_delta, 2),
    })

with open(f"{SCRATCH}/gap_fix_updates.sql", "w") as f:
    f.write("\n".join(sql_lines) + "\n")

json.dump(summary, open(f"{SCRATCH}/gap_fix_summary.json", "w"), indent=1)

print(f"rows updated: {len(summary)}")
print(f"total SQL statements: {len(sql_lines)}")
total_levels = sum(s["n_levels_shifted"] for s in summary)
total_parts = sum(s["n_parts_shifted"] for s in summary)
print(f"total levels shifted: {total_levels}, total parts moved: {total_parts}")
