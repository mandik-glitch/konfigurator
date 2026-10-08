"""Konfigurovatelny valeckovy dopravnik ve verejnem API konfiguratoru (bot5, 2026-10-07; Robert: "chceme generator dopravniku, at je muzeme ukazovat ve 3D online nabidce").

Navrh, parametry a rozdeleni prace: docs/NAVRH_GENERATOR_DOPRAVNIKU.md. Tenhle modul je SHOP vrstva (jako stul_shop.py): schema voleb (cs / en / sk), resolve (cena, platnost, stavy voleb, odkaz na model),
cena a kusovnik z dilu, `pro_objednavku` / `glb_bytes` pro kosik a online nabidku a obsluha tras. Routy `/api/shop/products/<id>/configurator`, `/api/shop/configurator/resolve|model|glb` zustavaji
v stul_shop.py, ktery pro produkt s receptem `dopravnik_valeckovy` (app_settings.configurator_products) deleguje sem pres api/konfigurator_registr.py. Tvar schematu a odpovedi je stejny jako u stolu
(docs/KONTRAKT_KONFIGURATOR_UI.md), takze sdilene UI (webapp/js/product-configurator.js) jede beze zmeny.

Zavisi na dvou modulech, ktere psou jini boti; do kazdeho se saha jen pres kontrakt a import je LENIVY (chybejici modul = 503 not_ready jen u dopravniku, stolu se to netyka):
  * dopravnik_konfigurator (bot8): `sestav_dopravnik(**p)` -> {"parametry": efektivni, "dily": [{sku, nazev, mnozstvi, jednotka "ks"|"m", volitelne kusy + delka_mm}], "upozorneni": [{id, ...}]},
    konstanty ROZSAH {len, pitch, h: (min, max, krok)}, TYPY, SIRKY_PODLE_TYPU, chyba DopravnikChyba;
  * dopravnik_glb (bot10): `model_pro_parametry(parametry, razitka=True)` -> (hash, glb_bytes), RULES_VERSION; razitka loga jsou na vsech modelech generatoru vychozi (WORKFLOW pravidlo 61, Robert 2026-10-08), zivy model i GLB do kosiku/nabidky je dostanou.

CENA = recept docs/dopravniky_recept.json (v1, opraveno 2026-10-07): ceil(soucet(USD dilu x mnozstvi) x (1 + prirazka 10 %) x kurz x koeficient 1,2), USD z karet dilu podle SKU
(shop_products.dogus_list_price_usd; profily jsou USD za 1 METR, "m" = metry, "ks" = kusy), kurz = nejvyssi dogus_price_rate_used z pouzitych dilu, zaokrouhleni po radcich jako v receptu, takze dopravnik
z katalogoveho rozmeru ma stejnou cenu jako karta hotoveho dopravniku (test). Cena je bez DPH, cele Kc. Chybi-li dilu cena, cena neni (valid False) - nikdy "cena 0".
V prvni verzi bez bocnich voditek (Robert 2026-10-07: nejdriv zjistit, jak se drzi na ramu); klice guide / guidetype zustavaji ve vyberu s hodnotou "none" / "40".
"""
import base64
import copy
import hashlib
import hmac
import json
import math
import time
from collections import OrderedDict

from flask import Response, jsonify, request

from app import app, get_conn
import stul_api

RECEPT = "dopravnik_valeckovy"
RULES_VERSION = "2026-10-07.1"
PRIRAZKA_PCT = 10
KOEFICIENT = 1.2
TYC_M = 3.0                                   # prodejni tyc profilu (m): jen pro hmotnost (weight_g profilu je za celou tyc)
MODEL_PLATNOST_S = 15 * 60
PREFIX_TOKENU = "dop."
CACHE_MAX = 64
TYPY = ("alu", "knurl", "steel")
RAMY = ("full", "cross", "none")
VYCHOZI_VYBER = {"rtype": "alu", "width": 590, "len": 2000, "pitch": 150, "h": 800, "legs": "auto", "frame": "full", "guide": "none", "guidetype": "40"}
ROZSAH_ZALOHA = {"len": (1000, 6000, 100), "pitch": (75, 300, 25), "h": (570, 870, 10)}          # kdyz konfigurator rozsah nevystavi
SIRKY_ZALOHA = {"alu": (290, 440, 590, 790), "knurl": (290, 440, 590, 790), "steel": (290, 440, 590, 790, 990)}

