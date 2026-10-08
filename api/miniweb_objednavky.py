"""Mini-shop: kosik a objednavka konfigurovatelneho stolu (faze 3 pro SK; bot5, 2026-10-03; zadani Robert pres bot3: "funkcni kosik a tlacitko Do kosiku jako v hlavnim e-shopu").

  POST /api/miniweb/quote    cenova kalkulace (cista cetba, nic se nezapisuje): {country, items:[{product_id, qty, configuration:{selection, rules_version}}]}
                              -> {currency "EUR", prices_include_vat false, lines, subtotal, shipping_options, vat, notes}
  POST /api/miniweb/orders   objednavka HOSTA (bez uctu, firma + ICO povinne, DIC volitelne): vznika bezna objednavka v shop_orders pod storefrontem shopu, vlastni (bez dealera)

Pravidla (nemenit bez Roberta):
  * KOSIK drzi prohlizec (volby, zadna cena), server cenu VZDY pocita znovu: vyber konfigurace se overi (konfigurace_kosik.vyres = konfigurator stolu), cena v Kc bez DPH se prevede na EUR
    (miniweb_cena: kurz z radku shopu nebo zivy Fio, marze z radku shopu; bez nich cena neni = 503 price_unavailable, nikdy odhad), celé EUR na kus, radek = kus x pocet. Klientova cena se nebere.
  * Objednavka je v Kc (shop_orders.total_czk = soucet cen konfigurace v Kc bez DPH, bez dopravy a platby); EUR cena pro zakaznika je ve snimku v admin_note (kurz, marze, zaokrouhleni).
  * ZADNA AUTOMATICKA PROFORMA, ZADNY E-MAIL (pravidlo 16; bot3 2026-10-03: EUR ucet a rezim DPH pro SK firmy nejsou k dispozici, nic se nehada a nevystavuje samo): objednavka se zalozi bez
    platebni metody (jadro tedy nevystavi zalohovou fakturu), zamestnanec ji vidi jako novou objednavku, doplni dopravu (Toptrans pro SK nejde: chybi hmotnosti dilu) a proformu vystavi rucne.
  * Doprava: "quote" (po dohode, cenu upresnime) nebo "pickup" (osobni odber); platba "transfer" (platba predem po vystaveni proformy).
  * Jen konfigurovatelny stul (jiny produkt = 422 product_not_available), jen shop ve stavu live s zapnutymi objednavkami (miniweb_shops.orders_enabled), jinak 404 - mini-shop zustava
    bez teto vetve beze zmeny. Ceny zakaznik nikdy nevidi z kusovniku (zakaznicky snimek konfigurace, viz konfigurace_kosik.zakaznicky_snimek).
  * Ochrany: rate limity (IP, e-mail za den), honeypot, strop mnozstvi a hodnoty, idempotentni opakovani (stejny zakaznik a obsah do 5 minut vrati puvodni objednavku), cena v objednavce se
    pred zapisem porovna s kalkulaci (rozdil = rollback + chyba), validace firmy a IC jako u poptavky (miniweb._company_ids).
"""
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP

from flask import request

from app import app, get_conn, log_audit, _client_ip, _rate_limited
import documents
import jazyky
import konfigurace_kosik as kk
import miniweb
import miniweb_cena
import miniweb_vies
import orders as orders_mod
from miniweb import ShopError, _respond, _plain, _str_only, _EMAIL_RE, _COUNTRY_RE, _company_ids

QUOTE_LIMIT_PER_IP = (60, 60)
ORDER_LIMIT_PER_IP = (5, 600)
ORDER_LIMIT_PER_EMAIL_DAY = 5
MAX_BODY = 65536
MAX_LINES = 10
MAX_QTY = kk.MAX_MNOZSTVI
MAX_ORDER_EUR = 100000
MAX_NOTE = 1000
SHIPPING = ("toptrans", "quote", "pickup")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()/.-]{5,29}\Z")
_ZIP_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z -]{1,10}\Z")
COUNTRY_NAMES = {"SK": "Slovensko", "CZ": "Česká republika"}
LABELS = {"sk": {"toptrans": "Doprava Toptrans", "quote": "Doprava po dohode (cenu upresnime)", "pickup": "Osobny odber"},
          "en": {"toptrans": "Toptrans delivery", "quote": "Delivery by agreement (we will confirm the price)", "pickup": "Personal pickup"},
          "cs": {"toptrans": "Doprava Toptrans", "quote": "Doprava po dohodě (cenu upřesníme)", "pickup": "Osobní odběr"}}
