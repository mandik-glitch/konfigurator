"""Dealersky program, krok 4 (bot5, 2026-10-02; zadani Robert pres bot3, zelena bot3 2026-10-02): OBJEDNAVKA Z WEBU DEALERA pres API (cesta (b)).

Dealer, ktery si zvolil cestu 'dealer' (dealers.order_path), dokonci objednavku NA SVEM WEBU a u nas ji zada serverovym volanim s tajnym klicem (sk_..., scope quote/orders).
Nakupuje za DEALERSKOU cenu (sleva, ne provize; provize se u teto cesty nepocita, viz dealer_commissions), platba predem (zalohova faktura na dealera), zbozi se dorucuje
KONCOVEMU ZAKAZNIKOVI dealera. Zadne webhooky (dealer si stav zjistuje dotazem), zadne e-maily koncovemu zakaznikovi, jen bezne produkty (stejna brana jako feed a widget:
dealers.dealer_product_view), zadne sestavy, montaz ani priřezy.

Endpointy (Authorization: Bearer sk_..., vsechny odpovedi Cache-Control no-store, bez CORS - volaji se ze serveru dealera):
  POST /api/dealer/v1/quote            scope quote   - cenova kalkulace (cista cetba, nic se nezapisuje): polozky za dealerskou cenu, nabidka dopravy pro PSC, soucty, castka k uhrade
  POST /api/dealer/v1/orders           scope orders  - vytvoreni objednavky (idempotentni podle external_ref: stejny dotaz = stejna objednavka, jiny obsah = 409)
  GET  /api/dealer/v1/orders           scope orders  - seznam objednavek dealera (nejnovejsi prvni)
  GET  /api/dealer/v1/orders/<external_ref>  scope orders - stav jedne objednavky (zaplaceno, expedovano, platebni udaje)

Bezpecnost a spravnost (nemenit bez Roberta):
  * cena se VZDY pocita na serveru (klientem poslana cena se odmitne jako neznamy parametr); quote a objednavka pouzivaji tutez dealerskou cenu a tutez dopravu, a objednavka
    se pred zapisem porovna s kalkulaci (rozdil = rollback + chyba, nikdy tichy rozdil v castce); volitelne expected_total_net_czk chrani dealera pred zmenou ceny mezi quote a objednavkou,
  * jen aktivni dealer s cestou 'dealer' a klicem s prislusnym scope; neplatny/odvolany klic je stale 401 invalid_key (viz dealers.resolve_secret_key),
  * vstupy koncoveho zakaznika (jmeno, adresa, telefon) se overuji PRISNE a znaky < a > se odmitaji: PDF doklady vkladaji text do reportlab Paragraph (documents._esc/_P to hlida taky),
  * limity: pocet polozek, mnozstvi, hodnota objednavky, pocet objednavek za den a pocet nezaplacenych (app_settings dealer_api_*), limit pozadavku na klic,
  * objednavky dealera se serializuji podle dealer_id (cizi objednavku dealer nevidi ani neodhadne: 404),
  * e-maily: potvrzeni objednavky a zalohova faktura jdou jako VZDY do schvalovaci fronty (pravidlo 16) a na e-mail DEALERA (ne koncoveho zakaznika); tenhle modul nic neodesila primo.
"""
import datetime
import functools
import re

import pymysql
from flask import request

from app import app, get_conn, log_audit, _client_ip, _rate_limited
import dealers
from dealers import DealerAuthError, _json, _setting_float
import documents
import orders as orders_mod

MAX_LINES = 50
MAX_QTY = 10000
MAX_BODY_BYTES = 64 * 1024
DEFAULT_MAX_ORDERS_PER_DAY = 100
DEFAULT_MAX_OPEN_UNPAID = 30
DEFAULT_MAX_ORDER_NET_CZK = 500000.0
ORDERS_PER_MIN = 30                  # navic ke klicovemu limitu (dealers.resolve_secret_key): zapis objednavky je drazsi nez cteni

