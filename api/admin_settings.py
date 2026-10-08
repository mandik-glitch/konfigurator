"""Admin: nastavení - popisky/možnosti polí skladové karty, obecná
nastavení (ceny spojů, kosík, SMTP), barvy motivu (theme-colors) a
výchozí Open Graph náhled webu (og-settings).

Vyčleněno z api/app.py (PLAN_ROZDELENI_BACKENDU.md skupina 12) - čistý
přesun, žádná změna chování/URL. `get_setting`, `THEME_COLOR_KEYS`,
`_HEX_COLOR_RE`, `OG_DEFAULT_*` a `_get_og_site_defaults` zůstávají v
app.py, protože je používá i kód mimo tuhle skupinu (theme-presets,
SEO rendering stránek e-shopu) - modul si je jen importuje.
"""
import json
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

from flask import request, jsonify

from app import (
    app, get_conn, require_permission, login_required, current_user, log_audit,
    get_setting, get_scene_price_coefficient, SCENE_PRICE_COEF_KEY,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_FROM, SMTP_PASSWORD,
    THEME_COLOR_KEYS, _HEX_COLOR_RE, _get_og_site_defaults,
)

# Rozsah koeficientu sceny (bot16, 2026-10-01, Robert: "koeficient pro scenu se tyka jen profilu a produktu, ktere
# se nacitaji z dogusu"; implementace bot8 c77795b5 v api/app.py - katalog() a priznak scene_coef v
# fetch_katalog_parts()). Vraci se v GET /api/admin/settings, aby se POPISKY v adminu (zalozka Koeficienty cen:
# #scenePriceCoefHint/#scenePriceCoefWarn + priklad v ceny.js) prepnuly SAMY v okamziku, kdy uz bezi backend s timhle
# omezenim: webapp se servíruje hned, backend jde ven az v planovanem nasazeni (3:30/12:30), takze text nesmi
# zalezet na tom, kdy se co commitne. Kdyz se rozsah nekdy zmeni, zmen TADY hodnotu i texty v admin.html a ceny.js.
SCENE_PRICE_COEF_SCOPE = "profily_dogus"


# Popisky poli skladove karty produktu (Robert 2026-07-28: "tyto nadpisy
# udelejme jako databazove polozky, tzn budou se moci menit" - screenshot
# skladove karty s poli Kategorie (Shoptet)/Dostupnost/Alternativni a
# Souvisejici kody). Ulozeno pod jednim klicem app_settings jako JSON
# {field_key: popisek}, stejny vzor jako theme_colors_*. Vraceny popisek
# je vzdy DEFAULT merge-nuty s pripadnym DB prepisem, takze chybejici/
# nove pridane klice v budoucnu nikdy nezpusobi prazdny popisek ve
# frontendu.
PRODUCT_FIELD_LABEL_DEFAULTS = {
    "manufacturer": "Výrobce",
    "supplier_name": "Dodavatel",
    "ean": "EAN",
    "warranty": "Záruka",
    "category_path": "Kategorie (Shoptet)",
    "availability_text": "Dostupnost",
    "alternative_codes": "Alternativní kódy",
    "related_codes": "Související kódy",
    "meta_title": "SEO titulek (title)",
    "meta_description": "SEO popis (meta description)",
}

# Vandr (vanDrawee) "Cena obsahuje" blok (Robert 2026-09-23: "tento
# text chci editovatelný v adminu, protože se bude opakovat na vsech
# Vandr sestavach") - editovatelny v app_settings, cteny DYNAMICKY na
# kazde karte (api/products.py::shop_products_get, jen kdyz
# supplier_name='vanDrawee'), NE zapecen do ulozeneho `description`
# jednotlivych karet - zmena tady se tak projevi na VSECH kartach
# najednou, bez dalsiho backfillu. Vychozi hodnota = puvodni text,
# ktery byl do 2026-09-23 napevno v kodu (scripts/2026-09-18_bot7_
# vandrawee_bulk_import.py + scripts/2026-09-22_vandr_fbx_watcher.py).
VANDRAWEE_CENA_OBSAHUJE_KEY = "vandrawee_cena_obsahuje_text"
VANDRAWEE_CENA_OBSAHUJE_DEFAULT = "\n".join([
    "Cena obsahuje:",
    "- výrobu stavebnice",
    "- dodání ve zcela rozloženém stavu, profily v ochranné fólii",
    "- obecný montážní návod v PDF a ručně doplněné popisy ve 3D náhledech",
])

# Kotvení/montáž text pro Vandr (regal_umisteni.id=7, kod "RP") - JEDINY
# radek teto tabulky, ktery Vandr pouziva (overeno primo: 530
# nativnich sestav ma umisteni_id=1, jen 1 - Vandr stub - ma
# umisteni_id=7), takze editace tady je bezpecne izolovana od nativni
# vetve. Zbytek tabulky (nativni umisteni) editovatelny neni - mimo
# rozsah tohohle zadani.
VANDR_UMISTENI_ID = 7


