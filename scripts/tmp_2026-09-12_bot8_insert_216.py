# Krok 7 procedury prepocet-kolizni-rezervy-existujici-sestavy: INSERT noveho
# radku product_assemblies pro id=216 (K-119, verze B) - puvodni radek 216
# NEDOTCEN. Pouziva vystup scripts/tmp_2026-09-12_216_parts_new.json
# (transformovane parts z tmp_2026-09-12_bot8_batch_216.js), ktery uz presel
# vsemi kroky 6a/6b/6c v tmp_2026-09-12_bot8_verify_216.js (0/73 kolizi s
# realnou karoserii K-119 CI19, gap=0.000000mm na posunutem svaru, 0 novych
# self-kolizi, dorovnani neni potreba - 169mm rezerva).
import json, sys, pymysql

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

cur.execute("SELECT * FROM product_assemblies WHERE id=216")
orig = cur.fetchone()
if orig is None:
    raise SystemExit("id=216 nenalezeno")
if orig["prepazka_rezerva_mm"] != 2 or orig["podbeh_rezerva_mm"] != 20:
    raise SystemExit(f"id=216 uz nema puvodni 2/20mm rezervu ({orig['prepazka_rezerva_mm']}/{orig['podbeh_rezerva_mm']}) - STOP, nekdo uz s nim mezitim hnul.")

orig_data = json.loads(orig["data"])
with open("/opt/konfigurator/scripts/tmp_2026-09-12_216_parts_new.json") as f:
    new_parts = json.load(f)

with open("/opt/konfigurator/scripts/tmp_2026-09-12_216_verify_report.json") as f:
    verify = json.load(f)
if verify["collisions"] != 0 or verify["seamGapOk"] is not True or len(verify["newProblems"]) != 0:
    raise SystemExit(f"Verify report neni cisty: {verify} - STOP, nezapisuji.")

new_data = {
    "parts": new_parts,
    "join_groups": orig_data.get("join_groups", []),
    "frame_groups": orig_data.get("frame_groups", []),
    "bom": [],
    "price_summary": None,
    "_note": (orig_data.get("_note") or "") +
        " | PREPOCET KOLIZNI REZERVY 2026-09-12 (bot, shape_geometry_methods.id=11): "
        "2/20mm -> 10/30mm. Delty: deltaZ=+8mm na plne noze na Z=-1522.500114440918 "
        "(predni-svislice/cap/spojnice-dolni/spojnice-horni/zadni-svislice-dolni/zaslepka x3/"
        "uhelnik-noha0 x7, cele) a na sloupci sloupec0 (nosnik/spojnice/eurobox, rozpeti "
        "leg0..leg1, stred +4mm=deltaZ/2, nosnik delka -8mm). Na sdilenem Z=-260.50011444091797 "
        "(soucasne plna 'predni' cast + vyrezova noha) zustava plna cast (predni-svislice/cap/"
        "spojnice-dolni/spojnice-horni/zaslepka x3) BEZE ZMENY (overeno empiricky na hotovem "
        "paru product_assemblies 279->340 a 184->348), meni se jen vyrezova trojice "
        "(sloupek-pred-podbehem/zadni-svislice-nad-zarezem/pricka-uzavreni-vyrezu, Y podle "
        "vzorce shape_geometry_methods.id=6, old_y_new=141.00018310546875) a uhelnik-noha1 "
        "(5 z 12 kusu, ty na svaru Y=141/171). Krok 4 (dorovnani pater): NEBYLO POTREBA - "
        "spodni hrana nejnizsiho patra (nosnik-sloupec0-patro0, Y=335.0002) ma po delte "
        "168.9996mm kladnou rezervu nad novym Y_new nohy1 (151.0002mm). Overeno: SAT test "
        "0/73 kolizi s realnou GLB karoserii K-119 (Citroen Jumpy CI19 2016-, _L/_R_D/_B), "
        "gap na posunutem svaru = 0.000000mm presne, self-kolize 0 novych (baseline "
        "puvodniho 216 mela taky 0 z 2628 paru). Zadna razitka v puvodnich datech nebyla "
        "(data nemela klic 'razitka'). Skripty: scripts/tmp_2026-09-12_bot8_batch_216.js "
        "(transform, prevzata genericka funkce z tmp_2026-09-12_bot8_batch_184.js), "
        "scripts/tmp_2026-09-12_bot8_verify_216.js (overeni krok 6a/6b/6c).",
}

new_name = orig["name"] + " [10/30mm od kolize]"

cols = [
    "name", "category_id", "car_model_id", "karoserie_kod", "typologie_id",
    "profil_mm", "verze", "typologie_varianta_id", "horni_blok_varianta_id",
    "dodatek", "kod_sestavy", "prepazka_rezerva_mm", "podbeh_rezerva_mm",
    "data", "created_by", "is_public", "technicky_ok", "is_master",
]
vals = [
    new_name, 4, 43, orig["karoserie_kod"], orig["typologie_id"],
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
            "prepazka_rezerva_mm, podbeh_rezerva_mm, is_public, created_by, is_master, technicky_ok "
            "FROM product_assemblies WHERE id=%s", (new_id,))
print(json.dumps(cur.fetchone(), default=str, ensure_ascii=False, indent=1))

# over ze 216 zustalo nedotcene
cur.execute("SELECT prepazka_rezerva_mm, podbeh_rezerva_mm, category_id FROM product_assemblies WHERE id=216")
print("216 (puvodni, kontrola nezmeneno):", json.dumps(cur.fetchone(), default=str))

conn.close()
print("\nNEW_ID=", new_id)
