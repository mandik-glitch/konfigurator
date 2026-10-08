#!/usr/bin/env python3
"""Zaplata api/stul_shop.py: verejne API generatoru stolu - slot `shelfboard` (spodni police BEZ DESKY; Robert 2026-10-07: "spodni police nech ma volbu byt bez desky, jen profily / ram").
Toggle skupiny Konstrukce za poctem polic, zavisi na slotu `shelf` (bez spodnich polic neexistuje), parametr generatoru `police_deska`; texty cs / en / sk (dalsi jazyky ze sad api/jazyky doplni
zaloha z anglictiny). Kotvene nahrady (assert count == 1) proti ZIVEMU souboru. Pouziti: patch_shop.py <vstup stul_shop.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


# 1) slot -> parametr generatoru (prepinace) a vychozi vyber
s = nahrad(s, '''"socket": "elektrozlab", "pet": "drzak_pet", "feet": "patky", "braces": "vzpery"}''',
           '''"socket": "elektrozlab", "pet": "drzak_pet", "feet": "patky", "braces": "vzpery", "shelfboard": "police_deska"}''', "PREPINACE")
s = nahrad(s, '''"posts": True, "shelf": 1, "wheels": True,''', '''"posts": True, "shelf": 1, "shelfboard": True, "wheels": True,''', "VYCHOZI_VYBER")

# 2) texty (cs / en / sk; de a hu doplni zaloha z anglictiny, dokud je nevyplni bot7 - viz docs/jazyky/README.md)
s = nahrad(s, '''        "help_shelf": "Police se rozloží po výšce rovnoměrně, mezi nimi je vždy aspoň 100 mm volného místa. Počet je omezen výškou stolu a šuplíky.",
''', '''        "help_shelf": "Police se rozloží po výšce rovnoměrně, mezi nimi je vždy aspoň 100 mm volného místa. Počet je omezen výškou stolu a šuplíky.",
        "shelfboard": "Desky na spodních policích",
        "help_shelfboard": "Bez desek zůstane z každé spodní police jen rám z profilů (bez desky a bez podpěr pod ní). Platí pro všechny spodní police.",
''', "TEXTY_cs")
s = nahrad(s, '''        "help_shelf": "The shelves are spread evenly over the height, with at least 100 mm of free space between them. The number is limited by the table height and the drawers.",
''', '''        "help_shelf": "The shelves are spread evenly over the height, with at least 100 mm of free space between them. The number is limited by the table height and the drawers.",
        "shelfboard": "Boards on the lower shelves",
        "help_shelfboard": "Without the boards each lower shelf is just a frame of profiles (no board and no supports under it). It applies to all lower shelves.",
''', "TEXTY_en")
s = nahrad(s, '''    "help_shelf": "Police sa rozložia rovnomerne po výške, medzi nimi zostane vždy aspoň 100 mm voľného miesta. Počet je obmedzený výškou stola a zásuvkami.",
''', '''    "help_shelf": "Police sa rozložia rovnomerne po výške, medzi nimi zostane vždy aspoň 100 mm voľného miesta. Počet je obmedzený výškou stola a zásuvkami.",
    "shelfboard": "Dosky na spodných policiach",
    "help_shelfboard": "Bez dosiek ostane z každej spodnej police len rám z profilov (bez dosky a bez podpier pod ňou). Platí pre všetky spodné police.",
''', "TEXTY_sk")
s = nahrad(s, '''        "shelf": "Spodní police se při této výšce nevejde.",
''', '''        "shelf": "Spodní police se při této výšce nevejde.",
        "shelfboard": "Volba platí jen se spodní policí.",
''', "DUVODY_cs")
s = nahrad(s, '''        "shelf": "The lower shelf does not fit this table height.",
''', '''        "shelf": "The lower shelf does not fit this table height.",
        "shelfboard": "This option only applies together with a lower shelf.",
''', "DUVODY_en")
s = nahrad(s, '''    "shelf": "Dolná polica sa pri tejto výške nezmestí.",
''', '''    "shelf": "Dolná polica sa pri tejto výške nezmestí.",
    "shelfboard": "Voľba platí len so spodnou policou.",
''', "DUVODY_sk")

# 3) schema (bez depends_on: nadrazeny slot `shelf` je posuvnik, kontrakt zna jen toggle - bez polic se slot skryva pres options.shelfboard.hidden, viz nize)
s = nahrad(s, '''            slider("shelf", "g_frame", 0, S.MAX_POLIC, 1, "ks", t["help_shelf"]),
''', '''            slider("shelf", "g_frame", 0, S.MAX_POLIC, 1, "ks", t["help_shelf"]),
            {**toggle("shelfboard", "g_frame"), "help": t["help_shelfboard"]},
''', "schema")

# 4) normalizace: bez spodnich polic je 'bez desky' bezpredmetne (server hodnotu ignoruje, vyber vrati s deskou)
s = nahrad(s, '''    p["police"] = int(_cislo(sel["shelf"], 0, S.MAX_POLIC, 1, 1))
''', '''    p["police"] = int(_cislo(sel["shelf"], 0, S.MAX_POLIC, 1, 1))
    if p["police"] < 1:
        p["police_deska"] = True                                  # bez spodnich polic volba 'bez desky' neexistuje (slot je skryty, hodnotu server ignoruje)
''', "normalizuj")

# 4b) options: bez spodnich polic slot neexistuje (UI ho nevykresli; options.<slot>.hidden je dolozeny mechanismus modulu voleb)
s = nahrad(s, '''    for sid, par in SLIDERY.items():
        lo, hi = S.ROZSAH[par]
''', '''    if p["police"] < 1:
        options["shelfboard"]["hidden"] = True                    # bez spodnich polic volba 'bez desky' neexistuje (slot se nevykresli, hodnotu server ignoruje - viz normalizuj)
    for sid, par in SLIDERY.items():
        lo, hi = S.ROZSAH[par]
''', "options_hidden")

# 5) podepsany odkaz na model: klic "B" jen u polic bez desky (starsi tokeny a vychozi = s deskou beze zmeny)
s = nahrad(s, '''    hs = [p.get(f"police_h{k}") for k in range(1, S.MAX_POLIC + 1)]
''', '''    if p.get("police") and not p.get("police_deska", True):
        out["B"] = 0                                                                         # spodni police BEZ DESKY (Robert 2026-10-07; bez klice = s deskou)
    hs = [p.get(f"police_h{k}") for k in range(1, S.MAX_POLIC + 1)]
''', "zabal")
s = nahrad(s, '''    p["suplik_vlevo"] = bool(o.get("f"))
''', '''    p["police_deska"] = "B" not in o
    p["suplik_vlevo"] = bool(o.get("f"))
''', "rozbal")

# 6) shrnuti voleb (doklad / nabidka): deska polic se ukaze jen kdyz je pryc, shrnuti vychoziho stolu zustava
s = nahrad(s, '''    for k in range(1, S.MAX_POLIC + 1):                           # vyska polic se ve shrnuti ukaze jen u existujici police s ruzne zadanou hodnotou
''', '''    if sel.get("shelfboard", True) or not sel.get("shelf"):
        skryt.add("shelfboard")                                  # deska spodnich polic se ve shrnuti ukaze jen kdyz je pryc (vychozi = s deskou; shrnuti vychoziho stolu zustava)
    for k in range(1, S.MAX_POLIC + 1):                           # vyska polic se ve shrnuti ukaze jen u existujici police s ruzne zadanou hodnotou
''', "souhrn")

# 7) odkaz na vyrobni list / sestavu pro zamestnance: vychozi hodnota (s deskou) se do odkazu nedava (odkazy beze zmeny)
s = nahrad(s, '''and not (k == "panely_delka" and int(round(float(v))) == S.PANEL_DELKA_VYCHOZI)})''',
           '''and not (k == "panely_delka" and int(round(float(v))) == S.PANEL_DELKA_VYCHOZI) and not (k == "police_deska" and v)})''', "qs")

open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
