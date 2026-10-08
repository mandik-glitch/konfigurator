#!/usr/bin/env python3
"""Oprava 16 nazvu nalezenych auditem 'nezarazenych' sestav 2026-09-14 -
nazev prepocitan PRIMO z data.parts (skutecny pocet euroboxu podle vysky),
ne rucne prepsany. K-122 (182/363) opravena stejnym vzorem jako K-123e
(189/372) dnes drive - "+ horni blok" odstranen, nahrazen pravdivym
popisem (zadny takovy dil v datech neni)."""
import json
import re
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn

HEIGHT_BY_SKU = {"product_3788": 120, "product_3793": 170, "product_3794": 220, "product_3795": 270}

BOX_COUNT_IDS = [109, 110, 125, 126, 143, 144, 148, 158, 165, 166, 169, 170, 210, 280]
HORNI_BLOK_IDS = [182, 363]


def box_composition(parts):
    counts = {}
    for p in parts:
        role = p.get("role") or ""
        if not role.startswith("eurobox"):
            continue
        h = HEIGHT_BY_SKU.get(p.get("part_id"))
        if h is None:
            continue
        counts[h] = counts.get(h, 0) + 1
    return counts


def rebuild_box_name(name, counts):
    m = re.match(r"^(.*boxy43-)([\dx\-]+)(.*)$", name)
    if not m:
        return None, "vzor 'boxy43-...' v nazvu nenalezen"
    prefix, _old, suffix = m.groups()
    segment = "-".join(f"{h}x{n}" for h, n in sorted(counts.items(), key=lambda kv: -kv[0]))
    return f"{prefix}{segment}{suffix}", None


conn = get_conn()
try:
    with conn.cursor() as cur:
        print("=== BOX-COUNT OPRAVY ===")
        for aid in BOX_COUNT_IDS:
            cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (aid,))
            row = cur.fetchone()
            d = json.loads(row["data"])
            counts = box_composition(d["parts"])
            new_name, err = rebuild_box_name(row["name"], counts)
            if err:
                print(f"id={aid}: CHYBA - {err} (nazev: {row['name']})")
                continue
            if new_name == row["name"]:
                print(f"id={aid}: uz spravny, beze zmeny")
                continue
            cur.execute("UPDATE product_assemblies SET name=%s WHERE id=%s", (new_name, aid))
            print(f"id={aid}:\n   stary: {row['name']}\n   novy:  {new_name}")

        print("\n=== '+ HORNI BLOK' OPRAVY (K-122) ===")
        for aid in HORNI_BLOK_IDS:
            cur.execute("SELECT name FROM product_assemblies WHERE id=%s", (aid,))
            row = cur.fetchone()
            old = row["name"]
            new = old.replace(
                " + horní blok",
                " (horní blok zatím nepostaven, plánováno pro dlouhé předměty)",
            )
            if new == old:
                print(f"id={aid}: vzor '+ horní blok' nenalezen, preskakuji ({old})")
                continue
            cur.execute("UPDATE product_assemblies SET name=%s WHERE id=%s", (new, aid))
            print(f"id={aid}:\n   stary: {old}\n   novy:  {new}")
    conn.commit()
finally:
    conn.close()
print("\nCOMMIT OK")
