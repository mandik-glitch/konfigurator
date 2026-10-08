# Online nabidka kartovou cestou na strane API (api/nabidka_kartova_cesta.py + vetev v blender_render() + tt-result v
# render_worker.py): od POST /api/admin/blender-render pres SKUTECNE CLI (zarazeni), dotaz agenta /poll, vysledek /tt-result az
# po koncovku stavu, ktera vraci PNG klientovi. Nahrazeno je jen: RENDER_OUT_DIR (docasna slozka), priprava sablony (atrapa,
# bez Blenderu) a tepy agentu. DB se jen cte (dily katalogu, panel Rendering).
# Spusteni:  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
#              --working-directory=/opt/konfigurator api/venv/bin/python3 -u scripts/2026-10-01_nabidka_kartova_cesta_testy/test_nabidka_api.py
import base64
import io
import json
import os
import sys
import tempfile
import threading
import time
import zipfile

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
if os.environ.get("API_KANDIDAT"):      # mutacni kontroly: kopie modulu pred nasazenymi
    sys.path.insert(0, os.environ["API_KANDIDAT"])
import _env  # noqa: E402
os.environ.update(_env.load_env())

import app as A  # noqa: E402
import blender_render as br  # noqa: E402
import render_worker as rw  # noqa: E402
import nabidka_kartova_cesta as nkc  # noqa: E402
from PIL import Image  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


if os.environ.get("API_KANDIDAT"):
    over("moduly pochazeji z kandidata (stinovani funguje)", rw.__file__.startswith(os.environ["API_KANDIDAT"]) and nkc.__file__.startswith(os.environ["API_KANDIDAT"]), (rw.__file__, nkc.__file__))

tmp = tempfile.mkdtemp(prefix="nabidka_api_")
br.RENDER_OUT_DIR = tmp
rw._HEARTBEAT_PATH = os.path.join(tmp, ".worker_heartbeat.json")
rw.NABIDKY_STROJ = "Omen"
rw.WORKER_TOKEN = "tajne"
os.environ["TEST_RENDER_OUT_DIR"] = tmp
cpu_behy = []
br._run_render_job = lambda *a, **k: cpu_behy.append(a)

# CLI se spousti pres tenky obal, ktery prepise RENDER_OUT_DIR a pripravu sablony (jinak by zapsal do skutecne fronty / spustil Blender)
obal = os.path.join(tmp, "cli_obal.py")
open(obal, "w").write('''
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("tt_render", "%s/scripts/2026-09-09_turntable_render.py")
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
R.RENDER_OUT_DIR = os.environ["TEST_RENDER_OUT_DIR"]
R.priprav_sablonu = lambda path, hdri_override=None, hdri_rotace_deg=None: (path, "atrapa")
sys.argv[0] = "turntable_render.py"
R.main()
''' % REPO)
nkc.CLI = obal
nkc.NABIDKA_CLAIM_S = 3

GPU_STANICE = "OPTIX: NVIDIA GeForce RTX 3060 | Blender 5.2.1"
GPU_NOTEBOOK = "OPTIX: NVIDIA GeForce RTX 4080 Laptop GPU | Blender 5.2.1"


def tep(jmeno, stari=2.0, gpu=GPU_NOTEBOOK):
    cesta = rw._HEARTBEAT_PATH if rw.je_vychozi_worker(jmeno) else rw._hb_cesta(jmeno)
    with open(cesta, "w") as fh:
        json.dump({"ts": time.time() - stari, "poll_ts": time.time() - stari, "name": jmeno, "gpu": gpu, "agent_since": time.time() - 100}, fh)


def vycisti():
    for f in os.listdir(tmp):
        p = os.path.join(tmp, f)
        if f in ("cli_obal.py", "__pycache__"):
            continue
        if os.path.isdir(p):
            import shutil
            shutil.rmtree(p, ignore_errors=True)
        else:
            os.remove(p)


def stavy():
    return sorted(f for f in os.listdir(tmp) if f.endswith(".status.json"))


def stav(job):
    return br._read_status(job) or {}


