#!/usr/bin/env python3
"""Nahraje Windows skripty renderovaciho agenta (deploy/windows/*.bat a CO_PLATI.txt) do slozky "Renderovaci agent (PC GPU)" na
Sdilenem disku (bot4 2026-10-01). Existujici soubor stejneho jmena se PREPISE NA MISTE (stejne id/odkaz) a puvodni
obsah se pred tim ulozi do backups/2026-10-01_agent_skripty_pred/. Soubor, ktery tam jeste neni, se zalozi.

Proc: SPUSTIT_AGENTA_NOTEBOOK.bat mel smycku bez stropu (Robert 2026-09-30, okno "Agent skoncil, restartuji za 3s"),
novy ma strop opakovani; ODINSTALOVAT_PROTOKOL.bat odebere zastaraly odkaz logimanrender:// z PC, ktery ho ma.

Spusteni (jako www-data, soubory na disku musi patrit www-data):
    systemd-run -p User=www-data -p Group=www-data --pipe --wait --quiet \\
      --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-01_agent_skripty_na_disk.py [--apply]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZDROJ = os.path.join(REPO, "deploy", "windows")
DISK = os.path.join(REPO, "private-files", "shared-drive")
ZALOHA = os.path.join(REPO, "backups", "2026-10-01_agent_skripty_pred")
SLOZKA = "Renderovaci agent (PC GPU)"
CONTENT_TYPES = {".bat": "application/x-msdos-program", ".txt": "text/plain"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="bez toho jen nahled")
    a = ap.parse_args()
    soubory = sorted(f for f in os.listdir(ZDROJ) if os.path.splitext(f)[1].lower() in CONTENT_TYPES)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shared_drive_folders WHERE name=%s", (SLOZKA,))
            radky = cur.fetchall()
            if len(radky) != 1:
                sys.exit("slozka '%s': nalezeno %d (cekam 1)" % (SLOZKA, len(radky)))
            folder_id = radky[0]["id"]
            for nazev in soubory:
                with open(os.path.join(ZDROJ, nazev), "rb") as fh:
                    data = fh.read()
                cur.execute("SELECT id, stored_filename, content_type, size_bytes FROM shared_drive_files "
                            "WHERE folder_id=%s AND filename=%s", (folder_id, nazev))
                stary = cur.fetchone()
                if stary:
                    cesta = os.path.join(DISK, stary["stored_filename"])
                    with open(cesta, "rb") as fh:
                        puvodni = fh.read()
                    if puvodni == data:
                        print("  %-32s beze zmeny (id %s)" % (nazev, stary["id"]))
                        continue
                    print("  %-32s PREPIS na miste (id %s, %d -> %d B)" % (nazev, stary["id"], len(puvodni), len(data)))
                    if a.apply:
                        os.makedirs(ZALOHA, exist_ok=True)
                        with open(os.path.join(ZALOHA, nazev), "wb") as fh:
                            fh.write(puvodni)
                        tmp = cesta + ".tmp"
                        with open(tmp, "wb") as fh:
                            fh.write(data)
                        os.replace(tmp, cesta)
                        cur.execute("UPDATE shared_drive_files SET size_bytes=%s WHERE id=%s", (len(data), stary["id"]))
                else:
                    print("  %-32s NOVY (%d B)" % (nazev, len(data)))
                    if a.apply:
                        pripona = os.path.splitext(nazev)[1].lower()
                        ulozeny = "%s%s" % (os.urandom(16).hex(), pripona)
                        tmp = os.path.join(DISK, ulozeny + ".tmp")
                        with open(tmp, "wb") as fh:
                            fh.write(data)
                        os.replace(tmp, os.path.join(DISK, ulozeny))
                        cur.execute(
                            "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) "
                            "VALUES (%s,%s,%s,%s,%s,%s)", (folder_id, nazev, ulozeny, CONTENT_TYPES[pripona], len(data), None))
        if a.apply:
            conn.commit()
    finally:
        conn.close()
    print("hotovo" if a.apply else "--dry-run: nic se nezapsalo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
