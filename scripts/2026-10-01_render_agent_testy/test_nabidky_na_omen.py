# Rendery NABIDEK a TESTU ze sceny na notebook (api/render_worker.py::dispatch_to_worker_or_local(cil=...), stroj_pro_ucel)
# - Robert pres bot5 2026-10-01: "Online nabidky se musi renderovat na Omen". Dočasna slozka misto private-files, falesne
# tepy agentu, CPU render serveru zachycen (nic skutecneho se nespousti), bez site. Importuje aplikaci (Flask); env z
# api/.env nacte scripts/_env.py jako casovace.
# Spusteni: api/venv/bin/python3 test_nabidky_na_omen.py   (konci kodem 0 jen kdyz VSE prosla; trva ~15 s kvuli hlidacum)
# Kandidat pred nasazenim: API_KANDIDAT=/cesta/ke/slozce/s/render_worker.py+blender_render.py (zastini nasazene moduly)
import json
import os
import re
import sys
import tempfile
import threading
import time

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
KANDIDAT = os.environ.get("API_KANDIDAT")
if KANDIDAT:
    sys.path.insert(0, KANDIDAT)
import _env  # noqa: E402
os.environ.update(_env.load_env())

import app as A  # noqa: E402,F401
import blender_render as br  # noqa: E402
import render_worker as rw  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


if KANDIDAT:
    over("moduly pochazeji z kandidata (stinovani funguje)", rw.__file__.startswith(KANDIDAT) and br.__file__.startswith(KANDIDAT), (rw.__file__, br.__file__))

tmp = tempfile.mkdtemp(prefix="nabidky_omen_")
br.RENDER_OUT_DIR = tmp
rw._HEARTBEAT_PATH = os.path.join(tmp, ".worker_heartbeat.json")
rw.NABIDKY_STROJ = "Omen"
rw.WORKER_CLAIM_TIMEOUT_S = 3
cpu_behy = []
br._run_render_job = lambda *a, **k: cpu_behy.append(a)      # CPU render serveru se nikdy nespusti
GPU_STANICE = "OPTIX: NVIDIA GeForce RTX 3060 | Blender 5.2.1"
GPU_NOTEBOOK = "OPTIX: NVIDIA GeForce RTX 4080 Laptop GPU | Blender 5.2.1"
cislo = [0]


def tep(jmeno, stari=2.0, gpu=GPU_NOTEBOOK):
    cesta = rw._HEARTBEAT_PATH if rw.je_vychozi_worker(jmeno) else rw._hb_cesta(jmeno)
    hb = {"ts": time.time() - stari, "poll_ts": time.time() - stari, "name": jmeno, "gpu": gpu, "agent_since": time.time() - 100}
    with open(cesta, "w", encoding="utf-8") as fh:
        json.dump(hb, fh)


def vycisti():
    for f in os.listdir(tmp):
        try:
            os.remove(os.path.join(tmp, f))
        except OSError:
            pass


def nova_uloha():
    cislo[0] += 1
    job = "%032x" % cislo[0]
    with open(os.path.join(tmp, job + ".json"), "w", encoding="utf-8") as fh:
        json.dump({"glb_path": "x", "output_path": "y"}, fh)
    br._write_status(job, state="queued")
    return job


def stav(job):
    return br._read_status(job) or {}


def pocka_hlidace(max_s=12):
    t0 = time.time()
    while time.time() - t0 < max_s:
        zive = [t for t in threading.enumerate() if t.name.startswith(("cil-watchdog", "worker-watchdog"))]
        if not zive:
            return True
        time.sleep(0.5)
    return False


# ---- 1) stroj_pro_ucel ---------------------------------------------------
over("1a ucel 'nabidka' -> Omen", rw.stroj_pro_ucel("nabidka") == "Omen", rw.stroj_pro_ucel("nabidka"))
over("1b velikost pismen a mezery nevadi", rw.stroj_pro_ucel("  NaBiDkA ") == "Omen")
over("1c jiny ucel / prazdny / None (zivy nahled, produkce) -> vychozi cesta", rw.stroj_pro_ucel("nahled") is None and rw.stroj_pro_ucel("") is None and rw.stroj_pro_ucel(None) is None)
rw.NABIDKY_STROJ = ""
over("1d RENDER_NABIDKY_STROJ prazdne = vypnuto", rw.stroj_pro_ucel("nabidka") is None)
rw.NABIDKY_STROJ = rw.WORKER_VYCHOZI_JMENO
over("1e jako cil nabidek nastavena vychozi stanice = bez cile (nic se necili)", rw.stroj_pro_ucel("nabidka") is None)
rw.NABIDKY_STROJ = "Omen"
over("1f verze Blenderu z retezce agenta", rw._verze_blenderu(GPU_STANICE) == (5, 2) and rw._verze_blenderu("x") is None and rw._verze_blenderu(None) is None)

