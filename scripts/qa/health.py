#!/usr/bin/env python3
"""
scripts/qa/health.py - jednorazovy snimek zdravi systemu (bot14,
2026-09-02, "kontrolni mechanismy na cely system konfiguratoru",
oblast OPS/health, zadani Roberta pres bot3).

Kontroluje BEZOVE veci, ktere qa_checks.py (data/kod v DB+repu) neresi:
systemd sluzby/timery, HTTP dostupnost verejnych stranek, TLS
certifikat, disk, DB provoz, fronty (system_emails/approvals/turntable
uklid), zaloha, gunicorn workery, nginx access log 5xx podil.

Pouziti:
  api/venv/bin/python3 scripts/qa/health.py            # lidsky text
  api/venv/bin/python3 scripts/qa/health.py --json      # JSON kontrakt (viz _common.py)

READ-ONLY vuci DB (SET SESSION TRANSACTION READ ONLY), zadne zapisy
nikam, zadne testovaci objednavky/leady - jen cteni + HTTP GET na
verejne (bezstavove) stranky.
"""
import argparse
import datetime
import glob
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import finding, get_conn, load_env, run_suite  # noqa: E402

TIMEOUT = 8


def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:  # noqa: BLE001
        return -1, "", str(e)


# --- systemd -----------------------------------------------------------

CORE_SERVICES = ["konfigurator.service", "nginx.service"]


def _check_ram_watchdog(findings):
    # bot3 živě ověřil (2026-09-02): na tomhle Contabo VPS
    # ram-watchdog.service ani /usr/local/sbin/ram-watchdog.sh vůbec
    # NEEXISTUJÍ - SERVER_RAM_WATCHDOG.md popisuje jiný (starší,
    # VerticalStocks 80.211.210.103) server. Neplést s "služba neběží"
    # (critical) - tohle je "nikdy nenasazeno na tomhle stroji"
    # (warning, nasazení je Robertovo rozhodnutí, ne bug). Zaroven
    # /run/ram-watchdog-alert soubor logicky nikdy nevznikne, takze
    # kontrola v RAM_alert_active() (_common.py) nikoho nechrani.
    code, _, _ = _run(["systemctl", "cat", "ram-watchdog.service"])
    if code != 0:
        findings.append(finding(
            "warning", "HEALTH_RAM_WATCHDOG_NOT_DEPLOYED",
            "ram-watchdog.service není na tomto serveru nasazený",
            "SERVER_RAM_WATCHDOG.md popisuje jiný (VerticalStocks) VPS - na tomhle stroji jednotka ani "
            "/usr/local/sbin/ram-watchdog.sh neexistují, /run/ram-watchdog-alert proto nikdy nevznikne a "
            "nic nechrání proti paralelnímu RAM náběhu více botů",
            where="ram-watchdog.service",
            fix_hint="nasazení je na Robertovi/koordinaci botů, viz SERVER_RAM_WATCHDOG.md pro originální skript",
        ))


