"""
Fotogalerie realizaci - bot2, 2026-07-25.

Robert: "udelej sekce fotogalerie, systemove at se pohodlne nahravaji
hromadne obrazky, at se jim z hlediska SEO davaji vhodne nazvy, cerpej z
fotogalerii logiman.cz rovnou tam nacucni ty obrazky"

Verejna stranka realizaci (jako logiman.cz "Foto vestavby dodavek"/"Foto
realizace stolu") + admin sprava (hromadny upload vice souboru najednou,
import z URL, editace popisku/kategorie/poradi, mazani). Soubory se
ukladaji do webapp/content-files/gallery/<kategorie>/ (stejny adresar
jako existujici UPLOAD_DIR pro obsah kategorii v app.py, jen podslozka
"gallery") - servirovane nginxem staticky pres /content-files/..., zadny
Flask route na cteni samotnych souboru neni potreba (viz nginx.conf
"location /content-files/").

SEO nazvy: _seo_slug() prevede puvodni nazev (diakritika, mezery, cisla
na zacatku typu "2_", "1_1_004-...") na cisty ASCII slug s pomlckami,
napr. "3_ocelové šuplíky s pojistkami.jpg" -> "ocelove-supliky-s-pojistkami.jpg".
Pouziva se STEJNE pro rucni admin upload (gallery_admin_upload) i pro
import z URL (import_image_from_url, sdileno s jednorazovym
import_logiman_gallery.py skriptem) - Robert vyslovne chtel "systemove",
tedy jednotny zpusob pojmenovani bez ohledu na zdroj obrazku.

Aktivace: `import gallery` na konec app.py (za ostatnimi moduly, poradi
mezi nimi nezalezi - gallery.py nezavisi na orders/documents/emails).

bot10, 2026-09-12 (centralni fotogalerie, Robert pres bot3): DB vrstva
prepojena z `shop_gallery_images` na `content_photo_library`
(realizace_tag = puvodni "category" bucket) - jeden zdroj pravdy misto
tri nezavislych mechanismu, ktere zpusobily is_public diru (viz
sql/2026-09-12_content_photo_library.sql). API kontrakt (URL/JSON tvar)
zustava STEJNY - webapp/admin/js/fotogalerie.js a admin.html panel
#tab-gallery se nemeni, jen to, odkud data jdou. `shop_gallery_images`
zustava netknuta jako historicky zaznam, nic uz do ni nezapisuje.

Smazani (admin/bulk-delete) NEMAZE radek/soubor - jen zrusi realizace_tag
(radek muze byt soucasne prirazeny i kategorii pres M:N, viz
content_photo_library_categories - "smazani" v jednom pohledu nesmi
zpusobit zmizeni jinde, stejny princip jako u fronty kategorii). Skutecne
trvale smazani z knihovny je vyhrazeno pro budouci centralni obrazovku.

bot16, 2026-09-13 (Robert primo: "rozdeleni na 2 pada, v adminu aplikuj
novou verzi fotogalerie, viz navod verim ze tam je zapsany") - ten "navod"
neni samostatny soubor (hledano v AGENTS_LOG.md/TASKS.md/design-concepts/,
nenalezeno), je to presne tenhle odstavec vyse + stejna vyhrada v
gallery_items.py (renderGalleryModule) + SQL komentar Robertovych
vlastnich slov v sql/2026-09-12_content_photo_library.sql ("centralni
fotogalerie na jednom miste v adminu... z teto fotogalerie se budou
prirazovat do kategorii ruzne fotky") - bot10 uz fazi 3 (DB vrstva)
zamerne navrhl tak, aby "budouci centralni obrazovku" bylo mozne doplnit
bez dalsi migrace. Tohle je ta obrazovka - sekce "GALLERY LIBRARY"
nize, nova admin sekce "Cela knihovna" v #tab-gallery.

Zaroven oprava zivé regrese, kterou fáze 3 nechala za sebou: homepage
mozaika (_index_page_response, api/storefront_pages.py) cetla porad ze
`shop_gallery_images`, ktera uz od fe93b24e nedostava zadne nove zapisy -
admin edituje jen content_photo_library, takze by se mozaika od prvni
dalsi zmeny v adminu tise rozjela od /realizace.html. Prepojeno na
content_photo_library (stejny dotaz jako gallery_public_list nize).

"Rozdeleni na 2": zamerne NEMAZU `shop_gallery_images` (DROP TABLE je
nevratna operace na produkci) - jen jsem dopojil posledniho ctenare, ktery
z ni jeste bral data. Tabulka ted uz nema zadneho ctenare ani zapisovace -
bezpecne k fyzickemu smazani, az to Robert vyslovne potvrdi.
"""
import os
import re
import unicodedata

