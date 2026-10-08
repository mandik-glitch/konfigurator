"""Karta produktu z KONFIGURACE generatoru stolu (stul 30 / 35 / 40 / 41 / 45) - backend (bot10, 2026-10-07).

Robert 2026-10-07: "pridat do generatoru: tlacitko ktere z aktualni sestavy vytvori aktivni kartu" (navazuje na jeho zadani pres bot4 "budu vyrabet sestavy stolu z generatoru (karty) stejne jako
u Vandr sestav"; kontrakt s bot4 / bot8 v TASKS.md a docs/KONTRAKT_KARTA_Z_KONFIGURACE.md). SKUPINA ROBERTOVYCH ROZHODNUTI: karta vznika AKTIVNI (vyslovny pokyn = vyjimka z "neaktivni
zakladani" u ostatnich skriptu; pravidlo 54 zakazuje jen RUCNI zasah bota do `active`, tady o aktivaci rozhodl Robert a udela ji clovek kliknutim), tlacitko vidi a mackne jen uzivatel s pravem
sklad_karty/vytvorit, AKTIVNI karta jen s pravem sklad_karty/upravit (jinak vznikne neaktivni).

CO SE ZALOZI (vse v JEDNE transakci, GLB se zapise PRED vlozenim karty a pri selhani se smaze):
  * shop_products: SKU `STUL-S<system>-<hash8>` (hash8 = prvnich 8 znaku kanonickeho hashe konfigurace, stul_glb.kanonicky_hash), nazev + popis (z karty generatoru + parametry konfigurace),
    cena = prodejni cena generatoru bez DPH v okamziku zalozeni (SNIMEK; stranka karty ukazuje zivou cenu), `glb_file` = `stul/<SKU>.glb` (model BEZ razitek v webapp/katalog/stul/, ma
    scenes[0].extras.v3d.front), jednotka / dostupnost / zobrazeni ceny a material renderu se kopiruji z karty generatoru, kategorie podle systemu (nebo volba v dialogu);
  * app_settings `configurator_products` + <id nove karty> -> recept zdrojove karty (karta je KONFIGURATOR s ulozenou vychozi konfiguraci: kosik, objednavka, nabidka a 3D jedou beze zmeny
    stejnou cestou jako u karty generatoru);
  * app_settings `configurator_default_<id>` = ulozeny vyber (stranka karty se otevre s TOUTO konfiguraci) a `stul_karta_<id>` = {system, selection, rules_version, hash, kod, zdroj_karta}
    (neměnný zaznam pro audit a pro scripts/stul_karta_glb.py; bez DDL);
  * audit_log (create_from_configuration).
Idempotentni: karta se stejnym SKU uz existuje -> vrati se ta (200, existing=true), nic se nemeni (ani `active`).

Klient posila JEN vyber (selection + rules_version, volitelne hash); cenu, kod, hash, model i popis pocita server (`konfigurace_kosik.vyres`, stejny zdroj jako kosik a online nabidka). Nazev a kategorie
smi admin upravit v dialogu (nazev se cisti, kategorie musi byt z nabidky sondy). Nahled (`nahled: true`) nic nezapisuje a nestavi model - jen vrati, co by vzniklo (SKU, nazev, cena, existujici karta).
"""
import json
import os
import re
import time

from flask import request, jsonify

from app import app, get_conn, require_permission, current_user, has_permission, _rate_limited, _product_slug_for_name
from documents import VAT_RATE
import konfigurace_kosik as kk
import konfigurator_registr
import stul_api
import stul_shop

