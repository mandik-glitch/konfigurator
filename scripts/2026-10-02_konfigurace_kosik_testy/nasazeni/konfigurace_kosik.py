"""Konfigurace sestavy v kosiku a v objednavce (bot5, 2026-10-02; zelenou dal bot3: "TED vetev kosiku a objednavky konfigurace, cena jen ze serveru").

Zivy konfigurator stolu (api/stul_shop.py, bot8) vraci pro zakaznikuv vyber EFEKTIVNI volby, hash, kod, platnost, cenu, neutralni kusovnik, hmotnost a cenovy souhrn - modul ho vola JEN pres
stabilni funkce `stul_shop.pro_objednavku` (a `konfigurovatelny`), do vnitrnosti konfiguratoru nesaha. Z vysledku dela radek KOSIKU a radek OBJEDNAVKY:
  * pridat_do_kosiku(cart_owner_id, product_id, body)   POST /api/cart/items s "configuration": {selection, rules_version}: server vyber znovu overi, cenu spocita sam (klient ji neposila),
                                                        ulozi efektivni vyber + hash (shop_cart_items.configuration_json / config_hash; stejny vyber = stejny radek, jina konfigurace = dalsi radek)
  * priprav_radek_kosiku(cur, r, user_id)               ZIVA cena a stav radku pri cteni kosiku (cena se v kosiku neuklada, jako u ostatnich radku)
  * upravit_radek(cur, item_id, qty, body)              mnozstvi a volba montaze (PUT /api/cart/items/<id>)
  * radek_objednavky(cur, product, it, user_id)         radek objednavky: znovu overeny vyber, cena po skupinove sleve, montaz, SNIMEK konfigurace (volby, kusovnik, cenovy souhrn) a kod

Rozhodnuti (bot3 2026-10-02): montaz konfigurace jen v CR a volitelne v % podle TYPU sestavy (sestava_typ_sluzba, klic montaz; nenastaveno = nenabizi se), do zahranici (i SK) jen rozlozeny BEZ montaze.
Konfigurace je vyroba na zakazku: radek objednavky ma product_id NULL (jako sluzba/rez), takze se na nej nevztahuje zadna logika skladu (potvrzeni, odpis, vraceni, objednavky u dodavatele),
odkaz na kartu a hash jsou ve snimku. Cena = bez DPH, cele Kc (stejne jako resolve), po skupinove sleve zakaznika; kupon a dealerska/akcni cena karty se na konfiguraci neuplatnuji.

Pozor na pooled spojeni: modul NIKDY nevola get_conn().close() na spojeni volajiciho (rollback by zahodil rozdelanou transakci kosiku/objednavky), pracuje jen pres predany kurzor;
jedina vyjimka je pridat_do_kosiku, ktera ma vlastni spojeni a transakci (volajici cart_add_item uz zadne nema otevrene).
"""
import json
import re

import configurator_price
import stul_shop
from app import get_conn, _rate_limited
from products import _effective_unit_price

TYP_SESTAVY = "STUL_SKLAD"                            # kod typu sestavy (sestava_typ.kod) konfigurovatelnych stolu: z nej se bere sazba montaze (dalsi recept = dalsi typ, az bude)
CFG_VERZE = 1
MAX_MNOZSTVI = 99
MAX_VYBER_ZNAKU = 4000
LIMIT_PRIDANI = (60, 60)                              # pridani konfigurace do kosiku: 60 za minutu na ucet
ZPRAVA_HMOTNOST = ("Dopravu Toptrans u této konfigurace zatím nelze spočítat automaticky (u některých dílů chybí hmotnost). "
                   "Zvolte osobní odběr, nebo nás kontaktujte.")
_HASH_RE = re.compile(r"^[0-9a-f]{16}\Z")


