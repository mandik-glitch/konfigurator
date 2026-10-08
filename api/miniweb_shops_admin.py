"""Mini-shopy v administraci (bot5, 2026-10-03; zadani bot16 pro zalozku "Mini-shopy" s RBAC, Robert pres bot3: stejne ucty a prava jako zbytek administrace).

  GET /api/admin/miniweb/shops                    prehled shopu (domena, jazyk, stav, cena/mena/marze/kurz, zeme, poptavky/objednavky zapnute, pocty)         RBAC miniweb/zobrazit
  PUT /api/admin/miniweb/shops/<storefront_id>    uprava nastaveni (price_mode, margin_pct, eur_rate, countries, inquiry_enabled, orders_enabled, contact, accent)  RBAC miniweb/upravit
  GET /api/admin/miniweb/inquiries?shop=<id>      poptavky shopu (z CRM, bez textu zpravy)                                                                    RBAC miniweb/zobrazit
  GET /api/admin/miniweb/orders?shop=<id>         objednavky shopu (kompaktne; plny detail je v Objednavkach)                                                 RBAC miniweb/zobrazit
Schvalovani textu (overview, approve, unapprove v miniweb_admin.py) ma vlastni sekci RBAC `miniweb_schvalovani`. Stav shopu (draft/live) se TADY nemeni: spusteni jen skriptem
`scripts/miniweb_shop.py --go-live` s kontrolou podminek (schvalene texty, prodejce, domena); zapnuti objednavek vyzaduje nastavenou cenu (shown, EUR, marze), jinak 422.
"""
import json
import re
from decimal import Decimal

from flask import request, jsonify

from app import app, get_conn, require_permission, current_user, log_audit
import miniweb
import miniweb_cena
import orders as orders_mod

PRICE_MODES = ("hidden", "indicative", "shown")
MAX_LIMIT = 200
_BAD_TEXT = re.compile(r"[<>@\x00-\x1f]")
_SHOP_KEYS = {"price_mode", "margin_pct", "eur_rate", "countries", "inquiry_enabled", "orders_enabled", "contact", "accent", "currency"}


def _resp(payload, status=200):
    r = jsonify(payload)
    r.status_code = status
    r.headers["Cache-Control"] = "no-store"
    return r


def _err(status, code, field=None):
    return _resp({"error": code, **({"field": field} if field else {})}, status)


def _num(v):
    return float(v) if v is not None else None


def _contact(raw):
    try:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else (raw or {})
    except ValueError:
        d = {}
    d = d if isinstance(d, dict) else {}
    return {"phone": d.get("phone") or "", "hours": d.get("hours") or "", "use_company": d.get("use_company") is True}


def _shop_json(r, counts):
    manual = _num(r["eur_rate"])
    hit = miniweb_cena._cache.get("EUR")                          # jen z cache, seznam nikdy nevola Fio
    live = hit[1] if hit and hit[0] > __import__("time").time() else None
    c = counts.get(r["storefront_id"], {})
    return {"storefront_id": r["storefront_id"], "slug": r["slug"], "name": r["name"], "domain": r["primary_domain"], "lang": r["lang"], "status": r["status"], "family": r["family"],
            "price_mode": r["price_mode"], "currency": r["currency"], "locale": r["locale"], "accent": r["accent"], "countries": [x for x in (r["countries"] or "").split(",") if x],
            "margin_pct": _num(r["margin_pct"]), "eur_rate": manual, "rate_source": "manual" if manual else "fio", "live_rate": live,
            "inquiry_enabled": bool(r["inquiry_enabled"]), "orders_enabled": bool(r.get("orders_enabled")), "contact": _contact(r["contact_json"]),
            "inquiries": c.get("inq", 0), "orders": c.get("ord", 0), "orders_to_review": c.get("rev", 0)}


@app.get("/api/admin/miniweb/shops")
@require_permission("miniweb", "zobrazit")
def admin_miniweb_shops():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT m.*, s.name, s.slug, s.primary_domain, s.status, s.lang FROM miniweb_shops m JOIN car_storefronts s ON s.id = m.storefront_id ORDER BY s.lang, s.id")
            rows = cur.fetchall()
            counts = {}
            cur.execute("SELECT storefront_id, COUNT(*) AS n FROM miniweb_inquiries GROUP BY storefront_id")
            for r in cur.fetchall():
                counts.setdefault(r["storefront_id"], {})["inq"] = r["n"]
            cur.execute("SELECT storefront_id, COUNT(*) AS n, SUM(shipping_review=1) AS rev FROM shop_orders WHERE is_test=0 AND order_host IS NOT NULL AND storefront_id IS NOT NULL GROUP BY storefront_id")
            for r in cur.fetchall():
                counts.setdefault(r["storefront_id"], {}).update(ord=r["n"], rev=int(r["rev"] or 0))
    finally:
        conn.close()
    return _resp({"shops": [_shop_json(r, counts) for r in rows]})


