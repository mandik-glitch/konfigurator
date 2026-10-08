"""ONLINE NABIDKA = stejna renderovaci cesta jako karty (bot4 2026-10-01).

Robert 2026-10-01: "renderovani v online nabidce musi mit i stejne pozadi jako automat na karty", "propojit" materialy
s panelem Rendering, "materialy stejne jako na Vandru". Obrazky nabidky (2 rendery ze sceny) se driv delaly cestou
api/blender_render_scene.py z GLB ze sceny - bez sablony X30-02, s HDRI z okna renderu a s materialy podle barev ve scene,
proto vypadaly jinak nez karty. Tenhle modul postavi z ZAPISU DILU sceny (to, co uklada sestava) TENTYZ job jako u nativni
karty (scripts/2026-09-09_turntable_job.py::build_job_nabidka) a zaradi ho CLI scripts/2026-09-09_turntable_render.py
(--nabidka-dily): sablona, pozadi, HDRI, svetla a prirazeni materialu z panelu Rendering se tak berou ze STEJNEHO mista a
STEJNYMI volbami jako u automatu (_render_prirazeni_lib.nacti_nastaveni_pro_automat). Vysledek (1 snimek, tier 1024) se v
render_worker.py::tt-result prevede na <job>.png, takze klient i vsechny stavove/obrazkove koncovky zustaly beze zmeny.

KDY SE NEPOUZIJE (volajici pak jede starou cestou GLB, nic se neztraci) - viz KartovaCestaNeni:
  * vypnuto (env RENDER_NABIDKY_KARTOVA_CESTA=0),
  * neni zadny pouzitelny GPU stroj (karta bez GPU by na CPU serveru bezela hodiny), nebo je vytizeny (pred nim stoji
    fronta; stara cesta si ulohu po 25 s bere sama na CPU),
  * zapis dilu je nepouzitelny / dil neni v katalogu (vlastni tvar bez GLB v katalogu, TMP import...),
  * panel Rendering neodpovida realite (chybi soubor/knihovna) - automat v tom pripade hlasite odmita, nabidka spadne
    na starou cestu misto aby zustala bez obrazku,
  * CLI selze nebo nestihne do CLI_TIMEOUT_S (napr. priprava sablony po zmene HDRI, ktera trva dlouho).
Po zarazeni hlida vlákno uloha: nevyzvedne-li ji stroj do NABIDKA_CLAIM_S, skonci chybou (klient pak sam zkusi starou
cestu); behem renderu plati stejna hlidaci pravidla jako u ostatnich uloh na workeru (render_worker._hlidej_postup).

Zarazeni CLI NEPOTREBUJE renderovaci klic ani pauzu (stejna vrstva jako POST /api/admin/blender-render, zamerne
nezamcena - viz scripts/_render_klic.py, "CO ZAMEK NEPOKRYVA"); CLI to dovoli jen s env KONFIGURATOR_NABIDKA_Z_API=1,
ktere nastavuje JEN tenhle modul. Testy: scripts/2026-10-01_nabidka_kartova_cesta_testy/.
"""
import json
import os
import subprocess
import sys
import threading
import time
import uuid

import blender_render as br
import render_worker as rw
from app import app, get_conn

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py")
PYTHON = sys.executable
POVOLENO = os.environ.get("RENDER_NABIDKY_KARTOVA_CESTA", "1").strip() != "0"
CLI_TIMEOUT_S = 120        # priprava sablony po zmene HDRI muze trvat dlouho (kopie se pak drzi v cache) - radeji stara cesta
NABIDKA_CLAIM_S = 90       # nevyzvedne-li stroj ulohu, skonci chybou (klient zkusi starou cestu)
MAX_DILY_BYTES = 2_000_000


class KartovaCestaNeni(Exception):
    """Tuhle nabidku nejde (nebo nema smysl) renderovat kartovou cestou; volajici jede starou cestou (GLB)."""


