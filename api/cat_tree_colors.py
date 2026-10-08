"""
cat_tree_colors.py - barva podkladu a pisma stromu kategorii (#catTree,
sidebar sdileny category.html/index.html/product.html/blok.html),
self-service pro admina.

Robert primo, 2026-09-17: "chci adminovsky posuvnik urcovani barvy
podkladu i pisma vsech prvku aktualniho menu/stromu kategorii" - stejny
vzor jako pd_desc_opacity.py (Robert uz takhle chce sam doladit vizual
bez dalsich kol pres nas).

ROZSIRENO (bot16, tyz den) - Robert po prvnim nasazeni: "vidime celkem 3
barvy podkladu, takze chci 3 barvy/posuvniky na podklad, k tomu chci 3
volby barvy/posuvniky na texty" - puvodni 1 sdileny par (podklad+pismo)
nahrazen 3 NEZAVISLYMI pary, jeden na kazdou vizualne odlisnou vrstvu
stromu (Robertuv vlastni odhad souhlasi s tim, jak je strom skutecne
postaveny - viz --cat-tree-*-rows/-open/-outer v category.html):
  - "rows"  = hloubkove odstupnovane radky zavrenych/neaktivnich polozek
  - "open"  = sdilena "sklenena" karta cele otevrene vetve (.is-open)
  - "outer" = holy podklad sidebaru (prosviti mezi radky, pod titulkem
              "KATEGORIE" a prazdnym stavem)

6 nastaveni v app_settings (cat_tree_{bg,text}_{rows,open,outer}_hex) -
hex retezec #rrggbb, NEBO prazdne/chybejici = "nezmeneno" pro tu
konkretni vrstvu. CSS pouziva fallback (var(--cat-tree-bg-rows,
var(--panel-bg-alt))) pro kazdou vrstvu zvlast, takze prazdna hodnota u
JEDNE vrstvy neovlivni ostatni a nema vizualni dopad, dokud si Robert
danou vrstvu sam nevybere. Zamerne JEDNA sdilena hodnota na vrstvu pro
oba motivy (ne zvlast tmavy/svetly) - stejna konvence jako uz sdileny
--cat-body-opacity (Robert: "ten posuvnik ma byt spolecny napric webem").

DOPLNENO (bot16, tyz den) - Robert u screenshotu prave OZNACENE (aktivni,
prave prohlizene) kategorie v menu: "jde o barvu prave oznaceneho textu,
pridej posuvnik/barvu" - 7. pole "text_active_hex". Na rozdil od
predchozich 3 vrstev NEMA vlastni "podklad" (aktivni polozka nema
zvlastni pozadi, jen barevny text+znacka) - jen 1 hodnota, ne par.

DOPLNENO (bot16, tyz den) - Robert: "pridej na nase menu prepinac caps
vsechno velke" + "vse samozrejme jen pro admina" (ovladac widi/pouziva
jen admin - stejny vzor jako VSECHNY ostatni ovladace tady, efekt sam
je verejny pro kazdeho navstevnika, presne jako barvy/font/zakladni
cerna). CAPS_KEY je boolovsky "1"/"" (ne hex), proto ma vlastni
zvlast osetreni mimo FIELD_KEYS/_HEX_COLOR_RE validaci nize.

DOPLNENO (bot16, 2026-09-25) - Robert: "potrebuju jako admin regulovat
podbarveni a silu linek" (podbarveni = uz existuje, viz bg_*_hex vyse;
tohle je jen ten druhy pozadavek). BORDER_WIDTH_KEY je cele cislo v px
(1-4, stejny rozsah jako puvodni pevna hodnota 2px v CSS) ulozene jako
retezec BEZ jednotky - vlastni validace mimo FIELD_KEYS/_HEX_COLOR_RE,
stejny vzor jako CAPS_KEY. CSS strana ctu var(--cat-tree-border-width,
2px), takze chybejici/prazdna hodnota = beze zmeny (puvodnich 2px).

DOPLNENO (bot16, 2026-09-25, tyz den) - Robert pres bot3: "chybi tam
barvitko pro podklad podkategorii". Zanorene urovne stromu (depth 1-4,
tzn. VSECHNY urovne pod nejvyssi) mely podklad jen DOPOCITANY z
bg_rows_hex (hloubkovy color-mix gradient smerem k --bg), zadny vlastni
ovladac. Pridana 2 nova pole DO FIELD_KEYS (bg_nested_hex,
text_nested_hex) - zadny specialni kod navic potreba, GET/PUT/SSR uz
generickym loopem pres FIELD_KEYS.items() obe pole automaticky
obslouzi presne jako zbylych 7. CSS strana (category/index/product/
blok.html) pouziva --cat-tree-bg-nested/--cat-tree-text-nested jako
novy PRVNI clanek fallback retezce PRED puvodnim bg_rows/text_rows -
nenastaveno = beze zmeny puvodniho chovani, nastaveno = prebije zdroj
gradientu pro VSECHNY zanorene urovne najednou (ne jen prvni).

DOPLNENO (bot16, 2026-09-26) - Robert u screenshotu aktivni polozky:
"kde presne urcuju podklad toho aktivniho podkladu?" - podklad aktivni
polozky byl dosud jen DOPOCITANY (12% pruhledny odstin z
text_active_hex pres color-mix), zadny vlastni ovladac, presne stejna
situace jako bg_nested pred dnem vyse. Pridano 1 nove pole (bg_active_hex),
opet zadny specialni kod navic - genericky loop pres FIELD_KEYS.items()
ho obslouzi sam. CSS strana (.cat-tree-row:has(.cat-tree-name.active))
pouziva --cat-tree-bg-active jako PRVNI clanek fallback retezce PRED
puvodnim color-mix vypoctem - nenastaveno = beze zmeny puvodniho
vzhledu, nastaveno = plati presne ta barva misto dopocitaneho odstinu.

DOPLNENO (bot16, 2026-09-26, tyz den) - Robert: "jeste tam chybi podklad
a pismo pro hover mysi". Hover (najeti mysi) mel dosud jen castecne a
nekonzistentni chovani - zanorene radky mely slaby DOPOCITANY odstin
(color-mix z --text, 6% pruhlednost), radky na 1. urovni nemely zadnou
hover barvu podkladu vubec, a hover text pouzival primo
--cat-tree-text-active (sdileny s "Aktivni polozkou", zadna vlastni
hodnota). Pridana 2 nova pole (bg_hover_hex, text_hover_hex), opet
genericky loop, zadny extra kod. CSS strana: --cat-tree-bg-hover jako
JEDNA sdilena hodnota pro VSECHNY hloubky (na rozdil od rows/nested,
ktere maji oddelene ovladace - hover je zamerne jednodussi, jeden
prepinac na cely strom), fallback zustava puvodni chovani na kazde
urovni zvlast (transparent na depth 0, color-mix odstin na zanorenych).
--cat-tree-text-hover je novy PRVNI clanek fallback retezce PRED
puvodnim --cat-tree-text-active.
"""
from flask import jsonify, request

