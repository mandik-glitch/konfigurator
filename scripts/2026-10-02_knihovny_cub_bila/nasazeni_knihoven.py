#!/usr/bin/env python3
"""Nahraje knihovny cub_seda.blend a bila.blend do slozky "HDRi" (id 45) Sdileneho disku a (volitelne, --three) upravi
render_materialy.three_json. Bez --apply je to JEN NAHLED (cte DB a soubory, nic nezapise).

Mechanismus (stejny jako api/drive.py drive_admin_files_upload a bot4 scripts/2026-10-01_agent_skripty_na_disk.py):
  1) soubor se zkopiruje do private-files/shared-drive/<32 hex nahodnych znaku>.blend (vlastnik www-data, 0644),
  2) vlozi se radek shared_drive_files(folder_id=45, filename, stored_filename, content_type, size_bytes, uploaded_by).
cesta_k_souboru_podle_jmena() pak najde soubor podle JMENA kdekoli na disku (posledni nahrany vyhrava).

Spusteni (jako www-data - soubory na disku musi patrit www-data; stejne jako skripty bota4):
  systemd-run -p User=www-data -p Group=www-data --pipe --wait --quiet \\
    --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
    api/venv/bin/python3 -B scripts/2026-10-02_knihovny_cub_bila/nasazeni_knihoven.py [--apply] [--three]
Zdrojove .blend musi lezet vedle skriptu (nebo --zdroj ADRESAR) a byt citelne pro www-data.
"""
import argparse
import hashlib
import json
import os
import sys

REPO = os.environ.get("KONF_REPO", "/opt/konfigurator")
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.dont_write_bytecode = True
from _env import get_conn  # noqa: E402

DISK = os.path.join(REPO, "private-files", "shared-drive")
SLOZKA_ID = 45                  # "HDRi" (rodic 42 "Rendering") - tam jsou vsechny ostatni knihovny materialu
SLOZKA_NAZEV = "HDRi"
SOUBORY = ("cub_seda.blend", "bila.blend", "laminodeska.blend", "eurobox_seda.blend")
MAX_B = 5 * 1024 * 1024

