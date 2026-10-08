#!/usr/bin/env python3
"""FAZE 2 generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08): KOTVENE zaplaty zivych souboru api/ (registr, routy stolu, kosik, nabidka) + NOVE soubory api/ (oploceni_*.py).
Z ZIVYCH souboru v <src_api> udela upravene soubory v <dst_api>; kazda kotva se musi v souboru vyskytovat PRAVE JEDNOU (assert), jinak se nic nezapise. src = dst => nasazeni primo do zivych souboru.
Zasady: zpetne kompatibilni (stul a dopravnik beze zmeny chovani; stare nazvy registru zustavaji), cizi soubory (bot5: kosik, nabidka; bot10: stul_shop) jen minimalnimi hunky.
  apply_patches_f2.py <src_api> <dst_api>"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NOVE_API = ("oploceni_konfigurator.py", "oploceni_glb.py", "oploceni_cena.py", "oploceni_shop.py")


def nahrad(s, a, b, label):
    n = s.count(a)
    if n != 1:
        raise AssertionError(f"kotva '{label}': {n} vyskytu (ocekavan 1)")
    return s.replace(a, b)


# ---------------------------------------------------------------------------------------------------------------------
# api/konfigurator_registr.py: rozcestnik recept -> modul (dopravnik, oploceni); stare nazvy a chovani dopravniku zustavaji
# ---------------------------------------------------------------------------------------------------------------------
REGISTR_NOVE = '''

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# DALSI MODULY (bot8, 2026-10-08): recept -> modul. Stul zustava v stul_shop, dopravnik (api/dopravnik_shop.py) a ochranny kryt a oploceni (api/oploceni_shop.py) jsou volitelne moduly s TYMZ kontraktem
# (odpoved_schema / odpoved_resolve / zna_hash / odpoved_model / odpoved_glb / pro_objednavku / glb_bytes). Stare nazvy (dopravnik_modul, dopravnik_pro, je_dopravnik, PREFIX_TOKENU_DOPRAVNIKU) se nemeni.
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
RECEPT_OPLOCENI = "oploceni_kryt"
MODUL_OPLOCENI = "oploceni_shop"
PREFIX_TOKENU_OPLOCENI = "opl."                 # token GLB oploceni = "opl." + telo.exp.podpis (jako "dop." u dopravniku; token stolu zacina base64 JSON, nemuzou se splest)
MODULY = {RECEPT_DOPRAVNIK: (MODUL_DOPRAVNIK, PREFIX_TOKENU_DOPRAVNIKU), RECEPT_OPLOCENI: (MODUL_OPLOCENI, PREFIX_TOKENU_OPLOCENI)}           # recept -> (jmeno modulu, prefix tokenu GLB)
RECEPTY_BEZ_MONTAZE = frozenset(MODULY)         # montaz se u produktu techto receptu nenabizi (typ sestavy bez sazby)
_HLEDANI_MODULY = {}


def modul_receptu(recept):
    """Modul pro recept (dopravnik / oploceni), nebo None (stul, neznamy recept, modul neexistuje). Chyba UVNITR existujiciho modulu se NEzahlazuje; chybejici modul se znovu hleda nejdriv za 30 s."""
    if recept == RECEPT_DOPRAVNIK:
        return dopravnik_modul()
    jm = MODULY.get(recept)
    if jm is None:
        return None
    m = sys.modules.get(jm[0])
    if m is not None:
        return m
    st = _HLEDANI_MODULY.setdefault(jm[0], {"t": 0.0, "existuje": False})
    if not st["existuje"] and time.time() - st["t"] < 30:
        return None
    st.update(t=time.time(), existuje=importlib.util.find_spec(jm[0]) is not None)
    return importlib.import_module(jm[0]) if st["existuje"] else None


def modul_pro(product_id):
    """Modul (dopravnik / oploceni), je-li product_id karta konfigurovatelneho produktu s takovym receptem (a modul existuje), jinak None (stul, neznamy produkt)."""
    return modul_receptu(recept_produktu(product_id))


def je_oploceni(product_id):
    return recept_produktu(product_id) == RECEPT_OPLOCENI


def bez_montaze(product_id):
    """True, kdyz se u receptu produktu montaz nenabizi (dopravnik, oploceni)."""
    return recept_produktu(product_id) in RECEPTY_BEZ_MONTAZE


def mimo_stul(product_id):
    """True pro produkt s receptem jineho modulu nez stul (dopravnik, oploceni): nema system profilu stolu."""
    return recept_produktu(product_id) in MODULY


def recept_z_tokenu(token):
    """Recept modulu podle prefixu tokenu GLB ('dop.' / 'opl.'), nebo None (token stolu)."""
    for recept, (_m, prefix) in MODULY.items():
        if str(token).startswith(prefix):
            return recept
    return None


def modul_z_tokenu(token):
    return modul_receptu(recept_z_tokenu(token))


def modul_pro_hash(h):
    """Modul, ktery zna hash konfigurace (route modelu), jinak None. Dopravnik prvni (dosavadni poradi), pak ostatni."""
    for recept in MODULY:
        m = modul_receptu(recept)
        if m is not None and getattr(m, "zna_hash", None) and m.zna_hash(h):
            return m
    return None


def produkt_pro_recept(recept):
    """(id, active) karty konfigurovatelneho produktu s receptem `recept` (nejnizsi id), nebo None - pro stranky generatoru bez pevneho ID karty (jen zamestnanci)."""
    ids = sorted(int(k) for k, v in _stul()._produkty().items() if v == recept and str(k).isdigit())
    if not ids:
        return None
    from app import get_conn
    cur = get_conn().cursor()
    cur.execute("SELECT id, active, is_archived FROM shop_products WHERE id=%s", (ids[0],))
    r = cur.fetchone()
    return ids[0], bool(r and r["active"] and not r["is_archived"])
'''


def patch_registr(s):
    s = nahrad(s, '''    return bool(_stul().konfigurovatelny(product_id)) or dopravnik_pro(product_id) is not None''',
               '''    return bool(_stul().konfigurovatelny(product_id)) or modul_pro(product_id) is not None''', "registr konfigurovatelny")
    s = nahrad(s, '''    dm = dopravnik_pro(product_id)
    if dm is not None:
        return dm.pro_objednavku(selection, rules_version, lang, product_id)''', '''    dm = modul_pro(product_id)
    if dm is not None:
        return dm.pro_objednavku(selection, rules_version, lang, product_id)''', "registr pro_objednavku")
    s = nahrad(s, '''    dm = dopravnik_pro(product_id)
    if dm is not None:
        return dm.glb_bytes(selection, razitka=razitka)''', '''    dm = modul_pro(product_id)
    if dm is not None:
        return dm.glb_bytes(selection, razitka=razitka)''', "registr glb_bytes")
    return s.rstrip("\n") + "\n" + REGISTR_NOVE


# ---------------------------------------------------------------------------------------------------------------------
# api/stul_shop.py: delegace v routach (schema, resolve, model, glb) pres zobecneny registr + staff routa "recept -> id karty"
# ---------------------------------------------------------------------------------------------------------------------
RECEPT_ROUTA = '''@app.get("/api/shop/configurator/recepty/<recept>")
def stul_shop_recept_produkt(recept):
    """Zamestnanci: id karty konfigurovatelneho produktu podle receptu (stranky generatoru nemaji pevne ID karty; app_settings.configurator_products). Neprihlaseny / ne zamestnanec = 403,
    zadna karta (nebo neznamy recept) = 404. Odpoved {recept, product_id, active}."""
    lim = _limit("schema", *LIMIT_SCHEMA)
    if lim:
        return lim
    if not _je_staff():
        return jsonify({"error": "forbidden"}), 403
    nalez = konfigurator_registr.produkt_pro_recept(recept)
    if nalez is None:
        return _nenalezeno()
    return jsonify({"recept": recept, "product_id": nalez[0], "active": nalez[1]})


'''


def patch_stul_shop(s):
    s = nahrad(s, '''    dm = konfigurator_registr.dopravnik_pro(product_id)
    if dm is not None:
        return dm.odpoved_schema(product_id)''', '''    dm = konfigurator_registr.modul_pro(product_id)
    if dm is not None:
        return dm.odpoved_schema(product_id)''', "stul_shop schema")
    s = nahrad(s, '''    dm = konfigurator_registr.dopravnik_pro(body.get("product_id"))''', '''    dm = konfigurator_registr.modul_pro(body.get("product_id"))''', "stul_shop resolve")
    s = nahrad(s, '''    dm = konfigurator_registr.dopravnik_modul()
    if dm is not None and dm.zna_hash(h):
        return dm.odpoved_model(h)''', '''    dm = konfigurator_registr.modul_pro_hash(h)
    if dm is not None:
        return dm.odpoved_model(h)''', "stul_shop model")
    s = nahrad(s, '''    if token.startswith(konfigurator_registr.PREFIX_TOKENU_DOPRAVNIKU):
        dm = konfigurator_registr.dopravnik_modul()
        return dm.odpoved_glb(token) if dm is not None else _nenalezeno()''', '''    if konfigurator_registr.recept_z_tokenu(token):
        dm = konfigurator_registr.modul_z_tokenu(token)
        return dm.odpoved_glb(token) if dm is not None else _nenalezeno()''', "stul_shop glb")
    s = nahrad(s, '''@app.get("/api/shop/products/<int:product_id>/configurator")
def stul_shop_schema(product_id):''', RECEPT_ROUTA + '''@app.get("/api/shop/products/<int:product_id>/configurator")
def stul_shop_schema(product_id):''', "stul_shop routa recepty")
    return s


# ---------------------------------------------------------------------------------------------------------------------
# api/konfigurace_kosik.py + api/nabidka_z_konfigurace.py: montaz se u oploceni nenabizi, nazev radku bere rozmery z modulu produktu, nabidka bez systemu stolu
# ---------------------------------------------------------------------------------------------------------------------
def patch_kosik(s):
    s = nahrad(s, '''    if product_id is not None and konfigurator_registr.je_dopravnik(product_id):
        return None''', '''    if product_id is not None and konfigurator_registr.bez_montaze(product_id):         # dopravnik a oploceni: montaz se nenabizi
        return None''', "kosik typ_produktu")
    s = nahrad(s, '''def jmeno_radku(product_name, selection, kod):
    """Nazev radku objednavky a dokladu: nazev karty, rozmery desky a kod konfigurace (<= 255 znaku)."""
    klice = ("len", "width") if "len" in selection else ("w", "d", "h")                # dopravnik: delka x sirka, stul: sirka x hloubka x vyska
    rozmery = " × ".join(str(int(selection[k])) for k in klice if isinstance(selection.get(k), (int, float)))''',
               '''def jmeno_radku(product_name, selection, kod, rozmery_text=None):
    """Nazev radku objednavky a dokladu: nazev karty, rozmery desky a kod konfigurace (<= 255 znaku). `rozmery_text` = rozmery z modulu produktu (oploceni: jen ty, ktere ve stavbe existuji)."""
    klice = ("len", "width") if "len" in selection else ("w", "d", "h")                # dopravnik: delka x sirka, stul: sirka x hloubka x vyska
    rozmery = rozmery_text or " × ".join(str(int(selection[k])) for k in klice if isinstance(selection.get(k), (int, float)))''', "kosik jmeno_radku")
    s = nahrad(s, '''"price_summary": {**souhrn_cen, "total_czk": net}, "warnings": [], "montaz_pct": pct, "montaz_czk": montaz_czk,
    }''', '''"price_summary": {**souhrn_cen, "total_czk": net}, "warnings": [], "montaz_pct": pct, "montaz_czk": montaz_czk, "rozmery_text": r.get("rozmery_text"),
    }''', "kosik vyres rozmery")
    s = nahrad(s, '''"product_name_snapshot": jmeno_radku(product.get("name"), res["selection"], res["kod"]),''',
               '''"product_name_snapshot": jmeno_radku(product.get("name"), res["selection"], res["kod"], res.get("rozmery_text")),''', "kosik radek_objednavky nazev")
    return s


def patch_nabidka(s):
    s = nahrad(s, '''        dopravnik = konfigurator_registr.je_dopravnik(produkt["id"])''', '''        dopravnik = konfigurator_registr.mimo_stul(produkt["id"])                       # dopravnik i oploceni: bez systemu stolu a bez montaze''', "nabidka mimo_stul")
    s = nahrad(s, '''        nazev = kk.jmeno_radku(produkt["name"], res["selection"], res["kod"])''', '''        nazev = kk.jmeno_radku(produkt["name"], res["selection"], res["kod"], res.get("rozmery_text"))''', "nabidka nazev")
    return s


PATCHE = {"konfigurator_registr.py": patch_registr, "stul_shop.py": patch_stul_shop, "konfigurace_kosik.py": patch_kosik, "nabidka_z_konfigurace.py": patch_nabidka}


def aplikuj(src_api, dst_api):
    vysl = {}
    for jmeno, fn in PATCHE.items():
        with open(os.path.join(src_api, jmeno), encoding="utf-8") as f:
            vysl[jmeno] = fn(f.read())
    for jmeno in NOVE_API:
        with open(os.path.join(HERE, "novy_api", jmeno), encoding="utf-8") as f:
            vysl[jmeno] = f.read()
    for jmeno, text in vysl.items():
        cil = os.path.join(dst_api, jmeno)
        if os.path.islink(cil):
            os.remove(cil)
        with open(cil, "w", encoding="utf-8") as f:
            f.write(text)
    return sorted(vysl)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    print("zapsano:", ", ".join(aplikuj(args[0], args[1])))
