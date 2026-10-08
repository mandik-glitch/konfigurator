"""
Car storefronts - mini-eshopy per model auta (bot14, 2026-08-29).

Robert (pres toscanaccio-0b): "ruzne znacky/modely aut budou mit vlastni
web s kosikem, tak jak mame karoserie... nemelo by to mit vlastni
administraci, ta by se ridila vice centralne". Architektura: 1 storefront
= 1 nazev vozu (nameplate, napr. "Fiat Ducato" - "nameplate" v DB jinak
neni samostatna entita, je jen implicitni v car_models.name), delkove/
vyskove varianty (car_models radky) na jedne strance, sdileny Flask
backend + DB + KOSIK (Robertovo vyslovne rozhodnuti - NE izolovany per
web, viz AGENTS_LOG.md). Zadny novy admin - jen nova sekce v existujicim
webapp/admin.html.

Domenu -> storefront resolvuje resolve_storefront() z request.host (viz
sql/2026-08-29_car_storefronts.sql pro schema). Ktere sestavy/produkty
patri na dany web se urcuje AUTOMATICKY podle
product_assemblies.car_model_id patriciho mezi car_storefront_models
dane domeny (Robert, doplneni 2026-08-29: "kdo ma male auto nepotrebuje
videt vestavby do velkych aut" - filtr na KONKRETNI zvolenou variantu na
strance, ne jen na cely nameplate) - zadna samostatna
storefront<->assembly vazebni tabulka, je zbytecna (puvodni navrh ji
mel, zjednoduseno po tomhle upresneni).

Cloudflare/nginx/DNS vrstva (IP/nameservery per domena, Origin CA cert,
Authenticated Origin Pulls) je MIMO rozsah tohohle souboru - resi se v
infrastrukture (scripts/gen_storefront_vhosts.py), backend o ni nevi a
vedet nemusi (Flask vidi jen Host hlavicku, at uz dorazila pres
Cloudflare nebo primo).

⭐ NAUCENY VZOR (bot16, 2026-09-16, 2x nezavisle nahlaseno Robertem az po
nasazeni - "vsude mas stejny obrazek", pak "Všude máš stejnou cenu"):
JEDNA skladova karta (shop_products) muze mit navazanych VIC sestav
(product_assemblies) = variant stejneho produktu (napr. "jedno pasmo"
vs. "dve pasma, plne vyplne, s polici"). Pole na `shop_products`
(thumbnail_file, price_czk_placeholder) popisuji SDILENOU kartu, NE
konkretni variantu - pouzit je primo pro kazdou sestavu je bug, i kdyz
se to na prvni pohled tvari spravne (nic nespadne, jen vsechny karty
ukazou identicky obrazek/cenu). Hlavni web tenhle pripad uz resil drive
(api/product_assemblies.py::product_assemblies_public(),
api/turntable.py::turntable_public_info(assembly_id=...)) - princip
"zastupce (`pa.is_master=1`) bere cenu/obrazek z karty, KAZDA DALSI
varianta ma vlastni" plati VSUDE, kde se sestavy vypisuji jednotlive
(karty v prehledu i detail produktu, viz _fetch_storefront_products/
_storefront_product_page_response nize). Kdyz pridavas DALSI pole
zavisle na konfiguraci (ne jen obrazek/cenu), over si nejdriv, jestli
je to vlastnost KARTY, nebo KONKRETNI SESTAVY - stejna past se muze
zopakovat i tam.

Aktivace: stejna konvence jako cart.py/orders.py (zadne Blueprints). Na
konec app.py pridat (za `import cart`):

    import car_storefronts  # noqa: F401 - registruje /api/storefront/* + /api/admin/storefronts

Vyzaduje uz nasazenou migraci sql/2026-08-29_car_storefronts.sql.

Endpointy:
  VEREJNE (bez loginu, stejny vzor jako /api/shop/products v products.py):
    GET /api/storefront/config    - branding + seznam variant (car_models) teto domeny
    GET /api/storefront/products  - sestavy teto domeny, ?car_model_id= zuzeni na presne
                                     tuto variantu (sestava bez car_model_id se NEUKAZE nikde,
                                     viz komentar u funkce)

  Admin (require_permission("mini_eshopy", ...), stejny vzor jako ostatni CRUD sekce v app.py):
    GET    /api/admin/storefronts             - seznam vsech (zobrazit)
    POST   /api/admin/storefronts             - zalozeni (vytvorit)
    PUT    /api/admin/storefronts/<id>        - uprava vc. domeny/sablony/brandingu/statusu (upravit)
    DELETE /api/admin/storefronts/<id>        - smazani (smazat)
    PUT    /api/admin/storefronts/<id>/models - nahrazeni cele sady navazanych car_model_id,
                                                 kazde variante se dopocita/preslugne variant_slug (upravit)

  Vyber car_makes/car_models pro picker v adminu resi uz existujici
  GET /api/car-makes-tree (app.py) - zadny novy endpoint na to netreba.

  SSR verejne stranky (Robert pres toscanaccio-0b, 2026-08-29: "lide
  zadavaji i 'vestavba do Ducato L2H2'" - kazda varianta MUSI mit vlastni
  indexovatelnou URL, ne jen JS prepinac v ramci jedne stranky). Interni
  prefix /api/storefront-page/... - VNEJSI cistou URL (napr.
  https://ducato-domena.top/l2h2) resi nginx vhost generovany
  scripts/gen_storefront_vhosts.py, prepisem cesty na tenhle prefix.
  Zamerne NE primo na "/" a "/<slug>" v teto Flask aplikaci - ta uz ma
  vlastni "/" a spoustu jednosegmentovych/<slug> rout pro hlavni web
  (kategorie, produkty...), sdilene napric VSEMI domenami bez ohledu na
  Host hlavicku (Flask routy nejsou Host-aware) - kolize/zastineni by
  bylo tise nebezpecne. Pouziva _render_og_page() (app.py, stejny
  mechanismus jako /kategorie/<slug> - staticky HTML soubor +
  string-replace placeholderu + OG/JSON-LD injektaz do <head>).
    GET /api/storefront-page               - prehled nameplate (vsechny varianty)
    GET /api/storefront-page/<variant_slug> - detail 1 konkretni varianty
"""
import json
import os
import re

from flask import request, jsonify, Response

from app import (
    app, get_conn, require_permission, current_user, log_audit, _render_og_page, _og_escape,
    _client_ip, _rate_limited, verejny_popisek_sestavy,
)
from products import _effective_unit_price


def _normalize_host(host):
    """Host hlavicka bez portu, lowercase, bez "www." prefixu - tak jsou
    ulozene i primary_domain radky v car_storefronts."""
    if not host:
        return ""
    host = host.split(":")[0].strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name):
    s = _SLUG_RE.sub("-", (name or "").lower()).strip("-")
    return s or "storefront"


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s):
    """hero_text/variant_description jsou ZAMERNE HTML (admin je pise
    jako HTML v adminu, overeno v DB - bot3/revize kodu, 2026-09-02,
    7/7 storefrontu a 22/44 popisu modelu obsahuje <p>...) - jinde na
    strance se proto vkladaji beze zmeny, NE _og_escape(). Vyjimka je
    tenhle kratky souhrn na hub karte: orez na 160 znaku pred stripnutim
    tagu by u textu zacinajiciho <p> ukazal escapovane "&lt;p&gt;…"
    misto souvisleho textu - tady tedy tagy nejdriv odstranit, pak
    teprve oriznout a escapovat (html entity uvnitr textu, napr.
    "&amp;", se NEresi - stejne jako u zbytku teto stranky, kde uz
    admin normalni text pise primo, ne entity)."""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", s or "")).strip()


