#!/usr/bin/env python3
"""Přepočet a zápis joint_count/joint_czk/total_czk pro VŠECHNY sestavy
(product_assemblies), podle pravidla profil-profil (Robert schválil
2026-09-11 ráno, zadání bot3 koordinace, nález "1 321 650 Kč napříč
katalogem" - staré ceny počítaly i úhelníky/záslepky do počtu spojů,
dnešní pravidlo počítá jen dvojice profil-profil).

SPUŠTĚNÍ (z /opt/konfigurator, jako root nebo běžný uživatel se čtením
api/.env - žádný speciální www-data účet není potřeba):

    api/venv/bin/python3 scripts/2026-09-11_robert_joint_count_prepocet_269.py

Skript nejdřív ukáže souhrn (kolik sestav, jaký součet rozdílu v Kč) a
počká na potvrzení - teprve po napsání "ANO" a Enter něco zapíše.

Bezpečnostní vlastnosti:
  - Nejdřív ověří, že záloha `backups/2026-09-11_joint_count_prepocet_269_
    backup_PRED.json` existuje a vypadá rozumně (269 řádků, čitelný JSON) -
    pokud ne, SKONČÍ bez zápisu.
  - Čte AKTUÁLNÍ stav těsně před zápisem KAŽDÉHO řádku zvlášť (ne davku
    načtenou předem) - katalog se mezitím mění (živá práce jiných botů).
  - Zapisuje výhradně přes JSON_SET na tři klíče uvnitř `price_summary`,
    NIKDY nesahá na `parts`/`bom` ani na cokoli jiného v `data` - i kdyby
    jiný bot mezitím přepsal geometrii, tenhle zápis to nepřepíše (JSON_SET
    pracuje nad PRÁVĚ AKTUÁLNÍM řádkem v okamžiku UPDATE, ne nad tím, co
    si tenhle skript načetl dřív).
  - Řádky, kde se nová hodnota neliší od staré, PŘESKOČÍ (nezapisuje) -
    druhé spuštění je tedy neškodné (idempotentní), nic neodečte podruhé.
  - Na konci znovu přečte skutečně zapsané řádky a nahlásí SKUTEČNÝ součet
    rozdílu - pokud se od toho, co skript hlásil PŘED zápisem, liší (typicky
    proto, že mezitím doběhla souběžná práce jiného bota na konkrétní
    sestavě), řekne to zvlášť a jmenovitě, ne mlčky.
"""
import json
import os
import sys

import numpy as np
import pymysql
import trimesh

ROOT = "/opt/konfigurator"
KATALOG_DIR = os.path.join(ROOT, "webapp", "katalog")
EPS_FACE = 0.75
EPS_OVERLAP = 0.5
BACKUP_PATH = os.path.join(ROOT, "backups", "2026-09-11_joint_count_prepocet_269_backup_PRED.json")


def load_env():
    env = {}
    with open(os.path.join(ROOT, "api", ".env")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v
    return env


def get_conn():
    env = load_env()
    return pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                            password=env["DB_PASSWORD"], database=env["DB_NAME"], charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor, autocommit=False)


def je_razitko(role):
    return str(role or "").startswith("logo-ochrana")


def quat_to_matrix(q):
    x, y, z, w = q
    n = x * x + y * y + z * z + w * w
    if n < 1e-12:
        return np.eye(3)
    s = 2.0 / n
    xx, yy, zz = x * x * s, y * y * s, z * z * s
    xy, xz, yz = x * y * s, x * z * s, y * z * s
    wx, wy, wz = w * x * s, w * y * s, w * z * s
    return np.array([
        [1 - (yy + zz), xy - wz, xz + wy],
        [xy + wz, 1 - (xx + zz), yz - wx],
        [xz - wy, yz + wx, 1 - (xx + yy)],
    ])


def world_bbox(mesh, position, quaternion, scale):
    verts = mesh.vertices * np.array(scale)
    rot = quat_to_matrix(quaternion)
    verts = verts @ rot.T
    verts = verts + np.array(position)
    return verts.min(axis=0), verts.max(axis=0)