VERZE = 1
SKU_RE = re.compile(r"^STUL-S(30|35|40|41|45)-([0-9a-f]{8})$")
KATALOG_STUL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp", "katalog", "stul")
GLB_PREFIX = "stul/"                                             # `shop_products.glb_file` je relativni k webapp/katalog/
KLIC_KARTY = "stul_karta_"                                       # app_settings `stul_karta_<id>`
KLIC_REGISTR = "configurator_products"
KORENOVA_KATEGORIE = 182                                         # "Balici stoly a pracoviste na miru": nabidka kategorii v dialogu = ona + jeji potomci
KATEGORIE_PODLE_SYSTEMU = {30: 206, 35: 312, 40: 311, 41: 183, 45: 330}    # vychozi kategorie karty podle systemu (generatory v kategoriich, viz webapp/category.html CATEGORY_GENERATORS); 45 = "Robustni balici stul system 45" (kat. 330, Robert 2026-10-08)
LIMIT_NA_UZIVATELE = (20, 3600)
POPIS_PARAMETRY = "Parametry této konfigurace:"
MAX_POPIS = 4000
_ZAKAZANE_ZNAKY_NAZVU = re.compile(r"[\x00-\x1f\x7f<>\[\]]")
_KONEC_NAZVU_KARTY = re.compile(r"\s+[–-]\s+(?:konfigurovateln\w*|\d+\s*[×x]\s*\d+(?:\s*[×x]\s*\d+)?\s*mm.*)$", re.IGNORECASE)