_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_BAD_CHARS_RE = re.compile(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")       # znacky a ridici znaky (novy radek a tabulator jen v poznamce)
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()/.-]{5,29}$")
_ZIP_RE = re.compile(r"^\d{3} ?\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_QUOTE_KEYS = {"items", "delivery_zip", "shipping_method_id"}
_ORDER_KEYS = {"external_ref", "items", "recipient", "shipping_method_id", "note", "expected_total_net_czk"}
_RECIPIENT_KEYS = {"name", "street", "city", "zip", "phone"}

_PRODUCT_COLS = ("id, name, sku, unit, price_czk_placeholder, stock_qty, active, weight_g, cfg_dily_id, length_mm, width_mm, height_mm, "
                 "is_board_material, is_profile_material, dealer_discount_percent, sale_price_czk, sale_price_from, sale_price_until, category_id")


class ApiError(Exception):
    """Chyba API dealera: HTTP stav, stroje citelny kod, cesky text, volitelne pole a dalsi udaje v odpovedi."""

    def __init__(self, status, code, message, field=None, extra=None):
        super().__init__(message)
        self.status, self.code, self.message, self.field, self.extra = status, code, message, field, extra

    def response(self):
        body = {"error": self.message, "code": self.code}
        if self.field:
            body["field"] = self.field
        if self.extra:
            body.update(self.extra)
        resp = _json(body, self.status)
        if self.status == 429:
            resp.headers["Retry-After"] = "60"
        return resp


def _money(v):
    return None if v is None else round(float(v), 2)


def _dt(v):
    return v.isoformat() if v is not None else None


# ---------------------------------------------------------------------------------------------------------------- vstupy
def _read_json(allowed):
    if request.content_length and request.content_length > MAX_BODY_BYTES:
        raise ApiError(413, "payload_too_large", "Požadavek je příliš velký.")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_json", "Tělo požadavku musí být JSON objekt (Content-Type: application/json).")
    for k in body:
        if k not in allowed:
            raise ApiError(400, "unknown_field", f"Pole {k} se neakceptuje (ceny a poplatky se počítají na serveru).", field=str(k)[:40])
    return body


def _int(value, field, lo, hi):
    if isinstance(value, bool) or not isinstance(value, int) or value < lo or value > hi:
        raise ApiError(400, "invalid_request", f"{field}: očekáváno celé číslo od {lo} do {hi}.", field=field)
    return value


def _text(value, field, lo, hi, multiline=False):
    if not isinstance(value, str):
        raise ApiError(400, "invalid_request", f"{field}: očekáván text.", field=field)
    s = re.sub(r"[ \t]+", " ", value.replace("\r", "")).strip() if multiline else re.sub(r"\s+", " ", value).strip()
    if multiline:
        s = re.sub(r"\n{3,}", "\n\n", s)
        bad = re.sub(r"[\n\t]", "", s)
    else:
        bad = s
    if len(s) < lo or len(s) > hi:
        raise ApiError(400, "invalid_request", f"{field}: délka musí být {lo} až {hi} znaků.", field=field)
    if _BAD_CHARS_RE.search(bad):
        raise ApiError(400, "invalid_request", f"{field}: obsahuje nepovolené znaky (< > nebo řídicí znaky).", field=field)
    return s


def _zip(value, field):
    if not isinstance(value, str) or not _ZIP_RE.match(value.strip()):
        raise ApiError(400, "invalid_request", f"{field}: očekáváno PSČ o 5 číslicích.", field=field)
    return re.sub(r"\D", "", value)


def _parse_items(raw):
    if not isinstance(raw, list) or not raw:
        raise ApiError(400, "invalid_request", "items: očekáván neprázdný seznam položek.", field="items")
    if len(raw) > MAX_LINES * 2:
        raise ApiError(400, "invalid_request", "items: příliš mnoho položek.", field="items")
    merged = {}
    for i, it in enumerate(raw):
        if not isinstance(it, dict):
            raise ApiError(400, "invalid_request", f"items[{i}]: očekáván objekt.", field=f"items[{i}]")
        for k in it:
            if k not in ("product_id", "qty"):
                raise ApiError(400, "unknown_field", f"items[{i}].{str(k)[:30]}: položka přijímá jen product_id a qty.", field=f"items[{i}].{str(k)[:30]}")
        pid = _int(it.get("product_id"), f"items[{i}].product_id", 1, 2147483647)
        qty = _int(it.get("qty"), f"items[{i}].qty", 1, MAX_QTY)
        merged[pid] = merged.get(pid, 0) + qty
    if len(merged) > MAX_LINES:
        raise ApiError(400, "invalid_request", f"items: nejvýše {MAX_LINES} různých produktů v jedné objednávce.", field="items")
    for pid, qty in merged.items():
        if qty > MAX_QTY:
            raise ApiError(400, "invalid_request", f"items: součet množství produktu {pid} překračuje {MAX_QTY}.", field="items")
    return sorted(merged.items())          # stabilni poradi = stabilni poradi zamku produktu v jadru objednavky (zadny deadlock dvou objednavek)


def _parse_recipient(raw):
    if not isinstance(raw, dict):
        raise ApiError(400, "invalid_request", "recipient: očekáván objekt (name, street, city, zip, phone).", field="recipient")
    for k in raw:
        if k not in _RECIPIENT_KEYS:
            raise ApiError(400, "unknown_field", f"recipient.{str(k)[:30]}: pole se neakceptuje.", field=f"recipient.{str(k)[:30]}")
    phone = _text(raw.get("phone"), "recipient.phone", 6, 30)
    if not _PHONE_RE.match(phone):
        raise ApiError(400, "invalid_request", "recipient.phone: neplatné telefonní číslo.", field="recipient.phone")
    return {"name": _text(raw.get("name"), "recipient.name", 2, 100), "street": _text(raw.get("street"), "recipient.street", 2, 100),
            "city": _text(raw.get("city"), "recipient.city", 2, 60), "zip": _zip(raw.get("zip"), "recipient.zip"), "phone": phone}


def _compose_delivery(r):
    """Doruceni koncovemu zakaznikovi jako jedna adresa (delivery_address je volny text, doklady ji tisknou jako 'Doručovací adresa')."""
    return f"{r['name']}, {r['street']}, {r['zip'][:3]} {r['zip'][3:]} {r['city']}, tel. {r['phone']}"


# ---------------------------------------------------------------------------------------------------------------- kalkulace
class Calc:
    """Vysledek kalkulace (quote i podklad objednavky): radky, doprava, soucty. Jen cisla, nic se nezapisuje."""
    __slots__ = ("lines", "items_net", "shipping", "options", "payment", "total_net", "vat", "amount_due", "has_missing_stock", "vat_rate")


def _payment_method(cur):
    """Platba predem: nejnizsi aktivni platebni metoda se zalohovou fakturou (dealer nema fakturu na splatnost, Robert 2026-10-02)."""
    cur.execute("SELECT id, name, price_czk FROM shop_payment_methods WHERE active=1 AND requires_advance_invoice=1 ORDER BY id LIMIT 1")
    pm = cur.fetchone()
    if not pm:
        raise ApiError(503, "payment_unavailable", "Platba předem momentálně není k dispozici.")
    return pm


def price_order(cur, dealer, items, delivery_zip, shipping_method_id=None):
    """Dealerska kalkulace, JEDINY vypocet pro quote i objednavku. items = [(product_id, qty)] unikatni, serazene. Vyhodi ApiError."""
    lines, total, weight_kg, volume_m3, missing = [], 0.0, 0.0, 0.0, False
    for pid, qty in items:
        cur.execute(f"SELECT {_PRODUCT_COLS} FROM shop_products WHERE id=%s", (pid,))
        p = cur.fetchone()
        view = dealers.dealer_product_view(cur, pid, mode="none") if p else None
        if view is None:
            raise ApiError(422, "product_not_available", f"Produkt {pid} není pro dealery k dispozici.", field="items")
        unit, basis = dealers.dealer_effective_price(cur, p, dealer)
        if unit is None:
            raise ApiError(422, "no_dealer_price", f"Pro produkt {pid} nemáte nastavenou dealerskou cenu.", field="items")
        line_total = round(unit * qty, 2)
        total += line_total
        weight_kg += float(p["weight_g"] or 0) / 1000.0 * qty
        unit_volume = orders_mod._product_unit_volume_m3(cur, p)
        if unit_volume is not None:
            volume_m3 += unit_volume * qty
        if (p["stock_qty"] or 0) < qty:
            missing = True
        lines.append({"product_id": pid, "sku": view["sku"], "name": p["name"], "unit": view["unit"], "qty": qty, "unit_price_net_czk": float(unit),
                      "line_net_czk": line_total, "price_basis": basis, "availability": view["availability"],
                      "_profile": bool(p["is_profile_material"]) and not p["is_board_material"]})
    pm = _payment_method(cur)
    payment_price = float(pm["price_czk"])
    cur.execute("SELECT id, name, price_czk, pricing_mode FROM shop_shipping_methods WHERE active=1 AND pricing_mode='zip_weight' ORDER BY sort_order, id")
    options, errors = [], {}
    for sm in cur.fetchall():
        try:
            price, _km, _basis = orders_mod._resolve_toptrans_price(cur, sm["id"], delivery_zip, weight_kg, volume_m3)
            options.append({"id": sm["id"], "name": sm["name"], "price_net_czk": round(float(price), 2)})
        except orders_mod._OrderCreateError as e:
            errors[sm["id"]] = e.message
    chosen = None
    if shipping_method_id is not None:
        chosen = next((o for o in options if o["id"] == shipping_method_id), None)
        if chosen is None:
            msg = errors.get(shipping_method_id) or "Zvolený způsob dopravy není pro dealery k dispozici."
            raise ApiError(422, "shipping_unavailable", msg, field="shipping_method_id")
    elif not options and errors:
        raise ApiError(422, "shipping_unavailable", next(iter(errors.values())), field="delivery_zip")
    shipping_price = chosen["price_net_czk"] if chosen else 0.0
    c = Calc()
    c.lines, c.items_net, c.options, c.has_missing_stock = lines, round(total, 2), options, missing
    c.shipping = chosen
    c.payment = {"id": pm["id"], "name": pm["name"], "price_net_czk": payment_price}
    c.total_net = round(total + shipping_price + payment_price, 2)
    # DPH a castka k uhrade presne stejnym vypoctem jako zalohova faktura (documents._build_items_with_vat/_totals), at se quote shoduje s fakturou na halere
    order_like = {"shipping_method_name": chosen["name"] if chosen else None, "shipping_price_czk": shipping_price,
                  "payment_method_name": pm["name"], "payment_price_czk": payment_price}
    items_db = [{"product_name_snapshot": ln["name"], "unit_price_czk": ln["unit_price_net_czk"], "qty": ln["qty"], "line_total_czk": ln["line_net_czk"],
                 "product_is_profile_material": ln["_profile"]} for ln in lines]
    doc_items = documents._build_items_with_vat(order_like, items_db)
    _net, vat, _gross_exact, gross_rounded, _rounding = documents._totals(doc_items)
    c.vat, c.amount_due, c.vat_rate = float(vat), float(gross_rounded), float(documents.VAT_RATE)
    return c


def _calc_payload(c):
    return {
        "currency": "CZK", "prices_include_vat": False, "vat_rate": c.vat_rate,
        "items": [{k: v for k, v in ln.items() if not k.startswith("_")} for ln in c.lines],
        "items_net_czk": c.items_net,
        "shipping_options": c.options,
        "shipping": c.shipping,
        "payment_method": c.payment["name"],
        "total_net_czk": c.total_net, "vat_czk": c.vat, "amount_due_czk": c.amount_due,
        "in_stock": not c.has_missing_stock,
    }


# ---------------------------------------------------------------------------------------------------------------- overeni a spolecne
def _auth(scope):
    """-> (dealer, key). Klic i dealer se overuji znovu v transakci (zamek radku dealera) pri zapisu; tady jen vstupni brana."""
    dealer, key = dealers.resolve_secret_key(request.headers.get("Authorization"), _client_ip(), scope=scope)
    if dealer["order_path"] != "dealer":
        raise ApiError(403, "order_path_not_dealer", "Objednávky přes API jsou dostupné jen dealerům s cestou „dokončí se na webu dealera“.")
    return dealer, key


def _guard(fn):
    """Obal endpointu: DealerAuthError a ApiError -> JSON odpoved, cokoli jineho -> 500 bez detailu (loguje se)."""
    @functools.wraps(fn)
    def wrapped(*a, **k):
        try:
            return fn(*a, **k)
        except DealerAuthError as e:
            return e.response()
        except ApiError as e:
            return e.response()
        except Exception:
            app.logger.exception("dealer API: neocekavana chyba v %s", fn.__name__)
            return _json({"error": "Interní chyba, zkuste to později.", "code": "internal_error"}, 500)
    return wrapped


def _limits(cur):
    return {"per_day": int(_setting_float(cur, "dealer_api_max_orders_per_day", DEFAULT_MAX_ORDERS_PER_DAY)),
            "open_unpaid": int(_setting_float(cur, "dealer_api_max_open_unpaid", DEFAULT_MAX_OPEN_UNPAID)),
            "max_net": _setting_float(cur, "dealer_api_max_order_net_czk", DEFAULT_MAX_ORDER_NET_CZK)}


def _digits(value):
    return re.sub(r"\D", "", value or "")


def _missing_profile(dealer):
    missing = [k for k in ("name", "ico", "billing_street", "billing_city", "billing_zip", "contact_email") if not (dealer.get(k) or "").strip()]
    if "contact_email" not in missing and not _EMAIL_RE.match(dealer["contact_email"].strip()):
        missing.append("contact_email")
    if "billing_zip" not in missing and len(_digits(dealer["billing_zip"])) != 5:
        missing.append("billing_zip")
    return missing


# ---------------------------------------------------------------------------------------------------------------- serializace objednavky
def _order_by_ref(cur, dealer_id, ref):
    cur.execute("SELECT * FROM shop_orders WHERE dealer_id=%s AND order_path='dealer' AND dealer_external_ref=%s", (dealer_id, ref))
    return cur.fetchone()


def _order_payload(cur, o):
    cur.execute("SELECT product_id, product_name_snapshot, unit_price_czk, qty, line_total_czk FROM shop_order_items WHERE order_id=%s AND product_id IS NOT NULL ORDER BY id", (o["id"],))
    items = [{"product_id": r["product_id"], "name": r["product_name_snapshot"], "qty": r["qty"], "unit_price_net_czk": _money(r["unit_price_czk"]),
              "line_net_czk": _money(r["line_total_czk"])} for r in cur.fetchall()]
    cur.execute("SELECT MIN(changed_at) AS t FROM shop_order_status_history WHERE order_id=%s AND status IN ('expedovana','fakturovana')", (o["id"],))
    shipped = cur.fetchone()["t"]
    cur.execute("SELECT id, document_number, variable_symbol, amount_due_czk, due_date FROM shop_documents WHERE order_id=%s AND document_type='proforma_invoice' ORDER BY id DESC LIMIT 1", (o["id"],))
    pro = cur.fetchone()
    order_like = {"shipping_method_name": o["shipping_method_name"], "shipping_price_czk": o["shipping_price_czk"],
                  "payment_method_name": o["payment_method_name"], "payment_price_czk": o["payment_price_czk"]}
    cur.execute("SELECT product_name_snapshot, unit_price_czk, qty, line_total_czk FROM shop_order_items WHERE order_id=%s AND product_id IS NOT NULL ORDER BY id", (o["id"],))
    doc_items = documents._build_items_with_vat(order_like, cur.fetchall())
    _net, vat, _ge, gross_rounded, _r = documents._totals(doc_items)
    payment = None
    if pro:
        try:
            iban = documents._cz_account_to_iban(documents.SUPPLIER["bank_account"])
        except Exception:
            iban = None
        payment = {"method": o["payment_method_name"], "document_number": pro["document_number"], "variable_symbol": pro["variable_symbol"],
                   "amount_due_czk": _money(pro["amount_due_czk"]), "due_date": _dt(pro["due_date"]),
                   "bank_account": documents.SUPPLIER["bank_account"], "iban": iban}
    paid_at = o.get("payment_received_at") or o.get("bank_paid_at")
    return {
        "order_number": o["order_number"], "external_ref": o["dealer_external_ref"],
        "status": o["status"], "status_label": orders_mod.STATUS_LABELS_CZ.get(o["status"], o["status"]),
        "created_at": _dt(o["created_at"]), "paid": bool(o.get("bank_paid")) or o.get("payment_received_at") is not None, "paid_at": _dt(paid_at),
        "shipped_at": _dt(shipped),
        "items": items,
        "shipping": {"name": o["shipping_method_name"], "price_net_czk": _money(o["shipping_price_czk"])} if o["shipping_method_name"] else None,
        "delivery": {"address": o["delivery_address"], "zip": o["delivery_zip"]},
        "note": o["note"],
        "currency": "CZK", "prices_include_vat": False, "vat_rate": float(documents.VAT_RATE),
        "total_net_czk": _money(o["total_czk"]), "vat_czk": float(vat), "amount_due_czk": float(gross_rounded),
        "payment": payment,
    }


def _same_request(cur, o, items, recipient, shipping_method_id):
    cur.execute("SELECT product_id, SUM(qty) AS q FROM shop_order_items WHERE order_id=%s AND product_id IS NOT NULL GROUP BY product_id", (o["id"],))
    have = {r["product_id"]: int(r["q"]) for r in cur.fetchall()}
    cur.execute("SELECT name FROM shop_shipping_methods WHERE id=%s", (shipping_method_id,))
    sm = cur.fetchone()
    return (have == dict(items) and o["delivery_zip"] == recipient["zip"] and o["delivery_address"] == _compose_delivery(recipient)
            and bool(sm) and o["shipping_method_name"] == sm["name"])


# ---------------------------------------------------------------------------------------------------------------- endpointy
@app.post("/api/dealer/v1/quote")
@_guard
def dealer_api_quote():
    """Kalkulace dealerske objednavky (cista cetba). {items:[{product_id, qty}], delivery_zip, shipping_method_id?} -> radky za dealerskou cenu, shipping_options pro PSC a hmotnost,
    soucty a castka k uhrade (stejny vypocet jako zalohova faktura). Bez shipping_method_id vraci jen nabidku dopravy a soucty bez dopravy."""
    dealer, _key = _auth("quote")
    body = _read_json(_QUOTE_KEYS)
    items = _parse_items(body.get("items"))
    zip_code = _zip(body.get("delivery_zip"), "delivery_zip")
    sid = body.get("shipping_method_id")
    if sid is not None:
        sid = _int(sid, "shipping_method_id", 1, 2147483647)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            c = price_order(cur, dealer, items, zip_code, sid)
    finally:
        conn.close()
    return _json(_calc_payload(c))


@app.post("/api/dealer/v1/orders")
@_guard
def dealer_api_order_create():
    """Vytvoreni dealerske objednavky. {external_ref, items:[{product_id, qty}], recipient:{name, street, city, zip, phone}, shipping_method_id, note?, expected_total_net_czk?}.
    201 = vytvorena, 200 + Idempotent-Replayed = stejny external_ref a stejny obsah uz existuje (vraci se puvodni objednavka), 409 external_ref_conflict = jiny obsah."""
    dealer, key = _auth("orders")
    ip = _client_ip()
    if _rate_limited(f"dealer_orders:{key['id']}", ORDERS_PER_MIN, 60):
        raise DealerAuthError(429, "rate_limited")
    body = _read_json(_ORDER_KEYS)
    ref = body.get("external_ref")
    if not isinstance(ref, str) or not _REF_RE.match(ref):
        raise ApiError(400, "invalid_request", "external_ref: 1 až 64 znaků (písmena, číslice a . _ : -), vaše unikátní označení objednávky.", field="external_ref")
    items = _parse_items(body.get("items"))
    recipient = _parse_recipient(body.get("recipient"))
    sid = _int(body.get("shipping_method_id"), "shipping_method_id", 1, 2147483647)
    note = _text(body["note"], "note", 0, 500, multiline=True) if body.get("note") not in (None, "") else None
    expected = body.get("expected_total_net_czk")
    if expected is not None and (isinstance(expected, bool) or not isinstance(expected, (int, float)) or expected < 0 or expected > 1e9):
        raise ApiError(400, "invalid_request", "expected_total_net_czk: očekáváno nezáporné číslo.", field="expected_total_net_czk")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # serializace objednavek jednoho dealera: zamek radku dealera, pak teprve kontrola duplicity - dva soubezne stejne pozadavky nemuzou vytvorit dve objednavky
            cur.execute("SELECT * FROM dealers WHERE id=%s FOR UPDATE", (dealer["id"],))
            dealer = cur.fetchone()
            if not dealers._dealer_usable(dealer) or dealer["order_path"] != "dealer":
                conn.rollback()
                raise DealerAuthError(403, "dealer_inactive")
            existing = _order_by_ref(cur, dealer["id"], ref)
            if existing:
                same = _same_request(cur, existing, items, recipient, sid)
                payload = _order_payload(cur, existing) if same else None
                conn.rollback()
                if not same:
                    raise ApiError(409, "external_ref_conflict", "Objednávka s tímto external_ref už existuje s jiným obsahem.", field="external_ref")
                resp = _json({"order": payload, "idempotent_replay": True}, 200)
                resp.headers["Idempotent-Replayed"] = "true"
                return resp
            missing = _missing_profile(dealer)
            if missing:
                conn.rollback()
                raise ApiError(409, "dealer_profile_incomplete", "Profil dealera je neúplný (firma, IČO, fakturační adresa, e-mail) - doplňte ho u správce.", extra={"missing": missing})
            lim = _limits(cur)
            today = datetime.datetime.combine(dealers._now().date(), datetime.time.min)
            cur.execute("SELECT COUNT(*) AS n FROM shop_orders WHERE dealer_id=%s AND order_path='dealer' AND created_at >= %s", (dealer["id"], today))
            if cur.fetchone()["n"] >= lim["per_day"]:
                conn.rollback()
                raise ApiError(429, "daily_limit", "Byl dosažen denní limit počtu objednávek.", extra={"limit": lim["per_day"]})
            cur.execute("SELECT COUNT(*) AS n FROM shop_orders WHERE dealer_id=%s AND order_path='dealer' AND status <> 'zrusena' AND payment_received_at IS NULL AND bank_paid=0", (dealer["id"],))
            if cur.fetchone()["n"] >= lim["open_unpaid"]:
                conn.rollback()
                raise ApiError(429, "open_orders_limit", "Máte příliš mnoho nezaplacených objednávek, nejdřív uhraďte nebo zrušte stávající.", extra={"limit": lim["open_unpaid"]})
            calc = price_order(cur, dealer, items, recipient["zip"], sid)
            if calc.total_net > lim["max_net"]:
                conn.rollback()
                raise ApiError(422, "order_too_large", "Hodnota objednávky překračuje limit, kontaktujte nás.", extra={"limit_net_czk": lim["max_net"]})
            if expected is not None and abs(round(float(expected), 2) - calc.total_net) > 0.005:
                conn.rollback()
                raise ApiError(409, "price_changed", "Cena objednávky se od kalkulace změnila.", extra={"current_total_net_czk": calc.total_net, "current_amount_due_czk": calc.amount_due})
            core_body = {
                "items": [{"product_id": pid, "qty": qty} for pid, qty in items],
                "customer_name": dealer["name"], "customer_email": dealer["contact_email"].strip().lower(), "customer_phone": dealer["contact_phone"],
                "billing_name": dealer["name"], "billing_ico": dealer["ico"], "billing_dic": dealer["dic"],
                "billing_address": f"{dealer['billing_street']}, {_digits(dealer['billing_zip'])[:3]} {_digits(dealer['billing_zip'])[3:]} {dealer['billing_city']}",
                "billing_zip": _digits(dealer["billing_zip"]),
                "delivery_address": _compose_delivery(recipient), "delivery_zip": recipient["zip"], "note": note,
                "shipping_method_id": sid, "payment_method_id": calc.payment["id"],
            }
            try:
                result = orders_mod._resolve_and_insert_order(cur, core_body, attribute_user_id=dealer["user_id"], profile_user_id=None, dealer=dealer)
            except orders_mod._OrderCreateError as e:
                conn.rollback()
                raise ApiError(e.status_code if e.status_code in (400, 409, 422) else 422, "order_rejected", e.message)
            if abs(float(result["total"]) - calc.total_net) > 0.005:
                conn.rollback()
                app.logger.error("dealer API: nesoulad kalkulace %s a objednavky %s (dealer %s, ref %s)", calc.total_net, result["total"], dealer["id"], ref)
                raise ApiError(500, "price_mismatch", "Interní chyba výpočtu ceny, objednávka nebyla vytvořena.")
            try:
                cur.execute("UPDATE shop_orders SET dealer_id=%s, order_path='dealer', dealer_external_ref=%s WHERE id=%s", (dealer["id"], ref, result["order_id"]))
            except pymysql.err.IntegrityError:          # zamek dealera to vylucuje, jistota pro pripad souboje mimo tenhle kod
                conn.rollback()
                raise ApiError(409, "external_ref_conflict", "Objednávka s tímto external_ref už existuje.", field="external_ref")
            cur.execute("INSERT INTO shop_order_status_history (order_id, status, changed_by, note) VALUES (%s,'nova',NULL,%s)",
                        (result["order_id"], f"Objednávka přijata přes API dealera {dealer['name']} (ref {ref})."))
            cur.execute("SELECT * FROM shop_orders WHERE id=%s", (result["order_id"],))
            payload = _order_payload(cur, cur.fetchone())
        conn.commit()
    finally:
        conn.close()
    try:
        orders_mod._send_order_emails_bg(result)         # potvrzeni objednavky + zalohova faktura DO SCHVALOVACI FRONTY (auto=True), prijemce = e-mail dealera
    except Exception:
        app.logger.exception("dealer API: zarazeni e-mailu objednavky %s selhalo", result.get("order_number"))
    try:
        log_audit(None, "dealer_api_order", "shop_order", result["order_id"],
                  {"dealer_id": dealer["id"], "key": key["public_id"], "ref": ref, "total_net_czk": calc.total_net, "ip": ip})
    except Exception:
        app.logger.exception("dealer API: audit objednavky %s selhal", result.get("order_number"))
    return _json({"order": payload, "idempotent_replay": False}, 201)


@app.get("/api/dealer/v1/orders")
@_guard
def dealer_api_orders_list():
    """Objednavky dealera pres API, nejnovejsi prvni. ?page=1 &page_size=50 (max 50)."""
    dealer, _key = _auth("orders")
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(50, max(1, int(request.args.get("page_size", 50))))
    except ValueError:
        raise ApiError(400, "invalid_request", "page a page_size musí být čísla.")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM shop_orders WHERE dealer_id=%s AND order_path='dealer' AND dealer_external_ref IS NOT NULL", (dealer["id"],))
            total = cur.fetchone()["n"]
            cur.execute("SELECT * FROM shop_orders WHERE dealer_id=%s AND order_path='dealer' AND dealer_external_ref IS NOT NULL ORDER BY id DESC LIMIT %s OFFSET %s",
                        (dealer["id"], page_size, (page - 1) * page_size))
            out = []
            for o in cur.fetchall():
                p = _order_payload(cur, o)
                out.append({k: p[k] for k in ("order_number", "external_ref", "status", "status_label", "created_at", "paid", "paid_at", "shipped_at", "total_net_czk", "amount_due_czk")})
    finally:
        conn.close()
    return _json({"orders": out, "total": total, "page": page, "page_size": page_size})


@app.get("/api/dealer/v1/orders/<external_ref>")
@_guard
def dealer_api_order_get(external_ref):
    """Stav jedne objednavky podle external_ref dealera (cizi objednavky a neexistujici = 404)."""
    dealer, _key = _auth("orders")
    if not _REF_RE.match(external_ref or ""):
        raise ApiError(404, "not_found", "Objednávka neexistuje.")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            o = _order_by_ref(cur, dealer["id"], external_ref)
            if not o:
                raise ApiError(404, "not_found", "Objednávka neexistuje.")
            payload = _order_payload(cur, o)
    finally:
        conn.close()
    return _json({"order": payload})
