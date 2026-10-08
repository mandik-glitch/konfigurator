"""SSE stul (system 41) ve verejnem API konfiguratoru stolu (bot8, 2026-10-05): schema voleb, normalizace vyberu, vypocet odpovedi resolve.

Verejne API (api/stul_shop.py) je psane pro stoly na sablone (systemy 30 / 35 / 40) s kopou prislusenstvi; SSE stul (api/stul_sse.py) ma jen zaklad, spodni polici a supliky, proto ma
VLASTNI schema (jen slidery sirka / hloubka / vyska / poloha stredni nohy / posun supliku / pocet supliku a prepinace police, supliky, supliky vlevo) a vlastni vypocet odpovedi. Obecne funkce
stul_shop.py se sem jen presmerovavaji (schema, vychozi_vyber, normalizuj, _spocti), vsechno ostatni (token modelu, routy, kosik, kusovnik) je spolecne. Vyber ZUSTAVA kompletni (vsechny
klice VYCHOZI_VYBER; co SSE nema, je vypnute), aby spolecny kod (souhrn voleb, prenos vyberu mezi systemy) fungoval beze zmeny.

Zakaznicke texty cs / en / sk: bez slov "laminodeska", "spojka", "katalog", SKU a "profil 30" (test ZAKAZANE); slovenske pojmenovani jeklu je "jakl" (ke kontrole bot7).
"""
import math

import jazyky                                                 # dalsi jazyky z dat (api/jazyky/<jazyk>.json), viz api/jazyky.py
import stul_api
import stul_glb
import stul_konfigurator as S
import stul_ovladani_verejne
import stul_sse

SYSTEM = S.SYSTEM_SSE
VYCHOZI = {"w": 2000, "d": 900, "h": 830, "mid": 50, "boxpos": 0, "shelf": 1, "drawers": True, "drawercount": int(S.SUPLIK_POCET_VYCHOZI), "drawleft": False}
VYPNUTE = ("posts", "wheels", "panels", "led", "ledlight", "socket", "pet", "feet", "braces", "bearings")          # volby, ktere SSE nema (v kompletnim vyberu vzdy vypnute)

TEXTY = {
    "cs": {
        "shelf": "Spodní police",
        "help_shelf": "Police leží na jeklových spojnicích nohou; její výška se mění spolu s výškou stolu.",
        "help_w": "Délku stolu určuje podélník (je o 10 mm kratší než deska – záslepky); největší deska je 3000 mm.",
        "help_d": "Hloubku stolu určuje jeklová spojnice nohy (400 až 1100 mm) a dva jekly 40 mm – hloubka je tedy 480 až 1180 mm.",
        "help_h": "Výška se nastavuje posunem jeklu nohy po vnitřním profilu 35×35 (700 až 1000 mm).",
        "help_mid": "Nad {prah} mm šířky přibývá uprostřed další noha. Posuň ji blíž k levé nebo pravé noze; deska i police se v její ose dělí na dvě desky.",
        "help_box": "Šuplíkový box lze posunout po celé délce podélníků; zapnutá volba „Šuplíky na levé straně“ ho přehodí k levé noze a posun se pak měří od ní.",
    },
    "en": {
        "shelf": "Lower shelf",
        "help_shelf": "The shelf rests on the steel cross-members of the legs; its height changes with the height of the table.",
        "help_w": "The length of the table is given by the rails (10 mm shorter than the worktop – end caps); the longest worktop is 3000 mm.",
        "help_d": "The depth of the table is given by the steel cross-member of the leg (400 to 1100 mm) plus two 40 mm box sections – so the depth is 480 to 1180 mm.",
        "help_h": "The height is set by sliding the box section of the leg along the 35×35 inner tube (700 to 1000 mm).",
        "help_mid": "Above {prah} mm width another leg is added in the middle. Move it closer to the left or right leg; the worktop and the shelf are split into two boards at its axis.",
        "help_box": "The drawer unit can be moved along the whole length of the rails; \"Drawers on the left side\" moves it to the left leg and the position is then measured from it.",
    },
    "sk": {
        "shelf": "Spodná polica",
        "help_shelf": "Polica leží na jaklových spojniciach nôh; jej výška sa mení spolu s výškou stola.",
        "help_w": "Dĺžku stola určuje pozdĺžnik (je o 10 mm kratší ako doska – záslepky); najväčšia doska je 3000 mm.",
        "help_d": "Hĺbku stola určuje jaklová spojnica nohy (400 až 1100 mm) a dva jakly 40 mm – hĺbka je teda 480 až 1180 mm.",
        "help_h": "Výška sa nastavuje posunom jakla nohy po vnútornom profile 35×35 (700 až 1000 mm).",
        "help_mid": "Nad šírku {prah} mm pribudne uprostred ďalšia noha. Posuňte ju bližšie k ľavej alebo pravej nohe; doska aj polica sa v jej osi delia na dve dosky.",
        "help_box": "Zásuvkový blok možno posúvať po celej dĺžke pozdĺžnikov; voľba „Zásuvky na ľavej strane“ ho presunie k ľavej nohe a posun sa potom meria od nej.",
    },
}
DUVOD_SUPLIKY = {"cs": "Šuplíky se při těchto rozměrech nevejdou (potřebují hloubku stolu aspoň {d} mm a šířku aspoň {w} mm).",
                 "en": "The drawers do not fit these dimensions (they need a table depth of at least {d} mm and a width of at least {w} mm).",
                 "sk": "Zásuvky sa pri týchto rozmeroch nezmestia (potrebujú hĺbku stola aspoň {d} mm a šírku aspoň {w} mm)."}
