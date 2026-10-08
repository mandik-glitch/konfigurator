"""
Sdileny disk (nahrada Google Drive sdilenych slozek) - bot5, 2026-08-01.

Robert: "na google drive máme sdílené složky a chci je tam zrušit a
vést sdílený disk (složky prostě uložiště) na našem serveru" ->
upresneno pres AskUserQuestion: vlastni modul primo v administraci
(stejne prihlaseni jako admin), postaveny na uz overenem vzoru
slozky/soubory z Nabidek (viz api/quotes.py).

Na rozdil od quotes.py (kde kazda nabidka ma VLASTNI strom slozek)
je tohle JEDEN globalni strom pro celou firmu - zadne "korenove"
id v URL, jen /api/admin/drive/folders[...] a /api/admin/drive/files[...].

Soubory NEJSOU pod webapp/ (cely adresar je nginxem servirovan
staticky, viz /etc/nginx/sites-enabled/konfigurator) - ukladaji se do
PRIVATE_FILES_DIR/shared-drive/ (mimo nginx docroot). Stazeni jde jen
pres autentizovany endpoint, VZDY Content-Disposition: attachment
(nikdy inline) - stejna pojistka proti stored XSS jako u Nabidek.

Endpointy (admin, @require_permission("sdileny_disk", ...)):
  GET              /api/admin/drive                        - cely strom + soubory v koreni
  POST/PUT/DELETE  /api/admin/drive/folders[/<fid>]
  POST/PUT/DELETE  /api/admin/drive/files[/<fid>]
  GET              /api/admin/drive/files/<fid>/download

Aktivace: `import drive` na konec app.py.
"""
import os
import re
import json

from flask import request, jsonify, Response

from app import app, get_conn, current_user, require_permission, admin_required, log_audit, PERMISSION_ROLES
from quotes import safe_stored_filename, content_disposition, PRIVATE_FILES_DIR

DRIVE_FILES_DIR = os.path.join(PRIVATE_FILES_DIR, "shared-drive")
os.makedirs(DRIVE_FILES_DIR, exist_ok=True)

# Omezeni pristupu podle role - jen na TOP-LEVEL slozkach (bot4,
# 2026-08-05, viz sql/2026-08-05_shared_drive_folder_roles.sql). Role,
# ktere lze u slozky nastavit ("admin" vzdy pristupny, nema smysl ho
# zaskrtavat).
DRIVE_EDITABLE_ROLES = tuple(r for r in PERMISSION_ROLES if r != "admin")


def _root_folder_id(cur, folder_id):
    """Projde parent_folder_id az k nejvyssimu predkovi (slozka bez
    rodice) - to je jednotka, na ktere se resi pristup podle role."""
    if folder_id is None:
        return None
    cur.execute("SELECT id, parent_folder_id FROM shared_drive_folders")
    parent_of = {r["id"]: r["parent_folder_id"] for r in cur.fetchall()}
    current, seen = folder_id, set()
    while parent_of.get(current) is not None:
        if current in seen:
            break
        seen.add(current)
        current = parent_of[current]
    return current


def _folder_allowed_roles(cur, root_folder_id):
    if root_folder_id is None:
        return []
    cur.execute("SELECT role FROM shared_drive_folder_roles WHERE folder_id=%s", (root_folder_id,))
    return [r["role"] for r in cur.fetchall()]


def _user_can_access_folder(cur, user, folder_id):
    """folder_id=None (koren disku) je vzdy pristupny - omezeni existuje
    jen na urovni top-level slozek. Admin vzdy pristupny (stejna
    pojistka jako has_permission v app.py). Slozka bez zadneho radku v
    shared_drive_folder_roles je neomezena (zpetna kompatibilita)."""
    if folder_id is None or user["role"] == "admin":
        return True
    root_id = _root_folder_id(cur, folder_id)
    if root_id is None:
        return True
    allowed = _folder_allowed_roles(cur, root_id)
    if not allowed:
        return True
    return user["role"] in allowed


