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


def insert_rack(full_path, name, note, car_body_ids):
    full = json.load(open(full_path))
    if not full["ok"]:
        raise SystemExit(f"REFUSING insert - full build not ok: {full_path}")
    l_id, r_id, b_id = car_body_ids
    car_body_parts = [
        {"part_id": f"car_body_{l_id}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
        {"part_id": f"car_body_{r_id}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
        {"part_id": f"car_body_{b_id}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
    ]
    all_parts = car_body_parts + full["parts"]
    payload = {
        "parts": all_parts, "join_groups": [], "frame_groups": [], "bom": [], "price_summary": {},
        "_note": note,
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
    print(f"product_assemblies.id={new_id} shop_product_id={shop_product_id} sku={sku} name={name} dily={len(all_parts)}")
    return new_id


if __name__ == "__main__":
    full_path, name, note, l_id, r_id, b_id = sys.argv[1:7]
    insert_rack(full_path, name, note, (int(l_id), int(r_id), int(b_id)))
