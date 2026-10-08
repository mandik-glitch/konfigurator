#!/usr/bin/env python3
"""Zalozeni produktove karty konfigurovatelneho stolu SYSTEM 41 = ERGONOMICKY STUL SSE (podelniky 40x40 + nohy SSE) a registrace v app_settings.configurator_products (bot8, 2026-10-05).

Robert 2026-10-05: ctvrty generator stolu "ergonomicky stul SSE system 40" (tvar #581 Noha SSE), kompatibilni s ostatnimi. Kontrakt konfiguratoru (api/stul_shop.py) potrebuje JEDNO
shop_products.id konfigurovatelneho produktu PRO KAZDY SYSTEM (karty: 30 #4934 STUL.SYSTEM30.KONF, 40 #4954, 35 #4955). Tenhle skript zalozi kartu STUL.SYSTEM41.KONF:
NEAKTIVNI (active=0, pravidlo 54 - aktivni ruce nepřepinat), standardne jako navrh karty (SKU, slug pres product_slug, jednotka ks); cena se nezapisuje (bere se z resolve).
Do `configurator_products` jen PRIDA zaznam {"<id>": "stul_system41"} (ostatni zaznamy zustavaji).

  api/venv/bin/python3 scripts/2026-10-05_sse/zaloz_kartu_sse.py            (nahled, nic nezapise)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-05_sse/zaloz_kartu_sse.py --apply

Idempotentni: existuje-li uz karta se SKU `STUL.SYSTEM35.KONF`, pouzije se. Zapis se overuje rowcountem a cteni z noveho spojeni.
POZOR: pridani zaznamu do `configurator_products` zapne routy pro recept stul_system41 AZ PO NASAZENI kodu api/stul_shop.py (RECEPTY obsahuji 41; deploy 0:00 / 12:30); do te doby stary kod
zaznam neznamy recept ignoruje (konfigurovatelny(id) = False -> 404), nic se tim nerozbije."""
import json
import os
import sys
import threading

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
SKU = "STUL.SYSTEM41.KONF"
NAZEV = "Ergonomický stůl SSE – konfigurovatelný"
RECEPT = "stul_system41"
apply = "--apply" in sys.argv

if not os.environ.get("DB_HOST"):
    from _env import get_conn  # nahled bez systemd-run (cte jen)
    conn = get_conn()
    slug_fn = None
else:
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    import app as appmod  # noqa: E402
    threading.Thread.start = _o
    conn = appmod.get_conn()
    slug_fn = appmod._product_slug_for_name
cur = conn.cursor()
cur.execute("SELECT id, sku, name, slug, active FROM shop_products WHERE sku=%s", (SKU,))
karta = cur.fetchone()
cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='configurator_products'")
row = cur.fetchone()
mapa = json.loads(row["setting_value"]) if row and row["setting_value"] else {}
print("karta se SKU", SKU, ":", karta or "NEEXISTUJE", "| configurator_products:", mapa or "nenastaveno")
if not apply:
    print("\n(nahled, nic nezapsano - zapis: --apply pres systemd-run, viz hlavicka)")
    sys.exit(0)

if karta is None:
    cur.execute("INSERT INTO shop_products (sku, name, slug, unit, active) VALUES (%s,%s,%s,%s,0)",
                (SKU, NAZEV, slug_fn(cur, NAZEV), "ks"))
    if cur.rowcount != 1:
        conn.rollback()
        raise SystemExit(f"CHYBA: INSERT karty rowcount={cur.rowcount} - ROLLBACK")
    pid = cur.lastrowid
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                (None, "create", "shop_product", pid, f"bot8: neaktivni karta konfigurovatelneho stolu SSE system 41 ({SKU}), ctvrty generator stolu (podelniky 40x40 + nohy SSE)"))
else:
    pid = karta["id"]
mapa[str(pid)] = RECEPT
hodnota = json.dumps(mapa, sort_keys=True)
if row:
    cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key='configurator_products'", (hodnota,))
else:
    cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES ('configurator_products', %s)", (hodnota,))
if cur.rowcount != 1:
    conn.rollback()
    raise SystemExit(f"CHYBA: zapis nastaveni rowcount={cur.rowcount} - ROLLBACK")
conn.commit()
c2 = appmod.get_conn().cursor() if os.environ.get("DB_HOST") else get_conn().cursor()
c2.execute("SELECT id, sku, name, slug, active FROM shop_products WHERE id=%s", (pid,))
k2 = c2.fetchone()
c2.execute("SELECT setting_value FROM app_settings WHERE setting_key='configurator_products'")
v2 = c2.fetchone()["setting_value"]
assert k2 and k2["active"] == 0 and json.loads(v2).get(str(pid)) == RECEPT, (k2, v2)
print(f"zapsano a overeno z noveho spojeni: karta #{pid} {k2['sku']} (active=0, slug {k2['slug']}), configurator_products = {v2}")
