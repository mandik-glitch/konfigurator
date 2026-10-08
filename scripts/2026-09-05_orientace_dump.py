#!/usr/bin/env python3
"""Dump karoserii z DB pro cerstvy audit orientace (Node nema pristup k MySQL).

Vystup: /tmp/orient_car_bodies_dump.tsv, radek = <car_bodies.id>\\t<glb_file>\\t<model_name>

bot8 2026-09-05. Read-only.
"""
import os
import sys

sys.path.insert(0, "/opt/konfigurator/api")
os.chdir("/opt/konfigurator/api")
for _l in open(".env"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
import app as A  # noqa: E402

OUT = "/tmp/orient_car_bodies_dump.tsv"

conn = A.get_conn()
cur = conn.cursor()
cur.execute("""
    SELECT cb.id, cb.glb_file, cm.name AS model_name
    FROM car_bodies cb
    JOIN car_models cm ON cm.id = cb.model_id
    WHERE cb.glb_file IS NOT NULL
    ORDER BY cb.glb_file
""")
rows = cur.fetchall()
with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        model = (r["model_name"] or "").replace("\t", " ").replace("\n", " ")
        f.write(f"{r['id']}\t{r['glb_file']}\t{model}\n")
print(f"Zapsano {len(rows)} karoserii -> {OUT}")