class _Chyba(Exception):
    def __init__(self, status, code, message, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra

    def odpoved(self):
        return jsonify({"error": self.code, "message": self.message, **self.extra}), self.status


def _cele(v, lo, hi):
    if isinstance(v, bool):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi and (not isinstance(v, float) or float(v) == n) else None


def _nazev(v):
    """Nazev zadany adminem -> ocisteny nazev, None (nezadan), nebo _Chyba 400."""
    if v is None or v == "":
        return None
    if not isinstance(v, str):
        raise _Chyba(400, "invalid_name", "Neplatný název karty.")
    if _ZAKAZANE_ZNAKY_NAZVU.search(v):
        raise _Chyba(400, "invalid_name", "Název karty nesmí obsahovat hranaté závorky, špičaté závorky ani řídicí znaky.")
    v = re.sub(r"\s+", " ", v).strip()
    if len(v) < 3 or len(v) > 200:
        raise _Chyba(400, "invalid_name", "Název karty musí mít 3 až 200 znaků.")
    return v


def _vstup(body):
    """Tvar pozadavku -> ocisteny dict, jinak _Chyba 400. Cenu, kod, hash ani model z pozadavku nebereme (jen vyber)."""
    if not isinstance(body, dict):
        raise _Chyba(400, "invalid_selection", "Neplatné tělo požadavku.")
    pid = _cele(body.get("product_id"), 1, 10 ** 9)
    if pid is None:
        raise _Chyba(400, "invalid_selection", "Chybí nebo je neplatné product_id.")
    conf = body.get("configuration")
    if not isinstance(conf, dict) or not isinstance(conf.get("selection"), dict):
        raise _Chyba(400, "invalid_selection", "Chybí konfigurace (selection).")
    rv = conf.get("rules_version")
    if rv is not None and not (isinstance(rv, str) and len(rv) <= 64):
        raise _Chyba(400, "invalid_selection", "Neplatná rules_version.")
    h = body.get("hash", conf.get("hash"))
    if h is not None and not (isinstance(h, str) and len(h) <= 64):
        raise _Chyba(400, "invalid_selection", "Neplatný hash.")
    kat = body.get("category_id")
    if kat is not None and kat != "":
        kat = _cele(kat, 1, 10 ** 9)
        if kat is None:
            raise _Chyba(400, "invalid_category", "Neplatná kategorie.")
    else:
        kat = None
    aktivni = body.get("active", True)
    if not isinstance(aktivni, bool):
        raise _Chyba(400, "invalid_selection", "Pole active musí být true / false.")
    return {"product_id": pid, "selection": conf["selection"], "rules_version": rv, "hash": h, "nahled": bool(body.get("nahled")), "name": _nazev(body.get("name")),
            "category_id": kat, "active": aktivni}


# ---------------------------------------------------------------------------------------------------------------- texty
def zaklad_nazvu(nazev_zdroje):
    """Nazev karty generatoru ("Pracovni stul system 40 - konfigurovatelny") bez koncovky "konfigurovatelny" / rozmeru, aby z karty vzniklé z karty nevznikal nazev s rozmery dvakrat."""
    return _KONEC_NAZVU_KARTY.sub("", (nazev_zdroje or "").strip()).strip() or "Pracovní stůl"


def rozmery(selection):
    """"1280 × 800 × 840" (sirka x hloubka x vyska desky) z EFEKTIVNIHO vyberu, nebo None."""
    cisla = []
    for k in ("w", "d", "h"):
        x = selection.get(k)
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            return None
        cisla.append(int(round(x)))
    return " × ".join(str(c) for c in cisla)


def auto_nazev(nazev_zdroje, selection):
    r = rozmery(selection)
    n = zaklad_nazvu(nazev_zdroje) + (f" – {r} mm" if r else "")
    return n if len(n) <= 200 else n[:200].rstrip()


def popis(popis_zdroje, souhrn):
    """Popis karty: text karty generatoru (bez drivejsiho bloku parametru) + parametry konfigurace (souhrn generatoru v cestine = to, co vidi zakaznik)."""
    zaklad = (popis_zdroje or "").split(POPIS_PARAMETRY)[0].strip()
    radky = []
    for s in souhrn or []:
        label, hodnota = (s or {}).get("label"), (s or {}).get("value")
        if label and hodnota not in (None, ""):
            radky.append(f"- {label}: {hodnota}")
    out = (zaklad + "\n\n" if zaklad else "") + POPIS_PARAMETRY + "\n" + "\n".join(radky)
    return out if len(out) <= MAX_POPIS else out[:MAX_POPIS - 1].rstrip() + "…"


# ---------------------------------------------------------------------------------------------------------------- kategorie
def kategorie_nabidky(cur):
    """[{id, name}] - korenova kategorie stolu a jeji viditelni potomci (volba v dialogu)."""
    cur.execute("SELECT id, name FROM content_categories WHERE (id=%s OR parent_id=%s) AND is_visible=1 ORDER BY (id=%s) DESC, sort_order, name", (KORENOVA_KATEGORIE, KORENOVA_KATEGORIE, KORENOVA_KATEGORIE))
    return [{"id": r["id"], "name": r["name"]} for r in cur.fetchall()]


def vychozi_kategorie(nabidka, system):
    """Vychozi kategorie karty pro system, nebo None (kategorie neexistuje / neni viditelna)."""
    kid = KATEGORIE_PODLE_SYSTEMU.get(system)
    return kid if kid is not None and any(k["id"] == kid for k in nabidka) else None


# ---------------------------------------------------------------------------------------------------------------- plan (cteni, nic nezapisuje)
def plan(cur, v, muze_aktivovat):
    """Vse, co z konfigurace vznikne: dict {sku, system, recept, nazev, popis, cena_net, kategorie_id, aktivni, res, zdroj, existujici}. _Chyba pri nekonfigurovatelnem produktu, neplatne / zmenene konfiguraci."""
    cur.execute("SELECT id, sku, name, description, unit, availability_text, price_visible_default, hover_show_price, hover_show_availability, render_material_key FROM shop_products WHERE id=%s",
                (v["product_id"],))
    zdroj = cur.fetchone()
    recept = konfigurator_registr.recept_produktu(v["product_id"]) if zdroj else None
    if not zdroj or recept not in stul_shop.RECEPTY:
        raise _Chyba(404, "not_configurable", "Tahle karta není konfigurovatelný stůl.")
    system = stul_shop.RECEPTY[recept]
    try:
        res = kk.vyres(cur, zdroj["id"], v["selection"], "cs", v["rules_version"])
    except kk.KonfiguraceChyba as e:
        raise _Chyba(e.status, e.code, e.message, **({"errors": e.errors} if e.errors else {}))
    if v["hash"] and v["hash"] != res["hash"]:
        raise _Chyba(409, "configuration_changed", "Konfigurace se liší od té, kterou server vyhodnotil. Otevřete ji znovu.")
    sku = f"STUL-S{system}-{res['hash'][:8]}"
    cur.execute("SELECT id, sku, name, slug, active, is_archived FROM shop_products WHERE sku=%s", (sku,))
    existujici = cur.fetchone()
    nabidka = kategorie_nabidky(cur)
    if v["category_id"] is not None and not any(k["id"] == v["category_id"] for k in nabidka):
        raise _Chyba(400, "invalid_category", "Tuhle kategorii nelze použít (vyber kategorii balicích stolů).")
    kategorie_id = v["category_id"] if v["category_id"] is not None else vychozi_kategorie(nabidka, system)
    return {"sku": sku, "system": system, "recept": recept, "nazev": v["name"] or auto_nazev(zdroj["name"], res["selection"]), "popis": popis(zdroj["description"], res["summary"]),
            "cena_net": int(res["net_czk"]), "kategorie_id": kategorie_id, "kategorie": nabidka, "aktivni": bool(v["active"] and muze_aktivovat), "muze_aktivovat": bool(muze_aktivovat),
            "res": res, "zdroj": zdroj, "existujici": existujici}


def _cena(net):
    vat = round(net * VAT_RATE / 100, 2)
    return {"net_czk": net, "vat_rate": VAT_RATE, "vat_czk": vat, "gross_czk": round(net + vat, 2)}


def _odkaz(slug, pid):
    return "/produkt/" + slug if slug else "/product.html?id=%s" % pid


def odpoved_nahled(p):
    ex = p["existujici"]
    return {"nahled": True, "sku": p["sku"], "system": p["system"], "name": p["nazev"], "kod": p["res"]["kod"], "hash": p["res"]["hash"], "price": _cena(p["cena_net"]),
            "category_id": p["kategorie_id"], "kategorie": p["kategorie"], "active": p["aktivni"], "muze_aktivovat": p["muze_aktivovat"], "rules_version": p["res"]["rules_version"],
            "existing": ({"id": ex["id"], "name": ex["name"], "active": bool(ex["active"]) and not ex["is_archived"], "archived": bool(ex["is_archived"]), "url": _odkaz(ex["slug"], ex["id"])} if ex else None)}


# ---------------------------------------------------------------------------------------------------------------- GLB
def _model_pro_kartu(selection, product_id):
    """GLB konfigurace S RAZITKY loga (pravidlo 61, Robert 2026-10-08: razitka na vsech 3D modelech ve vsech generatorech; ulozeny soubor je verejne dostupny primym odkazem /katalog/stul/<SKU>.glb);
    musi mit scenes[0].extras.v3d.front (celo - bez nej automat otocek kartu preskoci). Render dal pouziva scripts/stul_karta_glb.py --razitka (totez, postavene znovu z ulozeneho vyberu)."""
    import v3d_glb
    try:
        raw = konfigurator_registr.glb_bytes(selection, product_id, razitka=True)
        spec = v3d_glb.embedded_spec(raw)
    except Exception as e:                           # noqa: BLE001 - stavba modelu spadla: karta nevznikne (ValueError z modelu se nesmi splest s chybou ulozeni vyberu)
        app.logger.exception("stul_karta: model konfigurace se nepodarilo postavit")
        raise _Chyba(500, "glb_failed", "Model konfigurace se nepodařilo postavit (%s)." % type(e).__name__)
    front = spec.get("front") if isinstance(spec, dict) else None
    if not (isinstance(front, (list, tuple)) and len(front) == 3):
        raise _Chyba(500, "glb_invalid", "Model konfigurace nemá určené čelo (extras.v3d.front), kartu nelze založit.")
    return raw


def _zapis_glb(sku, data, adresar=None):
    """Atomicky zapise GLB do webapp/katalog/stul/<SKU>.glb (docasny soubor + rename). -> True, kdyz soubor predtim neexistoval (pri selhani karty se smaze)."""
    adresar = adresar or KATALOG_STUL_DIR
    os.makedirs(adresar, exist_ok=True)
    cil = os.path.join(adresar, sku + ".glb")
    nove = not os.path.exists(cil)
    tmp = os.path.join(adresar, ".%s.%d.%d.tmp" % (sku, os.getpid(), time.time_ns()))
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, cil)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return nove


