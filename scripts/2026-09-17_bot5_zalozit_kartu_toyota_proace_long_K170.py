#!/usr/bin/env python3
"""Zalozeni karty pro Toyota Proace Long K-170 (bot5, 2026-09-17).

Robert (pres bot3): "kdy budou 2 schvalene sestavy ProAce na webu" -
524 (Proace Long 16- B-03) a 528 (Proace Long 16- C-03) maji
technicky_ok=1 (technicky_ok_by=1/mandik@logiman.cz, realne
rozestoupene casy 08:43:49/08:44:09), ale zadnou kartu.

POZOR, odlisnost oproti vsem predchozim kartam teto session:
`product_assemblies.karoserie_kod` i `car_model_id` jsou u CELE Proace
rodiny (vsech 12 sester v teto "Proace Long 16-" vetvi, overeno) NULL -
znamy, uz drive zdokumentovany stav (viz api/production_overview.py
komentar u _resolve_vehicle(): "karoserie_kod jen u 243/269"). K-kod
NEODHADOVAN ze jmena, ale odvozen STEJNYM zpusobem jako
production_overview.py::_resolve_vehicle() - dohledani car_body_<id>
dilu v datech sestavy -> car_bodies.model_id -> car_models.name ->
K-kod. Vysledek jednoznacny a shodny u vsech 12 sester: K-170
(car_model_id=274, "Proace Long 16- [K-170]"). NEZAPISUJI zpet
karoserie_kod/car_model_id do product_assemblies - to je siresi,
katalogovy zasah mimo rozsah tohoto ukolu (a mimo domenu bot5).

Zadna varianta "04" (mezera<70mm vyjimka, PLAN_TVORBY_SESTAV.md Faze 4)
v teto rodine vubec neexistuje - kontrola pro jistotu prece jen
zabudovana (viz REGRESE 2026-09-17, scripts/2026-09-17_bot5_fix_
mezera04_shop_product_id.py).

Master = 528 (C-03, bohatsi skladba boxu - 3 ruzne vysky vs B-03 jen 1
- muj odhad, snadno prehoditelny v adminu).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-17_bot5_zalozit_kartu_toyota_proace_long_K170.py
    api/venv/bin/python3 scripts/2026-09-17_bot5_zalozit_kartu_toyota_proace_long_K170.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-17_bot5_zalozit_kartu_toyota_proace_long_K170",
)

CATEGORY_ID = 247

CARD = {
    "sku": "K-170-RL-EB-30",
    "name": "Regál na euroboxy – Toyota Proace Long (od 2016)",
    "slug": "regal-na-euroboxy-toyota-proace-long-od-2016",
    "assembly_ids": (524, 528),
    "master_id": 528,
    "description": (
        "Hliníkový regálový systém do nákladového prostoru Toyota Proace Long (od 2016). "
        "Na výběr jsou dvě skladby euroboxů: 23× box výšky 120 mm; nebo 5× box výšky 220 mm, "
        "5× 170 mm a 8× 120 mm.\n\n"
        "Rozměry nejsou dané. Každý díl jde posunout, zvětšit nebo vynechat na milimetr "
        "přesně tak, aby sestava seděla na vaše kufry a nářadí.\n\n"
        "Konstrukce se kotví do zpevněných částí karoserie (bočnice a podlaha). Montáž "
        "zahrnuje vrtání do těchto částí, v souladu s požadavky na homologaci."
    ),
    "short_description": "Hliníkový regál na euroboxy na míru pro Toyota Proace Long (od 2016), na výběr dvě skladby boxů.",
    "meta_title": "Regál na euroboxy do Toyota Proace Long",
    "meta_description": (
        "Hliníkový regál na euroboxy do Toyota Proace Long (od 2016). Dvě skladby boxů na "
        "výběr. Stavíme na míru na milimetr podle toho, co v autě vozíte."
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== zalozeni karty Toyota Proace Long K-170 — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = {"karta": None}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE sku=%s", (CARD["sku"],))
            existing = cur.fetchone()
            if existing:
                karta_id = existing["id"]
                print(f"Karta se SKU {CARD['sku']} uz existuje (id={karta_id}), preskakuji vytvoreni.")
            else:
                print(f"Vytvarim novou kartu: {CARD['name']} (SKU {CARD['sku']})")
                karta_id = None
                if args.apply:
                    cur.execute(
                        "INSERT INTO shop_products "
                        "(category_id, sku, name, slug, description, short_description, "
                        " meta_title, meta_description, unit, availability_text, "
                        " price_visible_default, hover_show_price, hover_show_availability, active) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)",
                        (CATEGORY_ID, CARD["sku"], CARD["name"], CARD["slug"], CARD["description"],
                         CARD["short_description"], CARD["meta_title"], CARD["meta_description"],
                         "ks", "3 - 5 týdnů", 1, 1, 0),
                    )
                    karta_id = cur.lastrowid

            zaloha_card = {"sku": CARD["sku"], "karta_id": karta_id, "assemblies": []}
            for aid in CARD["assembly_ids"]:
                cur.execute(
                    "SELECT pa.id, pa.name, pa.shop_product_id, pa.technicky_ok, "
                    "       pa.mezera_police_mm, hb.kod AS hb_kod "
                    "FROM product_assemblies pa "
                    "LEFT JOIN horni_blok_varianty hb ON hb.id=pa.horni_blok_varianta_id "
                    "WHERE pa.id=%s", (aid,),
                )
                r = cur.fetchone()
                if not r:
                    print(f"  id={aid}: sestava neexistuje, preskakuji"); continue
                if r["technicky_ok"] != 1:
                    print(f"  id={aid}: technicky_ok!=1, POZOR preskakuji"); continue
                # REGRESE 2026-09-17 pojistka: varianta "04" s mezerou<70mm
                # nikdy na kartu (PLAN_TVORBY_SESTAV.md Faze 4).
                if r["hb_kod"] == "04" and r["mezera_police_mm"] is not None and r["mezera_police_mm"] < 70:
                    print(f"  id={aid}: hb_kod=04 + mezera={r['mezera_police_mm']}mm<70, PRAVIDLO preskakuji"); continue
                if karta_id is not None and r["shop_product_id"] == karta_id:
                    print(f"  id={aid}: uz napojeno, preskakuji")
                    continue
                is_master = 1 if aid == CARD["master_id"] else 0
                print(f"  id={aid} ({r['name']}): -> karta {karta_id or '(nova)'}{' [MASTER]' if is_master else ''}")
                zaloha_card["assemblies"].append({"id": aid, "puvodni_shop_product_id": r["shop_product_id"]})
                if args.apply:
                    cur.execute(
                        "UPDATE product_assemblies SET shop_product_id=%s, is_master=%s WHERE id=%s",
                        (karta_id, is_master, aid),
                    )

            if args.apply and karta_id:
                cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (CARD["master_id"],))
                d = json.loads(cur.fetchone()["data"] or "{}")
                total = (d.get("price_summary") or {}).get("total_czk")
                if total is not None:
                    cur.execute("UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s",
                                (round(total), karta_id))
                    print(f"  cena karty nastavena: {round(total)} Kč")
            zaloha["karta"] = zaloha_card

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
                cur.execute("SELECT id, sku, name, active, price_czk_placeholder FROM shop_products WHERE sku=%s", (CARD["sku"],))
                print("Karta:", cur.fetchone())
                cur.execute(
                    "SELECT id, shop_product_id, is_master, technicky_ok FROM product_assemblies WHERE id IN %s",
                    (CARD["assembly_ids"],),
                )
                for r in cur.fetchall():
                    print(" ", r)
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