class KonfiguraceChyba(Exception):
    """Chyba konfigurace s strojovym kodem a HTTP stavem (code: invalid_selection, not_configurable, rules_changed, invalid_configuration, price_on_request,
    configuration_changed, montaz_unavailable ...). errors = seznam {slot, message} z resolve (jen pro invalid_configuration)."""

    def __init__(self, code, message, status=422, errors=None):
        super().__init__(message)
        self.code, self.message, self.status, self.errors = code, message, status, errors


def je_konfigurovatelny(product_id):
    try:
        return bool(stul_shop.konfigurovatelny(product_id))
    except Exception:                                  # chyba cteni nastaveni = produkt se tvari jako bezny (fail closed: bez ceny se nekoupi)
        return False


def typ_produktu():
    return TYP_SESTAVY


def montaz_pct_pro_typ(cur, kod_typu):
    """Sazba montaze (% z ceny po balnem) pro TYP sestavy -> float nebo None (nenabizi se). Stejne pravidlo jako configurator_price.montaz_pct_for_assembly, jen podle kodu typu
    (konfigurovatelna karta nema radek v product_assemblies). Radek sluzby: klic montaz, aktivni, pricing_mode procento_z_ceny, hodnota v (0, 100]. Cte jen pres kurzor."""
    if not kod_typu or str(kod_typu).upper() == "AUTO":
        return None
    cur.execute("SELECT id FROM sestava_typ WHERE kod=%s", (kod_typu,))
    typ = cur.fetchone()
    if not typ:
        return None
    cur.execute("SELECT hodnota FROM sestava_typ_sluzba WHERE sestava_typ_id=%s AND klic='montaz' AND aktivni=1 AND pricing_mode='procento_z_ceny' ORDER BY id LIMIT 1", (typ["id"],))
    row = cur.fetchone()
    if not row or row["hodnota"] is None:
        return None
    pct = float(row["hodnota"])
    return pct if 0 < pct <= 100 else None


def montaz_dostupna_pro_zemi(zeme):
    """Montaz se nabizi jen pri dodani v CR (Robert pres bot3: do zahranici vcetne Slovenska jen rozlozeny stul BEZ montaze). Prazdna zeme = CR (e-shop doruci jen v CR)."""
    return (zeme or "CZ").strip().upper() == "CZ"


# ---------------------------------------------------------------------------------------------------------------------
# nazev radku
# ---------------------------------------------------------------------------------------------------------------------
def jmeno_radku(product_name, selection, kod):
    """Nazev radku objednavky a dokladu: nazev karty, rozmery desky a kod konfigurace (<= 255 znaku)."""
    rozmery = " × ".join(str(int(selection[k])) for k in ("w", "d", "h") if isinstance(selection.get(k), (int, float)))
    jmeno = f"{(product_name or 'Konfigurace').strip()}" + (f" – {rozmery} mm" if rozmery else "") + f" ({kod})"
    return jmeno if len(jmeno) <= 255 else (jmeno[:255 - len(kod) - 5].rstrip() + f"… ({kod})")


