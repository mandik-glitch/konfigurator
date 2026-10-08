"""Registr botů (Robert, 2026-09-12, pres bot3/chat: "musime ustálit
boty, každý bude mít svou specializaci", "editovatelná tabulka botů,
včetně jejich popisu práce") - první tabulka v nové sekci "Přehledy"
administrace (webapp/admin.html, data-tab="boti").

VEDOMĚ SAMOSTATNÁ NOVÁ TABULKA (sql/2026-09-12_bots.sql), ne rozšíření
`bot_handover` (sql/2026-09-02_bot_handover.sql, scripts/handover.py) -
ten je LOG jednotlivých předávek/úkolů přes všech 6 projektů na VPS
(řádek na událost), tenhle je REGISTR (jeden řádek na bota, ručně
udržovaná AKTUÁLNÍ specializace). `bot_id` (např. "bot3", "bot16") je
ta neformální nálepka používaná uz dnes v BOT_ID env promenne pro git
commity (viz WORKFLOW.md) - boti dosud NEMĚLI žádný záznam v DB.

Dve pozdejsi rozsireni tehoz dne (Robert, chat, nad screenshotem Pipeline
diagramu + primo v chatu):
- `pipeline_uzly` (sql/2026-09-12_bots_pipeline_uzly.sql) - volny CSV
  seznam klicu uzlu Pipeline diagramu (kanonicky seznam viz
  PIPELINE_UZLY v webapp/admin/js/prehledy-boti.js), kdo ma ktery uzel
  na starosti.
- `bot_ukoly` (sql/2026-09-12_bot_ukoly.sql, SAMOSTATNA tabulka) -
  "ukoly a pravidla", ktere Robert v chatu oznaci frazi "ukol na zed",
  aby se neztratily mezi sessions. Robert vyslovne: "s kompletni historii"
  + "priradi se jen k tomu spravnemu botovi" - bot_id je proto POVINNY
  (musi jit o existujiciho bota z `bots`, overuje se pri zapisu) a UI
  nema tlacitko mazani (jen priznak `hotovo`) - historii drzi existujici
  log_audit()/#tab-auditlog, stejne jako zbytek administrace.
"""
import json
import re
import time
from datetime import datetime, timedelta

from flask import request, jsonify, Response

from app import app, get_conn, require_permission, current_user, log_audit

# Robert (chat, 2026-09-12): "kdyz bot zamrzne, zmizi, nereaguje nebo je
# neaktivni at se stav zobrazuje v tabulce" + "viditelny log kdy se
# naposled divail na svoje ukoly na zdi". www-data (gunicorn) nema
# pristup k root tmux socketum (overeno primo: /tmp/tmux-0/default je
# 0660 root:root, www-data v groupe neni) - "bezi ten bot fakt v
# tmuxu?" tedy ze serveru neni technicky zjistitelne. Misto toho
# SAMOHLASENY tep, stejny vzor jako uz existujici render worker
# heartbeat (api/render_worker.py, worker_tepe/worker_zaseknuty) - viz
# admin_bot_checkin() nize. Prahy jsou odhad (zadna historicka data o
# tom, jak casto boti realne checkuji) - klidne se casem doladi.
CHECKIN_AKTIVNI_MIN = 30      # posledni tep mladsi nez tohle = "aktivni"
CHECKIN_NEAKTIVNI_MIN = 180   # mladsi nez tohle = "neaktivni", starsi/zadny = "zmizel"