from app import app, get_conn, admin_required, current_user, log_audit, get_setting, _HEX_COLOR_RE

# field (JSON i JS strana) -> app_settings klic
FIELD_KEYS = {
    "bg_rows_hex": "cat_tree_bg_rows_hex",
    "bg_open_hex": "cat_tree_bg_open_hex",
    "bg_outer_hex": "cat_tree_bg_outer_hex",
    "bg_nested_hex": "cat_tree_bg_nested_hex",
    "bg_active_hex": "cat_tree_bg_active_hex",
    "bg_hover_hex": "cat_tree_bg_hover_hex",
    "text_rows_hex": "cat_tree_text_rows_hex",
    "text_open_hex": "cat_tree_text_open_hex",
    "text_outer_hex": "cat_tree_text_outer_hex",
    "text_nested_hex": "cat_tree_text_nested_hex",
    "text_active_hex": "cat_tree_text_active_hex",
    "text_hover_hex": "cat_tree_text_hover_hex",
}
CAPS_KEY = "cat_tree_caps"
BORDER_WIDTH_KEY = "cat_tree_border_width_px"
BORDER_WIDTH_MIN = 1
BORDER_WIDTH_MAX = 4
# bot16, 2026-09-26 (Robert: "ta linka efektova je moc silna, ale porad
# k ni neni zeslabovac, ten posuvnik se tyka jeste jine linky") -
# BORDER_WIDTH_KEY vyse (Sila linek) meni sirku LEVEHO PROUZKU aktivni
# polozky, ne intenzitu sweep hover efektu (viz catTreeSweepX/Y v
# category.html) - to je jina "linka", zadny spolecny ovladac. Ulozeno
# rovnou jako desetinne cislo (ne procenta) - primo se pouzije jako
# CSS opacity hodnota (0-1), zadny prevod na strane JS/CSS potreba.
SWEEP_OPACITY_KEY = "cat_tree_sweep_opacity"
SWEEP_OPACITY_MIN = 0.1
SWEEP_OPACITY_MAX = 1.0


