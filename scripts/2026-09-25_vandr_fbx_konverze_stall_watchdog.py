#!/usr/bin/env python3
"""Hlidac neresenych FBX->GLB konverznich hlaseni ve Vandr pipeline (bot3 ->
bot10, 2026-09-25, navazuje na opravu karet #4487/#4574: "udelej ten typ
selhani viditelnym... Zajisti, at se zaparkovana karta ozve (predavka,
AGENTS_LOG, cokoli, co si nekdo precte), nebo aspon at jde jednoduse zjistit,
kolik karet je v tomhle stavu"). Vzor (bot3: "mrkni na nej jako na vzor, at to
delas stejnym zpusobem a ne tretim"): scripts/2026-09-25_render_stall_watchdog.py
- stejne _zapsat_agents_log/_zapsat_handover, stejny "jen detekce a hlaseni,
nic neopravuje" postoj.

`nahlas_chybu()` v 2026-09-23_vandr_fbx_konverze_auto_dispatch.py UZ PRI KAZDEM
selhani zapisuje radek do bot_ukoly (bot_id='bot4', hotovo=0) - mechanismus na
zjisteni "kolik karet je zasekle" tedy uz existuje, jen ho nikdo aktivne
nesleduje (presne takhle zustaly karty #4487/#4574/#4586 nepovsimnute od
2026-09-24 vecer do dalsiho dne - bot3 se k nim dostal jen rucnim ctenim
zurnalu, ne z nejakeho alarmu). Tenhle skript nic noveho do pipeline
nezavadi, jen ty uz existujici nevyrizene radky periodicky prevadi na alarm
ve dvou kanalech, ktere boti uz sleduji (AGENTS_LOG.md, `handover.py list`),
aby "bot_ukoly ma 0 novych radku od posledni kontroly" prestalo byt jediny
zpusob, jak se o zaseknuti dozvedet.

Alarmuje jen pri ZMENE mnoziny nevyrizenych id (pribyla nova karta, nebo
naopak nejaka zmizela = niekdo ji vyresil/oznacil hotovo). Bez tohohle
rozliseni by kazdych 15 minut napsalo do AGENTS_LOG.md znovu stejny alarm
pro karty, o kterych uz vsichni vedi a cekaji na rozhodnuti (typicky #4586 -
zamerna rucni-review brzda kvuli neoverenemu 30x30 profilu, ne bug, viz
AGENTS_LOG.md 2026-09-25 bot10 - tenhle watchdog ji proto bude hlasit JEDNOU,
ne opakovane, dokud se bot_ukoly radek nezmeni).

Kazda karta muze v bot_ukoly skoncit ze DVOU ruznych duvodu - selhani
konverze (bug, ma se opravit) i zamerna bezpecnostni brzda overit_final_glb
(cekani na rozhodnuti) pisou text se stejnym prefixem "Vandr FBX->GLB
konverze:" - watchdog to zamerne NEROZLISUJE (neni to jeho ukol rozhodnout,
ktere z toho je ktere), jen hlasi obsah radku beze zmeny, cti je clovek/bot,
ktery se rozhodne.

Spousti se jako systemd timer (deploy/konfigurator-vandr-fbx-konverze-
stall-watchdog.{service,timer}), NE navazane na zadnou bot session.
"""
import datetime
import json
import os
import subprocess
import sys

REPO_ROOT = "/opt/konfigurator"
STATE_DIR = os.path.join(REPO_ROOT, "private-files", "vandr-fbx-konverze")
STATE_PATH = os.path.join(STATE_DIR, ".stall_watchdog_state.json")
BOT_UKOLY_PREFIX = "Vandr FBX->GLB konverze:"


