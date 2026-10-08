"""Mini-shop, FAZE 1b: import textu jako DRAFT a klikaci schvalovani (bot5, 2026-10-02; schvalil bot3: "import anglickych textu od bot7 jako draft + schvaleni Robertem v adminu, jednoduche klikaci
schvaleni, ať to zvladne z mobilu. Do schvaleni API verejne nic neukazuje").

  import_catalog(cur, data, apply, revise_approved, update_catalog)   nacte JSON (kategorie, produkty a jejich texty v JEDNOM jazyce) do miniweb_* jako DRAFT. Nikdy nezapisuje 'approved'.
      Schvaleny text se neprepise (vyjimka revise_approved: text se prepise a vrati do draft, verejne zmizi do dalsiho schvaleni). Cely soubor se nejdriv zvaliduje a pri jedine chybe se
      nezapise NIC. Bez apply je to jen nahled (co by se stalo). CLI: scripts/miniweb_import.py.
  GET  /api/admin/miniweb/overview    co ceka na schvaleni, tak jak to uvidi zakaznik (cisty text), s priznakem problemu a "bude verejne" + pocty a shopy
  POST /api/admin/miniweb/approve     schvali vybrane navrhy. Kazda polozka nese rev = otisk obsahu, ktery admin videl: kdyz se text mezitim zmenil (import), NESCHVALI se (co je schvaleno, to je to, co se videlo)
  POST /api/admin/miniweb/unapprove   vrati schvalene do draft
JEN admin (role admin). Schvaleni shop NEZVEREJNUJE: verejnosti se schvaleny text ukaze az kdyz je storefront shopu ve stavu live (zmena stavu je zamerne oddelena a jinde).
Texty se ukladaji uz OCISTENE (stejnou funkci jako vydava verejne API), takze schvaluje se presne to, co se zobrazi. Znacka/dodavatel a prazdny nazev text zablokuje (nejde schvalit ani importovat).

Format importu (version 1), jeden soubor = jedna rodina a jeden jazyk:
  {"version": 1, "family": "packstations", "lang": "en",
   "categories": [{"slug": "tables", "parent": null, "sort": 1, "name": "Tables"}],
   "products": [{"slug": "packing-station-ps120", "sku": "PS-120", "category": "tables", "sort": 1,
                 "configurator": {"available": true, "shop_product_id": 1234, "default_view": "configurator"},
                 "name": "...", "summary": "...", "description": "...", "delivery": "...", "specs": [{"name": "Width", "value": "1200 mm"}]}]}
Katalogova data (rodic, poradi, kod, kategorie, konfigurator) u UZ existujici polozky import nemeni (jen hlasi rozdil), meni je az update_catalog. Neznamy klic = chyba (preklep nesmi tise zahodit data).
"""
import hashlib
import json
import re

from flask import request, jsonify

import dealers
import miniweb
from app import app, get_conn, admin_required, current_user, log_audit

_FAMILY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}\Z")
_CAT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}\Z")
_PROD_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}\Z")
_SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,49}\Z")
_VIEW_RE = re.compile(r"^[a-z0-9_-]{1,20}\Z")
MAX_CATEGORIES = 500
MAX_PRODUCTS = 2000
MAX_APPROVE_ITEMS = 300
LIMITS = {"name": 200, "summary": 500, "description": 4000, "delivery": 255}
TOP_KEYS = {"version", "family", "lang", "categories", "products"}
CAT_KEYS = {"slug", "parent", "sort", "name"}
PROD_KEYS = {"slug", "sku", "category", "sort", "configurator", "name", "summary", "description", "delivery", "specs"}
CONF_KEYS = {"available", "shop_product_id", "default_view"}


