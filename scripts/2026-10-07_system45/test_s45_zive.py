#!/usr/bin/env python3
"""ZIVE TAZENI rozmeru HLUBOKEHO stolu systemu 45 (bot10, 2026-10-07): u tahu vyska / sirka / hloubka musi operace `zive` (posun / natahni) dat PRESNE totez, co model poskladany serverem pro novy
rozmer - KAZDY dil (<= 0.05 mm), vcetne novych dilu hluboke konstrukce (stredni nohy, pricky pres sirku, kolecka / patky strednich noh). Stejny princip a pomocne funkce jako
scripts/2026-10-02_stul_testy/test_stul_zive_vyska.py, ale nad systemem 45 a hloubkami nad 1500 mm (tam puvodni test nesahá: meze bere z S.ROZSAH).
Spusteni: api/venv/bin/python3 -B scripts/2026-10-07_system45/test_s45_zive.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "scripts", "2026-10-02_stul_testy"))
sys.dont_write_bytecode = True
import numpy as np  # noqa: E402
import test_stul_zive as Z  # noqa: E402

VARIANTY = (
    dict(system=45, hloubka=1800.0, sirka=1800.0),                                   # vychozi hluboky stul (kolecka, police, panely, LED, suplik)
    dict(system=45, hloubka=2200.0, sirka=1500.0, police=2),                         # dve police
    dict(system=45, hloubka=2000.0, sirka=2400.0, kolecka=False, patky=True),        # patky, siroky (stredni noha podle sirky)
    dict(system=45, hloubka=2500.0, sirka=3000.0),                                   # nejvetsi stul
    dict(system=45, hloubka=1700.0, vyska=600.0, led=False),
    dict(system=45, hloubka=1900.0, police=0, suplik=False),
    dict(system=45, hloubka=2100.0, kolecka=False, patky=False),                     # zaslepky na koncich noh
    dict(system=45, hloubka=1600.0, sirka=1840.0, vzpery=True, panely=False, elektrozlab=False),
)
ZMENY_VYSKA = (+100.0, -100.0, +260.0, -60.0)
ZMENY_ROZMER = (+100.0, -100.0, +50.0)


def urcuji(rr_, ax_):
    """Klice dilu, ktere urcuji obalku modelu v ose zmeny (GLB se vycentruje podle obalky; pres prah, kde obalku zacne urcovat jiny dil, neni vycentrovani linearni)."""
    bbs_ = [Z.S._aabb(d) for d in rr_["dily"]]
    lo_ = min(float(b[0][ax_]) for b in bbs_)
    hi_ = max(float(b[1][ax_]) for b in bbs_)
    kl = lambda i: tuple(rr_["klice"][i]) if isinstance(rr_["klice"][i], list) else rr_["klice"][i]  # noqa: E731
    return (frozenset(kl(i) for i, b in enumerate(bbs_) if abs(float(b[0][ax_]) - lo_) < 0.01), frozenset(kl(i) for i, b in enumerate(bbs_) if abs(float(b[1][ax_]) - hi_) < 0.01))


def main():
    pocet = preskoceno = 0
    zadani = [("vyska", par, z) for par in VARIANTY for z in ZMENY_VYSKA] + [(t, par, z) for t in ("sirka", "hloubka") for par in VARIANTY for z in ZMENY_ROZMER]
    for tid, par, z in zadani:
        r0 = Z.S.odpoved(par)
        v0 = r0["parametry"][tid]
        lo, hi = Z.S._rozsahy(45)[tid]
        if not (lo <= v0 + z <= hi):
            continue
        j = f"{tid} {par} {z:+.0f} mm"
        r1_ = Z.S.sestav_stul(**{**r0["parametry"], tid: v0 + z})
        if len(r1_["dily"]) != len(r0["dily"]):
            preskoceno += 1                                                  # zmena rozmeru meni SADU dilu (prah) - po dilech porovnat nejde
            continue
        ax_ = {"sirka": 2, "hloubka": 0, "vyska": 1}[tid]
        if tid != "vyska" and urcuji(r1_, ax_) != urcuji(Z.S.sestav_stul(**r0["parametry"]), ax_):
            preskoceno += 1
            continue
        res = Z.porovnej(par, tid, z, 0.05, j)
        if not res:
            continue
        chyby, pred, poz1, shift, roz, r0 = res
        pocet += 1
        for n, (c, i) in enumerate(chyby):                                   # plosne desky se v modelu ze serveru meritkuji i uvnitr: porovnava se obalka
            if r0["dily"][i]["part_id"] == "product_4933":
                r = roz[i]
                a, b = pred[r[0]][r[1]:r[1] + r[2]] + shift, poz1[r[0]][r[1]:r[1] + r[2]]
                chyby[n] = (float(max(np.abs(a.min(axis=0) - b.min(axis=0)).max(), np.abs(a.max(axis=0) - b.max(axis=0)).max())), i)
        hrube = sorted(((c, i) for c, i in chyby if c > 0.05), reverse=True)
        kl = [tuple(k) if isinstance(k, list) else k for k in Z.S.sestav_stul(**r0["parametry"])["klice"]]          # odpoved() klice odebira
        Z.check(not hrube, f"{j}: KAZDY dil sedi s modelem ze serveru (<= 0.05 mm); spatne: " + ", ".join(f"dil {i} {kl[i]} ({r0['dily'][i]['part_id']}, {c:.1f} mm)" for c, i in hrube[:6]))
    Z.check(pocet >= 40, f"zkouseno dost kombinaci ({pocet}; preskoceno {preskoceno})")
    print(f"{Z.OK} kontrol OK ({pocet} kombinaci, preskoceno {preskoceno} - zmena meni sadu dilu)")
    sys.exit(1 if Z.FAILS else 0)


if __name__ == "__main__":
    main()
