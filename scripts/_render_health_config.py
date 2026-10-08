"""Sdilene prahy + heartbeat helpery pro "zdravi" renderovaci fronty -
pouziva jak teplotni brzda (2026-09-23_vandr_render_auto_dispatch.py)
tak hlidac zaseknuti (2026-09-25_render_stall_watchdog.py).

bot3 2026-09-25, po nalezu ze oba skripty si bez tohohle souboru
kolidovaly (brzda spravne necha frontu stat pri prehrate GPU, hlidac o
tom nevedel a vypaloval plany "fronta stoji" alarm): "at prahy zijou na
jednom miste, ne ve dvou souborech s vlastni kopii" - stejny duvod, proc
uz existuje _vandr_razitka_otisk.py pro sdileny vypocet otisku.
"""
import datetime
import json
import os

REPO = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep + "scripts", 1)[0]
WORKER_HEARTBEAT_PATH = os.path.join(REPO, "private-files", "blender-renders",
                                      ".worker_heartbeat.json")
HEARTBEAT_MAX_STARI_S = 900  # starsi = agent uz asi neposila, nedoveryhodne

# --- teplotni brzda (dispatch) ---
PRAH_GPU_TEPLOTA_C = 80.0  # RTX 3060: bezny provoz pod zatizi 60-80 C,
                           # vyrobcem hlasene throttling okolo 83-90 C -
                           # 80 C nechava rozumnou rezervu. Cislo neni od
                           # Roberta presne zadano (2026-09-25), lze upravit.
PRAH_GPU_PREHRATI_DLOUHO_MIN = 60  # GPU souvisle nad prahem dele nez tohle
                                   # uz neni "normalni kratke vydechnuti
                                   # mezi davkami", ale sam o sobe nalez
                                   # (chlazeni stanice) - bot3 2026-09-25.

# --- hlidac zaseknuti ---
PRAH_NIC_NEBEZI_MIN = 20  # dispatch timer bezi po 5 min, kratke mezery jsou normalni
PRAH_PREP_MIN = 25  # pred prvnim snimkem - prep faze umi 12-17+ min bez snimku (viz memory)
PRAH_ZASEK_MIN = 8  # po >=1 snimku - normalni tempo je ~30s/snimek
PRAH_GPU_IDLE_PCT = 15  # pod timhle % povazujeme GPU za necinne

# bot3 2026-09-25, po nalezu #4587/#4593 sedm hodin ve fronte (skutecna
# pricina: api/render_worker.py::render_worker_poll() bere prvni
# "waiting_worker" job podle sorted(os.listdir()) - tedy podle NAHODNEHO
# UUID jmena souboru, ne podle queued_at - takze uloha s "pozdnim" UUID
# muze byt hodiny predbihana novejsimi frontami s "drivejsim" UUID).
# Detekce nezavisi na tom, jestli je oprava (FIFO podle queued_at)
# nasazena - hlasi kdykoli NEJAKA uloha ceka nerozumne dlouho, bez ohledu
# na pricinu. 45 min je bezpecne nad delkou jedne plne davky (~23-30 min),
# takze normalni "ceka na aktualne bezici" nealarmuje.
PRAH_FRONTA_STARVACE_MIN = 45


def _heartbeat():
    """Cely obsah .worker_heartbeat.json, nebo None kdyz chybi/je stary/
    poskozeny (agent na Logiman2 spadl - radeji nevedet, nez tvrdit cokoli
    o teplote/zatizeni bez dukazu)."""
    try:
        hb = json.load(open(WORKER_HEARTBEAT_PATH))
    except (OSError, ValueError):
        return None
    stari_s = datetime.datetime.now().timestamp() - float(hb.get("ts", 0))
    if stari_s > HEARTBEAT_MAX_STARI_S:
        return None
    return hb


def gpu_teplota_c():
    hb = _heartbeat()
    if hb is None:
        return None
    try:
        return float(hb["gpu_temp_c"])
    except (KeyError, TypeError, ValueError):
        return None


def gpu_util_pct():
    hb = _heartbeat()
    if hb is None:
        return None
    try:
        return float(hb["gpu_util_pct"])
    except (KeyError, TypeError, ValueError):
        return None
