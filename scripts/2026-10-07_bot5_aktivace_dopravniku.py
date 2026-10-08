#!/opt/konfigurator/api/venv/bin/python
"""Aktivace naimportovanych karet dopravniku bez pohonu na PRIMY pokyn Roberta (2026-10-07: "aktivuj vsechny za mě teď"). Pravidlo 54: bot sam nikdy - tady je to Robertovo rozhodnuti, bot je jen provedl.
Aktivuje JEN karty z importu (backups/2026-10-07_dopravniky_vytvorene_karty.json), ktere maji cenu, jsou neaktivni a nikdy nebyly aktivni (activated_at NULL); karty BEZ ceny (12 dopravniku bez skutecneho
valecku a valeckova draha #5273) zustavaji neaktivni. Zaroven zviditelni kategorie, ve kterych jsou ted aktivni karty (#323-329, #225, #214). Zaloha puvodniho stavu do backups/. Bez --apply jen nahled."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from _env import get_conn  # noqa: E402

KATEGORIE_ZVIDITELNIT = (323, 324, 325, 326, 327, 328, 329, 225, 214)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    vytv = json.load(open(os.path.join(REPO, "backups", "2026-10-07_dopravniky_vytvorene_karty.json"), encoding="utf-8"))
    ids = [v["id"] for v in vytv]
    conn = get_conn()
    cur = conn.cursor()
    try:
        fm = ",".join(["%s"] * len(ids))
        cur.execute(f"SELECT id, sku, name, active, activated_at, price_czk_placeholder, category_id FROM shop_products WHERE id IN ({fm})", ids)
        radky = cur.fetchall()
        k_aktivaci = [r for r in radky if r["price_czk_placeholder"] is not None and r["active"] == 0 and r["activated_at"] is None]
        bez_ceny = [r for r in radky if r["price_czk_placeholder"] is None]
        print(f"karet z importu {len(radky)}; K AKTIVACI {len(k_aktivaci)}; bez ceny (zustanou neaktivni) {len(bez_ceny)}: {[r['id'] for r in bez_ceny]}")
        if not a.apply:
            print("(nahled, nic nezapsano; --apply)")
            return
        zaloha = os.path.join(REPO, "backups", "2026-10-07_aktivace_dopravniku_pred_zmenou.json")
        if os.path.exists(zaloha):
            sys.exit("ZASTAVENO: zaloha uz existuje - aktivace uz probehla?")
        cur.execute("SELECT id, is_visible FROM content_categories WHERE id IN (" + ",".join(["%s"] * len(KATEGORIE_ZVIDITELNIT)) + ")", KATEGORIE_ZVIDITELNIT)
        json.dump({"karty": [{k: str(v) if v is not None else None for k, v in r.items()} for r in k_aktivaci], "kategorie": cur.fetchall()}, open(zaloha, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
        id_a = [r["id"] for r in k_aktivaci]
        n = cur.execute("UPDATE shop_products SET active=1, activated_at=NOW() WHERE id IN (" + ",".join(["%s"] * len(id_a)) + ") AND active=0 AND activated_at IS NULL AND price_czk_placeholder IS NOT NULL", id_a)
        if n != len(id_a):
            conn.rollback()
            sys.exit(f"ZASTAVENO, rollback: zmeneno {n} radku, ocekavano {len(id_a)}")
        m = cur.execute("UPDATE content_categories SET is_visible=1 WHERE id IN (" + ",".join(["%s"] * len(KATEGORIE_ZVIDITELNIT)) + ") AND is_visible=0", KATEGORIE_ZVIDITELNIT)
        cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'update','shop_product',NULL,%s)",
                    (f"aktivace {n} karet dopravniku bez pohonu na PRIMY pokyn Roberta 2026-10-07 (bot5 provedl); zviditelneno {m} kategorii; bez ceny zustalo neaktivnich {len(bez_ceny)}",))
        conn.commit()
        print(f"ZAPSANO: aktivovano {n} karet, zviditelneno {m} kategorii. Zaloha: {zaloha}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
