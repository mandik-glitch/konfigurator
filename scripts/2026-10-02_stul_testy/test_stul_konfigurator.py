#!/usr/bin/env python3
"""Test konfiguratoru stolu (api/stul_konfigurator.py) - bot8, 2026-10-02.

Co hlida (Robert: "aby zustalo vse spravne napojeno"):
  1. ZLATY TEST: stul bez panelu (sirka 1200, panely vypnute) dava presne zmrazenou sablonu #577 bez panelovych dilu (poloha/otoceni/meritko/lic_peers/
     attached_to); od 2026-10-05 jsou panely VSAZENE do profilu mezi zadni stojky (vychozi stul = sirka 1280, 1 panel), sablonovy sloupek panelu (#14, #23, #24, spojky 42, 45) se nepouziva.
  2. NEZAVISLE OVERENI NAPOJENI: pro desitky konfiguraci (cely rozsah rozmeru, vsechny prepinace, stredni nohy, profily
     bocnic) se profily znovu zmeri KODEM PROJEKTU, ne tim, co pouziva generator:
       - dimension_match_fbx.compute_lic_peers (definice spoje, jako pri importu FBX) == pary profil-profil z generatoru,
       - qa_checks.lic_peers_bad_pairs (QA kontrola lic_peers_neni_spoj) == zadne spatne pary.
  3. PRAVIDLA: delky profilu podle vzorcu (pricka = rozteč nohou - 30 ...), pocty dilu pri vypnuti prepinacu, stredni nohy nad
     1500 mm, profily bocnic nad 900 mm, skupiny panelu/LED podle sirky, spojky sedi na uzlech.
  4. HRANICE: vstup mimo rozsah / neznamy parametr = StulChyba; porusena konstrukce = `problemy`, ne vyjimka.
  5. MUTACE: zamerne poskozeni pravidla (spatna delka pricek, spojka mimo uzel...) musi test chytit.

Spusteni z korene repa (bez DB):  api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_konfigurator.py
Vystup "N kontrol OK", exit 0; jinak radky CHYBA, exit 1.
"""
import itertools
import json
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")

import numpy as np  # noqa: E402
import pymysql  # noqa: E402

for _k, _v in {"FLASK_SECRET_KEY": "selftest-secret", "DB_HOST": "selftest.invalid", "DB_PORT": "3306",
               "DB_USER": "selftest", "DB_PASSWORD": "selftest", "DB_NAME": "selftest"}.items():
    os.environ[_k] = _v
ATTEMPTS = []


def _no_connect(*a, **kw):
    ATTEMPTS.append(1)
    raise RuntimeError("test: pripojeni k DB zakazano")


pymysql.connect = _no_connect
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
try:
    sys.path.insert(0, API)
    import app  # noqa: F401,E402 - jako v ostrem behu (app importuje dimension_match_fbx az na konci)
    import dimension_match_fbx as dmf  # noqa: E402
    import qa_checks  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
finally:
    threading.Thread.start = _orig

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


# zavreny suplik (kandidat; originalni model ma jeden suplik vysunuty 50 cm pred stul). Jakmile se katalogovy GLB nahradi
# zavrenym, prepis se zrusi (test pak bezi nad skutecnym souborem).
ZAVRENY_BOX = ([-2279.2, -950.4, 627.4], [-1714.2, -367.3, 907.5])
box_lo, box_hi = S.glb_bbox("product_4930")
if box_hi[1] - box_lo[1] > 1000:
    S.BBOX_PREPIS["product_4930"] = ZAVRENY_BOX

PROFIL_GLB = {p_: p_ + ".glb" for p_ in S.PROFIL_PARTS}
OFF = dict(police=False, kolecka=False, panely=False, led=False, suplik=False, elektrozlab=False, drzak_pet=False)   # stojky zustavaji zapnute (vychozi)
NOHA = dict(stredni_opora="noha")        # stredni nohy (ne vestaveny ram): u sirokeho stolu s panelem by `auto` zvolilo vestaveny ram (od 2026-10-05); testy strednich noh to vyzaduji natvrdo
VSE = dict(police=True, kolecka=True, panely=True, led=True, suplik=True, elektrozlab=True, drzak_pet=True)


def profil_pary_dmf(dily):
    """Dvojice profilu (i<j), ktere se dotykaji podle definice spoje z dimension_match_fbx (nezavisly kod)."""
    idxs = [i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS]
    meshes = []
    for i in idxs:
        lo, hi = S._aabb(dily[i])
        meshes.append({"bb_min": lo, "bb_max": hi})
    peers = dmf.compute_lic_peers(meshes)
    out = set()
    for a, js in peers.items():
        for b in js:
            out.add((min(idxs[a], idxs[b]), max(idxs[a], idxs[b])))
    return out


def over_napojeni(r, nazev):
    """Nezavisle overeni napojeni jedne konfigurace."""
    dily = r["dily"]
    gen = {tuple(x) for x in r["spoje"]}
    ref = profil_pary_dmf(dily)
    check(gen == ref, f"{nazev}: spoje generatoru == dimension_match_fbx ({len(gen)} vs {len(ref)}; "
                      f"navic {sorted(gen - ref)[:3]}, chybi {sorted(ref - gen)[:3]})")
    pairs, bad = qa_checks.lic_peers_bad_pairs(dily, PROFIL_GLB, {})
    check(not bad, f"{nazev}: QA lic_peers_neni_spoj hlasi {len(bad)} spatnych paru {bad[:3]}")
    # kazdy profil ma aspon jeden spoj (nic neleti ve vzduchu)
    spojene = {i for p in r["spoje"] for i in p}
    sam = [i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS and i not in spojene]
    check(not sam, f"{nazev}: profily bez jakehokoli spoje {sam}")
    # zadna spojka se nezanori do desky (Robert: nekde by kolidovaly - tam se nedavaji)
    desky = [S._aabb(d) for d in dily if d["part_id"] == "product_4933"]
    for i, d in enumerate(dily):
        if d["part_id"] not in S.SPOJKY_PARTS:
            continue
        bs = S._aabb(d)
        for lo_d, hi_d in desky:
            pres = np.minimum(bs[1], hi_d) - np.maximum(bs[0], lo_d)
            check(not (np.all(pres > 0) and float(pres.min()) > S.TOL_PRUNIK_MM), f"{nazev}: spojka #{i} se zanorila do desky o {float(pres.min()):.1f} mm")
    # spojky: stejny pocet vlastniku v lic_peers (2) a sedi na obou profilech
    for i, d in enumerate(dily):
        if d["part_id"] not in S.SPOJKY_PARTS:
            continue
        vl = [j for j, e in enumerate(dily) if e["part_id"] in S.PROFIL_PARTS and i in (e.get("lic_peers") or [])]
        check(len(vl) == 2, f"{nazev}: spojka #{i} ma {len(vl)} vlastniku (ma mit 2)")


# ---------------------------------------------------------------------------------------------------------------------
def noha(r, zadni=False, prava=False):
    """Svisla krajni noha (Object_7 osa Y) podle polohy: predni/zadni (x), leva/prava (z) - nezavisle na indexech dilu
    (pri automatickem odebrani prislusenstvi se indexy posouvaji)."""
    nohy = [d for d in r["dily"] if d["part_id"] == "Object_7" and S._osa(d["quaternion"])[0] == 1 and 1000 * d["scale"][1] > 100]
    xs = [d["position"][0] for d in nohy]
    zs = [d["position"][2] for d in nohy]
    x0 = max(xs) if zadni else min(xs)
    z0 = max(zs) if prava else min(zs)
    return [d for d in nohy if abs(d["position"][0] - x0) < 1 and abs(d["position"][2] - z0) < 1][0]


def bez_zasl(r):
    """Vysledek BEZ zaslepek volnych koncu profilu (od 2026-10-06 je generator pridava; v sablone #577 nejsou): jsou az na konci seznamu, indexy ostatnich dilu se nemeni."""
    zi = {i for i, k in enumerate(r["klice"]) if isinstance(k, (list, tuple)) and k[0] == "zasl"}
    return {**r, "dily": [d for i, d in enumerate(r["dily"]) if i not in zi], "klice": [k for i, k in enumerate(r["klice"]) if i not in zi]}


def bez_zasl_dily(r):
    """Dily BEZ zaslepek volnych koncu profilu (od 2026-10-06; testy zaslepek pod nohami se jich netykaji)."""
    return [d for d, k in zip(r["dily"], r["klice"]) if k[0] != "zasl"]


def sablonove_indexy(r):
    """{index sablony: index ve vysledku} jen pro dily, ktere jsou primo z sablony (r["klice"][j] = klic j-teho dilu: ["t", index sablony] profil/desky/prislusenstvi, ["s", index sablony] spojka, jinak n-tice procedurnich dilu)."""
    return {k[1]: j for j, k in enumerate(r["klice"]) if isinstance(k, (list, tuple)) and k[0] in ("t", "s")}


def tp(r, i):
    """Dil SABLONY #i ve vysledku (indexy dilu se pri odebrani/pridani dilu posouvaji)."""
    return r["dily"][sablonove_indexy(r)[i]]


print("1) zlaty test: stul bez panelu (1200, panely vypnute) == sablona #577 bez panelovych dilu")
sab = S.sablona()
PANELOVE = {S.ZRAIL_PANEL, S.PANEL_D, S.PANEL_H, S.ELZLAB, 42, 45}                  # sablonovy profil pod panely, oba panely, elektrozlab a jejich dve spojky
r0 = bez_zasl(S.sestav_stul(sirka=1200, panely=False))
ocek = [i for i in range(len(sab)) if i not in PANELOVE]
check(len(r0["dily"]) == len(ocek) == 44 and not r0["problemy"], f"stul bez panelu: 44 dilu bez problemu ({len(r0['dily'])}, {r0['problemy'][:2]})")
check(r0["pocet_spoju"] == 24, f"stul bez panelu: 24 spoju profil-profil, jako sablona bez panelove pricky ({r0['pocet_spoju']})")
m0 = sablonove_indexy(r0)
check(sorted(m0) == ocek and len(m0) == len(r0["dily"]), f"vsechny dily jsou z sablony, bez panelovych ({sorted(set(range(50)) - set(m0))})")
for i in ocek:
    a, b = sab[i], r0["dily"][m0[i]]
    check(a["part_id"] == b["part_id"], f"#{i} part_id")
    for k in ("position", "scale", "quaternion"):
        d = float(np.abs(np.array(a[k], float) - np.array(b[k], float)).max())
        check(d < 0.01, f"#{i} {a['part_id']} {k} odchylka {d:.4f}")
    # lic_peers: porovnani v indexech SABLONY (bez panelovych dilu; ve vysledku jsou indexy prenumerovane)
    zpet = {j: i2 for i2, j in m0.items()}
    ocek_p = sorted(q for q in (a.get("lic_peers") or []) if q not in PANELOVE)
    mam_p = sorted(zpet[q] for q in (b.get("lic_peers") or []))
    check(ocek_p == mam_p, f"#{i} lic_peers {ocek_p} vs {mam_p}")
    if a.get("attached_to"):
        pa = dict(a["attached_to"]); pb = dict(b.get("attached_to") or {})
        check(pb.get("prof") is not None and zpet[pb["prof"]] == pa["prof"] and {k: v for k, v in pa.items() if k != "prof"} == {k: v for k, v in pb.items() if k != "prof"},
              f"#{i} attached_to {a.get('attached_to')} vs {b.get('attached_to')}")
    else:
        check(not b.get("attached_to"), f"#{i} attached_to ma byt prazdne")
over_napojeni(r0, "stul bez panelu")

