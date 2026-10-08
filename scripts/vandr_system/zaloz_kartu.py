#!/usr/bin/env python3
"""Zalozeni produktove karty komponentu Vandr systemu a navazani na registr (bot10, 2026-10-05; docs/VANDR_SYSTEM.md).

Zalozi NEAKTIVNI kartu (active=0, pravidlo 54 - aktivni ruce nepřepinat) v shop_products se SKU `VDK-<KOD>` (kod komponentu velkymi pismeny), slugem pres product_slug a jednotkou ks;
cena se do karty NEZAPISUJE (jediny zdroj ceny je registr: api/vandr_system.py::cena(), cena zavisi na sirce), kategorie zustava prazdna (nazev a umisteni urci bot7 / Robert), model
(`glb_file`) se do karty nedava (Vandr 3D se nesmi dostat verejne). Pak zapise SKU a id karty do `vd_komponenty`. Idempotentni: existuje-li uz karta s timto SKU, pouzije se.

  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/vandr_system/zaloz_kartu.py --kod kufrik-3x43-vysuv-d459 --nazev "Výsuv pro 3 systainery – šířka na míru"            (nahled)
      ... stejne s --apply                                                                                                                             (zapis)

Zapis se overuje rowcountem a nactenim z NOVEHO spojeni."""
import argparse
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
import vandr_system as VS  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--kod", required=True)
ap.add_argument("--nazev", required=True, help="zakaznicky nazev karty (cesky; bez 'Vandr' / 'vanDrawee')")
ap.add_argument("--apply", action="store_true")
a = ap.parse_args()
SKU = VS.kod_na_sku(a.kod)
low = a.nazev.lower()
if "vandr" in low or "vandrawee" in low:
    raise SystemExit("nazev karty nesmi obsahovat 'Vandr' / 'vanDrawee' (zakaznicky viditelny text)")

if not os.environ.get("DB_HOST"):
    raise SystemExit("spust pres systemd-run s EnvironmentFile=/opt/konfigurator/api/.env (viz hlavicka)")
_o = threading.Thread.start
threading.Thread.start = lambda self, *x, **k: None if self.name == "render-dozorce" else _o(self, *x, **k)
import app as appmod  # noqa: E402
threading.Thread.start = _o
conn = appmod.get_conn()
cur = conn.cursor()
komp = VS.nacti_komponentu(cur, a.kod)
if komp is None:
    raise SystemExit("komponenta %s neni v registru (nejdriv pridej_komponentu.py)" % a.kod)
cur.execute("SELECT id, sku, name, slug, active FROM shop_products WHERE sku=%s", (SKU,))
karta = cur.fetchone()
print("komponenta:", komp["kod"], "| registr: sku", komp["sku"], "karta", komp["shop_product_id"], "| karta se SKU", SKU, ":", karta or "NEEXISTUJE")
if not a.apply:
    print("\n(nahled, nic nezapsano; zapis: --apply pres systemd-run, viz hlavicka)")
    sys.exit(0)

if karta is None:
    cur.execute("INSERT INTO shop_products (sku, name, slug, unit, active) VALUES (%s,%s,%s,%s,0)", (SKU, a.nazev, appmod._product_slug_for_name(cur, a.nazev), "ks"))
    if cur.rowcount != 1:
        conn.rollback()
        raise SystemExit(f"CHYBA: INSERT karty rowcount={cur.rowcount} - ROLLBACK")
    pid = cur.lastrowid
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                (None, "create", "shop_product", pid, f"bot10: neaktivni karta komponentu Vandr systemu ({SKU}), cena podle sirky z registru vd_komponenty"))
else:
    pid = karta["id"]
VS.pripoj_kartu(cur, a.kod, pid)
conn.commit()

import pymysql  # noqa: E402
c2 = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 3306)), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                     database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)   # app.get_conn() je sdilene vlaknu - overeni z uplne noveho spojeni
cu2 = c2.cursor()
cu2.execute("SELECT id, sku, name, slug, active, category_id, price_czk_placeholder, glb_file FROM shop_products WHERE id=%s", (pid,))
k2 = cu2.fetchone()
d2 = VS.nacti_komponentu(cu2, a.kod)
print("karta:", k2)
print("registr: sku", d2["sku"], "shop_product_id", d2["shop_product_id"])
assert k2 and k2["sku"] == SKU and int(k2["active"]) == 0, k2
assert d2["sku"] == SKU and d2["shop_product_id"] == pid, d2
print("OK")
