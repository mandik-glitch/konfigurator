"""Krok 7 (zapis) procedury shape_geometry_methods.id=11 pro SIROKOU davku
(14 modelu / 44 sestav, bot8 2026-09-12). Pouziti:

  api/venv/bin/python3 2026-09-12_wide_write_one.py <id> <mode:update|insert> \
      <parts_new.json> <report.json> [<car_model_id>]

mode=update: primy UPDATE radku <id> (neni v seznamu chranenych) - meni jen
  data (parts) + prepazka_rezerva_mm/podbeh_rezerva_mm. category_id/name/
  vse ostatni beze zmeny.
mode=insert: NOVY radek (kopie metadat puvodniho <id>, ktery JE v seznamu
  chranenych - zakaz preulozeni 2026-09-11) - category_id=4, prepazka=10,
  podbeh=30, name suffix " -1030" (a kod_sestavy suffix "-1030" pokud neni
  NULL) - puvodni radek zustava NEDOTCEN.

Overuje pred zapisem: report["OK"] is True, a ze puvodni radek porad ma
2/20mm (nikdo jiny s nim mezitim nehnul).
"""
import json, sys, pymysql

PROTECTED = {79,82,83,116,117,134,135,151,152,173,182,189,209,219,224,250,251,
             279,289,294,320,321,332,333,334,335,336,337}

aid = int(sys.argv[1])
mode = sys.argv[2]
parts_path = sys.argv[3]
report_path = sys.argv[4]
car_model_id = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != "None" else None

if mode == "insert" and aid not in PROTECTED:
    raise SystemExit(f"id={aid} NENI v chranenem seznamu - mel by byt mode=update, ne insert. STOP.")
if mode == "update" and aid in PROTECTED:
    raise SystemExit(f"id={aid} JE v chranenem seznamu - nesmi se UPDATEnout primo. STOP.")

with open(report_path) as f:
    report = json.load(f)
if report.get("OK") is not True:
    raise SystemExit(f"id={aid}: verify report neni OK ({json.dumps({k:report.get(k) for k in ['collisions','allSeamsOk','newProblems']})}) - STOP, nezapisuji.")

with open(parts_path) as f:
    new_parts = json.load(f)

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
cur.execute("SELECT * FROM product_assemblies WHERE id=%s", (aid,))
orig = cur.fetchone()
if orig is None:
    raise SystemExit(f"id={aid} nenalezeno")
if orig["prepazka_rezerva_mm"] != 2 or orig["podbeh_rezerva_mm"] != 20:
    raise SystemExit(f"id={aid} uz nema puvodni 2/20mm rezervu ({orig['prepazka_rezerva_mm']}/{orig['podbeh_rezerva_mm']}) - nekdo uz s nim hnul. STOP.")

orig_data = json.loads(orig["data"])
note_suffix = (
    " | PREPOCET KOLIZNI REZERVY 2026-09-12 (bot8, shape_geometry_methods.id=11, "
    "siroka davka 14 modelu): 2/20mm -> 10/30mm. deltaZ=+8mm na noze0 (nejblize "
    "prepazce B.glb, overeno primo na realne GLB geometrii karoserie) + na sloupci0 "
    "(rozpeti noha0..noha1). Vyrezove nohy (majici sloupek-pred-podbehem/"
    "zadni-svislice-nad-zarezem/pricka-uzavreni-vyrezu) dostaly deltaY=+10mm na "
    "teto trojici podle vzorce shape_geometry_methods.id=6, old_y_new zmereno "
    "primo z dat. Genericky engine scripts/2026-09-12_wide_transform_lib.js "
    "(auto-detekce noh/sloupcu podle role+Z, ne hardcoded per-model). Overeno: "
    f"SAT test {report['collisions']}/{report['testedParts']} kolizi s realnou GLB "
    f"karoserii, seamChecks={json.dumps(report['seamChecks'])}, self-kolize "
    f"{report['afterSelfSusp']} celkem ({report['baselineSelfSusp']} uz v baseline, "
    f"{len(report['newProblems'])} novych). Skripty: "
    "scripts/2026-09-12_wide_transform_lib.js, scripts/2026-09-12_wide_verify_lib.js, "
    "scripts/2026-09-12_wide_process_one.js."
)
new_data = {
    "parts": new_parts,
    "join_groups": orig_data.get("join_groups", []),
    "frame_groups": orig_data.get("frame_groups", []),
    "bom": [],
    "price_summary": None,
    "_note": (orig_data.get("_note") or "") + note_suffix,
}

if mode == "update":
    cur.execute(
        "UPDATE product_assemblies SET data=%s, prepazka_rezerva_mm=10, podbeh_rezerva_mm=30 WHERE id=%s",
        (json.dumps(new_data, ensure_ascii=False), aid),
    )
    conn.commit()
    cur.execute("SELECT id, name, category_id, prepazka_rezerva_mm, podbeh_rezerva_mm FROM product_assemblies WHERE id=%s", (aid,))
    print("UPDATED:", json.dumps(cur.fetchone(), default=str, ensure_ascii=False))
else:
    new_name = orig["name"] + " -1030"
    new_kod_sestavy = (orig["kod_sestavy"] + "-1030") if orig["kod_sestavy"] else None
    cols = [
        "name", "category_id", "car_model_id", "karoserie_kod", "typologie_id",
        "profil_mm", "verze", "typologie_varianta_id", "horni_blok_varianta_id",
        "dodatek", "kod_sestavy", "prepazka_rezerva_mm", "podbeh_rezerva_mm",
        "data", "created_by", "is_public", "technicky_ok", "is_master",
    ]
    vals = [
        new_name, 4, (car_model_id if car_model_id is not None else orig["car_model_id"]), orig["karoserie_kod"], orig["typologie_id"],
        orig["profil_mm"], orig["verze"], orig["typologie_varianta_id"], orig["horni_blok_varianta_id"],
        orig["dodatek"], new_kod_sestavy, 10, 30,
        json.dumps(new_data, ensure_ascii=False), orig["created_by"], orig["is_public"], 0, 0,
    ]
    placeholders = ",".join(["%s"] * len(cols))
    sql = f"INSERT INTO product_assemblies ({','.join(cols)}) VALUES ({placeholders})"
    cur.execute(sql, vals)
    new_id = cur.lastrowid
    conn.commit()
    cur.execute("SELECT id, name, category_id, car_model_id, karoserie_kod, verze, kod_sestavy, "
                "prepazka_rezerva_mm, podbeh_rezerva_mm FROM product_assemblies WHERE id=%s", (new_id,))
    print("INSERTED new_id=", new_id, json.dumps(cur.fetchone(), default=str, ensure_ascii=False))
    cur.execute("SELECT prepazka_rezerva_mm, podbeh_rezerva_mm, category_id FROM product_assemblies WHERE id=%s", (aid,))
    print(f"puvodni id={aid} kontrola nezmeneno:", json.dumps(cur.fetchone(), default=str))

conn.close()