# ---------------------------------------------------------------------------------------------------------------------
# overeni vyberu, cena, kusovnik
# ---------------------------------------------------------------------------------------------------------------------
def vyres(cur, product_id, selection, lang="cs", rules_version=None):
    """Overi vyber na serveru a spocita cenu. Vraci dict:
        {selection (EFEKTIVNI), hash, kod, rules_version, net_czk (cele Kc bez DPH), weight_kg, weight_complete (bool), weight_missing [nazvy dilu bez hmotnosti v katalogu],
         summary [{label, value}], bom [{nazev, mnozstvi, rozmer}] (neutralni, bez cisel dilu a dodavatelu), pocet_spoju, price_summary (cenovy souhrn: material, rezy, spoje, prislusenstvi, balne,
         total_czk), warnings, montaz_pct, montaz_czk}
    HMOTNOST: weight_kg je soucet hmotnosti dilu, ktere ji maji v katalogu; kdyz nejaka chybi (dnes laminodeska, suplíky, LED, panely...), je weight_complete False a cislo se NESMI pouzit
    na vypocet dopravy (poddimenzovala by ji).
    montaz_pct/montaz_czk jsou None, kdyz se montaz u typu sestavy nenabizi. Chyby: KonfiguraceChyba (not_configurable 404, invalid_selection 400, rules_changed 409,
    invalid_configuration 422 s errors [{slot, message}], price_on_request 409)."""
    if not je_konfigurovatelny(product_id):
        raise KonfiguraceChyba("not_configurable", "Tenhle produkt není konfigurovatelný.", 404)
    if not isinstance(selection, dict) or len(json.dumps(selection, ensure_ascii=False, default=str)) > MAX_VYBER_ZNAKU:
        raise KonfiguraceChyba("invalid_selection", "Neplatný výběr konfigurace.", 400)
    lang = lang if lang in ("cs", "en") else "cs"
    r = stul_shop.pro_objednavku(selection, rules_version, lang)
    if not r.get("ok"):
        raise KonfiguraceChyba("rules_changed", "Pravidla konfigurátoru se změnila, otevřete konfiguraci znovu.", 409)
    if not r.get("valid"):
        raise KonfiguraceChyba("invalid_configuration", "Tuto konfiguraci nelze vyrobit.", 422, errors=[{"slot": None, "message": m} for m in r.get("errors") or []])
    net = (r.get("price") or {}).get("net")
    if net is None:
        raise KonfiguraceChyba("price_on_request", "Cena konfigurace není k dispozici.", 409)
    souhrn_cen = r.get("cenovy_souhrn")
    if not isinstance(souhrn_cen, dict):
        raise KonfiguraceChyba("price_on_request", "Cena konfigurace není k dispozici.", 409)
    pct = montaz_pct_pro_typ(cur, typ_produktu())
    montaz_czk = configurator_price._js_round(net * pct / 100) if pct is not None else None
    return {
        "selection": r["selection"], "hash": r["hash"], "kod": r["kod"], "rules_version": r["rules_version"], "net_czk": net, "weight_kg": float(r.get("hmotnost_kg") or 0.0),
        "weight_complete": r.get("hmotnost_uplna") is True, "weight_missing": list(r.get("hmotnost_chybi") or []),
        "summary": [{"label": s["label"], "value": s["value"]} for s in r.get("souhrn") or []], "bom": r.get("bom") or [], "pocet_spoju": r.get("pocet_spoju"),
        "price_summary": {**souhrn_cen, "total_czk": net}, "warnings": [], "montaz_pct": pct, "montaz_czk": montaz_czk,
    }


def _uloz_vyber(res):
    """Obsah shop_cart_items.configuration_json: efektivni vyber + verze pravidel + kod (cena se neuklada)."""
    return json.dumps({"v": CFG_VERZE, "selection": res["selection"], "rules_version": res["rules_version"], "kod": res["kod"]}, ensure_ascii=False, sort_keys=True)


def nacti_vyber(raw):
    """Ulozena konfigurace z kosiku -> dict se selection, nebo None (rozbity zaznam)."""
    try:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except ValueError:
        return None
    return d if isinstance(d, dict) and isinstance(d.get("selection"), dict) else None


def _cena_po_sleve(cur, product_id, net, user_id):
    """(cena, zaklad): skupinova sleva zakaznika (jedina slevova vrstva, ktera se uplatnuje na konfiguraci), jinak cena z konfiguratoru. Kupon, akce a dealerska sleva karty se NEuplatnuji."""
    produkt = {"id": product_id, "price_czk_placeholder": net, "dealer_discount_percent": None, "sale_price_czk": None, "sale_price_from": None, "sale_price_until": None}
    return _effective_unit_price(cur, produkt, user=user_id and {"id": user_id}, coupon_code=None)