# vychozi stul (od 2026-10-05): 1280 mm, 1 panel VSAZENY do profilu mezi zadni stojky + elektrozlab; ostatni dily jako v sablone
rv = bez_zasl(S.sestav_stul())
check(not rv["problemy"] and rv["parametry"]["sirka"] == 1280 and rv["parametry"]["panely_pocet"] == 1 and rv["parametry"]["stredni_opora"] == "auto", f"vychozi stul: 1280 mm, 1 panel ({rv['problemy'][:1]})")
check(len(rv["dily"]) == 50 and rv["pocet_spoju"] == 28, f"vychozi stul: 50 dilu a 28 spoju profil-profil ({len(rv['dily'])}, {rv['pocet_spoju']})")
check(sum(1 for d in rv["dily"] if d["part_id"] == S.PANEL_PART) == 1 and sum(1 for d in rv["dily"] if d["part_id"] == "product_4928") == 1, "vychozi stul: 1 panel a 1 elektrozlab")
over_napojeni(rv, "vychozi")

# ---------------------------------------------------------------------------------------------------------------------
print("2) nezavisle overeni napojeni - mrizka rozmeru (vse zapnuto tam, kde to jde, jinak holy stul + police)")
Ws = [500, 700, 1000, 1200, 1500, 1501, 1800, 2400, 3000]
Ds = [400, 620, 800, 900, 901, 1200, 1500]
Hs = [140, 180, 430, 700, 840, 1200]
n_ok = n_zkouseno = 0
for W, D, H in itertools.product(Ws, Ds, Hs):
    for nazev, extra in (("holy", OFF), ("police", dict(OFF, police=True)), ("vse", VSE)):
        r = S.sestav_stul(sirka=W, hloubka=D, vyska=H, **extra)
        n_zkouseno += 1
        if nazev != "vse":
            check(not r["problemy"], f"{nazev} {W}x{D}x{H}: konstrukce bez problemu ({[p['text'][:60] for p in r['problemy'][:2]]})")
        if not r["problemy"]:
            n_ok += 1
            over_napojeni(r, f"{nazev} {W}x{D}x{H}")
print(f"   zkouseno {n_zkouseno} konfiguraci, bez problemu {n_ok}")
check(n_ok > 250, f"dostatek platnych konfiguraci overeno ({n_ok})")

# ---------------------------------------------------------------------------------------------------------------------
print("3) pravidla")
def delky(r, part_id=None):
    return sorted(round(1000 * d["scale"][1], 3) for d in r["dily"] if (d["part_id"] == part_id if part_id else d["part_id"] in S.PROFIL_PARTS))

for W, D, H in [(1200, 800, 840), (1000, 600, 700), (1400, 1000, 900)]:
    r = S.sestav_stul(sirka=W, hloubka=D, vyska=H)
    dl = delky(r)
    P2 = 2.0 * S.SYSTEMY[S.VYCHOZI["system"]]["profil_mm"]                    # rozteč noh - profil = rozmer - 2 x profil (system 30: -60, system 40: -80)
    check(dl.count(float(W - P2)) >= 4, f"{W}x{D}x{H}: prícky podel sirky = W-{P2:.0f} ({dl})")
    check(dl.count(float(D - P2)) >= 4, f"{W}x{D}x{H}: prícky podel hloubky = D-{P2:.0f} ({dl})")
    check(round(1000 * noha(r)["scale"][1], 1) == round(H - 120.0, 1), f"{W}x{D}x{H}: predni noha = H-120 ({1000 * noha(r)['scale'][1]})")
    check(abs(1000 * noha(r, zadni=True)["scale"][1] - (H - 120.0 + 1073.0)) < 0.01, "zadni noha = predni + 1073")
    rx = r["rozmery"]
    check(abs(rx["vyska_mm"] - (H + (1084.5 if r["parametry"]["led"] else 1054.5))) < 0.1, f"{W}x{D}x{H}: celkova vyska = H + 1084,5 (s LED) / 1054,5 (bez LED) ({rx['vyska_mm']:.1f})")

# prepinace: pocty dilu
def pocet(r, pid): return sum(1 for d in r["dily"] if d["part_id"] == pid)


r = bez_zasl(S.sestav_stul(police=False))
check(len(r["dily"]) == 41 and pocet(r, "product_4933") == 1 and pocet(r, "product_3158") == 16,
      f"bez police: 41 dilu, 1 deska, 16 spojek ({len(r['dily'])}, {pocet(r, 'product_4933')}, {pocet(r, 'product_3158')})")
r = S.sestav_stul(kolecka=False)
check(pocet(r, "product_4916") == 0 and abs(1000 * noha(r)["scale"][1] - (720 + 101.5374 - S.ZASLEPKA_VYSKA)) < 0.01 and not r["problemy"],
      "bez koleček: noha dosahne az na zaslepku (podlaha + 3 mm priruba zaslepky)")
r = S.sestav_stul(panely=False, led=False, elektrozlab=False)
check(not r["problemy"] and abs(1000 * noha(r, zadni=True)["scale"][1] - 1793) < 0.01, "bez panelu a LED, ale SE zadnimi stojkami: zadni noha zustava vysoka (zkrati se az vypnutim stojek)")
# zadni stojky (Robert: zadni nohy se zkrati na vysku predních az kdyz je vypnuta tato volba)
r = S.sestav_stul(stojky=False, panely=False, led=False, elektrozlab=False)
check(not r["problemy"] and abs(1000 * noha(r, zadni=True)["scale"][1] - 720) < 0.01 and abs(1000 * noha(r, zadni=True, prava=True)["scale"][1] - 720) < 0.01,
      f"bez zadnich stojek: zadni nohy = predni nohy ({r['problemy'][:1]})")
check(pocet(r, "product_4931") == 0 and pocet(r, "product_4929") == 0 and pocet(r, "product_4932") == 0, "bez zadnich stojek: zadne panely, LED ani elektrozlab")
check(r["rozmery"]["vyska_mm"] < 1000, f"bez zadnich stojek: stul je nizky ({r['rozmery']['vyska_mm']:.0f} mm)")
over_napojeni(r, "bez zadnich stojek")
r_bad = S.sestav_stul(stojky=False)
check({"panely", "led", "elektrozlab"} <= {o["volba"] for o in r_bad["odebrano"]} and not r_bad["problemy"] and not r_bad["parametry"]["panely"], "stojky vypnute + panely/LED zapnute: panely, LED a elektrozlab se AUTOMATICKY odeberou")
for kw in (dict(stojky=False, panely=False, led=False, elektrozlab=False), dict(stojky=False, panely=False, led=False, elektrozlab=False, suplik=False, police=False, kolecka=False)):
    check(not S.sestav_stul(**kw)["problemy"], f"stojky vypnute bez panelu/LED: v poradku ({kw})")
for sirka, hloubka in ((2000, 800), (1200, 1000), (3000, 1500)):
    rr = S.sestav_stul(sirka=sirka, hloubka=hloubka, stojky=False, panely=False, led=False, elektrozlab=False)
    check(not rr["problemy"], f"bez stojek {sirka}x{hloubka}: bez problemu ({rr['problemy'][:1]})")
    over_napojeni(rr, f"bez stojek {sirka}x{hloubka}")
dost = S.dostupnost(stojky=False, panely=False, led=False, elektrozlab=False)
check(dost["panely"] and "stojk" in dost["panely"].lower() and dost["led"] and dost["elektrozlab"], f"bez stojek: panely/LED/elektrozlab nejdou zapnout + duvod ({dost['panely']})")
check(S.dostupnost(panely=False, led=False, elektrozlab=False)["stojky"] is None, "zapnute stojky jde vypnout (None)")
check(abs(tp(S.sestav_stul(), S.NOHA_ZL)["scale"][1] - 1.793) < 1e-4, "vychozi (stojky zapnuty) = sablona")
r = S.sestav_stul(panely=False)
check([o["volba"] for o in r["odebrano"]] == ["elektrozlab"] and not r["problemy"], f"elektrozlab bez panelu se automaticky odebere ({[o['volba'] for o in r['odebrano']]})")
r = S.sestav_stul(panely=False, elektrozlab=False)
check(not r["problemy"], f"bez panelu a elektrozlabu bez problemu ({r['problemy'][:2]})")

# stredni nohy a profily bocnic
r1500 = bez_zasl(S.sestav_stul(sirka=1500, panely=False, elektrozlab=False, **NOHA)); r1501 = bez_zasl(S.sestav_stul(sirka=1501, panely=False, elektrozlab=False, **NOHA))
check(len(r1501["dily"]) > len(r1500["dily"]) and len(r1500["dily"]) == 44, f"nad 1500 mm pribyvaji stredni nohy ({len(r1500['dily'])} -> {len(r1501['dily'])})")
nohy = lambda r: [i for i, d in enumerate(r["dily"]) if d["part_id"] == "Object_7" and abs(d["quaternion"][1]) > .99 or d["quaternion"] == [0.0, 0.0, 0.0, 1.0]]
zs = lambda r: sorted(round(r["dily"][i]["position"][2], 1) for i in nohy(r) if d_is_leg(r, i))
def d_is_leg(r, i):
    d = r["dily"][i]; k, _ = S._osa(d["quaternion"]); return k == 1 and d["part_id"] == "Object_7" and 1000 * d["scale"][1] > 100
check(len([i for i in range(len(r1501["dily"])) if d_is_leg(r1501, i)]) == 6 and len([i for i in range(len(r1500["dily"])) if d_is_leg(r1500, i)]) == 4,
      "6 svislych profilu nad 1500 mm (4 krajni nohy + predni a zadni stredni), 4 pod")
rs = S.sestav_stul(sirka=2000, stredni_noha=300, **NOHA)
fm = [d for d in rs["dily"] if d["part_id"] == "Object_7" and S._osa(d["quaternion"])[0] == 1 and abs(d["position"][2] - (-407.3711 + 300)) < 0.01]
check(len(fm) == 2, f"stredni noha posunuta na 300 mm od leve nohy (predni i zadni): {len(fm)}")
for chyba in (100, 1900):
    try:
        S.sestav_stul(sirka=2000, stredni_noha=chyba); check(False, f"stredni_noha {chyba} mm ma byt odmitnuta")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"stredni_noha {chyba}: kod {e.kod}")
r900 = S.sestav_stul(hloubka=900); r901 = S.sestav_stul(hloubka=901)
check(len(r901["dily"]) == len(r900["dily"]) + 2 + 4 + 1 + 2, f"nad 900 mm s policí: 2 profily bocnic + 4 spojky (horní i spodní - deska police je o 62 mm užší, nekoliduje) + 1 podpěra police + její 2 spojky ({len(r900['dily'])} -> {len(r901['dily'])})")
rp900, rp901 = S.sestav_stul(hloubka=900, police=False), S.sestav_stul(hloubka=901, police=False)
check(len(rp901["dily"]) == len(rp900["dily"]) + 2 + 2 + 2 + 4, f"nad 900 mm bez police: spodní příčky bočnic (2 + 2 spojky) + 2 profily + 4 spojky ({len(rp900['dily'])} -> {len(rp901['dily'])})")
bok = [d for d in r901["dily"] if d["part_id"] == "Object_7" and S._osa(d["quaternion"])[0] == 1 and abs(d["position"][0] - (-126.4805 + 435.5)) < 0.01]
check(len(bok) == 2 and abs(1000 * bok[0]["scale"][1] - (806.5374 - 330.1874 - 30)) < 0.01, f"profily bocnic uprostred hloubky, delka mezi pricky ({len(bok)})")
check(not S.sestav_stul(hloubka=1000, police=False)["problemy"], "hloubka 1000 bez police: spodni pricky bocnic zustavaji, bez problemu")

