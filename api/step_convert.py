"""
step_convert.py - bot1, 2026-07-27.

Robert: "co kdyz bychom chteli vkladat stp? umime to nejak tu strukturu
zjednodusit a dat do glb?" -> "potrebujeme tu mesh maximalne zjednodusit"
-> "osekat radiusy".

Tenhle modul BEZI v hlavnim app venv (lehky - zadna nova tezka zavislost
tady), ale samotny prevod (cadquery-ocp/OpenCascade, ~1.1GB) spousti jako
IZOLOVANY SUBPROCESS pres samostatny `api/step_venv` (viz
step_convert_worker.py). Duvod: server uz ma dost napjatou pamet (swap
byl pri testovani trvale plny) - kdyby prevod STEP souboru spadl, zabral
prilis pameti nebo se zacyklil, subprocess.run() s timeoutem ho jde
bezpecne zabit/ukoncit, aniz by to jakkoli ohrozilo hlavni gunicorn
worker/appku. `fbx_convert.py` (FBX->GLB) je oproti tomu poradne LEHCI
(assimp_py+trimesh, ~desitky MB) a proto zustava IN-PROCESS beze zmeny.
"""
import contextlib
import fcntl
import os
import json
import subprocess
import tempfile

STEP_VENV_PYTHON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "step_venv", "bin", "python3")
STEP_WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "step_convert_worker.py")
STEP_CONVERT_TIMEOUT_SEC = 120  # velkorysa rezerva - realne profily jsou male, ale radeji pockat nez useknout uprostred

# bot16 2026-09-03 (revize bot3): nahled kvality spousti 3 prevody za sebou
# (kazdy OpenCascade proces ~1 GB RAM) synchronne v HTTP requestu a bez
# fronty - N soubeznych pozadavku = 3N procesu na sdilene VPS. Souborovy
# zamek (flock, plati napric gunicorn workery - stejny vzor jako
# blender_render.QUEUE_LOCK_PATH) pusti VZDY JEN JEDEN takovy beh; dalsi
# dostane rovnou 409, misto aby cekal a narazil na gunicorn --timeout 60.
STEP_CONVERT_LOCK_PATH = os.path.join(
    os.environ.get("PRIVATE_FILES_DIR", "/opt/konfigurator/private-files"), ".step_convert.lock")


class StepConvertBusy(Exception):
    """Jiny STEP prevod prave bezi (zamek drzi jiny request/worker)."""


@contextlib.contextmanager
def step_convert_slot():
    """`with step_convert_slot():` - vyhradni slot pro STEP prevod, nebo
    StepConvertBusy bez cekani (LOCK_NB). Otevira se "a" (viz poznamka v
    blender_render._run_render_job - nepotrebuje pravo zapisu do obsahu)."""
    lock_fh = open(STEP_CONVERT_LOCK_PATH, "a")
    try:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise StepConvertBusy()
        yield
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        except OSError:
            pass
        lock_fh.close()


def step_venv_available():
    return os.path.isfile(STEP_VENV_PYTHON) and os.path.isfile(STEP_WORKER_SCRIPT)


