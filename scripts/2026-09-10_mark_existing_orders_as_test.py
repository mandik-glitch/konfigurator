#!/usr/bin/env python3
"""Oznaci VSECHNY stavajici objednavky jako testovaci (WORKFLOW.md bod 27).

Robert 2026-09-10 pres bot3: "Ty stavajici objednavky oznac taky jako
testovaci" a k dotazu, jestli se maji smazat hned (vsechny jsou starsi
14 dnu, 19 z nich je fakturovanych s danovymi doklady), doslova:
"pravidlo je po 14ti dnech, jako testovaci jsme je oznacili dnes".

Proto se tady NEMAZE nic - jen se nastavi priznak a razitko
`test_marked_at = NOW()`, od ktereho teprve bezi 14denni lhuta uklidu.
Historie se tedy pri prvnim behu uklidu NESMAZE; smaze se az 14 dni po
oznaceni, a do te doby jde rozhodnuti kdykoli vzit zpet (is_test=0).

Idempotentni: objednavky, ktere uz priznak maji, se znovu nerazitkuji
(jinak by kazde spusteni posunulo lhutu a uklid by nikdy nedosel).
"""
import sys
import pymysql

sys.path.insert(0, "/opt/konfigurator/api")


def env(key):
    for line in open("/opt/konfigurator/api/.env", encoding="utf-8"):
        line = line.strip()
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise RuntimeError(f"{key} chybi v api/.env")


def main():
    conn = pymysql.connect(
        host=env("DB_HOST"), port=int(env("DB_PORT")), user=env("DB_USER"),
        password=env("DB_PASSWORD"), database=env("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM shop_orders WHERE is_test=1")
            uz_oznaceno = cur.fetchone()["n"]
            cur.execute(
                "SELECT id, order_number, status, created_at "
                "FROM shop_orders WHERE is_test=0 ORDER BY id"
            )
            k_oznaceni = cur.fetchall()

            if not k_oznaceni:
                print(f"Neni co oznacit (uz oznaceno: {uz_oznaceno}). Konec bez zmeny.")
                return

            print(f"Oznacuji {len(k_oznaceni)} objednavek (uz oznaceno drive: {uz_oznaceno}):")
            for r in k_oznaceni:
                print(f"  #{r['id']:>4} {r['order_number']:<20} {r['status']:<14} {r['created_at']}")

            cur.execute(
                "UPDATE shop_orders SET is_test=1, test_marked_at=NOW() WHERE is_test=0"
            )
            zmeneno = cur.rowcount
        conn.commit()
        print(f"\nOK - oznaceno {zmeneno} objednavek, lhuta uklidu bezi od ted.")
    finally:
        conn.close()

    # Overeni CERSTVYM spojenim (WORKFLOW.md bod 28 - "overit na skutecnem cili")
    conn2 = pymysql.connect(
        host=env("DB_HOST"), port=int(env("DB_PORT")), user=env("DB_USER"),
        password=env("DB_PASSWORD"), database=env("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn2.cursor() as cur:
            cur.execute(
                "SELECT is_test, COUNT(*) n, MIN(test_marked_at) od, MAX(test_marked_at) do "
                "FROM shop_orders GROUP BY is_test"
            )
            print("\nKontrola z noveho spojeni:")
            for r in cur.fetchall():
                print(f"  is_test={r['is_test']}: {r['n']} objednavek, "
                      f"test_marked_at {r['od']} .. {r['do']}")
            cur.execute(
                "SELECT COUNT(*) n FROM shop_orders "
                "WHERE is_test=1 AND test_marked_at < NOW() - INTERVAL 14 DAY"
            )
            print(f"  ke smazani pri dnesnim uklidu: {cur.fetchone()['n']} "
                  f"(ocekavano 0 - lhuta zacala dnes)")
    finally:
        conn2.close()


if __name__ == "__main__":
    main()