# ---------------------------------------------------------------------------------------------------------------------
# kosik
# ---------------------------------------------------------------------------------------------------------------------
def pridat_do_kosiku(cart_owner_id, product_id, body):
    """POST /api/cart/items s konfiguraci. Vraci None (hotovo, radek je v kosiku) nebo (dict_chyby, http_stav). Ma vlastni spojeni a transakci."""
    if _rate_limited(f"cartcfg:{cart_owner_id}", *LIMIT_PRIDANI):
        return {"error": "Příliš mnoho požadavků, zkuste to za chvíli.", "code": "rate_limited"}, 429
    cfg = body.get("configuration")
    if not isinstance(cfg, dict):
        return {"error": "U konfigurovatelného produktu je potřeba poslat konfiguraci.", "code": "configuration_required"}, 400
    if (body.get("coupon_code") or "").strip():
        return {"error": "Slevový kód nelze uplatnit na konfiguraci.", "code": "coupon_not_applicable"}, 400
    if body.get("assembly_id") not in (None, "", 0, "0") or body.get("cut_pieces") is not None or body.get("bez_boxu"):
        return {"error": "Konfigurace nepodporuje variantu sestavy, přířezy ani volbu bez boxů.", "code": "bad_request"}, 400
    try:
        qty = int(body.get("qty", 1))
    except (TypeError, ValueError):
        return {"error": "Neplatné množství.", "code": "bad_request"}, 400
    if not 1 <= qty <= MAX_MNOZSTVI:
        return {"error": f"Množství musí být 1 až {MAX_MNOZSTVI}.", "code": "bad_request"}, 400
    lang = body.get("lang") if body.get("lang") in ("cs", "en") else "cs"
    zeme = body.get("delivery_country")
    montaz_chce = bool(body.get("montaz_zvolena"))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, active, is_archived FROM shop_products WHERE id=%s", (product_id,))
            produkt = cur.fetchone()
            if not produkt or not produkt["active"] or produkt["is_archived"]:
                conn.rollback()
                return {"error": "Produkt neexistuje nebo není dostupný.", "code": "product_unavailable"}, 400
            try:
                res = vyres(cur, product_id, cfg.get("selection"), lang, cfg.get("rules_version"))
            except KonfiguraceChyba as e:
                conn.rollback()
                return {"error": e.message, "code": e.code, **({"errors": e.errors} if e.errors else {})}, e.status
            montaz = bool(montaz_chce and res["montaz_pct"] is not None and montaz_dostupna_pro_zemi(zeme))
            cur.execute(
                "INSERT INTO shop_cart_items (user_id, product_id, qty, cut_pieces_json, cut_service_qty, coupon_code, assembly_id, montaz_zvolena, bez_boxu, montaz_misto, configuration_json, config_hash) "
                "VALUES (%s,%s,%s,NULL,NULL,NULL,0,%s,0,NULL,%s,%s) "
                "ON DUPLICATE KEY UPDATE qty=LEAST(qty+VALUES(qty), %s), montaz_zvolena=VALUES(montaz_zvolena), configuration_json=VALUES(configuration_json)",
                (cart_owner_id, product_id, qty, montaz, _uloz_vyber(res), res["hash"], MAX_MNOZSTVI))
        conn.commit()
    finally:
        conn.close()
    return None