# three_json pro koule v adminu / nahled v prohlizeci (klice cte webapp/admin/js/render-materialy-katalogu.js)
THREE = {
    "cub_seda": {"color": "#BCBCBC", "clearcoat": 0.08, "metalness": 0, "roughness": 0.28, "clearcoatRoughness": 0.15},
    "bila": {"color": "#F2F2EF", "clearcoat": 0.22, "metalness": 0, "roughness": 0.4, "clearcoatRoughness": 0.1},
    "laminodeska": {"color": "#C4C4C1", "clearcoat": 0, "metalness": 0, "roughness": 0.57, "clearcoatRoughness": 0.5},
    "eurobox_seda": {"color": "#A6A6A6", "clearcoat": 0.05, "metalness": 0, "roughness": 0.38, "clearcoatRoughness": 0.2},
}
# 2026-10-03 Robert: laminodeska, seda plastova vypln CUB a seda plast euroboxu jsou TRI ruzne materialy (drive jeden "cub_seda" pro lamino i vypln)
NAZEV = {"cub_seda": "Šedý plast výplní (CUB)", "laminodeska": "Šedý laminát (laminodeska)", "eurobox_seda": "Šedý plast euroboxů"}
NOVE = {   # klic -> (nazev_blender, knihovna_soubor, poradi); INSERT jen pro chybejici radky (--three --apply)
    "laminodeska": ("Laminodeska", "laminodeska.blend", 101),
    "eurobox_seda": ("Eurobox seda", "eurobox_seda.blend", 102),
}
POZNAMKA = {
    "cub_seda": "Šedá plastová výplň CUB (CUB10/CUB6/CUB8 v profilech, plastová deska 8 mm; Robert 2026-10-03: NE laminodeska ani eurobox, ty mají vlastní materiál). Knihovna cub_seda.blend (procedurální, odvozeno z KLT1, bez textur), materiál 'CUB seda'; Vandr GLB nativně 'CUB seda': Unity _Color 0.7358 gamma = #BCBCBC.",
    "laminodeska": "Laminované desky (lamino, např. 3671, 4933). Matná světle šedá, bez lesku, jemné zrno. Knihovna laminodeska.blend (procedurální, odvozeno z KLT1, bez textur), materiál 'Laminodeska'. Robert 2026-10-03: lamino, plastová výplň CUB a plast euroboxů jsou tři různé materiály.",
    "eurobox_seda": "Šedá plastová vana euroboxů (katalog eurobox_*, ve Vandru materiál 'box tmava' #A6A6A6). Půl-lesk, formovaný PP. Knihovna eurobox_seda.blend (procedurální, odvozeno z KLT1, bez textur), materiál 'Eurobox seda'. Robert 2026-10-03.",
    "bila": "Elektrožlab, lakovaný plech, ocelové šuplíky (Robert 2026-10-01). Knihovna bila.blend (procedurální, odvozeno ze Suplik_celo, bez textur), materiál 'Bila'; bílý lak #F2F2EF, lehký coat.",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="bez toho jen nahled")
    ap.add_argument("--three", action="store_true", help="navic UPDATE render_materialy.three_json (+poznamka, nazev cub_seda) a INSERT novych radku laminodeska, eurobox_seda")
    ap.add_argument("--zdroj", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()

    data = {}
    for n in SOUBORY:
        cesta = os.path.join(a.zdroj, n)
        with open(cesta, "rb") as fh:
            b = fh.read()
        if not (b[:4] == b"\x28\xb5\x2f\xfd" or b[:7] == b"BLENDER"):
            sys.exit("%s neni .blend (ani zstd komprimovany)" % cesta)
        if len(b) > MAX_B:
            sys.exit("%s ma %d B (> 5 MB), disk je skoro plny" % (cesta, len(b)))
        data[n] = b

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT f.id, f.name, p.name AS rodic FROM shared_drive_folders f "
                        "LEFT JOIN shared_drive_folders p ON p.id=f.parent_folder_id WHERE f.id=%s", (SLOZKA_ID,))
            sl = cur.fetchone()
            if not sl or sl["name"] != SLOZKA_NAZEV:
                sys.exit("slozka %s neni '%s' (%r) - zastaveno" % (SLOZKA_ID, SLOZKA_NAZEV, sl))
            print("cil: slozka %s '%s' (rodic '%s')" % (sl["id"], sl["name"], sl["rodic"]))
            for n in SOUBORY:
                b = data[n]
                cur.execute("SELECT id, folder_id, stored_filename, size_bytes FROM shared_drive_files WHERE filename=%s ORDER BY id", (n,))
                existuje = cur.fetchall()
                ve_slozce = [r for r in existuje if r["folder_id"] == SLOZKA_ID]
                mimo = [r for r in existuje if r["folder_id"] != SLOZKA_ID]
                if mimo:
                    print("  POZOR %s: stejne jmeno uz je v jine slozce (id %s) - cesta_k_souboru_podle_jmena bere POSLEDNI nahrany"
                          % (n, [r["id"] for r in mimo]))
                if ve_slozce:
                    r = ve_slozce[-1]
                    cesta = os.path.join(DISK, r["stored_filename"])
                    stary = open(cesta, "rb").read() if os.path.isfile(cesta) else b""
                    if hashlib.sha256(stary).digest() == hashlib.sha256(b).digest():
                        print("  %-16s beze zmeny (id %s)" % (n, r["id"]))
                        continue
                    print("  %-16s PREPIS NA MISTE (id %s, %d -> %d B), puvodni se zalohuje do backups/" % (n, r["id"], len(stary), len(b)))
                    if a.apply:
                        zaloha = os.path.join(REPO, "backups", "2026-10-02_knihovny_cub_bila_pred")
                        os.makedirs(zaloha, exist_ok=True)
                        with open(os.path.join(zaloha, n), "wb") as fh:
                            fh.write(stary)
                        tmp = cesta + ".tmp"
                        with open(tmp, "wb") as fh:
                            fh.write(b)
                        os.replace(tmp, cesta)
                        cur.execute("UPDATE shared_drive_files SET size_bytes=%s WHERE id=%s", (len(b), r["id"]))
                        if cur.rowcount != 1:
                            raise RuntimeError("rowcount %s != 1 pro %s" % (cur.rowcount, n))
                else:
                    print("  %-16s NOVY (%d B)" % (n, len(b)))
                    if a.apply:
                        ulozeny = "%s.blend" % os.urandom(16).hex()
                        tmp = os.path.join(DISK, ulozeny + ".tmp")
                        with open(tmp, "wb") as fh:
                            fh.write(b)
                        os.chmod(tmp, 0o644)
                        os.replace(tmp, os.path.join(DISK, ulozeny))
                        cur.execute("INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) "
                                    "VALUES (%s,%s,%s,%s,%s,%s)", (SLOZKA_ID, n, ulozeny, "application/octet-stream", len(b), None))
                        if cur.rowcount != 1:
                            raise RuntimeError("rowcount %s != 1 pro INSERT %s" % (cur.rowcount, n))
                        print("      -> %s, id %s" % (ulozeny, cur.lastrowid))
            if a.three:
                for klic, tj in THREE.items():
                    cur.execute("SELECT three_json, nazev, poznamka, nazev_blender, knihovna_soubor FROM render_materialy WHERE klic=%s", (klic,))
                    r = cur.fetchone()
                    if not r and klic in NOVE:
                        nb, kf, po = NOVE[klic]
                        print("  NOVY radek render_materialy %-12s %s (%s, poradi %d)" % (klic, NAZEV[klic], kf, po))
                        if a.apply:
                            cur.execute("INSERT INTO render_materialy (klic, nazev, nazev_blender, knihovna_soubor, three_json, poradi, aktivni, poznamka) "
                                        "VALUES (%s,%s,%s,%s,%s,%s,1,%s)", (klic, NAZEV[klic], nb, kf, json.dumps(tj), po, POZNAMKA[klic]))
                            if cur.rowcount != 1:
                                raise RuntimeError("rowcount %s != 1 pro INSERT %s" % (cur.rowcount, klic))
                        continue
                    if not r:
                        sys.exit("render_materialy.%s neexistuje" % klic)
                    print("  three_json %-9s %s  ->  %s" % (klic, r["three_json"], json.dumps(tj)))
                    if (a.apply and json.loads(r["three_json"] or "null") == tj and r["poznamka"] == POZNAMKA[klic]
                            and r["nazev"] == (NAZEV.get(klic) or r["nazev"])):
                        print("      radek %s beze zmeny (UPDATE preskocen, MySQL by vratil rowcount 0)" % klic)
                    elif a.apply:
                        cur.execute("UPDATE render_materialy SET three_json=%s, poznamka=%s, nazev=%s WHERE klic=%s",
                                    (json.dumps(tj), POZNAMKA[klic], NAZEV.get(klic) or r["nazev"], klic))
                        if cur.rowcount != 1:
                            raise RuntimeError("rowcount %s != 1 pro %s" % (cur.rowcount, klic))
        if a.apply:
            conn.commit()
            print("ZAPSANO (commit)")
        else:
            conn.rollback()
            print("--- NAHLED: nic se nezapsalo (pridej --apply) ---")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
