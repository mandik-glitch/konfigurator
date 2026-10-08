"""
hover_sweep_settings.py - nastavitelnost DVOU hover efektu na kartach
produktu/podkategorie v category.html:
  "sweep"  diagonalni jezdici pruh (`.cp-media::after`/`.cs-media::after`,
           `cpCardSweep` keyframe)
  "scan"   svisly sken shora dolu (`.cp-media::before`/`.cs-media::before`,
           `cpScan` keyframe)

Robert primo, 2026-09-15 (pres bot3), stejny vzor jako uz existujici
self-service pruhlednost .pd-desc-card (viz pd_desc_opacity.py). Puvodne
jen "sweep" (dotazano AskUserQuestion - jeden spolecny ovladac pro
produkty i podkategorie, ne dva zvlast). Pak Robert: "totez aplikujme i
na ten shora dolu" (scan) - dotazano znovu, tentokrat chce PRO SCAN
SAMOSTATNOU sadu 4 posuvniku (ne sdilenou se sweep). Pak: "chci aby se
ty efekty stridali" (mezi hovery, ne soucasne behem jednoho) a "menit
smer uhel" - dotazano, chce DALSI admin posuvnik (rozsah uhlu),
sdileny mezi obema efekty (1 spolecna hodnota tilt_deg).

1 nastaveni v app_settings, klic "hover_sweep_config" (JSON):
  sweep: {color, opacity_pct, width_pct, speed_s}   - jako drive
  scan:  {color, opacity_pct, thickness_px, speed_s} - "sila" = tloustka
         skenovaci cary v px (misto sirky pruhu v %, jina geometrie)
  tilt_deg: -60..60, sdileny naklon smeru OBOU efektu (0 = puvodni
            vychozi smer - sweep 100deg diagonala, scan presne svisle)
"""
from flask import jsonify, request

from app import app, get_conn, admin_required, current_user, log_audit, get_setting
import json

SETTING_KEY = "hover_sweep_config"
DEFAULTS = {
    "sweep": {"color": "#ffffff", "opacity_pct": 55, "width_pct": 10, "speed_s": 0.7},
    "scan": {"color": "#9fd0ff", "opacity_pct": 55, "thickness_px": 20, "speed_s": 1.1},
    "tilt_deg": 0,
}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _sanitize_color(raw, fallback):
    if isinstance(raw, str) and len(raw) in (4, 7) and raw.startswith("#"):
        return raw
    return fallback


def _sanitize_effect(raw, defaults, strength_key, strength_lo, strength_hi):
    cfg = dict(defaults)
    if not isinstance(raw, dict):
        return cfg
    cfg["color"] = _sanitize_color(raw.get("color"), defaults["color"])
    try:
        if "opacity_pct" in raw:
            cfg["opacity_pct"] = _clamp(int(raw["opacity_pct"]), 0, 100)
        if strength_key in raw:
            cfg[strength_key] = _clamp(int(raw[strength_key]), strength_lo, strength_hi)
        if "speed_s" in raw:
            cfg["speed_s"] = _clamp(round(float(raw["speed_s"]), 2), 0.1, 3.0)
    except (TypeError, ValueError):
        pass
    return cfg


def _sanitize(raw):
    if not isinstance(raw, dict):
        raw = {}
    cfg = {
        "sweep": _sanitize_effect(raw.get("sweep"), DEFAULTS["sweep"], "width_pct", 1, 30),
        "scan": _sanitize_effect(raw.get("scan"), DEFAULTS["scan"], "thickness_px", 2, 60),
        "tilt_deg": DEFAULTS["tilt_deg"],
    }
    try:
        if "tilt_deg" in raw:
            cfg["tilt_deg"] = _clamp(int(raw["tilt_deg"]), -60, 60)
    except (TypeError, ValueError):
        pass
    return cfg


@app.get("/api/public/hover-sweep-settings")
def public_hover_sweep_settings():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            raw = get_setting(cur, SETTING_KEY)
    finally:
        conn.close()
    try:
        parsed = json.loads(raw) if raw else None
    except (TypeError, ValueError):
        parsed = None
    return jsonify(_sanitize(parsed))


@app.put("/api/admin/hover-sweep-settings")
@admin_required
def admin_set_hover_sweep_settings():
    body = request.get_json(silent=True) or {}
    cfg = _sanitize(body)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            val = json.dumps(cfg, ensure_ascii=False)
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (SETTING_KEY, val, val),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "hover_sweep_settings", None, json.dumps(cfg, ensure_ascii=False))
    return jsonify({"status": "ok", **cfg})