def priprav_radek_kosiku(cur, r, user_id):
    """Doplni do radku kosiku (dict z _fetch_cart_rows) vse, co _serialize_cart cte: ZIVOU cenu (po skupinove sleve, s montazi), priznaky a blok `configuration`.
    Rozbita nebo uz neplatna konfigurace = radek bez ceny a configuration.valid false (objednavka ho odmitne), kosik se kvuli tomu nerozbije."""
    ulozeno = nacti_vyber(r.get("configuration_json"))
    cfg = {"valid": False, "error": None, "kod": None, "hash": r.get("config_hash"), "changed": False, "summary": [], "weight_kg": None, "weight_complete": False, "montaz_pct": None, "errors": []}
    r.update({"cut_service_unit_price_czk": None, "assembly_montaz_czk": None, "assembly_boxy_czk": None, "waste_breakdown": None, "montaz_misto_label": None,
              "stock_qty": None, "unit_price_czk": None, "price_basis": None, "configuration": cfg, "made_to_order": True})
    r["price_czk_placeholder"] = None
    if ulozeno is None:
        cfg["error"] = "invalid_selection"
        return
    try:
        res = vyres(cur, r["product_id"], ulozeno["selection"], "cs")
    except KonfiguraceChyba as e:
        cfg["error"], cfg["errors"], cfg["kod"] = e.code, e.errors or [], ulozeno.get("kod")
        return
    except Exception:                                  # neocekavana chyba (napr. konfigurator): radek bez ceny, kosik zije dal, objednavku odmitne
        cfg["error"], cfg["kod"] = "internal_error", ulozeno.get("kod")
        return
    cfg.update({"valid": True, "kod": res["kod"], "hash": res["hash"], "changed": res["hash"] != r.get("config_hash"), "summary": res["summary"], "weight_kg": res["weight_kg"] if res["weight_complete"] else None,
                "weight_complete": res["weight_complete"], "montaz_pct": res["montaz_pct"], "rules_version": res["rules_version"]})
    cena, zaklad = _cena_po_sleve(cur, r["product_id"], res["net_czk"], user_id)
    r["price_czk_placeholder"], r["price_basis"] = res["net_czk"], zaklad
    r["assembly_montaz_czk"] = res["montaz_czk"]
    r["unit_price_czk"] = round(cena + res["montaz_czk"], 2) if (r.get("montaz_zvolena") and res["montaz_czk"] is not None) else cena


def upravit_radek(cur, item_id, qty, body):
    """PUT /api/cart/items/<id> pro radek s konfiguraci: mnozstvi (<= 0 radek smaze) a prepnuti montaze (jen kdyz se nabizi). Misto montaze se u konfigurace nevybira."""
    if qty <= 0:
        cur.execute("DELETE FROM shop_cart_items WHERE id=%s", (item_id,))
        return
    qty = min(qty, MAX_MNOZSTVI)
    if "montaz_zvolena" in body:
        cur.execute("SELECT product_id FROM shop_cart_items WHERE id=%s", (item_id,))
        row = cur.fetchone()
        dostupna = row is not None and montaz_pct_pro_typ(cur, typ_produktu()) is not None
        cur.execute("UPDATE shop_cart_items SET qty=%s, montaz_zvolena=%s WHERE id=%s", (qty, bool(body.get("montaz_zvolena")) and dostupna, item_id))
    else:
        cur.execute("UPDATE shop_cart_items SET qty=%s WHERE id=%s", (qty, item_id))


