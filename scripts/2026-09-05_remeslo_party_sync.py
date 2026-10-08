#!/usr/bin/env python3
"""Party model, faze 5 - most k Remeslu (bot18, 2026-09-05, Robert pres
bot3). Jednosmerny, idempotentni sync `remeslo_craftsmen.party_id`
(DB "Remeslnik") z `app_users.party_id` (hlavni DB) - stejny princip
jako uz existujici precedens /opt/toscanaccio/scripts/sync_admin_
from_konfigurator.py (jednosmerny upsert, zadna cross-DB transakce).

ZADNA NOVA HEURISTIKA SHODY POTREBA - remeslo_craftsmen.app_user_id uz
dnes jednoznacne urcuje, ktery app_users radek (a tedy i ktera party)
tenhle remeslnik je. Skript jen precte hodnotu z jedne DB a zapise do
druhe - zadne dohadovani, zadne fuzzy e-mail/jmeno matchovani.

Bezpecne spustit opakovane (idempotentni) - hodi se jako periodicky
job (vzor scripts/2026-08-20_remeslo_*.py timer), ale zatim se
NEINSTALUJE zadny systemd timer (stejna disciplina jako u dosud
neinstalovaneho price-refresh timeru - o instalaci na sdilenou infru
rozhoduje Robert/bot3).

Pouziti:
  scripts/2026-09-05_remeslo_party_sync.py            (dry-run)
  scripts/2026-09-05_remeslo_party_sync.py --apply    (skutecny zapis)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import pymysql


def get_main_conn():
    return pymysql.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_remeslo_conn():
    return pymysql.connect(
        host=os.environ["REMESLO_DB_HOST"], port=int(os.environ["REMESLO_DB_PORT"]),
        user=os.environ["REMESLO_DB_USER"], password=os.environ["REMESLO_DB_PASSWORD"],
        database=os.environ["REMESLO_DB_NAME"], charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rconn = get_remeslo_conn()
    rcur = rconn.cursor()
    rcur.execute(
        "SELECT id, app_user_id, party_id FROM remeslo_craftsmen WHERE app_user_id IS NOT NULL"
    )
    craftsmen = rcur.fetchall()
    print(f"remeslo_craftsmen s app_user_id: {len(craftsmen)}")

    if not craftsmen:
        print("nic k synchronizaci.")
        return

    mconn = get_main_conn()
    mcur = mconn.cursor()
    app_user_ids = [c["app_user_id"] for c in craftsmen]
    fmt = ",".join(["%s"] * len(app_user_ids))
    mcur.execute(f"SELECT id, party_id FROM app_users WHERE id IN ({fmt})", app_user_ids)
    party_by_user = {r["id"]: r["party_id"] for r in mcur.fetchall()}
    mconn.close()

    changes = []
    for c in craftsmen:
        target_party_id = party_by_user.get(c["app_user_id"])
        if target_party_id is None:
            continue  # app_users radek jeste nema party_id (necekana situace, precestat rucne)
        if c["party_id"] != target_party_id:
            changes.append((c["id"], c["app_user_id"], c["party_id"], target_party_id))

    print(f"ke zmene: {len(changes)}")
    for craftsman_id, app_user_id, old, new in changes:
        print(f"  remeslo_craftsmen.id={craftsman_id} app_user_id={app_user_id}: party_id {old} -> {new}")

    if not args.apply:
        print("\nDRY-RUN - zadny zapis.")
        rconn.close()
        return

    if not changes:
        print("\nNic ke zmene.")
        rconn.close()
        return

    for craftsman_id, _, _, new in changes:
        rcur.execute("UPDATE remeslo_craftsmen SET party_id=%s WHERE id=%s", (new, craftsman_id))
    rconn.commit()
    print(f"\nzapsano {len(changes)} radku, commit proveden.")
    rconn.close()

    # Overeni cerstvym SELECTEM z NOVEHO spojeni.
    rconn2 = get_remeslo_conn()
    rcur2 = rconn2.cursor()
    errors = 0
    for craftsman_id, _, _, expected in changes:
        rcur2.execute("SELECT party_id FROM remeslo_craftsmen WHERE id=%s", (craftsman_id,))
        actual = rcur2.fetchone()["party_id"]
        if actual != expected:
            errors += 1
            print(f"NESEDI: id={craftsman_id} ocekavano={expected} skutecnost={actual}")
    print(f"\nOVERENI (cerstve spojeni): {len(changes)} zmen zkontrolovano, {errors} nesedi.")
    rconn2.close()
    if errors:
        sys.exit(2)


if __name__ == "__main__":
    main()
