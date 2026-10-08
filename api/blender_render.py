"""blender_render.py - server-side render sestavy Blenderem (Cycles).

Robert 2026-08-10 ("zapoj to do sceny, ale chci tam mit plne nastavovani
jako v blenderu") - jeho vlastni navrzena architektura:

    scene.html -> POST GLB + nastaveni -> tenhle endpoint
        -> subprocess: blender -b -P blender_render_scene.py -- cfg.json
        -> PNG na disk -> nacteno a vraceno zpet jako data URI

Proc server-side misto prohlizece: Blender ma BOX projekci textur, ktera
NEPOTREBUJE UV souradnice - katalogove GLB modely zadne nemaji (viz
AGENTS_LOG 2026-08-10), coz byl duvod, proc se PBR textura hliniku v
prohlizecovem rendereru nikdy neprojevila. Overeno na skutecne sestave
(nabidka Logiman0086): 1100x830, 48 vzorku, 44 s.

FRONTA (Robert citoval i tenhle bod ze sveho navodu - "Pokud na vasi
aplikaci kliknou 3 uzivatele naraz... implementujte frontu uloh"):
server ma 4 jadra a Cycles si vezme vsechna, takze soubezne rendery by
se navzajem brzdily a mohly vycerpat pamet. Semafor nize pousti VZDY JEN
JEDEN render; dalsi pozadavek pocka (s vlastnim timeoutem, at klient
neceka do nekonecna).
"""
import base64
import fcntl
import json
import glob
import os
import signal
import subprocess
import threading
import time
import uuid

from flask import jsonify, request

from app import app, get_conn, current_user, require_permission
from quotes import PRIVATE_FILES_DIR
from rendering_settings import _folder_id_setting, _detect_pbr_role, HDRI_EXT, PBR_EXT

# Robert 2026-08-11 ("ten server je slaby dlouho to trva"): oficialni
# Blender z blender.org (/opt/blender-<verze>) MISTO ubuntuho balicku - ten je
# sestaveny BEZ OpenImageDenoise, takze se kvalita musela dohanet poctem
# vzorku. S denoiserem staci nekolikanasobne mene vzorku pri stejne cistote.
# Fallback na /usr/bin/blender, kdyby oficialni build zmizel (a soubezne
# ho dal pouziva api/obj_to_fbx_blender.py - ten se nemeni).
# Robert 2026-09-29: starou 4.2.9 (/opt/blender-official) smazal - zustava 5.2.
#
# bot8 2026-09-09: pevna cesta na 4.2 uz NESTACI. Robert uklada sve
# soubory v Blenderu 5.2.1 a starsi Blender novejsi .blend NEOTEVRE
# ("mas stary blender") - projevi se to jako tise selhany krok, ne jako
# srozumitelna chyba. Bere se proto nejnovejsi nainstalovany:
# /opt/blender-<verze> se radi CISELNE (retezcove razeni by dalo
# "official" > "5.2", protoze 'o' > '5').
def _najdi_blender():
    kandidati = []
    for cesta in glob.glob("/opt/blender-*/blender"):
        znacka = os.path.basename(os.path.dirname(cesta)).split("-", 1)[1]
        try:
            verze = tuple(int(c) for c in znacka.split("."))
        except ValueError:
            verze = (0,)  # "official" a spol. - az za cislovanymi
        kandidati.append((verze, cesta))
    if kandidati:
        return max(kandidati)[1]
    return "/usr/bin/blender"


BLENDER_BIN = _najdi_blender()
BLENDER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_render_scene.py")
BLEND_LOCAL_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_render_blend_local.py")
# Robert 2026-09-09 ("budes delat rendery na nase produktove sestavy podle
# nastaveni VPS blenderu a na vzdalenem GPU") - treti typ ulohy: cely
# otocny nahled sestavy (162 snimku prstencu + 5 stills) z jedne scény.
# Viz PRODUKTOVE_RENDERY.md.
TURNTABLE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_render_turntable.py")
DRIVE_FILES_DIR = os.path.join(PRIVATE_FILES_DIR, "shared-drive")
RENDER_OUT_DIR = os.path.join(PRIVATE_FILES_DIR, "blender-renders")
os.makedirs(RENDER_OUT_DIR, exist_ok=True)

MAX_GLB_BYTES = 60 * 1024 * 1024
RENDER_TIMEOUT_S = 900          # tvrdy strop na jeden render
# bot8 2026-09-09: otocny nahled je 162 snimku + 5 stills z JEDNOHO
# spusteni Blenderu - na serverovem CPU (zadne GPU) to bezi hodiny, ne
# minuty. Kdyz ho server prebira po nepritomnem workerovi (viz
# render_worker.py::_prevzit_opustene_ulohy), 900 s by ho spolehlive
# zabilo tesne po zacatku a uloha by skoncila chybou "trval déle než".
RENDER_TIMEOUT_TURNTABLE_S = 6 * 3600
QUEUE_WAIT_TIMEOUT_S = 600      # jak dlouho uloha ceka ve fronte na volny slot
JOB_RETENTION_S = 3600          # po jake dobe se opustena uloha uklidi

# Robert 2026-08-10 ("CHYBA (Blender): HTTP 504"): render NESMI bezet
# uvnitr HTTP pozadavku - gunicorn ma `--timeout 60` (zabil by workera
# uprostred renderu, coz se stalo: "Worker exiting" + HTTP 500) a nginx
# `proxy_read_timeout 60s` (vratil 504). Oboji je overene v logu.
# Zvysovat oba timeouty by znamenalo drzet HTTP spojeni otevrene klidne
# 10 minut - krehke. Misto toho ASYNCHRONNI uloha: POST render jen
# nastartuje (vrati job_id) a klient se pak doptava na stav.
#
# Stav ulohy je v SOUBORU (ne v pameti procesu) zamerne - gunicorn bezi
# ve 2 workerech, takze dotaz na stav muze obslouzit uplne jiny proces,
# nez ktery render spustil. Ze stejneho duvodu je i fronta resena
# souborovym zamkem (flock), ne threading.Semaphore - ten plati jen
# uvnitr jednoho procesu.
QUEUE_LOCK_PATH = os.path.join(RENDER_OUT_DIR, ".render_queue.lock")


def _status_path(job):
    return os.path.join(RENDER_OUT_DIR, f"{job}.status.json")


