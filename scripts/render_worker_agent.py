#!/usr/bin/env python3
"""render_worker_agent.py - renderovaci agent pro Robertuv notebook (GPU).

Robert 2026-08-11: "zkus to presmerova na muj notebook, mam gpu"
(NVIDIA GeForce RTX 4080 Laptop GPU).

CO TO DELA: bezi na notebooku, kazdych par sekund se serveru zepta,
jestli nema hotovy render k odbaveni. Kdyz ano, stahne si model +
textury, vyrenderuje je LOKALNE NA GPU (OptiX) a posle obrazek zpet.
Ve scene se nic nemeni - uzivatel jen dostane vysledek mnohem driv.

Kdyz agent nebezi (notebook vypnuty/uspany), server render odbavi sam
na CPU - nic se nerozbije, jen to trva dyl.

SPUSTENI (Windows, PowerShell nebo cmd):

    python render_worker_agent.py

Pred prvnim spustenim nastav 2 veci nize v KONFIGURACE (nebo je predej
jako promenne prostredi RENDER_WORKER_TOKEN / BLENDER_EXE).

Zavislosti: ZADNE - staci nainstalovany Blender (agent bezi pod jeho
vlastnim Pythonem, viz SPUSTIT_AGENTA.bat).
"""
import glob
import re
import io
import queue
import zipfile
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import collections

import json
import urllib.error
import urllib.parse
import urllib.request

# Robert 2026-08-11 ("Python nebyl nalezen"): agent zamerne pouziva JEN
# standardni knihovnu (urllib), zadny `requests` - diky tomu ho jde
# spustit Pythonem, ktery je zabaleny primo v Blenderu, a na notebooku
# tak neni potreba instalovat vubec nic navic.

# FORMAT VERZE JE ZAVAZNY: "RRRR-MM-DD" + poradove pismeno v ramci dne.
# Odviji se od nej (a) porovnavani "je serverova verze novejsi?" - u
# tohohle tvaru staci retezcove porovnani, a hlavne (b) NAZEV SOUBORU
# `render_worker_agent_<verze>.py`, protoze SPUSTIT_AGENTA.bat vybira
# soubor s NEJVYSSIM nazvem (`dir /b /o-n`). Pozor na podtrzitko: nazev
# "..._2026-09-09_1930c.py" by se seradil POD "..._2026-09-09b.py"
# ('_' je v ASCII pred pismeny), takze by .bat pustil starou verzi.
AGENT_VERSION = "2026-09-29b"  # vypisuje se pri startu

# Cas startu TETO instance agenta. Posila se serveru pri kazdem pollu i
# tepu - server podle nej pozna, ze uloha, kterou porad vede jako
# "bezi na workerovi", zacala jeste PRED timhle spustenim agenta, a je
# tedy prokazatelne mrtva (agent mezitim restartoval).
AGENT_SINCE = time.time()

# ------------------------------------------------------- vypis do konzole
# bot8 2026-09-09 (realne chyceni): agent v 17:57:32 dostal z pollu
# HTTP 500 (zavod dvou gunicorn workeru o soubor tepu, uz opraveno na
# serveru) a HLAVNI SMYCKA se z toho uz nikdy nevzpamatovala - dalsi poll
# nedorazil ani po 1,5 hodine, zatimco tep chodil dal a server hlasil
# "ONLINE". Tep je totiz SAMOSTATNE vlakno, ktere nic netiskne; hlavni
# smycka po chybe volala print() - a prave print() je na Windows misto,
# kde se cela smycka umi navzdy zaseknout:
#
#   * konzole ma ve vychozim stavu zaply QuickEdit. Klikne-li do okna
#     kdokoli mysi (i omylem), prepne se do "selection mode" a PRVNI
#     dalsi zapis na stdout BLOKUJE, dokud clovek nezmackne Esc.
#   * pokud stdout neni konzole, ale roura (.bat presmerovany do souboru,
#     spusteni z jineho nastroje) a nikdo ji nectě, zaplni se buffer a
#     zapis blokuje uplne stejne.
#
# Reseni ma dve vrstvy: (1) QuickEdit se pri startu VYPNE (viz
# _vypnout_quick_edit), (2) hlavni smycka uz do konzole nikdy nepise
# primo - jen vlozi radek do fronty, kterou vyprazdnuje vlastni vlakno.
# Kdyz se konzole presto zasekne, plni se fronta, prebytek se ZAHODI a
# smycka jede dal. Vypis je diagnostika, prace je prace.
_VYPIS_FRONTA = queue.Queue(maxsize=3000)
_VYPIS_ZAHOZENO = [0]

# Robert 2026-09-13 ("log lezi na stanici, tak jí v nove verzi priraď
# ukol, aby ti ten log posilala"): drivejsi X-Worker-Error hlasilo jen
# kratkou zpravu (traceback, oriznuty na 500 znaku serverem) - kdyz se
# nekdo pta "proc presne to spadlo", chybelo KONTEXT (co se delo TESNE
# PRED tim). Tenhle rolujici buffer drzi poslednich UDIN_LOG_RADKU
# radku vypisu (stejny text jako jde do konzole) - `posli_log_serveru()"
# ho pripoji jako TELO POZADAVKU (ne hlavicku, ta ma tesny limit) kdyz
# uloha selze, viz run_job()/run_turntable_job().
UDIN_LOG_RADKU = 400
_LOG_HISTORIE = collections.deque(maxlen=UDIN_LOG_RADKU)


def _vypis_pumpa():
    while True:
        text = _VYPIS_FRONTA.get()
        try:
            sys.stdout.write(text + "\n")
            sys.stdout.flush()
        except Exception:
            pass          # zaseknuta/zavrena konzole nesmi shodit agenta


def vypis(*args):
    """Nahrada print() pro CELEHO agenta - nikdy neblokuje volajiciho."""
    text = " ".join(str(a) for a in args)
    _LOG_HISTORIE.append(text)
    try:
        _VYPIS_FRONTA.put_nowait(text)
    except queue.Full:
        _VYPIS_ZAHOZENO[0] += 1


def posledni_log():
    """Poslednich UDIN_LOG_RADKU radku vypisu, jako jeden text - pro
    posilani serveru pri selhani ulohy (viz posli_chybu_serveru nize)."""
    return "\n".join(_LOG_HISTORIE)


threading.Thread(target=_vypis_pumpa, name="vypis", daemon=True).start()