def resolve_storefront(cur, host=None):
    """Vrati radek car_storefronts (jen status='live') pro dany Host,
    nebo None. Zadna cache - stejne jednoduche jako
    get_scene_price_coefficient() v app.py, dotaz na 1 radek podle
    UNIQUE indexu (primary_domain) je levny."""
    host = _normalize_host(host if host is not None else request.host)
    if not host:
        return None
    cur.execute(
        "SELECT * FROM car_storefronts WHERE primary_domain=%s AND status='live'",
        (host,),
    )
    return cur.fetchone()


def resolve_storefront_id(cur, host=None):
    """Pro orders.py - jen id, nebo None (objednavka z hlavniho
    e-shopu/konfiguratoru, ne z modeloveho mini-eshopu)."""
    row = resolve_storefront(cur, host=host)
    return row["id"] if row else None


@app.get("/api/storefront/config")
def storefront_config():
    # VEREJNE - branding + seznam variant mini-eshopu podle domeny,
    # stejny vzor jako /api/shop/products (products.py).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sf = resolve_storefront(cur)
            if not sf:
                return jsonify({"error": "Web pro tuto domenu neni nastaveny nebo neni zverejneny.", "code": "storefront_not_found"}), 404
            cur.execute(
                "SELECT cm.id, cm.name, csm.variant_slug FROM car_storefront_models csm "
                "JOIN car_models cm ON cm.id = csm.car_model_id "
                "WHERE csm.storefront_id=%s ORDER BY cm.sort_order, cm.name",
                (sf["id"],),
            )
            models = cur.fetchall()
    finally:
        conn.close()
    return jsonify({
        "id": sf["id"],
        "name": sf["name"],
        "slug": sf["slug"],
        "template_id": sf["template_id"],
        "hero_title": sf["hero_title"],
        "hero_text": sf["hero_text"],
        "meta_title": sf["meta_title"],
        "meta_description": sf["meta_description"],
        "models": [{"id": m["id"], "name": m["name"], "variant_slug": m["variant_slug"]} for m in models],
    })


def _fetch_storefront_products(cur, storefront_model_ids, car_model_id=None):
    """Sdilena logika pro JSON endpoint i SSR stranku. car_model_id=None
    = vsechny sestavy patrici pod kteroukoli variantu teto domeny,
    jinak presne 1 konkretni variantu. Volajici musi predem overit, ze
    car_model_id (pokud zadan) patri mezi storefront_model_ids."""
    if not storefront_model_ids:
        return []
    if car_model_id is not None:
        model_filter_sql = "pa.car_model_id=%s"
        params = [car_model_id]
    else:
        placeholders = ",".join(["%s"] * len(storefront_model_ids))
        model_filter_sql = f"pa.car_model_id IN ({placeholders})"
        params = list(storefront_model_ids)

    cur.execute(
        f"""
        SELECT pa.id, pa.name, pa.car_model_id, pa.shop_product_id, pa.is_master, pa.data,
               sp.slug, sp.sku, sp.price_czk_placeholder, sp.sale_price_czk,
               sp.sale_price_from, sp.sale_price_until, sp.thumbnail_file,
               sp.stock_qty, sp.active, sp.is_archived,
               sp.price_visible_default, sp.hover_show_price, sp.hover_show_availability,
               sp.availability_text
        FROM product_assemblies pa
        LEFT JOIN shop_products sp ON sp.id = pa.shop_product_id
        WHERE pa.is_public=1 AND {model_filter_sql}
        ORDER BY pa.name
        """,
        params,
    )
    rows = cur.fetchall()

    # Otocny nahled je PER SESTAVA (bot16, 2026-09-16, Robert po zivem
    # vyzkouseni: "vsude mas stejny obrazek") - shop_products.thumbnail_file
    # je vlastnost SDILENE skladove karty, takze vsechny varianty (A-01,
    # A-02, ...) ukazovaly identickou fotku misto sve skutecne konfigurace.
    # Stejna funkce jako detail produktu (turntable.turntable_public_info),
    # jen volana zvlast pro kazdou sestavu - N+1 dotazu, ale N je tu v radu
    # jednotek az nizkych desitek karet na strance, ne stovky.
    import turntable
    card_images = {}
    for r in rows:
        if not r["shop_product_id"]:
            continue
        tt = turntable.turntable_public_info(cur, r["shop_product_id"], assembly_id=r["id"])
        if tt.get("available") and tt.get("hero_url"):
            card_images[r["id"]] = tt

    parts = []
    for r in rows:
        # Sestava BEZ karty vubec (LEFT JOIN -> shop_product_id IS NULL),
        # nebo navazana na produkt, ktery uz neni aktivni/je archivovany,
        # se na verejnem webu neukazuje (stejna logika jako jinde v
        # katalogu). Puvodni podminka `if r["shop_product_id"] and (...)`
        # kontrolovala jen druhy pripad - sestava BEZ shop_product_id
        # (napr. cerstve zalozena, karta jeste nevznikla) podminkou
        # propadla a sla ven bez ceny/karty (bot5, 2026-09-12, nalezeno
        # pri zakladani novych karet pro K-075/K-118/K-119 - dnes
        # neskodne jen proto, ze Citroen zadny storefront nema, ale
        # K-118/K-119 uz maji is_public=1 + car_model_id).
        if not r["shop_product_id"] or not r["active"] or r["is_archived"]:
            continue
        # Cena PER SESTAVA (bot16, 2026-09-16, Robert po zivem vyzkouseni:
        # "vsude mas stejnou cenu") - stejny princip jako
        # api/product_assemblies.py::product_assemblies_public()
        # ("zastupce = rucni price_czk_placeholder, jinak price_summary"):
        # zastupce (is_master=1) bere cenu z shop_products.price_czk_placeholder
        # (+ pripadna sale_price_czk pres _effective_unit_price), KAZDA
        # DALSI varianta ma svuj VLASTNI kusovnik s jinym souctem materialu/
        # spoju/baleni - price_summary.total_czk uz nese i marzi
        # (scene_price_coefficient), NENASOBIT znovu. Sleva (sale_price_czk)
        # zamerne plati JEN pro zastupce - stejne jako na hlavnim webu,
        # zadny zavedeny mechanismus jak ji aplikovat na cenu jine varianty.
        price, price_basis = None, None
        if r["is_master"]:
            if r["price_czk_placeholder"] is not None:
                price, price_basis = _effective_unit_price(cur, r, user=None)
        else:
            try:
                parsed = json.loads(r["data"]) if r["data"] else {}
            except (ValueError, TypeError):
                parsed = {}
            total = (parsed.get("price_summary") or {}).get("total_czk")
            if total is not None:
                price, price_basis = round(total), "assembly"
        parts.append({
            "assembly_id": r["id"],
            # Orez kodu karoserie a internich poznamek - viz komentar u
            # `verejny_popisek_sestavy` v app.py. Tady je to o to dulezitejsi,
            # ze storefront bezi na SKRYTE domene: sdileny identifikator jako
            # K-075 je presne ten "fingerprint", pred kterym varuje
            # TEXT_FILTR.md pravidlo 4 (dva weby jdou spojit pres kod, ktery
            # si nekdo vygoogli). Syrovy nazev se tudy posilal do 2026-09-12.
            "name": verejny_popisek_sestavy(r["name"]),
            "car_model_id": r["car_model_id"],
            "shop_product_id": r["shop_product_id"],
            "slug": r["slug"],
            "price_czk": price,
            "price_basis": price_basis,
            "thumbnail_file": r["thumbnail_file"],
            "card_image_url": card_images.get(r["id"], {}).get("hero_url"),
            "card_image_srcset": card_images.get(r["id"], {}).get("hero_srcset"),
            # bot16, 2026-09-27 (Robert pres bot3: hover efekt na vsech
            # kartach napric e-shopem, dosud jen category.html) - druhy
            # (hover) obrazek pro storefront karty bere jiny UZ EXISTUJICI
            # pojmenovany pohled ze STEJNE otockove davky (canonical dict,
            # viz turntable._build_public_payload) - zadny novy render,
            # jen jiny orez stejneho prstence. Potvrzeno s bot4 (spravce
            # GPU/renderu, dopnuje chybejici canonical soubory u 112
            # kandidatu - STEJNY zdrojovy soubor pouziva i pro
            # category.html hover, jen pres jine DB pole):
            #   - nase sestavy (hlavni = celni "hero") -> hover = "side"
            #     (bok, +90 stupnu)
            #   - Vandr karty (SKU "VD-%", hlavni = netradicni 60 stupnu
            #     mimo standardni canonical klice) -> hover = "hero"
            #     (celni pohled)
            # "_1024" varianta zamerne (bot4: mensi JPG primo pro
            # karty/nahledy, ne plne 2048 z otocky).
            "card_image_url_hover": (
                card_images.get(r["id"], {}).get("canonical", {}).get(
                    "hero_1024" if (r["sku"] or "").startswith("VD-") else "side_1024"
                )
            ),
            "stock_qty": r["stock_qty"],
            "price_visible_default": bool(r["price_visible_default"]) if r["price_visible_default"] is not None else True,
            "hover_show_price": bool(r["hover_show_price"]) if r["hover_show_price"] is not None else True,
            "hover_show_availability": bool(r["hover_show_availability"]) if r["hover_show_availability"] is not None else False,
            "availability_text": r["availability_text"],
        })
    return parts


