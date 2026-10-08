"""
Backfill shop_orders.delivery_state / billing_state ze stavajiciho
`status` - bot18, 2026-09-04 (Robert pres bot3, bod 2/5 schvalenych
doporuceni z Dolibarr/ERPNext rozboru).

PRIPRAVA - NESPOUSTET (ani --dry-run pred aplikaci sql/2026-09-04_
shop_orders_delivery_billing_state.sql, ten musi bezet prvni) bez
vyslovneho "jdi na to" - viz TASKS.md/AGENTS_LOG.md.

Mapovani (overeno proti ZIVE distribuci statusu 2026-09-04, 39 objednavek
v 5 hodnotach - fakturovana 19, ceka_na_zbozi 8, expedovana 8,
pripravit 2, zrusena 2):
  nova / ceka_na_zbozi / potvrzena / pripravit / expedovana
      -> delivery_state = STEJNY retezec, billing_state = nevyfakturovano
  fakturovana
      -> delivery_state = expedovana (ALLOWED_TRANSITIONS: jedina cesta
         do fakturovana je z expedovana), billing_state = fakturovano
  zrusena
      -> delivery_state = NULL (ALLOWED_TRANSITIONS dokazuje, ze zrusena
         nejde dosahnout z expedovana/fakturovana - cancelled objednavka
         nikdy nedosla dal nez potvrzena/pripravit, a pripadny odectrny
         sklad uz byl vracen pri prechodu DO zrusena - viz
         api/orders.py komentar u STOCK_DEDUCTED_STATUSES), billing_state
         = nevyfakturovano (fakturovana nemuze prejit do zrusena,
         ALLOWED_TRANSITIONS["fakturovana"] = set())

Pouziti:
  systemd-run ... scripts/2026-09-04_shop_orders_state_backfill.py           (dry-run, jen vypis)
  systemd-run ... scripts/2026-09-04_shop_orders_state_backfill.py --apply   (skutecny zapis + overeni)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymysql

MAPPING = {
    "nova": ("nova", "nevyfakturovano"),
    "ceka_na_zbozi": ("ceka_na_zbozi", "nevyfakturovano"),
    "potvrzena": ("potvrzena", "nevyfakturovano"),
    "pripravit": ("pripravit", "nevyfakturovano"),
    "expedovana": ("expedovana", "nevyfakturovano"),
    "fakturovana": ("expedovana", "fakturovano"),
    "zrusena": (None, "nevyfakturovano"),
}


def get_conn():
    return pymysql.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="skutecne zapsat (bez tohohle jen dry-run)")
    ap.add_argument("--backup-file", default=None, help="kam ulozit zalohu pred zapisem (jen s --apply)")
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SHOW COLUMNS FROM shop_orders LIKE 'delivery_state'")
    if not cur.fetchone():
        print("CHYBA: sloupec delivery_state neexistuje - napřed spustit "
              "sql/2026-09-04_shop_orders_delivery_billing_state.sql", file=sys.stderr)
        sys.exit(1)

    cur.execute("SELECT id, order_number, status, delivery_state, billing_state FROM shop_orders ORDER BY id")
    rows = cur.fetchall()

    unknown = [r for r in rows if r["status"] not in MAPPING]
    if unknown:
        print("CHYBA: nalezeny neznamy status, mapovani neni uplne:", file=sys.stderr)
        for r in unknown:
            print(f"  id={r['id']} order_number={r['order_number']} status={r['status']!r}", file=sys.stderr)
        sys.exit(1)

    already_set = [r for r in rows if r["delivery_state"] is not None or r["billing_state"] != "nevyfakturovano"]
    to_change = []
    for r in rows:
        new_delivery, new_billing = MAPPING[r["status"]]
        if r["delivery_state"] != new_delivery or r["billing_state"] != new_billing:
            to_change.append((r, new_delivery, new_billing))

    print(f"celkem objednavek: {len(rows)}")
    print(f"jiz nastavene (nenulove) delivery/billing_state pred behem: {len(already_set)} "
          f"{'(NEOCEKAVANO na cistem behu - zkontroluj rucne)' if already_set else '(ocekavano 0 na prvnim behu)'}")
    print(f"ke zmene: {len(to_change)}")
    for r, nd, nb in to_change:
        print(f"  id={r['id']:4d} {r['order_number']:>10s}  status={r['status']:15s} -> "
              f"delivery_state={str(nd):15s} billing_state={nb}")

    if not args.apply:
        print("\nDRY-RUN - zadny zapis neproveden. Spust s --apply pro skutecnou aplikaci.")
        conn.close()
        return

    if not to_change:
        print("\nNic ke zmene, konec.")
        conn.close()
        return

    backup_path = args.backup_file or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backups", "2026-09-04_shop_orders_pred_state_backfill.json",
    )
    backup_rows = []
    for r in rows:
        backup_rows.append({
            "id": r["id"], "order_number": r["order_number"], "status": r["status"],
            "delivery_state": r["delivery_state"], "billing_state": r["billing_state"],
        })
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup_rows, f, ensure_ascii=False, indent=2)
    print(f"\nzaloha (status + puvodni delivery/billing_state vsech {len(rows)} objednavek) ulozena: {backup_path}")

    for r, nd, nb in to_change:
        cur.execute(
            "UPDATE shop_orders SET delivery_state=%s, billing_state=%s WHERE id=%s",
            (nd, nb, r["id"]),
        )
    conn.commit()
    print(f"zapsano {len(to_change)} radku, commit proveden.")
    conn.close()

    # Overeni CERSTVYM SELECTEM z NOVEHO spojeni - "zadna vyjimka" neni
    # dukaz zapisu (tokenova disciplina bod 8).
    conn2 = get_conn()
    cur2 = conn2.cursor()
    cur2.execute("SELECT id, order_number, status, delivery_state, billing_state FROM shop_orders ORDER BY id")
    fresh = cur2.fetchall()
    errors = []
    for r in fresh:
        exp_d, exp_b = MAPPING[r["status"]]
        if r["delivery_state"] != exp_d or r["billing_state"] != exp_b:
            errors.append(r)
    print(f"\nOVERENI (cerstve spojeni): {len(fresh)} objednavek zkontrolovano, "
          f"{len(errors)} nesedi s ocekavanym mapovanim.")
    for r in errors:
        print(f"  NESEDI: id={r['id']} status={r['status']} delivery_state={r['delivery_state']} billing_state={r['billing_state']}")
    if errors:
        sys.exit(2)
    conn2.close()


if __name__ == "__main__":
    main()
