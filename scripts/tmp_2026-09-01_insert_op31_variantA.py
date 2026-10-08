import json, re, sys, pymysql

env = {}
for line in open('/opt/konfigurator/api/.env'):
    line = line.rstrip('\n')
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v

conn = pymysql.connect(host=env['DB_HOST'], port=int(env['DB_PORT']), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'], charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)


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


def insert_one(parts_path, car_body_B_id, label, note_extra):
    with open(parts_path) as f:
        rack_parts = json.load(f)
    summary = json.load(open("/opt/konfigurator/scripts/tmp_2026-09-01_op31_variantA_result.json"))
    col_summaries = summary["columnSummaries"]

    counts = {}
    for c in col_summaries:
        for h in c["boxHeights"]:
            counts[h] = counts.get(h, 0) + c["N"]
    parts_name = "-".join(f"{h}x{counts[h]}" for h in sorted(counts.keys(), reverse=True))
    name = f"{label} - boxy43-{parts_name}"

    L_id, RD_id, B_id = car_body_B_id - 2, car_body_B_id - 1, car_body_B_id
    car_body_parts = [
        {"part_id": f"car_body_{B_id}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
        {"part_id": f"car_body_{L_id}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
        {"part_id": f"car_body_{RD_id}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
    ]
    all_parts = car_body_parts + rack_parts

    payload = {
        "parts": all_parts, "join_groups": [], "frame_groups": [], "bom": [], "price_summary": {},
        "_note": note_extra,
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
    print(f"product_assemblies.id={new_id} shop_product_id={shop_product_id} sku={sku} name={name!r} parts={len(all_parts)}")
    return new_id


if __name__ == "__main__":
    insert_one(
        "/opt/konfigurator/scripts/tmp_2026-08-31_batch_OP31_parts.json",
        662,
        "Vivaro Electric L1 OP31",
        "bot16 2026-09-01: variant A, built from scratch (never built before, only OP18 pilot existed). "
        "Same shared leg design as OP18/Jumpy/Expert/ProAce/Custom/Transporter family (D=326,T=30,H=1180,"
        "CAP_H=260,CUTOUT_H=395). Independently measured OP31's own real GLB (zMidB=+1943.2 positive -> "
        "NEEDS_FLIP, physically 180-flipped, backup in backups/2026-09-01_car_body_vivaro_op31_180_flip/; "
        "after flip L wall on negative X -> mirror=true confirmed by engine auto-detect). Only 2 legs / 1 "
        "column fit (maxSpan=1620mm too short for a 2nd column after N=3 width column). Vyrez leg Y_new=313mm "
        "(unusually high cutout clearance vs OP18's 213/139mm - plausible battery-pack floor raise on this "
        "electric variant per task hypothesis) -> column floor=313mm, physical ceiling=927mm -> only 2 "
        "distinct heights (270+220) fit in the 614mm available; verified genuinely max-3-heights-infeasible "
        "here (3 smallest heights + overhead always exceed budget regardless of order), same category as "
        "ProAce TO07 precedent (rule 6 inapplicable, not violated). Door-height 1220mm > leg H=1180mm, no "
        "truncation needed.",
    )
