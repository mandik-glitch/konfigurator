#!/usr/bin/env python3
"""Sikme rozpery (bot8, 2026-10-03, Robert: "musime se naucit delat sikme rozpery - vezme se konkretni delka profilu a na jeho konce zrcadlove pripne Sikma spojka;
je to videt ve vlastnich tvarech, jen spojka na druhe strane chybi, muzes ji tam doplnit").

Vlastni tvar #178 "SIkma spojka 40 na profilu 40" = profil 40x40 (Object_11, delka 1000 mm, osa Z) + Sikma spojka (product_3220 "Spojka uhel 45 stupnu system 40") na zapornem
konci. Skript prida DRUHOU spojku na kladny konec, ZRCADLOVE podle roviny uprostred profilu (z -> -z):
  * pozice: stejne x, y; z = +500.1656 (symetricky ke spojce A),
  * natoceni: spojka musi mit seznuty konec zrcadlove k prvni (seznuti A vede nahoru a ven, B taky nahoru a ven) - ale je to STEJNY dil, ne zrcadlovy,
    proto vlastni rotace o 180 stupnu kolem osy (0,1,1)/sqrt2 (quaternion [0, 0.7071, 0.7071, 0]); overeno na skutecne geometrii (bokorys symetricky, zasunuti 1.83 mm do
    profilu jako u spojky A, stejny rozsah v x/y).
Hotove sikme rozpery pak vzniknou tak, ze se profil prerizne na pozadovanou delku a spojky se nasadi na oba konce (stejnym zpusobem jako tady).

Spusteni:  api/venv/bin/python3 scripts/2026-10-03_sikma_vzpera_druha_spojka.py           (jen kontrola, nic nezapisuje)
           systemd-run --pipe --wait --working-directory=/opt/konfigurator --property=EnvironmentFile=/opt/konfigurator/api/.env \\
                /opt/konfigurator/api/venv/bin/python3 /opt/konfigurator/scripts/2026-10-03_sikma_vzpera_druha_spojka.py --zapsat
--zapsat prepise data tvaru #178 (zaloha puvodnich dat jde do backups/); funguje jen kdyz tvar ma presne 2 dily (profil + jedna spojka)."""
import copy
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_glb as G  # noqa: E402

TVAR_ID = 178
S2 = 0.7071067811865476


def nacti_db():
    import pymysql
    c = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 3306)), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                        database=os.environ["DB_NAME"], charset="utf8mb4")
    cur = c.cursor()
    cur.execute("SELECT name, data FROM custom_shapes WHERE id=%s", (TVAR_ID,))
    row = cur.fetchone()
    return c, cur, row


def druha_spojka(a):
    """Zrcadlove umisteni spojky B ke spojce A (viz hlavicka)."""
    return {"part_id": a["part_id"], "position": [a["position"][0], a["position"][1], -a["position"][2]], "quaternion": [0.0, S2, S2, 0.0], "scale": [1.0, 1.0, 1.0]}


def aabb(d):
    p, _, _ = G._transformuj(d["part_id"], d)
    return p.min(axis=0), p.max(axis=0), p


def over(parts):
    prof = next(p for p in parts if p["part_id"] == "Object_11")
    spo = [p for p in parts if p["part_id"] == "product_3220"]
    assert len(spo) == 2, "ocekavam dve spojky"
    a, b = spo
    lp, hp, _ = aabb(prof)
    la, ha, pa = aabb(a)
    lb, hb, pb = aabb(b)
    print(f"profil z [{lp[2]:.2f}, {hp[2]:.2f}] | spojka A z [{la[2]:.2f}, {ha[2]:.2f}] | spojka B z [{lb[2]:.2f}, {hb[2]:.2f}]")
    chyby = []
    if abs((hp[2] - lb[2]) - (ha[2] - lp[2])) > 0.01:
        chyby.append(f"zasunuti do profilu se lisi: A {ha[2] - lp[2]:.3f} mm, B {hp[2] - lb[2]:.3f} mm")
    if np.abs((hb - lb) - (ha - la)).max() > 0.01:
        chyby.append("rozmery spojek A a B se lisi")
    if abs(la[0] - lb[0]) > 0.01 or abs(ha[0] - hb[0]) > 0.01 or abs(la[1] - lb[1]) > 0.01 or abs(ha[1] - hb[1]) > 0.01:
        chyby.append("spojky nemaji stejny rozsah v x/y")
    # bokorys (y proti z): B je zrcadlo A pres z = 0 (kontrola seznuti: nejnizsi bod spojky je na vnejsim konci)
    ya, yb = pa[np.argmax(np.abs(pa[:, 2])), 1], pb[np.argmax(np.abs(pb[:, 2])), 1]
    if abs(ya - yb) > 0.01:
        chyby.append(f"seznuti neni zrcadlove (y krajniho bodu {ya:.2f} vs {yb:.2f})")
    # spojky se nesmi dotykat nic jineho nez profilu (A x B)
    if (np.minimum(ha, hb) - np.maximum(la, lb) > 0).all():
        chyby.append("spojky A a B se prekryvaji")
    return chyby


