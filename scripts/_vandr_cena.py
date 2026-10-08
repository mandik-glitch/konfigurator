"""Sdilena logika pro cenu Vandr sestav ze zdroje pravdy (vandrawee_work,
StoredModel::price() - viz /opt/vandrawee/web/app/Models/VanDraweeWork/
StoredModel.php:84). JEDNO misto, ktere sklada vzorec - pouziva ho jak
denni sync (scripts/2026-09-25_vandr_cena_sync.py), tak webhook prijimac
(api/vandr_price_webhook.py), aby nemohly zacit ukazovat jinou cenu.

Stejny import vzor jako scripts/razitkovac.py <- api/product_assemblies.py
(soubor v scripts/ zacinajici cislicí nejde primo importovat, tenhle
nazev NE - jde importovat normalne)."""
import os

VANDRAWEE_ENV_PATH = "/opt/vandrawee/web/.env"


def vandr_env():
    """Cte /opt/vandrawee/web/.env - NIKDY catem, rucni parse (stejny
    vzor jako scripts/_env.py::load_env)."""
    env = {}
    with open(VANDRAWEE_ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v.strip().strip("'").strip('"')
    return env


def vandr_conn():
    import pymysql
    env = vandr_env()
    return pymysql.connect(
        host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USERNAME"],
        password=env["DB_PASSWORD"], database=env["DB_VANDRAWEE_WORK_DATABASE"],
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )


def vsechny_ceny(vcur):
    """{uuid_str: cena_czk} pro VSECHNY stored_models - presne
    StoredModel::price() (soucet left/right/bulkhead_part.price,
    NULL-safe, chybejici cast = 0 prispevek)."""
    vcur.execute("""
        SELECT LOWER(CONCAT_WS('-', SUBSTR(HEX(sm.uuid),1,8), SUBSTR(HEX(sm.uuid),9,4),
               SUBSTR(HEX(sm.uuid),13,4), SUBSTR(HEX(sm.uuid),17,4), SUBSTR(HEX(sm.uuid),21,12))) AS uuid_str,
               COALESCE(lp.price, 0) + COALESCE(rp.price, 0) + COALESCE(bp.price, 0) AS cena
        FROM stored_models sm
        LEFT JOIN stored_model_parts lp ON lp.id = sm.left_part_id
        LEFT JOIN stored_model_parts rp ON rp.id = sm.right_part_id
        LEFT JOIN stored_model_parts bp ON bp.id = sm.bulkhead_part_id
    """)
    return {r["uuid_str"]: float(r["cena"]) for r in vcur.fetchall()}


def cena_pro_uuid(vcur, uuid_str):
    """Cena pro JEDNU sestavu (uuid jako dashed lowercase string), nebo
    None kdyz uuid v adminu neexistuje. Pro webhook (jedna karta), ne
    pro hromadny sync."""
    vcur.execute("""
        SELECT COALESCE(lp.price, 0) + COALESCE(rp.price, 0) + COALESCE(bp.price, 0) AS cena
        FROM stored_models sm
        LEFT JOIN stored_model_parts lp ON lp.id = sm.left_part_id
        LEFT JOIN stored_model_parts rp ON rp.id = sm.right_part_id
        LEFT JOIN stored_model_parts bp ON bp.id = sm.bulkhead_part_id
        WHERE sm.uuid = UNHEX(REPLACE(%s, '-', ''))
    """, (uuid_str,))
    r = vcur.fetchone()
    return float(r["cena"]) if r else None
