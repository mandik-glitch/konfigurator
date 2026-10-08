"""Dealersky program - MESICNI VYUCTOVANI provizi, krok 3 (bot5, 2026-10-02; zadani Robert pres bot3, TASKS.md "ZADANO 2026-10-02 ... dealersky program").

Vyuctovani je PODKLAD, podle ktereho dealer vystavi nam fakturu (my zadnou fakturu nevystavujeme). Vznika tlacitkem v adminu (zadny casovac, zadny e-mail - odchozi
e-maily jen pres schvalovani, pravidlo 16): admin pusti generovani za mesic (POST /api/admin/dealer-statements/generate), prekontroluje navrh a SCHVALI ho (cislo DV-RRRR-NNN,
od te chvile je neměnne a dealer ho vidi v panelu), po uhrade ho oznaci jako zaplacene.

Co se do vyuctovani za mesic P dostane (jen provize cesty 'our', viz dealer_commissions.order_commission, stav 'k_vyplate' ke KONCI mesice P - dalsi mesic uz ne):
  * objednavka, jejiz lhuta na vraceni skoncila nejpozdeji koncem P a dosud neni v zadnem zivem vyuctovani -> radek 'commission' (cela provize),
  * objednavka uz drive vyuctovana, jejiz provize se od te doby zmenila (vraceni, storno, zmena po vyplate) -> radek 'adjustment' se ZNAMENKEM = rozdil
    proti tomu, co uz bylo vyuctovano (zaporny = dealer vraci). Vraceni, ktere se teprve posuzuje, se nechava stat, dokud se nevyjasni.
Radky jsou SNIMEK (cisla v okamziku generovani). Draft lze prepocitat (stary draft se oznaci 'zrusen' a vznikne novy, nic se nemaze), schvaleni znovu overi, ze se podklady
od generovani nezmenily (jinak 409 stale_draft). Schvalene vyuctovani nejde menit ani prepocitat, jen zrusit (a vydat nove) nebo oznacit za zaplacene.
"""
import datetime
import html
import json
import re

from flask import request, Response

from app import app, get_conn, require_permission, current_user, login_required, log_audit
import dealers
import dealer_commissions as dc
from dealers import _json, _err, _ser, _now

PERIOD_RE = re.compile(r"^(20\d\d)-(0[1-9]|1[0-2])$")
STATEMENT_STATUSES = ("navrh", "schvaleno", "zaplaceno", "zrusen")
PERMISSION_PROVIZE = "dealer_provize"
MAX_ORDERS_SCANNED = 5000


def period_bounds(period):
    """'2026-10' -> (zacatek, KONEC VYLOUCENY) = (2026-10-01 00:00, 2026-11-01 00:00). ValueError pri neplatnem obdobi."""
    m = PERIOD_RE.match(period or "")
    if not m:
        raise ValueError("Období musí být ve tvaru RRRR-MM (např. 2026-10).")
    y, mo = int(m.group(1)), int(m.group(2))
    return datetime.datetime(y, mo, 1), datetime.datetime(y + (1 if mo == 12 else 0), 1 if mo == 12 else mo + 1, 1)


def dealer_snapshot(d):
    return {k: d.get(k) for k in ("name", "ico", "dic", "billing_street", "billing_city", "billing_zip", "bank_account", "contact_email")}


def _already_included(cur, order_id, exclude_statement_id=None):
    q = ("SELECT COALESCE(SUM(l.commission_czk), 0) AS s FROM dealer_statement_lines l JOIN dealer_statements st ON st.id = l.statement_id "
         "WHERE l.order_id=%s AND st.status <> 'zrusen'")
    params = [order_id]
    if exclude_statement_id:
        q += " AND st.id <> %s"
        params.append(exclude_statement_id)
    cur.execute(q, params)
    return round(float(cur.fetchone()["s"] or 0), 2)


