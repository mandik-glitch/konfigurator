#!/usr/bin/env python3
"""Regresni sada FAZE 2 (bot8, 2026-10-08): existujici testy stolu, dopravniku, registru, kosiku a nabidky z konfigurace nad danym korenem repa (kandidatni <cand>/repo nebo zivy /opt/konfigurator)
+ nove testy oploceni. Kazdy test bezi pres systemd-run (DB jen cte), paralelne; vypise rc a posledni radky. Porovnani: spustit nad kandidatem a nad zivym stromem a porovnat souhrny.
  run_regrese.py <koren repa> <vystupni slozka> [-j 3] [--jen nazev,nazev]"""
import concurrent.futures
import os
import subprocess
import sys

TESTY = [
    ("registr", "scripts/2026-10-07_konfigurator_registr_testy/test_registr.py"),
    ("dopravnik_shop", "scripts/2026-10-07_dopravnik_shop_testy/test_dopravnik_shop.py"),
    ("kosik", "scripts/2026-10-02_konfigurace_kosik_testy/test_kosik_konfigurace.py"),
    ("nabidka", "scripts/2026-10-02_konfigurace_nabidka_testy/test_nabidka_konfigurace.py"),
    ("nabidka_backend", "scripts/2026-10-06_nabidka_tlacitko_testy/test_nabidka_backend_kontrakt.py"),
    ("stul_shop", "scripts/2026-10-02_stul_testy/test_stul_shop.py"),
    ("stul_api", "scripts/2026-10-02_stul_testy/test_stul_api.py"),
    ("oploceni_jadro", "scripts/2026-10-08_oploceni/test_oploceni.py"),
    ("oploceni_shop", "scripts/2026-10-08_oploceni/test_oploceni_shop.py"),
]
NEZAVISLE_NA_DB = {"oploceni_jadro"}


def spust(arg):
    koren, slozka, (nazev, cesta) = arg
    log = os.path.join(slozka, nazev + ".log")
    if not os.path.isfile(os.path.join(koren, cesta)):
        return nazev, None, "soubor testu neexistuje"
    prikaz = ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=/opt/konfigurator/api/.env", "--setenv=HOME=/root", "--setenv=PYTHONDONTWRITEBYTECODE=1",
              f"--working-directory={koren}", "/opt/konfigurator/api/venv/bin/python3", os.path.join(koren, cesta)]
    if nazev in NEZAVISLE_NA_DB:
        prikaz = ["/opt/konfigurator/api/venv/bin/python3", os.path.join(koren, cesta)]
    with open(log, "w", encoding="utf-8") as f:
        try:
            p = subprocess.run(prikaz, cwd=koren, stdout=f, stderr=subprocess.STDOUT, timeout=2400, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    posledni = [x for x in open(log, encoding="utf-8", errors="replace").read().splitlines() if x.strip()][-1:]
    return nazev, rc, (posledni[0][:160] if posledni else "")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    koren, slozka = os.path.abspath(args[0]), os.path.abspath(args[1])
    j = int(sys.argv[sys.argv.index("-j") + 1]) if "-j" in sys.argv else 3
    jen = set(sys.argv[sys.argv.index("--jen") + 1].split(",")) if "--jen" in sys.argv else None
    os.makedirs(slozka, exist_ok=True)
    seznam = [(koren, slozka, t) for t in TESTY if jen is None or t[0] in jen]
    with concurrent.futures.ThreadPoolExecutor(max_workers=j) as ex:
        for nazev, rc, posledni in ex.map(spust, seznam):
            print(f"{nazev:18s} rc={rc} {posledni}", flush=True)