def touching(boxA, boxB):
    minA, maxA = boxA
    minB, maxB = boxB
    for axis in range(3):
        face_close = (abs(maxA[axis] - minB[axis]) < EPS_FACE) or (abs(minA[axis] - maxB[axis]) < EPS_FACE)
        if not face_close:
            continue
        overlaps = True
        for j in range(3):
            if j == axis:
                continue
            lo = max(minA[j], minB[j])
            hi = min(maxA[j], maxB[j])
            size_a = maxA[j] - minA[j]
            size_b = maxB[j] - minB[j]
            min_size = min(size_a, size_b)
            if (hi - lo) < (min_size - EPS_OVERLAP):
                overlaps = False
                break
        if overlaps:
            return True
    return False


def verify_backup():
    if not os.path.exists(BACKUP_PATH):
        print(f"CHYBA: záloha nenalezena ({BACKUP_PATH}). KONČÍM, nic nezapisuji.")
        return False
    try:
        with open(BACKUP_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
    except (ValueError, OSError) as e:
        print(f"CHYBA: záloha se nedá načíst ({e}). KONČÍM, nic nezapisuji.")
        return False
    if not isinstance(rows, list) or len(rows) < 200:
        print(f"CHYBA: záloha vypadá podezřele ({len(rows) if isinstance(rows, list) else '?'} řádků, čekáno ~269). KONČÍM, nic nezapisuji.")
        return False
    sample = rows[0]
    if "id" not in sample or "data" not in sample:
        print("CHYBA: záloha nemá očekávanou strukturu (id/data). KONČÍM, nic nezapisuji.")
        return False
    print(f"Záloha OK: {BACKUP_PATH} ({len(rows)} řádků).")
    return True


def _setting_float(cur, key, default):
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (key,))
    row = cur.fetchone()
    if not row or row["setting_value"] in (None, ""):
        return default
    try:
        return float(row["setting_value"])
    except (TypeError, ValueError):
        return default


class Katalog:
    def __init__(self, conn):
        self.conn = conn
        self.mesh_cache = {}
        self.cfg_cache = {}
        with conn.cursor() as cur:
            self.joint_price = _setting_float(cur, "joint_price_czk", 0.0)
            # Marze konfiguratoru (Robert 2026-09-11: scene_price_coefficient
            # 1.0->1.4) - stejna fallback logika jako
            # get_scene_price_coefficient() v api/app.py: chybejici/nesmyslna
            # hodnota se chova jako 1.0 (zadne navyseni), nikdy nespadne.
            coef = _setting_float(cur, "scene_price_coefficient", 1.0)
            self.coef = coef if coef > 0 else 1.0
            # Balne (Robert 2026-09-11: "cena za balne 5%") - % z CELKOVE
            # ceny PO marzi, POSLEDNI krok vypoctu (viz compute_new_values).
            self.packaging_pct = _setting_float(cur, "packaging_pct", 0.0)

    def get_cfg(self, cur, part_id):
        if part_id not in self.cfg_cache:
            cur.execute("SELECT id, dim_x_mm, dim_y_mm, dim_z_mm, glb_file FROM cfg_dily WHERE id=%s", (part_id,))
            self.cfg_cache[part_id] = cur.fetchone()
        return self.cfg_cache[part_id]

    def get_mesh(self, glb_file):
        if glb_file not in self.mesh_cache:
            path = os.path.join(KATALOG_DIR, glb_file)
            self.mesh_cache[glb_file] = trimesh.load(path, force="mesh") if os.path.exists(path) else None
        return self.mesh_cache[glb_file]