# bot3, 2026-09-12 (Robert: "rucni prace nefunguje vzdy", "jak to delaji
# profi programy?"): pro boty se znamym `tmux_target` (lokalni tmux
# session na TETO VPS) existuje SILNEJSI signal nez checkin-timestamp -
# skutecny stav procesu (scripts/2026-09-12_bot_tmux_liveness.py, cron
# kazdou minutu, stejny princip jako systemd/Kubernetes liveness probe -
# viz hlavicka toho skriptu). Kdyz je znamo `proces_ziva=False`, je to
# tvrdy dukaz "zmizel" bez ohledu na to, jak stary/novy je posledni
# checkin. Boti BEZ tmux_target (bot8 - bezi jinde/pres Remote Control)
# tímhle nejsou pokryti vubec - `proces_ziva` u nich zustava NULL,
# padaji zpet na cisty checkin-timestamp odhad jako driv.
def _bot_stav(last_checkin_at, proces_ziva=None, proces_checked_at=None):
    # Robert 2026-09-12 ("pripada ti to zive?" nad screenshotem, kde bot4
    # - fyzicky bezici, prave se mnou komunikujici - svitil oranzove
    # "neaktivni", protoze checkin-timestamp byl stary 40 min): tvrdy
    # proof-of-life (tmux proces) MUSI byt silnejsi signal OBOUSMERNE, ne
    # jen pro "zmizel". "checkin je stary" znamena jen "naposledy
    # neudelal commit/render/prijatou zpravu" - NEznamena, ze bot fyzicky
    # neni tam a nepracuje (cti/kouka/ceka). Kdyz mame cerstve overeny
    # bezici proces, veri se JEMU, ne stare checkin-timestamp heuristice.
    if proces_checked_at is not None:
        stari_proc = datetime.now() - proces_checked_at
        if stari_proc <= timedelta(minutes=5):
            return "aktivni" if proces_ziva else "zmizel"
    if not last_checkin_at:
        return "nikdy"
    stari = datetime.now() - last_checkin_at
    if stari <= timedelta(minutes=CHECKIN_AKTIVNI_MIN):
        return "aktivni"
    if stari <= timedelta(minutes=CHECKIN_NEAKTIVNI_MIN):
        return "neaktivni"
    return "zmizel"


