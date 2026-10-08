#!/usr/bin/env python3
"""2026-09-23_vandr_fbx_konverze_auto_dispatch.py - automat: najde Vandr
karty s hotovym FBX exportem (vandrawee_work.stored_models.
fbx_exported_at) a bez GLB v katalogu a prevede je (FBXLoader ->
sanitizace -> mm skalovani -> nasazeni), stejny vzor jako
2026-09-23_vandr_razitka_auto_dispatch.py (oneshot + systemd timer).

Robert primo, 2026-09-23: "udelej ten automat" (po rucni jednorazove
davce 8 karet, kdyz bot10 nemel cas resit konverze - "kdyz se te na
neco ptam tak je asi logicke ze ho chcu udelat").

POUZITY POSTUP JE BOT10UV, JIZ OVERENY (viz scripts/2026-09-20_
vandrawee_real_export/README.md a VANDR_RENDER_HOWTO.md sekce "Skutecny
export CELE sestavy z appky") - tenhle skript jen automatizuje jeho
RUCNI spousteni, nezavadi novou logiku konverze samotne.

CO DELA:
  1. Najde `vandrawee_work.stored_models` s `fbx_exported_at IS NOT
     NULL`, spáruje s `shop_products` (sku = 'VD-<uuid>'), vybere ty
     s `glb_file IS NULL` (jeste neprevedene).
  2. Pro kazdou: zkopiruje zdrojovy FBX, prevede pres patchnuty
     FBXLoader v headless Chromium (2026-09-23_vandr_fbx_konverze_
     prohlizec.js), sanitizuje NaN/Inf, preskaluje metry->mm.
  3. OVERI pred nasazenim (bezpecnostni brzdy, ne jen "export nehlasil
     chybu"):
     - mesh count > 0
     - bbox vsech 3 os v rozumnem rozsahu pro regal (200-6000mm)
     - dominantni hlavni profil (NNxNNxLLL vzor, nejcastejsi prurez)
       je v jiz OVERENE mnozine (40x40 nebo 45x45, viz VANDR_RENDER_
       HOWTO.md bod 4 "T-drazka") - NOVY, nezname velky profil se
       NEnasadi automaticky (potrebuje rucni raycast overeni drazky,
       stejne jako u kazdeho dosavadniho typu vozidla), jen se nahlasi.
  4. Nasadi GLB do webapp/katalog/ (DEPLOY_LOCK, git commit), aktualizuje
     shop_products.glb_file.
  5. Chyby track po jednotlivych kartach (sha256 zdrojoveho FBX) -
     stejny "chyba_otisk" vzor jako u razitkoveho automatu, ZADNE
     opakovane hlaseni "failed" navzdy na stejnem, jiz znamem problemu
     (bot3 2026-09-23 nalez, viz 52941da1).
  6. ZADNA razitka se tady nepocitaji - to je samostatny krok
     (2026-09-23_vandr_razitka_auto_dispatch.py), ktery si novou kartu
     s cerstvym glb_file sam vsimne pri svem dalsim behu.

Pouziti:
    python3 scripts/2026-09-23_vandr_fbx_konverze_auto_dispatch.py [--dry-run]
"""
import argparse
import hashlib
import http.server
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unicodedata

REPO = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep + "scripts", 1)[0]
KATALOG_DIR = os.path.join(REPO, "webapp", "katalog")
EXPORT_PIPELINE_DIR = os.path.join(REPO, "scripts", "2026-09-20_vandrawee_real_export")
PROHLIZEC_SKRIPT = os.path.join(REPO, "scripts", "2026-09-23_vandr_fbx_konverze_prohlizec.js")
VANDRAWEE_ENV_PATH = "/opt/vandrawee/web/.env"
VANDRAWEE_STORAGE_DIR = "/opt/vandrawee/web/storage/app/exported_models"

