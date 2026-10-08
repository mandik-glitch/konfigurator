"""Objednavka konfigurovaneho stolu HOSTEM bez registrace (hlavni e-shop; bot5, 2026-10-04; Robert pres bot9: "objednavka HOSTA bez registrace = ANO", montaz = nastavitelne % z ceny stolu, vychozi 12 %).

  POST /api/shop/stul/quote   cenova kalkulace hostovskeho kosiku (cista cetba): {items:[{product_id, qty, montaz?, configuration:{selection, rules_version}}], delivery_zip?}
  POST /api/shop/stul/order   objednavka hosta: kontakt, dodaci (a fakturacni) adresa, doprava, souhlas -> vznika bezna objednavka v shop_orders BEZ uctu (user_id NULL)

Kosik drzi prohlizec (localStorage, jen volby, zadna cena); server cenu VZDY pocita znovu (konfigurator stolu: konfigurace_kosik.vyres), klientova cena se nebere. Pravidla (stejna jako u mini-shopu, krok 2):
  * Ceny v Kc BEZ DPH, DPH CZ 21 % (documents.VAT_RATE) se pricita; dodani jen v CR; montaz jen volitelne a jen pri nastavenem % u typu sestavy (sestava_typ_sluzba STUL_SKLAD / montaz, vychozi 12 %, admin
    ji meni v Typech sestav): cena montaze = % z ceny konfigurace bez DPH, v objednavce SAMOSTATNY radek "Montaz" (product_id NULL), DPH 21 %.
  * ZADNA AUTOMATICKA PROFORMA A ZADNY E-MAIL (pravidlo 16): objednavka vznika bez platebni metody (jadro tedy nevystavi zalohovou fakturu), s priznakem shipping_review = 1 (doprava ke schvaleni
    zamestnancem, POST /api/admin/orders/<id>/shipping), proformu vystavi zamestnanec po schvaleni dopravy; e-mail s fakturou jde do schvalovaci fronty. Host na obrazovce vidi cislo objednavky a ze zalohovou
    fakturu dostane po potvrzeni dopravy (e-mail jen po schvaleni).
  * Doprava: "toptrans" (odhad podle PSC a UPLNE hmotnosti; dnes chybi hmotnosti dilu, cena se nepocita a rozhodne zamestnanec), "quote" (po dohode), "pickup" (osobni odber, cena 0).
  * Ochrany: rate limity (IP, e-mail za den), honeypot, strop mnozstvi a hodnoty, otisk obsahu + pojmenovany zamek proti dvojitemu odeslani (stejny obsah do 5 minut = puvodni objednavka),
    vstupy jen jako retezce, zakaznicky text se do interni poznamky dava bez hranatych zavorek; objednavka vznika JEN u produktu, ktery je aktivni (pravidlo 54 se neobchazi).
"""
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP

from flask import request, jsonify

from app import app, get_conn, log_audit, _client_ip, _rate_limited
import documents
import konfigurace_kosik as kk
import orders as orders_mod
import stul_shop
from miniweb import ShopError, _plain, _str_only, _EMAIL_RE, _company_ids, _norm_id, _VAT_RE
from miniweb_objednavky import ObjChyba, _body, _address, _PHONE_RE, _safe_note

QUOTE_LIMIT_PER_IP = (60, 60)
ORDER_LIMIT_PER_IP = (5, 600)
ORDER_LIMIT_PER_EMAIL_DAY = 5
MAX_LINES = 10
MAX_QTY = kk.MAX_MNOZSTVI
MAX_ORDER_CZK = 2000000
MAX_NOTE = 1000
SHIPPING = ("toptrans", "quote", "pickup")
LABEL = {"toptrans": "Doprava Toptrans", "quote": "Doprava po dohodě (cenu upřesníme)", "pickup": "Osobní odběr"}
ADMIN_SHIPPING = {"toptrans": "Doprava Toptrans", "quote": "Doprava po dohodě (cenu upřesníme)", "pickup": "Osobní odběr"}


def _json(payload, status=200):
    r = jsonify(payload)
    r.status_code = status
    r.headers["Cache-Control"] = "no-store"
    return r


def _guard(fn):
    def wrapped(*a, **k):
        try:
            return fn(*a, **k)
        except ObjChyba as e:
            return _json({"error": e.code, **({"field": e.field} if e.field else {}), **e.extra}, e.status)
        except ShopError as e:
            return _json({"error": e.code, **({"field": e.field} if e.field else {})}, e.status)
        except Exception:
            app.logger.exception("stul host objednavka: neocekavana chyba v %s", fn.__name__)
            return _json({"error": "internal_error"}, 500)
    wrapped.__name__ = fn.__name__
    return wrapped