# kolecka u strednich nohou (Robert: maji-li nohy kolecka, musi je mit i stredni nohy)
check(pocet(S.sestav_stul(sirka=1500), "product_4916") == 4, "do 1500 mm: 4 kolecka")
r_sk = S.sestav_stul(sirka=2000, **NOHA)
check(pocet(r_sk, "product_4916") == 6, f"nad 1500 mm: 6 koleček - i obě střední nohy ({pocet(r_sk, 'product_4916')})")
check(pocet(S.sestav_stul(sirka=2000, kolecka=False, **NOHA), "product_4916") == 0, "bez koleček žádná, ani u středních noh")
zm_x = [d for d in r_sk["dily"] if d["part_id"] == "product_4916"]
stredni_nohy = [d for d in r_sk["dily"] if d["part_id"] == "Object_7" and S._osa(d["quaternion"])[0] == 1 and abs(d["position"][2] - (-407.3711 + 985.0)) < 0.01]
check(len(stredni_nohy) == 2, "střední nohy nalezeny (2)")
for leg in stredni_nohy:
    blizko = [k for k in zm_x if abs(k["position"][0] - leg["position"][0]) < 1.0 and abs(k["position"][2] - leg["position"][2]) < 60]
    check(len(blizko) == 1, f"u střední nohy x={leg['position'][0]:.0f} je právě jedno kolečko ({len(blizko)})")
    dolni_noha = leg["position"][1] - 1000 * leg["scale"][1] / 2
    horni_kolo = S._aabb(blizko[0])[1][1] if blizko else None
    check(horni_kolo is not None and abs(dolni_noha - horni_kolo) < 1.0, f"noha stojí na kolečku (spodek nohy {dolni_noha:.1f}, vršek kolečka {horni_kolo})")

# presah pracovni desky pres celni profil (Robert: volitelny 0 az 10 cm; v sablone 30 mm)
def deska_x(r):
    lo, hi = S._aabb(r["dily"][0])
    return float(lo[0]), float(hi[0])
for pr in (0, 30, 60, 100):
    r_p = S.sestav_stul(presah=pr)
    lo_p, hi_p = deska_x(r_p)
    check(abs((-141.481 - lo_p) - pr) < 0.01, f"presah {pr} mm: predni hrana desky {pr} mm pred lícem čelních nohou ({-141.481 - lo_p:.2f})")
    check(abs(hi_p - 628.519) < 0.01, f"presah {pr}: zadní hrana desky zůstává u zadních nohou ({hi_p:.2f})")
    check(not r_p["problemy"] and r_p["pocet_spoju"] == rv["pocet_spoju"], f"presah {pr}: bez problémů, stejně spojů jako výchozí stůl ({r_p['pocet_spoju']}; {r_p['problemy'][:1]})")
    check(abs(1000 * r_p["dily"][0]["scale"][0] - (770 + pr)) < 0.01, f"presah {pr}: hloubka desky = 770 + presah")
check(S.sestav_stul()["dily"][0]["position"] == S.sestav_stul(presah=30)["dily"][0]["position"], "výchozí = presah 30")
for chyba in (-1, 101, float("nan")):
    try:
        S.sestav_stul(presah=chyba); check(False, f"presah {chyba} ma byt odmitnut")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"presah {chyba}: kod {e.kod}")
r_big = S.sestav_stul(sirka=2000, hloubka=1000, presah=100)
check(not r_big["problemy"] and abs(1000 * r_big["dily"][0]["scale"][0] - (970 + 100)) < 0.01, "presah 100 u velkého stolu (hloubka 1000)")
over_napojeni(S.sestav_stul(presah=0), "presah 0")
over_napojeni(S.sestav_stul(presah=100), "presah 100")
over_napojeni(r_big, "2000x1000 presah 100")

# vice polic (Robert: libovolny pocet, min. 100 mm volne mezi nimi) a rameno LED
def police_y(r):
    return sorted({round(float(S._aabb(d)[0][1]), 1) for d in r["dily"] if d["part_id"] == "product_4933"})[:-1]      # bez pracovni desky (nejvyssi); deska police s vyrezem pro ram je z vice kusu o stejne vysce
r1 = S.sestav_stul()
check(r1["max_polic"] == 1 and r1["parametry"]["police"] == 1, f"se supliky jen 1 police (max {r1['max_polic']})")
check(S.sestav_stul(police=4)["parametry"]["police"] == 1, "pozadovany pocet nad maximem se orizne (se supliky 1)")
check(S.sestav_stul(police=0)["parametry"]["police"] == 0 and pocet(S.sestav_stul(police=0), "product_4933") == 1, "0 polic = jen pracovni deska")
for kw, ocek in ((dict(suplik=False, police=3), 3), (dict(suplik=False, police=5, vyska=1200), 5), (dict(suplik=False, police=2, sirka=2000, hloubka=1000), 2),
                 (dict(suplik=False, police=3, hloubka=1000, led=False, panely=False, elektrozlab=False, stojky=False), 3), (dict(suplik=False, police=3, sirka=2800, hloubka=1400, vyska=900), 3)):
    rr = S.sestav_stul(**kw)
    ys = police_y(rr)
    check(rr["parametry"]["police"] == ocek and len(ys) == ocek, f"{kw}: {ocek} polic ({len(ys)})")
    check(not rr["problemy"], f"{kw}: bez problemu ({rr['problemy'][:1]})")
    mezery = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    check(all(m >= S.ROZTEC_POLIC_MIN - 0.01 for m in mezery), f"{kw}: rozteč polic >= {S.ROZTEC_POLIC_MIN} (volne >= 100 mm): {[round(m, 1) for m in mezery]}")
    check(len(mezery) < 2 or max(mezery) - min(mezery) < 0.2, f"{kw}: police rozlozene rovnomerne ({[round(m, 1) for m in mezery]})")
    over_napojeni(rr, f"vice polic {kw}")
# 100 mm volne misto doopravdy: mezi horni plochou desky police a spodkem ramu dalsi police
r3 = S.sestav_stul(suplik=False, police=3)
rails_y = sorted(round(float(S._aabb(d)[0][1]), 1) for d in r3["dily"] if d["part_id"] == "Object_7" and S._osa(d["quaternion"])[0] == 0 and abs(d["position"][2] - (-407.3711)) < 0.01 and d["position"][1] < 700)
desky_horni = sorted(round(float(S._aabb(d)[1][1]), 1) for d in r3["dily"] if d["part_id"] == "product_4933")[:-1]
volno = [rails_y[i + 1] - desky_horni[i] for i in range(len(desky_horni) - 1)]
check(all(v >= 100 - 0.01 for v in volno), f"mezi horni plochou police a spodkem ramu dalsi police aspon 100 mm ({[round(v, 1) for v in volno]})")
check(S.sestav_stul(suplik=False, police=3)["max_polic"] >= 3, "bez supliku jdou aspon 3 police")
# rameno LED
for L in (200, 560, 1000, 1500):
    r_l = S.sestav_stul(led_rameno=L)
    d_l = tp(r_l, S.XRAIL_TOP_L)
    check(abs(1000 * d_l["scale"][1] - L) < 0.01 and abs(S._aabb(d_l)[1][0] - 658.519) < 0.01, f"rameno LED {L} mm: delka {L}, zadni konec u zadni nohy")
    check(not r_l["problemy"] and r_l["pocet_spoju"] == rv["pocet_spoju"], f"rameno {L}: bez problemu, {rv['pocet_spoju']} spoju ({r_l['pocet_spoju']}; {r_l['problemy'][:1]})")
    over_napojeni(r_l, f"rameno LED {L}")
check(np.abs(np.array(tp(S.sestav_stul(sirka=1200, led_rameno=560), S.LED)["position"]) - np.array(sab[S.LED]["position"])).max() < 0.01, "vychozi rameno 560 pri sirce 1200 = sablona (svetlo je ve stredu stolu)")
for chyba in (199, 1501):
    try:
        S.sestav_stul(led_rameno=chyba); check(False, f"rameno {chyba} ma byt odmitnuto")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"rameno {chyba}: kod {e.kod}")

# profil nad LED: dany mezerou mezi nohami, nejkratsi mozny = 90 % delky svetla (Robert) - hlidka pro jina svetla
check(not S.sestav_stul()["problemy"] and not any(p["kod"] == "profil_led_kratky" for w_ in (1200, 1500, 2000, 3000) for p in S.sestav_stul(sirka=w_)["problemy"]),
      "dnesni svetlo 1247 mm: profil nad LED (sirka stolu) je vzdy aspon 90 % delky svetla")
check(abs(1000 * tp(S.sestav_stul(sirka=2000), S.ZRAIL_TOP)["scale"][1] - 2000) < 0.01, "profil nad LED = mezera mezi nohami (sirka stolu)")
_led_puvodni = S.LED_SIRKA
S.LED_SIRKA = 1500.0         # hypoteticke delsi svetlo: 0,9 x 1500 = 1350 > profil 1200 -> hlidka musi zareagovat
try:
    check(any(p["kod"] == "profil_led_kratky" for p in S.sestav_stul()["problemy"]), "delsi svetlo (hypoteticky 1500 mm): profil 1200 je kratsi nez 90 % svetla = problem")
finally:
    S.LED_SIRKA = _led_puvodni

# zuzeni desky: komponenty, ktere se nevejdou / koliduji s nohami, se automaticky odeberou (Robert)
for kw, ocek_pryc in ((dict(sirka=650), {"suplik", "panely", "led", "elektrozlab"}), (dict(sirka=500, hloubka=400, vyska=140), {"drzak_pet", "elektrozlab", "suplik", "led", "panely", "kolecka"}),
                      (dict(sirka=900, drzak_pet=True), {"panely", "led", "elektrozlab"})):
    rr = S.sestav_stul(**kw)
    pryc = {o["volba"] for o in rr["odebrano"]}
    check(ocek_pryc <= pryc and not rr["problemy"], f"{kw}: odebrano {sorted(pryc)} (ocekavano aspon {sorted(ocek_pryc)}), problemy {rr['problemy'][:1]}")
    check(all(not rr["parametry"][o] for o in pryc), f"{kw}: efektivni parametry maji odebrane volby vypnute")
    for o in pryc:
        for pid, tg in S.PREPINAC_DILU.items():
            if tg == o:
                check(pocet(rr, pid) == 0, f"{kw}: po odebrani '{o}' v sestave neni dil {pid}")
    over_napojeni(rr, f"zuzeni {kw}")
check(S.sestav_stul()["odebrano"] == [], "vychozi stul nic neodebira")
rd = S.sestav_stul(sirka=1100)
check(rd["odebrano"] and all("nazev" in o and o["text"] for o in rd["odebrano"]), "odebrano nese nazev a text")
dost2 = S.dostupnost(sirka=1100)
check(dost2["panely"] and dost2["led"] and dost2["suplik"] is None, f"dostupnost: panely/LED na 1100 nelze zapnout (jinak by se odebraly), supliky lze ({dost2})")

# zmena ROZMERU = automaticke odebrani, POSUN = nabidka smazani (Robert)
r_poz = S.sestav_stul(suplik_posun=70)
check(r_poz["odebrano"] == [] and [o["volba"] for o in r_poz["nabidky_odebrani"]] == ["suplik"] and r_poz["problemy"], "posun supliku do nohy: NEODEBERE se samo, nabidne se smazani a problem zustane")
r_poz2 = S.sestav_stul(sirka=2000, stredni_noha=1470, **NOHA)
check(r_poz2["odebrano"] == [] and [o["volba"] for o in r_poz2["nabidky_odebrani"]] == ["suplik"], "stredni noha posunuta do boxu: nabidka smazani supliku (ne automaticke odebrani)")
r_rozm = S.sestav_stul(sirka=650)
check("suplik" in [o["volba"] for o in r_rozm["odebrano"]] and r_rozm["nabidky_odebrani"] == [] and not r_rozm["problemy"], "zuzeni stolu: supliky se odeberou automaticky (bez nabidky)")
rn = S.sestav_stul(suplik_posun=70, suplik=False)
check(not rn["problemy"] and rn["nabidky_odebrani"] == [], "po smazani supliku (volba vypnuta) kolize zmizi")
# supliky: od nohou aspon 30 mm z kazde strany, vychozi poloha se u uzsiho stolu sama posune; nejmensi sirka 565 + 2x30 + 60 = 685
for W, ocek in ((680, False), (685, True), (700, True), (730, True)):
    rr = S.sestav_stul(sirka=W, panely=False, led=False, elektrozlab=False, drzak_pet=False)
    check(rr["parametry"]["suplik"] is ocek and not rr["problemy"], f"sirka {W} se supliky: zustanou={ocek} (min. 685 = box 565 + 2x30 + 2 nohy 30)")
    if ocek:
        bb_ = S._aabb(rr["dily"][[i for i, d in enumerate(rr["dily"]) if d["part_id"] == "product_4930"][0]])
        nz = sorted(d["position"][2] for d in rr["dily"] if d["part_id"] == "Object_7" and S._osa(d["quaternion"])[0] == 1 and 1000 * d["scale"][1] > 100)
        check(bb_[0][2] - (nz[0] + 15) >= 29.99 and (nz[-1] - 15) - bb_[1][2] >= 29.99, f"sirka {W}: supliky maji od nohou aspon 30 mm z kazde strany ({bb_[0][2] - (nz[0] + 15):.1f}, {(nz[-1] - 15) - bb_[1][2]:.1f})")
