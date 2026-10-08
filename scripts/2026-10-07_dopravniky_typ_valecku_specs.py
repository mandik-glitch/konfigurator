#!/opt/konfigurator/api/venv/bin/python
"""Hotove valeckove dopravniky: do product_specs_json pridat klic "Typ válečku" (bot5, 2026-10-07; Robert pres bot9: "stitky pro rychle filtrovani podle delky, ne desitky stejnych obrazku" - tabulka/filtry stavi bot16, data se nemaji hadat z nazvu).
Typ se bere z prefixu SKU (16.10.01.050 = hlinik hladky, 16.12.01.050 = hlinik vroubkovany, 16.10.01.051 = ocel). Ostatni klice (Roller, Roller length, Conveyor Length, Height, Between the Roller Axes, Side Barrier) uz jsou.
Jen karty, kde klic chybi nebo se lisi; nic jineho se nemeni. Zaloha puvodnich specs do backups/. Bez --apply jen nahled.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_dopravniky_typ_valecku_specs.py [--apply]"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from _env import get_conn  # noqa: E402

KLIC = "Typ válečku"
TYPY = {"16.10.01.050": "Hliník hladký", "16.12.01.050": "Hliník vroubkovaný", "16.10.01.051": "Ocel"}
SKU_RE = re.compile(r"^(16\.1[02]\.01\.05[01])\.\d{4}\.\d{4}\.0$")


def typ_podle_sku(sku):
    m = SKU_RE.match(sku or "")
    return TYPY.get(m.group(1)) if m else None


def uprav_specs(specs, typ):
    """-> nove specs se klicem KLIC hned za 'Roller' (jinak na konec), ostatni poradi beze zmeny."""
    out = {}
    vlozeno = False
    for k, v in specs.items():
        if k == KLIC:
            continue
        out[k] = v
        if k == "Roller":
            out[KLIC] = typ
            vlozeno = True
    if not vlozeno:
        out[KLIC] = typ
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, sku, product_specs_json FROM shop_products WHERE category_id=324 AND sku REGEXP '^16\\\\.1[02]\\\\.01\\\\.05[01]\\\\.'")
        zmeny, nezname = [], []
        for r in cur.fetchall():
            typ = typ_podle_sku(r["sku"])
            if not typ:
                nezname.append(r["sku"])
                continue
            specs = json.loads(r["product_specs_json"]) if isinstance(r["product_specs_json"], str) else (r["product_specs_json"] or {})
            if not specs:
                nezname.append(r["sku"] + " (bez specs)")
                continue
            if specs.get(KLIC) != typ:
                zmeny.append((r["id"], r["sku"], r["product_specs_json"], json.dumps(uprav_specs(specs, typ), ensure_ascii=False)))
        print(f"ke zmene {len(zmeny)} karet; neznamy tvar SKU / bez specs: {nezname}")
        if not a.apply:
            print("(nahled, nic nezapsano; --apply)")
            return
        zaloha = os.path.join(REPO, "backups", "2026-10-07_dopravniky_specs_pred_typem_valecku.json")
        if os.path.exists(zaloha):
            sys.exit("ZASTAVENO: zaloha uz existuje")
        json.dump([{"id": z[0], "sku": z[1], "specs": z[2]} for z in zmeny], open(zaloha, "w", encoding="utf-8"), ensure_ascii=False)
        for pid, _sku, _old, nove in zmeny:
            cur.execute("UPDATE shop_products SET product_specs_json=%s WHERE id=%s", (nove, pid))
        conn.commit()
        cur.execute("SELECT COUNT(*) n FROM shop_products WHERE category_id=324 AND JSON_UNQUOTE(JSON_EXTRACT(product_specs_json, '$.\"Typ válečku\"')) IS NOT NULL")
        print("ZAPSANO: karet s klicem Typ valecku:", cur.fetchone()["n"])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
