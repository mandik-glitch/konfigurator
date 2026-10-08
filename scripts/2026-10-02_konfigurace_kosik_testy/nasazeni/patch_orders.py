#!/usr/bin/env python3
"""Patch api/orders.py: radek objednavky s konfiguraci sestavy (bot5, 2026-10-02). Opakovatelne (znacka), kazda kotva PRAVE jednou. Pouziti: patch_orders.py <cesta k orders.py>"""
import sys

ZNACKA = "bot5, 2026-10-02: konfigurace sestavy"
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
if ZNACKA in t:
    print("orders.py: konfigurace uz je")
    sys.exit(0)

ZAMENY = [
    # 1) serializace radku objednavky: kod a snimek konfigurace (zakaznik bez kusovniku a nakladove struktury, zamestnanec plny snimek)
    ('''def _serialize_item(row, misto_labels=None):
    cut_pieces = None''', '''def _serialize_konfigurace(raw, plna):
    # %s: snimek konfigurace na radku objednavky. Zakaznik vidi jen kod a souhrn voleb, kusovnik a cenovy souhrn (nakladova struktura) jen zamestnanec.
    if not raw:
        return None
    import konfigurace_kosik
    return konfigurace_kosik.nacti_vyber_snimku(raw) if plna else konfigurace_kosik.zakaznicky_snimek(raw)


def _serialize_item(row, misto_labels=None, plna_konfigurace=False):
    cut_pieces = None''' % ZNACKA),
    ('''        "boxy_czk_snapshot": _money(row.get("boxy_czk_snapshot")) if row.get("boxy_czk_snapshot") is not None else None,
    }
''', '''        "boxy_czk_snapshot": _money(row.get("boxy_czk_snapshot")) if row.get("boxy_czk_snapshot") is not None else None,
        "configuration_code": row.get("configuration_code"),
        "configuration": _serialize_konfigurace(row.get("configuration_json"), plna_konfigurace),
    }
'''),
    ('''    result = _serialize_order(order) if user["role"] == "admin" else _serialize_order_for_customer(order)
    result["items"] = [_serialize_item(i, misto_labels) for i in items]''', '''    result = _serialize_order(order) if user["role"] == "admin" else _serialize_order_for_customer(order)
    result["items"] = [_serialize_item(i, misto_labels, user["role"] == "admin") for i in items]'''),
    ('''    result = _serialize_order(order)
    result["items"] = [_serialize_item(i, misto_labels) for i in items]
    result["history"] = [''', '''    result = _serialize_order(order)
    result["items"] = [_serialize_item(i, misto_labels, True) for i in items]
    result["history"] = ['''),
    # 2) potvrzovaci e-mail: radky s konfiguraci nejsou "neni skladem" (vyroba na zakazku, product_id NULL)
    ('''                "FROM shop_order_items oi LEFT JOIN shop_products p ON p.id = oi.product_id "
                "WHERE oi.order_id=%s",''', '''                "FROM shop_order_items oi LEFT JOIN shop_products p ON p.id = oi.product_id "
                "WHERE oi.order_id=%s AND oi.configuration_json IS NULL",'''),
    # 3) kosik -> objednavka: sloupce konfigurace
    ('''            "SELECT ci.product_id, ci.qty, ci.cut_pieces_json, ci.cut_service_qty, ci.coupon_code, "
            "       ci.assembly_id, ci.montaz_zvolena, ci.bez_boxu, ci.montaz_misto "''', '''            "SELECT ci.product_id, ci.qty, ci.cut_pieces_json, ci.cut_service_qty, ci.coupon_code, "
            "       ci.assembly_id, ci.montaz_zvolena, ci.bez_boxu, ci.montaz_misto, ci.configuration_json, ci.config_hash "'''),
    ('''             "bez_boxu": bool(r["bez_boxu"]), "montaz_misto": r["montaz_misto"]}
            for r in cart_rows''', '''             "bez_boxu": bool(r["bez_boxu"]), "montaz_misto": r["montaz_misto"],
             "configuration_json": r["configuration_json"], "config_hash": r["config_hash"]}
            for r in cart_rows'''),
    # 4) polozky z pozadavku: konfigurace
    ('''            clean_items.append({
                "product_id": product_id, "qty": qty, "assembly_id": assembly_id,
                "montaz_zvolena": bool(raw.get("montaz_zvolena")), "bez_boxu": bool(raw.get("bez_boxu")),
                "montaz_misto": montaz_misto_raw,
            })''', '''            clean_items.append({
                "product_id": product_id, "qty": qty, "assembly_id": assembly_id,
                "montaz_zvolena": bool(raw.get("montaz_zvolena")), "bez_boxu": bool(raw.get("bez_boxu")),
                "montaz_misto": montaz_misto_raw, "configuration": raw.get("configuration"),
            })'''),
    # 5) smycka polozek: konfigurace je vyroba na zakazku (radek product_id NULL, bez zamku produktu, bez skladu)
    ('''    for it in clean_items:
        cur.execute(
            "SELECT id, name, price_czk_placeholder, stock_qty, active, weight_g, cfg_dily_id, "''', '''    weight_incomplete_cfg = False                          # %s: hmotnost konfigurace z katalogu je neuplna -> Toptrans se pro ni nepocita
    for it in clean_items:
        # %s: konfigurace je vyroba na zakazku. Vyber se znovu overi a cena spocita na serveru (z kosiku ani z pozadavku se cena nebere), radek ma
        # product_id NULL (jako sluzba), takze se na nej nevztahuje zadna logika skladu; odkaz na kartu a hash jsou ve snimku. Viz api/konfigurace_kosik.py.
        try:
            import konfigurace_kosik
        except Exception:                                      # modul se nenacetl: bezne radky dal funguji, konfigurovatelny produkt skonci jako "cena na dotaz"
            konfigurace_kosik = None
            getattr(app, "logger", None) and app.logger.exception("orders: modul konfigurace se nenacetl")
        if konfigurace_kosik is not None and (it.get("config_hash") or it.get("configuration") is not None or konfigurace_kosik.je_konfigurovatelny(it["product_id"])):
            if dealer is not None:
                raise _OrderCreateError("Konfigurovatelný produkt nelze objednat dealerskou cestou.", status_code=422)
            cur.execute("SELECT id, name, active FROM shop_products WHERE id=%%s", (it["product_id"],))
            product_cfg = cur.fetchone()
            if not product_cfg or (require_active and not product_cfg["active"]):
                raise _OrderCreateError(f"Produkt {it['product_id']} neexistuje nebo není dostupný.")
            order_item_cfg, kg_cfg, kg_cfg_ok = konfigurace_kosik.radek_objednavky(
                cur, product_cfg, it, attribute_user_id, lambda zprava, stav=400: _OrderCreateError(zprava, status_code=stav))
            total += order_item_cfg["line_total_czk"]
            total_weight_kg += kg_cfg
            weight_incomplete_cfg = weight_incomplete_cfg or not kg_cfg_ok
            order_items.append(order_item_cfg)
            continue
        cur.execute(
            "SELECT id, name, price_czk_placeholder, stock_qty, active, weight_g, cfg_dily_id, "''' % (ZNACKA, ZNACKA)),
    # 5b) doprava podle hmotnosti (Toptrans): hmotnost konfigurace z katalogu je neuplna (chybi laminodeska, suplíky...), poddimenzovala by dopravu -> automaticky se nepocita
    ('''        if sm["pricing_mode"] == "zip_weight":
            shipping_price, _km_band, _basis = _resolve_toptrans_price(''', '''        if sm["pricing_mode"] == "zip_weight":
            if weight_incomplete_cfg:                          # %s
                import konfigurace_kosik
                raise _OrderCreateError(konfigurace_kosik.ZPRAVA_HMOTNOST, status_code=409)
            shipping_price, _km_band, _basis = _resolve_toptrans_price(''' % ZNACKA),
    # 5c) nahled ceny dopravy (POST /api/shipping-price-preview): radek s konfiguraci ma hmotnost z konfigurace (karta ma hmotnost 0), pri neuplne hmotnosti se cena nepocita
    ('''                    "SELECT ci.product_id, ci.qty FROM shop_cart_items ci WHERE ci.user_id=%s",''',
     '''                    "SELECT ci.product_id, ci.qty, ci.configuration_json, ci.config_hash FROM shop_cart_items ci WHERE ci.user_id=%s",'''),
    ('''                        items.append({"product_id": int(raw.get("product_id")), "qty": int(raw.get("qty"))})''',
     '''                        items.append({"product_id": int(raw.get("product_id")), "qty": int(raw.get("qty")), "configuration": raw.get("configuration")})'''),
    ('''            for it in items:
                cur.execute(
                    "SELECT weight_g, cfg_dily_id, length_mm, width_mm, height_mm "''', '''            for it in items:
                # %s: konfigurace ma hmotnost z konfiguratoru; neuplna hmotnost (chybi hmotnosti dilu v katalogu) = cena dopravy se nepocita
                try:
                    import konfigurace_kosik
                except Exception:
                    konfigurace_kosik = None
                if konfigurace_kosik is not None and (it.get("config_hash") or it.get("configuration") is not None or konfigurace_kosik.je_konfigurovatelny(it["product_id"])):
                    try:
                        kg_cfg, kg_cfg_ok = konfigurace_kosik.hmotnost_pro_nahled(cur, it)
                    except konfigurace_kosik.KonfiguraceChyba as e:
                        return jsonify({"error": e.message, "code": e.code}), e.status
                    if not kg_cfg_ok:
                        return jsonify({"error": konfigurace_kosik.ZPRAVA_HMOTNOST, "code": "weight_incomplete"}), 409
                    total_weight_kg += kg_cfg
                    continue
                cur.execute(
                    "SELECT weight_g, cfg_dily_id, length_mm, width_mm, height_mm "''' % ZNACKA),
    # 6) zapis radku objednavky: snimek a kod konfigurace
    ('''            " assembly_id, assembly_kod_snapshot, montaz_zvolena, montaz_czk_snapshot, montaz_misto_snapshot, "
            " bez_boxu, boxy_czk_snapshot) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",''', '''            " assembly_id, assembly_kod_snapshot, montaz_zvolena, montaz_czk_snapshot, montaz_misto_snapshot, "
            " bez_boxu, boxy_czk_snapshot, configuration_json, configuration_code) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",'''),
    ('''             oi.get("bez_boxu", False), oi.get("boxy_czk_snapshot")),
        )''', '''             oi.get("bez_boxu", False), oi.get("boxy_czk_snapshot"),
             oi.get("configuration_json"), oi.get("configuration_code")),
        )'''),
]
for stare, nove in ZAMENY:
    assert t.count(stare) == 1, f"kotva nalezena {t.count(stare)}x: {stare[:70]!r}"
    t = t.replace(stare, nove)
open(p, "w", encoding="utf-8").write(t)
print(f"orders.py: patchovano ({len(ZAMENY)} zmen)")
