"""Verejne API konfiguratoru stolu pro e-shop / mini-shop (bot8, 2026-10-02) = SERVEROVA strana kontraktu z
docs/KONTRAKT_KONFIGURATOR_UI.md (bot16: webapp/js/product-configurator.js):

  GET  /api/shop/products/<id>/configurator   schema voleb (slidery rozmeru, prepinace prislusenstvi), `?lang=cs|en`
  POST /api/shop/configurator/resolve         {product_id, selection, rules_version, lang?} -> cena, platnost, stavy voleb, model
  GET  /api/shop/configurator/model/<hash>    stav modelu (hotovo hned - model se sklada za ~0,1 s)
  GET  /api/shop/configurator/glb/<token>     GLB poskladany na serveru (podepsany odkaz, platnost 15 min, bez loginu)

Vsechno je VEREJNE (bez loginu) - proto: (a) model neprichazi z katalogu ani ze sceny, ale jako jeden GLB s ploskymi uzly poskladany
tady (api/stul_glb.py), (b) odkaz na model je podepsany HMAC a kratce plati, (c) kazdy endpoint ma rate limit (429 + Retry-After),
(d) selection je jen mala sada cisel/prepinacu, server ji vzdy znovu normalizuje a nezna neco jineho nez rozmery a prepinace.

Produkt, ktery je konfigurovatelny, se urcuje v app_settings `configurator_products` = JSON {"<shop_product_id>": "stul_system30" | "stul_system35" | "stul_system40"}
(cte se pres kurzor, cache 60 s). Neni-li nastaveno, zadny produkt neni konfigurovatelny (404) - nic se nevystavi samo.
SYSTEM PROFILU (bot10, 2026-10-04): recept `stul_system30` = profil 30x30 (vychozi), `stul_system35` = profil 35x35 (od 2026-10-05), `stul_system40` = SuperLight 40x40; kazdy ma vlastni produktovou kartu. System je VLASTNOST PRODUKTU,
ne soucast vyberu zakaznika: vyber (rozmery, volby) je v obou systemech STEJNY a prenositelny (zakaznik muze tentyz stul zkusit v druhem systemu), server system bere z produktu
(`system_pro_produkt`) a predava ho jako parametr `system`; nese ho i podepsany token modelu. Co v druhem systemu nejde (dnes sikme vzpery ve 40), se odebere s duvodem v `notices`.

Ceny: bez DPH v Kc (stejna pravidla jako cena sestavy ve scene, api/configurator_price.py). Mena jina nez CZK = starost mini-shopu
(prepocet kurzem), tady se vraci `currency: "CZK"`.
"""
import base64
import hashlib
import hmac
import json
import copy
import math
import urllib.parse
import time
from collections import OrderedDict

from flask import Response, has_request_context, jsonify, request

from app import app, get_conn, _client_ip, _rate_limited, staff_required, current_user, require_permission, log_audit
import configurator_price
import jazyky                                                 # dalsi jazyky z dat (api/jazyky/<jazyk>.json, bot16 2026-10-07); cs / en / sk zustavaji v tomto souboru
import konfigurator_registr                                  # rozcestnik stul / dopravnik (bot5 2026-10-07): routy nize pro produkt s receptem dopravniku deleguji na api/dopravnik_shop.py
import miniweb_cena
import stul_api
import stul_glb
import stul_hpolice as HP                                    # horni police mezi zadnimi stojkami (Robert 2026-10-07)
import stul_konfigurator as S
import stul_ovladani_verejne
import stul_pohled                                            # vychozi uhel pohledu 3D v generatorech (bot10 2026-10-08): pole `view` schematu + PUT / DELETE /api/shop/configurator/view
import stul_vyrobni_list

RECEPT = "stul_system30"
RECEPT_40 = "stul_system40"                                   # druhy generator: profil SuperLight 40x40 (bot10, 2026-10-04)
RECEPT_35 = "stul_system35"                                   # treti generator: profil 35x35, drazka 8, spojky ze systemu 30 (bot10, 2026-10-05)
RECEPT_SSE = "stul_system41"                                  # ctvrty generator: ergonomicky stul SSE (podelniky 40x40 + nohy SSE; bot8, 2026-10-05; viz stul_sse.py, stul_shop_sse.py)
RECEPT_45 = "stul_system45"                                   # paty generator: hluboky stul (profil jako system 40, hloubka az 2500 mm, od 1500 mm stredni rada noh; bot10, 2026-10-07)
RECEPTY = {RECEPT: 30, RECEPT_35: 35, RECEPT_40: 40, RECEPT_SSE: 41, RECEPT_45: 45}          # recept -> system profilu (stul_konfigurator.SYSTEMY)


def _sse():
    """Verejne API SSE stolu (system 41): vlastni schema / normalizace / vypocet odpovedi; import az pri pouziti (modul importuje tenhle)."""
    import stul_shop_sse
    return stul_shop_sse
MODEL_PLATNOST_S = 15 * 60
LIMIT_RESOLVE = (120, 60)      # pozadavku / okno (s) na IP
LIMIT_GLB = (60, 60)
LIMIT_SCHEMA = (60, 60)
MIN_POLOHA_STREDNI_NOHY_PCT = 50

_PRODUKTY = {"t": 0.0, "map": {}}
_RESOLVE_CACHE = OrderedDict()
_STAV_PODLE_HASHE = OrderedDict()
CACHE_MAX = 64

# ---------------------------------------------------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------------------------------------------------
# DRZAK PET: na ktere noze (petleg) a ktere strane profilu (petface) visi; verejna id <-> parametry generatoru (pet_noha, pet_strana)
PET_NOHA_ID = {"fl": "PL", "fr": "PP", "rl": "ZL", "rr": "ZP", "fm": "FM", "rm": "RM"}
PET_STRANA_ID = {"right": "vpravo", "left": "vlevo", "front": "vpredu", "back": "vzadu"}
PET_NOHA_VEREJNE = {v: k for k, v in PET_NOHA_ID.items()}
PET_STRANA_VEREJNE = {v: k for k, v in PET_STRANA_ID.items()}

# STREDNI OPORA (Robert 2026-10-05): auto | legs (stredni nohy) | frame (vestaveny ram mezi podelniky); verejna id <-> parametr generatoru stredni_opora
MIDSUPPORT_ID = {"auto": "auto", "legs": "noha", "frame": "ram"}
MIDSUPPORT_VEREJNE = {v: k for k, v in MIDSUPPORT_ID.items()}

# DELKA PANELU (Robert 2026-10-07): verejne id volby = delka v mm jako text ("1190" | "1481" | "1671" | "1975"; S.PANEL_DELKY), parametr generatoru panely_delka (float)
PANELLEN_IDS = tuple(str(d) for d in S.PANEL_DELKY)


def _panellen(v, povolene=None):
    """Verejna volba delky panelu (text i cislo) -> parametr generatoru (mm); neznama nebo (pri `povolene`) nenabizena hodnota = vychozi (1190)."""
    try:
        d = int(round(float(v)))
    except (TypeError, ValueError, OverflowError):
        return float(S.PANEL_DELKA_VYCHOZI)
    return float(d) if (d in S.PANEL_TYPY and (povolene is None or d in povolene)) else float(S.PANEL_DELKA_VYCHOZI)


# DELKY PANELU V NABIDCE (Robert 2026-10-07; pravidlo 54 - kartu aktivuje jen Robert): VEREJNOST dostane vychozi 1190 a delky, jejichz karta je AKTIVNI a neni archivovana (nove karty #4972-4974 vznikly
# neaktivni s orientacnimi cenami, takze nove delky jsou venku, az je Robert potvrdi a aktivuje); ZAMESTNANEC (platna session) a kod mimo pozadavek (testy, skripty) vidi vsechny.
_DELKY_CACHE = {"t": 0.0, "set": frozenset({S.PANEL_DELKA_VYCHOZI})}
DELKY_TTL_S = 30.0


def delky_verejne():
    """Delky panelu v nabidce verejnosti (viz vyse); cache DELKY_TTL_S, chyba cteni DB = jen vychozi delka (stul nikdy nesmi spadnout kvuli volitelne delce)."""
    ted = time.time()
    if ted - _DELKY_CACHE["t"] > DELKY_TTL_S:
        mnozina = {S.PANEL_DELKA_VYCHOZI}
        try:
            ids = {int(pid.split("_", 1)[1]): d for d, pid in S.PANEL_TYPY.items() if d != S.PANEL_DELKA_VYCHOZI}
            cur = get_conn().cursor()
            cur.execute("SELECT id, active, is_archived FROM shop_products WHERE id IN (" + ",".join(["%s"] * len(ids)) + ")", tuple(ids))
            for r in cur.fetchall():
                if r["active"] and not r["is_archived"]:
                    mnozina.add(ids[r["id"]])
        except Exception as e:                                       # noqa: BLE001 - nikdy nesmi shodit verejny resolve
            app.logger.warning("stul_shop: nacteni aktivnich delek panelu selhalo (nabidnuta jen vychozi): %s", e)
        _DELKY_CACHE.update(t=ted, set=frozenset(mnozina))
    return _DELKY_CACHE["set"]


def delky_pro_pozadavek():
    """Delky panelu pro AKTUALNI pozadavek: zamestnanec a kod mimo pozadavek vsechny, verejnost jen delky s aktivni kartou (delky_verejne)."""
    if not has_request_context() or _je_staff():
        return frozenset(S.PANEL_DELKY)
    return delky_verejne()

# DELKA SVITIDLA LED (Robert 2026-10-07): verejne id volby = delka v mm jako text ("600" | "1200"; S.LED_DELKY), parametr generatoru led_delka (float)
LEDLEN_IDS = tuple(str(d) for d in S.LED_DELKY)


def _ledlen(v, povolene=None):
    """Verejna volba delky svitidla LED (text i cislo) -> parametr generatoru (mm); neznama nebo (pri `povolene`) nenabizena hodnota = vychozi (1200)."""
    try:
        d = int(round(float(v)))
    except (TypeError, ValueError, OverflowError):
        return float(S.LED_DELKA_VYCHOZI)
    return float(d) if (d in S.LED_TYPY and (povolene is None or d in povolene)) else float(S.LED_DELKA_VYCHOZI)


def _ledpos(v):
    """Verejna poloha svitidla LED (mm od osy stolu, + doprava; slot ledpos<k>) -> parametr generatoru led_z<k>; None / prazdne / neplatne = automaticka poloha. Na 0,1 mm (jako generator)."""
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return round(min(3000.0, max(-3000.0, x)), 1) if math.isfinite(x) else None


# DELKY LED V NABIDCE (pravidlo 54 - kartu aktivuje jen Robert): VEREJNOST dostane vychozi 1200 a delky, jejichz karta je AKTIVNI, neni archivovana, ma GLB a je viditelna ve scene (cena z katalogu dilu);
# ZAMESTNANEC (platna session) a kod mimo pozadavek (testy, skripty) vidi vsechny.
_LED_DELKY_CACHE = {"t": 0.0, "set": frozenset({S.LED_DELKA_VYCHOZI})}


def led_delky_verejne():
    """Delky svitidla LED v nabidce verejnosti (viz vyse); cache DELKY_TTL_S, chyba cteni DB = jen vychozi delka (stul nikdy nesmi spadnout kvuli volitelne delce)."""
    ted = time.time()
    if ted - _LED_DELKY_CACHE["t"] > DELKY_TTL_S:
        mnozina = {S.LED_DELKA_VYCHOZI}
        try:
            ids = {int(pid.split("_", 1)[1]): d for d, pid in S.LED_TYPY.items() if d != S.LED_DELKA_VYCHOZI}
            cur = get_conn().cursor()
            cur.execute("SELECT id, active, is_archived, glb_file, visible_in_scene FROM shop_products WHERE id IN (" + ",".join(["%s"] * len(ids)) + ")", tuple(ids))
            for r in cur.fetchall():
                if r["active"] and not r["is_archived"] and r["glb_file"] and r["visible_in_scene"]:
                    mnozina.add(ids[r["id"]])
        except Exception as e:                                       # noqa: BLE001 - nikdy nesmi shodit verejny resolve
            app.logger.warning("stul_shop: nacteni aktivnich delek LED selhalo (nabidnuta jen vychozi): %s", e)
        _LED_DELKY_CACHE.update(t=ted, set=frozenset(mnozina))
    return _LED_DELKY_CACHE["set"]


def led_delky_pro_pozadavek():
    """Delky svitidla LED pro AKTUALNI pozadavek: zamestnanec a kod mimo pozadavek vsechny, verejnost jen delky s aktivni kartou (led_delky_verejne)."""
    if not has_request_context() or _je_staff():
        return frozenset(S.LED_DELKY)
    return led_delky_verejne()


# KARTY HORNI POLICE V NABIDCE (Robert 2026-10-07; pravidlo 54 - kartu aktivuje jen Robert): VEREJNOST dostane jen desky, typy a dily, jejichz karta je AKTIVNI a neni archivovana (laminodeska 12 mm
# vznika jako neaktivni karta s orientacni cenou, takze je venku, az ji Robert potvrdi a aktivuje); ZAMESTNANEC (platna session) a kod mimo pozadavek (testy, skripty) vidi vsechno.
_KARTY_POLICE_CACHE = {"t": 0.0, "set": frozenset({"product_4933"})}


def karty_police_verejne():
    """Mnozina part_id karet horni police, ktere smi dostat verejnost (aktivni, neni archivovana); cache DELKY_TTL_S, chyba cteni DB = jen laminodeska 18 mm (stul nikdy nesmi spadnout kvuli volitelne polici)."""
    ted = time.time()
    if ted - _KARTY_POLICE_CACHE["t"] > DELKY_TTL_S:
        mnozina = {"product_4933"}
        try:
            ids = sorted({int(pid.split("_", 1)[1]) for pid in HP.vsechny_party()})
            cur = get_conn().cursor()
            cur.execute("SELECT id, active, is_archived FROM shop_products WHERE id IN (" + ",".join(["%s"] * len(ids)) + ")", tuple(ids))
            for r in cur.fetchall():
                if r["active"] and not r["is_archived"]:
                    mnozina.add(f"product_{r['id']}")
        except Exception as e:                                       # noqa: BLE001 - nikdy nesmi shodit verejny resolve
            app.logger.warning("stul_shop: nacteni aktivnich karet horni police selhalo (nabidnuta jen laminodeska 18 mm): %s", e)
        _KARTY_POLICE_CACHE.update(t=ted, set=frozenset(mnozina))
    return _KARTY_POLICE_CACHE["set"]


def nabidka_police(system, karty="pozadavek"):
    """(desky, typy) horni police v nabidce pro `system`: `karty` = "pozadavek" (zamestnanec / kod mimo pozadavek vsechno, verejnost jen karty z karty_police_verejne), nebo mnozina part_id (testy)."""
    if isinstance(karty, str):
        karty = None if (not has_request_context() or _je_staff()) else karty_police_verejne()
    return HP.nabidka(system, karty)


def _cele_nebo_none(v):
    """Vyska police do echa vyberu: None = automaticka, cele cislo jako int (640, ne 640.0), jinak desetinne."""
    return None if v is None else (int(v) if float(v).is_integer() else round(float(v), 1))


def _upshelf_typ(v, nab):
    """Verejna volba typu police -> typ generatoru; neznamy nebo nenabizeny typ = vychozi (rovna), nebo prvni nabizeny."""
    t = HP.TYP_ID.get(v) if isinstance(v, str) else None                                        # (vstup od klienta: seznam / slovnik nesmi spadnout na hash)
    return t if t in nab[1] else (HP.TYP_VYCHOZI if HP.TYP_VYCHOZI in nab[1] else nab[1][0])


def _upshelf_deska(v, system, typ, nab):
    """Verejna volba desky police -> id desky generatoru: neznama / pro typ a system nepouzitelna / nenabizena deska = prvni pouzitelna (ramova police bez desky: vychozi laminodeska 18 mm)."""
    pouz = [d for d in HP.nabidka_desek(system, typ) if d in nab[0]]
    if typ == "ram" or not pouz:
        return HP.DESKA_VYCHOZI
    return v if v in pouz else pouz[0]


# id slotu -> parametr generatoru (neprusvitne ID pro UI; stabilni)
SLIDERY = {"w": "sirka", "d": "hloubka", "h": "vyska", "ov": "presah", "arm": "led_rameno"}
PREPINACE = {"posts": "stojky", "wheels": "kolecka", "panels": "panely", "led": "led", "ledlight": "led_svetlo", "drawers": "suplik", "drawleft": "suplik_vlevo",
             "socket": "elektrozlab", "pet": "drzak_pet", "feet": "patky", "braces": "vzpery", "upshelf": "hpolice", "shelfboard": "police_deska"}
PREPINACE_NAVLEK = {"sleeve": "navlek"}                                          # navlek nohou (jekl 40x40x2): prepinac jen systemu s navlekem (S.NAVLEK_SYSTEMY); PREPINACE (systemy 30 a 40) zustava beze zmeny


def _prepinace(system):
    """Prepinace (slot -> parametr generatoru) systemu: PREPINACE + navlek nohou v systemech, ktere ho maji."""
    return {**PREPINACE, **PREPINACE_NAVLEK} if system in S.NAVLEK_SYSTEMY else PREPINACE
VYCHOZI_VYBER = {"w": int(S.VYCHOZI["sirka"]), "d": 800, "h": 840, "ov": 30, "arm": 560, "mid": 50, "boxpos": 0, "petleg": "fl", "petface": "right", "ledlight": True,
                 "panelcount": int(S.VYCHOZI["panely_pocet"]), "drawercount": int(S.VYCHOZI["suplik_pocet"]), "panelpos": 0, "panelside": 0, "panellen": str(S.PANEL_DELKA_VYCHOZI), "ledlen": str(S.LED_DELKA_VYCHOZI), "ledcount": 1, **{f"ledpos{k}": None for k in range(1, S.LED_MAX + 1)}, "midsupport": "auto", "posth": S.VYCHOZI["stojky_vyska"], "socketup": 0, "socketside": 0, "drawleft": False, "petpos": 0, **{f"sh{k}": None for k in range(1, S.MAX_POLIC + 1)},
                 "posts": True, "shelf": 1, "shelfboard": True, "wheels": True, "feet": False, "panels": True, "led": True, "drawers": True, "socket": True, "pet": True,
                 "braces": False, "bracelen": 300,
                 "upshelf": False, "upshelftype": "flat", "upshelfboard": "lam18", "upshelfpos": None, "upshelfdepth": int(HP.HLOUBKA_VYCHOZI), "upshelftilt": int(HP.SKLON_VYCHOZI)}      # horni police mezi zadnimi stojkami (pos None = automaticky)
VYCHOZI_VYBER_NAVLEK = {"sleeve": False, "sleevelen": 300}      # navlek nohou (jekl 40x40x2, jen system 35): klice vyberu, ktere ma jen system s navlekem (S.NAVLEK_SYSTEMY); VYCHOZI_VYBER (systemy 30 a 40) zustava beze zmeny
# vyrezy v pracovni desce (Robert): cut1..cut3 = zapnuto, cut<n>w/d = rozmer vyrezu po sirce/hloubce, cut<n>x = vzdalenost od PREDNIHO okraje desky,
# cut<n>z = vzdalenost od LEVEHO okraje desky (mm). Parametry generatoru: vyrez<n>, vyrez<n>_w/_d/_x/_z.
MAX_VYREZU = S.MAX_VYREZU
VYREZY = [(n, f"cut{n}", f"vyrez{n}", {"w": f"cut{n}w", "d": f"cut{n}d", "x": f"cut{n}x", "z": f"cut{n}z"}) for n in range(1, MAX_VYREZU + 1)]
for _n, _tg, _par, _sl in VYREZY:
    VYCHOZI_VYBER[_tg] = False
    VYCHOZI_VYBER[f"{_tg}shelf"] = False                      # police pod vyrezem (cut<n>shelf): parametr generatoru vyrez<n>_police
    for _sfx, _sid in _sl.items():
        VYCHOZI_VYBER[_sid] = int(S.VYCHOZI[f"{_par}_{_sfx}"])
# loziskove (kulickove) jednotky na pracovni desce (Robert): bearings = zapnuto, bearpitch = rozteč jednotek, bearedge = vzdalenost od okraje desky (mm);
# parametry generatoru loz, loz_rozteca, loz_okraj. Pocet jednotek z toho vyplyva (options.bearings.count). Okraj zacina na 30 mm, aby vychozi 100 lezelo
# na mrizce kroku 10 (generator by bral od 25 mm).
LOZ_OKRAJ_MIN = 30
VYCHOZI_VYBER.update({"bearings": False, "bearpitch": int(S.VYCHOZI["loz_rozteca"]), "bearedge": int(S.VYCHOZI["loz_okraj"])})


def vychozi_vyber(system=30):
    """Vychozi vyber pro system profilu: jako VYCHOZI_VYBER, jen vychozi poloha vyrezu od predni hrany podle systemu (S.SYSTEMY[...]["vyrez_x"]: zavesy police pod vyrezem jsou ve 40 sirsi)."""
    d = dict(VYCHOZI_VYBER)
    for n, tg, par, sl in VYREZY:
        d[sl["x"]] = int(S.SYSTEMY[system]["vyrez_x"])
    if system == S.SYSTEM_SSE:
        return _sse().vychozi_vyber(d)                                   # SSE: vlastni vychozi rozmery (2000 x 900 x 830), co SSE nema, je vypnute
    if system in S.NAVLEK_SYSTEMY:                       # system 35 ("ergonomicky balici stul", Robert 2026-10-05): vychozi koncovka nohou je NAVLEK (jekl 40x40x2, 300 mm), ne kolecka
        d.update(VYCHOZI_VYBER_NAVLEK)
        d["sleeve"], d["wheels"] = True, False
    return d


def _typ_sedi(zaklad, hodnota):
    """Ulozena hodnota vychoziho vyberu sedi typem na vestavenou (ano/ne jen ano/ne, cislo jen cislo, text jen text; vestavene null = automatika: null nebo cislo)."""
    if isinstance(zaklad, bool):
        return isinstance(hodnota, bool)
    if isinstance(zaklad, (int, float)):
        return isinstance(hodnota, (int, float)) and not isinstance(hodnota, bool)
    if isinstance(zaklad, str):
        return isinstance(hodnota, str)
    return hodnota is None or (isinstance(hodnota, (int, float)) and not isinstance(hodnota, bool))


def slij_vychozi(zaklad, ulozeny):
    """`default_selection` produktu: vestavene vychozi (`zaklad`, viz vychozi_vyber) s hodnotami z VYCHOZI KONFIGURACE ulozene adminem (stul_api.nacti_vychozi; tlacitko "Ulozit jako vychozi"
    na strance stolu). Preberou se jen klice, ktere schema zna, a hodnoty stejneho typu; co v ulozene konfiguraci chybi (slot pridany pozdeji), zustane vestavene."""
    out = dict(zaklad)
    for k, v in (ulozeny or {}).items():
        if k in out and _typ_sedi(zaklad[k], v):
            out[k] = v
    return out