def _q(x):
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _items(cur, raw):
    """Polozky z prohlizece: product_id (karta konfigurovatelneho stolu), qty, montaz (bool), configuration. Cena a cokoli jineho se ignoruje. Jen aktivni a konfigurovatelny produkt."""
    if not isinstance(raw, list) or not raw or len(raw) > MAX_LINES:
        raise ShopError(400, "items_invalid", "items")
    out = []
    for i, it in enumerate(raw):
        if not isinstance(it, dict):
            raise ShopError(400, "items_invalid", f"items[{i}]")
        pid, qty = orders_mod_int(it.get("product_id")), orders_mod_int(it.get("qty", 1))
        if qty is None or not 1 <= qty <= MAX_QTY:
            raise ShopError(400, "items_invalid", f"items[{i}].qty")
        if pid is None or not stul_shop.konfigurovatelny(pid):
            raise ObjChyba(422, "product_not_available", f"items[{i}]")
        cur.execute("SELECT id, name, active, is_archived FROM shop_products WHERE id=%s", (pid,))
        p = cur.fetchone()
        if not p or not p["active"] or p["is_archived"]:
            raise ObjChyba(422, "product_not_available", f"items[{i}]")
        conf = it.get("configuration")
        if not isinstance(conf, dict) or not isinstance(conf.get("selection"), dict) or len(json.dumps(conf, default=str)) > 6000:
            raise ShopError(400, "configuration_required", f"items[{i}].configuration")
        rv = conf.get("rules_version")
        out.append({"pid": pid, "name": p["name"], "qty": qty, "montaz": it.get("montaz") is True, "selection": conf["selection"], "rules_version": rv if isinstance(rv, str) and len(rv) <= 64 else None})
    return out


def orders_mod_int(v):
    if isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _spocti(cur, items, strict):
    """JEDINY vypocet pro quote i objednavku -> dict {lines, goods, montaz, kg, weight_complete}. Cena z konfigurace_kosik.vyres, montaz = res['montaz_czk'] (% z ceny konfigurace)."""
    merged, lines = {}, []
    for it in items:
        try:
            res = kk.vyres(cur, it["pid"], it["selection"], "cs", it["rules_version"])
        except kk.KonfiguraceChyba as e:
            if e.code == "invalid_configuration" and not strict:
                lines.append({"product_id": it["pid"], "name": it["name"], "qty": it["qty"], "made_to_order": True, "stock_qty": None, "unit_price_czk": None, "line_total_czk": None,
                              "montaz_zvolena": False, "montaz_pct": None, "montaz_czk": None, "montaz_total_czk": None,
                              "configuration": {"valid": False, "changed": False, "kod": None, "summary": [], "errors": e.errors or [], "weight_kg": None, "weight_complete": False}})
                continue
            raise ObjChyba(e.status, "product_not_available" if e.code == "not_configurable" else e.code, None, {"errors": e.errors} if e.errors else {})
        if it["montaz"] and (res["montaz_czk"] is None):
            raise ObjChyba(409, "montaz_unavailable", "items")
        key = (it["pid"], res["hash"], it["montaz"])
        if key in merged:
            merged[key]["qty"] += it["qty"]
            if merged[key]["qty"] > MAX_QTY:
                raise ShopError(400, "items_invalid", "items")
            continue
        unit = _q(res["net_czk"])
        mont = _q(res["montaz_czk"]) if it["montaz"] else None
        line = {"product_id": it["pid"], "name": it["name"], "qty": it["qty"], "made_to_order": True, "stock_qty": None, "unit_price_czk": float(unit), "line_total_czk": None,
                "montaz_zvolena": it["montaz"], "montaz_pct": res["montaz_pct"], "montaz_czk": float(mont) if mont is not None else None, "montaz_total_czk": None,
                "_unit": unit, "_mont": mont, "_kg": float(res["weight_kg"] or 0.0), "_kg_ok": bool(res["weight_complete"]), "_requested": {"selection": it["selection"], "rules_version": it["rules_version"]},
                "configuration": {"valid": True, "changed": res["selection"] != it["selection"], "kod": res["kod"], "hash": res["hash"], "selection": res["selection"], "rules_version": res["rules_version"],
                                  "summary": res["summary"], "errors": [], "weight_kg": float(res["weight_kg"]) if res["weight_complete"] else None, "weight_complete": bool(res["weight_complete"])}}
        merged[key] = line
        lines.append(line)
    goods, montaz, kg, ok = Decimal(0), Decimal(0), 0.0, True
    for ln in lines:
        if ln.get("_unit") is not None:
            ln["line_total_czk"] = float(_q(ln["_unit"] * ln["qty"]))
            goods += ln["_unit"] * ln["qty"]
            if ln["_mont"] is not None:
                ln["montaz_total_czk"] = float(_q(ln["_mont"] * ln["qty"]))
                montaz += ln["_mont"] * ln["qty"]
            kg += ln["_kg"] * ln["qty"]
            ok = ok and ln["_kg_ok"]
    return {"lines": lines, "goods": _q(goods), "montaz": _q(montaz), "kg": kg, "weight_complete": ok}


