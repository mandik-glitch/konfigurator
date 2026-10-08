"""Cena konfigurace sestavy - CISTA funkce bez prohlizece (bot5, 2026-10-02).

Zadani: zive 3D sestavy NE do auta (Robert pres bot3, TASKS.md "ZADANO 2026-10-02 ... zive 3D modely"). Cena konfigurace
se pocita na serveru z toho, co vrati compose() (bot10): seznam dilu (entries) s delkami profilu, rozmery desek a poctem
spoju. Tenhle modul tyhle cisla jen SECTE - pravidla jsou 1:1 prevzata z `computeAssemblyBomAndPrice` a `currentWeightPrice`
ve webapp/scene.html (JOINT_RULE_VERSION 3), takze konfigurace a sestava ulozena ze sceny davaji stejnou cenu.

  load_ctx(cur)                          -> ctx (jednou za pozadavek; cte katalog dilu, sazby a verzi pravidel spoju)
  price_entries(entries, ctx, ...)       -> {"bom": [...], "price_summary": {...}, "warnings": [...]}   (CISTA, bez DB a IO)
  apply_scene_coefficient(parts, coef)   -> koeficient sceny na dily (stejne pravidlo jako /api/katalog v app.py)
  montaz_pct_for_assembly(cur, id)       -> sazba montaze pro TYP sestavy (sestava_typ_sluzba), None = montaz se nenabizi

Vstup entries = [{product_id, length_mm?, width_mm?, height_mm?, joint_count?, custom_color?}]
  product_id : id dilu v katalogu sceny - cislo (shop_products.id -> "product_<id>") nebo text ("product_3671", "alu_30x30");
               alias klic `part_id`. Neznamy dil = ConfiguratorPriceError (zadne tiche vyrazeni, cena by byla podhodnocena).
  length_mm  : POVINNE u profilu (dil s delkou a prurezem v katalogu) - delka, na kterou je profil nastrihany.
  width_mm, height_mm : POVINNE u desky (is_board_material) - rozmery vyrezaneho kusu.
  joint_count: pocet spoju, ktere dil ve sestave ma (ve scene entry.jointCount) - urcuje geometrie v compose, ne cena.
  custom_color: jen pro seskupeni radku kusovniku (stejny dil jine barvy = jiny radek), jako ve scene.

Proc se tu NEPOUZIVAJI filtry ze sceny (razitko, kontrolni pomucka, karoserie, nahled importu): scena je potrebuje, protoze
`entries` tam jsou vsechno, co lezi ve scene. compose() vraci jen skutecne dily konfigurace, takze takovy dil by sem prisel
jen omylem - a to ma byt chyba (dil neni v katalogu cen / nema cenu), ne tiche prekryti.

Zaokrouhlovani je JS `Math.round` (pri .5 nahoru, ne Python banker's round) a soucty jdou ve STEJNEM poradi jako ve scene
(floaty), jinak by se ceny rozesly o halere/koruny proti sceny a online nabidkam.

Modul zamerne NEvola fetch_katalog_parts() z app.py: ta si bere vlastni get_conn() a jeho close() dela rollback na sdilenem
spojeni vlakna (past pooled conn) - uprostred transakce kosiku/objednavky by zahodila rozdelane zapisy. load_ctx(cur) cte
katalog PRES PREDANY KURZOR (zadny commit ani rollback) a rovnost s /api/katalog a /api/pricing-config hlida test
scripts/2026-10-02_konfigurator_cena_testy/test_cena_db.py. Dily karoserii (car_body_*) se nenacitaji - nemaji cenu a konfigurace
je nepouziva.
"""
import math


class ConfiguratorPriceError(ValueError):
    """Neplatny vstup ceny konfigurace (neznamy dil, chybejici rozmer, neplatne cislo). `code` je strojovy kod, `part_id` dil."""

    def __init__(self, message, code="neplatny_vstup", part_id=None):
        super().__init__(message)
        self.code = code
        self.part_id = part_id


# ---------------------------------------------------------------------------------------------------------------------
# pomocne funkce (1:1 se scenou)
# ---------------------------------------------------------------------------------------------------------------------