def build_lines(cur, dealer, as_of, exclude_statement_id=None):
    """Radky vyuctovani pro dealera k okamziku as_of (viz hlavicka modulu). Nic nezapisuje."""
    cur.execute("SELECT id, order_number, status, created_at, payment_received_at, payment_received_total_czk, total_czk, order_path, dealer_id "
                "FROM shop_orders WHERE dealer_id=%s AND order_path='our' AND is_test=0 ORDER BY created_at, id LIMIT %s", (dealer["id"], MAX_ORDERS_SCANNED))
    orders = cur.fetchall()
    hold = dc.hold_days(cur)
    cache, lines = {}, []
    for o in orders:
        r = dc.order_commission(cur, o, dealer, hold, as_of, cache)
        if r["status"] == "k_vyplate":
            target = r["commission_czk"]
        elif r["status"] == "zrusena":
            target = 0.0
        else:
            continue         # ceka na zaplaceni/expedici/lhutu/vraceni: do vyuctovani zatim nejde (a uz vyuctovane se nemeni, dokud se to nevyjasni)
        already = _already_included(cur, o["id"], exclude_statement_id)
        delta = round(target - already, 2)
        if abs(delta) < 0.005:
            continue
        lines.append({
            "order_id": o["id"], "order_number": o["order_number"], "order_created_at": o["created_at"],
            "line_type": "commission" if abs(already) < 0.005 else "adjustment",
            "base_net_czk": round(r["base_net_czk"] - r["refunded_net_czk"], 2), "commission_czk": delta,
            "detail": {"status": r["status"], "reason": r["reason"], "target_czk": round(target, 2), "already_czk": already, "paid_at": r["paid_at"], "shipped_at": r["shipped_at"],
                       "hold_until": r["hold_until"], "refunded_net_czk": r["refunded_net_czk"], "lines": r["lines"]},
        })
    return lines


def _signature(lines):
    return sorted((int(l["order_id"]), l["line_type"], round(float(l["commission_czk"]), 2)) for l in lines)


def _line_rows(cur, statement_id):
    cur.execute("SELECT order_id, line_type, commission_czk FROM dealer_statement_lines WHERE statement_id=%s", (statement_id,))
    return [{"order_id": r["order_id"], "line_type": r["line_type"], "commission_czk": float(r["commission_czk"])} for r in cur.fetchall()]