def _public_lines(lines):
    """Verejne radky: bez internich poli a BEZ sazby montaze (zakaznik % nevidi, jen castku; Robert pres bot9 2026-10-04)."""
    return [{k: v for k, v in ln.items() if not k.startswith("_") and k != "montaz_pct"} for ln in lines]


def _toptrans(cur, zip_raw, calc):
    """Odhad Toptrans (orders._resolve_toptrans_price, PSC dodaci adresy + UPLNA hmotnost) -> {net (Kc nebo None), reason}; jinak cenu urci zamestnanec pri schvaleni."""
    if not zip_raw or len(re.sub(r"\D", "", zip_raw)) != 5:
        return {"net": None, "reason": "zip_missing"}
    if not calc["weight_complete"] or calc["kg"] <= 0:
        return {"net": None, "reason": "weight_incomplete"}
    cur.execute("SELECT id FROM shop_shipping_methods WHERE active=1 AND pricing_mode='zip_weight' ORDER BY sort_order, id LIMIT 1")
    sm = cur.fetchone()
    if not sm:
        return {"net": None, "reason": "price_unavailable"}
    try:
        czk, _band, _basis = orders_mod._resolve_toptrans_price(cur, sm["id"], zip_raw, calc["kg"], 0.0)
    except orders_mod._OrderCreateError:
        return {"net": None, "reason": "price_unavailable"}
    return {"net": float(_q(czk)), "reason": None}


def _shipping_options(top):
    return [{"id": "toptrans", "label": LABEL["toptrans"], "net": top["net"], "estimated": True, **({"reason": top["reason"]} if top["reason"] else {})},
            {"id": "quote", "label": LABEL["quote"], "net": None}, {"id": "pickup", "label": LABEL["pickup"], "net": 0}]


def _vat(net, radky=None):
    """DPH CZ (cena s DPH se spotrebiteli ukazuje VZDY): rate, amount, total_with_vat (presne) a total_with_vat_rounded = castka k uhrade na zalohove fakture (DPH po radcich zaokrouhlene na halere a celek na cele Kc,
    stejne jako documents._totals). `radky` = seznam cen radku bez DPH (zbozi, montaz, doprava); bez nich se pocita z celku."""
    rate = Decimal(str(documents.VAT_RATE))
    rows = [Decimal(str(x)) for x in radky] if radky else [Decimal(str(net))]
    amount = sum((_q(r * rate / 100) for r in rows), Decimal(0))
    exact = _q(sum(rows, Decimal(0)) + amount)
    return {"rate": int(rate), "amount": float(amount), "total_with_vat": float(exact), "total_with_vat_rounded": int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))}