def _smaz_glb(sku, adresar=None):
    try:
        os.remove(os.path.join(adresar or KATALOG_STUL_DIR, sku + ".glb"))
    except OSError:
        pass


# ---------------------------------------------------------------------------------------------------------------- zapis
def _registr_zamknuty(cur):
    """app_settings.configurator_products ZAMCENE (SELECT ... FOR UPDATE): vytvareni karet se serializuje a nikdo neztrati cizi zapis do registru."""
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s FOR UPDATE", (KLIC_REGISTR,))
    row = cur.fetchone()
    if not row or not row["setting_value"]:
        raise _Chyba(500, "registry_missing", "Chybí registr konfigurovatelných produktů (app_settings.configurator_products).")
    try:
        mapa = json.loads(row["setting_value"])
    except ValueError:
        raise _Chyba(500, "registry_invalid", "Registr konfigurovatelných produktů je poškozený.")
    if not isinstance(mapa, dict):
        raise _Chyba(500, "registry_invalid", "Registr konfigurovatelných produktů je poškozený.")
    return mapa


def vytvor(cur, user_id, p, adresar_glb=None, model_fn=None):
    """Zalozi kartu podle planu `p` (z plan()) v transakci volajiciho (COMMIT / ROLLBACK dela on). Vraci (novy_id, slug, ulozeny_vyber). GLB se zapise PRED vlozenim karty; pri vyjimce se smaze.
    Pod zamkem registru znovu overi, ze SKU neexistuje (soubezne kliknuti) - tak vraci _Chyba 409 `exists`."""
    res, zdroj = p["res"], p["zdroj"]
    mapa = _registr_zamknuty(cur)
    cur.execute("SELECT id FROM shop_products WHERE sku=%s", (p["sku"],))
    if cur.fetchone():
        raise _Chyba(409, "exists", "Karta s touhle konfigurací právě vznikla. Otevřete ji znovu.")
    vyber = stul_api.vychozi_over(res["selection"])               # stejna pravidla jako u "Ulozit jako vychozi" (ValueError = nelze ulozit)
    glb = (model_fn or _model_pro_kartu)(res["selection"], zdroj["id"])
    nove_glb = _zapis_glb(p["sku"], glb, adresar_glb)
    try:
        slug = _product_slug_for_name(cur, p["nazev"])
        cur.execute(
            "INSERT INTO shop_products (category_id, sku, name, slug, description, unit, price_czk_placeholder, active, activated_at, availability_text, price_visible_default, hover_show_price, "
            "hover_show_availability, glb_file, render_material_key) VALUES (%s,%s,%s,%s,%s,%s,%s,%s," + ("NOW()" if p["aktivni"] else "NULL") + ",%s,%s,%s,%s,%s,%s)",
            (p["kategorie_id"], p["sku"], p["nazev"], slug, p["popis"], zdroj["unit"] or "ks", "%.2f" % p["cena_net"], 1 if p["aktivni"] else 0, zdroj["availability_text"], zdroj["price_visible_default"],
             zdroj["hover_show_price"], zdroj["hover_show_availability"], GLB_PREFIX + p["sku"] + ".glb", zdroj["render_material_key"]))
        if cur.rowcount != 1:
            raise _Chyba(500, "save_failed", "Kartu se nepodařilo uložit.")
        nove_id = cur.lastrowid
        mapa[str(nove_id)] = p["recept"]
        cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s", (json.dumps(mapa, sort_keys=True), KLIC_REGISTR))
        if cur.rowcount != 1:
            raise _Chyba(500, "save_failed", "Kartu se nepodařilo zaregistrovat jako konfigurovatelnou.")
        zaznam = {"v": VERZE, "system": p["system"], "selection": vyber, "rules_version": res["rules_version"], "hash": res["hash"], "kod": res["kod"], "zdroj_karta": zdroj["id"], "sku": p["sku"]}
        for klic, hodnota in ((stul_api.vychozi_klic(nove_id), vyber), (KLIC_KARTY + str(nove_id), zaznam)):
            cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)", (klic, json.dumps(hodnota, sort_keys=True)))
        cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                    (user_id, "create_from_configuration", "shop_product", nove_id,
                     json.dumps({"sku": p["sku"], "system": p["system"], "kod": res["kod"], "hash": res["hash"], "zdroj_karta": zdroj["id"], "active": p["aktivni"], "cena_net": p["cena_net"],
                                 "category_id": p["kategorie_id"]}, ensure_ascii=False)))
    except BaseException:
        if nove_glb:
            _smaz_glb(p["sku"], adresar_glb)
        raise
    return nove_id, slug, vyber