def _scripts_na_cestu():
    s = os.path.join(REPO, "scripts")
    if s not in sys.path:
        sys.path.insert(0, s)


def nacti_dily(text):
    """Pole formulare `recipe` -> seznam dilu; KartovaCestaNeni pri cemkoli nepouzitelnem (dal validuje stavitel jobu)."""
    if not text or len(text) > MAX_DILY_BYTES:
        raise KartovaCestaNeni("zapis dilu chybi nebo je prilis velky")
    try:
        dily = json.loads(text)
    except ValueError:
        raise KartovaCestaNeni("zapis dilu neni platny JSON")
    if not isinstance(dily, list) or not dily:
        raise KartovaCestaNeni("zapis dilu neni neprazdny seznam")
    return dily


def _vychozi_ma_praci():
    """Ceka na vychozi GPU stanici uloha bez cile, nebo na ni neco bezi? (pred nami by byla fronta)"""
    vych = rw._jmeno_klic(rw.WORKER_VYCHOZI_JMENO)
    for _j, st in rw._stavy_uloh():
        if st.get("state") == "waiting_worker" and not st.get("target_worker"):
            return True
        if st.get("state") == "running" and st.get("on_worker") and (
                not st.get("worker_name") or rw._jmeno_klic(st.get("worker_name")) == vych):
            return True
    return False


def zvol_stroj():
    """-> (cil, jmeno): cil = jmeno nabidkoveho stroje pro --worker, nebo None = vychozi GPU stanice; jmeno = pro zobrazeni.
    KartovaCestaNeni, kdyz neni zadny pouzitelny a VOLNY GPU stroj."""
    cil = rw.stroj_pro_ucel("nabidka")
    if cil:
        ok, _duvod = rw._stroj_pouzitelny_pro_nabidku(cil)
        if ok:
            return cil, rw.stav_workeru(cil).get("jmeno") or cil
    if not rw.worker_online():
        raise KartovaCestaNeni("zadny GPU stroj neni online")
    if _vychozi_ma_praci():
        raise KartovaCestaNeni("GPU stanice je vytizena (pred nabidkou by cekala fronta)")
    return None, rw.WORKER_VYCHOZI_JMENO


def args_z_panelu():
    """Volby panelu Rendering presne tak, jak je pouziva automat (vc. zatrzitka 'aktivni_pro_automat')."""
    _scripts_na_cestu()
    import _render_prirazeni_lib as lib
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            return list(lib.nacti_nastaveni_pro_automat(cur))
    except lib.PrirazeniNeplatne as e:
        raise KartovaCestaNeni("panel Rendering neodpovida realite: %s" % e)
    finally:
        conn.close()


