#!/opt/konfigurator/api/venv/bin/python
"""Zarazeni nove Vandr karty do kategorie ve watcheru (bot5, 2026-10-06): Ducato / Jumper / Boxer rovnou do SLOUCENE kategorie 233 (Robert: "kategorie techto 3 modelu sloucit"),
jen kdyz je 233 uz ve stromu "Vestavby podle vozidla" (parent 267 = po zapisu scripts/2026-10-06_slouceni_ducato_jumper_boxer.py); ostatni modely beze zmeny (_kategorie_modelu).
Falesny kurzor, zadna DB, nic se nezapisuje. Spusteni: api/venv/bin/python3 scripts/2026-10-06_vandr_watcher_kategorie_testy/test_kategorie.py"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "api"))
sys.path.insert(0, os.path.join(HERE, ".."))
spec = importlib.util.spec_from_file_location("w", os.path.join(HERE, "..", "2026-09-22_vandr_fbx_watcher.py"))
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


class Kurzor:
    """minimalni content_categories: {id: (name, parent_id)}"""
    def __init__(self, kat):
        self.kat, self.dotazy, self._r = kat, [], None

    def execute(self, sql, params=()):
        self.dotazy.append(sql)
        if sql.startswith("SELECT name FROM content_categories WHERE id=%s"):
            k = self.kat.get(params[0])
            self._r = [{"name": k[0]}] if k else []
        elif sql.startswith("SELECT id, name FROM content_categories WHERE parent_id=%s"):
            self._r = [{"id": i, "name": n} for i, (n, p) in self.kat.items() if p == params[0]]
        elif sql.startswith("SELECT id FROM content_categories WHERE id=%s AND parent_id=%s"):
            k = self.kat.get(params[0])
            self._r = [{"id": params[0]}] if k and k[1] == params[1] else []
        else:
            raise AssertionError("necekany dotaz: " + sql)

    def fetchone(self):
        return self._r[0] if self._r else None

    def fetchall(self):
        return list(self._r)


PRED = {184: ("Vestavby do dodavek, aut", None), 267: ("Vestavby podle vozidla", 184), 233: ("Vestavby pro Ducato, Jumper, Boxer", 184), 269: ("Vestavby pro Fiat", 267),
        300: ("Vestavby pro Fiat Ducato", 269), 273: ("Vestavby pro Fiat Doblo", 269), 268: ("Vestavby pro Citroen", 267), 288: ("Vestavby pro Peugeot", 267),
        285: ("Vestavby pro Renault", 267), 305: ("Vestavby pro Renault Master", 285)}
PO = dict(PRED)
PO[233] = ("Vestavby pro Ducato, Jumper, Boxer", 267)          # po zapisu skriptu: 233 pod 267
del PO[300]                                                    # kategorie 300 zanikla

print("== A _slouceny_model")
A = [("Fiat Ducato L2H2 3450 mm", 269, (233, 269)), ("Citroen Jumper L3H2", 268, (233, 268)), ("Peugeot Boxer L2H2", 288, (233, 288)), ("Ford Transit L2", 279, None),
     ("Fiat Doblò L1H1", 269, None), ("Fiat Ducato", None, None), (None, 269, None), ("Peugeot Ducato Boxer", 288, None), ("Citroen Ducato", 268, None),
     ("Ducatos L1", 269, None), ("fiat DUCATO l1h1", 269, (233, 269)), ("Renault Master L2H2", 285, None)]
for nazev, brand, ocek in A:
    over(f"A po zapisu: {nazev!r} + znacka {brand} -> {ocek}", w._slouceny_model(Kurzor(PO), brand, nazev) == ocek, w._slouceny_model(Kurzor(PO), brand, nazev))
over("A1 PRED zapisem skriptu (233 pod korenem 184) se nic nemeni: Fiat Ducato -> None (plati _kategorie_modelu)", w._slouceny_model(Kurzor(PRED), 269, "Fiat Ducato L2H2") is None, None)

print("== B _kategorie_modelu beze zmeny (ostatni modely)")
B = [(285, "Renault Master L2H2 3682 mm", 305), (269, "Fiat Doblò L1H1", 273), (285, "Renault Kangoo", 285), (None, "Neco", None), (285, None, 285)]
for brand, nazev, ocek in B:
    over(f"B {nazev!r} + znacka {brand} -> {ocek}", w._kategorie_modelu(Kurzor(PO), brand, nazev) == ocek, w._kategorie_modelu(Kurzor(PO), brand, nazev))
over("B1 pred zapisem skriptu: Fiat Ducato -> 300 (puvodni chovani)", w._kategorie_modelu(Kurzor(PRED), 269, "Fiat Ducato L2H2") == 300, w._kategorie_modelu(Kurzor(PRED), 269, "Fiat Ducato L2H2"))
over("B2 po zapisu skriptu (300 zanikla): _kategorie_modelu u Ducata vrati znackovou 269 (proto ma prednost _slouceny_model)", w._kategorie_modelu(Kurzor(PO), 269, "Fiat Ducato L2H2") == 269, None)

print("== C staticky: watcher pouziva sloucenou kategorii a pridava sekundarni vazbu")
src = open(os.path.join(HERE, "..", "2026-09-22_vandr_fbx_watcher.py"), encoding="utf-8").read()
over("C1 INSERT shop_products bere kategorii ze _slouceny_model, jinak z _kategorie_modelu", "slouceno[0] if slouceno else _kategorie_modelu(" in src, None)
over("C2 po INSERTu karty se zapise sekundarni vazba na znackovou kategorii (INSERT IGNORE shop_product_categories)", "INSERT IGNORE INTO shop_product_categories (product_id, category_id) VALUES (%s,%s)\", (new_pid, slouceno[1])" in src, None)
over("C3 active se nikde nenastavuje (karta vzniká s active=0, pravidlo 54)", "VALUES (%s,%s,%s,0,%s,%s,%s,%s,%s,%s,'vanDrawee',%s,0)" in src, None)

ok = sum(vysl)
print(f"\nVYSLEDEK kategorie nove Vandr karty: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
