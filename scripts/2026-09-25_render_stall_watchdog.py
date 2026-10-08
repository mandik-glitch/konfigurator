#!/usr/bin/env python3
"""Hlidac zaseknuti renderovaci fronty pres noc (bot3 -> bot4, 2026-09-25,
"Robert chce, at renderujeme bez zastavek... to nesmi stat na tom, jestli
ma nekdo z nas otevrenou session").

POUZE DETEKCE A HLASENI. Nikdy nic nerestartuje ani nezabiji - Robert/bot3
2026-09-25 vyslovne: "automaticky restart renderu je presne to, co by nam
mohlo rozbit rozdelanou davku". Behem jednoho behu maximalne zapise alarm
do AGENTS_LOG.md + scripts/handover.py add.

Prahy (PRAH_*) i cteni GPU heartbeatu jsou SDILENE s teplotni brzdou
dispatch skriptu pres _render_health_config.py (bot3 2026-09-25: "at
prahy zijou na jednom miste, ne ve dvou souborech s vlastni kopii" -
puvodni verze mela vlastni kopii a kolidovala s brzdou, viz podminka A).

Tri nezavisle podminky (mezistav v .stall_watchdog_state.json vedle
ostatnich stavovych souboru rendereru - STEJNY adresar, ne DB, aby
watchdog nezavisel na nicem, co by taky mohlo selhat):

  A) "fronta ceka, nic nebezi, BEZ ZJEVNEHO DUVODU" - kandidati()
     (2026-09-23_vandr_render_auto_dispatch.py, ZNOVUPOUZITO) hlasi >=1
     kandidata, zadny .status.json nema state=="running", tohle trva uz
     > PRAH_NIC_NEBEZI_MIN, A ZAROVEN GPU NENI prehrata (< PRAH_GPU_
     TEPLOTA_C). Kdyz JE GPU prehrata, dispatch ji zamerne necha
     vychladnout (viz 2026-09-23_vandr_render_auto_dispatch.py) - to je
     ocekavany stav, jen se vypise info radek, ne alarm. Bez tyhle
     vyjimky by teplotni brzda a tenhle hlidac na sebe plane spoustely
     poplach (bot3 2026-09-25 nalez).

  B) "beh je zaseklý" - nejaky .status.json MA state=="running", ale jeho
     frames_dir (out_dir z <uuid>.json, format <uuid>.frames/) nedostal
     novy/zmeneny soubor uz dele, nez tiery nize DOVOLUJI, A ZAROVEN GPU
     (.worker_heartbeat.json, "Logiman2" - VZDALENA stanice, ne tenhle
     VPS) je po celou tu dobu necinne (< PRAH_GPU_IDLE_PCT). Bez GPU
     podminky by tohle plane spoustelo alarm behem legitimni prep faze:
       - PRAH_PREP_MIN (0 snimku zatim) - import GLB + stavba HDRI
         importance-sampling mapy + BVH/kernel kompilace muze trvat
         "mnoho minut" bez jedineho viditelneho snimku, PRI GENUINE
         BEZICI GPU praci (zdokumentovano 2026-09-12, viz memory
         render_pipeline_prep_phase_blind_spot: 2 realne joby s timhle
         vzorem trvaly 12-17 min a NEBYLY zasekle - Robert je tehdy
         omylem restartoval, cimz teprve OPRAVDU zpusobil ztratu prace).
       - PRAH_ZASEK_MIN (uz >=1 snimek hotovy) - jeden snimek ze ~54
         trva bezne ~25-30s, presne jak bot3 zadal: "Y musi byt pohodlne
         nad delkou jednoho snimku, ne nad delkou cele davky".
     GPU idle-kontrola pouziva jen VLASTNI prubezne nasbirane vzorky
     (.stall_watchdog_state.json) za dobu, co frame count stoji.

  C) "GPU je prehrata dlouho souvisle" - teplota >= PRAH_GPU_TEPLOTA_C
     nepretrzite dele nez PRAH_GPU_PREHRATI_DLOUHO_MIN (bot3 2026-09-25:
     "kdyby se GPU drzela nad prahem hodiny v kuse, to uz je samo o sobe
     nález"). NEZAVISLE na A/B - hlasi se, i kdyz zrovna neco bezi.

Namerene 2026-09-24/25 (zapsano sem, at se priste nemusi dolovat znovu):
render bezi VE VLASTNIM VLAKNE uvnitr Flask procesu (api/blender_render.
py:_run_render_job) - gunicornuv `--timeout 60` se na nej NEVZTAHUJE.
QUEUE_WAIT_TIMEOUT_S=600 je strop na cekani JEDNE uz prijate ulohy na
volny zamek, ne na celou noc davek - dispatch (5min timer) v kazdem kole
zkousi znovu, takze v praxi nikdy nefronti vic nez 1 uloha najednou.
RENDER_TIMEOUT_TURNTABLE_S=6*3600 (6h) je az posledni tvrdy strop - moc
pomaly na to, aby v rozumnem case chytil zaseknuti jedne davky, presne
proto tenhle skript existuje.

Spousti se jako systemd timer (deploy/konfigurator-render-stall-watchdog.
{service,timer}), NE navazane na zadnou bot session.
"""
import datetime
import glob
import json
import os
import subprocess
import sys

