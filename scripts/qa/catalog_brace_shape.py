#!/usr/bin/env python3
"""QA: geometrie vzpery 45 st. vkladane z katalogu Sceny (viz catalog_brace_shape.js) na SKUTECNYCH sitich dilu: pro delky 100..1000 mm a systemy 30/40 spojky lezi svym celem
na koncich profilu (zasunuti 1-2 mm), jsou souose, B je zrcadlo A pres stred profilu (do 1 mm), rozsah v x/y je stejny a tvar neprekroci obalku profilu bokem.
Pouziti: api/venv/bin/python3 scripts/qa/catalog_brace_shape.py [--json]   Exit: 0 ok, 2 chyba"""
import json
import os
import subprocess
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_glb as G  # noqa: E402

t0 = time.time()
findings, ok = [], 0


def check(cond, code, title, detail=""):
    global ok
    if cond:
        ok += 1
    else:
        findings.append({"severity": "critical", "code": code, "title": title, "detail": str(detail), "where": "webapp/js/scene/catalog-panels.js (BRACE_DEFS)", "fix_hint": "polohy dilu musi odpovidat overene geometrii vzpery (tvary #178, #580)"})


raw = subprocess.run(["node", os.path.join(REPO, "scripts", "qa", "catalog_brace_shape.js")], capture_output=True, text=True, timeout=60)
data = json.loads(raw.stdout) if raw.stdout.strip() else {"error": raw.stderr[:200]}
check("error" not in data, "BRACE_NODE", "node skript nevypsal tvary", data.get("error"))
if "error" not in data:
    check(data["min"] == 100 and data["max"] == 1000, "BRACE_RANGE", "rozsah delky vzpery neni 100-1000 mm", f"{data['min']}-{data['max']}")
    check(all(x["shape"] is None for x in data["rejected"]) and data["badSys"] is None, "BRACE_VALIDATION", "neplatna delka (0, 99, 1001, NaN, 5000) nebo system se prijal")
    for it in data["shapes"]:
        sh, L, sys_ = it["shape"], it["L"], it["sys"]
        n = f"system {sys_}, delka {L} mm"
        check(sh and len(sh["parts"]) == 3, "BRACE_PARTS", f"{n}: tvar nema 3 dily")
        if not sh:
            continue
        prof, a, b = sh["parts"]
        check(abs(prof["scale"][1] - L / 1000.0) < 1e-9, "BRACE_LEN", f"{n}: delka profilu neodpovida", prof["scale"])
        P = [G._transformuj(d["part_id"], d)[0] for d in (prof, a, b)]
        lp, hp = P[0].min(axis=0), P[0].max(axis=0)
        la, ha, lb, hb = P[1].min(axis=0), P[1].max(axis=0), P[2].min(axis=0), P[2].max(axis=0)
        check(abs((hp[2] - lp[2]) - L) < 0.5, "BRACE_PROFILE_LEN", f"{n}: profil nema delku L", hp[2] - lp[2])
        zas_a, zas_b = ha[2] - lp[2], hp[2] - lb[2]
        check(0.5 < zas_a < 3.0 and abs(zas_a - zas_b) < 0.01, "BRACE_INSERT", f"{n}: zasunuti spojek do profilu {zas_a:.2f}/{zas_b:.2f} mm (ocekavam 1-2.5 mm, shodne)")
        check(np.abs((hb - lb) - (ha - la)).max() < 0.01 and abs(la[0] - lb[0]) < 0.01 and abs(la[1] - lb[1]) < 0.01, "BRACE_SAME_EXTENT", f"{n}: spojky nemaji stejny rozsah v x/y")
        check(la[0] >= lp[0] - 0.05 and ha[0] <= hp[0] + 0.05, "BRACE_WITHIN_SECTION", f"{n}: spojka presahuje bocni steny profilu", (la[0], ha[0], lp[0], hp[0]))
        odraz = P[1] * np.array([1.0, 1.0, -1.0])
        dm = np.sqrt(((odraz[:, None, :] - P[2][None, :, :]) ** 2).sum(axis=2))
        check(max(dm.min(axis=1).max(), dm.min(axis=0).max()) < 1.0, "BRACE_MIRROR", f"{n}: spojka B neni zrcadlo spojky A (do 1 mm)")
        check(abs((hb[2] + la[2])) < 0.01 or abs(((hb[2] - hp[2]) - (lp[2] - la[2]))) < 0.01, "BRACE_SYMMETRIC", f"{n}: tvar neni symetricky podle stredu profilu")
status = "fail" if findings else "ok"
if "--json" in sys.argv:
    print(json.dumps({"suite": "catalog_brace_shape", "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "duration_s": round(time.time() - t0, 2), "status": status, "findings": findings, "stats": {"checks_ok": ok}}))
else:
    for f in findings:
        print("CHYBA", f["code"], "-", f["title"], f["detail"])
    print(f"{len(findings)} CHYB, {ok} kontrol OK" if findings else f"{ok} kontrol OK")
sys.exit(2 if findings else 0)