def _bot_public(row):
    return {
        "id": row["id"],
        "bot_id": row["bot_id"],
        "specializace": row["specializace"] or "",
        "pipeline_uzly": row["pipeline_uzly"] or "",
        "last_checkin_at": row["last_checkin_at"].isoformat() if row["last_checkin_at"] else None,
        "aktualni_cinnost": row["aktualni_cinnost"] or "",
        "aktualni_soubor": row["aktualni_soubor"] or "",
        "tmux_target": row.get("tmux_target") or "",
        "proces_ziva": row.get("proces_ziva"),
        "proces_checked_at": row["proces_checked_at"].isoformat() if row.get("proces_checked_at") else None,
        "stav": _bot_stav(row["last_checkin_at"], row.get("proces_ziva"), row.get("proces_checked_at")),
        # bot16, 2026-09-17 (Robert primo): "skutecne aktualni model a
        # effort" - z stejneho OTel scrape jako Tokeny nize, ale primo
        # na `bots` (sql/2026-09-17_bots_current_model_effort.sql), ne
        # LEFT JOIN - zapisuje scripts/2026-09-12_bot_token_usage_sync.py
        # jen z `query_source="main"` radku PRI KLADNE delte (viz
        # komentar tam) - "posledni model, ktery FAKT jeste roste", ne
        # jen "posledni videny v expozici" (stary switchnuty model muze
        # v expozici zustat viset donekonecna).
        "current_model": row.get("current_model"),
        "current_effort": row.get("current_effort"),
        "current_model_updated_at": row["current_model_updated_at"].isoformat() if row.get("current_model_updated_at") else None,
        # bot16, 2026-09-12 (Robert pres bot3: sloupec "Tokeny") - z
        # LEFT JOIN bot_token_usage v admin_bots_list nize (viz
        # sql/2026-09-12_bot_token_usage.sql,
        # scripts/2026-09-12_bot_token_usage_sync.py). Do cutoveru
        # 2026-09-16 22:00 (viz /opt/bot-telemetry/RUNBOOK_CUTOVER.md)
        # zustanou tyhle hodnoty None/0 u vsech - zadna bot session
        # jeste neposila OTel metriky.
        "tokens_total": row.get("tokens_total"),
        "cost_usd_total": float(row["cost_usd_total"]) if row.get("cost_usd_total") is not None else None,
        "tokens_last_synced_at": row["tokens_last_synced_at"].isoformat() if row.get("tokens_last_synced_at") else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@app.get("/api/bots/checkin")
def bots_checkin():
    """Volá si to BOT SÁM (ne admin z prohlížeče, proto bez
    @require_permission - stejný "žádná login session, jen shodný stroj"
    model jako scripts/_render_klic.py). Jedna akce dělá dvě věci najednou
    (Robertovo zadání je spojilo do jedné otázky "kdy naposled checkoval /
    kdy naposled koukl na svoji zeď"): (1) zapíše tep = "tenhle bot žije",
    (2) vrátí nesplněné úkoly z jeho zdi - tím dostane bot i DŮVOD si to
    volat (chce vidět svoje úkoly), ne jen povinnost bez odezvy.
    """
    bot_id = (request.args.get("bot_id") or "").strip()
    # Kratky volny text "co prave delam" (Robert: "abych se te nemusel
    # porad ptat co kdo dela... strucne co dela") - VOLITELNY, bez nej se
    # jen zapise tep (stav bota porad jde videt). Orezano na delku sloupce,
    # ne 500 chyba - checkin ma byt bezbolestny, at ho boti fakt volaji.
    cinnost = (request.args.get("cinnost") or "").strip()[:300]
    # Robert 2026-09-12 ("pridej sloupec jmeno souboru, se kterym pracuje"):
    # VOLITELNY - jen nastroje, co se souborem primo pracuji (Edit/Write/
    # Read), Bash/SendMessage/atd. ho proste neposilaji (viz hook, co
    # nehada soubor z prikazu). Prazdna hodnota MAZE predchozi soubor
    # (bot uz nepracuje s tim starym) - proto se pise vzdy, ne jen "kdyz
    # neni prazdny" jako u cinnosti.
    soubor = (request.args.get("soubor") or "").strip()[:300]
    if not bot_id:
        return jsonify({"error": "Chybí bot_id."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM bots WHERE bot_id=%s", (bot_id,))
            if not cur.fetchone():
                return jsonify({"error": "Tenhle bot není v registru (Přehledy > Boti) - přidej ho tam nejdřív."}), 400
            if cinnost:
                cur.execute("UPDATE bots SET last_checkin_at=NOW(), aktualni_cinnost=%s, aktualni_soubor=%s WHERE bot_id=%s",
                            (cinnost, soubor or None, bot_id))
            else:
                cur.execute("UPDATE bots SET last_checkin_at=NOW() WHERE bot_id=%s", (bot_id,))
            cur.execute("SELECT text, created_at FROM bot_ukoly WHERE bot_id=%s AND hotovo=0 "
                        "ORDER BY created_at DESC", (bot_id,))
            ukoly = [{"text": r["text"], "created_at": r["created_at"].isoformat() if r["created_at"] else None}
                     for r in cur.fetchall()]
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "bot_id": bot_id, "ukoly_na_zdi": ukoly})


@app.get("/api/bots/stav")
def bots_stav_verejny():
    """Robert 2026-09-12 ("musi to byt aktualni PRO BOTY MEZI SEBOU", ne
    jen pro admin obrazovku v prohlizeci): boti potrebuji zjistit stav
    JINEHO bota (aktivni/neaktivni/zmizel, co dela ted) BEZ admin loginu -
    `/api/admin/bots` to ma, ale je za `@require_permission`, tedy pro
    boty nepouzitelne. Stejny "zadna login session, jen shodny stroj"
    model jako `/api/bots/checkin` a `scripts/_render_klic.py` - neni to
    bezpecnostni opatreni (viz tam), jen bot-facing verze te same tabulky,
    co uz admin obrazovka ukazuje verejne v prohlizeci."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM bots ORDER BY bot_id")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"items": [_bot_public(r) for r in rows]})


def _bots_rows():
    """Sdileny dotaz pro admin_bots_list() i SSE stream nize - jedno
    misto pravdy pro to, co "radek bota" znamena."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT b.*, t.tokens_total, t.cost_usd_total, "
                "t.last_synced_at AS tokens_last_synced_at "
                "FROM bots b LEFT JOIN bot_token_usage t ON t.bot_id = b.bot_id "
                "ORDER BY b.bot_id"
            )
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/admin/bots")
@require_permission("nastaveni", "zobrazit")
def admin_bots_list():
    return jsonify({"items": [_bot_public(r) for r in _bots_rows()]})