@app.get("/api/storefront/products")
def storefront_products():
    # VEREJNE. ?car_model_id= zuzi na sestavy vazane PRESNE na tuhle
    # konkretni variantu. Bez parametru se vrati vsechny sestavy patrici
    # pod KTEROUKOLI variantu teto domeny (uvodni pohled pred vyberem
    # konkretni delky/vysky). Robert 2026-08-29 ("kdo ma male auto
    # nepotrebuje videt vestavby do velkych aut") - proto zadny fallback
    # na car_model_id IS NULL: sestava bez konkretni vazby na model
    # (napr. stary testovaci zaznam, nebo sestava vytvorena pred zavedenim
    # tohohle sloupce) se NEUKAZE na zadnem storefrontu, dokud nedostane
    # realny car_model_id - jinak by "obecna" polozka prosakovala i tam,
    # kam nepatri (overeno testem: zaznam "12345" bez vazby by se jinak
    # ukazal na kazdem webu, jakmile zakaznik zvoli konkretni variantu).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sf = resolve_storefront(cur)
            if not sf:
                return jsonify({"error": "Web pro tuto domenu neni nastaveny nebo neni zverejneny.", "code": "storefront_not_found"}), 404
            cur.execute(
                "SELECT car_model_id FROM car_storefront_models WHERE storefront_id=%s",
                (sf["id"],),
            )
            storefront_model_ids = {r["car_model_id"] for r in cur.fetchall()}

            car_model_id_raw = request.args.get("car_model_id")
            car_model_id = None
            if car_model_id_raw is not None:
                try:
                    car_model_id = int(car_model_id_raw)
                except ValueError:
                    return jsonify({"error": "car_model_id musí být číslo."}), 400
                if car_model_id not in storefront_model_ids:
                    return jsonify({"error": "Tato varianta nepatří pod tento web."}), 400

            parts = _fetch_storefront_products(cur, storefront_model_ids, car_model_id)
    finally:
        conn.close()
    return jsonify({"storefront_id": sf["id"], "parts": parts})


@app.get("/api/admin/storefronts")
@require_permission("mini_eshopy", "zobrazit")
def admin_storefronts_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.*, mk.name AS car_make_name, "
                "(SELECT COUNT(*) FROM car_storefront_models WHERE storefront_id=s.id) AS model_count "
                "FROM car_storefronts s LEFT JOIN car_makes mk ON mk.id = s.car_make_id "
                "ORDER BY s.name"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    for r in rows:
        for k in ("created_at", "updated_at"):
            if r.get(k):
                r[k] = r[k].isoformat()
    return jsonify({"storefronts": rows})


@app.get("/api/admin/storefronts/<int:storefront_id>")
@require_permission("mini_eshopy", "zobrazit")
def admin_storefronts_get(storefront_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM car_storefronts WHERE id=%s", (storefront_id,))
            sf = cur.fetchone()
            if not sf:
                return jsonify({"error": "Nenalezeno."}), 404
            for k in ("created_at", "updated_at"):
                if sf.get(k):
                    sf[k] = sf[k].isoformat()
            cur.execute(
                "SELECT cm.id, cm.name, mk.name AS make_name, csm.variant_slug FROM car_storefront_models csm "
                "JOIN car_models cm ON cm.id = csm.car_model_id "
                "JOIN car_makes mk ON mk.id = cm.make_id "
                "WHERE csm.storefront_id=%s ORDER BY mk.name, cm.name",
                (storefront_id,),
            )
            sf["models"] = cur.fetchall()
    finally:
        conn.close()
    return jsonify(sf)


@app.post("/api/admin/storefronts")
@require_permission("mini_eshopy", "vytvorit")
def admin_storefronts_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    primary_domain = _normalize_host((body.get("primary_domain") or "").strip())
    if not name:
        return jsonify({"error": "Jméno je povinné."}), 400
    if not primary_domain:
        return jsonify({"error": "Doména je povinná."}), 400
    slug = _slugify(body.get("slug") or name)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM car_storefronts WHERE slug=%s OR primary_domain=%s",
                (slug, primary_domain),
            )
            if cur.fetchone():
                return jsonify({"error": "Slug nebo doména už existuje."}), 409
            cur.execute(
                "INSERT INTO car_storefronts "
                "(name, slug, car_make_id, primary_domain, template_id, status, "
                " hero_title, hero_text, meta_title, meta_description, created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (name, slug, body.get("car_make_id"), primary_domain,
                 body.get("template_id") or "default", body.get("status") or "draft",
                 body.get("hero_title"), body.get("hero_text"),
                 body.get("meta_title"), body.get("meta_description"),
                 current_user()["id"]),
            )
            storefront_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "car_storefront", storefront_id, name)
    return jsonify({"id": storefront_id}), 201


