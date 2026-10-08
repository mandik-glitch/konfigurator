#!/opt/konfigurator/api/venv/bin/python3
"""Nasazeni serveroveho kodu BEZ VYPADKU (gunicorn HUP) - planovane i rucni.

bot16, 2026-10-01, Robert pres bot3: "uz me nebavi delat restart". Za 7 dni
162 commitu do api/*.py a skoro kazdy chtel restart, ktery musel pustit Robert
(sandbox ho botum blokuje). Misto restartu ad hoc se nasazuje v davkach, v
pevny cas (0:00 a 12:30 Europe/Prague; nocni termin presunut z 3:30 na pulnoc 2026-10-04, Robert: nasazeni nema bezet v dobe zaloh 3:30-4:30), bez vypadku.

JAK TO FUNGUJE
  konfigurator.service ma ExecReload = `kill -HUP`. Gunicorn bezi BEZ --preload,
  takze pri HUP nahraje kod znovu z disku: spusti nove workery a stare ukonci.
  ZMERENO (zkusebni gunicorn 22.0.0, 4 workery, unix socket, atrapa aplikace,
  2 659 + 2 577 pozadavku behem HUP, nabeh 4 s a 15 s): ZADNY pozadavek nespadl,
  pozadavek rozbehnuty v okamziku HUP se dokoncil. POZOR, HUP nemeni workery
  postupne: vymeni se VSECHNY najednou a obsluha se zastavi na dobu nabehu
  novych workeru (skutecna aplikace ~4 s, `import app`). Pozadavky v tu chvili
  nepadaji, jen CEKAJI v backlogu socketu. Proto "bez vypadku" = bez chyb, ne
  bez 4s pauzy. Kazdy skutecny beh to meri znovu (sonda na /api/health) a
  vysledek zapisuje do tabulky deploy_runs.

  POZOR NA CACHE: hodinovy cron /etc/cron.hourly/free (`echo 1 > drop_caches`, od
  2026-08-28) shazuje systemovou cache VZDY V :17 (+0 az 16 s). Kdyz HUP padne do
  teto chvile, nove workery nacitaji vsechny moduly z disku a obsluha misto ~4 s
  stoji i 30 s (zmereno 2026-10-01 17:17:04, rucni nasazeni: 33,5 s, nic nespadlo).
  Planovane terminy (0:00 a 12:30) jsou daleko od :17, ale rucne spustene nasazeni
  po cekani na zamek se tam trefit muze, proto nasazeni v okne :16:30 az :17:25
  pocka (pockej_na_hodinovy_drop_caches). Preflight navic cache pred HUP ohreje.

CO SE NASAZUJE
  Jen to, co je COMMITNUTE. HUP nacte, co lezi na disku, takze pri necommitnute
  zmene v api/*.py by se nasadila rozdelana prace (presne ten incident, kvuli
  kteremu vznikl scripts/restart_konfigurator.sh). Planovany beh proto pri
  jakekoli necommitnute zmene v api/*.py NEnasazuje a vypise, ktery soubor to je
  a cim se da poznat, ci je. Git o autorovi necommitnute zmeny nevi nic a vsichni
  boti commituji pod jednim git uzivatelem (konfigurator-deploy), takze se pouziva
  drzitel DEPLOY_LOCK + cas zmeny + posledni commit souboru.

  Co ma ceka, se pocita z casu: kod bezi od startu NEJSTARSIHO workeru, ceka kazdy
  commit do api/*.py mladsi nez ten cas. Funguje to i po rucnim restartu nebo
  padu workeru, nejen po nasazeni tímto skriptem.

BEZ OBET
  Lokalni (CPU) render bezi UVNITR gunicornu a HUP ho zabije (viz
  restart_konfigurator.sh, "DRUHA SLEPA SKVRNA"). Planovany beh ho proto pocka
  (az 30 min), a kdyz neskonci, nasazeni PRESKOCI do dalsiho terminu.

AUTOMAT (WORKFLOW.md pravidlo 28) - pojistky na kazde vrstve
  * jedna instance: flock (/run/konfigurator-nasazeni.lock) + systemd oneshot
  * tvrdy strop: cekani na blokatory max 30 min, preflight/nabeh/kontroly maji
    vlastni limity, jednotka ma TimeoutStartSec; zadne opakovani ve smycce
  * idempotence: beh bez commitu od startu workeru NIC nereloaduje ("nic")
  * pozorovatelny stav: kazdy beh (i preskoceny a "nic") je radek v deploy_runs,
    ukazuje se na Dashboardu (panel Nasazeni serveru) a v `--stav`
  * selhani NIKDY e-mailem (pravidlo 16): jen Dashboard + zaznam v bot_handover

Pouziti:
  nasazeni.py --planovane            # systemd timer: striktni, ceka na blokatory, zapisuje
  nasazeni.py --rucni [--force]      # rucni reload; --force = kontroly uz probehly (vola ho
                                     # restart_konfigurator.sh --reload)
  nasazeni.py --stav [--json]        # kdy pujde kod ven, co ceka, posledni nasazeni (pro boty)
  nasazeni.py --planovane|--rucni --zkouska   # jen verdikt, nic nereloaduje ani nezapisuje

Zkouska bez systemd (jen pro vyvoj): NASAZENI_TEST_PID=<pid mastera gunicornu>,
NASAZENI_SOCKET=<socket>, NASAZENI_TEST_WORKERS=<n>, NASAZENI_BEZ_DB=1,
NASAZENI_BEZ_IMPORTU=1, NASAZENI_LOCK=<soubor>, NASAZENI_SMOKE="/ /x".
"""
import argparse
import datetime
import fcntl
import glob
import http.client
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
PY = os.path.join(REPO, "api", "venv", "bin", "python3")