def check_systemd(findings, stats):
    _check_ram_watchdog(findings)
    for svc in CORE_SERVICES:
        code, out, err = _run(["systemctl", "is-active", svc])
        active = out.strip() == "active"
        if not active:
            findings.append(finding(
                "critical", "HEALTH_SERVICE_DOWN", f"Služba {svc} neběží",
                f"systemctl is-active vrátil '{out.strip() or err.strip()}'", where=svc,
                fix_hint=f"systemctl status {svc}; systemctl restart {svc}",
            ))
            continue
        _, show_out, _ = _run(["systemctl", "show", svc, "-p", "NRestarts,ActiveEnterTimestamp"])
        vals = dict(line.split("=", 1) for line in show_out.strip().splitlines() if "=" in line)
        nrestarts = int(vals.get("NRestarts", "0") or 0)
        stats[f"{svc}_nrestarts"] = nrestarts
        stats[f"{svc}_since"] = vals.get("ActiveEnterTimestamp", "")
        if nrestarts > 3:
            findings.append(finding(
                "warning", "HEALTH_SERVICE_FLAPPING", f"Služba {svc} se opakovaně restartuje",
                f"NRestarts={nrestarts} od posledního bootu jednotky", where=svc,
                fix_hint="zkontroluj journalctl -u " + svc + " -n 200 pro důvod restartů",
            ))

    # DB server (managed remote MySQL, DB_HOST z .env) - neni systemd
    # jednotka na tomhle stroji, konektivita se overuje v check_db() nize.

    # Konfigurator-*.timer - posledni beh Result=success a ne starsi
    # nez 2x interval. bot3 opravil (2026-09-02, zivy test): interval
    # se NESMI hadat/hardcodovat (puvodni verze mela spatny odhad pro
    # triage-auto-check a nahlasila falesny poplach) - odvozuje se
    # PRIMO z jednotky (NextElapseUSecRealtime - LastTriggerUSec).
    # Hlasi se JEN kdyz: (a) dalsi planovany beh je uz v minulosti
    # (timer se nejak "zasekl"/nespustil se), nebo (b) posledni beh je
    # starsi nez 2x takhle zjisteny interval.
    code, out, err = _run(["systemctl", "list-timers", "--all", "--no-legend", "konfigurator-*.timer"])
    seen = set()
    now = datetime.datetime.now().astimezone()
    for line in out.strip().splitlines():
        m = re.search(r"(konfigurator-[\w-]+\.timer)", line)
        if not m:
            continue
        timer = m.group(1)
        seen.add(timer)
        svc = timer.replace(".timer", ".service")
        _, show_out, _ = _run(["systemctl", "show", svc, "-p", "Result,ActiveState"])
        vals = dict(l.split("=", 1) for l in show_out.strip().splitlines() if "=" in l)
        result = vals.get("Result", "")
        if result not in ("success", "") and vals.get("ActiveState") != "activating":
            _, tail_out, _ = _run(["journalctl", "-u", svc, "-n", "30", "--no-pager"])
            if "name resolution" in tail_out:
                # bot3 zivy overil (2026-09-02): overit, jestli DNS
                # selhani neni SYSTEMOVY problem resolveru, ne jen
                # jednorazova blika tohohle timeru - `journalctl
                # --since -14d | grep -c 'name resolution'` na CELEM
                # VPS ukazalo 24 vyskytu, ale VSECHNY krome jednoho
                # patrily cizimu projektu (radio-stream checker na
                # sdilenem stroji), pro TENHLE konkretni timer to bylo
                # izolovane 1x za 14 dni - proto NEJDE o systemovy
                # resolver problem, jen prechodny blip.
                _, own_dns_fails, _ = _run(["journalctl", "-u", svc, "--since", "-14d"])
                # Distinct INCIDENTY (casova znacka na zacatku radku), ne
                # holy pocet vyskytu retezce - jeden traceback muze
                # zminit "name resolution" 2x (puvodni socket.gaierror +
                # obalujici URLError na stejnem radku/case), coz by jinak
                # falesne vypadalo jako 2 ruzne vypadky.
                incident_timestamps = {
                    line[:15] for line in own_dns_fails.splitlines() if "name resolution" in line
                }
                own_count = len(incident_timestamps)
                findings.append(finding(
                    "warning", "HEALTH_TIMER_DNS_FAILURE", f"Poslední běh {svc} selhal na DNS (name resolution)",
                    f"Result={result}, za 14 dní {own_count} odlišný(ch) výskyt(ů) v logu TÉTO jednotky "
                    f"({'izolovaný výpadek' if own_count <= 1 else 'opakuje se, možný systémový problém resolveru'})",
                    where=svc,
                    fix_hint="přidat retry (2-3x s odstupem) přímo do skriptu, nebo "
                             "Restart=on-failure + RestartSec=10min + StartLimitIntervalSec do .service jednotky",
                ))
            else:
                findings.append(finding(
                    "warning", "HEALTH_TIMER_LAST_RUN_FAILED", f"Poslední běh {svc} neskončil úspěchem",
                    f"Result={result}", where=svc,
                    fix_hint=f"journalctl -u {svc} -n 100",
                ))

        _, timer_show, _ = _run(["systemctl", "show", timer, "-p", "LastTriggerUSec,NextElapseUSecRealtime"])
        tvals = dict(l.split("=", 1) for l in timer_show.strip().splitlines() if "=" in l)
        last_raw = tvals.get("LastTriggerUSec", "")
        next_raw = tvals.get("NextElapseUSecRealtime", "")

        def _parse_ts(raw):
            if not raw or raw in ("n/a", "0"):
                return None
            try:
                return datetime.datetime.strptime(raw, "%a %Y-%m-%d %H:%M:%S %Z").astimezone()
            except ValueError:
                return None

        last_dt = _parse_ts(last_raw)
        next_dt = _parse_ts(next_raw)
        if next_dt and next_dt < now:
            findings.append(finding(
                "warning", "HEALTH_TIMER_NEXT_ELAPSE_IN_PAST", f"{timer} má naplánovaný běh v minulosti",
                f"NextElapseUSecRealtime={next_raw} (systemd ho zjevně nespustil)",
                where=timer, fix_hint=f"systemctl status {timer}; systemctl restart {timer}",
            ))
        elif last_dt and next_dt:
            interval_s = (next_dt - last_dt).total_seconds()
            if interval_s > 0:
                age_s = (now - last_dt).total_seconds()
                if age_s > 2 * interval_s:
                    findings.append(finding(
                        "warning", "HEALTH_TIMER_STALE", f"{timer} neběžel dlouho vzhledem ke svému rozvrhu",
                        f"poslední běh {last_raw} (~{age_s / 3600:.1f} h zpět), odvozený interval "
                        f"~{interval_s / 3600:.2f} h (next_elapse − last_trigger)",
                        where=timer, fix_hint=f"systemctl status {svc}; journalctl -u {svc} -n 50",
                    ))
    stats["timers_checked"] = len(seen)