# ---- 2) Omen pouzitelny -> uloha jde na nej -------------------------------
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen")
job = nova_uloha()
r = rw.dispatch_to_worker_or_local(job, "c", "o", cil="Omen")
st = stav(job)
over("2a dispatch vraci 'worker' (zpetna kompatibilita s klientem)", r == "worker", r)
over("2b stav: waiting_worker s cilem Omen", st.get("state") == "waiting_worker" and st.get("target_worker") == "Omen" and st.get("worker_name") == "Omen", st)
over("2c stav nese GPU notebooku", "4080" in (st.get("worker_gpu") or ""), st)
over("2d CPU render serveru se nespustil", not cpu_behy, cpu_behy)
# agent Omenu si ulohu vezme (jako render_worker_poll) -> hlidac nesmi nic presmerovat
time.sleep(0.6)
br._write_status(job, state="running", started=time.time(), on_worker=True, worker_name="Omen")
time.sleep(rw.WORKER_CLAIM_TIMEOUT_S + 1.5)
st = stav(job)
over("2e po vyzvednuti zustava na Omenu (cil se nezrusil, zadny CPU render)", st.get("state") == "running" and st.get("target_worker") == "Omen" and not cpu_behy, st)
br._write_status(job, state="done")
over("2f hlidac po dokonceni skonci sam", pocka_hlidace(), [t.name for t in threading.enumerate()])

# ---- 3) Omen nepouzitelny -> vychozi cesta (jako dosud) + poznamka -----------
def scenar(nazev, priprava, ocekavej_poznamku):
    vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE)
    priprava()
    j = nova_uloha()
    vysledek = rw.dispatch_to_worker_or_local(j, "c", "o", cil="Omen")
    s = stav(j)
    over("%s: jde vychozi cestou (worker, bez cile)" % nazev, vysledek == "worker" and not s.get("target_worker") and s.get("state") == "waiting_worker", (vysledek, s))
    over("%s: worker_name = vychozi stanice" % nazev, s.get("worker_name") == rw.WORKER_VYCHOZI_JMENO, s)
    over("%s: poznamka vysvetluje proc (%s)" % (nazev, ocekavej_poznamku), ocekavej_poznamku in (s.get("note") or ""), s.get("note"))


scenar("3a Omen offline (zadny tep)", lambda: None, "offline")
scenar("3b Omen s tepem starsim nez 90 s", lambda: tep("Omen", stari=300), "offline")
scenar("3c starsi agent bez verze Blenderu", lambda: tep("Omen", gpu="OPTIX: NVIDIA GeForce RTX 4080 Laptop GPU"), "Blender 5.2")
scenar("3d Blender 4.1", lambda: tep("Omen", gpu="OPTIX: RTX 4080 Laptop GPU | Blender 4.1.0"), "Blender 5.2")


def omen_ma_cekajici():
    tep("Omen")
    br._write_status("a" * 32, state="waiting_worker", queued_at=time.time(), target_worker="Omen")


def omen_renderuje():
    tep("Omen")
    br._write_status("b" * 32, state="running", started=time.time(), on_worker=True, worker_name="Omen")


scenar("3e na Omen uz ceka cilena uloha (napr. jina nabidka)", omen_ma_cekajici, "jinou ulohu")
scenar("3f na Omenu bezi render", omen_renderuje, "jinou ulohu")

# ---- 4) Omen se tvari online, ale nevyzvedne -> presmerovani na vychozi stanici -------------
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen")
job = nova_uloha()
rw.dispatch_to_worker_or_local(job, "c", "o", cil="Omen")
over("4a zpocatku jde na Omen", stav(job).get("target_worker") == "Omen", stav(job))
time.sleep(rw.WORKER_CLAIM_TIMEOUT_S + 0.8)
st = stav(job)
over("4b po limitu bez vyzvednuti: cil ZRUSEN (lepivy klic), uloha ceka na vychozi stanici",
     st.get("target_worker") is None and st.get("state") == "waiting_worker" and st.get("worker_name") == rw.WORKER_VYCHOZI_JMENO, st)