TEXTY = {
    "cs": {
        "g_size": "Rozměry", "g_frame": "Konstrukce", "g_extras": "Příslušenství",
        "w": "Šířka desky", "d": "Hloubka desky", "h": "Výška pracovní desky", "ov": "Přesah desky vpředu přes čelní profil", "arm": "Délka ramene LED od zadních stojek",
        "mid": "Poloha střední nohy (od levé)", "boxpos": "Posun šuplíků po šířce", "drawleft": "Šuplíky na levé straně (jinak vpravo)", "petleg": "Držák PET lahve: na které noze", "petface": "Držák PET lahve: na které straně profilu",
        "petleg_fl": "Přední levá", "petleg_fr": "Přední pravá", "petleg_rl": "Zadní levá", "petleg_rr": "Zadní pravá", "petleg_fm": "Přední střední", "petleg_rm": "Zadní střední",
        "petface_right": "Vpravo", "petface_left": "Vlevo", "petface_front": "Vpředu", "petface_back": "Vzadu", "ledlight": "Svítidlo LED (bez něj zůstanou ramena a profily)", "petpos": "Výška držáku PET lahve na noze",
        "posts": "Zadní stojky (svislé profily nahoru)", "shelf": "Počet spodních polic", "wheels": "Kolečka", "feet": "Stavitelné patky (místo záslepek)", "panels": "Perforované panely na nářadí", "led": "LED osvětlení",
        "drawers": "Ocelové šuplíky", "socket": "Elektrožlab (zásuvky)", "pet": "Držák PET lahve",
        "braces": "Šikmé vzpěry ramen LED (podepření)", "bracelen": "Délka vzpěry",
        "help_braces": "Šikmé vzpěry pod rameny LED slouží jako stabilizace při zatížení: tyč zvolené délky se šikmými koncovkami na obou koncích, mezi zadní stojkou a ramenem. Délku vzpěry určuje délka tyče.",
        "help_mid": "Nad {prah} mm šířky přibývá přední i zadní střední noha. Posuň ji blíž k levé nebo pravé noze.",
        "help_box": "Šuplíkový box lze posunout po šířce stolu; zapnutá volba „Šuplíky na levé straně“ ho zrcadlově přehodí a posun se pak měří od levé nohy.",
        "help_petpos": "Držák PET lahve se posouvá po noze nahoru a dolů; meze dává délka nohy a okolní díly (např. šuplíky vlevo vyžadují držák níž).",
        "help_shelf": "Police se rozloží po výšce rovnoměrně, mezi nimi je vždy aspoň 100 mm volného místa. Počet je omezen výškou stolu a šuplíky.",
        "shelfboard": "Desky na spodních policích",
        "help_shelfboard": "Bez desek zůstane z každé spodní police jen rám z profilů (bez desky a bez podpěr pod ní). Platí pro všechny spodní police.",
        "drawercount": "Počet šuplíků v boxu",
        "help_drawercount": "Ocelový šuplíkový box má 1, 2 nebo 3 šuplíky (vnější výška 180 / 280 / 450 mm, visí pod pracovní deskou). Vyšší box potřebuje vyšší stůl nebo nižší polici; nevejde-li se, počet se sníží.",
        "bad_combo": "Tuhle kombinaci nelze vyrobit.",
        "panelcount": "Počet panelů", "panelpos": "Výška panelů (posun po zadních stojkách)", "panelside": "Panely do stran (posun mezi nohama)", "midsupport": "Střední opora u širokého stolu",
        "midsupport_auto": "Automaticky", "midsupport_legs": "Střední nohy", "midsupport_frame": "Vestavěný rám", "posth": "Výška zadních stojek nad deskou",
        "socketup": "Elektrožlab: posun nahoru", "socketside": "Elektrožlab: posun do stran",
        "help_panelcount": "Panel sedí mezi zadními stojkami, nad a pod ním je profil (mezera 1 mm). Další panely se přidávají po jednom kuse: vedle sebe, kde to šířka dovolí (mezi nimi je plná střední noha), jinak další řada nad.",
        "help_panelpos": "Panely s profily nad a pod nimi (a elektrožlab) se posouvají po zadních stojkách; dole leží spodní profil na zadní příčce rámu desky.",
        "help_panelside": "Mají-li panely mezi nohama mezeru, dají se posouvat do stran (spolu s elektrožlabem); od nohy vždy zůstane aspoň 1 mm. Kladná hodnota = doprava, 0 = uprostřed.",
        "help_midsupport": "U širokého stolu střední nohy, nebo vestavěný rám mezi podélníky (podélníky zůstanou celé; jen se spodní policí). Automaticky: nohy, rám jen když by se panel jinak nevešel.",
        "help_posth": "Zadní stojky lze zkracovat i natahovat; rameno LED jede s nimi. Panely potřebují stojky aspoň tak vysoké, aby se pod rameno LED vešly.",
        "help_socket": "Elektrožlab se vždy dotýká panelu nebo profilu; lze ho posouvat nahoru a dolů i do stran, meze dávají okolní díly.",
    },
    "en": {
        "g_size": "Dimensions", "g_frame": "Frame", "g_extras": "Accessories",
        "w": "Worktop width", "d": "Worktop depth", "h": "Worktop height", "ov": "Worktop overhang at the front", "arm": "LED arm length from the rear uprights",
        "mid": "Centre leg position (from left)", "boxpos": "Drawer unit position", "drawleft": "Drawers on the left side (otherwise right)", "petleg": "PET bottle holder: on which leg", "petface": "PET bottle holder: on which side of the profile",
        "petleg_fl": "Front left", "petleg_fr": "Front right", "petleg_rl": "Rear left", "petleg_rr": "Rear right", "petleg_fm": "Front centre", "petleg_rm": "Rear centre",
        "petface_right": "Right", "petface_left": "Left", "petface_front": "Front", "petface_back": "Back", "ledlight": "LED light fixture (without it the arms and profiles stay)", "petpos": "Height of the PET bottle holder on the leg",
        "posts": "Rear uprights (vertical profiles going up)", "shelf": "Number of lower shelves", "wheels": "Castors", "feet": "Adjustable feet (instead of end caps)", "panels": "Perforated tool panels", "led": "LED lighting",
        "drawers": "Steel drawers", "socket": "Power strip", "pet": "PET bottle holder",
        "braces": "Angled braces under the LED arms (support)", "bracelen": "Brace length",
        "help_braces": "Angled braces under the LED arms stabilise them under load: a bar of the chosen length with angled end fittings at both ends, between the rear upright and the arm. The brace length is the length of the bar.",
        "help_mid": "Above {prah} mm width a front and a rear centre leg are added. Move it closer to the left or right leg.",
        "help_box": "The drawer unit can be moved along the width of the table; \"Drawers on the left side\" mirrors it and the position is then measured from the left leg.",
        "help_petpos": "The PET bottle holder slides up and down the leg; the limits come from the leg length and the nearby parts (e.g. drawers on the left need the holder lower).",
        "help_shelf": "The shelves are spread evenly over the height, with at least 100 mm of free space between them. The number is limited by the table height and the drawers.",
        "shelfboard": "Boards on the lower shelves",
        "help_shelfboard": "Without the boards each lower shelf is just a frame of profiles (no board and no supports under it). It applies to all lower shelves.",
        "drawercount": "Number of drawers in the unit",
        "help_drawercount": "The steel drawer unit has 1, 2 or 3 drawers (outer height 180 / 280 / 450 mm, hanging under the worktop). A taller unit needs a taller table or a lower shelf; if it does not fit, the number is reduced.",
        "bad_combo": "This combination cannot be built.",
        "panelcount": "Number of panels", "panelpos": "Panel height (slide along the rear uprights)", "panelside": "Panels sideways (slide between the legs)", "midsupport": "Centre support on a wide table",
        "midsupport_auto": "Automatic", "midsupport_legs": "Centre legs", "midsupport_frame": "Built-in frame", "posth": "Height of the rear uprights above the worktop",
        "socketup": "Power strip: move up", "socketside": "Power strip: move sideways",
        "help_panelcount": "A panel sits between the rear uprights with a profile above and below it (1 mm gap). More panels are added one at a time: side by side where the width allows (a full centre leg stands between them), otherwise another row above.",
        "help_panelpos": "The panels with the profiles above and below them (and the power strip) slide along the rear uprights; at the bottom the lower profile rests on the rear rail of the worktop frame.",
        "help_panelside": "If the panels have a gap between the legs, they can be slid sideways (together with the power strip); at least 1 mm always stays between a panel and a leg. Positive = to the right, 0 = centred.",
        "help_midsupport": "On a wide table: centre legs, or a built-in frame between the long rails (the rails stay unbroken; needs a lower shelf). Automatic: legs; a frame only when a panel would not fit otherwise.",
        "help_posth": "The rear uprights can be shortened or extended; the LED arm moves with them. The panels need uprights tall enough to fit below the LED arm.",
        "help_socket": "The power strip always touches a panel or a profile; it can be moved up and down and sideways, the limits come from the surrounding parts.",
    },
}
for _lg, _t in (("cs", TEXTY["cs"]), ("en", TEXTY["en"])):
    for _k in range(1, S.MAX_POLIC + 1):                                  # VYSKA POLIC (Robert 2026-10-04): sh1 = odstup 1. (nejvyssi) police pod spodni hranou podelniku pracovni plochy, sh<k> = mezera mezi policemi
        _t[f"sh{_k}"] = (("Police 1 (nejvyšší): odstup pod pracovní plochou" if _k == 1 else f"Mezera mezi policí {_k - 1} a {_k}") if _lg == "cs"
                         else ("Shelf 1 (top): distance below the worktop" if _k == 1 else f"Gap between shelf {_k - 1} and {_k}"))
    _t["help_shelfh"] = ("Odstup se měří od spodní hrany podélníků, které podpírají pracovní plochu, k horní ploše desky nejvyšší police. Další police se nastavují mezerou mezi policemi "
                         "(od horní plochy desky po spodek rámu police nad ní). Dokud nic nenastavíš, jsou police rozložené rovnoměrně."
                         if _lg == "cs" else "The distance is measured from the lower edge of the rails supporting the worktop to the top surface of the highest shelf board. Further shelves are set by the gap "
                         "between shelves (from the top surface of the board to the underside of the shelf frame above). Until you set something, the shelves are spread evenly.")
    _t["g_cuts"] = "Výřezy v pracovní desce" if _lg == "cs" else "Cutouts in the worktop"
    _t["help_cuts"] = ("Výřez může mít libovolnou velikost a polohu. Od okraje desky zůstane aspoň 30 mm a mezi dvěma výřezy aspoň 30 mm."
                       if _lg == "cs" else "A cutout can have any size and position. At least 30 mm of the worktop stays at its edge and between two cutouts.")
    _t["g_bearings"] = "Ložiskové jednotky na desce" if _lg == "cs" else "Ball transfer units on the worktop"
    _t["bearings"] = "Ložiskové jednotky (kuličkové)" if _lg == "cs" else "Ball transfer units"
    _t["bearpitch"] = "Rozteč jednotek" if _lg == "cs" else "Spacing of the units"
    _t["bearedge"] = "Vzdálenost jednotek od okraje desky" if _lg == "cs" else "Distance of the units from the worktop edge"
    _t["help_bearings"] = ("Zadej rozteč jednotek a jejich vzdálenost od okraje desky – počet z toho vyplyne. V místě výřezu se jednotky vynechají."
                           if _lg == "cs" else "Enter the spacing of the units and their distance from the worktop edge – the number follows from that. Units are left out where there is a cutout.")
    for _n, _tg, _par, _sl in VYREZY:
        _t[f"{_tg}shelf"] = f"Police pod výřezem {_n}" if _lg == "cs" else f"Shelf under cutout {_n}"
        if _lg == "cs":
            _t[_tg], _t[_sl["w"]], _t[_sl["d"]] = f"Výřez {_n}", f"Šířka výřezu {_n} (podél stolu)", f"Hloubka výřezu {_n} (od předu dozadu)"
            _t[_sl["x"]], _t[_sl["z"]] = f"Vzdálenost výřezu {_n} od předního okraje", f"Vzdálenost výřezu {_n} od levého okraje"
        else:
            _t[_tg], _t[_sl["w"]], _t[_sl["d"]] = f"Cutout {_n}", f"Cutout {_n} width (along the table)", f"Cutout {_n} depth (front to back)"
            _t[_sl["x"]], _t[_sl["z"]] = f"Cutout {_n} distance from the front edge", f"Cutout {_n} distance from the left edge"
# Zakaznik NIKDY nevidi technicke hlasky generatoru (cisla dilu, souradnice, nazvy dilu) - jen vety podle slotu.
DUVODY = {
    "cs": {
        "panels": "Ani nejkratší perforovaný panel (1190 mm) se sem nevejde – potřebuje volné místo mezi zadními stojkami a dost vysoké stojky.",
        "socketup": "Elektrožlab se musí dotýkat panelu nebo profilu a vejít se na stůl – posuňte ho zpět (výška / do stran).",
        "socketside": "Elektrožlab se musí dotýkat panelu nebo profilu a vejít se na stůl – posuňte ho zpět (výška / do stran).",
        "led": "LED osvětlení (1,2 m) se na tuto šířku stolu nevejde – potřebuje šířku aspoň 1200 mm.",
        "drawers": "Šuplíky se při těchto rozměrech nevejdou (potřebují hloubku aspoň 620 mm, šířku aspoň 700 mm a dostatečnou výšku desky).",
        "socket": "Elektrožlab se montuje na perforovaný panel – bez panelů ho nelze zvolit.",
        "wheels": "Kolečka se při této výšce stolu nevejdou.",
        "feet": "Stavitelné patky jdou jen u stolu bez koleček a nevejdou se do příliš nízkého stolu.",
        "pet": "Držák PET lahve se při této výšce nevejde.",
        "shelf": "Spodní police se při této výšce nevejde.",
        "shelfboard": "Volba platí jen se spodní policí.",
        "posts": "Zadní stojky nelze vypnout, dokud jsou zapnuté panely, LED nebo elektrožlab.",
        "braces": "Šikmé vzpěry se při těchto rozměrech nevejdou – potřebují zadní stojky, LED osvětlení, volné místo před stojkami a dost dlouhé rameno LED.",
        None: "Tuhle kombinaci rozměrů nelze vyrobit.",
    },
    "en": {
        "panels": "Not even the shortest perforated panel (1190 mm) fits here – it needs free space between the rear uprights and tall enough uprights.",
        "socketup": "The power strip must touch a panel or a profile and fit on the table – move it back (height / sideways).",
        "socketside": "The power strip must touch a panel or a profile and fit on the table – move it back (height / sideways).",
        "led": "The LED light (1.2 m) does not fit this table width – at least 1200 mm is needed.",
        "drawers": "The drawers do not fit these dimensions (they need a depth of at least 620 mm, a width of at least 700 mm and enough worktop height).",
        "socket": "The power strip is mounted on the perforated panel – it cannot be chosen without panels.",
        "wheels": "The castors do not fit this table height.",
        "feet": "Adjustable feet only fit a table without castors and not a very low one.",
        "pet": "The PET bottle holder does not fit this table height.",
        "shelf": "The lower shelf does not fit this table height.",
        "shelfboard": "This option only applies together with a lower shelf.",
        "posts": "The rear uprights cannot be removed while the panels, LED or power strip are on.",
        "braces": "The angled braces do not fit these dimensions – they need the rear uprights, the LED light, free space in front of the uprights and a long enough LED arm.",
        None: "This combination cannot be built.",
    },
}
for _lg, _txt in (("cs", "Výřezy se překrývají nebo jsou blíž než 30 mm od sebe – posuň je, zmenši nebo jeden z nich odeber."),
                  ("en", "The cutouts overlap or are closer than 30 mm to each other – move or shrink them, or remove one of them.")):
    for _n, _tg, _par, _sl in VYREZY:
        DUVODY[_lg][_tg] = _txt
for _lg, _txt_pol, _txt_bez, _txt_loz in (
        ("cs", "Police pod výřezem se při těchto rozměrech nebo poloze nevejde – narazila by na nohu, šuplíky nebo jiný díl, případně je stůl příliš nízký. Posuň výřez, zmenši ho, nebo polici odeber.",
         "Nejdřív zapni výřez – police se montuje přímo pod něj.",
         "Příliš mnoho ložiskových jednotek (nejvýše 500 ks) – zvětši rozteč nebo vzdálenost od okraje."),
        ("en", "The shelf under the cutout does not fit these dimensions or this position – it would hit a leg, the drawers or another part, or the table is too low. Move or shrink the cutout, or remove the shelf.",
         "Switch the cutout on first – the shelf is mounted right under it.",
         "Too many ball transfer units (at most 500) – increase the spacing or the distance from the edge.")):
    for _n, _tg, _par, _sl in VYREZY:
        DUVODY[_lg][f"{_tg}shelf"] = _txt_pol
        DUVODY[_lg][f"{_tg}shelfoff"] = _txt_bez                # duvod zakazu zapnuti police, kdyz je vyrez vypnuty
    DUVODY[_lg]["bearpitch"] = _txt_loz
    DUVODY[_lg]["bearings"] = _txt_loz
PET_BEZ_STREDNI = {"cs": "Střední nohy má až širší stůl.", "en": "Centre legs only exist on a wider table.", "sk": "Stredné nohy má až širší stôl."}
PET_NOHA_NENI = {"cs": "Držák PET lahve nemůže viset na střední noze – tenhle stůl ji nemá. Vyber jinou nohu.", "en": "The PET bottle holder cannot hang on a centre leg – this table has none. Pick another leg.",
                 "sk": "Držiak na PET fľašu nemôže visieť na strednej nohe – tento stôl ju nemá. Vyberte inú nohu."}
KOLIZE_PET = {"cs": "Držák PET lahve na zvoleném místě naráží do jiného dílu (např. šuplíků) – zvol jinou nohu nebo stranu profilu, posuň ho výš či níž, nebo ho odeber.",
              "en": "The PET bottle holder collides with another part (e.g. the drawers) at the chosen place – pick another leg or side of the profile, move it up or down, or remove it.",
              "sk": "Držiak na PET fľašu na zvolenom mieste naráža do iného dielu (napr. zásuviek) – zvoľte inú nohu alebo stranu profilu, posuňte ho vyššie či nižšie, alebo ho odoberte."}
POTREBUJE_STOJKY = {"cs": "Potřebuje zadní stojky – nejdřív je zapni.", "en": "Needs the rear uprights – switch them on first."}
VZPERY_NENI = {"cs": "Šikmé vzpěry ramen LED zatím nejsou pro tento systém profilu k dispozici.", "en": "Angled LED arm braces are not available for this profile system yet.",
               "sk": "Šikmé vzpery ramien LED zatiaľ nie sú pre tento systém profilu k dispozícii."}
SUPLIK_PRAHY = {"cs": "Šuplíky se při těchto rozměrech nevejdou (potřebují hloubku aspoň {d} mm, šířku aspoň {w} mm a dostatečnou výšku desky).",
                "en": "The drawers do not fit these dimensions (they need a depth of at least {d} mm, a width of at least {w} mm and enough worktop height).",
                "sk": "Zásuvky sa pri týchto rozmeroch nezmestia (potrebujú hĺbku aspoň {d} mm, šírku aspoň {w} mm a dostatočnú výšku dosky)."}
_PRAHY_SUPLIK = {}                                           # system -> (nejmensi hloubka, nejmensi sirka), pri ktere zustanou supliky zapnute (zjisteno generatorem, drzi se v pameti)


def _prahy_suplik(system):
    """(hloubka, sirka) nejmensiho stolu systemu `system`, na kterem zustanou supliky zapnute (ostatni volby vychozi): pocita generator (profil 40 ma jina cisla nez 30)."""
    if system not in _PRAHY_SUPLIK:
        def zustane(**kw):
            return bool(S.sestav_stul(system=system, **kw)["parametry"]["suplik"])
        rz_h = S._rozsahy(system)["hloubka"]
        d = next((v for v in range(int(rz_h[0]), int(rz_h[1]) + 1, 10) if zustane(hloubka=v)), int(rz_h[1]))
        w = next((v for v in range(int(S.ROZSAH["sirka"][0]), int(S.ROZSAH["sirka"][1]) + 1, 10) if zustane(sirka=v)), int(S.ROZSAH["sirka"][1]))
        _PRAHY_SUPLIK[system] = (d, w)
    return _PRAHY_SUPLIK[system]


PANEL_NEVEJDE = {"cs": "Ani nejkratší perforovaný panel ({l} mm) se sem nevejde – mezi zadní stojky potřebuje stůl široký aspoň {w} mm a zadní stojky aspoň {h} mm nad deskou.",
                 "en": "Not even the shortest perforated panel ({l} mm) fits here – between the rear uprights it needs a table at least {w} mm wide and rear uprights at least {h} mm above the worktop.",
                 "sk": "Ani najkratší perforovaný panel ({l} mm) sa sem nezmestí – medzi zadné stojky potrebuje stôl široký aspoň {w} mm a zadné stojky aspoň {h} mm nad doskou."}
PANEL_NEVEJDE_NOHY = {"cs": "Ani nejkratší perforovaný panel ({l} mm) se sem nevejde – střední nohy dělí zadní stranu na dva úseky a do žádného se panel nevejde (úsek musí mít aspoň {u} mm, tedy stůl se středními nohami aspoň {w} mm). "
                            "Zvolte vestavěný rám místo středních noh (potřebuje spodní polici) nebo panel odeberte; zadní stojky musí být aspoň {h} mm nad deskou.",
                      "en": "Not even the shortest perforated panel ({l} mm) fits here – the centre legs split the rear side into two sections and the panel fits into neither (a section needs at least {u} mm, i.e. a table with centre legs at least {w} mm wide). "
                            "Choose the built-in frame instead of the centre legs (it needs a lower shelf) or remove the panel; the rear uprights must be at least {h} mm above the worktop.",
                      "sk": "Ani najkratší perforovaný panel ({l} mm) sa sem nezmestí – stredné nohy delia zadnú stranu na dva úseky a do žiadneho sa panel nezmestí (úsek musí mať aspoň {u} mm, teda stôl so strednými nohami aspoň {w} mm). "
                            "Zvoľte vstavaný rám namiesto stredných nôh (potrebuje spodnú policu) alebo panel odstráňte; zadné stojky musia byť aspoň {h} mm nad doskou."}
MIDSUPPORT_RAM_AUTO = {"cs": "Střední nohu nahradil vestavěný rám, aby se vešel panel.", "en": "A built-in frame replaces the centre leg so that the panel fits.",
                       "sk": "Strednú nohu nahradil vstavaný rám, aby sa zmestil panel."}
MIDSUPPORT_RAM_POLICE = {"cs": "Vestavěný rám potřebuje spodní polici.", "en": "The built-in frame needs a lower shelf.", "sk": "Vstavaný rám potrebuje spodnú policu."}
SUPLIKY_OREZANO = {"cs": "Počet šuplíků snížen na {n} – box s víc šuplíky se sem nevejde (vyšší stůl nebo nižší police).",
                   "en": "Number of drawers reduced to {n} – a unit with more drawers will not fit here (a taller table or a lower shelf).",
                   "sk": "Počet zásuviek znížený na {n} – box s viac zásuvkami sa sem nezmestí (vyšší stôl alebo nižšia polica)."}
LEDPOCET_OREZANO = {"cs": "Počet svítidel LED snížen na {n} – víc se jich sem nevejde vedle sebe (užší stůl nebo delší svítidla).",
                    "en": "Number of LED lights reduced to {n} – more will not fit side by side (a narrower table or longer lights).",
                    "sk": "Počet svietidiel LED znížený na {n} – viac sa ich sem nezmestí vedľa seba (užší stôl alebo dlhšie svietidlá)."}
PANELY_OREZANO = {"cs": "Počet panelů snížen na {n} – víc se sem nevejde (širší stůl, vyšší stojky nebo vestavěný rám).", "en": "Number of panels reduced to {n} – more will not fit (a wider table, taller uprights or a built-in frame).",
                  "sk": "Počet panelov znížený na {n} – viac sa sem nezmestí (širší stôl, vyššie stojky alebo vstavaný rám)."}


# DELKA PANELU (Robert 2026-10-07: dalsi velikosti perforovanych panelu 1481 / 1671 / 1975 mm vedle 1190): vsechny panely stolu jsou stejne dlouhe, delsi potrebuje sirsi stul
TEXTY["cs"].update({"panellen": "Délka panelu", "panellen_1190": "1190 mm", "panellen_1481": "1481 mm", "panellen_1671": "1671 mm", "panellen_1975": "1975 mm",
                    "help_panellen": "Perforované panely jsou v několika délkách; všechny panely stolu mají stejnou délku. Delší panel potřebuje širší stůl – délka, která se nevejde, je v nabídce zašedlá, "
                                     "a když se stůl zúží, délka se sama sníží na nejdelší, která se vejde."})
TEXTY["en"].update({"panellen": "Panel length", "panellen_1190": "1190 mm", "panellen_1481": "1481 mm", "panellen_1671": "1671 mm", "panellen_1975": "1975 mm",
                    "help_panellen": "The perforated panels come in several lengths; all panels of a table have the same length. A longer panel needs a wider table – a length that does not fit is greyed out, "
                                     "and when the table is made narrower the length is reduced to the longest one that fits."})
PANELY_ZKRACENO = {"cs": "Délka panelů snížena na {l} mm – delší se sem nevejde (širší stůl, vyšší stojky nebo vestavěný rám).",
                   "en": "Panel length reduced to {l} mm – a longer one does not fit here (a wider table, taller uprights or the built-in frame).",
                   "sk": "Dĺžka panelov znížená na {l} mm – dlhší sa sem nezmestí (širší stôl, vyššie stojky alebo vstavaný rám)."}
PANELLEN_NEVEJDE = {"cs": "Panel {l} mm se sem nevejde – mezi zadní stojky potřebuje stůl široký aspoň {w} mm.",
                    "en": "A {l} mm panel does not fit here – between the rear uprights it needs a table at least {w} mm wide.",
                    "sk": "Panel {l} mm sa sem nezmestí – medzi zadné stojky potrebuje stôl široký aspoň {w} mm."}
PANELLEN_NEVEJDE_NOHY = {"cs": "Panel {l} mm se sem nevejde – střední nohy dělí zadní stranu na dva úseky; potřebuje vestavěný rám místo středních noh (jen se spodní policí) a stůl široký aspoň {w} mm.",
                         "en": "A {l} mm panel does not fit here – the centre legs split the rear side into two sections; it needs the built-in frame instead of the centre legs (only with a lower shelf) and a table at least {w} mm wide.",
                         "sk": "Panel {l} mm sa sem nezmestí – stredné nohy delia zadnú stranu na dva úseky; potrebuje vstavaný rám namiesto stredných nôh (len so spodnou policou) a stôl široký aspoň {w} mm."}
PANELLEN_NEVEJDE_STOJKY = {"cs": "Panel {l} mm se sem nevejde – zadní stojky musí být aspoň {h} mm nad deskou.",
                           "en": "A {l} mm panel does not fit here – the rear uprights must be at least {h} mm above the worktop.",
                           "sk": "Panel {l} mm sa sem nezmestí – zadné stojky musia byť aspoň {h} mm nad doskou."}
NENI_V_NABIDCE = {"cs": "Tahle délka panelu teď není v nabídce.", "en": "This panel length is not available at the moment.", "sk": "Táto dĺžka panela teraz nie je v ponuke."}


def _led_kratsi(p, led_delky):
    """Nejdelsi KRATSI delka svitidla LED (z nabizenych `led_delky`), pri ktere se LED na tomto stole vejde (jinak None): nabidka u zakazaneho prepinace LED misto roztazeni stolu."""
    for d in sorted((x for x in led_delky if x < int(round(p["led_delka"]))), reverse=True):
        try:
            if S.sestav_stul(**{**p, "led": True, "led_delka": float(d)})["parametry"]["led"]:
                return d
        except S.StulChyba:
            continue
    return None


def _duvod_delky(lang, p, typ):
    """Proc se panel dane delky (`typ` z panely_info.typy) nevejde: nevejde se na vysku = nejnizsi zadni stojky; u uzsiho stolu nejmensi sirka, u stolu nad prahem stredni nohy (nohy deli zadni stranu)
    vestaveny ram + sirka."""
    if typ.get("vejde_sirka", True) and not typ.get("vejde_vyska", True):
        return PANELLEN_NEVEJDE_STOJKY[lang].format(l=typ["delka"], h=typ["min_stojky"])
    if p["sirka"] > S.prah_sirky(p["system"]):
        return PANELLEN_NEVEJDE_NOHY[lang].format(l=typ["delka"], w=typ["min_sirka"])
    return PANELLEN_NEVEJDE[lang].format(l=typ["delka"], w=typ["min_sirka"])