# --- HTTP ---------------------------------------------------------------

PUBLIC_PATHS = ["/", "/robots.txt", "/sitemap.xml", "/scene.html", "/kontakt.html", "/realizace.html"]


def _http_get(url, timeout=TIMEOUT, allow_redirects=True):
    req = urllib.request.Request(url, headers={"User-Agent": "konfigurator-qa-health/1"})
    started = time.monotonic()
    try:
        opener = urllib.request.build_opener()
        if not allow_redirects:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            opener = urllib.request.build_opener(NoRedirect)
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, len(body), round(time.monotonic() - started, 3), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, 0, round(time.monotonic() - started, 3), dict(e.headers or {})
    except Exception as e:  # noqa: BLE001
        return None, 0, round(time.monotonic() - started, 3), str(e)


def check_http(findings, stats):
    base_https = "https://autovestavby.logiman.cz"
    base_ip = "http://75.119.132.164:8090"

    # /api/health pres unix socket primo (obejde nginx) i pres verejnou domenu.
    sock_path = "/opt/konfigurator/api/konfigurator.sock"
    if os.path.exists(sock_path):
        code, out, err = _run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                                "--unix-socket", sock_path, "http://localhost/api/health"], timeout=TIMEOUT)
        if out.strip() != "200":
            findings.append(finding(
                "critical", "HEALTH_API_SOCKET_DOWN", "/api/health přes unix socket neodpovídá 200",
                f"HTTP {out.strip() or err.strip()}", where=sock_path,
                fix_hint="systemctl status konfigurator.service; journalctl -u konfigurator -n 100",
            ))
    else:
        findings.append(finding("critical", "HEALTH_SOCKET_MISSING", "Gunicorn unix socket neexistuje",
                                 sock_path, where=sock_path, fix_hint="systemctl restart konfigurator.service"))

    status, size, dur, headers = _http_get(f"{base_https}/api/health")
    stats["api_health_https_status"] = status
    stats["api_health_https_ms"] = round(dur * 1000)
    if status != 200:
        findings.append(finding("critical", "HEALTH_API_HTTPS_DOWN", "/api/health přes https://autovestavby.logiman.cz neodpovídá 200",
                                 f"status={status}", where=f"{base_https}/api/health"))

    for path in PUBLIC_PATHS:
        status, size, dur, headers = _http_get(f"{base_https}{path}")
        stats[f"page{path.replace('/', '_') or '_root'}_status"] = status
        stats[f"page{path.replace('/', '_') or '_root'}_ms"] = round(dur * 1000)
        stats[f"page{path.replace('/', '_') or '_root'}_bytes"] = size
        if status != 200:
            findings.append(finding(
                "critical" if path in ("/", "/scene.html") else "warning",
                "HEALTH_PAGE_NOT_200", f"{path} nevrací 200", f"status={status}",
                where=f"{base_https}{path}",
            ))
        elif dur > 3:
            findings.append(finding("warning", "HEALTH_PAGE_SLOW", f"{path} odpovídá pomalu",
                                     f"{dur:.2f} s", where=f"{base_https}{path}"))

    # 1 kategorie + 1 aktivni produkt (dynamicky z DB, ne natvrdo)
    try:
        env = load_env()
        conn = get_conn(env)
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM content_categories WHERE is_visible=1 AND slug IS NOT NULL LIMIT 1")
            cat = cur.fetchone()
            cur.execute("SELECT slug FROM shop_products WHERE active=1 AND is_archived=0 AND slug IS NOT NULL LIMIT 1")
            prod = cur.fetchone()
        conn.close()
        for label, row, rel in (("kategorie", cat, "kategorie"), ("produkt", prod, "produkt")):
            if not row:
                continue
            status, size, dur, _ = _http_get(f"{base_https}/{rel}/{row['slug']}")
            stats[f"sample_{label}_status"] = status
            if status != 200:
                findings.append(finding("critical", "HEALTH_SAMPLE_PAGE_DOWN", f"Ukázková {label} stránka nevrací 200",
                                         f"/{rel}/{row['slug']} -> {status}", where=f"{base_https}/{rel}/{row['slug']}"))
    except Exception as e:  # noqa: BLE001
        findings.append(finding("warning", "HEALTH_SAMPLE_PAGE_CHECK_FAILED", "Nepodařilo se ověřit ukázkovou kategorii/produkt", str(e)))

    # redirect http->https a www varianta
    status, _, _, headers = _http_get("http://autovestavby.logiman.cz/", allow_redirects=False)
    loc = headers.get("Location", "") if isinstance(headers, dict) else ""
    if status not in (301, 302, 308) or not loc.startswith("https://"):
        findings.append(finding("warning", "HEALTH_NO_HTTPS_REDIRECT", "http://autovestavby.logiman.cz/ nepřesměrovává na https",
                                 f"status={status} Location={loc}", where="http://autovestavby.logiman.cz/"))
    status_www, _, _, headers_www = _http_get("https://www.autovestavby.logiman.cz/", allow_redirects=True)
    stats["www_variant_status"] = status_www
    if status_www != 200:
        findings.append(finding("info", "HEALTH_WWW_VARIANT", "https://www.autovestavby.logiman.cz/ nevrací přímo 200",
                                 f"status={status_www}", where="https://www.autovestavby.logiman.cz/"))

    # IP vhost
    status, _, _, _ = _http_get(f"{base_ip}/api/health")
    stats["ip_vhost_status"] = status
    if status != 200:
        findings.append(finding("warning", "HEALTH_IP_VHOST_DOWN", "IP vhost (75.119.132.164:8090) neodpovídá",
                                 f"status={status}", where=base_ip))

    check_soft_404(findings, stats, base_https)
    check_backup_file_block(findings, stats, base_https)


