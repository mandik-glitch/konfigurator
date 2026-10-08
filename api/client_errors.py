"""
JS error beacon z prohlizecu (bot5, 2026-09-02, "kontrolni mechanismy na
cely system konfiguratoru" od Roberta pres bot3, dil J).

webapp/js/client-errors.js posila kazdou nezachycenou JS chybu
(window.onerror), odmitnuty Promise (unhandledrejection) a selhani
nacteni zdroje (capture 'error' listener na <script>/<img>/<link>) sem -
POST /api/client-errors (VEREJNE, bez auth - chyba muze nastat driv, nez
se stihne cokoli prihlasit). Admin cte agregovane pres GET
/api/admin/client-errors ("dash_js_chyby"/"zobrazit" - bot16, 2026-09-29,
puvodne sdilene "produkty_sklad" nesedelo s vlastni sekci panelu
clientErrorsPanel v DASHBOARD_PANEL_SECTION, viz AGENTS_LOG.md).

Agregace (ne nekonecne rostouci tabulka jednotlivych udalosti):
fingerprint = sha256(message+source+line), UNIQUE klic v client_errors
(sql/2026-09-02_client_errors.sql) - opakovany vyskyt stejne chyby (z
ruznych navstev/IP) jen zvysi `count`/posune `last_seen_at`.
"""
import hashlib
from datetime import datetime, timedelta

import pymysql
from flask import request, jsonify

from app import app, get_conn, require_permission, _client_ip, _rate_limited
from tracking import _ip_hash

# Migrace sql/2026-09-02_client_errors.sql zatim ceka na Roberta (bot3
# 2026-09-02: CREATE TABLE zablokoval auto-mode klasifikator). Dokud
# sloupec/tabulka chybi, endpoint nesmi vracet 500 na produkci - jen
# tise 204 + JEDEN warning do logu (ne pri kazdem requestu, aby log
# nezaplavilo). Az tabulka pribude, dalsi POST uz projde normalne bez
# jakehokoli restartu (stejny vzor jako turntable _has_deactivated_at_column).
_missing_table_warned = False

MAX_BODY_BYTES = 4 * 1024
MAX_MESSAGE_LEN = 500
MAX_SOURCE_LEN = 500
MAX_URL_LEN = 500
MAX_UA_LEN = 300
MAX_STACK_LEN = 2 * 1024
# Max 10 hlaseni/stranka hlida uz klient (client-errors.js) - tohle je
# druha, serverova brzda proti zneuziti/smycce napric strankami/IP
# (Robert/bot3: "limit per IP"). 120/10 min = i pri realne "error storm"
# situaci (spatny deploy, chyba na kazde strance) se stihne zaznamenat
# dost na diagnostiku, ale skript nemuze zahltit DB.
RATE_LIMIT_MAX = 120
RATE_LIMIT_WINDOW_S = 600


def _truncate(s, n):
    if s is None:
        return None
    s = str(s)
    return s[:n]


@app.post("/api/client-errors")
def public_client_error_report():
    # OPRAVA (bot15/remeslo, fáze 5 testování 2026-09-03, tenhle projekt
    # zkopírovala 1:1): `get_data(cache=False)` a PAK `request.get_json()`
    # - druhé čtení narazí na už vyčerpaný WSGI vstupní stream
    # (cache=False nic neuloží), takže `get_json(silent=True)` VŽDY tiše
    # vrátí {}, i při validním JSON těle. Živě potvrzeno na produkci:
    # jediný řádek v `client_errors` měl message="(bez zprávy)"/source
    # NULL, ale count=12 - 12 skutečných chyb tiše sesbíráno do
    # nepoužitelného placeholderu. `cache=True` (výchozí) nechá tělo v
    # mezipaměti pro následné `get_json()`.
    raw = request.get_data()
    if len(raw) > MAX_BODY_BYTES:
        return jsonify({"error": "Tělo požadavku je příliš velké."}), 413
    if _rate_limited(f"client_error:{_client_ip()}", max_requests=RATE_LIMIT_MAX, window_seconds=RATE_LIMIT_WINDOW_S):
        return jsonify({"error": "Příliš mnoho hlášení, zkuste to prosím později."}), 429

    body = request.get_json(silent=True) or {}
    message = _truncate(body.get("message") or "(bez zprávy)", MAX_MESSAGE_LEN)
    source = _truncate(body.get("source"), MAX_SOURCE_LEN)
    try:
        line = int(body.get("line")) if body.get("line") is not None else None
    except (TypeError, ValueError):
        line = None
    try:
        col = int(body.get("col")) if body.get("col") is not None else None
    except (TypeError, ValueError):
        col = None
    stack = _truncate(body.get("stack"), MAX_STACK_LEN)
    url = _truncate(body.get("url") or request.referrer or "", MAX_URL_LEN)
    # User-Agent bereme ze SERVEROVE hlavicky (stejna konvence jako
    # tracking.py), ne z klientem poslaneho pole - spolehlivejsi zdroj,
    # nejde ho z klienta zfalsovat/vynechat.
    user_agent = _truncate(request.headers.get("User-Agent"), MAX_UA_LEN)
    ip_hash = _ip_hash(_client_ip())

    fingerprint = hashlib.sha256(f"{message}|{source}|{line}".encode("utf-8")).hexdigest()

    global _missing_table_warned
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO client_errors "
                "(fingerprint, message, source, line, col, stack, url, user_agent, ip_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE count=count+1, last_seen_at=NOW(), "
                "url=VALUES(url), stack=VALUES(stack)",
                (fingerprint, message, source, line, col, stack, url, user_agent, ip_hash),
            )
        conn.commit()
    except pymysql.err.ProgrammingError as e:
        # 1146 = "Table '...' doesn't exist" (migrace jeste neprobehla,
        # viz komentar u _missing_table_warned) - nikdy 500 na produkci
        # kvuli tomuhle, jen jednou zalogovat, tise zahodit a vratit 204
        # (beacon pouziva sendBeacon/fetch keepalive - klientovi na
        # odpovedi nezalezi, hlavne aby request nikdy neselhal).
        if e.args and e.args[0] == 1146:
            if not _missing_table_warned:
                app.logger.warning(
                    "client_errors: tabulka jeste neexistuje (sql/2026-09-02_client_errors.sql "
                    "ceka na aplikaci) - beacon POSTy se zatim jen zahazuji"
                )
                _missing_table_warned = True
            return "", 204
        raise
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.get("/api/admin/client-errors")
@require_permission("dash_js_chyby", "zobrazit")
def admin_client_errors_list():
    since_raw = request.args.get("since")
    since = None
    if since_raw:
        try:
            since = datetime.fromisoformat(since_raw)
        except ValueError:
            return jsonify({"error": "Neplatné since (očekávám ISO datum)."}), 400
    else:
        since = datetime.now() - timedelta(days=14)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, fingerprint, message, source, line, col, stack, url, user_agent, "
                "count, created_at, last_seen_at FROM client_errors "
                "WHERE last_seen_at >= %s ORDER BY last_seen_at DESC LIMIT 500",
                (since,),
            )
            rows = cur.fetchall()
    except pymysql.err.ProgrammingError as e:
        if e.args and e.args[0] == 1146:  # tabulka jeste neexistuje - viz POST endpoint vyse
            return jsonify({"total": 0, "errors": [], "table_missing": True})
        raise
    finally:
        conn.close()
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
        r["last_seen_at"] = r["last_seen_at"].isoformat()
    return jsonify({"total": len(rows), "errors": rows})