SLUZBA = os.environ.get("NASAZENI_SLUZBA", "konfigurator.service")
TIMER = "konfigurator-nasazeni.timer"
SOCKET = os.environ.get("NASAZENI_SOCKET", os.path.join(REPO, "api", "konfigurator.sock"))
# Terminy musi sedet s deploy/konfigurator-nasazeni.timer a api/deploy_runs.py.
OKNA = ("00:00", "12:30")
TZ = ZoneInfo("Europe/Prague")
CEKANI_MAX_S = int(os.environ.get("NASAZENI_CEKANI_MAX_S", str(30 * 60)))
# Krok 15 s (puvodne 60): kontrola blokatoru stoji zlomek vteriny a drzitele zamku se strida i kvuli kratkemu zapisu do
# AGENTS_LOG/TASKS - pri rucne spustenem nasazeni (Robert ceka) je minuta mezi pokusy zbytecne dlouha.
CEKANI_KROK_S = int(os.environ.get("NASAZENI_CEKANI_KROK_S", "15"))
NABEH_MAX_S = int(os.environ.get("NASAZENI_NABEH_MAX_S", "120"))
STABILIZACE_S = float(os.environ.get("NASAZENI_STABILIZACE_S", "8"))
RENDER_DIR = os.environ.get("RESTART_RENDER_DIR", os.path.join(REPO, "private-files", "blender-renders"))
LOCK_PATH = os.environ.get("NASAZENI_LOCK", "/run/konfigurator-nasazeni.lock")
PATHSPEC_API = ":(glob)api/*.py"        # jen primo api/*.py (venv a podadresare ne)
PATHSPEC_JAZYKY = ":(glob)api/jazyky/*.json"   # datove sady dalsich jazyku (api/jazyky.py je pripoji pri startu): commit samotneho JSON musi nasazeni spustit
PATHSPECY_API = (PATHSPEC_API, PATHSPEC_JAZYKY)
HEALTH_URL = "/api/health"
# Pravidlo 33 (WORKFLOW.md): po nasazeni se overuje i endpoint s DB a SSR, ne jen /api/health.
SMOKE = tuple(os.environ.get("NASAZENI_SMOKE", "").split()) or (HEALTH_URL, "/api/shop/products?page_size=1", "/")
SMOKE_HOST = "autovestavby.logiman.cz"
NGINX_LOG = os.environ.get("NASAZENI_NGINX_LOG", "/var/log/nginx/access.log")
TEST_PID = os.environ.get("NASAZENI_TEST_PID")
BEZ_DB = os.environ.get("NASAZENI_BEZ_DB") == "1"
BEZ_IMPORTU = os.environ.get("NASAZENI_BEZ_IMPORTU") == "1"

DDL = """CREATE TABLE IF NOT EXISTS deploy_runs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  trigger_type VARCHAR(16) NOT NULL,
  status VARCHAR(24) NOT NULL,
  reason VARCHAR(600) NULL,
  head_before VARCHAR(40) NULL,
  head_after VARCHAR(40) NULL,
  commits_count INT NOT NULL DEFAULT 0,
  commits_json MEDIUMTEXT NULL,
  detail_json MEDIUMTEXT NULL,
  duration_s DECIMAL(8,2) NULL,
  requested_by VARCHAR(40) NULL,
  KEY idx_deploy_runs_started (started_at),
  KEY idx_deploy_runs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci"""


# ---------------------------------------------------------------------------
# pomocne
# ---------------------------------------------------------------------------
def ted():
    return datetime.datetime.now()


def log(msg):
    print("[%s] %s" % (ted().strftime("%H:%M:%S"), msg), flush=True)


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout po %ss: %s" % (timeout, " ".join(cmd[:3]))
    except OSError as e:
        return 127, "", str(e)


def git(*args, timeout=30):
    # -c safe.directory: stejnou logiku pouziva i api/deploy_runs.py (www-data, repo patri rootovi)
    return run(["git", "-c", "safe.directory=" + REPO, "-C", REPO] + list(args), timeout)


def git_head():
    return git("rev-parse", "HEAD")[1].strip()


# ---------------------------------------------------------------------------
# sluzba (systemd nebo zkusebni instance)
# ---------------------------------------------------------------------------
def _pid_zivy(pid):
    """Proces existuje a neni zombie (zkusebni gunicorn je potomek zkusebniho skriptu)."""
    try:
        with open("/proc/%s/stat" % pid) as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] not in ("Z", "X")
    except (OSError, IndexError):
        return False


class Sluzba:
    """konfigurator.service; s NASAZENI_TEST_PID zkusebni gunicorn bez systemd."""

    def aktivni(self):
        if TEST_PID:
            return _pid_zivy(TEST_PID)
        return run(["systemctl", "is-active", SLUZBA], 10)[1].strip() == "active"

    def master_pid(self):
        if TEST_PID:
            return int(TEST_PID) if _pid_zivy(TEST_PID) else None
        try:
            return int(run(["systemctl", "show", SLUZBA, "-p", "MainPID", "--value"], 10)[1].strip()) or None
        except ValueError:
            return None

    def workery(self, master=None):
        """[(pid, stari_s)] primych potomku mastera = gunicorn workery."""
        master = master or self.master_pid()
        if not master:
            return []
        res = []
        for r in run(["ps", "-o", "pid=,etimes=", "--ppid", str(master)], 10)[1].splitlines():
            p = r.split()
            if len(p) == 2 and p[0].isdigit() and p[1].isdigit():
                res.append((int(p[0]), int(p[1])))
        return res

    def pocet_workeru_cfg(self):
        if os.environ.get("NASAZENI_TEST_WORKERS"):
            return int(os.environ["NASAZENI_TEST_WORKERS"])
        m = re.search(r"--workers[ =](\d+)", run(["systemctl", "show", SLUZBA, "-p", "ExecStart", "--value"], 10)[1])
        return int(m.group(1)) if m else None

    def reload(self):
        if TEST_PID:
            os.kill(int(TEST_PID), signal.SIGHUP)
            return True, ""
        rc, out, err = run(["systemctl", "reload", SLUZBA], 30)
        return rc == 0, (err or out).strip()

    def journal(self, od, do=None):
        if TEST_PID:
            return ""
        cmd = ["journalctl", "-u", SLUZBA, "--no-pager", "-o", "cat", "--since", "@%d" % int(od)]
        if do:
            cmd += ["--until", "@%d" % int(do)]
        return run(cmd, 60)[1]


