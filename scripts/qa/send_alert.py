#!/usr/bin/env python3
"""
scripts/qa/send_alert.py - kdyz posledni slouceny QA report
(qa-reports/latest.json) obsahuje critical nalez, posle e-mail
Robertovi PRIMO (ne do fronty), bot14 2026-09-02 bod H, zmeneno
2026-09-15 (Robert/bot3, WORKFLOW.md pravidlo 16 - nova vyjimka:
interni notifikace, kde jedinym prijemcem je Robertova vlastni adresa,
jdou rovnou, ne do fronty system_emails).

PUVODNI chovani (do 2026-09-15) bylo zaradit do system_emails jako
pending - to uz NEPLATI, viz WORKFLOW.md pravidlo 16. Prijemce
(`app_settings.support_notify_email`) je dnes overene Robertova vlastni
adresa - kdyby se tohle nastaveni niekdy zmenilo na tretí stranu,
vyjimka uz neplati a je potreba vratit se k pending fronte.

Nekontroluje to `api/qa_checks.py::check_direct_send_email_bypass` -
ten skenuje jen `api/*.py`, ne `scripts/`.

Idempotentni v ramci JEDNOHO reportu (finding_key otisk z critical
nalezu, viz _report_fingerprint) - opakovane spusteni nad stejnym
latest.json neposle duplicitni e-mail, jen kdyz se sada critical
nalezu zmeni.

Volano z scripts/qa/run_all.sh AZ PO merge_reports.py (potrebuje
hotovy qa-reports/latest.json).
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# api/ je o DVE urovne vys nez tenhle soubor (scripts/qa/send_alert.py -> <repo>/api); dřív tu byla jedna úroveň = scripts/api a `from app import send_email` padal (QA služba 2026-09-28)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "api"))

from _common import QA_REPORTS_DIR, load_env  # noqa: E402

STATE_PATH = os.path.join(QA_REPORTS_DIR, "last_alert.json")
NOTIFY_EMAIL_SETTING_KEY = "support_notify_email"  # stejne nastaveni jako product_markups.py/support.py


def _report_fingerprint(critical_findings):
    keys = sorted(f"{f.get('code')}|{f.get('where')}" for f in critical_findings)
    return hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()


def main():
    latest_path = os.path.join(QA_REPORTS_DIR, "latest.json")
    if not os.path.isfile(latest_path):
        print("Zatím žádný qa-reports/latest.json - nic k ohlášení.")
        return 0
    with open(latest_path, encoding="utf-8") as f:
        report = json.load(f)

    critical = [f for f in report.get("findings", []) if f.get("severity") == "critical"]
    if not critical:
        print("Žádné critical nálezy - alert se nezakládá.")
        return 0

    fingerprint = _report_fingerprint(critical)
    prev_fingerprint = None
    if os.path.isfile(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                prev_fingerprint = json.load(f).get("fingerprint")
        except (OSError, ValueError):
            pass
    if fingerprint == prev_fingerprint:
        print("Stejná sada critical nálezů jako minule - alert už byl zařazen, nezakládám duplicitní.")
        return 0

    env = load_env()
    import pymysql  # noqa: E402 - az tady, jen kdyz je skutecne potreba cist DB
    conn = pymysql.connect(
        host=env.get("DB_HOST", "80.211.73.226"), port=int(env.get("DB_PORT", "3306")),
        user=env.get("DB_USER", ""), password=env.get("DB_PASSWORD", ""), database=env.get("DB_NAME", ""),
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key=%s", (NOTIFY_EMAIL_SETTING_KEY,)
            )
            row = cur.fetchone()
            notify_email = row["setting_value"] if row else None
            if not notify_email:
                print(f"Nastavení '{NOTIFY_EMAIL_SETTING_KEY}' není vyplněné - alert nemá komu poslat, jen loguji.")
                return 0

            lines = [f"QA report ({report.get('generated_at')}) má {len(critical)} kritických nálezů:", ""]
            for f in critical[:20]:
                lines.append(f"- [{f.get('suite')}] {f.get('code')}: {f.get('title')} (kde: {f.get('where') or '-'})")
            if len(critical) > 20:
                lines.append(f"... a dalších {len(critical) - 20}")
            lines.append("")
            lines.append("Detail v administraci: Dashboard > QA běhy (systém).")
            body = "\n".join(lines)
    finally:
        conn.close()

    # api/app.py cte DB_* pouze z prostredi (sam .env nenacita) a QA sluzba bezi bez EnvironmentFile - doplnime je z .env, co uz nacetlo load_env()
    for _k, _v in env.items():
        os.environ.setdefault(_k, _v)
    from app import send_email  # noqa: E402 - az tady, jen kdyz je skutecne potreba odeslat
    send_email(notify_email, f"QA report: {len(critical)} kritických nálezů", body)

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"fingerprint": fingerprint, "at": report.get("generated_at")}, f)
    print(f"Odesláno e-mailem {len(critical)} kritických nálezů pro {notify_email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