TEXTY = {
    "cs": {
        "g_valecky": "Válečky", "g_rozmery": "Rozměry", "g_podvozek": "Podvozek",
        "rtype": "Typ válečku", "rtype_alu": "Hliník, hladký (Ø50)", "rtype_knurl": "Hliník, vroubkovaný (Ø50)", "rtype_steel": "Ocel (Ø51)",
        "width": "Šířka dopravníku (délka válečku)", "help_width": "Šířka je daná skutečnou délkou válečku. Ocelové válečky jsou i v délce 990 mm.",
        "pitch": "Rozteč válečků", "help_pitch": "Čím menší rozteč, tím víc válečků na metr a vyšší cena.",
        "len": "Délka dopravníku", "h": "Výška (horní hrana válečků)", "help_h": "Nohy jsou teleskopické, výšku lze nastavit v rozsahu nohou.",
        "legs": "Počet noh", "legs_auto": "Automaticky", "legs_4": "4 nohy", "legs_6": "6 noh", "legs_8": "8 noh", "help_legs": "Nejdelší volný úsek mezi nohama je 3 m, delší dopravník potřebuje víc noh.",
        "frame": "Spodní rám", "frame_full": "Příčky a podélná tyč", "frame_cross": "Jen příčky", "frame_none": "Bez rámu",
        "help_frame": "Spodní rám z hliníkového profilu 40×40 zpevňuje nohy.",
    },
    "en": {
        "g_valecky": "Rollers", "g_rozmery": "Dimensions", "g_podvozek": "Frame and legs",
        "rtype": "Roller type", "rtype_alu": "Aluminium, smooth (Ø50)", "rtype_knurl": "Aluminium, knurled (Ø50)", "rtype_steel": "Steel (Ø51)",
        "width": "Conveyor width (roller length)", "help_width": "The width is given by the actual roller length. Steel rollers are also available in 990 mm.",
        "pitch": "Roller pitch", "help_pitch": "A smaller pitch means more rollers per metre and a higher price.",
        "len": "Conveyor length", "h": "Height (top of the rollers)", "help_h": "The legs are telescopic, the height can be set within the range of the legs.",
        "legs": "Number of legs", "legs_auto": "Automatic", "legs_4": "4 legs", "legs_6": "6 legs", "legs_8": "8 legs", "help_legs": "The longest free span between legs is 3 m, a longer conveyor needs more legs.",
        "frame": "Lower frame", "frame_full": "Cross bars and a long bar", "frame_cross": "Cross bars only", "frame_none": "No frame",
        "help_frame": "The lower frame made of 40×40 aluminium profile stiffens the legs.",
    },
    "sk": {
        "g_valecky": "Valčeky", "g_rozmery": "Rozmery", "g_podvozek": "Podvozok",
        "rtype": "Typ valčeka", "rtype_alu": "Hliník, hladký (Ø50)", "rtype_knurl": "Hliník, ryhovaný (Ø50)", "rtype_steel": "Oceľ (Ø51)",
        "width": "Šírka dopravníka (dĺžka valčeka)", "help_width": "Šírka je daná skutočnou dĺžkou valčeka. Oceľové valčeky sú aj v dĺžke 990 mm.",
        "pitch": "Rozstup valčekov", "help_pitch": "Čím menší rozstup, tým viac valčekov na meter a vyššia cena.",
        "len": "Dĺžka dopravníka", "h": "Výška (horná hrana valčekov)", "help_h": "Nohy sú teleskopické, výšku možno nastaviť v rozsahu nôh.",
        "legs": "Počet nôh", "legs_auto": "Automaticky", "legs_4": "4 nohy", "legs_6": "6 nôh", "legs_8": "8 nôh", "help_legs": "Najdlhší voľný úsek medzi nohami je 3 m, dlhší dopravník potrebuje viac nôh.",
        "frame": "Spodný rám", "frame_full": "Priečky a pozdĺžna tyč", "frame_cross": "Iba priečky", "frame_none": "Bez rámu",
        "help_frame": "Spodný rám z hliníkového profilu 40×40 spevňuje nohy.",
    },
}
UPOZORNENI = {
    "cs": {"len_upravena": "Délka dopravníku upravena na {hodnota} mm.", "sirka_upravena": "Šířka upravena na {hodnota} mm, vybraný typ válečku tuhle šířku nemá.",
           "pitch_upraven": "Rozteč válečků upravena na {hodnota} mm.", "h_upravena": "Výška upravena na {hodnota} mm, nohy ji jinak nenastaví.",
           "nohy_zvyseny": "Počet noh zvýšen na {hodnota}, při této délce jich je potřeba aspoň tolik."},
    "en": {"len_upravena": "Conveyor length adjusted to {hodnota} mm.", "sirka_upravena": "Width adjusted to {hodnota} mm, the selected roller type does not come in this width.",
           "pitch_upraven": "Roller pitch adjusted to {hodnota} mm.", "h_upravena": "Height adjusted to {hodnota} mm, the legs cannot be set otherwise.",
           "nohy_zvyseny": "The number of legs was raised to {hodnota}, at least that many are needed for this length."},
    "sk": {"len_upravena": "Dĺžka dopravníka upravená na {hodnota} mm.", "sirka_upravena": "Šírka upravená na {hodnota} mm, vybraný typ valčeka túto šírku nemá.",
           "pitch_upraven": "Rozstup valčekov upravený na {hodnota} mm.", "h_upravena": "Výška upravená na {hodnota} mm, nohy ju inak nenastavia.",
           "nohy_zvyseny": "Počet nôh zvýšený na {hodnota}, pri tejto dĺžke ich treba aspoň toľko."},
}
DUVOD_SIRKY = {"cs": "Tenhle typ válečku tuhle šířku nemá.", "en": "This roller type does not come in this width.", "sk": "Tento typ valčeka túto šírku nemá."}
DUVOD_NOHY = {"cs": "Při této délce je potřeba víc noh.", "en": "This length needs more legs.", "sk": "Pri tejto dĺžke treba viac nôh."}

