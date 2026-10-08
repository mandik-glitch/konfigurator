"""Pouziti: python3 patch_orders_origin.py <orders.py> - hook puvodu objednavky (order_host, order_lang) v orders_create a create_order_from_scene_offer + pole puvodu v _serialize_order (bot5, 2026-10-02)."""
import sys

p = sys.argv[1]
t = open(p, encoding="utf-8").read()


def zamen(a, b):
    global t
    assert t.count(a) == 1, (t.count(a), a[:90])
    t = t.replace(a, b)


# 1) zakaznicka objednavka: snimek puvodu hned za historii stavu, PRED atribuci dealera
zamen("""            # bot5, 2026-10-02 (dealersky program etapa 1): objednavka zakaznika, ktery prisel z odkazu dealera (cookie dlr, 30 dni od""", """            # bot5, 2026-10-02 (puvod objednavky, navrh A schvalil bot3): nemenny snimek hostu (order_host) a jazyka mini-shopu podle DOMENY (order_lang). NIKDY nevyhodi
            # vyjimku (record_order_origin chyby loguje, objednavka se nesmi rozbit).
            try:
                import car_storefronts
                car_storefronts.record_order_origin(cur, result["order_id"])
            except Exception:
                app.logger.exception("orders_create: zapis puvodu objednavky selhal (objednavka zalozena bez nej)")
            # bot5, 2026-10-02 (dealersky program etapa 1): objednavka zakaznika, ktery prisel z odkazu dealera (cookie dlr, 30 dni od""")

# 2) objednavka z prijate online nabidky (veřejná stranka): stejny snimek puvodu
zamen("""             line_total, length_mm, cut_kind, material_key),
        )
    return order_id, order_number
""", """             line_total, length_mm, cut_kind, material_key),
        )
    # bot5, 2026-10-02: snimek puvodu (host stranky nabidky, jazyk) - stejne jako u objednavky z e-shopu, nikdy nevyhodi vyjimku
    try:
        import car_storefronts
        car_storefronts.record_order_origin(cur, order_id)
    except Exception:
        app.logger.exception("create_order_from_scene_offer: zapis puvodu objednavky selhal")
    return order_id, order_number
""")

# 3) admin serializace: puvod a zdroj dealera
zamen("""        "dealer_external_ref": row.get("dealer_external_ref"),
""", """        "dealer_external_ref": row.get("dealer_external_ref"),
        # bot5, 2026-10-02 (puvod objednavky): mini-shop (storefront_id), nemenny snimek hostu a jazyka a jak se objednavka pripsala dealerovi (click/storefront/retro/api). Jen admin.
        "storefront_id": row.get("storefront_id"),
        "order_host": row.get("order_host"),
        "order_lang": row.get("order_lang"),
        "dealer_source": row.get("dealer_source"),
""")
open(p, "w", encoding="utf-8").write(t)