def _vypnout_quick_edit():
    """Windows: vypne QuickEdit konzole (viz komentar vyse).

    ENABLE_EXTENDED_FLAGS (0x0080) se MUSI nastavit zaroven - bez nej
    Windows zmenu bitu QuickEdit ignoruje. Kdyz agent nebezi v konzoli
    (sluzba, presmerovany vystup), GetConsoleMode selze a nedela se nic.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-10)          # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080
        novy = (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
        return bool(k.SetConsoleMode(h, novy))
    except Exception:
        return False


# ----------------------------------------------------------- KONFIGURACE
SERVER = os.environ.get("RENDER_SERVER", "https://autovestavby.logiman.cz")

# Token najdes na serveru v /opt/konfigurator/api/.env (RENDER_WORKER_TOKEN)
TOKEN = os.environ.get("RENDER_WORKER_TOKEN", "SEM_VLOZ_TOKEN")

BLENDER_MIN = (5, 2)   # sablony se ukladaji v 5.2.x, starsi Blender je nepreda ("not a blend file")
_VERZE_BLENDERU = {}


def _blender_verze(path):
    """(major, minor, patch) podle `blender --version`, None kdyz to nejde
    zjistit. Cesta ani env nemusi odpovidat verzi (BLENDER_EXE ze stareho
    .bat, `blender` v PATH ukazujici na 4.1)."""
    if path in _VERZE_BLENDERU:
        return _VERZE_BLENDERU[path]
    ver = None
    try:
        out = subprocess.run([path, "--version"], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                             errors="replace", timeout=60).stdout
        m = re.search(r"Blender\s+(\d+)\.(\d+)(?:\.(\d+))?", out)
        if m:
            ver = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
    except Exception:
        pass
    _VERZE_BLENDERU[path] = ver
    return ver


def _find_blender():
    """Cesta k Blenderu. Robert 2026-09-09 zapojuje NOVY GPU pocitac -
    at se na nem nemusi nic rucne nastavovat, agent si Blender najde sam:
    env BLENDER_EXE > `blender` v PATH > nejnovejsi instalace v obvyklych
    adresarich (Windows / Linux / macOS). Az kdyz nenajde nic, vypise, co
    ma clovek doplnit.

    2026-09-29 (notebook Omen): kdyz takhle vybrany Blender je starsi nez
    BLENDER_MIN (stary .bat s BLENDER_EXE na 4.1, PATH na 4.1), vezme se
    nejnovejsi nalezeny, ktery staci - jinak render spadne na "not a blend
    file". Stroj, ktery uz renderuje s dostatecne novym Blenderem, se
    chova jako driv."""
    pats = [
        r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender *\blender.exe"),
        r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
        os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender"),
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/opt/blender*/blender",
        "/usr/share/blender*/blender",
    ]
    hledane = []
    for pat in pats:
        hledane.extend(glob.glob(pat))

    # nejnovejsi verze = nejvyssi cislo v ceste (fallback: cas zmeny)
    def key(path):
        nums = re.findall(r"(\d+)\.(\d+)", path)
        ver = tuple(int(x) for x in nums[-1]) if nums else (0, 0)
        try:
            return (ver, os.path.getmtime(path))
        except OSError:
            return (ver, 0)

    poradi = []
    env = os.environ.get("BLENDER_EXE")
    if env:
        poradi.append(env)
    found = shutil.which("blender")
    if found:
        poradi.append(found)
    poradi.extend(sorted(set(hledane), key=key, reverse=True))
    poradi = list(dict.fromkeys(poradi))
    if not poradi:
        return ""
    prvni = poradi[0]
    if not os.path.exists(prvni):
        return prvni
    ver = _blender_verze(prvni)
    if ver is None or ver[:2] >= BLENDER_MIN:
        return prvni
    for c in poradi[1:]:
        if not os.path.exists(c):
            continue
        vc = _blender_verze(c)
        if vc and vc[:2] >= BLENDER_MIN:
            vypis("Blender %s (%s) je moc stary pro sablony (potreba %d.%d+), pouzivam %s (%s)."
                  % (".".join(map(str, ver)), prvni, BLENDER_MIN[0], BLENDER_MIN[1],
                     ".".join(map(str, vc)), c))
            return c
    vypis("POZOR: nalezeny Blender %s (%s) je starsi nez potrebnych %d.%d a jiny se nenasel. "
          "Nainstaluj novejsi nebo nastav BLENDER_EXE." % (".".join(map(str, ver)), prvni,
                                                          BLENDER_MIN[0], BLENDER_MIN[1]))
    return prvni


BLENDER_EXE = _find_blender()

WORKER_NAME = os.environ.get("WORKER_NAME", platform.node() or "notebook")
# Robert 2026-09-09 ("jak detekujeme novy PC s GPU?") - do teto chvile se
# GPU jen DEKLAROVALO: natvrdo "OPTIX" bez ohledu na to, co v pocitaci
# doopravdy je. Kdyby mel novy stroj AMD (HIP) nebo Intel (ONEAPI),
# Cycles by tise spadl na CPU a nikdo by se to nedozvedel - render by byl
# jen zahadne pomaly a admin by porad hlasil "OPTIX".
# Ted se skutecna zarizeni zjisti PRIMO Z BLENDERU pri startu agenta.
_GPU_PROBE = r"""
import bpy, json
prefs = bpy.context.preferences.addons["cycles"].preferences
found = {}
for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
    try:
        prefs.compute_device_type = backend
    except Exception:
        continue          # tuhle backend tenhle build Blenderu nezna
    try:
        prefs.refresh_devices()
        devs = prefs.get_devices_for_type(backend)
    except Exception:
        continue
    names = [d.name for d in devs if getattr(d, "type", None) == backend]
    if names:
        found[backend] = names
