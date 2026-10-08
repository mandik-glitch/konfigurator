"""Prepocet ulozenych cen sestav na balne 3 % (Robert 2026-10-01: "Balne 3%").

Stav pred prepoctem (overeno 2026-10-01): app_settings.packaging_pct = 3.0
(scena pocita 3 %), ale VSECH 530 sestav ma v price_summary balne 5 % a
12 karet na webu (shop_products.price_czk_placeholder = total_czk master
sestavy) tak ukazovalo cenu s 5 %. Priklad K-237 #128: dily a prace
16 721 Kc; 5 % = 836 -> 17 557 Kc (web), 3 % = 502 -> 17 223 Kc (scena).

Co dela (jen balne, nic jineho):
  subtotal  = total_czk - packaging_czk   (overi se proti souctu slozek)
  packaging = round(subtotal * 3 / 100)
  total     = subtotal + packaging
  montaz    = round(total * montaz_pct_applied / 100)   (informativni, neni v total)
  + price_summary.packaging_pct_applied = 3.0 (idempotence, dohledatelnost)
  karta (jen master sestava): price_czk_placeholder = total - ALE jen kdyz
  dnes presne sedi na stary total mastera (jinak ji nekdo upravil rucne ->
  nahlasit, neprepsat).
Nesaha na active (pravidlo 54), na rozpis dilu data.bom, na Vandr (VD-),
na nabidky/objednavky (historicke snimky).

Bezpecnost: zaloha pred zapisem, fresh-read pred zapisem kazde sestavy,
JSON_SET jen konkretnich klicu, rowcount kontrola, overeni z noveho spojeni.

Spusteni NA SERVERU v /opt/konfigurator:
    api/venv/bin/python3 scripts/2026-10-01_bot8_balne_3pct.py          (nahled)
    api/venv/bin/python3 scripts/2026-10-01_bot8_balne_3pct.py --apply  (zapis)
"""
import json
import os
import sys

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from _env import get_conn

NOVE_PCT = 3.0
ZAL_DIR = os.path.join(REPO, "backups", "2026-10-01_balne_3pct")
ZAL = os.path.join(ZAL_DIR, "pred_zapisem.json")


def prepocet(ps, montaz_pct_default):
    sub = ps["total_czk"] - ps["packaging_czk"]
    slozky = (ps.get("material_czk", 0) + ps.get("cut_czk", 0) + ps.get("profile_flat_fee_czk", 0)
              + ps.get("joint_czk", 0) + ps.get("accessory_czk", 0))
    if abs(slozky - sub) > 1:
        raise ValueError(f"subtotal {sub} nesedi na soucet slozek {slozky}")
    packaging = round(sub * NOVE_PCT / 100)
    total = sub + packaging
    mpct = ps.get("montaz_pct_applied") if ps.get("montaz_pct_applied") is not None else montaz_pct_default
    montaz = round(total * float(mpct) / 100)
    return sub, packaging, total, montaz


def nacti(cur):
    cur.execute("""
        SELECT pa.id, pa.is_master, pa.shop_product_id, pa.data, sp.sku, sp.name AS sp_name,
               sp.price_czk_placeholder
        FROM product_assemblies pa LEFT JOIN shop_products sp ON sp.id = pa.shop_product_id
        ORDER BY pa.id
    """)
    out = []
    for r in cur.fetchall():
        if r["sku"] and str(r["sku"]).startswith("VD-"):
            continue
        d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
        ps = (d or {}).get("price_summary") or {}
        if ps.get("total_czk") is None or ps.get("packaging_czk") is None:
            continue
        out.append((r, ps))
    return out


