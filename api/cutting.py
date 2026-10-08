"""
Rezne plany (bot4, "optimizer").

DB podklad (bot4, 2026-07-25, `sql/2026-07-25_cutting_plans.sql`, JIZ
APLIKOVANO na produkci): `shop_order_items` rozsireno o nullable sloupce
`cut_kind`/`material_key`/`length_mm`/`width_mm`/`height_mm`/`grain_locked`,
nove tabulky `shop_cutting_stock` (skladove rozmery materialu) a
`shop_cutting_settings` (kerf per material). Vazbu "3D scena -> objednavka
s temihle rozmery" (tj. KDO tyhle sloupce u konkretni polozky vyplni) resi
JINY BOT (viz NAVRH_REZNE_PLANY.md, sekce 5, bod 3 - potvrzeno Robertem) -
tenhle modul jen CTE, co uz v `shop_order_items` je, a pocita z toho plan.

DB podklad 2 (bot4, 2026-07-26, `sql/2026-07-26_cutting_plan_units.sql`,
JIZ APLIKOVANO): `shop_cutting_plans` + `shop_cutting_plan_units` -
perzistentni ulozeni vygenerovaneho planu, aby slo odskrtavat hotove tyce/
desky (Robert: "měly by se asi odklikávat, které jsou hotové" - viz
NAVRH_REZNE_PLANY.md sekce 6, POTVRZENO Robertem: jednotka odskrtnuti =
cela tyc/deska, hotove jednotky se NIKDY neprepocitavaji zpetne, vazba na
stav objednavky je jen INFORMATIVNI stitek, zadna automaticka zmena stavu).

Endpointy:
  GET  /api/admin/cutting/demo                - pevna ukazkova data (bez
                                                 DB), overeni funkcnosti
                                                 algoritmu.
  POST /api/admin/cutting-plan/generate       - spocita NOVY plan ze vsech
                                                 nevyrizenych objednavek
                                                 MINUS uz hotove kusy,
                                                 ulozi jako pending jednotky.
  GET  /api/admin/cutting-plan                - HLAVNI provozni pohled:
                                                 cte ULOZENE jednotky (ne
                                                 zivy prepocet), + informativni
                                                 order_progress na objednavku.
  PATCH /api/admin/cutting-plan/units/<id>    - oznaci jednotku hotovou/
                                                 nehotovou (odskrtnuti na dilne).
  GET  /api/admin/orders/<id>/cutting-plan    - DIAGNOSTICKY zivy prepocet
                                                 pro JEDNU objednavku (necte
                                                 ani nezapisuje perzistentni
                                                 jednotky, jen nahled).

Aktivace (stejna konvence jako orders.py/cart.py, zadne Blueprints): na
konec app.py (az po ostatnich `import orders`/`import cart` atd.) pridat:

    import cutting  # noqa: F401 - registruje /api/admin/cutting/*

Opravneni (bot5, 2026-08-02): puvodne @require_permission("objednavky", ...)
na vsech endpointech, ale zalozka "Řezné plány" je v navigaci zarazena
pod skupinou "Sklad" - checkbox u "Objednávky" v matici Role a opravneni
tak ridil neco jineho, nez kde tab vizualne je (Robert po vysvetleni
zvolil "sklad"). Prepnuto na "produkty_sklad", aby odpovidalo UI.
(bot16, 2026-09-29: "produkty_sklad" dal rozdeleno na granularni sekce
po zalozkach, tady je vlastni "rezne_plany" - viz AGENTS_LOG.md.)
"""
import json

from flask import jsonify, request

from app import app, admin_required, get_conn, require_permission, current_user, parse_bulk_ids, log_audit
from orders import _fetch_order_with_items, ORDER_STATUSES
import cutting_algo as ca

# Robert, 2026-07-25: "řezný plán se nedělá v každé objednávce, ale
# hromadně za všechny nevyřízené objednávky" - "nevyřízené" = zatím
# neuzavřené koncové stavy ("fakturovana"/"zrusena" ven, viz orders.py).
UNFINISHED_STATUSES = tuple(s for s in ORDER_STATUSES if s not in ("fakturovana", "zrusena"))

# Zasoba ZBYTKU (Robert 2026-08-06: "bude se kalkulovat skladová zásoba
# profilů (délka vždy 3000mm) a zásoba zbytků vzniklých řezáním, tzn se
# bude držet databáze zbytků") - kratší zbytek uz neni k nicemu, jde
# rovnou do odpadu, nikdy se nezaklada jako polozka v shop_cutting_remnants
# (viz sql/2026-08-06_cutting_remnants.sql, _spawn_remnant_if_applicable).
# Zbytky se zatim resi JEN pro cut_kind='profil' (2D zbytky z desek
# nejsou v rozsahu tohoto pozadavku).
MIN_REMNANT_LENGTH_MM = 50.0

# Barva kusu podle ZAKAZKY (bot4, 2026-07-26, viz sql/2026-07-26_order_colors.sql
# a Robert: "barva obřezávaného dílu... podle zakázky... barva se uvolní
# pro příští řezný plán a jinou objednávku"). Stejna paleta jako CP_COLORS
# ve webapp/admin.html (udrzovat obe sychronne, kdyz se meni).
ORDER_COLOR_PALETTE = [
    "#5b8def", "#e0a458", "#7ec488", "#d97b7b", "#9d7bd9", "#54b8b0",
    "#c78bd9", "#a3a86b", "#4fb3d9", "#e08ac0", "#a8c15a", "#c96f4a",
]

# --- Ukazkova data - POTVRZENO Robertem 2026-07-25 (viz NAVRH_REZNE_PLANY.md) ---

DEMO_STOCK_PROFIL = [
    {"id": "profil_3000", "label": "Tyč 30x30, 3000 mm", "length_mm": 3000, "qty": None, "price_czk": 0.0},
]

DEMO_PIECES_PROFIL = [
    {"id": "noha", "label": "Noha stolu 30x30", "length_mm": 800, "qty": 4},
    {"id": "pricka", "label": "Příčka 30x30", "length_mm": 1200, "qty": 6},
    {"id": "kratky", "label": "Krátký kus 30x30", "length_mm": 350, "qty": 10},
]

DEMO_STOCK_DESKA = [
    {"id": "preklizka_10", "label": "Překližka 10mm 2500×1250", "width_mm": 2500, "height_mm": 1250, "qty": None, "price_czk": 0.0},
    {"id": "mdf_8", "label": "MDF 8mm 2800×2070", "width_mm": 2800, "height_mm": 2070, "qty": None, "price_czk": 0.0},
]

DEMO_PIECES_DESKA = [
    {"id": "bok", "label": "Bok skříně (MDF)", "width_mm": 600, "height_mm": 720, "qty": 4, "grain_locked": True},
    {"id": "dno", "label": "Dno (překližka)", "width_mm": 560, "height_mm": 560, "qty": 2, "grain_locked": False},
    {"id": "police", "label": "Police (překližka)", "width_mm": 560, "height_mm": 300, "qty": 6, "grain_locked": False},
]


