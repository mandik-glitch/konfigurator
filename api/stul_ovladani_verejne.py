"""Verejna podoba popisu ovladani ve 3D (bot8, 2026-10-03): `vodici.ovladani` z api/stul_konfigurator.py (nazvy parametru generatoru, cesky) -> VEREJNE nazvy slotu
(w, d, h, cut1x, ... jako v schema/resolve) a texty cs/en/sk. Zadani modulu v prohlizeci: docs/OVLADANI_3D.md; kontrakt: docs/KONTRAKT_KONFIGURATOR_UI.md.

Pravidla: zadne cislo dilu ani index dilu ve verejnych id (nohy a konce se cisluji znovu), tah `stredni_noha` se predava jako slot `mid` v % (jednotka, mm_na_jednotku), dalsi `vodici.stredni_noha` zustava pro starsi klienty. Neznamy cesky text = chyba testu (prekladova tabulka musi pokryt vse, co generator vraci)."""
import re

import jazyky                                                 # dalsi jazyky z dat (api/jazyky/<jazyk>.json), viz api/jazyky.py
import stul_konfigurator as S

# parametr generatoru -> verejny slot
PARAM_NA_SLOT = {"sirka": "w", "hloubka": "d", "vyska": "h", "presah": "ov", "led_rameno": "arm", "stojky": "posts", "kolecka": "wheels", "patky": "feet",
                 "panely": "panels", "led": "led", "suplik": "drawers", "elektrozlab": "socket", "drzak_pet": "pet", "police": "shelf", "police_deska": "shelfboard", "suplik_posun": "boxpos", "suplik_pocet": "drawercount", "suplik_vlevo": "drawleft", "led_svetlo": "ledlight", "pet_posun": "petpos", "pet_noha": "petleg", "pet_strana": "petface",
                 **{f"police_h{_k}": f"sh{_k}" for _k in range(1, S.MAX_POLIC + 1)},
                 "loz": "bearings", "loz_rozteca": "bearpitch", "loz_okraj": "bearedge", "stredni_noha": "mid", "vzpery": "braces", "vzpera_delka": "bracelen", "navlek": "sleeve", "navlek_delka": "sleevelen",
                 "panely_pocet": "panelcount", "panely_posun": "panelpos", "panely_z": "panelside", "panely_delka": "panellen", "led_delka": "ledlen", "stredni_opora": "midsupport", "stojky_vyska": "posth", "elzlab_y": "socketup", "elzlab_z": "socketside",
                 "hpolice": "upshelf", "hpolice_typ": "upshelftype", "hpolice_deska": "upshelfboard", "hpolice_vyska": "upshelfpos", "hpolice_hloubka": "upshelfdepth", "hpolice_sklon": "upshelftilt"}
PARAM_NA_SLOT.update({"led_pocet": "ledcount", **{f"led_z{_k}": f"ledpos{_k}" for _k in range(1, S.LED_MAX + 1)}})          # svitidla LED RUCNE: pocet a poloha kazdeho (Robert 2026-10-08)
for _n in range(1, S.MAX_VYREZU + 1):
    PARAM_NA_SLOT.update({f"vyrez{_n}": f"cut{_n}", f"vyrez{_n}_w": f"cut{_n}w", f"vyrez{_n}_d": f"cut{_n}d", f"vyrez{_n}_x": f"cut{_n}x", f"vyrez{_n}_z": f"cut{_n}z",
                          f"vyrez{_n}_police": f"cut{_n}shelf"})

ID_CASTI = {"deska": "deck", "suplik": "drawers", "panely": "panels", "led": "led", "elektrozlab": "socket", "pet": "pet", "vzpery": "braces", "ram": "frame", "hpolice": "upshelf",
            **{f"led_{_k}": f"ledlamp{_k}" for _k in range(1, S.LED_MAX + 1)}}              # jednotliva svitidla LED (cast "led" = cele osvetleni)
