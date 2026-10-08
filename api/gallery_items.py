"""
Fotogalerie modul - polymorfni (kategorie NEBO produkty), pripojitelny
kdykoliv v adminu (Robert 2026-07-26: "vytvor modul fotogalerie tak aby
se to dalo pridavat kdykoliv pozdeji ... do kategorii ... nebo k
samotnym produktum katalogu").

Odlisne od dvou existujicich, uzce zamerenych systemu:
- shop_gallery_images (gallery.py) - VEREJNA fotogalerie realizaci/
  vestaveb, jen 2 pevne kategorie (vestavby_dodavek/realizace_stolu).
- shop_product_images - jen Shoptet-importovane fotky produktu, cisty
  import, zadne admin UI pro spravu (viz app.py stock card - jen cteni).

Tenhle modul je obecny "pripojitelny" k libovolnemu vlastnikovi
(owner_type: 'category'|'product'|'document'|'stock_movement'|'po_item')
pres jednu tabulku content_gallery_items (owner_type, owner_id, filename,
source_url, caption, sort_order) - BEZ FK (jeden sloupec owner_id nemuze
mit FK na vic ruznych tabulek), uklid osamocenych radku pri mazani
vlastnika resi delete_items_for_owner() nize, volana z app.py
(categories_delete/shop_products_delete/shop_products_bulk_delete) a
z api/documents.py, api/purchase_orders.py (viz jejich delete funkce).

Robert 2026-07-31 ("cely tento system foceni a ukladani potrebujeme
implementovat do projektu 3D konfigurator", prenos z projektu Photosss):
rozsireno o primy zaznam z fotoaparatu (media_type 'image'/'video' na
existujicim sloupci filename, zadny novy sloupec pro video), volitelnou
zvukovou poznamku (audio_filename - vzdy jen doplnek k foto/videu,
nikdy samostatny zaznam) a volitelnou GPS polohu (latitude/longitude -
zadna nova "lokacni" tabulka, viz gallery_items_nearby() nize pro
dopocet blizkych zaznamu za behu). Novy endpoint POST /api/gallery-
items/capture (ne rozsireni stavajiciho POST /api/gallery-items -
_seo_slug() nize tise prepisuje neznamou priponu na .jpg, coby pro
.webm/.mp4 poskodilo soubory).

Aktivace: `import gallery_items` na konec app.py (jako ostatni moduly).
"""
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from flask import request, jsonify

from app import app, get_conn, current_user, has_permission, log_audit, UPLOAD_DIR

GALLERY_ITEMS_DIR = os.path.join(UPLOAD_DIR, "gallery-items")
os.makedirs(GALLERY_ITEMS_DIR, exist_ok=True)


def _storage_dir_for(owner_type):
    # Remeslo-specificke privatni uloziste (PRIVATE_GALLERY_DIR) i cely
    # auth-gated /file route odstraneny (bot3, 2026-09-07, plna separace
    # Remesla do /opt/remeslo - viz AGENTS_LOG.md). Vsechny zbyle
    # owner_type byly a jsou VZDY verejne pres tenhle jeden adresar/nginx
    # alias - funkce zustava jen kvuli poctu volajicich mist, ktera na ni
    # nize spolehaji.
    return GALLERY_ITEMS_DIR


OWNER_TYPES = ("category", "product", "document", "stock_movement", "po_item", "order", "inbox", "lead", "homepage_block")
OWNER_TABLE = {
    "category": "content_categories", "product": "shop_products",
    "document": "shop_documents", "stock_movement": "shop_stock_movements",
    "po_item": "shop_purchase_order_items", "order": "shop_orders",
    "inbox": "app_users", "lead": "crm_leads",
    # Robert 2026-08-09 ("na dlazdici mozaiky homepage chceme umet vlozit
    # obrazek, video, apd") - vlozeny obrazek v Quill editoru tela textu
    # dlazdice (viz webapp/admin.html hpbQuillImageHandler) nahrava pres
    # tenhle stejny obecny mechanismus, jen novy owner_type.
    "homepage_block": "homepage_blocks",
}
OWNER_PERMISSION_SECTION = {
    # bot16, 2026-09-29: kategorie_obsah/produkty_sklad rozdeleny na
    # granularni sekce po zalozkach (viz AGENTS_LOG.md) - tady navazano
    # na tu, kam se dany owner_type skutecne edituje (skladova karta pro
    # "product"/"stock_movement", Homepage mozaika pro "homepage_block").
    "category": "kategorie", "product": "sklad_karty",
    "document": "doklady", "stock_movement": "sklad_pohyby", "po_item": "nakupni_objednavky",
    "order": "objednavky", "lead": "crm", "homepage_block": "homepage_mozaika",
}
# Mobilni fotoapka (Robert 2026-07-31): osobni sberny kos (owner_type
# 'inbox', owner_id = app_users.id). Kos NEni v role_permissions - pravo
# je "svuj vlastni kos" pro tyhle role (admin navic vidi/spravuje vsechny).
INBOX_ROLES = ("admin", "manager", "skladnik", "ucetni", "monter", "sklad")
GALLERY_IMAGE_MAX_BYTES = 15 * 1024 * 1024
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_EXT_CAPTURE_IMAGE = {"jpg", "jpeg", "png", "webp"}
ALLOWED_EXT_CAPTURE_VIDEO = {"webm", "mp4"}
ALLOWED_EXT_CAPTURE_AUDIO = {"webm", "ogg", "mp3", "wav"}


