#!/usr/bin/env python3
"""Prida dorazovou desku (vypln-bok-prepazka) do 6 Jumpy sestav (K-118/
K-119), ktere pouzivaji obecnou horni_blok_varianty kod="02" (id=3) -
Robert 2026-09-14: dorazova deska ma byt UNIVERZALNI standard pro
"jedno pasmo ram+dna", ne jen Doblo-K-075-specificky. Pravidlo (odvozeno
z realne GLB geometrie Doblo 369, jediny uz overeny/schvaleny pripad):
  - spodni hrana desky = realny vrchol pricka-spodni-0 (7mm zasun)
  - horni hrana desky = realny spodek zaslepky na noze u prepazky
    minus 11mm bezpecnostni mezera (presne zmereno na Doblo 369:
    zaslepka spodek 1208.0, deska vrch 1197.0)
Sirka desky = mezera mezi predni-svislice a cap (stejny 233mm-styl
vzorec jako Doblo: sirka = |cap.x - predni_svislice.x| - 2*8mm zasun).
"""
import json
import subprocess
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn

IDS = [348, 349, 350, 351, 353, 354]
SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad"


def najdi_prepazkovou_nohu(parts):
    pricka = next(p for p in parts if p.get("role") == "pricka-spodni-0")
    z = pricka["position"][2]
    at_z = [p for p in parts if abs(p["position"][2] - z) < 1 and not (p.get("part_id") or "").startswith("car_body")]
    predni = next(p for p in at_z if p.get("role") == "predni-svislice")
    cap = next(p for p in at_z if p.get("role") == "cap")
    zaslepky = [p for p in at_z if p.get("part_id") == "product_3071"]
    # zaslepka na predni-svislice/cap = ta s nejvyssim Y (na vrcholu nohy);
    # zadni-svislice-dolni ma svoji zaslepku niz (jina noha/uroven)
    zaslepky_top = sorted(zaslepky, key=lambda p: -p["position"][1])[:2]
    return pricka, predni, cap, zaslepky_top


def main():
    fetched = {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for aid in IDS:
                cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (aid,))
                row = cur.fetchone()
                d = json.loads(row["data"])
                fetched[aid] = {"name": row["name"], "parts": d["parts"], "count": len(d["parts"])}
    finally:
        conn.close()

    with open(f"{SCRATCH}/jumpy_raw.json", "w") as f:
        json.dump(fetched, f)
    print("nacteno", len(fetched), "sestav")
    for aid, info in fetched.items():
        print(" ", aid, info["name"][:55], info["count"], "dilu")


if __name__ == "__main__":
    main()
