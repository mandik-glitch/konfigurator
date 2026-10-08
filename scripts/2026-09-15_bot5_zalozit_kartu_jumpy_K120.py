#!/usr/bin/env python3
"""Zalozeni karty pro Jumpy L1 K-120 (bot5, 2026-09-15) - ČÁSTEČNÝ stav.

Na rozdil od K-122 (2026-09-14, vsech 12 sestav rovnou) je tohle
zalozeni s JEDINOU sestavou: Robert 15.9. rano (07:48-07:49, primo ve
scene, checkbox - overeno technicky_ok_by=1/mandik@logiman.cz, ne
bot-samoschvaleni jako u driveijsiho incidentu) schvalil jen 392
(K-120 A-03) a 393 (K-120 A-04). 393 je ale TRVALE vyrazena z e-shopu
(bot8, 2026-09-15: mezera_police_mm<70mm pravidlo,
shape_geometry_methods.id=9 - 393 ma 62,5mm) - nikdy se nesmi zobrazit
ani mit pozici na kartě, i kdyz je technicky_ok=1. 390/391 (A-01/A-02)
zustavaji technicky_ok=0, B/C verze cele neschvaleny.

Karta tedy vznika s JEDINOU pozici (392), is_master=392 (jedina
volba). Dalsi sestavy (390/391/394-401 az budou schvalene) se
napoji pozdeji samostatnym skriptem/updatem - `active` zustava 0.

Zaloha do backups/, idempotentni.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-15_bot5_zalozit_kartu_jumpy_K120.py
    api/venv/bin/python3 scripts/2026-09-15_bot5_zalozit_kartu_jumpy_K120.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-15_bot5_zalozit_kartu_jumpy_K120",
)

CATEGORY_ID = 247
SKU = "K-120-RL-EB-30"
NAME = "Regál na euroboxy – Citroën Jumpy L1 (od 2016)"
SLUG = "regal-na-euroboxy-citroen-jumpy-l1-od-2016"
DESCRIPTION = (
    "Hliníkový regálový systém do nákladového prostoru Citroën Jumpy L1 (od 2016). "
    "Na výběr jsou tři skladby euroboxů: 3× box výšky 170 mm a 6× 120 mm; "
    "dvanáct boxů výšky 120 mm; nebo 3× 220 mm, 3× 170 mm a 3× 120 mm.\n\n"
    "Rozměry nejsou dané. Každý díl jde posunout, zvětšit nebo vynechat na milimetr "
    "přesně tak, aby sestava seděla na vaše kufry a nářadí.\n\n"
    "Konstrukce se kotví do zpevněných částí karoserie (bočnice a podlaha). Montáž "
    "zahrnuje vrtání do těchto částí, v souladu s požadavky na homologaci.\n\n"
    "Výšku sestavy omezuje výška zadního nakládacího otvoru (1220 mm) – regál se do "
    "auta nakládá zadními dveřmi a musí jimi projít."
)
SHORT_DESCRIPTION = "Hliníkový regál na euroboxy na míru pro Citroën Jumpy L1 (od 2016), na výběr tři skladby boxů."
META_TITLE = "Regál na euroboxy do Citroën Jumpy L1"
META_DESCRIPTION = (
    "Hliníkový regál na euroboxy do Citroën Jumpy L1 (od 2016). Tři skladby boxů "
    "na výběr. Stavíme na míru na milimetr podle toho, co v autě vozíte."
)

# JEN 392 - jedina skutecne schvalena a eshop-eligible sestava zatim
# (393 trvale vyrazena pravidlem mezery, 390/391 zatim neschvaleny).
ASSEMBLY_IDS = (392,)
MASTER_ID = 392
# Vyslovne VYLOUCENA - nikdy nenapojovat, i kdyby mela technicky_ok=1.
NAVZDY_VYLOUCENE = (393,)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== zalozeni karty Jumpy K-120 (castecny stav) — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = {"karta_id": None, "assemblies": []}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, technicky_ok FROM product_assemblies WHERE id IN %s", (NAVZDY_VYLOUCENE,))
            for r in cur.fetchall():
                print(f"  KONTROLA: id={r['id']} (navzdy vylouceno pravidlem mezery) - NENAPOJUJI, "
                      f"technicky_ok={r['technicky_ok']} (i kdyby 1, netyka se)")

            cur.execute("SELECT id FROM shop_products WHERE sku=%s", (SKU,))
            existing = cur.fetchone()
            if existing:
                karta_id = existing["id"]
                print(f"\nKarta se SKU {SKU} uz existuje (id={karta_id}), preskakuji vytvoreni.")
            else:
                print(f"\nVytvarim novou kartu: {NAME} (SKU {SKU})")
                karta_id = None
                if args.apply:
                    cur.execute(
                        "INSERT INTO shop_products "
                        "(category_id, sku, name, slug, description, short_description, "
                        " meta_title, meta_description, unit, availability_text, "
                        " price_visible_default, hover_show_price, hover_show_availability, active) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)",
                        (CATEGORY_ID, SKU, NAME, SLUG, DESCRIPTION, SHORT_DESCRIPTION,
                         META_TITLE, META_DESCRIPTION, "ks", "3 - 5 týdnů", 1, 1, 0),
                    )
                    karta_id = cur.lastrowid

            for aid in ASSEMBLY_IDS:
                cur.execute(
                    "SELECT id, name, shop_product_id, technicky_ok FROM product_assemblies WHERE id=%s",
                    (aid,),
                )
                r = cur.fetchone()
                if not r:
                    print(f"  id={aid}: sestava neexistuje, preskakuji"); continue
                if r["technicky_ok"] != 1:
                    print(f"  id={aid}: technicky_ok!=1, POZOR preskakuji"); continue
                if karta_id is not None and r["shop_product_id"] == karta_id:
                    print(f"  id={aid}: uz napojeno, preskakuji")
                    continue
                is_master = 1 if aid == MASTER_ID else 0
                print(f"  id={aid} ({r['name']}): -> karta {karta_id or '(nova)'}{' [MASTER]' if is_master else ''}")
                zaloha["assemblies"].append({"id": aid, "puvodni_shop_product_id": r["shop_product_id"]})
                if args.apply:
                    cur.execute(
                        "UPDATE product_assemblies SET shop_product_id=%s, is_master=%s WHERE id=%s",
                        (karta_id, is_master, aid),
                    )

            if args.apply and karta_id:
                cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (MASTER_ID,))
                d = json.loads(cur.fetchone()["data"] or "{}")
                total = (d.get("price_summary") or {}).get("total_czk")
                if total is not None:
                    cur.execute("UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s",
                                (round(total), karta_id))
                    print(f"  cena karty nastavena: {round(total)} Kč")

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
                cur.execute("SELECT id, sku, name, active, price_czk_placeholder FROM shop_products WHERE sku=%s", (SKU,))
                print("Karta:", cur.fetchone())
                cur.execute("SELECT id, shop_product_id, is_master FROM product_assemblies WHERE id IN (390,391,392,393)")
                for r in cur.fetchall():
                    print(" ", r)
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
