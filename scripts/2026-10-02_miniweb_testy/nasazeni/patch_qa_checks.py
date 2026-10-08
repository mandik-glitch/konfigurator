#!/usr/bin/env python3
"""Patch api/qa_checks.py: pridava kontrolu miniweb_text_brand_leak (bot5, 2026-10-02). Opakovatelne (kdyz uz je, nic nedela). Pouziti: patch_qa_checks.py <cesta k qa_checks.py>"""
import sys

p = sys.argv[1]
t = open(p, encoding="utf-8").read()
if "check_miniweb_text_brand_leak" in t:
    print("qa_checks: miniweb_text_brand_leak uz je")
    sys.exit(0)

FUNKCE = '''def check_miniweb_text_brand_leak(cur):
    # bot5 2026-10-02 (TEXT_FILTR pravidlo 5, bot3: mini-shop Packstations je BEZ znacky): texty mini-shopu - nazvy kategorii, texty produktu v kazdem jazyce (i koncepty), parametry, verejny kod,
    # adresy, kontakt shopu a adresa jeho domeny - nesmi nest znacku ani dodavatele. Zdroj pravdy o tom, co je znacka, je dealers._BRAND_RE (stejny regex pouziva verejne API /api/miniweb/*
    # a dealersky program). API takovou polozku verejne SKRYJE (fail closed: produkt se znackou se nevyda, kategorie se znackou i s podkategoriemi), zakaznik by proto videl jen tise chybejici
    # produkt. Tahle kontrola ukaze, KTERY text to je, aby se opravil u zdroje (anglicke texty dodava bot7, schvaluje Robert). Jedina vyjimka je legal.seller (zakonny udaj), ten v DB neni.
    import app  # noqa: F401 - NEJDRIV cely app (poradi importu), az pak dealers: import dealers jako prvni konci kruhovym importem dealers <-> app (v serveru je app uz nacteny)
    import dealers  # lazy: nedostupnost modulu shodi jen tuhle kontrolu (run_checks ji odchyti)
    hit = dealers._brand_hit
    out = []
    cur.execute(
        "SELECT t.miniweb_category_id AS id, t.lang, t.name, c.slug FROM miniweb_category_texts t "
        "JOIN miniweb_categories c ON c.id = t.miniweb_category_id ORDER BY t.miniweb_category_id, t.lang"
    )
    for r in cur.fetchall():
        for field in ("name", "slug"):
            if hit(r[field]):
                out.append((f"kategorie:{r['id']}:{r['lang']}:{field}", f"miniweb_category_texts:{r['slug']}",
                            f"pole '{field}' (jazyk {r['lang']}) zmiňuje značku/dodavatele (pravidlo 5) - API kategorii i s podkategoriemi veřejně skrývá"))
    cur.execute(
        "SELECT t.miniweb_product_id AS id, t.lang, t.name, t.summary, t.description, t.delivery, t.specs_json, p.slug, p.public_sku "
        "FROM miniweb_product_texts t JOIN miniweb_products p ON p.id = t.miniweb_product_id ORDER BY t.miniweb_product_id, t.lang"
    )
    for r in cur.fetchall():
        for field in ("name", "summary", "description", "delivery", "specs_json", "slug", "public_sku"):
            if hit(r[field]):
                out.append((f"produkt:{r['id']}:{r['lang']}:{field}", f"miniweb_product_texts:{r['slug']}",
                            f"pole '{field}' (jazyk {r['lang']}) zmiňuje značku/dodavatele (pravidlo 5) - API produkt veřejně skrývá"))
    cur.execute("SELECT m.storefront_id AS id, m.contact_json, s.slug, s.primary_domain FROM miniweb_shops m JOIN car_storefronts s ON s.id = m.storefront_id ORDER BY m.storefront_id")
    for r in cur.fetchall():
        for field in ("contact_json", "slug", "primary_domain"):
            if hit(r[field]):
                out.append((f"shop:{r['id']}:{field}", f"miniweb_shops:{r['slug']}",
                            f"pole '{field}' zmiňuje značku/dodavatele (pravidlo 5) - API ho veřejně neuvádí (kontakt prázdný, odkaz na jazykovou verzi a slug neutrální)"))
    return out


'''

# 1) funkce pred sekci "Staticke stranky sdilene s anonymnimi domenami"
a = '# --- Staticke stranky sdilene s anonymnimi domenami (bot16, 2026-10-01'
assert t.count(a) == 1, "kotva funkce"
t = t.replace(a, FUNKCE + a)

# 2) tri registry (CHECKS, CHECK_CATEGORY, CHECK_ADDED)
for stary, novy in (
    ('    "static_page_brand_leak": ("Statická stránka sdílená s anonymními doménami zmiňuje mateřskou firmu", check_static_page_brand_leak),\n',
     '    "miniweb_text_brand_leak": ("Text mini-shopu zmiňuje značku/dodavatele (API ho veřejně skrývá)", check_miniweb_text_brand_leak),\n'),
    ('    "static_page_brand_leak": "opravit",\n', '    "miniweb_text_brand_leak": "opravit",\n'),
    ('    "static_page_brand_leak": "2026-10-01",\n', '    "miniweb_text_brand_leak": "2026-10-02",\n'),
):
    assert t.count(stary) == 1, f"kotva registru: {stary[:50]}"
    t = t.replace(stary, stary + novy)
open(p, "w", encoding="utf-8").write(t)
print("qa_checks: pridana kontrola miniweb_text_brand_leak")
