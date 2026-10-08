import json
import pymysql

env = {}
with open('/opt/konfigurator/api/.env') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k] = v

conn = pymysql.connect(host=env['DB_HOST'], port=int(env['DB_PORT']), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'],
                        cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

# --- nacti puvodni radek 333 (metadata + puvodni data JSON pro join_groups/frame_groups) ---
cur.execute("SELECT * FROM product_assemblies WHERE id=333")
src = cur.fetchone()
src_data = json.loads(src['data'])

with open('/opt/konfigurator/scripts/tmp_2026-09-12_333_parts_new.json') as f:
    new_parts = json.load(f)

assert len(new_parts) == len(src_data['parts']), "pocet dilu se zmenil!"

new_data = {
    "parts": new_parts,
    "join_groups": src_data.get("join_groups", []),
    "frame_groups": src_data.get("frame_groups", []),
    "bom": [],
    "price_summary": None,
    "razitka": None,
    "text_labels": [],
}

new_kod_sestavy = src['kod_sestavy'] + "-1030"

# --- unikatnost kod_sestavy ---
cur.execute("SELECT id FROM product_assemblies WHERE kod_sestavy=%s", (new_kod_sestavy,))
existing = cur.fetchone()
if existing:
    raise SystemExit(f"KOD_SESTAVY UZ EXISTUJE (id={existing['id']}) - STOP, needelam duplicitni insert.")

print("Novy kod_sestavy:", new_kod_sestavy, f"(delka {len(new_kod_sestavy)}, limit varchar(32))")
assert len(new_kod_sestavy) <= 32

cols = {
    "name": src["name"],
    "category_id": 4,
    "car_model_id": 7,  # dano zadanim (VSTUPNI DATA: car_body_base=Fiat_Doblo_FI14_2010-2022, car_model_id=7)
    "karoserie_kod": src["karoserie_kod"],
    "typologie_id": src["typologie_id"],
    "profil_mm": src["profil_mm"],
    "verze": src["verze"],
    "typologie_varianta_id": src["typologie_varianta_id"],
    "horni_blok_varianta_id": src["horni_blok_varianta_id"],
    "dodatek": src["dodatek"],
    "kod_sestavy": new_kod_sestavy,
    "prepazka_rezerva_mm": 10,
    "podbeh_rezerva_mm": 30,
    "data": json.dumps(new_data),
    "created_by": 1,
    "is_public": 1,
    "is_master": 0,
}

collist = list(cols.keys())
placeholders = ", ".join(["%s"] * len(collist))
sql = f"INSERT INTO product_assemblies ({', '.join(collist)}) VALUES ({placeholders})"
cur.execute(sql, [cols[c] for c in collist])
new_id = cur.lastrowid
conn.commit()
print("VLOZENO: novy radek id=", new_id)

# --- over ---
cur.execute("SELECT id, name, kod_sestavy, category_id, prepazka_rezerva_mm, podbeh_rezerva_mm, "
            "is_public, created_by, is_master, car_model_id, karoserie_kod, typologie_id, profil_mm, "
            "verze, typologie_varianta_id, horni_blok_varianta_id, dodatek FROM product_assemblies WHERE id=%s", (new_id,))
print(cur.fetchone())
cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (new_id,))
d = json.loads(cur.fetchone()['data'])
print("ulozeno parts:", len(d['parts']), "bom:", d['bom'], "price_summary:", d['price_summary'])

conn.close()