def zarad(dily, azimut, elevace, user=None):
    """Zaradi JEDEN snimek nabidky. Vraci {"job", "stroj"}; KartovaCestaNeni = jed starou cestou."""
    if not POVOLENO:
        raise KartovaCestaNeni("kartova cesta je vypnuta (RENDER_NABIDKY_KARTOVA_CESTA=0)")
    if not (isinstance(azimut, (int, float)) and isinstance(elevace, (int, float))
            and not isinstance(azimut, bool) and not isinstance(elevace, bool)
            and azimut == azimut and elevace == elevace):
        raise KartovaCestaNeni("kamera nema platny azimut/elevaci")
    cil, jmeno = zvol_stroj()
    panel = args_z_panelu()
    job = uuid.uuid4().hex
    soubor = os.path.join(br.RENDER_OUT_DIR, "%s.dily.json" % job)
    argv = [PYTHON, CLI, "--nabidka-dily", soubor, "--nabidka-azimut", repr(float(azimut)),
            "--nabidka-elevace", repr(float(elevace)), "--nabidka-job", job]
    if user and user.get("id") is not None:
        argv += ["--nabidka-uzivatel", str(int(user["id"]))]
    if cil:
        argv += ["--worker", cil]
    argv += panel
    env = dict(os.environ, KONFIGURATOR_NABIDKA_Z_API="1")
    br._cleanup_stale_jobs()
    killed = br._kill_running_renders(except_job=job, user=user)    # novy render rusi predchozi (jen vlastni), jako stara cesta
    try:
        with open(soubor, "w", encoding="utf-8") as fh:
            json.dump(dily, fh)
        try:
            p = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=CLI_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            _uklid_nezarazene(job)
            raise KartovaCestaNeni("zarazeni trvalo dyl nez %d s (priprava sablony?)" % CLI_TIMEOUT_S)
    finally:
        try:
            os.remove(soubor)
        except OSError:
            pass
    vystup = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        _uklid_nezarazene(job)
        radek = next((l for l in vystup.splitlines() if l.startswith("NABIDKA_NEJDE")), None)
        raise KartovaCestaNeni(radek or "CLI skoncilo kodem %s: %s" % (p.returncode, vystup.strip()[-300:]))
    st = br._read_status(job) or {}
    if st.get("state") != "waiting_worker":
        _uklid_nezarazene(job)
        raise KartovaCestaNeni("uloha po zarazeni nema stav waiting_worker (%r)" % (st.get("state"),))
    threading.Thread(target=_hlidac, args=(job, jmeno), name="nabidka-karta-%s" % job[:8], daemon=True).start()
    return {"job": job, "stroj": jmeno, "killed": killed}


def _uklid_nezarazene(job):
    """Po neuspesnem zarazeni nesmi po ulozce zustat nic, co by si mohl worker vzit."""
    for suffix in (".json", ".status.json", ".dily.json"):
        try:
            os.remove(os.path.join(br.RENDER_OUT_DIR, job + suffix))
        except OSError:
            pass


def _hlidac(job, jmeno):
    """Nevyzvedne-li stroj ulohu do NABIDKA_CLAIM_S, skonci chybou (klient zkusi starou cestu); jinak hlida postup."""
    deadline = time.time() + NABIDKA_CLAIM_S
    while time.time() < deadline:
        time.sleep(1)
        st = br._read_status(job) or {}
        if st.get("state") != "waiting_worker":
            break
    else:
        st = br._read_status(job) or {}
        if st.get("state") == "waiting_worker":
            app.logger.warning("Nabidka %s: stroj %s si ulohu nevyzvedl do %d s.", job, jmeno, NABIDKA_CLAIM_S)
            br._write_status(job, state="error",
                             error="Stroj %s si úlohu nevyzvedl do %d s." % (jmeno, NABIDKA_CLAIM_S))
            return
    rw._hlidej_postup(job, jmeno)


def vysledek_na_png(job, cfg, out_dir):
    """Po tt-result: snimek z <job>.frames -> PNG na cestu z cfg['nabidka_vystup'] (musi byt <job>.png v RENDER_OUT_DIR).
    Vraci velikost PNG v bajtech; vyhodi vyjimku, kdyz snimek chybi/nejde precist."""
    cil = os.path.join(br.RENDER_OUT_DIR, "%s.png" % job)
    if os.path.abspath(cfg.get("nabidka_vystup") or "") != os.path.abspath(cil):
        raise ValueError("neplatna cesta vystupu nabidky")
    from PIL import Image
    snimky = sorted(f for f in os.listdir(out_dir) if f.startswith("frame_") and f.endswith(".jpg"))
    if not snimky:
        raise ValueError("ZIP workera neobsahuje zadny frame_*.jpg")
    # nejvetsi tier (vychozi jeden, ale kdyby jich bylo vic, bereme ten s nejvetsim cislem t####)
    snimky.sort(key=lambda n: int(n.rsplit("_t", 1)[1].split(".")[0]) if "_t" in n else 0)
    tmp = cil + ".tmp.png"
    with Image.open(os.path.join(out_dir, snimky[-1])) as im:
        im.convert("RGB").save(tmp, "PNG", optimize=True)
    os.replace(tmp, cil)
    return os.path.getsize(cil)
