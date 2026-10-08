"""
Kosik - bot3, 2026-07-25 (v2).

Robert: rozhodnuto, ze UI kosiku postavi bot2 (oblast UI), tenhle modul je
jen backend/API vrstva pod tim - persistentni kosik navazany na
PRIHLASENEHO uzivatele (guest kosik zamerne neni, protoze objednavku uz
jde od 2026-07-25 zadat jen po prihlaseni - viz orders.py a AGENTS_LOG.md).
Diky tomu je model jednoduchy - 1 radek shop_cart_items = 1 produkt v
kosiku daneho uzivatele, zadna potreba resit guest token/cookie ani
mergovani kosiku pri prihlaseni.

Aktivace: stejna konvence jako orders.py (zadne Blueprints). Na konec
app.py pridat (za `import orders`):

    import cart  # noqa: F401 - registruje /api/cart

Vyzaduje uz nasazenou migraci 2026-07-25_orders_v2_customers_cart_shipping.sql
(tabulka shop_cart_items).

Endpointy (vsechny @login_required):
  GET    /api/cart                 - obsah kosiku + mezisoucet
  POST   /api/cart/items           - pridat produkt (nebo navysit mnozstvi, pokud uz v kosiku je)
  PUT    /api/cart/items/<id>      - zmenit mnozstvi polozky (qty<=0 = smazat)
  DELETE /api/cart/items/<id>      - smazat 1 polozku
  DELETE /api/cart                 - vyprazdnit cely kosik

Kosik NEKONTROLUJE dostupnost skladem pri pridavani (produkt muze byt
pridan i kdyz je prave vyprodany - beznea eshop chovani, "hlidani skladu"
resi az /api/orders pri skutecnem odeslani objednavky, ktere FOR UPDATE
zamkne radky a odmitne, pokud sklad nestaci). Kosik jen doplnuje aktualni
`stock_qty`/`active`/`is_archived` stav produktu do odpovedi, aby UI mohlo
zobrazit varovani (napr. "produkt jiz neni dostupny").

Prirezy profilu (bot3, 2026-08-06, viz api/app.py cut-plan-preview
docstring pro cely kontext): POST /api/cart/items smi navic nest
"cut_pieces" ([{"length_mm","qty"}, ...]) - server si sam (nevericky
klientovi) dopocita pocet celych tyci (cutting_algo.pack_1d, stejna
cesta jako preview endpoint) a ulozi ho jako `qty`. Invariant "pocet ks
nikdy nesmi klesnout pod to, co prirezy potrebuji" (Robert) je vynucen
i v PUT (viz cart_update_item) - snizeni qty pod minimum se tise
zvedne zpet.
"""
import json

from flask import request, jsonify

from app import (
    app, get_conn, login_required, current_user, require_permission,
    parse_bulk_ids, log_audit, get_setting,
)
from products import (
    _validate_cut_pieces, _rods_needed_for_cuts, _cut_service_price_czk, _waste_breakdown,
    _effective_unit_price, _validate_cut_pieces_2d, _sheets_needed_for_cuts, now_local,
    cena_desky,
)
from product_assemblies import _assembly_price_components, _montaz_mista_map


# Horni mez mnozstvi na radek (bot16, 2026-09-03, revize bot3 - W2): bez
# ni koncilo qty=10**10 na INT sloupci DataError 1264 -> 500 s prazdnym
# telem. Plati pro qty, extra_whole_qty i PUT.
CART_MAX_QTY = 9999

# bot5, 2026-09-28 (Robert primo: "potřebuji aby když jsem přihlašený
# jako admin, aby tentýž košík mohl sdílet a pridávat položky... i
# tento email logiman.sklad@seznam.cz") - RUCNI, explicitni mapa jen
# pro vyjmenovane ucty (email -> kanonicky vlastnik kosiku), zadny DB
# dotaz tady zamerne: get_conn() je thread-local pooled/1 spojeni na
# thread, kazdy volajici (cart_get/cart_add_item/...) uz ma VLASTNI
# otevrene spojeni/transakci - druhe volani get_conn() UPROSTRED by
# vratilo TOTOZNE spojeni a jeho .close() by predcasne zakomitoval/
# rozbil prave probihajici transakci (pooled-conn past, viz
# AGENTS_LOG.md). Kazdy JINY uzivatel/zakaznik ma kosik dal presne
# per-svuj user_id jako drive - tohle je vyjimka jen pro tyto ucty.
CART_SHARED_OWNER_ID = {
    "mandik@logiman.cz": 1,
    "logiman.sklad@seznam.cz": 1,
}


def _cart_owner_id(user):
    email = (user.get("email") or "").strip().lower()
    return CART_SHARED_OWNER_ID.get(email, user["id"])


def _money(v):
    return float(v) if v is not None else 0.0