over("4c poznamka rika, ze se Omen neozval", "neozval" in (st.get("note") or ""), st.get("note"))
# vychozi stanice ulohu vezme (poll pro nevychozi stroje uloze s cilem uz neukaze)
over("4d poll vychoziho stroje ji ted VIDI (target_worker je null)", not st.get("target_worker"), st)
pocka_hlidace(10)
vycisti()

# ---- 5) vychozi cesta beze zmeny ------------------------------------------------
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen")
job = nova_uloha()
r = rw.dispatch_to_worker_or_local(job, "c", "o")
st = stav(job)
over("5a bez cile: vychozi stanice, Omen se ignoruje (i kdyz je volny)", r == "worker" and not st.get("target_worker") and st.get("worker_name") == rw.WORKER_VYCHOZI_JMENO, (r, st))
vycisti()                                  # nikdo neni online
job = nova_uloha()
r = rw.dispatch_to_worker_or_local(job, "c", "o", cil="Omen")
over("5b nikdo neni online: CPU na serveru jako dosud", r == "local" and len(cpu_behy) >= 1, (r, cpu_behy))
pocka_hlidace(10)

# ---- 6) prehled stroju + stat. kontroly zdroje ------------------------------------
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen")
cile = {c["jmeno"]: c for c in rw.prehled_cilu()}
over("6a /cile oznaci Omen priznakem nabidky, Logiman2 ne", cile.get("Omen", {}).get("nabidky") is True and cile.get(rw.WORKER_VYCHOZI_JMENO, {}).get("nabidky") is False, cile)
zdroj_br = open(br.__file__, encoding="utf-8").read()
i0 = zdroj_br.index("def blender_render():")
i1 = zdroj_br.index("def blender_render_blend_start")
over("6b POST /api/admin/blender-render predava cil podle ucelu", "cil=render_worker.stroj_pro_ucel(ucel)" in zdroj_br[i0:i1], None)
over("6c varianta .blend ze Sdileneho disku se NEmeni (zadny cil)", "stroj_pro_ucel" not in zdroj_br[i1:zdroj_br.index("\n@app.", i1 + 10) if "\n@app." in zdroj_br[i1 + 10:] else len(zdroj_br)], None)
over("6d odpoved nese jmeno stroje (pro okno renderu)", '"stroj":' in zdroj_br[i0:i1], None)

# ---- 7) skutecne dotazovani workeru (/api/render-worker/poll): kdo ulohu dostane -------------------------
rw.WORKER_TOKEN = "tajne"
klient = A.app.test_client()


def poll(jmeno):
    r = klient.get("/api/render-worker/poll", query_string={"name": jmeno, "gpu": GPU_NOTEBOOK if jmeno == "Omen" else GPU_STANICE},
                   headers={"X-Worker-Token": "tajne"})
    return (r.get_json() or {}).get("job")


vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen")
job = nova_uloha()
rw.dispatch_to_worker_or_local(job, "c", "o", cil="Omen")
v = poll(rw.WORKER_VYCHOZI_JMENO)
over("7a ulohu s cilem Omen vychozi stanice pri dotazu NEdostane", v is None, v)
o = poll("Omen")
over("7b Omen ulohu dostane a stav se prepne na running na Omenu", o and o.get("job_id") == job and stav(job).get("state") == "running"
     and stav(job).get("worker_name") == "Omen", (o and o.get("job_id"), stav(job)))
br._write_status(job, state="done")
pocka_hlidace(10)

vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen")
job = nova_uloha()
rw.dispatch_to_worker_or_local(job, "c", "o", cil="Omen")
time.sleep(rw.WORKER_CLAIM_TIMEOUT_S + 0.8)               # Omen si ji nevzal -> presmerovano
v = poll(rw.WORKER_VYCHOZI_JMENO)
over("7c po presmerovani ulohu vychozi stanice DOSTANE (cil zrusen)", v and v.get("job_id") == job, v)
over("7d a Omen ji uz nedostane (je bezici na vychozi stanici)", poll("Omen") is None)
br._write_status(job, state="done")
pocka_hlidace(10)