def generate_for_dealer(cur, dealer, period, admin_id=None, now=None):
    """Vygeneruje (nebo prepocte) DRAFT vyuctovani dealera za obdobi. -> {"action": created | replaced | unchanged | skipped | no_lines, ...}. Vola se v transakci volajiciho."""
    start, end_excl = period_bounds(period)
    now = now or _now()
    as_of = min(now, end_excl)
    cur.execute("SELECT id FROM dealers WHERE id=%s FOR UPDATE", (dealer["id"],))          # zamek: dva soubezne pozadavky se serializuji
    cur.execute("SELECT * FROM dealer_statements WHERE dealer_id=%s AND period=%s AND status <> 'zrusen'", (dealer["id"], period))
    existing = cur.fetchone()
    if existing and existing["status"] != "navrh":
        return {"action": "skipped", "reason": "already_approved", "statement_id": existing["id"], "dealer_id": dealer["id"], "status": existing["status"]}
    lines = build_lines(cur, dealer, as_of, existing["id"] if existing else None)
    if not lines:
        if existing:
            cur.execute("UPDATE dealer_statements SET status='zrusen', cancelled_at=%s, cancelled_note=%s WHERE id=%s", (now, "Bez radků po přepočtu.", existing["id"]))
        return {"action": "no_lines", "dealer_id": dealer["id"], "cancelled_draft": existing["id"] if existing else None}
    if existing and _signature(lines) == _signature(_line_rows(cur, existing["id"])):
        return {"action": "unchanged", "statement_id": existing["id"], "dealer_id": dealer["id"], "total_czk": float(existing["total_czk"]), "lines_count": existing["lines_count"]}
    if existing:
        cur.execute("UPDATE dealer_statements SET status='zrusen', cancelled_at=%s, cancelled_note=%s WHERE id=%s", (now, "Přepočteno novým návrhem.", existing["id"]))
    total = round(sum(l["commission_czk"] for l in lines), 2)
    period_end_incl = end_excl - datetime.timedelta(seconds=1)
    cur.execute("INSERT INTO dealer_statements (dealer_id, period, status, total_czk, lines_count, period_end, dealer_snapshot, created_by) VALUES (%s,%s,'navrh',%s,%s,%s,%s,%s)",
                (dealer["id"], period, total, len(lines), period_end_incl, json.dumps(dealer_snapshot(dealer), ensure_ascii=False), admin_id))
    statement_id = cur.lastrowid
    for l in lines:
        cur.execute("INSERT INTO dealer_statement_lines (statement_id, order_id, line_type, order_number, order_created_at, base_net_czk, commission_czk, detail_json) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (statement_id, l["order_id"], l["line_type"], l["order_number"], l["order_created_at"], l["base_net_czk"], l["commission_czk"], json.dumps(l["detail"], ensure_ascii=False, default=str)))
    return {"action": "replaced" if existing else "created", "statement_id": statement_id, "dealer_id": dealer["id"], "total_czk": total, "lines_count": len(lines),
            "negative_total": total < 0, "replaced_statement_id": existing["id"] if existing else None}


# ---------------------------------------------------------------------------------------------------------------- serializace
def _statement_row(s, with_dealer_name=None):
    out = {k: _ser(v) for k, v in dict(s).items() if k not in ("dealer_snapshot", "period_active")}
    snap = s.get("dealer_snapshot")
    out["dealer"] = json.loads(snap) if isinstance(snap, (str, bytes)) else snap
    if with_dealer_name is not None:
        out["dealer_name"] = with_dealer_name
    return out


def _lines_of(cur, statement_id, detail=False):
    cur.execute("SELECT id, order_id, line_type, order_number, order_created_at, base_net_czk, commission_czk" + (", detail_json" if detail else "") +
                " FROM dealer_statement_lines WHERE statement_id=%s ORDER BY order_created_at, id", (statement_id,))
    rows = []
    for r in cur.fetchall():
        row = {k: _ser(v) for k, v in dict(r).items() if k != "detail_json"}
        if detail:
            dj = r.get("detail_json")
            row["detail"] = json.loads(dj) if isinstance(dj, (str, bytes)) else dj
        rows.append(row)
    return rows


def _fmt(v):
    return f"{float(v):,.2f}".replace(",", " ").replace(".", ",")


def render_document(statement, lines):
    """Vyuctovani jako samostatne HTML (tisk / ulozit jako PDF z prohlizece). Vsechny hodnoty jsou escapovane."""
    from documents import SUPPLIER
    e = lambda x: html.escape("" if x is None else str(x))
    snap = statement.get("dealer") or {}
    draft = statement["status"] == "navrh"
    zrusen = statement["status"] == "zrusen"
    rows = "".join(
        f"<tr><td>{e(l['order_number'])}</td><td>{e((l['order_created_at'] or '')[:10])}</td><td>{'Korekce' if l['line_type'] == 'adjustment' else 'Provize'}</td>"
        f"<td class='n'>{_fmt(l['base_net_czk'])}</td><td class='n'>{_fmt(l['commission_czk'])}</td></tr>" for l in lines)
    nadpis = f"Vyúčtování provize {e(statement.get('statement_number') or '(návrh)')}"
    stamp = "<div class='stamp'>NÁVRH – zatím není schváleno</div>" if draft else ("<div class='stamp'>ZRUŠENO</div>" if zrusen else "")
    adresa = ", ".join(x for x in (snap.get("billing_street"), " ".join(x for x in (snap.get("billing_zip"), snap.get("billing_city")) if x)) if x)
    return (
        "<!doctype html><html lang='cs'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{nadpis}</title><style>body{{font:14px/1.5 system-ui,sans-serif;margin:32px auto;max-width:860px;padding:0 16px;color:#111}}"
        "h1{font-size:22px;margin:0 0 4px}.sub{color:#555;margin-bottom:20px}.stamp{border:2px solid #b00;color:#b00;display:inline-block;padding:4px 12px;margin:8px 0;font-weight:700}"
        ".cols{display:flex;gap:32px;flex-wrap:wrap;margin:16px 0}.cols>div{min-width:240px}table{border-collapse:collapse;width:100%;margin:12px 0}"
        "th,td{border-bottom:1px solid #ccc;padding:6px 8px;text-align:left}th{background:#f3f3f3}.n{text-align:right;white-space:nowrap}.tot td{font-weight:700;border-top:2px solid #111}"
        ".note{background:#f7f7f7;padding:10px 14px;margin-top:20px;font-size:13px}@media print{body{margin:0}}</style></head><body>"
        f"<h1>{nadpis}</h1><div class='sub'>Období {e(statement['period'])} · stav: {e(statement['status'])}</div>{stamp}"
        f"<div class='cols'><div><b>Vystavovatel podkladu</b><br>{e(SUPPLIER['name'])}<br>{e(SUPPLIER['street'])}, {e(SUPPLIER['city'])}<br>IČO {e(SUPPLIER['ico'])} · DIČ {e(SUPPLIER['dic'])}</div>"
        f"<div><b>Dealer</b><br>{e(snap.get('name'))}<br>{e(adresa)}<br>IČO {e(snap.get('ico'))}{(' · DIČ ' + e(snap.get('dic'))) if snap.get('dic') else ''}"
        f"{('<br>Účet pro úhradu: ' + e(snap.get('bank_account'))) if snap.get('bank_account') else ''}</div></div>"
        "<table><thead><tr><th>Objednávka</th><th>Datum</th><th>Typ</th><th class='n'>Základ bez DPH (Kč)</th><th class='n'>Provize bez DPH (Kč)</th></tr></thead><tbody>"
        f"{rows}</tbody><tfoot><tr class='tot'><td colspan='4'>K fakturaci celkem (bez DPH)</td><td class='n'>{_fmt(statement['total_czk'])} Kč</td></tr></tfoot></table>"
        "<div class='note'>Podle tohoto vyúčtování vystaví dealer fakturu na uvedenou částku (DPH přidá dealer, je-li plátcem). Vlastní fakturu k provizi nevystavujeme. "
        "Provize je z ceny zboží bez DPH a bez dopravy; započítány jsou objednávky, jejichž lhůta na vrácení zboží skončila v daném období. Řádek „Korekce“ upravuje dříve vyúčtovanou provizi "
        "(vrácení nebo storno po vyúčtování; záporná částka se odečítá).</div></body></html>")


# ---------------------------------------------------------------------------------------------------------------- administrace
@app.get("/api/admin/dealer-statements")
@require_permission(PERMISSION_PROVIZE, "zobrazit")
def admin_statements_list():
    where, params = [], []
    for col, arg in (("s.dealer_id", request.args.get("dealer_id", type=int)), ("s.period", (request.args.get("period") or "").strip() or None)):
        if arg:
            where.append(f"{col}=%s")
            params.append(arg)
    status = request.args.get("status")
    if status in STATEMENT_STATUSES:
        where.append("s.status=%s")
        params.append(status)
    elif request.args.get("all") != "1":
        where.append("s.status <> 'zrusen'")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT s.*, d.name AS dealer_name FROM dealer_statements s JOIN dealers d ON d.id = s.dealer_id" + ((" WHERE " + " AND ".join(where)) if where else "") +
                        " ORDER BY s.period DESC, d.name, s.id DESC", params)
            rows = [_statement_row(r, r["dealer_name"]) for r in cur.fetchall()]
    finally:
        conn.close()
    return _json({"statements": rows})


