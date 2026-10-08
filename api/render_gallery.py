"""render_gallery.py - hotovy render -> fotogalerie SKLADOVE KARTY.

Robert 2026-09-09 ("kde se ukladaji rendery? chci je ukladat do obrazku /
fotogalerie skladovych karet"). Do te chvile zil vysledek renderu POUZE
jako docasny soubor private-files/blender-renders/<job>.png, ktery se
hodinu po dokonceni SAM SMAZAL (blender_render.py::_cleanup_stale_jobs,
JOB_RETENTION_S) - okno renderu si ho stihlo stahnout a tim to koncilo.
Zadne trvale uloziste renderu neexistovalo.

Tenhle modul render prekloni do UZ EXISTUJICI fotogalerie produktu
(content_gallery_items, owner_type='product', soubory v
private-files/gallery-items/ - viz api/gallery_items.py). ZADNA nova
tabulka ani nove uloziste: skladova karta uz svou fotogalerii ma, render
je z jejiho pohledu jen dalsi fotka.

Dve cesty, jak se tam render dostane:

1. RUCNE - POST /api/admin/blender-render/<job>/do-galerie
   {"product_id": N} po tom, co si clovek render prohledl a chce si ho
   nechat.

2. AUTOMATICKY - kdyz uloha uz pri startu vi, ke ktere skladove karte
   patri (settings["gallery_product_id"]), ulozi se sama hned po
   uspesnem dokonceni. To je vetev pro hromadne/automaticke rendery
   produktovych sestav, kde u toho nikdo nesedi: ulozit_po_dokonceni()
   vola api/blender_render.py (lokalni render) i api/render_worker.py
   (render na Robertove GPU stanici).

Zamerne se NEMAZE zdrojovy <job>.png - o ten se dal stara bezna hodinova
uklidova lhuta, tady vznika NEZAVISLA kopie v gallery-items (jinak by
smazani fotky z galerie vzalo i vysledek, ktery si okno renderu jeste
nemuselo stihnout stahnout).
"""
import os
import shutil

from flask import jsonify, request

from app import app, get_conn, log_audit

import blender_render as br
import gallery_items as gi
import png_jpg

# Prefix nazvu souboru v gallery-items, aby slo pozdeji poznat (i pouhym
# `ls`), co je fotka od cloveka a co strojovy render.
NAZEV_PREFIX = "render"

# Robert 2026-09-09 ("tak udelej prevadec z png na jpg"): render prichazi
# jako PNG s PRUHLEDNYM pozadim (HDRI je skryta pred kamerou - viz
# PRODUKTOVE_RENDERY.md pravidlo 11), ale ve fotogalerii skladove karty
# maji vsechny ostatni fotky JPEG. Prevadi se proto pri ulozeni, s
# podlozenim pruhlednych mist barvou - JEN ulozit jako JPEG by z
# pruhledneho pozadi udelalo cerne.
VYCHOZI_POZADI = png_jpg.BILA


def _dalsi_sort(cur, product_id):
    cur.execute(
        "SELECT COALESCE(MAX(sort_order), -1) AS m FROM content_gallery_items "
        "WHERE owner_type='product' AND owner_id=%s",
        (product_id,),
    )
    return cur.fetchone()["m"] + 1


def uloz_png_do_galerie(png_path, product_id, caption=None, user_id=None,
                        is_public=0, jako_jpg=True, pozadi=None):
    """Ulozi hotovy PNG render do fotogalerie skladove karty.

    `jako_jpg=True` (vychozi) render prevede na JPEG a pruhledna mista
    podlozi barvou `pozadi` (vychozi bila). `jako_jpg=False` ulozi PNG
    tak, jak je - vcetne alfy, kdyz ji ma.

    Vraci (item_id, stored_name). Vyhazuje FileNotFoundError, kdyz render
    uz neexistuje (typicky ho mezitim smazala hodinova uklidova lhuta),
    a ValueError, kdyz skladova karta neexistuje.
    """
    if not os.path.exists(png_path):
        raise FileNotFoundError(png_path)

    pripona = "jpg" if jako_jpg else "png"
    stored_name = f"product-{product_id}_{NAZEV_PREFIX}-{os.urandom(4).hex()}.{pripona}"
    cil = os.path.join(gi.GALLERY_ITEMS_DIR, stored_name)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
            if not cur.fetchone():
                raise ValueError("Skladová karta neexistuje.")
            sort_order = _dalsi_sort(cur, product_id)
            # Soubor ulozit AZ po overeni produktu, ale JESTE PRED
            # INSERTem - radek v DB bez souboru na disku je horsi nez
            # osamocený soubor (ten galerie jen nezobrazi).
            if jako_jpg:
                png_jpg.png_na_jpg(png_path, cil, pozadi=pozadi or VYCHOZI_POZADI)
            else:
                shutil.copyfile(png_path, cil)
            try:
                cur.execute(
                    "INSERT INTO content_gallery_items "
                    "(owner_type, owner_id, filename, media_type, caption, sort_order, "
                    " is_public, created_by, created_role) "
                    "VALUES ('product', %s, %s, 'image', %s, %s, %s, %s, %s)",
                    (product_id, stored_name, caption, sort_order,
                     1 if is_public else 0, user_id, "render"),
                )
                item_id = cur.lastrowid
            except Exception:
                try:
                    os.remove(cil)
                except OSError:
                    pass
                raise
        conn.commit()
    finally:
        conn.close()
    return item_id, stored_name