def _require_owner_permission(owner_type, action, owner_id=None):
    """Vraci (user, error_response|None). Opravneni se odvozuje od
    owner_type az za behu (kategorie->kategorie_obsah, produkt->
    produkty_sklad) - proto nejde pouzit staticky @require_permission
    decorator jako u ostatnich endpointu."""
    user = current_user()
    if not user or not user["active"]:
        return None, (jsonify({"error": "Nepřihlášeno.", "code": "unauthorized"}), 401)
    if owner_type == "inbox":
        # Osobni kos - pravo "muj vlastni kos" (admin spravuje vsechny);
        # kontrola owner_id==ja se dela u volajiciho pres _require_inbox_access.
        if user["role"] not in INBOX_ROLES:
            return None, (jsonify({"error": "Nemáte oprávnění k této akci.", "code": "forbidden"}), 403)
        return user, None
    section = OWNER_PERMISSION_SECTION.get(owner_type)
    if not section or not has_permission(user, section, action):
        return None, (jsonify({"error": "Nemáte oprávnění k této akci.", "code": "forbidden"}), 403)
    return user, None


def _require_inbox_access(user, owner_id):
    """Inbox smi cist/menit jen jeho vlastnik, admin kterykoli."""
    if user["role"] != "admin" and user["id"] != owner_id:
        return (jsonify({"error": "Cizí koš není přístupný.", "code": "forbidden"}), 403)
    return None


# SSRF helpery zijou v `net_fetch.py` (bot6, 2026-09-02) - sdileny se
# scrapery cen, ktere mely stejnou diru. Aliasy pod puvodnimi jmeny, aby
# volajici kod nize zustal beze zmeny; tenhle modul zamerne pouziva
# PRISNEJSI rezim "zadne presmerovani vubec" (import obrazku ma byt primy
# odkaz), zatimco fetch_public_url() par skoku povoluje.
from net_fetch import (  # noqa: E402
    NoRedirectHandler as _NoRedirectHandler,
    ensure_public_host as _ensure_public_host,
)


def _seo_slug(original_name):
    base, _, ext = original_name.rpartition(".")
    if not base:
        base, ext = original_name, ""
    ext = ext.lower()
    if ext not in ALLOWED_EXT:
        ext = "jpg"
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    base = base.lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-") or "obrazek"
    return base, ext


# Foto-dokumentace zakazky pred/po (bot14, 2026-08-19, TASKS.md) - faze,
# ve ktere fotka vznikla. Drzi se ve sloupci content_gallery_items.
# job_phase (viz sql/2026-08-19_gallery_items_job_phase.sql), ZADNA nova
# tabulka ani novy owner_type - zadani vyslovne rika nestavet od nuly.
JOB_PHASES = ("pred", "prubeh", "po")
# Faze ma smysl JEN u zakazky. U kategorie/produktu/dokladu by slo o
# nesmyslny udaj, takze se tam neprijme (misto tiche ignorace - jinak by
# volajici nepoznal, ze se jeho hodnota zahodila).
JOB_PHASE_OWNER_TYPES = ("remeslo_job",)


def _parse_job_phase(raw, owner_type):
    """(hodnota, chyba) pro ulozeni do job_phase. Prazdna hodnota =
    zamerne zruseni zarazeni (NULL), ne chyba - fotka bez faze je
    legitimni stav (viz komentar v migraci)."""
    value = (raw or "").strip()
    if not value:
        return None, None
    if owner_type not in JOB_PHASE_OWNER_TYPES:
        return None, f"Fáze se dá nastavit jen u fotek zakázky, ne u '{owner_type}'."
    if value not in JOB_PHASES:
        return None, f"Neplatná fáze '{value}' (očekáváno: {', '.join(JOB_PHASES)})."
    return value, None


def _parse_is_public(raw):
    """Vychozi hodnota je vzdy False (bezpecne chybeni, ne opt-out) -
    verejne je jen to, co remeslnik VYSLOVNE zaskrtne. Prijima form-
    data string i JSON bool, at funguje z multipart uploadu i z
    PUT tela."""
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in ("1", "true", "on", "yes")


def _validate_owner(cur, owner_type, owner_id):
    if owner_type not in OWNER_TYPES:
        return "Neplatný typ vlastníka."
    cur.execute(f"SELECT id FROM {OWNER_TABLE[owner_type]} WHERE id=%s", (owner_id,))
    if not cur.fetchone():
        return "Vlastník (kategorie/produkt) neexistuje."
    return None