print("GPUDETECT " + json.dumps(found))
"""

# poradi preference: nejrychlejsi/nejlepe podporovane napred
_GPU_PRIORITY = ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL")


def _detect_gpu():
    """Vraci (backend, popis). Env GPU_BACKEND ma prednost (nouzove
    prebiti), jinak se Blender jednou spusti a rekne, co umi."""
    env = os.environ.get("GPU_BACKEND")
    if env:
        return env.upper(), "%s (nastaveno rucne)" % env.upper()
    if not BLENDER_EXE or not os.path.exists(BLENDER_EXE):
        return "NONE", "Blender nenalezen"
    probe = os.path.join(tempfile.gettempdir(), "konf_gpu_probe.py")
    try:
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write(_GPU_PROBE)
        out = subprocess.run([BLENDER_EXE, "-b", "-noaudio", "--factory-startup",
                              "-P", probe],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=180).stdout
    except Exception as e:
        return "NONE", "detekce selhala (%s)" % e
    finally:
        try:
            os.remove(probe)
        except OSError:
            pass
    line = next((l for l in out.splitlines() if l.startswith("GPUDETECT ")), None)
    if not line:
        return "NONE", "Blender nevratil seznam zarizeni"
    try:
        found = json.loads(line[len("GPUDETECT "):])
    except ValueError:
        return "NONE", "necitelna odpoved detekce"
    for backend in _GPU_PRIORITY:
        if found.get(backend):
            return backend, "%s: %s" % (backend, ", ".join(found[backend]))
    return "NONE", "zadne GPU zarizeni (render pojede na CPU)"


GPU_BACKEND, GPU_INFO = _detect_gpu()
_v = _blender_verze(BLENDER_EXE) if BLENDER_EXE and os.path.exists(BLENDER_EXE) else None
if _v:
    GPU_INFO = "%s | Blender %s" % (GPU_INFO, ".".join(map(str, _v)))
POLL_SECONDS = 3
# -----------------------------------------------------------------------


def precti_gpu_senzory():
    """Teplota/zatizeni/takt GPU pres `nvidia-smi` (Robert 2026-09-11:
    "postavte sluzbu, ktera bude posilat informace o teplote na graficke
    karte" - Logiman2 jede hodiny pod plnou zatezi behem davky).

    ⭐ NIKDY NEVYHODI VYJIMKU A NIKDY NEZAMRZNE. Tohle bezi v agentovi, ke
    kteremu se boti nedostanou jinak nez pres jeho vlastni samoaktualizaci
    (viz komentar u AGENT_VERSION nize) - spadly agent je ztracena cesta
    tam, oprava uz jen rucne od Roberta. `subprocess.run` proto MA
    POVINNY timeout (zamrzle volani je presne to, co try/except samo o
    sobe nezachyti), a kompletni telo je v `try/except Exception`, ne jen
    v jeho casti - chybejici `nvidia-smi` (jina karta/ovladac), necekany
    format vystupu, cokoli - vsechno tise vraci None, agent bezi dal.

    Vraci {"teplota_c": int, "zatizeni_pct": int, "takt_mhz": int} nebo
    None.
    """
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=temperature.gpu,utilization.gpu,clocks.sm",
             "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=5).stdout
        cisla = [int(x.strip()) for x in out.strip().splitlines()[0].split(",")]
        if len(cisla) != 3:
            return None
        tep, zatiz, takt = cisla
        return {"teplota_c": tep, "zatizeni_pct": zatiz, "takt_mhz": takt}
    except Exception:
        return None

HEADERS = {"X-Worker-Token": TOKEN}


def api(path):
    return SERVER.rstrip("/") + path


def http_get(path, params=None, timeout=60):
    """Vraci (status, bytes, headers). Nevyhazuje na HTTP chybovem kodu -
    volajici se rozhoduje sam (napr. 401 = spatny token).

    bot4 2026-09-13 (Robert: "agenta budes opravovat, dokud nebude
    fungovat rendering"): puvodne se chytal jen HTTPError (cisty HTTP
    chybovy kod - server odpovedel, jen ne 200). VYPADEK SITE (DNS,
    connection reset, timeout behem stahovani velkeho .glb) je jiny druh
    chyby (URLError/OSError, HTTPError NENI jejich rodic obracene) a
    propadal az VEN z http_get() - presne tohle dnes shodilo vsech 6
    uloh Jumpy Crew Cab (traceback ukazal pad primo v `http_get(item
    ["url"], ...)` behem stahovani dilu). Misto pádu vraci sentinel
    status 0 - volajici uz maji `if status != 200: ...chyba...`, takze
    se to projevi presne stejne jako HTTP chyba (citelna zprava pres
    posli_chybu_serveru), ne dalsi tichy zombie stav."""
    url = api(path)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})
    except OSError as e:
        # URLError (DNS, connection refused/reset) i TimeoutError/
        # socket.timeout jsou v Pythonu 3 podtridy OSError - HTTPError uz
        # je odchycen vyse, takze sem spadne jen skutecny sitovy vypadek.
        return 0, ("Sitova chyba (%s): %s" % (type(e).__name__, e)).encode("utf-8"), {}


def http_get_json(path, params=None, timeout=60):
    status, body, _ = http_get(path, params, timeout)
    if status != 200:
        return status, None
    try:
        return status, json.loads(body.decode("utf-8"))
    except ValueError:
        return status, None


def http_post(path, data=b"", extra_headers=None, timeout=300):
    """Vraci HTTP status. bot4 2026-09-13 - stejna oprava jako http_get():
    sitovy vypadek (OSError/URLError/timeout) uz nepropada jako
    nezachycena vyjimka, vraci se sentinel 0 (nikdy nesedi na 200/OK
    kontrolu volajiciho)."""
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(api(path), data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except OSError:
        return 0


def _hlavicka_latin1(text):
    """HTTP hlavicka smi obsahovat jen latin-1 a zadny novy radek - jinak
    urllib vyhodi UnicodeEncodeError a chyba (napr. s ě/ř/š z nazvu sestavy)
    se serveru vubec nedostane (Robert 2026-09-29, notebook Omen)."""
    return text.replace("\r", " ").replace("\n", " ").encode("latin-1", "replace").decode("latin-1")


def posli_chybu_serveru(result_url, kratka_zprava):
    """Robert 2026-09-13 ("log lezi na stanici, tak jí v nove verzi
    priraď ukol, aby ti ten log posilala"): X-Worker-Error hlavicka (viz
    api/render_worker.py) ma tesny limit (server orizne na 500 znaku) -
    stacila na "CO", ne na "CO SE DELO PREDTIM". Tenhle helper posle OBOJI
    najednou: kratkou zpravu v hlavicce (zpetna kompatibilita - stary
    server kod, co cte jen hlavicku, porad funguje) A CELY nedavny log
    (viz _LOG_HISTORIE/posledni_log()) jako TELO POZADAVKU (tam neni tak
    tesny limit), aby slo zpetne zjistit presne, co se delo TESNE PRED
    padem, ne jen typ vyjimky."""
    try:
        http_post(result_url, posledni_log().encode("utf-8", errors="replace"),
                  {"X-Worker-Error": _hlavicka_latin1(kratka_zprava[-500:]),
                   "Content-Type": "text/plain; charset=utf-8"})
    except Exception as e:
        vypis("  (navic se nepodarilo poslat chybu/log serveru:", e, ")")


# Robert 2026-08-11 (jeho prvni ostry render sel omylem na server, ne na
# GPU): agent se driv hlasil serveru JEN pri dotazu na praci - jenze
# behem renderovani se neptá (je zamestnany), takze po
# WORKER_ONLINE_S (90 s) ho server povazoval za vypnuty a dalsi ulohu
# poslal na vlastni CPU. Tohle vlakno tepe NEZAVISLE na renderovani, po
# celou dobu behu agenta.
# --------------------------------------------------------------- nespat
# Robert 2026-09-09: "u toho PC musime zaroven pohlidat aby neusnul".
# Reseni pres Windows API SetThreadExecutionState, ne pres prestaveni
# systemovych nastaveni napajeni: plati JEN po dobu behu agenta a po jeho
# ukonceni se PC zase normalne uspava samo. ES_SYSTEM_REQUIRED = "system
# se nesmi uspat", ES_CONTINUOUS = "plati, dokud nereknu jinak" (per
# vlakno, proto se to znovu potvrzuje i v heartbeat vlakne).
# ES_DISPLAY_REQUIRED zamerne NE - obrazovka klidne zhasne, jen se nesmi
# uspat cely stroj.
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_awake():
    """Na Windows zakaze uspani. Jinde nedela nic (server/Mac si to resi
    po svem) - a nikdy nesmi shodit agenta, proto to cele v try."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except Exception:
        pass


# Navratove kody - cte je SPUSTIT_AGENTA.bat a podle nich se rozhoduje,
# jestli agenta nastartovat znovu:
EXIT_RESTART = 1   # spadl / skoncil necekane -> .bat ho pusti znovu
EXIT_ALREADY_RUNNING = 2   # uz bezi jina kopie -> NErestartovat
EXIT_CONFIG = 3   # spatny token / chybi Blender -> NErestartovat, opravit


def heartbeat_loop():
    while True:
        keep_awake()   # potvrdit i z tohohle vlakna (stav je per-vlakno)
        # `precti_gpu_senzory()` sama nikdy nevyhodi vyjimku (viz jeji
        # docstring) - i tak zustava volana tady, ne pridana rovnou do
        # dict literalu nize, aby bylo na prvni pohled videt, ze je to
        # samostatny, uz predem osetreny krok.
        senzory = precti_gpu_senzory()
        try:
            telo = {"name": WORKER_NAME, "gpu": GPU_INFO,
                    # viz AGENT_SINCE nahore - server podle
                    # zmeny teto hodnoty pozna restart agenta
                    "since": round(AGENT_SINCE),
                    # PRIMY signal verze (bot3 2026-09-11:
                    # "hlasi agent svoji verzi nekam, kde ji
                    # vidim?"). Do teto zmeny slo poznat jen
                    # NEPRIMO ze zmeny `since` (agent
                    # restartoval), ne CO nastartovalo -
                    # tenhle radek rika primo, ktera verze
                    # bezi.
                    "version": AGENT_VERSION}
            if senzory:
                telo["gpu_temp_c"] = senzory["teplota_c"]
                telo["gpu_util_pct"] = senzory["zatizeni_pct"]
                telo["gpu_clock_mhz"] = senzory["takt_mhz"]
            http_post("/api/render-worker/heartbeat",
                      json.dumps(telo).encode("utf-8"),
                      {"Content-Type": "application/json"}, timeout=20)
        except Exception:
            pass  # vypadek site nesmi agenta shodit
        time.sleep(20)


# ------------------------------------------ samoaktualizace agenta (verze)
# Robert 2026-09-09 ("nachystej to tak, jak to popisujes"): k tomuhle
# pocitaci nemame pristup, takze kazda oprava agenta se k nemu dosud
# dostala jen tak, ze ji nekdo rucne stahl ze Sdileneho disku - v praxi
# tedy nedostala vubec. Agent si proto novou verzi sam stahne ze serveru,
# stejne jako si uz stahuje renderovaci skripty (/script, /tt-script).
#
# POZOR na SPUSTIT_AGENTA.bat: cestu k agentovi si vyhodnoti JEDNOU pred
# smyckou restartu (`dir /b /o-n` nad :runloop), takze soubor s vyssim
# nazvem vedle nej by se sam NIKDY nespustil. Nova verze se proto zapisuje
# DVEMA zpusoby: (1) pod verzovanym nazvem - pro pripad, ze .bat startuje
# znovu (a pro noveji nahrany .bat, ktery uz hleda v kazdem kole), a
# (2) ATOMICKY PRES SEBE SAMA - tuhle cestu .bat spousti primo, takze se
# nova verze chytne uz pri nejblizsim restartu. Original zustava vedle
# jako `.bak`.
UPDATE_CHECK_S = 600          # jak casto se ptat na novou verzi
UPDATE_MAX_POKUSU = 3         # pojistka proti zacykleni restartu

_SEBE = os.path.abspath(__file__)
_UPDATE_MARKER = os.path.join(os.path.dirname(_SEBE), "render_worker_agent.aktualizace.json")
_update_ohlaseno = [False]


def _marker_nacti():
    try:
        with open(_UPDATE_MARKER, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _marker_zapis(data):
    try:
        with open(_UPDATE_MARKER, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        pass


def _bezpecny_nazev(nazev):
    """Nazev souboru urcuje server - nesmi z nej jit vyrobit cesta."""
    nazev = os.path.basename(nazev or "")
    if not re.match(r"^render_worker_agent[A-Za-z0-9_.\-]*\.py$", nazev):
        return None
    return nazev


def zkusit_aktualizaci():
    """True = nova verze lezi na disku, agent se ma ukoncit a nastartovat.

    Nic se nenasadi, dokud stazeny soubor NESEDI na velikost, SHA-256 a
    neprojde compile() - poskozene stazeni nesmi agenta zabit natrvalo,
    v takovem pripade se jede dal ve stavajici verzi.
    """
    status, meta = http_get_json("/api/render-worker/agent-version", timeout=30)
    if status != 200 or not meta:
        return False
    verze = str(meta.get("version") or "")
    # Verze je "RRRR-MM-DD<pismeno>" - retezcove porovnani je u tohohle
    # tvaru monotonni (datum je nulami doplnene, pismeno roste v ramci dne).
    if not verze or verze <= AGENT_VERSION:
        return False

    marker = _marker_nacti()
    pokusu = (marker.get("pokusu", 0) + 1) if marker.get("verze") == verze else 1
    if pokusu > UPDATE_MAX_POKUSU:
        if not _update_ohlaseno[0]:
            _update_ohlaseno[0] = True
            vypis("\n!!! Server nabizi verzi %s, ale %dx se ji nepodarilo nasadit."
                  "\n!!! Jedu dal ve verzi %s. Reseni: stahnout agenta rucne ze"
                  " Sdileneho disku (slozka Rendering).\n"
                  % (verze, UPDATE_MAX_POKUSU, AGENT_VERSION))
        return False
    _marker_zapis({"verze": verze, "pokusu": pokusu})

    vypis("  nova verze agenta na serveru: %s (mam %s) - stahuji"
          % (verze, AGENT_VERSION))
    status, data, _ = http_get("/api/render-worker/agent-source", timeout=120)
    if status != 200 or not data:
        vypis("  aktualizace: server vratil %s, zustavam na stavajici verzi" % status)
        return False
    import hashlib
    if meta.get("size") and len(data) != meta["size"]:
        vypis("  aktualizace: nesedi velikost (%d != %s), zahazuji"
              % (len(data), meta.get("size")))
        return False
    if meta.get("sha256") and hashlib.sha256(data).hexdigest() != meta["sha256"]:
        vypis("  aktualizace: nesedi kontrolni soucet, zahazuji")
        return False
    try:
        zdroj = data.decode("utf-8")
        compile(zdroj, "render_worker_agent.py", "exec")
    except (UnicodeDecodeError, SyntaxError) as e:
        vypis("  aktualizace: stazeny soubor neni platny Python (%s), zahazuji" % e)
        return False
    if ('AGENT_VERSION = "%s"' % verze) not in zdroj:
        vypis("  aktualizace: stazeny soubor nehlasi verzi %s, zahazuji" % verze)
        return False

    slozka = os.path.dirname(_SEBE)
    nazev = _bezpecny_nazev(meta.get("filename")) or ("render_worker_agent_%s.py" % verze)
    tmp = os.path.join(slozka, ".agent_novy.tmp")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        shutil.copyfile(_SEBE, _SEBE + ".bak")      # navrat, kdyby nova verze zlobila
        novy = os.path.join(slozka, nazev)
        if os.path.abspath(novy) != _SEBE:
            shutil.copyfile(tmp, novy)
        # az uplne nakonec vymena sebe sama - os.replace je atomicky i na
        # Windows, takze .bat nikdy nespusti napul zapsany soubor
        os.replace(tmp, _SEBE)
    except OSError as e:
        vypis("  aktualizace: zapis selhal (%s), zustavam na stavajici verzi" % e)
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
    vypis("  nova verze %s je na disku (%s) - koncim, .bat me za 10 s spusti znovu"
          % (verze, nazev))
    return True


# --------------------------------------------- hlidac HLAVNI SMYCKY agenta
# bot8 2026-09-09: tep sam o sobe NEDOKAZUJE, ze agent odebira praci -
# bezi ve vlastnim vlakne. Prave tak vypadal vecerni vypadek: server
# hlasil "ONLINE" a agent si 1,5 h nevzal ani jednu ulohu. Tohle vlakno
# hlida to druhe - jestli hlavni smycka porad chodi na /poll.
POLL_STUCK_S = 300       # 5 min ticha (a zadna uloha) -> hlasit vyrazne
POLL_RESTART_S = 900     # 15 min -> ukoncit proces, .bat agenta pusti znovu

_stav_smycky = {"posledni_poll": time.time(), "uloha": None}


def hlidac_smycky():
    hlaseno = False
    while True:
        time.sleep(30)
        # Behem renderu se poll necekava (Blender bezi klidne hodinu) -
        # hlidame jen necinnou smycku.
        if _stav_smycky["uloha"]:
            hlaseno = False
            continue
        ticho = time.time() - _stav_smycky["posledni_poll"]
        if ticho >= POLL_RESTART_S:
            vypis("\n!!! HLAVNI SMYCKA SE ZASEKLA (%d min bez dotazu na praci)."
                  "\n!!! Ukoncuji agenta - SPUSTIT_AGENTA.bat ho za 10 s pusti znovu.\n"
                  % (ticho // 60))
            time.sleep(3)          # dat vypisu sanci projit, kdyz konzole zije
            os._exit(EXIT_RESTART)
        if ticho >= POLL_STUCK_S and not hlaseno:
            hlaseno = True
            vypis("\n!!! POZOR: uz %d s jsem se serveru nezeptal na praci."
                  "\n!!! (zahozenych radku vypisu: %d) Za %d s se agent restartuje.\n"
                  % (round(ticho), _VYPIS_ZAHOZENO[0], round(POLL_RESTART_S - ticho)))
        elif ticho < POLL_STUCK_S:
            hlaseno = False


# Poznamka: drivejsi gpu_prelude() (vkladal kod pred renderovaci skript)
# byl odstranen - viz komentar u spousteni Blenderu nize. GPU se ted
# predava promennou prostredi KONF_GPU_BACKEND, kterou zpracuje primo
# blender_render_scene.py, a to az PO read_factory_settings().


def run_blend_job(job, work):
    """Robert 2026-09-09 ("rozšíření na .blend pro renderování automaticke
    na gpu v síti") - druhy typ ulohy: syrovy .blend soubor (vlastni
    kamera/material/engine/vzorky uvnitr, ulozeny primo z Blenderu na
    Sdileny disk), renderovany PRESNE tak, jak byl ulozen. Na rozdil od
    run_job() (GLB+skript) se tu NEVOLA read_factory_settings() vubec -
    tenhle notebook uz ma GPU (OptiX) zapnute ve svych vlastnich Cycles
    preferencich, takze scene.cycles.device="GPU" ulozene v souboru
    zabere bez dalsiho zasahu (zadny KONF_GPU_BACKEND shim potreba)."""
    job_id = job["job_id"]
    blend_path = os.path.join(work, "scene.blend")
    status, body, _ = http_get(job["blend_url"], timeout=300)
    if status != 200:
        vypis("  nepodarilo se stahnout .blend soubor:", status)
        return
    with open(blend_path, "wb") as fh:
        fh.write(body)

    out_png = os.path.join(work, "out.png")
    # Robert 2026-09-09: "nechceme to samotne pozadi hdri videt, slouzi
    # pouze pro odlesky". film_transparent nechava HDRI SVITIT i ODRAZET
    # SE v materialech (to je fyzikalne uplne stejne osvetleni), jen
    # paprsky, ktere z kamery proleti kolem sestavy do prazdna, konci
    # pruhlednou alfou misto obrazku mapy. Vysledny PNG s alfou je presne
    # to, co fotogalerie skladove karty potrebuje. Aplikuje se na STAZENOU
    # KOPII, Robertuv soubor na Sdilenem disku zustava nedotceny.
    pre_script = os.path.join(work, "pred_renderem.py")
    with open(pre_script, "w", encoding="utf-8") as fh:
        fh.write("import bpy\n"
                 "bpy.context.scene.render.film_transparent = True\n"
                 "print('HDRI jen na odlesky - pozadi pruhledne')\n")
    hdri_bg = bool((job.get("settings") or {}).get("hdri_as_background"))
    cmd = [BLENDER_EXE, "-b", "-noaudio", blend_path]
    if not hdri_bg:
        cmd += ["-P", pre_script]
    cmd += ["-o", out_png, "-F", "PNG", "-f", "1"]
    vypis("  renderuji .blend soubor presne tak, jak byl ulozen...")
    t0 = time.time()
    env = dict(os.environ)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    out_lines = []
    for line in proc.stdout:
        out_lines.append(line)
        low = line.lower()
        if "error" in low or "traceback" in low or "sample" in low:
            vypis("   ", line.rstrip()[:150])
    proc.wait()
    out = "".join(out_lines)
    # Blender pri "-o foo.png -f 1" priloha cislo snimku do nazvu
    # (foo0001.png) - presne cesta zavisi na verzi/padding, projdi
    # slozku work a najdi cerstve vytvoreny PNG, at se neuhadujeme.
    candidates = [f for f in os.listdir(work) if f.lower().endswith(".png")]
    real_out = None
    if candidates:
        real_out = os.path.join(work, sorted(candidates, key=lambda f: os.path.getmtime(os.path.join(work, f)))[-1])
    if not real_out or not os.path.exists(real_out):
        tail = out[-800:]
        vypis("  CHYBA renderu .blend:", tail[-300:])
        posli_chybu_serveru(f"/api/render-worker/job/{job_id}/result", tail.replace("\n", " "))
        return
    with open(real_out, "rb") as fh:
        http_post(f"/api/render-worker/job/{job_id}/result", fh.read(),
                  {"Content-Type": "image/png"}, timeout=600)
    vypis(f"  hotovo za {round(time.time() - t0, 1)} s, odeslano")


# ------------------------------------------------------ hlidac zaseknuti
# Robert 2026-09-09: "muze to spadnout a ja u toho nebudu sedet porad".
# Pad procesu resi restart v .bat; horsi je ZASEKNUTI - Blender zije, ale
# uz nic nedela (zamrzly ovladac GPU, cekani na sitovy disk). Agent by na
# nem visel donekonecna a server by mezitim marne cekal na vysledek.
# Proto: kdyz Blender po STALL_TIMEOUT_S nevypise ani radek, zabijeme ho
# a ohlasime chybu - uloha se vrati serveru misto tichého viseni.
STALL_TIMEOUT_S = 900   # 15 min bez jedineho radku vystupu = zaseknuto

# Postup Cycles ze stdout Blenderu, napr.:
#   Fra:1 Mem:120M | Time:00:05.12 | Remaining:01:02.33 | ... | Sample 128/4096
RE_SAMPLE = re.compile(r"Sample (\d+)/(\d+)")
RE_REMAIN = re.compile(r"Remaining:([\d:.]+)")
RE_PREVIEW = re.compile(r"^PREVIEW (\{.*\})$")
# Robert pres bot3 (2026-09-11, opakovane a duraznē): "hotove rendery se
# musi ukladat na sdileny disk OKAMZITE po vytvoreni". Min. odstup je jen
# pojistka proti zaplave, kdyby nekdy snimek renderoval < 1 s - u otocky to
# je vzdy radove desitky sekund az minuty, takze prakticky posilame KAZDY.
TT_PREVIEW_MIN_ODSTUP_S = 1.0


def read_lines_with_watchdog(proc, on_line, stall_timeout=STALL_TIMEOUT_S):
    """Cte stdout procesu v samostatnem vlakne a hlida, ze aspon obcas
    neco prijde. Vraci (vsechen_vystup, zaseknuto?). Cteni musi byt ve
    vlakne - proc.stdout.readline() se neda prerusit timeoutem."""
    lines = []
    last = [time.time()]
    done = threading.Event()

    def pump():
        try:
            for line in proc.stdout:
                lines.append(line)
                last[0] = time.time()
                on_line(line)
        except Exception:
            pass
        finally:
            done.set()

    t = threading.Thread(target=pump, name="blender-stdout", daemon=True)
    t.start()
    stalled = False
    while not done.wait(10):
        if time.time() - last[0] > stall_timeout:
            stalled = True
            vypis("  ZASEKNUTO: Blender %d min nic nevypsal, ukoncuji ho."
                  % (stall_timeout // 60))
            try:
                proc.kill()
            except Exception:
                pass
            done.wait(30)
            break
    proc.wait()
    return "".join(lines), stalled


def run_turntable_job(job, work):
    """Robert 2026-09-09 ("budes delat rendery na nase produktove sestavy
    podle nastaveni VPS blenderu a na vzdalenem GPU") - treti typ ulohy:
    CELY otocny nahled produktove sestavy (162 snimku prstencu + 5 stills)
    z jedne sceny, jednim spustenim Blenderu.

    Proc jednim spustenim: sestava ma pres sto dilu, jejich import a
    priprava materialu trva dele nez samotny render jednoho snimku -
    spoustet Blender 167x by byl nesmysl. Skript si kameru presouva sam.

    Vysledek se vraci jako JEDEN ZIP, ne 167 POSTu.

    Sablona (.blend z VPS Blenderu) je volitelna - kdyz ji uloha ma, otevre
    se jako soubor a skript z ni prebere world/svetla/engine/vzorky/
    materialy. Viz PRODUKTOVE_RENDERY.md."""
    job_id = job["job_id"]
    job_json = os.path.join(work, "job.json")
    frames_dir = os.path.join(work, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    # 1) job JSON
    status, body, _ = http_get(job["job_url"], timeout=120)
    if status != 200:
        vypis("  nepodarilo se stahnout job JSON:", status)
        posli_chybu_serveru(job["result_url"], "Nepodarilo se stahnout job JSON (HTTP %s)." % status)
        return
    cfg = json.loads(body.decode("utf-8"))

    # 2) renderovaci skript (vzdy ze serveru - agent nikdy nema starou verzi)
    status, body, _ = http_get(job["script_url"], timeout=60)
    if status != 200:
        vypis("  nepodarilo se stahnout renderovaci skript:", status)
        posli_chybu_serveru(job["result_url"], "Nepodarilo se stahnout renderovaci skript (HTTP %s)." % status)
        return
    script_path = os.path.join(work, "blender_render_turntable.py")
    with open(script_path, "wb") as fh:
        fh.write(body)

    # 3) unikatni .glb dilu (sestava o 128 dilech byva jen ~9 souboru)
    glb_dir = os.path.join(work, "glb")
    os.makedirs(glb_dir, exist_ok=True)
    local_glb = {}
    for item in job.get("glb_files", []):
        status, body, _ = http_get(item["url"], timeout=300)
        if status != 200:
            # Karoserie (item["required"]==False, bot3 2026-09-11: render
            # spadl na chybejicim souboru, "karoserie je doplnek, ne
            # podminka") - chybejici doplnek se preskoci a zaloguje,
            # zbytek ulohy pokracuje. Dily sestavy (required=True,
            # chybi u starsich uloh bez tohoto pole - proto .get(...,
            # True), aby se chovani nezmenilo) zustavaji povinne.
            if item.get("required", True):
                vypis("  nepodarilo se stahnout dil %s: %s" % (item["key"], status))
                posli_chybu_serveru(job["result_url"],
                                    "Nepodarilo se stahnout dil %s (HTTP %s)." % (item["key"], status))
                return
            vypis("  VAROVANI: nepodarilo se stahnout doplnkovy soubor %s (%s) - "
                  "pokracuji bez nej" % (item["key"], status))
            continue
        path = os.path.join(glb_dir, item["key"])
        with open(path, "wb") as fh:
            fh.write(body)
        local_glb[item["key"]] = path
    vypis("  stazeno %d unikatnich .glb pro %d dilu" % (len(local_glb), len(cfg.get("parts") or [])))

    # 4) volitelna sablona
    template = None
    if job.get("template_url"):
        status, body, _ = http_get(job["template_url"], timeout=600)
        if status == 200:
            template = os.path.join(work, "template.blend")
            with open(template, "wb") as fh:
                fh.write(body)
            vypis("  sablona stazena (%.1f MB)" % (len(body) / 1048576.0))
        else:
            vypis("  VAROVANI: sablonu se nepodarilo stahnout (%s), renderuji bez ni" % status)

    # 4b) volitelna VD_ material knihovna (bot4 2026-09-21, nativni_material
    # vetev/vanDrawee) - stejny vzor jako sablona vyse, jiny soubor.
    vd_materialy = None
    if job.get("vd_materialy_url"):
        status, body, _ = http_get(job["vd_materialy_url"], timeout=120)
        if status == 200:
            vd_materialy = os.path.join(work, "vd_materialy.blend")
            with open(vd_materialy, "wb") as fh:
                fh.write(body)
            vypis("  VD material knihovna stazena (%.1f KB)" % (len(body) / 1024.0))
        else:
            vypis("  VAROVANI: VD material knihovnu se nepodarilo stahnout (%s)" % status)

    # 5) dosadit lokalni cesty a spustit
    cfg["vd_materialy_path"] = vd_materialy
    for pt in cfg.get("parts") or []:
        pt["glb"] = local_glb.get(pt.get("glb_key"))
    cfg["parts"] = [pt for pt in (cfg.get("parts") or []) if pt.get("glb")]
    # Karoserie - stejny princip, ale chybejici soubory se jen VYNECHAJI
    # (ne cely dil zahodi jako u parts) - blender_render_turntable.py umi
    # pracovat i s neuplnou trojici (skusi, co ma, zbytek zaloguje).
    # `glb_files` se VZDY normalizuje na seznam (i kdyz server posle null
    # nebo klic chybi uplne) - .get(x, []) chrani jen proti chybejicimu
    # klici, ne proti ulozenemu null, a presne tahle mezera dnes shodila
    # render (bot3 2026-09-11).
    kar = cfg.get("karoserie_odraz") or {}
    if kar.get("glb_keys"):
        kar["glb_files"] = [local_glb[k] for k in kar["glb_keys"] if k in local_glb]
        if len(kar["glb_files"]) < len(kar["glb_keys"]):
            vypis("  VAROVANI: karoserie ma jen %d/%d souboru (zbytek se nestahl)"
                  % (len(kar["glb_files"]), len(kar["glb_keys"])))
    else:
        kar["glb_files"] = kar.get("glb_files") or []
    cfg["karoserie_odraz"] = kar
    cfg["out_dir"] = frames_dir
    with open(job_json, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False)

    total = (len(cfg.get("elevations") or []) * len(cfg.get("azimuths") or [])
             + len(cfg.get("stills") or []))
    vypis("  renderuji otocny nahled: %s (%d smeru + stills)"
          % (cfg.get("assembly_name", "?"), total))
    t0 = time.time()
    cmd = ([BLENDER_EXE, "-b", "-noaudio"] + ([template] if template else [])
           + ["-P", script_path, "--", job_json])
    # Bez tohohle renderuje otocny nahled na CPU (Robert 2026-09-09:
    # "v blenderu je nastaveno cpu to je divne") - promenna se driv
    # predavala jen u GLB uloh, u turntable se zapomnela.
    env = dict(os.environ)
    env["KONF_GPU_BACKEND"] = GPU_BACKEND.upper()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", env=env)
    last_report = [0.0]
    last_vzorky = [0.0]

    def posli_postup(note, min_odstup):
        """Serveru staci vedet, ze se porad neco deje (viz /progress).
        Posila se skrz, ne kazdy radek - odtud min_odstup."""
        if time.time() - last_report[0] < min_odstup:
            return
        last_report[0] = time.time()
        try:
            http_post("/api/render-worker/job/%s/progress" % job_id,
                      json.dumps({"note": note[:200]}).encode("utf-8"),
                      {"Content-Type": "application/json"}, timeout=20)
        except Exception:
            pass

    last_tt_preview = [0.0]
    tt_preview_bezi = [False]

    def posli_tt_nahled(meta):
        """Master snimek hned po dorenderovani - NA POZADI, nikdy neblokuje
        Blender ani cteni dalsich radku stdout. Robert pres bot3
        (2026-09-11, opakovane): "hotove rendery se musi ukladat na
        sdileny disk okamzite po vytvoreni" - proto se posila kazdy snimek
        (viz TT_PREVIEW_MIN_ODSTUP_S), ne kazdy N-ty.

        Kdyz predchozi odeslani jeste bezi (pomala sit), tenhle snimek se
        PRESKOCI - nikdy se nefronta vlaken, ktera by se casem hromadila.
        Dalsi snimek prijde za chvili znovu, takze se nic natrvalo neztrati.
        """
        if time.time() - last_tt_preview[0] < TT_PREVIEW_MIN_ODSTUP_S:
            return
        if tt_preview_bezi[0]:
            return
        last_tt_preview[0] = time.time()

        def _posli():
            tt_preview_bezi[0] = True
            try:
                with open(meta["path"], "rb") as fh:
                    data = fh.read()
                url = ("/api/render-worker/job/%s/tt-frame?el=%s&az=%s&tier=%s"
                      % (job_id, meta["el"], meta["az"], meta["tier"]))
                code = http_post(url, data, timeout=30)
                vypis("    prubezny snimek odeslan (e%+d a%03d, %d kB, HTTP %s)"
                      % (meta["el"], meta["az"], round(len(data) / 1024), code))
            except Exception as e:
                # Render nesmi zastavit kvuli spatne siti - jen zaloguj a jed dal.
                vypis("    prubezny snimek se nepodarilo poslat (render pokracuje):", e)
            finally:
                tt_preview_bezi[0] = False

        threading.Thread(target=_posli, name="tt-preview", daemon=True).start()

    def on_line(line):
        # Robert 2026-09-09: "uprav to tak, aby byl videt prubeh
        # renderovani v oknu terminalu". Cycles hlasi postup na stdout
        # (napr. "... | Remaining:01:02.33 | ... | Sample 128/4096"),
        # ale agent to drive zahazoval, takze okno pri dlouhem renderu
        # nekolik minut mlcelo a vypadalo zaseknute.
        m = RE_SAMPLE.search(line)
        if m:
            if time.time() - last_vzorky[0] >= 2.0:   # ne kazdy radek, jinak zaplava
                last_vzorky[0] = time.time()
                r = RE_REMAIN.search(line)
                hotovo, celkem = int(m.group(1)), int(m.group(2))
                pct = 100.0 * hotovo / celkem if celkem else 0.0
                vypis("      vzorky %d/%d (%.0f %%)%s"
                      % (hotovo, celkem, pct,
                         ", zbyva %s" % r.group(1) if r else ""))
                # bot8 2026-09-09: postup se driv hlasil JEN na radcich
                # "SNIMEK", tedy jednou za cely snimek - jenze jeden
                # snimek 2048px pri vysokych vzorcich bezi i pres 5 minut
                # a server mezitim ulohu povazoval za nemou. Vzorky
                # dokazuji beh spolehlive, staci je posilat rozvolnene.
                posli_postup(line.strip(), 30)
            return
        mp = RE_PREVIEW.match(line.strip())
        if mp:
            try:
                posli_tt_nahled(json.loads(mp.group(1)))
            except (ValueError, KeyError):
                pass  # spatny radek se jen ignoruje, render bezi dal
            return
        if line.startswith("SNIMEK "):
            vypis("   ", line.rstrip()[:120])
            posli_postup(line.strip(), 10)
        elif "error" in line.lower() or "traceback" in line.lower():
            vypis("   ", line.rstrip()[:150])

    out, stalled = read_lines_with_watchdog(proc, on_line)
    if stalled:
        posli_chybu_serveru(job["result_url"],
                            "Blender se zasekl (%d min bez vystupu), ukoncen." % (STALL_TIMEOUT_S // 60))
        return

    if "TURNTABLE_OK" not in out:
        tail = out[-1500:]
        vypis("  render selhal, posilam chybu na server")
        posli_chybu_serveru(job["result_url"], tail.replace("\n", " "))
        return

    # 6) zabalit a poslat
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:   # JPEG uz je komprimovany
        for name in sorted(os.listdir(frames_dir)):
            zf.write(os.path.join(frames_dir, name), name)
    payload = buf.getvalue()
    vypis("  hotovo za %.0f s, posilam %d souboru (%.1f MB)"
          % (time.time() - t0, len(os.listdir(frames_dir)), len(payload) / 1048576.0))
    # http_post vraci JEN cislo (HTTP status), ne trojici - rozbalovani do
    # tri promennych hazelo "cannot unpack non-iterable int object" AZ PO
    # odeslani, takze render byl na serveru, ale agent hlasil chybu
    # (chyceno 2026-09-09 na Robertove PC).
    status = http_post(job["result_url"], payload,
                       {"Content-Type": "application/zip"}, timeout=1800)
    if status == 200:
        vypis("  vysledek odeslan (HTTP 200)")
    else:
        vypis("  POZOR: server odmitl vysledek, HTTP %s" % status)


def run_job(job):
    job_id = job["job_id"]
    work = tempfile.mkdtemp(prefix="render_" + job_id[:8] + "_")
    try:
        if job.get("job_type") == "blend":
            run_blend_job(job, work)
            return
        if job.get("job_type") == "turntable":
            run_turntable_job(job, work)
            return
        settings = job["settings"]
        # 1) model + renderovaci skript + textury/HDRI
        glb = os.path.join(work, "model.glb")
        status, body, _ = http_get(job["model_url"], timeout=180)
        if status != 200:
            vypis("  nepodarilo se stahnout model:", status)
            return
        with open(glb, "wb") as fh:
            fh.write(body)

        status, body, _ = http_get(job["script_url"], timeout=60)
        if status != 200:
            vypis("  nepodarilo se stahnout renderovaci skript:", status)
            return
        script_body = body.decode("utf-8")

        textures = {}
        hdri_path = None
        for a in job.get("assets", []):
            status, body, hdrs = http_get(a["url"], timeout=240)
            if status != 200:
                vypis("  nepodarilo se stahnout", a["key"], status)
                return
            # priponu vezmeme z hlavicky, jinak Blender nepozna format
            ctype = hdrs.get("Content-Type", "")
            ext = {"image/jpeg": ".jpg", "image/png": ".png"}.get(ctype, "")
            if a["key"] == "hdri":
                ext = ".exr" if "exr" in (hdrs.get("Content-Disposition", "") or "").lower() else ".hdr"
            dest = os.path.join(work, a["key"].replace(":", "_") + (ext or ".bin"))
            with open(dest, "wb") as fh:
                fh.write(body)
            if a["key"] == "hdri":
                hdri_path = dest
            else:
                textures[a["role"]] = dest

        # 2) konfigurace s LOKALNIMI cestami
        out_png = os.path.join(work, "out.png")
        preview_png = os.path.join(work, "preview.png")
        cfg = dict(settings)
        cfg.update({"glb_path": glb, "output_path": out_png,
                    "preview_path": preview_png,
                    "hdri_path": hdri_path, "textures": textures})
        cfg_path = os.path.join(work, "cfg.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False)

        # 3) renderovaci skript (stazeny ze serveru, at je vzdy aktualni)
        script_path = os.path.join(work, "run.py")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(script_body)

        # GPU se predava PROMENNOU PROSTREDI, ne vlozenym kodem pred
        # skript. Duvod (Robert 2026-08-11 - "porovnej to"): skript volá
        # bpy.ops.wm.read_factory_settings(), coz resetuje i uzivatelske
        # predvolby Cycles - takze prelude GPU sice zapnul, ale o par
        # radku pozdeji se vyber zarizeni zase zahodil a RTX 4080 se k
        # renderu vubec nedostala (bezelo to na CPU notebooku).
        env = dict(os.environ)
        env["KONF_GPU_BACKEND"] = GPU_BACKEND.upper()

        vypis(f"  renderuji ({settings.get('samples')} vzorku, "
              f"{settings.get('resolution_x')}x{settings.get('resolution_y')})...")
        t0 = time.time()
        proc = subprocess.Popen(
            [BLENDER_EXE, "-b", "-noaudio", "-P", script_path, "--", cfg_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", bufsize=1, env=env,
        )

        # Robert 2026-08-11 ("jeden obyc obrazek a stale nemam obraz, neco
        # je spatne"): vypis Blenderu se driv jen posbiral a ukazal az na
        # KONCI - kdyz render trval dlouho, nikdo nevedel, jestli vubec
        # bezi, jestli chytil GPU, ani na kolikatem vzorku je. Ted se
        # zajimave radky (zarizeni, vzorky, chyby) tisknou ZIVE.
        out_lines = []
        last_sent = 0
        last_progress = 0

        def pump_output():
            for line in proc.stdout:
                out_lines.append(line)
                low = line.lower()
                if ("gpu backend" in low or "gpu zarizeni" in low or "error" in low or "warning: cycles" in low
                        or "cuda" in low or "optix" in low or "traceback" in low
                        or "pass_done" in low):
                    vypis("   ", line.rstrip()[:150])

        t_out = threading.Thread(target=pump_output, daemon=True)
        t_out.start()

        # prubezne nahledy posilame, jakmile je Blender zapise
        while proc.poll() is None:
            time.sleep(1)
            if time.time() - last_progress > 15:
                last_progress = time.time()
                el = round(time.time() - t0)
                # Posledni radek z Blenderu rekne, v jake fazi jsme
                # (napr. "Loading render kernels" = kompilace GPU jader,
                # ktera pri prvnim OptiX renderu trva i minuty).
                faze = ""
                for ln in reversed(out_lines[-40:]):
                    ln = ln.strip()
                    if ln and "|" in ln:
                        faze = ln.split("|")[-1].strip()[:60]
                        break
                vypis(f"    ...renderuji {el} s  {faze}")
                # dat serveru vedet, ze porad pracujeme (jinak by ulohu
                # po chvili prohlasil za spadlou)
                http_post(f"/api/render-worker/job/{job_id}/progress",
                          json.dumps({"note": faze or f"{el} s"}).encode("utf-8"),
                          {"Content-Type": "application/json"}, timeout=20)
            try:
                if os.path.exists(preview_png):
                    m = os.path.getmtime(preview_png)
                    if m > last_sent:
                        with open(preview_png, "rb") as fh:
                            data = fh.read()
                        code = http_post(f"/api/render-worker/job/{job_id}/preview",
                                         data, timeout=120)
                        vypis(f"    nahled odeslan ({round(len(data)/1024)} kB, HTTP {code})")
                        last_sent = m
            except Exception as e:
                vypis("    nahled se nepodarilo poslat:", e)

        t_out.join(timeout=5)
        out = "".join(out_lines)
        if "RENDER_OK" not in out or not os.path.exists(out_png):
            tail = out[-800:]
            vypis("  CHYBA renderu:", tail[-300:])
            posli_chybu_serveru(f"/api/render-worker/job/{job_id}/result", tail.replace("\n", " "))
            return

        with open(out_png, "rb") as fh:
            http_post(f"/api/render-worker/job/{job_id}/result", fh.read(),
                      {"Content-Type": "image/png"}, timeout=600)
        vypis(f"  hotovo za {round(time.time() - t0, 1)} s, odeslano")
    except Exception:
        # bot4 2026-09-13, Robert ("evidentne ta sluzba naprogramovana
        # spatne"): sit pro cokoli, co nechyti specificke osetreni chyb
        # uvnitr run_blend_job()/run_turntable_job()/legacy vetve vyse
        # (chybny HTTP status uz vraci citelnou chybu primo tam, viz
        # jejich vlastni http_post volani). Nezachycena VYJIMKA (KeyError,
        # network chyba neosetrena v http_get, spatny JSON...) driv
        # propadla az VEN z run_job() BEZE ZPRAVY SERVERU - vnejsi smycka
        # v main() ji jen vypsala lokalne (`vypis("  chyba spojeni:", e)`)
        # a jela dal, takze uloha zustala serveru navzdy "running" (presne
        # dnesni zaseknuti - 6 uloh Jumpy Crew Cab, zadna nedostala
        # citelnou chybu ani po prvni oprave tohohle souboru, protoze
        # tenhle pad nebyl v zadnem z tri drive osetrenych HTTP-status
        # mist). Chyba se posle serveru A ZNOVU VYHODI (re-raise) - vnejsi
        # try/except v main() se tak chova stejne jako driv (5s pauza,
        # dalsi poll), jen server tentokrat vi proc.
        tb = traceback.format_exc()
        vypis("  NEOCEKAVANA VYJIMKA v ulose:\n", tb)
        # Legacy (job_type glb) job nema "result_url" - uklada si svoji
        # cestu primo z job_id (viz vyse), na rozdil od blend/turntable.
        vysledkova_cesta = job.get("result_url") or f"/api/render-worker/job/{job_id}/result"
        posli_chybu_serveru(vysledkova_cesta, "Neocekavana vyjimka v agentovi: " + tb.replace("\n", " | "))
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    # Robert 2026-08-11 ("tlacitko Nabidka s rendery, kde se zaroven
    # automaticky spusti agent na mem pc"): agenta muze spustit i klik v
    # prohlizeci (protokol logimanrender://, viz INSTALACE_PROTOKOLU.reg)
    # - klidne i ve chvili, kdy uz bezi. Pojistka jedne instance: bind na
    # lokalni port; kdyz je obsazeny, agent uz bezi a tahle kopie hned
    # skonci (zadne dva agenty, zadne dvoji vyzvedavani uloh).
    import socket
    global _single_instance_lock
    _single_instance_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _single_instance_lock.bind(("127.0.0.1", 47653))
    except OSError:
        vypis("Agent uz bezi (port 47653 je obsazeny) - tahle kopie konci.")
        time.sleep(2)
        sys.exit(EXIT_ALREADY_RUNNING)

    if TOKEN == "SEM_VLOZ_TOKEN":
        vypis("Nejdriv nastav RENDER_WORKER_TOKEN (viz KONFIGURACE v tomhle souboru).")
        sys.exit(EXIT_CONFIG)
    if not os.path.exists(BLENDER_EXE):
        vypis("Blender nenalezen%s.\nAgent ho hleda sam (PATH + obvykle adresare) - kdyz je "
              "jinde, spust:\n  set BLENDER_EXE=C:\\cesta\\k\\blender.exe   (Windows)\n"
              "  export BLENDER_EXE=/cesta/k/blender          (Linux/macOS)"
              % (f": {BLENDER_EXE}" if BLENDER_EXE else ""))
        sys.exit(EXIT_CONFIG)

    keep_awake()
    quick_edit = _vypnout_quick_edit()
    # Uspesna aktualizace = bezim uz v te verzi, kterou marker hlida.
    if _marker_nacti().get("verze") == AGENT_VERSION:
        try:
            os.remove(_UPDATE_MARKER)
        except OSError:
            pass
    threading.Thread(target=heartbeat_loop, name="heartbeat", daemon=True).start()
    threading.Thread(target=hlidac_smycky, name="hlidac-smycky", daemon=True).start()
    vypis(f"Renderovaci agent bezi (verze {AGENT_VERSION}).\n  server: {SERVER}\n  jmeno:  {WORKER_NAME}"
          f"\n  GPU:    {GPU_INFO}\n  blender:{BLENDER_EXE}"
          f"\n  uspani: {'zakazano po dobu behu' if sys.platform.startswith('win') else 'neresi se (neni Windows)'}"
          f"\n  konzole:{'QuickEdit vypnut (klik do okna uz agenta nezastavi)' if quick_edit else 'QuickEdit se nepodarilo vypnout - vypis se pri zamrznuti zahazuje'}"
          f"\nCtrl+C ukonci.\n")
    try:
        if zkusit_aktualizaci():
            time.sleep(2)          # at vypis stihne projit
            sys.exit(EXIT_RESTART)
    except Exception as e:         # noqa: BLE001 - aktualizace nesmi shodit agenta
        vypis("  kontrola verze selhala:", e)
    posledni_kontrola = [time.time()]
    while True:
        try:
            if time.time() - posledni_kontrola[0] > UPDATE_CHECK_S:
                posledni_kontrola[0] = time.time()
                if zkusit_aktualizaci():
                    time.sleep(2)
                    sys.exit(EXIT_RESTART)
            status, data = http_get_json("/api/render-worker/poll",
                                         {"name": WORKER_NAME, "gpu": GPU_INFO,
                                          "since": round(AGENT_SINCE)}, timeout=40)
            if status == 401:
                vypis("Neplatny token - zkontroluj RENDER_WORKER_TOKEN.")
                time.sleep(15)
                continue
            if status != 200:
                # bot8 2026-09-09: JEDNA chyba serveru nesmi frontu
                # zastavit natrvalo (presne to se stalo v 17:57:32 -
                # jeden HTTP 500 a agent uz se nikdy nezeptal). Razitko
                # se tu ZAMERNE neposouva - hlidac_smycky() proto po
                # POLL_RESTART_S agenta restartuje, kdyby server chyboval
                # trvale a smycka se z toho nedokazala vyhrabat sama.
                vypis("  server odpovedel:", status, "- zkusim to znovu za 5 s")
                time.sleep(5)
                continue
            _stav_smycky["posledni_poll"] = time.time()
            job = (data or {}).get("job")
            if job:
                vypis(f"[{time.strftime('%H:%M:%S')}] uloha {job['job_id'][:8]}")
                _stav_smycky["uloha"] = job["job_id"]
                try:
                    run_job(job)
                finally:
                    _stav_smycky["uloha"] = None
                    _stav_smycky["posledni_poll"] = time.time()
            else:
                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            vypis("\nKonec.")
            return
        except Exception as e:  # noqa: BLE001 - agent musi prezit vypadek site
            vypis("  chyba spojeni:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