def _clean(body, row):
    """Overene zmeny {sloupec: hodnota} (jen zadane klice) nebo (None, chyba, pole)."""
    out = {}
    unknown = set(body) - _SHOP_KEYS
    if unknown:
        return None, "unknown_field", sorted(unknown)[0]
    if "price_mode" in body:
        if body["price_mode"] not in PRICE_MODES:
            return None, "price_mode_invalid", "price_mode"
        out["price_mode"] = body["price_mode"]
    if "currency" in body:
        if not isinstance(body["currency"], str) or not miniweb._CURRENCY_RE.match(body["currency"]):
            return None, "currency_invalid", "currency"
        out["currency"] = body["currency"]
    if "margin_pct" in body:
        v = body["margin_pct"]
        if v is None:
            out["margin_pct"] = None
        else:
            try:
                d = Decimal(str(v))
                ok = not isinstance(v, bool) and d.is_finite() and 0 <= d <= 500
            except Exception:
                ok = False
            if not ok:
                return None, "margin_pct_invalid", "margin_pct"
            out["margin_pct"] = d.quantize(Decimal("0.01"))
    if "eur_rate" in body:
        v = body["eur_rate"]
        if v is None:
            out["eur_rate"] = None                                  # zpet na zivy kurz Fio
        else:
            try:
                d = Decimal(str(v))
                ok = not isinstance(v, bool) and d.is_finite() and Decimal("0.0001") <= d <= Decimal("100000")
            except Exception:
                ok = False
            if not ok:
                return None, "eur_rate_invalid", "eur_rate"
            out["eur_rate"] = d.quantize(Decimal("0.0001"))
    if "countries" in body:
        v = body["countries"]
        items = v.split(",") if isinstance(v, str) else v
        if not isinstance(items, list) or not 1 <= len(items) <= 30 or not all(isinstance(x, str) and miniweb._COUNTRY_RE.match(x.strip().upper()) for x in items):
            return None, "countries_invalid", "countries"
        out["countries"] = ",".join(dict.fromkeys(x.strip().upper() for x in items))
    for k in ("inquiry_enabled", "orders_enabled"):
        if k in body:
            if not isinstance(body[k], bool):
                return None, f"{k}_invalid", k
            out[k] = 1 if body[k] else 0
    if "accent" in body:
        if body["accent"] is not None and not (isinstance(body["accent"], str) and miniweb._ACCENT_RE.match(body["accent"])):
            return None, "accent_invalid", "accent"
        out["accent"] = body["accent"]
    if "contact" in body:
        c = body["contact"]
        if not isinstance(c, dict) or set(c) - {"phone", "hours", "use_company"}:
            return None, "contact_invalid", "contact"
        cur_c = _contact(row["contact_json"])
        new = {"phone": cur_c["phone"], "hours": cur_c["hours"], "use_company": cur_c["use_company"]}
        for k, lim in (("phone", 40), ("hours", 120)):
            if k in c:
                t = str(c[k] or "").strip()
                if len(t) > lim or _BAD_TEXT.search(t):
                    return None, "contact_invalid", f"contact.{k}"
                new[k] = t
        if "use_company" in c:
            if not isinstance(c["use_company"], bool):
                return None, "contact_invalid", "contact.use_company"
            new["use_company"] = c["use_company"]
        out["contact_json"] = json.dumps({k: v for k, v in new.items() if v not in ("", False)} | ({"use_company": True} if new["use_company"] else {}), ensure_ascii=False)
    return out, None, None