@app.put("/api/admin/storefronts/<int:storefront_id>")
@require_permission("mini_eshopy", "upravit")
def admin_storefronts_update(storefront_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    for col in ("name", "car_make_id", "template_id", "status",
                "hero_title", "hero_text", "meta_title", "meta_description"):
        if col in body:
            fields.append(f"{col}=%s")
            params.append(body[col])

    new_domain = None
    if "primary_domain" in body:
        new_domain = _normalize_host(body["primary_domain"])
        if not new_domain:
            return jsonify({"error": "Doména nesmí být prázdná."}), 400
        fields.append("primary_domain=%s")
        params.append(new_domain)

    new_slug = None
    if "slug" in body:
        new_slug = _slugify(body["slug"])
        fields.append("slug=%s")
        params.append(new_slug)

    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM car_storefronts WHERE id=%s", (storefront_id,))
            if not cur.fetchone():
                return jsonify({"error": "Nenalezeno."}), 404
            if new_domain or new_slug:
                cond = []
                dup_params = []
                if new_domain:
                    cond.append("primary_domain=%s")
                    dup_params.append(new_domain)
                if new_slug:
                    cond.append("slug=%s")
                    dup_params.append(new_slug)
                cur.execute(
                    f"SELECT id FROM car_storefronts WHERE (({' OR '.join(cond)})) AND id!=%s",
                    dup_params + [storefront_id],
                )
                if cur.fetchone():
                    return jsonify({"error": "Slug nebo doména už existuje."}), 409
            params.append(storefront_id)
            cur.execute(f"UPDATE car_storefronts SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "car_storefront", storefront_id, ", ".join(fields))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/storefronts/<int:storefront_id>")
@require_permission("mini_eshopy", "smazat")
def admin_storefronts_delete(storefront_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM car_storefronts WHERE id=%s", (storefront_id,))
            sf = cur.fetchone()
            if not sf:
                return jsonify({"error": "Nenalezeno."}), 404
            cur.execute("DELETE FROM car_storefronts WHERE id=%s", (storefront_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "car_storefront", storefront_id, sf["name"])
    return jsonify({"status": "ok"})


_VARIANT_BRACKET_RE = re.compile(r"\[[^\]]*\]")
_VARIANT_DASH_TAIL_RE = re.compile(r"\s*[—–-]\s*$")
# bot18, 2026-09-04 (TASKS.md "osamocený rok v H1 storefront variant",
# oprava). car_models.name casto konci OTEVRENYM rokem vyroby jako
# "14-"/"22-"/"24-" (model se porad vyrabi) - stavajici
# _VARIANT_DASH_TAIL_RE strhne jen samotnou pomlcku, rok pred ni
# (oddeleny mezerou) zustane viset ("Ducato L2H2 14" misto "Ducato
# L2H2"). Testovano proti vsem 304 zivym car_models.name (2026-09-04) -
# 252 zaznamu (83 %) ma tenhle vzor, 0 nechtenych vedlejsich efektu na
# slozenych tokenech jako "H-1"/"NV200"/"T7" (tem chybi mezera pred
# cislici, takze regex nezasahne). VEDOME NEreseno: opacny/uzavreny
# vzor "-YY" (napr. "Amarok -22" = vyrabeno do 2022, ~50 modelu) - ten
# se dnes zobrazuje smysluplne, neni soucasti nahlaseneho bugu.
_VARIANT_YEAR_DASH_TAIL_RE = re.compile(r"\s+\d{2,4}\s*[—–-]\s*$")


def _clean_variant_label(nameplate_name, model_name):
    """Ocisti car_models.name na kratky citelny popisek varianty (napr.
    "L2H2") - odstrani zavorku s vendor kodem, rozmery za pomlckou,
    otevreny rok vyroby a nameplate prefix. Format nazvu neni
    konzistentni napric znackami (viz navrh v AGENTS_LOG.md) -
    best-effort, pouziva se pro zobrazeni i pro odvozeni URL slugu (viz
    _variant_slug_from_model_name nize) - POZOR, slug se ale pocita a
    UKLADA jen JEDNOU pri prirazeni modelu ke storefrontu
    (admin_storefronts_set_models), nikdy se nerecomputuje za behu, takze
    zmena teto funkce nemuze rozbit zadnou jiz existujici URL - viz
    AGENTS_LOG.md pro overeni."""
    s = model_name or ""
    if "—" in s:
        s = s.split("—", 1)[0]
    elif "–" in s:
        s = s.split("–", 1)[0]
    s = _VARIANT_BRACKET_RE.sub("", s)
    s = _VARIANT_YEAR_DASH_TAIL_RE.sub("", s)
    s = _VARIANT_DASH_TAIL_RE.sub("", s)
    s = s.strip()
    # car_models.name nikdy neobsahuje znacku (napr. "Ducato L2H2...", ne
    # "Fiat Ducato L2H2...") - storefront.name ale casto ano ("Fiat
    # Ducato"). Zkousej cely nameplate_name, pak postupne bez prvniho
    # slova ("Fiat Ducato" -> "Ducato"), az neco sedi jako prefix.
    words = (nameplate_name or "").strip().split()
    for start in range(len(words)):
        candidate = " ".join(words[start:])
        if candidate and s.lower().startswith(candidate.lower()):
            s = s[len(candidate):].strip()
            break
    return s or (model_name or "").strip()


def _variant_slug_from_model_name(nameplate_name, model_name):
    """Best-effort odvozeni kratkeho URL slugu varianty (napr. "l2h2") -
    admin muze vysledek v adminu rucne prepsat (viz car_model_slugs
    override nize)."""
    return _slugify(_clean_variant_label(nameplate_name, model_name))


@app.put("/api/admin/storefronts/<int:storefront_id>/models")
@require_permission("mini_eshopy", "upravit")
def admin_storefronts_set_models(storefront_id):
    # Nahrazuje CELOU sadu navazanych variant (car_models) najednou -
    # frontend posila multi-select jako pole id, stejny vzor jako jinde
    # v adminu (napr. accessory_conn_enabled) misto jednotlivych
    # pridat/odebrat volani. Kazde variante se dopocita variant_slug
    # (Robert: "vestavba do Ducato L2H2" - vlastni indexovatelna URL na
    # variantu, viz docstring modulu) - volitelny override
    # car_model_slugs = {"<car_model_id>": "vlastni-slug"} pro pripad, kdy
    # automaticky odvozeny slug neni hezky/spravny.
    body = request.get_json(silent=True) or {}
    car_model_ids = body.get("car_model_ids")
    if not isinstance(car_model_ids, list):
        return jsonify({"error": "car_model_ids musí být pole ID."}), 400
    try:
        car_model_ids = sorted({int(x) for x in car_model_ids})
    except (TypeError, ValueError):
        return jsonify({"error": "car_model_ids musí být čísla."}), 400
    slug_overrides_raw = body.get("car_model_slugs") or {}
    try:
        slug_overrides = {int(k): _slugify(v) for k, v in slug_overrides_raw.items()}
    except (TypeError, ValueError, AttributeError):
        return jsonify({"error": "car_model_slugs má neplatný formát."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM car_storefronts WHERE id=%s", (storefront_id,))
            sf = cur.fetchone()
            if not sf:
                return jsonify({"error": "Nenalezeno."}), 404
            rows_to_insert = []
            if car_model_ids:
                placeholders = ",".join(["%s"] * len(car_model_ids))
                cur.execute(f"SELECT id, name FROM car_models WHERE id IN ({placeholders})", car_model_ids)
                models_by_id = {r["id"]: r for r in cur.fetchall()}
                missing = set(car_model_ids) - set(models_by_id)
                if missing:
                    return jsonify({"error": f"Neexistující car_model_id: {sorted(missing)}"}), 400

                used_slugs = set()
                for mid in car_model_ids:
                    slug = slug_overrides.get(mid) or _variant_slug_from_model_name(sf["name"], models_by_id[mid]["name"])
                    base_slug = slug
                    n = 2
                    while slug in used_slugs:
                        slug = f"{base_slug}-{n}"
                        n += 1
                    used_slugs.add(slug)
                    rows_to_insert.append((storefront_id, mid, slug))

            cur.execute("DELETE FROM car_storefront_models WHERE storefront_id=%s", (storefront_id,))
            if rows_to_insert:
                cur.executemany(
                    "INSERT INTO car_storefront_models (storefront_id, car_model_id, variant_slug) VALUES (%s,%s,%s)",
                    rows_to_insert,
                )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "car_storefront_models", storefront_id, f"{len(car_model_ids)} variant")
    return jsonify({
        "status": "ok",
        "models": [{"car_model_id": mid, "variant_slug": slug} for (_, mid, slug) in rows_to_insert],
    })


def _hub_page_response(sf, cur):
    """SSR pro 'kind=brand_hub' storefront (Robert pres toscanaccio-0b,
    2026-08-30 noc: "fiat-autovestavby.top jako zastresujici hub nad
    Doblo/Ducato/Scudo") - prehledova stranka znacky, jen odkazuje na
    clenske 'model' storefronty (KAZDY na vlastni domene/subdomene),
    zadne vlastni varianty/produkty/kosik."""
    # Robert (pres toscanaccio-0b, 2026-08-30 noc): karty razeny podle
    # velikosti vozu (male->velke, zleva doprava - vizualni narativ
    # "prujezd auta rostouci velikosti", viz .sf-hub-car-drive v
    # storefront-hub.html), NE abecedne. sort_order rucne nastaven per
    # storefront (stejna konvence jako car_makes.sort_order jinde).
    #
    # bot16, 2026-09-17 (nalezeno pri oprave car_make_id NULL u
    # standalone "-vestavby.top" domen, bot3 zadani): filtr JEN podle
    # car_make_id NESTACI - stejna znacka ma i samostatne standalone
    # domeny (fiat-doblo-vestavby.top), ktere NEJSOU clenove tohohle
    # hubu, jen sdileji car_make_id. Puvodni kod na tohle omylem
    # spolehal na to, ze standalone radky maji car_make_id NULL (data
    # nekonzistence, ne zamer) - opravou te nekonzistence by se
    # standalone domeny zacaly ukazovat jako duplicitni clenove hubu
    # (Doblo/Ducato/Scudo 2x). Skutecne clenstvi v hubu pozna se podle
    # DOMENY - clen je subdomena hubovy vlastni domeny
    # (doblo.fiat-autovestavby.top pod fiat-autovestavby.top),
    # standalone domena (fiat-doblo-vestavby.top) subdomenou neni.
    domenova_pripona = "%." + sf["primary_domain"]
    cur.execute(
        "SELECT name, slug, primary_domain, hero_title, hero_text "
        "FROM car_storefronts WHERE car_make_id=%s AND kind='model' AND status='live' "
        "AND primary_domain LIKE %s "
        "ORDER BY sort_order, name",
        (sf["car_make_id"], domenova_pripona),
    )
    members = cur.fetchall()

    page_title = sf.get("meta_title") or f"{sf['name']} – vestavby na míru"
    page_desc = sf.get("meta_description") or sf.get("hero_text") or f"Vestavby na míru pro celou řadu {sf['name']}."
    og = {"title": page_title, "description": (page_desc or "")[:500], "image": None}

    # Robert (pres toscanaccio-0b, 2026-08-30 noc): hover efekt = "prujezd
    # auta" rostouci velikosti pres karty zleva doprava (male auto u
    # nejmensiho modelu, velke u nejvetsiho) - --sf-car-scale (0..1,
    # podle poradi mezi clenskymi storefronty) rika CSS (storefront-hub.
    # html), jak velkou siluetu vozu pro danou kartu vykreslit.
    member_count = max(len(members) - 1, 1)
    cards_html = "".join(
        f'<a class="sf-hub-card" href="https://{_og_escape(m["primary_domain"])}/" '
        f'style="--sf-car-scale:{idx / member_count:.2f}">'
        f'<div class="sf-hub-card-drive" aria-hidden="true"><span class="sf-hub-car-icon"></span></div>'
        f'<div class="sf-hub-card-title">{_og_escape(m["name"])}</div>'
        f'<div class="sf-hub-card-text">{_og_escape(_strip_tags(m.get("hero_text"))[:160])}</div>'
        '<div class="sf-hub-card-cta">Otevřít →</div>'
        '</a>'
        for idx, m in enumerate(members)
    ) or '<p class="sf-empty">Modelové weby zatím připravujeme.</p>'

    # Robert (pres toscanaccio-0b, 2026-08-30): "Logiman nemuze byt uvedeno
    # ani v paticce" - zadna zminka materske firmy, ani neprima.
    footer_html = f"{_og_escape(sf['name'])} – vestavby na míru na zakázku"

    body_replacements = {
        '<h1 id="sfHubTitle">Načítám…</h1>': f'<h1 id="sfHubTitle">{_og_escape(sf["hero_title"] or sf["name"])}</h1>',
        '<div id="sfHubText"></div>': f'<div id="sfHubText">{sf.get("hero_text") or ""}</div>',
        '<div id="sfHubGrid"></div>': f'<div id="sfHubGrid">{cards_html}</div>',
        '<div class="sf-hub-footer" id="sfHubFooter"></div>': f'<div class="sf-hub-footer" id="sfHubFooter">{footer_html}</div>',
    }
    return _render_og_page("storefront-hub.html", og, "", body_replacements)


def _storefront_page_response(sf, variant_slug=None):
    """SSR HTML pro verejnou storefront stranku (bez loginu). variant_slug=
    None = prehled nameplate (vsechny varianty), jinak detail 1 konkretni
    varianty. Pouziva _render_og_page() (app.py) - stejny mechanismus jako
    /kategorie/<slug>: staticky HTML soubor webapp/storefront-<template_id>.html
    + string-replace placeholderu + OG/JSON-LD injektaz do <head>."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if sf.get("kind") == "brand_hub":
                return _hub_page_response(sf, cur)

            cur.execute(
                "SELECT cm.id, cm.name, csm.variant_slug, csm.variant_description, "
                "       csm.meta_title, csm.meta_description, csm.hero_image_url "
                "FROM car_storefront_models csm "
                "JOIN car_models cm ON cm.id = csm.car_model_id "
                "WHERE csm.storefront_id=%s ORDER BY cm.sort_order, cm.name",
                (sf["id"],),
            )
            variants = cur.fetchall()

            selected = None
            if variant_slug is not None:
                selected = next((v for v in variants if v["variant_slug"] == variant_slug), None)
                if not selected:
                    return Response("Tato varianta nebyla nalezena.", status=404, mimetype="text/plain; charset=utf-8")

            storefront_model_ids = {v["id"] for v in variants}
            parts = _fetch_storefront_products(cur, storefront_model_ids, selected["id"] if selected else None)
    finally:
        conn.close()

    if selected:
        variant_label = _clean_variant_label(sf["name"], selected["name"])
        page_title = selected.get("meta_title") or f"{sf['name']} {variant_label} – vestavba na míru"
        page_desc = selected.get("meta_description") or (
            f"Vestavba do {sf['name']} {variant_label}. "
            f"Hliníkový stavebnicový systém na míru pro tuto konkrétní variantu vozu."
        )
        hero_extra_html = selected.get("variant_description") or ""
        hero_image_url = selected.get("hero_image_url")
    else:
        variant_label = None
        page_title = sf.get("meta_title") or f"{sf['name']} – vestavba na míru"
        page_desc = sf.get("meta_description") or (
            sf.get("hero_text") or f"Vestavby na míru pro {sf['name']} - hliníkový stavebnicový systém."
        )[:500]
        hero_extra_html = ""
        hero_image_url = None

    og = {"title": page_title, "description": (page_desc or "")[:500], "image": hero_image_url}

    nav_items = []
    nav_items.append(
        f'<a href="/" class="sf-variant-link{"" if selected else " sf-variant-active"}">Přehled</a>'
    )
    for v in variants:
        active = selected and v["id"] == selected["id"]
        nav_items.append(
            f'<a href="/{_og_escape(v["variant_slug"])}" class="sf-variant-link{" sf-variant-active" if active else ""}">'
            f'{_og_escape(_clean_variant_label(sf["name"], v["name"]))}</a>'
        )
    variant_nav_html = "".join(nav_items)

    cards_html = ""
    for p in parts:
        # bot16, 2026-09-27 (Robert pres bot3: hover efekt - skryta cena,
        # po najeti mysi cena + jiny render - na vsech kartach napric
        # e-shopem, dosud jen category.html) - 1:1 port stejneho
        # mechanismu jako api/storefront_pages.py (SSR karty kategorie,
        # zrcadli webapp/category.html::renderProducts()), jen s
        # sf-card-* tridami misto cp-*. Drz synchronni s obema pri
        # kazde zmene.
        hover_mode = p.get("price_visible_default") is False
        price_html = ""
        if p["price_czk"] is not None:
            price_fmt = f'{p["price_czk"]:,.0f}'.replace(",", " ")
            price_html = f'{price_fmt} Kč <span class="sf-card-vat">bez DPH</span>'
        price_block, hover_panel, name_swap_price = "", "", ""
        if hover_mode:
            if price_html and p.get("hover_show_price") is not False:
                name_swap_price = f'<div class="sf-card-name-price">{price_html}</div>'
            if p.get("availability_text") and p.get("hover_show_availability"):
                hover_panel = f'<div class="sf-card-hover-panel"><div class="sf-card-avail">{_og_escape(p["availability_text"])}</div></div>'
        elif price_html:
            price_block = f'<div class="sf-card-price">{price_html}</div>'
        cart_btn = ""
        if p["shop_product_id"]:
            cart_btn = (
                f'<button class="sf-add-cart-btn" data-product-id="{p["shop_product_id"]}">Do košíku</button>'
            )
        # Nahled (bot16, 2026-09-16, Robert: "potrebujeme tam dostat
        # obrazky") - PRIMARNE per-sestava otocny nahled (card_image_url,
        # viz turntable.turntable_public_info v _fetch_storefront_products) -
        # kazda varianta (A-01, A-02, ...) tak ukazuje SVOU skutecnou
        # konfiguraci, ne genericky obrazek sdilene skladove karty (Robert
        # po zivem vyzkouseni: "vsude mas stejny obrazek", puvodni verze
        # pouzivala jen sdilene shop_products.thumbnail_file). Fallback na
        # thumbnail_file, kdyz tahle konkretni sestava jeste nema render
        # (servirovano stejnou cestou jako zbytek katalogu -
        # webapp/katalog/thumbnails/, ne content-files - overeno pres
        # bot3/bot4 po chybnem prvnim nálezu). Prazdne/chybejici oboji =
        # zadny <img>, ne rozbita ikona.
        img_html = ""
        if p.get("card_image_url"):
            srcset_attr = f' srcset="{_og_escape(p["card_image_srcset"])}" sizes="220px"' if p.get("card_image_srcset") else ""
            img_html = f'<img class="sf-card-img" src="{_og_escape(p["card_image_url"])}"{srcset_attr} alt="{_og_escape(p["name"])}" loading="lazy">'
            if p.get("card_image_url_hover"):
                img_html += f'<img class="sf-card-img-hover" src="{_og_escape(p["card_image_url_hover"])}" loading="lazy" alt="">'
        elif p.get("thumbnail_file"):
            img_html = f'<img class="sf-card-img" src="/katalog/{_og_escape(p["thumbnail_file"])}" alt="{_og_escape(p["name"])}" loading="lazy">'
        # Odkaz na detail produktu (bot16, 2026-09-16) - kazda "sestava"
        # (assembly) muze mit jiny obrazek/nazev, ale nekolik jich sdili
        # JEDNU skladovou kartu (shop_product_id, tedy i slug) - proto
        # ?sestava=<assembly_id> vybira, ktera konkretni varianta se na
        # detailu ukaze jako vychozi (viz _storefront_product_page_response).
        card_link_open, card_link_close = "", ""
        if p.get("slug"):
            href = f'/produkt/{_og_escape(p["slug"])}?sestava={p["assembly_id"]}'
            card_link_open = f'<a class="sf-card-link" href="{href}">'
            card_link_close = '</a>'
        cards_html += (
            f'<div class="sf-card{" sf-card-hover-mode" if hover_mode else ""}">'
            f'{card_link_open}'
            f'<div class="sf-card-media">{img_html}{hover_panel}</div>'
            f'<div class="sf-card-name-row"><div class="sf-card-name">{_og_escape(p["name"])}</div>{name_swap_price}</div>'
            f'{card_link_close}'
            f'{price_block}{cart_btn}'
            '</div>'
        )
    if not cards_html:
        cards_html = '<p class="sf-empty">Pro tuto variantu zatím nejsou k dispozici žádné konkrétní sestavy - kontaktujte nás, poradíme s výběrem.</p>'

    hero_title_html = _og_escape(variant_label and f"{sf['name']} {variant_label}" or sf["name"])
    hero_text_html = (sf.get("hero_text") or "") + (f'<div class="sf-variant-desc">{hero_extra_html}</div>' if hero_extra_html else "")
    hero_image_html = f'<img class="sf-hero-img" src="{_og_escape(hero_image_url)}" alt="{hero_title_html}" loading="lazy">' if hero_image_url else ""
    # Robert (pres toscanaccio-0b, 2026-08-30): "Logiman nemuze byt uvedeno
    # ani v paticce" - zadna zminka materske firmy na storefront domenach,
    # ani nepřímá (viz i meta_title fix v _fetch_storefront_products
    # volajicich, DB obsah opraven zvlast). Paticka = vlastni jmeno
    # storefrontu, ne odkaz na Logiman.
    footer_html = f"{_og_escape(sf['name'])} – vestavby na míru na zakázku"

    body_replacements = {
        '<h1 id="sfHeroTitle">Načítám…</h1>': f'<h1 id="sfHeroTitle">{hero_title_html}</h1>',
        '<div id="sfHeroText"></div>': f'<div id="sfHeroText">{hero_text_html}</div>',
        '<div id="sfHeroImage"></div>': f'<div id="sfHeroImage">{hero_image_html}</div>',
        '<nav id="sfVariantNav"></nav>': f'<nav id="sfVariantNav">{variant_nav_html}</nav>',
        '<div id="sfProductGrid"></div>': f'<div id="sfProductGrid">{cards_html}</div>',
        '<div class="sf-footer" id="sfFooter"></div>': f'<div class="sf-footer" id="sfFooter">{footer_html}</div>',
        'id="sfLeadCarModelId" value="__CAR_MODEL_ID__"': f'id="sfLeadCarModelId" value="{selected["id"] if selected else ""}"',
    }

    template_filename = f"storefront-{sf.get('template_id') or 'default'}.html"
    template_path = os.path.join(os.path.dirname(__file__), "..", "webapp", template_filename)
    if not os.path.isfile(template_path):
        template_filename = "storefront-default.html"

    return _render_og_page(template_filename, og, "", body_replacements)


def _storefront_product_page_response(sf, slug):
    """Detail 1 konkretniho produktu na storefrontu (bot16, 2026-09-16,
    Robert: "musi to mit i nejaky detail produktu, stejne jako na
    hlavnim webu"). Maximalni znovupouziti vzoru z product.html/
    storefront_pages.py::_product_page_response (SSR turntable hero
    pres turntable.turntable_public_info(), stejna funkce).

    ZAMERNE VYNECHANO oproti hlavnimu webu (Robert 2026-09-16: "detaily
    musi byt plne", ale zaroven "jeste se rozhodnu" o firemni identite -
    do rozhodnuti zustava anonymizovano stejne jako zbytek storefrontu):
      - Kod produktu ("Kód: <sku>" na hlavnim webu, #pdSku) - SKU/K-kod
        je presne ten "otisk", pred kterym varuje TEXT_FILTR.md pravidlo
        4 (dva weby jdou spojit pres shodny kod). Nazev uz se cisti pres
        verejny_popisek_sestavy() stejne jako karty v prehledu.
      - STP stahovani 3D modelu, zakreslovaci nastroj pripominek,
        slevove kody, prepocet na kusy tyce - vsechno funkce vazane na
        interni pracovni postup hlavniho e-shopu, na skryte domene bez
        vlastni administrace nedavaji smysl / nebyly zadany.
    Snadno dopnutelne pozdeji, az/pokud Robert rozhodne jinak - viz
    komentare u prislusnych mist nize.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT car_model_id FROM car_storefront_models WHERE storefront_id=%s",
                (sf["id"],),
            )
            storefront_model_ids = {r["car_model_id"] for r in cur.fetchall()}
            if not storefront_model_ids:
                return Response("Produkt nebyl nalezen.", status=404, mimetype="text/plain; charset=utf-8")

            cur.execute(
                "SELECT id, slug, name, price_czk_placeholder, sale_price_czk, sale_price_from, "
                "sale_price_until, dealer_discount_percent, stock_qty, availability_text, "
                "length_mm, width_mm, height_mm, thumbnail_file "
                "FROM shop_products WHERE slug=%s AND active=1 AND is_archived=0",
                (slug,),
            )
            sp = cur.fetchone()
            if not sp:
                return Response("Produkt nebyl nalezen.", status=404, mimetype="text/plain; charset=utf-8")

            placeholders = ",".join(["%s"] * len(storefront_model_ids))
            cur.execute(
                f"SELECT id, name, car_model_id, is_master, data FROM product_assemblies "
                f"WHERE shop_product_id=%s AND is_public=1 AND car_model_id IN ({placeholders}) "
                f"ORDER BY is_master DESC, id ASC",
                [sp["id"]] + list(storefront_model_ids),
            )
            assemblies = cur.fetchall()
            if not assemblies:
                # Produkt existuje, ale zadna jeho verejna sestava nepatri
                # pod TUHLE domenu (stejna filozofie jako
                # _fetch_storefront_products - "kdo ma male auto nepotrebuje
                # videt vestavby do velkych aut", tady navic i cizi domena).
                return Response("Produkt nebyl nalezen.", status=404, mimetype="text/plain; charset=utf-8")

            selected = None
            sestava_raw = request.args.get("sestava")
            if sestava_raw:
                try:
                    sestava_id = int(sestava_raw)
                except ValueError:
                    sestava_id = None
                if sestava_id is not None:
                    selected = next((a for a in assemblies if a["id"] == sestava_id), None)
            if not selected:
                selected = assemblies[0]  # uz serazeno is_master DESC, id ASC

            # Cena PER SESTAVA - stejny princip jako v
            # _fetch_storefront_products vyse (viz komentar tam), jen tady
            # rovnou pro `selected` (aktualne vybranou variantu na detailu).
            price, price_basis = None, None
            if selected["is_master"]:
                if sp["price_czk_placeholder"] is not None:
                    price, price_basis = _effective_unit_price(cur, sp, user=None)
            else:
                try:
                    parsed = json.loads(selected["data"]) if selected["data"] else {}
                except (ValueError, TypeError):
                    parsed = {}
                total = (parsed.get("price_summary") or {}).get("total_czk")
                if total is not None:
                    price, price_basis = round(total), "assembly"

            import turntable
            tt_info = turntable.turntable_public_info(cur, sp["id"], assembly_id=selected["id"])
    finally:
        conn.close()

    product_name = verejny_popisek_sestavy(selected["name"]) or sf["name"]
    og = {
        "title": f"{product_name} – {sf['name']}",
        "description": f"{product_name} pro {sf['name']} - hliníkový stavebnicový systém na míru.",
        "image": tt_info.get("hero_url") if tt_info.get("available") else None,
    }

    hero_html = ""
    if tt_info.get("available") and tt_info.get("hero_url"):
        hero_w = tt_info.get("hero_width") or 2048
        hero_h = tt_info.get("hero_height") or 1536
        hero_srcset = tt_info.get("hero_srcset")
        srcset_attr = f' srcset="{_og_escape(hero_srcset)}" sizes="(max-width: 640px) 100vw, 50vw"' if hero_srcset else ""
        hero_html = (
            f'<img data-tt-hero src="{_og_escape(tt_info["hero_url"])}" width="{hero_w}" height="{hero_h}"'
            f'{srcset_attr} alt="{_og_escape(product_name)}" decoding="async" fetchpriority="high">'
        )

    # Prepinac variant (bot16) - zrcadli #pdAssemblyVariants na hlavnim
    # webu, jen jako skutecne odkazy (?sestava=<id>) misto JS prepinace -
    # zadny sdileny JS soubor mezi storefront sablonami (viz zbytek
    # tohohle souboru), odkazy funguji i bez JS a kazda varianta je
    # snadno sdilitelna URL.
    variants_html = ""
    if len(assemblies) > 1:
        pills = []
        for a in assemblies:
            active = a["id"] == selected["id"]
            label = verejny_popisek_sestavy(a["name"]) or "varianta"
            pills.append(
                f'<a class="sf-pd-variant-link{" sf-pd-variant-active" if active else ""}" '
                f'href="/produkt/{_og_escape(sp["slug"])}?sestava={a["id"]}">{_og_escape(label)}</a>'
            )
        variants_html = "".join(pills)

    price_html = ""
    if price is not None:
        price_fmt = f"{price:,.0f}".replace(",", " ")
        price_html = f'{price_fmt} Kč <span class="sf-pd-vat">bez DPH</span>'
    else:
        price_html = "Cena na dotaz"

    cart_btn_html = (
        f'<button class="sf-add-cart-btn" data-product-id="{sp["id"]}">Do košíku</button>'
        if price is not None else ""
    )
    availability_html = _og_escape(sp.get("availability_text") or "") if sp.get("availability_text") else ""

    body_replacements = {
        '<h1 id="sfPdTitle">Načítám…</h1>': f'<h1 id="sfPdTitle">{_og_escape(product_name)}</h1>',
        '<div id="sfPdHero"></div>': f'<div id="sfPdHero">{hero_html}</div>',
        '<div id="sfPdVariants"></div>': f'<div id="sfPdVariants">{variants_html}</div>',
        '<div id="sfPdPrice"></div>': f'<div id="sfPdPrice">{price_html}</div>',
        '<div id="sfPdCartBtn"></div>': f'<div id="sfPdCartBtn">{cart_btn_html}</div>',
        '<div id="sfPdAvailability"></div>': f'<div id="sfPdAvailability">{availability_html}</div>',
        '<div class="sf-footer" id="sfFooter"></div>': (
            f'<div class="sf-footer" id="sfFooter">{_og_escape(sf["name"])} – vestavby na míru na zakázku</div>'
        ),
    }

    return _render_og_page("storefront-product.html", og, "", body_replacements)


@app.get("/api/storefront-page/produkt/<slug>")
def storefront_page_product(slug):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sf = resolve_storefront(cur)
    finally:
        conn.close()
    if not sf:
        return Response("Web pro tuto doménu není nastavený nebo není zveřejněný.", status=404, mimetype="text/plain; charset=utf-8")
    return _storefront_product_page_response(sf, slug)


@app.get("/api/storefront-page")
def storefront_page_overview():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sf = resolve_storefront(cur)
    finally:
        conn.close()
    if not sf:
        return Response("Web pro tuto doménu není nastavený nebo není zveřejněný.", status=404, mimetype="text/plain; charset=utf-8")
    return _storefront_page_response(sf)


@app.get("/api/storefront-page/<variant_slug>")
def storefront_page_variant(variant_slug):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sf = resolve_storefront(cur)
    finally:
        conn.close()
    if not sf:
        return Response("Web pro tuto doménu není nastavený nebo není zveřejněný.", status=404, mimetype="text/plain; charset=utf-8")
    return _storefront_page_response(sf, variant_slug=variant_slug)


@app.post("/api/storefront/lead")
def storefront_lead_create():
    # VEREJNE - poptavkovy formular na storefront strance (Robert pres
    # toscanaccio-0b, 2026-08-30). NEPOSILA zadny e-mail primo -
    # WORKFLOW.md bod 16 ("zadne automaticke odchozi emaily bez
    # schvaleni admina") plati i tady. Zaklada:
    #   1) crm_leads radek (source='storefront') - STEJNY mechanismus
    #      jako existujici "Poptavky (CRM)" v adminu (viz crm.py
    #      crm_admin_lead_create pro puvodni vzor), takze poptavka je
    #      hned videt ve stavajici CRM pipeline, ne v novem separatnim
    #      miste.
    #   2) system_emails radek (kind='storefront_lead', status='pending')
    #      - potvrzovaci e-mail zakaznikovi, admin ho schvali/odmitne
    #      stejne jako kazdy jiny system email (viz system_emails.py),
    #      teprve schvalenim se skutecne odesle.
    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): verejny POST bez
    # limitu i honeypotu - stejna ochrana jako product_markups.py
    # (5/10 min per IP + tiche honeypot pole "website", ktere clovek
    # nikdy nevyplni - vzhlednym formularum ho jeste treba pridat, viz
    # webapp/storefront-*.html).
    if _rate_limited(f"storefront_lead:{_client_ip()}", max_requests=5, window_seconds=600):
        return jsonify({"error": "Příliš mnoho odeslaných poptávek, zkuste to prosím za chvíli."}), 429
    if (request.get_json(silent=True) or {}).get("website"):
        return jsonify({"status": "ok", "lead_id": 0}), 201

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sf = resolve_storefront(cur)
            if not sf:
                return jsonify({"error": "Web pro tuto doménu není nastavený."}), 404

            body = request.get_json(silent=True) or {}
            # Delkove limity - aspon oriznout extremni payload, at nejde
            # DB/e-mail frontu zaplavit.
            name = (body.get("name") or "").strip()[:255]
            email = (body.get("email") or "").strip().lower()[:255]
            phone = (body.get("phone") or "").strip()[:50] or None
            message = (body.get("message") or "").strip()[:4000]
            car_model_id_raw = body.get("car_model_id")

            if not name:
                return jsonify({"error": "Vyplňte jméno."}), 400
            if not email or "@" not in email:
                return jsonify({"error": "Vyplňte platný e-mail."}), 400
            if not message:
                return jsonify({"error": "Napište prosím, o co máte zájem."}), 400

            variant_label = None
            if car_model_id_raw is not None:
                try:
                    car_model_id = int(car_model_id_raw)
                except (TypeError, ValueError):
                    car_model_id = None
                if car_model_id is not None:
                    cur.execute(
                        "SELECT cm.name FROM car_storefront_models csm "
                        "JOIN car_models cm ON cm.id = csm.car_model_id "
                        "WHERE csm.storefront_id=%s AND csm.car_model_id=%s",
                        (sf["id"], car_model_id),
                    )
                    row = cur.fetchone()
                    if row:
                        variant_label = _clean_variant_label(sf["name"], row["name"])

            subject = f"Poptávka z webu {sf['name']}" + (f" – {variant_label}" if variant_label else "")

            cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (email,))
            cust = cur.fetchone()
            cur.execute(
                "INSERT INTO crm_leads (customer_id, contact_name, contact_email, contact_phone, "
                "subject, source, unread_by_admin) VALUES (%s,%s,%s,%s,%s,'storefront',1)",
                (cust["id"] if cust else None, name, email, phone, subject),
            )
            lead_id = cur.lastrowid
            cur.execute(
                "INSERT INTO crm_lead_messages (lead_id, sender_type, sender_name, body) "
                "VALUES (%s,'contact',%s,%s)",
                (lead_id, name, message),
            )

            # Potvrzovaci e-mail je zamerne brand-neutralni (jen jmeno
            # storefrontu, ne "Logiman") - stejny duvod jako paticka
            # stranky (viz AGENTS_LOG.md, 2026-08-30 noc).
            confirm_subject = f"Poptávka přijata – {sf['name']}"
            confirm_body = (
                f"Dobrý den{', ' + name if name else ''},\n\n"
                f"díky za poptávku přes web {sf['name']}"
                + (f" ({variant_label})" if variant_label else "")
                + ".\n\nOzveme se vám co nejdřív s dalšími informacemi.\n\nS pozdravem"
            )
            cur.execute(
                "INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) "
                "VALUES (NULL,'storefront_lead',%s,%s,%s,'pending','auto')",
                (email, confirm_subject, confirm_body),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "lead_id": lead_id}), 201