def pocka_hlidace(max_s=15):
    t0 = time.time()
    while time.time() - t0 < max_s:
        if not [t for t in threading.enumerate() if t.name.startswith("nabidka-karta")]:
            return True
        time.sleep(0.4)
    return False


# --- skutecne dily katalogu (jen cteni) -------------------------------------------------------------------------------
conn = A.get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT data FROM product_assemblies WHERE shop_product_id IS NOT NULL ORDER BY id DESC LIMIT 1")
    raw = json.loads(cur.fetchone()["data"]).get("parts") or []
conn.close()
DILY = [{k: d[k] for k in ("part_id", "position", "quaternion", "scale") if k in d} for d in raw if not str(d.get("part_id", "")).startswith("car_body_")][:10]
over("0 skutecne dily pro test", len(DILY) >= 3, len(DILY))
RECIPE = json.dumps(DILY)

# ---------------------------------------------------------------------------------------------------------------------
print("--- 1) zarad(): vyber stroje a zarazeni")
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen")
r = nkc.zarad(DILY, 30, 25, None)
st = stav(r["job"])
over("1a Omen pouzitelny -> uloha cilena na Omen, stroj Omen", r["stroj"] == "Omen" and st.get("target_worker") == "Omen" and st.get("state") == "waiting_worker", (r, st))
over("1b stav nese typ turntable + ucel nabidka", st.get("job_type") == "turntable" and st.get("ucel") == "nabidka", st)
over("1c docasny soubor s dily je pryc, zbyva <job>.json + status", not os.path.exists(os.path.join(tmp, r["job"] + ".dily.json")) and os.path.exists(os.path.join(tmp, r["job"] + ".json")))
cfg = json.load(open(os.path.join(tmp, r["job"] + ".json")))
over("1d konfigurace: 1 snimek, azimut scena 30 -> otocka 120, vystup <job>.png", cfg.get("azimuths") == [120] and cfg.get("elevations") == [25] and cfg.get("nabidka_vystup") == os.path.join(tmp, r["job"] + ".png"), {k: cfg.get(k) for k in ("azimuths", "elevations", "nabidka_vystup")})
pocka_hlidace(10)                                   # nikdo si ulohu nevzal -> hlidac ji po NABIDKA_CLAIM_S ukonci chybou
st = stav(r["job"])
over("1e nevyzvednuta uloha: po limitu chyba (klient zkusi starou cestu), worker ji uz nevezme", st.get("state") == "error" and "nevyzvedl" in (st.get("error") or ""), st)

vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE)
r = nkc.zarad(DILY, 30, 25, None)
st = stav(r["job"])
over("1f Omen offline, vychozi stanice volna -> bez cile, stroj = vychozi", r["stroj"] == rw.WORKER_VYCHOZI_JMENO and not st.get("target_worker") and st.get("state") == "waiting_worker", (r, st))
pocka_hlidace(10)

vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen")
br._write_status("a" * 32, state="waiting_worker", queued_at=time.time(), target_worker="Omen")       # na Omenu uz ceka uloha
r = nkc.zarad(DILY, 30, 25, None)
over("1g Omen ma praci, vychozi volna -> vychozi stanice", r["stroj"] == rw.WORKER_VYCHOZI_JMENO and not stav(r["job"]).get("target_worker"), (r, stav(r["job"])))
pocka_hlidace(10)


def nejde(nazev, priprava, ocekavany_text, **kw):
    vycisti()
    priprava()
    pred = stavy()
    soubory_pred = set(os.listdir(tmp))
    try:
        nkc.zarad(kw.get("dily", DILY), kw.get("az", 30), kw.get("el", 25), None)
        over("%s: mela vyhodit KartovaCestaNeni" % nazev, False, None)
    except nkc.KartovaCestaNeni as e:
        over("%s: KartovaCestaNeni (%s)" % (nazev, ocekavany_text), ocekavany_text in str(e), str(e)[:200])
    except Exception as e:   # noqa: BLE001
        over("%s: spatny typ vyjimky" % nazev, False, repr(e))
    pribylo = set(os.listdir(tmp)) - soubory_pred
    over("%s: nic nezustalo ve fronte ani po souborech (pribylo: %s)" % (nazev, sorted(pribylo)), stavy() == pred and not pribylo, sorted(pribylo))