def cat_tree_colors_ssr_style(cur):
    # bot16, 2026-09-17 (Robert: "je tam videt mezikrok, kdy se vykreslí
    # zelene (puvodni barva) a prekresli se novou barvou, ten problik
    # samozrejme nechceme") - dosud se ulozena barva aplikovala jen JS-em
    # AZ PO async fetch()i /api/public/cat-tree-colors, takze prvni
    # vykresleni vzdy ukazalo fallback (napr. --sidebar-accent) a pak
    # "probliklo" na skutecnou barvu. Volano z _render_og_page() (app.py)
    # pro KAZDOU stranku - vlozi <style> primo do <head> prvni odpovedi
    # ze serveru, cimz je spravna barva pritomna uz na prvnim vykresleni
    # (stejny princip jako uz existujici data-ssr="1" strom kategorii).
    # Prazdny retezec (nic nenastaveno) = zadny <style> tag - beze zmeny.
    pairs = []
    for field, key in FIELD_KEYS.items():
        val = get_setting(cur, key)
        if val and _HEX_COLOR_RE.match(val):
            css_var = "--cat-tree-" + field[:-4].replace("_", "-")
            pairs.append(f"{css_var}:{val}")
    style = ""
    if pairs:
        style += f'<style id="catTreeColorsSSR">:root{{{";".join(pairs)}}}</style>'
    if get_setting(cur, CAPS_KEY) == "1":
        style += '<style id="catTreeCapsSSR">.cat-tree-name{text-transform:uppercase;}</style>'
    border_val = get_setting(cur, BORDER_WIDTH_KEY)
    if border_val and border_val.isdigit() and BORDER_WIDTH_MIN <= int(border_val) <= BORDER_WIDTH_MAX:
        style += f'<style id="catTreeBorderSSR">:root{{--cat-tree-border-width:{border_val}px}}</style>'
    sweep_val = get_setting(cur, SWEEP_OPACITY_KEY)
    try:
        sweep_f = float(sweep_val) if sweep_val else None
    except ValueError:
        sweep_f = None
    if sweep_f is not None and SWEEP_OPACITY_MIN <= sweep_f <= SWEEP_OPACITY_MAX:
        style += f'<style id="catTreeSweepOpacitySSR">:root{{--cat-tree-sweep-opacity:{sweep_f}}}</style>'
    return style


