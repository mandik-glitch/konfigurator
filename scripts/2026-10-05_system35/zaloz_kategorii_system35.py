#!/usr/bin/env python3
"""Zalozeni kategorie "Ergonomicky balici stul system 35" (bot10, 2026-10-05).

Robert 2026-10-05: „pro generator stolu system 35 zaloz na kazdem webu novou kategorii: Ergonomicky balici stul system 35“ - domov tretiho generatoru stolu (profil 35x35, karta #4955),
sourozenec kategorii 206 „Lehky balici stul system 30“ a 311 „Robustni balici stul system 40“ pod 182 „Balicí stoly a pracoviste na miru“. Tenhle skript zalozi JEN KOSTRU: radek `content_categories` (nazev, adresa, nadrazena 182, viditelna).
ZADNE TEXTY (intro, meta, focus keyword, body) - ty skladá bot7 z overenych zdroju (TEXT_FILTR pravidlo 16 a 6); `content_pages` radek se nezaklada (vznikne pri prvnim ulozeni v adminu).

Stejne jako admin „Nova kategorie“ (`POST /api/categories`, api/categories.py): adresa = `_unique_category_slug(cur, _slugify(nazev))` z app.py/categories.py (jeden mechanismus, zadny vlastni slugify),
`sort_order` 1 (jako 206 a 311; razeni je `sort_order, name`, takze nova „Ergonomicky...“ je hned za 183 „Ergonomicke balici stoly SSE“ (0) a pred 206 „Lehky...“ a 311 „Robustni...“; sourozenci 226/289 s 2/3 zustavaji za ni - cizi radky se nemeni),
`is_visible` 1 (vychozi hodnota tabulky = totez, co by dostal Robert z formulare), `pending_review` 0 (nova kategorie je jeho zadani, ne navrh ke schvaleni).

  api/venv/bin/python3 scripts/2026-10-05_system35/zaloz_kategorii_system35.py            (nahled, nic nezapise)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-05_system35/zaloz_kategorii_system35.py --apply

Idempotentni: kategorie se stejnym nazvem pod stejnym rodicem se pouzije (nic se nezdvoji). Zapis se overuje rowcountem a cteni z noveho spojeni.
Zpet (jen kdyby Robert kategorii nechtel): `DELETE FROM content_categories WHERE id=<id>` (nema podkategorie ani stranku, FK ON DELETE CASCADE) - skript to NEPROVADI."""
import os
import sys
import threading

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
NAZEV = "Ergonomický balicí stůl system 35"
RODIC = 182          # „Balicí stoly a pracoviště na míru“ (sourozenci 206, 311)
SORT = 1             # jako 206 a 311; remiza se rozhodne podle nazvu
apply = "--apply" in sys.argv

if not os.environ.get("DB_HOST"):
    from _env import get_conn  # nahled bez systemd-run (cte jen)
    conn = get_conn()
    appmod = None
else:
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    import app as appmod  # noqa: E402
    import categories as catmod  # noqa: E402  (_unique_category_slug jako v admin route)
    threading.Thread.start = _o
    conn = appmod.get_conn()
cur = conn.cursor()
cur.execute("SELECT id, name FROM content_categories WHERE id=%s", (RODIC,))
rodic = cur.fetchone()
assert rodic, f"nadrazena kategorie {RODIC} neexistuje"
cur.execute("SELECT id, name, slug, parent_id, sort_order, is_visible FROM content_categories WHERE parent_id=%s AND name=%s", (RODIC, NAZEV))
existuje = cur.fetchone()
cur.execute("SELECT id, name, slug FROM content_categories WHERE name LIKE %s OR slug LIKE %s", ("%system 35%", "%system-35%"))
podobne = cur.fetchall()
print(f"rodic: #{rodic['id']} {rodic['name']}")
print("kategorie s timto nazvem pod rodicem:", existuje or "NEEXISTUJE")
print("podobne nazvy/adresy (kontrola dvojiti):", podobne or "zadne")
if not apply:
    cs = appmod._slugify(NAZEV) if appmod else "(adresa se spocita pri --apply z _slugify)"
    print(f"\nPo --apply vznikne: '{NAZEV}' pod #{RODIC}, adresa {cs}, sort_order {SORT}, viditelna, bez textu.")
    print("(nahled, nic nezapsano - zapis: --apply pres systemd-run, viz hlavicka)")
    sys.exit(0)

if existuje:
    cid = existuje["id"]
    print(f"kategorie uz existuje (#{cid}, {existuje['slug']}) - nic se nezapisuje")
else:
    cs = catmod._unique_category_slug(cur, appmod._slugify(NAZEV))
    cur.execute("INSERT INTO content_categories (parent_id, name, slug, sort_order) VALUES (%s,%s,%s,%s)", (RODIC, NAZEV, cs, SORT))
    if cur.rowcount != 1:
        conn.rollback()
        raise SystemExit(f"CHYBA: INSERT kategorie rowcount={cur.rowcount} - ROLLBACK")
    cid = cur.lastrowid
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                (None, "create", "category", cid, f"bot10: {NAZEV} (kostra bez textu; Robert 2026-10-05 - domov tretiho generatoru stolu, system 35)"))
    conn.commit()
c2 = appmod.get_conn().cursor()
c2.execute("SELECT id, parent_id, name, slug, sort_order, is_visible, pending_review, meta_title, image_filename FROM content_categories WHERE id=%s", (cid,))
k = c2.fetchone()
assert k and k["parent_id"] == RODIC and k["name"] == NAZEV and k["is_visible"] == 1, k
print(f"zapsano a overeno z noveho spojeni: #{k['id']} '{k['name']}' pod #{k['parent_id']}, adresa /{k['slug']}, sort_order {k['sort_order']}, viditelna, pending_review {k['pending_review']}")
print(f"URL: https://autovestavby.logiman.cz/{k['slug']}")
