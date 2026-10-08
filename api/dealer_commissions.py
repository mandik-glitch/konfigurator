"""Dealersky program - provize, krok 2: CTENI (bot5, 2026-10-02; zadani Robert pres bot3, TASKS.md "ZADANO 2026-10-02 ... dealersky program").

Cesta 'our': zakaznik, ktery prisel z odkazu dealera, dokonci objednavku U NAS (shop_orders.dealer_id + order_path='our', viz dealers.attach_attribution).
Provize dealerovi = procento (dealer > kategorie produktu > nastaveni, dealers.dealer_commission_pct) z ceny polozek BEZ DPH a BEZ dopravy a platby (shop_order_items.
line_total_czk, v DB jsou ceny bez DPH; doprava a platba jsou ve vlastnich sloupcich shop_orders). Stav provize se PRO KAZDOU objednavku pocita z dat, ktera uz v DB jsou
(zaplaceni, expedice, storno, vratky), zadne hooky do orders.py/returns.py a zadne nove tabulky; vyuctovani (krok 3) pak bude brat jen to, co je zde 'k_vyplate'.

Stavy (priorita shora dolu):
  zrusena            - objednavka zrusena, nebo cela vracena (reason: order_cancelled | fully_returned), provize 0
  ceka_na_vraceni    - existuje otevrena reklamace/vraceni (pozadovano, posuzovano, schvaleno, prijato) - dokud neni vyrizena, provize se nevyplaci
  ceka_na_zaplaceni  - objednavka neni (cela) zaplacena (shop_orders.payment_received_at + payment_received_total_czk >= total_czk)
  ceka_na_expedici   - zaplaceno, zatim neexpedovano (lhuta na vraceni jeste nezacala)
  ceka_na_lhutu      - ceka se 14 dni (app_settings.dealer_commission_hold_days) od POZDEJSIHO z zaplaceni a expedice (hold_until), zakonna lhuta na odstoupeni bezi od prevzeti
  k_vyplate          - lhuta uplynula, bez vraceni a stornu: pripravena do mesicniho vyuctovani
Vraceni (shop_returns vyrizeno + resolution 'refund', polozky shop_return_items) kraci provizi PORADNE po polozkach (vracena cast ceny polozky krat sazba), cela vracena = zrusena.
Dealer vidi cislo objednavky, data, castky a stav, NIKDY osobni udaje zakaznika. Nic se tu nezapisuje, e-maily se neposilaji.
"""
import datetime

from flask import request

from app import app, get_conn, require_permission, current_user, login_required, get_setting
import dealers
from dealers import _json, _err, _ser, _setting_float, _now

HOLD_DAYS_DEFAULT = 14
OPEN_RETURN_STATUSES = ("pozadovano", "posuzovano", "schvaleno", "prijato")
COMMISSION_STATUSES = ("zrusena", "ceka_na_vraceni", "ceka_na_zaplaceni", "ceka_na_expedici", "ceka_na_lhutu", "k_vyplate")
PERMISSION_PROVIZE = "dealer_provize"
MAX_ORDERS_SCANNED = 5000


def hold_days(cur):
    return int(_setting_float(cur, "dealer_commission_hold_days", HOLD_DAYS_DEFAULT))


def _money(v):
    return round(float(v or 0), 2)