def po_commitu(nove_id, vyber):
    """Cache tohoto procesu (ostatni gunicorn workery se osvezi do 60 s): registr produktu, karty systemu a ulozena vychozi konfigurace."""
    try:
        stul_shop._PRODUKTY["t"] = 0.0
        stul_shop._SYSTEMY_CACHE["t"] = 0.0
        stul_api._VYCHOZI_CACHE[int(nove_id)] = (time.time(), dict(vyber))
    except Exception:                                  # noqa: BLE001 - cache je jen uspora, nikdy nesmi shodit odpoved
        app.logger.warning("stul_karta: cache po zalozeni karty %s se nepodarilo obnovit", nove_id)


def odpoved_vytvoreno(p, nove_id, slug):
    return {"ok": True, "existing": False, "id": nove_id, "sku": p["sku"], "system": p["system"], "name": p["nazev"], "kod": p["res"]["kod"], "hash": p["res"]["hash"], "price": _cena(p["cena_net"]),
            "active": p["aktivni"], "category_id": p["kategorie_id"], "url": _odkaz(slug, nove_id), "glb_file": GLB_PREFIX + p["sku"] + ".glb", "rules_version": p["res"]["rules_version"],
            "poznamka": None if p["aktivni"] else "Karta vznikla NEAKTIVNÍ (aktivaci zapíná uživatel s právem upravovat skladové karty)."}


