"""
pd_desc_opacity.py - pruhlednost podkladu pod textem popisu produktu
(.pd-desc-card v product.html), self-service pro admina.

Robert primo, 2026-09-15 (pres bot3), po ctvrtem hlaseni te same veci
("proc neni ten podklad pod textem prusvitny") a nasledne opravene na
plne pruhledny (background:transparent): "chci mít primo v detailu
produktu pri prihlaseni jako admin moznost menit pruhlednost podkladu
pod textem" - misto dalsich kol ladeni pres nas si to chce doladit sam.

1 nastaveni v app_settings, klic "pd_desc_card_opacity_pct" - cele
cislo 0-100 (%), kolik barvy var(--panel-bg-2) je v pozadi .pd-desc-card
namichane (viz color-mix() v product.html CSS). Vychozi (nastaveni
jeste v DB neexistuje) je 0 - presne posledni rucne zvoleny stav.
"""
from flask import jsonify, request

from app import app, get_conn, admin_required, current_user, log_audit, get_setting

SETTING_KEY = "pd_desc_card_opacity_pct"
DEFAULT_PCT = 0


def _clamp_pct(pct):
    return max(0, min(100, pct))


@app.get("/api/public/pd-desc-opacity")
def public_pd_desc_opacity():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            raw = get_setting(cur, SETTING_KEY)
    finally:
        conn.close()
    try:
        pct = _clamp_pct(int(raw)) if raw is not None else DEFAULT_PCT
    except (TypeError, ValueError):
        pct = DEFAULT_PCT
    return jsonify({"opacity_pct": pct})


@app.put("/api/admin/pd-desc-opacity")
@admin_required
def admin_set_pd_desc_opacity():
    body = request.get_json(silent=True) or {}
    try:
        pct = int(body.get("opacity_pct"))
    except (TypeError, ValueError):
        return jsonify({"error": "opacity_pct musí být celé číslo 0-100."}), 400
    if not (0 <= pct <= 100):
        return jsonify({"error": "opacity_pct musí být v rozsahu 0-100."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (SETTING_KEY, str(pct), str(pct)),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "pd_desc_opacity", None, f"opacity_pct={pct}")
    return jsonify({"status": "ok", "opacity_pct": pct})
