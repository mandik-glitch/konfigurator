"""Admin CRUD pro tri samostatne CMS "dlazdicove" mechanismy: homepage
mozaika (homepage_blocks), hlasky na homepage (announcement_items) a
postranni panel (sidebar_blocks) - kazdy vlastni tabulka/slug/admin
sekce, zadny sdileny mechanismus mezi nimi.

POZOR: verejne SSR renderovani techto bloku na homepage
(_render_homepage_mosaic_html, _render_announcement_preview_html) a
sdilene SEO helpery (_content_file_dimensions, _og_image_1200x630*)
ZUSTAVAJI v app.py - pouziva je i kod mimo tenhle modul (homepage/
kategorie SSR, jeste nevycleneny). Verejny GET /api/sidebar-blocks
(napaji panel v sidebaru na vsech strankach) je ale soucasti tohoto
modulu, protoze nema zadnou vazbu na to, co zustava v app.py.

Vycleneno z api/app.py (bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 2) - cisty presun, zadna zmena chovani/URL.
"""
import os
import re
import shutil

from flask import request, jsonify

from app import (
    app, get_conn, require_permission, current_user, log_audit,
    UPLOAD_DIR, ALLOWED_CATEGORY_IMAGE_EXT, _slugify, get_setting,
)
import gallery_items

# ---------------------------------------------------------------------
# Homepage mozaika (Robert 2026-08-09: "na homepage vytvoř system
# sudeho poctu oken, ktere lze pridavat a odebirat... mozaika...
# pozitivni vliv na SEO/GEO... funkce jakoby mala web stranka
# zmensena, kde lze menit nazev, meta popis, obrazek, telo textu").
# AskUserQuestion: kazda dlazdice odkazuje na VLASTNI stranku
# (/blok/<slug>) se skutecnym title/meta description - realny SEO
# prinos (vic indexovatelnych stranek), ne jen kosmeticky prvek.
# Robert 2026-08-09 ("zrusme sudost" / "nemusi byt sude") - puvodni
# pozadavek na SUDY pocet viditelnych dlazdic zamerne zruseny, zadne
# omezeni poctu v CRUD endpointech nize.
# ---------------------------------------------------------------------
HOMEPAGE_BLOCK_IMAGE_DIR = os.path.join(UPLOAD_DIR, "homepage-blocks")
os.makedirs(HOMEPAGE_BLOCK_IMAGE_DIR, exist_ok=True)


def _unique_homepage_block_slug(cur, base, exclude_id=None):
    candidate = base
    n = 2
    while True:
        if exclude_id is not None:
            cur.execute("SELECT id FROM homepage_blocks WHERE slug=%s AND id<>%s", (candidate, exclude_id))
        else:
            cur.execute("SELECT id FROM homepage_blocks WHERE slug=%s", (candidate,))
        if not cur.fetchone():
            return candidate
        candidate = f"{base}-{n}"
        n += 1


# Musi odpovidat GALLERY_CATEGORIES/GALLERY_CATEGORY_LABELS v
# api/gallery.py (nejde primo importovat - gallery.py samo importuje z
# app.py, viz jeho docstring "Aktivace: import gallery na konec app.py").
HOMEPAGE_GALLERY_CATEGORIES = {
    "vestavby_dodavek": "Vestavby do dodávek",
    "realizace_stolu": "Realizace stolů a pracovišť",
}


def _homepage_block_public(b):
    return {
        "id": b["id"], "title": b["title"], "slug": b["slug"],
        "meta_description": b["meta_description"],
        "image_url": f"/content-files/homepage-blocks/{b['image_filename']}" if b.get("image_filename") else None,
        "sort_order": b["sort_order"], "is_visible": bool(b["is_visible"]),
        "gallery_preview": bool(b.get("gallery_preview")),
        "gallery_category": b.get("gallery_category"),
    }


@app.get("/api/admin/homepage-blocks")
@require_permission("homepage_mozaika", "zobrazit")
def admin_homepage_blocks_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM homepage_blocks ORDER BY sort_order ASC, id ASC")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"blocks": [_homepage_block_public(b) for b in rows]})


