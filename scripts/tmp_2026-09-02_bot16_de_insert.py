import json, re, pymysql

SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad"

env = {}
for line in open('/opt/konfigurator/api/.env'):
    line = line.rstrip('\n')
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v
conn = pymysql.connect(host=env['DB_HOST'], port=int(env['DB_PORT']), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'], charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)

VEHICLES = [
    {"key": "PE25", "srcId": 74, "baseName": "Peugeot e-Expert L1 PE25 (2021-)"},
    {"key": "MB47", "srcId": 83, "baseName": "Mercedes Vito MB47 (2014-)"},
    {"key": "FO31", "srcId": 111, "baseName": "Transit Custom L2 FO31"},
    {"key": "VW25", "srcId": 118, "baseName": "T7 VW25"},
    {"key": "OP31", "srcId": 136, "baseName": "Vivaro Electric L1 OP31"},
]

NOTE_TMPL = (
    "bot16 2026-09-02, varianta {tag} (budget - jen vysky 120/170/220mm, BEZ 270mm) pro "
    "nejnovejsi karoserii. Nohy/X-Z pudorys/car_body 100% beze zmeny vuci variante A "
    "(id={src_id}) - NA ROZDIL od variant B/C (ktere jen prelabelovaly box na uz existujici "
    "railY pozici), tady se railY pozice pater POCITAJI ZNOVU OD floor0 anchoru pomoci "
    "shape_geometry_methods.id=3 vzorce Y_rail_top(N+1)=Y_rail_top(N)+H_box(N)+60 (empiricky "
    "overeno 1:1 proti vsem 5 variantam A, diff=0.000mm), aby se vyuzila uspora mista z "
    "mensich boxu (bez 270mm) k pripadnemu PRIDANI dalsich pater navic oproti variante A. "
    "D = maximalni diverzita (220/170/120 tall-to-short, pak dopln 120mm patry navic, pokud "
    "budget dovoli). E = maximalni pocet kusu (vsechna patra 120mm - explicitne zadano, na "
    "rozdil od D). Kazde nejvyssi patro overeno REALNYM fyzickym stropem (viz "
    "physCeil/measurePhysCeil - horizontalni sonda sirokou jako cely box pudorys, postupne "
    "posouvana nahoru po 1mm dokud nezkoliduje s realnou karoserii, -2mm rezerva - STEJNA "
    "technika jako tmp_2026-08-31_batch_pipeline.js step7). Overeno: bez kolize s karoserii "
    "(collidesWithWalls na cele sestave), 0 neocekavanych self-kolizi, 2D sanity gate "
    "(heightY/depthX). DULEZITY NALEZ (viz AGENTS_LOG.md): primy test realneho eurobox GLB "
    "na jeho FINALNI pozici pomoci collidesWithWalls (edge-crossing raycasting) dava FALSE "
    "NEGATIVE, kdyz je box UZ CELY nad strechou (zadna hrana nekrizi stenu, overeno i na "
    "zjevne absurdni pozici Y=1900) - pouzita byla proto inkrementalni sonda (step7 styl), "
    "ktera zachyti presny okamzik prekroceni. Skladba: {byh}, celkem {total} euroboxu."
)


def height_suffix(by_height):
    parts = []
    for h in sorted((int(k) for k in by_height.keys()), reverse=True):
        parts.append(f"{h}x{by_height[str(h)]}")
    return "boxy43-" + "-".join(parts)


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


summary = json.load(open(f"{SCRATCH}/de_plan_summary.json"))
inserted = []

with conn.cursor() as cur:
    for v in VEHICLES:
        key = v["key"]
        src = json.load(open(f"{SCRATCH}/pa_{v['srcId']}.json"))
        for tag in ("D", "E"):
            res = summary[key][tag]
            if not res["ok"]:
                print(f"SKIP {key} {tag}: gate NEPROSEL ({res})")
                continue
            parts = json.load(open(f"{SCRATCH}/de_parts_{key}_{tag}.json"))
            byh = res["byHeight"]
            total = res["totalBoxes"]
            suffix = height_suffix(byh)
            name = f"{v['baseName']} {tag} - {suffix}"
            note = NOTE_TMPL.format(tag=tag, src_id=v["srcId"], byh=byh, total=total)
            payload = {
                "parts": parts,
                "join_groups": src.get("join_groups", []),
                "frame_groups": src.get("frame_groups", []),
                "bom": src.get("bom", []),
                "price_summary": src.get("price_summary", {}),
                "_note": note,
            }
            sku = generate_sku(cur, name)
            cur.execute(
                "INSERT INTO shop_products (sku, name, unit, active) VALUES (%s,%s,%s,0)",
                (sku, name, "ks"),
            )
            shop_product_id = cur.lastrowid
            cur.execute(
                "INSERT INTO product_assemblies (name, category_id, car_model_id, data, created_by, is_public, shop_product_id) "
                "VALUES (%s,NULL,NULL,%s,NULL,%s,%s)",
                (name, json.dumps(payload, ensure_ascii=False), 1, shop_product_id),
            )
            new_id = cur.lastrowid
            print(f"{key} variant {tag}: product_assemblies.id={new_id} shop_product_id={shop_product_id} sku={sku} dilu={len(parts)} name={name}")
            inserted.append({"key": key, "tag": tag, "product_assemblies_id": new_id, "shop_product_id": shop_product_id, "sku": sku, "name": name, "byHeight": byh, "totalBoxes": total})

conn.commit()
conn.close()
json.dump(inserted, open(f"{SCRATCH}/de_variants_inserted.json", "w"), ensure_ascii=False, indent=1)
print("HOTOVO, commit proveden.")
