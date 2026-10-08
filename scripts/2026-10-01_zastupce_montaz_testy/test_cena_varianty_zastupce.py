#!/opt/konfigurator/api/venv/bin/python
"""Zastupce sestavy (is_master) + volby "montaz" / "bez boxu" v kosiku a objednavce (bot5, 2026-10-01).

CHYBA: verejny JSON (product_assemblies_public) u zastupce nabizi montaz i "bez boxu" (opraveno 2026-09-15),
product.html je ukaze a pricte k cene, ale `_assembly_price_components` (product_assemblies.py, volaji ji kosik i
objednavka) vracelo u zastupce montaz/boxy None -> server volby tise zahodil. Zakaznik videl cenu s montazi,
do kosiku sla bez ni.

Cast A: `_assembly_price_components` (zastupce / varianta / cizi sestava / chybejici data), bez DB, falesny kurzor.
Cast B: skutecny handler `cart_add_item` (cart.py, AST + atrapy) s TOUTO funkci: volby u zastupce se musi ulozit.
Cast C: kontrakt - zadny jiny kod v cart.py/orders.py zastupce nerozlisuje (jedine misto = funkce vyse).
Cast D (mutace): puvodni (chybna) verze funkce MUSI na cast A i B selhat.
Bez DB a bez Flasku, nic nezapisuje.   Spusteni: api/venv/bin/python3 test_cena_varianty_zastupce.py
Kandidat pred nasazenim: PRODUCT_ASSEMBLIES_PY=... CART_PY=... api/venv/bin/python3 test_cena_varianty_zastupce.py
"""
import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(HERE, "..", "..", "api")
PA = os.environ.get("PRODUCT_ASSEMBLIES_PY", os.path.join(API, "product_assemblies.py"))
CART = os.environ.get("CART_PY", os.path.join(API, "cart.py"))
ORDERS = os.environ.get("ORDERS_PY", os.path.join(API, "orders.py"))

from stara_funkce import STARA_FUNKCE  # noqa: E402  (puvodni chybna verze - jen pro mutacni kontrolu)


def vytahni(cesta, jmena):
    with open(cesta, encoding="utf-8") as f:
        strom = ast.parse(f.read())
    nalezeno = {n.name: n for n in strom.body if isinstance(n, ast.FunctionDef) and n.name in jmena}
    chybi = [j for j in jmena if j not in nalezeno]
    assert not chybi, f"{cesta}: chybi funkce {chybi}"
    return [nalezeno[j] for j in jmena]


def nacti_funkce(stara=False):
    """-> slovnik se skutecnymi funkcemi z product_assemblies.py (nebo se starou verzi _assembly_price_components)"""
    fns = vytahni(PA, ["_num_or_none", "_eurobox_soucet_czk", "_assembly_price_components"])
    if stara:
        fns[2] = ast.parse(STARA_FUNKCE).body[0]
    ns = {"json": json}
    exec(compile(ast.Module(body=fns, type_ignores=[]), "product_assemblies", "exec"), ns)
    return ns


def sestava(id_, master, total, montaz, boxy_radky, kod="K-075-E30A72", bez_summary=False, vadna_data=False, data_none=False):
    if data_none:
        data = None
    elif vadna_data:
        data = "{tohle neni json"
    else:
        d = {"bom": [{"name": n, "total": t} for n, t in boxy_radky]}
        if not bez_summary:
            d["price_summary"] = {"total_czk": total, "montaz_czk": montaz}
        data = json.dumps(d)
    return {"id": id_, "data": data, "is_master": 1 if master else 0, "kod_sestavy": kod}


BOXY = [("eurobox_400x300x220 (produkt)", 760.0), ("eurobox_400x300x220 (produkt)", 760.0), ("profil 30x30 (Dogus)", 100.0)]
SESTAVY = {
    # (assembly_id, product_id) -> radek product_assemblies
    (344, 3943): sestava(344, True, 23081.4, 4616.2, BOXY),
    (345, 3943): sestava(345, False, 20262.4, 4052.5, BOXY, kod="K-075-E30B72"),
    (346, 3943): sestava(346, False, None, None, []),                      # varianta bez ceny
    (350, 3943): sestava(350, True, 23081.4, 4616.2, [("profil 30x30 (Dogus)", 100.0)]),   # bez euroboxu
    (351, 3943): sestava(351, True, None, None, [], data_none=True),       # zastupce bez dat
    (352, 3943): sestava(352, True, None, None, [], vadna_data=True),      # zastupce s poskozenym JSON
    (353, 3943): sestava(353, True, None, None, BOXY, bez_summary=True),   # zastupce bez price_summary
    (500, 3944): sestava(500, False, 16128.0, 3226.0, BOXY),               # sestava JINE karty
}


