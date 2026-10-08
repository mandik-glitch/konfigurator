"""Konfigurovatelny OCHRANNY KRYT A OPLOCENI ve verejnem API konfiguratoru (bot8, 2026-10-08, faze 2; Robert: "udelej generator ochranneho oploceni a krytovani stroju z profilu 40x40", "nahrat vsechno hned").

SHOP vrstva (jako dopravnik_shop.py / stul_shop.py): schema voleb (cs / en / sk), resolve (cena, platnost, stavy voleb, odkaz na model), cena a kusovnik z dilu, `pro_objednavku` / `glb_bytes` pro kosik
a online nabidku, token modelu a obsluha tras. Routy `/api/shop/products/<id>/configurator`, `/api/shop/configurator/resolve|model|glb` zustavaji v stul_shop.py, ktery pro produkt s receptem `oploceni_kryt`
(app_settings.configurator_products) deleguje sem pres api/konfigurator_registr.py. Tvar schematu a odpovedi je stejny jako u stolu a dopravniku (docs/KONTRAKT_KONFIGURATOR_UI.md), takze sdilene UI
(webapp/js/product-configurator.js) jede beze zmeny. Popis generatoru, pravidel a kontraktu: docs/KONTRAKT_OPLOCENI.md.

Vrstvy: oploceni_konfigurator.py (geometrie, kusovnik, entries; cista funkce), oploceni_cena.py (cena pres configurator_price.price_entries; vyplne = virtualni desky, dokud nemaji karty), oploceni_glb.py
(3D model). Tahle vrstva: verejne ID slotu (neutralni, bez internich nazvu) <-> parametry jadra, UPRAVA volby na proveditelnou (nic neprijde jako nesmyslna chyba: dvere, ktere se nevejdou, se vrati na
stenu a oznami se `notices`), stavy voleb (`options`: meze posuvniku, zakazane volby s duvodem, rozdily cen), cena, kusovnik pro zamestnance, hmotnost, verejne meze rozmeru a strop poctu dilu modelu.

CENA = celkova cena z price_entries bez DPH (cele Kc, bez montaze: u oploceni se montaz zatim nenabizi). Chybi-li dilu cena, cena neni (valid False) - nikdy "cena 0".
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
import oploceni_cena as OC
import oploceni_konfigurator as O
import stul_api

RECEPT = "oploceni_kryt"
RULES_VERSION = "2026-10-08.1"
PREFIX_TOKENU = "opl."
MODEL_PLATNOST_S = 15 * 60
CACHE_MAX = 64
CENY_TTL_S = 60.0
MAX_DILU_MODEL = 600                          # nejvic dilu v modelu pro verejnost (nejvetsi verejna konfigurace ma ~500); vic = model se nestavi (cena a kosik fungují)
VEREJNE_MEZE = {"w": (600, 4000, 10), "d": (600, 4000, 10), "h": (1000, 3000, 10), "door_w": (600, 1200, 10), "door_h": (1500, 2400, 10)}      # (min, max, krok) mm; jadro umi az 6000 x 6000

STRANY = ("front", "right", "back", "left")
STRANA_JADRO = {"front": "celo", "right": "prava", "back": "zadni", "left": "leva"}
TYP_STRANY = {"wall": "stena", "door": "dvere", "open": "otevreno"}
STRECHA = {"none": "zadna", "frame": "ram", "fill": "vyplne"}
VYPLN = {"pc_clear": "pc_cira", "pc_smoke": "pc_koura", "acrylic": "plexi", "mesh": "sit", "solid": "plna"}
POLOHA = {"left": "vlevo", "center": "stred", "right": "vpravo"}
ZAVESY = {"left": "vlevo", "right": "vpravo"}
ZAMEK = {"latch": "zapadka", "lock": "zamek", "none": "zadny"}
VYPLN_STRANY = ("fill_front", "fill_right", "fill_back", "fill_left", "fill_roof")
VYPLN_JADRO = {"fill_front": "vyplne_celo", "fill_right": "vyplne_prava", "fill_back": "vyplne_zadni", "fill_left": "vyplne_leva", "fill_roof": "vyplne_strecha"}
OBRAT = {"TYP_STRANY": {v: k for k, v in TYP_STRANY.items()}, "STRECHA": {v: k for k, v in STRECHA.items()}, "VYPLN": {v: k for k, v in VYPLN.items()},
         "POLOHA": {v: k for k, v in POLOHA.items()}, "ZAVESY": {v: k for k, v in ZAVESY.items()}, "ZAMEK": {v: k for k, v in ZAMEK.items()}}
VYCHOZI_VYBER = OrderedDict([
    ("w", 1500), ("d", 1500), ("h", 2200), ("front", "door"), ("right", "wall"), ("back", "wall"), ("left", "wall"), ("roof", "fill"), ("fill", "pc_clear"),
    ("fill_front", "auto"), ("fill_right", "auto"), ("fill_back", "auto"), ("fill_left", "auto"), ("fill_roof", "auto"),
    ("door_w", 800), ("door_h", None), ("door_pos", "right"), ("door_hinge", "right"), ("lock", "latch"), ("feet", False)])

TEXTY = {
    "cs": {
        "g_size": "Rozměry", "g_sides": "Strany a střecha", "g_fill": "Výplň", "g_fill_adv": "Výplň po stranách", "g_door": "Dveře", "g_extras": "Příslušenství",
        "w": "Šířka", "help_w": "Rozměr zleva doprava při pohledu na čelo (přední stranu).",
        "d": "Hloubka", "help_d": "Rozměr od čela dozadu. U jedné rovné strany bez střechy (oplocení) se hloubka nepoužije.",
        "h": "Výška", "help_h": "Celková výška od podlahy, včetně stavitelných patek.",
        "front": "Čelo (přední strana)", "right": "Pravá strana", "back": "Zadní strana", "left": "Levá strana",
        "help_sides": "Každá strana je stěna s výplní, strana s dveřmi, nebo bez stěny. Necháte-li jen jednu stranu a bez střechy, vznikne prosté oplocení.",
        "side_wall": "Stěna", "side_door": "Dveře", "side_open": "Bez stěny",
        "roof": "Střecha", "roof_none": "Bez střechy", "roof_frame": "Jen rám", "roof_fill": "S výplní",
        "fill": "Výplň", "help_fill": "Výplň je vsazená do drážky profilů; cena se mění podle plochy.",
        "fill_pc_clear": "Polykarbonát čirý 4 mm", "fill_pc_smoke": "Polykarbonát kouřový 4 mm", "fill_acrylic": "Plexisklo čiré 5 mm", "fill_mesh": "Svařovaná síť", "fill_solid": "Plná výplň (hliníkový kompozit 3 mm)",
        "fill_front": "Výplň – čelo", "fill_right": "Výplň – pravá strana", "fill_back": "Výplň – zadní strana", "fill_left": "Výplň – levá strana", "fill_roof": "Výplň – střecha", "fill_auto": "Jako celek",
        "help_fill_adv": "Chcete-li některou stranu nebo střechu s jinou výplní, zvolte ji tady; ostatní zůstanou podle volby „Výplň“.",
        "door_w": "Šířka dveří", "help_door_w": "Všechny dveře mají stejnou šířku, výšku a závěsy. Vedle dveří musí zůstat pole široké aspoň 150 mm.",
        "door_h": "Výška dveří", "help_door_h": "Automaticky = co nejvyšší, nejvýš 2000 mm; nad dveřmi vždy zůstane nadpraží aspoň 150 mm.",
        "door_pos": "Poloha dveří ve straně", "help_door_pos": "Při pohledu na stranu zvenku.", "pos_left": "Vlevo", "pos_center": "Uprostřed", "pos_right": "Vpravo",
        "door_hinge": "Závěsy", "help_door_hinge": "Dveře se otevírají ven.", "hinge_left": "Vlevo", "hinge_right": "Vpravo",
        "lock": "Zavírání", "lock_latch": "Kuličková západka", "lock_lock": "Bezpečnostní zámek", "lock_none": "Bez zámku",
        "feet": "Stavitelné patky", "help_feet": "Patky zvednou konstrukci o 79 mm; celková výška se nemění (sloupky jsou o patku kratší).",
        "dims_label": "Rozměry", "yes": "ano",
    },
    "en": {
        "g_size": "Dimensions", "g_sides": "Sides and roof", "g_fill": "Infill", "g_fill_adv": "Infill by side", "g_door": "Door", "g_extras": "Accessories",
        "w": "Width", "help_w": "Left to right when looking at the front side.",
        "d": "Depth", "help_d": "Front to back. A single straight side without a roof (a fence) has no depth.",
        "h": "Height", "help_h": "Overall height from the floor, including the levelling feet.",
        "front": "Front", "right": "Right side", "back": "Back", "left": "Left side",
        "help_sides": "Each side is a wall with infill, a side with a door, or open. Keep only one side and no roof and you get a plain fence.",
        "side_wall": "Wall", "side_door": "Door", "side_open": "Open",
        "roof": "Roof", "roof_none": "No roof", "roof_frame": "Frame only", "roof_fill": "With infill",
        "fill": "Infill", "help_fill": "The infill sits in the groove of the profiles; the price follows the area.",
        "fill_pc_clear": "Clear polycarbonate 4 mm", "fill_pc_smoke": "Smoked polycarbonate 4 mm", "fill_acrylic": "Clear acrylic 5 mm", "fill_mesh": "Welded wire mesh", "fill_solid": "Solid infill (aluminium composite 3 mm)",
        "fill_front": "Infill – front", "fill_right": "Infill – right side", "fill_back": "Infill – back", "fill_left": "Infill – left side", "fill_roof": "Infill – roof", "fill_auto": "Same as overall",
        "help_fill_adv": "To give one side or the roof a different infill, choose it here; the others follow the \"Infill\" choice.",
        "door_w": "Door width", "help_door_w": "All doors share the same width, height and hinges. A bay at least 150 mm wide must remain next to the door.",
        "door_h": "Door height", "help_door_h": "Automatic = as tall as possible, at most 2000 mm; at least 150 mm of lintel always remains above the door.",
        "door_pos": "Door position in the side", "help_door_pos": "Looking at the side from outside.", "pos_left": "Left", "pos_center": "Centre", "pos_right": "Right",
        "door_hinge": "Hinges", "help_door_hinge": "Doors open outwards.", "hinge_left": "Left", "hinge_right": "Right",
        "lock": "Closing", "lock_latch": "Ball catch", "lock_lock": "Safety lock", "lock_none": "No lock",
        "feet": "Levelling feet", "help_feet": "The feet raise the frame by 79 mm; the overall height stays the same (the posts are shorter by the foot).",
        "dims_label": "Dimensions", "yes": "yes",
    },
    "sk": {
        "g_size": "Rozmery", "g_sides": "Strany a strecha", "g_fill": "Výplň", "g_fill_adv": "Výplň po stranách", "g_door": "Dvere", "g_extras": "Príslušenstvo",
        "w": "Šírka", "help_w": "Rozmer zľava doprava pri pohľade na čelo (prednú stranu).",
        "d": "Hĺbka", "help_d": "Rozmer od čela dozadu. Pri jednej rovnej strane bez strechy (oplotenie) sa hĺbka nepoužije.",
        "h": "Výška", "help_h": "Celková výška od podlahy vrátane nastaviteľných pätiek.",
        "front": "Čelo (predná strana)", "right": "Pravá strana", "back": "Zadná strana", "left": "Ľavá strana",
        "help_sides": "Každá strana je stena s výplňou, strana s dverami, alebo bez steny. Ak ponecháte len jednu stranu a bez strechy, vznikne jednoduché oplotenie.",
        "side_wall": "Stena", "side_door": "Dvere", "side_open": "Bez steny",
        "roof": "Strecha", "roof_none": "Bez strechy", "roof_frame": "Len rám", "roof_fill": "S výplňou",
        "fill": "Výplň", "help_fill": "Výplň je vložená do drážky profilov; cena sa mení podľa plochy.",
        "fill_pc_clear": "Polykarbonát číry 4 mm", "fill_pc_smoke": "Polykarbonát dymový 4 mm", "fill_acrylic": "Plexisklo číre 5 mm", "fill_mesh": "Zváraná sieť", "fill_solid": "Plná výplň (hliníkový kompozit 3 mm)",
        "fill_front": "Výplň – čelo", "fill_right": "Výplň – pravá strana", "fill_back": "Výplň – zadná strana", "fill_left": "Výplň – ľavá strana", "fill_roof": "Výplň – strecha", "fill_auto": "Ako celok",
        "help_fill_adv": "Ak chcete mať niektorú stranu alebo strechu s inou výplňou, zvoľte ju tu; ostatné zostanú podľa voľby „Výplň“.",
        "door_w": "Šírka dverí", "help_door_w": "Všetky dvere majú rovnakú šírku, výšku a závesy. Vedľa dverí musí zostať pole široké aspoň 150 mm.",
        "door_h": "Výška dverí", "help_door_h": "Automaticky = čo najvyššie, najviac 2000 mm; nad dverami vždy zostane nadpražie aspoň 150 mm.",
        "door_pos": "Poloha dverí v strane", "help_door_pos": "Pri pohľade na stranu zvonku.", "pos_left": "Vľavo", "pos_center": "Uprostred", "pos_right": "Vpravo",
        "door_hinge": "Závesy", "help_door_hinge": "Dvere sa otvárajú von.", "hinge_left": "Vľavo", "hinge_right": "Vpravo",
        "lock": "Zatváranie", "lock_latch": "Guľôčková západka", "lock_lock": "Bezpečnostný zámok", "lock_none": "Bez zámku",
        "feet": "Nastaviteľné pätky", "help_feet": "Pätky zdvihnú konštrukciu o 79 mm; celková výška sa nemení (stĺpiky sú o pätku kratšie).",
        "dims_label": "Rozmery", "yes": "áno",
    },
}
# oznameni o UPRAVE volby (resolve.notices, action "adjusted") a duvody zakazanych voleb
UPRAVA = {
    "cs": {"clamp": "{label} upravena na {hodnota} mm (rozsah generátoru je {lo}–{hi} mm).",
           "h_feet": "Výška zvýšena na {hodnota} mm: s patkami musí mít konstrukce aspoň 1000 mm.",
           "door_side_height": "Na stranu „{strana}“ se dveře nevejdou: při této výšce potřebují výšku aspoň {min_vyska} mm. Zůstala stěna.",
           "door_side_length": "Na stranu „{strana}“ se dveře nevejdou: strana musí být dlouhá aspoň {min_delka} mm. Zůstala stěna.",
           "door_pos": "Dveře uprostřed se na nejkratší stranu s dveřmi nevejdou, poloha změněna na vpravo.",
           "door_w": "Šířka dveří upravena na {hodnota} mm: vedle dveří musí zůstat pole široké aspoň 150 mm.",
           "door_h": "Výška dveří upravena na {hodnota} mm: nad dveřmi musí zůstat nadpraží aspoň 150 mm.",
           "roof_forced": "Bez stěn a střechy by nezbylo nic – střecha nastavena na „Jen rám“."},
    "en": {"clamp": "{label} adjusted to {hodnota} mm (the generator range is {lo}–{hi} mm).",
           "h_feet": "Height raised to {hodnota} mm: with feet the structure must be at least 1000 mm.",
           "door_side_height": "A door does not fit the \"{strana}\" side: at this height it needs at least {min_vyska} mm. The wall stays.",
           "door_side_length": "A door does not fit the \"{strana}\" side: the side must be at least {min_delka} mm long. The wall stays.",
           "door_pos": "A centred door does not fit the shortest side with a door, the position was changed to right.",
           "door_w": "Door width adjusted to {hodnota} mm: a bay at least 150 mm wide must remain next to the door.",
           "door_h": "Door height adjusted to {hodnota} mm: at least 150 mm of lintel must remain above the door.",
           "roof_forced": "With no walls and no roof nothing would be left – the roof was set to \"Frame only\"."},
    "sk": {"clamp": "{label} upravená na {hodnota} mm (rozsah generátora je {lo}–{hi} mm).",
           "h_feet": "Výška zvýšená na {hodnota} mm: s pätkami musí mať konštrukcia aspoň 1000 mm.",
           "door_side_height": "Na stranu „{strana}“ sa dvere nezmestia: pri tejto výške potrebujú výšku aspoň {min_vyska} mm. Zostala stena.",
           "door_side_length": "Na stranu „{strana}“ sa dvere nezmestia: strana musí byť dlhá aspoň {min_delka} mm. Zostala stena.",
           "door_pos": "Dvere uprostred sa na najkratšiu stranu s dverami nezmestia, poloha zmenená na vpravo.",
           "door_w": "Šírka dverí upravená na {hodnota} mm: vedľa dverí musí zostať pole široké aspoň 150 mm.",
           "door_h": "Výška dverí upravená na {hodnota} mm: nad dverami musí zostať nadpražie aspoň 150 mm.",
           "roof_forced": "Bez stien a strechy by nezostalo nič – strecha nastavená na „Len rám“."},
}
DUVOD = {
    "cs": {"door_height": "Dveře se při této výšce nevejdou (potřebují výšku aspoň {min_vyska} mm).", "door_length": "Strana je na dveře krátká (musí mít aspoň {min_delka} mm).",
           "roof_none": "Bez stěn musí zůstat aspoň střecha nebo její rám."},
    "en": {"door_height": "A door does not fit at this height (it needs at least {min_vyska} mm).", "door_length": "The side is too short for a door (at least {min_delka} mm).",
           "roof_none": "With no walls at least the roof or its frame must remain."},
    "sk": {"door_height": "Dvere sa pri tejto výške nezmestia (potrebujú výšku aspoň {min_vyska} mm).", "door_length": "Strana je na dvere krátka (musí mať aspoň {min_delka} mm).",
           "roof_none": "Bez stien musí zostať aspoň strecha alebo jej rám."},
}
# upozorneni z jadra (id -> text); zakaznik je ma videt (bezpecnost: generator resi konstrukci, ne posouzeni stroje)
INFO = {
    "cs": {"norma": "Generátor řeší konstrukci krytu / oplocení. Bezpečnostní vzdálenosti, otvory výplní a zajištění dveří (ČSN EN ISO 14120, ČSN EN ISO 13857) posuzuje projektant stroje.",
           "kotveni": "Vysoká nebo dlouhá konstrukce: doporučujeme ji ukotvit k podlaze nebo ke zdi (kotvení se do ceny nepočítá).",
           "dvere_siroke": "Křídlo širší než 1000 mm je těžké: zkontrolujte únosnost závěsů a zvažte lehčí výplň.",
           "sit": "Síťová výplň: velikost ok a vzdálenost od nebezpečného místa musí vyhovovat ČSN EN ISO 13857."},
    "en": {"norma": "The generator designs the structure of the guard / fence. Safety distances, infill openings and door interlocking (EN ISO 14120, EN ISO 13857) are assessed by the machine designer.",
           "kotveni": "Tall or long structure: we recommend anchoring it to the floor or a wall (anchoring is not included in the price).",
           "dvere_siroke": "A leaf wider than 1000 mm is heavy: check the hinge load capacity and consider a lighter infill.",
           "sit": "Mesh infill: the mesh size and the distance from the danger zone must comply with EN ISO 13857."},
    "sk": {"norma": "Generátor rieši konštrukciu krytu / oplotenia. Bezpečnostné vzdialenosti, otvory výplní a zaistenie dverí (STN EN ISO 14120, STN EN ISO 13857) posudzuje projektant stroja.",
           "kotveni": "Vysoká alebo dlhá konštrukcia: odporúčame ju ukotviť k podlahe alebo k stene (kotvenie sa do ceny nepočíta).",
           "dvere_siroke": "Krídlo širšie ako 1000 mm je ťažké: skontrolujte únosnosť závesov a zvážte ľahšiu výplň.",
           "sit": "Sieťová výplň: veľkosť ôk a vzdialenosť od nebezpečného miesta musí vyhovovať STN EN ISO 13857."},
}
CHYBA = {"cs": {"obecna": "Tuhle konfiguraci nelze vyrobit.", "cena": "Cena konfigurace teď není k dispozici."},
         "en": {"obecna": "This configuration cannot be built.", "cena": "The price of this configuration is not available right now."},
         "sk": {"obecna": "Túto konfiguráciu nemožno vyrobiť.", "cena": "Cena konfigurácie teraz nie je k dispozícii."}}

_KONTEXT = {"t": 0.0, "base": None, "ctx": None}
_RESOLVE_CACHE = OrderedDict()
_STAV_PODLE_HASHE = OrderedDict()
_STAV_MAX = CACHE_MAX * 4


class Nedostupny(Exception):
    """Zachovano pro shodu s dopravnik_shop (modul oploceni je vzdy pripraven, import jadra je primy)."""


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
    return konfigurator_registr.recept_produktu(product_id) == RECEPT


def vychozi_vyber():
    return dict(VYCHOZI_VYBER)


# ---------------------------------------------------------------------------------------------------------------------
# vyber: verejne sloty <-> parametry jadra
# ---------------------------------------------------------------------------------------------------------------------
def _cislo(v, vychozi):
    if isinstance(v, bool):
        return vychozi
    try:
        x = float(v)
    except (TypeError, ValueError):
        return vychozi
    return int(round(x)) if math.isfinite(x) else vychozi


def _vycet(v, ids, vychozi):
    """Hodnota vyctu: jen retezec ze seznamu `ids` (cokoli jineho, i nehashovatelne, = vychozi)."""
    return v if isinstance(v, str) and v in ids else vychozi


def _zaklad(selection):
    """Hruby vyber z pozadavku: jen znama pole spravneho TYPU a platne hodnoty vyctu (cokoli jineho = vychozi); rozsahy a proveditelnost hlida `_uprav` a jadro."""
    sel = selection if isinstance(selection, dict) else {}
    p = dict(VYCHOZI_VYBER)
    for k in ("w", "d", "h", "door_w"):
        p[k] = _cislo(sel.get(k), p[k])
    dh = sel.get("door_h")
    p["door_h"] = None if dh in (None, "", "auto") else _cislo(dh, None)
    for k in STRANY:
        p[k] = _vycet(sel.get(k), TYP_STRANY, p[k])
    p["roof"] = _vycet(sel.get("roof"), STRECHA, p["roof"])
    p["fill"] = _vycet(sel.get("fill"), VYPLN, p["fill"])
    for k in VYPLN_STRANY:
        p[k] = _vycet(sel.get(k), VYPLN, "auto")
    p["door_pos"] = _vycet(sel.get("door_pos"), POLOHA, p["door_pos"])
    p["door_hinge"] = _vycet(sel.get("door_hinge"), ZAVESY, p["door_hinge"])
    p["lock"] = _vycet(sel.get("lock"), ZAMEK, p["lock"])
    f = sel.get("feet")
    p["feet"] = bool(f) if isinstance(f, (bool, int)) and f in (True, False, 0, 1) else p["feet"]
    return p


def _na_jadro(p):
    """Verejny vyber -> parametry jadra (jeste nenormalizovane)."""
    c = {"sirka": float(p["w"]), "hloubka": float(p["d"]), "vyska": float(p["h"]), "strecha": STRECHA[p["roof"]], "vyplne": VYPLN[p["fill"]],
         "dvere_sirka": float(p["door_w"]), "dvere_vyska": None if p["door_h"] is None else float(p["door_h"]), "dvere_poloha": POLOHA[p["door_pos"]],
         "dvere_zavesy": ZAVESY[p["door_hinge"]], "zamek": ZAMEK[p["lock"]], "patky": bool(p["feet"])}
    for s in STRANY:
        c[STRANA_JADRO[s]] = TYP_STRANY[p[s]]
    for k, jadro in VYPLN_JADRO.items():
        c[jadro] = None if p[k] == "auto" else VYPLN[p[k]]
    return c


def _z_jadra(c):
    """Normalizovane parametry jadra -> EFEKTIVNI verejny vyber."""
    p = {"w": int(round(c["sirka"])), "d": int(round(c["hloubka"])), "h": int(round(c["vyska"])), "roof": OBRAT["STRECHA"][c["strecha"]], "fill": OBRAT["VYPLN"][c["vyplne"]],
         "door_w": int(round(c["dvere_sirka"])), "door_h": None if c["dvere_vyska"] is None else int(round(c["dvere_vyska"])), "door_pos": OBRAT["POLOHA"][c["dvere_poloha"]],
         "door_hinge": OBRAT["ZAVESY"][c["dvere_zavesy"]], "lock": OBRAT["ZAMEK"][c["zamek"]], "feet": bool(c["patky"])}
    for s in STRANY:
        p[s] = OBRAT["TYP_STRANY"][c[STRANA_JADRO[s]]]
    for k, jadro in VYPLN_JADRO.items():
        p[k] = "auto" if c[jadro] is None else OBRAT["VYPLN"][c[jadro]]
    return OrderedDict((k, p[k]) for k in VYCHOZI_VYBER)


def _uprav(p0):
    """(verejny vyber po uprave, normalizovane parametry jadra, [(druh, data)]): vyber se upravi na PROVEDITELNY a kazda uprava se zaznamena do oznameni (druh + hodnoty pro text).
    Poradi: meze rozmeru -> patky a vyska -> strany s dvermi (nevejdou = stena) -> poloha, sirka a vyska dveri -> bez sten a strechy zustane aspon ram strechy."""
    p = dict(p0)
    upravy = []
    for k in ("w", "d", "h"):
        lo, hi, _ = VEREJNE_MEZE[k]
        v = min(hi, max(lo, p[k]))
        if v != p[k]:
            upravy.append(("clamp", {"slot": k, "hodnota": v, "lo": lo, "hi": hi}))
            p[k] = v
    if p["feet"] and p["h"] < 1000 + O.PATKA_VYSKA:
        p["h"] = int(1000 + O.PATKA_VYSKA)
        upravy.append(("h_feet", {"hodnota": p["h"]}))
    c = _na_jadro(p)
    dvere = []
    for s in STRANY:
        if p[s] != "door":
            continue
        ok, info = O.dvere_na_strane(c, STRANA_JADRO[s])
        if ok:
            dvere.append(s)
        else:
            p[s] = "wall"
            upravy.append(("door_side_height" if info["kod"] == "vyska" else "door_side_length", dict(info, strana=s)))
    if dvere:
        poloha = POLOHA[p["door_pos"]]
        if min(O.dvere_sirka_max(O.delka_strany(c, STRANA_JADRO[s]), poloha) or 0.0 for s in dvere) <= 0.0:
            p["door_pos"] = "right"                                          # stred se na nejkratsi stranu nevejde, vpravo ano (dvere_na_strane to overilo)
            poloha = "vpravo"
            upravy.append(("door_pos", {}))
        m = min(O.dvere_sirka_max(O.delka_strany(c, STRANA_JADRO[s]), poloha) for s in dvere)
        lo, hi, _ = VEREJNE_MEZE["door_w"]
        w = int(math.floor(min(hi, max(lo, p["door_w"]), m) + 1e-9))
        if w != p["door_w"]:
            upravy.append(("door_w" if (m < hi and p["door_w"] > m) else "clamp", {"hodnota": w, "slot": "door_w", "lo": lo, "hi": int(min(hi, m))}))
            p["door_w"] = w
        if p["door_h"] is not None:
            dh_max = int(math.floor(O.vyska_dveri_max(c)))
            lo, hi, _ = VEREJNE_MEZE["door_h"]
            v = min(hi, dh_max, max(lo, p["door_h"]))
            if v != p["door_h"]:
                upravy.append(("door_h" if (dh_max < hi and p["door_h"] > dh_max) else "clamp", {"hodnota": v, "slot": "door_h", "lo": lo, "hi": min(hi, dh_max)}))
                p["door_h"] = v
    else:                                                                   # bez dveri se parametry dveri neuplatni, ale musi zustat v mezich (jadro rozsahy overuje vzdy)
        p["door_w"] = min(VEREJNE_MEZE["door_w"][1], max(VEREJNE_MEZE["door_w"][0], p["door_w"]))
        if p["door_h"] is not None:
            p["door_h"] = min(VEREJNE_MEZE["door_h"][1], max(VEREJNE_MEZE["door_h"][0], p["door_h"]))
    if all(p[s] == "open" for s in STRANY) and p["roof"] == "none":
        p["roof"] = "frame"
        upravy.append(("roof_forced", {}))
    jadro = O.normalizuj(**_na_jadro(p))
    return p, jadro, upravy


def _text_upravy(druh, data, lang):
    t = _t(lang)
    sablona = (UPRAVA.get(lang) or UPRAVA["en"])[druh]
    d = dict(data)
    if "slot" in d:
        d["label"] = t.get(d["slot"], d["slot"])
    if "strana" in d:
        d["strana"] = t[d["strana"]].split(" (")[0].lower()
    for k in ("min_vyska", "min_delka", "hodnota", "lo", "hi"):
        if k in d:
            d[k] = int(round(d[k]))
    return sablona.format(**d)


def _slot_upravy(druh, data):
    return data.get("slot") or {"h_feet": "h", "door_side_height": data.get("strana"), "door_side_length": data.get("strana"), "door_pos": "door_pos", "door_w": "door_w", "door_h": "door_h",
                                "roof_forced": "roof"}.get(druh)


# ---------------------------------------------------------------------------------------------------------------------
# cena, kusovnik, hmotnost
# ---------------------------------------------------------------------------------------------------------------------
def _kontext():
    """Cenovy kontext oploceni (kopie kontextu stolu + karty dilu mimo scenu + mapovani karet vyplni); drzi se CENY_TTL_S."""
    base = stul_api._ctx_ceny()
    if _KONTEXT["ctx"] is None or _KONTEXT["base"] is not base or time.time() - _KONTEXT["t"] > CENY_TTL_S:
        cur = get_conn().cursor()
        _KONTEXT.update(ctx=OC.odvozeny_kontext(cur, base), base=base, t=time.time())
    return _KONTEXT["ctx"]


def _hash(jadro):
    kanon = json.dumps({"p": jadro, "v": RULES_VERSION}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(kanon.encode()).hexdigest()[:16]


def _neutralni_bom(r):
    """[{nazev, mnozstvi, rozmer}] bez cisel dilu a dodavatelu: profily podle delky, vyplne podle rozmeru tabule, ostatni kusy, tesneni v metrech, spojovaci material."""
    k = r["kusovnik"]
    out = []
    delky = OrderedDict()
    for x in k["profily"]:
        delky[x["delka_mm"]] = delky.get(x["delka_mm"], 0) + x["ks"]
    out += [{"nazev": "Profil 40×40 S10", "mnozstvi": n, "rozmer": f"{d:.0f} mm"} for d, n in delky.items()]
    out += [{"nazev": x["nazev"], "mnozstvi": x["mnozstvi"], "rozmer": None} for x in k["dily"]]
    out += [{"nazev": x["nazev"], "mnozstvi": x["ks"], "rozmer": f"{x['sirka_mm']:.0f} × {x['vyska_mm']:.0f} mm"} for x in k["vyplne"]]
    out += [{"nazev": x["nazev"], "mnozstvi": round(x["mnozstvi"], 2), "rozmer": "m"} for x in k["tesneni"]]
    out += [{"nazev": x["nazev"], "mnozstvi": x["mnozstvi"], "rozmer": None} for x in k["spojovaci_material"]]
    return sorted(out, key=lambda x: (x["nazev"], x["rozmer"] or ""))


def _hmotnost(r, cena_r):
    """(kg, [nazvy dilu bez hmotnosti]): soucet hmotnosti dilu z karet (price_summary.weight_kg) + ODHAD hmotnosti vyplni (plocha x kg/m2) a tesneni; dil bez hmotnosti v katalogu je v seznamu."""
    parts = cena_r["ctx"]["parts"]
    chybi = sorted({x["nazev"] for x in r["kusovnik"]["dily"] if (parts.get(x["part_id"]) or {}).get("weight_kg") in (None, 0, 0.0)})
    kg = (cena_r["price_summary"].get("weight_kg") or 0.0) + O.hmotnost_vyplni_kg(r)
    return round(kg, 2), chybi


def _rozmery_text(r):
    p = r["parametry"]
    rel = O.rozmery_relevantni(p)
    casti = ([p["sirka"]] if rel["sirka"] else []) + ([p["hloubka"]] if rel["hloubka"] else []) + [p["vyska"]]
    return " × ".join(str(int(round(x))) for x in casti)


def _souhrn(ef, jadro, lang):
    t = _t(lang)
    rel = O.rozmery_relevantni(jadro)
    out = [{"id": "dims", "label": t["dims_label"], "value": " × ".join(str(ef[k]) for k, ok in (("w", rel["sirka"]), ("d", rel["hloubka"]), ("h", True)) if ok) + " mm"}]
    for s in STRANY:
        out.append({"id": s, "label": t[s], "value": t["side_" + ef[s]]})
    out.append({"id": "roof", "label": t["roof"], "value": t["roof_" + ef["roof"]]})
    out.append({"id": "fill", "label": t["fill"], "value": t["fill_" + ef["fill"]]})
    for k in VYPLN_STRANY:
        if ef[k] != "auto":
            out.append({"id": k, "label": t[k], "value": t["fill_" + ef[k]]})
    if any(ef[s] == "door" for s in STRANY):
        out.append({"id": "door_w", "label": t["door_w"], "value": f"{ef['door_w']} mm"})
        out.append({"id": "door_h", "label": t["door_h"], "value": (f"{ef['door_h']} mm" if ef["door_h"] is not None else "–")})
        out.append({"id": "door_pos", "label": t["door_pos"], "value": t["pos_" + ef["door_pos"]]})
        out.append({"id": "door_hinge", "label": t["door_hinge"], "value": t["hinge_" + ef["door_hinge"]]})
        out.append({"id": "lock", "label": t["lock"], "value": t["lock_" + ef["lock"]]})
    if ef["feet"]:
        out.append({"id": "feet", "label": t["feet"], "value": t["yes"]})
    return out


def _info_upozorneni(r, lang):
    sab = INFO.get(lang) or INFO["en"]
    return [{"slot": None, "action": "info", "message": sab[u["id"]]} for u in r["upozorneni"] if u["id"] in sab]


def _cena_vyplni_alt(r, ctx, jadro, typ_alt):
    """Cena po zmene typu vyplne vsech poli, ktera maji typ CELKOVE vyplne (bez prepisu strany / strechy), na `typ_alt` (jen preceneni dilu, geometrie se nemeni -> presny rozdil)."""
    glob = jadro["vyplne"]
    typy = [typ_alt if v["typ"] == glob and jadro.get({"celo": "vyplne_celo", "prava": "vyplne_prava", "zadni": "vyplne_zadni", "leva": "vyplne_leva", "strecha": "vyplne_strecha"}[v["strana"]]) is None
            else v["typ"] for v in r["vyplne"]]
    return OC.cena(r, ctx, montaz_pct=0, vyplne_typy=typy)


# ---------------------------------------------------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------------------------------------------------
def schema(lang="cs"):
    t = _t(lang)

    def slider(id_, group, help_=None):
        mn, mx, st = VEREJNE_MEZE[id_]
        return {"id": id_, "group": group, "label": t[id_], "help": help_, "type": "slider", "slider": {"min": mn, "max": mx, "step": st, "unit": "mm"}}

    def vyber(typ, id_, group, ids, label_fn, help_=None):
        return {"id": id_, "group": group, "label": t[id_], "help": help_, "type": typ, "options": [{"id": o, "label": label_fn(o)} for o in ids]}

    def strana(id_, help_=None):
        return vyber("chips", id_, "g_sides", ("wall", "door", "open"), lambda o: t["side_" + o], help_)
    vyplne = tuple(VYPLN)
    return {
        "rules_version": RULES_VERSION,
        "recipe": RECEPT,
        "profile": "40x40",
        "groups": [{"id": g, "label": t[g]} for g in ("g_size", "g_sides", "g_fill", "g_fill_adv", "g_door", "g_extras")],
        "slots": [
            slider("w", "g_size", t["help_w"]), slider("d", "g_size", t["help_d"]), slider("h", "g_size", t["help_h"]),
            strana("front", t["help_sides"]), strana("right"), strana("back"), strana("left"),
            vyber("chips", "roof", "g_sides", ("none", "frame", "fill"), lambda o: t["roof_" + o]),
            vyber("select", "fill", "g_fill", vyplne, lambda o: t["fill_" + o], t["help_fill"]),
            vyber("select", "fill_front", "g_fill_adv", ("auto",) + vyplne, lambda o: t["fill_" + o], t["help_fill_adv"]),
            vyber("select", "fill_right", "g_fill_adv", ("auto",) + vyplne, lambda o: t["fill_" + o]),
            vyber("select", "fill_back", "g_fill_adv", ("auto",) + vyplne, lambda o: t["fill_" + o]),
            vyber("select", "fill_left", "g_fill_adv", ("auto",) + vyplne, lambda o: t["fill_" + o]),
            vyber("select", "fill_roof", "g_fill_adv", ("auto",) + vyplne, lambda o: t["fill_" + o]),
            slider("door_w", "g_door", t["help_door_w"]), slider("door_h", "g_door", t["help_door_h"]),
            vyber("chips", "door_pos", "g_door", ("left", "center", "right"), lambda o: t["pos_" + o], t["help_door_pos"]),
            vyber("chips", "door_hinge", "g_door", ("left", "right"), lambda o: t["hinge_" + o], t["help_door_hinge"]),
            vyber("chips", "lock", "g_door", ("latch", "lock", "none"), lambda o: t["lock_" + o]),
            {"id": "feet", "group": "g_extras", "label": t["feet"], "help": t["help_feet"], "type": "toggle"},
        ],
        "default_selection": vychozi_vyber(),
    }


# ---------------------------------------------------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------------------------------------------------
def _stavy(ef, jadro, r, ctx, cena_r, lang):
    """Stavy voleb pro tento vyber (UI: meze posuvniku, zakazane volby s duvodem, rozdily cen, skryte polozky)."""
    t = _t(lang)
    d = DUVOD.get(lang) or DUVOD["en"]
    rel = O.rozmery_relevantni(jadro)
    opt = {}
    h_min = VEREJNE_MEZE["h"][0] + (O.PATKA_VYSKA if ef["feet"] else 0)
    opt["w"] = {"min": VEREJNE_MEZE["w"][0], "max": VEREJNE_MEZE["w"][1]}
    opt["d"] = {"min": VEREJNE_MEZE["d"][0], "max": VEREJNE_MEZE["d"][1]}
    if not rel["sirka"]:
        opt["w"]["hidden"] = True
    if not rel["hloubka"]:
        opt["d"]["hidden"] = True
    opt["h"] = {"min": int(h_min), "max": VEREJNE_MEZE["h"][1]}
    vse_otevreno = all(ef[s] == "open" for s in STRANY)
    for s in STRANY:
        ok, info = O.dvere_na_strane(jadro, STRANA_JADRO[s])
        stav = {"wall": {"price_delta": None, "disabled": False, "reason": None}, "open": {"price_delta": None, "disabled": False, "reason": None},
                "door": {"price_delta": None, "disabled": not ok, "reason": None}}
        if not ok:
            stav["door"]["reason"] = d["door_height"].format(min_vyska=int(round(info["min_vyska"]))) if info["kod"] == "vyska" else d["door_length"].format(min_delka=int(round(info["min_delka"])))
        opt[s] = stav
    opt["roof"] = {"none": {"price_delta": None, "disabled": vse_otevreno, "reason": d["roof_none"] if vse_otevreno else None},
                   "frame": {"price_delta": None, "disabled": False, "reason": None}, "fill": {"price_delta": None, "disabled": False, "reason": None}}
    zakl = cena_r["price_summary"]["total_czk"]
    deltas = {}
    for typ in VYPLN:
        try:
            deltas[typ] = _cena_vyplni_alt(r, ctx, jadro, VYPLN[typ])["price_summary"]["total_czk"] - zakl
        except Exception:                                                  # noqa: BLE001 - rozdil ceny je doplnek
            deltas[typ] = None
    opt["fill"] = {typ: {"price_delta": deltas[typ], "disabled": False, "reason": None} for typ in VYPLN}
    for k, strana_jadro in (("fill_front", "celo"), ("fill_right", "prava"), ("fill_back", "zadni"), ("fill_left", "leva")):
        opt[k] = {"hidden": True} if jadro[strana_jadro] == "otevreno" else {}
    opt["fill_roof"] = {} if jadro["strecha"] == "vyplne" else {"hidden": True}
    jsou_dvere = any(ef[s] == "door" for s in STRANY)
    dl = min([O.dvere_sirka_max(O.delka_strany(jadro, STRANA_JADRO[s]), jadro["dvere_poloha"]) or 0.0 for s in STRANY if ef[s] == "door"] or [VEREJNE_MEZE["door_w"][1]])
    dh_max = O.vyska_dveri_max(jadro)
    opt["door_w"] = {"min": VEREJNE_MEZE["door_w"][0], "max": int(math.floor(max(VEREJNE_MEZE["door_w"][0], dl)))}
    opt["door_h"] = {"min": VEREJNE_MEZE["door_h"][0], "max": int(math.floor(max(VEREJNE_MEZE["door_h"][0], min(VEREJNE_MEZE["door_h"][1], dh_max)))),
                     "value": int(round(r["dvere"][0]["vyska_kridla"])) if r["dvere"] else int(round(min(2000.0, dh_max))), "auto": ef["door_h"] is None}
    for k in ("door_pos", "door_hinge", "lock"):
        opt[k] = {}
    if not jsou_dvere:
        for k in ("door_w", "door_h", "door_pos", "door_hinge", "lock"):
            opt[k]["hidden"] = True
    try:
        alt = dict(jadro, patky=not jadro["patky"])
        if alt["patky"]:
            alt["vyska"] = max(alt["vyska"], 1000.0 + O.PATKA_VYSKA)
        ra = O.sestav_oploceni(**O.normalizuj(**alt))
        dp = OC.cena(ra, ctx, montaz_pct=0)["price_summary"]["total_czk"] - zakl
    except Exception:                                                      # noqa: BLE001
        dp = None
    opt["feet"] = {"on": {"price_delta": dp if not jadro["patky"] else None, "disabled": False, "reason": None}}
    return opt


def _spocti(p0, lang):
    """(odpoved bez modelu, normalizovane parametry jadra, vysledek jadra, soukroma data pro zamestnance). `p0` = _zaklad(vyber)."""
    t = _t(lang)
    p, jadro, upravy = _uprav(p0)
    ef = _z_jadra(jadro)
    h = _hash(jadro)
    notices = [{"slot": _slot_upravy(druh, data), "action": "adjusted", "message": _text_upravy(druh, data, lang)} for druh, data in upravy]
    chyby = []
    out = {"selection": dict(ef), "hash": h, "kod": "OPL-" + h[:6].upper(), "rules_version": RULES_VERSION, "valid": False, "errors": chyby, "notices": notices, "offers": [], "price": None,
           "dims": None, "options": {}}
    try:
        r = O.sestav_oploceni(**jadro)
    except O.OploceniChyba as e:                                           # po uprave nemuze nastat; kdyby ano, je to oznamena chyba, ne vyjimka
        app.logger.warning("oploceni_shop: jadro po uprave odmitlo vyber %s: %s", jadro, e)
        chyby.append({"slot": e.data.get("slot"), "message": (CHYBA.get(lang) or CHYBA["en"])["obecna"]})
        return out, jadro, None, None
    ctx = _kontext()
    cena_r = OC.cena(r, ctx, montaz_pct=0)
    sum_ = cena_r["price_summary"]
    if cena_r["warnings"]:                                                 # dil bez ceny v katalogu: cena neni (nikdy "cena 0")
        chyby.append({"slot": None, "message": (CHYBA.get(lang) or CHYBA["en"])["cena"]})
    else:
        net = int(sum_["total_czk"])
        out["price"] = {"net": net, "vat_rate": stul_api.SAZBA_DPH, "gross": round(net * (1 + stul_api.SAZBA_DPH / 100.0)), "currency": "CZK"}
        out["valid"] = True
    out["notices"] = notices + _info_upozorneni(r, lang)
    rel = O.rozmery_relevantni(jadro)
    out["dims"] = {"width_mm": int(round(r["rozmery"]["sirka_mm"])), "depth_mm": int(round(r["rozmery"]["hloubka_mm"])) if rel["hloubka"] else None, "height_mm": int(round(r["rozmery"]["vyska_mm"]))}
    out["options"] = _stavy(ef, jadro, r, ctx, cena_r, lang)
    return out, jadro, r, {"cena_r": cena_r, "ctx": cena_r["ctx"]}


def resolve(selection, lang="cs", ted=None, skryt_cenu=False):
    """Telo odpovedi resolve (viz docs/KONTRAKT_KONFIGURATOR_UI.md); vzdy nova kopie (bez bloku pro zamestnance - ten pridava odpoved_resolve)."""
    out, jadro, r = _resolve_data(selection, lang)[:3]
    out = copy.deepcopy(out)
    if r is not None and len(r["dily"]) > MAX_DILU_MODEL:                  # na verejny model je konfigurace prilis rozsahla (cena a kosik fungují)
        out["model"] = {"stav": "chyba", "url": None, "odhad_ms": 0, "kod": "prilis_velky"}
    else:
        out["model"] = {"stav": "hotovo", "url": "/api/shop/configurator/glb/" + podepis_model(jadro, ted), "odhad_ms": 0}
    return _bez_ceny(out) if skryt_cenu else out


def _resolve_data(selection, lang):
    p0 = _zaklad(selection)
    klic = (json.dumps(p0, sort_keys=True), lang, RULES_VERSION)
    if klic in _RESOLVE_CACHE and time.time() - _RESOLVE_CACHE[klic][0] < CENY_TTL_S:
        _RESOLVE_CACHE.move_to_end(klic)
        z = _RESOLVE_CACHE[klic]
        out, jadro, r, soukr = z[1], z[2], z[3], z[4]
    else:
        out, jadro, r, soukr = _spocti(p0, lang)
        _RESOLVE_CACHE[klic] = (time.time(), out, jadro, r, soukr)
        while len(_RESOLVE_CACHE) > CACHE_MAX:
            _RESOLVE_CACHE.popitem(last=False)
    _STAV_PODLE_HASHE[out["hash"]] = dict(jadro)
    while len(_STAV_PODLE_HASHE) > _STAV_MAX:
        _STAV_PODLE_HASHE.popitem(last=False)
    return out, jadro, r, soukr


def _bez_ceny(out):
    out.pop("price", None)
    for o in (out.get("options") or {}).values():
        for st in o.values():
            if isinstance(st, dict):
                st.pop("price_delta", None)
    return out


def staff_blok(selection, lang="cs"):
    """Blok jen pro zamestnance (resolve s `staff: true` a platnou staff session; stejny tvar jako stul_shop._staff_blok): kompletni kusovnik s cenami, problemy, odkazy na vyrobu (zatim zadne)."""
    out, jadro, r, soukr = _resolve_data(selection, lang)
    if r is None:
        return None
    sum_ = soukr["cena_r"]["price_summary"]
    net = int(sum_["total_czk"])
    s_dph = round(net * (1 + stul_api.SAZBA_DPH / 100.0))
    kus = stul_api.kusovnik_z_ceny(soukr["cena_r"], soukr["ctx"], s_dph, soukr["cena_r"]["chybejici"])
    kus["montaz"] = {"pct": 0, "czk": 0, "poznamka": "u tohoto produktu se nenabízí"}
    kg, chybi = _hmotnost(r, soukr["cena_r"])
    kus["hmotnost_kg"] = kg
    kus["varovani"] = list(kus.get("varovani") or []) + [u["text"] for u in r["upozorneni"]] + ([f"Hmotnost je neúplná, chybí: {', '.join(chybi)}"] if chybi else [])
    return {"kusovnik": kus, "cena": {"bez_dph": net, "s_dph": s_dph, "sazba_dph": stul_api.SAZBA_DPH, "mena": "CZK"}, "problemy": [], "pocet_spoju": r["pocet_spoju"], "hash": out["hash"], "kod": out["kod"],
            "vyrobni_list_url": None, "vyrobni_sestava_url": None, "rozmery": r["rozmery"], "dilu": len(r["dily"])}


# ---------------------------------------------------------------------------------------------------------------------
# kosik / objednavka / nabidka
# ---------------------------------------------------------------------------------------------------------------------
def pro_objednavku(selection, rules_version=None, lang="cs", product_id=None):
    """Konfigurace pro kosik / objednavku / nabidku (tvar jako stul_shop.pro_objednavku): {ok, selection (EFEKTIVNI), hash, kod, rules_version, valid, errors [str], notices [str], price {net, vat_rate,
    gross, currency} | None, bom [{nazev, mnozstvi, rozmer}], pocet_spoju, souhrn [{id, label, value}], hmotnost_kg, hmotnost_uplna, hmotnost_chybi, cenovy_souhrn, rozmery_text}. Vzdy hluboka kopie."""
    lang = lang if lang in TEXTY else "cs"
    if rules_version is not None and str(rules_version) != RULES_VERSION:
        return {"ok": False, "chyba": "rules_changed", "rules_version": RULES_VERSION}
    out, jadro, r, soukr = _resolve_data(selection, lang)
    out = copy.deepcopy(out)
    base = {"ok": True, "selection": out["selection"], "hash": out["hash"], "kod": out["kod"], "rules_version": RULES_VERSION, "valid": out["valid"], "errors": [e["message"] for e in out["errors"]],
            "notices": [n["message"] for n in out["notices"]], "price": out["price"]}
    if r is None:
        return dict(base, bom=[], pocet_spoju=0, souhrn=[], hmotnost_kg=None, hmotnost_uplna=False, hmotnost_chybi=[], cenovy_souhrn=None, rozmery_text=None)
    kg, chybi = _hmotnost(r, soukr["cena_r"])
    ps = soukr["cena_r"]["price_summary"]
    souhrn_cen = {k: ps.get(k) for k in ("material_czk", "cut_czk", "joint_czk", "accessory_czk", "packaging_czk", "joint_count", "extra_work_czk")}
    souhrn_cen["weight_kg"] = kg
    return dict(base, bom=_neutralni_bom(r), pocet_spoju=r["pocet_spoju"], souhrn=_souhrn(out["selection"], jadro, lang), hmotnost_kg=kg, hmotnost_uplna=not chybi, hmotnost_chybi=chybi,
                cenovy_souhrn=(souhrn_cen if out["price"] else None), rozmery_text=_rozmery_text(r))


def glb_bytes(selection, razitka=False):
    """GLB (bytes) pro EFEKTIVNI vyber (razitka=True = model pro online nabidku: plne dily, bez textur)."""
    import oploceni_glb as OG
    _p, jadro, _u = _uprav(_zaklad(selection))
    return OG.model_pro_parametry(jadro, razitka=razitka, max_dilu=MAX_DILU_MODEL)[1]


# ---------------------------------------------------------------------------------------------------------------------
# token modelu a routy (volane z stul_shop.py pres konfigurator_registr)
# ---------------------------------------------------------------------------------------------------------------------
def _klic():
    return app.secret_key.encode() if isinstance(app.secret_key, str) else app.secret_key


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def podepis_model(jadro, ted=None):
    """Token pro /glb/<token>: "opl." + parametry jadra (jen cisla, bool a kratke kody) + platnost + HMAC (stateless)."""
    exp = int((ted or time.time()) + MODEL_PLATNOST_S)
    telo = _b64(json.dumps({k: jadro[k] for k in sorted(O.VYCHOZI)}, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(_klic(), f"{telo}.{exp}".encode(), hashlib.sha256).digest()[:18]
    return f"{PREFIX_TOKENU}{telo}.{exp}.{_b64(sig)}"


def over_model(token, ted=None):
    """(parametry jadra, None) nebo (None, 'podpis' | 'vyprsel')."""
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
        return (p, None) if isinstance(p, dict) and set(p) == set(O.VYCHOZI) else (None, "podpis")
    except Exception:                                       # noqa: BLE001
        return None, "podpis"


def zna_hash(h):
    return h in _STAV_PODLE_HASHE


def _nenalezeno():
    return jsonify({"error": "not_found"}), 404


def odpoved_schema(product_id):
    out = schema(_lang(request.args.get("lang")))
    out["systems"] = []
    out["env"] = None
    out["default_saved"] = False
    return jsonify(out)


def odpoved_resolve(body, skryt_cenu=False):
    if body.get("rules_version") and body.get("rules_version") != RULES_VERSION:
        return jsonify({"error": "rules_changed"}), 409
    lang = _lang(body.get("lang"))
    try:
        out = resolve(body.get("selection"), lang, skryt_cenu=skryt_cenu)
        if body.get("staff"):
            import stul_shop
            if stul_shop._je_staff():                              # jen zamestnanec s platnou session; verejny host tenhle blok nikdy nevidi
                out = dict(out)
                out["staff"] = staff_blok(body.get("selection"), lang)
        return jsonify(out)
    except Exception:                                               # noqa: BLE001 - verejny resolve nikdy nevraci vyjimku ani traceback
        app.logger.exception("oploceni_shop: resolve selhal")
        return jsonify({"error": "server_error"}), 500


def odpoved_model(h):
    p = _STAV_PODLE_HASHE.get(h)
    if p is None:
        return _nenalezeno()
    return jsonify({"model": {"stav": "hotovo", "url": "/api/shop/configurator/glb/" + podepis_model(p), "odhad_ms": 0}})


def odpoved_glb(token):
    p, chyba = over_model(token)
    if p is None:
        return (jsonify({"error": "expired" if chyba == "vyprsel" else "forbidden"}), 410 if chyba == "vyprsel" else 403)
    import oploceni_glb as OG
    import stul_glb
    try:
        h, data = OG.model_pro_parametry(p, razitka=False, max_dilu=MAX_DILU_MODEL)
    except O.OploceniChyba as e:
        return jsonify({"error": "too_large" if e.kod == "prilis_velky" else "invalid"}), (413 if e.kod == "prilis_velky" else 400)
    except Exception:                                               # noqa: BLE001
        app.logger.exception("oploceni_shop: stavba modelu selhala")
        return jsonify({"error": "server_error"}), 500
    data, kodovani = stul_glb.zakoduj_pro_klienta(h, data, request.headers.get("Accept-Encoding"))
    resp = Response(data, mimetype="model/gltf-binary")
    if kodovani:
        resp.headers["Content-Encoding"] = kodovani
    resp.headers["Vary"] = "Accept-Encoding"
    resp.headers["Cache-Control"] = "private, max-age=600"
    resp.headers["Content-Disposition"] = "inline"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp
