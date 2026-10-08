#!/usr/bin/env python3
"""Test loziskovych (kulickovych) jednotek na pracovni desce (bot8, 2026-10-02): karta 3025 'Kulickova jednotka 15mm - 20kg' (Kola Pirkl).

Robert: uzivatel zada rozteč a vzdalenost od okraje desky -> mrizka jednotek (jejich pocet z toho vyplyva); jednotky v miste otvoru (vyrezu)
se vynechavaji. Hlida: pocet a poloha podle nezavisleho vzorce, rozestupy, jednotky lezi NA desce a nic neprotinaji, vynechani u otvoru, strop
poctu, rozsahy a parsovani dotazu, cena (entries), GLB (chromovy material, procedural tvar).

Cista funkce nad generatorem (bez DB). Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_loz.py  (STUL_API_OVERRIDE = jina kopie api/)
Vystup 'N kontrol OK', exit 0.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")
sys.path.insert(0, API)
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
        print(f"  CHYBA: {msg}")


LOZ = "product_3025"


def jednotky(r):
    return [d for d in r["dily"] if d["part_id"] == LOZ]


def deska_rect(r):
    kusy = [d for d in r["dily"] if d["part_id"] == "product_4933" and d["position"][1] > 600]
    bbs = [S._aabb(d) for d in kusy]
    return (min(float(b[0][0]) for b in bbs), max(float(b[1][0]) for b in bbs), min(float(b[0][2]) for b in bbs), max(float(b[1][2]) for b in bbs),
            max(float(b[1][1]) for b in bbs))


def pocet_osa(delka, okraj, rozteca):
    d = delka - 2 * okraj
    return 0 if d < -0.05 else int((d + 0.05) // rozteca) + 1


print("1) vypnuto = zadne jednotky, zlaty test beze zmeny")
r0 = S.sestav_stul()
check(not jednotky(r0) and r0["loz"] is None, "vychozi stul nema loziskove jednotky")
sab = S.sablona()
r_z = S.sestav_stul(sirka=1200, panely=False)          # sablona #577 bez panelovych dilu (panely jsou od 2026-10-05 vsazene do profilu, viz test_stul_konfigurator.py, zlaty test)
r_z = {**r_z, "dily": [d for d, k in zip(r_z["dily"], r_z["klice"]) if k[0] != "zasl"], "klice": [k for k in r_z["klice"] if k[0] != "zasl"]}          # bez zaslepek volnych koncu (od 2026-10-06; v sablone nejsou)
check(len(r_z["dily"]) == 44 and all(k[0] in ("t", "s") and np.abs(np.array(sab[k[1]][f]) - np.array(d[f])).max() < 0.01 for k, d in zip(r_z["klice"], r_z["dily"]) for f in ("position", "scale", "quaternion")),
      "zlaty test (#577 bez panelu) beze zmeny")

print("2) mrizka: pocet a poloha podle nezavisleho vzorce")
for kw in (dict(), dict(loz_rozteca=150, loz_okraj=60), dict(sirka=2000, hloubka=1000, loz_rozteca=300, loz_okraj=60), dict(sirka=700, hloubka=500, loz_rozteca=100, loz_okraj=50),
           dict(sirka=1200, hloubka=800, loz_rozteca=250, loz_okraj=110), dict(sirka=3000, hloubka=1500, loz_rozteca=300, loz_okraj=100), dict(presah=100, loz_okraj=40)):
    r = S.sestav_stul(loz=True, **kw)
    p = r["parametry"]
    X0, X1, Z0, Z1, y = deska_rect(r)
    nx, nz = pocet_osa(X1 - X0, p["loz_okraj"], p["loz_rozteca"]), pocet_osa(Z1 - Z0, p["loz_okraj"], p["loz_rozteca"])
    ju = jednotky(r)
    # stul nad prahem sirky: pracovni deska je u stredni nohy DELENA na dve desky (Robert 2026-10-05, formaty tabuli) - jednotka se nevrta pres delici spáru: vynecha se, kdyz jeji
    # ctverec (r = 17 mm) zasahuje do spáry +- 2 mm (jako u vyrezu); mrizka (radku x sloupcu) zustava, jen chybi jednotky u spáry. Spára je ve stredu stolu (stredni_noha = None).
    r_j_ = S.LOZ_PRUMER / 2.0
    delka_z = (Z1 - Z0) - 2 * p["loz_okraj"]
    z0_mriz = Z0 + p["loz_okraj"] + (delka_z - (nz - 1) * p["loz_rozteca"]) / 2.0 if nz else 0.0
    zs_mriz = [z0_mriz + k * p["loz_rozteca"] for k in range(nz)]
    spara = (Z0 + Z1) / 2.0 if p["sirka"] > S.prah_sirky() else None
    vynech_z = [z for z in zs_mriz if spara is not None and abs(z - spara) < r_j_ + S.LOZ_MEZERA_OTVOR - 1e-6]
    n_ocek = nx * (nz - len(vynech_z))
    check(len(ju) == n_ocek and r["loz"]["pocet"] == n_ocek and (r["loz"]["radku"], r["loz"]["sloupcu"]) == (nx, nz), f"{kw}: pocet jednotek {len(ju)} = {nx} x {nz} (bez {len(vynech_z)} sloupcu u spáry)")
    xs, zs = sorted({round(d["position"][0], 1) for d in ju}), sorted({round(d["position"][2], 1) for d in ju})
    zs_vse = sorted(zs + [round(z, 1) for z in vynech_z])                                         # mrizka vcetne sloupcu vynechanych u spáry
    check(all(abs((b - a) - p["loz_rozteca"]) < 0.15 for a, b in zip(xs, xs[1:])) and all(abs((b - a) - p["loz_rozteca"]) < 0.15 for a, b in zip(zs_vse, zs_vse[1:])),
          f"{kw}: rozteč mezi jednotkami je {p['loz_rozteca']} mm")
    check(xs[0] - X0 >= p["loz_okraj"] - 0.1 and X1 - xs[-1] >= p["loz_okraj"] - 0.1 and zs[0] - Z0 >= p["loz_okraj"] - 0.1 and Z1 - zs[-1] >= p["loz_okraj"] - 0.1,
          f"{kw}: od okraje desky aspon {p['loz_okraj']} mm")
    check(abs((xs[0] - X0) - (X1 - xs[-1])) < 0.2 and abs((zs_vse[0] - Z0) - (Z1 - zs_vse[-1])) < 0.2, f"{kw}: mrizka je na desce vycentrovana")
    check(all(spara is None or abs(d["position"][2] - spara) >= r_j_ + S.LOZ_MEZERA_OTVOR - 0.1 for d in ju), f"{kw}: zadna jednotka nelezi na delici spáre desek")
    check(all(abs(d["position"][1] - y) < 0.01 for d in ju), f"{kw}: jednotky stoji NA desce (y = horni plocha desky {y:.1f})")
    check(not r["problemy"], f"{kw}: konstrukce bez problemu ({[q['text'][:70] for q in r['problemy']]})")

print("3) jednotky nic neprotinaji (kolik dalsich dilu mimo desku, panely, elektrozlab...)")
for kw in (dict(loz_okraj=25, loz_rozteca=40, sirka=800, hloubka=500), dict(loz_okraj=25, loz_rozteca=60), dict(loz_okraj=30, loz_rozteca=100, presah=0)):
    r = S.sestav_stul(loz=True, **kw)
    bb = [S._aabb(d) for d in r["dily"]]
    ju = [i for i, d in enumerate(r["dily"]) if d["part_id"] == LOZ]
    ostatni = [i for i, d in enumerate(r["dily"]) if d["part_id"] not in (LOZ, "product_4933") or d["position"][1] <= 600]
    zle = 0
    for i in ju:
        for j in ostatni:
            if np.all(np.minimum(bb[i][1], bb[j][1]) - np.maximum(bb[i][0], bb[j][0]) > S.TOL_PRUNIK_MM):
                zle += 1
    check(zle == 0 and not r["problemy"], f"{kw}: {len(ju)} jednotek neprotina zadny dil ({zle} kolizi, problemy {[q['text'][:60] for q in r['problemy']]})")

print("4) vynechani u otvoru (vyrezu)")
for kw in (dict(vyrez1=True), dict(vyrez1=True, vyrez1_w=500, vyrez1_d=300, vyrez1_x=150, vyrez1_z=300), dict(vyrez1=True, vyrez2=True, vyrez2_z=600.0, vyrez3=True, vyrez3_z=900.0),
           dict(sirka=2000, hloubka=1000, vyrez1=True, vyrez1_w=700, vyrez1_d=500, vyrez1_x=200, vyrez1_z=500, loz_rozteca=120, loz_okraj=50)):
    kw_l = {**kw}
    kw_l.setdefault("loz_rozteca", 100)
    kw_l.setdefault("loz_okraj", 50)
    r = S.sestav_stul(loz=True, **kw_l)
    r_bez = S.sestav_stul(loz=True, **{k: v for k, v in kw_l.items() if not k.startswith("vyrez")})
    ju = jednotky(r)
    r_j = S.LOZ_PRUMER / 2.0
    uvnitr = [d for d in ju for v in r["vyrezy"] if v["x0"] - 0.01 < d["position"][0] + r_j and d["position"][0] - r_j < v["x1"] + 0.01 and v["z0"] - 0.01 < d["position"][2] + r_j and d["position"][2] - r_j < v["z1"] + 0.01]
    check(not uvnitr, f"{kw}: zadna jednotka nepresahuje do otvoru")
    # nezavisle: ze vsech pozic mrizky se vynecha prave ty, jejichz paty (kruh r) zasahuji otvor + 2 mm
    X0, X1, Z0, Z1, y = deska_rect(r_bez)
    mriz = {(round(d["position"][0], 1), round(d["position"][2], 1)) for d in jednotky(r_bez)}
    zbyva = {(round(d["position"][0], 1), round(d["position"][2], 1)) for d in ju}
    spara4 = (Z0 + Z1) / 2.0 if r["parametry"]["sirka"] > S.prah_sirky() else None                      # u stolu nad prahem sirky se jednotky vynechavaji i u delici spáry desek (viz sekce 2)
    oc = {(x, z) for (x, z) in mriz if not any(v["x0"] - 2.0 < x + r_j and x - r_j < v["x1"] + 2.0 and v["z0"] - 2.0 < z + r_j and z - r_j < v["z1"] + 2.0 for v in r["vyrezy"])
          and not (spara4 is not None and abs(z - spara4) < r_j + 2.0 - 1e-6)}
    check(zbyva == oc, f"{kw}: zustaly prave jednotky mimo otvory ({len(zbyva)} vs {len(oc)})")
    n_cela = r["loz"]["radku"] * r["loz"]["sloupcu"]                                                       # cela mrizka (vcetne pozic vynechanych u vyrezu a u spáry)
    check(r["loz"]["vynechano"] == n_cela - len(zbyva) and len(mriz) - len(zbyva) > 0, f"{kw}: pocet vynechanych {r['loz']['vynechano']} = {n_cela - len(zbyva)}")
    check(not r["problemy"] or all(q["kod"] == "vyrez_prekryv" for q in r["problemy"]), f"{kw}: bez problemu ({[q['text'][:60] for q in r['problemy']]})")

print("5) strop poctu, rozsahy, dotaz")
rm = S.sestav_stul(loz=True, loz_rozteca=40, loz_okraj=25, sirka=3000, hloubka=1500)
check(not jednotky(rm) and any(q["kod"] == "loz_moc" for q in rm["problemy"]) and rm["loz"]["moc"], "nad 500 jednotek = problem loz_moc a zadne jednotky")
r500 = S.sestav_stul(loz=True, loz_rozteca=50, loz_okraj=50, sirka=1200, hloubka=800)
check(len(jednotky(r500)) == r500["loz"]["pocet"] and not r500["problemy"] or r500["loz"]["moc"], "hustejsi mrizka pod stropem je v poradku")
for kw in (dict(loz_rozteca=39), dict(loz_rozteca=1001), dict(loz_okraj=24), dict(loz_okraj=501)):
    try:
        S.sestav_stul(loz=True, **kw)
        check(False, f"{kw}: mimo rozsah musi selhat")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"{kw}: mimo rozsah ({e.kod})")
rq = S.parametry_z_dotazu({"loz": "1", "loz_rozteca": "150", "loz_okraj": "75.5"})
check(rq == {"loz": True, "loz_rozteca": 150.0, "loz_okraj": 75.5}, f"parsovani dotazu ({rq})")
check(S.parametry_z_dotazu({"loz": "0"}) == {"loz": False}, "loz=0")

print("6) cena (polozky) a GLB")
r = S.sestav_stul(loz=True)
ent = [e for e in S.entries_pro_cenu(r["dily"]) if e["part_id"] == LOZ]
check(len(ent) == len(jednotky(r)) and all(set(e) == {"part_id"} for e in ent), f"kazda jednotka je polozka ceny ({len(ent)})")
h, glb = G.model_pro_parametry({"loz": True})
check(glb[:4] == b"glTF", "GLB se slozilo")
import json, struct  # noqa: E402
n = struct.unpack("<I", glb[12:16])[0]
js = json.loads(glb[20:20 + n])
mat_chrom = [m for m in js["materials"] if m["pbrMetallicRoughness"].get("metallicFactor") == 1.0 and m["pbrMetallicRoughness"]["roughnessFactor"] < 0.3]
check(len(mat_chrom) == 1 and len(js["meshes"]) == len(js["materials"]) + 1, "jednotky maji vlastni chromovy material (a sit navic = horni suplik boxu na klik)")
h0, glb0 = G.model_pro_parametry({})
check(h != h0 and len(glb) > len(glb0), "jina konfigurace = jiny hash a vetsi model")
# procedural tvar: bbox mesh == deklarovany bbox, normaly jednotkove, trojuhelniky platne
P, N, T = G.nacti_mesh(LOZ)
lo, hi = S.glb_bbox(LOZ)
check(np.allclose(P.min(axis=0), lo, atol=0.01) and np.allclose(P.max(axis=0), hi, atol=0.01), f"bbox tvaru souhlasi s deklaraci ({P.min(axis=0)}..{P.max(axis=0)} vs {lo}..{hi})")
check(np.allclose(np.linalg.norm(N, axis=1), 1.0, atol=1e-3) and T.max() < len(P) and T.min() >= 0, "normaly jsou jednotkove, indexy platne")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