@app.put("/api/admin/miniweb/shops/<int:storefront_id>")
@require_permission("miniweb", "upravit")
def admin_miniweb_shop_update(storefront_id):
    if request.mimetype != "application/json":
        return _err(400, "invalid_json")
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body:
        return _err(400, "invalid_json")
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM miniweb_shops WHERE storefront_id=%s FOR UPDATE", (storefront_id,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return _err(404, "not_found")
            changes, code, field = _clean(body, row)
            if changes is None:
                conn.rollback()
                return _err(400, code, field)
            after = {**row, **changes}
            # Objednavky smi bezet jen s kompletni cenou (zobrazena cena v EUR, marze) a kontrola plati po KAZDE zmene, ne jen pri zapnuti (externi revize 2026-10-03, #8): u zapnutych objednavek nejde
            # skryt cenu, zmenit menu ani smazat marzi.
            if after["orders_enabled"] and (after["price_mode"] != "shown" or after["currency"] != "EUR" or after["margin_pct"] is None):
                conn.rollback()
                return _err(422, "price_not_configured", "orders_enabled" if changes.get("orders_enabled") == 1 else next((k for k in ("price_mode", "currency", "margin_pct") if k in changes), "orders_enabled"))
            # Ceny se NIKDY neskryvaji (Robert 2026-10-03): shop ve stavu live nebo s objednavkami musi mit price_mode 'shown' (externi revize 2026-10-03, #3)
            if (row_status(cur, storefront_id) == "live" or after["orders_enabled"]) and after["price_mode"] != "shown":
                conn.rollback()
                return _err(422, "price_policy", "price_mode")
            if changes:
                cur.execute(f"UPDATE miniweb_shops SET {', '.join(k + '=%s' for k in changes)} WHERE storefront_id=%s", list(changes.values()) + [storefront_id])
            cur.execute("SELECT m.*, s.name, s.slug, s.primary_domain, s.status, s.lang FROM miniweb_shops m JOIN car_storefronts s ON s.id = m.storefront_id WHERE m.storefront_id=%s", (storefront_id,))
            fresh = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    try:
        log_audit(user["id"], "update", "miniweb_shop", storefront_id, {"zmeny": {k: str(v) for k, v in changes.items()}})
    except Exception:
        app.logger.exception("miniweb admin: audit zmeny shopu %s selhal", storefront_id)
    return _resp({"shop": _shop_json(fresh, {})})


def row_status(cur, storefront_id):
    cur.execute("SELECT status FROM car_storefronts WHERE id=%s", (storefront_id,))
    r = cur.fetchone()
    return r["status"] if r else None


def _paging():
    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), MAX_LIMIT)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return None, None
    return limit, offset


def _shop_arg():
    try:
        return int(request.args.get("shop"))
    except (TypeError, ValueError):
        return None


@app.get("/api/admin/miniweb/inquiries")
@require_permission("miniweb", "zobrazit")
def admin_miniweb_inquiries():
    sid, (limit, offset) = _shop_arg(), _paging()
    if sid is None or limit is None:
        return _err(400, "bad_request", "shop")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM miniweb_inquiries WHERE storefront_id=%s", (sid,))
            total = cur.fetchone()["n"]
            cur.execute("SELECT i.id, i.country, i.lang, i.created_at, i.crm_lead_id, l.contact_name, l.contact_email, l.contact_phone, l.company_name, l.unread_by_admin, "
                        "(SELECT COUNT(*) FROM miniweb_inquiry_items it WHERE it.inquiry_id=i.id) AS items "
                        "FROM miniweb_inquiries i LEFT JOIN crm_leads l ON l.id = i.crm_lead_id WHERE i.storefront_id=%s ORDER BY i.id DESC LIMIT %s OFFSET %s", (sid, limit, offset))
            rows = cur.fetchall()
    finally:
        conn.close()
    return _resp({"total": total, "inquiries": [{"id": r["id"], "created_at": r["created_at"].isoformat(sep=" ", timespec="seconds") if r["created_at"] else None, "country": r["country"],
                                                  "lang": r["lang"], "crm_lead_id": r["crm_lead_id"], "name": r["contact_name"], "email": r["contact_email"], "phone": r["contact_phone"],
                                                  "company": r["company_name"], "items": r["items"], "unread": bool(r["unread_by_admin"])} for r in rows]})


@app.get("/api/admin/miniweb/orders")
@require_permission("miniweb", "zobrazit")
def admin_miniweb_orders():
    sid, (limit, offset) = _shop_arg(), _paging()
    if sid is None or limit is None:
        return _err(400, "bad_request", "shop")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM shop_orders WHERE storefront_id=%s AND is_test=0 AND order_host IS NOT NULL", (sid,))
            total = cur.fetchone()["n"]
            cur.execute("SELECT * FROM shop_orders WHERE storefront_id=%s AND is_test=0 AND order_host IS NOT NULL ORDER BY id DESC LIMIT %s OFFSET %s", (sid, limit, offset))
            rows = cur.fetchall()
    finally:
        conn.close()
    return _resp({"total": total, "orders": [{"id": r["id"], "order_number": r["order_number"], "status": r["status"], "created_at": r["created_at"].isoformat(sep=" ", timespec="seconds"),
                                              "customer_name": r["customer_name"], "company": r["billing_name"], "company_id": r["billing_ico"], "vat_id": r["billing_dic"],
                                              "total_czk": float(r["total_czk"]), "shipping_review": int(r.get("shipping_review") or 0), "vat_mode": r.get("vat_mode"),
                                              "vat_check": r.get("vat_check"), "is_urgent": bool(r["is_urgent"]), "origin_label": orders_mod._origin_label(r)} for r in rows]})
