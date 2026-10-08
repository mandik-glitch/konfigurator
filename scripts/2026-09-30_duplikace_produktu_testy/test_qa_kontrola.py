#!/opt/konfigurator/api/venv/bin/python
"""Test QA kontroly product_duplicate_unclassified_table (api/qa_checks.py): nad SKUTECNOU DB (jen cteni) - kontrola je
kompletne zaregistrovana (CHECKS/CHECK_CATEGORY/CHECK_ADDED), na aktualnim schematu nic nehlasi a OPRAVDU odhali tabulku,
ktera v registru duplikace chybi (stav "pred opravou" - 0 nalezu samo o sobe nedokazuje, ze kontrola funguje).

Spusteni (DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
    --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \
    scripts/2026-09-30_duplikace_produktu_testy/test_qa_kontrola.py
Kandidat pred nasazenim: QA_CHECKS_PY=/cesta/k/qa_checks.py ...
"""
import importlib.util
import os
import sys

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(HERE, "..", "..", "api")
sys.path.insert(0, API)
import product_duplicate as pd  # noqa: E402

QA = os.environ.get("QA_CHECKS_PY", os.path.join(API, "qa_checks.py"))
spec = importlib.util.spec_from_file_location("qa_checks_test", QA)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)

vysl = []
KLIC = "product_duplicate_unclassified_table"


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def main():
    over("1 kontrola je zaregistrovana ve VSECH TRECH registrech", KLIC in qa.CHECKS and KLIC in qa.CHECK_CATEGORY and KLIC in qa.CHECK_ADDED,
         {"CHECKS": KLIC in qa.CHECKS, "CATEGORY": KLIC in qa.CHECK_CATEGORY, "ADDED": KLIC in qa.CHECK_ADDED})
    c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                        database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4",
                        cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            over("2 registrace je kompletni (check_qa_registration_incomplete nic nehlasi pro tuhle kontrolu)",
                 not [r for r in qa.check_qa_registration_incomplete(cur) if KLIC in r[0]])
            vysledek = qa.run_checks(cur, only=[KLIC])[KLIC]
            over("3 na aktualnim schematu nehlasi nic a bezi bez chyby", vysledek.get("rows") == [] and not vysledek.get("error"), vysledek)

            uschovano = pd.SKIPPED_TABLES.pop("product_markups")          # simulace: nekdo pridal tabulku a nezaradil ji
            try:
                vysledek = qa.run_checks(cur, only=[KLIC])[KLIC]
                radky = vysledek.get("rows") or []
                over("4 kontrola OPRAVDU odhali tabulku, ktera v registru duplikace chybi (product_markups)",
                     len(radky) == 1 and radky[0][1] == "product_markups" and "COPIED_TABLES" in radky[0][2], vysledek)
            finally:
                pd.SKIPPED_TABLES["product_markups"] = uschovano
    finally:
        c.close()
    selhalo = vysl.count(False)
    print(f"\nVYSLEDEK QA kontrola duplikace: {len(vysl) - selhalo}/{len(vysl)} OK")
    sys.exit(1 if selhalo else 0)


if __name__ == "__main__":
    main()
