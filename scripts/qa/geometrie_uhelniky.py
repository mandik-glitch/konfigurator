#!/usr/bin/env python3
"""QA suita: kolizni uhelniky JINDE nez dole v nohach (bot9, 2026-09-11).

Navazuje na sweep bot16 (2026-09-11, commit a217280f), ktery napric
katalogem nasel 44 uhelniku s prunikem > 1 mm do jineho dilu - 24 "dole
v nohach" (ty se podle Robertova pravidla mazou) a **20 "jinde", coz jsou
skutecne kolize k reseni**. Nikdo je do te doby nehlidal a vznikly
generatorem, takze je kazda dalsi sestava muze zdedit - proto kontrola.

PROC SAMOSTATNA SUITA A NE api/qa_checks.py:
Mereni potrebuje node + three.js + skutecne GLB soubory z webapp/katalog/.
`api/qa_checks.py` je knihovna cistych DB kontrol tvaru `fn(cur)`, ktere
bezi i pri kazdem otevreni admin Dashboardu - pridat do ni spousteni
externiho procesu by tam zavleklo uplne jinou tridu zavislosti. QA
framework ma na tohle zavedeny mechanismus suit (`scripts/qa/*.py`, denni
beh 04:30 pres run_all.sh, merge do qa-reports/latest.json, viditelne
v adminu) a existuje i precedens node suity (scripts/qa/e2e/run.cjs).
Suita je tedy spravny domov; rozhodnuto bot9, nahlaseno bot8.

HLASI SE JEN "JINDE", NE "DOLE" - a je to zamerne:
"dole" je podle pravidla ocekavany stav k uklidu (Robert to ma spustit),
takze by kontrola po uklidu hlasila nulu a po kazdem dalsim generovani
zase sum. "Jinde" je skutecny nalez. Pocet "dole" se proto vede jen ve
`stats`, aby bylo videt, jestli uklid probehl, ale nekricelo to.

⚠ HRANICE "DOLE" STOJI NA ROBERTOVE ZADANI, NE NA FYZICE. Zmerenо bot16
a nezavisle overeno bot9 (2026-09-11) - prekryv po osach u vsech 44 kusu:
    dole  (24x)   X: 29..29 mm   Z: 28..28 mm   Y:  5..18 mm
    jinde (20x)   X: 29..29 mm   Z: 28..28 mm   Y: 20..22 mm
X i Z jsou v OBOU skupinach tataz konstanta (plny prurez profilu), lisi se
POUZE Y. Mechanicky je to tedy tataz vada, jen jednou nad profilem a jednou
pod nim - a kusy, ktere se NEmazou, pronikaji dokonce HLOUBEJI (20-22 mm
proti 5-18 mm). Dusledek pro cteni teto kontroly:
  - "0 nalezu" NEznamena, ze uhelniky nekoliduji; znamena, ze vsechny
    kolize lezi tam, kde je pravidlo toleruje.
  - Kdyby Robert pravidlo rozsiril na vsechny kolize, tahle suita zacne
    hlasit 0 a bude to spravne - uklid je pak provede jinde. Nehledat
    v tom chybu kontroly.

MERENI SI NEVYMYSLI - pouziva primo bot16 sweep skript (bot8: "vezmi si
odtud zpusob mereni, nevymyslej vlastni"). Kdyz ten skript zmizi (napr.
uklidem do scripts/archiv_tmp/), suita to HLASI jako kriticky nalez misto
aby tise reportovala nulu - stejny princip jako u ukazatele na sablonu
renderu: tiche "0 nalezu" z nefunkcni kontroly je horsi nez chyba.

POZOR NA PAST (bot16): starsi scripts/2026-09-05_filter_uhelniky_
collisions.cjs zamerne PRESKAKUJE profily vlastni nohy, protoze na ne
uhelnik flush dosedá. Jenze kolize, o kterou tu jde, je PRAVE s nimi -
jen ne dosedem, ale prunikem. Sweep bot16 proto vlastni nohu
nepreskakuje; tahle suita ten skript pouziva tak, jak je.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import finding, get_conn, run_suite  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SWEEP = os.path.join(REPO_ROOT, "scripts", "2026-09-11_sweep_kolizni_uhelniky.cjs")
# Prah shodny se sweepem - lezi v prazdnem pasmu mezi 0,00 mm (uhelniky,
# ktere jen dosedaji - to je jejich ucel) a 5,00 mm (nejmensi skutecna
# kolize), takze se nehada.
EPS_MM = 1.0


def _spust_sweep(rows):
    """Vrati seznam nalezu ze sweepu, nebo vyhodi RuntimeError."""
    if not os.path.exists(SWEEP):
        raise RuntimeError(
            "měřicí skript %s neexistuje - kontrola NEMŮŽE proběhnout. "
            "Nehlásím 0 nálezů, protože by to vypadalo jako čisto." % SWEEP)
    with tempfile.TemporaryDirectory() as tmp:
        vstup = os.path.join(tmp, "sestavy.json")
        vystup = os.path.join(tmp, "sweep.json")
        with open(vstup, "w", encoding="utf-8") as f:
            json.dump(rows, f, default=str)
        proc = subprocess.run(
            ["node", SWEEP, vstup, vystup],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
        if proc.returncode != 0 or not os.path.exists(vystup):
            raise RuntimeError("sweep selhal (exit %s): %s"
                               % (proc.returncode, (proc.stdout or "")[-500:]))
        with open(vystup, encoding="utf-8") as f:
            return json.load(f)


def collect():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, data FROM product_assemblies")
            rows = [{"id": r["id"], "name": r["name"], "data": r["data"]}
                    for r in cur.fetchall()]
    finally:
        conn.close()

    try:
        nalezy = _spust_sweep(rows)
    except Exception as e:  # noqa: BLE001 - chceme hlasit hlasite, ne spadnout
        return [finding("critical", "UHELNIKY_MERENI_SELHALO",
                        "Měření kolizí úhelníků neproběhlo",
                        str(e),
                        where=SWEEP,
                        fix_hint="Bez měřicího skriptu kontrola nic nezjistí. "
                                 "Obnov ho z gitu (commit a217280f) nebo suitu "
                                 "přepoj na jeho nástupce.")], {}

    jinde = [x for x in nalezy if not x.get("dole")]
    dole = [x for x in nalezy if x.get("dole")]

    findings = []
    for x in jinde:
        findings.append(finding(
            "warning", "UHELNIK_KOLIZE_JINDE",
            "Úhelník proniká do jiného dílu mimo spodek nohy",
            "sestava #%s „%s\": %s na Y=%s (hranice „dole\" je Y=%s) proniká "
            "%s mm do „%s\". Pozice %s. Průnik nad %s mm není dosed, ale kolize - "
            "úhelník, který jen dosedá, má průnik 0,00 mm."
            % (x["asm"], x.get("name", ""), x.get("role"), x.get("Y"),
               x.get("hraniceDole"), x.get("pruh"), x.get("partnerRole"),
               x.get("poz"), EPS_MM),
            where="product_assemblies:%s" % x["asm"],
            fix_hint="NEMAZAT jako ty dole v nohách - tohle je kolize k řešení "
                     "(posunout/odebrat úhelník, nebo opravit generátor, který "
                     "ho tam dal). Viz AGENTS_LOG.md commit a217280f."))

    stats = {
        "sestav_celkem": len(rows),
        "uhelniku_s_prunikem_celkem": len(nalezy),
        "z_toho_jinde_hlaseno": len(jinde),
        "z_toho_dole_neni_nalez": len(dole),
        "dotcenych_sestav_jinde": len({x["asm"] for x in jinde}),
        "prah_mm": EPS_MM,
    }
    return findings, stats


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    run_suite("geometrie_uhelniky", collect, args.json)


if __name__ == "__main__":
    main()
