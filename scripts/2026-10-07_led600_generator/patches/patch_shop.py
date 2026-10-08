#!/usr/bin/env python3
"""Zaplata api/stul_shop.py: verejne API generatoru stolu - DELKA SVITIDLA LED (Robert 2026-10-07: "LED 600 doplnit do generatoru"), slot `ledlen` (select 600 | 1200 mm) podle vzoru delek panelu.
Nabidka veridnosti jen s AKTIVNI kartou (pravidlo 54; `led_delky_pro_pozadavek`), zakazane delky s duvodem, nabidka "Zapnout kratsi LED N mm" u zakazaneho prepinace LED (misto roztazeni stolu),
token `K`, shrnuti voleb (jen kdyz neni vychozi), cache resolve, texty cs / en / sk (dalsi jazyky: anglicka zaloha; viz api/jazyky.py). Kotvene nahrady (assert count == 1) proti ZIVEMU souboru
(kotvy mimo oblasti jinych zmen: qs v `_staff_blok` se kotvi na podminku navleku, ne na panely). Pouziti: patch_shop.py <vstup stul_shop.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


# 1) verejne id delky, nabidka delek (jen aktivni karta pro verejnost), pomocne funkce
s = nahrad(s, '''# id slotu -> parametr generatoru (neprusvitne ID pro UI; stabilni)
''', '''# DELKA SVITIDLA LED (Robert 2026-10-07): verejne id volby = delka v mm jako text ("600" | "1200"; S.LED_DELKY), parametr generatoru led_delka (float)
LEDLEN_IDS = tuple(str(d) for d in S.LED_DELKY)


def _ledlen(v, povolene=None):
    """Verejna volba delky svitidla LED (text i cislo) -> parametr generatoru (mm); neznama nebo (pri `povolene`) nenabizena hodnota = vychozi (1200)."""
    try:
        d = int(round(float(v)))
    except (TypeError, ValueError, OverflowError):
        return float(S.LED_DELKA_VYCHOZI)
    return float(d) if (d in S.LED_TYPY and (povolene is None or d in povolene)) else float(S.LED_DELKA_VYCHOZI)


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


# id slotu -> parametr generatoru (neprusvitne ID pro UI; stabilni)
''', "led_delky")

# 2) vychozi vyber
s = nahrad(s, '''"panellen": str(S.PANEL_DELKA_VYCHOZI), ''', '''"panellen": str(S.PANEL_DELKA_VYCHOZI), "ledlen": str(S.LED_DELKA_VYCHOZI), ''', "VYCHOZI_VYBER")

# 3) slot -> dil (chybovy slot), zavislosti, schema
s = nahrad(s, '''"product_4929": "led", **{pid_: "drawers"''', '''**{pid_: "led" for pid_ in S.LED_PARTY}, **{pid_: "drawers"''', "DIL_NA_SLOT")
s = nahrad(s, '''"ledlight": ["posts", "led"], ''', '''"ledlight": ["posts", "led"], "ledlen": ["posts", "led", "ledlight"], ''', "zavisi_na")
s = nahrad(s, '''toggle("led", "g_extras"), toggle("ledlight", "g_extras"),''', '''toggle("led", "g_extras"), toggle("ledlight", "g_extras"), select("ledlen", "g_extras", LEDLEN_IDS, t["help_ledlen"]),''', "schema_slot")
s = nahrad(s, '''        out["default_selection"].pop("panellen", None)
''', '''        out["default_selection"].pop("panellen", None)
    led_delky_ = led_delky_pro_pozadavek()                       # delky svitidla LED v nabidce tohoto pozadavku: verejnost jen s aktivni kartou (pravidlo 54), zamestnanec vsechny
    for sl in out["slots"]:
        if sl["id"] == "ledlen":
            sl["options"] = [o for o in sl["options"] if int(o["id"]) in led_delky_]
    if len(led_delky_) < 2:                                      # nabizi se jen 1200: slot delky se verejnosti vubec nevraci (ani ve vychozim vyberu)
        out["slots"] = [sl for sl in out["slots"] if sl["id"] != "ledlen"]
        out["default_selection"].pop("ledlen", None)
''', "schema_filtr")

# 4) normalizace vyberu -> parametr generatoru a zpet
s = nahrad(s, '''    p["panely_delka"] = _panellen(sel.get("panellen")''', '''    p["led_delka"] = _ledlen(sel.get("ledlen"), led_delky_pro_pozadavek()) if p["led"] else float(S.LED_DELKA_VYCHOZI)          # delka svitidla LED (vsechna stejna); bez LED vychozi
    p["panely_delka"] = _panellen(sel.get("panellen")''', "normalizuj")
s = nahrad(s, '''    norm["panellen"] = str(int(round(p["panely_delka"])))
''', '''    norm["panellen"] = str(int(round(p["panely_delka"])))
    norm["ledlen"] = str(int(round(p["led_delka"])))
''', "norm")

# 5) token modelu: klic K (mm) jen u jine nez vychozi delky svitidla
s = nahrad(s, '''    if p.get("stredni_opora", "auto") != "auto":
''', '''    if p.get("led") and p.get("stojky", True) and p.get("led_svetlo", True) and int(round(float(p.get("led_delka", S.LED_DELKA_VYCHOZI)))) != S.LED_DELKA_VYCHOZI:
        out["K"] = int(round(float(p["led_delka"])))                                         # delka svitidla LED (mm; bez klice = 1200)
    if p.get("stredni_opora", "auto") != "auto":
''', "zabal")
s = nahrad(s, '''    if o.get("L"):
        p["panely_delka"] = float(o["L"])
''', '''    if o.get("L"):
        p["panely_delka"] = float(o["L"])
    if o.get("K"):
        p["led_delka"] = float(o["K"])
''', "rozbal")

# 6) klic cache resolve nese POZADOVANOU delku svitidla i nabizene delky
s = nahrad(s, '''norm.get("panellen"), tuple(sorted(delky)))''', '''norm.get("panellen"), tuple(sorted(delky)), norm.get("ledlen"), tuple(sorted(led_delky_pro_pozadavek())))''', "klic_cache")

# 7) shrnuti voleb: delka svitidla se ukaze jen kdyz neni vychozi (shrnuti vychoziho stolu zustava)
s = nahrad(s, '''        skryt.add("arm")
''', '''        skryt.add("arm")
    if not (sel["led"] and sel["posts"] and sel.get("ledlight", True)) or sel.get("ledlen", str(S.LED_DELKA_VYCHOZI)) == str(S.LED_DELKA_VYCHOZI):
        skryt.add("ledlen")                                      # delka svitidla LED ve shrnuti jen kdyz neni vychozi 1200 (shrnuti dosavadnich stolu beze zmeny)
''', "souhrn")

# 8) _spocti: efektivni delka svitidla, volba delky v options, nabidka kratsiho svitidla u zakazaneho prepinace LED
s = nahrad(s, '''    norm["panellen"] = str(int(round(p["panely_delka"]))) if p["panely"] else str(S.PANEL_DELKA_VYCHOZI)''',
           '''    norm["ledlen"] = str(int(round(p["led_delka"]))) if (p["led"] and p["stojky"] and p["led_svetlo"]) else str(S.LED_DELKA_VYCHOZI)          # efektivni delka svitidla LED
    norm["panellen"] = str(int(round(p["panely_delka"]))) if p["panely"] else str(S.PANEL_DELKA_VYCHOZI)''', "spocti_norm")
s = nahrad(s, '''        on = {"price_delta": delta, "disabled": bool(duvod), "reason": duvod}
''', '''        if par == "led" and duvod and p["stojky"] and not p[par]:                       # LED se v pozadovane delce nevejde: nabidka KRATSIHO svitidla, ktere se vejde (misto roztazeni stolu)
            kr_led = _led_kratsi(p, led_delky_pro_pozadavek())
            if kr_led:
                suggest = {"ledlen": str(kr_led)}
        on = {"price_delta": delta, "disabled": bool(duvod), "reason": duvod}
''', "spocti_nabidka_led")
s = nahrad(s, '''else ta["roztahnout_h"].format(v=suggest["posth"])))''',
           '''else (ta["roztahnout_h"].format(v=suggest["posth"]) if "posth" in suggest else ta["led_kratsi"].format(v=suggest["ledlen"]))))''', "spocti_stitek")
s = nahrad(s, '''                               for t_ in (pi.get("typy") or []) if t_["delka"] not in delky or not t_["vejde"]}
''', '''                               for t_ in (pi.get("typy") or []) if t_["delka"] not in delky or not t_["vejde"]}
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
''', "spocti_options")

# 9) pomocna funkce: kratsi svitidlo, ktere se vejde
s = nahrad(s, '''def _duvod_delky(lang, p, typ):
''', '''def _led_kratsi(p, led_delky):
    """Nejdelsi KRATSI delka svitidla LED (z nabizenych `led_delky`), pri ktere se LED na tomto stole vejde (jinak None): nabidka u zakazaneho prepinace LED misto roztazeni stolu."""
    for d in sorted((x for x in led_delky if x < int(round(p["led_delka"]))), reverse=True):
        try:
            if S.sestav_stul(**{**p, "led": True, "led_delka": float(d)})["parametry"]["led"]:
                return d
        except S.StulChyba:
            continue
    return None


def _duvod_delky(lang, p, typ):
''', "led_kratsi")

# 10) odkaz na vyrobni list / sestavu pro zamestnance: vychozi delka svitidla se do odkazu nedava (odkazy beze zmeny)
s = nahrad(s, '''and not (k in ("navlek", "navlek_delka") and not p.get("navlek"))''',
           '''and not (k in ("navlek", "navlek_delka") and not p.get("navlek")) and not (k == "led_delka" and int(round(float(v))) == S.LED_DELKA_VYCHOZI)''', "qs")

# 11) texty (cs / en / sk) a hlasky: PRED pripojenim dalsich jazyku (jazyky.pripoj_stul_shop doplni anglickou zalohu)
s = nahrad(s, '''# DALSI JAZYKY (bot16, 2026-10-07)''', '''# DELKA SVITIDLA LED (Robert 2026-10-07: LED 600 vedle LED 1200): vsechna svitidla stolu jsou stejne dlouha, kratsi se vejde i na uzsi stul
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

# DALSI JAZYKY (bot16, 2026-10-07)''', "texty")

open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