from flask import request, jsonify

from net_fetch import fetch_public_url
from app import (
    app, get_conn, require_permission, current_user, log_audit,
    parse_bulk_ids, bulk_update_fields, UPLOAD_DIR,
)
# bot10, 2026-09-12: realizace fotky teď sdílí STEJNÝ fyzický adresář
# jako zbytek centrální knihovny (content-files/gallery-items/) - import
# přímo odtud, ne vlastní nezávislá konstrukce cesty (jeden zdroj pravdy
# pro adresář stejně jako pro tabulku).
from gallery_items import GALLERY_ITEMS_DIR as GALLERY_ITEMS_DIR_FOR_REALIZACE

GALLERY_FETCH_TIMEOUT_S = 20
GALLERY_MAX_FETCH_BYTES = 20 * 1024 * 1024

GALLERY_CATEGORIES = ("vestavby_dodavek", "realizace_stolu")
GALLERY_CATEGORY_LABELS = {
    "vestavby_dodavek": "Vestavby do dodávek",
    "realizace_stolu": "Realizace stolů a pracovišť",
}
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}


def _seo_slug(original_name):
    """original_name vc. pripony -> (slug_base_bez_pripony, ext_lower).
    Diakritika pryc, mala pismena, mezery/podtrzitka/zavorky -> pomlcky,
    opakovane cislene prefixy na zacatku (Shoptet konvence "2_", "1_1_004-",
    "03_") odstraneny - viz docstring modulu."""
    base, _, ext = original_name.rpartition(".")
    if not base:
        base, ext = original_name, ""
    ext = ext.lower()
    if ext not in ALLOWED_EXT:
        ext = "jpg"
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"^(\d+[-_.]+)+", "", base)
    base = base.lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-")
    if not base:
        base = "obrazek"
    return base, ext


def _unique_filename(cur, base, ext):
    """Zaridi unikatnost jmena souboru (kolize -> -2, -3...) - VSECHNY
    fotky centralni knihovny sdileji jeden adresar (content-files/
    gallery-items/), takze unikatnost se overuje napric CELOU tabulkou,
    ne jen v ramci jedne realizace_tag hodnoty jako drive."""
    candidate = f"{base}.{ext}"
    n = 1
    while True:
        cur.execute(
            "SELECT 1 FROM content_photo_library WHERE file_path=%s",
            (f"content-files/gallery-items/{candidate}",),
        )
        if not cur.fetchone():
            return candidate
        n += 1
        candidate = f"{base}-{n}.{ext}"


def _storage_dir():
    os.makedirs(GALLERY_ITEMS_DIR_FOR_REALIZACE, exist_ok=True)
    return GALLERY_ITEMS_DIR_FOR_REALIZACE


