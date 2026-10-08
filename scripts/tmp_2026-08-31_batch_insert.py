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


def insert_one(key, car_body_id, label, note_extra):
    with open(f"/opt/konfigurator/scripts/tmp_2026-08-31_batch_{key}_parts.json") as f:
        rack_parts = json.load(f)
    with open("/opt/konfigurator/scripts/tmp_2026-08-31_batch_results.json") as f:
        results = json.load(f)
    summary = results[key]["summary"]
    col_summaries = summary["columnSummaries"]

    # agregace poctu boxu podle vysky napric celou sestavou (boxy43-H1xN1-H2xN2...)
    counts = {}
    for c in col_summaries:
        for h in c["boxHeights"]:
            counts[h] = counts.get(h, 0) + 1
    parts_name = "-".join(f"{h}x{counts[h]}" for h in sorted(counts.keys(), reverse=True))
    name = f"{label} - boxy43-{parts_name}"

    L_id, RD_id, B_id = car_body_id - 2, car_body_id - 1, car_body_id
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
    print(f"{key}: product_assemblies.id={new_id} shop_product_id={shop_product_id} sku={sku} name={name!r} parts={len(all_parts)}")
    return new_id


if __name__ == "__main__":
    # argv: key carBodyId label note
    key, car_body_id, label = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    note = sys.argv[4] if len(sys.argv) > 4 else ""
    insert_one(key, car_body_id, label, note)