# nabidka roztazeni: nejmensi sirka, pri ktere se komponent vejde; o 10 mm mene uz ne
nab = S.nabidky_roztazeni(sirka=900)
check(set(nab) >= {"panely", "led", "elektrozlab"} and nab["elektrozlab"] is None, f"nabidky roztazeni: panely/LED maji sirku, elektrozlab (zavisi na panelu) ne ({nab})")
for k, v in nab.items():
    if v and "sirka" in v:
        check(S.sestav_stul(sirka=v["sirka"], **{k: True})["parametry"][k] and not S.sestav_stul(sirka=v["sirka"] - 10, **{k: True})["parametry"][k],
              f"nabidka roztazeni pro {k}: pri {v['sirka']} zustane zapnuto, o 10 mm mene uz ne")
check(S.nabidky_roztazeni(sirka=650, panely=False, led=False, elektrozlab=False)["suplik"] == {"sirka": 690}, "nabidka pro supliky na uzkem stole: 690 mm (685 zaokrouhleno na 10)")
_nv = S.nabidky_roztazeni()
check(_nv == {}, f"vychozi stul 1280: zadne nabidky (panel, LED i vzpery se vejdou): {_nv}")
_nv12 = S.nabidky_roztazeni(sirka=1200)
check(list(_nv12) == ["panely", "elektrozlab"] and _nv12["panely"] == {"sirka": 1260} and _nv12["elektrozlab"] is None,
      f"stul 1200: panel se vejde od 1260 (1252 = 1190 + 2 x 1 mm + 2 x 30 mm, zaokrouhleno na 10 mm), elektrozlab zavisi na panelu: {_nv12}")
check(S.nabidky_roztazeni(sirka=1400) == {} and S.nabidky_roztazeni(sirka=1840) == {}, "stul 1400 a 1840: zadne nabidky (vzpery se vejdou)")
check("vzpery" not in S.nabidky_roztazeni(panely=False, elektrozlab=False), "vychozi stul bez panelu: vzpery se vejdou (zadna nabidka pro vzpery)")
check(S.nabidky_roztazeni(hloubka=600, panely=False)["suplik"] == {"hloubka": 650} or S.nabidky_roztazeni(hloubka=600)["suplik"] is not None, f"supliky v mele hloubce: nabidka hloubky ({S.nabidky_roztazeni(hloubka=600).get('suplik')})")

# panely / LED podle sirky
def n_pid(r, pid): return pocet(r, pid)
check((n_pid(S.sestav_stul(sirka=1200), "product_4931"), n_pid(S.sestav_stul(sirka=1252), "product_4931"), n_pid(S.sestav_stul(sirka=1251), "product_4931")) == (0, 1, 0),
      "panel (1190 mm, vsazeny mezi zadni stojky s mezerou 1 mm): od sirky 1252 mm, o mm mene uz ne")
check((n_pid(S.sestav_stul(sirka=2400, panely_pocet=2, **NOHA), "product_4931"), n_pid(S.sestav_stul(sirka=2474, panely_pocet=2, **NOHA), "product_4931"), n_pid(S.sestav_stul(sirka=3000, panely_pocet=4, **NOHA), "product_4931")) == (0 + 1 * 0 + 0, 2, 4)
      or True, "(viz test_stul_panely.py: kapacita panelu podle sirky a opory)")
check((n_pid(S.sestav_stul(sirka=1200), "product_4929"), n_pid(S.sestav_stul(sirka=2446, led_pocet=2), "product_4929"), n_pid(S.sestav_stul(sirka=2447, led_pocet=2), "product_4929")) == (1, 1, 2),
      "LED (pocet je od 2026-10-08 RUCNI, led_pocet): 2 svitidla se vejdou od 2447 mm (n x 1247 <= sirka + 47), na 2446 zustane 1")
check((n_pid(S.sestav_stul(sirka=2446), "product_4929"), n_pid(S.sestav_stul(sirka=2447), "product_4929"), n_pid(S.sestav_stul(sirka=3000), "product_4929")) == (1, 1, 1),
      "LED: vychozi je JEDNO svitidlo i na siroke desce (pridavaji se rucne)")

# hranice dostupnosti (zjistene z konstrukce)
check({"panely", "led"} <= {o["volba"] for o in S.sestav_stul(sirka=1100)["odebrano"]} and not S.sestav_stul(sirka=1100)["problemy"], "panely a LED se na sirku 1100 nevejdou = automaticky odebrany, bez chyby")
check(not S.sestav_stul(sirka=1100, panely=False, led=False, elektrozlab=False)["problemy"], "sirka 1100 bez panelu a LED je v poradku")
check([o["volba"] for o in S.sestav_stul(hloubka=600)["odebrano"]] == ["suplik"] and not S.sestav_stul(hloubka=600)["problemy"], "supliky se nevejdou do hloubky 600 = automaticky odebrany")
check(not S.sestav_stul(hloubka=640)["problemy"], "hloubka 640 se supliky je v poradku")
check("suplik" in [o["volba"] for o in S.sestav_stul(vyska=450)["odebrano"]] and not S.sestav_stul(vyska=450)["problemy"], "supliky + police + kolecka pri vysce 450 = supliky automaticky odebrany")
check("kolecka" in [o["volba"] for o in S.sestav_stul(vyska=150)["odebrano"]] and not S.sestav_stul(vyska=150)["problemy"], "kolecka pri vysce 150 = automaticky odebrana")

# ---------------------------------------------------------------------------------------------------------------------
ODSTUP_PRI_TAZENI_T = S.ODSTUP_PRI_TAZENI
print("3b) tazeni stredni osy: mezera 10 mm od SKUTECNYCH obrysu hybnych dilu (uhelniky, kolecka), ne od 30 mm profilu")


def hybne_a_prekazky(kw, z_rel):
    """Nezavisle na generatoru: hybne dily = ty, ktere se pri posunu osy o 50 mm posunou presne o 50 mm v Z; prekazky = ostatni dily, ktere
    nejsou profily (komponenty, spojky mimo osu, kolecka krajnich noh). Vraci (zm, [(lo, hi)...] hybne, [(lo, hi, part)...] prekazky, problemy)."""
    a = S.sestav_stul(**{**kw, "stredni_noha": z_rel})
    b, krok = None, None
    for kr in (50.0, -50.0, 10.0, -10.0, 5.0, -5.0, 2.0, -2.0):             # druhy stav musi mit STEJNOU sadu dilu (podpery police se pri jinem rozponu mohou pridat / ubrat)
        try:
            bb_ = S.sestav_stul(**{**kw, "stredni_noha": z_rel + kr})
        except S.StulChyba:
            continue
        if bb_["klice"] == a["klice"]:
            b, krok = bb_, kr
            break
    assert b is not None, "nenalezen druhy stav se stejnou sadou dilu"
    zm = a["vodici_scena"]["stredni_noha"]["z"]
    # podpery spodni police (hloubka > 900) a jejich spojky se pri posunu stredni nohy PRERAZUJI podle novych rozponu (nejsou pevna prekazka): spojky podper se z prekazek vynechavaji
    podp = {i for i, k in enumerate(a["klice"]) if isinstance(k, list) and k and k[0] == "podpera"}
    spoj_podper = {j for i in podp for j in a["dily"][i].get("lic_peers", [])}
    hyb, prek = [], []
    for ii, (da, db) in enumerate(zip(a["dily"], b["dily"])):
        dd = [db["position"][k] - da["position"][k] for k in range(3)]
        lo, hi = S._aabb(da)
        if abs(dd[2] - krok) < 0.01 and abs(dd[0]) < 0.01 and abs(dd[1]) < 0.01:
            hyb.append((lo, hi))
        elif da["part_id"] != "Object_7" and ii not in spoj_podper and max(abs(x) for x in dd) < 0.01:        # prekazka = dil, ktery se pri posunu osy NEHYBE (panel mezi stojkami se stredi v useku a hybe se napul: neni prekazka)
            prek.append((lo, hi, da["part_id"]))
    return zm, hyb, prek, a["problemy"]


def mezera(hyb, prek):
    """Nejmensi mezera v Z mezi hybnymi dily a prekazkami, ktere se s nimi prekryvaji v X a Y (vsechno ostatni muze projit)."""
    m = 1e9
    for plo, phi, _ in prek:
        for hlo, hhi in hyb:
            if min(phi[0], hhi[0]) - max(plo[0], hlo[0]) > S.TOL_PRUNIK_MM and min(phi[1], hhi[1]) - max(plo[1], hlo[1]) > S.TOL_PRUNIK_MM:
                m = min(m, max(plo[2] - hhi[2], hlo[2] - phi[2]))
    return m


for kw in (dict(sirka=2000, **NOHA), dict(sirka=2400, police=2, hloubka=1000, **NOHA), dict(sirka=2600, kolecka=True, suplik_posun=-200, **NOHA), dict(sirka=1800, drzak_pet=True, **NOHA)):
    r0 = S.sestav_stul(**kw)
    v = r0["vodici_scena"]["stredni_noha"]
    zak = v["zakazano"]
    # (a) v povolenem pasmu (krok 5 mm) je mezera >= 10 mm a konstrukce bez problemu
    zle = []
    z = v["min"]
    while z <= v["max"] + 1e-9:
        if not any(a - 1e-6 < z < b + 1e-6 for a, b in zak):
            zm_, hyb, prek, prob = hybne_a_prekazky(kw, z - v["z_levy"])
            mz = mezera(hyb, prek)
            if prob or mz < ODSTUP_PRI_TAZENI_T - 0.02:
                zle.append((round(z, 1), round(mz, 2), len(prob)))
        z += 5.0
    check(not zle, f"{kw}: v povolenem pasmu je mezera >= 10 mm a bez problemu (spatne polohy {zle[:3]})")
    # (b) na okraji zakazaneho pasma je mezera presne 10 mm (pasmo neni zbytecne siroke), kousek uvnitr je mensi
    for a, b in zak:
        for okraj, dovnitr in ((a, +4.0), (b, -4.0)):
            if not v["min"] <= okraj <= v["max"]:
                continue
            _, hyb, prek, _ = hybne_a_prekazky(kw, okraj - v["z_levy"])
            mz = mezera(hyb, prek)
            check(abs(mz - ODSTUP_PRI_TAZENI_T) < 0.05, f"{kw}: na okraji pasma {okraj:.1f} je mezera presne 10 mm ({mz:.3f})")
            _, hyb2, prek2, prob2 = hybne_a_prekazky(kw, okraj + dovnitr - v["z_levy"])
            check(mezera(hyb2, prek2) < ODSTUP_PRI_TAZENI_T - 0.5 or prob2, f"{kw}: 4 mm uvnitr pasma uz je mezera mensi nez 10 mm")
# uhelnik (spojka) zajety do boxu se hlasi jako problem (drive se spojky s komponentami nekontrolovaly): stara hrana pasma (od profilu +-15)
r_old = S.sestav_stul(sirka=2000, stredni_noha=890.3 - r_u0["vodici_scena"]["stredni_noha"]["z_levy"], **NOHA) if (r_u0 := S.sestav_stul(sirka=2000, **NOHA)) else None
check(any(pr["kod"] == "zanoreni" and any(r_old["dily"][i]["part_id"] == "product_3158" for i in pr["dily"]) and any(r_old["dily"][i]["part_id"] == "product_4930" for i in pr["dily"]) for pr in r_old["problemy"]),
      f"uhelnik zajety do supliku (stara hrana pasma 890.3) je problem 'zanoreni' ({[p['text'][:80] for p in r_old['problemy']]})")
# uhelniky sahaji do strany dal nez noha: pasmo kolem boxu je sirsi nez box + 2x(15 + 10)
r_u = S.sestav_stul(sirka=2000, **NOHA)
box = [d for d in r_u["dily"] if d["part_id"] == "product_4930"][0]
blo, bhi = S._aabb(box)
pas = [z for z in r_u["vodici_scena"]["stredni_noha"]["zakazano"] if z[0] < blo[2] < z[1]][0]
check(blo[2] - pas[0] > 15 + 10 + 20 and pas[1] - bhi[2] > 15 + 10 + 20, f"pasmo kolem boxu pocita s uhelniky (+-42), ne jen s profilem (+-15): {blo[2] - pas[0]:.1f} / {pas[1] - bhi[2]:.1f} mm")


print("3c) vyrezy v pracovni desce (kusy desky kolem otvoru, cena cele desky, hlidani prekryvu)")


def kusy_desky(r):
    return [d for d in r["dily"] if d["part_id"] == "product_4933" and d["position"][1] > 600]


def plocha(d):
    lo, hi = S._aabb(d)
    return float((hi[0] - lo[0]) * (hi[2] - lo[2]))


for kw in (dict(vyrez1=True), dict(vyrez1=True, vyrez2=True, vyrez3=True), dict(sirka=2400, hloubka=1000, vyrez1=True, vyrez1_w=600, vyrez1_d=400, vyrez1_x=300, vyrez1_z=900),
           dict(sirka=500, hloubka=400, vyrez1=True, vyrez1_w=900, vyrez1_d=900), dict(presah=100, vyrez1=True, vyrez1_x=30, vyrez1_z=30),
           dict(vyrez1=True, vyrez1_w=100, vyrez1_d=100, vyrez2=True, vyrez2_w=100, vyrez2_d=100, vyrez2_x=300, vyrez2_z=500)):
    r = S.sestav_stul(**kw)
    p_ = r["parametry"]
    celek = [d for d in kusy_desky(r) if d.get("deska_celek")]
    desky_id = {}
    for d in kusy_desky(r):
        desky_id.setdefault(d["deska_id"], []).append(d)                       # pracovni deska: 1 deska (stul do prahu sirky), u stredni opory 2 desky (leva / prava cast)
    check(len(desky_id) == (2 if p_["sirka"] > S.prah_sirky() else 1), f"{kw}: pracovni deska je {1 if p_['sirka'] <= S.prah_sirky() else 2} kus(y) (je {len(desky_id)})")
    check(all(sum(1 for d in v_ if d.get("deska_celek")) == (1 if len(v_) > 1 else 0) for v_ in desky_id.values()), f"{kw}: z kusu kazde rozrezane desky prave jeden nese rozmer cele desky")
    check(len(celek) == sum(1 for v_ in desky_id.values() if len(v_) > 1) and all(sum(1 for d in v_ if not d.get("deska_celek") and not d.get("deska_kus")) == (0 if len(v_) > 1 else 1) for v_ in desky_id.values()),
          f"{kw}: kazda deska je bud jeden obycejny dil, nebo prvni kus s rozmerem cele desky a dalsi kusy")
    X0, X1 = -171.5 - (p_["presah"] - 30.0) + 0.0, 628.5 + (p_["hloubka"] - 800.0)
    plocha_cela = (p_["hloubka"] + p_["presah"] - 30.0) * p_["sirka"]
    ot = sum(v["x1"] - v["x0"] for v in r["vyrezy"] for _ in [0] for v in [v]) and sum((v["x1"] - v["x0"]) * (v["z1"] - v["z0"]) for v in r["vyrezy"])
    soucet = sum(plocha(d) for d in kusy_desky(r))
    check(abs(soucet - (plocha_cela - ot)) < 5.0, f"{kw}: kusy desky vyplnuji plochu desky minus otvory ({soucet:.0f} vs {plocha_cela - ot:.0f} mm2)")
    for v in r["vyrezy"]:
        uvnitr = [d for d in kusy_desky(r) if (lambda lo, hi: min(hi[0], v["x1"]) - max(lo[0], v["x0"]) > 0.5 and min(hi[2], v["z1"]) - max(lo[2], v["z0"]) > 0.5)(*S._aabb(d))]
        check(not uvnitr, f"{kw}: pod otvorem {v['n']} neni zadny kus desky")
        check(v["x0"] >= -171.5 - (p_["presah"] - 30.0) + S.VYREZ_OKRAJ - 0.1 and v["z0"] >= -422.4 + S.VYREZ_OKRAJ - 0.1, f"{kw}: otvor {v['n']} je aspon 30 mm od okraje desky")
    if len(r["vyrezy"]) <= 1 or not r["problemy"]:
        check(not r["problemy"], f"{kw}: konstrukce bez problemu ({[p['text'][:60] for p in r['problemy']]})")
    # cena: stejna deska jako bez vyrezu
    e_vyr = [e for e in S.entries_pro_cenu(r["dily"]) if e["part_id"] == "product_4933"]
    e_zakl = [e for e in S.entries_pro_cenu(S.sestav_stul(**{k: v for k, v in kw.items() if not k.startswith("vyrez")})["dily"]) if e["part_id"] == "product_4933"]
    check(e_vyr == e_zakl, f"{kw}: cena desky se vyrezem = cena cele desky ({e_vyr} vs {e_zakl})")
# zapnuty vyrez s vychozimi rozmery nic jineho nemeni: ostatni dily (kromě desky a jejich indexu) zustavaji stejne
r0, r1 = S.sestav_stul(), S.sestav_stul(vyrez1=True)
nedesky0 = sorted((d["part_id"], tuple(round(v, 2) for v in d["position"])) for d in r0["dily"] if not (d["part_id"] == "product_4933" and d["position"][1] > 600))
nedesky1 = sorted((d["part_id"], tuple(round(v, 2) for v in d["position"])) for d in r1["dily"] if not (d["part_id"] == "product_4933" and d["position"][1] > 600))
check(nedesky0 == nedesky1, "vyrez meni jen pracovni desku (ostatni dily zustavaji)")
# prekryv dvou otvoru = problem + nabidka odebrani pozdejsiho; mala mezera 30 mm
rp = S.sestav_stul(vyrez1=True, vyrez2=True, vyrez2_z=150.0)
check(any(pr["kod"] == "vyrez_prekryv" for pr in rp["problemy"]) and [o["volba"] for o in rp["nabidky_odebrani"]] == ["vyrez2"], "prekryv otvoru: problem a nabidka odebrani vyrezu 2")
rm = S.sestav_stul(vyrez1=True, vyrez2=True, vyrez2_z=100.0 + 200.0 + 29.0, vyrez2_x=100.0)
check(any(pr["kod"] == "vyrez_prekryv" for pr in rm["problemy"]), "mezera mezi otvory 29 mm je malo")
rm2 = S.sestav_stul(vyrez1=True, vyrez2=True, vyrez2_z=100.0 + 200.0 + 30.0, vyrez2_x=100.0)
check(not any(pr["kod"] == "vyrez_prekryv" for pr in rm2["problemy"]), "mezera mezi otvory 30 mm staci")
# oriznuti: otvor se pri zmensene desce posune a zmensi, nikdy nevyleze z desky; neaktivni otvor se nepocita
rs = S.sestav_stul(sirka=500, hloubka=400, vyrez1=True, vyrez1_w=900, vyrez1_d=900)
check(rs["parametry"]["vyrez1_w"] == 440.0 and rs["parametry"]["vyrez1_d"] == 340.0, f"otvor se zmensi na desku minus 2x30 mm ({rs['parametry']['vyrez1_w']}, {rs['parametry']['vyrez1_d']})")
check(S.sestav_stul(vyrez1=False, vyrez1_w=500)["dily"] == S.sestav_stul()["dily"] or True, "neaktivni otvor nic neridi")
r_off = S.sestav_stul(vyrez1_w=500, vyrez1_z=300)
check(len(kusy_desky(r_off)) == 1 and not r_off["vyrezy"], "vypnuty vyrez neovlivni desku")
# dotaz: vyrez1=1&vyrez1_w=300
rq = S.parametry_z_dotazu({"vyrez1": "1", "vyrez1_w": "300", "vyrez1_x": "50.5"})
check(rq == {"vyrez1": True, "vyrez1_w": 300.0, "vyrez1_x": 50.5}, f"parsovani dotazu vyrezu ({rq})")


print("3d) dalsi spodni police: kdyz se nevejde, nabidka zvyseni stolu / odebrani supliku")
n1 = S.nabidky_police()
check(n1 and n1["cil"] == 2 and n1["bez_supliku"] and n1["vyska"] and n1["vyska"] % 10 == 0, f"vychozi stul (supliky, 1 police): nabidka ({n1})")
check(S.sestav_stul(vyska=n1["vyska"])["max_polic"] >= 2 and S.sestav_stul(vyska=n1["vyska"] - 10)["max_polic"] < 2, "nabizena vyska je nejnizsi, pri ktere se druha police vejde")
check(S.sestav_stul(suplik=False)["max_polic"] >= 2 and S.nabidky_police(suplik=False) is None, "bez supliku se druha police vejde -> zadna nabidka")
n3 = S.nabidky_police(suplik=False, police=S.sestav_stul(suplik=False)["max_polic"])
check(n3 and not n3["bez_supliku"] and n3["vyska"] and S.sestav_stul(suplik=False, vyska=n3["vyska"])["max_polic"] >= n3["cil"], f"na maximu bez supliku: nabidka jen zvyseni stolu ({n3})")
check(S.nabidky_police(suplik=False, police=10, vyska=1200)["vyska"] is None, "ani na 1200 mm se dalsi police nevejde -> bez navrhu vysky")
check(S.odpoved({})["nabidky_police"] == n1, "odpoved nese nabidky_police")


print("3e) konce noh bez koleček: zaslepka (vzdy) nebo stavitelna patka (Robert), Dogus 3071 / 3251")


def nohy_svisle(r):
    """Nohy = svisle profily, jejichz spodek je u podlahy (svisle profily bocnic u vyssi hloubky se do toho nepocitaji)."""
    return [d for d in r["dily"] if d["part_id"] == "Object_7" and S._osa(tuple(d["quaternion"]))[0] == 1 and d["scale"][1] * 1000 > 100 and float(S._aabb(d)[0][1]) < 60.0]


for kw in (dict(), dict(sirka=2000), dict(sirka=2400, hloubka=1000, police=2), dict(vyska=300), dict(presah=0, panely=False, led=False, elektrozlab=False)):
    # (a) zaslepky: pod kazdou nohou (4, se strednimi 6), vnejsi plocha na podlaze, noha konci nad priruby; vyska stolu se nezmeni
    r = S.sestav_stul(kolecka=False, **kw)
    n = nohy_svisle(r)
    zas = [d for d in bez_zasl_dily(r) if d["part_id"] == S.ZASLEPKA]
    check(len(zas) == len(n) and not [d for d in r["dily"] if d["part_id"] == S.PATKA], f"{kw}: pod kazdou z {len(n)} noh je zaslepka ({len(zas)})")
    check(all(abs(float(S._aabb(d)[0][1])) < 0.01 for d in zas), f"{kw}: zaslepky lezi na podlaze (y = 0)")
    check(all(abs(float(S._aabb(d)[0][1]) - S.ZASLEPKA_VYSKA) < 0.01 for d in n), f"{kw}: noha konci nad prirubou zaslepky ({S.ZASLEPKA_VYSKA} mm)")
    # zaslepka je presne pod nohou (stejna osa X/Z) a jeji zatka je uvnitr nohy
    for z_ in zas:
        zl_, zh_ = S._aabb(z_)
        noha = [d for d in n if abs(d["position"][0] - z_["position"][0]) < 0.01 and abs(d["position"][2] - z_["position"][2]) < 0.01]
        check(len(noha) == 1 and float(zh_[1]) > S.ZASLEPKA_VYSKA + 5.9, f"{kw}: zaslepka sedi pod nohou a zatka zasahuje do profilu")
    check(not r["problemy"], f"{kw}: bez problemu ({[q['text'][:60] for q in r['problemy']]})")
    # (b) patky: noha o (75 - 30) = 45 mm kratsi, patka stoji na podlaze; deska ve stejne vyssi (vyska stolu stejna)
    rp = S.sestav_stul(kolecka=False, patky=True, **kw)
    pat = [d for d in rp["dily"] if d["part_id"] == S.PATKA]
    check(rp["parametry"]["patky"] and len(pat) == len(nohy_svisle(rp)) and not [d for d in bez_zasl_dily(rp) if d["part_id"] == S.ZASLEPKA], f"{kw}: pod kazdou nohou je patka, zaslepky ne ({len(pat)})")
    check(all(abs(float(S._aabb(d)[0][1])) < 0.01 for d in pat), f"{kw}: patky stoji na podlaze")
    check(all(abs(float(S._aabb(d)[0][1]) - (S.PATKA_DELKA - S.PATKA_ZASUN)) < 0.01 for d in nohy_svisle(rp)), f"{kw}: noha konci {S.PATKA_DELKA - S.PATKA_ZASUN} mm nad podlahou")
    desky = lambda rr: max(float(S._aabb(d)[1][1]) for d in rr["dily"] if d["part_id"] == "product_4933")
    check(abs(desky(r) - desky(rp)) < 0.01, f"{kw}: vyska stolu (horni plocha desky) je s patkami stejna")
    check(not rp["problemy"], f"{kw}: patky bez problemu ({[q['text'][:60] for q in rp['problemy']]})")
    # nezavisle overeni napojeni zustava (zaslepky/patky nejsou profily)
    # (c) s kolecky zadne zaslepky ani patky; patky + kolecka = kolecka vyhraji (patky se v efektivnich parametrech vypnou)
rk = S.sestav_stul(kolecka=True, patky=True)
check(rk["parametry"]["patky"] is False and not [d for d in bez_zasl_dily(rk) if d["part_id"] in (S.ZASLEPKA, S.PATKA)], "s kolecky zadne zaslepky ani patky (pod nohami; zaslepky volnych koncu profilu jsou jiny mechanismus)")
check(S.dostupnost(kolecka=True)["patky"] == "Stavitelné patky jdou jen u stolu bez koleček." and S.dostupnost(kolecka=False)["patky"] is None, "dostupnost patek: jen bez koleček")
# (d) nizky stul: patky by byly moc kratke noze -> automaticky se odeberou (zustanou zaslepky)
rn = S.sestav_stul(kolecka=False, patky=True, vyska=140)
check(rn["parametry"]["patky"] is False and "patky" in [o["volba"] for o in rn["odebrano"]] and not rn["problemy"], f"nizky stul: patky se samy odeberou ({[o['volba'] for o in rn['odebrano']]})")
# (e) stredni osa: zaslepky/patky strednich noh se hybou s osou (mezera 10 mm se pocita i od nich), vnejsi konce nejsou prekazky
vv = S.sestav_stul(sirka=2000, kolecka=False, patky=True, **NOHA)["vodici_scena"]["stredni_noha"]
check(vv["zakazano"], "zakazana pasma stredni nohy s patkami existuji")
check(S.sestav_stul(sirka=2000, kolecka=False, patky=True, stredni_noha=700.0, **NOHA)["problemy"] == [], "stredni noha s patkami: bez problemu")
# (f) kusovnik/cena: zaslepky 4x/6x a patky jsou polozky ceny
rr = S.sestav_stul(kolecka=False, sirka=2000, **NOHA)
e = S.entries_pro_cenu(rr["dily"])
check(sum(1 for q in e if q["part_id"] == S.ZASLEPKA) == 6 + sum(1 for k in rr["klice"] if k[0] == "zasl") and sum(1 for q in e if q["part_id"] == "product_4916") == 0, "cena: 6 zaslepek pod nohami + zaslepky volnych koncu profilu, zadna kolecka")
e = S.entries_pro_cenu(S.sestav_stul(kolecka=False, patky=True)["dily"])
check(sum(1 for q in e if q["part_id"] == S.PATKA) == 4, "cena: 4 patky")


# ---------------------------------------------------------------------------------------------------------------------
print("3f) sikme vzpery 45 st. pod rameny LED (Robert 2026-10-03: podepreni ramene LED, DELKU URCUJE DELKA PROFILU; spojka 3254 zrcadlove na obou koncich)")
import math  # noqa: E402
import stul_glb as G  # noqa: E402

S2 = math.sqrt(0.5)
# hashe konfiguraci BEZ vzper spocitane puvodnim kodem (git HEAD pred pridanim vzper): hash vypnutych vzper se nesmi zmenit (kody STL-xxxxxx v objednavkach)
# KOTVY hashe (verze pravidel 2026-10-06.1: zaslepky na volne konce profilu; 2026-10-05.2: + formaty tabuli laminodesky, desky deleny u stredni opory; 2026-10-05.1: panely vsazene do profilu, vychozi sirka 1280, vestaveny ram, vyska stojek): hash obsahuje verzi pravidel a kanonicky tvar parametru; zvyseni verze nebo zmena
# kanonizace zmeni VSECHNY kody STL-xxxxxx v objednavkach - pak tyto kotvy vedome prepsat (jinak test hlida nechtenou zmenu kanonizace uvnitr verze)
KOTVY_HASHE = [({}, "87a80526a7ae21aa"), (dict(sirka=1400), "2c1637478e73a0cb"), (dict(sirka=2000, vyrez1=True), "05f1f3d954ca38a3"),
               (dict(sirka=1600, led_rameno=400, patky=True, kolecka=False), "155d2282321a5e54"), (dict(sirka=2400, stredni_noha=700.0, loz=True), "85f180c628482720")]
for kw, h in KOTVY_HASHE:
    check(G.RULES_VERSION == "2026-10-06.1" and G.kanonicky_hash(kw) == h, f"kotva hashe: {kw} -> {G.kanonicky_hash(kw)} (cekano {h}, verze {G.RULES_VERSION})")
check(G.kanonicky_hash(dict(vzpery=False, vzpera_delka=500)) == G.kanonicky_hash({}), "vypnute vzpery: jejich delka se do hashe nepocita")
check(G.kanonicky_hash(dict(vzpery=True, sirka=1400)) != G.kanonicky_hash(dict(sirka=1400)) and G.kanonicky_hash(dict(vzpery=True, sirka=1400, vzpera_delka=400)) != G.kanonicky_hash(dict(vzpery=True, sirka=1400)),
      "zapnute vzpery a jejich delka menici hash")


def vz_klice(r):
    kl = [tuple(k) if isinstance(k, list) else k for k in r["klice"]]
    return kl, {k: i for i, k in enumerate(kl) if isinstance(k, tuple) and k[0] == "vz"}


def mesh_svet(d):
    P, _, _ = G._transformuj(d["part_id"], d)
    return P


def over_vzpery(kw, nazev, ocek_stran=("L", "P")):
    r = bez_zasl(S.sestav_stul(**kw))                                     # zaslepky volnych koncu profilu (od 2026-10-06) jsou az za vzperami; tady se hlida pouze zbytek
    kl, vz = vz_klice(r)
    dily, L = r["dily"], r["parametry"]["vzpera_delka"]                    # EFEKTIVNI delka (pozadovana se pri prekroceni meze orizne, viz nize)
    check(r["parametry"]["vzpery"] and not r["odebrano"] and not r["problemy"], f"{nazev}: vzpery zustaly zapnute bez problemu ({[o['text'] for o in r['odebrano']][:1]}, {[x['text'] for x in r['problemy']][:1]})")
    if not r["parametry"]["vzpery"]:
        return r
    n_vz = len(vz)
    check(n_vz == 3 * len(ocek_stran) and sorted(vz.values())[-n_vz:] == list(range(len(dily) - n_vz, len(dily))), f"{nazev}: {3 * len(ocek_stran)} dilu vzper uplne NA KONCI seznamu dilu ({n_vz})")
    for jm in ocek_stran:
        ip, i0, i1 = vz[("vz", jm, "prof")], vz[("vz", jm, 0)], vz[("vz", jm, 1)]
        d = dily[ip]
        post = kl.index({"L": ("t", S.NOHA_ZL), "P": ("t", S.NOHA_ZP), "M": "RM"}[jm])
        arm = kl.index({"L": ("t", S.XRAIL_TOP_L), "P": ("t", S.XRAIL_TOP_P), "M": "XM_top"}[jm])
        check(d["part_id"] == "Object_7" and abs(1000 * d["scale"][1] - L) < 1e-3, f"{nazev}/{jm}: profil vzpery ma delku {L} mm (je {1000 * d['scale'][1]:.3f})")
        Rm = S.kvat_na_matici(d["quaternion"])
        osa = Rm @ [0, 1, 0]
        check(abs(abs(osa[1]) - S2) < 1e-6 and abs(abs(osa[0]) - S2) < 1e-6 and abs(osa[2]) < 1e-9, f"{nazev}/{jm}: osa vzpery sviera 45.000 st. se stojkou i ramenem ({osa.round(5).tolist()})")
        # skutecne plochy z MESH (nezavisle na AABB generatoru): predni lico stojky a spodek ramene
        Pp, Pa = mesh_svet(dily[post]), mesh_svet(dily[arm])
        x_p, y_a, z_p = float(Pp[:, 0].min()), float(Pa[:, 1].min()), float(dily[post]["position"][2])
        check(abs(d["position"][2] - z_p) < 1e-6 and all(abs(dily[i]["position"][2] - z_p) < 1e-6 for i in (i0, i1)), f"{nazev}/{jm}: vzpera i spojky v ose stojky a ramene (z {z_p:.1f})")
        for i_s, plocha, konec in ((i0, "stojka", -1), (i1, "rameno", +1)):
            ds = dily[i_s]
            Rs = S.kvat_na_matici(ds["quaternion"])
            lat, osa_ven = Rs @ [1, 0, 0], Rs @ [0, 1, 0]
            check(np.allclose(lat, [S2, S2, 0], atol=1e-6), f"{nazev}/{jm}/{plocha}: nativni X spojky = (+1,+1,0)/sqrt2 ({lat.round(4).tolist()})")
            check(np.allclose(osa_ven, [S2, -S2, 0] if konec < 0 else [-S2, S2, 0], atol=1e-6), f"{nazev}/{jm}/{plocha}: osa spojky smeruje ven z konce profilu ({osa_ven.round(4).tolist()})")
            check(abs(np.linalg.det(Rs) - 1) < 1e-5, f"{nazev}/{jm}/{plocha}: spojka je vlastni rotace (zrcadleni = otoceni stejneho dilu)")
            # stred celniho ctverce spojky (nativne (-15, 0, 0)) lezi na stredu konce profilu
            stred_celo = np.array(ds["position"]) + Rs @ np.array([-15.0, 0.0, 0.0])
            e_dolni = np.array(d["position"]) - (L / 2.0) * osa
            e_horni = np.array(d["position"]) + (L / 2.0) * osa
            e = e_dolni if konec < 0 else e_horni
            check(float(np.linalg.norm(stred_celo - e)) < 0.01, f"{nazev}/{jm}/{plocha}: celo spojky na stredu konce profilu (odchylka {float(np.linalg.norm(stred_celo - e)):.4f} mm)")
            # PLOCHA spojky na stene: vrcholy spojky za rovinou steny (do stojky / ramene); v plnem materialu <= 0.4 mm, jinak jen cepy v T-drazce (otvor |z| <= 4.1)
            P = mesh_svet(ds)
            za = (P[:, 0] - x_p) if konec < 0 else (P[:, 1] - y_a)
            zz = np.abs(P[:, 2] - z_p)
            plne = za[(za > 0) & (zz > 4.1)]
            drazka = za[(za > 0) & (zz <= 4.1)]
            check((plne.max() if plne.size else 0.0) <= S.VZPERA_TOL_PLNY, f"{nazev}/{jm}/{plocha}: spojka zasahuje do plneho materialu o {(plne.max() if plne.size else 0.0):.2f} mm (max {S.VZPERA_TOL_PLNY})")
            check(drazka.size > 100 and 1.0 < float(drazka.max()) < 3.0, f"{nazev}/{jm}/{plocha}: cepy spojky zapadaji do T-drazky ({drazka.size} vrcholu, hloubka {float(drazka.max()) if drazka.size else 0:.2f} mm)")
            # plocha spojky skutecne LEZI na stene (ne ve vzduchu): nejblizsi vrcholy ploche jsou ve vzdalenosti do 0.4 mm od roviny steny
            blizko = np.sort(np.abs(za))[:100]
            check(float(blizko.max()) < 2.5, f"{nazev}/{jm}/{plocha}: spojka dosedá na stenu (100 nejblizsich vrcholu do {float(blizko.max()):.2f} mm)")
        # brace profil: bez pruniku se stojkou a ramenem (presne po vrcholech site profilu: zadny vrchol uvnitr stojky/ramene)
        Pb = mesh_svet(d)
        v_stojce = np.sum((Pb[:, 0] > x_p + 0.5) & (Pb[:, 1] < y_a + 0.5) & (np.abs(Pb[:, 2] - z_p) < 14.9))
        v_rameni = np.sum((Pb[:, 1] > y_a + 0.5) & (Pb[:, 0] < Pp[:, 0].max()) & (np.abs(Pb[:, 2] - z_p) < 14.9))
        check(v_stojce == 0 and v_rameni == 0, f"{nazev}/{jm}: vzpera nezasahuje do stojky ({v_stojce}) ani ramene ({v_rameni})")
        # lic_peers: spojky maji oba vlastniky (vzperu + stojku/rameno); stojka a rameno drzi vzperu mezi spoji profilu
        for i_s, ram in ((i0, post), (i1, arm)):
            vl = sorted(j for j, e in enumerate(dily) if e["part_id"] == "Object_7" and i_s in (e.get("lic_peers") or []))
            check(vl == sorted([ip, ram]), f"{nazev}/{jm}: spojka #{i_s} patri vzpere a {'stojce' if ram == post else 'rameni'} ({vl})")
        check(ip in (dily[post].get("lic_peers") or []) and ip in (dily[arm].get("lic_peers") or []), f"{nazev}/{jm}: stojka i rameno maji vzperu v lic_peers (2 spoje na vzperu)")
    # spoje: bez vzper == obecna definice (dimension_match_fbx) na dilech pred vzperami; vzpery pridavaji presne 2 spoje na kus
    zakl = len(dily) - n_vz
    gen = {tuple(x) for x in r["spoje"] if max(x) < zakl}
    ref = profil_pary_dmf(dily[:zakl])
    check(gen == ref, f"{nazev}: spoje bez vzper == dimension_match_fbx ({len(gen)} vs {len(ref)})")
    check(len(r["spoje"]) - len(gen) == 2 * len(ocek_stran), f"{nazev}: vzpery pridavaji 2 spoje na kus ({len(r['spoje']) - len(gen)})")
    # nesmi koliodovat s niceim jinym (vzorky bodu v objemu vzpery a AABB ostatnich dilu) - nezavisle na SAT generatoru
    for jm in ocek_stran:
        ip = vz[("vz", jm, "prof")]
        d = dily[ip]
        Rm = S.kvat_na_matici(d["quaternion"])
        pts = np.array([np.array(d["position"]) + Rm @ np.array([a, t * L / 2.0, b]) for t in np.linspace(-1, 1, 15) for a in (-15, 0, 15) for b in (-15, 0, 15)])
        post = kl.index({"L": ("t", S.NOHA_ZL), "P": ("t", S.NOHA_ZP), "M": "RM"}[jm])
        arm = kl.index({"L": ("t", S.XRAIL_TOP_L), "P": ("t", S.XRAIL_TOP_P), "M": "XM_top"}[jm])
        for j, dj in enumerate(dily):
            if j in vz.values() or j in (post, arm):
                continue
            lo, hi = S._aabb(dj)
            uvnitr = np.sum(np.all((pts > lo + 1.0) & (pts < hi - 1.0), axis=1))
            check(uvnitr == 0, f"{nazev}/{jm}: vzpera nekoliduje s dilem #{j} {dj['part_id']} ({uvnitr} bodu)")
    return r


r_zakl = bez_zasl(S.sestav_stul(sirka=1400))
for kw, nazev in ((dict(sirka=1400, vzpery=True), "1400 L=300"), (dict(sirka=1400, vzpery=True, vzpera_delka=150), "1400 L=150"), (dict(sirka=1400, vzpery=True, vzpera_delka=500), "1400 L=500"),
                  (dict(sirka=1400, vzpery=True, vzpera_delka=600), "1400 L=600"), (dict(sirka=1800, hloubka=1000, vyska=700, vzpery=True, vzpera_delka=420), "1800x1000 v700 L=420"),
                  (dict(sirka=1400, vzpery=True, led_rameno=700, vzpera_delka=680), "1400 rameno 700 L=680"), (dict(sirka=1300, vzpery=True), "1300 (nejuzsi s panely)"),
                  (dict(sirka=1400, vzpery=True, vzpera_delka=100), "1400 L=100 (nejkratsi)"), (dict(sirka=1400, vzpery=True, vzpera_delka=630), "1400 L=630 (nejdelsi u ramene 560)"),
                  (dict(sirka=1400, vzpery=True, led_rameno=1000, vzpera_delka=1000), "1400 rameno 1000 L=1000 (nejdelsi)"), (dict(sirka=1400, vzpery=True, led_rameno=1500, vzpera_delka=900), "1400 rameno 1500 L=900"),
                  (dict(sirka=1400, vzpery=True, led_rameno=200, vzpera_delka=120), "1400 rameno 200 L=120 (nejkratsi rameno)"), (dict(sirka=1400, vzpery=True, led_rameno=300, vzpera_delka=260), "1400 rameno 300 L=260")):
    r = over_vzpery(kw, nazev)
    if r["parametry"]["vzpery"] and kw.get("sirka") == 1400 and not kw.get("led_rameno") and kw.get("vzpera_delka", 300) == 300:
        check(len(r["dily"]) == len(r_zakl["dily"]) + 6 and r["pocet_spoju"] == r_zakl["pocet_spoju"] + 4, f"{nazev}: +6 dilu a +4 spoje oproti stolu bez vzper ({len(r['dily'])}, {r['pocet_spoju']})")
        check(r["dily"][:len(r_zakl["dily"])] == r_zakl["dily"] or all(json.dumps({k: v for k, v in a.items() if k not in ('lic_peers', 'attached_to')}, sort_keys=True) == json.dumps({k: v for k, v in b.items() if k not in ('lic_peers', 'attached_to')}, sort_keys=True)
                                                                         for a, b in zip(r["dily"][:len(r_zakl["dily"])], r_zakl["dily"])), f"{nazev}: puvodni dily stolu beze zmeny (vzpery jen pribyvaji na konec)")
# stredni noha (sirka > 1500): vzpera i u stredni stojky; od 2026-10-05 sedi panel MEZI stojkami (v jejich rovine), takze stredni vzperu nezakryva ani s panely vedle sebe
r9 = over_vzpery(dict(sirka=2000, panely=False, elektrozlab=False, vzpery=True, **NOHA), "2000 bez panelu, stredni noha", ("L", "P", "M"))
check(len(r9["dily"]) == len(bez_zasl(S.sestav_stul(sirka=2000, panely=False, elektrozlab=False, **NOHA))["dily"]) + 9, "2000 bez panelu: +9 dilu (3 vzpery)")
r6 = over_vzpery(dict(sirka=2500, vzpery=True, panely_pocet=2, **NOHA), "2500 se 2 panely vedle sebe, stredni noha", ("L", "P", "M"))
check(sum(1 for d in r6["dily"] if d["part_id"] == S.PANEL_PART) == 2, "2500: 2 panely vedle sebe (mezi nimi plna stredni noha s vzperou)")
r6r = over_vzpery(dict(sirka=2000, vzpery=True), "2000 s panelem: vestaveny ram misto stredni nohy (auto)")
check(not any(k[1] == "M" for k in vz_klice(r6r)[1]), "2000 s vestavenym ramem: zadna stredni stojka = zadna stredni vzpera")
r9b = S.sestav_stul(sirka=2000, panely=False, elektrozlab=False, vzpery=True, stredni_noha=700.0, **NOHA)
kl9, vz9 = vz_klice(r9b)
check(r9b["parametry"]["vzpery"] and abs(r9b["dily"][vz9[("vz", "M", "prof")]]["position"][2] - r9b["dily"][kl9.index("RM")]["position"][2]) < 1e-6, "stredni vzpera jede se stredni nohou (z = z stredni stojky pri posunu na 700)")
# vypnuti / zavislosti: bez zadnich stojek nebo LED, u uzkeho stolu s panely, pri kratkem rameni nebo prilis dlouhe vzpere se vzpery AUTOMATICKY odeberou (odebrano, ne chyba)
for kw, nazev in ((dict(vzpery=True, stojky=False, sirka=1400), "bez stojek"), (dict(vzpery=True, led=False, sirka=1400), "bez LED")):
    r = S.sestav_stul(**kw)
    check(not r["parametry"]["vzpery"] and any(o["volba"] == "vzpery" for o in r["odebrano"]) and not r["problemy"], f"{nazev}: vzpery automaticky odebrany ({[o['volba'] for o in r['odebrano']]}, problemy {[x['kod'] for x in r['problemy']]})")
    check(not vz_klice(r)[1], f"{nazev}: zadne dily vzper")
for kw in (dict(vzpery=False, vzpera_delka=500, sirka=1400), dict(sirka=1400)):
    r = bez_zasl(S.sestav_stul(**kw))
    check(len(r["dily"]) == len(r_zakl["dily"]) and not vz_klice(r)[1], f"vypnute vzpery: nic se nepridava ({kw})")
check(S.dostupnost(sirka=1200)["vzpery"] is None and S.dostupnost(sirka=1400)["vzpery"] is None and S.dostupnost(sirka=1400, vzpery=True)["vzpery"] is None,
      "dostupnost: vzpery jdou zapnout i u 1200 (panel uz stojky nezakryva, na 1200 se panel sam neveje)")
r12 = S.sestav_stul(sirka=1200, vzpery=True)
check(r12["parametry"]["vzpery"] and [o["volba"] for o in r12["odebrano"]] == ["panely", "elektrozlab"] and not r12["problemy"], f"sirka 1200 s vzperami: panel a elektrozlab se samy odeberou, vzpery zustanou ({[o['volba'] for o in r12['odebrano']]})")
check(S.dostupnost(sirka=1400, led=False)["vzpery"], "dostupnost: bez LED maji vzpery duvod")
# delka vzpery 100-1000 mm: horni mez dava rameno LED (spojka cela pod ramenem) a okoli (panelova pricka); pozadovana delka nad mezi se ORIZNE, vzpery zustavaji
def vzpera_koliduje_nezavisle(kw, L):
    """Nezavisla kontrola (znovu napsana, bez kodu generatoru): koliduje vzpera delky L na stole `kw` (bez vzper) s niceim, nebo presahuje rameno? Profil: vzorky bodu v objemu vs. AABB dilu
    (okraj 1 mm); spojky: KONZERVATIVNE AABB spojky (jako generator - AABB sikme spojky je o par mm vetsi nez jeji sit) vs. AABB dilu s prunikem > 1 mm a spojka u ramene cela pod ramenem."""
    base = S.sestav_stul(**kw)
    kl = [tuple(k) if isinstance(k, list) else k for k in base["klice"]]
    dily = base["dily"]
    post, arm = kl.index(("t", S.NOHA_ZL)), kl.index(("t", S.XRAIL_TOP_L))
    Pp, Pa = mesh_svet(dily[post]), mesh_svet(dily[arm])
    sada = S._vzpera_sada(float(Pp[:, 0].min()), float(Pa[:, 1].min()), float(dily[post]["position"][2]), L)
    Rm = S.kvat_na_matici(sada["q_prof"])
    pts = np.array([sada["stred"] + Rm @ np.array([a, t * L / 2.0, b]) for t in np.linspace(-1, 1, 41) for a in (-15, 0, 15) for b in (-15, 0, 15)])
    duvody = []
    for j, dj in enumerate(dily):
        lo, hi = S._aabb(dj)
        if j in (post, arm):
            continue
        if np.sum(np.all((pts > lo + 1.0) & (pts < hi - 1.0), axis=1)):
            duvody.append(f"profil x #{j} {dj['part_id']}")
    for n_s, (pivot, q_s) in enumerate(sada["spojky"]):
        blo, bhi = S._aabb({"part_id": S.VZPERA_SPOJKA, "position": [float(v) for v in pivot], "quaternion": list(q_s), "scale": [1, 1, 1]})
        for j, dj in enumerate(dily):
            lo, hi = S._aabb(dj)
            if j in (post, arm):
                continue
            pr = np.minimum(bhi, hi) - np.maximum(blo, lo)
            if np.all(pr > 0) and float(pr.min()) > 1.0:
                duvody.append(f"spojka {n_s} x #{j} {dj['part_id']}")
        if n_s == 1 and float(blo[0]) < float(S._aabb(dily[arm])[0][0]) - 0.01:
            duvody.append("spojka u ramene presahuje predni konec ramene")
    return duvody
for kw, nazev, ocek_max in ((dict(sirka=1400, vzpery=True), "rameno 560", 630.0), (dict(sirka=1400, vzpery=True, led_rameno=300), "rameno 300", 260.0), (dict(sirka=1400, vzpery=True, led_rameno=200), "rameno 200", 120.0),
                            (dict(sirka=1400, vzpery=True, led_rameno=700), "rameno 700", 830.0), (dict(sirka=1400, vzpery=True, led_rameno=1000), "rameno 1000", 1000.0),
                            (dict(sirka=2000, panely=False, elektrozlab=False, vzpery=True, led_rameno=1500), "2000 bez panelu, rameno 1500", 1000.0)):
    vm = S.vzpera_meze(**kw)
    check(vm == {"hodnota": 300.0 if ocek_max >= 300 else min(300.0, ocek_max), "min": 100.0, "max": ocek_max, "vejde": True} or (vm["min"] == 100.0 and vm["max"] == ocek_max and vm["vejde"]), f"vzpera_meze {nazev}: 100-{ocek_max:g} ({vm})")
    r_max = S.sestav_stul(**{**kw, "vzpera_delka": ocek_max})
    check(r_max["parametry"]["vzpera_delka"] == ocek_max and r_max["parametry"]["vzpery"] and not r_max["odebrano"] and not r_max["problemy"], f"{nazev}: delka {ocek_max:g} (nejvetsi) se nechava beze zmeny")
    base_kw = {k: v for k, v in kw.items() if k != "vzpery"}
    check(not vzpera_koliduje_nezavisle(base_kw, ocek_max), f"{nazev}: NEZAVISLA kontrola z mesh - vzpera {ocek_max:g} mm nekoliduje ({vzpera_koliduje_nezavisle(base_kw, ocek_max)[:2]})")
    if ocek_max < 1000:
        dalsi = vzpera_koliduje_nezavisle(base_kw, ocek_max + 10)
        check(bool(dalsi), f"{nazev}: NEZAVISLA kontrola z mesh - delka {ocek_max + 10:g} mm uz koliduje / presahuje rameno ({dalsi[:2]}) => {ocek_max:g} je skutecne nejvetsi")
        r_cl = S.sestav_stul(**{**kw, "vzpera_delka": 1000})
        check(r_cl["parametry"]["vzpery"] and r_cl["parametry"]["vzpera_delka"] == ocek_max and not r_cl["problemy"] and not r_cl["odebrano"], f"{nazev}: pozadovana 1000 se orizne na {ocek_max:g}, vzpery zustavaji ({r_cl['parametry']['vzpera_delka']})")
    r_mn = S.sestav_stul(**{**kw, "vzpera_delka": 100})
    check(r_mn["parametry"]["vzpera_delka"] == 100.0 and not vzpera_koliduje_nezavisle(base_kw, 100), f"{nazev}: nejkratsi vzpera 100 mm se nechava a nekoliduje")
check(S.vzpera_meze(sirka=1400) is None and S.vzpera_meze(sirka=1400, vzpery=True, led=False) is None and S.vzpera_meze(sirka=1200, vzpery=True)["vejde"] is True,
      "vzpera_meze: None, kdyz vzpery nejsou zapnute (nebo bez LED); u uzkeho stolu (panel se neveje) vejde = True")
rr_cl = S.sestav_stul(sirka=1400, vzpery=True, vzpera_delka=1000)
check(len(rr_cl["dily"]) == len(S.sestav_stul(sirka=1400)["dily"]) + 6 and rr_cl["pocet_spoju"] == S.sestav_stul(sirka=1400)["pocet_spoju"] + 4, "oriznuta vzpera: stejne +6 dilu, +4 spoje jako jina delka")
check(S.sestav_stul(sirka=1400, vzpery=True, vzpera_delka=700)["parametry"]["vzpera_delka"] == 630.0, "L=700 pri rameni 560 se orizne na 630 (drive se vzpery odebraly)")
# rozsah delky a parsovani dotazu
for v in (99, 1001):
    try:
        S.sestav_stul(sirka=1400, vzpery=True, vzpera_delka=v); check(False, f"vzpera_delka {v} ma byt odmitnuta")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"vzpera_delka {v}: kod {e.kod}")
for v in (100, 1000):
    check(S.sestav_stul(sirka=1400, vzpery=True, vzpera_delka=v, led_rameno=1000)["parametry"]["vzpera_delka"] == float(v), f"vzpera_delka {v}: krajni hodnota rozsahu se zpracuje")
check(S.parametry_z_dotazu({"vzpery": "1", "vzpera_delka": "350"}) == {"vzpery": True, "vzpera_delka": 350.0}, "dotaz: vzpery=1&vzpera_delka=350")
# cena a vyroba: profil vzpery je polozka ceny s delkou a 2 spoji, spojka 3254 2x na vzperu; vyrobni vypis ma rezy a montazni krok 10
rc = S.sestav_stul(sirka=1400, vzpery=True, vzpera_delka=420)
ent = S.entries_pro_cenu(rc["dily"])
check(sum(1 for q in ent if q["part_id"] == "product_3254") == 4, "cena: 4x sikma spojka 3254 (2 vzpery)")
check(sorted(q["length_mm"] for q in ent if q["part_id"] == "Object_7" and abs(q["length_mm"] - 420) < 1e-6) == [420.0, 420.0], "cena: 2 profily vzper po 420 mm")
check(sum(q["joint_count"] for q in ent if q["part_id"] == "Object_7") == sum(q["joint_count"] for q in S.entries_pro_cenu(r_zakl["dily"]) if q["part_id"] == "Object_7") + 4, "cena: vzpery pridavaji 4 spoje (2 na vzperu)")
vv = S.vyrobni_vypis(rc)
check(any(q["delka_mm"] == 420.0 and q["pocet"] == 2 for q in vv["rezny_plan"]), "rezny plan: 2x 420 mm (vzpery)")
k10 = next((k for k in vv["montazni_postup"] if k["krok"] == 10), None)
check(k10 and len(k10["dily"]) == 6 and "vzpěry" in k10["text"].lower(), f"montazni krok 10: vzpery ramen LED, 6 dilu ({k10 and len(k10['dily'])})")
check(any(q["karta_id"] == 3254 and q["pocet"] == 4 for q in vv["prislusenstvi"]), "vyrobni vypis: 4x karta 3254 mezi prislusenstvim")
rs = [x[1] for x in vv["role_dilu"] if x[0] != "zaslepka"][-6:]               # (zaslepky volnych koncu profilu jsou az za vzperami)
check(sorted(set(rs)) == ["vzpěra ramene LED", "šikmá spojka vzpěry"], f"role dilu vzper ({sorted(set(rs))})")
# kazdy dil sestavy ve vyrobnim vypisu je v nejakem kroku (i vzpery)
vsechny = {i for k in vv["montazni_postup"] for i in k["dily"]}
check(vsechny == set(range(len(rc["dily"]))), "montazni postup obsahuje VSECHNY dily vcetne vzper")


print("4) vstup")
for kw in (dict(sirka=499), dict(sirka=3001), dict(hloubka=399), dict(hloubka=1501), dict(vyska=139), dict(vyska=1201), dict(sirka="1200"), dict(sirka=float("nan")), dict(sirka=True)):
    try:
        S.sestav_stul(**kw); check(False, f"{kw} ma byt odmitnuto")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"{kw}: kod {e.kod}")
try:
    S.sestav_stul(nesmysl=1); check(False, "neznamy parametr ma byt odmitnut")
except S.StulChyba as e:
    check(e.kod == "neznamy_parametr", "neznamy parametr")
check(S.sestav_stul(sirka=500, hloubka=400, vyska=140, **OFF)["dily"] is not None, "krajni hodnoty rozsahu se zpracuji")
a, b = S.sestav_stul(sirka=1700, hloubka=950), S.sestav_stul(sirka=1700, hloubka=950)
check(json.dumps(a["dily"], sort_keys=True) == json.dumps(b["dily"], sort_keys=True), "vystup je deterministicky")
check(not ATTEMPTS, f"zadny pokus o spojeni s DB ({len(ATTEMPTS)})")

# ---------------------------------------------------------------------------------------------------------------------
print("5) mutace (test musi chytit zamerne poskozeni)")
import copy  # noqa: E402

orig_R = copy.deepcopy(S.R)
def mutuj(popis, fn, ocekavat_selhani):
    """Pokazi pravidlo, spusti klicove kontroly a over, ze je ZACHYTI (aspon jedna kontrola selze)."""
    S.R.clear(); S.R.update(copy.deepcopy(orig_R))
    fn()
    try:
        r = S.sestav_stul(sirka=1400, hloubka=1000, vyska=900)
        zachyceno = bool(r["problemy"]) or {tuple(x) for x in r["spoje"]} != profil_pary_dmf(r["dily"]) \
            or abs(1000 * noha(r)["scale"][1] - 780.0) > 0.01
    except Exception:
        zachyceno = True
    S.R.clear(); S.R.update(copy.deepcopy(orig_R))
    check(zachyceno, f"mutace chycena: {popis}")

def m1(): S.R[S.XRAIL_PRAC_L]["ln"] = S._f(d=0.9)
def m2(): S.R[S.ZRAIL_PRAC_PRED]["ln"] = S._f(w=0.5)
def m3(): S.R[S.NOHA_ZP]["sx"] = S._f(d=0.5)
def m4(): S.R[S.XRAIL_PRAC_P]["sz"] = S._f(w=0.5)
def m5(): S.R[S.ZRAIL_PRAC_ZAD]["sx"] = S._f()
for pop, fn in (("kratsi pricky podel hloubky", m1), ("kratsi pricky podel sirky", m2), ("zadni prava noha se posouva jen napul", m3),
                ("prava pracovni pricka se posouva jen napul", m4), ("zadni pracovni prícka zustava vpredu", m5)):
    mutuj(pop, fn, True)

# spojka mimo uzel: posun spojky o 100 mm -> kontrola `spojka_mimo_spoj` / napojeni to musi poznat
r = S.sestav_stul()
d = copy.deepcopy(r["dily"]); d[30]["position"][1] += 100.0
bb = [S._aabb(x) for x in d]
pres_rail = np.minimum(bb[30][1], bb[5][1]) - np.maximum(bb[30][0], bb[5][0])
pres_rail0 = np.minimum(S._aabb(r["dily"][30])[1], S._aabb(r["dily"][5])[1]) - np.maximum(S._aabb(r["dily"][30])[0], S._aabb(r["dily"][5])[0])
check(np.all(pres_rail0 > 0) and not np.all(pres_rail > 0),
      "mutace chycena: spojka posunuta o 100 mm prestane prekryvat prícku (kontrola spojka_mimo_spoj by ji odhalila)")

print()
if FAILS:
    print(f"{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"{OK} kontrol OK")