jazyky.pripoj_objednavky(LABELS)                              # dalsi jazyky (de, hu ...) z api/jazyky/<jazyk>.json; cs / en / sk beze zmeny
ADMIN_SHIPPING = {"toptrans": "Doprava Toptrans", "quote": "Doprava na Slovensko – po dohodě (cenu upřesníme)", "pickup": "Osobní odběr"}


class ObjChyba(Exception):
    def __init__(self, status, code, field=None, extra=None):
        super().__init__(code)
        self.status, self.code, self.field, self.extra = status, code, field, extra or {}


def _guard(fn):
    def wrapped(*a, **k):
        try:
            return fn(*a, **k)
        except ObjChyba as e:
            return _respond({"error": e.code, **({"field": e.field} if e.field else {}), **e.extra}, None, e.status)
        except ShopError as e:
            return _respond({"error": e.code, **({"field": e.field} if e.field else {})}, None, e.status)
        except Exception:
            app.logger.exception("miniweb objednavky: neocekavana chyba v %s", fn.__name__)
            return _respond({"error": "internal_error"}, None, 500)
    wrapped.__name__ = fn.__name__
    return wrapped


def _body():
    if request.mimetype != "application/json":
        raise ShopError(400, "invalid_json")
    if (request.content_length or 0) > MAX_BODY:
        raise ObjChyba(413, "payload_too_large")
    raw = request.stream.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ObjChyba(413, "payload_too_large")
    try:
        body = json.loads(raw.decode("utf-8")) if raw else None
    except (ValueError, RecursionError):
        body = None
    if not isinstance(body, dict):
        raise ShopError(400, "invalid_json")
    return body


def _countries(shop):
    return [c for c in (x.strip().upper() for x in (shop["countries"] or "").split(",")) if _COUNTRY_RE.match(c)]


def _country(body, shop):
    country = miniweb._country_in(body.get("country"))
    countries = _countries(shop)
    if country is None and len(countries) == 1:
        country = countries[0]
    if country is None:
        raise ShopError(400, "country_required", "country")
    if not _COUNTRY_RE.match(country) or (countries and country not in countries):
        raise ShopError(400, "country_invalid", "country")
    return country


def _shop(cur):
    """Kontext shopu a nastaveni ceny: shop musi byt dostupny (live, nebo nahled pro staff), mit zapnute objednavky a cenu (marze + kurz)."""
    ctx = miniweb._shop_context(cur)
    shop = ctx["shop"]
    if not shop.get("orders_enabled"):
        raise ShopError(404, "orders_disabled")
    cfg = miniweb_cena.nastaveni(shop)
    if cfg is None:
        raise ObjChyba(503, "price_unavailable")
    return ctx, cfg


def _items(raw, products_by_id):
    """Polozky z prohlizece: jen product_id (id produktu mini-shopu jako u poptavky), qty a configuration. Cokoli jineho (cena, nazev, kod) se ignoruje."""
    if not isinstance(raw, list) or not raw or len(raw) > MAX_LINES:
        raise ShopError(400, "items_invalid", "items")
    out = []
    for i, it in enumerate(raw):
        if not isinstance(it, dict):
            raise ShopError(400, "items_invalid", f"items[{i}]")
        pid, qty = miniweb._as_int(it.get("product_id")), miniweb._as_int(it.get("qty", 1))
        if qty is None or not 1 <= qty <= MAX_QTY:
            raise ShopError(400, "items_invalid", f"items[{i}].qty")
        p = products_by_id.get(pid)
        cfgp = (p or {}).get("configurator") or {}
        if p is None or not cfgp.get("available") or not cfgp.get("product_id"):
            raise ObjChyba(422, "product_not_available", f"items[{i}]")
        conf = it.get("configuration")
        if not isinstance(conf, dict) or not isinstance(conf.get("selection"), dict) or miniweb._too_deep(conf):
            raise ShopError(400, "configuration_required", f"items[{i}].configuration")
        rv = conf.get("rules_version")
        out.append({"mw_id": pid, "shop_product_id": int(cfgp["product_id"]), "name": p["name"], "qty": qty, "selection": conf["selection"],
                    "rules_version": rv if isinstance(rv, str) and len(rv) <= 64 else None, "montaz": it.get("montaz") is True})
    return out