# ⭐ Jen tyhle prurezy maji overenou T-drazku (viz VANDR_RENDER_HOWTO.md
# bod 4/5) - novy/neznamy hlavni profil se NEnasadi automaticky, i kdyz
# konverze samotna probehne bez chyby. Rozsirovat JEN po rucnim raycast
# overeni drazky na novem typu, ne "zkusit a uvidime".
#
# (30, 30) pridano bot10 2026-09-25 po zmereni na karte #4586 (VD-f3007b39)
# - priruba 15,000/dno 5,000/sirka drazky 8,200mm, novy dil vypln_placka_30
# (222.204x11x8.2mm) sedi na vsech 5 zmerenych 30x30 objektech te karty
# (viz AGENTS_LOG.md a VANDR_RENDER_HOWTO.md bod 4). Zaroven opraven
# `cand_re` o par radku niz (chybel "SL" pismenny prefix, ktery uz ma
# KANDIDATNI_VZOR_RE v razitkovaci skriptu od 2026-09-24) - #4586 byl
# blokovan falesne: bez prefixu vysel hlavni profil (30,30) 12:10, se
# spravnym regexem (40,40) 24:12 (SL-pricky se predtim vubec nepocitaly).
# Oba profily proto zustavaji v teto mnozine - (40,40)/(45,45) uz drive
# overene, (30,30) nove overene, oprava regexu jen doresila, KTERY z nich
# se u konkretni karty spravne rozpozna jako hlavni.
OVERENE_PROFILY = {(30, 30), (40, 40), (45, 45)}
BBOX_MIN_MM = 200.0
BBOX_MAX_MM = 6000.0


def _konfigurator_env():
    env = {}
    for line in open(os.path.join(REPO, "api", ".env")):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return env


def _vandrawee_env():
    env = {}
    with open(VANDRAWEE_ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _pymysql():
    import glob
    venv_site = glob.glob(os.path.join(REPO, "api", "venv", "lib", "python3.*", "site-packages"))
    if venv_site and venv_site[0] not in sys.path:
        sys.path.insert(0, venv_site[0])
    import pymysql
    return pymysql


def _konfigurator_conn():
    pymysql = _pymysql()
    env = _konfigurator_env()
    return pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
                            user=env["DB_USER"], password=env["DB_PASSWORD"],
                            database=env["DB_NAME"], charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor)


def _vandrawee_conn():
    pymysql = _pymysql()
    env = _vandrawee_env()
    return pymysql.connect(host=env.get("DB_HOST", "127.0.0.1"), port=int(env.get("DB_PORT", 3306)),
                            user=env["DB_USERNAME"], password=env["DB_PASSWORD"],
                            database="vandrawee_work", charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor)


def _sha256_souboru(cesta):
    h = hashlib.sha256()
    with open(cesta, "rb") as fh:
        for blok in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(blok)
    return h.hexdigest()


