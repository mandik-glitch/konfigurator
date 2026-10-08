"""Mini-shop: schvaleni a uprava dopravy objednavky zamestnancem + vystaveni zalohove faktury (krok 2; bot5, 2026-10-03; zadani Robert pres bot3: hodnotu dopravneho musime kontrolovat,
s moznosti upravit a schvalit, teprve potom se vystavi proforma a zakaznik ji dostane).

  POST /api/admin/orders/<id>/shipping   {shipping_price_czk (Kc bez DPH, >= 0), approve: true|false, vat_ok?: true, note?}   RBAC objednavky/upravit (+ doklady/vytvorit pri approve)

V hlavnim systemu schvaleni dopravy NEEXISTUJE (cena dopravy se jen spocita pri vzniku objednavky); tohle je nova vec jen pro objednavky z mini-shopu (order_host NOT NULL, shipping_review = 1).
  * approve false: ulozi cenu dopravy a prepocte total_czk (zbozi + doprava + platba), objednavka zustava ke schvaleni;
  * approve true: totez + VYSTAVI zalohovou fakturu stejnou funkci jako automat hlavniho e-shopu (documents.create_proforma_invoice, jedna per objednavka), shipping_review = 0, a e-mail s fakturou
    jde do SCHVALOVACI FRONTY (documents._auto_email_after_issue, pravidlo 16 - nic se neposila primo).
  * IC DPH, ktere VIES nepotvrdilo (vat_check 'vies_unavailable'), zamestnanec musi vedome potvrdit (vat_ok true); 
  * rezim DPH 0 % (reverse_charge): doklady umi sazbu 0 % s dolozkou az od kroku 3 (documents.PODPORA_PRENESENE_DPH), do te doby je schvaleni odmitnuto (409 vat_regime_not_supported) - zadna spatna faktura.
Idempotence: schvalena objednavka (shipping_review 0) se nikdy nevystavi podruhe (409 shipping_not_in_review).
"""
import json
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation as ArithmeticException_

from flask import request, jsonify

from app import app, get_conn, log_audit, current_user, require_permission
import documents

SUFFIX_KE_SCHVALENI = " – cena ke schválení"
MAX_SHIPPING_CZK = 1000000


_SNAPSHOT_RE = re.compile(r"\[EUR-SNAPSHOT (\{[^\]]*\})\]")


