#!/usr/bin/env python3
"""Tvar "Sikma spojka 30 na profilu 30" (bot8, 2026-10-03, Robert: "mluvil jsem o tvaru jako je ten 40, tzn profil a na kazde strane sikma spojka zrcadlove").

Predloha: vlastni tvar #178 "SIkma spojka 40 na profilu 40" (po doplneni druhe spojky): profil 40x40 (Object_11, 1000 mm, osa Z, lezi na y = 0) + Sikma spojka 3220 na obou
koncich, seznuti vede nahoru a ven, na druhem konci zrcadlove. Tady totez pro system 30: profil Object_7 (30x30) + Sikma spojka product_3254 (SKU 2.2.001.08.3030.06).

Geometrie spojky 3254 (z jeji skutecne site): puvod je v ROHU celniho ctverce, ne ve stredu - cela plocha (n = -Y nativne) lezi v y = 0 a pokryva x v <-30, 0>, z v <-15, 15>
(stred (-15, 0)); sikma plocha ma normalu (0.6975, 0.7166, 0) (nativne je skloneni v ose X). Aby seznuti vedlo nahoru jako u 40, otoci se spojka tak, ze nativni X -> svet +Y
(nahoru), nativni Y (smer telesa spojky) -> -Z (ven ze zapornego konce), nativni Z -> -X; celo spojky (stred -15 v nativnim x) pak lezi o 15 mm pod pivotem => pivot je o 15 nad
osou profilu. Spojka na kladnem konci je zrcadlo (z -> -z) te na zapornem; 3254 je symetricka podle nativni roviny z = 0, takze zrcadlo = vlastni rotace stejneho dilu
(nativni X -> +Y, nativni Y -> +Z, nativni Z -> +X). Kontrola na skutecne siti: stejny rozsah v x/y, zasunuti do profilu, zrcadlovy bokorys, vrcholy B = odraz vrcholu A (do 1 mm).
Spusteni:  api/venv/bin/python3 scripts/2026-10-03_sikma_spojka_30_na_profilu_30.py            (jen vypocet a kontrola, nic nezapisuje)
           ... --zapsat   (INSERT jednoho radku do custom_shapes; opakovane spusteni se stejnym jmenem skonci chybou)"""
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_glb as G  # noqa: E402

JMENO = "Sikma spojka 30 na profilu 30"
DELKA = 1000.0
POL = 15.0
S2 = np.sqrt(0.5)


