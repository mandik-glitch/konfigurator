"""
base_dark_color.py - "zakladni cerna barva" pouzita napevno na spoustě
nezavislych mist napric webem (dlazdice na homepage, nazvove listy
nahledu kategorii, znackove dlazdice) - self-service pro admina.

Robert primo, 2026-09-17 (u screenshotu homepage s dlazdicemi
"Realizace vestaveb...", "Alu profily...", ...): "chci regulovat i tu
zakladní černou barvu na vsech mistech, pod menu, na dlazdicich, na
nahledech kategorií".

DULEZITE: tohle NENI totez jako --panel-bg-alt (ta uz existuje, je
THEME-REAKTIVNI - jina hodnota ve svetlem/tmavem rezimu, pouziva se
napr. pro .sidebar/cat-tree-bg-outer). Hodnota reseni tady
(--base-dark, vychozi #1a1d23) je puvodne ZAMERNE fixni/theme-
NEZAVISLA (Robert 2026-08-09: "chtel jsem i na svetlem motivu cernou
barvu ve spodni casti okna" - viz komentare u .cs-name/.hp-block-card
v kazde webapp/*.html) - "titulkovy pruh" pod fotkou dlazdice zustava
tmavy v obou motivech schvalne. Tenhle posuvnik meni tu FIXNI hodnotu,
ne theme-tokeny.

1 nastaveni v app_settings ("base_dark_hex"), hex retezec #rrggbb NEBO
prazdne/chybejici = vychozi #1a1d23. Stejny minimalisticky vzor jako
pd_desc_opacity.py/site_font.py.
"""
from flask import jsonify, request

from app import app, get_conn, admin_required, current_user, log_audit, get_setting, _HEX_COLOR_RE

SETTING_KEY = "base_dark_hex"
DEFAULT_HEX = "#1a1d23"


@app.get("/api/public/base-dark-color")
def public_base_dark_color():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            val = get_setting(cur, SETTING_KEY)
    finally:
        conn.close()
    hex_val = val if val and _HEX_COLOR_RE.match(val) else None
    return jsonify({"hex": hex_val, "default": DEFAULT_HEX})


@app.put("/api/admin/base-dark-color")
@admin_required
def admin_set_base_dark_color():
    body = request.get_json(silent=True) or {}
    val = body.get("hex")
    if val in (None, ""):
        val = ""
    elif not isinstance(val, str) or not _HEX_COLOR_RE.match(val):
        return jsonify({"error": f"Neplatná hex barva: {val}"}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (SETTING_KEY, val, val),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "base_dark_color", None, f"hex={val}")
    return jsonify({"status": "ok", "hex": val or None})


def base_dark_color_ssr_style(cur):
    # bot16, 2026-09-17 - volano z _render_og_page() (app.py) na KAZDE
    # strance, stejny vzor jako cat_tree_colors_ssr_style()/
    # site_font_ssr_head() - hodnota pritomna uz v prvni HTML odpovedi,
    # zadny problik. Prazdne (nic nenastaveno) = zadny <style> tag.
    val = get_setting(cur, SETTING_KEY)
    if not val or not _HEX_COLOR_RE.match(val):
        return ""
    return f'<style id="baseDarkColorSSR">:root{{--base-dark:{val}}}</style>'
