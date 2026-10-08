#!/usr/bin/env python3
"""Zalozeni karet pro zbyvajicich 5 Jumpy vozidel (bot5, 2026-09-14):
K-120, K-121e, K-123e, K-124, K-125e. Pokracovani
2026-09-14_bot5_zalozit_kartu_jumpy_K122.py (K-122 uz hotovo, karta
3946) - bot8 mezitim doplnil car_model_id (overena oficialni data,
karoserie_model_reference) pro vsech 5 zbyvajicich a bot3 dopocital
bom/price_summary, takze uz jde zalozit karty se skutecnou cenou
rovnou (na rozdil od K-122, kde price prisla az pozdeji).

Kazde vozidlo: A/B/C x 01-04 = 12 sestav, master = "A-01" (jedno pasmo
ram+dna [ZAKLAD]), stejny vzor jako K-122/Doblo K-075. `active=1` -
na rozdil od K-122 uz TADY cena i geometrie jsou hotove pri zalozeni
(zadny duvod cekat) - i tak necham na Robertovi posledni schvaleni,
proto `active` nastavuju az po explicitnim potvrzeni (viz spodek
skriptu - ACTIVATE=False dokud nedostanu OK).

Zaloha do backups/, idempotentni.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-14_bot5_zalozit_karty_jumpy_zbyvajici5.py
    api/venv/bin/python3 scripts/2026-09-14_bot5_zalozit_karty_jumpy_zbyvajici5.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

ZALOHA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-14_bot5_zalozit_karty_jumpy_zbyvajici5",
)

CATEGORY_ID = 247  # stejna jako K-118/K-119/K-122 - "regaly na euroboxy"

# box konfigurace pro vetu popisu, prevzato z typologie_varianty.nazev
def _box_veta(nazev):
    """'220x3-170x3-120x3' -> '3× box výšky 220 mm, 3× 170 mm a 3× 120 mm'.
    Jedina velikost (napr. '120x12') -> 'dvanáct boxů výšky 120 mm'
    (slovni cislovka jen pro caste 'vsechny stejne' pripady, jinak
    numericky format jako u vice velikosti)."""
    cisla_slovy = {6: "šest", 9: "devět", 12: "dvanáct", 15: "patnáct", 16: "šestnáct", 20: "dvacet"}
    casti = nazev.split("-")
    if len(casti) == 1:
        vyska, pocet = casti[0].split("x")
        pocet = int(pocet)
        slovo = cisla_slovy.get(pocet, str(pocet))
        return f"{slovo} boxů výšky {vyska} mm"
    kusy = []
    for cast in casti:
        vyska, pocet = cast.split("x")
        kusy.append(f"{pocet}× {vyska} mm" if kusy else f"{pocet}× box výšky {vyska} mm")
    if len(kusy) == 1:
        return kusy[0]
    return ", ".join(kusy[:-1]) + " a " + kusy[-1]


def _popis(nazev_vozidla, box_vety, vyska_otvoru_mm):
    a, b, c = box_vety
    return (
        f"Hliníkový regálový systém do nákladového prostoru {nazev_vozidla}. "
        f"Na výběr jsou tři skladby euroboxů: {a}; {b}; nebo {c}.\n\n"
        "Rozměry nejsou dané. Každý díl jde posunout, zvětšit nebo vynechat na milimetr "
        "přesně tak, aby sestava seděla na vaše kufry a nářadí.\n\n"
        "Konstrukce se kotví do zpevněných částí karoserie (bočnice a podlaha). Montáž "
        "zahrnuje vrtání do těchto částí, v souladu s požadavky na homologaci.\n\n"
        f"Výšku sestavy omezuje výška zadního nakládacího otvoru ({vyska_otvoru_mm} mm) – regál se do "
        "auta nakládá zadními dveřmi a musí jimi projít."
    )


# (karoserie_kod, nazev_vozidla_pro_popis, nazev_karty, slug, meta_nazev,
#  vyska_otvoru_mm, box_konfigurace A/B/C, master_id, assembly_ids)
VOZIDLA = [
    {
        "karoserie_kod": "K-120", "sku": "K-120-RL-EB-30",
        "nazev_vozidla": "Citroën Jumpy L1 (od 2016)",
        "name": "Regál na euroboxy – Citroën Jumpy L1 (od 2016)",
        "slug": "regal-na-euroboxy-citroen-jumpy-l1-od-2016",
        "meta_vozidlo": "Citroën Jumpy L1",
        "vyska_otvoru_mm": 1220,
        "box_nazvy": ("170x3-120x6", "120x12", "220x3-170x3-120x3"),
        "master_id": 390, "assembly_ids": list(range(390, 402)),
    },
    {
        "karoserie_kod": "K-121e", "sku": "K-121e-RL-EB-30",
        "nazev_vozidla": "Citroën ë-Jumpy L1 (od 2021)",
        "name": "Regál na euroboxy – Citroën ë-Jumpy L1 (od 2021)",
        "slug": "regal-na-euroboxy-citroen-e-jumpy-l1-od-2021",
        "meta_vozidlo": "Citroën ë-Jumpy L1",
        "vyska_otvoru_mm": 1220,
        "box_nazvy": ("170x3-120x6", "120x12", "220x3-170x3-120x3"),
        "master_id": 402, "assembly_ids": list(range(402, 414)),
    },
    {
        "karoserie_kod": "K-123e", "sku": "K-123e-RL-EB-30",
        "nazev_vozidla": "Citroën ë-Jumpy L2 (od 2021)",
        "name": "Regál na euroboxy – Citroën ë-Jumpy L2 (od 2021)",
        "slug": "regal-na-euroboxy-citroen-e-jumpy-l2-od-2021",
        "meta_vozidlo": "Citroën ë-Jumpy L2",
        "vyska_otvoru_mm": 1220,
        "box_nazvy": ("270x2-170x3-120x9", "120x16", "220x4-170x4-120x4"),
        "master_id": 426, "assembly_ids": list(range(426, 438)),
    },
    {
        "karoserie_kod": "K-124", "sku": "K-124-RL-EB-30",
        "nazev_vozidla": "Citroën Jumpy L3 (od 2016)",
        "name": "Regál na euroboxy – Citroën Jumpy L3 (od 2016)",
        "slug": "regal-na-euroboxy-citroen-jumpy-l3-od-2016",
        "meta_vozidlo": "Citroën Jumpy L3",
        "vyska_otvoru_mm": 1220,
        "box_nazvy": ("270x4-170x3-120x9", "120x20", "220x5-170x5-120x5"),
        "master_id": 386, "assembly_ids": [386, 387, 388, 389, 438, 439, 440, 441, 442, 443, 444, 445],
    },
    {
        "karoserie_kod": "K-125e", "sku": "K-125e-RL-EB-30",
        "nazev_vozidla": "Citroën ë-Jumpy L3 (od 2021)",
        "name": "Regál na euroboxy – Citroën ë-Jumpy L3 (od 2021)",
        "slug": "regal-na-euroboxy-citroen-e-jumpy-l3-od-2021",
        "meta_vozidlo": "Citroën ë-Jumpy L3",
        "vyska_otvoru_mm": 1220,
        "box_nazvy": ("270x4-170x3-120x9", "120x20", "220x5-170x5-120x5"),
        "master_id": 446, "assembly_ids": list(range(446, 458)),
    },
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== zalozeni 5 karet Jumpy — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    zaloha = []
    try:
        with conn.cursor() as cur:
            for v in VOZIDLA:
                print(f"--- {v['karoserie_kod']} ({v['sku']}) ---")
                box_vety = tuple(_box_veta(n) for n in v["box_nazvy"])
                popis = _popis(v["nazev_vozidla"], box_vety, v["vyska_otvoru_mm"])
                short_desc = f"Hliníkový regál na euroboxy na míru pro {v['nazev_vozidla']}, na výběr tři skladby boxů."
                meta_title = f"Regál na euroboxy do {v['meta_vozidlo']}"
                meta_desc = (
                    f"Hliníkový regál na euroboxy do {v['nazev_vozidla']}. Tři skladby boxů "
                    "na výběr. Stavíme na míru na milimetr podle toho, co v autě vozíte."
                )

                cur.execute("SELECT id FROM shop_products WHERE sku=%s", (v["sku"],))
                existing = cur.fetchone()
                if existing:
                    karta_id = existing["id"]
                    print(f"  Karta uz existuje (id={karta_id}), preskakuji vytvoreni.")
                else:
                    karta_id = None
                    print(f"  Vytvarim kartu: {v['name']}")
                    if args.apply:
                        cur.execute(
                            "INSERT INTO shop_products "
                            "(category_id, sku, name, slug, description, short_description, "
                            " meta_title, meta_description, unit, availability_text, "
                            " price_visible_default, hover_show_price, hover_show_availability, active) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)",
                            (CATEGORY_ID, v["sku"], v["name"], v["slug"], popis, short_desc,
                             meta_title, meta_desc, "ks", "3 - 5 týdnů", 1, 1, 0),
                        )
                        karta_id = cur.lastrowid

                for aid in v["assembly_ids"]:
                    cur.execute(
                        "SELECT id, name, shop_product_id, technicky_ok, data FROM product_assemblies WHERE id=%s",
                        (aid,),
                    )
                    r = cur.fetchone()
                    if not r:
                        print(f"    id={aid}: sestava neexistuje, preskakuji"); continue
                    if r["technicky_ok"] != 1:
                        print(f"    id={aid}: technicky_ok!=1, POZOR preskakuji"); continue
                    if karta_id is not None and r["shop_product_id"] == karta_id:
                        print(f"    id={aid}: uz napojeno, preskakuji")
                        continue
                    is_master = 1 if aid == v["master_id"] else 0
                    print(f"    id={aid} ({r['name']}): -> karta {karta_id or '(nova)'}{' [MASTER]' if is_master else ''}")
                    zaloha.append({"karoserie": v["karoserie_kod"], "id": aid,
                                    "puvodni_shop_product_id": r["shop_product_id"]})
                    if args.apply:
                        cur.execute(
                            "UPDATE product_assemblies SET shop_product_id=%s, is_master=%s WHERE id=%s",
                            (karta_id, is_master, aid),
                        )

                # cena karty = master.price_summary.total_czk, pokud existuje
                if args.apply and karta_id:
                    cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (v["master_id"],))
                    d = json.loads(cur.fetchone()["data"] or "{}")
                    total = (d.get("price_summary") or {}).get("total_czk")
                    if total is not None:
                        cur.execute(
                            "UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s",
                            (round(total), karta_id),
                        )
                        print(f"  cena karty nastavena: {round(total)} Kč (ze zástupce {v['master_id']})")
                print()

        if args.apply:
            os.makedirs(ZALOHA_DIR, exist_ok=True)
            with open(os.path.join(ZALOHA_DIR, "pred_zapisem.json"), "w", encoding="utf-8") as f:
                json.dump(zaloha, f, ensure_ascii=False, indent=2, default=str)
            conn.commit()
            print("COMMIT hotovy.")
        else:
            print("DRY-RUN: nic nezapsano.")
    finally:
        conn.close()

    if args.apply:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                print("\n=== OVERENI z noveho spojeni ===")
                for v in VOZIDLA:
                    cur.execute(
                        "SELECT id, sku, name, active, price_czk_placeholder FROM shop_products WHERE sku=%s",
                        (v["sku"],),
                    )
                    karta = cur.fetchone()
                    print("Karta:", karta)
                    cur.execute(
                        f"SELECT COUNT(*) AS n FROM product_assemblies WHERE shop_product_id=%s",
                        (karta["id"],),
                    )
                    print("  napojenych sestav:", cur.fetchone()["n"], "(ocekavano 12)")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
