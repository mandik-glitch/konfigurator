#!/usr/bin/env python3
"""Test UMISTENI DRZAKU PET (bot8, 2026-10-04; Robert: "drzak PET nech prepnutelny na jakoukoli jinou stranu profilu nebo jiny svisly profil").
NEZAVISLE na kodu generatoru (meri se z bboxu dilu): pro kazdou nohu (PL, PP, ZL, ZP, FM, RM) a kazdou stranu (vpravo +z, vlevo -z, vpredu -x, vzadu +x): drzak LICI k pozadovane strane
profilu nohy (mezera <= 1,5 mm, nepruniknuty), ma stejnou vysku a stejny pocet dilu jako vychozi, otoceni mu prohodi rozmery x/z, je vodorovne na noze vycentrovan stejne jako sablona
(boční odsazeni se otaci s nim), vychozi (PL, vpravo) = beze zmeny (50 dilu, hash); stredni noha, ktera neni = problem `pet_noha`; kolize se zvolenym umistenim se NABIDNE odebrat (nikdy
tichy zasah); meze vysky vzdy podle nohy, na ktere drzak visi.
Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_pet_umisteni.py"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))
import numpy as np  # noqa: E402
import stul_glb as G  # noqa: E402
import stul_konfigurator as S  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        if len(FAILS) <= 30:
            print(f"  CHYBA: {msg}")


def klic(k):
    return tuple(klic(x) for x in k) if isinstance(k, list) else k


def bb(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


KLIC_NOHY = {"PL": ("t", S.NOHA_PL), "PP": ("t", S.NOHA_PP), "ZL": ("t", S.NOHA_ZL), "ZP": ("t", S.NOHA_ZP), "FM": "FM", "RM": "RM"}
STRANA_OSA = {"vpravo": (2, +1), "vlevo": (2, -1), "vpredu": (0, -1), "vzadu": (0, +1)}          # (osa, smer od osy nohy k pozadovane plose)

NP = dict(stredni_opora="noha", panely=False, elektrozlab=False)          # stredni NOHY (ne ram) a bez panelu (u 1800-2400 s nohami by se panel samo odebral = `odebrano`, test hlida, ze se NIC jineho neodebira potichu)
for kw in (dict(sirka=2000, **NP), dict(sirka=1800, hloubka=1000, vyska=900, suplik=False, **NP), dict(sirka=2400, kolecka=False, patky=True, **NP)):
    r0 = S.sestav_stul(**kw)
    kl0 = [klic(k) for k in r0["klice"]]
    pet0 = next(bb(d) for d in r0["dily"] if d["part_id"] == "product_4928")
    ext0 = pet0[1] - pet0[0]
    nm0 = f"[{kw}]"
    check(r0["problemy"] == [], f"{nm0}: vychozi umisteni bez problemu")
    for noha, kn in KLIC_NOHY.items():
        leg = bb(r0["dily"][kl0.index(kn)])
        for strana, (osa, smer) in STRANA_OSA.items():
            r = S.sestav_stul(**kw, pet_noha=noha, pet_strana=strana)
            n = f"{nm0} {noha}/{strana}"
            petd = [d for d in r["dily"] if d["part_id"] == "product_4928"]
            if not petd:
                check(bool(r["odebrano"]), f"{n}: drzak chybi jen kdyz byl odebran ({r['odebrano']})")
                continue
            pet = bb(petd[0])
            ext = pet[1] - pet[0]
            # lici k pozadovane strane profilu
            mezera = (pet[0][osa] - leg[1][osa]) if smer > 0 else (leg[0][osa] - pet[1][osa])
            check(abs(mezera) <= 1.5, f"{n}: drzak lici ke strane profilu (mezera {mezera:.2f} mm)")
            check(abs(ext[1] - ext0[1]) < 0.05 and abs(pet[0][1] - pet0[0][1]) < 0.05, f"{n}: stejna vyska a poloha ve svisle ose ({pet[0][1]:.1f}..{pet[1][1]:.1f})")
            kolmo = 0 if osa == 2 else 2                                                   # osa podel plochy profilu
            sirka_dil = ext[osa]
            stejne = (abs(ext[0] - ext0[0]) < 0.05 and abs(ext[2] - ext0[2]) < 0.05) if strana in ("vpravo", "vlevo") else (abs(ext[0] - ext0[2]) < 0.05 and abs(ext[2] - ext0[0]) < 0.05)
            check(stejne, f"{n}: rozmery v X/Z {ext[0]:.1f} x {ext[2]:.1f} (sablona {ext0[0]:.1f} x {ext0[2]:.1f})")
            # vycentrovani podel plochy profilu: odchylka stredu drzaku od osy nohy je stejna (velikosti) jako u sablony
            leg0 = bb(r0["dily"][kl0.index(KLIC_NOHY["PL"])])
            odch0 = abs((pet0[0][0] + pet0[1][0]) / 2.0 - (leg0[0][0] + leg0[1][0]) / 2.0)           # sablona: odsazeni v X
            odch = abs((pet[0][kolmo] + pet[1][kolmo]) / 2.0 - (leg[0][kolmo] + leg[1][kolmo]) / 2.0)
            check(abs(odch - odch0) < 0.1, f"{n}: odsazeni od osy nohy podel plochy {odch:.2f} mm (sablona {odch0:.2f} mm)")
            # problemy: bez problemu nebo (kolize se zvolenym umistenim) NABIDKA odebrani, ne tiche odebrani
            if r["problemy"]:
                check(bool(r["nabidky_odebrani"]) and not r["odebrano"], f"{n}: kolize -> nabidka odebrani, ne tiche odebrani ({[x['kod'] for x in r['problemy']]})")
            # meze vysky z nohy, na ktere drzak visi: cely drzak zustane na noze
            pm = r["pet_meze"]
            if pm and pm["vejde"]:
                for v in (pm["min"], pm["max"]):
                    r1 = S.sestav_stul(**kw, pet_noha=noha, pet_strana=strana, pet_posun=v)
                    p1 = bb(next(d for d in r1["dily"] if d["part_id"] == "product_4928"))
                    check(p1[0][1] >= leg[0][1] - 0.05 and p1[1][1] <= leg[1][1] + 0.05, f"{n}: posun {v:+.0f} (mez) drzak zustava na noze (y {p1[0][1]:.0f}..{p1[1][1]:.0f}, noha {leg[0][1]:.0f}..{leg[1][1]:.0f})")

# stredni noha, ktera neni
for noha in ("FM", "RM"):
    r = S.sestav_stul(pet_noha=noha)
    check(any(x["kod"] == "pet_noha" for x in r["problemy"]), f"{noha} u uzkeho stolu: problem pet_noha")
# vychozi beze zmeny
check(sum(1 for k in S.sestav_stul()["klice"] if k[0] != "zasl") == 50 and G.kanonicky_hash({"pet_noha": "PL", "pet_strana": "vpravo"}) == G.kanonicky_hash({}), "vychozi (PL, vpravo): 50 dilu, hash beze zmeny")
check(G.kanonicky_hash({"pet_noha": "PP"}) != G.kanonicky_hash({}) and G.kanonicky_hash({"pet_strana": "vzadu"}) != G.kanonicky_hash({}), "jina noha / strana meni hash")
check(G.kanonicky_hash({"drzak_pet": False, "pet_noha": "ZL"}) == G.kanonicky_hash({"drzak_pet": False}), "bez drzaku se umisteni do hashe nepocita")
for spatne in ({"pet_noha": "XX"}, {"pet_strana": "nahore"}):
    try:
        S.sestav_stul(**spatne)
        check(False, f"{spatne}: musi byt chyba")
    except S.StulChyba:
        check(True, "")
print(f"\n{OK} kontrol OK" if not FAILS else f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
sys.exit(1 if FAILS else 0)
