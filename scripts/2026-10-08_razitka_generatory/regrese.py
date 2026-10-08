#!/usr/bin/env python3
"""Razitka na VSECH 3D modelech generatoru stolu (WORKFLOW pravidlo 61, Robert 2026-10-08) - REGRESE bit po bitu (bot8).

  regrese.py zaklad   [vystup.json]   nad API PRED zmenou (HEAD): pro mrizku konfiguraci (scripts/2026-10-08_led_rucne/_spolecne.mrizka, system 30 / 35 / 40 / 41 / 45) ulozi otisk
                                      GLB bez razitek, GLB s razitky (`razitka=True`), vedlejsich cache (posun, rozsahy, extra rozsahy = to, z ceho se pocitaji uchyty / ovladani / payload luxu)
  regrese.py porovnej [zaklad.json]   nad API PO zmene (STUL_API_OVERRIDE = kandidat): overi, ze
      1) `model_pro_parametry(p, razitka=False)` = TOTO jako drive bez razitek (bajt po bajtu),
      2) `model_pro_parametry(p)` (nove vychozi) = TOTO jako drive `razitka=True` (stejna razitka, stejne misto),
      3) vedlejsi cache po vychozim modelu (posun, rozsahy, extra) = presne drivejsi cache verejneho modelu -> uchyty ve 3D, payload luxu, zive tazeni se nezmenily,
      4) pocet razitek se nezmenil, hash konfigurace se nezmenil.
Hermeticky (falesne prostredi, DB zakazana), jako ostatni sady stolu.  Pouziti: api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/regrese.py zaklad|porovnej [soubor]"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2026-10-08_led_rucne"))
import _spolecne as C  # noqa: E402

ZAKLAD = os.path.join(HERE, "zaklad_pred_zmenou.json")


def sha(b):
    return hashlib.sha256(b).hexdigest()[:24]


def otisk_meta(G, h):
    """Otisk vedlejsich cache modelu: posun (generator -> GLB), rozsahy dilu, extra rozsahy (kuzel patky, suplik)."""
    def ploch(o):
        if hasattr(o, "tolist"):
            return [round(float(x), 5) for x in o.tolist()]
        if isinstance(o, dict):
            return {str(k): ploch(v) for k, v in sorted(o.items(), key=lambda kv: str(kv[0]))}
        if isinstance(o, (list, tuple)):
            return [ploch(x) for x in o]
        if isinstance(o, float):
            return round(o, 5)
        return o
    return sha(json.dumps([ploch(G._META_CACHE[h]), ploch(G._ROZSAHY_CACHE[h]), ploch(G._EXTRA_CACHE[h])], sort_keys=True).encode())


def konfigurace():
    return list(C.mrizka())


def zaklad(vystup):
    S, G = C.nacti_generator()
    import stul_razitka as RZ
    out = {}
    t0 = time.time()
    for p in konfigurace():
        r = S.sestav_stul(**p)
        par = r["parametry"]
        h = G.kanonicky_hash(par)
        plain = G.model_pro_parametry(par)[1]            # HEAD: bez razitek
        meta = otisk_meta(G, h)
        st = G.model_pro_parametry(par, razitka=True)[1]
        out[json.dumps(p, sort_keys=True)] = {"hash": h, "plain": sha(plain), "plain_B": len(plain), "stamp": sha(st), "stamp_B": len(st), "meta": meta, "razitek": len(RZ.razitka(r, h))}
    json.dump(out, open(vystup, "w", encoding="utf-8"), indent=0, sort_keys=True)
    print("zapsano %d konfiguraci do %s (%.0f s)" % (len(out), vystup, time.time() - t0))


def porovnej(vstup):
    S, G = C.nacti_generator()
    import stul_razitka as RZ
    print('stul_glb:', G.__file__, '| RAZITKA_VYCHOZI =', getattr(G, 'RAZITKA_VYCHOZI', '(neni - stary kod)'))
    zak = json.load(open(vstup, encoding="utf-8"))
    chyby, n, t0 = [], 0, time.time()
    for klic, z in zak.items():
        p = json.loads(klic)
        r = S.sestav_stul(**p)
        par = r["parametry"]
        h = G.kanonicky_hash(par)
        n += 1
        if h != z["hash"]:
            chyby.append((klic, "hash konfigurace se zmenil", h, z["hash"]))
            continue
        vych = G.model_pro_parametry(par)[1]                       # NOVE VYCHOZI
        if sha(vych) != z["stamp"]:
            chyby.append((klic, "vychozi model != drivejsi model s razitky", len(vych), z["stamp_B"]))
        if otisk_meta(G, h) != z["meta"]:
            chyby.append((klic, "vedlejsi cache po vychozim modelu != drivejsi cache verejneho modelu", None, None))
        bez = G.model_pro_parametry(par, razitka=False)[1]
        if sha(bez) != z["plain"]:
            chyby.append((klic, "model bez razitek (razitka=False) se zmenil", len(bez), z["plain_B"]))
        if otisk_meta(G, h) != z["meta"]:
            chyby.append((klic, "vedlejsi cache po modelu bez razitek se zmenily", None, None))
        if len(RZ.razitka(r, h)) != z["razitek"]:
            chyby.append((klic, "pocet razitek se zmenil", len(RZ.razitka(r, h)), z["razitek"]))
        kod_v, kod_b = G.zakoduj_pro_klienta(h, vych, "br")[0], G.zakoduj_pro_klienta(h, bez, "br")[0]
        if kod_v == kod_b:
            chyby.append((klic, "komprimovana cache vratila stejna data pro model s razitky i bez (kolize klice)", len(kod_v), len(kod_b)))
    print("porovnano %d konfiguraci, %d chyb (%.0f s)" % (n, len(chyby), time.time() - t0))
    for c in chyby[:25]:
        print("  CHYBA", c)
    return 1 if chyby else 0


if __name__ == "__main__":
    rezim = sys.argv[1] if len(sys.argv) > 1 else ""
    soubor = sys.argv[2] if len(sys.argv) > 2 else ZAKLAD
    if rezim == "zaklad":
        zaklad(soubor)
    elif rezim == "porovnej":
        sys.exit(porovnej(soubor))
    else:
        print(__doc__)
        sys.exit(2)
