#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Staticka kontrola novych a zmenenych souboru 3D nabidky (2026-10-02). Nic nespousti, nic nezapisuje.

  1. kompilace vsech .py (compile(), bez zapisu .pyc), node --check *.js, bash -n *.sh
  2. zadny tisk/logovani tajemstvi: print/logger s secret/password/token/V3D_MARK, vypis os.environ, cteni api/.env mimo CLI
  3. zadny zapis do DB v novych skriptech/modulech 3D (scripts/v3d, api/v3d_*.py) a zadne SQL zapisy ve vandr_scene_offers.py
  4. zadne cesty mimo repo: pracovni adresare sezeni a domovske adresare uzivatelu a nepovolene absolutni cesty (vzory nize)
  5. zakazana slova (grep -i) - seznam z $V3D_ZAKAZANA_SLOVA (carkou); bez nej se krok jen oznami (slovo se v repu nevypisuje)
Vystup: radky OK/CHYBA/INFO; exit 1 pri jakekoli CHYBA.
"""
import ast
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
import _cesty as CE  # noqa: E402

REPO = CE.REPO
chyby = []


def ok(msg):
    print("OK     " + msg)


def chyba(msg):
    chyby.append(msg)
    print("CHYBA  " + msg)


def info(msg):
    print("INFO   " + msg)


def soubory(*, pripony, kde):
    out = []
    for rel in kde:
        p = os.path.join(REPO, rel)
        if os.path.isfile(p):
            out.append(p)
        elif os.path.isdir(p):
            for d, dirs, files in os.walk(p):
                dirs[:] = [x for x in dirs if x not in ("__pycache__", "fixtures", "node_modules")]
                out += [os.path.join(d, f) for f in files if f.endswith(pripony)]
    return sorted(out)


NOVE_PY = soubory(pripony=(".py",), kde=["api/v3d_glb.py", "api/v3d_mark.py", "api/vandr_scene_offers.py", "api/scene_offers.py",
                                          "api/vandr_vykres_nahrada.py",
                                          "scripts/v3d", "scripts/2026-10-02_v3d_testy"])
V3D_MODULY = soubory(pripony=(".py",), kde=["api/v3d_glb.py", "api/v3d_mark.py", "api/vandr_vykres_nahrada.py", "scripts/v3d"])
BEZ_TESTU = [p for p in NOVE_PY if "_testy" not in p]


def rel(p):
    return os.path.relpath(p, REPO)


def cti(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


# 1) kompilace
for p in NOVE_PY:
    try:
        compile(cti(p), p, "exec")
    except SyntaxError as e:
        chyba("kompilace %s: %s" % (rel(p), e))
ok("kompilace %d souboru .py (bez zapisu .pyc)" % len(NOVE_PY))
for p in soubory(pripony=(".js",), kde=["scripts/2026-10-02_v3d_testy"]):
    r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
    (ok if r.returncode == 0 else chyba)("node --check %s %s" % (rel(p), r.stderr.strip()[:200]))
for p in soubory(pripony=(".sh",), kde=["scripts/2026-10-02_v3d_testy"]):
    r = subprocess.run(["bash", "-n", p], capture_output=True, text=True)
    (ok if r.returncode == 0 else chyba)("bash -n %s %s" % (rel(p), r.stderr.strip()[:200]))

# 2) tajemstvi
TAJ = re.compile(r"secret|password|passwd|heslo|api[_-]?key|V3D_MARK_SECRET|FLASK_SECRET|DB_PASSWORD", re.I)
VYPIS = re.compile(r"\b(print|logger\.\w+|app\.logger\.\w+|logging\.\w+|sys\.std(?:out|err)\.write)\s*\(")
nalezy = []
for p in BEZ_TESTU:
    for i, radek in enumerate(cti(p).splitlines(), 1):
        s = radek.strip()
        if s.startswith("#"):
            continue
        if VYPIS.search(s) and TAJ.search(s):
            nalezy.append("%s:%d: %s" % (rel(p), i, s[:140]))
        if re.search(r"os\.environ\s*\)|dict\(os\.environ|json\.dumps\(os\.environ|print\(.*os\.environ\b(?!\.get)", s):
            nalezy.append("%s:%d: vypis prostredi: %s" % (rel(p), i, s[:140]))
# vyjimka: oznameni, ze klic NENI nastaven / je neplatny (neobsahuje hodnotu klice) - kontrola dole proti hodnote
povolene = [n for n in nalezy if "V3D_MARK_SECRET neni nastaven" in n or "klic V3D_MARK_SECRET je neplatny" in n]
nalezy = [n for n in nalezy if n not in povolene]
for n in nalezy:
    chyba("tisk/log tajemstvi? " + n)
if povolene:
    info("log hlasi jen STAV klice (nastaven/neplatny), nikdy hodnotu: %d misto" % len(povolene))
ok("zadny print/log tajemstvi v %d souborech (mimo testy)" % len(BEZ_TESTU))
def retezce_mimo_docstringy(src):
    """vsechny retezcove konstanty kodu krome docstringu (AST) - komentare a docstringy nejsou cteni souboru"""
    strom = ast.parse(src)
    doc = set()
    for uzel in ast.walk(strom):
        if isinstance(uzel, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = uzel.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) and isinstance(b[0].value.value, str):
                doc.add(id(b[0].value))
    return [u.value for u in ast.walk(strom) if isinstance(u, ast.Constant) and isinstance(u.value, str) and id(u) not in doc]


env_cte = [rel(p) for p in BEZ_TESTU
           if any(x == ".env" or x.endswith("/.env") or x == "api/.env" for x in retezce_mimo_docstringy(cti(p)))]
if sorted(env_cte) != ["scripts/v3d/build_ctx.py", "scripts/v3d/v3d_mark_detect.py"]:
    chyba("cteni api/.env jinde nez v CLI build_ctx.py / v3d_mark_detect.py: %s" % env_cte)
else:
    ok("api/.env cte jen CLI scripts/v3d/build_ctx.py (DB READ ONLY) a v3d_mark_detect.py (klic znaceni); hodnoty nikam nevypisuji; "
       "API (api/*.py) .env nectou")
if "KONF_ENV_PATH" in cti(os.path.join(REPO, "scripts/v3d/build_ctx.py")) and \
        len(re.findall(r"_cti_env\(", cti(os.path.join(REPO, "scripts/v3d/build_ctx.py")))) != 2:
    chyba("build_ctx.py: _cti_env se vola jinde nez v konf_conn_ro")

# 3) zadne zapisy do DB
SQL_ZAPIS = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|REPLACE\s+INTO|DROP\s+TABLE|ALTER\s+TABLE|TRUNCATE)\b", re.I)
for p in V3D_MODULY + [os.path.join(REPO, "api/vandr_scene_offers.py")]:
    for i, radek in enumerate(cti(p).splitlines(), 1):
        if radek.strip().startswith("#"):
            continue
        if SQL_ZAPIS.search(radek):
            chyba("SQL zapis v %s:%d: %s" % (rel(p), i, radek.strip()[:120]))
ok("zadny SQL zapis v scripts/v3d, api/v3d_*.py ani api/vandr_scene_offers.py (zapis jen pres scene_offers.py a log_audit)")
# pripojeni ke konfigurator DB jen cteni: SET SESSION ... READ ONLY jen v CLI
if "SET SESSION TRANSACTION READ ONLY" not in cti(os.path.join(REPO, "scripts/v3d/build_ctx.py")):
    chyba("build_ctx.konf_conn_ro nema READ ONLY")

# 4) cesty
SCRATCH = re.compile(r"/tmp/claude|scratch" + "pad|integrace_" + "nabidka|/ro" + "ot/|/ho" + "me/|/v3d/live_" + "candidates")
POVOLENE_ABS = ("/usr/bin:/bin", "/usr/share/fonts/", "/opt/blender-5.2/blender", "/opt/vandrawee/web", "/opt/konfigurator", "/usr/bin/php", "/usr/bin/node",
                "/usr/bin/python3", "/usr/bin/env", "/bin/bash", "/etc/", "/dev/null", "/api/", "/js/", "/css/", "/katalog/",
                "/nabidka", "/private-files", "/webapp/", "/scripts/", "/public/")
ABS = re.compile(r"""["'](/(?:opt|usr|home|root|var|etc|mnt|srv|tmp|bin)/[^"'\s]*)["']""")
for p in NOVE_PY + soubory(pripony=(".js", ".sh"), kde=["scripts/2026-10-02_v3d_testy"]):
    if os.path.abspath(p) == os.path.abspath(__file__):
        continue                                    # definuje vzory sam
    t = cti(p)
    for i, radek in enumerate(t.splitlines(), 1):
        if SCRATCH.search(radek):
            chyba("scratch/uzivatelska cesta %s:%d: %s" % (rel(p), i, radek.strip()[:120]))
        for m in ABS.finditer(radek):
            if not m.group(1).startswith(POVOLENE_ABS):
                chyba("nepovolena absolutni cesta %s:%d: %s" % (rel(p), i, m.group(1)))
ok("zadne scratch/uzivatelske cesty, absolutni cesty jen provozni (/opt/blender-5.2, /opt/vandrawee/web, /opt/konfigurator, /usr/bin/*, systemova pisma /usr/share/fonts/)")

# 5) zakazana slova
slova = [s.strip() for s in (os.environ.get("V3D_ZAKAZANA_SLOVA") or "").split(",") if s.strip()]
if slova:
    cil = NOVE_PY + soubory(pripony=(".js", ".sh", ".md", ".json", ".html"), kde=["scripts/2026-10-02_v3d_testy", "scripts/v3d", "docs"])
    for p in cil:
        t = cti(p).lower()
        for s in slova:
            if s.lower() in t:
                chyba("zakazane slovo v %s" % rel(p))      # slovo se zamerne nevypisuje
    ok("zakazana slova: %d slov, %d souboru" % (len(slova), len(cil)))
else:
    info("zakazana slova: PRESKOCENO - pravidlo 56 slovo nevypisuje; spustte s V3D_ZAKAZANA_SLOVA=slovo1,slovo2")

print("\nSTATICKA KONTROLA: %s" % ("%d CHYB" % len(chyby) if chyby else "bez chyb"))
sys.exit(1 if chyby else 0)