def ulozit_po_dokonceni(job):
    """Automaticke ulozeni hned po uspesnem renderu - JEN kdyz si uloha
    nese settings["gallery_product_id"]. Vraci dict s poli do stavu
    ulohy (prazdny, kdyz se neukladalo).

    ZAMERNE NEZAPISUJE STAV SAMA. Volajici (blender_render.py pro lokalni
    render, render_worker.py pro render na GPU stanici) vysledek priloziji
    do TEHOZ _write_status(state="done", ...) volani, kterym ulohu
    dokoncuji. Dva duvody:

    1. _write_status() stav PREPISUJE (drzi si jen _STICKY_STATUS_KEYS),
       ne doplnuje - samostatny zapis by smazal prave dopsany state="done".
    2. Kdyby se zapisovalo az po "done", existoval by okamzik, kdy klient
       vidi hotovy render bez informace o galerii - a okno renderu by
       zacalo ukladat podruhe (dve stejne fotky u karty).

    NIKDY nesmi vyhodit vyjimku - hotovy render se kvuli selhani ukladani
    do galerie nesmi tvarit jako chyba.
    """
    try:
        cfg_path = os.path.join(br.RENDER_OUT_DIR, f"{job}.json")
        with open(cfg_path, "r", encoding="utf-8") as fh:
            import json
            settings = json.load(fh)
        product_id = settings.get("gallery_product_id")
        if not product_id:
            return {}
        st = br._read_status(job) or {}
        item_id, stored = uloz_png_do_galerie(
            os.path.join(br.RENDER_OUT_DIR, f"{job}.png"),
            int(product_id),
            caption=settings.get("gallery_caption") or settings.get("source_filename"),
            user_id=st.get("user_id"),
            jako_jpg=settings.get("gallery_format", "jpg") != "png",
            pozadi=png_jpg.parse_barva(settings.get("gallery_background")),
        )
        app.logger.info("Render %s ulozen do fotogalerie karty %s jako %s",
                        job, product_id, stored)
        return {"gallery_item_id": item_id, "gallery_product_id": int(product_id)}
    except Exception as e:  # noqa: BLE001 - viz docstring
        app.logger.exception("Render %s: ulozeni do fotogalerie selhalo", job)
        return {"gallery_error": str(e)[:200]}


@app.post("/api/admin/blender-render/<job>/do-galerie")
def blender_render_do_galerie(job):
    """Rucni ulozeni uz hotoveho renderu do fotogalerie skladove karty."""
    body = request.get_json(silent=True) or {}
    try:
        product_id = int(body.get("product_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí platné product_id."}), 400

    # Opravneni se ridi TOUTEZ sekci jako rucni nahrani fotky do galerie
    # produktu (produkty_sklad/upravit) - render, ktery v galerii skonci,
    # je z pohledu prav obycejna fotka skladove karty.
    user, err = gi._require_owner_permission("product", "upravit", product_id)
    if err:
        return err

    if not (job.isalnum() and len(job) == 32):
        return jsonify({"error": "Neplatné ID úlohy."}), 400
    st = br._read_status(job)
    if not st:
        return jsonify({"error": "Úloha neexistuje (nebo už byla uklizena)."}), 404
    if st.get("state") != "done":
        return jsonify({"error": "Render ještě není hotový."}), 409

    # format: "jpg" (vychozi, pruhledna mista podlozena barvou "background")
    # nebo "png" (ulozi se tak, jak je - vcetne alfy).
    try:
        pozadi = png_jpg.parse_barva(body.get("background"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    png_path = os.path.join(br.RENDER_OUT_DIR, f"{job}.png")
    try:
        item_id, stored = uloz_png_do_galerie(
            png_path, product_id,
            caption=(body.get("caption") or "").strip()[:255] or st.get("source_filename"),
            user_id=user["id"],
            is_public=1 if body.get("is_public") else 0,
            jako_jpg=(body.get("format") or "jpg") != "png",
            pozadi=pozadi,
        )
    except FileNotFoundError:
        return jsonify({"error": "Soubor renderu už na serveru není "
                                 "(rendery se hodinu po dokončení uklízejí)."}), 410
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    log_audit(user["id"], "create", "gallery_item", item_id,
              f"render {job[:8]} -> skladová karta #{product_id}")
    return jsonify({"status": "ok", "item_id": item_id, "filename": stored,
                    "url": f"/content-files/gallery-items/{stored}"})
