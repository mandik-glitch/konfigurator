"""Vychozi UHEL POHLEDU 3D v generatorech stolu (bot10, 2026-10-08; Robert: "chci nastavit vychozi uhel pohledu 3D v generatorech").

JEDNO nastaveni pro VSECHNY generatory stolu (30 / 35 / 40 / 41 / 45 i karty vznikle z konfigurace): app_settings `configurator_view_default` = JSON {az, el} ve stupnich
(az = otoceni od cela modelu, el = naklon nad vodorovnou; viewer3d.js 1.17.0 `opts.isoAngles`). Cte ho verejne schema konfiguratoru (pole `view`, null = puvodnich 35 / 25; viz stul_shop.stul_shop_schema
-> js/product-configurator.js -> V3D.mount) - tedy stranka Generator stolu, stranka produktu, mini-shopy i vlozeny generator; meni ho jen admin (PUT / DELETE, pravo nastaveni / upravit jako prostredi a
vychozi konfigurace) z okna "Vychozi konfigurace" na strance generatoru (tlacitko "Uložit aktuální pohled jako výchozí"). Hodnoty se tady KONTROLUJI znovu (stejne meze jako V3D.normalizeIsoAngles v
prohlizeci), nic se neorezava potichu: mimo meze = chyba. Vzdalenost kamery se neuklada - viewer ji dopocte tak, aby byl videt cely stul (fitDistance).
"""
import json
import math
import time

from flask import request, jsonify

from app import app, get_conn, get_setting, require_permission, current_user

POHLED_KLIC = "configurator_view_default"
POHLED_EL_MIN, POHLED_EL_MAX = -15.0, 85.0
POHLED_TTL_S = 5.0
_CACHE = {"t": 0.0, "view": None}


def pohled_over(cfg):
    """Zkontroluje {az, el} (cisla ve stupnich) a vrati normalizovany dict (az zabalene do (-180, 180], zaokrouhleno na 0,1), nebo vyhodi ValueError."""
    if not isinstance(cfg, dict):
        raise ValueError("pohled musi byt objekt {az, el}")
    if set(cfg) != {"az", "el"}:
        raise ValueError("pohled musi mit prave klice az a el" + (" (navic: " + ", ".join(sorted(set(cfg) - {"az", "el"})) + ")" if set(cfg) - {"az", "el"} else ""))
    out = {}
    for k in ("az", "el"):
        v = cfg[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"{k} musi byt cislo (stupne)")
        out[k] = float(v)
    if not POHLED_EL_MIN <= out["el"] <= POHLED_EL_MAX:
        raise ValueError(f"el {out['el']:g} je mimo rozsah {POHLED_EL_MIN:g} az {POHLED_EL_MAX:g} stupnu")
    az = (out["az"] + 180.0) % 360.0 - 180.0
    if az == -180.0:
        az = 180.0
    return {"az": round(az, 1), "el": round(out["el"], 1)}


def nacti_pohled(force=False):
    """Ulozeny vychozi uhel pohledu (dict {az, el}) nebo None (= puvodni). Cache POHLED_TTL_S; chybna ulozena hodnota = None (nikdy neshodi schema)."""
    ted = time.time()
    if not force and _CACHE["t"] and ted - _CACHE["t"] < POHLED_TTL_S:
        return _CACHE["view"]
    cfg = None
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                raw = get_setting(cur, POHLED_KLIC)
        finally:
            conn.close()
        cfg = pohled_over(json.loads(raw)) if raw else None
    except Exception as e:                                           # noqa: BLE001
        app.logger.warning("stul: ulozeny vychozi pohled 3D se nepodarilo nacist: %s", e)
    _CACHE.update(t=ted, view=cfg)
    return cfg


def uloz_pohled(cfg, user_id=None):
    """Ulozi (cfg = dict po pohled_over) nebo SMAZE (cfg = None) vychozi pohled a zapise audit_log VE STEJNE TRANSAKCI (zmena a jeji stopa vzniknou spolu nebo vubec). Vraci ulozenou hodnotu / None;
    chyba DB vyhodi vyjimku."""
    cfg = pohled_over(cfg) if cfg is not None else None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if cfg is None:
                cur.execute("DELETE FROM app_settings WHERE setting_key=%s", (POHLED_KLIC,))
            else:
                val = json.dumps(cfg, sort_keys=True)
                cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=%s", (POHLED_KLIC, val, val))
            cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                        (user_id, "update" if cfg else "delete", "configurator_view", None, json.dumps({"view": cfg}, sort_keys=True)))
        conn.commit()
    finally:
        conn.close()
    _CACHE.update(t=time.time(), view=cfg)
    return cfg


@app.put("/api/shop/configurator/view")
@require_permission("nastaveni", "upravit")
def stul_pohled_put():
    """Admin-only: ulozi vychozi uhel pohledu 3D pro VSECHNY generatory stolu (telo {az, el} ve stupnich: az = otoceni od cela modelu, el = naklon -15 az 85); telo `null` ulozene smaze (puvodni 35 / 25)."""
    raw = request.get_data(as_text=True).strip()
    if raw == "null":
        cfg = None
    else:
        cfg = request.get_json(silent=True)
        if not isinstance(cfg, dict):
            return jsonify({"error": "telo musi byt JSON objekt {az, el} nebo null"}), 400
    u = current_user()                                                # PRED get_conn() (sdilene spojeni: close() = rollback)
    try:
        ulozeno = uloz_pohled(cfg, u["id"] if u else None)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"view": ulozeno})


@app.delete("/api/shop/configurator/view")
@require_permission("nastaveni", "upravit")
def stul_pohled_delete():
    """Admin-only: smaze ulozeny vychozi uhel pohledu (zpet na puvodnich 35 / 25). Odpoved {view: null}."""
    u = current_user()
    uloz_pohled(None, u["id"] if u else None)
    return jsonify({"view": None})
