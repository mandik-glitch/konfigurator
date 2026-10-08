#!/usr/bin/env python3
"""Prejmenuje 5 Vandr karet, kde je v nazvu holy rozmer vozidla (rozvor
naprav) bez oznaceni - zakaznik si domysli, ze je to rozmer regalu.
Robert primo (pres bot8, ktery nalez zjistil a overil proti karoserie_
model_reference.wheelbase_mm, 8x presna shoda): "dopiseme to do nazvu:
.... pro Trafic L1H1 (rozvor 3098 mm)".

Zmena JEN name + short_description (stejny vzor "(rozvor X mm)"
pridany k existujicimu textu). Slug NEMENIME u ctyr z peti - PUT
/api/shop/products/<id> (api/products.py::shop_products_update)
slug pri zmene name VUBEC neprepocitava (overeno cteni kodu - zadna
zminka o `slug` v cele funkci), takze zadny redirect neni treba, URL
zustavaji funkcni presne jak jsou.

VYJIMKA #4904: slug je dnes NULL i pres active=1 (samostatna vada,
zjistil bot8) - bez slugu produkt neni dostupny na /produkt/<slug>.
Tady se slug DOPLNI (poprve, ne zmena) pres stejnou funkci jako
admin pri vytvoreni karty (_unique_product_slug).

Zaloha pred zapisem, rowcount kazdeho UPDATE overen.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-25_bot5_vandr_rozvor_v_nazvu.py
    api/venv/bin/python3 scripts/2026-09-25_bot5_vandr_rozvor_v_nazvu.py --apply
"""
import argparse
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402


def _slugify(text):
    """1:1 kopie api/app.py::_slugify - nezavisla na Flask app importu
    (lehky standalone skript, viz scripts/_env.py konvence)."""
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "kategorie"


def _unique_product_slug(cur, base):
    """1:1 kopie api/app.py::_unique_product_slug."""
    base = base or "produkt"
    candidate = base
    n = 2
    while True:
        cur.execute("SELECT id FROM shop_products WHERE slug=%s", (candidate,))
        if not cur.fetchone():
            return candidate
        candidate = f"{base}-{n}"
        n += 1

BACKUP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-25_vandr_rozvor_v_nazvu_pred_zapisem.json",
)

ZMENY = {
    4903: {
        "name": "Fiat Ducato L1H1 (rozvor 3000 mm)",
        "short_description": "Hliníková regálová vestavba pro Fiat Ducato L1H1 (rozvor 3000 mm), cena bez montáže.",
    },
    4904: {
        "name": "Renault Trafic L1H1 (rozvor 3098 mm)",
        "short_description": "Hliníková regálová vestavba pro Renault Trafic L1H1 (rozvor 3098 mm), cena bez montáže.",
    },
    4905: {
        "name": "Mercedes Sprinter L2H2 FWD (rozvor 3665 mm)",
        "short_description": "Hliníková regálová vestavba pro Mercedes Sprinter L2H2 FWD (rozvor 3665 mm), cena bez montáže.",
    },
    4906: {
        "name": "Ford Transit Custom L1H1 (rozvor 3300 mm)",
        "short_description": "Hliníková regálová vestavba pro Ford Transit Custom L1H1 (rozvor 3300 mm), cena bez montáže.",
    },
    4907: {
        "name": "Fiat Ducato L2H2 (rozvor 3450 mm)",
        "short_description": "Hliníková regálová vestavba pro Fiat Ducato L2H2 (rozvor 3450 mm), cena bez montáže.",
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Vandr karty: rozvor v nazvu — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sku, name, slug, short_description FROM shop_products WHERE id IN (%s)"
                % ",".join(str(i) for i in ZMENY),
            )
            rows = {r["id"]: r for r in cur.fetchall()}

            zaznamy = []
            for pid, novy in ZMENY.items():
                stary = rows.get(pid)
                if not stary:
                    print(f"  ⛔ id={pid}: nenalezeno, přeskakuji")
                    continue
                novy_slug = stary["slug"]
                if novy_slug is None:
                    novy_slug = _unique_product_slug(cur, _slugify(novy["name"]))
                    print(f"[{pid}] {stary['sku']}: slug CHYBĚL -> nově '{novy_slug}'")
                zaznamy.append({
                    "id": pid, "sku": stary["sku"],
                    "old_name": stary["name"], "new_name": novy["name"],
                    "old_short_description": stary["short_description"], "new_short_description": novy["short_description"],
                    "old_slug": stary["slug"], "new_slug": novy_slug,
                })
                print(f"[{pid}] {stary['sku']}:")
                print(f"    name: {stary['name']!r} -> {novy['name']!r}")
                print(f"    short_description: {stary['short_description']!r} -> {novy['short_description']!r}")
                print(f"    slug: {stary['slug']!r} -> {novy_slug!r} ({'BEZE ZMĚNY' if novy_slug == stary['slug'] else 'DOPLNĚN'})")

            if args.apply and zaznamy:
                os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
                with open(BACKUP_PATH, "w", encoding="utf-8") as f:
                    json.dump(zaznamy, f, ensure_ascii=False, indent=2)
                print(f"\nZáloha zapsána do {BACKUP_PATH}")
                for z in zaznamy:
                    cur.execute(
                        "UPDATE shop_products SET name=%s, short_description=%s, slug=%s WHERE id=%s",
                        (z["new_name"], z["new_short_description"], z["new_slug"], z["id"]),
                    )
                    if cur.rowcount != 1:
                        raise RuntimeError(f"UPDATE id={z['id']} zasáhl {cur.rowcount} řádků místo 1 - rollback")
                conn.commit()
                print(f"\nHOTOVO: zapsáno {len(zaznamy)} karet.")
            elif not args.apply:
                print(f"\nDRY-RUN: bylo by upraveno {len(zaznamy)} karet (spusť s --apply pro zápis).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
