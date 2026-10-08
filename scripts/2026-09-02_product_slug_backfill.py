#!/usr/bin/env python3
"""Doplneni slugu produktum, ktere ho nemaji (bot15/bot3, 2026-09-02, QA
seo.py SEO_SITEMAP_QUERY_URL: 9 aktivnich produktu id 3787-3796 melo v
sitemape product.html?id=).

Pricina: jednorazovy backfill slugu (commit 4e1267d, 2026-08-09) probehl
jen nad tehdejsimi produkty a zadna INSERT cesta slug nenastavovala -
opraveno v api/app.py (navrh sestavy) a api/products.py (admin karta, CSV
import). Tenhle skript je idempotentni doplnek pro uz existujici radky;
stejny _slugify + unikatni sufix jako app._unique_product_slug.

Pouziti:  api/venv/bin/python scripts/2026-09-02_product_slug_backfill.py [--dry-run] [--include-inactive]
Vychozi jen active=1 AND is_archived=0 (neaktivni nocni davky sestav se
mohou jeste prejmenovat - slug jim vznikne az pri aktivaci/rucne).
"""
import argparse
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402


def _slugify(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "produkt"


def _unique(cur, base, taken):
    candidate, n = base, 2
    while True:
        if candidate not in taken:
            cur.execute("SELECT id FROM shop_products WHERE slug=%s", (candidate,))
            if not cur.fetchone():
                taken.add(candidate)
                return candidate
        candidate = f"{base}-{n}"
        n += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-inactive", action="store_true")
    args = ap.parse_args()
    where = "" if args.include_inactive else " AND active=1 AND is_archived=0"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, name FROM shop_products WHERE (slug IS NULL OR slug='') {where} ORDER BY id")
            rows = cur.fetchall()
            taken = set()
            for r in rows:
                slug = _unique(cur, _slugify(r["name"]), taken)
                print(f"{r['id']}\t{r['name']!r}\t-> {slug}")
                if not args.dry_run:
                    cur.execute("UPDATE shop_products SET slug=%s WHERE id=%s AND (slug IS NULL OR slug='')", (slug, r["id"]))
        if args.dry_run:
            conn.rollback()
            print(f"dry-run: {len(rows)} produktu by dostalo slug")
        else:
            conn.commit()
            print(f"hotovo: {len(rows)} produktu dostalo slug")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
