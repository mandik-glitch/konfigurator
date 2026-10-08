"""Sprava osy "typ sestavy" (AUTO / STUL_SKLAD / dalsi) - Robert pres bot3,
2026-09-26 (PLAN_TVORBY_SESTAV.md, "Nová osa: typ sestavy"). Nahrazuje
dnesni ad-hoc rozlisovani pres nullable car_model_id + Vandr-specifickou
logiku centralne spravovanym typem s vlastnim vychozim textem a
volitelnymi sluzbami PER TYP - jedno misto v adminu ("Typy sestav", viz
webapp/admin.html + admin/js/typy-sestav.js), misto roztrousenych
nastaveni.

Konzultovano pred navrhem: bot8 (product_assemblies, vlastnik), bot5
(volitelne sluzby/pricing/sklad), bot10 (stolova linie). Schema+UI
schvalil bot3 bez podminek - viz sql/2026-09-26_sestava_typ_tabulka.sql.

Stejny vzor jako api/montaz_mista.py (kod/nazev jednoducha katalogova
tabulka, admin CRUD bez tvrdeho DELETE - jen deaktivace, aby se
neztratily historicke reference az se sestava_typ_id/sluzby zacnou
skutecne pouzivat). `kod`/`klic` jsou po zalozeni NEMENNE ze stejneho
duvodu jako `klic` u montaz_mista.

DULEZITE: tenhle modul zatim NIC nemeni na chovani webu ani na
existujicich ~530 product_assemblies radcich (sestava_typ_id je NULL
u vsech) - je to jen sprava ciselniku, migrace hodnot a presun
Vandr-specifickeho textu jsou SAMOSTATNE kroky s povinnym dry-run.
"""
import re as _re
import unicodedata

from flask import jsonify, request

from app import app, get_conn, admin_required, current_user, log_audit


def _serialize_typ(r):
    return {
        "id": r["id"], "kod": r["kod"], "nazev": r["nazev"],
        "popis_sablona": r["popis_sablona"], "aktivni": bool(r["aktivni"]),
        "sort_order": r["sort_order"],
    }


def _serialize_sluzba(r):
    return {
        "id": r["id"], "sestava_typ_id": r["sestava_typ_id"], "klic": r["klic"],
        "nazev": r["nazev"], "pricing_mode": r["pricing_mode"],
        "hodnota": float(r["hodnota"]) if r["hodnota"] is not None else None,
        "vyzaduje_dalsi_pole": bool(r["vyzaduje_dalsi_pole"]),
        "aktivni": bool(r["aktivni"]), "sort_order": r["sort_order"],
    }


def _slugify(nazev):
    basis = unicodedata.normalize("NFKD", nazev).encode("ascii", "ignore").decode("ascii")
    return _re.sub(r"[^a-z0-9]+", "_", basis.lower()).strip("_")


# ==================== sestava_typ ====================

@app.get("/api/admin/sestava-typ")
@admin_required
def admin_sestava_typ_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, kod, nazev, popis_sablona, aktivni, sort_order "
                "FROM sestava_typ ORDER BY sort_order, id"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"rows": [_serialize_typ(r) for r in rows]})


@app.post("/api/admin/sestava-typ")
@admin_required
def admin_sestava_typ_create():
    body = request.get_json(silent=True) or {}
    nazev = (body.get("nazev") or "").strip()
    if not nazev:
        return jsonify({"error": "Chybí název typu."}), 400
    kod = _slugify(nazev).upper()
    if not kod:
        return jsonify({"error": "Název musí obsahovat aspoň jedno písmeno/číslici."}), 400
    popis_sablona = (body.get("popis_sablona") or "").strip() or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM sestava_typ WHERE kod=%s", (kod,))
            if cur.fetchone():
                conn.rollback()
                return jsonify({"error": "Typ se stejným kódem už existuje."}), 400
            cur.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM sestava_typ")
            sort_order = cur.fetchone()["n"]
            cur.execute(
                "INSERT INTO sestava_typ (kod, nazev, popis_sablona, aktivni, sort_order) "
                "VALUES (%s,%s,%s,1,%s)",
                (kod, nazev, popis_sablona, sort_order),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "sestava_typ", new_id, kod)
    return jsonify({"status": "ok", "id": new_id, "kod": kod})


@app.put("/api/admin/sestava-typ/<int:typ_id>")
@admin_required
def admin_sestava_typ_update(typ_id):
    # POZOR: `kod` se NEDA menit po zalozeni - az se zacne pouzivat na
    # product_assemblies.sestava_typ_id/kod_sestavy, zmena by odtrhla
    # existujici prirazeni od popisku (stejny duvod jako klic u
    # montaz_mista).
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "nazev" in body:
        nazev = (body.get("nazev") or "").strip()
        if not nazev:
            return jsonify({"error": "Název nesmí být prázdný."}), 400
        fields.append("nazev=%s"); params.append(nazev)
    if "popis_sablona" in body:
        fields.append("popis_sablona=%s"); params.append((body.get("popis_sablona") or "").strip() or None)
    if "aktivni" in body:
        fields.append("aktivni=%s"); params.append(1 if body.get("aktivni") else 0)
    if "sort_order" in body:
        try:
            fields.append("sort_order=%s"); params.append(int(body.get("sort_order")))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné pořadí."}), 400
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(typ_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE sestava_typ SET {', '.join(fields)} WHERE id=%s", params)
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM sestava_typ WHERE id=%s", (typ_id,))
                if not cur.fetchone():
                    conn.rollback()
                    return jsonify({"error": "Typ neexistuje."}), 404
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "sestava_typ", typ_id, str(body))
    return jsonify({"status": "ok"})


# ==================== sestava_typ_sluzba ====================

_PRICING_MODES = ("informativni", "procento_z_ceny", "pevna_castka")


@app.get("/api/admin/sestava-typ-sluzby")
@admin_required
def admin_sestava_typ_sluzby_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sestava_typ_id, klic, nazev, pricing_mode, hodnota, "
                "vyzaduje_dalsi_pole, aktivni, sort_order FROM sestava_typ_sluzba "
                "ORDER BY sestava_typ_id IS NULL DESC, sestava_typ_id, sort_order, id"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"rows": [_serialize_sluzba(r) for r in rows]})


@app.post("/api/admin/sestava-typ-sluzby")
@admin_required
def admin_sestava_typ_sluzby_create():
    body = request.get_json(silent=True) or {}
    nazev = (body.get("nazev") or "").strip()
    if not nazev:
        return jsonify({"error": "Chybí název služby."}), 400
    klic = _slugify(nazev)
    if not klic:
        return jsonify({"error": "Název musí obsahovat aspoň jedno písmeno/číslici."}), 400
    pricing_mode = body.get("pricing_mode") or "informativni"
    if pricing_mode not in _PRICING_MODES:
        return jsonify({"error": f"Neplatný pricing_mode: {pricing_mode}"}), 400
    hodnota = body.get("hodnota")
    if pricing_mode != "informativni":
        try:
            hodnota = float(hodnota)
        except (TypeError, ValueError):
            return jsonify({"error": "Tento pricing_mode vyžaduje číselnou hodnotu."}), 400
    else:
        hodnota = None
    sestava_typ_id = body.get("sestava_typ_id")
    sestava_typ_id = int(sestava_typ_id) if sestava_typ_id not in (None, "") else None
    vyzaduje_dalsi_pole = 1 if body.get("vyzaduje_dalsi_pole") else 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if sestava_typ_id is not None:
                cur.execute("SELECT id FROM sestava_typ WHERE id=%s", (sestava_typ_id,))
                if not cur.fetchone():
                    conn.rollback()
                    return jsonify({"error": "Zadaný typ sestavy neexistuje."}), 400
            cur.execute(
                "SELECT id FROM sestava_typ_sluzba WHERE klic=%s AND "
                + ("sestava_typ_id IS NULL" if sestava_typ_id is None else "sestava_typ_id=%s"),
                (klic,) if sestava_typ_id is None else (klic, sestava_typ_id),
            )
            if cur.fetchone():
                conn.rollback()
                return jsonify({"error": "Služba se stejným názvem už u tohoto typu existuje."}), 400
            cur.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM sestava_typ_sluzba "
                + ("WHERE sestava_typ_id IS NULL" if sestava_typ_id is None else "WHERE sestava_typ_id=%s"),
                () if sestava_typ_id is None else (sestava_typ_id,),
            )
            sort_order = cur.fetchone()["n"]
            cur.execute(
                "INSERT INTO sestava_typ_sluzba "
                "(sestava_typ_id, klic, nazev, pricing_mode, hodnota, vyzaduje_dalsi_pole, aktivni, sort_order) "
                "VALUES (%s,%s,%s,%s,%s,%s,1,%s)",
                (sestava_typ_id, klic, nazev, pricing_mode, hodnota, vyzaduje_dalsi_pole, sort_order),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "sestava_typ_sluzba", new_id, klic)
    return jsonify({"status": "ok", "id": new_id, "klic": klic})


@app.put("/api/admin/sestava-typ-sluzby/<int:sluzba_id>")
@admin_required
def admin_sestava_typ_sluzby_update(sluzba_id):
    # `klic` a `sestava_typ_id` se NEDAJI menit po zalozeni - stejny
    # duvod jako `kod` u sestava_typ vyse (az se zacne pouzivat na
    # objednavkach, zmena by odtrhla historicke zaznamy od definice).
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "nazev" in body:
        nazev = (body.get("nazev") or "").strip()
        if not nazev:
            return jsonify({"error": "Název nesmí být prázdný."}), 400
        fields.append("nazev=%s"); params.append(nazev)
    if "pricing_mode" in body:
        pricing_mode = body.get("pricing_mode")
        if pricing_mode not in _PRICING_MODES:
            return jsonify({"error": f"Neplatný pricing_mode: {pricing_mode}"}), 400
        fields.append("pricing_mode=%s"); params.append(pricing_mode)
    if "hodnota" in body:
        hodnota = body.get("hodnota")
        if hodnota in (None, ""):
            fields.append("hodnota=%s"); params.append(None)
        else:
            try:
                fields.append("hodnota=%s"); params.append(float(hodnota))
            except (TypeError, ValueError):
                return jsonify({"error": "Neplatná hodnota."}), 400
    if "vyzaduje_dalsi_pole" in body:
        fields.append("vyzaduje_dalsi_pole=%s"); params.append(1 if body.get("vyzaduje_dalsi_pole") else 0)
    if "aktivni" in body:
        fields.append("aktivni=%s"); params.append(1 if body.get("aktivni") else 0)
    if "sort_order" in body:
        try:
            fields.append("sort_order=%s"); params.append(int(body.get("sort_order")))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné pořadí."}), 400
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(sluzba_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE sestava_typ_sluzba SET {', '.join(fields)} WHERE id=%s", params)
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM sestava_typ_sluzba WHERE id=%s", (sluzba_id,))
                if not cur.fetchone():
                    conn.rollback()
                    return jsonify({"error": "Služba neexistuje."}), 404
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "sestava_typ_sluzba", sluzba_id, str(body))
    return jsonify({"status": "ok"})