# ---------------------------------------------------------------------------
# co ceka a co blokuje
# ---------------------------------------------------------------------------
def bezi_od(workery):
    """Epoch startu NEJSTARSIHIHO workeru (kod bezi nejmene od tohoto casu)."""
    return time.time() - max(st for _, st in workery) if workery else None


def commity_od(epoch):
    """Commity zasahujici api/*.py mladsi nez epoch, nejnovejsi prvni."""
    out = git("log", "-n", "400", "--format=%h%x1f%ct%x1f%s", "--", *PATHSPECY_API)[1]
    res = []
    for r in out.splitlines():
        p = r.split("\x1f", 2)
        if len(p) == 3 and p[1].isdigit() and int(p[1]) > epoch:
            res.append({"hash": p[0], "ts": int(p[1]), "predmet": p[2][:160]})
    return res


def necommitnute_api():
    """[(stav, cesta)] necommitnute zmeny v api/*.py (vcetne novych souboru)."""
    res = []
    for r in git("status", "--porcelain", "--", *PATHSPECY_API)[1].splitlines():
        if len(r) < 4:
            continue
        cesta = r[3:].strip().strip('"')
        if " -> " in cesta:
            cesta = cesta.split(" -> ", 1)[1].strip('"')
        res.append((r[:2].strip() or "?", cesta))
    return res


def zamek():
    try:
        with open(os.path.join(REPO, "DEPLOY_LOCK.json"), encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    if not d.get("held_by"):
        return None
    since = None
    try:
        since = datetime.datetime.fromisoformat(d["since"]).timestamp()
    except Exception:  # noqa: BLE001
        pass
    return {"bot": d["held_by"], "since": since, "since_txt": d.get("since", ""), "note": d.get("note", "")}


def napoveda_vlastnika(cesta, zam):
    """VODITKO, ci je rozdelana zmena (ne dukaz)."""
    cast = []
    try:
        mt = os.path.getmtime(os.path.join(REPO, cesta))
    except OSError:
        mt = None
    if mt:
        cast.append("zmeneno %s" % datetime.datetime.fromtimestamp(mt).strftime("%H:%M:%S"))
        if zam and zam.get("since") and mt >= zam["since"]:
            cast.append("po vzeti zamku botem %s" % zam["bot"])
        if not BEZ_DB:
            try:
                from _env import get_conn
                conn = get_conn()
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT bot_id FROM bots WHERE last_checkin_at BETWEEN %s AND %s ORDER BY bot_id",
                                    (datetime.datetime.fromtimestamp(mt - 60), datetime.datetime.fromtimestamp(mt + 900)))
                        boti = [r["bot_id"] for r in cur.fetchall()]
                finally:
                    conn.close()
                if boti:
                    cast.append("kratce po zmene byli naposledy videni: %s" % ", ".join(boti))
            except Exception:  # noqa: BLE001 - voditko nesmi shodit nasazeni
                pass
    posledni = git("log", "-1", "--format=%h %s (%cr)", "--", cesta)[1].strip()
    if posledni:
        cast.append("naposledy commitnuto: %s" % posledni[:110])
    return "; ".join(cast)