def _duvod_slotu(lang, slot, system=30, sirka=None):
    """Verejny duvod pro slot; system 30 = beze zmeny (DUVODY), system 40: vzpery nejsou, cisla u supliku z generatoru. Panely: nejmensi sirka a vyska stojek podle profilu systemu; u stolu nad prahem
    stredni nohy (sirka > S.prah_sirky(system)) dela kratky usek mezi nohami to, ze se panel nevejde."""
    if slot == "panels":
        lim = S.panel_limity(system)
        if sirka is not None and sirka > S.prah_sirky(system):
            return PANEL_NEVEJDE_NOHY[lang].format(l=S.PANEL_DELKY[0], u=lim["usek"], w=lim["min_sirka_nohy"], h=lim["min_stojky"])
        return PANEL_NEVEJDE[lang].format(l=S.PANEL_DELKY[0], w=lim["min_sirka"], h=lim["min_stojky"])
    if system != 30:
        if slot == "braces" and not S.SYSTEMY[system]["vzpery"]:
            return VZPERY_NENI[lang]
        if slot == "drawers":
            d, w = _prahy_suplik(system)
            return SUPLIK_PRAHY[lang].format(d=d, w=w)
    return DUVODY[lang].get(slot) or DUVODY[lang][None]
# dily -> slot, ke kteremu chybovou hlasku priradit
DIL_NA_SLOT = {**{pid_: "panels" for pid_ in S.PANEL_PARTY}, **{pid_: "led" for pid_ in S.LED_PARTY}, **{pid_: "drawers" for pid_ in S.SUPLIK_PARTY_VSE}, "product_4932": "socket",
               "product_4928": "pet", "product_4916": "wheels", "product_3251": "feet", "product_3254": "braces", "product_3220": "braces",
               S.NAVLEK_PART: "sleeve", S.NAVLEK_ZASLEPKA: "sleeve"}


def _mnozne(n, tvary):
    """Ceske/slovenske skloňovani podle poctu: tvary = (1, 2-4, 5+)."""
    return tvary[0] if n == 1 else (tvary[1] if 2 <= n <= 4 else tvary[2])


def text_podpery(lang, inf):
    """Text informace `police_podpery` (stul_konfigurator `info`): pri hloubce nad 900 mm se deska spodni police zkrati o `kraceni_mm` z kazde strany a pod ni pribudou podperne
    profily (`podpery` ks na polici; 0 = zadne nejsou potreba, rozpony desky podpira stredni noha / jsou kratke)."""
    k, n, u, h = int(inf["kraceni_mm"]), int(inf["podpery"]), int(inf["urovni"]), int(inf.get("hloubka_mm", 900))
    if lang not in jazyky.VESTAVENE:                             # dalsi jazyk: sablony ze sady jazyka (jazyky.info); bez sablony anglicky
        r = jazyky.info(lang, "podpery", h=h, k=k, n=n, u=u)
        if r is not None:
            return r
        lang = "en"
    if lang == "en":
        z = f"Above {h} mm depth the lower shelf board is shortened by {k} mm on each side (clearance for the vertical profiles of the side frames)"
        if n:
            return z + f" and {n} supporting profile{'s' if n > 1 else ''} {'is' if n == 1 else 'are'} added under {'it' if u == 1 else 'each shelf'}."
        return z + "; no supporting profiles are needed under it (the spans are short or the middle leg supports it)."
    if lang == "sk":
        z = f"Pri hĺbke nad {h} mm sa doska spodnej police skráti o {k} mm z každej strany (kvôli zvislým profilom bočníc)"
        if n:
            return z + f" a pod {'ňu' if u == 1 else 'každú policu'} pribudn{'e' if n == 1 else 'ú'} {n} {_mnozne(n, ('podperný profil', 'podperné profily', 'podperných profilov'))}."
        return z + "; podperné profily pod ňu nie sú potrebné (rozpony sú krátke alebo ju podopiera stredná noha)."
    z = f"Při hloubce nad {h} mm se deska spodní police zkrátí o {k} mm z každé strany (kvůli svislým profilům bočnic)"
    if n:
        return z + f" a pod {'ni' if u == 1 else 'každou polici'} přibyde {n} {_mnozne(n, ('podpěrný profil', 'podpěrné profily', 'podpěrných profilů'))}."
    return z + "; podpěrné profily pod ni nejsou potřeba (rozpony jsou krátké, nebo ji podpírá střední noha)."


def text_podpery_desky(lang, inf):
    """Text informace `deska_podpery` (stul_konfigurator `info`): pri hloubce nad 900 mm pribudou pod pracovni desku podperne profily (`podpery` ks; stejna mista jako pod policí,
    pricky supliku, kdyz jsou, desku podpiraji samy). Vola se jen pro podpery > 0."""
    n, sup, h = int(inf["podpery"]), bool(inf.get("suplik")), int(inf.get("hloubka_mm", 900))
    if lang not in jazyky.VESTAVENE:
        r = jazyky.info(lang, "podpery_desky", h=h, n=n, sup=sup)
        if r is not None:
            return r
        lang = "en"
    if lang == "en":
        return (f"Above {h} mm depth {n} supporting profile{'s' if n > 1 else ''} {'is' if n == 1 else 'are'} added under the work surface"
                + (" (the drawer rails support the surface too)." if sup else "."))
    if lang == "sk":
        return (f"Pri hĺbke nad {h} mm pod pracovnú dosku pribudn{'e' if n == 1 else 'ú'} {n} {_mnozne(n, ('podperný profil', 'podperné profily', 'podperných profilov'))}"
                + (" (dosku podopierajú aj priečky zásuviek)." if sup else "."))
    return (f"Při hloubce nad {h} mm přibyde pod pracovní desku {n} {_mnozne(n, ('podpěrný profil', 'podpěrné profily', 'podpěrných profilů'))}"
            + (" (desku podpírají i příčky šuplíků)." if sup else "."))


def text_stredni_rada(lang, inf):
    """Text informace `stredni_rada_noh` (stul_konfigurator `info`, system 45): nad hloubkou `hloubka_mm` pribyva uprostred hloubky na kazde strane stredni noha a pod podperami desky (a policí) pricka pres sirku."""
    h = int(inf.get("hloubka_mm", 1500))
    if lang not in jazyky.VESTAVENE:
        r = jazyky.info(lang, "stredni_rada", h=h)
        if r is not None:
            return r
        lang = "en"
    if lang == "en":
        return f"Above {h} mm depth a middle leg is added in the middle of the depth on each side, with a cross rail between the two legs under the supports of the work surface (and of each shelf)."
    if lang == "sk":
        return f"Pri hĺbke nad {h} mm pribudne v strede hĺbky na každej strane stredná noha a pod podperami pracovnej dosky (a každej police) priečka cez šírku medzi obe nohy."
    return f"Při hloubce nad {h} mm přibude uprostřed hloubky na každé straně střední noha a pod podpěrami pracovní desky (i každé police) příčka přes šířku mezi obě nohy."


DESKA_MIMO_TABULI = {"cs": "Deska se nevejde do standardního formátu desky ({t1} × {t2} mm) – zmenšete rozměr stolu, nebo ho nechte přes střední nohu rozdělit na dvě desky.",
                     "en": "The worktop does not fit the standard board size ({t1} × {t2} mm) – reduce the table size or have it split into two boards at the centre leg.",
                     "sk": "Doska sa nezmestí do štandardného formátu dosky ({t1} × {t2} mm) – zmenšite rozmer stola, alebo ho nechajte rozdeliť cez strednú nohu na dve dosky."}


def text_desky_deleny(lang, rezim, mezera_mm, tabule):
    """Informace u stolu nad prahem sirky (stredni opora): pracovni deska i police se u stredni nohy / vestaveneho ramu DELI na dve desky, kazda se vejde do tabule laminodesky (Robert 2026-10-05);
    u vestaveneho ramu jsou spodni police o `mezera_mm` kratsi (svisly profil ramu prochazi rovinou police)."""
    t1, t2 = int(round(tabule[0])), int(round(tabule[1]))
    ram = rezim == "ram"
    if lang not in jazyky.VESTAVENE:
        r = jazyky.info(lang, "desky_deleny", t1=t1, t2=t2, mezera=int(mezera_mm), ram=ram)
        if r is not None:
            return r
        lang = "en"
    if lang == "en":
        return (f"The worktop and the shelves are split into two boards at the {'built-in frame' if ram else 'centre leg'} – each fits the standard board size ({t1} × {t2} mm)."
                + (f" The lower shelves are {int(mezera_mm)} mm shorter there so that the frame profile can pass through." if ram else ""))
    if lang == "sk":
        return (f"Pracovná doska a police sa pri {'vstavanom ráme' if ram else 'strednej nohe'} delia na dve dosky – každá sa zmestí do štandardného formátu dosky ({t1} × {t2} mm)."
                + (f" Spodné police sú tam o {int(mezera_mm)} mm kratšie, aby cez ne mohol prejsť profil rámu." if ram else ""))
    return (f"Pracovní deska a police se u {'vestavěného rámu' if ram else 'střední nohy'} dělí na dvě desky – každá se vejde do standardního formátu desky ({t1} × {t2} mm)."
            + (f" Spodní police jsou tam o {int(mezera_mm)} mm kratší, aby jimi mohl projít profil rámu." if ram else ""))


def _lang(v):
    v = (v or "").lower()[:2]
    if v in TEXTY:
        return v
    al = (request.headers.get("Accept-Language") or "").lower()[:2]
    return al if al in TEXTY else "cs"


def _zavisi_na():
    """slot -> seznam nadrazenych slotu (toggle), ktere musi byt VSECHNY zapnute, jinak slot neexistuje (UI ho neukazuje ani ve shrnuti, server jeho hodnotu ignoruje).
    Robert: volba bez nadrazene zapnute volby neexistuje (vyrezy, loziska, vzpery...)."""
    z = {"boxpos": ["drawers"], "drawleft": ["drawers"], "drawercount": ["drawers"], "ledlight": ["posts", "led"], "ledlen": ["posts", "led", "ledlight"], "petpos": ["pet"], "petleg": ["pet"], "petface": ["pet"], "panelcount": ["panels"], "panellen": ["panels"], "panelpos": ["panels"], "panelside": ["panels"], "posth": ["posts"], "socketup": ["socket"], "socketside": ["socket"], "panels": ["posts"], "led": ["posts"], "socket": ["panels"], "arm": ["led"], "braces": ["posts", "led"], "bracelen": ["braces"],
         "bearpitch": ["bearings"], "bearedge": ["bearings"]}
    z.update({k_: ["posts", "led", "ledlight"] for k_ in ("ledcount",) + tuple(f"ledpos{j}" for j in range(1, S.LED_MAX + 1))})          # pocet a poloha svitidel LED: jen se svitidlem (Robert 2026-10-08)
    z["sleevelen"] = ["sleeve"]                                      # delka navleku existuje jen se zapnutym navlekem
    z.update({k_: ["posts", "upshelf"] for k_ in ("upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt")})        # horni police: volby existuji jen se zapnutou policí (a stojkami)
    for n, tg, par, sl in VYREZY:
        for k in (sl["w"], sl["d"], sl["x"], sl["z"], f"{tg}shelf"):
            z[k] = [tg]
        if n > 1:
            z[tg] = [VYREZY[n - 2][1]]                              # dalsi vyrez jen kdyz je zapnuty predchozi
    return z


def _schema_zaklad(lang="cs", system=30):
    t = TEXTY[lang]
    pm = int(S.SYSTEMY[system]["profil_mm"])
    def slider(id_, group, mn, mx, step, unit, help_=None):
        return {"id": id_, "group": group, "label": t[id_], "help": help_, "type": "slider",
                "slider": {"min": mn, "max": mx, "step": step, "unit": unit}}
    def select(id_, group, ids, help_=None):
        return {"id": id_, "group": group, "label": t[id_], "help": help_, "type": "select", "options": [{"id": o, "label": t[f"{id_}_{o}"]} for o in ids]}

    def toggle(id_, group):
        return {"id": id_, "group": group, "label": t[id_], "help": None, "type": "toggle", "options": [{"id": "on", "label": t[id_]}]}
    return {
        "rules_version": stul_glb.RULES_VERSION,
        "profile": f"{pm}x{pm}", "profile_mm": pm,                     # hlavni profil stolu podle systemu (30x30 / 40x40): pro automaticke parovani animace "Pripni cokoli" (bot10, 2026-10-04)
        "system": system,                                              # system profilu produktu (30 | 40); vyber zakaznika je v obou systemech stejny
        "groups": [{"id": g, "label": t[g]} for g in ("g_size", "g_frame", "g_extras", "g_cuts", "g_bearings")],
        "slots": [
            slider("w", "g_size", S.ROZSAH["sirka"][0], S.ROZSAH["sirka"][1], 10, "mm"),
            slider("d", "g_size", S._rozsahy(system)["hloubka"][0], S._rozsahy(system)["hloubka"][1], 10, "mm"),
            slider("h", "g_size", S.ROZSAH["vyska"][0], S.ROZSAH["vyska"][1], 10, "mm"),
            slider("ov", "g_size", S.ROZSAH["presah"][0], S.ROZSAH["presah"][1], 10, "mm"),
            slider("mid", "g_frame", 5, 95, 1, "%", t["help_mid"]),
            select("midsupport", "g_frame", ("auto", "legs", "frame")),
            toggle("posts", "g_frame"), slider("posth", "g_frame", S.ROZSAH["stojky_vyska"][0], S.ROZSAH["stojky_vyska"][1], 10, "mm", t["help_posth"]),
            slider("shelf", "g_frame", 0, S.MAX_POLIC, 1, "ks", t["help_shelf"]),
            {**toggle("shelfboard", "g_frame"), "help": t["help_shelfboard"]},
            *[slider(f"sh{k}", "g_frame", 100, 1200, 10, "mm", t["help_shelfh"] if k == 1 else None) for k in range(1, S.MAX_POLIC + 1)],
            toggle("wheels", "g_frame"), toggle("feet", "g_frame"),
            toggle("sleeve", "g_frame"), slider("sleevelen", "g_frame", int(S.ROZSAH["navlek_delka"][0]), int(S.ROZSAH["navlek_delka"][1]), int(S.NAVLEK_KROK), "mm", t["help_sleeve"]),
            toggle("drawers", "g_extras"), slider("drawercount", "g_extras", S.SUPLIK_POCTY[0], S.SUPLIK_POCTY[-1], 1, "ks", t["help_drawercount"]), toggle("drawleft", "g_extras"),
            slider("boxpos", "g_extras", -2500, 80, 10, "mm", t["help_box"]),
            toggle("panels", "g_extras"), slider("panelcount", "g_extras", 1, S.PANELY_MAX, 1, "ks", t["help_panelcount"]), select("panellen", "g_extras", PANELLEN_IDS, t["help_panellen"]), slider("panelpos", "g_extras", 0, 600, 10, "mm", t["help_panelpos"]), slider("panelside", "g_extras", -1000, 1000, 1, "mm", t["help_panelside"]),
            toggle("led", "g_extras"), toggle("ledlight", "g_extras"), select("ledlen", "g_extras", LEDLEN_IDS, t["help_ledlen"]),
            slider("ledcount", "g_extras", 1, S.LED_MAX, 1, "ks", t["help_ledcount"]),
            *[slider(f"ledpos{k}", "g_extras", -1500, 1500, 1, "mm", t["help_ledpos"] if k == 1 else None) for k in range(1, S.LED_MAX + 1)],
            toggle("socket", "g_extras"), slider("socketup", "g_extras", -1500, 1500, 10, "mm", t["help_socket"]), slider("socketside", "g_extras", -1500, 1500, 10, "mm"), toggle("pet", "g_extras"),
            select("petleg", "g_extras", ("fl", "fr", "rl", "rr", "fm", "rm")), select("petface", "g_extras", ("right", "left", "front", "back")),
            slider("petpos", "g_extras", -1200, 600, 10, "mm", t["help_petpos"]),
            slider("arm", "g_extras", S.ROZSAH["led_rameno"][0], S.ROZSAH["led_rameno"][1], 10, "mm"),
            toggle("braces", "g_extras"), slider("bracelen", "g_extras", S.ROZSAH["vzpera_delka"][0], S.ROZSAH["vzpera_delka"][1], 10, "mm", t["help_braces"]),
            toggle("upshelf", "g_extras"), select("upshelftype", "g_extras", HP.TYP_IDS, t["help_upshelf"]), select("upshelfboard", "g_extras", HP.DESKY_IDS),
            slider("upshelfpos", "g_extras", int(HP.VYSKA_MIN), int(HP.VYSKA_MAX), 10, "mm"), slider("upshelfdepth", "g_extras", int(HP.HLOUBKA_MIN), int(HP.HLOUBKA_MAX), 10, "mm"), slider("upshelftilt", "g_extras", int(HP.SKLON_MIN), int(HP.SKLON_MAX), int(HP.SKLON_KROK), "°"),
        ] + [x for n, tg, par, sl in VYREZY for x in (
            toggle(tg, "g_cuts"),
            slider(sl["w"], "g_cuts", int(S.VYREZ_MIN), int(S.ROZSAH["sirka"][1] - 2 * S.VYREZ_OKRAJ), 10, "mm", t["help_cuts"] if n == 1 else None),
            slider(sl["d"], "g_cuts", int(S.VYREZ_MIN), int(S._rozsahy(system)["hloubka"][1] + S.ROZSAH["presah"][1] - 30 - 2 * S.VYREZ_OKRAJ + S.SYSTEMY[system]["profil_mm"]), 10, "mm"),
            slider(sl["x"], "g_cuts", int(S.VYREZ_OKRAJ), int(S._rozsahy(system)["hloubka"][1] + S.ROZSAH["presah"][1] - 30 - S.VYREZ_OKRAJ - S.VYREZ_MIN + S.SYSTEMY[system]["profil_mm"]), 10, "mm"),
            slider(sl["z"], "g_cuts", int(S.VYREZ_OKRAJ), int(S.ROZSAH["sirka"][1] - S.VYREZ_OKRAJ - S.VYREZ_MIN), 10, "mm"),
            toggle(f"{tg}shelf", "g_cuts"))] + [
            toggle("bearings", "g_bearings"),
            slider("bearpitch", "g_bearings", S.ROZSAH["loz_rozteca"][0], S.ROZSAH["loz_rozteca"][1], 10, "mm", t["help_bearings"]),
            slider("bearedge", "g_bearings", LOZ_OKRAJ_MIN, S.ROZSAH["loz_okraj"][1], 10, "mm")],
        "default_selection": vychozi_vyber(system),
    }


PROFIL_MM = 30                     # profil 30x30 (Object_7, SKU 1.1.08.030030.03); drazka 8 mm
PROFIL = f"{PROFIL_MM}x{PROFIL_MM}"
AUTO_VZPERY = {"cs": "Rameno LED je delší než {prah} mm – přidány šikmé vzpěry (jdou vypnout).",
               "en": "The LED arm is longer than {prah} mm – angled braces added (they can be switched off).",
               "sk": "Rameno LED je dlhšie ako {prah} mm – pridané šikmé vzpery (dajú sa vypnúť)."}


def schema(lang="cs", system=30, delky=None):
    if system == S.SYSTEM_SSE:
        return _sse().schema(lang)                                       # SSE: vlastni schema (jen rozmery, stredni noha, police, supliky)
    out = _schema_zaklad(lang, system)
    if not S.SYSTEMY[system]["vzpery"]:                         # system bez sikmych vzper (40): slot vzper se nenabizi
        out["slots"] = [sl for sl in out["slots"] if sl["id"] not in ("braces", "bracelen")]
    if system not in S.NAVLEK_SYSTEMY:                          # navlek nohou (jekl 40x40x2) je jen v systemu 35: v ostatnich se slot nenabizi
        out["slots"] = [sl for sl in out["slots"] if sl["id"] not in ("sleeve", "sleevelen")]
    delky_ = delky_pro_pozadavek() if delky is None else delky       # delky panelu v nabidce tohoto pozadavku: verejnost jen s aktivni kartou (pravidlo 54), zamestnanec vsechny
    nab_hp = nabidka_police(system)                              # horni police: desky a typy v nabidce (system; verejnost jen aktivni karty)
    for sl in out["slots"]:
        if sl["id"] == "upshelfboard":
            sl["options"] = [o for o in sl["options"] if o["id"] in nab_hp[0]]
        if sl["id"] == "upshelftype":
            sl["options"] = [o for o in sl["options"] if HP.TYP_ID[o["id"]] in nab_hp[1]]
        if sl["id"] == "panellen":
            sl["options"] = [o for o in sl["options"] if int(o["id"]) in delky_]
    if len(delky_) < 2:                                          # nabizi se jen 1190: slot delky se verejnosti vubec nevraci (ani ve vychozim vyberu)
        out["slots"] = [sl for sl in out["slots"] if sl["id"] != "panellen"]
        out["default_selection"].pop("panellen", None)
    led_delky_ = led_delky_pro_pozadavek()                       # delky svitidla LED v nabidce tohoto pozadavku: verejnost jen s aktivni kartou (pravidlo 54), zamestnanec vsechny
    for sl in out["slots"]:
        if sl["id"] == "ledlen":
            sl["options"] = [o for o in sl["options"] if int(o["id"]) in led_delky_]
    if len(led_delky_) < 2:                                      # nabizi se jen 1200: slot delky se verejnosti vubec nevraci (ani ve vychozim vyberu)
        out["slots"] = [sl for sl in out["slots"] if sl["id"] != "ledlen"]
        out["default_selection"].pop("ledlen", None)
    zav = _zavisi_na()
    for sl in out["slots"]:
        if sl["id"] in zav:
            sl["depends_on"] = list(zav[sl["id"]])
        if sl.get("help"):
            sl["help"] = sl["help"].replace("{prah}", str(int(S.prah_sirky(system))))          # nastavitelny prah (Pravidla stolu SYSTEMU): napoveda nese aktualni cislo
        if sl["id"] == "braces":
            # Robert 2026-10-04: pri delce ramene LED nad 500 mm od stojek se sikme vzpery pridaji AUTOMATICKY (jdou vypnout; nezapnou se, kdyz se nevejdou nebo je zakaznik sam vypnul).
            # Pravidlo vykonava modul voleb (product-configurator.js) po kazdem resolve; prah je nastavitelny (Pravidla stolu, app_settings stul_pravidla)
            prah = int(S.pravidlo("vzpery_od_ramene", system))
            sl["auto_on"] = {"when": {"slot": "arm", "above": prah}, "message": AUTO_VZPERY[lang if lang in AUTO_VZPERY else "cs"].format(prah=prah)}
    return out


