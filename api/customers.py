"""
Evidence zakazniku (fakturacni profil) - bot3, 2026-07-25 (v2).

Robert: "vytvoř systém evidence zákazníků, fakturační adresa, dodací
adresa, ičo dič jmeno firmy nebo živnostníka, kontaktní udaje, email
telefon". Kontext: ve stejny den bylo take rozhodnuto, ze objednavku uz
jde zadat jen po prihlaseni (zadny guest checkout), takze kazdy profil
zakaznika je vazany 1:1 na existujici ucet (app_users) - viz
shop_customers.user_id UNIQUE v sql/2026-07-25_orders_v2_customers_cart_shipping.sql.

Aktivace: stejna konvence jako orders.py/cart.py - zadne Blueprints, modul
se registruje primo na existujici `app` z app.py. Na konec app.py (za
ostatni `import orders`/`import cart` radky) pridat:

    import customers  # noqa: F401 - registruje /api/customer/profile + /api/admin/customers

Vyzaduje uz nasazenou migraci 2026-07-25_orders_v2_customers_cart_shipping.sql
(tabulka shop_customers).

Endpointy:
  GET  /api/customer/profile        - vlastni profil (nebo null, pokud jeste nevyplnil)
  PUT  /api/customer/profile        - ulozeni/uprava vlastniho profilu (upsert)
  GET  /api/admin/customers         - seznam vsech profilu (admin, s hledanim ?q=)
  GET  /api/admin/customers/<id>    - detail profilu (admin)
  PUT  /api/admin/customers/<id>    - rucni oprava profilu adminem (napr. spatne ICO)

Profil se v /api/orders (orders.py) pouziva jen jako VOLITELNY zdroj
predvyplnenych udaju - objednavka si vzdy ulozi vlastni snapshot (viz
billing_* sloupce v shop_orders), takze pozdejsi zmena profilu
nezmeni jiz existujici objednavky.

--- V3 (bot3, 2026-07-25, PRIPRAVENO, ZATIM NENASAZENO) ---
Robert: "skupiny zákazníků, potřebujeme jim přiřadit různou rámcovou
slevu." Pridava shop_customer_groups (nazev + discount_percent) a
shop_customers.group_id. Prirazeni skupiny je VYHRADNE admin akce -
samoobsluzny PUT /api/customer/profile zakaznikovi group_id zmenit
NEDOVOLI (viz _validate_and_clean - pole se v nem vubec nezpracovava).
Sleva skupiny se aplikuje pri POST /api/orders (orders.py) primo do ceny
polozek - viz tamni docstring. Vyzaduje migraci
sql/2026-07-25_customer_groups.sql (JESTE NEAPLIKOVANOU na produkci).

Nove admin endpointy:
  GET    /api/admin/customer-groups        - seznam vsech skupin
  POST   /api/admin/customer-groups        - vytvoreni skupiny
  PUT    /api/admin/customer-groups/<id>   - uprava (nazev/sleva/aktivni/poradi)
  DELETE /api/admin/customer-groups/<id>   - smazani (zakazniky ve skupine
                                              odpoji ON DELETE SET NULL)

--- V5 (bot3, 2026-07-25) - import historickych zakazniku ---
Robert poskytl customers.xml (export z puvodniho systemu, 612 zaznamu).
Import provaden jednorazovym skriptem (viz AGENTS_LOG.md, zaznam "bot3 -
import zakazniku"), NE pres API - "note"/"legacy_guid"/"legacy_order_count"/
"legacy_order_value_czk" sloupce z migrace
sql/2026-07-25_customers_import_prep.sql jsou proto ctecí (v _serialize_customer),
ale nejsou soucasti _PROFILE_FIELDS/_validate_and_clean - normalni PUT
endpointy je nemeni.
"""
import re
import secrets

import pymysql
from flask import request, jsonify
from werkzeug.security import generate_password_hash