_CENY = {"t": 0.0, "map": {}}
_RESOLVE_CACHE = OrderedDict()
_STAV_PODLE_HASHE = OrderedDict()
CENY_TTL_S = 60.0


class Nedostupny(Exception):
    """Chybi modul od jineho bota (konfigurator / GLB) - dopravnik zatim neni pripraveny; stolu se to netyka."""


def _import(jmeno):
    try:
        return __import__(jmeno)
    except ModuleNotFoundError as e:
        if e.name == jmeno:
            raise Nedostupny(jmeno) from e
        raise


def _K():
    return _import("dopravnik_konfigurator")


def _GLB():
    return _import("dopravnik_glb")


def _lang(v):
    v = (v or "").lower()[:2]
    if v in TEXTY:
        return v
    al = (request.headers.get("Accept-Language") or "").lower()[:2] if request else ""
    return al if al in TEXTY else "cs"


def _t(lang):
    return TEXTY.get(lang) or TEXTY["en"]


def konfigurovatelny(product_id):
    import konfigurator_registr
    return bool(konfigurator_registr.je_dopravnik(product_id))


def _rozsah(K):
    r = getattr(K, "ROZSAH", None) or {}
    return {k: tuple(r.get(k) or ROZSAH_ZALOHA[k]) for k in ROZSAH_ZALOHA}


def _sirky(K):
    s = getattr(K, "SIRKY_PODLE_TYPU", None) or SIRKY_ZALOHA
    return {t: tuple(int(x) for x in s.get(t, SIRKY_ZALOHA[t])) for t in TYPY}


