import json, re, pymysql

env = {}
for line in open('/opt/konfigurator/api/.env'):
    line = line.rstrip('\n')
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k] = v

conn = pymysql.connect(host=env['DB_HOST'], port=int(env['DB_PORT']), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'], charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)

SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad"
results = json.load(open(f"{SCRATCH}/de_variants_result.json"))
summary = json.load(open(f"{SCRATCH}/de_variants_summary.json"))

VEHICLES = {
    "berlingo": {"paId": 95, "base": "ë-Berlingo L1 CI22"},
    "partner": {"paId": 101, "base": "e-Partner L1 PE23"},
    "trafic": {"paId": 103, "base": "Trafic L1 RE28"},
    "caddy": {"paId": 126, "base": "Caddy Cargo PHEV VW31"},
    "fordconnect": {"paId": 130, "base": "Transit Connect L1 FO36"},
    "proace": {"paId": 64, "base": "Proace Long Electric 20-"},
}

# poznamka k patru zahozenemu kvuli pre-existujici kolizi (mimo rozsah, viz JS build skript)
DROPPED_NOTE = {
    "trafic": " Patro puvodne 'sloupec0-patro4' (nejvyssi, X=-643.3) bylo ZE VSECH variant D i E "
              "ODSTRANENO (rail+spojnice+box) - cerstvy baseline check (variant A, id=103, "
              "PRED touto davkou) potvrdil realnou kolizi s karoserii RE28 na tomto patre "
              "NEZAVISLE na vysce boxu (i puvodnich 120mm koliduje) - zadna z {120,170,220} by "
              "problem nevyresila, jde o Y-pozici/kolizi s karoserii, ne o vysku boxu. Mimo "
              "rozsah teto davky (box-height replanning) - nahlaseno souběžnému floor/crossbar "
              "auditu, NEOPRAVENO zde.",
}


def comp_str(heightCounts):
    items = sorted(heightCounts.items(), key=lambda kv: -int(kv[0]))
    return "-".join(f"{h}x{n}" for h, n in items)


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


with conn.cursor() as cur:
    for key, cfg in VEHICLES.items():
        cur.execute("SELECT name, category_id FROM product_assemblies WHERE id=%s", (cfg["paId"],))
        row = cur.fetchone()
        if row is None or row["name"].split(" - boxy43")[0] != cfg["base"]:
            raise SystemExit(f"NEOCEKAVANY STAV pro {key} id={cfg['paId']}: {row}")
        cfg["category_id"] = row["category_id"]

    inserted = []
    for key, cfg in VEHICLES.items():
        for tag in ("D", "E"):
            v = results[key][tag]
            s = summary[key][tag]
            if not s["ok"]:
                raise SystemExit(f"{key} {tag} NEPROSLO overenim, insert PRESKOCEN: {s}")
            comp = comp_str(s["byHeight"])
            name = f"{cfg['base']} {tag} - boxy43-{comp}"
            extra = DROPPED_NOTE.get(key, "")
            if tag == "D":
                variant_desc = ("Varianta D = maximalni diverzita (vsechny 3 dostupne vysky nekde "
                                 "v sestave, nerostouci zdola nahoru v kazdem realnem sloupci).")
            else:
                variant_desc = ("Varianta E = maximalni pocet boxu v ramci sady 120/170/220mm "
                                 "(zadne patro navic nezruseno oproti variante A, krome pripadu "
                                 "popsanych nize).")
            note = (
                f"Bot16, 2026-09-01. Varianta {tag} (OMEZENA sada vysek euroboxu 120/170/220mm, "
                f"BEZ 270mm - Robertovo zadani 'dalsi varianty boxy 120,170,220 pro novejsi "
                f"karoserie') odvozena z variant A (product_assemblies.id={cfg['paId']}, cerstve "
                f"precteno TESNE pred touto davkou) - nohy/nosniky/spojnice/zaslepky/car_body "
                f"BEZE ZMENY (byte-identicke s variantou A, krome pripadne odstranenych pater - "
                f"viz nize), meni se jen ktery vyskovy eurobox (product_3788=120/product_3793=170/"
                f"product_3794=220mm) obsazuje ktere jiz existujici patro + odpovidajici "
                f"centrovani (Y pres per-vysku K-konstantu, X/Z pres per-vysku DX/DZ korekci pro "
                f"asymetricky pivot 170mm - vzdy dynamicky dopocitano ze skutecneho GLB, viz "
                f"KOMPONENTY_EUROBOXY.md). Bezpecnostni pravidlo: nova vyska <= puvodni vysce "
                f"na danem patre (box sedi spodkem VZDY na stejnem miste, zmensena vyska je proto "
                f"vzdy PODMNOZINA puvodne overeneho prostoru - zadny novy kolizni krok potreba). "
                f"{variant_desc} "
                f"Slozeni: {comp} = {s['totalBoxes']} ks (distinct vysek: {s['distinctHeights']}). "
                f"Rozmery sestavy: {s['dims']['lengthZ']:.0f}x{s['dims']['depthX']:.0f}x"
                f"{s['dims']['heightY']:.0f}mm. Overeno (skript "
                f"tmp_2026-09-01_bot16_de_variants.js, PRED timto insertem): 0 kolizi "
                f"eurobox/rail-karoserie (realne GLB proti realnym L/R_D/B car_body GLB, "
                f"collidesWithWalls), 0 neocekavanych self-kolizi, sanity rozmery OK. 2D "
                f"pudorys+naryz (skutecny Box3, de_{key}_{tag}.json) vygenerovan PRED timto "
                f"insertem.{extra}"
            )
            payload = {
                "parts": v["parts"],
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
                (name, cfg["category_id"], json.dumps(payload, ensure_ascii=False), None, 1, shop_product_id),
            )
            new_id = cur.lastrowid
            inserted.append((key, tag, new_id, shop_product_id, sku, name, len(v["parts"])))
            print(f"{key} {tag}: product_assemblies.id={new_id} shop_product_id={shop_product_id} sku={sku} dilu={len(v['parts'])} name={name}")

conn.commit()
conn.close()
json.dump(inserted, open(f"{SCRATCH}/de_variants_inserted.json", 'w'), indent=1, ensure_ascii=False)
print("COMMITTED")