def main():
    zapsat = "--zapsat" in sys.argv
    if os.environ.get("DB_HOST"):
        c, cur, row = nacti_db()
        if not row:
            raise SystemExit(f"tvar #{TVAR_ID} neexistuje")
        jmeno, data = row[0], json.loads(row[1])
    else:
        jmeno = "SIkma spojka 40 na profilu 40 (kopie z 2026-10-03)"
        data = {"parts": [
            {"part_id": "product_3220", "position": [155.17159793665576, 19.983817645190204, -500.16556756019605], "quaternion": [-0.7071067811865476, 0.0, 0.0, 0.7071067811865475], "scale": [1.0, 1.0, 1.0]},
            {"part_id": "Object_11", "position": [155.1716055660503, 19.99996376037609, 0.0], "quaternion": [-0.7071067811865476, 0.0, 0.0, 0.7071067811865476], "scale": [1.0, 1.0, 1.0]}],
            "join_groups": [], "frame_groups": [], "text_labels": []}
        c = cur = None
        print("(bez DB: pouzita kopie dat tvaru #178 z 2026-10-03)")
    parts = data["parts"]
    if len(parts) != 2 or sorted(p["part_id"] for p in parts) != ["Object_11", "product_3220"]:
        raise SystemExit(f"tvar #{TVAR_ID} uz neni 'profil + jedna spojka' ({[p['part_id'] for p in parts]}) - nic nemenim")
    a = next(p for p in parts if p["part_id"] == "product_3220")
    nove = copy.deepcopy(data)
    nove["parts"].append(druha_spojka(a))
    chyby = over(nove["parts"])
    print("kontrola geometrie:", "OK" if not chyby else chyby)
    if chyby:
        raise SystemExit(1)
    print(f"tvar #{TVAR_ID} '{jmeno}': {len(parts)} -> {len(nove['parts'])} dily; nova spojka: {json.dumps(nove['parts'][-1])}")
    if not zapsat:
        print("\n(jen kontrola; zapis: --zapsat)")
        return 0
    if not cur:
        raise SystemExit("--zapsat vyzaduje pripojeni k DB (spustit pres systemd-run s api/.env)")
    zaloha = os.path.join(REPO, "backups", "2026-10-03_custom_shape_178_pred_druhou_sikmou_spojkou.json")
    with open(zaloha, "w", encoding="utf-8") as f:
        json.dump({"id": TVAR_ID, "name": jmeno, "data": data}, f, ensure_ascii=False, indent=1)
    cur.execute("UPDATE custom_shapes SET data=%s WHERE id=%s AND CHAR_LENGTH(data)=%s", (json.dumps(nove, ensure_ascii=False), TVAR_ID, len(row[1])))
    if cur.rowcount != 1:
        c.rollback()
        raise SystemExit(f"zapis se nepovedl (zmeneno radku: {cur.rowcount}) - tvar se mezitim zmenil? nic nezapsano")
    c.commit()
    print(f"ZAPSANO: custom_shapes #{TVAR_ID} ma ted {len(nove['parts'])} dily (zaloha puvodnich dat: {os.path.relpath(zaloha, REPO)})")
    print(f"Kontrola (odkaz): https://autovestavby.logiman.cz/api/kontrola-scena?items=cs:{TVAR_ID}  |  ve Scene: Vlastni tvary -> {jmeno}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
