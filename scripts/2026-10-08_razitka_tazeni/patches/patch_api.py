#!/usr/bin/env python3
"""Zaplata API (bot8, 2026-10-08; Robert: „razitka na generatoru pri tazeni zustavaji na miste“): model S razitky ma v `vodici.ovladani` nove pole `razitka` = [{dil, uzel, vypln: [uzel, od, pocet]}]
(dil = index dilu, na kterem razitko sedi; uzel = uzel n<i> loga v GLB; vypln = vrcholy vyplne drazky v uzlu hlinik), podle ktereho prohlizec pri zivem tazeni hybe razitka s dilem (v3d-ovladani.js).
Menit se `api/stul_razitka.py` (kazde razitko nese `dil`), `api/stul_glb.py` (info o razitkach pri skladani, cache, `vodici`) a `api/stul_ovladani_verejne.py` (pole se predava do verejneho popisu).
GLB bajty, pravidla umisteni, hash, cena a vedlejsi cache (posun, rozsahy, extra) se NEMENI.
Pouziti: patch_api.py <koren repa>   (soubory se prepisuji na miste; kazda kotva musi byt v souboru prave jednou)"""
import io
import os
import sys

koren = sys.argv[1] if len(sys.argv) > 1 else "/opt/konfigurator"
if "_RAZITKA_CACHE" in io.open(os.path.join(koren, "api/stul_glb.py"), encoding="utf-8").read():
    print("API: zaplata uz je aplikovana (commit e45888a3), nic se nemeni")
    sys.exit(0)


def uprav(soubor, zmeny):
    p = os.path.join(koren, soubor)
    s = io.open(p, encoding="utf-8").read()
    for a, b in zmeny:
        assert s.count(a) == 1, (soubor, s.count(a), a[:90])
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8").write(s)
    print("OK", soubor)


uprav("api/stul_razitka.py", [
    ('        out.append({"klic": klice[i], "lok": c["lok"],', '        out.append({"klic": klice[i], "dil": int(i), "lok": c["lok"],'),
    ('"vypln": {"pos", "q", "rozmer": [delka, sirka, hloubka]}}; souradnice generatoru.', '"vypln": {"pos", "q", "rozmer": [delka, sirka, hloubka]}, "dil": index dilu (v `r["dily"]`), na kterem razitko sedi}; souradnice generatoru.'),
])

