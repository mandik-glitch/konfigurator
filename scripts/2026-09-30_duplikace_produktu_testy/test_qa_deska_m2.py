#!/opt/konfigurator/api/venv/bin/python
"""Test QA kontroly board_price_not_per_m2 (api/qa_checks.py): deska musi mit cenu za 1 m² (unit 'm2') a formát tabule.
Cast 1 (bez DB, falesny kurzor): kontrola hlasi starsi stav 'ks', chybejici formát tabule i obojí, a NEhlasi spravnou desku -
vc. "stavu pred opravou" (kontrola musi najit presne ten stav, ktery vyrobil chybu u laminodesky 3671).
Cast 2 (skutecna DB, jen cteni): registrace ve vsech trech registrech a bezi bez chyby; nad skutecnymi daty hlasi jen desky.

Spusteni (cast 2 potrebuje DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
    --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \
    scripts/2026-09-30_duplikace_produktu_testy/test_qa_deska_m2.py
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

KLIC = "board_price_not_per_m2"
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


def deska(id_, unit, w=2070, h=2800, name="Deska"):
    return {"id": id_, "name": name, "unit": unit, "w": w, "h": h}


def main():
    over("1 kontrola je zaregistrovana ve VSECH TRECH registrech", KLIC in qa.CHECKS and KLIC in qa.CHECK_CATEGORY and KLIC in qa.CHECK_ADDED,
         {"CHECKS": KLIC in qa.CHECKS, "CATEGORY": KLIC in qa.CHECK_CATEGORY, "ADDED": KLIC in qa.CHECK_ADDED})
    fn = qa.check_board_price_not_per_m2
    cur = FakeCur([deska(3539, "ks", 1250, 2500, "PR10"), deska(3671, "m2"), deska(3939, "m2", None, None, "MDF"),
                   deska(5, "m2", 0, 2800, "nula"), deska(6, None, 100, 100, "bez jednotky")])
    nalezy = {r[0]: r[2] for r in fn(cur)}
    over("2 starsi stav (unit 'ks' = cena za tabuli) se hlasi s navodem na prevod", 3539 in nalezy and "Převést na cenu za 1 m²" in nalezy[3539] and "formát" not in nalezy[3539], nalezy)
    over("3 spravna deska (m2 + format tabule) se NEhlasi", 3671 not in nalezy, nalezy)
    over("4 chybejici format tabule se hlasi (None i 0)", 3939 in nalezy and "chybí formát tabule" in nalezy[3939] and 5 in nalezy, nalezy)
    over("5 deska bez jednotky se hlasi jako nesjednocena", 6 in nalezy and "jednotku" in nalezy[6], nalezy)
    over("6 SQL bere jen desky a ne archivovane", "is_board_material=1" in cur.sql and "is_archived=0" in cur.sql, cur.sql)

    # cast 2: skutecna DB, jen cteni
    if "DB_HOST" in os.environ:
        import pymysql
        c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                            database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor)
        try:
            with c.cursor() as cur2:
                over("7 registrace je kompletni (check_qa_registration_incomplete nic nehlasi pro tuhle kontrolu)",
                     not [r for r in qa.check_qa_registration_incomplete(cur2) if KLIC in r[0]])
                vysledek = qa.run_checks(cur2, only=[KLIC])[KLIC]
                over("8 nad skutecnymi daty bezi bez chyby", not vysledek.get("error"), vysledek)
                ids = [r[0] for r in vysledek.get("rows") or []]
                if ids:
                    cur2.execute("SELECT id FROM shop_products WHERE is_board_material=1 AND id IN (%s)" % ",".join(["%s"] * len(ids)), ids)
                    over("9 nad skutecnymi daty hlasi jen skutecne desky", len(cur2.fetchall()) == len(ids), ids)
                print("   (skutecne nalezy ted:", [(r[0], r[2][:60]) for r in vysledek.get("rows") or []], ")")
        finally:
            c.close()
    else:
        print("   (cast 2 - skutecna DB - preskocena: chybi DB_* v prostredi)")

    selhalo = vysl.count(False)
    print(f"\nVYSLEDEK QA kontrola desek: {len(vysl) - selhalo}/{len(vysl)} OK")
    sys.exit(1 if selhalo else 0)


if __name__ == "__main__":
    main()
