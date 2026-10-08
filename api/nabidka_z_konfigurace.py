"""Online nabidka z KONFIGUROVANEHO produktu (stul 30 / 35 / 40 / 41) - backend (bot5, 2026-10-06).

Robert 2026-10-06 (pres bot9): tlacitko "promitnout konfiguraci stolu do online nabidky" v KAZDEM generatoru. Kontrakt pro UI: docs/KONTRAKT_NABIDKA_Z_KONFIGURACE.md,
navrh z 2. 10.: docs/NAVRH_NABIDKA_Z_KONFIGURACE.md.

SAMOSTATNY modul (vzor vandr_scene_offers.py) nad sdilenymi funkcemi scene_offers.py (create_scene_offer_row / save_offer_model_bytes). NEPOUZIVA admin POST /api/admin/scene-offers
(ten bere cenu a obrazky od klienta) - zde si server VSE spocita sam: `konfigurace_kosik.vyres` overi vyber, cenu, kod, hash, souhrn voleb a neutralni kusovnik (stejny zdroj jako kosik),
`stul_shop.glb_bytes` postavi model, `v3d_glb.sanitize` + `final_check` ho projdou jako u kazde zakaznicke nabidky. Cokoli od klienta navic (cena, nazev, kusovnik) se IGNORUJE.

Bez DDL: snimek konfigurace je v `scene_offers.offer_options` (JSON): `source: "configurator"`, `config` (VEREJNA cast: kod, hash, system, ks, souhrn voleb, neutralni kusovnik)
a `config_private` (vyber, cenovy souhrn, hmotnost; verejny JSON nabidky ho NEvraci - viz scene_offers.public_offer_get). Cena i konfigurace jsou SNIMEK v okamziku vytvoreni.

Nabidku tvori jen zamestnanec s pravem nabidky/vytvorit (Robert 2026-10-06: zakaznik tlacitko zatim nevidi). Zadny e-mail se neposila (pravidlo 16). Selhani 3D nikdy nezakaze vznik nabidky.
"""
import datetime
import json
import os
import re
import time

from flask import request, jsonify

from app import app, get_conn, require_permission, current_user, log_audit, _rate_limited
from documents import VAT_RATE
import konfigurace_kosik as kk
import konfigurator_registr                                   # rozcestnik stul / valeckovy dopravnik (bot5 2026-10-07)
import scene_offers
import stul_shop