# Informativni pole, ktera se maji PRENASET pres vsechny zapisy stavu.
# Zapisuje je jen POST handler pri zalozeni ulohy; bez tohohle by je
# prepsal hned prvni zapis z renderovaciho vlakna (state=running/done)
# a klient by u hotoveho renderu videl "textury: zadne", i kdyz se
# ve skutecnosti pouzily (nalezeno pri testu volby PBR sady 2026-08-11).
#
# bot8 2026-09-09: dopsana POPISNA pole otocneho nahledu. Ulohu zaklada
# CLI skript (2026-09-09_turntable_render.py) se jmenem sestavy a poctem
# ocekavanych snimku - jenze prvni zapis stavu ze serveru (poll workera:
# state="running") je bez nich prepsal a v prehledu fronty pak u bezicich
# uloh svitil prazdny radek bez nazvu i bez "kolik z kolika". Sticky pole
# to ponesou pres vsechny dalsi zapisy stavu.
_STICKY_STATUS_KEYS = ("hdri_used", "textures_used",
                       "job_type", "assembly_id", "assembly_name",
                       "shop_product_id", "expected_frames", "expected_stills",
                       "note",
                       # bot8 2026-09-11: bez tohohle by prvni dalsi zapis
                       # stavu (napr. prechod waiting_worker->running) tenhle
                       # priznak tise zahodil - zalozeny PRI ZARAZENI (viz
                       # 2026-09-09_turntable_render.py), ale CTENY az na
                       # uplnem konci v render_worker_tt_result. Presne stejna
                       # past, kvuli ktere uz tahle sticky-mnozina existuje.
                       "ingest_bez_commitu",
                       # bot16, 2026-09-12 (bot4 zadani, "detail aktualne
                       # zpracovavane ulohy" v admin panelu) - stejny duvod
                       # jako assembly_name/expected_frames vyse: zapsane PRI
                       # ZARAZENI, ale panel se muze podivat kdykoli pozdeji
                       # behem waiting_worker->running prechodu.
                       "samples", "hdri_rotace_deg",
                       # bot4 2026-09-28: presny azimut testovaciho snimku z
                       # panelu, cteny az v render_worker_tt_result
                       "ingest_libovolny_azimut",
                       # bot4 2026-09-29: na KTEREM stroji se ma uloha
                       # renderovat (jmeno workera, napr. notebook) - cteny
                       # v /poll, dokud uloha ceka; bez sticky by ho prvni
                       # dalsi zapis stavu zahodil a uloha by sla na GPU stanici.
                       "target_worker")


def _write_status(job, **fields):
    prev = _read_status(job) or {}
    for k in _STICKY_STATUS_KEYS:
        if k not in fields and k in prev:
            fields[k] = prev[k]
    fields.setdefault("updated", time.time())
    tmp = _status_path(job) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(fields, fh, ensure_ascii=False)
    os.replace(tmp, _status_path(job))  # atomicky - ctenar nikdy neuvidi pulku


