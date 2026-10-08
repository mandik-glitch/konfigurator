"""Pouziti: python3 patch_storefronts_origin.py <car_storefronts.py> - aliasy hostu, jazyk mini-shopu (podle DOMENY), snimek puvodu objednavky, admin API (lang, aliasy v kontrole duplicit, mazani) (bot5, 2026-10-02)."""
import sys

p = sys.argv[1]
t = open(p, encoding="utf-8").read()


def zamen(a, b):
    global t
    assert t.count(a) == 1, (t.count(a), a[:90])
    t = t.replace(a, b)


zamen("from flask import request, jsonify, Response\n", "from flask import request, jsonify, Response\nfrom pymysql.err import IntegrityError\n")

# 1) rozpoznani storefrontu: hlavni domena, pak alias (dva jednoduche indexovane dotazy, tabulka car_storefronts nikdy 2x v jednom dotazu)
zamen('''    cur.execute(
        "SELECT * FROM car_storefronts WHERE primary_domain=%s AND status='live'",
        (host,),
    )
    return cur.fetchone()
''', '''    # bot5, 2026-10-02: jeden storefront muze mit vic hostu - hlavni (primary_domain) a aliasy (storefront_hosts, napr. vlastni domena dealera na jeho zadost). Nejdriv hlavni host.
    cur.execute(
        "SELECT * FROM car_storefronts WHERE primary_domain=%s AND status='live'",
        (host,),
    )
    row = cur.fetchone()
    if row:
        return row
    cur.execute(
        "SELECT s.* FROM storefront_hosts h JOIN car_storefronts s ON s.id = h.storefront_id WHERE h.host=%s AND s.status='live'",
        (host,),
    )
    return cur.fetchone()
''')

# 2) nove funkce za resolve_storefront_id
zamen('''    row = resolve_storefront(cur, host=host)
    return row["id"] if row else None
''', '''    row = resolve_storefront(cur, host=host)
    return row["id"] if row else None


# ---------------------------------------------------------------------------------------------------------------- puvod objednavky, jazyk, aliasy hostu (bot5, 2026-10-02)
DEFAULT_LANG = "cs"
_LANG_RE = re.compile(r"^[a-z]{2,3}(-[a-z]{2,4})?$")
_HOST_RE = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+([a-z]{2,63}|xn--[a-z0-9-]{2,59})$")


def clean_lang(value):
    """'DE', 'de_DE', ' en ' -> 'de', 'de-de', 'en'; neplatne -> None."""
    s = str(value or "").strip().lower().replace("_", "-")
    return s if _LANG_RE.match(s) else None


def clean_host(value):
    """Normalizovany platny host (male pismena, bez portu a www, bez wildcard) nebo None."""
    h = _normalize_host(str(value or "").strip())
    return h if h and len(h) <= 255 and _HOST_RE.match(h) else None


def record_order_origin(cur, order_id):
    """Snimek puvodu zakaznicke objednavky pri jejim vzniku: order_host = normalizovany Host, order_lang = jazyk mini-shopu podle DOMENY (car_storefronts.lang), jinak 'cs'.
    Zapisuje jen kdyz order_host je jeste NULL (nemenny snimek), NIKDY nevyhodi vyjimku (objednavka se nesmi kvuli tomu rozbit). -> True, kdyz se zapsalo."""
    try:
        host = _normalize_host(request.host)
        sf = resolve_storefront(cur, host=host) if host else None
        lang = clean_lang(sf.get("lang")) if sf else None
        cur.execute("UPDATE shop_orders SET order_host=%s, order_lang=%s WHERE id=%s AND order_host IS NULL", ((host[:255] or None), lang or DEFAULT_LANG, order_id))
        return cur.rowcount == 1
    except Exception:
        app.logger.exception("record_order_origin: zapis puvodu objednavky %s selhal", order_id)
        return False


def inherited_lang(cur, host):
    """Jazyk NOVEHO storefrontu na subdomene: lang storefrontu s nejdelsi priponou domeny (dealer dostane subdomenu na nasi domene daneho jazyka). None, kdyz zadny nesedi."""
    cur.execute("SELECT lang, primary_domain FROM car_storefronts WHERE %s LIKE CONCAT('%%.', primary_domain) ORDER BY CHAR_LENGTH(primary_domain) DESC LIMIT 1", (host,))
    row = cur.fetchone()
    return clean_lang(row["lang"]) if row else None


def host_in_use(cur, host):
    """Je host uz pouzity jako hlavni domena nebo alias nejakeho storefrontu?"""
    cur.execute("SELECT id FROM car_storefronts WHERE primary_domain=%s", (host,))
    if cur.fetchone():
        return True
    cur.execute("SELECT id FROM storefront_hosts WHERE host=%s", (host,))
    return cur.fetchone() is not None


def storefront_hosts_of(cur, storefront_id):
    """[hlavni host] + aliasy storefrontu (hlavni vzdy prvni)."""
    cur.execute("SELECT primary_domain FROM car_storefronts WHERE id=%s", (storefront_id,))
    row = cur.fetchone()
    if not row:
        return []
    cur.execute("SELECT host FROM storefront_hosts WHERE storefront_id=%s ORDER BY id", (storefront_id,))
    return [row["primary_domain"]] + [r["host"] for r in cur.fetchall()]


def add_storefront_host(cur, storefront_id, host, note=None, created_by=None):
    """Prida storefrontu dalsi host (alias). Host musi byt platny, nikde jinde nepouzity (ani jako hlavni domena, ani jako alias). Objednavky ani prirazeni dealera se tim nemeni:
    storefront_id zustava, shop_orders.order_host ponese skutecny host. -> id aliasu, ValueError s cesky textem."""
    h = clean_host(host)
    if not h:
        raise ValueError("Neplatný host (očekáván např. obchod.example.cz bez portu a bez *).")
    cur.execute("SELECT id FROM car_storefronts WHERE id=%s FOR UPDATE", (storefront_id,))
    if not cur.fetchone():
        raise ValueError("Mini-shop neexistuje.")
    if host_in_use(cur, h):
        raise ValueError("Tento host už je použitý (jako hlavní doména nebo alias mini-shopu).")
    cur.execute("INSERT INTO storefront_hosts (storefront_id, host, note, created_by) VALUES (%s,%s,%s,%s)",
                (storefront_id, h, (str(note).strip()[:255] if note else None), created_by))
    return cur.lastrowid


def remove_storefront_host(cur, storefront_id, host):
    """Odebere alias (hlavni domenu nikdy). Starsi objednavky maji host jen jako text order_host, nic se jim nemeni. -> True, kdyz alias existoval."""
    h = _normalize_host(str(host or "").strip())
    cur.execute("DELETE FROM storefront_hosts WHERE storefront_id=%s AND host=%s", (storefront_id, h))
    return cur.rowcount == 1
''')

