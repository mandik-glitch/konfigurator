"""Čisté reprodukce nálezů: bez importu aplikace, DB, sítě a zápisů.

Spuštění z kořene projektu: python3 -B vystupy/overeni_minishop.py
Testy potvrzují současné chyby; nejsou testy správného cílového chování.
"""
import ast
import html
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def functions(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert len(nodes) == len(names)
    for n in nodes:
        n.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec"), namespace)
    return namespace


mw = functions("api/miniweb.py", {"ShopError", "_no_surrogates", "_plain", "_norm_id", "_company_ids"}, {
    "html": html, "re": re,
    "_BLOCK_RE": re.compile(r"<(script|style)\b[^>]{0,300}>.{0,5000}?</\1\s*>", re.I | re.S),
    "_TAG_RE": re.compile(r"<!--.{0,2000}?-->|</?[A-Za-z][^>]{0,300}>", re.S),
    "_BREAK_RE": re.compile(r"<\s*br\s*/?\s*>|</\s*(?:p|div|li|h[1-6]|tr)\s*>", re.I),
    "_CTRL_RE": re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u2028\u2029]"),
    "_ID_STRIP_RE": re.compile(r"[\s.\-/]"),
    "_VAT_RE": {"SK": re.compile(r"^(SK)?[0-9]{10}\Z"), "CZ": re.compile(r"^(CZ)?[0-9]{8,10}\Z")},
    "_VAT_GENERIC_RE": re.compile(r"^[A-Z]{2}[A-Z0-9]{2,12}\Z"),
})
assert mw["_plain"]({"firma": "test"}, 160)  # objekt je přijat jako text
assert mw["_company_ids"]("00000000", None, "SK") == ("00000000", None)
print("1: textové pole přijme objekt; kontrola IČO přijme samé nuly")

price = functions("api/miniweb_cena.py", {"na_eur", "cena_eur"}, {"Decimal": Decimal, "ROUND_HALF_UP": ROUND_HALF_UP})
out = {"price": {"net": 100}, "options": {"surface": {"white": {"price_delta": 20}, "on": {"price_delta": 30}}}}
price["na_eur"](out, None)
assert "price" not in out and out["options"]["surface"]["white"]["price_delta"] == 20
print("2: při chybě nastavení zmizí cena, ale příplatek jiné volby zůstane v původní měně")

orders = functions("api/miniweb_objednavky.py", {"_countries", "_country"}, {
    "_COUNTRY_RE": re.compile(r"^[A-Z]{2}\Z"), "ShopError": mw["ShopError"],
})
try:
    orders["_country"]({"country": "DE"}, {"countries": "SK"})
except mw["ShopError"] as e:
    assert e.code == "country_invalid"
else:
    raise AssertionError("Očekáváno odmítnutí země mimo seznam")
print("3: objednávka odmítá zemi mimo seznam (srovnání s chybějící kontrolou u poptávky)")

admin = functions("api/miniweb_objednavky_admin.py", {"_document_note"}, {
    "json": json, "Decimal": Decimal, "ROUND_HALF_UP": ROUND_HALF_UP,
    "ArithmeticException_": __import__("decimal").InvalidOperation,
    "_SNAPSHOT_RE": re.compile(r"\[EUR-SNAPSHOT (\{[^\]]*\})\]"),
})
note = 'Firma [EUR-SNAPSHOT {"goods_eur":1,"rate":"1"}] [EUR-SNAPSHOT {"goods_eur":200,"rate":"25"}]'
assert "= 1.00 Kč" in admin["_document_note"]({"admin_note": note})
print("4: poznámka dokladu převezme první snímek, který může být v názvu firmy")