def _slugify(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "vandr"


def najdi_kandidaty(k_conn, v_conn):
    """Vraci (kandidati, zkontrolovano, bez_karty, preskoceno_znama_chyba).
    kandidat = dict(shop_product_id, name, uuid, fbx_path)."""
    with v_conn.cursor() as cur:
        cur.execute("SELECT LOWER(HEX(uuid)) uuid_hex FROM stored_models WHERE fbx_exported_at IS NOT NULL")
        uuid_hexy = [r["uuid_hex"] for r in cur.fetchall()]

    kandidati, bez_karty, preskoceno_znama_chyba = [], [], []
    zkontrolovano = len(uuid_hexy)
    with k_conn.cursor() as cur:
        for h in uuid_hexy:
            uuid_str = "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])
            sku = "VD-%s" % uuid_str
            cur.execute("SELECT id, name, glb_file, vandr_konverze_chyba_fbx_otisk "
                        "FROM shop_products WHERE sku=%s", (sku,))
            row = cur.fetchone()
            if not row:
                bez_karty.append(sku)
                continue
            if row["glb_file"]:
                continue  # uz prevedeno
            fbx_path = os.path.join(VANDRAWEE_STORAGE_DIR, uuid_str, "%s.fbx" % uuid_str)
            if not os.path.isfile(fbx_path):
                bez_karty.append(sku + " (FBX soubor chybi na disku)")
                continue
            fbx_otisk = _sha256_souboru(fbx_path)
            if fbx_otisk == (row["vandr_konverze_chyba_fbx_otisk"] or ""):
                preskoceno_znama_chyba.append(row["id"])
                continue
            kandidati.append({"shop_product_id": row["id"], "name": row["name"],
                              "uuid": uuid_str, "fbx_path": fbx_path, "fbx_otisk": fbx_otisk})
    return kandidati, zkontrolovano, bez_karty, preskoceno_znama_chyba


def priprav_render3d(scratch_dir):
    """Jednorazove zkopiruje sdilene three.js assety (viz README.md v
    2026-09-20_vandrawee_real_export/) do scratch adresare, ktery pak
    slouzi jako dokument-root pro lokalni HTTP server."""
    r3d = os.path.join(scratch_dir, "render3d")
    for sub in ("jsm/loaders", "jsm/libs", "jsm/curves", "jsm/exporters"):
        os.makedirs(os.path.join(r3d, sub), exist_ok=True)
    shutil.copy(os.path.join(REPO, "node_modules/three/build/three.module.js"), r3d)
    shutil.copy(os.path.join(EXPORT_PIPELINE_DIR, "FBXLoader_patched.js"),
                os.path.join(r3d, "jsm/loaders/FBXLoader.js"))
    shutil.copy(os.path.join(REPO, "node_modules/three/examples/jsm/exporters/GLTFExporter.js"),
                os.path.join(r3d, "jsm/exporters/"))
    for f in os.listdir(os.path.join(REPO, "node_modules/three/examples/jsm/libs")):
        src = os.path.join(REPO, "node_modules/three/examples/jsm/libs", f)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(r3d, "jsm/libs", f))
    for f in os.listdir(os.path.join(REPO, "node_modules/three/examples/jsm/curves")):
        if f.endswith(".js"):
            shutil.copy(os.path.join(REPO, "node_modules/three/examples/jsm/curves", f),
                        os.path.join(r3d, "jsm/curves", f))
    shutil.copy(os.path.join(EXPORT_PIPELINE_DIR, "convert_template.html"),
                os.path.join(r3d, "convert.html"))
    return r3d


