"""
Adresy (slugy) produktu - JEDINY mechanismus, ktery je tvori a meni (bot5, 2026-10-01).
Robert: "aby se prostě strojově vytvářely pěkné URL adresy pro SEO, ale ne ručně botem".

Cisty modul BEZ Flask/app zavislosti (kurzor = DictCursor), takze se testuje v docasnych tabulkach
(`scripts/2026-09-30_duplikace_produktu_testy/test_product_slug.py`). COMMIT/ROLLBACK DELA VOLAJICI.

PRAVIDLA
  * slug vznika z AKTUALNIHO zakaznickeho nazvu: bez diakritiky, male pismo, pomlcky, nejvys MAX_LEN znaku
    (na hranici slova); interni nazvy (DROP_TOKENS) se do adresy nikdy nedostanou;
  * unikatnost: `-2`, `-3`... A nova adresa nesmi byt ani ZNOVU POUZITA stara adresa jineho produktu (jeji
    presmerovani by pak vedlo na spatny produkt);
  * kazda zmena adresy ZAROVEN zapise 301: stara adresa -> `shop_product_redirects` (cte ji `/produkt/<slug>`
    v storefront_pages.py). Do teto tabulky dosud nezapisoval zadny kod, jediny radek tam byl vlozeny rucne;
  * adresa SLEDUJE nazev: prejmenovani v karte -> nova adresa + 301 (products.py), hromadne sjednoceni
    starych/rozjetych adres -> `proposals` + `apply` (admin tlacitko "Sjednotit adresy");
  * vsechny cesty, ktere zakladaji produkt (api i skripty), maji pouzit `slug_for_name`, ne vlastni slugify
    (v repu je jich desitky a nektere slug nenastavuji vubec).
"""
import re
import unicodedata

MAX_LEN = 70
# Interni nazev dodavatele systemu - v zakaznicke adrese nema co delat (92 verejnych adres koncilo na "-vandrawee",
# protoze vznikly z puvodnich nazvu, ktere se pozdeji vycistily, adresy ale zustaly).
DROP_TOKENS = ("vandrawee",)


def slugify(text):
    """Nazev -> zaklad adresy. Prazdny retezec, kdyz z nazvu nic zbyde (volajici pouzije 'produkt')."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    out = ""
    for part in t.split("-"):
        if not part or part in DROP_TOKENS:
            continue
        cand = part if not out else out + "-" + part
        if out and len(cand) > MAX_LEN:
            break                                  # dalsi slovo uz se nevejde - zkratit na hranici slova
        out = cand[:MAX_LEN]
    return out


def _taken(cur, slug, exclude_id):
    """Je adresa obsazena aktualnim slugem NEBO starou (presmerovanou) adresou JINEHO produktu?"""
    if exclude_id is None:
        cur.execute("SELECT 1 FROM shop_products WHERE slug=%s UNION ALL "
                    "SELECT 1 FROM shop_product_redirects WHERE old_slug=%s LIMIT 1", (slug, slug))
    else:
        cur.execute("SELECT 1 FROM shop_products WHERE slug=%s AND id<>%s UNION ALL "
                    "SELECT 1 FROM shop_product_redirects WHERE old_slug=%s AND product_id<>%s LIMIT 1",
                    (slug, exclude_id, slug, exclude_id))
    return cur.fetchone() is not None


def unique_slug(cur, base, exclude_id=None):
    base = base or "produkt"
    candidate, n = base, 2
    while _taken(cur, candidate, exclude_id):
        candidate = f"{base}-{n}"
        n += 1
        if n > 1000:
            raise RuntimeError("Nepodarilo se najit volnou adresu produktu.")
    return candidate


def slug_for_name(cur, name, exclude_id=None):
    """Adresa noveho/prejmenovaneho produktu z nazvu (zaklad + unikatni sufix)."""
    return unique_slug(cur, slugify(name) or "produkt", exclude_id)


def has_internal_token(slug):
    parts = (slug or "").split("-")
    return any(tok in parts for tok in DROP_TOKENS)


def is_stale(name, slug):
    """Adresa neodpovida nazvu (chybi, nebo vznikla z jineho/stareho nazvu). Pripona `-N` je jen citac kolizi."""
    if not slug:
        return True
    base = slugify(name) or "produkt"
    return not (slug == base or re.fullmatch(re.escape(base) + r"-\d+", slug))


def change_slug(cur, product_id, new_slug):
    """Zmeni adresu produktu a ZAROVEN zapise 301 ze stare. Vraci True, kdyz se zmenila."""
    cur.execute("SELECT slug FROM shop_products WHERE id=%s", (product_id,))
    row = cur.fetchone()
    old = row["slug"] if row else None
    if old == new_slug:
        return False
    cur.execute("UPDATE shop_products SET slug=%s WHERE id=%s", (new_slug, product_id))
    if old:
        cur.execute("INSERT IGNORE INTO shop_product_redirects (old_slug, product_id) VALUES (%s,%s)", (old, product_id))
    # navrat na drivejsi adresu tehoz produktu: nesmi zaroven zustat jako presmerovani sama na sebe
    cur.execute("DELETE FROM shop_product_redirects WHERE old_slug=%s AND product_id=%s", (new_slug, product_id))
    return True


def proposals(cur, ids=None):
    """Verejne produkty (aktivni, nearchivovane), jejichz adresa chybi, obsahuje interni nazev nebo neodpovida nazvu."""
    sql = "SELECT id, name, slug FROM shop_products WHERE active=1 AND is_archived=0"
    params = []
    if ids:
        sql += " AND id IN (" + ",".join(["%s"] * len(ids)) + ")"
        params = list(ids)
    cur.execute(sql + " ORDER BY id", params)
    out = []
    for r in cur.fetchall():
        if r["slug"] and has_internal_token(r["slug"]):
            duvod = "interni"
        elif not r["slug"]:
            duvod = "chybi"
        elif is_stale(r["name"], r["slug"]):
            duvod = "nesedi"
        else:
            continue
        out.append({"id": r["id"], "name": r["name"], "old": r["slug"], "reason": duvod})
    return out


def apply(cur, items):
    """Prepise adresy podle `proposals` (nova adresa se pocita ZNOVU z nazvu, ne z navrhu). Nekomituje."""
    zmeny = []
    for it in items:
        new = slug_for_name(cur, it["name"], exclude_id=it["id"])
        if change_slug(cur, it["id"], new):
            zmeny.append({"id": it["id"], "name": it["name"], "old": it["old"], "new": new, "reason": it["reason"]})
    return zmeny
