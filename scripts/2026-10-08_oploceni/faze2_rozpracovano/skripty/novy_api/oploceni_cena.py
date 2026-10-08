"""CENA generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08): z `entries` a `extra_prace` vysledku sestav_oploceni() pres `configurator_price.price_entries` (stejna pravidla jako cena stolu a sestavy
ve Scene: profily prepoctem delky + rez + pausal za profil, desky podle plochy, spoje, prislusenstvi, balne).

VYPLNE: dokud v katalogu nejsou jejich karty (zaloz_karty_vyplni.py), pocitaji se jako VIRTUALNI desky `navrh:<typ>` s ORIENTACNI cenou za m2 (O.VYPLNE[...]["cena_m2"]). Po zalozeni karet zapise
`zaloz_karty_vyplni.py --apply` do app_settings `oploceni_karty_vyplni` JSON {typ: id karty}; `karty_vyplni(cur)` ho cte a `cena()` pak misto `navrh:<typ>` pouzije `product_<id>` (cena z karty), ale JEN
kdyz je karta v cenovem kontextu (visible_in_scene=1 + glb_file) - jinak zustane virtualni deska (nic se nerozbije, API se nemeni). Spojovaci material ke spojce (srouby, matice) se hleda v ctx podle SKU;
chybejici SKU jsou v `chybejici` (kusovnik ho ukaze bez ceny). Tesneni je v `extra_prace` (cena za metr z karty).
Pouziti: ctx = odvozeny_kontext(cur, stul_api._ctx_ceny()); cena(r, ctx, montaz_pct=0) -> {price_summary, bom, warnings, chybejici}."""
import json

import configurator_price as CP
import oploceni_konfigurator as O

DOPLNKOVE_KARTY = (3176, 3091, 3644, 3645, 3283, 3298, 3423, 3218, 3199)             # dily generatoru, ktere nejsou ve scene (visible_in_scene) - cena z karty
DOPLNKOVE_SKU = tuple(sorted({sku for lst in O.SPOJOVACI_MATERIAL.values() for sku, _ks, _n in lst}))        # spojovaci material ke spojce (srouby M6x16, otocne matice do drazky 10)
KARTY_VYPLNI_KLIC = "oploceni_karty_vyplni"                                           # app_settings: JSON {typ vyplne: id karty desky}


def virtualni_dily(parts, karty=None):
    """Doplni do slovniku dilu ctx['parts'] virtualni desky `navrh:<typ>` (vyplne bez karty v cenovem kontextu)."""
    karty = karty or {}
    for typ, info in O.VYPLNE.items():
        pid = "navrh:" + typ
        if typ in karty:
            continue
        parts.setdefault(pid, {"id": pid, "name": f"{info['nazev']} [{info['sku']}] (návrh karty)", "layer": "výplň", "sku": None, "length_mm": None, "cross_section_mm": [None, None], "weight_kg": None,
                               "price_czk": info["cena_m2"], "price_per_cut_czk": None, "is_board_material": True, "source": "navrh", "scene_coef": False, "unit": "m2", "price_basis": None})


def karty_vyplni(cur):
    """{typ: id karty} z app_settings `oploceni_karty_vyplni` (jen znamé typy a kladna cela cisla; chybne / chybejici nastaveni = {}); cte jen pres kurzor."""
    try:
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KARTY_VYPLNI_KLIC,))
        row = cur.fetchone()
        d = json.loads(row["setting_value"]) if row and row["setting_value"] else {}
    except Exception:                                                   # noqa: BLE001 - nastaveni je doplnek, cena se vzdy spocita (virtualni desky)
        return {}
    if not isinstance(d, dict):
        return {}
    return {t: int(v) for t, v in d.items() if t in O.VYPLNE and isinstance(v, int) and not isinstance(v, bool) and v > 0}