@app.post("/api/shop/stul/quote")
@_guard
def stul_host_quote():
    if _rate_limited(f"stul_quote:{_client_ip()}", *QUOTE_LIMIT_PER_IP):
        return _json({"error": "rate_limited"}, 429)
    body = _body()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            items = _items(cur, body.get("items"))
            calc = _spocti(cur, items, strict=False)
            top = _toptrans(cur, _plain(_str_only(body.get("delivery_zip")), 12), calc)
    finally:
        conn.close()
    net = calc["goods"] + calc["montaz"]
    rate = Decimal(str(documents.VAT_RATE))
    for ln in calc["lines"]:                                    # ceny S DPH u kazdeho radku (spotrebitel), stejne zaokrouhleni jako doklad (DPH z radku na halere)
        if ln.get("_unit") is not None:
            ln["unit_price_with_vat_czk"] = float(_q(ln["_unit"] + _q(ln["_unit"] * rate / 100)))
            ln["line_total_with_vat_czk"] = float(_q(Decimal(str(ln["line_total_czk"])) + _q(Decimal(str(ln["line_total_czk"])) * rate / 100)))
            if ln["_mont"] is not None:
                ln["montaz_czk_with_vat"] = float(_q(ln["_mont"] + _q(ln["_mont"] * rate / 100)))
                ln["montaz_total_with_vat_czk"] = float(_q(Decimal(str(ln["montaz_total_czk"])) + _q(Decimal(str(ln["montaz_total_czk"])) * rate / 100)))
    radky = [ln["line_total_czk"] for ln in calc["lines"] if ln.get("_unit") is not None] + [ln["montaz_total_czk"] for ln in calc["lines"] if ln.get("_mont") is not None]
    return _json({"currency": "CZK", "prices_include_vat": False, "valid": all(ln["configuration"]["valid"] for ln in calc["lines"]), "lines": _public_lines(calc["lines"]),
                  "subtotal_goods_czk": float(calc["goods"]), "subtotal_montaz_czk": float(calc["montaz"]), "subtotal_czk": float(net), "vat": _vat(net, radky),
                  "shipping_options": _shipping_options(top), "notes": ["vat_excluded", "shipping_to_be_confirmed", "proforma_after_shipping_confirmation"]})


def _clean(body):
    name = _plain(_str_only(body.get("name")), 120)
    email = _str_only(body.get("email")).strip().lower()
    phone = re.sub(r"[^0-9+()./ \-]", "", _plain(_str_only(body.get("phone")), 40)).strip()
    company = _plain(_str_only(body.get("company")), 160)
    note = _plain(_str_only(body.get("note")), MAX_NOTE, multiline=True)
    if not name:
        raise ShopError(400, "name_required", "name")
    if len(email) > 254 or not _EMAIL_RE.match(email) or ".." in email:
        raise ShopError(400, "email_invalid", "email")
    if not _PHONE_RE.match(phone):
        raise ShopError(400, "phone_invalid", "phone")
    if not isinstance(body.get("delivery"), dict):
        raise ShopError(400, "delivery_required", "delivery")
    delivery = _address(body.get("delivery"), "delivery")
    bl = body.get("billing")
    billing = delivery if (bl is None or (isinstance(bl, dict) and bl.get("same") is True)) else _address(bl, "billing")
    for k, a in (("delivery", delivery), ("billing", billing)):
        if len(re.sub(r"\D", "", a["zip"])) != 5:
            raise ShopError(400, "zip_invalid", f"{k}.zip")
    # Firma, IČO i DIČ jsou NEPOVINNÉ (objednává i spotřebitel, Robert 2026-10-04: "pro nás v tom není rozdíl"); jsou-li zadané, validují se jako dosud (IČO 6-8 číslic, DIČ CZ).
    ico = dic = None
    raw_ico, raw_dic = _str_only(body.get("company_id")), _str_only(body.get("vat_id"))
    if raw_ico.strip():
        ico, dic = _company_ids(raw_ico, raw_dic, "CZ")
    elif raw_dic.strip():                                                  # DIČ bez IČO: jen syntaxe CZ DIČ
        dic = _norm_id(raw_dic)
        if not _VAT_RE["CZ"].match(dic):
            raise ShopError(400, "vat_id_invalid", "vat_id")
    if body.get("shipping") not in SHIPPING:
        raise ShopError(400, "shipping_invalid", "shipping")
    if body.get("payment") != "transfer":
        raise ShopError(400, "payment_invalid", "payment")
    if body.get("consent") is not True:
        raise ShopError(400, "consent_required", "consent")
    expected = body.get("expected_total_net")
    if expected is not None and (isinstance(expected, bool) or not isinstance(expected, (int, float)) or expected < 0 or expected > 10 ** 9):
        raise ShopError(400, "expected_total_invalid", "expected_total_net")
    return {"name": name, "email": email, "phone": phone, "company": company, "ico": ico, "dic": dic, "delivery": delivery, "billing": billing, "note": note, "shipping": body["shipping"], "expected": expected}


