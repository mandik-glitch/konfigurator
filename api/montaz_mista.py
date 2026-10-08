"""Sprava mist montaze (Praha/Slavicin) - Robert, 2026-09-13, doslova:
"u montáže nevidim v adminu ty dve volby kde se muze montovat." Puvodni
reseni (bd432c44/757e2617) melo dve PEVNE hodnoty zapecene v Python
konstante - zadna viditelnost/editace v adminu. Na dotaz "jen zobrazit,
nebo editovat?" Robert zvolil PLNOU editaci.

Maly katalog (`montaz_mista`), stejny vzor jako api/accessories.py
(cfg_accessories) - admin CRUD (bez tvrdeho DELETE, jen deaktivace, aby
se neztratil popisek u uz existujicich objednavek se snapshotovanym
`klic`, viz shop_order_items.montaz_misto_snapshot) + jeden VEREJNY GET
pro frontend (product.html vykresluje volbu mista dynamicky, ne natvrdo).
"""
from flask import request, jsonify

from app import app, get_conn, require_permission


def _serialize_misto(r):
    return {
        "id": r["id"], "klic": r["klic"], "nazev": r["nazev"],
        "aktivni": bool(r["aktivni"]), "sort_order": r["sort_order"],
    }


@app.get("/api/montaz-mista")
def montaz_mista_public():
    """Verejne (bez auth) - jen AKTIVNI mista, pro select/pill na detailu
    produktu. Zadna cena/interni udaj, jen klic+nazev."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT klic, nazev FROM montaz_mista WHERE aktivni=1 ORDER BY sort_order, id"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"mista": [{"klic": r["klic"], "nazev": r["nazev"]} for r in rows]})


@app.get("/api/admin/montaz-mista")
@require_permission("nastaveni", "zobrazit")
def admin_montaz_mista_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, klic, nazev, aktivni, sort_order FROM montaz_mista ORDER BY sort_order, id")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"rows": [_serialize_misto(r) for r in rows]})


@app.post("/api/admin/montaz-mista")
@require_permission("nastaveni", "upravit")
def admin_montaz_mista_create():
    body = request.get_json(silent=True) or {}
    nazev = (body.get("nazev") or "").strip()
    if not nazev:
        return jsonify({"error": "Chybí název místa."}), 400
    # Klic (stabilni retezec ulozeny na kosiku/objednavce, viz
    # shop_cart_items.montaz_misto) - odvozeny z nazvu, ne zadany rucne
    # (at admin nemusi resit "praha" vs "Praha" vs "PRAHA"). Diakritika/
    # mezery pryc, jen a-z0-9_ - zadny jiny katalog v projektu (regal_
    # umisteni.klic) nema diakritiku, stejny vzor.
    import unicodedata
    import re as _re
    basis = unicodedata.normalize("NFKD", nazev).encode("ascii", "ignore").decode("ascii")
    klic = _re.sub(r"[^a-z0-9]+", "_", basis.lower()).strip("_")
    if not klic:
        return jsonify({"error": "Název musí obsahovat aspoň jedno písmeno/číslici."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM montaz_mista WHERE klic=%s", (klic,))
            if cur.fetchone():
                conn.rollback()
                return jsonify({"error": "Místo se stejným názvem už existuje."}), 400
            cur.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM montaz_mista")
            sort_order = cur.fetchone()["n"]
            cur.execute(
                "INSERT INTO montaz_mista (klic, nazev, aktivni, sort_order) VALUES (%s,%s,1,%s)",
                (klic, nazev, sort_order),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": new_id, "klic": klic})


@app.put("/api/admin/montaz-mista/<int:mid>")
@require_permission("nastaveni", "upravit")
def admin_montaz_mista_update(mid):
    # POZOR: `klic` se NEDA menit (na rozdil od nazvu) - je zapecen v
    # historickych objednavkach (shop_order_items.montaz_misto_snapshot)
    # a v kosicich (shop_cart_items.montaz_misto), zmena by je odtrhla
    # od popisku. Kdo chce jiny klic, at zalozi nove misto a stare
    # deaktivuje.
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "nazev" in body:
        nazev = (body.get("nazev") or "").strip()
        if not nazev:
            return jsonify({"error": "Název nesmí být prázdný."}), 400
        fields.append("nazev=%s"); params.append(nazev)
    if "aktivni" in body:
        fields.append("aktivni=%s"); params.append(1 if body.get("aktivni") else 0)
    if "sort_order" in body:
        try:
            fields.append("sort_order=%s"); params.append(int(body.get("sort_order")))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné pořadí."}), 400
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(mid)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE montaz_mista SET {', '.join(fields)} WHERE id=%s", params)
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM montaz_mista WHERE id=%s", (mid,))
                if not cur.fetchone():
                    conn.rollback()
                    return jsonify({"error": "Místo neexistuje."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})