# bot16, 2026-09-17 (Robert pres bot3): linovy graf spotreby tokenu v
# case vedle tabulky v Prehledy > Boti. `bot_token_usage` (JOIN vys)
# drzi jen kumulativni SOUCET - zadna historie, tu drzi
# `bot_token_usage_history` (sql/2026-09-17b_bot_token_usage_history_
# intraday.sql - PUVODNI verze mela jen 1 UPSERTovany radek/den/bota,
# nahrazeno po zive zpetne vazbe od Roberta), plni ji
# `scripts/2026-09-12_bot_token_usage_sync.py::snapshot_historie()`
# NOVYM radkem pri kazdem behu syncu (~2 min timer). Vraci CUMULATIVNI
# hodnoty (ne delty) - graf kresli sklon, ne vysku sloupce.
#
# Meritka 5min az 1 mesic (Robert, 2026-09-17): kratke rozsahy vraci
# SYROVE ~2min radky (max ~150/bota), delsi rozsahy se agreguji na
# serveru do kbelicku (posledni hodnota v kbelicku = spravny downsample
# pro kumulativni cislo, MAX misto podselektu na "posledni ts" - obe
# sloupce v ramci `WHERE` okna rostou monotonne, takze MAX() = hodnota
# na konci kbelicku) - jinak by mesicni pohled poslal do prohlizece
# desitky tisic bodu na kazdeho bota zbytecne.
RANGE_CONFIG = {
    "5m":  {"seconds": 5 * 60, "bucket_s": None},
    "15m": {"seconds": 15 * 60, "bucket_s": None},
    "1h":  {"seconds": 60 * 60, "bucket_s": None},
    "5h":  {"seconds": 5 * 60 * 60, "bucket_s": None},
    "1d":  {"seconds": 24 * 60 * 60, "bucket_s": 15 * 60},
    "1w":  {"seconds": 7 * 24 * 60 * 60, "bucket_s": 60 * 60},
    "1m":  {"seconds": 30 * 24 * 60 * 60, "bucket_s": 24 * 60 * 60},
}
RANGE_DEFAULT = "1d"


@app.get("/api/admin/bots/token-history")
@require_permission("nastaveni", "zobrazit")
def admin_bots_token_history():
    rozsah = request.args.get("range", RANGE_DEFAULT)
    if rozsah not in RANGE_CONFIG:
        rozsah = RANGE_DEFAULT
    cfg = RANGE_CONFIG[rozsah]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if cfg["bucket_s"]:
                # POZOR: alias MUSI byt jiny nez skutecny sloupec `ts` -
                # `AS ts` + `GROUP BY ts` se ziva overilo, ze se navaze
                # na PUVODNI sloupec (kazdy radek zvlast'), ne na tenhle
                # vypocteny alias, a agregace by tise nedelala nic
                # (0 bucketovani, jen prejmenovani sloupce).
                cur.execute(
                    "SELECT bot_id, "
                    "FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(ts)/%s)*%s) AS bucket_ts, "
                    "MAX(tokens_total_snapshot) AS tokens_total_snapshot, "
                    "MAX(cost_usd_total_snapshot) AS cost_usd_total_snapshot "
                    "FROM bot_token_usage_history "
                    "WHERE ts >= DATE_SUB(NOW(), INTERVAL %s SECOND) "
                    "GROUP BY bot_id, bucket_ts "
                    "ORDER BY bot_id, bucket_ts",
                    (cfg["bucket_s"], cfg["bucket_s"], cfg["seconds"]),
                )
                sloupec_ts = "bucket_ts"
            else:
                cur.execute(
                    "SELECT bot_id, ts, tokens_total_snapshot, cost_usd_total_snapshot "
                    "FROM bot_token_usage_history "
                    "WHERE ts >= DATE_SUB(NOW(), INTERVAL %s SECOND) "
                    "ORDER BY bot_id, ts",
                    (cfg["seconds"],),
                )
                sloupec_ts = "ts"
            rows = cur.fetchall()
    finally:
        conn.close()
    items = [{
        "bot_id": r["bot_id"],
        "ts": r[sloupec_ts].isoformat() if r[sloupec_ts] else None,
        "tokens_total": r["tokens_total_snapshot"],
        "cost_usd_total": float(r["cost_usd_total_snapshot"]) if r["cost_usd_total_snapshot"] is not None else None,
    } for r in rows]
    return jsonify({"items": items, "range": rozsah, "bucketed": cfg["bucket_s"] is not None})


