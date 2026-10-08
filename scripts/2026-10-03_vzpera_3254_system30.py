#!/usr/bin/env python3
"""Vzpera 45 stupnu pro profily 30x30 (bot8, 2026-10-03, Robert: "najdi sikmou spojku pro profily 30x30 - je to 2.2.001.08.3030.06, vytvor ve scene stejnou komponentu:
vzperu jako je ta ze systemu 40").

Predloha = vlastni tvar #179 "kompletni spoj vzpera 3220 (ram+spojka+vzpera 45st)": ram (profil 40x40 svisle) + Sikma spojka 3220 na horním konci + vzpera (druhy profil) polozena
STENOU na sikmou plochu spojky tak, ze osy obou profilu svíraji 45 stupnu a stena vzpery lezi v rovine sikme plochy (stred vzpery nad referencnim bodem plochy, odsazeny o pul
sirky profilu po normale plochy). Tady totez pro system 30: ram Object_7 (30x30), spojka product_3254 "Spojka uhel 45 stupnu system 30" (SKU 2.2.001.08.3030.06),
vzpera Object_7.

Geometrie spojky 3254 (z jeji skutecne site, ne odhad): cela plocha (n = -Y) lezi v rovine y = 0 a pokryva x v <-30, 0>, z v <-15, 15> => stred celniho ctverce 30x30 je v (-15, 0),
spojka se proto klade na konec profilu s posunem o +15 v x; sikma plocha je ve skutecnosti vychylena o 0.77 st. od 45 (n = (0.6975, 0.7166, 0), plosny stred (-17.27, 24.81, 0)); vzpera se klade presne pod 45 st.
(vyrobce uvadi 45) a rovinou jejiho povrchu prochazi plosny stred plochy; vystupky spojky (cep, hrana) zasahuji do T-drazky vzpery, ne do plneho materialu.
Spusteni:  api/venv/bin/python3 scripts/2026-10-03_vzpera_3254_system30.py            (jen vypocet a kontrola geometrie, nic nezapisuje)
           systemd-run --pipe --wait --working-directory=/opt/konfigurator --property=EnvironmentFile=/opt/konfigurator/api/.env \\
                /opt/konfigurator/api/venv/bin/python3 /opt/konfigurator/scripts/2026-10-03_vzpera_3254_system30.py --zapsat      (vlozi novy radek do custom_shapes)"""
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_glb as G  # noqa: E402

JMENO = "bot8: kompletni spoj vzpera 3254 (ram+spojka+vzpera 45st, system 30)"
POL = 15.0                                         # pul sirky profilu 30x30
DELKA = 1000.0                                     # delka profilu v katalogu (Object_7)
Y_KONEC = DELKA / 2.0                              # horni konec svisleho ramu
S2 = np.sqrt(0.5)


def mat_na_quat(R):
    """quaternion (x, y, z, w) z rotacni matice."""
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
    return [float(x), float(y), float(z), float(w)]


