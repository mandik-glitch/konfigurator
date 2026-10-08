import re, json, pymysql

env = {}
for line in open("/opt/konfigurator/api/.env"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k] = v

conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
                        user=env["DB_USER"], password=env["DB_PASSWORD"],
                        database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)

DND = json.load(open("/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/karoserie_site_data_v2.json"))

def parse_overall(s):
    if not s: return (None, None, None)
    m = re.search(r"([\d.]+)mm\s*\(L\)\s*([\d.]+)mm\s*\(W\)\s*([\d.]+)mm\s*\(H\)", s)
    return (int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3)))) if m else (None, None, None)

def parse_wheelbase(s):
    if not s: return None
    m = re.search(r"([\d.]+)mm", s)
    return int(float(m.group(1))) if m else None

def parse_volume(s):
    if not s: return None
    m = re.search(r"([\d.]+)\s*m", s)
    return float(m.group(1)) if m else None

with conn.cursor() as cur:
    cur.execute("SHOW COLUMNS FROM karoserie_model_reference")
    existing_cols = {r["Field"] for r in cur.fetchall()}

    new_cols = [
        ("manufacturer", "VARCHAR(50) NULL"),
        ("model_range", "VARCHAR(100) NULL"),
        ("overall_text", "VARCHAR(100) NULL"),
        ("overall_length_mm", "INT NULL"),
        ("overall_width_mm", "INT NULL"),
        ("overall_height_mm", "INT NULL"),
        ("wheelbase_mm", "INT NULL"),
        ("cargo_text", "VARCHAR(100) NULL"),
        ("cargo_length_mm", "INT NULL"),
        ("cargo_width_mm", "INT NULL"),
        ("cargo_height_mm", "INT NULL"),
        ("cargo_volume_m3", "DECIMAL(6,2) NULL"),
        ("updated_at", "TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    ]
    for col, ddl in new_cols:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE karoserie_model_reference ADD COLUMN {col} {ddl}")
            print("pridan sloupec:", col)
conn.commit()

n_upsert = 0
with conn.cursor() as cur:
    for code, info in DND.items():
        ov_l, ov_w, ov_h = parse_overall(info.get("overall"))
        cg_l, cg_w, cg_h = parse_overall(info.get("cargo"))
        wb = parse_wheelbase(info.get("wheelbase"))
        vol = parse_volume(info.get("volume"))
        cur.execute("""
            INSERT INTO karoserie_model_reference
              (legacy_vendor_code, real_name, manufacturer, model_range, overall_text,
               overall_length_mm, overall_width_mm, overall_height_mm, wheelbase_mm,
               cargo_text, cargo_length_mm, cargo_width_mm, cargo_height_mm, cargo_volume_m3)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              real_name=VALUES(real_name), manufacturer=VALUES(manufacturer),
              model_range=VALUES(model_range), overall_text=VALUES(overall_text),
              overall_length_mm=VALUES(overall_length_mm), overall_width_mm=VALUES(overall_width_mm),
              overall_height_mm=VALUES(overall_height_mm), wheelbase_mm=VALUES(wheelbase_mm),
              cargo_text=VALUES(cargo_text), cargo_length_mm=VALUES(cargo_length_mm),
              cargo_width_mm=VALUES(cargo_width_mm), cargo_height_mm=VALUES(cargo_height_mm),
              cargo_volume_m3=VALUES(cargo_volume_m3)
        """, (code.upper(), info.get("name") or code, info.get("manufacturer"), info.get("model_range"),
              info.get("overall"), ov_l, ov_w, ov_h, wb,
              info.get("cargo"), cg_l, cg_w, cg_h, vol))
        n_upsert += 1
conn.commit()
print(f"upsertnuto {n_upsert} radku (z {len(DND)} DND zaznamu)")

with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) c FROM karoserie_model_reference")
    print("karoserie_model_reference celkem radku ted:", cur.fetchone())

conn.close()