def mat_na_quat(R):
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        w, x, y, z = 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    else:
        i = int(np.argmax(np.diag(R)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = np.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
        q = np.zeros(4)
        q[i] = 0.25 * s
        q[j] = (R[j, i] + R[i, j]) / s
        q[k] = (R[k, i] + R[i, k]) / s
        w = (R[k, j] - R[j, k]) / s
        x, y, z = q[0], q[1], q[2]
    q = np.array([x, y, z, w])
    return [float(v) for v in q / np.linalg.norm(q)]


def sestav():
    cx, cy = 0.0, POL                                              # osa profilu: x = 0, y = 15 (profil lezi na y = 0, jako #178)
    # profil: nativni Y (delka) -> -Z (stejne jako #178: q = R_x(-90))
    q_prof = [-S2, 0.0, 0.0, S2]
    # spojka A (zaporny konec): nativni X -> +Y, nativni Y -> -Z, nativni Z -> -X
    M_A = np.column_stack([[0, 1, 0], [0, 0, -1], [-1, 0, 0]]).astype(float)
    # spojka B (kladny konec) = zrcadlo A pres z = 0 (vlastni rotace, spojka je symetricka podle nativni z = 0): X -> +Y, Y -> +Z, Z -> +X
    M_B = np.column_stack([[0, 1, 0], [0, 0, 1], [1, 0, 0]]).astype(float)
    for M in (M_A, M_B):
        assert abs(np.linalg.det(M) - 1.0) < 1e-12
    pos_A = [cx, cy + POL, -DELKA / 2.0]                           # celo spojky (nativni stred (-15, 0)) pada na stred konce profilu
    pos_B = [cx, cy + POL, +DELKA / 2.0]
    return [
        {"part_id": "product_3254", "position": pos_A, "quaternion": mat_na_quat(M_A), "scale": [1.0, 1.0, 1.0]},
        {"part_id": "Object_7", "position": [cx, cy, 0.0], "quaternion": q_prof, "scale": [1.0, 1.0, 1.0]},
        {"part_id": "product_3254", "position": pos_B, "quaternion": mat_na_quat(M_B), "scale": [1.0, 1.0, 1.0]},
    ]


def aabb(d):
    p, _, _ = G._transformuj(d["part_id"], d)
    return p.min(axis=0), p.max(axis=0), p


def over(parts):
    a, prof, b = parts
    lp, hp, _ = aabb(prof)
    la, ha, pa = aabb(a)
    lb, hb, pb = aabb(b)
    print(f"profil: x [{lp[0]:.2f}, {hp[0]:.2f}] y [{lp[1]:.2f}, {hp[1]:.2f}] z [{lp[2]:.2f}, {hp[2]:.2f}]")
    print(f"spojka A: x [{la[0]:.2f}, {ha[0]:.2f}] y [{la[1]:.2f}, {ha[1]:.2f}] z [{la[2]:.2f}, {ha[2]:.2f}]")
    print(f"spojka B: x [{lb[0]:.2f}, {hb[0]:.2f}] y [{lb[1]:.2f}, {hb[1]:.2f}] z [{lb[2]:.2f}, {hb[2]:.2f}]")
    chyby = []
    # spojka je souosa s profilem (stred v x i mezi stenami profilu) a na koncich zasunuta o stejnou hodnotu
    zas_a, zas_b = ha[2] - lp[2], hp[2] - lb[2]
    print(f"zasunuti do profilu: A {zas_a:.2f} mm, B {zas_b:.2f} mm")
    if abs(zas_a - zas_b) > 0.01:
        chyby.append("nestejne zasunuti spojek")
    if np.abs((hb - lb) - (ha - la)).max() > 0.01 or abs(la[0] - lb[0]) > 0.01 or abs(la[1] - lb[1]) > 0.01:
        chyby.append("spojky A a B nemaji stejny rozsah v x/y")
    if la[0] < lp[0] - 0.05 or ha[0] > hp[0] + 0.05:
        chyby.append(f"spojka presahuje bocni steny profilu v x ({la[0]:.2f}..{ha[0]:.2f} vs {lp[0]:.2f}..{hp[0]:.2f})")
    print(f"presah spojky nad horni plochou profilu: {ha[1] - hp[1]:.2f} mm, pod spodni: {lp[1] - la[1]:.2f} mm")
    # B je odraz A pres z = 0 (vzdalenost mnozin vrcholu; 3254 je symetricka podle nativni z = 0 s odchylkou do 0.82 mm - drobna nesymetrie site)
    odraz = pa * np.array([1.0, 1.0, -1.0])
    dm = np.sqrt(((odraz[:, None, :] - pb[None, :, :]) ** 2).sum(axis=2))
    haus = float(max(dm.min(axis=1).max(), dm.min(axis=0).max()))
    print(f"B = zrcadlo A pres z = 0: vzdalenost mnozin vrcholu (Hausdorff) {haus:.3f} mm")
    if haus > 1.0:
        chyby.append(f"B neni zrcadlo A (odchylka {haus:.3f} mm)")
    # seznuti vede nahoru a ven: nejnizsi bod spojky je na vnejsim konci
    ya, yb = pa[np.argmax(np.abs(pa[:, 2])), 1], pb[np.argmax(np.abs(pb[:, 2])), 1]
    print(f"krajni bod spojky (nejdal od profilu) je ve vysce y: A {ya:.2f}, B {yb:.2f}")
    if abs(ya - yb) > 0.05:
        chyby.append("seznuti neni zrcadlove")
    if (np.minimum(ha, hb) - np.maximum(la, lb) > 0).all():
        chyby.append("spojky se prekryvaji")
    return chyby


def main():
    zapsat = "--zapsat" in sys.argv
    parts = sestav()
    chyby = over(parts)
    print("kontrola geometrie:", "OK" if not chyby else chyby)
    if chyby:
        return 1
    for i, p in enumerate(parts):
        print(i, json.dumps(p))
    if not zapsat:
        print("\n(jen kontrola; zapis: --zapsat)")
        return 0
    import pymysql
    c = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 3306)), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                        database=os.environ["DB_NAME"], charset="utf8mb4")
    cur = c.cursor()
    cur.execute("SELECT id FROM custom_shapes WHERE name=%s", (JMENO,))
    if cur.fetchone():
        raise SystemExit("tvar s timto jmenem uz existuje - nic nezapsano")
    data = json.dumps({"parts": parts, "join_groups": [], "frame_groups": [], "text_labels": []}, ensure_ascii=False)
    cur.execute("INSERT INTO custom_shapes (name, category_id, data, created_by, is_public) VALUES (%s, %s, %s, %s, %s)", (JMENO, None, data, 1, 1))
    nid = cur.lastrowid
    c.commit()
    print(f"ZAPSANO: custom_shapes #{nid} ({JMENO})")
    print(f"Kontrola (odkaz): https://autovestavby.logiman.cz/api/kontrola-scena?items=cs:178,cs:{nid}  |  ve Scene: Vlastni tvary -> #{nid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