@app.get("/api/admin/dealer-statements/<int:statement_id>")
@require_permission(PERMISSION_PROVIZE, "zobrazit")
def admin_statement_get(statement_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT s.*, d.name AS dealer_name FROM dealer_statements s JOIN dealers d ON d.id = s.dealer_id WHERE s.id=%s", (statement_id,))
            s = cur.fetchone()
            if not s:
                return _err("Vyúčtování neexistuje.", "not_found", 404)
            out = _statement_row(s, s["dealer_name"])
            out["lines"] = _lines_of(cur, statement_id, detail=request.args.get("detail") == "1")
    finally:
        conn.close()
    return _json({"statement": out})


@app.get("/api/admin/dealer-statements/<int:statement_id>/document")
@require_permission(PERMISSION_PROVIZE, "zobrazit")
def admin_statement_document(statement_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM dealer_statements WHERE id=%s", (statement_id,))
            s = cur.fetchone()
            if not s:
                return _err("Vyúčtování neexistuje.", "not_found", 404)
            doc = render_document(_statement_row(s), _lines_of(cur, statement_id))
    finally:
        conn.close()
    resp = Response(doc, mimetype="text/html")
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@app.post("/api/admin/dealer-statements/generate")
@require_permission(PERMISSION_PROVIZE, "vytvorit")
def admin_statements_generate():
    """Vygeneruje DRAFT vyuctovani za mesic: {"period": "2026-10", "dealer_id": volitelne}. Bez dealer_id pro vsechny dealery, kteri maji objednavky cesty 'our'.
    Odpoved: results[] (created | replaced | unchanged | skipped | no_lines) po dealerech. Nic se neposila, nic se nemaze."""
    body = request.get_json(silent=True) or {}
    period = (body.get("period") or "").strip()
    try:
        start, end_excl = period_bounds(period)
    except ValueError as e:
        return _err(str(e), "validation", 400)
    if start > _now():
        return _err("Za budoucí období nejde vyúčtování vytvořit.", "validation", 400)
    user = current_user()
    dealer_id = body.get("dealer_id")
    conn = get_conn()
    results = []
    try:
        with conn.cursor() as cur:
            if dealer_id:
                cur.execute("SELECT * FROM dealers WHERE id=%s", (dealer_id,))
                ds = cur.fetchall()
                if not ds:
                    return _err("Dealer neexistuje.", "not_found", 404)
            else:
                cur.execute("SELECT d.* FROM dealers d WHERE d.id IN (SELECT DISTINCT dealer_id FROM shop_orders WHERE dealer_id IS NOT NULL AND order_path='our') ORDER BY d.name")
                ds = cur.fetchall()
            for d in ds:
                try:
                    results.append(generate_for_dealer(cur, d, period, user["id"]))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    app.logger.exception("dealer_statements: generovani pro dealera %s selhalo", d["id"])
                    results.append({"action": "error", "dealer_id": d["id"]})
    finally:
        conn.close()
    log_audit(user["id"], "create", "dealer_statements", None, {"period": period, "results": [{k: r.get(k) for k in ("action", "dealer_id", "statement_id")} for r in results]})
    return _json({"period": period, "results": results})


def _load_for_update(cur, statement_id):
    cur.execute("SELECT * FROM dealer_statements WHERE id=%s FOR UPDATE", (statement_id,))
    return cur.fetchone()


@app.post("/api/admin/dealer-statements/<int:statement_id>/approve")
@require_permission(PERMISSION_PROVIZE, "upravit")
def admin_statement_approve(statement_id):
    """Schvali DRAFT: znovu overi, ze se podklady od generovani nezmenily (jinak 409 stale_draft), prideli cislo DV-RRRR-NNN a vyuctovani zamkne.
    Zaporny soucet (dealer vraci vic nez dostava) jde schvalit jen s {"force": true}."""
    body = request.get_json(silent=True) or {}
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            s = _load_for_update(cur, statement_id)
            if not s:
                return _err("Vyúčtování neexistuje.", "not_found", 404)
            if s["status"] != "navrh":
                return _err("Schválit jde jen návrh.", "bad_state", 409)
            dealer = dealers._load_dealer(cur, s["dealer_id"])
            start, end_excl = period_bounds(s["period"])
            lines = build_lines(cur, dealer, min(_now(), end_excl), s["id"])
            if _signature(lines) != _signature(_line_rows(cur, s["id"])):
                return _err("Podklady se od vygenerování změnily (vrácení, storno, platba) - vygenerujte vyúčtování znovu.", "stale_draft", 409)
            if float(s["total_czk"]) < 0 and not body.get("force"):
                return _err("Součet je záporný (dealer vrací víc, než dostává). Schválit jde jen s potvrzením (force).", "negative_total", 409)
            year = start.year
            cur.execute("SELECT COALESCE(MAX(seq_number), 0) AS m FROM dealer_statements WHERE seq_year=%s FOR UPDATE", (year,))
            seq = cur.fetchone()["m"] + 1
            number = f"DV-{year}-{seq:03d}"
            cur.execute("UPDATE dealer_statements SET status='schvaleno', approved_at=%s, approved_by=%s, seq_year=%s, seq_number=%s, statement_number=%s, dealer_snapshot=%s WHERE id=%s",
                        (_now(), user["id"], year, seq, number, json.dumps(dealer_snapshot(dealer), ensure_ascii=False), statement_id))
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "dealer_statement", statement_id, {"approved": number})
    return _json({"status": "ok", "statement_number": number})


@app.post("/api/admin/dealer-statements/<int:statement_id>/paid")
@require_permission(PERMISSION_PROVIZE, "upravit")
def admin_statement_paid(statement_id):
    """Oznaci schvalene vyuctovani za zaplacene: {"paid_at": "YYYY-MM-DD" (volitelne, vychozi dnes), "note": "..."}."""
    body = request.get_json(silent=True) or {}
    paid_at = _now()
    if body.get("paid_at"):
        try:
            paid_at = datetime.datetime.strptime(str(body["paid_at"])[:10], "%Y-%m-%d")
        except ValueError:
            return _err("Datum úhrady musí být ve tvaru RRRR-MM-DD.", "validation", 400)
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            s = _load_for_update(cur, statement_id)
            if not s:
                return _err("Vyúčtování neexistuje.", "not_found", 404)
            if s["status"] != "schvaleno":
                return _err("Zaplacené jde označit jen schválené vyúčtování.", "bad_state", 409)
            cur.execute("UPDATE dealer_statements SET status='zaplaceno', paid_at=%s, paid_note=%s WHERE id=%s", (paid_at, dealers._clean(body.get("note"), 255), statement_id))
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "dealer_statement", statement_id, {"paid_at": paid_at.isoformat()})
    return _json({"status": "ok"})


