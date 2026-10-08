"""render_worker.py - vzdaleny renderovaci worker (GPU notebook).

Robert 2026-08-11 ("ten server je slaby dlouho to trva" -> "zkus to
presmerova na muj notebook, mam gpu" - RTX 4080 Laptop GPU).

PROC AGENT A NE PRIME VOLANI: server se na notebook NEDOVOLA (je za
domacim NAT/routerem, nema verejnou IP). Tok je proto obraceny - na
notebooku bezi maly skript (scripts/render_worker_agent.py), ktery se
serveru sam pta "mas pro me praci?":

    [scena] -> POST /api/admin/blender-render (jako dosud)
        -> server: je worker online? (heartbeat < WORKER_ONLINE_S)
             ANO -> uloha ceka ve stavu "waiting_worker"
             NE  -> renderuje se lokalne na CPU (puvodni chovani)
    [notebook] GET  /api/render-worker/poll      <- vyzvedne ulohu
               GET  .../model, .../asset/<i>, .../script  <- stahne data
               POST .../preview                 <- prubezne nahledy
               POST .../result                  <- hotovy PNG
    [scena] se dal ptá na /api/admin/blender-render/<job> a nepozna
            rozdil - dostane stejny vysledek, jen mnohem driv.

POJISTKA: kdyz si worker ulohu do WORKER_CLAIM_TIMEOUT_S nevyzvedne
(notebook uspal, agent spadl, sit vypadla), server ji automaticky
prevezme a odrenderuje sam na CPU - uzivatel tedy nikdy neceka na
nepritomny notebook.

AUTENTIZACE: sdileny token (RENDER_WORKER_TOKEN v api/.env) v hlavicce
X-Worker-Token - agent bezi mimo prohlizec, takze session cookie nema.
"""
import hashlib
import io
import re
import shutil
import zipfile
import hmac
import json
import os
import threading
import time
import urllib.parse

from flask import jsonify, request, send_file

from app import app, admin_required, get_conn, _client_ip, require_permission
import blender_render as br

WORKER_TOKEN = os.environ.get("RENDER_WORKER_TOKEN", "")
WORKER_ONLINE_S = 90          # jak dlouho po heartbeatu povazujeme workera za online
WORKER_CLAIM_TIMEOUT_S = 25   # nevyzvedne-li si ulohu, prebira ji server
WORKER_RESULT_TIMEOUT_S = 3600  # absolutni strop na jeden render na workeru
# Robert 2026-08-11 ("Worker (notebook) render nedokoncil vcas"): puvodni
# pevny 10minutovy limit byl moc kratky - Blender pri PRVNIM OptiX renderu
# kompiluje GPU jadra (klidne nekolik minut) a teprve pak zacne pocitat.
# Server proto uz nehlida celkovy cas, ale to, jestli render POSTUPUJE:
# agent posila kazdych ~15 s ping (viz /progress nize) a teprve kdyz
# prestane, uloha spadne.
WORKER_NO_PROGRESS_S = 240

# --------------------------------------------------------------------
# bot8 2026-09-09 - PROC TU PRIBYLA CELA TAHLE PARTIE (Robert: "k agentovi
# na mem PC NEMAME PRISTUP, takze 'restartuj agenta' nesmi byt reseni,
# ktere pipeline potrebuje"):
#
# Vecer se fronta tise zastavila na 1,5 hodiny. Server pritom cely cas
# hlasil "WORKER: ONLINE", protoze veril JEDINE stari tepu - jenze tep je
# v agentovi samostatne vlakno. Hlavni smycka (ta, co si bere praci)
# mezitim nezila. "Tluce srdce" a "odebira praci" jsou dve RUZNE veci a
# server je od sebe musi umet rozeznat.
#
# Proto se ted zvlast zaznamenava CAS POSLEDNIHO POLLU (`poll_ts`) a
# stav workera ma tri hodnoty misto dvou: online / zaseknuty / offline.
# Ze stejneho udaje vychazi i prebirani opustenych uloh nize - aby uloha
# nikdy necekala donekonecna na nekoho, kdo uz se neptá.
WORKER_POLL_STALE_S = 180     # poll chodi a 3 s; 3 min ticha = uz to neni vypadek site
WORKER_TAKEOVER_S = 600       # jak dlouho uloha ceka na workera, nez ji prevezme server
WORKER_STALE_RUNNING_S = 1200  # "bezi na workerovi" bez jedineho hlaseni = mrtva
WORKER_MIN_ALIVE_S = 120      # nikdy neprohlasit za mrtvou ulohu mladsi nez tohle
WORKER_CIL_CEKANI_S = 600      # cilena uloha (test na notebooku), jehoz stroj se tolik minut neozval = chyba
SUPERVISOR_TICK_S = 30        # jak casto dozorce kontroluje frontu
SUPERVISOR_FIRST_TICK_S = 60  # prvni kontrola az za minutu (viz spousteni vlakna dole)

_HEARTBEAT_PATH = os.path.join(br.RENDER_OUT_DIR, ".worker_heartbeat.json")

# bot4 2026-09-29 (Robert: "nastav mi tam moznost renderovat u me" - notebook
# vedle GPU stanice): vic stroju. VYCHOZI worker (GPU stanice) dela vsechno
# jako dosud - produkci, automat, ulohy bez cile - a ma puvodni tepovy soubor,
# takze vsechen dohled (watchdog, worker_online()) zustava beze zmeny. KAZDY
# JINY stroj (notebook) bere JEN ulohy, u kterych je vyslovne uveden jako cil
# (`target_worker` ve stavu ulohy) a tepe do SVEHO souboru - jeho zapnuti nikdy
# neovlivni produkci ani neprepise tep GPU stanice. Jmeno = hostname agenta
# (WORKER_NAME / platform.node()), porovnava se bez ohledu na velikost pismen.
WORKER_VYCHOZI_JMENO = os.environ.get("RENDER_WORKER_VYCHOZI", "Logiman2").strip() or "Logiman2"


def _jmeno_klic(jmeno):
    return (jmeno or "").strip().lower()


def je_vychozi_worker(jmeno):
    """Prazdne/chybejici jmeno (starsi ulohy bez worker_name) = vychozi stroj."""
    k = _jmeno_klic(jmeno)
    return not k or k == _jmeno_klic(WORKER_VYCHOZI_JMENO)


def _hb_cesta(jmeno):
    if je_vychozi_worker(jmeno):
        return _HEARTBEAT_PATH
    slug = re.sub(r"[^a-z0-9_-]", "_", _jmeno_klic(jmeno))[:40] or "worker"
    return os.path.join(br.RENDER_OUT_DIR, ".worker_heartbeat.%s.json" % slug)


_SUPERVISOR_LOCK_PATH = os.path.join(br.RENDER_OUT_DIR, ".worker_supervisor.lock")

# Pole, ktera se pri zapisu tepu PRENASEJI z predchoziho stavu (tep i poll
# zapisuji tentyz soubor, ale kazdy vi jen o svem case).
#
# bot9 2026-09-11 (nalezeno pri opravovani chybejici verze v tepu, viz
# "version" nize): /api/render-worker/poll pise VLASTNI, uzsi slovnik
# (jen name/gpu/ip/agent_since) - bez prenaseni by KAZDY poll (chodi
# ~kazde 3 s, mnohem castej nez tep po 20 s) vymazal "version" z
# NEJVYSSI urovne JSON hned pri dalsim zapisu.
#
# POZOR: gpu_temp_c/gpu_util_pct/gpu_clock_mhz sem NEPATRI, i kdyz maji
# stejny problem (viz `_carry_gpu_hodnoty` nize, samostatne osetreno AZ
# PO rozhodnuti o zapisu do historie) - kdyby byly v tomhle seznamu,
# carry-forward by je vratil do `info` PRED kontrolou "je tohle cerstvy
# udaj?", a kazdy poll (ne jen tep) by tak vyrobil dalsi zaznam v
# `gpu_historie` se stejnymi starymi cisly - strop 1080 zaznamu (6 h)
# by se vycerpal za cca hodinu mista za 6 hodin.
_HB_PRENASENA = ("poll_ts", "agent_since", "agent_since_ts", "poll_missing_since",
                 "version")

# --------------------------------------------------------- teplota GPU
# Robert 2026-09-11: "postavte sluzbu, ktera bude posilat informace o
# teplote GPU". Agent (scripts/render_worker_agent.py) posila jen TRI
# CISLA za tep (temperature.gpu/utilization.gpu/clocks.sm z `nvidia-smi`,
# nikdy nevyhozena vyjimka, viz jeho `precti_gpu_senzory()`) - historie,
# prah a hystereze upozorneni zamerne zijou TADY, na serveru, ne v
# agentovi. Duvod: k agentovi na Logiman2 se boti nedostanou jinak nez
# pres jeho vlastni samoaktualizaci (viz WORKFLOW poznamka u
# render_worker_agent.py) - cokoli, co se muze jeste ladit (prah,
# delka historie), tu proto NENI zadratovane v kodu, ktery by kazda
# zmena musela znovu poslat do rizikoveho agenta.
GPU_HISTORIE_MAX = 1080   # 6 hodin pri tepu kazdych 20 s - "skromny kruhovy zaznam"
GPU_TEPLOTA_PRAH_VYCHOZI_C = 83.0   # RTX 3060: bezny provoz do ~80C, skrceni kolem 83C


