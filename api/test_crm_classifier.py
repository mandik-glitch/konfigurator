#!/usr/bin/env python3
"""
Test crm.classify_incoming_email po vypnuti automaticke klasifikace na
'poptavka' (2026-09-03, Robert pres bot3: "boti zde nejsou vubec schopni
rozeznat poptavku v prichozi poste, prestan to stitkovat").

Spusteni:  ./api/venv/bin/python api/test_crm_classifier.py

crm.py dela na modulove urovni `from app import (...)` a dalsi importy
(products/customers/gallery_items/quotes), ktere by za normalnich
okolnosti stahly cely app.py retezec (~60 dalsich modulu, DB_HOST env
promenne atd.) - misto toho se `app`/`products`/`customers`/
`gallery_items`/`quotes` podstrci do `sys.modules` jako Mock, PRED
importem crm.py, takze se importuje jen samotny crm.py beze zmeny a
skutecny app.py se vubec nenacita (zadne DB pripojeni, zadne vedlejsi
efekty). `get_conn`/kurzor uvnitr `classify_incoming_email` se
podstrkuji per-test (fake kurzor s pripravenymi radky).
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

for _name in ("app", "products", "customers", "gallery_items", "quotes"):
    sys.modules.setdefault(_name, mock.MagicMock(name=_name))

import crm  # noqa: E402


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)

    def close(self):
        pass


def _classify_with_rows(rows):
    with mock.patch.object(crm, "get_conn", return_value=_FakeConn(rows)):
        return crm.classify_incoming_email("predmet", "telo zpravy")


class ClassifyIncomingEmailTests(unittest.TestCase):
    def test_never_returns_poptavka_even_when_it_would_have_won(self):
        # poptavka_count drtive vyhrava nad jine_count i doklad_count -
        # driv by tohle vratilo 'poptavka', ted nesmi nikdy.
        rows = [{"poptavka_count": 50, "jine_count": 1, "doklad_count": 0}]
        self.assertEqual(_classify_with_rows(rows), "jine")

    def test_still_returns_doklad_when_it_wins(self):
        # doklad/jine logika NENI zmenena - musi zustat funkcni beze zmeny.
        rows = [{"poptavka_count": 0, "jine_count": 1, "doklad_count": 5}]
        self.assertEqual(_classify_with_rows(rows), "doklad")

    def test_still_returns_jine_when_jine_wins(self):
        rows = [{"poptavka_count": 3, "jine_count": 7, "doklad_count": 2}]
        self.assertEqual(_classify_with_rows(rows), "jine")

    def test_doklad_wins_tie_against_jine_unchanged(self):
        # puvodni chovani: remiza jine/doklad -> vyhrava doklad (bot8,
        # 2026-08-17) - musi zustat stejne.
        rows = [{"poptavka_count": 0, "jine_count": 3, "doklad_count": 3}]
        self.assertEqual(_classify_with_rows(rows), "doklad")

    def test_no_words_matched_falls_back_to_jine(self):
        self.assertEqual(_classify_with_rows([]), "jine")

    def test_no_tokens_at_all_short_circuits_to_jine(self):
        with mock.patch.object(crm, "get_conn") as m:
            result = crm.classify_incoming_email("", "")
        self.assertEqual(result, "jine")
        m.assert_not_called()

    def test_db_failure_fails_open_to_jine(self):
        with mock.patch.object(crm, "get_conn", side_effect=RuntimeError("DB vypadek")):
            result = crm.classify_incoming_email("predmet s poptavkovymi slovy", "telo")
        self.assertEqual(result, "jine")

    def test_high_poptavka_score_alone_still_never_wins(self):
        # I kdyz je poptavka_count extremne vysoke a jine/doklad jsou 0,
        # vysledek nesmi byt 'poptavka' (drivejsi kod by tu vratil
        # 'poptavka', protoze poptavka_score>0 a >= zbylym dvema).
        rows = [{"poptavka_count": 999, "jine_count": 0, "doklad_count": 0}]
        self.assertEqual(_classify_with_rows(rows), "jine")


if __name__ == "__main__":
    unittest.main()