@app.get("/api/admin/cutting/demo")
@admin_required
def cutting_demo():
    """
    DOČASNÝ demo endpoint (bot4) - ověřuje funkčnost `cutting_algo` na
    pevných ukázkových datech, NE na reálné objednávce. Nahradit/doplnit
    až bude hotové napojení na `shop_order_items` (viz docstring modulu).
    """
    profil_1d = ca.pack_1d(DEMO_PIECES_PROFIL, DEMO_STOCK_PROFIL, kerf_mm=3.0)
    # MDF a překližka se řežou zvlášť (jiný materiál) - ukázka řeší je
    # napřed dohromady, aby demo ukázalo obě materiálové skupiny najednou;
    # v ostrém provozu se `pack_2d` volá zvlášť pro každý `material_key`.
    preklizka_pieces = [p for p in DEMO_PIECES_DESKA if p["id"] != "bok"]
    mdf_pieces = [p for p in DEMO_PIECES_DESKA if p["id"] == "bok"]
    preklizka_2d = ca.pack_2d(preklizka_pieces, [DEMO_STOCK_DESKA[0]], kerf_mm=3.0)
    mdf_2d = ca.pack_2d(mdf_pieces, [DEMO_STOCK_DESKA[1]], kerf_mm=3.0)
    return jsonify({
        "note": "Demo řezného plánu (bot4/optimizer) - ukázková data, NE reálná objednávka. "
                "Viz NAVRH_REZNE_PLANY.md pro stav napojení na skutečné objednávky.",
        "profil_1d_30x30": profil_1d,
        "deska_2d_preklizka_10": preklizka_2d,
        "deska_2d_mdf_8": mdf_2d,
    })


# ---------------------------------------------------------------------------
# Realny rezny plan - HROMADNE za vice objednavek najednou
#
# Robert, 2026-07-25 (po prvni verzi s planem per-objednavka): "řezný plán
# se nedělá v každé objednávce, ale hromadně za všechny nevyřízené
# objednávky" - kusy stejneho materialu NAPRIC ruznymi objednavkami se
# maji sectat do JEDNOHO rezneho planu (min. odpad za cely aktualni
# provoz dilny, ne jen za jednu zakazku zvlast). Puvodni
# GET /api/admin/orders/<id>/cutting-plan (jedna objednavka) zustava
# zachovany jako diagnosticky/nahledovy nastroj (napr. "co presne je v
# TETO objednavce k rezani"), ale HLAVNI provozni endpoint je ted
# hromadny nize.
# ---------------------------------------------------------------------------

def _fetch_stock_and_kerf(cur, cut_kind, material_key):
    cur.execute(
        "SELECT id, label, stock_length_mm, stock_width_mm, stock_height_mm, price_czk "
        "FROM shop_cutting_stock WHERE cut_kind=%s AND material_key=%s AND active=1 "
        "ORDER BY sort_order",
        (cut_kind, material_key),
    )
    stock_rows = cur.fetchall()
    cur.execute("SELECT kerf_mm FROM shop_cutting_settings WHERE material_key=%s", (material_key,))
    settings_row = cur.fetchone()
    kerf_mm = float(settings_row["kerf_mm"]) if settings_row else 3.0
    return stock_rows, kerf_mm


def _fetch_available_remnants(cur, material_key):
    """Dostupne (jeste nepouzite) zbytky pro dany material - viz
    MIN_REMNANT_LENGTH_MM a _spawn_remnant_if_applicable (kde vznikaji)."""
    cur.execute(
        "SELECT id, length_mm FROM shop_cutting_remnants "
        "WHERE cut_kind='profil' AND material_key=%s AND status='available' "
        "ORDER BY length_mm ASC",
        (material_key,),
    )
    return cur.fetchall()


def _classify_items(rows):
    """
    rows: radky z `shop_order_items` (kazdy MUSI mit navic `order_number`
    - viz volajici SQL nize). Vraci (by_material, items_without_dimensions).
    by_material: {(cut_kind, material_key): [row, ...]}.
    """
    by_material = {}
    items_without_dimensions = []
    for it in rows:
        cut_kind = it.get("cut_kind")
        material_key = it.get("material_key")
        base = {
            "id": it["id"], "order_number": it["order_number"],
            "product_name": it["product_name_snapshot"], "qty": it["qty"],
        }
        if not cut_kind or not material_key:
            items_without_dimensions.append(base)
            continue
        if cut_kind == "profil" and not it.get("length_mm"):
            items_without_dimensions.append({**base, "reason": "cut_kind='profil', ale chybí length_mm"})
            continue
        if cut_kind == "deska" and (not it.get("width_mm") or not it.get("height_mm")):
            items_without_dimensions.append({**base, "reason": "cut_kind='deska', ale chybí width_mm/height_mm"})
            continue
        by_material.setdefault((cut_kind, material_key), []).append(it)
    return by_material, items_without_dimensions


def _enrich_with_order_number(result, id_to_order):
    """Doplni `order_number` ke kazdemu umistenemu kusu v planu (podle
    `piece_id` == id polozky objednavky), aby bylo na dilne jasne, kam
    ktery rozrezany kus patri - klicove pro HROMADNY plan pres vice
    objednavek najednou."""
    # "unplaced" v cutting_algo nese jen "label" (bez piece_id) - protoze
    # uz volajici (_build_plans nize) do labelu pri stavbe pieces vlozil
    # "(obj. <cislo>)", zustava dohledatelnost zachovana i tam bez dalsi
    # upravy cutting_algo.py.
    for group_key in ("bars", "sheets"):
        for group in result.get(group_key, []):
            for p in group["pieces"]:
                p["order_number"] = id_to_order.get(int(p["piece_id"]))


def _build_plans(cur, by_material, id_to_order):
    plans = []
    for (cut_kind, material_key), rows in by_material.items():
        stock_rows, kerf_mm = _fetch_stock_and_kerf(cur, cut_kind, material_key)
        if not stock_rows:
            plans.append({
                "cut_kind": cut_kind, "material_key": material_key,
                "error": f"Pro materiál '{material_key}' není v shop_cutting_stock žádná aktivní skladová varianta.",
                "item_ids": [r["id"] for r in rows],
            })
            continue

        if cut_kind == "profil":
            pieces = [{
                "id": str(r["id"]), "label": f"{r['product_name_snapshot']} (obj. {r['order_number']})",
                "length_mm": float(r["length_mm"]), "qty": r["qty"],
            } for r in rows]
            stock = [{
                "id": s["id"], "label": s["label"], "length_mm": float(s["stock_length_mm"]),
                "qty": None, "price_czk": float(s["price_czk"]),
            } for s in stock_rows]
            # Zbytky (Robert 2026-08-06: "zásoba zbytků vzniklých řezáním")
            # - kazdy zbytek je JEDNA konkretni fyzicka tyc s pevnou delkou
            # (qty=1, ne neomezene jako cerstvy material ze skladu). Zaporne
            # "id" (odvozene od shop_cutting_remnants.id) je jen interni
            # rozliseni pro zpetne dohledani v generate_cutting_plan - viz
            # tamni komentar. pack_1d uz sam pri otevirani nove tyce
            # preferuje NEJMENSI skladovou variantu, do ktere se kus vejde
            # (`_try_open_new_bar`, `stock_sorted` vzestupne dle delky) -
            # zbytky (kratsi nez cerstve 3000mm tyce) se tak prirozene
            # spotrebuji driv, aniz by bylo nutne cokoli menit v
            # cutting_algo.py.
            remnants = _fetch_available_remnants(cur, material_key)
            stock += [{
                "id": -r["id"], "label": f"Zbytek {float(r['length_mm']):.0f} mm",
                "length_mm": float(r["length_mm"]), "qty": 1, "price_czk": 0.0,
            } for r in remnants]
            result = ca.pack_1d(pieces, stock, kerf_mm=kerf_mm)
        else:  # deska
            pieces = [{
                "id": str(r["id"]), "label": f"{r['product_name_snapshot']} (obj. {r['order_number']})",
                "width_mm": float(r["width_mm"]), "height_mm": float(r["height_mm"]),
                "qty": r["qty"], "grain_locked": bool(r.get("grain_locked")),
                # Olepeni hran (bot4, 2026-07-26) - viz sql/2026-07-26_edge_banding.sql.
                # Vzdy vzhledem k DEKLAROVANE (nerotovane) width_mm/height_mm - viz
                # docstring cutting_algo.pack_2d ("rotated" priznak u vystupu).
                "edge_bands": {
                    "top": bool(r.get("edge_band_top")), "bottom": bool(r.get("edge_band_bottom")),
                    "left": bool(r.get("edge_band_left")), "right": bool(r.get("edge_band_right")),
                },
                "edge_banding_type": r.get("edge_banding_type"),
            } for r in rows]
            stock = [{
                "id": s["id"], "label": s["label"], "width_mm": float(s["stock_width_mm"]),
                "height_mm": float(s["stock_height_mm"]), "qty": None,
                "price_czk": float(s["price_czk"]),
            } for s in stock_rows]
            result = ca.pack_2d(pieces, stock, kerf_mm=kerf_mm)

        _enrich_with_order_number(result, id_to_order)
        plans.append({
            "cut_kind": cut_kind, "material_key": material_key, "kerf_mm": kerf_mm, "plan": result,
            # Kanonicky (kladny) shop_cutting_stock.id pro tenhle material -
            # potreba jako FK fallback pri ukladani jednotky vzesle ze
            # zbytku (zaporne "stock_id" v jednotlivych bars, viz vyse) -
            # shop_cutting_plan_units.stock_id musi vzdy ukazovat na
            # existujici radek shop_cutting_stock, skutecna delka/label se
            # pro zbytek bere z remnant_id (viz generate_cutting_plan).
            "canonical_stock_id": stock_rows[0]["id"],
        })
    return plans


