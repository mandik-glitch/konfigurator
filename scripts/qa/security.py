#!/usr/bin/env python3
"""
QA suita BEZPECNOST (bot6, 2026-09-02) - zadani Roberta pres bot3:
"kontrolni mechanismy na cely system konfiguratoru - hledat chyby...
hledat moznosti ke zlepseni". Tahle suita pokryva oblast (G) BEZPECNOST.

Sdileny JSON kontrakt/exit kody/READ-ONLY DB rezim viz `_common.py`
(bot14) - tenhle soubor si nic z toho nedefinuje znovu.

CO JE TU JINAK NEZ V `api/qa_checks.py`: qa_checks resi STATICKOU
analyzu kodu a konzistenci dat (50 kontrol, mj. `check_admin_route_
missing_permission`, `check_bare_except`, `check_requests_no_timeout`,
`check_direct_send_email_bypass`). Tahle suita je jeji doplnek -
DYNAMICKE overeni za behu (co server SKUTECNE odpovi) + systemova
vrstva (nginx/TLS/porty/systemd/zavislosti), kam staticka analyza
nedosahne. Staticke kontroly zamerne nedupluju.

== BEZPECNOSTNI PRAVIDLA BEHU (Robert/bot3: read-only, bez zateze) ==
- Jen GET/HEAD/OPTIONS + presne vymezeny pripad POST (viz nize).
- ZADNY brute-force/rate-limit test naziva (mohl by zablokovat Roberta),
  zadne fuzzovani, zadne odesilani formularu ani e-mailu, zadna
  testovaci data, zadny zapis do DB, zadna zmena konfigurace serveru.
- Mezi requesty je prodleva, aby to nedelalo zatez.

== PROC SE NA NECHRANENE POST ROUTY NEPOSILA NIC ==
Zadani znelo "pro POST prazdny JSON -> ocekavano 401/403". Poslat
prazdny POST je bezpecne JEN u routy, ktera ochranny dekorator MA:
dekorator se vyhodnoti PRED telem view funkce, takze request skonci na
401/403 a handler se vubec nespusti - presne to chceme overit (ze
dekorator za behu opravdu funguje, ne jen ze je napsany v kodu).
U routy BEZ dekoratoru by ale tentyz prazdny POST handler SKUTECNE
SPUSTIL - na zivem e-shopu (objednavky, poptavky, sklad, e-maily) je
to nepripustne riziko zapisu/odeslani. Takove routy proto jen HLASIME
k rucnimu overeni a nic jim neposilame. Pokryti tim netrpi: routa bez
dekoratoru je nalezena uz statickou analyzou, a to je prave ten nalez.
"""
import argparse
import ast
import glob
import hashlib
import json
import os
import re
import socket
import ssl
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import REPO_ROOT, finding, load_env, run_suite  # noqa: E402

API_DIR = os.path.join(REPO_ROOT, "api")
WEBAPP_DIR = os.path.join(REPO_ROOT, "webapp")

DEFAULT_BASES = ["https://autovestavby.logiman.cz", "http://75.119.132.164:8090"]
REQ_TIMEOUT = 12
REQ_DELAY = 0.05          # setrnost k zivemu provozu
USER_AGENT = "konfigurator-qa-security/1.0 (interni kontrola)"

# Ochranne dekoratory, ktere v tomhle projektu hlidaji pristup.
# POZOR: seznam musi sedet na REALITU repa, ne na obecnou predstavu. Prvni
# verze mela jen login_required/require_permission a tim padem povazovala
# 152 rout s @admin_required / @remeslnik_or_admin_required za nechranene -
# nejen falesne poplachy, ale hlavne se tyhle routy vubec neoverily naziva.
# Aktualni seznam podle `grep` dekoratoru nad @app.<metoda> v api/*.py.
AUTH_DECORATORS = {
    "login_required", "require_permission", "require_login",
    "admin_required", "require_admin", "remeslnik_or_admin_required",
    "staff_required",
}

# Cesty, ktere nginx NESMI servirovat (zadani bot3 + repo realita).
SENSITIVE_PATHS = [
    "/.env", "/api/.env", "/.git/HEAD", "/.git/config", "/DEPLOY_LOCK.json",
    "/PRISTUPY.md", "/WORKFLOW.md", "/AGENTS_LOG.md", "/CLAUDE.md", "/TASKS.md",
    "/backups/", "/sql/", "/scripts/", "/node_modules/", "/private-files/",
    "/api/toscanaccio.sock", "/server-status", "/qa-reports/",
    "/package.json", "/api/app.py", "/api/qa_checks.py",
]
# Adresare, u kterych nas zajima directory listing (autoindex).
LISTING_PATHS = ["/content-files/", "/content-files/turntable-frames/", "/webapp/", "/katalog/"]

# POZOR: kazdy vzor musi mit prave jednu zachytavajici skupinu = SAMOTNA
# HODNOTA (ne klicove slovo). Podle jejiho hashe se nalezy seskupuji a
# porovnavaji proti api/.env - kdyz skupina zachyti "password" misto hesla,
# vsechny vyskyty splynou do nesmyslne skupiny a shoda se zivym udajem se
# nepozna (presne na tohle jsem narazil pri ladeni).
SECRET_PATTERNS = [
    ("heslo/password prirazeni",
     re.compile(r"""(?i)\b(?:password|passwd|heslo)\s*[=:]\s*['"]([^'"]{6,})['"]""")),
    ("api_key/secret prirazeni",
     re.compile(r"""(?i)\b(?:api_key|apikey|secret|token)\s*[=:]\s*['"]([^'"]{12,})['"]""")),
    ("OpenAI/Anthropic klic", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})")),
    ("AWS klic", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
    ("Slack token", re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})")),
    ("privatni klic", re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----)")),
]


# ---------------------------------------------------------------- HTTP


def http(url, method="GET", body=None, headers=None, timeout=REQ_TIMEOUT):
    """Vraci (status, headers_dict, telo_prvnich_2kB, chyba_str)."""
    time.sleep(REQ_DELAY)
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, dict(r.headers), r.read(2048), None
    except urllib.error.HTTPError as e:
        try:
            payload = e.read(2048)
        except Exception:
            payload = b""
        return e.code, dict(e.headers or {}), payload, None
    except Exception as e:  # noqa: BLE001 - sit/TLS/DNS, chceme to jako text
        return None, {}, b"", repr(e)


def host_of(base):
    return base.split("//", 1)[-1].split("/", 1)[0]


# ------------------------------------------------- parsovani rout z kodu


def _decorator_name(node):
    d = node.func if isinstance(node, ast.Call) else node
    if isinstance(d, ast.Attribute):
        return d.attr
    if isinstance(d, ast.Name):
        return d.id
    return None


def _route_paths_and_methods(dec):
    """Z @app.get('/x') / @app.route('/x', methods=['POST']) vytahne
    (cesta, [metody]). Vraci [] u dekoratoru, ktere routu nedefinuji."""
    if not isinstance(dec, ast.Call):
        return []
    fn = dec.func
    if not isinstance(fn, ast.Attribute) or not dec.args:
        return []
    verb = fn.attr
    first = dec.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return []
    path = first.value
    if verb in ("get", "post", "put", "delete", "patch"):
        return [(path, [verb.upper()])]
    if verb == "route":
        methods = ["GET"]
        for kw in dec.keywords or []:
            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                methods = [e.value for e in kw.value.elts
                           if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        return [(path, methods)]
    return []


def _has_inline_auth_guard(func_node):
    """Nektere routy se nechrani dekoratorem, ale kontrolou primo v tele:
        user = current_user()
        if not user or not user.get("active"):
            return jsonify(...), 401
    (napr. api/approvals.py:37). Funguje to, ale staticky to vypada jako
    nechranena routa - bez teto detekce bych hlasil falesny poplach."""
    calls_current_user = any(
        isinstance(n, ast.Call) and (
            (isinstance(n.func, ast.Name) and n.func.id == "current_user")
            or (isinstance(n.func, ast.Attribute) and n.func.attr == "current_user"))
        for n in ast.walk(func_node))
    if not calls_current_user:
        return False
    for n in ast.walk(func_node):
        if isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple):
            for el in n.value.elts:
                if isinstance(el, ast.Constant) and el.value in (401, 403):
                    return True
    return False


