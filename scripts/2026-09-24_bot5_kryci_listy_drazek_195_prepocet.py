#!/usr/bin/env python3
"""Oprava kategorie 196 "Krycí lišty drážek" (39 produktu) - Robert pres
bot3, WORKFLOW.md pravidlo 52, resit hned. Robert doslova: "je to jako u
profilů, tzn, cena dogus je za 1m, a 1ks jsou 3metry".

Nalez (bot3, overeno zde znovu): vsech 39 produktu ma is_profile_material=0,
unit='ks', length_mm=NULL, category_id=196, category dogus_price_coefficient=1,200.
Ceny byly v kategorii NEKONZISTENTNI - cast spoctena profilovym vzorcem (x3),
cast ne-profilovym vzorcem (ceil, bez x3), i kdyz maji STEJNOU dogus_list_price_usd.

Rozhodnuti (bot5, zdokumentovano zde, ne tise): is_profile_material=1 pro
vsech 39 - NE jen kosmeticky "lista v nazvu" vyjimka jako u
2026-08-09_dogus_price_recompute.py (ta zamerne NEMENI is_profile_material,
protoze pro sirokou mnozinu ruznych kategorii nechtela zapnout prirezy
"kde to s tim vubec nesouvisi"). Tady je to jina situace: CELA kategorie
196 ("profile-seals" na Dogus - stejna kategorie jako profily, ne nahodna
shoda), Robert current a vyslovne rekl "je to jako u profilu" pro CELOU
kategorii, a zive overeno na strance produktu (napr.
https://en.doguskalip.com.tr/Urun/2713/slot-seal---slot-6) - ma vlastni
JS kalkulacku "zadej delku v mm -> cena a hmotnost se dopocitaji linearne"
(funkce go(a,b,c,d,e), vzorec cena=mm*strokPrm+strokSabit,
hmotnost=(mm*agirlikPrm+agirlikSabit)/1000), presne jako u profilu -
tohle NENI kusove zbozi, je to delkove zbozi prodavane Dogusem po metrech,
Robertovo "je to jako u profilu" je doslova pravda, ne jen analogie.
Vedlejsi efekt zapnuti is_profile_material=1 (prirezy na miru v kosiku) je
proto SPRAVNE chovani, ne omylem povolena funkce.

VZOREC (WORKFLOW pravidlo 9, profilova vetev):
  cena_za_m_czk = dogus_list_price_usd * kurz_fio_prodej
  cena_za_ks_czk = round(cena_za_m_czk * koeficient * 3)
Kurz ZIVE pres api/fio_rate.py::fetch_fio_usd_czk_sell_rate() (bot16,
nikdy nehardcodovat), zapsan i do dogus_price_rate_used.
dogus_list_price_usd se NEMENI (uz je spravne v DB, staci prepocitat
vysledek se stavajici hodnotou + cerstvym kurzem - zadny duvod znovu
scrapovat Dogus, cena v USD nebyla zpochybnena).

HMOTNOST (bod 3 zadani, doloze­no ne odhadem): stavajici weight_g je 1:1
kopie Dogus "Weight (gr)" bez nasobeni - overeno na 20x20 Sigma profile
(nase weight_g=1170 = Dogus "Mass: 0.39 kg/m" * 1000 * 3), TOTOZNY vzor
jako u vsech ostatnich profilu - weight_g v nasi DB VZDY predstavuje
CELOU 3m tyc, popis pak ukazuje weight_g/3000 jako "kg/m". Dogus u
profilu-tesneni (kategorie "profile-seals") vyjadruje hmotnost STEJNYM
zpusobem jako u profilu (viz JS kalkulacka vyse - hmotnost roste
linearne s delkou v mm, presne jako cena), jen bez explicitniho "/m" v
popisku tabulky (jina HTML sablona nez cisté profily). Proto: NOVE
weight_g = stavajici weight_g (= Dogus "Weight (gr)" za 1 m) * 3.

POPIS: prepsan do STEJNE sablony jako u realnych profilu (overeno na
SKU 1.1.06.020020.01): "<nazev> (z materiálu <mat>, barva <barva>).
Standardní délka tyče 3000 mm (3 m), hmotnost cca <W> g/m. <zbytek>." -
"3000 mm" tak projde i api/qa_checks.py::check_profile_wrong_length_claim
(regex "délka tyče (\\d+) mm" ocekava presne 3000).

Zaloha PRED zapisem (pravidlo backup pred content fixem) do
backups/2026-09-24_kryci_listy_drazek_pred_prepoctem.json. Rowcount
kazdeho UPDATE overen (1 radek), jinak chyba.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-24_bot5_kryci_listy_drazek_195_prepocet.py
    api/venv/bin/python3 scripts/2026-09-24_bot5_kryci_listy_drazek_195_prepocet.py --apply
"""
import argparse
import json
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
    "backups", "2026-09-24_kryci_listy_drazek_pred_prepoctem.json",
)