@app.post("/api/admin/dealer-statements/<int:statement_id>/cancel")
@require_permission(PERMISSION_PROVIZE, "upravit")
def admin_statement_cancel(statement_id):
    """Zrusi navrh nebo schvalene (ne zaplacene) vyuctovani: {"note": "duvod"}. Radky se uvolni - objednavky se zase mohou dostat do dalsiho vyuctovani. Nic se nemaze."""
    body = request.get_json(silent=True) or {}
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            s = _load_for_update(cur, statement_id)
            if not s:
                return _err("Vyúčtování neexistuje.", "not_found", 404)
            if s["status"] not in ("navrh", "schvaleno"):
                return _err("Zrušit jde jen návrh nebo schválené (nezaplacené) vyúčtování.", "bad_state", 409)
            cur.execute("UPDATE dealer_statements SET status='zrusen', cancelled_at=%s, cancelled_note=%s WHERE id=%s", (_now(), dealers._clean(body.get("note"), 255), statement_id))
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "dealer_statement", statement_id, {"cancelled": True})
    return _json({"status": "ok"})


# ---------------------------------------------------------------------------------------------------------------- partnersky panel
def _my_statement(cur, statement_id):
    d = dealers._my_dealer(cur)
    if not d:
        return None, None
    cur.execute("SELECT * FROM dealer_statements WHERE id=%s AND dealer_id=%s AND status IN ('schvaleno','zaplaceno')", (statement_id, d["id"]))
    return d, cur.fetchone()