from app import (
    app, get_conn, login_required, current_user, log_audit, require_permission,
    parse_bulk_ids, bulk_update_fields, bulk_delete, get_pagination_args, paginated_query,
    create_party,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CUSTOMER_TYPES = ("osoba", "firma")


def _serialize_customer(row, include_user=False):
    out = {
        "id": row["id"],
        "user_id": row["user_id"],
        "customer_type": row["customer_type"],
        "full_name": row["full_name"],
        "company_name": row["company_name"],
        "ico": row["ico"],
        "dic": row["dic"],
        "email": row["email"],
        "phone": row["phone"],
        "billing_address": row["billing_address"],
        "billing_street": row.get("billing_street"),
        "billing_city": row.get("billing_city"),
        "billing_zip": row.get("billing_zip"),
        "delivery_address": row["delivery_address"],
        "delivery_street": row.get("delivery_street"),
        "delivery_city": row.get("delivery_city"),
        "delivery_zip": row.get("delivery_zip"),
        "delivery_same_as_billing": bool(row.get("delivery_same_as_billing")),
        "hide_name_on_documents": bool(row.get("hide_name_on_documents")),
        "group_id": row.get("group_id"),
        "group_name": row.get("group_name"),
        "group_discount_percent": float(row["group_discount_percent"]) if row.get("group_discount_percent") is not None else None,
        "is_dealer_approved": bool(row.get("is_dealer_approved")),
        "note": row.get("note"),
        "legacy_order_count": row.get("legacy_order_count"),
        "legacy_order_value_czk": float(row["legacy_order_value_czk"]) if row.get("legacy_order_value_czk") is not None else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }
    if include_user:
        out["account_email"] = row.get("account_email")
        out["account_name"] = row.get("account_name")
    return out


def _serialize_group(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "discount_percent": float(row["discount_percent"]),
        "note": row["note"],
        "active": bool(row["active"]),
        "sort_order": row["sort_order"],
    }


_CUSTOMER_SELECT_WITH_GROUP = (
    "SELECT c.*, g.name AS group_name, g.discount_percent AS group_discount_percent "
    "FROM shop_customers c LEFT JOIN shop_customer_groups g ON g.id = c.group_id"
)


def _parse_zip(raw, label):
    """PSC normalizovane na 5 cistych cislic (bez mezery) - "123 45" i
    "12345" se ulozi stejne. Vraci (hodnota|None, chyba|None)."""
    raw = (raw or "").strip()
    if not raw:
        return None, None
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 5:
        return None, f"Neplatné PSČ {label} (očekáváno 5 číslic)."
    return digits, None


def _compose_address(street, city, zip_code, fallback):
    """Slozi jednoradkovou adresu ze strukturovanych poli (Robert V9,
    2026-07-26: "zvlast PSC, zvlast Mesto i Ulici"). Kdyz zadne
    strukturovane pole neprislo (napr. puvodni zakaznicky self-service
    checkout v category.html/product.html, ktery dal posila jen volny
    text), pouzije se `fallback` (puvodni primo poslane billing_address/
    delivery_address) - zpetna kompatibilita bez nutnosti menit ten
    checkout formular."""
    if not street and not city and not zip_code:
        return fallback
    zip_city = f"{zip_code or ''} {city or ''}".strip()
    parts = [p for p in (street, zip_city) if p]
    return ", ".join(parts) if parts else fallback


def _serialize_address(r):
    return {
        "id": r["id"], "label": r["label"], "street": r["street"], "city": r["city"],
        "zip": r["zip"], "is_default": bool(r["is_default"]), "sort_order": r["sort_order"],
    }


def _sync_default_address(cur, customer_id):
    """Zrcadli radek s is_default=1 (pokud existuje) do
    shop_customers.delivery_* - VSECHNA existujici mista, ktera ctou
    delivery_address PRIMO ze shop_customers (api/orders.py,
    api/documents.py, webapp/product.html, objednavky-doklady.js),
    tak funguji beze zmeny, i kdyz zakaznik ma vic ulozenych adres -
    porad jen ctou "tu jednu" delivery adresu, ktera se ted jen muze
    prepnout mezi vic ulozenymi variantami. Kdyz zadny radek neni
    is_default (prazdny adresar), shop_customers.delivery_* se
    NEMENI (nemazat existujici data jen proto, ze adresar zrovna nema
    zadny vychozi radek)."""
    cur.execute(
        "SELECT street, city, zip FROM shop_customer_addresses WHERE customer_id=%s AND is_default=1 LIMIT 1",
        (customer_id,),
    )
    row = cur.fetchone()
    if not row:
        return
    delivery_address = _compose_address(row["street"], row["city"], row["zip"], None)
    cur.execute(
        "UPDATE shop_customers SET delivery_street=%s, delivery_city=%s, delivery_zip=%s, "
        "delivery_address=%s, delivery_same_as_billing=0 WHERE id=%s",
        (row["street"], row["city"], row["zip"], delivery_address, customer_id),
    )


def _validate_and_clean(body, existing_email_fallback, raw_body=None):
    """`body` je uz PO merge s existujicim radkem (viz
    _merge_body_with_existing) - obsahuje kompletni sadu poli, chybejici
    klice doplnene z existujiciho radku. `raw_body` (kdyz predano) je
    PUVODNI telo POSLANE klientem v TOMHLE requestu, PRED merge - pouziva
    se vyhradne pro rozhodnuti volny-text-vs-strukturovana-adresa nize.
    Bez tohohle rozliseni by "carry-over" starych billing_street/city/zip
    z existujiciho radku tise prebil cerstve poslany billing_address
    (bug odhaleny integracnim testem V9 - zakaznik zmeni adresu jen
    volnym textem, ulozi se, ale zobrazi se porad stara slozena z
    predchozich strukturovanych poli)."""
    raw_body = body if raw_body is None else raw_body

    customer_type = (body.get("customer_type") or "osoba").strip()
    if customer_type not in CUSTOMER_TYPES:
        return None, "Neplatný typ zákazníka (očekáváno 'osoba' nebo 'firma')."

    full_name = (body.get("full_name") or "").strip()
    if not full_name:
        return None, "Jméno je povinné."

    company_name = (body.get("company_name") or "").strip() or None
    if customer_type == "firma" and not company_name:
        return None, "U firmy/živnostníka je povinný název firmy."

    ico = (body.get("ico") or "").strip() or None
    dic = (body.get("dic") or "").strip() or None

    email = (body.get("email") or "").strip().lower() or existing_email_fallback
    if not email or not _EMAIL_RE.match(email):
        return None, "Neplatný e-mail."

    phone = (body.get("phone") or "").strip() or None

    # V9 (bot5, 2026-07-26): strukturovana adresa (Robert: "zvlast PSC,
    # zvlast Mesto i Ulici, zatrzitko na stejnou dodaci adresu s
    # fakturacni"). billing_address/delivery_address (volny text)
    # ZUSTAVAJI v DB a v odpovedi. Zdroj pravdy pro TENHLE konkretni
    # request se urcuje z `raw_body` (co klient OPRAVDU poslal TEĎ, ne
    # co "prežilo" z merge): kdyz prijdou strukturovana pole, slozi se z
    # nich billing_address znovu; kdyz prijde JEN volny text
    # (puvodni zakaznicky checkout, ktery strukturovana pole vubec
    # nezna), ten je autoritativni a stare strukturovane pole se
    # rozpoji (nastavi na NULL), aby priste nezustavaly zastarale a
    # netise neprebily novy volny text.
    # Robert 2026-08-06 ("Pro dopravu Toptrans je nutné zadat PSČ dodací
    # adresy" - zakaznik se nemel jak z tehle hlasky dostat, checkout
    # v category.html/product.html/index.html zadne PSC pole nemel):
    # billing_zip/delivery_zip UMYSLNE vyjmuty z "structured_keys" nize -
    # kdyz prijde jen volny text adresy + samostatne PSC (novy checkout
    # bez street/city poli), volny text zustava AUTORITATIVNI (needuplikuje
    # se/nepreklada pres _compose_address, ktery by ho jinak zahodil a
    # nahradil pouhym cislem PSC), PSC se jen ulozi vedle nej do vlastniho
    # sloupce. Plne strukturovany zapis (street a/nebo city, admin.html)
    # se chova stejne jako drivi - viz "else" vetev nize.
    billing_structured_keys = ("billing_street", "billing_city")
    billing_has_structured = any(k in raw_body for k in billing_structured_keys)
    billing_free_text_only = ("billing_address" in raw_body) and not billing_has_structured
    if billing_free_text_only:
        billing_street = billing_city = None
        billing_address = (raw_body.get("billing_address") or "").strip() or None
        if "billing_zip" in raw_body:
            billing_zip, err = _parse_zip(body.get("billing_zip"), "fakturační adresy")
            if err:
                return None, err
        else:
            billing_zip = None
    else:
        billing_street = (body.get("billing_street") or "").strip() or None
        billing_city = (body.get("billing_city") or "").strip() or None
        billing_zip, err = _parse_zip(body.get("billing_zip"), "fakturační adresy")
        if err:
            return None, err
        billing_address = _compose_address(
            billing_street, billing_city, billing_zip,
            (body.get("billing_address") or "").strip() or None,
        )

    # "Stejna dodaci adresa jako fakturacni" - kdyz zaskrtnuto, dodaci
    # (strukturovane i slozene) se PREVEZME z prave vyreseneho
    # fakturacniho stavu na serveru - nezavisle na tom, co presne poslal
    # klient v delivery_*, server je zdroj pravdy pro tenhle odvozeny
    # stav.
    delivery_same_as_billing = bool(body.get("delivery_same_as_billing"))
    if delivery_same_as_billing:
        delivery_street, delivery_city, delivery_zip = billing_street, billing_city, billing_zip
        delivery_address = billing_address
    else:
        # Stejny duvod jako u billing_* vyse - billing_zip fallback (viz
        # api/orders.py::_resolve_and_insert_order) uz na delivery_zip
        # nepusti prazdnou hodnotu, kdyby ji tenhle blok tise nuloval,
        # jakmile prijde jen volny text.
        delivery_structured_keys = ("delivery_street", "delivery_city")
        delivery_has_structured = any(k in raw_body for k in delivery_structured_keys)
        delivery_free_text_only = ("delivery_address" in raw_body) and not delivery_has_structured
        if delivery_free_text_only:
            delivery_street = delivery_city = None
            delivery_address = (raw_body.get("delivery_address") or "").strip() or None
            if "delivery_zip" in raw_body:
                delivery_zip, err = _parse_zip(body.get("delivery_zip"), "dodací adresy")
                if err:
                    return None, err
            else:
                delivery_zip = None
        else:
            delivery_street = (body.get("delivery_street") or "").strip() or None
            delivery_city = (body.get("delivery_city") or "").strip() or None
            delivery_zip, err = _parse_zip(body.get("delivery_zip"), "dodací adresy")
            if err:
                return None, err
            delivery_address = _compose_address(
                delivery_street, delivery_city, delivery_zip,
                (body.get("delivery_address") or "").strip() or None,
            )

    # Robert: "u firmy jmeno zaznacit interne, ze se nema prenaset do
    # faktury a na doklady" - full_name je jen kontaktni osoba, na
    # dokladech firmy ma byt company_name. Priznak je informativni pro
    # admina/pripadne budouci generovani dokladu z profilu (objednavky
    # maji vlastni nezavisly snapshot, viz shop_orders.billing_name -
    # tenhle priznak jej primo neovlivnuje).
    hide_name_on_documents = bool(body.get("hide_name_on_documents"))

    return {
        "customer_type": customer_type,
        "full_name": full_name,
        "company_name": company_name,
        "ico": ico,
        "dic": dic,
        "email": email,
        "phone": phone,
        "billing_address": billing_address,
        "billing_street": billing_street,
        "billing_city": billing_city,
        "billing_zip": billing_zip,
        "delivery_address": delivery_address,
        "delivery_street": delivery_street,
        "delivery_city": delivery_city,
        "delivery_zip": delivery_zip,
        "delivery_same_as_billing": delivery_same_as_billing,
        "hide_name_on_documents": hide_name_on_documents,
    }, None


_PROFILE_FIELDS = (
    "customer_type", "full_name", "company_name", "ico", "dic",
    "email", "phone", "billing_address", "billing_street", "billing_city", "billing_zip",
    "delivery_address", "delivery_street", "delivery_city", "delivery_zip",
    "delivery_same_as_billing", "hide_name_on_documents",
)


def _customer_set_clause(clean):
    """`SET col=%s, col=%s...` + hodnoty v poradi _PROFILE_FIELDS -
    sdileno vsemi misty, ktera zapisuji shop_customers (profile upsert,
    admin create/update), aby pribyvajici pole stacilo pridat jen do
    _PROFILE_FIELDS (misto rucniho opakovani sloupcu na 3 mistech)."""
    set_sql = ", ".join(f"{f}=%s" for f in _PROFILE_FIELDS)
    values = tuple(clean[f] for f in _PROFILE_FIELDS)
    return set_sql, values


def _customer_insert_clause(clean):
    cols_sql = ", ".join(_PROFILE_FIELDS)
    placeholders = ", ".join(["%s"] * len(_PROFILE_FIELDS))
    values = tuple(clean[f] for f in _PROFILE_FIELDS)
    return cols_sql, placeholders, values


def _require_all_fields(clean, body):
    """Admin rucni zalozeni noveho zakaznika (Robert: "vsechny pole
    povinna krome poznamky") - prisnejsi nez bazova _validate_and_clean
    (ktera zustava mirnejsi kvuli zakaznickemu self-service profilu,
    kde se pole vyplnuji postupne). company_name/ico/dic zustavaji beze
    zmeny (company_name uz povinne jen u firmy, ico/dic volitelne -
    Robert to explicitne nezminil)."""
    missing = []
    if not (body.get("phone") or "").strip():
        missing.append("telefon")
    if not clean.get("billing_street"):
        missing.append("ulice (fakturační)")
    if not clean.get("billing_city"):
        missing.append("město (fakturační)")
    if not clean.get("billing_zip"):
        missing.append("PSČ (fakturační)")
    if not clean.get("delivery_same_as_billing"):
        if not clean.get("delivery_street"):
            missing.append("ulice (dodací)")
        if not clean.get("delivery_city"):
            missing.append("město (dodací)")
        if not clean.get("delivery_zip"):
            missing.append("PSČ (dodací)")
    if missing:
        return f"Chybí povinné údaje: {', '.join(missing)}."
    return None


def _merge_body_with_existing(body, existing_row):
    """
    Opravna poznamka (bot3, 2026-07-25, v4 pri priprave rucniho zadani
    objednavek): puvodni admin_customers_update() volala _validate_and_clean
    primo na castecnem body (napr. jen {"group_id": 1}) - protoze
    _validate_and_clean VZDY sestavuje VSECHNA pole znovu z "body.get(...)"
    s fallbackem na prazdno/None, jakekoli pole, ktere admin NEPOSLAL, se
    tim tise VYMAZALO (odhaleno testem test_harness/run_tests_v4.py -
    "delivery_address predvyplnena z profilu" selhavalo, protoze druhy
    admin PUT bez "delivery_address" v tele ho smazal).

    Tahle funkce spravne implementuje CASTECNY (PATCH-like) update: pole
    pritomne v "body" (i kdyz s hodnotou null - to je zamerne "smaz tohle
    pole") maji prednost, chybejici klice se doplni z existujiciho radku.
    Pouziva se PRED zavolanim _validate_and_clean, aby validace bezela na
    UPLNEM (spravne slucenem) profilu, ne na diry v castecnem requestu.
    """
    merged = {}
    for field in _PROFILE_FIELDS:
        merged[field] = body[field] if field in body else existing_row[field]
    return merged


# ---------------------------------------------------------------------------
# Vlastni profil (prihlaseny uzivatel)
# ---------------------------------------------------------------------------

@app.get("/api/customer/profile")
@login_required
def customer_profile_get():
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(_CUSTOMER_SELECT_WITH_GROUP + " WHERE c.user_id=%s", (user["id"],))
            row = cur.fetchone()
    finally:
        conn.close()
    return jsonify({"profile": _serialize_customer(row) if row else None})


@app.put("/api/customer/profile")
@login_required
def customer_profile_upsert():
    """
    Ulozeni/uprava vlastniho profilu - CASTECNY update (pole, ktera
    request neposle, zustanou beze zmeny - viz _merge_body_with_existing,
    oprava chyby odhalene testem pri priprave v4). "group_id" se tady
    zamerne vubec nezpracovava (viz modulovy docstring).
    """
    user = current_user()
    body = request.get_json(silent=True) or {}

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_customers WHERE user_id=%s", (user["id"],))
            existing = cur.fetchone()

            merged_body = _merge_body_with_existing(body, existing) if existing else body
            clean, err = _validate_and_clean(merged_body, existing_email_fallback=user["email"], raw_body=body)
            if err:
                conn.rollback()
                return jsonify({"error": err}), 400

            if existing:
                set_sql, values = _customer_set_clause(clean)
                extra_sql, extra_values = "", ()
                if not existing["party_id"] and user["party_id"]:
                    # Doplneni chybejiciho party_id na existujicim profilu -
                    # tvrda FK (user_id) uz jednoznacne rika, komu profil
                    # patri, tohle neni nova identita ani nove dohadovani.
                    extra_sql, extra_values = ", party_id=%s", (user["party_id"],)
                cur.execute(
                    f"UPDATE shop_customers SET {set_sql}{extra_sql} WHERE user_id=%s",
                    values + extra_values + (user["id"],),
                )
            else:
                cols_sql, placeholders, values = _customer_insert_clause(clean)
                cur.execute(
                    f"INSERT INTO shop_customers (user_id, party_id, {cols_sql}) VALUES (%s, %s, {placeholders})",
                    (user["id"], user["party_id"]) + values,
                )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.get("/api/admin/customers")
@require_permission("zakaznici", "zobrazit")
def admin_customers_list():
    q = (request.args.get("q") or "").strip()
    where, params = [], []
    if q:
        where.append(
            "(c.full_name LIKE %s OR c.company_name LIKE %s OR c.email LIKE %s "
            "OR c.ico LIKE %s OR u.email LIKE %s)"
        )
        like = f"%{q}%"
        params += [like, like, like, like, like]

    # Stránkování (task #78/80) - admin-only endpoint, defaultně stránkuj
    # i bez explicitního ?page_size=.
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base_sql = (
                "SELECT c.*, u.email AS account_email, u.name AS account_name, "
                "       g.name AS group_name, g.discount_percent AS group_discount_percent "
                "FROM shop_customers c "
                "JOIN app_users u ON u.id = c.user_id "
                "LEFT JOIN shop_customer_groups g ON g.id = c.group_id"
            )
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, base_sql, where_sql, params, " ORDER BY c.updated_at DESC", page, page_size)
    finally:
        conn.close()
    resp = {"customers": [_serialize_customer(r, include_user=True) for r in rows]}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.post("/api/admin/customers")
