#!/usr/bin/env python3
"""
QA audit produktovych detailu - bot4, 2026-08-09.

Robert: "nejaky scriptem hlidej aby nic nechybelo na detailech produktu,
vzdyt tam porad neco vypadavy nebo co" - navazuje primo na realny bug
nalezeny ve stejne konverzaci (76 profilu melo v popisu "Standardni delka
tyce 6000 mm (6 m)", i kdyz logiman.cz je prodava jako 3m useky - viz
oprava v backups/profile_description_length_fix_20260809.json).

Nasledne (Robert, stejny den): "na dashboardu admina mi udelej panel, kde
uvidim vsechny tyto chyby/odchylky" - kontroly jsou proto od
api/qa_checks.py (sdileny modul), tenhle skript je jen CLI obal nad nim
pro rucni/cron spousteni. Admin panel viz /api/admin/qa-audit
(api/qa_audit.py) + webapp/admin.html zalozka Dashboard.

Robert 2026-08-10 ("napříč naším celým kódem s nedokonalosti chybějící
prvky... chytrý skript který by nám toto na pozadí neustále
kontroloval") - kontroly rozsireny za hranice produktovych dat (admin
UI, kategorie, homepage mozaika, fotobanka), nazev souboru/skriptu
zustava kvuli existujicim odkazum (viz komentare vyse), obsah uz je
sirsi nez jen "produkty".

Pouziti:
  cd /opt/konfigurator && api/venv/bin/python3 scripts/qa_product_audit.py
  api/venv/bin/python3 scripts/qa_product_audit.py --only missing_price,missing_image

Vystup: textovy report na stdout, groupovany podle kontroly, s poctem a
prvnimi N nalezy (--limit, vychozi 20 na kontrolu, aby report zustal
citelny i kdyz je nejaka kontrola siroce rozbita).

--json (bot14, 2026-09-02, "kontrolni mechanismy na cely system
konfiguratoru" - spolecny QA ramec, viz scripts/qa/README.md): misto
puvodniho surveho {key: {label, rows}} tvaru ted vypisuje JEDEN JSON
objekt podle pevneho kontraktu sdileneho se scripts/qa/health.py a
logs.py ({"suite":"data_code", "ran_at":..., "duration_s":...,
"status":"ok|warn|fail", "findings":[...], "stats":{...}}) - suite
"data_code" v scripts/qa/run_all.sh agregatoru. Zadny predchozi
konzument stareho tvaru neexistoval (konfigurator-qa-audit.service bezi
bez --json vubec), takze zmena tvaru je bezpecna.
"""
import argparse
import datetime
import json
import os
import sys
import time

import pymysql

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "api"))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "qa"))

from qa_checks import CHECKS, CHECK_CATEGORY, run_checks  # noqa: E402
from _common import finding, overall_status, STATUS_EXIT_CODE  # noqa: E402

# "opravit" (vzor v kodu, skutecny bug) je zavaznejsi nez "doplnit"
# (chybejici udaj v datech) - stovky "doplnit" nalezu napric katalogem
# by jinak zaplavily report jako "warning", i kdyz jde o postupne
# doplnovana data, ne provozni riziko.
_CATEGORY_TO_SEVERITY = {"opravit": "warning", "doplnit": "info"}


def load_db_config():
    # Stejna konvence jako api/app.py (DB_HOST/DB_USER/... z .env, s
    # fallbackem na hodnoty v kodu) - .env ma prednost, protoze produkcni
    # sluzba bezi s .env (viz api/.env), ne s hardcoded fallbackem.
    #
    # Robert 2026-08-10 ("min to che 2x denne") - skript ted bezi i jako
    # systemd sluzba pod www-data (konfigurator-qa-audit.service).
    # api/.env je 600 root:root (stejne opravneni jako gunicorn service),
    # takze www-data ho neprecte primo - systemd ale EnvironmentFile=
    # cte JAKO ROOT pred dropnutim prav a promenne vlozi do os.environ
    # procesu, tam uz jsou pristupne. os.environ ma proto prednost;
    # primy pokus o cteni souboru je jen fallback pro rucni spusteni
    # (root/vlastnik) a tise selze (PermissionError), kdyz nejde cist.
    env = dict(os.environ)
    env_path = os.path.join(REPO_ROOT, "api", ".env")
    try:
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    env.setdefault(k.strip(), v.strip())
    except PermissionError:
        pass
    return {
        "host": env.get("DB_HOST", "80.211.73.226"),
        "port": int(env.get("DB_PORT", "3306")),
        "user": env.get("DB_USER", "t0vgm99ew1"),
        "password": env.get("DB_PASSWORD", "Vertical_001@"),
        "database": env.get("DB_NAME", "nrmmhhq65p"),
    }


def get_conn():
    cfg = load_db_config()
    conn = pymysql.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["password"],
        database=cfg["database"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )
    # READ-ONLY (spolecny QA ramec, bot3 2026-09-02) - kontrola nesmi
    # nic zapsat, jen cist a hlasit.
    with conn.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION READ ONLY")
    return conn


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="čárkou oddělený seznam kontrol (viz --list)")
    parser.add_argument("--list", action="store_true", help="vypsat dostupné kontroly a skončit")
    parser.add_argument("--limit", type=int, default=20, help="max. řádků na kontrolu ve výpisu (výchozí 20)")
    parser.add_argument("--json", action="store_true", help="strojově čitelný výstup podle qa/_common.py kontraktu (suite=data_code)")
    args = parser.parse_args()

    if args.list:
        for key, (label, _) in CHECKS.items():
            print(f"{key}: {label}")
        return

    selected = args.only.split(",") if args.only else None
    if selected:
        unknown = [k for k in selected if k not in CHECKS]
        if unknown:
            print(f"Neznámá kontrola: {', '.join(unknown)} (viz --list)", file=sys.stderr)
            sys.exit(2)

    started = time.monotonic()
    ran_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            results = run_checks(cur, only=selected)
    finally:
        conn.close()

    if args.json:
        findings = []
        stats = {}
        for key, v in results.items():
            rows = v["rows"]
            stats[key] = len(rows)
            severity = _CATEGORY_TO_SEVERITY.get(CHECK_CATEGORY.get(key), "warning")
            for pid, name, detail in rows:
                findings.append(finding(severity, f"DATA_{key.upper()}", v["label"], detail, where=f"#{pid} {name}"))
        status = overall_status(findings)
        result = {
            "suite": "data_code", "ran_at": ran_at, "duration_s": round(time.monotonic() - started, 2),
            "status": status, "findings": findings, "stats": stats,
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(STATUS_EXIT_CODE[status])

    total_issues = sum(len(v["rows"]) for v in results.values())
    print(f"=== QA audit (produkty, kategorie, homepage, admin UI, fotobanka) - {total_issues} nálezů celkem ===\n")
    for key, v in results.items():
        rows = v["rows"]
        status = "OK" if not rows else f"{len(rows)} nálezů"
        print(f"--- {v['label']} [{key}]: {status} ---")
        for pid, name, detail in rows[:args.limit]:
            print(f"  #{pid}  {name}  -  {detail}")
        if len(rows) > args.limit:
            print(f"  ... a dalších {len(rows) - args.limit} (viz --json pro plný seznam)")
        print()


if __name__ == "__main__":
    main()
