"""
QA audit panel na dashboardu admina - bot4, 2026-08-09.

Robert: "na dashboardu admina mi udelej panel, kde uvidim vsechny tyto
chyby/odchylky" (navazuje na scripts/qa_product_audit.py, viz komentar
tam). Kontroly same zije v qa_checks.py (sdileno s CLI skriptem) - tenhle
modul je tenky Flask obal: /api/admin/qa-audit (zive kontroly, bez
ukladani stavu, volitelny ?category=doplnit|opravit) +
/api/admin/qa-audit/tasks (2026-08-10, ulozene "vysoka priorita"
nahlaseni z tlacitka Opravit u nalezu bez editovatelneho zaznamu).

Robert: "jakmile ty odchylky vyresime, z panelu zmizi" - zadny "vyreseno"
flag/tabulka, kontroly bezi ZIVE nad aktualnim stavem DB pri kazdem
nacteni - jakmile se podkladovy problem oprav, dalsi refresh uz ho
proste nenajde.
"""
import glob
import json
import os

from flask import jsonify, request

from app import app, current_user, get_conn, has_permission, require_permission
from qa_checks import CHECK_ADDED, CHECK_CATEGORY, run_checks

# bot14, 2026-09-02 - "kontrolni mechanismy na cely system
# konfiguratoru" (Robert pres bot3), bod H: souhrnny report ze
# scripts/qa/run_all.sh (systemd/HTTP/TLS/disk/DB/fronty/zalohy,
# logy, data_code = tenhle modul) - JINY panel nez ziva "QA audit"
# kontrola vyse (ta bezi pri kazdem otevreni Dashboardu nad aktualnim
# stavem DB, tady je to bezici SNAPSHOT z casovace, viz konfigurator-
# qa.timer). qa-reports/ je mimo git (.gitignore), citaji se jen
# soubory generovane merge_reports.py (nikdy user-controlled cesta).
QA_REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qa-reports")


@app.get("/api/admin/qa-audit")
def admin_qa_audit():
    # Robert 2026-08-10 ("budou 2 scripty ktere bude admin spoustet a
    # zastavovat nezavisle") - volitelny filtr ?category=doplnit|opravit,
    # aby admin.html mohl mit dva samostatne panely s vlastnim
    # tlacitkem Spustit, kazdy volajici jen svou podmnozinu kontrol.
    #
    # bot16, 2026-09-29 (Robert pres bot3, "kazdy panel adminu do
    # tabulky roli a prav"): JEDEN endpoint napaji DVA ruzne dashboard
    # panely s DVEMA ruznymi sekcemi (qaBugPanel=dash_qa_bugy vs.
    # qaDataPanel=dash_qa_navrhy) - proto rucni kontrola podle ?category
    # misto jednoho spolecneho @require_permission dekoratoru.
    category = request.args.get("category")
    section = {"opravit": "dash_qa_bugy", "doplnit": "dash_qa_navrhy"}.get(category)
    if not section:
        return jsonify({"error": "Očekávám ?category=opravit nebo doplnit."}), 400
    user = current_user()
    if not user or not user["active"]:
        return jsonify({"error": "Neprihlaseno.", "code": "unauthorized"}), 401
    if not has_permission(user, section, "zobrazit"):
        return jsonify({"error": "Nemate opravneni k teto akci.", "code": "forbidden"}), 403
    only = [k for k, v in CHECK_CATEGORY.items() if v == category] if category in ("doplnit", "opravit") else None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            results = run_checks(cur, only=only)
    finally:
        conn.close()
    total = sum(len(v["rows"]) for v in results.values())
    checks = [
        {
            "key": key,
            "label": v["label"],
            "count": len(v["rows"]),
            "items": [{"id": pid, "name": name, "detail": detail} for pid, name, detail in v["rows"]],
            # Robert 2026-08-11 ("chci aby se logovalo datum přidání
            # každého nového typu kontroly") - viz CHECK_ADDED v
            # qa_checks.py, zpetne dohledano z git historie pro
            # kontroly existujici pred timhle pozadavkem.
            "added": CHECK_ADDED.get(key),
            # bot23 2026-08-18: kdyz tahle konkretni kontrola selhala
            # (viz run_checks), admin.html to muze zobrazit misto tise
            # nuloveho poctu - zbytek panelu (ostatni kontroly) zustava
            # funkcni, viz run_checks() v qa_checks.py.
            **({"error": v["error"]} if "error" in v else {}),
        }
        for key, v in results.items()
    ]
    return jsonify({"total": total, "checks": checks})