def lokalni_render():
    """Bezi lokalni (CPU) render uvnitr gunicornu? (port z restart_konfigurator.sh)"""
    radky = []
    for f in sorted(glob.glob(os.path.join(RENDER_DIR, "*.status.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                st = json.load(fh)
        except (OSError, ValueError):
            continue
        if st.get("state") not in ("running", "queued") or st.get("on_worker"):
            continue
        job = os.path.basename(f)[: -len(".status.json")]
        bezi = " | bezi %d min" % int((time.time() - st["started"]) // 60) if st.get("started") else ""
        hotovo = ""
        n = len(glob.glob(os.path.join(RENDER_DIR, job + ".frames", "*.jpg")))
        if n:
            hotovo = " | hotovo %d/%s snimku" % (n, st.get("expected_frames") or "?")
        radky.append("%s | sestava %s | stav %s%s%s" % (job[:12], st.get("assembly_id"), st.get("state"), bezi, hotovo))
    return radky


def blokatory(rezim, force):
    """Co brani nasazeni TED. Prazdny seznam = muze se."""
    if force:
        return []
    res = []
    zam = zamek()
    dirty = necommitnute_api()
    if dirty:
        popis = [{"soubor": c, "stav": s, "napoveda": napoveda_vlastnika(c, zam)} for s, c in dirty]
        res.append({"druh": "necommitnute", "text": "necommitnuté změny v api/*.py: " + ", ".join(p["soubor"] for p in popis),
                    "soubory": popis})
    if zam and rezim == "plan":
        res.append({"druh": "zamek", "text": "DEPLOY_LOCK drží %s od %s (%s)" % (zam["bot"], zam["since_txt"][11:19], zam["note"][:80])})
    r = lokalni_render()
    if r:
        res.append({"druh": "render", "text": "běží LOKÁLNÍ render, který by HUP zabil", "radky": r})
    return res


def text_blokatoru(bl):
    cast = []
    for b in bl:
        cast.append(b["text"])
        for s in b.get("soubory", []):
            cast.append("   %s [%s] - %s" % (s["soubor"], s["stav"], s["napoveda"]))
        for r in b.get("radky", []):
            cast.append("   " + r)
    return "\n".join(cast)


POMALA_PAUZA_S = 15       # obsluha po HUP stala dyl nez toto (obvykle ~5 s) -> varovani v panelu


def pockej_na_hodinovy_drop_caches(detail, zkouska=False):
    """Hodinovy cron /etc/cron.hourly/free shazuje systemovou cache v :17 (zmereno: :17:01 az :17:16). HUP v tu chvili
    znamena, ze nove workery nactou vsechny moduly z prazdne cache a obsluha stoji ~30 s misto ~4 s (2026-10-01 17:17:04).
    Proto se v okne :16:30 az :17:25 pocka; preflight, ktery nasleduje, cache zase ohreje."""
    if TEST_PID or zkouska:
        return
    n = ted()
    s = n.minute * 60 + n.second
    od, do = 16 * 60 + 30, 17 * 60 + 25
    if od <= s < do:
        cekat = do - s
        log("hodinový cron shazuje cache v :17 - čekám %d s, ať se nové workery nenačítají z prázdné cache" % cekat)
        time.sleep(cekat)
        detail["cekani_na_drop_caches_s"] = cekat


# ---------------------------------------------------------------------------
# preflight: nabehnou nove workery? (jinak by HUP shodil celou sluzbu)
# ---------------------------------------------------------------------------
def preflight():
    """(ok, text, import_s). Gunicorn pri `Worker failed to boot` ukonci CELEHO mastera, takze
    vadny commit by pri HUP znamenal skutecny vypadek. Proto se pred HUP overi, ze
    1) vsechny api/*.py maji platnou syntaxi (compile v pameti, bez zapisu .pyc),
    2) `import app` projde jako www-data presne tak, jak ho nacte worker."""
    chyby = []
    for f in sorted(glob.glob(os.path.join(REPO, "api", "*.py"))):
        try:
            with open(f, "rb") as fh:
                compile(fh.read(), f, "exec")
        except SyntaxError as e:
            chyby.append("%s:%s %s" % (os.path.relpath(f, REPO), e.lineno, e.msg))
    if chyby:
        return False, "syntaktická chyba: " + "; ".join(chyby[:5]), None
    if BEZ_IMPORTU:
        return True, "", None
    cmd = ["systemd-run", "--pipe", "--wait", "--quiet", "--collect", "-p", "User=www-data", "-p", "Group=www-data",
           "-p", "EnvironmentFile=" + os.path.join(REPO, "api", ".env"), "-p", "WorkingDirectory=" + os.path.join(REPO, "api"),
           "-p", "RuntimeMaxSec=150", PY, "-c",
           "import time; t=time.time(); import app; print('IMPORT_OK %.2f' % (time.time()-t))"]
    rc, out, err = run(cmd, 170)
    m = re.search(r"IMPORT_OK ([\d.]+)", out)
    if rc != 0 or not m:
        konec = [x for x in (err or out).strip().splitlines() if x.strip()][-4:]
        return False, "`import app` selhal: " + " | ".join(konec)[:400], None
    return True, "", float(m.group(1))


# ---------------------------------------------------------------------------
# HTTP pres unix socket + sonda
# ---------------------------------------------------------------------------
class _UnixConn(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__("localhost", timeout=timeout)
        self._sock_path = path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self._sock_path)
        self.sock = s


def http_get(url, timeout=60):
    t0 = time.time()
    try:
        c = _UnixConn(SOCKET, timeout)
        c.request("GET", url, headers={"Host": SMOKE_HOST})
        r = c.getresponse()
        r.read()
        c.close()
        return {"t": t0, "dt": time.time() - t0, "status": r.status, "err": None}
    except Exception as e:  # noqa: BLE001
        return {"t": t0, "dt": time.time() - t0, "status": None, "err": repr(e)[:120]}


class Sonda(threading.Thread):
    """Behem reloadu porad vola /api/health pres socket a meri, jestli neco spadlo a jak dlouho obsluha stala."""

    def __init__(self, interval=0.1):
        super().__init__(daemon=True)
        self.interval = interval
        self.vysledky = []
        self._stop_evt = threading.Event()

    def run(self):
        while not self._stop_evt.is_set():
            self.vysledky.append(http_get(HEALTH_URL, timeout=90))
            self._stop_evt.wait(self.interval)

    def zastav(self):
        self._stop_evt.set()
        self.join(timeout=100)

    def shrnuti(self):
        v = self.vysledky
        chyby = [x for x in v if x["status"] != 200]
        ok = sorted(x["t"] + x["dt"] for x in v if x["status"] == 200)
        return {
            "pozadavku": len(v), "selhalo": len(chyby),
            "max_latence_s": round(max((x["dt"] for x in v), default=0.0), 2),
            "nejdelsi_pauza_s": round(max((b - a for a, b in zip(ok, ok[1:])), default=0.0), 2),
            "chyby": [x["err"] or ("HTTP %s" % x["status"]) for x in chyby[:5]],
        }


def pockej_na_workery(sl, master, stare, ocekavano, limit_s):
    """(ok, proc_ne, [pidy novych workeru]) - vsechny stare pryc, novych aspon `ocekavano`."""
    t0 = time.time()
    while time.time() - t0 < limit_s:
        if sl.master_pid() != master:
            return False, "master se během reloadu změnil nebo zanikl (restart služby?)", []
        pidy = {p for p, _ in sl.workery(master)}
        nove = pidy - stare
        if len(nove) >= ocekavano and not (pidy & stare):
            return True, "", sorted(nove)
        time.sleep(0.5)
    return False, "workery se do %d s nevyměnily" % limit_s, []


# ---------------------------------------------------------------------------
# kontroly po nasazeni
# ---------------------------------------------------------------------------
FATAL_RE = re.compile(r"Worker failed to boot|HaltServer|Exception in worker process|Shutting down: Master")
SIGKILL_RE = re.compile(r"was sent SIGKILL|WORKER TIMEOUT")
TB_START = re.compile(r"^Traceback \(most recent call last\):")
# Pad arbitra gunicornu 22 (2026-10-02 17:37): SIGCHLD handler loguje do stderr, zatimco hlavni vlakno zrovna pise log ->
# "RuntimeError: reentrant call inside <_io.BufferedWriter name='<stderr>'>" -> "Unhandled exception in main loop" -> arbiter skonci,
# systemd ho po RestartSec spusti znovu (vypadek ~20 s). Opatreni: api/gunicorn.conf.py (logging.raiseExceptions = False).
ARBITER_PAD_RE = re.compile(r"Unhandled exception in main loop|reentrant call inside")


def traceback_podpisy(text):
    """['VyjimkaTyp: zprava @ soubor.py:radek'] - podpis = vyjimka + posledni ramec NASEHO kodu (ne venv)."""
    lines = text.splitlines()
    res, i = [], 0
    while i < len(lines):
        if TB_START.match(lines[i]):
            j, nas = i + 1, ""
            while j < len(lines) and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
                m = re.search(r'File "([^"]+)", line (\d+)', lines[j])
                if m and "/opt/konfigurator/api/" in m.group(1) and "/api/venv/" not in m.group(1):
                    nas = "%s:%s" % (os.path.basename(m.group(1)), m.group(2))
                j += 1
            res.append("%s @ %s" % (lines[j].strip()[:160] if j < len(lines) else "?", nas or "?"))
            i = j
        i += 1
    return res


def zkontroluj_journal(sl, t_hup):
    po = sl.journal(t_hup)
    pred = set(traceback_podpisy(sl.journal(t_hup - 1800, t_hup)))
    po_pod = traceback_podpisy(po)
    return {
        "fatalni": [l.strip()[:160] for l in po.splitlines() if FATAL_RE.search(l)][:5],
        "sigkill": [l.strip()[:160] for l in po.splitlines() if SIGKILL_RE.search(l)][:5],
        "arbiter_pad": [l.strip()[:160] for l in po.splitlines() if ARBITER_PAD_RE.search(l)][:3],
        # novy podpis = takovy, ktery se v 30 minutach PRED HUP nevyskytl (stara, uz znama chyba
        # nejineho endpointu nema nasazeni oznacit za vadne)
        "nove_tracebacky": [p for p in dict.fromkeys(po_pod) if p not in pred][:5],
        "tracebacku_celkem": len(po_pod),
        "workeru_nabootovalo": len(re.findall(r"Booting worker with pid", po)),
    }


def nasi_hostitele():
    hosts = set()
    for path in glob.glob("/etc/nginx/sites-enabled/*"):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                obsah = fh.read()
        except OSError:
            continue
        if "konfigurator_api" not in obsah and "konfigurator.sock" not in obsah:
            continue
        for radek in obsah.splitlines():
            r = radek.strip()
            if r.startswith("#"):
                continue
            m = re.search(r"server_name\s+([^;\n]+);", r)
            if m:
                hosts.update(h.lower() for h in m.group(1).split())
    return hosts


NGX_RE = re.compile(r'\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})\] "[^"]*" (\d{3}) .* host=(\S+)')


def nginx_5xx(od, do):
    """Kolik 502/503/504 dostali navstevnici nasich domen v okne [od, do] (log je spolecny pro cele VPS)."""
    try:
        size = os.path.getsize(NGINX_LOG)
        with open(NGINX_LOG, "rb") as fh:
            fh.seek(max(0, size - 12 * 1024 * 1024))
            data = fh.read().decode("utf-8", "replace")
    except OSError as e:
        return {"pocet": None, "poznamka": "log nelze cist: %s" % e}
    hosts = nasi_hostitele()
    n = 0
    for radek in data.splitlines():
        m = NGX_RE.search(radek)
        if not m or m.group(2) not in ("502", "503", "504") or m.group(3).lower() not in hosts:
            continue
        try:
            ts = datetime.datetime.strptime(m.group(1), "%d/%b/%Y:%H:%M:%S %z").timestamp()
        except ValueError:
            continue
        if od <= ts <= do:
            n += 1
    return {"pocet": n}


# ---------------------------------------------------------------------------
# zaznam do DB (deploy_runs) a hlaseni selhani
# ---------------------------------------------------------------------------
def db_conn():
    from _env import get_conn
    return get_conn()


def zacni_beh(trigger, kdo):
    if BEZ_DB:
        return None
    try:
        conn = db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(DDL)
                cur.execute("UPDATE deploy_runs SET status='prerusen', finished_at=NOW(), "
                            "reason='proces zanikl, aniž zapsal výsledek' "
                            "WHERE status='bezi' AND started_at < NOW() - INTERVAL 2 HOUR")
                cur.execute("INSERT INTO deploy_runs (started_at, trigger_type, status, head_before, requested_by) "
                            "VALUES (NOW(), %s, 'bezi', %s, %s)", (trigger, git_head(), kdo))
                rid = cur.lastrowid
            conn.commit()
            return rid
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001 - zapis nesmi shodit nasazeni
        log("ZAPIS DO deploy_runs SELHAL (nasazeni pokracuje): %s" % e)
        return None


def ukonci_beh(rid, status, reason, commity, detail, t0):
    if not rid:
        return
    try:
        conn = db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE deploy_runs SET finished_at=NOW(), status=%s, reason=%s, head_after=%s, commits_count=%s, "
                    "commits_json=%s, detail_json=%s, duration_s=%s WHERE id=%s",
                    (status, (reason or "")[:600], git_head(), len(commity or []),
                     json.dumps((commity or [])[:200], ensure_ascii=False),
                     json.dumps(detail, ensure_ascii=False, default=str), round(time.time() - t0, 2), rid))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        log("ZAPIS VYSLEDKU DO deploy_runs SELHAL: %s" % e)


def hlas_selhani(reason, detail):
    """Hlasite pro boty: radek v bot_handover (status blocked) - stejny vzor jako lock_watchdog. ZADNY e-mail."""
    if BEZ_DB:
        return
    try:
        run([PY, os.path.join(REPO, "scripts", "handover.py"), "add", "--bot", "system-nasazeni", "--project", "konfigurator",
             "--topic", "NASAZENI-SELHALO: " + reason[:110], "--status", "blocked", "--body",
             "Plánované nasazení serveru selhalo.\n\n%s\n\nDetail: Dashboard → panel Nasazení serveru, nebo "
             "`scripts/restart_konfigurator.sh --stav`.\n%s" % (reason, json.dumps(detail, ensure_ascii=False, default=str)[:1500])], 30)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# hlavni tok
# ---------------------------------------------------------------------------
def zamkni():
    fh = open(LOCK_PATH, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        return None
    return fh


def nasad(rezim, zkouska=False, force=False):
    """rezim 'plan' (timer) | 'rucni'. Vraci exit kod: 0 = ok/preskoceno/nic, 1 = selhalo."""
    t0 = time.time()
    kdo = os.environ.get("BOT_ID") or ("timer" if rezim == "plan" else "ručně")
    sl = Sluzba()
    detail = {"rezim": rezim}
    commity = []
    rid = None
    lockfh = None

    def konec(status, reason, kod):
        log("%s: %s" % (status.upper(), reason))
        if zkouska:
            return kod
        ukonci_beh(rid, status, reason, commity, detail, t0)
        if status == "selhalo":
            hlas_selhani(reason, detail)
        return kod

    if not zkouska:
        lockfh = zamkni()
        if lockfh is None:
            log("jiné nasazení právě běží - končím")
            return 0 if rezim == "plan" else 2
        rid = zacni_beh(rezim, kdo)

    try:
        if not sl.aktivni():
            return konec("selhalo", "služba %s neběží; automat ji nestartuje (ručně: systemctl start %s)" % (SLUZBA, SLUZBA), 1)
        master = sl.master_pid()
        workery0 = sl.workery(master)
        cfg = sl.pocet_workeru_cfg() or len(workery0)
        detail["workery_pred"] = len(workery0)
        detail["workery_cfg"] = cfg
        od = float(os.environ["NASAZENI_BEZI_OD"]) if os.environ.get("NASAZENI_BEZI_OD") else bezi_od(workery0)  # env jen pro testy
        if od is None:
            return konec("selhalo", "nenašel jsem workery gunicornu (master %s)" % master, 1)
        commity = commity_od(od)
        log("kód běží od %s, čeká %d commitů do api/*.py" % (datetime.datetime.fromtimestamp(od).strftime("%Y-%m-%d %H:%M:%S"), len(commity)))

        if rezim == "plan" and not commity:
            return konec("nic", "od startu workerů nebyl žádný commit do api/*.py - nebylo co nasazovat", 0)

        # po varovani v tomto okne se automat neopakuje (viz varovani_v_okne)
        if rezim == "plan" and not force:
            pv = varovani_v_okne(time.time())
            if pv:
                detail["predchozi_varovani"] = pv
                return konec("preskoceno", ("poslední nasazení (#%s v %s) v tomto okně skončilo VAROVÁNÍM - automat se v témže okně neopakuje. "
                                            "Zkontroluj příčinu (panel Nasazení serveru); další termín %s nebo vědomě `scripts/nasazeni.py --rucni`."
                                            % (pv["id"], pv["kdy"], dalsi_okno().strftime("%d.%m. %H:%M")))[:590], 0)

        # blokatory: planovany beh ceka (strop 30 min), rucni rozhodl uz volajici
        t_cek = time.time()
        bl = blokatory(rezim, force)
        while bl and rezim == "plan" and not zkouska and time.time() - t_cek < CEKANI_MAX_S:
            log("blokuje nasazení (zkusím znovu za %d s):\n%s" % (CEKANI_KROK_S, text_blokatoru(bl)))
            time.sleep(CEKANI_KROK_S)
            commity = commity_od(od)
            bl = blokatory(rezim, force)
        detail["cekani_s"] = round(time.time() - t_cek)
        if bl:
            detail["blokatory"] = bl
            if zkouska:
                print("[zkouska] nasazení by se PŘESKOČILO:\n" + text_blokatoru(bl))
                return 0
            if rezim == "plan":
                return konec("preskoceno", "nasazení přeskočeno do dalšího termínu (%d min čekání):\n%s"
                             % (CEKANI_MAX_S // 60, text_blokatoru(bl))[:590], 0)
            print("ODMÍTNUTO:\n" + text_blokatoru(bl) + "\n(--force přeskočí kontroly)")
            return konec("preskoceno", "ruční nasazení odmítnuto:\n" + text_blokatoru(bl)[:560], 1)

        pockej_na_hodinovy_drop_caches(detail, zkouska)
        ok, proc_ne, import_s = preflight()
        detail["preflight_import_s"] = import_s
        if not ok:
            return konec("selhalo", "NIC SE NENASADILO, služba běží dál na starém kódu. Preflight: " + proc_ne, 1)
        if zkouska:
            print("[zkouska] nasazení by proběhlo: %d commitů, preflight OK%s, workerů %d"
                  % (len(commity), " (import %.1f s)" % import_s if import_s else "", len(workery0)))
            for c in commity[:15]:
                print("   %s %s" % (c["hash"], c["predmet"]))
            return 0

        # Mezi kontrolou blokatoru a HUP uplynul preflight (~4 s): jeste jednou, at se nenasadi neco, co
        # mezitim nekdo zacal psat. (Dal uz jen kontrola po nasazeni - viz "necommitnute_po".)
        if rezim == "plan":
            bl2 = blokatory(rezim, force)
            if bl2:
                detail["blokatory"] = bl2
                return konec("preskoceno", ("těsně před HUP se objevila blokace, nasazení přeskočeno do dalšího termínu:\n%s"
                                            % text_blokatoru(bl2))[:590], 0)

        # --- HUP ---------------------------------------------------------
        stare = {p for p, _ in workery0}
        sonda = Sonda()
        sonda.start()
        time.sleep(1.0)
        t_hup = time.time()
        okr, err = sl.reload()
        if not okr:
            sonda.zastav()
            return konec("selhalo", "reload selhal: %s" % err, 1)
        log("HUP odeslán, čekám na nové workery (%d)" % cfg)
        nabehly, proc_ne, nove = pockej_na_workery(sl, master, stare, cfg, NABEH_MAX_S)
        # POZOR: tohle je cas, za ktery VZNIKLY procesy novych workeru - ne konec jejich importu.
        # Skutecnou pauzu obsluhy meri sonda nize (`nejdelsi_pauza_s`).
        detail["workery_vznik_s"] = round(time.time() - t_hup, 1)
        problemy, varovani = [], []
        if not nabehly:
            problemy.append(proc_ne)
        else:
            time.sleep(STABILIZACE_S)
            ws2 = {p for p, _ in sl.workery(master)}
            if ws2 != set(nove):
                varovani.append("workery se během stabilizace měnily (restart workeru?)")
            detail["workery_po"] = len(ws2)

        # health + smoke (pravidlo 33)
        smoke = {}
        for url in SMOKE:
            r = None
            for _ in range(15 if url == HEALTH_URL else 3):
                r = http_get(url, timeout=30)
                if r["status"] == 200:
                    break
                time.sleep(2)
            smoke[url] = {"status": r["status"], "ms": int(r["dt"] * 1000), "chyba": r["err"]}
            if r["status"] != 200:
                problemy.append("endpoint %s vrací %s%s" % (url, r["status"], " (%s)" % r["err"] if r["err"] else ""))
        detail["smoke"] = smoke

        sonda.zastav()
        t_konec = time.time()
        detail["sonda"] = sonda.shrnuti()
        if detail["sonda"]["selhalo"]:
            varovani.append("během reloadu selhalo %d požadavků na /api/health: %s"
                            % (detail["sonda"]["selhalo"], "; ".join(detail["sonda"]["chyby"][:2])))
        if detail["sonda"]["nejdelsi_pauza_s"] > POMALA_PAUZA_S:
            varovani.append("obsluha po HUP stála %s s (obvykle ~5 s): pomalý start aplikace, zkontroluj zátěž serveru "
                            "a hodinový drop_caches v :17" % ("%.1f" % detail["sonda"]["nejdelsi_pauza_s"]).replace(".", ","))

        j = zkontroluj_journal(sl, t_hup)
        detail["journal"] = j
        if j["fatalni"]:
            problemy.append("journal: " + j["fatalni"][0])
        if j["nove_tracebacky"]:
            varovani.append("nové tracebacky po nasazení: " + " || ".join(j["nove_tracebacky"][:2]))
        master_po = sl.master_pid()
        if j["arbiter_pad"] or (master_po and master and master_po != master):
            detail["arbiter_restart"] = {"master_pred": master, "master_po": master_po, "journal": j["arbiter_pad"][:2]}
            varovani.append("ARBITER GUNICORNU SPADL a systemd ho restartoval (MainPID %s → %s%s) - obsluha stála při HUP ~20 s; "
                            "příčina viz api/gunicorn.conf.py a scripts/nasazeni.py (ARBITER_PAD_RE)"
                            % (master, master_po, "; journal: " + j["arbiter_pad"][0] if j["arbiter_pad"] else ""))
        if j["sigkill"]:
            varovani.append("worker zabit násilím (rozdělaný požadavek byl delší než graceful timeout): " + j["sigkill"][0])

        ngx = nginx_5xx(t_hup - 2, t_konec + 5)
        detail["nginx_5xx"] = ngx
        if ngx.get("pocet"):
            varovani.append("nginx vrátil návštěvníkům %d× 502/503/504 v okně nasazení" % ngx["pocet"])

        dirty_po = necommitnute_api()
        if dirty_po and not force:
            detail["necommitnute_po"] = [c for _, c in dirty_po]
            varovani.append("během nasazení přibyla necommitnutá změna v api/*.py (%s) - mohl se nasadit nedodělaný kód"
                            % ", ".join(c for _, c in dirty_po[:3]))

        sh = ("%d commitů; po HUP obsluha stála %s s (workery se vyměnily najednou, požadavky čekaly), "
              "selhalo %d z %d požadavků na /api/health; %d workerů"
              % (len(commity), ("%.1f" % detail["sonda"]["nejdelsi_pauza_s"]).replace(".", ","), detail["sonda"]["selhalo"],
                 detail["sonda"]["pozadavku"], detail.get("workery_po", 0)))
        if problemy:
            return konec("selhalo", "; ".join(problemy)[:590], 1)
        if varovani:
            return konec("varovani", (sh + " | POZOR: " + " ; ".join(varovani))[:590], 0)
        return konec("ok", sh, 0)
    except Exception:  # noqa: BLE001
        detail["vyjimka"] = traceback.format_exc()[-1500:]
        return konec("selhalo", "interní chyba skriptu nasazeni.py: %s" % traceback.format_exc().strip().splitlines()[-1][:300], 1)
    finally:
        if lockfh:
            lockfh.close()


# ---------------------------------------------------------------------------
# --stav (pro boty; Dashboard ma vlastni cteni v api/deploy_runs.py)
# ---------------------------------------------------------------------------
def okno_od(ts):
    """Zacatek planovaneho okna, do ktereho cas ts patri = posledni termin z OKNA (00:00 / 12:30 Europe/Prague) <= ts."""
    dt = datetime.datetime.fromtimestamp(ts, TZ)
    kand = []
    for den in (0, -1):
        for hhmm in OKNA:
            h, m = map(int, hhmm.split(":"))
            d = (dt + datetime.timedelta(days=den)).replace(hour=h, minute=m, second=0, microsecond=0)
            if d <= dt:
                kand.append(d)
    return max(kand)


def varovani_v_okne(ted_ts):
    """Posledni SKUTECNE nasazeni (ok/varovani/selhalo; preskocena a 'nic' se nepocitaji) skoncilo varovanim A patri do stejneho
    planovaneho okna jako ted_ts -> dict {id, kdy, reason}, jinak None. Automat se pak v tom okne neopakuje (Robert/bot3 2026-10-02,
    po padu arbitra v behu #10): nekdo se musi podivat na priciny, dalsi planovany termin nebo `--rucni` jsou vedome rozhodnuti.
    Chyba DB = None (zapis nesmi blokovat nasazeni)."""
    if BEZ_DB:
        return None
    try:
        conn = db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, status, UNIX_TIMESTAMP(started_at) AS t, reason FROM deploy_runs "
                            "WHERE status IN ('ok','varovani','selhalo') ORDER BY id DESC LIMIT 1")
                r = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        log("kontrola predchoziho varovani selhala (nasazeni pokracuje): %s" % e)
        return None
    if not r:
        return None
    r = r if isinstance(r, dict) else dict(zip(("id", "status", "t", "reason"), r))
    if r["status"] != "varovani" or okno_od(float(r["t"])) != okno_od(ted_ts):
        return None
    return {"id": r["id"], "kdy": datetime.datetime.fromtimestamp(float(r["t"]), TZ).strftime("%H:%M"), "reason": (r["reason"] or "")[:200]}


def dalsi_okno():
    n = datetime.datetime.now(TZ)
    kand = []
    for den in (0, 1):
        for hhmm in OKNA:
            h, m = map(int, hhmm.split(":"))
            d = (n + datetime.timedelta(days=den)).replace(hour=h, minute=m, second=0, microsecond=0)
            if d > n:
                kand.append(d)
    return min(kand)


def za_kolik(d):
    s = int((d - datetime.datetime.now(TZ)).total_seconds())
    return "%d h %02d min" % (s // 3600, (s % 3600) // 60) if s >= 3600 else "%d min" % max(1, s // 60)


def casovac_stav():
    out = run(["systemctl", "show", TIMER, "-p", "LoadState", "-p", "ActiveState", "-p", "UnitFileState"], 10)[1]
    v = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
    if v.get("LoadState") in (None, "not-found"):
        return "není nainstalovaný (Robert musí spustit jednorázový příkaz, viz TASKS.md)"
    if v.get("ActiveState") == "active" and v.get("UnitFileState") == "enabled":
        return "zapnutý"
    return "vypnutý (%s/%s)" % (v.get("ActiveState"), v.get("UnitFileState"))


def posledni_behy(n=5):
    try:
        conn = db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, started_at, status, trigger_type, commits_count, duration_s, reason "
                            "FROM deploy_runs ORDER BY id DESC LIMIT %s", (n,))
                return cur.fetchall()
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        return "tabulka deploy_runs zatím není (vznikne při prvním běhu): %s" % str(e)[:80]


def stav(as_json=False):
    sl = Sluzba()
    ws = sl.workery()
    od = bezi_od(ws)
    ceka = commity_od(od) if od else []
    dirty = necommitnute_api()
    info = {
        "sluzba_aktivni": sl.aktivni(),
        "kod_bezi_od": datetime.datetime.fromtimestamp(od).strftime("%Y-%m-%d %H:%M:%S") if od else None,
        "dalsi_okno": dalsi_okno().isoformat(),
        "casovac": casovac_stav(),
        "ceka": ceka,
        "necommitnute_api": [{"stav": s, "soubor": c} for s, c in dirty],
        "posledni_behy": posledni_behy(),
    }
    if as_json:
        print(json.dumps(info, ensure_ascii=False, default=str, indent=1))
        return 0
    print("NASAZENÍ SERVERU (gunicorn HUP, bez výpadku; terminy %s Europe/Prague)" % " a ".join(OKNA))
    print("  služba          : %s | kód běží od %s" % ("běží" if info["sluzba_aktivni"] else "NEBĚŽÍ", info["kod_bezi_od"]))
    print("  časovač         : %s" % info["casovac"])
    d = dalsi_okno()
    print("  další termín    : %s (za %s)" % (d.strftime("%d.%m. %H:%M"), za_kolik(d)))
    print("  čeká na nasazení: %d commitů do api/*.py" % len(ceka))
    for c in ceka[:20]:
        print("      %s  %s  %s" % (c["hash"], datetime.datetime.fromtimestamp(c["ts"]).strftime("%H:%M"), c["predmet"][:90]))
    if dirty:
        print("  NECOMMITNUTÉ v api/*.py (blokují plánované nasazení, dokud se necommitnou):")
        zam = zamek()
        for s, c in dirty:
            print("      %s [%s] - %s" % (c, s, napoveda_vlastnika(c, zam)))
    pb = info["posledni_behy"]
    if isinstance(pb, str):
        print("  poslední běhy   : " + pb)
    elif not pb:
        print("  poslední běhy   : zatím žádný běh (první zapíše plánované nasazení)")
    else:
        print("  poslední běhy   :")
        for r in pb:
            print("      #%s %s %-10s %-6s %s commitů, %ss  %s" % (
                r["id"], r["started_at"], r["status"], r["trigger_type"], r["commits_count"], r["duration_s"], (r["reason"] or "")[:70].replace("\n", " ")))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--planovane", action="store_true")
    ap.add_argument("--rucni", action="store_true")
    ap.add_argument("--stav", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--zkouska", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.stav:
        return stav(a.json)
    if a.planovane:
        return nasad("plan", a.zkouska, a.force)
    if a.rucni:
        return nasad("rucni", a.zkouska, a.force)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