@require_permission("zakaznici", "vytvorit")
def admin_customers_create():
    """
    Rucni pridani noveho zakaznika adminem (bot2, 2026-07-25). Robert:
    "zákazník lze přidat i ručně" - doplnuje hromadny import z
    customers.xml (viz AGENTS_LOG "bot3 - import zakazniku") o moznost
    prubezne pridavat JEDNOTLIVE nove zakazniky (napr. telefonicky
    domluveny novy odberatel), bez nutnosti aby se sam registroval.

    Vytvori NOVY ucet (app_users, role "user") + profil (shop_customers)
    v jedne transakci. Heslo je nahodne vygenerovane a NIKAM se neuklada
    ani neodesila (stejny pristup jako u importu z customers.xml) -
    zakaznik si nastavi vlastni pres "Zapomenute heslo", pokud se bude
    chtit sam nekdy prihlasit.

    Ocekavany JSON payload (stejna pole jako PUT /api/admin/customers/<id>,
    navic email a volitelne account_name):
    {
      "email": "jan@example.cz",         (povinne, musi byt volny)
      "account_name": "Jan Novak",         (volitelne, jinak se pouzije full_name)
      "customer_type": "osoba"|"firma",
      "full_name": "...",                    (povinne)
      "company_name": "...",                   (povinne, pokud firma)
      "ico": "...", "dic": "...", "phone": "...",
      "billing_address": "...", "delivery_address": "...",
      "group_id": 2,                               (volitelne)
      "note": "..."                                  (volitelne)
    }
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}

    account_email = (body.get("email") or "").strip().lower()
    if not account_email or not _EMAIL_RE.match(account_email):
        return jsonify({"error": "Neplatný nebo chybějící e-mail."}), 400

    clean, err = _validate_and_clean(body, existing_email_fallback=account_email)
    if err:
        return jsonify({"error": err}), 400

    # Robert: "vsechny pole povinna krome poznamky" - jen pro RUCNI
    # zalozeni adminem, samoobsluzny zakaznicky profil (customer_profile_upsert)
    # timhle prisnejsim pravidlem NEPROCHAZI (viz _require_all_fields docstring).
    err = _require_all_fields(clean, body)
    if err:
        return jsonify({"error": err}), 400

    account_name = (body.get("account_name") or "").strip() or clean["full_name"]
    note = (body.get("note") or "").strip() or None
    raw_group_id = body.get("group_id")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM app_users WHERE email=%s", (account_email,))
            if cur.fetchone():
                conn.rollback()
                return jsonify({"error": "Uživatel s tímto e-mailem už existuje."}), 400

            group_id = None
            if raw_group_id is not None:
                try:
                    group_id = int(raw_group_id)
                except (TypeError, ValueError):
                    conn.rollback()
                    return jsonify({"error": "Neplatné group_id."}), 400
                cur.execute("SELECT id FROM shop_customer_groups WHERE id=%s", (group_id,))
                if not cur.fetchone():
                    conn.rollback()
                    return jsonify({"error": "Zvolená skupina zákazníků neexistuje."}), 400

            random_password = secrets.token_urlsafe(24)
            party_id = create_party(
                cur, party_type=clean["customer_type"], full_name=clean["full_name"],
                primary_email=clean["email"], primary_phone=clean["phone"],
                ico=clean["ico"], dic=clean["dic"],
            )
            cur.execute(
                "INSERT INTO app_users (email, password_hash, name, role, active, party_id) "
                "VALUES (%s,%s,%s,'user',1,%s)",
                (account_email, generate_password_hash(random_password), account_name, party_id),
            )
            new_user_id = cur.lastrowid

            cols_sql, placeholders, values = _customer_insert_clause(clean)
            cur.execute(
                f"INSERT INTO shop_customers (user_id, party_id, {cols_sql}, group_id, note) "
                f"VALUES (%s, %s, {placeholders}, %s, %s)",
                (new_user_id, party_id) + values + (group_id, note),
            )
            new_customer_id = cur.lastrowid
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                _CUSTOMER_SELECT_WITH_GROUP + " WHERE c.id=%s",
                (new_customer_id,),
            )
            row = cur.fetchone()
            cur.execute("SELECT email AS account_email, name AS account_name FROM app_users WHERE id=%s", (new_user_id,))
            urow = cur.fetchone()
    finally:
        conn.close()

    row["account_email"] = urow["account_email"]
    row["account_name"] = urow["account_name"]

    log_audit(admin["id"], "create", "customer", new_customer_id,
              f"Ručně přidán nový zákazník: {clean['full_name']} ({account_email}).")
    return jsonify({"status": "ok", "customer": _serialize_customer(row, include_user=True)}), 201


@app.get("/api/admin/customers/<int:customer_id>")
@require_permission("zakaznici", "zobrazit")
def admin_customers_get(customer_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.*, u.email AS account_email, u.name AS account_name, "
                "       g.name AS group_name, g.discount_percent AS group_discount_percent "
                "FROM shop_customers c "
                "JOIN app_users u ON u.id = c.user_id "
                "LEFT JOIN shop_customer_groups g ON g.id = c.group_id "
                "WHERE c.id=%s",
                (customer_id,),
            )
            row = cur.fetchone()
            # Adresar (Robert pres bot3, 2026-09-29: "vicero dodacich
            # adres") - rovnou soucasti detailu, at karta zakaznika
            # nemusi delat druhy request jen kvuli seznamu adres.
            addresses = []
            if row:
                cur.execute(
                    "SELECT * FROM shop_customer_addresses WHERE customer_id=%s ORDER BY sort_order, id",
                    (customer_id,),
                )
                addresses = [_serialize_address(r) for r in cur.fetchall()]
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Zákazník neexistuje."}), 404
    return jsonify({"customer": _serialize_customer(row, include_user=True), "addresses": addresses})


@app.put("/api/admin/customers/<int:customer_id>")
@require_permission("zakaznici", "upravit")
def admin_customers_update(customer_id):
    """
    Admin uprava profilu zakaznika - CASTECNY update, stejne jako
    PUT /api/customer/profile (viz _merge_body_with_existing). Krome
    stejnych poli navic prijima "group_id" (int nebo null) - PRIRAZENI
    SLEVOVE SKUPINY JE VYHRADNE ADMIN AKCE, samoobsluzny profil endpoint
    tohle pole vubec nezpracovava.
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_customers WHERE id=%s", (customer_id,))
            existing = cur.fetchone()
            if not existing:
                conn.rollback()
                return jsonify({"error": "Zákazník neexistuje."}), 404

            merged_body = _merge_body_with_existing(body, existing)
            clean, err = _validate_and_clean(merged_body, existing_email_fallback=existing["email"], raw_body=body)
            if err:
                conn.rollback()
                return jsonify({"error": err}), 400

            group_id = existing["group_id"]
            if "group_id" in body:
                group_id = body.get("group_id")
                if group_id is not None:
                    try:
                        group_id = int(group_id)
                    except (TypeError, ValueError):
                        conn.rollback()
                        return jsonify({"error": "Neplatné group_id."}), 400
                    cur.execute("SELECT id FROM shop_customer_groups WHERE id=%s", (group_id,))
                    if not cur.fetchone():
                        conn.rollback()
                        return jsonify({"error": "Zvolená skupina zákazníků neexistuje."}), 400

            # Dealerska sleva (Robert 2026-08-08: "pouze pro admina") -
            # schvaleni dealerskeho statusu je vyhradne admin akce, stejne
            # jako group_id vyse - vynuceno explicitne (ne jen spolehnuti
            # na "zakaznici"/"upravit" opravneni, ktere muze mit i
            # nesadmin role).
            is_dealer_approved = bool(existing.get("is_dealer_approved"))
            if "is_dealer_approved" in body:
                if admin["role"] != "admin":
                    conn.rollback()
                    return jsonify({"error": "Schválení dealerské slevy smí měnit jen administrátor."}), 403
                is_dealer_approved = bool(body["is_dealer_approved"])

            set_sql, values = _customer_set_clause(clean)
            cur.execute(
                f"UPDATE shop_customers SET {set_sql}, group_id=%s, is_dealer_approved=%s WHERE id=%s",
                values + (group_id, is_dealer_approved, customer_id),
            )
        conn.commit()
    finally:
        conn.close()

    log_audit(admin["id"], "update", "customer", customer_id, "Admin úprava profilu zákazníka.")
    return jsonify({"status": "ok"})