def convert_single_step(step_path, glb_path, linear_deflection_mm=None, simplify_percent=0.75, min_face_area_frac=0.01, quality=None):
    """Vrati (True, info) pri uspechu, (False, info) pri selhani - stejne
    rozhrani jako fbx_convert.convert_single_fbx(), aby volajici kod
    (admin_profily_fbx_upload) mohl obe cesty zpracovat jednotne.

    Robert 2026-07-28 (po srovnani STEP vs FBX na "Uhelnik 30x30"/produkt
    2895): "muzeme ten step jeste vice osekat? myslim ze urcite. a zrusit
    tam vzdy logo DogusKalip." - simplify_percent zvysen z 0.6 na 0.75
    (agresivnejsi quadric decimation, "percent" = podil K ODSTRANENI) a
    pridan min_face_area_frac (0.01 = 1 % nejvetsi plochy na dilu) - B-rep
    plochy mensi nez tenhle prah (typicky rytina/logo vyrobce, na testu
    produktu 2895 to bylo 107 z 144 ploch, vsechny pod 1.8 mm^2 proti
    nejmensi "opravdove" plose 70+ mm^2) se VUBEC netesseluji, takze do
    vysledneho GLB uz logo nedorazi.

    linear_deflection_mm vychozi None (2026-08-04, ne uz 0.5) - nechava
    step_convert_worker.py rozhodnout AUTOMATICKY dle bounding boxu dilu
    A podle toho, jestli byla detekovana rytina/logo (viz worker docstring,
    blok "0"): s logem beze zmeny, bez loga o 80 % jemnejsi sit. Rucni
    prepsani (explicitni cislo mm) je porad mozne, jen uz neni vychozi.

    quality (2026-08-04, druhy pozadavek tyz den) - "low"/"medium"/"high",
    RUCNI preset kvality, ktery MA PREDNOST pred automatickou detekci -
    viz worker docstring blok "00" (Robert: "vyber kvality 3D modelu...
    zaroven tam uvadejme velikost kB", pouzito z admin UI na skladove
    karte). None (vychozi) = beze zmeny, plati automaticka detekce."""
    if not step_venv_available():
        return False, {"error": "STEP převodní prostředí (step_venv) není na serveru nainstalované."}

    cmd = [
        STEP_VENV_PYTHON, STEP_WORKER_SCRIPT, step_path, glb_path,
        "--simplify-percent", str(simplify_percent),
        "--min-face-area-frac", str(min_face_area_frac),
    ]
    if linear_deflection_mm is not None:
        cmd += ["--linear-deflection", str(linear_deflection_mm)]
    if quality in ("low", "medium", "high"):
        cmd += ["--quality", quality]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=STEP_CONVERT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return False, {"error": f"Převod STEP souboru trval déle než {STEP_CONVERT_TIMEOUT_SEC}s a byl zastaven (příliš složitý model?)."}
    except Exception as e:
        return False, {"error": f"Nepodařilo se spustit STEP převodní proces: {type(e).__name__}: {e}"}

    try:
        result = json.loads((proc.stdout or "").strip().splitlines()[-1]) if proc.stdout else None
    except Exception:
        result = None

    if result is None:
        stderr_tail = (proc.stderr or "")[-500:]
        return False, {"error": f"STEP převodní proces neposlal čitelný výsledek (exit={proc.returncode}). {stderr_tail}"}

    if not result.get("ok"):
        return False, {"error": result.get("error") or "Neznámá chyba převodu STEP."}

    return True, result


def preview_step_qualities(step_path):
    """Spusti convert_single_step() TRIKRAT (low/medium/high) do docasnych
    GLB souboru, vrati velikost (kB) + zakladni info pro kazdy stupen, pak
    docasne GLB soubory smaze - bot2, 2026-08-04. Robert: "potrebujeme
    pridat do skladovych karet, zatrzitkovac hned vedle nacteni 3D modelu,
    ma to byt vyber kvality 3D modelu... zaroven tam uvadejme velikost
    kB". Pouziva admin UI (nahled PRED skutecnym nahranim/ulozenim, viz
    /api/admin/step-quality-preview v app.py) - nic se tu neuklada
    natrvalo, jen se docasne prevede pro zjisteni velikosti vysledku.

    Jednoduseji by slo spustit jen JEDNO cteni STEP souboru a 3x
    tesselovat v ramci jednoho subprocessu (usetrilo by to 2x parsovani
    STEP), ale pro realne dily v tomhle katalogu (male kovove spojky,
    des. az stovky KB) je i 3x samostatny subprocess v radu jednotek
    sekund - jednodussi a spolehlivejsi reseni bylo prednostnejsi nez
    slozitejsi refaktoring pod tlakem casu. Pokud by v budoucnu pribyly
    vyrazne vetsi/slozitejsi STEP soubory a preview zpomalilo admin UI,
    tohle je prvni misto ke zrychleni."""
    results = {}
    with tempfile.TemporaryDirectory(prefix="step_quality_preview_") as td:
        for q in ("low", "medium", "high"):
            glb_path = os.path.join(td, f"preview_{q}.glb")
            ok, info = convert_single_step(step_path, glb_path, quality=q)
            if ok and os.path.isfile(glb_path):
                size_bytes = os.path.getsize(glb_path)
                results[q] = {
                    "ok": True,
                    "size_kb": round(size_bytes / 1024, 1),
                    "logo_detected": info.get("logo_detected"),
                    "triangles_after_simplify": info.get("triangles_after_simplify"),
                    "vertices": info.get("vertices"),
                }
            else:
                results[q] = {"ok": False, "error": (info or {}).get("error") or "Náhled převodu selhal."}
    return results
