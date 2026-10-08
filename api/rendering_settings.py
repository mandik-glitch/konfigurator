"""
rendering_settings.py - vyber "aktivni" slozky na Sdilenem disku pro HDRI a
PBR textury pouzivane pri generovani nabidek (bot6, 2026-08-10).

Robert: "za chodu myslím toto: čerpat hdri i PBR pro 3D scenu v nabídce ve
sdíleném disku slozka rendering, ja jen budu vybírat na nějaké obrazovce
jaký se pouzije adresář pro HDRi a jaký pro PBR texturu" - zadna nova
uploadovaci infrastruktura (ta uz existuje - Sdileny disk, drive.py), jen
2 nastaveni (ulozena v app_settings): "ktera slozka je prave aktivni HDRI"
a "ktera je aktivni PBR sada". Admin soubory nahraje bezne pres Sdileny
disk (libovolne nazvy - role PBR mapy se pozna z nazvu souboru, viz
_detect_pbr_role), pak jen vybere spravnou slozku v teto obrazovce.

Pouziva se VYHRADNE pro fotorealisticky path-traceovany nahled nabidky
(scene.html::capturePathTracedOfferViews) a zivy 3D model v
nabidka-online.html - NEOVLIVNUJE zavodni interaktivni scenu (ta ma
vlastni, oddeleny system HDRI odlesku, viz hdri.py/applyHdri).

Bezpecnost: soubory na Sdilenem disku jsou normalne privatni/admin-only
(drive.py). Aby je ale mohl nacist i NEPRIHLASENY zakaznik prohlizejici
online nabidku (3D model pouziva textury zive v prohlizeci), /api/public/
rendering/file/<id> je verejny, ale VRACI JEN soubory, jejichz folder_id
je prave nekonfigurovana jako aktivni HDRI/PBR slozka - zbytek Sdileneho
disku zustava privatni.
"""
import os
import re

from flask import jsonify, request, Response

from app import app, get_conn, admin_required, current_user, log_audit, get_setting
from drive import DRIVE_FILES_DIR
from quotes import content_disposition

HDRI_EXT = (".hdr", ".exr")
PBR_EXT = (".jpg", ".jpeg", ".png", ".webp")

_AO_RE = re.compile(r"(?:^|[_\-\s.])ao(?:[_\-\s.]|\d|$)")


def _detect_pbr_role(filename):
    # Robert nahral 2 ruzne sady - jedna s hezky pojmenovanymi soubory
    # (Aluminium 2_baseColor.jpeg), druha s vychozimi nazvy z texturove
    # knihovny (metal_0058_color_4k.jpg, "normal_direct"/"normal_opengl"
    # varianty - WebGL/three.js pouziva OpenGL konvenci normal mapy,
    # takze DirectX variantu explicitne PRESKAKUJEME, aby se neomylem
    # nepouzila spatna (invertovana zelena slozka by delala viditelne
    # "obracene" stiny na hrbolcich).
    name = filename.lower()
    if "normal" in name:
        return None if "direct" in name else "normal"
    if "roughness" in name:
        return "roughness"
    if "metallic" in name or "metalness" in name:
        return "metallic"
    if "occlusion" in name or _AO_RE.search(name):
        return "ambientOcclusion"
    if "basecolor" in name or "albedo" in name or "diffuse" in name or "color" in name:
        return "baseColor"
    return None


def _folder_id_setting(cur, key):
    raw = get_setting(cur, key)
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _set_folder_id_setting(cur, key, value):
    val = str(int(value)) if value not in (None, "") else ""
    cur.execute(
        "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
        "ON DUPLICATE KEY UPDATE setting_value=%s",
        (key, val, val),
    )


@app.get("/api/admin/rendering-settings")
@admin_required
def rendering_settings_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            hdri_folder_id = _folder_id_setting(cur, "rendering_hdri_folder_id")
            pbr_folder_id = _folder_id_setting(cur, "rendering_pbr_folder_id")

            def folder_info(folder_id):
                if folder_id is None:
                    return None
                cur.execute("SELECT id, name FROM shared_drive_folders WHERE id=%s", (folder_id,))
                row = cur.fetchone()
                return {"id": folder_id, "name": row["name"] if row else "(smazaná složka)"}

            def files_preview(folder_id, exts):
                if folder_id is None:
                    return []
                cur.execute(
                    "SELECT id, filename FROM shared_drive_files WHERE folder_id=%s ORDER BY filename",
                    (folder_id,),
                )
                out = []
                for r in cur.fetchall():
                    ext = os.path.splitext(r["filename"])[1].lower()
                    if ext in exts:
                        out.append({"id": r["id"], "filename": r["filename"]})
                return out

            hdri_files = files_preview(hdri_folder_id, HDRI_EXT)
            pbr_files = files_preview(pbr_folder_id, PBR_EXT)
            # POZOR: musi bezet zatimco je cursor jeste otevreny (uvnitr
            # `with` bloku) - puvodni chyba mela tyhle 2 volani az v
            # return jsonify() NIZE, po conn.close(), coz shazovalo
            # "pymysql.err.ProgrammingError: Cursor closed".
            hdri_folder_info = folder_info(hdri_folder_id)
            pbr_folder_info = folder_info(pbr_folder_id)
    finally:
        conn.close()
    return jsonify({
        "hdri_folder": hdri_folder_info,
        "pbr_folder": pbr_folder_info,
        "hdri_files": hdri_files,
        "pbr_files": [{"id": f["id"], "filename": f["filename"], "role": _detect_pbr_role(f["filename"])} for f in pbr_files],
    })


