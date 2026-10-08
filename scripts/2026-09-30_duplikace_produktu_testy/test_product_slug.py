#!/opt/konfigurator/api/venv/bin/python
"""Test mechanismu adres produktu (api/product_slug.py) nad DOCASNYMI tabulkami - nic se nezapisuje do ostrych dat.
Pro soubezne spojeni se vytvori TEMPORARY tabulky shop_products a shop_product_redirects (stini ostre, stejne indexy,
bez FK), modul bezi nad nimi; na konci se na NOVEM spojeni overi, ze ostre tabulky se nezmenily.

Spusteni (DB prihlaseni pres systemd, ne cteni api/.env):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
    --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \
    scripts/2026-09-30_duplikace_produktu_testy/test_product_slug.py
"""
import os
import sys

import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "api"))
import product_slug as ps  # noqa: E402

TABULKY = ["shop_products", "shop_product_redirects"]
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def connect():
    return pymysql.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)),
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def ostry_stav():
    c = connect()
    try:
        with c.cursor() as cur:
            st = {}
            for t in TABULKY:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                st[t] = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM shop_products WHERE sku LIKE 'ZZSLUG-%'")
            st["testovaci_sku"] = cur.fetchone()["n"]
    finally:
        c.close()
    return st


def vloz(cur, sku, name, slug, active=1, archived=0):
    cur.execute("INSERT INTO shop_products (sku, name, slug, active, is_archived) VALUES (%s,%s,%s,%s,%s)",
                (sku, name, slug, active, archived))
    return cur.lastrowid


def slug_z_db(cur, id_):
    cur.execute("SELECT slug FROM shop_products WHERE id=%s", (id_,))
    return cur.fetchone()["slug"]


def presmerovani(cur):
    cur.execute("SELECT old_slug, product_id FROM shop_product_redirects ORDER BY old_slug")
    return {r["old_slug"]: r["product_id"] for r in cur.fetchall()}