def _parse_cut_pieces(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _serialize_cart(rows):
    items = []
    subtotal = 0.0
    total_qty = 0
    for r in rows:
        unit_price = _money(r["unit_price_czk"])
        line_total = round(unit_price * r["qty"], 2)
        # Rezy jako samostatna castka (Robert 2026-08-06: "vždy když
        # klient zadá přířezy je nutné do objenávky přidat automaticky
        # řezy, musí figurovat v košíku") - pricita se do mezisouctu
        # jako skutecna cast ceny objednavky, ne jen informativni radek.
        cut_service_qty = r.get("cut_service_qty")
        cut_service_unit_price = r.get("cut_service_unit_price_czk")
        cut_service_total = round(cut_service_qty * cut_service_unit_price, 2) if cut_service_qty and cut_service_unit_price is not None else None
        subtotal += line_total + (cut_service_total or 0)
        total_qty += r["qty"]
        items.append({
            "id": r["id"],
            "product_id": r["product_id"],
            "sku": r["sku"],
            "name": r["name"],
            "unit_price_czk": unit_price,
            "price_basis": r.get("price_basis"),
            # Puvodni cena bez slevy (Robert 2026-08-08: "prihlaseny mající
            # rámcovou slevu... uvidi take cenu ponizenou podle sve
            # skupiny a totez uvidi v kosiku, obe ceny, ale v součtu
            # kosiku už bude figurovat ta nižší") - frontend vedle sebe
            # ukaze puvodni (preskrtnutou) i efektivni cenu, kdyz se lisi;
            # subtotal/line_total pocitane vyse pouziva VZDY jen
            # unit_price_czk (efektivni), tohle pole je jen pro zobrazeni.
            "price_czk_placeholder": _money(r.get("price_czk_placeholder")),
            "coupon_code": r.get("coupon_code"),
            "qty": r["qty"],
            "cut_pieces": _parse_cut_pieces(r.get("cut_pieces_json")),
            # Profil (fyzicky prutahovany material, viz cfg_dily_id) se
            # vzdy prodava po celych 3000mm tycich, i kdyz zakaznik nezadal
            # zadne prirezy - stejny signal jako "isProfile" v product.html
            # (Robert 2026-08-08: "u profilů bez přířezu též uvádějme že
            # se jedná o tyč 3000mm").
            # POZOR: is_board_material se testuje jako VYLUCUJICI prvni -
            # desky (napr. PR10) maji casto nastavene i cfg_dily_id (kvuli
            # 3D scene/hmotnosti), takze "je to profil" NENI proste
            # bool(cfg_dily_id).
            "is_profile": bool(r.get("is_profile_material")) and not r.get("is_board_material"),
            "is_board": bool(r.get("is_board_material")),
            "cut_service_qty": cut_service_qty,
            "cut_service_unit_price_czk": cut_service_unit_price,
            "cut_service_total_czk": cut_service_total,
            "waste_breakdown": r.get("waste_breakdown"),
            "line_total_czk": line_total,
            "stock_qty": r["stock_qty"],
            "active": bool(r["active"]),
            "is_archived": bool(r["is_archived"]),
            "image_url": f"/content-files/gallery/{r['image_filename']}" if r.get("image_filename") else None,
            # Varianta sestavy + volby "montáž"/"bez boxů" (Robert
            # 2026-09-13) - `assembly_id` 0 (DB default) se ven posila
            # jako None, aby frontend mel jednoduchou "ma variantu?"
            # podminku (`if item.assembly_id`), ne "!== 0".
            "assembly_id": r["assembly_id"] or None,
            "montaz_zvolena": bool(r.get("montaz_zvolena")),
            "montaz_czk": _money(r.get("assembly_montaz_czk")) if r.get("assembly_montaz_czk") is not None else None,
            # Misto montaze (Robert pres bot16, 2026-09-13: povinny vyber,
            # dnes editovatelny katalog montaz_mista) - kod i popisek,
            # predpocitane v _fetch_cart_rows (viz misto_labels tam).
            "montaz_misto": r.get("montaz_misto"),
            "montaz_misto_label": r.get("montaz_misto_label"),
            "bez_boxu": bool(r.get("bez_boxu")),
            "boxy_czk": _money(r.get("assembly_boxy_czk")) if r.get("assembly_boxy_czk") is not None else None,
            # bot5, 2026-10-02: konfigurace sestavy - vyroba na zakazku: bez skladu, `configuration` = overeny vyber, kod, souhrn voleb a stav (valid, changed), viz api/konfigurace_kosik.py
            "made_to_order": bool(r.get("made_to_order")),
            "configuration": r.get("configuration"),
        })
    return {
        "items": items,
        "subtotal_czk": round(subtotal, 2),
        "item_count": len(items),
        "total_qty": total_qty,
    }


def _fetch_cart_rows(conn, user_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ci.id, ci.product_id, ci.qty, ci.cut_pieces_json, ci.cut_service_qty, ci.coupon_code, "
            "       ci.assembly_id, ci.montaz_zvolena, ci.bez_boxu, ci.montaz_misto, ci.configuration_json, ci.config_hash, "
            "       p.sku, p.name, p.price_czk_placeholder, p.cfg_dily_id, p.is_board_material, p.is_profile_material, "
            "       p.supplier_name, "
            # unit + rozmery tabule: deska muze mit cenu ulozenou za m2 i za
            # celou tabuli a radek kosiku se nasobi POCTEM TABULI (cena_desky).
            "       p.unit, p.board_sheet_width_mm, p.board_sheet_height_mm, "
            "       p.dealer_discount_percent, p.sale_price_czk, p.sale_price_from, p.sale_price_until, "
            "       p.stock_qty, p.active, p.is_archived, "
            # Nahledovy obrazek (Robert 2026-08-06, kosik jako "vicekrokovy
            # wizard v designu online nabidky" - tabulka polozek potrebuje
            # miniaturu, stejny vzor jako shop_products_get() v api/app.py).
            "       (SELECT filename FROM shop_product_images WHERE product_id=p.id ORDER BY sort_order, id LIMIT 1) AS image_filename "
            "FROM shop_cart_items ci JOIN shop_products p ON p.id = ci.product_id "
            "WHERE ci.user_id=%s ORDER BY ci.added_at ASC",
            (user_id,),
        )
        rows = cur.fetchall()
        # Popisky mist montaze - JEDEN dotaz pro celý košík (ne N dotazů
        # v cyklu níže), _serialize_cart uz nemá otevřené spojení (viz
        # cart_get - conn.close() před voláním), takže label musí být
        # předpočítaný TADY.
        misto_labels = _montaz_mista_map(cur, jen_aktivni=False)
        # Cena za rez (Robert: "ceny řezů jsou v adminu u cen profilů") se
        # NEUKLADA na radek kosiku - dopocitava se VZDY ZIVA z
        # cfg_dily.price_per_cut_czk, aby zmena ceny v adminu platila i
        # pro uz rozpracovany kosik (stejny princip jako unit_price_per_m_czk
        # v api/app.py::shop_products_get).
        for r in rows:
            if r.get("config_hash"):
                # bot5, 2026-10-02: konfigurace sestavy: vlastni ZIVE pocitani ceny a stavu, viz api/konfigurace_kosik.py (lazy import: poradi importu v app.py). Chyba nesmi rozbit cely kosik:
                # radek se pak ukaze jako neplatny (bez ceny) a objednavka ho odmitne.
                try:
                    import konfigurace_kosik
                    konfigurace_kosik.priprav_radek_kosiku(cur, r, user_id)
                except Exception:
                    getattr(app, "logger", None) and app.logger.exception("cart: radek s konfiguraci se nepodarilo spocitat")
                    r.update({"cut_service_unit_price_czk": None, "assembly_montaz_czk": None, "assembly_boxy_czk": None, "waste_breakdown": None, "montaz_misto_label": None,
                              "stock_qty": None, "unit_price_czk": None, "price_basis": None, "price_czk_placeholder": None, "made_to_order": True,
                              "configuration": {"valid": False, "error": "internal_error", "kod": None, "hash": r.get("config_hash"), "changed": False, "summary": [],
                                                "weight_kg": None, "montaz_pct": None, "errors": []}})
                continue
            r["montaz_misto_label"] = misto_labels.get(r.get("montaz_misto"))
            if r.get("cut_service_qty"):
                r["cut_service_unit_price_czk"] = _cut_service_price_czk(cur, r.get("cfg_dily_id"))
            else:
                r["cut_service_unit_price_czk"] = None
            # Cenova hierarchie (Robert 2026-08-08: "dealerska sleva...
            # akcni cena... kuponovy system") - ZIVA, stejny duvod jako
            # cena za rez vyse (zmena v adminu plati i pro rozpracovany
            # kosik). Kupon zustava ulozeny na radku kosiku (na rozdil od
            # ceny) - viz sql/2026-08-08_cart_coupon_code.sql.
            #
            # Varianta sestavy (Robert 2026-09-13) - kdyz radek nese
            # `assembly_id`, dealerska sleva/akcni cena/kupon se pocitaji
            # ze ZAKLADNI CENY VYBRANE VARIANTY (price_summary.total_czk),
            # NE z p.price_czk_placeholder (to je cena ZASTUPCE karty -
            # bez tohohle by kosik VZDY ukazal cenu zastupce, bez ohledu
            # na to, kterou variantu si zakaznik na detailu vybral). Cena
            # montaze/odectena cena boxu se pricitaji/odecitaji AZ PO
            # teto hierarchii - nejsou to slevy, jsou to samostatne
            # sluzby/slozky (TEXT_FILTR.md pravidlo 14a).
            r["assembly_montaz_czk"] = None
            r["assembly_boxy_czk"] = None
            base_placeholder = r["price_czk_placeholder"]
            if r.get("assembly_id"):
                assembly_ceny = _assembly_price_components(
                    cur, r["assembly_id"], r["product_id"],
                    float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None,
                )
                if assembly_ceny is not None and assembly_ceny["base_czk"] is not None:
                    base_placeholder = assembly_ceny["base_czk"]
                    r["assembly_montaz_czk"] = assembly_ceny["montaz_czk"]
                    r["assembly_boxy_czk"] = assembly_ceny["boxy_czk"]
            elif r.get("supplier_name") == "vanDrawee" and base_placeholder is not None:
                # Montaz jako procento z ceny sestavy (Robert 2026-09-18) -
                # viz komentar u is_supplier_montaz v cart_items_post() vyse,
                # zadna realna geometrie/misto montaze u techto karet.
                # Procento editovatelne v adminu (Koeficienty cen), NE
                # napevno - viz api/admin_settings.py vandrawee_montaz_pct.
                vd_pct = get_setting(cur, "vandrawee_montaz_pct", "20")
                r["assembly_montaz_czk"] = round(float(base_placeholder) * float(vd_pct) / 100.0, 2)
            # Prepis "puvodni ceny pro zobrazeni" (viz price_czk_placeholder
            # v _serialize_cart) na skutecny zaklad TOHOTO radku - u
            # assembly radku by jinak frontend ukazal preskrtnutou cenu
            # ZASTUPCE karty, ne vybrane varianty.
            r["price_czk_placeholder"] = base_placeholder
            product_for_pricing = {
                "id": r["product_id"], "price_czk_placeholder": base_placeholder,
                "dealer_discount_percent": r.get("dealer_discount_percent"),
                "sale_price_czk": r.get("sale_price_czk"),
                "sale_price_from": r.get("sale_price_from"), "sale_price_until": r.get("sale_price_until"),
            }
            r["unit_price_czk"], r["price_basis"] = _effective_unit_price(
                cur, product_for_pricing, user={"id": user_id}, coupon_code=r.get("coupon_code"),
            )
            if r.get("bez_boxu") and r["assembly_boxy_czk"]:
                r["unit_price_czk"] = round(r["unit_price_czk"] - r["assembly_boxy_czk"], 2)
            if r.get("montaz_zvolena") and r["assembly_montaz_czk"]:
                r["unit_price_czk"] = round(r["unit_price_czk"] + r["assembly_montaz_czk"], 2)
            # DESKA: `qty` je pocet CELYCH TABULI (_sheets_needed_for_cuts),
            # takze `unit_price_czk` musi byt cena za tabuli. U desky s
            # unit='m2' je ale ulozena cena za metr ctverecni a radek by
            # vysel na sestinu - viz cena_desky() v products.py.
            if r.get("is_board_material"):
                r["unit_price_czk"], r["unit_price_per_m2_czk"] = cena_desky({
                    "is_board_material": True,
                    "unit": r.get("unit"),
                    "board_sheet_width_mm": r.get("board_sheet_width_mm"),
                    "board_sheet_height_mm": r.get("board_sheet_height_mm"),
                }, r["unit_price_czk"])
            # Zbytky z tyci patri klientovi (Robert) - kolik dlouhych a v
            # jakych poctech se dopocitava ZIVA ze zadanych prirezu, stejny
            # duvod jako u ceny za rez vyse (2026-08-06: "doplňujme vždy
            # jak dlouhé zbytky dostane klient a v jakých počtech"). Jen
            # profily (1D tyc) - u desek (2D) tenhle "zbytek klientovi"
            # koncept zatim neresime (viz plan 2026-08-08), waste_breakdown
            # zustava None.
            cut_pieces = _parse_cut_pieces(r.get("cut_pieces_json"))
            # POZOR: desky (napr. PR10) maji casto nastavene i cfg_dily_id
            # (kvuli 3D scene/hmotnosti) - "is profil" tedy NENI proste
            # bool(cfg_dily_id), musi vyloucit is_board_material, jinak by
            # se 2D prirezy desky poslaly do 1D _rods_needed_for_cuts a
            # spadly na chybejicim length_mm.
            if cut_pieces and r.get("is_profile_material") and not r.get("is_board_material"):
                _, plan = _rods_needed_for_cuts(cut_pieces)
                r["waste_breakdown"] = _waste_breakdown(plan)
            else:
                r["waste_breakdown"] = None
        return rows


@app.get("/api/cart")
@login_required
def cart_get():
    user = current_user()
    conn = get_conn()
    try:
        rows = _fetch_cart_rows(conn, _cart_owner_id(user))
    finally:
        conn.close()
    return jsonify(_serialize_cart(rows))


@app.post("/api/cart/items")
@login_required
def cart_add_item():
    # Robert 2026-08-18: docasna deaktivace kosiku (reverzibilni
    # app_settings priznak, viz api/app.py admin_settings_get/set) -
    # skutecne vynuceni tady na backendu, ne jen schovane tlacitko v UI
    # (to by slo obejit primym API volanim). GET/PUT/DELETE zustavaji
    # funkcni beze zmeny - kdo uz neco v kosiku ma, muze si to dal
    # prohlizet/upravovat/odebrat, jen NOVE pridani je blokovane.
    conn_flag = get_conn()
    try:
        with conn_flag.cursor() as cur_flag:
            cart_enabled = get_setting(cur_flag, "cart_enabled", "1") != "0"
    finally:
        conn_flag.close()
    if not cart_enabled:
        return jsonify({"error": "Košík je dočasně nedostupný."}), 403

    user = current_user()
    cart_owner_id = _cart_owner_id(user)
    body = request.get_json(silent=True) or {}
    try:
        product_id = int(body.get("product_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné product_id."}), 400
    # bot5, 2026-10-02: konfigurace sestavy: server vyber znovu overi a cenu spocita sam, viz api/konfigurace_kosik.py (lazy import: poradi importu v app.py; kdyz se modul nenacte,
    # bezne produkty funguji dal a konfigurovatelny produkt skonci jako "cena na dotaz")
    try:
        import konfigurace_kosik
    except Exception:
        konfigurace_kosik = None
        getattr(app, "logger", None) and app.logger.exception("cart: modul konfigurace se nenacetl")
    if konfigurace_kosik is not None and (body.get("configuration") is not None or konfigurace_kosik.je_konfigurovatelny(product_id)):
        chyba_cfg = konfigurace_kosik.pridat_do_kosiku(cart_owner_id, product_id, body)
        if chyba_cfg is not None:
            return jsonify(chyba_cfg[0]), chyba_cfg[1]
        conn_cfg = get_conn()
        try:
            rows_cfg = _fetch_cart_rows(conn_cfg, cart_owner_id)
        finally:
            conn_cfg.close()
        return jsonify(_serialize_cart(rows_cfg)), 201

    # Varianta sestavy + volby "montáž"/"bez boxů" (Robert 2026-09-13:
    # "u sestav s euroboxy... vedle výběru montáže, také volbu: bez boxů").
    # `assembly_id` chybel v kosiku uplne - jedna karta = jedna cena
    # (price_czk_placeholder), bez ohledu na to, kterou variantu si
    # zakaznik na detailu prohlizel. 0 = "bez varianty" (bezny produkt),
    # NIKDY None - viz komentar u UNIQUE KEY v migraci (sql/2026-09-13h_...),
    # NULL by rozbilo dedup bezneho produktu bez varianty.
    assembly_id_raw = body.get("assembly_id")
    try:
        assembly_id = int(assembly_id_raw) if assembly_id_raw not in (None, "", 0, "0") else 0
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatná varianta sestavy."}), 400
    if assembly_id < 0:
        return jsonify({"error": "Neplatná varianta sestavy."}), 400
    montaz_zvolena_in = bool(body.get("montaz_zvolena"))
    bez_boxu_in = bool(body.get("bez_boxu"))
    # Misto montaze (Robert pres bot16, 2026-09-13: "výběr montáže
    # klientem: v Praze nebo ve Slavičíně, povinný výběr") - POVINNE, kdyz
    # je montaz zvolena. Kontrola az NIZE (po zjisteni, jestli varianta
    # montaz vubec nabizi - viz montaz_zvolena klampovani), ne tady, jinak
    # by "montaz_zvolena: true" na sestave BEZ montazni ceny vyzadovalo
    # misto, ktere pak nikam neslo ulozit.
    montaz_misto_in = (body.get("montaz_misto") or "").strip().lower() or None
    # Overeni proti katalogu montaz_mista AZ NIZE (potrebuje `cur`,
    # viz blok "Misto montaze POVINNE" pod nactenim produktu).

    # Prirezy (Robert 2026-08-06, rozsireno o desky 2026-08-08) - kdyz je
    # "cut_pieces" v requestu, qty se NEBERE od klienta, ale dopocita se
    # ze zadanych prirezu (server si to znovu spocita sam, stejne jako
    # preview endpoint - nevericky klientske cene/poctu). Tvar prirezu
    # (1D delka vs. 2D sirka+vyska) zavisi na TYPU produktu (profil vs.
    # deska), ktery jeste neznáme - validace prirezu se proto provede az
    # NIZE, po nacteni produktu z DB (viz "cut_pieces_json"/"cut_service_qty"
    # blok). Bez "cut_pieces" beze zmeny (bezny produkt).
    cut_pieces_raw = body.get("cut_pieces")
    if cut_pieces_raw is None:
        try:
            qty = int(body.get("qty", 1))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné množství."}), 400
        if qty <= 0:
            return jsonify({"error": "Množství musí být kladné celé číslo."}), 400
        if qty > CART_MAX_QTY:
            return jsonify({"error": f"Množství je příliš velké (max {CART_MAX_QTY})."}), 400

    # Tyce navic bez rezu (Robert 2026-08-09: "kdyz pridam prirezy, kolik
    # tyci se prida - jen na prirezy nebo 1ks navic?"). Puvodne se qty od
    # klienta pri "cut_pieces" v requestu VUBEC nebral (viz komentar vyse) -
    # pole "Pocet celych tyci" na product.html tak vypadalo funkcni, ale
    # bylo ticha ignorovano. Ted se posila jako samostatny "extra_whole_qty"
    # a PRICITA se k poctu tyci dopocitanem z prirezu (jen u profilu -
    # desky pole na frontendu nemaji, viz pdWholeQtyWrap).
    try:
        extra_whole_qty = int(body.get("extra_whole_qty", 0) or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatný počet celých tyčí navíc."}), 400
    if extra_whole_qty < 0:
        return jsonify({"error": "Počet celých tyčí navíc nesmí být záporný."}), 400
    if extra_whole_qty > CART_MAX_QTY:
        return jsonify({"error": f"Množství je příliš velké (max {CART_MAX_QTY})."}), 400

    # Kupon (Robert 2026-08-08: "kuponovy system... zadani kodu na
    # product.html") - overi se hned tady (ne az ZIVE pri zobrazeni
    # kosiku jako u_cut_service_price_czk), aby zakaznik dostal okamzitou
    # zpetnou vazbu na neplatny/expirovany kod, misto tiseho "proste to
    # nefunguje".
    coupon_code = (body.get("coupon_code") or "").strip().upper() or None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, active, is_archived, cfg_dily_id, is_board_material, is_profile_material, cutting_material_key, "
                "       price_czk_placeholder, supplier_name "
                "FROM shop_products WHERE id=%s",
                (product_id,),
            )
            product = cur.fetchone()
            if not product or not product["active"] or product["is_archived"]:
                conn.rollback()
                return jsonify({"error": "Produkt neexistuje nebo není dostupný."}), 400
            # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): produkt bez
            # ceny (price_czk_placeholder NULL, typicky nedoceneny SEST-
            # sestava) sel do kosiku za 0 Kc - _effective_unit_price() dela
            # "or 0" jen jako obranu proti chybejicimu radku, ne jako
            # zamerne "0 = zdarma" (zadny takovy komentar v kodu neni).
            if product["price_czk_placeholder"] is None:
                conn.rollback()
                return jsonify({"error": "price_on_request"}), 409

            # Varianta sestavy (Robert 2026-09-13) - overeni, ze assembly_id
            # SKUTECNE patri tomuto product_id (bezpecnostni kontrola proti
            # cizimu assembly_id z requestu - napr. levnejsi varianta jine
            # karty). `_assembly_price_components` vraci None i kdyz
            # assembly_id neexistuje vubec.
            assembly_ceny = None
            if assembly_id:
                assembly_ceny = _assembly_price_components(
                    cur, assembly_id, product_id, float(product["price_czk_placeholder"]),
                )
                if assembly_ceny is None:
                    conn.rollback()
                    return jsonify({"error": "Neplatná varianta sestavy pro tento produkt."}), 400
                if assembly_ceny["base_czk"] is None:
                    conn.rollback()
                    return jsonify({"error": "price_on_request"}), 409
            # Montaz jako procento z ceny u dodavatelskych (vanDrawee) karet
            # (Robert 2026-09-18: "napojit na stejny mechanismus jako nase
            # sestavy" -> zjisteno, ze product_assemblies je REALNA 3D
            # scena/geometrie, tam by vanDrawee karta nesmyslne zaznamenala
            # falesnou geometrii (domena bota8), takze CENA se pocita
            # samostatne - procento z price_czk_placeholder, ne z
            # geometrie). Misto montaze (Praha/Slavicin) ale Robert PRESTO
            # chce i tady ("chybi misto montaze, vyber") - pouziva stejny
            # katalog montaz_mista jako nase sestavy.
            is_supplier_montaz = (not assembly_id) and product.get("supplier_name") == "vanDrawee"
            # Volby "montáž"/"bez boxů" se KLAMPUJI na to, co varianta
            # skutecne nabizi - klient posilajici montaz_zvolena=true u
            # sestavy bez zapecene montazni ceny (jeste neprepocitano ze
            # sceny) by jinak skoncil s ulozenym priznakem "chce montaz",
            # ale cenovym dopadem 0 Kc - matouci pro obsluhu objednavky.
            montaz_zvolena = montaz_zvolena_in and (
                bool(assembly_ceny and assembly_ceny.get("montaz_czk") is not None) or is_supplier_montaz
            )
            bez_boxu = bez_boxu_in and bool(assembly_ceny and assembly_ceny.get("boxy_czk") is not None)
            # Misto montaze POVINNE, kdyz je montaz skutecne zvolena
            # (viz komentar u montaz_misto_in vyse) - kontrola az TADY,
            # az je jasne, ze montaz_zvolena neni jen klientem poslane a
            # klampovanim zahozene "chteni". Plati STEJNE pro dodavatelskou
            # (vanDrawee) montaz jako pro nasi.
            if montaz_zvolena and montaz_misto_in is None:
                conn.rollback()
                return jsonify({"error": "Vyberte místo montáže."}), 400
            if montaz_misto_in is not None and montaz_misto_in not in _montaz_mista_map(cur):
                conn.rollback()
                return jsonify({"error": "Neplatné místo montáže."}), 400
            montaz_misto = montaz_misto_in if montaz_zvolena else None

            if coupon_code:
                # Robert (pres bot3, 2026-09-04): "deaktivuj slevove kody
                # vsude v e-shopu" - stejny reverzibilni feature-flag jako
                # cart_enabled. Explicitni odmitnuti misto ticheho ignorovani
                # kodu, ať zakaznik dostane jasnou zpravu, ne matouci "neplatny
                # kod" u kodu, ktery by jinak byl platny.
                if get_setting(cur, "discount_codes_enabled", "1") == "0":
                    conn.rollback()
                    return jsonify({"error": "Slevové kódy jsou momentálně nedostupné."}), 400
                cur.execute(
                    "SELECT discount_type, discount_value, valid_from, valid_until, active "
                    "FROM shop_product_coupons WHERE product_id=%s AND code=%s",
                    (product_id, coupon_code),
                )
                coupon = cur.fetchone()
                now = now_local()  # viz products.py::now_local - DB ma prazsky mistni cas, ne UTC
                valid = (
                    coupon and coupon["active"]
                    and (coupon["valid_from"] is None or now >= coupon["valid_from"])
                    and (coupon["valid_until"] is None or now <= coupon["valid_until"])
                )
                if not valid:
                    conn.rollback()
                    return jsonify({"error": "Slevový kód je neplatný nebo už nemá platnost."}), 400

            cut_pieces_json = None
            cut_service_qty = None
            clean_cuts = None
            if cut_pieces_raw is not None:
                # POZOR poradi: desky (PR10 apod.) maji casto NASTAVENE
                # OBOJI cfg_dily_id (kvuli 3D scene/hmotnosti) i
                # is_board_material - is_board_material je specifictejsi
                # priznak a MUSI se testovat prvni, jinak by se deska
                # omylem chovala jako 1D profil (viz test 2026-08-08).
                if product.get("is_board_material"):
                    # Desky na prirez (Robert 2026-08-08: "nebudou se
                    # prodavat cele desky ale přířezy") - 2D obdoba nize,
                    # mirror _validate_cut_pieces/_rods_needed_for_cuts,
                    # jen sirka+vyska misto delky (viz products.py).
                    if not product.get("cutting_material_key"):
                        conn.rollback()
                        return jsonify({"error": "Pro tento produkt zatím není v adminu nastavený materiál pro řezný plán."}), 400
                    clean_cuts, err = _validate_cut_pieces_2d(cut_pieces_raw)
                    if err:
                        conn.rollback()
                        return jsonify({"error": err}), 400
                    sheets_needed, board_plan, stock_err = _sheets_needed_for_cuts(cur, clean_cuts, product["cutting_material_key"])
                    if stock_err:
                        conn.rollback()
                        return jsonify({"error": stock_err}), 400
                    qty = sheets_needed
                    cut_pieces_json = json.dumps(clean_cuts)
                    cut_service_qty = None  # cena za rez u desek zatim neresena, viz plan
                elif product.get("is_profile_material"):
                    clean_cuts, err = _validate_cut_pieces(cut_pieces_raw)
                    if err:
                        conn.rollback()
                        return jsonify({"error": err}), 400
                    rods_needed, plan = _rods_needed_for_cuts(clean_cuts)
                    qty = rods_needed + extra_whole_qty
                    cut_pieces_json = json.dumps(clean_cuts)
                    # Rezy jako samostatna polozka (Robert 2026-08-06: "vždy
                    # když klient zadá přířezy je nutné do objenávky přidat
                    # automaticky řezy, musí figurovat v košíku"). Pocet rezu je
                    # fyzikalni fakt nezavisly na cene - uklada se VZDY. Jestli
                    # ma profil v adminu nastavenou cenu za rez se resi az ZIVE
                    # pri zobrazeni/checkoutu (_cut_service_price_czk v
                    # _fetch_cart_rows / orders.py), stejne jako u
                    # unit_price_per_m_czk. Puvodne se tu cena kontrolovala uz
                    # pri pridani do kosiku - kdyz admin doplnil cenu AZ POTOM,
                    # uz ulozena polozka v kosiku zustala navzdy bez rezu (cenu
                    # nikdo znovu nekontroloval), viz Robert: "cenu jsem vyplnil
                    # a nic".
                    cut_service_qty = plan.get("stats", {}).get("total_cuts") or 0
                else:
                    conn.rollback()
                    return jsonify({"error": "Tenhle produkt není profil ani deska na přířez."}), 400

            if clean_cuts is not None:
                cur.execute(
                    "SELECT id, qty FROM shop_cart_items WHERE user_id=%s AND product_id=%s",
                    (cart_owner_id, product_id),
                )
                existing = cur.fetchone()
                if existing:
                    # Novy seznam prirezu NAHRAZUJE predchozi stav radku
                    # (nemergovat s pripadnym starym cut_pieces_json -
                    # cerstve zadany seznam je citelnejsi mentalni model
                    # nez ticha kumulace, viz plan).
                    cur.execute(
                        "UPDATE shop_cart_items SET qty=%s, cut_pieces_json=%s, cut_service_qty=%s, coupon_code=%s WHERE id=%s",
                        (qty, cut_pieces_json, cut_service_qty, coupon_code, existing["id"]),
                    )
                else:
                    cur.execute(
                        "INSERT INTO shop_cart_items (user_id, product_id, qty, cut_pieces_json, cut_service_qty, coupon_code) "
                        "VALUES (%s,%s,%s,%s,%s,%s)",
                        (cart_owner_id, product_id, qty, cut_pieces_json, cut_service_qty, coupon_code),
                    )
            else:
                # Bezny produkt: atomicky upsert pres UNIQUE
                # (user_id, product_id, assembly_id) - bot16, 2026-09-03,
                # revize bot3 (I5): drive check-then-INSERT, dva soubezne
                # POST tehoz produktu koncily IntegrityError 1062 -> 500.
                # Semantika stejna jako dosavadni UPDATE vetev (qty se
                # pricita, kupon se prepise jen kdyz prisel novy).
                # `assembly_id` (Robert 2026-09-13) je NYNI SOUCASTI
                # UNIQUE klice - ruzne varianty tehoz produktu tak dostanou
                # SAMOSTATNE radky (misto tise zamenene varianty na
                # existujicim radku), zatimco opakovane pridani STEJNE
                # varianty dal jen navysi qty. montaz_zvolena/bez_boxu se
                # pri duplicite PREPISUJI na nejnovejsi volbu (na rozdil
                # od kuponu, ktery se drzi puvodniho, kdyz novy nedosel) -
                # jsou to jednoduche prepinace, ne volitelny doplnek.
                cur.execute(
                    "INSERT INTO shop_cart_items "
                    "(user_id, product_id, qty, cut_pieces_json, cut_service_qty, coupon_code, "
                    " assembly_id, montaz_zvolena, bez_boxu, montaz_misto) "
                    "VALUES (%s,%s,%s,NULL,NULL,%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE qty=qty+VALUES(qty), "
                    "coupon_code=COALESCE(VALUES(coupon_code), coupon_code), "
                    "montaz_zvolena=VALUES(montaz_zvolena), bez_boxu=VALUES(bez_boxu), "
                    "montaz_misto=VALUES(montaz_misto)",
                    (cart_owner_id, product_id, qty, coupon_code, assembly_id, montaz_zvolena, bez_boxu, montaz_misto),
                )
        conn.commit()
        rows = _fetch_cart_rows(conn, cart_owner_id)
    finally:
        conn.close()
    return jsonify(_serialize_cart(rows)), 201


@app.put("/api/cart/items/<int:item_id>")
@login_required
def cart_update_item(item_id):
    user = current_user()
    body = request.get_json(silent=True) or {}
    try:
        qty = int(body.get("qty"))
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatné množství."}), 400
    if qty > CART_MAX_QTY:
        return jsonify({"error": f"Množství je příliš velké (max {CART_MAX_QTY})."}), 400
    # Zruseni kuponu (bot16, 2026-09-03, revize bot3 - I4): POST dela
    # COALESCE (kupon jde jen nastavit), takze dosud nesel z radku sundat
    # jinak nez smazanim polozky. `"coupon_code": null` nebo "" = zrusit;
    # klic chybi = beze zmeny.
    clear_coupon = "coupon_code" in body and not (body.get("coupon_code") or "").strip()
    # Prepnuti "montáž"/"bez boxů" na uz vlozene polozce (Robert
    # 2026-09-13) - stejny vzor jako clear_coupon vyse: klic v tele = nova
    # hodnota, chybejici klic = beze zmeny (zakaznik meni jen qty).
    set_montaz = "montaz_zvolena" in body
    set_bez_boxu = "bez_boxu" in body
    # Misto montaze (Robert pres bot16, 2026-09-13, povinny vyber
    # Praha/Slavicin) - stejny vzor: klic v tele = nova hodnota. Validace
    # az NIZE, kdyz uz je jasne, jaka bude VYSLEDNA hodnota montaz_zvolena
    # (mohla prijit z tohoto requestu, nebo uz drive byla ulozena).
    set_misto = "montaz_misto" in body
    montaz_misto_in = (body.get("montaz_misto") or "").strip().lower() or None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if montaz_misto_in is not None and montaz_misto_in not in _montaz_mista_map(cur):
                conn.rollback()
                return jsonify({"error": "Neplatné místo montáže."}), 400
            cur.execute(
                "SELECT ci.id, ci.cut_pieces_json, ci.montaz_zvolena, ci.montaz_misto, ci.assembly_id, ci.config_hash, "
                "       p.cfg_dily_id, p.is_board_material, p.is_profile_material, p.cutting_material_key "
                "FROM shop_cart_items ci JOIN shop_products p ON p.id = ci.product_id "
                "WHERE ci.id=%s AND ci.user_id=%s",
                (item_id, _cart_owner_id(user)),
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return jsonify({"error": "Položka košíku neexistuje."}), 404
            if row.get("config_hash"):
                # bot5, 2026-10-02: konfigurace sestavy: mnozstvi a montaz, misto montaze se u konfigurace nevybira
                import konfigurace_kosik
                konfigurace_kosik.upravit_radek(cur, item_id, qty, body)
                conn.commit()
                rows = _fetch_cart_rows(conn, _cart_owner_id(user))
                return jsonify(_serialize_cart(rows))
            vysledna_montaz = bool(body.get("montaz_zvolena")) if set_montaz else bool(row["montaz_zvolena"])
            vysledne_misto = montaz_misto_in if set_misto else row.get("montaz_misto")
            if vysledna_montaz and vysledne_misto is None:
                conn.rollback()
                return jsonify({"error": "Vyberte místo montáže."}), 400
            if not vysledna_montaz:
                vysledne_misto = None  # montaz zrusena/nezvolena -> misto nema vyznam
            if qty <= 0:
                cur.execute("DELETE FROM shop_cart_items WHERE id=%s", (item_id,))
            else:
                # Invariant (Robert 2026-08-06, rozsireno o desky
                # 2026-08-08): u radku s prirezy nesmi pocet ks klesnout
                # pod minimum, ktere prirezy potrebuji - pokus o snizeni
                # pod minimum se tise zvedne zpet (ne 400). Tvar prirezu
                # (1D/2D) zavisi na typu produktu, stejne jako v
                # cart_add_item vyse.
                # POZOR poradi (viz stejna poznamka v cart_add_item vyse) -
                # is_board_material se testuje PRVNI, protoze desky maji
                # casto nastavene i cfg_dily_id.
                clean_cuts = _parse_cut_pieces(row.get("cut_pieces_json"))
                if clean_cuts and row.get("is_board_material") and row.get("cutting_material_key"):
                    sheets_needed, _plan, stock_err = _sheets_needed_for_cuts(cur, clean_cuts, row["cutting_material_key"])
                    if not stock_err:
                        qty = max(qty, sheets_needed)
                elif clean_cuts and row.get("is_profile_material"):
                    rods_needed, _plan = _rods_needed_for_cuts(clean_cuts)
                    qty = max(qty, rods_needed)
                set_clauses = ["qty=%s"]
                params = [qty]
                if clear_coupon:
                    set_clauses.append("coupon_code=NULL")
                if set_montaz:
                    set_clauses.append("montaz_zvolena=%s")
                    params.append(bool(body.get("montaz_zvolena")))
                if set_bez_boxu:
                    set_clauses.append("bez_boxu=%s")
                    params.append(bool(body.get("bez_boxu")))
                if set_misto or (set_montaz and not vysledna_montaz):
                    set_clauses.append("montaz_misto=%s")
                    params.append(vysledne_misto)
                params.append(item_id)
                cur.execute(f"UPDATE shop_cart_items SET {', '.join(set_clauses)} WHERE id=%s", params)
        conn.commit()
        rows = _fetch_cart_rows(conn, _cart_owner_id(user))
    finally:
        conn.close()
    return jsonify(_serialize_cart(rows))


@app.delete("/api/cart/items/<int:item_id>")
@login_required
def cart_delete_item(item_id):
    user = current_user()
    cart_owner_id = _cart_owner_id(user)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM shop_cart_items WHERE id=%s AND user_id=%s",
                (item_id, cart_owner_id),
            )
        conn.commit()
        rows = _fetch_cart_rows(conn, cart_owner_id)
    finally:
        conn.close()
    return jsonify(_serialize_cart(rows))


@app.delete("/api/cart")
@login_required
def cart_clear():
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shop_cart_items WHERE user_id=%s", (_cart_owner_id(user),))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "items": [], "subtotal_czk": 0.0, "item_count": 0, "total_qty": 0})


# ---------------------------------------------------------------------------
# Admin: prehled kosiku VSECH zakazniku (bot2, 2026-07-25). Robert: "chci
# jako admin videt vsechno tzn i kosik." Jen cteni - zadna zmena cizich
# kosiku (na to staci primy pristup do DB, admin akce tu neni potreba).
# Vraci jen NEPRAZDNE kosiky, seskupene podle zakaznika, stejny tvar
# jedne polozky jako _serialize_cart() vyse (vc. stock_qty/active/
# is_archived pro pripadne varovani v UI).
# ---------------------------------------------------------------------------

@app.get("/api/admin/carts")
@require_permission("kosiky", "zobrazit")
def admin_carts_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ci.id, ci.user_id, ci.product_id, ci.qty, ci.added_at, ci.updated_at, ci.config_hash, "
                "       u.name AS user_name, u.email AS user_email, "
                "       p.sku, p.name, p.price_czk_placeholder, p.stock_qty, p.active, p.is_archived "
                "FROM shop_cart_items ci "
                "JOIN app_users u ON u.id = ci.user_id "
                "JOIN shop_products p ON p.id = ci.product_id "
                "ORDER BY ci.user_id, ci.added_at ASC"
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    carts_by_user = {}
    order = []
    for r in rows:
        uid = r["user_id"]
        if uid not in carts_by_user:
            carts_by_user[uid] = {
                "user_id": uid,
                "user_name": r["user_name"],
                "user_email": r["user_email"],
                "items": [],
                "subtotal_czk": 0.0,
                "total_qty": 0,
                "updated_at": None,
            }
            order.append(uid)
        unit_price = _money(r["price_czk_placeholder"])
        line_total = round(unit_price * r["qty"], 2)
        entry = carts_by_user[uid]
        entry["items"].append({
            "id": r["id"],
            "product_id": r["product_id"],
            "sku": r["sku"],
            "name": r["name"],
            "unit_price_czk": unit_price,
            "qty": r["qty"],
            "line_total_czk": line_total,
            "stock_qty": r["stock_qty"],
            "active": bool(r["active"]),
            "is_archived": bool(r["is_archived"]),
            "made_to_order": bool(r.get("config_hash")),
        })
        entry["subtotal_czk"] = round(entry["subtotal_czk"] + line_total, 2)
        entry["total_qty"] += r["qty"]
        upd = r["updated_at"].isoformat() if r["updated_at"] else None
        if upd and (entry["updated_at"] is None or upd > entry["updated_at"]):
            entry["updated_at"] = upd

    carts = [carts_by_user[uid] for uid in order]
    carts.sort(key=lambda c: c["updated_at"] or "", reverse=True)
    return jsonify({"carts": carts, "total_carts": len(carts)})


@app.post("/api/admin/carts/bulk-clear")
@require_permission("kosiky", "smazat")
def admin_carts_bulk_clear():
    """Hromadne vyprazdneni kosiku vybranych zakazniku (Robert 2026-07-26:
    "mazat musí být všude !!!" - prekryva puvodni rozhodnuti "jen cteni,
    admin akce tu neni potreba"). "ids" jsou zde user_id (radek v teto
    tabulce = agregovany kosik jednoho zakaznika, ne jednotliva polozka) -
    maze VSECHNY polozky kosiku daneho zakaznika najednou. Pozor: jde o
    zakaznikuv AKTIVNI kosik, muze v nem prave nakupovat."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"DELETE FROM shop_cart_items WHERE user_id IN ({placeholders})", ids)
            deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "bulk_delete", "cart", None,
              f"Košíky {len(ids)} zákazníků vyprázdněny ({deleted} položek)")
    return jsonify({"status": "ok", "deleted": deleted})