@app.get("/api/public/cat-tree-colors")
def public_cat_tree_colors():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            raw = {field: get_setting(cur, key) for field, key in FIELD_KEYS.items()}
            caps = get_setting(cur, CAPS_KEY) == "1"
            border_val = get_setting(cur, BORDER_WIDTH_KEY)
            sweep_val = get_setting(cur, SWEEP_OPACITY_KEY)
    finally:
        conn.close()
    border_width = (
        int(border_val)
        if border_val and border_val.isdigit() and BORDER_WIDTH_MIN <= int(border_val) <= BORDER_WIDTH_MAX
        else None
    )
    try:
        sweep_f = float(sweep_val) if sweep_val else None
    except ValueError:
        sweep_f = None
    sweep_opacity = sweep_f if sweep_f is not None and SWEEP_OPACITY_MIN <= sweep_f <= SWEEP_OPACITY_MAX else None
    return jsonify({
        **{
            field: (val if val and _HEX_COLOR_RE.match(val) else None)
            for field, val in raw.items()
        },
        "caps": caps,
        "border_width": border_width,
        "sweep_opacity": sweep_opacity,
    })


@app.put("/api/admin/cat-tree-colors")
@admin_required
def admin_set_cat_tree_colors():
    body = request.get_json(silent=True) or {}
    updates = {}
    for field, key in FIELD_KEYS.items():
        if field not in body:
            continue
        val = body.get(field)
        if val in (None, ""):
            updates[key] = ""
            continue
        if not isinstance(val, str) or not _HEX_COLOR_RE.match(val):
            return jsonify({"error": f"Neplatná hex barva pro {field}: {val}"}), 400
        updates[key] = val
    caps_included = "caps" in body
    if caps_included:
        updates[CAPS_KEY] = "1" if body.get("caps") else ""
    border_width_included = "border_width" in body
    if border_width_included:
        bw = body.get("border_width")
        if bw in (None, ""):
            updates[BORDER_WIDTH_KEY] = ""
        else:
            try:
                bw_int = int(bw)
            except (TypeError, ValueError):
                return jsonify({"error": f"Neplatná síla linky: {bw}"}), 400
            if not (BORDER_WIDTH_MIN <= bw_int <= BORDER_WIDTH_MAX):
                return jsonify({"error": f"Síla linky musí být {BORDER_WIDTH_MIN}-{BORDER_WIDTH_MAX}px."}), 400
            updates[BORDER_WIDTH_KEY] = str(bw_int)
    sweep_included = "sweep_opacity" in body
    if sweep_included:
        sv = body.get("sweep_opacity")
        if sv in (None, ""):
            updates[SWEEP_OPACITY_KEY] = ""
        else:
            try:
                sv_f = round(float(sv), 2)
            except (TypeError, ValueError):
                return jsonify({"error": f"Neplatná síla efektu: {sv}"}), 400
            if not (SWEEP_OPACITY_MIN <= sv_f <= SWEEP_OPACITY_MAX):
                return jsonify({"error": f"Síla efektu musí být {SWEEP_OPACITY_MIN}-{SWEEP_OPACITY_MAX}."}), 400
            updates[SWEEP_OPACITY_KEY] = str(sv_f)
    if not updates:
        return jsonify({"error": "Nic k uložení."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for key, val in updates.items():
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    (key, val, val),
                )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "cat_tree_colors", None, str(updates))
    key_to_field = {key: field for field, key in FIELD_KEYS.items()}
    result = {
        key_to_field[key]: (val or None)
        for key, val in updates.items() if key not in (CAPS_KEY, BORDER_WIDTH_KEY, SWEEP_OPACITY_KEY)
    }
    if caps_included:
        result["caps"] = updates[CAPS_KEY] == "1"
    if border_width_included:
        result["border_width"] = int(updates[BORDER_WIDTH_KEY]) if updates[BORDER_WIDTH_KEY] else None
    if sweep_included:
        result["sweep_opacity"] = float(updates[SWEEP_OPACITY_KEY]) if updates[SWEEP_OPACITY_KEY] else None
    return jsonify({"status": "ok", **result})