ID_TAHU = {"vyska": "h", "sirka": "w", "hloubka": "d", "suplik_posun": "boxpos", "led_rameno": "arm", "pet_posun": "petpos", "panely_posun": "panelpos", "panely_z": "panelside", "stojky_vyska": "posth",
           "elzlab_y": "socketup", "elzlab_z": "socketside", **{f"police_h{_k}": f"sh{_k}" for _k in range(1, S.MAX_POLIC + 1)},
           **{f"led_z{_k}": f"ledpos{_k}" for _k in range(1, S.LED_MAX + 1)}}

# (cesky text s {n}, anglicky, slovensky); {n} = cislo vyrezu 1-3
_PREKLADY = [
    # casti
    ("Pracovní deska", "Worktop", "Pracovná doska"), ("Výřez {n}", "Cutout {n}", "Výrez {n}"), ("Police pod výřezem {n}", "Shelf under cutout {n}", "Polica pod výrezom {n}"),
    ("Spodní police", "Lower shelf", "Spodná polica"), ("Spodní police {n}", "Lower shelf {n}", "Spodná polica {n}"), ("Šuplíky", "Drawers", "Zásuvky"),
    ("Podpěry spodní police", "Lower shelf supports", "Podpery spodnej police"), ("Podpěry spodní police {n}", "Lower shelf supports {n}", "Podpery spodnej police {n}"),
    ("Podpěry pod pracovní deskou", "Work surface supports", "Podpery pod pracovnou doskou"),
    ("Počet podpěr určuje šířka stolu, střední noha a šuplíky (jejich příčky desku podpírají)", "The number of supports depends on the table width, the middle leg and the drawers (their rails support the surface too)",
     "Počet podpier určuje šírka stola, stredná noha a zásuvky (ich priečky dosku podopierajú)"),
    ("Počet podpěr určuje šířka stolu a střední noha", "The number of supports depends on the table width and the middle leg", "Počet podpier určuje šírka stola a stredná noha"),
    ("Podpěry jsou při větší hloubce stolu vždy; zmenšením hloubky zmizí", "The supports are always added at a larger table depth; they disappear when the depth is reduced",
     "Podpery sú pri väčšej hĺbke stola vždy; zmenšením hĺbky zmiznú"),
    ("Perforované panely", "Perforated panels", "Perforované panely"), ("LED osvětlení", "LED light", "LED osvetlenie"), ("Elektrožlab", "Power strip", "Napájacia lišta"),
    ("Držák PET lahve", "PET bottle holder", "Držiak na PET fľašu"), ("Noha přední levá", "Front left leg", "Predná ľavá noha"), ("Noha přední pravá", "Front right leg", "Predná pravá noha"),
    ("Noha zadní levá", "Rear left leg", "Zadná ľavá noha"), ("Noha zadní pravá", "Rear right leg", "Zadná pravá noha"), ("Střední noha přední", "Front middle leg", "Stredná noha predná"),
    ("Střední noha zadní", "Rear middle leg", "Stredná noha zadná"), ("Konec nohy", "Leg end", "Koniec nohy"),
    ("Vestavěný rám (střední opora)", "Built-in frame (centre support)", "Vstavaný rám (stredná opora)"),
    # polozky nabidky
    ("Přidat výřez sem", "Add a cutout here", "Pridať výrez sem"), ("Ložiskové jednotky: vypnout", "Ball transfer units: switch off", "Ložiskové jednotky: vypnúť"),
    ("Ložiskové jednotky: zapnout", "Ball transfer units: switch on", "Ložiskové jednotky: zapnúť"),
    ("Jednotky hustěji (rozteč −10 mm)", "Units closer together (spacing −10 mm)", "Jednotky hustejšie (rozstup −10 mm)"),
    ("Jednotky řidčeji (rozteč +10 mm)", "Units further apart (spacing +10 mm)", "Jednotky redšie (rozstup +10 mm)"),
    ("Rozměry desky nastavit v panelu", "Set the worktop size in the panel", "Rozmery dosky nastaviť v paneli"),
    ("Police pod výřezem {n}: odebrat", "Shelf under cutout {n}: remove", "Polica pod výrezom {n}: odstrániť"), ("Police pod výřezem {n}: přidat", "Shelf under cutout {n}: add", "Polica pod výrezom {n}: pridať"),
    ("Odebrat výřez {n}", "Remove cutout {n}", "Odstrániť výrez {n}"), ("Odebrat polici pod výřezem {n}", "Remove the shelf under cutout {n}", "Odstrániť policu pod výrezom {n}"),
    ("Odebrat výřez {n} i s policí", "Remove cutout {n} with its shelf", "Odstrániť výrez {n} aj s policou"),
    ("Přidat spodní polici", "Add a lower shelf", "Pridať spodnú policu"), ("Odebrat spodní polici", "Remove a lower shelf", "Odstrániť spodnú policu"),
    ("Odebrat desku police", "Remove the shelf board", "Odstrániť dosku police"), ("Vrátit desku police", "Put the shelf board back", "Vrátiť dosku police"),
    ("Odebrat desky všech polic", "Remove the boards of all shelves", "Odstrániť dosky všetkých políc"), ("Vrátit desky všech polic", "Put the boards back on all shelves", "Vrátiť dosky na všetky police"),
    ("Odebrat šuplíky", "Remove the drawers", "Odstrániť zásuvky"), ("Šuplíky vrátit na výchozí místo", "Move the drawers back to the default position", "Zásuvky vrátiť na pôvodné miesto"),
    ("Box s 1 šuplíkem", "Unit with 1 drawer", "Box s 1 zásuvkou"), ("Box s 2 šuplíky", "Unit with 2 drawers", "Box s 2 zásuvkami"), ("Box s 3 šuplíky", "Unit with 3 drawers", "Box s 3 zásuvkami"),
    ("Odebrat perforované panely (i elektrožlab)", "Remove the perforated panels (and the power strip)", "Odstrániť perforované panely (aj napájaciu lištu)"),
    ("Odebrat LED osvětlení", "Remove the LED light", "Odstrániť LED osvetlenie"), ("Odebrat elektrožlab", "Remove the power strip", "Odstrániť napájaciu lištu"),
    ("Odebrat držák PET lahve", "Remove the PET bottle holder", "Odstrániť držiak na PET fľašu"),
    ("Vzpěry ramen LED", "LED arm braces", "Vzpery ramien LED"), ("Odebrat vzpěry ramen LED", "Remove the LED arm braces", "Odstrániť vzpery ramien LED"),
    ("Přidat vzpěry ramen LED", "Add braces under the LED arms", "Pridať vzpery pod ramená LED"),
    ("Vzpěry delší (+50 mm)", "Longer braces (+50 mm)", "Dlhšie vzpery (+50 mm)"), ("Vzpěry kratší (−50 mm)", "Shorter braces (−50 mm)", "Kratšie vzpery (−50 mm)"),
    ("Delší vzpěra se sem nevejde.", "A longer brace does not fit here.", "Dlhšia vzpera sa sem nezmestí."), ("Kratší vzpěra už není možná.", "A shorter brace is not possible.", "Kratšia vzpera už nie je možná."),
    ("Místo koleček záslepky", "End caps instead of castors", "Záslepky namiesto koliesok"), ("Místo koleček stavitelné patky", "Adjustable feet instead of castors", "Nastaviteľné nožičky namiesto koliesok"),
    ("Místo patek záslepky", "End caps instead of feet", "Záslepky namiesto nožičiek"), ("Místo patek kolečka", "Castors instead of feet", "Kolieska namiesto nožičiek"),
    ("Kolečka", "Castors", "Kolieska"), ("Stavitelné patky místo záslepek", "Adjustable feet instead of end caps", "Nastaviteľné nožičky namiesto záslepiek"),
    # navlek nohou (jekl 40x40x2, system 35; Robert 2026-10-05)
    ("Místo koleček návlek (jekl 40×40×2)", "Steel sleeves instead of castors", "Návleky z jekla namiesto koliesok"),
    ("Místo patek návlek (jekl 40×40×2)", "Steel sleeves instead of feet", "Návleky z jekla namiesto nožičiek"),
    ("Místo záslepek návlek (jekl 40×40×2)", "Steel sleeves instead of end caps", "Návleky z jekla namiesto záslepiek"),
    ("Místo návleku záslepky", "End caps instead of sleeves", "Záslepky namiesto návlekov"), ("Místo návleku kolečka", "Castors instead of sleeves", "Kolieska namiesto návlekov"),
    ("Návlek delší (+50 mm)", "Longer sleeves (+50 mm)", "Dlhšie návleky (+50 mm)"), ("Návlek kratší (−50 mm)", "Shorter sleeves (−50 mm)", "Kratšie návleky (−50 mm)"),
    ("Delší návlek se sem nevejde.", "A longer sleeve does not fit here.", "Dlhší návlek sa sem nezmestí."), ("Kratší návlek už není možný.", "A shorter sleeve is not possible.", "Kratší návlek už nie je možný."),
    ("Zadní stojky: vypnout (i panely, LED, elektrožlab)", "Rear uprights: switch off (also panels, LED, power strip)", "Zadné stojky: vypnúť (aj panely, LED, napájaciu lištu)"),
    ("Zadní stojky: zapnout", "Rear uprights: switch on", "Zadné stojky: zapnúť"), ("Střední nohu vrátit doprostřed", "Move the middle leg back to the centre", "Strednú nohu vrátiť do stredu"),
    # panely, stojky, elektrozlab, stredni opora (Robert 2026-10-05)
    ("Přidat panel", "Add a panel", "Pridať panel"), ("Odebrat panel", "Remove a panel", "Odstrániť panel"),
    ("Odebrat panel (i elektrožlab)", "Remove the panel (and the power strip)", "Odstrániť panel (aj napájaciu lištu)"),
    ("Odebrat všechny panely (i elektrožlab)", "Remove all panels (and the power strip)", "Odstrániť všetky panely (aj napájaciu lištu)"),
    ("Panely vrátit do spodní polohy", "Move the panels back down", "Panely vrátiť do dolnej polohy"), ("Už jsou dole.", "Already at the bottom.", "Už sú dole."),
    ("Další panel se sem nevejde (širší stůl, vyšší stojky nebo vestavěný rám).", "Another panel does not fit here (a wider table, taller uprights or a built-in frame).",
     "Ďalší panel sa sem nezmestí (širší stôl, vyššie stojky alebo vstavaný rám)."),
    ("Elektrožlab vrátit na výchozí místo", "Move the power strip back to the default place", "Napájaciu lištu vrátiť na pôvodné miesto"),
    ("Už je na výchozím místě.", "Already in the default place.", "Už je na pôvodnom mieste."),
    ("Střední nohy místo vestavěného rámu", "Centre legs instead of the built-in frame", "Stredné nohy namiesto vstavaného rámu"), ("Rám vrátit doprostřed", "Move the frame back to the centre", "Rám vrátiť do stredu"),
    ("Střední nohy nahradit vestavěným rámem", "Replace the centre legs with a built-in frame", "Stredné nohy nahradiť vstavaným rámom"),
    ("Vestavěný rám potřebuje spodní polici.", "The built-in frame needs a lower shelf.", "Vstavaný rám potrebuje spodnú policu."),
    ("Výška panelů", "Panel height", "Výška panelov"), ("posun panelů nahoru", "panels moved up", "posun panelov nahor"),
    ("Panely vrátit doprostřed mezi nohy", "Centre the panels between the legs", "Panely vrátiť doprostred medzi nohy"), ("Už jsou uprostřed.", "Already centred.", "Už sú uprostred."),
    ("Panely do stran", "Panels sideways", "Panely do strán"), ("od střední nohy", "from the middle leg", "od strednej nohy"),
    ("levý panel od levé nohy", "left panel from the left leg", "ľavý panel od ľavej nohy"), ("levý panel od střední nohy", "left panel from the middle leg", "ľavý panel od strednej nohy"),
    ("pravý panel od střední nohy", "right panel from the middle leg", "pravý panel od strednej nohy"), ("pravý panel od pravé nohy", "right panel from the right leg", "pravý panel od pravej nohy"),
    ("Výška zadních stojek", "Rear upright height", "Výška zadných stojok"), ("výška stojek nad deskou", "upright height above the worktop", "výška stojok nad doskou"),
    ("Elektrožlab: výška", "Power strip: height", "Napájacia lišta: výška"), ("posun elektrožlabu nahoru", "power strip moved up", "posun napájacej lišty nahor"),
    ("Elektrožlab: do stran", "Power strip: sideways", "Napájacia lišta: do strán"), ("posun elektrožlabu doprava", "power strip moved to the right", "posun napájacej lišty doprava"),
    # duvody zakazu
    (f"Už je {S.MAX_VYREZU} výřezy (nejvíc).", f"There are already {S.MAX_VYREZU} cutouts (the maximum).", f"Už sú {S.MAX_VYREZU} výrezy (maximum)."),
    ("Další police se nevejde (nízký stůl nebo šuplíky).", "Another shelf does not fit (low table or the drawers).", "Ďalšia polica sa nezmestí (nízky stôl alebo zásuvky)."),
    ("Žádná police není.", "There is no shelf.", "Žiadna polica nie je."), ("Už jsou na výchozím místě.", "Already in the default position.", "Už sú na pôvodnom mieste."),
    ("Už je uprostřed.", "Already in the centre.", "Už je v strede."),
    ("Odebrat jen svítidlo LED (profily zůstanou)", "Remove only the LED light (the profiles stay)", "Odobrať len svietidlo LED (profily ostanú)"), ("Vrátit svítidlo LED", "Put the LED light back", "Vrátiť svietidlo LED"),
    ("Přehodit šuplíky na levou stranu", "Move the drawers to the left side", "Prehodiť zásuvky na ľavú stranu"),
    ("Přehodit šuplíky na pravou stranu", "Move the drawers to the right side", "Prehodiť zásuvky na pravú stranu"),
    ("Držák PET lahve vrátit na výchozí výšku", "Move the PET bottle holder back to the default height", "Držiak na PET fľašu vrátiť na pôvodnú výšku"),
    ("Už je ve výchozí výšce.", "Already at the default height.", "Už je na pôvodnej výške."),
    # tahy a mereni
    ("Výška držáku PET", "PET holder height", "Výška držiaka PET"), ("posun držáku", "holder position", "posun držiaka"),
    ("Výška police {n}", "Shelf {n} height", "Výška police {n}"), ("odstup pod deskou", "distance below the worktop", "odstup pod doskou"), ("mezera nad policí", "gap above the shelf", "medzera nad policou"),
    ("Střední noha", "Middle leg", "Stredná noha"), ("od levé nohy", "from the left leg", "od ľavej nohy"), ("od pravé nohy", "from the right leg", "od pravej nohy"),
    ("Výška desky", "Worktop height", "Výška pracovnej dosky"), ("Šířka desky", "Worktop width", "Šírka dosky"), ("Hloubka desky", "Worktop depth", "Hĺbka dosky"),
    ("Posun šuplíků", "Drawers position", "Posun zásuviek"), ("Délka ramene LED", "LED arm length", "Dĺžka ramena LED"), ("Výřez {n}: posun", "Cutout {n}: move", "Výrez {n}: posun"),
    ("Výřez {n}: velikost", "Cutout {n}: size", "Výrez {n}: veľkosť"), ("výška desky", "worktop height", "výška dosky"), ("šířka desky", "worktop width", "šírka dosky"),
    # stul SSE (system 41, bot8 2026-10-05): nohy SSE a jejich nabidka
    ("Levá noha SSE", "Left SSE leg", "Ľavá noha SSE"), ("Pravá noha SSE", "Right SSE leg", "Pravá noha SSE"), ("Střední noha SSE", "Centre SSE leg", "Stredná noha SSE"),
    ("Výšku stolu nastavit v panelu", "Set the table height in the panel", "Výšku stola nastavte v paneli"),
    ("Hloubku stolu (spojnici nohy) nastavit v panelu", "Set the table depth (leg cross-member) in the panel", "Hĺbku stola (spojnicu nohy) nastavte v paneli"),
    ("hloubka desky", "worktop depth", "hĺbka dosky"), ("posun šuplíků", "drawers position", "posun zásuviek"), ("délka ramene", "arm length", "dĺžka ramena"),
    ("od předního okraje", "from the front edge", "od predného okraja"), ("od levého okraje", "from the left edge", "od ľavého okraja"),
    ("šířka výřezu", "cutout width", "šírka výrezu"), ("hloubka výřezu", "cutout depth", "hĺbka výrezu"),
    # delka panelu (Robert 2026-10-07): polozky menu panelu
    # delka svitidla LED (Robert 2026-10-07): polozky menu svitidla
    *[(f"Zvolit LED {_d} mm", f"Use the {_d} mm LED light", f"Zvoliť LED {_d} mm") for _d in S.LED_DELKY],
    ("Tahle délka LED se sem nevejde (širší stůl).", "This LED length does not fit here (a wider table).", "Táto dĺžka LED sa sem nezmestí (širší stôl)."),
    *[(f"Zvolit panel {_d} mm", f"Use the {_d} mm panel", f"Zvoliť panel {_d} mm") for _d in S.PANEL_DELKY],
    ("Tahle délka panelu se sem nevejde (širší stůl, vyšší stojky nebo vestavěný rám).", "This panel length does not fit here (a wider table, taller uprights or the built-in frame).",
     "Táto dĺžka panela sa sem nezmestí (širší stôl, vyššie stojky alebo vstavaný rám)."),
    # svitidla LED RUCNE (Robert 2026-10-08): pridat / odebrat svitidlo, posun kazdeho podel profilu
    ("Přidat svítidlo LED", "Add an LED light", "Pridať svietidlo LED"),
    ("Další svítidlo LED se sem nevejde (jejich délky dohromady by přesáhly šířku stolu).", "Another LED light does not fit here (their lengths together would exceed the table width).",
     "Ďalšie svietidlo LED sa sem nezmestí (ich dĺžky dokopy by presiahli šírku stola)."),
    ("Odebrat toto svítidlo", "Remove this light", "Odstrániť toto svietidlo"),
    ("Vrátit svítidlo na výchozí místo", "Move the light back to its default place", "Vrátiť svietidlo na pôvodné miesto"),
    ("Svítidlo LED", "LED light", "Svietidlo LED"), ("Posun svítidla LED", "LED light position", "Posun svietidla LED"),
    *[(f"Svítidlo LED {_k}", f"LED light {_k}", f"Svietidlo LED {_k}") for _k in range(1, S.LED_MAX + 1)],
    *[(f"Posun svítidla LED {_k}", f"LED light {_k} position", f"Posun svietidla LED {_k}") for _k in range(1, S.LED_MAX + 1)],
    ("od levého okraje stolu", "from the left edge of the table", "od ľavého okraja stola"), ("od pravého okraje stolu", "from the right edge of the table", "od pravého okraja stola"),
    ("od levého svítidla", "from the left light", "od ľavého svietidla"), ("od pravého svítidla", "from the right light", "od pravého svietidla"),
] + S._hpol().PREKLADY                                       # horni police mezi zadnimi stojkami (Robert 2026-10-07)