def check_backup_file_block(findings, stats, base_https):
    # Regresni kontrola (bot6/bot3, 2026-09-02, zivy nalez): webapp/*.bak
    # zalohy byly verejne stahnutelne (uz smazane, ale muzou vzniknout
    # znovu) - nginx ted ma "location ~* \.(bak|orig|save|swp|old)$
    # { return 404; }" v obou vhostech. Testovaci cesta neexistuje, jde
    # o overeni, ze SAMOTNA pripona je blokovana bez ohledu na to, jestli
    # soubor fyzicky existuje.
    path = "/qa-health-check-nonexistent-2026.html.bak"
    status, size, dur, headers = _http_get(f"{base_https}{path}")
    stats["backup_file_block_status"] = status
    if status != 404:
        findings.append(finding(
            "critical", "HEALTH_BACKUP_FILE_NOT_BLOCKED", "Přípony záložních souborů (.bak/.orig/.save/.swp/.old) nejsou blokované",
            f"{base_https}{path} -> status={status} (očekáváno 404) - pokud v budoucnu vznikne "
            f"webapp/*.bak (např. omylem vytvořená editorem), byl by veřejně stažitelný",
            where=f"{base_https}{path}",
            fix_hint="nginx: location ~* \\.(bak|orig|save|swp|old)$ { return 404; } v obou vhostech "
                     "(viz AGENTS_LOG.md, oprava 2026-09-02)",
        ))