def order_commission(cur, order, dealer, hold, now=None, cache=None):
    """Provize a stav pro JEDNU objednavku dealera (order = radek shop_orders, dealer = radek dealers). Cista funkce nad daty v DB, nic nezapisuje."""
    now = now or _now()
    cache = cache if cache is not None else {}
    cur.execute("SELECT id, product_id, product_name_snapshot, qty, line_total_czk FROM shop_order_items WHERE order_id=%s ORDER BY id", (order["id"],))
    items = cur.fetchall()
    cur.execute("SELECT r.id, r.status, r.resolution, ri.order_item_id, ri.qty, ri.unit_price_czk FROM shop_returns r "
                "LEFT JOIN shop_return_items ri ON ri.return_id = r.id WHERE r.order_id=%s AND r.status NOT IN ('zamitnuto','zruseno')", (order["id"],))
    returns = cur.fetchall()
    open_return = any(r["status"] in OPEN_RETURN_STATUSES for r in returns)
    refunded = {}
    for r in returns:
        if r["status"] == "vyrizeno" and r["resolution"] == "refund" and r["order_item_id"] is not None:
            refunded[r["order_item_id"]] = refunded.get(r["order_item_id"], 0.0) + float(r["qty"] or 0) * float(r["unit_price_czk"] or 0)
    cur.execute("SELECT MIN(changed_at) AS t FROM shop_order_status_history WHERE order_id=%s AND status IN ('expedovana','fakturovana')", (order["id"],))
    shipped_at = cur.fetchone()["t"]

    lines, base, refunded_total, commission = [], 0.0, 0.0, 0.0
    for it in items:
        key = ("p", it["product_id"])
        if key not in cache:
            category_id = None
            if it["product_id"]:
                cur.execute("SELECT category_id FROM shop_products WHERE id=%s", (it["product_id"],))
                row = cur.fetchone()
                category_id = row["category_id"] if row else None
            cache[key] = category_id
        category_id = cache[key]
        ckey = ("c", dealer["id"], category_id)
        if ckey not in cache:
            cache[ckey] = dealers.dealer_commission_pct(cur, dealer, category_id)
        pct = cache[ckey]
        net = _money(it["line_total_czk"])
        back = min(_money(refunded.get(it["id"], 0.0)), net)
        item_commission = round((net - back) * pct / 100.0, 2)
        base += net
        refunded_total += back
        commission += item_commission
        lines.append({"item_id": it["id"], "name": it["product_name_snapshot"], "qty": it["qty"], "net_czk": net, "refunded_czk": back,
                      "commission_pct": pct, "commission_czk": item_commission})
    commission = round(commission, 2)
    base, refunded_total = round(base, 2), round(refunded_total, 2)

    paid_at = order["payment_received_at"]
    fully_paid = paid_at is not None and float(order["payment_received_total_czk"] or 0) >= float(order["total_czk"] or 0) - 1.0
    hold_until, reason = None, None
    if order["status"] == "zrusena":
        status, reason, commission = "zrusena", "order_cancelled", 0.0
    elif base > 0 and refunded_total >= base - 0.005:
        status, reason, commission = "zrusena", "fully_returned", 0.0
    elif open_return:
        status = "ceka_na_vraceni"
    elif not fully_paid:
        status = "ceka_na_zaplaceni"
    elif shipped_at is None:
        status = "ceka_na_expedici"
    else:
        hold_until = max(paid_at, shipped_at) + datetime.timedelta(days=hold)
        status = "ceka_na_lhutu" if now < hold_until else "k_vyplate"
    return {
        "order_id": order["id"], "order_number": order["order_number"], "dealer_id": dealer["id"], "order_path": order["order_path"],
        "order_status": order["status"], "created_at": _ser(order["created_at"]), "paid_at": _ser(paid_at), "shipped_at": _ser(shipped_at),
        "hold_until": _ser(hold_until), "status": status, "reason": reason,
        "base_net_czk": base, "refunded_net_czk": refunded_total, "commission_czk": commission, "lines": lines,
    }


def _date_arg(name):
    raw = (request.args.get(name) or "").strip()
    if not raw:
        return None
    try:
        return datetime.datetime.strptime(raw[:10], "%Y-%m-%d")
    except ValueError:
        return None


def commission_overview(cur, dealer_ids=None, status=None, since=None, until=None, page=1, page_size=50, with_lines=False, order_path=None):
    """Prehled provizi (nejnovejsi prvni) + souhrn podle stavu. dealer_ids None = vsichni dealeri (admin). Souhrn se pocita ze VSECH vyhovujicich objednavek,
    seznam je strankovany. Jen objednavky s dealerem, ne testovaci. Bez osobnich udaju zakazniku."""
    where, params = ["o.dealer_id IS NOT NULL", "o.is_test=0"], []
    if order_path:
        where.append("o.order_path=%s")
        params.append(order_path)
    if dealer_ids is not None:
        if not dealer_ids:
            return {"summary": {}, "total": 0, "page": page, "page_size": page_size, "commissions": []}
        where.append("o.dealer_id IN (" + ",".join(["%s"] * len(dealer_ids)) + ")")
        params += list(dealer_ids)
    if since:
        where.append("o.created_at >= %s")
        params.append(since)
    if until:
        where.append("o.created_at < %s")
        params.append(until + datetime.timedelta(days=1))
    cur.execute("SELECT o.id, o.order_number, o.status, o.created_at, o.payment_received_at, o.payment_received_total_czk, o.total_czk, o.order_path, o.dealer_id "
                f"FROM shop_orders o WHERE {' AND '.join(where)} ORDER BY o.created_at DESC, o.id DESC LIMIT {MAX_ORDERS_SCANNED}", params)
    orders = cur.fetchall()
    hold = hold_days(cur)
    now = _now()
    dealer_cache, calc_cache, rows = {}, {}, []
    for o in orders:
        if o["dealer_id"] not in dealer_cache:
            dealer_cache[o["dealer_id"]] = dealers._load_dealer(cur, o["dealer_id"])
        d = dealer_cache[o["dealer_id"]]
        if o["order_path"] == "our":
            row = order_commission(cur, o, d, hold, now, calc_cache)
        else:      # cesta 'dealer' (objednavka z jeho webu za dealerskou cenu) provizi nema
            row = {"order_id": o["id"], "order_number": o["order_number"], "dealer_id": d["id"], "order_path": o["order_path"], "order_status": o["status"],
                   "created_at": _ser(o["created_at"]), "paid_at": _ser(o["payment_received_at"]), "shipped_at": None, "hold_until": None,
                   "status": None, "reason": "no_commission_path", "base_net_czk": None, "refunded_net_czk": None, "commission_czk": 0.0, "lines": []}
        row["dealer_name"] = d["name"]
        rows.append(row)
    summary = {}
    for r in rows:
        if r["status"] is None:
            continue
        s = summary.setdefault(r["status"], {"orders": 0, "commission_czk": 0.0})
        s["orders"] += 1
        s["commission_czk"] = round(s["commission_czk"] + r["commission_czk"], 2)
    if status:
        rows = [r for r in rows if r["status"] == status]
    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start:start + page_size]
    if not with_lines:
        for r in page_rows:
            r.pop("lines", None)
    return {"summary": summary, "total": total, "page": page, "page_size": page_size, "commissions": page_rows}