def _pripoj_db():
    import pymysql
    env = {}
    for line in open(os.path.join(REPO_ROOT, "api", ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                            password=env["DB_PASSWORD"], database=env["DB_NAME"],
                            cursorclass=pymysql.cursors.DictCursor)


def _nevyrizene_ukoly(conn):
    """Radky bot_ukoly zapsane nahlas_chybu() (2026-09-23_vandr_fbx_konverze_
    auto_dispatch.py), ktere jeste nikdo neoznacil hotovo=1. Cte primo tabulku
    (ne pres import kandidatu funkce z dispatch skriptu jako render-stall-
    watchdog) - tady nechceme znovu pocitat sha256 vsech FBX a ptat se "co je
    PRAVE TED zasekle", ale "o cem uz vime a nikdo to nedoresil", coz uz
    presne rika bot_ukoly.hotovo samo o sobe."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, text, created_at FROM bot_ukoly "
            "WHERE bot_id='bot4' AND hotovo=0 AND text LIKE %s "
            "ORDER BY id", (BOT_UKOLY_PREFIX + "%",))
        return cur.fetchall()


def _nacti_stav():
    try:
        return json.load(open(STATE_PATH))
    except (OSError, ValueError):
        return {}


def _uloz_stav(stav):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stav, f, indent=2)
    os.replace(tmp, STATE_PATH)


def _zapsat_agents_log(zprava):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (f"\n## vandr-fbx-konverze-stall-watchdog (automaticky, "
             f"scripts/2026-09-25_vandr_fbx_konverze_stall_watchdog.py) — {ts}\n\n{zprava}\n")
    try:
        with open(os.path.join(REPO_ROOT, "AGENTS_LOG.md"), "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError as e:
        print(f"[fbx-konverze-stall-watchdog] zapis do AGENTS_LOG.md selhal: {e}", file=sys.stderr)


def _zapsat_handover(topic, body):
    try:
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "scripts", "handover.py"), "add",
             "--bot", "bot10", "--project", "konfigurator", "--topic", topic,
             "--status", "open", "--body", body],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        print(f"[fbx-konverze-stall-watchdog] handover.py add selhal: {e}", file=sys.stderr)


def main():
    conn = _pripoj_db()
    try:
        radky = _nevyrizene_ukoly(conn)
    finally:
        conn.close()

    aktualni_id = sorted(r["id"] for r in radky)
    stav = _nacti_stav()
    posledni_id = stav.get("posledni_alarmovane_id") or []

    if aktualni_id != posledni_id:
        if aktualni_id:
            radky_txt = "\n".join(
                "- bot_ukoly #%d (%s): %s" % (
                    r["id"], r["created_at"].strftime("%Y-%m-%d %H:%M"),
                    r["text"].splitlines()[0])
                for r in radky)
            zprava = (
                "%d nevyrizen(a/ych) FBX->GLB konverzni(ch) hlaseni v bot_ukoly "
                "(bot_id='bot4', hotovo=0), zmena oproti minule kontrole "
                "(drive nahlaseno: %s):\n%s\n\n"
                "Cely text kazdeho hlaseni je v bot_ukoly.text (tady jen prvni "
                "radek). Muze jit o skutecnou chybu KE OPRAVE, nebo o zamernou "
                "rucni-review brzdu CEKAJICI NA ROZHODNUTI (watchdog to "
                "nerozlisuje) - oznac hotovo=1, az bude doreseno, jinak to "
                "bude watchdog pripominat pri kazde zmene mnoziny."
                % (len(aktualni_id), posledni_id or "zadne", radky_txt))
            print("ALARM: %s" % zprava)
            _zapsat_agents_log(zprava)
            _zapsat_handover("vandr fbx konverze: nevyrizena hlaseni", zprava)
        else:
            zprava = ("Vsechna drive hlasena FBX->GLB konverzni hlaseni (id %s) "
                      "jsou nyni oznacena hotovo=1 - fronta cista." % posledni_id)
            print("OK (zmena k lepsimu): %s" % zprava)
            _zapsat_agents_log(zprava)
        stav["posledni_alarmovane_id"] = aktualni_id
    else:
        print("OK: beze zmeny, %d nevyrizeno (%s)" % (
            len(aktualni_id), aktualni_id if aktualni_id else "-"))

    stav["posledni_kontrola"] = datetime.datetime.now().isoformat()
    _uloz_stav(stav)


if __name__ == "__main__":
    main()