# ---------------------------------------------------------------------------------------------------------------------
# objednavka
# ---------------------------------------------------------------------------------------------------------------------
def radek_objednavky(cur, product, it, user_id, chyba):
    """Radek objednavky z radku kosiku nebo z polozky pozadavku. `it` nese configuration_json (kosik) nebo configuration {selection, rules_version} (pozadavek), config_hash (kosik),
    qty a montaz_zvolena. `chyba(zprava, status)` vyhodi chybu objednavky (orders._OrderCreateError). -> (order_item_dict, weight_kg radku, weight_complete); pri weight_complete False volajici
    NESMI dopravu podle hmotnosti (Toptrans) pocitat.
    Cenu NIKDY nebere z kosiku ani z pozadavku: vyber se znovu overi a cena spocita. Vybrana konfigurace se musi shodovat s tou, kterou zakaznik dal do kosiku (hash)."""
    pozadavek = it.get("configuration")
    ulozeno = nacti_vyber(it.get("configuration_json")) or (pozadavek if isinstance(pozadavek, dict) and isinstance(pozadavek.get("selection"), dict) else None)
    if ulozeno is None:
        raise chyba("Chybí nebo je poškozená konfigurace u položky.", 400)
    try:
        res = vyres(cur, product["id"], ulozeno["selection"], "cs", ulozeno.get("rules_version") if pozadavek is not None else None)
    except KonfiguraceChyba as e:
        raise chyba(e.message, e.status)
    if it.get("config_hash") and res["hash"] != it["config_hash"]:
        raise chyba("Konfigurace se po změně pravidel liší od té, kterou jste dali do košíku. Otevřete ji znovu a uložte do košíku.", 409)
    qty = int(it["qty"])
    if not 1 <= qty <= MAX_MNOZSTVI:
        raise chyba(f"Množství konfigurace musí být 1 až {MAX_MNOZSTVI}.", 400)
    montaz_zvolena = bool(it.get("montaz_zvolena"))
    if montaz_zvolena and (res["montaz_czk"] is None or not montaz_dostupna_pro_zemi(it.get("delivery_country"))):
        raise chyba("Montáž u této konfigurace se nenabízí, odeberte ji v košíku.", 409)
    cena, zaklad = _cena_po_sleve(cur, product["id"], res["net_czk"], user_id)
    unit = round(cena + res["montaz_czk"], 2) if montaz_zvolena else cena
    snimek = {"v": CFG_VERZE, "product_id": product["id"], "kod": res["kod"], "hash": res["hash"], "rules_version": res["rules_version"], "lang": "cs",
              "selection": res["selection"], "summary": res["summary"], "bom": res["bom"], "pocet_spoju": res["pocet_spoju"], "price_summary": res["price_summary"], "warnings": res["warnings"],
              "list_net_czk": res["net_czk"], "price_basis": zaklad, "weight_kg": res["weight_kg"], "weight_complete": res["weight_complete"], "weight_missing": res["weight_missing"],
              "montaz": {"zvolena": montaz_zvolena, "pct": res["montaz_pct"], "czk": res["montaz_czk"] if montaz_zvolena else None}}
    return {
        "product_id": None, "product_name_snapshot": jmeno_radku(product.get("name"), res["selection"], res["kod"]), "unit_price_czk": unit, "qty": qty, "cut_pieces_json": None,
        "line_total_czk": round(unit * qty, 2), "stock_qty": 0, "is_profile_material": False, "assembly_id": None, "assembly_kod_snapshot": None,
        "montaz_zvolena": montaz_zvolena, "montaz_czk_snapshot": res["montaz_czk"] if montaz_zvolena else None, "montaz_misto_snapshot": None, "bez_boxu": False, "boxy_czk_snapshot": None,
        "configuration_json": json.dumps(snimek, ensure_ascii=False), "configuration_code": res["kod"],
    }, float(res["weight_kg"] or 0.0) * qty, res["weight_complete"]


def hmotnost_pro_nahled(cur, it):
    """(hmotnost_kg radku, uplna) pro nahled ceny dopravy (POST /api/shipping-price-preview): `it` nese product_id, qty a configuration_json (kosik) nebo configuration {selection} (pozadavek).
    Chyby konfigurace jako KonfiguraceChyba."""
    pozadavek = it.get("configuration")
    ulozeno = nacti_vyber(it.get("configuration_json")) or (pozadavek if isinstance(pozadavek, dict) and isinstance(pozadavek.get("selection"), dict) else None)
    if ulozeno is None:
        raise KonfiguraceChyba("configuration_required", "U konfigurovatelného produktu je potřeba poslat konfiguraci.", 400)
    res = vyres(cur, it["product_id"], ulozeno["selection"], "cs", ulozeno.get("rules_version") if pozadavek is not None else None)
    return float(res["weight_kg"] or 0.0) * int(it["qty"]), res["weight_complete"]


def zakaznicky_snimek(raw):
    """Co z konfigurace objednavky smi videt ZAKAZNIK: kod, souhrn voleb, montaz. Kusovnik a cenovy souhrn (nakladova struktura) jen zamestnanec."""
    d = nacti_vyber_snimku(raw)
    if d is None:
        return None
    return {"kod": d.get("kod"), "hash": d.get("hash"), "summary": d.get("summary") or [], "montaz": d.get("montaz"), "rules_version": d.get("rules_version")}


def nacti_vyber_snimku(raw):
    try:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except ValueError:
        return None
    return d if isinstance(d, dict) else None