def parse_routes():
    """[{path, methods, protected, decorators, file, line, func}] ze VSECH api/*.py."""
    routes = []
    for py in sorted(glob.glob(os.path.join(API_DIR, "*.py"))):
        try:
            tree = ast.parse(open(py, encoding="utf-8").read(), filename=py)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = [_decorator_name(d) for d in node.decorator_list]
            paths = []
            for d in node.decorator_list:
                paths.extend(_route_paths_and_methods(d))
            if not paths:
                continue
            protected = any(n in AUTH_DECORATORS for n in names if n)
            inline_guard = _has_inline_auth_guard(node)
            for path, methods in paths:
                routes.append({
                    "path": path, "methods": methods,
                    "protected": protected or inline_guard,
                    "inline_guard": inline_guard and not protected,
                    "decorators": [n for n in names if n],
                    "file": os.path.relpath(py, REPO_ROOT), "line": node.lineno,
                    "func": node.name,
                })
    return routes


PARAM_RE = re.compile(r"<[^>]+>")


def concretize(path):
    """'/api/x/<int:pid>' -> '/api/x/999000111' (neexistujici ID; u
    chranene routy musi 401/403 prijit tak jako tak, pred dotazem do DB)."""
    def repl(m):
        return "999000111" if "int:" in m.group(0) or "float:" in m.group(0) else "qa-nonexistent"
    return PARAM_RE.sub(repl, path)


# ------------------------------------------------------------- kontroly


def check_route_auth(bases, findings, stats):
    routes = parse_routes()
    stats["routes_total"] = len(routes)
    protected = [r for r in routes if r["protected"]]
    admin_unprotected = [r for r in routes
                         if not r["protected"] and r["path"].startswith("/api/admin")]
    stats["routes_protected"] = len(protected)
    stats["routes_admin_unprotected_static"] = len(admin_unprotected)

    # Routy bez dekoratoru na /api/admin/* NETESTUJEME zive (viz hlavicka) -
    # hlasime je k rucnimu overeni.
    for r in [x for x in routes if x.get("inline_guard") and x["path"].startswith("/api/admin")]:
        findings.append(finding(
            "info", "SEC_ADMIN_ROUTE_INLINE_GUARD",
            "Admin routa se chrani kontrolou v tele, ne dekoratorem",
            f"{r['methods']} {r['path']} ({r['func']}) vola current_user() a vraci 401/403 "
            "primo v tele. Funguje, ale nejde to poznat z hlavicky funkce a snadno se "
            "na to pri uprave zapomene.",
            where=f"{r['file']}:{r['line']}",
            fix_hint="Sjednotit na dekorator (@admin_required / @require_permission), "
                     "at je ochrana videt na prvni pohled a chytne ji i staticka kontrola."))

    for r in admin_unprotected:
        findings.append(finding(
            "warning", "SEC_ADMIN_ROUTE_NO_DECORATOR",
            "Admin routa bez ochranneho dekoratoru (nutne rucni overeni)",
            f"{r['methods']} {r['path']} ({r['func']}) nema zadny z {sorted(AUTH_DECORATORS)}. "
            "Zive jsem ji ZAMERNE netestoval - prazdny POST na nechranenou routu by "
            "spustil handler na zivem e-shopu.",
            where=f"{r['file']}:{r['line']}",
            fix_hint="Doplnit @login_required / @require_permission(...), nebo potvrdit, "
                     "ze routa ma byt verejna, a poznamenat to komentarem u dekoratoru."))

    tested = 0
    for base in bases:
        for r in protected:
            url = base + concretize(r["path"])
            methods = [m for m in r["methods"] if m in ("GET", "POST", "PUT", "DELETE", "PATCH")]
            if not methods:
                continue
            method = "GET" if "GET" in methods else methods[0]
            body, hdrs = None, {}
            if method != "GET":
                # Bezpecne prave proto, ze routa dekorator MA - viz hlavicka.
                body, hdrs = b"{}", {"Content-Type": "application/json"}
            status, _, payload, err = http(url, method=method, body=body, headers=hdrs)
            # 5xx byva PRECHODNY stav (jiny bot prave restartuje sluzbu -
            # presne to se mi stalo pri ladeni: 8 rout vratilo 502 uprostred
            # cizi deploye a po chvili zase spravne 401). Jeden opakovany
            # pokus odfiltruje deploy okno, aniz by zamaskoval trvaly problem.
            if status is not None and status >= 500:
                time.sleep(2.0)
                status, _, payload, err = http(url, method=method, body=body, headers=hdrs)
            tested += 1
            if err:
                findings.append(finding(
                    "info", "SEC_ROUTE_UNREACHABLE", "Routu neslo overit",
                    f"{method} {url}: {err}", where=f"{r['file']}:{r['line']}"))
                continue
            if status in (401, 403, 405, 404, 400, 302, 301):
                continue
            if status is not None and status >= 500:
                findings.append(finding(
                    "warning", "SEC_ROUTE_SERVER_ERROR",
                    "Chranena routa vraci serverovou chybu misto 401/403",
                    f"{method} {url} -> {status} i po opakovanem pokusu. Bud chyba v "
                    "handleru pred kontrolou opravneni, nebo probihajici vypadek.",
                    where=f"{r['file']}:{r['line']}",
                    fix_hint="Overit log gunicornu; anonymni request by nikdy nemel "
                             "dojit az k vyjimce."))
                continue
            sev = "critical" if status == 200 else "warning"
            findings.append(finding(
                sev, "SEC_PROTECTED_ROUTE_ANON_ACCESS",
                "Chranena routa neodmitla anonymni pristup",
                f"{method} {url} vratilo {status} (ocekavano 401/403). "
                f"Dekoratory v kodu: {r['decorators']}. Prvnich 200 B odpovedi: "
                f"{payload[:200]!r}",
                where=f"{r['file']}:{r['line']}",
                fix_hint="Overit, ze dekorator je NAD @app.<metoda> ve spravnem poradi a ze "
                         "se skutecne aplikuje (poradi dekoratoru u Flasku rozhoduje)."))
    stats["routes_tested_live"] = tested


def _catchall_signature(base):
    """Nginx tu na NEZNAME cesty vraci 200 s HTML shellem, ne 404. Bez
    rozpoznani tohohle by skript hlasil jako "verejne servirovane" i
    soubory, ktere server vubec nema (overeno rucne na /PRISTUPY.md:
    200, ale je to 99 kB HTML shellu, ne ten soubor). Otisk si vezmeme
    z nahodne neexistujici cesty a pak ho porovnavame."""
    status, hdrs, payload, err = http(base + "/qa-nonexistent-probe-4f2a9c/", method="GET")
    if err:
        return None
    return (status, hdrs.get("Content-Type", ""), len(payload), payload[:200])