class FakeCur:
    def __init__(self, sestavy=None, produkt=None):
        self.sestavy, self.produkt, self.sql = sestavy if sestavy is not None else SESTAVY, produkt, []
        self.last = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        self.last = (sql, params)

    def fetchone(self):
        sql, params = self.last
        if "FROM product_assemblies WHERE id=%s AND shop_product_id=%s" in sql:
            return self.sestavy.get((params[0], params[1]))
        if "FROM shop_products WHERE id=%s" in sql:
            return self.produkt if self.produkt and self.produkt["id"] == params[0] else None
        return None


vysl = []


def over(prefix, nazev, podminka, detail=None):
    vysl.append((prefix, bool(podminka)))
    if prefix.startswith("MUT"):       # mutace: selhani je OCEKAVANE (dokazuje, ze test chybu chyti) - netvarit se jako FAIL
        print(("   (mutace prosla)  " if podminka else "   (mutace ZACHYCENA) ") + prefix + " " + nazev)
        return
    print(("OK   " if podminka else "FAIL ") + prefix + " " + nazev + ("" if podminka else "  -> " + repr(detail)))


def cast_a(ns, prefix):
    komp = ns["_assembly_price_components"]
    cur = FakeCur()
    r = komp(cur, 344, 3943, 23081.0)
    over(prefix + "A1", "zastupce: cena = cena karty, montaz a boxy ze svych dat (4 616 Kc / 1 520 Kc)",
         r == {"base_czk": 23081.0, "montaz_czk": 4616, "boxy_czk": 1520, "kod_sestavy": "K-075-E30A72"}, r)
    r = komp(cur, 344, 3943, 22999.0)
    over(prefix + "A2", "zastupce s RUCNE zmenenou cenou karty (22 999 != total): base = cena karty, montaz beze zmeny",
         r["base_czk"] == 22999.0 and r["montaz_czk"] == 4616, r)
    r = komp(cur, 345, 3943, 23081.0)
    over(prefix + "A3", "varianta (ne zastupce) beze zmeny: base = round(total), montaz, boxy",
         r == {"base_czk": 20262, "montaz_czk": 4052, "boxy_czk": 1520, "kod_sestavy": "K-075-E30B72"}, r)
    r = komp(cur, 346, 3943, 23081.0)
    over(prefix + "A4", "varianta bez ceny: base None (volajici hlasi price_on_request), montaz None, boxy None",
         r["base_czk"] is None and r["montaz_czk"] is None and r["boxy_czk"] is None, r)
    r = komp(cur, 350, 3943, 23081.0)
    over(prefix + "A5", "zastupce BEZ euroboxu v kusovniku: boxy None (volba 'bez boxu' se nenabidne), montaz ano",
         r["boxy_czk"] is None and r["montaz_czk"] == 4616, r)
    for aid, popis in ((351, "bez dat (NULL)"), (352, "s poskozenym JSON"), (353, "bez price_summary")):
        try:
            r = komp(cur, aid, 3943, 23081.0)
            ok = r is not None and r["base_czk"] == 23081.0 and r["montaz_czk"] is None
        except Exception as e:  # noqa: BLE001
            r, ok = repr(e), False
        over(prefix + "A6", f"zastupce {popis}: nespadne, cena = cena karty, montaz None", ok, r)
    r = komp(cur, 500, 3943, 23081.0)
    over(prefix + "A7", "assembly_id patri JINEMU produktu -> None (volajici vrati 400, bezpecnostni kontrola drzi)", r is None, r)
    over(prefix + "A8", "dotaz overuje dvojici (assembly_id, product_id)",
         cur.sql[-1][1] == (500, 3943) and "shop_product_id=%s" in cur.sql[-1][0], cur.sql[-1])
    r = komp(cur, 344, 3943, 23081.0)
    over(prefix + "A9", "tvar vysledku se nezmenil (volajici cetou presne tyhle 4 klice)",
         set(r) == {"base_czk", "montaz_czk", "boxy_czk", "kod_sestavy"}, sorted(r))


