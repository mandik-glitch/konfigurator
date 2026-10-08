#!/usr/bin/env python3
"""Razitka na vsech 3D modelech generatoru (pravidlo 61, bot8 2026-10-08) - regrese VEREJNEHO resolve: odpoved (cena, kusovnik, hash, platnost, options, vodici = uchyty ve 3D, payload luxu, odkaz na model)
se zapnutim razitek NESMI zmenit ani bit (razitka jsou jen v GLB; GLB se pocita pri resolve kvuli vodicim znackam, takze se overuje, ze vodici znacky vznikly ze stejnych vedlejsich cache).

  regrese_resolve.py zaklad   [vystup.json]   nad API PRED zmenou
  regrese_resolve.py porovnej [zaklad.json]   nad API PO zmene (STUL_API_OVERRIDE = kandidat)
DB se jen CTE (ceny karet): spusteni pres systemd-run s prostredim z api/.env:
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/regrese_resolve.py zaklad|porovnej"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2026-10-08_led_rucne"))
import _spolecne as C  # noqa: E402

ZAKLAD = os.path.join(HERE, "zaklad_resolve_pred_zmenou.json")
TED = 1_800_000_000.0                                       # pevny cas podpisu odkazu na model (jinak by se token menil)
VYBERY = [
    {}, {"w": 1100}, {"w": 2000, "d": 900}, {"w": 2800, "d": 1000, "shelf": 2}, {"led": False}, {"w": 3000, "ledcount": 2}, {"w": 3000, "ledlen": "600", "ledcount": 3}, {"posts": False},
    {"upshelf": True}, {"upshelf": True, "w": 2200}, {"drawers": True}, {"panels": True, "panelcount": 2}, {"wheels": True}, {"cut1": True}, {"braces": True}, {"w": 2400, "midsupport": "frame"},
    {"shelf": 3, "shelfboard": False}, {"w": 1800, "led": True, "ledlight": False},
]


def sha(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()[:24]


def vsechny(SH):
    out = {}
    for sy in (30, 35, 40, 41, 45):
        for i, sel in enumerate(VYBERY):
            klic = "%d|%s" % (sy, json.dumps(sel, sort_keys=True))
            try:
                r = SH.resolve(dict(sel), "cs", ted=TED, system=sy)
                ((r.get("vodici") or {}).get("ovladani") or {}).pop("razitka", None)          # od razitka-tazeni (2026-10-08) nese vodici.ovladani pole `razitka` = ocekavany prirustek, jinak beze zmeny
                out[klic] = {"sha": sha(r), "hash": r.get("hash"), "valid": r.get("valid"), "vodici": sha(r.get("vodici")), "klice": sorted(r.keys())}
            except Exception as e:                           # neplatna kombinace u nektereho systemu: ulozi se typ chyby (musi byt stejny po zmene)
                out[klic] = {"chyba": type(e).__name__ + ": " + str(e)[:80]}
    return out


def main():
    rezim = sys.argv[1] if len(sys.argv) > 1 else ""
    soubor = sys.argv[2] if len(sys.argv) > 2 else ZAKLAD
    S, G = C.nacti_generator(hermeticky=False)
    import stul_shop as SH
    print('stul_glb:', G.__file__, '| RAZITKA_VYCHOZI =', getattr(G, 'RAZITKA_VYCHOZI', '(neni - stary kod)'))
    t0 = time.time()
    nyni = vsechny(SH)
    if rezim == "zaklad":
        json.dump(nyni, open(soubor, "w", encoding="utf-8"), indent=0, sort_keys=True)
        print("zapsano %d odpovedi resolve do %s (%.0f s)" % (len(nyni), soubor, time.time() - t0))
        return 0
    if rezim == "porovnej":
        zak = json.load(open(soubor, encoding="utf-8"))
        chyby = [(k, zak.get(k), nyni.get(k)) for k in sorted(set(zak) | set(nyni)) if zak.get(k) != nyni.get(k)]
        print("porovnano %d odpovedi resolve, %d rozdilu (%.0f s)" % (len(nyni), len(chyby), time.time() - t0))
        for c in chyby[:15]:
            print("  ROZDIL", c)
        return 1 if chyby else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