def doplnky_ctx(cur, ctx):
    """Doplni do ctx['parts'] karty dilu oploceni, ktere v katalogu sceny nejsou (panty, zapadka, patka, tesneni, spojovaci material), jako stul_api._doplnky_ctx (cena z karty; Dogus / profilove karty
    se scene koeficientem)."""
    cur.execute("SELECT id, name, sku, weight_g, price_czk_placeholder, unit, dogus_url, is_profile_material FROM shop_products WHERE id IN (" + ",".join(["%s"] * len(DOPLNKOVE_KARTY)) + ")"
                " OR sku IN (" + ",".join(["%s"] * len(DOPLNKOVE_SKU)) + ")", tuple(DOPLNKOVE_KARTY) + tuple(DOPLNKOVE_SKU))
    nove = []
    for r in cur.fetchall():
        part_id = f"product_{r['id']}"
        if part_id in ctx["parts"]:
            continue
        ctx["parts"][part_id] = {"id": part_id, "name": r["name"], "layer": "produkt", "sku": r.get("sku"), "length_mm": None, "cross_section_mm": [None, None],
                                 "weight_kg": float(r["weight_g"]) / 1000 if r["weight_g"] is not None else None,
                                 "price_czk": float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None, "price_per_cut_czk": None, "is_board_material": False,
                                 "source": "product", "scene_coef": bool(r.get("is_profile_material")) or bool(r.get("dogus_url")), "unit": (r.get("unit") or "").strip().lower() or None, "price_basis": None}
        nove.append(ctx["parts"][part_id])
    CP.apply_scene_coefficient(nove, ctx["pricing"].get("scene_price_coefficient", 1.0))
    return ctx


def odvozeny_kontext(cur, base):
    """Cenovy kontext oploceni z kontextu stolu `base` (stul_api._ctx_ceny; SDILENY, nemeni se): kopie + karty dilu mimo scenu + mapovani karet vyplni (jen ty, ktere jsou v kontextu dilu)."""
    ctx = dict(base)
    ctx["parts"] = dict(base["parts"])
    doplnky_ctx(cur, ctx)
    ctx["karty_vyplni"] = {t: i for t, i in karty_vyplni(cur).items() if f"product_{i}" in ctx["parts"] and ctx["parts"][f"product_{i}"].get("is_board_material")}
    return ctx


def tesneni_extra(vyplne, typy):
    """Dalsi prace do ceny: tesneni (metry = obvod otvoru kazde vyplne, cena za metr z karty tesneni podle typu vyplne `typy[i]`) - stejny tvar a poradi jako r["extra_prace"] jadra."""
    metry = {}
    for v, typ in zip(vyplne, typy):
        pid = O.VYPLNE[typ]["tesneni"]
        metry[pid] = metry.get(pid, 0.0) + 2.0 * (v["w"] + v["h"]) / 1000.0
    return [{"name": f"{O.TESNENI_KARTY[pid]['nazev']} [{O.TESNENI_KARTY[pid]['sku']}]", "qty": round(m, 3), "unit_czk": O.TESNENI_KARTY[pid]["cena_m"]} for pid, m in metry.items()]


def cena(r, ctx, montaz_pct=None, vyplne_typy=None):
    """Cena konfigurace `r` (vysledek sestav_oploceni) v kontextu `ctx`: {price_summary, bom, warnings, chybejici, ctx}. montaz_pct=0 = bez montaze (u oploceni se montaz nenabizi).
    `vyplne_typy` = jiny typ vyplne pro kazde pole (poradi r["vyplne"]) - presne preceneni bez nove stavby geometrie (rozdily cen voleb vyplne)."""
    ctx2 = dict(ctx)
    ctx2["parts"] = dict(ctx["parts"])
    karty = ctx.get("karty_vyplni") or {}
    virtualni_dily(ctx2["parts"], karty)
    sku_na_id = {str(v.get("sku")): k for k, v in ctx2["parts"].items() if v.get("sku")}
    entries, chybejici = [], []
    zaklad = r["entries"][:len(r["entries"]) - len(r["vyplne"])]                           # profily a dily; vyplne jsou posledni (poradi r["vyplne"])
    pole = r["entries"][len(zaklad):]
    extra = r["extra_prace"]
    if vyplne_typy is not None:
        pole = [{"product_id": "navrh:" + typ, "width_mm": e["width_mm"], "height_mm": e["height_mm"]} for e, typ in zip(pole, vyplne_typy)]
        extra = tesneni_extra(r["vyplne"], vyplne_typy)
    for e in zaklad + pole:
        pid = e["product_id"]
        if pid.startswith("navrh:") and pid[len("navrh:"):] in karty:
            e = dict(e, product_id=f"product_{karty[pid[len('navrh:'):]]}")
        entries.append(e)
    for m in r["kusovnik"]["spojovaci_material"]:
        pid = sku_na_id.get(str(m["sku"]))
        if pid is None:
            chybejici.append(m)
            continue
        entries.extend({"product_id": pid} for _ in range(m["mnozstvi"]))
    out = CP.price_entries(entries, ctx2, montaz_pct=montaz_pct, extra_work=extra)
    out["chybejici"] = chybejici
    out["ctx"] = ctx2
    return out