def _serialize_folder(row):
    return {
        "id": row["id"], "parent_folder_id": row["parent_folder_id"],
        "name": row["name"], "sort_order": row["sort_order"],
        "created_by": row["created_by"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _serialize_file(row):
    return {
        "id": row["id"], "folder_id": row["folder_id"],
        "filename": row["filename"], "content_type": row["content_type"], "size_bytes": row["size_bytes"],
        "uploaded_by": row["uploaded_by"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@app.get("/api/admin/drive")
@require_permission("sdileny_disk", "zobrazit")
def drive_admin_tree():
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shared_drive_folders ORDER BY sort_order, name")
            folders = cur.fetchall()
            cur.execute("SELECT * FROM shared_drive_files ORDER BY sort_order, filename")
            files = cur.fetchall()
            cur.execute("SELECT folder_id, role FROM shared_drive_folder_roles")
            roles_by_folder = {}
            for r in cur.fetchall():
                roles_by_folder.setdefault(r["folder_id"], []).append(r["role"])
    finally:
        conn.close()

    by_parent = {}
    for f in folders:
        by_parent.setdefault(f["parent_folder_id"], []).append(f)
    files_by_folder = {}
    for fl in files:
        files_by_folder.setdefault(fl["folder_id"], []).append(fl)

    def build(parent_id, allowed=True):
        # Omezeni podle role plati jen na TOP-LEVEL slozkach (parent_id is
        # None) - hlubsi urovne dedi "allowed" od sve top-level predchudkyne.
        # Uzamcena top-level slozka ZUSTAVA VE STROMU VIDITELNA (Robert:
        # "slozka je vidět, ale uzamčená"), jen bez deti/souboru - at
        # neprozradi jejich nazvy.
        out = []
        for f in by_parent.get(parent_id, []):
            if parent_id is None:
                allowed_roles = roles_by_folder.get(f["id"], [])
                this_allowed = user["role"] == "admin" or not allowed_roles or user["role"] in allowed_roles
            else:
                allowed_roles = None
                this_allowed = allowed
            node = {
                **_serialize_folder(f),
                "children": build(f["id"], this_allowed) if this_allowed else [],
                "files": [_serialize_file(x) for x in files_by_folder.get(f["id"], [])] if this_allowed else [],
                "locked": not this_allowed,
            }
            if parent_id is None:
                node["allowed_roles"] = allowed_roles
            out.append(node)
        return out

    return jsonify({
        "folders": build(None),
        "root_files": [_serialize_file(x) for x in files_by_folder.get(None, [])],
    })


# ---------------------------------------------------------------------------
# Slozky
# ---------------------------------------------------------------------------

@app.post("/api/admin/drive/folders")
@require_permission("sdileny_disk", "vytvorit")
def drive_admin_folder_create():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Název složky je povinný."}), 400
    parent_folder_id = body.get("parent_folder_id") or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if parent_folder_id:
                cur.execute("SELECT id FROM shared_drive_folders WHERE id=%s", (parent_folder_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Nadřazená složka neexistuje."}), 400
                if not _user_can_access_folder(cur, admin, parent_folder_id):
                    return jsonify({"error": "Nemáte přístup k této složce."}), 403
            cur.execute(
                "INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
                (parent_folder_id, name, admin["id"]),
            )
            folder_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": folder_id}), 201


@app.put("/api/admin/drive/folders/<int:folder_id>")
@require_permission("sdileny_disk", "upravit")
def drive_admin_folder_update(folder_id):
    user = current_user()
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Název složky nesmí být prázdný."}), 400
        fields.append("name=%s"); params.append(name)
    if "parent_folder_id" in body:
        fields.append("parent_folder_id=%s"); params.append(body.get("parent_folder_id") or None)
    if not fields:
        return jsonify({"error": "Nebyla zadána žádná změna."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shared_drive_folders WHERE id=%s", (folder_id,))
            if not cur.fetchone():
                return jsonify({"error": "Složka neexistuje."}), 404
            if not _user_can_access_folder(cur, user, folder_id):
                return jsonify({"error": "Nemáte přístup k této složce."}), 403
            new_parent = body.get("parent_folder_id") if "parent_folder_id" in body else None
            if new_parent:
                if not _user_can_access_folder(cur, user, new_parent):
                    return jsonify({"error": "Nemáte přístup k cílové složce."}), 403
                # Omezena top-level slozka (ma vlastni radky v shared_drive_folder_roles)
                # se nesmi presunout dovnitr jine - jinak by omezeni tise "osirelo"
                # (prestalo platit, protoze uz neni top-level).
                cur.execute("SELECT 1 FROM shared_drive_folder_roles WHERE folder_id=%s LIMIT 1", (folder_id,))
                if cur.fetchone():
                    return jsonify({"error": "Složka má nastavené omezení podle role - nejdřív ho zrušte, než ji přesunete do jiné složky."}), 400
                # Zabranit cyklu - novy rodic nesmi byt sam sobe ani vlastnimu potomkovi.
                cur.execute("SELECT id, parent_folder_id FROM shared_drive_folders")
                parent_of = {r["id"]: r["parent_folder_id"] for r in cur.fetchall()}
                walker, seen = new_parent, set()
                while walker is not None:
                    if walker == folder_id:
                        return jsonify({"error": "Nelze přesunout složku do sebe/vlastního podstromu."}), 400
                    if walker in seen:
                        break
                    seen.add(walker)
                    walker = parent_of.get(walker)
            params.append(folder_id)
            cur.execute(f"UPDATE shared_drive_folders SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.put("/api/admin/drive/folders/<int:folder_id>/roles")
@admin_required
def drive_admin_folder_roles_update(folder_id):
    """Sprava omezeni pristupu podle role - vyhradne admin (stejny
    duvod jako u admin_role_permissions_update v app.py: sprava
    opravneni ostatnich roli je citliva operace)."""
    body = request.get_json(silent=True) or {}
    roles = body.get("roles")
    if not isinstance(roles, list) or any(not isinstance(r, str) for r in roles):
        return jsonify({"error": "roles musí být pole názvů rolí."}), 400
    invalid = [r for r in roles if r not in DRIVE_EDITABLE_ROLES]
    if invalid:
        return jsonify({"error": f"Neplatná role: {invalid[0]}"}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT parent_folder_id FROM shared_drive_folders WHERE id=%s", (folder_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Složka neexistuje."}), 404
            if row["parent_folder_id"] is not None:
                return jsonify({"error": "Omezení podle role lze nastavit jen na složce nejvyšší úrovně."}), 400
            cur.execute("DELETE FROM shared_drive_folder_roles WHERE folder_id=%s", (folder_id,))
            for role in sorted(set(roles)):
                cur.execute("INSERT INTO shared_drive_folder_roles (folder_id, role) VALUES (%s,%s)", (folder_id, role))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


def _collect_folder_subtree_ids(cur, folder_id):
    cur.execute("SELECT id, parent_folder_id FROM shared_drive_folders")
    children_by_parent = {}
    for r in cur.fetchall():
        children_by_parent.setdefault(r["parent_folder_id"], []).append(r["id"])
    ids, stack = [folder_id], [folder_id]
    while stack:
        current = stack.pop()
        for child_id in children_by_parent.get(current, []):
            ids.append(child_id)
            stack.append(child_id)
    return ids


@app.delete("/api/admin/drive/folders/<int:folder_id>")
@require_permission("sdileny_disk", "smazat")
def drive_admin_folder_delete(folder_id):
    """Smaze slozku VCETNE cele podslozkove vetve a VSECH souboru v ni.
    fk_sdfiles_folder je ON DELETE CASCADE (na rozdil od puvodni verze
    u Nabidek, kde SET NULL zpusobilo FK konflikt pri souvisejicim
    mazani - viz sql/2026-08-01_crm_quote_files_folder_fk_fix.sql) -
    DB kaskada by tedy soubory smazala sama, ale fyzicke soubory na
    disku uklizime explicitne PRED DB DELETE, at nezustanou osirele."""
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shared_drive_folders WHERE id=%s", (folder_id,))
            if not cur.fetchone():
                return jsonify({"error": "Složka neexistuje."}), 404
            if not _user_can_access_folder(cur, user, folder_id):
                return jsonify({"error": "Nemáte přístup k této složce."}), 403
            folder_ids = _collect_folder_subtree_ids(cur, folder_id)
            placeholders = ",".join(["%s"] * len(folder_ids))
            cur.execute(f"SELECT stored_filename FROM shared_drive_files WHERE folder_id IN ({placeholders})", folder_ids)
            file_rows = cur.fetchall()
            cur.execute("DELETE FROM shared_drive_folders WHERE id=%s", (folder_id,))
        conn.commit()
    finally:
        conn.close()
    for r in file_rows:
        try:
            os.remove(os.path.join(DRIVE_FILES_DIR, r["stored_filename"]))
        except OSError:
            pass
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Soubory
# ---------------------------------------------------------------------------

def _find_or_create_folder_path(cur, admin, root_folder_id, segments, cache):
    """Robert 2026-08-21 ("udelej sdileny disk... aby mohl uploadovat cely
    strom se soubory uvnitr"): najde/vytvori retez podslozek pod
    root_folder_id podle segments (napr. ["Karoserie","Ford"]) -
    kazdy segment jedna uroven, znovupouzije uz existujici podslozku
    stejneho jmena misto duplikovani (dulezite pri opakovanem nahravani
    stromu s stovkami souboru - user reuploadne totez, nechceme desitky
    duplicitnich slozek "Ford", "Ford (1)", ...). Vraci id nejhlubsi
    (listove) slozky. `cache` je dict sdileny jen v ramci JEDNOHO
    pozadavku (predava volajici) - ne globalni/modulovy stav, aby
    nehrozila kolize mezi soubeznymi requesty."""
    parent_id = root_folder_id
    for seg in segments:
        seg = seg.strip()[:255]
        if not seg:
            continue
        cache_key = (parent_id, seg)
        if cache_key in cache:
            parent_id = cache[cache_key]
            continue
        if parent_id is None:
            cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s", (seg,))
        else:
            cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s", (parent_id, seg))
        row = cur.fetchone()
        if row:
            parent_id = row["id"]
        else:
            cur.execute(
                "INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
                (parent_id, seg, admin["id"]),
            )
            parent_id = cur.lastrowid
        cache[cache_key] = parent_id
    return parent_id


@app.post("/api/admin/drive/files")
@require_permission("sdileny_disk", "vytvorit")
def drive_admin_files_upload():
    admin = current_user()
    folder_id = request.form.get("folder_id", type=int)
    files = request.files.getlist("files")
    # Robert 2026-08-21: volitelny paralelni seznam relativnich cest (JSON
    # pole stringu, stejna delka/poradi jako "files") - kdyz pritomny,
    # kazdy soubor se ulozi do odpovidajici (najde/vytvori) podslozky
    # PODLE SLOZEK V CESTE (bez posledniho segmentu = nazev souboru),
    # misto placeho ulozeni vseho do jedne cilove slozky. Umoznuje
    # nahrat cely adresarovy strom (webkitdirectory na frontendu) a
    # zachovat jeho strukturu.
    paths_raw = request.form.get("paths")
    paths = None
    if paths_raw:
        try:
            paths = json.loads(paths_raw)
        except (ValueError, TypeError):
            return jsonify({"error": "Neplatný formát cest (paths)."}), 400
        if not isinstance(paths, list) or len(paths) != len(files):
            return jsonify({"error": "Počet cest neodpovídá počtu souborů."}), 400
    files = [(i, f) for i, f in enumerate(files) if f and f.filename]
    if not files:
        return jsonify({"error": "Chybí soubor."}), 400
    conn = get_conn()
    created = []
    skipped = []
    try:
        with conn.cursor() as cur:
            if folder_id:
                cur.execute("SELECT id FROM shared_drive_folders WHERE id=%s", (folder_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Složka neexistuje."}), 400
                if not _user_can_access_folder(cur, admin, folder_id):
                    return jsonify({"error": "Nemáte přístup k této složce."}), 403
            folder_cache = {}
            for i, f in files:
                target_folder_id = folder_id
                if paths:
                    segments = [s for s in re.split(r"[\\/]+", paths[i]) if s][:-1]  # bez nazvu souboru
                    if segments:
                        target_folder_id = _find_or_create_folder_path(cur, admin, folder_id, segments, folder_cache)
                if paths:
                    # Robert 2026-08-21 ("kdyz to spadne musí se to obnovit...
                    # ať se to nepřepisuje zbytečně"): u stromoveho uploadu
                    # (paths pritomne) je bezpecne OPAKOVANI cely postup
                    # DULEZITEJSI nez umoznit zamerny duplicitni nazev - soubor
                    # se stejnym jmenem uz v cilove slozce se PRESKOCI (ne
                    # prepise, ne zduplikuje). Diky tomu je re-upload cele
                    # stejne slozky po vypadku bezpecny: uz hotove se tise
                    # preskoci, dokonci se jen zbytek.
                    if target_folder_id is None:
                        cur.execute("SELECT id FROM shared_drive_files WHERE folder_id IS NULL AND filename=%s", (f.filename[:255],))
                    else:
                        cur.execute("SELECT id FROM shared_drive_files WHERE folder_id=%s AND filename=%s", (target_folder_id, f.filename[:255]))
                    if cur.fetchone():
                        skipped.append(f.filename)
                        continue
                stored_filename = safe_stored_filename(f.filename)
                dest = os.path.join(DRIVE_FILES_DIR, stored_filename)
                f.save(dest)
                size_bytes = os.path.getsize(dest)
                cur.execute(
                    "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, "
                    "size_bytes, uploaded_by) VALUES (%s,%s,%s,%s,%s,%s)",
                    (target_folder_id, f.filename[:255], stored_filename, f.mimetype, size_bytes, admin["id"]),
                )
                created.append(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "upload", "shared_drive_file",
              None, f"{len(created)} souborů" + (f", {len(skipped)} přeskočeno (už existovalo)" if skipped else ""))
    return jsonify({"status": "ok", "ids": created, "skipped": skipped}), 201


@app.put("/api/admin/drive/files/<int:file_id>")
@require_permission("sdileny_disk", "upravit")
def drive_admin_files_update(file_id):
    user = current_user()
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "filename" in body:
        fn = (body.get("filename") or "").strip()
        if not fn:
            return jsonify({"error": "Název souboru nesmí být prázdný."}), 400
        fields.append("filename=%s"); params.append(fn[:255])
    if "folder_id" in body:
        fields.append("folder_id=%s"); params.append(body.get("folder_id") or None)
    if not fields:
        return jsonify({"error": "Nebyla zadána žádná změna."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, folder_id FROM shared_drive_files WHERE id=%s", (file_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Soubor neexistuje."}), 404
            if not _user_can_access_folder(cur, user, row["folder_id"]):
                return jsonify({"error": "Nemáte přístup k této složce."}), 403
            if body.get("folder_id"):
                cur.execute("SELECT id FROM shared_drive_folders WHERE id=%s", (body["folder_id"],))
                if not cur.fetchone():
                    return jsonify({"error": "Složka neexistuje."}), 400
                if not _user_can_access_folder(cur, user, body["folder_id"]):
                    return jsonify({"error": "Nemáte přístup k cílové složce."}), 403
            params.append(file_id)
            cur.execute(f"UPDATE shared_drive_files SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.delete("/api/admin/drive/files/<int:file_id>")
@require_permission("sdileny_disk", "smazat")
def drive_admin_files_delete(file_id):
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT stored_filename, folder_id FROM shared_drive_files WHERE id=%s", (file_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Soubor neexistuje."}), 404
            if not _user_can_access_folder(cur, user, row["folder_id"]):
                return jsonify({"error": "Nemáte přístup k této složce."}), 403
            cur.execute("DELETE FROM shared_drive_files WHERE id=%s", (file_id,))
        conn.commit()
    finally:
        conn.close()
    try:
        os.remove(os.path.join(DRIVE_FILES_DIR, row["stored_filename"]))
    except OSError:
        pass
    return jsonify({"status": "ok"})


@app.get("/api/admin/drive/files/<int:file_id>/download")
@require_permission("sdileny_disk", "zobrazit")
def drive_admin_files_download(file_id):
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shared_drive_files WHERE id=%s", (file_id,))
            row = cur.fetchone()
            if row and not _user_can_access_folder(cur, user, row["folder_id"]):
                return jsonify({"error": "Nemáte přístup k této složce."}), 403
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Soubor neexistuje."}), 404
    try:
        with open(os.path.join(DRIVE_FILES_DIR, row["stored_filename"]), "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "Soubor na disku chybí."}), 404
    return Response(data, mimetype=row["content_type"] or "application/octet-stream", headers={
        "Content-Disposition": content_disposition(row["filename"]),
    })


@app.get("/api/admin/drive/files/<int:file_id>/preview")
@require_permission("sdileny_disk", "zobrazit")
def drive_admin_files_preview(file_id):
    """Nahled PDF primo v adminu (Robert: "u nabidek PDF v disku, vytvor
    moznost zobrazit primo v adminu" - mirror quotes.py::quotes_admin_files_preview,
    stejne zduvodneni: /download vyse zustava vzdy attachment (pojistka
    proti stored XSS), inline se povoli jen kdyz OBSAH souboru zacina
    magic bytes %PDF- (ne stored content_type/pripona - oboji nedoveryhodne)."""
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shared_drive_files WHERE id=%s", (file_id,))
            row = cur.fetchone()
            if row and not _user_can_access_folder(cur, user, row["folder_id"]):
                return jsonify({"error": "Nemáte přístup k této složce."}), 403
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Soubor neexistuje."}), 404
    try:
        with open(os.path.join(DRIVE_FILES_DIR, row["stored_filename"]), "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "Soubor na disku chybí."}), 404
    if not data.startswith(b"%PDF-"):
        return jsonify({"error": "Náhled je dostupný jen pro PDF soubory."}), 415
    safe_ascii = "".join(c if 32 <= ord(c) < 127 and c != '"' else "_" for c in (row["filename"] or "")) or "soubor"
    return Response(data, mimetype="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{safe_ascii}"',
        "X-Content-Type-Options": "nosniff",
    })