def _serialize_item(row, public=False):
    # public=True (bot3/revize kodu, 2026-09-02, pripraveno pro pripadne
    # budouci verejne pouziti) - bez GPS/created_by/created_role/
    # job_phase, ktere `is_public=1` na fotce NEMA zverejnit (jen fotka
    # sama, ne kdo/kdy/kde ji poridil).
    if public:
        return {
            "id": row["id"],
            "filename": row["filename"],
            "caption": row["caption"],
            "sort_order": row["sort_order"],
        }
    audio_filename = row.get("audio_filename")
    lat = row.get("latitude")
    lon = row.get("longitude")
    owner_type = row["owner_type"]
    url = f"/content-files/gallery-items/{row['filename']}"
    audio_url = f"/content-files/gallery-items/{audio_filename}" if audio_filename else None
    return {
        "id": row["id"],
        "owner_type": owner_type,
        "owner_id": row["owner_id"],
        "filename": row["filename"],
        "url": url,
        "media_type": row.get("media_type") or "image",
        "audio_url": audio_url,
        "source_url": row["source_url"],
        "caption": row["caption"],
        "job_phase": row.get("job_phase"),
        "is_public": bool(row.get("is_public")),
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lon) if lon is not None else None,
        "sort_order": row["sort_order"],
        "created_by": row.get("created_by"),
        "created_role": row.get("created_role"),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _serialize_library_item(row, category_id):
    """content_photo_library radek do STEJNEHO JSON tvaru jako
    _serialize_item() (bot10, 2026-09-12, centralni fotogalerie) - frontend
    (renderGalleryModule) je uz obecny a cte jen id/url/media_type/
    audio_url/caption, takze nepotrebuje zadnou zmenu. `url` se sklada
    primo z `file_path` (uz obsahuje "content-files/..." predponu, na
    rozdil od content_gallery_items.filename, ktere ma jen holy nazev
    souboru) - viz sql/2026-09-12_content_photo_library.sql."""
    return {
        "id": row["id"],
        "owner_type": "category",
        "owner_id": category_id,
        "filename": os.path.basename(row["file_path"]),
        "url": f"/{row['file_path']}",
        "media_type": "image",
        "audio_url": None,
        "source_url": None,
        "caption": row.get("caption"),
        "job_phase": None,
        "is_public": bool(row.get("is_public")),
        "latitude": None,
        "longitude": None,
        "sort_order": row["sort_order"],
        "created_by": row.get("created_by"),
        "created_role": None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def delete_items_for_owner(owner_type, owner_id):
    """Uklid osamocenych fotek, kdyz se smaze vlastnik (kategorie/
    produkt). Vlastni pripojeni/transakce, volano AZ PO commitu hlavniho
    DELETE v app.py - selhani uklidu fotek nema nikdy zablokovat/
    rozbit samotne mazani vlastnika. POZOR: mazani kategorie s
    podkategoriemi kaskaduje na urovni DB (fk_cat_parent ON DELETE
    CASCADE) - fotky podkategorii (jina radky teto tabulky) timto
    zavolanim NEJSOU osetreny, zustanou osamocene (znamy, vedomy
    kompromis kvuli rozsahu - vzacny pripad, nerozbiji funkcnost)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT filename, audio_filename FROM content_gallery_items WHERE owner_type=%s AND owner_id=%s",
                (owner_type, owner_id),
            )
            rows = cur.fetchall()
            cur.execute(
                "DELETE FROM content_gallery_items WHERE owner_type=%s AND owner_id=%s",
                (owner_type, owner_id),
            )
        conn.commit()
    finally:
        conn.close()
    filenames = [r["filename"] for r in rows] + [r["audio_filename"] for r in rows if r["audio_filename"]]
    storage_dir = _storage_dir_for(owner_type)
    for fn in filenames:
        try:
            os.remove(os.path.join(storage_dir, fn))
        except OSError:
            pass


def delete_items_for_owners_bulk(owner_type, owner_ids):
    """Hromadna varianta delete_items_for_owner - JEDNO spojeni a jeden
    SELECT+DELETE pro vsechny vlastniky najednou (bot6, 2026-08-02:
    radkove volani pri bulk mazani stovek produktu otviralo stovky
    spojeni na vzdalenou DB a shazovalo request na gunicorn timeout)."""
    if not owner_ids:
        return
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(owner_ids))
            cur.execute(
                f"SELECT filename, audio_filename FROM content_gallery_items "
                f"WHERE owner_type=%s AND owner_id IN ({placeholders})",
                (owner_type, *owner_ids),
            )
            rows = cur.fetchall()
            cur.execute(
                f"DELETE FROM content_gallery_items WHERE owner_type=%s AND owner_id IN ({placeholders})",
                (owner_type, *owner_ids),
            )
        conn.commit()
    finally:
        conn.close()
    filenames = [r["filename"] for r in rows] + [r["audio_filename"] for r in rows if r["audio_filename"]]
    storage_dir = _storage_dir_for(owner_type)
    for fn in filenames:
        try:
            os.remove(os.path.join(storage_dir, fn))
        except OSError:
            pass


@app.get("/api/gallery-items")
def gallery_items_list():
    # VEREJNE cteni JEN pro category/product (stejny duvod jako
    # /api/categories - kategorie i obsah produktu se zobrazuje i bez
    # prihlaseni na e-shopu). Zapis (upload/import/reorder/delete nize)
    # je gated podle owner_type.
    #
    # bot10, 2026-09-12 (bot3 nalez u is_public na api/categories.py -
    # tohle je DALSI cast stejne diry): tenhle endpoint donedavna
    # (1) vubec nefiltroval is_public (nezverejnene fotky kategorie/
    # produktu by tak sly precist primo pres tenhle endpoint, i po
    # oprave v api/categories.py/api/products.py) a (2) nemel ZADNOU
    # kontrolu prav pro VSECHNY OSTATNI owner_type (document/
    # stock_movement/po_item/order/lead/homepage_block - interni
    # doklady/objednavky/CRM leady, ne verejny obsah) - kdokoli bez
    # prihlaseni mohl zavolat napr. ?owner_type=document&owner_id=X.
    # K 2026-09-12 v techhle typech zadna data nejsou (overeno pred
    # zapisem), takze bez unikleho obsahu, ale dira samotna byla realna.
    # Zadna verejna stranka tenhle endpoint pro homepage_block/document/...
    # nevola (jen scene.html/capture.html, oba staff-only), takze
    # zpritneni na category/product + permission gate pro zbytek
    # nic nerozbiji.
    owner_type = request.args.get("owner_type")
    owner_id = request.args.get("owner_id", type=int)
    if owner_type not in OWNER_TYPES or not owner_id:
        return jsonify({"error": "Chybí owner_type/owner_id."}), 400
    is_public_filter = False
    if owner_type == "inbox":
        # Osobni kos NENI verejny (na rozdil od galerii kategorii/produktu).
        user, err = _require_owner_permission("inbox", "zobrazit")
        if err:
            return err
        acc_err = _require_inbox_access(user, owner_id)
        if acc_err:
            return acc_err
    elif owner_type in OWNER_PERMISSION_SECTION:
        # document/stock_movement/po_item/order/lead/homepage_block -
        # interni obsah, ne verejna galerie kategorie/produktu.
        user, err = _require_owner_permission(owner_type, "zobrazit")
        if err:
            return err
    else:
        # category/product - jedine dva skutecne verejne typy. bot10,
        # 2026-09-12: prihlaseny stafista s pravem "zobrazit" nad danym
        # owner_type vidi VSECHNO (i is_public=0) - jinak by admin galerie
        # v editoru kategorie/produktu nedokazala ukazat vlastni jeste-
        # nezverejnene fotky, ktere prave nahrala. Anonymni/verejny
        # pristup (zadny prihlaseny uzivatel, nebo bez prava) zustava
        # filtrovany na is_public=1 - stejny bezpecnostni pozadavek jako
        # dnesni oprava.
        u = current_user()
        section = "kategorie" if owner_type == "category" else "sklad_karty"
        if not (u and has_permission(u, section, "zobrazit")):
            is_public_filter = True

    if owner_type == "category":
        # bot10, 2026-09-12: centralni fotogalerie - kategorie ted cte z
        # content_photo_library (M:N pres content_photo_library_categories),
        # ne z content_gallery_items (viz sql/2026-09-12_content_photo_
        # library.sql pro duvod migrace).
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                sql = (
                    "SELECT p.* FROM content_photo_library p "
                    "JOIN content_photo_library_categories c ON c.photo_id = p.id "
                    "WHERE c.category_id=%s"
                )
                if is_public_filter:
                    sql += " AND p.is_public=1"
                sql += " ORDER BY c.sort_order, p.id"
                cur.execute(sql, (owner_id,))
                rows = cur.fetchall()
        finally:
            conn.close()
        return jsonify({"items": [_serialize_library_item(r, owner_id) for r in rows]})

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM content_gallery_items WHERE owner_type=%s AND owner_id=%s"
            if is_public_filter:
                sql += " AND is_public=1"
            sql += " ORDER BY sort_order, id"
            cur.execute(sql, (owner_type, owner_id))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"items": [_serialize_item(r) for r in rows]})


@app.post("/api/gallery-items")
def gallery_items_upload():
    owner_type = request.form.get("owner_type")
    try:
        owner_id = int(request.form.get("owner_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí owner_id."}), 400
    user, err = _require_owner_permission(owner_type, "upravit", owner_id)
    if err:
        return err
    files = request.files.getlist("files")
    if not files:
        single = request.files.get("file")
        files = [single] if single else []
    files = [f for f in files if f and f.filename]
    if not files:
        return jsonify({"error": "Chybí soubor."}), 400
    job_phase, phase_err = _parse_job_phase(request.form.get("job_phase"), owner_type)
    if phase_err:
        return jsonify({"error": phase_err}), 400
    is_public = _parse_is_public(request.form.get("is_public"))
    storage_dir = _storage_dir_for(owner_type)
    conn = get_conn()
    created = []
    try:
        with conn.cursor() as cur:
            owner_err = _validate_owner(cur, owner_type, owner_id)
            if owner_err:
                return jsonify({"error": owner_err}), 400

            if owner_type == "category":
                # bot10, 2026-09-12: centralni fotogalerie - novy upload
                # kategorie jde do content_photo_library (+ M:N prirazeni),
                # NIKDY do content_gallery_items (ta pro kategorie od tohodle
                # bodu uz jen dobiha stare radky, novy zapis tam nechodi).
                cur.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) AS m FROM content_photo_library_categories WHERE category_id=%s",
                    (owner_id,),
                )
                next_sort = cur.fetchone()["m"] + 1
                for f in files:
                    f.stream.seek(0, os.SEEK_END)
                    size = f.stream.tell()
                    f.stream.seek(0)
                    if size > GALLERY_IMAGE_MAX_BYTES:
                        return jsonify({"error": f"Soubor {f.filename} je příliš velký."}), 413
                    base, ext = _seo_slug(f.filename)
                    stored_name = f"{owner_type}-{owner_id}_{base}-{os.urandom(4).hex()}.{ext}"
                    f.save(os.path.join(storage_dir, stored_name))
                    file_path = f"content-files/gallery-items/{stored_name}"
                    cur.execute(
                        "INSERT INTO content_photo_library (file_path, is_public, legacy_source, sort_order, created_by) "
                        "VALUES (%s,%s,'upload',%s,%s)",
                        (file_path, is_public, next_sort, user["id"]),
                    )
                    photo_id = cur.lastrowid
                    cur.execute(
                        "INSERT INTO content_photo_library_categories (photo_id, category_id, sort_order) VALUES (%s,%s,%s)",
                        (photo_id, owner_id, next_sort),
                    )
                    created.append(_serialize_library_item({
                        "id": photo_id, "file_path": file_path, "caption": None,
                        "is_public": is_public, "sort_order": next_sort,
                        "created_by": user["id"], "created_at": None,
                    }, owner_id))
                    next_sort += 1
                conn.commit()
                log_audit(user["id"], "create", "gallery_item", None, f"{owner_type}#{owner_id}: {len(created)} fotek")
                return jsonify({"status": "ok", "items": created})

            cur.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM content_gallery_items WHERE owner_type=%s AND owner_id=%s",
                (owner_type, owner_id),
            )
            next_sort = cur.fetchone()["m"] + 1
            for f in files:
                # QA nalez (2026-09-05): chybel limit velikosti per soubor
                # (nginx client_max_body_size 50M je jen hruby sdileny strop
                # pro cely vhost/request, ne per-soubor u vicenasobneho uploadu).
                f.stream.seek(0, os.SEEK_END)
                size = f.stream.tell()
                f.stream.seek(0)
                if size > GALLERY_IMAGE_MAX_BYTES:
                    return jsonify({"error": f"Soubor {f.filename} je příliš velký."}), 413
                base, ext = _seo_slug(f.filename)
                stored_name = f"{owner_type}-{owner_id}_{base}-{os.urandom(4).hex()}.{ext}"
                f.save(os.path.join(storage_dir, stored_name))
                cur.execute(
                    "INSERT INTO content_gallery_items (owner_type, owner_id, filename, sort_order, job_phase, is_public) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (owner_type, owner_id, stored_name, next_sort, job_phase, is_public),
                )
                created.append(_serialize_item({
                    "id": cur.lastrowid, "owner_type": owner_type, "owner_id": owner_id,
                    "filename": stored_name, "source_url": None, "caption": None,
                    "sort_order": next_sort, "created_at": None, "job_phase": job_phase,
                    "is_public": is_public,
                }))
                next_sort += 1
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "gallery_item", None, f"{owner_type}#{owner_id}: {len(created)} fotek")
    return jsonify({"status": "ok", "items": created})


@app.post("/api/gallery-items/import-url")
def gallery_items_import_url():
    body = request.get_json(silent=True) or {}
    owner_type = body.get("owner_type")
    try:
        owner_id = int(body.get("owner_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí owner_id."}), 400
    user, err = _require_owner_permission(owner_type, "upravit", owner_id)
    if err:
        return err
    source_url = (body.get("url") or "").strip()
    if not source_url:
        return jsonify({"error": "Chybí url."}), 400
    # Bezpecnost (bot11, 2026-08-18, audit AUDIT_SYSTEM_2026-08-18.md
    # nalez 1.4 - SSRF): `urllib.request` ma ve vychozim stavu
    # zaregistrovany `FileHandler` - bez kontroly schematu by
    # `url: "file:///opt/konfigurator/api/.env"` STAHLO lokalni soubor
    # ze serveru a ulozilo ho jako VEREJNE stazitelny gallery item.
    # Allowlist jen http/https.
    parsed = urllib.parse.urlparse(source_url)
    if parsed.scheme not in ("http", "https"):
        return jsonify({"error": "Nepovolené schéma URL (jen http/https)."}), 400
    # Rozsireni (bot3/revize kodu, 2026-09-02): scheme allowlist sam
    # nebrani http/https na INTERNI adresu (127.0.0.1, cloud metadata
    # 169.254.169.254 apod.) - viz _ensure_public_host/_NoRedirectHandler
    # docstringy vyse. Presmerovani se NENASLEDUJE (mohlo by vest na
    # interni adresu bez teto same kontroly).
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    host_err = _ensure_public_host(parsed.hostname, port)
    if host_err:
        return jsonify({"error": host_err}), 400
    safe_url = urllib.parse.quote(source_url, safe=":/?&=%")
    try:
        req = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0 (konfigurator-gallery-items)"})
        opener = urllib.request.build_opener(_NoRedirectHandler)
        with opener.open(req, timeout=15) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return jsonify({"error": "URL přesměrovává, zadejte přímý odkaz na obrázek."}), 400
        return jsonify({"error": f"Stažení se nezdařilo: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Stažení se nezdařilo: {e}"}), 502
    orig_name = source_url.rsplit("/", 1)[-1].split("?")[0]
    base, ext = _seo_slug(orig_name)
    stored_name = f"{owner_type}-{owner_id}_{base}-{os.urandom(4).hex()}.{ext}"
    is_public = _parse_is_public(body.get("is_public"))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            owner_err = _validate_owner(cur, owner_type, owner_id)
            if owner_err:
                return jsonify({"error": owner_err}), 400

            if owner_type == "category":
                # bot10, 2026-09-12: viz gallery_items_upload() vyse - novy
                # obsah kategorie jde vzdy do centralni knihovny.
                cur.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) AS m FROM content_photo_library_categories WHERE category_id=%s",
                    (owner_id,),
                )
                next_sort = cur.fetchone()["m"] + 1
                with open(os.path.join(_storage_dir_for(owner_type), stored_name), "wb") as fh:
                    fh.write(data)
                file_path = f"content-files/gallery-items/{stored_name}"
                cur.execute(
                    "INSERT INTO content_photo_library (file_path, is_public, legacy_source, sort_order, created_by) "
                    "VALUES (%s,%s,'upload',%s,%s)",
                    (file_path, is_public, next_sort, user["id"]),
                )
                new_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO content_photo_library_categories (photo_id, category_id, sort_order) VALUES (%s,%s,%s)",
                    (new_id, owner_id, next_sort),
                )
                conn.commit()
                log_audit(user["id"], "import", "gallery_item", new_id, source_url)
                return jsonify({"status": "ok", "id": new_id, "filename": stored_name})

            cur.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM content_gallery_items WHERE owner_type=%s AND owner_id=%s",
                (owner_type, owner_id),
            )
            next_sort = cur.fetchone()["m"] + 1
            with open(os.path.join(_storage_dir_for(owner_type), stored_name), "wb") as fh:
                fh.write(data)
            cur.execute(
                "INSERT INTO content_gallery_items (owner_type, owner_id, filename, source_url, sort_order, is_public) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (owner_type, owner_id, stored_name, source_url, next_sort, is_public),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "import", "gallery_item", new_id, source_url)
    return jsonify({"status": "ok", "id": new_id, "filename": stored_name})


@app.put("/api/gallery-items/<int:item_id>")
def gallery_items_update(item_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT owner_type, owner_id FROM content_gallery_items WHERE id=%s", (item_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Fotka neexistuje."}), 404
            user, err = _require_owner_permission(row["owner_type"], "upravit", row["owner_id"])
            if err:
                return err
            body = request.get_json(silent=True) or {}
            fields, params = [], []
            if "caption" in body:
                fields.append("caption=%s"); params.append((body.get("caption") or "").strip() or None)
            if "sort_order" in body:
                fields.append("sort_order=%s"); params.append(int(body.get("sort_order") or 0))
            if "job_phase" in body:
                # prerazeni fotky mezi fazemi (i zpet na "nezarazeno")
                phase, phase_err = _parse_job_phase(body.get("job_phase"), row["owner_type"])
                if phase_err:
                    return jsonify({"error": phase_err}), 400
                fields.append("job_phase=%s"); params.append(phase)
            if "is_public" in body:
                # Sloupec bez funkcniho dopadu od odstraneni Remesla
                # (bot3, 2026-09-07) - nastaveni nezakazujeme (neskodi,
                # jen se nikde necte).
                fields.append("is_public=%s"); params.append(_parse_is_public(body.get("is_public")))
            if not fields:
                return jsonify({"error": "Nic ke změně."}), 400
            params.append(item_id)
            cur.execute(f"UPDATE content_gallery_items SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/gallery-items/reorder")
def gallery_items_reorder():
    body = request.get_json(silent=True) or {}
    owner_type = body.get("owner_type")
    try:
        owner_id = int(body.get("owner_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí owner_id."}), 400
    user, err = _require_owner_permission(owner_type, "upravit", owner_id)
    if err:
        return err
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "Chybí ids."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if owner_type == "category":
                # bot10, 2026-09-12: poradi kategorie je ted v M:N tabulce
                # (per-kategorie sort_order, stejna fotka muze mit jine
                # poradi v kazde kategorii, kde je prirazena).
                for i, item_id in enumerate(ids):
                    cur.execute(
                        "UPDATE content_photo_library_categories SET sort_order=%s WHERE photo_id=%s AND category_id=%s",
                        (i, item_id, owner_id),
                    )
            else:
                for i, item_id in enumerate(ids):
                    cur.execute(
                        "UPDATE content_gallery_items SET sort_order=%s WHERE id=%s AND owner_type=%s AND owner_id=%s",
                        (i, item_id, owner_type, owner_id),
                    )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.delete("/api/gallery-items/<int:item_id>")
def gallery_items_delete(item_id):
    # bot10, 2026-09-12: `item_id` uz neni jednoznacny napric tabulkami -
    # kategorie ted zije v content_photo_library s VLASTNI radou id,
    # nezavislou na content_gallery_items (viz sql/2026-09-12_content_
    # photo_library.sql). Bezpecne, dokud content_gallery_items nedostava
    # NOVE kategorie radky (nedostava - upload vyse uz pise jen do
    # knihovny) - zkusi se nejdriv stara tabulka (pokryva vsechny ostatni
    # owner_type beze zmeny), pak centralni knihovna.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT owner_type, owner_id, filename, audio_filename FROM content_gallery_items WHERE id=%s",
                (item_id,),
            )
            row = cur.fetchone()
            if row:
                user, err = _require_owner_permission(row["owner_type"], "smazat", row["owner_id"])
                if err:
                    return err
                if row["owner_type"] == "inbox":
                    acc_err = _require_inbox_access(user, row["owner_id"])
                    if acc_err:
                        return acc_err
                cur.execute("DELETE FROM content_gallery_items WHERE id=%s", (item_id,))
                conn.commit()
                storage_dir = _storage_dir_for(row["owner_type"])
                for fn in [row["filename"], row["audio_filename"]]:
                    if fn:
                        try:
                            os.remove(os.path.join(storage_dir, fn))
                        except OSError:
                            pass
                log_audit(user["id"], "delete", "gallery_item", item_id, f"{row['owner_type']}#{row['owner_id']}")
                return jsonify({"status": "ok"})

            # Nenalezeno ve stare tabulce -> centralni knihovna (kategorie).
            # "Smazat" tady NIKDY nemaze fotku/soubor - jen zrusi PRIRAZENI
            # k TETO jedne kategorii (bot3/Robert, 2026-09-12: "tlačítko v
            # pohledu jedné kategorie nemá právo smazat něco, co vidí i
            # jiná kategorie" - fotka muze byt v libovolnem poctu kategorii
            # zaroven pres M:N). Skutecne trvale smazani z knihovny (i z
            # disku) zije vyhradne v nove centralni obrazovce, ne tady.
            cur.execute("SELECT id FROM content_photo_library WHERE id=%s", (item_id,))
            if not cur.fetchone():
                return jsonify({"error": "Fotka neexistuje."}), 404
            category_id = request.args.get("owner_id", type=int)
            if not category_id:
                return jsonify({"error": "Chybí owner_id (kterou kategorii odebrat)."}), 400
            user, err = _require_owner_permission("category", "upravit", category_id)
            if err:
                return err
            cur.execute(
                "DELETE FROM content_photo_library_categories WHERE photo_id=%s AND category_id=%s",
                (item_id, category_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "gallery_item", item_id, f"category#{category_id}: odebráno z kategorie")
    return jsonify({"status": "ok"})


@app.post("/api/gallery-items/capture")
def gallery_items_capture():
    """Zaznam primo z fotoaparatu v adminu (foto NEBO video) + volitelna
    zvukova poznamka + volitelna GPS poloha. Samostatny endpoint od
    POST /api/gallery-items zamerne - _seo_slug() vyse tise prepisuje
    neznamou priponu na .jpg, coz by pro .webm/.mp4 poskodilo soubor;
    tady se pripona overuje explicitne a pri neshode se vraci 400."""
    owner_type = request.form.get("owner_type")
    try:
        owner_id = int(request.form.get("owner_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí owner_id."}), 400
    user, err = _require_owner_permission(owner_type, "upravit", owner_id)
    if err:
        return err
    if owner_type == "inbox":
        acc_err = _require_inbox_access(user, owner_id)
        if acc_err:
            return acc_err

    media_type = request.form.get("media_type")
    if media_type not in ("image", "video"):
        return jsonify({"error": "media_type musí být 'image' nebo 'video'."}), 400
    media_file = request.files.get("media")
    if not media_file or not media_file.filename:
        return jsonify({"error": "Chybí zachycený soubor (media)."}), 400
    media_ext = media_file.filename.rsplit(".", 1)[-1].lower() if "." in media_file.filename else ""
    allowed = ALLOWED_EXT_CAPTURE_IMAGE if media_type == "image" else ALLOWED_EXT_CAPTURE_VIDEO
    if media_ext not in allowed:
        return jsonify({"error": f"Nepodporovaná přípona pro {media_type}: .{media_ext}"}), 400

    audio_file = request.files.get("audio")
    if audio_file and audio_file.filename:
        audio_ext = audio_file.filename.rsplit(".", 1)[-1].lower() if "." in audio_file.filename else ""
        if audio_ext not in ALLOWED_EXT_CAPTURE_AUDIO:
            return jsonify({"error": f"Nepodporovaná přípona zvuku: .{audio_ext}"}), 400
    else:
        audio_file, audio_ext = None, None

    caption = (request.form.get("caption") or "").strip() or None
    job_phase, phase_err = _parse_job_phase(request.form.get("job_phase"), owner_type)
    if phase_err:
        return jsonify({"error": phase_err}), 400
    lat = request.form.get("latitude")
    lon = request.form.get("longitude")
    try:
        lat = float(lat) if lat not in (None, "") else None
        lon = float(lon) if lon not in (None, "") else None
    except ValueError:
        return jsonify({"error": "latitude/longitude musí být číslo."}), 400
    is_public = _parse_is_public(request.form.get("is_public"))
    storage_dir = _storage_dir_for(owner_type)

    if owner_type == "category" and media_type != "image":
        # bot10, 2026-09-12: centralni knihovna dnes modeluje jen fotky
        # (zadny media_type/audio/GPS sloupec - viz sql/2026-09-12_content_
        # photo_library.sql). Video/audio/poloha jsou realne pro mobilni
        # "muj kos" terenni dokumentaci, ne pro fotogalerii kategorie -
        # nerozsiruji schema kvuli pripadu, ktery Robert nezadal.
        return jsonify({"error": "Galerie kategorie zatím podporuje jen fotky, ne video."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            owner_err = _validate_owner(cur, owner_type, owner_id)
            if owner_err:
                return jsonify({"error": owner_err}), 400

            if owner_type == "category":
                cur.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) AS m FROM content_photo_library_categories WHERE category_id=%s",
                    (owner_id,),
                )
                next_sort = cur.fetchone()["m"] + 1
                base, _ = _seo_slug(media_file.filename)
                token = os.urandom(4).hex()
                stored_name = f"{owner_type}-{owner_id}_{base}-{token}.{media_ext}"
                media_file.save(os.path.join(storage_dir, stored_name))
                file_path = f"content-files/gallery-items/{stored_name}"
                cur.execute(
                    "INSERT INTO content_photo_library (file_path, caption, is_public, legacy_source, sort_order, created_by) "
                    "VALUES (%s,%s,%s,'upload',%s,%s)",
                    (file_path, caption, is_public, next_sort, user["id"]),
                )
                new_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO content_photo_library_categories (photo_id, category_id, sort_order) VALUES (%s,%s,%s)",
                    (new_id, owner_id, next_sort),
                )
                conn.commit()
                log_audit(user["id"], "capture", "gallery_item", new_id, f"{owner_type}#{owner_id}: {media_type}")
                return jsonify({"status": "ok", "item": _serialize_library_item({
                    "id": new_id, "file_path": file_path, "caption": caption,
                    "is_public": is_public, "sort_order": next_sort,
                    "created_by": user["id"], "created_at": None,
                }, owner_id)})

            cur.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM content_gallery_items WHERE owner_type=%s AND owner_id=%s",
                (owner_type, owner_id),
            )
            next_sort = cur.fetchone()["m"] + 1

            base, _ = _seo_slug(media_file.filename)
            token = os.urandom(4).hex()
            stored_name = f"{owner_type}-{owner_id}_{base}-{token}.{media_ext}"
            media_file.save(os.path.join(storage_dir, stored_name))

            audio_stored_name = None
            if audio_file:
                audio_stored_name = f"{owner_type}-{owner_id}_{base}-{token}-audio.{audio_ext}"
                audio_file.save(os.path.join(storage_dir, audio_stored_name))

            cur.execute(
                """INSERT INTO content_gallery_items
                   (owner_type, owner_id, filename, media_type, audio_filename, caption, latitude, longitude,
                    created_by, created_role, sort_order, job_phase, is_public)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (owner_type, owner_id, stored_name, media_type, audio_stored_name, caption, lat, lon,
                 user["id"], user["role"], next_sort, job_phase, is_public),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "capture", "gallery_item", new_id, f"{owner_type}#{owner_id}: {media_type}")
    return jsonify({"status": "ok", "item": _serialize_item({
        "id": new_id, "owner_type": owner_type, "owner_id": owner_id,
        "filename": stored_name, "media_type": media_type, "audio_filename": audio_stored_name,
        "source_url": None, "caption": caption, "latitude": lat, "longitude": lon,
        "created_by": user["id"], "created_role": user["role"],
        "sort_order": next_sort, "created_at": None, "job_phase": job_phase, "is_public": is_public,
    })})