def _fetch_items_by_order_ids(cur, order_ids):
    placeholders = ",".join(["%s"] * len(order_ids))
    cur.execute(
        f"SELECT oi.*, o.order_number, o.status AS order_status "
        f"FROM shop_order_items oi JOIN shop_orders o ON o.id = oi.order_id "
        f"WHERE o.id IN ({placeholders}) "
        f"ORDER BY o.created_at ASC, oi.id ASC",
        order_ids,
    )
    return cur.fetchall()


def _load_pieces_json(raw):
    """pymysql muze JSON sloupec vratit uz jako list/dict, nebo jako
    retezec (zavisi na verzi/konfiguraci ovladace) - podpora obojiho."""
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _collect_pending_order_numbers(cur):
    """Mnozina cisel objednavek, ktere maji aspon jeden kus v NEKTERE
    'pending' jednotce (napric vsemi materialy/tycemi/deskami)."""
    cur.execute("SELECT pieces_json FROM shop_cutting_plan_units WHERE status='pending'")
    orders = set()
    for row in cur.fetchall():
        for p in _load_pieces_json(row["pieces_json"]):
            on = p.get("order_number")
            if on:
                orders.add(on)
    return orders


def _sync_order_colors(cur):
    """Prirad kazde objednavce s aspon jednim NEDOKONCENYM (pending) kusem
    trvalou barvu z `ORDER_COLOR_PALETTE` (Robert, 2026-07-26: "barva
    obřezávaného dílu... podle zakázky") - stejna objednavka ma stejnou
    barvu napric VSEMI tycemi/deskami v hromadnem planu, ruzne soubezne
    objednavky maji ruznou barvu. Jakmile uz objednavka nema zadny pending
    kus (vsechno uz je 'done'), jeji radek v `shop_cutting_order_colors`
    se SMAZE - barva se tim uvolni pro jinou objednavku pri pristim
    volani ("kdyz se to odškrtne jako hotové, barva se uvolní pro příští
    řezný plán a jinou objednávku" - viz sql/2026-07-26_order_colors.sql).

    Volat pri kazdem cteni/generovani/odskrtnuti planu (idempotentni,
    levne - jednotky planu jsou radove destky/stovky, ne tisice).

    Vraci {order_number: barva} pro VSECHNY aktualne pending objednavky."""
    pending_orders = _collect_pending_order_numbers(cur)

    cur.execute("SELECT order_number, color FROM shop_cutting_order_colors")
    existing = {r["order_number"]: r["color"] for r in cur.fetchall()}

    stale = [o for o in existing if o not in pending_orders]
    if stale:
        placeholders = ",".join(["%s"] * len(stale))
        cur.execute(
            f"DELETE FROM shop_cutting_order_colors WHERE order_number IN ({placeholders})",
            stale,
        )
        for o in stale:
            del existing[o]

    used_colors = set(existing.values())
    free_colors = [c for c in ORDER_COLOR_PALETTE if c not in used_colors]
    fi = 0
    for order_number in sorted(pending_orders):
        if order_number in existing:
            continue
        if fi < len(free_colors):
            color = free_colors[fi]
            fi += 1
        else:
            # Paleta vycerpana (vic soubeznych rozpracovanych objednavek
            # nez barev v palete) - deterministicky hash fallback, aby se
            # aspon nemenil pri kazdem nacteni (muze se priblizne shodovat
            # s jinou objednavkou - dokumentovane omezeni pro tenhle
            # okrajovy pripad).
            color = ORDER_COLOR_PALETTE[sum(ord(ch) for ch in order_number) % len(ORDER_COLOR_PALETTE)]
        cur.execute(
            "INSERT INTO shop_cutting_order_colors (order_number, color) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE color=color",
            (order_number, color),
        )
        existing[order_number] = color

    return existing


def _piece_counts_by_status(cur, statuses):
    """Kolikrat uz byl kazdy `piece_id` (= id polozky objednavky) soucasti
    NEJAKE jednotky s jednim z danych statusu, napric VSEMI plany
    historicky. `statuses` je n-tice/seznam z {'pending','done'}."""
    placeholders = ",".join(["%s"] * len(statuses))
    cur.execute(f"SELECT pieces_json FROM shop_cutting_plan_units WHERE status IN ({placeholders})", list(statuses))
    counts = {}
    for row in cur.fetchall():
        for p in _load_pieces_json(row["pieces_json"]):
            iid = int(p["piece_id"])
            counts[iid] = counts.get(iid, 0) + 1
    return counts


def _done_piece_counts(cur):
    """Jen 'done' - pouziva se pro `order_progress` (kolik je SKUTECNE
    narezano), NE pro generovani (tam viz `_piece_counts_by_status` s
    obema statusy, aby se nezdvojovaly uz naplanovane pending jednotky)."""
    return _piece_counts_by_status(cur, ("done",))


def _apply_done_offset(rows, accounted_counts):
    """Odecte od `qty` kazde polozky pocet kusu, ktere uz jsou soucasti
    NEJAKE existujici jednotky (pending NEBO done - `accounted_counts`,
    viz `_piece_counts_by_status(cur, ('pending','done'))` u volajiciho).
    Bez tohohle by kazde dalsi 'Generovat' vytvorilo DUPLICITNI pending
    jednotky pro kusy, ktere uz jednu pending jednotku maji z minula -
    odhaleno pri testovani (2026-07-26), viz AGENTS_LOG.md.

    Vraci (rows_se_snizenym_qty_bez_nulovych, already_planned_info) -
    druhy seznam je informativni (polozky, ktere uz maji VSECHNY kusy
    pokryte drivejsi jednotkou, pending nebo done)."""
    adjusted = []
    already_planned = []
    for r in rows:
        accounted = accounted_counts.get(r["id"], 0)
        remaining = r["qty"] - accounted
        if remaining <= 0:
            if accounted:
                already_planned.append({
                    "id": r["id"], "order_number": r["order_number"],
                    "product_name": r["product_name_snapshot"], "qty": r["qty"],
                })
            continue
        r2 = dict(r)
        r2["qty"] = remaining
        adjusted.append(r2)
    return adjusted, already_planned


MANUAL_PIECE_ORDER_NUMBER = "Ruční zadání"