# ------------------------------------------------------------------------------- cast B: handler kosiku
def nacti_handler(ns_pa, log):
    fn = vytahni(CART, ["cart_add_item"])[0]
    st = log
    app = types.SimpleNamespace(post=lambda *a, **k: (lambda f: f), put=lambda *a, **k: (lambda f: f),
                                get=lambda *a, **k: (lambda f: f), delete=lambda *a, **k: (lambda f: f))

    class Conn:
        def cursor(self):
            return st["cur"]

        def commit(self):
            st["ops"].append("commit")

        def rollback(self):
            st["ops"].append("rollback")

        def close(self):
            st["ops"].append("close")

    class Cur(FakeCur):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if sql.lstrip().upper().startswith("INSERT INTO SHOP_CART_ITEMS"):
                st["inserts"].append(params)

    st["cur"] = Cur(produkt={"id": 3943, "active": 1, "is_archived": 0, "cfg_dily_id": None, "is_board_material": 0,
                              "is_profile_material": 0, "cutting_material_key": None, "price_czk_placeholder": 23081.0,
                              "supplier_name": None})
    ns = {
        "app": app, "login_required": lambda f: f, "jsonify": lambda d: d,
        "request": types.SimpleNamespace(get_json=lambda silent=True: st["body"]),
        "current_user": lambda: {"id": 793, "role": "user", "email": "zakaznik@test"},
        "_cart_owner_id": lambda u: u["id"], "get_conn": lambda: Conn(), "get_setting": lambda cur, k, d=None: d,
        "CART_MAX_QTY": 999, "_montaz_mista_map": lambda cur: {"praha": "Praha", "slavicin": "Slavičín"},
        "_assembly_price_components": ns_pa["_assembly_price_components"],
        "_fetch_cart_rows": lambda conn, owner: [], "_serialize_cart": lambda rows: {"items": []},
        "now_local": lambda: None,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "cart", "exec"), ns)
    return ns["cart_add_item"]


def pridej(ns_pa, body):
    log = {"body": body, "ops": [], "inserts": []}
    handler = nacti_handler(ns_pa, log)
    odp = handler()
    status = odp[1] if isinstance(odp, tuple) else None
    zprava = odp[0] if isinstance(odp, tuple) else odp
    # INSERT params: (owner, product_id, qty, coupon, assembly_id, montaz_zvolena, bez_boxu, montaz_misto)
    ins = log["inserts"][-1] if log["inserts"] else None
    return status, zprava, ins, log["ops"]


