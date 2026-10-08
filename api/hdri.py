"""
hdri.py - sprava HDRI environmentalnich map pro 3D scenu (bot5, 2026-08-06).

Robert: "dej mi do konfiguratoru moznost nahravat, menit HDRI
environmentalni mapu". Soubory .hdr/.exr se ukladaji do
webapp/katalog/hdri/ (nginx /katalog/ alias funguje rekurzivne, stejny
princip jako auta/ - zadna zmena nginx configu). Zadna DB tabulka -
seznam se cte primo z adresare (jednoduchy, bezstavovy pristup; nazev
souboru je zaroven identifikator).

CELA funkce jen pro admina (Robert 2026-08-06: "tu funkci HDRI nechme
jen pro admina") - seznam, upload i mazani. Volba mapy se uklada
klientsky v localStorage admina.
"""
import os
import re

from flask import request, jsonify
from werkzeug.utils import secure_filename

from app import app, admin_required, current_user, log_audit, KATALOG_GLB_DIR

HDRI_DIR = os.path.join(KATALOG_GLB_DIR, "hdri")
os.makedirs(HDRI_DIR, exist_ok=True)

ALLOWED_EXT = (".hdr", ".exr")


@app.get("/api/hdri")
@admin_required
def hdri_list():
    files = []
    for fname in sorted(os.listdir(HDRI_DIR)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ALLOWED_EXT:
            continue
        files.append({
            "file": fname,
            # zobrazovany nazev = nazev souboru bez pripony, podtrzitka
            # na mezery (nic se neuklada, ciste kosmetika pro <select>)
            "name": re.sub(r"[_-]+", " ", os.path.splitext(fname)[0]).strip(),
            "size_bytes": os.path.getsize(os.path.join(HDRI_DIR, fname)),
        })
    return jsonify({"files": files})


@app.post("/api/admin/hdri")
@admin_required
def hdri_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe = secure_filename(f.filename)
    ext = os.path.splitext(safe)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "Očekávám soubor .hdr nebo .exr."}), 400
    dest = os.path.join(HDRI_DIR, safe)
    f.save(dest)
    log_audit(current_user()["id"], "upload", "hdri", None, safe)
    return jsonify({"status": "ok", "file": safe}), 201


@app.delete("/api/admin/hdri/<path:fname>")
@admin_required
def hdri_delete(fname):
    safe = secure_filename(fname)
    ext = os.path.splitext(safe)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "Neplatný soubor."}), 400
    path = os.path.join(HDRI_DIR, safe)
    if not os.path.exists(path):
        return jsonify({"error": "Soubor neexistuje."}), 404
    os.remove(path)
    log_audit(current_user()["id"], "delete", "hdri", None, safe)
    return jsonify({"status": "ok"})
