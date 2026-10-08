#!/usr/bin/env python3
"""Zkouska (bot8, 2026-10-03, Robert: "zkus udelat v hl. sceni tento stul z profilu 30x30" + obrazek baliciho stolu 1400x800, deska 900, celkem 1737):
nový Vlastni tvar ve Sceni z dilu generatoru stolu system 30 (porad stejne spoje/lic_peers), upraveny podle obrazku:
  * deska 1400x800 ve vysce 900, jedna spodni police, stavitelne patky (obrazek ma stavitelne nozky),
  * stredni noha 510 mm od leve nohy (leva prihradka pro kos je 510 siroka),
  * horni ramy: zadni stojky zkracene tak, aby cely stul mel 1737 mm, ramena 400 mm dopredu, pricka u ramen,
  * pricka pro zavesenou polici 1033 mm nad podlahou (obrazek: ~133 mm nad deskou),
  * zadni zástena na desce (lamino 18 mm, vyska 100) a zadni stena spodnich prihradek vpravo (lamino 18 mm, vyska 450),
  * BEZ: LED, perforovanych panelu, elektrozlabu, supliku, koleček (generator je zapnul/neumi), druha stredni noha, monitor, kos, polic nahore.
Spusteni:  api/venv/bin/python3 scripts/2026-10-03_stul_balici_z_obrazku.py            (jen vypise a zkontroluje, nic nezapisuje)
           systemd-run --pipe --wait --property=EnvironmentFile=/opt/konfigurator/api/.env api/venv/bin/python3 scripts/2026-10-03_stul_balici_z_obrazku.py --zapsat
Zapis = INSERT jednoho radku do custom_shapes (jako ostatni vlastni tvary). Opakovany zapis stejneho jmena nic neprepise (konci chybou)."""
import copy
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_konfigurator as S  # noqa: E402

JMENO = "Stul.balici.1400x800.z.obrazku.zkouska"
CILOVA_VYSKA = 1737.0                    # celkem od podlahy po horni plochu horniho ramene (obrazek)
PRICKA_STRED_Y = 1033.0                  # stred pricky pro zavesenou polici (obrazek: ~133 mm nad deskou 900)
DESKA_Y = 900.0
PAR = dict(sirka=1400, hloubka=800, vyska=900, police=1, suplik=False, drzak_pet=False, kolecka=False, patky=True, led_rameno=400.0,
           panely=True, led=True, elektrozlab=False, stredni_noha=510.0)
ODEBRAT_ID = ("product_4929", "product_4931")          # LED, perforovane panely (generator je pro horni ramy zapnul; do tvaru nepatri)