VERZE = 1
MAX_KS = kk.MAX_MNOZSTVI
LIMIT_NA_UZIVATELE = (30, 3600)
MARK_ENV = "V3D_MARK_SECRET"
VYKRESY_LHUTA_H = 24                                  # vykresy ze sceny lze k nabidce nahrat/vymenit do 24 h od jejiho vytvoreni
VYKRESY_POVINNE = (("narys", "Nárys"), ("bokorys", "Bokorys"), ("pudorys", "Půdorys"))
VYKRESY_VOLITELNE = (("view3d_a", "3D pohled 1"), ("view3d_b", "3D pohled 2"))
_SLOUPCE_OBRAZKU = {"narys": "view_narys", "bokorys": "view_bokorys", "pudorys": "view_pudorys", "view3d_a": "view_3d_a", "view3d_b": "view_3d_b"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ZEME_RE = re.compile(r"^[A-Za-z]{2}$")
_znacka_vypnuto_zalogovano = False
# scene_offers vyzaduje obrazky narysu a 3D pohledu (sloupce NOT NULL); nabidka z konfigurace je nepotrebuje (stranka ukazuje interaktivni 3D), proto 1x1 pruhledny PNG
_PRAZDNY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
_PRAZDNE_OBRAZKY = {"narys": _PRAZDNY_PNG, "view3d_a": _PRAZDNY_PNG, "view3d_b": _PRAZDNY_PNG}


class _Chyba(Exception):
    def __init__(self, status, code, message, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra

    def odpoved(self):
        return jsonify({"error": self.code, "message": self.message, **self.extra}), self.status


def _text(v, maxlen):
    return v.strip()[:maxlen] if isinstance(v, str) and v.strip() else None


def _cele(v, lo, hi):
    if isinstance(v, bool):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi and (not isinstance(v, float) or float(v) == n) else None


def _vstup(body):
    """Tvar pozadavku -> ocisteny dict, jinak _Chyba 400 (cenu, nazev ani kusovnik z pozadavku nebereme)."""
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
    qty = _cele(body.get("qty", 1), 1, MAX_KS)
    if qty is None:
        raise _Chyba(400, "items_invalid", f"Množství musí být 1 až {MAX_KS}.")
    raw_pct = body.get("montaz_pct")
    pct = None
    if raw_pct is not None and raw_pct != "":
        pct = scene_offers._sanitize_montaz_pct(raw_pct)
        if pct is None:
            raise _Chyba(400, "items_invalid", "Sazba montáže musí být číslo 0 až 100.")
    zeme = body.get("delivery_country", "CZ")
    if zeme is None or zeme == "":
        zeme = "CZ"
    if not isinstance(zeme, str) or not _ZEME_RE.match(zeme):
        raise _Chyba(400, "items_invalid", "Země dodání musí být dvoupísmenný kód (např. CZ).")
    zakaznik = body.get("customer")
    jmeno = email = None
    if zakaznik is not None:
        if not isinstance(zakaznik, dict):
            raise _Chyba(400, "items_invalid", "Neplatný zákazník.")
        jmeno = _text(zakaznik.get("name"), 255)
        email = _text(zakaznik.get("email"), 255)
        if email and not _EMAIL_RE.match(email):
            raise _Chyba(400, "items_invalid", "Neplatný e-mail zákazníka.")
    h = body.get("hash")
    if h is not None and not (isinstance(h, str) and len(h) <= 64):
        raise _Chyba(400, "items_invalid", "Neplatný hash.")
    return {"product_id": pid, "selection": conf["selection"], "rules_version": rv, "qty": qty, "montaz_pct": pct, "zeme": zeme.upper(),
            "jmeno": jmeno, "email": email, "hash": h}


# ---------------------------------------------------------------------------------------------------------------- 3D model
def _znackovaci_klic():
    """-> (bytes | None, varovani). None = neviditelne znaceni VYPNUTO (V3D_MARK_SECRET neni v prostredi nebo je neplatny); stejne pravidlo jako u Vandr nabidek."""
    global _znacka_vypnuto_zalogovano
    hodnota = (os.environ.get(MARK_ENV) or "").strip()
    klic = varovani = None
    if hodnota:
        import v3d_mark
        try:
            klic = v3d_mark.get_secret(env={MARK_ENV: hodnota})
        except ValueError as e:
            varovani = "Neviditelné značení vypnuto: %s" % e
    if klic is None and not _znacka_vypnuto_zalogovano:
        _znacka_vypnuto_zalogovano = True
        app.logger.warning("nabidka z konfigurace: neviditelne znaceni modelu je VYPNUTO (%s)", "klic V3D_MARK_SECRET je neplatny" if hodnota else "V3D_MARK_SECRET neni nastaven")
    return klic, varovani


def _zakaznicky_glb(selection, product_id):
    """GLB konfigurace pro zakaznika: model z generatoru S RAZITKY loga -> v3d_glb.sanitize + final_check (polohy popisku kot `dims[].m` z generatoru zustavaji; validator je zna od 2026-10-06, bot10).
    ValueError = model nevznikl."""
    import v3d_glb
    raw = konfigurator_registr.glb_bytes(selection, product_id, razitka=True)         # model pro NABIDKU nese razitka loga na profilech (Robert 2026-10-06; verejny generator a kosik ho maji bez nich)
    spec = v3d_glb.embedded_spec(raw)
    if not isinstance(spec, dict):
        raise v3d_glb.V3DError("GLB nema popis v3d (scenes[0].extras.v3d)")
    out = v3d_glb.sanitize(raw, spec)
    gltf, _bin = v3d_glb.read_glb(out)
    v3d_glb.final_check(gltf)
    if len(out) > scene_offers.MAX_MODEL_BYTES:
        raise v3d_glb.V3DError("model je po kontrole příliš velký (%.1f MB)" % (len(out) / 1048576))
    return out


def _uloz_model(offer_id, user_id, glb):
    """Znaceni (je-li zapnute) + ulozeni modelu k nabidce. -> (v3d_ok, duvod, znacka)."""
    try:
        klic, varovani = _znackovaci_klic()
    except ImportError as e:
        return False, "modul značení (api/v3d_mark.py) nejde načíst: %s" % e, None
    znacka = "vypnuto"
    if klic is not None:
        try:
            import v3d_mark
            glb = v3d_mark.mark(glb, int(offer_id), klic)
            znacka = "zapnuto"
        except Exception as e:                       # noqa: BLE001 - se zapnutym znacenim se neznaceny model nikdy neulozi
            app.logger.warning("nabidka z konfigurace %s: model nejde oznacit: %s", offer_id, e)
            return False, "model nejde označit číslem nabídky (%s)" % type(e).__name__, None
    err = scene_offers.save_offer_model_bytes(offer_id, glb, user_id)
    if err:
        return False, err, None
    return True, varovani, znacka


def snapshot_pro_objednavku(offer_options):
    """Snimek konfigurace pro RADEK objednavky z prijate nabidky (stejny tvar jako kosik, konfigurace_kosik.radek_objednavky; navic zdroj=nabidka) z offer_options nabidky;
    None, kdyz to neni nabidka z konfigurace nebo snimek chybi/je poskozeny. Vola orders.create_order_from_scene_offer."""
    if not isinstance(offer_options, dict) or offer_options.get("source") != "configurator":
        return None
    cfg, priv = offer_options.get("config"), offer_options.get("config_private")
    if not (isinstance(cfg, dict) and isinstance(priv, dict) and cfg.get("kod") and isinstance(priv.get("selection"), dict)):
        return None
    return {"v": kk.CFG_VERZE, "product_id": cfg.get("product_id"), "kod": cfg.get("kod"), "hash": cfg.get("hash"), "rules_version": cfg.get("rules_version"), "lang": "cs",
            "selection": priv["selection"], "summary": cfg.get("souhrn"), "bom": cfg.get("bom"), "pocet_spoju": cfg.get("pocet_spoju"), "price_summary": priv.get("price_summary"),
            "list_net_czk": priv.get("list_net_czk"), "weight_kg": priv.get("weight_kg"), "weight_complete": priv.get("weight_complete"), "weight_missing": priv.get("weight_missing"),
            "zdroj": "nabidka"}


# ---------------------------------------------------------------------------------------------------------------- endpointy
@app.post("/api/admin/konfigurace/nabidka/<int:offer_id>/vykresy")
@require_permission("nabidky", "vytvorit")
def konfigurace_nabidka_vykresy(offer_id):
    """Kotovane 2D vykresy ke KONFIGURACNI nabidce (Robert 2026-10-06: v nabidce z generatoru chybi 2D kotovaci system ze sceny). Obrazky vyrobi Scena (stejnym kotovanim jako nabidka ze
    sceny, `scene.html?stul=<query>&nabidka_vykresy=<offer_id>`) a poslou sem: `{"views": {"narys", "bokorys", "pudorys" (povinne), "view3d_a", "view3d_b" (volitelne)}}` jako data-URI png/jpeg.
    Jen zamestnanec s pravem nabidky/vytvorit, jen nabidka z konfigurace, jen do 24 h od vytvoreni; opakovane nahrani vymeni predchozi vykresy. Po nahrani stranka nabidky ukaze stranky Vykresy."""
    user = current_user()
    body = request.get_json(silent=True)
    views_in = body.get("views") if isinstance(body, dict) else None
    if not isinstance(views_in, dict):
        return jsonify({"error": "invalid_views", "message": "Chybí views s obrázky výkresů."}), 400
    views = {}
    try:
        for klic, popis in VYKRESY_POVINNE:
            views[klic] = scene_offers._validate_data_uri(views_in.get(klic), popis)
        for klic, popis in VYKRESY_VOLITELNE:
            if views_in.get(klic) is not None:
                views[klic] = scene_offers._validate_data_uri(views_in.get(klic), popis)
    except ValueError as e:
        return jsonify({"error": "invalid_views", "message": str(e)}), 400
    conn = get_conn()
    stare_soubory = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, offer_number, created_at, offer_options, view_narys, view_bokorys, view_pudorys, view_3d_a, view_3d_b FROM scene_offers WHERE id=%s FOR UPDATE", (offer_id,))
            nab = cur.fetchone()
            if not nab:
                return jsonify({"error": "not_found", "message": "Nabídka neexistuje."}), 404
            try:
                opts = json.loads(nab["offer_options"]) if nab["offer_options"] else {}
            except (TypeError, ValueError):
                opts = {}
            if not (isinstance(opts, dict) and opts.get("source") == "configurator" and isinstance(opts.get("config"), dict)):
                return jsonify({"error": "not_configurator_offer", "message": "Výkresy lze nahrát jen k nabídce z konfigurace."}), 409
            if nab["created_at"] < datetime.datetime.now() - datetime.timedelta(hours=VYKRESY_LHUTA_H):
                return jsonify({"error": "vykresy_expired", "message": f"Výkresy lze nahrát jen do {VYKRESY_LHUTA_H} hodin od vytvoření nabídky."}), 409
            nove, sloupce = [], {}
            try:
                for klic, data_uri in views.items():
                    ulozeno = scene_offers._save_offer_image(data_uri)
                    nove.append(ulozeno)
                    sloupce[_SLOUPCE_OBRAZKU[klic]] = ulozeno
            except Exception:
                for f in nove:
                    _smaz_obrazek(f)
                raise
            stare_soubory = [nab[c] for c in sloupce if nab.get(c)]
            opts["config"]["vykresy"] = True
            sety = ", ".join(f"{c}=%s" for c in sloupce)
            cur.execute(f"UPDATE scene_offers SET {sety}, offer_options=%s WHERE id=%s", (*sloupce.values(), json.dumps(opts, ensure_ascii=False), offer_id))
        conn.commit()
    except Exception:
        conn.rollback()
        app.logger.exception("nabidka z konfigurace %s: ulozeni vykresu selhalo", offer_id)
        return jsonify({"error": "save_failed", "message": "Výkresy se nepodařilo uložit."}), 500
    finally:
        conn.close()
    for f in stare_soubory:
        _smaz_obrazek(f)
    log_audit(user["id"], "update", "scene_offer", offer_id, "výkresy z konfigurace ze Scény (" + ", ".join(views) + ")")
    return jsonify({"ok": True, "offer_id": offer_id, "vykresy": sorted(views)})


def _smaz_obrazek(stored_filename):
    """Best-effort smazani drivejsiho obrazku nabidky (zastupny nebo vymeneny vykres); jen jmeno souboru, nikdy cesta."""
    try:
        os.remove(os.path.join(scene_offers.OFFER_IMAGES_DIR, os.path.basename(str(stored_filename))))
    except OSError:
        pass


@app.get("/api/admin/konfigurace/nabidka")
@require_permission("nabidky", "vytvorit")
def konfigurace_nabidka_sonda():
    """Sonda pro UI: 200 jen se pravem; 401/403 = bez prava, 404 = backend jeste neni nasazen (tlacitko se ma skryt)."""
    return jsonify({"ok": True, "verze": VERZE})


@app.post("/api/admin/konfigurace/nabidka")
@require_permission("nabidky", "vytvorit")
def konfigurace_nabidka_vytvorit():
    user = current_user()                            # PRED get_conn() (pooled spojeni)
    if _rate_limited(f"konfig_nabidka:{user['id']}", *LIMIT_NA_UZIVATELE):
        return jsonify({"error": "rate_limited", "message": "Příliš mnoho nabídek, zkuste to za chvíli."}), 429
    try:
        v = _vstup(request.get_json(silent=True))
        t0 = time.time()
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name FROM shop_products WHERE id=%s", (v["product_id"],))
                produkt = cur.fetchone()
                if not produkt:
                    raise _Chyba(404, "not_configurable", "Tenhle produkt není konfigurovatelný.")
                try:
                    res = kk.vyres(cur, produkt["id"], v["selection"], "cs", v["rules_version"])
                except kk.KonfiguraceChyba as e:
                    raise _Chyba(e.status, e.code, e.message, **({"errors": e.errors} if e.errors else {}))
        finally:
            conn.close()
        if v["hash"] and v["hash"] != res["hash"]:
            raise _Chyba(409, "configuration_changed", "Konfigurace se liší od té, kterou server vyhodnotil. Otevřete ji znovu.")
        dopravnik = konfigurator_registr.je_dopravnik(produkt["id"])
        system = None if dopravnik else stul_shop.system_pro_produkt(produkt["id"])          # system profilu (30 | 35 | 40 | 41) je jen u stolu
        unit = int(res["net_czk"])
        total = unit * v["qty"]
        # montaz: vlastni sazba nabidky, jinak vychozi sazba stolu (stul_montaz_pct) - ulozi se do nabidky JAKO SNIMEK (zmena vychozi sazby uz rozeslane nabidky nehne);
        # mimo CR se vynuti 0 (do zahranici jen rozlozeny stul bez montaze, jako v kosiku)
        pct = v["montaz_pct"] if v["montaz_pct"] is not None else (res["montaz_pct"] if res["montaz_pct"] is not None else 0.0)
        if v["zeme"] != "CZ" or dopravnik:                         # dopravnik se montaz nenabizi (typ sestavy bez sazby)
            pct = 0.0
        montaz_czk = round(total * pct / 100, 2) if pct else None
        nazev = kk.jmeno_radku(produkt["name"], res["selection"], res["kod"])
        items = [{"name": nazev, "dim": "", "qty": 1, "unit_price": float(unit), "total": float(unit), "product_id": None,
                  "configuration_code": res["kod"], "config_hash": res["hash"]}]
        offer_options = {
            **scene_offers.OFFER_OPTIONS_DEFAULT,
            "source": "configurator",
            "montaz_pct": float(pct),
            "hidden_payment_method": "dobirka",                    # vyroba na zakazku: jen platba predem (jako kosik a mini-shop)
            # mimo CR (i SK) se zakaznikovi nabidne jen rozlozeny stul (Smontovano se skryje); v CR obe moznosti + montaz % jako informace pod tabulkou
            "hidden_delivery_state": "smontovano" if v["zeme"] != "CZ" else None,
            "config": {"v": VERZE, "product_id": produkt["id"], "system": system, "kod": res["kod"], "hash": res["hash"], "rules_version": res["rules_version"],
                       "qty": v["qty"], "delivery_country": v["zeme"], "souhrn": res["summary"], "bom": res["bom"], "pocet_spoju": res["pocet_spoju"]},
            "config_private": {"selection": res["selection"], "price_summary": res["price_summary"], "list_net_czk": res["net_czk"], "weight_kg": res["weight_kg"],
                               "weight_complete": res["weight_complete"], "weight_missing": res["weight_missing"], "montaz_czk_za_kus": res["montaz_czk"]},
        }
        offer_id, offer_number, token = scene_offers.create_scene_offer_row(items, float(unit), dict(_PRAZDNE_OBRAZKY), v["jmeno"], v["email"], None, offer_options, user["id"])
        # 3D: po zalozeni nabidky (potrebuje jeji cislo pro znaceni); selhani NEzrusi nabidku
        v3d_ok, v3d_duvod, znacka = False, None, None
        try:
            glb = _zakaznicky_glb(res["selection"], produkt["id"])
            v3d_ok, dalsi, znacka = _uloz_model(offer_id, user["id"], glb)
            v3d_duvod = None if v3d_ok else dalsi
        except ValueError as e:                      # V3DError je podtrida ValueError
            v3d_duvod = "3D model neprošel kontrolou: %s" % str(e)[:300]
        except Exception as e:                       # noqa: BLE001
            app.logger.exception("nabidka z konfigurace %s: stavba 3D modelu spadla", offer_number)
            v3d_duvod = "3D model se nepodařilo postavit (%s)" % type(e).__name__
        if not v3d_ok:
            app.logger.warning("nabidka z konfigurace %s: bez 3D modelu: %s", offer_number, v3d_duvod)
        vat = round(total * VAT_RATE / 100, 2)
        log_audit(user["id"], "create_from_configuration", "scene_offer", offer_id,
                  json.dumps({"product_id": produkt["id"], "system": system, "kod": res["kod"], "hash": res["hash"], "qty": v["qty"], "v3d": v3d_ok, "znacka": znacka,
                              "ms": int((time.time() - t0) * 1000)}, ensure_ascii=False))
        return jsonify({
            "offer_id": offer_id, "offer_number": offer_number, "online_url": "/nabidka-online.html?t=%s" % token,
            "line": {"kod": res["kod"], "hash": res["hash"], "qty": v["qty"], "unit_net_czk": unit, "total_net_czk": total},
            "price": {"net_czk": total, "vat_rate": VAT_RATE, "vat_czk": vat, "gross_czk": round(total + vat, 2)},
            "montaz": {"pct": float(pct), "czk": montaz_czk} if pct else None,
            "rules_version": res["rules_version"], "v3d": v3d_ok, "v3d_duvod": v3d_duvod,
        }), 201
    except _Chyba as e:
        return e.odpoved()
