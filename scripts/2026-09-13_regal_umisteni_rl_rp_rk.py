#!/usr/bin/env python3
"""Rozdeli RB na RL/RP a prejmenuje puvodni RP (prepazka) na RK (kabina).

Robert 2026-09-13 v chatu, po otazce "jak urcis leva/prava": leva a prava
strana NEJSOU orientace jednoho kodu, jsou to DVA SAMOSTATNE kody
ciselniku - "regal levy RL, regal pravy RP, regal kabina RK - kabina je
v podstate za prepazkou, nemuzeme pouzit druhe P" (puvodni RP = prepazka
koliduje s novym RP = pravy, proto prepazka dostava RK a synonymum
"kabina").

Zmeny (poradi ZALEZI kvuli UNIQUE(kod)):
  1. id=1 RB/bocni_strana  -> RL/regal_levy   "Regál levý"
  2. id=2 RP/prepazka      -> RK/kabina       "Regál — kabina (za přepážkou)"
  3. NOVY radek            -> RP/regal_pravy  "Regál pravý"

Bezpecne: product_assemblies.umisteni_id je dnes NULL u vsech 293 sestav
(zadna sestava zadne umisteni nema prirazene), takze zadna zmena kodu
neprepisuje zadnou existujici vazbu.

Pouziti:
    python3 scripts/2026-09-13_regal_umisteni_rl_rp_rk.py            # dry-run
    python3 scripts/2026-09-13_regal_umisteni_rl_rp_rk.py --apply    # zapis
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

APPLY = "--apply" in sys.argv


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) n FROM product_assemblies WHERE umisteni_id IS NOT NULL")
    obsazeno = cur.fetchone()["n"]
    print(f"[sestav s vyplněným umisteni_id] {obsazeno} (očekáváno 0)")

    cur.execute("SELECT id, kod, klic FROM regal_umisteni WHERE klic='bocni_strana'")
    rb = cur.fetchone()
    cur.execute("SELECT id, kod, klic FROM regal_umisteni WHERE klic='prepazka'")
    rp_stary = cur.fetchone()
    cur.execute("SELECT id FROM regal_umisteni WHERE klic='regal_pravy'")
    rp_novy_existuje = cur.fetchone()

    if not rb and not rp_stary and rp_novy_existuje:
        print("Vypadá už hotovo (RL/RP/RK existují, RB/prepazka ne) - nic k udělání.")
        cur.close()
        conn.close()
        return

    if rb:
        print(f"  [{rb['kod']}/{rb['klic']}] -> RL/regal_levy \"Regál levý\"")
        if APPLY:
            cur.execute(
                "UPDATE regal_umisteni SET kod='RL', klic='regal_levy', nazev=%s, popis=%s WHERE id=%s",
                ("Regál levý",
                 "Regál podél levé boční stěny nákladového prostoru. Kombinace s EB "
                 "(euroboxy) je dnes rozpracovávaná - vzor Doblo C. Které z 341-347 "
                 "je RL a které RP, zatím neurčeno (čeká na rozhodnutí, jestli levá/"
                 "pravá geometricky liší, nebo je to čisté zrcadlení).",
                 rb["id"]),
            )
    else:
        print("  RB/bocni_strana už neexistuje, přeskočeno")

    if rp_stary:
        print(f"  [{rp_stary['kod']}/{rp_stary['klic']}] -> RK/kabina \"Regál — kabina (za přepážkou)\"")
        if APPLY:
            cur.execute(
                "UPDATE regal_umisteni SET kod='RK', klic='kabina', nazev=%s, popis=%s WHERE id=%s",
                ("Regál — kabina (za přepážkou)",
                 "Regál hned za přepážkou (oddělovací stěna kabina/náklad) - Robert "
                 "2026-09-13: \"kabina je v podstatě za přepážkou\". Nemá horní blok "
                 "jako boční regály - u některých vozidel místo toho spodní blok "
                 "(koncept zatím nerozpracován). Dřívější kód RP uvolněn pro "
                 "\"Regál pravý\".",
                 rp_stary["id"]),
            )
    else:
        print("  RP/prepazka už neexistuje, přeskočeno")

    if not rp_novy_existuje:
        print("  NOVÝ řádek -> RP/regal_pravy \"Regál pravý\", sort_order=11")
        if APPLY:
            cur.execute(
                "INSERT INTO regal_umisteni (kod, klic, nazev, popis, sort_order) VALUES (%s,%s,%s,%s,%s)",
                ("RP", "regal_pravy", "Regál pravý",
                 "Regál podél pravé boční stěny nákladového prostoru. Kombinace s EB "
                 "(euroboxy) je dnes rozpracovávaná - vzor Doblo C. Které z 341-347 "
                 "je RL a které RP, zatím neurčeno.",
                 11),
            )
    else:
        print("  RP/regal_pravy už existuje, přeskočeno")

    if APPLY:
        conn.commit()
        print("\nAPLIKOVÁNO.")
        cur.execute("SELECT kod, klic, nazev, sort_order FROM regal_umisteni ORDER BY sort_order")
        for r in cur.fetchall():
            print(" ", r)
    else:
        conn.rollback()
        print("\nDRY-RUN, nic nezapsáno. Spusť s --apply pro zápis.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