# ---------------------------------------------------------------------------------------------------------------------
# vyber <-> parametry generatoru
# ---------------------------------------------------------------------------------------------------------------------
def _cislo(v, lo, hi, vychozi, krok=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return vychozi
    if not math.isfinite(x):
        return vychozi
    x = min(hi, max(lo, x))
    if krok:
        x = lo + round((x - lo) / krok) * krok
    return x


def _mid_meze_pct(sirka, system):
    """(nejmene, nejvic) procent rozpeti (od leve nohy) pro stredni nohu / ram: aspon MIN_ODSTUP_STREDNI_NOHY od krajnich noh a obe casti desky (deli se u opory) se vejdou do tabule laminodesky
    (S.stredni_noha_meze). Procenta jsou cela cisla uvnitr mezi (zaokrouhleno dovnitr), nejmene 5 a nejvic 95 jako dosud."""
    span = sirka - S.SYSTEMY[system]["profil_mm"]
    zm_min, zm_max = S.stredni_noha_meze(sirka, system)
    mn = max(5, math.ceil(zm_min / span * 100 - 1e-9))
    mx = min(95, math.floor(zm_max / span * 100 + 1e-9))
    return (mn, mx) if mn <= mx else (50, 50)


def normalizuj(selection, system=30, delky=None, nab_hp=None):
    """Vybrany stav -> (parametry generatoru, normalizovany vyber pro UI). Hodnoty mimo rozsah se orezou, neznama pole zahodi. `system` = system profilu produktu (30 | 40)."""
    system = S.over_system(system)
    if system == S.SYSTEM_SSE:
        return _sse().normalizuj(selection)
    sel = vychozi_vyber(system)
    for k_, v_ in VYCHOZI_VYBER_NAVLEK.items():                          # systemy bez navleku: klice nejsou ve vychozim vyberu; klient je muze poslat (vyber z jineho systemu), zahodi se nize (`p["navlek"]`)
        sel.setdefault(k_, v_)
    if isinstance(selection, dict):
        for k in selection:
            if k in VYCHOZI_VYBER or k in VYCHOZI_VYBER_NAVLEK:
                sel[k] = selection[k]
    p = {
        "system": system,
        "sirka": _cislo(sel["w"], *S.ROZSAH["sirka"], S.VYCHOZI["sirka"], 10),
        "hloubka": _cislo(sel["d"], *S._rozsahy(system)["hloubka"], 800, 10),
        "vyska": _cislo(sel["h"], *S.ROZSAH["vyska"], 840, 10),
        "presah": _cislo(sel["ov"], *S.ROZSAH["presah"], 30, 10),
        "led_rameno": _cislo(sel["arm"], *S.ROZSAH["led_rameno"], 560, 10),
    }
    for sid, par in _prepinace(system).items():
        p[par] = bool(sel[sid]) if not isinstance(sel[sid], str) else sel[sid].lower() in ("1", "true", "on", "yes")
    p["navlek"] = bool(p.get("navlek")) and system in S.NAVLEK_SYSTEMY     # navlek jen v systemu 35 (vyber z jineho systemu se pri preklopeni tise zahodi)
    p["navlek_delka"] = _cislo(sel["sleevelen"], *S.ROZSAH["navlek_delka"], S.VYCHOZI["navlek_delka"], S.NAVLEK_KROK) if p["navlek"] else float(S.VYCHOZI["navlek_delka"])
    p["police"] = int(_cislo(sel["shelf"], 0, S.MAX_POLIC, 1, 1))
    if p["police"] < 1:
        p["police_deska"] = True                                  # bez spodnich polic volba 'bez desky' neexistuje (slot je skryty, hodnotu server ignoruje)
    p["suplik_pocet"] = int(_cislo(sel["drawercount"], S.SUPLIK_POCTY[0], S.SUPLIK_POCTY[-1], S.SUPLIK_POCET_VYCHOZI, 1)) if p["suplik"] else int(S.SUPLIK_POCET_VYCHOZI)          # pocet supliku boxu 1 / 2 / 3
    p["panely_pocet"] = int(_cislo(sel["panelcount"], 0, S.PANELY_MAX, S.VYCHOZI["panely_pocet"], 1)) if p["panely"] else int(S.VYCHOZI["panely_pocet"])          # panely: pocet po jednom kuse, posun po stojkach
    p["panely_posun"] = _cislo(sel["panelpos"], 0, 3000, 0, 10) if p["panely"] else 0.0
    p["led_delka"] = _ledlen(sel.get("ledlen"), led_delky_pro_pozadavek()) if p["led"] else float(S.LED_DELKA_VYCHOZI)          # delka svitidla LED (vsechna stejna); bez LED vychozi
    p["led_pocet"] = int(_cislo(sel.get("ledcount"), 1, S.LED_MAX, 1, 1)) if p["led"] else 1          # svitidla LED RUCNE (Robert 2026-10-08): pocet (vychozi 1) a poloha kazdeho (mm od osy stolu, None = automaticky); PRESNE meze hlida generator (options.ledcount / ledpos<k>)
    for k in range(1, S.LED_MAX + 1):
        p[f"led_z{k}"] = _ledpos(sel.get(f"ledpos{k}")) if (p["led"] and k <= p["led_pocet"]) else None
    p["panely_delka"] = _panellen(sel.get("panellen"), delky_pro_pozadavek() if delky is None else delky) if p["panely"] else float(S.PANEL_DELKA_VYCHOZI)          # delka panelu (vsechny panely stolu stejne dlouhe); co se nevejde, snizi generator
    p["panely_z"] = _cislo(sel["panelside"], -3000, 3000, 0, 1) if p["panely"] else 0.0          # panely do stran (mm od stredu useku mezi nohama; PRESNE meze hlida generator: options.panelside)
    nab_hp = nabidka_police(system) if nab_hp is None else nab_hp                                                       # desky a typy horni police v nabidce (verejnost jen aktivni karty)
    p["hpolice_typ"] = _upshelf_typ(sel.get("upshelftype"), nab_hp) if p["hpolice"] else HP.TYP_VYCHOZI                  # horni police: typ, deska podle typu a systemu, vyska (None = automaticky), hloubka
    p["hpolice_deska"] = _upshelf_deska(sel.get("upshelfboard"), system, p["hpolice_typ"], nab_hp) if p["hpolice"] else HP.DESKA_VYCHOZI
    p["hpolice_vyska"] = (None if sel.get("upshelfpos") in (None, "") else round(_cislo(sel["upshelfpos"], HP.VYSKA_MIN, HP.VYSKA_MAX, HP.VYSKA_MIN), 1)) if p["hpolice"] else None
    p["hpolice_hloubka"] = _cislo(sel["upshelfdepth"], HP.HLOUBKA_MIN, HP.HLOUBKA_MAX, HP.HLOUBKA_VYCHOZI, 10) if p["hpolice"] else float(HP.HLOUBKA_VYCHOZI)
    p["hpolice_sklon"] = _cislo(sel["upshelftilt"], HP.SKLON_MIN, HP.SKLON_MAX, HP.SKLON_VYCHOZI, HP.SKLON_KROK) if (p["hpolice"] and p["hpolice_typ"] == "sikma") else float(HP.SKLON_VYCHOZI)       # sklon jen u sikme police
    p["stredni_opora"] = MIDSUPPORT_ID.get(sel.get("midsupport"), "auto")
    p["stojky_vyska"] = _cislo(sel["posth"], *S.ROZSAH["stojky_vyska"], S.VYCHOZI["stojky_vyska"])                # bez zaokrouhleni: vychozi 1073 (sablona) neni na mrizce 10 mm
    p["elzlab_y"] = _cislo(sel["socketup"], -3000, 3000, 0, 10) if (p["elektrozlab"] and p["panely"]) else 0.0     # elektrozlab: posun svisle / do stran (PRESNE meze hlida generator: options.socketup / socketside)
    p["elzlab_z"] = _cislo(sel["socketside"], -3000, 3000, 0, 10) if (p["elektrozlab"] and p["panely"]) else 0.0
    for k in range(1, S.MAX_POLIC + 1):                            # vyska polic: None = automaticky (rovnomerne); PRESNE meze hlida generator (`police_meze` -> options.sh<k>)
        p[f"police_h{k}"] = None if sel.get(f"sh{k}") in (None, "") else round(_cislo(sel[f"sh{k}"], 0, 3000, 100), 1)          # bez mrizky 10 mm: meze jsou na 0,1 mm
    for n, tg, par, sl in VYREZY:                                  # vyrezy: rozmery po 10 mm, presne orezani na desku dela generator
        v = sel[tg]
        p[par] = bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "on", "yes")
        for sfx, lo in (("w", S.VYREZ_MIN), ("d", S.VYREZ_MIN), ("x", S.VYREZ_OKRAJ), ("z", S.VYREZ_OKRAJ)):
            p[f"{par}_{sfx}"] = _cislo(sel[sl[sfx]], lo, 3000, S.VYCHOZI[f"{par}_{sfx}"], 10)
        v = sel[f"{tg}shelf"]
        p[f"{par}_police"] = bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "on", "yes")
    v = sel["bearings"]
    p["loz"] = bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "on", "yes")
    p["loz_rozteca"] = _cislo(sel["bearpitch"], S.ROZSAH["loz_rozteca"][0], S.ROZSAH["loz_rozteca"][1], S.VYCHOZI["loz_rozteca"], 10)
    p["loz_okraj"] = _cislo(sel["bearedge"], LOZ_OKRAJ_MIN, S.ROZSAH["loz_okraj"][1], S.VYCHOZI["loz_okraj"], 10)
    p["vzpera_delka"] = _cislo(sel["bracelen"], *S.ROZSAH["vzpera_delka"], S.VYCHOZI["vzpera_delka"], 10)
    span = p["sirka"] - S.SYSTEMY[system]["profil_mm"]
    mid_pct = _cislo(sel["mid"], 5, 95, 50, 1)
    p["stredni_noha"] = None
    if p["sirka"] > S.prah_sirky(system):
        min_pct, max_pct = _mid_meze_pct(p["sirka"], system)
        mid_pct = min(max_pct, max(min_pct, mid_pct))
        p["stredni_noha"] = span * mid_pct / 100.0 if mid_pct != 50 else None
    else:
        mid_pct = 50
    # posun supliku: rozumny rozsah jen proti nesmyslum; PRESNE meze (odstup od kazde nohy) hlida generator (`suplik_meze` -> options.boxpos), mimo ne vznikne problem/nabidka
    p["suplik_posun"] = _cislo(sel["boxpos"], -3000, 3000, 0, 10) if p["suplik"] else 0.0
    p["pet_noha"] = PET_NOHA_ID.get(sel.get("petleg"), "PL") if p["drzak_pet"] else "PL"                 # umisteni drzaku PET (noha, strana profilu); neznama hodnota = vychozi
    p["pet_strana"] = PET_STRANA_ID.get(sel.get("petface"), "vpravo") if p["drzak_pet"] else "vpravo"
    p["pet_posun"] = _cislo(sel["petpos"], -2000, 2000, 0, 10) if p["drzak_pet"] else 0.0              # svisly posun drzaku PET lahve; PRESNE meze hlida generator (`pet_meze` -> options.petpos)
    norm = {"w": int(p["sirka"]), "d": int(p["hloubka"]), "h": int(p["vyska"]), "ov": int(p["presah"]), "arm": int(p["led_rameno"]), "mid": int(mid_pct), "boxpos": int(p["suplik_posun"]), "petpos": int(p["pet_posun"]), "petleg": PET_NOHA_VEREJNE[p["pet_noha"]], "petface": PET_STRANA_VEREJNE[p["pet_strana"]]}
    for k in range(1, S.MAX_POLIC + 1):
        norm[f"sh{k}"] = None if p[f"police_h{k}"] is None else round(float(p[f"police_h{k}"]), 1)
    for sid, par in _prepinace(system).items():
        norm[sid] = p[par]
    norm["shelf"] = p["police"]
    for n, tg, par, sl in VYREZY:
        norm[tg] = p[par]
        norm[f"{tg}shelf"] = bool(p[f"{par}_police"] and p[par])
        for sfx in ("w", "d", "x", "z"):
            norm[sl[sfx]] = int(round(p[f"{par}_{sfx}"]))
    norm["bearings"], norm["bearpitch"], norm["bearedge"] = p["loz"], int(p["loz_rozteca"]), int(p["loz_okraj"])
    norm["bracelen"] = int(p["vzpera_delka"])
    if system in S.NAVLEK_SYSTEMY:
        norm["sleevelen"] = int(p["navlek_delka"])
    norm["panelcount"], norm["panelpos"], norm["midsupport"] = p["panely_pocet"], int(p["panely_posun"]), MIDSUPPORT_VEREJNE[p["stredni_opora"]]
    norm["panelside"] = int(round(p["panely_z"]))
    norm["panellen"] = str(int(round(p["panely_delka"])))
    norm["ledlen"] = str(int(round(p["led_delka"])))
    norm["ledcount"] = p["led_pocet"]
    for k in range(1, S.LED_MAX + 1):
        norm[f"ledpos{k}"] = _cele_nebo_none(p[f"led_z{k}"])
    norm["drawercount"] = p["suplik_pocet"]
    norm["posth"], norm["socketup"], norm["socketside"] = round(float(p["stojky_vyska"]), 1), int(p["elzlab_y"]), int(p["elzlab_z"])
    norm["upshelftype"], norm["upshelfboard"] = HP.TYP_VEREJNE[p["hpolice_typ"]], p["hpolice_deska"]
    norm["upshelfpos"], norm["upshelfdepth"] = _cele_nebo_none(p["hpolice_vyska"]), int(round(p["hpolice_hloubka"]))
    norm["upshelftilt"] = int(round(p["hpolice_sklon"]))
    return p, norm


