"""CENA generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08; faze 1): z `entries` a `extra_prace` vysledku sestav_oploceni() pres `configurator_price.price_entries` (stejna pravidla jako cena stolu a sestavy
ve Scene: profily prepoctem delky + rez + pausal za profil, desky podle plochy, spoje, prislusenstvi, balne). Vyplne NEMAJI kartu v katalogu (zatim): pocitaji se jako VIRTUALNI desky `navrh:<typ>` s
ORIENTACNI cenou za m2 (O.VYPLNE[...]["cena_m2"]) - po zalozeni karet (zaloz_karty_vyplni.py) se `product_id` v entries zmeni na kartu. Spojovaci material ke spojce (srouby, matice) se hleda v ctx podle SKU
(ctx z stul_api._ctx_ceny); chybejici SKU jsou v `chybejici` (kusovnik ho ukaze bez ceny). Tesneni je v `extra_prace` (cena za metr z karty).
Pouziti: ctx = stul_api._ctx_ceny() (nebo configurator_price.load_ctx(cur)); cena(r, ctx) -> {price_summary, bom, warnings, chybejici}."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "api"))
import configurator_price as CP  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oploceni_konfigurator as O  # noqa: E402


def virtualni_dily(parts):
    """Doplni do slovniku dilu ctx['parts'] virtualni desky `navrh:<typ>` (vyplne bez karty)."""
    for typ, info in O.VYPLNE.items():
        pid = "navrh:" + typ
        parts.setdefault(pid, {"id": pid, "name": f"{info['nazev']} [{info['sku']}] (návrh karty)", "layer": "výplň", "sku": None, "length_mm": None, "cross_section_mm": [None, None], "weight_kg": None,
                               "price_czk": info["cena_m2"], "price_per_cut_czk": None, "is_board_material": True, "source": "navrh", "scene_coef": False, "unit": "m2", "price_basis": None})


def cena(r, ctx, montaz_pct=None):
    ctx2 = dict(ctx)
    ctx2["parts"] = dict(ctx["parts"])
    virtualni_dily(ctx2["parts"])
    sku_na_id = {str(v.get("sku")): k for k, v in ctx2["parts"].items() if v.get("sku")}
    entries, chybejici = list(r["entries"]), []
    for m in r["kusovnik"]["spojovaci_material"]:
        pid = sku_na_id.get(str(m["sku"]))
        if pid is None:
            chybejici.append(m)
            continue
        entries.extend({"product_id": pid} for _ in range(m["mnozstvi"]))
    out = CP.price_entries(entries, ctx2, montaz_pct=montaz_pct, extra_work=r["extra_prace"])
    out["chybejici"] = chybejici
    return out


DOPLNKOVE_KARTY = (3176, 3091, 3644, 3645, 3283, 3298, 3423, 3218, 3199)             # dily generatoru, ktere nejsou ve scene (visible_in_scene) - cena z karty
DOPLNKOVE_SKU = ("2.1.21.0616", "2.1.001.10.06")                                      # spojovaci material ke spojce (srouby M6x16, otocne matice do drazky 10)


def doplnky_ctx(cur, ctx):
    """Doplni do ctx['parts'] karty dilu oploceni, ktere v katalogu sceny nejsou (panty, zapadka, patka, ...), jako stul_api._doplnky_ctx (cena z karty; Dogus / profilove karty se scene koeficientem)."""
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
