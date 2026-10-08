#!/usr/bin/env python3
"""Mutace zaplaty razitek (bot8, 2026-10-08, WORKFLOW pravidlo 61): do KANDIDATNIHO api/stul_glb.py (po patches/patch_glb.py) se postupne vnese jedna chyba a testy musi selhat.
Kazda mutace = kopie kandidatniho api (symlinky) s upravenym stul_glb.py, test_razitka_vychozi.py (hermeticky) a u mutaci vazanych na verejnou routu i test_razitka_shop.py (DB pres systemd-run).
  mutace.py [kandidat = $SP/razitka/cand]  [-j 4]      -> "ZCHYCENO n/m" a seznam prezivsich"""
import concurrent.futures
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
CAND = next((a for a in sys.argv[1:] if not a.startswith("-") and not a.isdigit()), os.path.join(os.environ.get("SP", "/tmp"), "razitka", "cand"))

MUTACE = [
    ("razitka nejsou vychozi", "RAZITKA_VYCHOZI = True ", "RAZITKA_VYCHOZI = False", "vychozi,shop"),
    ("explicitni razitka=False se ignoruje (vzdy razitka)", "    if razitka is None:\n        razitka = RAZITKA_VYCHOZI\n", "    razitka = RAZITKA_VYCHOZI or razitka\n", "vychozi"),
    ("model s razitky se sklada bez razitek", "data = poskladej_glb(r[\"dily\"], r[\"rozmery\"], stul_koty.koty(r), razitka=stul_razitka.razitka(r, h))", "data = poskladej_glb(r[\"dily\"], r[\"rozmery\"], stul_koty.koty(r))", "vychozi,shop"),
    ("model s razitky nenaplni posun (_META_CACHE)", "        _META_CACHE[h] = _POSLEDNI_POSUN[0]\n        _ROZSAHY_CACHE[h] = _POSLEDNI_ROZSAHY[0]\n        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}\n        for c_ in (_GLB_RAZITKA_CACHE",
     "        _ROZSAHY_CACHE[h] = _POSLEDNI_ROZSAHY[0]\n        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}\n        for c_ in (_GLB_RAZITKA_CACHE", "vychozi"),
    ("model s razitky nenaplni rozsahy dilu", "        _ROZSAHY_CACHE[h] = _POSLEDNI_ROZSAHY[0]\n        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}\n        for c_ in (_GLB_RAZITKA_CACHE",
     "        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}\n        for c_ in (_GLB_RAZITKA_CACHE", "vychozi"),
    ("model s razitky nenaplni extra rozsahy", "        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}\n        for c_ in (_GLB_RAZITKA_CACHE", "        for c_ in (_GLB_RAZITKA_CACHE", "vychozi"),
    ("zasah vedlejsich cache pri zasahu do poradi: posun se bere ze stareho stavu", "        _META_CACHE[h] = _POSLEDNI_POSUN[0]\n        _ROZSAHY_CACHE[h] = _POSLEDNI_ROZSAHY[0]\n        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}\n        for c_ in (_GLB_RAZITKA_CACHE",
     "        _META_CACHE[h] = _POSLEDNI_POSUN[0] + 1.0\n        _ROZSAHY_CACHE[h] = _POSLEDNI_ROZSAHY[0]\n        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}\n        for c_ in (_GLB_RAZITKA_CACHE", "vychozi"),
    ("zasah do cache: model s razitky se neulozi", "        _GLB_RAZITKA_CACHE[h] = data\n        _META_CACHE[h]", "        _META_CACHE[h]", "vychozi"),
    ("zasah do cache: zasah bez kontroly vedlejsich cache (zasah po vytlaceni)", "        if h in _GLB_RAZITKA_CACHE and h in _META_CACHE and h in _ROZSAHY_CACHE and h in _EXTRA_CACHE:\n            for c_ in (_GLB_RAZITKA_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE):\n                c_.move_to_end(h)",
     "        if h in _GLB_RAZITKA_CACHE:\n            for c_ in (_GLB_RAZITKA_CACHE,):\n                c_.move_to_end(h)", "vychozi"),
    ("cache razitek neni omezena", "            while len(c_) > CACHE_MAX:\n                c_.popitem(last=False)\n        return h, data\n    if h in _GLB_CACHE", "            while len(c_) > CACHE_MAX * 1000:\n                c_.popitem(last=False)\n        return h, data\n    if h in _GLB_CACHE", "vychozi"),
    ("komprimovana cache klicovana jen hashem", "    klic = (h, kod, len(data))", "    klic = (h, kod)", "vychozi,shop"),
    ("holy model se kvuli vedlejsim cache stavi i pri vychozim modelu (zbytecne dvakrat)", "        r = S.sestav_stul(**parametry)\n        data = poskladej_glb(r[\"dily\"], r[\"rozmery\"], stul_koty.koty(r), razitka=stul_razitka.razitka(r, h))",
     "        model_pro_parametry(parametry, razitka=False)\n        r = S.sestav_stul(**parametry)\n        data = poskladej_glb(r[\"dily\"], r[\"rozmery\"], stul_koty.koty(r), razitka=stul_razitka.razitka(r, h))", "vychozi"),
]