def _bezpecne_cislo(v):
    """Cislo z JSON tela pozadavku, nebo None - nikdy vyjimka. Agent
    posila cisla, ale telo requestu je vnejsi vstup, nikdy mu neverit
    natvrdo (viz `_write_heartbeat` OSError vzor nize)."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _gpu_teplota_prah_c():
    """Prah pro upozorneni na teplotu GPU - NASTAVITELNY (app_settings),
    ne zadratovany. Stejny vzorec jako uz existujici
    `_vzorky_z_nastaveni()` (scripts/2026-09-09_turntable_job.py):
    chybejici/nesmyslna hodnota v DB tise spadne na vychozi konstantu."""
    try:
        conn = get_conn()
    except Exception:
        return GPU_TEPLOTA_PRAH_VYCHOZI_C
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
                        ("gpu_teplota_prah_c",))
            row = cur.fetchone()
        if row and row.get("setting_value"):
            return float(row["setting_value"])
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return GPU_TEPLOTA_PRAH_VYCHOZI_C


def _write_heartbeat(info, poll=False):
    """Zapis tepu workera. Docasny soubor MUSI byt unikatni per proces.

    bot8 2026-09-09 (realne chycene, cely vecer zdrzelo): tmp mel pevny
    nazev `.worker_heartbeat.json.tmp`, ale gunicorn bezi s `--workers 2`
    a agent tluce heartbeat i poll soubezne. Dva procesy si tak psaly do
    TEHOZ souboru a ten, kdo prisel na `os.replace` druhy, uz tmp nenasel
    (prvni ho prejmenoval) -> FileNotFoundError -> HTTP 500 na
    /api/render-worker/poll. Agent na to odpovedel jen vypisem do konzole
    a fronta se zastavila. Unikatni nazev podle PID sraz odstranuje;
    `os.replace` samotny je atomicky, takze ctenar nikdy neuvidi pulku.
    """
    cesta_hb = _hb_cesta(info.get("name"))
    prev = _read_heartbeat(cesta_hb) or {}
    info = dict(info)
    if poll:
        info["poll_ts"] = info.get("ts") or time.time()
    # `agent_since` je cas startu agenta podle JEHO hodin - porovnavat ho
    # s nasimi casy uloh nelze (jine hodiny, jina zona). Vedle nej si
    # proto drzime `agent_since_ts`: NAS cas, kdy jsme tuhle hodnotu
    # videli poprve. Zmenila-li se, agent mezitim restartoval - a kazda
    # uloha, kterou porad vedeme jako "bezi u nej", je prokazatelne mrtva.
    # POZOR na normalizaci: poll posila `since` v URL (retezec), tep v
    # JSON tele (cislo). Bez sjednoceni by se hodnota "menila" pri kazdem
    # druhem zapisu a server by kazdou chvili myslel, ze agent restartoval
    # (a rusil by ulohy, ktere v poradku bezi).
    try:
        since = str(int(float(info.get("agent_since")))) if info.get("agent_since") else None
    except (TypeError, ValueError):
        since = None
    info["agent_since"] = since
    if since and since != prev.get("agent_since"):
        info["agent_since_ts"] = time.time()
    for k in _HB_PRENASENA:
        if info.get(k) is None and prev.get(k) is not None:
            info[k] = prev[k]
    # Agent, ktery jen tepe a NIKDY se nezeptal na praci, je stejne
    # zaseknuty jako ten, co prestal - jen o nem nemame zadny poll, se
    # kterym bychom cas porovnali. Zaznamename si tedy, odkdy tep chodi
    # bez pollu (presne stav po vecernim vypadku 2026-09-09).
    if info.get("poll_ts"):
        info.pop("poll_missing_since", None)     # uz mame s cim porovnavat
    elif not info.get("poll_missing_since"):
        info["poll_missing_since"] = time.time()

    # Teplota GPU (Robert 2026-09-11) - historie a prah/hystereze upozorneni
    # zijou tady, ne v agentovi (viz komentar u GPU_HISTORIE_MAX). Cela
    # partie v samostatnem try/except ze stejneho duvodu jako OSError nize:
    # tep je diagnostika, chyba v NOVEM kodu nesmi shodit zapis, na kterem
    # visi skutecny poll.
    try:
        historie = list(prev.get("gpu_historie") or [])
        if info.get("gpu_temp_c") is not None:
            historie.append({"ts": info.get("ts") or time.time(),
                             "teplota_c": info["gpu_temp_c"],
                             "zatizeni_pct": info.get("gpu_util_pct"),
                             "takt_mhz": info.get("gpu_clock_mhz")})
            historie = historie[-GPU_HISTORIE_MAX:]
        info["gpu_historie"] = historie
        # Hystereze: upozorneni se zapise (log) jen na VZESTUPNOU hranu
        # (prekroceni prahu, kdyz predtim prekroceny NEbyl) - ne pri kazdem
        # tepu behem cele davky, a znovu az po navratu pod prah.
        predtim_prekroceno = bool(prev.get("gpu_prah_prekrocen"))
        prah = _gpu_teplota_prah_c()
        aktualne_prekroceno = (info.get("gpu_temp_c") is not None
                              and info["gpu_temp_c"] > prah)
        if aktualne_prekroceno and not predtim_prekroceno:
            app.logger.warning("GPU worker %s: teplota %s C prekrocila prah %s C",
                               info.get("name"), info.get("gpu_temp_c"), prah)
        info["gpu_prah_prekrocen"] = aktualne_prekroceno
        info["gpu_teplota_prah_c"] = prah
    except Exception:
        app.logger.warning("Zpracovani teploty GPU selhalo", exc_info=True)
        info["gpu_historie"] = prev.get("gpu_historie") or []
        info["gpu_prah_prekrocen"] = prev.get("gpu_prah_prekrocen", False)

    # Aktualni hodnota (pro dashboard/admin "ted") se doplni z predchoziho
    # zapisu AZ TADY - po historii/hysterezi vyse, ktere uz s puvodnim
    # (necarrieovanym) `info.get("gpu_temp_c")` spravne rozhodly, jestli
    # jde o cerstvy udaj. Kdyby carry-forward bezel drive (napr. pres
    # _HB_PRENASENA), kazdy poll bez cerstvych dat by vyrobil dalsi
    # (duplicitni) zaznam v historii - viz komentar u _HB_PRENASENA.
    for k in ("gpu_temp_c", "gpu_util_pct", "gpu_clock_mhz"):
        if info.get(k) is None and prev.get(k) is not None:
            info[k] = prev[k]

    tmp = "%s.tmp.%d" % (cesta_hb, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(info, fh)
        os.replace(tmp, cesta_hb)
    except OSError:
        # Tep je diagnostika - jeho selhani nesmi shodit poll, ktery na
        # nem jen mimochodem visi (prave to se 2026-09-09 stalo).
        app.logger.warning("Tep workera se nepodarilo zapsat", exc_info=True)
        try:
            os.remove(tmp)
        except OSError:
            pass


def _read_heartbeat(cesta=None):
    try:
        with open(cesta or _HEARTBEAT_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def worker_tepe():
    """Chodi tep? Sam o sobe NEZNAMENA, ze si agent bere praci."""
    hb = _read_heartbeat()
    return bool(hb) and (time.time() - hb.get("ts", 0)) < WORKER_ONLINE_S


def worker_zaseknuty():
    """Tep chodi, ale agent se dlouho neptal na praci.

    Presne stav z 2026-09-09 17:57-19:25: tep a 20 s, poll ani jeden.
    Behem renderu se poll NECEKA (Blender bezi klidne hodinu a agent se
    mezitim neptá) - proto se ptame i na to, jestli u nej neco bezi."""
    hb = _read_heartbeat() or {}
    if not worker_tepe():
        return False                     # offline neni zaseknuty
    # Bez jedineho pollu porovnavame s tim, odkdy chodi holy tep.
    od = (hb.get("poll_ts") or hb.get("poll_missing_since") or 0)
    if not od or time.time() - od <= WORKER_POLL_STALE_S:
        return False
    return not worker_busy()


def worker_online():
    """Pouziva i blender_render.py pri rozhodovani, kam ulohu poslat.
    Robert 2026-08-11: agent tepe z vlastniho vlakna i behem renderovani
    (driv se hlasil jen pri dotazu na praci, takze pri delsim renderu
    "zmizel" a dalsi uloha spadla na pomalejsi server).

    bot8 2026-09-09: "online" ted znamena TAKE "odebira praci" - zaseknuty
    agent (tep bez pollu) se chova jako vypnuty, aby uloha rovnou sla na
    server misto ceka ni na nekoho, kdo si ji nevezme."""
    return worker_tepe() and not worker_zaseknuty()


def worker_busy():
    """Bezi uz na workeru nejaka uloha? Pak dalsi POCKA (worker si ji
    vyzvedne, az dokonci tu soucasnou) misto okamziteho prepadnuti na
    server - GPU je i tak nekolikanasobne rychlejsi nez zdejsi CPU."""
    try:
        names = os.listdir(br.RENDER_OUT_DIR)
    except OSError:
        return False
    for name in names:
        if not name.endswith(".status.json"):
            continue
        st = br._read_status(name[:-len(".status.json")]) or {}
        # Ulohu na jinem stroji (notebook) sem NEpocitat - GPU stanice je
        # volna, dalsi ulohy bez cile na ni nemaji cekat.
        if (st.get("state") == "running" and st.get("on_worker")
                and je_vychozi_worker(st.get("worker_name"))):
            return True
    return False


def stav_workeru(jmeno):
    """Stav JEDNOHO stroje podle jeho vlastniho tepu: {jmeno, gpu, online, duvod}.
    online = tep cerstvy A agent si chodi pro praci (nebo prave renderuje) -
    stejne kriterium jako worker_online() u GPU stanice."""
    hb = _read_heartbeat(_hb_cesta(jmeno)) or {}
    if not hb:
        return {"jmeno": jmeno, "gpu": None, "online": False,
                "duvod": "zatím se nikdy nepřipojil"}
    stari = time.time() - (hb.get("ts") or 0)
    if stari >= WORKER_ONLINE_S:
        return {"jmeno": hb.get("name") or jmeno, "gpu": hb.get("gpu"), "online": False,
                "duvod": "nehlásí se %d min (agent neběží nebo je notebook uspaný)" % max(1, int(stari // 60))}
    od = hb.get("poll_ts") or hb.get("poll_missing_since") or 0
    if od and time.time() - od > WORKER_POLL_STALE_S:
        bezi = any(st.get("state") == "running" and st.get("on_worker")
                   and _jmeno_klic(st.get("worker_name")) == _jmeno_klic(jmeno)
                   for _j, st in _stavy_uloh())
        if not bezi:
            return {"jmeno": hb.get("name") or jmeno, "gpu": hb.get("gpu"), "online": False,
                    "duvod": "agent tepe, ale nebere si práci (zaseknutý)"}
    return {"jmeno": hb.get("name") or jmeno, "gpu": hb.get("gpu"), "online": True, "duvod": None}


def _jina_jmena_workeru():
    """Jmena vsech NEvychozich stroju, ktere se nekdy pripojily (soubory tepu)."""
    out = []
    try:
        names = sorted(os.listdir(br.RENDER_OUT_DIR))
    except OSError:
        return out
    for n in names:
        if not (n.startswith(".worker_heartbeat.") and n.endswith(".json")) or n == ".worker_heartbeat.json":
            continue
        hb = _read_heartbeat(os.path.join(br.RENDER_OUT_DIR, n)) or {}
        if hb.get("name") and not je_vychozi_worker(hb["name"]):
            out.append(hb["name"])
    return out


def prehled_cilu():
    """Kde jde ulohu renderovat: [{jmeno, vychozi, gpu, online, duvod}, ...],
    vychozi stroj (GPU stanice) prvni."""
    vychozi = stav_workeru(WORKER_VYCHOZI_JMENO)
    vychozi["jmeno"] = WORKER_VYCHOZI_JMENO
    vychozi["vychozi"] = True
    vychozi["nabidky"] = False
    out = [vychozi]
    for jmeno in _jina_jmena_workeru():
        st = stav_workeru(jmeno)
        st["vychozi"] = False
        st["nabidky"] = je_stroj_pro_nabidky(jmeno)    # na tomhle stroji se renderuji nabidky a testy ze sceny
        out.append(st)
    return out


@app.get("/api/admin/render-worker/cile")
@admin_required
def admin_render_worker_cile():
    """Vyber "kde renderovat" pro panel Rendering (bot4 2026-09-29)."""
    return jsonify({"cile": prehled_cilu()})


def _stavy_uloh():
    """[(job, stav), ...] pro vsechny ulohy ve fronte."""
    out = []
    try:
        names = sorted(os.listdir(br.RENDER_OUT_DIR))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".status.json"):
            continue
        job = name[:-len(".status.json")]
        st = br._read_status(job)
        if st:
            out.append((job, st))
    return out


def _uloha_na_workeru():
    """Prave bezici uloha NA WORKERU (ne lokalni CPU render) - detail pro
    admin panel (bot4, 2026-09-12, po dnesnim omylu "GPU spí/neslyším ho",
    ktery vedl k rucnimu restartu agenta UPROSTRED behu): "detail
    aktualne zpracovavane ulohy - sestava/produkt, cas od startu, samples,
    hdri_rotace_deg pokud nastaveno, expected_frames vs kolik realne
    zapsano" + "odznak v pripravne fazi, zadny postup zatim normalni".
    Vraci dict nebo None (nic nebezi)."""
    for job, st in _stavy_uloh():
        if (st.get("state") == "running" and st.get("on_worker")
                and je_vychozi_worker(st.get("worker_name"))):
            started = st.get("started")
            progress_ts = st.get("progress_ts")
            frames_written = st.get("frames_written") or 0
            return {
                "job": job,
                "assembly_id": st.get("assembly_id"),
                "assembly_name": st.get("assembly_name"),
                "shop_product_id": st.get("shop_product_id"),
                "elapsed_s": round(time.time() - started, 1) if started else None,
                "samples": st.get("samples"),
                "hdri_rotace_deg": st.get("hdri_rotace_deg"),
                "expected_frames": st.get("expected_frames"),
                "frames_written": frames_written,
                # Bezi, ale jeste nema zadny zaznamenany postup (zadny
                # snimek, zadny progress_ts) = normalni "jeste se
                # pripravuje" (nahrava sablonu, GLB, sklada scenu), NE
                # zaseknuty stav - presne tahle zamena dnes vedla k
                # zbytecnemu rucnimu restartu agenta.
                "priprava": not progress_ts and not frames_written,
            }
    return None


def _posledni_ulohy(n=5):
    """Poslednich N DOKONCENYCH uloh (done/error/cancelled), nejnovejsi
    prvni - bot4: "poslednich par dokoncenych uloh + render_seconds
    (kalibrace co je normalni)" + "text posledni chyby" +
    "is_active/ingest_bez_commitu stav u hotovych uloh".

    `is_active` jako samostatne pole v status.json NEEXISTUJE (to je
    vlastnost VYSLEDNYCH obrazku v katalogu, ne ulohy) - nejblizsi
    realny ekvivalent je `commit_pending` (cekaji snimky na aktivaci?)
    + volny text `note`, oboje uz `render_worker_tt_result` zapisuje."""
    hotove = [(job, st) for job, st in _stavy_uloh() if st.get("state") in ("done", "error", "cancelled")]
    hotove.sort(key=lambda t: t[1].get("updated") or 0, reverse=True)
    out = []
    for job, st in hotove[:n]:
        out.append({
            "job": job,
            "state": st.get("state"),
            "assembly_id": st.get("assembly_id"),
            "assembly_name": st.get("assembly_name"),
            "render_seconds": st.get("render_seconds"),
            "error": st.get("error"),
            "commit_pending": st.get("commit_pending"),
            "ingest_bez_commitu": st.get("ingest_bez_commitu"),
            "note": st.get("note"),
            "updated": st.get("updated"),
        })
    return out


@app.get("/api/admin/pipeline/render-overview")
@admin_required
def admin_pipeline_render_overview():
    """Zivy prehled render/GPU fronty pro Pipeline > Render/GPU diagram
    (bot16, 2026-09-12, Robert: "pipeline na vsechno co se deje v
    projektu", "musi to byt zivy pipeline odraz skutecneho stavu").

    Znovupouziva uz existujici _stavy_uloh()/worker_tepe() - stejny
    cti-jen zdroj jako api/system_pipeline.py (_check_render_jobs/
    _check_render_worker), jen jinak agregovany: podle STAVU jednotlivych
    uloh (waiting_worker/queued/running/done/error/cancelled), ne jen
    celkovy pocet + mtime posledniho souboru.
    """
    counts = {}
    for _job, st in _stavy_uloh():
        s = st.get("state") or "?"
        counts[s] = counts.get(s, 0) + 1
    hb = _read_heartbeat() or {}
    return jsonify({
        "counts": counts,
        "worker": {
            "online": worker_tepe(),
            "name": hb.get("name"),
            "gpu": hb.get("gpu"),
            "gpu_temp_c": hb.get("gpu_temp_c"),
        },
        # bot16, 2026-09-12 (bot4 zadani pres cross-session zpravu - Robert
        # se divá SEM, ne na Dashboard/gpuMonitorPanel, kam puvodne mirilo
        # zadani "detail aktualne zpracovavane ulohy"): stejna data jako
        # /api/admin/render-worker/status, znovupouzity uz existujici
        # _uloha_na_workeru()/_posledni_ulohy() - nic tu neduplikovano.
        "current_job": _uloha_na_workeru(),
        "recent_jobs": _posledni_ulohy(),
    })


def uklidit_mrtve_ulohy_workera():
    """Ulohy, ktere server porad vede jako "bezi na workerovi", i kdyz uz
    davno nebezi. Vraci seznam uklizenych ID.

    PROC TO NEZACHYTIL WORKER_NO_PROGRESS_S: ten hlida vlakno, ktere
    spousti VYHRADNE dispatch_to_worker_or_local() - tedy jen u uloh
    zarazenych pres Flask. Otocny nahled se zarazuje z prikazove radky
    (scripts/2026-09-09_turntable_render.py zamerne neimportuje aplikaci,
    aby sel z cronu), takze zadne hlidaci vlakno nikdy nevzniklo. A i u
    Flask uloh vlakno zmizi s kazdym respawnem gunicorn workera. Tahle
    kontrola je proto SOUBOROVA a bezstavova - prezije restart i to, ze
    ulohu zaradil uplne jiny proces.

    PRODUKTOVE_RENDERY.md, pravidlo 5 ("pred zrusenim zjisti, jestli uz
    nebezi nebo nedobehl"): nic se nemaze, stav se prepisuje jen na
    "error". Kdyby vysledek presto dorazil, tt-result/result ho prijmou
    (odmita se jen stav "cancelled") a uloha skonci jako "done".
    """
    now = time.time()
    uklizeno = []
    # Cilena uloha (test render "kde renderovat" = notebook): kdyz se cilovy
    # stroj neozve, uloha by cekala navzdy A blokovala testovaci kartu i pro
    # GPU stanici. Hlasite selhani po WORKER_CIL_CEKANI_S, ne tiche cekani -
    # a NIKDY ne prevzeti jinym strojem (Robert si vybral konkretni).
    for job, st in _stavy_uloh():
        cil = st.get("target_worker")
        if st.get("state") != "waiting_worker" or not cil:
            continue
        od = st.get("queued_at") or st.get("updated") or now
        if now - od < WORKER_CIL_CEKANI_S:
            continue
        stav = stav_workeru(cil)
        if stav["online"]:
            continue
        br._write_status(job, state="error",
                         error="Cílový stroj '%s' se do %d min nepřihlásil (%s). Zapni ho a spusť test znovu."
                         % (cil, WORKER_CIL_CEKANI_S // 60, stav["duvod"]))
        app.logger.warning("Cilena uloha %s zrusena: stroj %s offline", job, cil)
        uklizeno.append(job)
    for job, st in _stavy_uloh():
        if st.get("state") != "running" or not st.get("on_worker"):
            continue
        # Restart agenta se posuzuje podle tepu TOHO stroje, na kterem uloha
        # bezi (notebook ma svuj soubor) - restart GPU stanice nesmi zabit
        # ulohu na notebooku a naopak.
        hb = _read_heartbeat(_hb_cesta(st.get("worker_name"))) or {}
        agent_od = hb.get("agent_since_ts") or 0
        posledni = max(st.get("progress_ts") or 0, st.get("started") or 0,
                       st.get("updated") or 0)
        ticho = now - posledni
        if ticho < WORKER_MIN_ALIVE_S:
            continue
        # Dukaz c. 1: agent se od zacatku ulohy restartoval (hlasi jiny
        # cas startu, nez kdyz ulohu prebiral) - u nej uz nebezi nic.
        po_restartu = bool(agent_od) and (st.get("started") or 0) < agent_od
        if not po_restartu and ticho < WORKER_STALE_RUNNING_S:
            continue    # dukaz c. 2: dlouho ani hlasku o postupu
        duvod = ("Agent na GPU stanici se mezitím restartoval - render u něj "
                 "už neběží." if po_restartu else
                 "Worker se %d min neozval, render u něj nejspíš spadl."
                 % (WORKER_STALE_RUNNING_S // 60))
        br._write_status(job, state="error", error=duvod + " Zařaď render znovu.")
        app.logger.warning("Uklizena mrtva uloha workera %s: %s", job, duvod)
        uklizeno.append(job)
    return uklizeno


def _fronta_serveru_volna():
    """Bezi/ceka uz na TOMHLE serveru nejaky render? Prebirat druhy nema
    smysl - fronta je stejne jen jednomistna (QUEUE_LOCK_PATH) a druhy by
    jen cekal, az mu vyprsi QUEUE_WAIT_TIMEOUT_S a spadl na chybu."""
    for _job, st in _stavy_uloh():
        if st.get("state") in ("queued", "running") and not st.get("on_worker"):
            return False
    return True


def prevzit_opustenou_ulohu():
    """Uloha, kterou si worker v rozumne dobe nevyzvedl, se dorenderuje
    na serveru (CPU). Vraci ID prevzate ulohy nebo None.

    Robert 2026-09-09 pres bot3: "k agentovi na mem PC nemame pristup,
    takze 'restartuj agenta' nesmi byt reseni, ktere pipeline potrebuje."
    Uloha zarazena z prikazove radky sla dosud rovnou do "waiting_worker"
    a NIKDO ji nehlidal - kdyz si ji agent nevzal, visela navzdy. Tohle
    je tentyz zachranny mechanismus, jaky uz mely ulohy zarazene pres
    Flask (watchdog v dispatch_to_worker_or_local), jen souborovy, takze
    plati pro VSECHNY ulohy bez ohledu na to, kdo je zaradil.

    Server je proti GPU pomaly (otocny nahled = hodiny), proto je to
    ZACHRANA, ne vychozi cesta: prebira se az po WORKER_TAKEOVER_S, jen
    jedna uloha naraz a nikdy ve chvili, kdy worker zjevne pracuje.
    """
    if not _fronta_serveru_volna():
        return None
    # Worker prave renderuje neco jineho -> ostatni ulohy at pockaji na
    # GPU (stejna uvaha jako ve watchdogu dispatch_to_worker_or_local).
    if worker_online() and worker_busy():
        return None
    now = time.time()
    cekajici = [(st.get("queued_at") or st.get("updated") or now, job, st)
                for job, st in _stavy_uloh() if st.get("state") == "waiting_worker"]
    cekajici.sort()
    for od, job, st in cekajici:
        if now - od < WORKER_TAKEOVER_S:
            continue
        cfg_path = os.path.join(br.RENDER_OUT_DIR, f"{job}.json")
        out_path = os.path.join(br.RENDER_OUT_DIR, f"{job}.png")
        if not os.path.exists(cfg_path):
            br._write_status(job, state="error",
                             error="Konfigurace úlohy chybí, nelze ji převzít na server.")
            continue
        # ⭐ OTOCNY NAHLED SE NA CPU NEPREBIRA (bot8 2026-09-11, nasel bot4).
        #
        # Dva duvody, oba zmerene dnes, ne teoreticke:
        #  1. `br._run_render_job` u otocky pri uspechu zapise state="done"
        #     BEZ INGESTU (blender_render.py: "ten si vysledky uklada vlastni
        #     cestou" - to uz neplati). Snimky by zustaly ve slozce a v DB by
        #     byla nula radku, tedy PRESNE ten stav, kvuli kteremu vznikl
        #     commit 3adf36f6, jen jinou cestou. Dnes se to spustilo dvakrat
        #     u sestavy 333; skoda nevznikla jen proto, ze obe ulohy zabil
        #     restart sluzby.
        #  2. Ten restart je druhy duvod: CPU render bezi ve VLAKNE weboveho
        #     workera, takze ho kazdy deploy zabije. Dnes se to stalo dvakrat
        #     za 35 minut. Plna davka je na CPU navic na hodiny, tedy o rad
        #     dele, nez jak dlouho tady vydrzi beh bez restartu - takhle by
        #     se nedokoncila nikdy.
        #
        # Prilepit sem ingest by zachranilo bod 1, ale ne bod 2: zustala by
        # zachranna cesta, ktera svuj vysledek spolehlive znici. Uloha proto
        # radeji ceka na GPU - a ve stavu je videt, ze ceka a proc.
        if st.get("job_type") == "turntable":
            # Poznamka se zapisuje JEN JEDNOU. `_write_status` neni merge -
            # nese jen sticky klice, takze opakovany zapis by pri kazdem
            # pruchodu dozorce zahodil `queued_at` a uloha by se navzdy
            # tvarila jako cerstve zarazena.
            if not (st.get("note") or "").startswith("Čeká na GPU"):
                br._write_status(job, state="waiting_worker", queued_at=od,
                                 note="Čeká na GPU workera. Otočný náhled se na server (CPU) "
                                      "záměrně nepřebírá - běžel by ve vlákně webového workeru, "
                                      "takže by ho zabil první restart služby.")
            continue
        pozn = ("Worker si úlohu %d min nevyzvedl - přebírá ji server (CPU, "
                "pomalejší než GPU)." % (WORKER_TAKEOVER_S // 60))
        br._write_status(job, state="queued", note=pozn, taken_over_at=now)
        app.logger.warning("Uloha %s prebrana na server: %s", job, pozn)
        threading.Thread(target=br._run_render_job, args=(job, cfg_path, out_path),
                         name=f"prevzato-{job[:8]}", daemon=True).start()
        return job
    return None


def _dozorce_fronty():
    """Jedina periodicka kontrola fronty. Bezi v obou gunicorn workerech,
    proto souborovy zamek (flock) - jinak by ulohu mohli prevzit oba
    najednou a spustit dva Blendery na tutez praci."""
    import fcntl
    time.sleep(SUPERVISOR_FIRST_TICK_S)
    while True:
        try:
            fh = open(_SUPERVISOR_LOCK_PATH, "a")
        except OSError:
            time.sleep(SUPERVISOR_TICK_S)
            continue
        try:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue        # kontroluje prave druhy proces
            uklidit_mrtve_ulohy_workera()
            prevzit_opustenou_ulohu()
        except Exception:       # noqa: BLE001 - dozorce nesmi umrit potichu
            app.logger.exception("Dozorce renderovaci fronty spadl")
        finally:
            try:
                fcntl.flock(fh, fcntl.LOCK_UN)
            except OSError:
                pass
            fh.close()
            time.sleep(SUPERVISOR_TICK_S)


# Prvni kontrola az za SUPERVISOR_FIRST_TICK_S - modul importuji i kratke
# skripty z prikazove radky (pres `import app`) a ty nemaji frontu resit;
# dozivou driv, nez vlakno vubec poprve nadechne.
threading.Thread(target=_dozorce_fronty, name="render-dozorce", daemon=True).start()


# Robert 2026-09-09: "pc kde sedi nase GPU je s IP: 81.162.200.49".
# ZAMERNE se na tu IP neblokuje - kdyby se mu zmenila (dynamicka IP,
# jina sit, VPN), rendery by tise prestaly jezdit a nikdo by nevedel proc.
# Autentizacni hranice je a zustava token; tohle je jen kontrola v prehledu
# ("hlasi se ocekavany stroj?"), aby slo poznat stary notebook od noveho
# GPU pocitace. Prazdna hodnota = kontrola vypnuta.
EXPECTED_WORKER_IP = (os.environ.get("RENDER_WORKER_EXPECTED_IP") or "").strip()


def _worker_info():
    hb = _read_heartbeat() or {}
    ip = hb.get("ip")
    zaseknuty = worker_zaseknuty()
    expected_version = _expected_agent_version()
    return {
        "online": worker_online(),
        # bot8 2026-09-09: tri stavy misto dvou - "zaseknuty" je agent,
        # kteremu tluce tep, ale nebere si praci (viz worker_zaseknuty).
        "state": "stuck" if zaseknuty else ("online" if worker_tepe() else "offline"),
        "stuck": zaseknuty,
        "name": hb.get("name"),
        "gpu": hb.get("gpu"),
        "ip": ip,
        "expected_ip": EXPECTED_WORKER_IP or None,
        "ip_matches": (None if not (EXPECTED_WORKER_IP and ip) else ip == EXPECTED_WORKER_IP),
        "last_seen_s": round(time.time() - hb["ts"], 1) if hb.get("ts") else None,
        "last_poll_s": round(time.time() - hb["poll_ts"], 1) if hb.get("poll_ts") else None,
        "busy": worker_busy(),
        # Teplota/zatizeni/takt/otacky GPU (Robert 2026-09-11: "chci videt
        # zive v adminu teplotu PC GPU karty a rychlost ventilatoru") -
        # hodnoty uz `_write_heartbeat()` uklada, tady se jen posilaji dal
        # do admin panelu. `gpu_fan_pct` bot9 teprve doplnuje do agenta -
        # dokud chybi, `hb.get()` vrati None a frontend to musi ukazat
        # jako "nehlasi", nikdy jako 0.
        "gpu_temp_c": hb.get("gpu_temp_c"),
        "gpu_util_pct": hb.get("gpu_util_pct"),
        "gpu_clock_mhz": hb.get("gpu_clock_mhz"),
        "gpu_fan_pct": hb.get("gpu_fan_pct"),
        "gpu_teplota_prah_c": hb.get("gpu_teplota_prah_c"),
        "gpu_prah_prekrocen": hb.get("gpu_prah_prekrocen"),
        "gpu_historie": hb.get("gpu_historie") or [],
        # Verze agenta (bot9, commit 01ebcd2f - "version" v tepu chodi, ale
        # /api/admin/render-worker/status ho nikdy neposilal dal). Stejny
        # vzor jako ip/expected_ip/ip_matches vyse - "je to stary agent?"
        # je dalsi zdroj "GPU teplota se nehlasi", ktery Robert/bot3
        # chteli umet odlisit od stanice offline.
        "version": hb.get("version"),
        "expected_version": expected_version,
        "version_matches": (None if not (expected_version and hb.get("version"))
                            else hb.get("version") == expected_version),
    }


def _expected_agent_version():
    try:
        _raw, meta = _agent_meta()
        return meta.get("version")
    except OSError:
        return None


def _require_token():
    if not WORKER_TOKEN:
        return jsonify({"error": "Worker není na serveru nakonfigurovaný (chybí RENDER_WORKER_TOKEN)."}), 503
    # compare_digest - konstantni cas, at nejde token odhadovat po znacich
    if not hmac.compare_digest(request.headers.get("X-Worker-Token") or "", WORKER_TOKEN):
        return jsonify({"error": "Neplatný worker token."}), 401
    return None


def _valid_job(job):
    return job.isalnum() and len(job) == 32


# ---------------------------------------------------------------- agent API

@app.post("/api/render-worker/heartbeat")
def render_worker_heartbeat():
    err = _require_token()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    _write_heartbeat({
        "ts": time.time(),
        "name": str(body.get("name") or "worker")[:60],
        "gpu": str(body.get("gpu") or "?")[:120],
        # Robert 2026-09-09 ("jak detekujeme novy PC s GPU?", "pres IP ne?"):
        # IP se k NICEMU neoveruje - autentizace je token, identita je
        # hostname, worker se pripojuje SAM ven (proto funguje za NATem
        # i s menici se IP, bez portu a bez firewallu na jeho strane).
        # Ukladame ji jen jako DIAGNOSTIKU do prehledu, at je poznat, ze
        # se hlasi opravdu ocekavany stroj a ne stary notebook.
        "ip": _client_ip(),
        # cas startu agenta podle jeho hodin - viz _write_heartbeat
        "agent_since": body.get("since"),
        # PRIMY signal verze (bot3 2026-09-11: "hlasi agent svoji verzi
        # nekam, kde ji vidim?"). POZOR - agent uz tohle pole posilal od
        # d48aaab2 (heartbeat_loop()), ale tenhle handler ho do ted
        # nikdy necetl z `body` (jen carka doslova zmizela) - proto tep
        # verzi nikdy nemel, i kdyz agent ji poctive posilal. Bez tohohle
        # radku nejde poznat, ktera verze doopravdy bezi na stanici, ke
        # ktere se boti nedostanou jinak (viz bot3 2026-09-11: tri
        # neuspesne pokusy o nasazeni beze zpetne vazby).
        "version": str(body.get("version") or "")[:40],
        # Teplota/zatizeni/takt GPU (Robert 2026-09-11) - agent posila
        # cisla, kdyz je `nvidia-smi` precetl, jinak klic vubec neposle.
        # `_bezpecne_cislo` nedovoli, aby zvlastni/poskozeny udaj od
        # agenta shodil tep celeho workera.
        "gpu_temp_c": _bezpecne_cislo(body.get("gpu_temp_c")),
        "gpu_util_pct": _bezpecne_cislo(body.get("gpu_util_pct")),
        "gpu_clock_mhz": _bezpecne_cislo(body.get("gpu_clock_mhz")),
    })
    return jsonify({"status": "ok"})


@app.get("/api/render-worker/poll")
def render_worker_poll():
    err = _require_token()
    if err:
        return err
    # poll=True zapise i `poll_ts` - jediny udaj, podle ktereho jde
    # poznat, ze si agent OPRAVDU chodi pro praci (tep to nedokazuje,
    # viz komentar u WORKER_POLL_STALE_S).
    volajici = request.args.get("name", "worker")[:60]
    _write_heartbeat({
        "ts": time.time(),
        "name": volajici,
        "gpu": request.args.get("gpu", "?")[:120],
        "ip": _client_ip(),   # jen diagnostika, viz /heartbeat vyse
        "agent_since": request.args.get("since"),
    }, poll=True)
    try:
        names = os.listdir(br.RENDER_OUT_DIR)
    except OSError:
        return jsonify({"job": None})

    # bot3 2026-09-25, po nalezu #4587/#4593 (radove hodiny ve fronte -
    # skutecne 22 uloh, 74-438 min, ne jen ty 2 znama): puvodni kod bral
    # PRVNI "waiting_worker" podle sorted() NAZVU SOUBORU, tedy podle
    # NAHODNEHO UUID, ne podle poradi zarazeni - uloha s "pozdnim" UUID
    # (napr. "fc...") mohla cekat hodiny, zatimco fronty s "drivejsim"
    # UUID prubezne vyhravaly. Oprava: skutecne FIFO podle queued_at.
    # Chybejici/stare queued_at (uloha z pred zavedenim pole) = 0 =
    # nejstarsi - NIKDY na konec, to by ji poskodilo stejnym zpusobem.
    cekajici = []
    for name in names:
        if not name.endswith(".status.json"):
            continue
        job = name[:-len(".status.json")]
        st = br._read_status(job) or {}
        if st.get("state") != "waiting_worker":
            continue
        # bot4 2026-09-29: uloha s cilem (`target_worker`) jde JEN tomu
        # stroji; uloha bez cile JEN vychozimu (GPU stanice) - notebook si
        # produkci nikdy nevezme, ani kdyz agent bezi.
        cil = st.get("target_worker")
        if cil:
            if _jmeno_klic(cil) != _jmeno_klic(volajici):
                continue
        elif not je_vychozi_worker(volajici):
            continue
        cekajici.append((st.get("queued_at") or 0, job, st))
    cekajici.sort(key=lambda t: t[0])

    for _, job, st in cekajici:
        # Vyzvednuto - prepnout na "running", aby ji nevzal nikdo jiny
        # ani nezacal renderovat server (viz watchdog nize).
        br._write_status(job, state="running", started=time.time(), on_worker=True,
                         worker_name=request.args.get("name", "worker")[:60])
        try:
            with open(os.path.join(br.RENDER_OUT_DIR, f"{job}.json"), "r", encoding="utf-8") as fh:
                settings = json.load(fh)
        except (OSError, ValueError):
            br._write_status(job, state="error", error="Konfigurace úlohy chybí.")
            continue

        # Robert 2026-09-09 ("udelej rozšíření na .blend pro renderování
        # automaticke na gpu v síti") - druhy typ ulohy vedle "glb+skript":
        # syrovy .blend soubor ze Sdileneho disku, renderovany PRESNE tak,
        # jak si ho ulozil (vlastni kamera/material/engine/vzorky uvnitr) -
        # zadny blender_render_scene.py, zadne GLB. Worker pozna typ podle
        # "job_type" a stahne jen jeden soubor (viz render_worker_blend nize).
        if settings.get("job_type") == "blend":
            return jsonify({"job": {
                "job_id": job,
                "job_type": "blend",
                # Robert 2026-09-09 ("nechceme to samotne pozadi hdri
                # videt, slouzi pouze pro odlesky") - JEDINY zasah do
                # jinak nedotcenych nastaveni souboru. Samotny .blend na
                # Sdilenem disku se NEPREPISUJE, prepinac se aplikuje az
                # na stazenou kopii u workera (viz run_blend_job).
                "settings": {"hdri_as_background": bool(settings.get("hdri_as_background", False))},
                "blend_url": f"/api/render-worker/job/{job}/blend",
            }})

        # Robert 2026-09-09 - treti typ ulohy: CELY otocny nahled sestavy
        # (162 snimku prstencu + 5 stills) z jedne sceny. Worker si stahne
        # job JSON, unikatni .glb dilu (128 dilu byva jen ~9 ruznych
        # souboru - proto klice, ne 128 URL) a volitelnou sablonu; vysledek
        # vraci jako JEDEN ZIP, ne 167 POSTu. Viz PRODUKTOVE_RENDERY.md.
        if settings.get("job_type") == "turntable":
            all_glb = _tt_all_glb_paths(settings)
            # Karoserie je DOPLNEK, ne podminka (Robert/bot3 2026-09-11,
            # po padu renderu na chybejicim souboru) - kdyz stazeni
            # nektereho z jejich .glb selze, uloha ma pokracovat bez ni,
            # ne skoncit. Dily sestavy zustavaji povinne jako dosud.
            kar_keys = {os.path.basename(p) for p in
                        ((settings.get("karoserie_odraz") or {}).get("glb_files") or [])}
            keys = sorted(all_glb.keys())
            return jsonify({"job": {
                "job_id": job,
                "job_type": "turntable",
                "settings": {},
                "job_url": f"/api/render-worker/job/{job}/tt-job",
                "script_url": "/api/render-worker/tt-script",
                "template_url": (f"/api/render-worker/job/{job}/tt-template"
                                 if settings.get("template_blend") else None),
                # VD_ material knihovna (bot4 2026-09-21, nativni_material
                # vetev/vanDrawee) - stejny vzor jako template_url vyse,
                # jen kdyz uloha ma co poslat (settings.get("vd_materialy_blend")
                # nastavuje scripts/2026-09-09_turntable_render.py, jen pro
                # ulohy s aspon jednim nativni_material dilem).
                "vd_materialy_url": (f"/api/render-worker/job/{job}/tt-vd-materialy"
                                     if settings.get("vd_materialy_blend") else None),
                # bot4 2026-09-13 (Robert: "aby diakritika nebyla znovu
                # problem"): "k" je zakladni jmeno souboru na disku
                # (_tt_all_glb_paths, os.path.basename) a muze obsahovat
                # cokoli, co tam davá katalog/dodavatel - dnes to shodilo
                # render na "Citroën_*.glb" (agent na Windows nedokazal
                # zakodovat "ë" do ASCII HTTP request radku). Prejmenovani
                # konkretnich souboru (viz backups/2026-09-13_citroen_
                # filename_fix/) resi JEN dnesni pripady, ne cely druh
                # chyby - proto navic urllib.parse.quote() v URL, at
                # JAKYKOLI budouci znak (diakritika, mezera, #, ?, ...)
                # zustane bezpecny bez ohledu na to, jestli nekdo soubor
                # prejmenuje. `key` v odpovedi zustava PUVODNI (neenkodovane)
                # jmeno - to je "human" identifikator, kterym agent hlasi
                # pruebeh (vypis()); jen URL cesta se koduje. Flask cestu
                # automaticky dekoduje zpet, takze `_tt_all_glb_paths(st).get(key)`
                # v render_worker_tt_glb() dostane puvodni "k" beze zmeny.
                "glb_files": [{"key": k, "url": f"/api/render-worker/job/{job}/tt-glb/{urllib.parse.quote(k, safe='')}",
                               "required": k not in kar_keys}
                              for k in keys],
                "result_url": f"/api/render-worker/job/{job}/tt-result",
            }})

        # Cesty k souborum na SERVERU nahradit stahovacimi odkazy - worker
        # si je stahne k sobe a cesty si prepise sam.
        assets = []
        if settings.get("hdri_path"):
            assets.append({"key": "hdri", "role": None, "url": f"/api/render-worker/job/{job}/asset/hdri"})
        for role in sorted((settings.get("textures") or {}).keys()):
            assets.append({"key": f"tex:{role}", "role": role,
                           "url": f"/api/render-worker/job/{job}/asset/tex/{role}"})
        safe_settings = {k: v for k, v in settings.items()
                         if k not in ("hdri_path", "textures", "glb_path", "output_path", "preview_path")}
        return jsonify({"job": {
            "job_id": job,
            "job_type": "glb",
            "settings": safe_settings,
            "model_url": f"/api/render-worker/job/{job}/model",
            "script_url": "/api/render-worker/script",
            "assets": assets,
        }})
    return jsonify({"job": None})


def _blend_ve_povolene_slozce(path):
    """Smi se agentovi poslat tenhle .blend?

    Robert 2026-09-09 (log agenta: "nepodarilo se stahnout .blend soubor:
    400"): puvodni kontrola pustila JEN soubory ze Sdileneho disku
    (DRIVE_FILES_DIR). Renderovat se ale posila PRIPRAVENA KOPIE sablony
    (zabalene HDRI/textury, viz priprav_sablonu.py), ktera lezi v
    RENDER_OUT_DIR - ta se proto vzdy odmitla a uloha umrela jeste nez
    zacala. Povolene jsou tedy obe slozky; obe zaklada a plni aplikace,
    cesta do nich nikdy neprijde od uzivatele.

    Zaroven opraveno deravé porovnani: `startswith` bez oddelovace
    propousti i sourozence se stejnym prefixem (realne se to stalo -
    ".../private-files/shared-drive-named/..." proslo jako by bylo uvnitr
    ".../private-files/shared-drive"). Proto commonpath.
    """
    try:
        skutecna = os.path.realpath(path)
    except OSError:
        return False
    for zaklad in (br.DRIVE_FILES_DIR, br.RENDER_OUT_DIR):
        try:
            if os.path.commonpath([skutecna, os.path.realpath(zaklad)]) == os.path.realpath(zaklad):
                return True
        except ValueError:      # ruzne disky/nesrovnatelne cesty
            continue
    return False


@app.get("/api/render-worker/job/<job>/blend")
def render_worker_blend(job):
    """Syrovy .blend soubor pro job_type=blend (viz render_worker_poll) -
    stejna ochrana proti podvrzene ceste jako u render_worker_asset."""
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    try:
        with open(os.path.join(br.RENDER_OUT_DIR, f"{job}.json"), "r", encoding="utf-8") as fh:
            settings = json.load(fh)
    except (OSError, ValueError):
        return jsonify({"error": "Konfigurace úlohy chybí."}), 404
    path = settings.get("blend_path")
    if not path or not _blend_ve_povolene_slozce(path):
        return jsonify({"error": "Neplatná cesta k .blend souboru."}), 400
    if not os.path.exists(path):
        return jsonify({"error": ".blend soubor nenalezen."}), 404
    return send_file(path, mimetype="application/octet-stream", as_attachment=True, download_name="scene.blend")


# ---------------------------------------------- otocny nahled (turntable)

def _tt_settings(job):
    """Konfigurace turntable ulohy, nebo (None, chybova odpoved)."""
    try:
        with open(os.path.join(br.RENDER_OUT_DIR, f"{job}.json"), "r", encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        return None, (jsonify({"error": "Konfigurace úlohy chybí."}), 404)
    if st.get("job_type") != "turntable":
        return None, (jsonify({"error": "Úloha není typu turntable."}), 400)
    return st, None


def _tt_all_glb_paths(settings):
    """basename -> absolutni cesta na serveru, pro VSECHNY .glb ulohy -
    dily sestavy I karoserii (settings["karoserie_odraz"]["glb_files"],
    bot3 2026-09-11: render spadl, protoze karoserie se do tohohle
    seznamu nedostala - stavela se jako vyjimka mimo existujici prenosovy
    mechanismus misto aby se do nej zapojila). Jedno misto pro vsechny 3
    endpointy nize (poll/tt-job/tt-glb), aby se znova nerozjely."""
    out = {}
    for pt in (settings.get("parts") or []):
        if pt.get("glb"):
            out[os.path.basename(pt["glb"])] = pt["glb"]
    for p in ((settings.get("karoserie_odraz") or {}).get("glb_files") or []):
        out[os.path.basename(p)] = p
    return out


@app.get("/api/render-worker/tt-script")
def render_worker_tt_script():
    """Renderovaci skript otocneho nahledu - stejny princip jako
    /script vyse: agent nikdy nema zastaralou verzi."""
    err = _require_token()
    if err:
        return err
    return send_file(br.TURNTABLE_SCRIPT, mimetype="text/x-python",
                     as_attachment=False, download_name="blender_render_turntable.py")


@app.get("/api/render-worker/job/<job>/tt-job")
def render_worker_tt_job(job):
    """Job JSON s cestami prepsanymi na KLICE (basename .glb). Worker si
    dosadi vlastni lokalni cesty - absolutni cesty na serveru mu jsou
    k nicemu a nemel by je ani videt."""
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    st, bad = _tt_settings(job)
    if bad:
        return bad
    out = dict(st)
    out["parts"] = [dict(pt, glb_key=os.path.basename(pt["glb"]), glb=None)
                    for pt in (st.get("parts") or [])]
    # Karoserie (bot3 2026-09-11: render spadl - "Please select a file" -
    # protoze absolutni cesty ze serveru se sem drive nedostaly vubec,
    # worker dostal nic). Stejny vzor jako u parts: klice, ne cesty.
    #
    # DRUHY PAD (bot3, tyz den): "glb_files" se tu prepisovalo na `None`
    # (ne na []) - o krok dal (render_worker_agent.py/blender_render_
    # turntable.py) `.get("glb_files", [])` cetlo tenhle `None` misto
    # vychoziho [] (default u .get() plati JEN kdyz klic chybi, ne kdyz
    # je ulozeny jako null - stejna past jako u price_summary z rana).
    # Null je treti stav, ne "chybi" - vracet [] rovnou.
    kar = dict(st.get("karoserie_odraz") or {})
    if kar.get("glb_files"):
        kar["glb_keys"] = [os.path.basename(p) for p in kar["glb_files"]]
        kar["glb_files"] = []
    out["karoserie_odraz"] = kar
    for k in ("template_blend", "vd_materialy_blend", "out_dir"):
        out.pop(k, None)
    return jsonify(out)


@app.get("/api/render-worker/job/<job>/tt-glb/<key>")
def render_worker_tt_glb(job, key):
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    st, bad = _tt_settings(job)
    if bad:
        return bad
    # Klic se NEsklada do cesty - hleda se mezi soubory ulohy (dily I
    # karoserie, viz _tt_all_glb_paths), takze projit muze jen soubor,
    # ktery uloha opravdu pouziva (zadne ../).
    path = _tt_all_glb_paths(st).get(key)
    if not path or not os.path.exists(path):
        return jsonify({"error": "Díl úlohy nenalezen."}), 404
    return send_file(path, mimetype="model/gltf-binary",
                     as_attachment=True, download_name=key)


@app.get("/api/render-worker/job/<job>/tt-template")
def render_worker_tt_template(job):
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    st, bad = _tt_settings(job)
    if bad:
        return bad
    path = st.get("template_blend")
    if not path or not os.path.exists(path):
        return jsonify({"error": "Šablona úlohy nenalezena."}), 404
    return send_file(path, mimetype="application/octet-stream",
                     as_attachment=True, download_name="template.blend")


@app.get("/api/render-worker/job/<job>/tt-vd-materialy")
def render_worker_tt_vd_materialy(job):
    """VD_ material knihovna pro nativni_material vetev (vanDrawee) -
    stejny vzor jako render_worker_tt_template vyse, jen jiny soubor a
    jine nastaveni (vd_materialy_blend, viz render_worker_tt_job)."""
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    st, bad = _tt_settings(job)
    if bad:
        return bad
    path = st.get("vd_materialy_blend")
    if not path or not os.path.exists(path):
        return jsonify({"error": "VD material knihovna úlohy nenalezena."}), 404
    return send_file(path, mimetype="application/octet-stream",
                     as_attachment=True, download_name="vd_materialy.blend")


def _smaz_tt_nahled(job):
    """Uklidi prubezny nahled otocky (<job>.preview.jpg) - volat pri KAZDEM
    konci ulohy (uspech i chyba), aby se na disku nehromadily. Best-effort,
    stejny princip jako zbytek modulu: chybejici soubor neni chyba."""
    for suf in (".preview.jpg", ".preview.jpg.tmp.jpg"):
        try:
            os.remove(os.path.join(br.RENDER_OUT_DIR, job + suf))
        except OSError:
            pass


# Jen jednou za beh procesu (ne na kazdy snimek - davka ma desitky) - viz
# pouziti nize. bot4 2026-09-11: chybejici funkce byla PRICINOU tříhodinoveho
# vypadku archivace (11:44-15:11, Robert se ptal 3x proc se nic neuklada) -
# duck-typed volani ticho zamyslene nespadne, ale to tise POKRACOVAT nesmi
# byt NEME. Restart procesu VZDY vyprazdni tenhle flag (je to promenna v
# pameti, ne v souboru), takze po nasazeni chybejici funkce se varovani
# spravne znovu objevi, dokud se proces nerestartuje.
_ARCHIV_FN_VAROVANI_VYPSANO = False


@app.post("/api/render-worker/job/<job>/tt-frame")
def render_worker_tt_frame(job):
    """PRUBEZNY master snimek otocky, poslany agentem HNED po dorenderovani
    jednoho snimku - NE cela davka na konci (Robert pres bot3, 2026-09-11:
    "musime videt rendery prubezne pro kontrolu" / "hotove rendery je musi
    po jednom hned ukladat do sdileneho disku"). Bez tohohle Robert neuvidel
    ani jeden snimek 81-snimkove davky, dokud nedobehla cela - spatne
    nastavena davka (material/svetlo/orez/chybejici razitko) se pozna az po
    hodine a pul misto na patem snimku.

    Dve nezavisle veci, obe best-effort (spatny/chybejici snimek NESMI
    shodit bezici render):
      1. <job>.preview.jpg - stejny mechanismus jako u GLB uloh
         (blender_render_status cte preview_mtime/preview), prehled uloh tak
         umi ukazat posledni hotovy snimek bez zvlastniho kodu na strane UI.
      2. progresivni zapis na Sdileny disk pres turntable_archiv - DUCK
         TYPED (`getattr(..., "archivuj_snimek", None)`), protoze presne
         tvar te funkce je domluveny s bot16 (mail-relay-7c) a muze pribyt
         AZ PO tomhle commitu. Kdyz funkce jeste neexistuje, endpoint jen
         zapise thumbnail a ticho pokracuje - zadny redeploy tu pak nebude
         potreba, aktivuje se to samo.

    NENI to prijata davka: soubor sem prichazejici NEJDE do
    product_turntable_frames a nejde primo na web - to porad dela jen
    /tt-result (cely ZIP) + ingest."""
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    try:
        el = int(request.args.get("el"))
        az = int(request.args.get("az"))
        tier = int(request.args.get("tier"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí nebo neplatné el/az/tier."}), 400
    data = request.get_data()
    if not data or data[:3] != b"\xff\xd8\xff" or len(data) > 8 * 1024 * 1024:
        return jsonify({"error": "Očekávám JPEG (max 8 MB)."}), 400
    st = br._read_status(job)
    if not st:
        return jsonify({"error": "Úloha neexistuje."}), 404

    preview = os.path.join(br.RENDER_OUT_DIR, f"{job}.preview.jpg")
    tmp = preview + ".tmp.jpg"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, preview)

    archiv = None
    assembly_id = st.get("assembly_id")
    if assembly_id:
        try:
            import turntable_archiv
            fn = getattr(turntable_archiv, "archivuj_snimek", None)
            if fn:
                archiv = fn(int(assembly_id), el, az, tier, data)
            else:
                global _ARCHIV_FN_VAROVANI_VYPSANO
                if not _ARCHIV_FN_VAROVANI_VYPSANO:
                    app.logger.warning(
                        "archivuj_snimek nenalezena v turntable_archiv - "
                        "prubezny archiv na Sdileny disk NEAKTIVNI (uklada se "
                        "jen nahledovy thumbnail, ne snimky do Sdileneho "
                        "disku). Pokud uz byla nasazena (git pull/commit "
                        "hotovy), tenhle proces bezi se starsi verzi modulu v "
                        "pameti - restartuj ho (systemctl restart "
                        "konfigurator)."
                    )
                    _ARCHIV_FN_VAROVANI_VYPSANO = True
        except Exception as e:  # noqa: BLE001 - prubezny archiv nesmi shodit render
            app.logger.warning("prubezny archiv snimku selhal (uloha %s, e%d a%d): %s",
                               job, el, az, e)
            archiv = {"stav": "chyba", "popis": str(e)}
    return jsonify({"status": "ok", "archiv": archiv})


@app.post("/api/render-worker/job/<job>/tt-result")
def render_worker_tt_result(job):
    """Vysledek otocneho nahledu = JEDEN ZIP (162 + 5 JPEGu + manifest).
    Rozbali se do <job>.frames/; odtud ho prebira ingest do uloziste
    otocneho nahledu (api/turntable.py). ZIP se rozbaluje po polozkach
    s kontrolou nazvu - zadne cesty, zadne ../."""
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    st = br._read_status(job)
    if not st:
        return jsonify({"error": "Úloha neexistuje."}), 404
    if st.get("state") == "cancelled":
        _smaz_tt_nahled(job)
        return jsonify({"status": "ok", "note": "Úloha byla mezitím zrušena."})

    err_msg = request.headers.get("X-Worker-Error")
    if err_msg:
        log_ulozen = _uloz_worker_log(job)
        br._write_status(job, state="error", error=f"Worker: {err_msg[:500]}",
                         worker_log_saved=log_ulozen)
        _smaz_tt_nahled(job)
        return jsonify({"status": "ok"})

    data = request.get_data()
    if not data or data[:2] != b"PK":
        return jsonify({"error": "Očekávám ZIP."}), 400

    out_dir = os.path.join(br.RENDER_OUT_DIR, f"{job}.frames")
    os.makedirs(out_dir, exist_ok=True)
    safe = re.compile(r"^(frame_e-?\d{1,2}_a\d{3}_t\d{3,4}\.jpg|still_[a-z0-9_]{1,32}\.jpg|manifest\.json)$")
    written = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                name = os.path.basename(info.filename)
                if info.is_dir() or not safe.match(name):
                    continue
                with zf.open(info) as src, open(os.path.join(out_dir, name), "wb") as dst:
                    shutil.copyfileobj(src, dst)
                written += 1
    except zipfile.BadZipFile:
        return jsonify({"error": "Poškozený ZIP."}), 400

    if not os.path.exists(os.path.join(out_dir, "manifest.json")):
        br._write_status(job, state="error", error="ZIP workera neobsahuje manifest.json.")
        return jsonify({"error": "Chybí manifest.json."}), 400

    started = st.get("started") or time.time()
    zaklad = dict(on_worker=True, worker_name=st.get("worker_name"),
                  frames_dir=out_dir, frames_written=written,
                  render_seconds=round(time.time() - started, 1),
                  queue_wait_seconds=st.get("queue_wait_seconds", 0))

    # bot8 2026-09-11: PREVZETI do uloziste otocneho nahledu. Do teto zmeny
    # uloha tady skoncila jako state="done" a snimky zustaly lezet ve slozce -
    # k 2026-09-11 to bylo 40 hotovych sad a NULA radku v
    # product_turntable_frames, pritom uloha svitila zelene "hotovo".
    # Endpointy /turntable/frames + /turntable/commit vola jen prohlizec
    # (scene.html), GPU vetev do nich nikdy nevstoupila. Od ted "hotovo"
    # znamena "je to na e-shopu"; kdyz se prevzeti nepovede, uloha je
    # `error` a nese `ingest_ok=False` + duvod - snimky se NEMAZOU, da se
    # to dohnat rucne (api/turntable_ingest.py z prikazove radky).
    # ONLINE NABIDKA kartovou cestou (bot4 2026-10-01, api/nabidka_kartova_cesta.py): jeden snimek -> <job>.png k nabidce,
    # zadny ingest do otocneho nahledu (neni to karta). Poznat se to podle `ucel` v konfiguraci ulohy.
    cfg_nabidky, _ = _tt_settings(job)
    if cfg_nabidky and cfg_nabidky.get("ucel") == "nabidka":
        return _tt_result_nabidka(job, cfg_nabidky, out_dir, zaklad, written)
    assembly_id, shop_product_id = st.get("assembly_id"), st.get("shop_product_id")
    # Vandr karty (bot4 2026-09-23) nemaji product_assemblies radek, takze
    # assembly_id je LEGITIMNE None - product_turntable_frames.assembly_id
    # je uz NULLable presne pro tenhle pripad ("snimky patri produktu, ne
    # sablone", viz sql/2026-09-02_product_turntable_frames.sql). Jedina
    # skutecne nutna hodnota je shop_product_id - bez toho neni kam
    # snimky prevzit vubec.
    if not shop_product_id:
        br._write_status(job, state="error", ingest_ok=False, **zaklad,
                         error="Render OK, ale úloha nenese shop_product_id - "
                               f"není kam snímky převzít. Zůstávají v {out_dir}.")
        _smaz_tt_nahled(job)
        return jsonify({"status": "ok", "written": written, "ingest": "skipped"})
    # `ingest_bez_commitu` ve stavu ulohy = snimky zapsat, ale davku
    # NEAKTIVOVAT (is_active=0, na e-shopu se nezmeni nic). Zavedeno
    # 2026-09-11 pro situaci "uz vyrenderovano, jeste neschvaleno" -
    # rozhodnuti je DATA v ulohe, ne prepinac v kodu, aby platilo pro jednu
    # konkretni davku a nedalo se omylem zapnout plosne.
    bez_commitu = bool(st.get("ingest_bez_commitu"))
    try:
        import turntable_ingest as ti
        zprava = ti.ingest_frames_dir(out_dir, int(assembly_id) if assembly_id else None,
                                      int(shop_product_id), commit=not bez_commitu,
                                      libovolny_azimut=bez_commitu and bool(st.get("ingest_libovolny_azimut")))
    except Exception as e:  # vcetne IngestError - render se povedl, prevzeti ne
        app.logger.exception("turntable ingest selhal (uloha %s)", job)
        br._write_status(job, state="error", ingest_ok=False, **zaklad,
                         error=f"Render OK, převzetí do otočného náhledu selhalo: {e} "
                               f"(snímky zůstávají v {out_dir})")
        _smaz_tt_nahled(job)
        return jsonify({"status": "ok", "written": written, "ingest": "error"}), 200
    # Preskoceny commit NENI chyba - snimky jsou v DB, jen cekaji na
    # schvaleni. Stav proto zustava "done" a nese `commit_pending`, aby
    # bylo poznat, ze davka je nahrana a NEAKTIVNI.
    nahrano = bool(zprava.get("upload_ok"))
    preskoceno = bool(zprava.get("commit_skipped"))
    hotovo = bool(zprava.get("commit_ok")) or (preskoceno and nahrano)
    br._write_status(job, state="done" if hotovo else "error", **zaklad,
                     ingest_ok=nahrano, ingest_uploaded=zprava.get("uploaded", 0),
                     ingest_batch=zprava.get("batch"),
                     commit_pending=preskoceno,
                     note=zprava.get("note") if preskoceno else None,
                     error=None if hotovo else
                     f"Render OK, snímky nahrány ({zprava.get('uploaded', 0)}), ale commit neprošel: "
                     f"{zprava.get('commit_error')}")
    _smaz_tt_nahled(job)  # davka je hotova (nebo bezpecne neaktivni) - prubezny nahled uz neni potreba
    return jsonify({"status": "ok", "written": written,
                    "ingest": "commit-pending" if preskoceno else ("ok" if hotovo else "commit-failed"),
                    "batch": zprava.get("batch")})


def _tt_result_nabidka(job, cfg, out_dir, zaklad, written):
    """Vysledek online nabidky kartovou cestou: snimek ze ZIPu -> PNG (jak ho ceka klient u stare cesty), stav done."""
    zaklad = {k: v for k, v in zaklad.items() if k != "frames_dir"}      # slozka se smaze nize
    try:
        import nabidka_kartova_cesta as nkc
        nkc.vysledek_na_png(job, cfg, out_dir)
    except Exception as e:  # noqa: BLE001
        app.logger.exception("online nabidka: snimek se nepodarilo ulozit (uloha %s)", job)
        br._write_status(job, state="error", **zaklad,
                         error=f"Render OK, ale snímek nabídky se nepodařilo uložit: {e}")
        _smaz_tt_nahled(job)
        return jsonify({"status": "ok", "written": written, "ingest": "nabidka-error"})
    shutil.rmtree(out_dir, ignore_errors=True)
    # job_type=None VYSLOVNE: jinak by ho sticky klic nechal "turntable" a koncovka stavu by misto obrazku vratila jen stav
    br._write_status(job, state="done", job_type=None, ucel="nabidka", **zaklad)
    _smaz_tt_nahled(job)
    return jsonify({"status": "ok", "written": written, "ingest": "nabidka"})


# ------------------------------------------- samoaktualizace agenta (F)
# Robert 2026-09-09 pres bot3 ("nachystej to tak, jak to popisujes"):
# k GPU pocitaci nemame pristup, takze oprava agenta se k nemu dosud
# nemela jak dostat - "nahraj to na Sdileny disk a at si to nekdo stahne"
# v praxi znamenalo, ze se neaktualizuje nikdy. Stejny princip, jaky uz
# roky pouzivaji /script a /tt-script (renderovaci skripty se stahuji ze
# serveru, aby agent nikdy nemel starou verzi), se tim rozsiruje i na
# agenta samotneho. Za tymz tokenem jako zbytek worker API.
AGENT_SOURCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 os.pardir, "scripts", "render_worker_agent.py")


def _agent_meta():
    with open(AGENT_SOURCE_PATH, "rb") as fh:
        raw = fh.read()
    m = re.search(rb'AGENT_VERSION\s*=\s*"([^"\n]{1,40})"', raw)
    verze = m.group(1).decode("utf-8", "replace") if m else None
    return raw, {
        "version": verze,
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        # Nazev, pod ktery si ma agent verzi ulozit. SPUSTIT_AGENTA.bat
        # vybira soubor s NEJVYSSIM nazvem (`dir /b /o-n`), proto verze
        # v nazvu - a proto se datovy tvar verze nesmi menit.
        "filename": ("render_worker_agent_%s.py" % verze) if verze else None,
    }


@app.get("/api/render-worker/agent-version")
def render_worker_agent_version():
    err = _require_token()
    if err:
        return err
    try:
        _raw, meta = _agent_meta()
    except OSError:
        return jsonify({"error": "Zdrojový soubor agenta na serveru chybí."}), 404
    return jsonify(meta)


@app.get("/api/render-worker/agent-source")
def render_worker_agent_source():
    err = _require_token()
    if err:
        return err
    if not os.path.exists(AGENT_SOURCE_PATH):
        return jsonify({"error": "Zdrojový soubor agenta na serveru chybí."}), 404
    return send_file(AGENT_SOURCE_PATH, mimetype="text/x-python",
                     as_attachment=False, download_name="render_worker_agent.py")


@app.get("/api/render-worker/script")
def render_worker_script():
    """Renderovaci skript serviruje server - agent tak nikdy nema
    zastaralou verzi a pri kazde uprave se automaticky sjednoti."""
    err = _require_token()
    if err:
        return err
    return send_file(br.BLENDER_SCRIPT, mimetype="text/x-python",
                     as_attachment=False, download_name="blender_render_scene.py")


@app.get("/api/render-worker/job/<job>/model")
def render_worker_model(job):
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    path = os.path.join(br.RENDER_OUT_DIR, f"{job}.glb")
    if not os.path.exists(path):
        return jsonify({"error": "Model úlohy nenalezen."}), 404
    return send_file(path, mimetype="model/gltf-binary")


@app.get("/api/render-worker/job/<job>/asset/<kind>")
@app.get("/api/render-worker/job/<job>/asset/<kind>/<role>")
def render_worker_asset(job, kind, role=None):
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    try:
        with open(os.path.join(br.RENDER_OUT_DIR, f"{job}.json"), "r", encoding="utf-8") as fh:
            settings = json.load(fh)
    except (OSError, ValueError):
        return jsonify({"error": "Konfigurace úlohy chybí."}), 404

    path = settings.get("hdri_path") if kind == "hdri" else (settings.get("textures") or {}).get(role or "")
    # Nikdy neposilat nic mimo slozku Sdileneho disku (ochrana proti
    # podvrzene ceste v konfiguraci).
    if not path or not os.path.realpath(path).startswith(os.path.realpath(br.DRIVE_FILES_DIR)):
        return jsonify({"error": "Soubor není součástí této úlohy."}), 404
    if not os.path.exists(path):
        return jsonify({"error": "Soubor nenalezen."}), 404
    return send_file(path)


@app.post("/api/render-worker/job/<job>/progress")
def render_worker_progress(job):
    """Agent hlasi, ze na uloze porad pracuje (vc. faze - napr. kompilace
    GPU jader, ktera muze trvat minuty a jinak vypada jako zamrznuti)."""
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    st = br._read_status(job)
    if not st or st.get("state") != "running":
        return jsonify({"status": "ok", "state": st.get("state") if st else None})
    body = request.get_json(silent=True) or {}
    st["progress_note"] = str(body.get("note") or "")[:120]
    st["progress_ts"] = time.time()
    br._write_status(job, **{k: v for k, v in st.items() if k != "updated"})
    return jsonify({"status": "ok"})


@app.post("/api/render-worker/job/<job>/preview")
def render_worker_preview(job):
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    data = request.get_data()
    if not data or len(data) > 20 * 1024 * 1024:
        return jsonify({"error": "Neplatný náhled."}), 400
    preview = os.path.join(br.RENDER_OUT_DIR, f"{job}.preview.png")
    tmp = preview + ".tmp.png"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, preview)  # atomicky, stejne jako u lokalniho renderu
    return jsonify({"status": "ok"})


WORKER_LOG_MAX_BYTES = 200_000  # ~400 kB textu, dost i pro UDIN_LOG_RADKU=400 radku, orez proti zblbnutemu klientovi


def _uloz_worker_log(job):
    """Robert 2026-09-13 ("log lezi na stanici, tak jí v nove verzi
    priraď ukol, aby ti ten log posilala"): agent (od verze 2026-09-13b,
    viz scripts/render_worker_agent.py::posli_chybu_serveru) posila pri
    selhani NEJEN kratkou X-Worker-Error hlavicku (ta zustava - zpetna
    kompatibilita se starsi verzi agenta, co telo neposila), ale i CELY
    nedavny konzolovy log jako TELO POZADAVKU (text/plain). Ulozi se
    vedle stavoveho souboru jako <job>.worker_log.txt, aby slo zpetne
    zjistit, co se delo TESNE PRED padem - ne jen typ vyjimky.

    Bezpecne volat vzdy (i kdyz telo chybi/je prazdne - stary agent) -
    v tom pripade se jen nic neulozi. Vraci True, kdyz neco ulozila."""
    data = request.get_data()
    if not data:
        return False
    if len(data) > WORKER_LOG_MAX_BYTES:
        data = data[-WORKER_LOG_MAX_BYTES:]
    try:
        with open(os.path.join(br.RENDER_OUT_DIR, f"{job}.worker_log.txt"), "wb") as fh:
            fh.write(data)
        return True
    except OSError:
        return False


@app.post("/api/render-worker/job/<job>/result")
def render_worker_result(job):
    err = _require_token()
    if err:
        return err
    if not _valid_job(job):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    st = br._read_status(job)
    if not st:
        return jsonify({"error": "Úloha neexistuje."}), 404
    if st.get("state") == "cancelled":
        return jsonify({"status": "ok", "note": "Úloha byla mezitím zrušena."})

    err_msg = request.headers.get("X-Worker-Error")
    if err_msg:
        log_ulozen = _uloz_worker_log(job)
        br._write_status(job, state="error", error=f"Worker: {err_msg[:500]}",
                         worker_log_saved=log_ulozen)
        return jsonify({"status": "ok"})

    data = request.get_data()
    if not data or data[:8] != b"\x89PNG\r\n\x1a\n":
        return jsonify({"error": "Očekávám PNG."}), 400
    # Pres docasny soubor + os.replace (atomicky) - stejne jako u nahledu,
    # at klient nikdy nedostane napul zapsany PNG.
    final = os.path.join(br.RENDER_OUT_DIR, f"{job}.png")
    tmp = final + ".tmp.png"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, final)
    started = st.get("started") or time.time()
    # Stejne jako u lokalniho renderu (blender_render.py::_run_render_job):
    # uloha, ktera vi ke ktere skladove karte patri, si vysledek rovnou
    # zaradi do jeji fotogalerie - a to JESTE PRED zapisem "done", aby to
    # slo jednim zapisem stavu (viz api/render_gallery.py).
    import render_gallery
    gal = render_gallery.ulozit_po_dokonceni(job)
    br._write_status(job, state="done", on_worker=True,
                     worker_name=st.get("worker_name"),
                     render_seconds=round(time.time() - started, 1),
                     queue_wait_seconds=st.get("queue_wait_seconds", 0),
                     **gal)
    return jsonify({"status": "ok"})


# ------------------------------------------------- stav workera pro UI

@app.get("/api/admin/render-worker/status")
# bot16, 2026-09-29 (Robert pres bot3: "kazdy panel adminu do tabulky
# roli a prav") - drive @admin_required, ted stejna sekce jako
# webapp/admin.html DASHBOARD_PANEL_SECTION.gpuMonitorPanel, aby
# checkbox v Role a opravneni skutecne ovladal i data, ne jen viditelnost
# panelu. Jediny konzument je gpu-monitor.js (overeno, zadny jiny tab).
@require_permission("dash_gpu_monitor", "zobrazit")
def render_worker_status():
    info = _worker_info()
    # bot16, 2026-09-12 (bot4 zadani, viz _uloha_na_workeru/_posledni_ulohy
    # vyse) - detail aktualni ulohy + historie posledních pár, pripojene ke
    # stejne odpovedi jako zdravi workera (jeden fetch pro cely panel).
    info["current_job"] = _uloha_na_workeru()
    info["recent_jobs"] = _posledni_ulohy()
    return info


# ---------------------------------------------------------------------------
# Rendery NABIDEK a TESTU ze sceny na notebook (bot4 2026-10-01, Robert pres bot5: "Online nabidky se musi renderovat
# na Omen"). Scena u techto renderu posila "ucel": "nabidka"; stroj vybira SERVER (stroj_pro_ucel). Interaktivni
# render nesmi viset, proto jde na preferovany stroj JEN kdyz je pouzitelny (online, agent hlasi Blender >= 5.2, nema
# jinou praci) a kdyz si ho do WORKER_CLAIM_TIMEOUT_S nevezme, presmeruje se vychozi cestou (GPU stanice, pri jejim
# vypadku server) - presne jako dosud. Vypnuti: RENDER_NABIDKY_STROJ= (prazdne). Produkce se tohoto netyka; automat
# naopak tento stroj NEPOUZIVA (scripts/_render_stroje.py::je_vyhrazen, stejna promenna) - nabidku ceka clovek a agent
# bere ulohy FIFO po jedne, takze by za dlouhou otockou cekala.
NABIDKY_STROJ = os.environ.get("RENDER_NABIDKY_STROJ", "Omen").strip()
NABIDKY_MIN_BLENDER = (5, 2)    # sablona renderu je z Blenderu 5.2; starsi ji neprecte ("not a blend file")


def _verze_blenderu(gpu):
    """(major, minor) z retezce `... | Blender 5.2.1` v `gpu` tepu agenta, jinak None."""
    m = re.search(r"Blender\s+(\d+)\.(\d+)", gpu or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def je_stroj_pro_nabidky(jmeno):
    return (bool(NABIDKY_STROJ) and not je_vychozi_worker(NABIDKY_STROJ)
            and _jmeno_klic(jmeno) == _jmeno_klic(NABIDKY_STROJ))


def stroj_pro_ucel(ucel):
    """Jmeno stroje, na ktery maji jit rendery daneho UCELU, nebo None = vychozi cesta. Dnes jen "nabidka"
    (rendery nabidek a testy ze sceny); cokoli jineho (zivy nahled, produkce) jde vychozi cestou."""
    if (ucel or "").strip().lower() == "nabidka" and NABIDKY_STROJ and not je_vychozi_worker(NABIDKY_STROJ):
        return NABIDKY_STROJ
    return None


def _stroj_ma_praci(jmeno):
    """Ceka na stroj cilena uloha, nebo na nem neco bezi? (stejna pravidla jako scripts/_render_stroje.py)"""
    for _j, st in _stavy_uloh():
        if st.get("state") == "waiting_worker" and st.get("target_worker") \
                and _jmeno_klic(st.get("target_worker")) == _jmeno_klic(jmeno):
            return True
        if st.get("state") == "running" and st.get("on_worker") \
                and _jmeno_klic(st.get("worker_name")) == _jmeno_klic(jmeno):
            return True
    return False


def _stroj_pouzitelny_pro_nabidku(jmeno):
    """(ok, duvod_proc_ne)."""
    st = stav_workeru(jmeno)
    if not st["online"]:
        return False, "je offline (%s)" % (st.get("duvod") or "bez tepu")
    v = _verze_blenderu(st.get("gpu"))
    if v is None or v < NABIDKY_MIN_BLENDER:
        return False, "agent nehlasi Blender %d.%d nebo novejsi" % NABIDKY_MIN_BLENDER
    if _stroj_ma_praci(jmeno):
        return False, "uz renderuje jinou ulohu"
    return True, None


def _dispatch_na_cil(job, cfg_path, out_path, cil):
    st = stav_workeru(cil)
    jmeno = st.get("jmeno") or cil
    br._write_status(job, state="waiting_worker", queued_at=time.time(), target_worker=jmeno,
                     worker_name=jmeno, worker_gpu=st.get("gpu"),
                     note="Render jde na stroj %s." % jmeno)
    threading.Thread(target=_hlidac_cileneho, args=(job, cfg_path, out_path, jmeno),
                     name=f"cil-watchdog-{job[:8]}", daemon=True).start()
    return "worker"


def _hlidac_cileneho(job, cfg_path, out_path, cil):
    """Hlidani ulohy poslane na PREFEROVANY stroj. Nevyzvedne-li si ji do WORKER_CLAIM_TIMEOUT_S (stroj mezitim
    usnul nebo vypnul agenta), jde vychozi cestou jako kdyby cil nebyl; jinak se hlida postup."""
    deadline_claim = time.time() + WORKER_CLAIM_TIMEOUT_S
    while time.time() < deadline_claim:
        time.sleep(1)
        st = br._read_status(job) or {}
        if st.get("state") != "waiting_worker":
            break
    else:
        st = br._read_status(job) or {}
        if st.get("state") == "waiting_worker":
            app.logger.warning("Stroj %s si ulohu %s nevyzvedl do %d s, jde vychozi cestou.",
                               cil, job, WORKER_CLAIM_TIMEOUT_S)
            # target_worker je "lepivy" klic stavu - musi se zrusit VYSLOVNE (None), jinak by ulohu nevzal nikdo
            br._write_status(job, state="queued", target_worker=None,
                             note="Stroj %s se neozval, renderuje GPU stanice." % cil)
            dispatch_to_worker_or_local(job, cfg_path, out_path)
            return
    _hlidej_postup(job, cil)


def _hlidej_postup(job, cil):
    """Jako hlidani vychoziho workera: uloha, ze ktere agent prestane hlasit postup, spadne na chybu."""
    hard_deadline = time.time() + WORKER_RESULT_TIMEOUT_S
    last_seen = time.time()
    while time.time() < hard_deadline:
        time.sleep(2)
        st = br._read_status(job) or {}
        if st.get("state") in ("done", "error", "cancelled"):
            return
        last_seen = max(last_seen, st.get("progress_ts") or 0, st.get("started") or 0)
        if time.time() - last_seen > WORKER_NO_PROGRESS_S:
            st = br._read_status(job) or {}
            if st.get("state") in ("done", "error", "cancelled"):
                return    # vysledek mohl dorazit behem teto vteriny
            br._write_status(job, state="error",
                             error=f"Stroj {cil} se {WORKER_NO_PROGRESS_S} s neozval - "
                                   f"render nejspíš spadl. Zkontroluj okno agenta.")
            return
    st = br._read_status(job) or {}
    if st.get("state") == "running" and st.get("on_worker"):
        br._write_status(job, state="error", error=f"Render na stroji {cil} běží neúměrně dlouho, ukončeno.")


def dispatch_to_worker_or_local(job, cfg_path, out_path, cil=None):
    """Rozhodne, kam uloha pujde. Vola se z blender_render.py misto
    primeho spusteni lokalniho vlakna.

    `cil` = jmeno PREFEROVANEHO nevychoziho stroje (rendery nabidek a testu ze sceny, viz stroj_pro_ucel): je-li
    pouzitelny, uloha jde NA NEJ; jinak se chova jako dosud a do stavu se zapise poznamka proc."""
    poznamka = None
    if cil:
        ok, duvod = _stroj_pouzitelny_pro_nabidku(cil)
        if ok:
            return _dispatch_na_cil(job, cfg_path, out_path, cil)
        app.logger.info("Render %s: preferovany stroj %s nejde pouzit (%s), jde vychozi cestou.", job, cil, duvod)
        poznamka = "Stroj %s nejde pouzit (%s), renderuje GPU stanice." % (cil, duvod)
    if not worker_online():
        threading.Thread(target=br._run_render_job, args=(job, cfg_path, out_path),
                         name=f"blender-render-{job[:8]}", daemon=True).start()
        return "local"

    hb = _read_heartbeat() or {}
    br._write_status(job, state="waiting_worker", queued_at=time.time(),
                     worker_name=hb.get("name"), worker_gpu=hb.get("gpu"),
                     **({"note": poznamka} if poznamka else {}))

    def watchdog():
        """Nevyzvedne-li/nedokonci-li worker ulohu vcas, prebere ji server."""
        deadline_claim = time.time() + WORKER_CLAIM_TIMEOUT_S
        while time.time() < deadline_claim:
            time.sleep(1)
            st = br._read_status(job) or {}
            if st.get("state") != "waiting_worker":
                break
            # Worker prave renderuje neco jineho - posunout limit, at
            # uloha pocka na GPU misto prepadnuti na pomalejsi CPU.
            if worker_busy() and worker_online():
                deadline_claim = time.time() + WORKER_CLAIM_TIMEOUT_S
        else:
            st = br._read_status(job) or {}
            if st.get("state") == "waiting_worker":
                app.logger.warning("Worker si ulohu %s nevyzvedl, renderuje server.", job)
                br._write_status(job, state="queued",
                                 note="Worker nereagoval, render probíhá na serveru.")
                br._run_render_job(job, cfg_path, out_path)
                return
        # Uloha bezi na workeru. Nehlidame celkovy cas (prvni OptiX render
        # kompiluje jadra i nekolik minut), ale to, jestli agent hlasi
        # postup - viz /progress vyse.
        hard_deadline = time.time() + WORKER_RESULT_TIMEOUT_S
        # Robert 2026-08-11: hlidane razitko drzime MONOTONNE a vzdy aspon
        # od teto chvile. Driv se cetlo primo ze stavu, a kdyz v nem
        # razitko zrovna chybelo (nektery zapis stav prepisuje cely),
        # vyslo "0" = nekonecne stary -> uloha spadla na chybu, i kdyz
        # v poradku bezela.
        last_seen = time.time()
        while time.time() < hard_deadline:
            time.sleep(2)
            st = br._read_status(job) or {}
            if st.get("state") in ("done", "error", "cancelled"):
                return
            last_seen = max(last_seen, st.get("progress_ts") or 0, st.get("started") or 0)
            if time.time() - last_seen > WORKER_NO_PROGRESS_S:
                # Posledni kontrola tesne pred zapisem: vysledek mohl
                # dorazit behem teto vteriny a hotovy render se nesmi
                # prepsat chybou (presne to se stalo u ulohy 69e5f66c -
                # obrazek dorazil za 49,4 s a stav se pak zmenil na chybu).
                st = br._read_status(job) or {}
                if st.get("state") in ("done", "error", "cancelled"):
                    return
                br._write_status(job, state="error",
                                 error=f"Notebook se {WORKER_NO_PROGRESS_S} s neozval - "
                                       f"render nejspíš spadl. Zkontroluj okno agenta.")
                return
        st = br._read_status(job) or {}
        if st.get("state") == "running" and st.get("on_worker"):
            br._write_status(job, state="error",
                             error="Render na notebooku běží neúměrně dlouho, ukončeno.")

    threading.Thread(target=watchdog, name=f"worker-watchdog-{job[:8]}", daemon=True).start()
    return "worker"