def _serialize_image(row):
    return {
        "id": row["id"],
        "category": row["realizace_tag"],
        "category_label": GALLERY_CATEGORY_LABELS.get(row["realizace_tag"], row["realizace_tag"]),
        "filename": os.path.basename(row["file_path"]),
        "url": f"/{row['file_path']}",
        "alt_text": row["alt_text"],
        "title": row["title"],
        "sort_order": row["sort_order"],
        "active": bool(row["is_public"]),
        "source_url": None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


# ---------------------------------------------------------------------------
# Verejne (bez prihlaseni) - jen aktivni obrazky
# ---------------------------------------------------------------------------

@app.get("/api/gallery")
def gallery_public_list():
    category = request.args.get("category")
    if category and category not in GALLERY_CATEGORIES:
        return jsonify({"error": "Neplatná kategorie."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(GALLERY_CATEGORIES))
            sql = f"SELECT * FROM content_photo_library WHERE realizace_tag IN ({placeholders}) AND is_public=1"
            params = list(GALLERY_CATEGORIES)
            if category:
                sql += " AND realizace_tag=%s"
                params.append(category)
            sql += " ORDER BY realizace_tag, sort_order ASC, id ASC"
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({
        "images": [_serialize_image(r) for r in rows],
        "categories": [{"key": k, "label": v} for k, v in GALLERY_CATEGORY_LABELS.items()],
    })


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.get("/api/admin/gallery")
@require_permission("galerie", "zobrazit")
def gallery_admin_list():
    category = request.args.get("category")
    if category and category not in GALLERY_CATEGORIES:
        return jsonify({"error": "Neplatná kategorie."}), 400
    # Robert 2026-08-01: "chceme ukazovat veškeré možné archivní věci
    # položky" - stejny vzor jako shop_suppliers (purchase_orders.py) -
    # vychozi jen active=1, ?archived=1 prohodi na jen neaktivni (counts
    # se pocitaji ze stejne mnoziny, aby sedely s vykreslenym seznamem).
    show_archived = request.args.get("archived") == "1"
    active_val = 0 if show_archived else 1
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(GALLERY_CATEGORIES))
            sql = f"SELECT * FROM content_photo_library WHERE realizace_tag IN ({placeholders}) AND is_public=%s"
            params = list(GALLERY_CATEGORIES) + [active_val]
            if category:
                sql += " AND realizace_tag=%s"
                params.append(category)
            sql += " ORDER BY realizace_tag, sort_order ASC, id ASC"
            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.execute(
                f"SELECT realizace_tag, COUNT(*) AS n FROM content_photo_library "
                f"WHERE realizace_tag IN ({placeholders}) AND is_public=%s GROUP BY realizace_tag",
                list(GALLERY_CATEGORIES) + [active_val],
            )
            counts = {r["realizace_tag"]: r["n"] for r in cur.fetchall()}
    finally:
        conn.close()
    return jsonify({
        "images": [_serialize_image(r) for r in rows],
        "counts": counts,
        "categories": [{"key": k, "label": v} for k, v in GALLERY_CATEGORY_LABELS.items()],
    })


@app.post("/api/admin/gallery/upload")
@require_permission("galerie", "vytvorit")
def gallery_admin_upload():
    """Hromadny upload - vice souboru najednou v jednom requestu (Robert:
    "at se pohodlne nahravaji hromadne obrazky"). Kazdy soubor dostane SEO
    nazev odvozeny z puvodniho jmena pres _seo_slug()."""
    admin = current_user()
    category = request.form.get("category") or GALLERY_CATEGORIES[0]
    if category not in GALLERY_CATEGORIES:
        return jsonify({"error": "Neplatná kategorie."}), 400
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Chybí soubory."}), 400

    created = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(sort_order),0) AS m FROM content_photo_library WHERE realizace_tag=%s",
                (category,),
            )
            next_sort = cur.fetchone()["m"] + 1
            for f in files:
                if not f or not f.filename:
                    continue
                base, ext = _seo_slug(f.filename)
                filename = _unique_filename(cur, base, ext)
                f.save(os.path.join(_storage_dir(), filename))
                title = base.replace("-", " ").capitalize()
                file_path = f"content-files/gallery-items/{filename}"
                cur.execute(
                    "INSERT INTO content_photo_library "
                    "(file_path, alt_text, title, sort_order, is_public, realizace_tag, legacy_source, created_by) "
                    "VALUES (%s,%s,%s,%s,1,%s,'upload',%s)",
                    (file_path, title, title, next_sort, category, admin["id"]),
                )
                created.append(cur.lastrowid)
                next_sort += 1
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "upload", "gallery_image", None, f"{len(created)} souborů do {category}")
    return jsonify({"status": "ok", "created_ids": created, "count": len(created)})