print("--- 2) kdy se kartova cesta nepouzije")
nejde("2a zadny GPU stroj online", lambda: None, "neni online")
nejde("2b vychozi stanice vytizena (ceka uloha bez cile)", lambda: (tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE), br._write_status("b" * 32, state="waiting_worker", queued_at=time.time())), "vytizena")
nejde("2c vychozi stanice vytizena (bezi render)", lambda: (tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE), br._write_status("b" * 32, state="running", started=time.time(), on_worker=True, worker_name=rw.WORKER_VYCHOZI_JMENO)), "vytizena")
nejde("2d dil mimo katalog", lambda: tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE), "NABIDKA_NEJDE", dily=[{"part_id": "neexistuje_xyz", "position": [0, 0, 0], "quaternion": [0, 0, 0, 1], "scale": [1, 1, 1]}])
nejde("2e kamera bez uhlu", lambda: tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE), "azimut", az=None)
nejde("2f nesmyslna cisla v dilech", lambda: tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE), "NABIDKA_NEJDE", dily=[{"part_id": DILY[0]["part_id"], "position": [0, 0, "x"], "quaternion": [0, 0, 0, 1], "scale": [1, 1, 1]}])
nkc.POVOLENO = False
nejde("2g vypnuto (RENDER_NABIDKY_KARTOVA_CESTA=0)", lambda: tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE), "vypnuta")
nkc.POVOLENO = True
puvodni_panel = nkc.args_z_panelu


def panel_spatny():
    raise nkc.KartovaCestaNeni("panel Rendering neodpovida realite: knihovna x chybi")


nkc.args_z_panelu = panel_spatny
nejde("2h panel Rendering neodpovida realite", lambda: tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE), "panel Rendering")
nkc.args_z_panelu = puvodni_panel
nkc.CLI_TIMEOUT_S = 0.05
nejde("2i CLI nestihne casovy limit", lambda: tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE), "dyl nez")
nkc.CLI_TIMEOUT_S = 120
vycisti()
for suf in (".json", ".status.json", ".dily.json"):
    open(os.path.join(tmp, "9" * 32 + suf), "w").write("{}")
open(os.path.join(tmp, "8" * 32 + ".status.json"), "w").write("{}")
nkc._uklid_nezarazene("9" * 32)
over("2j _uklid_nezarazene smaze soubory JEN te ulohy (cizi uloha zustane)", not [f for f in os.listdir(tmp) if f.startswith("9" * 32)] and os.path.exists(os.path.join(tmp, "8" * 32 + ".status.json")), os.listdir(tmp))

# ---------------------------------------------------------------------------------------------------------------------
print("--- 3) skutecny handler POST /api/admin/blender-render")
handler = A.app.view_functions["blender_render"].__wrapped__
br.BLENDER_BIN = sys.executable
puvodni_dispatch = rw.dispatch_to_worker_or_local
volani_stare = []
rw.dispatch_to_worker_or_local = lambda job, cfg_path, out_path, cil=None: (volani_stare.append(job), "worker")[1]


def post(nastaveni, recipe=None):
    data = {"model": (io.BytesIO(b"glTF" + b"\0" * 40), "model.glb"), "settings": json.dumps(nastaveni)}
    if recipe is not None:
        data["recipe"] = recipe
    with A.app.test_request_context("/api/admin/blender-render", method="POST", data=data, content_type="multipart/form-data"):
        odp = handler()
    odp, kod = odp if isinstance(odp, tuple) else (odp, 200)
    return kod, odp.get_json()


vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen"); volani_stare.clear()
kod, j = post({"ucel": "nabidka", "camera_azimuth_deg": 40, "camera_elevation_deg": 30}, RECIPE)
over("3a nabidka + zapis dilu -> 202, cesta karta, stroj Omen, stara cesta se nevolala", kod == 202 and j.get("cesta") == "karta" and j.get("stroj") == "Omen" and j.get("target") == "worker" and not volani_stare, (kod, j, volani_stare))
JOB = j["job_id"]
st = stav(JOB)
over("3b ve stavu cileno na Omen, bez GLB ze sceny na disku (neni potreba)", st.get("target_worker") == "Omen" and not os.path.exists(os.path.join(tmp, JOB + ".glb")), st)
over("3c azimut 40 (scena) -> 130 (otocka)", json.load(open(os.path.join(tmp, JOB + ".json"))).get("azimuths") == [130])

