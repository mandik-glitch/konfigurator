"""
Davkovy prevod STP/FBX -> GLB pro produkty, ktere maji nahrany zdrojovy
3D model (fbx_original_name), ale zatim nemaji prevedeny glb_file -
Robert 2026-08-10 ("zobrazovat pro 3D zivy nahled potrebujeme glb,
takze to se musi jeste prevest ve spravne kvalite, ani mala ani velka")
navazuje na zive 3D nahledy v detailu produktu (webapp/product.html,
viz AGENTS_LOG.md "bot8 - Zivy 3D nahled + STP download").

Kvalita "medium" (viz api/step_convert_worker.py QUALITY_PRESETS) -
stredni stupen mezi "low" (hruba sit, jen odstrani logo) a "high" (zadna
simplifikace, nejvetsi soubory) - deflection_mult 0.2, simplify_percent
0.75, min_face_area_frac 0.01. FBX zdroje (fbx_convert.py) zadnou volbu
kvality nemaji, quality parametr se pro ne ignoruje.

Bezi PRIMO v api/ venv (potrebuje step_convert.py/fbx_convert.py ze
stejneho adresare) - spoustet jako:
  cd /opt/konfigurator/api && venv/bin/python3 ../scripts/2026-08-10_product_stp_to_glb_batch.py

Idempotentni: bere jen radky s glb_file IS NULL, takze opakovane
spusteni prevede jen to, co jeste chybi (napr. po pridani noveho STP).
Zdrojovy STP/FBX soubor se nikdy nemaze/nemeni. Prubezny log do stdout
+ souhrn na konec do backups/.
"""
import os
import sys
import json
import time
import glob as globmod

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import pymysql
import step_convert
import fbx_convert

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
PRODUCT_FBX_UPLOAD_DIR = "/opt/konfigurator/webapp/content-files/product_fbx"
KATALOG_GLB_DIR = "/opt/konfigurator/webapp/katalog"
QUALITY = "medium"


def convert_one(product_id, src_path):
    ext = os.path.splitext(src_path)[1].lower()
    glb_name = f"product_{product_id}.glb"
    glb_dest = os.path.join(KATALOG_GLB_DIR, glb_name)
    if ext == ".fbx":
        ok, info = fbx_convert.convert_single_fbx(src_path, glb_dest)
    elif ext in (".stp", ".step"):
        ok, info = step_convert.convert_single_step(src_path, glb_dest, quality=QUALITY)
    else:
        return False, {"error": f"nepodporovana pripona {ext}"}, None
    return ok, info, glb_name


def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, sku, name, fbx_original_name FROM shop_products "
        "WHERE fbx_original_name IS NOT NULL AND glb_file IS NULL "
        "AND active=1 AND is_archived=0 ORDER BY id"
    )
    rows = cur.fetchall()
    total = len(rows)
    print(f"Ke zpracovani: {total} produktu (quality={QUALITY})", flush=True)

    ok_count, fail_count, missing_count = 0, 0, 0
    failures = []
    missing = []
    t0 = time.time()

    for i, r in enumerate(rows, 1):
        pid = r["id"]
        matches = globmod.glob(os.path.join(PRODUCT_FBX_UPLOAD_DIR, f"{pid}.*"))
        if not matches:
            missing_count += 1
            missing.append({"id": pid, "sku": r["sku"], "name": r["name"], "fbx_original_name": r["fbx_original_name"]})
            print(f"[{i}/{total}] id={pid} SKIP - zdrojovy soubor na disku chybi", flush=True)
            continue

        ok, info, glb_name = convert_one(pid, matches[0])
        if ok:
            cur.execute("UPDATE shop_products SET glb_file=%s WHERE id=%s", (glb_name, pid))
            conn.commit()
            ok_count += 1
            print(f"[{i}/{total}] id={pid} OK -> {glb_name}", flush=True)
        else:
            fail_count += 1
            failures.append({"id": pid, "sku": r["sku"], "name": r["name"], "error": info.get("error")})
            print(f"[{i}/{total}] id={pid} SELHALO - {info.get('error')}", flush=True)

    elapsed = round(time.time() - t0, 1)
    summary = {
        "total": total, "ok": ok_count, "failed": fail_count, "missing_source_file": missing_count,
        "elapsed_sec": elapsed, "quality": QUALITY, "failures": failures, "missing": missing,
    }
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "backups",
        "2026-08-10_product_stp_to_glb_batch_summary.json",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nHOTOVO za {elapsed}s: OK={ok_count} SELHALO={fail_count} CHYBI_ZDROJ={missing_count} (souhrn: {out_path})", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