def _paging():
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(200, max(1, int(request.args.get("page_size", 50))))
    except ValueError:
        page, page_size = 1, 50
    return page, page_size


def _status_arg():
    s = (request.args.get("status") or "").strip()
    return s if s in COMMISSION_STATUSES else None


# ---------------------------------------------------------------------------------------------------------------- partnersky panel
@app.get("/api/dealer/commissions")
@login_required
def dealer_commissions_list():
    """Provize dealera (jen jeho objednavky cesty 'our') + souhrn podle stavu. ?status=, ?from=YYYY-MM-DD, ?to=, ?page=, ?page_size=."""
    page, page_size = _paging()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d = dealers._my_dealer(cur)
            if not d:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            out = commission_overview(cur, [d["id"]], _status_arg(), _date_arg("from"), _date_arg("to"), page, page_size, order_path="our")
            out["hold_days"] = hold_days(cur)
    finally:
        conn.close()
    return _json(out)


@app.get("/api/dealer/orders")
@login_required
def dealer_orders_list():
    """Objednavky pripsane dealerovi (obe cesty) s provizi u cesty 'our'. Stejne filtry jako /api/dealer/commissions."""
    page, page_size = _paging()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d = dealers._my_dealer(cur)
            if not d:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            out = commission_overview(cur, [d["id"]], _status_arg(), _date_arg("from"), _date_arg("to"), page, page_size)
    finally:
        conn.close()
    return _json({"orders": out["commissions"], "total": out["total"], "page": page, "page_size": page_size})


@app.get("/api/dealer/commissions/<int:order_id>")
@login_required
def dealer_commission_detail(order_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d = dealers._my_dealer(cur)
            if not d:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            cur.execute("SELECT id, order_number, status, created_at, payment_received_at, payment_received_total_czk, total_czk, order_path, dealer_id "
                        "FROM shop_orders WHERE id=%s AND dealer_id=%s AND is_test=0", (order_id, d["id"]))
            o = cur.fetchone()
            if not o or o["order_path"] != "our":
                return _err("Objednávka neexistuje.", "not_found", 404)
            out = order_commission(cur, o, d, hold_days(cur))
    finally:
        conn.close()
    return _json({"commission": out})


# ---------------------------------------------------------------------------------------------------------------- administrace
@app.get("/api/admin/dealer-commissions")
@require_permission(PERMISSION_PROVIZE, "zobrazit")
def admin_dealer_commissions_list():
    """Provize vsech dealeru. ?dealer_id=, ?status=, ?from=, ?to=, ?page=, ?page_size=. Souhrn podle stavu je za vsechny vyhovujici objednavky."""
    page, page_size = _paging()
    dealer_id = request.args.get("dealer_id", type=int)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            out = commission_overview(cur, [dealer_id] if dealer_id else None, _status_arg(), _date_arg("from"), _date_arg("to"), page, page_size)
            out["hold_days"] = hold_days(cur)
    finally:
        conn.close()
    return _json(out)


@app.get("/api/admin/dealer-commissions/<int:order_id>")
@require_permission(PERMISSION_PROVIZE, "zobrazit")
def admin_dealer_commission_detail(order_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, order_number, status, created_at, payment_received_at, payment_received_total_czk, total_czk, order_path, dealer_id "
                        "FROM shop_orders WHERE id=%s AND dealer_id IS NOT NULL", (order_id,))
            o = cur.fetchone()
            if not o:
                return _err("Objednávka dealera neexistuje.", "not_found", 404)
            d = dealers._load_dealer(cur, o["dealer_id"])
            out = order_commission(cur, o, d, hold_days(cur)) if o["order_path"] == "our" else None
            if out:
                out["dealer_name"] = d["name"]
    finally:
        conn.close()
    if not out:
        return _err("Tahle objednávka je z cesty dealera bez provize.", "no_commission_path", 404)
    return _json({"commission": out})
