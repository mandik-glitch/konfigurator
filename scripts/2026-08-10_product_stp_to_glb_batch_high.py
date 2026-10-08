"""
Precestovani VSECH produktu se zdrojovym STP/FBX na kvalitu "high"
(zadne filtrovani malych ploch, zadna decimace - viz
api/step_convert_worker.py QUALITY_PRESETS) - Robert 2026-08-10:
"nektere nejsou dobre, prevedme vsechny v plne kvalite z Step do Glb,
i kdyby meli zakomponovane logo Dogus" - navazuje na
2026-08-10_product_stp_to_glb_batch.py (ktery delal jen "medium" a jen
pro produkty bez existujiciho glb_file).

Na rozdil od puvodniho skriptu tenhle NENI idempotentni na "uz ma
glb_file" - preveden a PREPSAN je KAZDY aktivni, nearchivovany produkt
se zdrojovym STP/FBX, bez ohledu na to, jestli uz nejaky GLB ma (i tech
puvodnich 10, ktere mely GLB jeste pred timhle kolem).

Bezi PRIMO v api/ venv - spoustet jako:
  cd /opt/konfigurator/api && venv/bin/python3 ../scripts/2026-08-10_product_stp_to_glb_batch_high.py

POZOR: soubory vznikaji pod uzivatelem, kterym skript bezi - pokud se
spousti jako root (ne www-data, pod kterym bezi konfigurator.service),
je NUTNE po dobehnuti spustit
  find webapp/katalog -name "product_*.glb" -exec chown www-data:www-data {} +
jinak admin re-convert z UI selze PermissionError (viz AGENTS_LOG.md,
"fix opravneni souboru po davkove konverzi").
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
QUALITY = "high"


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
        "WHERE fbx_original_name IS NOT NULL AND active=1 AND is_archived=0 ORDER BY id"
    )
    rows = cur.fetchall()
    total = len(rows)
    print(f"Ke zpracovani: {total} produktu (quality={QUALITY}, force reconvert)", flush=True)

    ok_count, fail_count, missing_count = 0, 0, 0
    failures, missing = [], []
    t0 = time.time()

    for i, r in enumerate(rows, 1):
        pid = r["id"]
        matches = globmod.glob(os.path.join(PRODUCT_FBX_UPLOAD_DIR, f"{pid}.*"))
        if not matches:
            missing_count += 1
            missing.append({"id": pid, "sku": r["sku"], "name": r["name"]})
            print(f"[{i}/{total}] id={pid} SKIP - zdrojovy soubor chybi", flush=True)
            continue

        ok, info, glb_name = convert_one(pid, matches[0])
        if ok:
            cur.execute("UPDATE shop_products SET glb_file=%s WHERE id=%s", (glb_name, pid))
            conn.commit()
            ok_count += 1
            print(f"[{i}/{total}] id={pid} OK -> {glb_name} ({info.get('triangles_after_simplify')} tri)", flush=True)
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
        "2026-08-10_product_stp_to_glb_batch_high_summary.json",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nHOTOVO za {elapsed}s: OK={ok_count} SELHALO={fail_count} CHYBI_ZDROJ={missing_count} (souhrn: {out_path})", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
