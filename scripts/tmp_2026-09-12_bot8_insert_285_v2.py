# Krok 7 procedury prepocet-kolizni-rezervy-existujici-sestavy: INSERT noveho
# radku product_assemblies pro id=285 (K-118, verze C) - puvodni radek 285
# NEDOTCEN. Pouziva vystup scripts/tmp_2026-09-12_285_parts_new.json
# (transformovane parts z tmp_2026-09-12_bot8_batch_285_v2.js, ktery
# ZNOVUPOUZIVA uz 4x overenou transformAssembly() z
# tmp_2026-09-12_bot8_batch_184.js - stejna rodina K-118, identicka
# geometrie noh), ktery uz presel vsemi kroky 6a/6b/6c (0 kolizi s realnou
# karoserii, gap=0.000000mm na posunutem svaru, 0 novych self-kolizi).
#
# Presne stejny vzor jako tmp_2026-09-12_insert_184_1030.py (sourozenec
# stejne rodiny, stejna session) - car_model_id=42, kod_sestavy=puvodni
# (NULL, cela K-118 rodina ho nikdy nemela), category_id=4.
import json, pymysql

env = {}
with open("api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
                        user=env["DB_USER"], password=env["DB_PASSWORD"],
                        database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

cur.execute("SELECT * FROM product_assemblies WHERE id=285")
orig = cur.fetchone()
if orig is None:
    raise SystemExit("id=285 nenalezeno")

with open("/opt/konfigurator/scripts/tmp_2026-09-12_285_verify_report.json") as f:
    verify = json.load(f)
assert verify["collisions"] == 0, "SAT nenaslo 0 - NEZAPISOVAT"
assert all(abs(s["gap"]) < 0.01 or s["gap"] >= 0 for s in verify["seamChecks"]), "seam gap problem - NEZAPISOVAT"
assert verify["afterSelfSusp"] == 0, "self-kolize po transformu - NEZAPISOVAT"
assert len(verify["newProblems"]) == 0, "nove self-kolize - NEZAPISOVAT"

orig_data = json.loads(orig["data"])
with open("/opt/konfigurator/scripts/tmp_2026-09-12_285_parts_new.json") as f:
    new_parts = json.load(f)
assert len(new_parts) == 61

new_data = {
    "parts": new_parts,
    "join_groups": orig_data.get("join_groups", []),
    "frame_groups": orig_data.get("frame_groups", []),
    "bom": [],
    "price_summary": None,
    "_note": (orig_data.get("_note") or "") +
        " | PREPOCET KOLIZNI REZERVY 2026-09-12 (bot8, shape_geometry_methods.id=11): "
        "2/20mm -> 10/30mm. Delty: deltaZ=+8mm na plne noze na Z=-1170.5000534057617 "
        "(predni-svislice/cap/spojnice-dolni/spojnice-horni/zadni-svislice-dolni/zaslepka x3/"
        "uhelnik-noha0 x7, cele) a na sloupci sloupec0 (nosnik/spojnice/eurobox, rozpeti "
        "leg0..leg1, stred +4mm=deltaZ/2, nosnik delka -8mm). Na sdilenem Z=-308.5000534057617 "
        "(soucasne plna+vyrezova noha) zustava plna cast (predni-svislice/cap/spojnice-dolni/"
        "spojnice-horni/zaslepka x3) BEZE ZMENY (overeno empiricky na hotovem paru "
        "product_assemblies 279->340, stejna transformAssembly() jako sourozenec 184->348), "
        "meni se jen vyrezova trojice (sloupek-pred-podbehem/zadni-svislice-nad-zarezem/"
        "pricka-uzavreni-vyrezu, Y podle vzorce shape_geometry_methods.id=6) a uhelnik-noha1 "
        "(5 z 12 kusu, ty na svaru Y=291/321). Krok 4 (dorovnani pater): NEBYLO POTREBA - "
        "spodni hrana nejnizsiho patra (nosnik-sloupec0-patro0, Y=335.0001) ma po delte porad "
        "18.9997mm kladnou rezervu nad novym Y_new nohy1 (301.0001mm). Overeno: SAT test 0/58 "
        "kolizi s realnou GLB karoserii K-118 (_L/_R_D/_B), gap na posunutem svaru = 0.000000mm "
        "presne, self-kolize 0 novych (baseline puvodniho 285 mela taky 0). Skripty: "
        "scripts/tmp_2026-09-12_bot8_batch_285_v2.js (transform, znovupouziva transformAssembly() "
        "z tmp_2026-09-12_bot8_batch_184.js + krok 6 overeni).",
}

new_name = orig["name"] + " [10/30mm od kolize]"

cols = [
    "name", "category_id", "car_model_id", "karoserie_kod", "typologie_id",
    "profil_mm", "verze", "typologie_varianta_id", "horni_blok_varianta_id",
    "dodatek", "kod_sestavy", "prepazka_rezerva_mm", "podbeh_rezerva_mm",
    "data", "created_by", "is_public", "technicky_ok", "is_master",
]
vals = [
    new_name, 4, 42, orig["karoserie_kod"], orig["typologie_id"],
    orig["profil_mm"], orig["verze"], orig["typologie_varianta_id"], orig["horni_blok_varianta_id"],
    orig["dodatek"], orig["kod_sestavy"], 10, 30,
    json.dumps(new_data, ensure_ascii=False), 1, 1, 0, 0,
]

placeholders = ",".join(["%s"] * len(cols))
sql = f"INSERT INTO product_assemblies ({','.join(cols)}) VALUES ({placeholders})"
cur.execute(sql, vals)
new_id = cur.lastrowid
conn.commit()

cur.execute("SELECT id, name, category_id, car_model_id, karoserie_kod, verze, kod_sestavy, "
            "prepazka_rezerva_mm, podbeh_rezerva_mm, is_public, created_by, is_master, technicky_ok, "
            "JSON_LENGTH(data, '$.parts') n_parts "
            "FROM product_assemblies WHERE id=%s", (new_id,))
print(json.dumps(cur.fetchone(), default=str, ensure_ascii=False, indent=1))

cur.execute("SELECT prepazka_rezerva_mm, podbeh_rezerva_mm, category_id FROM product_assemblies WHERE id=285")
print("285 (puvodni, kontrola nezmeneno):", json.dumps(cur.fetchone(), default=str))

conn.close()
print("\nNEW_ID=", new_id)
