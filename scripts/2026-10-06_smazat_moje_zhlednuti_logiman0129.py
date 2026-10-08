#!/opt/konfigurator/api/venv/bin/python
"""Robert 2026-10-06 (klik "Ano, smazat"): zhlednuti nabidky Logiman0129 (scene_offers.id 123) z IP 46.135.92.225 jsou jeho vlastni (22:59-23:36) a nemaji byt ve statistikach.
Smaze JEN radky scene_offer_views teto IP u teto nabidky + jejich scene_offer_page_events. Zaloha JSON v backups/ pred zapisem; pocty radku se kontroluji, nesedi-li, rollback.
Pouziti (z roota):  /opt/konfigurator/api/venv/bin/python3 /opt/konfigurator/scripts/2026-10-06_smazat_moje_zhlednuti_logiman0129.py [--apply]   (bez --apply = jen vypise)"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

OFFER_ID, OFFER_NUMBER, IP, OCEKAVANO = 123, "Logiman0129", "46.135.92.225", 7     # 6 v 23:36 + 1 v 23:41 (stejny prohlizec, pred zapnutim hlidani zamestnancu 23:42:42)
ZALOHA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups", "2026-10-06_moje_zhlednuti_logiman0129.json")


def main(argv):
    apply_ = "--apply" in argv
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT offer_number FROM scene_offers WHERE id=%s", (OFFER_ID,))
        o = cur.fetchone()
        if not o or o["offer_number"] != OFFER_NUMBER:
            print("ZASTAVENO: nabidka", OFFER_ID, "neni", OFFER_NUMBER, o)
            return 2
        cur.execute("SELECT * FROM scene_offer_views WHERE offer_id=%s AND ip_address=%s ORDER BY id", (OFFER_ID, IP))
        views = cur.fetchall()
        ids = [v["id"] for v in views]
        print(f"nalezeno zhlednuti z {IP} u {OFFER_NUMBER}: {len(ids)} (ocekavano {OCEKAVANO}), id {ids}")
        if len(ids) != OCEKAVANO:
            print("ZASTAVENO: pocet se lisi od ocekavaneho - nic nemazu")
            return 2
        fm = ",".join(["%s"] * len(ids))
        cur.execute(f"SELECT * FROM scene_offer_page_events WHERE view_id IN ({fm}) ORDER BY id", ids)
        events = cur.fetchall()
        print(f"jejich udalosti: {len(events)}")
        if not apply_:
            print("(nic nezapsano; spust s --apply)")
            return 0
        if os.path.exists(ZALOHA):
            print("ZASTAVENO: zaloha uz existuje", ZALOHA)
            return 2
        with open(ZALOHA, "w", encoding="utf-8") as f:
            json.dump({"views": views, "events": events}, f, ensure_ascii=False, indent=1, default=str)
        print("zaloha:", ZALOHA)
        n_ev = cur.execute(f"DELETE FROM scene_offer_page_events WHERE view_id IN ({fm})", ids)
        n_v = cur.execute(f"DELETE FROM scene_offer_views WHERE id IN ({fm}) AND offer_id=%s AND ip_address=%s", ids + [OFFER_ID, IP])
        if n_ev != len(events) or n_v != len(ids):
            conn.rollback()
            print(f"ZASTAVENO, rollback: smazano udalosti {n_ev}/{len(events)}, zhlednuti {n_v}/{len(ids)}")
            return 2
        conn.commit()
        print(f"SMAZANO: zhlednuti {n_v}, udalosti {n_ev}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
