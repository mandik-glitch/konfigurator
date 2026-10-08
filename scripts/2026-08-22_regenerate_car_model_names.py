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

CODE_RE = re.compile(r"^[A-Za-z]{2,3}\d{1,3}$")

def extract_code(filename):
    base = filename.rsplit(".", 1)[0]
    tokens = re.split(r"[_\s]+", base)
    cands = [t for t in tokens if CODE_RE.match(t)]
    return cands[-1] if cands else None

with conn.cursor() as cur:
    cur.execute("""
        SELECT cm.id model_id, cm.name cur_name, mk.name brand,
               (SELECT cb2.original_filename FROM car_bodies cb2 WHERE cb2.model_id=cm.id LIMIT 1) fname
        FROM car_models cm JOIN car_makes mk ON mk.id=cm.make_id
    """)
    models = cur.fetchall()

    cur.execute("SELECT * FROM karoserie_model_reference")
    ref = {r["legacy_vendor_code"].upper(): r for r in cur.fetchall()}

    cur.execute("SELECT id, model_id FROM car_bodies")
    body_to_model = {r["id"]: r["model_id"] for r in cur.fetchall()}

    cur.execute("SELECT id, name, data FROM custom_shapes WHERE name LIKE '%karoserie (L+R_D+B)%'")
    shapes = cur.fetchall()

# model_id -> shape row (1:1 podle puvodni logiky wire_full_batch.py)
model_to_shape = {}
for s in shapes:
    try:
        parts = json.loads(s["data"]).get("parts") or []
    except (ValueError, TypeError):
        continue
    for p in parts:
        pid = p.get("part_id", "")
        if pid.startswith("car_body_"):
            try:
                body_id = int(pid[len("car_body_"):])
            except ValueError:
                continue
            mid = body_to_model.get(body_id)
            if mid is not None:
                model_to_shape[mid] = s["id"]
            break

print(f"modelu: {len(models)}, shapes s karoserii: {len(shapes)}, model->shape mapovani: {len(model_to_shape)}")

updates = []
no_ref = []
for m in models:
    code = extract_code(m["fname"] or "")
    if not code or code.upper() not in ref:
        no_ref.append((m["model_id"], m["brand"], m["fname"], code))
        continue
    r = ref[code.upper()]
    nm = r["real_name"]
    if nm.upper().startswith(m["brand"].upper() + " "):
        nm = nm[len(m["brand"]) + 1:]
    # Robert 2026-08-22: "vendor" schvalne NENI v zobrazenem nazvu - jen
    # kod v hranatych zavorkach (unikatni identifikator + zdroj pro hover
    # kartu s rozmery).
    if r["overall_text"]:
        new_name = f"{nm} [{code}] — {r['overall_text']}"
    else:
        new_name = f"{nm} [{code}]"
    new_name = new_name[:250]
    if new_name != m["cur_name"]:
        updates.append((m["model_id"], m["cur_name"], new_name))

print(f"\nke zmene: {len(updates)} / {len(models)}")
print(f"BEZ reference (zustavaji jak jsou): {len(no_ref)}")
for x in no_ref:
    print("  ", x)

print("\nprvnich 8 zmen (nahled):")
for mid, old, new in updates[:8]:
    print(f"  #{mid}: {old!r}\n       -> {new!r}")

with open("/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/name_updates_preview.json", "w") as f:
    json.dump({"updates": updates, "model_to_shape": model_to_shape}, f, ensure_ascii=False)

conn.close()
