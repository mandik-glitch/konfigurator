"""Sazba montaze konfigurovaneho stolu (bot5, 2026-10-04; Robert pres bot9: "cena montaze jako mnou nastavitelne % z celkove ceny stolu, vychozi 12 %", "to % volim primo v generatoru",
"montaz je vzdy volitelna", zakaznik % nevidi ani nemeni).

JEDINE rozhodnuti o sazbe: app_settings `stul_montaz_pct` (cislo 0-100, chybi = 12; 0 = montaz se nenabizi). Cte ho konfigurace_kosik.montaz_pct_pro_typ (kosik, objednavka, hostovska objednavka, kalkulace).
  GET /api/stul/montaz   {pct, default, available}         zamestnanec (jako GET /api/stul/pravidla)
  PUT /api/stul/montaz   {pct}                              RBAC nastaveni/upravit (jako PUT /api/stul/pravidla); 0 az 100, jinak 400; audit_log
Cena montaze = pct % z ceny konfigurace BEZ DPH (stejny zaklad jako cena ve generatoru), v objednavce samostatny radek 'Montaz', DPH 21 %.
"""
from decimal import Decimal, InvalidOperation

from flask import request, jsonify

from app import app, get_conn, staff_required, require_permission, get_setting, current_user, log_audit

KLIC = "stul_montaz_pct"
VYCHOZI = 12.0


def pct(cur):
    """Sazba montaze v % pro stul: nastavena hodnota, jinak 12; 0 nebo neplatna hodnota = None (montaz se nenabizi, fail closed). Cte jen pres kurzor."""
    raw = get_setting(cur, KLIC, None)
    if raw is None or str(raw).strip() == "":
        return VYCHOZI
    try:
        v = float(Decimal(str(raw).strip()))
    except (InvalidOperation, ValueError):
        return None
    return v if 0 < v <= 100 else None


def _odpoved(cur):
    p = pct(cur)
    raw = get_setting(cur, KLIC, None)
    return {"pct": p if p is not None else (0.0 if raw not in (None, "") else None), "default": VYCHOZI, "available": p is not None, "stored": raw not in (None, "")}


@app.get("/api/stul/montaz")
@staff_required
def stul_montaz_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            out = _odpoved(cur)
    finally:
        conn.close()
    r = jsonify(out)
    r.headers["Cache-Control"] = "no-store"
    return r


@app.put("/api/stul/montaz")
@require_permission("nastaveni", "upravit")
def stul_montaz_put():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "pct" not in body:
        return jsonify({"error": "pct_required"}), 400
    v = body["pct"]
    try:
        if isinstance(v, bool) or v is None or v == "":
            raise ValueError
        d = Decimal(str(v))
        if not d.is_finite() or d < 0 or d > 100:
            raise ValueError
    except (ValueError, InvalidOperation):
        return jsonify({"error": "pct_invalid", "message": "Sazba montáže musí být číslo 0 až 100 (0 = montáž se nenabízí)."}), 400
    d = d.quantize(Decimal("0.01"))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            stare = get_setting(cur, KLIC, None)
            cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=%s", (KLIC, str(d), str(d)))
            out = _odpoved(cur)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "app_setting", None, {"klic": KLIC, "z": stare, "na": str(d)})
    return jsonify(out)
