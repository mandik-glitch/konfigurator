#!/usr/bin/env python3
"""Napoji cenu Vandr karet (shop_products.price_czk_placeholder) na
zdroj pravdy - vandrawee_work.stored_models (admin
test.logiman.cz/admin/work-stored-model). Robert pres bot3, 2026-09-25:
"vztah je tam jednoduchý, prostě cena na webu je cena v DB" - POMER 1:1,
zadny koeficient, zadna DPH.

ZDROJ PRAVDY (overeno v kodu, ne odhad): StoredModel::price()
(/opt/vandrawee/web/app/Models/VanDraweeWork/StoredModel.php:84) =
left_part->price + right_part->price + bulkhead_part->price (kazda
cast NULL-safe, chybejici cast prispiva 0). Tenhle skript pocita
STEJNY soucet primo SQL JOINem nad stored_model_parts.price.

PAROVANI: `shop_products.vandr_stored_model_uuid` (viz
sql/2026-09-25_shop_products_vandr_stored_model_uuid.sql) - explicitni
sloupec, NE parsovani SKU za behu (Robert: "musí se to normálně na
sebe napárovat"). Tenhle skript ho KAZDY beh doplni/overi (idempotentni -
napoji jen kartu, jejiz UUID cast SKU skutecne existuje v
stored_models, NIKDY nevymysli par u zbylych), ale i tohle doplneni je
JEN v pameti v dry-run rezimu - do DB se pise vyhradne s --apply.

DRY-RUN JE VYCHOZI CHOVANI (Robert vyslovne: "nic nepřepisuj" - prvni
verze nesmi sama zapsat jedinou cenu). Vystup: tabulka karta/SKU/cena
dnes/cena z adminu/rozdil Kc/rozdil %/aktivni. Az Robert schvali nad
touhle tabulkou, teprve pak --apply.

Dotcene jen SKU 'VD-%' (1. vetev/klasicke profily maji jinou
cenotvorbu, viz scripts/2026-08-09_dogus_price_recompute.py). Karta
se nikdy neaktivuje ani nedeaktivuje (pravidlo 54) - jen cena.

DOPLNENO 2026-09-26 (Robert primo: "kdyz se zmeni cena v db musi se to
zmenit i na eshopu", ne jen 1x denne): skutecne OKAMZITE napojeni ted
dela api/vandr_price_webhook.py - vanDrawee sam zavola pri ulozeni ceny
casti. Tenhle denni beh zustava jako ZALOZNI SIT (webhook muze selhat -
vypadek site/DB, fronta jobu zpozdena) a jako jediny mechanismus, ktery
resi PAROVANI novych karet (webhook resi jen JIZ parovane UUID). Oba
pouzivaji stejny vzorec z scripts/_vandr_cena.py - nemuzou se rozejit.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-25_vandr_cena_sync.py
    api/venv/bin/python3 scripts/2026-09-25_vandr_cena_sync.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402
from _vandr_cena import vandr_conn as _vandr_conn, vsechny_ceny as _admin_ceny  # noqa: E402

BACKUP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backups", "2026-09-25_vandr_cena_sync_pred_zapisem.json",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== Vandr cena sync (zdroj: vandrawee admin) — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    vconn = _vandr_conn()
    try:
        with vconn.cursor() as vcur:
            admin_ceny = _admin_ceny(vcur)
    finally:
        vconn.close()
    print(f"Sestav v adminu (stored_models): {len(admin_ceny)}\n")

    kconn = get_conn()
    try:
        with kconn.cursor() as cur:
            cur.execute("SELECT id, sku, name, active, vandr_stored_model_uuid, price_czk_placeholder "
                        "FROM shop_products WHERE sku LIKE 'VD-%'")
            karty = cur.fetchall()
            print(f"Karet se SKU 'VD-%': {len(karty)}\n")

            # --- parovani (v pameti, zapis jen s --apply) ---
            parovani_updates = []
            nesparovano = []
            for k in karty:
                uuid_candidate = k["sku"][3:]  # za "VD-"
                skutecny_par = uuid_candidate if uuid_candidate in admin_ceny else None
                if skutecny_par is not None and k["vandr_stored_model_uuid"] != skutecny_par:
                    parovani_updates.append((k["id"], skutecny_par))
                if skutecny_par is None:
                    nesparovano.append(k)

            if parovani_updates:
                print(f"Párování (nové/změněné): {len(parovani_updates)}")
                for pid, u in parovani_updates:
                    print(f"  [{pid}] -> {u}")
            print(f"\nBEZ PROTĚJŠKU v adminu ({len(nesparovano)}) - vazba zůstává NULL, žádný pár se nevymýšlí:")
            for k in nesparovano:
                print(f"  [{k['id']}] {k['sku']} (active={k['active']}) — {k['name']}")

            if args.apply:
                for pid, u in parovani_updates:
                    cur.execute("UPDATE shop_products SET vandr_stored_model_uuid=%s WHERE id=%s", (u, pid))
                    if cur.rowcount != 1:
                        raise RuntimeError(f"párování UPDATE id={pid} zasáhl {cur.rowcount} řádků místo 1 - rollback")

            # --- cenova tabulka (jen spárované) ---
            parovani_map = dict(parovani_updates)
            radky = []
            for k in karty:
                uuid_par = parovani_map.get(k["id"], k["vandr_stored_model_uuid"])
                if uuid_par is None or uuid_par not in admin_ceny:
                    continue
                cena_dnes = float(k["price_czk_placeholder"]) if k["price_czk_placeholder"] is not None else None
                cena_admin = round(admin_ceny[uuid_par])
                rozdil_kc = None if cena_dnes is None else round(cena_admin - cena_dnes)
                rozdil_pct = None if not cena_dnes else round((cena_admin - cena_dnes) / cena_dnes * 100, 1)
                radky.append({
                    "id": k["id"], "sku": k["sku"], "name": k["name"], "active": bool(k["active"]),
                    "cena_dnes": cena_dnes, "cena_admin": cena_admin,
                    "rozdil_kc": rozdil_kc, "rozdil_pct": rozdil_pct,
                })

            print(f"\n=== CENOVÁ TABULKA ({len(radky)} spárovaných karet) ===")
            print(f"{'id':>5} {'aktivní':>7} {'cena dnes':>10} {'cena admin':>11} {'rozdíl Kč':>10} {'rozdíl %':>9}  SKU / název")
            for r in sorted(radky, key=lambda x: (x["rozdil_kc"] is None, x["rozdil_kc"] or 0)):
                cena_dnes_str = "—" if r["cena_dnes"] is None else str(r["cena_dnes"])
                rozdil_kc_str = "" if r["rozdil_kc"] is None else f"{r['rozdil_kc']:+}"
                rozdil_pct_str = "" if r["rozdil_pct"] is None else f"{r['rozdil_pct']:+.1f}"
                aktivni_str = "ANO" if r["active"] else "ne"
                print(f"{r['id']:>5} {aktivni_str:>7} {cena_dnes_str:>10} {r['cena_admin']:>11} "
                      f"{rozdil_kc_str:>10} {rozdil_pct_str:>9}  {r['sku']} / {r['name'][:50]}")

            zvysi = sum(1 for r in radky if r["rozdil_kc"] and r["rozdil_kc"] > 0)
            snizi = sum(1 for r in radky if r["rozdil_kc"] and r["rozdil_kc"] < 0)
            beze_zmeny = sum(1 for r in radky if r["rozdil_kc"] == 0)
            chybi_dnes = sum(1 for r in radky if r["cena_dnes"] is None)
            soucet_dnes = sum(r["cena_dnes"] or 0 for r in radky)
            soucet_admin = sum(r["cena_admin"] for r in radky)
            aktivnich_zmena = sum(1 for r in radky if r["active"] and r["rozdil_kc"])
            print(f"\nSouhrn: stoupne u {zvysi}, klesne u {snizi}, beze změny {beze_zmeny}, "
                  f"chybí dnešní cena u {chybi_dnes}. Aktivních karet se změnou ceny: {aktivnich_zmena}.")
            print(f"Součet dnes: {soucet_dnes:,.0f} Kč -> podle adminu: {soucet_admin:,.0f} Kč "
                  f"({soucet_admin - soucet_dnes:+,.0f} Kč, {(soucet_admin - soucet_dnes) / soucet_dnes * 100:+.2f} %)"
                  .replace(",", " "))

            if args.apply:
                os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
                with open(BACKUP_PATH, "w", encoding="utf-8") as f:
                    json.dump({"parovani": parovani_updates, "ceny": radky}, f, ensure_ascii=False, indent=2)
                print(f"\nZáloha zapsána do {BACKUP_PATH}")
                zapsano = 0
                for r in radky:
                    if r["rozdil_kc"] == 0:
                        continue
                    cur.execute("UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s",
                                (r["cena_admin"], r["id"]))
                    if cur.rowcount != 1:
                        raise RuntimeError(f"cena UPDATE id={r['id']} zasáhl {cur.rowcount} řádků místo 1 - rollback")
                    zapsano += 1
                kconn.commit()
                print(f"HOTOVO: napárováno {len(parovani_updates)}, cena zapsána u {zapsano} karet.")
            else:
                print("\n(dry-run - nic nezapsáno, spusť s --apply pro skutečný zápis)")
    except Exception:
        kconn.rollback()
        raise
    finally:
        kconn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
