#!/usr/bin/env python3
"""Spusti ostatni sady testu stolu (mimo kroky scripts/2026-10-02_stul_testy/run_all.sh, ty bere run_suite.py z 2026-10-07_police_stojky) nad danym korenem repa (zivy /opt/konfigurator nebo
kandidatni strom z prepare_cand.sh) paralelne; kazdy test pres systemd-run s prostredim z api/.env (DB se jen CTE).
  run_regrese.py <koren repa> <vystupni slozka> [-j 4] [--jen podretezec,podretezec]  -> pro kazdy test <poradi>.log a souhrn "rc test"
Testy, ktere potrebuji prohlizec (.js) a nasazeny staticky JS, se preskakuji."""
import concurrent.futures
import os
import subprocess
import sys

PY = "/opt/konfigurator/api/venv/bin/python3"
TESTY = [
    "2026-10-02_konfigurace_kosik_testy/test_kosik_konfigurace.py",
    "2026-10-02_konfigurace_nabidka_testy/test_nabidka_konfigurace.py",
    "2026-10-03_miniweb_ceny_eur/test_resolve_eur.py",
    "2026-10-03_miniweb_domena_testy/test_vhost.py",
    "2026-10-03_miniweb_objednavky_testy/test_miniweb_objednavky.py",
    "2026-10-04_stul_host_testy/test_stul_objednavka_host.py",
    "2026-10-04_system40/test_prejimka_system40.py",
    "2026-10-04_system40/test_regrese_35_40_navlek.py",
    "2026-10-04_system40/test_regrese_system30.py",
    "2026-10-04_system40/test_shop_system40.py",
    "2026-10-05_stul_ulozeni_testy/test_stul_ulozeni.py",
    "2026-10-05_system35/test_prejimka_system35.py",
    "2026-10-05_system35/test_shop_system35.py",
    "2026-10-05_vychozi_konfigurace/test_vychozi.py",
    "2026-10-06_nabidka_tlacitko_testy/test_nabidka_backend_kontrakt.py",
    "2026-10-06_nabidka_z_konfigurace_testy/test_nabidka_z_konfigurace.py",
    "2026-10-07_jazyky_testy/test_jazyky.py",
    "2026-10-07_konfigurator_registr_testy/test_registr.py",
    "2026-10-07_miniweb_jazyky_testy/test_podminky_jazyka.py",
    "2026-10-07_led600_generator/test_led_delka.py",
    "2026-10-07_led600_generator/test_led_delka_zive.py",
    "2026-10-07_led600_generator/test_led_delka_shop.py",
    "2026-10-07_led600_generator/test_led_delka_lux.py",
    "2026-10-07_led600_generator/test_regrese_bez_led.py",
    "2026-10-07_police_bez_desky/test_police_bez_desky.py",
    "2026-10-07_police_bez_desky/test_police_bez_desky_shop.py",
    "2026-10-07_police_bez_desky/test_police_bez_desky_zlato.py",
    "2026-10-07_police_stojky/test_hpolice.py",
    "2026-10-07_police_stojky/test_hpolice_shop.py",
    "2026-10-07_police_stojky/test_hpolice_sikma.py",
    "2026-10-07_stul_karta/test_karta_cli.py",
    "2026-10-07_stul_karta/test_karta_db.py",
    "2026-10-07_stul_karta/test_karta_route.py",
    "2026-10-07_system45/test_s45_jadro.py",
    "2026-10-07_system45/test_s45_pravidla.py",
    "2026-10-07_system45/test_s45_regrese.py",
    "2026-10-07_system45/test_s45_shop.py",
    "2026-10-07_system45/test_s45_zive.py",
    "2026-10-08_patky_kuzel/test_patky_kuzel.py",
    "2026-10-08_vychozi_pohled/test_pohled_api.py",
    "2026-10-08_led_rucne/test_led_rucne.py",
    "2026-10-08_led_rucne/test_led_rucne_shop.py",
]


def spust(arg):
    n, koren, slozka, t = arg
    cmd = ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=/opt/konfigurator/api/.env", "--setenv=HOME=/root", "--setenv=PYTHONDONTWRITEBYTECODE=1",
           f"--working-directory={koren}", PY, os.path.join(koren, "scripts", t)]
    with open(os.path.join(slozka, f"{n:02d}.log"), "w", encoding="utf-8") as f:
        f.write("== " + t + "\n")
        f.flush()
        try:
            rc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=2400).returncode
        except subprocess.TimeoutExpired:
            rc = 124
    return n, t, rc


if __name__ == "__main__":
    koren, slozka = sys.argv[1], sys.argv[2]
    j = int(sys.argv[sys.argv.index("-j") + 1]) if "-j" in sys.argv else 4
    jen = sys.argv[sys.argv.index("--jen") + 1].split(",") if "--jen" in sys.argv else None
    os.makedirs(slozka, exist_ok=True)
    seznam = [(i, koren, slozka, t) for i, t in enumerate(TESTY, 1) if jen is None or any(x in t for x in jen)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=j) as ex:
        for n, t, rc in ex.map(spust, seznam):
            print(f"{n:2d} rc={rc} {t}", flush=True)
