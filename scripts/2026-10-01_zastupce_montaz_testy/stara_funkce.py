"""Puvodni (chybna) verze product_assemblies._assembly_price_components - jen pro mutacni kontroly testu zastupce+montaz.
Zastupce (is_master) vracel montaz/boxy None, takze kosik/objednavka tise zahodily volby montaz / bez boxu."""
STARA_FUNKCE = '''
def _assembly_price_components(cur, assembly_id, product_id, master_price_placeholder):
    cur.execute(
        "SELECT id, data, is_master, kod_sestavy FROM product_assemblies "
        "WHERE id=%s AND shop_product_id=%s",
        (assembly_id, product_id),
    )
    r = cur.fetchone()
    if not r:
        return None
    if r["is_master"]:
        return {"base_czk": master_price_placeholder, "montaz_czk": None, "boxy_czk": None, "kod_sestavy": r["kod_sestavy"]}
    try:
        parsed = json.loads(r["data"]) if r["data"] else {}
    except (ValueError, TypeError):
        parsed = {}
    ps = parsed.get("price_summary") or {}
    total = ps.get("total_czk")
    montaz = ps.get("montaz_czk")
    return {
        "base_czk": round(total) if total is not None else None,
        "montaz_czk": round(montaz) if montaz is not None else None,
        "boxy_czk": _eurobox_soucet_czk(parsed.get("bom")),
        "kod_sestavy": r["kod_sestavy"],
    }
'''
