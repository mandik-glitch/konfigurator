#!/usr/bin/env python3
"""Test ZIVEHO tazeni ROZMERU desky - vyska, sirka, hloubka (bot8, 2026-10-04, Robert: "smerem nahoru zustava mezera, nenatahuje se to plynule"): u tahu `vyska` musi operace `zive` (posun / natahni)
dat PRESNE totez, co model poskladany serverem pro novou vysku - KAZDY dil, ne jen vetsina (puvodni test_stul_zive.py hlida u rozmeru jen "nahled" a chybu, kdy se dve predni nohy
posunuly celé misto natazeni, nechytil).
Plosne desky (laminodeska) se v modelu ze serveru meritkuji i uvnitr (zaobleni rohu), nahled hybe jen okraje -> u nich se porovnava obalka.
Stejny princip jako test_stul_zive.py: operace se aplikuji na GLB puvodniho stavu (stejna pravidla jako v prohlizeci) a porovnavaji s GLB pro novou vysku (<= 0.05 mm).
Sirka a hloubka se zkousi do kroku sondy (+-100 mm): sonda je linearni v rozsahu kroku, dal je to nahled (u nekterych stolu se pravidla lamou po ~300 mm - napr. patky misto koleček - a model
ze serveru po pusteni to opravi).
Kde zmena rozmeru meni SADU dilu (prah, kde pribyvaji nohy / podpery), porovnat po dilech nejde - tam se kombinace preskoci (rozhodne server po pusteni).
Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_zive_vyska.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import test_stul_zive as Z  # noqa: E402

VARIANTY = (
    dict(),                                                                    # vychozi (kolecka, police, panely, LED, suplik, elektrozlab)
    dict(vyska=990),
    dict(vyska=600, led=False),
    dict(kolecka=False),                                                       # stavitelne patky misto koleček
    dict(police=0, suplik=False),
    dict(sirka=2000, stredni_noha=900.0),                                      # stredni noha
    dict(sirka=2400, hloubka=1000, vyrez1=True, loz=True),                     # siroky, hluboky, vyrez, loziska (podpery police)
    dict(sirka=1840, vzpery=True, panely=False, elektrozlab=False),            # vzpery ramen LED
    dict(police=2, hloubka=600),
    dict(vyska=1150),                                                          # u horni meze se sonda dela smerem dolu
)
ZMENY = (+100.0, -100.0, +260.0, -60.0)


def main():
    pocet = 0
    for tid, par, z in [("vyska", par, z) for par in VARIANTY for z in ZMENY] + [(t, par, z) for t in ("sirka", "hloubka") for par in VARIANTY[:8] for z in (+100.0, -100.0, +50.0)]:
        if True:
            r0 = Z.S.odpoved(par)
            v0 = r0["parametry"][tid]
            if not (Z.S.ROZSAH[tid][0] <= v0 + z <= Z.S.ROZSAH[tid][1]):
                continue
            j = f"{tid} {par} {z:+.0f} mm"
            r1_ = Z.S.sestav_stul(**{**r0["parametry"], tid: v0 + z})
            if len(r1_["dily"]) != len(r0["dily"]):
                continue                                               # zmena rozmeru meni SADU dilu (prah) - po dilech porovnat nejde
            ax_ = {"sirka": 2, "hloubka": 0, "vyska": 1}[tid]

            def urcuji(rr_):
                """Klice dilu, ktere urcuji obalku modelu v ose zmeny (GLB se vycentruje podle obalky; pres prah, kde obalku zacne urcovat jiny dil - napr. LED presahuje uzky stul - neni vycentrovani linearni)."""
                bbs_ = [Z.S._aabb(d) for d in rr_["dily"]]
                lo_ = min(float(b[0][ax_]) for b in bbs_)
                hi_ = max(float(b[1][ax_]) for b in bbs_)
                return (frozenset(tuple(rr_["klice"][i]) if isinstance(rr_["klice"][i], list) else rr_["klice"][i] for i, b in enumerate(bbs_) if abs(float(b[0][ax_]) - lo_) < 0.01),
                        frozenset(tuple(rr_["klice"][i]) if isinstance(rr_["klice"][i], list) else rr_["klice"][i] for i, b in enumerate(bbs_) if abs(float(b[1][ax_]) - hi_) < 0.01))
            if tid != "vyska" and urcuji(r1_) != urcuji(Z.S.sestav_stul(**r0["parametry"])):
                continue                                               # obalku zacal urcovat jiny dil (prah) - vycentrovani GLB neni linearni
            res = Z.porovnej(par, tid, z, 0.05, j)
            if not res:
                continue
            chyby, pred, poz1, shift, roz, r0 = res
            pocet += 1
            # Plosne desky (laminodeska) se v modelu ze serveru meritkuji CELE (i vnitrni vrcholy, napr. zaobleni rohu), nahled hybe jen okraje -> u nich se porovnava obalka (okraje) dilu
            for n, (c, i) in enumerate(chyby):
                if r0["dily"][i]["part_id"] == "product_4933":
                    r = roz[i]
                    a, b = pred[r[0]][r[1]:r[1] + r[2]] + shift, poz1[r[0]][r[1]:r[1] + r[2]]
                    chyby[n] = (float(max(np.abs(a.min(axis=0) - b.min(axis=0)).max(), np.abs(a.max(axis=0) - b.max(axis=0)).max())), i)
            hrube = sorted(((c, i) for c, i in chyby if c > 0.05), reverse=True)
            Z.check(not hrube, f"{j}: KAZDY dil sedi s modelem ze serveru (<= 0.05 mm); spatne: " + ", ".join(f"dil {i} ({r0['dily'][i]['part_id']}, {c:.1f} mm)" for c, i in hrube[:5]))
    print(f"{Z.OK} kontrol OK ({pocet} kombinaci)")
    sys.exit(1 if Z.FAILS else 0)


if __name__ == "__main__":
    main()
