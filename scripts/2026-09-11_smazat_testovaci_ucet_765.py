#!/usr/bin/env python3
"""Smaze TESTOVACI UCET 765 (bot13-mobile-a-1787234384@test.local).

Robert 2026-09-11 (pres bot3): smazat. Ucet nasla QA kontrola
DB_TEST_ACCOUNT_IN_PROD jako testovaci ucet v produkcni DB (porusuje
WORKFLOW.md bod 1 / zakaz testovacich dat v produkci).

PROC PRAVE TENHLE A NE TEN DRUHY: QA hlasi dva ucty. 765 je CISTY pripad -
role `remeslnik`, **nula navazanych radku**, za celou dobu existence
neudelal nic. Druhy ucet `662` (bot8-test-scene@test.local, role admin) se
NEMAZE a tenhle skript na nej NESAHA: visi na nem 862 radku reálné prace
vcetne 120 akci v audit logu (zmeny cislovani dokladu, mazani konverzaci
podpory). Smazanim by se 861 radkum zahodilo autorstvi (FK jsou SET NULL) a
audit log by prisel o jedinou stopu, kdo ty zasahy udelal. O 662 Robert
zatim nerozhodl.

POZOR pro pripad, ze by se nekdy mazal i 662: `support_email_triage_runs.
requested_by` ma FK `NO ACTION`, takze prosty DELETE na 662 spadne na chybu
cizího klice. Neni to problem opravneni, jak to na prvni pohled vypada.

BEZPECNOSTNI POJISTKY (vsechny musi projit, jinak se NEMAZE nic):
  1. ucet musi existovat a mit PRESNE ocekavany e-mail i roli
  2. musi mit NULA navazanych radku (kontroluje se ZNOVU tesne pred
     mazanim - mezi pripravou skriptu a jeho spustenim mohl nekdo neco
     navazat)
  3. zaloha se zapise a OVERI (fsync + kontrola velikosti + zpetne nacteni)
     jako DOKONCENY krok PRED mazanim
  4. po zapisu se stav overi z NOVEHO spojeni

Bez `--provest` jen ukaze, co by udelal, a NIC nemaze. Zamerne opacne nez
starsi mazaci skripty (`--dry-run`): u nevratneho DELETE nad `app_users` ma
byt vychozi stav "nedelej nic".

Pouziti:
    api/venv/bin/python3 scripts/2026-09-11_smazat_testovaci_ucet_765.py
    api/venv/bin/python3 scripts/2026-09-11_smazat_testovaci_ucet_765.py --provest
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from _env import get_conn  # noqa: E402

UCET_ID = 765
OCEKAVANY_EMAIL = "bot13-mobile-a-1787234384@test.local"
OCEKAVANA_ROLE = "remeslnik"
NESAHAT = 662          # druhy testovaci ucet - o nem Robert nerozhodl
ZALOHA = "/opt/konfigurator/backups/2026-09-11_smazani_uctu_765.json"

PROVEST = "--provest" in sys.argv


def main():
    conn = get_conn(zapis_do_app_users=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, name, role, active, email_verified, created_at, party_id "
                        "FROM app_users WHERE id=%s", (UCET_ID,))
            ucet = cur.fetchone()
            if not ucet:
                sys.exit("KONCIM: ucet %s neexistuje - uz byl nekym smazan?" % UCET_ID)

            print("Ucet ke smazani:")
            for k, v in ucet.items():
                print("   %-15s %s" % (k, v))

            # --- POJISTKA 1: e-mail i role musi sedet ---
            if ucet["email"] != OCEKAVANY_EMAIL or ucet["role"] != OCEKAVANA_ROLE:
                sys.exit(
                    "KONCIM, NIC NEMAZU: ucet %s ma jiny e-mail/roli, nez se ceka.\n"
                    "  ceka se : %s / %s\n  je tam  : %s / %s\n"
                    "Na tomhle ID je nekdo jiny - overte rucne."
                    % (UCET_ID, OCEKAVANY_EMAIL, OCEKAVANA_ROLE, ucet["email"], ucet["role"]))

            # --- POJISTKA 2: nula navazanych radku, overeno ZNOVU ---
            cur.execute("""SELECT TABLE_NAME t, COLUMN_NAME c FROM information_schema.KEY_COLUMN_USAGE
                           WHERE REFERENCED_TABLE_SCHEMA=DATABASE()
                             AND REFERENCED_TABLE_NAME='app_users'""")
            vazby = []
            for v in cur.fetchall():
                cur.execute("SELECT COUNT(*) n FROM `%s` WHERE `%s`=%%s" % (v["t"], v["c"]), (UCET_ID,))
                n = cur.fetchone()["n"]
                if n:
                    vazby.append((v["t"], v["c"], n))
            if vazby:
                print("\nNAVAZANA DATA:")
                for t, c, n in vazby:
                    print("   %s.%s -> %d radku" % (t, c, n))
                sys.exit(
                    "KONCIM, NIC NEMAZU: ucet uz neni prazdny (%d vazeb). Mazani bylo "
                    "schvaleno prave proto, ze nic navazaneho nemel - to uz neplati."
                    % len(vazby))
            print("\nNavazanych radku: 0 (overeno znovu ted)")

            if not PROVEST:
                print("\n[NAHLED] Nic se nesmazalo. Spust s --provest.")
                return

            # --- POJISTKA 3: zaloha jako DOKONCENY krok PRED mazanim ---
            with open(ZALOHA, "w", encoding="utf-8") as fh:
                json.dump({"kdy": "2026-09-11", "co": "ucet pred smazanim (Robertovo rozhodnuti)",
                           "poznamka": "password_hash zamerne nezalohovan - backups/ je v gitu",
                           "ucet": ucet}, fh, ensure_ascii=False, indent=1, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            velikost = os.path.getsize(ZALOHA)
            zpet = json.load(open(ZALOHA, encoding="utf-8"))
            if velikost < 100 or zpet["ucet"]["id"] != UCET_ID:
                sys.exit("KONCIM, NIC NEMAZU: zaloha %s nevypada uplne (%d B)." % (ZALOHA, velikost))
            print("Zaloha: %s (%d B, zpetne nactena a overena)" % (ZALOHA, velikost))

            # --- SAMOTNE MAZANI (jedno ID, nikdy ne 662) ---
            cur.execute("DELETE FROM app_users WHERE id=%s AND id<>%s", (UCET_ID, NESAHAT))
            print("Smazano radku: %d" % cur.rowcount)
        conn.commit()
    finally:
        conn.close()

    # --- POJISTKA 4: kontrola z NOVEHO spojeni ---
    conn2 = get_conn(zapis_do_app_users=True)
    try:
        with conn2.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM app_users WHERE id=%s", (UCET_ID,))
            zbylo = cur.fetchone()["n"]
            cur.execute("SELECT id, email, role FROM app_users WHERE id=%s", (NESAHAT,))
            druhy = cur.fetchone()
        print("\nOVERENI z noveho spojeni:")
        print("   ucet %s existuje: %s (ocekavano 0)" % (UCET_ID, zbylo))
        print("   ucet %s netknut : %s" % (NESAHAT, druhy))
        if zbylo:
            sys.exit("POZOR: ucet %s tam porad je!" % UCET_ID)
        if not druhy:
            sys.exit("POZOR: ucet %s zmizel - to se stat nemelo!" % NESAHAT)
        print("\nHOTOVO.")
    finally:
        conn2.close()


if __name__ == "__main__":
    main()
