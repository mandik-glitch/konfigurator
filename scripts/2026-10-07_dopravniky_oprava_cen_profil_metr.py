#!/opt/konfigurator/api/venv/bin/python
"""Oprava cen hotovych valeckovych dopravniku (bot5, 2026-10-07): cena profilu u Dogusu je za 1 METR, recept v1 ji delil delkou tyce (3 m) -> boční profily a spodni ram vychazely 3x levneji.
Robert 2026-10-07 (klik "Opravit vsech 78 hned"): prepocet cen + souctu USD podle opraveneho receptu (scripts/dopravniky_cena_z_komponent.py), kurz zustava ten, se kterym se karta cenila
(shop_products.dogus_price_rate_used karty). Meni JEN price_czk_placeholder a dogus_list_price_usd (kusovnik a nazvy se nemeni, mnozstvi jsou stejna). Karty zustavaji aktivni. Zaloha puvodnich hodnot do backups/.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_dopravniky_oprava_cen_profil_metr.py [--apply]"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from _env import get_conn  # noqa: E402

_spec = importlib.util.spec_from_file_location("dcz", os.path.join(HERE, "dopravniky_cena_z_komponent.py"))
DCZ = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DCZ)
ZALOHA = os.path.join(REPO, "backups", "2026-10-07_dopravniky_ceny_pred_opravou_profil_metr.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    recept = json.load(open(os.path.join(REPO, "docs", "dopravniky_recept.json"), encoding="utf-8"))
    koef, prirazka = recept["koeficient_kategorie"], recept["vychozi"]["prirazka_pct"]
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, sku, price_czk_placeholder, dogus_list_price_usd, dogus_price_rate_used, active FROM shop_products WHERE category_id=324 AND price_czk_placeholder IS NOT NULL ORDER BY sku")
        karty = cur.fetchall()
        usd = DCZ.nacti_usd(cur, recept, [k["sku"] for k in karty])
        zmeny = []
        for k in karty:
            radky, soucet = DCZ.kusovnik(k["sku"], recept, usd, None)
            nova = DCZ.cena_czk(soucet, float(k["dogus_price_rate_used"]), koef, prirazka)
            zmeny.append({"id": k["id"], "sku": k["sku"], "stara_cena": float(k["price_czk_placeholder"]), "nova_cena": nova,
                          "stary_usd": float(k["dogus_list_price_usd"]), "novy_usd": soucet, "kurz": float(k["dogus_price_rate_used"])})
        pc = [z["nova_cena"] / z["stara_cena"] * 100 - 100 for z in zmeny]
        print(f"{len(zmeny)} karet; zvyseni {min(pc):.1f} az {max(pc):.1f} % (prumer {sum(pc) / len(pc):.1f} %)")
        for z in (zmeny[0], zmeny[len(zmeny) // 2], zmeny[-1]):
            print(f"  {z['sku']}: {z['stara_cena']:.0f} -> {z['nova_cena']} Kc ({z['stary_usd']} -> {z['novy_usd']} USD)")
        if not a.apply:
            print("(nahled, nic nezapsano; --apply)")
            return
        if os.path.exists(ZALOHA):
            sys.exit("ZASTAVENO: zaloha uz existuje - oprava uz probehla?")
        json.dump(zmeny, open(ZALOHA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for z in zmeny:
            cur.execute("UPDATE shop_products SET price_czk_placeholder=%s, dogus_list_price_usd=%s WHERE id=%s AND category_id=324", (z["nova_cena"], z["novy_usd"], z["id"]))
        cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'update','shop_product',NULL,%s)",
                    (f"oprava cen {len(zmeny)} valeckovych dopravniku: cena profilu je za 1 m, ne za tyc (Robert 2026-10-07: opravit hned); zvyseni {min(pc):.1f}-{max(pc):.1f} %",))
        conn.commit()
        cur.execute("SELECT id, price_czk_placeholder, dogus_list_price_usd FROM shop_products WHERE category_id=324 AND price_czk_placeholder IS NOT NULL")
        ted = {r["id"]: (float(r["price_czk_placeholder"]), float(r["dogus_list_price_usd"])) for r in cur.fetchall()}
        spatne = [z["sku"] for z in zmeny if ted.get(z["id"]) != (float(z["nova_cena"]), float(z["novy_usd"]))]
        print("ZAPSANO a overeno SELECTem; neshoda:", spatne if spatne else "zadna")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
