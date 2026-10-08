#!/usr/bin/env python3
"""Odstavi testovaci ADMIN ucet 662 - NEMAZE ho, jen mu sebere prava.

Robert 2026-09-11 (pres bot3), doslova: "udelej co je treba bot nemuze mit
admin ucet."

PROC SE NEMAZE: na uctu visi 862 radku realne prace (396 souboru na
Sdilenem disku, 304 vlastnich tvaru, 21 slozek, 20 kategorii) a 120 akci
v audit logu. Vsechny FK jsou SET NULL, takze smazanim by data zustala, ale
861 radkum by zmizelo AUTORSTVI - vcetne audit logu, ktery je jedinou
stopou, co se pod tim uctem delo. Bezpecnostni problem resi odebrani prav,
ne smazani; ztrata historie by byla nevratna.

CO SE MENI:
  role   admin -> user   `user` NENI v PERMISSION_ROLES, takze ucet ztraci
                         pristup ke scene i k celemu adminu (nejen admin
                         prava - zadna zamestnanecka prava)
  active 1 -> 0          nelze se prihlasit
  email  -> @odstaveno.invalid   `.invalid` je vyhrazena TLD, ktera nikdy
                         nemuze byt funkcni adresa (RFC 2606)
  name   -> [ODSTAVENO] ...      at je za rok poznat, co to bylo

CO SE NEMENI: id (drzi vazby), created_at, a VSECHNA navazana data.

POJISTKY (vsechny musi projit, jinak se NEMENI nic):
  1. ucet musi existovat a mit PRESNE ocekavany e-mail i roli admin
  2. novy e-mail nesmi kolidovat (sloupec je UNIQUE)
  3. zaloha jako DOKONCENY krok PRED zapisem (fsync + kontrola + zpetne
     nacteni)
  4. po zapisu kontrola z NOVEHO spojeni vcetne toho, ze pocet navazanych
     radku se NEZMENIL (nic se nesmelo odpojit)

Bez `--provest` jen ukaze, co by udelal.

Pouziti:
    api/venv/bin/python3 scripts/2026-09-11_odstavit_ucet_662.py
    api/venv/bin/python3 scripts/2026-09-11_odstavit_ucet_662.py --provest
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

UCET_ID = 662
OCEKAVANY_EMAIL = "bot8-test-scene@test.local"
OCEKAVANA_ROLE = "admin"
NOVY_EMAIL = "bot8-test-scene@odstaveno.invalid"
NOVE_JMENO = "[ODSTAVENO 2026-09-11] bot8 scene test - jen historie, neprihlasovat"
NOVA_ROLE = "user"
ZALOHA = "/opt/konfigurator/backups/2026-09-11_odstaveni_uctu_662.json"

PROVEST = "--provest" in sys.argv


def _vazby(cur, uid):
    cur.execute("""SELECT TABLE_NAME t, COLUMN_NAME c FROM information_schema.KEY_COLUMN_USAGE
                   WHERE REFERENCED_TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME='app_users'""")
    out = {}
    for v in cur.fetchall():
        cur.execute("SELECT COUNT(*) n FROM `%s` WHERE `%s`=%%s" % (v["t"], v["c"]), (uid,))
        n = cur.fetchone()["n"]
        if n:
            out["%s.%s" % (v["t"], v["c"])] = n
    return out


def main():
    conn = get_conn(zapis_do_app_users=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, name, role, active, created_at FROM app_users WHERE id=%s",
                        (UCET_ID,))
            ucet = cur.fetchone()
            if not ucet:
                sys.exit("KONCIM: ucet %s neexistuje." % UCET_ID)

            # --- POJISTKA 1 ---
            if ucet["email"] != OCEKAVANY_EMAIL or ucet["role"] != OCEKAVANA_ROLE:
                sys.exit("KONCIM, NIC NEMENIM: ucet %s ma jiny e-mail/roli, nez se ceka.\n"
                         "  ceka se: %s / %s\n  je tam : %s / %s"
                         % (UCET_ID, OCEKAVANY_EMAIL, OCEKAVANA_ROLE, ucet["email"], ucet["role"]))

            vazby_pred = _vazby(cur, UCET_ID)
            print("Ucet:", ucet["email"], "| role:", ucet["role"], "| aktivni:", ucet["active"])
            print("Navazana data (zustavaji beze zmeny):")
            for k, n in sorted(vazby_pred.items()):
                print("   %-45s %d" % (k, n))
            print("\nZmeny:")
            print("   role   %s -> %s" % (ucet["role"], NOVA_ROLE))
            print("   active %s -> 0" % ucet["active"])
            print("   email  %s -> %s" % (ucet["email"], NOVY_EMAIL))
            print("   name   %s -> %s" % (ucet["name"], NOVE_JMENO))

            # --- POJISTKA 2 ---
            cur.execute("SELECT id FROM app_users WHERE email=%s AND id<>%s", (NOVY_EMAIL, UCET_ID))
            if cur.fetchone():
                sys.exit("KONCIM, NIC NEMENIM: e-mail %s uz nekdo ma." % NOVY_EMAIL)

            if not PROVEST:
                print("\n[NAHLED] Nic se nezmenilo. Spust s --provest.")
                return

            # --- POJISTKA 3: zaloha jako dokonceny krok ---
            with open(ZALOHA, "w", encoding="utf-8") as fh:
                json.dump({"kdy": "2026-09-11", "co": "ucet 662 PRED odstavenim",
                           "poznamka": "password_hash zamerne nezalohovan (backups/ je v gitu)",
                           "ucet": ucet, "navazana_data": vazby_pred}, fh,
                          ensure_ascii=False, indent=1, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            vel = os.path.getsize(ZALOHA)
            if vel < 100 or json.load(open(ZALOHA, encoding="utf-8"))["ucet"]["id"] != UCET_ID:
                sys.exit("KONCIM, NIC NEMENIM: zaloha nevypada uplne (%d B)." % vel)
            print("\nZaloha: %s (%d B, zpetne overena)" % (ZALOHA, vel))

            cur.execute("UPDATE app_users SET role=%s, active=0, email=%s, name=%s "
                        "WHERE id=%s AND email=%s AND role=%s",
                        (NOVA_ROLE, NOVY_EMAIL, NOVE_JMENO, UCET_ID, OCEKAVANY_EMAIL, OCEKAVANA_ROLE))
            print("Zmeneno radku: %d" % cur.rowcount)
        conn.commit()
    finally:
        conn.close()

    # --- POJISTKA 4: kontrola z NOVEHO spojeni ---
    conn2 = get_conn(zapis_do_app_users=True)
    try:
        with conn2.cursor() as cur:
            cur.execute("SELECT id, email, name, role, active FROM app_users WHERE id=%s", (UCET_ID,))
            po = cur.fetchone()
            vazby_po = _vazby(cur, UCET_ID)
            cur.execute("SELECT COUNT(*) n FROM app_users WHERE role='admin' AND active=1")
            adminu = cur.fetchone()["n"]
        print("\nOVERENI z noveho spojeni:")
        print("   ", po)
        print("   navazanych radku po zmene:", sum(vazby_po.values()), "(pred:", sum(vazby_pred.values()), ")")
        print("   aktivnich admin uctu v systemu:", adminu)
        if po["role"] != NOVA_ROLE or po["active"] != 0:
            sys.exit("POZOR: zmena se neprojevila!")
        if sum(vazby_po.values()) != sum(vazby_pred.values()):
            sys.exit("POZOR: zmenil se pocet navazanych radku - neco se odpojilo!")
        print("\nHOTOVO. Historie zachovana, ucet bez prav a neaktivni.")
    finally:
        conn2.close()


if __name__ == "__main__":
    main()
