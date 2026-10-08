#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Systematicke srovnani nastaveni renderu pro vanDrawee (Robert 2026-09-23):
"potrebuji nejak systematicky videt mnoho renderu ruznych nastaveni (vcetne
popisu nastaveni) aby to slo rychle tak vzorky jen 100" + "je potreba take
zkusit otacet mapu HDRI" + "renderuj testy, chci videt desitky kombinaci".

Jeden pohled (--prstenec) na testovaci sestavu 672 (Fiat Ducato L1H1
regal), 100 Cycles vzorku, sekvencne (idempotence v turntable_render.py
povoluje jen 1 aktivni ulohu na sestavu).

DULEZITE (oprava 2026-09-23 po Robertove "kde to mam hledat"): "Sdileny
disk" v adminu (api/drive.py) NENI proste adresar na disku - cte se z DB
(shared_drive_folders/shared_drive_files). Kazdy hotovy render se proto
rovnou REGISTRUJE do techto tabulek (ne jen zkopiruje do OUT_DIR), aby se
objevil v adminu Sdileny disk -> Rendering -> [nazev slozky teto davky].
"""
import json, os, re, subprocess, time

REPO = "/opt/konfigurator"
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
RENDER_SCRIPT = os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py")
RENDER_OUT_DIR = os.path.join(REPO, "private-files", "blender-renders")
DRIVE_FILES_DIR = os.path.join(REPO, "private-files", "shared-drive")
RENDERING_TOP_FOLDER_ID = 42  # "Rendering" - existujici top-level slozka Sdileneho disku
DRIVE_FOLDER_NAME = "2026-09-23 porovnani nastaveni (vanDrawee)"
ROBERT_APP_USER_ID = 1  # app_users.id pro mandik@logiman.cz - pouzito jako created_by/uploaded_by
ASSEMBLY_ID = "672"
SHOP_PRODUCT_ID = 4903  # vanDrawee Ducato test - jediny s nativni_material=1 pouzity tady
HDRI_KATALOG = os.path.join(REPO, "webapp", "katalog", "hdri")
HDRI_SHARED = os.path.join(REPO, "private-files", "shared-drive-named", "Rendering", "HDRi")


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


def set_nativni_material(hodnota):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE shop_products SET nativni_material=%s WHERE id=%s",
                        (hodnota, SHOP_PRODUCT_ID))
        conn.commit()
    finally:
        conn.close()


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


ROTACE = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]
HDRI_VOLBY = [
    ("canary_wharf_8k", None),  # aktualni vychozi z app_settings, zadny --hdri override
    ("canary_wharf_4k", os.path.join(HDRI_KATALOG, "canary_wharf_4k.exr")),
    ("docklands_01_4k", os.path.join(HDRI_SHARED, "docklands_01_4k.hdr")),
    ("docklands_02_2k", os.path.join(HDRI_KATALOG, "docklands_02_2k.exr")),
    ("studio_small_08_4k", os.path.join(HDRI_SHARED, "studio_small_08_4k.exr")),
    ("brown_photostudio_02_4k", os.path.join(HDRI_SHARED, "brown_photostudio_02_4k.exr")),
    ("crossfit_gym_2k", os.path.join(HDRI_SHARED, "crossfit_gym_2k.exr")),
    ("abandoned_garage_2k", os.path.join(HDRI_KATALOG, "abandoned_garage_2k.exr")),
]
SILY = [0.3, 0.5, 0.75, 1.25, 1.5, 2.0, 3.0]


def build_varianty():
    v = [{
        "label": "00_baseline_aktualni_vychozi",
        "popis": "AKTUALNI VYCHOZI NASTAVENI ZIVE V ADMINU (canary_wharf_8k, rotace 120, sila 1.0, sablonova svetla ZAPNUTA, nativni material z FBX)",
        "flags": [],
    }]
    n = 1
    # HDRI VOLBA x ROTACE (0/120/240) - hlavni sada, kazda HDRI mapa ve 3 natoceni
    for hdri_nazev, hdri_cesta in HDRI_VOLBY:
        for rot in (0, 120, 240):
            if hdri_cesta is None and rot == 120:
                continue  # presne = baseline (00), nerenderovat 2x
            flags = ["--hdri-rotace-deg", str(rot)]
            if hdri_cesta:
                flags += ["--hdri", hdri_cesta]
            v.append({"label": "%02d_hdri_%s_rot%03d" % (n, hdri_nazev, rot),
                      "popis": "HDRI=%s, rotace=%d stupnu (sila 1.0, svetla sablony zap., nativni material)" % (hdri_nazev, rot),
                      "flags": flags})
            n += 1
    # jemny sweep rotace na baseline HDRI (zbyvajici uhly po 30 stupnich)
    for rot in ROTACE:
        if rot in (0, 120, 240):
            continue  # uz pokryto vyse
        v.append({"label": "%02d_rotace_%03d" % (n, rot),
                  "popis": "jen rotace HDRI %d stupnu (canary_wharf_8k, jinak baseline)" % rot,
                  "flags": ["--hdri-rotace-deg", str(rot)]})
        n += 1
    # sila HDRI na baseline HDRI/rotaci
    for sila in SILY:
        v.append({"label": "%02d_sila_%s" % (n, sila),
                  "popis": "jen sila HDRI x%s (baseline HDRI/rotace, svetla sablony zap.)" % sila,
                  "flags": ["--hdri-sila", str(sila)]})
        n += 1
    # svetla x material krizem (00 baseline = jen_hdri:0/native:1 uz existuje)
    for jen_hdri, native in ((True, True), (False, False), (True, False)):
        flags = ["--jen-hdri"] if jen_hdri else []
        popis = "svetla sablony %s, material %s (baseline HDRI/rotace/sila)" % (
            "VYPNUTA (jen HDRI)" if jen_hdri else "ZAPNUTA",
            "NATIVNI (z FBX)" if native else "VYPOCTENY (Logiman fallback)")
        varianta = {"label": "%02d_svetla_%s_material_%s" % (n, "hdri" if jen_hdri else "sablona",
                                                              "nativni" if native else "vypocteny"),
                    "popis": popis, "flags": flags}
        if not native:
            varianta["nativni_material"] = 0
        v.append(varianta)
        n += 1
    return v


VARIANTY = build_varianty()


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
        "Systematicke porovnani nastaveni renderu - vanDrawee (Robert 2026-09-23)",
        "Sestava: assembly_id=%s (vanDrawee EXPORT test render - Fiat Ducato L1H1), "
        "100 Cycles vzorku, jeden pohled (--prstenec) shodny pro vsechny snimky." % ASSEMBLY_ID,
        "",
    ]
    celkem = len(VARIANTY)
    print("Celkem variant: %d" % celkem, flush=True)
    hotovo, chyby = 0, 0
    for i, v in enumerate(VARIANTY, 1):
        print("[%d/%d] %s - %s" % (i, celkem, v["label"], v["popis"]), flush=True)
        if "nativni_material" in v:
            set_nativni_material(v["nativni_material"])
        try:
            pokusy = 0
            while True:
                try:
                    job_id = dispatch(v["flags"])
                    break
                except RuntimeError as e:
                    if "ODMITNUTO" in str(e) and "uz ceka" in str(e) and pokusy < 5:
                        pokusy += 1
                        print("    fronta obsazena (jina uloha na %s), cekam 15s..." % ASSEMBLY_ID, flush=True)
                        time.sleep(15)
                        continue
                    raise
            print("    uloha %s zarazena, cekam na dokonceni..." % job_id, flush=True)
            st = wait_done(job_id)
            if st.get("state") != "done":
                print("    CHYBA: %s" % st.get("error"), flush=True)
                popis_lines.append("%s.jpg  CHYBA (%s): %s" % (v["label"], st.get("error"), v["popis"]))
                chyby += 1
                continue
            src = newest_frame(job_id)
            display_name = "%s.jpg" % v["label"]
            register_drive_file(folder_id, display_name, src, "image/jpeg")
            hotovo += 1
            print("    OK -> Sdileny disk/%s (job %s, render %.1fs)"
                  % (display_name, job_id, st.get("render_seconds") or 0), flush=True)
            popis_lines.append("%s  (job %s)  %s" % (display_name, job_id, v["popis"]))
        finally:
            if "nativni_material" in v:
                set_nativni_material(1)
    popis_path = "/tmp/2026-09-23_vandrawee_render_porovnani_POPIS.txt"
    with open(popis_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(popis_lines) + "\n")
    register_drive_file(folder_id, "POPIS.txt", popis_path, "text/plain")
    os.remove(popis_path)
    print("\nHOTOVO. %d/%d OK, %d chyb. Sdileny disk -> Rendering -> %s"
          % (hotovo, celkem, chyby, DRIVE_FOLDER_NAME), flush=True)


if __name__ == "__main__":
    main()
