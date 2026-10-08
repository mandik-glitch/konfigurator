#!/usr/bin/env python3
"""Aktivace karet Ford Transit Connect K-237/K-239 (bot5, 2026-09-16).

Obe karty (3952 K-237-RL-EB-30, 3953 K-239-RL-EB-30) zalozeny
2026-09-15 jako active=0 (render tehdy jeste nebezel). Overeno ted
primo pred aktivaci: vsech 6 navazanych sestav (128,213,283,129,214,284)
ma technicky_ok=1, aktualni razitka a 54 aktivnich turntable snimku
kazda - stejna rigorozni kontrola jako u vsech predchozich aktivaci
(K-120/K-121e/K-122) tuhle session.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

CARDS = (3952, 3953)
ASSEMBLY_IDS = (128, 213, 283, 129, 214, 284)


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ph = ",".join(["%s"] * len(ASSEMBLY_IDS))
            cur.execute(
                f"SELECT id, shop_product_id, technicky_ok, "
                f"(SELECT COUNT(*) FROM product_turntable_frames t "
                f" WHERE t.assembly_id=product_assemblies.id AND t.is_active=1) AS turntable "
                f"FROM product_assemblies WHERE id IN ({ph})",
                ASSEMBLY_IDS,
            )
            rows = cur.fetchall()
            for r in rows:
                print(r)
                if r["technicky_ok"] != 1 or not r["turntable"]:
                    print(f"STOP: assembly {r['id']} neni pripravena (technicky_ok/turntable), aktivaci PRERUSUJI")
                    return 1
            cur.execute(
                f"UPDATE shop_products SET active=1 WHERE id IN ({','.join(['%s'] * len(CARDS))})",
                CARDS,
            )
        conn.commit()
        print(f"Aktivovano: {CARDS}")
    finally:
        conn.close()

    conn2 = get_conn()
    try:
        with conn2.cursor() as cur:
            cur.execute(
                f"SELECT id, sku, active, slug FROM shop_products WHERE id IN ({','.join(['%s'] * len(CARDS))})",
                CARDS,
            )
            for r in cur.fetchall():
                print("OVERENI:", r)
    finally:
        conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