def _spocti(cur, items, cfg, lang, strict):
    """JEDINY vypocet zbozi pro quote i objednavku. -> dict {lines, goods (EUR zbozi), montaz (EUR montaz), subtotal (EUR zbozi + montaz), total_czk (katalogove Kc), settle (Decimal Kc k uhrade = EUR x kurz), kg, weight_complete}.
    strict=True (objednavka): neplatna konfigurace = chyba; strict=False (quote): radek s valid false (do souctu se nepocita)."""
    merged = {}
    lines = []
    for it in items:
        try:
            res = kk.vyres(cur, it["shop_product_id"], it["selection"], "cs", it["rules_version"])
        except kk.KonfiguraceChyba as e:
            if e.code == "invalid_configuration" and not strict:
                lines.append({"product_id": it["mw_id"], "name": it["name"], "qty": it["qty"], "net_unit": None, "net_total": None, "montaz_zvolena": False, "montaz_option_eur": None,
                              "montaz_eur": None, "montaz_total_eur": None, "configuration": {"valid": False, "changed": False, "kod": None, "summary": [], "errors": e.errors or []}})
                continue
            extra = {"errors": e.errors} if e.errors else {}
            code = "product_not_available" if e.code == "not_configurable" else e.code
            raise ObjChyba(e.status, code, None, extra)
        key = (it["mw_id"], res["hash"], it["montaz"])
        if key in merged:
            merged[key]["qty"] += it["qty"]
            if merged[key]["qty"] > MAX_QTY:
                raise ShopError(400, "items_invalid", "items")
            continue
        unit_eur = miniweb_cena.cena_eur(res["net_czk"], cfg)
        if unit_eur is None or unit_eur <= 0:
            raise ObjChyba(503, "price_unavailable")
        # MONTAZ (Robert 2026-10-04: vzdy volitelna, i v mini-shopech; pravidlo "do zahranici rozlozeny stul" pro mini-shopy padlo): % z ceny konfigurace v EUR (sazba app_settings stul_montaz_pct, zakaznik ji nevidi),
        # cele EUR; sazba 0/neplatna = montaz se nenabizi (montaz_option_eur null) a pozadavek na ni je 409 montaz_unavailable
        pct = res.get("montaz_pct")
        mont_opt = int((Decimal(unit_eur) * Decimal(str(pct)) / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)) if pct else None
        mont_opt = mont_opt if mont_opt and mont_opt > 0 else None
        if it["montaz"] and mont_opt is None:
            raise ObjChyba(409, "montaz_unavailable", "items")
        line = {"product_id": it["mw_id"], "name": it["name"], "qty": it["qty"], "net_unit": unit_eur, "net_total": None, "_czk": float(res["net_czk"]), "_shop_pid": it["shop_product_id"],
                "montaz_zvolena": it["montaz"], "montaz_option_eur": mont_opt, "montaz_eur": mont_opt if it["montaz"] else None, "montaz_total_eur": None,
                "_requested": {"selection": it["selection"], "rules_version": it["rules_version"]}, "_kg": float(res["weight_kg"] or 0.0), "_kg_ok": bool(res["weight_complete"]),
                "configuration": {"valid": True, "changed": res["selection"] != it["selection"], "kod": res["kod"], "hash": res["hash"], "selection": res["selection"],
                                  "rules_version": res["rules_version"], "summary": res["summary"], "errors": []}}
        merged[key] = line
        lines.append(line)
    subtotal, total_czk, settle, kg, kg_ok, goods, montaz = 0, 0.0, Decimal(0), 0.0, True, 0, 0
    for ln in lines:
        if ln["net_unit"] is not None:
            ln["net_total"] = ln["net_unit"] * ln["qty"]
            goods += ln["net_total"]
            subtotal += ln["net_total"]
            total_czk += round(ln["_czk"] * ln["qty"], 2)
            # K UHRADE V Kc (jediny ucet je cesky, Robert pres bot3 2026-10-03): cena v EUR x kurz objednavky; kurz a EUR castka jsou ve snimku objednavky a na proforme
            ln["_settle_unit"] = (Decimal(ln["net_unit"]) * cfg["rate"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            settle += ln["_settle_unit"] * ln["qty"]
            if ln["montaz_eur"]:                                                  # montaz = samostatny radek objednavky; cena k uhrade stejne EUR x kurz
                ln["montaz_total_eur"] = ln["montaz_eur"] * ln["qty"]
                montaz += ln["montaz_total_eur"]
                subtotal += ln["montaz_total_eur"]
                ln["_mont_settle_unit"] = (Decimal(ln["montaz_eur"]) * cfg["rate"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                settle += ln["_mont_settle_unit"] * ln["qty"]
            kg += ln["_kg"] * ln["qty"]
            kg_ok = kg_ok and ln["_kg_ok"]
    return {"lines": lines, "goods": goods, "montaz": montaz, "subtotal": subtotal, "total_czk": round(total_czk, 2), "settle": settle, "kg": kg, "weight_complete": kg_ok}


def _public_lines(lines):
    return [{k: v for k, v in ln.items() if not k.startswith("_")} for ln in lines]


def _toptrans(cur, cfg, delivery_zip, calc):
    """Odhad dopravy Toptrans (ceník podle PSC dodaci adresy a hmotnosti, stejna funkce jako e-shop: orders._resolve_toptrans_price) -> {net (EUR nebo None), reason, czk}.
    Bez uplne hmotnosti (dnes chybi hmotnosti dilu: laminodeska, suplíky, LED, panely, elektrozlab, drzak PET, kolecka) se cena NEPOCITA (poddimenzovala by dopravu); neznama PSC (slovenska)
    ceník mapuje na nejvyssi pasmo 700 km. Vzdy jen ODHAD, cenu pred zalohovou fakturou potvrzuje zamestnanec."""
    if not delivery_zip or len(re.sub(r"\D", "", delivery_zip)) != 5:
        return {"net": None, "reason": "zip_missing", "czk": None}
    if not calc["weight_complete"] or calc["kg"] <= 0:
        return {"net": None, "reason": "weight_incomplete", "czk": None}
    cur.execute("SELECT id FROM shop_shipping_methods WHERE active=1 AND pricing_mode='zip_weight' ORDER BY sort_order, id LIMIT 1")
    sm = cur.fetchone()
    if not sm:
        return {"net": None, "reason": "price_unavailable", "czk": None}
    try:
        czk, _band, _basis = orders_mod._resolve_toptrans_price(cur, sm["id"], delivery_zip, calc["kg"], 0.0)
    except orders_mod._OrderCreateError:
        return {"net": None, "reason": "price_unavailable", "czk": None}
    eur = miniweb_cena.cena_eur(czk, cfg)
    return {"net": eur, "reason": None, "czk": float(czk)} if eur is not None else {"net": None, "reason": "price_unavailable", "czk": None}


def _shipping_options(lang, toptrans):
    lab = LABELS.get(lang) or LABELS.get(lang.split("-")[0]) or LABELS["en"]
    return [{"id": "toptrans", "label": lab["toptrans"], "net": toptrans["net"], "estimated": True, **({"reason": toptrans["reason"]} if toptrans["reason"] else {})},
            {"id": "quote", "label": lab["quote"], "net": None}, {"id": "pickup", "label": lab["pickup"], "net": 0}]


def _dph(country, vat_id, fetch=None):
    """Rezim DPH (Robert pres bot3 2026-10-03): dodavame z CR. Zakaznik z JINEHO clenskeho statu s PLATNYM IC DPH (VIES) = DPH 0 % (osvobozeno / preneseni danove povinnosti, doloka na dokladu);
    bez platneho cisla (nebo z CR) se uctuje CZ sazba. VIES nedostupne = DPH 0 % jen pro FORMALNE platne cislo a objednavka se oznaci k RUCNI KONTROLE; nic se nepocita automaticky navic.
    -> {applied, rate, mode ('standard'|'reverse_charge'), reason, check ('none'|'vies_valid'|'vies_unavailable'|'vies_invalid'), manual_check}. Neplatne cislo (VIES) = check 'vies_invalid', sazba CZ."""
    rate = int(documents.VAT_RATE)
    if country == "CZ" or not vat_id:
        return {"applied": True, "rate": rate, "mode": "standard", "reason": "domestic" if country == "CZ" else "no_vat_id", "check": "none", "manual_check": False}
    stav = miniweb_vies.vies_stav(country, vat_id, fetch=fetch)
    if stav == "valid":
        return {"applied": False, "rate": 0, "mode": "reverse_charge", "reason": "valid_vat_id", "check": "vies_valid", "manual_check": False}
    if stav == "unavailable":
        return {"applied": False, "rate": 0, "mode": "reverse_charge", "reason": "valid_vat_id_unverified", "check": "vies_unavailable", "manual_check": True}
    return {"applied": True, "rate": rate, "mode": "standard", "reason": "vat_id_not_valid", "check": "vies_invalid", "manual_check": False}


def _vat_json(dph, net):
    amount = (Decimal(net) * dph["rate"] / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"applied": dph["applied"], "rate": dph["rate"], "mode": dph["mode"], "reason": dph["reason"], "amount": float(amount), "total_with_vat": float(Decimal(net) + amount),
            "manual_check": dph["manual_check"]}


def _vat_id_from(body, country):
    """Volitelne IC DPH z tela: syntaxe jako u poptavky (miniweb._company_ids), jinak ShopError vat_id_invalid."""
    if not _str_only(body.get("vat_id")):
        return None
    return miniweb._company_ids("1" * 8 if country in ("CZ", "SK") else "1111", _str_only(body.get("vat_id")), country)[1]


@app.post("/api/miniweb/quote")
@_guard
def miniweb_quote():
    if _rate_limited(f"miniweb_quote:{_client_ip()}", *QUOTE_LIMIT_PER_IP):
        return _respond({"error": "rate_limited"}, None, 429)
    body = _body()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx, cfg = _shop(cur)
            country = _country(body, ctx["shop"])
            products, _cats = miniweb._visible_products(cur, ctx)
            items = _items(body.get("items"), {p["id"]: p for p in products})
            calc = _spocti(cur, items, cfg, ctx["lang"], strict=False)
            vat_id = _vat_id_from(body, country)
            top = _toptrans(cur, cfg, _plain(body.get("delivery_zip"), 12), calc)
    finally:
        conn.close()
    dph = _dph(country, vat_id)
    valid = all(ln["configuration"]["valid"] for ln in calc["lines"])
    return _respond({"currency": "EUR", "prices_include_vat": False, "country": country, "valid": valid, "lines": _public_lines(calc["lines"]), "subtotal": calc["subtotal"],
                     "total_goods": calc["goods"], "subtotal_montaz": calc["montaz"], "shipping_options": _shipping_options(ctx["lang"], top), "vat": _vat_json(dph, calc["subtotal"]),
                     "notes": ["vat_excluded", "shipping_to_be_confirmed", "proforma_after_shipping_confirmation"]}, ctx)


@app.post("/api/miniweb/vat-check")
@_guard
def miniweb_vat_check():
    """Overeni IC DPH zakaznika (VIES) pro pokladnu: {country, vat_id} -> {valid: true|false|null, status, vat}. null = VIES nedostupne (objednavka pak pujde k rucni kontrole)."""
    if _rate_limited(f"miniweb_vat:{_client_ip()}", 20, 60):
        return _respond({"error": "rate_limited"}, None, 429)
    body = _body()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = miniweb._shop_context(cur)
            country = _country(body, ctx["shop"])
    finally:
        conn.close()
    if not _str_only(body.get("vat_id")):
        raise ShopError(400, "vat_id_required", "vat_id")
    vat_id = _vat_id_from(body, country)
    dph = _dph(country, vat_id)
    stav = {"vies_valid": "valid", "vies_unavailable": "unavailable", "vies_invalid": "invalid", "none": "none"}[dph["check"]]
    return _respond({"valid": True if stav == "valid" else (None if stav == "unavailable" else False), "status": stav, "vat": _vat_json(dph, 0)}, ctx)


def _address(raw, field):
    """Adresa {street, city, zip}: povinna pole, text bez znacek; PSC 2 az 11 znaku (SK 'ddd dd')."""
    if not isinstance(raw, dict):
        raise ShopError(400, "street_required", f"{field}.street")
    street, city, zip_ = _plain(_str_only(raw.get("street")), 160), _plain(_str_only(raw.get("city")), 100), _plain(_str_only(raw.get("zip")), 12)
    if not street:
        raise ShopError(400, "street_required", f"{field}.street")
    if not city:
        raise ShopError(400, "city_required", f"{field}.city")
    if not _ZIP_RE.match(zip_):
        raise ShopError(400, "zip_invalid", f"{field}.zip")
    return {"street": street, "city": city, "zip": zip_}


_SNAP_RE = re.compile(r"\[EUR-SNAPSHOT (\{[^\]]*\})\]")


def _safe_note(text):
    """Zakaznicky text do interni poznamky: hranate zavorky pryc, aby se nedal podvrhnout system znacky ([EUR-SNAPSHOT ...], [ORDER-FP ...]; externi revize 2026-10-03, #5)."""
    return str(text).replace("[", "(").replace("]", ")")


def _last_snapshot(admin_note):
    """Systemovy snimek ceny = POSLEDNI znacka v poznamce (pridava se na konec); nikdy prvni - jine casti poznamky mohou nest zakaznicky text."""
    found = _SNAP_RE.findall(admin_note or "")
    try:
        return json.loads(found[-1]) if found else {}
    except ValueError:
        return {}


def _clean_order_body(body):
    name = _plain(_str_only(body.get("name")), 120)                 # jen retezce (externi revize 2026-10-03, #16)
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
    if not company:
        raise ShopError(400, "company_required", "company")
    billing = _address(body.get("billing"), "billing")
    dl = body.get("delivery")
    if not isinstance(dl, dict):
        raise ShopError(400, "delivery_required", "delivery")
    delivery = billing if dl.get("same") is True else _address(dl, "delivery")
    if body.get("shipping") not in SHIPPING:
        raise ShopError(400, "shipping_invalid", "shipping")
    if body.get("payment") != "transfer":
        raise ShopError(400, "payment_invalid", "payment")
    if body.get("consent") is not True:
        raise ShopError(400, "consent_required", "consent")
    if body.get("b2b_confirm") is not True:
        raise ShopError(400, "b2b_confirm_required", "b2b_confirm")
    expected = body.get("expected_total_net")
    if expected is not None and (isinstance(expected, bool) or not isinstance(expected, int) or expected < 0 or expected > 10 ** 9):
        raise ShopError(400, "expected_total_invalid", "expected_total_net")
    return {"name": name, "email": email, "phone": phone, "company": company, "billing": billing, "delivery": delivery, "note": note, "shipping": body["shipping"], "expected": expected}


def _one_line(a, country_name):
    return f"{a['street']}, {a['zip']} {a['city']}, {country_name}"


def _order_payload(order, subtotal, ship_net, shipping, review, dph):
    net_all = subtotal + (ship_net or 0)
    vat = _vat_json(dph, net_all)
    return {"reference": order["order_number"], "status": "received", "total": {"net": net_all, "currency": "EUR", "with_vat": vat["total_with_vat"]}, "vat": vat,
            "shipping": {"id": shipping, "net": ship_net if shipping != "quote" else None, "review": bool(review)}, "shipping_review": bool(review), "payment": None,
            "next": "proforma_after_shipping_confirmation"}


@app.post("/api/miniweb/orders")
@_guard
def miniweb_order_create():
    if _rate_limited(f"miniweb_order:{_client_ip()}", *ORDER_LIMIT_PER_IP):
        return _respond({"error": "rate_limited"}, None, 429)
    body = _body()
    if body.get("website"):                                    # honeypot: tvarime se, ze se povedlo, nic neukladame
        return _respond({"reference": "", "status": "received", "payment": None}, None, 201)
    conn = get_conn()
    lock_name = None
    try:
        with conn.cursor() as cur:
            ctx, cfg = _shop(cur)
            shop = ctx["shop"]
            o = _clean_order_body(body)
            country = _country(body, shop)
            company_id, vat_id = _company_ids(_str_only(body.get("company_id")), _str_only(body.get("vat_id")), country)
            dph = _dph(country, vat_id)
            if dph["check"] == "vies_invalid":
                raise ObjChyba(422, "vat_id_not_valid", "vat_id")
            products, _cats = miniweb._visible_products(cur, ctx)
            items = _items(body.get("items"), {p["id"]: p for p in products})
            calc = _spocti(cur, items, cfg, ctx["lang"], strict=True)
            subtotal = calc["subtotal"]
            if subtotal > MAX_ORDER_EUR:
                raise ObjChyba(422, "order_too_large")
            if o["expected"] is not None and o["expected"] != subtotal:
                raise ObjChyba(409, "price_changed", None, {"current_total_net": subtotal})
            ship = o["shipping"]
            top = _toptrans(cur, cfg, o["delivery"]["zip"], calc) if ship == "toptrans" else {"net": None, "reason": None, "czk": None}
            ship_net = 0 if ship == "pickup" else top["net"]                                    # EUR; None = cena dopravy se urci pri schvaleni
            ship_settle = (Decimal(ship_net) * cfg["rate"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if ship_net else Decimal(0)
            review = True                                                                       # KAZDA objednavka z mini-shopu ceka na schvaleni zamestnancem (doprava; u osobniho odberu cena 0) pred zalohovou fakturou (externi revize 2026-10-03, #9)
            settle_total = float(calc["settle"] + ship_settle)
            if not ctx["live"]:                                # nahled pro staff: jen validace a kalkulace, nic se nezapisuje (zadna testovaci data v produkci)
                return _respond({"reference": "", "status": "received", "preview": True, "total": {"net": subtotal + (ship_net or 0), "currency": "EUR"}, "payment": None}, ctx, 201)
            sf_id = ctx["sf"]["id"]
            cur.execute("SELECT COUNT(*) AS n FROM shop_orders WHERE storefront_id=%s AND customer_email=%s AND created_at > NOW() - INTERVAL 1 DAY", (sf_id, o["email"]))
            vsechny = cur.fetchone()["n"]
            # Opakovani (dvojity klik, vypadek site): jen STEJNY OBSAH. Otisk = shop + zakaznik + firma + adresy + doprava + poznamka + vsechny konfigurace a mnozstvi (ne jen castka; externi revize
            # 2026-10-03, #1); soubezne stejne pozadavky serializuje pojmenovany zamek na otisku, takze druhy uz najde ulozenou objednavku.
            fp = hashlib.sha1(json.dumps({"sf": sf_id, "email": o["email"], "name": o["name"], "phone": o["phone"], "company": o["company"], "ico": company_id, "vat": vat_id, "country": country,
                                          "billing": o["billing"], "delivery": o["delivery"], "ship": ship, "note": o["note"],
                                          "lines": sorted([ln["configuration"]["hash"], ln["qty"], ln["montaz_zvolena"]] for ln in calc["lines"])}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:20]
            cur.execute("SELECT GET_LOCK(%s, 5) AS l", (f"mwo:{sf_id}:{fp}",))
            if not cur.fetchone()["l"]:
                raise ObjChyba(409, "order_in_progress")
            lock_name = f"mwo:{sf_id}:{fp}"
            cur.execute("SELECT * FROM shop_orders WHERE storefront_id=%s AND admin_note LIKE %s AND created_at > NOW() - INTERVAL 5 MINUTE ORDER BY id DESC LIMIT 1", (sf_id, f"%[ORDER-FP {fp}]%"))
            dup = cur.fetchone()
            if dup:                                            # puvodni objednavka s puvodnimi castkami ze snimku, nic noveho
                snap = _last_snapshot(dup.get("admin_note"))
                resp = _respond({**_order_payload(dup, int(snap.get("goods_eur", subtotal)) + int(snap.get("montaz_eur", 0)), snap.get("shipping_eur") if "shipping_eur" in snap else ship_net, ship, dup.get("shipping_review"), dph),
                                 "idempotent_replay": True}, ctx, 200)
                conn.rollback()
                return resp
            if vsechny >= ORDER_LIMIT_PER_EMAIL_DAY:
                raise ObjChyba(429, "too_many_orders")
            country_name = COUNTRY_NAMES.get(country, country)
            core = {"items": [{"product_id": ln["_shop_pid"], "qty": ln["qty"], "configuration": ln["_requested"]} for ln in calc["lines"]],
                    "customer_name": o["name"], "customer_email": o["email"], "customer_phone": o["phone"],
                    "billing_name": o["company"], "billing_ico": company_id, "billing_dic": vat_id,
                    "billing_address": _one_line(o["billing"], country_name), "delivery_address": _one_line(o["delivery"], country_name), "note": o["note"] or None}
            for klic, a in (("billing_zip", o["billing"]), ("delivery_zip", o["delivery"])):
                digits = re.sub(r"\D", "", a["zip"])
                if len(digits) == 5:                           # PSC jadro zna jen petimistne (SK, CZ); jinde se nepredava
                    core[klic] = digits
            try:
                result = orders_mod._resolve_and_insert_order(cur, core, attribute_user_id=None, profile_user_id=None, require_active=False)
            except orders_mod._OrderCreateError as e:
                conn.rollback()
                raise ObjChyba(e.status_code if e.status_code in (400, 409, 422) else 422, "order_rejected", None, {"message": e.message})
            if abs(float(result["total"]) - calc["total_czk"]) > 0.005:
                conn.rollback()
                app.logger.error("miniweb objednavky: nesoulad kalkulace %s a objednavky %s (shop %s)", calc["total_czk"], result["total"], sf_id)
                raise ObjChyba(500, "price_mismatch")
            for ln in calc["lines"]:                           # cena k uhrade v Kc = EUR x kurz (radky objednavky, ne katalogova Kc)
                cur.execute("UPDATE shop_order_items SET unit_price_czk=%s, line_total_czk=%s WHERE order_id=%s AND configuration_code=%s",
                            (ln["_settle_unit"], ln["_settle_unit"] * ln["qty"], result["order_id"], ln["configuration"]["kod"]))
                if cur.rowcount != 1:
                    conn.rollback()
                    raise ObjChyba(500, "order_update_failed")
                if ln.get("montaz_eur"):                       # montaz = SAMOSTATNY radek objednavky (product_id NULL, cena k uhrade EUR x kurz, DPH jako zbozi)
                    cur.execute("INSERT INTO shop_order_items (order_id, product_id, product_name_snapshot, unit_price_czk, qty, line_total_czk) VALUES (%s,NULL,%s,%s,%s,%s)",
                                (result["order_id"], f"Montáž – {ln['configuration']['kod']}", ln["_mont_settle_unit"], ln["qty"], ln["_mont_settle_unit"] * ln["qty"]))
                    if cur.rowcount != 1:
                        conn.rollback()
                        raise ObjChyba(500, "order_update_failed")
            ship_name = ADMIN_SHIPPING[ship] + (" – cena ke schválení" if ship_net is None and ship == "toptrans" else "")
            kontrola = []
            if dph["manual_check"]:
                kontrola.append("K RUČNÍ KONTROLE: VIES nebylo dostupné, IČ DPH není ověřeno (DPH 0 % jen podmíněně)")
            if ship == "toptrans" and top["reason"]:
                kontrola.append({"weight_incomplete": "doprava Toptrans: u konfigurace chybí hmotnosti dílů, cenu zadá zaměstnanec", "zip_missing": "doprava Toptrans: chybí PSČ",
                                 "price_unavailable": "doprava Toptrans: ceník ji nespočítal"}.get(top["reason"], "doprava Toptrans: ruční cena"))
            admin_note = (f"Mini-shop {ctx['host']} ({ctx['lang']}). Zboží pro zákazníka: {calc['goods']} EUR" + (f" + montáž {calc['montaz']} EUR" if calc["montaz"] else "") + f" bez DPH (kurz {cfg['rate']} Kč/EUR, marže {cfg['margin_pct']} %, celé EUR za kus); "
                          f"k úhradě v Kč = EUR × kurz = {calc['settle']} Kč bez DPH za zboží" + (" a montáž" if calc["montaz"] else "") + f". Doprava: {ADMIN_SHIPPING[ship]}"
                          + (f", odhad {ship_net} EUR ({ship_settle} Kč)" if ship_net else "") + f". DPH: {dph['mode']} {dph['rate']} % ({dph['reason']}, VIES {dph['check']}). "
                          f"Zálohovou fakturu vystaví zaměstnanec po schválení dopravy (nic se nevystavuje ani neposílá automaticky). Firma {_safe_note(o['company'])}, IČO {company_id}"
                          + (f", IČ DPH {vat_id}" if vat_id else "") + f", země {country}." + ("".join(" " + k + "." for k in kontrola))
                          + " [ORDER-FP " + fp + "] [EUR-SNAPSHOT " + json.dumps({"goods_eur": calc["goods"], "montaz_eur": calc["montaz"], "rate": str(cfg["rate"]), "margin_pct": str(cfg["margin_pct"]), "shipping_eur": ship_net}) + "]")
            cur.execute("UPDATE shop_orders SET storefront_id=%s, shipping_method_name=%s, shipping_price_czk=%s, payment_method_name='Platba předem', total_czk=%s, order_host=%s, order_lang=%s, admin_note=%s, "
                        "shipping_review=%s, vat_mode=%s, vat_check=%s, is_urgent=%s WHERE id=%s",
                        (sf_id, ship_name, ship_settle, settle_total, ctx["host"][:255], ctx["lang"][:10], admin_note, 1 if review else 0, dph["mode"], dph["check"], 1 if dph["manual_check"] else 0, result["order_id"]))
            if cur.rowcount != 1:
                conn.rollback()
                raise ObjChyba(500, "order_update_failed")
            cur.execute("INSERT INTO shop_order_status_history (order_id, status, changed_by, note) VALUES (%s,'nova',NULL,%s)",
                        (result["order_id"], f"Objednávka přijata z mini-shopu {ctx['host']} (firma {o['company']}); čeká na schválení dopravy a zálohovou fakturu."))
            cur.execute("SELECT * FROM shop_orders WHERE id=%s", (result["order_id"],))
            order_row = cur.fetchone()
            payload = _order_payload(order_row, subtotal, ship_net, ship, review, dph)
        conn.commit()
    finally:
        if lock_name:
            try:
                with conn.cursor() as cur_l:
                    cur_l.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
            except Exception:
                app.logger.exception("miniweb objednavky: uvolneni zamku selhalo")
        conn.close()
    try:
        log_audit(None, "miniweb_order", "shop_order", result["order_id"], {"host": ctx["host"], "total_eur": subtotal, "total_czk": settle_total, "ip": _client_ip()})
    except Exception:
        app.logger.exception("miniweb objednavky: audit objednavky %s selhal", result.get("order_number"))
    return _respond({**payload, "idempotent_replay": False}, ctx, 201)