DESC_RE = re.compile(
    r"^(?P<head>.+?) \(z materiálu (?P<mat>[^,]+), barva (?P<barva>[^,]+), "
    r"hmotnost cca (?P<w>[\d.,]+) g\)\.\s*(?P<tail>.+)$"
)


def _novy_popis(stary, w_za_m):
    m = DESC_RE.match(stary or "")
    if not m:
        return None
    w_str = f"{w_za_m:g}"
    return (f"{m.group('head')} (z materiálu {m.group('mat')}, barva {m.group('barva')}). "
            f"Standardní délka tyče 3000 mm (3 m), hmotnost cca {w_str} g/m. {m.group('tail')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Krycí lišty drážek (kat. {CATEGORY_ID}) - prepocet — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    fio_rate = fetch_fio_usd_czk_sell_rate()
    print(f"Kurz Fio banka USD/CZK (prodej), ziva hodnota: {fio_rate}\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT dogus_price_coefficient FROM content_categories WHERE id=%s", (CATEGORY_ID,))
            cat = cur.fetchone()
            if not cat or cat["dogus_price_coefficient"] is None:
                print("CHYBA: kategorie nema dogus_price_coefficient, koncim.")
                return 1
            coef = float(cat["dogus_price_coefficient"])
            print(f"Koeficient kategorie {CATEGORY_ID}: {coef}\n")

            cur.execute(
                "SELECT id, sku, name, description, is_profile_material, unit, weight_g, "
                "price_czk_placeholder, dogus_list_price_usd, dogus_price_rate_used "
                "FROM shop_products WHERE category_id=%s ORDER BY id",
                (CATEGORY_ID,),
            )
            rows = cur.fetchall()
            print(f"Produktů v kategorii: {len(rows)}\n")

            zmeny, chyby = [], []
            for r in rows:
                if r["dogus_list_price_usd"] is None:
                    chyby.append((r["id"], r["sku"], "chybí dogus_list_price_usd"))
                    continue
                if r["weight_g"] is None:
                    chyby.append((r["id"], r["sku"], "chybí weight_g"))
                    continue
                usd = float(r["dogus_list_price_usd"])
                cena_za_m = usd * fio_rate
                novy_kod = round(cena_za_m * coef * 3)
                nova_hmotnost_za_m = float(r["weight_g"])  # stavajici = uz za 1 m (viz docstring)
                nova_hmotnost_celkem = round(nova_hmotnost_za_m * 3, 3)
                novy_popis = _novy_popis(r["description"], nova_hmotnost_za_m)
                if novy_popis is None:
                    chyby.append((r["id"], r["sku"], f"popis nesedí na očekávaný vzor: {r['description']!r}"))
                    continue
                zmeny.append({
                    "id": r["id"], "sku": r["sku"], "name": r["name"],
                    "old_price_czk": float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None,
                    "new_price_czk": novy_kod,
                    "old_weight_g": float(r["weight_g"]), "new_weight_g": nova_hmotnost_celkem,
                    "old_description": r["description"], "new_description": novy_popis,
                    "old_is_profile_material": r["is_profile_material"],
                    "dogus_list_price_usd": usd, "fio_rate": fio_rate, "coef": coef,
                })
                print(f"[{r['id']}] {r['sku']}: {usd} USD/m x {fio_rate} x {coef} x 3 = "
                      f"{cena_za_m * coef * 3:.4f} -> {novy_kod} Kč (bylo {r['price_czk_placeholder']}); "
                      f"hmotnost {r['weight_g']}g/m -> {nova_hmotnost_celkem}g/3m")

            if chyby:
                print(f"\nCHYBY ({len(chyby)}) - PRESKOCENY, needituji:")
                for id_, sku, msg in chyby:
                    print(f"  [{id_}] {sku}: {msg}")

            if args.apply and zmeny:
                os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
                with open(BACKUP_PATH, "w", encoding="utf-8") as f:
                    json.dump(zmeny, f, ensure_ascii=False, indent=2)
                print(f"\nZáloha zapsána do {BACKUP_PATH}")

                for z in zmeny:
                    cur.execute(
                        "UPDATE shop_products SET is_profile_material=1, price_czk_placeholder=%s, "
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