def odpoved_existujici(p):
    ex = p["existujici"]
    return {"ok": True, "existing": True, "id": ex["id"], "sku": p["sku"], "system": p["system"], "name": ex["name"], "active": bool(ex["active"]) and not ex["is_archived"],
            "archived": bool(ex["is_archived"]), "url": _odkaz(ex["slug"], ex["id"]), "price": _cena(p["cena_net"]), "kod": p["res"]["kod"], "hash": p["res"]["hash"]}


# ---------------------------------------------------------------------------------------------------------------- endpointy
@app.get("/api/admin/konfigurace/karta")
@require_permission("sklad_karty", "vytvorit")
def konfigurace_karta_sonda():
    """Sonda pro UI: 200 jen s pravem sklad_karty/vytvorit; 401/403 = bez prava, 404 = backend jeste neni nasazen (tlacitko se ma skryt). Nese kategorie nabidky a pravo aktivovat."""
    user = current_user()
    muze = has_permission(user, "sklad_karty", "upravit")          # PRED get_conn() (has_permission otevira a zavira sdilene spojeni = rollback)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            kategorie = kategorie_nabidky(cur)
    finally:
        conn.close()
    return jsonify({"ok": True, "verze": VERZE, "muze_aktivovat": bool(muze), "kategorie": kategorie,
                    "vychozi_kategorie": {str(s): vychozi_kategorie(kategorie, s) for s in stul_shop.RECEPTY.values()}})


@app.post("/api/admin/konfigurace/karta")
@require_permission("sklad_karty", "vytvorit")
def konfigurace_karta_vytvorit():
    user = current_user()                            # PRED get_conn() (pooled spojeni: close() = rollback)
    muze_aktivovat = has_permission(user, "sklad_karty", "upravit")
    try:
        v = _vstup(request.get_json(silent=True))
        if not v["nahled"] and _rate_limited(f"stul_karta:{user['id']}", *LIMIT_NA_UZIVATELE):
            raise _Chyba(429, "rate_limited", "Příliš mnoho nových karet, zkuste to za chvíli.")
        conn = get_conn()
        nove_id = slug = vyber = None
        try:
            with conn.cursor() as cur:
                p = plan(cur, v, muze_aktivovat)
                if v["nahled"]:
                    conn.rollback()
                    return jsonify(odpoved_nahled(p)), 200
                if p["existujici"]:
                    conn.rollback()
                    return jsonify(odpoved_existujici(p)), 200
                try:
                    nove_id, slug, vyber = vytvor(cur, user["id"], p)
                except ValueError as e:                           # stul_api.vychozi_over: vyber nelze ulozit
                    raise _Chyba(500, "selection_not_storable", "Konfiguraci nelze uložit: %s" % e)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        po_commitu(nove_id, vyber)
        app.logger.info("stul_karta: vznikla karta %s (%s) z karty %s, aktivni=%s", nove_id, p["sku"], p["zdroj"]["id"], p["aktivni"])
        return jsonify(odpoved_vytvoreno(p, nove_id, slug)), 201
    except _Chyba as e:
        return e.odpoved()
