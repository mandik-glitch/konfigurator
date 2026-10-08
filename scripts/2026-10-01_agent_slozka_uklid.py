#!/usr/bin/env python3
"""Uklid slozky "Renderovaci agent (PC GPU)" na Sdilenem disku (bot4 2026-10-01, Robert: "je tam bordel nevim co plati").

Stary agent render_worker_agent_2026-09-10.py (verze 2026-09-09c, bez hlaseni verze Blenderu) se PRESUNE (ne maze) do
podslozky "STARE - nepouzivat". Past, kterou to odstranuje: NAINSTALOVAT_SLUZBU.bat bere `dir /b /o-n render_worker_agent*.py`,
tj. PRVNI podle abecedy sestupne = prave tenhle stary soubor (09-10 > 08-11), takze by nainstaloval zastaraleho agenta.
Aktualni agent je render_worker_agent_2026-08-11_1455.py (obsah == scripts/render_worker_agent.py, verze 2026-09-29b;
nazev je historicky, NEPREJMENOVAVA se, protoze ho pouziva SPUSTIT_AGENTA_NOTEBOOK.bat i kopie na notebooku).
Pred zmenou se radky ulozi do backups/2026-10-01_agent_slozka_pred.json. Idempotentni. Soubor CO_PLATI.txt nahraje
2026-10-01_agent_skripty_na_disk.py.

Spusteni:  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
             --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-01_agent_slozka_uklid.py [--apply]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZALOHA = os.path.join(REPO, "backups", "2026-10-01_agent_slozka_pred.json")
SLOZKA = "Renderovaci agent (PC GPU)"
PODSLOZKA = "STARE - nepouzivat"
STARY_SOUBOR = "render_worker_agent_2026-09-10.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shared_drive_folders WHERE name=%s", (SLOZKA,))
            r = cur.fetchall()
            if len(r) != 1:
                sys.exit("slozka '%s': nalezeno %d (cekam 1)" % (SLOZKA, len(r)))
            hlavni = r[0]["id"]
            cur.execute("SELECT * FROM shared_drive_files WHERE folder_id=%s ORDER BY id", (hlavni,))
            soubory = cur.fetchall()
            cur.execute("SELECT * FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s", (hlavni, PODSLOZKA))
            pod = cur.fetchone()
            stary = next((f for f in soubory if f["filename"] == STARY_SOUBOR), None)
            if not stary:
                print("%s uz ve slozce neni - nic k presunu" % STARY_SOUBOR)
                return 0
            print("presun: id %s %s -> podslozka '%s' (%s)" % (stary["id"], STARY_SOUBOR, PODSLOZKA, "existuje" if pod else "bude zalozena"))
            if not a.apply:
                print("--dry-run: nic se nezapsalo")
                return 0
            os.makedirs(os.path.dirname(ZALOHA), exist_ok=True)
            with open(ZALOHA, "w", encoding="utf-8") as fh:
                json.dump({"folder_id": hlavni, "files": soubory, "podslozka": pod}, fh, default=str, ensure_ascii=False, indent=1)
            if pod:
                pod_id = pod["id"]
            else:
                cur.execute("INSERT INTO shared_drive_folders (parent_folder_id, name) VALUES (%s,%s)", (hlavni, PODSLOZKA))
                pod_id = cur.lastrowid
            cur.execute("UPDATE shared_drive_files SET folder_id=%s WHERE id=%s AND folder_id=%s", (pod_id, stary["id"], hlavni))
            if cur.rowcount != 1:
                conn.rollback()
                sys.exit("UPDATE zmenil %d radku (cekam 1) - vraceno" % cur.rowcount)
        conn.commit()
    finally:
        conn.close()
    print("hotovo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