def main():
    pred = ostry_stav()

    # ---- ciste funkce (bez DB) --------------------------------------------------------------------------------
    over("1.1 slugify: diakritika, mala pismena, pomlcky", ps.slugify("Překližka 10 mm, šedá") == "preklizka-10-mm-seda", ps.slugify("Překližka 10 mm, šedá"))
    over("1.2 slugify: interni nazev dodavatele se do adresy nedostane",
         ps.slugify("Regálová vestavba – Peugeot Expert L2 – vanDrawee") == "regalova-vestavba-peugeot-expert-l2", ps.slugify("Regálová vestavba – Peugeot Expert L2 – vanDrawee"))
    dlouhy = ps.slugify("Velmi dlouhy nazev " * 12)
    over("1.3 slugify: nejvys MAX_LEN znaku a konci cele slovo", len(dlouhy) <= ps.MAX_LEN and not dlouhy.endswith("-") and dlouhy.startswith("velmi-dlouhy-nazev"), dlouhy)
    over("1.4 slugify: nic pouzitelneho -> prazdny retezec", ps.slugify("— / ??") == "" and ps.slugify(None) == "", (ps.slugify("— / ??"), ps.slugify(None)))
    over("1.5 is_stale: shoda, citac kolize -N = cerstve; jiny nazev / chybejici = zastarale",
         not ps.is_stale("Úhelník 30", "uhelnik-30") and not ps.is_stale("Úhelník 30", "uhelnik-30-2") and ps.is_stale("Úhelník 30", "stary-nazev")
         and ps.is_stale("Úhelník 30", None) and ps.is_stale("Úhelník 30", "uhelnik-30-neco"))
    over("1.6 has_internal_token: jen jako cele slovo adresy", ps.has_internal_token("regal-peugeot-vandrawee") and not ps.has_internal_token("regal-peugeot") and not ps.has_internal_token(None))

    # ---- DB: docasne tabulky ----------------------------------------------------------------------------------
    conn = connect()
    try:
        with conn.cursor() as cur:
            for t in TABULKY:
                cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            for t in TABULKY:                                   # stinove tabulky (LIKE sama sebe MySQL nepusti, 1066)
                cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            conn.commit()

            a = vloz(cur, "ZZSLUG-A", "Regálová vestavba – Peugeot Expert L2", "regalova-vestavba-peugeot-expert-l2-vandrawee")
            b = vloz(cur, "ZZSLUG-B", "Vyrovnávací šroubovací patka M6", "plastova-patka-m6")
            c_ = vloz(cur, "ZZSLUG-C", "Úhelník 30", "uhelnik-30")
            c2 = vloz(cur, "ZZSLUG-C2", "Úhelník 30", "uhelnik-30-2")                       # citac kolize = v poradku
            d = vloz(cur, "ZZSLUG-D", "Bez adresy", None)                                  # verejny, slug chybi
            e = vloz(cur, "ZZSLUG-E", "Neaktivni bez adresy", None, active=0)              # neverejny -> ignorovat
            f = vloz(cur, "ZZSLUG-F", "Archivovany", "stary-archiv", archived=1)           # archivovany -> ignorovat
            g1 = vloz(cur, "ZZSLUG-G1", "Stejny nazev", "g-stary-1")                       # dva produkty, tentyz nazev
            g2 = vloz(cur, "ZZSLUG-G2", "Stejny nazev", "g-stary-2")
            conn.commit()

            # --- unikatnost vcetne starych (presmerovanych) adres ---
            cur.execute("INSERT INTO shop_product_redirects (old_slug, product_id) VALUES ('drive-pouzita', %s)", (c_,))
            over("2.1 unique_slug: obsazeny slug -> pripona -2", ps.unique_slug(cur, "uhelnik-30") == "uhelnik-30-3", ps.unique_slug(cur, "uhelnik-30"))
            over("2.2 unique_slug: stara adresa JINEHO produktu se znovu nepouzije", ps.unique_slug(cur, "drive-pouzita") == "drive-pouzita-2", ps.unique_slug(cur, "drive-pouzita"))
            over("2.3 unique_slug: vlastni stara adresa a vlastni slug jsou pro ten produkt volne", ps.unique_slug(cur, "drive-pouzita", exclude_id=c_) == "drive-pouzita" and ps.unique_slug(cur, "uhelnik-30", exclude_id=c_) == "uhelnik-30")
            cur.execute("DELETE FROM shop_product_redirects")

            # --- zmena adresy zapisuje 301 ---
            over("3.1 change_slug: zmeni adresu a zapise 301 ze stare", ps.change_slug(cur, c_, "novy-uhelnik") is True and slug_z_db(cur, c_) == "novy-uhelnik" and presmerovani(cur) == {"uhelnik-30": c_}, presmerovani(cur))
            over("3.2 change_slug: stejna adresa = nic (idempotentni)", ps.change_slug(cur, c_, "novy-uhelnik") is False and presmerovani(cur) == {"uhelnik-30": c_})
            over("3.3 change_slug: navrat na drivejsi adresu nenecha presmerovani samo na sebe a stara adresa se presmeruje",
                 ps.change_slug(cur, c_, "uhelnik-30") is True and presmerovani(cur) == {"novy-uhelnik": c_}, presmerovani(cur))
            ps.change_slug(cur, c_, "uhelnik-30")
            cur.execute("DELETE FROM shop_product_redirects")
            conn.commit()

            # --- navrhy a aplikace ---
            n = {p["id"]: p for p in ps.proposals(cur)}
            over("4.1 proposals: interni nazev, nesedi, chybi - ano; cerstve (vc. -2), neaktivni a archivovane - ne",
                 set(n) == {a, b, d, g1, g2} and n[a]["reason"] == "interni" and n[b]["reason"] == "nesedi" and n[d]["reason"] == "chybi", {k: v["reason"] for k, v in n.items()})
            over("4.2 proposals(ids) omezi vyber", [p["id"] for p in ps.proposals(cur, ids=[b])] == [b])

            zmeny = ps.apply(cur, ps.proposals(cur))
            nove = {z["id"]: z["new"] for z in zmeny}
            over("4.3 apply: adresa sleduje nazev, interni nazev pryc",
                 nove[a] == "regalova-vestavba-peugeot-expert-l2" and nove[b] == "vyrovnavaci-sroubovaci-patka-m6" and nove[d] == "bez-adresy", nove)
            over("4.4 apply: dva produkty se stejnym nazvem dostanou ruzne adresy (-2)", {nove[g1], nove[g2]} == {"stejny-nazev", "stejny-nazev-2"}, nove)
            over("4.5 apply: kazda zmenena ZNAMA stara adresa je presmerovana na SPRAVNY produkt (301); chybejici stara adresa nic nezapise",
                 presmerovani(cur) == {"regalova-vestavba-peugeot-expert-l2-vandrawee": a, "plastova-patka-m6": b, "g-stary-1": g1, "g-stary-2": g2}, presmerovani(cur))
            over("4.6 neaktivni a archivovany produkt zustaly beze zmeny", slug_z_db(cur, e) is None and slug_z_db(cur, f) == "stary-archiv")
            over("4.7 po aplikaci uz neni co navrhovat (idempotence)", ps.proposals(cur) == [], ps.proposals(cur))
            conn.commit()

            # --- dry-run = apply + rollback (presny nahled bez zapisu) ---
            h = vloz(cur, "ZZSLUG-H", "Dalsi produkt", "uplne-jina-adresa")
            conn.commit()
            nahled = ps.apply(cur, ps.proposals(cur))
            conn.rollback()
            over("5.1 nahled (apply + rollback) ukaze zmenu, ale nic nezapise", [z["new"] for z in nahled] == ["dalsi-produkt"] and slug_z_db(cur, h) == "uplne-jina-adresa" and "uplne-jina-adresa" not in presmerovani(cur), nahled)
    finally:
        conn.close()

    po = ostry_stav()
    over("6 ostre tabulky se nezmenily a zadny testovaci radek nepretekl do ostre DB", po == pred, {"pred": pred, "po": po})

    selhalo = vysl.count(False)
    print(f"\nVYSLEDEK adresy produktu: {len(vysl) - selhalo}/{len(vysl)} OK")
    sys.exit(1 if selhalo else 0)


if __name__ == "__main__":
    main()
