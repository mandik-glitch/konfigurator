#!/usr/bin/env python3
"""Test BUILDU multiboxu a podnosu ocelovych supliku (scripts/v3d/vandr_offer_build.py, Blender na CPU): seznam mbx ve spec v3d postavenych Vandr karet (bot8, 2026-10-07).
Vstup: <OUT>/out/<karta>.json (geom.json z build_karty.py) a <OUT>/out2/<karta>.offer.glb; OUT = $V3D_TEST_OUT nebo <tmp>/v3d_testy. Nic nestavi, nic nezapisuje (karty se staví v run_all.sh).
Ocekavani jsou zmerena na skutecnych kartach 2026-10-07: 4921 = police (8 boxu) + 2 sufliky (7 + 7), 4917 = 2 police + 2 sufliky vc. boxu otocenych (e = -1), 4918 = police (6) + 2 sufliky, 4594 = bez multiboxu."""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.environ.get("PRICKY_API") or os.path.join(REPO, "api")
OUT = os.environ.get("V3D_TEST_OUT") or os.path.join(tempfile.gettempdir(), "v3d_testy")
sys.path.insert(0, API)
sys.dont_write_bytecode = True
import nabidka_pricky as P  # noqa: E402
import v3d_glb  # noqa: E402

bad = total = 0


def t(name, cond, detail=None):
    global bad, total
    total += 1
    bad += 0 if cond else 1
    print("[%s] %s%s" % ("OK   " if cond else "CHYBA", name, "" if cond or detail is None else " | %r" % (detail,)))


