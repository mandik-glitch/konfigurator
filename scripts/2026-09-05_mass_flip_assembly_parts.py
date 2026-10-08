#!/usr/bin/env python3
# Navazuje na 2026-09-05_mass_orientation_fix.js: po baked 180Y flipu GLB
# prepocita regaly v dotcenych product_assemblies. car_body party zustavaji
# na identite (mesh uz je baked-flipnuty), ostatni dily se transformuji -
# pouziva OVERENY node skript flip_product_assembly_parts_180.js (zadna
# replikace kvaternionove matematiky). Zaloha kazde sestavy pred UPDATE.
# bot22 2026-09-05.  Rezim: --dry-run | (bez argu = provede)
import json, os, sys, subprocess, tempfile

DRY = "--dry-run" in sys.argv
sys.path.insert(0, "/opt/konfigurator/api"); os.chdir("/opt/konfigurator/api")
for l in open(".env"):
    l = l.strip()
    if l and not l.startswith("#") and "=" in l:
        k, v = l.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
import app as A

FLIPPED = set(json.load(open("/tmp/flipped_cb_ids.json")))
BACKUP = "/opt/konfigurator/backups/2026-09-05_mass_orientation_flip/assemblies"
os.makedirs(BACKUP, exist_ok=True)
NODE_FLIP = "/opt/konfigurator/scripts/2026-08-31_flip_product_assembly_parts_180.js"

conn = A.get_conn(); cur = conn.cursor()
cur.execute("SELECT id, name, data FROM product_assemblies")
rows = cur.fetchall()

affected = []
for r in rows:
    try:
        d = json.loads(r["data"])
    except Exception:
        continue
    cb_ids = [int(str(p["part_id"]).replace("car_body_", "")) for p in d.get("parts", [])
              if str(p.get("part_id", "")).startswith("car_body_")]
    if any(cid in FLIPPED for cid in cb_ids):
        affected.append((r["id"], r["name"], d))

print(f"Dotcenych sestav (regal na flipnute karoserii): {len(affected)}")
for aid, name, _ in affected[:40]:
    print(f"  id={aid}  {name[:55]}")
if len(affected) > 40:
    print(f"  ... a dalsich {len(affected)-40}")

if DRY:
    print("--- DRY RUN, nic se nemeni ---")
    sys.exit(0)

done = 0; errs = []
for aid, name, d in affected:
    # zaloha - NIKDY neprepisovat existujici (bot8 2026-09-05): druhy beh skriptu
    # by jinak zapsal UZ FLIPNUTA data pres jedinou pred-flip zalohu a znicil
    # jedinou cestu k obnove. Doprovodny JS (mass_orientation_fix.js:112) tuhle
    # ochranu ma (`if (!fs.existsSync(bpath))`), tady chybela.
    bpath = os.path.join(BACKUP, f"assembly_{aid}.json")
    if not os.path.exists(bpath):
        with open(bpath, "w") as f:
            json.dump({"id": aid, "name": name, "data": d}, f, ensure_ascii=False, indent=1)
    # flip pres overeny node skript
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fi:
        json.dump(d, fi, ensure_ascii=False); inp = fi.name
    outp = inp + ".out"
    try:
        subprocess.run(["node", NODE_FLIP, inp, outp], check=True, capture_output=True, text=True)
        newd = json.load(open(outp))
        cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s", (json.dumps(newd, ensure_ascii=False), aid))
        done += 1
    except subprocess.CalledProcessError as e:
        errs.append(f"id={aid}: {e.stderr.strip()[:120]}")
    finally:
        for f in (inp, outp):
            try: os.unlink(f)
            except OSError: pass

conn.commit()
print(f"\nHOTOVO: {done} sestav prepocitano a ulozeno. Zalohy: {BACKUP}")
if errs:
    print(f"CHYBY ({len(errs)}):"); [print("  " + e) for e in errs[:10]]
