#!/usr/bin/env python3
"""Backfill chybejiciho cut_kind/material_key na shop_order_items
(bot5, 2026-09-17, Robert pres bot3: "rozmery profilu se z nabidky
nepropsaly do objednavky").

`length_mm` se u polozek z create_order_from_scene_offer() ukladalo
spravne uz od 2026-09-16, ale `cut_kind`/`material_key` chybely - bez
nich api/cutting.py::_classify_items() polozku vubec nezaradi mezi
profily k rezani ("if not cut_kind or not material_key: continue"),
takze Rezny plan panel hlasil "zadne polozky k rezani", i kdyz
`length_mm` v DB bylo spravne. Opraveno v api/orders.py::
create_order_from_scene_offer() (dopredu, komit viz git log) - tenhle
skript jen dohanni JIZ EXISTUJICI radky vytvorene PRED opravou.

Rozsah (overeno primo v DB pred spustenim, cele katalog ne jen
OBJ-2026-00187): 4 radky, vsechny na order_id=187 (jediny objednavka
z scene-offer, ktera existovala pred timhle fixem).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-17_bot5_fix_chybejici_cut_kind_material_key.py
    api/venv/bin/python3 scripts/2026-09-17_bot5_fix_chybejici_cut_kind_material_key.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-17_bot5_fix_chybejici_cut_kind_material_key",
)


def _cross_key_for_profile(cur, cfg_dily_id):
    """Presna kopie api/orders.py::_cross_key_for_profile - jednoducha
    cista funkce, bezpecne duplikovat do jednorazoveho skriptu misto
    tahani zavislosti na cele api/app.py."""
    cur.execute("SELECT dim_x_mm, dim_y_mm, dim_z_mm FROM cfg_dily WHERE id=%s", (cfg_dily_id,))
    d = cur.fetchone()
    if not d or d["dim_x_mm"] is None or d["dim_y_mm"] is None or d["dim_z_mm"] is None:
        return None
    a, b, _c = sorted([float(d["dim_x_mm"]), float(d["dim_y_mm"]), float(d["dim_z_mm"])])
    return f"{int(round(a))}x{int(round(b))}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== backfill cut_kind/material_key — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT soi.id, soi.order_id, soi.product_id, soi.length_mm, "
                "       sp.is_profile_material, sp.cfg_dily_id "
                "FROM shop_order_items soi "
                "JOIN shop_products sp ON sp.id=soi.product_id "
                "JOIN shop_orders so ON so.id=soi.order_id "
                "WHERE so.source_scene_offer_id IS NOT NULL "
                "  AND sp.is_profile_material=1 AND soi.length_mm IS NOT NULL "
                "  AND (soi.cut_kind IS NULL OR soi.material_key IS NULL)"
            )
            radky = cur.fetchall()
            print(f"Nalezeno {len(radky)} postizenych radku:")
            for r in radky:
                material_key = _cross_key_for_profile(cur, r["cfg_dily_id"]) if r["cfg_dily_id"] else None
                if not material_key:
                    print(f"  id={r['id']} (order {r['order_id']}): cfg_dily {r['cfg_dily_id']} bez "
                          f"kompletnich rozmeru, PRESKAKUJI (nehaduju material_key)")
                    continue
                print(f"  id={r['id']} (order {r['order_id']}, product {r['product_id']}, "
                      f"length_mm={r['length_mm']}) -> cut_kind=profil, material_key={material_key}")
                zaloha.append({"id": r["id"], "order_id": r["order_id"], "length_mm": str(r["length_mm"])})
                if args.apply:
                    cur.execute(
                        "UPDATE shop_order_items SET cut_kind='profil', material_key=%s WHERE id=%s",
                        (material_key, r["id"]),
                    )

        if args.apply:
            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=2, default=str)
            conn.commit()
            print("\nCOMMIT hotovy.")
        else:
            print("\nDRY-RUN: nic nezapsano.")
    finally:
        conn.close()

    if args.apply:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                print("\n=== OVERENI z noveho spojeni ===")
                cur.execute("SELECT id, order_id, cut_kind, material_key, length_mm FROM shop_order_items WHERE order_id=187 ORDER BY id")
                for r in cur.fetchall():
                    print(" ", r)
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