REPO_ROOT = "/opt/konfigurator"
BLENDER_RENDERS_DIR = os.path.join(REPO_ROOT, "private-files", "blender-renders")
STATE_PATH = os.path.join(BLENDER_RENDERS_DIR, ".stall_watchdog_state.json")

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import _render_health_config as rhc  # noqa: E402


def _nacti_kandidati_funkci():
    """scripts/2026-09-23_vandr_render_auto_dispatch.py ma v nazvu
    pomlky/cislice na zacatku - normalni `import` na to nestaci, proto
    importlib.util primo z cesty."""
    import importlib.util
    cesta = os.path.join(REPO_ROOT, "scripts", "2026-09-23_vandr_render_auto_dispatch.py")
    spec = importlib.util.spec_from_file_location("vandr_render_auto_dispatch", cesta)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul.kandidati


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


def _najdi_bezici_ulohu():
    """Vrati (job_id, frames_dir) prvni ulohy se state=='running', nebo
    (None, None) kdyz zadna nebezi. Necte cely soubor destruktivne -
    tise preskoci status.json, ktery se prave prepisuje (JSONDecodeError)."""
    for cesta in glob.glob(os.path.join(BLENDER_RENDERS_DIR, "*.status.json")):
        try:
            st = json.load(open(cesta))
        except (OSError, ValueError):
            continue
        if st.get("state") == "running":
            job_id = os.path.basename(cesta)[: -len(".status.json")]
            frames_dir = st.get("frames_dir") or os.path.join(BLENDER_RENDERS_DIR, job_id + ".frames")
            return job_id, frames_dir
    return None, None


def _najdi_stare_cekajici(ted_ts, prah_min):
    """Vsechny ulohy se state=='waiting_worker', ktere ceka(l)y dele nez
    prah_min - bot3 2026-09-25 nalez #4587/#4593: render_worker_poll()
    bere prvni podle sorted(os.listdir()), tedy podle NAHODNEHO UUID
    jmena souboru, ne podle queued_at - starsi uloha s "pozdnim" UUID
    muze byt hodiny predbihana novejsimi frontami. Vraci list (job_id,
    minut_cekani)."""
    stare = []
    for cesta in glob.glob(os.path.join(BLENDER_RENDERS_DIR, "*.status.json")):
        try:
            st = json.load(open(cesta))
        except (OSError, ValueError):
            continue
        if st.get("state") != "waiting_worker":
            continue
        queued_at = st.get("queued_at")
        if not queued_at:
            continue
        min_cekani = (ted_ts - float(queued_at)) / 60.0
        if min_cekani > prah_min:
            job_id = os.path.basename(cesta)[: -len(".status.json")]
            stare.append((job_id, min_cekani))
    return stare


def _frames_otisk(frames_dir):
    """(pocet souboru, nejnovejsi mtime) - staci na detekci "nic se
    nezmenilo", nemusime vedet PRESNY soubor."""
    if not frames_dir or not os.path.isdir(frames_dir):
        return 0, 0.0
    soubory = glob.glob(os.path.join(frames_dir, "**", "*"), recursive=True)
    soubory = [s for s in soubory if os.path.isfile(s)]
    if not soubory:
        return 0, 0.0
    return len(soubory), max(os.path.getmtime(s) for s in soubory)


def _nacti_stav():
    try:
        return json.load(open(STATE_PATH))
    except (OSError, ValueError):
        return {}


def _uloz_stav(stav):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stav, f, indent=2)
    os.replace(tmp, STATE_PATH)


def _zapsat_agents_log(zprava):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (f"\n## render-stall-watchdog (automaticky, "
             f"scripts/2026-09-25_render_stall_watchdog.py) — {ts}\n\n{zprava}\n")
    try:
        with open(os.path.join(REPO_ROOT, "AGENTS_LOG.md"), "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError as e:
        print(f"[render-stall-watchdog] zapis do AGENTS_LOG.md selhal: {e}", file=sys.stderr)


def _zapsat_handover(topic, body):
    try:
        subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "scripts", "handover.py"), "add",
             "--bot", "bot4", "--project", "konfigurator", "--topic", topic,
             "--status", "open", "--body", body],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        print(f"[render-stall-watchdog] handover.py add selhal: {e}", file=sys.stderr)