def _read_status(job):
    try:
        with open(_status_path(job), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _cleanup_job(job, keep_result=False):
    """keep_result=True nechá `<job>.png` a `<job>.status.json` na místě.

    Robert 2026-09-09 ("chci je ukládat do fotogalerie skladových karet"):
    dokud se vysledek mazal hned po tom, co si ho okno renderu stahlo,
    nesel uz nikam ulozit - kdo si render prohledl a AZ POTOM se rozhodl,
    ze ho chce u skladove karty, nasel prazdno. Vstupy (.glb/.json/nahledy)
    se maza dal hned - ty uz k nicemu nejsou; vysledek dozije bezne
    hodinove lhute (_cleanup_stale_jobs), behem ktere ho lze poslat do
    galerie pres /api/admin/blender-render/<job>/do-galerie.
    """
    suffixes = [".glb", ".json", ".png.tmp.png", ".preview.png", ".preview.png.tmp.png"]
    if not keep_result:
        suffixes += [".png", ".status.json"]
    for suffix in suffixes:
        try:
            os.remove(os.path.join(RENDER_OUT_DIR, job + suffix))
        except OSError:
            pass


def _cleanup_stale_jobs():
    """Opustene ulohy (klient zavrel okno a nikdy si vysledek nevyzvedl).

    bot16 2026-09-03 (revize bot3): maze se PO ULOHACH a jen ty, ktere uz
    skoncily (done/error/cancelled) nebo nemaji zadny stavovy soubor -
    drive se mazal kazdy soubor starsi nez hodina bez ohledu na stav,
    takze dlouhemu renderu na workeru (strop 3600 s) mohl zmizet .glb
    i .status.json zpod rukou. Vola se i pri startu appky, ne jen pri
    novem POST (jinak tu po tydnech lezely soubory z davno hotovych uloh)."""
    now = time.time()
    try:
        names = os.listdir(RENDER_OUT_DIR)
    except OSError:
        return
    newest_age = {}  # job -> stari NEJNOVEJSIHO souboru ulohy
    for name in names:
        if name.startswith("."):
            continue
        job = name.split(".", 1)[0]
        try:
            age = now - os.path.getmtime(os.path.join(RENDER_OUT_DIR, name))
        except OSError:
            continue
        newest_age[job] = min(newest_age.get(job, age), age)
    for job, age in newest_age.items():
        if age <= JOB_RETENTION_S:
            continue  # aspon jeden cerstvy soubor -> uloha se nemaze
        st = _read_status(job)
        if st and st.get("state") not in ("done", "error", "cancelled"):
            continue  # bezi/ceka - nesahat
        _cleanup_job(job)


def blender_bezi_pro_ulohu(job):
    """Bezi na TOMHLE serveru Blender, ktery pracuje prave na teto uloze?

    PRODUKTOVE_RENDERY.md, pravidlo 5: "pred zrusenim renderu zjisti,
    jestli uz nebezi nebo nedobehl" - oznaceni za mrtvou zahodi i hotovy
    vysledek. Otocny nahled jde spustit i RUCNE z prikazove radky
    (`scripts/2026-09-09_turntable_render.py --local`, dnes bezne
    pouzivane pri ladeni): takovy proces neni potomkem aplikace, nema
    zapsany PID ve stavu a pri restartu sluzby by mu stav spadl na
    "error", i kdyz v poradku bezi. Hledame proto ID ulohy primo v
    prikazovych radcich bezicich procesu (cfg cesta ho obsahuje).
    """
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return False
    needle = job.encode()
    for pid in pids:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                argv = fh.read()
        except OSError:
            continue          # proces mezitim skoncil / cizi uzivatel
        if needle in argv and b"blender" in argv.split(b"\0", 1)[0].lower():
            return True
    return False


def _fail_orphaned_jobs_on_startup():
    """Robert 2026-08-11 (uloha visela 40 minut ve stavu "running", i kdyz
    nic nebezelo): rozdelane ulohy NEPREZIJI restart sluzby - renderovaci
    vlakna jsou pryc, ale stavovy soubor zustal na "running"/"queued",
    takze se klient ptal donekonecna. Pri startu je proto oznacime jako
    chybu, at okno renderu hned rekne, co se stalo, misto tichého ceka
    ni. (Ulohu bezici na vzdalenem workeru necháváme být - ta na restartu
    serveru nezavisi, worker si ji dokonci a vysledek posle sam.)"""
    try:
        names = os.listdir(RENDER_OUT_DIR)
    except OSError:
        return
    for name in names:
        if not name.endswith(".status.json"):
            continue
        job = name[:-len(".status.json")]
        st = _read_status(job) or {}
        # POZOR (bot8 2026-09-09): "waiting_worker" se tu ZAMERNE NERUSI.
        # Tahle funkce bezi pri KAZDEM importu modulu, tedy i kdyz si
        # gunicorn nahodi noveho workera (--workers 2, respawn pri
        # --timeout 60) - ne jen pri skutecnem restartu serveru. Uloha
        # cekajici na Robertovu GPU stanici muze cekat i desitky minut
        # (agent zrovna nebezi) a nemela zadnou souvislost s tim, ze se
        # uvnitr appky nahodil worker - presto ji to oznacilo za chybu
        # s matoucim textem "Render byl přerušen restartem serveru".
        # Realne chyceno: uloha s Robertovou sablonou X30 takhle zemrela,
        # i kdyz se API od 09:36 nerestartovalo.
        # Vzdaleny worker na stavu appky nezavisi - uloha na nej pocka.
        if st.get("state") == "queued" or (
                st.get("state") == "running" and not st.get("on_worker")):
            # bot8 2026-09-09: ...a JESTE JEDNA vyjimka - render spusteny
            # rucne z prikazove radky (--local) na appce nezavisi taky.
            # Bez teto kontroly mu kazdy restart sluzby (i respawn
            # gunicorn workera) prepsal stav na "error" uprostred behu.
            if blender_bezi_pro_ulohu(job):
                continue
            _write_status(job, state="error",
                          error="Render byl přerušen restartem serveru - spusť ho prosím znovu.")


_fail_orphaned_jobs_on_startup()
_cleanup_stale_jobs()


def _pid_is_blender(pid):
    """bot16 2026-09-03 (revize bot3): PID ve stavovem souboru muze byt po
    padu vlakna/restartu uz davno cizi proces (PID se recykluji) - SIGKILL
    naslepo by mohl sestrelit napr. gunicorn worker. Zabijet jen tehdy,
    kdyz /proc/<pid>/cmdline je opravdu nas Blender."""
    try:
        with open(f"/proc/{int(pid)}/cmdline", "rb") as fh:
            argv = fh.read().split(b"\0")
    except (OSError, ValueError):
        return False
    return bool(argv) and os.path.basename(argv[0].decode("utf-8", "replace")) == os.path.basename(BLENDER_BIN)


def _kill_job_pid(job, pid):
    if not pid:
        return
    if not _pid_is_blender(pid):
        app.logger.warning("Blender render %s: PID %s neni Blender, kill preskocen.", job, pid)
        return
    try:
        os.kill(int(pid), signal.SIGKILL)
    except (OSError, ValueError):
        pass


def _may_control_job(st, user):
    """bot16 2026-09-03 (revize bot3): rusit/killovat smi jen vlastnik
    ulohy (user_id ulozene ve stavu pri startu) nebo admin. Starsi stavy
    bez user_id (z doby pred touto zmenou) smi rusit kdokoli jako dosud."""
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    owner = (st or {}).get("user_id")
    return owner is None or owner == user.get("id")


def _kill_running_renders(except_job=None, user=None):
    """Robert 2026-08-10 ("a pridej tam kill predesle rendery"): novy
    render zrusi vsechny predchozi bezici/cekajici - typicky uzivatel
    zmeni nastaveni a chce hned videt novy vysledek, na stary uz ceka
    zbytecne (a blokoval by frontu na dalsi minuty). Zabiji se cely
    strom procesu Blenderu podle ulozeneho PID, ne signalem na skupinu -
    at to nikdy nesahne na jine procesy serveru.

    bot16 2026-09-03: rusi se jen VLASTNI ulohy (admin vsechny) - drive
    kazdy s pravem sdileny_disk:zobrazit sestrelil rendery vsech ostatnich."""
    killed = 0
    try:
        names = os.listdir(RENDER_OUT_DIR)
    except OSError:
        return 0
    for name in names:
        if not name.endswith(".status.json"):
            continue
        other = name[:-len(".status.json")]
        if other == except_job:
            continue
        st = _read_status(other)
        if not st or st.get("state") not in ("queued", "running", "waiting_worker"):
            continue
        if not _may_control_job(st, user):
            continue
        _kill_job_pid(other, st.get("pid"))
        _write_status(other, state="cancelled",
                      error="Zrušeno - byl spuštěn novější render.")
        killed += 1
    return killed


def _run_render_job(job, cfg_path, out_path):
    """Bezi v samostatnem vlakne - gunicornuv `--timeout 60` se na nej
    NEVZTAHUJE (ten hlida jen delku obsluhy HTTP pozadavku)."""
    queued_at = time.time()
    # Robert 2026-08-10 ("nezabils to"): uloha zustala navzdy viset ve
    # stavu "queued", protoze vlakno hned spadlo na
    # `PermissionError: .render_queue.lock` - soubor zamku vytvoril
    # dřívější rucni test spusteny jako ROOT, ale appka bezi jako
    # www-data. Pojistky: (1) otevirat "a" misto "w" (nepotrebuje pravo
    # zapisu do obsahu, jen otevrit - a nemaze cizi obsah), (2) pri
    # jakemkoli selhani NAPSAT chybu do stavu, at uloha nikdy nezustane
    # tise viset (presne to Robert videl).
    try:
        lock_fh = open(QUEUE_LOCK_PATH, "a")
    except OSError as e:
        app.logger.error("Blender render: nelze otevrit zamek fronty: %s", e)
        _write_status(job, state="error",
                      error=f"Nelze otevřít zámek fronty renderů ({e}). "
                            f"Zkontroluj práva na složce blender-renders.")
        return
    try:
        # Fronta: vzdy jen JEDEN render naraz (server ma 4 jadra a Cycles
        # si vezme vsechna) - presne ten bod z Robertova navodu.
        #
        # Robert 2026-08-10 ("ten killing nefunguje"): PRAVA PRICINA byla
        # tady. _kill_running_renders() rusi ulohu tak, ze ji zabije podle
        # PID - jenze uloha CEKAJICI VE FRONTE zadny PID jeste nema, takze
        # se jen prepsal jeji stav na "cancelled", ale TOHLE VLAKNO cekalo
        # dal, zamek nakonec ziskalo, prepsalo si stav zpatky na "running"
        # a normalne renderovalo. Novy render pak stal frontu za nim -
        # presne to Robert videl ("Cekam ve fronte... 16 s"). Reseni:
        # kontrolovat zruseni V KAZDEM kole cekani i tesne po ziskani
        # zamku (mezi tim mohl kill dorazit taky).
        while True:
            if (_read_status(job) or {}).get("state") == "cancelled":
                return
            try:
                fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - queued_at > QUEUE_WAIT_TIMEOUT_S:
                    _write_status(job, state="error",
                                  error="Render čekal ve frontě příliš dlouho.")
                    return
                _write_status(job, state="queued",
                              queue_wait_seconds=round(time.time() - queued_at, 1))
                time.sleep(2)

        if (_read_status(job) or {}).get("state") == "cancelled":
            return  # zruseno tesne pred startem - Blender uz vubec nespoustet

        started = time.time()
        # Robert 2026-09-09 ("rozšíření na .blend"): job_type "blend" ma
        # jiny prubeh nez obvykly GLB+skript - otevira se PRIMO ulozeny
        # .blend soubor (vlastni kamera/material/engine uvnitr), jen s
        # bezpecnostni pojistkou GPU->CPU (server GPU nema), viz
        # blender_render_blend_local.py.
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                _job_settings = json.load(fh)
        except (OSError, ValueError):
            _job_settings = {}
        _job_type = _job_settings.get("job_type")
        if _job_type == "blend":
            blend_cmd = [BLENDER_BIN, "-b", "-noaudio", _job_settings["blend_path"],
                        "-P", BLEND_LOCAL_SCRIPT, "--", out_path]
        elif _job_type == "turntable":
            # Sablona (Robertuv .blend z VPS Blenderu) je VOLITELNA - bez ni
            # skript pouzije vestavene vychozi hodnoty. Musi stat PRED -P,
            # jinak ji Blender nenacte jako otviraný soubor.
            _tmpl = _job_settings.get("template_blend")
            blend_cmd = ([BLENDER_BIN, "-b", "-noaudio"]
                         + ([_tmpl] if _tmpl and os.path.exists(_tmpl) else [])
                         + ["-P", TURNTABLE_SCRIPT, "--", cfg_path])
        else:
            blend_cmd = [BLENDER_BIN, "-b", "-noaudio", "-P", BLENDER_SCRIPT, "--", cfg_path]
        # Popen (ne subprocess.run) - potrebujeme PID, aby sel render
        # zabit, kdyz uzivatel spusti novy (viz _kill_running_renders).
        proc = subprocess.Popen(
            blend_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        _write_status(job, state="running", started=started, pid=proc.pid,
                      queue_wait_seconds=round(started - queued_at, 1))
        _strop = RENDER_TIMEOUT_TURNTABLE_S if _job_type == "turntable" else RENDER_TIMEOUT_S
        try:
            stdout, stderr = proc.communicate(timeout=_strop)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            _write_status(job, state="error",
                          error=f"Render trval déle než {_strop} s a byl přerušen - "
                                f"zkus méně vzorků nebo menší rozlišení.")
            return

        # Zabity render (novejsi ho zrusil) uz ma stav "cancelled" -
        # nepsat pres nej chybu, klient by videl matouci hlasku.
        if (_read_status(job) or {}).get("state") == "cancelled":
            return

        if _job_type == "turntable":
            # Vysledek neni jeden PNG, ale adresar snimku + manifest.json.
            _ok = ("TURNTABLE_OK" in (stdout or "")
                   and os.path.exists(os.path.join(_job_settings.get("out_dir", ""), "manifest.json")))
        else:
            _ok = "RENDER_OK" in (stdout or "") and os.path.exists(out_path)
        if not _ok:
            tail = ((stderr or "") + (stdout or ""))[-1200:]
            app.logger.warning("Blender render selhal (job %s): %s", job, tail)
            _write_status(job, state="error", error="Render v Blenderu selhal.", detail=tail)
            return

        # Robert 2026-09-09 ("chci je ukladat do obrazku / fotogalerie
        # skladovych karet"): kdyz uloha vi, ke ktere skladove karte
        # patri, hotovy render se rovnou zaradi do jeji fotogalerie -
        # jinak by ho za hodinu vzal _cleanup_stale_jobs(). Turntable
        # nema jeden vysledny PNG (adresar snimku + manifest), ten si
        # vysledky uklada vlastni cestou.
        #
        # Poradi je zamerne: nejdriv ulozit, pak JEDNIM zapisem oznamit
        # "done" i vysledek ulozeni - klient tak nikdy nevidi hotovy
        # render bez informace o galerii (viz render_gallery.py).
        gal = {}
        if _job_type != "turntable":
            import render_gallery
            gal = render_gallery.ulozit_po_dokonceni(job)
        _write_status(job, state="done",
                      render_seconds=round(time.time() - started, 1),
                      queue_wait_seconds=round(started - queued_at, 1),
                      **gal)
    except Exception as e:  # noqa: BLE001 - vlakno nesmi umrit potichu
        app.logger.exception("Blender render job %s spadl", job)
        _write_status(job, state="error", error=str(e))
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        except OSError:
            pass
        lock_fh.close()

# Meze jednotlivych parametru - klient posila cokoli, server to VZDY
# uzavre do rozumneho rozsahu (jinak by slo poslat samples=1000000 a
# zablokovat server na hodiny).
NUM_LIMITS = {
    "samples": (1, 4096, 48),          # Max Samples - s denoiserem staci vyrazne min (32 vz = 39 s a cisto)
    "min_samples": (0, 4096, 0),       # Min Samples
    "noise_threshold": (0.0, 1.0, 0.05),   # 0.01 = pomale/produkcni, 0.05 = rychle a bez viditelneho sumu
    "time_limit_s": (0, 900, 0),       # 0 = bez limitu (strop stejne hlida RENDER_TIMEOUT_S)
    "resolution_x": (160, 2560, 1100),
    "resolution_y": (120, 2560, 825),
    "max_bounces": (0, 32, 6),
    "diffuse_bounces": (0, 32, 3),
    "glossy_bounces": (0, 32, 3),
    "transmission_bounces": (0, 32, 4),
    "volume_bounces": (0, 32, 0),
    "transparent_bounces": (0, 32, 6),
    "clamp_direct": (0.0, 100.0, 0.0),
    "clamp_indirect": (0.0, 100.0, 10.0),
    "exposure": (-8.0, 8.0, -0.2),
    "gamma": (0.1, 5.0, 1.0),
    "hdri_strength": (0.0, 10.0, 0.7),
    "hdri_rotation_deg": (0.0, 360.0, 0.0),
    "sun_energy": (0.0, 50.0, 3.0),
    "sun_softness_deg": (0.0, 45.0, 7.0),  # mekci stiny - Robert 2026-08-11 "co doporucujes udelej jako default"
    "sun_azimuth_deg": (-360.0, 360.0, 45.0),
    "sun_elevation_deg": (-89.0, 89.0, 50.0),
    "camera_lens_mm": (8.0, 300.0, 50.0),
    "camera_distance_factor": (0.3, 10.0, 2.2),
    "camera_azimuth_deg": (-360.0, 360.0, -50.0),
    "camera_elevation_deg": (-89.0, 89.0, 25.0),
    "dof_fstop": (0.5, 32.0, 2.8),
    "texture_tile_mm": (1.0, 2000.0, 40.0),
    "texture_box_blend": (0.0, 1.0, 0.3),
    "normal_strength": (0.0, 4.0, 1.0),
    "bevel_mm": (0.0, 5.0, 0.4),       # zaobleni hran jen v odrazech (realismus), 0 = vypnuto
    "material_roughness": (0.0, 1.0, 0.28),
    "material_metallic": (0.0, 1.0, 1.0),
    "floor_roughness": (0.0, 1.0, 0.6),
    "floor_dot_spacing_mm": (0.0, 2000.0, 0.0),    # HUD sit bodu na podlaze; 0 = auto podle velikosti sestavy
    "floor_dot_radius_mm": (0.0, 100.0, 0.0),      # 0 = auto (9 % rozteci)
    "floor_dot_glow": (0.0, 5.0, 0.35),
    # Shading (Robert 2026-08-11: "chci mit moznost zmenit texturu a
    # shading nodes" primo v okne renderu) - pouziva se, kdyz jsou
    # PBR textury vypnute (use_pbr_textures=False), plus coat platit vzdy.
    "coat_weight": (0.0, 1.0, 0.0),
}
BOOL_KEYS = ("floor_enabled", "floor_dots", "sun_enabled", "dof_enabled", "hdri_as_background",
             "transparent_background", "use_normal_map", "shade_smooth",
             "adaptive_sampling", "use_pbr_textures", "progressive_preview",
             "use_denoising")
# Robert 2026-08-11 ("nejak se mu nechce renderovat"): prepinace, ktere
# maji byt ZAPNUTE, kdyz je klient vubec neposle. Drive se vsechny bralo
# jako False - u `progressive_preview` (ktery nema v panelu zatrzitko a
# tedy se nikdy neposilal) to znamenalo, ze prubezne nahledy behem
# renderu UPLNE PRESTALY chodit, i kdyz je Robert vyslovne chtel
# ("chci to videt prubezne obraz kazdych 5 sec"). Same plati pro volani
# z jinych mist (napr. budouci render nabidek), ktera posilaji jen cast
# nastaveni.
BOOL_DEFAULTS = {
    "floor_dots": True,
    "progressive_preview": True,
    "use_pbr_textures": True,
    "use_normal_map": True,
    "floor_enabled": True,
    "sun_enabled": True,
    "adaptive_sampling": True,
    "use_denoising": True,
}
VIEW_TRANSFORMS = ("Standard", "Filmic", "Filmic Log", "Raw", "AgX", "Khronos PBR Neutral")
LOOKS = ("None", "Medium Contrast", "High Contrast", "Low Contrast",
         "Very High Contrast", "Very Low Contrast")


def _clamp_settings(raw):
    out = {}
    for key, (lo, hi, default) in NUM_LIMITS.items():
        try:
            v = float(raw.get(key, default))
        except (TypeError, ValueError):
            v = default
        out[key] = max(lo, min(hi, v))
    for key in BOOL_KEYS:
        out[key] = bool(raw.get(key, BOOL_DEFAULTS.get(key, False)))
    # Robert 2026-09-09 ("dej tam jen 2 možnosti blender/cycles a ten
    # Luxcore") - alternativni vypocetni engine vedle Cyclesu, zatim jen
    # zkusebni/porovnavaci (viz blender_render_scene.py "renderer").
    renderer = raw.get("renderer")
    out["renderer"] = renderer if renderer in ("cycles", "luxcore") else "cycles"
    vt = raw.get("view_transform")
    out["view_transform"] = vt if vt in VIEW_TRANSFORMS else "AgX"
    look = raw.get("look")
    out["look"] = look if look in LOOKS else "None"
    fp = raw.get("floor_pattern")
    out["floor_pattern"] = fp if fp in ("dots", "lines", "grid", "cross", "none") else "lines"
    for key, default in (("background_color", [0.85, 0.86, 0.87]),
                         ("floor_color", [0.35, 0.35, 0.36]),
                         # Robert 2026-09-08 ("hledej na internetu odborné
                         # podklady") - puvodni [0.62,0.64,0.67] byl daleko
                         # pod skutecnou odrazivosti hliniku. Zmereny F0
                         # (odraz pri normalovem dopadu) cisteho hliniku v
                         # linearnim prostoru je (0.91, 0.92, 0.92) - viz
                         # AGENTS_LOG.md pro zdroje.
                         ("base_color", [0.91, 0.92, 0.92])):
        val = raw.get(key)
        if (isinstance(val, list) and len(val) == 3
                and all(isinstance(c, (int, float)) for c in val)):
            out[key] = [max(0.0, min(1.0, float(c))) for c in val]
        else:
            out[key] = default

    # Robert 2026-08-11 ("ted potrebujeme nas Render cycle dostat do
    # nabidky"): konkretni kamera ze sceny (souradnice v mm, three.js
    # Y-nahoru - prevod na Blender resi renderovaci skript). Kdyz
    # nedorazi, kamera se dopocita z azimut/elevace posuvniku jako dosud.
    for key in ("camera_position", "camera_target"):
        val = raw.get(key)
        if (isinstance(val, list) and len(val) == 3
                and all(isinstance(c, (int, float)) for c in val)
                and all(abs(float(c)) < 1e7 for c in val)):
            out[key] = [float(c) for c in val]
    try:
        fov = float(raw.get("camera_fov_deg", 0) or 0)
    except (TypeError, ValueError):
        fov = 0.0
    if 1.0 <= fov <= 170.0:
        out["camera_fov_deg"] = fov
    return out


def _files_for_choice(hdri_file_id, pbr_folder_id):
    """Robert 2026-08-11: konkretni HDRI/PBR sada vybrana v okne renderu
    (viz /assets vyse). Kdyz klient nic nevybral, vrati (None, None) a
    volajici pouzije vychozi sadu nastavenou v administraci."""
    hdri_path, textures = None, None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if hdri_file_id:
                cur.execute("SELECT filename, stored_filename FROM shared_drive_files WHERE id=%s",
                            (hdri_file_id,))
                r = cur.fetchone()
                if r and os.path.splitext(r["filename"])[1].lower() in HDRI_EXT:
                    p = os.path.join(DRIVE_FILES_DIR, r["stored_filename"])
                    if os.path.exists(p):
                        hdri_path = p
            if pbr_folder_id:
                cur.execute("SELECT filename, stored_filename FROM shared_drive_files "
                            "WHERE folder_id=%s ORDER BY filename", (pbr_folder_id,))
                textures = {}
                for r in cur.fetchall():
                    role = _detect_pbr_role(r["filename"])
                    if role and role not in textures:
                        p = os.path.join(DRIVE_FILES_DIR, r["stored_filename"])
                        if os.path.exists(p):
                            textures[role] = p
    finally:
        conn.close()
    return hdri_path, textures


def _active_rendering_files():
    """Cesty k aktivni HDRI mape a PBR sade NA DISKU (ne URL) - Blender
    bezi jako lokalni proces, takze cte primo soubory."""
    hdri_path, textures = None, {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            hdri_folder = _folder_id_setting(cur, "rendering_hdri_folder_id")
            if hdri_folder is not None:
                cur.execute("SELECT filename, stored_filename FROM shared_drive_files "
                            "WHERE folder_id=%s ORDER BY filename", (hdri_folder,))
                for r in cur.fetchall():
                    if os.path.splitext(r["filename"])[1].lower() in HDRI_EXT:
                        p = os.path.join(DRIVE_FILES_DIR, r["stored_filename"])
                        if os.path.exists(p):
                            hdri_path = p
                            break
            pbr_folder = _folder_id_setting(cur, "rendering_pbr_folder_id")
            if pbr_folder is not None:
                cur.execute("SELECT filename, stored_filename FROM shared_drive_files "
                            "WHERE folder_id=%s ORDER BY filename", (pbr_folder,))
                for r in cur.fetchall():
                    role = _detect_pbr_role(r["filename"])
                    if role and role not in textures:
                        p = os.path.join(DRIVE_FILES_DIR, r["stored_filename"])
                        if os.path.exists(p):
                            textures[role] = p
    finally:
        conn.close()
    return hdri_path, textures


@app.post("/api/admin/blender-render")
@require_permission("sdileny_disk", "zobrazit")
def blender_render():
    if not os.path.exists(BLENDER_BIN):
        return jsonify({"error": "Blender není na serveru nainstalovaný."}), 503

    f = request.files.get("model")
    if not f or not f.filename:
        return jsonify({"error": "Chybí GLB model."}), 400
    raw = f.read()
    if len(raw) > MAX_GLB_BYTES:
        return jsonify({"error": f"Model je příliš velký (max {MAX_GLB_BYTES // (1024*1024)} MB)."}), 400
    if len(raw) < 20 or raw[:4] != b"glTF":
        return jsonify({"error": "Neplatný GLB soubor."}), 400

    try:
        raw_settings = json.loads(request.form.get("settings") or "{}")
    except ValueError:
        raw_settings = {}
    settings = _clamp_settings(raw_settings if isinstance(raw_settings, dict) else {})

    # Vyber v okne renderu ma prednost pred vychozi sadou z administrace.
    raw_dict = raw_settings if isinstance(raw_settings, dict) else {}

    def _int_or_none(v):
        try:
            return int(v) if v not in (None, "", "auto") else None
        except (TypeError, ValueError):
            return None

    hdri_path, textures = _files_for_choice(_int_or_none(raw_dict.get("hdri_file_id")),
                                            _int_or_none(raw_dict.get("pbr_folder_id")))
    default_hdri, default_tex = _active_rendering_files()
    if hdri_path is None:
        hdri_path = default_hdri
    if not textures:
        textures = default_tex
    settings["hdri_path"] = hdri_path
    settings["textures"] = textures if settings.get("use_pbr_textures", True) else {}
    # Volitelne: ke ktere skladove karte render patri (viz render_gallery.py) -
    # po dokonceni se sam zaradi do jeji fotogalerie misto toho, aby ho za
    # hodinu vzal uklid. Bez nej se chova render jako doted (jen okno renderu).
    _gp = _int_or_none(raw_dict.get("gallery_product_id"))
    if _gp:
        settings["gallery_product_id"] = _gp
    # bot4 2026-10-01 (Robert pres bot5: "Online nabidky se musi renderovat na Omen"): scena u renderu nabidek a
    # testu posila ucel "nabidka"; ktery stroj ho dostane, rozhoduje server (render_worker.stroj_pro_ucel).
    ucel = str(raw_dict.get("ucel") or "").strip().lower()[:20]
    # bot4 2026-10-01 (Robert: "renderovani v online nabidce musi mit stejne pozadi jako automat na karty" + materialy
    # jako Vandr): kdyz scena k nabidce posle i ZAPIS DILU (`recipe`), zkusi se KARTOVA cesta (sablona X30-02, HDRI,
    # materialy z panelu - viz api/nabidka_kartova_cesta.py). Kdykoli to nejde (zadny volny GPU stroj, dil mimo katalog,
    # vypnuto...), jede se STAROU cestou nize, jako dosud; nic se tim neztrati.
    poznamka_cesty = None
    if ucel == "nabidka" and request.form.get("recipe"):
        try:
            import nabidka_kartova_cesta as nkc
            kam = nkc.zarad(nkc.nacti_dily(request.form.get("recipe")), raw_dict.get("camera_azimuth_deg"),
                            raw_dict.get("camera_elevation_deg"), current_user())
            return jsonify({"job_id": kam["job"], "state": "queued", "cancelled_previous": kam["killed"],
                            "target": "worker", "stroj": kam["stroj"], "cesta": "karta"}), 202
        except Exception as e:  # noqa: BLE001 - nabidka nesmi spadnout kvuli nove ceste
            if e.__class__.__name__ == "KartovaCestaNeni":
                app.logger.info("Nabidka: kartova cesta nejde (%s), jede stara cesta.", e)
            else:
                app.logger.exception("Nabidka: kartova cesta selhala necekane, jede stara cesta")
            poznamka_cesty = "Kartová cesta nejde (%s), renderuje se starou cestou." % str(e)[:200]
    if raw_dict.get("gallery_caption"):
        settings["gallery_caption"] = str(raw_dict["gallery_caption"])[:255]

    job = uuid.uuid4().hex
    glb_path = os.path.join(RENDER_OUT_DIR, f"{job}.glb")
    cfg_path = os.path.join(RENDER_OUT_DIR, f"{job}.json")
    out_path = os.path.join(RENDER_OUT_DIR, f"{job}.png")
    settings["glb_path"] = glb_path
    settings["output_path"] = out_path
    settings["preview_path"] = os.path.join(RENDER_OUT_DIR, f"{job}.preview.png")

    user = current_user()
    _cleanup_stale_jobs()
    killed = _kill_running_renders(except_job=job, user=user)  # novy render rusi predchozi (jen vlastni)
    with open(glb_path, "wb") as fh:
        fh.write(raw)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, ensure_ascii=False)
    _write_status(job, state="queued", queue_wait_seconds=0,
                  user_id=user["id"] if user else None,
                  **({"note": poznamka_cesty} if poznamka_cesty else {}),
                  hdri_used=os.path.basename(hdri_path) if hdri_path else None,
                  # hlasit to, co se SKUTECNE pouzije (pri vypnutych
                  # texturach je settings["textures"] prazdne)
                  textures_used=sorted((settings.get("textures") or {}).keys()))

    # Robert 2026-08-11 ("zkus to presmerova na muj notebook, mam gpu"):
    # kdyz je pripojeny GPU worker (jeho notebook), uloha jde JEMU;
    # jinak se renderuje lokalne na CPU jako doted. Rozhodnuti + pojistka
    # pro pripad, ze si ji worker nevyzvedne, viz api/render_worker.py.
    try:
        import render_worker
        target = render_worker.dispatch_to_worker_or_local(job, cfg_path, out_path,
                                                           cil=render_worker.stroj_pro_ucel(ucel))
    except Exception:  # noqa: BLE001 - render nesmi spadnout kvuli workeru
        app.logger.exception("Dispatch na worker selhal, renderuji lokalne")
        threading.Thread(target=_run_render_job, args=(job, cfg_path, out_path),
                         name=f"blender-render-{job[:8]}", daemon=True).start()
        target = "local"

    # 202 Accepted - render TEPRVE ZACAL, klient si vysledek vyzvedne
    # dotazovanim na /api/admin/blender-render/<job> (viz nize).
    _st = _read_status(job) or {}
    return jsonify({"job_id": job, "state": "queued", "cancelled_previous": killed,
                    "target": target, "stroj": _st.get("target_worker") or _st.get("worker_name")}), 202


# Robert 2026-09-09 ("udelej rozšíření na .blend pro renderování
# automaticke na gpu v síti") - druhy typ ulohy vedle GLB+skript: syrovy
# .blend soubor uz ulozeny na Sdilenem disku (Robert si ho tam sam
# ulozil primo z Blenderu), renderovany PRESNE tak, jak byl ulozen
# (vlastni kamera/material/engine/vzorky uvnitr, zadna sestava se
# nestavi z nasich katalogovych dat). Stejny job/queue/worker mechanismus
# jako GLB vetev - jen jiny "job_type" v ulozenych nastaveni (viz
# render_worker.py::render_worker_poll a _run_render_job vyse).
@app.post("/api/admin/blender-render-blend")
@require_permission("sdileny_disk", "zobrazit")
def blender_render_blend_start():
    body = request.get_json(silent=True) or {}
    try:
        file_id = int(body.get("file_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí platné file_id."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, filename, stored_filename FROM shared_drive_files WHERE id=%s", (file_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Soubor na Sdíleném disku nenalezen."}), 404
    if not row["filename"].lower().endswith(".blend"):
        return jsonify({"error": "Vybraný soubor není .blend."}), 400

    blend_path = os.path.realpath(os.path.join(DRIVE_FILES_DIR, row["stored_filename"]))
    if not blend_path.startswith(os.path.realpath(DRIVE_FILES_DIR)) or not os.path.exists(blend_path):
        return jsonify({"error": ".blend soubor nenalezen na disku."}), 404

    job = uuid.uuid4().hex
    cfg_path = os.path.join(RENDER_OUT_DIR, f"{job}.json")
    out_path = os.path.join(RENDER_OUT_DIR, f"{job}.png")
    settings = {"job_type": "blend", "blend_path": blend_path, "output_path": out_path,
                "source_filename": row["filename"]}
    # Volitelne: ke ktere skladove karte render patri. Kdyz je vyplneno,
    # hotovy PNG se sam zaradi do jeji fotogalerie (viz render_gallery.py).
    try:
        if body.get("product_id") not in (None, "", 0):
            settings["gallery_product_id"] = int(body["product_id"])
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné product_id."}), 400
    if body.get("caption"):
        settings["gallery_caption"] = str(body["caption"])[:255]

    user = current_user()
    _cleanup_stale_jobs()
    killed = _kill_running_renders(except_job=job, user=user)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, ensure_ascii=False)
    _write_status(job, state="queued", queue_wait_seconds=0,
                  user_id=user["id"] if user else None, source_filename=row["filename"])

    try:
        import render_worker
        target = render_worker.dispatch_to_worker_or_local(job, cfg_path, out_path)
    except Exception:  # noqa: BLE001 - render nesmi spadnout kvuli workeru
        app.logger.exception("Dispatch .blend na worker selhal, renderuji lokalne")
        threading.Thread(target=_run_render_job, args=(job, cfg_path, out_path),
                         name=f"blender-render-{job[:8]}", daemon=True).start()
        target = "local"

    return jsonify({"job_id": job, "state": "queued", "cancelled_previous": killed,
                    "target": target}), 202


@app.get("/api/admin/blender-render/assets")
@require_permission("sdileny_disk", "zobrazit")
def blender_render_assets():
    """Robert 2026-08-11 ("prave v tomto okne chci mit moznost zmenit
    texturu a shading nodes"): seznam VSECH pouzitelnych HDRI map a PBR
    sad na Sdilenem disku, aby sla textura/prostredi prepnout primo v
    okne renderu - bez chozeni do administrace (tam se dal nastavuje
    jen VYCHOZI sada, kterou pouzivaji nabidky)."""
    hdri, pbr_sets = [], {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT f.id, f.filename, f.folder_id, d.name AS folder_name "
                "FROM shared_drive_files f "
                "LEFT JOIN shared_drive_folders d ON d.id = f.folder_id "
                "ORDER BY d.name, f.filename"
            )
            for r in cur.fetchall():
                ext = os.path.splitext(r["filename"])[1].lower()
                if ext in HDRI_EXT:
                    hdri.append({"id": r["id"], "name": r["filename"],
                                 "folder": r["folder_name"] or "-"})
                    continue
                role = _detect_pbr_role(r["filename"])
                if role and ext in PBR_EXT:
                    s = pbr_sets.setdefault(r["folder_id"], {
                        "folder_id": r["folder_id"],
                        "name": r["folder_name"] or f"složka #{r['folder_id']}",
                        "roles": [],
                    })
                    if role not in s["roles"]:
                        s["roles"].append(role)
    finally:
        conn.close()
    # Ktera sada je vychozi (volba "- vychozi z administrace -") a jake
    # ma mapy - panel podle toho pozna, ktere posuvniky textura skutecne
    # prebiji (Robert 2026-08-11: "zamceli se posuvniky, to je spatne" -
    # Hlinik_1 nema metallic mapu, takze Metallic posuvnik PLATI).
    default_roles = []
    _, default_tex = _active_rendering_files()
    if default_tex:
        default_roles = sorted(default_tex.keys())
    return jsonify({"hdri": hdri,
                    "default_pbr_roles": default_roles,
                    "pbr_sets": sorted(pbr_sets.values(), key=lambda s: s["name"])})


@app.post("/api/admin/blender-render/<job>/cancel")
@require_permission("sdileny_disk", "zobrazit")
def blender_render_cancel(job):
    """Robert 2026-08-10 ("v blenderu byva tlacitko stop (killer) u cycles
    behem renderovani"): rucni zastaveni PRAVE TOHOTO renderu tlacitkem v
    okne vysledku. Stejny mechanismus jako automaticke ruseni pri
    spusteni noveho renderu (_kill_running_renders), jen cileno na jednu
    konkretni ulohu a s vlastni hlaskou, at je v okne poznat, ze to
    zastavil uzivatel, ne ze neco spadlo."""
    if not job.isalnum() or len(job) != 32:
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    st = _read_status(job)
    if not st:
        return jsonify({"error": "Úloha neexistuje."}), 404
    if st.get("state") in ("done", "error", "cancelled"):
        return jsonify({"status": "ok", "state": st.get("state")})  # uz je po vsem
    if not _may_control_job(st, current_user()):
        return jsonify({"error": "Tenhle render spustil jiný uživatel."}), 403
    _kill_job_pid(job, st.get("pid"))
    _write_status(job, state="cancelled", error="Render zastaven uživatelem.",
                  stopped_by_user=True)
    return jsonify({"status": "ok", "state": "cancelled"})


@app.get("/api/admin/blender-render/<job>")
@require_permission("sdileny_disk", "zobrazit")
def blender_render_status(job):
    if not job.isalnum() or len(job) != 32:  # ochrana proti path traversal
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    status = _read_status(job)
    if not status:
        return jsonify({"error": "Úloha neexistuje (nebo už byla vyzvednuta/uklizena)."}), 404

    state = status.get("state")
    if state != "done":
        # Robert ("chci to videt prubezne obraz kazdych 5 sec"): dokud
        # render bezi, vracime i posledni hotovy PRUCHOD (viz progresivni
        # pruchody v blender_render_scene.py). `preview_mtime` slouzi
        # klientovi k tomu, aby stejny nahled nestahoval znovu - posle ho
        # zpet jako ?have=<mtime> a server pak obrazek vynecha.
        preview_path = os.path.join(RENDER_OUT_DIR, f"{job}.preview.png")
        try:
            mtime = os.path.getmtime(preview_path)
            status["preview_mtime"] = round(mtime, 3)
            if request.args.get("have") != str(round(mtime, 3)):
                with open(preview_path, "rb") as fh:
                    status["preview"] = "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")
        except OSError:
            pass  # jeste neni ani prvni pruchod hotovy
        return jsonify(status)

    # Otocny nahled nema `<job>.png` - jeho vysledkem je davka snimku, kterou
    # uz prevzal turntable_ingest (viz render_worker_tt_result). Bez tehle
    # vetve by dotaz na HOTOVOU otocnou ulohu spadl nize na chybejici PNG,
    # vratil 404 "Výsledek renderu už na serveru není" a jeste ulohu uklidil -
    # tedy presne v okamziku, kdy ma klient videt `ingest_ok`. (bot8 2026-09-11)
    if status.get("job_type") == "turntable":
        return jsonify(status)

    out_path = os.path.join(RENDER_OUT_DIR, f"{job}.png")
    try:
        with open(out_path, "rb") as fh:
            png = fh.read()
    except OSError:
        _cleanup_job(job)
        return jsonify({"error": "Výsledek renderu už na serveru není."}), 404

    payload = dict(status)
    payload["image"] = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    payload["size_kb"] = round(len(png) / 1024)
    # Vstupy uz nejsou potreba, ale VYSLEDEK zustava do konce hodinove
    # lhuty - aby sel po prohlednuti poslat do fotogalerie skladove karty
    # (viz _cleanup_job vyse a api/render_gallery.py).
    _cleanup_job(job, keep_result=True)
    return jsonify(payload)
