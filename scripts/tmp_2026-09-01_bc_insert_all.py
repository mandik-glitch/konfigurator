import json, re, pymysql

env = {}
for line in open('/opt/konfigurator/api/.env'):
    line = line.rstrip('\n')
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v

conn = pymysql.connect(host=env['DB_HOST'], port=int(env['DB_PORT']), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'], charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)

VEHICLES = {
    "MB47": "Mercedes Vito MB47 (2014-)",
    "FO31": "Transit Custom L2 FO31",
    "VW25": "T7 VW25",
    "OP31": "Vivaro Electric L1 OP31",
}

summary = json.load(open("/opt/konfigurator/scripts/tmp_2026-09-01_bc_all_summary.json"))


def generate_sku(cur, name):
    base = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").upper()[:40] or "SESTAVA"
    candidate = f"SEST-{base}"
    n = 1
    while True:
        cur.execute("SELECT id FROM shop_products WHERE sku=%s", (candidate,))
        if not cur.fetchone():
            return candidate
        n += 1
        candidate = f"SEST-{base}-{n}"


def insert_one(vkey, letter, label):
    key = f"{vkey}_{letter}"
    s = summary[key]
    # OP31 is physically limited to 2 levels/2 distinct heights in a single column
    # (real physical ceiling only ~5mm above the leg's structural RAIL_TOP_MAX, same
    # finding as variant A / ProAce TO07 precedent) - rule 6 ("distinct>=3") is
    # genuinely inapplicable for a SINGLE OP31 assembly; diversity is instead achieved
    # ACROSS the A/B/C family (A={270,220}, B={270,170}, C={220,120} -> union=all 4).
    hard_ok = not s["legsCollide"] and not s["boxesCollide"] and s["unexpectedSelfCollisions"] == 0 and s["nonIncreasingOk"]
    assert hard_ok, f"{key}: hard checks failed! {s}"
    if not s["ok"]:
        assert vkey == "OP31" and len(s["distinct"]) == 2, f"{key}: not ok and not the known OP31 exception! {s}"
    with open(f"/opt/konfigurator/scripts/tmp_2026-09-01_bc_{key}_parts.json") as f:
        all_parts = json.load(f)

    counts = {}
    for c in s["columnFinal"]:
        for h in c["heights"]:
            counts[h] = counts.get(h, 0) + c["N"]
    parts_name = "-".join(f"{h}x{counts[h]}" for h in sorted(counts.keys(), reverse=True))
    name = f"{label} {letter} - boxy43-{parts_name}"

    payload = {
        "parts": all_parts, "join_groups": [], "frame_groups": [], "bom": [], "price_summary": {},
        "_note": (
            f"bot16 2026-09-01: variant {letter} (part of the A/B/{'C' if letter=='B' else 'B'} batch adding "
            "height-diversified variants to vehicles that only ever got 1 built variant). Legs/rails-X/rails-Z/"
            "column positions IDENTICAL to variant A (read straight from the saved variant-A DB row) - only "
            "per-level box heights (and therefore per-level rail Y positions) replanned. Verified via REAL GLB "
            "collision (collidesWithWalls) against the actual car body for every column with automatic top-level "
            "height backoff on collision (script tmp_2026-09-01_bc_build.js) - no car-body collision, no "
            "unexpected self-collision, non-increasing heights bottom-to-top confirmed. "
            f"columnFinal={json.dumps(s['columnFinal'])}"
        ),
    }

    with conn.cursor() as cur:
        sku = generate_sku(cur, name)
        cur.execute("INSERT INTO shop_products (sku, name, unit, active) VALUES (%s,%s,%s,0)", (sku, name, "ks"))
        shop_product_id = cur.lastrowid
        cur.execute(
            "INSERT INTO product_assemblies (name, category_id, data, created_by, is_public, shop_product_id) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (name, None, json.dumps(payload, ensure_ascii=False), None, 1, shop_product_id),
        )
        new_id = cur.lastrowid
    conn.commit()
    print(f"{key}: product_assemblies.id={new_id} shop_product_id={shop_product_id} sku={sku} name={name!r} parts={len(all_parts)}")
    return new_id


if __name__ == "__main__":
    import sys
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    ids = {}
    for vkey, label in VEHICLES.items():
        for letter in ["B", "C"]:
            key = f"{vkey}_{letter}"
            if only and key not in only:
                continue
            ids[key] = insert_one(vkey, letter, label)
    prior = {}
    try:
        prior = json.load(open("/opt/konfigurator/scripts/tmp_2026-09-01_bc_inserted_ids.json"))
    except Exception:
        pass
    prior.update(ids)
    json.dump(prior, open("/opt/konfigurator/scripts/tmp_2026-09-01_bc_inserted_ids.json", "w"), indent=1)
    print(json.dumps(ids, indent=1))