# ---------------------------------------------------------------------------------------------------------------------
# vyber
# ---------------------------------------------------------------------------------------------------------------------
def _cislo(v, vychozi):
    if isinstance(v, bool):
        return vychozi
    try:
        x = float(v)
    except (TypeError, ValueError):
        return vychozi
    return int(round(x)) if math.isfinite(x) else vychozi


def vychozi_vyber():
    return dict(VYCHOZI_VYBER)


def _zaklad(selection):
    """Hruby vyber z pozadavku: jen znama pole spravneho TYPU (rozsahy a platne kombinace hlida konfigurator); voditka jsou v 1. verzi vzdy vypnuta."""
    sel = selection if isinstance(selection, dict) else {}
    p = dict(VYCHOZI_VYBER)
    p["rtype"] = sel.get("rtype") if sel.get("rtype") in TYPY else p["rtype"]
    p["frame"] = sel.get("frame") if sel.get("frame") in RAMY else p["frame"]
    for k in ("width", "len", "pitch", "h"):
        p[k] = _cislo(sel.get(k), p[k])
    legs = sel.get("legs")
    p["legs"] = _cislo(legs, "auto") if legs not in (None, "auto") else "auto"
    if p["legs"] not in ("auto", 4, 6, 8):
        p["legs"] = "auto"
    return p


def _sestav(p):
    K = _K()
    return K.sestav_dopravnik(**p)


# ---------------------------------------------------------------------------------------------------------------------
# cena a kusovnik
# ---------------------------------------------------------------------------------------------------------------------
def _ceny_dilu(skus):
    """{sku: {usd, kurz, weight_g}} z karet dilu (cache 60 s; chybejici SKU se dotahnou)."""
    skus = set(skus)
    if time.time() - _CENY["t"] > CENY_TTL_S:
        _CENY.update(t=time.time(), map={})
    chybi = [s for s in skus if s not in _CENY["map"]]
    if chybi:
        cur = get_conn().cursor()
        cur.execute("SELECT sku, dogus_list_price_usd, dogus_price_rate_used, weight_g FROM shop_products WHERE is_archived=0 AND sku IN (" + ",".join(["%s"] * len(chybi)) + ")", chybi)
        for r in cur.fetchall():
            _CENY["map"][r["sku"]] = {"usd": float(r["dogus_list_price_usd"]) if r["dogus_list_price_usd"] is not None else None,
                                      "kurz": float(r["dogus_price_rate_used"]) if r["dogus_price_rate_used"] is not None else None,
                                      "weight_g": float(r["weight_g"]) if r["weight_g"] is not None else None}
        for s in chybi:
            _CENY["map"].setdefault(s, {"usd": None, "kurz": None, "weight_g": None})
    return {s: _CENY["map"][s] for s in skus}


def cena_dilu(dily, kurz=None):
    """({net, usd, kurz, radky}, []) nebo (None, [sku bez ceny]). `kurz` jen pro testy (jinak nejvyssi kurz z karet dilu). Zaokrouhleni po radcich jako v receptu (mnozstvi na 3, radek na 2 desetinna)."""
    ceny = _ceny_dilu([d["sku"] for d in dily])
    bez = sorted({d["sku"] for d in dily if not ceny[d["sku"]]["usd"]})
    if bez:
        return None, bez
    kurzy = [ceny[d["sku"]]["kurz"] for d in dily if ceny[d["sku"]]["kurz"]]
    if kurz is None and not kurzy:
        return None, sorted({d["sku"] for d in dily})
    k = float(kurz) if kurz is not None else max(kurzy)
    radky = [round(ceny[d["sku"]]["usd"] * round(d["mnozstvi"], 3), 2) for d in dily]
    soucet = round(sum(radky), 2)
    net = math.ceil(soucet * (1 + PRIRAZKA_PCT / 100.0) * k * KOEFICIENT - 1e-9)
    return {"net": net, "usd": soucet, "kurz": k, "radky": radky}, []