# agent Omenu si ulohu vezme (skutecny /poll) a vrati vysledek (skutecny /tt-result)
klient = A.app.test_client()
hlav = {"X-Worker-Token": "tajne"}
poll = klient.get("/api/render-worker/poll", query_string={"name": "Omen", "gpu": GPU_NOTEBOOK}, headers=hlav).get_json().get("job")
over("3d agent Omenu dostane ulohu typu turntable se sablonou a dily", poll and poll.get("job_type") == "turntable" and poll.get("job_id") == JOB and poll.get("glb_files") and poll.get("template_url"), poll and {k: poll.get(k) for k in ("job_type", "job_id")})
over("3e vychozi stanice tu ulohu nedostane (cilena na Omen)", klient.get("/api/render-worker/poll", query_string={"name": rw.WORKER_VYCHOZI_JMENO, "gpu": GPU_STANICE}, headers=hlav).get_json().get("job") is None)
over("3f stav -> running na Omenu", stav(JOB).get("state") == "running" and stav(JOB).get("worker_name") == "Omen", stav(JOB))

buf = io.BytesIO()
snimek = io.BytesIO()
Image.new("RGB", (1024, 1024), (240, 243, 245)).save(snimek, "JPEG", quality=90)
with zipfile.ZipFile(buf, "w") as zf:
    zf.writestr("frame_e30_a130_t1024.jpg", snimek.getvalue())
    zf.writestr("manifest.json", json.dumps({"ok": True}))
ingest_volani = []
import turntable_ingest as ti  # noqa: E402
ti.ingest_frames_dir = lambda *a, **k: (ingest_volani.append(a), {})[1]
odp = klient.post("/api/render-worker/job/%s/tt-result" % JOB, data=buf.getvalue(), headers=hlav)
over("3g tt-result: 200 a ingest do otocneho nahledu se NEvolal", odp.status_code == 200 and (odp.get_json() or {}).get("ingest") == "nabidka" and not ingest_volani, (odp.status_code, odp.get_json(), ingest_volani))
st = stav(JOB)
over("3h stav done, job_type vynulovan (sticky), PNG existuje", st.get("state") == "done" and st.get("job_type") is None and os.path.exists(os.path.join(tmp, JOB + ".png")), st)
with Image.open(os.path.join(tmp, JOB + ".png")) as im:
    over("3i PNG je 1024x1024 RGB", im.format == "PNG" and im.size == (1024, 1024) and im.mode == "RGB", (im.format, im.size, im.mode))
over("3j slozka se snimky uklizena", not os.path.exists(os.path.join(tmp, JOB + ".frames")))
koncovka = A.app.view_functions["blender_render_status"].__wrapped__
with A.app.test_request_context("/api/admin/blender-render/%s" % JOB):
    odp = koncovka(JOB)
odp, kod = odp if isinstance(odp, tuple) else (odp, 200)
jj = odp.get_json()
over("3k klientska koncovka stavu vraci hotovy obrazek (data URL PNG) jako u stare cesty", kod == 200 and jj.get("state") == "done" and str(jj.get("image", "")).startswith("data:image/png;base64,"), (kod, {k: (str(v)[:40]) for k, v in (jj or {}).items()}))
if jj.get("image"):
    over("3l obrazek v odpovedi je skutecne PNG", base64.b64decode(jj["image"].split(",", 1)[1])[:8] == b"\x89PNG\r\n\x1a\n")