def check_sensitive_paths(bases, findings, stats):
    exposed = 0
    for base in bases:
        shell = _catchall_signature(base)
        for path in SENSITIVE_PATHS:
            status, hdrs, payload, err = http(base + path, method="GET")
            if err or status != 200:
                continue
            if shell and (status, hdrs.get("Content-Type", ""), len(payload), payload[:200]) == shell:
                continue  # je to catch-all shell, ne ten soubor
            if shell and hdrs.get("Content-Type", "").startswith("text/html") \
                    and payload[:200] == shell[3]:
                continue
            exposed += 1
            findings.append(finding(
                "critical", "SEC_SENSITIVE_PATH_SERVED",
                "Citliva cesta je verejne servirovana",
                f"GET {base}{path} -> 200, content-type={hdrs.get('Content-Type')}, "
                f"ukazka: {payload[:120]!r}",
                where=f"{base}{path}",
                fix_hint="V nginx vhostu pridat `location ~ /\\.(env|git)` a explicitni deny "
                         "pro /backups/, /sql/, /scripts/, /private-files/, *.md, *.py "
                         "(return 404), aby se servirovala jen webapp/ statika."))

    # Zalohy admin.html a spol. primo ve webapp/ (servirovane jako statika).
    baks = sorted(glob.glob(os.path.join(WEBAPP_DIR, "*.bak*")) +
                  glob.glob(os.path.join(WEBAPP_DIR, "*.orig")))
    stats["webapp_backup_files"] = len(baks)
    for b in baks[:40]:
        rel = "/" + os.path.relpath(b, WEBAPP_DIR)
        for base in bases:
            shell = _catchall_signature(base)
            status, hdrs, payload, err = http(base + rel, method="GET")
            if err or status != 200:
                continue
            if shell and payload[:200] == shell[3]:
                continue
            exposed += 1
            findings.append(finding(
                "critical", "SEC_BACKUP_FILE_SERVED",
                "Zaloha zdrojoveho souboru je verejne stazitelna",
                f"GET {base}{rel} -> 200 ({len(payload)}+ B). Zalohy admin/HTML "
                "casto obsahuji interni endpointy, komentare i docasne klice.",
                where=f"{base}{rel}",
                fix_hint="Zalohy nepatri do webrootu - presunout do backups/ (mimo "
                         "servirovany adresar) a v nginx pridat deny na *.bak*/*.orig."))

    for base in bases:
        for path in LISTING_PATHS:
            status, hdrs, payload, err = http(base + path, method="GET")
            if err or status != 200:
                continue
            if b"<title>Index of" in payload or b"Index of /" in payload:
                findings.append(finding(
                    "warning", "SEC_DIRECTORY_LISTING",
                    "Nginx vypisuje obsah adresare",
                    f"GET {base}{path} -> 200 s directory listingem.",
                    where=f"{base}{path}",
                    fix_hint="V nginx `autoindex off;` pro tuhle location."))
    stats["sensitive_paths_exposed"] = exposed


HEADER_RULES = [
    ("Strict-Transport-Security", "warning", "SEC_MISSING_HSTS",
     'add_header Strict-Transport-Security "max-age=15768000; includeSubDomains" always;'),
    ("X-Content-Type-Options", "warning", "SEC_MISSING_XCTO",
     'add_header X-Content-Type-Options "nosniff" always;'),
    ("Referrer-Policy", "warning", "SEC_MISSING_REFERRER_POLICY",
     'add_header Referrer-Policy "strict-origin-when-cross-origin" always;'),
    ("Permissions-Policy", "info", "SEC_MISSING_PERMISSIONS_POLICY",
     'add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;'),
]


def check_headers(bases, findings, stats):
    for base in bases:
        status, hdrs, _, err = http(base + "/", method="GET")
        if err:
            findings.append(finding("info", "SEC_BASE_UNREACHABLE",
                                    "Zakladni URL nesla nacist", f"{base}: {err}", where=base))
            continue
        lower = {k.lower(): v for k, v in hdrs.items()}
        is_https = base.startswith("https://")

        for header, sev, code, hint in HEADER_RULES:
            if header.lower() in lower:
                continue
            if header == "Strict-Transport-Security" and not is_https:
                continue  # HSTS na http vhostu nema smysl
            findings.append(finding(
                sev, code, f"Chybi hlavicka {header}",
                f"GET {base}/ -> {status}, hlavicka {header} neni v odpovedi.",
                where=base, fix_hint=f"Do nginx server bloku: {hint}"))

        if "strict-transport-security" in lower and is_https:
            m = re.search(r"max-age=(\d+)", lower["strict-transport-security"])
            if m and int(m.group(1)) < 15552000:
                findings.append(finding(
                    "warning", "SEC_WEAK_HSTS", "HSTS max-age je kratsi nez 6 mesicu",
                    f"{lower['strict-transport-security']}", where=base,
                    fix_hint="max-age=15768000 (6 mesicu) nebo vic."))

        if "x-frame-options" not in lower and "frame-ancestors" not in lower.get("content-security-policy", ""):
            findings.append(finding(
                "warning", "SEC_MISSING_FRAME_PROTECTION",
                "Chybi ochrana proti vlozeni do iframe (clickjacking)",
                f"Ani X-Frame-Options, ani CSP frame-ancestors na {base}/.", where=base,
                fix_hint='add_header X-Frame-Options "SAMEORIGIN" always; '
                         "(nebo CSP frame-ancestors 'self')"))

        if "content-security-policy" not in lower and "content-security-policy-report-only" not in lower:
            findings.append(finding(
                "info", "SEC_MISSING_CSP", "Chybi Content-Security-Policy",
                f"{base}/ nema CSP ani v Report-Only rezimu.", where=base,
                fix_hint="Zacit Report-Only variantou, at se nic nerozbije: "
                         "add_header Content-Security-Policy-Report-Only "
                         "\"default-src 'self'; img-src 'self' data:; report-uri /csp-report\";"))

        server = lower.get("server", "")
        if re.search(r"\d+\.\d+", server):
            findings.append(finding(
                "info", "SEC_SERVER_VERSION_DISCLOSED", "Nginx hlasi presnou verzi",
                f"Server: {server}", where=base,
                fix_hint="`server_tokens off;` v http bloku nginx.conf."))
        if "x-powered-by" in lower:
            findings.append(finding(
                "info", "SEC_X_POWERED_BY", "Hlavicka X-Powered-By prozrazuje stack",
                f"X-Powered-By: {lower['x-powered-by']}", where=base,
                fix_hint="Odstranit (`proxy_hide_header X-Powered-By;`)."))


def check_cors_and_cookies(bases, findings, stats):
    routes = parse_routes()
    protected = [r for r in routes if r["protected"] and "GET" in r["methods"]]
    sample = protected[:12]
    for base in bases:
        for r in sample:
            url = base + concretize(r["path"])
            status, hdrs, _, err = http(url, headers={"Origin": "https://qa-security-probe.invalid"})
            if err:
                continue
            lower = {k.lower(): v for k, v in hdrs.items()}
            acao = lower.get("access-control-allow-origin")
            if acao == "*":
                findings.append(finding(
                    "critical", "SEC_CORS_WILDCARD_ON_AUTH",
                    "Autentizovany endpoint posila Access-Control-Allow-Origin: *",
                    f"{url} -> {status}, ACAO: *", where=url,
                    fix_hint="Na autentizovanych cestach nepouzivat wildcard - "
                             "povolit konkretni origin, nebo CORS vubec neposilat."))
            elif acao == "https://qa-security-probe.invalid":
                findings.append(finding(
                    "critical", "SEC_CORS_REFLECTS_ORIGIN",
                    "Server zrcadli libovolny Origin do ACAO",
                    f"{url} -> ACAO odrazi nas testovaci origin.", where=url,
                    fix_hint="Zrcadleni Originu je stejne slabe jako wildcard - "
                             "porovnavat proti allowlistu."))

    # Cookies: pro nastaveni session cookie staci navstivit homepage.
    for base in bases:
        status, hdrs, _, err = http(base + "/")
        if err:
            continue
        raw = [v for k, v in hdrs.items() if k.lower() == "set-cookie"]
        for cookie in raw:
            name = cookie.split("=", 1)[0].strip()
            low = cookie.lower()
            missing = []
            if "httponly" not in low:
                missing.append("HttpOnly")
            if base.startswith("https://") and "secure" not in low:
                missing.append("Secure")
            if "samesite" not in low:
                missing.append("SameSite")
            if missing:
                findings.append(finding(
                    "warning", "SEC_COOKIE_FLAGS",
                    f"Cookie {name} nema priznaky: {', '.join(missing)}",
                    f"Set-Cookie z {base}/: {cookie[:160]}", where=base,
                    fix_hint="Flask: SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=True, "
                             "SESSION_COOKIE_SAMESITE='Lax'."))
            if base.startswith("http://") and "secure" not in low:
                findings.append(finding(
                    "warning", "SEC_COOKIE_ON_PLAIN_HTTP",
                    f"Cookie {name} se nastavuje i na neistenem http vhostu",
                    f"{base} posila Set-Cookie bez Secure - session jde po siti v plaintextu.",
                    where=base,
                    fix_hint="Bud http vhost presmerovat na https, nebo na nem session "
                             "cookie vubec nenastavovat."))


# --------------------------------------------------- staticka analyza kodu