def _hmotnost(dily):
    """(kg, chybi [nazvy]): hmotnost z karet dilu; u metru (profily) je weight_g za celou tyc TYC_M m."""
    ceny = _ceny_dilu([d["sku"] for d in dily])
    g, chybi = 0.0, []
    for d in dily:
        w = ceny[d["sku"]]["weight_g"]
        if w is None:
            chybi.append(d["nazev"])
        else:
            g += w * d["mnozstvi"] / (TYC_M if d["jednotka"] == "m" else 1.0)
    return round(g / 1000.0, 2), chybi


def _neutralni_bom(dily):
    """[{nazev, mnozstvi, rozmer}] bez cisel dilu a dodavatelu; dil s `kusy` + `delka_mm` jde jako kusy o delce (rezny seznam), ostatni mnozstvim."""
    out = []
    for d in dily:
        if d.get("kusy") and d.get("delka_mm"):
            out.append({"nazev": d["nazev"], "mnozstvi": int(d["kusy"]), "rozmer": f"{float(d['delka_mm']):.0f} mm"})
        else:
            m = float(d["mnozstvi"])
            out.append({"nazev": d["nazev"], "mnozstvi": int(round(m)) if m == int(m) else round(m, 2), "rozmer": "m" if d["jednotka"] == "m" else None})
    return sorted(out, key=lambda x: (x["nazev"], x["rozmer"] or ""))


def _souhrn(p, lang):
    """Souhrn voleb pro kosik / nabidku; jen to, co dopravnik obsahuje (bez spodniho ramu se radek neuvadi - Robert 2026-10-08 pro stoly, stejne pravidlo)."""
    t = _t(lang)
    radky = [{"id": "rtype", "label": t["rtype"], "value": t["rtype_" + p["rtype"]]},
            {"id": "width", "label": t["width"], "value": f"{int(p['width'])} mm"},
            {"id": "len", "label": t["len"], "value": f"{int(p['len'])} mm"},
            {"id": "pitch", "label": t["pitch"], "value": f"{int(p['pitch'])} mm"},
            {"id": "h", "label": t["h"], "value": f"{int(p['h'])} mm"},
            {"id": "legs", "label": t["legs"], "value": t["legs_" + str(int(p["legs"]))]},
            {"id": "frame", "label": t["frame"], "value": t["frame_" + p["frame"]]}]
    return [r for r in radky if not (r["id"] == "frame" and p["frame"] == "none")]


# ---------------------------------------------------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------------------------------------------------
def schema(lang="cs"):
    t = _t(lang)
    K = _K()
    r, sirky = _rozsah(K), _sirky(K)
    vsechny_sirky = sorted({s for t_ in TYPY for s in sirky[t_]})

    def slider(id_, group, help_=None):
        mn, mx, st = r[id_]
        return {"id": id_, "group": group, "label": t[id_], "help": help_, "type": "slider", "slider": {"min": mn, "max": mx, "step": st, "unit": "mm"}}

    def select(id_, group, ids, label_fn, help_=None):
        return {"id": id_, "group": group, "label": t[id_], "help": help_, "type": "select", "options": [{"id": str(o), "label": label_fn(o)} for o in ids]}
    return {
        "rules_version": RULES_VERSION,
        "recipe": RECEPT,
        "groups": [{"id": g, "label": t[g]} for g in ("g_valecky", "g_rozmery", "g_podvozek")],
        "slots": [
            select("rtype", "g_valecky", TYPY, lambda o: t["rtype_" + o]),
            slider("pitch", "g_valecky", t["help_pitch"]),
            select("width", "g_rozmery", vsechny_sirky, lambda o: f"{o} mm", t["help_width"]),
            slider("len", "g_rozmery"),
            slider("h", "g_podvozek", t["help_h"]),
            select("legs", "g_podvozek", ("auto", 4, 6, 8), lambda o: t["legs_" + str(o)], t["help_legs"]),
            select("frame", "g_podvozek", RAMY, lambda o: t["frame_" + o], t["help_frame"]),
        ],
        "default_selection": vychozi_vyber(),
    }


