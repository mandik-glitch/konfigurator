#!/opt/konfigurator/api/venv/bin/python
"""Aktivace karty #5273 (valeckova draha 40 mm O24, hlinikova, 278 Kc/ks) na PRIMY klik Roberta 2026-10-07 ("Aktivovat hned"); pravidlo 54: bot sam nikdy, tohle je jeho rozhodnuti.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_bot5_aktivace_draha_5273.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT active, activated_at, price_czk_placeholder FROM shop_products WHERE id=5273 AND sku='2.2.016.024.040.01'")
r = cur.fetchone()
if not r or r["price_czk_placeholder"] is None or r["active"] or r["activated_at"] is not None:
    sys.exit(f"ZASTAVENO: neocekavany stav {r}")
cur.execute("UPDATE shop_products SET active=1, activated_at=NOW() WHERE id=5273 AND active=0 AND price_czk_placeholder IS NOT NULL")
cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'update','shop_product',5273,'aktivace karty 5273 (valeckova draha 40 mm, 278 Kc/ks) na PRIMY klik Roberta 2026-10-07; bot5 provedl')")
conn.commit()
cur.execute("SELECT active, price_czk_placeholder FROM shop_products WHERE id=5273")
print("ZAPSANO:", cur.fetchone())