@app.get("/api/dealer/statements")
@login_required
def dealer_statements_list():
    """Vyuctovani dealera: jen SCHVALENA a zaplacena (navrhy a zrusena dealer nevidi)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d = dealers._my_dealer(cur)
            if not d:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            cur.execute("SELECT * FROM dealer_statements WHERE dealer_id=%s AND status IN ('schvaleno','zaplaceno') ORDER BY period DESC, id DESC", (d["id"],))
            rows = [_statement_row(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return _json({"statements": rows})


@app.get("/api/dealer/statements/<int:statement_id>")
@login_required
def dealer_statement_get(statement_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d, s = _my_statement(cur, statement_id)
            if d is None:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            if not s:
                return _err("Vyúčtování neexistuje.", "not_found", 404)
            out = _statement_row(s)
            out["lines"] = _lines_of(cur, statement_id)
    finally:
        conn.close()
    return _json({"statement": out})


@app.get("/api/dealer/statements/<int:statement_id>/document")
@login_required
def dealer_statement_document(statement_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d, s = _my_statement(cur, statement_id)
            if d is None:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            if not s:
                return _err("Vyúčtování neexistuje.", "not_found", 404)
            doc = render_document(_statement_row(s), _lines_of(cur, statement_id))
    finally:
        conn.close()
    resp = Response(doc, mimetype="text/html")
    resp.headers["Cache-Control"] = "private, no-store"
    return resp