# ---------------------------------------------------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------------------------------------------------
def _hash(p):
    kanon = json.dumps({"p": {k: p[k] for k in sorted(VYCHOZI_VYBER)}, "v": RULES_VERSION}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(kanon.encode()).hexdigest()[:16]


def _efektivni(p):
    """(efektivni parametry s `legs` jako cislo, puvodni legs, gen) po normalizaci konfiguratorem."""
    gen = _sestav(p)
    ef = dict(VYCHOZI_VYBER)
    ef.update({k: gen["parametry"][k] for k in VYCHOZI_VYBER if k in gen["parametry"]})
    return ef, gen


def _upozorneni(gen, lang):
    out = []
    for u in gen.get("upozorneni") or []:
        sablona = (UPOZORNENI.get(lang) or UPOZORNENI["en"]).get(u.get("id"))
        text = sablona.format(**{k: u.get(k) for k in ("hodnota",)}) if sablona else (u.get("text") or "")
        if text:
            out.append({"slot": u.get("slot"), "action": "adjusted", "message": text})
    return out


def _spocti(p, lang):
    """(odpoved bez modelu, efektivni parametry, vysledek konfiguratoru). `selection` zachova volbu "auto" u poctu noh (po zmene delky se pocet znovu urci), hash a model jdou z efektivnich hodnot."""
    K = _K()
    ef, gen = _efektivni(p)
    h = _hash(ef)
    cena, bez_ceny = cena_dilu(gen["dily"])
    chyby = []
    if cena is None:
        chyby.append({"slot": None, "message": {"cs": "Cena konfigurace teď není k dispozici.", "en": "The price of this configuration is not available right now.", "sk": "Cena konfigurácie teraz nie je k dispozícii."}.get(lang, "")})
    out = {
        "selection": {**ef, "legs": "auto" if p["legs"] == "auto" else ef["legs"]}, "hash": h, "kod": "DOP-" + h[:6].upper(), "rules_version": RULES_VERSION, "valid": cena is not None, "errors": chyby,
        "notices": _upozorneni(gen, lang), "offers": [],
        "price": {"net": cena["net"], "vat_rate": stul_api.SAZBA_DPH, "gross": round(cena["net"] * (1 + stul_api.SAZBA_DPH / 100.0)), "currency": "CZK"} if cena else None,
        "dims": {"length_mm": ef["len"], "width_mm": ef["width"] + 2 * 23, "height_mm": ef["h"]},
    }
    t = _t(lang)
    sirky, r = _sirky(K), _rozsah(K)
    options = {s: {"min": r[s][0], "max": r[s][1]} for s in ("len", "pitch", "h")}
    zakl = cena["net"] if cena else None

    def alt(klic, hodnota):
        q = dict(ef)
        q[klic] = hodnota
        try:
            g2 = _sestav(q)
        except Exception:                                   # noqa: BLE001 - nepouzitelna varianta se jen oznaci jako zakazana
            return None, None
        c2, _ = cena_dilu(g2["dily"])
        return g2["parametry"], c2

    for klic, hodnoty in (("rtype", TYPY), ("width", sorted({s for t_ in TYPY for s in sirky[t_]})), ("legs", ("auto", 4, 6, 8)), ("frame", RAMY)):
        stav = {}
        for hv in hodnoty:
            kandidat = hv if klic != "legs" or hv != "auto" else "auto"
            pp, c2 = alt(klic, kandidat)
            zakazano, duvod = pp is None, None
            if klic == "width" and pp is not None and int(pp["width"]) != int(hv):
                zakazano, duvod = True, DUVOD_SIRKY[lang]
            if klic == "legs" and hv != "auto" and pp is not None and int(pp["legs"]) != int(hv):
                zakazano, duvod = True, DUVOD_NOHY[lang]
            delta = (c2["net"] - zakl) if (c2 and zakl is not None and not zakazano) else None
            stav[str(hv)] = {"price_delta": delta, "disabled": bool(zakazano), "reason": duvod}
        options[klic] = stav
    out["options"] = options
    return out, ef, gen


def resolve(selection, lang="cs", ted=None, skryt_cenu=False):
    """Telo odpovedi resolve (viz docs/KONTRAKT_KONFIGURATOR_UI.md); vzdy nova kopie. Vyhodi Nedostupny, kdyz chybi modul od jineho bota."""
    p = _zaklad(selection)
    klic = (json.dumps(p, sort_keys=True), lang, RULES_VERSION)
    if klic in _RESOLVE_CACHE and time.time() - _RESOLVE_CACHE[klic][0] < CENY_TTL_S:
        _RESOLVE_CACHE.move_to_end(klic)
        out, ef = copy.deepcopy(_RESOLVE_CACHE[klic][1]), dict(_RESOLVE_CACHE[klic][2])
    else:
        out, ef, _ = _spocti(p, lang)
        _RESOLVE_CACHE[klic] = (time.time(), copy.deepcopy(out), dict(ef))
        while len(_RESOLVE_CACHE) > CACHE_MAX:
            _RESOLVE_CACHE.popitem(last=False)
    _STAV_PODLE_HASHE[out["hash"]] = dict(ef)
    while len(_STAV_PODLE_HASHE) > CACHE_MAX * 4:
        _STAV_PODLE_HASHE.popitem(last=False)
    out["model"] = {"stav": "hotovo", "url": "/api/shop/configurator/glb/" + podepis_model(ef, ted), "odhad_ms": 0}
    return _bez_ceny(out) if skryt_cenu else out


def _bez_ceny(out):
    out.pop("price", None)
    for o in (out.get("options") or {}).values():
        for st in o.values():
            if isinstance(st, dict):
                st.pop("price_delta", None)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# kosik / objednavka / nabidka
# ---------------------------------------------------------------------------------------------------------------------
def pro_objednavku(selection, rules_version=None, lang="cs", product_id=None):
    """Konfigurace pro kosik / objednavku / nabidku (tvar jako stul_shop.pro_objednavku): {ok, selection (EFEKTIVNI), hash, kod, rules_version, valid, errors [str], notices [str], price {net, vat_rate,
    gross, currency} | None, bom [{nazev, mnozstvi, rozmer}], pocet_spoju, souhrn [{id, label, value}], hmotnost_kg, hmotnost_uplna, hmotnost_chybi, cenovy_souhrn}. Vzdy hluboka kopie."""
    lang = lang if lang in TEXTY else "cs"
    if rules_version is not None and str(rules_version) != RULES_VERSION:
        return {"ok": False, "chyba": "rules_changed", "rules_version": RULES_VERSION}
    r, ef, gen = _spocti(_zaklad(selection), lang)
    kg, chybi = _hmotnost(gen["dily"])
    cena = r.get("price")
    return {"ok": True, "selection": r["selection"], "hash": r["hash"], "kod": r["kod"], "rules_version": RULES_VERSION, "valid": r["valid"],
            "errors": [e["message"] for e in r["errors"]], "notices": [n["message"] for n in r["notices"]], "price": cena,
            "bom": _neutralni_bom(gen["dily"]), "pocet_spoju": 0, "souhrn": _souhrn(ef, lang),
            "hmotnost_kg": kg, "hmotnost_uplna": not chybi, "hmotnost_chybi": chybi,
            "cenovy_souhrn": ({"material_czk": cena["net"], "cut_czk": 0, "joint_czk": 0, "accessory_czk": 0, "packaging_czk": 0, "joint_count": 0, "weight_kg": kg} if cena else None)}


def glb_bytes(selection, razitka=True):
    """GLB (bytes) pro EFEKTIVNI vyber; s razitky loga (pravidlo 61: vsechny modely vsech generatoru), razitka=False jen vyslovne."""
    ef, _ = _efektivni(_zaklad(selection))
    return _GLB().model_pro_parametry(ef, razitka=razitka)[1]


# ---------------------------------------------------------------------------------------------------------------------
# token modelu a routy (volane z stul_shop.py pres konfigurator_registr)
# ---------------------------------------------------------------------------------------------------------------------
def _klic():
    return app.secret_key.encode() if isinstance(app.secret_key, str) else app.secret_key


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def podepis_model(p, ted=None):
    """Token pro /glb/<token>: "dop." + parametry (jen cisla a kratke kody) + platnost + HMAC (stateless)."""
    exp = int((ted or time.time()) + MODEL_PLATNOST_S)
    telo = _b64(json.dumps({k: p[k] for k in sorted(VYCHOZI_VYBER)}, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(_klic(), f"{telo}.{exp}".encode(), hashlib.sha256).digest()[:18]
    return f"{PREFIX_TOKENU}{telo}.{exp}.{_b64(sig)}"


def over_model(token, ted=None):
    """(parametry, None) nebo (None, 'podpis' | 'vyprsel')."""
    try:
        if not token.startswith(PREFIX_TOKENU):
            return None, "podpis"
        telo, exp, sig = token[len(PREFIX_TOKENU):].split(".")
        spravny = hmac.new(_klic(), f"{telo}.{exp}".encode(), hashlib.sha256).digest()[:18]
        if not hmac.compare_digest(spravny, _unb64(sig)):
            return None, "podpis"
        if (ted or time.time()) > int(exp):
            return None, "vyprsel"
        p = json.loads(_unb64(telo))
        return (p, None) if isinstance(p, dict) and set(p) == set(VYCHOZI_VYBER) else (None, "podpis")
    except Exception:                                       # noqa: BLE001
        return None, "podpis"


def zna_hash(h):
    return h in _STAV_PODLE_HASHE


def _nenalezeno():
    return jsonify({"error": "not_found"}), 404


def _nepripraveno(e):
    app.logger.warning("dopravnik_shop: chybi modul %s (jeste neni pripraven)", e)
    return jsonify({"error": "not_ready"}), 503


def odpoved_schema(product_id):
    try:
        out = schema(_lang(request.args.get("lang")))
    except Nedostupny as e:
        return _nepripraveno(e)
    out["systems"] = []
    out["env"] = None
    out["default_saved"] = False
    return jsonify(out)


def odpoved_resolve(body, skryt_cenu=False):
    if body.get("rules_version") and body.get("rules_version") != RULES_VERSION:
        return jsonify({"error": "rules_changed"}), 409
    try:
        return jsonify(resolve(body.get("selection"), _lang(body.get("lang")), skryt_cenu=skryt_cenu))
    except Nedostupny as e:
        return _nepripraveno(e)


def odpoved_model(h):
    p = _STAV_PODLE_HASHE.get(h)
    if p is None:
        return _nenalezeno()
    return jsonify({"model": {"stav": "hotovo", "url": "/api/shop/configurator/glb/" + podepis_model(p), "odhad_ms": 0}})


def odpoved_glb(token):
    p, chyba = over_model(token)
    if p is None:
        return (jsonify({"error": "expired" if chyba == "vyprsel" else "forbidden"}), 410 if chyba == "vyprsel" else 403)
    try:
        h, data = _GLB().model_pro_parametry(p, razitka=True)         # zivy model v generatoru: razitka jako vsude (pravidlo 61)
    except Nedostupny as e:
        return _nepripraveno(e)
    import stul_glb
    data, kodovani = stul_glb.zakoduj_pro_klienta(h, data, request.headers.get("Accept-Encoding"))
    resp = Response(data, mimetype="model/gltf-binary")
    if kodovani:
        resp.headers["Content-Encoding"] = kodovani
    resp.headers["Vary"] = "Accept-Encoding"
    resp.headers["Cache-Control"] = "private, max-age=600"
    resp.headers["Content-Disposition"] = "inline"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp
