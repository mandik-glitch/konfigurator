"""Admin CRUD pro centralni panel popisu kategorii - obor (content_obor)
-> typologie (content_typologie). Robert pres bot3, 2026-09-27: "Postav
nekde v adminu panel jako centralni popis nasich webovych kategorii,
rozdeleno podle oboru a typologie."

Pracovni postup (Robertova vlastni slova): bot7 navrhne text (ze zaloh,
drivejsiho zkoumani logiman.cz a konkurence), admin (Robert) ho projde,
opravi a schvali - pak uz na nej bot7 nesmi sahnout. `schvaleno` +
`schvaleno_at` na obou urovnich (obor i typologie) nesou tenhle stav.
Databaze/API tenhle zamek NEVYNUCUJE technicky (Robert sam smi cokoli
upravit dal pres tenhle admin panel) - je to bota7 vlastni disciplina
(nikdy nezavolat update/*.py skript na uz schvaleny radek), viz memory
feedback_approved_central_text_hands_off.md.

Az bude obsah schvaleny, bot7 z nej dela VYTAZKY (cele odstavce/vety, ne
prepisovani) do jednotlivych kategorii e-shopu - `kategorie_ids` na
typologii uz ted nese navrzene mapovani na zivy strom (`content_categories.id`,
comma-separated), aby se pri tom kroku nemuselo hledat znovu.
"""
from flask import request, jsonify

from app import app, get_conn, require_permission, current_user, log_audit


def _obor_public(o, with_typologie=None):
    data = {
        "id": o["id"], "kod": o["kod"], "nazev": o["nazev"],
        "sort_order": o["sort_order"], "aktivni": bool(o["aktivni"]),
        "schvaleno": bool(o["schvaleno"]),
        "schvaleno_at": o["schvaleno_at"].isoformat() if o.get("schvaleno_at") else None,
    }
    if with_typologie is not None:
        data["typologie"] = with_typologie
    return data


def _typologie_public(t, with_popis=False):
    data = {
        "id": t["id"], "obor_id": t["obor_id"], "klic": t["klic"], "nazev": t["nazev"],
        "kategorie_ids": t.get("kategorie_ids"),
        "sort_order": t["sort_order"], "aktivni": bool(t["aktivni"]),
        "schvaleno": bool(t["schvaleno"]),
        "schvaleno_at": t["schvaleno_at"].isoformat() if t.get("schvaleno_at") else None,
    }
    if with_popis:
        data["popis_html"] = t.get("popis_html")
    return data


# ------------------------- OBOR -------------------------

@app.get("/api/admin/content-obor")
@require_permission("centralni_texty", "zobrazit")
def admin_content_obor_list():
    # Seznamovy pohled - i s typologiemi (bez jejich popis_html, muze byt
    # velky, netreba ho tahat pro vypis) - admin panel je jednostrankovy
    # strom obor->typologie, ne dve samostatne obrazovky.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM content_obor ORDER BY sort_order ASC, id ASC")
            obory = cur.fetchall()
            cur.execute("SELECT id, obor_id, klic, nazev, kategorie_ids, sort_order, aktivni, schvaleno, schvaleno_at FROM content_typologie ORDER BY sort_order ASC, id ASC")
            typologie_all = cur.fetchall()
    finally:
        conn.close()
    by_obor = {}
    for t in typologie_all:
        by_obor.setdefault(t["obor_id"], []).append(_typologie_public(t))
    return jsonify({"obory": [_obor_public(o, by_obor.get(o["id"], [])) for o in obory]})


@app.get("/api/admin/content-obor/<int:obor_id>")
@require_permission("centralni_texty", "zobrazit")
def admin_content_obor_detail(obor_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM content_obor WHERE id=%s", (obor_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Obor nenalezen."}), 404
    data = _obor_public(row)
    data["popis_html"] = row.get("popis_html")
    return jsonify(data)


@app.post("/api/admin/content-obor")
@require_permission("centralni_texty", "vytvorit")
def admin_content_obor_create():
    body = request.get_json(silent=True) or {}
    kod = (body.get("kod") or "").strip()
    nazev = (body.get("nazev") or "").strip()
    if not kod or not nazev:
        return jsonify({"error": "Chybí kód nebo název."}), 400
    popis_html = body.get("popis_html") or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM content_obor WHERE kod=%s", (kod,))
            if cur.fetchone():
                return jsonify({"error": "Tenhle kód oboru už existuje."}), 400
            cur.execute(
                "INSERT INTO content_obor (kod, nazev, popis_html, sort_order) "
                "SELECT %s, %s, %s, COALESCE(MAX(sort_order),0)+10 FROM content_obor",
                (kod, nazev, popis_html),
            )
            obor_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "content_obor", obor_id, nazev)
    return jsonify({"status": "ok", "id": obor_id})


@app.put("/api/admin/content-obor/<int:obor_id>")
@require_permission("centralni_texty", "upravit")
def admin_content_obor_update(obor_id):
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM content_obor WHERE id=%s", (obor_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Obor nenalezen."}), 404

            fields, params = [], []
            if "nazev" in body:
                nazev = (body.get("nazev") or "").strip()
                if not nazev:
                    return jsonify({"error": "Název nesmí být prázdný."}), 400
                fields.append("nazev=%s"); params.append(nazev)
            if "popis_html" in body:
                fields.append("popis_html=%s"); params.append(body.get("popis_html") or None)
            if "aktivni" in body:
                fields.append("aktivni=%s"); params.append(1 if body.get("aktivni") else 0)
            if "sort_order" in body:
                try:
                    fields.append("sort_order=%s"); params.append(int(body.get("sort_order")))
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné pořadí."}), 400
            if "schvaleno" in body:
                if body.get("schvaleno"):
                    fields.append("schvaleno=1"); fields.append("schvaleno_at=NOW()")
                else:
                    fields.append("schvaleno=0"); fields.append("schvaleno_at=NULL")

            if fields:
                params.append(obor_id)
                cur.execute(f"UPDATE content_obor SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "content_obor", obor_id, ", ".join(body.keys()))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/content-obor/<int:obor_id>")
@require_permission("centralni_texty", "smazat")
def admin_content_obor_delete(obor_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM content_obor WHERE id=%s", (obor_id,))
            if not cur.fetchone():
                return jsonify({"error": "Obor nenalezen."}), 404
            cur.execute("DELETE FROM content_obor WHERE id=%s", (obor_id,))  # CASCADE smaze i typologie
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "content_obor", obor_id, "")
    return jsonify({"status": "ok"})


# ------------------------- TYPOLOGIE -------------------------

@app.get("/api/admin/content-typologie/<int:typologie_id>")
@require_permission("centralni_texty", "zobrazit")
def admin_content_typologie_detail(typologie_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM content_typologie WHERE id=%s", (typologie_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Typologie nenalezena."}), 404
    return jsonify(_typologie_public(row, with_popis=True))


@app.post("/api/admin/content-obor/<int:obor_id>/typologie")
@require_permission("centralni_texty", "vytvorit")
def admin_content_typologie_create(obor_id):
    body = request.get_json(silent=True) or {}
    klic = (body.get("klic") or "").strip()
    nazev = (body.get("nazev") or "").strip()
    if not klic or not nazev:
        return jsonify({"error": "Chybí klíč nebo název."}), 400
    popis_html = body.get("popis_html") or None
    kategorie_ids = (body.get("kategorie_ids") or "").strip() or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM content_obor WHERE id=%s", (obor_id,))
            if not cur.fetchone():
                return jsonify({"error": "Obor nenalezen."}), 404
            cur.execute("SELECT id FROM content_typologie WHERE obor_id=%s AND klic=%s", (obor_id, klic))
            if cur.fetchone():
                return jsonify({"error": "Tenhle klíč typologie v oboru už existuje."}), 400
            cur.execute(
                "INSERT INTO content_typologie (obor_id, klic, nazev, popis_html, kategorie_ids, sort_order) "
                "SELECT %s, %s, %s, %s, %s, COALESCE(MAX(sort_order),0)+10 FROM content_typologie WHERE obor_id=%s",
                (obor_id, klic, nazev, popis_html, kategorie_ids, obor_id),
            )
            typologie_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "content_typologie", typologie_id, nazev)
    return jsonify({"status": "ok", "id": typologie_id})


@app.put("/api/admin/content-typologie/<int:typologie_id>")
@require_permission("centralni_texty", "upravit")
def admin_content_typologie_update(typologie_id):
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM content_typologie WHERE id=%s", (typologie_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Typologie nenalezena."}), 404

            fields, params = [], []
            if "nazev" in body:
                nazev = (body.get("nazev") or "").strip()
                if not nazev:
                    return jsonify({"error": "Název nesmí být prázdný."}), 400
                fields.append("nazev=%s"); params.append(nazev)
            if "popis_html" in body:
                fields.append("popis_html=%s"); params.append(body.get("popis_html") or None)
            if "kategorie_ids" in body:
                fields.append("kategorie_ids=%s"); params.append((body.get("kategorie_ids") or "").strip() or None)
            if "aktivni" in body:
                fields.append("aktivni=%s"); params.append(1 if body.get("aktivni") else 0)
            if "sort_order" in body:
                try:
                    fields.append("sort_order=%s"); params.append(int(body.get("sort_order")))
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné pořadí."}), 400
            if "schvaleno" in body:
                schvaleno = 1 if body.get("schvaleno") else 0
                if schvaleno:
                    fields.append("schvaleno=1"); fields.append("schvaleno_at=NOW()")
                else:
                    fields.append("schvaleno=0"); fields.append("schvaleno_at=NULL")

            if fields:
                params.append(typologie_id)
                cur.execute(f"UPDATE content_typologie SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "content_typologie", typologie_id, ", ".join(body.keys()))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/content-typologie/<int:typologie_id>")
@require_permission("centralni_texty", "smazat")
def admin_content_typologie_delete(typologie_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM content_typologie WHERE id=%s", (typologie_id,))
            if not cur.fetchone():
                return jsonify({"error": "Typologie nenalezena."}), 404
            cur.execute("DELETE FROM content_typologie WHERE id=%s", (typologie_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "content_typologie", typologie_id, "")
    return jsonify({"status": "ok"})