def priprav(n, stare, nove, koren):
    d = os.path.join(koren, f"m{n}", "api")
    os.makedirs(d)
    for f in os.listdir(os.path.join(CAND, "api")):
        if f in ("__pycache__", "stul_glb.py"):
            continue
        os.symlink(os.path.realpath(os.path.join(CAND, "api", f)), os.path.join(d, f))
    os.makedirs(os.path.join(d, "__pycache__"))
    s = open(os.path.join(CAND, "api", "stul_glb.py"), encoding="utf-8").read()
    if s.count(stare) != 1:
        raise SystemExit(f"mutace {n}: kotva nalezena {s.count(stare)}x: {stare[:60]!r}")
    open(os.path.join(d, "stul_glb.py"), "w", encoding="utf-8").write(s.replace(stare, nove))
    return d


def spust(arg):
    n, nazev, stare, nove, testy, koren = arg
    api = priprav(n, stare, nove, koren)
    zchyceno = []
    for t in testy.split(","):
        if t == "vychozi":
            cmd = [PY, os.path.join(HERE, "test_razitka_vychozi.py")]
            env = dict(os.environ, STUL_API_OVERRIDE=api, PYTHONDONTWRITEBYTECODE="1")
        else:
            cmd = ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=/opt/konfigurator/api/.env", "--setenv=HOME=/root", "--setenv=PYTHONDONTWRITEBYTECODE=1", f"--setenv=STUL_API_OVERRIDE={api}",
                   f"--working-directory={REPO}", PY, os.path.join(HERE, "test_razitka_shop.py")]
            env = dict(os.environ)
        try:
            rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, timeout=1200).returncode
        except subprocess.TimeoutExpired:
            rc = 124
        zchyceno.append((t, rc != 0))
    return n, nazev, zchyceno


if __name__ == "__main__":
    j = int(sys.argv[sys.argv.index("-j") + 1]) if "-j" in sys.argv else 4
    koren = tempfile.mkdtemp(prefix="mut_razitka_")
    try:
        seznam = [(i, *m, koren) for i, m in enumerate(MUTACE, 1)]
        zive = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=j) as ex:
            for n, nazev, z in ex.map(spust, seznam):
                chycena = all(ok for _, ok in z)
                print(f"{'ZCHYCENO' if chycena else 'PREZILA '} {n:2d} {nazev}  [{', '.join(t + (':selhal' if ok else ':PROSEL') for t, ok in z)}]", flush=True)
                if not chycena:
                    zive.append(n)
        print(f"\nZCHYCENO {len(MUTACE) - len(zive)}/{len(MUTACE)}" + (f"; prezivsi: {zive}" if zive else ""))
        sys.exit(1 if zive else 0)
    finally:
        shutil.rmtree(koren, ignore_errors=True)