_PRAHY = {}


def _SH():
    import stul_shop
    return stul_shop


def _t(lang):
    SH = _SH()
    return {**SH.TEXTY[lang], **TEXTY[lang]}


def pravda(v):
    return bool(v) if not isinstance(v, str) else v.strip().lower() in ("1", "true", "on", "yes")


def vychozi_vyber(d):
    """Kompletni vychozi vyber SSE stolu: `d` = zaklad (VYCHOZI_VYBER), SSE hodnoty prepisou, co SSE nema, je vypnute."""
    d = dict(d)
    d.update(VYCHOZI)
    for k in VYPNUTE:
        d[k] = False
    return d


def schema(lang="cs"):
    """Schema voleb SSE stolu (viz stul_shop.schema): slidery sirka / hloubka / vyska, poloha stredni nohy, spodni police, supliky (pocet, posun, strana)."""
    SH = _SH()
    t = _t(lang)
    rz = S.SYSTEMY[SYSTEM]["rozsah"]
    pm = int(S.SYSTEMY[SYSTEM]["profil_mm"])

    def slider(id_, group, mn, mx, step, unit, help_=None):
        return {"id": id_, "group": group, "label": t[id_], "help": help_, "type": "slider", "slider": {"min": mn, "max": mx, "step": step, "unit": unit}}

    def toggle(id_, group, help_=None):
        return {"id": id_, "group": group, "label": t[id_], "help": help_, "type": "toggle", "options": [{"id": "on", "label": t[id_]}]}
    slots = [slider("w", "g_size", int(rz["sirka"][0]), int(rz["sirka"][1]), 10, "mm", t["help_w"]),
             slider("d", "g_size", int(rz["hloubka"][0]), int(rz["hloubka"][1]), 10, "mm", t["help_d"]),
             slider("h", "g_size", int(rz["vyska"][0]), int(rz["vyska"][1]), 10, "mm", t["help_h"]),
             slider("mid", "g_frame", 5, 95, 1, "%", t["help_mid"]),
             toggle("shelf", "g_frame", t["help_shelf"]),
             toggle("drawers", "g_extras"), slider("drawercount", "g_extras", S.SUPLIK_POCTY[0], S.SUPLIK_POCTY[-1], 1, "ks", t["help_drawercount"]),
             slider("boxpos", "g_extras", -2500, 2500, 10, "mm", t["help_box"]), toggle("drawleft", "g_extras")]
    zav = {"boxpos": ["drawers"], "drawleft": ["drawers"], "drawercount": ["drawers"]}
    for sl in slots:
        if sl["id"] in zav:
            sl["depends_on"] = list(zav[sl["id"]])
        if sl.get("help"):
            sl["help"] = sl["help"].replace("{prah}", str(int(S.prah_sirky(SYSTEM))))                # nastavitelny prah (Pravidla stolu SYSTEMU SSE)
    return {"rules_version": stul_glb.RULES_VERSION, "profile": f"{pm}x{pm}", "profile_mm": pm, "system": SYSTEM,
            "groups": [{"id": g, "label": t[g]} for g in ("g_size", "g_frame", "g_extras")], "slots": slots,
            "default_selection": SH.vychozi_vyber(SYSTEM)}


def mid_meze_pct(sirka):
    """(nejmene, nejvic) procent rozpeti krajnich noh (od leve nohy) pro stredni nohu: aspon MIN_ODSTUP_STREDNI_NOHY od krajnich noh a obe casti desky se vejdou do tabule laminodesky
    (stul_sse.stredni_meze); cela cisla uvnitr mezi, nejmene 5 a nejvic 95."""
    zl, zr = stul_sse.zeme_nohou(sirka)
    lo, hi = stul_sse.stredni_meze(sirka)
    span = zr - zl
    mn = max(5, math.ceil((lo - zl) / span * 100 - 1e-9))
    mx = min(95, math.floor((hi - zl) / span * 100 + 1e-9))
    return (mn, mx) if mn <= mx else (50, 50)


def normalizuj(selection):
    """Vybrany stav -> (parametry generatoru, normalizovany KOMPLETNI vyber pro UI). Hodnoty mimo rozsah se orezou, neznama pole zahodi, SSE nema volby (stojky, panely...) -> vypnute."""
    SH = _SH()
    sel = SH.vychozi_vyber(SYSTEM)
    if isinstance(selection, dict):
        for k in selection:
            if k in sel:
                sel[k] = selection[k]
    rz = S.SYSTEMY[SYSTEM]["rozsah"]
    p = {"system": SYSTEM,
         "sirka": SH._cislo(sel["w"], *rz["sirka"], VYCHOZI["w"], 10), "hloubka": SH._cislo(sel["d"], *rz["hloubka"], VYCHOZI["d"], 10), "vyska": SH._cislo(sel["h"], *rz["vyska"], VYCHOZI["h"], 10),
         "police": 1 if pravda(sel["shelf"]) else 0, "suplik": pravda(sel["drawers"])}
    p["suplik_vlevo"] = bool(pravda(sel["drawleft"]) and p["suplik"])
    p["suplik_pocet"] = int(SH._cislo(sel["drawercount"], S.SUPLIK_POCTY[0], S.SUPLIK_POCTY[-1], S.SUPLIK_POCET_VYCHOZI, 1)) if p["suplik"] else int(S.SUPLIK_POCET_VYCHOZI)
    p["suplik_posun"] = SH._cislo(sel["boxpos"], -3000, 3000, 0, 10) if p["suplik"] else 0.0
    mid_pct = SH._cislo(sel["mid"], 5, 95, 50, 1)
    p["stredni_noha"] = None
    if p["sirka"] > S.prah_sirky(SYSTEM):
        mn, mx = mid_meze_pct(p["sirka"])
        mid_pct = min(mx, max(mn, mid_pct))
        zl, zr = stul_sse.zeme_nohou(p["sirka"])
        p["stredni_noha"] = (zr - zl) * mid_pct / 100.0 if mid_pct != 50 else None
    else:
        mid_pct = 50
    norm = SH.vychozi_vyber(SYSTEM)                                           # NEUTRALNI kompletni vyber (nepodporovane volby a jejich rozmery z odeslaneho vyberu se nepreberou), pak jen volby SSE
    norm.update({"w": int(p["sirka"]), "d": int(p["hloubka"]), "h": int(p["vyska"]), "mid": int(mid_pct), "shelf": p["police"], "drawers": p["suplik"], "drawleft": p["suplik_vlevo"],
                 "drawercount": p["suplik_pocet"], "boxpos": int(p["suplik_posun"])})
    return p, norm


def prahy_suplik():
    """(hloubka, sirka) nejmensiho stolu SSE, na kterem zustanou supliky zapnute (pocita generator; vychozi rozmery jinak)."""
    if "s" not in _PRAHY:
        rz = S.SYSTEMY[SYSTEM]["rozsah"]

        def zustane(**kw):
            return bool(S.sestav_stul(system=SYSTEM, **kw)["parametry"]["suplik"])
        d = next((v for v in range(int(rz["hloubka"][0]), int(rz["hloubka"][1]) + 1, 10) if zustane(hloubka=v)), int(rz["hloubka"][1]))
        w = next((v for v in range(int(rz["sirka"][0]), int(rz["sirka"][1]) + 1, 10) if zustane(sirka=v)), int(rz["sirka"][1]))
        _PRAHY["s"] = (d, w)
    return _PRAHY["s"]