def _load_product_field_options(cur):
    """Nacte {field_key: [moznost1, moznost2, ...]} z app_settings. Prazdny
    seznam / chybejici klic = pole zustava volny text (zadna zmena chovani
    ve frontendu)."""
    raw = get_setting(cur, "product_field_options")
    options = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if k in PRODUCT_FIELD_LABEL_DEFAULTS and isinstance(v, list):
                        cleaned = [str(x).strip() for x in v if str(x).strip()]
                        if cleaned:
                            options[k] = cleaned
        except (TypeError, ValueError):
            pass
    return options

@app.get("/api/admin/field-labels")
@require_permission("eshop_nastaveni", "zobrazit")
def field_labels_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            raw = get_setting(cur, "product_field_labels")
            options = _load_product_field_options(cur)
    finally:
        conn.close()
    labels = dict(PRODUCT_FIELD_LABEL_DEFAULTS)
    if raw:
        try:
            overrides = json.loads(raw)
            if isinstance(overrides, dict):
                for k, v in overrides.items():
                    if k in PRODUCT_FIELD_LABEL_DEFAULTS and isinstance(v, str) and v.strip():
                        labels[k] = v.strip()
        except (TypeError, ValueError):
            pass
    return jsonify({"labels": labels, "options": options})

@app.put("/api/admin/field-labels")
@require_permission("eshop_nastaveni", "upravit")
def field_labels_set():
    body = request.get_json(silent=True) or {}
    key = body.get("key")
    text = (body.get("text") or "").strip()
    if key not in PRODUCT_FIELD_LABEL_DEFAULTS:
        return jsonify({"error": f"Neznámý popisek: {key}"}), 400
    if not text:
        return jsonify({"error": "Popisek nesmí být prázdný."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            raw = get_setting(cur, "product_field_labels")
            overrides = {}
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        overrides = parsed
                except (TypeError, ValueError):
                    overrides = {}
            overrides[key] = text
            val = json.dumps(overrides)
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                ("product_field_labels", val, val),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "field_label", None, f"{key} → {text}")
    return jsonify({"status": "ok", "labels": {**PRODUCT_FIELD_LABEL_DEFAULTS, **overrides}})

# Robert 2026-07-28 (po AskUserQuestion): "Fixní seznam možností pro
# vyplňování (enum)" - u vybraných poli detailu produktu (spravuje se v
# nove zalozce Nastaveni) muze admin definovat pevny seznam hodnot (napr.
# Dostupnost: "Skladem"/"U dodavatele"/"Vyprodáno"). Kdyz pole ma
# definovane moznosti, skladova karta ho vykresli jako <select> misto
# volneho textu (viz webapp/admin.html scFieldInput()); prazdny seznam =
# pole zustava volny text jako drive (zadna zmena/migrace dat).
@app.put("/api/admin/field-options")
@require_permission("eshop_nastaveni", "upravit")
def field_options_set():
    body = request.get_json(silent=True) or {}
    key = body.get("key")
    if key not in PRODUCT_FIELD_LABEL_DEFAULTS:
        return jsonify({"error": f"Neznámé pole: {key}"}), 400
    raw_options = body.get("options")
    if not isinstance(raw_options, list):
        return jsonify({"error": "options musí být seznam."}), 400
    cleaned = []
    seen = set()
    for item in raw_options:
        text = str(item).strip()
        if text and text not in seen:
            cleaned.append(text)
            seen.add(text)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            raw = get_setting(cur, "product_field_options")
            all_options = {}
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        all_options = parsed
                except (TypeError, ValueError):
                    all_options = {}
            if cleaned:
                all_options[key] = cleaned
            else:
                all_options.pop(key, None)
            val = json.dumps(all_options)
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                ("product_field_options", val, val),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "field_options", None,
              f"{key} → {len(cleaned)} možností" if cleaned else f"{key} → volný text (možnosti zrušeny)")
    return jsonify({"status": "ok", "options": cleaned})

