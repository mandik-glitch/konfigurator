#!/usr/bin/env python3
"""Zalozeni nove karty pro Jumpy L2 K-122 (bot5, 2026-09-14).

Kontext: bot8 postavil 72 novych sestav (id 386-457) pro 6 novych Jumpy
vozidel (K-120, K-121e, K-122, K-123e, K-124, K-125e), kazde A/B/C x
01-04 horni_blok, stejny vzor jako uz zive Doblo K-075 (karta 3943).
Bot8 nechal category_id/shop_product_id na mne (SKU/karta je moje
strana, viz "Delba prace: bot8 cenik -> bot5 SKU").

K-122 je JEDINE z tech 6, ktere ma overena oficialni data (car_model_id
=40 -> karoserie_model_reference: "Jumpy L2 16-", cargo 2512x1258x1397mm,
vyska naklad. otvoru 1220mm) - K-120/K-121e/K-123e/K-124/K-125e maji
car_model_id=NULL, tedy zadna overena data k dispozici (viz zprava
bot8, cekam na doplneni pred zalozenim jejich karet).

Sestavy 414-425 (K-122 A/B/C x 01-04) - VSECHNY technicky_ok=1
(bot8 potvrdil 0 kolizi), zadny bom/price_summary jeste (bot8 jeste
nedopocital cenu) - `price_czk_placeholder` NECHAVAM NULL, karta
zustava `active=0` (necekana/nedokoncena cena, stejny princip jako
"radsi chybejici nez vymysleny" cely tenhle session).

is_master = 414 (K-122 A-01, "jedno pasmo - ram+dna [ZAKLAD]") -
konzistentni s Doblo vzorem (master = "01 ZAKLAD" varianta).

Zaloha do backups/, idempotentni.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-14_bot5_zalozit_kartu_jumpy_K122.py
    api/venv/bin/python3 scripts/2026-09-14_bot5_zalozit_kartu_jumpy_K122.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-14_bot5_zalozit_kartu_jumpy_K122",
)

ASSEMBLY_IDS = (414, 415, 416, 417, 418, 419, 420, 421, 422, 423, 424, 425)
MASTER_ID = 414

KARTA = {
    "category_id": 247,  # stejna jako K-118/K-119 (3944/3945) - "regaly na euroboxy"
    "sku": "K-122-RL-EB-30",
    "name": "Regál na euroboxy – Citroën Jumpy L2 (od 2016)",
    "slug": "regal-na-euroboxy-citroen-jumpy-l2-od-2016",
    "description": (
        "Hliníkový regálový systém do nákladového prostoru Citroën Jumpy L2 (od 2016). "
        "Na výběr jsou tři skladby euroboxů: 2× box výšky 270 mm, 3× 170 mm a 9× 120 mm; "
        "patnáct boxů výšky 120 mm; nebo 4× 220 mm, 4× 170 mm a 3× 120 mm.\n\n"
        "Rozměry nejsou dané. Každý díl jde posunout, zvětšit nebo vynechat na milimetr "
        "přesně tak, aby sestava seděla na vaše kufry a nářadí.\n\n"
        "Konstrukce se kotví do zpevněných částí karoserie (bočnice a podlaha). Montáž "
        "zahrnuje vrtání do těchto částí, v souladu s požadavky na homologaci.\n\n"
        "Výšku sestavy omezuje výška zadního nakládacího otvoru (1220 mm) – regál se do "
        "auta nakládá zadními dveřmi a musí jimi projít."
    ),
    "short_description": (
        "Hliníkový regál na euroboxy na míru pro Citroën Jumpy L2 (od 2016), na výběr "
        "tři skladby boxů."
    ),
    "meta_title": "Regál na euroboxy do Citroën Jumpy L2",
    "meta_description": (
        "Hliníkový regál na euroboxy do Citroën Jumpy L2 (od 2016). Tři skladby boxů "
        "na výběr. Stavíme na míru na milimetr podle toho, co v autě vozíte."
    ),
    "unit": "ks",
    "availability_text": "3 - 5 týdnů",
    "price_visible_default": 1,
    "hover_show_price": 1,
    "hover_show_availability": 0,
    "active": 0,  # cena/rendery jeste nejsou hotove - viz docstring
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== zalozeni karty Jumpy K-122 — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = {"karta_id": None, "assemblies": []}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE sku=%s", (KARTA["sku"],))
            existing = cur.fetchone()
            if existing:
                karta_id = existing["id"]
                print(f"Karta se SKU {KARTA['sku']} uz existuje (id={karta_id}), preskakuji vytvoreni.")
            else:
                print(f"Vytvarim novou kartu: {KARTA['name']} (SKU {KARTA['sku']})")
                karta_id = None
                if args.apply:
                    cur.execute(
                        "INSERT INTO shop_products "
                        "(category_id, sku, name, slug, description, short_description, "
                        " meta_title, meta_description, unit, availability_text, "
                        " price_visible_default, hover_show_price, hover_show_availability, active) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (KARTA["category_id"], KARTA["sku"], KARTA["name"], KARTA["slug"],
                         KARTA["description"], KARTA["short_description"], KARTA["meta_title"],
                         KARTA["meta_description"], KARTA["unit"], KARTA["availability_text"],
                         KARTA["price_visible_default"], KARTA["hover_show_price"],
                         KARTA["hover_show_availability"], KARTA["active"]),
                    )
                    karta_id = cur.lastrowid
            zaloha["karta_id"] = karta_id

            for aid in ASSEMBLY_IDS:
                cur.execute(
                    "SELECT id, name, shop_product_id, technicky_ok FROM product_assemblies WHERE id=%s",
                    (aid,),
                )
                r = cur.fetchone()
                if not r:
                    print(f"  id={aid}: sestava neexistuje, preskakuji"); continue
                if r["technicky_ok"] != 1:
                    print(f"  id={aid} ({r['name']}): technicky_ok!=1, POZOR preskakuji"); continue
                if karta_id is not None and r["shop_product_id"] == karta_id:
                    print(f"  id={aid}: uz napojeno, preskakuji")
                    continue
                is_master = 1 if aid == MASTER_ID else 0
                print(f"  id={aid} ({r['name']}): shop_product_id -> {karta_id or '(bude prirazeno)'}"
                      f"{' [MASTER]' if is_master else ''}")
                zaloha["assemblies"].append({"id": aid, "puvodni_shop_product_id": r["shop_product_id"]})
                if args.apply:
                    cur.execute(
                        "UPDATE product_assemblies SET shop_product_id=%s, is_master=%s WHERE id=%s",
                        (karta_id, is_master, aid),
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
                cur.execute("SELECT id, sku, name, active, category_id FROM shop_products WHERE sku=%s", (KARTA["sku"],))
                print("Karta:", cur.fetchone())
                cur.execute(
                    f"SELECT id, name, shop_product_id, is_master, kod_sestavy FROM product_assemblies "
                    f"WHERE id IN ({','.join(str(i) for i in ASSEMBLY_IDS)}) ORDER BY id"
                )
                for r in cur.fetchall():
                    print(" ", r)
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