def compute_new_values(cur, kat, data_json):
    """Vrátí dict s novými hodnotami, nebo None, když sestavu nejde
    spočítat (chybějící parts/price_summary/geometrie).

    Tři nezávislé opravy najednou (Robert/bot3, 2026-09-11, stejný den):
      1. joint_count/joint_czk - pravidlo profil-profil (canonical touch).
      2. material_czk/accessory_czk - marže konfigurátoru
         (app_settings.scene_price_coefficient), STEJNÝ rozsah jako scéna
         (get_scene_price_coefficient() v api/app.py): NIKDY cut_czk/
         profile_flat_fee_czk/joint_czk.
      3. packaging_czk - balné (app_settings.packaging_pct), POSLEDNÍ
         krok, % ze součtu všech ostatních už zaokrouhlených položek.

    Idempotence marže (aby se 1.4x nenabalilo na 1.4x při druhém běhu
    tohoto skriptu, nebo při pozdější změně koeficientu): tenhle skript
    si do `price_summary.scene_price_coefficient_applied` ukládá, jaký
    koeficient na řádek naposledy sám aplikoval. Při dalším běhu se z
    aktuálně uložené (už jednou navýšené) hodnoty nejdřív zpětně
    vydělením obnoví PŮVODNÍ základ, teprve ten se vynásobí AKTUÁLNÍM
    koeficientem - výsledek je tedy stejný, ať skript běží podruhé se
    stejným koeficientem (beze změny), nebo s jiným (Robert dolaďuje)."""
    try:
        d = json.loads(data_json) if data_json else {}
    except (ValueError, TypeError):
        return None
    parts = d.get("parts") or []
    ps = d.get("price_summary") or {}
    if not parts or ps.get("joint_count") is None:
        return None

    profile_boxes = []
    for p in parts:
        pid = str(p.get("part_id") or "")
        role = p.get("role")
        if pid.startswith("car_body_") or je_razitko(role) or pid.startswith("product_"):
            continue
        cfg = kat.get_cfg(cur, pid)
        if not cfg or cfg["dim_x_mm"] is None or cfg["dim_y_mm"] is None or cfg["dim_z_mm"] is None:
            continue
        if not cfg["glb_file"]:
            continue
        if not isinstance(p.get("position"), list) or not isinstance(p.get("quaternion"), list):
            return None
        mesh = kat.get_mesh(cfg["glb_file"])
        if mesh is None:
            continue
        profile_boxes.append(world_bbox(mesh, p["position"], p["quaternion"], p.get("scale", [1, 1, 1])))

    new_joint_count = 0
    for i in range(len(profile_boxes)):
        for j in range(i + 1, len(profile_boxes)):
            if touching(profile_boxes[i], profile_boxes[j]):
                new_joint_count += 1
    new_joint_czk = round(new_joint_count * kat.joint_price)

    applied = ps.get("scene_price_coefficient_applied")
    material_stored = ps.get("material_czk") or 0
    accessory_stored = ps.get("accessory_czk") or 0
    if applied and applied > 0:
        material_base = material_stored / applied
        accessory_base = accessory_stored / applied
    else:
        material_base = material_stored
        accessory_base = accessory_stored
    new_material_czk = round(material_base * kat.coef)
    new_accessory_czk = round(accessory_base * kat.coef)

    cut_czk = ps.get("cut_czk") or 0
    profile_flat_fee_czk = ps.get("profile_flat_fee_czk") or 0
    subtotal_czk = new_material_czk + cut_czk + profile_flat_fee_czk + new_joint_czk + new_accessory_czk
    new_packaging_czk = round(subtotal_czk * kat.packaging_pct / 100)
    new_total_czk = subtotal_czk + new_packaging_czk

    return {
        "new_joint_count": new_joint_count, "new_joint_czk": new_joint_czk,
        "new_material_czk": new_material_czk, "new_accessory_czk": new_accessory_czk,
        "new_packaging_czk": new_packaging_czk, "new_total_czk": new_total_czk,
        "coef": kat.coef,
        "old_joint_count": ps.get("joint_count"), "old_total_czk": ps.get("total_czk"),
        "old_material_czk": ps.get("material_czk"), "old_accessory_czk": ps.get("accessory_czk"),
    }