@app.get("/api/pricing-config")
@login_required
def pricing_config():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            joint_price = get_setting(cur, "joint_price_czk", "0")
            # Paušál za profil (Kč) - rozhodnuti 2026-07-23: jedna spolecna
            # sazba (stejny princip jako joint_price_czk), ktera se v zivem
            # prehledu (refreshSummary() ve scene.html) vynasobi POCTEM
            # profilu v aktualni sestave (kazdy profil ve scene ma cislo -
            # viz cislovani dilu) a pricte se k celkove cene. Na rozdil od
            # "ceny rezu" (price_per_cut_czk), ktera je nastavena SAMOSTATNE
            # pro kazdy prurez v tabulce cen, je tohle JEDNA paušální castka
            # platna stejne pro kazdy profil bez ohledu na prurez/delku.
            profile_flat_fee = get_setting(cur, "profile_flat_fee_czk", "0")
            # Balne (Robert 2026-09-11: "dal pridej cenu za balne 5%") -
            # procento z CELKOVE ceny (po marzi konfiguratoru), posledni
            # polozka souhrnu - viz komentar u packaging_czk v
            # computeAssemblyBomAndPrice() (scene.html), proc musi byt
            # POSLEDNI (nesmi se nasobit s nicim dalsim). Vychozi 0 = zadne
            # balne, dokud ho Robert nenastavi (stejny bezpecny vychozi
            # vzor jako joint_price_czk/profile_flat_fee_czk vyse).
            packaging_pct = get_setting(cur, "packaging_pct", "0")
            # Montaz jako nabizena sluzba (Robert 2026-09-13, pres bot9/bot3,
            # TEXT_FILTR.md pravidlo 14: "montaz sestavy z vice profilu je
            # nabizena SLUZBA s vlastni cenou, cena se ma prebirat u sestavy
            # ze sceny") - stejny princip jako packaging_pct (procento z
            # CELKOVE ceny sestavy PO vsech ostatnich slozkach vc. balneho,
            # viz montaz_czk v computeAssemblyBomAndPrice()). NEpricita se do
            # "Cena celkem" (je to volitelna sluzba, ne povinna slozka) -
            # scena ji jen dopocita a vystavi zvlast, obchodni stranu (kdy se
            # skutecne nabidne/nauctuje) resi bot5 na sve strane.
            montaz_pct = get_setting(cur, "montaz_pct", "0")
            # Koeficient se v konfiguratoru NEAPLIKUJE tady - uz je
            # zapecen v cenach dilu z /api/katalog (viz katalog() vyse).
            # Posila se sem ciste jako HODNOTA K OTISKU: scene.html si ji
            # ulozi do price_summary.scene_price_coefficient_applied,
            # aby pozdejsi davkovy prepocet (scripts/2026-09-11_robert_
            # joint_count_prepocet_269.py) poznal, jestli ulozena
            # material_czk/accessory_czk uz marzi obsahuje, a nenasobil
            # podruhe pri dalsim uez sestavy ve scene.
            scene_price_coef = get_scene_price_coefficient(cur)
            cur.execute("""
                SELECT id, name, price_czk, qty_per_joint FROM cfg_accessories
                WHERE active=1 ORDER BY sort_order, name
            """)
            accessories = [
                {
                    "id": r["id"], "name": r["name"],
                    "price_czk": float(r["price_czk"]),
                    "qty_per_joint": float(r["qty_per_joint"]),
                }
                for r in cur.fetchall()
            ]
    finally:
        conn.close()
    return jsonify({
        "joint_price_czk": float(joint_price) if joint_price is not None else 0,
        "profile_flat_fee_czk": float(profile_flat_fee) if profile_flat_fee is not None else 0,
        "packaging_pct": float(packaging_pct) if packaging_pct is not None else 0,
        "montaz_pct": float(montaz_pct) if montaz_pct is not None else 0,
        "scene_price_coefficient": scene_price_coef,
        "accessories": accessories,
    })

@app.get("/api/admin/settings")
@require_permission("nastaveni", "zobrazit")
def admin_settings_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            joint_price = get_setting(cur, "joint_price_czk", "0")
            profile_flat_fee = get_setting(cur, "profile_flat_fee_czk", "0")
            packaging_pct = get_setting(cur, "packaging_pct", "0")
            montaz_pct = get_setting(cur, "montaz_pct", "0")
            # Montaz u dodavatelskych (vanDrawee) karet (Robert 2026-09-18) -
            # SAMOSTATNY klic od montaz_pct vyse (ten je pro nase sestavy/
            # scenu), viz api/products.py::shop_products_get + api/cart.py.
            vandrawee_montaz_pct = get_setting(cur, "vandrawee_montaz_pct", "20")
            vandrawee_cena_obsahuje_text = get_setting(
                cur, VANDRAWEE_CENA_OBSAHUJE_KEY, VANDRAWEE_CENA_OBSAHUJE_DEFAULT)
            cur.execute(
                "SELECT kotveni_zakaznicky, montaz_zakaznicky FROM regal_umisteni WHERE id=%s",
                (VANDR_UMISTENI_ID,),
            )
            vandr_umisteni_row = cur.fetchone() or {}
            cart_enabled = get_setting(cur, "cart_enabled", "1")
            discount_codes_enabled = get_setting(cur, "discount_codes_enabled", "1")
            scene_price_coef = get_scene_price_coefficient(cur)
            smtp_override_raw = get_setting(cur, "smtp_config")
    finally:
        conn.close()
    smtp_override = {}
    if smtp_override_raw:
        try:
            smtp_override = json.loads(smtp_override_raw)
        except (TypeError, ValueError):
            smtp_override = {}
    return jsonify({
        "joint_price_czk": float(joint_price) if joint_price is not None else 0,
        "profile_flat_fee_czk": float(profile_flat_fee) if profile_flat_fee is not None else 0,
        "packaging_pct": float(packaging_pct) if packaging_pct is not None else 0,
        "montaz_pct": float(montaz_pct) if montaz_pct is not None else 0,
        "vandrawee_montaz_pct": float(vandrawee_montaz_pct) if vandrawee_montaz_pct is not None else 20,
        # priznak pro admin: tlacitko "Ulozit a prepocitat vse" u sazeb montaze se ukaze JEN kdyz server prepocet umi (statika jde ven driv nez planovane nasazeni API; viz montaz_prepocet_* nize)
        "montaz_prepocet": True,
        "vandrawee_cena_obsahuje_text": vandrawee_cena_obsahuje_text,
        "vandr_kotveni_text": vandr_umisteni_row.get("kotveni_zakaznicky") or "",
        "vandr_montaz_text": vandr_umisteni_row.get("montaz_zakaznicky") or "",
        "cart_enabled": cart_enabled != "0",
        "discount_codes_enabled": discount_codes_enabled != "0",
        "scene_price_coefficient": scene_price_coef,
        "scene_price_coefficient_scope": SCENE_PRICE_COEF_SCOPE,
        # Robert 2026-08-24: editovatelne v adminu misto rucni upravy .env
        # (viz _get_smtp_config() vyse) - efektivni hodnoty (override, nebo
        # kdyz override nema dane pole, hodnota z .env), heslo se NIKDY
        # neposila zpet na klienta, jen priznak, jestli nejake je nastavene.
        "smtp_host": smtp_override.get("host") or SMTP_HOST,
        "smtp_port": smtp_override.get("port") or SMTP_PORT,
        "smtp_user": smtp_override.get("user") or SMTP_USER,
        "smtp_from": smtp_override.get("from") or SMTP_FROM,
        "smtp_password_configured": bool(smtp_override.get("password") or SMTP_PASSWORD),
    })

