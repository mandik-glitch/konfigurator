#!/usr/bin/env python3
"""2026-10-06_vandr_cizi_fbx_na_kartu.py - FBX, ktery Robert dodal MIMO Vandr admin (soubor v chatu / z CADu), zalozi jako Vandr kartu
STEJNE, jako by ho vyexportoval z Vandr systemu (bot8, Robert 2026-10-06: "pridej tento stul do auta, ke karoserii MAN L3H3 na prepazku
jako nova karta" + "pokracuj s tim stejne jakobych to vyexportoval z Vandr systemu").

PROC TO NENI UZ HOTOVY AUTOMAT: watcher (2026-09-22_vandr_fbx_watcher.py) zaklada kartu jen kdyz najde UUID v lokalni vandrawee_work DB
(zdroj A) nebo soubor "<uuid>.fbx" na Sdilenem disku (zdroj B, ale pak karta bez nazvu/vozidla/umisteni) a konverzni automat
(2026-09-23_vandr_fbx_konverze_auto_dispatch.py) bere JEN stored_models z vandrawee_work (a umi jen Unity export: osa Y nahoru, METRY ->
vzdy x1000). Tenhle skript udela totez rucne pro cizi soubor a zachova VSECHNO ostatni: karta VD-<uuid> (neaktivni, bez ceny - pravidlo 54),
GLB v chranene slozce webapp/katalog/vandr/ (commit pod DEPLOY_LOCK), `nativni_material=1`, `vandr_hlavni_prurez_mm`, stitek umisteni, fronta
`vandr_fbx_queue` + puvodni FBX na Sdilenem disku ("vanDrawee sestavy/<uuid>.fbx"). Razitka (vc. predniho azimutu), render a aktivaci
pak delaji UZ EXISTUJICI automaty bez dalsiho zasahu (razitka :14/:29/:44/:59, render, aktivace az bude cena + 2 elevace).

Rozdily proti Unity exportu, ktere skript resi (volby): --osa-nahoru Z|Y (FBX z CADu/Rhina ma Z nahoru; vysledny GLB ma Y nahoru, stejny
prevod os jako univerzalni import FBX: scena_x=fbx_y, scena_y=fbx_z, scena_z=fbx_x) a --jednotky mm|m (mm = bez skalovani, m = x1000 jako Vandr).

Pouziti (NA SERVERU, jako root):
    api/venv/bin/python3 scripts/2026-10-06_vandr_cizi_fbx_na_kartu.py --fbx <soubor.fbx> --nazev "<nazev karty>" --umisteni RK \
        [--osa-nahoru Z] [--jednotky mm] [--popis "..."] [--kratky-popis "..."] [--uuid <uuid>]            # nahled, nic nezapisuje
    ... --apply                                                                                            # zalozi kartu + GLB
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid as uuid_module

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "api"))
from _env import get_conn  # noqa: E402
import product_slug  # noqa: E402

KATALOG_VANDR_DIR = os.path.join(REPO, "webapp", "katalog", "vandr")
PRIVATE_FILES_DIR = os.environ.get("PRIVATE_FILES_DIR", os.path.join(REPO, "private-files"))
DRIVE_FILES_DIR = os.path.join(PRIVATE_FILES_DIR, "shared-drive")
ROOT_FOLDER_NAME = "vanDrawee sestavy"
UMISTENI = {"RL": 1, "RK": 2, "RP": 7}        # regal_umisteni.id (overeno v DB 2026-10-06: RL=1 levy, RK=2 kabina/prepazka, RP=7 pravy)


def _konv():
    spec = importlib.util.spec_from_file_location("vandr_konverze", os.path.join(REPO, "scripts", "2026-09-23_vandr_fbx_konverze_auto_dispatch.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def zabal_osu_nahoru(glb_in, glb_out):
    """Koreny sceny obali novym uzlem s rotaci (x,y,z)->(y,z,x): osa Z nahoru -> osa Y nahoru. Vrcholy ani akcesory se nemeni."""
    b = open(glb_in, "rb").read()
    assert b[:4] == b"glTF"
    off, js, binc = 12, None, None
    while off < len(b):
        ln, typ = struct.unpack("<II", b[off:off + 8])
        data = b[off + 8: off + 8 + ln]
        if typ == 0x4E4F534A:
            js = json.loads(data)
        elif typ == 0x004E4942:
            binc = data
        off += 8 + ln
    sc = js["scenes"][js.get("scene", 0)]
    js["nodes"].append({"name": "osy_Zup_na_Yup", "rotation": [-0.5, -0.5, -0.5, 0.5], "children": list(sc["nodes"])})
    sc["nodes"] = [len(js["nodes"]) - 1]
    j = json.dumps(js, separators=(",", ":")).encode()
    j += b" " * ((4 - len(j) % 4) % 4)
    bb = binc + b"\x00" * ((4 - len(binc) % 4) % 4)
    total = 12 + 8 + len(j) + 8 + len(bb)
    with open(glb_out, "wb") as f:
        f.write(b"glTF" + struct.pack("<II", 2, total) + struct.pack("<II", len(j), 0x4E4F534A) + j + struct.pack("<II", len(bb), 0x004E4942) + bb)


def preved(fbx, osa_nahoru, jednotky, tmp):
    """FBX -> GLB presne postupem Vandr konverze (patchnuty FBXLoader, sanitizace) + volitelne metry->mm a Z->Y nahoru; overeni Blenderem."""
    konv = _konv()
    r3d = konv.priprav_render3d(tmp)
    httpd = konv.spust_http_server(r3d)
    try:
        ok, final, hlaseni = konv.preved_jeden(r3d, httpd.server_address[1], fbx, tmp)
    finally:
        httpd.shutdown()
    if not ok:
        raise SystemExit("KONVERZE SELHALA: %s" % hlaseni)
    zdroj = final if jednotky == "m" else os.path.join(tmp, "sanitized.glb")      # final = po scale_to_mm (x1000 z metru)
    if osa_nahoru == "Z":
        vysledek = os.path.join(tmp, "vysledek.glb")
        zabal_osu_nahoru(zdroj, vysledek)
    else:
        vysledek = zdroj
    ok, hlaseni, prurez = konv.overit_final_glb(vysledek)
    if not ok:
        raise SystemExit("OVERENI GLB SELHALO (nic nezapsano): %s" % hlaseni)
    return vysledek, hlaseni, prurez


def nasad_glb(glb, fname_bez_prefixu, uuid8):
    """Zkopiruje do webapp/katalog/vandr/ a commitne pod DEPLOY_LOCK (jako nasad_a_zapis automatu, jen s identitou bot8)."""
    env = {**os.environ, "BOT_ID": "bot8"}
    dest = os.path.join(KATALOG_VANDR_DIR, fname_bez_prefixu)
    rel = os.path.relpath(dest, REPO)
    zamek = subprocess.run(["bash", os.path.join(REPO, "scripts", "lock.sh"), "acquire", "bot8", "bot8: nasazeni noveho Vandr GLB (%s)" % fname_bez_prefixu, "--wait=300"],
                           capture_output=True, text=True, timeout=400, env=env)
    if zamek.returncode != 0:
        raise SystemExit("DEPLOY_LOCK acquire selhal (nic nezapsano): %s" % (zamek.stdout + zamek.stderr))
    try:
        if subprocess.run(["bash", os.path.join(REPO, "scripts", "lock.sh"), "require", "bot8"], capture_output=True, text=True, env=env).returncode != 0:
            raise SystemExit("zamek nedrzim (lock.sh require) - nic nezapsano")
        os.makedirs(KATALOG_VANDR_DIR, exist_ok=True)
        shutil.copy(glb, dest)
        os.chmod(dest, 0o644)
        p = subprocess.run(["git", "add", rel], cwd=REPO, capture_output=True, text=True)
        if p.returncode != 0:
            raise SystemExit("git add selhal: %s" % (p.stdout + p.stderr))
        zprava = ("feat(vandr): nova GLB z FBX dodaneho mimo Vandr admin - vandr/%s (karta VD-%s, bot8)\n\n"
                  "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\n"
                  "Claude-Session: https://claude.ai/code/session_0117meq81TnjQhy1Mvk3fLRV\n" % (fname_bez_prefixu, uuid8))
        p = subprocess.run(["git", "commit", "-m", zprava, "--", rel], cwd=REPO, capture_output=True, text=True, env=env)
        if p.returncode != 0:
            raise SystemExit("git commit selhal: %s" % (p.stdout + p.stderr))
    finally:
        subprocess.run(["bash", os.path.join(REPO, "scripts", "lock.sh"), "release", "bot8"], capture_output=True, text=True, env=env)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fbx", required=True)
    ap.add_argument("--nazev", required=True, help="nazev karty (zakaznicky text - TEXT_FILTR.md)")
    ap.add_argument("--vozidlo", required=True, help="vozidlo do stitku/popisu, napr. 'MAN TGE L3H3'")
    ap.add_argument("--umisteni", required=True, choices=sorted(UMISTENI))
    ap.add_argument("--osa-nahoru", choices=["Y", "Z"], default="Z")
    ap.add_argument("--jednotky", choices=["mm", "m"], default="mm")
    ap.add_argument("--popis")
    ap.add_argument("--kratky-popis")
    ap.add_argument("--uuid")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.fbx):
        raise SystemExit("FBX neexistuje: %s" % a.fbx)
    nove_uuid = (a.uuid or str(uuid_module.uuid4())).lower()
    uuid_module.UUID(nove_uuid)
    uuid8 = nove_uuid.split("-")[0]
    sku = "VD-%s" % nove_uuid
    fbx_sha = hashlib.sha256(open(a.fbx, "rb").read()).hexdigest()

    tmp = tempfile.mkdtemp(prefix="vandr_cizi_fbx_")
    try:
        glb, hlaseni, prurez = preved(a.fbx, a.osa_nahoru, a.jednotky, tmp)
        print("GLB OK: %s | %s" % (hlaseni, os.path.getsize(glb)))
        konv = _konv()
        fname_bez_prefixu = "vd_export_%s_%s.glb" % (konv._slugify(a.nazev)[:40], uuid8)
        prurez_mm = prurez[0] if prurez and prurez[0] == prurez[1] else None
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM shop_products WHERE sku=%s", (sku,))
                if cur.fetchone():
                    raise SystemExit("karta %s uz existuje - nic nezakladam" % sku)
                slug = product_slug.slug_for_name(cur, a.nazev)
                cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s", (ROOT_FOLDER_NAME,))
                root = cur.fetchone()
                if not root:
                    raise SystemExit("korenova slozka '%s' na Sdilenem disku neexistuje" % ROOT_FOLDER_NAME)
                print("PLAN: sku=%s | nazev=%r | slug=%s | umisteni=%s (id %s) | GLB vandr/%s | FBX -> Sdileny disk slozka %s jako %s.fbx | hlavni prurez %s"
                      % (sku, a.nazev, slug, a.umisteni, UMISTENI[a.umisteni], fname_bez_prefixu, root["id"], nove_uuid, prurez_mm))
                if not a.apply:
                    print("\nNAHLED: nic nezapsano (pridej --apply).")
                    return 0

                # 1) GLB do chranene slozky + commit pod zamkem (guarded cesta), az POTOM DB (kdyby commit selhal, v DB nic neni)
                nasad_glb(glb, fname_bez_prefixu, uuid8)

                # 2) FBX na Sdileny disk (private-files/shared-drive, vlastnik www-data jako ostatni)
                stored = os.urandom(16).hex() + ".fbx"
                os.makedirs(DRIVE_FILES_DIR, exist_ok=True)
                cil_fbx = os.path.join(DRIVE_FILES_DIR, stored)
                shutil.copy(a.fbx, cil_fbx)
                try:
                    shutil.chown(cil_fbx, "www-data", "www-data")
                    os.chmod(cil_fbx, 0o640)
                except (LookupError, PermissionError):
                    pass

                # 3) DB (jedna transakce): karta presne jako watcher (INSERT stejnych sloupcu) + GLB, fronta, soubor na disku, ukol na zed
                try:
                    cur.execute(
                        "INSERT INTO shop_products (sku, name, slug, active, price_czk_placeholder, weight_g, category_id, description, short_description, "
                        "product_specs_json, supplier_name, umisteni_id, price_visible_default, glb_file, nativni_material, vandr_hlavni_prurez_mm) "
                        "VALUES (%s,%s,%s,0,NULL,NULL,NULL,%s,%s,NULL,'vanDrawee',%s,0,%s,1,%s)",
                        (sku, a.nazev, slug, a.popis, a.kratky_popis, UMISTENI[a.umisteni], "vandr/%s" % fname_bez_prefixu, prurez_mm))
                    pid = cur.lastrowid
                    cur.execute("INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) VALUES (%s,%s,%s,%s,%s,NULL)",
                                (root["id"], "%s.fbx" % nove_uuid, stored, "application/octet-stream", os.path.getsize(cil_fbx)))
                    drive_id = cur.lastrowid
                    cur.execute("INSERT INTO vandr_fbx_queue (shared_drive_file_id, vandrawee_uuid, shop_product_id, stav, poznamka) VALUES (%s,%s,%s,'karta_zalozena',%s)",
                                (drive_id, nove_uuid, pid, "%s (FBX dodal Robert mimo Vandr admin, zalozeno rucne: scripts/2026-10-06_vandr_cizi_fbx_na_kartu.py)" % a.vozidlo))
                    text = ("NOVÁ VANDR KARTA #%d: \"%s\" založena ručně z FBX dodaného Robertem mimo Vandr admin (pokyn: jako by to vyexportoval z Vandr systému; "
                            "vozidlo %s, umístění %s). Chybí: cena (není ve Vandr DB, nepřijde ze synchronizace), kategorie (značka mimo mapování ZNACKA_ID_TO_CATEGORY) - "
                            "doplň v adminu; razítka a render běží automaticky, aktivace až bude cena a dokončený render." % (pid, a.nazev, a.vozidlo, a.umisteni))
                    cur.execute("INSERT INTO bot_ukoly (text, bot_id) VALUES (%s,'bot5')", (text,))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    try:
                        os.remove(cil_fbx)
                    except OSError:
                        pass
                    raise
                print("ZALOZENO: shop_products #%d (%s), GLB vandr/%s, FBX na Sdilenem disku (soubor #%d), fronta + ukol bot5. FBX sha256 %s" % (pid, sku, fname_bez_prefixu, drive_id, fbx_sha))
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