def _document_note(order):
    """Text o prepoctu meny na zalohovou fakturu: cena zbozi v EUR x kurz objednavky = castka v Kc (snimek z admin_note; kdyz chybi, nic se nepise)."""
    found = _SNAPSHOT_RE.findall(order.get("admin_note") or "")             # systemovy snimek je POSLEDNI znacka (zakaznicky text nesmi podvrhnout prvni; externi revize 2026-10-03, #5)
    if not found:
        return None
    try:
        snap = json.loads(found[-1])
        goods, rate = int(snap["goods_eur"]), Decimal(str(snap["rate"]))
        montaz = int(snap.get("montaz_eur") or 0)
        if goods < 0 or rate <= 0:
            return None
    except (ValueError, KeyError, TypeError, ArithmeticException_):
        return None
    kc = ((Decimal(goods) + montaz) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cena = f"Cena zboží {goods} EUR" + (f" a montáže {montaz} EUR" if montaz else "")
    return f"{cena} bez DPH × kurz {format(rate.normalize(), 'f')} Kč/EUR = {kc} Kč bez DPH; částka k úhradě je v Kč."


def _price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        d = Decimal(str(value))
    except Exception:
        return None
    if not d.is_finite() or d < 0 or d > MAX_SHIPPING_CZK:
        return None
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _err(status, code, message):
    return jsonify({"error": code, "message": message}), status


@app.post("/api/admin/orders/<int:order_id>/shipping")
@require_permission("objednavky", "upravit")
def admin_miniweb_order_shipping(order_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _err(400, "invalid_request", "Tělo musí být JSON objekt.")
    price = _price(body.get("shipping_price_czk"))
    if price is None:
        return _err(400, "shipping_price_invalid", "Cena dopravy: nezáporné číslo v Kč bez DPH.")
    approve = body.get("approve") is True
    if body.get("approve") not in (True, False, None):
        return _err(400, "invalid_request", "approve: true nebo false.")
    admin = current_user()
    if approve and not documents_permission(admin):
        return _err(403, "forbidden", "Vystavení zálohové faktury vyžaduje oprávnění k dokladům.")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            if not order:
                conn.rollback()
                return _err(404, "not_found", "Objednávka neexistuje.")
            if not order.get("shipping_review"):               # od 2026-10-04 i objednavky hlavniho e-shopu (konfigurace stolu s neuplnou hmotnosti, hostovska objednavka stolu)
                conn.rollback()
                return _err(409, "shipping_not_in_review", "Doprava u této objednávky už je schválená (nebo nebyla ke schválení).")
            if approve:
                if order.get("vat_mode") == "reverse_charge" and not getattr(documents, "PODPORA_PRENESENE_DPH", False):
                    conn.rollback()
                    return _err(409, "vat_regime_not_supported", "Doklady zatím neumí DPH 0 % s doložkou, zálohovou fakturu u této objednávky nelze vystavit automaticky.")
                if order.get("vat_check") == "vies_unavailable" and body.get("vat_ok") is not True:
                    conn.rollback()
                    return _err(409, "vat_check_required", "IČ DPH nebylo ověřeno ve VIES. Potvrďte kontrolu (vat_ok: true).")
                cur.execute("SELECT id FROM shop_documents WHERE order_id=%s AND document_type='proforma_invoice'", (order_id,))
                if cur.fetchone():
                    conn.rollback()
                    return _err(409, "proforma_exists", "Zálohová faktura k této objednávce už existuje.")
            cur.execute("SELECT COALESCE(SUM(line_total_czk),0) AS s FROM shop_order_items WHERE order_id=%s", (order_id,))
            goods = Decimal(str(cur.fetchone()["s"]))
            total = (goods + price + Decimal(str(order.get("payment_price_czk") or 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            name = (order.get("shipping_method_name") or "Doprava")
            if name.endswith(SUFFIX_KE_SCHVALENI):
                name = name[: -len(SUFFIX_KE_SCHVALENI)]
            cur.execute("UPDATE shop_orders SET shipping_price_czk=%s, shipping_method_name=%s, total_czk=%s WHERE id=%s", (price, name, total, order_id))      # radek je zamceny (FOR UPDATE); rowcount 0 = stejne hodnoty, ne chyba
            old = Decimal(str(order.get("shipping_price_czk") or 0))
            note = (str(body.get("note") or "").strip())[:300]
            hist = f"Doprava {'schválena' if approve else 'upravena'} zaměstnancem: {price} Kč bez DPH (původně {old} Kč)" + (f". {note}" if note else ".")
            cur.execute("INSERT INTO shop_order_status_history (order_id, status, changed_by, note) VALUES (%s,%s,%s,%s)", (order_id, order["status"], admin["id"], hist))
            result = None
            if approve:
                cur.execute("SELECT * FROM shop_orders WHERE id=%s", (order_id,))
                fresh = cur.fetchone()
                fresh["document_note"] = _document_note(fresh)
                items = documents._fetch_order_items(cur, order_id)
                result = documents.create_proforma_invoice(cur, fresh, items, documents._issued_by_label(admin))
                cur.execute("UPDATE shop_orders SET shipping_review=0, is_urgent=0 WHERE id=%s", (order_id,))
        conn.commit()
    finally:
        conn.close()
    try:
        log_audit(admin["id"], "miniweb_shipping_approve" if approve else "miniweb_shipping_edit", "shop_order", order_id,
                  {"shipping_price_czk": str(price), "total_czk": str(total), "proforma": result["document_number"] if result else None})
    except Exception:
        app.logger.exception("miniweb: audit schvaleni dopravy %s selhal", order_id)
    if result:
        try:
            documents._auto_email_after_issue(order_id, result["id"])     # e-mail s fakturou do SCHVALOVACI FRONTY (pravidlo 16)
        except Exception:
            app.logger.exception("miniweb: zarazeni e-mailu s fakturou objednavky %s selhalo", order_id)
    return jsonify({"status": "ok", "approved": approve, "shipping_price_czk": float(price), "total_czk": float(total),
                    "proforma": ({"id": result["id"], "document_number": result["document_number"], "amount_due_czk": result["amount_due_czk"]} if result else None)})


def documents_permission(admin):
    """Vystaveni faktury vyzaduje oprávnění doklady/vytvorit (stejně jako ruční vystavení v Dokladech); admin ho má vždy."""
    try:
        from app import has_permission
        return bool(has_permission(admin, "doklady", "vytvorit"))
    except Exception:
        return (admin or {}).get("role") == "admin"
