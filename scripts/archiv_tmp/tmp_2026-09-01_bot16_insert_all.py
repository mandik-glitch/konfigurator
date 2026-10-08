import json, re, pymysql

env = {}
for line in open('/opt/konfigurator/api/.env'):
    line = line.rstrip('\n')
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v

conn = pymysql.connect(host=env['DB_HOST'], port=int(env['DB_PORT']), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'], charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)

with open('/opt/konfigurator/scripts/tmp_2026-09-01_bot16_summary.json') as f:
    summary = json.load(f)

# key -> (car_short_name, car_body_ids [L,R_D,B], row_id)
VEHICLES = {
 "caddy_VW13": ("Caddy VW13", [834, 835, 836], 836),
 "caddy_VW14": ("Caddy Maxi VW14", [837, 838, 839], 839),
 "caddy_VW21": ("Caddy Cargo VW21", [840, 841, 842], 842),
 "caddy_VW22": ("Caddy Cargo Maxi VW22", [843, 844, 845], 845),
 "caddy_VW31": ("Caddy Cargo PHEV VW31", [846, 847, 848], 848),
 "caddy_VW32": ("Caddy Cargo Maxi PHEV VW32", [849, 850, 851], 851),
 "ford_FO12": ("Ford Connect FO12", [231, 232, 233], 233),
 "ford_FO13": ("Ford Connect FO13", [72, 73, 74], 74),
 "ford_FO36": ("Transit Connect L1 FO36", [234, 235, 236], 236),
 "ford_FO37": ("Transit Connect L2 FO37", [237, 238, 239], 239),
 "ford_FO45": ("Transit Connect PHEV L1 FO45", [240, 241, 242], 242),
 "ford_FO46": ("Transit Connect PHEV L2 FO46", [243, 244, 245], 245),
 "doblo_FI14": ("Doblo FI14", [15, 16, 17], 17),
 "doblo_FI15": ("Doblo Maxi FI15", [66, 67, 68], 68),
}

def height_signature(column_summaries):
    counts = {}
    for c in column_summaries:
        N = c["N"]
        for h in c["heights"]:
            counts[h] = counts.get(h, 0) + N
    heights_desc = sorted(counts.keys(), reverse=True)
    return "-".join(f"{h}x{counts[h]}" for h in heights_desc), counts


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


inserted = []
with conn.cursor() as cur:
    for key, (short_name, body_ids, row_id) in VEHICLES.items():
        s = summary.get(key)
        if not s or not s.get("ok"):
            print(f"SKIP {key}: not ok")
            continue
        with open(f"/opt/konfigurator/scripts/tmp_2026-09-01_bot16_rack_{key}.json") as f:
            rack_parts = json.load(f)
        with open("/opt/konfigurator/scripts/tmp_2026-09-01_bot16_column_summaries.json") as f:
            all_cs = json.load(f)
        column_summaries = all_cs[key]
        sig, counts = height_signature(column_summaries)
        name = f"{short_name} - boxy43-{sig}"

        car_body_parts = [
            {"part_id": f"car_body_{body_ids[0]}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
            {"part_id": f"car_body_{body_ids[1]}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
            {"part_id": f"car_body_{body_ids[2]}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
        ]
        all_parts = car_body_parts + rack_parts
        payload = {
            "parts": all_parts,
            "join_groups": [],
            "frame_groups": [],
            "bom": [],
            "price_summary": {},
            "_note": (
                f"bot16 2026-09-01, davka Caddy/Ford Connect/Doblo. Karoserie car_bodies id={row_id} "
                f"(L={body_ids[0]}/R_D={body_ids[1]}/B={body_ids[2]}), profil 30x30 (Object_7, prevod ze "
                f"stavajicich 40x40 katalogovych noh metodou shape_geometry_methods.id=1), hloubka D=349mm. "
                f"Karoserie fyzicky otocena o 180 (viz orientacni audit + backups/2026-08-31_car_body_"
                f"caddy_connect_doblo_180_flip/) - stena L na zaporne strane X, pouzita MIRROR konvence "
                f"worldX = offsetX - localX (car_body_placement_methods.id=1, mirror_x_pro_stenu_na_"
                f"zaporne_strane_2026_08_31). Kolizni krokovani (id=1) + hladove sloupcove plneni (id=5) + "
                f"protazeni vyrezove nohy fresh pro tohle konkretni auto (id=6, pokud noha vyrez existuje) + "
                f"rail-floor kontrola pres cely rozpon sloupce (id=6 korekce) + strop kontrola celou hloubkou "
                f"D (CI25 nalez) + vyska pater dle id=3 (alespon 3 ze 4 vysek 120/170/220/270mm kdekoli v "
                f"cele sestave, kde to geometrie dovolila). Overeno: bez kolize s karoserii (profily i "
                f"euroboxy), 0 neocekavane self-kolize. Sloupce: {json.dumps(column_summaries, ensure_ascii=False)}."
            ),
        }
        sku = generate_sku(cur, name)
        cur.execute("INSERT INTO shop_products (sku, name, unit, active) VALUES (%s,%s,%s,0)", (sku, name, "ks"))
        shop_product_id = cur.lastrowid
        cur.execute(
            "INSERT INTO product_assemblies (name, category_id, data, created_by, is_public, shop_product_id) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (name, None, json.dumps(payload, ensure_ascii=False), None, 1, shop_product_id),
        )
        new_id = cur.lastrowid
        inserted.append({"key": key, "product_assemblies_id": new_id, "shop_product_id": shop_product_id, "sku": sku, "name": name, "car_body_id": row_id})
        print(f"{key}: product_assemblies.id={new_id} shop_product_id={shop_product_id} sku={sku} name='{name}'")

conn.commit()
conn.close()
with open("/opt/konfigurator/scripts/tmp_2026-09-01_bot16_inserted.json", "w") as f:
    json.dump(inserted, f, indent=1, ensure_ascii=False)
print("\nTOTAL INSERTED:", len(inserted))