# 3) admin: vytvoreni (lang, jazyk podle nadrazene domeny, aliasy v kontrole duplicit)
zamen('''    slug = _slugify(body.get("slug") or name)

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
            )''', '''    slug = _slugify(body.get("slug") or name)
    lang = None
    if body.get("lang") not in (None, ""):
        lang = clean_lang(body.get("lang"))
        if not lang:
            return jsonify({"error": "Neplatný jazyk (např. cs, en, de)."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM car_storefronts WHERE slug=%s OR primary_domain=%s",
                (slug, primary_domain),
            )
            if cur.fetchone() or host_in_use(cur, primary_domain):
                return jsonify({"error": "Slug nebo doména už existuje."}), 409
            if lang is None:
                # subdomena nasi domeny daneho jazyka dedi jeho jazyk (dealer dostane subdomenu na domene daneho jazyka)
                lang = inherited_lang(cur, primary_domain) or DEFAULT_LANG
            cur.execute(
                "INSERT INTO car_storefronts "
                "(name, slug, car_make_id, primary_domain, template_id, status, "
                " hero_title, hero_text, meta_title, meta_description, created_by, lang) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (name, slug, body.get("car_make_id"), primary_domain,
                 body.get("template_id") or "default", body.get("status") or "draft",
                 body.get("hero_title"), body.get("hero_text"),
                 body.get("meta_title"), body.get("meta_description"),
                 current_user()["id"], lang),
            )''')

# 4) admin: uprava (lang, aliasy v kontrole duplicit)
zamen('''    new_domain = None
    if "primary_domain" in body:''', '''    if "lang" in body:
        new_lang = clean_lang(body["lang"])
        if not new_lang:
            return jsonify({"error": "Neplatný jazyk (např. cs, en, de)."}), 400
        fields.append("lang=%s")
        params.append(new_lang)

    new_domain = None
    if "primary_domain" in body:''')
zamen('''                if cur.fetchone():
                    return jsonify({"error": "Slug nebo doména už existuje."}), 409
            params.append(storefront_id)''', '''                if cur.fetchone():
                    return jsonify({"error": "Slug nebo doména už existuje."}), 409
                if new_domain and host_in_use(cur, new_domain):
                    cur.execute("SELECT id FROM car_storefronts WHERE primary_domain=%s AND id=%s", (new_domain, storefront_id))
                    if not cur.fetchone():
                        return jsonify({"error": "Slug nebo doména už existuje."}), 409
            params.append(storefront_id)''')

# 5) admin: mazani - mini-shop s aliasy nebo historii prirazeni dealerovi se nemaze (FK RESTRICT), misto 500 srozumitelna odpoved
zamen('''            cur.execute("DELETE FROM car_storefronts WHERE id=%s", (storefront_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "car_storefront", storefront_id, sf["name"])''', '''            try:
                cur.execute("DELETE FROM car_storefronts WHERE id=%s", (storefront_id,))
            except IntegrityError:
                conn.rollback()
                return jsonify({"error": "Mini-shop má další hosty (aliasy) nebo historii přiřazení dealerovi, smazat nejde."}), 409
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "car_storefront", storefront_id, sf["name"])''')
open(p, "w", encoding="utf-8").write(t)