def check_soft_404(findings, stats, base_https):
    # Regresni kontrola (bot3, 2026-09-02, zivy nalez): nginx "location /"
    # fallback drive tise servíroval 200+homepage pro JAKOUKOLI neexistujici
    # cestu (soft-404, Google to vidi jako duplicitni obsah) - opraveno na
    # skutecne 404 + webapp/404.html. Deterministicka (ne nahodna) cesta,
    # at je test opakovatelny/diffovatelny mezi behy.
    path = "/qa-health-check-nonexistent-path-2026/"
    status, size, dur, headers = _http_get(f"{base_https}{path}")
    stats["soft_404_check_status"] = status
    if status != 404:
        findings.append(finding(
            "critical", "HEALTH_SOFT_404", "Neexistující cesta nevrací 404 (soft-404)",
            f"{base_https}{path} -> status={status} (očekáváno 404) - Google to indexuje jako duplicitní obsah, "
            f"smazané stránky nikdy nezmizí z indexu",
            where=f"{base_https}{path}",
            fix_hint="nginx location / musí mít 'try_files $uri $uri/ =404;' + 'error_page 404 /404.html;', "
                     "ne fallback na /index.html (viz AGENTS_LOG.md, oprava 2026-09-02)",
        ))


# --- TLS ------------------------------------------------------------------

def check_tls(findings, stats):
    host = "autovestavby.logiman.cz"
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        not_after = datetime.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=datetime.timezone.utc)
        days_left = (not_after - datetime.datetime.now(datetime.timezone.utc)).days
        stats["tls_days_to_expiry"] = days_left
        if days_left < 7:
            findings.append(finding("critical", "HEALTH_TLS_EXPIRING", "TLS certifikát brzy vyprší",
                                     f"{days_left} dní do expirace ({not_after.isoformat()})", where=host,
                                     fix_hint="certbot renew --cert-name autovestavby.logiman.cz"))
        elif days_left < 14:
            findings.append(finding("warning", "HEALTH_TLS_EXPIRING", "TLS certifikát vyprší za méně než 14 dní",
                                     f"{days_left} dní do expirace ({not_after.isoformat()})", where=host))
    except Exception as e:  # noqa: BLE001
        findings.append(finding("critical", "HEALTH_TLS_CHECK_FAILED", "Nepodařilo se ověřit TLS certifikát", str(e), where=host))

    code, out, err = _run(["which", "certbot"])
    if code != 0:
        findings.append(finding("warning", "HEALTH_CERTBOT_MISSING", "certbot binárka nenalezena", err or out))
    else:
        code2, out2, err2 = _run(["systemctl", "is-enabled", "certbot.timer"])
        if code2 != 0:
            findings.append(finding("info", "HEALTH_CERTBOT_TIMER", "certbot.timer není enabled (obnova certů může chybět)", out2 or err2))


# --- Disk -------------------------------------------------------------------

def check_disk(findings, stats):
    for path in ("/", "/opt"):
        try:
            st = os.statvfs(path)
            total = st.f_frsize * st.f_blocks
            free = st.f_frsize * st.f_bavail
            used_pct = round((1 - free / total) * 100, 1) if total else 0
            stats[f"disk_used_pct{path.replace('/', '_root') if path == '/' else path.replace('/', '_')}"] = used_pct
            inode_used_pct = round((1 - st.f_favail / st.f_files) * 100, 1) if st.f_files else 0
            if used_pct > 80:
                findings.append(finding("warning", "HEALTH_DISK_FULL", f"Disk {path} nad 80 % využití",
                                         f"{used_pct} % využito", where=path,
                                         fix_hint="df -h; najít a smazat/přesunout velké staré soubory"))
            if inode_used_pct > 80:
                findings.append(finding("warning", "HEALTH_INODES_FULL", f"Disk {path} nad 80 % využitých inodů",
                                         f"{inode_used_pct} % inodů", where=path))
        except OSError as e:
            findings.append(finding("warning", "HEALTH_DISK_CHECK_FAILED", f"Nepodařilo se zjistit využití disku {path}", str(e)))

    def du(path):
        code, out, err = _run(["du", "-sk", path], timeout=60)
        if code == 0 and out.strip():
            return int(out.split()[0]) * 1024
        return None

    for name, path in (
        ("content_files_kb", "/opt/konfigurator/webapp/content-files"),
        ("turntable_frames_kb", "/opt/konfigurator/webapp/content-files/turntable-frames"),
        ("nginx_logs_kb", "/var/log/nginx"),
    ):
        size = du(path)
        if size is not None:
            stats[name] = size // 1024


