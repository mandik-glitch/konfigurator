#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Druhe kolo srovnani (Robert 2026-09-23, po prvni 43-variantni davce):
"a neuvadiš tam materiály !!! ... každy testovací render ponese infomaci:
hdri, sila, natočení podle svisle osy, materiál hliniku, čela šuplíku,
plastové vyplně cub" + "hliník chci prostřídat také abychom nasli nejlepsi
variantu materiálu ALU vs HDri".

Vyuziva novy --vd-tint mechanismus (blender_render_turntable.py, dnes
pridano) - zadny z realnych VD_/ALU materialu nema hotovou druhou variantu
(overeno primo v .blend souborech pres bota4 + vlastni introspekci), tint
je jednorazovy Mix(Color) prekryv nad puvodni texturou/procedurou, PRO
TUHLE DAVKU, nic v knihovne na disku se netrvale nemeni.

Kazdy zaznam popisuje VSECH PET os najednou (hdri, sila, rotace, alu,
suplik, cub), i kdyz se pro danou variantu nemeni - presne Robertuv
pozadavek "kazdy render ponese informaci", ne jen to, co se zrovna lisi.
"""
import json, os, re, subprocess, time

REPO = "/opt/konfigurator"
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
RENDER_SCRIPT = os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py")
RENDER_OUT_DIR = os.path.join(REPO, "private-files", "blender-renders")
DRIVE_FILES_DIR = os.path.join(REPO, "private-files", "shared-drive")
RENDERING_TOP_FOLDER_ID = 42  # "Rendering"
DRIVE_FOLDER_NAME = "2026-09-23b porovnani materialu (vanDrawee)"
ROBERT_APP_USER_ID = 1
ASSEMBLY_ID = "672"

# Baseline (drzeny konstantni, pokud dana varianta nerika jinak):
BASELINE_HDRI_NAZEV = "canary_wharf_8k"  # aktualni vychozi z app_settings, zadny --hdri override
ALT_HDRI_NAZEV = "studio_small_08_4k"
ALT_HDRI_CESTA = os.path.join(REPO, "private-files", "shared-drive-named", "Rendering", "HDRi", "studio_small_08_4k.exr")
BASELINE_ROT = 120
BASELINE_SILA = 1.0

ALU_VARIANTY = [
    ("nativni (Sandblasted aluminium, bez uprav)", None),
    ("teplejsi/champagne tint #b8a888 mix0.35", {"match": "alu", "hex": "#b8a888", "mix": 0.35}),
    ("chladnejsi/gunmetal tint #6b7480 mix0.35", {"match": "alu", "hex": "#6b7480", "mix": 0.35}),
    ("tmavsi/antracit tint #3a3a3d mix0.5", {"match": "alu", "hex": "#3a3a3d", "mix": 0.5}),
    ("svetlejsi/surovy tint #d8d8d8 mix0.35", {"match": "alu", "hex": "#d8d8d8", "mix": 0.35}),
]
SUPLIK_VARIANTY = [
    ("cervena #c0392b mix0.85", {"match": "tyrkys", "hex": "#c0392b", "mix": 0.85}),
    ("tmave seda #3a3a3d mix0.85", {"match": "tyrkys", "hex": "#3a3a3d", "mix": 0.85}),
    ("oranzova (brand #d4863f) mix0.85", {"match": "tyrkys", "hex": "#d4863f", "mix": 0.85}),
]
CUB_VARIANTY = [
    ("tmavsi antracit #4a4a4a mix0.7", {"match": "cub", "hex": "#4a4a4a", "mix": 0.7}),
    ("svetlejsi bezmala bila #d0d0d0 mix0.7", {"match": "cub", "hex": "#d0d0d0", "mix": 0.7}),
]


def popis5(hdri, sila, rot, alu, suplik, cub):
    return ("HDRI=%s | sila=%s | rotace=%s stupnu | hlinik=%s | "
            "cela suplíku=%s | plastove vyplne CUB=%s" % (hdri, sila, rot, alu, suplik, cub))


def build_varianty():
    v = []
    n = 0
    # 1) ALU x HDRI (hlavni pozadavek: "hliník vs HDRI")
    for hdri_nazev, hdri_cesta in [(BASELINE_HDRI_NAZEV, None), (ALT_HDRI_NAZEV, ALT_HDRI_CESTA)]:
        for alu_popis, alu_override in ALU_VARIANTY:
            flags = []
            if hdri_cesta:
                flags += ["--hdri", hdri_cesta]
            if alu_override:
                flags += ["--vd-tint", "%s:%s:%s" % (alu_override["match"], alu_override["hex"], alu_override["mix"])]
            n += 1
            v.append({
                "label": "%02d_alu_%s_hdri_%s" % (n, re.sub(r"[^a-z0-9]+", "-", alu_popis.split(" ")[0].lower()), hdri_nazev),
                "popis": popis5(hdri_nazev, BASELINE_SILA, BASELINE_ROT, alu_popis, "nativni (modra)", "nativni (svetle seda)"),
                "flags": flags,
            })
    # 2) Suplik (celo) varianty - na baseline HDRI/ALU
    for suplik_popis, suplik_override in SUPLIK_VARIANTY:
        n += 1
        v.append({
            "label": "%02d_suplik_%s" % (n, re.sub(r"[^a-z0-9]+", "-", suplik_popis.split(" ")[0].lower())),
            "popis": popis5(BASELINE_HDRI_NAZEV, BASELINE_SILA, BASELINE_ROT, "nativni (Sandblasted aluminium)", suplik_popis, "nativni (svetle seda)"),
            "flags": ["--vd-tint", "%s:%s:%s" % (suplik_override["match"], suplik_override["hex"], suplik_override["mix"])],
        })
    # 3) CUB (plastove vyplne) varianty - na baseline HDRI/ALU
    for cub_popis, cub_override in CUB_VARIANTY:
        n += 1
        v.append({
            "label": "%02d_cub_%s" % (n, re.sub(r"[^a-z0-9]+", "-", cub_popis.split(" ")[0].lower())),
            "popis": popis5(BASELINE_HDRI_NAZEV, BASELINE_SILA, BASELINE_ROT, "nativni (Sandblasted aluminium)", "nativni (modra)", cub_popis),
            "flags": ["--vd-tint", "%s:%s:%s" % (cub_override["match"], cub_override["hex"], cub_override["mix"])],
        })
    return v


VARIANTY = build_varianty()


def env():
    d = {}
    for line in open(os.path.join(REPO, "api", ".env"), encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        d[k] = v
    return d


def db_conn():
    import pymysql
    e = env()
    return pymysql.connect(host=e["DB_HOST"], port=int(e.get("DB_PORT", 3306)),
                            user=e["DB_USER"], password=e["DB_PASSWORD"],
                            database=e["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)


def ensure_drive_folder():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s",
                        (RENDERING_TOP_FOLDER_ID, DRIVE_FOLDER_NAME))
            row = cur.fetchone()
            if row:
                return row["id"]
            cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
                        (RENDERING_TOP_FOLDER_ID, DRIVE_FOLDER_NAME, ROBERT_APP_USER_ID))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def register_drive_file(folder_id, display_name, src_path, content_type):
    ext = os.path.splitext(display_name)[1].lstrip(".").lower() or "bin"
    stored_name = "%s.%s" % (os.urandom(16).hex(), ext)
    dest = os.path.join(DRIVE_FILES_DIR, stored_name)
    size = os.path.getsize(src_path)
    with open(src_path, "rb") as fsrc, open(dest, "wb") as fdst:
        fdst.write(fsrc.read())
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, "
                "size_bytes, uploaded_by) VALUES (%s,%s,%s,%s,%s,%s)",
                (folder_id, display_name[:255], stored_name, content_type, size, ROBERT_APP_USER_ID),
            )
        conn.commit()
    finally:
        conn.close()


def dispatch(flags):
    cmd = [PY, RENDER_SCRIPT, ASSEMBLY_ID, "--prstenec", "--samples", "100"] + flags
    child_env = dict(os.environ)
    child_env["KONFIGURATOR_RENDER_KLIC_SOUBOR"] = "/root/.konfigurator_render_klic"
    child_env.setdefault("BOT_ID", "bot10")
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=90, env=child_env)
    out = proc.stdout + proc.stderr
    if proc.returncode != 0:
        raise RuntimeError("dispatch selhal (rc=%d):\n%s" % (proc.returncode, out))
    m = re.search(r"Uloha ([0-9a-f]{16,40}) pripravena", out)
    if not m:
        raise RuntimeError("nenasel jsem job id ve vystupu:\n%s" % out)
    return m.group(1)


def wait_done(job_id, timeout_s=600):
    status_path = os.path.join(RENDER_OUT_DIR, "%s.status.json" % job_id)
    t0 = time.time()
    last_state = None
    while time.time() - t0 < timeout_s:
        if os.path.exists(status_path):
            try:
                st = json.load(open(status_path, encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                st = None
            if st:
                if st.get("state") != last_state:
                    last_state = st.get("state")
                    print("    stav: %s" % last_state, flush=True)
                if st.get("state") in ("done", "error"):
                    return st
        time.sleep(4)
    raise TimeoutError("uloha %s nedobehla do %ds" % (job_id, timeout_s))


def newest_frame(job_id):
    frames_dir = os.path.join(RENDER_OUT_DIR, "%s.frames" % job_id)
    cands = [f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".jpg")]
    if not cands:
        raise RuntimeError("zadny frame_*.jpg v %s" % frames_dir)
    t1024 = [f for f in cands if "_t1024" in f]
    vyber = sorted(t1024 or cands)[0]
    return os.path.join(frames_dir, vyber)


def main():
    folder_id = ensure_drive_folder()
    print("Sdileny disk slozka id=%d (Rendering -> %s)" % (folder_id, DRIVE_FOLDER_NAME), flush=True)
    popis_lines = [
        "Porovnani MATERIALU - vanDrawee (Robert 2026-09-23, druhe kolo)",
        "Sestava: assembly_id=%s, 100 Cycles vzorku, jeden pohled (--prstenec).\n" % ASSEMBLY_ID,
        "Kazdy radek = VSECH PET os najednou (i kdyz se nemeni vuci baseline):\n",
    ]
    celkem = len(VARIANTY)
    print("Celkem variant: %d" % celkem, flush=True)
    for i, v in enumerate(VARIANTY, 1):
        print("[%d/%d] %s" % (i, celkem, v["popis"]), flush=True)
        pokusy = 0
        while True:
            try:
                job_id = dispatch(v["flags"])
                break
            except RuntimeError as e:
                if "ODMITNUTO" in str(e) and "uz ceka" in str(e) and pokusy < 5:
                    pokusy += 1
                    print("    fronta obsazena, cekam 15s...", flush=True)
                    time.sleep(15)
                    continue
                raise
        print("    uloha %s zarazena, cekam na dokonceni..." % job_id, flush=True)
        st = wait_done(job_id)
        if st.get("state") != "done":
            print("    CHYBA: %s" % st.get("error"), flush=True)
            popis_lines.append("%s.jpg  CHYBA (%s): %s" % (v["label"], st.get("error"), v["popis"]))
            continue
        src = newest_frame(job_id)
        display_name = "%s.jpg" % v["label"]
        register_drive_file(folder_id, display_name, src, "image/jpeg")
        print("    OK -> Sdileny disk/%s (job %s, render %.1fs)"
              % (display_name, job_id, st.get("render_seconds") or 0), flush=True)
        popis_lines.append("%s\n  %s\n" % (display_name, v["popis"]))
    popis_path = "/tmp/2026-09-23b_material_porovnani_POPIS.txt"
    with open(popis_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(popis_lines) + "\n")
    register_drive_file(folder_id, "POPIS.txt", popis_path, "text/plain")
    os.remove(popis_path)
    print("\nHOTOVO. Sdileny disk -> Rendering -> %s" % DRIVE_FOLDER_NAME, flush=True)


if __name__ == "__main__":
    main()
