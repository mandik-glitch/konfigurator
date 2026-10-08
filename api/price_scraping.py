"""Kontrola/nacteni ceny PRODUKTU z logiman.cz na pozadani z adminu.

Vycleneno z api/app.py (bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 6) - cisty presun, zadna zmena chovani/URL.

Pozn.: samotny scraping helper `scrape_logiman_product_price` a
`refresh_price_for_product` ZUSTAVAJI v app.py, protoze je primo pouziva
i `run_product_price_refresh_cli()` (tydenni systemd timer
konfigurator-refresh-product-prices.timer, viz `if __name__ ==
"__main__"` blok na konci app.py) - ten kod bezi jeste PRED tim, nez se
na konci app.py naimportuji vyclenene moduly (viz komentar "OPRAVA
bot10" tamtez), takze by import z tohohle modulu v tu chvili selhal.
Stejne tak `refresh_price_for_row` (profily, ne produkty) zustava v
app.py - pouziva ji i admin_profily blok (jina skupina). Tenhle modul
si obe funkce jen importuje.
"""
from flask import request, jsonify

from app import (
    app,
    get_conn,
    admin_required,
    require_permission,
    scrape_logiman_product_price,
    refresh_price_for_product,
)


@app.post("/api/admin/logiman-price-check")
@admin_required
def logiman_price_check():
    # Cte-only "kolik to stoji na logiman.cz PRAVE TED" pro dany produkt -
    # NA ROZDIL od /api/shop/products/<id>/refresh-price (ktery cenu rovnou
    # ULOZI do price_czk_placeholder), tenhle endpoint nic v DB nemeni.
    # Robert potrebuje videt OBE cisla vedle sebe (nase aktualni x
    # logiman), aby si "dopočítal koeficienty rozdílem" - kdyby refresh-
    # price rovnou prepsal nasi cenu, rozdil by uz nesel videt.
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    if not product_id:
        return jsonify({"error": "Chybí product_id."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sku, price_source_url FROM shop_products WHERE id=%s", (product_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Produkt neexistuje."}), 404
    if not row["price_source_url"]:
        return jsonify({"error": "Tenhle produkt nemá nastavenou zdrojovou URL na logiman.cz."}), 400
    try:
        price = scrape_logiman_product_price(row["price_source_url"], row["sku"])
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    if price is None:
        return jsonify({"error": "Na stránce se nepodařilo najít cenu podle kódu produktu."}), 502
    return jsonify({"logiman_price_czk": price})


@app.post("/api/shop/products/<int:product_id>/refresh-price")
@require_permission("sklad_karty", "upravit")
def shop_products_refresh_price(product_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sku, price_source_url FROM shop_products WHERE id=%s", (product_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Produkt neexistuje."}), 404
            if not row["price_source_url"]:
                return jsonify({"error": "Tenhle produkt nemá nastavenou zdrojovou URL na logiman.cz."}), 400
            result = refresh_price_for_product(cur, product_id, row["sku"], row["price_source_url"])
        conn.commit()
    finally:
        conn.close()
    if result["status"] == "error":
        return jsonify(result), 502
    return jsonify(result)