# --- DB ----------------------------------------------------------------------

def check_db(findings, stats):
    env = load_env()
    try:
        conn = get_conn(env)
    except Exception as e:  # noqa: BLE001
        findings.append(finding("critical", "HEALTH_DB_DOWN", "Nelze se připojit k databázi", str(e), where=env.get("DB_HOST")))
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW GLOBAL STATUS WHERE Variable_name IN "
                        "('Threads_connected','Uptime','Slow_queries','Aborted_connects')")
            for r in cur.fetchall():
                stats[f"db_{r['Variable_name']}"] = r["Value"]

            cur.execute(
                "SELECT table_name AS tbl_name, ROUND((data_length+index_length)/1024/1024,1) AS mb "
                "FROM information_schema.tables WHERE table_schema=%s "
                "ORDER BY (data_length+index_length) DESC LIMIT 10",
                (env.get("DB_NAME"),),
            )
            stats["db_top_tables_mb"] = [{"table": r["tbl_name"], "mb": float(r["mb"] or 0)} for r in cur.fetchall()]

            cur.execute(
                "SELECT t.table_name AS tbl_name FROM information_schema.tables t "
                "LEFT JOIN information_schema.table_constraints tc "
                "  ON tc.table_schema=t.table_schema AND tc.table_name=t.table_name AND tc.constraint_type='PRIMARY KEY' "
                "WHERE t.table_schema=%s AND t.table_type='BASE TABLE' AND tc.constraint_name IS NULL",
                (env.get("DB_NAME"),),
            )
            no_pk = [r["tbl_name"] for r in cur.fetchall()]
            if no_pk:
                findings.append(finding("warning", "HEALTH_TABLE_NO_PK", "Tabulky bez PRIMARY KEY",
                                         ", ".join(no_pk), where=env.get("DB_NAME"),
                                         fix_hint="zvážit doplnění PK (replikace/nástroje na ně obvykle spoléhají)"))
            stats["db_tables_without_pk"] = no_pk
        return conn
    except Exception as e:  # noqa: BLE001
        findings.append(finding("warning", "HEALTH_DB_STATUS_CHECK_FAILED", "SHOW GLOBAL STATUS / metadata dotaz selhal", str(e)))
        return conn


# --- fronty ---------------------------------------------------------------