def _min_platne(par, p, krok=10):
    """Nejmensi hodnota posuvniku `par`, pri ktere je (pri ostatnich volbach beze zmeny) konfigurace platna; pulenim intervalu
    (omezeni je monotonni: vetsi stul vzdy vyhovuje, kdyz vyhovuje mensi)."""
    lo0, hi0 = S.ROZSAH[par]
    def ok(v):
        return not S.sestav_stul(**{**p, par: v})["problemy"]
    if ok(lo0):
        return int(lo0)
    if not ok(hi0):
        return int(lo0)               # nic nevyhovuje (jine volby) - neomezuj, chybu ukaze `errors`
    lo, hi = 0, int((hi0 - lo0) // krok)
    while lo < hi:
        mid = (lo + hi) // 2
        if ok(lo0 + mid * krok):
            hi = mid
        else:
            lo = mid + 1
    return int(lo0 + lo * krok)


# ---------------------------------------------------------------------------------------------------------------------
# podepsany odkaz na model
# ---------------------------------------------------------------------------------------------------------------------
def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _klic():
    return app.secret_key.encode() if isinstance(app.secret_key, str) else app.secret_key


_BITY = [None, "kolecka", "panely", "led", "suplik", "elektrozlab", "drzak_pet", "patky", "vzpery", "navlek", "hpolice"]      # bit 10 horni police mezi zadnimi stojkami; bit 0 drive police (ted pocet v klici "p"); bit 8 sikme vzpery ramen LED; bit 9 navlek nohou (system 35)


def _zabal(p):
    t = sum(1 << i for i, k in enumerate(_BITY) if k and p[k])
    out = {"w": int(p["sirka"]), "d": int(p["hloubka"]), "h": int(p["vyska"]), "o": int(p["presah"]), "r": int(p["led_rameno"]), "p": int(p["police"]), "t": t, "b": int(p["suplik_posun"])}
    if p.get("stredni_noha") is not None:
        out["m"] = round(float(p["stredni_noha"]), 1)
    if not p.get("stojky", True):
        out["s"] = 0                          # zadni stojky vypnuty (starsi tokeny bez klice = zapnuty)
    c = [([round(float(p[f"{par}_{sfx}"]), 1) for sfx in ("w", "d", "x", "z")] + ([1] if p.get(f"{par}_police") else [])) if p.get(par) else 0
         for n, tg, par, sl in VYREZY]
    if any(c):
        out["c"] = c                          # vyrezy: [w, d, x, z(, 1 = police pod vyrezem)] zapnutych, 0 = vypnuty (starsi tokeny bez klice = zadne vyrezy)
    if p.get("loz"):
        out["l"] = [round(float(p["loz_rozteca"]), 1), round(float(p["loz_okraj"]), 1)]      # loziskove jednotky: [rozteč, okraj] (bez klice = vypnuto)
    if p.get("vzpery"):
        out["v"] = int(p["vzpera_delka"])                                                    # sikme vzpery ramen LED: delka profilu (mm); zapnuti nese bit "vzpery" v "t"
    if p.get("hpolice") and p.get("stojky", True):
        out["R"] = [p["hpolice_typ"], p["hpolice_deska"], None if p.get("hpolice_vyska") is None else round(float(p["hpolice_vyska"]), 1), round(float(p["hpolice_hloubka"]), 1)] + ([round(float(p["hpolice_sklon"]), 1)] if p["hpolice_typ"] == "sikma" else [])      # horni police: typ, deska, vyska (None = auto), hloubka; zapnuti nese bit "hpolice" v "t"; klic R (K je delka LED)
    if p.get("navlek"):
        out["a"] = int(round(float(p["navlek_delka"])))                                      # navlek nohou (jekl, system 35): delka (mm); zapnuti nese bit "navlek" v "t"
    if not p.get("led_svetlo", True) and p.get("led") and p.get("stojky", True):
        out["u"] = 0                                                                         # svitidlo LED odebrano (ramena + pricny profil zustavaji)
    if p.get("suplik_vlevo") and p.get("suplik"):
        out["f"] = 1                                                                         # suplikovy box na leve strane (zrcadlova poloha)
    if p.get("suplik") and int(p.get("suplik_pocet", S.SUPLIK_POCET_VYCHOZI)) != S.SUPLIK_POCET_VYCHOZI:
        out["D"] = int(p["suplik_pocet"])                                                    # pocet supliku boxu 1 / 3 (bez klice = 2)
    if p.get("system", 30) != 30:
        out["y"] = int(p["system"])                                                          # system profilu (40); bez klice = 30 (starsi tokeny)
    if p.get("panely") and p.get("stojky", True):
        if int(p.get("panely_pocet", 1)) != 1:
            out["N"] = int(p["panely_pocet"])                                                # pocet panelu (bez klice = 1)
        if p.get("panely_posun"):
            out["Q"] = round(float(p["panely_posun"]), 1)                                    # posun panelu po stojkach (mm)
        if p.get("panely_z"):
            out["X"] = round(float(p["panely_z"]), 1)                                        # posun panelu do stran (mm, + doprava; bez klice = uprostred)
        if int(round(float(p.get("panely_delka", S.PANEL_DELKA_VYCHOZI)))) != S.PANEL_DELKA_VYCHOZI:
            out["L"] = int(round(float(p["panely_delka"])))                                  # delka panelu (mm; bez klice = 1190)
    if p.get("led") and p.get("stojky", True) and p.get("led_svetlo", True) and int(round(float(p.get("led_delka", S.LED_DELKA_VYCHOZI)))) != S.LED_DELKA_VYCHOZI:
        out["K"] = int(round(float(p["led_delka"])))                                         # delka svitidla LED (mm; bez klice = 1200)
    if p.get("led") and p.get("stojky", True) and p.get("led_svetlo", True) and (int(p.get("led_pocet", 1)) != 1 or any(p.get(f"led_z{k}") is not None for k in range(1, S.LED_MAX + 1))):
        n_led = int(p.get("led_pocet", 1))
        out["J"] = [n_led] + [None if p.get(f"led_z{k}") is None else round(float(p[f"led_z{k}"]), 1) for k in range(1, n_led + 1)]          # svitidla LED RUCNE: [pocet, poloha 1.. (None = automaticky)]; bez klice = jedno svitidlo na automaticke poloze
    if p.get("stredni_opora", "auto") != "auto":
        out["M"] = 1 if p["stredni_opora"] == "noha" else 2                                  # stredni opora: 1 = nohy, 2 = vestaveny ram (bez klice = auto)
    if p.get("stojky", True) and abs(float(p.get("stojky_vyska", S.VYCHOZI["stojky_vyska"])) - S.VYCHOZI["stojky_vyska"]) > 1e-9:
        out["Z"] = round(float(p["stojky_vyska"]), 1)                                        # vyska zadnich stojek nad deskou (bez klice = 1073)
    if p.get("elektrozlab") and p.get("panely") and (p.get("elzlab_y") or p.get("elzlab_z")):
        out["E"] = [round(float(p.get("elzlab_y", 0)), 1), round(float(p.get("elzlab_z", 0)), 1)]      # posun elektrozlabu (svisle, do stran)
    if p.get("drzak_pet") and (p.get("pet_noha", "PL") != "PL" or p.get("pet_strana", "vpravo") != "vpravo"):
        out["P"] = [p.get("pet_noha", "PL"), p.get("pet_strana", "vpravo")]                  # umisteni drzaku PET (noha, strana profilu); bez klice = vychozi
    if p.get("pet_posun") and p.get("drzak_pet"):
        out["q"] = int(p["pet_posun"])                                                       # svisly posun drzaku PET lahve (mm, + nahoru)
    if p.get("police") and not p.get("police_deska", True):
        out["B"] = 0                                                                         # spodni police BEZ DESKY (Robert 2026-10-07; bez klice = s deskou)
    hs = [p.get(f"police_h{k}") for k in range(1, S.MAX_POLIC + 1)]
    if any(v is not None for v in hs[:int(p["police"])]):
        out["H"] = [None if (v is None or i >= int(p["police"])) else round(float(v), 1) for i, v in enumerate(hs)]          # vyska polic shora: [odstup 1. police, mezery...] (None = automaticky)
    return out


def _rozbal(o):
    p = {"sirka": o["w"], "hloubka": o["d"], "vyska": o["h"], "presah": o.get("o", 30), "led_rameno": o.get("r", 560), "suplik_posun": o.get("b", 0), "stredni_noha": o.get("m")}
    for i, k in enumerate(_BITY):
        if k:
            p[k] = bool(o["t"] >> i & 1)
    p["police"] = int(o["p"]) if "p" in o else int(o["t"] & 1)             # starsi tokeny: bit 0 = police zapnuta (1 ks)
    p["stojky"] = bool(o.get("s", 1))
    for (n, tg, par, sl), e in zip(VYREZY, list(o.get("c") or []) + [0] * MAX_VYREZU):
        if e:
            p[par] = True
            for sfx, v in zip(("w", "d", "x", "z"), e):
                p[f"{par}_{sfx}"] = float(v)
            p[f"{par}_police"] = bool(len(e) > 4 and e[4])
    if o.get("l"):
        p["loz"], p["loz_rozteca"], p["loz_okraj"] = True, float(o["l"][0]), float(o["l"][1])
    if o.get("v"):
        p["vzpera_delka"] = float(o["v"])
    if o.get("a"):
        p["navlek_delka"] = float(o["a"])
    if o.get("R"):                                                           # (klic "K" patri delce svitidla LED - vetev led600)
        p["hpolice_typ"], p["hpolice_deska"] = str(o["R"][0]), str(o["R"][1])
        p["hpolice_vyska"] = None if o["R"][2] is None else float(o["R"][2])
        p["hpolice_hloubka"] = float(o["R"][3])
        if len(o["R"]) > 4:
            p["hpolice_sklon"] = float(o["R"][4])
    for i, v in enumerate(o.get("H") or []):
        p[f"police_h{i + 1}"] = None if v is None else float(v)
    if o.get("P"):
        p["pet_noha"], p["pet_strana"] = str(o["P"][0]), str(o["P"][1])
    p["system"] = S.over_system(o.get("y", 30))
    if o.get("N"):
        p["panely_pocet"] = int(o["N"])
    if o.get("Q"):
        p["panely_posun"] = float(o["Q"])
    if o.get("X"):
        p["panely_z"] = float(o["X"])
    if o.get("L"):
        p["panely_delka"] = float(o["L"])
    if o.get("K"):
        p["led_delka"] = float(o["K"])
    if o.get("J"):
        p["led_pocet"] = int(o["J"][0])
        for i, v in enumerate(o["J"][1:], 1):
            p[f"led_z{i}"] = None if v is None else float(v)
    if o.get("M"):
        p["stredni_opora"] = "noha" if int(o["M"]) == 1 else "ram"
    if o.get("Z"):
        p["stojky_vyska"] = float(o["Z"])
    if o.get("E"):
        p["elzlab_y"], p["elzlab_z"] = float(o["E"][0]), float(o["E"][1])
    p["police_deska"] = "B" not in o
    p["suplik_vlevo"] = bool(o.get("f"))
    if o.get("D"):
        p["suplik_pocet"] = int(o["D"])
    p["led_svetlo"] = bool(o.get("u", 1))
    p["pet_posun"] = float(o.get("q", 0))
    return p


def podepis_model(p, ted=None):
    """Token pro /glb/<token>: kompaktni parametry (jen cisla, zadne nazvy) + platnost + HMAC (stateless, prezije restart serveru)."""
    exp = int((ted or time.time()) + MODEL_PLATNOST_S)
    telo = _b64(json.dumps(_zabal(p), separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(_klic(), f"{telo}.{exp}".encode(), hashlib.sha256).digest()[:18]
    return f"{telo}.{exp}.{_b64(sig)}"


def over_model(token, ted=None):
    """(parametry, None) nebo (None, kod chyby: 'podpis'|'vyprsel')."""
    try:
        telo, exp, sig = token.split(".")
        spravny = hmac.new(_klic(), f"{telo}.{exp}".encode(), hashlib.sha256).digest()[:18]
        if not hmac.compare_digest(spravny, _unb64(sig)):
            return None, "podpis"
        if (ted or time.time()) > int(exp):
            return None, "vyprsel"
        return _rozbal(json.loads(_unb64(telo))), None
    except Exception:
        return None, "podpis"


# ---------------------------------------------------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------------------------------------------------
def _slot_pro_problem(problem, dily, p, gen=None):
    n_pol = S._problem_police_vyrez(gen, problem) if gen else None        # kolize patri k polici pod vyrezem -> chyba u jejiho slotu (ne u prislusenstvi)
    if n_pol:
        return f"cut{n_pol}shelf"
    if problem.get("kod") == "loz_moc":
        return "bearpitch"
    if problem.get("kod") == "panel_nevejde":
        return "panels"
    if problem.get("kod") == "hpolice_nevejde":
        return "upshelf"
    if problem.get("kod") == "elzlab_bez_opory":
        return "socketup"
    if problem.get("kod") == "deska_mimo_tabuli":
        return "w" if problem.get("rozmer") == "sirka" else "d"                          # deska se nevejde do tabule laminodesky: chyba u rozmeru, ktery ji prodluzuje
    if problem.get("kod") in ("vzpera_kolize", "vzpery_potreba"):
        return "braces"
    if problem.get("kod") in ("navlek_vyska", "navlek_potreba", "navlek_kolize") or (problem.get("kod") == "kratka_noha" and p.get("navlek")):
        return "sleeve"
    for i in problem.get("dily") or []:
        kl_ = gen["klice"][i] if (gen and 0 <= i < len(gen["klice"])) else None
        if isinstance(kl_, (list, tuple)) and kl_ and kl_[0] == "hpol":
            return "upshelf"                                    # dily horni police: chyba patri k jejimu slotu
    for i in problem.get("dily") or []:
        if 0 <= i < len(dily) and dily[i]["part_id"] in DIL_NA_SLOT:
            if dily[i]["part_id"] == "product_4932" and (p["elzlab_y"] or p["elzlab_z"]):
                return "socketup"                                   # kolize / pokus o posun mimo stul u posunuteho elektrozlabu: chyba patri k jeho posuvnikum
            return DIL_NA_SLOT[dily[i]["part_id"]]
    if problem.get("kod") == "vyrez_prekryv":
        return f"cut{problem['vyrez']}"
    if problem.get("kod") == "stojky_potreba":
        return "posts"
    if problem.get("kod") == "elektrozlab_bez_panelu":
        return "socket"
    if problem.get("kod") == "kratka_noha" and p.get("kolecka"):
        return "wheels"
    return None


def _bez_ceny(out):
    """Odpoved BEZ jakekoli ceny (mini-shop je jen poptavka, ceny jsou skryte): zmizi `price` i `options.*.on.price_delta`."""
    out.pop("price", None)
    for o in (out.get("options") or {}).values():
        if isinstance(o, dict) and isinstance(o.get("on"), dict):
            o["on"].pop("price_delta", None)
    return out


def resolve(selection, lang="cs", ted=None, skryt_cenu=False, system=30):
    """Telo odpovedi resolve (viz modul). Cista funkce nad generatorem + cenou (DB jen cte pres stul_api._ctx_ceny). skryt_cenu=True = bez ceny (mini-shop).
    `system` = system profilu produktu (30 | 40)."""
    delky = delky_pro_pozadavek()                                # delky panelu v nabidce tohoto pozadavku (verejnost jen s aktivni kartou)
    nab_hp = nabidka_police(system)                              # desky a typy horni police v nabidce tohoto pozadavku (totez)
    p, norm = normalizuj(selection, system, delky, nab_hp)
    gen = S.sestav_stul(**p)
    p = {k: v for k, v in gen["parametry"].items()}              # EFEKTIVNI parametry: po automatickem odebrani prislusenstvi a orezu poctu polic
    h = stul_glb.kanonicky_hash(p)
    klic = (h, lang, tuple(sorted((o["volba"]) for o in gen["odebrano"])), S.pravidlo("cena_vyrez", p["system"]), norm.get("panelcount"), norm.get("drawercount"),
            S.pravidlo("cena_navlek_200", p["system"]), S.pravidlo("cena_navlek_400", p["system"]), norm.get("sleevelen"),
            S.pravidlo("cena_noha_sse_400", p["system"]), S.pravidlo("cena_noha_sse_1100", p["system"]), norm.get("panellen"), tuple(sorted(delky)), nab_hp, norm.get("ledlen"), norm.get("ledcount"), tuple(sorted(led_delky_pro_pozadavek())))          # cena za vyrez a navlek jsou pravidla mimo hash; POZADOVANY pocet panelu, supliku, delka navleku a delka panelu (upozorneni na orez / snizeni), nabizene delky
    if klic in _RESOLVE_CACHE:
        _RESOLVE_CACHE.move_to_end(klic)
        r = _RESOLVE_CACHE[klic]
    else:
        r = _spocti(p, norm, lang, h, gen, delky, nab_hp)
        _RESOLVE_CACHE[klic] = r
        while len(_RESOLVE_CACHE) > CACHE_MAX:
            _RESOLVE_CACHE.popitem(last=False)
    _STAV_PODLE_HASHE[h] = p
    while len(_STAV_PODLE_HASHE) > CACHE_MAX * 4:
        _STAV_PODLE_HASHE.popitem(last=False)
    out = copy.deepcopy(r)                                       # cache se sdili - volajici dostane vlastni kopii (zmena by poskodila ostatni)
    out["model"] = _model(p, ted)
    return _bez_ceny(out) if skryt_cenu else out


# ---------------------------------------------------------------------------------------------------------------------
# STABILNI VEREJNA FUNKCE PRO KOSIK / OBJEDNAVKU / NABIDKU (bot5, 2026-10-02): nezavisla na vnitrnostech (resolve/normalizuj/generator)
# ---------------------------------------------------------------------------------------------------------------------
def _hodnota_pro_souhrn(slot, hodnota, lang):
    ano, ne = jazyky.ano_ne(lang) or (("ano", "ne") if lang == "cs" else ("yes", "no"))      # jazyk z dat ma vlastni ano / ne; cs / en / sk beze zmeny
    if slot["type"] == "toggle":
        return ano if hodnota else ne
    if slot["type"] == "slider":
        return f"{hodnota} {slot['slider']['unit']}"
    if slot["type"] == "select":
        return next((o["label"] for o in slot.get("options", []) if o["id"] == hodnota), str(hodnota))
    return str(hodnota)


def _souhrn_voleb(sel, lang, system=30):
    """[{id, label, value}] - citelne shrnuti vyberu pro doklad/nabidku: jen volby, ktere maji v dane konfiguraci smysl, a jen to, co stul obsahuje (vypnute prepinace se neuvadeji, Robert 2026-10-08)."""
    schema_ = schema(lang, system)
    skryt = set()
    if sel["w"] <= S.prah_sirky(system):
        skryt.add("mid")
    if not sel["panels"]:
        skryt.update(("panelcount", "panellen", "panelpos", "panelside"))
    else:
        for sid_p in ("panelpos", "panelside"):
            if not sel.get(sid_p):
                skryt.add(sid_p)
    if not sel.get("sleeve"):
        skryt.add("sleevelen")                                   # delka navleku se ve shrnuti ukaze jen se zapnutym navlekem (kontrola 2026-10-05)
    if not sel["posts"]:
        skryt.add("posth")
    if sel["w"] <= S.prah_sirky(system) or sel.get("midsupport") == "auto":
        skryt.add("midsupport")
    if not (sel["socket"] and sel["panels"]):
        skryt.update(("socketup", "socketside"))
    else:
        for sid_z in ("socketup", "socketside"):
            if not sel.get(sid_z):
                skryt.add(sid_z)
    if not (sel["led"] and sel["posts"]):
        skryt.add("ledlight")
    if not (sel["led"] and sel["posts"]):
        skryt.add("arm")
    if not (sel["led"] and sel["posts"] and sel.get("ledlight", True)) or sel.get("ledlen", str(S.LED_DELKA_VYCHOZI)) == str(S.LED_DELKA_VYCHOZI):
        skryt.add("ledlen")                                      # delka svitidla LED ve shrnuti jen kdyz neni vychozi 1200 (shrnuti dosavadnich stolu beze zmeny)
    svitidlo_ = bool(sel["led"] and sel["posts"] and sel.get("ledlight", True))
    if not svitidlo_ or int(sel.get("ledcount") or 1) == 1:
        skryt.add("ledcount")                                    # pocet svitidel LED ve shrnuti jen kdyz neni 1 (shrnuti dosavadnich stolu beze zmeny)
    for k in range(1, S.LED_MAX + 1):
        if not svitidlo_ or k > int(sel.get("ledcount") or 1) or sel.get(f"ledpos{k}") is None:
            skryt.add(f"ledpos{k}")                              # poloha svitidla ve shrnuti jen u existujiciho svitidla s vyslovne zadanou polohou
    if not sel["drawers"]:
        skryt.update(("boxpos", "drawleft", "drawercount"))
    if not sel["pet"]:
        skryt.update(("petpos", "petleg", "petface"))
    else:
        if sel.get("petleg") == "fl":
            skryt.add("petleg")                                      # vychozi umisteni drzaku PET se ve shrnuti neopakuje
        if sel.get("petface") == "right":
            skryt.add("petface")
    if sel.get("shelfboard", True) or not sel.get("shelf"):
        skryt.add("shelfboard")                                  # deska spodnich polic se ve shrnuti ukaze jen kdyz je pryc (vychozi = s deskou; shrnuti vychoziho stolu zustava)
    for k in range(1, S.MAX_POLIC + 1):                           # vyska polic se ve shrnuti ukaze jen u existujici police s ruzne zadanou hodnotou
        if k > sel["shelf"] or sel.get(f"sh{k}") is None:
            skryt.add(f"sh{k}")
    for n, tg, par, sl in VYREZY:
        if not sel[tg]:
            skryt.update(sl.values())
            skryt.add(f"{tg}shelf")
    if not sel["bearings"]:
        skryt.update(("bearpitch", "bearedge"))
    if not sel["braces"]:
        skryt.add("bracelen")
    if not (sel.get("upshelf") and sel["posts"]):                  # horni police: volby se ve shrnuti ukazi jen se zapnutou policí; automaticka vyska ani deska ramove police se neuvadi
        skryt.update(("upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt"))
    else:
        if sel.get("upshelfpos") is None:
            skryt.add("upshelfpos")
        if sel.get("upshelftype") == "frame":
            skryt.add("upshelfboard")
        if sel.get("upshelftype") != "slope":
            skryt.add("upshelftilt")
    out = []
    for slot in schema_["slots"]:
        if slot["id"] in skryt or slot["id"] not in sel:
            continue
        if slot["type"] == "toggle" and not sel[slot["id"]]:
            continue                                             # Robert 2026-10-08: ve vypisech a popisech stolu jen to, co stul MA - vypnute volby (ne) se neuvadeji
        out.append({"id": slot["id"], "label": slot["label"], "value": _hodnota_pro_souhrn(slot, sel[slot["id"]], lang)})
    return out


def _neutralni_bom(dily):
    """Neutralni kusovnik (bez cisel dilu a dodavatelu): [{nazev, mnozstvi, rozmer}] - profily podle delky, desky podle rozmeru, ostatni kusy."""
    pocty = OrderedDict()
    for e in S.entries_pro_cenu(dily):
        nazev = S._NAZVY.get(e["part_id"], "díl")
        if "length_mm" in e:
            rozmer = f"{e['length_mm']:.0f} mm"
        elif "width_mm" in e:
            rozmer = f"{e['width_mm']:.0f} × {e['height_mm']:.0f} mm"
        else:
            rozmer = None
        pocty[(nazev, rozmer)] = pocty.get((nazev, rozmer), 0) + 1
    for m in S.spojovaci_material(dily, stul_api.nazvy_karet()):  # spojovaci material ke spojkam (sroub / matice) - nazev karty z katalogu, bez SKU
        pocty[(m["nazev"], None)] = pocty.get((m["nazev"], None), 0) + m["mnozstvi"]
    for d in dily:                                                # navlek nohou (jekl, system 35) a jeho zaslepka: nejsou karty katalogu (entries_pro_cenu je preskoci), ale patri do kusovniku
        if d["part_id"] == S.NAVLEK_PART:
            k_ = (S._NAZVY[S.NAVLEK_PART], f"{1000.0 * d['scale'][1]:.0f} mm")
            pocty[k_] = pocty.get(k_, 0) + 1
        elif d["part_id"] == S.NAVLEK_ZASLEPKA:
            k_ = (S._NAZVY[S.NAVLEK_ZASLEPKA], None)
            pocty[k_] = pocty.get(k_, 0) + 1
        elif d["part_id"] in (S.SSE_JEKL_PART, S.SSE_PROFIL_PART):                       # nohy SSE (system 41): nejsou karty katalogu (cena je pravidlo), do kusovniku patri
            k_ = (S._NAZVY[d["part_id"]], f"{1000.0 * d['scale'][1]:.0f} mm")
            pocty[k_] = pocty.get(k_, 0) + 1
        elif d["part_id"] in S.SSE_PARTS:
            k_ = (S._NAZVY[d["part_id"]], None)
            pocty[k_] = pocty.get(k_, 0) + 1
    return [{"nazev": n, "mnozstvi": q, "rozmer": r} for (n, r), q in sorted(pocty.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))]


def _hmotnost(gen, souhrn_ceny):
    """(hmotnost_kg | None, [nazvy dilu bez hmotnosti]). Hmotnost je jen soucet toho, co ma v katalogu hmotnost; dily bez hmotnosti (supliky, LED, panely,
    kolecka...) se nepocitaji - volajici musi vedet, ze cislo je NEUPLNE (doprava!), a ktere dily chybi. Laminodesky: karta hmotnost nema, spocte se
    ze skutecne plochy x 11,2 kg/m2 (Robert)."""
    ctx_dily = stul_api._ctx_ceny()["parts"]
    chybi = sorted({S._NAZVY.get(e["part_id"], "díl") for e in S.entries_pro_cenu(gen["dily"])
                    if (ctx_dily.get(e["part_id"]) or {}).get("weight_kg") in (None, 0, 0.0)})
    hmotnost = (souhrn_ceny or {}).get("weight_kg")
    if "laminodeska" in chybi and hmotnost is not None:
        hmotnost = round(hmotnost + S.hmotnost_lamino_kg(gen["dily"]), 3)
        chybi = [n for n in chybi if n != "laminodeska"]
    if hmotnost is not None and any(d["part_id"] == S.NAVLEK_PART for d in gen["dily"]):
        hmotnost = round(hmotnost + S.hmotnost_navleku_kg(gen["dily"]), 3)           # navlek nohou (jekl + zaslepka) nema kartu: hmotnost z delky jeklu
    if any(d["part_id"] in S.SSE_PARTS for d in gen["dily"]):                         # nohy SSE: hmotnost je jen ODHAD z rozmeru (jekl, vnitrni profil, plechy) -> hmotnost se nepovazuje za uplnou
        if hmotnost is not None:
            hmotnost = round(hmotnost + S.hmotnost_nohou_sse_kg(gen["dily"]), 3)
        chybi = sorted(set(chybi) | {"nohy SSE (hmotnost jen odhadem z rozměrů)"})
    return hmotnost, chybi


def _sestava_z_gen(gen):
    """SESTAVA = to, co se uklada pri objednani a z ceho se vyrabi: snimek dilu (format custom_shapes.data.parts), vyrobni vypis (rezny plan, desky
    s vyrezy, prislusenstvi, spojovaci material, montazni postup, role dilu) a katalogovy kusovnik se SKU a cenami. JSON-able, nova kopie."""
    p = gen["parametry"]
    h = stul_glb.kanonicky_hash(p)
    cena = stul_api.cena_konfigurace(gen["dily"], p["system"])
    kus, cena_celkem = [], None
    try:
        entries_, chybejici_ = stul_api.entries_s_materialem(gen["dily"])
        r = configurator_price.price_entries(entries_, stul_api._ctx_ceny())
        kus = [{"nazev": b["name"], "rozmer": (None if b["dim"] in (None, "", "-") else b["dim"]), "mnozstvi": b["qty"], "cena_ks_czk": b["unit_price"], "celkem_czk": b["total"]}
               for b in r["bom"]] + [{"nazev": m["nazev"] + (f" [{m['sku']}]" if m["sku"] else ""), "rozmer": None, "mnozstvi": m["mnozstvi"], "cena_ks_czk": None, "celkem_czk": 0} for m in chybejici_]
        cena_celkem = cena["bez_dph"] if cena else r["price_summary"]["total_czk"]          # vcetne prace mimo dily (cena za vyrez), stejne jako verejna cena
    except Exception as e:                                         # kusovnik z katalogu je doplnek vypisu - chyba ceniku nesmi shodit sestavu
        app.logger.warning("stul: katalogovy kusovnik selhal: %s", e)
    souhrn = copy.deepcopy(cena["souhrn"]) if cena else None
    hmotnost, chybi = _hmotnost(gen, souhrn)
    # co cenu doplnuje mimo dily z katalogu (rezy, pausal za profil, spoje, balne, zaokrouhleni): TY RADKY jsou soucasti celkove ceny, takze je vypis musi ukazat (vyrobni list) - stejne jako kusovnik pro zamestnance
    prace = [{"nazev": x["nazev"], "rozmer": None, "mnozstvi": x["mnozstvi"], "cena_ks_czk": x["cena_ks"], "celkem_czk": x["celkem"]} for x in (((cena or {}).get("kusovnik") or {}).get("prace") or [])]
    return {"parametry": copy.deepcopy(p), "hash": h, "kod": "STL-" + h[:6].upper(), "rules_version": stul_glb.RULES_VERSION, "valid": not gen["problemy"],
            "problemy": [x["text"] for x in gen["problemy"]], "dily": copy.deepcopy(gen["dily"]), "vypis": S.vyrobni_vypis(gen, stul_api.nazvy_karet()), "kusovnik_katalog": kus, "kusovnik_prace": prace,
            "cena_celkem_czk": cena_celkem, "cenovy_souhrn": souhrn, "hmotnost_kg": hmotnost, "hmotnost_uplna": not chybi, "hmotnost_chybi": chybi}


def _system_volani(product_id=None, system=None):
    """System profilu pro volani bez routy: `product_id` (karta, na kterou se kupuje) ma prednost pred `system`; bez obojiho 30."""
    if product_id is not None:
        return system_pro_produkt(product_id)
    return 30 if system is None else S.over_system(system)


def vyrobni_sestava(selection, rules_version=None, lang="cs", product_id=None, system=None):
    """SESTAVA konfigurace pro ulozeni pri objednani a pro vyrobu (stabilni funkce pro bot5): vyber (+ verze pravidel) -> {ok, selection, hash, kod, rules_version,
    parametry, dily (snimek: position/quaternion/scale/lic_peers/attached_to... jako custom_shapes.data.parts), vypis (rezny plan, desky s vyrezy, prislusenstvi,
    spojovaci material, montazni postup, role dilu), kusovnik_katalog (nazev se SKU, rozmer, pocet, cena), cenovy_souhrn, hmotnost_kg + neuplnost}. Nevalidni
    konfigurace -> {ok: false, chyba: "invalid_configuration", errors}; jina verze pravidel -> {ok: false, chyba: "rules_changed"}. Vzdy nova kopie."""
    po = pro_objednavku(selection, rules_version, lang, product_id, system)
    if not po["ok"]:
        return po
    if not po["valid"]:
        return {"ok": False, "chyba": "invalid_configuration", "errors": po["errors"]}
    p, _ = normalizuj(po["selection"], _system_volani(product_id, system))
    out = _sestava_z_gen(S.sestav_stul(**p))
    out.update(ok=True, selection=po["selection"])
    return out


def pro_objednavku(selection, rules_version=None, lang="cs", product_id=None, system=None):
    """Konfigurace stolu pro kosik/objednavku/nabidku (`product_id` = karta, na kterou se kupuje, urci system profilu 30 | 40; bez ni plati `system`, jinak 30): vyber (+ verze pravidel) -> EFEKTIVNI vyber, hash, kod, cena, neutralni kusovnik, souhrn voleb.
    Vraci vzdy HLUBOKOU KOPII (volajici ji muze menit). `rules_version` None = nekontrolovat; jina nez aktualni -> {"ok": False, "chyba": "rules_changed",
    "rules_version": aktualni} (volajici ma znovu zavolat bez ni a ukazat zakaznikovi novou cenu). Vyhodi jen pri chybe serveru (ne pri neplatnem vyberu -
    ten se orizne a ohlasi v `valid`/`errors`).
    {"ok": True, "selection", "hash", "kod", "rules_version", "valid", "errors": [str], "notices": [str], "price": {net, vat_rate, gross, currency} | None,
     "bom": [{nazev, mnozstvi, rozmer}], "pocet_spoju", "souhrn": [{id, label, value}], "hmotnost_kg": float|None (soucet hmotnosti dilu z katalogu + lamino desky ze skutecne plochy x 11,2 kg/m2 - NEUPLNE, dokud chybi dalsi hmotnosti), "hmotnost_uplna": bool,
     "hmotnost_chybi": [neutralni nazvy dilu bez hmotnosti v katalogu],
     "cenovy_souhrn": {material_czk, cut_czk, joint_czk, accessory_czk, packaging_czk, joint_count, weight_kg}|None}"""
    lang = lang if lang in TEXTY else "cs"
    aktualni = stul_glb.RULES_VERSION
    if rules_version is not None and str(rules_version) != aktualni:
        return {"ok": False, "chyba": "rules_changed", "rules_version": aktualni}
    sys_ = _system_volani(product_id, system)
    r = resolve(selection, lang, system=sys_)
    p, _ = normalizuj(r["selection"], sys_)
    gen = S.sestav_stul(**p)
    cena = stul_api.cena_konfigurace(gen["dily"], p["system"])
    souhrn_ceny = copy.deepcopy(cena["souhrn"]) if cena else None
    hmotnost, chybi = _hmotnost(gen, souhrn_ceny)
    return {"ok": True, "selection": r["selection"], "hash": r["hash"], "kod": r["kod"], "rules_version": aktualni, "valid": r["valid"],
            "errors": [e["message"] for e in r["errors"]], "notices": [n["message"] for n in r.get("notices", [])], "price": r["price"],
            "bom": _neutralni_bom(gen["dily"]), "pocet_spoju": gen["pocet_spoju"], "souhrn": _souhrn_voleb(r["selection"], lang, sys_),
            "hmotnost_kg": hmotnost, "hmotnost_uplna": not chybi, "hmotnost_chybi": chybi, "cenovy_souhrn": souhrn_ceny}


def glb_bytes(selection, system=30, razitka=None):
    """GLB (bytes) konfigurace pro vyber (EFEKTIVNI vyber po automatickem odebrani). Nemenne bytes z cache - muze se cist, ne menit v miste. razitka=None = VYCHOZI NASTAVENI GENERATORU (stul_glb.model_pro_parametry;
    WORKFLOW pravidlo 61, Robert 2026-10-08: razitka na vsech 3D modelech ve vsech generatorech, prepina ho jen stul_glb - bot8), True/False se predava vyslovne."""
    p, _ = normalizuj(selection, system)
    gen = S.sestav_stul(**p)
    return stul_glb.model_pro_parametry(gen["parametry"], **({} if razitka is None else {"razitka": razitka}))[1]


@app.get("/api/stul/vyrobni-sestava")
@staff_required
def stul_vyrobni_sestava_route():
    """Vyrobni sestava stolu jako JSON (jen zamestnanci); parametry jako /api/stul/konfigurace."""
    try:
        gen = S.sestav_stul(**S.parametry_z_dotazu(request.args))
    except S.StulChyba as e:
        return jsonify({"error": str(e), "kod": e.kod}), 400
    return jsonify(_sestava_z_gen(gen))


@app.get("/api/stul/vyrobni-list")
@staff_required
def stul_vyrobni_list_route():
    """Vyrobni list stolu (citelna HTML stranka k tisku: rezny plan, desky s vykresem, prislusenstvi, spojovaci material, montazni postup, kusovnik)."""
    try:
        gen = S.sestav_stul(**S.parametry_z_dotazu(request.args))
    except S.StulChyba as e:
        return jsonify({"error": str(e), "kod": e.kod}), 400
    resp = Response(stul_vyrobni_list.html_list(_sestava_z_gen(gen)), mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _model(p, ted=None):
    return {"stav": "hotovo", "url": "/api/shop/configurator/glb/" + podepis_model(p, ted), "odhad_ms": 0}


VOLBA_NA_SLOT = {"suplik": "drawers", "panely": "panels", "led": "led", "elektrozlab": "socket", "drzak_pet": "pet", "kolecka": "wheels", "patky": "feet", "vzpery": "braces", "navlek": "sleeve"}
VOLBA_NA_SLOT.update({par: tg for n, tg, par, sl in VYREZY})
VOLBA_NA_SLOT.update({f"{par}_police": f"{tg}shelf" for n, tg, par, sl in VYREZY})
NAZVY_SLOTU = {"cs": {"drawers": "šuplíky", "panels": "panely", "led": "LED osvětlení", "socket": "elektrožlab", "pet": "držák PET lahve", "wheels": "kolečka", "feet": "stavitelné patky",
                      "braces": "šikmé vzpěry ramen LED", "sleeve": "návlek nohou"},
               "en": {"drawers": "the drawers", "panels": "the panels", "led": "the LED light", "socket": "the power strip", "pet": "the PET bottle holder", "wheels": "the castors", "feet": "the adjustable feet",
                      "braces": "the angled LED arm braces", "sleeve": "the leg sleeves"}}
for _n, _tg, _par, _sl in VYREZY:
    NAZVY_SLOTU["cs"][_tg], NAZVY_SLOTU["en"][_tg] = f"výřez {_n}", f"cutout {_n}"
    NAZVY_SLOTU["cs"][f"{_tg}shelf"], NAZVY_SLOTU["en"][f"{_tg}shelf"] = f"polici pod výřezem {_n}", f"the shelf under cutout {_n}"
TEXTY_AKCI = {
    "cs": {"odebrano": "Automaticky odebráno: ", "odebrat": "Odebrat ", "roztahnout_w": "Roztáhnout stůl na šířku {v} mm a zapnout", "roztahnout_d": "Roztáhnout stůl na hloubku {v} mm a zapnout",
           "roztahnout_h": "Zvýšit zadní stojky na {v} mm a zapnout"},
    "en": {"odebrano": "Automatically removed: ", "odebrat": "Remove ", "roztahnout_w": "Widen the table to {v} mm and switch on", "roztahnout_d": "Make the table {v} mm deep and switch on",
           "roztahnout_h": "Raise the rear uprights to {v} mm and switch on"},
}


# ---------------------------------------------------------------------------------------------------------------------
# slovenčina (bot7 2026-10-02: docs/miniweb_stul_popisky_sk_navrh.json; slovo "konfigurátor" se ve verejnem textu nepouziva; texty vlozeny primo,
# bez zavislosti na souboru; doplneno: feet a NAZVY_SLOTU/TEXTY_AKCI - bot8, ke kontrole bot7)
# ---------------------------------------------------------------------------------------------------------------------
_SK_TEXTY = {
    "g_size": "Rozmery",
    "g_frame": "Konštrukcia",
    "g_extras": "Príslušenstvo",
    "w": "Šírka dosky",
    "d": "Hĺbka dosky",
    "h": "Výška pracovnej dosky",
    "ov": "Presah dosky vpredu cez čelný profil",
    "arm": "Dĺžka ramena LED od zadných stojok",
    "mid": "Poloha strednej nohy (zľava)",
    "boxpos": "Poloha zásuvkového bloku",
    **{f"sh{_k}": ("Polica 1 (najvyššia): odstup pod pracovnou plochou" if _k == 1 else f"Medzera medzi policou {_k - 1} a {_k}") for _k in range(1, 11)},
    "help_shelfh": "Odstup sa meria od spodnej hrany pozdĺžnikov, ktoré podopierajú pracovnú plochu, k hornej ploche dosky najvyššej police. Ďalšie police sa nastavujú medzerou medzi policami (od hornej plochy dosky po spodok rámu police nad ňou). Kým nič nenastavíte, police sú rozložené rovnomerne.",
    "drawleft": "Zásuvky na ľavej strane (inak vpravo)",
    "petleg": "Držiak na PET fľašu: na ktorej nohe", "petface": "Držiak na PET fľašu: na ktorej strane profilu",
    "petleg_fl": "Predná ľavá", "petleg_fr": "Predná pravá", "petleg_rl": "Zadná ľavá", "petleg_rr": "Zadná pravá", "petleg_fm": "Predná stredná", "petleg_rm": "Zadná stredná",
    "petface_right": "Vpravo", "petface_left": "Vľavo", "petface_front": "Vpredu", "petface_back": "Vzadu",
    "ledlight": "LED svietidlo (bez neho ostanú ramená a profily)",
    "petpos": "Výška držiaka PET fľaše na nohe",
    "posts": "Zadné stojky (zvislé profily nahor)",
    "shelf": "Počet dolných políc",
    "wheels": "Kolieska",
    "panels": "Perforované panely na náradie",
    "led": "LED osvetlenie",
    "drawers": "Oceľové zásuvky",
    "socket": "Napájacia lišta so zásuvkami",
    "pet": "Držiak na PET fľašu",
    "help_mid": "Nad šírku {prah} mm pribudne predná aj zadná stredná noha. Posuňte ju bližšie k ľavej alebo pravej nohe.",
    "help_box": "Zásuvkový blok možno posúvať po šírke stola; voľba „Zásuvky na ľavej strane“ ho zrkadlovo prehodí a posun sa potom meria od ľavej nohy.",
    "help_petpos": "Držiak na PET fľašu sa posúva po nohe nahor a nadol; hranice dáva dĺžka nohy a okolité diely (napr. zásuvky vľavo vyžadujú držiak nižšie).",
    "help_shelf": "Police sa rozložia rovnomerne po výške, medzi nimi zostane vždy aspoň 100 mm voľného miesta. Počet je obmedzený výškou stola a zásuvkami.",
    "shelfboard": "Dosky na spodných policiach",
    "help_shelfboard": "Bez dosiek ostane z každej spodnej police len rám z profilov (bez dosky a bez podpier pod ňou). Platí pre všetky spodné police.",
    "drawercount": "Počet zásuviek v boxe",
    "help_drawercount": "Oceľový zásuvkový box má 1, 2 alebo 3 zásuvky (vonkajšia výška 180 / 280 / 450 mm, visí pod pracovnou doskou). Vyšší box potrebuje vyšší stôl alebo nižšiu policu; ak sa nezmestí, počet sa zníži.",
    "bad_combo": "Túto kombináciu nie je možné vyrobiť.",
    "g_cuts": "Výrezy v pracovnej doske",
    "help_cuts": "Výrez môže mať ľubovoľnú veľkosť a polohu. Od okraja dosky zostane aspoň 30 mm a medzi dvoma výrezmi aspoň 30 mm.",
    "g_bearings": "Ložiskové jednotky na doske",
    "bearings": "Ložiskové jednotky (guľôčkové)",
    "bearpitch": "Rozstup jednotiek",
    "bearedge": "Vzdialenosť jednotiek od okraja dosky",
    "help_bearings": "Zadajte rozstup jednotiek a ich vzdialenosť od okraja dosky – počet z toho vyplynie. V mieste výrezu sa jednotky vynechajú.",
    "cut1": "Výrez 1",
    "cut1w": "Šírka výrezu 1 (pozdĺž stola)",
    "cut1d": "Hĺbka výrezu 1 (spredu dozadu)",
    "cut1x": "Vzdialenosť výrezu 1 od predného okraja",
    "cut1z": "Vzdialenosť výrezu 1 od ľavého okraja",
    "cut1shelf": "Polica pod výrezom 1",
    "cut2": "Výrez 2",
    "cut2w": "Šírka výrezu 2 (pozdĺž stola)",
    "cut2d": "Hĺbka výrezu 2 (spredu dozadu)",
    "cut2x": "Vzdialenosť výrezu 2 od predného okraja",
    "cut2z": "Vzdialenosť výrezu 2 od ľavého okraja",
    "cut2shelf": "Polica pod výrezom 2",
    "cut3": "Výrez 3",
    "cut3w": "Šírka výrezu 3 (pozdĺž stola)",
    "cut3d": "Hĺbka výrezu 3 (spredu dozadu)",
    "cut3x": "Vzdialenosť výrezu 3 od predného okraja",
    "cut3z": "Vzdialenosť výrezu 3 od ľavého okraja",
    "cut3shelf": "Polica pod výrezom 3",
    "feet": "Nastaviteľné nožičky (namiesto záslepiek)",
    "braces": "Šikmé vzpery ramien LED (podopretie)",
    "bracelen": "Dĺžka vzpery",
    "help_braces": "Šikmé vzpery pod ramenami LED slúžia ako stabilizácia pri zaťažení: tyč zvolenej dĺžky so šikmými koncovkami na oboch koncoch, medzi zadnou stojkou a ramenom. Dĺžku vzpery určuje dĺžka tyče.",
    "panelcount": "Počet panelov", "panelpos": "Výška panelov (posun po zadných stojkách)", "panelside": "Panely do strán (posun medzi nohami)", "midsupport": "Stredná opora pri širokom stole",
    "midsupport_auto": "Automaticky", "midsupport_legs": "Stredné nohy", "midsupport_frame": "Vstavaný rám", "posth": "Výška zadných stojok nad doskou",
    "socketup": "Napájacia lišta: posun nahor", "socketside": "Napájacia lišta: posun do strán",
    "help_panelcount": "Panel sedí medzi zadnými stojkami, nad ním a pod ním je profil (medzera 1 mm). Ďalšie panely sa pridávajú po jednom kuse: vedľa seba, kde to šírka dovolí (medzi nimi je plná stredná noha), inak ďalší rad nad ním.",
    "help_panelpos": "Panely s profilmi nad a pod nimi (a napájacia lišta) sa posúvajú po zadných stojkách; dole leží spodný profil na zadnej priečke rámu dosky.",
    "help_panelside": "Ak majú panely medzi nohami medzeru, dajú sa posúvať do strán (spolu s napájacou lištou); od nohy vždy zostane aspoň 1 mm. Kladná hodnota = doprava, 0 = uprostred.",
    "help_midsupport": "Pri širokom stole sú buď stredné nohy, alebo vstavaný rám medzi pozdĺžnikmi (pozdĺžniky zostanú celé; len so spodnou policou). Automaticky: nohy, rám len ak by sa panel inak nezmestil.",
    "help_posth": "Zadné stojky možno skracovať aj predlžovať; rameno LED sa posúva s nimi. Panely potrebujú stojky aspoň tak vysoké, aby sa pod rameno LED zmestili.",
    "help_socket": "Napájacia lišta sa vždy dotýka panela alebo profilu; možno ju posúvať nahor a nadol aj do strán, hranice určujú okolité diely.",
}
_SK_DUVODY = {
    "panels": "Ani najkratší perforovaný panel (1190 mm) sa sem nezmestí – potrebuje voľné miesto medzi zadnými stojkami a dosť vysoké stojky.",
    "socketup": "Napájacia lišta sa musí dotýkať panela alebo profilu a zmestiť sa na stôl – posuňte ju späť (výška / do strán).",
    "socketside": "Napájacia lišta sa musí dotýkať panela alebo profilu a zmestiť sa na stôl – posuňte ju späť (výška / do strán).",
    "led": "LED osvetlenie (1,2 m) sa na túto šírku stola nezmestí – potrebuje šírku aspoň 1200 mm.",
    "drawers": "Zásuvky sa pri týchto rozmeroch nezmestia (potrebujú hĺbku aspoň 620 mm, šírku aspoň 700 mm a dostatočnú výšku dosky).",
    "socket": "Napájacia lišta sa montuje na perforovaný panel – bez panelov ju nie je možné zvoliť.",
    "wheels": "Kolieska sa pri tejto výške stola nezmestia.",
    "pet": "Držiak na PET fľašu sa pri tejto výške nezmestí.",
    "shelf": "Dolná polica sa pri tejto výške nezmestí.",
    "shelfboard": "Voľba platí len so spodnou policou.",
    "posts": "Zadné stojky nemožno vypnúť, kým sú zapnuté panely, LED alebo napájacia lišta.",
    None: "Túto kombináciu rozmerov nie je možné vyrobiť.",
    "cut1": "Výrezy sa prekrývajú alebo sú bližšie ako 30 mm od seba – posuňte ich, zmenšite ich, alebo jeden z nich odstráňte.",
    "cut1shelf": "Polica pod výrezom sa pri týchto rozmeroch alebo polohe nezmestí – narazila by na nohu, zásuvky alebo iný diel, prípadne je stôl príliš nízky. Posuňte výrez, zmenšite ho, alebo policu odstráňte.",
    "cut1shelfoff": "Najprv zapnite výrez – polica sa montuje priamo pod neho.",
    "cut2": "Výrezy sa prekrývajú alebo sú bližšie ako 30 mm od seba – posuňte ich, zmenšite ich, alebo jeden z nich odstráňte.",
    "cut2shelf": "Polica pod výrezom sa pri týchto rozmeroch alebo polohe nezmestí – narazila by na nohu, zásuvky alebo iný diel, prípadne je stôl príliš nízky. Posuňte výrez, zmenšite ho, alebo policu odstráňte.",
    "cut2shelfoff": "Najprv zapnite výrez – polica sa montuje priamo pod neho.",
    "cut3": "Výrezy sa prekrývajú alebo sú bližšie ako 30 mm od seba – posuňte ich, zmenšite ich, alebo jeden z nich odstráňte.",
    "cut3shelf": "Polica pod výrezom sa pri týchto rozmeroch alebo polohe nezmestí – narazila by na nohu, zásuvky alebo iný diel, prípadne je stôl príliš nízky. Posuňte výrez, zmenšite ho, alebo policu odstráňte.",
    "cut3shelfoff": "Najprv zapnite výrez – polica sa montuje priamo pod neho.",
    "bearpitch": "Príliš veľa ložiskových jednotiek (najviac 500 ks) – zväčšite rozstup alebo vzdialenosť od okraja.",
    "bearings": "Príliš veľa ložiskových jednotiek (najviac 500 ks) – zväčšite rozstup alebo vzdialenosť od okraja.",
    "feet": "Nastaviteľné nožičky sa dajú použiť len pri stole bez koliesok a pri príliš nízkom stole sa nezmestia.",
    "braces": "Šikmé vzpery sa pri týchto rozmeroch nezmestia – potrebujú zadné stojky, LED osvetlenie, voľné miesto pred stojkami a dostatočne dlhé rameno LED.",
}
TEXTY["sk"] = _SK_TEXTY
TEXTY["sk"].update({"panellen": "Dĺžka panela", "panellen_1190": "1190 mm", "panellen_1481": "1481 mm", "panellen_1671": "1671 mm", "panellen_1975": "1975 mm",
                    "help_panellen": "Perforované panely sú v niekoľkých dĺžkach; všetky panely stola majú rovnakú dĺžku. Dlhší panel potrebuje širší stôl – dĺžka, ktorá sa nezmestí, je v ponuke zašednutá, "
                                     "a keď sa stôl zúži, dĺžka sa sama zníži na najdlhšiu, ktorá sa zmestí."})
DUVODY["sk"] = _SK_DUVODY
# NAVLEK NOHOU (bot10, 2026-10-05; Robert: jekl 40x40, stena 2 mm, delka 200-400 mm, misto koleček / zaslepek / patek, nohy v nem aspon 70 mm, v urovni navleku zadny jiny komponent) - jen system 35.
# Zakaznicke texty ke kontrole bot7 (slovenske pojmenovani jeklu: "jakl").
TEXTY["cs"].update({"sleeve": "Návlek nohou (jekl 40×40×2) – mechanická výška", "sleevelen": "Délka návleku",
                    "help_sleeve": "Na spodek každé nohy se místo koleček, záslepek a patek nasadí jekl 40×40 se stěnou 2 mm a záslepkou dole (barva RAL 7016, lesk); noha v něm zajíždí nejméně 70 mm, takže výšku stolu lze mechanicky měnit. "
                                   "Délka návleku je 200 až 400 mm. V úrovni návleku nesmí být žádný jiný komponent, proto jsou police nad ním."})
TEXTY["en"].update({"sleeve": "Leg sleeves (40×40×2 steel box section) – mechanical height", "sleevelen": "Sleeve length",
                    "help_sleeve": "A 40×40 steel box-section sleeve with a 2 mm wall and an end cap at the bottom (colour RAL 7016, gloss) is put on the foot of every leg instead of castors, end caps or feet; the leg goes into it at least 70 mm, "
                                   "so the height of the table can be changed mechanically. The sleeve is 200 to 400 mm long. No other component can be at the level of the sleeve, so the shelves are above it."})
TEXTY["sk"].update({"sleeve": "Návleky nôh (jakl 40×40×2) – mechanická výška", "sleevelen": "Dĺžka návleku",
                    "help_sleeve": "Na spodok každej nohy sa namiesto koliesok, záslepiek a nožičiek nasadí jakl 40×40 so stenou 2 mm a záslepkou dole (farba RAL 7016, lesk); noha v ňom zasahuje najmenej 70 mm, takže výšku stola možno mechanicky meniť. "
                                   "Dĺžka návleku je 200 až 400 mm. V úrovni návleku nesmie byť žiadny iný komponent, preto sú police nad ním."})
DUVODY["cs"].update({"sleeve": "Návlek se při této výšce stolu nevejde – nad jeho horním koncem musí zůstat volné místo a pak spodek rámu (u stolu s policí i police).",
                     "sleeve_nahrazuje": "Návlek nahrazuje kolečka, záslepky i patky – nejdřív ho vypněte.",
                     "sleeve_kolize": "V úrovni návleku nesmí být žádný jiný komponent (police, držák PET lahve, šuplíky…) – zkraťte návlek, zvyšte stůl nebo komponent přesuňte výš.",
                     "sleeve_orezano": "Délka návleku snížena na {v} mm – delší se pod stůl této výšky nevejde."})
DUVODY["en"].update({"sleeve": "The sleeve does not fit this table height – there must be free space above its top end and then the underside of the frame (and of the shelf if there is one).",
                     "sleeve_nahrazuje": "The sleeves replace the castors, end caps and feet – switch them off first.",
                     "sleeve_kolize": "No other component can be at the level of the sleeve (shelf, PET bottle holder, drawers…) – shorten the sleeve, make the table taller or move the component higher.",
                     "sleeve_orezano": "Sleeve length reduced to {v} mm – a longer one does not fit under a table of this height."})
DUVODY["sk"].update({"sleeve": "Návlek sa pri tejto výške stola nezmestí – nad jeho horným koncom musí zostať voľné miesto a potom spodok rámu (pri stole s policou aj polica).",
                     "sleeve_nahrazuje": "Návleky nahrádzajú kolieska, záslepky aj nožičky – najprv ich vypnite.",
                     "sleeve_kolize": "V úrovni návleku nesmie byť žiadny iný komponent (polica, držiak na PET fľašu, zásuvky…) – skráťte návlek, zvýšte stôl alebo komponent presuňte vyššie.",
                     "sleeve_orezano": "Dĺžka návleku znížená na {v} mm – dlhší sa pod stôl tejto výšky nezmestí."})
POTREBUJE_STOJKY["sk"] = "Potrebuje zadné stojky – najprv ich zapnite."
NAZVY_SLOTU["sk"] = {"drawers": "zásuvky", "panels": "panely", "led": "LED osvetlenie", "socket": "napájacia lišta", "pet": "držiak na PET fľašu",
                     "wheels": "kolieska", "feet": "nastaviteľné nožičky", "braces": "šikmé vzpery ramien LED", "sleeve": "návleky nôh"}
for _n, _tg, _par, _sl in VYREZY:
    NAZVY_SLOTU["sk"][_tg] = f"výrez {_n}"
    NAZVY_SLOTU["sk"][f"{_tg}shelf"] = f"polica pod výrezom {_n}"
TEXTY_AKCI["sk"] = {"odebrano": "Automaticky odstránené: ", "odebrat": "Odstrániť: ", "roztahnout_w": "Rozšíriť stôl na šírku {v} mm a zapnúť",
                    "roztahnout_d": "Zväčšiť hĺbku stola na {v} mm a zapnúť", "roztahnout_h": "Zvýšiť zadné stojky na {v} mm a zapnúť"}


# HORNI POLICE MEZI ZADNIMI STOJKAMI (Robert 2026-10-07; api/stul_hpolice.py): texty cs / en / sk (dalsi jazyky z api/jazyky; chybejici klic = anglicky)
TEXTY["cs"].update({
    "upshelf": "Police mezi zadními stojkami", "upshelftype": "Typ police", "upshelfboard": "Deska police", "upshelfpos": "Výška police nad deskou stolu", "upshelfdepth": "Hloubka police",
    "upshelftype_flat": "Rovná, deska na rámu", "upshelftype_frame": "Rámová, bez desky", "upshelftype_groove": "Rám s deskou v drážce", "upshelftype_lip": "S lemem na přední hraně",
    "upshelftype_dividers": "Rám s přepážkami z překližky",
    "upshelfboard_lam18": "Laminodeska 18 mm", "upshelfboard_lam12": "Laminodeska 12 mm", "upshelfboard_mdf8": "MDF 8 mm (do drážky)", "upshelfboard_pr10": "Překližka 10 mm (do drážky)",
    "help_upshelf": "Police se montuje mezi zadní stojky: rám z profilů (zadní a přední příčka, boční profily a u širších polic střední) a deska shora na rámu, nebo v drážce profilů. Rám s přepážkami má "
                    "podlahu v drážce a svislé přepážky z překližky 10 mm na úhelnících; lem je pás z překližky na přední hraně. Výchozí výška je nad panely."})
TEXTY["en"].update({
    "upshelf": "Shelf between the rear uprights", "upshelftype": "Shelf type", "upshelfboard": "Shelf board", "upshelfpos": "Shelf height above the worktop", "upshelfdepth": "Shelf depth",
    "upshelftype_flat": "Flat, board on the frame", "upshelftype_frame": "Frame only, no board", "upshelftype_groove": "Frame with a board in the slot", "upshelftype_lip": "With a lip on the front edge",
    "upshelftype_dividers": "Frame with plywood dividers",
    "upshelfboard_lam18": "Laminated chipboard 18 mm", "upshelfboard_lam12": "Laminated chipboard 12 mm", "upshelfboard_mdf8": "MDF 8 mm (in the slot)", "upshelfboard_pr10": "Plywood 10 mm (in the slot)",
    "help_upshelf": "The shelf is mounted between the rear uprights: a frame of profiles (rear and front cross-member, side profiles and, for wider shelves, centre profiles) and a board on top of the frame "
                    "or in the slot of the profiles. The frame with dividers has the floor in the slot and vertical 10 mm plywood dividers on angle brackets; the lip is a plywood strip on the front edge. "
                    "The default height is above the panels."})
TEXTY["sk"].update({
    "upshelf": "Polica medzi zadnými stojkami", "upshelftype": "Typ police", "upshelfboard": "Doska police", "upshelfpos": "Výška police nad doskou stola", "upshelfdepth": "Hĺbka police",
    "upshelftype_flat": "Rovná, doska na ráme", "upshelftype_frame": "Rámová, bez dosky", "upshelftype_groove": "Rám s doskou v drážke", "upshelftype_lip": "S lemom na prednej hrane",
    "upshelftype_dividers": "Rám s priehradkami z preglejky",
    "upshelfboard_lam18": "Laminovaná drevotrieska 18 mm", "upshelfboard_lam12": "Laminovaná drevotrieska 12 mm", "upshelfboard_mdf8": "MDF 8 mm (do drážky)", "upshelfboard_pr10": "Preglejka 10 mm (do drážky)",
    "help_upshelf": "Polica sa montuje medzi zadné stojky: rám z profilov (zadná a predná priečka, bočné profily a pri širších policiach stredné) a doska zhora na ráme, alebo v drážke profilov. Rám "
                    "s priehradkami má podlahu v drážke a zvislé priehradky z preglejky 10 mm na uholníkoch; lem je pás z preglejky na prednej hrane. Predvolená výška je nad panelmi."})
DUVODY["cs"].update({"upshelf": "Police mezi zadními stojkami se sem nevejde – potřebuje zadní stojky a místo mezi panely (nebo deskou) a ramenem LED; zvyšte stojky, snižte počet panelů, nebo ji vypněte.",
                     "upshelf_deska_ram": "Rámová police nemá desku.", "upshelf_deska_drazka": "Do drážky jde jen deska {d}.", "upshelf_deska_shora": "Deska do drážky jde jen u rámu s deskou v drážce a s přepážkami.",
                     "upshelf_deska_nabidka": "Tahle deska teď není v nabídce.", "upshelf_typ_nabidka": "Tahle varianta police teď není v nabídce.",
                     "upshelf_typ_nevejde": "Tenhle typ police se sem nevejde – nad rámem potřebuje víc volného místa (zvyšte zadní stojky nebo snižte počet panelů)."})
DUVODY["en"].update({"upshelf": "The shelf between the rear uprights does not fit here – it needs the rear uprights and space between the panels (or the worktop) and the LED arm; raise the uprights, reduce the panels or switch it off.",
                     "upshelf_deska_ram": "A frame-only shelf has no board.", "upshelf_deska_drazka": "Only the {d} board goes into the slot.", "upshelf_deska_shora": "A board in the slot is only for the frame with a board in the slot and the frame with dividers.",
                     "upshelf_deska_nabidka": "This board is not available at the moment.", "upshelf_typ_nabidka": "This shelf variant is not available at the moment.",
                     "upshelf_typ_nevejde": "This shelf type does not fit here – it needs more free room above the frame (raise the rear uprights or reduce the panels)."})
DUVODY["sk"].update({"upshelf": "Polica medzi zadnými stojkami sa sem nezmestí – potrebuje zadné stojky a miesto medzi panelmi (alebo doskou) a ramenom LED; zvýšte stojky, znížte počet panelov, alebo ju vypnite.",
                     "upshelf_deska_ram": "Rámová polica nemá dosku.", "upshelf_deska_drazka": "Do drážky ide len doska {d}.", "upshelf_deska_shora": "Doska do drážky ide len pri ráme s doskou v drážke a s priehradkami.",
                     "upshelf_deska_nabidka": "Táto doska teraz nie je v ponuke.", "upshelf_typ_nabidka": "Táto varianta police teraz nie je v ponuke.",
                     "upshelf_typ_nevejde": "Tento typ police sa sem nezmestí – nad rámom potrebuje viac voľného miesta (zvýšte zadné stojky alebo znížte počet panelov)."})
VOLBA_NA_SLOT["hpolice"] = "upshelf"
NAZVY_SLOTU["cs"]["upshelf"], NAZVY_SLOTU["en"]["upshelf"], NAZVY_SLOTU["sk"]["upshelf"] = "polici mezi zadními stojkami", "the shelf between the rear uprights", "policu medzi zadnými stojkami"
UPSHELF_NAZVY_DESEK = {"lam18": "laminodeska 18 mm", "lam12": "laminodeska 12 mm", "mdf8": "MDF 8 mm", "pr10": "překližka 10 mm"}


# SIKMA POLICE NA BOXY (2. kolo, bot8 2026-10-08): slot sklonu `upshelftilt` (5-30 st. po 5, vychozi 15; jen u typu `slope`), texty cs / en / sk
TEXTY["cs"].update({"upshelftilt": "Sklon police (vpředu níž)", "upshelftype_slope": "Šikmá, na boxy (s lemem vpředu)"})
TEXTY["en"].update({"upshelftilt": "Shelf slope (lower at the front)", "upshelftype_slope": "Sloped, for boxes (with a front lip)"})
TEXTY["sk"].update({"upshelftilt": "Sklon police (vpredu nižšie)", "upshelftype_slope": "Šikmá, na boxy (s lemom vpredu)"})
TEXTY["cs"]["help_upshelf"] += " Šikmá police na boxy je skloněná dopředu dolů (výchozí sklon 15°), vpředu má lem proti sjetí boxů a drží ji dvě naklápěcí konzole na zadních stojkách; výška je výška zadního okraje desky."
TEXTY["en"]["help_upshelf"] += " The sloped shelf for boxes slopes down towards the front (default 15°), has a front lip so that boxes cannot slide off and is held by two tilting brackets on the rear uprights; the height is the height of the rear edge of the board."
TEXTY["sk"]["help_upshelf"] += " Šikmá polica na boxy je naklonená dopredu nadol (predvolený sklon 15°), vpredu má lem proti zošmyknutiu boxov a drží ju dve naklápacie konzoly na zadných stojkách; výška je výška zadnej hrany dosky."
DUVODY["cs"]["upshelf_typ_sekce"] = "Šikmá police zatím nejde u stolu se střední zadní nohou (na jednu stojku by se nevešly dvě konzole) – zvolte vestavěný rám, nebo jiný typ police."
DUVODY["en"]["upshelf_typ_sekce"] = "The sloped shelf is not available yet for a table with a rear centre leg (two brackets would not fit on one upright) – choose the built-in frame or another shelf type."
DUVODY["sk"]["upshelf_typ_sekce"] = "Šikmá polica zatiaľ nejde pri stole so strednou zadnou nohou (na jednu stojku by sa nezmestili dve konzoly) – zvoľte vstavaný rám, alebo iný typ police."


def _spocti(p, norm, lang, h, gen, delky=None, nab_hp=None):
    nab_hp = HP.nabidka(p["system"], None) if nab_hp is None else nab_hp                     # desky a typy horni police v nabidce (verejnost jen s aktivni kartou)
    delky = frozenset(S.PANEL_DELKY) if delky is None else delky                 # delky panelu v nabidce (verejnost jen s aktivni kartou)
    if p["system"] == S.SYSTEM_SSE:
        return _sse().spocti(p, norm, lang, h, gen)
    t = TEXTY[lang]
    pozad_panelu = norm.get("panelcount")                         # POZADOVANY pocet panelu (norm se nize prepise efektivnimi hodnotami)
    pozad_delka = norm.get("panellen")                            # POZADOVANA delka panelu (generator ji snizi, kdyz se zvolena nevejde)
    pozad_navlek = norm.get("sleevelen")                          # POZADOVANA delka navleku (generator ji na nizkem stole orizne)
    pozad_led = norm.get("ledcount")                              # POZADOVANY pocet svitidel LED (generator ho orizne na pocet, ktery se vejde)
    ta = TEXTY_AKCI[lang]
    for sid, par in _prepinace(p["system"]).items():
        norm[sid] = p[par]                                       # efektivni hodnoty (po automatickem odebrani)
    norm["shelf"] = p["police"]
    norm["boxpos"] = int(p["suplik_posun"]) if p["suplik"] else 0
    norm["petpos"] = int(p["pet_posun"]) if p["drzak_pet"] else 0
    norm["petleg"], norm["petface"] = PET_NOHA_VEREJNE[p["pet_noha"]], PET_STRANA_VEREJNE[p["pet_strana"]]
    for k in range(1, S.MAX_POLIC + 1):
        norm[f"sh{k}"] = None if (p[f"police_h{k}"] is None or k > p["police"]) else round(float(p[f"police_h{k}"]), 1)
    for n, tg, par, sl in VYREZY:                                # efektivni (orezane na desku) rozmery vyrezu
        norm[tg] = p[par]
        norm[f"{tg}shelf"] = bool(p[f"{par}_police"] and p[par])
        for sfx in ("w", "d", "x", "z"):
            norm[sl[sfx]] = int(round(p[f"{par}_{sfx}"]))
    norm["bearings"], norm["bearpitch"], norm["bearedge"] = p["loz"], int(p["loz_rozteca"]), int(p["loz_okraj"])
    norm["bracelen"] = int(p["vzpera_delka"])
    norm["drawercount"] = p["suplik_pocet"] if p["suplik"] else int(S.SUPLIK_POCET_VYCHOZI)                    # efektivni pocet supliku (po orezu, kdyz se vyssi box nevejde)
    if p["system"] in S.NAVLEK_SYSTEMY:
        norm["sleevelen"] = int(p["navlek_delka"])                                                                # efektivni delka navleku (po orezu)
    norm["panelcount"] = p["panely_pocet"] if p["panely"] else int(S.VYCHOZI["panely_pocet"])                  # efektivni panely, stredni opora, vyska stojek a posun elektrozlabu
    norm["panelpos"] = int(round(p["panely_posun"])) if p["panely"] else 0
    norm["panelside"] = int(round(p["panely_z"])) if p["panely"] else 0                                      # efektivni posun do stran (generator ho orizne podle mezery u noh)
    norm["ledlen"] = str(int(round(p["led_delka"]))) if (p["led"] and p["stojky"] and p["led_svetlo"]) else str(S.LED_DELKA_VYCHOZI)          # efektivni delka svitidla LED
    norm["panellen"] = str(int(round(p["panely_delka"]))) if p["panely"] else str(S.PANEL_DELKA_VYCHOZI)       # efektivni delka panelu (po snizeni, kdyz se zvolena nevejde)
    norm["ledcount"] = int(p["led_pocet"])                                                                       # efektivni pocet a polohy svitidel LED (generator je orizne; bez svitidla 1 / automaticky)
    for k in range(1, S.LED_MAX + 1):
        norm[f"ledpos{k}"] = _cele_nebo_none(p[f"led_z{k}"])
    norm["midsupport"] = MIDSUPPORT_VEREJNE[p["stredni_opora"]]
    norm["posth"] = round(float(p["stojky_vyska"]), 1)
    norm["socketup"], norm["socketside"] = (int(round(p["elzlab_y"])), int(round(p["elzlab_z"]))) if (p["elektrozlab"] and p["panely"]) else (0, 0)
    hp_inf = gen.get("hpolice_info")                                                                              # efektivni horni police (typ, deska, vyska, hloubka po orezu na meze)
    norm["upshelftype"], norm["upshelfboard"] = HP.TYP_VEREJNE[p["hpolice_typ"]], p["hpolice_deska"]
    norm["upshelfpos"] = _cele_nebo_none(p["hpolice_vyska"]) if p["hpolice"] else None
    norm["upshelfdepth"] = int(round(p["hpolice_hloubka"]))
    norm["upshelftilt"] = int(round(p["hpolice_sklon"])) if (p["hpolice"] and p["hpolice_typ"] == "sikma") else int(HP.SKLON_VYCHOZI)
    cena = stul_api.cena_konfigurace(gen["dily"], p["system"])
    cur = cena["bez_dph"] if cena else None
    errors = []
    videno = set()
    for pr in gen["problemy"]:
        slot = _slot_pro_problem(pr, gen["dily"], p, gen)
        if slot in videno:
            continue
        videno.add(slot)
        errors.append({"slot": slot, "message": DESKA_MIMO_TABULI[lang].format(t1=int(S.tabule()[0]), t2=int(S.tabule()[1])) if pr.get("kod") == "deska_mimo_tabuli" else PET_NOHA_NENI[lang] if pr.get("kod") == "pet_noha" else DUVODY[lang]["sleeve_kolize"] if pr.get("kod") == "navlek_kolize" else KOLIZE_PET[lang] if (slot in ("pet", "drawers") and p["drzak_pet"] and (p["suplik_vlevo"] or p["pet_posun"] or p["pet_noha"] != "PL" or p["pet_strana"] != "vpravo") and pr.get("kod") in ("zanoreni", "mimo_obrys")) else _duvod_slotu(lang, slot, p["system"], p["sirka"])})
    # co se samo odebralo (zmena rozmeru) a co se nabizi smazat (posun) - Robert
    notices = [{"slot": VOLBA_NA_SLOT[o["volba"]], "action": "removed",
                "message": ta["odebrano"] + NAZVY_SLOTU[lang][VOLBA_NA_SLOT[o["volba"]]] + " – " + _duvod_slotu(lang, VOLBA_NA_SLOT[o["volba"]], p["system"], p["sirka"])} for o in gen["odebrano"]]
    for inf in gen.get("info", []):                                  # informace o konstrukci (ne chyba, ne odebrani): action "info", slot = rozmer, kterym vznikla
        if inf["kod"] == "police_podpery":
            notices.append({"slot": "d", "action": "info", "message": text_podpery(lang, inf)})
        elif inf["kod"] == "deska_podpery" and inf["podpery"]:
            notices.append({"slot": "d", "action": "info", "message": text_podpery_desky(lang, inf)})
        elif inf["kod"] == "stredni_rada_noh":
            notices.append({"slot": "d", "action": "info", "message": text_stredni_rada(lang, inf)})
    pi = gen.get("panely_info") or {}
    if pi.get("rezim") == "ram" and p["stredni_opora"] == "auto":
        notices.append({"slot": "midsupport", "action": "info", "message": MIDSUPPORT_RAM_AUTO[lang]})
    if pi.get("rezim") in ("noha", "ram"):                           # stul nad prahem sirky: desky delene u stredni opory (formaty tabuli laminodesky)
        notices.append({"slot": "midsupport", "action": "info",
                        "message": text_desky_deleny(lang, pi["rezim"], S.SYSTEMY[p["system"]]["profil_mm"] + 2 * S.RAM_VULE_VYREZU, S.tabule())})
    if gen.get("suplik_orez"):                                       # pozadovany pocet supliku se snizil (vyssi box se nevejde)
        notices.append({"slot": "drawercount", "action": "info", "message": SUPLIKY_OREZANO[lang].format(n=int(gen["suplik_orez"]["pocet"]))})
    if p["navlek"] and pozad_navlek and int(pozad_navlek) > int(p["navlek_delka"]):
        notices.append({"slot": "sleevelen", "action": "info", "message": DUVODY[lang]["sleeve_orezano"].format(v=int(p["navlek_delka"]))})
    if p["panely"] and pozad_panelu and pi.get("pocet") and int(pozad_panelu) > int(pi["pocet"]):
        notices.append({"slot": "panelcount", "action": "info", "message": PANELY_OREZANO[lang].format(n=int(pi["pocet"]))})
    if p["panely"] and pozad_delka and int(pozad_delka) > int(round(p["panely_delka"])):
        notices.append({"slot": "panellen", "action": "info", "message": PANELY_ZKRACENO[lang].format(l=int(round(p["panely_delka"])))})
    if p["led"] and p["stojky"] and p["led_svetlo"] and pozad_led and int(pozad_led) > int(p["led_pocet"]):
        notices.append({"slot": "ledcount", "action": "info", "message": LEDPOCET_OREZANO[lang].format(n=int(p["led_pocet"]))})
    offers = [{"slot": VOLBA_NA_SLOT[o["volba"]], "action": "remove", "label": ta["odebrat"] + NAZVY_SLOTU[lang][VOLBA_NA_SLOT[o["volba"]]],
               "message": KOLIZE_PET[lang] if (o["volba"] in ("drzak_pet", "suplik") and p["drzak_pet"] and (p["suplik_vlevo"] or p["pet_posun"] or p["pet_noha"] != "PL" or p["pet_strana"] != "vpravo")) else _duvod_slotu(lang, VOLBA_NA_SLOT[o["volba"]], p["system"], p["sirka"])} for o in gen["nabidky_odebrani"]]
    options = {}
    roztazeni = S.nabidky_roztazeni(**p)
    for sid, par in _prepinace(p["system"]).items():
        if par == "vzpery" and not S.SYSTEMY[p["system"]]["vzpery"]:                    # system bez sikmych vzper: slot neni ve schematu, jen zakazana volba s duvodem
            options[sid] = {"on": {"price_delta": 0, "disabled": True, "reason": VZPERY_NENI[lang]}}
            continue
        delta, duvod, suggest = 0, None, None
        if not p[par]:
            alt_gen = S.sestav_stul(**{**p, par: True})            # co by se stalo po zapnuti (cena + zda by se zase odebralo)
            if not alt_gen["parametry"][par]:
                duvod = (POTREBUJE_STOJKY[lang] if (par in ("panely", "led", "elektrozlab", "hpolice") and not p["stojky"]) else _duvod_slotu(lang, sid, p["system"], p["sirka"]))
            if par in ("kolecka", "patky") and p["navlek"]:
                duvod = DUVODY[lang]["sleeve_nahrazuje"]                                  # navlek nahrazuje kolecka, zaslepky i patky (zapnout je jde az po vypnuti navleku)
            alt = stul_api.cena_konfigurace(alt_gen["dily"], p["system"])
            delta = (alt["bez_dph"] - cur) if (alt and cur is not None) else 0
            nab = roztazeni.get(par) if duvod else None
            if nab and ("sirka" in nab or "hloubka" in nab or "stojky_vyska" in nab):               # nabidka muze nest jen "vypnout" (vzpery bez panelu) - to verejne API zatim nenabizi
                suggest = {"w": nab["sirka"]} if "sirka" in nab else ({"d": nab["hloubka"]} if "hloubka" in nab else {"posth": nab["stojky_vyska"]})
        if par == "led" and duvod and p["stojky"] and not p[par]:                       # LED se v pozadovane delce nevejde: nabidka KRATSIHO svitidla, ktere se vejde (misto roztazeni stolu)
            kr_led = _led_kratsi(p, led_delky_pro_pozadavek())
            if kr_led:
                suggest = {"ledlen": str(kr_led)}
        on = {"price_delta": delta, "disabled": bool(duvod), "reason": duvod}
        if suggest:
            on["suggest"] = suggest
            on["suggest_label"] = (ta["roztahnout_w"].format(v=suggest["w"]) if "w" in suggest else (ta["roztahnout_d"].format(v=suggest["d"]) if "d" in suggest else (ta["roztahnout_h"].format(v=suggest["posth"]) if "posth" in suggest else ta["led_kratsi"].format(v=suggest["ledlen"]))))
        options[sid] = {"on": on}
    if p["police"] < 1:
        options["shelfboard"]["hidden"] = True                    # bez spodnich polic volba 'bez desky' neexistuje (slot se nevykresli, hodnotu server ignoruje - viz normalizuj)
    for sid, par in SLIDERY.items():
        lo, hi = S._rozsahy(p["system"])[par]                  # meze podle SYSTEMU (system 45: hloubka az 2500 mm; globalni ROZSAH by ji orezal na 1500 - nalez bot16 2026-10-08)
        if sid == "arm":
            options[sid] = {"min": int(lo), "max": int(hi)} if (p["led"] and p["stojky"]) else {"min": 560, "max": 560}
            continue
        options[sid] = {"min": int(lo), "max": int(hi)}          # mimo rozsah pomuze automaticke odebrani prislusenstvi, ne omezeni posuvniku
    # posuvnik 1-3 vzdy (vyssi box, ktery se nevejde, se snizi a hlasi to oznameni `drawercount` - zakaznik se dozvi PROC; nejvyssi pocet nezamykame, jako by posuvnik nefungoval)
    options["drawercount"] = ({"min": S.SUPLIK_POCTY[0], "max": S.SUPLIK_POCTY[-1], "value": int(p["suplik_pocet"])} if p["suplik"]
                              else {"min": S.SUPLIK_POCET_VYCHOZI, "max": S.SUPLIK_POCET_VYCHOZI})
    if p["sirka"] > S.prah_sirky(p["system"]):
        mn, mx = _mid_meze_pct(p["sirka"], p["system"])
        options["mid"] = {"min": mn, "max": mx}
    else:
        options["mid"] = {"min": 50, "max": 50}
    sirka_d, hloubka_d = p["sirka"], (p["hloubka"] + p["presah"] - 30.0 - S.SYSTEMY[p["system"]]["deska_zkraceni"]
                                      + S.deska_zadni_pokracovani(S.SYSTEMY[p["system"]], p["stojky"]))                    # rozmery pracovni desky (bez zadnich stojek pokracuje dozadu)
    for n, tg, par, sl in VYREZY:
        vyrez_delta = 0                                                                  # otvor cenu nemeni (deska se ridi jako cela), pokud Robert v generatoru nestanovil cenu za vyrez (pravidlo cena_vyrez)
        if not p[par] and S.pravidlo("cena_vyrez", p["system"]):
            alt_v = stul_api.cena_konfigurace(S.sestav_stul(**{**p, par: True})["dily"], p["system"])
            vyrez_delta = (alt_v["bez_dph"] - cur) if (alt_v and cur is not None) else 0
        options[tg] = {"on": {"price_delta": vyrez_delta, "disabled": False, "reason": None}}
        if p[par]:
            mez = {"w": (S.VYREZ_MIN, sirka_d - 2 * S.VYREZ_OKRAJ), "d": (S.VYREZ_MIN, hloubka_d - 2 * S.VYREZ_OKRAJ),
                   "x": (S.VYREZ_OKRAJ, hloubka_d - S.VYREZ_OKRAJ - p[f"{par}_d"]), "z": (S.VYREZ_OKRAJ, sirka_d - S.VYREZ_OKRAJ - p[f"{par}_w"])}
        else:
            mez = {sfx: (p[f"{par}_{sfx}"], p[f"{par}_{sfx}"]) for sfx in ("w", "d", "x", "z")}   # vypnuty vyrez: posuvniky zamcene (min = max)
        for sfx in ("w", "d", "x", "z"):
            options[sl[sfx]] = {"min": int(round(mez[sfx][0])), "max": int(round(mez[sfx][1]))}
        # police pod vyrezem: bez zapnuteho vyrezu nelze; cena podle skutecneho rozdilu; kolize hlasi errors/offers po zapnuti (ne zakaz)
        pol = {"price_delta": 0, "disabled": False, "reason": None}
        if not p[par]:
            pol.update(disabled=True, reason=DUVODY[lang][f"{tg}shelfoff"])
        elif not p[f"{par}_police"]:
            alt_pol = S.sestav_stul(**{**p, f"{par}_police": True})
            alt_c = stul_api.cena_konfigurace(alt_pol["dily"], p["system"])
            pol["price_delta"] = (alt_c["bez_dph"] - cur) if (alt_c and cur is not None) else 0
        options[f"{tg}shelf"] = {"on": pol}
    # loziskove jednotky: toggle (cena = skutecny rozdil), pocet jednotek (options.bearings.count), posuvniky zamcene, kdyz jsou vypnute
    loz_on = {"price_delta": 0, "disabled": False, "reason": None}
    loz_gen = gen["loz"]
    if not p["loz"]:
        alt_loz = S.sestav_stul(**{**p, "loz": True})
        alt_c = stul_api.cena_konfigurace(alt_loz["dily"], p["system"])
        loz_on["price_delta"] = (alt_c["bez_dph"] - cur) if (alt_c and cur is not None) else 0
        loz_gen = alt_loz["loz"]                                  # kolik jednotek by pribylo pri zapnuti
    options["bearings"] = {"on": loz_on, "count": {"placed": int(loz_gen["pocet"]) if loz_gen else 0, "omitted": int(loz_gen["vynechano"]) if loz_gen else 0}}
    if p["loz"]:
        options["bearpitch"] = {"min": int(S.ROZSAH["loz_rozteca"][0]), "max": int(S.ROZSAH["loz_rozteca"][1])}
        options["bearedge"] = {"min": LOZ_OKRAJ_MIN, "max": int(S.ROZSAH["loz_okraj"][1])}
    else:
        options["bearpitch"] = {"min": int(p["loz_rozteca"]), "max": int(p["loz_rozteca"])}
        options["bearedge"] = {"min": int(p["loz_okraj"]), "max": int(p["loz_okraj"])}
    vm = S.vzpera_meze(**p) if p["vzpery"] else None             # PRESNE meze delky vzpery (rameno LED, vyska stojky, okoli) - horni mez neni pevna 1000 mm
    gen["vzpera_meze"] = vm
    options["bracelen"] = ({"min": int(vm["min"]), "max": int(vm["max"])} if vm else {"min": int(p["vzpera_delka"]), "max": int(p["vzpera_delka"])})      # vypnute vzpery: posuvnik zamcen
    nm_ = gen.get("navlek_meze")                                  # PRESNE meze delky navleku: nejvic podle vysky stolu (horni konec jeklu + 3 mm pod spodkem ramu / nejnizsi police)
    if p["system"] in S.NAVLEK_SYSTEMY:
        options["sleevelen"] = ({"min": int(nm_["min"]), "max": int(nm_["max"]), "value": int(round(nm_["hodnota"])), "fits": bool(nm_["vejde"])} if (p["navlek"] and nm_)
                                else {"min": int(p["navlek_delka"]), "max": int(p["navlek_delka"])})
    options["shelf"] = {"min": 0, "max": int(gen["max_polic"])}
    sm = gen.get("suplik_meze")
    # PRESNE meze posunu supliku z generatoru (odstup aspon 30 mm od kazde nohy, krajni i stredni); value = skutecny posun boxu (u uzkeho stolu s automatickym posunem
    # se lisi od vyberu 0), fits = box se vubec vejde (jinak min = max)
    options["boxpos"] = ({"min": int(sm["min"]), "max": int(sm["max"]), "value": int(round(sm["hodnota"])), "fits": bool(sm["vejde"])} if (p["suplik"] and sm) else {"min": 0, "max": 0})
    pol_m = gen.get("police_meze") or {}
    for k in range(1, S.MAX_POLIC + 1):
        if k <= (pol_m.get("n") or 0):
            options[f"sh{k}"] = {"min": pol_m["min"][k - 1], "max": pol_m["max"][k - 1], "value": round(pol_m["hodnoty"][k - 1], 1), "auto": bool(pol_m["auto"][k - 1]), "fits": bool(pol_m["ok"])}
        else:
            options[f"sh{k}"] = {"min": 0, "max": 0, "hidden": True}              # police tohoto cisla neni: jezdec se neukazuje
    if p["panely"] and pi.get("pocet"):                                    # panely: pocet po jednom kuse (max podle sirky/stojek/opory), posun po stojkach
        options["panelcount"] = {"min": 1, "max": max(1, int(pi["max"])), "value": int(pi["pocet"])}
        options["panelpos"] = {"min": 0, "max": int(math.floor(pi["posun_max"] / 10.0 + 1e-9) * 10), "value": int(round(p["panely_posun"]))}
        pz_ = pi.get("posun_z") or {"min": 0.0, "max": 0.0}                                                   # panely do stran: jen kdyz maji mezi nohama mezeru (jinak jezdec nema rozsah)
        options["panelside"] = {"min": int(pz_["min"]), "max": int(pz_["max"]), "value": int(round(p["panely_z"]))}
    else:
        options["panelcount"] = {"min": 1, "max": 1}
        options["panelpos"] = {"min": 0, "max": 0}
        options["panelside"] = {"min": 0, "max": 0}
    # delka panelu: bez panelu nic; verejnosti zatim jen 1190 (karty novych delek neaktivni) = volba se nevykresli (hidden); jinak delky mimo nabidku a ty, ktere se mezi stojky nevejdou, jsou zakazane s duvodem
    if not (p["panely"] and pi.get("pocet")):
        options["panellen"] = {}
    elif len(delky) < 2:
        options["panellen"] = {"hidden": True}
    else:
        options["panellen"] = {str(t_["delka"]): {"disabled": True, "reason": NENI_V_NABIDCE[lang] if t_["delka"] not in delky else _duvod_delky(lang, p, t_)}
                               for t_ in (pi.get("typy") or []) if t_["delka"] not in delky or not t_["vejde"]}
    # delka svitidla LED: bez svitidla nic; verejnosti zatim jen 1200 (karta LED 600 neaktivni) = volba se nevykresli (hidden); jinak delky mimo nabidku a ty, ktere se na tento stul nevejdou, jsou zakazane s duvodem
    led_delky = led_delky_pro_pozadavek()
    li_ = gen.get("led_info") or {}
    if not (p["led"] and p["stojky"] and p["led_svetlo"] and li_.get("typy")):
        options["ledlen"] = {}
    elif len(led_delky) < 2:
        options["ledlen"] = {"hidden": True}
    else:
        options["ledlen"] = {str(t_["delka"]): {"disabled": True, "reason": LED_NENI_V_NABIDCE[lang] if t_["delka"] not in led_delky else LEDLEN_NEVEJDE[lang].format(l=t_["delka"], w=t_["min_sirka"])}
                             for t_ in li_["typy"] if t_["delka"] not in led_delky or not t_["vejde"]}
    # svitidla LED RUCNE (Robert 2026-10-08): pocet 1..max, co se vejde vedle sebe; poloha kazdeho svitidla = stred v mm od osy stolu. min / max polohy je CELY rozsah stredu svitidla nad profilem (stejny pro vsechna svitidla
    # a nezavisly na poctu): tahle volba musi snest zmenu poctu v jednom kroku z nabidky ve 3D (pridat / odebrat svitidlo posune cisla poloh); nepripustne soucasne polohy (prekryti sousedu) generator upravi a vrati skutecne hodnoty
    if p["led"] and p["stojky"] and p["led_svetlo"] and li_.get("polohy"):
        n_led_ = int(li_["pocet"])
        options["ledcount"] = {"min": 1, "max": max(1, int(li_["max"])), "value": n_led_}
        for k in range(1, S.LED_MAX + 1):
            options[f"ledpos{k}"] = ({"min": int(math.ceil(li_["stred"][0])), "max": int(math.floor(li_["stred"][1])), "value": _cele_nebo_none(li_["polohy"][k - 1]), "auto": p[f"led_z{k}"] is None, "fits": True}
                                     if k <= n_led_ else {"hidden": True})
    else:
        options["ledcount"] = {"min": 1, "max": 1}
        for k in range(1, S.LED_MAX + 1):
            options[f"ledpos{k}"] = {"hidden": True}
    sm_st = gen.get("stojky_meze")
    options["posth"] = ({"min": int(math.ceil(sm_st["min"] / 10.0)) * 10, "max": int(sm_st["max"]), "value": round(float(sm_st["hodnota"]), 1)} if (p["stojky"] and sm_st)
                        else {"min": int(p["stojky_vyska"]), "max": int(p["stojky_vyska"])})
    police_ok = p["police"] >= 1
    options["midsupport"] = ({"hidden": True} if p["sirka"] <= S.prah_sirky(p["system"])                                   # stredni opora existuje jen u sirokeho stolu
                             else {"frame": {"disabled": not police_ok, "reason": None if police_ok else MIDSUPPORT_RAM_POLICE[lang]}, "effective": MIDSUPPORT_VEREJNE.get(pi.get("rezim"), "legs")})
    zm_ = S.elzlab_meze(gen) if (p["elektrozlab"] and p["panely"] and pi.get("pocet")) else None
    options["socketup"] = ({"min": int(zm_["y"]["min"]), "max": int(zm_["y"]["max"]), "value": int(round(zm_["y"]["hodnota"])), "fits": bool(zm_["vejde"])} if zm_ else {"min": 0, "max": 0})
    options["socketside"] = ({"min": int(zm_["z"]["min"]), "max": int(zm_["z"]["max"]), "value": int(round(zm_["z"]["hodnota"])), "fits": bool(zm_["vejde"])} if zm_ else {"min": 0, "max": 0})
    mid_ne = p["sirka"] <= S.prah_sirky(p["system"])
    options["petleg"] = {o: {"disabled": True, "reason": PET_BEZ_STREDNI[lang]} for o in ("fm", "rm")} if (p["drzak_pet"] and mid_ne) else {}          # stredni nohy jsou jen u sirsiho stolu
    options["petface"] = {}
    pm = gen.get("pet_meze")
    options["petpos"] = ({"min": int(pm["min"]), "max": int(pm["max"]), "value": int(round(pm["hodnota"])), "fits": bool(pm["vejde"])} if (p["drzak_pet"] and pm) else {"min": 0, "max": 0})
    # horni police: vyska (posuvnik po 10 mm; automaticky = hodnota z generatoru), hloubka, typy a desky (zakazane, co se nevejde / nepatri k typu a systemu / neni v nabidce)
    if p["hpolice"] and p["stojky"] and hp_inf and not hp_inf.get("problem"):
        hv, hh = hp_inf["vyska"], hp_inf["hloubka"]
        options["upshelfpos"] = {"min": int(math.ceil(hv["min"] / 10.0)) * 10, "max": int(math.floor(hv["max"] / 10.0)) * 10, "value": round(float(hv["hodnota"]), 1), "auto": bool(hv["auto"]), "fits": True}
        options["upshelfdepth"] = {"min": int(hh["min"]), "max": int(math.floor(hh["max"] / 10.0)) * 10, "value": int(round(hh["hodnota"]))}
    else:
        options["upshelfpos"] = {"min": 0, "max": 0}
        options["upshelfdepth"] = {"min": 0, "max": 0}
    if p["hpolice"] and p["stojky"] and hp_inf and not hp_inf.get("problem") and p["hpolice_typ"] == "sikma":          # sklon sikme police (jen u typu sikma; jinak posuvnik zamceny)
        options["upshelftilt"] = {"min": int(HP.SKLON_MIN), "max": int(HP.SKLON_MAX), "value": int(round(p["hpolice_sklon"]))}
    else:
        options["upshelftilt"] = {"min": int(HP.SKLON_VYCHOZI), "max": int(HP.SKLON_VYCHOZI)}
    dz = DUVODY[lang]
    options["upshelftype"] = {HP.TYP_VEREJNE[t_]: {"disabled": True, "reason": dz["upshelf_typ_nabidka"]} for t_ in HP.TYPY if t_ not in nab_hp[1]}           # typy mimo nabidku (verejnost: neaktivni karta)
    if p["hpolice"] and p["stojky"] and hp_inf:                                                                     # typy, na ktere neni nad ramem dost mista (aktualni zustava volitelny)
        options["upshelftype"].update({HP.TYP_VEREJNE[x_["typ"]]: {"disabled": True, "reason": dz["upshelf_typ_sekce"] if x_.get("duvod") == "sekce" else dz["upshelf_typ_nevejde"]}
                                       for x_ in hp_inf["typy"] if not x_["vejde"] and x_["typ"] != p["hpolice_typ"] and x_["typ"] in nab_hp[1]})
    options["upshelfboard"] = {}
    for d_ in HP.DESKY_SYSTEMU[p["system"]]:
        if p["hpolice_typ"] == "ram":
            duv = dz["upshelf_deska_ram"]
        elif HP.potrebuje_drazku(p["hpolice_typ"]) and d_ != HP.DRAZKA_DESKA[p["system"]]:
            duv = dz["upshelf_deska_drazka"].format(d=UPSHELF_NAZVY_DESEK[HP.DRAZKA_DESKA[p["system"]]])
        elif not HP.potrebuje_drazku(p["hpolice_typ"]) and HP.DESKY[d_]["drazka"]:
            duv = dz["upshelf_deska_shora"]
        elif d_ not in nab_hp[0]:
            duv = dz["upshelf_deska_nabidka"]
        else:
            duv = None
        if duv:
            options["upshelfboard"][d_] = {"disabled": True, "reason": duv}
    vat = float(stul_api.SAZBA_DPH)
    gen["ovladani_scena"] = S.ovladani_3d(gen)
    vod = stul_glb.vodici(p, gen)
    if vod and vod.get("ovladani"):                              # ovladani ve 3D: verejne nazvy slotu a texty ve zvolenem jazyce (docs/OVLADANI_3D.md)
        try:
            vod["ovladani"] = stul_ovladani_verejne.ovladani_verejne(vod["ovladani"], lang, S.SYSTEMY[p["system"]]["profil_mm"])
        except stul_ovladani_verejne.ChybiPreklad as e:
            app.logger.error("stul_shop: ovladani ve 3D vynechano: %s", e)
            vod.pop("ovladani", None)
    return {
        "vodici": vod or None,
        "selection": norm, "hash": h, "kod": "STL-" + h[:6].upper(), "rules_version": stul_glb.RULES_VERSION,
        "valid": not gen["problemy"], "errors": errors, "notices": notices, "offers": offers,
        "price": ({"net": cena["bez_dph"], "vat_rate": vat, "gross": cena["s_dph"], "currency": "CZK"} if cena else None),
        "options": options,
    }


# ---------------------------------------------------------------------------------------------------------------------
# routy
# ---------------------------------------------------------------------------------------------------------------------
def _produkty():
    if time.time() - _PRODUKTY["t"] > 60:
        mapa = {}
        try:
            cur = get_conn().cursor()
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='configurator_products'")
            row = cur.fetchone()
            if row and row["setting_value"]:
                mapa = {str(k): v for k, v in json.loads(row["setting_value"]).items()}
        except Exception as e:
            app.logger.warning("stul_shop: nacteni configurator_products selhalo: %s", e)
        _PRODUKTY.update(t=time.time(), map=mapa)
    return _PRODUKTY["map"]


def konfigurovatelny(product_id):
    """True, je-li produkt konfigurovatelny stul (app_settings.configurator_products, recept stul_system30 nebo stul_system40). Pro product.configurator.available."""
    return _produkty().get(str(product_id)) in RECEPTY


def system_pro_produkt(product_id):
    """System profilu (30 | 40) produktu podle receptu v app_settings.configurator_products; neznamy / nekonfigurovatelny produkt = 30."""
    return RECEPTY.get(_produkty().get(str(product_id)), 30)


_SYSTEMY_CACHE = {"t": 0.0, "list": []}


def systemy_produktu():
    """[{system, card_id, active}] - karty konfigurovatelneho stolu po JEDNE na system profilu (nejnizsi id, kdyz jich je vic), podle app_settings.configurator_products;
    `active` = karta je v obchode aktivni a neni archivovana (cte jen shop_products, cache 60 s). Slouzi k preklopeni TEHOZ vyberu mezi systemy 30 a 40 (schema.systems);
    verejne UI nabizi prepnuti jen na aktivni karty, interni stranky generatoru i na neaktivni (karta se pouští až na Robertuv pokyn - pravidlo 54)."""
    if time.time() - _SYSTEMY_CACHE["t"] > 60:
        nalezene = {}
        for k, v in sorted(_produkty().items(), key=lambda kv: (int(kv[0]) if str(kv[0]).isdigit() else 10 ** 12)):
            if v in RECEPTY and str(k).isdigit() and RECEPTY[v] not in nalezene:
                nalezene[RECEPTY[v]] = int(k)
        aktivni = {}
        if nalezene:
            try:
                cur = get_conn().cursor()
                cur.execute("SELECT id, active, is_archived FROM shop_products WHERE id IN (" + ",".join(["%s"] * len(nalezene)) + ")", tuple(nalezene.values()))
                aktivni = {r["id"]: bool(r["active"]) and not r.get("is_archived") for r in cur.fetchall()}
            except Exception as e:                      # noqa: BLE001 - schema nesmi zaviset na dotazu na katalog
                app.logger.warning("stul_shop: stav karet systemu se nepodarilo nacist: %s", e)
        _SYSTEMY_CACHE.update(t=time.time(), list=[{"system": sy, "card_id": pid, "active": bool(aktivni.get(pid))} for sy, pid in sorted(nalezene.items())])
    return [dict(x) for x in _SYSTEMY_CACHE["list"]]


def _zapnuto():
    """Vypnuti jednou volbou v DB: app_settings.configurator_products bez zaznamu pro zadny recept stolu = vsechny routy 404."""
    return any(v in RECEPTY for v in _produkty().values())


_HOSTY_BEZ_CENY = {"t": 0.0, "hosty": set()}


def _hosty_bez_ceny():
    """app_settings.configurator_hide_price_hosts = JSON seznam hostnames (mini-shopy): odpoved na ne NIKDY neobsahuje cenu, at klient posle cokoli
    (technicky navstevnik by jinak stacil volat API bez parametru price=hidden). Prazdne/chybi = nic se neskryva automaticky."""
    if time.time() - _HOSTY_BEZ_CENY["t"] > 60:
        hosty = set()
        try:
            cur = get_conn().cursor()
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='configurator_hide_price_hosts'")
            row = cur.fetchone()
            if row and row["setting_value"]:
                hosty = {str(h).strip().lower() for h in json.loads(row["setting_value"])}
        except Exception as e:
            app.logger.warning("stul_shop: nacteni configurator_hide_price_hosts selhalo: %s", e)
        _HOSTY_BEZ_CENY.update(t=time.time(), hosty=hosty)
    return _HOSTY_BEZ_CENY["hosty"]


def _skryt_cenu(body):
    """Skryt cenu v odpovedi resolve: explicitne `price: "hidden"` (telo) / `?price=hidden`, nebo host z app_settings.configurator_hide_price_hosts."""
    if str(body.get("price") or request.args.get("price") or "").strip().lower() == "hidden":
        return True
    return (request.host or "").split(":")[0].strip().lower() in _hosty_bez_ceny()


HODINOVY_STROP = {"resolve": 3000, "glb": 600, "model": 3000, "schema": 600}


def _limit(kategorie, max_req, okno):
    if _rate_limited(f"stulshop:{kategorie}:h:{_client_ip()}", HODINOVY_STROP.get(kategorie, 600), 3600) or \
            _rate_limited(f"stulshop:{kategorie}:{_client_ip()}", max_req, okno):
        resp = jsonify({"error": "rate_limited"})
        resp.status_code = 429
        resp.headers["Retry-After"] = "3"
        return resp
    return None


def _nenalezeno():
    return jsonify({"error": "not_found"}), 404


@app.get("/api/shop/products/<int:product_id>/configurator")
def stul_shop_schema(product_id):
    lim = _limit("schema", *LIMIT_SCHEMA)
    if lim:
        return lim
    dm = konfigurator_registr.dopravnik_pro(product_id)
    if dm is not None:
        return dm.odpoved_schema(product_id)
    if not konfigurovatelny(product_id):
        return _nenalezeno()
    out = schema(_lang(request.args.get("lang")), system_pro_produkt(product_id))
    out["systems"] = systemy_produktu()                       # karty systemu 30 / 40 (preklopeni tehoz vyberu na druhou kartu); active = karta je v obchode aktivni
    out["env"] = stul_api.nacti_env(product_id)               # ulozene prostredi (HDRI) generatoru pro vsechny navstevniky, nebo null = vychozi (bot10, 2026-10-04)
    out["view"] = stul_pohled.nacti_pohled()                  # ulozeny vychozi UHEL POHLEDU 3D {az, el} pro vsechny generatory, nebo null = puvodnich 35 / 25 (Robert 2026-10-08)
    ul = stul_api.nacti_vychozi(product_id)                   # vychozi konfigurace ulozena adminem ("Ulozit jako vychozi" na strance stolu, Robert 2026-10-05); None = vestavena
    out["default_saved"] = bool(ul)
    if ul:
        out["default_selection"] = slij_vychozi(out["default_selection"], ul)
        # Robert 2026-10-07 ("vychozi stul si automaticky nasazuje sikme vzpery, i kdyz si ulozim vychozi bez nich"): ULOZENA vychozi konfigurace je zavazna. Vypina-li slot, ktery ma pravidlo
        # auto_on (vzpery) a ulozene rameno je NAD prahem pravidla (tam, kde by modul slot po nacteni stranky hned zase zapnul), pravidlo se u TOHOTO produktu nepouzije. Rozhoduje ULOZENA hodnota (ne
        # slouceny vyber: klic, ktery v ulozeni chybi, je vestavene vychozi, ne rozhodnuti admina); ulozeno s ramenem na prahu / pod nim = pravidlo zustava. "Vratit puvodni" (DELETE) ho vraci.
        for sl in out["slots"]:
            a = sl.get("auto_on")
            kdy = ul.get(a["when"]["slot"]) if a else None
            if a and ul.get(sl["id"]) is False and isinstance(kdy, (int, float)) and not isinstance(kdy, bool) and kdy > a["when"]["above"]:
                del sl["auto_on"]
    return jsonify(out)


@app.put("/api/shop/products/<int:product_id>/configurator/env")
@require_permission("nastaveni", "upravit")
def stul_shop_env_put(product_id):
    """Admin-only: ulozi prostredi (HDRI) generatoru pro vsechny ({hdri, strength 0,1-3, rot_deg +-180, hemi 0-1,2}); telo `null` ulozene smaze (vychozi). Mimo meze = 400."""
    if not konfigurovatelny(product_id):
        return _nenalezeno()
    raw = request.get_data(as_text=True).strip()
    if raw == "null":
        cfg = None
    else:
        cfg = request.get_json(silent=True)
        if not isinstance(cfg, dict):
            return jsonify({"error": "telo musi byt JSON objekt {hdri, strength, rot_deg, hemi} nebo null"}), 400
    try:
        ulozeno = stul_api.uloz_env(product_id, cfg)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"env": ulozeno})


@app.put("/api/shop/products/<int:product_id>/configurator/default")
@require_permission("nastaveni", "upravit")
def stul_shop_vychozi_put(product_id):
    """Admin-only (tlacitko "Ulozit jako vychozi" na strance stolu, Robert 2026-10-05): ulozi KONFIGURACI jako vychozi stav generatoru tohoto produktu pro vsechny navstevniky (stranka stolu,
    stranka produktu, mini-shop, embed). Telo {"selection": {...}} = aktualni vyber; server ho znormalizuje a PREPOCITA - neplatna konfigurace se neulozi (409), neznama / nepodporovana volba
    nebo chybny tvar = 400. Odpoved {default_saved, default_selection, hash, kod, notices}; zmena se projevi v `default_selection` schematu (do 5 s i na jinych workerech)."""
    if not konfigurovatelny(product_id):
        return _nenalezeno()
    body = request.get_json(silent=True)
    sel = body.get("selection") if isinstance(body, dict) else None
    if not isinstance(sel, dict) or not sel:
        return jsonify({"error": "telo musi byt {\"selection\": {...}} (uplny vyber konfigurace)"}), 400
    system = system_pro_produkt(product_id)
    try:
        stul_api.vychozi_over(sel)
        r = resolve(sel, "cs", skryt_cenu=True, system=system)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except (S.StulChyba, stul_glb.GlbChyba) as e:
        return jsonify({"error": str(e)}), 400
    if not r["valid"]:
        chyby = [e["message"] for e in r["errors"]]
        return jsonify({"error": "Konfigurace není platná, jako výchozí ji uložit nejde: " + "; ".join(chyby), "errors": chyby}), 409
    try:
        ulozeno = stul_api.uloz_vychozi(product_id, r["selection"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    u = current_user()
    log_audit(u["id"] if u else None, "update", "configurator_default", product_id, {"system": system, "kod": r["kod"], "selection": ulozeno})
    return jsonify({"default_saved": True, "default_selection": slij_vychozi(vychozi_vyber(system), ulozeno), "hash": r["hash"], "kod": r["kod"],
                    "notices": [n["message"] for n in r.get("notices", [])]})


@app.delete("/api/shop/products/<int:product_id>/configurator/default")
@require_permission("nastaveni", "upravit")
def stul_shop_vychozi_delete(product_id):
    """Admin-only: smaze ulozenou vychozi konfiguraci generatoru (zpet na vestavene vychozi hodnoty). Odpoved {default_saved: false, default_selection}."""
    if not konfigurovatelny(product_id):
        return _nenalezeno()
    system = system_pro_produkt(product_id)
    stul_api.uloz_vychozi(product_id, None)
    u = current_user()
    log_audit(u["id"] if u else None, "delete", "configurator_default", product_id, {"system": system})
    return jsonify({"default_saved": False, "default_selection": vychozi_vyber(system)})


def _je_staff():
    """Prihlaseny ZAMESTNANEC (stejna role jako @staff_required)? Verejny host/zakaznik -> False."""
    try:
        u = current_user()
        from app import PERMISSION_ROLES
        return bool(u and u.get("active") and u.get("role") in PERMISSION_ROLES)
    except Exception:                                         # noqa: BLE001 - nikdy nesmi shodit verejny resolve
        return False


def _staff_blok(h):
    """Blok jen pro zamestnance (resolve s `staff: true` a platnou staff session): kompletni kusovnik s cenami, technicke problemy generatoru, odkazy na vyrobni list.
    Spolecny modul ovladani (webapp/js/product-configurator.js) tak slouzi mini-shopu i strance stolu pro zamestnance (Robert: nic neduplikovat); mini-shop tenhle blok
    NIKDY nedostane (bez session staff se neprida)."""
    p = _STAV_PODLE_HASHE.get(h)
    if p is None:
        return None
    gen = S.sestav_stul(**p)
    cena = stul_api.cena_konfigurace(gen["dily"], p["system"])
    qs = urllib.parse.urlencode({k: (int(v) if isinstance(v, bool) else v) for k, v in p.items() if v is not None and not (k == "system" and v == 30)
                                 and not (k in ("navlek", "navlek_delka") and not p.get("navlek")) and not (k == "led_delka" and int(round(float(v))) == S.LED_DELKA_VYCHOZI) and not (k == "led_pocet" and int(v) == 1) and not (k == "panely_delka" and int(round(float(v))) == S.PANEL_DELKA_VYCHOZI) and not (k.startswith("hpolice") and k != "hpolice" and not p.get("hpolice")) and not (k == "hpolice" and not v) and not (k == "hpolice_sklon" and p.get("hpolice_typ") != "sikma") and not (k == "police_deska" and v)})          # navlek jen kdyz je zapnuty (odkazy systemu 30 a 40 beze zmeny)
    return {"kusovnik": (cena or {}).get("kusovnik"), "cena": ({"bez_dph": cena["bez_dph"], "s_dph": cena["s_dph"], "sazba_dph": cena["sazba_dph"], "mena": cena["mena"]} if cena else None),
            "problemy": [{"kod": x.get("kod"), "text": x.get("text")} for x in gen["problemy"]], "pocet_spoju": gen["pocet_spoju"],
            "hash": h, "kod": "STL-" + h[:6].upper(), "vyrobni_list_url": "/api/stul/vyrobni-list?" + qs, "vyrobni_sestava_url": "/api/stul/vyrobni-sestava?" + qs}


@app.post("/api/shop/configurator/resolve")
def stul_shop_resolve():
    lim = _limit("resolve", *LIMIT_RESOLVE)
    if lim:
        return lim
    body = request.get_json(silent=True) or {}
    dm = konfigurator_registr.dopravnik_pro(body.get("product_id"))
    if dm is not None:
        return dm.odpoved_resolve(body, _skryt_cenu(body))
    if not konfigurovatelny(body.get("product_id")):
        return _nenalezeno()
    rv = body.get("rules_version")
    if rv and rv != stul_glb.RULES_VERSION:
        return jsonify({"error": "rules_changed"}), 409
    try:
        skryt = _skryt_cenu(body)
        out = resolve(body.get("selection"), _lang(body.get("lang")), skryt_cenu=skryt, system=system_pro_produkt(body.get("product_id")))
        if not skryt:
            eur, cfg = miniweb_cena.pro_host(request.host, get_conn)      # mini-shop s price_mode 'shown': cena v EUR (kurz + marze), bez nastaveni zadna cena
            if eur:
                out = miniweb_cena.na_eur(out, cfg)
        if body.get("staff") and _je_staff():                  # jen zamestnanec s platnou session; verejny host tenhle blok nikdy nevidi
            out = dict(out)
            out["staff"] = _staff_blok(out.get("hash"))
        return jsonify(out)
    except (S.StulChyba, stul_glb.GlbChyba) as e:
        app.logger.error("stul_shop: resolve selhal: %s", e)
        return jsonify({"error": "server_error"}), 500


@app.get("/api/shop/configurator/model/<h>")
def stul_shop_model(h):
    lim = _limit("model", *LIMIT_RESOLVE)
    if lim:
        return lim
    dm = konfigurator_registr.dopravnik_modul()
    if dm is not None and dm.zna_hash(h):
        return dm.odpoved_model(h)
    if not _zapnuto():
        return _nenalezeno()
    p = _STAV_PODLE_HASHE.get(h)
    if p is None:
        return _nenalezeno()
    return jsonify({"model": _model(p)})


@app.get("/api/shop/configurator/glb/<token>")
def stul_shop_glb(token):
    lim = _limit("glb", *LIMIT_GLB)
    if lim:
        return lim
    if token.startswith(konfigurator_registr.PREFIX_TOKENU_DOPRAVNIKU):
        dm = konfigurator_registr.dopravnik_modul()
        return dm.odpoved_glb(token) if dm is not None else _nenalezeno()
    if not _zapnuto():
        return _nenalezeno()
    p, chyba = over_model(token)
    if p is None:
        return (jsonify({"error": "expired" if chyba == "vyprsel" else "forbidden"}), 410 if chyba == "vyprsel" else 403)
    try:
        h, data = stul_glb.model_pro_parametry(p)
    except (S.StulChyba, stul_glb.GlbChyba) as e:
        app.logger.error("stul_shop: model selhal: %s", e)
        return jsonify({"error": "server_error"}), 500
    data, kodovani = stul_glb.zakoduj_pro_klienta(h, data, request.headers.get("Accept-Encoding"))          # br / gzip: 4,7 MB -> ~0,7-1 MB
    resp = Response(data, mimetype="model/gltf-binary")
    if kodovani:
        resp.headers["Content-Encoding"] = kodovani
    resp.headers["Vary"] = "Accept-Encoding"
    resp.headers["Cache-Control"] = "private, max-age=600"
    resp.headers["Content-Disposition"] = "inline"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp


# DELKA SVITIDLA LED (Robert 2026-10-07: LED 600 vedle LED 1200): vsechna svitidla stolu jsou stejne dlouha, kratsi se vejde i na uzsi stul
TEXTY["cs"].update({"ledlen": "Délka LED svítidla", "ledlen_600": "600 mm", "ledlen_1200": "1200 mm",
                    "help_ledlen": "LED svítidla jsou ve dvou délkách (1200 a 600 mm); všechna svítidla stolu mají stejnou délku a řadí se vedle sebe po šířce stolu. Kratší svítidlo se vejde i na užší stůl – "
                                   "délka, která se nevejde, je v nabídce zašedlá."})
TEXTY["en"].update({"ledlen": "LED light length", "ledlen_600": "600 mm", "ledlen_1200": "1200 mm",
                    "help_ledlen": "The LED lights come in two lengths (1200 and 600 mm); all lights of a table have the same length and are placed side by side across the table width. The shorter light also "
                                   "fits a narrower table – a length that does not fit is greyed out."})
TEXTY["sk"].update({"ledlen": "Dĺžka LED svietidla", "ledlen_600": "600 mm", "ledlen_1200": "1200 mm",
                    "help_ledlen": "LED svietidlá sú v dvoch dĺžkach (1200 a 600 mm); všetky svietidlá stola majú rovnakú dĺžku a radia sa vedľa seba po šírke stola. Kratšie svietidlo sa zmestí aj na užší stôl – "
                                   "dĺžka, ktorá sa nezmestí, je v ponuke zašednutá."})
LEDLEN_NEVEJDE = {"cs": "LED svítidlo {l} mm se sem nevejde – potřebuje stůl široký aspoň {w} mm.",
                  "en": "A {l} mm LED light does not fit here – it needs a table at least {w} mm wide.",
                  "sk": "LED svietidlo {l} mm sa sem nezmestí – potrebuje stôl široký aspoň {w} mm."}
LED_NENI_V_NABIDCE = {"cs": "Tahle délka LED svítidla teď není v nabídce.", "en": "This LED light length is not available at the moment.", "sk": "Táto dĺžka LED svietidla teraz nie je v ponuke."}
TEXTY_AKCI["cs"]["led_kratsi"] = "Zapnout kratší LED {v} mm"
TEXTY_AKCI["en"]["led_kratsi"] = "Switch on the shorter {v} mm LED light"
TEXTY_AKCI["sk"]["led_kratsi"] = "Zapnúť kratšie LED {v} mm"

# SVITIDLA LED RUCNE (Robert 2026-10-08): svitidla se neprinavaji sama podle sirky stolu; pocet (vychozi 1) a polohu kazdeho svitidla podel pricneho profilu voli zakaznik (take tazenim ve 3D)
_h_ledlen_cs = TEXTY["cs"]["help_ledlen"]
assert " a řadí se vedle sebe po šířce stolu" in _h_ledlen_cs
TEXTY["cs"]["help_ledlen"] = _h_ledlen_cs.replace(" a řadí se vedle sebe po šířce stolu", "; kolik jich je a kde leží, volíte níže")
assert " and are placed side by side across the table width" in TEXTY["en"]["help_ledlen"]
TEXTY["en"]["help_ledlen"] = TEXTY["en"]["help_ledlen"].replace(" and are placed side by side across the table width", "; you choose below how many there are and where they sit")
assert " a radia sa vedľa seba po šírke stola" in TEXTY["sk"]["help_ledlen"]
TEXTY["sk"]["help_ledlen"] = TEXTY["sk"]["help_ledlen"].replace(" a radia sa vedľa seba po šírke stola", "; koľko ich je a kde ležia, volíte nižšie")
TEXTY["cs"].update({"ledcount": "Počet svítidel LED",
                    "help_ledcount": "Svítidla LED se samy nepřidávají podle šířky stolu: výchozí je jedno svítidlo a další si přidáváte sami – nejvíc tolik, kolik se jich vejde vedle sebe na šířku stolu.",
                    "help_ledpos": "Poloha středu svítidla podél příčného profilu v mm od osy stolu (kladná hodnota = doprava, 0 = uprostřed). Svítidla se nemohou překrývat a aspoň 90 % délky každého musí ležet nad profilem. "
                                   "Svítidlo jde posouvat i přímo ve 3D tažením.",
                    **{f"ledpos{k}": f"Poloha svítidla LED {k}" for k in range(1, S.LED_MAX + 1)}})
TEXTY["en"].update({"ledcount": "Number of LED lights",
                    "help_ledcount": "LED lights are not added automatically according to the table width: the default is one light and you add more yourself – as many as fit side by side across the table width.",
                    "help_ledpos": "Position of the centre of the light along the cross profile in mm from the table axis (positive = to the right, 0 = centred). The lights cannot overlap and at least 90 % of the length of "
                                   "each must lie over the profile. A light can also be moved directly in 3D by dragging.",
                    **{f"ledpos{k}": f"LED light {k} position" for k in range(1, S.LED_MAX + 1)}})
TEXTY["sk"].update({"ledcount": "Počet svietidiel LED",
                    "help_ledcount": "Svietidlá LED sa samy nepridávajú podľa šírky stola: predvolené je jedno svietidlo a ďalšie si pridávate sami – najviac toľko, koľko sa ich zmestí vedľa seba na šírku stola.",
                    "help_ledpos": "Poloha stredu svietidla pozdĺž priečneho profilu v mm od osi stola (kladná hodnota = doprava, 0 = uprostred). Svietidlá sa nemôžu prekrývať a aspoň 90 % dĺžky každého musí ležať nad profilom. "
                                   "Svietidlo ide posúvať aj priamo v 3D ťahaním.",
                    **{f"ledpos{k}": f"Poloha svietidla LED {k}" for k in range(1, S.LED_MAX + 1)}})

# DALSI JAZYKY (bot16, 2026-10-07): texty serveru pro jazyky mimo cs / en / sk (de, hu ...) jsou data v api/jazyky/<jazyk>.json a pripojuji se az sem, na konec modulu, kdyz jsou
# vsechny slovniky nahore hotove (chybejici klic = anglicka zaloha + varovani do logu; viz api/jazyky.py, docs/jazyky/README.md). Bez sad se nic nezmeni.
jazyky.pripoj_stul_shop(globals())