# Robert 2026-08-10 ("stisknu opravit a nic... rovnou poslat botovi
# (vytvorit ukol)" -> "pokud admin stiskne opravit, ma se tato chyba
# hned zacit resit, osetrit" -> AskUserQuestion: "označit jako VYSOKÁ
# PRIORITA pro další session", NE automaticka oprava kodu zivym
# systemem) - nalezy BEZ zaznamu v administraci (kodove bugy,
# duplicate_sku, missing_glb_file, orphaned_gallery_items) nemaji
# tlacitko "Opravit" kam otevrit - misto tise kopirovat do schranky
# (Robert: "a nic") se ukladaji sem s priority=1, at je bot v dalsi
# session vidi jako prvni. TASKS.md (git-trackovany rucni backlog) tu
# zamerne NENI cilem zapisu - www-data (Flask) do nej nemuze psat
# (600 root:root jako zbytek repa) a menit opravneni produkcniho
# souboru kvuli tomuhle Robert nechtel (viz AskUserQuestion).
@app.post("/api/admin/qa-audit/tasks")
def admin_qa_audit_report_task():
    # bot16, 2026-09-29: tlacitko "Opravit"/"Doplnit" je uvnitr obou
    # panelu (qaBugPanel/qaDataPanel), takze staci videt JEDEN z nich -
    # viz stejny komentar u admin_qa_audit() vyse.
    user = current_user()
    if not user or not user["active"]:
        return jsonify({"error": "Neprihlaseno.", "code": "unauthorized"}), 401
    if not (has_permission(user, "dash_qa_bugy", "zobrazit") or has_permission(user, "dash_qa_navrhy", "zobrazit")):
        return jsonify({"error": "Nemate opravneni k teto akci.", "code": "forbidden"}), 403
    body = request.get_json(silent=True) or {}
    check_key = (body.get("check_key") or "").strip()[:100]
    finding_key = (body.get("finding_key") or "").strip()[:255]
    label = (body.get("label") or "").strip()[:255]
    detail = (body.get("detail") or "").strip()
    if not check_key or not finding_key or not label or not detail:
        return jsonify({"error": "Chybí povinné údaje nálezu."}), 400
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM qa_reported_tasks WHERE finding_key=%s AND status='open'",
                (finding_key,),
            )
            existing = cur.fetchone()
            if existing:
                return jsonify({"status": "ok", "id": existing["id"], "already_reported": True})
            cur.execute(
                "INSERT INTO qa_reported_tasks (check_key, finding_key, label, detail, priority, created_by) "
                "VALUES (%s,%s,%s,%s,1,%s)",
                (check_key, finding_key, label, detail, user["id"]),
            )
            task_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": task_id, "already_reported": False}), 201


@app.get("/api/admin/qa-audit/tasks")
@require_permission("dash_qa_ukoly", "zobrazit")
def admin_qa_audit_tasks_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, check_key, label, detail, priority, created_at FROM qa_reported_tasks "
                "WHERE status='open' ORDER BY priority DESC, created_at DESC"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"tasks": [
        {"id": r["id"], "check_key": r["check_key"], "label": r["label"], "detail": r["detail"],
         "priority": bool(r["priority"]), "created_at": r["created_at"].isoformat()} for r in rows
    ]})


@app.post("/api/admin/qa-audit/tasks/<int:task_id>/resolve")
@require_permission("dash_qa_ukoly", "zobrazit")
def admin_qa_audit_task_resolve(task_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE qa_reported_tasks SET status='done', resolved_at=NOW() WHERE id=%s AND status='open'",
                (task_id,),
            )
            affected = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if not affected:
        return jsonify({"error": "Úkol nenalezen nebo už je hotový."}), 404
    return jsonify({"status": "ok"})


@app.get("/api/admin/qa-report/latest")
@require_permission("dash_qa_system", "zobrazit")
def admin_qa_report_latest():
    # ?list=1 - jen seznam dostupnych beheu (jmeno + cas), pro pripadny
    # vyber "historie" v adminu, bez nutnosti stahovat kazdy cely JSON.
    if request.args.get("list"):
        files = sorted(glob.glob(os.path.join(QA_REPORTS_DIR, "20*.json")), reverse=True)
        return jsonify({"reports": [os.path.basename(f)[:-5] for f in files]})

    latest_path = os.path.join(QA_REPORTS_DIR, "latest.json")
    if not os.path.isfile(latest_path):
        return jsonify({"error": "Zatím žádný QA report neproběhl.", "code": "no_report_yet"}), 404
    try:
        with open(latest_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return jsonify({"error": f"QA report se nepodařilo přečíst: {e}"}), 500
    return jsonify(data)
