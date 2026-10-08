#!/usr/bin/env python3
"""Porovná lokální DB `konfigurator` proti živé Forpsi DB - bot14, 2026-09-06.

PROČ: probíhá příprava přesunu produkční DB konfigurátoru z Forpsi
DBaaS (80.211.73.226, `DB_*` v `api/.env`) na lokální MySQL na tomhle
VPS (`konfigurator_app`@`127.0.0.1`/DB `konfigurator`). Dokud neproběhne
finální cutover (přepnutí `DB_HOST` v `api/.env` + restart
`konfigurator.service`), appka pořád píše na Forpsi - lokální kopie
(dump z 2026-09-06) se tedy může kdykoli rozejít. Tenhle skript je
ověřovací krok PŘED cutoverem (spustit těsně předtím, delta musí být 0)
i PO cutoveru (kontrola, že nikde nezůstal zapomenutý zápis na starou
Forpsi DB).

Vzor převzat z `/opt/remeslo/scripts/compare_forpsi_delta.py` (bot20,
2026-09-03, stejný typ přesunu na sesterském projektu).

POUŽITÍ (potřebuje credentials Forpsi z `api/.env` + lokální credentials
z `/root/konfigurator_local_db.env`, oboje mimo git):

    systemd-run --pipe --wait --quiet \\
      --property=EnvironmentFile=/opt/konfigurator/api/.env \\
      --property=EnvironmentFile=/root/konfigurator_local_db.env \\
      --working-directory=/opt/konfigurator \\
      /opt/konfigurator/api/venv/bin/python3 scripts/compare_forpsi_delta.py

Exit 0 = žádná delta (bezpečné pokračovat k cutoveru / potvrzuje cutover
proběhl čistě), exit 1 = delta nalezena (NEPOKRAČOVAT, nejdřív
dosynchronizovat).

Je VÝHRADNĚ ke čtení - nikdy nikam nezapisuje, ani do jedné DB. Až
Forpsi zanikne (Robertovo plošné zrušení DBaaS), skript ztrácí smysl a
smaže se.
"""
import os
import sys

import pymysql


def connect(prefix):
    return pymysql.connect(
        host=os.environ[f"{prefix}_HOST"],
        port=int(os.environ[f"{prefix}_PORT"]),
        user=os.environ[f"{prefix}_USER"],
        password=os.environ[f"{prefix}_PASSWORD"],
        database=os.environ[f"{prefix}_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=15,
    )


def table_list(cur, schema):
    cur.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME",
        (schema,),
    )
    return [r["TABLE_NAME"] for r in cur.fetchall()]


def main():
    forpsi = connect("DB")
    local = connect("LOCAL_DB")
    fcur, lcur = forpsi.cursor(), local.cursor()

    f_tables = set(table_list(fcur, os.environ["DB_NAME"]))
    l_tables = set(table_list(lcur, os.environ["LOCAL_DB_NAME"]))

    problems = []
    only_forpsi = f_tables - l_tables
    only_local = l_tables - f_tables
    if only_forpsi:
        problems.append(f"Tabulky jen na Forpsi (chybi lokalne): {sorted(only_forpsi)}")
    if only_local:
        problems.append(f"Tabulky jen lokalne (navic): {sorted(only_local)}")

    common = sorted(f_tables & l_tables)
    print(f"Spolecnych tabulek: {len(common)} (Forpsi celkem {len(f_tables)}, lokal celkem {len(l_tables)})")

    row_mismatches = []
    checksum_mismatches = []
    for t in common:
        fcur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
        f_n = fcur.fetchone()["n"]
        lcur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
        l_n = lcur.fetchone()["n"]
        if f_n != l_n:
            row_mismatches.append((t, f_n, l_n))
            continue
        if f_n == 0:
            continue
        fcur.execute(f"CHECKSUM TABLE `{t}`")
        f_cs = fcur.fetchone()["Checksum"]
        lcur.execute(f"CHECKSUM TABLE `{t}`")
        l_cs = lcur.fetchone()["Checksum"]
        if f_cs != l_cs:
            checksum_mismatches.append((t, f_cs, l_cs))

    print(f"Radkovych neshod: {len(row_mismatches)}")
    for t, f_n, l_n in row_mismatches:
        print(f"  {t}: Forpsi={f_n} lokal={l_n} (delta={f_n - l_n:+d})")

    print(f"Checksum neshod (stejny pocet radku, jiny obsah): {len(checksum_mismatches)}")
    for t, f_cs, l_cs in checksum_mismatches:
        print(f"  {t}: Forpsi checksum={f_cs} lokal checksum={l_cs}")

    forpsi.close()
    local.close()

    ok = not problems and not row_mismatches and not checksum_mismatches
    if ok:
        print("VYSLEDEK: 0 rozdilu, lokalni kopie je bit-shodna s Forpsi.")
        sys.exit(0)
    else:
        print("VYSLEDEK: NALEZEN ROZDIL, viz vypis vyse.")
        for p in problems:
            print(p)
        sys.exit(1)


if __name__ == "__main__":
    main()
