#!/usr/bin/env python3
"""Doplni `shop_products.price_czk_placeholder` z ceny ZASTUPCE sestavy.

Problem (Robert, 2026-09-13): *"Doblo L1 hotová sestava na eshopu proč
variantám chybí ceny"*. Sest ze sedmi provedeni cenu ukazovalo, zastupce ne -
a protoze zastupce reprezentuje celou kartu, stranka i vypis produktu psaly
"Cena na dotaz".

Priciny jsou dve a tenhle skript resi tu druhou:
  1. `_price_for()` ve verejnem API u zastupce IGNORUJE jeho vlastni
     spocitanou cenu a bere `price_czk_placeholder` z karty. Opraveno v
     `api/product_assemblies.py` (fallback na vlastni cenu).
  2. Karta sama zadnou cenu nema - `price_czk_placeholder` NIC NEPLNI
     automaticky. To resi tenhle skript.

PROC SE TO ZAPISUJE DO DB A NEDOPOCITAVA JEN PRI ZOBRAZENI
----------------------------------------------------------
`_effective_unit_price()` (api/products.py) pocita cenu do KOSIKU jako
`float(product.get("price_czk_placeholder") or 0)`. Kdyby se cena jen
dopocitavala pri vypisu, zakaznik by videl 15 247 Kc a kosik by pocital
s nulou. Displejovy fallback bez zapisu by tedy vyrobil horsi vadu, nez
jakou opravuje.

JAKA CENA SE ZAPISUJE
---------------------
`price_summary.total_czk` ZASTUPCE (`is_master=1`). Je to uz PRODEJNI cena
vcetne marze, ne naklad: koeficient `app_settings.scene_price_coefficient`
(dnes 1.4) se aplikuje jednou, v `/api/katalog`, tedy uz v cenach dilu, ze
kterych se kusovnik pocita. Overeno na datech 2026-09-12: kusova polozka se
zakladni cenou 5 Kc ma v kusovniku 7 Kc, polozka za 17 Kc ma 24 Kc - pomer
1.400. NENASOBIT marzi znovu.

⚠️ Cena je DOLNI ODHAD, kde `joint_czk=0` - u takovych sestav se nedochoval
pocet spoju a prace za ne neni zapocitana (`joint_price_odhad_chybi_czk`
rika, kolik odhadem chybi). Skript to u kazde karty VYPISE, at je videt,
ze zapsane cislo neni konecne.

BEZPECNOSTNI MEZE
-----------------
* Zapisuje POUZE tam, kde je `price_czk_placeholder` NULL - existujici cenu
  nikdy neprepise (doplnit chybejici != prepsat rucne nastavenou).
* Vyzaduje, aby karta mela prave jednoho zastupce. Bez zastupce se karta
  PRESKOCI a nahlasi - vybrat, ktere provedeni kartu reprezentuje, je
  rozhodnuti o produktu, ne oprava chyby (tyka se dnes karet 3944/3945).
* Idempotentni: druhy beh uz nema co delat.
* Zaloha stavu pred zapisem do `backups/`.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-13_bot5_cena_karty_ze_zastupce.py
    api/venv/bin/python3 scripts/2026-09-13_bot5_cena_karty_ze_zastupce.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-13_bot5_cena_karty_ze_zastupce",
)


def nacti_karty(cur):
    """Karty navazane na sestavy, ktere jeste nemaji cenu."""
    cur.execute(
        "SELECT sp.id, sp.sku, sp.name, sp.price_czk_placeholder "
        "FROM shop_products sp "
        "WHERE sp.is_archived=0 AND EXISTS ("
        "  SELECT 1 FROM product_assemblies pa WHERE pa.shop_product_id=sp.id) "
        "ORDER BY sp.id"
    )
    return cur.fetchall()


def cena_zastupce(cur, product_id):
    """(cena, id_zastupce, odhad_chybi) nebo (None, None, None) + duvod."""
    cur.execute(
        "SELECT id, data FROM product_assemblies "
        "WHERE shop_product_id=%s AND is_master=1",
        (product_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return None, None, None, "karta nema zastupce (is_master)"
    if len(rows) > 1:
        return None, None, None, f"karta ma {len(rows)} zastupcu, ocekaval jsem jednoho"
    try:
        data = json.loads(rows[0]["data"]) if rows[0]["data"] else {}
    except (ValueError, TypeError):
        return None, None, None, "data sestavy nejdou precist"
    ps = data.get("price_summary") or {}
    total = ps.get("total_czk")
    if total is None:
        return None, None, None, "zastupce nema spocitanou cenu (price_summary.total_czk)"
    chybi = ps.get("joint_price_odhad_chybi_czk") if not ps.get("joint_czk") else None
    return round(float(total)), rows[0]["id"], chybi, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="skutecne zapsat (jinak dry-run)")
    args = ap.parse_args()
    print(f"=== Cena karty ze zastupce — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha, zapsat = [], []
    try:
        with conn.cursor() as cur:
            for k in nacti_karty(cur):
                cena, zid, chybi, duvod = cena_zastupce(cur, k["id"])
                if k["price_czk_placeholder"] is not None:
                    print(f"  {k['id']} [{k['sku']}] uz cenu ma "
                          f"({k['price_czk_placeholder']} Kc), preskakuji")
                    continue
                if cena is None:
                    print(f"  {k['id']} [{k['sku']}] PRESKAKUJI — {duvod}")
                    continue
                print(f"  {k['id']} [{k['sku']}] NULL -> {cena} Kc (ze zastupce {zid})")
                if chybi:
                    print(f"       ⚠ dolni odhad, prace za spoje nezapocitana "
                          f"(odhadem chybi {round(float(chybi))} Kc)")
                zaloha.append({"product_id": k["id"], "sku": k["sku"],
                               "puvodni_price_czk_placeholder": None,
                               "nova": cena, "ze_sestavy": zid})
                zapsat.append((cena, k["id"]))

            if args.apply and zapsat:
                os.makedirs(ZALOHA_DIR, exist_ok=True)
                with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(zaloha, f, ensure_ascii=False, indent=2)
                for cena, pid in zapsat:
                    # `AND price_czk_placeholder IS NULL` i tady: mezi ctenim a
                    # zapisem mohl cenu doplnit clovek v adminu.
                    cur.execute(
                        "UPDATE shop_products SET price_czk_placeholder=%s "
                        "WHERE id=%s AND price_czk_placeholder IS NULL",
                        (cena, pid),
                    )
                    cur.execute(
                        "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) "
                        "VALUES (NULL,'update','shop_product',%s,%s)",
                        (pid, f"bot5 skript 2026-09-13: doplnena cena {cena} Kc "
                              f"z price_summary zastupce (karta byla bez ceny)"),
                    )
        if args.apply:
            conn.commit()
            print(f"\nCOMMIT hotovy, doplneno karet: {len(zapsat)}")
        else:
            print(f"\nDRY-RUN: nic nezapsano, k doplneni karet: {len(zapsat)}")
    finally:
        conn.close()

    if args.apply and zapsat:
        print("\n=== OVERENI z noveho spojeni ===")
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                for _cena, pid in zapsat:
                    cur.execute(
                        "SELECT id, sku, price_czk_placeholder FROM shop_products WHERE id=%s",
                        (pid,),
                    )
                    r = cur.fetchone()
                    print(f"  {r['id']} [{r['sku']}] = {r['price_czk_placeholder']} Kc")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