def spocti(p, norm, lang, h, gen):
    """Odpoved resolve pro SSE (viz stul_shop._spocti): cena, platnost, oznameni, volby (meze posuvniku, ceny a zakazy prepinacu), 3D ovladani."""
    SH = _SH()
    ta = SH.TEXTY_AKCI[lang]
    t = TEXTY[lang]
    norm.update({"shelf": p["police"], "drawers": bool(p["suplik"]), "drawleft": bool(p["suplik"] and p["suplik_vlevo"]), "boxpos": int(p["suplik_posun"]) if p["suplik"] else 0,
                 "drawercount": p["suplik_pocet"] if p["suplik"] else int(S.SUPLIK_POCET_VYCHOZI)})
    for k in VYPNUTE:
        norm[k] = False
    cena = stul_api.cena_konfigurace(gen["dily"], SYSTEM)
    cur = cena["bez_dph"] if cena else None
    errors = [{"slot": None, "message": SH.DUVODY[lang][None]} for _ in gen["problemy"][:1]]
    duvod_sup = DUVOD_SUPLIKY[lang].format(d=prahy_suplik()[0], w=prahy_suplik()[1])
    notices = [{"slot": "drawers", "action": "removed", "message": ta["odebrano"] + SH.NAZVY_SLOTU[lang]["drawers"] + " – " + duvod_sup} for o in gen["odebrano"] if o["volba"] == "suplik"]
    sse = gen.get("sse") or {}
    if sse.get("stredni") is not None:                                        # stul nad prahem sirky: desky delene u stredni nohy (formaty tabuli laminodesky)
        notices.append({"slot": "mid", "action": "info", "message": SH.text_desky_deleny(lang, "noha", 0, S.tabule())})

    def delta(**zmena):
        """Zmena ceny (Kc bez DPH), kdyz se `zmena` zapne; (delta, vysledek generatoru)."""
        alt = S.sestav_stul(**{**p, **zmena})
        c = stul_api.cena_konfigurace(alt["dily"], SYSTEM)
        return ((c["bez_dph"] - cur) if (c and cur is not None) else 0), alt

    options = {}
    rz = S.SYSTEMY[SYSTEM]["rozsah"]
    for sid, par in (("w", "sirka"), ("d", "hloubka"), ("h", "vyska")):
        options[sid] = {"min": int(rz[par][0]), "max": int(rz[par][1])}
    if p["sirka"] > S.prah_sirky(SYSTEM):
        mn, mx = mid_meze_pct(p["sirka"])
        options["mid"] = {"min": mn, "max": mx}
    else:
        options["mid"] = {"min": 50, "max": 50}
    sh = {"price_delta": 0, "disabled": False, "reason": None}
    if not p["police"]:
        sh["price_delta"] = delta(police=1)[0]
    options["shelf"] = {"on": sh}
    sp = {"price_delta": 0, "disabled": False, "reason": None}
    if not p["suplik"]:
        d_, alt = delta(suplik=True)
        sp["price_delta"] = d_
        if not alt["parametry"]["suplik"]:
            sp.update(disabled=True, reason=duvod_sup)
    options["drawers"] = {"on": sp}
    options["drawleft"] = {"on": {"price_delta": 0, "disabled": False, "reason": None}}
    options["drawercount"] = ({"min": S.SUPLIK_POCTY[0], "max": S.SUPLIK_POCTY[-1], "value": int(p["suplik_pocet"])} if p["suplik"]
                              else {"min": S.SUPLIK_POCET_VYCHOZI, "max": S.SUPLIK_POCET_VYCHOZI})
    sm = gen.get("suplik_meze")
    options["boxpos"] = ({"min": int(sm["min"]), "max": int(sm["max"]), "value": int(round(sm["hodnota"])), "fits": bool(sm["vejde"])} if (p["suplik"] and sm) else {"min": 0, "max": 0})
    gen["ovladani_scena"] = S.ovladani_3d(gen)
    vod = stul_glb.vodici(p, gen)
    if vod and vod.get("ovladani"):
        try:
            vod["ovladani"] = stul_ovladani_verejne.ovladani_verejne(vod["ovladani"], lang, S.SYSTEMY[SYSTEM]["profil_mm"])
        except stul_ovladani_verejne.ChybiPreklad as e:
            SH.app.logger.error("stul_shop: ovladani ve 3D vynechano: %s", e)
            vod.pop("ovladani", None)
    vat = float(stul_api.SAZBA_DPH)
    return {
        "vodici": vod or None,
        "selection": norm, "hash": h, "kod": "STL-" + h[:6].upper(), "rules_version": stul_glb.RULES_VERSION,
        "valid": not gen["problemy"], "errors": errors, "notices": notices, "offers": [],
        "price": ({"net": cena["bez_dph"], "vat_rate": vat, "gross": cena["s_dph"], "currency": "CZK"} if cena else None),
        "options": options,
    }


# DALSI JAZYKY (bot16, 2026-10-07): texty SSE stolu pro jazyky mimo cs / en / sk z api/jazyky/<jazyk>.json (chybejici klic = anglicka zaloha); bez sad se nic nezmeni.
jazyky.pripoj_stul_shop_sse(globals())