# ==================== ADRESAR (vicero dodacich adres) ====================
# Robert pres bot3, 2026-09-29: "u zakazniku potrebujeme mit moznost
# vicero dodacich adres, asi na zalozky." Viz _sync_default_address
# vyse pro zduvodneni, proc shop_customers.delivery_* zustava
# nedotcene (zpetna kompatibilita se vsemi existujicimi cteni).

@app.post("/api/admin/customers/<int:customer_id>/addresses")
@require_permission("zakaznici", "vytvorit")
def admin_customer_addresses_create(customer_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    label = (body.get("label") or "").strip()
    if not label:
        return jsonify({"error": "Chybí název adresy (např. „Sklad Praha“)."}), 400
    street = (body.get("street") or "").strip() or None
    city = (body.get("city") or "").strip() or None
    zip_code, err = _parse_zip(body.get("zip"), "adresy")
    if err:
        return jsonify({"error": err}), 400
    is_default = bool(body.get("is_default"))

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_customers WHERE id=%s", (customer_id,))
            if not cur.fetchone():
                conn.rollback()
                return jsonify({"error": "Zákazník neexistuje."}), 404
            cur.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n, COUNT(*) AS c "
                "FROM shop_customer_addresses WHERE customer_id=%s", (customer_id,),
            )
            agg = cur.fetchone()
            sort_order = agg["n"]
            # Prvni adresa zakaznika je vzdy vychozi - jinak by adresar
            # mohl skoncit bez jedine vychozi adresy.
            if agg["c"] == 0:
                is_default = True
            if is_default:
                cur.execute("UPDATE shop_customer_addresses SET is_default=0 WHERE customer_id=%s", (customer_id,))
            cur.execute(
                "INSERT INTO shop_customer_addresses (customer_id, label, street, city, zip, is_default, sort_order) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (customer_id, label, street, city, zip_code, is_default, sort_order),
            )
            new_id = cur.lastrowid
            if is_default:
                _sync_default_address(cur, customer_id)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "customer_address", new_id, f"{label} (zákazník #{customer_id})")
    return jsonify({"status": "ok", "id": new_id}), 201