def main():
    apply = "--apply" in sys.argv
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='packaging_pct'")
    nastaveni = float(cur.fetchone()["setting_value"])
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='montaz_pct'")
    montaz_pct = float(cur.fetchone()["setting_value"])
    if abs(nastaveni - NOVE_PCT) > 1e-9:
        raise SystemExit(f"CHYBA: app_settings.packaging_pct = {nastaveni}, ne {NOVE_PCT} - nesoulad se scenou, nic nedelam")

    radky = nacti(cur)
    plan, karty, preskoceno, karty_rucne = [], [], 0, []
    for r, ps in radky:
        if ps.get("packaging_pct_applied") == NOVE_PCT:
            preskoceno += 1
            continue
        sub, packaging, total, montaz = prepocet(ps, montaz_pct)
        plan.append({"id": r["id"], "sku": r["sku"], "is_master": bool(r["is_master"]),
                     "shop_product_id": r["shop_product_id"], "total_dnes": ps["total_czk"],
                     "packaging_dnes": ps["packaging_czk"], "sub": sub, "packaging": packaging,
                     "total": total, "montaz": montaz})
        if r["is_master"] and r["shop_product_id"]:
            cena = float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None
            if cena is not None and round(cena) == ps["total_czk"]:
                karty.append({"shop_product_id": r["shop_product_id"], "sku": r["sku"], "nazev": r["sp_name"],
                              "assembly_id": r["id"], "cena_dnes": round(cena), "cena_nova": total})
            else:
                karty_rucne.append((r["shop_product_id"], r["sku"], cena, ps["total_czk"]))

    print(f"balne v nastaveni: {nastaveni} %  |  sestav k prepoctu: {len(plan)}  |  uz prepoctenych: {preskoceno}")
    print("=" * 96)
    print("CENA KARET NA WEBU (master sestava) - dily a prace + balne = cena")
    print("=" * 96)
    print(f"{'karta':>6} {'sku':<18} {'dily+prace':>11} {'balne 5 %':>10} {'dnes':>8} {'balne 3 %':>10} {'nove':>8} {'rozdil':>8}")
    for k in karty:
        p = next(x for x in plan if x["id"] == k["assembly_id"])
        print(f"{k['shop_product_id']:>6} {k['sku']:<18} {p['sub']:>11} {p['packaging_dnes']:>10} {k['cena_dnes']:>8} "
              f"{p['packaging']:>10} {k['cena_nova']:>8} {k['cena_nova'] - k['cena_dnes']:>+8}")
    s0, s1 = sum(k["cena_dnes"] for k in karty), sum(k["cena_nova"] for k in karty)
    if karty:
        print("-" * 96)
        print(f"karet: {len(karty)}   soucet dnes {s0:,} Kc -> nove {s1:,} Kc   rozdil {s1 - s0:+,} Kc "
              f"({(s1 / s0 - 1) * 100:+.2f} %)".replace(",", " "))
    if karty_rucne:
        print("\n!!! KARTY, KTERE NESEDI NA MASTER (rucne upravena cena?) - cena karty se NEPREPISE:")
        for sid, sku, cena, tot in karty_rucne:
            print(f"   karta {sid} {sku}: karta {cena}, master total {tot}")
    if plan:
        d0 = sum(p["total_dnes"] for p in plan)
        d1 = sum(p["total"] for p in plan)
        print(f"\nvsech {len(plan)} sestav (vc. nenapojenych na kartu): price_summary.total_czk {d0:,} -> {d1:,} Kc".replace(",", " "))
        p = plan[0]
        print(f"priklad #{p['id']} {p['sku'] or ''}: {p['sub']} + {p['packaging_dnes']} (5 %) = {p['total_dnes']}  ->  "
              f"{p['sub']} + {p['packaging']} (3 %) = {p['total']}; montaz {p['montaz']}")

    if not apply:
        print("\n(nahled, nic nezapsano - zapis: --apply)")
        return

    os.makedirs(ZAL_DIR, exist_ok=True)
    if os.path.exists(ZAL):
        raise SystemExit(f"CHYBA: zaloha {ZAL} uz existuje - neprepisuji ji (druhy beh?). Over stav a prejmenuj ji.")
    with open(ZAL, "w", encoding="utf-8") as f:
        json.dump({"sestavy": [{"id": r["id"], "price_summary": ps} for r, ps in radky],
                   "karty": [{"shop_product_id": k["shop_product_id"], "price_czk_placeholder": k["cena_dnes"]} for k in karty]},
                  f, ensure_ascii=False, indent=1, default=str)
    print(f"\nzaloha: {ZAL}")

    zapsano = 0
    for p in plan:
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (p["id"],))
        d = json.loads(cur.fetchone()["data"])
        ps = d.get("price_summary") or {}
        if ps.get("total_czk") != p["total_dnes"] or ps.get("packaging_czk") != p["packaging_dnes"]:
            conn.rollback()
            raise SystemExit(f"CHYBA: sestava #{p['id']} se mezitim zmenila - ROLLBACK, nic nezapsano")
        cur.execute("""
            UPDATE product_assemblies SET data = JSON_SET(data,
                '$.price_summary.packaging_czk', %s,
                '$.price_summary.total_czk', %s,
                '$.price_summary.montaz_czk', %s,
                '$.price_summary.packaging_pct_applied', %s
            ) WHERE id=%s
        """, (p["packaging"], p["total"], p["montaz"], NOVE_PCT, p["id"]))
        if cur.rowcount != 1:
            conn.rollback()
            raise SystemExit(f"CHYBA: UPDATE sestavy #{p['id']} rowcount={cur.rowcount} - ROLLBACK")
        zapsano += 1
    for k in karty:
        cur.execute("UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s AND ROUND(price_czk_placeholder)=%s",
                    (k["cena_nova"], k["shop_product_id"], k["cena_dnes"]))
        if cur.rowcount != 1:
            conn.rollback()
            raise SystemExit(f"CHYBA: karta {k['shop_product_id']} rowcount={cur.rowcount} (zmenila se?) - ROLLBACK")
    conn.commit()
    print(f"zapsano: {zapsano} sestav, {len(karty)} karet")

    conn2 = get_conn()
    c2 = conn2.cursor()
    chyby = 0
    for p in plan:
        c2.execute("SELECT data FROM product_assemblies WHERE id=%s", (p["id"],))
        ps = json.loads(c2.fetchone()["data"])["price_summary"]
        if ps["total_czk"] != p["total"] or ps["packaging_czk"] != p["packaging"]:
            chyby += 1
            print(f"   NESEDI #{p['id']}: {ps['total_czk']}/{ps['packaging_czk']}")
    for k in karty:
        c2.execute("SELECT price_czk_placeholder FROM shop_products WHERE id=%s", (k["shop_product_id"],))
        if round(float(c2.fetchone()["price_czk_placeholder"])) != k["cena_nova"]:
            chyby += 1
            print(f"   NESEDI karta {k['shop_product_id']}")
    if chyby:
        raise SystemExit(f"CHYBA: {chyby} hodnot po zapisu nesedi")
    print("OK - overeno z noveho spojeni")


if __name__ == "__main__":
    main()
