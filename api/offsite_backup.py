"""offsite_backup.py - admin prehled stavu offsite (Contabo S3) zalohy.

Robert (pres bot3, 2026-09-13): chce v adminu (Přehledy) videt otisk/
stav offsite zalohy, at se kvuli tomu nemusi prihlasovat na Contabo.

Zapis dela scripts/daily_backup.py (bezi jako root, systemd timer
konfigurator-daily-backup.timer, denne v 03:30) po KAZDEM pokusu o
upload - viz sql/2026-09-13_offsite_backup_log.sql,
_zapis_offsite_log()/_rclone_remote_celkem() tamtez.

TENHLE modul jen CTE tu tabulku - ZADNE zive volani rclone/mysqldump z
admin pozadavku. Duvod: /root/.config/rclone/rclone.conf je root-only
600, www-data (gunicorn) k nemu nema pristup, a i kdyby mel, zivy
sitovy dotaz pri kazdem nacteni admin stranky by byl pomaly a krehky.
"""
from flask import jsonify

from app import app, get_conn, require_permission


def _radek_public(row):
    return {
        "id": row["id"],
        "soubor": row["soubor"],
        "velikost_b": row["velikost_b"],
        "remote_cesta": row["remote_cesta"],
        "stav": row["stav"],
        "detail": row["detail"],
        "remote_objektu_celkem": row["remote_objektu_celkem"],
        "remote_bytu_celkem": row["remote_bytu_celkem"],
        "nahrano_at": row["nahrano_at"].isoformat() if row["nahrano_at"] else None,
    }


def _soubor_public(row):
    return {
        "soubor": row["soubor"],
        "velikost_b": row["velikost_b"],
        "zmeneno_at": row["zmeneno_at"].isoformat() if row["zmeneno_at"] else None,
    }


@app.get("/api/admin/offsite-backup")
@require_permission("nastaveni", "zobrazit")
def admin_offsite_backup():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM offsite_backup_log ORDER BY nahrano_at DESC, id DESC LIMIT 1")
            posledni = cur.fetchone()
            cur.execute("SELECT * FROM offsite_backup_log ORDER BY nahrano_at DESC, id DESC LIMIT 10")
            historie = cur.fetchall()
            # Robert upresnil: "výpis uložených souborů záloh z uloziste
            # S3, ne samotne soubory, jen seznam" - viz
            # sql/2026-09-13_offsite_backup_files.sql (zrcadlo `rclone
            # lsjson`, zapisuje daily_backup.py).
            cur.execute("SELECT * FROM offsite_backup_files ORDER BY soubor DESC")
            soubory = cur.fetchall()
    finally:
        conn.close()
    return jsonify({
        "posledni": _radek_public(posledni) if posledni else None,
        "historie": [_radek_public(r) for r in historie],
        "soubory": [_soubor_public(r) for r in soubory],
    })