@app.put("/api/admin/customers/addresses/<int:address_id>")
@require_permission("zakaznici", "upravit")
def admin_customer_addresses_update(address_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_customer_addresses WHERE id=%s", (address_id,))
            existing = cur.fetchone()
            if not existing:
                conn.rollback()
                return jsonify({"error": "Adresa neexistuje."}), 404
            customer_id = existing["customer_id"]
            label = ((body.get("label") if "label" in body else existing["label"]) or "").strip()
            if not label:
                conn.rollback()
                return jsonify({"error": "Chybí název adresy."}), 400
            street = (body.get("street") if "street" in body else existing["street"])
            street = street.strip() if isinstance(street, str) else street
            street = street or None
            city = (body.get("city") if "city" in body else existing["city"])
            city = city.strip() if isinstance(city, str) else city
            city = city or None
            if "zip" in body:
                zip_code, err = _parse_zip(body.get("zip"), "adresy")
                if err:
                    conn.rollback()
                    return jsonify({"error": err}), 400
            else:
                zip_code = existing["zip"]
            is_default = bool(body["is_default"]) if "is_default" in body else bool(existing["is_default"])
            if is_default:
                cur.execute(
                    "UPDATE shop_customer_addresses SET is_default=0 WHERE customer_id=%s AND id<>%s",
                    (customer_id, address_id),
                )
            cur.execute(
                "UPDATE shop_customer_addresses SET label=%s, street=%s, city=%s, zip=%s, is_default=%s WHERE id=%s",
                (label, street, city, zip_code, is_default, address_id),
            )
            if is_default:
                _sync_default_address(cur, customer_id)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "customer_address", address_id, label)
    return jsonify({"status": "ok"})