def _radky_objednavky(calc, ship_czk):
    """Ceny radku bez DPH, jak jdou na zalohovou fakturu (konfigurace, montaz, doprava) - zaklad pro DPH po radcich."""
    r = [ln["line_total_czk"] for ln in calc["lines"]] + [ln["montaz_total_czk"] for ln in calc["lines"] if ln.get("_mont") is not None]
    return r + ([float(ship_czk)] if ship_czk else [])


def _line_addr(a):
    return f"{a['street']}, {a['zip']} {a['city']}, Česká republika"


@app.post("/api/shop/stul/order")
@_guard
def stul_host_order():
    if _rate_limited(f"stul_order:{_client_ip()}", *ORDER_LIMIT_PER_IP):
        return _json({"error": "rate_limited"}, 429)
    body = _body()
    if body.get("website"):                                          # honeypot
        return _json({"reference": "", "status": "received", "payment": None}, 201)
    conn = get_conn()
    lock_name = None
    try:
        with conn.cursor() as cur:
            o = _clean(body)
            items = _items(cur, body.get("items"))
            calc = _spocti(cur, items, strict=True)
            net = calc["goods"] + calc["montaz"]
            if net > MAX_ORDER_CZK:
                raise ObjChyba(422, "order_too_large")
            if o["expected"] is not None and abs(Decimal(str(o["expected"])) - net) > Decimal("0.005"):
                raise ObjChyba(409, "price_changed", None, {"current_total_net": float(net)})
            ship = o["shipping"]
            top = _toptrans(cur, o["delivery"]["zip"], calc) if ship == "toptrans" else {"net": None, "reason": None}
            ship_czk = _q(0 if ship == "pickup" else (top["net"] or 0))
            host = (request.host or "").split(":")[0].strip().lower()[:255]
            fp = hashlib.sha1(json.dumps({"host": host, "email": o["email"], "name": o["name"], "phone": o["phone"], "company": o["company"], "ico": o["ico"], "dic": o["dic"], "delivery": o["delivery"],
                                          "billing": o["billing"], "ship": ship, "note": o["note"],
                                          "lines": sorted([ln["configuration"]["hash"], ln["qty"], ln["montaz_zvolena"]] for ln in calc["lines"])}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:20]
            lock_name = f"stulo:{fp}"
            cur.execute("SELECT GET_LOCK(%s, 5) AS l", (lock_name,))
            if not cur.fetchone()["l"]:
                lock_name = None
                raise ObjChyba(409, "order_in_progress")
            cur.execute("SELECT * FROM shop_orders WHERE order_host=%s AND admin_note LIKE %s AND created_at > NOW() - INTERVAL 5 MINUTE ORDER BY id DESC LIMIT 1", (host, f"%[ORDER-FP {fp}]%"))
            dup = cur.fetchone()
            if dup:
                payload = {"reference": dup["order_number"], "status": "received", "total": {"net": float(net + ship_czk), "currency": "CZK", **_vat(net + ship_czk, _radky_objednavky(calc, ship_czk))}, "shipping": {"id": ship, "net": float(ship_czk) if ship != "quote" else None,
                           "review": True}, "payment": None, "next": "proforma_after_shipping_confirmation", "idempotent_replay": True}
                conn.rollback()
                return _json(payload, 200)
            cur.execute("SELECT COUNT(*) AS n FROM shop_orders WHERE order_host=%s AND customer_email=%s AND created_at > NOW() - INTERVAL 1 DAY", (host, o["email"]))
            if cur.fetchone()["n"] >= ORDER_LIMIT_PER_EMAIL_DAY:
                raise ObjChyba(429, "too_many_orders")
            core = {"items": [{"product_id": ln["product_id"], "qty": ln["qty"], "configuration": ln["_requested"], "montaz_zvolena": False} for ln in calc["lines"]],
                    "customer_name": o["name"], "customer_email": o["email"], "customer_phone": o["phone"],
                    "billing_name": o["company"] or o["name"], "billing_ico": o["ico"], "billing_dic": o["dic"], "billing_address": _line_addr(o["billing"]), "delivery_address": _line_addr(o["delivery"]),
                    "billing_zip": re.sub(r"\D", "", o["billing"]["zip"]), "delivery_zip": re.sub(r"\D", "", o["delivery"]["zip"]), "note": o["note"] or None}
            try:
                result = orders_mod._resolve_and_insert_order(cur, core, attribute_user_id=None, profile_user_id=None, require_active=True)
            except orders_mod._OrderCreateError as e:
                conn.rollback()
                raise ObjChyba(e.status_code if e.status_code in (400, 409, 422) else 422, "order_rejected", None, {"message": e.message})
            if abs(Decimal(str(result["total"])) - calc["goods"]) > Decimal("0.005"):
                conn.rollback()
                app.logger.error("stul host objednavka: nesoulad kalkulace %s a objednavky %s", calc["goods"], result["total"])
                raise ObjChyba(500, "price_mismatch")
            for ln in calc["lines"]:                                  # montaz = SAMOSTATNY radek (product_id NULL, DPH 21 % jako zbozi)
                if ln["_mont"] is not None:
                    cur.execute("INSERT INTO shop_order_items (order_id, product_id, product_name_snapshot, unit_price_czk, qty, line_total_czk) VALUES (%s,NULL,%s,%s,%s,%s)",
                                (result["order_id"], f"Montáž – {ln['configuration']['kod']}", ln["_mont"], ln["qty"], _q(ln["_mont"] * ln["qty"])))
                    if cur.rowcount != 1:
                        conn.rollback()
                        raise ObjChyba(500, "order_update_failed")
            total = _q(calc["goods"] + calc["montaz"] + ship_czk)
            ship_name = ADMIN_SHIPPING[ship] + (" – cena ke schválení" if ship == "toptrans" and not top["net"] else "")
            kontrola = {"weight_incomplete": "doprava Toptrans: u konfigurace chybí hmotnosti dílů, cenu zadá zaměstnanec", "zip_missing": "doprava Toptrans: chybí PSČ",
                        "price_unavailable": "doprava Toptrans: ceník ji nespočítal"}.get(top["reason"]) if ship == "toptrans" else None
            admin_note = (f"Objednávka HOSTA bez účtu z {host} (hlavní e-shop). Zboží {calc['goods']} Kč" + (f", montáž {calc['montaz']} Kč" if calc["montaz"] else "") + f" bez DPH, DPH CZ {documents.VAT_RATE} %. "
                          f"Doprava: {ADMIN_SHIPPING[ship]}" + (f", odhad {ship_czk} Kč" if ship_czk else "") + ". Zálohovou fakturu vystaví zaměstnanec po schválení dopravy (nic se nevystavuje ani neposílá automaticky)."
                          + (" Zákazník: " + ("podnikatel" if o["ico"] else "spotřebitel/bez IČO") + (f" {_safe_note(o['company'])}" if o["company"] else "") + (f", IČO {o['ico']}" if o["ico"] else "") + (f", DIČ {o['dic']}" if o["dic"] else "") + "."
                             ) + " Potvrzeny obchodni podminky a seznameni se zasadami ochrany udaju (zatrzitko pri odeslani)." + (f" {kontrola}." if kontrola else "") + f" [ORDER-FP {fp}]")
            cur.execute("UPDATE shop_orders SET shipping_method_name=%s, shipping_price_czk=%s, payment_method_name='Platba předem', total_czk=%s, order_host=%s, order_lang='cs', admin_note=%s, "
                        "shipping_review=1, vat_mode='standard', vat_check='none' WHERE id=%s", (ship_name, ship_czk, total, host, admin_note, result["order_id"]))
            cur.execute("INSERT INTO shop_order_status_history (order_id, status, changed_by, note) VALUES (%s,'nova',NULL,%s)",
                        (result["order_id"], f"Objednávka hosta přijata z {host}; čeká na schválení dopravy a zálohovou fakturu."))
            cur.execute("SELECT * FROM shop_orders WHERE id=%s", (result["order_id"],))
            row = cur.fetchone()
        conn.commit()
    finally:
        if lock_name:
            try:
                with conn.cursor() as cur_l:
                    cur_l.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
            except Exception:
                app.logger.exception("stul host objednavka: uvolneni zamku selhalo")
        conn.close()
    try:
        log_audit(None, "stul_host_order", "shop_order", result["order_id"], {"host": host, "net_czk": str(net), "ip": _client_ip()})
    except Exception:
        app.logger.exception("stul host objednavka: audit %s selhal", result.get("order_number"))
    return _json({"reference": row["order_number"], "status": "received", "total": {"net": float(net + ship_czk), "currency": "CZK", **_vat(net + ship_czk, _radky_objednavky(calc, ship_czk))},
                  "shipping": {"id": ship, "net": float(ship_czk) if ship != "quote" else None, "review": True}, "payment": None, "next": "proforma_after_shipping_confirmation", "idempotent_replay": False}, 201)