@app.put("/api/admin/settings")
@require_permission("nastaveni", "upravit")
def admin_settings_set():
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if "joint_price_czk" in body:
                val = body.get("joint_price_czk")
                val = str(float(val)) if val not in (None, "") else "0"
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    ("joint_price_czk", val, val),
                )
            if "profile_flat_fee_czk" in body:
                val = body.get("profile_flat_fee_czk")
                val = str(float(val)) if val not in (None, "") else "0"
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    ("profile_flat_fee_czk", val, val),
                )
            if "packaging_pct" in body:
                raw = body.get("packaging_pct")
                if raw in (None, ""):
                    val = "0"
                else:
                    try:
                        pct = float(raw)
                    except (TypeError, ValueError):
                        return jsonify({"error": "Balné musí být číslo."}), 400
                    if pct < 0:
                        return jsonify({"error": "Balné nemůže být záporné."}), 400
                    val = str(pct)
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    ("packaging_pct", val, val),
                )
            if "montaz_pct" in body:
                raw = body.get("montaz_pct")
                if raw in (None, ""):
                    val = "0"
                else:
                    try:
                        pct = float(raw)
                    except (TypeError, ValueError):
                        return jsonify({"error": "Montáž musí být číslo."}), 400
                    if pct < 0:
                        return jsonify({"error": "Montáž nemůže být záporná."}), 400
                    val = str(pct)
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    ("montaz_pct", val, val),
                )
            if "vandrawee_montaz_pct" in body:
                raw = body.get("vandrawee_montaz_pct")
                if raw in (None, ""):
                    val = "20"
                else:
                    try:
                        pct = float(raw)
                    except (TypeError, ValueError):
                        return jsonify({"error": "Montáž vanDrawee musí být číslo."}), 400
                    if pct < 0:
                        return jsonify({"error": "Montáž vanDrawee nemůže být záporná."}), 400
                    val = str(pct)
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    ("vandrawee_montaz_pct", val, val),
                )
            if "vandrawee_cena_obsahuje_text" in body:
                val = (body.get("vandrawee_cena_obsahuje_text") or "").strip() or VANDRAWEE_CENA_OBSAHUJE_DEFAULT
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    (VANDRAWEE_CENA_OBSAHUJE_KEY, val, val),
                )
            if "vandr_kotveni_text" in body or "vandr_montaz_text" in body:
                # regal_umisteni.id=7 - VYHRADNE Vandr (viz komentar u
                # VANDR_UMISTENI_ID vyse), editace tady se nativni vetve
                # netyka.
                sets, params = [], []
                if "vandr_kotveni_text" in body:
                    sets.append("kotveni_zakaznicky=%s")
                    params.append((body.get("vandr_kotveni_text") or "").strip() or None)
                if "vandr_montaz_text" in body:
                    sets.append("montaz_zakaznicky=%s")
                    params.append((body.get("vandr_montaz_text") or "").strip() or None)
                params.append(VANDR_UMISTENI_ID)
                cur.execute(f"UPDATE regal_umisteni SET {', '.join(sets)} WHERE id=%s", params)
            if SCENE_PRICE_COEF_KEY in body:
                raw = body.get(SCENE_PRICE_COEF_KEY)
                # prazdna hodnota = "nenavysovat" (1.0), ne chyba
                if raw in (None, ""):
                    val = "1"
                else:
                    try:
                        coef = float(raw)
                    except (TypeError, ValueError):
                        return jsonify({"error": "Koeficient konfigurátoru musí být číslo."}), 400
                    # 0 nebo zaporne cislo by vynulovalo/prevratilo celou
                    # cenotvorbu - odmitnout hlasite, ne tise opravit
                    if coef <= 0:
                        return jsonify({"error": "Koeficient konfigurátoru musí být větší než 0."}), 400
                    val = str(coef)
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    (SCENE_PRICE_COEF_KEY, val, val),
                )
            if "cart_enabled" in body:
                # Robert 2026-08-18: docasna deaktivace kosiku (reverzibilni
                # feature-flag, zadna zmena dat) - skutecne vynuceni je na
                # backendu v cart.py (POST /api/cart/items)/orders.py
                # (POST /api/orders), tohle jen prepina priznak. Existujici
                # obsah kosiku (GET/uprava/smazani polozky) zustava funkcni
                # bez ohledu na tenhle priznak.
                val = "1" if body.get("cart_enabled") else "0"
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    ("cart_enabled", val, val),
                )
            if "discount_codes_enabled" in body:
                # Robert (pres bot3, 2026-09-04): "deaktivuj slevove kody
                # vsude v e-shopu" - stejny reverzibilni feature-flag vzor
                # jako cart_enabled vyse (zadna zmena/mazani dat, jen
                # prepinac). Skutecne vynuceni je v _effective_unit_price()
                # (products.py, jediny zdroj ceny pro produktovou stranku/
                # kosik/checkout) a v cart.py (odmitnuti kodu pri pridani
                # do kosiku).
                val = "1" if body.get("discount_codes_enabled") else "0"
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    ("discount_codes_enabled", val, val),
                )
            smtp_fields = ("smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from")
            if any(f in body for f in smtp_fields):
                # Merge do existujiciho override, ne prepis celeho JSON -
                # prazdne/chybejici heslo v requestu znamena "necham puvodni",
                # ne "smaz heslo" (frontend posila heslo, jen kdyz ho admin
                # skutecne prepsal, viz admin.html).
                cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='smtp_config'")
                row = cur.fetchone()
                try:
                    cfg = json.loads(row["setting_value"]) if row else {}
                except (TypeError, ValueError, KeyError):
                    cfg = {}
                if "smtp_host" in body and body["smtp_host"]:
                    cfg["host"] = body["smtp_host"]
                if "smtp_port" in body and body["smtp_port"]:
                    try:
                        cfg["port"] = int(body["smtp_port"])
                    except (TypeError, ValueError):
                        return jsonify({"error": "SMTP port musí být číslo."}), 400
                if "smtp_user" in body and body["smtp_user"]:
                    cfg["user"] = body["smtp_user"]
                if "smtp_password" in body and body["smtp_password"]:
                    cfg["password"] = body["smtp_password"]
                if "smtp_from" in body and body["smtp_from"]:
                    cfg["from"] = body["smtp_from"]
                val = json.dumps(cfg)
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    ("smtp_config", val, val),
                )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})

