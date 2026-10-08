#!/usr/bin/env python3
"""Prejmenovani rodiny karet 2.1.21.* (bot8, 2026-10-04, Robert: "Sroub imbus s valcovou hlavou M6x12 opraveno, nech nekdo prejmenovat ostatni v rodine").
Dogus ma rodinu 2.1.21.* jako sestihranne srouby (hex-head), karty ale Robert ma jako imbus s valcovou hlavou: M6x12 (id 4944) uz Robert opravil v adminu, zbytek (18 karet) dostane
stejny tvar nazvu: "Sroub se sestihrannou hlavou M<d>x<l>" -> "Sroub imbus s valcovou hlavou M<d>x<l>". Meni se JEN `name` (a adresa produktu pres product_slug.change_slug se 301 ze
stare - jediny mechanismus adres, viz api/product_slug.py), popis z Dogusu (kopie jejich textu) a Dogus pole se nemeni.
Bezpecnost: dry-run je vychozi; --zapsat zalohuje puvodni radky do backups/, UPDATE ma WHERE name=<puvodni> (rowcount musi byt 1), jedna transakce, audit_log radek ke kazde karte.
Spusteni: systemd-run --pipe --wait --working-directory=/opt/konfigurator --property=EnvironmentFile=/opt/konfigurator/api/.env api/venv/bin/python3 scripts/2026-10-04_prejmenovat_sroubu_2_1_21.py [--zapsat]"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "api"))
import pymysql  # noqa: E402
import product_slug  # noqa: E402

STARY = "Šroub se šestihrannou hlavou"
NOVY = "Šroub imbus s válcovou hlavou"


def main():
    zapsat = "--zapsat" in sys.argv
    c = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 3306)), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                        database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=False)
    cur = c.cursor()
    cur.execute("SELECT * FROM shop_products WHERE sku LIKE '2.1.21.%%' AND name LIKE %s ORDER BY sku", (STARY + " %",))
    radky = cur.fetchall()
    print(f"karet k prejmenovani: {len(radky)}")
    plan = [(r, r["name"].replace(STARY, NOVY, 1)) for r in radky]
    for r, novy in plan:
        print(f"  {r['id']} {r['sku']}: {r['name']!r} -> {novy!r}   (adresa {r['slug']})")
    if not zapsat:
        print("\n(dry-run: nic nezapsano; zapis: --zapsat)")
        return 0
    zaloha = os.path.join(REPO, "backups", "2026-10-04_prejmenovani_sroubu_2_1_21_pred.json")
    with open(zaloha, "w", encoding="utf-8") as f:
        json.dump([{k: (str(v) if v is not None and not isinstance(v, (int, float, str)) else v) for k, v in r.items()} for r in radky], f, ensure_ascii=False, indent=1)
    print("zaloha:", os.path.relpath(zaloha, REPO))
    n = 0
    try:
        for r, novy in plan:
            cur.execute("UPDATE shop_products SET name=%s WHERE id=%s AND name=%s", (novy, r["id"], r["name"]))
            if cur.rowcount != 1:
                raise RuntimeError(f"karta {r['id']}: UPDATE zmenil {cur.rowcount} radku (cekano 1) - vse vraceno")
            nova_adresa = product_slug.slug_for_name(cur, novy, exclude_id=r["id"])
            product_slug.change_slug(cur, r["id"], nova_adresa)
            cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'update','shop_product',%s,%s)",
                        (r["id"], f"bot8 skript 2026-10-04: prejmenovani rodiny 2.1.21 ({r['name']} -> {novy}), adresa -> {nova_adresa}"))
            n += 1
        c.commit()
    except Exception:
        c.rollback()
        raise
    print(f"COMMIT hotovy, prejmenovano {n} karet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
