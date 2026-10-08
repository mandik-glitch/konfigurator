#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nahledy NAVRHU razitek pro Roberta (2026-09-24: "chci od tebe ukazky
sestav a na nich tvoje navrhy razitek", "ukazky mi staci z cpu renderu").

Pro jednu kartu:
  1. spusti generator v --dry-run (NIC nezapisuje do DB) -> SOUHRN_JSON
     (pocet poli, celo, pozadovane/umistene pocty) + RAZITKA_JSON (navrh);
  2. pro kazdou ze 4 stran zaradi --prstenec snimek (100 vzorku) pres
     turntable_render.py --local --razitka-json <navrh> a spusti lokalni
     CPU render Blenderem 5.2 (4.2.9 z /opt/blender-official neotevre
     sablonu X30-02.blend ani vd_materialy.blend - overeno);
  3. sklizeny snimek (t2048, Robert: "v plnem rozliseni") zaregistruje do
     Sdileneho disku (Rendering -> slozka) s nazvem nesoucim kartu, pocet
     poli, stranu a razitka umistena/pozadovana na te strane;
  4. lokalni ulohu oznaci `cancelled` (dokumentovany terminalni stav), aby
     nedrzela idempotencni zamek "1 aktivni uloha na produkt".

Zadny zapis do shop_products - vandr-render-dispatch timer reaguje na
kazdou zmenu vandr_razitka_json a pustil by ostry render neschvaleneho
navrhu. Do DB jdou razitka az po Robertove schvaleni (spocitat.py bez
--dry-run).

POUZITI:
  api/venv/bin/python3 scripts/2026-09-24_vandrawee_razitka_nahledy.py --karta 4904 \
      [--strany predni,zadni,leva,prava] [--slozka "..."] [--samples 100]