# bot3, 2026-09-12 (Robert: "udelej tu tabulku opravdu zivou", pak
# vyslovne "(Server-Sent Events / WebSocket)" - rychly polling nestacil,
# chtel skutecny server->prohlizec push). SSE misto WebSocketu - je to
# jednosmerny tok (server->klient), presne to, co tabulka potrebuje,
# a funguje nad bezným HTTP/Response streamem bez extra knihovny.
#
# ⭐ PRODUKCNI RIZIKO, KTEREMU SE TENHLE ENDPOINT MUSI VYHNOUT: gunicorn
# tady bezi v `sync` worker tride (kazde HTTP spojeni = 1 vlakno/proces
# po celou dobu) a OBSLUHUJE I VEREJNY E-SHOP, ne jen admin. Drive
# otevrene SSE spojeni by si drzelo workera navzdy - par zapomenutych
# otevrenych panelu by dokazalo vycerpat vsechny workery a spadnout
# CELY web zakaznikum. Pojistky: (1) workers 2->4 (viz
# /etc/systemd/system/konfigurator.service, 2026-09-12) davaji rezervu,
# (2) SSE_MAX_TRVANI_S tvrde uzavre stream i pri zapomenutem panelu,
# (3) posila se jen kdyz se data SKUTECNE zmenila (diff proti
# poslednimu payloadu), ne kazdou periodu naslepo - snizuje pocet
# zapisu, ne pocet drzenych workeru, ale je to zadarmo navic.
# bot3, 2026-09-12 (Robert: "neni to zive ani nahodou" - SKUTECNA
# pricina, ne jen nginx buffer: gunicorn bezi v `sync` tride s
# `--timeout 60` (systemd unit) - to je LIMIT, po kterem arbiter zabije
# "zaseknuty" worker proces. Sync worker se ale nema jak "ozvat" arbitru
# uprostred dlouheho pythoního generatoru - z jeho pohledu je 15minutove
# SSE spojeni k nerozeznani od skutecne zaseknuteho requestu, takze by
# ho po 60s prostě zabil. Reseni NENI zvednout globalni --timeout (to by
# oslabilo ochranu i pro VSECHNY OSTATNI routy na tomhle gunicornu -
# skutecne zaseknuty worker jinde by se poznal az za nekolik minut misto
# za minutu). Misto toho SSE_MAX_TRVANI_S drzi kazde jednotlive spojeni
# bezpecne POD 60s - server sam cistě ukonci stream, EventSource na
# klientovi (viz webapp/admin/js/prehledy-boti.js, "timeout" listener) se
# hned znovu pripoji. Uzivatel vidi nepretrzity tok (par stovek ms mezera
# na reconnect, nepostrehnutelne), gunicornuv arbiter nikdy nevidi worker
# drzet jedno spojeni dele nez desitky vterin.
SSE_INTERVAL_S = 2
SSE_MAX_TRVANI_S = 45


@app.get("/api/admin/bots/events")
@require_permission("nastaveni", "zobrazit")
def admin_bots_events():
    def generate():
        posledni_payload = None
        zacatek = time.time()
        while time.time() - zacatek < SSE_MAX_TRVANI_S:
            try:
                data = [_bot_public(r) for r in _bots_rows()]
                payload = json.dumps({"items": data}, ensure_ascii=False)
            except Exception as e:
                yield "event: error\ndata: %s\n\n" % json.dumps({"error": str(e)})
                return
            if payload != posledni_payload:
                yield "data: %s\n\n" % payload
                posledni_payload = payload
            else:
                yield ": ping\n\n"  # keep-alive komentar, zadna zmena dat
            time.sleep(SSE_INTERVAL_S)
        yield 'event: timeout\ndata: {"reason":"max_trvani"}\n\n'

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # nginx by jinak SSE bufferoval misto prubezneho posilani
        "Connection": "keep-alive",
    })


def _valid_bot_id(s):
    # Stejná neformální konvence jako BOT_ID env promenna (WORKFLOW.md) -
    # pismena/cislice/pomlcka, zadne mezery (pouziva se i jako klic
    # localStorage/lock.sh poznamek jinde v projektu).
    return bool(s) and bool(re.fullmatch(r"[a-zA-Z0-9\-]{1,40}", s))


@app.post("/api/admin/bots")
@require_permission("nastaveni", "vytvorit")
def admin_bots_create():
    body = request.get_json(silent=True) or {}
    bot_id = (body.get("bot_id") or "").strip()
    if not _valid_bot_id(bot_id):
        return jsonify({"error": "Neplatné jméno bota (písmena/číslice/pomlčka, bez mezer)."}), 400
    specializace = (body.get("specializace") or "").strip() or None
    pipeline_uzly = (body.get("pipeline_uzly") or "").strip() or None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM bots WHERE bot_id=%s", (bot_id,))
            if cur.fetchone():
                return jsonify({"error": "Tenhle bot už v tabulce je."}), 409
            cur.execute("INSERT INTO bots (bot_id, specializace, pipeline_uzly) VALUES (%s,%s,%s)",
                        (bot_id, specializace, pipeline_uzly))
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "bot", new_id, bot_id)
    return jsonify({"status": "ok", "id": new_id})