# --- Prepocet ulozene montaze karet (bot16, 2026-10-07; Robert: "chci u tech tlacitek za montaze mit nejen ulozit ale prepocitat vse, aby se vsechny karty prekalkulovaly") ---
# Karty sestav typu AUTO maji montaz ULOZENOU v data.price_summary (montaz_czk, montaz_pct_applied): scena ji pocita pri ulozeni sestavy jako Math.round(total_czk * sazba / 100)
# (scene.html computeAssemblyBomAndPrice) a cte ji product_assemblies._assembly_price_components -> kosik / objednavka a verejny JSON karet. Zmena app_settings.montaz_pct se do uz ulozenych
# karet sama NEpromitne (stav 2026-10-07: vsech 530 karet melo ulozeno 20 %, nastaveni bylo 10 %). Tenhle prepocet je srovna: meni JEN ta dve pole a JEN u sestav typu AUTO (sestava_typ AUTO nebo
# bez typu = starsi sestavy ze sceny); ostatni typy, sestavy bez price_summary / total_czk a rozbita data se nedotknou. Karty vanDrawee (products.py / cart.py) a stoly (konfigurace_kosik.py)
# pocitaji montaz ZIVE z aktualni sazby, objednavky maji snapshot (montaz_czk_snapshot) - tem neni co prepocitavat. GET = nahled (nic nezapisuje), POST = provede (jedna transakce, stare hodnoty
# do audit_log po davkach, idempotentni). Zaokrouhleni pul nahoru jako JS Math.round (ne bankerske Pythonu: 25905 * 10 % = 2591).
MONTAZ_PREPOCET_AUDIT_DAVKA = 400


def _montaz_pct_nastaveni(cur):
    """Aktualni sazba montaze vestaveb (app_settings montaz_pct) jako Decimal 0-100, jinak None (neplatne / chybi -> prepocet se neprovede)."""
    raw = get_setting(cur, "montaz_pct", "0")
    try:
        d = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None
    return d if d.is_finite() and 0 <= d <= 100 else None


def _pul_nahoru(x):
    return int((x + Decimal("0.5")).to_integral_value(rounding=ROUND_FLOOR))