def _js_round(x):
    """JS Math.round: nejblizsi cele cislo, pri shode (.5) smerem k +nekonecnu (Python round() by dalo k sudemu)."""
    fl = math.floor(x)
    return fl + 1 if (x - fl) >= 0.5 else fl


def _is_profile(part):
    """scene-geometry-shared.js isProfilePart: dil ma delku a prurez."""
    cs = part.get("cross_section_mm")
    return bool(part.get("length_mm")) and bool(cs) and cs[0] is not None


def _part_display_name(part):
    """scene.html partDisplayName: nazev + SKU v hranatych zavorkach, pokud ho nazev jeste neobsahuje."""
    name = part.get("name") or part.get("nazev") or "díl"
    sku = part.get("sku")
    if sku and str(sku) not in str(name):
        return f"{name} [{sku}]"
    return name


def _positive_number(value, field, part_id):
    if isinstance(value, bool) or value is None:
        raise ConfiguratorPriceError(f"Dílu „{part_id}“ chybí rozměr {field}.", code="chybi_rozmer", part_id=part_id)
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ConfiguratorPriceError(f"Rozměr {field} dílu „{part_id}“ není číslo.", code="neplatne_cislo", part_id=part_id)
    if not math.isfinite(num) or num <= 0:
        raise ConfiguratorPriceError(f"Rozměr {field} dílu „{part_id}“ musí být kladné číslo.", code="neplatne_cislo", part_id=part_id)
    return num


def _joint_count(value, part_id):
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ConfiguratorPriceError(f"Počet spojů dílu „{part_id}“ není číslo.", code="neplatne_cislo", part_id=part_id)
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ConfiguratorPriceError(f"Počet spojů dílu „{part_id}“ není číslo.", code="neplatne_cislo", part_id=part_id)
    if not math.isfinite(num) or num < 0 or num != math.floor(num):
        raise ConfiguratorPriceError(f"Počet spojů dílu „{part_id}“ musí být celé nezáporné číslo.", code="neplatne_cislo", part_id=part_id)
    return int(num)


def _resolve_part(parts, entry):
    raw = entry.get("part_id", entry.get("product_id"))
    if raw is None or isinstance(raw, bool):
        raise ConfiguratorPriceError("Položka konfigurace nemá product_id.", code="chybi_dil")
    key = str(raw)
    if key in parts:
        return parts[key]
    if isinstance(raw, (int, float)) or key.isdigit():
        try:
            alt = f"product_{int(float(raw))}"
        except (TypeError, ValueError):
            alt = None
        if alt and alt in parts:
            return parts[alt]
    raise ConfiguratorPriceError(f"Díl „{raw}“ není v katalogu cen konfigurátoru.", code="neznamy_dil", part_id=key)


def _entry_weight_price(part, length_mm, width_mm, height_mm):
    """scene.html currentWeightPrice: {weight, price, length_mm, width_mm, height_mm} podle druhu dilu."""
    price_czk = part.get("price_czk")
    weight_kg = part.get("weight_kg")
    if part.get("is_board_material"):
        if price_czk is None:
            # scena: bez ceny desky se vraci katalogova hodnota (None) a rozmery se do kusovniku NEpropisou
            return {"weight": weight_kg, "price": None, "length_mm": None, "width_mm": None, "height_mm": None}
        area_m2 = (width_mm / 1000) * (height_mm / 1000)
        return {"weight": weight_kg, "price": price_czk * area_m2, "length_mm": None, "width_mm": width_mm, "height_mm": height_mm}
    if not _is_profile(part):
        return {"weight": weight_kg, "price": price_czk, "length_mm": None, "width_mm": None, "height_mm": None}
    factor = length_mm / part["length_mm"]
    return {
        "weight": weight_kg * factor if weight_kg is not None else None,
        "price": price_czk * factor if price_czk is not None else None,
        "length_mm": length_mm, "width_mm": None, "height_mm": None,
    }


# ---------------------------------------------------------------------------------------------------------------------
# CISTA cena
# ---------------------------------------------------------------------------------------------------------------------

