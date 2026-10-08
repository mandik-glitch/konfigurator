import json, re, pymysql

env = {}
for line in open("/opt/konfigurator/api/.env"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k] = v

conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
                        user=env["DB_USER"], password=env["DB_PASSWORD"],
                        database=env["DB_NAME"], charset="utf8mb4",
                        cursorclass=pymysql.cursors.DictCursor)

ROW_IDS = [93,94,95,96,111,112,113,114,115,118,119,137,138,153,154,155,156,159,160,175,176,177,178]

with conn.cursor() as cur:
    cur.execute(f"SELECT id, name, data FROM product_assemblies WHERE id IN ({','.join(map(str, ROW_IDS))})")
    pa_rows = cur.fetchall()
    assert len(pa_rows) == 23, f"expected 23 rows, got {len(pa_rows)}"

    cur.execute("SELECT legacy_vendor_code, official_door_opening_height_mm FROM karoserie_model_reference")
    door_h = {r["legacy_vendor_code"]: r["official_door_opening_height_mm"] for r in cur.fetchall()}

    cur.execute("SELECT id, glb_file, original_filename FROM car_bodies")
    cb_rows = cur.fetchall()
    cb_glb = {}
    cb_code = {}
    code_re = re.compile(r"_([A-Za-z]{2,3}\d{1,3})_")
    for r in cb_rows:
        cb_glb[str(r["id"])] = r["glb_file"].split("/")[-1]  # bare filename, KAT already includes car_bodies/ via basePath logic below
        m = code_re.search(r["original_filename"] or "")
        if m:
            cb_code[r["id"]] = m.group(1)

rows_full = []
rows_meta = []
for r in pa_rows:
    data = json.loads(r["data"])
    parts = data.get("parts", [])
    car_body_ids = []
    for p in parts:
        pid = p.get("part_id", "")
        if pid.startswith("car_body_"):
            try:
                car_body_ids.append(int(pid[len("car_body_"):]))
            except ValueError:
                pass
    codes = {cb_code.get(cid) for cid in car_body_ids if cb_code.get(cid)}
    assert len(codes) == 1, f"row {r['id']}: expected exactly 1 vendor code, got {codes}"
    legacy_vendor_code = codes.pop()
    dh = door_h.get(legacy_vendor_code)
    assert dh is not None, f"row {r['id']}: missing door height for {legacy_vendor_code}"
    rows_full.append({"id": r["id"], "name": r["name"], "data": data,
                       "legacy_vendor_code": legacy_vendor_code, "door_height_mm": dh})
    rows_meta.append({"id": r["id"], "car_body_ids": car_body_ids})

SCRATCH = "/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad"
with open(f"{SCRATCH}/rows_full.json", "w") as f:
    json.dump(rows_full, f)
with open(f"{SCRATCH}/rows_meta.json", "w") as f:
    json.dump(rows_meta, f)
# car_body_glb.json: id -> bare "_L/_R_D/_B.glb" filename, but note actual files live
# under webapp/katalog/car_bodies/ subdir -> store WITH that prefix so KAT+name resolves.
cb_glb_prefixed = {}
for cid in {cid for m in rows_meta for cid in m["car_body_ids"]}:
    fname = cb_glb.get(str(cid))
    if fname:
        cb_glb_prefixed[str(cid)] = "car_bodies/" + fname
with open(f"{SCRATCH}/car_body_glb.json", "w") as f:
    json.dump(cb_glb_prefixed, f, ensure_ascii=False)

print("rows_full:", len(rows_full), "rows_meta:", len(rows_meta), "car_body_glb entries:", len(cb_glb_prefixed))
for r in rows_full:
    print(r["id"], r["name"], r["legacy_vendor_code"], r["door_height_mm"])