@app.get("/api/admin/homepage-blocks/<int:block_id>")
@require_permission("homepage_mozaika", "zobrazit")
def admin_homepage_blocks_detail(block_id):
    # body_html chybi v /api/admin/homepage-blocks (seznam) - muze byt
    # velky, netreba ho tahat pro kazdy radek, jen pri otevreni editace.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM homepage_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Dlaždice nenalezena."}), 404
    data = _homepage_block_public(row)
    data["body_html"] = row["body_html"]
    return jsonify(data)


@app.post("/api/admin/homepage-blocks")
@require_permission("homepage_mozaika", "vytvorit")
def admin_homepage_blocks_create():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Chybí název."}), 400
    meta_description = (body.get("meta_description") or "").strip()[:500] or None
    body_html = body.get("body_html") or None
    is_visible = 1 if body.get("is_visible", True) else 0
    gallery_preview = 1 if body.get("gallery_preview") else 0
    gallery_category = (body.get("gallery_category") or "").strip() or None
    if gallery_category and gallery_category not in HOMEPAGE_GALLERY_CATEGORIES:
        return jsonify({"error": "Neplatná kategorie fotogalerie."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            slug = _unique_homepage_block_slug(cur, _slugify(title))
            cur.execute(
                "INSERT INTO homepage_blocks (title, slug, meta_description, body_html, sort_order, is_visible, gallery_preview, gallery_category) "
                "SELECT %s,%s,%s,%s, COALESCE(MAX(sort_order),0)+1, %s, %s, %s FROM homepage_blocks",
                (title, slug, meta_description, body_html, is_visible, gallery_preview, gallery_category),
            )
            block_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "homepage_block", block_id, title)
    return jsonify({"status": "ok", "id": block_id, "slug": slug})


@app.put("/api/admin/homepage-blocks/<int:block_id>")
@require_permission("homepage_mozaika", "upravit")
def admin_homepage_blocks_update(block_id):
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM homepage_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Dlaždice nenalezena."}), 404

            fields, params = [], []
            if "title" in body:
                title = (body.get("title") or "").strip()
                if not title:
                    return jsonify({"error": "Název nesmí být prázdný."}), 400
                fields.append("title=%s"); params.append(title)
                if title != row["title"]:
                    new_slug = _unique_homepage_block_slug(cur, _slugify(title), exclude_id=block_id)
                    fields.append("slug=%s"); params.append(new_slug)
            if "meta_description" in body:
                fields.append("meta_description=%s"); params.append((body.get("meta_description") or "").strip()[:500] or None)
            if "body_html" in body:
                fields.append("body_html=%s"); params.append(body.get("body_html") or None)
            if "is_visible" in body:
                fields.append("is_visible=%s"); params.append(1 if body.get("is_visible") else 0)
            if "gallery_preview" in body:
                fields.append("gallery_preview=%s"); params.append(1 if body.get("gallery_preview") else 0)
            if "gallery_category" in body:
                gallery_category = (body.get("gallery_category") or "").strip() or None
                if gallery_category and gallery_category not in HOMEPAGE_GALLERY_CATEGORIES:
                    return jsonify({"error": "Neplatná kategorie fotogalerie."}), 400
                fields.append("gallery_category=%s"); params.append(gallery_category)
            if "sort_order" in body:
                try:
                    fields.append("sort_order=%s"); params.append(int(body.get("sort_order")))
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné pořadí."}), 400

            if fields:
                params.append(block_id)
                cur.execute(f"UPDATE homepage_blocks SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "homepage_block", block_id, ", ".join(body.keys()))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/homepage-blocks/<int:block_id>")
@require_permission("homepage_mozaika", "smazat")
def admin_homepage_blocks_delete(block_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT image_filename, is_visible FROM homepage_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Dlaždice nenalezena."}), 404
            cur.execute("DELETE FROM homepage_blocks WHERE id=%s", (block_id,))
        conn.commit()
    finally:
        conn.close()
    if row.get("image_filename"):
        try:
            os.remove(os.path.join(HOMEPAGE_BLOCK_IMAGE_DIR, row["image_filename"]))
        except OSError:
            pass
    # Robert 2026-08-09 ("na dlazdici mozaiky homepage chceme umet vlozit
    # obrazek, video, apd") - obrazky vlozene primo do tela textu (Quill
    # editor, owner_type="homepage_block") uklidit stejne jako u kategorii
    # vyse, at po smazani dlazdice nezustanou osirele soubory/radky.
    gallery_items.delete_items_for_owner("homepage_block", block_id)
    log_audit(current_user()["id"], "delete", "homepage_block", block_id, "")
    return jsonify({"status": "ok"})


@app.post("/api/admin/homepage-blocks/<int:block_id>/image")
@require_permission("homepage_mozaika", "upravit")
def admin_homepage_blocks_image_upload(block_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_CATEGORY_IMAGE_EXT:
        return jsonify({"error": "Nepovolený formát obrázku (jpg/png/webp/gif)."}), 400
    stored_name = f"{block_id}_{os.urandom(6).hex()}.{ext}"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT image_filename FROM homepage_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Dlaždice nenalezena."}), 404
            old_name = row["image_filename"]
            f.save(os.path.join(HOMEPAGE_BLOCK_IMAGE_DIR, stored_name))
            cur.execute("UPDATE homepage_blocks SET image_filename=%s WHERE id=%s", (stored_name, block_id))
        conn.commit()
    finally:
        conn.close()
    if old_name:
        try:
            os.remove(os.path.join(HOMEPAGE_BLOCK_IMAGE_DIR, old_name))
        except OSError:
            pass
    log_audit(current_user()["id"], "update", "homepage_block", block_id, "obrázek dlaždice")
    return jsonify({"status": "ok", "image_filename": stored_name})


@app.post("/api/admin/homepage-blocks/<int:block_id>/image-from-library")
@require_permission("homepage_mozaika", "upravit")
def admin_homepage_blocks_image_from_library(block_id):
    # bot16, 2026-09-13 (Robert primo: "v kazde kategorii eshopu i v
    # dlazdicich mozaiky se nabidne adminovi moznost vlozit fotky z
    # centralni fotogalerie") - ALTERNATIVA k image_upload vyse: misto
    # cerstveho souboru z disku admina vezme existujici fotku z
    # content_photo_library (viz api/gallery.py "Knihovna fotek").
    #
    # ZAMERNE zkopiruje bajty do HOMEPAGE_BLOCK_IMAGE_DIR (stejne jako
    # klasicky upload), NEODKAZUJE se na content_photo_library.id primo -
    # dlazdice ma porad jen jeden staticky obrazek (image_filename), zadne
    # M:N jako u kategorii nize neni potreba (jedna dlazdice = jeden
    # obrazek, ne galerie). "Provazani se zarazovanim v adminu
    # fotogalerie" se tu projevuje jinak: admin fotku VYBIRA ze stejne
    # centralni knihovny, ne ze zvlastniho uploadu - zdrojova fotka v
    # knihovne zustava nedotcena a dal viditelna/spravovatelna tam.
    body = request.get_json(silent=True) or {}
    photo_id = body.get("photo_id")
    if not photo_id:
        return jsonify({"error": "Chybí photo_id."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT file_path FROM content_photo_library WHERE id=%s", (photo_id,))
            photo = cur.fetchone()
            if not photo:
                return jsonify({"error": "Fotka v knihovně nenalezena."}), 404
            cur.execute("SELECT image_filename FROM homepage_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Dlaždice nenalezena."}), 404
            old_name = row["image_filename"]
            src_path = photo["file_path"]
            ext = src_path.rsplit(".", 1)[-1].lower() if "." in src_path else "jpg"
            stored_name = f"{block_id}_{os.urandom(6).hex()}.{ext}"
            src_abs = os.path.join(os.path.dirname(UPLOAD_DIR), src_path)
            try:
                shutil.copyfile(src_abs, os.path.join(HOMEPAGE_BLOCK_IMAGE_DIR, stored_name))
            except OSError:
                return jsonify({"error": "Soubor fotky se nepodařilo najít na disku."}), 500
            cur.execute("UPDATE homepage_blocks SET image_filename=%s WHERE id=%s", (stored_name, block_id))
        conn.commit()
    finally:
        conn.close()
    if old_name:
        try:
            os.remove(os.path.join(HOMEPAGE_BLOCK_IMAGE_DIR, old_name))
        except OSError:
            pass
    log_audit(current_user()["id"], "update", "homepage_block", block_id, "obrázek dlaždice (z knihovny fotek)")
    return jsonify({"status": "ok", "image_filename": stored_name})


# ---------------------------------------------------------------------
# HLASKY (bot5 2026-08-10/11, Robert: "udelej pro homepage jednoduchý
# typ dlazdice povedle mozaiky, pro ohlašování nových zpráv novinek
# tzn jen text plnohodnotně pro seo... jen s možností menit barvy
# okrajů" -> (po iteraci) "tato dlaždice není o novinkách ale pro
# hlášky, dlaždici pro novinky udeláme extra jinou další" - PUVODNE
# postavena jako "Novinky" s vlastni SEO strankou na polozku
# (news_items), pak zjednodusena na kratke bezodkazovaci "hlasky" (viz
# _render_announcement_preview_html v app.py - zadna vlastni stranka,
# zadny klik-skrz, odkazy primo v textu zpravy) a nakonec PREJMENOVANA
# (tabulka news_items -> announcement_items, viz
# sql/2026-08-11_news_items_rename_to_announcements.sql), aby nazev
# nekoliduje se skutecnou budouci "Novinky" dlazdici (ta bude
# potrebovat vlastni tabulku/nazvy, az na ni dojde rada). 1 kompaktni
# dlazdice na homepage rotuje (JS crossfade) poslednich az 3 hlasky,
# zadna samostatna verejna stranka.
# ---------------------------------------------------------------------

def _announcement_item_public(n):
    return {
        "id": n["id"], "title": n["title"],
        "border_color": n.get("border_color"),
        "is_visible": bool(n["is_visible"]),
        "created_at": n["created_at"].isoformat() if n.get("created_at") else None,
    }


@app.get("/api/admin/announcement-items")
@require_permission("hlasky", "zobrazit")
def admin_announcement_items_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM announcement_items ORDER BY created_at DESC, id DESC")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"items": [_announcement_item_public(n) for n in rows]})


@app.get("/api/admin/announcement-items/<int:item_id>")
@require_permission("hlasky", "zobrazit")
def admin_announcement_items_detail(item_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM announcement_items WHERE id=%s", (item_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Hláška nenalezena."}), 404
    data = _announcement_item_public(row)
    data["body_html"] = row["body_html"]
    return jsonify(data)


def _valid_hex_color(s):
    return bool(s) and re.fullmatch(r"#[0-9a-fA-F]{6}", s or "")


@app.post("/api/admin/announcement-items")
@require_permission("hlasky", "vytvorit")
def admin_announcement_items_create():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Chybí název."}), 400
    body_html = body.get("body_html") or None
    is_visible = 1 if body.get("is_visible", True) else 0
    border_color = (body.get("border_color") or "").strip() or None
    if border_color and not _valid_hex_color(border_color):
        return jsonify({"error": "Neplatná barva (očekáván formát #rrggbb)."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO announcement_items (title, body_html, border_color, is_visible) "
                "VALUES (%s,%s,%s,%s)",
                (title, body_html, border_color, is_visible),
            )
            item_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "announcement_item", item_id, title)
    return jsonify({"status": "ok", "id": item_id})


@app.put("/api/admin/announcement-items/<int:item_id>")
@require_permission("hlasky", "upravit")
def admin_announcement_items_update(item_id):
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM announcement_items WHERE id=%s", (item_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Hláška nenalezena."}), 404

            fields, params = [], []
            if "title" in body:
                title = (body.get("title") or "").strip()
                if not title:
                    return jsonify({"error": "Název nesmí být prázdný."}), 400
                fields.append("title=%s"); params.append(title)
            if "body_html" in body:
                fields.append("body_html=%s"); params.append(body.get("body_html") or None)
            if "is_visible" in body:
                fields.append("is_visible=%s"); params.append(1 if body.get("is_visible") else 0)
            if "border_color" in body:
                border_color = (body.get("border_color") or "").strip() or None
                if border_color and not _valid_hex_color(border_color):
                    return jsonify({"error": "Neplatná barva (očekáván formát #rrggbb)."}), 400
                fields.append("border_color=%s"); params.append(border_color)

            if fields:
                params.append(item_id)
                cur.execute(f"UPDATE announcement_items SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "announcement_item", item_id, ", ".join(body.keys()))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/announcement-items/<int:item_id>")
@require_permission("hlasky", "smazat")
def admin_announcement_items_delete(item_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM announcement_items WHERE id=%s", (item_id,))
            if not cur.fetchone():
                return jsonify({"error": "Hláška nenalezena."}), 404
            cur.execute("DELETE FROM announcement_items WHERE id=%s", (item_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "announcement_item", item_id, "")
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------
# POSTRANNI PANEL (bot5 2026-08-10, Robert: "vloz tam nejdrive panel
# ktery bude videt vzdy na vsech url webu jakoby paticka ale je to
# vlevo pod menu" -> "měla by to být v podstatě další dlaždice,
# akorát má jiné umístění" -> "udelej novou sekci v adminu, a dlazdici
# tam prenes, prekopiruj") - SAMOSTATNA obdoba homepage_blocks (vlastni
# tabulka/admin sekce/verejna stranka), ne sdileny mechanismus - jen
# jine umisteni (levy sidebar na VSECH strankach s menu kategorii, ne
# homepage mozaika) a navic video_filename (Robert: "to video tam
# vloží admin" - vlastni upload tlacitko pro video, ne jen pro
# nahledovy obrazek). Verejna stranka /panel/<slug> zustava v app.py
# (SSR, stejny duvod jako /blok/<slug>), tady jen samotna CRUD data +
# verejny GET /api/sidebar-blocks (napaji panel v sidebaru).
# ---------------------------------------------------------------------
SIDEBAR_BLOCK_IMAGE_DIR = os.path.join(UPLOAD_DIR, "sidebar-blocks")
os.makedirs(SIDEBAR_BLOCK_IMAGE_DIR, exist_ok=True)
SIDEBAR_BLOCK_VIDEO_DIR = os.path.join(UPLOAD_DIR, "sidebar-blocks-video")
os.makedirs(SIDEBAR_BLOCK_VIDEO_DIR, exist_ok=True)
ALLOWED_SIDEBAR_BLOCK_VIDEO_EXT = {"mp4", "webm", "mov"}


def _unique_sidebar_block_slug(cur, base, exclude_id=None):
    candidate = base
    n = 2
    while True:
        if exclude_id is not None:
            cur.execute("SELECT id FROM sidebar_blocks WHERE slug=%s AND id<>%s", (candidate, exclude_id))
        else:
            cur.execute("SELECT id FROM sidebar_blocks WHERE slug=%s", (candidate,))
        if not cur.fetchone():
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def _sidebar_block_public(b):
    return {
        "id": b["id"], "title": b["title"], "slug": b["slug"],
        "meta_description": b["meta_description"],
        "image_url": f"/content-files/sidebar-blocks/{b['image_filename']}" if b.get("image_filename") else None,
        "video_url": f"/content-files/sidebar-blocks-video/{b['video_filename']}" if b.get("video_filename") else None,
        "sort_order": b["sort_order"], "is_visible": bool(b["is_visible"]),
    }


@app.get("/api/sidebar-blocks")
def sidebar_blocks_public():
    # VEREJNE - napaje panel v levem sidebaru na index/category/product/
    # blok.html (viz webapp/*.html renderSidebarFooter()).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sidebar_blocks WHERE is_visible=1 ORDER BY sort_order ASC, id ASC")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"blocks": [_sidebar_block_public(b) for b in rows]})


@app.get("/api/admin/sidebar-blocks")
@require_permission("postranni_panel", "zobrazit")
def admin_sidebar_blocks_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sidebar_blocks ORDER BY sort_order ASC, id ASC")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"blocks": [_sidebar_block_public(b) for b in rows]})


@app.get("/api/admin/sidebar-blocks/<int:block_id>")
@require_permission("postranni_panel", "zobrazit")
def admin_sidebar_blocks_detail(block_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sidebar_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Panel nenalezen."}), 404
    data = _sidebar_block_public(row)
    data["body_html"] = row["body_html"]
    return jsonify(data)


@app.post("/api/admin/sidebar-blocks")
@require_permission("postranni_panel", "vytvorit")
def admin_sidebar_blocks_create():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Chybí název."}), 400
    meta_description = (body.get("meta_description") or "").strip()[:500] or None
    body_html = body.get("body_html") or None
    is_visible = 1 if body.get("is_visible", True) else 0

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            slug = _unique_sidebar_block_slug(cur, _slugify(title))
            cur.execute(
                "INSERT INTO sidebar_blocks (title, slug, meta_description, body_html, sort_order, is_visible) "
                "SELECT %s,%s,%s,%s, COALESCE(MAX(sort_order),0)+1, %s FROM sidebar_blocks",
                (title, slug, meta_description, body_html, is_visible),
            )
            block_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "sidebar_block", block_id, title)
    return jsonify({"status": "ok", "id": block_id, "slug": slug})


@app.put("/api/admin/sidebar-blocks/<int:block_id>")
@require_permission("postranni_panel", "upravit")
def admin_sidebar_blocks_update(block_id):
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sidebar_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Panel nenalezen."}), 404

            fields, params = [], []
            if "title" in body:
                title = (body.get("title") or "").strip()
                if not title:
                    return jsonify({"error": "Název nesmí být prázdný."}), 400
                fields.append("title=%s"); params.append(title)
                if title != row["title"]:
                    new_slug = _unique_sidebar_block_slug(cur, _slugify(title), exclude_id=block_id)
                    fields.append("slug=%s"); params.append(new_slug)
            if "meta_description" in body:
                fields.append("meta_description=%s"); params.append((body.get("meta_description") or "").strip()[:500] or None)
            if "body_html" in body:
                fields.append("body_html=%s"); params.append(body.get("body_html") or None)
            if "is_visible" in body:
                fields.append("is_visible=%s"); params.append(1 if body.get("is_visible") else 0)
            if "sort_order" in body:
                try:
                    fields.append("sort_order=%s"); params.append(int(body.get("sort_order")))
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné pořadí."}), 400

            if fields:
                params.append(block_id)
                cur.execute(f"UPDATE sidebar_blocks SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "sidebar_block", block_id, ", ".join(body.keys()))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/sidebar-blocks/<int:block_id>")
@require_permission("postranni_panel", "smazat")
def admin_sidebar_blocks_delete(block_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT image_filename, video_filename FROM sidebar_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Panel nenalezen."}), 404
            cur.execute("DELETE FROM sidebar_blocks WHERE id=%s", (block_id,))
        conn.commit()
    finally:
        conn.close()
    if row.get("image_filename"):
        try:
            os.remove(os.path.join(SIDEBAR_BLOCK_IMAGE_DIR, row["image_filename"]))
        except OSError:
            pass
    if row.get("video_filename"):
        try:
            os.remove(os.path.join(SIDEBAR_BLOCK_VIDEO_DIR, row["video_filename"]))
        except OSError:
            pass
    gallery_items.delete_items_for_owner("sidebar_block", block_id)
    log_audit(current_user()["id"], "delete", "sidebar_block", block_id, "")
    return jsonify({"status": "ok"})


@app.post("/api/admin/sidebar-blocks/<int:block_id>/image")
@require_permission("postranni_panel", "upravit")
def admin_sidebar_blocks_image_upload(block_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_CATEGORY_IMAGE_EXT:
        return jsonify({"error": "Nepovolený formát obrázku (jpg/png/webp/gif)."}), 400
    stored_name = f"{block_id}_{os.urandom(6).hex()}.{ext}"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT image_filename FROM sidebar_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Panel nenalezen."}), 404
            old_name = row["image_filename"]
            f.save(os.path.join(SIDEBAR_BLOCK_IMAGE_DIR, stored_name))
            cur.execute("UPDATE sidebar_blocks SET image_filename=%s WHERE id=%s", (stored_name, block_id))
        conn.commit()
    finally:
        conn.close()
    if old_name:
        try:
            os.remove(os.path.join(SIDEBAR_BLOCK_IMAGE_DIR, old_name))
        except OSError:
            pass
    log_audit(current_user()["id"], "update", "sidebar_block", block_id, "obrázek panelu")
    return jsonify({"status": "ok", "image_filename": stored_name})


@app.post("/api/admin/sidebar-blocks/<int:block_id>/video")
@require_permission("postranni_panel", "upravit")
def admin_sidebar_blocks_video_upload(block_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_SIDEBAR_BLOCK_VIDEO_EXT:
        return jsonify({"error": "Nepovolený formát videa (mp4/webm/mov)."}), 400
    stored_name = f"{block_id}_{os.urandom(6).hex()}.{ext}"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT video_filename FROM sidebar_blocks WHERE id=%s", (block_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Panel nenalezen."}), 404
            old_name = row["video_filename"]
            f.save(os.path.join(SIDEBAR_BLOCK_VIDEO_DIR, stored_name))
            cur.execute("UPDATE sidebar_blocks SET video_filename=%s WHERE id=%s", (stored_name, block_id))
        conn.commit()
    finally:
        conn.close()
    if old_name:
        try:
            os.remove(os.path.join(SIDEBAR_BLOCK_VIDEO_DIR, old_name))
        except OSError:
            pass
    log_audit(current_user()["id"], "update", "sidebar_block", block_id, "video panelu")
    return jsonify({"status": "ok", "video_filename": stored_name})


# ---------------------------------------------------------------------
# HOMEPAGE CAROUSEL (Robert pres bot3, 2026-09-27: "na nas homepage
# chceme stejny carousel jako je na homepage logimanu" - stary Shoptet
# e-shop stejne firmy, mechanismus okopirovan - autoplay crossfade
# 4000ms/600ms + sipky + puntiky, prvni slide aktivni). Zamerne SAMOSTATNA
# tabulka, ne rozsireni homepage_blocks - slide karuselu nema vlastni SEO
# stranku (zadny slug/meta_description/body_html), je to jen obrazek +
# volitelny odkaz + volitelny popisek + poradi + aktivni. Verejne SSR
# renderovani (_render_homepage_carousel_html) zustava v app.py, stejny
# vzor jako mozaika/hlasky vyse.
# ---------------------------------------------------------------------
HOMEPAGE_CAROUSEL_IMAGE_DIR = os.path.join(UPLOAD_DIR, "homepage-carousel")
os.makedirs(HOMEPAGE_CAROUSEL_IMAGE_DIR, exist_ok=True)


def _homepage_carousel_slide_public(s):
    return {
        "id": s["id"],
        "image_url": f"/content-files/homepage-carousel/{s['image_filename']}" if s.get("image_filename") else None,
        "caption_text": s.get("caption_text"),
        "link_url": s.get("link_url"),
        "sort_order": s["sort_order"], "is_visible": bool(s["is_visible"]),
    }


@app.get("/api/admin/homepage-carousel")
@require_permission("homepage_carousel", "zobrazit")
def admin_homepage_carousel_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM homepage_carousel_slides ORDER BY sort_order ASC, id ASC")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"slides": [_homepage_carousel_slide_public(s) for s in rows]})


@app.post("/api/admin/homepage-carousel")
@require_permission("homepage_carousel", "vytvorit")
def admin_homepage_carousel_create():
    body = request.get_json(silent=True) or {}
    caption_text = (body.get("caption_text") or "").strip()[:255] or None
    link_url = (body.get("link_url") or "").strip()[:500] or None
    is_visible = 1 if body.get("is_visible", True) else 0

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO homepage_carousel_slides (image_filename, caption_text, link_url, sort_order, is_visible) "
                "SELECT '', %s, %s, COALESCE(MAX(sort_order),0)+1, %s FROM homepage_carousel_slides",
                (caption_text, link_url, is_visible),
            )
            slide_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "homepage_carousel_slide", slide_id, caption_text or "")
    return jsonify({"status": "ok", "id": slide_id})


@app.put("/api/admin/homepage-carousel/<int:slide_id>")
@require_permission("homepage_carousel", "upravit")
def admin_homepage_carousel_update(slide_id):
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM homepage_carousel_slides WHERE id=%s", (slide_id,))
            if not cur.fetchone():
                return jsonify({"error": "Slide nenalezen."}), 404

            fields, params = [], []
            if "caption_text" in body:
                fields.append("caption_text=%s"); params.append((body.get("caption_text") or "").strip()[:255] or None)
            if "link_url" in body:
                fields.append("link_url=%s"); params.append((body.get("link_url") or "").strip()[:500] or None)
            if "is_visible" in body:
                fields.append("is_visible=%s"); params.append(1 if body.get("is_visible") else 0)
            if "sort_order" in body:
                try:
                    fields.append("sort_order=%s"); params.append(int(body.get("sort_order")))
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné pořadí."}), 400

            if fields:
                params.append(slide_id)
                cur.execute(f"UPDATE homepage_carousel_slides SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "homepage_carousel_slide", slide_id, ", ".join(body.keys()))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/homepage-carousel/<int:slide_id>")
@require_permission("homepage_carousel", "smazat")
def admin_homepage_carousel_delete(slide_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT image_filename FROM homepage_carousel_slides WHERE id=%s", (slide_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Slide nenalezen."}), 404
            cur.execute("DELETE FROM homepage_carousel_slides WHERE id=%s", (slide_id,))
        conn.commit()
    finally:
        conn.close()
    if row.get("image_filename"):
        try:
            os.remove(os.path.join(HOMEPAGE_CAROUSEL_IMAGE_DIR, row["image_filename"]))
        except OSError:
            pass
    log_audit(current_user()["id"], "delete", "homepage_carousel_slide", slide_id, "")
    return jsonify({"status": "ok"})


@app.post("/api/admin/homepage-carousel/<int:slide_id>/image")
@require_permission("homepage_carousel", "upravit")
def admin_homepage_carousel_image_upload(slide_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_CATEGORY_IMAGE_EXT:
        return jsonify({"error": "Nepovolený formát obrázku (jpg/png/webp/gif)."}), 400
    stored_name = f"{slide_id}_{os.urandom(6).hex()}.{ext}"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT image_filename FROM homepage_carousel_slides WHERE id=%s", (slide_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Slide nenalezen."}), 404
            old_name = row["image_filename"]
            f.save(os.path.join(HOMEPAGE_CAROUSEL_IMAGE_DIR, stored_name))
            cur.execute("UPDATE homepage_carousel_slides SET image_filename=%s WHERE id=%s", (stored_name, slide_id))
        conn.commit()
    finally:
        conn.close()
    if old_name:
        try:
            os.remove(os.path.join(HOMEPAGE_CAROUSEL_IMAGE_DIR, old_name))
        except OSError:
            pass
    log_audit(current_user()["id"], "update", "homepage_carousel_slide", slide_id, "obrázek slidu")
    return jsonify({"status": "ok", "image_filename": stored_name})