CODE_RULES = [
    ("SEC_EVAL_EXEC", "critical", "Volani eval()/exec()",
     re.compile(r"(?<![\w.])(eval|exec)\s*\("),
     "Nahradit konkretnim parsovanim (ast.literal_eval, json.loads)."),
    ("SEC_PICKLE_LOADS", "critical", "pickle.loads na (potencialne) cizich datech",
     re.compile(r"pickle\.loads?\s*\("),
     "Pickle umi spustit kod - pouzit JSON."),
    ("SEC_SHELL_TRUE", "warning", "subprocess se shell=True",
     re.compile(r"shell\s*=\s*True"),
     "Predat argumenty jako seznam bez shell=True; pokud shell nutny, shlex.quote()."),
    ("SEC_YAML_LOAD", "warning", "yaml.load bez Loaderu",
     re.compile(r"yaml\.load\s*\((?![^)]*Loader)"),
     "yaml.safe_load()."),
    ("SEC_FLASK_DEBUG", "critical", "Flask debug=True",
     re.compile(r"debug\s*=\s*True"),
     "Debug rezim da komukoli interaktivni konzoli - v produkci nikdy."),
    ("SEC_JWT_ALG_NONE", "critical", "JWT s algoritmem none",
     re.compile(r"(?i)algorithm[s]?\s*=\s*\[?\s*['\"]none['\"]"),
     "Vynutit konkretni alg (HS256/RS256) a overovat podpis."),
]


# --- SQL injection: dataflow, ne holy regex ---------------------------------
#
# Naivni regex "execute( f'..." hlasi v tomhle repu 112 mist, a skoro vsechna
# jsou BEZPECNY idiom: hodnoty jdou pres %s a f-string vklada jen IDENTIFIKATORY
# sestavene v kodu (`{', '.join(fields)}`, `{','.join(['%s']*len(ids))}`).
# Takovy report je k nicemu - 112 "critical" nikdo neprojde. Rozhoduje proto,
# ODKUD interpolovana promenna pochazi: kdyz z requestu (nebo je to parametr
# view funkce), je to skutecny kandidat na injection; kdyz z literalu/whitelistu,
# neni to nalez.
REQUEST_SOURCE_RE = re.compile(
    r"\brequest\.|\bget_json\b|\.args\b|\.form\b|\.values\b|\.files\b|"
    r"\bpayload\b|\bbody\b")
PLACEHOLDER_ONLY_RE = re.compile(r"^[\s,%s'\"\[\]()*+]*$")


def _interpolated_names(arg):
    """Jmena promennych vlozenych do SQL retezce (f-string nebo konkatenace)."""
    names = set()
    if isinstance(arg, ast.JoinedStr):
        for part in arg.values:
            if isinstance(part, ast.FormattedValue):
                names |= {n.id for n in ast.walk(part.value) if isinstance(n, ast.Name)}
    elif isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Add, ast.Mod)):
        names |= {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)}
    return names


def _assignment_sources(func_node):
    """{jmeno: [zdrojovy vyraz prirazeni, ...]} v ramci jedne funkce."""
    out = {}
    for n in ast.walk(func_node):
        if isinstance(n, ast.Assign):
            try:
                value = ast.unparse(n.value)
            except Exception:  # noqa: BLE001
                value = ""
            for t in n.targets:
                for name in (x.id for x in ast.walk(t) if isinstance(x, ast.Name)):
                    out.setdefault(name, []).append(value)
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)) and getattr(n, "value", None) is not None:
            try:
                value = ast.unparse(n.value)
            except Exception:  # noqa: BLE001
                value = ""
            for name in (x.id for x in ast.walk(n.target) if isinstance(x, ast.Name)):
                out.setdefault(name, []).append(value)
    return out



_WHITELIST_JOIN_RE = re.compile(
    r"""\.join\(.*\bfor\s+(\w+)\s+in\s+(\w+)""", re.S)


def _is_whitelist_join(expr):
    """True pro `', '.join(f'{f}=%s' for f in FIELDS if f in body)`, kde se
    do SQL dostavaji jen prvky z FIELDS. Podminka `if ... in body` jen
    filtruje, hodnoty jdou parametrem - to neni injection."""
    m = _WHITELIST_JOIN_RE.search(expr)
    if not m:
        return False
    loop_var, source = m.group(1), m.group(2)
    # zdroj iterace nesmi byt primo z requestu
    if REQUEST_SOURCE_RE.search(source):
        return False
    # do retezce se vklada jen promenna cyklu (ne treba body[f])
    interpolated = re.findall(r"\{([^{}]+)\}", expr)
    return bool(interpolated) and all(
        part.strip() == loop_var for part in interpolated)


_CALLERS_CACHE = {}


def _all_calls():
    """{jmeno_funkce: [(rel, lineno, [pozicni argumenty], {kwargy})]} napric api/*.py."""
    if _CALLERS_CACHE:
        return _CALLERS_CACHE
    for py in sorted(glob.glob(os.path.join(API_DIR, "*.py"))):
        rel = os.path.relpath(py, REPO_ROOT)
        try:
            tree = ast.parse(open(py, encoding="utf-8").read(), filename=py)
        except SyntaxError:
            continue
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call):
                continue
            fn = call.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
            if not name:
                continue
            try:
                pos = [ast.unparse(a) for a in call.args]
                kw = {k.arg: ast.unparse(k.value) for k in call.keywords if k.arg}
            except Exception:  # noqa: BLE001
                continue
            _CALLERS_CACHE.setdefault(name, []).append((rel, call.lineno, pos, kw))
    return _CALLERS_CACHE


def _param_taint_from_callers(func_name, param_name, func_node):
    """Co volajici predavaji do `param_name`? -> ('safe'|'tainted'|'unknown', dukaz)"""
    order = [a.arg for a in func_node.args.args]
    try:
        idx = order.index(param_name)
    except ValueError:
        return "unknown", "parametr nenalezen v signature"
    calls = _all_calls().get(func_name, [])
    if not calls:
        return "unknown", "zadne volani v api/*.py (volano odjinud?)"
    values = []
    for rel, line, pos, kw in calls:
        if param_name in kw:
            values.append((rel, line, kw[param_name]))
        elif idx < len(pos):
            values.append((rel, line, pos[idx]))
    if not values:
        return "unknown", "volajici parametr nepredavaji (vychozi hodnota)"
    for rel, line, expr in values:
        if REQUEST_SOURCE_RE.search(expr):
            return "tainted", f"{rel}:{line} predava {expr[:60]}"
    if all(re.match(r"""^\s*(['"]).*\1\s*$""", v[2]) for v in values):
        return "safe", f"vsech {len(values)} volani predava literal"
    sample = "; ".join(f"{r}:{l} {e[:40]}" for r, l, e in values[:3])
    return "unknown", f"{len(values)} volani, napr. {sample}"


