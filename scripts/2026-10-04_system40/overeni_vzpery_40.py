#!/opt/konfigurator/api/venv/bin/python
"""Overeni geometrie sikmych vzper (bot10, 2026-10-04): sikma spojka na koncich profilu v generatoru vs VLASTNI TVARY ve Scene (DB custom_shapes, jen cteni):
  #580 "Sikma spojka 30 na profilu 30" (spojka 3254 na profilu Object_7)  a  #178 "SIkma spojka 40 na profilu 40" (spojka 3220 na profilu Object_11; Robert).
Porovnava se, jak lezi pivot spojky vuci profilu (osove odsazeni za koncem, bocni odsazeni od osy) a kolik je kolmy odstup STREDU KONCE profilu od sikme plochy spojky (to je to, co urcuje,
kde plocha lezi na stene stojky / spodku ramene); stejne cislo ma generator (`SYSTEMY[s]["vzpera_sten"]`). Plocha spojky se bere z meshe katalogu (normala (0, 1, 1) / (1, 1, 0) / sqrt2).
  api/venv/bin/python scripts/2026-10-04_system40/overeni_vzpery_40.py"""
import json
import os
import sys

import numpy as np

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import stul_konfigurator as S  # noqa: E402
import stul_glb as G  # noqa: E402
from _env import get_conn  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print("  CHYBA:", msg)


def plocha_spojky(part_id, n_nat):
    """(normala, kolmy odstup od pocatku, plosny stred) nejvetsi sikme roviny spojky z meshe (nativni souradnice)."""
    pos, nrm, tri = G.nacti_mesh(part_id)
    P = pos.astype(float)
    a, b, c = P[tri[:, 0]], P[tri[:, 1]], P[tri[:, 2]]
    n = np.cross(b - a, c - a)
    ar = np.linalg.norm(n, axis=1) / 2
    n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    cen = (a + b + c) / 3
    n0 = np.array(n_nat, float) / np.linalg.norm(n_nat)
    shoda = (n @ n0) > 0.999
    d = cen @ n0
    hist, edges = np.histogram(d[shoda], bins=np.arange(d[shoda].min() - 0.5, d[shoda].max() + 0.6, 0.1))
    dm = edges[np.argmax(hist)] + 0.05
    m = shoda & (np.abs(d - dm) < 0.35)
    area = ar[m].sum()
    C = (cen[m] * ar[m, None]).sum(axis=0) / area
    return n0, float(C @ n0), C


def rel_vuci_profilu(profil, spojka, part_spojky, n_nat):
    """Pro jednu spojku: osove odsazeni pivotu za koncem profilu, bocni odsazeni a kolmy odstup STREDU KONCE od sikme plochy; vse ve svetovych souradnicich dilu (position, quaternion)."""
    Rp = S.kvat_na_matici(profil["quaternion"])
    ax = Rp @ np.array([0.0, 1.0, 0.0])                       # osa profilu (nativni Y) ve svete
    L = 1000.0 * profil["scale"][1]
    c = np.array(profil["position"], float)
    p = np.array(spojka["position"], float)
    d = p - c
    axial = float(d @ ax)                                     # +: u konce v kladnem smeru osy
    smer = 1.0 if axial > 0 else -1.0
    out = ax * smer                                           # osa ven z konce profilu u teto spojky
    konec = c + out * L / 2.0
    Rs = S.kvat_na_matici(spojka["quaternion"])
    n_w = Rs @ n_nat
    n_w = n_w / np.linalg.norm(n_w)
    # nativni Y spojky ma mirit ven z konce profilu
    y_w = Rs @ np.array([0.0, 1.0, 0.0])
    lat_dir = n_w - (n_w @ out) * out
    lat_dir = lat_dir / np.linalg.norm(lat_dir)
    n_nat0, d_nat, _ = plocha_spojky(part_spojky, n_nat)
    # rovina plochy ve svete: n_w . (x - p) = d_nat ; kolmy odstup stredu konce od roviny
    odstup = d_nat - float(n_w @ (konec - p))
    return {"mezera": abs(axial) - L / 2.0, "boční_od_osy": float((d - axial * ax) @ lat_dir), "ven": float(y_w @ out), "n_podel_osy": float(n_w @ out), "odstup": odstup}


