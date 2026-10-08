#!/usr/bin/env python3
"""Zalozeni produktove karty konfigurovatelneho stolu (system 30) a registrace v app_settings.configurator_products (bot8, 2026-10-02).

Robert (pres bot16): konfigurator stolu ma jit na prvni mini-shop (Packstations, cesky). Kontrakt konfiguratoru (api/stul_shop.py)
potrebuje JEDNO shop_products.id konfigurovatelneho produktu. Karta se zaklada NEAKTIVNI (active=0, pravidlo 54 - aktivni ruce nepřepinat),
standardnim zpusobem jako navrh karty u sestavy (SKU, slug, jednotka ks). Cena se nezapisuje - mini-shop bere cenu z resolve.

  api/venv/bin/python3 scripts/2026-10-02_bot8_stul_karta.py            (nahled, nic nezapise)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-02_bot8_stul_karta.py --apply

Idempotentni: existuje-li uz karta se SKU `STUL.SYSTEM30.KONF`, pouzije se; setting `configurator_products` se jen DOPLNI o tuhle kartu
(ostatni polozky zustavaji). Vystup: id karty a obsah nastaveni; zapis se overuje cteni z noveho spojeni a rowcount.
"""
import json
import os
import sys
import threading

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
SKU = "STUL.SYSTEM30.KONF"
NAZEV = "Pracovní stůl systém 30 – konfigurovatelný"
RECEPT = "stul_system30"
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
                (None, "create", "shop_product", pid, f"bot8: neaktivni karta konfigurovatelneho stolu system 30 ({SKU}) pro mini-shop Packstations"))
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