# "Univerzální tyč" (Robert pres bot3, 2026-09-07): rucni kus, kde admin
# nezna/nema katalogovy material_key (zbytek/odrezek/koupeno mimo sklad),
# ale zna delku SKLADOVE tyce, ze ktere se bude rezat. `material_key` z
# `shop_cutting_stock`/`shop_cutting_settings` je klic pouzivany UPLNE
# VSUDE nize (seskupovani rucnich kusu do optimalizacnich skupin, zbytky,
# ulozene jednotky planu, FK `shop_cutting_plan_units.stock_id` -> REALNY
# radek `shop_cutting_stock.id`) - misto zavadeni paralelni cesty pro
# "material bez katalogoveho radku" (dotklo by se _fetch_stock_and_kerf,
# _build_plans, _spawn_remnant_if_applicable, bulk_cutting_plan JOIN...)
# se pro kazdou pouzitou delku LINE (nebo znovupouzije, viz
# _get_or_create_universal_rod_stock) SKUTECNY radek shop_cutting_stock
# se synteticky odvozenym material_key - zbytek kodu pak funguje BEZE
# ZMENY (vc. zbytku vznikajicich po narezani, ktere se pri stejne delce
# pouzite znovu prirozene nabidnou k dosypani). Synteticky radek je
# schvalne VYLOUCEN z `cutting_plan_materials()` (viz tam), aby se
# neplet s katalogem k rucnimu vyberu - je jen internim implementacnim
# detailem tehle funkce.
UNIVERSAL_ROD_KEY_PREFIX = "univ_tyc_"
UNIVERSAL_ROD_MAX_MM = 6000


def _get_or_create_universal_rod_stock(cur, length_mm):
    """Vrati material_key syntetickeho `shop_cutting_stock` radku pro
    "univerzalni tyc" zadane delky (vytvori ho, pokud jeste neexistuje -
    stejna delka = stejny material_key = znovupouziti, viz komentar
    vyse). `length_mm` uz musi byt validovana volajicim (0 < x <=
    UNIVERSAL_ROD_MAX_MM)."""
    material_key = f"{UNIVERSAL_ROD_KEY_PREFIX}{int(round(length_mm))}"
    cur.execute(
        "SELECT id FROM shop_cutting_stock WHERE cut_kind='profil' AND material_key=%s",
        (material_key,),
    )
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO shop_cutting_stock "
            "(cut_kind, material_key, label, stock_length_mm, price_czk, active, sort_order) "
            "VALUES ('profil', %s, %s, %s, 0.00, 1, 999)",
            (material_key, f"Univerzální tyč {length_mm:.0f} mm", length_mm),
        )
    return material_key


def _insert_manual_pieces(cur, admin_id, pieces_raw):
    """Rezne kusy BEZ vazby na objednavku (Robert pres bot3, 2026-09-03,
    "hned") - kazdy polozeny radek se NEJDRIV ulozi do
    shop_cutting_manual_pieces (ciste jako bezkolizni zdroj ID + audit
    stopa, zadna FK vazba na cutting plan samotny) a az pak se z nej
    postavi synteticky "row" ve stejnem tvaru, jaky ceka _classify_items/
    _build_plans (stejne klice jako radek z shop_order_items+shop_orders
    JOIN, viz _fetch_items_by_order_ids).

    piece_id = -id (stejna konvence jako uz existujici zbytky, viz
    "id": -r["id"] v _build_plans) - pieces_json je JSON sloupec, zadny
    FK constraint na nem nejde vubec vytvorit (overeno SHOW CREATE TABLE
    shop_cutting_plan_units), ale AUTO_INCREMENT v teto tabulce garantuje
    globalni unikatnost navzdy - i mezi dvema ruznymi rucnimi davkami
    navzajem, ne jen vuci objednavkam (ty maji vzdy kladne id).

    Vraci (synthetic_rows, error) - `error` je text k vraceni jako 400,
    nebo None pri uspechu. Zadna kontrola proti duplicitnimu odeslani
    (Robert/bot3 schvalili: rucni kusy nemaji idempotentni ochranu jako
    objednavky - riziko je jen "naplanovano 2x", viditelne a opravitelne
    bulk-delete pending jednotek, ne nevratne jako u penez)."""
    rows = []
    for i, p in enumerate(pieces_raw):
        if not isinstance(p, dict):
            return None, f"Ruční položka #{i + 1}: neplatný formát."
        cut_kind = p.get("cut_kind")
        if cut_kind not in ("profil", "deska"):
            return None, f"Ruční položka #{i + 1}: cut_kind musí být 'profil' nebo 'deska'."

        universal_len_raw = p.get("universal_stock_length_mm")
        if universal_len_raw is not None:
            if cut_kind != "profil":
                return None, f"Ruční položka #{i + 1}: univerzální tyč lze zadat jen pro cut_kind='profil'."
            try:
                universal_len = float(universal_len_raw)
            except (TypeError, ValueError):
                universal_len = 0
            if not (0 < universal_len <= UNIVERSAL_ROD_MAX_MM):
                return None, (
                    f"Ruční položka #{i + 1}: délka univerzální tyče musí být "
                    f"kladné číslo do {UNIVERSAL_ROD_MAX_MM} mm."
                )
            material_key = _get_or_create_universal_rod_stock(cur, universal_len)
        else:
            material_key = (p.get("material_key") or "").strip()
            if not material_key:
                return None, f"Ruční položka #{i + 1}: chybí material_key."
        try:
            qty = int(p.get("qty"))
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            return None, f"Ruční položka #{i + 1}: qty musí být kladné celé číslo."
        length_mm = width_mm = height_mm = None
        if cut_kind == "profil":
            try:
                length_mm = float(p.get("length_mm"))
            except (TypeError, ValueError):
                length_mm = 0
            if length_mm <= 0:
                return None, f"Ruční položka #{i + 1}: u profilu je nutné zadat kladné length_mm."
            if universal_len_raw is not None and length_mm > universal_len:
                return None, (
                    f"Ruční položka #{i + 1}: délka kusu ({length_mm:.0f} mm) je delší než "
                    f"zadaná univerzální tyč ({universal_len:.0f} mm)."
                )
        else:
            try:
                width_mm = float(p.get("width_mm"))
                height_mm = float(p.get("height_mm"))
            except (TypeError, ValueError):
                width_mm = height_mm = 0
            if width_mm <= 0 or height_mm <= 0:
                return None, f"Ruční položka #{i + 1}: u desky je nutné zadat kladné width_mm i height_mm."
        label = (p.get("label") or "").strip() or None

        cur.execute(
            "INSERT INTO shop_cutting_manual_pieces "
            "(cut_kind, material_key, length_mm, width_mm, height_mm, qty, label, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (cut_kind, material_key, length_mm, width_mm, height_mm, qty, label, admin_id),
        )
        row_id = cur.lastrowid
        default_label = (
            f"Univerzální tyč {universal_len:.0f} mm ({material_key})" if universal_len_raw is not None
            else f"Ruční kus ({material_key})"
        )
        rows.append({
            "id": -row_id,
            "order_number": MANUAL_PIECE_ORDER_NUMBER,
            "product_name_snapshot": label or default_label,
            "qty": qty,
            "cut_kind": cut_kind,
            "material_key": material_key,
            "length_mm": length_mm,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "grain_locked": False,
        })
    return rows, None