def check_queues(findings, stats, conn):
    if conn is None:
        return
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c, MIN(created_at) AS oldest FROM system_emails WHERE status='pending'")
        r = cur.fetchone()
        stats["system_emails_pending"] = r["c"]
        if r["c"] and r["oldest"]:
            age_h = (datetime.datetime.now() - r["oldest"]).total_seconds() / 3600
            stats["system_emails_pending_oldest_h"] = round(age_h, 1)
            if age_h > 24:
                findings.append(finding("warning", "HEALTH_EMAIL_QUEUE_STALE", "Nejstarší pending system_emails čeká déle než 24 h",
                                         f"{age_h:.1f} h, {r['c']} celkem pending", where="system_emails",
                                         fix_hint="admin > Emaily odchozí/frontu zkontrolovat a schválit/zamítnout"))
        cur.execute("SELECT COUNT(*) AS c FROM system_emails WHERE status='failed' AND created_at > NOW() - INTERVAL 24 HOUR")
        r2 = cur.fetchone()
        stats["system_emails_failed_24h"] = r2["c"]
        if r2["c"]:
            findings.append(finding("warning", "HEALTH_EMAIL_FAILED", "Systémové e-maily selhaly za posledních 24 h",
                                     f"{r2['c']} selhaných", where="system_emails"))

        approvals_total = 0
        for label, sql in (
            ("purchase_orders", "SELECT COUNT(*) AS c FROM shop_purchase_orders WHERE status='navrh' AND created_at < NOW() - INTERVAL 7 DAY"),
            ("orders", "SELECT COUNT(*) AS c FROM shop_orders WHERE status='nova' AND created_at < NOW() - INTERVAL 7 DAY"),
            ("quotes", "SELECT COUNT(*) AS c FROM crm_quotes WHERE approval_status='ceka_schvaleni' AND created_at < NOW() - INTERVAL 7 DAY"),
            ("documents", "SELECT COUNT(*) AS c FROM shop_documents WHERE approval_status='ceka_schvaleni' AND created_at < NOW() - INTERVAL 7 DAY"),
        ):
            try:
                cur.execute(sql)
                c = cur.fetchone()["c"]
                stats[f"approvals_stale_{label}"] = c
                approvals_total += c
            except Exception:  # noqa: BLE001 - tabulka/sloupec se muze lisit, netrestat cely health check
                pass
        if approvals_total:
            findings.append(finding("warning", "HEALTH_APPROVALS_STALE", "Položky čekající na schválení déle než 7 dní",
                                     f"celkem {approvals_total} napříč purchase_orders/orders/quotes/documents",
                                     where="approvals", fix_hint="admin dashboard > Ke schválení"))

        # product_turntable_frames uklid - schema-tolerantne (deactivated_at
        # zatim v DB neni, viz bot3 zadani/AGENTS_LOG.md).
        try:
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.columns "
                "WHERE table_schema=DATABASE() AND table_name='product_turntable_frames' AND column_name='deactivated_at'"
            )
            has_col = cur.fetchone()["c"] > 0
            cur.execute("SELECT COUNT(*) AS c FROM product_turntable_frames WHERE is_active=0")
            inactive_c = cur.fetchone()["c"]
            stats["turntable_frames_inactive"] = inactive_c
            if has_col:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM product_turntable_frames "
                    "WHERE is_active=0 AND deactivated_at < NOW() - INTERVAL 24 HOUR"
                )
                stale = cur.fetchone()["c"]
                if stale:
                    findings.append(finding("warning", "HEALTH_TURNTABLE_CLEANUP_STALE",
                                             "Neaktivní snímky otočného náhledu nejsou smazané přes grace period",
                                             f"{stale} řádků is_active=0 starších než 24 h", where="product_turntable_frames"))
            elif inactive_c:
                findings.append(finding("info", "HEALTH_TURNTABLE_NO_DEACTIVATED_AT",
                                         "product_turntable_frames.deactivated_at zatím neexistuje - úklid nelze časově ověřit",
                                         f"{inactive_c} řádků is_active=0 bez informace, odkdy",
                                         where="product_turntable_frames",
                                         fix_hint="migrace deactivated_at čeká na Roberta (viz AGENTS_LOG.md)"))
        except Exception:  # noqa: BLE001
            pass


# --- zaloha -----------------------------------------------------------------

def check_backup(findings, stats):
    pattern = "/opt/konfigurator/private-files/shared-drive/zaloha_*.tar.gz"
    files = glob.glob(pattern)
    if not files:
        findings.append(finding("critical", "HEALTH_NO_BACKUP_FOUND", "Nenalezena žádná záloha (daily_backup.py)",
                                 f"vzor {pattern} nic nenašel", where=pattern,
                                 fix_hint="systemctl status konfigurator-daily-backup.service; ruční spuštění pro ověření"))
        return
    latest = max(files, key=os.path.getmtime)
    age_h = (time.time() - os.path.getmtime(latest)) / 3600
    stats["backup_latest_file"] = os.path.basename(latest)
    stats["backup_latest_age_h"] = round(age_h, 1)
    stats["backup_count"] = len(files)
    if age_h > 26:
        findings.append(finding("warning", "HEALTH_BACKUP_STALE", "Poslední záloha je starší než 26 h",
                                 f"{os.path.basename(latest)}, {age_h:.1f} h stará", where=latest,
                                 fix_hint="systemctl status konfigurator-daily-backup.timer/.service"))


# --- gunicorn -----------------------------------------------------------------

