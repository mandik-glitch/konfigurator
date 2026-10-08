#!/usr/bin/env python3
"""Zaplata api/stul_shop.py: RUCNI svitidla LED ve verejnem API (sloty `ledcount`, `ledpos1..4`) - bot8, 2026-10-08.
Robert: "svitidla v generatoru se pridavaji automaticky za sebe podle delky, ale chceme aby se pridavali jen rucne a mohli se posouvat podel profilu".
Pouziti: patch_shop.py <vstup stul_shop.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


# 1) pomocna funkce: verejna poloha svitidla -> parametr generatoru ----------------------------------------------------------------------------------------------------------------------
s = nahrad(s, '''# DELKY LED V NABIDCE (pravidlo 54 - kartu aktivuje jen Robert)''', '''def _ledpos(v):
    """Verejna poloha svitidla LED (mm od osy stolu, + doprava; slot ledpos<k>) -> parametr generatoru led_z<k>; None / prazdne / neplatne = automaticka poloha. Na 0,1 mm (jako generator)."""
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return round(min(3000.0, max(-3000.0, x)), 1) if math.isfinite(x) else None


# DELKY LED V NABIDCE (pravidlo 54 - kartu aktivuje jen Robert)''', "ledpos")

# 2) vychozi vyber ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad(s, '''"ledlen": str(S.LED_DELKA_VYCHOZI), "midsupport": "auto",''', '''"ledlen": str(S.LED_DELKA_VYCHOZI), "ledcount": 1, **{f"ledpos{k}": None for k in range(1, S.LED_MAX + 1)}, "midsupport": "auto",''', "VYCHOZI_VYBER")

# 3) zavislosti slotu ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad(s, '''    z["sleevelen"] = ["sleeve"]''', '''    z.update({k_: ["posts", "led", "ledlight"] for k_ in ("ledcount",) + tuple(f"ledpos{j}" for j in range(1, S.LED_MAX + 1))})          # pocet a poloha svitidel LED: jen se svitidlem (Robert 2026-10-08)
    z["sleevelen"] = ["sleeve"]''', "zavisi_na")

# 4) schema -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad(s, '''select("ledlen", "g_extras", LEDLEN_IDS, t["help_ledlen"]),''', '''select("ledlen", "g_extras", LEDLEN_IDS, t["help_ledlen"]),
            slider("ledcount", "g_extras", 1, S.LED_MAX, 1, "ks", t["help_ledcount"]),
            *[slider(f"ledpos{k}", "g_extras", -1500, 1500, 1, "mm", t["help_ledpos"] if k == 1 else None) for k in range(1, S.LED_MAX + 1)],''', "schema")

# 5) vyber -> parametry generatoru -------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad(s, '''    p["panely_delka"] = _panellen(sel.get("panellen"),''', '''    p["led_pocet"] = int(_cislo(sel.get("ledcount"), 1, S.LED_MAX, 1, 1)) if p["led"] else 1          # svitidla LED RUCNE (Robert 2026-10-08): pocet (vychozi 1) a poloha kazdeho (mm od osy stolu, None = automaticky); PRESNE meze hlida generator (options.ledcount / ledpos<k>)
    for k in range(1, S.LED_MAX + 1):
        p[f"led_z{k}"] = _ledpos(sel.get(f"ledpos{k}")) if (p["led"] and k <= p["led_pocet"]) else None
    p["panely_delka"] = _panellen(sel.get("panellen"),''', "sel->p")
s = nahrad(s, '''    norm["ledlen"] = str(int(round(p["led_delka"])))
    norm["drawercount"] = p["suplik_pocet"]
''', '''    norm["ledlen"] = str(int(round(p["led_delka"])))
    norm["ledcount"] = p["led_pocet"]
    for k in range(1, S.LED_MAX + 1):
        norm[f"ledpos{k}"] = _cele_nebo_none(p[f"led_z{k}"])
    norm["drawercount"] = p["suplik_pocet"]
''', "norm")

# 6) token ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad(s, '''    if p.get("stredni_opora", "auto") != "auto":
        out["M"] = 1 if p["stredni_opora"] == "noha" else 2''', '''    if p.get("led") and p.get("stojky", True) and p.get("led_svetlo", True) and (int(p.get("led_pocet", 1)) != 1 or any(p.get(f"led_z{k}") is not None for k in range(1, S.LED_MAX + 1))):
        n_led = int(p.get("led_pocet", 1))
        out["J"] = [n_led] + [None if p.get(f"led_z{k}") is None else round(float(p[f"led_z{k}"]), 1) for k in range(1, n_led + 1)]          # svitidla LED RUCNE: [pocet, poloha 1.. (None = automaticky)]; bez klice = jedno svitidlo na automaticke poloze
    if p.get("stredni_opora", "auto") != "auto":
        out["M"] = 1 if p["stredni_opora"] == "noha" else 2''', "zabal")
s = nahrad(s, '''    if o.get("K"):
        p["led_delka"] = float(o["K"])
''', '''    if o.get("K"):
        p["led_delka"] = float(o["K"])
    if o.get("J"):
        p["led_pocet"] = int(o["J"][0])
        for i, v in enumerate(o["J"][1:], 1):
            p[f"led_z{i}"] = None if v is None else float(v)
''', "rozbal")

# 7) mezipamet resolve + odkaz na vyrobni list (zamestnanec) --------------------------------------------------------------------------------------------------------------------------
s = nahrad(s, '''norm.get("ledlen"), tuple(sorted(led_delky_pro_pozadavek())))''', '''norm.get("ledlen"), norm.get("ledcount"), tuple(sorted(led_delky_pro_pozadavek())))''', "cache klic")
s = nahrad(s, '''and not (k == "led_delka" and int(round(float(v))) == S.LED_DELKA_VYCHOZI)''', '''and not (k == "led_delka" and int(round(float(v))) == S.LED_DELKA_VYCHOZI) and not (k == "led_pocet" and int(v) == 1)''', "qs")

# 8) _spocti: pozadovany pocet (pro oznameni), efektivni hodnoty, oznameni, options ----------------------------------------------------------------------------------------
s = nahrad(s, '''    pozad_navlek = norm.get("sleevelen")                          # POZADOVANA delka navleku (generator ji na nizkem stole orizne)
''', '''    pozad_navlek = norm.get("sleevelen")                          # POZADOVANA delka navleku (generator ji na nizkem stole orizne)
    pozad_led = norm.get("ledcount")                              # POZADOVANY pocet svitidel LED (generator ho orizne na pocet, ktery se vejde)
''', "pozad_led")
s = nahrad(s, '''    norm["panellen"] = str(int(round(p["panely_delka"]))) if p["panely"] else str(S.PANEL_DELKA_VYCHOZI)       # efektivni delka panelu (po snizeni, kdyz se zvolena nevejde)
''', '''    norm["panellen"] = str(int(round(p["panely_delka"]))) if p["panely"] else str(S.PANEL_DELKA_VYCHOZI)       # efektivni delka panelu (po snizeni, kdyz se zvolena nevejde)
    norm["ledcount"] = int(p["led_pocet"])                                                                       # efektivni pocet a polohy svitidel LED (generator je orizne; bez svitidla 1 / automaticky)
    for k in range(1, S.LED_MAX + 1):
        norm[f"ledpos{k}"] = _cele_nebo_none(p[f"led_z{k}"])
''', "efektivni led")
s = nahrad(s, '''    if p["panely"] and pozad_delka and int(pozad_delka) > int(round(p["panely_delka"])):
        notices.append({"slot": "panellen", "action": "info", "message": PANELY_ZKRACENO[lang].format(l=int(round(p["panely_delka"])))})
''', '''    if p["panely"] and pozad_delka and int(pozad_delka) > int(round(p["panely_delka"])):
        notices.append({"slot": "panellen", "action": "info", "message": PANELY_ZKRACENO[lang].format(l=int(round(p["panely_delka"])))})
    if p["led"] and p["stojky"] and p["led_svetlo"] and pozad_led and int(pozad_led) > int(p["led_pocet"]):
        notices.append({"slot": "ledcount", "action": "info", "message": LEDPOCET_OREZANO[lang].format(n=int(p["led_pocet"]))})
''', "notice led")
s = nahrad(s, '''    sm_st = gen.get("stojky_meze")
    options["posth"]''', '''    # svitidla LED RUCNE (Robert 2026-10-08): pocet 1..max, co se vejde vedle sebe; poloha kazdeho svitidla = stred v mm od osy stolu. min / max polohy je CELY rozsah stredu svitidla nad profilem (stejny pro vsechna svitidla
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
    options["posth"]''', "options led")
s = nahrad(s, '''PANELY_OREZANO = {''', '''LEDPOCET_OREZANO = {"cs": "Počet svítidel LED snížen na {n} – víc se jich sem nevejde vedle sebe (užší stůl nebo delší svítidla).",
                    "en": "Number of LED lights reduced to {n} – more will not fit side by side (a narrower table or longer lights).",
                    "sk": "Počet svietidiel LED znížený na {n} – viac sa ich sem nezmestí vedľa seba (užší stôl alebo dlhšie svietidlá)."}
PANELY_OREZANO = {''', "LEDPOCET_OREZANO")

# 9) shrnuti ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad(s, '''    if not sel["drawers"]:
        skryt.update(("boxpos", "drawleft", "drawercount"))''', '''    svitidlo_ = bool(sel["led"] and sel["posts"] and sel.get("ledlight", True))
    if not svitidlo_ or int(sel.get("ledcount") or 1) == 1:
        skryt.add("ledcount")                                    # pocet svitidel LED ve shrnuti jen kdyz neni 1 (shrnuti dosavadnich stolu beze zmeny)
    for k in range(1, S.LED_MAX + 1):
        if not svitidlo_ or k > int(sel.get("ledcount") or 1) or sel.get(f"ledpos{k}") is None:
            skryt.add(f"ledpos{k}")                              # poloha svitidla ve shrnuti jen u existujiciho svitidla s vyslovne zadanou polohou
    if not sel["drawers"]:
        skryt.update(("boxpos", "drawleft", "drawercount"))''', "souhrn")

# 10) texty cs / en / sk ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad(s, '''TEXTY_AKCI["sk"]["led_kratsi"] = "Zapnúť kratšie LED {v} mm"
''', '''TEXTY_AKCI["sk"]["led_kratsi"] = "Zapnúť kratšie LED {v} mm"

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
''', "texty")

open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