def price_entries(entries, ctx, montaz_pct=None, strict_prices=False, extra_work=None):
    """Kusovnik a cena konfigurace z dilu (computeAssemblyBomAndPrice ve scene.html).

    entries       : seznam dilu, viz hlavicka modulu.
    ctx           : vysledek load_ctx(cur) - {"parts": {id: dil}, "pricing": {...}, "joint_rule_version": int}; funkce ho nemeni.
    montaz_pct    : volitelne PREBITI sazby montaze (% z ceny po balnem) - pro typy sestav s vlastni sazbou (ne globalni 20 %
                    z app_settings, ta plati pro auta); None = sazba z ctx.
    extra_work    : volitelne [{"name", "qty", "unit_czk"}] - DALSI PRACE mimo dily (napr. cena za vyrez v desce, stanovena v generatoru stolu); soucet (zaokrouhleny) se pocita
                    do mezisouctu PRED balnym a montazi jako rezy a spoje, v price_summary je `extra_work_czk` a seznam `extra_work` (radky s celkem).
    strict_prices : True = dil bez ceny v katalogu je chyba (ConfiguratorPriceError); False (vychozi, jako scena) = pocita se
                    jako 0 Kc a prida se varovani do `warnings`.

    Vraci {"bom": [{name, dim, qty, unit_price, total}], "price_summary": {...stejna pole jako ve scene...}, "warnings": [str]}.
    Vsechny castky jsou BEZ DPH, cela Kc; montaz je volitelna sluzba a NENI soucasti total_czk (jako ve scene).
    """
    parts = ctx["parts"]
    pricing = ctx["pricing"]
    joint_price_czk = pricing.get("joint_price_czk") or 0
    profile_flat_fee_czk = pricing.get("profile_flat_fee_czk") or 0
    packaging_pct = pricing.get("packaging_pct") or 0
    if montaz_pct is None:
        montaz_pct = pricing.get("montaz_pct") or 0
    else:
        montaz_pct = montaz_pct or 0
    accessories = pricing.get("accessories") or []
    warnings = []

    rows = []        # [(part, entry_values, jointCount, customColor)]
    for entry in entries:
        part = _resolve_part(parts, entry)
        part_id = part["id"]
        length_mm = width_mm = height_mm = None
        if part.get("is_board_material"):
            width_mm = _positive_number(entry.get("width_mm"), "width_mm", part_id)
            height_mm = _positive_number(entry.get("height_mm"), "height_mm", part_id)
        elif _is_profile(part):
            length_mm = _positive_number(entry.get("length_mm"), "length_mm", part_id)
        values = _entry_weight_price(part, length_mm, width_mm, height_mm)
        if values["price"] is None:
            if strict_prices:
                raise ConfiguratorPriceError(f"Díl „{_part_display_name(part)}“ nemá v katalogu cenu.", code="chybi_cena", part_id=part_id)
            warnings.append(f"Díl „{_part_display_name(part)}“ nemá v katalogu cenu (počítá se jako 0 Kč).")
        custom_color = entry.get("custom_color")
        rows.append((part, values, _joint_count(entry.get("joint_count"), part_id), custom_color if custom_color else ""))

    def is_material(part):
        return _is_profile(part) or bool(part.get("is_board_material"))

    total_w = 0
    total_material = 0
    total_accessory_parts = 0
    total_cut = 0
    total_profiles = 0
    total_joints = 0
    for part, values, joints, _color in rows:
        total_w = total_w + (values["weight"] or 0)
        if is_material(part):
            total_material = total_material + (values["price"] or 0)
        else:
            total_accessory_parts = total_accessory_parts + (values["price"] or 0)
        total_cut = total_cut + (part.get("price_per_cut_czk") or 0)
        total_profiles = total_profiles + (1 if _is_profile(part) else 0)
        total_joints = total_joints + joints

    total_profile_flat_fee = total_profiles * profile_flat_fee_czk
    total_joint_price = total_joints * joint_price_czk
    total_accessory_hardware = 0
    for acc in accessories:
        total_accessory_hardware = total_accessory_hardware + (acc.get("qty_per_joint") or 0) * total_joints * (acc.get("price_czk") or 0)
    total_accessory = total_accessory_parts + total_accessory_hardware

    # poradi a zaokrouhleni jako ve scene: nejdriv kazda slozka zvlast, balne az POSLEDNI z uz zaokrouhlenych slozek
    material_czk = _js_round(total_material)
    cut_czk = _js_round(total_cut)
    profile_flat_fee_czk_rounded = _js_round(total_profile_flat_fee)
    joint_czk = _js_round(total_joint_price)
    accessory_czk = _js_round(total_accessory)
    extra_rows = [{"name": str(x["name"]), "qty": x.get("qty"), "unit_czk": x.get("unit_czk"), "czk": _js_round((x.get("qty") or 0) * (x.get("unit_czk") or 0))} for x in (extra_work or [])]
    extra_work_czk = sum(x["czk"] for x in extra_rows)
    subtotal_czk = material_czk + cut_czk + profile_flat_fee_czk_rounded + joint_czk + accessory_czk + extra_work_czk
    packaging_czk = _js_round(subtotal_czk * packaging_pct / 100)
    grand_total = subtotal_czk + packaging_czk
    montaz_czk = _js_round(grand_total * montaz_pct / 100)

    groups = {}
    for part, values, _joints, color in rows:
        len_rounded = _js_round(values["length_mm"]) if values["length_mm"] is not None else None
        board_key = f"{_js_round(values['width_mm'])}x{_js_round(values['height_mm'])}" if values["width_mm"] is not None else None
        key = f"{part['id']}|{len_rounded}|{board_key}|{color}"
        unit = _js_round(values["price"]) if values["price"] is not None else 0
        group = groups.get(key)
        if group:
            group["qty"] += 1
        else:
            if len_rounded is not None:
                dim = f"{len_rounded} mm"
            elif board_key:
                dim = f"{_js_round(values['width_mm'])} × {_js_round(values['height_mm'])} mm"
            else:
                dim = "-"
            groups[key] = {"name": f"{_part_display_name(part)} ({part.get('layer')})", "dim": dim, "unit_price": unit, "qty": 1}
    bom = [{"name": g["name"], "dim": g["dim"], "qty": g["qty"], "unit_price": g["unit_price"],
            "total": _js_round(g["unit_price"] * g["qty"])} for g in groups.values()]

    return {
        "bom": bom,
        "price_summary": {
            "count": len(rows),
            "weight_kg": _js_round(total_w * 1000) / 1000,
            "material_czk": material_czk,
            "cut_czk": cut_czk,
            "profile_flat_fee_czk": profile_flat_fee_czk_rounded,
            "joint_czk": joint_czk,
            "joint_count": total_joints,
            "joint_rule_version": ctx["joint_rule_version"],
            "accessory_czk": accessory_czk,
            "scene_price_coefficient_applied": pricing.get("scene_price_coefficient") or 1,
            "extra_work_czk": extra_work_czk,
            "extra_work": extra_rows,
            "packaging_czk": packaging_czk,
            "total_czk": _js_round(grand_total),
            "montaz_pct_applied": montaz_pct,
            "montaz_czk": montaz_czk,
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------------------------------------------------
# koeficient sceny + nacteni kontextu (jediny kod s DB, jen pres predany kurzor)
# ---------------------------------------------------------------------------------------------------------------------

def apply_scene_coefficient(parts, coef):
    """Stejne pravidlo jako /api/katalog v app.py: cena dilu * koeficient JEN u dilu s priznakem scene_coef (profily a dily z
    externiho katalogu), zaokrouhleno na 2 desetinna mista; cena rezu (price_per_cut_czk) se NEnasobi - je to priplatek za praci.
    `parts` je iterovatelna kolekce dilu, meni se na miste."""
    if coef == 1.0:
        return
    for part in parts:
        base = part.get("price_czk")
        if base is not None and part.get("scene_coef"):
            part["price_czk"] = round(base * coef, 2)


def _setting(cur, key, default):
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (key,))
    row = cur.fetchone()
    return row["setting_value"] if row else default


def _setting_float(cur, key):
    raw = _setting(cur, key, "0")
    if raw is None:
        return 0
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ConfiguratorPriceError(f"Nastavení „{key}“ není číslo.", code="neplatne_nastaveni")


def _scene_coefficient(cur):
    """app.py get_scene_price_coefficient: neplatna/nekladna hodnota = 1.0 (cenotvorba nikdy nespadne na preklepu)."""
    raw = _setting(cur, "scene_price_coefficient", "1")
    try:
        coef = float(raw)
    except (TypeError, ValueError):
        return 1.0
    return coef if coef > 0 else 1.0


def _load_pricing(cur):
    """Stejna data jako GET /api/pricing-config (admin_settings.py::pricing_config)."""
    pricing = {
        "joint_price_czk": _setting_float(cur, "joint_price_czk"),
        "profile_flat_fee_czk": _setting_float(cur, "profile_flat_fee_czk"),
        "packaging_pct": _setting_float(cur, "packaging_pct"),
        "montaz_pct": _setting_float(cur, "montaz_pct"),
        "scene_price_coefficient": _scene_coefficient(cur),
    }
    cur.execute("SELECT id, name, price_czk, qty_per_joint FROM cfg_accessories WHERE active=1 ORDER BY sort_order, name")
    pricing["accessories"] = [
        {"id": r["id"], "name": r["name"], "price_czk": float(r["price_czk"]), "qty_per_joint": float(r["qty_per_joint"])}
        for r in cur.fetchall()
    ]
    return pricing


def _load_parts(cur):
    """Dily katalogu sceny, ktere maji cenu: cfg_dily (profily a drobny hardware) + shop_products viditelne ve scene.
    Stejne SQL, vyber a prepocty jako fetch_katalog_parts() v app.py (bez karoserii a bez poli, ktera cena nepotrebuje)."""
    parts = {}
    cur.execute("""
        SELECT d.id, d.name, d.layer,
               d.dim_x_mm, d.dim_y_mm, d.dim_z_mm,
               d.weight_kg_approx, d.price_czk_approx, d.price_per_cut_czk,
               spm.shop_product_id,
               sp.visible_in_scene AS sp_visible_in_scene, sp.glb_file AS sp_glb_file, sp.price_czk_placeholder,
               sp.dogus_url AS sp_dogus_url, sp.is_profile_material AS sp_is_profile_material
        FROM cfg_dily d
        LEFT JOIN (
            SELECT cfg_dily_id, MIN(id) AS shop_product_id
            FROM shop_products
            WHERE active=1 AND is_archived=0 AND cfg_dily_id IS NOT NULL
            GROUP BY cfg_dily_id
        ) spm ON spm.cfg_dily_id = d.id
        LEFT JOIN shop_products sp ON sp.id = spm.shop_product_id
        ORDER BY d.layer, d.name
    """)
    for r in cur.fetchall():
        # dvojnik v shop_products, ktery se v katalogu ukaze sam, je duplicita - vynechat (bot7, 2026-08-08, viz app.py)
        if r.get("shop_product_id") and r.get("sp_visible_in_scene") and r.get("sp_glb_file"):
            continue
        dims = [float(r[k]) if r[k] is not None else None for k in ("dim_x_mm", "dim_y_mm", "dim_z_mm")]
        if all(d is not None for d in dims):
            dims_sorted = sorted(dims)
            length_mm = dims_sorted[2]
            cross_section_mm = [dims_sorted[0], dims_sorted[1]]
        else:
            length_mm = None
            cross_section_mm = [None, None]
        if r.get("price_czk_placeholder") is not None:
            price = round(float(r["price_czk_placeholder"]) / 3.0, 2)
        else:
            price = float(r["price_czk_approx"]) if r["price_czk_approx"] is not None else None
        parts[str(r["id"])] = {
            "id": str(r["id"]), "name": r["name"], "layer": r["layer"], "sku": None,
            "length_mm": length_mm, "cross_section_mm": cross_section_mm,
            "weight_kg": float(r["weight_kg_approx"]) if r["weight_kg_approx"] is not None else None,
            "price_czk": price,
            "price_per_cut_czk": float(r["price_per_cut_czk"]) if r.get("price_per_cut_czk") is not None else None,
            "is_board_material": False, "source": "profil",
            "scene_coef": bool(r.get("sp_is_profile_material")) or bool(r.get("sp_dogus_url"))
                          or (not r.get("shop_product_id") and str(r.get("name") or "").lower().startswith("profil")),
            "unit": None, "price_basis": None,
        }
    cur.execute("""
        SELECT id, name, sku, weight_g, price_czk_placeholder, unit, is_board_material,
               board_sheet_width_mm, board_sheet_height_mm, dogus_url, is_profile_material
        FROM shop_products
        WHERE visible_in_scene=1 AND glb_file IS NOT NULL
        ORDER BY name
    """)
    for r in cur.fetchall():
        # cena desky MUSI byt v Kc/m2 (jednotka sceny); deska ulozena jako cena tabule se prepocte (app.py, 2026-09-10)
        price = float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None
        unit = (r.get("unit") or "").strip().lower() or None
        price_basis = unit
        if r["is_board_material"] and price is not None and unit != "m2":
            width, height = r.get("board_sheet_width_mm"), r.get("board_sheet_height_mm")
            area_m2 = (float(width) * float(height) / 1e6) if (width and height) else None
            if area_m2 and area_m2 > 0:
                price = round(price / area_m2, 4)
                price_basis = "m2_z_tabule"
            else:
                price_basis = "neznamy_prepocet_nelze"
        part_id = f"product_{r['id']}"
        parts[part_id] = {
            "id": part_id, "name": r["name"], "layer": "produkt", "sku": r.get("sku"),
            "length_mm": None, "cross_section_mm": [None, None],
            "weight_kg": float(r["weight_g"]) / 1000 if r["weight_g"] is not None else None,
            "price_czk": price, "price_per_cut_czk": None,
            "is_board_material": bool(r.get("is_board_material")), "source": "product",
            "scene_coef": bool(r.get("is_profile_material")) or bool(r.get("dogus_url")),
            "unit": unit, "price_basis": price_basis,
        }
    return parts


def montaz_pct_for_assembly(cur, assembly_id):
    """Sazba montaze (% z ceny po balnem) pro konfiguraci sestavy podle jejiho TYPU -> float nebo None (None = montaz se NENABIZI).
    Zdroj: tabulka sestava_typ_sluzba (admin ji nastavuje v obrazovce Typy sestav): radek PRO TYP TETO SESTAVY s klic 'montaz', aktivni=1 a
    pricing_mode 'procento_z_ceny'; hodnota musi byt > 0 a <= 100. Radek bez typu (sestava_typ_id NULL = vsechny typy) se zamerne NEPOUZIVA a
    typ AUTO se neridi touhle tabulkou vubec (auta berou app_settings.montaz_pct a price_summary.montaz_czk) - nenastaveno/nejasne = None
    (fail-closed, montaz se nenabidne). Cte jen pres predany kurzor (zadny commit/rollback). Vysledek se predava do price_entries(montaz_pct=...)."""
    cur.execute("SELECT t.id AS typ_id, t.kod FROM product_assemblies a JOIN sestava_typ t ON t.id = a.sestava_typ_id WHERE a.id=%s", (assembly_id,))
    typ = cur.fetchone()
    if not typ or str(typ["kod"]).upper() == "AUTO":
        return None
    cur.execute("SELECT hodnota FROM sestava_typ_sluzba WHERE sestava_typ_id=%s AND klic='montaz' AND aktivni=1 AND pricing_mode='procento_z_ceny' "
                "ORDER BY id LIMIT 1", (typ["typ_id"],))
    row = cur.fetchone()
    if not row or row["hodnota"] is None:
        return None
    pct = float(row["hodnota"])
    return pct if 0 < pct <= 100 else None


def load_ctx(cur):
    """Kontext ceny na JEDEN pozadavek: dily katalogu (s koeficientem sceny), sazby a verze pravidel spoju.
    Cte jen pres predany kurzor (zadny commit/rollback, bezpecne uprostred transakce). Volat jednou a predat do vsech
    price_entries tohoto pozadavku (cena alternativ voleb)."""
    pricing = _load_pricing(cur)
    parts = _load_parts(cur)
    apply_scene_coefficient(parts.values(), pricing["scene_price_coefficient"])
    # verze pravidel spoju = ta, podle ktere se v dashboardu pozna zastarala cena sestavy (obe cisla se meni SOUCASNE)
    from production_overview import CURRENT_JOINT_RULE_VERSION
    return {"parts": parts, "pricing": pricing, "joint_rule_version": CURRENT_JOINT_RULE_VERSION}
