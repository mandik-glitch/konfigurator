#!/usr/bin/env python3
"""Zalozeni karty pro Mercedes Vito Compact K-289 (bot5, 2026-09-16).

Robert (pres bot4): "proc se nerenderuje connect?" -> "ford connect" ->
pak primo o K-289 (Vito Compact D-04): sestava id=517 ma technicky_ok=1
(potvrzeno 2026-09-16 07:36:49, technicky_ok_by=1/mandik@logiman.cz),
BOM+cena hotove (total_czk=35421, 117 spoju), ale shop_product_id je
NULL - render_auto_dispatch (bot4) ji proto spravne preskakuje (vyzaduje
shop_product_id IS NOT NULL).

Stejny vzor jako K-237/K-239 Ford Connect
(scripts/2026-09-15_bot5_zalozit_karty_ford_connect.py): SKU = prvni 4
segmenty kod_sestavy (karoserie-umisteni-typologie-profil), overeno
primo ze sloupcu (umisteni_kod=RL, typologie_kod=EB, profil_mm=30).

ROZDIL oproti Ford Connect: tam uz VSECHNY navazovane sestavy mely
technicky_ok=1 v okamziku zalozeni karty. Tady je to JEN 517 (D-04) -
sourozenci D-01/D-02/D-03 (514/515/516) i cele verze A/B/C (ktere
sdileji STEJNOU kartu, stejne jako u K-075 Doblo A/B/C na karte 3943)
jsou zatim technicky_ok=0. Skript uz ma vestavenou pojistku (viz
"technicky_ok!=1, POZOR preskakuji" nize) - do karty se napoji JEN
517, ostatni ID jsou v seznamu uz TED (aby se pri jejich schvaleni
stacilo znovu spustit --apply, zadny novy skript). Popis karty proto
zminuje JEN skutecne dostupnou skladbu (D, 12x box vysky 120mm), ne
konfigurace A/B/C, ktere zatim nejsou schvalene ani na vyber.

Zadny render zatim neexistuje (turntable=0) - karta se zaklada jako
active=0, aktivace az po dokoncenem renderu - bud rucne, nebo
autonomne (scripts/2026-09-16_card_auto_activate.py, systemd timer
15 min).

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-16_bot5_zalozit_kartu_mercedes_vito_K289.py
    api/venv/bin/python3 scripts/2026-09-16_bot5_zalozit_kartu_mercedes_vito_K289.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-16_bot5_zalozit_kartu_mercedes_vito_K289",
)

CATEGORY_ID = 247

CARD = {
    "sku": "K-289-RL-EB-30",
    "name": "Regál na euroboxy – Mercedes Vito Compact (od 2014)",
    "slug": "regal-na-euroboxy-mercedes-vito-compact-od-2014",
    # 514/515/516 = D-01/D-02/D-03, zatim technicky_ok=0 - skript je
    # preskoci (viz kontrola nize), pripraveno pro pozdejsi doplneni.
    "assembly_ids": (514, 515, 516, 517),
    "master_id": 517,
    "description": (
        "Hliníkový regálový systém do nákladového prostoru Mercedes Vito Compact (od 2014). "
        "Aktuální skladba: 12× box výšky 120 mm, ve dvou výškových pásmech, s policí.\n\n"
        "Rozměry nejsou dané. Každý díl jde posunout, zvětšit nebo vynechat na milimetr "
        "přesně tak, aby sestava seděla na vaše kufry a nářadí.\n\n"
        "Konstrukce se kotví do zpevněných částí karoserie (bočnice a podlaha). Montáž "
        "zahrnuje vrtání do těchto částí, v souladu s požadavky na homologaci."
    ),
    "short_description": "Hliníkový regál na euroboxy na míru pro Mercedes Vito Compact (od 2014), dvanáct boxů výšky 120 mm ve dvou pásmech s policí.",
    "meta_title": "Regál na euroboxy do Mercedes Vito Compact",
    "meta_description": (
        "Hliníkový regál na euroboxy do Mercedes Vito Compact (od 2014). "
        "Stavíme na míru na milimetr podle toho, co v autě vozíte."
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== zalozeni karty Mercedes Vito Compact K-289 — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

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