@app.put("/api/gallery-items/<int:item_id>/move")
def gallery_items_move(item_id):
    """Presun fotky z osobniho kose (nebo odkudkoli) na cilovy zaznam
    (objednavka/produkt/doklad/pohyb/PO polozka). Pravo: 'upravit' na
    CILOVE sekci (napr. manazer -> objednavky). U zdroje-inboxu smi
    presouvat jen vlastnik kose nebo admin. Soubor na disku se
    neprejmenovava (nazev je jen nazev), meni se jen DB radek."""
    body = request.get_json(silent=True) or {}
    new_type = body.get("owner_type")
    try:
        new_id = int(body.get("owner_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí owner_id."}), 400
    if new_type not in OWNER_TYPES or new_type == "inbox":
        return jsonify({"error": "Neplatný cílový typ."}), 400
    user, err = _require_owner_permission(new_type, "upravit", new_id)
    if err:
        return err
    # Faze se posila rovnou s presunem - mobilni tok je "vyfot do kose ->
    # priradit k zakazce jako PRED/PO" na jeden krok, ne presun a pak
    # jeste druhy dotaz na fazi.
    job_phase, phase_err = _parse_job_phase(body.get("job_phase"), new_type)
    if phase_err:
        return jsonify({"error": phase_err}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT owner_type, owner_id, filename, audio_filename FROM content_gallery_items WHERE id=%s",
                (item_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Fotka neexistuje."}), 404
            if row["owner_type"] == "inbox":
                acc_err = _require_inbox_access(user, row["owner_id"])
                if acc_err:
                    return acc_err
            else:
                # OPRAVA (bot16, 2026-09-02, revize bot3 - K1, IDOR): dosud se
                # overoval jen CIL presunu - remeslnik s vlastni zakazkou tak
                # mohl "presunout" (= ukrast a pak cist pres /file) libovolnou
                # cizi fotku podle id, vc. soukrome fotodokumentace/uctenek
                # jineho remeslnika nebo fotek objednavek e-shopu. Zdroj musi
                # projit stejnou kontrolou jako jeho smazani (DELETE nize).
                _, src_err = _require_owner_permission(row["owner_type"], "smazat", row["owner_id"])
                if src_err:
                    return src_err
            owner_err = _validate_owner(cur, new_type, new_id)
            if owner_err:
                return jsonify({"error": owner_err}), 400
            cur.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM content_gallery_items WHERE owner_type=%s AND owner_id=%s",
                (new_type, new_id),
            )
            next_sort = cur.fetchone()["m"] + 1
            # job_phase se prepisuje VZDY, i kdyz se neposlala: pri
            # presunu ZE zakazky jinam (napr. na produkt) by jinak zustala
            # viset faze u vlastnika, kde nedava zadny smysl. _parse_job_
            # phase vraci pro necilovou zakazku None, takze se korektne
            # vynuluje.
            cur.execute(
                "UPDATE content_gallery_items SET owner_type=%s, owner_id=%s, sort_order=%s, job_phase=%s WHERE id=%s",
                (new_type, new_id, next_sort, job_phase, item_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "move", "gallery_item", item_id,
              f"{row['owner_type']}#{row['owner_id']} -> {new_type}#{new_id}")
    return jsonify({"status": "ok"})


@app.get("/api/gallery-items/inboxes")
def gallery_items_inboxes():
    """Prehled osobnich kosu (kdo ma kolik fotek) - jen admin.
    Pro zalozku "Foto kos" v adminu."""
    user = current_user()
    if not user or not user["active"]:
        return jsonify({"error": "Nepřihlášeno.", "code": "unauthorized"}), 401
    if user["role"] != "admin":
        return jsonify({"error": "Jen pro admina.", "code": "forbidden"}), 403
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.name, u.email, u.role, COUNT(g.id) AS item_count
                FROM app_users u
                JOIN content_gallery_items g ON g.owner_type='inbox' AND g.owner_id=u.id
                GROUP BY u.id, u.name, u.email, u.role
                ORDER BY item_count DESC
            """)
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"inboxes": rows})


@app.get("/api/gallery-items/nearby")
def gallery_items_nearby():
    """Cistě informativni - 'N blizkych zaznamu' k danemu GPS-tagovanemu
    zaznamu, napric vsemi owner_type. Nic neblokuje/negatuje, jen chip
    v UI. Haversine pres cely sloupec latitude/longitude - pri realnem
    poctu radku v tomto adminu (nizke stovky/tisice) bez potreby
    prostoroveho indexu."""
    try:
        item_id = int(request.args.get("item_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí item_id."}), 400
    try:
        radius_m = float(request.args.get("radius_m") or 150)
    except ValueError:
        radius_m = 150

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT latitude, longitude FROM content_gallery_items WHERE id=%s", (item_id,))
            src = cur.fetchone()
            if not src or src["latitude"] is None or src["longitude"] is None:
                return jsonify({"items": []})
            cur.execute(
                """
                SELECT *,
                       (6371000 * ACOS(LEAST(1, GREATEST(-1,
                          COS(RADIANS(%s)) * COS(RADIANS(latitude)) * COS(RADIANS(longitude) - RADIANS(%s))
                          + SIN(RADIANS(%s)) * SIN(RADIANS(latitude))
                       )))) AS distance_m
                FROM content_gallery_items
                WHERE id != %s AND latitude IS NOT NULL AND longitude IS NOT NULL
                HAVING distance_m <= %s
                ORDER BY distance_m
                LIMIT 20
                """,
                (src["latitude"], src["longitude"], src["latitude"], item_id, radius_m),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = [_serialize_item(r) | {"distance_m": round(r["distance_m"], 1)} for r in rows]
    return jsonify({"items": items})