def hr(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


def sestav():
    S.SIRKA_STREDNI_NOHY = 1300.0                       # jen pro tuto zkousku: stredni noha uz u sirky 1400 (generator ji dava od 1500)
    r = S.sestav_stul(**PAR)
    if r["problemy"]:
        raise SystemExit(f"generator hlasi problemy: {r['problemy']}")
    dily = copy.deepcopy(r["dily"])
    klice = [tuple(k) if isinstance(k, list) else k for k in r["klice"]]
    zaklad = copy.deepcopy(dily)
    # --- horni rame: vse nad 1900 mm (krome zadnich stojek) o delta dolu, stojky zkratit
    top = max(hr(d)[1][1] for d, k in zip(dily, klice) if d["part_id"] == "Object_7")
    delta = float(top - CILOVA_VYSKA)
    stojky = [i for i, k in enumerate(klice) if k in (("t", S.NOHA_ZL), ("t", S.NOHA_ZP), "RM")]
    horni = [i for i, d in enumerate(dily) if hr(d)[0][1] >= 1900.0 and i not in stojky and d["part_id"] not in ODEBRAT_ID]
    for i in stojky:
        lo, hi = hr(dily[i])
        nova_delka = float(hi[1] - delta - lo[1])
        dily[i]["scale"][1] = round(nova_delka / 1000.0, 6)
        dily[i]["position"][1] = round(dily[i]["position"][1] - delta / 2.0, 4)       # pivot profilu = stred
    for i in horni:
        dily[i]["position"][1] = round(dily[i]["position"][1] - delta, 4)
    # --- pricka pro zavesenou polici: cela skupina "pricka panelu" (profily + jejich spojky) z ~1363 na PRICKA_STRED_Y
    pr = [i for i, k in enumerate(klice) if k in (("t", 14), ("seg", 14))]
    y0 = float(np.mean([(hr(dily[i])[0][1] + hr(dily[i])[1][1]) / 2 for i in pr]))
    dy = PRICKA_STRED_Y - y0
    spoj_pr = [i for i, d in enumerate(dily) if d["part_id"] == "product_3158" and abs((hr(d)[0][1] + hr(d)[1][1]) / 2 - y0) < 45.0]
    for i in pr + spoj_pr:
        dily[i]["position"][1] = round(dily[i]["position"][1] + dy, 4)
    # --- nove desky (lamino 18 mm, part_id product_4933): zadni zastena na desce a zadni stena spodnich prihradek
    zad_x1 = max(hr(dily[i])[0][0] for i in stojky)                       # zadni plocha desky/ vnitrni plocha zadnich stojek
    z_lev, z_prav = min(hr(dily[i])[1][2] for i in stojky if klice[i] != "RM"), max(hr(dily[i])[0][2] for i in stojky if klice[i] != "RM")
    z_mid = hr(dily[klice.index("RM")])[1][2]
    police_y = max(hr(d)[1][1] for d, k in zip(dily, klice) if k == ("t", 1))

    def deska_svisla(x_zad, z0, z1, y0_, y1_, tl=18.0):
        d = {"part_id": "product_4933", "position": [0.0, 0.0, 0.0], "quaternion": [0.0, 0.707107, 0.0, 0.707107], "scale": [round((z1 - z0) / 1000.0, 6), round((y1_ - y0_) / 1000.0, 6), 1.0]}
        lo, hi = hr(d)
        cil_lo, cil_hi = np.array([x_zad - tl, y0_, z0]), np.array([x_zad, y1_, z1])
        d["position"] = [round(float(v), 4) for v in ((cil_lo + cil_hi) / 2 - (lo + hi) / 2)]
        lo, hi = hr(d)
        if np.abs((hi - lo) - (cil_hi - cil_lo)).max() > 0.5:
            raise SystemExit(f"nova deska ma jiny rozmer nez cil: {hi - lo} vs {cil_hi - cil_lo}")
        return d
    nove = [deska_svisla(zad_x1, z_lev, z_prav, DESKA_Y, DESKA_Y + 100.0),                          # zastena na desce
            deska_svisla(zad_x1, z_mid + 60.0, z_prav - 5.0, police_y + 12.0, police_y + 12.0 + 450.0)]   # zadni stena vpravo (mezery k spojkam)
    # --- odebrani LED/perforovanych panelu, prepocet indexu
    pryc = {i for i, d in enumerate(dily) if d["part_id"] in ODEBRAT_ID}
    mapa, n = {}, 0
    for i in range(len(dily)):
        if i not in pryc:
            mapa[i] = n
            n += 1
    out = []
    for i, d in enumerate(dily):
        if i in pryc:
            continue
        d = copy.deepcopy(d)
        if d.get("lic_peers"):
            d["lic_peers"] = sorted(mapa[j] for j in d["lic_peers"] if j in mapa)
            if not d["lic_peers"]:
                d.pop("lic_peers")
        if isinstance(d.get("attached_to"), dict) and d["attached_to"].get("prof") in mapa:
            d["attached_to"]["prof"] = mapa[d["attached_to"]["prof"]]
        for k in ("deska_celek", "deska_kus"):
            d.pop(k, None)
        out.append(d)
    out.extend(nove)
    return out, r, zaklad, delta, dy


def kolize(dily, prah=1.0):
    bb = [hr(d) for d in dily]
    res = []
    for i in range(len(dily)):
        for j in range(i + 1, len(dily)):
            pr = np.minimum(bb[i][1], bb[j][1]) - np.maximum(bb[i][0], bb[j][0])
            if (pr > prah).all():
                res.append((i, j, [round(float(v), 1) for v in pr]))
    return res


def main():
    zapsat = "--zapsat" in sys.argv
    dily, r, zaklad, delta, dy = sestav()
    lo = np.min([hr(d)[0] for d in dily], axis=0)
    hi = np.max([hr(d)[1] for d in dily], axis=0)
    print(f"dily: {len(dily)} (z toho profilu {sum(d['part_id'] == 'Object_7' for d in dily)}, spojek {sum(d['part_id'] == 'product_3158' for d in dily)}, desek {sum(d['part_id'] == 'product_4933' for d in dily)})")
    print(f"zkraceni horniho ramene o {delta:.1f} mm, pricka posunuta o {dy:.1f} mm")
    print(f"vnejsi rozmer: hloubka {hi[0] - lo[0]:.0f}, vyska {hi[1] - lo[1]:.1f} (cil {CILOVA_VYSKA:.0f}), sirka {hi[2] - lo[2]:.0f}; dolni hrana y = {lo[1]:.1f}")
    base_k = {(i, j) for i, j, _ in kolize(zaklad)}
    kol = kolize(dily)
    print(f"kolize (prunik > 1 mm ve vsech osach): zaklad generatoru {len(base_k)}, po uprave {len(kol)}")
    nove_idx = range(len(dily) - 2, len(dily))
    for i, j, pr in kol:
        if i in nove_idx or j in nove_idx:
            print("  NOVA deska koliduje:", i, dily[i]["part_id"], "x", j, dily[j]["part_id"], pr)
    zk = [(i, j, pr) for i, j, pr in kol if i not in nove_idx and j not in nove_idx]
    print(f"  kolize mezi puvodnimi dily po uprave (spojka x profil jsou v generatoru bezne): {len(zk)}")
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
    data = json.dumps({"parts": dily, "join_groups": [], "text_labels": [], "frame_groups": []}, ensure_ascii=False)
    cur.execute("INSERT INTO custom_shapes (name, category_id, data, created_by, is_public) VALUES (%s, %s, %s, %s, %s)", (JMENO, 50, data, 1, 1))
    nid = cur.lastrowid
    c.commit()
    cur.execute("SELECT CHAR_LENGTH(data) FROM custom_shapes WHERE id=%s", (nid,))
    print(f"ZAPSANO: custom_shapes #{nid} ({JMENO}), {cur.fetchone()[0]} znaku, {cur.rowcount} radek")
    print(f"Kontrola (odkaz): https://autovestavby.logiman.cz/api/kontrola-scena?items=cs:{nid}  |  ve Scene: Vlastni tvary -> {JMENO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
