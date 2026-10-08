#!/opt/konfigurator/api/venv/bin/python
"""Originalni STEP komponent Dynamic (86 souboru stazenych Johnem z Dogus) na Sdileny disk (bot5, 2026-10-07; Robert: "kde jsou ty original STEP?"): ZIP do slozky Vlastni tvary / Dynamic - originalni STEP z Dogus.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_bot5_sdileny_disk_dynamic_step.py <zip>"""
import grp
import os
import pwd
import secrets
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

zip_path = sys.argv[1]
NAZEV_SLOZKY, NAZEV_SOUBORU = "Dynamic – originální STEP z Dogus", os.path.basename(zip_path)
DRIVE = "/opt/konfigurator/private-files/shared-drive"
conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=21 AND name=%s", (NAZEV_SLOZKY,))
r = cur.fetchone()
if r:
    fid = r["id"]
else:
    cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (21,%s,1)", (NAZEV_SLOZKY,))
    fid = cur.lastrowid
cur.execute("SELECT id FROM shared_drive_files WHERE folder_id=%s AND filename=%s", (fid, NAZEV_SOUBORU))
if cur.fetchone():
    sys.exit("ZASTAVENO: soubor uz ve slozce je")
stored = secrets.token_hex(16) + ".zip"
dst = os.path.join(DRIVE, stored)
shutil.copyfile(zip_path, dst)
os.chown(dst, pwd.getpwnam("www-data").pw_uid, grp.getgrnam("www-data").gr_gid)
os.chmod(dst, 0o644)
cur.execute("INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) VALUES (%s,%s,%s,'application/zip',%s,1)", (fid, NAZEV_SOUBORU, stored, os.path.getsize(dst)))
conn.commit()
cur.execute("SELECT f.id, f.filename, f.size_bytes, d.name slozka FROM shared_drive_files f JOIN shared_drive_folders d ON d.id=f.folder_id WHERE f.stored_filename=%s", (stored,))
print("ZAPSANO:", cur.fetchone(), "| slozka id", fid)
