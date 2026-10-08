#!/opt/konfigurator/api/venv/bin/python
"""Test QA kontroly product_slug_not_from_name (api/qa_checks.py): verejny produkt s adresou, ktera neodpovida nazvu / obsahuje
interni nazev / chybi, se hlasi; cerstve adresy (vc. citace kolize -N) ne. Cast 1 bez DB (falesny kurzor), cast 2 nad
skutecnou DB jen cteni (registrace, beh bez chyby, jen verejne produkty).

Spusteni (cast 2 potrebuje DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
    --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \
    scripts/2026-09-30_duplikace_produktu_testy/test_qa_slug.py
Kandidat pred nasazenim: QA_CHECKS_PY=/cesta/k/qa_checks.py ...
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(HERE, "..", "..", "api")
sys.path.insert(0, API)
QA = os.environ.get("QA_CHECKS_PY", os.path.join(API, "qa_checks.py"))
spec = importlib.util.spec_from_file_location("qa_checks_test", QA)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)

KLIC = "product_slug_not_from_name"
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


class FakeCur:
    def __init__(self, radky):
        self.radky, self.sql = radky, None

    def execute(self, sql, params=None):
        self.sql = sql

    def fetchall(self):
        return self.radky


def main():
    over("1 kontrola je zaregistrovana ve VSECH TRECH registrech", KLIC in qa.CHECKS and KLIC in qa.CHECK_CATEGORY and KLIC in qa.CHECK_ADDED,
         {"CHECKS": KLIC in qa.CHECKS, "CATEGORY": KLIC in qa.CHECK_CATEGORY, "ADDED": KLIC in qa.CHECK_ADDED})
    cur = FakeCur([
        {"id": 1, "name": "Regálová vestavba – Peugeot Expert L2", "slug": "regalova-vestavba-peugeot-expert-l2-vandrawee"},
        {"id": 2, "name": "Vyrovnávací šroubovací patka M6", "slug": "plastova-patka-m6"},
        {"id": 3, "name": "Úhelník 30", "slug": "uhelnik-30"},
        {"id": 4, "name": "Úhelník 30", "slug": "uhelnik-30-2"},
        {"id": 5, "name": "Bez adresy", "slug": None},
    ])
    nalezy = {r[0]: r for r in qa.check_product_slug_not_from_name(cur)}
    over("2 interni nazev v adrese se hlasi (a rika proc)", 1 in nalezy and "interní název dodavatele" in nalezy[1][2], nalezy.get(1))
    over("3 adresa neodpovidajici nazvu se hlasi", 2 in nalezy and "neodpovídá aktuálnímu názvu" in nalezy[2][2], nalezy.get(2))
    over("4 chybejici adresa se hlasi", 5 in nalezy and "nemá žádnou adresu" in nalezy[5][2], nalezy.get(5))
    over("5 cerstve adresy (shoda i citac kolize -2) se NEhlasi", 3 not in nalezy and 4 not in nalezy, sorted(nalezy))
    over("6 kazdy nalez ukazuje, jak ho opravit (tlacitko Sjednotit adresy)", all("Sjednotit adresy" in r[2] for r in nalezy.values()), list(nalezy.values())[:1])
    over("7 SQL bere jen verejne (aktivni, nearchivovane) produkty", "active=1" in cur.sql and "is_archived=0" in cur.sql, cur.sql)

    if "DB_HOST" in os.environ:
        import pymysql
        c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                            database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor)
        try:
            with c.cursor() as cur2:
                over("8 registrace je kompletni (check_qa_registration_incomplete nic nehlasi pro tuhle kontrolu)",
                     not [r for r in qa.check_qa_registration_incomplete(cur2) if KLIC in r[0]])
                vysledek = qa.run_checks(cur2, only=[KLIC])[KLIC]
                over("9 nad skutecnymi daty bezi bez chyby", not vysledek.get("error"), vysledek)
                ids = [r[0] for r in vysledek.get("rows") or []]
                if ids:
                    cur2.execute("SELECT COUNT(*) AS n FROM shop_products WHERE active=1 AND is_archived=0 AND id IN (%s)" % ",".join(["%s"] * len(ids)), ids)
                    over("10 nad skutecnymi daty hlasi jen verejne produkty", cur2.fetchone()["n"] == len(ids), len(ids))
                print("   (skutecnych nalezu ted:", len(ids), ")")
        finally:
            c.close()
    else:
        print("   (cast 2 - skutecna DB - preskocena: chybi DB_* v prostredi)")

    selhalo = vysl.count(False)
    print(f"\nVYSLEDEK QA kontrola adres: {len(vysl) - selhalo}/{len(vysl)} OK")
    sys.exit(1 if selhalo else 0)


if __name__ == "__main__":
    main()
