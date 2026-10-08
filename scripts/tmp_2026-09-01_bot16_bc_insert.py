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
    {
        "key": "FO36", "srcId": 130, "baseName": "Transit Connect L1 FO36",
        "note_prefix": "bot16 2026-09-01, varianta {tag} pro nejnovejsi karoserii Ford Connect (FO36, L1). Nohy/sloupce/rail-Y beze zmeny vuci variante A (id=130) - meni se JEN ktery eurobox-GLB (vyska) sedi na kterem uz existujicim patre (1 sloupec, N=1, 4 patra). Pravidlo bezpecnosti: nova vyska na kazdem patre <= puvodni vyska variante A na tom patre (box sedi spodkem VZDY na stejnem miste - rail top - 12mm - zmensena vyska je proto podmnozina puvodne overeneho prostoru, zadna nova kolize s karoserii nemuze vzniknout). Overeno: bez kolize s karoserii (cely soubor dilu), 0 neocekavanych self-kolizi (nesting box/rail na stejnem patre a zaslepky/cap ocekavany), 2D top+elevation gate (skutecny Box3, heightY/depthX v rozumnem rozsahu) presel PRED ulozenim. Pozn.: FO36 ma OBE nohy plain (bez podbehu) s floorY~2mm - mozny kandidat na 'plna_noha_bez_podbehu_floor_200mm' pravidlo z probihajiciho auditu (NEOPRAVOVANO zde, mimo rozsah - noha byla prevzata beze zmeny z variant A, audit resi zvlast).",
    },
    {
        "key": "TO23", "srcId": 64, "baseName": "Proace Long Electric 20-",
        "note_prefix": "bot16 2026-09-01, varianta {tag} pro Proace Long Electric TO23 (nahrazuje puvodne planovany Proace Max TO14, ktery Robert vyloucil z automatizovanych navrhu - 'neni mala dodavka'). Nohy/sloupce/rail-Y beze zmeny vuci variante A (id=64) - meni se JEN ktery eurobox-GLB (vyska) sedi na kterem uz existujicim patre (2 sloupce: sloupec0 N=3, sloupec1 N=2, kazdy 2 patra). Pravidlo bezpecnosti: nova vyska na kazdem patre <= puvodni vyska variante A na tom patre (viz FO36 pozn. pro zduvodneni bezpecnosti). Overeno: 0 neocekavanych self-kolizi, 2D top+elevation gate presel. POZOR - nalezena PRE-EXISTUJICI kolize s karoserii u SLOUPCE 0 (nezmenene, stejne v A i B i C - nosnik/spojnice/eurobox sloupec0 patro0+patro1 a 2 dily nohy u zadni podbehove nohy) pri opakovanem behu collidesWithWalls (tmp_2026-08-31_batch_engine.js) - protoze je IDENTICKA i v puvodni variante A (nezavisla na teto praci, sloupec1 kde delam zmeny je cisty), jde bud o false-positive te konkretni kolizni metody (flush-touch raycasting artefakt) nebo o skutecny drobny nedostatek puvodniho ProAce batch buildu - NEOPRAVOVANO zde (mimo rozsah zadani, legs/columns/orientace 'jiz overene'), zapsano pro navazujici audit.",
    },
    {
        "key": "PE25", "srcId": 74, "baseName": "Peugeot e-Expert L1 PE25 (2021-)",
        "note_prefix": "bot16 2026-09-01, varianta {tag} pro Peugeot e-Expert L1 PE25. Nohy/sloupce/rail-Y beze zmeny vuci variante A (id=74) - meni se JEN ktery eurobox-GLB (vyska) sedi na kterem uz existujicim patre (1 sloupec, N=3, 2 patra). Pravidlo bezpecnosti: nova vyska na kazdem patre <= puvodni vyska variante A na tom patre. Overeno: bez kolize s karoserii, 0 neocekavanych self-kolizi, 2D top+elevation gate presel.",
    },
]


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


summary = json.load(open(f"{SCRATCH}/bc_variants_summary.json"))
inserted = []

with conn.cursor() as cur:
    for v in VEHICLES:
        key = v["key"]
        src = json.load(open(f"{SCRATCH}/pa_{v['srcId']}_bot16bc.json"))
        for tag in ("B", "C"):
            parts = json.load(open(f"{SCRATCH}/parts_{key}_{tag}.json"))
            byh = summary[key][tag]["byHeight"]
            total = summary[key][tag]["totalBoxes"]
            suffix = height_suffix(byh)
            name = f"{v['baseName']} {tag} - {suffix}"
            note = v["note_prefix"].format(tag=tag) + f" Skladba: {byh}, celkem {total} euroboxu."
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
json.dump(inserted, open(f"{SCRATCH}/bc_variants_inserted.json", "w"), ensure_ascii=False, indent=1)
print("HOTOVO, commit proveden.")
