#!/usr/bin/env python3
"""Doplneni strukturovane vety o rozmerech (Vyska zadniho nakladaciho
otvoru + bocni dvere) do car_storefront_models.variant_description na
Doblo SUBDOMENE (storefront_id=11, doblo.fiat-autovestavby.top) - ta
vetu uz ma STANDALONE domena (storefront_id=14, fiat-doblo-vestavby.top)
pro STEJNE car_model_id radky (zdroj pravdy, jen chybi zrcadlit).

Kontext: Robert si vsiml, ze standalone domena "ma tabulku rozmeru",
subdomena ne - diagnoza (bot18, 2026-09-05) potvrdila, ze je to CISTE
obsahovy rozdil (obe domeny jedou přes stejnou _storefront_page_response,
zadny kod/sablona se nelisi). Schvaleno bot3 pro Doblo+Ducato; tenhle
skript resi jen Doblo (Ducato ma jinou nuanci - existujici prosa uz
vetsinou vysku otvoru zminuje jinymi slovy, viz zprava bot3).

Zpusob: pro kazdy z 6 car_model_id spolecnych obema Doblo storefrontum
se k EXISTUJICIMU obsahu subdomeny PRIDA (ne prepise) nova <p> se
STEJNOU vetou, jakou uz ma standalone (zkopirovano 1:1, zadna nova
cisla, jen zrcadleni jiz publikovaneho textu).

Pouziti:
  scripts/2026-09-05_doblo_subdomain_dims_backfill.py            (dry-run)
  scripts/2026-09-05_doblo_subdomain_dims_backfill.py --apply    (skutecny zapis)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import pymysql

SUBDOMAIN_ID = 11
STANDALONE_ID = 14


def get_conn():
    return pymysql.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT car_model_id, variant_description FROM car_storefront_models WHERE storefront_id=%s",
        (STANDALONE_ID,),
    )
    standalone = {r["car_model_id"]: r["variant_description"] for r in cur.fetchall()}

    cur.execute(
        "SELECT car_model_id, variant_description FROM car_storefront_models WHERE storefront_id=%s",
        (SUBDOMAIN_ID,),
    )
    sub_rows = cur.fetchall()

    backup = []
    changes = []
    for r in sub_rows:
        cmid = r["car_model_id"]
        old = r["variant_description"] or ""
        dims_sentence = standalone.get(cmid)
        if not dims_sentence:
            print(f"CHYBA: car_model_id={cmid} nema protejsek na standalone - preskakuji", file=sys.stderr)
            continue
        if dims_sentence in old:
            print(f"car_model_id={cmid}: standalone veta uz je obsazena v subdomene, preskakuji")
            continue
        new = f"{old}<p>{dims_sentence}</p>"
        backup.append({"car_model_id": cmid, "variant_description": old})
        changes.append((cmid, old, new))

    print(f"ke zmene: {len(changes)} z {len(sub_rows)} radku")
    for cmid, old, new in changes:
        print(f"  car_model_id={cmid}")
        print(f"    PRED: {old[:80]}...")
        print(f"    PO:   ...{new[-140:]}")

    if not args.apply:
        print("\nDRY-RUN - zadny zapis.")
        conn.close()
        return

    if not changes:
        print("\nNic ke zmene.")
        conn.close()
        return

    backup_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backups", "2026-09-05_doblo_subdomain_variant_description_pred_backfill.json",
    )
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    print(f"\nzaloha ulozena: {backup_path}")

    for cmid, old, new in changes:
        cur.execute(
            "UPDATE car_storefront_models SET variant_description=%s WHERE storefront_id=%s AND car_model_id=%s",
            (new, SUBDOMAIN_ID, cmid),
        )
    conn.commit()
    print(f"zapsano {len(changes)} radku, commit proveden.")
    conn.close()

    # Overeni cerstvym SELECTem z NOVEHO spojeni.
    conn2 = get_conn()
    cur2 = conn2.cursor()
    cur2.execute(
        "SELECT car_model_id, variant_description FROM car_storefront_models WHERE storefront_id=%s",
        (SUBDOMAIN_ID,),
    )
    fresh = {r["car_model_id"]: r["variant_description"] for r in cur2.fetchall()}
    errors = 0
    for cmid, old, new in changes:
        if fresh.get(cmid) != new:
            errors += 1
            print(f"NESEDI: car_model_id={cmid}")
    print(f"\nOVERENI (cerstve spojeni): {len(changes)} zmen zkontrolovano, {errors} nesedi.")
    conn2.close()
    if errors:
        sys.exit(2)


if __name__ == "__main__":
    main()