def _alarm(kod, zprava):
    print(f"ALARM [{kod}]: {zprava}")
    _zapsat_agents_log(zprava)
    _zapsat_handover(f"render stall watchdog: {kod}", zprava)


def main():
    os.makedirs(BLENDER_RENDERS_DIR, exist_ok=True)
    stav = _nacti_stav()
    ted = datetime.datetime.now()
    ted_ts = ted.timestamp()

    kandidati_fn = _nacti_kandidati_funkci()
    conn = _pripoj_db()
    try:
        with conn.cursor() as cur:
            kand, _, _ = kandidati_fn(cur)
    finally:
        conn.close()
    pocet_kandidatu = len(kand)

    job_id, frames_dir = _najdi_bezici_ulohu()
    teplota = rhc.gpu_teplota_c()
    gpu_prehrata = teplota is not None and teplota >= rhc.PRAH_GPU_TEPLOTA_C

    # --- podminka C: GPU prehrata dlouho souvisle (nezavisle na A/B) ---
    if gpu_prehrata:
        if not stav.get("gpu_prehrate_od"):
            stav["gpu_prehrate_od"] = ted_ts
        trva_prehrati_min = (ted_ts - stav["gpu_prehrate_od"]) / 60.0
        if trva_prehrati_min > rhc.PRAH_GPU_PREHRATI_DLOUHO_MIN and not stav.get("alarm_c_poslany"):
            _alarm("gpu-prehrata-dlouho",
                   f"GPU (Logiman2) je {round(trva_prehrati_min)} min souvisle nad "
                   f"prahem {rhc.PRAH_GPU_TEPLOTA_C:.0f} C (aktualne {teplota:.1f} C). "
                   f"Teplotni brzda dispatch skriptu proto uz dlouho nezahajuje dalsi "
                   f"davky - fronta muze stat cele hodiny. Zkontroluj chlazeni "
                   f"stanice Logiman2 fyzicky, tohle uz neni normalni kratke "
                   f"vydechnuti mezi davkami.")
            stav["alarm_c_poslany"] = True
    else:
        stav["gpu_prehrate_od"] = None
        stav["alarm_c_poslany"] = False

    # --- podminka A: fronta ceka, nic nebezi, BEZ ZJEVNEHO DUVODU ---
    if pocet_kandidatu > 0 and job_id is None:
        if not stav.get("nic_nebezi_od"):
            stav["nic_nebezi_od"] = ted_ts
        trva_min = (ted_ts - stav["nic_nebezi_od"]) / 60.0
        if gpu_prehrata:
            print(f"info: fronta stoji ({pocet_kandidatu} kandidatu, {round(trva_min)} min), "
                  f"ale GPU se chladi ({teplota:.1f} C >= {rhc.PRAH_GPU_TEPLOTA_C:.0f} C) - "
                  f"ocekavany stav teplotni brzdy, nealarmuji (viz podminka C pro "
                  f"dlouhodobe prehrati).")
        elif trva_min > rhc.PRAH_NIC_NEBEZI_MIN and not stav.get("alarm_a_poslany"):
            _alarm("fronta-stoji",
                   f"{pocet_kandidatu} kandidat(u) na render ceka, ale poslednich "
                   f"{round(trva_min)} min nic nebezi (prah {rhc.PRAH_NIC_NEBEZI_MIN} min) "
                   f"a GPU NENI prehrata (teplota {teplota if teplota is not None else '?'} C) "
                   f"- teplotni brzda tedy neni duvod. Dispatch (timer po 5 min) bud "
                   f"nedostal novy kandidat spravne, nebo se sam zastavil - zkontroluj "
                   f"`systemctl status konfigurator-vandr-render-dispatch.timer` a "
                   f"posledni radky `journalctl -u konfigurator-vandr-render-dispatch.service`.")
            stav["alarm_a_poslany"] = True
    else:
        stav["nic_nebezi_od"] = None
        stav["alarm_a_poslany"] = False

    # --- podminka B: beh je zasekly (frame count stoji I GPU je necinne) ---
    gpu_pct = rhc.gpu_util_pct()
    if job_id is not None:
        pocet, mtime = _frames_otisk(frames_dir)
        posledni_job = stav.get("posledni_job_id")
        if posledni_job != job_id or stav.get("posledni_pocet_snimku") != pocet:
            # novy job, nebo pribyl/zmenil se snimek - restart casovace i GPU vzorku
            stav["posledni_job_id"] = job_id
            stav["posledni_pocet_snimku"] = pocet
            stav["beze_zmeny_od"] = ted_ts
            stav["gpu_vzorky_behem_stoje"] = []
            stav["alarm_b_poslany"] = False
        else:
            trva_min = (ted_ts - stav.get("beze_zmeny_od", ted_ts)) / 60.0
            prah_min = rhc.PRAH_PREP_MIN if pocet == 0 else rhc.PRAH_ZASEK_MIN
            vzorky = stav.get("gpu_vzorky_behem_stoje") or []
            if gpu_pct is not None:
                vzorky.append(gpu_pct)
            stav["gpu_vzorky_behem_stoje"] = vzorky[-20:]
            gpu_vypada_necinne = bool(vzorky) and all(v < rhc.PRAH_GPU_IDLE_PCT for v in vzorky)
            if trva_min > prah_min and gpu_vypada_necinne and not stav.get("alarm_b_poslany"):
                _alarm("beh-zasekly",
                       f"Uloha {job_id} je porad 'running', {pocet} snimku hotovo, "
                       f"ve frames_dir ({frames_dir}) se {round(trva_min)} min nic "
                       f"nezmenilo (prah {prah_min} min - {'pred prvnim snimkem' if pocet == 0 else 'po prvnim snimku'}) "
                       f"A GPU (Logiman2) je po celou tu dobu necinne (vzorky "
                       f"gpu_util_pct: {[round(v) for v in vzorky]}, vsechny pod "
                       f"{rhc.PRAH_GPU_IDLE_PCT}%). Zkontroluj PID z <job>.status.json na "
                       f"stanici. NEZABIJENO automaticky.")
                stav["alarm_b_poslany"] = True
            elif trva_min > prah_min and not gpu_vypada_necinne:
                print(f"info: frame count stoji {round(trva_min)} min, ale GPU vypada "
                      f"aktivni (vzorky {[round(v) for v in vzorky]}) - povazuji za "
                      f"legitimni prep/pomaly snimek, nealarmuji.")
    else:
        stav["posledni_job_id"] = None
        stav["posledni_pocet_snimku"] = None
        stav["beze_zmeny_od"] = None
        stav["gpu_vzorky_behem_stoje"] = []
        stav["alarm_b_poslany"] = False

    # --- podminka D: konkretni uloha visi ve fronte dlouho (hladoveni) ---
    # bot3 2026-09-25, po nalezu #4587/#4593 (7 hodin ve waiting_worker,
    # pricina: render_worker_poll() radi podle nahodneho UUID jmena
    # souboru, ne podle queued_at). Nezavisle na A/B/C - hlasi se i kdyz
    # neco jineho bezi normalne, protoze prave TOHLE se stalo dnes (jina
    # uloha bezela/dobihala, zatimco 4587/4593 hladovely v pozadi).
    stare_cekajici = _najdi_stare_cekajici(ted_ts, rhc.PRAH_FRONTA_STARVACE_MIN)
    stare_job_ids = sorted(jid for jid, _ in stare_cekajici)
    if stare_job_ids != (stav.get("hladovejici_joby") or []):
        # zmena mnoziny (pribyla/zmizela hladovejici uloha) - novy alarm,
        # ne jen "porad totez" na kazdem tiku.
        stav["alarm_d_poslany_pro"] = []
    if stare_cekajici and sorted(stare_job_ids) != sorted(stav.get("alarm_d_poslany_pro") or []):
        popis = ", ".join(f"{jid} ({round(min_c)} min)" for jid, min_c in stare_cekajici)
        _alarm("fronta-hladoveni",
               f"{len(stare_cekajici)} uloha(y) ceka(ji) ve stavu 'waiting_worker' "
               f"dele nez {rhc.PRAH_FRONTA_STARVACE_MIN} min, i kdyz fronta jinak "
               f"vypada zdrava: {popis}. Typicky priznak hladoveni podle poradi "
               f"vyzvednuti (viz render_worker_poll() - kandidat #4587/#4593 "
               f"2026-09-25), ne zaseknuti jedine bezici ulohy. NEPREZAROZOVANO "
               f"automaticky.")
        stav["alarm_d_poslany_pro"] = stare_job_ids
    stav["hladovejici_joby"] = stare_job_ids

    stav["posledni_kontrola"] = ted.isoformat()
    _uloz_stav(stav)
    print(f"OK: kandidatu={pocet_kandidatu} bezici_job={job_id or '-'} "
          f"teplota={teplota if teplota is not None else '?'} "
          f"hladovejici={len(stare_cekajici)} "
          f"({ted.strftime('%Y-%m-%d %H:%M')})")


if __name__ == "__main__":
    main()