# --- 4) fallback na starou cestu
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen"); volani_stare.clear()
kod, j = post({"ucel": "nabidka", "camera_azimuth_deg": 40, "camera_elevation_deg": 30})
over("4a bez zapisu dilu -> stara cesta (dispatch zavolan), bez priznaku cesta", kod == 202 and len(volani_stare) == 1 and j.get("cesta") is None, (kod, j, volani_stare))
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); volani_stare.clear()
br._write_status("c" * 32, state="running", started=time.time(), on_worker=True, worker_name=rw.WORKER_VYCHOZI_JMENO)       # vychozi vytizena, Omen offline
kod, j = post({"ucel": "nabidka", "camera_azimuth_deg": 40, "camera_elevation_deg": 30}, RECIPE)
st = stav(j["job_id"])
over("4b kartova cesta nejde (vytizeno) -> stara cesta + poznamka ve stavu", kod == 202 and len(volani_stare) == 1 and "Kartová cesta nejde" in (st.get("note") or ""), (kod, volani_stare, st.get("note")))
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen"); volani_stare.clear()
kod, j = post({"camera_azimuth_deg": 40, "camera_elevation_deg": 30}, RECIPE)
over("4c zivy nahled (bez ucelu) i se zapisem dilu -> stara cesta", kod == 202 and len(volani_stare) == 1 and j.get("cesta") is None, (kod, j, volani_stare))
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE); tep("Omen"); volani_stare.clear()
kod, j = post({"ucel": "nabidka", "camera_azimuth_deg": 40, "camera_elevation_deg": 30}, "to neni json")
over("4d rozbity zapis dilu -> stara cesta, 202", kod == 202 and len(volani_stare) == 1, (kod, j))
nkc.zarad = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("necekana chyba"))
volani_stare.clear()
kod, j = post({"ucel": "nabidka", "camera_azimuth_deg": 40, "camera_elevation_deg": 30}, RECIPE)
over("4e necekana vyjimka v nove ceste nic neshodi -> stara cesta", kod == 202 and len(volani_stare) == 1, (kod, j))
rw.dispatch_to_worker_or_local = puvodni_dispatch

# --- 5) tt-result: obrana a beze zmeny pro karty
vycisti(); tep(rw.WORKER_VYCHOZI_JMENO, gpu=GPU_STANICE)
JOB5 = "5" * 32
json.dump({"job_type": "turntable", "ucel": "nabidka", "nabidka_vystup": "/etc/cokoli.png", "parts": [], "out_dir": tmp}, open(os.path.join(tmp, JOB5 + ".json"), "w"))
br._write_status(JOB5, state="running", started=time.time(), on_worker=True, worker_name="Omen", job_type="turntable")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as zf:
    zf.writestr("frame_e30_a130_t1024.jpg", snimek.getvalue())
    zf.writestr("manifest.json", "{}")
odp = klient.post("/api/render-worker/job/%s/tt-result" % JOB5, data=buf.getvalue(), headers=hlav)
st = stav(JOB5)
over("5a podvrzena cesta vystupu se nezapise (stav error, mimo RENDER_OUT_DIR nic nevznikne)", st.get("state") == "error" and not os.path.exists("/etc/cokoli.png"), st)
JOB6 = "6" * 32
json.dump({"job_type": "turntable", "parts": [], "out_dir": tmp}, open(os.path.join(tmp, JOB6 + ".json"), "w"))
br._write_status(JOB6, state="running", started=time.time(), on_worker=True, worker_name="Omen", job_type="turntable", shop_product_id=123, assembly_id=45)
ingest_volani.clear()
ti.ingest_frames_dir = lambda *a, **k: (ingest_volani.append((a, k)), {"upload_ok": True, "commit_ok": True, "uploaded": 1, "batch": 1})[1]
odp = klient.post("/api/render-worker/job/%s/tt-result" % JOB6, data=buf.getvalue(), headers=hlav)
over("5b KARTA (bez ucelu nabidka) jde dal pres ingest do otocneho nahledu, beze zmeny", len(ingest_volani) == 1 and stav(JOB6).get("state") == "done" and not os.path.exists(os.path.join(tmp, JOB6 + ".png")), (ingest_volani, stav(JOB6)))

print("\nVYSLEDEK nabidka API: %d/%d OK" % (sum(vysl), len(vysl)))
sys.stdout.flush()
os._exit(0 if all(vysl) else 1)
