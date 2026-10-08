"""
Sdilene jadro pro QA suity (bot14, 2026-09-02, "kontrolni mechanismy na
cely system konfiguratoru" - zadani od Roberta pres bot3, oblast OPS:
health.py/logs.py/run_all.sh + admin panel + timer).

Pevny JSON kontrakt (bot3): kazda suita s --json vypise na stdout JEDEN
JSON objekt:
    {"suite": "health", "ran_at": "2026-09-02T20:55:00+02:00",
     "duration_s": 12.3, "status": "ok|warn|fail",
     "findings": [{"severity": "critical|warning|info", "code": "...",
                   "title": "...", "detail": "...", "where": "...",
                   "fix_hint": "..."}],
     "stats": {...}}
Bez --json lidsky citelny text. Exit kod: 0 ok, 1 warn, 2 fail,
3 skript sam selhal (viz run_suite()/main_wrapper() nize).

READ-ONLY vuci datum (Robert, viz WORKFLOW.md) - get_conn() otevira
spojeni a rovnou spusti `SET SESSION TRANSACTION READ ONLY`, takze
jakykoli omylem napsany INSERT/UPDATE/DELETE selze hlasite misto aby
tise zapsal neco do produkce.
"""
import datetime
import json
import os
import sys
import time
import traceback

import pymysql

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QA_REPORTS_DIR = os.path.join(REPO_ROOT, "qa-reports")
os.makedirs(QA_REPORTS_DIR, exist_ok=True)

SEVERITY_TO_STATUS = {"critical": "fail", "warning": "warn", "info": "ok"}
STATUS_EXIT_CODE = {"ok": 0, "warn": 1, "fail": 2}


def load_env(path=None):
    """Stejna konvence jako scripts/qa_product_audit.py::load_db_config -
    .env ma prednost pred os.environ (produkcni sluzba bezi s .env),
    ale kdyz .env neni citelny (spravny run pod www-data bez prav na
    600 root:root soubor), tise se pouzije jen os.environ (systemd
    EnvironmentFile= uz promenne vlozil pred dropnutim prav)."""
    env = dict(os.environ)
    env_path = path or os.path.join(REPO_ROOT, "api", ".env")
    try:
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    v = v.strip()
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                        v = v[1:-1]
                    env.setdefault(k.strip(), v)
    except PermissionError:
        pass
    return env


def get_conn(env=None):
    """DB spojeni s READ ONLY transakci (Robert: zadny INSERT/UPDATE/
    DELETE z QA skriptu). Volajici stale musi otevrit `with conn.cursor()`
    sam - tady jen navazujeme spojeni a nastavime read-only mod."""
    env = env or load_env()
    conn = pymysql.connect(
        host=env.get("DB_HOST", "80.211.73.226"),
        port=int(env.get("DB_PORT", "3306")),
        user=env.get("DB_USER", ""),
        password=env.get("DB_PASSWORD", ""),
        database=env.get("DB_NAME", ""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
    )
    with conn.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION READ ONLY")
    return conn


def finding(severity, code, title, detail, where=None, fix_hint=None):
    assert severity in ("critical", "warning", "info"), f"neplatna zavaznost: {severity}"
    return {
        "severity": severity, "code": code, "title": title, "detail": detail,
        "where": where, "fix_hint": fix_hint,
    }


def overall_status(findings):
    """critical->fail, warning->warn (bez critical), jinak ok."""
    if any(f["severity"] == "critical" for f in findings):
        return "fail"
    if any(f["severity"] == "warning" for f in findings):
        return "warn"
    return "ok"


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def print_human(suite, findings, stats):
    status = overall_status(findings)
    print(f"=== {suite}: {status.upper()} ({len(findings)} nálezů) ===\n")
    order = {"critical": 0, "warning": 1, "info": 2}
    for f in sorted(findings, key=lambda x: order.get(x["severity"], 9)):
        print(f"[{f['severity'].upper()}] {f['code']} - {f['title']}")
        print(f"  kde: {f.get('where') or '-'}")
        print(f"  detail: {f['detail']}")
        if f.get("fix_hint"):
            print(f"  navrh: {f['fix_hint']}")
        print()
    if stats:
        print("--- stats ---")
        for k, v in stats.items():
            print(f"  {k}: {v}")


def run_suite(suite_name, collect_fn, as_json):
    """collect_fn() -> (findings_list, stats_dict). Chytá VŠECHNY
    vyjimky - skript, ktery sam spadne (napr. DB nedostupna), ma vratit
    exit 3 a JSON s prazdnym findings + chybou v stats, ne tichy
    traceback bez JSONu (run_all.sh ho jinak nemuze slit do souhrnu)."""
    started = time.monotonic()
    ran_at = now_iso()
    try:
        findings, stats = collect_fn()
        status = overall_status(findings)
        duration = round(time.monotonic() - started, 2)
        result = {
            "suite": suite_name, "ran_at": ran_at, "duration_s": duration,
            "status": status, "findings": findings, "stats": stats or {},
        }
        if as_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print_human(suite_name, findings, stats)
        sys.exit(STATUS_EXIT_CODE[status])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 - skript sam selhal, chceme to zachytit vzdy
        duration = round(time.monotonic() - started, 2)
        tb = traceback.format_exc()
        result = {
            "suite": suite_name, "ran_at": ran_at, "duration_s": duration,
            "status": "fail",
            "findings": [finding("critical", "QA_SCRIPT_CRASHED",
                                  f"Skript {suite_name} sám selhal", f"{e!r}\n{tb}")],
            "stats": {},
        }
        if as_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"CHYBA: {suite_name} selhal: {e}\n{tb}", file=sys.stderr)
        sys.exit(3)


def ram_watchdog_alert_active():
    return os.path.exists("/run/ram-watchdog-alert")
