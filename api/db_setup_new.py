#!/usr/bin/env python3
"""
Vytvori tabulku cfg_dily v existujici DB (nrmmhhq65p) a naimportuje katalog
z catalog_manifest.json. Tabulka je prefixovana "cfg_", aby se nemichala
s tabulkami appky Sklad (ST_*, Warehouses, atd.) ve stejne databazi.

Pouziti (na serveru): python3 db_setup.py /cesta/k/katalog/catalog_manifest.json
"""
import sys, json, os
import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _env import load_env as _load_env

_cfg = _load_env()
DB_HOST = _cfg["DB_HOST"]
DB_PORT = int(_cfg.get("DB_PORT", 3306))
DB_USER = _cfg["DB_USER"]
DB_PASSWORD = _cfg["DB_PASSWORD"]
DB_NAME = _cfg["DB_NAME"]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cfg_dily (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    layer VARCHAR(64) NOT NULL,
    material_label VARCHAR(128),
    dim_x_mm DECIMAL(10,2),
    dim_y_mm DECIMAL(10,2),
    dim_z_mm DECIMAL(10,2),
    weight_kg_approx DECIMAL(10,4),
    density_kg_m3 DECIMAL(10,2),
    price_per_kg_czk_placeholder DECIMAL(10,2),
    price_czk_approx DECIMAL(10,2),
    volume_mm3 DECIMAL(14,1),
    volume_method VARCHAR(32),
    glb_file VARCHAR(255) NOT NULL,
    vertices INT,
    faces INT,
    watertight TINYINT(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

UPSERT_SQL = """
INSERT INTO cfg_dily (
    id, name, layer, material_label, dim_x_mm, dim_y_mm, dim_z_mm,
    weight_kg_approx, density_kg_m3, price_per_kg_czk_placeholder,
    price_czk_approx, volume_mm3, volume_method, glb_file, vertices, faces, watertight
) VALUES (
    %(id)s, %(name)s, %(layer)s, %(material_label)s, %(dim_x_mm)s, %(dim_y_mm)s, %(dim_z_mm)s,
    %(weight_kg_approx)s, %(density_kg_m3)s, %(price_per_kg_czk_placeholder)s,
    %(price_czk_approx)s, %(volume_mm3)s, %(volume_method)s, %(glb_file)s, %(vertices)s, %(faces)s, %(watertight)s
)
ON DUPLICATE KEY UPDATE
    name=VALUES(name), layer=VALUES(layer), material_label=VALUES(material_label),
    dim_x_mm=VALUES(dim_x_mm), dim_y_mm=VALUES(dim_y_mm), dim_z_mm=VALUES(dim_z_mm),
    weight_kg_approx=VALUES(weight_kg_approx), density_kg_m3=VALUES(density_kg_m3),
    price_per_kg_czk_placeholder=VALUES(price_per_kg_czk_placeholder),
    price_czk_approx=VALUES(price_czk_approx), volume_mm3=VALUES(volume_mm3),
    volume_method=VALUES(volume_method), glb_file=VALUES(glb_file),
    vertices=VALUES(vertices), faces=VALUES(faces), watertight=VALUES(watertight);
"""


def main():
    if len(sys.argv) < 2:
        print("Pouziti: python3 db_setup.py catalog_manifest.json")
        sys.exit(1)

    manifest_path = sys.argv[1]
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    parts = data["parts"]

    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4", autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            n = 0
            for p in parts:
                dims = p["dims_mm"]
                row = {
                    "id": p["id"],
                    "name": p["name"],
                    "layer": p["layer"],
                    "material_label": p.get("material_label"),
                    "dim_x_mm": dims[0], "dim_y_mm": dims[1], "dim_z_mm": dims[2],
                    "weight_kg_approx": p.get("weight_kg_approx"),
                    "density_kg_m3": p.get("density_kg_m3"),
                    "price_per_kg_czk_placeholder": p.get("price_per_kg_czk_placeholder"),
                    "price_czk_approx": p.get("price_czk_approx_PLACEHOLDER"),
                    "volume_mm3": p.get("volume_mm3"),
                    "volume_method": p.get("volume_method"),
                    "glb_file": p["file"],
                    "vertices": p.get("vertices"),
                    "faces": p.get("faces"),
                    "watertight": 1 if p.get("watertight") else 0,
                }
                cur.execute(UPSERT_SQL, row)
                n += 1
        conn.commit()
        print(f"Hotovo: {n} dilu nahrano/aktualizovano v tabulce cfg_dily.")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cfg_dily;")
            print("Radku v cfg_dily celkem:", cur.fetchone()[0])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