# ---------------------------------------------------------------------
# Uvodni text homepage (Robert primo: "pridej editovatelny text na
# homepage vcetne meta popisu") - meta popis homepage uz editovatelny
# byl (Sociální sítě > og-settings, viz api/admin_settings.py -
# _get_og_site_defaults() slouzi jako fallback pro stranky bez vlastniho
# obsahu, homepage predevsim), chybel ale VIDITELNY textovy blok na
# strance samotne. Jednoduchy app_settings radek (`homepage_intro_html`)
# misto cele nove tabulky - je to jen JEDEN kus textu, ne seznam
# polozek jako carousel/mozaika/sidebar. SSR render viz api/app.py
# (_index_page_response), umisteni AZ POD celou mozaikou (SEO substance
# pod vizualni castí, nerusi prvni dojem stranky).
# ---------------------------------------------------------------------

@app.get("/api/admin/homepage-intro-text")
@require_permission("homepage_mozaika", "zobrazit")
def admin_homepage_intro_text_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            html = get_setting(cur, "homepage_intro_html", "")
    finally:
        conn.close()
    return jsonify({"body_html": html or ""})


@app.put("/api/admin/homepage-intro-text")
@require_permission("homepage_mozaika", "upravit")
def admin_homepage_intro_text_set():
    body = request.get_json(silent=True) or {}
    html = (body.get("body_html") or "").strip()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES ('homepage_intro_html',%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (html, html),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "homepage_intro_html", None, "")
    return jsonify({"status": "ok"})
