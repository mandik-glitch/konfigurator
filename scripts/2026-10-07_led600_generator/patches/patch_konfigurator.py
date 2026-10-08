#!/usr/bin/env python3
"""Zaplata api/stul_konfigurator.py: DELKA LED SVITIDLA (Robert 2026-10-07: "LED 600 doplnit do generatoru"; karta #5359 LED600, GLB product_5359.glb = LED 1200 zkracena o 600 mm).
Parametr `led_delka` (1200 | 600, vychozi 1200 = beze zmeny vseho stavajiciho; vsechna svitidla stolu stejne dlouha), LED_TYPY, delka tělesa z GLB, skupina LED s dilem zvolene delky,
`led_info` (typy + zda se vejdou), 3D menu "Zvolit LED N mm", PREPINAC_DILU / _NAZVY / pevne / _CISLA. Kotvene nahrady (assert count == 1) proti ZIVEMU souboru.
Pouziti: patch_konfigurator.py <vstup stul_konfigurator.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


# 1) konstanty: typy a delky LED
s = nahrad(s, '''MIN_PODIL_PROFILU_LED = 0.9        # podelny profil nad LED je dany mezerou mezi nohami, ale nejkratsi mozny = 90 % delky svetla (Robert; svetla budou i v jinych delkach)
''', '''MIN_PODIL_PROFILU_LED = 0.9        # podelny profil nad LED je dany mezerou mezi nohami, ale nejkratsi mozny = 90 % delky svetla (Robert; svetla budou i v jinych delkach)
# DELKY LED (Robert 2026-10-07: "LED 600 doplnit do generatoru"): nominalni delka svitidla (mm) -> dil katalogu (karta #5359 LED600: GLB = LED 1200 zkracena o 600 mm, STEJNA lokalni souradnicova soustava
# a STEJNY stred bboxu jako product_4929, X = delka; sablonovy clen LED se klonuje se stejnou polohou / otocenim, jen s jinym dilem). Delka TELESA vc. koncovek se bere z GLB (`led_telo_dilu`: 1247 / 647 mm);
# vsechna svitidla stolu jsou stejne dlouha (`led_delka`, vychozi 1200 = beze zmeny stavajicich konfiguraci i hashu).
LED_PART = "product_4929"
LED_TYPY = {1200: LED_PART, 600: "product_5359"}
LED_DELKY = tuple(sorted(LED_TYPY))
LED_DELKA_VYCHOZI = 1200
LED_PARTY = frozenset(LED_TYPY.values())
''', "konstanty")

# 2) VYCHOZI
s = nahrad(s, '''    "led_svetlo": True,           # Robert 2026-10-04: samotne SVITIDLO LED lze odebrat, profily (ramena + pricny profil) zustanou; relevantni jen kdyz led a stojky
''', '''    "led_svetlo": True,           # Robert 2026-10-04: samotne SVITIDLO LED lze odebrat, profily (ramena + pricny profil) zustanou; relevantni jen kdyz led a stojky
    "led_delka": float(LED_DELKA_VYCHOZI),    # Robert 2026-10-07: delka svitidel LED (1200 | 600 mm; viz LED_TYPY); vsechna svitidla stolu jsou stejna; relevantni jen kdyz led, stojky a svitidlo
''', "VYCHOZI")

# 3) _norm_parametry
s = nahrad(s, '''    out["led_svetlo"] = bool(out["led_svetlo"])
''', '''    out["led_svetlo"] = bool(out["led_svetlo"])
    ld_ = out["led_delka"]
    if isinstance(ld_, bool) or not isinstance(ld_, (int, float)) or not math.isfinite(ld_) or abs(ld_ - round(ld_)) > 1e-6 or int(round(ld_)) not in LED_TYPY:
        raise StulChyba(f"led_delka: {ld_!r} neni jedna z delek LED svitidla {', '.join(str(d_) for d_ in LED_DELKY)} mm", "mimo_rozsah")
    out["led_delka"] = float(int(round(ld_)))
''', "norm")

# 4) pomocne funkce delky tělesa (pred kvat_na_matici)
s = nahrad(s, '''def kvat_na_matici(q):
''', '''_LED_TELO = {}


def _led_delka_int(delka):
    """Delka svitidla LED jako cele cislo z LED_TYPY (jinak StulChyba)."""
    d = int(round(float(delka)))
    if d not in LED_TYPY:
        raise StulChyba(f"led_delka: {delka!r} neni jedna z delek LED svitidla {', '.join(str(x) for x in LED_DELKY)} mm", "mimo_rozsah")
    return d


def _led_telo_presne(part_id):
    """Delka tělesa svitidla (mm) z GLB (accessor min/max): osa delky = lokalni X (sablonovy clen LED ji otaci do sirky stolu)."""
    lo, hi = glb_bbox(part_id)
    return float(hi[0] - lo[0])


def led_telo_dilu(part_id):
    """Delka TELESA svitidla vc. koncovek (mm, zaokrouhleno na cele mm jako LED_SIRKA = 1247 u product_4929) podle GLB dilu; vychozi svitidlo vraci konstantu LED_SIRKA (hodnota se nesmi zmenit).
    Chybi-li GLB dilu, vyhodi StulChyba (volitelna delka se pak nenabizi, vychozi cesta nespadne)."""
    if part_id == LED_PART:
        return LED_SIRKA
    v = _LED_TELO.get(part_id)
    if v is None:
        v = _LED_TELO[part_id] = float(round(_led_telo_presne(part_id)))
    return v


def kvat_na_matici(q):
''', "pomocne_fce")

# 5) skupina LED podle sirky: dil zvolene delky, rozteč = delka tělesa
s = nahrad(s, '''    if (p["led"] and p["stojky"] and p["led_svetlo"]):
        n_l = max(1, int((p["sirka"] + LED_PREVIS) // LED_SIRKA))
        zakl = clenove[("t", LED)]
        zakl["pos"][0] += x_led
        zakl["pos"][2] += (0 - (n_l - 1) / 2.0) * LED_SIRKA
        for k in range(1, n_l):
            kl = _klon(sab, LED, zakl["pos"] + np.array([0, 0, k * LED_SIRKA]))
            clenove[("led", k)] = kl
''', '''    if (p["led"] and p["stojky"] and p["led_svetlo"]):
        d_led = _led_delka_int(p["led_delka"])                       # delka svitidel (vsechna stejna): dil katalogu zvolene delky, rozteč = delka jeho tělesa z GLB (1200: 1247, 600: 647 mm)
        s_led = led_telo_dilu(LED_TYPY[d_led])
        n_l = max(1, int((p["sirka"] + LED_PREVIS) // s_led))
        zakl = clenove[("t", LED)]
        zakl["part_id"] = LED_TYPY[d_led]                            # clen sablony nese dil 1200; jina delka = jiny dil se STEJNYM otocenim a polohou (stejny stred bboxu)
        zakl["pos"][0] += x_led
        zakl["pos"][2] += (0 - (n_l - 1) / 2.0) * s_led
        for k in range(1, n_l):
            kl = _klon(sab, LED, zakl["pos"] + np.array([0, 0, k * s_led]))
            kl["part_id"] = LED_TYPY[d_led]
            clenove[("led", k)] = kl
    else:
        p["led_delka"] = float(LED_DELKA_VYCHOZI)                    # bez svitidla (vypnute LED / stojky / svitidlo, nebo odebrane, protoze se nevejde) delka nic nedela
''', "umisteni")

# 6) kontrola profilu nad LED: soucet delek tělesa svitidel (stejne jako n x LED_SIRKA u vychoziho svitidla)
s = nahrad(s, '''        delka_svetla = led_idx_n * LED_SIRKA
''', '''        delka_svetla = sum(led_telo_dilu(c["part_id"]) for c in clenove.values() if c["druh"] == "prisl" and c["src"] == LED)          # = led_idx_n x delka tělesa svitidla (1247 u 1200)
''', "kontrola_profilu")

# 7) led_info (typy svitidel a zda se vejdou) po kontrole sestavy
s = nahrad(s, '''    problemy = _zkontroluj(dily, bb, clenove, spojky, idx, konce_ocek, (xf, xr, zl, zr))
''', '''    problemy = _zkontroluj(dily, bb, clenove, spojky, idx, konce_ocek, (xf, xr, zl, zr))
    led_info = {"delka": int(round(float(p["led_delka"]))), "typy": []}               # delky svitidel LED a zda se na tento stul vejdou (stejne vzorce jako kontroly `mimo_obrys` a `profil_led_kratky`)
    if p["led"] and p["stojky"] and p["led_svetlo"]:
        wout = float(zr - zl + 2 * _H())
        dp_led = 1000.0 * clenove[("t", ZRAIL_TOP)]["scale"][1] if ("t", ZRAIL_TOP) in clenove else None
        for d_led in LED_DELKY:
            try:
                telo_l, presne_l = led_telo_dilu(LED_TYPY[d_led]), _led_telo_presne(LED_TYPY[d_led])
            except StulChyba:
                continue                                                           # GLB teto delky v katalogu chybi: delka se nenabizi
            n_t = max(1, int((p["sirka"] + LED_PREVIS) // telo_l))
            presah_t = (n_t - 1) * telo_l + presne_l - wout
            led_info["typy"].append({"delka": d_led, "telo": telo_l, "pocet": n_t, "min_sirka": int(math.ceil(telo_l - LED_PREVIS)),
                                     "vejde": bool(presah_t <= LED_PREVIS + 1.0 and (dp_led is None or dp_led >= MIN_PODIL_PROFILU_LED * n_t * telo_l - 0.01))})
''', "led_info")
s = nahrad(s, '''        "panely_info": panely_info,
''', '''        "panely_info": panely_info,
        "led_info": led_info,
''', "led_info_vysledek")

# 8) prepinac dilu, nazvy
s = nahrad(s, '''**{pid_: "panely" for pid_ in PANEL_PARTY}, "product_4929": "led", "product_4932": "elektrozlab",''',
           '''**{pid_: "panely" for pid_ in PANEL_PARTY}, **{pid_: "led" for pid_ in LED_PARTY}, "product_4932": "elektrozlab",''', "PREPINAC_DILU")
s = nahrad(s, '''_NAZVY.update({"product_4956": "šuplíkový box (1 šuplík)", "product_4957": "šuplíkový box (3 šuplíky)"})
''', '''_NAZVY.update({"product_4956": "šuplíkový box (1 šuplík)", "product_4957": "šuplíkový box (3 šuplíky)"})
_NAZVY.update({pid_: f"LED osvětlení {d_} mm" for d_, pid_ in LED_TYPY.items() if pid_ != LED_PART})        # delka v nazvu: kusovnik / nabidka rozlisi delky (LED 1200 beze zmeny)
''', "NAZVY")

# 9) vstup z dotazu (cislo)
s = nahrad(s, '''"stojky_vyska", "navlek_delka", "panely_delka") + VYREZY_CISLA''', '''"stojky_vyska", "navlek_delka", "panely_delka", "led_delka") + VYREZY_CISLA''', "CISLA")

# 10) 3D menu: delka svitidla
s = nahrad(s, '''    led_ids = skupina("led", "LED osvětlení", lambda k, rl, d: d["part_id"] == "product_4929" or k in (("t", XRAIL_TOP_L), ("t", XRAIL_TOP_P), ("t", ZRAIL_TOP)), ["led", "led_rameno", "vzpery", "led_svetlo"],
                      [pol("Odebrat LED osvětlení", {"led": False}),
                       pol("Vrátit svítidlo LED" if not p["led_svetlo"] else "Odebrat jen svítidlo LED (profily zůstanou)", {"led_svetlo": not p["led_svetlo"]})]
                      + ([pol("Přidat vzpěry ramen LED", {"vzpery": True})] if not p["vzpery"] and p["stojky"] and _sd()["vzpery"] else []))''',
           '''    menu_led_delky = []
    for t_ in ((r.get("led_info") or {}).get("typy") or []):                                  # delka svitidla LED (Robert 2026-10-07): ostatni delky jako volby v menu; ktera se nevejde, je zakazana s duvodem
        if p["led"] and p["stojky"] and p["led_svetlo"] and t_["delka"] != int(p["led_delka"]):
            menu_led_delky.append(pol(f"Zvolit LED {t_['delka']} mm", {"led_delka": float(t_["delka"])}, None if t_["vejde"] else "Tahle délka LED se sem nevejde (širší stůl)."))
    led_ids = skupina("led", "LED osvětlení", lambda k, rl, d: d["part_id"] in LED_PARTY or k in (("t", XRAIL_TOP_L), ("t", XRAIL_TOP_P), ("t", ZRAIL_TOP)), ["led", "led_delka", "led_rameno", "vzpery", "led_svetlo"],
                      [pol("Odebrat LED osvětlení", {"led": False}),
                       pol("Vrátit svítidlo LED" if not p["led_svetlo"] else "Odebrat jen svítidlo LED (profily zůstanou)", {"led_svetlo": not p["led_svetlo"]})]
                      + menu_led_delky
                      + ([pol("Přidat vzpěry ramen LED", {"vzpery": True})] if not p["vzpery"] and p["stojky"] and _sd()["vzpery"] else []))''', "menu")

# 11) rameno LED: pevne dily (svitidlo jede s pricnou)
s = nahrad(s, '''        pevne = [i for i in range(n) if klice_t[i] == ("t", ZRAIL_TOP) or dily[i]["part_id"] == "product_4929"]''',
           '''        pevne = [i for i in range(n) if klice_t[i] == ("t", ZRAIL_TOP) or dily[i]["part_id"] in LED_PARTY]''', "pevne")

open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