@app.get("/api/admin/cutting-plan/materials")
@require_permission("rezne_plany", "zobrazit")
def cutting_plan_materials():
    """Seznam aktivnich materialu ve shop_cutting_stock (cut_kind +
    material_key) - pro dropdown/datalist u rucniho pridani kusu bez
    objednavky (Robert pres bot3, 2026-09-03), at se material_key
    nepřeklepne (chybu by jinak ukazal az generate_cutting_plan).

    Syntetické "univerzální tyč" řádky (viz `_get_or_create_universal_rod_
    stock`, prefix `UNIVERSAL_ROD_KEY_PREFIX`) jsou ZÁMĚRNĚ vynechané -
    frontend nabízí "Univerzální tyč (vlastní délka)" jako samostatnou
    volbu vedle tohohle seznamu, ne jako další katalogovou položku."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT cut_kind, material_key FROM shop_cutting_stock "
                "WHERE active=1 ORDER BY cut_kind, material_key"
            )
            rows = [r for r in cur.fetchall() if not r["material_key"].startswith(UNIVERSAL_ROD_KEY_PREFIX)]
    finally:
        conn.close()
    return jsonify({"materials": rows})


@app.get("/api/admin/cutting-plan/candidate-orders")
@require_permission("rezne_plany", "zobrazit")
def cutting_plan_candidate_orders():
    """
    Nabídka objednávek pro ruční zaškrtávání v "Vygenerovat plán" (Robert,
    2026-08-06 - náhrada za dřívější výběr podle stavu objednávky).
    Vrací každou nezrušenou objednávku, která má aspoň jednu položku s
    rozměry k řezání (`cut_kind` + délka/š×v vyplněné), spolu s tím, kolik
    kusů z ní je celkem k řezání a kolik je jich už "vyřízeno" (v nějaké
    pending/done jednotce dřívějšího plánu) - podle toho jde v UI
    předvybrat jen ty, kde ještě něco zbývá.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT o.id AS order_id, o.order_number, o.customer_name, o.status, o.created_at, "
                "       oi.id AS item_id, oi.qty, oi.cut_kind, oi.length_mm, oi.width_mm, oi.height_mm "
                "FROM shop_orders o JOIN shop_order_items oi ON oi.order_id = o.id "
                "WHERE o.status != 'zrusena' AND oi.cut_kind IS NOT NULL "
                "ORDER BY o.created_at DESC"
            )
            rows = cur.fetchall()
            accounted_counts = _piece_counts_by_status(cur, ("pending", "done"))
    finally:
        conn.close()

    by_order = {}
    for r in rows:
        has_dims = (r["cut_kind"] == "profil" and r["length_mm"]) or \
                   (r["cut_kind"] == "deska" and r["width_mm"] and r["height_mm"])
        if not has_dims:
            continue
        entry = by_order.setdefault(r["order_id"], {
            "order_id": r["order_id"], "order_number": r["order_number"],
            "customer_name": r["customer_name"], "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "total_pieces": 0, "remaining_pieces": 0,
        })
        entry["total_pieces"] += r["qty"]
        entry["remaining_pieces"] += max(0, r["qty"] - accounted_counts.get(r["item_id"], 0))

    orders = sorted(by_order.values(), key=lambda e: e["created_at"] or "", reverse=True)
    return jsonify({"orders": orders})


@app.post("/api/admin/cutting-plan/generate")
@require_permission("rezne_plany", "upravit")
def generate_cutting_plan():
    """
    Spočítá NOVÝ řezný plán z RUČNĚ VYBRANÝCH objednávek (Robert,
    2026-08-06: "chci zaškrtávat konkrétní objednávky", náhrada za
    dřívější výběr podle stavu objednávky) MÍNUS kusy, které jsou už
    "done" v nějaké dřívější jednotce (viz `_done_piece_counts`) -
    jednou nařezaný kus se znovu nenabízí. Výsledek se ULOŽÍ jako nová
    `shop_cutting_plans` řádka + `shop_cutting_plan_units`
    (status='pending', jedna řádka = jedna tyč/deska). Existující
    'done' jednotky se NIKDY nemažou ani nepřepočítávají (POTVRZENO
    Robertem, viz NAVRH_REZNE_PLANY.md sekce 6).

    Tělo požadavku: {"order_ids": [12, 34, ...]} (id objednávek ke
    spočítání, viz GET .../candidate-orders pro nabídku ke checkboxům)
    a/nebo {"pieces": [{"cut_kind","material_key","length_mm" nebo
    "width_mm"+"height_mm","qty","label"(volitelný)}, ...]} - ruční
    kusy BEZ vazby na objednávku (Robert pres bot3, 2026-09-03, "hned"
    - viz _insert_manual_pieces). Aspoň jedno z obou musí být neprázdné
    - lze poslat i obojí najednou (sdílený plán objednávek i ručních
    kusů, lepší využití materiálu/zbytků napříč oběma).

    U "profil" kusu lze místo "material_key" poslat
    "universal_stock_length_mm" (Robert pres bot3, 2026-09-07,
    "Univerzální tyč") - vlastní délka SKLADOVÉ tyče (do
    UNIVERSAL_ROD_MAX_MM), nezávislá na katalogu shop_cutting_stock, viz
    _get_or_create_universal_rod_stock.
    """
    body = request.get_json(silent=True) or {}
    order_ids_raw = body.get("order_ids") or []
    pieces_raw = body.get("pieces") or []
    if not isinstance(order_ids_raw, list) or not isinstance(pieces_raw, list):
        return jsonify({"error": "order_ids/pieces musí být pole."}), 400
    if not order_ids_raw and not pieces_raw:
        return jsonify({"error": "Vyber aspoň jednu objednávku, nebo přidej ruční položku."}), 400
    try:
        order_ids = sorted({int(x) for x in order_ids_raw})
    except (TypeError, ValueError):
        return jsonify({"error": "order_ids musí být seznam čísel."}), 400

    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            rows = _fetch_items_by_order_ids(cur, order_ids) if order_ids else []
            if pieces_raw:
                manual_rows, manual_err = _insert_manual_pieces(cur, admin["id"], pieces_raw)
                if manual_err:
                    conn.rollback()
                    return jsonify({"error": manual_err}), 400
                rows = rows + manual_rows
            order_numbers = sorted({r["order_number"] for r in rows})
            # POZOR: offset musi pocitat pending I done jednotky, jinak by
            # kazde dalsi "Generovat" zdvojilo pending jednotky pro kusy,
            # ktere uz jednu pending jednotku maji z minulého generovani
            # (viz docstring _apply_done_offset - odhaleno testovanim).
            # Rucni kusy (zaporne id, viz _insert_manual_pieces) tudy
            # projdou vzdy beze zmeny - cerstve vlozeny radek nemuze mit
            # zadnou historii v pieces_json, takze accounted vzdy 0.
            accounted_counts = _piece_counts_by_status(cur, ("pending", "done"))
            adjusted_rows, already_planned = _apply_done_offset(rows, accounted_counts)

            by_material, items_without_dimensions = _classify_items(adjusted_rows)
            id_to_order = {r["id"]: r["order_number"] for r in rows}
            plans = _build_plans(cur, by_material, id_to_order)

            cur.execute(
                "INSERT INTO shop_cutting_plans (generated_by, statuses_filter, order_ids_filter) "
                "VALUES (%s, NULL, %s)",
                (admin["id"], ",".join(order_numbers)),
            )
            plan_id = cur.lastrowid

            # Zivy nalez (Robert, 2026-09-03, prvni pokus o rucni kus s
            # preklepnutym material_key "2500x1250" mista skutecneho klice
            # jako "mdf_8"): _build_plans uz umel oznacit material bez
            # aktivni skladove varianty jako "error", ale generate_cutting_plan
            # tenhle text ZAHAZOVAL - odpoved obsahovala jen obecne "Zadne
            # kusy k naplanovani", bez duvodu proc. Plati stejne pro polozky
            # objednavek se spatne nastavenym material_key na skladove karte,
            # ne jen pro nove rucni kusy - opraveno pro oba pripady najednou.
            plan_errors = [
                {"cut_kind": p["cut_kind"], "material_key": p["material_key"], "error": p["error"]}
                for p in plans if p.get("error")
            ]

            unit_count = 0
            for p in plans:
                if p.get("error"):
                    continue
                # `_build_plans` postavil `stock` pro pack_1d/pack_2d primo z
                # `shop_cutting_stock.id` (viz "id": s["id"] tamtez), takze
                # `group["stock_id"]` v ulozenem planu uz JE spravne DB id -
                # zadne dalsi dohledavani podle labelu neni potreba. Vyjimka:
                # ZAPORNE "stock_id" u profilu = zbytek (viz _build_plans,
                # "id": -r["id"]) - FK shop_cutting_plan_units.stock_id musi
                # ukazovat na existujici (kladny) shop_cutting_stock radek,
                # proto se tam ulozi "canonical_stock_id" a skutecny puvod
                # (a spravna delka/label pri cteni) jde pres remnant_id.
                groups = p["plan"].get("bars") or p["plan"].get("sheets") or []
                for idx, group in enumerate(groups, start=1):
                    raw_stock_id = group["stock_id"]
                    remnant_id = None
                    if p["cut_kind"] == "profil" and raw_stock_id < 0:
                        remnant_id = -raw_stock_id
                        stock_id = p["canonical_stock_id"]
                    else:
                        stock_id = raw_stock_id
                    if p["cut_kind"] == "profil":
                        used_amount, waste_amount = group["used_mm"], group["waste_mm"]
                    else:
                        used_amount, waste_amount = group["used_area_mm2"], group["waste_area_mm2"]
                    cur.execute(
                        "INSERT INTO shop_cutting_plan_units "
                        "(plan_id, cut_kind, material_key, stock_id, remnant_id, unit_index, pieces_json, "
                        " used_amount, waste_amount, kerf_mm, cuts_count, status) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')",
                        (plan_id, p["cut_kind"], p["material_key"], stock_id, remnant_id, idx,
                         json.dumps(group["pieces"], ensure_ascii=False), used_amount, waste_amount,
                         p["kerf_mm"], group["cuts"]),
                    )
                    new_unit_id = cur.lastrowid
                    if remnant_id is not None:
                        # zbytek prave "spotrebovan" timhle (novym) planem -
                        # nikdy uz se nenabidne DALSIMU generovani, dokud
                        # tahle jednotka existuje (viz bulk-delete nize pro
                        # vraceni, kdyz se jednotka smaze bez narezani).
                        cur.execute(
                            "UPDATE shop_cutting_remnants SET status='used', used_by_unit_id=%s, used_at=NOW() WHERE id=%s",
                            (new_unit_id, remnant_id),
                        )
                    unit_count += 1
            # Robert 2026-08 ("proc tam jsou rezne plany kdyz neni zadna
            # objednavka?"): kdyz nevznikla ZADNA jednotka (zadne
            # objednavky/kusy k narezani), prazdnou skorapku planu vubec
            # neukladat - drive se INSERT udelal vzdy a seznam planu se
            # plnil prazdnymi zaznamy pri kazdem kliknuti na Generovat.
            if unit_count == 0:
                conn.rollback()
                return jsonify({
                    "status": "empty", "plan_id": None, "units_created": 0,
                    "order_ids": order_ids,
                    "items_without_dimensions": items_without_dimensions,
                    "already_planned_skipped": already_planned,
                    "errors": plan_errors,
                    "message": "Žádné kusy k naplánování - plán nebyl vytvořen.",
                }), 200
            # bot4, 2026-07-26: nove vygenerovane pending jednotky mohou
            # patrit novym objednavkam bez barvy - priradit hned (viz
            # _sync_order_colors docstring, "barva podle zakázky").
            _sync_order_colors(cur)
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "status": "ok", "plan_id": plan_id, "units_created": unit_count,
        "order_ids": order_ids, "items_without_dimensions": items_without_dimensions,
        "already_planned_skipped": already_planned, "errors": plan_errors,
    }), 201


