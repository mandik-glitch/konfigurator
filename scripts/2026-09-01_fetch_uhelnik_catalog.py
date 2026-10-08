# Obecna metoda "uhelniky na spoje nohou" (bot16, 2026-09-01) - DB krok.
# Vytahne z shop_products vsechny katalogove "uhelnikove"/"rozkove" dily
# (attach_mode='corner_side', SKU-typovy suffix '01' - presne stejny filtr
# jako zivy uhelnikAutPart() ve webapp/scene.html), spocita "sizes" stejnym
# algoritmem jako partCompatMeta() (4-mistny segment SKU + nazev), a dumpne
# do JSON, ktery konzumuje scripts/2026-09-01_uhelniky_leg_joints_lib.js
# (Node engine - geometrie/three.js tam, DB cteni tady, presne podle
# zavedene konvence projektu: Python+pymysql pro DB, Node+three pro geometrii).
import json, re, pymysql

env = {}
for line in open('/opt/konfigurator/api/.env'):
    line = line.rstrip('\n')
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v

conn = pymysql.connect(host=env['DB_HOST'], port=int(env['DB_PORT']), user=env['DB_USER'],
                        password=env['DB_PASSWORD'], database=env['DB_NAME'], charset='utf8mb4',
                        cursorclass=pymysql.cursors.DictCursor, autocommit=False)

PROFILE_SIZE_NUMBERS = [10, 20, 25, 30, 35, 40, 45, 50, 60, 80, 90]


def sku_type_suffix(sku):
    seg = str(sku or "").split(".")
    return seg[-1] if seg else ""


def part_compat_sizes(sku, name):
    # port partCompatMeta() 'sizes' cast (webapp/scene.html) - jen 4-mistny
    # SKU segment (napr. "4040" -> 40,40) + "NNxNN"/"NNxNNN" v nazvu.
    sizes = set()
    for seg in str(sku or "").split("."):
        if len(seg) == 4 and seg.isdigit():
            a, b = int(seg[:2]), int(seg[2:])
            if a in PROFILE_SIZE_NUMBERS and b in PROFILE_SIZE_NUMBERS:
                sizes.add(a); sizes.add(b)
    for m in re.finditer(r"(\d{2})\s*[xX×]\s*(\d{2,3})", str(name or "")):
        for v in (m.group(1), m.group(2)):
            n = int(v)
            if n in PROFILE_SIZE_NUMBERS:
                sizes.add(n)
    return sorted(sizes)


with conn.cursor() as cur:
    cur.execute("""
        SELECT id, sku, name, attach_mode, uhelnik_pose, geo_faces_json, glb_file,
               cross_section_label, accessory_conn_enabled
        FROM shop_products
        WHERE attach_mode = 'corner_side'
    """)
    rows = cur.fetchall()

brackets = []
for r in rows:
    if sku_type_suffix(r["sku"]) != "01":
        continue  # jen "Uhelnikova spojka" rodina (viz uhelnikAutPart skuTypeSuffix filtr)
    sizes = part_compat_sizes(r["sku"], r["name"])
    if not sizes:
        continue
    geo_faces = json.loads(r["geo_faces_json"]) if r["geo_faces_json"] else None
    uhelnik_pose = json.loads(r["uhelnik_pose"]) if r["uhelnik_pose"] else None
    accessory_conn_enabled = json.loads(r["accessory_conn_enabled"]) if r.get("accessory_conn_enabled") else None
    brackets.append({
        "id": r["id"],
        "part_id": f"product_{r['id']}",
        "sku": r["sku"],
        "name": r["name"],
        "attach_mode": r["attach_mode"],
        "sizes": sizes,
        "glb_file": r["glb_file"],
        "geo_faces": geo_faces,
        "uhelnik_pose": uhelnik_pose,
        "accessory_conn_enabled": accessory_conn_enabled,
    })

out_path = "/opt/konfigurator/scripts/2026-09-01_uhelnik_catalog.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(brackets, f, ensure_ascii=False, indent=2)

print(f"{len(brackets)} corner_side/.01 bracket(s) written to {out_path}")
for b in brackets:
    print(" ", b["id"], b["sku"], b["name"], "sizes=", b["sizes"], "pose=", bool(b["uhelnik_pose"]), "geo_faces=", bool(b["geo_faces"]))