def _cislo(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _montaz_prepocet_plan(cur, pct):
    """Plan prepoctu: ({id: (parsed_data, nova_czk, stara_czk, stary_pct, nazev, kod)}, pocty). pct = Decimal. Nic nezapisuje."""
    cur.execute("SELECT a.id, a.name, a.kod_sestavy, a.data FROM product_assemblies a LEFT JOIN sestava_typ t ON t.id = a.sestava_typ_id "
                "WHERE a.sestava_typ_id IS NULL OR t.kod = 'AUTO' ORDER BY a.id")
    zmeny, pocty = {}, {"sestav_auto": 0, "bez_zmeny": 0, "preskoceno_bez_ceny": 0, "preskoceno_rozbita_data": 0}
    pct_ulozit = int(pct) if pct == pct.to_integral_value() else float(pct)
    for r in cur.fetchall():
        pocty["sestav_auto"] += 1
        try:
            parsed = json.loads(r["data"]) if r["data"] else {}
        except (TypeError, ValueError):
            parsed = None
        if not isinstance(parsed, dict):
            pocty["preskoceno_rozbita_data"] += 1
            continue
        ps = parsed.get("price_summary")
        total = _cislo(ps.get("total_czk")) if isinstance(ps, dict) else None
        if total is None:
            pocty["preskoceno_bez_ceny"] += 1
            continue
        nova = _pul_nahoru(Decimal(str(total)) * pct / 100)
        stara, stary_pct = _cislo(ps.get("montaz_czk")), _cislo(ps.get("montaz_pct_applied"))
        if stara == nova and stary_pct is not None and Decimal(str(stary_pct)) == pct:
            pocty["bez_zmeny"] += 1
            continue
        ps["montaz_czk"] = nova
        ps["montaz_pct_applied"] = pct_ulozit
        zmeny[r["id"]] = (parsed, nova, stara, stary_pct, r["name"], r["kod_sestavy"])
    return zmeny, pocty


def _montaz_prepocet_neplatna_sazba():
    return jsonify({"error": "montaz_pct_invalid", "message": "Sazba montáže vestaveb (Obecné → Montáž) není číslo 0 až 100 - nejdřív ji ulož."}), 409


@app.get("/api/admin/montaz/prepocet")
@require_permission("nastaveni", "zobrazit")
def montaz_prepocet_nahled():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            pct = _montaz_pct_nastaveni(cur)
            if pct is None:
                return _montaz_prepocet_neplatna_sazba()
            zmeny, pocty = _montaz_prepocet_plan(cur, pct)
    finally:
        conn.close()
    ukazky = [{"id": i, "nazev": z[4], "kod": z[5], "total_czk": z[0]["price_summary"]["total_czk"], "montaz_stara_czk": z[2], "montaz_nova_czk": z[1], "pct_stara": z[3]}
              for i, z in list(zmeny.items())[:3]]
    r = jsonify({"pct": float(pct), "ke_zmene": len(zmeny), "ukazky": ukazky, **pocty})
    r.headers["Cache-Control"] = "no-store"
    return r


@app.post("/api/admin/montaz/prepocet")
@require_permission("nastaveni", "upravit")
def montaz_prepocet_provest():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            pct = _montaz_pct_nastaveni(cur)
            if pct is None:
                return _montaz_prepocet_neplatna_sazba()
            zmeny, pocty = _montaz_prepocet_plan(cur, pct)
            zaloha = []
            for aid, (parsed, nova, stara, stary_pct, _nazev, _kod) in zmeny.items():
                cur.execute("SELECT data FROM product_assemblies WHERE id=%s FOR UPDATE", (aid,))          # zamek radku; plan byl spocten bez nej (nahled) - pred zapisem se data znovu nactou
                r = cur.fetchone()
                try:
                    cur_parsed = json.loads(r["data"]) if r and r["data"] else None
                except (TypeError, ValueError):
                    cur_parsed = None
                ps = cur_parsed.get("price_summary") if isinstance(cur_parsed, dict) else None
                total = _cislo(ps.get("total_czk")) if isinstance(ps, dict) else None
                if total is None:
                    continue                                                                           # mezitim zmenena / rozbita - neprepisovat
                nova = _pul_nahoru(Decimal(str(total)) * pct / 100)
                zaloha.append([aid, _cislo(ps.get("montaz_czk")), _cislo(ps.get("montaz_pct_applied"))])
                ps["montaz_czk"] = nova
                ps["montaz_pct_applied"] = int(pct) if pct == pct.to_integral_value() else float(pct)
                cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s", (json.dumps(cur_parsed, ensure_ascii=False), aid))
        conn.commit()
    finally:
        conn.close()
    uid = current_user()["id"]
    for i in range(0, len(zaloha), MONTAZ_PREPOCET_AUDIT_DAVKA):                                          # stare hodnoty [id, montaz_czk, montaz_pct_applied] - audit_log.detail je TEXT, proto po davkach
        log_audit(uid, "update", "montaz_prepocet_zaloha", None, {"pct": float(pct), "davka": i // MONTAZ_PREPOCET_AUDIT_DAVKA + 1, "stare": zaloha[i:i + MONTAZ_PREPOCET_AUDIT_DAVKA]})
    log_audit(uid, "update", "montaz_prepocet", None, {"pct": float(pct), "zmeneno": len(zaloha), **pocty})
    return jsonify({"pct": float(pct), "zmeneno": len(zaloha), **pocty})


# Globalne nastavitelne barvy (task #66/#69, Robert 2026-07-26) - napevno v
# admin.html/scene.html/... byly dosud jen literalni hex hodnoty pro tmavy/
# svetly rezim; ted jsou to defaulty, ktere Robert muze prebarvit v adminu
# (zalozka Vzhled) a ulozi se do app_settings jako JSON.
#
# Puvodne byla paleta jedna spolecna pro admin panel i zakaznicky web
# ("theme_colors_dark"/"theme_colors_light"). Robert: "vyres barevnostni
# schema pro cely eshop i administraci... nechci po tobe konkretni, chci
# si vse obarvit sam" - tedy ne noveho hardcodovana paleta ode mě, ale
# moznost nastavit KAZDY povrch samostatne (task #66 "odděleně"). Proto
# je ted paleta rozdelena podle "surface": "admin" (administrace) a
# "eshop" (zakaznicky web), kazda se svym dark/light ulozenim v
# app_settings pod klicem "theme_colors_{surface}_{mode}".
#
# Zpetna kompatibilita: puvodni sdileny klic "theme_colors_{mode}" (bez
# surface) zustava v DB jako fallback - pokud pro dany surface/mode jeste
# neexistuji surface-specificka data, cte se z neho, aby se barvy po
# nasazeni vizualne nezmenily, dokud si Robert danou kombinaci poprve
# neuprav.
THEME_SURFACES = ("admin", "eshop", "nabidka", "cart")

THEME_COLOR_DEFAULTS = {
    "dark": {
        # Robert 2026-08-09 ("podklad tmaveho rezimu zesvetlit o 20%") -
        # #1b1e24 -> #494b50. Tenhle default se pouzije jen kdyz PRO DANY
        # SURFACE jeste neexistuje ulozeny radek v app_settings
        # (theme_colors_<surface>_dark) - zive hodnoty pro admin/eshop uz
        # jsou ulozene v DB (viz _load_theme_palette), tam se meni
        # samostatne. Bez teto zmeny by kazdy NOVY/nekonfigurovany surface
        # znovu zacinal na stare tmavsi barve.
        "bg": "#494b50", "panel_bg": "#22262e", "panel_bg_alt": "#1a1d23",
        "border": "#3a3f4a", "border_soft": "#333333", "border_soft2": "#2c313a",
        "border_faint": "#2a2e36",
        "text": "#e8eaed", "text2": "#c7ccd4", "text_muted": "#8b93a1",
        "text_faint": "#6f7684",
        "accent": "#9fd0ff", "accent_focus": "#6fa8ff",
        "btn_bg": "#3a5a7a", "btn_bg_hover": "#4a6a8a",
        "btn_danger": "#7a3a3a", "btn_danger_hover": "#8a4a4a",
        "error": "#e07070", "success": "#7ed49a", "warn": "#e0a070",
        "row_dirty_bg": "#26303c",
        "support_bubble_bg": "#3a4049", "support_ai_bubble_bg": "#3a3560",
        "support_ai_text": "#e0d4ff", "thumb_bg": "#111111",
        "sc_stat_bg": "#1a1d23", "sc_stat_border": "#2c313a",
        "sc_section_header": "#8b93a1", "sc_table_header_bg": "#1a1d23",
        # Nabidka nema tmavy/svetly rezim - "dark" tu jen kopiruje "light"
        # (viz komentar u "offer_*" v THEME_COLOR_KEYS vyse).
        "offer_navy_dark": "#0f2138", "offer_navy": "#16324f", "offer_navy_light": "#1c4a6b",
        "offer_orange": "#ff7a3d", "offer_orange_light": "#ffb35c",
        "offer_card_bg": "#f4f8fb", "offer_ink": "#1b2430", "offer_ink_soft": "#2a3646",
        "offer_muted": "#7a8798", "offer_border": "#e2e7f1",
        # Kosik nema tez tmavy/svetly rezim (viz komentar u "cart_*" v
        # THEME_COLOR_KEYS) - hodnoty odpovidaji dosavadnim natvrdo
        # zapsanym --cn-* promennym v #cartDrawer (product/category/index.html).
        "cart_navy_dark": "#0f2138", "cart_navy": "#16324f", "cart_navy_light": "#1c4a6b",
        "cart_orange": "#ff7a3d", "cart_orange_light": "#ffb35c",
        "cart_card_bg": "#f4f8fb", "cart_ink": "#1b2430", "cart_ink_soft": "#2a3646",
        "cart_muted": "#7a8798", "cart_border": "#e2e8ee",
    },
    "light": {
        "bg": "#eef1f5", "panel_bg": "#ffffff", "panel_bg_alt": "#f3f5f8",
        "border": "#d7dce3", "border_soft": "#e3e7ec", "border_soft2": "#dde2e8",
        "border_faint": "#e6e9ee",
        "text": "#1b1e24", "text2": "#3a3f4a", "text_muted": "#5c6570",
        "text_faint": "#97a0ab",
        "accent": "#1a6fd4", "accent_focus": "#2d6cdf",
        "btn_bg": "#2f6690", "btn_bg_hover": "#3a76a0",
        "btn_danger": "#b23b3b", "btn_danger_hover": "#c24b4b",
        "error": "#c23b3b", "success": "#2f9e5c", "warn": "#b8721f",
        "row_dirty_bg": "#eaf2fb",
        "support_bubble_bg": "#eceff2", "support_ai_bubble_bg": "#ece7fb",
        "support_ai_text": "#4a3f7a", "thumb_bg": "#dfe3e8",
        "sc_stat_bg": "#f3f5f8", "sc_stat_border": "#dde2e8",
        "sc_section_header": "#5c6570", "sc_table_header_bg": "#f3f5f8",
        "offer_navy_dark": "#0f2138", "offer_navy": "#16324f", "offer_navy_light": "#1c4a6b",
        "offer_orange": "#ff7a3d", "offer_orange_light": "#ffb35c",
        "offer_card_bg": "#f4f8fb", "offer_ink": "#1b2430", "offer_ink_soft": "#2a3646",
        "offer_muted": "#7a8798", "offer_border": "#e2e7f1",
        # Kosik nema tez tmavy/svetly rezim (viz komentar u "cart_*" v
        # THEME_COLOR_KEYS) - hodnoty odpovidaji dosavadnim natvrdo
        # zapsanym --cn-* promennym v #cartDrawer (product/category/index.html).
        "cart_navy_dark": "#0f2138", "cart_navy": "#16324f", "cart_navy_light": "#1c4a6b",
        "cart_orange": "#ff7a3d", "cart_orange_light": "#ffb35c",
        "cart_card_bg": "#f4f8fb", "cart_ink": "#1b2430", "cart_ink_soft": "#2a3646",
        "cart_muted": "#7a8798", "cart_border": "#e2e8ee",
    },
}

def _load_theme_palette(cur, surface, mode):
    defaults = THEME_COLOR_DEFAULTS[mode]
    raw = get_setting(cur, f"theme_colors_{surface}_{mode}", None)
    if not raw:
        # Zpetna kompatibilita se sdilenym klicem pred rozdelenim na
        # surface - viz komentar u THEME_SURFACES vyse.
        raw = get_setting(cur, "theme_colors_" + mode, None)
    if not raw:
        return dict(defaults)
    try:
        saved = json.loads(raw)
    except (ValueError, TypeError):
        return dict(defaults)
    palette = dict(defaults)
    for key in THEME_COLOR_KEYS:
        if key in saved and _HEX_COLOR_RE.match(str(saved[key])):
            palette[key] = saved[key]
    return palette

@app.get("/api/theme-colors")
def theme_colors_get():
    # Verejne, bez loginu - potrebuje i anonymni navstevnik e-shopu
    # (index.html/scene.html/...), ne jen prihlaseny admin.
    surface = request.args.get("surface")
    if surface not in THEME_SURFACES:
        # Zpetna kompatibilita s volanim bez ?surface= (stary frontend) -
        # puvodne to bylo napric vsim, takze admin je bezpecny default.
        surface = "admin"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            dark = _load_theme_palette(cur, surface, "dark")
            light = _load_theme_palette(cur, surface, "light")
    finally:
        conn.close()
    return jsonify({"dark": dark, "light": light, "surface": surface})

@app.put("/api/admin/theme-colors")
@require_permission("nastaveni", "upravit")
def theme_colors_set():
    body = request.get_json(silent=True) or {}
    surface = body.get("surface")
    if surface not in THEME_SURFACES:
        surface = "admin"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for mode in ("dark", "light"):
                if mode not in body or not isinstance(body[mode], dict):
                    continue
                incoming = body[mode]
                palette = _load_theme_palette(cur, surface, mode)
                for key, val in incoming.items():
                    if key not in THEME_COLOR_KEYS:
                        return jsonify({"error": f"Neznama barva: {key}"}), 400
                    if not isinstance(val, str) or not _HEX_COLOR_RE.match(val):
                        return jsonify({"error": f"Neplatna hex barva pro {key}: {val}"}), 400
                    palette[key] = val
                setting_key = f"theme_colors_{surface}_{mode}"
                val = json.dumps(palette)
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    (setting_key, val, val),
                )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})

@app.get("/api/admin/og-settings")
@require_permission("nastaveni", "zobrazit")
def og_settings_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            return jsonify(_get_og_site_defaults(cur))
    finally:
        conn.close()

@app.put("/api/admin/og-settings")
@require_permission("nastaveni", "upravit")
def og_settings_set():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    description = (body.get("description") or "").strip()
    image = (body.get("image") or "").strip()
    if not title or not description or not image:
        return jsonify({"error": "Vyplň název, popis i obrázek."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            val = json.dumps({"title": title, "description": description, "image": image})
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES ('og_site_defaults',%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (val, val),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})

