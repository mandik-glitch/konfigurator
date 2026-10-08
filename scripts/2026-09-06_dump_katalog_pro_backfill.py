#!/usr/bin/env python3
"""Dump katalogu presne tak, jak ho vidi /api/katalog (vc. koeficientu).

DUVOD: backfill kusovniku/ceny sestav (2026-09-06_backfill_bom_price.js)
potrebuje STEJNA cisla, jaka by scena pouzila pri zivem ulozeni - ne vlastni
odhad. Misto volani pres HTTP (endpoint je @staff_required, nemam staff
session a nemam zakladat testovaci ucet) volam produkcni funkce PRIMO
(fetch_katalog_parts + get_scene_price_coefficient) - presne to, co dela
telo routy /api/katalog (api/app.py, funkce katalog()), jen bez HTTP vrstvy.

Koeficientovy krok NIZE je DOSLOVNA KOPIE tela te routy (viz api/app.py,
komentar tam vysvetluje proc se aplikuje TADY a ne uvnitr fetch_katalog_parts) -
kdyby se logika routy zmenila, tenhle skript je potreba prekopirovat znovu,
ne "opravit z hlavy".

Vystup: /tmp/katalog_pro_backfill.json - pole objektu presne ve tvaru,
jaky /api/katalog vraci v poli "parts".

bot8 2026-09-06. READ-ONLY.
"""
import json
import os
import sys

sys.path.insert(0, "/opt/konfigurator/api")
os.chdir("/opt/konfigurator/api")
for _l in open(".env"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _k, _v = _l.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
import app as A  # noqa: E402

OUT = "/tmp/katalog_pro_backfill.json"

parts = A.fetch_katalog_parts()
conn = A.get_conn()
try:
    with conn.cursor() as cur:
        coef = A.get_scene_price_coefficient(cur)
finally:
    conn.close()

# --- DOSLOVNA KOPIE tela /api/katalog (api/app.py, funkce katalog()) ---
if coef != 1.0:
    for p in parts:
        base = p.get("price_czk_approx_PLACEHOLDER")
        if base is not None:
            p["price_czk_approx_PLACEHOLDER"] = round(base * coef, 2)
        # price_per_cut_czk (cena rezu) se ZAMERNE nenasobi.
# --- konec kopie ---

# --- PRICING_CONFIG (api/admin_settings.py, GET /api/pricing-config) ---
conn = A.get_conn()
try:
    with conn.cursor() as cur:
        joint_price = A.get_setting(cur, "joint_price_czk", "0")
        profile_flat_fee = A.get_setting(cur, "profile_flat_fee_czk", "0")
        packaging_pct = A.get_setting(cur, "packaging_pct", "0")
        montaz_pct = A.get_setting(cur, "montaz_pct", "0")
        cur.execute("""
            SELECT id, name, price_czk, qty_per_joint FROM cfg_accessories
            WHERE active=1 ORDER BY sort_order, name
        """)
        accessories = [
            {"id": r["id"], "name": r["name"], "price_czk": float(r["price_czk"]),
             "qty_per_joint": float(r["qty_per_joint"])}
            for r in cur.fetchall()
        ]
finally:
    conn.close()
pricing_config = {
    "joint_price_czk": float(joint_price) if joint_price is not None else 0,
    "profile_flat_fee_czk": float(profile_flat_fee) if profile_flat_fee is not None else 0,
    "packaging_pct": float(packaging_pct) if packaging_pct is not None else 0,
    "montaz_pct": float(montaz_pct) if montaz_pct is not None else 0,
    # bot8 2026-09-13: chybelo (viz GET /api/pricing-config v admin_settings.py,
    # "posila se ciste jako HODNOTA K OTISKU") - bez tohohle vychazelo
    # price_summary.scene_price_coefficient_applied vzdy 1 (fallback), i kdyz
    # `coef` vyse uz byl skutecne zapecen do price_czk_approx_PLACEHOLDER -
    # metadatove pole tak lhalo, ze zadne navyseni neni aplikovano.
    "scene_price_coefficient": coef,
    "accessories": accessories,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"parts": parts, "price_coefficient": coef, "pricing_config": pricing_config},
               f, ensure_ascii=False)
print(f"Zapsano {len(parts)} katalogovych dilu (koeficient={coef}) -> {OUT}")
print(f"  pricing_config: {pricing_config}")