@app.delete("/api/admin/customers/addresses/<int:address_id>")
@require_permission("zakaznici", "smazat")
def admin_customer_addresses_delete(address_id):
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_customer_addresses WHERE id=%s", (address_id,))
            existing = cur.fetchone()
            if not existing:
                conn.rollback()
                return jsonify({"error": "Adresa neexistuje."}), 404
            customer_id = existing["customer_id"]
            was_default = bool(existing["is_default"])
            cur.execute("DELETE FROM shop_customer_addresses WHERE id=%s", (address_id,))
            if was_default:
                # Vychozi adresa smazana - povysit dalsi zbyvajici (podle
                # poradi), at adresar (kdyz neni prazdny) vzdy ma presne
                # jednu vychozi adresu.
                cur.execute(
                    "SELECT id FROM shop_customer_addresses WHERE customer_id=%s ORDER BY sort_order, id LIMIT 1",
                    (customer_id,),
                )
                promote = cur.fetchone()
                if promote:
                    cur.execute("UPDATE shop_customer_addresses SET is_default=1 WHERE id=%s", (promote["id"],))
                    _sync_default_address(cur, customer_id)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "delete", "customer_address", address_id, existing["label"])
    return jsonify({"status": "ok"})


@app.delete("/api/admin/customers/<int:customer_id>")
@require_permission("zakaznici", "smazat")
def admin_customers_delete_one(customer_id):
    """
    Smazani JEDNOHO zakaznika (Robert 2026-07-25: "dej moznost smazat
    zakaznika po jednom" - doplnuje hromadne "Smazat vse"). Stejna
    mechanika jako hromadne mazani (DELETE z app_users, kaskadove smaze
    shop_customers + shop_cart_items, existujici objednavky si jen
    ztrati vazbu na ucet - ON DELETE SET NULL), jen bez confirm_count
    (jednotlivy zaznam neni tak rizikovy jako smazani vseho najednou,
    potvrzeni resi frontend pres confirm() dialog).
    """
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT sc.user_id, sc.full_name, sc.email, au.role "
                "FROM shop_customers sc JOIN app_users au ON au.id = sc.user_id WHERE sc.id=%s",
                (customer_id,),
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return jsonify({"error": "Zákazník neexistuje."}), 404
            # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02, zive overeno):
            # admin ucet (id=1) ma shop_customers radek (id=232) - bez tehle
            # kontroly by "zakaznici:smazat" pravo smazalo i staff/admin ucet.
            # Mazani zamestnaneckych uctu ma vlastni endpoint s vlastnimi
            # pojistkami (viz admin_users_delete v app.py).
            if row["role"] != "user":
                conn.rollback()
                return jsonify({"error": "Účet zaměstnance se maže v Uživatelích."}), 400
            try:
                cur.execute("DELETE FROM app_users WHERE id=%s", (row["user_id"],))
            except pymysql.err.IntegrityError:
                conn.rollback()
                return jsonify({"error": "Zákazníka nelze smazat - má navázané záznamy, které brání smazání."}), 409
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "delete", "customer", customer_id,
              f"Smazán zákazník: {row['full_name']} ({row['email']}).")
    return jsonify({"status": "ok"})


