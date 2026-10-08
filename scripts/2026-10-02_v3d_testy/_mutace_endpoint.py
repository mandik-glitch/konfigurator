#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mutacni kontrola testu endpointu (test_endpoint.py): rozbije jednu vec v api/vandr_scene_offers.py a overi,
ze testy selzou (jinak by dane pravidlo hlidal jen komentar). Vypise radek na mutaci; "!!!" = testy chybu nechytily
(exit 1). Nic se nezapisuje mimo <OUT>; DB je atrapa. Spusteni: api/venv/bin/python _mutace_endpoint.py (~1 min)."""
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import test_endpoint as T  # noqa: E402

if not T.BLENDER_OK:
    print("PRESKOCENO: Blender neni k dispozici (mutace potrebuji skutecny build)")
    sys.exit(0)


def run(names):
    suite = unittest.TestSuite()
    for n in names:
        suite.addTest(unittest.defaultTestLoader.loadTestsFromName(n, T))
    r = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return len(r.failures) + len(r.errors)


cases = []


def mutate(nazev, attrs, tests):
    """attrs: {atribut modulu vandr_scene_offers: nova hodnota | @factory(vso)->hodnota}. Runner volá setUpModule()
    znovu pri kazdem behu (nove atrapy a CERSTVE nactene moduly), proto se mutace aplikuje az v obalenem setUpModule."""
    puvodni_setup = T.setUpModule

    def setup_s_mutaci():
        puvodni_setup()
        vso = T.S["vso"]
        for k, v in attrs.items():
            setattr(vso, k, v(vso) if getattr(v, "_factory", False) else v)
    T.setUpModule = setup_s_mutaci
    try:
        cases.append((nazev, run(tests)))
    finally:
        T.setUpModule = puvodni_setup


def factory(fn):
    fn._factory = True
    return fn


@factory
def zaloha_flask(vso):
    def f():
        import v3d_mark
        return v3d_mark.derive_secret(T.S["app"].secret_key), None
    return f


@factory
def bez_ceny(vso):
    puvodni_can = vso.can_create_offer

    def f(karta_row, katalog_dir=None):
        if karta_row and karta_row.get("glb_file") and (karta_row.get("sku") or "").startswith("VD-"):
            return True, None
        return puvodni_can(karta_row, katalog_dir)
    return f


@factory
def bez_opakovani(vso):
    return lambda uuid: (vso._fetch_vandr_offer_data(uuid, v3d=True), None)


def boom(*a, **k):
    raise RuntimeError("3D shodi nabidku")


mutate("brana zakaznickeho GLB vypnuta", {"_over_zakaznicky_glb": lambda raw: raw},
       ["TestSelhani.test_otravena_cache_se_nepousti_k_zakaznikovi"])
mutate("klic znaceni se bere i z FLASK_SECRET_KEY", {"_znackovaci_klic": zaloha_flask},
       ["TestZnaceni.test_flask_klic_se_nepouzije_jako_zaloha"])
mutate("znaceni se nikdy nevklada", {"_oznac_model": lambda g, oid: (g, "vypnuto", None)},
       ["TestZnaceni.test_zapnuto_s_klicem_a_cte_se"])
mutate("znaceni se tvari, ze probehlo (uloz neoznaceny)", {"_oznac_model": lambda g, oid: (g, "zapnuto", None)},
       ["TestZnaceni.test_zapnuto_s_klicem_a_cte_se"])
mutate("selhani znaceni neprepne na staticky model",
       {"_oznac_model": lambda g, oid: (g, "zapnuto", None)},
       ["TestZnaceni.test_znaceni_selze_s_klicem_je_v3d_false"])
mutate("can_create_offer nekontroluje cenu", {"can_create_offer": bez_ceny},
       ["TestCanCreateOffer.test_texty_a_poradi", "TestCanCreateOffer.test_endpoint_stejne_statusy_a_texty"])
mutate("chybejici --v3d = chyba 500", {"_nacti_vandr_data": bez_opakovani},
       ["TestSelhani.test_prikaz_bez_v3d", "TestSelhani.test_prikaz_s_v3d_selze_jinak"])
mutate("chyba 3D shodi tvorbu nabidky", {"_postav_v3d_model": boom},
       ["TestSelhani.test_modul_offer_model_nejde_nacist", "TestSelhani.test_neocekavana_chyba_buildu"])
def bez_nahrady(*a, **k):
    from_ = ValueError("atrapa: nahrada vypnuta")
    raise from_


@factory
def vandr_bez_prednosti(vso):
    puvodni = vso._dopln_obrazky

    def f(shop_product_id, karta, part, model_glb):
        return puvodni(shop_product_id, karta, {}, model_glb)          # jako by Vandr nemel zadne obrazky
    return f


mutate("nahrada obrazku vypnuta (chybejici Vandr obrazky = chyba)", {"_dopln_obrazky": bez_nahrady},
       ["TestNahradniObrazky.test_v3d_karta_bez_vandr_obrazku_snimky_otocky",
        "TestNahradniObrazky.test_400_zustava_jen_pro_vyjmenovane_pripady_obrazky_mezi_nimi_nejsou"])
mutate("Vandr obrazky nemaji prednost pred nahradou", {"_dopln_obrazky": vandr_bez_prednosti},
       ["TestNahradniObrazky.test_vsechno_vandr_beze_zmeny", "TestNahradniObrazky.test_kombinace_vandr_a_nahrada"])
mutate("rozpocet 55 s zvysen", {"CELKOVY_LIMIT_S": 70}, ["TestSelhani.test_casovy_rozpocet"])
mutate("rezerva na staticky model pryc", {"REZERVA_STATICKY_MODEL_S": 0}, ["TestSelhani.test_casovy_rozpocet"])

bad = 0
for nazev, fails in cases:
    print("%-58s selhanych testu: %d  %s" % (nazev, fails, "OK (test chybu chyti)" if fails else "!!! TEST CHYBU NECHYTIL"))
    bad += not fails
sys.exit(1 if bad else 0)
