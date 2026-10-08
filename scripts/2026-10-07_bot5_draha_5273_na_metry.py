#!/opt/konfigurator/api/venv/bin/python
"""Valeckova draha 40 mm O24 (#5273): prodej PO METRECH (bot5, 2026-10-07; Robert pres bot9: "rikali jsme prodej po metrech" - muj zapis "draha na kusy" byl nedorozumeni).
Mechanismus metraze v e-shopu = shop_products.unit = 'm' (jako 39 karet, napr. kat. 196 Kryci listy): karta ukazuje "za m · bez DPH", mnozstvi v kosiku/objednavce/nabidce je v metrech, cena radku = cena za metr x metry.
Cena za metr = ceil(USD/m x kurz x koeficient kategorie 1,0) = stejny vzorec jako u 'kus', takze nocni prepocet ceny se nemeni (278 Kc/m). Meni se JEN sloupec unit; puvodni radek se zalohuje do backups/.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_bot5_draha_5273_na_metry.py"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _env import get_conn  # noqa: E402

conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT id, sku, name, unit, active, price_czk_placeholder, dogus_list_price_usd, dogus_price_rate_used FROM shop_products WHERE id=5273 AND sku='2.2.016.024.040.01'")
r = cur.fetchone()
if not r or not r["active"]:
    sys.exit(f"ZASTAVENO: neocekavany stav {r}")
if r["unit"] == "m":
    sys.exit("hotovo uz drive (unit je 'm')")
zaloha = os.path.join(os.path.dirname(HERE), "backups", "2026-10-07_draha_5273_pred_zmenou_na_metry.json")
json.dump({k: (str(v) if v is not None else None) for k, v in r.items()}, open(zaloha, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
cur.execute("UPDATE shop_products SET unit='m' WHERE id=5273 AND active=1")
cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'update','shop_product',5273,'valeckova draha 40 mm: prodej po metrech (unit m), cena za metr 278 Kc bez DPH beze zmeny; Robert pres bot9 (nedorozumeni \"na kusy\"); bot5')")
conn.commit()
cur.execute("SELECT unit, active, price_czk_placeholder FROM shop_products WHERE id=5273")
print("ZAPSANO:", cur.fetchone())