@app.put("/api/admin/bots/<int:bot_row_id>")
@require_permission("nastaveni", "upravit")
def admin_bots_update(bot_row_id):
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM bots WHERE id=%s", (bot_row_id,))
            if not cur.fetchone():
                return jsonify({"error": "Bot nenalezen."}), 404
            fields, params = [], []
            if "bot_id" in body:
                bot_id = (body.get("bot_id") or "").strip()
                if not _valid_bot_id(bot_id):
                    return jsonify({"error": "Neplatné jméno bota (písmena/číslice/pomlčka, bez mezer)."}), 400
                cur.execute("SELECT id FROM bots WHERE bot_id=%s AND id!=%s", (bot_id, bot_row_id))
                if cur.fetchone():
                    return jsonify({"error": "Tenhle bot už v tabulce je."}), 409
                fields.append("bot_id=%s"); params.append(bot_id)
            if "specializace" in body:
                fields.append("specializace=%s"); params.append((body.get("specializace") or "").strip() or None)
            if "pipeline_uzly" in body:
                fields.append("pipeline_uzly=%s"); params.append((body.get("pipeline_uzly") or "").strip() or None)
            if fields:
                params.append(bot_row_id)
                cur.execute(f"UPDATE bots SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "bot", bot_row_id, ", ".join(body.keys()))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/bots/<int:bot_row_id>")