# ---------------------------------------------------------------------------------------------------------------- spolecne
def text_rev(name, summary, description, delivery, specs):
    """Otisk obsahu textu (uz ocisteneho): co admin videl, to schvaluje, zmena kterehokoli pole zmeni otisk."""
    blob = json.dumps([name or "", summary or "", description or "", delivery or "", specs or []], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def _clean_product_text(t):
    return {"name": miniweb._plain(t["name"], LIMITS["name"]), "summary": miniweb._plain(t["summary"], LIMITS["summary"]),
            "description": miniweb._plain(t["description"], LIMITS["description"], multiline=True), "delivery": miniweb._plain(t["delivery"], LIMITS["delivery"]), "specs": miniweb._specs(t["specs_json"])}


def _problems(clean, slug, sku, raw_changed):
    """(blokujici, informativni) seznamy kodu problemu. Blokujici = nejde schvalit."""
    blocking, info = [], []
    texts = [clean["name"], clean["summary"], clean["description"], clean["delivery"], slug, sku] + [x for s in clean["specs"] for x in (s["name"], s["value"])]
    if dealers._brand_hit(*texts):
        blocking.append("brand")
    if not clean["name"]:
        blocking.append("no_name")
    if sku is not None and not clean["description"]:
        info.append("no_description")
    if raw_changed:
        info.append("cleaned")
    return blocking, info


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if value is not None else None


# ---------------------------------------------------------------------------------------------------------------- import
def _new_report():
    return {"errors": [], "warnings": [], "applied": False,
            "categories": {"created": 0, "unchanged": 0, "differs": 0, "updated": 0},
            "products": {"created": 0, "unchanged": 0, "differs": 0, "updated": 0},
            "texts": {"created": 0, "updated": 0, "unchanged": 0, "skipped_approved": 0, "revised": 0}}


def _field(report, where, entry, key, required=False, multiline=False):
    """Ocisteny textovy udaj z polozky souboru, nebo None. Chyby: neni retezec, prazdny povinny, delsi nez limit, znacka/dodavatel."""
    raw = entry.get(key)
    if raw is None or raw == "":
        if required:
            report["errors"].append(f"{where}: chybí povinné pole '{key}'")
        return ""
    if not isinstance(raw, str):
        report["errors"].append(f"{where}: pole '{key}' musí být text")
        return ""
    limit = LIMITS[key]
    cleaned = miniweb._plain(raw, 10 ** 6, multiline=multiline)
    if len(cleaned) > limit:
        report["errors"].append(f"{where}: pole '{key}' má po vyčištění {len(cleaned)} znaků, limit je {limit}")
    if required and not cleaned:
        report["errors"].append(f"{where}: pole '{key}' je po vyčištění prázdné")
    if dealers._brand_hit(cleaned):
        report["errors"].append(f"{where}: pole '{key}' zmiňuje značku/dodavatele (pravidlo 5), opravit u zdroje")
    return cleaned[:limit]


def _int(report, where, entry, key, default=0, lo=-10000, hi=10000):
    v = entry.get(key, default)
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        report["errors"].append(f"{where}: pole '{key}' musí být celé číslo {lo} až {hi}")
        return default
    return v


def _unknown(report, where, entry, allowed):
    extra = sorted(set(entry) - allowed)
    if extra:
        report["errors"].append(f"{where}: neznámé klíče {extra} (preklep? povolené: {sorted(allowed)})")


def _parse(data, report):
    """Strukturalni validace souboru bez databaze -> {"family", "lang", "categories": [...], "products": [...]} (cisty), chyby do reportu."""
    if not isinstance(data, dict):
        report["errors"].append("soubor musí být JSON objekt")
        return None
    _unknown(report, "soubor", data, TOP_KEYS)
    if data.get("version") != 1:
        report["errors"].append("soubor: version musí být 1")
    family = data.get("family")
    if not isinstance(family, str) or not _FAMILY_RE.match(family):
        report["errors"].append("soubor: family musí být malá písmena, číslice a pomlčky (např. packstations)")
    lang = miniweb._clean_lang(data.get("lang")) if isinstance(data.get("lang"), str) else None
    if not lang or lang != data.get("lang"):
        report["errors"].append("soubor: lang musí být kód jazyka malými písmeny (en, de, en-ie)")
    cats_raw, prods_raw = data.get("categories", []), data.get("products", [])
    if not isinstance(cats_raw, list) or not isinstance(prods_raw, list) or len(cats_raw) > MAX_CATEGORIES or len(prods_raw) > MAX_PRODUCTS:
        report["errors"].append(f"soubor: categories a products musí být seznamy (max {MAX_CATEGORIES} a {MAX_PRODUCTS})")
        return None
    cats, seen = [], set()
    for i, c in enumerate(cats_raw):
        where = f"kategorie[{i}]"
        if not isinstance(c, dict):
            report["errors"].append(f"{where}: musí být objekt")
            continue
        _unknown(report, where, c, CAT_KEYS)
        slug = c.get("slug")
        if not isinstance(slug, str) or not _CAT_SLUG_RE.match(slug) or dealers._brand_hit(slug):
            report["errors"].append(f"{where}: slug musí být malá písmena, číslice a pomlčky bez značky")
            continue
        where = f"kategorie '{slug}'"
        if slug in seen:
            report["errors"].append(f"{where}: slug je v souboru dvakrát")
        seen.add(slug)
        parent = c.get("parent")
        if parent is not None and (not isinstance(parent, str) or not _CAT_SLUG_RE.match(parent)):
            report["errors"].append(f"{where}: parent musí být slug nadřazené kategorie nebo null")
            parent = None
        cats.append({"slug": slug, "parent": parent, "sort": _int(report, where, c, "sort"), "name": _field(report, where, c, "name", required=True)})
    prods, seen_slug, seen_sku = [], set(), set()
    for i, p in enumerate(prods_raw):
        where = f"produkt[{i}]"
        if not isinstance(p, dict):
            report["errors"].append(f"{where}: musí být objekt")
            continue
        _unknown(report, where, p, PROD_KEYS)
        slug, sku = p.get("slug"), p.get("sku")
        if not isinstance(slug, str) or not _PROD_SLUG_RE.match(slug) or dealers._brand_hit(slug):
            report["errors"].append(f"{where}: slug musí být malá písmena, číslice a pomlčky bez značky")
            continue
        where = f"produkt '{slug}'"
        if not isinstance(sku, str) or not _SKU_RE.match(sku) or dealers._brand_hit(sku):
            report["errors"].append(f"{where}: sku (veřejný kód) musí být písmena, číslice, tečka, pomlčka nebo podtržítko bez značky")
            sku = None
        if slug in seen_slug:
            report["errors"].append(f"{where}: slug je v souboru dvakrát")
        if sku and sku in seen_sku:
            report["errors"].append(f"{where}: sku '{sku}' je v souboru dvakrát")
        seen_slug.add(slug)
        seen_sku.add(sku)
        if not isinstance(p.get("category"), str) or not _CAT_SLUG_RE.match(p.get("category") or ""):
            report["errors"].append(f"{where}: category musí být slug kategorie")
        conf = p.get("configurator")
        conf_clean = {"available": False, "shop_product_id": None, "default_view": "configurator"}
        if conf is not None:
            if not isinstance(conf, dict):
                report["errors"].append(f"{where}: configurator musí být objekt")
            else:
                _unknown(report, f"{where}.configurator", conf, CONF_KEYS)
                avail = conf.get("available", False)
                sp = conf.get("shop_product_id")
                view = conf.get("default_view", "configurator")
                if not isinstance(avail, bool) or (sp is not None and (isinstance(sp, bool) or not isinstance(sp, int) or sp <= 0)) or not isinstance(view, str) or not _VIEW_RE.match(view):
                    report["errors"].append(f"{where}: configurator má neplatné available, shop_product_id nebo default_view")
                elif avail and sp is None:
                    report["errors"].append(f"{where}: configurator.available vyžaduje shop_product_id (karta sestavy)")
                else:
                    conf_clean = {"available": avail, "shop_product_id": sp, "default_view": view}
        specs, raw_specs = [], p.get("specs", [])
        if not isinstance(raw_specs, list) or len(raw_specs) > 40:
            report["errors"].append(f"{where}: specs musí být seznam (max 40) objektů name a value")
            raw_specs = []
        for j, s in enumerate(raw_specs):
            if not isinstance(s, dict) or set(s) - {"name", "value"} or not isinstance(s.get("name"), str) or not isinstance(s.get("value"), str):
                report["errors"].append(f"{where}: specs[{j}] musí být objekt jen s texty name a value")
                continue
            n, v = miniweb._plain(s["name"], 10 ** 5), miniweb._plain(s["value"], 10 ** 5)
            if not n or not v or len(n) > 120 or len(v) > 300:
                report["errors"].append(f"{where}: specs[{j}] má prázdný nebo příliš dlouhý název (120) či hodnotu (300)")
            elif dealers._brand_hit(n, v):
                report["errors"].append(f"{where}: specs[{j}] zmiňuje značku/dodavatele (pravidlo 5)")
            else:
                specs.append({"name": n, "value": v})
        prods.append({"slug": slug, "sku": sku, "category": p.get("category"), "sort": _int(report, where, p, "sort"), "configurator": conf_clean, "name": _field(report, where, p, "name", required=True),
                      "summary": _field(report, where, p, "summary"), "description": _field(report, where, p, "description", multiline=True), "delivery": _field(report, where, p, "delivery"), "specs": specs})
    return {"family": family, "lang": lang, "categories": cats, "products": prods}


def _same_text(row, new):
    cur_clean = _clean_product_text(row) if "specs_json" in row else {"name": miniweb._plain(row["name"], LIMITS["name"]), "summary": "", "description": "", "delivery": "", "specs": []}
    return text_rev(cur_clean["name"], cur_clean["summary"], cur_clean["description"], cur_clean["delivery"], cur_clean["specs"]) == text_rev(new["name"], new.get("summary", ""), new.get("description", ""), new.get("delivery", ""), new.get("specs", []))


def import_catalog(cur, data, apply=False, revise_approved=False, update_catalog=False):
    """Viz hlavicka modulu. Vraci report (dict). Zapisuje JEN kdyz apply a bez chyb, v transakci volajiciho (volajici commitne)."""
    report = _new_report()
    parsed = _parse(data, report)
    if parsed is None or report["errors"]:
        return report
    family, lang = parsed["family"], parsed["lang"]

    cur.execute("SELECT id, parent_id, slug, sort_order FROM miniweb_categories WHERE family=%s", (family,))
    db_cats = {r["slug"]: r for r in cur.fetchall()}
    db_cat_by_id = {r["id"]: r for r in db_cats.values()}
    file_cats = {c["slug"]: c for c in parsed["categories"]}

    # --- kategorie: rodic musi existovat (v souboru nebo v DB teze rodiny), zadne cykly (efektivni rodic = ze souboru u nove nebo pri update_catalog, jinak z DB)
    eff = {s: (db_cat_by_id[r["parent_id"]]["slug"] if r["parent_id"] in db_cat_by_id else None) for s, r in db_cats.items()}
    for s, c in file_cats.items():
        if s not in db_cats or update_catalog:
            eff[s] = c["parent"]
    for c in parsed["categories"]:
        if c["parent"] and c["parent"] not in file_cats and c["parent"] not in db_cats:
            report["errors"].append(f"kategorie '{c['slug']}': nadřazená kategorie '{c['parent']}' neexistuje (ani v souboru, ani v rodině {family})")
        walk, hops = eff.get(c["slug"]), 0
        while walk is not None and hops < 1000:
            if walk == c["slug"]:
                report["errors"].append(f"kategorie '{c['slug']}': cyklus v nadřazených kategoriích")
                break
            walk, hops = eff.get(walk), hops + 1
    # --- produkty: kategorie existuje, slug a sku nepatri jinemu produktu, karta sestavy existuje
    cur.execute("SELECT p.id, p.slug, p.public_sku, p.category_id, p.sort_order, p.shop_product_id, p.configurator_available, p.default_view, c.family, c.slug AS category_slug "
                "FROM miniweb_products p JOIN miniweb_categories c ON c.id = p.category_id")
    db_prods = {r["slug"]: r for r in cur.fetchall()}
    db_sku = {r["public_sku"]: r for r in db_prods.values()}
    for p in parsed["products"]:
        where = f"produkt '{p['slug']}'"
        if p["category"] not in file_cats and p["category"] not in db_cats:
            report["errors"].append(f"{where}: kategorie '{p['category']}' neexistuje (ani v souboru, ani v rodině {family})")
        ex = db_prods.get(p["slug"])
        if ex and ex["family"] != family:
            report["errors"].append(f"{where}: slug už patří produktu jiné rodiny ({ex['family']})")
        if p["sku"] and p["sku"] in db_sku and db_sku[p["sku"]]["slug"] != p["slug"]:
            report["errors"].append(f"{where}: sku '{p['sku']}' už má produkt '{db_sku[p['sku']]['slug']}'")
        sp = p["configurator"]["shop_product_id"]
        if sp is not None:
            cur.execute("SELECT id FROM shop_products WHERE id=%s", (sp,))
            if not cur.fetchone():
                report["errors"].append(f"{where}: karta sestavy shop_product_id {sp} neexistuje")
    if report["errors"]:
        return report

    # --- plan a zapis; kategorie od rodicu k potomkum
    cat_ids = {s: r["id"] for s, r in db_cats.items()}
    pending, guard = list(parsed["categories"]), 0
    order = []
    placed = set(db_cats)
    while pending and guard < 1000:
        guard += 1
        nxt = [c for c in pending if c["parent"] is None or c["parent"] in placed]
        if not nxt:
            break
        for c in nxt:
            order.append(c)
            placed.add(c["slug"])
            pending.remove(c)
    for c in order:
        ex = db_cats.get(c["slug"])
        want_parent = cat_ids.get(c["parent"]) if c["parent"] else None
        if ex is None:
            report["categories"]["created"] += 1
            if apply:
                cur.execute("INSERT INTO miniweb_categories (parent_id, family, slug, sort_order) VALUES (%s,%s,%s,%s)", (want_parent, family, c["slug"], c["sort"]))
                cat_ids[c["slug"]] = cur.lastrowid
            else:
                cat_ids[c["slug"]] = -len(cat_ids) - 1          # zastupne id v nahledu
        elif ex["parent_id"] == want_parent and ex["sort_order"] == c["sort"]:
            report["categories"]["unchanged"] += 1
        elif update_catalog:
            report["categories"]["updated"] += 1
            if apply:
                cur.execute("UPDATE miniweb_categories SET parent_id=%s, sort_order=%s WHERE id=%s", (want_parent, c["sort"], ex["id"]))
        else:
            report["categories"]["differs"] += 1
            report["warnings"].append(f"kategorie '{c['slug']}': katalogová data (nadřazená kategorie nebo pořadí) se liší od databáze, nezměněno (změní až update_catalog)")
        _upsert_text(cur, report, apply, revise_approved, "miniweb_category_texts", "miniweb_category_id", cat_ids[c["slug"]], lang,
                     {"name": c["name"], "summary": "", "description": "", "delivery": "", "specs": []}, f"kategorie '{c['slug']}'", is_product=False)
    for p in parsed["products"]:
        ex = db_prods.get(p["slug"])
        cat_id = cat_ids[p["category"]]
        conf = p["configurator"]
        if ex is None:
            report["products"]["created"] += 1
            if apply:
                cur.execute("INSERT INTO miniweb_products (category_id, slug, public_sku, shop_product_id, configurator_available, default_view, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (cat_id, p["slug"], p["sku"], conf["shop_product_id"], 1 if conf["available"] else 0, conf["default_view"], p["sort"]))
                pid = cur.lastrowid
            else:
                pid = -len(db_prods) - report["products"]["created"]
        else:
            pid = ex["id"]
            same = (ex["category_id"] == cat_id and ex["public_sku"] == p["sku"] and ex["sort_order"] == p["sort"] and ex["shop_product_id"] == conf["shop_product_id"]
                    and bool(ex["configurator_available"]) == conf["available"] and ex["default_view"] == conf["default_view"])
            if same:
                report["products"]["unchanged"] += 1
            elif update_catalog:
                report["products"]["updated"] += 1
                if apply:
                    cur.execute("UPDATE miniweb_products SET category_id=%s, public_sku=%s, shop_product_id=%s, configurator_available=%s, default_view=%s, sort_order=%s WHERE id=%s",
                                (cat_id, p["sku"], conf["shop_product_id"], 1 if conf["available"] else 0, conf["default_view"], p["sort"], pid))
            else:
                report["products"]["differs"] += 1
                report["warnings"].append(f"produkt '{p['slug']}': katalogová data (kategorie, kód, pořadí, konfigurátor) se liší od databáze, nezměněno (změní až update_catalog)")
        _upsert_text(cur, report, apply, revise_approved, "miniweb_product_texts", "miniweb_product_id", pid, lang, p, f"produkt '{p['slug']}'", is_product=True)
    report["applied"] = bool(apply)
    return report


def _upsert_text(cur, report, apply, revise_approved, table, idcol, item_id, lang, new, label, is_product):
    row = None
    if item_id > 0:                                      # zaporne id = nova polozka v nahledu (bez zapisu), text neexistuje
        cur.execute(f"SELECT * FROM {table} WHERE {idcol}=%s AND lang=%s", (item_id, lang))
        row = cur.fetchone()
    t = report["texts"]
    if row is None:
        t["created"] += 1
        if apply:
            _write_text(cur, table, idcol, item_id, lang, new, is_product, insert=True)
        return
    if _same_text(row, new):
        t["unchanged"] += 1
        return
    if row["status"] == "approved" and not revise_approved:
        t["skipped_approved"] += 1
        report["warnings"].append(f"{label} ({lang}): schválený text se liší od souboru, NEPŘEPSÁNO (přepsat a vrátit do návrhu jen s revise_approved)")
        return
    if row["status"] == "approved":
        t["revised"] += 1
    else:
        t["updated"] += 1
    if apply:
        _write_text(cur, table, idcol, item_id, lang, new, is_product, insert=False)


def _write_text(cur, table, idcol, item_id, lang, new, is_product, insert):
    if is_product:
        vals = (new["name"], new["summary"] or None, new["description"] or None, new["delivery"] or None, _json_text(new["specs"]) if new["specs"] else None)
        if insert:
            cur.execute(f"INSERT INTO {table} ({idcol}, lang, name, summary, description, delivery, specs_json, status) VALUES (%s,%s,%s,%s,%s,%s,%s,'draft')", (item_id, lang) + vals)
        else:
            cur.execute(f"UPDATE {table} SET name=%s, summary=%s, description=%s, delivery=%s, specs_json=%s, status='draft', approved_by=NULL, approved_at=NULL WHERE {idcol}=%s AND lang=%s", vals + (item_id, lang))
    elif insert:
        cur.execute(f"INSERT INTO {table} ({idcol}, lang, name, status) VALUES (%s,%s,%s,'draft')", (item_id, lang, new["name"]))
    else:
        cur.execute(f"UPDATE {table} SET name=%s, status='draft', approved_by=NULL, approved_at=NULL WHERE {idcol}=%s AND lang=%s", (new["name"], item_id, lang))


# ---------------------------------------------------------------------------------------------------------------- prehled a schvalovani
def _public_sets(cur, memo, family, lang):
    """Id kategorii a produktu, ktere by verejne API (shop ve stavu live) pro danou rodinu a jazyk ted skutecne vydalo."""
    key = (family, lang)
    if key not in memo:
        langs = [lang] + ([lang.split("-")[0]] if "-" in lang else [])
        ctx = {"shop": {"family": family, "currency": None}, "langs": langs, "statuses": ["approved"], "include_draft": False}
        products, cats = miniweb._visible_products(cur, ctx)
        memo[key] = ({p["id"] for p in products}, set(cats))
    return memo[key]


def build_overview(cur, only_lang=None):
    cur.execute("SELECT m.storefront_id, m.family, m.price_mode, m.inquiry_enabled, s.slug, s.primary_domain AS domain, s.status, s.lang FROM miniweb_shops m JOIN car_storefronts s ON s.id = m.storefront_id ORDER BY s.lang, s.id")
    shops = [{"storefront_id": r["storefront_id"], "slug": r["slug"], "domain": r["domain"], "status": r["status"], "lang": r["lang"], "family": r["family"], "price_mode": r["price_mode"],
              "inquiry_enabled": bool(r["inquiry_enabled"])} for r in cur.fetchall()]
    cur.execute("SELECT c.id, c.family, c.slug, c.sort_order, c.is_active, t.lang, t.name, t.status, t.approved_at, t.updated_at FROM miniweb_categories c "
                "JOIN miniweb_category_texts t ON t.miniweb_category_id = c.id ORDER BY c.family, c.sort_order, c.id, t.lang")
    cat_rows = cur.fetchall()
    cat_name = {(r["id"], r["lang"]): miniweb._plain(r["name"], 200) for r in cat_rows}
    cur.execute("SELECT p.id, p.slug, p.public_sku, p.sort_order, p.category_id, p.is_active, c.family, c.slug AS category_slug, t.* FROM miniweb_products p "
                "JOIN miniweb_categories c ON c.id = p.category_id JOIN miniweb_product_texts t ON t.miniweb_product_id = p.id ORDER BY c.family, p.sort_order, p.id, t.lang")
    prod_rows = cur.fetchall()
    memo, items = {}, []
    for r in cat_rows:
        if only_lang and r["lang"] != only_lang:
            continue
        clean = {"name": miniweb._plain(r["name"], LIMITS["name"]), "summary": "", "description": "", "delivery": "", "specs": []}
        blocking, info = _problems(clean, r["slug"], None, False)
        _pids, public_cats = _public_sets(cur, memo, r["family"], r["lang"])
        items.append({"kind": "category", "id": r["id"], "lang": r["lang"], "family": r["family"], "status": r["status"], "slug": r["slug"], "sku": None, "category": None, **clean,
                      "rev": text_rev(clean["name"], "", "", "", []), "blocking": blocking, "info": info, "active": bool(r["is_active"]), "public": r["id"] in public_cats,
                      "approved_at": r["approved_at"].isoformat(sep=" ", timespec="seconds") if r["approved_at"] else None, "updated_at": r["updated_at"].isoformat(sep=" ", timespec="seconds") if r["updated_at"] else None})
    for r in prod_rows:
        if only_lang and r["lang"] != only_lang:
            continue
        clean = _clean_product_text(r)
        raw_changed = any(clean[k] != (r[k] or "") for k in ("name", "summary", "description", "delivery"))
        blocking, info = _problems(clean, r["slug"], r["public_sku"], raw_changed)
        pub_prods, _c = _public_sets(cur, memo, r["family"], r["lang"])
        items.append({"kind": "product", "id": r["id"], "lang": r["lang"], "family": r["family"], "status": r["status"], "slug": r["slug"], "sku": r["public_sku"],
                      "category": cat_name.get((r["category_id"], r["lang"])) or r["category_slug"], **clean, "rev": text_rev(clean["name"], clean["summary"], clean["description"], clean["delivery"], clean["specs"]),
                      "blocking": blocking, "info": info, "active": bool(r["is_active"]), "public": r["id"] in pub_prods,
                      "approved_at": r["approved_at"].isoformat(sep=" ", timespec="seconds") if r["approved_at"] else None, "updated_at": r["updated_at"].isoformat(sep=" ", timespec="seconds") if r["updated_at"] else None})
    counts = {"draft": sum(1 for i in items if i["status"] == "draft"), "approved": sum(1 for i in items if i["status"] == "approved"), "blocked": sum(1 for i in items if i["blocking"]),
              "public": sum(1 for i in items if i["public"])}
    return {"shops": shops, "items": items, "counts": counts, "langs": sorted({i["lang"] for i in items})}


def _admin_json():
    """Telo POST: jen application/json (cross-site formular ho neposle bez preflightu) a objekt. Jinak None."""
    if request.mimetype != "application/json":
        return None
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


def _parse_items(body, need_rev):
    items = body.get("items")
    if not isinstance(items, list) or not items or len(items) > MAX_APPROVE_ITEMS:
        return None
    out = []
    for it in items:
        if not isinstance(it, dict) or it.get("kind") not in ("product", "category") or isinstance(it.get("id"), bool) or not isinstance(it.get("id"), int):
            return None
        lang = miniweb._clean_lang(it.get("lang")) if isinstance(it.get("lang"), str) else None
        rev = it.get("rev")
        if not lang or (need_rev and not (isinstance(rev, str) and re.match(r"^[0-9a-f]{16}\Z", rev))):
            return None
        out.append({"kind": it["kind"], "id": it["id"], "lang": lang, "rev": rev})
    return out


def apply_status_change(cur, user_id, items, approve):
    """Schvali (approve=True, jen kdyz se otisk shoduje, neni blokovano a je v draftu) nebo vrati do draftu. -> (pocet, preskocene). Transakci commituje volajici."""
    done, skipped = 0, []
    for it in items:
        if it["kind"] == "product":
            cur.execute("SELECT t.*, p.slug, p.public_sku FROM miniweb_product_texts t JOIN miniweb_products p ON p.id = t.miniweb_product_id WHERE t.miniweb_product_id=%s AND t.lang=%s FOR UPDATE", (it["id"], it["lang"]))
            table, idcol = "miniweb_product_texts", "miniweb_product_id"
        else:
            cur.execute("SELECT t.*, c.slug, NULL AS public_sku FROM miniweb_category_texts t JOIN miniweb_categories c ON c.id = t.miniweb_category_id WHERE t.miniweb_category_id=%s AND t.lang=%s FOR UPDATE", (it["id"], it["lang"]))
            table, idcol = "miniweb_category_texts", "miniweb_category_id"
        row = cur.fetchone()
        ref = {"kind": it["kind"], "id": it["id"], "lang": it["lang"]}
        if row is None:
            skipped.append({**ref, "reason": "not_found"})
            continue
        if approve:
            clean = _clean_product_text(row) if it["kind"] == "product" else {"name": miniweb._plain(row["name"], LIMITS["name"]), "summary": "", "description": "", "delivery": "", "specs": []}
            blocking, _info = _problems(clean, row["slug"], row["public_sku"], False)
            if blocking:
                skipped.append({**ref, "reason": "blocked"})
            elif text_rev(clean["name"], clean["summary"], clean["description"], clean["delivery"], clean["specs"]) != it["rev"]:
                skipped.append({**ref, "reason": "changed"})
            elif row["status"] == "approved":
                skipped.append({**ref, "reason": "already"})
            else:
                cur.execute(f"UPDATE {table} SET status='approved', approved_by=%s, approved_at=NOW() WHERE {idcol}=%s AND lang=%s AND status='draft'", (user_id, it["id"], it["lang"]))
                done += cur.rowcount
        elif row["status"] != "approved":
            skipped.append({**ref, "reason": "already"})
        else:
            cur.execute(f"UPDATE {table} SET status='draft', approved_by=NULL, approved_at=NULL WHERE {idcol}=%s AND lang=%s AND status='approved'", (it["id"], it["lang"]))
            done += cur.rowcount
    return done, skipped


@app.get("/api/admin/miniweb/overview")
@admin_required
def admin_miniweb_overview():
    lang = miniweb._clean_lang(request.args.get("lang")) if request.args.get("lang") else None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            data = build_overview(cur, lang)
    finally:
        conn.close()
    resp = jsonify(data)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _status_change(approve):
    body = _admin_json()
    items = _parse_items(body, need_rev=approve) if body is not None else None
    if items is None:
        return jsonify({"error": "bad_request"}), 400
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            done, skipped = apply_status_change(cur, user["id"], items, approve)
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "miniweb_text", None, {"akce": "approve" if approve else "unapprove", "zmeneno": done, "preskoceno": len(skipped), "polozky": [f"{i['kind']}:{i['id']}:{i['lang']}" for i in items][:100]})
    resp = jsonify({"status": "ok", "changed": done, "skipped": skipped})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/api/admin/miniweb/approve")
@admin_required
def admin_miniweb_approve():
    return _status_change(True)


@app.post("/api/admin/miniweb/unapprove")
@admin_required
def admin_miniweb_unapprove():
    return _status_change(False)