def _tabulka():
    out = {"en": {}, "sk": {}}
    for cs, en, sk in _PREKLADY:
        for n in (range(1, S.MAX_POLIC + 1) if "{n}" in cs else (0,)):                # {n} = cislo vyrezu (1-3) nebo police (1-MAX_POLIC)
            k = cs.format(n=n) if "{n}" in cs else cs
            out["en"][k] = en.format(n=n) if "{n}" in en else en
            out["sk"][k] = sk.format(n=n) if "{n}" in sk else sk
    return out


_TAB = _tabulka()
jazyky.pripoj_ovladani(_TAB, _PREKLADY, S.MAX_POLIC)                  # dalsi jazyky (de, hu ...) ze sad; chybejici preklad = anglicky text; cs / en / sk beze zmeny


class ChybiPreklad(KeyError):
    pass


def _t(text, lang):
    if lang == "cs" or text is None:
        return text
    try:
        return _TAB[lang][text]
    except KeyError:
        raise ChybiPreklad(f"chybi preklad ({lang}): {text!r}")


def _hodnota(v):
    return v


def _nastav_na_sloty(nastav):
    if nastav is None:
        return None
    out = {}
    for k, v in nastav.items():
        slot = PARAM_NA_SLOT[k]
        out[slot] = 50 if (k == "stredni_noha" and v is None) else v        # doprostred = 50 % (verejny slot mid je v %)
        if k == "stredni_opora":
            out[slot] = {"auto": "auto", "noha": "legs", "ram": "frame"}[v]
        if k == "led_delka":
            out[slot] = str(int(round(float(v))))                                 # verejne id volby delky LED je text ("600"), stejne jako ve schematu
        if k == "hpolice_typ":
            out[slot] = S._hpol().TYP_VEREJNE[v]                                  # verejne id typu police (flat | frame | groove | lip | dividers)
        if k == "panely_delka":
            out[slot] = str(int(round(float(v))))                                 # verejne id volby delky panelu je text ("1481"), stejne jako ve schematu
    return out