@require_permission("nastaveni", "smazat")
def admin_bots_delete(bot_row_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT bot_id FROM bots WHERE id=%s", (bot_row_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Bot nenalezen."}), 404
            cur.execute("DELETE FROM bots WHERE id=%s", (bot_row_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "bot", bot_row_id, row["bot_id"])
    return jsonify({"status": "ok"})
# ==================== PIPELINE UZLY (odpovednost bota) ====================
# Robert (chat, po prvnim navrhu sloupce v tabulce Boti): "nejak to
# efektne oprav aby se to dalo zaroven rucne menit a hlavne aby to
# nezbralo velkou plochu, stacilo by uplne kdyby to bylo v tom
# pipelinu, tady to byt nemusi" - presunuto z Boti tabu do Pipeline
# tabu (viz renderPipelineDiagram + novy ovladaci radek v
# crm-nabidky.js). Data zustavaji ve stejnem sloupci `bots.pipeline_uzly`
# (CSV) jako driv - meni se jen KDE/JAK se edituje, ne tvar dat.
#
# Endpoint vynucuje NEJVYSE JEDNOHO vlastnika na uzel (na rozdil od
# puvodniho multi-selectu, kde teoreticky mohlo "vsechno mit vsechno" -
# presne tenhle dojem Robertovi vadil - "to maji vsichni odpovednost za
# vse?"): pri prirazeni uzlu botovi se stejny uzel nejdriv odebere
# VSEM ostatnim, teprve pak prida cilovemu (nebo jen odebere, kdyz
# bot_id chybi = "nikdo").


@app.put("/api/admin/bots/pipeline-uzel")
@require_permission("nastaveni", "upravit")
def admin_bots_set_pipeline_uzel():
    body = request.get_json(silent=True) or {}
    uzel = (body.get("uzel") or "").strip()
    bot_id = (body.get("bot_id") or "").strip() or None
    if not uzel:
        return jsonify({"error": "Chybí uzel."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if bot_id:
                cur.execute("SELECT id FROM bots WHERE bot_id=%s", (bot_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Tenhle bot není v registru (Přehledy > Boti)."}), 400
            cur.execute("SELECT id, bot_id, pipeline_uzly FROM bots")
            for r in cur.fetchall():
                aktualni = set(x.strip() for x in (r["pipeline_uzly"] or "").split(",") if x.strip())
                ma_ho = uzel in aktualni
                ma_byt = (r["bot_id"] == bot_id)
                if ma_ho == ma_byt:
                    continue
                if ma_byt:
                    aktualni.add(uzel)
                else:
                    aktualni.discard(uzel)
                cur.execute("UPDATE bots SET pipeline_uzly=%s WHERE id=%s",
                            (",".join(sorted(aktualni)) or None, r["id"]))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "bot_pipeline_uzel", None,
              "%s -> %s" % (uzel, bot_id or "(nikdo)"))
    return jsonify({"status": "ok"})


# ==================== UKOLY NA ZED ====================
# Robert (chat, 2026-09-12): "tabulka botů musí obsahovat mnou zadané
# ukoly a pravidla které v chatu oznacim jako: ukol na zed, s kompletní
# historí, a priradi se jen k tomu spravnemu botovi". Viz komentar v
# hlavicce souboru + sql/2026-09-12_bot_ukoly.sql.


def _ukol_public(row):
    return {
        "id": row["id"],
        "text": row["text"],
        "bot_id": row["bot_id"],
        "hotovo": bool(row["hotovo"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@app.get("/api/admin/bot-ukoly")
@require_permission("nastaveni", "zobrazit")
def admin_bot_ukoly_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Nejnovejsi prvni - "nastenka", cerstve zapsane ukoly patri
            # nahoru. Nedokoncene pred hotovymi v ramci stejneho dne by
            # slo pridat pozdeji, kdyz pribude vic radku - zatim staci.
            cur.execute("SELECT * FROM bot_ukoly ORDER BY created_at DESC, id DESC")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"items": [_ukol_public(r) for r in rows]})


@app.post("/api/admin/bot-ukoly")
@require_permission("nastaveni", "vytvorit")
def admin_bot_ukoly_create():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    bot_id = (body.get("bot_id") or "").strip()
    if not text:
        return jsonify({"error": "Vyplň text úkolu/pravidla."}), 400
    if not bot_id:
        return jsonify({"error": "Vyber, ke kterému botovi úkol patří."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # "priradi se jen k tomu spravnemu botovi" - overit, ze bot
            # opravdu existuje v registru, driv nez se k nemu neco prisoudi.
            cur.execute("SELECT id FROM bots WHERE bot_id=%s", (bot_id,))
            if not cur.fetchone():
                return jsonify({"error": "Tenhle bot není v registru (Přehledy > Boti) - přidej ho tam nejdřív."}), 400
            cur.execute("INSERT INTO bot_ukoly (text, bot_id) VALUES (%s,%s)", (text, bot_id))
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "bot_ukol", new_id, "%s: %s" % (bot_id, text[:120]))
    return jsonify({"status": "ok", "id": new_id})


@app.put("/api/admin/bot-ukoly/<int:ukol_id>")
@require_permission("nastaveni", "upravit")
def admin_bot_ukoly_update(ukol_id):
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM bot_ukoly WHERE id=%s", (ukol_id,))
            if not cur.fetchone():
                return jsonify({"error": "Úkol nenalezen."}), 404
            fields, params = [], []
            if "text" in body:
                text = (body.get("text") or "").strip()
                if not text:
                    return jsonify({"error": "Text úkolu nemůže být prázdný."}), 400
                fields.append("text=%s"); params.append(text)
            if "bot_id" in body:
                bot_id = (body.get("bot_id") or "").strip()
                if not bot_id:
                    return jsonify({"error": "Vyber, ke kterému botovi úkol patří."}), 400
                cur.execute("SELECT id FROM bots WHERE bot_id=%s", (bot_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Tenhle bot není v registru (Přehledy > Boti)."}), 400
                fields.append("bot_id=%s"); params.append(bot_id)
            if "hotovo" in body:
                fields.append("hotovo=%s"); params.append(1 if body.get("hotovo") else 0)
            if fields:
                params.append(ukol_id)
                cur.execute(f"UPDATE bot_ukoly SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "bot_ukol", ukol_id, ", ".join(body.keys()))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/bot-ukoly/<int:ukol_id>")
@require_permission("nastaveni", "smazat")
def admin_bot_ukoly_delete(ukol_id):
    # Zadne tlacitko na tohle v UI (viz prehledy-boti.js) - "kompletni
    # historie" ma zustavat, mazani jen pro skutecny omyl primo pres API.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT text FROM bot_ukoly WHERE id=%s", (ukol_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Úkol nenalezen."}), 404
            cur.execute("DELETE FROM bot_ukoly WHERE id=%s", (ukol_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "bot_ukol", ukol_id, row["text"][:120])
    return jsonify({"status": "ok"})
