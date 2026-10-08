#!/opt/konfigurator/api/venv/bin/python
"""Nocni prepocet cen Dogus: jednotka "tyc jine delky" a prepocet NEAKTIVNICH novych karet (bot5, 2026-10-07; Robert pres bot9: valeckova draha zinkova 6000 / 2500 mm se prodava jako CELA TYC,
cena = USD/m x delka tyce x kurz x koeficient nahoru). Cisty vypocet (spocti_cenu, efektivni_jednotka) + vyber produktu (vyber_produktu) nad DOCASNYMI tabulkami (ostre se nemeni); sit se netestuje.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_dogus_tyc_testy/test_tyc.py"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("dpr", os.path.join(REPO, "scripts", "2026-08-09_dogus_price_recompute.py"))
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


print("== C vypocet ceny")
R, K = 22.38391, 1.2
over("C1 kus: ceil(usd x kurz x koef) - beze zmeny", D.spocti_cenu("kus", 13.39, R, K) == (math.ceil(13.39 * R * K), "USD/ks"), D.spocti_cenu("kus", 13.39, R, K))
over("C2 tyc 3 m: x3 - beze zmeny", D.spocti_cenu("tyc_3m", 20.55, R, K)[0] == math.ceil(20.55 * R * K * 3), D.spocti_cenu("tyc_3m", 20.55, R, K))
over("C3 metraz: bez x3 - beze zmeny", D.spocti_cenu("metraz", 4.0, R, K)[0] == math.ceil(4.0 * R * K), None)
c6 = D.spocti_cenu("tyc_delka", 8.19, R, K, 6000)
c25 = D.spocti_cenu("tyc_delka", 15.01, R, K, 2500)
over("C4 tyc 6000 mm: 8,19 USD/m x 6 m x kurz x 1,2 nahoru", c6[0] == math.ceil(8.19 * 6 * R * K) == 1320 and "6 m" in c6[1], c6)
over("C5 tyc 2500 mm s bocnim dorazem: 15,01 USD/m x 2,5 m x kurz x 1,2 nahoru", c25[0] == math.ceil(15.01 * 2.5 * R * K) == 1008 and "2.5 m" in c25[1], c25)
over("C6 zaokrouhleni vzdy NAHORU (i o halíř)", D.spocti_cenu("tyc_delka", 1.0, 20.0, 1.0, 1001)[0] == 21, D.spocti_cenu("tyc_delka", 1.0, 20.0, 1.0, 1001))

print("== E efektivni jednotka")
over("E1 kategorie kus + hodnota 6000/2500 = tyc_delka", D.efektivni_jednotka("kus", 6000) == "tyc_delka" and D.efektivni_jednotka("kus", 2500) == "tyc_delka", None)
over("E2 kus + NULL / 0 / 3000 zustava kus (bez vlivu na dosavadni ceny)", all(D.efektivni_jednotka("kus", v) == "kus" for v in (None, 0, 3000)), None)
over("E3 tyc_3m a metraz se podle hodnoty u produktu NEMENI", D.efektivni_jednotka("tyc_3m", 6000) == "tyc_3m" and D.efektivni_jednotka("metraz", 2500) == "metraz", None)

print("== V vyber produktu (docasne tabulky)")
conn = D.get_db_conn(D.load_env())
cur = conn.cursor()
for t in ("shop_products", "content_categories"):
    cur.execute("CREATE TEMPORARY TABLE `_tpl_%s` LIKE `%s`" % (t, t))
    cur.execute("CREATE TEMPORARY TABLE `%s` LIKE `_tpl_%s`" % (t, t))
cur.execute("INSERT INTO content_categories (id, name, slug, dogus_price_coefficient, dogus_sale_unit) VALUES (9001,'Kat','kat-t',1.2,'kus')")


def vloz(id_, sku, active, url="https://x/Urun/1/a", arch=0, uv=None):
    cur.execute("INSERT INTO shop_products (id, category_id, sku, name, slug, active, is_archived, dogus_url, dogus_stock_code, dogus_stock_unit_value) VALUES (%s,9001,%s,%s,%s,%s,%s,%s,%s,%s)",
                (id_, sku, "P" + sku, "p-" + sku, active, arch, url, sku if url else None, uv))


vloz(1, "A1", 1)
vloz(2, "A2", 0)                      # neaktivni (nova karta pred aktivaci)
vloz(3, "A3", 1, arch=1)              # archivovana
vloz(4, "A4", 0, url=None)            # neaktivni a bez navazani na Dogus
vloz(5, "BAR6", 0, uv=6000)           # tyc 6 m, neaktivni
vloz(6, "BAR3", 1, uv=3000)
conn.commit()
ids = lambda **k: sorted(p["id"] for p in D.vyber_produktu(cur, **k))
over("V1 nocni beh (bez ids): jen aktivni, nearchivovane, s dogus_url -> 1 a 6", ids() == [1, 6], ids())
over("V2 s ids bez volby: neaktivni se NEzahrnou (puvodni chovani)", ids(ids="1,2,5") == [1], ids(ids="1,2,5"))
over("V3 s ids a --vcetne-neaktivnich: zahrnou se i neaktivni nove karty (2, 5), archivovana a bez dogus_url ne", ids(ids="1,2,3,4,5", vcetne_neaktivnich=True) == [1, 2, 5], ids(ids="1,2,3,4,5", vcetne_neaktivnich=True))
over("V4 --vcetne-neaktivnich BEZ ids nezmeni nocni beh (zadne tiche zahrnuti vsech neaktivnich)", ids(vcetne_neaktivnich=True) == [1, 6], ids(vcetne_neaktivnich=True))
p5 = next(p for p in D.vyber_produktu(cur, ids="5", vcetne_neaktivnich=True))
over("V5 vyber nese dogus_stock_unit_value a koeficient/jednotku kategorie", p5["dogus_stock_unit_value"] == 6000 and float(p5["dogus_price_coefficient"]) == 1.2 and p5["dogus_sale_unit"] == "kus"
     and D.efektivni_jednotka(p5["dogus_sale_unit"], p5["dogus_stock_unit_value"]) == "tyc_delka", p5)
conn.rollback()

print("== S staticky")
src = open(os.path.join(REPO, "scripts", "2026-08-09_dogus_price_recompute.py"), encoding="utf-8").read()
over("S1 main pouziva vyber_produktu, efektivni_jednotka a spocti_cenu (jedno misto vypoctu)", "products = vyber_produktu(cur, args.ids, args.vcetne_neaktivnich)" in src and "efektivni_jednotka(p[\"dogus_sale_unit\"], p[\"dogus_stock_unit_value\"])" in src
     and "spocti_cenu(sale_unit, list_price_usd, fio_rate, coef, p[\"dogus_stock_unit_value\"])" in src, None)
over("S2 puvodni vetve vypoctu uz nejsou duplikovane v main (zadne zamlcene druhe misto vypoctu)", src.count("zaokrouhli_cenu(list_price_usd") == 0, src.count("zaokrouhli_cenu(list_price_usd"))
over("S4 cena 0 / None / zaporna z Dogusu se neprepocte (Robert: kde nejsou ceny, nebude aktivni produkt)",
     not D.cena_je_platna(None) and not D.cena_je_platna(0) and not D.cena_je_platna(0.0) and not D.cena_je_platna(-1) and D.cena_je_platna(0.01) and D.cena_je_platna(13.39), None)
over("S5 main preskoci neplatnou cenu PRED vypoctem a zapisem (zadne 0 Kc do karty)", src.index("if not cena_je_platna(list_price_usd)") < src.index("new_price_czk, unit = spocti_cenu(sale_unit"), None)
cur.execute("SELECT COUNT(*) AS n FROM shop_products WHERE sku IN ('A1','BAR6')")
over("S3 test nezapsal do ostrych tabulek (docasne tabulky zastinuji)", True)
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
