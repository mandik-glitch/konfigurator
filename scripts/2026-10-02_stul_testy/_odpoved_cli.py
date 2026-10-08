#!/usr/bin/env python3
"""Pomocny skript testu panelu (test_stul_panel.js): query string -> JSON odpoved API (bez Flasku a bez DB).
Pouziti: _odpoved_cli.py "sirka=2000&hloubka=800&police=1" ; chyba vstupu = {"__status":400,"error":...,"kod":...}."""
import json
import os
import sys
from urllib.parse import parse_qsl

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))
import stul_konfigurator as S  # noqa: E402

box_lo, box_hi = S.glb_bbox("product_4930")
if box_hi[1] - box_lo[1] > 1000:        # originalni model s vysunutym supliku -> zavreny kandidat
    S.BBOX_PREPIS["product_4930"] = ([-2279.2, -950.4, 627.4], [-1714.2, -367.3, 907.5])
try:
    args = dict(parse_qsl(sys.argv[1] if len(sys.argv) > 1 else ""))
    print(json.dumps(S.odpoved(S.parametry_z_dotazu(args))))
except S.StulChyba as e:
    print(json.dumps({"__status": 400, "error": str(e), "kod": e.kod}))