# ---- 8) klient (scena) posila ucel jen u renderu nabidek a testu, ne u zriveho nahledu -----------------------
klient_js = open(os.path.join(os.environ.get("SCENA_ADRESAR", os.path.join(REPO, "webapp/js/scene")), "path-traced-preview.js"), encoding="utf-8").read()
over("8a klient nastavuje ucel 'nabidka' pri renderech nabidky (settings.ucel)", klient_js.count('settings.ucel = "nabidka";') == 1, klient_js.count('settings.ucel = "nabidka";'))
over("8b klient posila ucel i pri testovacich renderech", klient_js.count('ucel: "nabidka",') == 1, klient_js.count('ucel: "nabidka",'))
over("8c zadny jiny zapis ucelu (zivy nahled a ostatni cesty jdou vychozi cestou)", len(re.findall(r"\bucel\b\s*[:=]", klient_js)) == 2, len(re.findall(r"\bucel\b\s*[:=]", klient_js)))

# ---- 9) SKUTECNY handler POST /api/admin/blender-render (jen bez obalky opravneni): ucel dojde az k vyberu stroje ---------
import io

handler = A.app.view_functions["blender_render"].__wrapped__          # puvodni funkce pod require_permission (functools.wraps)
br.BLENDER_BIN = sys.executable                                        # handler kontroluje, ze Blender na serveru existuje
dispatch_puvodni = rw.dispatch_to_worker_or_local
volani = []


def zaznam(job, cfg_path, out_path, cil=None):
    volani.append(cil)
    return dispatch_puvodni(job, cfg_path, out_path, cil=cil)


rw.dispatch_to_worker_or_local = zaznam


def post(nastaveni):
    """Zavola handler jako POST s GLB a nastavenim -> (stavovy kod, json, stav ulohy)."""
    data = {"model": (io.BytesIO(b"glTF" + b"\0" * 40), "model.glb"), "settings": json.dumps(nastaveni)}
    with A.app.test_request_context("/api/admin/blender-render", method="POST", data=data, content_type="multipart/form-data"):
        odp = handler()
    odp, kod = odp if isinstance(odp, tuple) else (odp, 200)
    j = odp.get_json()
    return kod, j, (br._read_status(j["job_id"]) or {}) if j and j.get("job_id") else {}


vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen"); volani.clear()
kod, j, st = post({"ucel": "nabidka"})
over("9a nabidka: handler vraci 202 a stroj Omen", kod == 202 and j.get("target") == "worker" and j.get("stroj") == "Omen", (kod, j))
over("9b nabidka: stav ulohy je cileny na Omen, dispatch dostal cil", st.get("target_worker") == "Omen" and volani == ["Omen"], (st, volani))
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen"); volani.clear()
kod, j, st = post({"azimuth": 10})
over("9c zivy nahled (bez ucelu): vychozi stanice, zadny cil", kod == 202 and j.get("stroj") == rw.WORKER_VYCHOZI_JMENO and not st.get("target_worker") and volani == [None], (kod, j, st, volani))
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); volani.clear()                  # Omen se neozval
kod, j, st = post({"ucel": "nabidka"})
over("9d nabidka, Omen offline: 202, vychozi stanice + poznamka (render nikdy nevisi)", kod == 202 and j.get("stroj") == rw.WORKER_VYCHOZI_JMENO and not st.get("target_worker") and "offline" in (st.get("note") or ""), (kod, j, st))
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen"); volani.clear()
rw.NABIDKY_STROJ = ""
kod, j, st = post({"ucel": "nabidka"})
over("9e RENDER_NABIDKY_STROJ prazdne: ucel se ignoruje (vychozi stanice)", kod == 202 and not st.get("target_worker") and volani == [None], (kod, j, st, volani))
rw.NABIDKY_STROJ = "Omen"
for cizi in (5, ["nabidka"], {"a": 1}, "  NABIDKA  ", "x" * 500, None):
    vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen"); volani.clear()
    try:
        kod, j, st = post({"ucel": cizi})
        ocekavano = "Omen" if cizi == "  NABIDKA  " else None
        over("9f ucel %r: bez padu, cil %s" % (str(cizi)[:12], ocekavano), kod == 202 and volani == [ocekavano], (kod, volani))
    except Exception as e:   # noqa: BLE001
        over("9f ucel %r: bez padu" % (str(cizi)[:12],), False, repr(e))
rw.dispatch_to_worker_or_local = dispatch_puvodni
pocka_hlidace(12)

print("\nVYSLEDEK nabidky na Omen: %d/%d OK" % (sum(vysl), len(vysl)))
sys.stdout.flush()
os._exit(0 if all(vysl) else 1)    # daemon vlakna aplikace (dozorce) nesmi test zdrzet