def _order_progress(cur, statuses):
    """Informativní přehled 'kolik kusů z objednávky je nařezáno' - podle
    Roberta JEN informativní štítek, žádná vazba na stav objednávky.
    total = součet qty přes cut_kind položky s vyplněnými rozměry, done =
    kolik z nich už je v nějaké 'done' jednotce."""
    placeholders = ",".join(["%s"] * len(statuses))
    cur.execute(
        f"SELECT oi.id, oi.qty, oi.cut_kind, oi.length_mm, oi.width_mm, oi.height_mm, "
        f"       o.order_number "
        f"FROM shop_order_items oi JOIN shop_orders o ON o.id = oi.order_id "
        f"WHERE o.status IN ({placeholders}) AND oi.cut_kind IS NOT NULL",
        statuses,
    )
    rows = cur.fetchall()
    done_counts = _done_piece_counts(cur)

    by_order = {}
    for r in rows:
        has_dims = (r["cut_kind"] == "profil" and r["length_mm"]) or \
                   (r["cut_kind"] == "deska" and r["width_mm"] and r["height_mm"])
        if not has_dims:
            continue
        entry = by_order.setdefault(r["order_number"], {"order_number": r["order_number"], "total": 0, "done": 0})
        entry["total"] += r["qty"]
        entry["done"] += min(r["qty"], done_counts.get(r["id"], 0))
    return sorted(by_order.values(), key=lambda e: e["order_number"])


