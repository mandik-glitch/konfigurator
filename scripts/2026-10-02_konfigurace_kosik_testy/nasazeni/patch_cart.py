#!/usr/bin/env python3
"""Patch api/cart.py: konfigurace sestavy v kosiku (bot5, 2026-10-02). Opakovatelne (znacka KONFIGURACE-KOSIK), kazda kotva musi byt v souboru PRAVE jednou. Pouziti: patch_cart.py <cesta k cart.py>"""
import sys

ZNACKA = "bot5, 2026-10-02: konfigurace sestavy"
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
if ZNACKA in t:
    print("cart.py: konfigurace uz je")
    sys.exit(0)

ZAMENY = [
    # 1) serializace radku kosiku: priznak zakazkove vyroby a blok configuration
    ('''            "bez_boxu": bool(r.get("bez_boxu")),
            "boxy_czk": _money(r.get("assembly_boxy_czk")) if r.get("assembly_boxy_czk") is not None else None,
        })''', '''            "bez_boxu": bool(r.get("bez_boxu")),
            "boxy_czk": _money(r.get("assembly_boxy_czk")) if r.get("assembly_boxy_czk") is not None else None,
            # %s - vyroba na zakazku: bez skladu, `configuration` = overeny vyber, kod, souhrn voleb a stav (valid, changed), viz api/konfigurace_kosik.py
            "made_to_order": bool(r.get("made_to_order")),
            "configuration": r.get("configuration"),
        })''' % ZNACKA),
    # 2) nacteni radku kosiku: sloupce konfigurace
    ('''            "       ci.assembly_id, ci.montaz_zvolena, ci.bez_boxu, ci.montaz_misto, "
            "       p.sku, p.name, p.price_czk_placeholder, p.cfg_dily_id, p.is_board_material, p.is_profile_material, "''',
     '''            "       ci.assembly_id, ci.montaz_zvolena, ci.bez_boxu, ci.montaz_misto, ci.configuration_json, ci.config_hash, "
            "       p.sku, p.name, p.price_czk_placeholder, p.cfg_dily_id, p.is_board_material, p.is_profile_material, "'''),
    # 3) zive pocitani radku s konfiguraci
    ('''        for r in rows:
            r["montaz_misto_label"] = misto_labels.get(r.get("montaz_misto"))''', '''        for r in rows:
            if r.get("config_hash"):
                # %s: vlastni ZIVE pocitani ceny a stavu, viz api/konfigurace_kosik.py (lazy import: poradi importu v app.py). Chyba nesmi rozbit cely kosik:
                # radek se pak ukaze jako neplatny (bez ceny) a objednavka ho odmitne.
                try:
                    import konfigurace_kosik
                    konfigurace_kosik.priprav_radek_kosiku(cur, r, user_id)
                except Exception:
                    getattr(app, "logger", None) and app.logger.exception("cart: radek s konfiguraci se nepodarilo spocitat")
                    r.update({"cut_service_unit_price_czk": None, "assembly_montaz_czk": None, "assembly_boxy_czk": None, "waste_breakdown": None, "montaz_misto_label": None,
                              "stock_qty": None, "unit_price_czk": None, "price_basis": None, "price_czk_placeholder": None, "made_to_order": True,
                              "configuration": {"valid": False, "error": "internal_error", "kod": None, "hash": r.get("config_hash"), "changed": False, "summary": [],
                                                "weight_kg": None, "montaz_pct": None, "errors": []}})
                continue
            r["montaz_misto_label"] = misto_labels.get(r.get("montaz_misto"))''' % ZNACKA),
    # 4) pridani do kosiku: konfigurace (a konfigurovatelny produkt BEZ konfigurace = chyba, ne tichy bezny radek)
    ('''    try:
        product_id = int(body.get("product_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné product_id."}), 400
''', '''    try:
        product_id = int(body.get("product_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné product_id."}), 400
    # %s: server vyber znovu overi a cenu spocita sam, viz api/konfigurace_kosik.py (lazy import: poradi importu v app.py; kdyz se modul nenacte,
    # bezne produkty funguji dal a konfigurovatelny produkt skonci jako "cena na dotaz")
    try:
        import konfigurace_kosik
    except Exception:
        konfigurace_kosik = None
        getattr(app, "logger", None) and app.logger.exception("cart: modul konfigurace se nenacetl")
    if konfigurace_kosik is not None and (body.get("configuration") is not None or konfigurace_kosik.je_konfigurovatelny(product_id)):
        chyba_cfg = konfigurace_kosik.pridat_do_kosiku(cart_owner_id, product_id, body)
        if chyba_cfg is not None:
            return jsonify(chyba_cfg[0]), chyba_cfg[1]
        conn_cfg = get_conn()
        try:
            rows_cfg = _fetch_cart_rows(conn_cfg, cart_owner_id)
        finally:
            conn_cfg.close()
        return jsonify(_serialize_cart(rows_cfg)), 201
''' % ZNACKA),
    # 5) uprava radku: sloupec konfigurace a vetev
    ('''                "SELECT ci.id, ci.cut_pieces_json, ci.montaz_zvolena, ci.montaz_misto, ci.assembly_id, "''',
     '''                "SELECT ci.id, ci.cut_pieces_json, ci.montaz_zvolena, ci.montaz_misto, ci.assembly_id, ci.config_hash, "'''),
    ('''            if not row:
                conn.rollback()
                return jsonify({"error": "Položka košíku neexistuje."}), 404
''', '''            if not row:
                conn.rollback()
                return jsonify({"error": "Položka košíku neexistuje."}), 404
            if row.get("config_hash"):
                # %s: mnozstvi a montaz, misto montaze se u konfigurace nevybira
                import konfigurace_kosik
                konfigurace_kosik.upravit_radek(cur, item_id, qty, body)
                conn.commit()
                rows = _fetch_cart_rows(conn, _cart_owner_id(user))
                return jsonify(_serialize_cart(rows))
''' % ZNACKA),
    # 6) admin prehled kosiku: priznak konfigurace (cena karty tu neni cena konfigurace)
    ('''                "SELECT ci.id, ci.user_id, ci.product_id, ci.qty, ci.added_at, ci.updated_at, "''',
     '''                "SELECT ci.id, ci.user_id, ci.product_id, ci.qty, ci.added_at, ci.updated_at, ci.config_hash, "'''),
    ('''            "is_archived": bool(r["is_archived"]),
        })
        entry["subtotal_czk"] = round(entry["subtotal_czk"] + line_total, 2)''', '''            "is_archived": bool(r["is_archived"]),
            "made_to_order": bool(r.get("config_hash")),
        })
        entry["subtotal_czk"] = round(entry["subtotal_czk"] + line_total, 2)'''),
]
for stare, nove in ZAMENY:
    assert t.count(stare) == 1, f"kotva nalezena {t.count(stare)}x: {stare[:70]!r}"
    t = t.replace(stare, nove)
open(p, "w", encoding="utf-8").write(t)
print(f"cart.py: patchovano ({len(ZAMENY)} zmen)")