uprav("api/stul_glb.py", [
    ("_EXTRA_CACHE = OrderedDict()\nSUPLIK_OTEVRENI_PODIL",
     "_EXTRA_CACHE = OrderedDict()\n"
     "_POSLEDNI_RAZITKA = [None]     # [{dil, uzel, vypln: [uzel, od, pocet]}] razitek posledniho modelu S razitky (None = model bez razitek): kde je logo (uzel n<uzel>) a jeho vypln drazky (vrcholy v uzlu hlinik) a na kterem dilu sedi; prohlizec je pri zivem tazeni hybe s dilem\n"
     "_RAZITKA_CACHE = OrderedDict()   # hash -> info o razitkach modelu S razitky (jen k modelu v _GLB_RAZITKA_CACHE)\n"
     "SUPLIK_OTEVRENI_PODIL"),
    ("    for rz in (razitka or []):                       # vypln drazky pod logem (kvadr:",
     "    vyplne_rozsahy = []                              # (od, pocet) vrcholu vyplne kazdeho razitka v uzlu hlinik (zive tazeni je hybe s dilem)\n"
     "    for rz in (razitka or []):                       # vypln drazky pod logem (kvadr:"),
    ('        g["T"].append(Tm + g["base"])\n        g["base"] += len(Pm)\n    vsechny = np.vstack(',
     '        g["T"].append(Tm + g["base"])\n        vyplne_rozsahy.append((g["base"], len(Pm)))\n        g["base"] += len(Pm)\n    vsechny = np.vstack('),
    ("    _POSLEDNI_EXTRA[0] = extra or None\n", "    _POSLEDNI_EXTRA[0] = extra or None\n    _POSLEDNI_RAZITKA[0] = None\n"),
    ('        for rz in razitka:\n            nodes.append({"name": f"n{len(nodes)}", "mesh": mesh_loga, "rotation": [round(float(v), 7) for v in rz["logo"]["q"]],\n'
     '                          "translation": [round(float(v), 4) for v in (np.array(rz["logo"]["pos"], float) + posun)]})\n',
     '        info_razitek = []\n'
     '        for k_, rz in enumerate(razitka):\n'
     '            info_razitek.append({"dil": rz.get("dil"), "uzel": len(nodes), "vypln": [uzel_materialu["alu"], int(vyplne_rozsahy[k_][0]), int(vyplne_rozsahy[k_][1])]})\n'
     '            nodes.append({"name": f"n{len(nodes)}", "mesh": mesh_loga, "rotation": [round(float(v), 7) for v in rz["logo"]["q"]],\n'
     '                          "translation": [round(float(v), 4) for v in (np.array(rz["logo"]["pos"], float) + posun)]})\n'
     '        _POSLEDNI_RAZITKA[0] = info_razitek\n'),
    ("        if h in _GLB_RAZITKA_CACHE and h in _META_CACHE and h in _ROZSAHY_CACHE and h in _EXTRA_CACHE:\n"
     "            for c_ in (_GLB_RAZITKA_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE):\n"
     "                c_.move_to_end(h)",
     "        if h in _GLB_RAZITKA_CACHE and h in _META_CACHE and h in _ROZSAHY_CACHE and h in _EXTRA_CACHE and h in _RAZITKA_CACHE:\n"
     "            for c_ in (_GLB_RAZITKA_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE, _RAZITKA_CACHE):\n"
     "                c_.move_to_end(h)"),
    ("        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}\n"
     "        for c_ in (_GLB_RAZITKA_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE):\n"
     "            while len(c_) > CACHE_MAX:",
     "        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}\n"
     "        _RAZITKA_CACHE[h] = _POSLEDNI_RAZITKA[0] or []\n"
     "        for c_ in (_GLB_RAZITKA_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE, _RAZITKA_CACHE):\n"
     "            while len(c_) > CACHE_MAX:"),
    ('                out["ovladani"]["zive_rozsahy_extra"] = {str(k_): v_ for k_, v_ in ex_.items()}      # dil rozdeleny do vice uzlu (spodni suplik boxu): dalsi rozsahy, hybou se spolu s dilem\n',
     '                out["ovladani"]["zive_rozsahy_extra"] = {str(k_): v_ for k_, v_ in ex_.items()}      # dil rozdeleny do vice uzlu (spodni suplik boxu): dalsi rozsahy, hybou se spolu s dilem\n'
     '            rz_ = _RAZITKA_CACHE.get(h) if RAZITKA_VYCHOZI else None\n'
     '            if rz_:\n'
     '                out["ovladani"]["razitka"] = rz_            # razitka (logo + vypln drazky) a dil, na kterem sedi: prohlizec je pri zivem tazeni hybe s dilem (docs/OVLADANI_3D.md; Robert 2026-10-08); jen kdyz je vychozi model S razitky\n'),
])

uprav("api/stul_ovladani_verejne.py", [
    ('                                                                       # tazeni sirky / posunu boxu jelo jen telo skrine a suplik zustal na miste (odtrhl se od boxu; Robert 2026-10-06, od 8cd23e6c)\n    return out',
     '                                                                       # tazeni sirky / posunu boxu jelo jen telo skrine a suplik zustal na miste (odtrhl se od boxu; Robert 2026-10-06, od 8cd23e6c)\n'
     '        if ov.get("razitka"):\n'
     '            out["razitka"] = ov["razitka"]                             # razitka (logo + vypln drazky) a dil, na kterem sedi: pri zivem tazeni se hybou s dilem (WORKFLOW pravidlo 61; Robert 2026-10-08)\n'
     '    return out'),
])
