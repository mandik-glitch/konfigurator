#!/usr/bin/env python3
"""2026-09-09_turntable_status.py - prehled renderovaci fronty a workera
(bot8, Robert 2026-09-09: "agenta si musis spoustet a kontrolovat sam
program protoze to muze spadnout a ja u toho nebudu sedet porad").

Cte JEN soubory v RENDER_OUT_DIR - zadna DB, zadny Flask, zadny token.
Da se pustit kdykoli i z cronu.

    api/venv/bin/python3 scripts/2026-09-09_turntable_status.py
    api/venv/bin/python3 scripts/2026-09-09_turntable_status.py --watch
"""
import argparse
import json
import os
import re
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "private-files", "blender-renders")
HEARTBEAT = os.path.join(OUT, ".worker_heartbeat.json")
AGENT_SOURCE = os.path.join(REPO, "scripts", "render_worker_agent.py")
ONLINE_S = 90          # stejna hranice jako api/render_worker.py
POLL_STALE_S = 180     # = WORKER_POLL_STALE_S tamtez
EXPECTED_IP_KEY = "RENDER_WORKER_EXPECTED_IP"


def _server_nabizi_verzi():
    """Ctena PRIMO ze zdrojoveho souboru (stejny regex jako api/
    render_worker.py::_agent_meta(), zamerne bez importu Flasku - viz
    modulovy docstring "zadny Flask") - tohle je verze, kterou by si
    stanice vzala pri pristim /agent-version pollu, NE nutne verze,
    ktera na ni ted skutecne bezi."""
    try:
        with open(AGENT_SOURCE, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return None
    m = re.search(r'AGENT_VERSION\s*=\s*"([^"\n]{1,40})"', raw)
    return m.group(1) if m else None


def _expected_ip():
    """Ocekavana IP z api/.env - cte se jen tenhle jeden klic, zadna
    tajemstvi se nikam nevypisuji."""
    try:
        with open(os.path.join(REPO, "api", ".env"), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith(EXPECTED_IP_KEY + "="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def _vsechny_stavy():
    out = []
    try:
        names = sorted(os.listdir(OUT))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".status.json"):
            continue
        try:
            with open(os.path.join(OUT, name), encoding="utf-8") as fh:
                out.append((name[: -len(".status.json")], json.load(fh)))
        except (OSError, ValueError):
            continue
    return out


def _bezi_neco_na_workeru():
    """Behem renderu se agent na praci neptá - to NENI zaseknuti."""
    return any(st.get("state") == "running" and st.get("on_worker")
               for _job, st in _vsechny_stavy())


def worker_line():
    try:
        with open(HEARTBEAT, encoding="utf-8") as fh:
            hb = json.load(fh)
    except (OSError, ValueError):
        return "WORKER: nikdy se neohlasil"
    age = time.time() - hb.get("ts", 0)
    online = age < ONLINE_S
    exp = _expected_ip()
    ip = hb.get("ip")
    if exp and ip:
        ip_note = " (ocekavana)" if ip == exp else " (JINA nez ocekavana %s)" % exp
    else:
        ip_note = ""
    # bot8 2026-09-09: tep NEDOKAZUJE, ze si agent bere praci - tluce ve
    # vlastnim vlakne. Vecer 2026-09-09 hlasil tenhle radek 1,5 hodiny
    # "ONLINE", zatimco agent si nevzal ani jednu ulohu. Rozhoduje proto
    # cas POSLEDNIHO POLLU (server ho zapisuje zvlast, viz
    # api/render_worker.py::_write_heartbeat).
    poll_ts = hb.get("poll_ts")
    # Agent, ktery jen tepe a na praci se nezeptal ANI JEDNOU, je stejne
    # zaseknuty - meri se od chvile, kdy zacal chodit holy tep.
    od = poll_ts or hb.get("poll_missing_since")
    poll_age = (time.time() - od) if od else None
    bezi_uloha = _bezi_neco_na_workeru()
    if not online:
        stav = "OFFLINE"
    elif poll_age is None:
        stav = "ONLINE(?)"          # zatim nemame co porovnat
    elif poll_age > POLL_STALE_S and not bezi_uloha:
        stav = "ZASEKNUTY"
    else:
        stav = "ONLINE"
    if poll_age is None:
        poll_note = "poll: zatim zadny"
    elif not poll_ts:
        poll_note = "poll: ANI JEDEN (tep chodi uz %.0f s)" % poll_age
    else:
        poll_note = "poll pred %.0f s%s" % (poll_age, " (bezi uloha)" if bezi_uloha else "")
    hlaska = ("WORKER: %s | %s | GPU %s | IP %s%s | tep pred %.0f s | %s"
              % (stav, hb.get("name", "?"), hb.get("gpu", "?"), ip or "?",
                 ip_note, age, poll_note))
    # Verze agenta (bot3 2026-09-11, po tretim neuspesnem pokusu o nasazeni
    # bez zpetne vazby: "musis ho obslozit pres nove verze sluzby... a
    # hlavne: hlasit, kdyz se lisi od verze na serveru"). Agent posilal
    # "version" v tepu uz od d48aaab2, ale /api/render-worker/heartbeat ho
    # do 2026-09-11 nikdy necetl z tela pozadavku (viz oprava v
    # api/render_worker.py) - proto tu do ted vzdy chybelo.
    verze_stanice = hb.get("version")
    verze_server = _server_nabizi_verzi()
    if verze_stanice:
        hlaska += " | verze %s" % verze_stanice
        if verze_server and verze_stanice != verze_server:
            hlaska += ("\n  POZOR: stanice bezi na verzi %s, server nabizi %s -"
                      " aktualizace se jeste nenasadila (kontrola je na"
                      " zacatku smycky, pred pollem - vezme si ji az po"
                      " dokonceni prave bezici ulohy)."
                      % (verze_stanice, verze_server))
    elif verze_server:
        hlaska += " | verze stanice neznama (starsi agent bez signalu verze)"
    # Teplota GPU (Robert 2026-09-11, bot16 postavil agent+server, bot9
    # dashboard) - hned vedle "ONLINE", protoze tohle je prvni misto, kam
    # se kazdy divá. Historie/prah zijou v heartbeat souboru (server je
    # tam zapsal, viz api/render_worker.py), tady se jen cte a zobrazuje -
    # chybejici klice (starsi agent, jeste zadny tep se senzory) tise
    # vynechaji celou vsuvku, ne "?" na kazdem miste.
    if hb.get("gpu_temp_c") is not None:
        prah = hb.get("gpu_teplota_prah_c")
        prekroceno = bool(hb.get("gpu_prah_prekrocen"))
        gpu_bit = " | GPU teplota %s°C" % hb["gpu_temp_c"]
        if hb.get("gpu_util_pct") is not None:
            gpu_bit += ", zatíž %s%%" % hb["gpu_util_pct"]
        if hb.get("gpu_clock_mhz") is not None:
            gpu_bit += ", takt %s MHz" % hb["gpu_clock_mhz"]
        if prah is not None:
            gpu_bit += ", práh %s°C" % prah
        if prekroceno:
            gpu_bit += " *** PREKROCENO ***"
        hlaska += gpu_bit
    if stav == "ZASEKNUTY":
        hlaska += ("\n  POZOR: agentovi tluce tep, ale uz si nebere praci."
                   "\n  Server ceka jen do 10 min, pak ulohu prevezme sam na CPU.")
    return hlaska


def jobs():
    out = []
    try:
        names = sorted(os.listdir(OUT))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".status.json"):
            continue
        job = name[: -len(".status.json")]
        try:
            with open(os.path.join(OUT, name), encoding="utf-8") as fh:
                st = json.load(fh)
        except (OSError, ValueError):
            continue
        if st.get("job_type") != "turntable" and not os.path.isdir(os.path.join(OUT, job + ".frames")):
            continue
        frames_dir = os.path.join(OUT, job + ".frames")
        done = 0
        if os.path.isdir(frames_dir):
            done = sum(1 for f in os.listdir(frames_dir) if f.endswith(".jpg"))
        out.append((job, st, done))
    return out


def render(once=False):
    print(worker_line())
    js = jobs()
    if not js:
        print("FRONTA: prazdna")
        return
    print("FRONTA: %d uloh" % len(js))
    for job, st, done in js:
        exp = (st.get("expected_frames") or 0) + (st.get("expected_stills") or 0)
        pct = (" %d/%d" % (done, exp)) if exp else (" %d snimku" % done if done else "")
        age = time.time() - (st.get("updated") or 0)
        print("  %s  %-14s %-42s%s  (pred %.0f s)"
              % (job[:8], st.get("state", "?"),
                 (st.get("assembly_name") or "")[:42], pct, age))
        if st.get("note"):
            print("      %s" % str(st["note"])[:160])
        if st.get("error"):
            print("      CHYBA: %s" % str(st["error"])[:160])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="obnovovat kazdych 10 s")
    a = ap.parse_args()
    if not a.watch:
        render()
        return
    try:
        while True:
            print("\033[2J\033[H", end="")
            print(time.strftime("%H:%M:%S"))
            render()
            time.sleep(10)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
