"""Rozcestnik konfiguratoru (bot5, 2026-10-07): ktery modul patri produktu - konfigurovatelny stul (api/stul_shop.py) nebo konfigurovatelny valeckovy dopravnik (api/dopravnik_shop.py).

Recept produktu je v app_settings.configurator_products ({id karty: recept}, stejny zdroj jako u stolu, cache 60 s v stul_shop._produkty). Recepty stolu (stul_system30 / 35 / 40 / 41)
zustavaji v stul_shop; recept `dopravnik_valeckovy` patri dopravnikovi. Modul dopravniku je volitelny: dokud neexistuje (nebo kdyz neni zadny produkt s jeho receptem), vsechno se chova jako dosud
(stolove routy vraci pro cizi produkt 404, kosik a nabidka berou produkt jako bezny).

Pouziti: routy v stul_shop.py (schema, resolve, model, glb) na zacatku zkusi `dopravnik_pro(product_id)` / `dopravnik_modul()`; kosik (konfigurace_kosik.py) a nabidka z konfigurace
(nabidka_z_konfigurace.py) volaji `konfigurovatelny`, `pro_objednavku`, `glb_bytes` tady, ne primo stul_shop.
"""
import importlib
import importlib.util
import sys
import time

RECEPT_DOPRAVNIK = "dopravnik_valeckovy"
MODUL_DOPRAVNIK = "dopravnik_shop"
PREFIX_TOKENU_DOPRAVNIKU = "dop."             # token GLB dopravniku = "dop." + telo.exp.podpis; token stolu ma jen 3 casti oddelene teckou a zacina base64 JSON, takze se nemuzou splest


def _stul():
    import stul_shop
    return stul_shop


def recept_produktu(product_id):
    """Recept karty podle app_settings.configurator_products, nebo None (neznamy / nekonfigurovatelny produkt, neplatne id)."""
    try:
        klic = str(int(product_id))
    except (TypeError, ValueError):
        return None
    return _stul()._produkty().get(klic)


def je_dopravnik(product_id):
    return recept_produktu(product_id) == RECEPT_DOPRAVNIK


_HLEDANI = {"t": 0.0, "existuje": False}


def dopravnik_modul():
    """Modul api/dopravnik_shop.py, nebo None, kdyz soubor neexistuje (chyba UVNITR existujiciho modulu se NEzahlazuje - projevi se u dopravniku, stolu se netyka).
    Uz nacteny modul se vraci hned; chybejici se znovu hleda nejdriv za 30 s (routy modelu volaji tuhle funkci pri kazdem pozadavku)."""
    m = sys.modules.get(MODUL_DOPRAVNIK)
    if m is not None:
        return m
    if not _HLEDANI["existuje"] and time.time() - _HLEDANI["t"] < 30:
        return None
    _HLEDANI.update(t=time.time(), existuje=importlib.util.find_spec(MODUL_DOPRAVNIK) is not None)
    return importlib.import_module(MODUL_DOPRAVNIK) if _HLEDANI["existuje"] else None


def dopravnik_pro(product_id):
    """Modul dopravniku, je-li product_id karta konfigurovatelneho dopravniku (a modul existuje), jinak None."""
    if not je_dopravnik(product_id):
        return None
    return dopravnik_modul()


def konfigurovatelny(product_id):
    """True pro konfigurovatelny stul i dopravnik (dopravnik jen s existujicim modulem)."""
    return bool(_stul().konfigurovatelny(product_id)) or dopravnik_pro(product_id) is not None


def pro_objednavku(selection, rules_version, lang, product_id):
    """Konfigurace pro kosik / objednavku / nabidku: stul -> stul_shop.pro_objednavku, dopravnik -> dopravnik_shop.pro_objednavku (stejny tvar odpovedi)."""
    dm = dopravnik_pro(product_id)
    if dm is not None:
        return dm.pro_objednavku(selection, rules_version, lang, product_id)
    return _stul().pro_objednavku(selection, rules_version, lang, product_id)


def glb_bytes(selection, product_id, razitka=None):
    """GLB (bytes) konfigurace pro vyber a kartu produktu (u stolu podle jeho systemu profilu). Razitka loga jsou na vsech 3D modelech generatoru (WORKFLOW pravidlo 61, Robert 2026-10-08):
    razitka=None = vychozi nastaveni generatoru (stul: stul_glb, prepina bot8; dopravnik: vzdy S razitky), True/False se predava vyslovne (vypnout je vyzaduje Robertuv pokyn)."""
    dm = dopravnik_pro(product_id)
    if dm is not None:
        return dm.glb_bytes(selection, razitka=True if razitka is None else razitka)
    sh = _stul()
    return sh.glb_bytes(selection, sh.system_pro_produkt(product_id), razitka=razitka)