@app.delete("/api/admin/customers")
@require_permission("zakaznici", "smazat")
def admin_customers_delete_all():
    """
    Hromadne smazani VSECH zakaznickych profilu + uctu najednou (Robert
    2026-07-25: "potřebujeme tlačítka v zakaznikách: smazat vše" -
    explicitne potvrzeno, ze cilem jsou samotni zakaznici/profily, ne
    kosiky ani skupiny). NEVRATNA akce nad realnymi importovanymi zaznamy
    (customers.xml import, viz AGENTS_LOG "bot3 - import zakazniku") -
    proto vyzaduje "confirm_count" presne odpovidajici AKTUALNIMU poctu
    zakazniku (ochrana proti nechtenemu/naskriptovanemu volani a proti
    race podmince, kdy mezitim pribyl/ubyl zakaznik).

    Mazani probiha DELETE z app_users (jen ucty, ktere maji profil v
    shop_customers) - kaskadove s sebou smaze i shop_customers a
    shop_cart_items (ON DELETE CASCADE, viz fk_shop_customers_user /
    fk_shop_cart_items_user). Existujici objednavky (shop_orders) se
    NEMAZOU, jen se jim user_id nastavi na NULL (ON DELETE SET NULL,
    fk_shop_orders_user) - historie objednavek zustava zachovana, jen
    ztrati vazbu na (smazany) ucet.

    Ocekavany JSON payload: {"confirm_count": <aktualni pocet zakazniku>}
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # role='user' (bezpecnostni nalez, bot3/revize kodu 2026-09-02,
            # zive overeno: admin ucet id=1 ma shop_customers radek) - staff
            # ucty se do "Smazat vse" vubec nepocitaji/nemazou.
            cur.execute(
                "SELECT u.id FROM app_users u JOIN shop_customers c ON c.user_id = u.id WHERE u.role='user'"
            )
            user_ids = [r["id"] for r in cur.fetchall()]
            actual_count = len(user_ids)

            try:
                confirm_count = int(body.get("confirm_count"))
            except (TypeError, ValueError):
                conn.rollback()
                return jsonify({"error": "Chybí potvrzení počtu.", "current_count": actual_count}), 400

            if confirm_count != actual_count:
                conn.rollback()
                return jsonify({
                    "error": f"Potvrzený počet ({confirm_count}) neodpovídá aktuálnímu počtu "
                             f"zákazníků ({actual_count}). Zkuste to prosím znovu.",
                    "current_count": actual_count,
                }), 409

            if actual_count == 0:
                conn.rollback()
                return jsonify({"status": "ok", "deleted": 0})

            placeholders = ",".join(["%s"] * len(user_ids))
            try:
                cur.execute(f"DELETE FROM app_users WHERE id IN ({placeholders})", user_ids)
            except pymysql.err.IntegrityError:
                conn.rollback()
                return jsonify({"error": "Někteří zákazníci mají navázané záznamy, které brání smazání."}), 409
            deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    log_audit(admin["id"], "delete_all", "customer", None,
              f"Hromadně smazáno {deleted} zákazníků (účty + profily).")
    return jsonify({"status": "ok", "deleted": deleted})


# V11 (bot3, 2026-07-26, viz NAVRH_HROMADNE_AKCE.md) - hromadne akce nad
# VYBRANOU podmnozinou zakazniku (doplnuje "smazat vse" nad, ktere je
# jiny use-case s confirm_count pojistkou). Stejna mechanika mazani jako
# admin_customers_delete_one/delete_all - DELETE z app_users (kaskadove
# smaze shop_customers/shop_cart_items, objednavky ztrati jen vazbu -
# ON DELETE SET NULL), "id" v requestu = shop_customers.id (stejne jako
# v URL radkove akce), ne app_users.id.
@app.delete("/api/admin/customers/bulk")
@require_permission("zakaznici", "smazat")
def admin_customers_bulk_delete():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(
                f"SELECT sc.id, sc.user_id, sc.full_name, sc.email, au.role "
                f"FROM shop_customers sc JOIN app_users au ON au.id = sc.user_id WHERE sc.id IN ({placeholders})",
                ids,
            )
            rows = cur.fetchall()
            # role='user' (bezpecnostni nalez, bot3/revize kodu 2026-09-02) -
            # staff ucet napojeny na shop_customers se z davky vynecha, ne
            # celou davku shodi.
            staff_rows = [r for r in rows if r["role"] != "user"]
            user_ids = [r["user_id"] for r in rows if r["role"] == "user"]
            deleted = 0
            if user_ids:
                up = ",".join(["%s"] * len(user_ids))
                try:
                    cur.execute(f"DELETE FROM app_users WHERE id IN ({up})", user_ids)
                except pymysql.err.IntegrityError:
                    conn.rollback()
                    return jsonify({"error": "Někteří zákazníci mají navázané záznamy, které brání smazání."}), 409
                deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    found_ids = {r["id"] for r in rows}
    missing = [i for i in ids if i not in found_ids]
    failed = [{"id": i, "error": "Zákazník neexistuje."} for i in missing] + [
        {"id": r["id"], "error": "Účet zaměstnance se maže v Uživatelích."} for r in staff_rows
    ]
    log_audit(admin["id"], "bulk_delete", "customer", None,
              f"{deleted} zákazníků smazáno" + (f", {len(failed)} přeskočeno" if failed else ""))
    return jsonify({"status": "ok", "deleted": deleted, "failed": failed})


@app.post("/api/admin/customers/bulk-group")
@require_permission("zakaznici", "upravit")
def admin_customers_bulk_group():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    if "group_id" not in body:
        return jsonify({"error": "Chybí group_id."}), 400
    group_id = body.get("group_id")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if group_id is not None:
                try:
                    group_id = int(group_id)
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné group_id."}), 400
                cur.execute("SELECT id FROM shop_customer_groups WHERE id=%s", (group_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Skupina neexistuje."}), 400
            updated = bulk_update_fields(cur, "shop_customers", ids, {"group_id": group_id})
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "bulk_update", "customer", None,
              f"{updated} zákazníků -> skupina {group_id}")
    return jsonify({"status": "ok", "updated": updated})


# ---------------------------------------------------------------------------
# V8 (bot3, 2026-07-25): hlidani duplicit vracejicich se zakazniku.
# Robert: "dále je potřeba hlídat duplicity když klient už nakoupil v
# minulosti." Rozhodnuto (AskUserQuestion): hledat podle e-mailu A ICO,
# system ma AUTOMATICKY NABIDNOUT propojeni (ne tise auto-propojit).
#
# Tenhle endpoint je zamysleny pro 2 pouziti:
#   1) bot2 admin UI ho muze volat ZIVE, jak admin pise kontakt do
#      formulare rucniho zadani objednavky (POST /api/admin/orders) -
#      "tenhle e-mail/ICO uz mame, chcete propojit na existujici ucet?"
#   2) admin_orders_create() NIZE ho vola AUTOMATICKY sam, kdyz admin
#      vytvori objednavku BEZ user_id, ale s e-mailem/ICO - vysledek se
#      vraci v odpovedi jako "duplicate_suggestions", takze upozorneni
#      dostane i admin, ktery pred vytvorenim objednavky nekontroloval.
# ---------------------------------------------------------------------------

def _normalize_phone_last9(phone):
    """Posledni 9 cislic telefonu (bez mezer/pomlcek/predvolby +420) -
    Robert 2026-08-22 ("jméno + telefon" jako kriterium pro soukrome
    osoby bez ICO): telefony jsou v DB ulozene v ruznych formatech
    ('+420 777 000 111' i '777828628', viz zive overeno v produkci) -
    presny retezcovy match by casto minul stejne cislo jen kvuli
    formatovani. Ceska cisla (mobil i pevna linka) maji vzdy 9 cislic,
    posledních 9 je tedy spolehlivy normalizovany klic bez ohledu na
    pritomnost/formu predvolby. Vraci None, kdyz po ocisteni zbyde
    min nez 9 cislic (nejde spolehlive normalizovat)."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else None


