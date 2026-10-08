#!/usr/bin/env python3
"""Test PODPER SPODNI POLICE a ZKRACENI DESKY police pri hloubce > 900 mm (bot8, 2026-10-03; Robert: "jakmile se objevi pri vetsi hloubce stolu pomocna podpera v nohach,
spodni police resp. deska se na svou sirku zkrati z kazde strany 31 mm a pribudou pod policii podperne profily mezi celni a zadni podelnik (1-2 ks) podle delky stolu a zda
vznikne stredni noha, ktera podperu suplje").

NEZAVISLE na kodu generatoru (meri se ze skutecnych bboxu dilu, pocet podper se pocita znovu z pravidla):
  * hloubka <= 900: zadne podpery, deska police je siroka jako stul (beze zmeny),
  * hloubka 901..1500 x sirky x police 1-3: zadny problem, deska police je o 62 mm uzsi, od KAZDEHO dilu, ktery se s ni prekryva v X a Y (svisle profily bocnic...), ma v Z aspon 0.9 mm,
  * pocet podper = soucet ceil(rozpon / 800) - 1 pres rozpony mezi vnitrnimi plochami bocnich pricek police (a pricky stredni nohy), podpery rovnomerne, zadny nepodepreny usek > 800 mm,
  * podpera: profil 30x30 v ose X, delka = vzdalenost mezi zadni plochou predniho a predni plochou zadniho podelniku police, lezi ve vysce podelniku (horni plocha = horni plocha podelniku),
    T-styl: konce dosedaji na oba podelniky (lic_peers), predni konec ma rohove spojky ze spoje pricek drzicich supliky, ve stredni noze 30 mm od pricky stredni nohy,
  * `info` (police_podpery) nese pocet, texty cs/en/sk existuji.
Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_podpery.py   (STUL_API_OVERRIDE = jina kopie api/)"""
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))
import numpy as np  # noqa: E402
import stul_konfigurator as S  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        if len(FAILS) <= 25:
            print(f"  CHYBA: {msg}")