def ovladani_verejne(ov, lang="cs", profil_mm=30.0):
    """Prevede `vodici.ovladani` (GLB souradnice, nazvy parametru generatoru) na verejnou podobu: nazvy slotu, texty ve zvolenem jazyce, bez indexu dilu.
    `profil_mm` = sirka profilu systemu stolu (30 / 40): verejny slot `mid` je v % rozpeti mezi osami krajnich noh = sirka - profil."""
    if not ov:
        return None
    lang = lang if (lang in ("cs", "en", "sk") or lang in _TAB) else "cs"
    prejm = {}
    nohy = konce = 0
    for c in ov["casti"]:
        cid = c["id"]
        if cid in ID_CASTI:
            nove = ID_CASTI[cid]
        elif cid.startswith("noha_"):
            nohy += 1
            nove = f"leg{nohy}"
        elif cid.startswith("konec_"):
            konce += 1
            nove = f"legend{konce}"
        elif re.fullmatch(r"vyrez\d", cid):
            nove = "cut" + cid[-1]
        elif re.fullmatch(r"vyrez\d_police", cid):
            nove = f"cut{cid[5]}shelf"
        elif cid.startswith("police_"):
            nove = "shelf" + cid.split("_")[1]
        elif cid.startswith("podpery_"):
            nove = "supports" + cid.split("_")[1]
        else:
            nove = cid
        prejm[cid] = nove
    casti = []
    for c in ov["casti"]:
        menu = []
        for m in c["menu"]:
            polozka = {"text": _t(m["text"], lang), "nastav": _nastav_na_sloty(m.get("nastav")), "zakazano": bool(m.get("zakazano")), "duvod": _t(m.get("duvod"), lang)}
            if m.get("bod_na_desce"):
                b = m["bod_na_desce"]
                polozka["bod_na_desce"] = {"x": PARAM_NA_SLOT[b["x"]], "z": PARAM_NA_SLOT[b["z"]], "stred_o": [PARAM_NA_SLOT[q] for q in b["stred_o"]]}
            if m.get("fokus"):
                polozka["fokus"] = PARAM_NA_SLOT[m["fokus"]]
            menu.append(polozka)
        casti.append({"id": prejm[c["id"]], "label": _t(c["label"], lang), "param": [PARAM_NA_SLOT[q] for q in c["param"] if q in PARAM_NA_SLOT], "aabb": c["aabb"],
                      "priorita": c["priorita"], "menu": menu})
    tahy = []
    for t in ov["tahy"]:
        if t["id"] == "stredni_noha":
            # verejny slot `mid` je v % rozpeti mezi osami krajnich noh (sirka - profil), tah ve 3D jde v mm -> faktor = % na mm; meze, zakazana pasma a odstup v %, mereni (mm) pres mul/add,
            # `jednotka` = co ukazuje hlavni hodnota stitku, `mm_na_jednotku` = prepocet mezery u prekazky na mm. Tim odpada samostatny uchyt stredni nohy ve Volbe komponent.
            span = float(ov["deska"]["sirka"]) - float(profil_mm)
            if span <= 0:
                continue
            pct = 100.0 / span
            nov = {k: v for k, v in t.items() if k not in ("id", "label", "param", "casti", "mereni", "zakazano")}
            nov.update(id="mid", label=_t(t["label"], lang), param="mid", faktor=round(pct, 8), hodnota=round(t["hodnota"] * pct, 3), min=round(t["min"] * pct, 3), max=round(t["max"] * pct, 3),
                       krok=1.0, jednotka="%", mm_na_jednotku=round(span / 100.0, 6), odstup_od_prekazky=round(float(t.get("odstup_od_prekazky") or 0.0) * pct, 4),
                       zakazano=[[round(a * pct, 3), round(b * pct, 3)] for a, b in t.get("zakazano", [])], casti=[prejm[q] for q in t.get("casti", [])],
                       mereni=[{"label": _t(m["label"], lang), "param": "mid", "mul": round(m["mul"] * span / 100.0, 6), "add": m["add"]} for m in t["mereni"]])
            tahy.append(nov)
            continue
        tid = ID_TAHU.get(t["id"]) or re.sub(r"^vyrez(\d)_presun$", r"cut\1_move", re.sub(r"^vyrez(\d)_velikost$", r"cut\1_size", t["id"]))
        nov = {k: v for k, v in t.items() if k not in ("id", "label", "param", "param_x", "param_z", "casti", "mereni")}
        nov.update(id=tid, label=_t(t["label"], lang), casti=[prejm[q] for q in t.get("casti", [])],
                   mereni=[dict(m, label=_t(m["label"], lang), param=PARAM_NA_SLOT[m["param"]]) for m in t["mereni"]])
        for k in ("param", "param_x", "param_z"):
            if k in t:
                nov[k] = PARAM_NA_SLOT[t[k]]
        tahy.append(nov)
    out = {"units": "mm; GLB axes: X depth (backwards), Y up, Z width (right); centred, floor y = 0", "deska": ov.get("deska"), "casti": casti, "tahy": tahy}
    if ov.get("zive_rozsahy") is not None:
        out["zive_rozsahy"] = ov["zive_rozsahy"]                       # kde jsou vrcholy dilu v GLB (zive tazeni v prohlizeci, docs/OVLADANI_3D.md)
        if ov.get("zive_rozsahy_extra"):
            out["zive_rozsahy_extra"] = ov["zive_rozsahy_extra"]       # dil rozdeleny do vice uzlu (SPODNI suplik boxu je vlastni uzel kvuli pohybu na klik): dalsi rozsahy se hybou s dilem; bez nich by pri
                                                                       # tazeni sirky / posunu boxu jelo jen telo skrine a suplik zustal na miste (odtrhl se od boxu; Robert 2026-10-06, od 8cd23e6c)
        if ov.get("razitka"):
            out["razitka"] = ov["razitka"]                             # razitka (logo + vypln drazky) a dil, na kterem sedi: pri zivem tazeni se hybou s dilem (WORKFLOW pravidlo 61; Robert 2026-10-08)
    return out