"""
import argparse, json, os, re, shlex, subprocess, time

REPO = "/opt/konfigurator"
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
BLENDER52 = "/opt/blender-5.2/blender"
GENERATOR = os.path.join(REPO, "scripts", "2026-09-23_vandr_razitka_spocitat.py")
RENDER_SCRIPT = os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py")
RENDER_OUT_DIR = os.path.join(REPO, "private-files", "blender-renders")
KATALOG_DIR = os.path.join(REPO, "webapp", "katalog")
DRIVE_FILES_DIR = os.path.join(REPO, "private-files", "shared-drive")
RENDERING_TOP_FOLDER_ID = 42
ROBERT_APP_USER_ID = 1
STRANY_POSUN = {"predni": 0, "prava": 90, "zadni": 180, "leva": 270}


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


def glb_karty(karta):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name, glb_file FROM shop_products WHERE id=%s", (karta,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or not row["glb_file"]:
        raise SystemExit("karta %s neexistuje nebo nema glb_file" % karta)
    return row["name"], os.path.join(KATALOG_DIR, row["glb_file"])


def ensure_drive_folder(name):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s",
                        (RENDERING_TOP_FOLDER_ID, name))
            row = cur.fetchone()
            if row:
                return row["id"]
            cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
                        (RENDERING_TOP_FOLDER_ID, name, ROBERT_APP_USER_ID))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def register_drive_file(folder_id, display_name, src_path, content_type):
    ext = os.path.splitext(display_name)[1].lstrip(".").lower() or "bin"
    stored = "%s.%s" % (os.urandom(16).hex(), ext)
    dest = os.path.join(DRIVE_FILES_DIR, stored)
    with open(src_path, "rb") as fsrc, open(dest, "wb") as fdst:
        fdst.write(fsrc.read())
    size = os.path.getsize(dest)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, "
                "size_bytes, uploaded_by) VALUES (%s,%s,%s,%s,%s,%s)",
                (folder_id, display_name[:255], stored, content_type, size, ROBERT_APP_USER_ID),
            )
        conn.commit()
    finally:
        conn.close()


def dry_run_generator(karta, glb_path):
    """Vrati (souhrn, razitka). NIC nezapisuje (--dry-run)."""
    proc = subprocess.run([BLENDER52, "-b", "-noaudio", "-P", GENERATOR, "--",
                           glb_path, "--shop-product-id", str(karta), "--dry-run"],
                          cwd=REPO, capture_output=True, text=True, timeout=600)
    out = proc.stdout + proc.stderr
    m_s = re.search(r"^SOUHRN_JSON: (.*)$", out, re.M)
    m_r = re.search(r"RAZITKA_JSON: (.*)$", out, re.M)
    if not m_s or not m_r:
        raise SystemExit("generator nevratil SOUHRN_JSON/RAZITKA_JSON (rc=%d):\n%s" % (proc.returncode, out[-3000:]))
    souhrn = json.loads(m_s.group(1))
    razitka = json.loads(m_r.group(1))
    for line in out.splitlines():
        if line.startswith(("NOHY:", "CELO:", "POCTY PO STRANACH:", "VAROVANI", "EXPONOVANOST")):
            print("    " + line)
    return souhrn, razitka


def zarad_local(karta, azimut, samples, razitka_path):
    cmd = [PY, RENDER_SCRIPT, "--shop-product-id", str(karta), "--prstenec", "--samples", str(samples),
           "--azimut", str(int(azimut) % 360), "--local", "--razitka-json", razitka_path]
    child_env = dict(os.environ)
    child_env["KONFIGURATOR_RENDER_KLIC_SOUBOR"] = "/root/.konfigurator_render_klic"
    child_env.setdefault("BOT_ID", "bot10")
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=180, env=child_env)
    out = proc.stdout + proc.stderr
    if proc.returncode != 0:
        raise RuntimeError("zarazeni selhalo (rc=%d):\n%s" % (proc.returncode, out))
    m_job = re.search(r"Uloha ([0-9a-f]{16,40}) pripravena", out)
    m_cmd = re.search(r"^\s*(/opt/\S*blender\S*)\s+(-b .*)$", out, re.M)
    if not m_job or not m_cmd:
        raise RuntimeError("nenasel jsem job id nebo lokalni prikaz:\n%s" % out)
    m_az = re.search(r"\(el (-?\d+) / az (\d+),", out)
    az_real = m_az.group(2) if m_az else "?"
    # 4.2.9 (/opt/blender-official) neotevre 5.2 soubory - lokalne vzdy 5.2.
    local_cmd = [BLENDER52] + shlex.split(m_cmd.group(2))
    return m_job.group(1), az_real, local_cmd


def render_local(local_cmd, timeout_s):
    t0 = time.time()
    proc = subprocess.run(local_cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout_s)
    dt = time.time() - t0
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-2500:]
        raise RuntimeError("lokalni render selhal (rc=%d, %.0fs):\n%s" % (proc.returncode, dt, tail))
    return dt


def best_frame(job_id):
    frames_dir = os.path.join(RENDER_OUT_DIR, "%s.frames" % job_id)
    if not os.path.isdir(frames_dir):
        raise RuntimeError("chybi %s" % frames_dir)
    cands = [f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".jpg")]
    if not cands:
        raise RuntimeError("zadny frame_*.jpg v %s" % frames_dir)
    velke = [f for f in cands if "_t2048" in f]
    return os.path.join(frames_dir, sorted(velke or cands)[0])


def zrus_lokalni_ulohu(job_id, poznamka):
    """Lokalni uloha zustava po renderu ve stavu 'queued' (zadny worker ji
    neingestuje) a drzela by idempotencni zamek 1 aktivni uloha/produkt -
    `cancelled` je dokumentovany terminalni stav (viz turntable_render.py)."""
    p = os.path.join(RENDER_OUT_DIR, "%s.status.json" % job_id)
    try:
        st = json.load(open(p, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        st = {}
    st.update({"state": "cancelled", "note": poznamka, "updated": time.time()})
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser(description="Nahledy navrhu razitek (4 strany) jedne Vandr karty -> Sdileny disk, bez zapisu do DB")
    ap.add_argument("--karta", type=int, required=True)
    ap.add_argument("--strany", default="predni,zadni,leva,prava")
    ap.add_argument("--slozka", default="2026-09-24 navrhy razitek (vanDrawee)")
    ap.add_argument("--samples", type=int, default=100)
    ap.add_argument("--timeout", type=int, default=3600, help="max s na jeden lokalni CPU snimek")
    a = ap.parse_args()

    name, glb_path = glb_karty(a.karta)
    print("KARTA %d: %s" % (a.karta, name), flush=True)
    print("[dry-run generatoru]", flush=True)
    souhrn, razitka = dry_run_generator(a.karta, glb_path)
    pole = souhrn["pocet_sloupcu"]
    predni_az = souhrn["predni_azimut_rig"]
    pozad, umist = souhrn.get("pozadovane", {}), souhrn.get("umistene", {})
    print("  poli=%d, celo podle: %s, predni azimut rig=%s, pozadovane=%s, umistene=%s%s"
          % (pole, souhrn.get("celo_podle"), predni_az, pozad, umist,
             (" NEDOSTATEK=%s" % souhrn["nedostatek"]) if souhrn.get("nedostatek") else ""), flush=True)

    razitka_path = "/tmp/razitka_navrh_%d.json" % a.karta
    with open(razitka_path, "w", encoding="utf-8") as fh:
        json.dump(razitka, fh, ensure_ascii=False)

    folder_id = ensure_drive_folder(a.slozka)
    popis = ["Karta %d - %s" % (a.karta, name),
             "poli: %d (pozic noh %d, nohy: %s) | celo: %s | predni azimut rig: %s"
             % (pole, souhrn.get("pocet_pozic_noh"), souhrn.get("metoda_noh"), souhrn.get("celo_podle"), predni_az),
             "pozadovane: %s | umistene: %s | nedostatek: %s" % (pozad, umist, souhrn.get("nedostatek") or "-"),
             "exponovanych kandidatu po stranach: %s" % souhrn.get("exponovanych"), ""]

    for strana in [s.strip() for s in a.strany.split(",") if s.strip()]:
        az = (predni_az + STRANY_POSUN[strana]) % 360
        chce, ma = pozad.get(strana, 0), umist.get(strana, 0)
        label = "%d_%dpole_%s_az%03d_razitka%d-z-%d%s" % (
            a.karta, pole, strana, az, ma, chce, "" if ma == chce else "_NEDOSTATEK")
        print("[%s] azimut %d, razitka %d/%d" % (strana, az, ma, chce), flush=True)
        try:
            job_id, az_real, local_cmd = zarad_local(a.karta, az, a.samples, razitka_path)
            print("    uloha %s (rig az %s), lokalni CPU render..." % (job_id, az_real), flush=True)
            dt = render_local(local_cmd, a.timeout)
            src = best_frame(job_id)
            display = label + ".jpg"
            register_drive_file(folder_id, display, src, "image/jpeg")
            zrus_lokalni_ulohu(job_id, "lokalni nahled navrhu razitek (bot10), snimek v Sdilenem disku: %s" % display)
            popis.append("%s  (rig az %s, %.0fs CPU, job %s)" % (display, az_real, dt, job_id))
            print("    OK -> %s (%.0fs)" % (display, dt), flush=True)
        except Exception as e:  # jedna strana nesmi shodit zbytek, ale musi byt videt
            print("    CHYBA: %s" % e, flush=True)
            popis.append("%s  CHYBA: %s" % (label, str(e)[:300]))

    tmp = "/tmp/popis_razitka_%d.txt" % a.karta
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(popis) + "\n")
    register_drive_file(folder_id, "POPIS_%d.txt" % a.karta, tmp, "text/plain")
    os.remove(tmp)
    os.remove(razitka_path)
    print("\nHOTOVO karta %d -> Sdileny disk / Rendering / %s" % (a.karta, a.slozka), flush=True)


if __name__ == "__main__":
    main()