def find_duplicate_customers(cur, email=None, ico=None, dic=None, full_name=None, phone=None):
    """Vraci seznam existujicich zakaznickych uctu, ktere se shoduji podle
    e-mailu, ICO/DIC (firmy), nebo jmena+telefonu (soukrome osoby bez ICO -
    Robert 2026-08-22, potvrzeno: "jméno + telefon"). E-mail se hleda jak
    v prihlasovacim uctu (app_users.email - VZDY unikatni), tak v
    kontaktnim e-mailu profilu (shop_customers.email - muze se od
    prihlasovaciho lisit, napr. kdyz admin zada objednavku na jiny
    kontaktni e-mail nez je login). ICO/DIC/jmeno+telefon NEJSOU unique
    (firma muze mit vic kontaktnich osob/uctu, jmeno+telefon je jen
    pravdepodobnostni shoda) - vsechna kriteria se kombinuji aditivne
    (OR mezi kriterii), `matched_by` u kazdeho vysledku rika, ktera
    presne sedela. Pouziva se z endpointu find-duplicates NIZE, primo z
    orders.py::admin_orders_create, i z crm.py::crm_admin_lead_convert
    (tam navic s dic/full_name/phone vytazenymi z podpisu e-mailu,
    _extract_signature_fields)."""
    matches = {}
    email = (email or "").strip().lower()
    ico = (ico or "").strip()
    dic = (dic or "").strip()
    full_name = (full_name or "").strip()
    phone_norm = _normalize_phone_last9(phone)

    def _merge(rows, criterion):
        for row in rows:
            if row["customer_id"] in matches:
                matches[row["customer_id"]]["matched_by"].append(criterion)
            else:
                matches[row["customer_id"]] = {**row, "matched_by": [criterion]}

    _SELECT_BASE = (
        "SELECT c.id AS customer_id, c.full_name, c.company_name, c.email, c.ico, c.dic, c.phone, "
        "       u.id AS user_id, u.email AS account_email "
        "FROM shop_customers c JOIN app_users u ON u.id = c.user_id "
    )

    if email:
        cur.execute(_SELECT_BASE + "WHERE LOWER(u.email) = %s OR LOWER(c.email) = %s", (email, email))
        _merge(cur.fetchall(), "email")

    if ico:
        cur.execute(_SELECT_BASE + "WHERE c.ico = %s", (ico,))
        _merge(cur.fetchall(), "ico")

    if dic:
        cur.execute(_SELECT_BASE + "WHERE c.dic = %s", (dic,))
        _merge(cur.fetchall(), "dic")

    # jmeno+telefon - jen kdyz mame OBOJI (samotne jmeno je moc slaby
    # signal - bezna jmena se opakuji; samotny telefon bez jmena uz
    # pokryva pripad vyse, kdyby se nekdy pridal telefon jako
    # samostatne kriterium). RIGHT(REPLACE...) v SQL normalizuje
    # ulozeny telefon stejne jako _normalize_phone_last9() vyse.
    if full_name and phone_norm:
        cur.execute(
            _SELECT_BASE + "WHERE LOWER(c.full_name) = %s "
            "AND RIGHT(REPLACE(REPLACE(REPLACE(c.phone,' ',''),'-',''),'+',''), 9) = %s",
            (full_name.lower(), phone_norm),
        )
        _merge(cur.fetchall(), "name_phone")

    return list(matches.values())


@app.get("/api/admin/customers/find-duplicates")
@require_permission("zakaznici", "zobrazit")
def admin_customers_find_duplicates():
    """?email=...&ico=...&dic=...&full_name=...&phone=... (alespoň jedno
    z nich) - viz find_duplicate_customers()."""
    email = request.args.get("email")
    ico = request.args.get("ico")
    dic = request.args.get("dic")
    full_name = request.args.get("full_name")
    phone = request.args.get("phone")
    if not any((v or "").strip() for v in (email, ico, dic, full_name, phone)):
        return jsonify({"error": "Zadejte alespoň email, ico, dic, nebo full_name+phone."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            matches = find_duplicate_customers(cur, email=email, ico=ico, dic=dic, full_name=full_name, phone=phone)
    finally:
        conn.close()
    return jsonify({"matches": matches})


# ---------------------------------------------------------------------------
# Skupiny zakazniku (ramcova sleva) - admin CRUD
# ---------------------------------------------------------------------------

@app.get("/api/admin/customer-groups")
@require_permission("zakaznici", "zobrazit")
def admin_customer_groups_list():
    # Robert 2026-08-01: "chceme ukazovat veškeré možné archivní věci
    # položky" - stejny vzor jako shop_suppliers (purchase_orders.py).
    show_archived = request.args.get("archived") == "1"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM shop_customer_groups WHERE active=%s ORDER BY sort_order, name",
                (0 if show_archived else 1,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"groups": [_serialize_group(r) for r in rows]})


@app.post("/api/admin/customer-groups")
@require_permission("zakaznici", "vytvorit")
def admin_customer_groups_create():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Chybí název skupiny."}), 400
    try:
        discount = float(body.get("discount_percent") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatná sleva."}), 400
    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): bez tehle
    # kontroly slo zadat treba 150 % - efektivni cena by pak vysla
    # zaporna (products.py::_effective_unit_price).
    if not (0 <= discount <= 100):
        return jsonify({"error": "Sleva musí být mezi 0 a 100 %."}), 400
    note = (body.get("note") or "").strip() or None
    sort_order = int(body.get("sort_order") or 0)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shop_customer_groups (name, discount_percent, note, active, sort_order) "
                "VALUES (%s,%s,%s,1,%s)",
                (name, discount, note, sort_order),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "customer_group", new_id, f"{name} ({discount} %)")
    return jsonify({"status": "ok", "id": new_id})


@app.put("/api/admin/customer-groups/<int:group_id>")
@require_permission("zakaznici", "upravit")
def admin_customer_groups_update(group_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        fields.append("name=%s"); params.append((body.get("name") or "").strip())
    if "discount_percent" in body:
        try:
            discount = float(body.get("discount_percent") or 0)
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatná sleva."}), 400
        # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02) - stejna
        # kontrola jako admin_customer_groups_create.
        if not (0 <= discount <= 100):
            return jsonify({"error": "Sleva musí být mezi 0 a 100 %."}), 400
        fields.append("discount_percent=%s"); params.append(discount)
    if "note" in body:
        fields.append("note=%s"); params.append((body.get("note") or "").strip() or None)
    if "active" in body:
        fields.append("active=%s"); params.append(1 if body.get("active") else 0)
    if "sort_order" in body:
        fields.append("sort_order=%s"); params.append(int(body.get("sort_order") or 0))
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(group_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE shop_customer_groups SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "customer_group", group_id, None)
    return jsonify({"status": "ok"})


@app.delete("/api/admin/customer-groups/<int:group_id>")
@require_permission("zakaznici", "smazat")
def admin_customer_groups_delete(group_id):
    """Smazani skupiny NIC nesmaze u zakazniku, jen jim odpojí group_id
    (ON DELETE SET NULL - viz migrace)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shop_customer_groups WHERE id=%s", (group_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "delete", "customer_group", group_id, None)
    return jsonify({"status": "ok"})


@app.post("/api/admin/customer-groups/bulk-delete")
@require_permission("zakaznici", "smazat")
def admin_customer_groups_bulk_delete():
    """Hromadne smazani skupin - stejne jako radkove mazani, zakaznici
    jen ztrati group_id (ON DELETE SET NULL), zadne dalsi vedlejsi
    ucinky (Robert: "mazat musí být všude !!!")."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deleted = bulk_delete(cur, "shop_customer_groups", ids)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "bulk_delete", "customer_group", None, f"{deleted} skupin smazáno")
    return jsonify({"status": "ok", "deleted": deleted})


@app.post("/api/admin/customer-groups/bulk-active")
@require_permission("zakaznici", "upravit")
def admin_customer_groups_bulk_active():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    if "active" not in body:
        return jsonify({"error": "Chybí pole active."}), 400
    active = 1 if body.get("active") else 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            updated = bulk_update_fields(cur, "shop_customer_groups", ids, {"active": active})
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "bulk_active", "customer_group", None,
              f"{updated} skupin -> active={active}")
    return jsonify({"status": "ok", "updated": updated})