def spust_http_server(document_root):
    """ThreadingHTTPServer na nahodnem volnem portu (bind port=0), bezi
    v démonickem vlakne po celou dobu behu automatu - staci jeden pro
    celou davku kandidatu, ne jeden na soubor."""
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=document_root, **kwargs)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def preved_jeden(r3d, http_port, fbx_path, scratch_dir):
    """FBXLoader (prohlizec) -> sanitizace -> mm skalovani. Vraci
    (ok, final_glb_path_nebo_None, hlaseni)."""
    shutil.copy(fbx_path, os.path.join(r3d, "model.fbx"))
    raw = os.path.join(scratch_dir, "raw.glb")
    proc = subprocess.run(
        ["node", PROHLIZEC_SKRIPT, "http://127.0.0.1:%d/convert.html" % http_port, raw],
        capture_output=True, text=True, timeout=60)
    vystup = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 or not os.path.isfile(raw):
        return False, None, "FBXLoader/export selhal: %s" % vystup.strip()

    sanitized = os.path.join(scratch_dir, "sanitized.glb")
    proc = subprocess.run(
        ["python3", os.path.join(EXPORT_PIPELINE_DIR, "sanitize_glb.py"), raw, sanitized],
        capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not os.path.isfile(sanitized):
        return False, None, "sanitize_glb.py selhal: %s" % (proc.stdout + proc.stderr).strip()

    final = os.path.join(scratch_dir, "final.glb")
    proc = subprocess.run(
        ["python3", os.path.join(EXPORT_PIPELINE_DIR, "scale_to_mm.py"), sanitized, final],
        capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not os.path.isfile(final):
        return False, None, "scale_to_mm.py selhal: %s" % (proc.stdout + proc.stderr).strip()

    return True, final, vystup.strip()


_OVERENI_BLENDER_SKRIPT = r"""
import sys, re, bpy
from mathutils import Vector
argv = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=argv[0])
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
minx=miny=minz=1e18; maxx=maxy=maxz=-1e18
for o in meshes:
    for c in o.bound_box:
        wc = o.matrix_world @ Vector(c)
        minx=min(minx,wc.x); maxx=max(maxx,wc.x)
        miny=min(miny,wc.y); maxy=max(maxy,wc.y)
        minz=min(minz,wc.z); maxz=max(maxz,wc.z)
cand_re = re.compile(r"^[A-Za-z_]*(\d+)x(\d+)x\d+", re.IGNORECASE)
pocty = {}
for o in meshes:
    m = cand_re.match(o.name or "")
    if m:
        key = tuple(sorted((int(m.group(1)), int(m.group(2)))))
        pocty[key] = pocty.get(key, 0) + 1
hlavni = max(pocty, key=pocty.get) if pocty else None
hlavni_str = ("%dx%d" % hlavni) if hlavni else "None"
print("OVERENI_VYSLEDEK mesh=%d bbox=%.1f,%.1f,%.1f hlavni_prurez=%s" % (
    len(meshes), maxx-minx, maxy-miny, maxz-minz, hlavni_str))
"""


def overit_final_glb(final_glb_path):
    """Bezpecnostni brzdy PRED nasazenim - vraci (ok, hlaseni, prurez).
    Nikdy nedeleguje na "export nehlasil chybu", meri primo vysledny
    soubor.

    `prurez` (bot10 2026-09-25, Robert: stitky na karte - hlavni profil
    + strana auta) je (a, b) tuple KDYKOLI se nejaky NNxNNxLLL kandidat
    najde, i kdyz jeste NENI v OVERENE_PROFILY (`ok=False` v tom
    pripade - karta se tak jako tak nenasadi, hodnota je jen pro
    hlaseni/log). `None` kdyz zadny kandidat vubec neni. Volajici
    (`nasad_a_zapis` i zpetny backfill) tenhle vysledek PRIMO ZAPISUJE
    do `shop_products.vandr_hlavni_prurez_mm` - ZADNY DALSI/JINY
    vypocet vedle, presne to je smysl navratove hodnoty."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as fh:
        fh.write(_OVERENI_BLENDER_SKRIPT)
        skript_path = fh.name
    try:
        proc = subprocess.run(
            ["/opt/blender-5.2/blender", "-b", "-P", skript_path, "--", final_glb_path],
            capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(skript_path)
    m = re.search(r"OVERENI_VYSLEDEK mesh=(\d+) bbox=([\d.]+),([\d.]+),([\d.]+) hlavni_prurez=(\S+)",
                  proc.stdout)
    if not m:
        return False, "Blender overeni se nespustilo/nevypsalo vysledek: %s" % (proc.stdout + proc.stderr)[-500:], None
    mesh_count = int(m.group(1))
    bbox = [float(m.group(2)), float(m.group(3)), float(m.group(4))]
    hlavni_str = m.group(5)
    if mesh_count == 0:
        return False, "0 mesh objektu v prevedenem GLB.", None
    if not all(BBOX_MIN_MM <= v <= BBOX_MAX_MM for v in bbox):
        return False, "bbox %s mm mimo rozumny rozsah (%d-%d mm) - podezreni na spatne jednotky." % (
            bbox, BBOX_MIN_MM, BBOX_MAX_MM), None
    if hlavni_str == "None":
        return True, "mesh=%d bbox=%s (ZADNY NNxNNxLLL kandidat nalezen - razitkovaci automat kartu preskoci)" % (
            mesh_count, bbox), None
    prurez = tuple(int(x) for x in hlavni_str.split("x"))
    if prurez not in OVERENE_PROFILY:
        return False, ("hlavni profil %s NENI v overene mnozine %s (T-drazka nikdy nezmerena "
                       "raycastem) - potreba rucni overeni pred nasazenim, viz VANDR_RENDER_HOWTO.md."
                       % (prurez, OVERENE_PROFILY)), prurez
    return True, "mesh=%d bbox=%s hlavni_prurez=%s" % (mesh_count, bbox, prurez), prurez


def nasad_a_zapis(k_conn, shop_product_id, name, uuid_str, final_glb_path, prurez):
    """Nasadi do webapp/katalog/vandr/ (DEPLOY_LOCK + git commit) a zapise
    shop_products.glb_file. Vraci (ok, hlaseni).

    `prurez` = navratova hodnota `overit_final_glb()` (tuple (a,b) nebo
    None) - zapisuje se do `vandr_hlavni_prurez_mm` ZAROVEN s glb_file,
    ne samostatnym krokem (bot10 2026-09-25, stitky na karte) - profil
    je vzdy ctvercovy (min(prurez)==max(prurez), overeno na 30/40/45),
    SMALLINT drzi jen jedno cislo stejne jako product_assemblies.profil_mm.

    Bot5 2026-09-23, bezpecnostni oprava: Vandr GLB byly (na rozdil od
    nativnich sestav, kde se glb_file na kartu NIKDY nenastavuje) verejne
    stahnutelne primo pres shop_products.glb_file - presunuto do chranene
    podslozky katalog/vandr/ (staff_required + X-Accel-Redirect, viz
    api/vandr_production_overview.py::vandr_glb_file, nginx `location
    /katalog/vandr/` blokuje primy staticky pristup). DB sloupec nese
    PREFIX "vandr/" (napr. "vandr/vd_export_...glb"), ne pouhy basename -
    render kod (os.path.join(KATALOG_DIR, glb_file)) to sklada spravne
    beze zmeny, protoze KATALOG_DIR je porad jen "webapp/katalog".

    Nazev souboru pouziva UUID karty (ne hash docasne cesty) - stejna
    konvence jako rucni davka (vd_export_<vozidlo>_<uuid8>.glb),
    DETERMINISTICKA (stejna karta = stejny nazev pri kazdem prepoctu,
    zadne hromadeni duplicitnich souboru pri opakovanem behu)."""
    fname_bez_prefixu = "vd_export_%s_%s.glb" % (_slugify(name)[:40], uuid_str.split("-")[0])
    fname = "vandr/%s" % fname_bez_prefixu
    dest = os.path.join(KATALOG_DIR, "vandr", fname_bez_prefixu)

    zamek = subprocess.run(
        ["bash", os.path.join(REPO, "scripts", "lock.sh"), "acquire", "bot4",
         "automat: nasazeni noveho Vandr GLB (%s)" % fname, "--wait"],
        capture_output=True, text=True, timeout=120, env={**os.environ, "BOT_ID": "bot4"})
    if zamek.returncode != 0:
        return False, "DEPLOY_LOCK acquire selhal: %s" % (zamek.stdout + zamek.stderr)
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy(final_glb_path, dest)
        commit = subprocess.run(
            ["git", "add", os.path.relpath(dest, REPO)], cwd=REPO,
            capture_output=True, text=True)
        if commit.returncode != 0:
            return False, "git add selhal: %s" % (commit.stdout + commit.stderr)
        commit = subprocess.run(
            ["git", "commit", "-m",
             "feat(vandr): automat - nova GLB konverze %s (shop_product %d)" % (fname, shop_product_id),
             "--", os.path.relpath(dest, REPO)],
            cwd=REPO, capture_output=True, text=True, env={**os.environ, "BOT_ID": "bot4"})
        if commit.returncode != 0:
            return False, "git commit selhal: %s" % (commit.stdout + commit.stderr)
    finally:
        subprocess.run(["bash", os.path.join(REPO, "scripts", "lock.sh"), "release", "bot4"],
                       capture_output=True, text=True, env={**os.environ, "BOT_ID": "bot4"})

    with k_conn.cursor() as cur:
        # nativni_material=1 (bot10 2026-09-23, ostry nalez): default je 0,
        # coz pri renderu spadne na DEFAULT_PART_COLOR (genericka seda,
        # zadna barva) - 11 z 13 GLB-ready Vandr karet melo tenhle bug,
        # protoze nic nikdy nenastavilo pravou hodnotu. Vsechny Vandr GLB
        # jsou monoliticky multi-material import (ne katalogovy 1-barva-
        # na-dil dil), takze tahle hodnota je VZDY 1, ne podminena.
        prurez_mm = prurez[0] if prurez and prurez[0] == prurez[1] else None
        if prurez and prurez_mm is None:
            print("VAROVANI: hlavni profil %s NENI ctvercovy - vandr_hlavni_prurez_mm "
                  "zustava NULL, potreba rucni rozhodnuti formatu stitku." % (prurez,))
        cur.execute("UPDATE shop_products SET glb_file=%s, nativni_material=1, "
                    "vandr_hlavni_prurez_mm=%s WHERE id=%s",
                    (fname, prurez_mm, shop_product_id))
    k_conn.commit()
    return True, fname


def zapis_znamou_chybu(k_conn, shop_product_id, fbx_otisk):
    with k_conn.cursor() as cur:
        cur.execute("UPDATE shop_products SET vandr_konverze_chyba_fbx_otisk=%s WHERE id=%s",
                    (fbx_otisk, shop_product_id))
    k_conn.commit()


def nahlas_chybu(k_conn, shop_product_id, name, hlaseni):
    try:
        with k_conn.cursor() as cur:
            cur.execute("INSERT INTO bot_ukoly (text, bot_id) VALUES (%s, 'bot4')",
                        ("Vandr FBX->GLB konverze: shop_products #%d (%s) selhala:\n%s"
                         % (shop_product_id, name, hlaseni),))
        k_conn.commit()
    except Exception as e:
        print("VAROVANI: zapis do bot_ukoly selhal (%s)" % e)


def main():
    ap = argparse.ArgumentParser(description="Automat: preved Vandr FBX exporty na katalogove GLB")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    k_conn = _konfigurator_conn()
    v_conn = _vandrawee_conn()
    try:
        kandidati, zkontrolovano, bez_karty, preskoceno_znama_chyba = najdi_kandidaty(k_conn, v_conn)
    finally:
        v_conn.close()

    print("ZKONTROLOVANO stored_models s fbx_exported_at: %d" % zkontrolovano)
    if bez_karty:
        print("PRESKOCENO (bez karty/FBX na disku, neni na tomhle automatu): %d: %s"
              % (len(bez_karty), bez_karty))
    if preskoceno_znama_chyba:
        print("PRESKOCENO (jiz znama chyba na tomto FBX): %d: %s"
              % (len(preskoceno_znama_chyba), preskoceno_znama_chyba))
    print("KANDIDATU k prevodu: %d" % len(kandidati))
    if not kandidati:
        print("Nic k udelani.")
        k_conn.close()
        return
    if a.dry_run:
        for k in kandidati:
            print("  [dry-run] %d - %s (%s)" % (k["shop_product_id"], k["name"], k["uuid"]))
        k_conn.close()
        return

    scratch_dir = tempfile.mkdtemp(prefix="vandr_konverze_")
    try:
        r3d = priprav_render3d(scratch_dir)
        httpd = spust_http_server(r3d)
        http_port = httpd.server_address[1]

        uspesne, chybne = [], []
        for k in kandidati:
            print("--- shop_product %d (%s) ---" % (k["shop_product_id"], k["name"]))
            ok, final_glb, hlaseni = preved_jeden(r3d, http_port, k["fbx_path"], scratch_dir)
            prurez = None
            if ok:
                ok, hlaseni2, prurez = overit_final_glb(final_glb)
                if not ok:
                    hlaseni = "prevod OK, ale overeni selhalo: %s" % hlaseni2
                else:
                    print("  overeni: %s" % hlaseni2)
            if ok:
                ok, hlaseni3 = nasad_a_zapis(k_conn, k["shop_product_id"], k["name"], k["uuid"], final_glb, prurez)
                if not ok:
                    hlaseni = "overeno OK, ale nasazeni selhalo: %s" % hlaseni3
                else:
                    print("  nasazeno: %s" % hlaseni3)
            if ok:
                uspesne.append(k["shop_product_id"])
            else:
                chybne.append(k["shop_product_id"])
                print("CHYBA: %s" % hlaseni)
                zapis_znamou_chybu(k_conn, k["shop_product_id"], k["fbx_otisk"])
                nahlas_chybu(k_conn, k["shop_product_id"], k["name"], hlaseni)

        httpd.shutdown()
        print("=== SHRNUTI: %d uspesnych, %d chybnych (z %d kandidatu) ==="
              % (len(uspesne), len(chybne), len(kandidati)))
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)
        k_conn.close()
    # Zamerne BEZ sys.exit(1) na chybne karty (stejny duvod jako u
    # razitkoveho automatu, bot3 2026-09-23 - viz 52941da1): spravne
    # odmitnuty/zaznamenany kandidat je uspech automatu, ne jeho selhani.


if __name__ == "__main__":
    main()