def check_sql_injection(findings, stats):
    checked = flagged = 0
    for py in sorted(glob.glob(os.path.join(API_DIR, "*.py"))):
        rel = os.path.relpath(py, REPO_ROOT)
        if rel.endswith("qa_checks.py"):
            continue
        try:
            tree = ast.parse(open(py, encoding="utf-8").read(), filename=py)
        except SyntaxError:
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = {a.arg for a in func.args.args} | {a.arg for a in func.args.kwonlyargs}
            assigns = _assignment_sources(func)
            for call in ast.walk(func):
                if not isinstance(call, ast.Call):
                    continue
                fn = call.func
                if not isinstance(fn, ast.Attribute) or fn.attr not in ("execute", "executemany"):
                    continue
                if not call.args:
                    continue
                names = _interpolated_names(call.args[0])
                if not names:
                    continue
                checked += 1
                tainted, unknown = [], []
                for name in sorted(names):
                    sources = assigns.get(name, [])
                    if any(_is_whitelist_join(s) for s in sources):
                        # `", ".join(f"{f}=%s" for f in FIELDS if f in body)` -
                        # nazvy sloupcu pochazi z literalniho whitelistu, request
                        # jen VYBIRA, ktere z nich se pouziji, hodnoty jdou pres
                        # %s. Overeno rucne na api/crm.py:1533. Bez teto vyjimky
                        # skript hlasi bezpecny idiom jako critical.
                        continue
                    if any(REQUEST_SOURCE_RE.search(s) for s in sources):
                        tainted.append(f"{name} = {sources[0][:70]}")
                    elif name in params and not sources:
                        # Parametr funkce sam o sobe nic nedokazuje - rozhoduje,
                        # CO do nej predavaji volajici. Bez tohohle kroku hlasi
                        # skript kazdou pomocnou funkci typu _method_admin_crud(table)
                        # jako critical, i kdyz ji vsichni volaji s literalem.
                        verdict, evidence = _param_taint_from_callers(func.name, name, func)
                        if verdict == "tainted":
                            tainted.append(f"{name} <- {evidence}")
                        elif verdict == "unknown":
                            unknown.append(f"{name} ({evidence})")
                    elif not sources:
                        unknown.append(name)
                if not tainted and not unknown:
                    continue
                try:
                    snippet = ast.unparse(call)[:200]
                except Exception:  # noqa: BLE001
                    snippet = ""
                flagged += 1
                if tainted:
                    findings.append(finding(
                        "critical", "SEC_SQL_INTERPOLATION_FROM_REQUEST",
                        "Do SQL se vklada hodnota odvozena z requestu",
                        f"{snippet}\n  podezrele: {'; '.join(tainted)}",
                        where=f"{rel}:{call.lineno}",
                        fix_hint="Hodnoty predavat parametrem (%s), identifikatory "
                                 "(nazvy sloupcu/tabulek) overit proti pevnemu whitelistu, "
                                 "ne poskladat z uzivatelskeho vstupu."))
                else:
                    findings.append(finding(
                        "info", "SEC_SQL_INTERPOLATION_UNKNOWN_ORIGIN",
                        "SQL vklada promennou, jejiz puvod skript neurcil",
                        f"{snippet}\n  promenne: {', '.join(unknown)}",
                        where=f"{rel}:{call.lineno}",
                        fix_hint="Rucne overit, ze promenna pochazi z literalu/whitelistu. "
                                 "Pokud ano, neni to nalez."))
    stats["sql_interpolation_sites"] = checked
    stats["sql_interpolation_flagged"] = flagged


def _iter_py_lines():
    for py in sorted(glob.glob(os.path.join(API_DIR, "*.py"))):
        rel = os.path.relpath(py, REPO_ROOT)
        try:
            for i, line in enumerate(open(py, encoding="utf-8"), 1):
                yield rel, i, line
        except OSError:
            continue


def check_code_patterns(findings, stats):
    hits = 0
    for rel, i, line in _iter_py_lines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for code, sev, title, rx, hint in CODE_RULES:
            if not rx.search(line):
                continue
            # qa_checks.py sam obsahuje tyhle vzory jako REGEXY, ne jako volani
            if rel.endswith("qa_checks.py"):
                continue
            hits += 1
            findings.append(finding(
                sev, code, title, f"{stripped[:220]}", where=f"{rel}:{i}",
                fix_hint=hint + " (Kazdy vyskyt overit rucne - regex hlasi i legitimni pripady.)"))
    stats["code_pattern_hits"] = hits

    # send_file / os.path.join s uzivatelskym vstupem -> path traversal
    trav = 0
    for rel, i, line in _iter_py_lines():
        if "send_file" not in line and "send_from_directory" not in line:
            continue
        if re.search(r"send_file\s*\(\s*(?:os\.path\.join\s*\()?[^)]*\b(request|args|form|json|filename|path|name)\b", line):
            trav += 1
            findings.append(finding(
                "warning", "SEC_SEND_FILE_USER_PATH",
                "send_file s cestou odvozenou z uzivatelskeho vstupu",
                line.strip()[:220], where=f"{rel}:{i}",
                fix_hint="Overit, ze se jmeno normalizuje (os.path.basename / werkzeug "
                         "secure_filename) a ze vysledek lezi POD povolenym adresarem "
                         "(os.path.realpath + startswith). Jinak hrozi ../ traversal."))
    stats["send_file_user_path"] = trav


def check_secret_key_and_hashing(findings, stats):
    app_py = os.path.join(API_DIR, "app.py")
    try:
        src = open(app_py, encoding="utf-8").read()
    except OSError:
        return
    m = re.search(r"secret_key\s*=\s*(.+)", src)
    if m:
        expr = m.group(1).strip()
        if re.match(r"""^['"]""", expr) or "dev" in expr.lower() or "change" in expr.lower():
            findings.append(finding(
                "critical", "SEC_HARDCODED_SECRET_KEY",
                "Flask SECRET_KEY vypada napevno/vychozi",
                f"api/app.py: secret_key = {expr[:80]}",
                where="api/app.py",
                fix_hint="Nacitat z prostredi (os.environ['FLASK_SECRET_KEY']) a v .env mit "
                         "dlouhou nahodnou hodnotu; pri zmene se odhlasi vsichni."))

    algos = {
        "werkzeug generate_password_hash": "generate_password_hash",
        "bcrypt": "bcrypt",
        "argon2": "argon2",
        "hashlib.md5": "md5(",
        "hashlib.sha1": "sha1(",
        "hashlib.sha256 (holy)": "sha256(",
    }
    found = {}
    for rel, i, line in _iter_py_lines():
        if "password" not in line.lower() and "heslo" not in line.lower():
            continue
        for label, needle in algos.items():
            if needle in line:
                found.setdefault(label, []).append(f"{rel}:{i}")
    stats["password_hash_algos"] = {k: v[:3] for k, v in found.items()}
    for weak in ("hashlib.md5", "hashlib.sha1", "hashlib.sha256 (holy)"):
        if weak in found:
            findings.append(finding(
                "critical", "SEC_WEAK_PASSWORD_HASH",
                f"Hesla se zrejme hashuji pres {weak}",
                f"Vyskyty: {', '.join(found[weak][:5])}", where=found[weak][0],
                fix_hint="Pouzit bcrypt/argon2 nebo werkzeug generate_password_hash "
                         "(pbkdf2 s dostatecnym poctem iteraci). Holy SHA/MD5 je "
                         "pro hesla prolomitelny hrubou silou."))


def check_public_post_protections(findings, stats):
    """Verejne (nechranene) POST routy - co jim staticky chybi."""
    routes = parse_routes()
    public_posts = [r for r in routes
                    if not r["protected"] and any(m != "GET" for m in r["methods"])]
    stats["public_post_routes"] = len(public_posts)
    src_cache = {}

    def src_of(rel):
        if rel not in src_cache:
            src_cache[rel] = open(os.path.join(REPO_ROOT, rel), encoding="utf-8").read()
        return src_cache[rel]

    interesting = re.compile(r"(?i)(register|login|forgot|reset|password|contact|kontakt|"
                             r"poptav|inquir|markup|cart|kosik|order|objednav|upload|email)")
    checked = 0
    for r in public_posts:
        if not interesting.search(r["path"] + " " + r["func"]):
            continue
        checked += 1
        try:
            src = src_of(r["file"])
        except OSError:
            continue
        # telo funkce (hrube: od def po dalsi def na urovni 0)
        body = src.split(f"def {r['func']}(", 1)[-1][:4000]
        missing = []
        if not re.search(r"(?i)(rate|limit|throttle|attempts|pokusy)", body):
            missing.append("omezeni poctu pokusu per IP")
        if not re.search(r"(?i)(honeypot|hp_field|bot_field)", body):
            missing.append("honeypot pole")
        if not re.search(r"(?i)(len\(|MAX_|max_length|content_length|size)", body):
            missing.append("limit velikosti tela/poli")
        if re.search(r"(?i)email", body) and not re.search(r"(?i)(@|validate|regex|re\.match|EMAIL_RE)", body):
            missing.append("validace e-mailu")
        if missing:
            findings.append(finding(
                "info", "SEC_PUBLIC_POST_MISSING_GUARDS",
                "Verejny POST endpoint bez zjevnych ochran",
                f"{r['methods']} {r['path']} ({r['func']}) - chybi: {', '.join(missing)}. "
                "Heuristika nad telem funkce, over rucne.",
                where=f"{r['file']}:{r['line']}",
                fix_hint="U verejnych formularu se hodi aspon: limit pokusu per IP "
                         "(napr. jednoducha tabulka/pamet + okno), honeypot pole, "
                         "MAX_CONTENT_LENGTH a validace formatu."))
    stats["public_post_checked"] = checked

    # Upload routy - whitelist pripon, limit velikosti, cil mimo webroot
    for r in public_posts:
        if "upload" not in (r["path"] + r["func"]).lower():
            continue
        try:
            src = src_of(r["file"])
        except OSError:
            continue
        gaps = []
        if not re.search(r"(?i)(ALLOWED_EXT|allowed_extensions|splitext)", src):
            gaps.append("whitelist pripon")
        if not re.search(r"(?i)(MAX_UPLOAD|MAX_CONTENT_LENGTH|content_length)", src):
            gaps.append("limit velikosti")
        if not re.search(r"(?i)(magic|imghdr|Image\.open|filetype)", src):
            gaps.append("kontrola magic bytes")
        if gaps:
            findings.append(finding(
                "warning", "SEC_UPLOAD_MISSING_GUARDS",
                "Verejny upload bez plne validace",
                f"{r['path']} ({r['func']}) - chybi: {', '.join(gaps)}",
                where=f"{r['file']}:{r['line']}",
                fix_hint="Whitelist pripon + kontrola skutecneho typu (magic bytes) + "
                         "limit velikosti + ukladat mimo webroot pod vygenerovanym jmenem."))


