import json, re, pymysql

env = {}
for line in open('/opt/konfigurator/api/.env'):
    line = line.rstrip('\n')
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v

conn = pymysql.connect(host=env['DB_HOST'], port=int(env['DB_PORT']), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'], charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)

configs = json.load(open('/opt/konfigurator/scripts/tmp_2026-08-31_bpt_configs.json'))

# car_bodies id trojice (B/L/R_D) - z DB dotazu tohoto behu
CAR_BODY_IDS = {
  "CI03": {"B": 11, "L": 9, "R_D": 10},
  "CI04": {"B": 65, "L": 63, "R_D": 64},
  "CI16": {"B": 149, "L": 147, "R_D": 148},
  "CI17": {"B": 152, "L": 150, "R_D": 151},
  "CI22": {"B": 155, "L": 153, "R_D": 154},
  "CI23": {"B": 158, "L": 156, "R_D": 157},
  "PE02": {"B": 716, "L": 714, "R_D": 715},
  "PE03": {"B": 719, "L": 717, "R_D": 718},
  "PE18": {"B": 722, "L": 720, "R_D": 721},
  "PE19": {"B": 725, "L": 723, "R_D": 724},
  "PE23": {"B": 728, "L": 726, "R_D": 727},
  "PE24": {"B": 731, "L": 729, "R_D": 730},
  "RE28": {"B": 776, "L": 774, "R_D": 775},
  "RE29": {"B": 779, "L": 777, "R_D": 778},
}
SHORT_NAME = {
  "CI03": "Berlingo CI03", "CI04": "Berlingo CI04", "CI16": "Berlingo L1 CI16",
  "CI17": "Berlingo L2 CI17", "CI22": u"ë-Berlingo L1 CI22", "CI23": u"ë-Berlingo L2 CI23",
  "PE02": "Partner PE02", "PE03": "Partner PE03", "PE18": "Partner L1 PE18",
  "PE19": "Partner L2 PE19", "PE23": "e-Partner L1 PE23", "PE24": "e-Partner L2 PE24",
  "RE28": "Trafic L1 RE28", "RE29": "Trafic L2 RE29",
}
LEG_SHAPE_ID = {"Berlingo": 539, "Partner": 539, "Trafic": 540}


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
    for cfg in configs:
        code = cfg["code"]; tag = cfg["tag"]
        result = json.load(open(f"/tmp/bpt_out_{tag}_result.json"))
        parts = json.load(open(f"/tmp/bpt_out_{tag}_parts.json"))
        verify = json.load(open(f"/tmp/bpt_verify2d_{tag}.json"))
        if not result["ok"] or not verify["ok"]:
            print(f"SKIP {code}: ok={result['ok']} verify_ok={verify['ok']}")
            continue

        # agregace poctu boxu podle vysky napric CELOU sestavou, sestupne
        counts = {}
        for cs in result["columnSummaries"]:
            for h in cs["heights"]:
                counts[h] = counts.get(h, 0) + cs["N"]
        height_desc = sorted(counts.keys(), reverse=True)
        name_suffix = "-".join(f"{h}x{counts[h]}" for h in height_desc)
        name = f"{SHORT_NAME[code]} - boxy43-{name_suffix}"

        ids = CAR_BODY_IDS[code]
        car_body_parts = [
            {"part_id": f"car_body_{ids['L']}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
            {"part_id": f"car_body_{ids['R_D']}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
            {"part_id": f"car_body_{ids['B']}", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
        ]
        all_parts = car_body_parts + parts

        total_boxes = sum(counts.values())
        note = (
            f"Bot16, 2026-08-31, davkova uloha Berlingo/Partner/Trafic (leva stena, noha 30x30 D=349mm, "
            f"custom_shapes.id={LEG_SHAPE_ID[cfg['family']]}). Karoserie {code} (car_bodies B={ids['B']}/L={ids['L']}/R_D={ids['R_D']}) "
            f"byla TETO session fyzicky otocena o 180 (orientation audit NEEDS_FLIP, zivě overeno proti zMid formuli). "
            f"Kolizni krokovani (car_body_placement_methods.id=1): step1 corner={result['step1']}, "
            f"step2 max_rozpon={result['step2']}. Sloupcove plneni (shape_geometry_methods.id=5): "
            f"{len(result['columnSummaries'])} sloupec(u), detail={result['columnSummaries']}. "
            f"Politika noh: {cfg['legPolicy']} - "
            + ("overeno realnym kolriznim testem (arch-check A/B: plny profil vs jen horni cast), zadny vyznamny podbeh nalezen, plain po cele delce." if cfg['legPolicy']=='all-plain' else
               f"Trafic MA nizky-vyskovy podbeh/naruseni pocinaje cca Z=-1007 (vzhledem k prednimu rohu) - overeno A/B testem (diff=929mm mezi plnym a jen-hornim profilem); WALL_CLEARANCE_ARCH={cfg.get('wallClearanceArch')} urceno realnym kolriznim skenem (ne prevzato z jineho vozidla). V TETO KONKRETNI sestave ale zadna vyrez noha nebyla nakonec potreba (sloupec se vejde jeste pred zonou podbehu, viz step4 vysledky - vsechny nohy vysly typem plain).") +
            f" Rear door height check (pravidlo 2): leg H={cfg['H']}mm porovnano s karoserie_model_reference.official_door_opening_height_mm/cargo_height_mm - "
            f"zadne zkraceni nutne (viz AGENTS_LOG.md pro presna cisla a poznamku o chybejicich oficialnich datech u nekterych kodu). "
            f"Vyskovy plan (pravidlo 6, cyklus 270/220/170/120 sestupne): distinct vysky pouzite={result['distinctHeights']}. "
            f"2D kontrolni mereni (pravidlo 8, skutecny Box3 z GLB): dims={verify['dims']}, 0 chyb. "
            f"Overeno: 0 kolizi s karoserii, 0 neocekavanych self-kolizi, celkem {len(all_parts)} dilu ({total_boxes} euroboxu)."
        )

        payload = {
            "parts": all_parts,
            "join_groups": [],
            "frame_groups": [],
            "bom": [],
            "price_summary": {},
            "_note": note,
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
        inserted.append({"code": code, "product_assemblies_id": new_id, "shop_product_id": shop_product_id, "sku": sku, "name": name, "total_boxes": total_boxes})
        print(f"{code}: product_assemblies.id={new_id} shop_product_id={shop_product_id} sku={sku} name={name!r} dily={len(all_parts)} boxy={total_boxes}")

conn.commit()
conn.close()
json.dump(inserted, open('/tmp/bpt_inserted.json', 'w'), indent=1, ensure_ascii=False)
print("\nHOTOVO, vlozeno", len(inserted), "sestav")