def quat_na_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def sestav():
    # spojka 3254: poloha na konci ramu (stred celniho ctverce (-15, 0) -> osa profilu)
    spoj_pos = np.array([POL, Y_KONEC, 0.0])
    n = np.array([S2, S2, 0.0])                                    # normala sikme plochy (nativne i ve svete - spojka je bez natoceni)
    f_nat = np.array([-17.27, 24.81, 0.0])                         # plosny stred sikme plochy (jako u 3220 / #179: tam je brana plosny stred plochy, ne hranicni)
    f = spoj_pos + f_nat
    t = np.array([-S2, S2, 0.0])                                   # smer vzpery v rovine plochy (nahoru a dozadu - stejne jako u systemu 40: tam (0, .707, -.707))
    # osy vzpery: nativni X -> -n (stena smerem k plose), nativni Y -> t (osa profilu), nativni Z = X x Y
    X, Y = -n, t
    Z = np.cross(X, Y)
    R = np.column_stack([X, Y, Z])
    assert abs(np.linalg.det(R) - 1.0) < 1e-9
    stred_vzpery = f + POL * n
    return [
        {"part_id": "Object_7", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
        {"part_id": "product_3254", "position": [float(v) for v in spoj_pos], "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
        {"part_id": "Object_7", "position": [float(v) for v in stred_vzpery], "quaternion": mat_na_quat(R), "scale": [1.0, 1.0, 1.0]},
    ], n, f


def sat_obb_aabb(c1, R1, h1, lo, hi):
    """Prekryv OBB (stred c1, osy R1 po sloupcich, polorozmery h1) a AABB [lo, hi] podle SAT; vraci nejmensi hloubku pruniku (mm; <= 0 = bez pruniku)."""
    c2, h2 = (lo + hi) / 2.0, (hi - lo) / 2.0
    A = [R1[:, i] for i in range(3)]
    B = [np.eye(3)[i] for i in range(3)]
    osy = A + B + [np.cross(a, b) for a in A for b in B if np.linalg.norm(np.cross(a, b)) > 1e-9]
    minp = np.inf
    for ax in osy:
        ax = ax / np.linalg.norm(ax)
        r1 = sum(h1[i] * abs(ax @ A[i]) for i in range(3))
        r2 = sum(h2[i] * abs(ax @ B[i]) for i in range(3))
        pr = r1 + r2 - abs(ax @ (c2 - c1))
        minp = min(minp, pr)
    return minp


def over(parts, n):
    ram, spoj, vz = parts
    P, _, _ = G._transformuj("product_3254", spoj)
    chyby = []
    R = quat_na_mat(vz["quaternion"])
    c = np.array(vz["position"])
    loc = (P - c) @ R                                              # souradnice vrcholu spojky v osach vzpery: x = k plose (stena vzpery u spojky je x = +15), z = napric, y = podel osy
    za = loc[:, 0] < POL - 0.05                                    # vrcholy spojky uvnitr obalky vzpery
    hl = POL - loc[:, 0]
    v_drazce = za & (np.abs(loc[:, 2]) <= 4.1)                     # T-drazka Object_7: otvor 8.2 mm siroky, 10 mm hluboky (z prurezu site profilu)
    v_plnem = za & (np.abs(loc[:, 2]) > 4.1)
    max_drazka = float(hl[v_drazce].max()) if v_drazce.any() else 0.0
    max_plne = float(hl[v_plnem].max()) if v_plnem.any() else 0.0
    print(f"vrcholy spojky uvnitr obalky vzpery: {int(za.sum())} - v otvoru T-drazky {int(v_drazce.sum())} (max {max_drazka:.2f} mm hluboko, drazka je 10 mm), v plnem materialu {int(v_plnem.sum())} (max {max_plne:.2f} mm)")
    if max_drazka > 10.0:
        chyby.append(f"cep spojky zasahuje do drazky hloubeji nez 10 mm ({max_drazka:.2f})")
    if max_plne > 0.4:
        chyby.append(f"spojka zasahuje do plneho materialu vzpery o {max_plne:.2f} mm (povoleno 0.4 mm = odchylka sikme plochy 0.77 st. od 45)")
    # vzpera x ram: bez pruniku
    pr_ram = sat_obb_aabb(c, R, np.array([POL, DELKA / 2.0, POL]), np.array([-POL, -DELKA / 2.0, -POL]), np.array([POL, DELKA / 2.0, POL]))
    print(f"vzpera x ram: hloubka pruniku {pr_ram:+.2f} mm (<= 0 = bez pruniku)")
    if pr_ram > 0.05:
        chyby.append(f"vzpera se protina s ramem o {pr_ram:.2f} mm")
    # mezera mezi plochou spojkou a stenou vzpery (nejblizsi vrcholy ploche) - aby vzpera nelevitovala
    plocha = P[(np.abs(loc[:, 2]) <= POL) & (loc[:, 0] < POL + 1.0)]
    print(f"nejblizsi bod spojky ke stene vzpery: {POL - (loc[:, 0]).min():+.2f} mm za stenou (kladne = zasah)")
    uhel = np.degrees(np.arccos(np.clip(abs((R @ [0, 1, 0]) @ np.array([0, 1, 0])), -1, 1)))
    print(f"uhel mezi osami ramu a vzpery: {uhel:.2f} stupnu (cil 45)")
    if abs(uhel - 45.0) > 0.01:
        chyby.append(f"uhel {uhel:.2f}")
    print(f"spojka zasunuta do ramu: {Y_KONEC - P[:, 1].min():.2f} mm | vyska spojky nad ramem: {P[:, 1].max() - Y_KONEC:.2f} mm")
    return chyby


def main():
    zapsat = "--zapsat" in sys.argv
    parts, n, f = sestav()
    chyby = over(parts, n)
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
    print(f"Kontrola (odkaz): https://autovestavby.logiman.cz/api/kontrola-scena?items=cs:{nid},cs:179  |  ve Scene: Vlastni tvary -> {JMENO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