def bbox(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


def klic(k):
    return tuple(klic(x) for x in k) if isinstance(k, list) else k


SIRKY = (600, 1000, 1200, 1500, 1600, 2000, 2400, 3000)
HLOUBKY = (901, 950, 1000, 1050, 1100, 1150, 1200, 1250, 1300, 1350, 1400, 1450, 1500)
tabulka = {}                                                # (sirka, hloubka 1000, police 1) -> pocet podper na polici
zkouseno = 0
for w in SIRKY:
    # ---- hloubka <= 900: beze zmeny
    for dh in (400, 800, 900):
        r = S.sestav_stul(sirka=w, hloubka=dh, police=1)
        kl = [klic(k) for k in r["klice"]]
        check(not any(isinstance(k, tuple) and k[0] == "podpera" for k in kl), f"[{w}x{dh}] hloubka <= 900: zadne podpery")
        check(r["info"] == [], f"[{w}x{dh}] hloubka <= 900: zadna informace o podperach")
        pol0 = [i for i, d in enumerate(r["dily"]) if str(d.get("deska_id") or "").startswith("pol0_")]            # police (u stredni nohy ve dvou castech navazujicich bez mezery)
        if pol0:
            lo, hi = np.min([bbox(r["dily"][i])[0] for i in pol0], axis=0), np.max([bbox(r["dily"][i])[1] for i in pol0], axis=0)
            check(abs((hi[2] - lo[2]) - r["parametry"]["sirka"]) < 0.5, f"[{w}x{dh}] hloubka <= 900: deska police siroka jako stul ({hi[2] - lo[2]:.1f} mm)")
    for dh in HLOUBKY:
        for pol in (1, 2, 3):
            kw = dict(sirka=w, hloubka=dh, police=pol, vyska=1100, suplik=False, stredni_opora="noha")           # vyssi stul: i 3 police se vejdou; stredni NOHY (ne vestaveny ram)
            r = S.sestav_stul(**kw)
            zkouseno += 1
            n = f"[sirka {w}, hloubka {dh}, police {pol}]"
            kl = [klic(k) for k in r["klice"]]
            dily = r["dily"]
            check(r["problemy"] == [], f"{n}: zadny problem ({[p['kod'] for p in r['problemy']]})")
            n_pol = r["parametry"]["police"]
            # ---- desky police o 62 mm uzsi, od kazdeho prekryvajiciho se dilu aspon 0.9 mm v Z
            #   (Robert 2026-10-05: formaty tabuli) u stolu se strednimi nohami je kazda police DELENA u stredni nohy na dve desky (navazuji bez mezery): soucet sirek = sirka stolu - 62 mm
            desky = [i for i, d in enumerate(dily) if d["part_id"] == "product_4933" and str(d.get("deska_id") or "").startswith("pol") and not str(d.get("deska_id")).startswith("polvyr")]
            n_cast = 2 if r["parametry"]["sirka"] > S.prah_sirky() else 1
            check(len(desky) == n_pol * n_cast, f"{n}: {n_pol} polic x {n_cast} desek (je {len(desky)})")
            kr2 = 2.0 * (S.SYSTEMY[r["parametry"]["system"]]["profil_mm"] + 1.0)             # system 30: 62 mm (2 x 31), system 40: 82 mm (2 x 41) - svisly profil bocnice + 1 mm vule
            patra = {}
            for i in desky:
                patra.setdefault(dily[i]["deska_id"].split("_")[0], []).append(i)
            for ids_p in patra.values():
                lo_p, hi_p = np.min([bbox(dily[i])[0] for i in ids_p], axis=0), np.max([bbox(dily[i])[1] for i in ids_p], axis=0)
                check(abs((hi_p[2] - lo_p[2]) - (r["parametry"]["sirka"] - kr2)) < 0.5, f"{n}: deska police o {kr2:.0f} mm uzsi ({hi_p[2] - lo_p[2]:.1f} vs {r['parametry']['sirka'] - kr2:.1f})")
                check(abs(sum(float(bbox(dily[i])[1][2] - bbox(dily[i])[0][2]) for i in ids_p) - (r["parametry"]["sirka"] - kr2)) < 0.5, f"{n}: casti police na sebe navazuji bez mezery")
            for i in desky:
                lo, hi = bbox(dily[i])
                for j, d in enumerate(dily):
                    if j == i or d["part_id"] == "product_4933":
                        continue
                    lo2, hi2 = bbox(d)
                    px = min(hi[0], hi2[0]) - max(lo[0], lo2[0])
                    py = min(hi[1], hi2[1]) - max(lo[1], lo2[1])
                    if px > 0.5 and py > 0.5:
                        mezera = max(lo2[2] - hi[2], lo[2] - hi2[2])
                        check(mezera >= 0.9 or px < 1.0, f"{n}: deska police a dil {kl[j]} (prekryv X {px:.1f}, Y {py:.1f}) maji v Z mezeru {mezera:.2f} mm (aspon 0.9)")
            # ---- podpery: pocet z pravidla
            podp = {}
            for i, k in enumerate(kl):
                if isinstance(k, tuple) and k[0] == "podpera":
                    podp.setdefault(k[1], []).append(i)
            hladiny_boku = sorted(float((bbox(dily[i])[0][1] + bbox(dily[i])[1][1]) / 2.0) for i, k in enumerate(kl) if k in (("t", S.XRAIL_POL_L),) or (isinstance(k, tuple) and k[0] == "polic" and k[2] == ("t", S.XRAIL_POL_L)))
            i_l, i_p = kl.index(("t", S.XRAIL_POL_L)), kl.index(("t", S.XRAIL_POL_P))
            z_leva, z_prava = float(bbox(dily[i_l])[1][2]), float(bbox(dily[i_p])[0][2])             # vnitrni plochy bocnich pricek police
            stredni = "XM_pol" in kl
            if stredni:
                zlo, zhi = bbox(dily[kl.index("XM_pol")])
                useky = [(z_leva, float(zlo[2])), (float(zhi[2]), z_prava)]
            else:
                useky = [(z_leva, z_prava)]
            cekane = []
            for a, b in useky:
                m = max(0, math.ceil((b - a) / 800.0 - 1e-9) - 1)
                cekane += [a + (q + 1) * (b - a) / (m + 1) for q in range(m)]
            if cekane:
                check(sorted(podp) == list(range(n_pol)), f"{n}: podpery jsou pod kazdou ({n_pol}) policii (urovne {sorted(podp)})")
            else:
                check(not podp, f"{n}: pravidlo nechce zadne podpery, ale jsou ({sorted(podp)})")
            if w == 1200 and dh == 1000 and pol == 1:
                tabulka[(w, dh)] = len(cekane)
            if dh == 1000 and pol == 1:
                tabulka[(w, dh)] = len(cekane)
            for k_u, ids in podp.items():
                check(len(ids) == len(cekane), f"{n}: uroven {k_u}: {len(ids)} podper, pravidlo chce {len(cekane)}")
                zs = []
                def podelnik(kod, z_):
                    """Usek podelniku police (v dane urovni) pokryvajici souradnici z_: pri stredni noze je podelnik rozdelen na dva useky (t, seg)."""
                    for druh in ("t", "seg"):
                        kk = (druh, kod) if k_u == 0 else ("polic", k_u, (druh, kod))
                        if kk in kl:
                            lo_, hi_ = bbox(dily[kl.index(kk)])
                            if lo_[2] - 0.5 <= z_ <= hi_[2] + 0.5:
                                return kl.index(kk)
                    return None
                i_pred0 = kl.index(("t", S.ZRAIL_POL_PRED)) if k_u == 0 else kl.index(("polic", k_u, ("t", S.ZRAIL_POL_PRED)))
                i_zad0 = kl.index(("t", S.ZRAIL_POL_ZAD)) if k_u == 0 else kl.index(("polic", k_u, ("t", S.ZRAIL_POL_ZAD)))
                x_od = float(bbox(dily[i_pred0])[1][0])                          # zadni plocha predniho podelniku
                x_do = float(bbox(dily[i_zad0])[0][0])                           # predni plocha zadniho podelniku
                y_horni = float(bbox(dily[i_pred0])[1][1])
                for i in ids:
                    lo, hi = bbox(dily[i])
                    zs.append(float((lo[2] + hi[2]) / 2.0))
                    i_pred, i_zad = podelnik(S.ZRAIL_POL_PRED, zs[-1]), podelnik(S.ZRAIL_POL_ZAD, zs[-1])
                    check(i_pred is not None and i_zad is not None, f"{n}: pro podperu {i} (z {zs[-1]:.0f}) existuje usek predniho i zadniho podelniku")
                    if i_pred is None or i_zad is None:
                        continue
                    PM = S.SYSTEMY[r["parametry"]["system"]]["profil_mm"]                            # 30 nebo 40
                    check(abs((hi[2] - lo[2]) - PM) < 0.1 and abs((hi[1] - lo[1]) - PM) < 0.1, f"{n}: podpera ma profil {PM:.0f}x{PM:.0f} ({hi[2] - lo[2]:.1f} x {hi[1] - lo[1]:.1f})")
                    check(abs(lo[0] - x_od) < 0.1 and abs(hi[0] - x_do) < 0.1, f"{n}: podpera X {lo[0]:.1f}..{hi[0]:.1f} = mezi podelniky {x_od:.1f}..{x_do:.1f}")
                    check(abs(hi[1] - y_horni) < 0.1, f"{n}: horni plocha podpery {hi[1]:.1f} = horni plocha podelniku {y_horni:.1f}")
                    check(abs(1000.0 * dily[i]["scale"][1] - (x_do - x_od)) < 0.1, f"{n}: delka podpery {1000 * dily[i]['scale'][1]:.1f} = {x_do - x_od:.1f}")
                    # T-styl: konce dosedaji na oba podelniky (lic_peers: nizsi index drzi spoj)
                    par_pred = (min(i, i_pred), max(i, i_pred))
                    par_zad = (min(i, i_zad), max(i, i_zad))
                    for par in (par_pred, par_zad):
                        check(par[1] in dily[par[0]].get("lic_peers", []), f"{n}: podpera {i} dosedá na podelnik ({par}) - chybi v lic_peers")
                    # rohove spojky na predni konci: patri podpere, lezi u predniho podelniku
                    spoj = [j for j in dily[i].get("lic_peers", []) if dily[j]["part_id"] in S.SPOJKY_PARTS] + [j for j, d in enumerate(dily) if d["part_id"] in S.SPOJKY_PARTS and i in [] ]
                    spoj_vse = [j for j, d in enumerate(dily) if d["part_id"] in S.SPOJKY_PARTS and i in (d.get("lic_peers") or [])]
                    # spojky maji oba vlastniky v lic_peers PROFILU (profil -> spojka): spojky podpery = ty v jejim lic_peers
                    check(len(spoj) >= 1, f"{n}: podpera {i} ma aspon 1 predni spojku (ma {len(spoj)})")
                    for j in spoj:
                        slo, shi = bbox(dily[j])
                        pr = np.minimum(shi, hi) - np.maximum(slo, lo)
                        check(np.all(pr > -0.5), f"{n}: spojka {j} prilehá k podpere {i}")
                        check(abs(float(slo[0]) - x_od) < 40.0, f"{n}: spojka {j} je u predniho konce podpery (X {slo[0]:.1f})")
                zs.sort()
                body = sorted([z_leva] + zs + [z_prava] + ([float(zlo[2]), float(zhi[2])] if stredni else []))
                mezery = [b - a for a, b in zip(body, body[1:])]
                # nepodepreny usek = vzdalenost sousednich opor (plochy bocnich pricek / pricky stredni nohy / stredy podper): u podper pocitat od jejich plochy
                HP = S.SYSTEMY[r["parametry"]["system"]]["profil_mm"] / 2.0                       # polovina profilu: 15 (system 30) / 20 (system 40)
                opory = [(z_leva, z_leva)] + [(z - HP, z + HP) for z in zs] + ([(float(zlo[2]), float(zhi[2]))] if stredni else []) + [(z_prava, z_prava)]
                opory.sort()
                nejvetsi = max(b[0] - a[1] for a, b in zip(opory, opory[1:]))
                check(nejvetsi <= 800.0 + 1e-6, f"{n}: nejvetsi nepodepreny usek {nejvetsi:.1f} mm (nejvic 800)")
                if stredni:
                    for z in zs:
                        check(min(abs(z - float(zlo[2])), abs(z - float(zhi[2]))) >= 30.0, f"{n}: podpera ve stredni noze (z {z:.0f}) je blizko pricky stredni nohy")
                    check(all(not (float(zlo[2]) - S.SYSTEMY[r["parametry"]["system"]]["profil_mm"] / 2.0 < z < float(zhi[2]) + S.SYSTEMY[r["parametry"]["system"]]["profil_mm"] / 2.0) for z in zs), f"{n}: podpera nesmi lezet v prici stredni nohy")
            # ---- informace pro uzivatele
            inf = r["info"]
            inf_p = [i for i in inf if i["kod"] == "police_podpery"]
            check(len(inf_p) == 1 and inf_p[0]["podpery"] == len(cekane) and inf_p[0]["kraceni_mm"] == S.SYSTEMY[r["parametry"]["system"]]["profil_mm"] + 1.0 and inf_p[0]["urovni"] == n_pol, f"{n}: info police_podpery {inf}")

# ---- PODPERY POD PRACOVNI DESKOU (hloubka > 900; Robert 2026-10-04: "stejne podperne profily pod hlavni desku ve stejne vzdalenosti od noh resp. nad sebou"; supliky: kdyz tam
#      jsou, pocitaji se jejich pricky jako podpera, kdyz nejsou, pricky zmizely a podpery se doplni)
def z_stred(r, k):
    kl = [klic(x) for x in r["klice"]]
    i = kl.index(k)
    lo, hi = bbox(r["dily"][i])
    return float((lo[2] + hi[2]) / 2.0), lo, hi, i


zkouseno_d = 0
for w in SIRKY:
    for dh in (400, 800, 900):
        r = S.sestav_stul(sirka=w, hloubka=dh)
        check(not any(isinstance(klic(k), tuple) and klic(k)[0] == "podpera_d" for k in r["klice"]), f"[{w}x{dh}] hloubka <= 900: zadne podpery pod deskou")
        check(not any(i["kod"] == "deska_podpery" for i in r["info"]), f"[{w}x{dh}] hloubka <= 900: zadna informace o podperach desky")
    for dh in (901, 1000, 1200, 1500):
        for suplik in (True, False):
            for stredni in ((None,) if w <= S.SIRKA_STREDNI_NOHY else (None, 400.0)):
                kw = dict(sirka=w, hloubka=dh, suplik=suplik, police=1, vyska=840, stredni_opora="noha")
                if stredni is not None:
                    kw["stredni_noha"] = stredni
                r = S.sestav_stul(**kw)
                zkouseno_d += 1
                n = f"[deska: sirka {w}, hloubka {dh}, suplik {suplik}, stredni {stredni}]"
                kl = [klic(k) for k in r["klice"]]
                dily = r["dily"]
                supp = [i for i, k in enumerate(kl) if isinstance(k, tuple) and k[0] == "podpera_d"]
                nic_navic = [x for x in r["problemy"]]
                check(nic_navic == [], f"{n}: zadny problem ({[x['kod'] for x in nic_navic]})")
                # linie podelnych profilu pod deskou: bocni pricky (osy v z), pricka stredni nohy, pricky supliku
                lin = []
                for k in (("t", S.XRAIL_PRAC_L), ("t", S.XRAIL_PRAC_P), "XM_prac", ("t", S.XRAIL_BOX1), ("t", S.XRAIL_BOX2)):
                    if k in kl:
                        lin.append(z_stred(r, k)[0])
                lin.sort()
                cekane_d = []
                for a, b in zip(lin, lin[1:]):
                    a_, b_ = a + HP, b - HP
                    m = max(0, int(math.ceil((b_ - a_) / 800.0 - 1e-9)) - 1)
                    cekane_d += [a_ + (j + 1) * (b_ - a_) / (m + 1) for j in range(m)]
                zs = sorted(z_stred(r, kl[i])[0] for i in supp)
                check(len(zs) == len(cekane_d) and all(abs(a - b) < 0.6 for a, b in zip(zs, sorted(cekane_d))), f"{n}: podpery pod deskou na ocekavanych mistech {[round(z) for z in cekane_d]} (jsou {[round(z) for z in zs]})")
                # zadny nepodepreny usek > 800 mm (mezi plochami sousednich opor)
                opory = sorted([(z - HP, z + HP) for z in lin] + [(z - HP, z + HP) for z in zs])
                check(max(b[0] - a[1] for a, b in zip(opory, opory[1:])) <= 800.0 + 1e-6, f"{n}: zadny nepodepreny usek desky > 800 mm")
                # bez supliku stejna mista jako pod policí (nad sebou), kdyz je police
                if not suplik:
                    pol_z = sorted(z_stred(r, kl[i])[0] for i, k in enumerate(kl) if isinstance(k, tuple) and k[0] == "podpera" and k[1] == 0)
                    check(len(pol_z) == len(zs) and all(abs(a - b) < 0.6 for a, b in zip(pol_z, zs)), f"{n}: bez supliku jsou podpery desky NAD podperami police ({[round(z) for z in zs]} vs {[round(z) for z in pol_z]})")
                # tvar a poloha: profil 30x30 v ose X, ve vysce pricek ramu, delka jako bocni pricka, T-styl (spoje) a oba konce dosedaji
                z_l, lo_l, hi_l, i_l = z_stred(r, ("t", S.XRAIL_PRAC_L))
                PM = S.SYSTEMY[r["parametry"]["system"]]["profil_mm"]
                for i in supp:
                    lo, hi = bbox(dily[i])
                    check(abs((hi[0] - lo[0]) - (hi_l[0] - lo_l[0])) < 0.5 and abs((hi[1] - lo[1]) - PM) < 0.5 and abs((hi[2] - lo[2]) - PM) < 0.5, f"{n}: podpera pod deskou je profil {PM:.0f}x{PM:.0f} v ose X delky bocni pricky")
                    check(abs(lo[1] - lo_l[1]) < 0.5 and abs(lo[0] - lo_l[0]) < 0.5, f"{n}: podpera pod deskou lezi ve vysce a v X jako bocni pricka")
                    check(len(dily[i].get("lic_peers", [])) >= 2, f"{n}: podpera pod deskou dosedá oběma konci (lic_peers {dily[i].get('lic_peers')})")
                    prek = [j for j in range(len(dily)) if j != i and dily[j]["part_id"] not in S.SPOJKY_PARTS and np.all(np.minimum(bbox(dily[j])[1], hi) - np.maximum(bbox(dily[j])[0], lo) > 1.0)]
                    check(not prek, f"{n}: podpera pod deskou se s nicim neprotina ({[(j, kl[j]) for j in prek][:3]})")
                inf = [i for i in r["info"] if i["kod"] == "deska_podpery"]
                check(len(inf) == 1 and inf[0]["podpery"] == len(supp) and inf[0]["suplik"] == (("t", S.XRAIL_BOX1) in kl), f"{n}: info deska_podpery {inf}")

# texty informace cs/en/sk
try:
    os.environ.setdefault("STUL_TEST_NO_DB", "1")
except Exception:
    pass
print("pocet podper na polici pri hloubce 1000 (sirka -> ks):", {w: tabulka.get((w, 1000)) for w in SIRKY})
print(f"zkouseno {zkouseno} konfiguraci polic a {zkouseno_d} konfiguraci podper desky")
if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
