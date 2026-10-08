#!/usr/bin/env python3
"""Prevede kategorii 196 "Krycí lišty drážek" (39 produktu) z dnesniho
DOPOLEDNIHO "tyc 3m" fixu (commit 0bda7d96) na FINALNI "metraz" model
(Robert pres bot3, 2026-09-24, "podle DOGUSICH SEKCI" - sekce 84
profile-seals = metraz, viz sql/2026-09-24e_content_categories_
dogus_sale_unit.sql). Zpetne odectena dnesni "tyc 3m" uprava, aplikovan
metrazovy model:

- unit: 'ks' -> 'm' (unit je cisty display label, VZDY overeno grepem -
  zadny kod v cart.py/orders.py/documents.py na presnou hodnotu retezce
  nevetvi, jen ho vypisuje vedle ceny; mnozstvi zustava cele cislo -
  "1 m" jednotky presne jako drivejsi "1 ks", zadna nova logika netreba).
- price_czk_placeholder: ceil(dogus_list_price_usd x kurz_zivy x koef),
  BEZ x3 (Robert: "celé koruny vždy nahoru" plati pro vsechny 3 skupiny).
- weight_g: DELENO 3 (dnes rano vynasobeno x3 na celou 3m tyc, ted zpet
  na hmotnost za 1 m - presne hodnota, kterou uz description sama
  obsahuje jako "hmotnost cca X g/m").
- is_profile_material: 1 -> 0 (metraz neni "tyc na 3m", nema prirezy ani
  "1 ks = 3000 mm" - overeno pred zapisem, na co vsechno flag u
  kategorie 196 dnes visel: jen unit_price_per_m_czk/unit_weight_per_m_kg
  vypocet v products.py (fired jen kdyz uz je is_profile_material,
  prestane se pocitat - v poradku, u metraze davaji smysl primo
  price_czk_placeholder/weight_g uz jako "za 1 m") a przirezy UI
  (product.html isProfile - prestane se nabizet, spravne, metraz se
  neresi jako "rez z tyce").
- description: prepsana ze "Standardní délka tyče 3000 mm (3 m),
  hmotnost cca X g/m" na "Prodává se na metry (cena za 1 m), hmotnost
  cca X g/m" - X hodnota se preziva 1:1 (uz byla za 1 m).

Zaloha pred zapisem, rowcount kazdeho UPDATE overen.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-24_bot5_kategorie196_na_metraz.py
    api/venv/bin/python3 scripts/2026-09-24_bot5_kategorie196_na_metraz.py --apply
"""
import argparse
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api"))
from _env import get_conn  # noqa: E402
from fio_rate import fetch_fio_usd_czk_sell_rate  # noqa: E402

CATEGORY_ID = 196
BACKUP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-24_kategorie196_na_metraz_pred_zapisem.json",
)

DESC_RE = re.compile(
    r"^(?P<head>.+? \(z materiálu [^,]+, barva [^,)]+\))\. "
    r"Standardní délka tyče 3000 mm \(3 m\), hmotnost cca (?P<w>[\d.,]+) g/m\.\s*(?P<tail>.+)$"
)


def _novy_popis(stary):
    m = DESC_RE.match(stary or "")
    if not m:
        return None, None
    w = m.group("w")
    return f"{m.group('head')}. Prodává se na metry (cena za 1 m), hmotnost cca {w} g/m. {m.group('tail')}", w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Kategorie 196 -> METRAZ — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    fio_rate = fetch_fio_usd_czk_sell_rate()
    print(f"Kurz Fio banka USD/CZK (prodej), živá hodnota: {fio_rate}\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT dogus_price_coefficient FROM content_categories WHERE id=%s", (CATEGORY_ID,))
            coef = float(cur.fetchone()["dogus_price_coefficient"])
            print(f"Koeficient kategorie {CATEGORY_ID}: {coef}\n")

            cur.execute(
                "SELECT id, sku, name, description, weight_g, price_czk_placeholder, "
                "is_profile_material, unit, dogus_list_price_usd "
                "FROM shop_products WHERE category_id=%s ORDER BY id",
                (CATEGORY_ID,),
            )
            rows = cur.fetchall()
            print(f"Produktů v kategorii: {len(rows)}\n")

            zmeny, chyby = [], []
            for r in rows:
                if r["dogus_list_price_usd"] is None or r["weight_g"] is None:
                    chyby.append((r["id"], r["sku"], "chybí dogus_list_price_usd nebo weight_g"))
                    continue
                novy_popis, w_za_m = _novy_popis(r["description"])
                if novy_popis is None:
                    chyby.append((r["id"], r["sku"], f"popis nesedí na dnešní (tyč 3m) vzor: {r['description']!r}"))
                    continue
                usd = float(r["dogus_list_price_usd"])
                novy_kod = math.ceil(usd * fio_rate * coef)
                nova_hmotnost = round(float(r["weight_g"]) / 3.0, 3)
                zmeny.append({
                    "id": r["id"], "sku": r["sku"], "name": r["name"],
                    "old_price_czk": float(r["price_czk_placeholder"]), "new_price_czk": novy_kod,
                    "old_weight_g": float(r["weight_g"]), "new_weight_g": nova_hmotnost,
                    "old_unit": r["unit"], "new_unit": "m",
                    "old_is_profile_material": r["is_profile_material"],
                    "old_description": r["description"], "new_description": novy_popis,
                    "usd": usd, "fio_rate": fio_rate, "coef": coef,
                })
                print(f"[{r['id']}] {r['sku']}: {usd} USD/m x {fio_rate} x {coef} = {usd*fio_rate*coef:.4f} -> "
                      f"ceil={novy_kod} Kč/m (bylo {r['price_czk_placeholder']} Kč/ks-3m); "
                      f"hmotnost {r['weight_g']}g -> {nova_hmotnost}g/m")

            if chyby:
                print(f"\nCHYBY ({len(chyby)}) - PŘESKOČENY:")
                for id_, sku, msg in chyby:
                    print(f"  [{id_}] {sku}: {msg}")

            if args.apply and zmeny:
                os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
                with open(BACKUP_PATH, "w", encoding="utf-8") as f:
                    json.dump(zmeny, f, ensure_ascii=False, indent=2)
                print(f"\nZáloha zapsána do {BACKUP_PATH}")
                for z in zmeny:
                    cur.execute(
                        "UPDATE shop_products SET unit='m', is_profile_material=0, price_czk_placeholder=%s, "
                        "weight_g=%s, description=%s, dogus_price_rate_used=%s, price_last_refreshed_at=NOW() "
                        "WHERE id=%s",
                        (z["new_price_czk"], z["new_weight_g"], z["new_description"], fio_rate, z["id"]),
                    )
                    if cur.rowcount != 1:
                        raise RuntimeError(f"UPDATE id={z['id']} zasáhl {cur.rowcount} řádků místo 1 - rollback")
                conn.commit()
                print(f"\nHOTOVO: zapsáno {len(zmeny)} produktů.")
            elif not args.apply:
                print(f"\nDRY-RUN: bylo by upraveno {len(zmeny)} produktů (spusť s --apply pro zápis).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