def check_secrets_and_perms(findings, stats):
    env_path = os.path.join(API_DIR, ".env")
    try:
        st = os.stat(env_path)
        mode = stat.S_IMODE(st.st_mode)
        stats["env_mode"] = oct(mode)
        if mode & 0o077:
            findings.append(finding(
                "critical", "SEC_ENV_PERMISSIONS",
                "api/.env je citelny i pro ostatni uzivatele",
                f"prava {oct(mode)}, vlastnik uid={st.st_uid}", where="api/.env",
                fix_hint="chmod 600 api/.env a vlastnika nastavit na uzivatele sluzby."))
    except OSError as e:
        findings.append(finding("info", "SEC_ENV_UNREADABLE", "api/.env nelze overit",
                                repr(e), where="api/.env"))

    # .gitignore pokryti
    try:
        gi = open(os.path.join(REPO_ROOT, ".gitignore"), encoding="utf-8").read()
    except OSError:
        gi = ""
    for needed in ["api/.env", "backups/", "private-files/", "qa-reports/",
                   "scripts/qa/.venv", "PRISTUPY.md"]:
        base = needed.rstrip("/")
        if base not in gi:
            findings.append(finding(
                "warning", "SEC_GITIGNORE_GAP", f"{needed} neni v .gitignore",
                "Hrozi commitnuti tajemstvi/velkych dat.", where=".gitignore",
                fix_hint=f"Pridat radek `{needed}`."))

    # Tajemstvi v HISTORII gitu (ne jen v aktualnich souborech).
    #
    # OPRAVA (bot18, 2026-09-03) - puvodni podoba byla rozbita v OBOU smerech:
    #  (a) FALESNE POZITIVNI NA SEBE: hledala doslovny retezec "BEGIN PRIVATE
    #      KEY" pres `-S`, jenze presne ten retezec je v TOMHLE souboru nize
    #      jako argument `-G`/text hlasky. Jedina shoda v celych 6642 commitech
    #      byl commit a93fd2b, ktery pridal tuhle suitu - hlasilo se to jako
    #      "critical: v historii gitu je privatni klic" a vedlo k uvaham o
    #      rotaci klice a prepisu historie, ktery nikdy nebyl potreba.
    #      Reseni: pathspec vylouceni scripts/qa/ (sken SLEDOVANYCH souboru nize
    #      uz to delal, sken historie jako jediny ne).
    #  (b) FALESNE NEGATIVNI NA SKUTECNE KLICE: doslovny retezec "BEGIN PRIVATE
    #      KEY" NENI podretezcem "BEGIN RSA PRIVATE KEY" ani "BEGIN OPENSSH
    #      PRIVATE KEY" - realne uniknuty klic techto (nejcastejsich) typu by
    #      kontrola minula. Reseni: `-G` s regexem pres vsechny varianty,
    #      shodnym s _SECRET_PATTERNS vyse.
    # Overeno pri oprave: stary dotaz 1 shoda (sam sebe), novy 0 shod, a regex
    # prokazatelne chyta podstrceny "-----BEGIN OPENSSH PRIVATE KEY-----".
    # `-p` odstraneno zamerne - s `--oneline` michalo radky patche do poctu
    # commitu, takze i hlaska "vratil N radku" byla zavadejici.
    rc, out = run_cmd(["git", "-C", REPO_ROOT, "log", "--all", "--oneline",
                       "-G", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
                       "--", ".", ":(exclude)scripts/qa/"], timeout=120)
    if rc == 0 and out.strip():
        commits = [ln.split(" ", 1)[0] for ln in out.splitlines() if ln.strip()]
        findings.append(finding(
            "critical", "SEC_PRIVATE_KEY_IN_GIT_HISTORY",
            "V historii gitu je privatni klic",
            f"PEM hlavicka privatniho klice se objevuje v {len(commits)} commitech: "
            + ", ".join(commits[:5]) + ("..." if len(commits) > 5 else ""),
            where="git history",
            fix_hint="Klic povazovat za kompromitovany a vygenerovat novy. Prepis "
                     "historie (git filter-repo) az po domluve s Robertem - u MRTVEHO "
                     "credentialu je precedens historii NEprepisovat (rozbiti hashu pro "
                     "soubezne worktree prevazuje nad zbytkovym rizikem, viz AGENTS_LOG "
                     "2026-09-03)."))

    # Tajemstvi v aktualne sledovanych souborech.
    #
    # Nalezy SESKUPUJEME podle hodnoty (hash), ne podle souboru: jedno heslo
    # zkopirovane do 23 skriptu je JEDEN problem k vyreseni, ne 23 radek v
    # reportu. Zavaznost urcuje, jestli jde o ZIVY udaj - porovnava se hash
    # proti api/.env, samotna hodnota se nikam nevypisuje ani neloguje.
    live_hashes = {}
    try:
        env = load_env()
        for k in ("DB_PASSWORD", "DB_USER", "SMTP_PASSWORD", "FLASK_SECRET_KEY",
                  "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            if env.get(k):
                live_hashes[hashlib.sha256(env[k].encode()).hexdigest()] = k
    except Exception:  # noqa: BLE001
        pass

    HIGH_RISK_LABELS = {"OpenAI/Anthropic klic", "AWS klic", "Slack token", "privatni klic"}
    groups = {}
    rc, tracked = run_cmd(["git", "-C", REPO_ROOT, "ls-files"], timeout=60)
    if rc == 0:
        for rel in tracked.splitlines():
            if not rel.endswith((".py", ".js", ".html", ".md", ".json", ".sh", ".conf")):
                continue
            if rel.startswith(("node_modules/", "scripts/qa/")):
                continue
            full = os.path.join(REPO_ROOT, rel)
            try:
                if os.path.getsize(full) > 2_000_000:
                    continue
                content = open(full, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for label, rx in SECRET_PATTERNS:
                for m in rx.finditer(content):
                    line_no = content[:m.start()].count("\n") + 1
                    raw = m.group(0)
                    value = m.group(1)
                    digest = hashlib.sha256(value.encode()).hexdigest()
                    key = (label, digest)
                    groups.setdefault(key, {"places": [], "sample": raw})
                    groups[key]["places"].append(f"{rel}:{line_no}")
    hits = sum(len(g["places"]) for g in groups.values())
    stats["secret_hits_tracked"] = hits
    stats["secret_groups"] = len(groups)

    for (label, digest), info in sorted(groups.items(), key=lambda kv: -len(kv[1]["places"])):
        places = info["places"]
        sample = info["sample"]
        masked = (sample[:8] + "…" + sample[-3:]) if len(sample) > 14 else "…"
        live_key = live_hashes.get(digest)
        if live_key:
            findings.append(finding(
                "critical", "SEC_LIVE_CREDENTIAL_IN_GIT",
                f"ZIVY udaj ({live_key}) je natvrdo v {len(places)} sledovanych souborech",
                f"Hodnota se shoduje s {live_key} v api/.env (porovnano hashem, "
                f"hodnota se nikde nevypisuje). Vyskyty: {', '.join(places[:6])}"
                + (f" … a dalsich {len(places)-6}" if len(places) > 6 else ""),
                where=places[0],
                fix_hint=f"1) Rotovat {live_key}. 2) Skripty prepsat na cteni z api/.env "
                         "(vzor: scripts/qa/_common.py::load_env). 3) Zvazit prepis "
                         "historie gitu - hodnota je i ve starych commitech."))
        elif label in HIGH_RISK_LABELS:
            findings.append(finding(
                "critical", "SEC_API_KEY_IN_GIT",
                f"Klic/token typu '{label}' je ve sledovanych souborech",
                f"maskovana ukazka: {masked}; vyskyty: {', '.join(places[:6])}",
                where=places[0],
                fix_hint="Povazovat za kompromitovany: rotovat u vydavatele, presunout do "
                         ".env (gitignored) a odstranit z historie gitu."))
        else:
            findings.append(finding(
                "warning", "SEC_SECRET_IN_TRACKED_FILE",
                f"Mozne tajemstvi ve sledovanych souborech ({label})",
                f"maskovana ukazka: {masked}; vyskyty ({len(places)}): "
                f"{', '.join(places[:6])}",
                where=places[0],
                fix_hint="Pokud jde o skutecne tajemstvi: rotovat, presunout do .env "
                         "a odstranit z gitu vcetne historie."))

    # world-writable soubory
    ww = []
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "venv", ".venv")]
        for name in files:
            p = os.path.join(root, name)
            try:
                if stat.S_IMODE(os.lstat(p).st_mode) & stat.S_IWOTH:
                    ww.append(os.path.relpath(p, REPO_ROOT))
            except OSError:
                continue
        if len(ww) > 50:
            break
    stats["world_writable"] = len(ww)
    if ww:
        findings.append(finding(
            "warning", "SEC_WORLD_WRITABLE",
            f"{len(ww)} souboru je zapisovatelnych pro kohokoli",
            "Ukazka: " + ", ".join(ww[:10]), where=REPO_ROOT,
            fix_hint="chmod o-w na dotcene soubory."))


