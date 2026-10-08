# Rezim ONLINE NABIDKY v zarazovacim CLI (scripts/2026-09-09_turntable_render.py --nabidka-dily) + stavitel
# tj.build_job_nabidka (scripts/2026-09-09_turntable_job.py). Cte SKUTECNOU DB (jen SELECT: dily katalogu, nastaveni
# renderu), ale zapisuje jen do docasne slozky (RENDER_OUT_DIR modulu se prepise) a priprava sablony je atrapa - nic se
# nezaradi do skutecne fronty a nespusti se Blender.
# Spusteni:  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
#              --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-01_nabidka_kartova_cesta_testy/test_nabidka_cli.py
import contextlib
import importlib.util
import io
import json
import math
import os
import sys
import tempfile

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


spec = importlib.util.spec_from_file_location("tt_render", os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
tj = R.tj

tmp = tempfile.mkdtemp(prefix="nabidka_cli_")
R.RENDER_OUT_DIR = tmp
R.priprav_sablonu = lambda path, hdri_override=None, hdri_rotace_deg=None: (path, "atrapa")     # zadny Blender


def spust(argv, env_api=True):
    """-> (kod, stdout). Simuluje prikazovou radku; SystemExit z argparse/skriptu se zachyti."""
    puvodni = (sys.argv, os.environ.get("KONFIGURATOR_NABIDKA_Z_API"))
    sys.argv = ["turntable_render.py"] + argv
    if env_api:
        os.environ["KONFIGURATOR_NABIDKA_Z_API"] = "1"
    else:
        os.environ.pop("KONFIGURATOR_NABIDKA_Z_API", None)
    out, err = io.StringIO(), io.StringIO()
    kod = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            R.main()
    except SystemExit as e:
        kod = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if isinstance(e.code, str):
            out.write(e.code)
    finally:
        sys.argv = puvodni[0]
        if puvodni[1] is None:
            os.environ.pop("KONFIGURATOR_NABIDKA_Z_API", None)
        else:
            os.environ["KONFIGURATOR_NABIDKA_Z_API"] = puvodni[1]
    return kod, out.getvalue() + err.getvalue()


# --- skutecne dily z nejnovejsi sestavy karty (jen cteni) ------------------------------------------------------
conn = tj._connect()
with conn.cursor() as cur:
    cur.execute("SELECT data FROM product_assemblies WHERE shop_product_id IS NOT NULL ORDER BY id DESC LIMIT 1")
    raw_sestavy = json.loads(cur.fetchone()["data"]).get("parts") or []
conn.close()
dily = [{k: d[k] for k in ("part_id", "position", "quaternion", "scale") if k in d} for d in raw_sestavy if not str(d.get("part_id", "")).startswith("car_body_")][:12]
over("0 mam skutecne dily z katalogu pro test", len(dily) >= 3, len(dily))
soubor = os.path.join(tmp, "dily.json")
json.dump(dily + [{"part_id": "car_body_X", "position": [0, 0, 0], "quaternion": [0, 0, 0, 1], "scale": [1, 1, 1]}], open(soubor, "w"))
JOB = "ab" * 16

# --- 1) uspesne zarazeni -----------------------------------------------------------------------------------------
kod, vystup = spust(["--nabidka-dily", soubor, "--nabidka-azimut", "30", "--nabidka-elevace", "25", "--nabidka-job", JOB, "--nabidka-uzivatel", "7"])
over("1a CLI skonci kodem 0 (bez renderovaciho klice a bez pauzy)", kod == 0, (kod, vystup[-600:]))
cfg = json.load(open(os.path.join(tmp, JOB + ".json"))) if os.path.exists(os.path.join(tmp, JOB + ".json")) else {}
st = json.load(open(os.path.join(tmp, JOB + ".status.json"))) if os.path.exists(os.path.join(tmp, JOB + ".status.json")) else {}
over("1b cfg: typ turntable, ucel nabidka, vystup <job>.png v RENDER_OUT_DIR", cfg.get("job_type") == "turntable" and cfg.get("ucel") == "nabidka"
     and cfg.get("nabidka_vystup") == os.path.join(tmp, JOB + ".png"), {k: cfg.get(k) for k in ("job_type", "ucel", "nabidka_vystup")})
over("1c cfg: jeden snimek (1 azimut, 1 elevace, 1 tier, 0 stills)", len(cfg.get("azimuths", [])) == 1 and cfg.get("elevations") == [25]
     and list(cfg.get("tiers", {})) == [str(tj.NABIDKA_TIER)] and cfg.get("stills") == [] and cfg.get("expected_frames") == 1,
     {k: cfg.get(k) for k in ("azimuths", "elevations", "tiers", "stills", "expected_frames")})
over("1d azimut 30 (scena) -> 120 (otocka)", cfg.get("azimuths") == [120], cfg.get("azimuths"))
over("1e karoserie se nerenderuje, dily z katalogu ano (bez razitek)", len(cfg.get("parts", [])) == len(dily) and not any(str(p["part_id"]).startswith("car_body_") for p in cfg.get("parts", [])), len(cfg.get("parts", [])))
over("1f dily nesou material ze stejneho resolveru jako karty (base_color/metalness/roughness)", all("base_color" in p and "metalness" in p and "roughness" in p for p in cfg.get("parts", [])))
over("1g pozadi jako u karet (gradient z konstant jobu)", cfg.get("bg_color") == tj.TT_BG_COLOR and cfg.get("bg_color_bottom") == tj.TT_BG_COLOR_BOTTOM, (cfg.get("bg_color"), cfg.get("bg_color_bottom")))
over("1h sablona renderu je nastavena (X30-02 ze Sdileneho disku)", bool(cfg.get("template_blend")), cfg.get("template_blend"))
over("1i stav: waiting_worker, turntable, ucel, user_id, zaradil, bez assembly_id", st.get("state") == "waiting_worker" and st.get("job_type") == "turntable"
     and st.get("ucel") == "nabidka" and st.get("user_id") == 7 and st.get("zaradil") == "api-nabidka" and st.get("assembly_id") is None
     and st.get("expected_frames") == 1, st)
over("1j nic jineho do fronty nepribylo", sorted(f for f in os.listdir(tmp) if f.endswith(".status.json")) == [JOB + ".status.json"], os.listdir(tmp))

# --- 2) cilene na stroj ---------------------------------------------------------------------------------------------
JOB2 = "cd" * 16
kod, vystup = spust(["--nabidka-dily", soubor, "--nabidka-azimut", "-50", "--nabidka-elevace", "70", "--nabidka-job", JOB2, "--worker", "Omen"])
st2 = json.load(open(os.path.join(tmp, JOB2 + ".status.json"))) if os.path.exists(os.path.join(tmp, JOB2 + ".status.json")) else {}
cfg2 = json.load(open(os.path.join(tmp, JOB2 + ".json"))) if os.path.exists(os.path.join(tmp, JOB2 + ".json")) else {}
over("2a --worker Omen -> cil ve stavu", kod == 0 and st2.get("target_worker") == "Omen", (kod, st2))
over("2b azimut -50 (scena) -> 40 (otocka), elevace 70", cfg2.get("azimuths") == [40] and cfg2.get("elevations") == [70], (cfg2.get("azimuths"), cfg2.get("elevations")))

# --- 3) odmitnuti -------------------------------------------------------------------------------------------------------
kod, vystup = spust(["--nabidka-dily", soubor, "--nabidka-azimut", "1", "--nabidka-elevace", "1"], env_api=False)
over("3a bez env KONFIGURATOR_NABIDKA_Z_API=1 a bez renderovaciho klice se odmitne (boti bez klice nesmi)", kod != 0 and not os.path.exists(os.path.join(tmp, "ab" * 16 + ".x")), (kod, vystup[-300:]))
kod, vystup = spust(["--nabidka-dily", soubor, "--nabidka-azimut", "1"])
over("3b chybi elevace -> chyba", kod != 0, (kod, vystup[-200:]))
kod, vystup = spust(["--nabidka-dily", soubor, "--nabidka-azimut", "1", "--nabidka-elevace", "1", "--nabidka-job", "../../etc/passwd"])
over("3c neplatne job id -> chyba (zadna cesta ven)", kod != 0, (kod, vystup[-200:]))
kod, vystup = spust(["--nabidka-dily", soubor, "--nabidka-azimut", "1", "--nabidka-elevace", "1", "--test", "5"])
over("3d nejde kombinovat s --test/assembly_id", kod != 0, (kod, vystup[-200:]))
kod, vystup = spust(["--nabidka-azimut", "1"])
over("3e volby nabidky bez --nabidka-dily -> chyba", kod != 0, (kod, vystup[-200:]))

json.dump([{"part_id": "neexistujici_dil_xyz", "position": [0, 0, 0], "quaternion": [0, 0, 0, 1], "scale": [1, 1, 1]}], open(os.path.join(tmp, "chybi.json"), "w"))
kod, vystup = spust(["--nabidka-dily", os.path.join(tmp, "chybi.json"), "--nabidka-azimut", "1", "--nabidka-elevace", "1", "--nabidka-job", "ef" * 16])
over("3f dil, ktery v katalogu neni -> kod 3 + NABIDKA_NEJDE (API spadne na starou cestu)", kod == 3 and "NABIDKA_NEJDE" in vystup, (kod, vystup[-200:]))
over("3g a nic se nezaradilo", not os.path.exists(os.path.join(tmp, "ef" * 16 + ".status.json")))
json.dump([{"part_id": "car_body_X", "position": [0, 0, 0], "quaternion": [0, 0, 0, 1], "scale": [1, 1, 1]}], open(os.path.join(tmp, "jen_kar.json"), "w"))
kod, vystup = spust(["--nabidka-dily", os.path.join(tmp, "jen_kar.json"), "--nabidka-azimut", "1", "--nabidka-elevace", "1"])
over("3h jen karoserie -> NABIDKA_NEJDE", kod == 3 and "NABIDKA_NEJDE" in vystup, (kod, vystup[-200:]))
json.dump("neni seznam", open(os.path.join(tmp, "spatny.json"), "w"))
kod, vystup = spust(["--nabidka-dily", os.path.join(tmp, "spatny.json"), "--nabidka-azimut", "1", "--nabidka-elevace", "1"])
over("3i dily nejsou seznam -> NABIDKA_NEJDE", kod == 3 and "NABIDKA_NEJDE" in vystup, (kod, vystup[-200:]))
kod, vystup = spust(["--nabidka-dily", os.path.join(tmp, "neexistuje.json"), "--nabidka-azimut", "1", "--nabidka-elevace", "1"])
over("3j soubor s dily neexistuje -> NABIDKA_NEJDE", kod == 3 and "NABIDKA_NEJDE" in vystup, (kod, vystup[-200:]))

# --- 4) puvodni (kartova/automatova) cesta ma zamek dal ---------------------------------------------------------------
os.environ.pop("KONFIGURATOR_RENDER_KLIC_SOUBOR", None)
kod, vystup = spust(["1"], env_api=False)
over("4a bezna otocka bez renderovaciho klice se STALE odmitne (zamek se nezeslabil)", kod != 0 and not os.path.exists(os.path.join(tmp, "x")), (kod, vystup[-300:]))
over("4b a nic nezaradila", len([f for f in os.listdir(tmp) if f.endswith(".status.json")]) == 2, os.listdir(tmp))

# --- 5) prevod azimutu: nezavisle overeni proti vzorci kamer obou skriptu ---------------------------------------------------
def smer_scena(az_s, el):       # blender_render_scene.py: smer stred -> kamera v Blender souradnicich
    a, e = math.radians(az_s), math.radians(el)
    return (math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))


def smer_otocka(az_t, el):      # blender_render_turntable.py::_cam_dir v three.js souradnicich -> Blender (x, -z, y)
    a, e = math.radians(az_t), math.radians(el)
    tx, ty, tz = math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a)
    return (tx, -tz, ty)


nejhorsi = 0.0
for az_s in range(-180, 360, 15):
    for el in (-40, 0, 25, 70):
        s1, s2 = smer_scena(az_s, el), smer_otocka(tj.azimut_sceny_na_otocku(az_s), el)
        nejhorsi = max(nejhorsi, max(abs(x - y) for x, y in zip(s1, s2)))
over("5 prevod azimutu: smer kamery je pro scenu a otocku IDENTICKY (max odchylka %.2e)" % nejhorsi, nejhorsi < 1e-9, nejhorsi)

print("\nVYSLEDEK nabidka CLI: %d/%d OK" % (sum(vysl), len(vysl)))
sys.stdout.flush()
os._exit(0 if all(vysl) else 1)
