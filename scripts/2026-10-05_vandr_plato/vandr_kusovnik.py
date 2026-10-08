#!/usr/bin/env python3
"""Kusovnik, cena a vaha komponentu Vandru z DB Vandru (bot10, 2026-10-05) - snimek ceniku pro `build_plato.py --kusovnik`. Jen CTE, nic nezapisuje.

  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
    api/venv/bin/python3 scripts/2026-10-05_vandr_plato/vandr_kusovnik.py --komponent Kufrik.3x43.vysuv.1057.459 --vystup scripts/2026-10-05_vandr_plato/kusovnik_plato.json

Pravidla Vandru (app/Models/Part.php::computePriceWeight, StoredModelPart): cena komponentu = SOUCET cen jeho dilu x pocet (`components_parts`; overeno: Kufrik 3x43 = 4 677,59 Kc = soucet);
dil s presnym nazvem v `parts` ma pevnou cenu a vahu (vcetne operaci, napr. vrtani Zx4), dil BEZ radku v `parts` se oceni z MATERIALU podle rozmeru v nazvu: nazev zacina jmenem
materialu (`20x40x`, `CUB6_`), prvni cislo = delka v mm, pripadne `x<druhy rozmer>`; velikost = delka[m] (x druhy rozmer[m]), cena = velikost x cena materialu (Kc/m nebo Kc/m2), vaha obdobne (g).
Z toho pro dil, ktery se pri zmene sirky protahuje, plyne cena za 1 mm delky (`material_cena_za_mm`); operace (napr. 490 Kc u profilu se Zx4) se pri zmene delky nemeni."""
import argparse
import importlib.util
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def velikost(nazev_za_materialem, delka_mm):
    """Jak Vandr cte rozmery z nazvu za jmenem materialu: delka (prvni cislo, nahrazeno `delka_mm`) a pripadne `x` druhy rozmer -> velikost v m / m2."""
    m = re.match(r"([0-9.]+)(?:x([0-9.]+))?", nazev_za_materialem)
    if not m:
        raise ValueError("nelze precist delku: " + nazev_za_materialem)
    s = float(delka_mm) * 0.001
    if m.group(2):
        s *= float(m.group(2)) * 0.001
    return s


def vrat_material(nazev, materialy):
    for mat in materialy:
        if nazev.startswith(mat["name"]):
            return mat, nazev[len(mat["name"]):]
    return None, None


def nacti(unity_id):
    """(kusovnik dict, radek komponentu) z DB Vandru pro `components.unity_id`; kontroluje, ze soucet dilu = cena a vaha komponentu. Jen cteni."""
    spec = importlib.util.spec_from_file_location("w", os.path.join(REPO, "scripts/2026-09-22_vandr_fbx_watcher.py"))
    w = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(w)
    env = w._vandr_env()

    def q(conn, sql, args=None):
        cur = conn.cursor()
        cur.execute(sql, args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) if not isinstance(r, dict) else r for r in cur.fetchall()]

    cw = w._vandr_conn(env, env.get("DB_VANDRAWEE_WORK_DATABASE", "vandrawee_work"))
    cv = w._vandr_conn(env, env.get("DB_DATABASE", "vandrawee"))
    comp = q(cw, "SELECT * FROM components WHERE unity_id=%s", (unity_id,))
    if len(comp) != 1:
        raise SystemExit("komponent %s: nalezeno %d radku" % (unity_id, len(comp)))
    comp = comp[0]
    bom = q(cw, "SELECT part_id, count FROM components_parts WHERE component_id=%s", (comp["id"],))
    materialy = [{"name": m["name"], "price": float(m["price"]), "weight": float(m["weight"])} for m in q(cv, "SELECT name, price, weight FROM materials")]
    radky = []
    for b in bom:
        p = q(cv, "SELECT unity_id, price, weight FROM parts WHERE id=%s", (b["part_id"],))
        if len(p) != 1:
            raise SystemExit("dil id %s neni v parts" % b["part_id"])
        p = p[0]
        r = {"dil": p["unity_id"], "ks": int(b["count"]), "cena": float(p["price"]), "vaha": float(p["weight"])}
        mat, zbytek = vrat_material(p["unity_id"], materialy)
        if mat is not None:                                    # dil z materialu: delka-zavisla cena (Vandr oceni novy rozmer z materialu)
            s0 = velikost(zbytek, 1.0)
            r["material"] = {"jmeno": mat["name"], "cena_za_mm": round(mat["price"] * s0, 6), "vaha_za_mm": round(mat["weight"] * s0, 6),
                             "cena_materialu0": round(mat["price"] * velikost(zbytek, float(re.match(r"[0-9.]+", zbytek).group(0))), 4)}
        radky.append(r)
    soucet = round(sum(r["cena"] * r["ks"] for r in radky), 2)
    soucet_vaha = round(sum(r["vaha"] * r["ks"] for r in radky), 2)
    if abs(soucet - float(comp["price"])) > 0.01 or abs(soucet_vaha - float(comp["weight"])) > 0.01:
        raise SystemExit("soucet dilu (%.2f Kc, %.2f g) nesedi s cenou / vahou komponentu (%s, %s) - pravidlo Vandru se zmenilo" % (soucet, soucet_vaha, comp["price"], comp["weight"]))
    out = {"v": 1, "mena": "CZK", "komponent": unity_id, "zdroj": "DB Vandru (components, components_parts, parts, materials)", "snimek": os.popen("date +%F").read().strip(),
           "cena0": float(comp["price"]), "vaha0_g": float(comp["weight"]), "radky": radky}
    return out, comp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--komponent", required=True, help="unity_id komponentu (components.unity_id), napr. Kufrik.3x43.vysuv.1057.459")
    ap.add_argument("--vystup", required=True)
    a = ap.parse_args()
    out, _comp = nacti(a.komponent)
    with open(a.vystup, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("ok: %d radku, soucet %.2f Kc = cena komponentu, vaha %.2f g -> %s" % (len(out["radky"]), out["cena0"], out["vaha0_g"], a.vystup))


if __name__ == "__main__":
    sys.exit(main())
