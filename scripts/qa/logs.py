#!/usr/bin/env python3
"""
scripts/qa/logs.py - skener logu za poslednich N hodin (bot14,
2026-09-02, "kontrolni mechanismy na cely system konfiguratoru",
oblast OPS/logs, zadani Roberta pres bot3).

Zdroje: journalctl -u konfigurator (gunicorn StandardOutput=journal,
viz systemctl show), nginx error.log, nginx access.log.

POZOR - sdileny VPS: gunicorn procesy (viz health.py) i nginx access/
error log jsou SDILENE napric vsemi projekty na tomhle stroji (domeny,
vybaveni-uzitkovych-vozidel, no-sim, imiei.top, toscanaccio...).
`journalctl -u konfigurator` je uz spravne scoped (jednotka), ale nginx
error.log/access.log NE - viz _our_domains()/poznamky u
check_nginx_access() nize.

Pouziti:
  api/venv/bin/python3 scripts/qa/logs.py --since 24h
  api/venv/bin/python3 scripts/qa/logs.py --since 24h --json
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import finding, QA_REPORTS_DIR, run_suite  # noqa: E402

SEEN_PATH = os.path.join(QA_REPORTS_DIR, "logs_seen.json")


def _run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:  # noqa: BLE001
        return -1, "", str(e)


def _parse_since(s):
    m = re.match(r"^(\d+)h$", s or "24h")
    hours = int(m.group(1)) if m else 24
    return hours


def _load_seen():
    if os.path.isfile(SEEN_PATH):
        try:
            with open(SEEN_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    return {}


def _save_seen(seen):
    tmp = SEEN_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SEEN_PATH)


# --- konfigurator.service journal (gunicorn stdout/stderr) -------------------

TRACEBACK_START = re.compile(r"Traceback \(most recent call last\):")
FRAME_RE = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
_JOURNAL_PREFIX_RE = re.compile(r"gunicorn\[\d+\]:\s?(.*)$")


def _journal_content(line):
    """Obsah radku BEZ syslog/journalctl predpony ("MMM DD HH:MM:SS host
    gunicorn[PID]: ") - potrebne pro spolehlive rozliseni odsazenych
    (soucast tracebacku) vs neodsazenych (konec tracebacku) radku."""
    m = _JOURNAL_PREFIX_RE.search(line)
    return m.group(1) if m else line
# POZOR (zivy test 2026-09-02 odhalil bug): venv je FYZICKY pod
# /opt/konfigurator/api/venv/, takze samotne "/opt/konfigurator/api/"
# jako marker chytalo i knihovni kod treti strany (napr. pymysql
# connections.py) jako by to byl "nas" ramec - signatura pak ukazovala
# na cizi radek v knihovne, ne na misto v NASEM kodu, ktere volani
# vyvolalo. Vyloucit /api/venv/ explicitne.
OUR_CODE_MARK = "/opt/konfigurator/api/"
OUR_CODE_EXCLUDE = "/opt/konfigurator/api/venv/"


def check_konfigurator_journal(findings, stats, since_hours, seen):
    code, out, err = _run(["journalctl", "-u", "konfigurator.service", "--since", f"-{since_hours}h", "--no-pager"])
    if code != 0:
        findings.append(finding("warning", "LOGS_JOURNAL_READ_FAILED", "journalctl -u konfigurator selhal", err or out))
        return
    lines = out.splitlines()

    tracebacks = []  # list of (signature, exc_line, sample_block, first_ts, last_ts)
    i = 0
    worker_timeout = booting_worker = memory_error = error_handling_request = 0
    while i < len(lines):
        line = lines[i]
        if "WORKER TIMEOUT" in line:
            worker_timeout += 1
        if "Booting worker" in line:
            booting_worker += 1
        if "MemoryError" in line:
            memory_error += 1
        if "Error handling request" in line:
            error_handling_request += 1
        if TRACEBACK_START.search(_journal_content(line)):
            ts_str = " ".join(line.split(" ", 3)[:3])
            block = [line]
            frames = []
            j = i + 1
            exc_line = None
            # Skutecna struktura Python tracebacku v journalu: "  File
            # ..." radky (2 mezery), pod kazdym odsazeny zdrojovy radek
            # (4 mezery), a NAKONEC jeden NEODSAZENY radek =
            # "VyjimkaTyp: zprava" - to je konec bloku. Puvodni verze
            # (zivy test 2026-09-02) tohle nerozlisovala a jako
            # "exc_line" brala nahodny odsazeny zdrojovy radek misto
            # skutecne vyjimky.
            while j < len(lines):
                c2 = _journal_content(lines[j])
                if not c2.strip():
                    j += 1
                    continue
                if c2[0] in (" ", "\t"):
                    fm = FRAME_RE.search(c2)
                    if fm:
                        frames.append(fm.groups())
                    block.append(lines[j])
                    j += 1
                    continue
                # neodsazeny radek = konec tracebacku (vyjimka), NEBO uz
                # neni soucasti tohohle bloku vubec (napr. dalsi
                # "Traceback" bez mezivrstvy - edge case pri oriznuti
                # oknem --since).
                exc_line = c2.strip()
                block.append(lines[j])
                j += 1
                break
            if exc_line is None:
                exc_line = "(traceback nedokoncen v logu)"
            our_frame = next(
                (f for f in reversed(frames) if OUR_CODE_MARK in f[0] and OUR_CODE_EXCLUDE not in f[0]), None
            )
            if our_frame:
                rel = our_frame[0].split("/opt/konfigurator/")[-1]
                sig = f"{exc_line.split(':')[0]} @ {rel}:{our_frame[1]}"
            else:
                sig = exc_line.split(":")[0] or "unknown"
            tracebacks.append({"sig": sig, "exc": exc_line, "ts": ts_str, "sample": "\n".join(block[:20])})
            i = j
            continue
        i += 1

    grouped = defaultdict(list)
    for t in tracebacks:
        grouped[t["sig"]].append(t)

    stats["journal_lines_scanned"] = len(lines)
    stats["worker_timeout_count"] = worker_timeout
    stats["worker_boots_count"] = booting_worker
    stats["memory_error_count"] = memory_error
    stats["error_handling_request_count"] = error_handling_request
    stats["distinct_traceback_signatures"] = len(grouped)
    stats["total_tracebacks"] = len(tracebacks)

    for sig, items in grouped.items():
        first_ts, last_ts = items[0]["ts"], items[-1]["ts"]
        is_new = sig not in seen.get("tracebacks", {})
        sev = "warning" if is_new else "info"
        findings.append(finding(
            sev, "LOGS_NEW_TRACEBACK" if is_new else "LOGS_KNOWN_TRACEBACK",
            f"{'Nová' if is_new else 'Známá'} chybová signatura ({len(items)}x): {sig}",
            f"první výskyt {first_ts}, poslední {last_ts}. Ukázka:\n{items[0]['sample']}",
            where=sig,
        ))
        seen.setdefault("tracebacks", {})[sig] = {"last_seen": last_ts, "count_last_run": len(items)}

    if worker_timeout:
        findings.append(finding("warning", "LOGS_WORKER_TIMEOUT", "Gunicorn worker timeout(y) v logu",
                                 f"{worker_timeout}x za posledních {since_hours} h", where="konfigurator.service"))
    if booting_worker > 3:
        findings.append(finding("warning", "LOGS_WORKER_RESTARTS", "Časté restarty gunicorn workerů",
                                 f"'Booting worker' {booting_worker}x za {since_hours} h", where="konfigurator.service"))
    if memory_error:
        findings.append(finding("critical", "LOGS_MEMORY_ERROR", "MemoryError v aplikačním logu",
                                 f"{memory_error}x za {since_hours} h", where="konfigurator.service"))


# --- nginx error.log -----------------------------------------------------------

ERROR_TYPE_PATTERNS = [
    ("upstream_timed_out", re.compile(r"upstream timed out")),
    ("connect_failed", re.compile(r"connect\(\) failed")),
    ("permission_denied", re.compile(r"[Pp]ermission denied")),
    ("no_such_file", re.compile(r"[Nn]o such file")),
    ("directory_index_forbidden", re.compile(r"directory index of .* is forbidden")),
    ("connection_reset", re.compile(r"Connection reset by peer")),
]


def _our_domains():
    """Vsechny domeny, ktere podle nginx vhostu proxuji na konfigurator
    (konfigurator_api upstream nebo primo unix:.../konfigurator.sock) -
    zjisteno DYNAMICKY ze sites-enabled, ne hardcoded seznam (at se
    novy storefront/subdomena automaticky zapocita, viz webapp/js
    turntable atd. pro presedent takovych pribyvajicich domen)."""
    domains = set()
    for path in glob.glob("/etc/nginx/sites-enabled/*"):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        if "konfigurator_api" not in content and "konfigurator.sock" not in content:
            continue
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line.startswith("#"):
                continue
            # [^;\n] (NE [^;]) - negovana trida bez \n by jinak (skutecny
            # bug pri prvnim psani) presahla pres radky az k prvnimu
            # strednikou KDEKOLI dal v souboru, vcetne komentaru jako
            # "# - server_name na HTTP bloku zmenit na ..." o par radku
            # vyse (ten sam obsahuje slovo "server_name", ale bez strednika).
            m = re.search(r"server_name\s+([^;\n]+);", line)
            if m:
                for d in m.group(1).split():
                    domains.add(d.lower())
    return domains


def check_nginx_error(findings, stats, since_hours):
    log_path = "/var/log/nginx/error.log"
    rotated = glob.glob(log_path + ".*")
    our_domains = _our_domains()
    stats["nginx_our_domains"] = sorted(our_domains)
    cutoff = time.time() - since_hours * 3600
    type_counts = Counter()
    our_type_counts = Counter()
    samples = {}
    total_lines = 0
    if os.path.getmtime(log_path) >= cutoff and os.path.isfile(log_path):
        files = [log_path]
    else:
        files = [log_path]  # aktualni soubor vzdy zkusit, i kdyz mtime je stara (prazdny den)
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = re.match(r"^(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2})", line)
                    if m:
                        import datetime
                        ts = datetime.datetime(*[int(x) for x in m.groups()])
                        if ts.timestamp() < cutoff:
                            continue
                    total_lines += 1
                    matched_type = None
                    for name, pat in ERROR_TYPE_PATTERNS:
                        if pat.search(line):
                            matched_type = name
                            break
                    if not matched_type:
                        matched_type = "other"
                    type_counts[matched_type] += 1
                    hm = re.search(r'host: "([^"]+)"', line)
                    host = hm.group(1).lower() if hm else None
                    is_ours = (host in our_domains) if host else ("konfigurator.sock" in line)
                    if is_ours:
                        our_type_counts[matched_type] += 1
                        samples.setdefault(matched_type, line.strip())
        except OSError as e:
            findings.append(finding("warning", "LOGS_NGINX_ERROR_READ_FAILED", f"Nepodařilo se přečíst {path}", str(e)))

    stats["nginx_error_lines_total_24h"] = total_lines
    stats["nginx_error_types_all_vhosts"] = dict(type_counts)
    stats["nginx_error_types_konfigurator"] = dict(our_type_counts)
    for t, c in our_type_counts.items():
        if t in ("upstream_timed_out", "connect_failed", "permission_denied", "no_such_file") and c:
            findings.append(finding("warning", f"LOGS_NGINX_{t.upper()}", f"nginx error.log: {t} ({c}x, jen konfigurator domény)",
                                     samples.get(t, ""), where="konfigurator"))


# --- nginx access.log -----------------------------------------------------------

# Siroky, best-effort seznam (zivy test 2026-09-02 ukazal, ze puvodni
# uzka verze propustila wp-includes/.aws/docker-compose.yml/secrets.json/
# .npmrc jako "nase" 404) - VPS je sdileny s dalsimi projekty a scanner
# provoz cili na kazdou domenu na spolecne IP, ne jen konfigurator, viz
# LOGS_NO_HOST_IN_ACCESS_LOG pro proc se to neda filtrovat presneji.
SCANNER_PATH_RE = re.compile(
    # POZOR: puvodni verze mela vse zabalene v "/(...)"$, cimz kazda
    # alternativa vyzadovala LITERALNI "/" bezprostredne pred sebou -
    # "\.php$" tak matchovalo jen soubor doslova nazvany ".php", ne
    # libovolny "*.php" (zjisteno 2026-09-02 pri zapojeni per-host
    # filtrace). Pripony jako .php/.env/.git proto NEJSOU v te vnitrni
    # slozkove skupine, aby matchovaly kdekoli v ceste.
    r"(/(wp-admin|wp-login|wp-content|wp-includes|wordpress|wp[0-9]?/|"
    r"\.well-known/security\.txt|xmlrpc\.php|phpmyadmin|phpinfo|"
    r"docker-compose|secrets\.json|config\.json|ads\.txt|wallet/|"
    r"vendor/|\.vscode|actuator|swagger|_ignition|telescope|"
    r"debug/default/view)|\.env|\.git|\.aws|\.npmrc|\.ssh|\.php$|\.php\?)",
    re.IGNORECASE,
)
BOT_UA_RE = re.compile(r"bot|crawl|spider|slurp|claudebot|gptbot", re.IGNORECASE)


def check_nginx_access(findings, stats, since_hours):
    # access.log je SDILENY napric vsemi projekty na VPS. Do 2026-09-02
    # pouzival vychozi nginx 'combined' log_format bez $host, takze
    # nesel filtrovat per projekt vubec - viz stary LOGS_NO_HOST_IN_ACCESS_LOG
    # nalez. Od 2026-09-02 (bot14, schvaleno bot3) ma nginx.conf vlastni
    # log_format "konf_ext", ktery na konec PRIDAVA "host=... rt=...".
    # Stare radky pred reloadem tohle pole nemaji - regex ho bere jako
    # VOLITELNE, takze parsuje oba formaty najednou. Kdyz je pole
    # pritomne, umime navic spocitat p95 a filtrovat jen na domeny
    # konfiguratoru (_our_domains()).
    log_path = "/var/log/nginx/access.log"
    cutoff = time.time() - since_hours * 3600
    line_re = re.compile(
        r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d{3}) \d+ "[^"]*" "([^"]*)"'
        r'(?: host=(\S+) rt=([\d.]+))?'
    )
    our_domains = _our_domains()
    status_by_path = Counter()
    path_hits = Counter()
    konf_status_by_path = Counter()
    konf_path_hits = Counter()
    konf_response_times = []
    ua_total = 0
    ua_bot = 0
    total = 0
    with_host_field = 0
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = line_re.match(line)
                if not m:
                    continue
                ip, time_local, method, path, status, ua, host, rt = m.groups()
                total += 1
                ua_total += 1
                if BOT_UA_RE.search(ua):
                    ua_bot += 1
                status_i = int(status)
                is_scanner_404 = status_i == 404 and SCANNER_PATH_RE.search(path)
                if status_i == 404 and not is_scanner_404:
                    path_hits[path] += 1
                elif status_i >= 500:
                    status_by_path[path] += 1

                if host:
                    with_host_field += 1
                    if host in our_domains:
                        if rt:
                            try:
                                konf_response_times.append(float(rt))
                            except ValueError:
                                pass
                        if status_i == 404 and not is_scanner_404:
                            konf_path_hits[path] += 1
                        elif status_i >= 500:
                            konf_status_by_path[path] += 1
    except OSError as e:
        findings.append(finding("warning", "LOGS_NGINX_ACCESS_READ_FAILED", "Nepodařilo se přečíst access.log", str(e)))
        return

    stats["access_requests_seen"] = total
    stats["access_bot_pct"] = round(ua_bot / ua_total * 100, 1) if ua_total else 0
    stats["access_host_field_pct"] = round(with_host_field / total * 100, 1) if total else 0
    top_404 = path_hits.most_common(30)
    stats["top_404_paths"] = [{"path": p, "count": c} for p, c in top_404]
    stats["5xx_by_path"] = [{"path": p, "count": c} for p, c in status_by_path.most_common(20)]

    content_files_404 = sum(c for p, c in top_404 if p.startswith("/content-files/"))
    api_404 = sum(c for p, c in top_404 if p.startswith("/api/"))
    if content_files_404:
        findings.append(finding("warning", "LOGS_MISSING_IMAGES", "404 na /content-files/ (chybějící obrázky)",
                                 f"{content_files_404} takových 404 (z celého VPS, viz poznámka o $host)", where="/content-files/"))
    if api_404:
        findings.append(finding("warning", "LOGS_BROKEN_API_CALL", "404 na /api/ (rozbité volání)",
                                 f"{api_404} takových 404 (z celého VPS, viz poznámka o $host)", where="/api/"))

    if konf_response_times:
        konf_response_times.sort()
        idx = min(len(konf_response_times) - 1, int(round(0.95 * (len(konf_response_times) - 1))))
        stats["konf_requests_with_host"] = len(konf_response_times)
        stats["konf_p95_response_time_ms"] = round(konf_response_times[idx] * 1000)
        stats["konf_top_404_paths"] = [{"path": p, "count": c} for p, c in konf_path_hits.most_common(30)]
        stats["konf_5xx_by_path"] = [{"path": p, "count": c} for p, c in konf_status_by_path.most_common(20)]

    if stats["access_host_field_pct"] < 50:
        findings.append(finding(
            "info", "LOGS_NO_HOST_IN_ACCESS_LOG",
            "Většina access.log řádků ve zvoleném okně ještě nemá $host (starý formát před reloadem 2026-09-02)",
            f"jen {stats['access_host_field_pct']}% řádků má host=... - 404/5xx analýza výše je proto za CELÝ VPS, "
            "ne jen konfigurator; s dalším odstupem od reloadu tento poměr poroste sám",
            fix_hint="nic dělat netřeba - log_format 'konf_ext' už je nasazený (nginx.conf, bot14 2026-09-02), "
                     "jen čekat, až staré řádky vypadnou z okna/rotace",
        ))


def collect(since_hours):
    findings = []
    stats = {"since_hours": since_hours}
    seen = _load_seen()
    check_konfigurator_journal(findings, stats, since_hours, seen)
    check_nginx_error(findings, stats, since_hours)
    check_nginx_access(findings, stats, since_hours)
    _save_seen(seen)
    return findings, stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="24h", help="např. 24h (výchozí)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    hours = _parse_since(args.since)
    run_suite("logs", lambda: collect(hours), args.json)