@app.get("/api/admin/cutting-plan")
@require_permission("rezne_plany", "zobrazit")
def bulk_cutting_plan():
    """
    HLAVNÍ provozní pohled (viz Robert 2026-07-25/26) - čte PERZISTENTNÍ
    jednotky uložené posledním `POST .../generate` (NEPOČÍTÁ nic nově -
    pro přepočet/doplnění nových objednávek zavolej generate). Vrací
    jednotky seskupené podle materiálu, každá s `pieces` (obsahují
    `order_number` z doby vygenerování) a `status` (pending/done).

    ?status=pending - jen nedokončené jednotky (výchozí: všechny).
    ?plan_id=<id> - jen jednotky z jednoho konkrétního plánu (např. pro
    zobrazení výsledku "Ruční kusy" bez zásahu do sdíleného přehledu).
    """
    status_filter = request.args.get("status")
    if status_filter and status_filter not in ("pending", "done"):
        return jsonify({"error": "status musí být 'pending' nebo 'done'."}), 400
    plan_id_filter = request.args.get("plan_id")
    if plan_id_filter is not None:
        try:
            plan_id_filter = int(plan_id_filter)
        except ValueError:
            return jsonify({"error": "plan_id musí být celé číslo."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # LEFT JOIN na shop_cutting_remnants - jednotka narezana ze
            # ZBYTKU (u.remnant_id NOT NULL) ma skutecnou delku/label z
            # rezervovaneho zbytku, ne z kanonickeho (3000mm) skladoveho
            # radku, na ktery u.stock_id kvuli FK porad ukazuje (viz
            # generate_cutting_plan - "canonical_stock_id" fallback).
            sql = (
                "SELECT u.*, "
                "COALESCE(r.length_mm, s.stock_length_mm) AS stock_length_mm, "
                "s.stock_width_mm, s.stock_height_mm, "
                "CASE WHEN r.id IS NOT NULL THEN CONCAT('Zbytek ', r.length_mm, ' mm') ELSE s.label END AS stock_label, "
                "(r.id IS NOT NULL) AS is_remnant "
                "FROM shop_cutting_plan_units u "
                "JOIN shop_cutting_stock s ON s.id = u.stock_id "
                "LEFT JOIN shop_cutting_remnants r ON r.id = u.remnant_id"
            )
            params = []
            where = []
            if status_filter:
                where.append("u.status=%s")
                params.append(status_filter)
            if plan_id_filter is not None:
                where.append("u.plan_id=%s")
                params.append(plan_id_filter)
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY u.cut_kind, u.material_key, u.unit_index"
            cur.execute(sql, params)
            unit_rows = cur.fetchall()

            # Celkovy pocet jednotek NA MATERIAL (bez ohledu na filtr) -
            # potreba pro "Tabule: X/Y" v hlavicce (Y = pocet VSECH tabuli
            # v tehle materialove skupine, ne jen zobrazenych po filtru).
            cur.execute(
                "SELECT cut_kind, material_key, COUNT(*) AS n "
                "FROM shop_cutting_plan_units GROUP BY cut_kind, material_key"
            )
            total_per_material = {(r["cut_kind"], r["material_key"]): r["n"] for r in cur.fetchall()}

            order_progress = _order_progress(cur, list(UNFINISHED_STATUSES))
            # bot4, 2026-07-26: "barva podle zakázky" - viz _sync_order_colors
            # docstring. GET je te ted taky misto zapisu (prirazeni/uvolneni
            # barev), proto commit nize (predtim byl endpoint cistě cteci).
            order_colors = _sync_order_colors(cur)
        conn.commit()
    finally:
        conn.close()

    by_material = {}
    for u in unit_rows:
        key = (u["cut_kind"], u["material_key"])
        group = by_material.setdefault(key, {
            "cut_kind": u["cut_kind"], "material_key": u["material_key"],
            "unit_count_total": total_per_material.get(key, 0),
            "units": [],
        })

        stock_length = float(u["stock_length_mm"]) if u["stock_length_mm"] is not None else None
        stock_width = float(u["stock_width_mm"]) if u["stock_width_mm"] is not None else None
        stock_height = float(u["stock_height_mm"]) if u["stock_height_mm"] is not None else None
        used_amount = float(u["used_amount"]) if u["used_amount"] is not None else None
        stock_amount = stock_length if u["cut_kind"] == "profil" else (
            stock_width * stock_height if stock_width is not None and stock_height is not None else None
        )
        utilization_percent = (
            round(used_amount / stock_amount * 100, 1) if used_amount is not None and stock_amount else None
        )
        pieces = _load_pieces_json(u["pieces_json"])
        # "Zakazka" (Robert, 2026-07-26, dle referencniho nahledu CAM
        # softwaru) - odvozeno z order_number kusu na teto tyci/desce, ne
        # samostatny sloupec v DB (uz je to v pieces_json od generovani).
        order_numbers = sorted({p.get("order_number") for p in pieces if p.get("order_number")})
        zakazka = order_numbers[0] if len(order_numbers) == 1 else (
            f"{len(order_numbers)} zakázek: " + ", ".join(order_numbers) if order_numbers else None
        )

        group["units"].append({
            "id": u["id"], "unit_index": u["unit_index"], "unit_count_total": total_per_material.get(key, 0),
            "status": u["status"],
            "stock_label": u["stock_label"], "is_remnant": bool(u["is_remnant"]),
            "stock_length_mm": stock_length, "stock_width_mm": stock_width, "stock_height_mm": stock_height,
            "pieces": pieces,
            "zakazka": zakazka,
            "used_amount": used_amount,
            "waste_amount": float(u["waste_amount"]) if u["waste_amount"] is not None else None,
            "utilization_percent": utilization_percent,
            "kerf_mm": float(u["kerf_mm"]) if u["kerf_mm"] is not None else None,
            "cuts_count": u["cuts_count"],
            "done_at": u["done_at"].isoformat() if u["done_at"] else None,
            "done_by": u["done_by"],
        })

    return jsonify({
        "materials": list(by_material.values()),
        "order_progress": order_progress,
        "order_colors": order_colors,
    })


def _spawn_remnant_if_applicable(cur, unit):
    """Po odskrtnuti tyce jako 'hotovo' zaeviduj vznikly ZBYTEK (Robert
    2026-08-06: "zásoba zbytků vzniklých řezáním") - jen pro
    cut_kind='profil' a jen pokud je zbytek aspon MIN_REMNANT_LENGTH_MM
    (kratsi uz neni k nicemu, jde rovnou do odpadu, do
    shop_cutting_remnants se nezaklada). `unit` musi byt cely radek
    shop_cutting_plan_units (dict). Idempotentni vuci opakovanemu volani
    pro stejnou jednotku (kontrola existujici source_unit_id) - relevantni
    pro bulk-status, kde muze byt jednotka "done" i pri opakovanem
    hromadnem odeslani stejneho vyberu."""
    if unit["cut_kind"] != "profil":
        return
    waste = float(unit["waste_amount"] or 0)
    if waste < MIN_REMNANT_LENGTH_MM:
        return
    cur.execute("SELECT id FROM shop_cutting_remnants WHERE source_unit_id=%s", (unit["id"],))
    if cur.fetchone():
        return
    cur.execute(
        "INSERT INTO shop_cutting_remnants (cut_kind, material_key, length_mm, status, source_unit_id) "
        "VALUES ('profil', %s, %s, 'available', %s)",
        (unit["material_key"], waste, unit["id"]),
    )


def _undo_remnant_if_applicable(cur, unit_id):
    """Protejsek k _spawn_remnant_if_applicable - pri vraceni tyce
    z 'hotovo' zpatky na 'pending' smaz zbytek, ktery z ni vznikl, POKUD
    uz mezitim nebyl spotrebovan v jinem (novejsim) planu (status=
    'available' - jinak by smazani osirelo cizi jiz vygenerovanou
    jednotku, ktera na nej ukazuje pres remnant_id)."""
    cur.execute(
        "DELETE FROM shop_cutting_remnants WHERE source_unit_id=%s AND status='available'",
        (unit_id,),
    )


@app.patch("/api/admin/cutting-plan/units/<int:unit_id>")
@require_permission("rezne_plany", "upravit")
def update_cutting_plan_unit(unit_id):
    """Odškrtnutí na dílně: {"status": "done"} po nařezání tyče/desky,
    {"status": "pending"} pro vrácení omylem odškrtnuté jednotky.

    U profilu navic (Robert 2026-08-06): prechod na 'done' zaeviduje
    vznikly zbytek do zasoby (_spawn_remnant_if_applicable), prechod
    zpatky na 'pending' ho zase odebere, pokud uz nebyl spotrebovan
    (_undo_remnant_if_applicable)."""
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    if new_status not in ("pending", "done"):
        return jsonify({"error": "status musí být 'pending' nebo 'done'."}), 400

    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_cutting_plan_units WHERE id=%s", (unit_id,))
            unit = cur.fetchone()
            if not unit:
                conn.rollback()
                return jsonify({"error": "Jednotka neexistuje."}), 404
            if new_status == "done":
                cur.execute(
                    "UPDATE shop_cutting_plan_units SET status='done', done_at=NOW(), done_by=%s WHERE id=%s",
                    (admin["id"], unit_id),
                )
                if unit["status"] != "done":
                    _spawn_remnant_if_applicable(cur, unit)
            else:
                cur.execute(
                    "UPDATE shop_cutting_plan_units SET status='pending', done_at=NULL, done_by=NULL WHERE id=%s",
                    (unit_id,),
                )
                if unit["status"] == "done":
                    _undo_remnant_if_applicable(cur, unit_id)
            # bot4, 2026-07-26: odskrtnuti muze byt posledni pending kus
            # dane objednavky - hned uvolnit/prirazuje barvu (viz
            # _sync_order_colors docstring), ne az pri pristim GET.
            _sync_order_colors(cur)
        conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/admin/cutting-plan/units/bulk-status")
@require_permission("rezne_plany", "upravit")
def bulk_update_cutting_plan_units():
    """Hromadne odskrtnuti/vraceni vice tyci/desek najednou (dilna
    casto oznacuje cely material naraz, ne kus po kusu - viz stejny
    pozadavek jako u jednotlive PATCH varianty vyse). Jeden UPDATE ...
    WHERE id IN (...), ale zbytky (viz _spawn_remnant_if_applicable/
    _undo_remnant_if_applicable) uz je potreba resit PO JEDNOM radku,
    proto se pred UPDATE nactou puvodni stavy vsech dotcenych jednotek."""
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    new_status = body.get("status")
    if new_status not in ("pending", "done"):
        return jsonify({"error": "status musí být 'pending' nebo 'done'."}), 400

    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT * FROM shop_cutting_plan_units WHERE id IN ({placeholders})", ids)
            units_before = cur.fetchall()
            if new_status == "done":
                cur.execute(
                    f"UPDATE shop_cutting_plan_units SET status='done', done_at=NOW(), done_by=%s WHERE id IN ({placeholders})",
                    (admin["id"], *ids),
                )
                updated = cur.rowcount
                for u in units_before:
                    if u["status"] != "done":
                        _spawn_remnant_if_applicable(cur, u)
            else:
                cur.execute(
                    f"UPDATE shop_cutting_plan_units SET status='pending', done_at=NULL, done_by=NULL WHERE id IN ({placeholders})",
                    ids,
                )
                updated = cur.rowcount
                for u in units_before:
                    if u["status"] == "done":
                        _undo_remnant_if_applicable(cur, u["id"])
            _sync_order_colors(cur)
        conn.commit()
    finally:
        conn.close()

    log_audit(
        admin["id"], "bulk_status", "cutting_plan_unit", None,
        f"{updated} jednotek řezného plánu → {new_status}",
    )
    return jsonify({"status": "ok", "updated": updated})


@app.post("/api/admin/cutting-plan/units/bulk-delete")
@require_permission("rezne_plany", "upravit")
def bulk_delete_cutting_plan_units():
    """Hromadne SMAZANI vybranych jednotek (tyci/desek) rezneho planu
    (Robert 2026-08: "dej reznym planum bulk mazani"). Po smazani
    jednotek se rovnou uklidi i vsechny plany, kterym uz nezbyla ZADNA
    jednotka (vcetne historickych prazdnych skorapek z drivejska, kdy
    Generovat vytvarel plan i bez jedine jednotky) - prazdny plan nema
    zadnou informacni hodnotu a v seznamu jen mate.

    Zbytky (Robert 2026-08-06): mazane jednotky mohly (a) SPOTREBOVAT
    zbytek pri generovani (remnant_id) - ten se vrati zpet mezi dostupne,
    protoze planovana tyc uz nikdy nevznikne; (b) SAMY byt zdrojem zbytku
    (jiny radek v shop_cutting_remnants ma jejich id v source_unit_id,
    pokud uz byly drive "done") - pokud ten zbytek jeste nikdo nepouzil,
    zanikne s nimi (FK ON DELETE SET NULL je jen zaloha pro pripad, ze uz
    byl mezitim pouzity v jinem planu - takovy zbytek zustava platny)."""
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err

    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(
                f"UPDATE shop_cutting_remnants SET status='available', used_by_unit_id=NULL, used_at=NULL "
                f"WHERE used_by_unit_id IN ({placeholders})",
                ids,
            )
            cur.execute(
                f"DELETE FROM shop_cutting_remnants WHERE source_unit_id IN ({placeholders}) AND status='available'",
                ids,
            )
            cur.execute(
                f"DELETE FROM shop_cutting_plan_units WHERE id IN ({placeholders})",
                ids,
            )
            deleted = cur.rowcount
            cur.execute(
                "DELETE FROM shop_cutting_plans WHERE id NOT IN "
                "(SELECT DISTINCT plan_id FROM shop_cutting_plan_units)"
            )
            empty_plans_deleted = cur.rowcount
            _sync_order_colors(cur)
        conn.commit()
    finally:
        conn.close()

    log_audit(
        admin["id"], "bulk_delete", "cutting_plan_unit", None,
        f"{deleted} jednotek řezného plánu smazáno (+ {empty_plans_deleted} prázdných plánů uklizeno)",
    )
    return jsonify({"status": "ok", "deleted": deleted, "empty_plans_deleted": empty_plans_deleted})


@app.get("/api/admin/cutting-plan/remnants")
@require_permission("rezne_plany", "zobrazit")
def cutting_remnants_list():
    """
    Prehled zasoby zbytku (Robert 2026-08-06: "bude se držet databáze
    zbytků") - "available" jsou volne pouzitelne v pristim generovani,
    "used" uz jsou rezervovane/spotrebovane konkretni (pending/done)
    jednotkou (viz used_by_unit_id -> shop_cutting_plan_units.id).

    ?status=available|used - volitelny filtr, jinak vse.
    """
    status_filter = request.args.get("status")
    if status_filter and status_filter not in ("available", "used"):
        return jsonify({"error": "status musí být 'available' nebo 'used'."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM shop_cutting_remnants"
            params = []
            if status_filter:
                sql += " WHERE status=%s"
                params.append(status_filter)
            sql += " ORDER BY material_key, length_mm DESC"
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    return jsonify({"remnants": [
        {
            "id": r["id"], "cut_kind": r["cut_kind"], "material_key": r["material_key"],
            "length_mm": float(r["length_mm"]), "status": r["status"],
            "source_unit_id": r["source_unit_id"], "used_by_unit_id": r["used_by_unit_id"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "used_at": r["used_at"].isoformat() if r["used_at"] else None,
        }
        for r in rows
    ]})


@app.delete("/api/admin/cutting-plan/remnants/<int:remnant_id>")
@require_permission("rezne_plany", "upravit")
def cutting_remnant_delete(remnant_id):
    """Rucni odebrani zbytku ze zasoby (fyzicky ztracen/vyhozen/uz
    nepouzitelny) - jen pokud jeste neni rezervovany zadnym planem."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM shop_cutting_remnants WHERE id=%s", (remnant_id,))
            r = cur.fetchone()
            if not r:
                conn.rollback()
                return jsonify({"error": "Zbytek neexistuje."}), 404
            if r["status"] != "available":
                conn.rollback()
                return jsonify({"error": "Zbytek je už použitý v jiném plánu, nelze ho smazat."}), 400
            cur.execute("DELETE FROM shop_cutting_remnants WHERE id=%s", (remnant_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.get("/api/admin/orders/<int:order_id>/cutting-plan")
@require_permission("rezne_plany", "zobrazit")
def order_cutting_plan(order_id):
    """
    DIAGNOSTICKÝ/náhledový endpoint pro JEDNU objednávku - NENÍ hlavní
    provozní tok (ten je `GET /api/admin/cutting-plan` výše, hromadně za
    všechny nevyřízené objednávky, viz Robert 2026-07-25). Užitečné pro
    rychlou kontrolu "co přesně je v TÉTO objednávce k řezání", bez
    míchání s ostatními objednávkami.
    """
    conn = get_conn()
    try:
        order, items = _fetch_order_with_items(conn, order_id)
        if not order:
            return jsonify({"error": "Objednávka neexistuje."}), 404

        for it in items:
            it["order_number"] = order["order_number"]
        by_material, items_without_dimensions = _classify_items(items)
        id_to_order = {it["id"]: order["order_number"] for it in items}

        with conn.cursor() as cur:
            plans = _build_plans(cur, by_material, id_to_order)
    finally:
        conn.close()

    return jsonify({
        "order_id": order_id,
        "order_number": order["order_number"],
        "plans": plans,
        "items_without_dimensions": items_without_dimensions,
    })
