#!/usr/bin/env python3
"""Zpetne doplneni polozek do jiz existujici objednavky OBJ-2026-00187
(bot5, 2026-09-16, Robert primo: "propiš mi ty díly i do stávající
obj[ednávky]") - vznikla z nabidky Logiman0109 (offer id=103) jeste
PRED opravou create_order_from_scene_offer() (commit 0af404fc), takze
nema zadne shop_order_items.

Stejna mapovaci logika jako oprava sama - jen aplikovana rucne na uz
existujici objednavku misto v ramci prijeti nove. qty_multiplier=3
overen primo ze scene_offer_order_prefs (guest_id 2a871b3b..., IP
178.22.113.55 - shoduje se s IP v scene_offer_acceptances, tedy
skutecny zakaznik, ne Robertuv vlastni drivejsi test s qty=1).

Zaloha do backups/, idempotentni (pri druhem spusteni s jiz
existujicimi polozkami preskoci).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-16_bot5_backfill_polozky_obj187",
)
ORDER_NUMBER = "OBJ-2026-00187"
QTY_MULTIPLIER = 3

_DIM_MM_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*mm$")


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, source_scene_offer_id FROM shop_orders WHERE order_number=%s", (ORDER_NUMBER,))
            order = cur.fetchone()
            if not order:
                print(f"CHYBA: objednavka {ORDER_NUMBER} neexistuje"); return 1
            order_id = order["id"]

            cur.execute("SELECT COUNT(*) AS c FROM shop_order_items WHERE order_id=%s", (order_id,))
            if cur.fetchone()["c"]:
                print(f"Objednavka {ORDER_NUMBER} uz polozky ma, nic nedelam (idempotence)."); return 0

            cur.execute("SELECT items FROM scene_offers WHERE id=%s", (order["source_scene_offer_id"],))
            offer_row = cur.fetchone()
            items = json.loads(offer_row["items"] or "[]")

            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump({"order_id": order_id, "order_number": ORDER_NUMBER,
                           "offer_id": order["source_scene_offer_id"], "items": items,
                           "qty_multiplier": QTY_MULTIPLIER}, f, ensure_ascii=False, indent=2)

            zapsano = 0
            for it in items:
                if not isinstance(it, dict) or not it.get("name"):
                    continue
                qty_raw = str(it.get("qty") or "1")
                m = re.match(r"\d+", qty_raw)
                qty = (int(m.group()) if m else 1) * QTY_MULTIPLIER
                unit_price = float(it.get("unit_price") or 0)
                line_total = float(it.get("total") or 0) * QTY_MULTIPLIER
                dim_match = _DIM_MM_RE.match(str(it.get("dim") or "").strip())
                length_mm = float(dim_match.group(1).replace(",", ".")) if dim_match else None
                cur.execute(
                    "INSERT INTO shop_order_items "
                    "(order_id, product_id, product_name_snapshot, unit_price_czk, qty, "
                    " line_total_czk, length_mm) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (order_id, it.get("product_id"), str(it["name"])[:255], unit_price, qty,
                     line_total, length_mm),
                )
                zapsano += 1
                print(f"  + {it['name']} qty={qty} total={line_total}")

            cur.execute(
                "INSERT INTO shop_order_status_history (order_id, status, changed_by, note) "
                "VALUES (%s, 'nova', NULL, %s)",
                (order_id, f"Položky zpětně doplněny z nabídky (backfill, {zapsano} položek, "
                           f"qty_multiplier={QTY_MULTIPLIER})."),
            )
        conn.commit()
        print(f"\nCOMMIT hotovy - {zapsano} polozek zapsano do objednavky {ORDER_NUMBER} (id={order_id}).")
    finally:
        conn.close()

    conn2 = get_conn()
    try:
        with conn2.cursor() as cur:
            cur.execute("SELECT SUM(line_total_czk) AS s, COUNT(*) AS c FROM shop_order_items WHERE order_id=%s", (order_id,))
            print("OVERENI:", cur.fetchone())
    finally:
        conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