@app.put("/api/admin/gallery/<int:image_id>")
@require_permission("galerie", "upravit")
def gallery_admin_update(image_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "alt_text" in body:
        fields.append("alt_text=%s"); params.append(body.get("alt_text"))
    if "title" in body:
        fields.append("title=%s"); params.append(body.get("title"))
    if "category" in body:
        if body["category"] not in GALLERY_CATEGORIES:
            return jsonify({"error": "Neplatná kategorie."}), 400
        fields.append("realizace_tag=%s"); params.append(body["category"])
    if "sort_order" in body:
        fields.append("sort_order=%s"); params.append(body.get("sort_order"))
    if "active" in body:
        fields.append("is_public=%s"); params.append(1 if body.get("active") else 0)
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(image_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Jen radky, ktere uz PATRI do realizace bucketu - endpoint
            # nesmi editovat knihovni fotku, ktera sem nikdy nepatrila
            # (napr. cistou fotku kategorie), i kdyby nekdo uhodl jeji id.
            cur.execute("SELECT id FROM content_photo_library WHERE id=%s AND realizace_tag IS NOT NULL", (image_id,))
            if not cur.fetchone():
                return jsonify({"error": "Obrázek neexistuje."}), 404
            cur.execute(f"UPDATE content_photo_library SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "gallery_image", image_id, None)
    return jsonify({"status": "ok"})


@app.delete("/api/admin/gallery/<int:image_id>")
@require_permission("galerie", "smazat")
def gallery_admin_delete(image_id):
    # NEMAZE radek/soubor (viz docstring modulu - M:N sdileni s kategoriemi) -
    # jen zrusi realizace_tag, cimz fotka zmizi z /realizace.html.
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT realizace_tag FROM content_photo_library WHERE id=%s AND realizace_tag IS NOT NULL", (image_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Obrázek neexistuje."}), 404
            cur.execute("UPDATE content_photo_library SET realizace_tag=NULL WHERE id=%s", (image_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "gallery_image", image_id, "odebráno z realizace bucketu (soubor zachován)")
    return jsonify({"status": "ok"})


def save_gallery_bytes(cur, category, data, name_hint, source_url=None):
    """Jadro ulozeni obrazku (spolecne pro import z URL i pripadne budouci
    cesty) - ocekava uz STAZENA data. Vraci (id, filename). Vyclenene z
    import_image_from_url() aby import_logiman_gallery.py mohl pred
    ulozenim udelat vlastni dedup podle obsahu (hash bajtu), bez nutnosti
    stahovat/ukladat soubor dvakrat."""
    base, ext = _seo_slug(name_hint)
    filename = _unique_filename(cur, base, ext)
    path = os.path.join(_storage_dir(), filename)
    with open(path, "wb") as fh:
        fh.write(data)
    title = base.replace("-", " ").capitalize()
    cur.execute("SELECT COALESCE(MAX(sort_order),0) AS m FROM content_photo_library WHERE realizace_tag=%s", (category,))
    next_sort = cur.fetchone()["m"] + 1
    file_path = f"content-files/gallery-items/{filename}"
    cur.execute(
        "INSERT INTO content_photo_library "
        "(file_path, alt_text, title, sort_order, is_public, realizace_tag, legacy_source) "
        "VALUES (%s,%s,%s,%s,1,%s,'upload')",
        (file_path, title, title, next_sort, category),
    )
    return cur.lastrowid, filename


def fetch_url_bytes(source_url):
    """Stahne obsah URL pres sdileny `net_fetch.fetch_public_url` (bot6,
    2026-09-02): allowlist http/https, kontrola cilove IP po DNS resolve
    (interni adresy odmitnuty) a LIMIT VELIKOSTI - driv tu bylo holé
    `resp.read()`, takze jedna obri odpoved mohla natahnout RAM.
    Percent-encoding zdrojovych URL (Shoptet nazvy s mezerami/diakritikou
    primo v ceste) resi helper. Vyhazuje ValueError s ceskou hlaskou."""
    return fetch_public_url(source_url, timeout=GALLERY_FETCH_TIMEOUT_S,
                            max_bytes=GALLERY_MAX_FETCH_BYTES,
                            user_agent="Mozilla/5.0 (konfigurator-gallery-import)")


def import_image_from_url(cur, category, source_url, title_hint=None):
    """Stahne obrazek z URL, ulozi pod SEO nazvem, zalozi DB radek. Pouziva
    se pro POST /api/admin/gallery/import-url - STEJNA logika nazvu jako
    admin upload (Robert: "systemove"). Vraci (id, filename)."""
    data = fetch_url_bytes(source_url)
    orig_name = source_url.rsplit("/", 1)[-1].split("?")[0]
    return save_gallery_bytes(cur, category, data, title_hint or orig_name, source_url)


@app.post("/api/admin/gallery/import-url")
@require_permission("galerie", "vytvorit")
def gallery_admin_import_url():
    """Import jednoho obrazku z externi URL - pro pripadne budouci
    jednotlive doplneni z adminu (hromadny import z logiman.cz resil
    jednorazovy import_logiman_gallery.py skript primo, viz AGENTS_LOG)."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    category = body.get("category")
    source_url = (body.get("url") or "").strip()
    title_hint = body.get("title")
    if category not in GALLERY_CATEGORIES:
        return jsonify({"error": "Neplatná kategorie."}), 400
    if not source_url:
        return jsonify({"error": "Chybí url."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                new_id, filename = import_image_from_url(cur, category, source_url, title_hint)
            except Exception as e:
                return jsonify({"error": f"Stažení se nezdařilo: {e}"}), 502
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "import", "gallery_image", new_id, source_url)
    return jsonify({"status": "ok", "id": new_id, "filename": filename})



# --- Hromadne akce (V11, bot3, 2026-07-26, viz NAVRH_HROMADNE_AKCE.md).
# Cely soubor mezitim (2026-07-26, "role a opravneni... na sekce pridej
# vsechno relevantni") prepojen z @admin_required na
# @require_permission("galerie", ...) - viz nova sekce v app.py. ---
@app.post("/api/admin/gallery/bulk-delete")
@require_permission("galerie", "smazat")
def gallery_admin_bulk_delete():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            # Jen radky patrici do realizace bucketu (viz gallery_admin_update) -
            # a NEMAZE (soubor/radek muze byt sdileny s kategorii pres M:N),
            # jen zrusi realizace_tag.
            cur.execute(
                f"UPDATE content_photo_library SET realizace_tag=NULL "
                f"WHERE id IN ({placeholders}) AND realizace_tag IS NOT NULL",
                ids,
            )
            deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "bulk_update", "gallery_image", None,
              f"{deleted} obrázků odebráno z realizace bucketu (soubory zachovány)")
    return jsonify({"status": "ok", "deleted": deleted})


@app.post("/api/admin/gallery/bulk-visibility")
@require_permission("galerie", "upravit")
def gallery_admin_bulk_visibility():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    if "active" in body:
        value = body.get("active")
    elif "visible" in body:
        value = body.get("visible")
    else:
        return jsonify({"error": "Chybí active."}), 400
    active_int = 1 if value else 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            updated = bulk_update_fields(cur, "content_photo_library", ids, {"is_public": active_int})
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "bulk_update", "gallery_image", None,
              f"{updated} obrázků -> active={active_int}")
    return jsonify({"status": "ok", "updated": updated})


# ---------------------------------------------------------------------------
# Knihovna fotek - centralni obrazovka (bot16, 2026-09-13, Robert primo)
#
# Na rozdil od /api/admin/gallery vyse (ktery pracuje jen s radky, co maji
# realizace_tag - bucket pro /realizace.html), tahle sekce ukazuje CELOU
# content_photo_library a je jedine misto, odkud jde fotku:
#  (a) prirazovat do libovolneho poctu e-shopovych kategorii (M:N,
#      content_photo_library_categories) - dosud slo jen z editace JEDNE
#      kategorie (renderGalleryModule, sklad-produkty.js), fotku bylo
#      nutne pridavat category-po-category,
#  (b) trvale smazat (radek + soubor z disku) - jinde (renderGalleryModule
#      u owner_type='category', gallery_admin_delete vyse) "smazat" vzdy
#      jen RUSI PRIRAZENI/realizace_tag, soubor v knihovne zustava.
#
# ZAMERNE VYNECHANO: legacy_source='kategorie_popisy' (445 radku) - to
# jsou obrazky vlozene PRIMO do textu popisu kategorie (content_pages.
# body_html), ne samostatne "prilohy" k prirazovani/mazani odsud. Kdyby
# sem sly, hrozilo by omylem smazat/prevesit obrazek, ktery je soucasti
# uz vyrenderovaneho textu - to se resi ve WYSIWYG editoru popisu, ne tady.
def _library_abs_path(file_path):
    return os.path.join(os.path.dirname(UPLOAD_DIR), file_path)


LIBRARY_EXCLUDED_LEGACY_SOURCES = ("kategorie_popisy",)


@app.get("/api/admin/gallery/library")
@require_permission("galerie", "zobrazit")
def gallery_library_list():
    q = (request.args.get("q") or "").strip()
    category_id = request.args.get("category_id", type=int)
    unassigned = request.args.get("unassigned") == "1"
    placeholders = ",".join(["%s"] * len(LIBRARY_EXCLUDED_LEGACY_SOURCES))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = f"SELECT * FROM content_photo_library WHERE legacy_source NOT IN ({placeholders})"
            params = list(LIBRARY_EXCLUDED_LEGACY_SOURCES)
            if q:
                sql += " AND (title LIKE %s OR alt_text LIKE %s OR file_path LIKE %s)"
                like = f"%{q}%"
                params += [like, like, like]
            if category_id:
                sql += " AND EXISTS (SELECT 1 FROM content_photo_library_categories cc WHERE cc.photo_id=content_photo_library.id AND cc.category_id=%s)"
                params.append(category_id)
            if unassigned:
                sql += (" AND realizace_tag IS NULL AND NOT EXISTS "
                        "(SELECT 1 FROM content_photo_library_categories cc2 WHERE cc2.photo_id=content_photo_library.id)")
            # Robert primo, 2026-09-13: "potrebuje fotky nejak usporadat
            # podle nazvu obrazku" - podle SOUBORU (vzdy vyplneny), ne
            # podle title (u vetsiny fotek prazdny, viz gallery_library_
            # list serializace nize - trideni podle title by je jen
            # shluklo v NULL na zacatku a nic neusporadalo).
            sql += " ORDER BY SUBSTRING_INDEX(file_path, '/', -1)"
            cur.execute(sql, params)
            rows = cur.fetchall()

            photo_ids = [r["id"] for r in rows]
            cats_by_photo = {}
            if photo_ids:
                id_placeholders = ",".join(["%s"] * len(photo_ids))
                cur.execute(
                    f"SELECT cc.photo_id, cat.id, cat.name FROM content_photo_library_categories cc "
                    f"JOIN content_categories cat ON cat.id = cc.category_id "
                    f"WHERE cc.photo_id IN ({id_placeholders}) ORDER BY cat.name",
                    photo_ids,
                )
                for r in cur.fetchall():
                    cats_by_photo.setdefault(r["photo_id"], []).append({"id": r["id"], "name": r["name"]})
    finally:
        conn.close()
    photos = []
    for r in rows:
        cats = cats_by_photo.get(r["id"], [])
        photos.append({
            "id": r["id"],
            "filename": os.path.basename(r["file_path"]),
            "url": f"/{r['file_path']}",
            "title": r["title"],
            "alt_text": r["alt_text"],
            "realizace_tag": r["realizace_tag"],
            "is_public": bool(r["is_public"]),
            "legacy_source": r["legacy_source"],
            "categories": cats,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })
    return jsonify({"photos": photos})


@app.put("/api/admin/gallery/library/<int:photo_id>")
@require_permission("galerie", "upravit")
def gallery_library_update(photo_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(LIBRARY_EXCLUDED_LEGACY_SOURCES))
            cur.execute(
                f"SELECT id FROM content_photo_library WHERE id=%s AND legacy_source NOT IN ({placeholders})",
                [photo_id] + list(LIBRARY_EXCLUDED_LEGACY_SOURCES),
            )
            if not cur.fetchone():
                return jsonify({"error": "Fotka neexistuje."}), 404

            fields, params = [], []
            if "title" in body:
                fields.append("title=%s"); params.append(body.get("title"))
            if "alt_text" in body:
                fields.append("alt_text=%s"); params.append(body.get("alt_text"))
            if "is_public" in body:
                fields.append("is_public=%s"); params.append(1 if body.get("is_public") else 0)
            if "realizace_tag" in body:
                tag = body.get("realizace_tag") or None
                if tag is not None and tag not in GALLERY_CATEGORIES:
                    return jsonify({"error": "Neplatná realizace kategorie."}), 400
                fields.append("realizace_tag=%s"); params.append(tag)
            if fields:
                params.append(photo_id)
                cur.execute(f"UPDATE content_photo_library SET {', '.join(fields)} WHERE id=%s", params)

            if "category_ids" in body:
                category_ids = body.get("category_ids") or []
                if not isinstance(category_ids, list):
                    return jsonify({"error": "category_ids musí být pole."}), 400
                try:
                    category_ids = [int(c) for c in category_ids]
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné ID kategorie."}), 400
                if category_ids:
                    id_placeholders = ",".join(["%s"] * len(category_ids))
                    cur.execute(f"SELECT id FROM content_categories WHERE id IN ({id_placeholders})", category_ids)
                    valid_ids = {r["id"] for r in cur.fetchall()}
                    unknown = set(category_ids) - valid_ids
                    if unknown:
                        return jsonify({"error": f"Neznámá kategorie: {sorted(unknown)}"}), 400
                # bot16, 2026-09-13: DELETE-vse-a-znovu-INSERT s
                # sort_order=index-v-poli (puvodni verze) davalo sort_order
                # spatny vyznam - sloupec ma znamenat "poradi TETO fotky
                # MEZI OSTATNIMI fotkami dane kategorie" (tak ho cte
                # gallery_items.py "ORDER BY c.sort_order, p.id"), ne
                # "poradi teto kategorie mezi kategoriemi teto fotky".
                # Zmena se dela jako diff: NEZMENENA prirazeni si drzi svuj
                # stavajici sort_order (needitujeme poradi v ramci ciziho
                # seznamu jen proto, ze se pridava/ubira JINA kategorie),
                # NOVA se pripoji az za konec dane kategorie (stejny vzor
                # jako upload v gallery_items.py), ODEBRANA se jen smazou.
                cur.execute(
                    "SELECT category_id FROM content_photo_library_categories WHERE photo_id=%s",
                    (photo_id,),
                )
                current_ids = {r["category_id"] for r in cur.fetchall()}
                new_ids = set(category_ids)
                to_remove = current_ids - new_ids
                to_add = new_ids - current_ids
                if to_remove:
                    remove_placeholders = ",".join(["%s"] * len(to_remove))
                    cur.execute(
                        f"DELETE FROM content_photo_library_categories WHERE photo_id=%s AND category_id IN ({remove_placeholders})",
                        [photo_id] + list(to_remove),
                    )
                for cid in to_add:
                    cur.execute(
                        "SELECT COALESCE(MAX(sort_order), -1) AS m FROM content_photo_library_categories WHERE category_id=%s",
                        (cid,),
                    )
                    next_sort = cur.fetchone()["m"] + 1
                    cur.execute(
                        "INSERT INTO content_photo_library_categories (photo_id, category_id, sort_order) VALUES (%s,%s,%s)",
                        (photo_id, cid, next_sort),
                    )
            if not fields and "category_ids" not in body:
                return jsonify({"error": "Nic ke změně."}), 400
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "gallery_library_photo", photo_id, None)
    return jsonify({"status": "ok"})


@app.delete("/api/admin/gallery/library/<int:photo_id>")
@require_permission("galerie", "smazat")
def gallery_library_delete(photo_id):
    # Skutecne trvale smazani - na rozdil od gallery_admin_delete vyse
    # (ktery jen rusi realizace_tag) tohle maze radek, VSECHNA prirazeni
    # do kategorii i fyzicky soubor z disku. Nevratne - potvrzeni je na
    # fronte v adminu (viz fotogalerie.js).
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(LIBRARY_EXCLUDED_LEGACY_SOURCES))
            cur.execute(
                f"SELECT file_path FROM content_photo_library WHERE id=%s AND legacy_source NOT IN ({placeholders})",
                [photo_id] + list(LIBRARY_EXCLUDED_LEGACY_SOURCES),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Fotka neexistuje."}), 404
            file_path = row["file_path"]
            cur.execute("DELETE FROM content_photo_library_categories WHERE photo_id=%s", (photo_id,))
            cur.execute("DELETE FROM content_photo_library WHERE id=%s", (photo_id,))
        conn.commit()
    finally:
        conn.close()
    try:
        os.remove(_library_abs_path(file_path))
    except OSError:
        pass
    log_audit(admin["id"], "delete", "gallery_library_photo", photo_id, file_path)
    return jsonify({"status": "ok"})


@app.get("/api/admin/categories/flat")
@require_permission("galerie", "zobrazit")
def categories_flat_admin():
    # Plochy seznam VSECH kategorii (i neviditelnych, na rozdil od
    # verejneho /api/categories) pro admin pickery - prvni pouziti tady
    # (Knihovna fotek, vyber kam fotku priradit).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, parent_id FROM content_categories ORDER BY name")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"categories": rows})