def vlastni_tvar(tid):
    cur = get_conn().cursor()
    cur.execute("SELECT name, data FROM custom_shapes WHERE id=%s", (tid,))
    r = cur.fetchone()
    return r["name"], (json.loads(r["data"]) if isinstance(r["data"], (str, bytes)) else r["data"])["parts"]


def porovnej(system, tid, part_spojky, n_nat):
    nazev, parts = vlastni_tvar(tid)
    print(f"\n== system {system}: vlastni tvar #{tid} '{nazev}' vs generator")
    profil = next(d for d in parts if d["part_id"] in S.PROFIL_PARTS)
    spojky = [d for d in parts if d["part_id"] == part_spojky]
    check(len(spojky) == 2 and profil["part_id"] == S.SYSTEMY[system]["profil"], f"tvar #{tid}: profil {S.SYSTEMY[system]['profil']} a 2 spojky {part_spojky}")
    tv = [rel_vuci_profilu(profil, sp, part_spojky, n_nat) for sp in spojky]
    r = S.sestav_stul(system=system, sirka=1400, vzpery=True, vzpera_delka=420)
    klice = [tuple(k) if isinstance(k, list) else k for k in r["klice"]]
    prof = r["dily"][klice.index(("vz", "L", "prof"))]
    gen = [rel_vuci_profilu(prof, r["dily"][klice.index(("vz", "L", n))], part_spojky, n_nat) for n in (0, 1)]
    for nm, lst in (("tvar", tv), ("generator", gen)):
        for i, x in enumerate(lst):
            print(f"   {nm} spojka {i}: mezera za koncem {x['mezera']:.4f} mm, bocni odsazeni od osy {x['boční_od_osy']:.4f}, nativni Y ven {x['ven']:.3f}, normala plochy podel osy {x['n_podel_osy']:.4f}, odstup stredu konce od plochy {x['odstup']:.4f}")
    for i, x in enumerate(tv):
        check(abs(x["ven"] - 1.0) < 1e-4, f"tvar #{tid} spojka {i}: nativni Y miri ven z konce profilu")
    for i, g in enumerate(gen):
        t = tv[0]
        check(abs(g["ven"] - 1.0) < 1e-4, f"generator spojka {i}: nativni Y miri ven z konce profilu")
        check(abs(g["mezera"] - t["mezera"]) < 0.01, f"generator spojka {i}: mezera za koncem profilu {g['mezera']:.4f} = tvar {t['mezera']:.4f} (+-0,01 mm)")
        check(abs(g["boční_od_osy"] - t["boční_od_osy"]) < 0.05, f"generator spojka {i}: bocni odsazeni pivotu {g['boční_od_osy']:.3f} = tvar {t['boční_od_osy']:.3f} (+-0,05 mm)")
        check(abs(g["n_podel_osy"] - t["n_podel_osy"]) < 1e-3, f"generator spojka {i}: sikma plocha svira s osou profilu stejny uhel jako ve tvaru ({g['n_podel_osy']:.4f})")
        check(abs(g["odstup"] - t["odstup"]) < 0.4, f"generator spojka {i}: odstup stredu konce od sikme plochy {g['odstup']:.3f} = tvar {t['odstup']:.3f} (+-0,4 mm = VZPERA_TOL_PLNY)")
        check(abs(g["odstup"] - S.SYSTEMY[system]["vzpera_sten"]) < 0.1, f"generator spojka {i}: odstup {g['odstup']:.3f} = SYSTEMY[{system}]['vzpera_sten'] {S.SYSTEMY[system]['vzpera_sten']:.3f} (+-0,1 mm; u systemu 30 je konstanta z kalibrace sikme plochy 0,77 st.)")


porovnej(30, 580, "product_3254", (1.0, 1.0, 0.0))
porovnej(40, 178, "product_3220", (0.0, 1.0, 1.0))
print(f"\n{OK} kontrol OK" + ("" if not FAILS else f"; SELHALO {len(FAILS)}"))
sys.exit(1 if FAILS else 0)