def check_gunicorn(findings, stats):
    # POZOR: sdileny VPS ma gunicorn i pro sesterske projekty
    # (domeny/vybaveni-uzitkovych-vozidel/no-sim) - "app:app" samo o
    # sobe je matchne vsechny. Filtrovat konkretne na konfigurator.sock.
    code, out, err = _run(["pgrep", "-af", "gunicorn.*konfigurator.sock"])
    if code != 0 or not out.strip():
        findings.append(finding("critical", "HEALTH_GUNICORN_NO_WORKERS", "Žádný gunicorn worker proces nenalezen", err or out))
        return
    pids = [line.split()[0] for line in out.strip().splitlines()]
    stats["gunicorn_processes"] = len(pids)
    max_rss_mb = 0
    for pid in pids:
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        kb = int(line.split()[1])
                        max_rss_mb = max(max_rss_mb, kb / 1024)
        except OSError:
            continue
    stats["gunicorn_max_rss_mb"] = round(max_rss_mb)
    if max_rss_mb > 1024:
        findings.append(finding("warning", "HEALTH_GUNICORN_RSS_HIGH", "Gunicorn worker používá přes 1 GB RSS",
                                 f"max {max_rss_mb:.0f} MB napříč {len(pids)} procesy", where="konfigurator.service"))
    # ocekavany pocet workeru podle --workers v ExecStart (master + N workeru = N+1 procesu)
    _, show_out, _ = _run(["systemctl", "cat", "konfigurator.service"])
    m = re.search(r"--workers\s+(\d+)", show_out)
    if m:
        expected = int(m.group(1))
        stats["gunicorn_expected_workers"] = expected
        if len(pids) < expected:
            findings.append(finding("warning", "HEALTH_GUNICORN_MISSING_WORKERS",
                                     "Méně gunicorn procesů, než je nakonfigurováno",
                                     f"nalezeno {len(pids)}, očekáváno master+{expected}", where="konfigurator.service"))


# --- nginx access log ----------------------------------------------------------

def check_nginx_log(findings, stats):
    log_path = "/var/log/nginx/access.log"
    if not os.path.isfile(log_path):
        findings.append(finding("warning", "HEALTH_NGINX_LOG_MISSING", "nginx access.log nenalezen", log_path))
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
    total = 0
    err5xx = 0
    c499 = c502 = c504 = 0
    line_re = re.compile(r'\[(\d{2})/(\w{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2}) [^\]]*\].*" (\d{3}) ')
    months = {m: i + 1 for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = line_re.search(line)
                if not m:
                    continue
                day, mon, year, hh, mm, ss, status = m.groups()
                try:
                    ts = datetime.datetime(int(year), months[mon], int(day), int(hh), int(mm), int(ss))
                except (KeyError, ValueError):
                    continue
                if ts < cutoff:
                    continue
                total += 1
                status_i = int(status)
                if status_i >= 500:
                    err5xx += 1
                if status_i == 499:
                    c499 += 1
                elif status_i == 502:
                    c502 += 1
                elif status_i == 504:
                    c504 += 1
    except OSError as e:
        findings.append(finding("warning", "HEALTH_NGINX_LOG_READ_FAILED", "Nepodařilo se přečíst access.log", str(e)))
        return
    stats["nginx_requests_24h"] = total
    stats["nginx_5xx_24h"] = err5xx
    stats["nginx_499_24h"] = c499
    stats["nginx_502_24h"] = c502
    stats["nginx_504_24h"] = c504
    if total:
        pct = round(err5xx / total * 100, 3)
        stats["nginx_5xx_pct_24h"] = pct
        if pct > 0.5:
            findings.append(finding("warning", "HEALTH_NGINX_5XX_HIGH", "Podíl 5xx odpovědí za 24 h přesáhl 0,5 %",
                                     f"{pct}% ({err5xx}/{total})", where=log_path))

    _, fmt_out, _ = _run(["grep", "-c", "request_time", "/etc/nginx/nginx.conf"])
    if fmt_out.strip() == "0":
        findings.append(finding("info", "HEALTH_NO_REQUEST_TIME_LOG",
                                 "nginx log_format neobsahuje $request_time/$upstream_response_time - p95 doby odezvy nelze měřit z logů",
                                 "default 'combined' formát",
                                 fix_hint="přidat vlastní log_format s $request_time do http{} bloku nginx.conf a "
                                          "'access_log ... custom_format;' do vhostů - vyžaduje jen reload, ne restart, bez výpadku"))


def collect():
    findings = []
    stats = {}
    check_systemd(findings, stats)
    check_http(findings, stats)
    check_tls(findings, stats)
    check_disk(findings, stats)
    conn = check_db(findings, stats)
    if conn is not None:
        check_queues(findings, stats, conn)
        conn.close()
    check_backup(findings, stats)
    check_gunicorn(findings, stats)
    check_nginx_log(findings, stats)
    return findings, stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    run_suite("health", collect, args.json)