def cast_b(ns_pa, prefix):
    s, z, ins, ops = pridej(ns_pa, {"product_id": 3943, "assembly_id": 344, "montaz_zvolena": True, "montaz_misto": "praha", "bez_boxu": False})
    over(prefix + "B1", "KOSIK: zastupce + montaz (Praha) -> montaz_zvolena i misto se ULOZI (dril je ztrata ceny pro zakaznika)",
         s == 201 and ins is not None and ins[4] == 344 and ins[5] is True and ins[7] == "praha", (s, z, ins))
    s, z, ins, ops = pridej(ns_pa, {"product_id": 3943, "assembly_id": 344, "bez_boxu": True})
    over(prefix + "B2", "KOSIK: zastupce + 'bez boxu' -> bez_boxu se ULOZI, montaz zustane vypnuta",
         s == 201 and ins is not None and ins[4] == 344 and ins[6] is True and ins[5] is False and ins[7] is None, (s, z, ins))
    s, z, ins, ops = pridej(ns_pa, {"product_id": 3943, "assembly_id": 344, "montaz_zvolena": True, "montaz_misto": "slavicin", "bez_boxu": True})
    over(prefix + "B3", "KOSIK: zastupce + montaz i 'bez boxu' -> obe volby ulozeny",
         s == 201 and ins is not None and ins[5] is True and ins[6] is True and ins[7] == "slavicin", (s, z, ins))
    s, z, ins, ops = pridej(ns_pa, {"product_id": 3943, "assembly_id": 344, "montaz_zvolena": True})
    over(prefix + "B4", "KOSIK: zastupce + montaz BEZ mista -> 400 'Vyberte misto montaze', nic se neulozi",
         s == 400 and ins is None and "Vyberte místo montáže" in str(z), (s, z, ins))
    s, z, ins, ops = pridej(ns_pa, {"product_id": 3943, "assembly_id": 353, "montaz_zvolena": True, "montaz_misto": "praha"})
    over(prefix + "B5", "KOSIK: zastupce, jehoz sestava nema zapecenou montaz -> volba se zahodi (bez padu, bez mista)",
         s == 201 and ins is not None and ins[5] is False and ins[7] is None, (s, z, ins))
    s, z, ins, ops = pridej(ns_pa, {"product_id": 3943, "assembly_id": 345, "montaz_zvolena": True, "montaz_misto": "praha", "bez_boxu": True})
    over(prefix + "B6", "KOSIK: bezna varianta (ne zastupce) funguje stejne jako driv",
         s == 201 and ins is not None and ins[4] == 345 and ins[5] is True and ins[6] is True, (s, z, ins))
    s, z, ins, ops = pridej(ns_pa, {"product_id": 3943, "assembly_id": 500, "montaz_zvolena": True, "montaz_misto": "praha"})
    over(prefix + "B7", "KOSIK: sestava JINE karty -> 400 'Neplatna varianta', nic se neulozi",
         s == 400 and ins is None and "Neplatná varianta" in str(z), (s, z, ins))
    s, z, ins, ops = pridej(ns_pa, {"product_id": 3943, "qty": 2})
    over(prefix + "B8", "KOSIK: bezny produkt bez varianty beze zmeny (assembly_id 0, volby vypnute)",
         s == 201 and ins is not None and ins[2] == 2 and ins[4] == 0 and ins[5] is False and ins[6] is False, (s, z, ins))
    s, z, ins, ops = pridej(ns_pa, {"product_id": 3943, "assembly_id": 346})
    over(prefix + "B9", "KOSIK: varianta bez ceny -> 409 price_on_request (beze zmeny)",
         s == 409 and ins is None, (s, z, ins))


# ------------------------------------------------------------------------------- hlavni beh
ns_nova = nacti_funkce()
cast_a(ns_nova, "")
cast_b(ns_nova, "")

# cast C: kontrakt - zastupce se nerozlisuje nikde jinde (cart.py, orders.py)
for nazev, cesta in (("cart.py", CART), ("orders.py", ORDERS)):
    with open(cesta, encoding="utf-8") as f:
        txt = f.read()
    over("", f"C {nazev}: nepouziva is_master (zastupce rozlisuje jen _assembly_price_components)", "is_master" not in txt)
    over("", f"C {nazev}: volby montaz/boxy klampuje podle vysledku _assembly_price_components",
         'assembly_ceny.get("montaz_czk") is not None' in txt or "assembly_montaz_czk is not None" in txt)

# cast D: puvodni chybna verze musi selhat (jinak by test chybu nechytal)
print("\n--- mutace: puvodni (chybna) verze _assembly_price_components ---")
pocet_pred = len(vysl)
ns_stara = nacti_funkce(stara=True)
cast_a(ns_stara, "MUT ")
cast_b(ns_stara, "MUT ")
mutace = vysl[pocet_pred:]
selhalo = [p for p, ok in mutace if not ok]
del vysl[pocet_pred:]
over("", "D mutace: puvodni verze selhava na zastupci (A1, A2, A5, B1, B2, B3 musi padnout)",
     {"MUT A1", "MUT A2", "MUT A5", "MUT B1", "MUT B2", "MUT B3"} <= {p.strip() for p in selhalo}, selhalo)
over("", "D mutace: puvodni verze presto prosla to, co se nezmenilo (A3, A4, A7, B6, B7, B8 musi projit)",
     not ({"MUT A3", "MUT A4", "MUT A7", "MUT B6", "MUT B7", "MUT B8"} & {p.strip() for p in selhalo}), selhalo)

ok = sum(1 for _, o in vysl if o)
print(f"\nVYSLEDEK zastupce + montaz v kosiku: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