def geom(k):
    p = os.path.join(OUT, "out", k + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def offer_spec(k):
    p = os.path.join(OUT, "out2", k + ".offer.glb")
    return v3d_glb.embedded_spec(open(p, "rb").read()) if os.path.isfile(p) else None


def skupiny(mbx):
    d = {}
    for b in mbx:
        d.setdefault((b["s"], b["sk"]), []).append(b)
    return d


# karta -> (multiboxy: pocet, [(pocet boxu ve skupine, druh)], e=+1, e=-1, sirokych 186 | podnosy supliku: [pocet podnosu v instanci (skupine)], e=+1, e=-1, typy)
# Multiboxy zmereno na kartach 2026-10-07; PODNOSY NEZAVISLE z katalogovych GLB (instance komponent Suplikocel* / 2suplikyocel*, kazda instance = skupina; orientace e podle polohy celniho
# (modreho) panelu vedle podnosu: celo na MIN strane hloubky = e +1, na MAX = e -1; 4968 = obracena instalace, vsech 6 podnosu e = -1, dvojice 443 + 695 vedle sebe)
OCEK = {"4921": (22, [(8, 1), (7, 2), (7, 2)], 22, 0, 17, [1, 1, 1], 3, 0, {"S950x384x101": 3}),
        "4917": (28, [(6, 1), (8, 1), (7, 2), (7, 2)], 20, 8, 21, [1, 1, 1], 3, 0, {"S950x384x137": 3}),
        "4918": (20, [(6, 1), (7, 2), (7, 2)], 20, 0, 16, [1, 1, 1], 3, 0, {"S950x384x137": 3}),
        "4453": (7, [(7, 2)], 7, 0, 6, [1, 1, 1, 1], 4, 0, {"S950x384x101": 4}),
        "4474": (8, [(8, 1)], 8, 0, 5, [2, 2, 2, 2], 8, 0, {"S443x384x137": 8}),
        "4910": (8, [(8, 1)], 8, 0, 5, [1, 1, 1, 1], 4, 0, {"S443x384x137": 3, "S443x384x210": 1}),
        "4968": (0, [], 0, 0, 0, [2, 2, 2], 0, 6, {"S443x384x137": 2, "S695x384x137": 2, "S443x384x210": 1, "S695x384x210": 1})}
for k, (n, grp, e_plus, e_minus, sirokych, sgrp, s_plus, s_minus, styp) in OCEK.items():
    g = geom(k)
    if g is None:
        print("PRESKOCENO %s (chybi %s/out/%s.json - spust build_karty.py)" % (k, OUT, k))
        continue
    mbx_all = (g["v3d"] or {}).get("mbx") or []
    mbx = [b for b in mbx_all if b["sk"] != 4]
    sup = [b for b in mbx_all if b["sk"] == 4]
    nsup = sum(sgrp)
    t("%s: %d multiboxu + %d podnosu supliku ve spec buildu, stats.multiboxy souhlasi" % (k, n, nsup), len(mbx) == n and len(sup) == nsup and g["stats"].get("multiboxy") == n + nsup, (len(mbx), len(sup), g["stats"].get("multiboxy")))
    sk = skupiny(mbx_all)
    t("%s: skupiny multiboxu (police / vysuvy) %s" % (k, grp), sorted((len(v), key[1]) for key, v in sk.items() if key[1] != 4) == sorted(grp), sorted((len(v), key[1]) for key, v in sk.items() if key[1] != 4))
    t("%s: skupiny podnosu supliku (druh 4, jedna instance = jedna skupina) %s" % (k, sgrp), sorted(len(v) for key, v in sk.items() if key[1] == 4) == sorted(sgrp), sorted(len(v) for key, v in sk.items() if key[1] == 4))
    t("%s: cisla skupin 1..%d souvisla" % (k, len(grp) + len(sgrp)), sorted({b["s"] for b in mbx_all}) == list(range(1, len(grp) + len(sgrp) + 1)))
    t("%s: konec s vykrojem multiboxu: e=+1 x %d, e=-1 x %d" % (k, e_plus, e_minus), sum(1 for b in mbx if b["e"] == 1) == e_plus and sum(1 for b in mbx if b["e"] == -1) == e_minus,
      (sum(1 for b in mbx if b["e"] == 1), sum(1 for b in mbx if b["e"] == -1)))
    t("%s: celo podnosu supliku (e): +1 x %d, -1 x %d (nezavisle podle celniho panelu v katalogu)" % (k, s_plus, s_minus), sum(1 for b in sup if b["e"] == 1) == s_plus and sum(1 for b in sup if b["e"] == -1) == s_minus,
      (sum(1 for b in sup if b["e"] == 1), sum(1 for b in sup if b["e"] == -1)))
    t("%s: vsechny boxy a podnosy jedou s pivotem" % k, all(b["p"] for b in mbx_all))
    t("%s: id b01..b%02d a n 1..%d bez mezer" % (k, n + nsup, n + nsup), [b["id"] for b in mbx_all] == ["b%02d" % i for i in range(1, n + nsup + 1)] and [b["n"] for b in mbx_all] == list(range(1, n + nsup + 1)))
    typy = [P.typ_boxu(b["min"], b["max"]) for b in mbx_all]
    t("%s: vsechny boxy a podnosy znameho typu, %d sirokych 186" % (k, sirokych), None not in typy and sum(1 for x in typy if x.endswith("x186")) == sirokych, typy)
    tt = {}
    for x in typy:
        if x and x.startswith("S"):
            tt[x] = tt.get(x, 0) + 1
    t("%s: typy podnosu supliku %s" % (k, styp), tt == styp, tt)
    t("%s: druh skupiny podle typu (podnos = 4, multibox nikdy 4)" % k, all((x is not None and x.startswith("S")) == (b["sk"] == 4) for x, b in zip(typy, mbx_all)))
    t("%s: razeni shora dolu (stred Y neroste)" % k, all((mbx_all[i]["min"][1] + mbx_all[i]["max"][1]) >= (mbx_all[i + 1]["min"][1] + mbx_all[i + 1]["max"][1]) - 10.5 for i in range(len(mbx_all) - 1)))
    box = g["v3d"]["box"]
    t("%s: boxy lezi v obalce modelu (+-1 mm)" % k, all(b["min"][a] >= box["min"][a] - 1.0 and b["max"][a] <= box["max"][a] + 1.0 for b in mbx_all for a in range(3)))
    vyp = [w for w in g["warnings"] if w.lower().startswith("multibox") or w.lower().startswith("suplik:") or w.lower().startswith("suplik ")]      # varovani z detekce boxu a podnosu (jina varovani o dvirkach atd. sem nepatri)
    t("%s: zadne varovani o multiboxech a podnosech supliku" % k, not vyp, vyp)
    sp = offer_spec(k)
    t("%s: zakaznicky GLB (po sanitize) nese stejny seznam boxu" % k, sp is not None and sp.get("mbx") == v3d_glb.validate_spec(g["v3d"])["mbx"])
    # kazdy box lezi ve sve skupine ve stejne rade: stejna osa delky (u podnosu delsi = sirka); skupina podnosu = jedna instance komponenty
    for (s_, druh), bs in sk.items():
        osy = {P.osa_delky(b["min"], b["max"]) for b in bs}
        t("%s: skupina %d - vsechny boxy maji stejnou osu delky" % (k, s_), len(osy) == 1, osy)
for k in ("4594",):
    g = geom(k)
    if g is None:
        print("PRESKOCENO %s (chybi geom)" % k)
        continue
    t("%s: karta bez multiboxu - spec nema klic mbx a stats.multiboxy = 0" % k, "mbx" not in g["v3d"] and g["stats"].get("multiboxy") == 0, (list(g["v3d"]), g["stats"].get("multiboxy")))
    sp = offer_spec(k)
    t("%s: zakaznicky GLB bez mbx" % k, sp is not None and "mbx" not in sp)
print("\n%d/%d OK" % (total - bad, total))
sys.exit(1 if bad else 0)
