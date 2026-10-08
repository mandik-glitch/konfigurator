#!/usr/bin/env python3
"""Zaplata api/stul_glb.py (bot8, 2026-10-08, WORKFLOW pravidlo 61): razitka loga na VSECH 3D modelech generatoru = `model_pro_parametry(parametry, razitka=None)` ma razitka VYCHOZI (RAZITKA_VYCHOZI = True);
model s razitky plni i spolecne vedlejsi cache (posun, rozsahy, extra), takze `vodici` (uchyty ve 3D, payload luxu, zive tazeni) funguje nad modelem S razitky; komprimovana cache GLB (`zakoduj_pro_klienta`) se
klicuje i delkou dat (model s razitky a bez nich se pri stejnem hashi nesmi zamenit).
Pouziti: patch_glb.py <vstup> <vystup>   (kotvene nahrazeni: kazda kotva musi byt v souboru prave jednou)"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
if "RAZITKA_VYCHOZI = True" in s:                          # uz aplikovano (commit 3b7d5076): vystup = vstup
    open(dst, "w", encoding="utf-8").write(s)
    print("stul_glb.py: razitka uz jsou vychozi (3b7d5076), nic se nemeni")
    sys.exit(0)


def sub(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


STARE = '''_GLB_RAZITKA_CACHE = OrderedDict()                            # hash -> GLB s razitky (jen model v online nabidce); oddelene od cache verejneho modelu


def model_pro_parametry(parametry, razitka=False):
    """(hash, bytes GLB) pro parametry konfigurace; LRU cache podle kanonickeho hashe. `razitka=True` = model PRO ONLINE NABIDKU s razitky loga na profilech (stul_razitka; Robert 2026-10-06:
    razitkovani je jen u modelu v nabidce): jina cache a verejny model, `vodici` ani zive rozsahy se nemeni. Vyhodi StulChyba/GlbChyba."""
    h = kanonicky_hash(parametry)
    if razitka:
        if h in _GLB_RAZITKA_CACHE:
            _GLB_RAZITKA_CACHE.move_to_end(h)
            return h, _GLB_RAZITKA_CACHE[h]
        import stul_razitka
        r = S.sestav_stul(**parametry)
        posledni = (_POSLEDNI_POSUN[0], _POSLEDNI_ROZSAHY[0], _POSLEDNI_EXTRA[0])             # poskladej_glb je zapisuje; verejny model ma vlastni cache, nesmi o ne prijit
        try:
            data = poskladej_glb(r["dily"], r["rozmery"], stul_koty.koty(r), razitka=stul_razitka.razitka(r, h))
        finally:
            _POSLEDNI_POSUN[0], _POSLEDNI_ROZSAHY[0], _POSLEDNI_EXTRA[0] = posledni
        _GLB_RAZITKA_CACHE[h] = data
        while len(_GLB_RAZITKA_CACHE) > CACHE_MAX:
            _GLB_RAZITKA_CACHE.popitem(last=False)
        return h, data'''

NOVE = '''RAZITKA_VYCHOZI = True                                        # WORKFLOW pravidlo 61 (Robert 2026-10-08: "razitka budou na vsech 3D modelech ve vsech generatorech"): logo LOGIMAN.CZ na profilech u ziveho modelu, kosiku, nabidky i karet; False jen na Robertuv pokyn
_GLB_RAZITKA_CACHE = OrderedDict()                            # hash -> GLB S razitky; oddelene od cache modelu bez razitek (_GLB_CACHE). Vedlejsi cache (posun, rozsahy, extra) jsou SPOLECNE pro oba modely (razitka je nemeni, overuje regrese)


def model_pro_parametry(parametry, razitka=None):
    """(hash, bytes GLB) pro parametry konfigurace; LRU cache podle kanonickeho hashe. `razitka=None` = VYCHOZI NASTAVENI GENERATORU (RAZITKA_VYCHOZI = True: logo LOGIMAN.CZ na profilech - zivy model, kosik, nabidka,
    karta; WORKFLOW pravidlo 61, Robert 2026-10-08, pravidla umisteni stul_razitka beze zmeny), True / False se predava vyslovne (False = holy model bez razitek: testy geometrie, srovnani). Model s razitky a bez nich
    ma kazdy SVOU cache (razitka nejsou soucasti hashe konfigurace, jsou z nej odvozena); `vodici`, uchyty a zive tazeni ctou posun / rozsahy / extra z cache SPOLECNYCH - razitka zadny dil neposouvaji (jsou jen pripojena
    na konec materialu hlinik a jako dalsi uzly), takze model s razitky je plnohodnotny verejny model. Vyhodi StulChyba/GlbChyba."""
    if razitka is None:
        razitka = RAZITKA_VYCHOZI
    h = kanonicky_hash(parametry)
    if razitka:
        if h in _GLB_RAZITKA_CACHE and h in _META_CACHE and h in _ROZSAHY_CACHE and h in _EXTRA_CACHE:
            for c_ in (_GLB_RAZITKA_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE):
                c_.move_to_end(h)                              # vsechny ctyri cache se drzi spolecne (jinak by `vodici` pro horky model ztratilo posun a vratilo None)
            return h, _GLB_RAZITKA_CACHE[h]
        import stul_razitka
        r = S.sestav_stul(**parametry)
        data = poskladej_glb(r["dily"], r["rozmery"], stul_koty.koty(r), razitka=stul_razitka.razitka(r, h))
        _GLB_RAZITKA_CACHE[h] = data
        _META_CACHE[h] = _POSLEDNI_POSUN[0]
        _ROZSAHY_CACHE[h] = _POSLEDNI_ROZSAHY[0]
        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}
        for c_ in (_GLB_RAZITKA_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE):
            while len(c_) > CACHE_MAX:
                c_.popitem(last=False)
        return h, data'''

sub(STARE, NOVE)
sub("    klic = (h, kod)\n", "    klic = (h, kod, len(data))                                       # model S razitky a BEZ nich maji stejny hash, ale jina data: klic nese i delku dat\n")
sub("bytes se drzi v LRU podle (hash, kodovani), takze se stejny model nekomprimuje dvakrat.", "bytes se drzi v LRU podle (hash, kodovani, delka dat), takze se stejny model nekomprimuje dvakrat a model s razitky se nezamění s modelem bez nich.")
open(dst, "w", encoding="utf-8").write(s)
print("OK stul_glb.py: razitka vychozi")