@app.put("/api/admin/rendering-settings")
@admin_required
def rendering_settings_set():
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if "hdri_folder_id" in body:
                fid = body.get("hdri_folder_id")
                if fid is not None:
                    cur.execute("SELECT id FROM shared_drive_folders WHERE id=%s", (fid,))
                    if not cur.fetchone():
                        return jsonify({"error": "Zvolená HDRI složka neexistuje."}), 400
                _set_folder_id_setting(cur, "rendering_hdri_folder_id", fid)
            if "pbr_folder_id" in body:
                fid = body.get("pbr_folder_id")
                if fid is not None:
                    cur.execute("SELECT id FROM shared_drive_folders WHERE id=%s", (fid,))
                    if not cur.fetchone():
                        return jsonify({"error": "Zvolená PBR složka neexistuje."}), 400
                _set_folder_id_setting(cur, "rendering_pbr_folder_id", fid)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "rendering_settings", None,
              f"hdri_folder_id={body.get('hdri_folder_id')}, pbr_folder_id={body.get('pbr_folder_id')}")
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Verejne cteni (pouziva scene.html PRI generovani nabidky - admin je sice
# prihlaseny, ale stejny endpoint pouziva i nabidka-online.html pro
# neprihlaseneho zakaznika, takze je jednodussi mit JEN jednu verejnou
# cestu misto dvou paralelnich admin/public variant).
# ---------------------------------------------------------------------------

@app.get("/api/public/rendering/hdri")
def public_rendering_hdri():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            folder_id = _folder_id_setting(cur, "rendering_hdri_folder_id")
            if folder_id is None:
                return jsonify({"file": None})
            cur.execute(
                "SELECT id, filename FROM shared_drive_files WHERE folder_id=%s ORDER BY filename",
                (folder_id,),
            )
            for r in cur.fetchall():
                ext = os.path.splitext(r["filename"])[1].lower()
                if ext in HDRI_EXT:
                    return jsonify({"file": {
                        "id": r["id"], "filename": r["filename"], "ext": ext.lstrip("."),
                        "url": f"/api/public/rendering/file/{r['id']}",
                    }})
            return jsonify({"file": None})
    finally:
        conn.close()


@app.get("/api/public/rendering/pbr")
def public_rendering_pbr():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            folder_id = _folder_id_setting(cur, "rendering_pbr_folder_id")
            if folder_id is None:
                return jsonify({"roles": {}})
            cur.execute(
                "SELECT id, filename FROM shared_drive_files WHERE folder_id=%s ORDER BY filename",
                (folder_id,),
            )
            roles = {}
            for r in cur.fetchall():
                role = _detect_pbr_role(r["filename"])
                if role and role not in roles:  # prvni nalezeny soubor dane role vyhrava
                    roles[role] = {
                        "id": r["id"], "filename": r["filename"],
                        "url": f"/api/public/rendering/file/{r['id']}",
                    }
            return jsonify({"roles": roles})
    finally:
        conn.close()


@app.get("/api/public/rendering/file/<int:file_id>")
def public_rendering_file(file_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            hdri_folder_id = _folder_id_setting(cur, "rendering_hdri_folder_id")
            pbr_folder_id = _folder_id_setting(cur, "rendering_pbr_folder_id")
            cur.execute("SELECT * FROM shared_drive_files WHERE id=%s", (file_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Soubor neexistuje."}), 404
    # KRITICKE: verejne se smi cist jen soubor z prave AKTIVNI HDRI/PBR
    # slozky - zbytek Sdileneho disku zustava privatni (viz modulovy
    # docstring). Bez tehle kontroly by tenhle endpoint byl obecny
    # neautentizovany pristup ke KAZDEMU souboru na Sdilenem disku podle id.
    if row["folder_id"] not in (hdri_folder_id, pbr_folder_id):
        return jsonify({"error": "Soubor není veřejně dostupný."}), 403
    try:
        with open(os.path.join(DRIVE_FILES_DIR, row["stored_filename"]), "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "Soubor na disku chybí."}), 404
    return Response(data, mimetype=row["content_type"] or "application/octet-stream", headers={
        "Content-Disposition": content_disposition(row["filename"]),
        "Cache-Control": "public, max-age=300",
    })
