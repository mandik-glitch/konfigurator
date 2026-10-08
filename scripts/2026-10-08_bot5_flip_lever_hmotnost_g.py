#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Opravi jednotku hmotnosti v popisu 8 aktivnich karet Flip Lever / Vyklopna paka (bot5, 2026-10-08; nalez bot7 pri prekladu): zdroj Dogus ma 'Weight (kg)' = 23, 55, 40 ... u plastove packy (16-69),
popis rikal 'hmotnost cca 23 kg'. Plastova packa nemuze vazit 23 kg - jde o gramy. Mění se JEN veta 'hmotnost cca N kg' -> 'hmotnost cca N g' ve sloupcich textu tech 8 karet; zaloha puvodnich textu
do backups/2026-10-08_flip_lever_hmotnost_pred.json PRED zapisem; hodnota weight_g (None) a product_specs_json se nemeni.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_bot5_flip_lever_hmotnost_g.py [--apply]"""
import json
import os
import re
import sys

import pymysql

IDS = (3277, 3281, 3289, 3290, 3291, 3301, 3306, 3307)
VZOR = re.compile(r"hmotnost cca (\d+(?:[.,]\d+)?) kg", re.I)
ZALOHA = "/opt/konfigurator/backups/2026-10-08_flip_lever_hmotnost_pred.json"


def main():
    apply = "--apply" in sys.argv
    c = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", "3306")), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    cur = c.cursor()
    cur.execute("SELECT COLUMN_NAME n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_products' AND DATA_TYPE IN ('varchar','text','mediumtext','longtext')")
    sloupce = [r["n"] for r in cur.fetchall() if r["n"] != "product_specs_json"]
    cur.execute("SELECT id, name, " + ", ".join("`%s`" % s for s in sloupce) + " FROM shop_products WHERE id IN (%s) ORDER BY id" % ",".join(str(i) for i in IDS))
    radky = cur.fetchall()
    zmeny, zaloha = [], {}
    for r in radky:
        for s in sloupce:
            t = r.get(s)
            if isinstance(t, str) and VZOR.search(t):
                zmeny.append((r["id"], s, VZOR.search(t).group(0), VZOR.sub(lambda m: "hmotnost cca %s g" % m.group(1), t)))
                zaloha.setdefault(str(r["id"]), {})[s] = t
    print("karet:", len(radky), "| zmen:", len(zmeny))
    for i, s, stary, _ in zmeny:
        print("  #%s %s: %r -> g" % (i, s, stary))
    if not apply:
        print("(nic se nezapsalo; --apply zapise)")
        return
    os.makedirs(os.path.dirname(ZALOHA), exist_ok=True)
    json.dump(zaloha, open(ZALOHA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for i, s, _, novy in zmeny:
        cur.execute("UPDATE shop_products SET `%s`=%%s WHERE id=%%s" % s, (novy, i))
    c.commit()
    print("zapsano, zaloha:", ZALOHA)


if __name__ == "__main__":
    main()