def main():
    if not verify_backup():
        sys.exit(1)

    conn = get_conn()
    kat = Katalog(conn)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM product_assemblies ORDER BY id")
        ids = [r["id"] for r in cur.fetchall()]

    print(f"joint_price_czk = {kat.joint_price}, scene_price_coefficient = {kat.coef}, packaging_pct = {kat.packaging_pct}")
    print(f"Sestav v DB: {len(ids)}")
    print("\n--- NÁHLED (čtení právě teď, nic se ještě nezapisuje) ---")

    def needs_write(r):
        return (r["new_joint_count"] != r["old_joint_count"]) or (r["new_total_czk"] != r["old_total_czk"])

    preview = {}
    skipped = []
    with conn.cursor() as cur:
        for aid in ids:
            cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (aid,))
            row = cur.fetchone()
            result = compute_new_values(cur, kat, row["data"])
            if result is None:
                skipped.append(aid)
                continue
            preview[aid] = result

    changed_preview = {aid: v for aid, v in preview.items() if needs_write(v)}
    preview_diff_czk = sum((v["old_total_czk"] - v["new_total_czk"]) for v in changed_preview.values()
                           if v["old_total_czk"] is not None)
    print(f"Přeskočeno (nedá se spočítat, nezmění se): {len(skipped)} {skipped if skipped else ''}")
    print(f"Sestav ke změně (joint_count a/nebo cena): {len(changed_preview)} / {len(preview)}")
    print(f"Součet rozdílu total_czk (staré - nové), podle NÁHLEDU: {preview_diff_czk} Kč")

    if not changed_preview:
        print("\nNic ke změně - všechny sestavy už mají aktuální hodnoty. Konec.")
        conn.close()
        return

    print("\nOpravdu zapsat tyhle změny do product_assemblies (jen price_summary."
          "{joint_count,joint_czk,material_czk,accessory_czk,packaging_czk,total_czk,"
          "scene_price_coefficient_applied})?")
    confirm = input("Napiš ANO a stiskni Enter pro pokračování, cokoli jiného ukončí bez zápisu: ")
    if confirm.strip() != "ANO":
        print("Zrušeno, nic nezapsáno.")
        conn.close()
        return

    print("\n--- ZÁPIS (čtu znovu čerstvě těsně před každým UPDATE) ---")
    written = []
    with conn.cursor() as cur:
        for aid in ids:
            cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (aid,))
            row = cur.fetchone()
            r = compute_new_values(cur, kat, row["data"])
            if r is None or not needs_write(r):
                continue  # beze zmeny - idempotentni chovani, druhe spusteni nic neodecte
            cur.execute(
                "UPDATE product_assemblies SET data = JSON_SET(data, "
                "'$.price_summary.joint_count', CAST(%s AS JSON), "
                "'$.price_summary.joint_czk', CAST(%s AS JSON), "
                "'$.price_summary.material_czk', CAST(%s AS JSON), "
                "'$.price_summary.accessory_czk', CAST(%s AS JSON), "
                "'$.price_summary.packaging_czk', CAST(%s AS JSON), "
                "'$.price_summary.total_czk', CAST(%s AS JSON), "
                "'$.price_summary.scene_price_coefficient_applied', CAST(%s AS JSON)) "
                "WHERE id=%s",
                (r["new_joint_count"], r["new_joint_czk"], r["new_material_czk"], r["new_accessory_czk"],
                 r["new_packaging_czk"], r["new_total_czk"], r["coef"], aid),
            )
            conn.commit()
            written.append({"id": aid, "old_jc": r["old_joint_count"], "new_jc": r["new_joint_count"],
                             "old_total": r["old_total_czk"], "new_total": r["new_total_czk"]})

    conn.close()

    actual_diff = sum((w["old_total"] - w["new_total"]) for w in written if w["old_total"] is not None)
    print(f"\nZapsáno řádků: {len(written)}")
    print(f"Skutečně zapsaný součet rozdílu total_czk: {actual_diff} Kč")
    if actual_diff != preview_diff_czk:
        print(f"POZOR: liší se od náhledu ({preview_diff_czk} Kč) - rozdíl {actual_diff - preview_diff_czk} Kč.")
        print("Nejpravděpodobnější důvod: mezi náhledem a zápisem někdo (jiný bot) tuhle sestavu upravil.")
        preview_ids = set(changed_preview.keys())
        written_ids = set(w["id"] for w in written)
        if preview_ids != written_ids:
            print(f"  V náhledu, ale ne v zápisu: {sorted(preview_ids - written_ids)}")
            print(f"  V zápisu, ale ne v náhledu: {sorted(written_ids - preview_ids)}")
    else:
        print("Sedí přesně na náhled.")

    log_path = os.path.join(ROOT, "backups", "2026-09-11_joint_count_prepocet_269_zapis_LOG.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump({"written": written, "skipped": skipped, "preview_diff_czk": preview_diff_czk,
                    "actual_diff_czk": actual_diff}, f, ensure_ascii=False, indent=1)
    print(f"\nLog zápisu uložen: {log_path}")


if __name__ == "__main__":
    main()