# ------------------------------------------------------------- system


def run_cmd(cmd, timeout=30):
    """(rc, stdout+stderr). rc=-1 kdyz prikaz vubec nesel spustit
    (chybejici binarka, zamitnute opravneni) - volajici to hlasi jako
    'neslo overit', ne jako 'v poradku'."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:  # noqa: BLE001
        return -1, repr(e)


def check_system(findings, stats):
    rc, out = run_cmd(["ss", "-tlnH"])
    if rc != 0:
        findings.append(finding("info", "SEC_SKIPPED_PORTS", "Nesel zjistit seznam portu",
                                out[:200], where="ss -tln",
                                fix_hint="Spustit suitu s pravy, kde `ss` funguje."))
    else:
        public = []
        for line in out.splitlines():
            m = re.search(r"(\S+):(\d+)\s", line)
            if not m:
                continue
            addr, port = m.group(1), int(m.group(2))
            if addr in ("127.0.0.1", "[::1]", "::1"):
                continue
            if port in (80, 443, 22):
                continue
            public.append(f"{addr}:{port}")
        stats["public_ports"] = public
        for p in public:
            sev = "critical" if p.endswith((":3306", ":5432", ":6379", ":27017", ":11211")) else "warning"
            findings.append(finding(
                sev, "SEC_PUBLIC_PORT", f"Port {p} naslouchá mimo localhost",
                f"`ss -tln` ukazuje {p} na verejnem rozhrani.", where=p,
                fix_hint="Pokud sluzba nema byt zvenku dostupna, navazat ji na 127.0.0.1 "
                         "nebo zavrit ve firewallu."))

    rc, out = run_cmd(["systemctl", "cat", "konfigurator"])
    if rc == 0:
        unit = out
        stats["unit_read"] = True
        user_m = re.search(r"(?m)^User=(.+)$", unit)
        if not user_m:
            findings.append(finding(
                "warning", "SEC_SERVICE_RUNS_AS_ROOT",
                "konfigurator.service nema User= (bezi tedy jako root)",
                "V unitu neni direktiva User=.", where="/etc/systemd/system/konfigurator.service",
                fix_hint="User=www-data (a odpovidajici prava na private-files/, "
                         "content-files/) - kompromitace appky pak nedava rovnou root."))
        elif user_m.group(1).strip() == "root":
            findings.append(finding(
                "warning", "SEC_SERVICE_RUNS_AS_ROOT",
                "konfigurator.service bezi jako root", f"User={user_m.group(1)}",
                where="/etc/systemd/system/konfigurator.service",
                fix_hint="Prepnout na neprivilegovaneho uzivatele."))
        for directive, hint in [
            ("NoNewPrivileges", "NoNewPrivileges=yes"),
            ("ProtectSystem", "ProtectSystem=full (nebo strict + ReadWritePaths=)"),
            ("PrivateTmp", "PrivateTmp=yes"),
        ]:
            if directive not in unit:
                findings.append(finding(
                    "info", "SEC_SERVICE_HARDENING",
                    f"systemd unit nema {directive}",
                    "Doporucene zpevneni sluzby chybi.",
                    where="/etc/systemd/system/konfigurator.service",
                    fix_hint=f"Do [Service] pridat {hint}"))
    else:
        findings.append(finding("info", "SEC_SKIPPED_UNIT", "Nesel precist systemd unit",
                                out[:200], where="systemctl cat konfigurator"))

    rc, out = run_cmd(["ufw", "status"])
    if rc == 0:
        stats["ufw"] = out.splitlines()[0] if out else ""
        if "inactive" in out.lower():
            findings.append(finding(
                "warning", "SEC_FIREWALL_INACTIVE", "ufw je neaktivni",
                out.strip()[:200], where="ufw status",
                fix_hint="Zapnout firewall a povolit jen 22/80/443 (pozor na porty "
                         "jinych projektu na teze VPS - projit s Robertem)."))
    else:
        findings.append(finding("info", "SEC_SKIPPED_FIREWALL", "Nesel zjistit stav firewallu",
                                out[:200], where="ufw status"))

    rc, out = run_cmd(["systemctl", "is-active", "fail2ban"])
    if rc != 0 or "inactive" in out:
        findings.append(finding(
            "info", "SEC_NO_FAIL2BAN", "fail2ban nebezi",
            f"is-active: {out.strip()[:80]}", where="fail2ban",
            fix_hint="Zvazit fail2ban na sshd (a pripadne nginx) - levna obrana proti "
                     "hadani hesel. POZOR: nezavadet rate-limit testy naziva."))

    try:
        sshd = open("/etc/ssh/sshd_config", encoding="utf-8").read()
        stats["sshd_read"] = True
        if re.search(r"(?mi)^\s*PermitRootLogin\s+yes", sshd):
            findings.append(finding(
                "warning", "SEC_SSH_ROOT_LOGIN", "SSH povoluje prihlaseni roota",
                "PermitRootLogin yes", where="/etc/ssh/sshd_config",
                fix_hint="PermitRootLogin prohibit-password (nebo no)."))
        if re.search(r"(?mi)^\s*PasswordAuthentication\s+yes", sshd):
            findings.append(finding(
                "warning", "SEC_SSH_PASSWORD_AUTH", "SSH povoluje prihlaseni heslem",
                "PasswordAuthentication yes", where="/etc/ssh/sshd_config",
                fix_hint="Prejit na klice a nastavit PasswordAuthentication no."))
    except OSError as e:
        findings.append(finding("info", "SEC_SKIPPED_SSHD", "Nesel precist sshd_config",
                                repr(e)[:200], where="/etc/ssh/sshd_config"))


def check_tls(bases, findings, stats):
    for base in bases:
        if not base.startswith("https://"):
            continue
        host = host_of(base).split(":")[0]
        # Expirace certifikatu
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ss:
                    cert = ss.getpeercert()
                    stats["tls_version"] = ss.version()
            import datetime as _dt
            exp = _dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            days = (exp - _dt.datetime.utcnow()).days
            stats["cert_days_left"] = days
            if days < 14:
                findings.append(finding(
                    "critical", "SEC_CERT_EXPIRING", "Certifikat brzy vyprsi",
                    f"{host}: zbyva {days} dni (do {cert['notAfter']})", where=host,
                    fix_hint="Overit certbot renew timer."))
            elif days < 30:
                findings.append(finding(
                    "warning", "SEC_CERT_EXPIRING", "Certifikat vyprsi do mesice",
                    f"{host}: zbyva {days} dni", where=host,
                    fix_hint="Overit certbot renew timer."))
        except Exception as e:  # noqa: BLE001
            findings.append(finding("info", "SEC_TLS_CHECK_FAILED",
                                    "Nesel overit certifikat", repr(e)[:200], where=host))

        # Stare protokoly MUSI selhat
        for proto, name in ((ssl.TLSVersion.TLSv1, "TLS 1.0"), (ssl.TLSVersion.TLSv1_1, "TLS 1.1")):
            try:
                c = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                c.check_hostname = False
                c.verify_mode = ssl.CERT_NONE
                c.minimum_version = proto
                c.maximum_version = proto
                with socket.create_connection((host, 443), timeout=8) as sock:
                    with c.wrap_socket(sock, server_hostname=host):
                        findings.append(finding(
                            "warning", "SEC_OLD_TLS_ENABLED",
                            f"Server prijima {name}", f"{host} navazal spojeni pres {name}.",
                            where=host,
                            fix_hint="V nginx `ssl_protocols TLSv1.2 TLSv1.3;`"))
            except Exception:
                pass  # spravne odmitnuto


def check_nginx_conf(findings, stats):
    candidates = glob.glob("/etc/nginx/sites-enabled/*konfigurator*") + \
                 glob.glob("/etc/nginx/sites-available/*konfigurator*")
    if not candidates:
        findings.append(finding("info", "SEC_SKIPPED_NGINX_CONF",
                                "Nginx konfigurace konfiguratoru nenalezena/necitelna",
                                "Hledano v /etc/nginx/sites-{enabled,available}/*konfigurator*",
                                where="/etc/nginx"))
        return
    path = candidates[0]
    try:
        conf = open(path, encoding="utf-8").read()
    except OSError as e:
        findings.append(finding("info", "SEC_SKIPPED_NGINX_CONF", "Nginx conf necitelna",
                                repr(e)[:200], where=path))
        return
    stats["nginx_conf"] = path
    if "client_max_body_size" not in conf:
        findings.append(finding(
            "info", "SEC_NGINX_NO_BODY_LIMIT", "Nginx nema client_max_body_size",
            "Bez limitu muze jeden request zabrat hodne pameti/disku.", where=path,
            fix_hint="client_max_body_size 25M; (podle nejvetsiho legitimniho uploadu)"))
    if "limit_req" not in conf:
        findings.append(finding(
            "info", "SEC_NGINX_NO_RATE_LIMIT", "Nginx nema zadnou limit_req zonu",
            "Prihlasovaci/verejne POST cesty nemaji limit na urovni nginx.", where=path,
            fix_hint="limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m; "
                     "a limit_req zone=login burst=5 nodelay; na /api/admin/login. "
                     "POZOR: nasazovat po domluve, ne pri behu QA."))
    if re.search(r"autoindex\s+on", conf):
        findings.append(finding(
            "warning", "SEC_NGINX_AUTOINDEX_ON", "Nginx ma nekde autoindex on",
            "Directory listing zverejnuje strukturu adresaru.", where=path,
            fix_hint="autoindex off;"))


def check_dependencies(findings, stats, enabled):
    if not enabled:
        stats["deps_checked"] = False
        return
    venv_py = os.path.join(REPO_ROOT, "api", "venv", "bin", "python")
    if not os.path.exists(venv_py):
        findings.append(finding("info", "SEC_SKIPPED_DEPS", "Produkcni venv nenalezen",
                                venv_py, where=venv_py))
        return
    rc, out = run_cmd([venv_py, "-m", "pip", "list", "--outdated", "--format=json"], timeout=120)
    if rc == 0:
        try:
            outdated = json.loads(out[out.find("["):]) if "[" in out else []
        except json.JSONDecodeError:
            outdated = []
        stats["outdated_packages"] = len(outdated)
        risky = [p for p in outdated
                 if p.get("name", "").lower() in
                 ("flask", "werkzeug", "jinja2", "gunicorn", "requests", "urllib3",
                  "pillow", "cryptography", "pymysql", "sqlalchemy")]
        for p in risky:
            findings.append(finding(
                "info", "SEC_OUTDATED_DEPENDENCY",
                f"Zastaraly balicek {p['name']}",
                f"{p['name']} {p.get('version')} -> {p.get('latest_version')}",
                where="api/requirements.txt",
                fix_hint="Projit changelog a aktualizovat v testovacim okne "
                         "(bezpecnostni opravy Werkzeug/Flask/Pillow byvaji zasadni)."))
    else:
        findings.append(finding("info", "SEC_SKIPPED_DEPS", "pip list --outdated selhal",
                                out[:200], where=venv_py))

    qa_venv_audit = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "pip-audit")
    if os.path.exists(qa_venv_audit):
        rc, out = run_cmd([qa_venv_audit, "-f", "json",
                           "-r", os.path.join(REPO_ROOT, "api", "requirements.txt")], timeout=180)
        if rc in (0, 1) and out.strip().startswith("{"):
            try:
                data = json.loads(out)
            except json.JSONDecodeError:
                data = {}
            vulns = data.get("dependencies", [])
            n = 0
            for dep in vulns:
                for v in dep.get("vulns", []):
                    n += 1
                    findings.append(finding(
                        "warning", "SEC_KNOWN_CVE",
                        f"Znama zranitelnost v {dep.get('name')}",
                        f"{v.get('id')}: {(v.get('description') or '')[:200]}",
                        where=f"{dep.get('name')} {dep.get('version')}",
                        fix_hint=f"Aktualizovat na {v.get('fix_versions')}"))
            stats["pip_audit_vulns"] = n
    else:
        findings.append(finding(
            "info", "SEC_PIP_AUDIT_MISSING", "pip-audit neni nainstalovany",
            "Kontrola proti databazi CVE se nespustila.", where="scripts/qa/.venv",
            fix_hint="python3 -m venv scripts/qa/.venv && "
                     "scripts/qa/.venv/bin/pip install pip-audit  (mimo produkcni venv)"))


# ---------------------------------------------------------------- main


def collect(args):
    findings, stats = [], {"bases": args.base}
    check_code_patterns(findings, stats)
    check_sql_injection(findings, stats)
    check_secret_key_and_hashing(findings, stats)
    check_public_post_protections(findings, stats)
    check_secrets_and_perms(findings, stats)
    check_nginx_conf(findings, stats)
    check_system(findings, stats)
    check_dependencies(findings, stats, args.deps)
    if not args.no_net:
        check_route_auth(args.base, findings, stats)
        check_sensitive_paths(args.base, findings, stats)
        check_headers(args.base, findings, stats)
        check_cors_and_cookies(args.base, findings, stats)
        check_tls(args.base, findings, stats)
    return findings, stats


def main():
    ap = argparse.ArgumentParser(description="QA suita: bezpecnost (read-only)")
    ap.add_argument("--json", action="store_true", help="strojovy vystup")
    ap.add_argument("--base", action="append", default=None,
                    help=f"testovana URL (opakovatelne); vychozi: {DEFAULT_BASES}")
    ap.add_argument("--no-net", action="store_true", help="jen staticke/systemove kontroly")
    ap.add_argument("--deps", action="store_true",
                    help="i kontrola zavislosti (pomalejsi, sahá na pip)")
    args = ap.parse_args()
    args.base = args.base or DEFAULT_BASES
    run_suite("security", lambda: collect(args), args.json)


if __name__ == "__main__":
    main()
